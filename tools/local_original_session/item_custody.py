"""Explicit local whole-B custody data, never a live ground capability.

One canonical AB image and one owner for B share the inventory sidecar. The
same-B return is a declared local storage policy, not an original-server UID
mapping claim. Ground appearance/registration remains source-not-ready.
"""
from dataclasses import dataclass, replace
import hashlib
import json

from tools.local_original_session import inventory

CUSTODY_POLICY = 'EXPLICIT_LOCAL_ANCHOR_A_OTHER_B_WHOLE_CUSTODY_V1'
VERSION = 2
MAX_REVISION = (1 << 64) - 1
need = inventory.need


@dataclass(frozen=True, slots=True)
class GroundLocation:
    """Storage coordinates only; no actor UID, epoch, appearance or permission."""
    map_id: int
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class EquipmentGuard:
    character_uid: int
    item_uid: int
    template: int
    weapon_uid: int
    revision: int


@dataclass(frozen=True, slots=True)
class CustodySnapshot:
    character_uid: int
    frame_ab: bytes
    owner: str
    phase: str
    revision: int
    location: GroundLocation | None
    equipment_guard: EquipmentGuard | None
    profile_path: str
    file_sha256: str


def _members(frame):
    items = inventory.validate_collection_frame(frame, policy=inventory.COLLECTION_POLICY)
    need(len(items) == 2 and all(item.template_bits == 1 and
         dict(item.raw_fields)[4] > 0 for item in items),
         'ITEM_CUSTODY_EXACT_TEMPLATE1_AB_REQUIRED')
    return items


def _validate(value):
    need(type(value) is CustodySnapshot, 'ITEM_CUSTODY_EXACT_SNAPSHOT_REQUIRED')
    need(type(value.character_uid) is int and 0 < value.character_uid < 1 << 32,
         'ITEM_CUSTODY_CHARACTER_UID_REQUIRED')
    a, b = _members(value.frame_ab)
    need(type(value.revision) is int and 0 < value.revision <= MAX_REVISION,
         'ITEM_CUSTODY_REVISION_REQUIRED')
    need(type(value.profile_path) is str and bool(value.profile_path) and
         type(value.file_sha256) is str and len(value.file_sha256) == 64 and
         all(c in '0123456789abcdef' for c in value.file_sha256),
         'ITEM_CUSTODY_FILE_BINDING_REQUIRED')
    need(type(value.owner) is str and type(value.phase) is str,
         'ITEM_CUSTODY_OWNER_PHASE_REQUIRED')
    if value.phase == 'READY':
        need(value.owner == 'PLAYER' and value.location is None and
             value.equipment_guard is None, 'ITEM_CUSTODY_READY_SHAPE')
    else:
        need(value.phase in ('DROPPED', 'RETURNED'), 'ITEM_CUSTODY_PHASE_REQUIRED')
        guard = value.equipment_guard
        need(type(guard) is EquipmentGuard and
             all(type(v) is int for v in (guard.character_uid, guard.item_uid,
                 guard.template, guard.weapon_uid, guard.revision)) and
             guard.character_uid == value.character_uid and guard.item_uid == a.identifier and
             guard.template == 1 and guard.weapon_uid in (0, a.identifier) and
             0 < guard.revision <= MAX_REVISION, 'ITEM_CUSTODY_UNEQUIPPED_B_GUARD_REQUIRED')
        if value.phase == 'DROPPED':
            loc = value.location
            need(value.owner == 'GROUND' and type(loc) is GroundLocation and
                 all(type(v) is int for v in (loc.map_id, loc.x, loc.y)) and
                 0 <= loc.map_id < 1 << 31 and -(1 << 31) <= loc.x < 1 << 31 and
                 -(1 << 31) <= loc.y < 1 << 31, 'ITEM_CUSTODY_GROUND_LOCATION_REQUIRED')
        else:
            need(value.owner == 'PLAYER' and value.location is None,
                 'ITEM_CUSTODY_RETURNED_SHAPE')
    return a, b


def owned_frame(value):
    a, _ = _validate(value)
    if value.owner == 'PLAYER':
        return value.frame_ab
    return inventory.build_collection_add((a,), policy=inventory.COLLECTION_POLICY)


def _equipment_guard(state):
    # Exact actual DTO type, still only data. InventoryStore rereads the bound
    # real EquipmentStore under its original locks before a storage transition.
    from tools.local_original_session.equipment_store import EquipmentState
    need(type(state) is EquipmentState, 'ITEM_CUSTODY_ACTUAL_EQUIPMENT_STATE_REQUIRED')
    return EquipmentGuard(state.character_uid, state.item_uid, state.template,
                          state.weapon_uid, state.revision)


def _drop_storage_plan(expected, location, equipment):
    """Private policy fixture/data plan; NOT an operation admission API."""
    _validate(expected)
    need(expected.phase == 'READY', 'ITEM_CUSTODY_DROP_READY_REQUIRED')
    result = replace(expected, owner='GROUND', phase='DROPPED',
                     revision=expected.revision + 1, location=location,
                     equipment_guard=_equipment_guard(equipment))
    _validate(result)
    return result


def _pickup_storage_plan(expected, equipment):
    _validate(expected)
    need(expected.phase == 'DROPPED', 'ITEM_CUSTODY_PICKUP_DROPPED_REQUIRED')
    need(_equipment_guard(equipment) == expected.equipment_guard,
         'ITEM_CUSTODY_EQUIPMENT_CHANGED')
    result = replace(expected, owner='PLAYER', phase='RETURNED',
                     revision=expected.revision + 1, location=None)
    _validate(result)
    return result


def validate_transition(expected, replacement):
    _validate(expected)
    _validate(replacement)
    need(expected.revision < MAX_REVISION and
         replacement.revision == expected.revision + 1,
         'ITEM_CUSTODY_REVISION_CAPACITY_OR_SEQUENCE')
    need((replacement.character_uid, replacement.frame_ab, replacement.profile_path,
          replacement.file_sha256) == (expected.character_uid, expected.frame_ab,
          expected.profile_path, expected.file_sha256), 'ITEM_CUSTODY_IMMUTABLE_BINDING_CHANGED')
    if expected.phase == 'READY':
        need(replacement.phase == 'DROPPED', 'ITEM_CUSTODY_DROP_TRANSITION_REQUIRED')
    else:
        need(expected.phase == 'DROPPED' and replacement.phase == 'RETURNED' and
             replacement.equipment_guard == expected.equipment_guard,
             'ITEM_CUSTODY_PICKUP_TRANSITION_REQUIRED')


def encode(value):
    _validate(value)
    loc, guard = value.location, value.equipment_guard
    row = dict(character_uid=value.character_uid, frame_ab=value.frame_ab.hex(),
               owner=value.owner, phase=value.phase, revision=value.revision,
               location=None if loc is None else dict(map_id=loc.map_id, x=loc.x, y=loc.y),
               equipment_guard=None if guard is None else [guard.character_uid,
                   guard.item_uid, guard.template, guard.weapon_uid, guard.revision])
    return (json.dumps(dict(version=VERSION, policy=CUSTODY_POLICY, collections=[row]),
                       separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')


def decode(data, raw, known, profile_path):
    need(type(data) is dict and set(data) == {'version', 'policy', 'collections'} and
         type(data['version']) is int and data['version'] == VERSION and
         type(data['policy']) is str and data['policy'] == CUSTODY_POLICY and
         type(data['collections']) is list and len(data['collections']) == 1,
         'ITEM_CUSTODY_AGGREGATE_SCHEMA')
    row, = data['collections']
    need(type(row) is dict and set(row) == {'character_uid', 'frame_ab', 'owner',
         'phase', 'revision', 'location', 'equipment_guard'}, 'ITEM_CUSTODY_ROW_SCHEMA')
    uid, encoded = row['character_uid'], row['frame_ab']
    need(type(uid) is int and uid in known, 'ITEM_CUSTODY_KNOWN_CHARACTER_REQUIRED')
    need(type(encoded) is str and 12 <= len(encoded) <= inventory.MAX_FRAME * 2,
         'ITEM_CUSTODY_FRAME_REQUIRED')
    try:
        frame = bytes.fromhex(encoded)
    except ValueError:
        raise ValueError('ITEM_CUSTODY_FRAME_REQUIRED') from None
    need(frame.hex() == encoded, 'ITEM_CUSTODY_CANONICAL_HEX_REQUIRED')
    loc, guard = row['location'], row['equipment_guard']
    if loc is not None:
        need(type(loc) is dict and set(loc) == {'map_id', 'x', 'y'}, 'ITEM_CUSTODY_LOCATION_SCHEMA')
        loc = GroundLocation(**loc)
    if guard is not None:
        need(type(guard) is list and len(guard) == 5, 'ITEM_CUSTODY_EQUIPMENT_SCHEMA')
        guard = EquipmentGuard(*guard)
    value = CustodySnapshot(uid, frame, row['owner'], row['phase'], row['revision'],
                           loc, guard, profile_path, hashlib.sha256(raw).hexdigest())
    _validate(value)
    return value
