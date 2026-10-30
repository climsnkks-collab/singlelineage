"""Offline undead-melee policy/HP-consumer checks; no game/socket/native PASS."""
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import random
import unittest
from unittest.mock import Mock

from tools.local_original_session import game_data, world_combat as combat


MONSTER_TABLES = (
    'm1/monsters.json', 'm3/monsters.json', 'm4/monsters.json',
    'm5/monsters.json', 'm6/monsters.json', 'm6/map_expansion2_population.json',
    'm6/map0_population.json', 'm6/field_population.json',
)


class UndeadDamageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = game_data.load_m1()
        cls.zombie = cls.data.monsters[27]

    def profile(self, enchant=0, item_id=39):
        weapon = replace(combat.weapon_from_item(self.data.items[item_id]), enchant=enchant)
        # STR13 is the existing +1 STR damage table entry used by the video.
        return combat.PcProfile(60, 1, 0, 13, 13, weapon=weapon)

    def test_all_startup_tables_project_sourced_category_and_existing_reference(self):
        base = Path(game_data.__file__).parent / 'data'
        unique = {}
        for relative in MONSTER_TABLES:
            raw = json.loads((base / relative).read_text(encoding='utf-8'))
            parsed = game_data._monsters(raw)
            for row in raw['monsters']:
                monster = parsed[row['template_id']['value']]
                self.assertEqual(monster.undead, row['l1j_undead']['value'])
                self.assertEqual(monster.sources['l1j_undead'].kind, 'l1j')
                self.assertIn('npc.undead', monster.sources['l1j_undead'].ref)
                pair = monster.l1j_npcid, monster.undead
                self.assertEqual(unique.setdefault(monster.template_id, pair), pair)
        reference = json.loads((base / 'm3/player_spells.json').read_text(encoding='utf-8'))
        reference = reference['local_policy']['npc_status_reference']
        for tid, row in reference.items():
            self.assertEqual(unique[int(tid)], (row['l1j_npcid'], row['undead']))
        row = json.loads((base / 'm1/monsters.json').read_text(encoding='utf-8'))['monsters'][0]
        row.pop('l1j_undead')
        self.assertIsNone(game_data._monsters({'monsters': [row]})[0].undead)
        print('UNDEAD_SOURCE_ROWS', sum(len(json.loads((base / f).read_text(encoding='utf-8'))
              ['monsters']) for f in MONSTER_TABLES), 'UNIQUE', len(unique),
              'CATEGORIES', dict(sorted(Counter(v[1] for v in unique.values()).items())),
              'EXISTING_REFERENCE_MATCHES', len(reference))

    def test_only_video_confirmed_weapons_are_admitted(self):
        actual = {item.template_id for item in self.data.items.values()
                  if item.kind == 'weapon' and combat.weapon_from_item(item).undead_bonus}
        self.assertEqual(actual, {39, 278})
        # Angel staff's Turn Undead proc and silver-name/material candidates
        # have no explicit evidence of this bonus in the supplied video.
        for item_id in (1, 11, 358, 359, 360, 3018):
            self.assertFalse(combat.weapon_from_item(self.data.items[item_id]).undead_bonus)

    def test_additive_enchant_str_weapon_bonus_and_both_undead_categories(self):
        for item_id in (39, 278):
            for category in (1, 3):
                for size in ('small', 'large'):
                    pc = self.profile(6, item_id)
                    pc = replace(pc, weapon=replace(pc.weapon, damage=3))
                    maximum = pc.weapon.large if size == 'large' else pc.weapon.small
                    rng = Mock(randint=Mock(side_effect=[20, 1, maximum, 16]))
                    swing = combat.pc_hits_npc(pc, replace(self.zombie, undead=category, size=size), rng)
                    self.assertEqual(swing, combat.Swing(True, maximum + 1 + 6 + 3 + 16))
                    self.assertEqual(rng.randint.call_args.args, (1, 16))
                    self.assertEqual(rng.randint.call_count, 4)

    def test_non_undead_ineligible_weapon_ranged_and_miss_do_not_roll_bonus(self):
        for category in (None, 0, 2, 5):
            rng = Mock(randint=Mock(side_effect=[20, 1, 4]))
            swing = combat.pc_hits_npc(self.profile(6), replace(self.zombie, undead=category), rng)
            self.assertEqual(swing, combat.Swing(True, 11))
            self.assertEqual(rng.randint.call_count, 3)
        for item_id in (1, 358, 3018):
            pc = self.profile(6, item_id)
            rng = Mock(randint=Mock(side_effect=[20, 1, pc.weapon.small]))
            swing = combat.pc_hits_npc(pc, self.zombie, rng)
            self.assertEqual(swing.damage, pc.weapon.small + pc.weapon.damage + 6 + 1)
            self.assertEqual(rng.randint.call_count, 3)
        from tools.local_original_session.world_ammo import ArrowDef
        rng = Mock(randint=Mock(side_effect=[20, 1, 3]))
        arrow = ArrowDef(0, 'fixture arrow', 3, 9)
        pc = self.profile(6)
        swing = combat.pc_hits_npc(pc, self.zombie, rng, arrow=arrow)
        self.assertEqual(swing.damage, 3 + pc.weapon.damage + 6 + combat.DEX_DMG[13])
        self.assertEqual(rng.randint.call_count, 3)
        rng = Mock(randint=Mock(side_effect=[1, 100]))
        self.assertEqual(combat.pc_hits_npc(pc, self.zombie, rng), combat.Swing(False, 0))
        self.assertEqual(rng.randint.call_count, 2)

    def test_seeded_samples_match_inclusive_range_and_local_uniform_mean(self):
        # Paired RNG state isolates the added die from weapon/status/enchant
        # damage and hit/miss. This checks our policy, not the video's PDF.
        for enchant in (0, 6, 8, 9):
            rng, baseline = random.Random(20261030 + enchant), random.Random()
            pc = self.profile(enchant)
            plain = replace(pc, weapon=replace(pc.weapon, undead_bonus=False))
            values, totals, misses = [], [], 0
            for _ in range(10000):
                baseline.setstate(rng.getstate())
                swing = combat.pc_hits_npc(pc, self.zombie, rng)
                before = combat.pc_hits_npc(plain, self.zombie, baseline)
                self.assertEqual(swing.landed, before.landed)
                if swing.landed:
                    values.append(swing.damage - before.damage)
                    totals.append(swing.damage)
                else:
                    misses += 1
            maximum, expected = 10 + enchant, (11 + enchant) / 2
            self.assertEqual((min(values), max(values)), (1, maximum))
            self.assertLess(abs(sum(values) / len(values) - expected), .15)
            self.assertEqual((min(totals), max(totals)), (3 + enchant, 15 + 2 * enchant))
            print('UNDEAD_SAMPLE', json.dumps(dict(enchant=enchant, seed=20261030 + enchant,
                  attempts=10000, hits=len(values), misses=misses,
                  bonus_min=min(values), bonus_max=max(values),
                  bonus_mean=round(sum(values) / len(values), 6), expected_mean=expected,
                  total_min=min(totals), total_max=max(totals))))

    def test_real_pc_attack_consumes_bonus_in_npc_hp_and_keeps_cadence(self):
        from tools.local_original_session.world_ai_tests import GridTerrain, status_fields
        from tools.local_original_session.world_visibility import WorldView
        # Development fixture: actual sourced zombie and equipment definitions,
        # a local spawn rectangle and isolated in-memory HP; no saved character.
        spawn = next(s for s in self.data.spawns if s.group_id == 'm1_orc')
        spawn = replace(spawn, template_id=27, target_count=1)
        now = [100.0]
        view = WorldView.create(data=replace(self.data, spawns=(spawn,)),
                               terrain=GridTerrain(), clock=lambda: now[0], rng=random.Random(3))
        self.addCleanup(view.close)
        state = view.bind_pc(1, self.profile(6), status_fields(500))
        view.update_pc(1, 0, 32590, 32880, reset=True)
        group = view.spawner.groups[0]
        slot = group.slots[0]
        target = view.entities.get(slot.uid)
        view.update_pc(1, 0, target.x - 1, target.y)
        slot.hp = 100
        view.drain(1)
        view.combat.rng = Mock(randint=Mock(side_effect=[20, 1, 4, 16]))
        frames = view.pc_attack(1, target.uid)
        self.assertEqual(slot.hp, 73)
        self.assertTrue(any(int.from_bytes(wire[2:4], 'little') == combat.ATTACK_OPCODE
                            for wire in frames))
        self.assertEqual(view.combat.rng.randint.call_count, 4)
        self.assertEqual(view.pc_attack(1, target.uid), [])
        self.assertEqual(slot.hp, 73)
        self.assertEqual(view.combat.rng.randint.call_count, 4)
        now[0] += 2
        view.combat.rng = Mock(randint=Mock(side_effect=[1, 100]))
        view.pc_attack(1, target.uid)
        self.assertEqual(slot.hp, 73)
        self.assertEqual(view.combat.rng.randint.call_count, 2)
        print('UNDEAD_HP_CONSUMER weapon39+6 zombie27 HP100->73; cadence refuses; miss HP73')


if __name__ == '__main__':
    unittest.main()
