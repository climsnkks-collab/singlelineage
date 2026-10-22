"""Explicit local current-target retaliation over the original feature monitor.

Accepted/drained server input issues a persistent target. Original current-owner
APIs drive source-bound action cadence and HP/death; input diagnostics remain
separate. The L1J reference policy does not establish official template mapping.
"""
from dataclasses import dataclass
import asyncio
import time
from tools.local_original_session import feature_config as fc, npc_player_hit, npc_session
from tools.local_original_session import npc_respawn_focused as original

need = fc.need
PROFILE = 'sibling-background-npc-continuous-retaliation-spawn'
WAIT_NS = original.WAIT_NS
NATIVE_SHA = '18164426c1b9397c8e4216ad083842dbf2ed7a662acfa49bde39fbec2f2e0e80'

from tools.local_original_session import continuous_policy, npc_continuous_retaliation
Binding=continuous_policy.Binding
load_binding=continuous_policy.load_binding

def configuration(config, *, inventory=None, auto_inventory=None):
    from tools.local_original_session import npc_hp, npc, npc_death, npc_respawn, npc_motion, hp_status, player_life, movement
    from tools.local_original_session import inventory as inv, inventory_store, restart, attack_session
    from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap
    need(type(config) is fc.Features and len(config.spawns) == 2,
         'RESPAWN_HIT_EXACT_TYPED_CONFIG_REQUIRED')
    spawn, second = config.spawns
    fresh = config.npc_respawn_spawn
    need(type(spawn) is npc.NpcSpawn and type(fresh) is npc.NpcSpawn and fresh is not spawn
         and (spawn.uid,spawn.map_id,spawn.fields[3],spawn.fields[39],spawn.fields[1]) == (2,0,56,0,2159181633)
         and (fresh.map_id,fresh.policy,dict(fresh.fields)) == (spawn.map_id,spawn.policy,dict(spawn.fields))
         and type(config.attack_hp_provider) is npc_hp.ExplicitInputs,
         'RESPAWN_HIT_ORIGINAL217_RECIPE_REQUIRED')
    need(type(second) is npc.NpcSpawn and second.uid == 3 and second.map_id == spawn.map_id
         and second.policy == spawn.policy
         and dict(second.fields) == dict(spawn.fields) | {2:3,
             1:movement.authority.pack_grid(
                 movement.authority.unpack_grid(spawn.fields[1])[0]+1,
                 movement.authority.unpack_grid(spawn.fields[1])[1])}
         and len(config.attack_hp_provider.rows) == 2,
         'TWO_ENEMY_EXPLICIT_SECOND_RECIPE_REQUIRED')
    first_row, second_row = config.attack_hp_provider.rows
    need(tuple(row.target for row in (first_row,second_row)) ==
             (npc_hp.Target(2,0,56,0),npc_hp.Target(3,0,56,0))
         and all(row.hp == npc_hp.Hp(2,2) and row.hit == npc_hp.Hit(True,1)
                 for row in (first_row,second_row)) and config.attack_policy == fc.ATTACK_INTENT_POLICY
         and type(config.attack_feedback) is attack_session.FeedbackConfig
         and config.npc_death_policy == npc_death.DEATH_POLICY
         and config.npc_remove_policy == npc_death.REMOVE_POLICY
         and config.npc_respawn_policy == npc_respawn.POLICY
         and config.interval_ns == 800000000 and config.motion_policy == npc_motion.LOCAL_PRE_STEP
         and config.goal_policy == npc_session.AXIS_SIGN_GOAL and config.goal is None,
         'RESPAWN_HIT_ORIGINAL217_LIFECYCLE_REQUIRED')
    need(config.npc_player_hit_repeated_policy == npc_player_hit.REPEATED_POLICY
         and type(config.npc_player_hit_repeated_input) is fc.NpcPlayerHitInput
         and config.npc_player_hit_repeated_input == fc.NpcPlayerHitInput(1,8,True)
         and config.hp_status_policy == hp_status.POLICY and config.hp_status_input is None
         and type(config.player_life_policy) is player_life.Policy
         and config.player_life_policy is config.canonical_bootstrap._continuous_binding.life_policy
         and config.npc_player_lethal_recovery_input is None
         and config.npc_player_hit_policy is config.npc_player_hit_input is None
         and config.npc_approach_hit_policy is config.npc_approach_hit_input is None,
         'RESPAWN_HIT_POSITIVE_POLICY_ONLY_REQUIRED')
    selected = config.canonical_bootstrap
    need(type(selected) is CanonicalFeatureBootstrap and selected.resource_only
         and selected.shop is selected.trade is None and not selected._retired
         and selected._hp_consumer_sources is not None
         and config.inventory_policy == inv.POLICY
         and config.inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
         and config.inventory_collection_policy == inv.COLLECTION_POLICY
         and config.inventory_collection_grant == (inventory_store.SECOND_INSTANCE_POLICY,frozenset())
         and config.inventory_reselection_policy == fc.LOCAL_SAVED_ROW_ON_RESELECTION
         and config.inventory_delivery_policy == fc.LOCAL_WORLD_READY_ONCE
         and config.inventory_missing_row_policy is None and config.restart_policy == restart.POLICY
         and config.item_use_policy is config.item_equipment_policy is None
         and (inventory is None or inventory is True) and (auto_inventory is None or auto_inventory is True),
         'RESPAWN_HIT_CANONICAL_SOURCE_OWNER_REQUIRED')
    need(type(getattr(selected,'_continuous_binding',None)) is Binding,
         'RETALIATION_DEFAULT_OFF_EXPLICIT_INPUT_REQUIRED')
    from tools.local_original_session import player_life
    need(tuple(p.check() for p in selected._hp_consumer_sources)==(npc_player_hit,player_life,npc_session)
         and config.inventory_custody_policy is config.item_transfer_policy is None
         and config.item_equipment_first_enable is False,
         'RESPAWN_HIT_EXACT_CONSUMER_NAMESPACE_REQUIRED')
    inv.validate_frame(config.inventory_frame)
    return config


def configure_factory(factory, *, reader, product, control_mode, directory, config, flags):
    from tools.local_original_session import launcher, observe
    configuration(config)
    selected = config.canonical_bootstrap
    need(type(factory) is launcher.ProductFeatureFactory and product == PROFILE and control_mode == 'manual'
         and type(reader) is observe.RetainedSceneReader
         and all(type(flag) is bool and flag is False for flag in flags)
         and selected._factory is None and selected._lifetime_state == 'READY',
         'RESPAWN_HIT_SINGLE_COLD_FACTORY_REQUIRED')
    descriptor = launcher.PRODUCTS[product]
    need(descriptor.get('npc_continuous_retaliation') is True
         and descriptor['bridges']['own-login-bridge-dg49.dll'] == NATIVE_SHA
         and descriptor['bridge_artifact'] == launcher.ROOT / 'work/local_original_session/integration-1/item-reference-repeat-native-composite-v1/native/own-login-bridge-dg49.dll'
         and descriptor.get('continuous_manual_attack') is True
         and descriptor.get('manual_attack_move_replacement') is False,
         'RESPAWN_HIT_EXACT_NATIVE181_DESCRIPTOR_REQUIRED')
    factory.reader,factory.directory,factory.config,factory.product = reader,directory,config,product
    factory.manual = factory.inventory = factory.allow_attack = True
    factory.lethal_attack_preparation = False
    # These existing launcher flags remain exact False; no old profile predicate
    # is weakened to admit this explicitly named composition.
    for name in ('zero_use_reselect','_zero_use_reselect_bound','zero_use_profile','swap_reselect',
                 'swap_saved_b_tail','_swap_saved_b_tail_bound','item_transfer_ui','allow_use_item',
                 'allow_attack_replacement','allow_respawn_attack','npc_hp_feedback_only',
                 'reselect_equipment_restore','normal_open_use_current_ui','allow_inventory_ui_open',
                 'ui_inventory_update_only'):
        setattr(factory,name,False)
    factory.hp_status_enabled = factory.npc_player_hit_repeated_enabled = True
    factory.npc_factory = npc_session.NpcSessionFactory(reader,config=npc_session.NpcSessionConfig(
        spawns=config.spawns,interval_ns=config.interval_ns,policy=config.motion_policy,
        goal_policy=config.goal_policy,respawn_policy=config.npc_respawn_policy))
    selected._factory,selected._config = factory,config
    selected.factory_current(factory)


def build_runtime(factory, broker):
    from tools.local_original_session import launcher, manual_move_commands as commands
    from tools.local_original_session.repeated_player_life_focused import require_owner_binding
    config=configuration(factory.config); selected=config.canonical_bootstrap
    selected.factory_current(factory)
    owner=require_owner_binding(broker)
    need(factory.product == PROFILE and selected._broker is broker and selected._owner is owner,
         'RESPAWN_HIT_ATTACHED_CANONICAL_OWNER_REQUIRED')
    session=factory.npc_factory._session
    need(type(session) is npc_session.NpcSession and session.broker is broker and not session._closed,
         'RESPAWN_HIT_ORIGINAL_BOUND_SESSION_REQUIRED')
    manual=None
    try:
        consumer=commands.ManualMoveCommands(factory.reader,current=lambda:launcher.current_manual_binding(broker),
            allow_attack=True,allow_attack_replacement=False,observe_attack_feedback=True,
            lethal_attack_preparation=False, attack_completion='CONTINUOUS_DRAINED_INTENT',
            allow_source_restart=True,continuous_target_release=True)
        manual=launcher.ManualMoveRequests(factory.directory,consumer,allow_attack=True,allow_move=False,allow_source_restart=True,
            inventory_broker=broker,inventory_delivery_policy=config.inventory_delivery_policy,
            inventory_reselection_policy=config.inventory_reselection_policy,lethal_attack_preparation=False)
        runtime=launcher.ProductFeatures(manual,session,npc_respawn_policy=config.npc_respawn_policy,
            npc_respawn_spawn=config.npc_respawn_spawn)
        from tools.local_original_session import player_life_observe
        need(broker._player_life_observer is None,'CONTINUOUS_COLD_LIFE_OBSERVER_REQUIRED')
        observer=player_life_observe.PlayerLifeObserver(broker,factory.reader)
        runtime.player_life_observer=observer
        selected.factory_current(factory);require_owner_binding(broker,expected=owner)
        broker._player_life_observer=observer
        return runtime
    except BaseException:
        if manual is not None:manual.close()
        raise


def scenario_type(base):
    # Reuse genuine inventory2rows and normal attack request/collect callers.
    from tools.local_original_session import npc_retaliation_runtime as checkpoint, launcher
    from tools.local_original_session.run_manual_baseline_scenario import _atomic
    parent=checkpoint.scenario_type(base)
    class ContinuousScenario(parent):
        configuration=staticmethod(configuration)
        source_quit_profile=PROFILE
        RESTART_SEQUENCE=4
        summary_byte_limit=16384
        def __init__(self,*args,**kwargs):
            self.enemy_index=0;self.engagements=[]
            self.two_enemy=dict(status='PENDING',order=[2,3],engagements=self.engagements)
            self.input_diagnostic=None
            self.target_release=dict(status='NOT_REQUESTED',proof_scope='UNKNOWN')
            self.source_restart=dict(status='NOT_REQUESTED',proof_scope='UNKNOWN',ui='UNKNOWN',inventory_restore='UNKNOWN')
            self.restart_manual=self.restart_refs=self.restart_started=self.restart_events=None
            self.follow=dict(status='NOT_REQUESTED',client_pose='UNKNOWN',render='UNKNOWN')
            super().__init__(*args,**kwargs)
            self.expected_move_count=0
            self.path=self.monitor.directory/'manual-npc-continuous-retaliation-scenario.json'
        def summary(self):
            result=super().summary()
            result['npc_continuous_retaliation']=(dict(status='NOT_REQUESTED') if self.target_runtime is None
                                                 else dict(self.target_runtime.result))
            # Parent and continuous names held the same live result twice.
            # Keep the feature's current result under its actual consumer key.
            result.pop('npc_retaliation',None)
            diagnostic=self.input_diagnostic
            result['npc_two_enemy']=dict(self.two_enemy)
            result['npc_target_release']=dict(self.target_release)
            result['input_diagnostic']=(None if diagnostic is None else
                {key:diagnostic[key] for key in ('status','reason','phase','command','sequence',
                    'native_attempted','cleanup_required','automatic_retry','last_sequence') if key in diagnostic})
            # Detailed action snapshots already have their own existing file.
            return result
        def require_attack_feedback(self,result):
            # Each ordered continuous input completes at the real accepted/drained
            # response. Read-only action samples do not prove or gate its intent.
            runtime = self.target_runtime
            need(type(runtime) is Runtime and runtime.scenario is self
                 and runtime.manual.consumer._attack_completion_mode == 'CONTINUOUS_DRAINED_INTENT'
                 and runtime.manual.consumer.pending is None
                 and runtime.manual.last_result == result
                 and result.get('status') == 'COMMITTED'
                 and result.get('proof_scope') == 'VALIDATED_ATTACK_INTENT_ONLY'
                 and result.get('observation_scope') == 'VALIDATED_DRAINED_INPUT_ONLY'
                 and result.get('native_attempted') is True,
                 'CONTINUOUS_DRAINED_INPUT_COMPLETION_REQUIRED')
            self.capture_attack_transport()
            session = self.attack_session
            target = runtime.controller.target
            need(type(target) is npc_continuous_retaliation.TargetReceipt
                 and target.issuer is runtime.controller and target.runtime is runtime
                 and target.scenario is self and session is runtime.controller.combat
                 and any(issued is target for issued in runtime.controller._issued)
                 and target.intent is session.current_intent() is session._feedback_intent
                 and target.intent.accepted_ordinal == session.accepted_count
                 and target.feedback is session._feedback_frame
                 and session._feedback_state == 'DRAINED'
                 and self.attack['feedback']['state'] == 'DRAINED'
                 and all(self.attack['feedback'][key] == self.enemy_index+1 for key in
                         ('prepared','reserved','write_attempted','drained')),
                 'CONTINUOUS_DRAINED_INPUT_TARGET_REQUIRED')
        def current(self,row,broker,**kwargs):
            if self.stage in ('FOLLOW_MOVE_READY','MOVE_READY','MOVE_WAIT','MOVE_PROVEN',
                              'FOLLOW_ARRIVAL_WAIT','FOLLOW_HIT_WAIT'):
                from tools.local_original_session.run_manual_baseline_scenario import ContinuousMoveScenario
                return ContinuousMoveScenario.current(self,row,broker,require_idle=True)
            return super().current(row,broker,**kwargs)
        def choose_move_candidate(self,choices):
            from tools.local_original_session import movement
            controller=self.target_runtime.controller
            target=controller.target
            need(target is self.target_runtime._follow_target and target is not None,
                 'FOLLOW_SAME_TARGET_REQUIRED')
            npc_grid=movement.authority.unpack_grid(target.mover.state.packed)
            selected=[item for item in choices if max(abs(a-b) for a,b in
                zip(item['grid_target'],npc_grid))>1]
            need(bool(selected),'FOLLOW_NO_CURRENT_CLEAR_OUT_OF_RANGE_EDGE')
            return selected[0]
        def collect_attack(self,row,broker):
            from tools.local_original_session.run_manual_baseline_scenario import AttackTargetScenario
            AttackTargetScenario.collect_attack(self,row,broker)
            if self.attack['status']=='COMMITTED':self.stage='CONTINUOUS_TARGET_ACTIVE'

        def submit_attack(self, row, broker):
            from tools.local_original_session import attack, attack_session, commands
            service, position, _proof, known = self.current(row, broker)
            if not known:
                return
            spawn = self.features.spawns[self.enemy_index]
            actual = broker.realm._npc_spawns
            from tools.local_original_session import npc_edge
            npc = self.target_runtime.original.npc_session
            need(type(npc) is npc_session.NpcSession and npc.broker is broker,
                 'SCENARIO_SAME_STATIONARY_NPC_TARGET_REQUIRED')
            need(len(actual) == 2 and [item[0].uid for item in actual] == [2,3]
                 and any(item[0] is spawn for item in actual)
                 and spawn.uid != position.uid and spawn.map_id == position.map_id,
                 'TWO_ENEMY_PUBLISHED_REQUEST_UID_REQUIRED')
            controller=self.target_runtime.controller
            need(controller.lease is controller.operation is controller.motion_lease is controller.motion_step is None
                 and controller.lethal is None,
                 'TWO_ENEMY_PREVIOUS_OPERATION_NOT_SETTLED')
            session = broker._attack_session
            need(type(session) is attack_session.AttackSession and broker.realm._attack_session is session
                 and session.policy == self.features.attack_policy and not session.closed and not session.fatal
                 and session.feedback == self.features.attack_feedback
                 and session.accepted_count == self.enemy_index
                 and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0),
                 'SCENARIO_CURRENT_FRESH_ATTACK_SESSION_REQUIRED')
            self.attack_session, self.attack_before = session, session.accepted_count
            self.attack_projection = attack.AttackTargets._project(session.targets, self.move_bound[0],
                                                                  attack.AttackRequest(spawn.uid))
            self.attack_counters=(service.requests_received,service.committed,service.corrections_prepared)
            self.attack_events = broker.policy.events
            if self.features.attack_feedback is not None:
                self.capture_attack_transport()
                need(self.attack['feedback']['state'] == ('NOT_REQUESTED' if self.enemy_index == 0 else 'DRAINED')
                     and all(self.attack['feedback'][key] == self.enemy_index
                             for key in ('prepared', 'reserved', 'write_attempted', 'drained')),
                     'SCENARIO_FRESH_ATTACK_FEEDBACK_REQUIRED')
            if self.origin is None:
                self.origin, self.land_since = position.metadata(), self.clock()
                self.idle_last_good = self.land_since
                self.idle_reason = 'CONSUMER_TYPED_ADMISSION_SEPARATE_FROM_SCENARIO_WORLD'
                self.move_event_start = broker.policy.events
            need(position.metadata() == self.origin, 'SCENARIO_ATTACK_AUTHORITY_CHANGED')
            request = dict(schema=commands.REQUEST_SCHEMA, sequence=self.ATTACK_SEQUENCE, command='AttackTarget',
                           uid=position.uid, target_uid=spawn.uid, map_id=position.map_id)
            self.attack.update(status='CLAIMED_NO_RETRY', sequence=self.ATTACK_SEQUENCE, uid=position.uid,
                               target_uid=spawn.uid, map_id=position.map_id)
            if self.enemy_index:self.target_runtime._quit_input=None
            self.stage, self.attack_started = 'ATTACK_WAIT', self.clock()
            self.save()
            _atomic(self.monitor.directory / 'command.request.json', request, 1024)
            self.attack['status'] = 'PUBLISHED'

        def finish_restart(self):
            self.target_runtime.finish_target_release()
            self.stage='TARGET_RELEASE_COMPLETE_STOP_REQUESTED';self.stop.set()

        def tick(self,row,broker,state):
            if state=='CLOSING':return self.confirm_close(row,broker)
            if self.stage in ('TARGET_RELEASE_READY','RESTART_WAIT'):
                if state!='RUNNING' or self.stop.is_set():return
                try:
                    self.reader.validate();self.background_desktop()
                    need(self.owner.validate(self.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
                    fresh=self.monitor.samples!=self.last_sample;self.last_sample=self.monitor.samples
                    from tools.local_original_session.run_manual_baseline_scenario import SourceRestartScenario
                    if self.stage=='TARGET_RELEASE_READY' and fresh:
                        SourceRestartScenario.submit_restart(self,row,broker)
                    elif self.stage=='RESTART_WAIT':
                        SourceRestartScenario.collect_restart(self,broker)
                    self.save()
                except Exception as error:
                    self.error=launcher.safe_error_code(error) or type(error).__name__
                    self.target_release.update(status='UNKNOWN',reason=self.error)
                    self.stage='TARGET_RELEASE_UNKNOWN_STOP_REQUESTED';self.stop.set();self.save()
                return
            if self.stage in ('FOLLOW_MOVE_READY','MOVE_WAIT','MOVE_PROVEN',
                              'FOLLOW_ARRIVAL_WAIT','FOLLOW_HIT_WAIT'):
                if state!='RUNNING' or self.stop.is_set():return
                try:
                    self.reader.validate();self.background_desktop()
                    need(self.owner.validate(self.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
                    fresh=self.monitor.samples!=self.last_sample;self.last_sample=self.monitor.samples
                    from tools.local_original_session.run_manual_baseline_scenario import ContinuousMoveScenario
                    if self.stage=='FOLLOW_MOVE_READY' and fresh:
                        ContinuousMoveScenario.submit(self,row,broker)
                    elif self.stage=='MOVE_WAIT':
                        ContinuousMoveScenario.collect(self,row,broker)
                    self.save()
                except Exception as error:
                    self.error=launcher.safe_error_code(error) or type(error).__name__
                    self.follow.update(status='UNKNOWN',reason=self.error)
                    self.stage='FOLLOW_UNKNOWN_STOP_REQUESTED';self.stop.set();self.save()
                return
            if self.stage=='CONTINUOUS_TARGET_ACTIVE':return
            if self.stage!='ATTACK_WAIT':return super().tick(row,broker,state)
            if state!='RUNNING' or self.stop.is_set():return
            collecting=False
            try:
                self.reader.validate();self.background_desktop()
                need(self.owner.validate(self.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
                collecting=True
                self.collect_attack(row,broker)
                if self.attack['status']=='COMMITTED':self.stage='CONTINUOUS_TARGET_ACTIVE'
            except Exception as error:
                # Diagnostic failure never becomes server authority. The target
                # was already issued by accepted HPcommit + original drain;
                # Runtime independently revalidates it before every effect.
                manual=self.target_runtime.manual
                state=manual.last_result
                if collecting and self.target_runtime.input_diagnostic_current(error):
                    self.input_diagnostic=dict(state)
                    self.attack.update(status='UNKNOWN',consumer_status='UNKNOWN',reason=state['reason'])
                    self.stage='CONTINUOUS_TARGET_ACTIVE'
                else:
                    self.error=launcher.safe_error_code(error) or type(error).__name__
                    self.stage='ATTACK_UNKNOWN_STOP_REQUESTED';self.stop.set()
            self.save()
    return ContinuousScenario




@dataclass(frozen=True, slots=True)
class _InputClaim:
    runtime: object
    manual: object
    consumer: object
    pending: object
    request: object
    request_data: tuple
    target: object
    public_sequence: int
    native_sequence: int
    started_ns: int
    identities: tuple
    current: tuple
    bound: object
    native_data: object
    native_identity: object


class Runtime:
    def __init__(self,original,scenario):
        from tools.local_original_session import launcher
        need(type(original) is launcher.ProductFeatures,'CONTINUOUS_ORIGINAL_PRODUCT_RUNTIME_REQUIRED')
        self.original,self.scenario,self.manual=original,scenario,original.manual
        from tools.local_original_session.run_manual_baseline_scenario import NpcHpFeedbackOnlyScenario
        NpcHpFeedbackOnlyScenario.bind_runtime(scenario,original)
        self.broker=original.npc_session.broker
        config=configuration(scenario.features)
        scenario.target_runtime=self
        self.controller=npc_continuous_retaliation.Controller(original,binding=config.canonical_bootstrap._continuous_binding,
            runtime=self,scenario=scenario)
        self.closed=False;self._polling=False;self._settled_input=None;self._quit_input=None
        self._release_target=self._release_state=self._release_life_record=None
        self._release_effect_count=None
        self._release_pending=self._release_public=self._release_restart_state=None
        self._enemy_target=None;self._enemy_pose=None;self._enemy_effect_baseline=None
        self._enemy_completed=[]
        scenario.restart_manual=self.manual
        self._follow_target=None;self._follow_initial_state=None
        self._follow_move_pending=self._follow_move_public=self._follow_after_move=None
        self._follow_pose_state=None;self._follow_hit_baseline=None
        self._follow_move_claims=();self._follow_consumed_move=None
        self._follow_first_step=self._follow_first_goal=self._follow_initial_position=None
        self.result=dict(status='NOT_REQUESTED',overall='PENDING',input_consumer={},official_mapping='UNKNOWN')
        scenario.target_runtime=self

    def _input_claim(self):
        # Read the original producer's stored claim only. No query, clock,
        # Native read/retry, command publication or new server authority.
        from tools.local_original_session import launcher,manual_move_commands as commands
        m=self.manual;c=m.consumer;p=c.pending;t=self.controller.target
        if (type(m) is not launcher.ManualMoveRequests
            or m._actual_manual_producer(asynchronous=True) is not c
            or type(p) is not dict or p.get('kind')!='AttackTarget'
            or p.get('phase')!='NATIVE_WAIT' or type(p.get('request')) is not dict
            or p.get('native_attempted') is not True or m._pending_command!='AttackTarget'
            or not m.pending or m.closed):return None
        current=c._attack_current() # Original source-issued current, before terminal cleanup.
        need(c.pending is p and not m.closed, 'CONTINUOUS_INPUT_CAPTURE_CHANGED')
        request=p['request']
        # A pending B request can precede its accepted/drained target receipt.
        # Preserve only the current receipt for this exact requested UID; an
        # existing A receipt supplies no authority for the B producer claim.
        captured=(t if type(t) is npc_continuous_retaliation.TargetReceipt
                  and t.target_uid==request.get('target_uid') else None)
        return _InputClaim(self,m,c,p,request,tuple(sorted(request.items())),captured,m.sequence,c.sequence,p['started'],
            (m._manual_producer,c.reader,c.reader.owner,c.reader.member,c.current,c.clock_ns,
             self.broker.source_guard,p['attack_session'],p['attack_targets'],p['initial']),
            current,c._bound,None if p['native'] is None else tuple(sorted(p['native'].items())),p['result_identity'])

    def _input_terminal_refs(self, claim, state, target):
        from tools.local_original_session import launcher,manual_move_commands as commands
        from tools.local_original_session import npc_continuous_retaliation as continuous
        need(type(claim) is _InputClaim and claim.runtime is self and not self.closed
             and claim.manual is self.manual and claim.consumer is self.manual.consumer
             and type(self.manual) is launcher.ManualMoveRequests
             and self.manual._actual_manual_producer(asynchronous=True) is claim.consumer,
             'CONTINUOUS_EXACT_INPUT_PRODUCER_REQUIRED')
        m,c,p,t=claim.manual,claim.consumer,claim.pending,target
        need((claim.target is None or claim.target is t)
             and type(t) is continuous.TargetReceipt and t is self.controller.target and t.runtime is self
             and t.scenario is self.scenario and t.issuer is self.controller
             and self.scenario.target_runtime is self and not self.scenario.stop.is_set()
             and self.broker._npc_continuous is self.controller and not self.controller.closed
             and not self.broker._closing and not self.broker.failure.is_set()
             and not t.row['failed'] and not t.row['joined']
             and c.pending is p and p.get('kind')=='AttackTarget' and p.get('phase')=='NATIVE_WAIT'
             and p.get('native_attempted') is True and p.get('request') is claim.request
             and tuple(sorted(claim.request.items()))==claim.request_data
             and c._bound is claim.bound and claim.current[5] == claim.bound[1]
             and m._pending_command=='AttackTarget' and m.pending
             and m.sequence==claim.public_sequence and c.sequence==claim.native_sequence
             and state is m.last_result and state.get('sequence')==claim.public_sequence
             and state.get('command')=='AttackTarget' and state.get('phase')=='NATIVE_WAIT'
             and state.get('status')=='UNKNOWN' and state.get('cleanup_required') is True
             and state.get('native_attempted') is True,
             'CONTINUOUS_EXACT_INPUT_CLAIM_REQUIRED')
        need(all(a is b for a,b in zip(claim.identities,
            (m._manual_producer,c.reader,c.reader.owner,c.reader.member,c.current,c.clock_ns,
             self.broker.source_guard,p['attack_session'],p['attack_targets'],p['initial'])))
             and p['attack_session'] is self.controller.combat
             and p['attack_targets'] is self.controller.combat.targets
             and t.intent.accepted_ordinal==p['attack_before']+1
             and t.intent._bound.attacker is p['initial']
             and t.intent._bound._writer is t.writer
             and t.intent._bound._authority is p['attack_targets']
             and type(claim.started_ns) is int and p['started']==claim.started_ns
             and claim.started_ns<=t.issued_ns<claim.started_ns+commands.WAIT_NS,
             'CONTINUOUS_PREDEADLINE_ACCEPTED_INPUT_REQUIRED')
        request=dict(claim.request_data);native=p.get('native')
        need(request.get('schema')=='own-attack-target-request-v1'
             and request.get('command')=='AttackTarget' and request.get('seq')==claim.native_sequence
             and (request.get('player_uid'),request.get('target_uid'),request.get('map_id'))
                 ==(p['initial'].uid,t.intent._bound.target_uid,p['initial'].map_id)
             and type(native) is dict
             and native==dict(request,schema='own-attack-target-result-v1',status='RETURNED',reason=0,invoked=True)
             and type(native.get('reason')) is int and native['invoked'] is True
             and type(p.get('result_identity')) is tuple and len(p['result_identity'])==4
             and all(type(v) is int for v in p['result_identity']) and p['result_identity'][2]>0,
             'CONTINUOUS_SETTLED_NATIVE_INPUT_REQUIRED')
        need(m.closed and m._resources_closed and not m._polling and not c._busy
             and c._readonly_pending is None and c._reservation is True
             and c._action_sequence is None and c._action_bound is None
             and c.state.get('status')=='UNKNOWN' and c.state.get('cleanup_required') is True
             and self.controller.inventory_owner.command_closed,
             'CONTINUOUS_INPUT_CLEANUP_REQUIRED')
        reason=state.get('reason')
        need(reason in ('MANUAL_ATTACK_ACTION_SNAPSHOT_UNKNOWN','MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE'),
             'CONTINUOUS_INPUT_DIAGNOSTIC_REASON_REQUIRED')
        if reason=='MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE':
            need(claim.native_data is not None and tuple(sorted(p['native'].items()))==claim.native_data
                 and p['result_identity']==claim.native_identity
                 and type(c._now) is int and c._now>=claim.started_ns+commands.WAIT_NS,
                 'CONTINUOUS_ORIGINAL_INPUT_DEADLINE_REQUIRED')
        self.controller.inventory_owner.require_current()
        return claim

    async def _consume_input_terminal(self,error,claim):
        need(type(error) is ValueError and str(error)=='MANUAL_MOVE_TERMINAL_UNKNOWN',
             'CONTINUOUS_ORIGINAL_INPUT_TERMINAL_REQUIRED')
        state=self.manual.last_result;t=self.controller.target
        self._input_terminal_refs(claim,state,t)
        async with self.broker._row_operation(t.writer,t.row):
            await self.broker._checkpoint(t.writer,t.row)
            self.controller.current_locked(t)
            # Reuse the original immutable file/schema/identity consumer with
            # its retained source-issued tuple. No terminal current is revived.
            from tools.local_original_session import manual_move_commands as commands
            commands.ManualMoveCommands._attack_result(claim.consumer,claim.current,_pending=claim.pending)
            self._input_terminal_refs(claim,state,t)
            self.controller._pure_current(t)
        # This is only a settled command diagnostic. The pre-issued target,
        # fresh owner, policy cadence and per-effect authority stay independent.
        self._settled_input=(claim,state,t)
        self.scenario.input_diagnostic=dict(state)
        self.scenario.attack.update(status='UNKNOWN',consumer_status='UNKNOWN',reason=state['reason'])
        self.scenario.stage='CONTINUOUS_TARGET_ACTIVE'
        return dict(manual_move=dict(state))

    def input_diagnostic_current(self,error):
        if (type(error) is not ValueError or str(error) not in
            ('MANUAL_MOVE_TERMINAL_UNKNOWN','SCENARIO_ATTACK_CONSUMER_REFUSED','SCENARIO_STRICT_CONSUMER_REFUSED')
            or self._settled_input is None):return False
        claim,state,target=self._settled_input
        self._input_terminal_refs(claim,state,target)
        return True

    def _remember_quit_input(self, claim, phase):
        """Keep the source-issued Native return across successful/terminal command retirement."""
        if type(claim) is not _InputClaim or self._quit_input is not None or phase not in ('COMMITTED','TERMINAL'):
            return False
        manual, consumer, pending = self.manual, self.manual.consumer, claim.pending
        state, request = manual.last_result, claim.request
        native = pending.get('native') if type(pending) is dict else None
        identity = pending.get('result_identity') if type(pending) is dict else None
        if (claim.runtime is not self or claim.manual is not manual or claim.consumer is not consumer
                or type(pending) is not dict or type(request) is not dict
                or pending.get('request') is not request
                or tuple(sorted(request.items())) != claim.request_data
                or claim.public_sequence != manual.sequence or claim.native_sequence != consumer.sequence
                or claim.bound is not consumer._bound or consumer._reservation is not True
                or type(native) is not dict
                or native != dict(request, schema='own-attack-target-result-v1',
                                  status='RETURNED', reason=0, invoked=True)
                or type(identity) is not tuple or len(identity) != 4
                or not all(type(value) is int for value in identity) or identity[2] <= 0
                or type(state) is not dict or state.get('command') != 'AttackTarget'
                or state.get('sequence') != claim.public_sequence
                or state.get('native_attempted') is not True):
            return False
        if phase == 'COMMITTED':
            if (state.get('status') != 'COMMITTED' or state.get('cleanup_required') is not False
                    or consumer.state.get('status') != 'COMMITTED' or consumer.pending is not None
                    or manual.pending is not False or manual._pending_command is not None
                    or manual.closed or manual._resources_closed):
                return False
        elif (state.get('status') != 'UNKNOWN' or state.get('cleanup_required') is not True
                or consumer.state.get('status') != 'UNKNOWN' or consumer.pending is not pending
                or manual.pending is not True or manual._pending_command != 'AttackTarget'
                or not manual.closed or not manual._resources_closed or manual._polling
                or not self.controller.inventory_owner.command_closed
                or consumer._action_sequence is not None or consumer._action_bound is not None):
            return False
        public = tuple((key,state.get(key)) for key in
            ('status','reason','phase','command','sequence','native_attempted','cleanup_required'))
        self._quit_input = (phase,claim,state,public,native,dict(native),identity)
        return True

    async def _follow_progress(self,monitor):
        """Observe each real requested target, its own pose and a fresh typed counter."""
        from tools.local_original_session import movement,npc_observe,npc_player_hit
        scenario=self.scenario;controller=self.controller
        if scenario.stop.is_set() or self._release_target is not None:return
        if scenario.attack.get('status')!='COMMITTED':return
        target=controller.target;uid=(2,3)[scenario.enemy_index]
        need(type(target) is npc_continuous_retaliation.TargetReceipt and target.target_uid==uid
             and target.hp_result.target.uid==uid and target.mover.state.uid==uid,
             'TWO_ENEMY_CURRENT_REQUEST_ATTRIBUTION_REQUIRED')
        if self._enemy_target is None:
            if scenario.enemy_index:
                old,old_state,old_hp=self._enemy_completed[0]
                need(target is not old and target.serial==old.serial+1
                     and target.generation is not old.generation and target.mover is not old.mover
                     and old.mover.state is old_state
                     and controller.combat._hp._entries[(id(old.writer),2)].hp==old_hp
                     and controller.lease is controller.operation is controller.motion_lease is controller.motion_step is None
                     and controller._owned_goal is None,
                     'TWO_ENEMY_OLD_TARGET_RETIRED_BEFORE_NEW_REQUIRED')
            self._enemy_target=target
        need(target is self._enemy_target,'TWO_ENEMY_TARGET_CHANGED')
        if self._enemy_pose is None:
            now=time.monotonic_ns()
            if now/1e9<monitor.next_memory:return
            observer=self.manual.consumer._attack_observer
            need(type(observer) is npc_observe.NpcObserver,'TWO_ENEMY_ORIGINAL_OBSERVER_REQUIRED')
            async with self.broker._row_operation(target.writer,target.row):
                await self.broker._checkpoint(target.writer,target.row)
                before,position,mover,_,_=controller.current_locked(target)
                state=mover.state;grid=movement.authority.unpack_grid(state.packed)
                monitor.next_memory=max(monitor.next_memory,now/1e9+.5)
                try:sample=await observer.sample_motion(target.writer,uid,now_ns=now)
                finally:monitor.next_memory=max(monitor.next_memory,time.monotonic()+.5)
                after,current,again,_,_=controller.current_locked(target)
                need(current is position and again is mover and mover.state is state
                     and sample.get('status')=='OBSERVED' and sample.get('uid')==uid
                     and sample.get('map_id')==position.map_id
                     and sample.get('source_contract_valid') is True
                     and sample.get('source_owner_revalidated') is True
                     and (sample.get('stable_double_read') is True and sample.get('read_consistency')=='STRICT_STABLE'
                          or sample.get('stable_double_read') is False
                          and sample.get('read_consistency') in (
                              'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE',
                              'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_FINAL_READBACK',
                              'SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_BOTH')
                          and sample.get('motion_scope')=='READONLY_DIRECT_NPC_MOTION_STOP')
                     and type(sample.get('typed_bytes_requested')) is int
                     and 0<=sample['typed_bytes_requested']<=16384 and sample.get('typed_byte_limit')==16384
                     and sample.get('max_samples_per_second')==2
                     and tuple(sample.get('server_grid') or ())==tuple(grid)
                     and sample.get('snapshot_atomic') is False
                     and sample.get('client_grid_used_as_authority') is False,
                     'TWO_ENEMY_CURRENT_POSE_UNKNOWN')
                if (sample.get('coordinates_match') is not True or sample.get('npc_idle') is not True
                        or tuple(sample.get('client_grid') or ())!=tuple(grid)):return
                self._enemy_pose=state;self._enemy_effect_baseline=(len(controller.effects),after)
                scenario.two_enemy['current_pose']=dict(uid=uid,server_grid=list(grid),client_pose='OBSERVED')
            scenario.save();return
        count,baseline=self._enemy_effect_baseline
        if len(controller.effects)==count:return
        need(len(controller.effects)==count+1,'TWO_ENEMY_ONE_FRESH_COUNTER_REQUIRED')
        async with self.broker._row_operation(target.writer,target.row):
            snapshot,position,mover,_,_=controller.current_locked(target)
            effect=controller.effects[-1]
            need(type(effect) is npc_player_hit.Result and effect.source_uid==uid
                 and effect.before is baseline and effect.after is snapshot
                 and snapshot.current_hp==baseline.current_hp-1
                 and mover.state is self._enemy_pose,
                 'TWO_ENEMY_COUNTER_ATTRIBUTION_REQUIRED')
            effect.require_current_locked(target.writer)
            hp=controller.combat._hp._entries[(id(target.writer),uid)].hp
            need(hp==target.hp_result.after,'TWO_ENEMY_OWN_NPC_HP_REQUIRED')
            self._enemy_completed.append((target,mover.state,hp))
            scenario.engagements.append(dict(uid=uid,target_serial=target.serial,generation=target.generation.ordinal,
                request_sequence=scenario.ATTACK_SEQUENCE,hp=dict(current=hp.current,maximum=hp.maximum),counter=effect.metadata(),client_pose='OBSERVED'))
        if scenario.enemy_index==0:
            scenario.enemy_index=1;scenario.ATTACK_SEQUENCE=3
            self._enemy_target=self._enemy_pose=self._enemy_effect_baseline=None
            scenario.attack['status']='NOT_REQUESTED';scenario.stage='ATTACK_READY'
        else:
            session=self.original.npc_session
            need(set(session._owned_targets)=={2,3}
                 and all(session._owned_targets[t.target_uid][0] is t.generation
                         and session._owned_targets[t.target_uid][1] is t.mover
                         for t,_,_ in self._enemy_completed),
                 'TWO_ENEMY_EXACT_OWNED_SESSION_TARGETS_REQUIRED')
            self._follow_target=target;self._follow_after_move=(position,snapshot,len(controller.effects))
            self._release_target=target;self._release_state=mover.state
            self._follow_move_public=self.manual.last_result
            self._release_life_record=controller.life._tokens.get(id(target.writer))
            self._release_effect_count=len(controller.effects)
            scenario.target_release.update(status='PENDING',target_serial=target.serial,generation=target.generation.ordinal)
            scenario.stage='TARGET_RELEASE_READY'
        scenario.save()

    def release_prepared(self,row,broker,manual,service,position):
        target=self._release_target;controller=self.controller
        need(not self.closed and not self.scenario.stop.is_set() and self.scenario.target_runtime is self
             and self.scenario.stage=='TARGET_RELEASE_READY' and target is controller.target
             and target is self._follow_target and broker is self.broker and manual is self.manual
             and self.original.manual is manual and manual.sequence==3 and manual.consumer.sequence==2
             and manual.last_result is self._follow_move_public and not manual.pending
             and manual.consumer.pending is None and self.scenario.inventory['status']=='COMMITTED'
             and self.scenario.attack['status']=='COMMITTED' and not self.scenario.moves
             and len(self._enemy_completed)==2 and service is target.movement
             and position is self._follow_after_move[0] and service.snapshot() is position
             and target.mover.state is self._release_state and controller._owned_goal is None and self.original.npc_session._goal is None
             and len(controller.effects)==self._release_effect_count,
             'TARGET_RELEASE_REAL_QUIESCED_CALLER_REQUIRED')
        return True

    def release_admission(self,consumer,current):
        target=self._release_target;controller=self.controller
        need(self._polling and not self.closed and not self.scenario.stop.is_set()
             and self.scenario.target_runtime is self and self.scenario.stage=='RESTART_WAIT'
             and self.broker._npc_continuous is controller and controller.runtime is self
             and controller.target is target is self._follow_target
             and consumer is self.manual.consumer and self.original.manual is self.manual
             and consumer._continuous_target_release is True and consumer.allow_source_reselect is False
             and self.manual.sequence==4 and consumer.sequence==2
             and current[0].broker is self.broker and current[0].writer is target.writer
             and current[1] is target.row and current[3] is self._follow_after_move[0]
             and target.mover.state is self._release_state and len(controller.effects)==self._release_effect_count
             and self.broker._player_life._tokens.get(id(target.writer)) is self._release_life_record,
             'TARGET_RELEASE_CURRENT_ADMISSION_REQUIRED')

    def _capture_release_pending(self):
        if self._release_target is None:return
        consumer=self.manual.consumer
        pending=consumer.pending or consumer._source_restart_completed
        if type(pending) is not dict or pending.get('kind')!='SourceRestart':return
        need(self._release_pending is None or self._release_pending is pending,
             'TARGET_RELEASE_SAME_RESTART_PENDING_REQUIRED')
        self._release_pending=pending
        self._release_restart_state=pending.get('restart_state')
        if self.manual.last_result.get('command')=='SourceRestart':
            self._release_public=self.manual.last_result

    def finish_target_release(self):
        """Called only after the original Restart collector's complete proof."""
        from tools.local_original_session import launcher
        target=self._release_target;controller=self.controller;manual=self.manual;consumer=manual.consumer
        pending=self._release_pending;state=target.row.get('_restart')
        task=asyncio.current_task()
        if task is not None and task.cancelling():raise asyncio.CancelledError()
        need(not self.closed and not self.scenario.stop.is_set() and self.scenario.target_runtime is self
             and self.scenario.source_restart['status']=='COMMITTED'
             and pending is consumer._source_restart_completed and type(pending) is dict
             and pending['kind']=='SourceRestart' and pending['native_attempted'] is True
             and pending['request']['seq']==consumer.sequence==3 and manual.sequence==4
             and pending['native']==dict(pending['request'],schema='own-source-restart-result-v1',
                                        status='RETURNED',reason=0,invoked=True)
             and pending['result_identity'] is not None
             and state is pending['restart_state'] is self._release_restart_state
             and state['phase']=='DRAINED' and pending['completed_restart_frame'] is state['frame']
             and all(state[k] is True for k in ('write_attempted','drain_returned','response_drained','selection_cleared'))
             and all(a is b for a,b in zip(state['binding'][0][6:11],
                 (self.broker.realm,target.game,target.movement,self._follow_after_move[0],target.selection)))
             and launcher.ManualMoveRequests._actual_source_restart_commit(manual,consumer.state,asynchronous=True)
             and manual.last_result is self._release_public and not manual.pending
             and controller.target is None and controller.released_target is target
             and controller.released_life_record is self._release_life_record
             and controller.reason=='PLAYER_SELECTION_RELEASED' and getattr(controller,'cleanup_error',None) is None
             and id(target.writer) not in controller.life._tokens
             and controller._owned_goal is None and self.original.npc_session._goal is None
             and self.original.npc_session._goal_player_life is None
             and target.mover.state is self._release_state and len(controller.effects)==self._release_effect_count,
             'TARGET_RELEASE_ORIGINAL_RESTART_COMPLETION_REQUIRED')
        session=self.original.npc_session
        need(session._owned_targets=={} and session._generation is session._owned_mover is session._goal is None
             and all(t.mover.state is state for t,state,_ in self._enemy_completed),
             'TWO_ENEMY_BOTH_SESSION_TARGETS_RELEASED_REQUIRED')
        self.scenario.target_release.update(status='COMMITTED',proof_scope='TWO_ENEMY_SAME_SELECTION_RESTART_RELEASE_ONLY',
            public_sequence=manual.sequence,native_sequence=consumer.sequence,selection_cleared=True,
            owned_goal_cleared=True,additional_effects_at_release=0,new_life='UNKNOWN',follow='REUSED_387',retired_uids=[2,3])
        self.scenario.two_enemy.update(status='COMMITTED',selection_cleared=True,both_targets_cleared=True)


    def _sync(self):
        state=self.manual.last_result
        self.result.update(server=self.controller.metadata(),input_consumer={k:state[k] for k in
            ('status','phase','reason','command','sequence','cleanup_required') if k in state})
        if self.controller.effects:self.result['status']='COMMITTED'
        if self.controller.lethal is not None and self.controller.lethal.result is not None:
            self.result['status']='COMMITTED'
        if state.get('status')=='UNKNOWN':self.result['overall']='UNKNOWN'

    async def poll(self,monitor=None):
        need(monitor is self.scenario.monitor and not self._polling,'CONTINUOUS_SAME_SERIAL_MONITOR_REQUIRED')
        if self.closed:return {}
        if self.scenario.stop.is_set():
            self.controller.retire('CANCELLED');self._sync();return {}
        self._polling=True
        try:
            # Target/current validation precedes every original NPC tick. The
            # command wrapper never ticks an old goal before target retirement.
            await self._follow_progress(monitor)
            if self.scenario.stop.is_set():self._sync();return {}
            if self._release_target is None:
                await self.controller.poll(now_ns=time.monotonic_ns(),monitor=monitor)
            if self.manual.closed and self.scenario.input_diagnostic is not None:
                result=dict(manual_move=dict(self.manual.last_result))
            else:
                claim=self._input_claim()
                self._capture_release_pending()
                try:result=await self.original.poll(monitor,npc_poll=False)
                except Exception as error:
                    if (claim is None or type(error) is not ValueError
                        or str(error)!='MANUAL_MOVE_TERMINAL_UNKNOWN'
                        or self.manual.last_result.get('reason') not in
                            ('MANUAL_ATTACK_ACTION_SNAPSHOT_UNKNOWN','MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')):
                        self._remember_quit_input(claim,'TERMINAL')
                        raise
                    result=await self._consume_input_terminal(error,claim)
                else:self._remember_quit_input(claim,'COMMITTED')
                self._capture_release_pending()
            await self._follow_progress(monitor)
            self._sync()
            if self.controller.lethal is not None and self.controller.lethal.stage=='DEAD_OBSERVED':
                self.scenario.stage='CONTINUOUS_PLAYER_DEAD_STOP_REQUESTED'
                self.scenario.stop.set()
            return dict(result,npc_continuous_retaliation=dict(self.result))
        except asyncio.CancelledError:
            if self.scenario.follow['status']=='PENDING':
                self.scenario.follow.update(status='UNKNOWN',reason='CANCELLED')
            self.controller.retire('CANCELLED');self._sync();raise
        except BaseException as error:
            if self.scenario.follow['status']=='PENDING':
                from tools.local_original_session import launcher
                self.scenario.follow.update(status='UNKNOWN',
                    reason=launcher.safe_error_code(error) or type(error).__name__)
            self.controller.retire('CURRENT_OR_TRANSPORT_FAILURE');self._sync();raise
        finally:self._polling=False

    def close(self):
        if self.closed:return
        self.closed=True;self.controller.retire('FEATURE_CLOSED');self._sync()
        try:return self.original.close()
        finally:self.controller.close()



