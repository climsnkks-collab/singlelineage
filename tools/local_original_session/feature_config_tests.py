"""Bounded config/real consumer validation only; no listener or native process."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.local_original_session import feature_config as f, npc, npc_motion
from tools.local_original_session.npc_tests import fields


def config():
    return dict(schema=f.SCHEMA, npc=dict(
        spawn=dict(fields={str(key): value for key, value in fields().items()},
                   map_id=0, policy=npc.POLICY),
        motion=dict(interval_ns=1000000, policy=npc_motion.LOCAL_PRE_STEP,
                    goal_policy='EXPLICIT_LOCAL_AXIS_SIGN_GOAL'), goal=None))


class FeatureTests(unittest.TestCase):
    def test_world_ready_delivery_is_local_opt_in_and_requires_store_policy(self):
        from tools.local_original_session import inventory, inventory_tests, inventory_store
        raw = {str(k): list(v) if type(v) is bytes else v
               for k, v in inventory_tests.explicit_fields().items()}
        value = dict(schema=f.SCHEMA, npc=None,
                     inventory=dict(policy=inventory.POLICY, fields=raw, store_policy=inventory_store.POLICY))
        self.assertIsNone(f.parse(value).inventory_delivery_policy)
        self.assertIsNone(f.Features().inventory_delivery_policy)
        value['inventory']['delivery_policy'] = f.LOCAL_WORLD_READY_ONCE
        self.assertEqual(f.parse(value).inventory_delivery_policy, f.LOCAL_WORLD_READY_ONCE)
        for wrong in (True, 'UNKNOWN', {}, 1):
            candidate = copy.deepcopy(value); candidate['inventory']['delivery_policy'] = wrong
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, 'DELIVERY_POLICY'):
                f.parse(candidate)
        del value['inventory']['store_policy']
        with self.assertRaisesRegex(ValueError, 'DELIVERY_POLICY'): f.parse(value)

    def test_inventory_explicit_raw_subset_is_npc_independent_and_canonical(self):
        from tools.local_original_session import inventory, inventory_tests
        fields = inventory_tests.explicit_fields()
        raw = {str(k): list(v) if type(v) is bytes else v for k, v in fields.items()}
        value = dict(schema=f.SCHEMA, npc=None, inventory=dict(policy=inventory.POLICY, fields=raw))
        parsed = f.parse(value)
        self.assertEqual(parsed.spawns, ())
        self.assertEqual(parsed.inventory_policy, inventory.POLICY)
        self.assertEqual(parsed.inventory_frame, inventory.build_add(fields))
        self.assertEqual(dict(inventory.validate_frame(parsed.inventory_frame).raw_fields), fields)
        self.assertIsNone(f.parse(dict(schema=f.SCHEMA, npc=None)).inventory_frame)
        self.assertIsNone(f.parse(dict(schema=f.SCHEMA, npc=None, inventory=None)).inventory_frame)
        edits = [lambda x: x['inventory'].update(policy='UNKNOWN'),
                 lambda x: x['inventory'].update(extra=True),
                 lambda x: x['inventory']['fields'].pop('26'),
                 lambda x: x['inventory']['fields'].update({'19': {}}),
                 lambda x: x['inventory']['fields'].update({'1': True}),
                 lambda x: x['inventory']['fields'].update({'4': -1}),
                 lambda x: x['inventory']['fields'].update({'24': 0}),
                 lambda x: x['inventory']['fields'].update({'18': 'raw'}),
                 lambda x: x['inventory']['fields'].update({'18': [True]}),
                 lambda x: x['inventory']['fields'].update({'18': [256]}),
                 lambda x: x['inventory']['fields'].update({'18': [0] * 257})]
        for edit in edits:
            candidate = copy.deepcopy(value); edit(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                f.parse(candidate)

    def test_attack_optional_key_preserves_old_schema_and_requires_explicit_npc_policy(self):
        previous = config()
        self.assertIsNone(f.parse(previous).attack_policy)
        self.assertIsNone(f.parse(dict(previous, attack=None)).attack_policy)
        previous['attack'] = dict(policy=f.ATTACK_INTENT_POLICY)
        self.assertEqual(f.parse(previous).attack_policy, f.ATTACK_INTENT_POLICY)
        for value in (dict(schema=f.SCHEMA, npc=None, attack=previous['attack']),
                      dict(previous, attack=True), dict(previous, attack={}),
                      dict(previous, attack=dict(policy='UNKNOWN')),
                      dict(previous, attack=dict(policy=f.ATTACK_INTENT_POLICY, damage=0))):
            with self.subTest(value=value), self.assertRaises(ValueError):
                f.parse(value)

    def test_feedback_requires_explicit_exact_values_and_old_intent_remains_off(self):
        from tools.local_original_session import attack_feedback
        value = config()
        value['attack'] = dict(policy=f.ATTACK_INTENT_POLICY)
        self.assertIsNone(f.parse(value).attack_feedback)
        value['attack']['feedback'] = dict(policy=attack_feedback.POLICY,
            raw_effect=0, direction=8, self_action=True)
        result = f.parse(value)
        self.assertEqual((result.attack_feedback.raw_effect, result.attack_feedback.direction,
                          result.attack_feedback.self_action), (0, 8, True))
        for key, wrong in (('policy', 'UNKNOWN'), ('raw_effect', True), ('raw_effect', 1 << 31),
                           ('direction', True), ('direction', 9), ('self_action', None),
                           ('self_action', 1)):
            candidate = copy.deepcopy(value); candidate['attack']['feedback'][key] = wrong
            with self.subTest(key=key, wrong=wrong), self.assertRaises(ValueError):
                f.parse(candidate)
        candidate = copy.deepcopy(value); del candidate['attack']['feedback']['self_action']
        with self.assertRaises(ValueError): f.parse(candidate)
        candidate = copy.deepcopy(value); candidate['attack']['feedback']['damage'] = 0
        with self.assertRaises(ValueError): f.parse(candidate)

    def test_restart_explicit_policy_is_independent_and_old_config_remains_off(self):
        from tools.local_original_session import restart
        self.assertIsNone(f.parse(dict(schema=f.SCHEMA, npc=None)).restart_policy)
        enabled = f.parse(dict(schema=f.SCHEMA, npc=None, restart=dict(policy=restart.POLICY)))
        self.assertEqual(enabled.restart_policy, restart.POLICY)
        self.assertEqual(enabled.spawns, ())
        self.assertIsNone(enabled.attack_policy)
        from tools.local_original_session.launcher import ProductFeatureFactory
        factory = ProductFeatureFactory(None, product='sibling-manual-play-spawn',
            control_mode='manual', directory=Path('.'), config=enabled)
        self.assertEqual(factory.broker_options(), dict(restart_policy=restart.POLICY))
        for candidate in (True, {}, {'policy': True}, {'policy': 'UNKNOWN'},
                          {'policy': restart.POLICY, 'success': True}):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                f.parse(dict(schema=f.SCHEMA, npc=None, restart=candidate))

    def test_inventory_store_policy_is_explicit_and_optional_without_raw_defaults(self):
        from tools.local_original_session import inventory, inventory_tests, inventory_store
        raw = {str(k): list(v) if type(v) is bytes else v for k, v in inventory_tests.explicit_fields().items()}
        value = dict(schema=f.SCHEMA, npc=None, inventory=dict(policy=inventory.POLICY, fields=raw))
        self.assertIsNone(f.parse(value).inventory_store_policy)
        value['inventory']['store_policy'] = inventory_store.POLICY
        parsed = f.parse(value)
        self.assertEqual(parsed.inventory_store_policy, inventory_store.POLICY)
        for wrong in (True, 'UNKNOWN', {}, 1):
            candidate = copy.deepcopy(value); candidate['inventory']['store_policy'] = wrong
            with self.subTest(wrong=wrong), self.assertRaises(ValueError): f.parse(candidate)
        candidate = copy.deepcopy(value); del candidate['inventory']['fields']['24']
        with self.assertRaises(ValueError): f.parse(candidate)

    def test_absent_and_explicit_off_have_no_broker_overrides(self):
        for feature in (f.load(None), f.parse(dict(schema=f.SCHEMA, npc=None))):
            self.assertEqual(feature.spawns, ())
            self.assertIsNone(feature.interval_ns)

    def test_all_explicit_values_reach_real_consumers(self):
        feature = f.parse(config())
        self.assertEqual(feature.interval_ns, 1000000)
        self.assertEqual(feature.motion_policy, npc_motion.LOCAL_PRE_STEP)
        self.assertEqual(npc.prepare(feature.spawns, self_uid=1)[0][0].fields, fields())
        with self.assertRaisesRegex(ValueError, 'NPC_SELF_UID_COLLISION'):
            npc.prepare(feature.spawns, self_uid=2)

    def test_spawn_only_preserves_motion_off(self):
        value = config(); value['npc']['motion'] = None
        self.assertIsNone(f.parse(value).interval_ns)

    def test_wrong_keys_types_ranges_and_missing_fields_are_rejected(self):
        edits = [lambda x: x.update(other=True),
                 lambda x: x['npc']['spawn'].update(map_id=True),
                 lambda x: x['npc']['spawn'].update(map_id=1),
                 lambda x: x['npc']['motion'].update(interval_ns=True),
                 lambda x: x['npc']['motion'].update(interval_ns=0),
                 lambda x: x['npc']['motion'].update(policy='official'),
                 lambda x: x['npc']['spawn']['fields'].pop('39'),
                 lambda x: x['npc']['spawn']['fields'].update({'2': True}),
                 lambda x: x['npc']['spawn']['fields'].update({'16': True})]
        for edit in edits:
            value = copy.deepcopy(config()); edit(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                f.parse(value)

    def test_file_is_bounded_and_rejects_duplicate_or_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(config()), encoding='utf-8')
            self.assertEqual(f.load(path).spawns[0].uid, 2)
            for text, reason in (('{"schema":1,"schema":2}', 'DUPLICATE'),
                                 ('{"schema":NaN,"npc":null}', 'FINITE'),
                                 (' ' * 32769, 'TOO_LARGE')):
                path.write_text(text, encoding='utf-8')
                with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                    f.load(path)


class ItemUseConfigTests(unittest.TestCase):
    def test_exact_item_use_opt_in_requires_inventory_and_store_in_all_npc_shapes(self):
        from tools.local_original_session import inventory, inventory_tests, inventory_store, item_use_session
        raw = {str(k): list(v) if type(v) is bytes else v for k, v in inventory_tests.explicit_fields().items()}
        stored = dict(policy=inventory.POLICY, fields=raw, store_policy=inventory_store.POLICY)
        for world in (None, config()['npc'], dict(config()['npc'], motion=None)):
            value = dict(schema=f.SCHEMA, npc=world, inventory=stored,
                         item_use=dict(policy=item_use_session.POLICY))
            with self.subTest(npc=world is not None):
                self.assertEqual(f.parse(value).item_use_policy, item_use_session.POLICY)
        value = dict(schema=f.SCHEMA, npc=None, inventory=stored)
        self.assertIsNone(f.parse(value).item_use_policy)
        value['item_use'] = None
        self.assertIsNone(f.parse(value).item_use_policy)
        self.assertIsNone(f.Features().item_use_policy)
        for item in ({}, {'policy': True}, {'policy': 'UNKNOWN'}, {'policy': item_use_session.POLICY, 'extra': 0}):
            value['item_use'] = item
            with self.subTest(item=item), self.assertRaises(ValueError): f.parse(value)
        value['item_use'] = dict(policy=item_use_session.POLICY)
        value['inventory'] = dict(policy=inventory.POLICY, fields=raw)
        with self.assertRaisesRegex(ValueError, 'REQUIRES_STORED_INVENTORY'): f.parse(value)
        value['inventory'] = None
        with self.assertRaisesRegex(ValueError, 'REQUIRES_STORED_INVENTORY'): f.parse(value)


class InventoryUpdateConfigTests(unittest.TestCase):
    def test_trial_is_existing_auto_config_plus_only_update_policy(self):
        from tools.local_original_session import broker
        root = Path(__file__).resolve().parents[2]
        base = root / 'work/local_original_session/integration-1/use-item-product-link/before-runtime-config.json'
        trial = root / 'work/local_original_session/integration-1/inventory-update-product-link/attack-inventory-auto-update-runtime-config.json'
        previous = json.loads(base.read_text(encoding='utf-8-sig'))
        current = json.loads(trial.read_text(encoding='utf-8'))
        self.assertEqual({k: v for k, v in current.items() if k != 'inventory_update'}, previous)
        self.assertNotIn('item_use', current)
        self.assertEqual(f.parse(current).inventory_update_policy, broker.INVENTORY_UPDATE_POLICY)

    def test_exact_optional_policy_requires_stored_inventory_in_every_npc_shape(self):
        from tools.local_original_session import broker, inventory, inventory_tests, inventory_store
        raw = {str(k): list(v) if type(v) is bytes else v for k, v in inventory_tests.explicit_fields().items()}
        stored = dict(policy=inventory.POLICY, fields=raw, store_policy=inventory_store.POLICY)
        self.assertIsNone(f.Features().inventory_update_policy)
        for world in (None, config()['npc'], dict(config()['npc'], motion=None)):
            value = dict(schema=f.SCHEMA, npc=world, inventory=stored,
                inventory_update=dict(policy=broker.INVENTORY_UPDATE_POLICY))
            with self.subTest(world=world is None):
                self.assertEqual(f.parse(value).inventory_update_policy, broker.INVENTORY_UPDATE_POLICY)
        value = dict(schema=f.SCHEMA, npc=None, inventory=stored)
        self.assertIsNone(f.parse(value).inventory_update_policy)
        for malformed in ({}, {'policy': True}, {'policy': 'unknown'},
                          {'policy': broker.INVENTORY_UPDATE_POLICY, 'changes': {4: 2}}):
            value['inventory_update'] = malformed
            with self.subTest(malformed=malformed), self.assertRaises(ValueError): f.parse(value)
        value['inventory_update'] = dict(policy=broker.INVENTORY_UPDATE_POLICY)
        for missing in (None, dict(policy=inventory.POLICY, fields=raw)):
            value['inventory'] = missing
            with self.assertRaisesRegex(ValueError, 'REQUIRES_STORED_INVENTORY'): f.parse(value)


class InventoryReselectionConfigTests(unittest.TestCase):
    def enabled(self, world=None):
        from tools.local_original_session import inventory, inventory_tests, inventory_store, restart
        raw = {str(k): list(v) if type(v) is bytes else v for k, v in inventory_tests.explicit_fields().items()}
        return dict(schema=f.SCHEMA, npc=world, restart=dict(policy=restart.POLICY),
            inventory=dict(policy=inventory.POLICY, fields=raw, store_policy=inventory_store.POLICY,
                delivery_policy=f.LOCAL_WORLD_READY_ONCE, reselection_policy=f.LOCAL_SAVED_ROW_ON_RESELECTION))

    def test_exact_reselection_policy_reaches_features_and_factory_only_when_explicit(self):
        from tools.local_original_session.launcher import ProductFeatureFactory
        for world in (None, config()['npc'], dict(config()['npc'], motion=None)):
            with self.subTest(world=world is None):
                parsed = f.parse(self.enabled(world))
                self.assertEqual(parsed.inventory_reselection_policy, f.LOCAL_SAVED_ROW_ON_RESELECTION)
                if world is None:  # Motion factories require the real retained-reader fixture.
                    factory = ProductFeatureFactory(None, product='sibling-manual-play-spawn',
                        control_mode='manual', directory=Path('.'), config=parsed)
                    self.assertEqual(factory.broker_options()['inventory_reselection_policy'], f.LOCAL_SAVED_ROW_ON_RESELECTION)
                    self.assertEqual(factory.broker_options()['inventory_delivery_policy'], f.LOCAL_WORLD_READY_ONCE)
        value = self.enabled(); del value['inventory']['reselection_policy']
        for parsed in (f.Features(), f.parse(dict(schema=f.SCHEMA, npc=None)), f.parse(value)):
            self.assertIsNone(parsed.inventory_reselection_policy)
            factory = ProductFeatureFactory(None, product='sibling-manual-play-spawn',
                control_mode='manual', directory=Path('.'), config=parsed)
            self.assertNotIn('inventory_reselection_policy', factory.broker_options())
            self.assertNotIn('inventory_delivery_policy', factory.broker_options())
        value['inventory']['reselection_policy'] = None
        self.assertIsNone(f.parse(value).inventory_reselection_policy)

    def test_reselection_rejects_bad_policy_and_missing_any_required_optin(self):
        for bad in (False, True, 0, 1, {}, '', 'UNKNOWN'):
            value = self.enabled(); value['inventory']['reselection_policy'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError): f.parse(value)
        edits = (lambda value: value['inventory'].pop('store_policy'),
            lambda value: value['inventory'].pop('delivery_policy'),
            lambda value: value.pop('restart'),
            lambda value: value['inventory'].update(policy='UNKNOWN'),
            lambda value: value['inventory'].update(unrelated=0))
        for edit in edits:
            value = self.enabled(); edit(value)
            with self.subTest(edit=edit), self.assertRaises(ValueError): f.parse(value)


if __name__ == '__main__':
    unittest.main()
