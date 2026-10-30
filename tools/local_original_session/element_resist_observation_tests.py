"""Focused development regressions for producer ownership and wire attribution.

No sockets, original client, user save or formal gameplay PASS.
"""
from dataclasses import replace
from types import MethodType
import unittest
from unittest.mock import Mock

from tools.local_original_session import world_feature_magic as magic_feature
from tools.local_original_session import world_feature_monster_skills as skill_feature
from tools.local_original_session import world_registry
from tools.local_original_session.hunt_bot_element_resist import spell_wire


class ProducerOwnershipTests(unittest.TestCase):
    def fixture(self, *, magic=True, skills=True, chance=100, reverse=False):
        from tools.local_original_session.world_magic_tests import WorldConsumerTests
        from tools.local_original_session.game_data import load_npc_spells
        fixture = WorldConsumerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        ctx, view = fixture.ctx, fixture.view
        modules = tuple(m for enabled, m in ((magic, magic_feature), (skills, skill_feature)) if enabled)
        ctx._world_registry = world_registry.build_registry(modules)
        for module in modules:
            for fn in module.METHODS:
                setattr(ctx, fn.__name__, MethodType(fn, ctx))
        ctx._world_magic_npc_spells = load_npc_spells()
        ctx._world_magic_npc_swing = Mock(wraps=ctx._world_magic_npc_swing)
        if skills:
            ctx._monster_skills_initialize()
            ctx._world_monster_skills_attacks = {
                npc: tuple(dict(r, chance_percent=chance) for r in rows)
                for npc, rows in ctx._world_monster_skills_attacks.items()}
        starts = []
        if magic:
            starts.append(lambda: magic_feature._world_magic_consumers(ctx))
        if skills:
            starts.append(ctx._monster_skills_started)
        for start in reversed(starts) if reverse else starts:
            start()
        entity, monster = fixture.fixture.monster(7)
        view._refresh(1)  # Establish the fixture PC's normal visibility set.
        fixture.state.hp = fixture.state.max_hp = 4000
        fixture.state.profile = replace(fixture.state.profile, mr=0, resist_wind=20)
        view.combat.rng = Mock(randint=Mock(side_effect=lambda low, high: low))
        view.drain(1)
        return fixture, ctx, view, entity, monster

    def attack(self, fixture, view, entity, now=None):
        now = fixture.fixture.now if now is None else now
        view.ai.on_hit(entity.uid, 1, now)
        view.ai._act(entity.uid, now)

    def test_coexisting_producers_cast_and_pay_once_in_both_wrapper_orders(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                f, ctx, view, entity, monster = self.fixture(reverse=reverse)
                self.attack(f, view, entity)
                events = ctx._world_monster_skills_events
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['mp_before'] - events[0]['mp_after'], 18)
                self.assertEqual(f.state.hp, 4000 - events[0]['amount'])
                self.assertEqual(ctx._world_magic_events, [])
                ctx._world_magic_npc_swing.assert_not_called()
                self.assertEqual(sum(int.from_bytes(w[2:4], 'little') == 0x4e31
                                     for w in view.drain(1)), 1)

    def test_refused_skill_uses_physical_without_second_magic_roll_or_cost(self):
        f, ctx, view, entity, monster = self.fixture(chance=0)
        self.attack(f, view, entity)
        self.assertEqual(ctx._world_monster_skills_events, [])
        self.assertEqual(ctx._world_magic_events, [])
        ctx._world_magic_npc_swing.assert_not_called()
        resources = view.extensions['npc_resources']
        self.assertEqual(resources.mana_of(entity.ref, monster.mp), monster.mp)
        self.assertEqual(sum(int.from_bytes(w[2:4], 'little') == 0x4e31
                             for w in view.drain(1)), 1)

    def test_magic_removed_keeps_monster_spell_and_hp_consumer(self):
        f, ctx, view, entity, monster = self.fixture(magic=False)
        self.attack(f, view, entity)
        self.assertIsNone(ctx._world_monster_skills.magic)
        self.assertEqual(len(ctx._world_monster_skills_events), 1)
        self.assertLess(f.state.hp, 4000)
        self.assertEqual(ctx._world_magic_events, [])

    def test_monster_skills_removed_keeps_legacy_spell_and_hp_consumer(self):
        f, ctx, view, entity, monster = self.fixture(skills=False)
        self.attack(f, view, entity)
        self.assertEqual(len(ctx._world_magic_events), 1)
        self.assertEqual(ctx._world_magic_events[0]['mp_before'] -
                         ctx._world_magic_events[0]['mp_after'], 18)
        self.assertLess(f.state.hp, 4000)

    def test_stopping_monster_skills_restores_legacy_producer(self):
        f, ctx, view, entity, monster = self.fixture()
        ctx._monster_skills_stopped()
        self.attack(f, view, entity)
        self.assertEqual(ctx._world_monster_skills_events, [])
        self.assertEqual(len(ctx._world_magic_events), 1)


class WireAttributionTests(unittest.TestCase):
    def row(self, ordinal, opcode, fields, at=101):
        return dict(ordinal=ordinal, opcode=opcode, fields=fields, at=at)

    def test_event_requires_new_ordered_target_swing_hp_and_effect(self):
        event = dict(npc_uid=7, hp_after=90, at=100, effect_id=10)
        swing = self.row(11, '0x4E31', {'2': 7, '3': 1})
        hp = self.row(12, '0x4E38', {'1': 1, '10': 90})
        effect = self.row(13, '0x4ED8', {'1': 1, '2': 10})
        self.assertIsNotNone(spell_wire(event, [swing, hp, effect], 10, 1))
        self.assertIsNone(spell_wire(event, [swing, hp, effect], 13, 1))
        self.assertIsNone(spell_wire(event, [dict(swing, at=99), hp, effect], 10, 1))
        self.assertIsNone(spell_wire(event, [hp, swing, effect], 10, 1))
        self.assertIsNone(spell_wire(event, [swing, hp], 10, 1))
        other = self.row(12, '0x4E31', {'2': 8, '3': 1})
        self.assertIsNone(spell_wire(event, [swing, other, hp, effect], 10, 1))
        self.assertIsNone(spell_wire(event, [dict(swing, fields={'2': 7, '3': 2}), hp, effect], 10, 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
