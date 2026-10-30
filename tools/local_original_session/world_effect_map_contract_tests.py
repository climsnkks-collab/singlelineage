"""Pure integration contracts only; no broker, socket, game or save access."""
from dataclasses import replace
import random
import unittest

from tools.local_original_session import game_data, world_combat as combat
from tools.local_original_session.world_ammo import L1J_ARROWS
from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_interest_spawn import InterestSpawner, with_dungeon_data
from tools.local_original_session.world_terrain import WorldTerrain


class FixedHit(random.Random):
    def __init__(self):
        super().__init__(7)
        self.sides = []

    def randint(self, lower, upper):
        self.sides.append(upper)
        return 20 if upper == 20 else 1


class CombatContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = game_data.load_m1()
        cls.monster = next(iter(cls.data.monsters.values()))

    def test_ranged_die_uses_dex_without_melee_die_or_strength(self):
        profile = combat.PcProfile(100, 2, 0, 59, 18,
            weapon=combat.Weapon('bow', 99, 99, damage=2, enchant=3))
        rng = FixedHit()
        shot = combat.pc_hits_npc(profile, self.monster, rng, arrow=L1J_ARROWS[40743])
        self.assertEqual(shot, combat.Swing(True, 1 + 2 + 3 + 4))
        self.assertEqual(rng.sides, [20, 100, 6])
        weaker = replace(profile, strength=1)
        self.assertEqual(combat.pc_hits_npc(weaker, self.monster, FixedHit(),
            arrow=L1J_ARROWS[40743]), shot)

    def test_default_melee_path_keeps_weapon_die(self):
        profile = combat.PcProfile(100, 1, 0, 18, 13,
            weapon=combat.Weapon('sword', 99, 99))
        rng = FixedHit()
        combat.pc_hits_npc(profile, self.monster, rng)
        self.assertEqual(rng.sides, [20, 100, 99])

    def test_readiness_is_side_effect_free_and_dead_refuses(self):
        rng = FixedHit()
        owner = combat.WorldCombat(self.data, rng)
        self.assertFalse(owner.pc_swing_ready(123, 100.0))
        state = owner.bind_pc(123, combat.PcProfile(1, 1, 0, 13, 13), {10: 10, 11: 20})
        self.assertTrue(owner.pc_swing_ready(123, 100.0))
        self.assertEqual((state.next_attack_at, rng.sides), (0.0, []))
        owner.try_pc_swing(123, self.monster, 100.0, arrow=L1J_ARROWS[40743])
        self.assertFalse(owner.pc_swing_ready(123, 100.0))
        state.dead = True
        sides = list(rng.sides)
        self.assertIsNone(owner.try_pc_swing(123, self.monster, 999.0))
        self.assertEqual(rng.sides, sides)


class DungeonDataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = game_data.load_m1()
        cls.data = with_dungeon_data(cls.base)

    def test_opt_in_keeps_m1_inputs_and_adds_existing_sourced_tables(self):
        directory = game_data.M1_DATA_DIR.parent / 'm3'
        monsters = game_data._monsters(game_data._read(directory, 'monsters.json'))
        spawns = game_data._spawns(game_data._read(directory, 'spawns.json'))
        drops, unresolved = game_data._drops(game_data._read(directory, 'drops.json'))
        self.assertEqual(set(self.data.monsters), set(self.base.monsters) | set(monsters))
        self.assertEqual(self.data.spawns, self.base.spawns + spawns)
        self.assertEqual(self.data.drops_unresolved, self.base.drops_unresolved + unresolved)
        for template in monsters:
            self.assertEqual(self.data.monsters[template], monsters[template])
            self.assertEqual(self.data.drops[template], drops[template])
        for name in ('items', 'town', 'action_speed', 'starter', 'pc_exp', 'level_growth'):
            self.assertIs(getattr(self.data, name), getattr(self.base, name))
        self.assertTrue({0, 245, 1, 8} <= set(self.base.monsters))
        for template in set(self.base.monsters) - set(monsters):
            self.assertIs(self.data.monsters[template], self.base.monsters[template])

    def test_real_dungeon_terrain_places_only_on_known_cells_and_dormant_keeps_hp(self):
        terrain = WorldTerrain.load(map_ids=(1, 2))
        spawner = InterestSpawner(EntityRegistry(), self.data,
                                  passable=terrain.can_stand, rng=random.Random(7))
        for map_id in (1, 2):
            rect = next(s.rect for s in self.data.spawns if s.map_id == map_id)
            point = next((x, y) for y in range(rect.y1, rect.y2 + 1)
                         for x in range(rect.x1, rect.x2 + 1)
                         if terrain.can_stand(map_id, x, y) is True)
            self.assertTrue(spawner.update_interest([(map_id, *point)], 100.0))
            active = [g for g in spawner.groups if g.active]
            self.assertTrue(active)
            slots = [s for g in active for s in g.slots if s.uid is not None]
            self.assertTrue(slots)
            for slot in slots:
                entity = spawner.entities.get(slot.uid)
                self.assertTrue(terrain.can_stand(entity.map_id, entity.x, entity.y))
            slot = slots[0]
            spawner.set_hp(slot.uid, 1)
            old_uid = slot.uid
            spawner.update_interest([], 101.0)
            spawner.tick(200.0)
            spawner.update_interest([(map_id, *point)], 201.0)
            self.assertEqual((slot.uid, slot.hp), (old_uid, 1))


if __name__ == '__main__':
    unittest.main()
