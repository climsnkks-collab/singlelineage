"""Offline NPC placement regression: source data -> startup owners -> real S32.

Reads existing JSON/SQL/map assets and uses an in-memory registry only. No game,
broker/server, socket, save, subprocess, bot, or temporary files are involved.
L1J placements are backend reference policy; seeded positions and the retry
budget are LOCAL choices, not observed original Classic NPC coordinates.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import world_town as town
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_feature_m5 import _m5_town_setup
from tools.local_original_session.world_feature_town import setup_town
from tools.local_original_session.world_terrain import WorldTerrain


# spawnlist_npc in l1jdb_m10.sql:49242-49245. These are range centres,
# not four claimed fixed tiles. The original JSON and SQL are never rewritten.
SOURCE_ROWS = ((70100, 87553, 'Lengo'), (70101, 87554, 'Fiin'),
               (70102, 87555, 'Judice'), (70529, 87556, 'Mona'))


class NpcPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = town.load_town()
        cls.terrain = WorldTerrain.load(map_ids=(0, 4))

    def owner(self, *, passable=None, data=None):
        return town.TownNpcs(EntityRegistry(), self.data if data is None else data,
            town.TownConfig(candidate_npc_ids={row[0] for row in SOURCE_ROWS}),
            passable=passable)

    def test_source_rows_are_preserved_in_both_consumed_tables(self):
        sql_path = Path(self.data.source_documents['town_npcs']['reference_paths']['l1jdb'])
        # Read only the required source lines instead of retaining the full DB.
        with sql_path.open(encoding='utf-8') as source:
            source_lines = {number: line.strip() for number, line in enumerate(source, 1)
                            if 49242 <= number <= 49245}
        for offset, (npc_id, spawn_id, label) in enumerate(SOURCE_ROWS):
            with self.subTest(npc_id=npc_id):
                npc = self.data.placements[npc_id, spawn_id]
                expected = dict(id=spawn_id, count=1, locx=32575, locy=32946,
                    randomx=25, randomy=25, heading=0, respawn_delay=90,
                    mapid=0, movement_distance=0)
                self.assertEqual({key: npc.spawn[key] for key in expected}, expected)
                self.assertEqual({key: npc.shop_row['spawn'][key] for key in expected}, expected)
                self.assertEqual(npc.spawn['source_ref'], f'l1jdb:{49242 + offset}')
                self.assertEqual(source_lines[49242 + offset],
                    f"INSERT INTO `spawnlist_npc` VALUES ('{spawn_id}', '{label}', '1', "
                    f"'{npc_id}', '32575', '32946', '25', '25', '0', '90', '0', '0');")

    def test_l1j_random25_extremes_are_24_and_use_four_independent_draws(self):
        owner = self.owner()
        npc = self.data.placements[70101, 87554]
        # Source L1Spawn.java:435-438: the two extreme floor results are 0/24.
        # An inclusive uniform +-25 sampler or one-draw axis sampler fails this.
        with patch.object(town.random, 'Random') as factory:
            factory.return_value.random.side_effect = (0.0, 0.999999, 0.999999, 0.0)
            self.assertEqual(owner._placement(npc, 0), (32551, 32970))
            self.assertEqual(factory.return_value.random.call_count, 4)

    def test_blocked_centre_does_not_disable_standable_source_range(self):
        self.assertIs(self.terrain.can_stand(0, 32575, 32946), False)
        owner = self.owner(passable=self.terrain.can_stand)
        entities = owner.register()
        self.assertEqual({owner.npc_for(entity.uid).key for entity in entities},
                         {(row[0], row[1]) for row in SOURCE_ROWS})
        self.assertEqual(len({(entity.map_id, entity.x, entity.y) for entity in entities}), 4)
        for entity in entities:
            with self.subTest(npc=owner.npc_for(entity.uid).key):
                self.assertIs(self.terrain.can_stand(entity.map_id, entity.x, entity.y), True)
                self.assertLessEqual(abs(entity.x - 32575), 24)
                self.assertLessEqual(abs(entity.y - 32946), 24)
                self.assertEqual((entity.map_id, entity.heading), (0, 0))
        # Seeded reproducibility is explicit LOCAL policy, not original tiles.
        again = self.owner(passable=self.terrain.can_stand)
        self.assertEqual([(e.map_id, e.x, e.y) for e in entities],
                         [(e.map_id, e.x, e.y) for e in again.register()])
        self.assertEqual(owner.register(), ())

    def test_exhausted_candidates_cannot_fall_back_to_blocked_or_occupied_centre(self):
        npc = self.data.placements[70101, 87554]
        for occupied in (False, True):
            with self.subTest(occupied=occupied):
                owner = self.owner(passable=(lambda *_: True) if occupied else (lambda *_: False))
                if occupied:
                    owner.entities.add(Kind.NPC, 0, 32575, 32946)
                with patch.object(town.random, 'Random') as factory:
                    factory.return_value.random.return_value = 0.5
                    self.assertIsNone(owner._placement(npc, 0))
                    self.assertEqual(factory.return_value.random.call_count, 64 * 4)
                # No UID is issued for an invalid tile, but a later register
                # with actual terrain can still create all four source slots.
                if not occupied:
                    self.assertEqual(owner.register(), ())
                    owner.passable = self.terrain.can_stand
                    owner.random_passable = self.terrain.can_stand
                    self.assertEqual(len(owner.register()), 4)

    def test_fullworld_initial_registration_and_m5_transfer_keep_valid_tiles(self):
        events = SimpleNamespace(add=lambda *_args, **_kwargs: None)
        world = SimpleNamespace(entities=EntityRegistry(), terrain=self.terrain,
                                extensions={}, events=events)
        context = SimpleNamespace(_world=world, world=world, _world_map_exp=2,
            _world_warehouse_exp=True, _world_handler_bindings=SimpleNamespace(sale_item=object()))
        initial = {}

        def configure(owner, _sources, **_kwargs):
            world.town = owner

        def fold(_hook, setup):
            initial.update({uid: world.entities.resolve(ref)
                            for uid, (ref, _npc, _ordinal) in setup.town._owned.items()})
            return _m5_town_setup(context, setup)

        context.configure_town = configure
        context.collect_sync_hooks = lambda *_args: ()
        context.fold_sync_hooks = fold
        context.add_item_policies = lambda *_args: None
        with patch.dict('os.environ', {'SL_EXPERIMENT_MAP': '2', 'SL_EXPERIMENT_M5': '1',
                'SL_WORLD_TOWN_CANDIDATES': '', 'SL_EXPERIMENT_SHOP': ''}):
            setup_town(context, ())
        self.addCleanup(world.town.close)
        actual = defaultdict(list)
        for entity in world.entities:
            npc = world.town.npc_for(entity.uid)
            if npc is None:
                continue
            actual[entity.map_id, entity.x, entity.y].append(npc.key)
            if npc.spawn.get('randomx', 0) or npc.spawn.get('randomy', 0):
                self.assertIs(self.terrain.can_stand(entity.map_id, entity.x, entity.y), True, npc.key)
        self.assertFalse({tile: keys for tile, keys in actual.items() if len(keys) > 1})
        for uid, original in initial.items():
            self.assertIs(world.entities.get(uid), original)  # M5 keeps UID/lifetime.
        selected = {world.town.npc_for(e.uid).key for e in world.entities}
        self.assertTrue({(row[0], row[1]) for row in SOURCE_ROWS} <= selected)
        # Existing accepted map0 fixed placements/services are not removed or
        # moved by a change to random range consumption. Their blocked S32
        # centres remain a separate unresolved placement limitation.
        for key, kind in (((60001, 60009), 'warehouse'), ((70523, 87192), 'dialogue')):
            entity = next(e for e in world.entities if world.town.npc_for(e.uid).key == key)
            spawn = self.data.placements[key].spawn
            self.assertEqual((entity.x, entity.y), (spawn['locx'], spawn['locy']))
            self.assertIn(entity.uid, initial)
            self.assertIs(world.entities.get(entity.uid), initial[entity.uid])
            self.assertIs(self.terrain.can_stand(entity.map_id, entity.x, entity.y), False)
            interaction = world.town.route_click(entity.uid, player_map_id=entity.map_id,
                player_x=entity.x, player_y=entity.y, max_distance=1)
            self.assertEqual(interaction.kind, kind)
            self.assertEqual(interaction.npc.key, key)


if __name__ == '__main__':
    unittest.main(verbosity=2)
