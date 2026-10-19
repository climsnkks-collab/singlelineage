"""Fresh UI-thread primitive observation. No input, Use, send or effect authority.

The Native source owner path decides the supported model-state subset
(current0105: normal0..2). Missing/REFUSED is UNKNOWN data, never false D4. One existing Native queue
sequence; no action/public reply is modified. Cache contains no native pointers.
"""
from __future__ import annotations
import asyncio
import threading
import time
from types import MethodType

from tools.local_original_session import commands, inventory, manual_move_commands as m, observe

MESSAGE = 'LC-Owned-ItemEquipmentUIObserve-v1'
REQUEST = 'own-item-equipment-ui-observe-request-v1'
RESULT = 'own-item-equipment-ui-observe-result-v1'
COMMAND = 'ObserveItemEquipmentUI'
need = observe.need
_CURRENT, _WINDOW = m.ManualMoveCommands._current, m.ManualMoveCommands._window
_CURRENT_SELECTOR = object()


def _empty(reason):
    return dict(status='UNKNOWN', reason=reason, invoked=False, observed=False,
                model_uid=None, model_d4=None, native_sequence=None,
                source_pid=None, source_birth=None, source_image_sha256=None,
                player_uid=None, item_identifier=None, map_id=None,
                query_started_monotonic_ns=None, cleanup_required=False)


class ItemEquipmentUIObserver:
    def __init__(self, manual, *, collection_policy=None):
        from tools.local_original_session.launcher import ManualMoveRequests
        need(type(manual) is ManualMoveRequests and type(manual.consumer) is m.ManualMoveCommands,
             'UI_OBSERVE_ORIGINAL_MANUAL_REQUIRED')
        self.manual, self.consumer = manual, manual.consumer
        need(collection_policy is None or type(collection_policy) is str
             and collection_policy == inventory.COLLECTION_POLICY,
             'UI_OBSERVE_COLLECTION_POLICY_REQUIRED')
        self.collection_policy = collection_policy
        self._collection_current(manual.inventory_broker)
        self._item_identifier = None
        self._pending = None
        self._closed = self._terminal = False
        self._thread = threading.get_ident()
        self._life = None
        self._requested = False
        self._request_life = None
        self.last_sample_monotonic_ns = None
        self.last_result = _empty('NOT_SAMPLED')

    def request(self, item_identifier=None):
        """Queue one current life, no Native seq/query and no expected value."""
        if self._closed or self._terminal:
            return False
        if item_identifier is not None and not (type(item_identifier) is int and 0 < item_identifier <= 0xffffffff):
            return False  # Never replace a pending request/cache with invalid input.
        if self._pending is not None or self._requested:
            # Compare only the already fixed request; no new authority or
            # selector may be produced while the original queue owns it.
            try:
                life = self._request_life if self._request_life is not None else self._pending[2]
                wanted = self._items(life[4])[0].identifier if item_identifier is None else item_identifier
                return wanted == life[6]
            except Exception:
                return False
        try:
            _, self._request_life = self._current(item_identifier=item_identifier)
            self._item_identifier = self._request_life[6]
            self._requested = True
            self.last_result = _empty('UI_OBSERVE_REQUESTED')
            self._life = self._request_life  # Tag null cache only, never a Native lease.
            return True
        except Exception as error:
            self._unknown(observe.reason(error))
            return False

    def _collection_current(self, broker):
        actual = getattr(broker, '_inventory_collection_policy', None)
        need((self.collection_policy is None and actual is None)
             or (type(self.collection_policy) is str and type(actual) is str
                 and self.collection_policy == actual == inventory.COLLECTION_POLICY),
             'UI_OBSERVE_COLLECTION_POLICY_CHANGED')

    def _items(self, frame):
        return ((inventory.validate_frame(frame),) if self.collection_policy is None else
                inventory.validate_collection_frame(frame, policy=self.collection_policy))

    def _item(self, frame, identifier):
        items = self._items(frame)
        if identifier is None:
            return items[0]
        matches = [item for item in items if type(identifier) is int and item.identifier == identifier]
        need(len(matches) == 1, 'UI_OBSERVE_CURRENT_MEMBER_REQUIRED')
        return matches[0]

    def _current(self, *, item_identifier=_CURRENT_SELECTOR):
        manual, consumer = self.manual, self.consumer
        need(not self._closed and not manual.closed and not manual._resources_closed
             and threading.get_ident() == self._thread and manual.consumer is consumer
             and manual._actual_manual_producer(asynchronous=True) is consumer,
             'UI_OBSERVE_CURRENT_CONSUMER_REQUIRED')
        for name, original in (('_current', _CURRENT), ('_window', _WINDOW)):
            method = getattr(consumer, name)
            need(type(method) is MethodType and method.__self__ is consumer
                 and method.__func__ is original and getattr(type(consumer), name) is original,
                 'UI_OBSERVE_ORIGINAL_METHOD_REQUIRED')
        current = _CURRENT(consumer)
        broker, writer = current[0].broker, current[0].writer
        need(broker is manual.inventory_broker, 'UI_OBSERVE_SAME_BROKER_REQUIRED')
        self._collection_current(broker)
        generation = manual._inventory_reselection_current(writer)
        need(generation is not None and generation.phase == 'ACTIVE'
             and not generation.service._closed and generation.current_frame is broker._inventory_current_frame
             and type(generation.current_frame) is bytes and generation.delivery_authority is not None
             and generation.write_attempted is True and generation.attempted is True,
             'UI_OBSERVE_DELIVERED_CURRENT_GENERATION_REQUIRED')
        if self.collection_policy is not None:
            need(type(generation.service) is inventory.InventoryService
                 and generation.service is broker._inventory_service
                 and generation.service.broker is broker and generation.service.reader is consumer.reader
                 and generation.service._collection_policy == self.collection_policy,
                 'UI_OBSERVE_COLLECTION_SERVICE_CHANGED')
        chosen = self._item_identifier if item_identifier is _CURRENT_SELECTOR else item_identifier
        info = self._item(generation.current_frame, chosen)
        need(current[6]['candidate_sha256'] == m.USE_ITEM_IMAGE_SHA,
             'UI_OBSERVE_PROGRAM_IMAGE_REQUIRED')
        # Exact selected lifetime + canonical current row, not a new generation,
        # admission receipt or public Intent. Frame identity change invalidates it.
        life = (writer, generation, generation.selected, generation.service,
                generation.current_frame, current[1], info.identifier, current[3].uid, current[3].map_id)
        return current, life

    @staticmethod
    def _same(left, right):
        return (all(a is b for a, b in zip(left[:6], right[:6])) and left[6:] == right[6:])

    def _unknown(self, reason, *, terminal=False):
        self._terminal |= terminal
        if self._terminal:
            self._requested = False
        self.last_result = _empty(reason)
        self.last_result['cleanup_required'] = self._terminal
        return dict(self.last_result)

    def observation(self):
        if self._closed:
            return self._unknown('UI_OBSERVE_CLOSED')
        try:
            _, life = self._current()
            if self._life is not None and not self._same(self._life, life):
                return self._unknown('UI_OBSERVE_SELECTION_CHANGED')
        except Exception:
            return self._unknown('UI_OBSERVE_NO_CURRENT_SELECTION')
        return dict(self.last_result)

    def collect(self):
        """File-only collection. No typed read/query or message publication."""
        pending = self._pending
        if pending is None:
            return self.observation()
        request, path, life, started = pending
        try:
            # Read even after selection/close to observe the original Native
            # completion/cleanup. No new dispatch before that completion.
            try:
                row = commands._json(path, 2048)
            except ValueError as error:
                # Recollect only the same posted result, with the original
                # byte bound/deadline. Ambient LastError is not evidence.
                metadata = getattr(error, 'input_read_metadata', None)
                publication_pending = False
                if (type(error) is ValueError and type(metadata) is dict
                        and set(metadata) == {'stage', 'winerror', 'same_file'}
                        and type(metadata['stage']) is str):
                    publication_pending = (
                        error.args == ('INPUT_REQUEST_OPEN_FAILED',) and metadata['stage'] == 'OPEN'
                        and type(metadata['winerror']) is int and metadata['winerror'] in (32, 33)
                        and metadata['same_file'] is False
                        or error.args == ('INPUT_REQUEST_CHANGED',)
                        and metadata['stage'] == 'FINAL_SIZE_OR_MTIME'
                        and metadata['winerror'] is None and metadata['same_file'] is True)
                if not publication_pending:
                    raise
                need(time.monotonic_ns() - started < m.WAIT_NS,
                     'UI_OBSERVE_REPLY_DEADLINE')
                return dict(self.last_result)
            expected = dict(request, schema=RESULT)
            need(set(row) == set(expected) | {'status', 'reason', 'invoked', 'observed', 'model_uid', 'model_d4'}
                 and all(type(row[k]) is type(v) and row[k] == v for k, v in expected.items()),
                 'UI_OBSERVE_REPLY_IDENTITY_REQUIRED')
            need(type(row['status']) is str and row['status'] in ('OBSERVED', 'REFUSED', 'CODE_ANCHOR_BLOCKED', 'UNKNOWN')
                 and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
                 and row['invoked'] is False and type(row['observed']) is bool,
                 'UI_OBSERVE_REPLY_TYPES_REQUIRED')
            need((row['status'] == 'OBSERVED' and row['observed'] is True
                  and type(row['model_uid']) is int and row['model_uid'] == request['item_identifier']
                  and type(row['model_d4']) is bool and row['reason'] == 0)
                 or (row['status'] != 'OBSERVED' and row['observed'] is False
                     and row['model_uid'] is None and row['model_d4'] is None),
                 'UI_OBSERVE_REPLY_PRIMITIVES_REQUIRED')
            if row['status'] == 'UNKNOWN':
                self._terminal = True
            self._pending = None
            self._requested = False
            self._request_life = None
            if row['status'] != 'UNKNOWN' and self.consumer._readonly_pending is self:
                self.consumer._readonly_pending = None
            if self._closed:
                return self._unknown('UI_OBSERVE_CLOSED')
            if self._terminal:
                return self._unknown('UI_OBSERVE_TERMINAL', terminal=True)
            current, actual = self._current()
            if not self._same(life, actual):
                self._requested = False
                return self._unknown('UI_OBSERVE_SELECTION_CHANGED')
            need(time.monotonic_ns() - started < m.WAIT_NS, 'UI_OBSERVE_REPLY_DEADLINE')
            self._life = life
            if row['status'] == 'OBSERVED':
                self._requested = False
                self._request_life = None
            self.last_result = dict(status=row['status'], reason=row['reason'], invoked=False,
                observed=row['observed'], model_uid=row['model_uid'], model_d4=row['model_d4'],
                native_sequence=request['seq'], source_pid=request['pid'], source_birth=request['birth'],
                source_image_sha256=request['candidate_sha256'], player_uid=request['player_uid'],
                item_identifier=request['item_identifier'], map_id=request['map_id'],
                query_started_monotonic_ns=started, cleanup_required=False)
            return dict(self.last_result)
        except FileNotFoundError:
            if time.monotonic_ns() - started >= m.WAIT_NS:
                return self._unknown('UI_OBSERVE_REPLY_DEADLINE', terminal=True)
            return dict(self.last_result)
        except Exception as error:
            # Unknown completion does not free the Native slot; root cleanup is
            # required. A valid old-generation completed reply above frees it.
            return self._unknown(observe.reason(error), terminal=self._pending is not None)

    async def sample(self):
        """Use one serial sample slot; pending action/busy always has priority."""
        consumer, manual = self.consumer, self.manual
        if (self._closed or self._terminal or self._pending is not None or manual.closed
                or manual.pending or manual._polling or manual._inventory_request is not None
                or manual._inventory_wait is not None or consumer.pending is not None
                or consumer._busy or consumer._readonly_pending is not None):
            return False
        now = time.monotonic_ns()
        previous = max((n for n in (self.last_sample_monotonic_ns,
            manual.last_sample_monotonic_ns) if n is not None), default=None)
        if previous is not None and now - previous < m.SAMPLE_NS:
            return False
        entered = False
        try:
            current, life = self._current()
            if self._request_life is not None and not self._same(self._request_life, life):
                self._requested = False
                self._unknown('UI_OBSERVE_SELECTION_CHANGED')
                return False
            row, writer = current[1], current[0].writer
            async with row['operation_lock']:
                need(not self._closed and not consumer._busy and consumer.pending is None,
                     'UI_OBSERVE_PENDING_CHANGED')
                consumer._busy, entered = True, True
                broker = current[0].broker
                need(await broker._movement_owner(writer, row, current[3]) is True,
                     'UI_OBSERVE_NATIVE_OWNER_REQUIRED')
                current, after = self._current()
                need(self._same(life, after), 'UI_OBSERVE_SELECTION_CHANGED')
                hwnd = _WINDOW(consumer, current)
                need(consumer.sequence < m.MAX_SEQUENCE, 'UI_OBSERVE_SEQUENCE_EXHAUSTED')
                consumer.sequence += 1  # Shared original consumer; action cache untouched.
                seq, boundary, identity = consumer.sequence, current[5], current[6]
                request = dict(schema=REQUEST, **identity, seq=seq, command=COMMAND,
                    player_uid=current[3].uid, item_identifier=life[6], map_id=current[3].map_id)
                path = boundary / ('item-equipment-ui-observe-result-' + str(seq) + '.json')
                commands._ordinary(path, absent=True)
                m._create_once(boundary / ('item-equipment-ui-observe-request-' + str(seq) + '.json'), request)
                user = consumer.reader.owner.native.u
                message = int(user.RegisterWindowMessageW(MESSAGE))
                need(0xc000 <= message <= 0xffff, 'UI_OBSERVE_MESSAGE_REQUIRED')
                final, final_life = self._current()
                need(self._same(life, final_life) and _WINDOW(consumer, final) == hwnd,
                     'UI_OBSERVE_PREPOST_CHANGED')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                self._pending = (request, path, life, now)
                consumer._readonly_pending = self
                self._life = life
                self.last_sample_monotonic_ns = now
                self.last_result = _empty('UI_OBSERVE_PENDING')
                owner = consumer.reader.owner
                desktop = getattr(owner, 'private_desktop', None)
                if desktop is not None:
                    need(desktop.post_command(owner, identity, hwnd, owner.child.tid, message, seq)
                         is True, 'UI_OBSERVE_POST_UNKNOWN')
                else:
                    need(user.PostMessageW(hwnd, message, seq, 0), 'UI_OBSERVE_POST_UNKNOWN')
                final, final_life = self._current()
                need(self._same(life, final_life) and _WINDOW(consumer, final) == hwnd,
                     'UI_OBSERVE_POST_CHANGED')
            self.collect()
            return True
        except asyncio.CancelledError:
            self._unknown('UI_OBSERVE_CANCELLED', terminal=True)
            raise
        except Exception as error:
            self._unknown(observe.reason(error), terminal=True)
            return self.last_sample_monotonic_ns == now
        finally:
            if entered:
                consumer._busy = False

    def close(self):
        self._closed = True
        self._requested = False
        self.last_result = _empty('UI_OBSERVE_CLOSED')
        # Preserve unresolved queue ownership. No guessed cleanup or new action.
        if self._pending is not None:
            self.collect()
