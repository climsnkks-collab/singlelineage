"""Explicit trial lifetime decision, scheduled in the existing serial poll.

Install as tools.local_original_session.npc_combat_focused. No process/native
sender, task, timer, raw attack packet, or persistent game policy is introduced.
"""
import time

from tools.local_original_session import attack, attack_action_observe, npc_death, npc_observe

need = attack.need
WAIT_NS = 15_000_000_000
INTERVAL_NS = 500_000_000
REGISTRY_SAMPLE = npc_observe.NpcObserver.sample_registry


def configuration(features):
    from tools.local_original_session import npc_hp
    need(type(features.attack_hp_provider) is npc_hp.ExplicitInputs
         and features.npc_death_policy == npc_death.DEATH_POLICY
         and features.npc_remove_policy == npc_death.REMOVE_POLICY
         and features.attack_feedback is not None,
         'SCENARIO_NPC_EXPLICIT_HP_DEATH_REMOVE_REQUIRED')
    spawn, = features.spawns
    row, = features.attack_hp_provider.rows
    need(row.target == npc_hp.Target(spawn.uid, spawn.map_id, spawn.fields[3], spawn.fields[39])
         and row.hit.landed is True and row.hit.damage >= row.hp.current,
         'SCENARIO_NPC_EXACT_LETHAL_LOCAL_INPUT_REQUIRED')
    return features


class Trial:
    def __init__(self, scenario, runtime, *, clock_ns=time.monotonic_ns):
        self.scenario, self.runtime, self.clock_ns = scenario, runtime, clock_ns
        self.started_ns = None
        self.writer = self.row = self.session = self.hp_result = None
        self.hp_entry = self.notification_record = self.lifetime = None
        self.ordinal = None
        self.phase = 'WAIT_ATTACK'
        self.remove_claimed = False
        self.death_sample_claimed = False
        self.registry_sample_claimed = False
        self.result = dict(status='NOT_REQUESTED', server_hp=None,
            death_transport=None, death_action=None, remove_transport=None, registry=None,
            remove_decision='EXPLICIT_BACKEND_TRIAL_LIFETIME', hp_wire='UNKNOWN', screen='UNKNOWN',
            snapshot_atomic=False, automatic_retry=False)

    def begin(self, broker):
        scenario = self.scenario
        need(self.phase == 'WAIT_ATTACK' and scenario.attack['status'] == 'COMMITTED',
             'SCENARIO_NPC_ONCE_ATTACK_REQUIRED')
        self.writer, self.session = scenario.move_bound[0], scenario.attack_session
        need(self.session is broker._attack_session and not self.session.closed and not self.session.fatal,
             'SCENARIO_NPC_CURRENT_SESSION_REQUIRED')
        projected = self.session.targets._project(self.writer, attack.AttackRequest(scenario.attack['target_uid']))
        self.row = projected[0]
        self.hp_result = self.session.last_hp_result
        need(self.hp_result is not None and self.hp_result.died
             and self.hp_result.after.current == 0 and self.hp_result.hit.landed is True
             and self.hp_result.target.uid == scenario.attack['target_uid']
             and self.hp_result.accepted_ordinal == self.session.accepted_count,
             'SCENARIO_NPC_ACCEPTED_LETHAL_COMMIT_REQUIRED')
        self.ordinal = self.hp_result.accepted_ordinal
        self.hp_entry = self.session._hp._entries.get((id(self.writer), self.hp_result.target.uid))
        self.notification_record = self.session._notifications._records.get((id(self.writer), self.hp_result.target.uid))
        need(self.hp_entry is not None and self.notification_record is not None
             and self.notification_record.entry is self.hp_entry
             and self.notification_record.result is self.hp_result,
             'SCENARIO_NPC_ACCEPTED_LETHAL_RECORD_REQUIRED')
        self.lifetime = self.hp_entry.lifetime
        self.started_ns = self.clock_ns()
        self.result.update(status='PENDING', server_hp=self.hp_result.metadata())
        self.result['death_transport'] = self.transport(npc_death.DEATH_OPCODE)
        snapshots = scenario.attack['attack_observations']
        matches = [(stage, row) for stage, row in snapshots.items()
                   if stage in ('post_feedback', 'next_strict_idle') and row.get('status') == 'OBSERVED'
                   and (row.get('death_current') is True or row.get('death_queued') is True)]
        if matches:
            stage, row = matches[-1]
            self.result['death_action'] = dict(status='OBSERVED', reason=None, source='COMMAND_RESULT',
                stage=stage, death_current=row['death_current'], death_queued=row['death_queued'],
                observation_scope='READONLY_ACTION_SNAPSHOTS')
            self.phase = 'REMOVE'
        else:
            self.phase = 'DEATH_SAMPLE'
        self.current(broker)

    def transport(self, opcode):
        row = self.session.metadata().get('npc_notifications', {}).get('last', {}).get(hex(opcode))
        need(type(row) is dict and row.get('target_uid') == self.hp_result.target.uid
             and row.get('accepted_ordinal') == self.ordinal and row.get('phase') == 'DRAINED'
             and row.get('write_attempted') is True and row.get('drained') is True
             and row.get('delivery') == 'TRANSPORT_DRAIN_ONLY',
             'SCENARIO_NPC_NOTIFICATION_DRAIN_REQUIRED')
        return dict(row)

    def _same_lifetime(self, broker):
        need(broker._attack_session is self.session and self.session.last_hp_result is self.hp_result
             and self.session.accepted_count == self.ordinal and not self.session.closed and not self.session.fatal,
             'SCENARIO_NPC_SELECTED_LIFETIME_CHANGED')
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is self.writer]
        need(len(rows) == 1 and rows[0] is self.row, 'SCENARIO_NPC_SAME_ROW_REQUIRED')
        key, realm = (id(self.writer), self.hp_result.target.uid), broker.realm
        need(self.session._hp._entries.get(key) is self.hp_entry
             and self.session._notifications._records.get(key) is self.notification_record,
             'SCENARIO_NPC_LETHAL_RECORD_RELEASED')
        # Same selected-life identities after Remove without target projection:
        # the latter correctly rejects the selected-life tombstone. Position
        # replacement is deliberately absent from this immutable lifetime.
        game = realm.registry.resolve(self.writer)
        spawn, = [spawn for spawn, _ in realm._npc_spawns if spawn.uid == self.hp_result.target.uid]
        lifetime = (realm, realm.registry, game, game.selection, realm.service(self.writer),
                    realm._npc_frames[id(self.writer)], realm._npc_spawns, spawn,
                    self.row['operation_lock'], self.row['policy_row'])
        need(len(lifetime) == len(self.lifetime) and all(a is b for a, b in zip(lifetime, self.lifetime)),
             'SCENARIO_NPC_SELECTED_LIFETIME_CHANGED')

    def current(self, broker):
        self._same_lifetime(broker)
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True,
             'RETAINED_BASELINE_OWNER_LOST')
        self._same_lifetime(broker)  # Final callback cannot substitute selection/record.
        need(self.clock_ns() - self.started_ns < WAIT_NS, 'SCENARIO_NPC_ORIGINAL_DEADLINE')

    async def step(self, broker, monitor):
        now = self.clock_ns()
        need(now - self.started_ns < WAIT_NS, 'SCENARIO_NPC_ORIGINAL_DEADLINE')
        self.current(broker)
        uid = self.hp_result.target.uid
        if self.phase == 'DEATH_SAMPLE':
            need(not self.death_sample_claimed, 'SCENARIO_NPC_DEATH_SAMPLE_NO_REPLAY')
            self.death_sample_claimed = True
            observer = self.runtime.manual.consumer._attack_action_observer
            need(type(observer) is attack_action_observe.AttackActionObserver
                 and type(observer).prepare is attack_action_observe.PREPARE_METHOD
                 and type(observer).collect is attack_action_observe.COLLECT_METHOD
                 and observer.reader is self.scenario.reader and observer.targets.broker is broker,
                 'SCENARIO_NPC_CANONICAL_ACTION_OBSERVER_REQUIRED')
            async with self.row['operation_lock']:
                self.current(broker)
                await observer.prepare(self.writer, uid, now_ns=now)
                self.current(broker)
                memory, _ = self.scenario.reader.sample(include_input_state=False, attack_action_observer=observer)
                self.current(broker)
            raw = memory.get('attack_action', {})
            def death(slot):
                action = (raw.get('target') or {}).get(slot, {})
                return (action.get('present') is True and action.get('kind') == 'DeathAction'
                        if action.get('status') == 'OBSERVED' else None)
            self.result['death_action'] = dict(status=raw.get('status', 'UNKNOWN'),
                reason=raw.get('reason'), source='CANONICAL_RETAINED_SAMPLE', death_current=death('current'),
                death_queued=death('queue_head'), observation_scope='READONLY_ACTION_SNAPSHOTS')
            need(raw.get('status') == 'OBSERVED' and raw.get('source_contract_valid') is True
                 and raw.get('stable_double_read') is True and raw.get('target_uid') == uid
                 and raw.get('map_id') == self.hp_result.target.map_id,
                 'SCENARIO_NPC_DEATH_SNAPSHOT_UNKNOWN')
            self.phase = 'REMOVE'
            return
        if self.phase == 'REMOVE':
            need(not self.remove_claimed, 'SCENARIO_NPC_REMOVE_NO_REPLAY')
            self.remove_claimed = True  # Claim before await; no second call on any outcome.
            self.result['remove_transport'] = dict(phase='CLAIMED_NO_RETRY', delivery='UNKNOWN')
            # Public backend API acquires the same lock itself; never reenter.
            need(not self.row['operation_lock'].locked(), 'SCENARIO_NPC_REMOVE_OUTSIDE_ROW_LOCK_REQUIRED')
            await broker.remove_dead_npc(self.writer, uid, self.ordinal, policy=npc_death.REMOVE_POLICY)
            self.current(broker)
            self.result['remove_transport'] = self.transport(npc_death.REMOVE_OPCODE)
            self.phase = 'REGISTRY_SAMPLE'
            return
        if self.phase == 'REGISTRY_SAMPLE':
            need(not self.registry_sample_claimed, 'SCENARIO_NPC_REGISTRY_SAMPLE_NO_REPLAY')
            self.registry_sample_claimed = True
            observer = self.runtime.manual.consumer._attack_observer
            need(type(observer) is npc_observe.NpcObserver and observer.targets.reader is self.scenario.reader
                 and observer.targets.broker is broker and type(observer).sample_registry is REGISTRY_SAMPLE
                 and observer.sample_registry.__self__ is observer
                 and observer.sample_registry.__func__ is REGISTRY_SAMPLE,
                 'SCENARIO_NPC_CANONICAL_REGISTRY_OBSERVER_REQUIRED')
            async with self.row['operation_lock']:
                self.current(broker)
                result = await observer.sample_registry(self.writer, uid, now_ns=now)
                self.current(broker)
            self.result['registry'] = result
            need(type(result) is dict and result.get('status') == 'OBSERVED'
                 and result.get('uid') == uid and result.get('map_id') == self.hp_result.target.map_id
                 and result.get('lookup_scope') == 'THREE_LOOKUP_VECTORS'
                 and result.get('observation_scope') == 'READONLY_SNAPSHOT'
                 and result.get('snapshot_atomic') is False and result.get('source_contract_valid') is True
                 and result.get('stable_double_read') is True
                 and type(result.get('uid_absent')) is bool
                 and type(result.get('vector_counts')) is list and len(result['vector_counts']) == 3
                 and all(type(n) is int and n >= 0 for n in result['vector_counts'])
                 and type(result.get('typed_bytes_requested')) is int
                 and 0 <= result['typed_bytes_requested'] <= 16384
                 and result.get('typed_byte_limit') == 16384 and result.get('max_samples_per_second') == 2,
                 'SCENARIO_NPC_REGISTRY_SNAPSHOT_UNKNOWN')
            action = self.result['death_action']
            complete = (action.get('status') == 'OBSERVED'
                        and (action.get('death_current') is True or action.get('death_queued') is True)
                        and result.get('uid_absent') is True)
            self.result['status'] = 'COMMITTED' if complete else 'PARTIAL'
            self.phase = 'DONE'
            self.scenario.stage = 'NPC_COMPLETE_STOP_REQUESTED'
            self.scenario.stop.set()  # Existing owner Quit/monitor/cleanup only.
            return
        need(False, 'SCENARIO_NPC_UNKNOWN_PHASE')

    def fail(self, error):
        from tools.local_original_session import launcher
        code = launcher.safe_error_code(error) or type(error).__name__
        self.result.update(status='UNKNOWN', reason=code)
        self.phase = 'FAILED'
        self.scenario.error = self.scenario.error or code
        self.scenario.stage = 'NPC_UNKNOWN_STOP_REQUESTED'
        self.scenario.stop.set()


class Runtime:
    """Serialize trial continuation with existing feature poll and 2-Hz slot."""
    def __init__(self, runtime, scenario):
        self.original, self.scenario = runtime, scenario
        self.manual = runtime.manual
        self.trial = Trial(scenario, runtime)
        scenario.npc_trial = self.trial

    async def poll(self, monitor=None):
        trial = self.trial
        if self.scenario.stop.is_set():
            return {}
        if trial.phase not in ('WAIT_ATTACK', 'DONE', 'FAILED'):
            try:
                need(monitor is self.scenario.monitor, 'SCENARIO_NPC_SAME_MONITOR_REQUIRED')
                now = trial.clock_ns()
                need(now - trial.started_ns < WAIT_NS, 'SCENARIO_NPC_ORIGINAL_DEADLINE')
                if now / 1e9 >= monitor.next_memory:
                    try:
                        await trial.step(self.manual.inventory_broker, monitor)
                    finally:
                        # Same serialized slot, never raise any original read cap.
                        monitor.next_memory = max(monitor.next_memory, trial.clock_ns() / 1e9 + .5)
            except Exception as error:
                trial.fail(error)
            self.scenario.save()
            if self.scenario.stop.is_set():
                return {}  # Cleanup belongs to the unchanged run_session owner.
        return await self.original.poll(monitor)

    def close(self):
        self.original.close()
