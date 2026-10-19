"""Explicit OpenInventoryUI action. Original queue reservation, no Use/effect authority.
The historical _readonly_pending field is an opaque shared Native reservation.
No engine pointer/callback construction or cached UI pointers cross this call.
"""
from __future__ import annotations
import asyncio
import threading
import time
from types import MethodType

from tools.local_original_session import commands, inventory, manual_move_commands as m, observe

MESSAGE = 'LC-Owned-InventoryUIOpen-v1'
REQUEST = 'own-inventory-ui-open-request-v1'
RESULT = 'own-inventory-ui-open-result-v1'
COMMAND = 'OpenInventoryUI'
AFTER_MESSAGE = 'LC-Owned-InventoryUICurrentAfterReselect-v1'
AFTER_REQUEST = 'own-inventory-ui-current-after-reselect-request-v1'
AFTER_RESULT = 'own-inventory-ui-current-after-reselect-result-v1'
AFTER_COMMAND = 'InventoryUICurrentAfterReselect'
AFTER_STEM = 'inventory-ui-current-after-reselect'
need = observe.need
_CURRENT, _WINDOW = m.ManualMoveCommands._current, m.ManualMoveCommands._window


def _empty(reason):
    return dict(status='UNKNOWN', reason=reason, invoked=None, opened=None,
                before_own_visible=None, after_own_visible=None, native_sequence=None,
                source_pid=None, source_birth=None, source_image_sha256=None,
                player_uid=None, item_identifier=None, map_id=None,
                query_started_monotonic_ns=None, cleanup_required=False)


def current_after_reselect_reply(row, request):
    """Strict new Native DTO; never promote a known-current observation to Open."""
    expected = dict(request, schema=AFTER_RESULT)
    fields = {'status', 'reason', 'invoked', 'opened', 'before_own_visible',
              'after_own_visible', 'branch', 'current_own_visible'}
    need(type(row) is dict and set(row) == set(expected) | fields
         and all(type(row[k]) is type(v) and row[k] == v for k, v in expected.items()),
         'INVENTORY_UI_CURRENT_REPLY_IDENTITY_REQUIRED')
    need(type(row['status']) is str and row['status'] in
         ('RETURNED', 'OBSERVED_ALREADY_OPEN', 'REFUSED', 'CODE_ANCHOR_BLOCKED', 'UNKNOWN')
         and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
         and type(row['invoked']) is bool, 'INVENTORY_UI_CURRENT_REPLY_TYPES_REQUIRED')
    opened = (row['status'] == 'RETURNED' and row['reason'] == 0 and row['invoked'] is True
         and row['opened'] is True and row['before_own_visible'] is False
         and row['after_own_visible'] is True and row['branch'] == 'OPEN_RETURNED'
         and row['current_own_visible'] is None)
    current = (row['status'] == 'OBSERVED_ALREADY_OPEN' and row['reason'] == 0
         and row['invoked'] is False and row['opened'] is None
         and row['before_own_visible'] is True and row['after_own_visible'] is None
         and row['branch'] == 'ALREADY_OPEN_CURRENT' and row['current_own_visible'] is True)
    failed = (row['status'] in ('REFUSED', 'CODE_ANCHOR_BLOCKED', 'UNKNOWN')
         and (row['status'] == 'UNKNOWN' or row['invoked'] is False)
         and all(row[k] is None for k in
             ('opened', 'before_own_visible', 'after_own_visible', 'branch', 'current_own_visible')))
    need(opened or current or failed, 'INVENTORY_UI_CURRENT_REPLY_PRIMITIVES_REQUIRED')
    return row


class InventoryUIOpen:
    def __init__(self, manual, *, collection_policy=None):
        from tools.local_original_session.launcher import ManualMoveRequests
        need(type(manual) is ManualMoveRequests and type(manual.consumer) is m.ManualMoveCommands,
             'INVENTORY_UI_OPEN_ORIGINAL_MANUAL_REQUIRED')
        self.manual, self.consumer = manual, manual.consumer
        need(collection_policy is None or type(collection_policy) is str
             and collection_policy == inventory.COLLECTION_POLICY,
             'INVENTORY_UI_OPEN_COLLECTION_POLICY_REQUIRED')
        self.collection_policy = collection_policy
        self._collection_current(manual.inventory_broker)
        self._pending = None
        self._closed = self._terminal = False
        self._thread = threading.get_ident()
        self._life = None
        self._requested = False
        self._request_life = None
        self._claimed = False
        self._retire_attempted = False
        self._completion = None
        self._current_after_reselect = False
        self._current_after_reselect_proof = None
        self._reselect_current_original = ManualMoveRequests._source_reselect_current
        self._invoke_observed = None
        self.last_sample_monotonic_ns = None
        self.last_result = _empty('NOT_SAMPLED')

    def _collection_current(self, broker):
        actual = getattr(broker, '_inventory_collection_policy', None)
        need((self.collection_policy is None and actual is None)
             or (type(self.collection_policy) is str and type(actual) is str
                 and self.collection_policy == actual == inventory.COLLECTION_POLICY),
             'INVENTORY_UI_OPEN_COLLECTION_POLICY_CHANGED')

    def request(self):
        """Queue one explicit action; no query/seq until the serial slot admits it."""
        if self._closed or self._terminal:
            return False
        if self._pending is not None or self._requested:
            return True  # Existing request only; never reset or promote cache.
        if self._claimed:
            return False
        try:
            _, self._request_life = self._current()
            self._requested = True
            self.last_result = _empty('INVENTORY_UI_OPEN_REQUESTED')
            self._life = self._request_life  # Tag null cache only, never a Native lease.
            return True
        except Exception as error:
            self._unknown(observe.reason(error))
            return False

    def _current(self):
        manual, consumer = self.manual, self.consumer
        need(not self._closed and not manual.closed and not manual._resources_closed
             and threading.get_ident() == self._thread and manual.consumer is consumer
             and manual._actual_manual_producer(asynchronous=True) is consumer,
             'INVENTORY_UI_OPEN_CURRENT_CONSUMER_REQUIRED')
        for name, original in (('_current', _CURRENT), ('_window', _WINDOW)):
            method = getattr(consumer, name)
            need(type(method) is MethodType and method.__self__ is consumer
                 and method.__func__ is original and getattr(type(consumer), name) is original,
                 'INVENTORY_UI_OPEN_ORIGINAL_METHOD_REQUIRED')
        current = _CURRENT(consumer)
        broker, writer = current[0].broker, current[0].writer
        need(broker is manual.inventory_broker, 'INVENTORY_UI_OPEN_SAME_BROKER_REQUIRED')
        self._collection_current(broker)
        if getattr(broker, '_item_transfer_policy_bound', None) is not None:
            from tools.local_original_session.item_transfer_session import ItemTransferSession
            transfer = broker._inventory_generation.transfer_session
            need(type(transfer) is ItemTransferSession, 'INVENTORY_UI_OPEN_REAL_CUSTODY_SESSION_REQUIRED')
            transfer.helper_open_allowed(writer)
        generation = manual._inventory_reselection_current(writer)
        need(generation is not None and generation.phase == 'ACTIVE'
             and not generation.service._closed and generation.current_frame is broker._inventory_current_frame
             and type(generation.current_frame) is bytes and generation.delivery_authority is not None
             and generation.write_attempted is True and generation.attempted is True,
             'INVENTORY_UI_OPEN_DELIVERED_CURRENT_GENERATION_REQUIRED')
        if self.collection_policy is None:
            info = inventory.validate_frame(generation.current_frame)
        else:
            need(type(generation.service) is inventory.InventoryService
                 and generation.service is broker._inventory_service
                 and generation.service.broker is broker and generation.service.reader is consumer.reader
                 and generation.service._collection_policy == self.collection_policy,
                 'INVENTORY_UI_OPEN_COLLECTION_SERVICE_CHANGED')
            info = inventory.validate_collection_frame(generation.current_frame, policy=self.collection_policy)[0]
        need(current[6]['candidate_sha256'] == m.USE_ITEM_IMAGE_SHA,
             'INVENTORY_UI_OPEN_PROGRAM_IMAGE_REQUIRED')
        # Exact selected lifetime + canonical current row, not a new generation,
        # admission receipt or public Intent. Frame identity change invalidates it.
        life = (writer, generation, generation.selected, generation.service,
                generation.current_frame, current[1], info.identifier, current[3].uid, current[3].map_id)
        if self._current_after_reselect:
            from tools.local_original_session.launcher import ManualMoveRequests
            need(self._current_after_reselect is True and manual.allow_use_item is False
                 and consumer.allow_use_item is False
                 and ManualMoveRequests._source_reselect_current is self._reselect_current_original
                 and self._reselect_current_original(manual) is self._current_after_reselect_proof
                 and self._current_after_reselect_proof[1] is generation,
                 'INVENTORY_UI_CURRENT_AFTER_RESELECT_PROOF_REQUIRED')
        return current, life

    @staticmethod
    def _same(left, right):
        return (all(a is b for a, b in zip(left[:6], right[:6])) and left[6:] == right[6:])

    def _unknown(self, reason, *, terminal=False):
        self._terminal |= terminal
        if self._terminal:
            self._requested = False
        self.last_result = _empty(reason)
        self.last_result['invoked'] = self._invoke_observed
        self.last_result['cleanup_required'] = self._terminal
        return dict(self.last_result)

    def observation(self):
        if self._closed:
            return self._unknown('INVENTORY_UI_OPEN_CLOSED')
        try:
            _, life = self._current()
            if self._life is not None and not self._same(self._life, life):
                return self._unknown('INVENTORY_UI_OPEN_SELECTION_CHANGED')
        except Exception:
            return self._unknown('INVENTORY_UI_OPEN_NO_CURRENT_SELECTION')
        return dict(self.last_result)

    def collect(self):
        """File-only completion; exact Native reply, never a new action attempt."""
        pending = self._pending
        if pending is None:
            return self.observation()
        request, path, life, started = pending
        try:
            try:
                row = commands._json(path, 2048)
            except ValueError as error:
                metadata = getattr(error, 'input_read_metadata', None)
                waiting = False
                if (type(error) is ValueError and type(metadata) is dict
                        and set(metadata) == {'stage', 'winerror', 'same_file'}
                        and type(metadata['stage']) is str):
                    waiting = (error.args == ('INPUT_REQUEST_OPEN_FAILED',)
                        and metadata['stage'] == 'OPEN' and type(metadata['winerror']) is int
                        and metadata['winerror'] in (32, 33) and metadata['same_file'] is False
                        or error.args == ('INPUT_REQUEST_CHANGED',)
                        and metadata['stage'] == 'FINAL_SIZE_OR_MTIME'
                        and metadata['winerror'] is None and metadata['same_file'] is True)
                if not waiting:
                    raise
                need(time.monotonic_ns() - started < m.WAIT_NS, 'INVENTORY_UI_OPEN_REPLY_DEADLINE')
                return dict(self.last_result)
            if self._current_after_reselect:
                current_after_reselect_reply(row, request)
            else:
                expected = dict(request, schema=RESULT)
                need(set(row) == set(expected) | {'status', 'reason', 'invoked', 'opened',
                                                'before_own_visible', 'after_own_visible'}
                     and all(type(row[k]) is type(v) and row[k] == v for k, v in expected.items()),
                     'INVENTORY_UI_OPEN_REPLY_IDENTITY_REQUIRED')
                need(type(row['status']) is str and row['status'] in ('RETURNED', 'REFUSED', 'CODE_ANCHOR_BLOCKED', 'UNKNOWN')
                     and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
                     and type(row['invoked']) is bool, 'INVENTORY_UI_OPEN_REPLY_TYPES_REQUIRED')
                need((row['status'] == 'RETURNED' and row['reason'] == 0 and row['invoked'] is True
                      and row['opened'] is True and row['before_own_visible'] is False
                      and row['after_own_visible'] is True)
                     or (row['status'] != 'RETURNED' and (row['status'] == 'UNKNOWN' or row['invoked'] is False)
                         and all(row[k] is None for k in
                         ('opened', 'before_own_visible', 'after_own_visible'))),
                     'INVENTORY_UI_OPEN_REPLY_PRIMITIVES_REQUIRED')
            actual_invoked = row['invoked']
            self._invoke_observed = actual_invoked
            if row['status'] == 'UNKNOWN':
                self._terminal = True
                self.last_result = _empty('INVENTORY_UI_OPEN_NATIVE_UNKNOWN')
                self.last_result.update(reason=row['reason'], invoked=actual_invoked, cleanup_required=True)
                return dict(self.last_result)  # Native completion/cleanup ambiguous; reservation stays.
            current, actual = self._current()
            need(self._same(life, actual), 'INVENTORY_UI_OPEN_SELECTION_CHANGED')
            need(time.monotonic_ns() - started < m.WAIT_NS, 'INVENTORY_UI_OPEN_REPLY_DEADLINE')
            need(self.consumer._readonly_pending is self, 'INVENTORY_UI_OPEN_RESERVATION_CHANGED')
            self._pending = None
            self._requested = False
            self._request_life = None
            self.consumer._readonly_pending = None
            completed = time.monotonic_ns()
            self.last_sample_monotonic_ns = completed
            self.consumer.last_sample_ns = completed
            if self._closed or self._terminal:
                return self._unknown('INVENTORY_UI_OPEN_CLOSED_OR_TERMINAL', terminal=True)
            self._life = life
            self.last_result = dict(status=row['status'], reason=row['reason'], invoked=actual_invoked,
                opened=row['opened'], before_own_visible=row['before_own_visible'], after_own_visible=row['after_own_visible'],
                native_sequence=request['seq'], source_pid=request['pid'], source_birth=request['birth'],
                source_image_sha256=request['candidate_sha256'], player_uid=request['player_uid'],
                item_identifier=request['item_identifier'], map_id=request['map_id'],
                query_started_monotonic_ns=started, cleanup_required=False)
            if self._current_after_reselect:
                self.last_result.update(schema=AFTER_RESULT, command=AFTER_COMMAND,
                    branch=row['branch'], current_own_visible=row['current_own_visible'])
            if self.collection_policy is not None and row['status'] == 'RETURNED' and self._completion is None:
                # Historical completion only. observation() may correctly become
                # UNKNOWN while Restart/Reselect retires this exact old life.
                self._completion = (life, dict(self.last_result))
            return dict(self.last_result)
        except FileNotFoundError:
            if time.monotonic_ns() - started >= m.WAIT_NS:
                return self._unknown('INVENTORY_UI_OPEN_REPLY_DEADLINE', terminal=True)
            return dict(self.last_result)
        except Exception as error:
            return self._unknown(observe.reason(error), terminal=self._pending is not None)

    async def sample(self):
        """Use one serial sample slot; pending action/busy always has priority."""
        consumer, manual = self.consumer, self.manual
        if (not self._requested or self._claimed or self._closed or self._terminal or self._pending is not None or manual.closed
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
                self._unknown('INVENTORY_UI_OPEN_SELECTION_CHANGED')
                return False
            row, writer = current[1], current[0].writer
            async with row['operation_lock']:
                need(not self._closed and not consumer._busy and consumer.pending is None
                     and consumer._readonly_pending is None and not self._claimed,
                     'INVENTORY_UI_OPEN_PENDING_CHANGED')
                consumer._busy, entered = True, True
                broker = current[0].broker
                need(await broker._movement_owner(writer, row, current[3]) is True,
                     'INVENTORY_UI_OPEN_NATIVE_OWNER_REQUIRED')
                current, after = self._current()
                need(self._same(life, after), 'INVENTORY_UI_OPEN_SELECTION_CHANGED')
                hwnd = _WINDOW(consumer, current)
                need(consumer.sequence < m.MAX_SEQUENCE, 'INVENTORY_UI_OPEN_SEQUENCE_EXHAUSTED')
                self._claimed = True  # One explicit action; no rearm after publication ambiguity.
                consumer.sequence += 1  # Shared original consumer; public action cache untouched.
                seq, boundary, identity = consumer.sequence, current[5], current[6]
                stem = AFTER_STEM if self._current_after_reselect else 'inventory-ui-open'
                request = dict(schema=AFTER_REQUEST if self._current_after_reselect else REQUEST,
                    **identity, seq=seq, command=AFTER_COMMAND if self._current_after_reselect else COMMAND,
                    player_uid=current[3].uid, item_identifier=life[6], map_id=current[3].map_id)
                path = boundary / (stem + '-result-' + str(seq) + '.json')
                commands._ordinary(path, absent=True)
                m._create_once(boundary / (stem + '-request-' + str(seq) + '.json'), request)
                user = consumer.reader.owner.native.u
                message = int(user.RegisterWindowMessageW(AFTER_MESSAGE if self._current_after_reselect else MESSAGE))
                need(0xc000 <= message <= 0xffff, 'INVENTORY_UI_OPEN_MESSAGE_REQUIRED')
                final, final_life = self._current()
                need(self._same(life, final_life) and _WINDOW(consumer, final) == hwnd,
                     'INVENTORY_UI_OPEN_PREPOST_CHANGED')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                self._pending = (request, path, life, now)
                consumer._readonly_pending = self
                self._life = life
                self.last_sample_monotonic_ns = now
                consumer.last_sample_ns = now
                self.last_result = _empty('INVENTORY_UI_OPEN_PENDING')
                owner = consumer.reader.owner
                desktop = getattr(owner, 'private_desktop', None)
                if desktop is not None:
                    need(desktop.post_command(owner, identity, hwnd, owner.child.tid, message, seq)
                         is True, 'INVENTORY_UI_OPEN_POST_UNKNOWN')
                else:
                    need(user.PostMessageW(hwnd, message, seq, 0), 'INVENTORY_UI_OPEN_POST_UNKNOWN')
                final, final_life = self._current()
                need(self._same(life, final_life) and _WINDOW(consumer, final) == hwnd,
                     'INVENTORY_UI_OPEN_POST_CHANGED')
            self.collect()
            return True
        except asyncio.CancelledError:
            self._unknown('INVENTORY_UI_OPEN_CANCELLED', terminal=True)
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
        self.last_result = _empty('INVENTORY_UI_OPEN_CLOSED')
        # Preserve unresolved queue ownership. No guessed cleanup or new action.
        if self._pending is not None:
            self.collect()

    def retire_after_reselect(self, completed, *, current_after_reselect=False):
        """One collection-only original old->new proof, never rearm this action.

        The caller may adopt only the returned fresh original instance. Failure
        spends this retirement attempt; no old receipt/borrow becomes new life.
        """
        from tools.local_original_session.launcher import ManualMoveRequests
        need(type(self) is InventoryUIOpen and self.collection_policy is not None
             and not self._retire_attempted, 'INVENTORY_UI_OPEN_RETIRE_EXPLICIT_ONCE_REQUIRED')
        need(type(current_after_reselect) is bool,
             'INVENTORY_UI_CURRENT_AFTER_RESELECT_EXPLICIT_BOOL_REQUIRED')
        self._retire_attempted = True
        try:
            need(not current_after_reselect or (self.manual.allow_use_item is False
                 and self.consumer.allow_use_item is False),
                 'INVENTORY_UI_CURRENT_AFTER_RESELECT_ZERO_USE_REQUIRED')
            manual, consumer = self.manual, self.consumer
            need(not self._closed and not self._terminal and self._claimed is True
                 and self._pending is None and self._requested is False
                 and manual.consumer is consumer and not manual.closed and not manual._resources_closed
                 and not manual.pending and not manual._polling and not consumer._busy
                 and manual._inventory_request is None and manual._inventory_wait is None
                 and consumer.pending is None and consumer._readonly_pending is None,
                 'INVENTORY_UI_OPEN_RETIRE_QUEUE_FREE_REQUIRED')
            need(type(self._completion) is tuple and len(self._completion) == 2,
                 'INVENTORY_UI_OPEN_RETIRE_NORMAL_RETURN_REQUIRED')
            old_life, result = self._completion
            need(type(result) is dict and result.get('status') == 'RETURNED'
                 and type(result.get('reason')) is int and result['reason'] == 0
                 and result.get('invoked') is result.get('opened') is True
                 and result.get('before_own_visible') is False and result.get('after_own_visible') is True
                 and result.get('cleanup_required') is False and type(old_life) is tuple and len(old_life) == 9
                 and result.get('item_identifier') == old_life[6]
                 and result.get('player_uid') == old_life[7] and result.get('map_id') == old_life[8],
                 'INVENTORY_UI_OPEN_RETIRE_NORMAL_RETURN_REQUIRED')
            need(ManualMoveRequests._source_reselect_current is self._reselect_current_original,
                 'INVENTORY_UI_OPEN_RETIRE_ORIGINAL_METHOD_REQUIRED')
            actual = self._reselect_current_original(manual)
            need(actual is completed, 'INVENTORY_UI_OPEN_RETIRE_ORIGINAL_PROOF_REQUIRED')
            old, generation, _bound, _current = actual
            previous = old['restart_generation']
            need(old_life[1] is previous and previous.phase == 'RETIRED' and previous.service._closed
                 and generation.previous is previous and generation.phase == 'ACTIVE'
                 and generation.selected is generation.game.selection,
                 'INVENTORY_UI_OPEN_RETIRE_OLD_NEW_GENERATION_REQUIRED')
            current, life = self._current()
            identity = current[6]
            need(life[1] is generation and old_life[0] is life[0] and old_life[7:] == life[7:]
                 and all(type(result.get(key)) is int and result[key] == identity[field]
                         for key, field in (('source_pid', 'pid'), ('source_birth', 'birth')))
                 and result.get('source_image_sha256') == identity['candidate_sha256'],
                 'INVENTORY_UI_OPEN_RETIRE_SOURCE_CHANGED')
            InventoryUIOpen.close(self)  # Permanently close before constructing any successor.
            fresh = InventoryUIOpen(manual, collection_policy=self.collection_policy)
            try:
                _, fresh_life = fresh._current()
                need(fresh_life[1] is generation and self._same(life, fresh_life),
                     'INVENTORY_UI_OPEN_RETIRE_NEW_CURRENT_CHANGED')
                if current_after_reselect:
                    fresh._current_after_reselect = True
                    fresh._current_after_reselect_proof = actual
                    fresh._current()
            except BaseException:
                InventoryUIOpen.close(fresh)
                raise
            return fresh
        except BaseException:
            InventoryUIOpen.close(self)
            raise
