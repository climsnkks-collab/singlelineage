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


def parse(value):
    need(type(value) is dict and {'schema', 'npc'} <= set(value) <= {'schema', 'npc', 'attack', 'inventory', 'restart', 'item_use', 'inventory_update'},
         'FEATURE_EXACT_SCHEMA_REQUIRED')
    need(value['schema'] == SCHEMA, 'FEATURE_SCHEMA_REQUIRED')
    restart_policy = None
    if value.get('restart') is not None:
        from tools.local_original_session import restart
        _keys(value['restart'], ('policy',))
        restart_policy = value['restart']['policy']
        need(type(restart_policy) is str and restart_policy == restart.POLICY,
             'FEATURE_EXPLICIT_RESTART_POLICY_REQUIRED')
        restart.source_ready()
    inventory_policy = inventory_frame = inventory_store_policy = inventory_delivery_policy = None
    inventory_reselection_policy = None
    if value.get('inventory') is not None:
        from tools.local_original_session import inventory
        config = value['inventory']
        need(type(config) is dict and {'policy', 'fields'} <= set(config) <= {'policy', 'fields', 'store_policy', 'delivery_policy', 'reselection_policy'},
             'FEATURE_EXACT_SCHEMA_REQUIRED')
        inventory_store_policy = config.get('store_policy')
        if inventory_store_policy is not None:
            from tools.local_original_session import inventory_store
            need(type(inventory_store_policy) is str and inventory_store_policy == inventory_store.POLICY,
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
    item_use_policy = None
    if value.get('item_use') is not None:
        from tools.local_original_session import item_use_session
        _keys(value['item_use'], ('policy',))
        item_use_policy = value['item_use']['policy']
        need(type(item_use_policy) is str and item_use_policy == item_use_session.POLICY,
             'FEATURE_EXPLICIT_ITEM_USE_POLICY_REQUIRED')
        need(inventory_policy is not None and inventory_store_policy is not None,
             'FEATURE_ITEM_USE_REQUIRES_STORED_INVENTORY')
    inventory_update_policy = None
    if value.get('inventory_update') is not None:
        from tools.local_original_session.broker import INVENTORY_UPDATE_POLICY
        _keys(value['inventory_update'], ('policy',))
        inventory_update_policy = value['inventory_update']['policy']
        need(type(inventory_update_policy) is str and inventory_update_policy == INVENTORY_UPDATE_POLICY,
             'FEATURE_EXPLICIT_INVENTORY_UPDATE_POLICY_REQUIRED')
        need(inventory_policy is not None and inventory_store_policy is not None,
             'FEATURE_INVENTORY_UPDATE_REQUIRES_STORED_INVENTORY')
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
        return Features(inventory_policy=inventory_policy, inventory_frame=inventory_frame,
                        restart_policy=restart_policy, inventory_store_policy=inventory_store_policy,
                        inventory_delivery_policy=inventory_delivery_policy, item_use_policy=item_use_policy,
                        inventory_update_policy=inventory_update_policy,
                        inventory_reselection_policy=inventory_reselection_policy)
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
                        inventory_reselection_policy=inventory_reselection_policy)
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
                    inventory_reselection_policy)


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
