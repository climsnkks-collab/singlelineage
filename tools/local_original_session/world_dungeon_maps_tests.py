"""Pure dungeon startup/data/terrain checks. No sockets or native game."""
from collections import deque
from pathlib import Path
from types import SimpleNamespace
import json
import os
import random
import unittest
from unittest.mock import patch

from tools.local_original_session import game_data as gd
from tools.local_original_session import world_feature_dungeons as feature
from tools.local_original_session import world_maps as maps
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_feature_maps import realm_serves_map
from tools.local_original_session.world_interest_spawn import with_dungeon_data
from tools.local_original_session.world_item_effects import ItemEffectResult, WorldItemEffects
from tools.local_original_session.world_terrain import WorldTerrain, DELTAS
from tools.local_original_session.world_visibility import WorldView


class DungeonMapsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = maps.load_dungeon_policy()
        cls.terrain = WorldTerrain.load(map_ids=(0, 4, *cls.policy.maps))
        with patch.dict(os.environ, {'SL_EXPERIMENT_MAP': '2'}):
            cls.base = with_dungeon_data(gd.load_m1())
        cls.data = feature.load_dungeon_data(cls.base)

    def test_optional_registration_and_default_transition_contract(self):
        realm = SimpleNamespace(_world_map_exp=2)
        self.assertFalse(realm_serves_map(realm, 7))
        self.assertTrue(realm_serves_map(realm, 4))
        self.assertIsNone(maps.resolve_transition(4, 32728, 32929))
        realm._world_dungeon_maps = self.policy.maps
        self.assertTrue(realm_serves_map(realm, 7))
        self.assertEqual(maps.resolve_transition(4, 32728, 32929,
            extra=self.policy.transitions), maps.MapDestination(7, 32812, 32724, 4))
        for mode in (0, 1, 3):
            realm._world_map_exp = mode
            self.assertFalse(realm_serves_map(realm, 7))
            self.assertTrue(realm_serves_map(realm, 0))

    def test_extension_retains_shared_policy_objects(self):
        for name in ('town', 'starter', 'items', 'action_speed', 'level_growth', 'pc_exp'):
            self.assertIs(getattr(self.data, name), getattr(self.base, name))
        for tid in self.base.monsters:
            self.assertIs(self.data.monsters[tid], self.base.monsters[tid])
            self.assertIs(self.data.drops[tid], self.base.drops[tid])
        self.assertEqual(set(self.data.monsters) - set(self.base.monsters), {156, 235, 236})
        self.assertEqual(self.data.monsters[235].level, 12)
        self.assertEqual(self.data.monsters[236].level, 20)

    def test_startup_adds_groups_without_replacing_live_owners(self):
        world = WorldView.create(data=self.base, terrain=self.terrain, rng=random.Random(91))
        original_groups = tuple(world.spawner.groups)
        original_spawner, original_combat, original_ground = world.spawner, world.combat, world.ground
        ctx = SimpleNamespace(world=world, realm=SimpleNamespace(), _world_map_exp=2,
            _world_item_effects=WorldItemEffects(world.combat, self.terrain))
        feature._world_dungeons_initialize(ctx)
        self.assertIs(world.spawner, original_spawner)
        self.assertIs(world.combat, original_combat)
        self.assertIs(world.ground, original_ground)
        self.assertIs(world.data, world.combat.data)
        self.assertIs(world.data, world.ground.data)
        self.assertEqual(tuple(world.spawner.groups[:len(original_groups)]), original_groups)
        self.assertEqual({g.spec.map_id for g in world.spawner.groups
            if g.spec.group_id.startswith('m6_')}, set(self.policy.maps) - {5, 6})
        self.assertFalse(any(g.active for g in world.spawner.groups))
        self.assertEqual(ctx.realm._world_dungeon_maps, self.policy.maps)
        world.close()

    def test_disabled_feature_does_not_load_or_mutate_world(self):
        realm, world = SimpleNamespace(), object()
        ctx = SimpleNamespace(realm=realm, world=world, _world_map_exp=0)
        with patch.object(feature, 'load_dungeon_policy', side_effect=AssertionError('unexpected read')):
            feature._world_dungeons_initialize(ctx)
        self.assertIs(ctx.world, world)
        self.assertIsNone(ctx._world_dungeon_policy)
        self.assertEqual(realm._world_dungeon_maps, ())

    def test_scroll_return_composes_previous_effects_and_death_only_queues(self):
        fallback = maps.MapDestination(0, 32578, 32946, 5)
        class Previous:
            combat = terrain = definitions = rng = None
            def use(self, uid, template_id, now, **options):
                if template_id == 162:
                    return ItemEffectResult(162, 'return_town', 'destination_proposed',
                        consume_count=1, destination=fallback)
                return ItemEffectResult(template_id, 'heal', 'no_effect')
        effects = feature.DungeonItemEffects(Previous(), self.policy)
        for map_id in self.policy.maps:
            position = maps.MapDestination(map_id, 32750, 32750, 0)
            result = effects.use(1, 162, 0, position=position)
            self.assertEqual(result.destination, self.policy.return_for(map_id))
            self.assertEqual(result.consume_count, 1)
            self.assertEqual(effects.use(1, 0, 0, position=position).kind, 'heal')
        self.assertEqual(effects.use(1, 162, 0,
            position=maps.MapDestination(0, 32580, 32946, 0)).destination, fallback)
        world = WorldView.create(data=self.base, terrain=self.terrain)
        actor = world.entities.add(Kind.PC, 19, 32805, 32724)
        ctx = SimpleNamespace(world=world, _world_dungeon_policy=self.policy, _world_relocations={})
        before = (actor.map_id, actor.x, actor.y)
        feature._world_dungeons_death(ctx, actor.uid)
        self.assertEqual(ctx._world_relocations[actor.uid], self.policy.return_for(19))
        self.assertEqual((actor.map_id, actor.x, actor.y), before)
        world.close()

    def test_stairs_returns_and_spawn_rectangles_have_real_static_terrain(self):
        for origin, transition in self.policy.transitions.items():
            self.assertEqual(transition.native_trigger_status, 'UNKNOWN')
            self.assertTrue(transition.source.startswith('local_policy/'))
            self.assertIs(self.terrain.can_stand(*origin), True)
            d = transition.destination
            self.assertIs(self.terrain.can_stand(d.map_id, d.x, d.y), True)
        for destination in self.policy.returns.values():
            self.assertIs(self.terrain.can_stand(destination.map_id, destination.x, destination.y), True)
        for spec in self.data.spawns[len(self.base.spawns):]:
            for x in range(spec.rect.x1, spec.rect.x2 + 1):
                for y in range(spec.rect.y1, spec.rect.y2 + 1):
                    self.assertIs(self.terrain.can_stand(spec.map_id, x, y), True)
            self.assertIn(spec.template_id, self.data.monsters)

    def test_first_floor_entrance_reaches_selected_hunting_and_next_connection(self):
        for map_id in (7, 19, 43):
            entrance = next(t.destination for k, t in self.policy.transitions.items()
                            if k[0] == 4 and t.destination.map_id == map_id)
            seen, queue = {(entrance.x, entrance.y)}, deque([(entrance.x, entrance.y)])
            while queue:
                x, y = queue.popleft()
                for heading, (dx, dy) in enumerate(DELTAS):
                    if self.terrain.can_step(map_id, x, y, heading) is not True:
                        continue
                    nx, ny = x + dx, y + dy
                    transition = self.policy.transitions.get((map_id, nx, ny))
                    if transition is not None:
                        if transition.destination.map_id != map_id:
                            continue
                        nx, ny = transition.destination.x, transition.destination.y
                    if (nx, ny) not in seen:
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            groups = [s for s in self.data.spawns[len(self.base.spawns):] if s.map_id == map_id]
            for spec in groups:
                self.assertTrue(all((x, y) in seen
                    for x in range(spec.rect.x1, spec.rect.x2 + 1)
                    for y in range(spec.rect.y1, spec.rect.y2 + 1)))
            self.assertTrue(any(k[0] == map_id and t.destination.map_id not in (map_id, 0, 4)
                and any((k[1] - dx, k[2] - dy) in seen
                    and self.terrain.can_step(map_id, k[1] - dx, k[2] - dy, heading) is True
                    for heading, (dx, dy) in enumerate(DELTAS))
                for k, t in self.policy.transitions.items()))

    def test_new_drops_only_award_existing_usable_official_items(self):
        path = Path(__file__).resolve().parent / 'data/official/monsters.json'
        official = {r['official_id']: r for r in json.loads(path.read_text(encoding='utf-8'))['monsters']}
        for tid in (156, 235, 236):
            allowed = {r['official_item_id'] for r in official[tid]['drops']}
            for drop in self.data.drops[tid]:
                self.assertIn(drop.item_id, allowed)
                self.assertIn(drop.item_id, self.data.items)
                self.assertEqual(drop.sources['roll'].kind, 'l1j')


if __name__ == '__main__':
    unittest.main()
