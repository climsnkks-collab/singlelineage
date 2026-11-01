"""Elemental resistance development checks; no sockets or original game.

Synthetic spell parameters exercise arithmetic and the actual HP consumer.
Source-backed NPC producer checks also use development fixtures. These are
not formal login/packet/gameplay PASS or native display evidence.
"""
from dataclasses import replace
import random
from types import MethodType, SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from tools.local_original_session import inventory, world_combat as combat
from tools.local_original_session import world_core_stats as core, world_stats as stats
from tools.local_original_session import world_weight
from tools.local_original_session.equipment_store import EquipmentState
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_ai_tests import status_fields, status_hp


ELEMENTS = ('earth', 'fire', 'water', 'wind')


def resistance(value):
    return tuple(getattr(value, 'resist_' + element) for element in ELEMENTS)


def parameters(attr=2):
    return dict(damage_value=100, damage_dice=1, damage_dice_count=0,
                element_attr_raw=attr, skill_level=7)


def rng(value=100):
    return Mock(randint=Mock(return_value=value))


def bag(rows):
    return inventory.build_kit_frame([
        {1: uid, 2: template, 3: 0, 4: 1, 5: 0, 7: 71, 9: 0, 10: 0,
         13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0, 24: False, 25: 0,
         26: False} for uid, template in rows])


class ElementResistanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_m1()
        cls.items = cls.data.items

    def setUp(self):
        self.base = stats.CharacterStats(20, 1, stats.Attributes(18, 12, 16, 10, 12, 8))
        self.pc = combat.PcProfile(20, 1, 0, 18, 12)

    def test_catalog_four_elements_ring_and_belt_add_once_then_unequip(self):
        for index, (ring, belt) in enumerate(((500, 3936), (498, 3934),
                                             (499, 3935), (501, 3937))):
            with self.subTest(element=ELEMENTS[index]):
                equipped = tuple(stats.EquippedItem(self.items[key]) for key in (ring, belt))
                expected = tuple(20 if axis == index else 0 for axis in range(4))
                self.assertEqual(resistance(stats.calculate_stats(self.base, equipped)), expected)
                one = stats.calculate_stats(self.base, equipped[:1])
                self.assertEqual(resistance(one)[index], 10)
                self.assertEqual(resistance(stats.calculate_stats(self.base)), (0, 0, 0, 0))

    def test_effective_clamp_is_after_sum_and_preserves_negative_resistance(self):
        value = stats.calculate_stats(self.base, buffs=(
            stats.StatModifiers(resist_earth=200, resist_fire=-200,
                                resist_water=500, resist_wind=-500),
            stats.StatModifiers(resist_earth=-100, resist_fire=100)))
        self.assertEqual(resistance(value), (100, -100, 127, -128))
        boundary = stats.calculate_stats(self.base, buffs=(stats.StatModifiers(
            resist_earth=127, resist_fire=-128, resist_water=128, resist_wind=-129),))
        self.assertEqual(resistance(boundary), (127, -128, 127, -128))

    def test_pc_and_companion_project_only_their_selected_equipment(self):
        owner_frame = bag(((101, 498), (102, 501)))  # fire selected, wind in bag
        mage_frame = bag(((201, 499), (202, 500)))  # water selected, earth in bag
        owner_equipment = EquipmentState(1, 101, 498, 0, 0,
            ((self.items[498].slot_key, 101),))
        mage_equipment = EquipmentState(2, 201, 499, 0, 0,
            ((self.items[499].slot_key, 201),))
        info = {3: 1, 5: 0, 10: 20, 11: 18, 12: 12, 13: 16, 14: 10, 15: 12, 16: 8}
        world = NS(data=self.data)
        ctx = NS(world=world, _world=world, item_policies={},
            realm=NS(store=NS(select=lambda name: (1, info))),
            _world_progress_for=lambda uid: None,
            _item_equipment_effect=NS(store=NS(peek=lambda uid: (owner_equipment, owner_frame))),
            fold_sync_hooks=lambda name, value, *args, **kwargs: value)
        ctx._world_stats_for = MethodType(core._world_stats_for, ctx)
        position = NS(uid=1, name='OwnedFixture')
        owner = core._world_pc_profile(ctx, object(), position)
        weights = world_weight.load_weight_catalog()

        def mage_profile():
            calculated, worn = stats.companion_stats(NS(level=20),
                (8, 7, 16, 18, 8, 18), mage_frame, mage_equipment, self.items, weights)
            return combat.companion_profile(calculated, worn, 0)

        mage = mage_profile()
        self.assertEqual(resistance(owner), (0, 10, 0, 0))
        self.assertEqual(resistance(mage), (0, 0, 10, 0))
        self.assertEqual((owner.mr, mage.mr), (20, 35))
        # Recompute through the same producers after each character changes gear.
        owner_equipment = replace(owner_equipment, slots=((self.items[501].slot_key, 102),))
        mage_equipment = replace(mage_equipment, slots=((self.items[500].slot_key, 202),))
        self.assertEqual(resistance(core._world_pc_profile(ctx, object(), position)), (0, 0, 0, 10))
        self.assertEqual(resistance(mage_profile()), (10, 0, 0, 0))

    def test_independent_element_multiplier_positive_negative_and_effective_bounds(self):
        for resist, expected in ((0, 109), (50, 54), (100, 0), (-50, 163),
                                 (127, 0), (-128, 248)):
            with self.subTest(resistance=resist):
                target = replace(self.pc, resist_fire=resist)
                self.assertEqual(combat.magic_damage(parameters(), 12, rng(),
                    target=target, npc=True), expected)

    def test_each_attack_element_uses_only_its_matching_resistance(self):
        target = replace(self.pc, resist_earth=10, resist_fire=20,
                         resist_water=30, resist_wind=40)
        for attr, expected in ((1, 98), (2, 87), (4, 76), (8, 65),
                               (0, 109), (3, 109), (16, 109)):
            with self.subTest(attr=attr):
                self.assertEqual(combat.magic_damage(parameters(attr), 12, rng(),
                    target=target, npc=True), expected)
        fire_only = replace(self.pc, resist_fire=100)
        self.assertEqual(combat.magic_damage(parameters(4), 12, rng(),
            target=fire_only, npc=True), 109)

    def test_retained_player_spell_parameters_cover_each_element_without_rewriting_attr(self):
        from tools.local_original_session.world_magic import PlayerMagic, load_catalog
        spells = PlayerMagic(load_catalog()).spells
        # Existing source-backed player attacks; this does not make them NPC attacks.
        for element, key, attr in (('earth', 15, 1), ('fire', 14, 2),
                                   ('water', 5, 4), ('wind', 6, 8)):
            with self.subTest(element=element, key=key):
                spell = spells[key]
                params = spell.raw['formula']['parameters']
                self.assertEqual(params['element_attr_raw'], attr)
                amounts = [combat.magic_damage(params, 12, random.Random(7),
                    target=replace(self.pc, **{'resist_' + element: value}))
                    for value in (-50, 0, 50, 100)]
                self.assertTrue(all(left > right for left, right in zip(amounts, amounts[1:])), amounts)
                other = 'water' if element != 'water' else 'fire'
                self.assertEqual(combat.magic_damage(params, 12, random.Random(7),
                    target=replace(self.pc, **{'resist_' + other: 100})), amounts[1])

    def test_mr_is_independent_and_npc_probability_boundary_is_inclusive(self):
        for resist, unhalved, halved in ((0, 109, 54), (50, 54, 27), (100, 0, 0), (-50, 163, 81)):
            target = replace(self.pc, resist_fire=resist, mr=50)
            self.assertEqual(combat.magic_damage(parameters(), 12, rng(51),
                target=target, npc=True), unhalved)
            self.assertEqual(combat.magic_damage(parameters(), 12, rng(50),
                target=target, npc=True), halved)
        target = replace(self.pc, resist_fire=50, mr=100)
        # Defender projection supplies MR even if the legacy argument differs.
        self.assertEqual(combat.magic_damage(parameters(), 12, rng(),
            target=target, mr=0, npc=True), 27)
        self.assertEqual(combat.magic_damage(parameters(), 12, rng(), target=target), 27)

    def test_npc_has_no_pc_critical_and_element_multiplies_sp_bonus_too(self):
        spell = {**parameters(), 'skill_level': 1}
        self.assertEqual(combat.magic_damage(spell, 12, rng(1), target=self.pc, npc=True), 109)
        self.assertEqual(combat.magic_damage(spell, 12, rng(1), target=self.pc), 163)
        target = replace(self.pc, resist_fire=50)
        self.assertEqual(combat.magic_damage(parameters(), 12, rng(),
            target=target, npc=True, item_sp=4), 68)
        # attr0/weak_attr0 is neutral, not an elemental weakness match.
        self.assertEqual(combat.magic_damage(parameters(0), 12, rng(), weak_attr=0), 109)

    def test_ordinary_npc_melee_is_unchanged_by_resistance_and_mr(self):
        defended = replace(self.pc, mr=200, resist_earth=127, resist_fire=127,
                           resist_water=127, resist_wind=127)
        monster = next(iter(self.data.monsters.values()))
        for seed in range(12):
            self.assertEqual(combat.npc_hits_pc(monster, self.pc, random.Random(seed)),
                             combat.npc_hits_pc(monster, defended, random.Random(seed)))

    def test_explicit_development_magic_attack_consumes_real_hp_and_emits_actual_status(self):
        monster = next(iter(self.data.monsters.values()))
        magic = combat.NpcMagicAttack(parameters(), 12)
        for resist, damage in ((0, 109), (50, 54), (100, 0), (-50, 163), (127, 0)):
            with self.subTest(resistance=resist):
                world = combat.WorldCombat(self.data, rng())
                state = world.bind_pc(1, replace(self.pc, resist_fire=resist), status_fields(500))
                swing, wire = world.npc_magic_swing(monster, 1, magic)
                self.assertEqual((swing.landed, swing.damage), (True, damage))
                self.assertEqual(state.hp, 500 - damage)
                self.assertEqual(world.hp_of(1), state.hp)
                self.assertFalse(state.dead)
                if damage:
                    self.assertEqual(status_hp(wire), state.hp)
                else:
                    self.assertIsNone(wire)
        world = combat.WorldCombat(self.data, rng())
        state = world.bind_pc(1, self.pc, status_fields(9))
        swing, wire = world.npc_magic_swing(monster, 1, magic)
        self.assertEqual((swing.damage, state.hp, state.dead, status_hp(wire)), (109, 0, True, 0))

    def test_explicit_magic_hp_consumer_remains_available_with_optional_magic_wrappers(self):
        from tools.local_original_session.world_magic_tests import WorldConsumerTests
        from tools.local_original_session.world_feature_magic import _world_magic_consumers
        fixture = WorldConsumerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        view, state = fixture.view, fixture.state
        _world_magic_consumers(fixture.ctx)
        monster = next(iter(self.data.monsters.values()))
        state.profile = replace(state.profile, mr=0, resist_fire=50)
        before = state.hp
        view.combat.rng = rng()
        swing, wire = view.combat.npc_magic_swing(monster, 1,
            combat.NpcMagicAttack(parameters(), 12))
        self.assertEqual((swing.damage, state.hp, status_hp(wire)), (54, before - 54, before - 54))

    def test_sourced_npc_selection_four_elements_cost_reuse_drain_and_physical_fallback(self):
        from tools.local_original_session.game_data import load_npc_spells
        from tools.local_original_session.hunt_bot_spawn_audit import all_data
        from tools.local_original_session.world_magic_tests import WorldConsumerTests
        from tools.local_original_session.world_feature_magic import _world_magic_consumers
        fixture = WorldConsumerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        view, state = fixture.view, fixture.state
        fixture.fixture.data = all_data()
        view.replace_data(fixture.fixture.data)
        fixture.ctx._world_magic_npc_spells = load_npc_spells()
        _world_magic_consumers(fixture.ctx)
        for template, element in ((180, 'earth'), (274, 'fire'), (7, 'wind'), (63, 'water')):
            with self.subTest(template=template, element=element):
                target, monster = fixture.fixture.monster(template)
                state.hp = state.max_hp = 4000
                state.profile = replace(self.pc, **{'resist_' + element: 20})
                view.combat.rng = Mock(randint=Mock(side_effect=lambda low, high: low))
                group, slot = view.spawner.slot_for(target.uid)
                slot.hp -= 10
                view.npc_attack(target, monster, 1, fixture.fixture.now)
                event = fixture.ctx._world_magic_events[-1]
                self.assertEqual(event['outcome'], 'npc_magic')
                self.assertEqual(event['mp_before']-event['mp_after'],
                    fixture.ctx._world_magic_npc_spells[monster.l1j_npcid][0].mp_cost)
                self.assertGreater(event['trace']['elemental_defense'], 0)
                self.assertEqual(event['hp_before']-state.hp, event['rolled_damage'])
                self.assertEqual(event['amount'], event['rolled_damage'])
                if element == 'water':
                    self.assertEqual(event['drain_restored'], min(10, event['amount']))
                    self.assertEqual(slot.hp, monster.hp - 10 + event['drain_restored'])
                row = fixture.magic.npc_statuses[target.uid]
                before = len(fixture.ctx._world_magic_events)
                # Reuse and exhausted mana each fall through to core physical;
                # neither spends MP nor manufactures an additional spell event.
                self.assertIsNone(fixture.ctx._world_magic_npc_swing(
                    monster, 1, target.ref, fixture.fixture.now))
                resources = view.extensions['npc_resources']
                resources.spend_mana(target.ref, monster.mp, resources.mana_of(target.ref, monster.mp))
                self.assertIsNone(fixture.ctx._world_magic_npc_swing(
                    monster, 1, target.ref, row['next_cast_at'] + 1))
                self.assertEqual(len(fixture.ctx._world_magic_events), before)

    def test_npc_leverage_and_element_narrowing_precede_mr(self):
        trace = {}
        target = replace(self.pc, resist_fire=50, mr=100)
        amount = combat.magic_damage(parameters(), 12, rng(100), target=target,
            npc=True, leverage=5, trace=trace)
        self.assertEqual((trace['base_damage'], trace['damage_before_mr'], amount), (100, 27, 13))

    def test_removing_optional_magic_restores_sourced_npc_basic_physical_swing(self):
        from tools.local_original_session.game_data import load_npc_spells
        from tools.local_original_session.world_magic_tests import WorldConsumerTests
        from tools.local_original_session.world_feature_magic import _world_magic_consumers
        fixture = WorldConsumerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.ctx._world_magic_npc_spells = load_npc_spells()
        _world_magic_consumers(fixture.ctx)
        fixture.ctx._world_magic_stopped()
        self.assertIs(fixture.view.combat.npc_swing.__func__, combat.WorldCombat.npc_swing)
        target, monster = fixture.fixture.monster(7)
        fixture.view.combat.rng = random.Random(29)
        expected = combat.npc_hits_pc(monster, fixture.state.profile, random.Random(29))
        before = fixture.state.hp
        fixture.view.npc_attack(target, monster, 1, fixture.fixture.now)
        self.assertEqual(fixture.state.hp, max(0, before - expected.damage))
        self.assertEqual(fixture.ctx._world_magic_events, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
