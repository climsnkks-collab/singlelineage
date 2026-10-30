"""M5 sourced-data checks and one owned socket scenario; native UI unverified.

Run this module alone so its sequential port ownership is explicit. The
starting map4/level5 fixture is developmental; packet and direct-call checks
are reported separately from original-client completion.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import MethodType, SimpleNamespace
from types import MappingProxyType
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import game_data as gd, world_town as town
from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_terrain import WorldTerrain

M5 = gd.M1_DATA_DIR.parent / 'm5'


class M5DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = WorldTerrain.load(map_ids=(0, 4))
        cls.document = json.loads((M5 / 'towns.json').read_text(encoding='utf-8'))

    def test_five_village_regions_and_fixed_returns_use_real_terrain(self):
        rows = self.document['towns']
        self.assertEqual({row['town_id'] for row in rows},
                         {'kent', 'windawood', 'giran', 'oren', 'heine'})
        woodbec = next(row for row in rows if row['town_id'] == 'windawood')
        self.assertEqual(woodbec['region_ids'], [147, 148])
        self.assertNotIn(111, woodbec['region_ids'])
        for row in rows:
            with self.subTest(town=row['town_id']):
                point = row['return_point']
                self.assertEqual(point['map_id'], 4)
                self.assertIs(self.terrain.can_stand(4, point['x'], point['y']), True)
                self.assertEqual(row['return_source']['kind'], 'local_policy')
                self.assertTrue(any(box['bounds']['_left'] <= point['x'] <= box['bounds']['_right']
                    and box['bounds']['_top'] <= point['y'] <= box['bounds']['_bottom']
                    for box in row['regions']))

    def test_spawn_rectangles_are_finite_fully_standable_outside_towns(self):
        groups = gd._spawns(gd._read(M5, 'spawns.json'))
        self.assertTrue(groups)
        self.assertEqual(len({group.group_id for group in groups}), len(groups))
        for group in groups:
            with self.subTest(group=group.group_id):
                self.assertEqual(group.map_id, 4)
                self.assertGreater(group.target_count, 0)
                # Registry-population rectangles (spawn audit) may include
                # blocked cells: the spawner only places on can_stand tiles, so
                # they need enough standable cells; original rows stay full.
                partial = group.group_id.startswith('registry_population_')
                standable = 0
                for y in range(group.rect.y1, group.rect.y2 + 1):
                    for x in range(group.rect.x1, group.rect.x2 + 1):
                        if self.terrain.can_stand(4, x, y) is not True:
                            self.assertTrue(partial, (group.group_id, x, y))
                            continue
                        standable += 1
                        self.assertFalse(any(box['bounds']['_left'] <= x <= box['bounds']['_right']
                            and box['bounds']['_top'] <= y <= box['bounds']['_bottom']
                            for row in self.document['towns'] for box in row['regions']))
                self.assertGreaterEqual(standable, group.target_count, group.group_id)

    def test_registration_preserves_source_counts_and_excludes_unstandable_centres(self):
        data = town.load_town(M5)
        entities = EntityRegistry()
        owner = town.TownNpcs(entities, data, town.TownConfig(enable_candidates=True,
            include_special=True, include_adjacent=True), passable=self.terrain.can_stand)
        owner.register()
        enabled = {npc.key for npc in data.placements.values() if npc.spawn['count'] > 0
            and self.terrain.can_stand(npc.spawn['mapid'], npc.spawn['locx'], npc.spawn['locy']) is True}
        actual = {npc.key for _, npc, _ in owner._owned.values()}
        self.assertEqual(actual, enabled)
        for entity in entities:
            self.assertIs(self.terrain.can_stand(entity.map_id, entity.x, entity.y), True)
        owner.close()
        self.assertEqual(len(entities), 0)

    def test_extension_retains_existing_shared_templates_rewards_and_core_data(self):
        from tools.local_original_session.world_feature_m5 import load_m5_data
        base = gd.load_m4(gd.load_m1())
        merged = load_m5_data(base)
        self.assertIs(merged.town, base.town)
        self.assertIs(merged.starter, base.starter)
        self.assertIs(merged.action_speed, base.action_speed)
        self.assertEqual(merged.spawns[:len(base.spawns)], base.spawns)
        for key, value in base.monsters.items():
            self.assertIs(merged.monsters[key], value)
            self.assertIs(merged.drops[key], base.drops[key])

    def test_development_death_hook_chooses_regional_towns_and_preserves_pending_other_uid(self):
        # Explicit direct hook check. This does not claim natural combat death,
        # Restart/reselection packets, revival or death-penalty verification.
        from tools.local_original_session.world_feature_m5 import load_m5_policy, _m5_after_death
        from tools.local_original_session.world_core_life import _world_set_relocation
        import random
        policy = load_m5_policy(can_stand=self.terrain.can_stand)
        for row in self.document['towns']:
            with self.subTest(town=row['town_id']):
                point = row['return_point']
                entity = SimpleNamespace(map_id=4, x=point['x'] + 1, y=point['y'])
                owner = SimpleNamespace(_world_m5=policy,
                    world=SimpleNamespace(entities=SimpleNamespace(get=Mock(return_value=entity)),
                        combat=SimpleNamespace(pcs={1:SimpleNamespace(profile=SimpleNamespace(character_class=1))},
                                               rng=random.Random(17))),
                    _world_relocations={99: 'preserved'})
                owner._world_set_relocation = MethodType(_world_set_relocation, owner)
                _m5_after_death(owner, 1)
                self.assertEqual(owner._world_relocations[99], 'preserved')
                destination = owner._world_relocations[1]
                self.assertIn(destination, policy.return_candidates(4, entity.x, entity.y, 1))
                entity.map_id = 0
                del owner._world_relocations[1]
                _m5_after_death(owner, 1)
                self.assertNotIn(1, owner._world_relocations)

    def test_selected_teleport_actions_prices_and_destination_terrain(self):
        from tools.local_original_session.world_town_services import load_town_services
        services = load_town_services(M5)
        raw = json.loads((M5 / 'town_services.json').read_text(encoding='utf-8'))
        resources = json.loads((M5 / 'npc_menus.json').read_text(encoding='utf-8'))['resources']
        self.assertEqual(len(raw['teleporters']), 6)  # Gludin and five villages.
        for source in raw['teleporters']:
            self.assertTrue(source['destinations'])
            actions = resources[source['stem']]['actions']
            for row in source['destinations']:
                with self.subTest(npc=source['l1j_npc_id'], action=row['action']):
                    self.assertIn(row['action'].removeprefix('teleport '), actions)
                    route = services.teleports[source['l1j_npc_id'], row['action']]
                    self.assertGreaterEqual(route.price, 0)
                    self.assertTrue(route.source_ref)
                    self.assertIs(self.terrain.can_stand(route.map_id, route.x, route.y), True)

    def test_gludin_island_uses_sourced_coordinates_price_and_funds_boundary(self):
        from tools.local_original_session.world_town_services import (
            TownServiceError, calculate_teleport, load_town_services)
        services = load_town_services(M5)
        trip = calculate_teleport(services, 50024, 'teleport gludin-island',
                                  adena=550, level=5)
        self.assertEqual((trip.destination.map_id, trip.destination.x,
                          trip.destination.y, trip.destination.heading),
                         (0, 32583, 32924, 5))
        self.assertEqual((trip.cost, trip.adena_after), (550, 0))
        self.assertIs(self.terrain.can_stand(0, 32583, 32924), True)
        with self.assertRaisesRegex(TownServiceError, '^INSUFFICIENT_ADENA$'):
            calculate_teleport(services, 50024, 'teleport gludin-island',
                               adena=549, level=5)

    def test_optional_registry_removal_and_disabled_initializer(self):
        from tools.local_original_session import world_handlers as handlers
        from tools.local_original_session.world_feature_m5 import _m5_initialize
        names = tuple(name for name in handlers.FEATURE_MODULES if name != 'world_feature_m5')
        handlers.feature_registry.cache_clear()
        try:
            with patch.object(handlers, 'FEATURE_MODULES', names):
                registry = handlers.feature_registry()
            self.assertFalse(any(name.startswith('_m5_') for name in registry.methods))
            self.assertFalse(any(name.startswith('_m5_') for names in registry.hooks.values() for name in names))
            self.assertIn('_world_maps_initialize', registry.methods)
        finally:
            handlers.feature_registry.cache_clear()
        owner = SimpleNamespace(_world_map_exp=2)
        with patch.dict(os.environ, {'SL_EXPERIMENT_M5': '0'}), patch(
                'tools.local_original_session.world_feature_m5._read', side_effect=AssertionError('DISABLED_IO')):
            _m5_initialize(owner)
        self.assertIsNone(owner._world_m5)

    def test_initialize_retains_existing_live_refs_external_source_and_callbacks(self):
        import random
        from tools.local_original_session import world_handlers as handlers
        from tools.local_original_session.world_bridge import Context
        from tools.local_original_session.world_feature_m5 import _m5_initialize, _m5_town_setup
        from tools.local_original_session.world_shop_menu import ShopExperiment
        from tools.local_original_session.world_town_services import load_town_services
        from tools.local_original_session.world_visibility import WorldView
        data = gd.load_m4(gd.load_m1())
        world = WorldView.create(data=data, terrain=self.terrain,
            passable=self.terrain.can_stand, rng=random.Random(11))
        self.addCleanup(world.close)
        entities = world.entities
        old = town.TownNpcs(entities, town.with_gludin_town(town.load_town()),
            town.TownConfig(candidate_npc_ids={50015}), passable=self.terrain.can_stand)
        # The retained source is on map0; terrain for that map remains the
        # existing owner's decision. This unit fixture registers it directly.
        old.passable = None
        old.register()
        retained = {uid: (entities.get(uid), record) for uid, record in old._owned.items()}
        self.assertTrue(retained)
        uid, (entity, (_, npc, _)) = next(iter(retained.items()))
        resource = SimpleNamespace(current=Mock(return_value=True), dialogue_target=uid)
        external = handlers.HostNpcSource(resource, npc.key, MappingProxyType({}))
        allocate, seller = Mock(), Mock()
        bindings = handlers.HostBindings(object(), old, MappingProxyType({npc.key: external}),
            MappingProxyType({}), 15, allocate, seller)
        owner = SimpleNamespace(_world=world, _world_map_exp=2, _world_services=load_town_services(),
            _world_handler_bindings=bindings, _world_shop_experiment=ShopExperiment())
        context = Context(owner)
        with patch.dict(os.environ, {'SL_EXPERIMENT_M5': '1'}):
            _m5_initialize(context)
            configured = _m5_town_setup(context, town.TownSetup(old,
                owner._world_services, (external,), owner._world_shop_experiment))
            owner._world_services = configured.services
            town.attach_view(world, configured.town)
            context.configure_town(configured.town, configured.sources, refresh_policies=False)
        for uid, (entity, record) in retained.items():
            self.assertIs(entities.resolve(record[0]), entity)
            self.assertEqual(world.town._owned[uid], record)
        self.assertEqual(old._owned, {})
        self.assertIs(owner._world_handler_bindings.sources[npc.key], external)
        self.assertEqual(resource.dialogue_target, entity.uid)
        self.assertIs(owner._world_handler_bindings.allocate_uid, allocate)
        self.assertIs(owner._world_handler_bindings.sale_item, seller)
        world.town.close()


class M5BotActionTests(unittest.TestCase):
    def test_pickup_action_preserves_life_and_death_action_ends_it(self):
        from tools.local_original_session import hunt_bot as hb, hunt_bot_scenarios as hs
        from tools.local_original_session import player_life_codec, world_visibility
        bot = hs.ScenarioBot(SimpleNamespace())
        bot.self_uid, bot.hp, bot.max_hp = 1, 18, 20
        bot.actors[2] = dict(position=(10, 10), template=2, alive=True)
        bot.last_attacker[2] = bot.self_uid

        def receive(wire, ordinal):
            bot.apply(hb.Received(ordinal, 0, int.from_bytes(wire[2:4], 'little'),
                hb.fields(wire[4:-2]), wire))

        for ordinal, uid in enumerate((1, 2), 1):
            receive(world_visibility.pickup_frame(uid), ordinal)
        self.assertFalse(bot.dead)
        self.assertFalse(bot.own_death_frame)
        self.assertEqual(bot.hp, 18)
        self.assertTrue(bot.actors[2]['alive'])
        self.assertEqual(bot.deaths, set())
        self.assertEqual(bot.kills, set())

        receive(player_life_codec.death(2), 3)
        self.assertFalse(bot.actors[2]['alive'])
        self.assertEqual(bot.kills, {2})
        self.assertFalse(bot.dead)
        receive(player_life_codec.death(1), 4)
        self.assertTrue(bot.dead)
        self.assertTrue(bot.own_death_frame)
        self.assertEqual(bot.deaths, {1, 2})


class M5PacketTests(unittest.IsolatedAsyncioTestCase):
    async def test_mainland_services_field_recall_and_saved_reconnect(self):
        from tools.local_original_session import hunt_bot_m5 as bot
        # This regression's saved-position/inventory/warehouse assertions are
        # Kent-scoped; the standalone bot's wider town selector is separate.
        args = bot.parser().parse_args(['--towns', 'kent', '--navigation-timeout', '240', '--hunt-timeout', '180',
            '--output-root', str(Path(__file__).resolve().parents[2] / '_work/m5_returns')])
        if output_root := os.environ.get('SL_TEST_OUTPUT_ROOT'):
            args.output_root = Path(output_root)
        with patch.dict(os.environ, {'SL_TEST_PORT_BASE': os.environ.get('SL_TEST_PORT_BASE', '20000')}):
            result = await bot.run(args)
        print('M5_PACKET_RESULT=' + result['directory'])
        self.assertTrue(result['cleanup_complete'], result['directory'])
        self.assertEqual(result['status'], 'PASS',
                         {key: result[key] for key in ('directory', 'failure', 'gaps', 'failures')})
        checks = {row['check']: row for row in result['checks']}
        for name in ('kent_paid_teleport_saved', 'kent_shop_buy_saved',
                     'kent_shop_sell_saved', 'kent_warehouse_deposit_saved',
                     'kent_warehouse_withdraw_saved', 'kent_field_received_combat_drop',
                     'kent_recall_saved_local_return',
                     'mainland_saved_position_inventory_warehouse_restored'):
            self.assertEqual(checks[name]['status'], 'PASS', (name, result['directory']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
