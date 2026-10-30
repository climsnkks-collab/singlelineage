"""No-port development checks for optional boss windows and restart projection."""
from dataclasses import replace
import json
from pathlib import Path
import random
import uuid
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import game_data as gd, world_interest_spawn as spawn
from tools.local_original_session import world_feature_boss_cycles as boss
from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_feature_dungeons import load_dungeon_data
from tools.local_original_session.world_feature_m5 import load_m5_data
from tools.local_original_session.world_registry import build_registry
from tools.local_original_session.world_extensions import WorldEvents
from tools.local_original_session.world_terrain import WorldTerrain


def all_data():
    with patch.dict('os.environ', {'SL_EXPERIMENT_MAP': '0'}):
        return load_dungeon_data(load_m5_data(gd.load_m4(spawn.with_dungeon_data(gd.load_m1()))))


class Clock:
    def __init__(self, now=1700000000):
        self.now = now

    def __call__(self):
        return self.now


class BossCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = all_data()
        cls.waves = boss.load_policy(cls.data)

    def setUp(self):
        # Persist artifacts and avoid Windows Python 3.13's mode-0700 temp
        # directories, whose sandbox ACL can make even their owner unreadable.
        self.directory = Path(__file__).resolve().parents[2] / '_work/boss_cycle/unit_artifacts' / uuid.uuid4().hex
        self.directory.mkdir(parents=True)
        self.path = self.directory / 'characters.json.boss_cycles.json'
        self.wall = Clock()

    def owner(self, keys=('17',), *, path=None, passable=lambda *_: True):
        selected = tuple(w for w in self.waves if w.key in keys)
        spawner = spawn.InterestSpawner(EntityRegistry(), self.data,
            passable=passable, rng=random.Random(1))
        owner = boss.BossCycles(spawner, self.data, selected,
            path=path, wall_clock=self.wall, rng=random.Random(2))
        return owner, spawner

    def due(self, owner, key='17'):
        self.wall.now = owner.document['waves'][key]['due_epoch']

    def groups(self, spawner):
        return [g for g in spawner.groups if g.spec.group_id.startswith('boss_')]

    def test_xml_end_defaults_to_period_and_sources_cover_called_out_bosses(self):
        by_key = {wave.key: wave for wave in self.waves}
        self.assertEqual((by_key['17'].period, by_key['17'].start, by_key['17'].end),
                         (3600, 1800, 3600))
        self.assertEqual(sum(s.target_count for s in by_key['17'].groups), 4)
        self.assertEqual({s.template_id for s in by_key['17'].groups}, {34, 35, 36, 37})
        self.assertEqual(sum(s.target_count for s in by_key['26'].groups), 2)
        self.assertEqual(by_key['22'].groups[0].template_id, 588)
        self.assertEqual(by_key['46'].groups[0].template_id, 590)
        self.assertTrue(all(s.sources['boss_cycle'].kind == 'local_policy'
                            for w in self.waves for s in w.groups))

    def test_before_window_hold_tick_without_pc_and_no_alive_duplicates(self):
        owner, spawner = self.owner()
        self.due(owner)
        self.wall.now -= 1
        self.assertFalse(spawner.tick(10))
        self.assertTrue(all(g.active for g in self.groups(spawner)))
        self.wall.now += 1
        self.assertTrue(spawner.tick(11))
        groups = self.groups(spawner)
        ids = {s.uid for g in groups for s in g.slots}
        self.assertEqual(len(ids), 4)
        self.assertNotIn(None, ids)
        self.wall.now += 10 * 86400
        self.assertFalse(spawner.tick(100))
        self.assertEqual(ids, {s.uid for g in groups for s in g.slots})
        self.assertTrue(all(r['due_epoch'] is None for r in owner.status()))

    def test_party_dead_member_waits_all_dead_then_next_window_and_corpse_cleanup(self):
        owner, spawner = self.owner(path=self.path)
        self.due(owner)
        spawner.tick(10)
        groups = self.groups(spawner)
        slots = [s for g in groups for s in g.slots]
        first = slots[0]
        old_uid = first.uid
        spawner.mark_dead(old_uid, 10)
        spawner.tick(first.corpse_at)
        self.assertIsNone(spawner.entities.get(old_uid))
        self.assertEqual(first.state, spawn.SlotState.WAIT)
        self.assertEqual(owner.document['waves']['17']['members'][groups[0].spec.group_id][0]['phase'], 'dead')
        for slot in slots[1:]:
            spawner.mark_dead(slot.uid, 11)
        row = owner.document['waves']['17']
        self.assertGreater(row['due_epoch'], self.wall.now)
        self.assertTrue(all(r['due_epoch'] is not None for r in owner.status()))
        self.wall.now = row['due_epoch']
        self.assertTrue(spawner.tick(10000))
        self.assertTrue(all(s.state is spawn.SlotState.ALIVE for s in slots))
        self.assertNotEqual(first.uid, old_uid)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')), owner.document)

    def test_death_after_many_survived_windows_never_replays_missed_cycle(self):
        owner, spawner = self.owner(('35',))
        self.due(owner, '35')
        spawner.tick(0)
        self.wall.now += 13 * 86400
        wave = owner.waves[0]
        anchor = owner.document['anchor_epoch']
        current = int((self.wall.now - anchor) // wave.period)
        # Kill near current window end, when a new random time could be past.
        self.wall.now = anchor + current * wave.period + wave.end - 1
        spawner.mark_dead(self.groups(spawner)[0].slots[0].uid, 10)
        next_row = owner.document['waves']['35']
        self.assertEqual(next_row['cycle_index'], current + 1)
        self.assertGreater(next_row['due_epoch'], self.wall.now)

    def test_restart_alive_preserves_hp_position_home_and_single_instance(self):
        owner, spawner = self.owner(path=self.path)
        self.due(owner)
        spawner.tick(10)
        group = self.groups(spawner)[0]
        slot = group.slots[0]
        spawner.set_hp(slot.uid, 7)
        entity = spawner.entities.get(slot.uid)
        expected = (entity.x, entity.y, entity.heading, slot.home)
        anchor = owner.document['anchor_epoch']
        owner.close()
        self.wall.now += 7 * 86400
        restored, second = self.owner(path=self.path)
        second.tick(0)
        second.tick(1)
        revived = self.groups(second)[0].slots[0]
        actor = second.entities.get(revived.uid)
        self.assertEqual(revived.hp, 7)
        self.assertEqual((actor.x, actor.y, actor.heading, revived.home), expected)
        self.assertEqual(restored.document['anchor_epoch'], anchor)
        self.assertEqual(sum(s.state is spawn.SlotState.ALIVE for g in self.groups(second) for s in g.slots), 4)

    def test_restart_pending_deadline_not_resampled_and_downtime_spawns_once(self):
        owner, _ = self.owner(('35',), path=self.path)
        row = owner.document['waves']['35'].copy()
        owner.close()
        self.wall.now = row['due_epoch'] + 30 * 86400
        second, spawner = self.owner(('35',), path=self.path)
        self.assertEqual(second.document['waves']['35']['due_epoch'], row['due_epoch'])
        spawner.tick(0)
        self.assertFalse(spawner.tick(1))
        self.assertEqual(len(list(spawner.entities)), 1)

    def test_blocked_placement_keeps_pending_no_forced_success(self):
        owner, spawner = self.owner(passable=lambda *_: None)
        self.due(owner)
        self.assertFalse(spawner.tick(10))
        self.assertFalse(list(spawner.entities))
        self.assertEqual(owner.status()[0]['pending'], 4)
        spawner.passable = lambda *_: True
        self.assertTrue(spawner.tick(16))
        self.assertEqual(owner.status()[0]['alive'], 4)

    def test_single_tile_dark_elder_minions_use_sourced_radius_and_whole_party_dies(self):
        owner, spawner = self.owner(('31',))
        self.due(owner, '31')
        self.assertTrue(spawner.tick(10))
        groups = self.groups(spawner)
        leader = spawner.entities.get(groups[0].slots[0].uid)
        self.assertEqual(len(list(spawner.entities)), 3)
        for slot in groups[1].slots:
            actor = spawner.entities.get(slot.uid)
            self.assertLessEqual(max(abs(actor.x-leader.x), abs(actor.y-leader.y)), 2)
        for group in groups:
            for slot in group.slots:
                spawner.mark_dead(slot.uid, 10)
        self.assertGreater(owner.document['waves']['31']['due_epoch'], self.wall.now)

    def test_ordinary_groups_identical_feature_removed_or_map_disabled(self):
        owner, spawner = self.owner(('17',))
        suppressed = set().union(*(w.suppress for w in owner.waves))
        ordinary = [g for g in spawner.groups if not g.spec.group_id.startswith('boss_')]
        self.assertEqual([g.spec for g in ordinary],
            [s for s in self.data.spawns if (s.map_id, s.template_id) not in suppressed])
        self.assertTrue(any(g.spec.template_id == 30 for g in ordinary))
        plain = spawn.InterestSpawner(EntityRegistry(), self.data, passable=lambda *_: True)
        self.assertEqual(tuple(g.spec for g in plain.groups), self.data.spawns)
        self.assertEqual(boss.load_policy(self.data, serves_map=lambda _: False), ())
        registry = build_registry((boss,))
        self.assertIn('runtime_started', registry.hooks)
        self.assertEqual(build_registry(()).hooks, {})

    def test_state_path_isolates_stores_and_corruption_preserved(self):
        self.assertNotEqual(boss.state_path_for(Path('a/characters.json')),
                            boss.state_path_for(Path('b/characters.json')))
        self.path.write_text('{invalid', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            self.owner(path=self.path)
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{invalid')

    def test_actual_client_dark_elder_party_placement(self):
        terrain = WorldTerrain.load(map_ids=(4,))
        owner, spawner = self.owner(('31',), passable=terrain.can_stand)
        self.due(owner, '31')
        for now in range(0, 101, 5):
            spawner.tick(now)
        self.assertEqual(owner.status()[0]['alive'], 3)
        self.assertTrue(all(terrain.can_stand(e.map_id, e.x, e.y) is True for e in spawner.entities))

    def test_registered_feature_start_report_and_stop_keep_catalogs_and_cleanup(self):
        # Exercise the actual exported hook callables without sockets/client.
        spawner = spawn.InterestSpawner(EntityRegistry(), self.data,
            passable=lambda *_: True, rng=random.Random(3))
        world = SimpleNamespace(spawner=spawner, data=self.data, events=WorldEvents())
        world.combat = SimpleNamespace(data=self.data)
        world.ground = SimpleNamespace(data=self.data)
        def replace_data(data):
            world.data = world.combat.data = world.ground.data = data
        world.replace_data = replace_data
        context = SimpleNamespace(world=world,
            realm=SimpleNamespace(serves_map=lambda map_id: map_id == 9),
            world_options={'store_path': self.directory / 'characters.json'})
        registry = build_registry((boss,))
        for name in registry.hooks['runtime_started']:
            registry.methods[name](context)
        owner = context._world_boss_cycles
        self.assertEqual(owner.path, boss.state_path_for(context.world_options['store_path']))
        self.assertEqual(len(owner.waves), 1)
        self.assertIs(world.combat.data, world.data)
        self.assertIs(world.ground.data, world.data)
        self.assertEqual(world.data.spawns, tuple(g.spec for g in spawner.groups))
        report = {}
        for name in registry.hooks['report']:
            registry.methods[name](context, report)
        self.assertEqual(report['boss_cycles']['schedule'][0]['key'], '17')
        self.assertIsNotNone(report['boss_cycles']['schedule'][0]['due_epoch'])
        world.events.emit('close')
        for name in registry.hooks['runtime_stopped']:
            registry.methods[name](context)
        self.assertTrue(owner.closed)
        self.assertFalse(owner.handles)
        self.assertTrue(owner.path.exists())


if __name__ == '__main__':
    unittest.main()
