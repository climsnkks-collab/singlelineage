"""Development consumer checks; no game, socket, user save or formal PASS."""
from dataclasses import replace
from types import MethodType
import json
import unittest

from tools.local_original_session import monster_skills_tests as monster_fixture
from tools.local_original_session import world_magic_tests as magic_fixture
from tools.local_original_session import world_feature_magic as magic_feature
from tools.local_original_session import world_feature_monster_skills as monster_feature
from tools.local_original_session import world_item_effects as items
from tools.local_original_session import world_magic, world_magic_status, world_registry
from tools.local_original_session import world_monster_skills as skills


class MonsterCureConsumerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = magic_fixture.WorldConsumerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.ctx, self.view, self.magic = self.fixture.ctx, self.fixture.view, self.fixture.magic
        self.ctx._world_registry = world_registry.build_registry((magic_feature, monster_feature))
        for fn in monster_feature.METHODS:
            setattr(self.ctx, fn.__name__, MethodType(fn, self.ctx))
        self.owner = skills.MonsterSkills(self.view, skills.load_attacks(),
            provider=self.ctx._world_magic_consumable_provider())
        self.ctx._world_monster_skills = self.owner
        self.owner.start()
        self.addCleanup(self.owner.close)
        self.effects = items.WorldItemEffects(self.view.combat)
        self.ctx._world_item_effects = self.effects
        self.ctx.inventory_frame = None
        items._world_consumable_started(self.ctx)
        self.addCleanup(self.effects.detach)
        self.data = monster_fixture.all_data()
        self.entity, _ = self.fixture.fixture.monster(7)

    def row(self, template, kind):
        return next(row for rows in self.owner.attacks.values() for row in rows
                    if row['template_id'] == template and row['kind'] == kind)

    def inflict(self, template, kind, uid=1):
        row = self.row(template, kind)
        monster = self.data.monsters[template]
        group, slot = self.view.spawner.slot_for(self.entity.uid)
        group.monster, group.spec = monster, replace(group.spec, template_id=template)
        group.active = True
        slot.hp = monster.hp
        self.entity.template_id = template
        self.owner.forget(self.entity.uid)
        self.owner.resources.forget(self.entity.uid)
        self.assertTrue(self.owner.cast(self.entity, monster,
            self.view.entities.get(uid), row, self.fixture.fixture.now))
        return row

    def test_potion_cures_delayed_and_active_paralysis_and_saved_restore_stays_cured(self):
        for elapsed in (10, 21):
            with self.subTest(elapsed=elapsed):
                self.fixture.fixture.now = 100
                self.inflict(28, 'paralysis')
                self.fixture.fixture.now += elapsed
                self.assertEqual(world_magic_status.ai_status(self.magic.effects(1),
                    self.fixture.fixture.now)['blocked'], elapsed >= 20)
                result = self.effects.use(1, 126, self.fixture.fixture.now,
                                          ailments=items.PcAilments())
                self.assertEqual((result.outcome, result.consume_count, result.poison_cured),
                                 ('applied', 1, True))
                self.assertIsNone(self.magic.status(1, 'paralyze', self.fixture.fixture.now))
                restored = world_magic.PlayerMagic(world_magic.load_catalog())
                saved = self.fixture.saved[-1]
                restored.restore(1, saved, 1000, wall=saved['saved_at'])
                self.assertIsNone(restored.status(1, 'paralyze', 1100))
                self.owner.tick(200)
                self.assertIsNone(self.magic.status(1, 'paralyze', 200))

    def test_potion_cures_silence_and_damage_poison_preserving_other_statuses(self):
        for template, kind in ((115, 'silence'), (31, 'poison')):
            with self.subTest(kind=kind):
                self.inflict(template, kind)
                self.magic.apply_status(1, 'slow', 10, 90)
                result = self.effects.use(1, 126, 11, ailments=items.PcAilments())
                self.assertTrue(result.poison_cured)
                self.assertIsNone(self.magic.status(1, 'silence', 11))
                self.assertIsNone(self.magic.state(1).poison)
                self.assertIsNotNone(self.magic.status(1, 'slow', 11))
        self.magic.apply_status(1, 'paralyze', 11, 30, params={'monster_poison': False})
        result = self.effects.use(1, 126, 12, ailments=items.PcAilments())
        self.assertEqual((result.outcome, result.consume_count), ('no_effect', 1))
        self.assertIsNotNone(self.magic.status(1, 'paralyze', 12))

    def test_magic_cure_uses_same_registered_hook_and_real_mp_cost(self):
        from tools.local_original_session.world_pc_response_tests import actor
        source = self.view.combat.pcs[1]
        # PC visibility is populated by the registered Actor DTO via _refresh.
        self.view.update_pc(3, 0, 100, 101, actor_fields=actor(3, 100, 101))
        target_fields = dict(source.status_fields)
        target_fields[1] = 3
        self.view.bind_pc(3, source.profile, target_fields)
        self.view._refresh(1)
        for template, kind in ((28, 'paralysis'), (115, 'silence')):
            with self.subTest(kind=kind):
                self.fixture.fixture.now += 2
                self.inflict(template, kind, 3)
                before = source.mp
                self.ctx._world_magic_cast(1, 8, 3, self.fixture.fixture.now)
                self.assertEqual(source.mp, before - self.magic.spells[8].mp)
                self.assertIsNone(self.magic.status(3, 'paralyze', self.fixture.fixture.now))
                self.assertIsNone(self.magic.status(3, 'silence', self.fixture.fixture.now))
                self.assertIsNone(self.magic.state(3).poison)

    def test_detach_removes_cure_callback(self):
        self.effects.detach()
        self.assertIsNone(self.effects.cure_poison)


class PromotedEnergyBoltTests(unittest.TestCase):
    def test_raw_attr16_uses_source_zero_resistance_branch_and_actual_damage_cost(self):
        fixture = monster_fixture.MonsterSkillsTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        row = fixture.row(36, 'magic')
        self.assertEqual(row['parameters']['element_attr_raw'], 16)
        monster, target = fixture.configure(row, distance=3)
        before = fixture.view.combat.pcs[1].hp
        self.assertTrue(fixture.owner.cast(fixture.entity, monster, target, row, 100))
        event = fixture.owner.events[-1]
        self.assertGreater(event['amount'], 0)
        self.assertEqual(fixture.view.combat.pcs[1].hp, before - event['amount'])
        self.assertEqual(event['mp_before'] - event['mp_after'], 3)
        self.assertFalse(fixture.owner.cast(fixture.entity, monster, target, row, 100.1))
        from tools.local_original_session.world_combat import elemental_defense
        resistant = replace(fixture.view.combat.pcs[1].profile,
            resist_earth=100, resist_fire=100, resist_water=100, resist_wind=100)
        self.assertEqual(elemental_defense(16, resistant), 0)
        raw = json.loads(skills.DATA_PATH.read_text(encoding='utf-8'))
        self.assertNotIn(row['id'], {item['id'] for item in raw['omitted']})


if __name__ == '__main__':
    unittest.main()
