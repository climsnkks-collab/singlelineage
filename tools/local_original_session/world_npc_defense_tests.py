"""Development-only size/MR connections; no socket/native gameplay PASS."""
from dataclasses import replace
import json
from pathlib import Path
import random
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import game_data, world_combat as combat


class NpcDefenseTests(unittest.TestCase):
    def test_all_consumed_monster_rows_load_size_mr_and_sources(self):
        directory = Path(game_data.__file__).parent / 'data'
        unique = {}
        for relative in ('m1/monsters.json', 'm3/monsters.json', 'm4/monsters.json',
                         'm5/monsters.json', 'm6/monsters.json', 'm6/map_expansion2_population.json'):
            raw = json.loads((directory / relative).read_text(encoding='utf-8'))
            parsed = game_data._monsters(raw)
            for row in raw['monsters']:
                definition = parsed[row['template_id']['value']]
                self.assertEqual(definition.size, row['size']['value'])
                self.assertEqual(definition.mr, row['l1j_mr']['value'])
                self.assertIn('size', definition.sources)
                self.assertIn('l1j_mr', definition.sources)
                self.assertIn(definition.size, ('small', 'large'))
                pair = definition.size, definition.mr
                self.assertEqual(unique.setdefault(definition.template_id, pair), pair)
        # FILL_MONSTERS raised the registered species from 119 to 277.
        self.assertGreaterEqual(len(unique), 277)

    def test_melee_and_arrow_use_actual_target_size(self):
        from tools.local_original_session.world_ammo import ArrowDef
        monster = game_data.load_m1().monsters[5]
        pc = combat.PcProfile(60, 1, 0, 18, 18, weapon=combat.Weapon('fixture', 2, 11))
        for arrow in (None, ArrowDef(0, 'fixture', 3, 9)):
            amounts = []
            for size in ('small', 'large'):
                maximum = ((2 if size == 'small' else 11) if arrow is None
                           else (3 if size == 'small' else 9))
                rng = Mock(randint=Mock(side_effect=[20, 1, maximum]))
                swing = combat.pc_hits_npc(pc, replace(monster, size=size), rng, arrow=arrow)
                self.assertTrue(swing.landed)
                self.assertEqual(rng.randint.call_args.args, (1, maximum))
                amounts.append(swing.damage)
            self.assertEqual(amounts[1] - amounts[0], 9 if arrow is None else 6)

    def test_companion_basic_attack_shares_size_selection(self):
        from tools.local_original_session.world_companion_integration_tests import CompanionWorldViewTests
        fixture = CompanionWorldViewTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        monster = fixture.data.monsters[5]
        profile = replace(fixture.view.companion_profiles[2], level=60, strength=18,
                          weapon=combat.Weapon('fixture', 2, 11))
        for size, maximum in (('small', 2), ('large', 11)):
            fixture.view.combat.rng = Mock(randint=Mock(side_effect=[20, 1, maximum]))
            swing = fixture.view.combat.companion_swing(
                fixture.actor, profile, replace(monster, size=size))
            self.assertTrue(swing.landed)
            self.assertEqual(fixture.view.combat.rng.randint.call_args.args, (1, maximum))


class PlayerNpcMrTests(unittest.TestCase):
    def fixture(self, mr):
        from tools.local_original_session.world_magic_tests import WorldConsumerTests
        fixture = WorldConsumerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.state.profile = replace(fixture.state.profile, level=60)
        fixture.magic.state(1).learned.update((16, 28))
        target = fixture.enemy()
        group, slot = fixture.view.spawner.slot_for(target.uid)
        group.monster = replace(group.monster, mr=mr)
        slot.hp = 500
        fixture.view.combat.rng = random.Random(8)
        return fixture, target

    def test_single_and_area_attack_damage_use_table_mr(self):
        for key in (3, 16):
            values = []
            for mr in (0, 100):
                fixture, target = self.fixture(mr)
                with patch.object(combat, 'magic_damage', wraps=combat.magic_damage) as observed:
                    fixture.ctx._world_magic_cast(1, key, target.uid, fixture.fixture.now)
                self.assertEqual(observed.call_args.kwargs['mr'], mr)
                values.append(fixture.ctx._world_magic_events[-1]['amount'])
            self.assertGreater(values[0], values[1])

    def test_general_probability_uses_table_mr_beyond_legacy_status_catalog(self):
        from tools.local_original_session import world_magic_status
        outcomes = []
        for mr in (0, 1000):
            fixture, target = self.fixture(mr)
            # Existing fixtures use a legacy catalog MR; actual MonsterDef wins.
            spell = fixture.magic.spells[28]
            fixture.magic.spells[28] = replace(spell, raw={**spell.raw, 'materials': {'value': []}})
            with patch.object(world_magic_status, 'probability', wraps=world_magic_status.probability) as observed:
                fixture.ctx._world_magic_cast(1, 28, target.uid, fixture.fixture.now)
            self.assertEqual(observed.call_args.args[4], mr)
            outcomes.append(fixture.ctx._world_magic_events[-1]['outcome'])
        self.assertEqual(outcomes, ['cast', 'failed'])

    def test_erase_halves_actual_monster_mr_and_is_consumed_once(self):
        fixture, target = self.fixture(80)
        fixture.magic.apply_status(target.uid, 'erase_magic', fixture.fixture.now, 16,
                                   spell=152, target_ref=target.ref)
        with patch.object(combat, 'magic_damage', wraps=combat.magic_damage) as observed:
            fixture.ctx._world_magic_cast(1, 3, target.uid, fixture.fixture.now)
        self.assertEqual(observed.call_args.kwargs['mr'], 40)
        self.assertIsNone(fixture.magic.status(target.uid, 'erase_magic', fixture.fixture.now))


if __name__ == '__main__':
    unittest.main()
