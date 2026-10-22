"""Strict opt-in local NPC configuration; no actor, stat or motion defaults."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from tools.local_original_session import movement, npc, npc_motion

SCHEMA = 'local-original-features-v1'
ATTACK_INTENT_POLICY = 'EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT'
LOCAL_WORLD_READY_ONCE = 'LOCAL_WORLD_READY_ONCE'
LOCAL_SAVED_ROW_ON_RESELECTION = 'LOCAL_SAVED_ROW_ON_RESELECTION'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def _object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'FEATURE_DUPLICATE_KEY')
        result[key] = value
    return result


def _keys(value, required):
    need(type(value) is dict and set(value) == set(required), 'FEATURE_EXACT_SCHEMA_REQUIRED')


HP_STATUS_SCOPE = 'SELECTED_LOCAL_CHARACTER_HP_DISPLAY_ONLY'


@dataclass(frozen=True, slots=True)
class HpStatusInput:
    target_uid: int
    map_id: int
    current_hp: int
    maximum_hp: int
    expected_revision: int
    scope: str
    observe_hud_bar: bool = False

    def __post_init__(self):
        need(type(self.target_uid) is int and 0 < self.target_uid < (1 << 64)
             and type(self.map_id) is int and -(1 << 31) <= self.map_id < (1 << 31)
             and type(self.current_hp) is type(self.maximum_hp) is int
             and 0 < self.current_hp <= self.maximum_hp <= 0x7fffffff
             and type(self.expected_revision) is int and 0 <= self.expected_revision < (1 << 63)
             and type(self.scope) is str and self.scope == HP_STATUS_SCOPE
             and type(self.observe_hud_bar) is bool,
             'FEATURE_EXPLICIT_LOCAL_CHARACTER_POSITIVE_HP_INPUT_REQUIRED')


@dataclass(frozen=True, slots=True)
class NpcPlayerHitInput:
    raw_effect: int
    direction: int
    observe_hud_bar: bool

    def __post_init__(self):
        # Named product choice; raw effect is not the separate local HP damage.
        need(type(self.raw_effect) is int and self.raw_effect == 1
             and type(self.direction) is int and self.direction == 8
             and self.observe_hud_bar is True,
             'FEATURE_NPC_PLAYER_HIT_EXPLICIT_EFFECT_DIRECTION_HUD_REQUIRED')


@dataclass(frozen=True, slots=True)
class NpcApproachHitInput:
    goal: tuple
    expected_player_grid: tuple
    raw_effect: int
    observe_hud_bar: bool

    def __post_init__(self):
        need(type(self.goal) is tuple and len(self.goal) == 2
             and type(self.expected_player_grid) is tuple and len(self.expected_player_grid) == 2
             and type(self.raw_effect) is int and self.raw_effect == 1
             and self.observe_hud_bar is True,
             'FEATURE_NPC_APPROACH_EXPLICIT_GOAL_EFFECT_HUD_REQUIRED')
        movement.authority.pack_grid(*self.goal)
        movement.authority.pack_grid(*self.expected_player_grid)


@dataclass(frozen=True, slots=True)
class Features:
    spawns: tuple = ()
    interval_ns: int | None = None
    motion_policy: str | None = None
    goal_policy: str | None = None
    goal: tuple | None = None
    attack_policy: str | None = None
    inventory_policy: str | None = None
    inventory_frame: bytes | None = None
    attack_feedback: object | None = None
    restart_policy: str | None = None
    inventory_store_policy: str | None = None
    inventory_delivery_policy: str | None = None
    item_use_policy: str | None = None
    inventory_update_policy: str | None = None
    inventory_reselection_policy: str | None = None
    item_equipment_policy: str | None = None
    item_equipment_first_enable: bool = False
    inventory_missing_row_policy: str | None = None
    attack_hp_provider: object | None = None
    npc_death_policy: str | None = None
    npc_remove_policy: str | None = None
    npc_respawn_policy: str | None = None
    npc_respawn_spawn: object | None = None
    hp_status_policy: str | None = None
    hp_status_input: HpStatusInput | None = None
    inventory_collection_policy: str | None = None
    inventory_collection_grant: tuple | None = None
    npc_player_hit_policy: str | None = None
    npc_player_hit_input: NpcPlayerHitInput | None = None
    npc_player_hit_repeated_policy: str | None = None
    npc_player_hit_repeated_input: NpcPlayerHitInput | None = None
    inventory_custody_policy: str | None = None
    item_transfer_policy: str | None = None
    npc_approach_hit_policy: str | None = None
    npc_approach_hit_input: NpcApproachHitInput | None = None
    player_life_policy: object | None = None
    npc_player_lethal_recovery_input: object | None = None
    # Trusted in-process fixture selection only; parse() deliberately has no
    # corresponding JSON key or capability/authority deserializer.
    canonical_bootstrap: object | None = None


def _npc_respawn(value, actor, combat):
    policy = spawn = None
    if value.get('npc_respawn') is not None:
        from tools.local_original_session import npc_respawn, npc_death
        config = value['npc_respawn']
        _keys(config, ('policy', 'spawn'))
        policy = config['policy']
        need(type(policy) is str and policy == npc_respawn.POLICY,
             'FEATURE_EXPLICIT_NPC_RESPAWN_POLICY_REQUIRED')
        need(actor is not None and value['npc']['motion'] is not None
             and combat['attack_hp_provider'] is not None
             and combat['npc_death_policy'] == npc_death.DEATH_POLICY
             and combat['npc_remove_policy'] == npc_death.REMOVE_POLICY,
             'FEATURE_NPC_RESPAWN_REQUIRES_MOTION_HP_DEATH_REMOVE')
        entry = config['spawn']
        _keys(entry, ('fields', 'map_id', 'policy'))
        fields = entry['fields']
        need(type(fields) is dict and set(fields) == {str(k) for k in npc.FIELDS},
             'NPC_ALL_REQUIRED_AND_TEMPLATE39_EXPLICIT_ONLY')
        spawn = npc.NpcSpawn({int(k): item for k, item in fields.items()},
                             map_id=entry['map_id'], policy=entry['policy'])
        need(dict(spawn.fields) == dict(actor.fields) and spawn.map_id == actor.map_id
             and spawn.policy == actor.policy,
             'FEATURE_NPC_RESPAWN_EXACT_ORIGINAL_RECIPE_REQUIRED')
    return dict(npc_respawn_policy=policy, npc_respawn_spawn=spawn)


def _npc_combat(value, actor, attack_policy, attack_feedback):
    provider = death_policy = remove_policy = None
    if value.get('npc_hp') is not None:
        from tools.local_original_session import npc_hp
        config = value['npc_hp']
        _keys(config, ('policy', 'rows'))
        need(type(config['policy']) is str and config['policy'] == npc_hp.POLICY,
             'FEATURE_EXPLICIT_NPC_HP_POLICY_REQUIRED')
        need(actor is not None and attack_policy == ATTACK_INTENT_POLICY,
             'FEATURE_NPC_HP_REQUIRES_NPC_ATTACK')
        rows = config['rows']
        need(type(rows) is list and len(rows) == 1, 'FEATURE_NPC_HP_SINGLE_ROW_REQUIRED')
        row = rows[0]
        _keys(row, ('target', 'hp', 'hit'))
        _keys(row['target'], ('uid', 'map_id', 'sprite_id', 'template_id'))
        _keys(row['hp'], ('current', 'maximum'))
        _keys(row['hit'], ('landed', 'damage'))
        inputs = npc_hp.Inputs(npc_hp.Target(**row['target']), npc_hp.Hp(**row['hp']),
                               npc_hp.Hit(**row['hit']))
        need(inputs.target == npc_hp.Target(actor.uid, actor.map_id, actor.fields[3], actor.fields[39]),
             'FEATURE_NPC_HP_EXACT_CURRENT_SPAWN_REQUIRED')
        provider = npc_hp.ExplicitInputs((inputs,))
    if value.get('npc_death') is not None:
        from tools.local_original_session import npc_death
        _keys(value['npc_death'], ('policy',))
        death_policy = value['npc_death']['policy']
        need(type(death_policy) is str and death_policy == npc_death.DEATH_POLICY,
             'FEATURE_EXPLICIT_NPC_DEATH_POLICY_REQUIRED')
        need(provider is not None and attack_feedback is not None,
             'FEATURE_NPC_DEATH_REQUIRES_HP_FEEDBACK')
        npc_death.source_ready()
    if value.get('npc_remove') is not None:
        from tools.local_original_session import npc_death
        _keys(value['npc_remove'], ('policy',))
        remove_policy = value['npc_remove']['policy']
        need(type(remove_policy) is str and remove_policy == npc_death.REMOVE_POLICY,
             'FEATURE_EXPLICIT_NPC_REMOVE_POLICY_REQUIRED')
        need(death_policy is not None, 'FEATURE_NPC_REMOVE_REQUIRES_DEATH')
    return dict(attack_hp_provider=provider, npc_death_policy=death_policy,
                npc_remove_policy=remove_policy)


def _hp_status(value):
    config = value.get('hp_status')
    if config is None:
        return dict(hp_status_policy=None, hp_status_input=None)
    from tools.local_original_session import hp_status
    need(type(config) is dict, 'FEATURE_EXACT_SCHEMA_REQUIRED')
    required=('policy', 'scope', 'target', 'current_hp', 'maximum_hp', 'expected_revision')
    _keys(config, required + (('observe_hud_bar',) if 'observe_hud_bar' in config else ()))
    _keys(config['target'], ('uid', 'map_id'))
    policy = config['policy']
    need(type(policy) is str and policy == hp_status.POLICY,
         'FEATURE_EXPLICIT_HP_STATUS_POLICY_REQUIRED')
    inputs = HpStatusInput(config['target']['uid'], config['target']['map_id'],
        config['current_hp'], config['maximum_hp'], config['expected_revision'], config['scope'],
        config.get('observe_hud_bar', False))
    return dict(hp_status_policy=policy, hp_status_input=inputs)


def _npc_player_hit(value, actor, combat):
    config = value.get('npc_player_hit')
    if config is None:
        return dict(npc_player_hit_policy=None, npc_player_hit_input=None)
    from tools.local_original_session import npc_player_hit, hp_status
    _keys(config, ('policy', 'raw_effect', 'direction', 'observe_hud_bar'))
    need(type(config['policy']) is str and config['policy'] == npc_player_hit.POLICY,
         'FEATURE_NPC_PLAYER_HIT_EXPLICIT_POLICY_REQUIRED')
    need(actor is not None and value['npc']['motion'] is not None
         and value['npc']['goal'] is None and combat['attack_hp_provider'] is not None
         and value.get('hp_status') is None,
         'FEATURE_NPC_PLAYER_HIT_CURRENT_NPC_AND_STATUS_REQUIRED')
    return dict(npc_player_hit_policy=config['policy'],
        npc_player_hit_input=NpcPlayerHitInput(config['raw_effect'], config['direction'], config['observe_hud_bar']),
        hp_status_policy=hp_status.POLICY)


def _npc_player_hit_repeated(value, actor, combat):
    config = value.get('npc_player_hit_repeated')
    if config is None:
        return dict(npc_player_hit_repeated_policy=None, npc_player_hit_repeated_input=None)
    from tools.local_original_session import npc_player_hit, hp_status
    _keys(config, ('policy', 'raw_effect', 'direction', 'observe_hud_bar'))
    need(type(config['policy']) is str and config['policy'] == npc_player_hit.REPEATED_POLICY
         and value.get('npc_player_hit') is None,
         'FEATURE_NPC_PLAYER_HIT_REPEATED_EXCLUSIVE_POLICY_REQUIRED')
    need(actor is not None and value['npc']['motion'] is not None
         and value['npc']['goal'] is None and combat['attack_hp_provider'] is not None
         and value.get('hp_status') is None,
         'FEATURE_NPC_PLAYER_HIT_REPEATED_CURRENT_NPC_AND_STATUS_REQUIRED')
    return dict(npc_player_hit_repeated_policy=config['policy'],
        npc_player_hit_repeated_input=NpcPlayerHitInput(config['raw_effect'], config['direction'], config['observe_hud_bar']),
        hp_status_policy=hp_status.POLICY)


def _npc_approach_hit(value, actor, combat):
    config = value.get('npc_approach_hit')
    if config is None:
        return dict(npc_approach_hit_policy=None, npc_approach_hit_input=None)
    from tools.local_original_session import npc_approach_hit, npc_player_hit, hp_status
    _keys(config, ('policy', 'goal', 'expected_player_grid', 'raw_effect', 'observe_hud_bar'))
    need(type(config['policy']) is str and config['policy'] in (npc_approach_hit.LOCAL_REFERENCE_MELEE_RANGE_ONE, npc_approach_hit.STATIC_STEP_CONTACT_POLICY)
         and all(value.get(name) is None for name in ('npc_player_hit', 'npc_player_hit_repeated', 'hp_status')),
         'FEATURE_NPC_APPROACH_EXCLUSIVE_POLICY_REQUIRED')
    need(actor is not None and value['npc']['motion'] is not None
         and value['npc']['goal'] is None and combat['attack_hp_provider'] is not None
         and type(config['goal']) is list and len(config['goal']) == 2
         and type(config['expected_player_grid']) is list and len(config['expected_player_grid']) == 2,
         'FEATURE_NPC_APPROACH_CURRENT_NPC_EXPLICIT_GOAL_REQUIRED')
    return dict(npc_approach_hit_policy=config['policy'],
        npc_approach_hit_input=NpcApproachHitInput(tuple(config['goal']), tuple(config['expected_player_grid']),
            config['raw_effect'], config['observe_hud_bar']),
        npc_player_hit_repeated_policy=npc_player_hit.REPEATED_POLICY, hp_status_policy=hp_status.POLICY)



def _player_death_recovery(value):
    config = value.get('player_death_recovery')
    if config is None:
        return dict(player_life_policy=None)
    from tools.local_original_session import player_life
    _keys(config, ('label', 'lethal', 'sequence', 'recovery', 'init', 'newlife'))
    # Both labels require every local choice explicitly; no defaults are supplied.
    npc_mode = value.get('npc_player_lethal_recovery') is not None
    need(config['label'] in ((player_life.NPC_POLICY_LABEL,) if npc_mode else
         ('TEST_LOCAL_POLICY', 'EXPLICIT_LOCAL_OWN_PLAYER_HP1_DEAD_RESTART_MAX_SAME_GRID_V1')),
         'FEATURE_EXPLICIT_PLAYER_LIFE_POLICY_LABEL_REQUIRED')
    need(all(value.get(name) is None for name in
             ('hp_status', 'npc_player_hit', 'npc_player_hit_repeated', 'npc_approach_hit',
              'npc_death', 'npc_remove', 'npc_respawn', 'restart')),
         'FEATURE_PLAYER_LIFE_EXCLUSIVE_MODE_REQUIRED')
    policy = player_life.Policy(**config)
    if npc_mode:
        from tools.local_original_session.npc_player_lethal_recovery_focused import Input
        raw = value['npc_player_lethal_recovery']
        _keys(raw, ('goal', 'expected_player_grid', 'raw_effect'))
        need(type(raw['goal']) is list and type(raw['expected_player_grid']) is list,
             'FEATURE_NPC_LETHAL_EXPLICIT_GRID_LIST_REQUIRED')
        payload = Input(tuple(raw['goal']), tuple(raw['expected_player_grid']), raw['raw_effect'])
        need(value['npc'] is not None and value['npc']['motion'] is not None
             and value['npc']['goal'] is None, 'FEATURE_NPC_LETHAL_MOTION_REQUIRED')
    else: payload = None
    return dict(player_life_policy=policy, npc_player_lethal_recovery_input=payload)


def parse(value):
    need(type(value) is dict and {'schema', 'npc'} <= set(value) <= {'schema', 'npc', 'attack', 'inventory', 'restart', 'item_use', 'inventory_update', 'item_equipment', 'npc_hp', 'npc_death', 'npc_remove', 'npc_respawn', 'hp_status', 'npc_player_hit', 'npc_player_hit_repeated', 'item_transfer', 'npc_approach_hit', 'player_death_recovery', 'npc_player_lethal_recovery'},
         'FEATURE_EXACT_SCHEMA_REQUIRED')
    need(value['schema'] == SCHEMA, 'FEATURE_SCHEMA_REQUIRED')
    need(value.get('npc_player_lethal_recovery') is None or value.get('player_death_recovery') is not None,
         'FEATURE_NPC_LETHAL_PAIRED_LIFE_POLICY_REQUIRED')
    life = _player_death_recovery(value)
    item_transfer_policy = None
    if value.get('item_transfer') is not None:
        from tools.local_original_session.item_transfer_session import POLICY as TRANSFER_POLICY
        _keys(value['item_transfer'], ('policy',))
        item_transfer_policy = value['item_transfer']['policy']
        need(type(item_transfer_policy) is str and item_transfer_policy == TRANSFER_POLICY,
             'FEATURE_EXPLICIT_ITEM_TRANSFER_POLICY_REQUIRED')
    restart_policy = None
    if value.get('restart') is not None:
        from tools.local_original_session import restart
        _keys(value['restart'], ('policy',))
        restart_policy = value['restart']['policy']
        need(type(restart_policy) is str and restart_policy == restart.POLICY,
             'FEATURE_EXPLICIT_RESTART_POLICY_REQUIRED')
        restart.source_ready()
    inventory_policy = inventory_frame = inventory_store_policy = inventory_delivery_policy = None
    inventory_reselection_policy = inventory_missing_row_policy = None
    inventory_collection_policy = inventory_collection_grant = None
    inventory_custody_policy = None
    if value.get('inventory') is not None:
        from tools.local_original_session import inventory
        config = value['inventory']
        need(type(config) is dict and {'policy', 'fields'} <= set(config) <= {'policy', 'fields', 'store_policy', 'delivery_policy', 'reselection_policy', 'missing_row_policy', 'collection', 'custody_policy'},
             'FEATURE_EXACT_SCHEMA_REQUIRED')
        inventory_custody_policy = config.get('custody_policy')
        if inventory_custody_policy is not None:
            from tools.local_original_session.item_custody import CUSTODY_POLICY
            need(type(inventory_custody_policy) is str and inventory_custody_policy == CUSTODY_POLICY,
                 'FEATURE_EXPLICIT_INVENTORY_CUSTODY_POLICY_REQUIRED')
        inventory_store_policy = config.get('store_policy')
        if inventory_store_policy is not None:
            from tools.local_original_session import inventory_store
            need(type(inventory_store_policy) is str and inventory_store_policy in (inventory_store.POLICY, inventory_store.COLLECTION_STORE_POLICY),
                 'FEATURE_EXPLICIT_INVENTORY_STORE_POLICY_REQUIRED')
        inventory_delivery_policy = config.get('delivery_policy')
        need(inventory_delivery_policy is None or type(inventory_delivery_policy) is str
             and inventory_delivery_policy == LOCAL_WORLD_READY_ONCE and inventory_store_policy is not None,
             'FEATURE_EXPLICIT_STORED_INVENTORY_DELIVERY_POLICY_REQUIRED')
        inventory_reselection_policy = config.get('reselection_policy')
        if inventory_reselection_policy is not None:
            from tools.local_original_session.restart import POLICY as RESTART_POLICY
            need(type(inventory_reselection_policy) is str
                 and inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
                 and inventory_store_policy is not None
                 and inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
                 and restart_policy == RESTART_POLICY,
                 'FEATURE_EXPLICIT_STORED_INVENTORY_RESELECTION_POLICY_REQUIRED')
        inventory_policy = config['policy']
        need(type(inventory_policy) is str and inventory_policy == inventory.POLICY,
             'FEATURE_EXPLICIT_INVENTORY_POLICY_REQUIRED')
        fields = config['fields']
        need(type(fields) is dict and set(fields) == {str(k) for k in inventory.FIELD_TYPES},
             'FEATURE_EXPLICIT_INVENTORY_FIELDS_REQUIRED')
        fields = {int(k): item for k, item in fields.items()}
        raw = fields[18]
        need(type(raw) is list and len(raw) <= 256
             and all(type(b) is int and 0 <= b <= 255 for b in raw),
             'FEATURE_INVENTORY_RAW_BYTES_REQUIRED')
        fields[18] = bytes(raw)
        inventory_frame = inventory.build_add(fields)
        inventory.validate_frame(inventory_frame)
        inventory_missing_row_policy = config.get('missing_row_policy')
        if inventory_missing_row_policy is not None:
            from tools.local_original_session.broker import INVENTORY_MISSING_ROW_POLICY, INVENTORY_STARTER_FIELDS
            need(type(inventory_missing_row_policy) is str
                 and inventory_missing_row_policy == INVENTORY_MISSING_ROW_POLICY
                 and inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
                 and inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
                 and inventory_store_policy is not None,
                 'FEATURE_EXPLICIT_MISSING_ROW_STARTER_POLICY_REQUIRED')
            need(dict(inventory.validate_frame(inventory_frame).raw_fields) == INVENTORY_STARTER_FIELDS,
                 'FEATURE_EXACT_MISSING_ROW_ATHAME_STARTER_REQUIRED')
        collection = config.get('collection')
        if collection is not None:
            from tools.local_original_session import inventory_store
            _keys(collection, ('policy',) if inventory_custody_policy is not None
                  else ('policy', 'grant_policy', 'reserved_uids'))
            inventory_collection_policy = collection['policy']
            need(type(inventory_collection_policy) is str and inventory_collection_policy == inventory.COLLECTION_POLICY
                 and inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
                 and inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
                 and inventory_delivery_policy == LOCAL_WORLD_READY_ONCE and inventory_missing_row_policy is None,
                 'FEATURE_COLLECTION_EXPLICIT_RESTORE_ONLY_REQUIRED')
            if inventory_custody_policy is None:
                reserved = collection['reserved_uids']
                need(type(collection['grant_policy']) is str and collection['grant_policy'] == inventory_store.SECOND_INSTANCE_POLICY
                     and type(reserved) is list and len(reserved) <= 4096
                     and all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in reserved)
                     and len(set(reserved)) == len(reserved),
                     'FEATURE_COLLECTION_EXPLICIT_GRANT_OPTIONS_REQUIRED')
                inventory_collection_grant = (collection['grant_policy'], frozenset(reserved))
        else:
            from tools.local_original_session import inventory_store
            need(inventory_store_policy is None or inventory_store_policy == inventory_store.POLICY,
                 'FEATURE_COLLECTION_POLICY_REQUIRED')
    item_use_policy = None
    if value.get('item_use') is not None:
        from tools.local_original_session import item_use_session
        _keys(value['item_use'], ('policy',))
        item_use_policy = value['item_use']['policy']
        need(type(item_use_policy) is str and item_use_policy == item_use_session.POLICY,
             'FEATURE_EXPLICIT_ITEM_USE_POLICY_REQUIRED')
        need(inventory_policy is not None and inventory_store_policy is not None,
             'FEATURE_ITEM_USE_REQUIRES_STORED_INVENTORY')
    item_equipment_policy, item_equipment_first_enable = None, False
    if value.get('item_equipment') is not None:
        from tools.local_original_session.item_equipment_effect import POLICY
        _keys(value['item_equipment'], ('policy', 'first_enable'))
        item_equipment_policy = value['item_equipment']['policy']
        item_equipment_first_enable = value['item_equipment']['first_enable']
        need(type(item_equipment_policy) is str and item_equipment_policy == POLICY,
             'FEATURE_EXPLICIT_ITEM_EQUIPMENT_POLICY_REQUIRED')
        need(type(item_equipment_first_enable) is bool,
             'FEATURE_EXPLICIT_ITEM_EQUIPMENT_FIRST_ENABLE_REQUIRED')
        need(item_use_policy is not None and inventory_store_policy is not None
             and inventory_delivery_policy == LOCAL_WORLD_READY_ONCE,
             'FEATURE_ITEM_EQUIPMENT_REQUIRES_STORED_AUTO_INVENTORY_USE')
        need(inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION,
             'FEATURE_ITEM_EQUIPMENT_REQUIRES_SELECTED_GENERATION')
    inventory_update_policy = None
    if value.get('inventory_update') is not None:
        from tools.local_original_session.broker import INVENTORY_UPDATE_POLICY
        _keys(value['inventory_update'], ('policy',))
        inventory_update_policy = value['inventory_update']['policy']
        need(type(inventory_update_policy) is str and inventory_update_policy == INVENTORY_UPDATE_POLICY,
             'FEATURE_EXPLICIT_INVENTORY_UPDATE_POLICY_REQUIRED')
        need(inventory_policy is not None and inventory_store_policy is not None,
             'FEATURE_INVENTORY_UPDATE_REQUIRES_STORED_INVENTORY')
    if item_transfer_policy is not None or inventory_custody_policy is not None:
        from tools.local_original_session.item_transfer_session import validate_mode
        validate_mode(policy=item_transfer_policy, custody_policy=inventory_custody_policy,
            inventory_policy=inventory_policy, frame=inventory_frame,
            store_policy=inventory_store_policy, collection_policy=inventory_collection_policy,
            collection_grant=inventory_collection_grant, reselection_policy=inventory_reselection_policy,
            delivery_policy=inventory_delivery_policy, missing_row_policy=inventory_missing_row_policy,
            restart_policy=restart_policy)
        need(value['npc'] is None and value.get('attack') is None
             and inventory_update_policy is None and item_equipment_first_enable is False,
             'FEATURE_ITEM_TRANSFER_SEPARATE_READONLY_MODE_REQUIRED')
    attack_policy = attack_feedback = None
    if value.get('attack') is not None:
        need(type(value['attack']) is dict and {'policy'} <= set(value['attack']) <= {'policy', 'feedback'},
             'FEATURE_EXACT_SCHEMA_REQUIRED')
        attack_policy = value['attack']['policy']
        need(attack_policy == ATTACK_INTENT_POLICY, 'FEATURE_EXPLICIT_ATTACK_INTENT_POLICY_REQUIRED')
        need(value['npc'] is not None, 'FEATURE_ATTACK_REQUIRES_NPC')
        from tools.local_original_session import attack
        attack.source_ready()
        if value['attack'].get('feedback') is not None:
            from tools.local_original_session.attack_session import FeedbackConfig
            feedback = value['attack']['feedback']
            _keys(feedback, ('policy', 'raw_effect', 'direction', 'self_action'))
            attack_feedback = FeedbackConfig(**feedback)
    if value['npc'] is None:
        combat = _npc_combat(value, None, attack_policy, attack_feedback)
        combat.update(_npc_respawn(value, None, combat))
        combat.update(_hp_status(value))
        combat.update(_npc_player_hit(value, None, combat))
        combat.update(_npc_player_hit_repeated(value, None, combat))
        combat.update(_npc_approach_hit(value, None, combat))
        combat.update(life)
        return Features(inventory_policy=inventory_policy, inventory_frame=inventory_frame,
                        restart_policy=restart_policy, inventory_store_policy=inventory_store_policy,
                        inventory_delivery_policy=inventory_delivery_policy, item_use_policy=item_use_policy,
                        inventory_update_policy=inventory_update_policy,
                        inventory_reselection_policy=inventory_reselection_policy,
                        item_equipment_policy=item_equipment_policy,
                        item_equipment_first_enable=item_equipment_first_enable,
                        inventory_missing_row_policy=inventory_missing_row_policy, inventory_collection_policy=inventory_collection_policy,
                        inventory_collection_grant=inventory_collection_grant,
                        inventory_custody_policy=inventory_custody_policy, item_transfer_policy=item_transfer_policy, **combat)
    config = value['npc']
    _keys(config, ('spawn', 'motion', 'goal'))
    spawn = config['spawn']
    _keys(spawn, ('fields', 'map_id', 'policy'))
    fields = spawn['fields']
    need(type(fields) is dict and set(fields) == {str(key) for key in npc.FIELDS},
         'NPC_ALL_REQUIRED_AND_TEMPLATE39_EXPLICIT_ONLY')
    actor = npc.NpcSpawn({int(key): item for key, item in fields.items()},
                         map_id=spawn['map_id'], policy=spawn['policy'])
    npc.source_ready()
    combat = _npc_combat(value, actor, attack_policy, attack_feedback)
    combat.update(_npc_respawn(value, actor, combat))
    combat.update(_hp_status(value))
    combat.update(_npc_player_hit(value, actor, combat))
    combat.update(_npc_player_hit_repeated(value, actor, combat))
    combat.update(_npc_approach_hit(value, actor, combat))
    combat.update(life)
    goal = config['goal']
    need(goal is None or type(goal) is list and len(goal) == 2, 'FEATURE_EXPLICIT_NPC_GOAL_REQUIRED')
    if goal is not None:
        goal = tuple(goal)
        movement.authority.pack_grid(*goal)
    if config['motion'] is None:
        need(goal is None, 'FEATURE_NPC_GOAL_REQUIRES_MOTION')
        return Features((actor,), attack_policy=attack_policy, attack_feedback=attack_feedback,
                        restart_policy=restart_policy, inventory_store_policy=inventory_store_policy,
                        inventory_policy=inventory_policy, inventory_frame=inventory_frame,
                        inventory_delivery_policy=inventory_delivery_policy, item_use_policy=item_use_policy,
                        inventory_update_policy=inventory_update_policy,
                        inventory_reselection_policy=inventory_reselection_policy,
                        item_equipment_policy=item_equipment_policy,
                        item_equipment_first_enable=item_equipment_first_enable,
                        inventory_missing_row_policy=inventory_missing_row_policy, inventory_collection_policy=inventory_collection_policy,
                        inventory_collection_grant=inventory_collection_grant,
                        inventory_custody_policy=inventory_custody_policy, item_transfer_policy=item_transfer_policy, **combat)
    motion = config['motion']
    _keys(motion, ('interval_ns', 'policy', 'goal_policy'))
    # Reuse the actual consumer validator; self_uid=0 is only a validation
    # sentinel. The real realm checks UID collisions against its real profile.
    npc_motion.NpcMotion(actor, self_uid=0, interval_ns=motion['interval_ns'],
                         policy=motion['policy'])
    npc_motion.source_ready(motion['policy'])
    from tools.local_original_session.npc_session import NpcSessionConfig
    NpcSessionConfig(spawns=(actor,), interval_ns=motion['interval_ns'],
                     policy=motion['policy'], goal_policy=motion['goal_policy'])
    return Features((actor,), motion['interval_ns'], motion['policy'], motion['goal_policy'], goal,
                    attack_policy, inventory_policy, inventory_frame, attack_feedback, restart_policy,
                    inventory_store_policy, inventory_delivery_policy, item_use_policy, inventory_update_policy,
                    inventory_reselection_policy, item_equipment_policy, item_equipment_first_enable,
                    inventory_missing_row_policy, inventory_collection_policy=inventory_collection_policy,
                    inventory_collection_grant=inventory_collection_grant,
                        inventory_custody_policy=inventory_custody_policy, item_transfer_policy=item_transfer_policy, **combat)


def _finite_json(_):
    raise ValueError('FEATURE_FINITE_JSON_REQUIRED')


def load(path):
    if path is None:
        return Features()
    need(isinstance(path, Path), 'FEATURE_CONFIG_PATH_REQUIRED')
    with path.open('rb') as stream:
        raw = stream.read(32769)
    need(len(raw) <= 32768, 'FEATURE_CONFIG_TOO_LARGE')
    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_finite_json)
    return parse(value)
