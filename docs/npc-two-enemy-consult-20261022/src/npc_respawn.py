"""Explicit local same-recipe NPC generation replacement; no timer or HP reset.

The registry result is consumed inside the original operation lock. It is a
passive absence snapshot, never a lease or authority to address a client object.
The player claim survives; old NPC capabilities do not.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import inspect

from tools.local_original_session import attack, edge, npc, npc_edge, npc_motion, npc_observe
from tools.local_original_session.broker import PersistentBroker

POLICY = 'EXPLICIT_LOCAL_SAME_UID_RESPAWN_AFTER_FRESH_ABSENCE'
need = attack.need
_REGISTRY = npc_observe.NpcObserver.sample_registry
_SELECTION = npc_observe.NpcObserver._registry_selection
_CURRENT = npc_observe.NpcObserver._registry_current
_SEND = PersistentBroker._send
_OWNER = PersistentBroker._movement_owner
_CHECKPOINT = PersistentBroker._checkpoint


def _fresh_absence_diagnostic(result, *, target_uid, map_id):
    """Bounded output from the already-returned query, never absence authority."""
    if type(result) is not dict:
        return None
    detail = {}
    strings = ('status', 'reason', 'lookup_scope', 'observation_scope',
               'typed_read_changed_field', 'typed_read_changed_origin', 'typed_read_changed_stage')
    integers = ('uid', 'map_id', 'typed_bytes_requested', 'typed_byte_limit',
                'max_samples_per_second', 'unsupported_type_rva', 'unsupported_vector_index')
    booleans = ('uid_absent', 'snapshot_atomic', 'source_contract_valid', 'stable_double_read')
    for key in strings + integers + booleans + ('vector_counts',):
        if key not in result:
            continue
        value = result[key]
        if value is not None:
            if key in strings:
                if (type(value) is not str or not 0 < len(value) <= 96 or not value.isascii()
                        or not all(c.isalnum() or c == '_' for c in value)):
                    return None
            elif key in integers:
                if type(value) is not int or not 0 <= value < (1 << 64):
                    return None
            elif key in booleans:
                if type(value) is not bool:
                    return None
            elif (type(value) is not list or len(value) != 3
                  or not all(type(n) is int and 0 <= n < (1 << 31) for n in value)):
                return None
        detail[key] = list(value) if key == 'vector_counts' and value is not None else value
    predicates = (('STATUS_NOT_OBSERVED', result.get('status') == 'OBSERVED'),
                  ('TARGET_UID_MISMATCH', result.get('uid') == target_uid),
                  ('MAP_ID_MISMATCH', result.get('map_id') == map_id),
                  ('UID_ABSENCE_NOT_TRUE', result.get('uid_absent') is True),
                  ('SOURCE_CONTRACT_NOT_TRUE', result.get('source_contract_valid') is True),
                  ('STABLE_DOUBLE_READ_NOT_TRUE', result.get('stable_double_read') is True),
                  ('LOOKUP_SCOPE_MISMATCH', result.get('lookup_scope') == 'THREE_LOOKUP_VECTORS'),
                  ('OBSERVATION_SCOPE_MISMATCH', result.get('observation_scope') == 'READONLY_SNAPSHOT'))
    detail['first_rejected_predicate'] = next((name for name, passed in predicates if not passed), None)
    detail['diagnostic_scope'] = 'OUTPUT_ONLY_PRE_SPAWN_ABSENCE'
    return detail


@dataclass(frozen=True, slots=True)
class Generation:
    ordinal: int
    writer: object = field(repr=False)
    row: object = field(repr=False)
    frames: object = field(repr=False)
    recipe: object = field(repr=False)
    spawn: object = field(repr=False)
    mover: object = field(repr=False)


@dataclass(slots=True)
class Ticket:
    writer: object = field(repr=False)
    old_generation: Generation = field(repr=False)
    accepted_ordinal: int
    phase: str = 'TRIGGERED'
    fresh_absence: dict | None = field(default=None, repr=False)  # Output only; not a lease.


@dataclass(frozen=True, slots=True)
class Receipt:
    writer: object = field(repr=False)
    row: object = field(repr=False)
    old_generation: Generation = field(repr=False)
    generation: Generation = field(repr=False)
    spawn: object = field(repr=False)
    recipe: object = field(repr=False)
    mover: object = field(repr=False)
    adapter: object = field(repr=False)
    _service: object = field(repr=False)

    def metadata(self):
        self._service.require_current(self)
        need(self._service._phases.get(self._service._key(self.writer,self.spawn.uid)) == 'COMMITTED',
             'NPC_RESPAWN_ADOPTION_NOT_COMMITTED')
        return dict(status='COMMITTED', generation=self.generation.ordinal,
                    target_uid=self.spawn.uid, map_id=self.spawn.map_id,
                    grid=list(npc_motion.movement.authority.unpack_grid(self.spawn.fields[1])),
                    transport='DRAINED', client_registry='UNKNOWN', scope='NEW_LOCAL_NPC_LIFE_ONLY')


class Service:
    def __init__(self, broker, reader, *, policy):
        from tools.local_original_session.broker import PersistentBroker
        need(type(policy) is str and policy == POLICY and type(broker) is PersistentBroker,
             'NPC_RESPAWN_EXPLICIT_POLICY_REAL_BROKER_REQUIRED')
        session = broker._attack_session
        need(session is not None and session._hp is not None and session._notifications is not None
             and session._notifications.remove_policy is not None
             and broker.realm._npc_motion_interval_ns is not None
             and session.targets.reader is reader, 'NPC_RESPAWN_HP_REMOVE_MOTION_REQUIRED')
        self.broker, self.reader, self.policy = broker, reader, policy
        self._source_guard = broker.source_guard
        self._session, self._hp, self._notifications = session, session._hp, session._notifications
        self.observer = npc_observe.NpcObserver(broker, reader)
        self._generations, self._tickets, self._receipts, self._phases = {}, {}, {}, {}
        self._pending = None

    def _canonical(self):
        need(self.broker._npc_respawn is self and self.broker.realm._npc_respawn is self
             and self.broker.source_guard is self._source_guard
             and self.broker._attack_session is self.broker.realm._attack_session is self._session
             and self._session._hp is self._hp and self._session._notifications is self._notifications
             and self.broker._send.__func__ is _SEND and self.broker._movement_owner.__func__ is _OWNER
             and self.broker._checkpoint.__func__ is _CHECKPOINT
             and self.observer.sample_registry.__func__ is _REGISTRY
             and self.observer._registry_selection.__func__ is _SELECTION
             and self.observer._registry_current.__func__ is _CURRENT,
             'NPC_RESPAWN_CANONICAL_PRODUCER_REQUIRED')

    def _key(self,writer,target_uid=None):
        return self.broker.realm.npc_key(writer,target_uid)

    def _recipe(self,target_uid=None):
        uid=self.broker.realm.npc_target_uid(target_uid)
        return next(spawn for spawn,_ in self.broker.realm._npc_spawns if spawn.uid==uid)

    def _selected(self, writer, target_uid=None):
        broker, realm = self.broker, self.broker.realm
        self._canonical()
        need(broker._npc_respawn is self and realm._npc_respawn is self and self.policy == POLICY
             and self.observer.targets.broker is broker and self.observer.targets.reader is self.reader
             and self.observer.sample_registry.__func__ is _REGISTRY
             and self.observer._registry_selection.__func__ is _SELECTION,
             'NPC_RESPAWN_CANONICAL_SERVICE_REQUIRED')
        recipe=self._recipe(target_uid)
        selection = self.observer._registry_selection(writer, recipe.uid)
        mover = realm.npc_mover(writer,target_uid=recipe.uid)
        need(type(mover) is npc_motion.NpcMotion and mover.spawn_drained and not mover.closed
             and not mover.fatal and mover.pending is None, 'NPC_RESPAWN_CURRENT_MOVER_REQUIRED')
        return selection, recipe, mover

    def current_generation(self, writer, *, target_uid=None):
        # NpcSession calls this read-free projection outside an operation. The
        # selected-only validator requires the existing row lock, so use its
        # full projection only when locked and require the original session's
        # pure binding outside it.
        realm = self.broker.realm
        self._canonical()
        rows = [r for values in self.broker._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_RESPAWN_CURRENT_CLAIM_REQUIRED')
        row, = rows
        need(self.broker._npc_respawn is self and realm._npc_respawn is self
             and not self.broker._closing and not self.broker.failure.is_set()
             and not row['failed'] and not row['joined'], 'NPC_RESPAWN_CURRENT_SERVICE_REQUIRED')
        recipe=self._recipe(target_uid)
        frames=realm.npc_frames(writer,target_uid=recipe.uid)
        key=self._key(writer,recipe.uid)
        mover = realm.npc_mover(writer,target_uid=recipe.uid)
        need(type(mover) is npc_motion.NpcMotion and mover.spawn_drained and not mover.closed
             and not mover.fatal and mover.pending is None and frames[0] is writer,
             'NPC_RESPAWN_CURRENT_MOVER_REQUIRED')
        generation = self._generations.get(key)
        if generation is None:
            generation = Generation(0, writer, row, frames, recipe, recipe, mover)
            self._generations[key] = generation
        need(type(generation) is Generation and generation.writer is writer and generation.row is row
             and generation.frames is frames and generation.recipe is recipe and generation.mover is mover,
             'NPC_RESPAWN_GENERATION_CHANGED')
        return generation

    def trigger(self, writer, uid, accepted_ordinal):
        need(type(uid) is int and type(accepted_ordinal) is int and accepted_ordinal > 0,
             'NPC_RESPAWN_TYPED_TRIGGER_REQUIRED')
        generation = self.current_generation(writer,target_uid=uid)
        key=self._key(writer,uid)
        previous = self._tickets.get(key)
        need(uid == generation.recipe.uid and (previous is None or previous.phase == 'COMMITTED'
             and previous.old_generation is not generation),
             'NPC_RESPAWN_EXPLICIT_ONCE_TRIGGER_REQUIRED')
        ticket = Ticket(writer, generation, accepted_ordinal)
        self._tickets[key] = ticket
        return ticket

    def _old(self, writer, ticket):
        need(type(ticket) is Ticket and self._tickets.get(self._key(writer,ticket.old_generation.recipe.uid)) is ticket and ticket.writer is writer
             and self.current_generation(writer,target_uid=ticket.old_generation.recipe.uid) is ticket.old_generation,
             'NPC_RESPAWN_SAME_TICKET_GENERATION_REQUIRED')
        selected, recipe, mover = self._selected(writer,ticket.old_generation.recipe.uid)
        row = selected[0]
        session = self.broker._attack_session
        notifications, hp = session._notifications, session._hp
        entry = hp._entries.get((id(writer), recipe.uid))
        record = notifications._records.get((id(writer), recipe.uid))
        lifetime, target = session._hp_binding(writer, row, recipe.uid)
        need(entry is not None and entry.writer is writer and entry.row is row and entry.lock is row['operation_lock']
             and entry.target == target and not entry.hp.alive
             and len(lifetime) == len(entry.lifetime) and all(a is b for a, b in zip(lifetime, entry.lifetime))
             and record is not None and record.entry is entry and record.result.died and record.removed
             and record.result.accepted_ordinal == ticket.accepted_ordinal
             and record.death.phase == 'DRAINED' and record.death.drained
             and record.remove is not None and record.remove.phase == 'DRAINED' and record.remove.drained
             and notifications.is_removed(writer, recipe.uid), 'NPC_RESPAWN_DRAINED_REMOVED_LIFE_REQUIRED')
        return selected, entry, record

    def _pending_current(self, writer, wire, *, phase=None):
        op = self._pending
        need(op is not None and op['writer'] is writer and op['wire'] is wire
             and op['row']['operation_lock'].locked() and (phase is None or op['phase'] == phase),
             'NPC_RESPAWN_EXACT_PENDING_WIRE_REQUIRED')
        current, entry, record = self._old(writer, op['ticket'])
        before = op['selection']
        need(attack._same_binding(current[2], current[3], before[2], before[3])
             and entry is op['entry'] and record is op['record']
             and self.broker.realm.npc_edge_passability is op['old_adapter'],
             'NPC_RESPAWN_PENDING_AUTHORITY_CHANGED')
        need(op['spawn'].frame() == wire and wire is not op['ticket'].old_generation.frames[3][0],
             'NPC_RESPAWN_FRESH_SOURCE_FRAME_REQUIRED')
        return op

    def validate_pending_spawn(self, writer, wire):
        self._pending_current(writer, wire)

    def reserve(self, writer, row, wire):
        op = self._pending_current(writer, wire, phase='PREPARED')
        need(op['row'] is row, 'NPC_RESPAWN_SAME_ROW_REQUIRED')
        op['phase'], op['ticket'].phase = 'RESERVED', 'RESERVED'

    def attempt(self, writer, row, wire):
        op = self._pending_current(writer, wire, phase='RESERVED')
        need(op['row'] is row, 'NPC_RESPAWN_SAME_ROW_REQUIRED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        op['phase'], op['ticket'].phase = 'WRITE_ATTEMPTED', 'WRITE_ATTEMPTED'

    def drained(self, writer, row, wire, queued):
        op = self._pending_current(writer, wire, phase='WRITE_ATTEMPTED')
        policy = row['policy_row']
        need(op['row'] is row and policy is op['policy_row'] and queued == 0
             and policy.sent == op['sent'] + 1 and policy.pending_opcode is None
             and policy.drain_started_ns is None, 'NPC_RESPAWN_EXACT_DRAIN_REQUIRED')
        op['phase'], op['ticket'].phase = 'DRAINED', 'DRAINED'

    def require_current(self, receipt):
        need(type(receipt) is Receipt and receipt._service is self
             and self._receipts.get(self._key(receipt.writer,receipt.spawn.uid)) is receipt
             and self._phases.get(self._key(receipt.writer,receipt.spawn.uid)) in ('ADOPTING', 'COMMITTED')
             and self.current_generation(receipt.writer,target_uid=receipt.spawn.uid) is receipt.generation
             and self.broker.realm.npc_edge_passability is receipt.adapter,
             'NPC_RESPAWN_CURRENT_RECEIPT_REQUIRED')
        return receipt.generation

    async def run(self, writer, *, ticket, spawn, now_ns, prepared_adapter, adopt_generation):
        from tools.local_original_session import npc_session
        generation = self.current_generation(writer,target_uid=ticket.old_generation.recipe.uid)
        row, recipe = generation.row, generation.recipe
        key=self._key(writer,recipe.uid)
        need(type(spawn) is npc.NpcSpawn and spawn is not recipe and spawn is not generation.spawn
             and spawn.map_id == recipe.map_id and spawn.policy == recipe.policy
             and dict(spawn.fields) == dict(recipe.fields), 'NPC_RESPAWN_SAME_RECIPE_NEW_OBJECT_REQUIRED')
        need(type(prepared_adapter) is npc_edge.NpcEdgeAdapter
             and type(prepared_adapter._proof) is edge.EdgeAdapter
             and prepared_adapter._proof.reader is self.reader
             and prepared_adapter.__call__.__func__ is npc_edge.NpcEdgeAdapter.__call__
             and prepared_adapter._current.__func__ is npc_edge.NpcEdgeAdapter._current
             and callable(adopt_generation),
             'NPC_RESPAWN_CANONICAL_FRESH_ADAPTER_REQUIRED')
        factory = getattr(prepared_adapter.current, '__self__', None)
        old_adapter = self.broker.realm.npc_edge_passability
        old_factory = getattr(old_adapter.current, '__self__', None)
        need(type(factory) is npc_session.NpcSessionFactory and type(old_factory) is npc_session.NpcSessionFactory
             and factory is not old_factory and factory.adapter is prepared_adapter
             and prepared_adapter.current.__func__ is npc_session.NpcSessionFactory.current_binding
             and old_adapter.current.__func__ is npc_session.NpcSessionFactory.current_binding
             and factory.reader is self.reader and factory._session is None and not factory._closed
             and len(factory.config.spawns) == len(self.broker.realm._npc_spawns)
             and all(a is b for a,(b,_) in zip(factory.config.spawns,self.broker.realm._npc_spawns))
             and any(item is recipe for item in factory.config.spawns)
             and (len(self.broker.realm._npc_spawns)==1 or old_factory._session._target_uid==recipe.uid)
             and type(old_factory._session) is npc_session.NpcSession and not old_factory._closed
             and old_factory._session.broker is self.broker
             and old_factory._session._generation is generation
             and old_factory._session._owned_mover is generation.mover,
             'NPC_RESPAWN_FRESH_CANONICAL_FACTORY_REQUIRED')
        async with row['operation_lock']:
            need(self._pending is None and ticket.phase == 'TRIGGERED', 'NPC_RESPAWN_ONCE_PENDING_REQUIRED')
            ticket.phase = 'PREPARING'
            mover = op = None
            try:
                selected, entry, record = self._old(writer, ticket)
                wire = spawn.frame()
                result = await self.observer.sample_registry(writer, recipe.uid, now_ns=now_ns)
                # Optional metadata cannot replace the original gate/exception.
                try:
                    ticket.fresh_absence = _fresh_absence_diagnostic(
                        result, target_uid=recipe.uid, map_id=recipe.map_id)
                except BaseException:
                    pass
                need(result['status'] == 'OBSERVED' and result['uid'] == recipe.uid
                     and result['map_id'] == recipe.map_id and result['uid_absent'] is True
                     and result['source_contract_valid'] is True and result['stable_double_read'] is True
                     and result['lookup_scope'] == 'THREE_LOOKUP_VECTORS'
                     and result['observation_scope'] == 'READONLY_SNAPSHOT', 'NPC_RESPAWN_FRESH_ABSENCE_REQUIRED')
                after, actual_entry, actual_record = self._old(writer, ticket)
                need(attack._same_binding(after[2], after[3], selected[2], selected[3])
                     and actual_entry is entry and actual_record is record, 'NPC_RESPAWN_ABSENCE_AUTHORITY_CHANGED')
                mover = npc_motion.NpcMotion(spawn, self_uid=selected[1].uid,
                    interval_ns=self.broker.realm._npc_motion_interval_ns, policy=self.broker.realm._npc_motion_policy)
                op = dict(writer=writer, row=row, ticket=ticket, spawn=spawn, wire=wire,
                          selection=selected, entry=entry, record=record, old_adapter=old_adapter,
                          phase='PREPARED', policy_row=row['policy_row'], sent=row['policy_row'].sent)
                self._pending = op
                await self.broker._send(writer, row, (wire,), game=True,
                    operation_lock=row['operation_lock'], npc_respawn_operation=op)
                self._pending_current(writer, wire, phase='DRAINED')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                realm = self.broker.realm
                frames=(writer,generation.frames[1],generation.frames[2],(wire,))
                new = Generation(generation.ordinal + 1, writer, row, frames, recipe, spawn, mover)
                # Existing release revokes this writer's proof objects without
                # mutating old Hp/Death flags or the active player claim.
                self.broker._attack_session.release(writer,target_uid=recipe.uid)
                generation.mover.close()
                realm._replace_npc(writer,recipe.uid,wire,mover,frames=frames)
                mover.spawn_drained = True
                self._generations[key] = new
                receipt = Receipt(writer, row, generation, new, spawn, recipe, mover, prepared_adapter, self)
                self._receipts[key], self._phases[key] = receipt, 'ADOPTING'
                returned = adopt_generation(receipt)
                if inspect.iscoroutine(returned):
                    returned.close()  # Reject an async hook without executing it.
                need(not inspect.isawaitable(returned) and type(returned) is npc_session.NpcSession
                     and returned.factory is factory and factory._session is returned
                     and returned.broker is self.broker and not returned._closed and not factory._closed
                     and getattr(returned, '_generation', None) is new
                     and getattr(returned, '_owned_mover', None) is mover
                     and (len(self.broker.realm._npc_spawns)==1 or returned._target_uid==recipe.uid)
                     and old_factory._closed and old_factory._session._closed
                     and old_factory._session._goal is None
                     and factory.current_binding().owner is writer,
                     'NPC_RESPAWN_FRESH_SESSION_ADOPTION_REQUIRED')
                self.require_current(receipt)
                self._phases[key], ticket.phase = 'COMMITTED', 'COMMITTED'
                return receipt
            except BaseException:
                ticket.phase = 'TERMINAL'
                if mover is not None:
                    mover.fail()
                if op is not None and op['phase'] in ('RESERVED', 'WRITE_ATTEMPTED', 'DRAINED'):
                    generation.mover.fail()
                    row['failed'] = True
                    self.broker._fail('NPC_RESPAWN_OUTCOME_UNKNOWN')
                raise
            finally:
                self._pending = None

    def release(self, writer, *, target_uid=None):
        keys=({self._key(writer,target_uid)} if target_uid is not None else
              {key for mapping in (self._generations,self._tickets,self._receipts,self._phases)
               for key in mapping if key==id(writer) or type(key) is tuple and key[0]==id(writer)})
        for key in keys:
            self._generations.pop(key,None)
            ticket=self._tickets.pop(key,None)
            if ticket is not None:ticket.phase='TERMINAL'
            self._receipts.pop(key,None);self._phases.pop(key,None)
