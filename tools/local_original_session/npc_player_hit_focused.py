"""One named local NPC hit configuration; no AI, timer or collector."""
from tools.local_original_session import feature_config as fc, hp_status, inventory as inv, inventory_store
from tools.local_original_session import npc_hp, npc_motion, npc_player_hit, npc_session, restart

PROFILE = 'sibling-background-npc-player-hit-spawn'
REPEATED_PROFILE = 'sibling-background-npc-player-hit-repeated-spawn'
need = fc.need


def configuration(config, *, inventory=False, auto_inventory=False):
    need(type(config) is fc.Features and config.npc_player_hit_policy == npc_player_hit.POLICY
         and type(config.npc_player_hit_policy) is str
         and type(config.npc_player_hit_input) is fc.NpcPlayerHitInput
         and config.npc_player_hit_input.raw_effect == 1
         and config.npc_player_hit_input.direction == 8
         and config.npc_player_hit_input.observe_hud_bar is True
         and config.npc_player_hit_repeated_policy is None and config.npc_player_hit_repeated_input is None,
         'SCENARIO_NPC_PLAYER_HIT_EXPLICIT_POLICY_INPUT_REQUIRED')
    return _configuration(config, inventory=inventory, auto_inventory=auto_inventory)


def repeated_configuration(config, *, inventory=False, auto_inventory=False):
    need(type(config) is fc.Features and config.npc_player_hit_repeated_policy == npc_player_hit.REPEATED_POLICY
         and type(config.npc_player_hit_repeated_policy) is str
         and type(config.npc_player_hit_repeated_input) is fc.NpcPlayerHitInput
         and config.npc_player_hit_repeated_input.raw_effect == 1
         and config.npc_player_hit_repeated_input.direction == 8
         and config.npc_player_hit_repeated_input.observe_hud_bar is True
         and config.npc_player_hit_policy is None and config.npc_player_hit_input is None,
         'SCENARIO_NPC_PLAYER_HIT_REPEATED_EXCLUSIVE_POLICY_INPUT_REQUIRED')
    return _configuration(config, inventory=inventory, auto_inventory=auto_inventory)


def _configuration(config, *, inventory, auto_inventory):
    need(len(config.spawns) == 1 and type(config.interval_ns) is int and config.interval_ns > 0
         and config.motion_policy == npc_motion.LOCAL_PRE_STEP
         and config.goal_policy == npc_session.AXIS_SIGN_GOAL and config.goal is None
         and config.attack_policy == fc.ATTACK_INTENT_POLICY
         and type(config.attack_hp_provider) is npc_hp.ExplicitInputs
         and config.hp_status_policy == hp_status.POLICY and config.hp_status_input is None,
         'SCENARIO_NPC_PLAYER_HIT_CURRENT_LIFE_STATUS_REQUIRED')
    spawn, = config.spawns
    rows = config.attack_hp_provider.rows
    need(type(rows) is tuple and len(rows) == 1 and type(rows[0]) is npc_hp.Inputs
         and rows[0].target == npc_hp.Target(spawn.uid, spawn.map_id, spawn.fields[3], spawn.fields[39])
         and rows[0].hp.alive and spawn.map_id == 0,
         'SCENARIO_NPC_PLAYER_HIT_EXACT_LIVE_NPC_REQUIRED')
    need(all(getattr(config, name) is None for name in ('attack_feedback', 'npc_death_policy',
             'npc_remove_policy', 'npc_respawn_policy', 'npc_respawn_spawn', 'item_use_policy',
             'item_equipment_policy', 'inventory_update_policy', 'inventory_missing_row_policy',
             'inventory_collection_policy', 'inventory_collection_grant'))
         and config.item_equipment_first_enable is False,
         'SCENARIO_NPC_PLAYER_HIT_EXCLUSIVE_CONFIG_REQUIRED')
    need(inventory is True and auto_inventory is True and config.inventory_policy == inv.POLICY
         and type(config.inventory_frame) is bytes and config.inventory_store_policy == inventory_store.POLICY
         and config.inventory_delivery_policy == fc.LOCAL_WORLD_READY_ONCE
         and config.inventory_reselection_policy == fc.LOCAL_SAVED_ROW_ON_RESELECTION
         and config.restart_policy == restart.POLICY,
         'SCENARIO_NPC_PLAYER_HIT_EXISTING_SAVED_PREPARATION_REQUIRED')
    inv.validate_frame(config.inventory_frame)
    return config
