"""run394 warehouse wire shapes and per-character LOCAL asset persistence.

The host owns menu/NPC/session lifetime, current issued row keys, policy, UID
allocation and the existing world lock. All unknown COUNT/LIST operands must
come from its explicit experiment configuration. No INFO0973 success is made.
Warehouse rows preserve the inventory kit's complete canonical ItemInfo bytes.
An absent character row is the empty warehouse, never an empty ADD to a client.

WarehouseStore is startup-loaded and single-process. A durable transfer intent
completes both sidecars after interruption; it is not a rollback or retry token.
After an uncertain commit the live owner must stop using this store and restart
through recovery. Existing InventoryStore.replace_kit retains its own CAS/read
contract; this module adds no request-path reads of warehouse/intent files.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
import os
from pathlib import Path
import threading
import uuid

from tools.local_original_session import inventory

COUNT, LIST, CLOSE = 0x4ED2, 0x0971, 0x097B
WAREHOUSE_SLOTS = 150
pb = inventory.pb


class WarehouseError(ValueError):
    pass


def _need(value, reason):
    if not value:
        raise WarehouseError(reason)


def _uint(value, bits=32):
    _need(type(value) is int and 0 <= value < 1 << bits, 'WAREHOUSE_UNSIGNED_INTEGER')
    return value


def _field(number, value):
    return pb.encode_varint(number << 3) + pb.encode_varint(_uint(value, 64))


def _frame(opcode, body):
    _need(len(body) + 6 <= 65535, 'WAREHOUSE_FRAME_SIZE')
    return ((len(body) + 6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little')
            + body + b'\0\0')


def request_mode(direction, kind):
    """Native A/B kind branching; enum scope names remain unconfirmed."""
    _need(type(kind) is int and kind in (1, 2, 3), 'WAREHOUSE_NATIVE_KIND')
    _need(direction in ('deposit', 'withdraw'), 'WAREHOUSE_DIRECTION')
    return (3 if kind == 2 else 1) if direction == 'deposit' else (4 if kind == 2 else 2)


@dataclass(frozen=True)
class Selection:
    row_key_u32: int
    quantity: int


@dataclass(frozen=True)
class Request:
    context_u32: int
    mode: int
    items: tuple[Selection, ...]
    x_i32: int = 0
    y_i32: int = 0


def decode_request(payload):
    """run394 4ED1 modes1..4; existing shop decoder accepts only5/6.

    Normal warehouse writer includes both coordinates as0. Field order is not
    an action order; repeated selection keys are aggregated by the policy.
    """
    with pb.parse_message(payload, limits=pb.WireLimits(max_body=8192,
            max_fields=154, max_field_bytes=128)) as parsed:
        _need(all(len(parsed.occurrences(n)) == 1 for n in (1, 2, 4, 5))
              and all(f.number in (1, 2, 3, 4, 5) and f.wire_type == (2 if f.number == 3 else 0)
                      for f in parsed.fields), 'WAREHOUSE_REQUEST_FIELDS')
        context, mode = parsed.occurrences(1)[0].value, parsed.occurrences(2)[0].value
        _uint(context)
        _need(mode in (1, 2, 3, 4) and parsed.occurrences(4)[0].value == 0
              and parsed.occurrences(5)[0].value == 0, 'WAREHOUSE_MODE_OR_COORDINATES')
        items = []
        for child in parsed.occurrences(3):
            with pb.parse_message(bytes(child.value), limits=pb.WireLimits(
                    max_body=128, max_fields=2, max_field_bytes=32)) as row:
                _need(len(row.fields) == 2 and all(len(row.occurrences(n)) == 1 for n in (1, 2))
                      and all(f.wire_type == 0 for f in row.fields), 'WAREHOUSE_SELECTION_FIELDS')
                key, count = row.occurrences(1)[0].value, row.occurrences(2)[0].value
                _uint(key)
                _need(1 <= count <= 0x7fffffff, 'WAREHOUSE_SELECTION_QUANTITY')
                items.append(Selection(key, count))
        _need(1 <= len(items) <= 150, 'WAREHOUSE_SELECTION_COUNT')
        return Request(context, mode, tuple(items))


def count_frame(context, *, kind, f1, f3):
    """4ED2 A model: explicit required f1/2/3 and optional context f4."""
    request_mode('deposit', kind)
    values = (_uint(f1), kind, _uint(f3), _uint(context))
    return _frame(COUNT, b''.join(_field(n, v) for n, v in enumerate(values, 1)))


def _item_body(item):
    _need(type(item) is inventory.ItemInfo, 'WAREHOUSE_FULL_ITEMINFO_REQUIRED')
    # The original kit codec preserves all of its explicit raw field presence.
    single = inventory.build_kit_frame([dict(item.raw_fields)])
    with pb.parse_message(single[4:-2]) as parsed:
        return bytes(parsed.occurrences(1)[0].value)


def list_frame(context, rows, *, kind, f2, f4, f5, f6, active=True):
    """0971 B model with opaque issued keys and complete original ItemInfo.

    f2/f4/f5/f6 remain unnamed explicit operands; f5 is not asserted to be fee.
    """
    request_mode('withdraw', kind)
    _need(type(active) is bool, 'WAREHOUSE_ACTIVE_BOOLEAN')
    values = (_uint(context), _uint(f2), kind, _uint(f4), _uint(f5, 64), _uint(f6))
    body = b''.join(_field(n, v) for n, v in enumerate(values, 1))
    seen = set()
    for key, item in rows:
        _uint(key)
        _need(key not in seen and len(seen) < WAREHOUSE_SLOTS, 'WAREHOUSE_LIST_KEYS_OR_SLOTS')
        seen.add(key)
        child = _field(1, key) + pb.encode_bytes(2, _item_body(item))
        body += pb.encode_bytes(7, child)
    return _frame(LIST, body + _field(8, int(active)))


def close_body(payload):
    """Validate 097B's normal empty body or its schema's optional enum f1.

    Closing the native window is independent of any transaction's success.
    The existing ctx.wire.trade decoder owns 4ED1; normal warehouse x/y are0/0.
    """
    _need(type(payload) is bytes, 'WAREHOUSE_CLOSE_BODY')
    with pb.parse_message(payload, limits=pb.WireLimits(max_body=32, max_fields=1,
                                                       max_field_bytes=16)) as parsed:
        _need(not parsed.fields or (len(parsed.fields) == 1
              and parsed.fields[0].number == 1 and parsed.fields[0].wire_type == 0
              and parsed.fields[0].value < 1 << 64), 'WAREHOUSE_CLOSE_BODY')


def _kit(frame, *, optional=False):
    if optional and frame is None:
        return ()
    return inventory.validate_kit_frame(frame)


def _warehouse(frame):
    items = _kit(frame, optional=True)
    _need(len(items) <= WAREHOUSE_SLOTS, 'WAREHOUSE_SLOT_LIMIT')
    return items


def _hex(frame):
    return None if frame is None else frame.hex()


def _unhex(value, *, optional=False):
    if optional and value is None:
        return None
    _need(type(value) is str, 'WAREHOUSE_FRAME_HEX')
    try:
        result = bytes.fromhex(value)
    except ValueError:
        raise WarehouseError('WAREHOUSE_FRAME_HEX') from None
    _need(result.hex() == value, 'WAREHOUSE_FRAME_HEX')
    _kit(result)
    return result


def _json_bytes(data):
    return (json.dumps(data, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')


def _atomic_raw(path, raw):
    temporary = path.with_name('.' + path.stem + '-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            _need(stream.write(raw) == len(raw), 'WAREHOUSE_PARTIAL_WRITE')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path, data):
    _atomic_raw(path, _json_bytes(data))


def _equipment_raw(path):
    if not path.exists():
        return None
    with path.open('rb') as stream:
        raw = stream.read(4097)
    _need(len(raw) <= 4096, 'WAREHOUSE_EQUIPMENT_SIZE')
    return raw


def _raw_unhex(value):
    if value is None:
        return None
    _need(type(value) is str, 'WAREHOUSE_EQUIPMENT_HEX')
    try:
        raw = bytes.fromhex(value)
    except ValueError:
        raise WarehouseError('WAREHOUSE_EQUIPMENT_HEX') from None
    _need(raw.hex() == value and len(raw) <= 4096, 'WAREHOUSE_EQUIPMENT_HEX')
    return raw


class WarehouseStore:
    """One existing InventoryStore plus warehouse.json and one transfer intent.

    Construct before accepting requests, including after a failed commit. The
    host must serialize other inventory changes with commit/recovery. Warehouse
    data is loaded once; restore/rows do not reopen any file. No account-wide or
    v2 custody migration is performed.
    """
    def __init__(self, inventory_store):
        self.inventory_store = inventory_store
        profile = Path(inventory_store.profile)
        _need(profile.is_absolute(), 'WAREHOUSE_ABSOLUTE_PROFILE')
        self.path = profile.with_name('warehouse.json')
        self.intent_path = profile.with_name('warehouse-transfer.json')
        self.equipment_path = profile.with_name('equipment.json')
        self._lock = threading.RLock()
        self._pending = None
        self._rows = self._load()
        self._recover()

    def _load(self):
        if not self.path.exists():
            return {}
        with self.path.open('rb') as stream:
            raw = stream.read(2_000_001)
        _need(len(raw) <= 2_000_000, 'WAREHOUSE_STORE_SIZE')
        data = json.loads(raw, object_pairs_hook=inventory.movement._unique_object)
        _need(type(data) is dict and set(data) == {'version', 'inventories'}
              and type(data['version']) is int and data['version'] == 1
              and type(data['inventories']) is list, 'WAREHOUSE_STORE_SCHEMA')
        result = {}
        for row in data['inventories']:
            _need(type(row) is dict and set(row) == {'uid', 'frame'}, 'WAREHOUSE_STORE_ROW')
            uid = self._character_uid(row['uid'])
            _need(uid not in result, 'WAREHOUSE_DUPLICATE_CHARACTER')
            # Startup-only roster validation via the existing inventory owner.
            self.inventory_store.restore(uid)
            result[uid] = _unhex(row['frame'])
            _warehouse(result[uid])
        return result

    @staticmethod
    def _character_uid(uid):
        _uint(uid)
        _need(uid > 0, 'WAREHOUSE_CHARACTER_UID')
        return uid

    def _write_rows(self, rows):
        _atomic_json(self.path, dict(version=1, inventories=[
            dict(uid=uid, frame=frame.hex()) for uid, frame in sorted(rows.items())]))

    def _finish(self, intent, inventory_current, equipment_current=None):
        uid = intent['uid']
        old_i, new_i = intent['inventory_before'], intent['inventory_after']
        old_w, new_w = intent['warehouse_before'], intent['warehouse_after']
        _need(inventory_current in (old_i, new_i)
              and self._rows.get(uid) in (old_w, new_w), 'WAREHOUSE_RECOVERY_STATE_CONFLICT')
        if 'equipment_after' in intent:
            _need(equipment_current in (intent['equipment_before'], intent['equipment_after']),
                  'WAREHOUSE_RECOVERY_EQUIPMENT_CONFLICT')
        if inventory_current != new_i:
            self.inventory_store.replace_kit(uid, old_i, new_i, append=True)
        if ('equipment_after' in intent and equipment_current != intent['equipment_after']):
            _atomic_raw(self.equipment_path, intent['equipment_after'])
        rows = dict(self._rows)
        if new_w is None:
            rows.pop(uid, None)
        else:
            rows[uid] = new_w
        if rows != self._rows:
            self._write_rows(rows)
            self._rows = rows
        self.intent_path.unlink()
        self._pending = None

    def _recover(self):
        if not self.intent_path.exists():
            return
        with self.intent_path.open('rb') as stream:
            raw = stream.read(300_001)
        _need(len(raw) <= 300_000, 'WAREHOUSE_INTENT_SIZE')
        data = json.loads(raw, object_pairs_hook=inventory.movement._unique_object)
        keys = {'version', 'uid', 'inventory_before', 'inventory_after',
                'warehouse_before', 'warehouse_after'}
        equipment_keys = {'equipment_before', 'equipment_after'}
        _need(type(data) is dict and set(data) in (keys, keys | equipment_keys)
              and type(data['version']) is int and data['version'] == 1,
              'WAREHOUSE_INTENT_SCHEMA')
        uid = self._character_uid(data['uid'])
        intent = dict(uid=uid)
        for key in keys - {'uid', 'version'}:
            intent[key] = _unhex(data[key], optional=key.startswith('warehouse'))
            if key.startswith('warehouse'):
                _warehouse(intent[key])
        if equipment_keys <= data.keys():
            for key in equipment_keys:
                intent[key] = _raw_unhex(data[key])
            _need(intent['equipment_after'] is not None, 'WAREHOUSE_EQUIPMENT_AFTER_REQUIRED')
        self._pending = intent
        self._finish(intent, self.inventory_store.restore(uid),
                     _equipment_raw(self.equipment_path) if equipment_keys <= data.keys() else None)

    def restore(self, character_uid):
        self._character_uid(character_uid)
        with self._lock:
            return self._rows.get(character_uid)

    def rows(self):
        with self._lock:
            return dict(self._rows)

    def commit(self, character_uid, inventory_before, inventory_after,
               warehouse_before, warehouse_after, *, equipment_store=None,
               equipment_before=None, equipment_after=None):
        """Persist one host-approved transfer; return only after both saves.

        A raised IO error preserves the intent; do not refund, retry or publish
        success. Recovery accepts only exact old/new rows and finishes forward.
        """
        uid = self._character_uid(character_uid)
        _kit(inventory_before)
        _kit(inventory_after)
        _warehouse(warehouse_before)
        _warehouse(warehouse_after)
        from tools.local_original_session import inventory_store as stores
        with self._lock, stores._lock, stores.realm._lock:
            _need(self._pending is None, 'WAREHOUSE_RECOVERY_REQUIRED')
            _need(self._rows.get(uid) == warehouse_before, 'WAREHOUSE_EXPECTED_FRAME_CHANGED')
            intent = dict(uid=uid, inventory_before=inventory_before,
                          inventory_after=inventory_after, warehouse_before=warehouse_before,
                          warehouse_after=warehouse_after)
            equipment_current = None
            if equipment_store is not None:
                from tools.local_original_session import equipment_store as equipment
                _need(type(equipment_store) is equipment.EquipmentStore
                      and equipment_store.inventory_store is self.inventory_store
                      and equipment_store.path == self.equipment_path,
                      'WAREHOUSE_EQUIPMENT_OWNER')
                rows, frames, known = equipment_store._read()
                _need(rows.get(uid) == equipment_before and frames.get(uid) == inventory_before,
                      'WAREHOUSE_EXPECTED_EQUIPMENT_CHANGED')
                _need(type(equipment_after) is equipment.EquipmentState
                      and equipment_after.character_uid == uid, 'WAREHOUSE_EQUIPMENT_AFTER_REQUIRED')
                changed_frames = dict(frames)
                changed_frames[uid] = inventory_after
                if equipment_store._kit is not None:
                    equipment_store._kit_state(equipment._row(equipment_after), known,
                                               changed_frames, equipment_store._kit)
                else:
                    equipment_store._state(equipment._row(equipment_after), known, changed_frames,
                                           collection_policy=equipment_store._collection_policy)
                equipment_current = _equipment_raw(self.equipment_path)
                old_document = dict(version=1, policy=equipment.POLICY,
                    equipment=[equipment._row(value) for _, value in sorted(rows.items())])
                _need((equipment_current is None and not rows)
                      or json.loads(equipment_current) == old_document,
                      'WAREHOUSE_EXPECTED_EQUIPMENT_CHANGED')
                rows[uid] = equipment_after
                equipment_new = _json_bytes(dict(version=1, policy=equipment.POLICY,
                    equipment=[equipment._row(value) for _, value in sorted(rows.items())]))
                _need(len(equipment_new) <= equipment_store.MAX_BYTES, 'WAREHOUSE_EQUIPMENT_SIZE')
                intent.update(equipment_before=equipment_current, equipment_after=equipment_new)
            else:
                _need(equipment_before is None and equipment_after is None, 'WAREHOUSE_EQUIPMENT_OWNER')
            if (inventory_before == inventory_after and warehouse_before == warehouse_after
                    and ('equipment_after' not in intent
                         or intent['equipment_before'] == intent['equipment_after'])):
                return False
            self._pending = intent  # Uncertain intent IO also requires startup recovery.
            _atomic_json(self.intent_path, dict(version=1, uid=uid,
                **{key: _hex(value) for key, value in intent.items() if key != 'uid'}))
            self._finish(intent, inventory_before, equipment_current)
            return True
