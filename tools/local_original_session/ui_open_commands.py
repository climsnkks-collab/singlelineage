"""Explicit original UI calls on the retained manual consumer's serial slot.

RETURNED only means that the native call returned. Window pixels and gameplay
effects remain UNKNOWN; screenshots use the existing original capture observer.
Magic/stats invoke original toggle callbacks. Pet requires the actual target UID.
Hotbar DTO slots are 0..7, but the candidate returns UNSUPPORTED/reason8 without
invoking: the original dispatch requires an actual populated SlotNode binding.
"""
from __future__ import annotations

import asyncio
import threading
import time

from tools.local_original_session import commands, inventory, manual_move_commands as move, observe
from tools.local_original_session.original_screenshot import OriginalScreenshotObserver

MESSAGE = 'LC-Owned-UIOpen-v1'
REQUEST = 'own-ui-open-request-v1'
RESULT = 'own-ui-open-result-v1'
COMMANDS = ('open_magic_window', 'open_stats_window', 'open_pet_window', 'hotbar_cast')
need = observe.need


def current_kit(manual):
    """Reuse the original selected-generation/current-owner resolver for M1 kits."""
    consumer = manual.consumer
    need(not manual.closed and not manual._resources_closed
         and manual._actual_manual_producer(asynchronous=True) is consumer,
         'UI_OPEN_CURRENT_CONSUMER_REQUIRED')
    current = consumer._current()
    broker, writer = current[0].broker, current[0].writer
    need(broker is manual.inventory_broker, 'UI_OPEN_SAME_BROKER_REQUIRED')
    generation = manual._inventory_reselection_current(writer)
    need(generation is not None and generation.phase == 'ACTIVE'
         and generation.current_frame is broker._inventory_current_frame
         and generation.delivery_authority is not None and generation.write_attempted,
         'UI_OPEN_DELIVERED_CURRENT_GENERATION_REQUIRED')
    items = inventory.validate_kit_frame(generation.current_frame)
    life = (writer, generation, generation.selected, generation.service,
            generation.current_frame, current[1], items[0].identifier,
            current[3].uid, current[3].map_id)
    return current, life


def build_request(identity, sequence, command, slot=0, target_uid=0):
    need(command in COMMANDS and type(slot) is int
         and (0 <= slot <= 7 if command == 'hotbar_cast' else slot == 0),
         'UI_OPEN_COMMAND_OR_SLOT_REQUIRED')
    need(type(target_uid) is int and (0 < target_uid <= 0xffffffffffffffff
         if command == 'open_pet_window' else target_uid == 0), 'UI_OPEN_TARGET_UID_REQUIRED')
    return dict(schema=REQUEST, **identity, seq=sequence, command=command, slot=slot, target_uid=target_uid)


def validate_result(row, request):
    expected = dict(request, schema=RESULT)
    need(type(row) is dict and set(row) == set(expected) |
         {'status', 'reason', 'invoked', 'action', 'window_state', 'effect'}
         and all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items()),
         'UI_OPEN_RESULT_IDENTITY_OR_SCHEMA')
    need(type(row['status']) is str and row['status'] in
         ('RETURNED', 'REFUSED', 'UNKNOWN', 'CODE_ANCHOR_BLOCKED', 'UNSUPPORTED')
         and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
         and type(row['invoked']) is bool, 'UI_OPEN_RESULT_TYPES')
    need(row['status'] != 'RETURNED' or row['invoked'] is True and row['reason'] == 0,
         'UI_OPEN_RESULT_RETURN_REQUIRED')
    need(type(row['action']) is str and row['action'] in ('none', 'toggle', 'slot_dispatch', 'pet_request')
         and row['window_state'] == 'UNKNOWN'
         and row['effect'] == 'UNKNOWN', 'UI_OPEN_RESULT_SCOPE_REQUIRED')
    return dict(row, window_state='UNKNOWN', effect='UNKNOWN')


def talking_scroll(manual):
    """raw f4 maps to protobuf field 5; resolve the UID from this current kit."""
    current, _ = current_kit(manual)
    items = inventory.validate_kit_frame(current[0].broker._inventory_current_frame)
    matches = [item for item in items if item.template_bits == 12273
               and dict(item.raw_fields).get(5) == 133 and dict(item.raw_fields).get(4, 0) > 0]
    need(len(matches) == 1, 'UI_OPEN_CURRENT_TALKING_SCROLL_REQUIRED')
    return matches[0]


class KitScreenshotObserver(OriginalScreenshotObserver):
    """Original capture/backup/PNG/cleanup implementation, with kit selection."""
    def _current(self, *, item_identifier=None):
        need(not self._closed and threading.get_ident() == self._thread,
             'UI_SCREENSHOT_CURRENT_THREAD_REQUIRED')
        return current_kit(self.manual)

    def _items(self, frame):
        return inventory.validate_kit_frame(frame)


class UIOpenCommands:
    def __init__(self, manual):
        self.manual, self.consumer = manual, manual.consumer
        self.pending = None
        self.last_result = dict(status='NOT_REQUESTED', window_state='UNKNOWN', effect='UNKNOWN')
        self.closed = False

    async def request(self, command, slot=0, *, target_uid=0):
        return await self._post(command, slot, target_uid=target_uid)

    async def use_talking_scroll(self):
        return await self._post('UseItem', item=talking_scroll(self.manual))

    async def _post(self, command, slot=0, item=None, target_uid=0):
        c, manual = self.consumer, self.manual
        if (self.closed or self.pending is not None or manual.pending or manual._polling
                or manual._inventory_request is not None or manual._inventory_wait is not None
                or c.pending is not None or c._busy or c._readonly_pending is not None):
            return False
        current, life = current_kit(manual)
        async with current[1]['operation_lock']:
            c._busy = True
            try:
                need(await current[0].broker._movement_owner(current[0].writer, current[1], current[3])
                     is True, 'UI_OPEN_NATIVE_OWNER_REQUIRED')
                after, actual = current_kit(manual)
                need(OriginalScreenshotObserver._same(life, actual), 'UI_OPEN_SELECTION_CHANGED')
                hwnd = c._window(after)
                need(c.sequence < move.MAX_SEQUENCE, 'UI_OPEN_SEQUENCE_EXHAUSTED')
                c.sequence += 1
                sequence, boundary, identity = c.sequence, after[5], after[6]
                if item is None:
                    request = build_request(identity, sequence, command, slot, target_uid)
                    path = boundary / f'ui-open-request-{sequence}.json'
                    result = boundary / f'ui-open-result-{sequence}.json'
                    message_name = MESSAGE
                else:
                    need(talking_scroll(manual).identifier == item.identifier, 'UI_OPEN_CURRENT_TALKING_SCROLL_REQUIRED')
                    request = dict(schema='own-use-item-request-v1', **identity, seq=sequence,
                        command='UseItem', player_uid=after[3].uid,
                        item_identifier=item.identifier, map_id=after[3].map_id)
                    path, result = boundary / 'use-item-request.json', boundary / f'use-item-result-{sequence}.json'
                    message_name = move.USE_ITEM_MESSAGE
                commands._ordinary(result, absent=True)
                move._create_once(path, request)
                owner = c.reader.owner
                message = int(owner.native.u.RegisterWindowMessageW(message_name))
                need(0xc000 <= message <= 0xffff, 'UI_OPEN_MESSAGE_REQUIRED')
                final, actual = current_kit(manual)
                need(OriginalScreenshotObserver._same(life, actual) and c._window(final) == hwnd,
                     'UI_OPEN_PREPOST_CHANGED')
                self.pending = (request, result, life, time.monotonic_ns())
                c._readonly_pending = self
                self.last_result = dict(status='PENDING', request=request,
                    window_state='UNKNOWN', effect='UNKNOWN')
                need(owner.private_desktop.post_command(owner, identity, hwnd, owner.child.tid,
                    message, sequence) is True, 'UI_OPEN_POST_UNKNOWN')
                return True
            finally:
                c._busy = False

    def collect(self):
        if self.pending is None:
            return dict(self.last_result)
        request, path, life, started = self.pending
        try:
            try:
                row = commands._json(path, 2048)
            except ValueError as error:
                # Same in-progress publication handling as InventoryUIOpen.
                metadata = getattr(error, 'input_read_metadata', None)
                waiting = (type(metadata) is dict and (
                    error.args == ('INPUT_REQUEST_OPEN_FAILED',)
                    and metadata.get('stage') == 'OPEN' and metadata.get('winerror') in (32, 33)
                    and metadata.get('same_file') is False
                    or error.args == ('INPUT_REQUEST_CHANGED',)
                    and metadata.get('stage') == 'FINAL_SIZE_OR_MTIME'
                    and metadata.get('winerror') is None and metadata.get('same_file') is True))
                if waiting and time.monotonic_ns() - started < move.WAIT_NS:
                    return dict(self.last_result)
                raise
            if request['command'] == 'UseItem':
                expected = dict(request, schema='own-use-item-result-v1')
                need(set(row) == set(expected) | {'status', 'reason', 'invoked'}
                     and all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items()),
                     'MANUAL_USE_ITEM_RESULT_IDENTITY_OR_SCHEMA')
                need(row['status'] in ('RETURNED', 'UNKNOWN', 'BLOCKED_SOURCE_BINDING',
                    'CODE_ANCHOR_BLOCKED', 'REFUSED') and type(row['invoked']) is bool
                    and type(row['reason']) is int and (row['status'] != 'RETURNED'
                    or row['invoked'] is True and row['reason'] == 0),
                    'MANUAL_USE_ITEM_RESULT_IDENTITY_OR_SCHEMA')
                answer = dict(row, window_state='UNKNOWN', effect='UNKNOWN', server_commit='NOT_REQUIRED_CLIENT_LOCAL_UI')
            else:
                answer = validate_result(row, request)
            self.last_result = answer
            if row['status'] == 'UNKNOWN':
                return dict(answer)  # Ambiguous native lifetime retains the serial reservation.
            _, actual = current_kit(self.manual)
            need(OriginalScreenshotObserver._same(life, actual), 'UI_OPEN_SELECTION_CHANGED')
            need(self.consumer._readonly_pending is self, 'UI_OPEN_RESERVATION_CHANGED')
            self.consumer._readonly_pending = None
            self.consumer.last_sample_ns = time.monotonic_ns()
            self.pending = None
        except FileNotFoundError:
            if time.monotonic_ns() - started >= move.WAIT_NS:
                self.last_result = dict(status='UNKNOWN', reason='UI_OPEN_REPLY_DEADLINE',
                    request=request, cleanup_required=True, window_state='UNKNOWN', effect='UNKNOWN')
        except Exception as error:
            self.last_result = dict(status='UNKNOWN', reason=observe.reason(error),
                request=request, cleanup_required=True, window_state='UNKNOWN', effect='UNKNOWN')
        return dict(self.last_result)

    def close(self):
        if self.pending is not None:
            self.collect()
        self.closed = True  # Unresolved ownership is preserved for original finally/Job cleanup.
