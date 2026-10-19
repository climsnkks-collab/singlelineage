"""Explicit respawn trial over public product APIs and fresh NPC observations.

The initial attack/death/remove is preparation, not a repeated feature verdict.
No old Trial stop is cleared/masked; no old packet or target lease is adopted.
"""
import asyncio
import time

from tools.local_original_session import (attack, attack_session, feature_config, launcher,
    movement, npc, npc_death, npc_hp, npc_motion, npc_observe, npc_respawn, npc_session,
    attack_action_observe, manual_move_commands, observe, broker as broker_module, npc_motion_focused)

need = attack.need
WAIT_NS = 15_000_000_000
RESPAWN_METHOD = getattr(launcher.ProductFeatures, 'respawn_npc', None)
REGISTRY_SAMPLE = npc_observe.NpcObserver.sample_registry
MOTION_SAMPLE = npc_observe.NpcObserver.sample_motion
MANUAL_TYPE = launcher.ManualMoveRequests
VALIDATE_PREPARATION = getattr(MANUAL_TYPE, 'validate_lethal_preparation', None)
PRODUCER_TYPE = manual_move_commands.ManualMoveCommands
PRODUCER_VALIDATE = getattr(PRODUCER_TYPE, 'validate_lethal_preparation', None)
LETHAL_PROOF_TYPE = getattr(manual_move_commands, '_LethalPreparation', None)
LETHAL_SCOPE = 'CURRENT_LETHAL_NPC_DEATH_DRAIN_ONLY'
LETHAL_PHASE = 'LETHAL_PREPARATION_READY'
RETAINED_SAMPLE = observe.RetainedSceneReader.sample
ARM_RESPAWN_HIT = getattr(launcher.ProductFeatures, 'arm_respawn_attack', None)
VALIDATE_RESPAWN_HIT = getattr(MANUAL_TYPE, 'validate_respawn_attack', None)
REMOVE_NPC_METHOD = broker_module.PersistentBroker.remove_dead_npc
NPC_POLL_METHOD = launcher.ProductFeatures._poll_npc


def configuration(features, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import inventory as inv, inventory_store
    from tools.local_native_login_spawn_render_retry_runtime import spawn_hook
    need(type(features) is feature_config.Features and len(features.spawns) == 1
         and features.attack_policy == feature_config.ATTACK_INTENT_POLICY
         and type(features.attack_feedback) is attack_session.FeedbackConfig
         and type(features.attack_hp_provider) is npc_hp.ExplicitInputs
         and features.npc_death_policy == npc_death.DEATH_POLICY
         and features.npc_remove_policy == npc_death.REMOVE_POLICY
         and features.npc_respawn_policy == npc_respawn.POLICY
         and type(features.interval_ns) is int and 0 < features.interval_ns < (1 << 63)
         and features.motion_policy == npc_motion.LOCAL_PRE_STEP
         and features.goal_policy == npc_session.AXIS_SIGN_GOAL and features.goal is None
         and features.item_use_policy is features.item_equipment_policy is features.inventory_update_policy is None,
         'SCENARIO_NPC_RESPAWN_EXPLICIT_CONFIG_REQUIRED')
    recipe, = features.spawns
    fresh = features.npc_respawn_spawn
    need(type(fresh) is npc.NpcSpawn and fresh is not recipe
         and (fresh.map_id, fresh.policy, dict(fresh.fields)) == (recipe.map_id, recipe.policy, dict(recipe.fields)),
         'SCENARIO_NPC_RESPAWN_EXACT_FRESH_RECIPE_REQUIRED')
    row, = features.attack_hp_provider.rows
    need(row.target == npc_hp.Target(recipe.uid, recipe.map_id, recipe.fields[3], recipe.fields[39])
         and row.hit.landed is True and row.hit.damage >= row.hp.current,
         'SCENARIO_NPC_RESPAWN_EXPLICIT_LETHAL_PREPARATION_REQUIRED')
    need(inventory is True and auto_inventory is True and features.inventory_policy == inv.POLICY
         and type(features.inventory_frame) is bytes
         and features.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
         and features.inventory_store_policy == inventory_store.POLICY,
         'SCENARIO_NPC_RESPAWN_SOURCE_QUIT_PREPARATION_REQUIRED')
    inv.validate_frame(features.inventory_frame)
    npc.prepare(features.spawns, self_uid=spawn_hook.profiles()[0].fields[1])
    return features


def publish_preparation_attack(scenario, row, broker):
    """Normal AttackTarget command, with an explicit unmoved NPC controller.

    The old stationary-only scenario forbids any mover. This new product has
    a goal-free controller ready to be replaced; it emits no NPC motion here.
    """
    from tools.local_original_session import commands
    service, position, _proof, known = scenario.current(row, broker)
    if not known:
        return
    spawn, = scenario.features.spawns
    actual = broker.realm._npc_spawns
    need(scenario.inventory['status'] == 'COMMITTED', 'SCENARIO_INVENTORY_FIRST_REQUIRED')
    trial = scenario.respawn_trial
    controller = trial.runtime.npc_session
    mover = broker.realm.npc_mover(scenario.move_bound[0])
    need(len(actual) == 1 and actual[0][0] is spawn and spawn.uid != position.uid
         and spawn.map_id == position.map_id and controller._goal is None
         and mover.state.packed == spawn.fields[1] and mover.state.last_step_ns is None
         and mover.pending is None and mover.spawn_drained is True,
         'SCENARIO_NPC_RESPAWN_UNMOVED_PREPARATION_TARGET_REQUIRED')
    session = broker._attack_session
    need(type(session) is attack_session.AttackSession and broker.realm._attack_session is session
         and session.policy == scenario.features.attack_policy and not session.closed and not session.fatal
         and session.feedback is scenario.features.attack_feedback and session.accepted_count == 0
         and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0),
         'SCENARIO_CURRENT_FRESH_ATTACK_SESSION_REQUIRED')
    scenario.attack_session, scenario.attack_before = session, session.accepted_count
    scenario.attack_projection = attack.AttackTargets._project(session.targets, scenario.move_bound[0],
                                                              attack.AttackRequest(spawn.uid))
    scenario.attack_events = broker.policy.events
    scenario.capture_attack_transport()
    need(scenario.attack['feedback']['state'] == 'NOT_REQUESTED'
         and all(scenario.attack['feedback'][key] == 0 for key in ('prepared', 'reserved', 'write_attempted', 'drained')),
         'SCENARIO_FRESH_ATTACK_FEEDBACK_REQUIRED')
    need(position.metadata() == scenario.origin, 'SCENARIO_ATTACK_AUTHORITY_CHANGED')
    request = dict(schema=commands.REQUEST_SCHEMA, sequence=scenario.ATTACK_SEQUENCE, command='AttackTarget',
                   uid=position.uid, target_uid=spawn.uid, map_id=position.map_id)
    scenario.attack.update(status='CLAIMED_NO_RETRY', sequence=scenario.ATTACK_SEQUENCE, uid=position.uid,
        target_uid=spawn.uid, map_id=position.map_id, trial_role='RESPAWN_PREPARATION_ONLY')
    scenario.stage, scenario.attack_started = 'ATTACK_WAIT', scenario.clock()
    scenario.save()
    commands._atomic(scenario.monitor.directory / 'command.request.json', request, 1024)
    scenario.attack['status'] = 'PUBLISHED'


def grid(value):
    return (tuple(value) if type(value) in (tuple, list) and len(value) == 2
            and all(type(n) is int and 0 <= n <= 65535 for n in value) else None)


class Trial:
    def __init__(self, scenario, runtime, *, clock_ns=time.monotonic_ns, completion=None):
        need(type(runtime) is launcher.ProductFeatures and callable(RESPAWN_METHOD)
             and type(runtime).respawn_npc is RESPAWN_METHOD,
             'SCENARIO_NPC_RESPAWN_ACTUAL_PRODUCT_API_REQUIRED')
        need(completion is None or callable(completion), 'SCENARIO_NPC_RESPAWN_COMPLETION_REQUIRED')
        self.completion = completion
        self.scenario, self.runtime, self.clock_ns = scenario, runtime, clock_ns
        self.phase = 'WAIT_ATTACK_PREPARATION'
        self.writer = self.row = self.broker = self.service = self.hp_result = None
        self.base_refs = self.base_scalars = self.old_refs = self.new_refs = None
        self.old_session = self.old_mover = self.old_generation = self.old_frames = None
        self.receipt = self.observer = None
        self.prepare_started_ns = self.respawn_started_ns = None
        self.ordinal = None
        self.remove_claimed = self.respawn_claimed = self.death_sample_claimed = False
        self._death_read_pending = False
        self.preparation_proof = self.consumer = None
        self.result = dict(status='NOT_REQUESTED', preparation=None, respawn=None, registry=None, pose=None,
            scope='CLIENT_REGISTRY_POSE_FRESH_TARGET_LIFE_ONLY', new_target_life='UNKNOWN',
            hp='LAZY_INITIAL_ON_NEXT_REAL_ATTACK_NOT_OBSERVED', screen='UNKNOWN', free='UNKNOWN',
            official_stats='UNKNOWN', automatic_retry=False)

    def _base(self):
        broker, reader = self.broker, self.scenario.reader
        realm, writer = broker.realm, self.writer
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows) == 1 and rows[0] is self.row and not self.row['failed'] and not self.row['joined']
             and not broker._closing and not broker.failure.is_set(), 'SCENARIO_NPC_RESPAWN_CURRENT_CLAIM_REQUIRED')
        game, movement_service = realm.registry.resolve(writer), realm.service(writer)
        return (broker, broker.policy, realm, realm.registry, game, game.selection, movement_service,
                movement_service.snapshot(), self.row['operation_lock'], self.row['policy_row'],
                reader, reader.owner, reader.member, reader.backend, reader.sampler,
                getattr(reader.member, 'identity', None), broker._npc_respawn, realm._npc_respawn,
                realm._npc_spawns, self.runtime, self.runtime.manual, self.scenario.features,
                self.service.reader, self.service.observer, self.runtime._npc_respawn_spawn,
                self.preparation_proof, self.runtime.manual.consumer)

    def _scalars(self):
        reader, service = self.scenario.reader, self.broker.realm.service(self.writer)
        owner, member = reader.owner, reader.member
        return (owner.owner_handle, owner.owner_job, member.process, member.job,
            getattr(member, 'pid', None), getattr(member, 'identity', {}).get('birth'), reader.backend.handle,
            reader.sample_byte_limit, getattr(reader, 'closed', False), owner.closed,
            service.requests_received, service.committed, service.corrections_prepared)

    def _same_base(self):
        actual = self._base()
        need(all(a is b for a, b in zip(actual, self.base_refs)), 'SCENARIO_NPC_RESPAWN_SELECTION_CHANGED')
        need(all(type(a) is type(b) and a == b for a, b in zip(self._scalars(), self.base_scalars)),
             'SCENARIO_NPC_RESPAWN_RETAINED_SCALARS_CHANGED')
        need(not self.runtime._closed and self.broker._npc_respawn is self.service is self.broker.realm._npc_respawn,
             'SCENARIO_NPC_RESPAWN_SERVICE_CHANGED')

    def _old(self):
        realm, session = self.broker.realm, self.runtime.npc_session
        return (session, session.factory, session.factory.config, session.factory.adapter,
                realm.npc_mover(self.writer), realm.npc_mover(self.writer).state,
                realm._npc_frames[id(self.writer)], self.broker._attack_session,
                self.broker._attack_session.last_hp_result, session.factory.reader,
                self.service.current_generation(self.writer), realm.npc_edge_passability,
                self.broker._attack_session._hp._entries.get((id(self.writer), self.hp_result.target.uid)),
                self.broker._attack_session._notifications._records.get((id(self.writer), self.hp_result.target.uid)))

    def _new(self):
        receipt, runtime = self.receipt, self.runtime
        need(type(receipt) is npc_respawn.Receipt, 'SCENARIO_NPC_RESPAWN_ACTUAL_RECEIPT_REQUIRED')
        self.service.require_current(receipt)
        need(receipt.old_generation is self.old_generation and receipt.generation is not self.old_generation
             and receipt.generation.ordinal == self.old_generation.ordinal + 1
             and self.broker.realm._npc_frames[id(self.writer)] is not self.old_frames
             and self.broker.realm._npc_frames[id(self.writer)][3][0] is not self.old_frames[3][0],
             'SCENARIO_NPC_RESPAWN_FRESH_GENERATION_FRAMES_REQUIRED')
        session = runtime.npc_session
        need(type(session) is npc_session.NpcSession and session is not self.old_session
             and session.factory is not self.old_session.factory
             and session.factory._session is session and session.factory.reader is self.scenario.reader
             and session.factory.adapter is receipt.adapter
             and session._generation is receipt.generation and session._owned_mover is receipt.mover
             and not session._closed and not session.factory._closed and session._goal is None
             and self.old_session._closed and self.old_session.factory._closed and self.old_mover.closed,
             'SCENARIO_NPC_RESPAWN_FRESH_PRODUCT_BINDING_REQUIRED')
        binding = session.current_binding()
        need(binding is not None and binding.owner is self.writer and binding.broker is self.broker,
             'SCENARIO_NPC_RESPAWN_NEW_CURRENT_BINDING_REQUIRED')
        need(receipt.writer is self.writer and receipt.row is self.row
             and receipt.spawn is self.scenario.features.npc_respawn_spawn
             and receipt.recipe is self.scenario.features.spawns[0]
             and receipt.mover is self.broker.realm.npc_mover(self.writer)
             and receipt.mover is not self.old_mover and receipt.mover.spawn_drained is True
             and receipt.mover.pending is None and not receipt.mover.closed and not receipt.mover.fatal,
             'SCENARIO_NPC_RESPAWN_NEW_OWNED_GENERATION_REQUIRED')
        return (receipt.generation, receipt.spawn, receipt.recipe, receipt.mover, receipt.mover.state,
                receipt.adapter, session, session.factory, session.factory.config,
                self.broker.realm._npc_frames[id(self.writer)])

    def current(self, *, fresh=False):
        def structural():
            need(not self.scenario.stop.is_set(), 'SCENARIO_NPC_RESPAWN_CANCELLED')
            self._same_base()
            if fresh:
                actual = self._new()
                need(self.new_refs is None or all(a is b for a, b in zip(actual, self.new_refs)),
                     'SCENARIO_NPC_RESPAWN_NEW_GENERATION_CHANGED')
            else:
                need(all(a is b for a, b in zip(self._old(), self.old_refs)),
                     'SCENARIO_NPC_RESPAWN_PREPARATION_CHANGED')
        structural()
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        structural()
        started = self.respawn_started_ns if self.respawn_started_ns is not None else self.prepare_started_ns
        need(self.clock_ns() - started < WAIT_NS, 'SCENARIO_NPC_RESPAWN_ORIGINAL_OPERATION_DEADLINE')

    def queue_preparation(self, broker):
        """No authority from JSON: validation belongs in the next existing slot."""
        scenario = self.scenario
        need(self.phase == 'WAIT_ATTACK_PREPARATION' and scenario.attack['status'] == 'PREPARED'
             and scenario.attack['phase'] == LETHAL_PHASE and scenario.attack['proof_scope'] == LETHAL_SCOPE
             and not scenario.moves, 'SCENARIO_NPC_RESPAWN_ONCE_PREPARATION_REQUIRED')
        self.broker, self.writer = broker, scenario.move_bound[0]
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is self.writer]
        need(len(rows) == 1, 'SCENARIO_NPC_RESPAWN_CURRENT_CLAIM_REQUIRED')
        self.row, = rows
        self.consumer = self.runtime.manual.consumer
        proof = getattr(self.consumer, '_lethal_preparation_completed', None)
        need(LETHAL_PROOF_TYPE is not None and type(proof) is LETHAL_PROOF_TYPE
             and type(proof.accepted_ordinal) is int and proof.accepted_ordinal > 0
             and type(proof.originalstarted_ns) is int and 0 <= proof.originalstarted_ns <= self.clock_ns(),
             'SCENARIO_NPC_RESPAWN_REAL_LETHAL_PROOF_REQUIRED')
        self.preparation_proof, self.ordinal = proof, proof.accepted_ordinal
        self.prepare_started_ns = proof.originalstarted_ns  # Original claim, never a new polling deadline.
        self.result.update(status='PENDING', preparation=dict(status='PENDING_CURRENT_PROOF',
            role='REQUIRED_RESPAWN_PREPARATION_ONLY', proof_scope=LETHAL_SCOPE))
        self.phase = 'CHECK_PREPARATION'

    def _validate_preparation(self):
        manual, consumer, proof = self.runtime.manual, self.consumer, self.preparation_proof
        need(self.row['operation_lock'].locked() and type(manual) is MANUAL_TYPE
             and launcher.ManualMoveRequests is MANUAL_TYPE and MANUAL_TYPE.validate_lethal_preparation is VALIDATE_PREPARATION
             and manual.validate_lethal_preparation.__self__ is manual
             and manual.validate_lethal_preparation.__func__ is VALIDATE_PREPARATION
             and type(consumer) is PRODUCER_TYPE and manual.consumer is consumer
             and manual_move_commands.ManualMoveCommands is PRODUCER_TYPE
             and PRODUCER_TYPE.validate_lethal_preparation is PRODUCER_VALIDATE
             and consumer.validate_lethal_preparation.__self__ is consumer
             and consumer.validate_lethal_preparation.__func__ is PRODUCER_VALIDATE
             and type(proof) is LETHAL_PROOF_TYPE and consumer._lethal_preparation_completed is proof,
             'SCENARIO_NPC_RESPAWN_CANONICAL_LETHAL_PRODUCER_REQUIRED')
        need(not self.scenario.stop.is_set(), 'SCENARIO_NPC_RESPAWN_CANCELLED')
        need(self.clock_ns() - self.prepare_started_ns < WAIT_NS,
             'SCENARIO_NPC_RESPAWN_ORIGINAL_OPERATION_DEADLINE')
        actual = manual.validate_lethal_preparation(self.writer, accepted_ordinal=self.ordinal)
        need(actual is proof and proof.writer is self.writer and proof.row is self.row
             and proof.session is self.broker._attack_session
             and all(type(value) is int for value in (proof.sequence, consumer._action_sequence, consumer.sequence,
                 manual.sequence, manual.last_result.get('sequence'), manual.last_result.get('last_sequence')))
             and proof.sequence == consumer._action_sequence == consumer.sequence
             and manual.sequence == manual.last_result['sequence'] == manual.last_result['last_sequence']
                 == self.scenario.ATTACK_SEQUENCE
             and manual.last_result.get('status') == 'PREPARED'
             and manual.last_result.get('command') == 'AttackTarget'
             and manual.last_result.get('phase') == LETHAL_PHASE
             and manual.last_result.get('proof_scope') == LETHAL_SCOPE
             and proof.target_uid == self.scenario.features.spawns[0].uid
             and proof.hp_result is self.broker._attack_session.last_hp_result
             and proof.accepted_ordinal == self.ordinal and proof.originalstarted_ns == self.prepare_started_ns,
             'SCENARIO_NPC_RESPAWN_CURRENT_LETHAL_PROOF_REQUIRED')
        need(not self.scenario.stop.is_set(), 'SCENARIO_NPC_RESPAWN_CANCELLED')
        return proof

    def _begin_preparation_locked(self):
        proof = self._validate_preparation()
        self.service = self.broker._npc_respawn
        self.hp_result = proof.hp_result
        need(type(self.hp_result) is npc_hp.Result and self.hp_result.died and self.hp_result.after.current == 0
             and self.hp_result.hit.landed is True and self.hp_result.accepted_ordinal == self.ordinal
             and proof.hp_entry is self.broker._attack_session._hp._entries.get((id(self.writer),proof.target_uid))
             and proof.notification_record is self.broker._attack_session._notifications._records.get((id(self.writer),proof.target_uid)),
             'SCENARIO_NPC_RESPAWN_CURRENT_LETHAL_PREPARATION_REQUIRED')
        death = self.broker._attack_session.metadata().get('npc_notifications', {}).get('last', {}).get(hex(npc_death.DEATH_OPCODE))
        need(type(death) is dict and death.get('target_uid') == self.hp_result.target.uid
             and death.get('accepted_ordinal') == self.ordinal and death.get('phase') == 'DRAINED'
             and death.get('write_attempted') is True and death.get('drained') is True
             and death.get('delivery') == 'TRANSPORT_DRAIN_ONLY',
             'SCENARIO_NPC_RESPAWN_DEATH_PREPARATION_DRAIN_REQUIRED')
        self.base_refs, self.base_scalars = self._base(), self._scalars()
        self.old_refs = self._old()
        self.old_frames, self.old_generation = self.old_refs[6], self.old_refs[10]
        self.old_session, self.old_mover = self.runtime.npc_session, self.broker.realm.npc_mover(self.writer)
        need(self.old_session._goal is None, 'SCENARIO_NPC_RESPAWN_NO_OLD_GOAL_REQUIRED')
        self.result['preparation'].update(status='CURRENT_PROOF_VALIDATED', target_uid=proof.target_uid,
            accepted_ordinal=self.ordinal, server_hp=self.hp_result.metadata(), death_transport=death,
            death_action=None, remove_transport=None)
        self.phase = 'DEATH_SAMPLE'
        self.current()
        self._validate_preparation()

    async def _death_sample(self):
        need(self.phase == 'DEATH_SAMPLE' and not self.remove_claimed and not self.respawn_claimed
             and (not self.death_sample_claimed or self._death_read_pending),
             'SCENARIO_NPC_RESPAWN_DEATH_SAMPLE_NO_REPLAY')
        self._death_read_pending = False
        self.death_sample_claimed = True
        observer = self.consumer._attack_action_observer
        need(type(observer) is attack_action_observe.AttackActionObserver
             and type(observer).prepare is attack_action_observe.PREPARE_METHOD
             and type(observer).collect is attack_action_observe.COLLECT_METHOD
             and observer.prepare.__self__ is observer and observer.prepare.__func__ is attack_action_observe.PREPARE_METHOD
             and observer.collect.__self__ is observer and observer.collect.__func__ is attack_action_observe.COLLECT_METHOD
             and observer.reader is self.scenario.reader and observer.targets.broker is self.broker,
             'SCENARIO_NPC_RESPAWN_CANONICAL_DEATH_OBSERVER_REQUIRED')
        self.current()
        self._validate_preparation()
        await observer.prepare(self.writer, self.hp_result.target.uid, now_ns=self.clock_ns())
        self.current()
        self._validate_preparation()
        reader = self.scenario.reader
        need(type(reader) is observe.RetainedSceneReader and type(reader).sample is RETAINED_SAMPLE
             and reader.sample.__self__ is reader and reader.sample.__func__ is RETAINED_SAMPLE,
             'SCENARIO_NPC_RESPAWN_CANONICAL_RETAINED_SAMPLE_REQUIRED')
        memory, _ = reader.sample(include_input_state=False, attack_action_observer=observer)
        self.current()
        self._validate_preparation()
        raw = memory.get('attack_action', {})
        def death(slot):
            action = (raw.get('target') or {}).get(slot,{})
            return (action.get('present') is True and action.get('kind') == 'DeathAction'
                    if action.get('status') == 'OBSERVED' else None)
        detail = dict(status=raw.get('status','UNKNOWN'), reason=raw.get('reason'), source='CANONICAL_RETAINED_SAMPLE',
            death_current=death('current'), death_queued=death('queue_head'),
            observation_scope='READONLY_ACTION_SNAPSHOTS', typed_bytes_requested=raw.get('typed_bytes_requested'),
            combined_typed_bytes_requested=raw.get('combined_typed_bytes_requested'),
            typed_byte_limit=attack_action_observe.BYTE_LIMIT, retained_base_byte_limit=16384, raw=raw)
        self.result['preparation']['death_action'] = detail
        if (raw.get('status') == 'UNKNOWN' and raw.get('reason') == 'ATTACK_OBSERVE_TYPED_READ_CHANGED'
                and raw.get('typed_read_changed_field') == 'ACTION_QUEUE_HEADER'
                and raw.get('typed_read_changed_origin') == 'FINAL_PHYSICAL_READBACK'):
            expected = attack_action_observe.empty('ATTACK_OBSERVE_TYPED_READ_CHANGED')
            typed, combined = (raw.get(key) for key in ('typed_bytes_requested', 'combined_typed_bytes_requested'))
            need(type(typed) is type(combined) is int
                 and 0 <= typed <= combined <= attack_action_observe.BYTE_LIMIT,
                 'SCENARIO_NPC_RESPAWN_DEATH_INCOMPLETE_SHAPE_REQUIRED')
            expected.update(typed_bytes_requested=typed, combined_typed_bytes_requested=combined,
                typed_read_changed_field='ACTION_QUEUE_HEADER', typed_read_changed_origin='FINAL_PHYSICAL_READBACK')
            need(set(raw) == set(expected)
                 and all(type(raw[key]) is type(value) and raw[key] == value for key, value in expected.items()),
                 'SCENARIO_NPC_RESPAWN_DEATH_INCOMPLETE_SHAPE_REQUIRED')
            # This failed query grants no source/owner/action authority. The
            # same lethal proof is revalidated before every fresh <=2Hz query,
            # within its original deadline; no Attack/Death/Remove is replayed.
            self.result['preparation'].setdefault('incomplete_death_action', detail)
            self._death_read_pending = True
            return
        need(raw.get('status') == 'OBSERVED' and raw.get('source_contract_valid') is True
             and raw.get('stable_double_read') is True and raw.get('target_uid') == self.hp_result.target.uid
             and raw.get('actor_uid') == self.broker.realm.service(self.writer).snapshot().uid
             and raw.get('map_id') == self.hp_result.target.map_id
             and raw.get('snapshot_atomic') is False and raw.get('typed_byte_limit') == attack_action_observe.BYTE_LIMIT
             and type(raw.get('typed_bytes_requested')) is int
             and type(raw.get('combined_typed_bytes_requested')) is int
             and 0 <= raw['typed_bytes_requested'] <= raw['combined_typed_bytes_requested'] <= attack_action_observe.BYTE_LIMIT,
             'SCENARIO_NPC_RESPAWN_DEATH_SNAPSHOT_UNKNOWN')
        need(detail['death_current'] is True or detail['death_queued'] is True,
             'SCENARIO_NPC_RESPAWN_POSITIVE_DEATH_ACTION_REQUIRED')
        self.result['preparation']['status'] = 'LETHAL_PREPARATION_READY'
        self.phase = 'REMOVE_READY'

    def _capture_fresh_absence(self, previous_ticket):
        """Copy only this invocation's output; preserve any original failure."""
        try:
            ticket = self.service._tickets.get(id(self.writer))
            if (type(ticket) is npc_respawn.Ticket and ticket is not previous_ticket
                    and ticket.writer is self.writer and ticket.old_generation is self.old_generation
                    and ticket.old_generation.row is self.row
                    and type(ticket.accepted_ordinal) is int and ticket.accepted_ordinal == self.ordinal):
                detail = npc_respawn._fresh_absence_diagnostic(ticket.fresh_absence,
                    target_uid=self.hp_result.target.uid, map_id=self.hp_result.target.map_id)
                if detail is not None and type(self.result.get('respawn')) is dict:
                    self.result['respawn']['fresh_absence'] = detail
        except BaseException:
            pass  # Optional diagnostic must never replace cancellation/cleanup/original reason.

    async def step(self):
        if self.phase == 'CHECK_PREPARATION':
            async with self.row['operation_lock']:
                self._begin_preparation_locked()
                await self._death_sample()
            return
        if self.phase == 'DEATH_SAMPLE':
            async with self.row['operation_lock']:
                await self._death_sample()
            return
        fresh = self.phase in ('NEW_REGISTRY', 'NEW_POSE')
        self.current(fresh=fresh)
        uid, broker = self.hp_result.target.uid, self.broker
        if self.phase == 'REMOVE_READY':
            need(not self.remove_claimed, 'SCENARIO_NPC_RESPAWN_REMOVE_NO_REPLAY')
            self.remove_claimed = True
            self.result['preparation']['remove_transport'] = dict(status='CLAIMED_NO_RETRY')
            async with self.row['operation_lock']:
                self.current()
                self._validate_preparation()
                self.current()
            need(not self.row['operation_lock'].locked(), 'SCENARIO_NPC_RESPAWN_PUBLIC_REMOVE_OUTSIDE_LOCK')
            result = await broker.remove_dead_npc(self.writer, uid, self.ordinal, policy=npc_death.REMOVE_POLICY)
            self.current()
            self.result['preparation']['remove_transport'] = result
            need(type(result) is dict and result.get('status') == 'DRAINED'
                 and result.get('target_uid') == uid and result.get('accepted_ordinal') == self.ordinal,
                 'SCENARIO_NPC_RESPAWN_REMOVE_PREPARATION_DRAIN_REQUIRED')
            self.phase = 'RESPAWN_READY'
            return
        if self.phase == 'RESPAWN_READY':
            need(not self.respawn_claimed, 'SCENARIO_NPC_RESPAWN_TRIGGER_NO_REPLAY')
            self.respawn_claimed = True
            self.respawn_started_ns = self.clock_ns()  # New explicit operation, never reset on polling/retry.
            self.result['respawn'] = dict(status='CLAIMED_NO_RETRY')
            need(type(self.runtime) is launcher.ProductFeatures and type(self.runtime).respawn_npc is RESPAWN_METHOD
                 and self.runtime.respawn_npc.__self__ is self.runtime
                 and self.runtime.respawn_npc.__func__ is RESPAWN_METHOD,
                 'SCENARIO_NPC_RESPAWN_ACTUAL_PRODUCT_API_REQUIRED')
            previous_ticket = self.service._tickets.get(id(self.writer))
            try:
                self.receipt = await self.runtime.respawn_npc(writer=self.writer, target_uid=uid,
                    accepted_ordinal=self.ordinal, spawn=self.scenario.features.npc_respawn_spawn,
                    now_ns=self.respawn_started_ns, policy=self.scenario.features.npc_respawn_policy,
                    monitor=self.scenario.monitor)
            finally:
                self._capture_fresh_absence(previous_ticket)
            self.current(fresh=True)
            self.new_refs = self._new()
            metadata = self.receipt.metadata()
            self.result['respawn'] = metadata
            need(type(metadata) is dict and set(metadata) == {'status', 'generation', 'target_uid', 'map_id',
                    'grid', 'transport', 'client_registry', 'scope'}
                 and metadata['status'] == 'COMMITTED' and metadata['transport'] == 'DRAINED'
                 and type(metadata['generation']) is int and metadata['generation'] > 0
                 and metadata['target_uid'] == uid and metadata['map_id'] == self.hp_result.target.map_id
                 and grid(metadata['grid']) == movement.authority.unpack_grid(self.receipt.spawn.fields[1])
                 and metadata['client_registry'] == 'UNKNOWN' and metadata['scope'] == 'NEW_LOCAL_NPC_LIFE_ONLY',
                 'SCENARIO_NPC_RESPAWN_RECEIPT_METADATA_REQUIRED')
            self.observer = npc_observe.NpcObserver(broker, self.scenario.reader)
            self.phase = 'NEW_REGISTRY'
            return
        observer = self.observer
        need(type(observer) is npc_observe.NpcObserver and observer.targets.broker is broker
             and observer.targets.reader is self.scenario.reader,
             'SCENARIO_NPC_RESPAWN_FRESH_CANONICAL_OBSERVER_REQUIRED')
        method = REGISTRY_SAMPLE if self.phase == 'NEW_REGISTRY' else MOTION_SAMPLE
        bound = observer.sample_registry if self.phase == 'NEW_REGISTRY' else observer.sample_motion
        need(bound.__self__ is observer and bound.__func__ is method
             and (type(observer).sample_registry if self.phase == 'NEW_REGISTRY' else type(observer).sample_motion) is method,
             'SCENARIO_NPC_RESPAWN_CANONICAL_OBSERVATION_METHOD_REQUIRED')
        async with self.row['operation_lock']:
            self.current(fresh=True)
            result = await bound(self.writer, uid, now_ns=self.clock_ns())
            self.current(fresh=True)
        key = 'registry' if self.phase == 'NEW_REGISTRY' else 'pose'
        self.result[key] = result
        need(type(result) is dict and result.get('status') == 'OBSERVED'
             and result.get('uid') == uid and result.get('map_id') == self.hp_result.target.map_id
             and result.get('source_contract_valid') is True and result.get('snapshot_atomic') is False
             and type(result.get('typed_bytes_requested')) is int and 0 <= result['typed_bytes_requested'] <= 16384
             and result.get('typed_byte_limit') == 16384 and result.get('max_samples_per_second') == 2,
             'SCENARIO_NPC_RESPAWN_NEW_OBSERVATION_UNKNOWN')
        if key == 'registry':
            need(result.get('stable_double_read') is True and result.get('uid_absent') is False
                 and result.get('lookup_scope') == 'THREE_LOOKUP_VECTORS'
                 and result.get('observation_scope') == 'READONLY_SNAPSHOT'
                 and type(result.get('vector_counts')) is list and len(result['vector_counts']) == 3
                 and all(type(n) is int and n >= 0 for n in result['vector_counts']),
                 'SCENARIO_NPC_RESPAWN_NEW_UID_REGISTRATION_REQUIRED')
            self.phase = 'NEW_POSE'
            return
        consistency = result.get('read_consistency')
        need(result.get('client_grid_used_as_authority') is False
             and result.get('source_owner_revalidated') is True
             and (result.get('stable_double_read') is True and consistency == 'STRICT_STABLE'
                  or result.get('stable_double_read') is False and type(consistency) is str
                  and consistency in ('SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE',
                      'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_FINAL_READBACK',
                      'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_BOTH')
                  and type(result.get('motion_scope')) is str
                  and result['motion_scope'] == 'READONLY_DIRECT_NPC_MOTION_STOP'),
             'SCENARIO_NPC_RESPAWN_NEW_POSE_SOURCE_REQUIRED')
        expected = movement.authority.unpack_grid(self.receipt.spawn.fields[1])
        need(grid(result.get('server_grid')) == expected, 'SCENARIO_NPC_RESPAWN_NEW_SERVER_GRID_CHANGED')
        if result.get('coordinates_match') is True and grid(result.get('client_grid')) == expected and result.get('npc_idle') is True:
            self.current(fresh=True)
            self.result.update(status='COMMITTED', new_target_life='FRESH_CANONICAL_TARGET_PATH_OBSERVED')
            self.phase = 'DONE'
            if self.completion is None:
                self.scenario.stage = 'NPC_RESPAWN_COMPLETE_STOP_REQUESTED'
                self.scenario.stop.set()
            else:
                self.completion(self)

    def fail(self, error):
        reason = launcher.safe_error_code(error) or type(error).__name__
        self.result.update(status='UNKNOWN', reason=reason)
        self.phase = 'FAILED'
        self.scenario.error = self.scenario.error or reason
        self.scenario.stage = 'NPC_RESPAWN_UNKNOWN_STOP_REQUESTED'
        self.scenario.stop.set()


class Followup:
    """One normal real Attack on the adopted NPC life; respawn stays DONE."""
    generation_ordinal = 1
    accepted_before = 1
    expected_namespace = (3,2,2,1)
    waiting_phase = 'WAIT_RESPAWN_COMPLETE'
    run_stage = 'NPC_RESPAWN_NEXT_HIT_RUN'
    done_stage = 'NPC_RESPAWN_NEXT_HIT_COMPLETE_STOP_REQUESTED'
    failed_stage = 'NPC_RESPAWN_NEXT_HIT_UNKNOWN_STOP_REQUESTED'

    def prior_hp(self, trial):
        return trial.hp_result

    def validate_new_hit(self, proof, hp, entry):
        pass  # The original mode's existing normal-proof checks follow below.

    def __init__(self, scenario, runtime, *, clock_ns=time.monotonic_ns, completion=None):
        need(completion is None or callable(completion), 'SCENARIO_RESPAWN_HIT_COMPLETION_REQUIRED')
        self.completion = completion
        self.scenario, self.runtime, self.clock_ns = scenario, runtime, clock_ns
        self.phase, self.started_ns = self.waiting_phase, None
        self.trial = self.receipt = self.refs = self.claim = self.proof = self.old_hp = None
        self.result = dict(status='NOT_REQUESTED', scope='ONE_NORMAL_ATTACK_ON_NEW_LOCAL_NPC_LIFE',
            preparation='RESPAWN_REQUIRED_PREPARATION_ONLY', server_hp=None, current_intent='UNKNOWN',
            attack_action_complete='UNKNOWN', automatic_retry=False, screen='UNKNOWN', official_stats='UNKNOWN')

    def _life(self):
        t, r = self.trial, self.runtime
        b, reader, receipt = t.broker, self.scenario.reader, self.receipt
        game = b.realm.registry.resolve(t.writer)
        session, hp = b._attack_session, b._attack_session._hp
        return (b, b.policy, b.realm, b.realm.registry, game, game.selection, b.realm.service(t.writer),
            t.writer, t.row, t.row['operation_lock'], t.row['policy_row'], reader, reader.owner, reader.member,
            reader.backend, reader.sampler, getattr(reader.member, 'identity', None), r, r.manual, r.manual.consumer,
            self.scenario.features, t.service, receipt, receipt.generation, receipt.mover, receipt.spawn, receipt.recipe,
            b.realm._npc_frames[id(t.writer)], r.npc_session, r.npc_session.factory, r.npc_session.factory.config,
            r.npc_session.factory.adapter, r.npc_session.factory.reader, session, session.targets, hp, hp.provider,
            session._notifications, r._npc_respawn_receipt, r.manual.consumer._lethal_preparation_completed,
            r.manual.consumer._attack_purpose)

    def _scalars(self):
        reader, owner = self.scenario.reader, self.scenario.owner
        return (owner.owner_handle, owner.owner_job, owner.closed, reader.member.process, reader.member.job,
            getattr(reader.member, 'pid', None), getattr(reader.member, 'identity', {}).get('birth'),
            reader.backend.handle, reader.sample_byte_limit, getattr(reader, 'closed', False))

    def current(self):
        def structural():
            t, r, receipt = self.trial, self.runtime, self.receipt
            need(not self.scenario.stop.is_set() and not r._closed and t.phase == 'DONE'
                 and t.result['status'] == 'COMMITTED', 'SCENARIO_RESPAWN_HIT_CANCELLED_OR_PREPARATION_CHANGED')
            need(all(a is b for a, b in zip(self._life(), self.refs))
                 and all(type(a) is type(b) and a == b for a,b in zip(self._scalars(),self.scalars)),
                 'SCENARIO_RESPAWN_HIT_LIFETIME_CHANGED')
            need(not t.broker._closing and not t.broker.failure.is_set() and not t.row['failed'] and not t.row['joined']
                 and any(row is t.row for rows in t.broker._claims.values() for row in rows),
                 'SCENARIO_RESPAWN_HIT_CURRENT_CLAIM_REQUIRED')
            t.service.require_current(receipt)
            need(r._npc_respawn_receipt is receipt and r._allow_respawn_attack is True
                 and t.service._phases.get(id(t.writer)) == 'COMMITTED'
                 and r.manual.allow_respawn_attack is True and r.manual.consumer.allow_respawn_attack is True
                 and r.manual.consumer.lethal_attack_preparation is True,
                 'SCENARIO_RESPAWN_HIT_COMMITTED_ADOPTED_RECEIPT_REQUIRED')
            need(type(receipt.generation.ordinal) is int and receipt.generation.ordinal == self.generation_ordinal
                 and r.npc_session._generation is receipt.generation
                 and r.npc_session._owned_mover is receipt.mover and r.npc_session.factory.reader is self.scenario.reader
                 and not r.npc_session._closed and not r.npc_session.factory._closed and r.npc_session._goal is None
                 and not receipt.mover.closed and not receipt.mover.fatal,
                 'SCENARIO_RESPAWN_HIT_CURRENT_GENERATION_REQUIRED')
        structural()
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        structural()
        need(type(self.started_ns) is int and 0 <= self.clock_ns() - self.started_ns < WAIT_NS,
             'SCENARIO_RESPAWN_HIT_ORIGINAL_OPERATION_DEADLINE')

    def begin(self, trial):
        need(self.phase == self.waiting_phase, 'SCENARIO_RESPAWN_HIT_ONCE_HANDOFF_REQUIRED')
        self.phase, self.started_ns = 'ARM_READY', self.clock_ns()
        self.trial, self.receipt = trial, trial.receipt
        self.old_hp = self.prior_hp(trial)
        self.refs, self.scalars = self._life(), self._scalars()
        self.current()
        self.result.update(status='PENDING', generation=self.receipt.generation.ordinal)
        self.scenario.stage = self.run_stage

    def capture_attack_transport(self):
        return self.scenario.capture_attack_transport.__func__(self)

    async def arm(self):
        need(self.phase == 'ARM_READY', 'SCENARIO_RESPAWN_HIT_NO_REARM')
        self.phase = 'ARM_CLAIMED'
        self.current()
        t, session = self.trial, self.trial.broker._attack_session
        self.attack_session, self.features = session, self.scenario.features
        self.attack = dict(attack_observations={}, feedback={})
        async with t.row['operation_lock']:
            self.current()
            self.projection = attack.AttackTargets._project(session.targets, t.writer, attack.AttackRequest(self.receipt.spawn.uid))
            self.counters = tuple(getattr(t.broker.realm.service(t.writer), key)
                for key in ('requests_received', 'committed', 'corrections_prepared'))
            self.events = t.broker.policy.events
            self.before = session.accepted_count
            self.feedback_before = tuple(getattr(session, 'feedback_' + key)
                for key in ('prepared', 'reserved', 'write_attempted', 'drained'))
            need(type(self.before) is int and self.before == self.accepted_before and self.feedback_before == (self.accepted_before,)*4
                 and session.current_intent() is None
                 and (id(t.writer), self.receipt.spawn.uid) not in session._hp._entries,
                 'SCENARIO_RESPAWN_HIT_RETIRED_HP_AND_INTENT_REQUIRED')
            self.current()
        method = ARM_RESPAWN_HIT
        need(callable(method) and type(self.runtime) is launcher.ProductFeatures
             and type(self.runtime).arm_respawn_attack is method
             and self.runtime.arm_respawn_attack.__func__ is method,
             'SCENARIO_RESPAWN_HIT_ACTUAL_ARM_API_REQUIRED')
        claim = await self.runtime.arm_respawn_attack(self.receipt)
        self.current()
        need(type(claim) is dict and set(claim) == {'status','public_sequence','native_sequence','accepted_ordinal','generation'}
             and claim['status'] == 'ARMED'
             and all(type(claim[key]) is int for key in ('public_sequence','native_sequence','accepted_ordinal','generation'))
             and (claim['public_sequence'],claim['native_sequence'],claim['accepted_ordinal'],claim['generation']) == self.expected_namespace,
             'SCENARIO_RESPAWN_HIT_ARM_NAMESPACE_REQUIRED')
        self.claim, self.phase = dict(claim), 'ATTACK_WAIT'
        self.result.update(status='PENDING', **{k:v for k,v in claim.items() if k != 'status'})
        self.current()
        from tools.local_original_session import commands
        commands._atomic(self.scenario.monitor.directory / 'command.request.json',
            dict(schema=commands.REQUEST_SCHEMA, sequence=claim['public_sequence'], command='AttackTarget',
                uid=t.broker.realm.service(t.writer).snapshot().uid, target_uid=self.receipt.spawn.uid,
                map_id=self.receipt.spawn.map_id), 1024)
        self.current()

    async def collect(self):
        if self.phase != 'ATTACK_WAIT':
            return
        self.current()
        t, manual, session = self.trial, self.runtime.manual, self.attack_session
        result = manual.last_result
        self.capture_discarded_post(result)
        need(type(result) is dict and type(result.get('sequence')) is int,
             'SCENARIO_RESPAWN_HIT_PUBLIC_RESULT_REQUIRED')
        if result['sequence'] < self.claim['public_sequence']:
            return
        need(type(result.get('last_sequence')) is int and type(manual.sequence) is int
             and result['sequence'] == result.get('last_sequence') == manual.sequence == self.claim['public_sequence']
             and result.get('command') == 'AttackTarget' and result.get('status') in ('CLAIMED','PENDING','COMMITTED')
             and result.get('cleanup_required') is not True, 'SCENARIO_RESPAWN_HIT_NORMAL_CONSUMER_REFUSED')
        self.result.update(consumer_status=result['status'], phase=result.get('phase'), reason=result.get('reason'))
        self.scenario.capture_attack_observations.__func__(self, result)
        self.capture_attack_transport()
        self.result['attack_observations'] = self.attack['attack_observations']
        self.result['feedback'] = self.attack['feedback']
        if result['status'] != 'COMMITTED':
            return
        async with t.row['operation_lock']:
            self.current()
            validator = VALIDATE_RESPAWN_HIT
            need(type(manual) is MANUAL_TYPE and callable(validator)
                 and type(manual).validate_respawn_attack is validator
                 and manual.validate_respawn_attack.__func__ is validator,
                 'SCENARIO_RESPAWN_HIT_ACTUAL_CURRENT_PROOF_API_REQUIRED')
            proof = manual.validate_respawn_attack(self.receipt)
            proof_type = getattr(manual_move_commands, 'RESPAWN_ATTACK_PROOF_TYPE', None)
            need(proof_type is not None and type(proof) is proof_type
                 and proof is manual.consumer._respawn_attack_completed
                 and proof.receipt is self.receipt and proof.generation is self.receipt.generation
                 and proof.writer is t.writer and proof.row is t.row and proof.session is session
                 and all(type(value) is int for value in (proof.sequence,manual.consumer.sequence,
                     manual.consumer._action_sequence,proof.accepted_ordinal))
                 and proof.sequence == manual.consumer.sequence == manual.consumer._action_sequence == self.claim['native_sequence']
                 and proof.accepted_ordinal == session.accepted_count == self.before + 1 == self.claim['accepted_ordinal'],
                 'SCENARIO_RESPAWN_HIT_CURRENT_NORMAL_PROOF_REQUIRED')
            need(result.get('proof_scope') == 'VALIDATED_ATTACK_INTENT_ONLY'
                 and result.get('combat_effect') == 'UNKNOWN' and result.get('native_attempted') is True
                 and result.get('cleanup_required') is False and not manual.pending,
                 'SCENARIO_RESPAWN_HIT_NORMAL_COMMITTED_REQUIRED')
            snapshots, feedback = self.attack['attack_observations'], self.attack['feedback']
            need(feedback['state'] == 'DRAINED' and tuple(feedback[key] for key in
                 ('prepared','reserved','write_attempted','drained')) == tuple(n+1 for n in self.feedback_before)
                 and result.get('observation_scope') == 'READONLY_ACTION_SNAPSHOTS'
                 and set(result.get('attack_observations',{})) == set(snapshots) == {'pre_command','post_feedback','next_strict_idle'}
                 and all(s['status'] == 'OBSERVED' for s in snapshots.values())
                 and snapshots['pre_command']['strict_idle'] is True
                 and snapshots['post_feedback']['strict_idle'] is None
                 and snapshots['next_strict_idle']['strict_idle'] is True
                 and snapshots['pre_command']['at_ns'] < snapshots['post_feedback']['at_ns'] < snapshots['next_strict_idle']['at_ns'],
                 'SCENARIO_RESPAWN_HIT_FULL_NORMAL_SNAPSHOTS_REQUIRED')
            current = attack.AttackTargets._project(session.targets, t.writer, attack.AttackRequest(self.receipt.spawn.uid))
            counters = tuple(getattr(t.broker.realm.service(t.writer), key)
                for key in ('requests_received', 'committed', 'corrections_prepared'))
            if current[1] is not self.projection[1] or counters != self.counters:
                current, actual, _events = attack.AttackTargets.observe_committed_approach(session.targets,
                    t.writer, attack.AttackRequest(self.receipt.spawn.uid), self.projection, self.counters, self.events)
                need(actual == counters, 'SCENARIO_RESPAWN_HIT_APPROACH_CHANGED')
            else:
                need(attack.AttackTargets.same_authority(self.projection,current), 'SCENARIO_RESPAWN_HIT_TARGET_CHANGED')
            intent = session.current_intent()
            hp = session.last_hp_result
            entry = session._hp._entries.get((id(t.writer), self.receipt.spawn.uid))
            configured, = self.features.attack_hp_provider.rows
            need(intent is proof.intent and intent is not None and intent.accepted_ordinal == self.claim['accepted_ordinal']
                 and intent._bound._writer is t.writer and intent._bound.attacker is current[1]
                 and (intent._bound.target_uid,intent._bound.map_id) == (self.receipt.spawn.uid,self.receipt.spawn.map_id)
                 and type(hp) is npc_hp.Result and hp is proof.hp_result and hp is not self.old_hp
                 and hp.accepted_ordinal == self.claim['accepted_ordinal'] and hp.before == configured.hp
                 and hp.target == configured.target and hp.hit == configured.hit
                 and entry is proof.hp_entry and entry.intent is intent and entry.hp is hp.after,
                 'SCENARIO_RESPAWN_HIT_FRESH_LAZY_HP_CURRENT_INTENT_REQUIRED')
            self.validate_new_hit(proof,hp,entry)
            self.current()
            self.proof = proof
            self.result.update(status='COMMITTED', server_hp=hp.metadata(), current_intent='NEW_CURRENT_INTENT',
                attack_action_complete='NORMAL_FULL_SNAPSHOTS_AND_STRICT_IDLE', combat_effect='UNKNOWN')
            self.phase = 'DONE'
            if self.completion is None:
                self.scenario.stage = self.done_stage
                self.scenario.stop.set()
            else:
                self.completion(self)

    def capture_discarded_post(self, result):
        """The producer's bounded diagnostic is never a completion proof."""
        if (self.claim is None or type(result) is not dict or result.get('command') != 'AttackTarget'
                or type(result.get('sequence')) is not int or result['sequence'] != self.claim['public_sequence']):
            return False
        row = getattr(getattr(getattr(self.runtime, 'manual', None), 'consumer', None), '_respawn_post_discarded', None)
        if (type(row) is not dict or set(row) != {'at_ns', 'read_field', 'combined_bytes'}
                or not all(type(row[key]) is int for key in row)
                or not 0 <= row['at_ns'] < (1 << 63) or row['read_field'] != 3
                or not 0 <= row['combined_bytes'] <= 24576):
            return False
        self.result['discarded_post_feedback'] = dict(status='UNKNOWN',
            reason='ATTACK_OBSERVE_TYPED_READ_CHANGED', **row)
        return True

    def capture_terminal_result(self):
        """Output only: retain the already published final public refusal."""
        result = getattr(getattr(self.runtime, 'manual', None), 'last_result', None)
        discarded = self.capture_discarded_post(result)
        if (self.claim is None or type(result) is not dict or result.get('status') != 'UNKNOWN'
                or result.get('command') != 'AttackTarget' or type(result.get('sequence')) is not int
                or result['sequence'] != self.claim['public_sequence']):
            return discarded
        self.result.update(status='UNKNOWN', consumer_status='UNKNOWN', consumer_sequence=result['sequence'])
        for key in ('reason', 'phase'):
            value = result.get(key)
            if value is None or type(value) is str and len(value) <= 120:
                self.result['consumer_' + key] = value
                if key == 'phase':
                    self.result[key] = value
        try:
            self.scenario.capture_attack_observations.__func__(self, result)
            self.result['attack_observations'] = self.attack['attack_observations']
        except (ValueError, TypeError, KeyError, AttributeError):
            pass  # Optional output cannot replace the original terminal failure.
        return True

    def fail(self, error):
        self.result.update(status='UNKNOWN', reason=launcher.safe_error_code(error) or type(error).__name__)
        self.capture_terminal_result()
        self.phase = 'FAILED'
        self.scenario.error = self.scenario.error or self.result['reason']
        self.scenario.stage = self.failed_stage
        self.scenario.stop.set()


class CurrentLifeHit(Followup):
    """A new action on current gen2; previous action proofs remain history."""
    generation_ordinal = 2
    accepted_before = 2
    expected_namespace = (4,3,3,2)
    waiting_phase = 'WAIT_SECOND_RESPAWN_COMPLETE'
    run_stage = 'NPC_CURRENT_LIFE_NEXT_HIT_RUN'
    done_stage = 'NPC_CURRENT_LIFE_NEXT_HIT_COMPLETE_STOP_REQUESTED'
    failed_stage = 'NPC_CURRENT_LIFE_NEXT_HIT_UNKNOWN_STOP_REQUESTED'

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.result.update(scope='ONE_NORMAL_ATTACK_ON_CURRENT_GEN2_LOCAL_NPC_LIFE',
            preparation='SECOND_RESPAWN_REQUIRED_PREPARATION_ONLY')

    def prior_hp(self,second):
        return second.retire.proof.hp_result

    def _life(self):
        second=self.trial;retire=second.retire
        return super()._life()+(second,second.result,retire,retire.result,retire.proof,retire.entry,retire.record,
            retire.followup,retire.followup.result,retire.followup.proof,retire.followup.trial,
            retire.followup.trial.result,second.broker.source_guard)

    def _history_current(self):
        second=self.trial;retire=second.retire
        need(second.phase=='DONE' and second.result['status']=='COMMITTED'
             and retire.phase=='DONE' and retire.result['status']=='COMMITTED'
             and retire.followup.phase=='DONE' and retire.followup.result['status']=='COMMITTED'
             and retire.followup.trial.phase=='DONE' and retire.followup.trial.result['status']=='COMMITTED',
             'SCENARIO_CURRENT_LIFE_COMPLETED_HISTORY_CHANGED')

    def current(self):
        self._history_current();super().current()
        self.trial.broker.source_guard()
        self._history_current();super().current()

    def begin(self,second):
        need(type(second) is SecondRespawn and second.phase=='DONE' and second.result['status']=='COMMITTED',
             'SCENARIO_CURRENT_LIFE_SECOND_RESPAWN_REQUIRED')
        super().begin(second)

    def capture_discarded_post(self,result):
        consumer=self.runtime.manual.consumer
        claim=getattr(consumer,'_respawn_attack_claim',None)
        if claim is None or getattr(consumer,'_respawn_post_discarded_claim',None) is not claim:
            return False
        return super().capture_discarded_post(result)

    def validate_new_hit(self,proof,hp,entry):
        old=self.trial.retire
        record=self.attack_session._notifications._records.get((id(proof.writer),self.receipt.spawn.uid))
        need(proof is not old.proof and proof.generation is self.receipt.generation
             and proof.intent is not old.proof.intent and entry is not old.entry
             and hp is not old.proof.hp_result and hp.accepted_ordinal==3 and hp.died
             and record is not None and record is not old.record and record.entry is entry
             and record.result is hp and record.death.phase=='DRAINED' and record.death.drained is True
             and record.death.write_attempted is True
             and record.remove is None and not record.removed,
             'SCENARIO_CURRENT_LIFE_FRESH_INTENT_HP_DEATH_REQUIRED')
        self.result.update(new_hp_entry='FRESH_GEN2_ORDINAL3_ENTRY',death_transport=dict(
            status='DRAINED',accepted_ordinal=3,target_uid=self.receipt.spawn.uid,
            write_attempted=record.death.write_attempted,drained=record.death.drained,proof_scope='TRANSPORT_DRAIN_ONLY'))


class Retire:
    """Explicit removal of the completed gen1 lethal life, with one fresh absence."""
    generation_ordinal = 1
    accepted_ordinal = 2
    scope = 'GEN1_ORDINAL2_REMOVE_AND_FRESH_UID_ABSENCE'
    preparation = 'RESPAWN_AND_NEXT_HIT_REQUIRED_PREPARATION_ONLY'
    waiting_phase = 'WAIT_FOLLOWUP_COMPLETE'
    run_stage = 'NPC_RETIRE_SECOND_LIFE_RUN'
    done_stage = 'NPC_RETIRE_SECOND_LIFE_COMPLETE_STOP_REQUESTED'
    failed_stage = 'NPC_RETIRE_SECOND_LIFE_UNKNOWN_STOP_REQUESTED'

    def __init__(self, scenario, runtime, *, clock_ns=time.monotonic_ns, completion=None):
        need(completion is None or callable(completion),'SCENARIO_NPC_RETIRE_COMPLETION_REQUIRED')
        self.completion = completion
        self.scenario, self.runtime, self.clock_ns = scenario, runtime, clock_ns
        self.phase, self.started_ns = self.waiting_phase, None
        self.followup = self.proof = self.entry = self.record = self.refs = self.scalars = None
        self.death_claimed = self.remove_claimed = self.registry_claimed = False
        self.removed = False
        self.result = dict(status='NOT_REQUESTED', scope=self.scope,
            preparation=self.preparation, death_action=None,
            remove_transport=None, registry=None, target_reuse='UNKNOWN', screen='UNKNOWN', free='UNKNOWN',
            automatic_retry=False, snapshot_atomic=False, leaf_deadline_ns=WAIT_NS,
            completed_proof_deadline_ns=manual_move_commands.WAIT_NS)

    def _same_lifetime(self):
        f, proof = self.followup, self.proof
        b, writer, row, receipt = f.trial.broker, proof.writer, proof.row, proof.receipt
        session = proof.session
        need(f.phase == 'DONE' and f.result['status'] == 'COMMITTED' and f.proof is proof
             and all(a is b for a,b in zip(f._life() + (b.source_guard,), self.refs))
             and all(type(a) is type(b) and a == b for a,b in zip(f._scalars(),self.scalars)),
             'SCENARIO_NPC_RETIRE_COMPLETED_LIFE_CHANGED')
        need(type(proof) is getattr(manual_move_commands,'RESPAWN_ATTACK_PROOF_TYPE',None)
             and proof is self.runtime.manual.consumer._respawn_attack_completed
             and proof.generation is receipt.generation and type(receipt.generation.ordinal) is int and receipt.generation.ordinal == self.generation_ordinal
             and b._attack_session is session and not session.closed and not session.fatal
             and session.last_hp_result is proof.hp_result and session.accepted_count == proof.accepted_ordinal == self.accepted_ordinal
             and session._hp._entries.get((id(writer),receipt.spawn.uid)) is self.entry is proof.hp_entry
             and session._notifications._records.get((id(writer),receipt.spawn.uid)) is self.record
             and self.record.entry is self.entry and self.record.result is proof.hp_result
             and self.entry.writer is writer and self.entry.row is row and self.entry.lock is row['operation_lock']
             and session._notifications.death_policy == npc_death.DEATH_POLICY
             and session._notifications.remove_policy == npc_death.REMOVE_POLICY
             and self.entry.intent is proof.intent and self.entry.hp is proof.hp_result.after
             and proof.hp_result.died and not self.entry.hp.alive,
             'SCENARIO_NPC_RETIRE_CURRENT_LETHAL_RECORD_REQUIRED')
        rows=[r for values in b._claims.values() for r in values if r['writer'] is writer]
        need(len(rows)==1 and rows[0] is row and not row['failed'] and not row['joined']
             and not b._closing and not b.failure.is_set() and not self.runtime._closed,
             'SCENARIO_NPC_RETIRE_CURRENT_CLAIM_REQUIRED')
        realm=b.realm;game=realm.registry.resolve(writer)
        recipe,=[spawn for spawn,_ in realm._npc_spawns if spawn.uid==receipt.spawn.uid]
        life=(realm,realm.registry,game,game.selection,realm.service(writer),realm._npc_frames[id(writer)],
            realm._npc_spawns,recipe,row['operation_lock'],row['policy_row'])
        need(len(life)==len(self.entry.lifetime) and all(a is c for a,c in zip(life,self.entry.lifetime))
             and life[5] is receipt.generation.frames and recipe is receipt.recipe,
             'SCENARIO_NPC_RETIRE_SELECTED_LIFETIME_CHANGED')
        receipt._service.require_current(receipt)
        need(receipt._service._phases.get(id(writer))=='COMMITTED'
             and self.runtime._npc_respawn_receipt is receipt
             and self.runtime.npc_session._generation is receipt.generation
             and self.runtime.npc_session._owned_mover is receipt.mover
             and self.runtime.npc_session._goal is None and not self.runtime.npc_session._closed
             and not self.runtime.npc_session.factory._closed,
             'SCENARIO_NPC_RETIRE_ADOPTED_GENERATION_CHANGED')
        need(self.record.death.phase=='DRAINED' and self.record.death.drained is True
             and self.record.death.write_attempted is True
             and npc_death.validate_frame(self.record.death.wire)==(npc_death.DEATH_OPCODE,receipt.spawn.uid),
             'SCENARIO_NPC_RETIRE_DEATH_DRAIN_REQUIRED')
        if self.removed:
            need(self.record.removed is True and self.record.remove is not None
                 and self.record.remove.phase=='DRAINED' and self.record.remove.drained is True
                 and self.record.remove.write_attempted is True
                 and session._notifications.is_removed(writer,receipt.spawn.uid) is True
                 and npc_death.validate_frame(self.record.remove.wire)==(npc_death.REMOVE_OPCODE,receipt.spawn.uid),
                 'SCENARIO_NPC_RETIRE_TOMBSTONE_REQUIRED')
        else:
            need(self.record.removed is False and self.record.remove is None,
                 'SCENARIO_NPC_RETIRE_UNCLAIMED_REMOVE_REQUIRED')

    def current(self):
        need(not self.scenario.stop.is_set(), 'SCENARIO_NPC_RETIRE_CANCELLED')
        self._same_lifetime()
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
        self.followup.trial.broker.source_guard()
        self._same_lifetime() # No target projection after Remove, including callbacks.
        manual_move_commands._source_quit_cancel_check()
        need(type(self.started_ns) is int and 0<=self.clock_ns()-self.started_ns<WAIT_NS,
             'SCENARIO_NPC_RETIRE_ORIGINAL_DEADLINE')

    def before_remove(self):
        self.current()
        need(self.proof.row['operation_lock'].locked(),'SCENARIO_NPC_RETIRE_EXISTING_ROW_LOCK_REQUIRED')
        manual=self.runtime.manual
        need(type(manual) is MANUAL_TYPE and type(manual).validate_respawn_attack is VALIDATE_RESPAWN_HIT
             and manual.validate_respawn_attack.__func__ is VALIDATE_RESPAWN_HIT
             and manual.validate_respawn_attack(self.proof.receipt) is self.proof,
             'SCENARIO_NPC_RETIRE_CURRENT_COMPLETED_PROOF_REQUIRED')
        self.current() # The canonical proof enforces its original 10-second clock.

    def begin(self, followup):
        need(self.phase==self.waiting_phase,'SCENARIO_NPC_RETIRE_ONCE_HANDOFF_REQUIRED')
        self.phase,self.started_ns='DEATH_SAMPLE',self.clock_ns()
        self.followup,self.proof=followup,followup.proof
        self.entry=self.proof.hp_entry
        b=followup.trial.broker
        self.record=b._attack_session._notifications._records.get((id(self.proof.writer),self.proof.receipt.spawn.uid))
        self.refs=followup._life()+(b.source_guard,);self.scalars=followup._scalars()
        self.before_remove()
        self.result.update(status='PENDING',generation=self.generation_ordinal,accepted_ordinal=self.accepted_ordinal,server_hp=self.proof.hp_result.metadata())
        self.scenario.stage=self.run_stage

    async def step(self):
        self.current()
        p=self.proof;row=p.row;uid=p.receipt.spawn.uid;b=self.followup.trial.broker
        if self.phase=='DEATH_SAMPLE':
            need(not self.death_claimed,'SCENARIO_NPC_RETIRE_DEATH_SAMPLE_NO_REPLAY')
            self.death_claimed=True
            observer=self.runtime.manual.consumer._attack_action_observer
            need(type(observer) is attack_action_observe.AttackActionObserver
                 and observer.reader is self.scenario.reader and observer.targets.broker is b
                 and observer.prepare.__self__ is observer and observer.collect.__self__ is observer
                 and observer.prepare.__func__ is attack_action_observe.PREPARE_METHOD
                 and observer.collect.__func__ is attack_action_observe.COLLECT_METHOD
                 and type(observer).prepare is attack_action_observe.PREPARE_METHOD
                 and type(observer).collect is attack_action_observe.COLLECT_METHOD,
                 'SCENARIO_NPC_RETIRE_CANONICAL_DEATH_OBSERVER_REQUIRED')
            async with row['operation_lock']:
                self.before_remove()
                await observer.prepare(p.writer,uid,now_ns=self.clock_ns())
                self.before_remove()
                reader=self.scenario.reader
                need(type(reader) is observe.RetainedSceneReader and type(reader).sample is RETAINED_SAMPLE
                     and reader.sample.__self__ is reader and reader.sample.__func__ is RETAINED_SAMPLE,
                     'SCENARIO_NPC_RETIRE_CANONICAL_READER_REQUIRED')
                memory,_=reader.sample(include_input_state=False,attack_action_observer=observer)
                self.before_remove()
            raw=memory.get('attack_action',{})
            positive=any((raw.get('target') or {}).get(slot,{}).get('status')=='OBSERVED'
                and (raw.get('target') or {}).get(slot,{}).get('present') is True
                and (raw.get('target') or {}).get(slot,{}).get('kind')=='DeathAction'
                for slot in ('current','queue_head'))
            self.result['death_action']=dict(status=raw.get('status','UNKNOWN'),reason=raw.get('reason'),
                source='CANONICAL_RETAINED_SAMPLE',positive_death=positive,raw=raw)
            need(raw.get('status')=='OBSERVED' and raw.get('source_contract_valid') is True
                 and raw.get('stable_double_read') is True and raw.get('target_uid')==uid
                 and raw.get('actor_uid')==b.realm.service(p.writer).snapshot().uid
                 and raw.get('map_id')==p.receipt.spawn.map_id and raw.get('snapshot_atomic') is False
                 and raw.get('typed_byte_limit')==attack_action_observe.BYTE_LIMIT
                 and type(raw.get('typed_bytes_requested')) is int and type(raw.get('combined_typed_bytes_requested')) is int
                 and 0<=raw['typed_bytes_requested']<=raw['combined_typed_bytes_requested']<=attack_action_observe.BYTE_LIMIT,
                 'SCENARIO_NPC_RETIRE_DEATH_SNAPSHOT_UNKNOWN')
            need(positive,'SCENARIO_NPC_RETIRE_POSITIVE_DEATH_REQUIRED')
            self.phase='REMOVE_READY'
            return
        if self.phase=='REMOVE_READY':
            need(not self.remove_claimed,'SCENARIO_NPC_RETIRE_REMOVE_NO_REPLAY')
            self.remove_claimed=True
            async with row['operation_lock']:
                self.before_remove()
            need(not row['operation_lock'].locked(),'SCENARIO_NPC_RETIRE_REMOVE_OUTSIDE_LOCK_REQUIRED')
            need(type(b) is broker_module.PersistentBroker and type(b).remove_dead_npc is REMOVE_NPC_METHOD
                 and b.remove_dead_npc.__func__ is REMOVE_NPC_METHOD,'SCENARIO_NPC_RETIRE_PUBLIC_REMOVE_REQUIRED')
            self.result['remove_transport']=dict(status='CLAIMED_NO_RETRY')
            result=await b.remove_dead_npc(p.writer,uid,self.accepted_ordinal,policy=npc_death.REMOVE_POLICY)
            self.removed=True
            self.current()
            self.result['remove_transport']=result
            need(type(result) is dict and result.get('status')=='DRAINED' and result.get('target_uid')==uid
                 and result.get('accepted_ordinal')==self.accepted_ordinal and result.get('client_registry')=='UNKNOWN',
                 'SCENARIO_NPC_RETIRE_REMOVE_DRAIN_REQUIRED')
            self.phase='REGISTRY_SAMPLE'
            return
        need(self.phase=='REGISTRY_SAMPLE' and not self.registry_claimed,'SCENARIO_NPC_RETIRE_REGISTRY_NO_REPLAY')
        self.registry_claimed=True
        observer=npc_observe.NpcObserver(b,self.scenario.reader)
        need(type(observer).sample_registry is REGISTRY_SAMPLE and observer.sample_registry.__self__ is observer
             and observer.sample_registry.__func__ is REGISTRY_SAMPLE,
             'SCENARIO_NPC_RETIRE_CANONICAL_REGISTRY_REQUIRED')
        async with row['operation_lock']:
            self.current()
            result=await observer.sample_registry(p.writer,uid,now_ns=self.clock_ns())
            self.current()
            try:
                attack.AttackTargets._project(p.session.targets,p.writer,attack.AttackRequest(uid))
            except ValueError as error:
                need(error.args==('ATTACK_LOCAL_TARGET_REMOVED',),'SCENARIO_NPC_RETIRE_WRONG_REUSE_REFUSAL')
            else:
                need(False,'SCENARIO_NPC_RETIRE_TARGET_REUSE_NOT_REFUSED')
            self.current()
        self.result['registry']=result
        self.result['target_reuse']=dict(status='REFUSED',reason='ATTACK_LOCAL_TARGET_REMOVED',
            scope='CANONICAL_LOCAL_TARGET_ADMISSION',native_attempted=False,wire_attempted=False)
        need(type(result) is dict and result.get('status')=='OBSERVED' and result.get('uid')==uid
             and result.get('map_id')==p.receipt.spawn.map_id and result.get('source_contract_valid') is True
             and result.get('stable_double_read') is True and result.get('lookup_scope')=='THREE_LOOKUP_VECTORS'
             and result.get('observation_scope')=='READONLY_SNAPSHOT' and result.get('snapshot_atomic') is False
             and type(result.get('uid_absent')) is bool and type(result.get('vector_counts')) is list
             and len(result['vector_counts'])==3 and all(type(n) is int and n>=0 for n in result['vector_counts'])
             and type(result.get('typed_bytes_requested')) is int and 0<=result['typed_bytes_requested']<=16384
             and result.get('typed_byte_limit')==16384 and result.get('max_samples_per_second')==2,
             'SCENARIO_NPC_RETIRE_REGISTRY_UNKNOWN')
        self.result['status']='COMMITTED' if result['uid_absent'] is True else 'PARTIAL'
        self.phase='DONE'
        if self.completion is not None and self.result['status']=='COMMITTED':
            async with row['operation_lock']:
                self.current()
                self.completion(self)
        else:
            self.scenario.stage=self.done_stage
            self.scenario.stop.set()

    def fail(self,error):
        reason=launcher.safe_error_code(error) or type(error).__name__
        self.result.update(status='UNKNOWN',reason=reason)
        self.phase='FAILED'
        self.scenario.error=self.scenario.error or reason
        self.scenario.stage=self.failed_stage
        self.scenario.stop.set()


class CurrentLifeRetire(Retire):
    """Retire only the completed current gen2/ordinal3 lethal life."""
    generation_ordinal = 2
    accepted_ordinal = 3
    scope = 'GEN2_ORDINAL3_REMOVE_AND_FRESH_UID_ABSENCE'
    preparation = 'CURRENT_GEN2_NORMAL_HIT_REQUIRED_PREPARATION_ONLY'
    waiting_phase = 'WAIT_CURRENT_LIFE_HIT_COMPLETE'
    run_stage = 'NPC_CURRENT_LIFE_RETIRE_RUN'
    done_stage = 'NPC_CURRENT_LIFE_RETIRE_COMPLETE_STOP_REQUESTED'
    failed_stage = 'NPC_CURRENT_LIFE_RETIRE_UNKNOWN_STOP_REQUESTED'

    def _same_lifetime(self):
        super()._same_lifetime()
        proof=self.proof;consumer=self.runtime.manual.consumer
        claims=consumer._respawn_attack_claims;completed=consumer._respawn_attack_completions
        need(type(self.followup) is CurrentLifeHit and type(claims) is type(completed) is tuple
             and len(claims)==len(completed)==2 and claims[-1] is proof.claim is consumer._respawn_attack_claim
             and completed[-1] is proof is consumer._respawn_attack_completed and proof._consumer is consumer
             and consumer.pending is None and consumer.state is proof._state and consumer.state==proof._state_data
             and all(type(n) is int for n in (proof.sequence,consumer.sequence,consumer._action_sequence,
                 proof.accepted_ordinal,self.runtime.manual.sequence))
             and proof.sequence==consumer.sequence==consumer._action_sequence==3
             and proof.accepted_ordinal==3 and self.runtime.manual.sequence==4
             and proof.receipt is self.followup.receipt is self.followup.trial.receipt,
             'SCENARIO_CURRENT_RETIRE_CURRENT_GEN2_CLAIM_REQUIRED')


class SecondRespawn:
    """One explicit gen1 to gen2 transaction; old completions are history only."""
    _base = Trial._base
    _scalars = Trial._scalars
    _same_base = Trial._same_base

    def __init__(self, scenario, runtime, *, clock_ns=time.monotonic_ns, completion=None):
        need(completion is None or callable(completion),'SCENARIO_SECOND_RESPAWN_COMPLETION_REQUIRED')
        self.completion=completion
        self.scenario,self.runtime,self.clock_ns=scenario,runtime,clock_ns
        self.phase,self.started_ns='WAIT_RETIRE_COMPLETE',None
        self.retire=self.receipt=self.observer=self.base_refs=self.base_scalars=self.new_refs=None
        self.preparation_proof=None
        self.claimed=self.registry_claimed=self.pose_claimed=False
        self.result=dict(status='NOT_REQUESTED',scope='SECOND_EXPLICIT_SAME_UID_LOCAL_LIFE_ONLY',
            preparation='GEN1_RETIREMENT_REQUIRED_PREPARATION_ONLY',respawn=None,registry=None,pose=None,
            current_target='UNKNOWN',hp='UNKNOWN',screen='UNKNOWN',free='UNKNOWN',automatic_retry=False)

    def _old(self):
        r=self.runtime;session=r.npc_session;g=self.service.current_generation(self.writer)
        need(type(session) is npc_session.NpcSession and not session._closed and not session.factory._closed
             and session.factory._session is session and session.factory.reader is self.scenario.reader
             and session.factory.config.spawns[0] is self.scenario.features.spawns[0]
             and session.factory.config.respawn_policy==self.scenario.features.npc_respawn_policy
             and session._generation is g and session._owned_mover is g.mover and session._goal is None
             and g.mover.spawn_drained is True and not g.mover.closed and not g.mover.fatal and g.mover.pending is None,
             'SCENARIO_SECOND_RESPAWN_CURRENT_OLD_SESSION_REQUIRED')
        return (r._npc_respawn_receipt,g,session,session.factory,session.factory.config,session.factory.reader,
            session.factory.adapter,g.mover,g.mover.state,g.frames)

    def _new(self):
        receipt,r=self.receipt,self.runtime
        need(type(receipt) is npc_respawn.Receipt,'SCENARIO_SECOND_RESPAWN_REAL_RECEIPT_REQUIRED')
        self.service.require_current(receipt)
        seed=self.scenario.features.npc_respawn_spawn;old=self.old_refs
        need(receipt is not old[0] and receipt.old_generation is old[1]
             and type(receipt.generation.ordinal) is int and receipt.generation.ordinal==2
             and receipt.generation is not old[1] and receipt.writer is self.writer and receipt.row is self.row
             and receipt.recipe is self.scenario.features.spawns[0] and receipt.recipe is old[0].recipe
             and receipt.spawn is not seed and receipt.spawn is not old[0].spawn
             and type(receipt.spawn) is npc.NpcSpawn
             and (receipt.spawn.map_id,receipt.spawn.policy,dict(receipt.spawn.fields)) == (seed.map_id,seed.policy,dict(seed.fields))
             and receipt.generation.frames is self.broker.realm._npc_frames[id(self.writer)]
             and receipt.generation.frames is not old[9] and receipt.generation.frames[3][0] is not old[9][3][0]
             and self.service._phases.get(id(self.writer))=='COMMITTED' and r._npc_respawn_receipt is receipt,
             'SCENARIO_SECOND_RESPAWN_FRESH_GENERATION_REQUIRED')
        session=r.npc_session
        need(type(session) is npc_session.NpcSession and session is not old[2] and session.factory is not old[3]
             and session.factory.config is old[4] and session.factory.reader is self.scenario.reader
             and session.factory._session is session and session.factory.adapter is receipt.adapter
             and session._generation is receipt.generation and session._owned_mover is receipt.mover
             and receipt.mover is self.broker.realm.npc_mover(self.writer) and receipt.mover is not old[7]
             and receipt.mover.spawn_drained is True and receipt.mover.pending is None
             and not session._closed and not session.factory._closed and not receipt.mover.closed and not receipt.mover.fatal
             and session._goal is None and old[2]._closed and old[3]._closed and old[7].closed,
             'SCENARIO_SECOND_RESPAWN_FRESH_PRODUCT_REQUIRED')
        binding=session.current_binding()
        need(binding is not None and binding.owner is self.writer and binding.broker is self.broker,
             'SCENARIO_SECOND_RESPAWN_CURRENT_BINDING_REQUIRED')
        attack_session_=self.broker._attack_session;key=(id(self.writer),seed.uid)
        need(attack_session_ is self.attack_session and not attack_session_.closed and not attack_session_.fatal
             and attack_session_.accepted_count==2 and attack_session_.feedback_drained==2
             and attack_session_.current_intent() is None and key not in attack_session_._hp._entries
             and key not in attack_session_._notifications._records,
             'SCENARIO_SECOND_RESPAWN_LAZY_HP_NOT_INITIALIZED_REQUIRED')
        return (receipt,receipt.generation,receipt.spawn,receipt.recipe,receipt.mover,receipt.mover.state,
                receipt.adapter,session,session.factory,session.factory.config,session.factory.reader,receipt.generation.frames)

    def current(self):
        def structural():
            need(not self.scenario.stop.is_set(),'SCENARIO_SECOND_RESPAWN_CANCELLED')
            self._same_base()
            need(self.retire.phase=='DONE' and self.retire.result is self.history[0]
                 and self.retire.result['status']=='COMMITTED' and self.retire.proof is self.history[1]
                 and self.retire.followup.phase=='DONE' and self.retire.followup.result is self.history[2]
                 and self.retire.followup.trial.phase=='DONE' and self.retire.followup.trial.result is self.history[3]
                 and self.broker.source_guard is self.source_guard,
                 'SCENARIO_SECOND_RESPAWN_HISTORY_OR_SOURCE_CHANGED')
            if self.receipt is None:
                need(all(a is b for a,b in zip(self._old(),self.old_refs)),
                     'SCENARIO_SECOND_RESPAWN_OLD_GENERATION_CHANGED')
            else:
                refs=self._new()
                need(self.new_refs is None or all(a is b for a,b in zip(refs,self.new_refs)),
                     'SCENARIO_SECOND_RESPAWN_NEW_LIFE_CHANGED')
        structural()
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
        self.source_guard()
        structural()
        now_ns=self.clock_ns()
        need(type(self.started_ns) is int and type(now_ns) is int and 0<=now_ns-self.started_ns<WAIT_NS,
             'SCENARIO_SECOND_RESPAWN_OPERATION_DEADLINE')
        task=asyncio.current_task()
        if task is not None and task.cancelling():raise asyncio.CancelledError()

    def begin(self,retire):
        need(self.phase=='WAIT_RETIRE_COMPLETE' and retire.phase=='DONE' and retire.result['status']=='COMMITTED',
             'SCENARIO_SECOND_RESPAWN_ONCE_HANDOFF_REQUIRED')
        self.retire=retire;self.started_ns=self.clock_ns();self.phase='RESPAWN_READY'
        need(retire.proof.row['operation_lock'].locked(),'SCENARIO_SECOND_RESPAWN_ROWLOCK_HANDOFF_REQUIRED')
        retire.current() # Current gen1 tombstone authority, before any new adoption.
        self.broker=retire.followup.trial.broker;self.writer=retire.proof.writer;self.row=retire.proof.row
        self.service=self.broker._npc_respawn;self.attack_session=self.broker._attack_session
        self.old_refs=self._old()
        need(type(self.old_refs[1].ordinal) is int and self.old_refs[1].ordinal==1,
             'SCENARIO_SECOND_RESPAWN_EXACT_GEN1_REQUIRED')
        self.history=(retire.result,retire.proof,retire.followup.result,retire.followup.trial.result)
        self.source_guard=self.broker.source_guard;self.base_refs,self.base_scalars=self._base(),self._scalars()
        self.current()
        self.result.update(status='PENDING',old_generation=1,accepted_ordinal=2)
        self.scenario.stage='NPC_SECOND_RESPAWN_RUN'

    async def step(self):
        self.current();uid=self.scenario.features.spawns[0].uid
        if self.phase=='RESPAWN_READY':
            need(not self.claimed,'SCENARIO_SECOND_RESPAWN_NO_REPLAY');self.claimed=True
            need(type(self.runtime) is launcher.ProductFeatures and type(self.runtime).respawn_npc is RESPAWN_METHOD
                 and self.runtime.respawn_npc.__self__ is self.runtime and self.runtime.respawn_npc.__func__ is RESPAWN_METHOD,
                 'SCENARIO_SECOND_RESPAWN_PUBLIC_API_REQUIRED')
            self.receipt=await self.runtime.respawn_npc(writer=self.writer,target_uid=uid,accepted_ordinal=2,
                spawn=self.scenario.features.npc_respawn_spawn,now_ns=self.clock_ns(),
                policy=self.scenario.features.npc_respawn_policy,monitor=self.scenario.monitor)
            self.current();self.new_refs=self._new()
            metadata=self.receipt.metadata()
            need(metadata.get('status')=='COMMITTED' and metadata.get('generation')==2
                 and metadata.get('transport')=='DRAINED' and metadata.get('client_registry')=='UNKNOWN',
                 'SCENARIO_SECOND_RESPAWN_DRAIN_METADATA_REQUIRED')
            self.result['respawn']=metadata
            self.observer=npc_observe.NpcObserver(self.broker,self.scenario.reader)
            self.phase='NEW_REGISTRY';return
        registry=self.phase=='NEW_REGISTRY'
        need(self.phase in ('NEW_REGISTRY','NEW_POSE'),'SCENARIO_SECOND_RESPAWN_PHASE_REQUIRED')
        claim='registry_claimed' if registry else 'pose_claimed'
        need(not getattr(self,claim),'SCENARIO_SECOND_RESPAWN_SAMPLE_NO_REPLAY');setattr(self,claim,True)
        observer=self.observer;method=REGISTRY_SAMPLE if registry else MOTION_SAMPLE
        bound=observer.sample_registry if registry else observer.sample_motion
        need(type(observer) is npc_observe.NpcObserver and observer.targets.broker is self.broker
             and observer.targets.reader is self.scenario.reader and bound.__self__ is observer and bound.__func__ is method
             and (type(observer).sample_registry if registry else type(observer).sample_motion) is method,
             'SCENARIO_SECOND_RESPAWN_CANONICAL_OBSERVER_REQUIRED')
        async with self.row['operation_lock']:
            self.current();result=await bound(self.writer,uid,now_ns=self.clock_ns());self.current()
            target=attack.AttackTargets._project(self.attack_session.targets,self.writer,attack.AttackRequest(uid))
            self.current()
        self.result['registry' if registry else 'pose']=result
        need(type(result) is dict and result.get('status')=='OBSERVED' and result.get('uid')==uid
             and result.get('map_id')==self.receipt.spawn.map_id and result.get('source_contract_valid') is True
             and result.get('snapshot_atomic') is False and type(result.get('typed_bytes_requested')) is int
             and 0<=result['typed_bytes_requested']<=16384 and result.get('typed_byte_limit')==16384
             and result.get('max_samples_per_second')==2,'SCENARIO_SECOND_RESPAWN_OBSERVATION_UNKNOWN')
        if registry:
            counts=result.get('vector_counts')
            need(result.get('stable_double_read') is True and result.get('uid_absent') is False
                 and result.get('lookup_scope')=='THREE_LOOKUP_VECTORS' and result.get('observation_scope')=='READONLY_SNAPSHOT'
                 and type(counts) is list and len(counts)==3 and all(type(n) is int and n>=0 for n in counts),
                 'SCENARIO_SECOND_RESPAWN_REGISTRATION_REQUIRED')
            self.phase='NEW_POSE';return
        consistency=result.get('read_consistency')
        stable=(result.get('stable_double_read') is True and consistency=='STRICT_STABLE'
            or result.get('stable_double_read') is False and type(consistency) is str
            and consistency in ('SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE',
                'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_FINAL_READBACK','SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_BOTH')
            and result.get('motion_scope')=='READONLY_DIRECT_NPC_MOTION_STOP')
        expected=movement.authority.unpack_grid(self.receipt.spawn.fields[1])
        need(stable and result.get('source_owner_revalidated') is True and result.get('client_grid_used_as_authority') is False
             and grid(result.get('server_grid'))==expected,'SCENARIO_SECOND_RESPAWN_POSE_SOURCE_REQUIRED')
        matched=result.get('coordinates_match') is True and grid(result.get('client_grid'))==expected and result.get('npc_idle') is True
        self.current()
        self.result.update(status='COMMITTED' if matched else 'PARTIAL',generation=2,
            current_target='FRESH_CANONICAL_TARGET_ADMISSIBLE',hp='HP_NOT_INITIALIZED_LAZY_PROVIDER_PENDING')
        self.phase='DONE'
        if self.completion is not None and self.result['status']=='COMMITTED':
            self.completion(self)
        else:
            self.scenario.stage='NPC_SECOND_RESPAWN_COMPLETE_STOP_REQUESTED';self.scenario.stop.set()

    def fail(self,error):
        reason=launcher.safe_error_code(error) or type(error).__name__
        self.result.update(status='UNKNOWN',reason=reason);self.phase='FAILED'
        self.scenario.error=self.scenario.error or reason
        self.scenario.stage='NPC_SECOND_RESPAWN_UNKNOWN_STOP_REQUESTED';self.scenario.stop.set()


class RespawnMotion(npc_motion_focused.Trial):
    """One explicit move on the fresh gen1 life; completed prep stays history."""
    def __init__(self,scenario,runtime,*,goal):
        need(type(goal) is tuple and grid(goal)==goal and goal==(32578,32946),
             'SCENARIO_RESPAWN_MOTION_EXACT_GOAL_REQUIRED')
        self.scenario,self.runtime,self.goal=scenario,runtime,goal
        self.phase='WAIT_RESPAWN_COMPLETE'
        self.result=dict(status='NOT_REQUESTED',scope='FRESH_GEN1_EXPLICIT_ONE_STEP_POSE_IDLE',
            preparation='GEN1_RESPAWN_REQUIRED_PREPARATION_ONLY',goal=list(goal),screen='UNKNOWN',automatic_retry=False)
        self.clock_ns=time.monotonic_ns

    def begin(self,trial):
        need(self.phase=='WAIT_RESPAWN_COMPLETE' and trial.phase=='DONE' and trial.result['status']=='COMMITTED',
             'SCENARIO_RESPAWN_MOTION_ONCE_HANDOFF_REQUIRED')
        self.phase='BINDING';started=self.clock_ns();self.trial=trial
        self.receipt=trial.receipt;self.service=trial.service
        npc_motion_focused.Trial.__init__(self,self.scenario,self.runtime,goal=self.goal,clock_ns=self.clock_ns)
        self.started_ns=started
        self.writer,self.row=trial.writer,trial.row
        self.mover=self.receipt.mover;self.before=self.mover.state
        need(type(self.receipt) is npc_respawn.Receipt and type(self.receipt.generation.ordinal) is int
             and self.receipt.generation.ordinal==1 and self.runtime._npc_respawn_receipt is self.receipt
             and self.service.require_current(self.receipt) is self.receipt.generation
             and self.service._phases.get(id(self.writer))=='COMMITTED'
             and self.mover is trial.broker.realm.npc_mover(self.writer)
             and self.session is self.runtime.npc_session and self.session._generation is self.receipt.generation
             and self.session._owned_mover is self.mover and self.session._goal is None,
             'SCENARIO_RESPAWN_MOTION_CURRENT_GEN1_REQUIRED')
        start=movement.authority.unpack_grid(self.before.packed)
        need(self.before.map_id==0 and start==(32577,32946)
             and self.before.last_step_ns is self.before.goal is None
             and max(abs(a-b) for a,b in zip(start,self.goal))==1,
             'SCENARIO_RESPAWN_MOTION_FRESH_ADJACENT_START_REQUIRED')
        self.history=trial.result;self.source_guard=trial.broker.source_guard
        self.life=self._life(trial.broker);self.retained_scalars=self._retained_scalars()
        player=trial.broker.realm.service(self.writer)
        self.movement_counters=(player.requests_received,player.committed,player.corrections_prepared)
        self.event_start=trial.broker.policy.events;self.sent_before=self.row['policy_row'].sent
        self.result.update(status='PENDING',scope='FRESH_GEN1_EXPLICIT_ONE_STEP_POSE_IDLE',
            preparation='GEN1_RESPAWN_REQUIRED_PREPARATION_ONLY',generation=1,
            receipt_before_motion=self.receipt.metadata(),server_before=self.state(self.before),
            edge_byte_limit=40960,pose_byte_limit=16384,hp='HP_NOT_INITIALIZED_LAZY_PROVIDER_PENDING')
        self.phase='PRE_POSE';self.scenario.stage='NPC_RESPAWN_MOTION_RUN'
        self.current(trial.broker)

    def _life(self,broker):
        receipt=self.receipt
        return super()._life(broker)+(self.trial,self.trial.result,receipt,receipt.generation,receipt.recipe,
            receipt.spawn,receipt.mover,receipt.adapter,receipt.generation.frames,broker.source_guard)

    def _same(self,broker,*,transition=False):
        super()._same(broker,transition=transition)
        receipt=self.receipt;session=broker._attack_session;key=(id(self.writer),receipt.spawn.uid)
        need(self.trial.phase=='DONE' and self.trial.result is self.history and self.history['status']=='COMMITTED'
             and self.runtime._npc_respawn_receipt is receipt and receipt._service is self.service
             and self.service.require_current(receipt) is receipt.generation
             and self.service._phases.get(id(self.writer))=='COMMITTED'
             and receipt.generation.ordinal==1 and receipt.generation.frames is broker.realm._npc_frames[id(self.writer)]
             and receipt.writer is self.writer and receipt.row is self.row and receipt.mover is self.mover
             and self.session._generation is receipt.generation and self.session._owned_mover is self.mover
             and broker.source_guard is self.source_guard and self.runtime._closed is False
             and session.accepted_count==1 and session.feedback_drained==1 and session.current_intent() is None
             and key not in session._hp._entries and key not in session._notifications._records,
             'SCENARIO_RESPAWN_MOTION_LIFE_CHANGED')

    def current(self,broker,*,transition=False):
        self._same(broker,transition=transition)
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
        self.source_guard();self._same(broker,transition=transition)
        now=self.clock_ns()
        need(type(self.started_ns) is int and type(now) is int and 0<=now-self.started_ns<WAIT_NS,
             'SCENARIO_RESPAWN_MOTION_ORIGINAL_DEADLINE')
        manual_move_commands._source_quit_cancel_check()

    async def sample(self,broker):
        await super().sample(broker)
        if self.phase=='DONE':self.scenario.stage='NPC_RESPAWN_MOTION_COMPLETE_STOP_REQUESTED'

    async def poll(self,monitor):
        broker=self.trial.broker
        need(monitor is self.scenario.monitor and self.runtime._npc_bound_monitor is monitor,
             'SCENARIO_RESPAWN_MOTION_BOUND_MONITOR_REQUIRED')
        self.current(broker)
        due=self.clock_ns()/1e9>=monitor.next_memory
        if self.phase in ('PRE_POSE','POST_POSE'):
            if self.phase=='POST_POSE' and not self.at_goal:
                result=await self._npc_poll(monitor,reserve=False)
                self.after_poll(broker,result)
            if due:
                monitor.next_memory=self.clock_ns()/1e9+.5
                try:
                    await self.sample(broker)
                finally:
                    monitor.next_memory=max(monitor.next_memory,self.clock_ns()/1e9+.5)
            return {}
        if self.phase=='GOAL_READY':
            if not due:return {}
            self.submit(broker)
        if self.phase=='WAIT_MOVE':
            result=await self._npc_poll(monitor,reserve=due)
            self.after_poll(broker,result)
            return result
        return {}

    async def _npc_poll(self,monitor,*,reserve):
        need(type(self.runtime) is launcher.ProductFeatures and type(self.runtime)._poll_npc is NPC_POLL_METHOD
             and self.runtime._poll_npc.__self__ is self.runtime and self.runtime._poll_npc.__func__ is NPC_POLL_METHOD,
             'SCENARIO_RESPAWN_MOTION_CANONICAL_NPC_SCHEDULER_REQUIRED')
        result=await self.runtime._poll_npc(monitor,reserve=reserve)
        return dict(npc=result)

    def fail(self,error):
        super().fail(error)
        self.scenario.stage='NPC_RESPAWN_MOTION_UNKNOWN_STOP_REQUESTED'


class Runtime:
    def __init__(self, runtime, scenario, *, next_hit=False, retire=False, second_respawn=False, current_life_hit=False, current_life_retire=False, motion_goal=None):
        need(motion_goal is None or type(motion_goal) is tuple and grid(motion_goal)==motion_goal and motion_goal==(32578,32946)
             and not any((next_hit,retire,second_respawn,current_life_hit,current_life_retire)),
             'SCENARIO_RESPAWN_MOTION_EXPLICIT_MODE_REQUIRED')
        self.motion=RespawnMotion(scenario,runtime,goal=motion_goal) if motion_goal is not None else None
        scenario.respawn_motion=self.motion
        need(type(next_hit) is bool, 'SCENARIO_RESPAWN_HIT_EXPLICIT_BOOL_REQUIRED')
        need(type(retire) is bool and (not retire or next_hit), 'SCENARIO_NPC_RETIRE_EXPLICIT_MODE_REQUIRED')
        need(type(second_respawn) is bool and (not second_respawn or retire),'SCENARIO_SECOND_RESPAWN_EXPLICIT_MODE_REQUIRED')
        need(type(current_life_hit) is bool and (not current_life_hit or second_respawn),'SCENARIO_CURRENT_LIFE_EXPLICIT_MODE_REQUIRED')
        need(type(current_life_retire) is bool and (not current_life_retire or current_life_hit),'SCENARIO_CURRENT_RETIRE_EXPLICIT_MODE_REQUIRED')
        self.current_life_retire=CurrentLifeRetire(scenario,runtime) if current_life_retire else None
        scenario.current_life_retire=self.current_life_retire
        self.current_life_hit=CurrentLifeHit(scenario,runtime,completion=self.current_life_retire.begin if self.current_life_retire is not None else None) if current_life_hit else None
        scenario.current_life_hit=self.current_life_hit
        self.second_respawn = SecondRespawn(scenario,runtime,completion=self.current_life_hit.begin if self.current_life_hit is not None else None) if second_respawn else None
        scenario.second_respawn = self.second_respawn
        self.retire = Retire(scenario, runtime, completion=self.second_respawn.begin if self.second_respawn is not None else None) if retire else None
        self.followup = Followup(scenario, runtime, completion=self.retire.begin if self.retire is not None else None) if next_hit else None
        scenario.respawn_retire = self.retire
        self.original, self.scenario = runtime, scenario
        self.manual = runtime.manual
        self.trial = Trial(scenario, runtime, completion=self.motion.begin if self.motion is not None else self.followup.begin if self.followup is not None else None)
        scenario.respawn_followup = self.followup
        scenario.respawn_trial = self.trial

    async def poll(self, monitor=None):
        trial = self.trial
        if self.scenario.stop.is_set():
            if self.motion is not None and self.motion.phase not in ('WAIT_RESPAWN_COMPLETE','DONE','FAILED'):
                self.motion.fail(ValueError('SCENARIO_RESPAWN_MOTION_CANCELLED'));self.scenario.save()
            elif self.current_life_retire is not None and self.current_life_retire.phase not in ('WAIT_CURRENT_LIFE_HIT_COMPLETE','DONE','FAILED'):
                self.current_life_retire.fail(ValueError('SCENARIO_CURRENT_RETIRE_CANCELLED'));self.scenario.save()
            elif self.current_life_hit is not None and self.current_life_hit.phase not in ('WAIT_SECOND_RESPAWN_COMPLETE','DONE','FAILED'):
                self.current_life_hit.fail(ValueError('SCENARIO_CURRENT_LIFE_CANCELLED'));self.scenario.save()
            elif self.second_respawn is not None and self.second_respawn.phase not in ('WAIT_RETIRE_COMPLETE','DONE','FAILED'):
                self.second_respawn.fail(ValueError('SCENARIO_SECOND_RESPAWN_CANCELLED'))
                self.scenario.save()
            elif self.retire is not None and self.retire.phase not in ('WAIT_FOLLOWUP_COMPLETE','DONE','FAILED'):
                self.retire.fail(ValueError('SCENARIO_NPC_RETIRE_CANCELLED'))
                self.scenario.save()
            elif self.followup is not None and trial.phase == 'DONE' and self.followup.phase not in ('DONE','FAILED'):
                self.followup.fail(ValueError('SCENARIO_RESPAWN_HIT_CANCELLED'))
                self.scenario.save()
            elif trial.phase not in ('WAIT_ATTACK_PREPARATION', 'DONE', 'FAILED'):
                trial.fail(ValueError('SCENARIO_NPC_RESPAWN_CANCELLED'))
                self.scenario.save()
            return {}
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_NPC_RESPAWN_SAME_MONITOR_REQUIRED')
            if self.motion is not None and self.motion.phase!='WAIT_RESPAWN_COMPLETE':
                result=await self.motion.poll(monitor) if self.motion.phase not in ('DONE','FAILED') else {}
                self.scenario.save();return result
            if self.current_life_retire is not None and self.current_life_retire.phase!='WAIT_CURRENT_LIFE_HIT_COMPLETE':
                action=self.current_life_retire
                if action.phase not in ('DONE','FAILED'):
                    action.current()
                    if action.clock_ns()/1e9>=monitor.next_memory:
                        monitor.next_memory=action.clock_ns()/1e9+.5
                        try:
                            await action.step()
                        finally:
                            monitor.next_memory=max(monitor.next_memory,action.clock_ns()/1e9+.5)
                    self.scenario.save()
                return {} # No completed manual/fulltarget reentry after current-life retirement.
            if self.current_life_hit is not None and self.current_life_hit.phase != 'WAIT_SECOND_RESPAWN_COMPLETE':
                if self.current_life_hit.phase=='ARM_READY':await self.current_life_hit.arm()
                result=await self.original.poll(monitor)
                await self.current_life_hit.collect();self.scenario.save()
                return result
            if self.second_respawn is not None and self.second_respawn.phase != 'WAIT_RETIRE_COMPLETE':
                action=self.second_respawn
                if action.phase not in ('DONE','FAILED'):
                    action.current()
                    if action.clock_ns()/1e9 >= monitor.next_memory:
                        api_reserves_slot=action.phase=='RESPAWN_READY'
                        if not api_reserves_slot:monitor.next_memory=action.clock_ns()/1e9+.5
                        try:
                            await action.step()
                        finally:
                            if not api_reserves_slot:monitor.next_memory=max(monitor.next_memory,action.clock_ns()/1e9+.5)
                    self.scenario.save()
                return {} # No completed manual/fulltarget poll after second adoption.
            if self.retire is not None and self.retire.phase != 'WAIT_FOLLOWUP_COMPLETE':
                if self.retire.phase not in ('DONE','FAILED'):
                    self.retire.current()
                    if self.retire.clock_ns()/1e9 >= monitor.next_memory:
                        monitor.next_memory = self.retire.clock_ns()/1e9 + .5
                        try:
                            await self.retire.step()
                        finally:
                            monitor.next_memory = max(monitor.next_memory,self.retire.clock_ns()/1e9+.5)
                    self.scenario.save()
                return {} # Completed manual must not revalidate a removed target.

            if trial.phase not in ('WAIT_ATTACK_PREPARATION', 'DONE', 'FAILED'):
                if trial.phase == 'CHECK_PREPARATION':
                    need(trial.clock_ns() - trial.prepare_started_ns < WAIT_NS,
                         'SCENARIO_NPC_RESPAWN_ORIGINAL_OPERATION_DEADLINE')
                else:
                    trial.current(fresh=trial.phase in ('NEW_REGISTRY', 'NEW_POSE'))
                if trial.clock_ns() / 1e9 >= monitor.next_memory:
                    api_reserves_slot = trial.phase == 'RESPAWN_READY'
                    if not api_reserves_slot:
                        monitor.next_memory = trial.clock_ns() / 1e9 + .5
                    try:
                        await trial.step()
                    finally:
                        if not api_reserves_slot:
                            monitor.next_memory = max(monitor.next_memory, trial.clock_ns() / 1e9 + .5)
                self.scenario.save()
            if trial.phase == 'DEATH_SAMPLE':
                return {} # Only a fresh proof-bound query may finish this preparation.
            if self.scenario.stop.is_set():
                return {}
            if self.motion is not None and self.motion.phase!='WAIT_RESPAWN_COMPLETE':
                return {} # Fresh motion tail never polls the completed manual, including handoff.
            if self.followup is not None and self.followup.phase == 'ARM_READY':
                await self.followup.arm()
            result = await self.original.poll(monitor)
            if self.followup is not None:
                await self.followup.collect()
                self.scenario.save()
            return result
        except asyncio.CancelledError:
            self._failure_target().fail(
                ValueError('SCENARIO_NPC_RESPAWN_CANCELLED'))
            self.scenario.save()
            raise
        except Exception as error:
            self._failure_target().fail(error)
            self.scenario.save()
            return {}

    def _failure_target(self):
        if self.motion is not None and (self.motion.phase!='WAIT_RESPAWN_COMPLETE' or self.trial.phase=='DONE'):
            return self.motion
        if self.current_life_retire is not None and (self.current_life_retire.phase!='WAIT_CURRENT_LIFE_HIT_COMPLETE'
                or self.current_life_hit.phase=='DONE'):
            return self.current_life_retire
        if self.current_life_hit is not None and (self.current_life_hit.phase != 'WAIT_SECOND_RESPAWN_COMPLETE'
                or self.second_respawn.phase=='DONE'):
            return self.current_life_hit
        if self.second_respawn is not None and (self.second_respawn.phase != 'WAIT_RETIRE_COMPLETE'
                or self.retire.phase == 'DONE'):
            return self.second_respawn
        if self.retire is not None and self.retire.phase != 'WAIT_FOLLOWUP_COMPLETE':
            return self.retire
        return self.followup if self.followup is not None and self.trial.phase == 'DONE' else self.trial

    def close(self):
        try:
            self.original.close()
        finally:
            try:
                captured=False
                if self.current_life_hit is not None and self.current_life_hit.phase!='WAIT_SECOND_RESPAWN_COMPLETE':
                    captured=self.current_life_hit.capture_terminal_result()
                elif self.followup is not None:
                    captured=self.followup.capture_terminal_result()
                if captured:self.scenario.save()
            except Exception:
                pass  # Optional output must not replace the original close failure.
