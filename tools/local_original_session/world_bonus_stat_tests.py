"""Bonus growth/legacy progress/joint recovery tests on disposable profiles."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_store, world_progress as p
from tools.local_original_session import world_warehouse as w
from tools.local_original_session import world_feature_bonus_stat as b
from tools.local_original_session.world_state_services import InventoryTransactions


def item(uid, quantity=1):
    return {1: uid, 2: 895, 3: 0, 4: quantity, 5: 0, 7: 1143, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'elixir', 22: 0, 24: False, 25: 0, 26: False}


class Rules(unittest.TestCase):
    def test_all_native_enums_and_level_entitlement(self):
        for attribute in range(6):
            allocated, elixirs = b.increase(51, (13,) * 6, (b.ZERO, b.ZERO), attribute)
            self.assertEqual(allocated[attribute], 1)
            self.assertEqual(sum(allocated), 1)
            self.assertEqual(elixirs, b.ZERO)
            with self.assertRaisesRegex(ValueError, 'NO_POINTS'):
                b.increase(51, (14,) * 6, (allocated, elixirs), attribute)
        for level in (1, 49, 50):
            with self.assertRaisesRegex(ValueError, 'NO_POINTS'):
                b.increase(level, (13,) * 6, (b.ZERO, b.ZERO), 0)
        self.assertEqual(b.available(55, (1, 1, 1, 0, 0, 0)), 2)
        self.assertEqual(b.available(50, (1, 0, 0, 0, 0, 0)), 0)

    def test_caps_elixir_count_level_and_no_points_consumed(self):
        with self.assertRaisesRegex(ValueError, 'CAP'):
            b.increase(99, (35,) * 6, (b.ZERO, b.ZERO), 0)
        for invalid in (-1, 6, True):
            with self.assertRaisesRegex(ValueError, 'ATTRIBUTE'):
                b.increase(99, (13,) * 6, (b.ZERO, b.ZERO), invalid)
        with self.assertRaisesRegex(ValueError, 'LEVEL'):
            b.increase(49, (13,) * 6, (b.ZERO, b.ZERO), 0, elixir=True)
        bonus = (b.ZERO, b.ZERO)
        for _ in range(5):
            bonus = b.increase(50, (13,) * 6, bonus, 0, elixir=True)
        self.assertEqual(bonus, (b.ZERO, (5, 0, 0, 0, 0, 0)))
        with self.assertRaisesRegex(ValueError, 'COUNT_CAP'):
            b.increase(50, (13,) * 6, bonus, 1, elixir=True)
        self.assertEqual(b.available(51, bonus[0]), 1)

    def test_single_f1_wire_and_duplicate_rejection(self):
        for attribute in range(6):
            self.assertEqual(b._scalar(bytes((8, attribute))), attribute)
        for raw in (b'', b'\x10\x01', b'\x08\x00\x08\x01'):
            with self.assertRaises(ValueError):
                b._scalar(raw)
        self.assertEqual(b.bonus_frame(2), b'\x08\x00\x0f\x4f\x08\x02\0\0')


class Saves(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.profile = Path(temp.name) / 'characters.json'
        roster = inventory_store.realm.CharacterStore(self.profile)
        roster.create(inventory_store.realm.Creation('BonusOne', 0, 0, (13,) * 6))
        self.inv = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                 kit_policy=inventory.KIT_POLICY)
        self.before = inventory.build_kit_frame([item(10, 2), item(11)])
        self.after = inventory.build_kit_frame([item(10, 1), item(11)])
        self.inv.grant(1, self.before)
        self.progress = p.ProgressStore(self.profile)
        self.initial = p.Progress(100, 51, 200, 100, -30)
        self.progress.commit(1, self.initial)
        self.bonus = ((0, 0, 0, 0, 1, 0), (1, 0, 0, 0, 0, 0))
        self.raw = self.progress.prepare_bonus(1, self.initial, *self.bonus)

    def test_optional_field_old_rows_and_all_progress_writers(self):
        self.assertNotIn('bonus_stats', json.loads(self.progress.path.read_bytes())['rows'][0])
        self.progress.replace_document(self.raw)
        from tools.local_original_session.world_combat import PcProfile, PcState
        state = PcState(PcProfile(52, 0, 0, 13, 13),
                        {2: 52, 10: 10, 11: 210, 12: 2, 13: 105, 18: 999}, 10, 210)
        world = NS(combat=NS(pcs={1: state}), exp={1: 200})
        owner = p.ProgressOwner(world)
        owner.attach_store(self.progress)
        value = owner.mark(1)
        self.progress.stage(1, value)
        self.progress.commit(1, value)
        owner.adopt(1, p.Progress(300, 53, 220, 110, -44))
        self.progress.commit(1, owner.snapshot(1))
        fresh = p.ProgressStore(self.profile)
        self.assertEqual(fresh.bonus_stats(1), self.bonus)
        self.assertEqual(fresh.get(1), p.Progress(300, 53, 220, 110, -44))
        self.assertEqual(self.progress.bonus_stats(1), self.bonus)

    def test_progress_write_failure_preserves_old_memory_and_disk(self):
        old = self.progress.path.read_bytes()
        with patch.object(p.os, 'replace', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.progress.replace_document(self.raw)
        self.assertEqual(self.progress.path.read_bytes(), old)
        self.assertEqual(self.progress.bonus_stats(1), (b.ZERO, b.ZERO))

    def test_joint_consumption_recovery_after_inventory_before_progress(self):
        tx = InventoryTransactions(self.inv)
        with patch.object(self.progress, 'replace_document', side_effect=OSError('interrupt')):
            with self.assertRaises(OSError):
                tx.commit_inventory(1, self.before, self.after, progress_store=self.progress,
                    progress_before=self.progress.document(), progress_after=self.raw)
        self.assertEqual(self.inv.restore(1), self.after)
        self.assertNotEqual(self.progress.path.read_bytes(), self.raw)
        self.assertTrue(tx._warehouse.intent_path.exists())
        # A new InventoryStore/ProgressStore/transaction owner completes forward.
        fresh_inv = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                   kit_policy=inventory.KIT_POLICY)
        fresh_tx = InventoryTransactions(fresh_inv)
        fresh_progress = p.ProgressStore(self.profile)
        self.assertEqual(fresh_progress.bonus_stats(1), self.bonus)
        self.assertEqual(fresh_inv.restore(1), self.after)
        self.assertFalse(fresh_tx._warehouse.intent_path.exists())
        # An ordinary later legacy growth write preserves both optional arrays.
        fresh_progress.commit(1, replace(self.initial, level=52, exp=200))
        self.assertEqual(p.ProgressStore(self.profile).bonus_stats(1), self.bonus)

    def test_joint_recovery_after_progress_before_intent_unlink(self):
        tx = InventoryTransactions(self.inv)
        original = Path.unlink
        def interrupted(path, *args, **kwargs):
            if path == tx._warehouse.intent_path:
                raise OSError('unlink interruption')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', interrupted):
            with self.assertRaises(OSError):
                tx.commit_inventory(1, self.before, self.after, progress_store=self.progress,
                    progress_before=self.progress.document(), progress_after=self.raw)
        self.assertEqual(self.progress.path.read_bytes(), self.raw)
        InventoryTransactions(self.inv)
        self.assertEqual(p.ProgressStore(self.profile).bonus_stats(1), self.bonus)
        self.assertFalse(tx._warehouse.intent_path.exists())

    def test_existing_quest_joint_progress_recovery_keeps_optional_growth(self):
        from tools.local_original_session import world_quest_store as q
        from tools.local_original_session.world_quest import QuestState
        self.progress.replace_document(self.raw)
        store = q.QuestStore(self.inv, self.progress)
        state = QuestState('local_material')
        next_state = replace(state, accepted=True, counts=(0,))
        store.commit(1, state, next_state, class_key='knight', reference_before={},
                     reference_after={}, progress_before=self.initial,
                     progress_after=replace(self.initial, level=52, exp=200))
        self.assertEqual(p.ProgressStore(self.profile).bonus_stats(1), self.bonus)

    def test_existing_quest_intent_recovery_with_fresh_progress_owner(self):
        from tools.local_original_session import world_quest_store as q
        from tools.local_original_session.world_quest import QuestState
        self.progress.replace_document(self.raw)
        store = q.QuestStore(self.inv, self.progress)
        state = QuestState('local_material')
        after = replace(self.initial, level=52, exp=200)
        with patch.object(self.progress, 'commit', side_effect=OSError('quest interrupted')):
            with self.assertRaises(OSError):
                store.commit(1, state, replace(state, accepted=True, counts=(0,)),
                    class_key='knight', reference_before={}, reference_after={},
                    progress_before=self.initial, progress_after=after)
        fresh = p.ProgressStore(self.profile)
        q.QuestStore(self.inv, fresh)
        self.assertEqual(fresh.get(1), after)
        self.assertEqual(fresh.bonus_stats(1), self.bonus)

    def test_core_projection_updates_growth_CON_WIS_and_derived_Dex_AC(self):
        from tools.local_original_session import world_core_stats as core, world_stats as s
        from tools.local_original_session.world_combat import PcProfile, PcState
        from tools.local_original_session.world_reward import RewardPcState
        allocated, elixirs = (0, 0, 0, 1, 0, 0), (0, 0, 1, 0, 1, 0)
        self.progress.replace_document(self.progress.prepare_bonus(1, self.initial, allocated, elixirs))
        info = {3: 0, 5: 0, 10: 51, 11: 13, 12: 17, 13: 17, 14: 17, 15: 13, 16: 13}
        position = NS(uid=1, name='BonusOne')
        state = core._resource_state(PcState(PcProfile(51, 0, 0, 13, 17, con=17, wis=17),
            {1: 1, 2: 51, 4: 13, 5: 17, 6: 13, 7: 17, 8: 17, 9: 13,
             10: 10, 11: 200, 12: 2, 13: 100, 14: 0, 18: -30}, 10, 200))
        ctx = NS(progress_store=self.progress, realm=NS(store=NS(select=lambda name: (None, info))),
                 world=NS(combat=NS(pcs={1: state})))
        ctx._world = ctx.world
        ctx.world.progress = NS(lawful_of=lambda uid, fallback: fallback)
        ctx._world_progress_for = lambda uid: self.progress.get(uid)
        ctx.fold_sync_hooks = lambda name, value, *args, **kwargs: (
            b._bonus_base(ctx, value, args[0]) if name == 'base_attributes' else value)
        ctx._world_stats_for = lambda pos, **kwargs: core._world_stats_for(ctx, pos, **kwargs)
        calculated, _, folded = ctx._world_stats_for(position)
        original = s.calculate_stats(s.CharacterStats(51, 0, s.Attributes(13, 17, 17, 17, 13, 13)))
        self.assertLess(calculated.ac, original.ac)
        self.assertGreater(calculated.mr, original.mr)
        core._world_fields_for(ctx, position, state.status_fields)
        growth = RewardPcState.from_combat(state, exp=self.initial.exp)
        self.assertEqual((growth.profile.con, growth.profile.wis), (18, 18))
        self.assertEqual((growth.max_hp, growth.max_mp), (200, 100))
        self.assertEqual((folded[13], folded[14]), (18, 18))

    def test_permanent_base_fold_precedes_derived_and_excludes_equipment(self):
        from tools.local_original_session import world_stats as s
        self.progress.replace_document(self.raw)
        info = {field: 13 for field in b.ATTR_INFO}
        ctx = NS(progress_store=self.progress)
        folded = b._bonus_base(ctx, info, NS(uid=1))
        self.assertEqual(info[13], 13)
        self.assertEqual((folded[11], folded[13]), (14, 14))
        base = s.CharacterStats(51, 0, s.Attributes(13, 13, 13, 13, 13, 13))
        changed = replace(base, attributes=s.Attributes(folded[11], folded[12], folded[13],
                          folded[14], folded[15], folded[16]))
        normal, permanent = s.calculate_stats(base), s.calculate_stats(changed)
        self.assertGreater(permanent.max_weight, normal.max_weight)
        self.assertEqual(permanent.attributes.strength, 14)

    def test_registry_omission_has_no_handler_or_hooks(self):
        from tools.local_original_session.world_handlers import CORE_MODULES, FEATURE_MODULES
        from tools.local_original_session.world_registry import build_registry
        normal = build_registry(CORE_MODULES + FEATURE_MODULES)
        removed = build_registry(CORE_MODULES + tuple(x for x in FEATURE_MODULES if x != 'world_feature_bonus_stat'))
        self.assertIn(b.RAISE, normal.frames)
        self.assertNotIn(b.RAISE, removed.frames)
        self.assertNotIn('base_attributes', removed.hooks)
        self.assertEqual(p.ProgressStore(self.profile).bonus_stats(1), (b.ZERO, b.ZERO))


if __name__ == '__main__':
    unittest.main()
