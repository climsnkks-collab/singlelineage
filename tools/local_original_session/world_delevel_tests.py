"""Death growth development checks; no client, listener or formal gameplay PASS."""
from dataclasses import replace
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest

from tools.local_original_session import world_reward as reward
from tools.local_original_session import world_combat as combat
from tools.local_original_session import world_core_stats as stats
from tools.local_original_session.world_progress import ProgressOwner, ProgressStore, base_maxima
from tools.local_original_session.game_data import load_m1
from tools.local_native_login_self_actor_hook import hook as actor_hook


class DelevelArithmeticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_m1()

    def inputs(self, *, character_class=0, hp=100, mp=40, con=10, wis=10):
        return reward.RewardPcState(self.data.exp_for_level(11),
            combat.PcProfile(11, character_class, 0, 13, 10, con=con, wis=wis), hp, mp)

    def test_all_classes_reuse_sourced_rolls_without_a_previous_growth_history(self):
        for character_class, loss in enumerate(((18, 5), (24, 2), (16, 8), (13, 10))):
            with self.subTest(character_class=character_class):
                value = self.inputs(character_class=character_class, con=18, wis=18)
                self.assertEqual(reward.delevel_maxima(value, 10, random.Random(7), data=self.data),
                                 (100 - loss[0], 40 - loss[1]))

    def test_each_lost_level_draws_again_and_floors_hp_one_mp_zero(self):
        rng = random.Random(7)
        expected_rng = random.Random(7)
        for _ in range(10):
            expected_rng.randint(0, 1)
            expected_rng.randint(1, 2)
        self.assertEqual(reward.delevel_maxima(self.inputs(hp=3, mp=1), 1, rng), (1, 0))
        self.assertEqual(rng.getstate(), expected_rng.getstate())

    def test_unchanged_level_consumes_no_rng_and_unknown_mp_stays_unknown(self):
        rng = random.Random(7)
        original = rng.getstate()
        self.assertEqual(reward.delevel_maxima(self.inputs(), 11, rng), (100, 40))
        self.assertEqual(rng.getstate(), original)
        self.assertEqual(reward.delevel_maxima(self.inputs(mp=None), 10, rng), (88, None))
        expected = random.Random(7)
        expected.randint(0, 1)
        self.assertEqual(rng.getstate(), expected.getstate())

    def test_decrement_roll_uses_zero_cap_basis_even_at_growth_cap(self):
        growth = self.data.level_growth[0]
        self.assertEqual(reward.delevel_maxima(self.inputs(hp=growth.hp_cap, mp=growth.mp_cap),
                         10, random.Random(7)), (growth.hp_cap - 12, growth.mp_cap - 2))

    def test_invalid_level_or_exp_does_not_consume_rng(self):
        rng = random.Random(7)
        before = rng.getstate()
        for level in (0, 12):
            with self.assertRaises(ValueError):
                reward.delevel_maxima(self.inputs(), level, rng)
        with self.assertRaises(ValueError):
            reward.delevel_maxima(replace(self.inputs(), exp=0), 10, rng)
        self.assertEqual(rng.getstate(), before)


class _DelevelPcFixture(unittest.TestCase):
    def setUp(self):
        self.data = load_m1()
        profile = combat.PcProfile(11, 0, 0, 13, 10, con=30, wis=30)
        fields = dict(actor_hook.profiles()[0].fields)
        fields.update({2: 11, 10: 0, 11: 100, 12: 40, 13: 40})
        self.state = stats._resource_state(combat.PcState(profile, fields, 0, 100))
        self.state.base_growth_con = self.state.base_growth_wis = 10
        self.calculated = SimpleNamespace(max_hp_bonus=40, max_mp_bonus=20)
        stats.project_resources(self.state, self.calculated)
        self.state.status_fields[12] = 60
        self.world = SimpleNamespace(data=self.data, exp={1: self.data.exp_for_level(11)},
            combat=SimpleNamespace(pcs={1: self.state}, rng=random.Random(7)),
            outbox={1: [combat.status_frame(self.state.status_fields, 0), combat.death_frame(1)]})
        self.world.progress = ProgressOwner(self.world)
        self.saved = []
        self.ctx = SimpleNamespace(_world=self.world, _world_progress_errors=[],
            _world_recalculate_uid=lambda uid: stats.project_resources(self.state, self.calculated),
            _world_save_progress=lambda uid: self.saved.append(self.world.progress.snapshot(uid)))

    def die(self):
        from tools.local_original_session.world_core_life import _world_pc_died
        _world_pc_died(self.ctx, 1)


class DelevelPcTests(_DelevelPcFixture):
    def test_death_projects_bases_keeps_equipment_clamps_mp_and_preserves_wire_order(self):
        self.die()
        self.assertEqual(base_maxima(self.state), (88, 38))
        self.assertEqual((self.state.hp, self.state.mp, self.state.max_hp, self.state.max_mp),
                         (0, 58, 128, 58))
        self.assertEqual(self.state.profile.level, 10)
        self.assertEqual((self.saved[-1].max_hp, self.saved[-1].max_mp), (88, 38))
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in self.world.outbox[1]], [0x4e38, 0x4e39])
        self.assertEqual(self.world.outbox[1][0], combat.status_frame(self.state.status_fields, 0))
        stats.project_resources(self.state, self.calculated)
        self.assertEqual(base_maxima(self.state), (88, 38))

    def test_regaining_level_uses_fresh_rolls_without_full_heal(self):
        self.die()
        self.state.hp = 1  # development-only revived state, not a gameplay PASS
        current_mp = self.state.mp
        self.world.combat.rng = random.Random(0)
        missing = self.data.exp_for_level(11) - self.world.exp[1]
        monster = replace(self.data.monsters[0], template_id=-1, kill_exp=missing)
        growth = reward.on_kill(reward.RewardPcState.from_combat(self.state, exp=self.world.exp[1]),
                                monster, self.world.combat.rng, data=self.data)
        self.world.progress.adopt(1, replace(self.saved[-1], exp=growth.new_exp, level=growth.new_level,
                                            max_hp=growth.max_hp, max_mp=growth.max_mp))
        stats.project_resources(self.state, self.calculated)
        self.assertEqual((growth.max_hp, growth.max_mp), (100, 41))
        self.assertEqual((self.state.hp, self.state.mp), (1, current_mp))
        self.assertLess(self.state.hp, self.state.max_hp)

    def test_same_level_death_preserves_maxima_and_rng(self):
        self.world.exp[1] = 16000
        before = self.world.combat.rng.getstate()
        self.die()
        self.assertEqual(base_maxima(self.state), (100, 40))
        self.assertEqual(self.world.combat.rng.getstate(), before)

    def test_directly_selected_companion_returns_growth_bases_to_its_record(self):
        from tools.local_original_session.world_companion import CompanionRecord
        from tools.local_original_session.world_feature_companion import _companion_player_inventory
        member = CompanionRecord(1, 3, 'test', max_hp=100, max_mp=40)
        self.world.companions = SimpleNamespace(records={1: member})
        writer = object()
        ctx = SimpleNamespace(world=self.world, inventory_frame=b'unchanged',
            _companion_inventory=SimpleNamespace(frames={1: b'unchanged'},
                refresh=lambda uid, publish: member.project_resources(self.calculated)),
            _world_bound=lambda writer: True, _world_pcs={id(writer): (writer, 1)},
            _companion_save=lambda owner: None)
        _companion_player_inventory(ctx, writer, None, None, 0, None)
        self.assertEqual((member.max_hp, member.max_mp, member.hp, member.mp), (100, 40, 0, 60))
        self.assertEqual((member.effective_max_hp, member.effective_max_mp), (140, 60))
        member.validate()

    def test_zero_mp_growth_snapshot_survives_existing_store_document_codec(self):
        from tools.local_original_session.world_progress import _decode_document
        self.state.base_max_mp = 1
        self.state.status_fields[13] = 21
        self.die()
        raw = ProgressStore._encode({1: self.saved[-1]}, {})
        rows, bonuses = _decode_document(raw)
        self.assertEqual((rows[1].max_hp, rows[1].max_mp), (88, 0))
        self.assertEqual(bonuses, {})


class DelevelCompanionTests(unittest.TestCase):
    def setUp(self):
        from tools.local_original_session.world_companion_integration_tests import CompanionWorldViewTests
        self.fixture = CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.record = self.fixture.view, self.fixture.record
        self.record.level, self.record.exp = 11, self.view.data.exp_for_level(11)
        self.record.hp, self.record.mp, self.record.max_hp, self.record.max_mp = 100, 40, 100, 40
        self.view.companion_profiles[2] = replace(self.view.companion_profiles[2], con=30, wis=30)
        self.ctx = SimpleNamespace(world=self.view,
            _companion_rows={2: {'attributes': (8, 7, 16, 18, 8, 18)}},
            _companion_errors=[], _companion_death_penalties=[])
        from tools.local_original_session.world_feature_companion import _companion_death_penalty
        self.view.companions.on_death = lambda record, now: _companion_death_penalty(self.ctx, record, now)

    def test_companion_death_uses_own_saved_stats_and_death_once(self):
        rng = random.Random()
        rng.setstate(self.view.combat.rng.getstate())
        expected = reward.delevel_maxima(reward.RewardPcState.from_companion(self.record,
            self.view.companion_profiles[2], attributes=self.ctx._companion_rows[2]['attributes']), 10, rng)
        self.view.companions.die(2, self.fixture.now)
        self.assertEqual((self.record.hp, self.record.mp, self.record.max_hp, self.record.max_mp),
                         (0, min(40, expected[1]), *expected))
        self.assertEqual(self.record.level, 10)
        self.assertEqual(self.view.companion_profiles[2].level, 10)
        after = self.view.combat.rng.getstate()
        self.view.companions.die(2, self.fixture.now)
        self.assertEqual(self.view.combat.rng.getstate(), after)
        self.assertEqual(len(self.ctx._companion_death_penalties), 1)
        self.record.validate()

    def test_companion_regrowth_uses_base_stats_and_preserves_current_vitals(self):
        from tools.local_original_session.world_companion_runtime import FollowerRewardPlan
        self.view.companions.die(2, self.fixture.now)
        self.view.companions.revive(2, self.fixture.now, hp=1)
        before = (self.record.hp, self.record.mp)
        self.view.companion_ai.inventory = SimpleNamespace(characters=self.ctx._companion_rows)
        missing = self.view.data.exp_for_level(11) - self.record.exp
        monster = replace(self.view.data.monsters[0], template_id=-1, kill_exp=missing)
        plan = FollowerRewardPlan(self.view, 1, SimpleNamespace(uid=123, generation=1), monster,
            self.fixture.actor, SimpleNamespace(owner_exp=0, companion_exp=missing, owner_half=0, companion_half=0))
        plan.calculate()
        self.assertLess(plan.growth.max_hp - self.record.max_hp, 15)  # saved CON16, not worn CON30
        plan.commit()
        self.assertEqual(self.record.level, 11)
        self.assertEqual((self.record.hp, self.record.mp), before)

    def test_shared_follower_growth_keeps_pet_profile_when_bags_have_no_character_row(self):
        from tools.local_original_session.world_companion_runtime import FollowerRewardPlan
        self.view.companion_ai.inventory = SimpleNamespace(characters={})
        monster = replace(self.view.data.monsters[0], template_id=-1, kill_exp=1)
        plan = FollowerRewardPlan(self.view, 1, SimpleNamespace(uid=123, generation=1), monster,
            self.fixture.actor, SimpleNamespace(owner_exp=0, companion_exp=1, owner_half=0, companion_half=0))
        plan.calculate()
        self.assertEqual((plan.growth.new_exp, plan.growth.max_hp, plan.growth.max_mp),
                         (self.record.exp + 1, self.record.max_hp, self.record.max_mp))


class DelevelPersistenceTests(_DelevelPcFixture):
    def test_progress_zero_mp_and_equipment_bases_survive_fresh_store(self):
        self.state.base_max_mp = 1
        self.state.status_fields[13] = 21
        self.die()
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder).resolve() / 'characters.json'
            store = ProgressStore(profile)
            store.commit(1, self.saved[-1])
            fresh = ProgressStore(profile).get(1)
            self.assertEqual((fresh.max_hp, fresh.max_mp), (88, 0))
            self.world.progress.adopt(1, fresh)
            stats.project_resources(self.state, self.calculated)
            self.assertEqual((self.state.max_hp, self.state.max_mp), (128, 20))

    def test_joint_companion_owner_snapshot_saves_growth_bases(self):
        from tools.local_original_session.world_companion import CompanionRecord, CompanionStore, record_from_row
        self.die()
        record = CompanionRecord(2, 1, 'test', level=10, exp=self.world.exp[1],
                                 hp=0, mp=0, max_hp=1, max_mp=0, alive=False)
        self.world.companions = SimpleNamespace(records={2: record})
        self.world.companion_owner_half = {}
        self.world.companion_reward_receipts = []
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder).resolve() / 'characters.json'
            store = CompanionStore(profile)
            store.commit(self.world, 1)
            saved = CompanionStore(profile).payload
            self.assertEqual((saved['owners']['1']['max_hp'], saved['owners']['1']['max_mp']), (88, 38))
            restored = record_from_row(saved['records'][0])
            self.assertEqual((restored.hp, restored.mp, restored.max_hp, restored.max_mp), (0, 0, 1, 0))


if __name__ == '__main__':
    unittest.main()
