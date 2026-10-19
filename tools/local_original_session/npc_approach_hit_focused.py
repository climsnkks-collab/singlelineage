"""Existing one-step pose/idle arrival, retained for the approach hit handoff.

This motion consumer neither computes a combat radius nor grants an attack.
The backend Plan owns the selected source policy. Static-step contact does
not prove the reference arrow/closed-door predicate.
"""
from tools.local_original_session import npc_motion_focused as motion
from tools.local_original_session import npc_approach_hit as approach
import asyncio

PROFILE = 'sibling-background-npc-approach-player-hit-spawn'


def configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import feature_config as fc, npc_player_hit, npc_player_hit_focused
    motion.need(type(config) is fc.Features
                and config.npc_approach_hit_policy in (approach.LOCAL_REFERENCE_MELEE_RANGE_ONE, approach.STATIC_STEP_CONTACT_POLICY)
                and type(config.npc_approach_hit_policy) is str
                and type(config.npc_approach_hit_input) is fc.NpcApproachHitInput
                and config.npc_player_hit_repeated_policy == npc_player_hit.REPEATED_POLICY
                and config.npc_player_hit_repeated_input is None
                and config.npc_player_hit_policy is config.npc_player_hit_input is None,
                'SCENARIO_APPROACH_EXPLICIT_NAMED_POLICY_REQUIRED')
    return npc_player_hit_focused._configuration(config, inventory=inventory, auto_inventory=auto_inventory)


class ApproachTrial(motion.Trial):
    def __init__(self, scenario, runtime, *, goal, plan, **kwargs):
        motion.need(type(plan) is approach.Plan and plan.goal is goal and plan.session is runtime.npc_session,
                    'SCENARIO_APPROACH_EXACT_PLAN_GOAL_REQUIRED')
        self.plan = plan
        self.plan_sample = approach.Plan.sample_motion_locked
        super().__init__(scenario, runtime, goal=goal, **kwargs)

    async def _sample_motion_locked(self, broker, now):
        motion.need(type(self.plan) is approach.Plan
                    and type(self.plan).sample_motion_locked is self.plan_sample
                    and self.plan.sample_motion_locked.__self__ is self.plan
                    and self.plan.sample_motion_locked.__func__ is self.plan_sample,
                    'SCENARIO_APPROACH_CANONICAL_POSE_PRODUCER_REQUIRED')
        return await self.plan.sample_motion_locked(self.writer, self.observer, now_ns=now)

    def _complete_arrival(self):
        self.result.update(status='COMMITTED', at_goal=True)
        self.phase = 'DONE'
        self.scenario.stage = 'NPC_APPROACH_ARRIVED_READY'


class ApproachMotionRuntime(motion.Runtime):
    def __init__(self, runtime, scenario, *, goal, plan):
        self.original, self.scenario = runtime, scenario
        self.manual = runtime.manual
        self.npc_session = runtime.npc_session
        self.trial = ApproachTrial(scenario, runtime, goal=goal, plan=plan,
                                   clock_ns=lambda:int(scenario.clock()*1e9))
        scenario.npc_motion_trial = self.trial

    async def poll(self, monitor=None):
        trial = self.trial
        # Sparse callers can reach the POST slot before polling AT_GOAL. Close
        # that original session result first, then mint the one fresh arrival.
        if trial.phase != 'POST_POSE' or trial.at_goal:
            return await super().poll(monitor)
        try:
            motion.need(monitor is self.scenario.monitor,
                        'SCENARIO_NPC_MOTION_SAME_MONITOR_REQUIRED')
            trial.current(self.npc_session.broker)
            result = await self.original.poll(monitor)
            trial.after_poll(self.npc_session.broker, result)
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
