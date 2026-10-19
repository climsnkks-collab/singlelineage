"""Source-bound Monster Death/Remove notifications; explicit local ordering.

Transport DRAINED proves neither DeathAction admission/completion nor registry
or screen state. Remove is an independent backend call, never a corpse timer.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct

from tools.local_original_session import attack

ROOT = Path(__file__).resolve().parents[2]
DEATH_OPCODE, REMOVE_OPCODE = 0x4e39, 0x4e40
DEATH_POLICY = 'EXPLICIT_LOCAL_LETHAL_AFTER_FEEDBACK_DEATH'
REMOVE_POLICY = 'EXPLICIT_LOCAL_BACKEND_REMOVE_DEAD_NPC'
SOURCE = 'work/local_server_rea_20261016/run75_npc_hp_death_contract/'
SOURCE_PINS = {
    SOURCE + 'findings.md': 'cd90a61d24344080317055415b16897b56df5c1691c52026179def2e67d919dc',
    SOURCE + 'source-evidence.json': '63d7e6678e9e60d4adc739934a593bcd900d9dc8a0b86902f4906c830fcd40a9',
    SOURCE + 'main-review.json': '7b068a4a747f7c3c8f4ff363e32e1b8130d1a6da0b03052e5cff7d210abc1b73',
}
need = attack.need


def source_ready():
    """Read only accepted bounded text evidence, never a producer or binary."""
    for relative, digest in SOURCE_PINS.items():
        path = ROOT / relative
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536,
             'NPC_DEATH_SOURCE_BOUND')
        raw = path.read_bytes()
        need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == digest,
             'NPC_DEATH_SOURCE_CHANGED')
        if relative.endswith('source-evidence.json'):
            contracts = json.loads(raw)['accepted_static_contracts']
            need(contracts['0x4E39']['mask'] == 3
                 and contracts['0x4E39']['ordinary_Monster_death_selector'] == 8
                 and contracts['0x4E40']['mask'] == 1
                 and contracts['0x4E40']['consumer'] == '0x61650', 'NPC_DEATH_SOURCE_CONTRACT')


def frame(opcode, uid):
    source_ready()
    need(type(opcode) is int and opcode in (DEATH_OPCODE, REMOVE_OPCODE), 'NPC_DEATH_OPCODE_REQUIRED')
    need(type(uid) is int and 0 < uid < attack.U64_MAX, 'NPC_DEATH_LOCAL_UID_REQUIRED')
    body = attack._field(1, uid)
    if opcode == DEATH_OPCODE:
        body += attack._field(2, 8)  # Source-bound ordinary Monster DeathAction selector.
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def validate_frame(wire):
    """Exact minimal canonical local subset; optional opaque f3 is omitted."""
    source_ready()
    need(type(wire) is bytes and 8 <= len(wire) <= 19, 'NPC_DEATH_FRAME_BOUND')
    length, opcode = struct.unpack('<HH', wire[:4])
    need(length == len(wire) and wire[-2:] == b'\0\0'
         and opcode in (DEATH_OPCODE, REMOVE_OPCODE), 'NPC_DEATH_FRAME_HEADER')
    schema = {1: 0, 2: 0} if opcode == DEATH_OPCODE else {1: 0}
    with attack.pb.parse_message(wire[4:-2], schema=schema,
            limits=attack.pb.WireLimits(max_body=13, max_fields=2, max_field_bytes=13)) as parsed:
        need(all(len(parsed.occurrences(n)) == 1 for n in schema), 'NPC_DEATH_REQUIRED_FIELDS')
        uid = parsed.occurrences(1)[0].value
        need(wire == frame(opcode, uid), 'NPC_DEATH_EXACT_LOCAL_FRAME_REQUIRED')
    return opcode, uid


@dataclass(slots=True)
class _Delivery:
    wire: bytes
    phase: str = 'PREPARED'
    write_attempted: bool = False
    drained: bool = False


@dataclass(slots=True)
class _Death:
    entry: object
    result: object
    death: _Delivery
    remove: _Delivery | None = None
    removed: bool = False


class Notifications:
    """One selected-life lethal record; no replay queue or network request API."""
    def __init__(self, service, *, death_policy, remove_policy):
        need(death_policy == DEATH_POLICY and remove_policy in (None, REMOVE_POLICY),
             'NPC_DEATH_EXPLICIT_POLICY_REQUIRED')
        source_ready()
        self.service = service
        self.death_policy, self.remove_policy = death_policy, remove_policy
        self._records = {}
        self.last = {}

    def _record_current(self, writer, uid, record):
        service = self.service
        need(not service.closed and not service.fatal and service._hp is not None,
             'NPC_DEATH_SESSION_UNAVAILABLE')
        attack.source_ready()
        current = service.targets._project(writer, attack.AttackRequest(uid))
        row = current[0]
        lifetime, target = service._hp_binding(writer, row, uid)
        entry, result = record.entry, record.result
        need(service._hp._entries.get((id(writer), uid)) is entry and entry.writer is writer
             and entry.row is row and entry.lock is row['operation_lock'] and entry.lock.locked()
             and len(entry.lifetime) == len(lifetime)
             and all(a is b for a, b in zip(entry.lifetime, lifetime))
             and entry.target == target == result.target and not entry.hp.alive
             and entry.intent.accepted_ordinal == result.accepted_ordinal
             and result.died and entry.hp is result.after,
             'NPC_DEATH_SAME_LETHAL_SELECTION_REQUIRED')
        return row

    def prepare_death(self, writer, row, intent):
        service = self.service
        result = service.last_hp_result
        if result is None or not result.died or result.accepted_ordinal != intent.accepted_ordinal:
            return None
        need(service._feedback_state == 'DRAINED' and service._feedback_intent is intent
             and service._current is intent and service.accepted_count == intent.accepted_ordinal,
             'NPC_DEATH_SAME_DRAINED_FEEDBACK_REQUIRED')
        uid = result.target.uid
        key = (id(writer), uid)
        if key in self._records:
            need(self._records[key].entry.intent is intent, 'NPC_DEATH_EXISTING_LIFETIME_REQUIRED')
            return None
        entry = service._hp._entries[key]
        record = _Death(entry, result, _Delivery(frame(DEATH_OPCODE, uid)))
        need(self._record_current(writer, uid, record) is row, 'NPC_DEATH_SAME_ROW_REQUIRED')
        self._records[key] = record
        return record.death

    def prepare_remove(self, writer, row, *, uid, accepted_ordinal, policy):
        need(type(policy) is str and policy == self.remove_policy == REMOVE_POLICY,
             'NPC_REMOVE_EXPLICIT_BACKEND_POLICY_REQUIRED')
        need(type(uid) is int and type(accepted_ordinal) is int, 'NPC_REMOVE_TYPED_INPUT_REQUIRED')
        need(not self.service.closed and not self.service.fatal, 'NPC_DEATH_SESSION_UNAVAILABLE')
        record = self._records.get((id(writer), uid))
        need(record is not None and record.result.accepted_ordinal == accepted_ordinal,
             'NPC_REMOVE_CURRENT_LETHAL_RECORD_REQUIRED')
        need(record.death.drained, 'NPC_REMOVE_LOCAL_DEATH_DRAIN_REQUIRED')
        if record.remove is not None:
            need(not record.remove.drained, 'NPC_REMOVE_ALREADY_DRAINED')
            raise ValueError('NPC_REMOVE_PREVIOUS_OUTCOME_UNRESOLVED')
        try:
            record.remove = _Delivery(frame(REMOVE_OPCODE, uid))
            need(self._record_current(writer, uid, record) is row, 'NPC_REMOVE_SAME_ROW_REQUIRED')
        except BaseException:
            # A real lifetime/source/read failure is terminal too, even before
            # write. Bad backend arguments above never consume this operation.
            self.service.fail()
            raise
        return record.remove

    def validate(self, writer, wire, *, phase):
        opcode, uid = validate_frame(wire)
        record = self._records.get((id(writer), uid))
        need(record is not None, 'NPC_DEATH_CURRENT_RECORD_REQUIRED')
        delivery = record.death if opcode == DEATH_OPCODE else record.remove
        need(delivery is not None and delivery.wire is wire and delivery.phase == phase
             and not record.removed, 'NPC_DEATH_CURRENT_ONCE_FRAME_REQUIRED')
        row = self._record_current(writer, uid, record)
        return row, record, delivery

    def reserve(self, writer, wire):
        row, record, delivery = self.validate(writer, wire, phase='PREPARED')
        delivery.phase = 'RESERVED'
        return row, record, delivery

    def attempt(self, writer, wire):
        actual = self.validate(writer, wire, phase='RESERVED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        delivery = actual[2]
        delivery.phase, delivery.write_attempted = 'WRITE_ATTEMPTED', True
        return actual

    def drained(self, writer, wire):
        row, record, delivery = self.validate(writer, wire, phase='WRITE_ATTEMPTED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        delivery.phase, delivery.drained = 'DRAINED', True
        if delivery is record.remove:
            record.removed = True  # Local selected-life tombstone, not client registry observation.
        self._remember(record, delivery)

    def require_not_removed_spawn(self, writer, uid):
        need(not self.is_removed(writer, uid), 'NPC_REMOVED_OLD_SPAWN_REFUSED')

    def is_removed(self, writer, uid):
        record = self._records.get((id(writer), uid))
        if record is None or not record.removed or record.entry.writer is not writer:
            return False
        # Pure current-selection query. Never recurse into AttackTargets: this
        # is itself called by its fresh projection and by spawn validation.
        broker, entry = self.service.targets.broker, record.entry
        realm = broker.realm
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is writer]
        if len(rows) != 1 or rows[0] is not entry.row:
            return False
        try:
            game, service = realm.registry.resolve(writer), realm.service(writer)
            frames = realm._npc_frames[id(writer)]
            spawn, = [spawn for spawn, _ in realm._npc_spawns if spawn.uid == uid]
        except (KeyError, ValueError):
            return False
        current = (realm, realm.registry, game, game.selection, service, frames,
                   realm._npc_spawns, spawn, entry.row['operation_lock'], entry.row['policy_row'])
        return len(current) == len(entry.lifetime) and all(a is b for a, b in zip(current, entry.lifetime))

    def require_not_removed_target(self, writer, uid):
        need(not self.is_removed(writer, uid), 'ATTACK_LOCAL_TARGET_REMOVED')

    def _remember(self, record, delivery):
        opcode = int.from_bytes(delivery.wire[2:4], 'little')
        self.last[opcode] = dict(target_uid=record.result.target.uid,
            accepted_ordinal=record.result.accepted_ordinal, phase=delivery.phase,
            write_attempted=delivery.write_attempted, drained=delivery.drained,
            removed=record.removed, delivery=('TRANSPORT_DRAIN_ONLY' if delivery.drained else
                'UNKNOWN' if delivery.write_attempted else 'NOT_WRITTEN'),
            client_action='UNKNOWN', client_registry='UNKNOWN', screen='UNKNOWN')

    def fail(self):
        for record in self._records.values():
            for delivery in (record.death, record.remove):
                if delivery is not None:
                    if delivery.phase != 'DRAINED':
                        delivery.phase = 'TERMINAL'
                    self._remember(record, delivery)

    def release(self, writer):
        for key, record in tuple(self._records.items()):
            if record.entry.writer is writer:
                self.fail_record(record)
                del self._records[key]

    def fail_record(self, record):
        for delivery in (record.death, record.remove):
            if delivery is not None:
                if delivery.phase != 'DRAINED':
                    delivery.phase = 'TERMINAL'
                self._remember(record, delivery)

    def close(self):
        self.fail()
        self._records.clear()

    def metadata(self):
        return dict(death_policy=self.death_policy, remove_policy=self.remove_policy,
            selected_records=len(self._records), last={hex(k): dict(v) for k, v in self.last.items()},
            order='EXPLICIT_LOCAL_FEEDBACK_THEN_DEATH_SEPARATE_BACKEND_REMOVE',
            official_order='UNKNOWN', hp_wire='UNKNOWN', action_admission='UNKNOWN',
            action_complete='UNKNOWN', client_registry='UNKNOWN', screen='UNKNOWN')
