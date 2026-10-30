"""Pure dungeon startup/data/terrain checks. No sockets or native game."""
from collections import deque
import asyncio
from pathlib import Path
from types import MethodType, SimpleNamespace
import json
import os
import random
import unittest
from unittest.mock import patch

from tools.local_original_session import game_data as gd
from tools.local_original_session import world_feature_dungeons as feature
from tools.local_original_session import world_maps as maps
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_core_maps import realm_serves_map
from tools.local_original_session.world_core_life import _world_set_relocation
from tools.local_original_session.world_registry import build_registry
from tools.local_original_session.world_interest_spawn import with_dungeon_data
from tools.local_original_session.world_item_effects import ItemEffectResult, WorldItemEffects
from tools.local_original_session.world_terrain import WorldTerrain, DELTAS, LAZY_MAP_IDS
from tools.local_original_session.world_visibility import WorldView


class DungeonMapsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = maps.load_dungeon_policy()
        cls.terrain = WorldTerrain.load(map_ids=(0, 4, *feature.load_island_policy().maps))
        with patch.dict(os.environ, {'SL_EXPERIMENT_MAP': '2'}):
            cls.base = with_dungeon_data(gd.load_m1())
        cls.data = feature.load_dungeon_data(cls.base)

    def test_optional_registration_and_default_transition_contract(self):
        context = SimpleNamespace(world=object(), _world_dungeon_policy=None)
        realm = SimpleNamespace(_world_map_exp=2, _world_context=context,
                                _world_registry=build_registry((feature,)))
        self.assertFalse(realm_serves_map(realm, 7))
        self.assertTrue(realm_serves_map(realm, 4))
        self.assertIsNone(maps.resolve_transition(4, 32728, 32929))
        context._world_dungeon_policy = self.policy
        self.assertTrue(realm_serves_map(realm, 7))
        self.assertEqual(maps.resolve_transition(4, 32728, 32929,
            extra=self.policy.transitions), maps.MapDestination(7, 32812, 32724, 4))
        for mode in (0, 1, 3):
            realm._world_map_exp = mode
            context._world_dungeon_policy = None  # disabled startup configuration
            self.assertFalse(realm_serves_map(realm, 7))
            self.assertTrue(realm_serves_map(realm, 0))

    def test_extension_retains_shared_policy_objects(self):
        for name in ('town', 'starter', 'items', 'action_speed', 'level_growth', 'pc_exp'):
            self.assertIs(getattr(self.data, name), getattr(self.base, name))
        for tid in self.base.monsters:
            self.assertIs(self.data.monsters[tid], self.base.monsters[tid])
            self.assertIs(self.data.drops[tid], self.base.drops[tid])
        dungeon_monsters = gd._monsters(gd._read(gd.M1_DATA_DIR.parent / 'm6', 'monsters.json'))
        # Map expansion population rows are part of the same dungeon extension.
        population = gd._monsters(gd._read(gd.M1_DATA_DIR.parent / 'm6', 'map_expansion2_population.json'))
        map0 = gd._monsters(gd._read(gd.M1_DATA_DIR.parent / 'm6', 'map0_population.json'))
        self.assertEqual(set(self.data.monsters),
                         set(self.base.monsters) | set(dungeon_monsters) | set(population) | set(map0))
        self.assertTrue({156, 235, 236} <= set(self.data.monsters))
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
        specs = {spec.group_id: spec for spec in world.data.spawns}
        self.assertEqual({group.spec.group_id: group.spec for group in world.spawner.groups}, specs)
        for group in world.spawner.groups:
            self.assertEqual(len(group.slots), group.spec.target_count)
            self.assertTrue(all(slot.uid is None for slot in group.slots))
        map0 = [group for group in world.spawner.groups if group.spec.map_id == 0]
        self.assertEqual((len(map0), sum(len(group.slots) for group in map0)), (91, 2732))
        self.assertEqual(sum(group.spec.group_id == 'm1_orc' for group in map0), 1)
        orcs = next(group for group in map0 if group.spec.group_id == 'm1_orc')
        self.assertEqual((orcs.spec.target_count, orcs.spec.rect),
                         (60, gd.Rect(32561, 32796, 32707, 32885)))
        # All m6 dungeon groups (original floors plus map expansions 2-6).
        expected = {spec.map_id for spec in feature.load_dungeon_data(self.base).spawns
                    if spec.group_id.startswith('m6_')}
        self.assertTrue(set(range(7,14)) | {19,20,21,25,26,27,28,30,4} | set(range(43,52)) <= expected)
        self.assertEqual({g.spec.map_id for g in world.spawner.groups
            if g.spec.group_id.startswith('m6_')}, expected)
        self.assertFalse(any(g.active for g in world.spawner.groups))
        self.assertEqual(ctx._world_dungeon_policy.maps, feature.load_island_policy().maps)
        world.close()

    def test_disabled_feature_does_not_load_or_mutate_world(self):
        realm, world = SimpleNamespace(), object()
        ctx = SimpleNamespace(realm=realm, world=world, _world_map_exp=0)
        with patch.object(feature, 'load_dungeon_policy', side_effect=AssertionError('unexpected read')):
            feature._world_dungeons_initialize(ctx)
        self.assertIs(ctx.world, world)
        self.assertIsNone(ctx._world_dungeon_policy)
        self.assertFalse(feature._world_dungeons_serves_map(
            SimpleNamespace(_world_context=ctx), False, 7))

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
        ctx._world_set_relocation = MethodType(_world_set_relocation, ctx)
        before = (actor.map_id, actor.x, actor.y)
        feature._world_dungeons_death(ctx, actor.uid)
        self.assertEqual(ctx._world_relocations[actor.uid], self.policy.return_for(19))
        self.assertEqual((actor.map_id, actor.x, actor.y), before)
        world.close()

    def test_stairs_returns_and_spawn_rectangles_have_real_static_terrain(self):
        for origin, transition in self.policy.transitions.items():
            self.assertEqual(transition.native_trigger_status, 'UNKNOWN')
            # Map expansions 5/6 also add client S32 named links (106-110).
            self.assertTrue(transition.source.startswith(('local_policy/', 'client_s32_named_link/')))
            self.assertIs(self.terrain.can_stand(*origin), True)
            d = transition.destination
            self.assertIs(self.terrain.can_stand(d.map_id, d.x, d.y), True)
        for destination in self.policy.returns.values():
            self.assertIs(self.terrain.can_stand(destination.map_id, destination.x, destination.y), True)
        for spec in self.data.spawns[len(self.base.spawns):]:
            # Registry-population rectangles may include blocked cells (the
            # spawner places only on can_stand tiles); they need enough cells.
            partial = (spec.group_id.startswith('registry_population_')
                       or spec.group_id.startswith('m6_field_l1j_')
                       or spec.group_id.startswith('m6_exp2_population_30_')
                       or (spec.map_id == 0 and spec.sources['rect'].kind == 'l1j'))
            standable = 0
            for x in range(spec.rect.x1, spec.rect.x2 + 1):
                for y in range(spec.rect.y1, spec.rect.y2 + 1):
                    ok = self.terrain.can_stand(spec.map_id, x, y) is True
                    if not partial:
                        self.assertIs(ok, True)
                    standable += ok
            self.assertGreaterEqual(standable, spec.target_count, spec.group_id)
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

    def test_map30_source_counts_fit_disjoint_entrance_connected_rectangles(self):
        document = gd._read(gd.M1_DATA_DIR.parent / 'm6', 'map_expansion2_population.json')
        groups = [g for g in document['groups'] if g['map_id']['value'] == 30]
        expected = {288: (24, 46138), 290: (24, 46139),
                    289: (26, 46140), 279: (20, 46143)}
        self.assertEqual({g['template_id']['value'] for g in groups}, set(expected))
        entrance = next(t.destination for k, t in self.policy.transitions.items()
                        if k[0] == 4 and t.destination.map_id == 30)
        seen, queue = {(entrance.x, entrance.y)}, deque([(entrance.x, entrance.y)])
        while queue:
            x, y = queue.popleft()
            for heading, (dx, dy) in enumerate(DELTAS):
                point = x+dx, y+dy
                if (point not in seen and (30, *point) not in self.policy.transitions
                        and self.terrain.can_step(30, x, y, heading) is True):
                    seen.add(point)
                    queue.append(point)
        occupied = {(x, y) for s in self.data.spawns if s.group_id == 'm6_exp2_30_30'
                    for x in range(s.rect.x1, s.rect.x2+1)
                    for y in range(s.rect.y1, s.rect.y2+1)}
        for group in groups:
            tid = group['template_id']['value']
            count, line = expected[tid]
            reference = group['reference_spawn_rows'][0]
            raw, rect = reference['row'], group['rect']['value']
            self.assertEqual((reference['line'], reference['table']), (line, 'spawnlist'))
            self.assertEqual((int(raw['mapid']), int(raw['npc_templateid'])),
                             (30, self.data.monsters[tid].l1j_npcid))
            self.assertEqual((group['target_count']['value'], int(raw['count'])), (count, count))
            self.assertTrue(int(raw['locx1']) <= rect['x1'] <= rect['x2'] <= int(raw['locx2']))
            self.assertTrue(int(raw['locy1']) <= rect['y1'] <= rect['y2'] <= int(raw['locy2']))
            points = {(x, y) for x in range(rect['x1'], rect['x2']+1)
                      for y in range(rect['y1'], rect['y2']+1)}
            standable = {p for p in points if self.terrain.can_stand(30, *p) is True}
            self.assertGreaterEqual(len(standable), count)
            self.assertTrue(standable <= seen)
            self.assertFalse(any((30, *p) in self.policy.transitions for p in points))
            self.assertFalse(points & occupied)
            occupied |= points

    def test_new_drops_only_award_existing_usable_official_items(self):
        path = Path(__file__).resolve().parent / 'data/official/monsters.json'
        official = {r['official_id']: r for r in json.loads(path.read_text(encoding='utf-8'))['monsters']}
        for tid in (156, 235, 236):
            allowed = {r['official_item_id'] for r in official[tid]['drops']}
            for drop in self.data.drops[tid]:
                self.assertIn(drop.item_id, allowed)
                self.assertIn(drop.item_id, self.data.items)
                # The original Mimic/Chest rolls retain their L1J source;
                # newly activated item rows explicitly declare LOCAL policy.
                # Later drop fills added more LOCAL-policy rows; the original
                # L1J potion/adena/teleport rows keep their L1J roll source.
                source = 'l1j' if tid != 156 and drop.item_id in (7, 17, 23) else 'local_policy'
                self.assertEqual(drop.sources['roll'].kind, source)

    def test_upper_tower_internal_stairs_and_exact_spawn_references(self):
        document = gd._read(gd.M1_DATA_DIR.parent / 'm6', 'map_expansion6.json')
        upper = set(range(111, 121))
        self.assertTrue(upper <= set(self.policy.maps))
        self.assertFalse(any(origin[0] == 110 and transition.destination.map_id == 111
                             for origin, transition in self.policy.transitions.items()))
        upper_links = {origin: transition for origin, transition in self.policy.transitions.items()
                       if origin[0] in upper}
        self.assertEqual(len(upper_links), 40)
        self.assertEqual({(origin[0], transition.destination.map_id)
                          for origin, transition in upper_links.items()},
                         {(a, b) for a in upper for b in upper if abs(a-b) == 1})
        # Runtime lazy loading must admit the same maps as the startup policy.
        lazy = WorldTerrain.load(map_ids=(), lazy_map_ids=LAZY_MAP_IDS)
        selected = {111: set(), 112: {1028}, 113: {1028}, 114: {1028},
                    115: {1027, 1028}, 116: set(), 117: {895, 1027},
                    118: {895, 1027}, 119: {895, 1027}, 120: {895, 1027}}
        groups = [row for row in document['groups']
                  if row['group_id']['value'].startswith('m6_tower_upper_')]
        for mid in upper:
            incoming = next(t.destination for origin, t in upper_links.items()
                            if t.destination.map_id == mid)
            self.assertIs(lazy.can_stand(mid, incoming.x, incoming.y), True)
            seen, queue = {(incoming.x, incoming.y)}, deque([(incoming.x, incoming.y)])
            while queue:
                x, y = queue.popleft()
                for heading, (dx, dy) in enumerate(DELTAS):
                    point = x+dx, y+dy
                    if (point not in seen and (mid, *point) not in upper_links
                            and self.terrain.can_step(mid, x, y, heading) is True):
                        seen.add(point)
                        queue.append(point)
            for origin in (origin for origin in upper_links if origin[0] == mid):
                self.assertTrue(any((origin[1]-dx, origin[2]-dy) in seen
                    and self.terrain.can_step(mid, origin[1]-dx, origin[2]-dy, heading) is True
                    for heading, (dx, dy) in enumerate(DELTAS)), origin)
            actual = [row for row in groups if row['map_id']['value'] == mid]
            self.assertEqual({row['template_id']['value'] for row in actual}, selected[mid])
            for row in actual:
                raw = row['l1j_spawn_reference']['raw']
                tid = row['template_id']['value']
                self.assertEqual((int(raw[16]), int(raw[3])),
                                 (mid, self.data.monsters[tid].l1j_npcid))
                rect = row['rect']['value']
                self.assertTrue(int(raw[9]) <= rect['x1'] <= rect['x2'] <= int(raw[11]))
                self.assertTrue(int(raw[10]) <= rect['y1'] <= rect['y2'] <= int(raw[12]))
                self.assertTrue(all((x, y) in seen for x in range(rect['x1'], rect['x2']+1)
                                    for y in range(rect['y1'], rect['y2']+1)))


class ExpansionHuntTests(unittest.TestCase):
    def test_map36_first_kill_does_not_wait_for_a_random_drop_or_respawn(self):
        from tools.local_original_session.hunt_bot_map_expansion2 import ExpansionScenario
        scenario = object.__new__(ExpansionScenario)
        scenario.case = {'map_id': 36, 'group_id': 'ettin'}
        scenario.args = SimpleNamespace(hunt_timeout=1)
        group = SimpleNamespace(group_id='ettin', template_id=287,
                                rect=gd.Rect(32700, 32700, 32702, 32702))
        scenario.broker = SimpleNamespace(_world=SimpleNamespace(
            data=SimpleNamespace(spawns=(group,), drops={287: (object(),)})))
        bot = SimpleNamespace(kills=set(), pickups=0, dead=False, hp=100, max_hp=100,
            ground={}, actors={9: {'alive': True, 'template': 287, 'position': (32701, 32701)}},
            position=(32701, 32700), map_id=36, swings=0, last_alive=float('inf'))
        async def attack(uid):
            bot.swings += 1
            bot.kills.add(uid)
            bot.actors[uid]['alive'] = False
        async def step(*args, **options):
            self.fail('must not seek another respawn after the observed kill')
        bot.attack, bot.step = attack, step
        scenario.bot, scenario.start_ground = bot, set()
        scenario.last_speed_use = float('inf')
        checks = {}
        scenario.record = lambda name, passed, **details: checks.update({name: (passed, details)})
        asyncio.run(scenario.case_combat())
        self.assertEqual((bot.kills, bot.swings, bot.pickups), ({9}, 1, 0))
        self.assertTrue(checks['received_actor_kill'][0])
        self.assertTrue(checks['no_drop_observed'][0])
        self.assertNotIn('received_drop_and_pickup', checks)

    def test_map37_received_live_boss_requests_danger_return_without_kill_claim(self):
        from tools.local_original_session.hunt_bot_map_expansion2 import ExpansionScenario
        scenario = object.__new__(ExpansionScenario)
        scenario.case = {'map_id': 37, 'group_id': 'antharas'}
        scenario.args = SimpleNamespace(boss_timeout=1)
        group = SimpleNamespace(group_id='antharas', template_id=327,
                                rect=gd.Rect(32700, 32700, 32702, 32702))
        scenario.broker = SimpleNamespace(_world=SimpleNamespace(
            data=SimpleNamespace(spawns=(group,), drops={327: (object(),)})))
        bot = SimpleNamespace(kills=set(), pickups=0, dead=False, hp=1926, max_hp=1926,
            actors={9: {'alive': True, 'template': 327, 'position': (32701, 32701)}},
            position=(32701, 32700), map_id=37, swings=0)
        scenario.bot, scenario.danger_return = bot, None
        checks = {}
        scenario.record = lambda name, passed, **details: checks.update({name: (passed, details)})
        asyncio.run(scenario.case_combat())
        self.assertEqual(scenario.danger_return['received_uid'], 9)
        self.assertGreater(scenario.danger_return['unresisted_spell10054_upper_bound'], bot.hp)
        self.assertEqual(bot.swings, 0)
        self.assertTrue(checks['received_boss_danger'][0])
        self.assertNotIn('received_actor_kill', checks)
        self.assertNotIn('received_drop_and_pickup', checks)

    def test_no_drop_representative_requires_kill_without_waiting_for_loot(self):
        from tools.local_original_session.hunt_bot_map_expansion2 import ExpansionScenario
        scenario = object.__new__(ExpansionScenario)
        scenario.case = {'map_id': 26, 'group_id': 'blob'}
        scenario.args = SimpleNamespace(hunt_timeout=1)
        group = SimpleNamespace(group_id='blob', template_id=145,
                                rect=gd.Rect(32700, 32700, 32702, 32702))
        scenario.broker = SimpleNamespace(_world=SimpleNamespace(
            data=SimpleNamespace(spawns=(group,), drops={145: ()})))
        bot = SimpleNamespace(kills=set(), pickups=0, dead=False, hp=100, max_hp=100,
            ground={}, actors={9: {'alive': True, 'template': 145, 'position': (32701, 32701)}},
            position=(32701, 32700), map_id=26, swings=0, last_alive=float('inf'))
        async def attack(uid):
            bot.swings += 1
            bot.kills.add(uid)
        bot.attack = attack
        scenario.bot = bot
        scenario.start_ground = set()
        checks = {}
        scenario.record = lambda name, passed, **details: checks.update({name: (passed, details)})
        asyncio.run(scenario.case_combat())
        self.assertEqual((bot.kills, bot.swings, bot.pickups), ({9}, 1, 0))
        self.assertTrue(checks['received_actor_kill'][0])
        self.assertIn('no_active_drop_policy', checks)
        self.assertNotIn('received_drop_and_pickup', checks)


if __name__ == '__main__':
    unittest.main()
