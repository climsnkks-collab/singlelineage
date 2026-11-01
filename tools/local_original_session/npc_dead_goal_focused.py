"""Opt-in arrival/death cleanup consumer over the retained product runtime.

Saved inventory and the original Attack2 remain in the existing scenario.
No new source observer, sender, timer, native operation or HP producer exists.
"""
import asyncio
import time

from tools.local_original_session import npc_combat_focused as combat
from tools.local_original_session import npc_motion, npc_session

need = combat.need


def configuration(features, *, base_configuration, inventory=False, auto_inventory=False):
    from dataclasses import replace
    need(type(features.interval_ns) is int and 0 < features.interval_ns < (1 << 63)
         and features.motion_policy == npc_motion.LOCAL_PRE_STEP
         and features.goal_policy == npc_session.AXIS_SIGN_GOAL and features.goal is None
         and features.npc_respawn_policy is features.npc_respawn_spawn is None,
         'SCENARIO_DEAD_GOAL_EXPLICIT_MOTION_WITHOUT_RESPAWN_REQUIRED')
    # Reuse stationary attack/inventory constraints without relaxing their
    # public default. Only the named trial adds an idle, source-bound mover.
    base_configuration(replace(features, interval_ns=None, motion_policy=None, goal_policy=None),
                       inventory=inventory, auto_inventory=auto_inventory,
                       collection_restore_only=features.inventory_collection_policy is not None)
    combat.configuration(features)
    return features


def collection_configuration(features):
    """Existing actual257 restore input on this explicit lethal-goal mode only."""
    from tools.local_original_session import feature_config, inventory, inventory_store
    need(type(features) is feature_config.Features and len(features.spawns) == 1
         and features.inventory_policy == inventory.POLICY
         and features.inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
         and features.inventory_collection_policy == inventory.COLLECTION_POLICY
         and features.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
         and features.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
         and features.inventory_missing_row_policy is features.inventory_custody_policy
             is features.item_transfer_policy is features.item_use_policy
             is features.item_equipment_policy is features.inventory_update_policy is None
         and features.player_life_policy is features.npc_respawn_policy is None
         and type(features.interval_ns) is int and features.interval_ns > 0
         and features.motion_policy == npc_motion.LOCAL_PRE_STEP
         and features.goal_policy == npc_session.AXIS_SIGN_GOAL and features.goal is None,
         'FEATURE_NPC_DEAD_GOAL_EXACT_COLLECTION_REQUIRED')
    grant = features.inventory_collection_grant
    need(type(grant) is tuple and len(grant) == 2
         and grant[0] == inventory_store.SECOND_INSTANCE_POLICY
         and type(grant[1]) is frozenset and grant[1] == frozenset((65538,)),
         'FEATURE_NPC_DEAD_GOAL_EXISTING_257_COLLECTION_REQUIRED')
    combat.configuration(features)
    return features


class Trial(combat.Trial):
    def __init__(self, scenario, runtime, *, clock_ns=time.monotonic_ns):
        super().__init__(scenario, runtime, clock_ns=clock_ns)
        self.controller = runtime.npc_session
        need(type(self.controller) is npc_session.NpcSession
             and self.controller.broker is runtime.manual.inventory_broker
             and self.controller.factory.reader is scenario.reader,
             'SCENARIO_DEAD_GOAL_ORIGINAL_SESSION_REQUIRED')
        self.phase = 'WAIT_PREPARATION'
        self.goal = self.mover = self.motion_state = self.motion_combat = None
        self.motion_writer = self.motion_row = None
        self.motion_events = None
        self.live_claimed = self.dead_claimed = self.idle_claimed = False
        self.result.update(status='NOT_REQUESTED', scope='SERVER_DEAD_GOAL_RUNTIME_CLEANUP',
            live_at_goal=None, dead=None, idle=None, goal_submissions=0, extra_move_packets=None,
            death_action='REUSED_EXISTING_SUCCESS_NOT_RETESTED',
            remove_transport='NOT_REQUESTED', registry='REUSED_EXISTING_SUCCESS_NOT_RETESTED')

    def arm(self, broker):
        need(self.phase == 'WAIT_PREPARATION' and self.scenario.stage == 'ATTACK_READY'
             and self.scenario.inventory['status'] == 'COMMITTED',
             'SCENARIO_DEAD_GOAL_ONCE_PREPARATION_REQUIRED')
        binding = self.controller.current_binding()
        need(binding is not None and binding.broker is broker
             and binding.owner is self.scenario.move_bound[0]
             and self.controller._goal is None, 'SCENARIO_DEAD_GOAL_CURRENT_SELECTION_REQUIRED')
        self.motion_writer = binding.owner
        rows = [row for rows in broker._claims.values() for row in rows if row['writer'] is binding.owner]
        need(len(rows) == 1, 'SCENARIO_DEAD_GOAL_CURRENT_ROW_REQUIRED')
        self.motion_row, = rows
        self.mover = broker.realm.npc_mover(binding.owner)
        self.motion_state = self.mover.state
        self.motion_combat = broker._attack_session
        self.goal = tuple(npc_session.movement.authority.unpack_grid(self.motion_state.packed))
        self.motion_events = broker.policy.events
        self.started_ns = self.clock_ns()
        self.result.update(status='PENDING', goal=list(self.goal))
        self.phase = 'LIVE_READY'
        self.scenario.stage = 'NPC_DEAD_GOAL_LIVE_READY'

    def motion_current(self, broker):
        need(self.clock_ns() - self.started_ns < combat.WAIT_NS,
             'SCENARIO_NPC_ORIGINAL_DEADLINE')
        binding = self.controller.current_binding()
        need(binding is not None and binding.owner is self.motion_writer and binding.broker is broker
             and broker._attack_session is self.motion_combat is broker.realm._attack_session
             and broker.realm.npc_mover(self.motion_writer) is self.mover
             and self.mover.state is self.motion_state
             and self.controller.factory._session is self.controller,
             'SCENARIO_DEAD_GOAL_SAME_RUNTIME_LIFETIME_REQUIRED')
        rows = [row for rows in broker._claims.values() for row in rows if row['writer'] is self.motion_writer]
        need(len(rows) == 1 and rows[0] is self.motion_row,
             'SCENARIO_DEAD_GOAL_SAME_ROW_REQUIRED')
        events = list(broker.policy.log)
        start = self.motion_events - (broker.policy.events-len(events))
        need(0 <= start <= len(events), 'SCENARIO_DEAD_GOAL_ORIGINAL_EVENTS_REQUIRED')
        moves = [event for event in events[start:] if event[0] == 'tx' and event[2] == npc_motion.OPCODE]
        need(not moves, 'SCENARIO_DEAD_GOAL_UNEXPECTED_MOVE_PACKET')
        return len(moves)

    def require_attack_target(self, broker, spawn):
        self.motion_current(broker)
        need(self.phase == 'WAIT_ATTACK' and self.live_claimed and not self.dead_claimed
             and self.controller._goal is self.goal
             and self.controller.factory.config.spawns is self.scenario.features.spawns
             and self.motion_state.uid == spawn.uid and self.motion_state.map_id == spawn.map_id
             and tuple(npc_session.movement.authority.unpack_grid(self.motion_state.packed)) == self.goal,
             'SCENARIO_DEAD_GOAL_EXACT_UNMOVED_ATTACK_TARGET_REQUIRED')
        return True

    async def live(self, broker, monitor):
        need(self.phase == 'LIVE_READY' and not self.live_claimed,
             'SCENARIO_DEAD_GOAL_LIVE_ONCE_REQUIRED')
        self.live_claimed = True
        self.motion_current(broker)
        self.controller.submit_goal(goal=self.goal)
        self.result['goal_submissions'] = 1
        result = await self.runtime.poll(monitor)
        self.motion_current(broker)
        row = result.get('npc', {})
        need(row.get('status') == 'AT_GOAL' and row.get('reason') is None
             and row.get('typed_slot_reserved') is False and self.controller._goal is self.goal,
             'SCENARIO_DEAD_GOAL_LIVE_AT_GOAL_REQUIRED')
        self.result['live_at_goal'] = dict(row)
        self.phase = 'WAIT_ATTACK'
        self.scenario.stage = 'ATTACK_READY'
        return result

    def begin(self, broker):
        need(self.phase == 'WAIT_ATTACK' and self.live_claimed,
             'SCENARIO_DEAD_GOAL_LIVE_BEFORE_ATTACK_REQUIRED')
        self.motion_current(broker)
        started = self.started_ns
        # Existing exact accepted HP/notification/transport/owner validation.
        # It performs no new Death/Remove/registry observation or send here.
        super().begin(broker)
        self.started_ns = started  # Never extend the original trial deadline.
        need(self.writer is self.motion_writer and self.row is self.motion_row
             and self.session is self.motion_combat and self.controller._goal is self.goal,
             'SCENARIO_DEAD_GOAL_ACCEPTED_SAME_LIFETIME_REQUIRED')
        self.phase = 'DEAD_READY'
        self.scenario.stage = 'NPC_DEAD_GOAL_RUN'

    async def finish_poll(self, broker, monitor):
        self.motion_current(broker)
        self.current(broker)
        dead = self.phase == 'DEAD_READY'
        need(dead and not self.dead_claimed or self.phase == 'IDLE_READY' and not self.idle_claimed,
             'SCENARIO_DEAD_GOAL_COMPLETION_ONCE_REQUIRED')
        if dead:
            self.dead_claimed = True
        else:
            self.idle_claimed = True
        result = await self.runtime.poll(monitor)
        self.motion_current(broker)
        self.current(broker)
        row = result.get('npc', {})
        need(row.get('status') == ('DEAD' if dead else 'IDLE')
             and row.get('reason') == ('NPC_HP_DEAD_MOTION_REFUSED' if dead else None)
             and row.get('typed_slot_reserved') is False and self.controller._goal is None,
             'SCENARIO_DEAD_GOAL_PRODUCT_COMPLETION_REQUIRED')
        self.result['dead' if dead else 'idle'] = dict(row)
        self.result['extra_move_packets'] = self.motion_current(broker)
        self.phase = 'IDLE_READY' if dead else 'DONE'
        if not dead:
            self.result['status'] = 'COMMITTED'
            self.scenario.stage = 'NPC_COMPLETE_STOP_REQUESTED'
            self.scenario.stop.set()  # Existing run_session Quit/cleanup.
        return result


class Runtime:
    def __init__(self, runtime, scenario):
        from tools.local_original_session.launcher import ProductFeatures
        need(type(runtime) is ProductFeatures, 'SCENARIO_DEAD_GOAL_REAL_PRODUCT_REQUIRED')
        self.original, self.scenario, self.manual = runtime, scenario, runtime.manual
        scenario.npc_inventory_runtime = runtime  # Same typed two-row readiness consumer.
        self.trial = Trial(scenario, runtime)
        scenario.npc_trial = self.trial

    async def poll(self, monitor=None):
        if self.scenario.stop.is_set():
            return {}
        need(monitor is self.scenario.monitor, 'SCENARIO_NPC_SAME_MONITOR_REQUIRED')
        trial, broker = self.trial, self.manual.inventory_broker
        try:
            if trial.phase == 'LIVE_READY':
                result = await trial.live(broker, monitor)
            elif trial.phase in ('DEAD_READY', 'IDLE_READY'):
                result = await trial.finish_poll(broker, monitor)
            else:
                if trial.phase == 'WAIT_ATTACK':
                    trial.motion_current(broker)
                # The same original manual scheduler continues. No repeated
                # AT_GOAL poll or stale outcome is substituted during Attack2.
                result = await self.original.poll(monitor, npc_poll=trial.phase != 'WAIT_ATTACK')
            self.scenario.save()
            return result
        except asyncio.CancelledError:
            trial.fail(ValueError('SCENARIO_DEAD_GOAL_CANCELLED'))
            self.scenario.save()
            raise
        except Exception as error:
            trial.fail(error)
            self.scenario.save()
            return {}

    def close(self):
        self.original.close()
