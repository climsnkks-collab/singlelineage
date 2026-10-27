"""M4 sourced data and broker loopback experiments; no native-game/UI claim.

Fresh fixture inventory/position/coins/tickets and the death test are explicit
development inputs. FIRST/login/select, NPC menus, item use, ship request,
movement, restart, save/restore and cleanup use the real broker/router. The
opaque ship f1 is a trial input, not an asserted native ShipInfo key.
"""
from __future__ import annotations

from dataclasses import fields
import json
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import uuid

from tools.local_original_session import game_data as gd, inventory, movement
from tools.local_original_session import hunt_bot as hb, hunt_bot_scenarios as scenarios
from tools.local_original_session import world_maps as maps, world_town as town
from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_interest_spawn import InterestSpawner, with_dungeon_data
from tools.local_original_session.world_terrain import WorldTerrain


class M4DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = WorldTerrain.load(map_ids=(0, 4))
        cls.policy = maps.load_gludin_policy()

    def test_extension_preserves_existing_policy_and_loads_groups(self):
        with patch.dict(os.environ, {'SL_EXPERIMENT_MAP': '0'}):
            base = with_dungeon_data(gd.load_m1())
        extended = gd.load_m4(base)
        self.assertIs(extended.town, base.town)
        self.assertIs(extended.starter, base.starter)
        self.assertIs(extended.action_speed, base.action_speed)
        self.assertTrue(set(base.items) < set(extended.items))
        self.assertIn(67, extended.items)
        self.assertEqual(extended.spawns[:len(base.spawns)], base.spawns)
        m4_spawns = gd._spawns(gd._read(gd.M1_DATA_DIR.parent / 'm4', 'spawns.json'))
        self.assertEqual(extended.spawns[len(base.spawns):], m4_spawns)
        m4_monsters = gd._monsters(gd._read(gd.M1_DATA_DIR.parent / 'm4', 'monsters.json'))
        for key, monster in m4_monsters.items():
            if key not in base.monsters:
                self.assertEqual(extended.monsters[key], monster)
                continue
            self.assertIs(extended.monsters[key], base.monsters[key])
            self.assertIs(extended.drops[key], base.drops[key])
            for field in fields(monster):
                if field.name != 'sources':
                    self.assertEqual(getattr(monster, field.name), getattr(base.monsters[key], field.name))

    def test_real_terrain_and_nearby_spawn_lifecycle(self):
        terrain = self.terrain
        self.assertEqual(terrain.bounds(4), (32448, 32128, 34367, 33599))
        self.assertEqual(sum(source.startswith('4/') for source in terrain.sources), 650)
        data = gd.load_m4(gd.load_m1())
        entities = EntityRegistry()
        spawner = InterestSpawner(entities, data, passable=terrain.can_stand, rng=random.Random(17))
        self.assertFalse(any(g.active for g in spawner.groups))
        self.assertTrue(spawner.update_interest(((4, 32770, 32740),), 0))
        # This lifecycle assertion keeps the original east Gludio fixture;
        # expansion rectangles have their own all-cell terrain checks.
        groups = [g for g in spawner.groups if g.spec.group_id in {
            'm4_gludio_east_zombie', 'm4_gludio_east_skeleton',
            'm4_gludio_east_skeleton_archer'}]
        self.assertEqual(sum(g.spec.target_count for g in groups), 9)
        self.assertEqual(sum(s.uid is not None for g in groups for s in g.slots), 9)
        for group in groups:
            for slot in group.slots:
                entity = entities.get(slot.uid)
                self.assertIs(terrain.can_stand(4, entity.x, entity.y), True)
                self.assertTrue(group.spec.rect.contains(entity.x, entity.y))
        first = groups[0].slots[0]
        identity = (first.uid, first.hp, first.home)
        spawner.update_interest(((0, 32578, 32946),), 1)
        self.assertFalse(any(g.active for g in groups))
        spawner.update_interest(((4, 32770, 32740),), 2)
        self.assertEqual((first.uid, first.hp, first.home), identity)

    def test_town_merge_confirmed_defaults_and_blocked_count0_exclusions(self):
        base = town.load_town()
        merged = town.with_gludin_town(base)
        extra = town.load_town(gd.M1_DATA_DIR.parent / 'm4')
        self.assertEqual(len(merged.placements), len(base.placements) + len(extra.placements))
        self.assertEqual(town.confirmed_npc_ids(extra), {80093, 80098})
        registry = EntityRegistry()
        owner = town.TownNpcs(registry, merged,
            town.TownConfig(candidate_npc_ids=town.confirmed_npc_ids(merged)),
            passable=lambda m, x, y: m != 4 or self.terrain.can_stand(m, x, y))
        owner.register()
        confirmed = [owner.npc_for(e.uid) for e in registry if e.map_id == 4]
        self.assertEqual({p.npc_id for p in confirmed}, {80093, 80098})
        self.assertTrue(all(owner.appearance(e.uid).sprite_id is not None for e in registry))
        owner.register(town.TownConfig(enable_candidates=True, include_special=True, include_adjacent=True))
        self.assertFalse(any(owner.npc_for(e.uid).key == (60007, 60004) for e in registry))
        self.assertFalse(any(owner.npc_for(e.uid).spawn['count'] == 0 for e in registry))
        self.assertEqual(merged.placements[(60007, 60004)].spawn['locx'], 32618)
        owner.close()
        self.assertEqual(len(registry), 0)

    def test_local_return_and_boat_centers_standable_but_interiors_unknown(self):
        for destination in (self.policy.town_return, *(r.destination for r in self.policy.boats)):
            self.assertIs(self.terrain.can_stand(destination.map_id, destination.x, destination.y), True)
        self.assertIsNone(self.terrain.bounds(5))
        self.assertIsNone(self.terrain.bounds(6))
        for route in self.policy.boats:
            self.assertIs(self.policy.boat_at(route.source_map, route.dock.x1, route.dock.y1), route)
            self.assertIsNone(self.policy.boat_at(route.source_map, route.dock.x1 - 1, route.dock.y1))

    def test_map4_is_only_served_by_mapexp2(self):
        from types import SimpleNamespace
        from tools.local_original_session.world_core_maps import realm_serves_map
        for mode in (0, 1, 2, 3):
            self.assertEqual(realm_serves_map(SimpleNamespace(_world_map_exp=mode), 4), mode == 2)


class GludinScenarioBot(scenarios.ScenarioBot):
    def apply(self, frame):
        if frame.opcode == 0x4e44:
            frame.values = hb.fields(frame.wire[4:-2])
        super().apply(frame)

    async def login(self):
        try:
            await super().login()
        except hb.BotFailure as error:
            # Extend this test client's old map0/1/2 assertion only after the
            # real login/select has received map4 + self/status. No server
            # readiness, packet response or PositionStore rule is replaced.
            if (str(error) != 'MAP0_SELF_POSITION_AND_HP_REQUIRED' or self.map_id != 4
                    or self.position is None or self.hp is None or not self.max_hp):
                raise
            await self.alive()


class GludinScenario(scenarios.Scenario):
    async def open(self, **options):
        with patch.object(scenarios, 'ScenarioBot', GludinScenarioBot):
            await super().open(**options)


class M4LoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.environment = patch.dict(os.environ, {'SL_EXPERIMENT_MAP': '2',
                                                  'SL_WORLD_TOWN_CANDIDATES': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.scene = None

    async def asyncTearDown(self):
        if self.scene is not None:
            self.assertTrue(await self.scene.close(), self.scene.epochs)

    async def open_fixture(self, origin, *, ticket=None):
        from tools.local_original_session import hunt_bot_scenarios as scenarios
        from tools.local_original_session import broker as host
        from tools.local_original_session.hunt_bot_loopback import START, KNIGHT
        root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
        root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='m4-gludin-', dir=root))
        broker, store, _ = await scenarios.build_epoch(directory, str(uuid.uuid4()), seed=True)
        try:
            self.assertIs(broker._world.terrain.can_stand(*origin), True)
            prior = broker.realm.positions.restore(movement.Position(1, KNIGHT[0], 0, *START))
            if origin[0] == 0:
                broker.realm.positions.commit(prior, movement.Position(1, prior.name, *origin))
            before = store.restore(1)
            rows = [dict(i.raw_fields) for i in inventory.validate_kit_frame(before)]
            next(r for r in rows if r[2] == 7)[4] = 2000
            if ticket is not None:
                item = dict(host.INVENTORY_STARTER_FIELDS)
                item.update({1: max(r[1] for r in rows) + 1, 2: ticket, 4: 1, 7: 0})
                rows.append(item)
            store.replace_kit(1, before, inventory.build_kit_frame(rows), append=True)
        finally:
            self.assertTrue((await broker.close())['cleanup_complete'])
        if origin[0] != 0:
            # Fresh, unselected development starting snapshot only. This does
            # not exercise or replace the product's cross-map PositionStore
            # commit. The boat/Lucas tests still use that real transition.
            (directory / 'positions.json').write_text(json.dumps(dict(version=1,
                positions=[dict(uid=1, map_id=origin[0], grid=list(origin[1:]))])) + '\n',
                encoding='utf-8')
        args = scenarios.parser().parse_args(['--timeout', '5'])
        self.scene = GludinScenario(args, 'm4_gludin', directory)
        await self.scene.open(seed=False)
        print('M4_DEV_FIXTURE=' + str(directory))
        return self.scene.broker, self.scene.bot

    def assert_position(self, expected):
        broker, bot = self.scene.broker, self.scene.bot
        service = broker.realm.service(broker._claims[12000][-1]['writer'])
        position = service.snapshot()
        self.assertEqual((position.map_id, position.word0, position.word1), expected)
        self.assertEqual((bot.map_id, *bot.position), expected)
        self.assertEqual(broker.realm.positions.restore(position), position)
        self.assertEqual(broker._world.pcs[bot.self_uid], expected)

    async def action(self, target, literal, response):
        from tools.local_original_session import hunt_bot as hb
        return await self.scene.bot.peer.request(0x4ed4, hb.uint(1, target)
            + hb.pb.encode_bytes(2, literal.encode()) + hb.uint(4, 0) + hb.uint(5, 0), check=response)

    async def test_lucas_menu_paid_map4_move_and_reconnect(self):
        from tools.local_original_session import hunt_bot as hb
        broker, bot = await self.open_fixture((0, 32583, 32923))
        lucas = next(e for e in broker._world.entities
                     if (npc := broker._world.town.npc_for(e.uid)) is not None and npc.npc_id == 50015)
        # His native appearance remains unavailable: resolve the current
        # backend fixture NPC, without fabricating a Classic sprite/f39.
        self.assertIsNone(broker._world.town.appearance(lucas.uid).sprite_id)
        clicked = await bot.peer.request(0x4e43, hb.uint(1, lucas.uid),
                                        check=lambda batch: hb.find(batch, 0x4e44))
        menu = hb.find(clicked, 0x4e44)
        self.assertEqual(hb.scalar(menu.values, 2), b'lucas1')
        context = hb.scalar(menu.values, 1)
        pages = await self.action(context, 'teleportURL', lambda batch: hb.find(batch, 0x4e44))
        self.assertEqual(hb.scalar(hb.find(pages, 0x4e44).values, 2), b'lucas2')
        frames = await self.action(context, 'island-gludin', lambda batch: hb.find(batch, 0x4e96,
                                                                       **{'2': bot.self_uid}))
        maps_received = hb.find(frames, 0x4e95)
        status = hb.find(frames, 0x4e38)
        own = hb.find(frames, 0x4e96, **{'2': bot.self_uid})
        self.assertLess(maps_received.ordinal, status.ordinal)
        self.assertLess(status.ordinal, own.ordinal)
        self.assert_position((4, 32608, 32734))
        self.assertEqual(next(r[4] for r in bot.inventory.values() if r[2] == 7), 500)
        self.assertEqual(next(dict(i.raw_fields)[4] for i in inventory.validate_kit_frame(
            self.scene.store.restore(bot.self_uid)) if i.template_bits == 7), 500)
        # Ordinary next movement uses the destination's terrain and map owner.
        choice = next(h for h in range(8) if broker._world_edge_fallback(4, *bot.position, h) is True)
        destination = (bot.position[0] + hb.DELTAS[choice][0], bot.position[1] + hb.DELTAS[choice][1])
        await bot.step(destination)
        self.assert_position((4, *destination))
        character = bot.character
        self.assertTrue(await self.scene.close())
        await self.scene.open(seed=False, character=character)
        self.assert_position((4, *destination))

    async def test_gludin_return_scroll_uses_local_town(self):
        from tools.local_original_session import hunt_bot as hb
        _, bot = await self.open_fixture((4, 32610, 32734))
        identifier = next(uid for uid, row in bot.inventory.items() if row[2] == 162)
        quantity = bot.inventory[identifier][4]
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        await bot.peer.request(0x0960, hb.uint(1, identifier) + hb.pb.encode_bytes(2, params),
            check=lambda batch: hb.find(batch, 0x4e96, **{'2': bot.self_uid}))
        self.assert_position((4, 32608, 32734))
        if quantity == 1:
            self.assertNotIn(identifier, bot.inventory)
        else:
            self.assertEqual(bot.inventory[identifier][4], quantity - 1)
        saved = {i.identifier: dict(i.raw_fields) for i in inventory.validate_kit_frame(
            self.scene.store.restore(bot.self_uid))}
        self.assertEqual(saved.get(identifier, {}).get(4, 0), quantity - 1)

    async def test_boat_each_direction_consumes_owned_ticket_and_saves(self):
        from tools.local_original_session import hunt_bot as hb
        for origin, template, expected in (((0, 32630, 32982), 124, (4, 32569, 32726)),
                                            ((4, 32544, 32727), 125, (0, 32632, 32963))):
            with self.subTest(origin=origin):
                broker, bot = await self.open_fixture(origin, ticket=template)
                try:
                    ticket = next(uid for uid, row in bot.inventory.items() if row[2] == template)
                    frames = await bot.peer.request(0x4ef8, hb.uint(1, 173),
                        check=lambda batch: hb.find(batch, 0x4e96, **{'2': bot.self_uid}))
                    self.assert_position(expected)
                    self.assertNotIn(ticket, bot.inventory)
                    self.assertFalse(any(i.identifier == ticket for i in inventory.validate_kit_frame(
                        self.scene.store.restore(bot.self_uid))))
                    self.assertFalse(any(f.opcode == 0x4f0e for f in frames))
                    before = broker._world_map_transitions
                    await bot.peer.request(0x4ef8, hb.uint(1, 173), alive=True,
                                           check=lambda batch: hb.find(batch, 0x4f57))
                    self.assertEqual(broker._world_map_transitions, before)
                    self.assert_position(expected)
                finally:
                    self.assertTrue(await self.scene.close(), self.scene.epochs)

    async def test_boat_without_ticket_refuses_before_position_or_inventory_change(self):
        from tools.local_original_session import hunt_bot as hb
        broker, bot = await self.open_fixture((0, 32630, 32982))
        before = self.scene.store.restore(bot.self_uid)
        await bot.peer.request(0x4ef8, hb.uint(1, 173), alive=True,
                               check=lambda batch: hb.find(batch, 0x4f57))
        self.assert_position((0, 32630, 32982))
        self.assertEqual(self.scene.store.restore(bot.self_uid), before)
        self.assertIn('BOAT_OWNED_TICKET_REQUIRED', broker._world_handler_errors)

    async def test_development_death_then_real_restart_reselect_returns_gludin(self):
        from tools.local_original_session import hunt_bot as hb
        broker, bot = await self.open_fixture((4, 32610, 32734))
        uid = bot.self_uid

        def development_death():
            # Explicit direct-call fixture, not natural-combat or formal PASS.
            state = broker._world.combat.pcs[uid]
            state.hp, state.dead = 0, True
            broker._world._pc_died(uid, broker._world.runtime.clock())

        await broker._world.runtime.dispatch_now(development_death)
        await bot.alive()
        await bot.peer.request(0x4eec, check=lambda batch: hb.find(batch, 0x4e3b, **{'1': 1}))
        bot.selected = False
        await bot.reselect()
        self.assert_position((4, 32608, 32734))
        self.assertGreater(bot.hp, 0)
        self.assertNotIn(uid, broker._world_relocations)
        self.assertNotIn(uid, broker._world_respawn)


if __name__ == '__main__':
    unittest.main(verbosity=2)
