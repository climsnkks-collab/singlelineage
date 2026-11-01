"""Development return-policy/consumer checks; no client, sockets or game input."""
from pathlib import Path
import random
from types import MethodType, SimpleNamespace
import unittest
import uuid

from tools.local_original_session import movement, world_core_life, world_core_maps
from tools.local_original_session import world_feature_dungeons as dungeons
from tools.local_original_session import world_feature_m5 as m5
from tools.local_original_session.world_item_effects import WorldItemEffects, ItemEffectResult
from tools.local_original_session.world_maps import MapDestination, load_dungeon_policy
from tools.local_original_session.world_terrain import WorldTerrain


class ReturnFixture:
    @classmethod
    def setUpClass(cls):
        cls.terrain = WorldTerrain.load(map_ids=(4,))
        cls.policy = m5.load_m5_policy(can_stand=cls.terrain.can_stand)

    def town_points(self, town_id):
        return self.policy.getback.towns[town_id]

    def assert_town(self, map_id, x, y, town_id, cls=1):
        self.assertEqual(self.policy.return_candidates(map_id, x, y, cls), self.town_points(town_id))


class ReturnPolicyTests(ReturnFixture, unittest.TestCase):
    def test_regional_towns_supersede_nearest_point_and_supply_only_metadata(self):
        # The old nearest-point implementation sent these supply bases elsewhere.
        self.assert_town(4, 33096, 33402, 2)
        self.assert_town(4, 32738, 32448, 4)
        for x, y, town_id in ((32600, 32700, 3), (32600, 33200, 5),
                (33050, 32780, 6), (33429, 32814, 7), (33604, 33237, 8),
                (33722, 32496, 9), (34053, 32284, 10), (33962, 33254, 12)):
            with self.subTest(x=x, y=y):
                self.assert_town(4, x, y, town_id)

    def test_inclusive_boundaries_use_sql_area_x1_descending_precedence(self):
        # 33280 is simultaneously Kent's inclusive x2 and Giran's x1.
        self.assert_town(4, 33279, 32511, 6)
        self.assert_town(4, 33280, 32511, 7)
        # 32574 touches Werldan and the southern Giran rectangle.
        self.assert_town(4, 33536, 32573, 9)
        self.assert_town(4, 33536, 32574, 7)
        self.assert_town(4, 32959, 32536, 4)
        self.assert_town(4, 32959, 32537, 3)
        self.assert_town(4, 32960, 32511, 6)
        self.assert_town(4, 32960, 32510, 4)

    def test_supported_classes_use_elf_override_only_in_sourced_regions(self):
        for cls in range(4):
            town_id = 11 if cls == 2 else 4
            self.assert_town(4, 33000, 32300, town_id, cls)
            self.assert_town(19, 32805, 32724, town_id, cls)
            self.assert_town(20, 32750, 32750, town_id, cls)
            self.assert_town(21, 32750, 32750, town_id, cls)
            self.assert_town(4, 33300, 32300, 11 if cls == 2 else 7, cls)
            self.assert_town(4, 32738, 32448, 4, cls)
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_CHARACTER_CLASS'):
            self.policy.return_for(4, 33000, 32300, 4)

    def test_mainland_dungeon_town_override_uses_random_pool_not_raw_sql_point(self):
        for map_id, town_id in ((7, 3), (13, 3), (23, 5), (25, 2),
                (43, 2), (51, 2), (30, 7), (56, 7), (59, 8), (65, 8),
                (72, 10), (82, 10), (101, 12), (110, 12)):
            self.assert_town(map_id, 32750, 32750, town_id)
        legacy = load_dungeon_policy()
        selected = {r.map_id for r in self.policy.getback.rules}
        expected = ({4, 23, 24, 29, 65} | set(range(7, 14)) | set(range(19, 22))
            | set(range(25, 29)) | set(range(30, 34)) | set(range(35, 38))
            | set(range(43, 52)) | set(range(53, 57)) | set(range(59, 64))
            | set(range(72, 83)) | set(range(101, 111)))
        self.assertEqual(selected, expected)
        self.assertLessEqual(selected - {4}, set(legacy.maps))

    def test_random_choice_covers_pool_and_reuses_supplied_rng(self):
        rng = random.Random(37)
        outcomes = {self.policy.return_for(4, 33096, 33402, 1, rng=rng) for _ in range(100)}
        self.assertEqual(outcomes, set(self.town_points(2)))
        first, second = random.Random(71), random.Random(71)
        self.assertEqual([self.policy.return_for(19, 0, 0, 2, rng=first) for _ in range(20)],
                         [self.policy.return_for(19, 0, 0, 2, rng=second) for _ in range(20)])

    def test_unmatched_area_fallback_and_unowned_maps_are_explicit(self):
        self.assertEqual(self.policy.return_for(4, 1, 1, 1),
                         MapDestination(4, 33089, 33397, 5))
        for map_id in (0, 1, 2, 5, 6, 303, 999):
            self.assertIsNone(self.policy.return_for(map_id, 32750, 32750, 1))

    def test_only_source_points_survive_terrain_filter_without_substitutions(self):
        all_points = {p for points in self.policy.getback.towns.values() for p in points}
        for point in all_points:
            self.assertIs(self.terrain.can_stand(point.map_id, point.x, point.y), True)
        excluded = self.town_points(2)[0]
        policy = m5.load_m5_policy(can_stand=lambda map_id, x, y:
            False if (map_id, x, y) == (excluded.map_id, excluded.x, excluded.y) else True)
        self.assertEqual(policy.return_candidates(4, 33096, 33402, 1),
                         tuple(p for p in self.town_points(2) if p != excluded))
        unavailable = m5.load_m5_policy(can_stand=lambda *args: False)
        with self.assertRaisesRegex(ValueError, 'GETBACK_KNOWN_DESTINATION_REQUIRED'):
            unavailable.return_for(4, 33096, 33402, 1)


class ReturnConsumerTests(ReturnFixture, unittest.TestCase):
    def context(self, cls=2):
        rng = random.Random(51)
        combat = SimpleNamespace(pcs={17: SimpleNamespace(profile=SimpleNamespace(character_class=cls)),
                                      99: SimpleNamespace(profile=SimpleNamespace(character_class=1))}, rng=rng)
        entity = SimpleNamespace(uid=17, map_id=19, x=32805, y=32724)
        world = SimpleNamespace(combat=combat, entities=SimpleNamespace(get=lambda uid: entity if uid == 17 else None),
                                data=SimpleNamespace(town=SimpleNamespace(map_id=0, respawn_x=32578, respawn_y=32946)))
        combat.data = world.data
        ctx = SimpleNamespace(world=world, _world_m5=self.policy,
            _world_dungeon_policy=load_dungeon_policy(), _world_relocations={99: 'preserved'})
        ctx._world_set_relocation = MethodType(world_core_life._world_set_relocation, ctx)
        return ctx, entity

    def test_real_effect_proposal_preserves_uid_through_earlier_dungeon_hook(self):
        ctx, entity = self.context()
        effects = m5.MainlandItemEffects(WorldItemEffects(ctx.world.combat, self.terrain), self.policy)
        position = MapDestination(19, entity.x, entity.y, 5)  # production hook lacks uid
        # Real WorldItemEffects requires the selected PC to be living.
        pc = ctx.world.combat.pcs[17]
        pc.dead, pc.hp = False, 20
        result = effects.use(17, 162, 0, position=position)
        self.assertEqual((result.return_uid, result.consume_count), (17, 1))
        result = dungeons._world_dungeons_destination(ctx, result, position)
        self.assertEqual(result.return_uid, 17)
        result = m5._m5_destination(ctx, result, position)
        self.assertIn(result.destination, self.town_points(11))
        self.assertNotIn(result.destination, self.town_points(4))
        self.assertEqual(result.consume_count, 1)
        self.assertEqual([r.kind for r in result.requirements], ['teleport', 'map_notify'])

    def test_request_identity_is_per_result_and_non_return_effects_are_unchanged(self):
        ctx, entity = self.context()
        class Previous:
            def use(self, uid, template_id, now, **options):
                return ItemEffectResult(template_id, 'return_town' if template_id == 162 else 'heal',
                    'destination_proposed', destination=MapDestination(0, 32578, 32946, 5))
        effects = m5.MainlandItemEffects(Previous(), self.policy)
        position = MapDestination(19, entity.x, entity.y, 5)
        elf = effects.use(17, 162, 0, position=position)
        knight = effects.use(99, 162, 0, position=position)
        self.assertIn(m5._m5_destination(ctx, elf, position).destination, self.town_points(11))
        self.assertIn(m5._m5_destination(ctx, knight, position).destination, self.town_points(4))
        heal = effects.use(17, 14, 0, position=position)
        self.assertIs(m5._m5_destination(ctx, heal, position), heal)

    def test_death_queues_class_return_and_existing_respawn_consumer_commits_then_clears(self):
        ctx, entity = self.context()
        before = (entity.map_id, entity.x, entity.y)
        dungeons._world_dungeons_death(ctx, 17)
        m5._m5_after_death(ctx, 17)
        target = ctx._world_relocations[17]
        self.assertIn(target, self.town_points(11))
        self.assertEqual((entity.map_id, entity.x, entity.y), before)
        self.assertEqual(ctx._world_relocations[99], 'preserved')
        # Existing PositionStore bytes/CAS and respawn consumer, on a fresh copy.
        from tools.local_original_session.movement import PositionStore
        directory = Path(__file__).resolve().parents[2] / '_work/m5_returns' / ('respawn-' + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        profile = directory / 'characters.json'
        store = PositionStore(profile)
        start = movement.Position(17, 'Elf', *before)
        store.commit(start, start)
        ctx.realm = SimpleNamespace(positions=store)
        ctx._world = ctx.world
        ctx._world_respawn, ctx._world_respawn_errors = {17: 'Elf'}, []
        self.assertTrue(world_core_life._world_commit_respawn(ctx, 17, strict=True))
        restored = PositionStore(profile).restore(start)
        self.assertEqual((restored.map_id, restored.word0, restored.word1),
                         (target.map_id, target.x, target.y))
        self.assertNotIn(17, ctx._world_respawn)
        self.assertNotIn(17, ctx._world_relocations)


if __name__ == '__main__':
    unittest.main(verbosity=2)
