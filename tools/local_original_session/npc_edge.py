"""NPC exact-edge callback for an explicit local destination subset.

The NPC start comes from the current server mover, never MyPlayer prediction.
MyPlayer remains a separate selected-world/reader owner check. Both actual
spatial stores must prove empty or contain only the same-query exact current
moving Monster at the authoritative start. Other pointers remain UNKNOWN.
This reuses a conservative local filter, not full original Navigation policy.
"""
from dataclasses import dataclass
import hashlib
import struct

from tools.local_original_session import attack, edge, movement, npc_motion, npc_observe, observe

need = observe.need


@dataclass(frozen=True, slots=True)
class NpcEdgeBinding:
    """Current trusted registry projection, not an occupancy assertion.

    owner is the literal selected writer and broker is its PersistentBroker.
    The realm, admitted claim and retained native owner are resolved directly
    through that broker. No caller-constructed state authorizes an edge.
    """
    owner: object
    broker: object


class NpcEdgeAdapter:
    """Synchronous, injectable retained reader plus current registry resolver.

    current() must project the presently admitted selected writer from the real
    registry, or fail/return None when it is no longer current. It must not cache
    a selection, mutate state or reenter the reader. This adapter performs no
    await, process attachment, client call, input, scheduling or authority write.
    A repeated read is not an atomic snapshot or a new lifetime guarantee.
    """
    def __init__(self, reader, *, current):
        need(callable(current), 'NPC_EDGE_CURRENT_BINDING_REQUIRED')
        self._proof = edge.EdgeAdapter(reader)
        self.current = current
        self.last_result = dict(status='UNKNOWN', reason='NOT_SAMPLED')

    def _current(self, uid, map_id, start):
        from tools.local_original_session.broker import LocalRealm, PersistentBroker, _TransportPolicy
        binding = self.current()
        need(type(binding) is NpcEdgeBinding, 'NPC_EDGE_CURRENT_BINDING_REQUIRED')
        need(not isinstance(binding.owner, (str, int, float, bool, bytes, dict, list,
                                           tuple, type(None))), 'NPC_EDGE_LITERAL_OWNER_REQUIRED')
        broker, reader = binding.broker, self._proof.reader
        need(type(broker) is PersistentBroker, 'NPC_EDGE_REAL_BROKER_REQUIRED')
        policy, retained, member = broker.policy, reader.owner, reader.member
        need(type(policy) is _TransportPolicy and retained is not None
             and policy.owner is retained and not retained.closed
             and member is retained.child and member is not None
             and policy.handle is retained.owner_handle and policy.job is retained.owner_job
             and member.process == retained.owner_handle and member.job == retained.owner_job,
             'NPC_EDGE_SAME_RETAINED_BROKER_REQUIRED')
        need(not broker._closing and not broker.failure.is_set() and policy.state == 'OPEN',
             'NPC_EDGE_BROKER_LIFETIME_REQUIRED')
        claims = [row for rows in broker._claims.values() for row in rows
                  if row['writer'] is binding.owner]
        need(len(claims) == 1, 'NPC_EDGE_CURRENT_CLAIM_REQUIRED')
        row, = claims
        policy_row = policy._connection(binding.owner)
        need(row['policy_row'] is policy_row and policy_row.writer is binding.owner
             and policy_row.stage == 1 and not row['failed'] and not row['joined']
             and not policy_row.eof and not policy_row.task_joined and not policy_row.registry_removed,
             'NPC_EDGE_CURRENT_CLAIM_REQUIRED')
        realm = broker.realm
        need(type(realm) is LocalRealm, 'NPC_EDGE_REAL_LOCAL_REALM_REQUIRED')
        service = realm.service(binding.owner)
        selected = service.snapshot()
        mover = realm.npc_mover(binding.owner)
        need(type(service) is movement.MovementService and type(selected) is movement.Position
             and type(mover) is npc_motion.NpcMotion,
             'NPC_EDGE_CURRENT_AUTHORITY_REQUIRED')
        state = mover.state
        need(type(state) is npc_motion.State and not mover.closed and not mover.fatal
             and mover.pending is None and mover.spawn_drained is True,
             'NPC_EDGE_CURRENT_DRAINED_MOVER_REQUIRED')
        need(type(state.uid) is int and 0 < state.uid <= 0xffffffff
             and state.uid != selected.uid and type(state.map_id) is int
             and type(state.packed) is int
             and (state.uid, state.map_id, state.packed) == (uid, map_id, start)
             and selected.map_id == map_id, 'NPC_EDGE_CURRENT_UID_MAP_START_MISMATCH')
        admission = (policy, row, policy_row, retained, member, realm, broker.failure,
                     *(attack._handle_value(value) for value in (
                         policy.handle, policy.job, retained.owner_handle, retained.owner_job,
                         member.process, member.job)))
        return binding, admission, service, selected, mover, state

    def __call__(self, uid, map_id, start, direction, destination):
        proof, budget = self._proof, None
        details = dict(phase='REQUEST', local_server_subset='NPC_EMPTY_OR_EXACT_SELF_DESTINATION_ONLY',
                       official_navigation_equivalence='UNKNOWN', snapshot_atomic=False,
                       stable_double_read=False, occupancy='UNKNOWN',
                       authoritative_start_grid=None, observed_client_grid=None, observed_npc_grid=None,
                       client_grid_used_as_authority=False,
                       nonempty_self_npc='NOT_REQUIRED', self_npc_candidates=0, raw_candidates_by_store=[])
        try:
            grid, target = edge._request(proof.tile, uid, map_id, start, direction, destination)
            need(tuple(proof.tile.DELTAS) == movement.authority.DELTAS,
                 'NPC_EDGE_DIRECTION_CONTRACT_CHANGED')
            initial, admission, service, selected, mover, state_before = self._current(uid, map_id, start)
            details['authoritative_start_grid'] = list(grid)
            native, sampler = proof._binding()
            reader = proof.reader
            retained = (reader.owner, reader.member, native, sampler)
            budget = edge._Budget(native, sampler, diagnostic=details)
            exact, targets, authority_before, monster_checks = None, None, None, None
            with budget.installed():
                details['phase'] = 'SOURCE_BEFORE'
                proof._code(sampler, budget)
                for table in proof.tables:
                    raw = sampler.read(sampler.g['base'] + table['rva'], table['length'], image=True)
                    need(hashlib.sha256(raw).hexdigest() == table['sha256'],
                         'EDGE_DIRECTION_CONSTANT_CHANGED')
                details['phase'] = 'SELECTED_WORLD'
                # This is the genuine selected player UID, not the NPC UID.
                # Its coordinates are observed, never used for the NPC query.
                reads, actors, context, route, world_state, scene_raw, _ = edge._world(
                    native, sampler, proof.public, proof.world, proof.position_source,
                    selected.uid, map_id, grid, require_current_start=False,
                    observation=details)
                details['phase'] = 'TILES'
                flags, resources = [], {}
                for segment, local in proof.tile.probe_cells(grid, direction):
                    if segment not in resources:
                        resources[segment] = proof.tile.lookup_resource(
                            reads, context, (segment[0] << 16) | segment[1])
                    cell, _, _ = proof.tile.cell(reads, resources[segment], local)
                    flags.append(struct.unpack_from('<H', cell, 4)[0])
                blocked = proof.tile.flag_blocked(direction, flags, 1)
                if not blocked:
                    for index, offset in enumerate((0, 0x40)):
                        details['phase'] = 'SPATIAL_STORE_' + str(index)
                        at = actors + 0x798 + offset
                        try:
                            result = proof.nav.empty_store(reads, at, target=target)
                            need(result.get('complete') is True and result.get('raw_candidates') == 0,
                                 'NPC_EDGE_COMPLETE_EMPTY_STORE_REQUIRED')
                            details['raw_candidates_by_store'].append(0)
                            continue
                        except Exception as error:
                            if observe.reason(error) != 'SPATIAL_TARGET_NONEMPTY_UNCLASSIFIED':
                                raise
                        details['nonempty_self_npc'] = 'UNKNOWN'
                        if exact is None:
                            details['phase'] = 'EXACT_SELF_NPC_SOURCE'
                            monster, common, inherited = npc_observe._source()
                            monster_checks = inherited + proof.public['Position']['source_checks'] + proof.lookup_contract['code_checks']
                            monster_checks = list({(c['rva'], c['length'], c['sha256']): c
                                                   for c in monster_checks}.values())
                            proof._code(sampler, budget, monster_checks)
                            targets = attack.AttackTargets(initial.broker, reader)
                            authority_before = targets._project(initial.owner, attack.AttackRequest(uid))
                            need(authority_before[1] is selected and authority_before[2:4] == grid,
                                 'NPC_EDGE_EXACT_CURRENT_AUTHORITY_REQUIRED')
                            exact, current_grid = npc_observe._resolve_monster(
                                reads, sampler, proof, monster, common, actors, uid)
                            need(current_grid == list(grid), 'NPC_EDGE_EXACT_CURRENT_START_REQUIRED')
                            details['observed_npc_grid'] = current_grid
                            details['nonempty_self_npc'] = 'TYPED_PENDING_RECHECK'
                        details['phase'] = 'SPATIAL_EXACT_SELF_' + str(index)
                        # This existing helper audits the entire store and
                        # compares every target-vector pointer to one exact
                        # object. Its filter is pointer equality; it performs no
                        # MyPlayer cast. The Monster proof above replaces the
                        # caller's player proof for this explicit local subset.
                        details['self_npc_candidates'] += edge._empty_or_exact_self_store(
                            proof.nav, reads, at, target, exact, details)
                    details['occupancy'] = ('BOTH_COMPLETE_TARGETS_EXACT_SELF_NPC_OR_EMPTY'
                                            if exact is not None else 'BOTH_COMPLETE_TARGETS_EMPTY')
                details['phase'] = 'TYPED_RECHECK'
                budget.verify()
                details['phase'] = 'WORLD_RECHECK'
                budget.retain = False
                try:
                    need(sampler.read(world_state + 0x360, 36) == scene_raw
                         and sampler.route() == route, 'EDGE_WORLD_OWNER_CHANGED')
                finally:
                    budget.retain = True
                details['phase'] = 'SOURCE_AFTER'
                proof._code(sampler, budget)
                if exact is not None:
                    proof._code(sampler, budget, monster_checks)
                    npc_observe._source()
                    authority_after = targets._project(initial.owner, attack.AttackRequest(uid))
                    need(authority_after[1:5] == authority_before[1:5]
                         and targets.same_authority(authority_after, authority_before),
                         'NPC_EDGE_EXACT_AUTHORITY_CHANGED')
                details['phase'] = 'OWNER_AFTER'
                need(all(actual is before for actual, before in zip(
                    (reader.owner, reader.member, reader.backend, reader.sampler), retained)),
                    'NPC_EDGE_RETAINED_OWNER_CHANGED')
                reader.validate()
                after, admission_after, service_after, selected_after, mover_after, state_after = self._current(uid, map_id, start)
                need(after.owner is initial.owner and after.broker is initial.broker
                     and attack._same_binding(admission_after[:7], admission_after[7:],
                                              admission[:7], admission[7:])
                     and service_after is service and selected_after is selected
                     and mover_after is mover and state_after is state_before,
                     'NPC_EDGE_AUTHORITY_CHANGED')
            details.update(phase='COMPLETE', stable_double_read=True)
            if exact is not None:
                details['nonempty_self_npc'] = 'EXACT_CURRENT_MOVING_MONSTER'
            self.last_result = dict(status=('BLOCKED_MASK1' if blocked else
                                    'CLEAR_EXACT_SELF_NPC_SUBSET' if exact is not None else 'CLEAR_EMPTY_SUBSET'),
                                    reason=None, typed_bytes_requested=budget.spent, **details)
            return not blocked
        except Exception as error:
            self.last_result = dict(status='UNKNOWN', reason=observe.reason(error),
                                    typed_bytes_requested=0 if budget is None else budget.spent,
                                    **details)
            return None
