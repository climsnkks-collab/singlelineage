"""Expansion table/asset/terrain contracts; file reads only, no native UI claim."""
from collections import Counter
import json
from pathlib import Path
import re
import unittest

from tools.local_original_session import game_data as gd
from tools.local_original_session.world_terrain import WorldTerrain

ROOT = Path(__file__).resolve().parents[2]
# Original rectangles allow blocked cells; earlier expansion rectangles remain
# fully standable. Population rows explicitly reuse existing rectangles and
# retain the spawner's passable-only placement/retry policy.
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
                    rect_source = group.sources['rect']
                    reused_population = (group.group_id.startswith('population_')
                        and rect_source.kind == 'local_policy'
                        and rect_source.note.startswith(
                            'Reuse existing rectangle in the exact same map/field.'))
                    if group.group_id not in BASE_GROUPS[name] and not reused_population:
                        self.assertEqual(counts[False], 0)


class ReassessedDropTests(unittest.TestCase):
    """Current item identities and own-NPC SQL rates; no acquisition claim."""

    @classmethod
    def setUpClass(cls):
        cls.tables = {name: gd._read(gd.M1_DATA_DIR.parent / name, 'drops.json')
                      for name in ('m1', 'm3', 'm4', 'm6', 'catalog/map0')}

    def test_baphomet_accessories_use_own_rates_and_keep_client_ids(self):
        drops, _ = gd._drops(self.tables['m3'])
        by_pair = {(d.item_id, d.grade): d for d in drops[24]}
        for item, chance in ((64, 5000), (311, 20000)):
            with self.subTest(item=item):
                drop = by_pair[item, 1]
                self.assertEqual((drop.chance, drop.min_count, drop.max_count),
                                 (chance, 1, 1))
                self.assertIn('mobId=45573', drop.sources['roll'].ref)
                self.assertIn(item, gd.load_items())
        # Registration alone cannot supply Baltuzar's missing polymorph roll.
        _, held = gd._drops(self.tables['m6'])
        self.assertTrue(any((r.template_id, r.item_id, r.grade) == (34, 65, 1)
                            for r in held))

    def test_reassessed_rows_match_reference_sql_and_prior_identity(self):
        import csv
        sql_path = Path('D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql')
        if not sql_path.exists():
            self.skipTest('retained local L1J SQL reference is unavailable')
        columns, sql_rows, current = {}, {}, None
        for number, line in enumerate(sql_path.read_text(encoding='utf-8').splitlines(), 1):
            if line.startswith('CREATE TABLE `'):
                current = line.split('`')[1]
                columns[current] = []
            elif current and line.startswith('  `'):
                columns[current].append(line.split('`')[1])
            elif line.startswith(') ENGINE'):
                current = None
            if line.startswith('INSERT INTO `'):
                table = line.split('`')[1]
                if table not in ('droplist', 'weapon', 'armor', 'etcitem'):
                    continue
                values = next(csv.reader([line[line.index('(') + 1:line.rindex(')')]],
                                         quotechar="'", escapechar='\\', skipinitialspace=True))
                sql_rows[number] = table, dict(zip(columns[table], values))

        items = gd.load_items()
        extra = gd._items(gd._read(gd.M1_DATA_DIR.parent / 'm4', 'items.json'))
        seen = 0
        identity_ids = {}
        for name, raw in self.tables.items():
            monsters = (gd._monsters(gd._read(gd.M1_DATA_DIR.parent / name, 'monsters.json'))
                        if name != 'catalog/map0' else {})
            drops, held = gd._drops(raw)
            held_keys = {(d.template_id, d.item_id, d.grade) for d in held}
            for entry in raw.get('resolved_unresolved_history', []):
                if entry.get('resolution') != 'current_itemdef_unique_identity_own_npc_sql_20261029':
                    continue
                original = entry['original_unresolved']
                template, item = original['template_id'], original['item']
                key = (template, item['id'], item['grade'])
                with self.subTest(table=name, key=key):
                    active = [r for r in raw['drops'][str(template)]
                              if r['item']['value'] == item]
                    self.assertEqual(len(active), 1)
                    row = active[0]
                    self.assertNotIn(key, held_keys)
                    available = items if name in ('m1', 'm3', 'catalog/map0') else dict(extra) | dict(items)
                    self.assertIn(item['id'], available)
                    line = int(row['l1j_drop_ref'].split(':')[1])
                    table, sql = sql_rows[line]
                    self.assertEqual(table, 'droplist')
                    npc = original.get('l1j_npcid', row['l1j_npcid'])
                    if name != 'catalog/map0':
                        self.assertEqual(monsters[template].l1j_npcid, npc)
                    self.assertEqual(int(sql['mobId']), npc)
                    self.assertEqual(int(sql['itemId']), row['l1j_item_id'])
                    self.assertEqual(row['roll']['value'],
                                     {k: int(sql[k]) for k in ('chance', 'min', 'max')})
                    self.assertTrue(0 < int(sql['chance']) <= gd.CHANCE_DENOMINATOR)
                    mapping = row['mapping']
                    item_line = int(re.search(r'\.sql:(\d+)', mapping['ref'])[1])
                    kind, sql_item = sql_rows[item_line]
                    self.assertEqual(int(sql_item['item_id']), row['l1j_item_id'])
                    self.assertEqual(int(sql_item['bless']), item['grade'])
                    self.assertEqual(kind, mapping['l1j_kind'])
                    self.assertEqual(sql_item['identified_name_id'], mapping['l1j_identified_name_id'])
                    self.assertEqual(sql_item['name'], mapping['l1j_name'])
                    identity_key = (item['id'], item['grade'])
                    identity_ids.setdefault(identity_key, set()).add(row['l1j_item_id'])
                    if 'reused_identity' in mapping:
                        source = mapping['reused_identity']
                        prior = json.loads((ROOT / source['path']).read_text(encoding='utf-8'))
                        matches = [r for r in prior['drops'][str(source['template_id'])]
                                   if r['item']['value']['id'] == item['id']
                                   and r['item']['value']['grade'] == item['grade']]
                        self.assertEqual(len(matches), 1)
                        references = re.findall(r'(?:l1jdb|l1jdb_m10\.sql):(\d+)',
                                                matches[0]['roll']['ref'])
                        self.assertTrue(any(int(sql_rows[int(n)][1].get('itemId', -1))
                                            == row['l1j_item_id'] for n in references
                                            if int(n) in sql_rows))
                    seen += 1
        self.assertGreater(seen, 0)
        self.assertTrue(all(len(ids) == 1 for ids in identity_ids.values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
