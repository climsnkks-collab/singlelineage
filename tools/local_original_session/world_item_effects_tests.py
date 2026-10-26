"""Pure consumable behavior checks; no broker/game/server/save access."""
from array import array
from dataclasses import replace
import random
import unittest

from tools.local_original_session import game_data, world_combat as wc
from tools.local_original_session.world_item_effects import (
    PcAilments, WorldItemEffects, load_effects, random_destination)
from tools.local_original_session.world_maps import MapDestination
from tools.local_original_session.world_terrain import FLAG_COUNT, WorldTerrain
from tools.local_world_protocol import model as world

PC = 65537


class MeanRoll(random.Random):
    def gauss(self, mu, sigma):
        return 0.0


class SmallTerrain:
    def __init__(self, cells):
        self.cells = cells
        self.maps_seen = set()

    def bounds(self, map_id):
        self.maps_seen.add(map_id)
        return (8, 8, 12, 12)

    def can_stand(self, map_id, x, y):
        self.maps_seen.add(map_id)
        return self.cells.get((x, y))


class ItemEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = game_data.load_m1()

    def setUp(self):
        self.combat = wc.WorldCombat(self.data, MeanRoll(5))
        self.fields = {1: PC, 2: 1, 4: 13, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15,
                       10: 1, 11: 200, 12: 3, 13: 10, 14: -10, 15: 1793000000,
                       16: 200, 17: 7, 18: -123, 20: 9}
        self.pc = self.combat.bind_pc(PC, wc.PcProfile(1, 1, 0, 13, 13), self.fields)
        self.effects = WorldItemEffects(self.combat, SmallTerrain({(11, 10): True}))

    def use(self, template, **kwargs):
        return self.effects.use(PC, template, 100.0, **kwargs)

    def test_explicit_classic_mapping_and_reference_ids_separated(self):
        definitions = load_effects()
        self.assertEqual(set(definitions), {14, 15, 130, 17, 296, 495, 126, 162, 23})
        self.assertEqual(definitions[15].reference_id, 40011)
        self.assertEqual(definitions[130].heal_hp, 75)
        for template in (40010, 40011, 40100, 806, 10014):
            result = self.use(template)
            self.assertEqual((result.outcome, result.consume_count), ('unsupported', 0))

    def test_three_healing_amounts_full_status_and_clamp(self):
        for template, base in ((14, 15), (15, 45), (130, 75)):
            with self.subTest(template=template):
                self.pc.hp = 1
                result = self.use(template)
                self.assertEqual((result.healed_hp, self.pc.hp, result.consume_count), (base, 1 + base, 1))
                frame, = result.frames
                self.assertEqual(int.from_bytes(frame[2:4], 'little'), 0x4E38)
                fields = world.decode_payload(0x4E38, frame[4:-2])
                self.assertEqual(fields[10], 1 + base)
                self.assertEqual(fields[12], 3)
                self.assertEqual(fields[18], -123)
        self.pc.hp = 199
        self.assertEqual(self.use(130).healed_hp, 1)
        self.assertEqual(self.pc.hp, 200)
        full = self.use(130)
        self.assertEqual((full.outcome, full.healed_hp, full.consume_count), ('no_effect', 0, 1))

    def test_healing_reuses_existing_gaussian_and_nonnegative_policy(self):
        self.combat.rng = random.Random(73)
        expected = wc.potion_heal(45, random.Random(73))
        self.assertEqual(self.use(15).healed_hp, expected)

    def test_speed_stacks_caps_class_and_expiry_via_combat(self):
        green = self.use(17)
        self.assertEqual((green.buff_kind, green.buff_expires_at), ('haste', 400.0))
        self.assertEqual(int.from_bytes(green.frames[0][2:4], 'little'), 0x4E5B)
        self.assertEqual(self.use(17).buff_expires_at, 700.0)
        brave = self.use(296)
        self.assertEqual(brave.buff_kind, 'brave')
        self.assertAlmostEqual(self.combat.speed_factor(PC, 100.0), 0.745 ** 2)
        self.assertEqual(self.use(495).buff_expires_at, 1900.0)
        self.assertIsNone(self.combat.expire_buff(PC, 'haste', 1899.0))
        self.assertIsNotNone(self.combat.expire_buff(PC, 'haste', 1900.0))
        self.assertIsNotNone(self.combat.expire_buff(PC, 'brave', 1900.0))
        self.assertEqual(self.combat.speed_factor(PC, 1900.0), 1.0)
        self.pc.profile = replace(self.pc.profile, character_class=2)
        no_effect = self.use(296)
        self.assertEqual((no_effect.outcome, no_effect.consume_count, no_effect.frames), ('no_effect', 1, ()))

    def test_unbound_and_dead_pc_do_not_change_or_consume(self):
        ailments = PcAilments('damage_poison')
        for dead in (False, True):
            uid = PC if dead else PC + 1
            self.pc.dead = dead
            for template in load_effects():
                result = self.effects.use(uid, template, 100.0, ailments=ailments,
                    position=MapDestination(0, 10, 10, 0))
                self.assertEqual((result.outcome, result.consume_count), ('refused', 0))
        self.assertEqual((self.pc.hp, self.pc.buffs, ailments.poison), (1, {}, 'damage_poison'))

    def test_cure_requires_explicit_state_and_only_clears_poison(self):
        self.assertEqual(self.use(126).reason, 'POISON_STATE_UNSUPPLIED')
        ailments = PcAilments('damage_poison')
        result = self.use(126, ailments=ailments)
        self.assertTrue(result.poison_cured)
        self.assertIsNone(ailments.poison)
        self.assertEqual((result.consume_count, result.frames, self.pc.hp), (1, (), 1))
        self.assertIsNone(result.requirements[0].opcode)
        self.assertEqual(self.use(126, ailments=ailments).outcome, 'no_effect')

    def test_return_uses_existing_town_and_is_only_a_proposal(self):
        position = MapDestination(2, 10, 10, 0)
        result = self.use(162, position=position)
        town = self.data.town
        self.assertEqual(result.destination, MapDestination(town.map_id, town.respawn_x, town.respawn_y, 5))
        self.assertEqual(result.outcome, 'destination_proposed')
        self.assertEqual(result.frames, ())
        self.assertEqual([(r.kind, r.opcode) for r in result.requirements],
                         [('teleport', None), ('map_notify', 0x4E95)])
        self.assertEqual(position, MapDestination(2, 10, 10, 0))
        same_map = self.use(162, position=MapDestination(0, 10, 10, 0))
        self.assertEqual(len(same_map.requirements), 1)

    def test_random_teleport_stays_on_map_and_ignores_unknown_blocked_current(self):
        terrain = SmallTerrain({(10, 10): True, (11, 10): True, (12, 10): False, (9, 10): None})
        self.effects.terrain = terrain
        result = self.use(23, position=MapDestination(2, 10, 10, 0))
        self.assertEqual(result.destination, MapDestination(2, 11, 10, 5))
        self.assertEqual(terrain.maps_seen, {2})
        self.assertEqual(result.frames, ())
        self.assertEqual([(r.kind, r.opcode) for r in result.requirements], [('teleport', None)])
        self.assertEqual(self.use(23).consume_count, 0)

    def test_random_teleport_no_terrain_or_no_valid_tile_does_not_consume(self):
        position = MapDestination(0, 10, 10, 0)
        self.effects.terrain = None
        self.assertEqual(self.use(23, position=position).reason, 'TERRAIN_UNSUPPLIED')
        self.effects.terrain = SmallTerrain({(10, 10): True})
        result = self.use(23, position=position)
        self.assertEqual((result.reason, result.consume_count, result.destination),
                         ('NO_KNOWN_STANDABLE_DESTINATION', 0, None))

    def test_sparse_destination_reservoir_fallback_after_rejection_misses(self):
        class MissFirst(random.Random):
            attempts = 0

            def randint(self, a, b):
                self.attempts += 1
                return a  # (8,8) is unknown; all 32 initial attempts miss.

        rng = MissFirst(7)
        terrain = SmallTerrain({(11, 10): True})
        result = random_destination(MapDestination(2, 10, 10, 0), terrain, rng)
        self.assertEqual(rng.attempts, 64)
        self.assertEqual(result, MapDestination(2, 11, 10, 5))

    def test_random_destination_uses_real_classic_can_stand_and_radius(self):
        terrain = WorldTerrain({2: {(0, 0): array('H', [0]) * FLAG_COUNT}})
        position = MapDestination(2, 30, 30, 0)
        for seed in range(5):
            result = random_destination(position, terrain, random.Random(seed), radius=2)
            self.assertEqual(result.map_id, 2)
            self.assertTrue(terrain.can_stand(result.map_id, result.x, result.y))
            self.assertLessEqual(max(abs(result.x-30), abs(result.y-30)), 2)
            self.assertNotEqual((result.x, result.y), (30, 30))


if __name__ == '__main__':
    unittest.main()
