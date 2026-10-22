"""Selected local-character HP display over the existing full SC_STATUS.

The original world send seeds all current fields. Explicit positive HP updates
advance that selection's sole status authority; transport is never readback.
No NPC HP mapping, damage formula, death, timer or persistence lives here.
"""
from dataclasses import dataclass, field
import asyncio
import hashlib
from types import MappingProxyType

from tools.local_game_session import session
from tools.local_original_session import observe

POLICY = 'EXPLICIT_LOCAL_SELECTED_FULL_STATUS_HP_NOTIFY'
REPEATED_POLICY = 'EXPLICIT_LOCAL_SELECTED_REPEATED_POSITIVE_HP_NOTIFY'
SCOPE = 'SELECTED_LOCAL_CHARACTER_HP_DISPLAY_ONLY'
OPCODE = 0x4e38
SOURCE_PINS = {
    'work/source_hp_network/source.json': '1b5c4dffee2e9a96092ebbecc2275ff72477604c9162d9fc84d02d9ddfabc8ec',
    'work/source_hp_binding/source.json': 'a38fa51fca4c2b7f6ede8ac2855cc246a73e88234bdf3191710ac9d438094773',
    'tools/local_world_protocol/model.py': '2d1ebdec0c3fc7830702691d045d89c6dacfdbf706cbf5eb9670be20e3cd5f07',
}
need = observe.need


def source_ready():
    for relative, expected in SOURCE_PINS.items():
        raw = observe.ordinary(observe.ROOT / relative).read_bytes()
        need(0 < len(raw) <= 1048576 and hashlib.sha256(raw).hexdigest() == expected,
             'HP_STATUS_SOURCE_CHANGED')


def hp_pair(current, maximum):
    need(type(current) is type(maximum) is int and 0 < current <= maximum <= 0x7fffffff,
         'HP_STATUS_EXPLICIT_POSITIVE_INT32_PAIR_REQUIRED')


def frame(fields):
    body = session.world.encode_payload(OPCODE, fields)
    return (len(body) + 6).to_bytes(2, 'little') + OPCODE.to_bytes(2, 'little') + body + b'\0\0'


@dataclass(frozen=True, slots=True)
class Snapshot:
    fields: object = field(repr=False)
    revision: int
    _service: object = field(repr=False)
    _lifetime: tuple = field(repr=False)

    @property
    def current_hp(self): return self.fields[10]

    @property
    def maximum_hp(self): return self.fields[11]

    @property
    def target_uid(self): return self.fields[1]

    @property
    def map_id(self): return self._lifetime[10].snapshot().map_id


@dataclass(frozen=True, slots=True)
class Result:
    before: Snapshot = field(repr=False)
    after: Snapshot = field(repr=False)


@dataclass(slots=True)
class _Delivery:
    writer: object = field(repr=False)
    row: object = field(repr=False)
    result: Result = field(repr=False)
    wire: bytes = field(repr=False)
    phase: str = 'PREPARED'
    previous: object = field(default=None, repr=False)
    life_context: object = field(default=None, repr=False)
    resource_context: object = field(default=None, repr=False)


class Service:
    def __init__(self, broker, *, policy, repeated_policy=None):
        need(type(policy) is str and policy == POLICY, 'HP_STATUS_EXPLICIT_POLICY_REQUIRED')
        need(repeated_policy is None or type(repeated_policy) is str and repeated_policy == REPEATED_POLICY,
             'HP_STATUS_EXPLICIT_REPEATED_POLICY_REQUIRED')
        source_ready()
        self.repeated_policy = repeated_policy
        self._repeated_histories = {}  # Append only until this selection is released.
        self.broker, self.policy = broker, policy
        self._source_guard = broker.source_guard
        self._profile = broker.realm._self_fields
        self._profile_fields = dict(self._profile)
        self._states, self._operations = {}, {}
        self._world = {}
        self._life_deliveries = {}  # Append-only, separate explicit death/recovery branch.
        self.closed = False
        self.last_result = None
        self._resource_owner = None  # Explicit opt-in canonical backing only.
        self._resource_deliveries = {}

    def _binding(self, writer, *, locked=False):
        from tools.local_original_session.broker import PersistentBroker, LocalRealm, _TransportPolicy
        broker, realm = self.broker, self.broker.realm
        need(type(self) is Service and type(broker) is PersistentBroker and type(realm) is LocalRealm
             and type(broker.policy) is _TransportPolicy
             and not self.closed and broker._hp_status is self and realm._hp_status is self
             and self.policy == POLICY and not broker._closing and not broker.failure.is_set()
             and broker.source_guard is self._source_guard,
             'HP_STATUS_CURRENT_SERVICE_REQUIRED')
        need(realm._self_fields is self._profile and dict(self._profile) == self._profile_fields,
             'HP_STATUS_PROFILE_MUTATION_REFUSED')
        rows = [r for values in broker._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'HP_STATUS_CURRENT_ROW_REQUIRED')
        row, = rows
        admitted = broker.policy._connection(writer)
        need(row['policy_row'] is admitted and admitted.writer is writer
             and not any((row['failed'], row['joined'], admitted.failed, admitted.eof,
                          admitted.task_joined, admitted.registry_removed))
             and admitted.stage == 1 and admitted.rx_boot == 2 and admitted.tx_boot == 3
             and (not locked or row['operation_lock'].locked()), 'HP_STATUS_CURRENT_LOCKED_ROW_REQUIRED')
        game, movement = realm.registry.resolve(writer), realm.service(writer)
        position, selected = movement.snapshot(), game.selection
        need(selected is not None and realm.registry.selected.get(position.name) is selected
             and selected.reference == position.name and position.uid == realm.profile_uid
             and position.map_id == 0 and movement._connection is writer and not movement.fatal
             and not realm._settings_failed and id(writer) not in realm._quit,
             'HP_STATUS_CURRENT_SELECTION_REQUIRED')
        return (broker, realm, writer, row, row['operation_lock'], broker.policy, admitted,
                realm.registry, game, selected, movement, realm.store, realm.positions, self._source_guard)

    def _checked(self, writer, *, locked=False):
        before = self._binding(writer, locked=locked)
        self._source_guard()
        source_ready()
        after = self._binding(writer, locked=locked)
        need(all(a is b for a, b in zip(before, after)), 'HP_STATUS_AUTHORITY_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return after

    def _resource_raw_current(self, writer):
        lifetime = self._checked(writer)
        snapshot = self._states.get(id(writer))
        need(type(snapshot) is Snapshot and snapshot._service is self
             and len(snapshot._lifetime) == len(lifetime)
             and all(a is b for a, b in zip(snapshot._lifetime, lifetime))
             and snapshot.target_uid == lifetime[10].snapshot().uid,
             'HP_STATUS_CURRENT_DRAINED_SNAPSHOT_REQUIRED')
        need(type(snapshot.fields) is MappingProxyType and type(snapshot.revision) is int
             and ((self._resource_owner is not None and self._resource_owner.active)
                  or ((snapshot.revision in (0, 1) if not self._repeated_histories.get(id(writer))
                   else self._repeated_snapshot(writer, snapshot))
                  or self._player_life_snapshot(writer, snapshot)))
             and {k:v for k,v in snapshot.fields.items() if k not in ((10,11,12,13,14) if self._resource_owner is not None and self._resource_owner.active and getattr(self.broker,'_buff_lifecycle',None)is not None else (10,11,12,13) if self._resource_owner is not None and self._resource_owner.active else (10,11))} ==
                 {k:v for k,v in self._profile_fields.items() if k not in ((10,11,12,13,14) if self._resource_owner is not None and self._resource_owner.active and getattr(self.broker,'_buff_lifecycle',None)is not None else (10,11,12,13) if self._resource_owner is not None and self._resource_owner.active else (10,11))},
             'HP_STATUS_NON_HP_FIELDS_CHANGED')
        life = getattr(self.broker, '_player_life', None)
        cycle = None if life is None else life._cycles.get(id(writer))
        zero = (self._resource_owner is not None and snapshot.current_hp == 0
                and cycle is not None and not cycle.terminal and cycle.status is not None
                and cycle.status.result.after is snapshot and cycle.stage == 'INIT_DRAINED'
                and cycle.status.phase == 'DRAINED')
        if not zero:
            if life is not None: life.permits_positive(writer, snapshot)
            hp_pair(snapshot.current_hp, snapshot.maximum_hp)
        return snapshot

    def current(self, writer):
        snapshot = self._resource_raw_current(writer)
        if self._resource_owner is not None:
            self._resource_owner.validate_projection(writer, snapshot)
        return snapshot

    def bind_resource_owner(self, owner, writer):
        # Existing raw current validates the original completed world/profile/
        # source/lifetime before an interceptor or durable seed is installed.
        from tools.local_original_session.hp_resource_owner import ResourceOwner
        need(type(owner) is ResourceOwner and owner.status is self
             and self._resource_owner is None, 'HP_RESOURCE_EXACT_OWNER_REQUIRED')
        snapshot = self._resource_raw_current(writer)
        owner.arm(writer, snapshot)
        self._resource_owner = owner
        return snapshot

    def bind_resource_seed_world(self, owner, writer):
        from tools.local_original_session.hp_resource_owner import ResourceOwner
        need(type(owner) is ResourceOwner and owner.status is self
             and self._resource_owner is None and id(writer) not in self._states,
             'HP_RESOURCE_EXACT_SOURCE_WORLD_SETUP_REQUIRED')
        owner.provider.current(owner._world_setup[0])
        need(owner._world_setup[0].writer is writer and not owner.active,
             'HP_RESOURCE_EXPLICIT_WORLD_SETUP_REQUIRED')
        self._resource_owner = owner

    def bind_resource_restore_owner(self, owner, writer):
        # Existing RESOURCE is installed BEFORE outgoing world_frames calls
        # fields_for; a missing participant is refused, never profile-seeded.
        from tools.local_original_session.hp_resource_owner import ResourceOwner
        need(type(owner) is ResourceOwner and owner.status is self
             and self._resource_owner is None and id(writer) not in self._states,
             'HP_RESOURCE_EXACT_RESTORE_OWNER_REQUIRED')
        owner.arm_restore(writer)
        self._resource_owner = owner

    def project_resource_commit(self, writer, row, before, fields, revision, permit):
        owner = self._resource_owner
        need(owner is not None and owner.active, 'HP_RESOURCE_BACKING_REQUIRED')
        # Raw validated borrow is deliberate: canonical commit is already ahead
        # of projection and normal current must refuse that stale projection.
        need(self._resource_raw_current(writer) is before
             and self._checked(writer, locked=True)[3] is row,
             'HP_RESOURCE_EXACT_PRECOMMIT_PROJECTION_REQUIRED')
        owner.authorize_projection(writer, row, before, fields, revision, permit)
        wire = permit.wire
        need(type(wire) is bytes and wire == frame(fields), 'HP_RESOURCE_PREFLIGHT_FULL_STATUS_CHANGED')
        lineage = before.revision + int(fields[10] != before.fields[10] or fields[11] != before.fields[11])
        after = Snapshot(MappingProxyType(dict(fields)), lineage, self, before._lifetime)
        result = Result(before, after)
        delivery = _Delivery(writer, row, result, wire, resource_context=permit)
        self._states[id(writer)] = after
        self._resource_deliveries[id(writer)] = delivery
        self.last_result = result
        self.broker.realm._world_frames.pop(id(writer), None)
        owner.projection_installed(writer, delivery, permit)
        return delivery

    def install_resource_new_life(self, owner, writer, before, cycle):
        permit=owner._hp_baseline_projection
        need(owner is self._resource_owner and owner.status is self
             and type(permit) is tuple and len(permit) == 3
             and permit[0] is writer and permit[1] is before and permit[2] is cycle
             and self._states.get(id(writer)) is before
             and self.broker._player_life._cycles.get(id(writer)) is cycle
             and cycle.stage == 'NEW_LIFE' and cycle.status.phase == 'DRAINED',
             'HP_RESOURCE_EXACT_NEW_LIFE_INSTALLATION')
        after = Snapshot(MappingProxyType(dict(before.fields)), 0, self, before._lifetime)
        self._states[id(writer)] = after
        self._operations.pop(id(writer), None)
        self._repeated_histories.pop(id(writer), None)
        self._life_deliveries.pop(id(writer), None)
        return after

    def _player_life_snapshot(self, writer, snapshot):
        history = self._life_deliveries.get(id(writer))
        if not history: return False
        head = history[-1]
        if head.result.after is snapshot: return True
        operation = self._operations.get(id(writer))
        return (operation is not None and operation.result.before is head.result.after
                and operation.result.after is snapshot and snapshot.revision == head.result.after.revision + 1)

    def current_player_life(self, writer, context):
        life = getattr(self.broker, '_player_life', None)
        need(life is not None, 'HP_STATUS_PLAYER_LIFE_DISABLED')
        life.owns_context(writer, context)
        lifetime = self._checked(writer, locked=True)
        snapshot = self._states.get(id(writer))
        need(type(snapshot) is Snapshot and snapshot._service is self
             and len(lifetime) == len(snapshot._lifetime)
             and all(a is b for a,b in zip(lifetime,snapshot._lifetime))
             and snapshot.target_uid == context.target_uid
             and (snapshot is context.snapshot or self._player_life_snapshot(writer,snapshot)),
             'HP_STATUS_PLAYER_LIFE_CURRENT_AUTHORITY_REQUIRED')
        if self._resource_owner is not None:
            self._resource_owner.validate_projection(writer, snapshot)
        return snapshot

    def prepare_player_life(self, writer, row, *, context, kind):
        from tools.local_original_session import player_life_codec as codec
        life = self.broker._player_life
        need(life.current_locked(writer, context) is row, 'HP_STATUS_PLAYER_LIFE_ROW_REQUIRED')
        before = self.current_player_life(writer, context)
        cycle = life._cycles[id(writer)]
        need(kind in ('ZERO','RESTORE') and cycle.context is context and not cycle.terminal,
             'HP_STATUS_PLAYER_LIFE_EXACT_CYCLE_REQUIRED')
        if kind == 'ZERO':
            need(cycle.stage == 'PREPARED' and before is context.snapshot
                 and (before.current_hp == 1 or life.adjudicated_lethal_locked(writer,cycle)),
                 'HP_STATUS_PLAYER_LIFE_ONE_TO_ZERO_REQUIRED')
            previous = self._operations.get(id(writer))
            history = self._repeated_histories.get(id(writer))
            if history: previous = history[-1]
            need(previous is None or previous.phase == 'DRAINED' and (previous.result.after is before
                 or self._resource_owner is not None and self._resource_owner.hp_lineage_ready(writer,before,previous)),
                 'HP_STATUS_PLAYER_LIFE_PREVIOUS_DELIVERY_REQUIRED')
            value = 0
        else:
            need(cycle.stage == 'INIT_DRAINED' and before.current_hp == 0
                 and self._life_deliveries[id(writer)][-1].phase == 'DRAINED',
                 'HP_STATUS_PLAYER_LIFE_ZERO_RESTORE_REQUIRED')
            value = before.maximum_hp
        return self._commit_current(writer,row,before,current_hp=value,
            maximum_hp=before.maximum_hp,life_context=context)

    def _repeated_snapshot(self, writer, snapshot):
        history = self._repeated_histories.get(id(writer))
        if self.repeated_policy != REPEATED_POLICY or not history:
            return False
        delivery = history[-1]
        previous = None if len(history) == 1 else history[-2]
        return (type(delivery) is _Delivery and delivery.writer is writer
                and delivery.result.after is snapshot and snapshot.revision == len(history)
                and delivery.result.before.revision + 1 == snapshot.revision
                and delivery.previous is previous
                and (delivery.result.before.revision == 0 if previous is None else
                     previous.phase == 'DRAINED' and delivery.result.before is previous.result.after))

    def repeated_delivery(self, writer):
        history = self._repeated_histories.get(id(writer))
        need(self.repeated_policy == REPEATED_POLICY and history
             and (self.current(writer) is history[-1].result.after or self._resource_owner is not None
                  and self._resource_owner.hp_lineage_ready(writer, self.current(writer), history[-1])),
             'HP_STATUS_CURRENT_REPEATED_DELIVERY_REQUIRED')
        return history[-1]

    def require_repeated_ready(self, writer, row, *, expected_snapshot, expected_revision, policy):
        need(type(policy) is str and policy == self.repeated_policy == REPEATED_POLICY,
             'HP_STATUS_EXPLICIT_REPEATED_POLICY_REQUIRED')
        lifetime = self._checked(writer, locked=True)
        before = self.current(writer)
        need(lifetime[3] is row and before is expected_snapshot
             and type(expected_revision) is int and before.revision == expected_revision
             and id(writer) not in self._operations, 'HP_STATUS_REPEATED_CURRENT_SNAPSHOT_REQUIRED')
        hp_pair(before.current_hp-1, before.maximum_hp)
        history = self._repeated_histories.get(id(writer))
        previous = None if not history else history[-1]
        need((self._resource_owner.hp_lineage_ready(writer, before, previous) if self._resource_owner is not None else
              (before.revision == 0 if previous is None else
              previous.phase == 'DRAINED' and previous.writer is writer and previous.row is row
              and previous.result.after is before and self._repeated_snapshot(writer, before))),
             'HP_STATUS_PREVIOUS_REPEATED_DRAIN_REQUIRED')
        return before, history, previous

    def prepare_repeated(self, writer, row, *, expected_snapshot, expected_revision, policy, current_hp=None):
        before, history, previous = self.require_repeated_ready(writer, row,
            expected_snapshot=expected_snapshot, expected_revision=expected_revision, policy=policy)
        value = before.current_hp-1 if current_hp is None else current_hp
        hp_pair(value,before.maximum_hp)
        need(0 < value < before.current_hp, "COMBAT_NONLETHAL_HP_DECREASE_REQUIRED")
        return self._commit_current(writer, row, before, current_hp=value,
            maximum_hp=before.maximum_hp, repeated=(history, previous))

    def fields_for(self, writer):
        if id(writer) not in self._states:
            if self._resource_owner is not None:
                return self._resource_owner.world_fields(writer, self._profile_fields)
            return None
        return self.current(writer).fields

    def begin_world(self, writer, row, replies):
        # Only the original complete ordered world response is seed material.
        if id(writer) in self._states:
            return None
        if not any(int.from_bytes(wire[2:4], 'little') == OPCODE for wire in replies):
            return None
        frames = self.broker.realm.world_frames(writer)
        starts = [i for i in range(max(0, len(replies)-2))
                  if all(replies[i+j] is frames[j] for j in range(3))]
        if not starts:
            return None
        need(len(starts) == 1 and id(writer) not in self._world,
             'HP_STATUS_WORLD_SEED_ONCE_REQUIRED')
        lifetime = self._checked(writer, locked=True)
        need(lifetime[3] is row, 'HP_STATUS_SAME_ROW_REQUIRED')
        fields = session.world.decode_payload(OPCODE, frames[1][4:-2])
        expected = (self._profile_fields if self._resource_owner is None else
                    self._resource_owner.world_fields(writer, self._profile_fields))
        need(fields == expected and fields[1] == lifetime[10].snapshot().uid,
             'HP_STATUS_EXACT_WORLD_STATUS_REQUIRED')
        hp_pair(fields[10], fields[11])
        pending = dict(lifetime=lifetime, frames=frames, fields=fields,
                       sent=row['policy_row'].sent, replies=tuple(replies), drained=[],
                       reply_object=replies, index=0, reservation=None)
        self._world[id(writer)] = pending
        if self._resource_owner is not None:
            self._resource_owner.open_world_projection(writer, pending)
        return pending

    def validate_world_pending(self, writer, row, replies, wire, pending):
        need(self._world.get(id(writer)) is pending
             and pending['reply_object'] is replies
             and len(replies) == len(pending['replies'])
             and all(a is b for a, b in zip(replies, pending['replies']))
             and 0 <= pending['index'] < len(replies)
             and wire is pending['replies'][pending['index']],
             'HP_STATUS_SAME_WORLD_BATCH_REQUIRED')
        lifetime = self._checked(writer, locked=True)
        need(lifetime[3] is row and all(a is b for a, b in zip(lifetime, pending['lifetime']))
             and all(a is b for a, b in zip(self.broker.realm.world_frames(writer), pending['frames'])),
             'HP_STATUS_SAME_WORLD_AUTHORITY_REQUIRED')
        policy = row['policy_row']
        reservation = (policy, policy.pending_opcode, policy.pending_size,
                       policy.drain_started_ns, policy.sent)
        need(policy.pending_opcode == int.from_bytes(wire[2:4], 'little')
             and policy.pending_size == len(wire) and policy.drain_started_ns is not None
             and policy.sent == pending['sent'] + pending['index'],
             'HP_STATUS_SAME_WORLD_RESERVATION_REQUIRED')
        if pending['reservation'] is None:
            pending['reservation'] = reservation
        else:
            need(pending['reservation'] == reservation,
                 'HP_STATUS_SAME_WORLD_RESERVATION_REQUIRED')
        if self._resource_owner is not None:
            self._resource_owner.world_projection_pending(writer, pending, wire)

    def world_frame_drained(self, writer, row, wire, pending, queued):
        need(self._world.get(id(writer)) is pending and type(queued) is int and queued == 0
             and self._checked(writer, locked=True)[3] is row
             and pending['reply_object'] is not None
             and len(pending['reply_object']) == len(pending['replies'])
             and all(a is b for a, b in zip(pending['reply_object'], pending['replies']))
             and wire is pending['replies'][pending['index']]
             and pending['reservation'] is not None
             and row['policy_row'] is pending['reservation'][0]
             and row['policy_row'].sent == pending['sent'] + pending['index'] + 1
             and row['policy_row'].pending_opcode is row['policy_row'].drain_started_ns is None,
             'HP_STATUS_WORLD_DRAIN_REQUIRED')
        for expected in pending['frames']:
            if wire is expected:
                need(len(pending['drained']) < 3
                     and wire is pending['frames'][len(pending['drained'])],
                     'HP_STATUS_ORDERED_WORLD_DRAIN_REQUIRED')
                pending['drained'].append(wire)
                break
        if self._resource_owner is not None:
            self._resource_owner.world_projection_drained(writer, pending)
        pending['index'] += 1
        pending['resource_drain_returned'] = False
        pending['reservation'] = None

    def finish_world(self, writer, row, pending):
        need(self._world.get(id(writer)) is pending and id(writer) not in self._states,
             'HP_STATUS_WORLD_SEED_ONCE_REQUIRED')
        lifetime = self._checked(writer, locked=True)
        policy = row['policy_row']
        need(all(a is b for a, b in zip(lifetime, pending['lifetime']))
             and len(pending['drained']) == 3 and policy.pending_opcode is None
             and pending['index'] == len(pending['replies']) and pending['reservation'] is None
             and len(pending['reply_object']) == len(pending['replies'])
             and all(a is b for a, b in zip(pending['reply_object'], pending['replies']))
             and policy.drain_started_ns is None
             and policy.sent == pending['sent'] + len(pending['replies'])
             and all(a is b for a, b in zip(self.broker.realm.world_frames(writer), pending['frames'])),
             'HP_STATUS_COMPLETE_WORLD_DRAIN_REQUIRED')
        revision = 0  # Selection HP notification lineage, never RESOURCE CAS version.
        self._states[id(writer)] = Snapshot(MappingProxyType(dict(pending['fields'])), revision, self, lifetime)
        del self._world[id(writer)]
        if self._resource_owner is not None:
            self._resource_owner.world_completed(writer, self._states[id(writer)])

    def prepare(self, writer, row, *, current_hp, maximum_hp, expected_snapshot, expected_revision):
        hp_pair(current_hp, maximum_hp)
        need(type(expected_revision) is int and expected_revision >= 0,
             'HP_STATUS_EXPLICIT_REVISION_REQUIRED')
        lifetime = self._checked(writer, locked=True)
        before = self.current(writer)
        need(lifetime[3] is row and before is expected_snapshot and before.revision == expected_revision
             and id(writer) not in self._operations, 'HP_STATUS_CURRENT_SNAPSHOT_ONCE_REQUIRED')
        need(maximum_hp == before.maximum_hp, 'HP_STATUS_CURRENT_MAXIMUM_UNCHANGED_REQUIRED')
        need(current_hp != before.current_hp, 'HP_STATUS_CURRENT_VALUE_CHANGE_REQUIRED')
        need(not self._repeated_histories.get(id(writer)), 'HP_STATUS_REPEATED_REQUIRES_EXPLICIT_API')
        return self._commit_current(writer, row, before, current_hp=current_hp, maximum_hp=maximum_hp)

    def _commit_current(self, writer, row, before, *, current_hp, maximum_hp, repeated=None, life_context=None):
        if self._resource_owner is not None:
            delivery = self._resource_owner.commit_hp_locked(writer, row, before,
                current_hp=current_hp, maximum_hp=maximum_hp, life_context=life_context)
            if life_context is not None:
                self._life_deliveries.setdefault(id(writer), []).append(delivery)
            elif repeated is None:
                self._operations[id(writer)] = delivery
            else:
                history, previous = repeated
                delivery.previous = previous
                if history is None: history = self._repeated_histories[id(writer)] = []
                history.append(delivery)
            return delivery
        fields = dict(before.fields)
        fields[10], fields[11] = current_hp, maximum_hp
        if life_context is not None:
            from tools.local_original_session import player_life_codec as codec
            wire = codec.full_status(fields)
        else:
            wire = frame(fields)  # Full required/current DTO, validated before commit.
        after = Snapshot(MappingProxyType(fields), before.revision + 1, self, before._lifetime)
        result = Result(before, after)
        delivery = _Delivery(writer, row, result, wire, life_context=life_context)
        current = (self.current(writer) if life_context is None else self.current_player_life(writer,life_context))
        need(current is before and self._checked(writer, locked=True)[3] is row,
             'HP_STATUS_PRECOMMIT_AUTHORITY_CHANGED')
        if repeated is not None:
            history, previous = repeated
            need(self._states.get(id(writer)) is before
                 and self._repeated_histories.get(id(writer)) is history
                 and (not history if previous is None else history[-1] is previous
                      and previous.phase == 'DRAINED' and previous.result.after is before)
                 and id(writer) not in self._operations, 'HP_STATUS_REPEATED_PRECOMMIT_CHANGED')
            delivery.previous = previous
        # No callback/await between current status commit and its once delivery.
        self._states[id(writer)] = after
        if life_context is not None:
            self._life_deliveries.setdefault(id(writer),[]).append(delivery)
        elif repeated is None:
            self._operations[id(writer)] = delivery
        else:
            if history is None:
                history = self._repeated_histories[id(writer)] = []
            history.append(delivery)  # Every predecessor remains in the same history.
        self.last_result = result
        self.broker.realm._world_frames.pop(id(writer), None)
        return delivery

    def validate(self, writer, wire, *, phase):
        history = self._repeated_histories.get(id(writer))
        operation = history[-1] if history else self._operations.get(id(writer))
        resource_delivery = self._resource_deliveries.get(id(writer))
        if resource_delivery is not None and resource_delivery.wire is wire:
            operation = resource_delivery
        life_history = self._life_deliveries.get(id(writer))
        if life_history and life_history[-1].wire is wire: operation = life_history[-1]
        need(type(operation) is _Delivery and operation.writer is writer
             and operation.wire is wire and operation.phase == phase
             and (self.current(writer) if operation.life_context is None else
                  self.current_player_life(writer,operation.life_context)) is operation.result.after
             and self._checked(writer, locked=True)[3] is operation.row,
             'HP_STATUS_CURRENT_ONCE_DELIVERY_REQUIRED')
        if operation.life_context is not None:
            from tools.local_original_session import player_life_codec as codec
            self.broker._player_life.current_locked(writer,operation.life_context)
            expected = codec.full_status(operation.result.after.fields)
        else: expected = frame(operation.result.after.fields)
        need(expected == wire, 'HP_STATUS_EXACT_FULL_FRAME_REQUIRED')
        return operation

    def reserve(self, writer, wire):
        operation = self.validate(writer, wire, phase='PREPARED')
        if self._resource_owner is not None and self._resource_owner._hp_effect is not None:
            self._resource_owner._hp_effect.reserve()
        operation.phase = 'RESERVED'

    def attempt(self, writer, wire):
        operation = self.validate(writer, wire, phase='RESERVED')
        if self._resource_owner is not None and self._resource_owner._hp_effect is not None:
            self._resource_owner._hp_effect.attempt()
        elif operation.resource_context is not None:
            self._resource_owner.mark_delivery(writer, operation, 'WRITE_ATTEMPTED')
        operation.phase = 'WRITE_ATTEMPTED'

    def drained(self, writer, wire):
        operation = self.validate(writer, wire, phase='WRITE_ATTEMPTED')
        if self._resource_owner is not None and self._resource_owner._hp_effect is not None:
            self._resource_owner._hp_effect.drained()
        elif operation.resource_context is not None:
            self._resource_owner.mark_delivery(writer, operation, 'DRAINED')
        operation.phase = 'DRAINED'

    def summary(self, writer):
        operation = self._operations.get(id(writer))
        need(operation is not None and operation.phase == 'DRAINED'
             and self.current(writer) is operation.result.after, 'HP_STATUS_DRAINED_RESULT_REQUIRED')
        current = operation.result.after
        return dict(status='DRAINED', target_uid=current.target_uid, map_id=current.map_id,
            revision=current.revision, current_hp=current.current_hp, maximum_hp=current.maximum_hp,
            scope=SCOPE, client_hp='UNKNOWN', player_death='NOT_IN_SCOPE')

    def release(self, writer):
        if self._resource_owner is not None:
            self._resource_owner.release_hp_selection(writer)
        resource_delivery = self._resource_deliveries.pop(id(writer), None)
        if resource_delivery is not None:
            self._resource_owner.release_delivery(writer, resource_delivery)
            if resource_delivery.phase != 'DRAINED':
                resource_delivery.phase = 'TERMINAL'
        self._states.pop(id(writer), None)
        self._world.pop(id(writer), None)
        if self._resource_owner is not None:
            self._resource_owner.release_world_projection(writer)
        for delivery in self._life_deliveries.pop(id(writer), ()):
            if delivery.phase != 'DRAINED': delivery.phase = 'TERMINAL'
        history = self._repeated_histories.pop(id(writer), ())
        for delivery in history:
            if delivery.phase != 'DRAINED': delivery.phase = 'TERMINAL'
        operation = self._operations.pop(id(writer), None)
        if operation is not None and operation.phase != 'DRAINED':
            operation.phase = 'TERMINAL'

    def close(self):
        for writer in [value._lifetime[2] for value in self._states.values()]:
            self.release(writer)
        self._world.clear()
        self.closed = True
