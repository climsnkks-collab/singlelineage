"""Expansion table/asset/terrain contracts; file reads only, no native UI claim."""
from collections import Counter
import json
from pathlib import Path
import re
import unittest

from tools.local_original_session import game_data as gd
from tools.local_original_session.world_terrain import WorldTerrain

ROOT = Path(__file__).resolve().parents[2]
# Retain the original rectangles' partial-standability policy. New rectangles
# are deliberately fully standable, which is a separate expansion contract.
BASE_GROUPS = {
    'm1': {'m1_orc', 'm1_goblin', 'm1_orc_archer', 'm1_werewolf'},
    'm3': {'m3_tic1_zombie', 'm3_tic1_floating_eye', 'm3_tic1_skeleton',
           'm3_tic2_zombie', 'm3_tic2_floating_eye', 'm3_tic2_skeleton',
           'm3_tic2_skeleton_archer', 'm3_tic2_stone_golem', 'm3_tic2_spartoi'},
    'm4': {'m4_gludio_east_zombie', 'm4_gludio_east_skeleton',
           'm4_gludio_east_skeleton_archer'},
}


class ExpansionDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundles = {}
        for name in ('m1', 'm3', 'm4'):
            directory = gd.M1_DATA_DIR.parent / name
            cls.bundles[name] = (gd._monsters(gd._read(directory, 'monsters.json')),
                gd._spawns(gd._read(directory, 'spawns.json')),
                gd._drops(gd._read(directory, 'drops.json'))[0])
        cls.terrain = WorldTerrain.load(map_ids=(0, 1, 2, 4))
        cls.native = {}
        with (ROOT / 'work/source_game_data/native-dump-v1.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['table'] == 'npc':
                    cls.native[row['id']] = row
        cls.sprites = {int(value) for value in re.findall(r'^#(\d+)\b',
            (ROOT / 'work/local_resource_provider/assets/data/list.spr').read_text(encoding='utf-8'), re.M)}
        base_items = gd.load_m1().items
        # with_dungeon_data also has a standalone M1+M3 consumer. Item67 is
        # supplied only by load_m4 and cannot satisfy that independent bundle.
        cls.items = {'m1': base_items, 'm3': base_items,
            'm4': gd.load_m4(gd.load_m1()).items}

    def test_monster_identity_and_client_sprite_exists(self):
        for name, (monsters, _, _) in self.bundles.items():
            for template, monster in monsters.items():
                with self.subTest(bundle=name, template=template):
                    native = self.native[template]
                    sprite = next(f['scalar'] for f in native['fields'] if f['number'] == 2)
                    self.assertEqual(monster.sprite_id, sprite)
                    self.assertEqual(monster.name_ko, native['name']['KR'])
                    self.assertEqual(monster.name_token, native['name']['reference'])
                    self.assertIn(sprite, self.sprites)
                    self.assertEqual(monster.sources['sprite_id'].kind, 'client')

    def test_every_resolved_drop_is_loadable_item(self):
        for name, (monsters, _, drops) in self.bundles.items():
            self.assertEqual(set(monsters), set(drops), name)
            for template, rows in drops.items():
                for row in rows:
                    with self.subTest(bundle=name, template=template, item=row.item_id):
                        self.assertIn(row.item_id, self.items[name])
                        self.assertGreater(row.min_count, 0)
                        self.assertGreaterEqual(row.max_count, row.min_count)
                        self.assertTrue(0 <= row.chance <= gd.CHANCE_DENOMINATOR)

    def test_every_spawn_is_known_and_new_rectangles_fully_standable(self):
        for name, (monsters, groups, _) in self.bundles.items():
            self.assertEqual(len(groups), len({g.group_id for g in groups}))
            for group in groups:
                with self.subTest(bundle=name, group=group.group_id):
                    self.assertIn(group.template_id, monsters)
                    x1, y1, x2, y2 = self.terrain.bounds(group.map_id)
                    r = group.rect
                    self.assertTrue(x1 <= r.x1 <= r.x2 <= x2)
                    self.assertTrue(y1 <= r.y1 <= r.y2 <= y2)
                    counts = Counter(self.terrain.can_stand(group.map_id, x, y)
                        for y in range(r.y1, r.y2 + 1) for x in range(r.x1, r.x2 + 1))
                    self.assertEqual(counts[None], 0)
                    self.assertGreaterEqual(counts[True], group.target_count)
                    if group.group_id not in BASE_GROUPS[name]:
                        self.assertEqual(counts[False], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
