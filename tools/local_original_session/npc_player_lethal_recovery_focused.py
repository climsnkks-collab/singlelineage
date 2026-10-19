"""Dedicated opt-in current NPC lethal hit and original own-player recovery.

The selected one-step/contact and recovery values are explicit local policy.
Original arrow/door, damage formula and official server order remain unknown.
"""
from dataclasses import dataclass
from tools.local_original_session import feature_config as fc, attack, movement, player_life
from tools.local_original_session import player_death_recovery_focused as life
from tools.local_original_session import npc_approach_hit as approach, npc_motion_focused as motion, npc_motion
from tools.local_original_session import npc_approach_hit_focused as arrival

need = fc.need
PROFILE = 'sibling-background-npc-player-lethal-recovery-spawn'

@dataclass(frozen=True, slots=True)
class Input:
    goal: tuple
    expected_player_grid: tuple
    raw_effect: int

    def __post_init__(self):
        for grid in (self.goal, self.expected_player_grid):
            need(type(grid) is tuple and len(grid) == 2, 'FEATURE_NPC_LETHAL_TYPED_GRID_REQUIRED')
            movement.authority.pack_grid(*grid)
        approach.melee_geometry(self.goal, self.expected_player_grid)
        attack._int32(self.raw_effect)
        need(self.raw_effect > 0, 'FEATURE_NPC_LETHAL_POSITIVE_RAW_EFFECT_REQUIRED')


def configuration(config):
    need(type(config) is fc.Features and type(config.npc_player_lethal_recovery_input) is Input
         and type(config.player_life_policy) is player_life.Policy
         and config.player_life_policy.label == player_life.NPC_POLICY_LABEL,
         'NPC_LETHAL_EXACT_PAIRED_LOCAL_CONFIGURATION_REQUIRED')
    need(all(getattr(config, key) is None for key in (
        'hp_status_input', 'npc_player_hit_policy', 'npc_player_hit_repeated_policy',
        'npc_approach_hit_policy', 'restart_policy', 'npc_death_policy',
        'npc_remove_policy', 'npc_respawn_policy')),
        'NPC_LETHAL_EXCLUSIVE_CONSUMER_REQUIRED')
    need(len(config.spawns) == 1 and config.interval_ns is not None and config.goal is None
         and config.motion_policy == npc_motion.LOCAL_PRE_STEP
         and config.goal_policy == motion.npc_session.AXIS_SIGN_GOAL,
         'NPC_LETHAL_EXPLICIT_SINGLE_STEP_SESSION_REQUIRED')
    return config.player_life_policy


def broker_options(config):
    from tools.local_original_session import hp_status, npc_player_hit, npc_hp
    policy = configuration(config)
    need(config.attack_policy == fc.ATTACK_INTENT_POLICY
         and type(config.attack_hp_provider) is npc_hp.ExplicitInputs,
         'NPC_LETHAL_CURRENT_PROJECTOR_DEPENDENCIES_REQUIRED')
    return dict(player_life_policy=policy, hp_status_policy=hp_status.POLICY,
                npc_player_hit_policy=npc_player_hit.POLICY)


class SourceDeadRestartRequests(life.SourceDeadRestartRequests):
    """Exact dedicated host type; inherited original callback producer only."""


class ApproachTrial(arrival.ApproachTrial):
    def __init__(self, scenario, runtime, *, goal, plan, **kwargs):
        from tools.local_original_session import npc_player_lethal as lethal
        need(type(plan) is lethal.Plan and plan.goal is goal and plan.session is runtime.npc_session,
             'NPC_LETHAL_EXACT_PLAN_GOAL_REQUIRED')
        self.plan = plan
        self.plan_sample = approach.Plan.sample_motion_locked
        motion.Trial.__init__(self, scenario, runtime, goal=goal, **kwargs)

    async def _sample_motion_locked(self, broker, now):
        from tools.local_original_session import npc_player_lethal as lethal
        need(type(self.plan) is lethal.Plan
             and type(self.plan).sample_motion_locked is self.plan_sample
             and self.plan.sample_motion_locked.__func__ is self.plan_sample,
             'NPC_LETHAL_CANONICAL_POSE_PRODUCER_REQUIRED')
        return await self.plan_sample(self.plan, self.writer, self.observer, now_ns=now)


class ApproachMotionRuntime(arrival.ApproachMotionRuntime):
    def __init__(self, runtime, scenario, *, goal, plan):
        self.original, self.scenario = runtime, scenario
        self.manual, self.npc_session = runtime.manual, runtime.npc_session
        self.trial = ApproachTrial(scenario, runtime, goal=goal, plan=plan,
                                  clock_ns=lambda: int(scenario.clock()*1e9))
        scenario.npc_motion_trial = self.trial
