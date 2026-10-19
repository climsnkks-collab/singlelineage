"""Explicit one-step goal trial over the existing serial product poll.

No sender, native call, task, timer, collision implementation or saved state.
Transport, server commit and readonly client pose/idle remain separate facts.
"""
import asyncio
import time

from tools.local_original_session import attack, movement, npc_observe, npc_session

need = attack.need
WAIT_NS = 15_000_000_000
MIN_INTERVAL_NS = 500_000_000
MOTION_SAMPLE = getattr(npc_observe.NpcObserver, 'sample_motion', None)


def configuration(features, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import feature_config, inventory as inv, inventory_store, npc, npc_motion
    from tools.local_native_login_spawn_render_retry_runtime import spawn_hook
    need(type(features) is feature_config.Features and len(features.spawns) == 1
         and type(features.interval_ns) is int and 0 < features.interval_ns < (1 << 63)
         and features.motion_policy == npc_motion.LOCAL_PRE_STEP
         and features.goal_policy == npc_session.AXIS_SIGN_GOAL and features.goal is None
         and features.attack_policy == feature_config.ATTACK_INTENT_POLICY
         and features.attack_feedback is features.attack_hp_provider is features.npc_death_policy
             is features.npc_remove_policy is None
         and features.item_use_policy is features.item_equipment_policy is features.inventory_update_policy is None,
         'SCENARIO_NPC_MOTION_EXPLICIT_CONFIG_REQUIRED')
    need(inventory is True and auto_inventory is True and features.inventory_policy == inv.POLICY
         and type(features.inventory_frame) is bytes
         and features.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
         and features.inventory_store_policy == inventory_store.POLICY,
         'SCENARIO_NPC_MOTION_SOURCE_QUIT_PREPARATION_REQUIRED')
    inv.validate_frame(features.inventory_frame)
    profile = spawn_hook.profiles()[0]
    npc.prepare(features.spawns, self_uid=profile.fields[1])
    return features  # The original object is used by scenario, factory and broker.


def grid(value):
    return (tuple(value) if type(value) in (tuple, list) and len(value) == 2
            and all(type(n) is int and 0 <= n <= 65535 for n in value) else None)


class Trial:
    def __init__(self, scenario, runtime, *, goal, clock_ns=time.monotonic_ns):
        need(type(goal) is tuple and grid(goal) == goal, 'SCENARIO_NPC_MOTION_EXPLICIT_GOAL_REQUIRED')
        self.scenario, self.runtime, self.goal, self.clock_ns = scenario, runtime, goal, clock_ns
        self.session = runtime.npc_session
        need(type(self.session) is npc_session.NpcSession
             and self.session.factory._session is self.session
             and self.session.factory.reader is scenario.reader,
             'SCENARIO_NPC_MOTION_ACTUAL_SESSION_REQUIRED')
        need(callable(MOTION_SAMPLE) and npc_observe.NpcObserver.sample_motion is MOTION_SAMPLE,
             'SCENARIO_NPC_MOTION_CANONICAL_OBSERVER_REQUIRED')
        self.observer = npc_observe.NpcObserver(self.session.broker, scenario.reader)
        self.phase = 'WAIT_PREPARATION'
        self.started_ns = self.published_ns = None
        self.writer = self.row = self.mover = self.before = self.after = self.life = None
        self.event_start = self.sent_before = self.movement_counters = None
        self.retained_scalars = None
        self.goal_claimed = False
        self.at_goal = False
        self.samples = 0
        self.result = dict(status='NOT_REQUESTED', goal=list(goal), goal_policy=npc_session.AXIS_SIGN_GOAL,
            preparation='EXISTING_SAVED_ROW_AND_WORLD_ONLY', server_before=None, server_after=None,
            transport=None, pre_pose=None, post_pose=None, at_goal=False, goal_submissions=0,
            npc_poll=None,
            observation_scope='READONLY_NPC_POSE_AND_IDLE', client_pose_authority=False,
            screen='UNKNOWN', automatic_retry=False)

    @staticmethod
    def state(state):
        return dict(uid=state.uid, map_id=state.map_id, grid=list(movement.authority.unpack_grid(state.packed)),
                    direction=state.direction, goal=None if state.goal is None else list(state.goal),
                    last_step_ns=state.last_step_ns)

    def _life(self, broker):
        realm = broker.realm
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is self.writer]
        need(len(rows) == 1 and rows[0] is self.row and not self.row['failed'] and not self.row['joined'],
             'SCENARIO_NPC_MOTION_SAME_CLAIM_REQUIRED')
        game = realm.registry.resolve(self.writer)
        spawn, = [spawn for spawn, _ in realm._npc_spawns if spawn.uid == self.mover.state.uid]
        return (broker, realm, realm.registry, game, game.selection, realm.service(self.writer),
                realm._npc_frames[id(self.writer)], realm._npc_spawns, spawn,
                self.row['operation_lock'], self.row['policy_row'], realm.npc_mover(self.writer),
                realm.npc_edge_passability, self.session.factory, broker.policy,
                self.scenario.reader, self.scenario.reader.owner, self.scenario.reader.member,
                self.scenario.reader.backend, self.scenario.reader.sampler,
                self.session.factory.reader, self.session.factory.config,
                realm.service(self.writer).snapshot(), getattr(self.scenario.reader.member, 'identity', None))

    def _retained_scalars(self):
        reader = self.scenario.reader
        owner, member = reader.owner, reader.member
        return (owner.owner_handle, owner.owner_job, member.process, member.job,
                getattr(member, 'pid', None), getattr(member, 'identity', {}).get('birth'),
                reader.backend.handle, reader.sample_byte_limit,
                getattr(reader, 'closed', False), owner.closed)

    def _same(self, broker, *, transition=False):
        need(self.runtime.npc_session is self.session and self.session.broker is broker
             and self.session.factory._session is self.session and not self.session._closed
             and self.session.factory.reader is self.scenario.reader
             and not self.session.factory._closed and not broker._closing and not broker.failure.is_set(),
             'SCENARIO_NPC_MOTION_SESSION_CHANGED')
        actual = self._life(broker)
        need(len(actual) == len(self.life) and all(a is b for a, b in zip(actual, self.life)),
             'SCENARIO_NPC_MOTION_SELECTION_CHANGED')
        need(all(type(a) is type(b) and a == b
                 for a, b in zip(self._retained_scalars(), self.retained_scalars)),
             'SCENARIO_NPC_MOTION_RETAINED_SCALARS_CHANGED')
        state = self.mover.state
        need(not self.mover.closed and not self.mover.fatal and self.mover.pending is None
             and self.mover.spawn_drained is True
             and (transition or state is (self.after or self.before))
             and self.session._goal is (self.goal if self.goal_claimed else None),
             'SCENARIO_NPC_MOTION_STATE_CHANGED')
        service = actual[5]
        need((service.requests_received, service.committed, service.corrections_prepared) == self.movement_counters,
             'SCENARIO_NPC_MOTION_PLAYER_COMMAND_NOT_PART_OF_TRIAL')
        binding = self.session.current_binding()
        need(binding is not None and binding.owner is self.writer and binding.broker is broker,
             'SCENARIO_NPC_MOTION_CURRENT_BINDING_REQUIRED')

    def current(self, broker, *, transition=False):
        self._same(broker, transition=transition)
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        self._same(broker, transition=transition)  # Callback cannot replace the selection/state.
        need(self.clock_ns() - self.started_ns < WAIT_NS, 'SCENARIO_NPC_MOTION_ORIGINAL_DEADLINE')

    def begin(self, broker):
        need(self.phase == 'WAIT_PREPARATION' and self.scenario.inventory['status'] == 'COMMITTED'
             and self.scenario.attack['status'] == 'NOT_REQUESTED' and not self.scenario.moves,
             'SCENARIO_NPC_MOTION_ONCE_PREPARATION_REQUIRED')
        self.writer = self.scenario.move_bound[0]
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is self.writer]
        need(len(rows) == 1, 'SCENARIO_NPC_MOTION_SAME_CLAIM_REQUIRED')
        self.row = rows[0]
        self.mover = broker.realm.npc_mover(self.writer)
        self.before = self.mover.state
        start = movement.authority.unpack_grid(self.before.packed)
        need(self.before.last_step_ns is self.before.goal is None and self.session._goal is None
             and max(abs(a - b) for a, b in zip(start, self.goal)) == 1,
             'SCENARIO_NPC_MOTION_FRESH_ONE_STEP_GOAL_REQUIRED')
        self.life = self._life(broker)
        self.retained_scalars = self._retained_scalars()
        service = self.life[5]
        self.movement_counters = (service.requests_received, service.committed, service.corrections_prepared)
        self.started_ns = self.clock_ns()
        self.event_start, self.sent_before = broker.policy.events, self.row['policy_row'].sent
        self.result.update(status='PENDING', server_before=self.state(self.before))
        self.phase = 'PRE_POSE'
        self.current(broker)

    async def sample(self, broker):
        now = self.clock_ns()
        self.current(broker)
        observer = self.observer
        need(type(observer) is npc_observe.NpcObserver and type(observer).sample_motion is MOTION_SAMPLE
             and observer.sample_motion.__self__ is observer and observer.sample_motion.__func__ is MOTION_SAMPLE
             and observer.targets.broker is broker and observer.targets.reader is self.scenario.reader,
             'SCENARIO_NPC_MOTION_CANONICAL_OBSERVER_REQUIRED')
        async with self.row['operation_lock']:
            self.current(broker)
            result = await self._sample_motion_locked(broker, now)
            self.current(broker)
        self.samples += 1
        self.result['pre_pose' if self.phase == 'PRE_POSE' else 'post_pose'] = result
        need(type(result) is dict and result.get('status') == 'OBSERVED'
             and result.get('uid') == self.before.uid and result.get('map_id') == self.before.map_id
             and result.get('source_contract_valid') is True and result.get('source_owner_revalidated') is True
             and (result.get('stable_double_read') is True and result.get('read_consistency') == 'STRICT_STABLE'
                  or result.get('stable_double_read') is False
                  and type(result.get('read_consistency')) is str
                  and result['read_consistency'] in (
                      'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE',
                      'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_FINAL_READBACK',
                      'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_BOTH')
                  and type(result.get('motion_scope')) is str
                  and result['motion_scope'] == 'READONLY_DIRECT_NPC_MOTION_STOP')
             and result.get('snapshot_atomic') is False and result.get('client_grid_used_as_authority') is False
             and type(result.get('typed_bytes_requested')) is int
             and 0 <= result['typed_bytes_requested'] <= 16384 and result.get('typed_byte_limit') == 16384
             and result.get('max_samples_per_second') == 2,
             'SCENARIO_NPC_MOTION_POSE_UNKNOWN')
        expected = movement.authority.unpack_grid((self.after or self.before).packed)
        need(grid(result.get('server_grid')) == expected, 'SCENARIO_NPC_MOTION_OBSERVED_AUTHORITY_CHANGED')
        matched = result.get('coordinates_match') is True and grid(result.get('client_grid')) == expected
        idle = result.get('npc_idle') is True
        if self.phase == 'PRE_POSE':
            need(matched and idle, 'SCENARIO_NPC_MOTION_INITIAL_POSE_IDLE_REQUIRED')
            self.phase = 'GOAL_READY'
        elif matched and idle and self.at_goal:
            self._complete_arrival()

    def _complete_arrival(self):
        self.result.update(status='COMMITTED', at_goal=True)
        self.phase = 'DONE'
        self.scenario.stage = 'NPC_MOTION_COMPLETE_STOP_REQUESTED'
        self.scenario.stop.set()

    async def _sample_motion_locked(self, broker, now):
        return await self.observer.sample_motion(self.writer, self.before.uid, now_ns=now)

    def submit(self, broker):
        self.current(broker)
        need(self.phase == 'GOAL_READY' and not self.goal_claimed, 'SCENARIO_NPC_MOTION_GOAL_NO_REPLAY')
        self.goal_claimed = True  # Exactly one submit, even if the API raises.
        self.result['goal_submissions'] = 1
        self.published_ns = self.clock_ns()
        self.session.submit_goal(goal=self.goal)
        self.current(broker)
        self.phase = 'WAIT_MOVE'

    def after_poll(self, broker, result):
        if self.phase not in ('WAIT_MOVE', 'POST_POSE'):
            return
        self.current(broker, transition=self.phase == 'WAIT_MOVE')
        self.result['npc_poll'] = {key: result.get('npc', {}).get(key)
                                  for key in ('status', 'reason', 'typed_slot_reserved')}
        changed = result.get('npc', {}).get('changed_read1')
        if type(changed) is dict:
            self.result['npc_poll']['changed_read1'] = {key: changed[key] for key in
                ('address', 'size', 'field_role', 'before_sha256', 'after_sha256',
                 'capture_phase', 'comparison')}
        status = result.get('npc', {}).get('status')
        if self.phase == 'WAIT_MOVE':
            if status == 'OBSERVATION_CADENCE':
                need(self.mover.state is self.before, 'SCENARIO_NPC_MOTION_STATE_CHANGED')
                return
            need(status == 'MOVED' and result.get('npc', {}).get('typed_slot_reserved') is True,
                 'SCENARIO_NPC_MOTION_STEP_NOT_COMMITTED')
            after = self.mover.state
            need(after is not self.before and movement.authority.unpack_grid(after.packed) == self.goal
                 and after.goal is self.goal and type(after.last_step_ns) is int
                 and after.last_step_ns >= self.published_ns,
                 'SCENARIO_NPC_MOTION_ONE_STEP_COMMIT_REQUIRED')
            self.after = after
            events = list(broker.policy.log)
            offset = self.event_start - (broker.policy.events - len(events))
            need(0 <= offset <= len(events), 'SCENARIO_NPC_MOTION_TRANSPORT_EVENTS_DROPPED')
            drained = [event for event in events[offset:] if event[0] == 'tx' and event[2] == 0x4e2c]
            policy_row = self.row['policy_row']
            need(len(drained) == 1 and policy_row.sent >= self.sent_before + 1
                 and policy_row.pending_opcode is policy_row.drain_started_ns is None
                 and policy_row.pending_size == 0,
                 'SCENARIO_NPC_MOTION_ONCE_DRAIN_REQUIRED')
            self.result.update(server_after=self.state(after), transport=dict(state='DRAINED', opcode=0x4e2c,
                drained_frames=1, commit_count=1, typed_slot_reserved=True,
                proof_scope='TRANSPORT_DRAIN_ONLY'))
            self.phase = 'POST_POSE'
        else:
            need(status == 'AT_GOAL', 'SCENARIO_NPC_MOTION_POST_GOAL_REQUIRED')
            self.at_goal = True
            self.result['at_goal'] = True
        self.current(broker)

    def fail(self, error):
        from tools.local_original_session import launcher
        reason = launcher.safe_error_code(error) or type(error).__name__
        self.result.update(status='UNKNOWN', reason=reason)
        self.phase = 'FAILED'
        self.scenario.error = self.scenario.error or reason
        self.scenario.stage = 'NPC_MOTION_UNKNOWN_STOP_REQUESTED'
        self.scenario.stop.set()


class Runtime:
    def __init__(self, runtime, scenario, *, goal):
        self.original, self.scenario = runtime, scenario
        self.manual = runtime.manual
        self.npc_session = runtime.npc_session
        self.trial = Trial(scenario, runtime, goal=goal)
        scenario.npc_motion_trial = self.trial

    async def poll(self, monitor=None):
        trial = self.trial
        if self.scenario.stop.is_set():
            return {}
        broker = self.npc_session.broker
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_NPC_MOTION_SAME_MONITOR_REQUIRED')
            if trial.phase not in ('WAIT_PREPARATION', 'DONE', 'FAILED'):
                trial.current(broker)
                due = trial.clock_ns() / 1e9 >= monitor.next_memory
                if trial.phase in ('PRE_POSE', 'POST_POSE') and due:
                    monitor.next_memory = trial.clock_ns() / 1e9 + .5
                    try:
                        await trial.sample(broker)
                    finally:
                        monitor.next_memory = max(monitor.next_memory, trial.clock_ns() / 1e9 + .5)
                elif trial.phase == 'GOAL_READY' and due:
                    trial.submit(broker)
            if self.scenario.stop.is_set():
                self.scenario.save()
                return {}
            result = await self.original.poll(monitor)
            trial.after_poll(broker, result)
            self.scenario.save()
            return result
        except asyncio.CancelledError:
            trial.fail(ValueError('SCENARIO_NPC_MOTION_CANCELLED'))
            self.scenario.save()
            raise
        except Exception as error:
            trial.fail(error)
            self.scenario.save()
            return {}

    def close(self):
        self.original.close()
