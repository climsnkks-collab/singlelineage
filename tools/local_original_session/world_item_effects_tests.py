"""Pure consumable behavior checks; no broker/game/server/save access."""
from array import array
from dataclasses import replace
from types import SimpleNamespace
from pathlib import Path
import tempfile
import random
import unittest

from tools.local_original_session import game_data, world_combat as wc
from tools.local_original_session.world_item_effects import (
    PcAilments, WorldItemEffects, ConsumableState, ConsumableStore,
    consumable_snapshot, consumable_restore, consumable_mutation,
    identified_projection, load_effects, random_destination, buff_icon_frame)
from tools.local_original_session.world_maps import MapDestination
from tools.local_original_session.world_terrain import FLAG_COUNT, WorldTerrain
from tools.local_world_protocol import model as world

PC = 65537


class BuffIconFrameTests(unittest.TestCase):
    def child_fields(self, wire):
        from tools.local_entry_server import protobuf as pb
        with pb.parse_message(wire[4:-2]) as outer:
            with pb.parse_message(bytes(outer.occurrences(2)[0].value)) as child:
                return {f.number: f.value for f in child.fields}

    def test_exact_catalog_tooltip_and_explicit_distinct_chat_callbacks(self):
        # CommonSpell selected source rows, no icon/catalog numeric substitution.
        for catalog, key, reference in ((223, 481, 849), (224, 486, 851),
                (231, 484, 3154), (232, 5399, 3988), (225, 486, 851),
                (1062, 486, 851), (229, 552, 856), (2, 485, 853)):
            values = self.child_fields(buff_icon_frame(catalog, key, 10))
            self.assertEqual(values[7], reference)
            self.assertNotIn(8, values)
            self.assertNotIn(9, values)
        values = self.child_fields(buff_icon_frame(99999, 12, 10,
            description_ref=100, start_chat_ref=200, end_chat_ref=300))
        self.assertEqual((values[7], values[8], values[9]), (100, 200, 300))
        self.assertEqual(self.child_fields(buff_icon_frame(99999, 12, 0, remove=True,
            start_chat_ref=200, end_chat_ref=300)), {4: 12})

    def test_zero_or_absent_resource_reference_does_not_invent_description(self):
        for catalog in (1, 146, 99999):
            self.assertNotIn(7, self.child_fields(buff_icon_frame(catalog, 12, 10)))

    def test_same_supplied_key_add_refresh_and_remove_keep_remaining_time_formatter(self):
        from tools.local_entry_server import protobuf as pb
        # Synthetic encoder inputs, not an item/catalog-to-image mapping.
        for remaining, remove, duration, operation in (
                (60.1, False, 61, 1), (120.25, False, 121, 1),
                (0, True, 0, 3), (-1, True, 0, 3)):
            with self.subTest(remaining=remaining, remove=remove):
                wire = buff_icon_frame(7, 0xffffffff, remaining, remove=remove)
                self.assertEqual(int.from_bytes(wire[:2], 'little'), len(wire))
                self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x4e91)
                self.assertEqual(wire[-2:], b'\0\0')
                with pb.parse_message(wire[4:-2]) as outer:
                    self.assertEqual([(f.number, f.wire_type) for f in outer.fields],
                                     [(1, 0), (2, 2)])
                    self.assertEqual(outer.occurrences(1)[0].value, operation)
                    with pb.parse_message(bytes(outer.occurrences(2)[0].value)) as child:
                        self.assertEqual({f.number: f.value for f in child.fields},
                                         {4: 0xffffffff} if remove else
                                         {1: 7, 2: 1, 3: duration, 4: 0xffffffff, 7: 685})


class MeanRoll(random.Random):
    def gauss(self, mu, sigma):
        return 0.0


class SmallTerrain:
    def __init__(self, cells):
        self.cells = cells
        self.maps_seen = set()

    def bounds(self, map_id):
        self.maps_seen.add(map_id)
        return (8, 8, 12, 12)

    def can_stand(self, map_id, x, y):
        self.maps_seen.add(map_id)
        return self.cells.get((x, y))


class ItemEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = game_data.load_m1()

    def setUp(self):
        self.combat = wc.WorldCombat(self.data, MeanRoll(5))
        self.fields = {1: PC, 2: 1, 4: 13, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15,
                       10: 1, 11: 200, 12: 3, 13: 10, 14: -10, 15: 1793000000,
                       16: 200, 17: 7, 18: -123, 20: 9}
        self.pc = self.combat.bind_pc(PC, wc.PcProfile(1, 1, 0, 13, 13), self.fields)
        self.effects = WorldItemEffects(self.combat, SmallTerrain({(11, 10): True}))

    def use(self, template, **kwargs):
        return self.effects.use(PC, template, 100.0, **kwargs)

    def test_explicit_classic_mapping_and_reference_ids_separated(self):
        definitions = load_effects()
        self.assertEqual(set(definitions), {14, 15, 130, 17, 296, 495, 126, 162, 23,
                                           492, 16, 248, 279, 86, 1408, 15410, 15430})
        self.assertEqual(definitions[15].reference_id, 40011)
        self.assertEqual(definitions[130].heal_hp, 75)
        for template in (40010, 40011, 40100, 806, 10014):
            result = self.use(template)
            self.assertEqual((result.outcome, result.consume_count), ('unsupported', 0))

    def test_three_healing_amounts_full_status_and_clamp(self):
        for template, endpoints in ((14, (6, 27)), (15, (26, 68)), (130, (44, 107))):
            with self.subTest(template=template):
                self.pc.hp = 1
                expected_rng = random.Random()
                expected_rng.setstate(self.effects.rng.getstate())
                amount = expected_rng.randint(*endpoints)
                result = self.use(template)
                self.assertEqual((result.healed_hp, self.pc.hp, result.consume_count), (amount, 1 + amount, 1))
                effect, frame = result.frames  # 4ED8 use effect, then SC_STATUS
                from tools.local_original_session.world_status_frames import effect_frame
                self.assertEqual(effect, effect_frame(PC, {14: 189, 15: 194, 130: 197}[template]))
                self.assertEqual(int.from_bytes(frame[2:4], 'little'), 0x4E38)
                fields = world.decode_payload(0x4E38, frame[4:-2])
                self.assertEqual(fields[10], 1 + amount)
                self.assertEqual(fields[12], 3)
                self.assertEqual(fields[18], -123)
        self.pc.hp = 199
        self.assertEqual(self.use(130).healed_hp, 1)
        self.assertEqual(self.pc.hp, 200)
        full = self.use(130)
        self.assertEqual((full.outcome, full.healed_hp, full.consume_count), ('no_effect', 0, 1))

    def test_healing_uses_official_range_and_shared_rng(self):
        self.effects.rng.seed(73)
        expected = random.Random(73).randint(26, 68)
        self.assertEqual(self.use(15).healed_hp, expected)

    def test_ent_fruit_heals_and_class_specific_bravery_uses_real_combat(self):
        self.pc.hp = 1
        self.assertTrue(44 <= self.use(279).healed_hp <= 107)
        for template, character_class, duration in ((86, 2, 480), (1408, 0, 600)):
            self.pc.buffs.clear()
            self.pc.profile = replace(self.pc.profile, character_class=character_class)
            result = self.use(template)
            self.assertEqual(result.buff_expires_at, 100 + duration)
            self.assertEqual(self.combat.speed_factor(PC, 100), .745)
            self.assertEqual(self.combat.speed_factor(PC, 100 + duration), 1)
            self.pc.profile = replace(self.pc.profile, character_class=3)
            self.assertEqual(self.use(template).outcome, 'no_effect')

    def test_incomplete_rows_are_separate_and_do_not_claim_consumption(self):
        rows = load_effects(owner='unsupported')
        self.assertEqual(set(rows), {806, 15400, 15457})
        self.assertEqual(set(load_effects(owner='consumables')),
                         {9, 10, 37, 43, 55, 59, 60, 82, 83, 362, 22, 24, 297, 417, 418})
        for template in rows:
            result = self.use(template)
            self.assertEqual((result.outcome, result.consume_count), ('unsupported', 0))

    def test_foods_restore_fullness_cap_and_do_not_spend_when_full(self):
        for template, nutrition in ((9, 5), (10, 10), (37, 5), (43, 8), (55, 5),
                                    (59, 8), (60, 20), (82, 5), (83, 8), (362, 3)):
            self.effects.state(PC).fullness = 0
            result = self.use(template)
            self.assertEqual((result.outcome, result.consume_count), ('applied', 1))
            self.assertEqual(self.effects.state(PC).fullness, nutrition)
        self.effects.state(PC).fullness = 224
        self.use(10)
        self.assertEqual(self.effects.state(PC).fullness, 225)
        self.assertEqual((self.use(10).reason, self.use(10).consume_count), ('FOOD_ALREADY_FULL', 0))

    def test_wisdom_mage_only_real_deadline_and_breath_refresh(self):
        self.assertEqual((self.use(297).reason, self.use(297).consume_count), ('WISDOM_MAGE_REQUIRED', 0))
        self.pc.profile = replace(self.pc.profile, character_class=3)
        self.assertEqual(self.use(297).outcome, 'applied')
        self.assertEqual(self.effects.spell_power(PC, 399.99), 2)
        self.assertEqual(self.effects.spell_power(PC, 400), 0)
        self.use(417)
        self.use(418)
        self.assertEqual(self.effects.state(PC).breath_until, 1900)
        self.assertTrue(self.effects.can_breathe(PC, 1899))
        self.assertFalse(self.effects.can_breathe(PC, 1900))

    def test_identify_and_equipped_curse_only_use_current_owned_uids(self):
        result = self.use(22, owned_uids=(7, 8), target_uid=99)
        self.assertEqual((result.reason, result.consume_count), ('OWNED_ITEM_TARGET_REQUIRED', 0))
        self.use(22, owned_uids=(7, 8), target_uid=7)
        self.assertEqual(self.effects.state(PC).identified, {7})
        self.use(22, owned_uids=(7, 8))
        self.assertEqual(self.effects.state(PC).identified, {7, 8})
        self.effects.state(PC).curses = {7, 8, 99}
        self.assertFalse(self.effects.can_unequip(PC, 7))
        self.use(24, owned_uids=(7, 8), equipped_uids=(7,))
        self.assertTrue(self.effects.can_unequip(PC, 7))
        self.assertEqual(self.effects.state(PC).curses, {8, 99})
        self.assertEqual(self.use(24, owned_uids=(7, 8)).consume_count, 0)

    def test_durable_snapshot_offline_expiry_preserves_opaque_authorities(self):
        state = ConsumableState(20, 400, 1900, {7}, {8})
        row = consumable_snapshot(PC, state, 100, wall=1000)
        restored = consumable_restore(row, 50, wall=1200)
        self.assertEqual((restored.fullness, restored.wisdom_until, restored.breath_until), (20, 150, 1650))
        self.assertEqual((restored.identified, restored.curses), ({7}, {8}))
        expired = consumable_restore(row, 50, wall=3000)
        self.assertEqual((expired.wisdom_until, expired.breath_until), (50, 50))
        for change in ({'fullness': 226}, {'curses': [{}]}, {'wisdom_remaining': float('nan')}):
            with self.assertRaises(ValueError):
                consumable_restore(dict(row, **change), 50, wall=1200)

    def test_saved_potion_schema_rejects_unknown_nonfinite_and_duplicate_speed_kind(self):
        row = consumable_snapshot(PC, ConsumableState(), 100, wall=1000)
        for potions in ({'999': 10}, {'17': float('nan')}, {'17': -1},
                        {'17': 10, '495': 20}, {'296': 10, '86': 20}):
            with self.subTest(potions=potions), self.assertRaisesRegex(ValueError, 'CONSUMABLE_SAVE_POTIONS'):
                consumable_restore(dict(row, potion_remaining=potions), 100, wall=1000)

    def test_blind_has_existing_sight_consumer_and_cures_clear_actual_poison(self):
        from tools.local_original_session import world_magic, world_magic_status
        engine = self.effects.magic = world_magic.PlayerMagic(world_magic.load_catalog())
        self.effects.magic_save = lambda uid, now: saved.append(engine.snapshot(uid, now))
        saved = []
        engine.apply_status(PC, 'darkness', 100, 300)
        result = self.use(16)
        state = engine.state(PC)
        self.assertEqual((result.outcome, result.consume_count), ('applied', 1))
        self.assertNotIn('darkness', state.effects)
        self.assertEqual(world_magic_status.ai_status(state.effects, 115)['sight'], 1)
        self.assertIsNone(world_magic_status.ai_status(state.effects, 116)['sight'])
        self.assertIn('blind', saved[-1]['statuses']['effects'])
        state.poison = dict(until=150, next_tick=103, tick_seconds=3, damage=5, source_uid=123)
        self.assertTrue(engine.is_poisoned(PC, 100))
        cured = self.use(248, ailments=PcAilments())
        self.assertTrue(cured.poison_cured)
        self.assertFalse(engine.is_poisoned(PC, 100))
        self.assertNotIn('poison', saved[-1]['statuses'])

    def test_speed_stacks_caps_class_and_expiry_via_combat(self):
        green = self.use(17)
        self.assertEqual((green.buff_kind, green.buff_expires_at), ('haste', 400.0))
        from tools.local_original_session.world_status_frames import effect_frame
        self.assertEqual(green.frames[0], effect_frame(PC, 191))  # L1J useGreenPotion sound
        self.assertEqual(int.from_bytes(green.frames[1][2:4], 'little'), 0x4E5B)
        self.assertEqual(self.use(17).buff_expires_at, 700.0)
        brave = self.use(296)
        self.assertEqual(brave.buff_kind, 'brave')
        self.assertAlmostEqual(self.combat.speed_factor(PC, 100.0), 0.745 ** 2)
        self.assertEqual(self.use(495).buff_expires_at, 1900.0)
        self.assertIsNone(self.combat.expire_buff(PC, 'haste', 1899.0))
        self.assertIsNotNone(self.combat.expire_buff(PC, 'haste', 1900.0))
        self.assertIsNotNone(self.combat.expire_buff(PC, 'brave', 1900.0))
        self.assertEqual(self.combat.speed_factor(PC, 1900.0), 1.0)
        self.pc.profile = replace(self.pc.profile, character_class=2)
        no_effect = self.use(296)
        self.assertEqual((no_effect.outcome, no_effect.consume_count, no_effect.frames), ('no_effect', 1, ()))

    def test_speed_icon_mapping_keeps_cost_deadlines_and_unmapped_templates(self):
        for template, character_class, duration, mapping in (
                (17, 1, 300, (223, 481)), (495, 1, 1800, (226, 481)),
                (296, 1, 300, (224, 486)), (86, 2, 480, (225, 486)),
                (1408, 0, 600, (1062, 486))):
            with self.subTest(template=template):
                self.pc.buffs.clear()
                self.pc.profile = replace(self.pc.profile, character_class=character_class)
                result = self.use(template)
                self.assertEqual((result.outcome, result.consume_count), ('applied', 1))
                self.assertEqual(result.buff_expires_at - 100, duration)
                if mapping is None:
                    requirement, = result.requirements
                    self.assertEqual((requirement.kind, requirement.opcode), ('speed_buff_icon', 0x4E91))
                    self.assertIn('UNSUPPLIED', requirement.unresolved)
                else:
                    self.assertEqual(result.requirements, ())
                    self.assertEqual(result.frames[-1], buff_icon_frame(*mapping, duration))
                expected = ([0x4ED8] if self.effects.definitions[template].use_gfx is not None else [])
                self.assertEqual([int.from_bytes(f[2:4], 'little') for f in result.frames],
                                 expected + [0x4E5B] + ([] if mapping is None else [0x4E91]))

        self.pc.buffs.clear()
        self.pc.profile = replace(self.pc.profile, character_class=1)
        self.use(17)
        refreshed = self.effects.use(PC, 17, 125.25)
        self.assertEqual(refreshed.buff_expires_at - 125.25, 574.75)
        self.assertEqual(refreshed.frames[-1], buff_icon_frame(223, 481, 574.75))
        capped = self.effects.use(PC, 495, 150)
        self.assertEqual(capped.buff_expires_at - 150, 1800)
        self.assertEqual(capped.frames[-1], buff_icon_frame(226, 481, 1800))

    def test_unbound_and_dead_pc_do_not_change_or_consume(self):
        ailments = PcAilments('damage_poison')
        for dead in (False, True):
            uid = PC if dead else PC + 1
            self.pc.dead = dead
            for template in load_effects():
                result = self.effects.use(uid, template, 100.0, ailments=ailments,
                    position=MapDestination(0, 10, 10, 0))
                self.assertEqual((result.outcome, result.consume_count), ('refused', 0))
        self.assertEqual((self.pc.hp, self.pc.buffs, ailments.poison), (1, {}, 'damage_poison'))

    def test_cure_requires_explicit_state_and_only_clears_poison(self):
        self.assertEqual(self.use(126).reason, 'POISON_STATE_UNSUPPLIED')
        ailments = PcAilments('damage_poison')
        result = self.use(126, ailments=ailments)
        self.assertTrue(result.poison_cured)
        self.assertIsNone(ailments.poison)
        from tools.local_original_session.world_status_frames import effect_frame
        self.assertEqual((result.consume_count, result.frames, self.pc.hp), (1, (effect_frame(PC, 192),), 1))
        self.assertIsNone(result.requirements[0].opcode)
        self.assertEqual(self.use(126, ailments=ailments).outcome, 'no_effect')

    def test_return_uses_existing_town_and_is_only_a_proposal(self):
        from tools.local_original_session.world_item_effects import teleport_effect_frame
        position = MapDestination(2, 10, 10, 0)
        result = self.use(162, position=position)
        town = self.data.town
        self.assertEqual(result.destination, MapDestination(town.map_id, town.respawn_x, town.respawn_y, 5))
        self.assertEqual(result.outcome, 'destination_proposed')
        self.assertEqual(result.frames, (teleport_effect_frame(PC),))
        self.assertEqual([(r.kind, r.opcode) for r in result.requirements],
                         [('teleport', None), ('map_notify', 0x4E95)])
        self.assertEqual(position, MapDestination(2, 10, 10, 0))
        same_map = self.use(162, position=MapDestination(0, 10, 10, 0))
        self.assertEqual(len(same_map.requirements), 1)

    def test_random_teleport_stays_on_map_and_ignores_unknown_blocked_current(self):
        from tools.local_original_session.world_item_effects import teleport_effect_frame
        terrain = SmallTerrain({(10, 10): True, (11, 10): True, (12, 10): False, (9, 10): None})
        self.effects.terrain = terrain
        result = self.use(23, position=MapDestination(2, 10, 10, 0))
        self.assertEqual(result.destination, MapDestination(2, 11, 10, 5))
        self.assertEqual(terrain.maps_seen, {2})
        self.assertEqual(result.frames, (teleport_effect_frame(PC),))
        self.assertEqual([(r.kind, r.opcode) for r in result.requirements], [('teleport', None)])
        self.assertEqual(self.use(23).consume_count, 0)

    def test_random_teleport_no_terrain_or_no_valid_tile_does_not_consume(self):
        position = MapDestination(0, 10, 10, 0)
        self.effects.terrain = None
        refused = self.use(23, position=position)
        self.assertEqual((refused.reason, refused.frames), ('TERRAIN_UNSUPPLIED', ()))
        self.effects.terrain = SmallTerrain({(10, 10): True})
        result = self.use(23, position=position)
        self.assertEqual((result.reason, result.consume_count, result.destination),
                         ('NO_KNOWN_STANDABLE_DESTINATION', 0, None))
        self.assertEqual(result.frames, ())

    def test_sparse_destination_reservoir_fallback_after_rejection_misses(self):
        class MissFirst(random.Random):
            attempts = 0

            def randint(self, a, b):
                self.attempts += 1
                return a  # (8,8) is unknown; all 32 initial attempts miss.

        rng = MissFirst(7)
        terrain = SmallTerrain({(11, 10): True})
        result = random_destination(MapDestination(2, 10, 10, 0), terrain, rng)
        self.assertEqual(rng.attempts, 64)
        self.assertEqual(result, MapDestination(2, 11, 10, 5))

    def test_random_destination_uses_real_classic_can_stand_and_radius(self):
        terrain = WorldTerrain({2: {(0, 0): array('H', [0]) * FLAG_COUNT}})
        position = MapDestination(2, 30, 30, 0)
        for seed in range(5):
            result = random_destination(position, terrain, random.Random(seed), radius=2)
            self.assertEqual(result.map_id, 2)
            self.assertTrue(terrain.can_stand(result.map_id, result.x, result.y))
            self.assertLessEqual(max(abs(result.x-30), abs(result.y-30)), 2)
            self.assertNotEqual((result.x, result.y), (30, 30))


class BlueRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tools.local_original_session.world_visibility import WorldView
        self.now = 100.0
        self.view = WorldView.create(clock=lambda: self.now, rng=random.Random(7))
        self.fields = {1: PC, 2: 1, 4: 13, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15,
                       10: 200, 11: 200, 12: 0, 13: 100, 14: -10, 15: 1793000000,
                       16: 200, 17: 7, 18: -123, 20: 9}
        self.profile = wc.PcProfile(1, 3, 0, 13, 13, wis=15)
        self.view.bind_pc(PC, self.profile, self.fields)
        self.pc = self.view.combat.pcs[PC]
        self.effects = WorldItemEffects(self.view.combat)
        self.effects.attach(self.view)
        self.effects.project_fullness(PC)  # fixture's local nutrition starts at0

    async def advance(self, count, *, activity=None):
        for _ in range(count):
            if activity is not None:
                self.view.combat.note_activity(PC, activity)
            self.now += 1
            await self.view.runtime.tick_once(self.now)

    async def test_blue_uses_natural_threshold_then_bonus_and_full_status(self):
        result = self.effects.use(PC, 492, self.now)
        self.assertEqual((result.outcome, result.consume_count, result.buff_kind), ('applied', 1, None))
        await self.advance(15)
        self.assertEqual(self.pc.mp, 0)
        await self.advance(1)
        self.assertEqual(self.pc.mp, 12)  # natural WIS15 +2, blue +10
        frames = [f for f in self.view.drain(PC) if int.from_bytes(f[2:4], 'little') == 0x4e38]
        self.assertEqual(world.decode_payload(0x4e38, frames[-1][4:-2])[12], 12)
        self.effects.tick(self.now)  # repeated observer must not repeat recovery
        self.assertEqual(self.pc.mp, 12)
        self.pc.status_fields[12] = 99
        await self.advance(16)
        self.assertEqual(self.pc.mp, 100)

    async def test_movement_slowdown_and_expiry_use_same_natural_clock(self):
        self.effects.use(PC, 492, self.now)
        await self.advance(31, activity=self.view.combat.regen.move_points)
        self.assertEqual(self.pc.mp, 0)
        await self.advance(1, activity=self.view.combat.regen.move_points)
        self.assertEqual(self.pc.mp, 12)
        self.effects.active[PC]['mana_regen'].until = self.now + 16
        await self.advance(16)
        self.assertEqual(self.pc.mp, 14)  # expires at boundary: natural only
        self.assertNotIn(PC, self.effects.active)

    async def test_stacking_cap_rebind_and_detach_do_not_carry_bonus(self):
        for _ in range(3):
            self.effects.use(PC, 492, self.now)
        self.assertEqual(self.effects.active[PC]['mana_regen'].until, self.now + 1200)
        self.view.combat.forget_pc(PC)
        self.view.bind_pc(PC, self.profile, self.fields)
        await self.advance(16)
        self.assertEqual(self.view.combat.pcs[PC].mp, 2)
        self.assertNotIn(PC, self.effects.active)
        self.effects.use(PC, 492, self.now)
        self.effects.detach()
        self.assertNotIn(self.effects.tick, self.view.runtime._hooks)
        self.assertEqual(self.effects.active, {})
        await self.advance(16)
        self.assertEqual(self.view.combat.pcs[PC].mp, 4)

    async def test_food_bonus_uses_existing_hp_threshold_and_no_duplicate_tick(self):
        self.pc.hp = 1
        self.effects.tick(self.now)
        self.effects.use(PC, 10, self.now)
        threshold = self.view.combat.regen.hp_threshold(self.pc.profile.level)
        count = (threshold + self.view.combat.regen.idle_points - 1) // self.view.combat.regen.idle_points
        await self.advance(count - 1)
        self.assertEqual(self.pc.hp, 1)
        await self.advance(1)
        natural = self.view.combat.regen.hp_amount(self.pc.profile.con)
        self.assertEqual(self.pc.hp, 1 + natural + 1)
        self.effects.tick(self.now)
        self.assertEqual(self.pc.hp, 1 + natural + 1)
        self.now = 401
        self.effects.tick(self.now)
        self.assertEqual(self.effects.state(PC).fullness, 9)

    async def test_hunger_full_status_proposal_commit_restore_and_live_depletion(self):
        from tools.local_original_session.world_item_effects import _world_consumable_pc_bound
        self.effects.state(PC).fullness = 215
        self.effects.project_fullness(PC)
        self.assertEqual(self.pc.status_fields[16], 95)
        proposed = self.effects.use(PC, 10, self.now, remember_icon=False)
        self.assertEqual(self.pc.status_fields[16], 95)  # before durable commit
        hunger = world.decode_payload(0x4e38, proposed.frames[-1][4:-2])
        self.assertEqual(hunger[16], 100)
        self.assertEqual((hunger[10], hunger[12], hunger[18]), (200, 0, -123))
        self.effects.project_fullness(PC)  # adapter's postcommit projection
        self.assertEqual(self.pc.status_fields[16], 100)
        self.effects.tick(self.now)
        self.view.drain(PC)
        self.now += 300
        self.effects.tick(self.now)
        depleted = world.decode_payload(0x4e38, self.view.drain(PC)[-1][4:-2])
        self.assertEqual((self.effects.state(PC).fullness, depleted[16]), (224, 99))
        saved = consumable_snapshot(PC, self.effects.state(PC), self.now, wall=1000)
        self.effects.states[PC] = consumable_restore(saved, self.now, wall=1100)
        self.pc.status_fields[16] = 0
        ctx = SimpleNamespace(world=self.view, _world_item_effects=self.effects)
        _world_consumable_pc_bound(ctx, PC)
        restored = world.decode_payload(0x4e38, self.view.drain(PC)[-1][4:-2])
        self.assertEqual(restored[16], 99)

    async def test_blue_and_wisdom_add_update_use_actual_deadlines_without_broadcast(self):
        blue = self.effects.use(PC, 492, self.now)
        self.assertEqual(blue.frames[-1], buff_icon_frame(232, 5399, 600))
        self.now = 125.25
        blue = self.effects.use(PC, 492, self.now)
        self.assertEqual(blue.frames[-1], buff_icon_frame(232, 5399, 1174.75))
        wisdom = self.effects.use(PC, 297, self.now)
        self.assertEqual(wisdom.frames[-1], buff_icon_frame(231, 484, 300))
        # use proposes frames; only the existing owner send lane publishes them.
        self.assertEqual(self.view.outbox, {})

    async def test_wafer_blood_shared_key_keeps_latest_identity_and_brave_deadline(self):
        self.pc.profile = replace(self.profile, character_class=1)
        self.effects.use(PC, 296, self.now)
        self.pc.profile = replace(self.profile, character_class=2)
        self.now = 120
        wafer = self.effects.use(PC, 86, self.now)
        # Existing same-kind accumulation: 280 remaining plus480, no new timer.
        self.assertEqual(wafer.buff_expires_at, 880)
        self.assertEqual(wafer.frames[-1], buff_icon_frame(225, 486, 760))
        self.pc.profile = replace(self.profile, character_class=0)
        blood = self.effects.use(PC, 1408, self.now)
        self.assertEqual(blood.buff_expires_at, 1480)
        self.assertEqual(set(self.effects.icons[PC]), {486})
        self.assertEqual(self.effects.icons[PC][486], (self.pc, 1408))
        self.now = 880
        self.effects.tick(self.now)
        self.assertEqual(self.view.drain(PC), [])
        self.now = 1480
        self.effects.tick(self.now)
        self.assertEqual(self.view.drain(PC), [buff_icon_frame(1062, 486, 0, remove=True)])

    async def test_eva_shared_breath_deadline_refresh_expiry_and_restore(self):
        self.effects.use(PC, 417, self.now)
        self.now = 150
        scale = self.effects.use(PC, 418, self.now)
        until = self.effects.state(PC).breath_until
        self.assertEqual(scale.frames[-1], buff_icon_frame(229, 552, until-self.now))
        self.assertEqual(set(self.effects.icons[PC]), {552})
        saved = consumable_snapshot(PC, self.effects.state(PC), self.now, wall=1000)
        self.effects.icons.clear()
        self.effects.states[PC] = consumable_restore(saved, self.now, wall=1100)
        self.assertEqual(self.effects.resend_icons(PC, self.now),
                         (buff_icon_frame(229, 552, until-self.now-100),))
        self.now = until-100
        self.effects.tick(self.now)
        self.assertEqual(self.view.drain(PC), [buff_icon_frame(229, 552, 0, remove=True)])
        self.effects.tick(self.now)
        self.assertEqual(self.view.drain(PC), [])

    async def test_all_four_icons_expire_once_through_owner_outbox(self):
        self.pc.profile = replace(self.profile, character_class=1)
        self.effects.use(PC, 296, self.now)
        self.pc.profile = self.profile
        for template in (17, 492, 297):
            self.effects.use(PC, template, self.now)
        self.view._queue(PC + 1, b'other-owner-frame')
        self.now = 400
        await self.view.runtime.tick_once(self.now)
        icons = [wire for wire in self.view.drain(PC) if int.from_bytes(wire[2:4], 'little') == 0x4e91]
        self.assertCountEqual(icons, [buff_icon_frame(0, key, 0, remove=True)
                                      for key in (481, 486, 484)])
        self.assertEqual(self.view.drain(PC + 1), [b'other-owner-frame'])
        self.now = 700
        await self.view.runtime.tick_once(self.now)
        icons = [wire for wire in self.view.drain(PC) if int.from_bytes(wire[2:4], 'little') == 0x4e91]
        self.assertEqual(icons, [buff_icon_frame(232, 5399, 0, remove=True)])
        self.effects.tick(self.now)
        self.assertEqual(self.view.drain(PC), [])

    async def test_death_removes_published_icons_and_clears_effects_once(self):
        from tools.local_original_session.world_item_effects import _world_consumable_died
        for template in (17, 492, 297):
            self.effects.use(PC, template, self.now)
        self.pc.dead = True
        ctx = SimpleNamespace(_world_item_effects=self.effects, world=self.view)
        _world_consumable_died(ctx, PC)
        self.assertCountEqual(self.view.drain(PC), [buff_icon_frame(0, key, 0, remove=True)
                                                   for key in (481, 5399, 484)])
        self.assertEqual(self.effects.state(PC).wisdom_until, 0)
        self.assertNotIn(PC, self.effects.active)
        _world_consumable_died(ctx, PC)
        self.assertEqual(self.view.drain(PC), [])

    async def test_reconnect_sends_only_restored_authority_with_remaining_seconds(self):
        from tools.local_original_session.world_item_effects import (
            _world_consumable_left, _world_consumable_enter)
        from unittest.mock import AsyncMock
        for template in (17, 492, 297):
            self.effects.use(PC, template, self.now)
        saved = consumable_snapshot(PC, self.effects.state(PC), self.now, wall=1000)
        self.view.leave_pc(PC)
        writer = object()
        ctx = SimpleNamespace(world=self.view, _world_item_effects=self.effects,
            _world_pcs={id(writer): (writer, PC)}, inventory_frame=None, send=AsyncMock())
        _world_consumable_left(ctx)
        self.now = 250.25
        self.view.bind_pc(PC, self.profile, self.fields)
        self.effects.states[PC] = consumable_restore(saved, self.now, wall=1100.5)
        self.view.drain(PC)
        row, game, lock = {}, object(), object()
        await _world_consumable_enter(ctx, writer, row, game, lock)
        ctx.send.assert_not_awaited()
        from tools.local_original_session import inventory
        from tools.local_original_session.world_handlers import _starter_fields
        ctx.inventory_frame = inventory.build_kit_frame([_starter_fields()])
        await _world_consumable_enter(ctx, writer, row, game, lock)
        expected = (self.effects.use_effect_frame(PC, 17),
                    wc.speed_frame(PC, self.view.combat.speed_factor(PC, self.now)),
                    buff_icon_frame(223, 481, 300),
                    self.effects.use_effect_frame(PC, 492),
                    buff_icon_frame(232, 5399, 600), buff_icon_frame(231, 484, 199.5))
        from tools.local_original_session.world_bridge import WORLD_SEND_CHUNK
        self.assertEqual(tuple(call.args[2] for call in ctx.send.await_args_list),
                         (expected[:WORLD_SEND_CHUNK], expected[WORLD_SEND_CHUNK:]))
        for call in ctx.send.await_args_list:
            self.assertEqual(call.args[:2], (writer, row))
            self.assertEqual(call.kwargs, dict(game=True, operation_lock=lock,
                                               world_operation=call.args[2]))
        self.assertEqual(self.view.combat.pcs[PC].buffs['haste'][0], self.now + 300)
        self.assertEqual(self.effects.active[PC]['mana_regen'].until, self.now + 600)
        self.assertEqual(set(self.effects.icons[PC]), {481, 5399, 484})

    async def test_knight_logout_freezes_remaining_and_reconnect_restores_expiry_and_regen(self):
        from tools.local_original_session.world_item_effects import _world_consumable_before_leave
        self.pc.profile = replace(self.profile, character_class=1)
        for template in (495, 296, 492):
            self.effects.use(PC, template, self.now)
        self.now += 42.25
        rows = {}
        self.effects.store = SimpleNamespace(save=lambda uid, state, now:
            rows.update({uid: consumable_snapshot(uid, state, now, wall=1000)}))
        ctx = SimpleNamespace(world=self.view, _world_item_effects=self.effects)
        await _world_consumable_before_leave(ctx, object(), PC)
        saved = rows[PC]
        self.assertEqual(saved['potion_remaining'], {'296': 257.75, '492': 557.75, '495': 1757.75})
        self.view.leave_pc(PC)
        self.effects.states[PC] = consumable_restore(saved, self.now, wall=100000)
        # The same-process paused state must not run down while unselected.
        # A freshly loaded server may also wait this long before the first bind.
        self.now += 10000
        self.assertEqual(consumable_snapshot(PC, self.effects.state(PC), self.now)['potion_remaining'],
                         saved['potion_remaining'])
        self.view.bind_pc(PC, replace(self.profile, character_class=1), self.fields)
        self.pc = self.view.combat.pcs[PC]
        wires = self.effects.restore_potions(PC, self.now)
        self.assertEqual(wires, (wc.speed_frame(PC, self.view.combat.speed_factor(PC, self.now)),))
        self.assertEqual(set(self.view.buffs), {(PC, 'haste'), (PC, 'brave')})
        self.assertCountEqual(self.effects.resend_icons(PC, self.now), (
            buff_icon_frame(226, 481, 1757.75), buff_icon_frame(224, 486, 257.75),
            buff_icon_frame(232, 5399, 557.75)))
        deadlines = dict(self.pc.buffs)
        self.now += 1
        self.assertEqual(self.effects.restore_potions(PC, self.now), ())
        self.assertEqual(self.pc.buffs, deadlines)  # inventory delivery cannot refresh
        await self.advance(16)
        self.assertEqual(self.pc.mp, 12)  # restored blue uses the existing natural consumer
        self.now = deadlines['brave'][0]
        await self.view.runtime.tick_once(self.now)
        self.assertNotIn('brave', self.pc.buffs)
        self.assertIn(buff_icon_frame(224, 486, 0, remove=True), self.view.drain(PC))
        self.now = deadlines['haste'][0]
        await self.view.runtime.tick_once(self.now)
        self.assertFalse(self.pc.buffs)
        self.assertNotIn(PC, self.effects.active)
        self.view.leave_pc(PC)
        self.assertEqual(self.effects.state(PC).potions, {})
        self.view.bind_pc(PC, replace(self.profile, character_class=1), self.fields)
        self.assertEqual(self.effects.restore_potions(PC, self.now), ())
        self.assertEqual(self.effects.resend_icons(PC, self.now), ())

    async def test_first_entry_reads_store_without_overwriting_later_paused_state(self):
        self.pc.profile = replace(self.profile, character_class=1)
        saved = consumable_snapshot(PC,
            ConsumableState(potions={17: 200}, potions_paused=True), self.now, wall=1000)
        self.effects.store = SimpleNamespace(rows={PC: saved})
        self.effects.states[PC] = ConsumableState()  # Observed reconnect default.
        self.effects.restore_potions(PC, self.now)
        self.assertIn('haste', self.pc.buffs)
        self.now += 25
        self.view.leave_pc(PC)  # In-memory remaining survives an interrupted save.
        remaining = self.effects.state(PC).potions[17]
        self.assertAlmostEqual(remaining, 175)
        self.view.bind_pc(PC, replace(self.profile, character_class=1), self.fields)
        self.effects.restore_potions(PC, self.now)
        self.assertAlmostEqual(self.view.combat.pcs[PC].buffs['haste'][0] - self.now, 175)

    async def test_death_does_not_restore_saved_speed_or_blue(self):
        from tools.local_original_session.world_item_effects import _world_consumable_died
        for template in (17, 492):
            self.effects.use(PC, template, self.now)
        self.pc.dead = True
        _world_consumable_died(SimpleNamespace(world=self.view, _world_item_effects=self.effects), PC)
        self.view.leave_pc(PC)
        self.view.bind_pc(PC, self.profile, self.fields)
        self.assertEqual(self.effects.restore_potions(PC, self.now), ())
        self.assertEqual(self.effects.resend_icons(PC, self.now), ())

    async def test_legacy_row_and_wrong_class_do_not_create_speed_or_hud(self):
        row = consumable_snapshot(PC, ConsumableState(), self.now, wall=1000)
        row.pop('potion_remaining')
        self.effects.states[PC] = consumable_restore(row, self.now, wall=2000)
        self.assertEqual(self.effects.restore_potions(PC, self.now), ())
        self.view.leave_pc(PC)
        self.view.bind_pc(PC, self.profile, self.fields)  # mage cannot restore knight bravery
        row['potion_remaining'] = {'296': 100}
        self.effects.states[PC] = consumable_restore(row, self.now, wall=3000)
        self.assertEqual(self.effects.restore_potions(PC, self.now), ())
        self.assertFalse(self.view.combat.pcs[PC].buffs)
        self.assertEqual(self.effects.resend_icons(PC, self.now), ())

    async def test_proposed_wisdom_does_not_publish_or_remember_before_commit(self):
        previous = self.effects.state(PC)
        proposed = replace(previous)
        self.effects.states[PC] = proposed
        result = self.effects.use(PC, 297, self.now, remember_icon=False)
        self.assertEqual(result.frames[-1], buff_icon_frame(231, 484, 300))
        self.assertEqual(self.effects.icons, {})
        self.assertEqual(self.view.outbox, {})
        self.effects.states[PC] = previous  # failed proposal leaves no HUD cleanup state
        self.effects.tick(self.now + 301)
        self.assertFalse(any(int.from_bytes(wire[2:4], 'little') == 0x4e91
                             for wire in self.view.drain(PC)))

    async def test_existing_kit_speed_lane_sends_icon_only_to_its_owner(self):
        import asyncio
        from unittest.mock import AsyncMock
        from tools.local_original_session.world_feature_items import _world_buff_locked
        writer = object()
        lock = asyncio.Lock()
        row = dict(writer=writer, operation_lock=lock)
        ctx = SimpleNamespace(_world=self.view, _world_item_effects=self.effects,
            _world_bound=lambda current: current is writer,
            _world_pcs={id(writer): (writer, PC)}, _world_events={}, _world_send=AsyncMock())
        async with lock:
            result = await _world_buff_locked(ctx, writer, row, b'quantity',
                                              self.view.data.items[17].buff, 17)
        self.assertTrue(result['buff_applied'])
        self.assertEqual(ctx._world_send.await_args.args[:2], (writer, row))
        frames = ctx._world_send.await_args.args[2]
        self.assertEqual(frames[-1], buff_icon_frame(223, 481, 300))
        self.assertEqual(self.view.outbox, {})
        self.now = 400
        await self.view.runtime.tick_once(self.now)
        self.assertIn(buff_icon_frame(0, 481, 0, remove=True), self.view.drain(PC))

    async def test_companion_use_keeps_sound_speed_and_never_emits_hud(self):
        from tools.local_original_session.world_companion_inventory import CompanionInventory
        queued = []
        entity = object()
        view = SimpleNamespace(entities=SimpleNamespace(resolve=lambda ref: entity),
            _watchers=lambda current: (PC, PC + 1),
            _queue=lambda uid, wire: queued.append((uid, wire)), _announce=lambda: None)
        entity = SimpleNamespace(uid=PC + 10)
        owner = SimpleNamespace(ctx=SimpleNamespace(world=view),
            item_effects={**load_effects(), **load_effects(owner='consumables')},
            speed_factor=lambda uid, now: .745)
        rt = SimpleNamespace(ref=object(), character_id=7)
        for template in (17, 495, 296, 492, 297):
            CompanionInventory._publish_use(owner, rt, template, self.now,
                                             speed=template in (17, 495, 296))
        self.assertTrue(queued)
        self.assertEqual({int.from_bytes(wire[2:4], 'little') for _, wire in queued},
                         {0x4ed8, 0x4e5b})


class ConsumableStoreTests(unittest.TestCase):
    def setUp(self):
        from tools.local_original_session import inventory
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        fields = {1: 7, 2: 22, 3: 0, 4: 2, 5: 0, 7: 0, 9: 0, 10: 0,
                  13: 0, 14: 0, 16: 0, 17: 0, 18: b'+3 canonical', 22: 0,
                  24: False, 25: 0, 26: False}
        self.before = inventory.build_kit_frame([fields])
        self.previous = ConsumableState()
        self.proposed = ConsumableState(10, 400, 1900, {7}, {8})
        self.after, self.frames = consumable_mutation(self.before, 7, 'identify',
            self.previous, self.proposed, {7})
        self.inventory = SimpleNamespace(profile=Path(self.temp.name) / 'characters.json',
                                         restore=lambda uid: self.current)
        self.current, self.replacements, self.fail = self.before, 0, False
        def replace_kit(uid, before, after):
            if self.current != before:
                raise ValueError('TEST_STALE_KIT')
            self.current = after
            self.replacements += 1
            if self.fail:
                raise OSError('TEST_AFTER_REPLACE_FAILURE')
            return True
        self.inventory.replace_kit = replace_kit

    def test_commit_and_fresh_store_restore_canonical_name_and_state(self):
        from tools.local_original_session import inventory
        store = ConsumableStore(self.inventory)
        store.commit(PC, self.before, self.after, self.proposed, 100)
        self.assertEqual((self.current, self.replacements), (self.after, 1))
        self.assertFalse(store.intent.exists())
        fresh = ConsumableStore(self.inventory)
        state = consumable_restore(fresh.rows[PC], 200)
        self.assertEqual((state.fullness, state.identified, state.curses), (10, {7}, {8}))
        self.assertEqual(dict(inventory.validate_kit_frame(self.after)[0].raw_fields)[18], b'+3 canonical')
        label, = identified_projection(self.after, state)
        self.assertIn('[확인됨]'.encode('utf-8'), label)
        self.assertEqual(len(self.frames), 1)

    def test_saved_potion_remaining_roundtrips_fresh_store_without_offline_loss(self):
        store = ConsumableStore(self.inventory)
        state = ConsumableState(potions={495: 1899.5, 296: 250.25, 492: 700})
        store.save(PC, state, 100)
        fresh = ConsumableStore(self.inventory)
        restored = consumable_restore(fresh.rows[PC], 50000, wall=10**12)
        self.assertTrue(restored.potions_paused)
        self.assertEqual(restored.potions, {495: 1799.5, 296: 150.25, 492: 600})
        store.save(PC, ConsumableState(potions={17: 99, 492: 100}), 100)
        expired = ConsumableStore(self.inventory)
        self.assertEqual(expired.rows[PC]['potion_remaining'], {})

    def test_replace_then_raise_recovers_once_without_consuming_again(self):
        store = ConsumableStore(self.inventory)
        self.fail = True
        with self.assertRaisesRegex(OSError, 'TEST_AFTER_REPLACE_FAILURE'):
            store.commit(PC, self.before, self.after, self.proposed, 100)
        self.assertTrue(store.intent.exists())
        self.assertEqual(self.replacements, 1)
        recovered = ConsumableStore(self.inventory)
        self.assertFalse(recovered.intent.exists())
        self.assertEqual(self.replacements, 1)
        self.assertEqual(recovered.rows[PC]['fullness'], 10)

    def test_curse_names_scroll_cost_and_legacy_state_recover_together(self):
        from tools.local_original_session import inventory, world_enchant_inventory as enchant
        from tools.local_original_session.game_data import load_m1
        defs = load_m1().items
        rows = [dict(inventory.validate_kit_frame(self.before)[0].raw_fields)]
        rows[0].update({2: 24, 18: b''})
        cursed = dict(rows[0])
        cursed.update({1: 8, 2: 40, 4: 1,
                       18: enchant.enchanted_name(defs[40], -2, grade=2)})
        rows.append(cursed)
        self.current = before = inventory.build_kit_frame(rows)
        previous, proposed = ConsumableState(curses={8}), ConsumableState()
        after, wires = consumable_mutation(before, 7, 'remove_curse', previous, proposed,
                                          {8}, definitions=defs)
        saved = inventory.validate_kit_frame(after)
        self.assertEqual(dict(saved[0].raw_fields)[4], 1)
        self.assertEqual((saved[1].bless, enchant.enchant_level(saved[1], defs[40])), (1, -2))
        self.assertEqual(previous.curses, {8})
        self.assertEqual(len(wires), 2)
        store = ConsumableStore(self.inventory)
        self.fail = True
        with self.assertRaises(OSError):
            store.commit(PC, before, after, proposed, 100)
        self.assertTrue(store.intent.exists())
        recovered = ConsumableStore(self.inventory)
        self.assertEqual((self.current, self.replacements), (after, 1))
        self.assertEqual(recovered.rows[PC]['curses'], [])
        self.assertFalse(recovered.intent.exists())

    def test_conflicting_startup_preserves_pending_intent_and_current(self):
        store = ConsumableStore(self.inventory)
        self.fail = True
        with self.assertRaises(OSError):
            store.commit(PC, self.before, self.after, self.proposed, 100)
        self.current = b'foreign existing save'
        with self.assertRaisesRegex(ValueError, 'CONSUMABLE_INVENTORY_CONFLICT'):
            ConsumableStore(self.inventory)
        self.assertTrue(store.intent.exists())
        self.assertEqual((self.current, self.replacements), (b'foreign existing save', 1))


class TowerItemUseTests(unittest.IsolatedAsyncioTestCase):
    """LOCAL rules and actual 0960 adapter; synthetic fixtures, no game/ports."""

    def setUp(self):
        from tools.local_original_session import inventory
        from tools.local_original_session.world_handlers import _starter_fields
        self.inventory = inventory
        self.combat = wc.WorldCombat(game_data.load_m1(), MeanRoll(5))
        self.combat.bind_pc(PC, wc.PcProfile(1, 1, 0, 13, 13),
                           {1: PC, 10: 1, 11: 200, 12: 3, 16: 200})
        self.effects = WorldItemEffects(self.combat)
        self.writer, self.game = object(), SimpleNamespace()
        self.position = SimpleNamespace(map_id=101, word0=32816, word1=32778)
        self.costs, self.moves, self.sent = [], [], []
        self.allowed, self.standable = True, True

        async def dispatch(fn):
            return await fn()

        async def send(writer, row, frames, lock):
            self.sent.extend(frames)

        def consume(writer, uid):
            self.costs.append(uid)
            rows = [dict(v.raw_fields) for v in inventory.validate_kit_frame(self.ctx.inventory_frame)]
            rows[0][4] -= 1
            self.ctx.inventory_frame = inventory.build_kit_frame(rows)
            return b'cost'

        def relocate(writer, row, game, destination):
            self.moves.append(destination)
            self.position.map_id = destination.map_id
            self.position.word0, self.position.word1 = destination.x, destination.y
            return (b'relocation',)

        self.ctx = SimpleNamespace(
            _inventory_kit_policy=inventory.KIT_POLICY, _world_item_effects=self.effects,
            _world_pcs={id(self.writer): (self.writer, PC)}, _world_events={},
            _world_item_errors=[], _world_map_exp=2,
            _world_bound=lambda writer: writer is self.writer,
            _world_ready=lambda *args: True,
            realm=SimpleNamespace(registry=SimpleNamespace(resolve=lambda writer: self.game),
                service=lambda writer: SimpleNamespace(snapshot=lambda: self.position),
                serves_map=lambda map_id: self.allowed),
            _world=SimpleNamespace(combat=self.combat,
                runtime=SimpleNamespace(clock=lambda: 100, dispatch_now=dispatch),
                terrain=SimpleNamespace(can_stand=lambda *args: self.standable),
                broadcast_pc_effects=lambda *args: None, drain=lambda uid: ()),
            fold_sync_hooks=lambda name, result, position: result,
            _world_consume_kit=consume, _world_relocate_locked=relocate, _world_send=send)
        self.fields = _starter_fields()
        self.fields.update({1: 65590, 2: 15430, 4: 2, 7: 2879})
        self.set_item(15430)

    def set_item(self, template):
        self.fields[2] = template
        self.ctx.inventory_frame = self.inventory.build_kit_frame([self.fields])

    def frame(self, uid=65590, params=None):
        from tools.local_entry_server import protobuf as pb
        from tools.local_original_session.world_bookmark import varint
        if params is None:
            params = b''.join(varint(n, v) for n, v in {1: 1, 15: 0, 16: 0}.items())
        return SimpleNamespace(payload=varint(1, uid) + pb.encode_bytes(2, params))

    async def use(self, **kwargs):
        from tools.local_original_session.world_feature_items import _world_use_item
        return await _world_use_item(self.ctx, self.writer, {}, self.game,
                                     self.frame(**kwargs), object())

    def test_charm_inclusive_entry_bounds_and_refused_adjacent_cells(self):
        for x, y in ((32816, 32778), (32821, 32783)):
            result = self.effects.use(PC, 15430, 100, position=MapDestination(101, x, y, 5))
            self.assertEqual((result.outcome, result.consume_count), ('destination_proposed', 0))
            self.assertEqual(result.destination, MapDestination(111, 32669, 32814, 5))
        for m, x, y in ((100, 32816, 32778), (102, 32816, 32778),
                        (101, 32815, 32778), (101, 32822, 32778),
                        (101, 32816, 32777), (101, 32816, 32784)):
            result = self.effects.use(PC, 15430, 100, position=MapDestination(m, x, y, 5))
            self.assertEqual((result.reason, result.consume_count), ('TOWER_CHARM_ENTRY_AREA_REQUIRED', 0))

    def test_scroll_escapable_departure_and_unknown_policy(self):
        for map_id in (0, 4, 101, 110, 111, 120):
            result = self.effects.use(PC, 15410, 100, position=MapDestination(map_id, 1, 1, 5))
            self.assertEqual((result.outcome, result.consume_count), ('destination_proposed', 1))
        for map_id, reason in ((70, 'TOWER_DEPARTURE_NOT_ESCAPABLE'),
                               (9999, 'TOWER_DEPARTURE_POLICY_UNKNOWN')):
            result = self.effects.use(PC, 15410, 100, position=MapDestination(map_id, 1, 1, 5))
            self.assertEqual((result.reason, result.consume_count), (reason, 0))

    async def test_reusable_charm_never_debits_and_same_uid_can_be_used_again(self):
        from tools.local_original_session.world_item_effects import teleport_effect_frame
        before = self.ctx.inventory_frame
        for _ in range(2):
            # Explicit unit-fixture reset, not a claim of a real return journey.
            self.position.map_id, self.position.word0, self.position.word1 = 101, 32816, 32778
            self.assertTrue(await self.use())
            self.assertEqual(self.ctx.inventory_frame, before)
        self.assertEqual((len(self.moves), self.costs, self.sent),
                         (2, [], [teleport_effect_frame(PC), b'relocation'] * 2))

    async def test_scroll_debits_one_and_relocates_through_existing_owner(self):
        from tools.local_original_session.world_item_effects import teleport_effect_frame
        self.set_item(15410)
        self.position.map_id = 4
        self.assertTrue(await self.use())
        self.assertEqual(self.costs, [65590])
        item = self.inventory.validate_kit_frame(self.ctx.inventory_frame)[0]
        self.assertEqual(dict(item.raw_fields)[4], 1)
        self.assertEqual(self.moves, [MapDestination(111, 32669, 32814, 5)])
        self.assertEqual(self.sent, [b'cost', teleport_effect_frame(PC), b'relocation'])

    async def test_refused_area_and_unavailable_destination_keep_inventory(self):
        before = self.ctx.inventory_frame
        for map_id, allowed, standable in ((4, True, True), (101, False, True), (101, True, False)):
            self.position.map_id, self.allowed, self.standable = map_id, allowed, standable
            self.assertTrue(await self.use())
            self.assertEqual(self.ctx.inventory_frame, before)
        self.assertEqual((self.costs, self.moves, self.sent), ([], [], []))

    async def test_scroll_departure_refusal_and_stale_uid_do_not_debit(self):
        self.set_item(15410)
        self.position.map_id = 70
        before = self.ctx.inventory_frame
        self.assertTrue(await self.use())
        self.assertFalse(await self.use(uid=9999))
        self.assertEqual((self.ctx.inventory_frame, self.costs, self.moves), (before, [], []))

    async def test_sealed_charm_stays_unsupported_and_keeps_owned_inventory(self):
        from tools.local_original_session.world_item_effects import _world_consumable_unsupported
        self.set_item(15457)
        self.ctx.selected_session = lambda writer: self.game
        before = self.ctx.inventory_frame
        self.assertTrue(await _world_consumable_unsupported(
            self.ctx, self.writer, {}, self.game, self.frame(), object()))
        self.assertEqual(self.ctx._world_item_errors[-1], 'TOWER_SEAL_RELEASE_RESULT_UNSUPPLIED')
        self.assertEqual((self.ctx.inventory_frame, self.costs, self.moves), (before, [], []))


if __name__ == '__main__':
    unittest.main()
