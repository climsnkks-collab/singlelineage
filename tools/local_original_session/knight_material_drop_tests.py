"""Pure sourced material roll -> owned ground -> pickup checks; no ports/temp/save.

These checks establish LOCAL data/consumer behavior, not a formal quest or
native-client PASS. Rolls use unchanged production probabilities and real RNG.
"""
import random
import unittest

from tools.local_original_session import game_data as gd
from tools.local_original_session.world_combat import PcProfile
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_feature_dungeons import load_dungeon_data
from tools.local_original_session.world_feature_m5 import load_m5_data
from tools.local_original_session.world_ground_items import GroundItems
from tools.local_original_session.world_interest_spawn import with_dungeon_data
from tools.local_original_session.world_reward import RewardPcState, on_kill
from tools.local_original_session.world_scheduler import Scheduler


MATERIALS = ((15, 633, 50000), (15, 639, 50000),
             (520, 650, 50000), (33, 707, 20000))


class KnightMaterialDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_dungeon_data(load_m5_data(
            gd.load_m4(with_dungeon_data(gd.load_m1()))))

    def test_full_data_composition_keeps_own_npc_rates_and_existing_spawns(self):
        for template, item, chance in MATERIALS:
            with self.subTest(template=template, item=item):
                rows = [r for r in self.data.drops[template] if r.item_id == item]
                self.assertEqual(len(rows), 1)
                row, = rows
                self.assertEqual((row.grade, row.chance, row.min_count, row.max_count),
                                 (1, chance, 1, 1))
                self.assertIn(item, self.data.items)
                self.assertTrue(any(s.template_id == template for s in self.data.spawns))

    def test_unmodified_seeded_rolls_reach_owned_ground_and_real_pickup(self):
        exp = self.data.exp_for_level(45)
        state = RewardPcState(exp, PcProfile(45, 1, 0, 13, 10), 200, 10)
        for template, item, _ in MATERIALS:
            with self.subTest(template=template, item=item):
                rng = random.Random(20261029 + item)
                # Keep the production table, rates, and monster unchanged.
                for _attempt in range(1000):
                    reward = on_kill(state, self.data.monsters[template], rng, data=self.data)
                    if (item, 1) in reward.drops:
                        break
                else:
                    self.fail(f'No target material from 1000 seeded real rolls: {item}')
                entities = EntityRegistry()
                pc = entities.add(Kind.PC, 4, 100, 100, uid=1)
                npc = entities.add(Kind.NPC, 4, 100, 100, template_id=template)
                entities.kill(npc.uid)
                scheduler = Scheduler(clock=lambda: 100.0, is_current=entities.is_current)
                ground = GroundItems(entities, scheduler, self.data, passable=lambda *_: True)
                drops = ground.spawn_reward(npc.ref, reward, owner_uid=pc.uid)
                material, = [r for r in drops if r.item_id == item]
                self.assertEqual((material.count, material.grade, material.owner_uid), (1, 1, pc.uid))
                self.assertEqual(ground.pickup(pc.ref, material.ref, 1), (item, 1))
                self.assertIsNone(ground.get(material.ref))


if __name__ == '__main__':
    unittest.main()
