"""Companion part1/part2 server rules: class data, walking, stances, owner death,
death EXP, bridge signals/models, ATS scope (development checks, no sockets)."""
from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.local_original_session import world_companion_integration_tests as fixtures


class ClassDefinitionTests(unittest.TestCase):
    def test_mage_row_and_weapon_timing_from_client_data(self):
        from tools.local_original_session.world_companion_classes import load_definitions
        defs = load_definitions()
        self.assertIn(3, defs.class_ids)
        self.assertEqual(defs.classes[3].sprite(0), 734)
        self.assertEqual(defs.classes[3].sprite(1), 1186)
        self.assertEqual(defs.action_ms(3, 0, 'staff'), (667, 1167))
        self.assertEqual(defs.action_ms(3, 1, 'dagger'), (667, 958))
        self.assertEqual(defs.action_ms(3, 0, None), (667, 917))
        self.assertEqual(defs.action_ms(3, 0, 'blunt'), defs.action_ms(3, 0, 'axe'))
        self.assertEqual(defs.max_active_per_owner, 1)
        self.assertEqual(defs.return_scroll_templates, (162,))

    def test_old_saved_rows_load_with_class_and_summoned_defaults(self):
        from dataclasses import asdict
        from tools.local_original_session.world_companion import CompanionRecord, record_from_row
        row = asdict(CompanionRecord(2, 1, 'a', hp=5, max_hp=5))
        row.pop('class_id')
        row.pop('summoned')
        record = record_from_row(row)
        self.assertEqual((record.class_id, record.summoned), (3, True))
        with self.assertRaisesRegex(ValueError, 'COMPANION_INVALID_RECORD'):
            record_from_row(dict(row, unknown=1))

    def test_roster_accepts_only_configured_classes(self):
        from tools.local_original_session.world_companion import CompanionRecord, _validate_roster
        roster = {1: dict(account_id='a', class_id=1), 2: dict(account_id='a', class_id=2)}
        elf = CompanionRecord(2, 1, 'a', hp=5, max_hp=5, class_id=2)
        with self.assertRaises(ValueError):
            _validate_roster(elf, roster)
        _validate_roster(elf, roster, frozenset((2, 3)))


class WalkingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.actor = self.fixture.view, self.fixture.actor
        self.view.companions.set_commands(2, movement_mode='FOLLOW', combat_mode='PASSIVE')
        self.view.companion_ai.follow_distance = 1
        self.entity = self.view.entities.resolve(self.actor.ref)

    def test_steps_keep_due_time_grid_despite_tick_lateness(self):
        ai, walk = self.view.companion_ai, 16 / 24
        self.view.update_pc(1, 0, 130, 100)
        now = 20.0
        self.actor.next_move_at = now
        dues = []
        for late in (0.0, 0.12, 0.05, 0.14, 0.0):
            due = self.actor.next_move_at
            ai.step(self.actor.ref, due + late)
            dues.append(self.actor.next_move_at)
        steps = [round(b - a, 6) for a, b in zip(dues, dues[1:])]
        self.assertEqual(steps, [round(walk, 6)] * 4)  # no drift from lateness

    def test_long_stall_rebases_without_burst(self):
        ai = self.view.companion_ai
        self.view.update_pc(1, 0, 130, 100)
        self.actor.next_move_at = 20.0
        ai.step(self.actor.ref, 25.0)
        self.assertAlmostEqual(self.actor.next_move_at, 25.0 + 16 / 24)

    def test_following_schedules_exact_due_time_and_requests_wake(self):
        ai, wakes = self.view.companion_ai, []
        ai.wake = wakes.append
        self.view.update_pc(1, 0, 130, 100)
        self.actor.next_move_at = 20.0
        ai.step(self.actor.ref, 20.0)
        self.assertAlmostEqual(self.actor.handle.at, min(20.0 + 0.15, 20.0 + 16 / 24))
        self.assertIn(self.actor.handle.at, wakes)

    def test_owner_move_starts_following_immediately(self):
        before = (self.entity.x, self.entity.y)
        self.view.update_pc(1, 0, 106, 100)
        self.actor.next_move_at = 0
        self.view.drain(1)
        self.view.companion_ai.owner_moved(1, self.fixture.now)
        self.assertNotEqual((self.entity.x, self.entity.y), before)

    def test_owner_move_before_due_schedules_at_due(self):
        self.view.update_pc(1, 0, 106, 100)
        self.actor.next_move_at = self.fixture.now + 0.4
        self.view.companion_ai.owner_moved(1, self.fixture.now)
        self.assertAlmostEqual(self.actor.handle.at, self.fixture.now + 0.4)

    def test_intervals_follow_weapon_and_speed_effects(self):
        from tools.local_original_session.world_companion_classes import load_definitions
        from tools.local_original_session.world_feature_companion import _companion_intervals
        bags = SimpleNamespace(speed_factor=lambda uid, now: 0.745)
        ctx = SimpleNamespace(_companion_defs=load_definitions(), world=self.view,
                              _companion_rows={2: dict(gender=0)}, _companion_inventory=bags)
        self.view.companion_looks[2]['weapon_type'] = 'staff'
        walk, attack = _companion_intervals(ctx, self.actor)
        self.assertAlmostEqual(walk, 0.667 * 0.745)
        self.assertAlmostEqual(attack, 1.167 * 0.745)
        ctx._companion_rows = {}
        self.assertIsNone(_companion_intervals(ctx, self.actor))


class StanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.actor = self.fixture.view, self.fixture.actor
        self.ai = self.view.companion_ai
        self.ai.assist_scan_tiles = 3

    def stance(self, combat, movement='FOLLOW'):
        self.view.companions.set_commands(2, combat_mode=combat, movement_mode=movement)
        self.ai.command_changed(self.actor.ref, self.fixture.now)

    def test_assist_preempts_monster_coming_at_owner(self):
        monster, _ = self.fixture.monster()
        self.view.ai.on_hit(monster.uid, 1, self.fixture.now)  # monster now targets owner
        self.stance('ASSIST')
        self.ai.step(self.actor.ref, self.fixture.now)
        self.assertEqual(self.actor.target, monster.ref)

    def test_defend_and_passive_do_not_preempt(self):
        monster, _ = self.fixture.monster()
        self.view.ai.on_hit(monster.uid, 1, self.fixture.now)
        for mode in ('DEFEND', 'PASSIVE'):
            with self.subTest(mode=mode):
                self.stance(mode)
                self.ai.step(self.actor.ref, self.fixture.now)
                self.assertIsNone(self.actor.target)

    def test_defend_answers_hits_on_owner_or_self_only(self):
        monster, _ = self.fixture.monster()
        self.stance('DEFEND')
        self.ai.owner_attacked(self.view.entities.get(1).ref, monster.ref, self.fixture.now)
        self.assertIsNone(self.actor.target)
        self.ai.on_hit(self.view.entities.get(1).ref, monster.ref, self.fixture.now)
        self.assertEqual(self.actor.target, monster.ref)

    def test_passive_follow_never_attacks(self):
        monster, _ = self.fixture.monster()
        self.stance('PASSIVE')
        self.ai.on_hit(self.actor.ref, monster.ref, self.fixture.now)
        self.ai.owner_attacked(self.view.entities.get(1).ref, monster.ref, self.fixture.now)
        self.assertIsNone(self.actor.target)

    def test_target_designation_wins_over_owner_target_changes(self):
        first, _ = self.fixture.monster()
        second, _ = self.fixture.monster()
        self.stance('ASSIST')
        self.assertTrue(self.ai.focus_target(self.actor.ref, first.ref, self.fixture.now))
        self.ai.owner_attacked(self.view.entities.get(1).ref, second.ref, self.fixture.now)
        self.assertEqual(self.actor.target, first.ref)
        self.ai.release_target(first.uid, self.fixture.now)
        self.assertIsNone(self.actor.focus)
        self.ai.owner_attacked(self.view.entities.get(1).ref, second.ref, self.fixture.now)
        self.assertEqual(self.actor.target, second.ref)


class OwnerDeathAndExpTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.actor, self.record = self.fixture.view, self.fixture.actor, self.fixture.record
        from tools.local_original_session.world_companion_classes import load_definitions
        from tools.local_original_session import world_feature_companion as feature
        from tools.local_original_session import inventory, world_core_maps as maps
        from tools.local_original_session.world_core_inventory import INVENTORY_STARTER_FIELDS
        self.inventory = inventory
        self.scrolls = []
        base = dict(INVENTORY_STARTER_FIELDS)
        base.update({1: 122, 2: 1, 4: 5})
        self.base = base
        self.no_scroll = inventory.build_kit_frame([base])
        def consume(uid, templates):
            result = self.scrolls.pop() if self.scrolls else None
            if result is not None:
                bags.frames[uid] = self.no_scroll
            return result
        bags = SimpleNamespace(consume_template=consume, frames={2: self.no_scroll})
        self.ctx = SimpleNamespace(world=self.view, _companion_rows={2: dict(name='FixtureMage')}, _companion_inventory=bags,
                                   _companion_defs=load_definitions(), _companion_returns=[],
                                   _companion_errors=[], _companion_death_penalties=[],
                                   _world_map_exp=2, _world_gludin=None,
                                   realm=SimpleNamespace(serves_map=lambda _: True))
        self.ctx.fold_sync_hooks = lambda name, result, position: maps._world_maps_item_destination(self.ctx, result, position)
        self.ctx._world_return_destination = lambda *args: maps._world_return_destination(self.ctx, *args)
        self.ctx._world_relocate_saved_character = lambda *args: maps._world_relocate_saved_character(self.ctx, *args)
        self.view.terrain.can_stand = lambda *_: True
        self.view.companion_owner_death = lambda uid, now: feature._companion_owner_death(self.ctx, uid, now)
        self.view.companions.on_death = lambda record, now: feature._companion_death_penalty(self.ctx, record, now)

    def kill_owner(self):
        state = self.view.combat.pcs[1]
        state.hp = 0
        state.dead = True
        self.view._pc_died(1, self.fixture.now)

    def test_return_scroll_sends_member_to_town_and_keeps_it_summoned(self):
        from tools.local_original_session import movement, world_core_maps as maps, world_item_effects
        from tools.local_original_session.world_maps import MapDestination, load_gludin_policy
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.positions = movement.PositionStore(Path(directory, 'characters.json'))
        self.positions.commit(movement.Position(2, 'FixtureMage', 0, 101, 100),
                              movement.Position(2, 'FixtureMage', 0, 101, 100))
        self.ctx.realm.positions = self.positions
        # Same map4 policy hook and persisted PositionStore as an ordinary return.
        self.ctx._world_gludin = load_gludin_policy()
        entity = self.view.entities.resolve(self.actor.ref)
        self.view.entities.move(entity.uid, 4, 32600, 32700)
        position = MapDestination(entity.map_id, entity.x, entity.y, entity.heading)
        ordinary = world_item_effects.WorldItemEffects(self.view.combat).use(1, 162, 10, position=position)
        expected = maps._world_maps_item_destination(self.ctx, ordinary, position).destination
        from tools.local_original_session.world_core_inventory import INVENTORY_STARTER_FIELDS
        fields = dict(INVENTORY_STARTER_FIELDS)
        fields.update({1: 123, 2: 162, 4: 1})
        self.ctx._companion_inventory.frames[2] = self.inventory.build_kit_frame([self.base, fields])
        self.scrolls.append(162)
        moves = []
        original_move = self.view.entities.move
        def move(uid, map_id, x, y, *args):
            moves.append((uid, map_id, x, y))
            return original_move(uid, map_id, x, y, *args)
        self.view.entities.move = move
        self.kill_owner()
        self.assertNotIn(2, self.view.companions.active)
        self.assertTrue(self.record.summoned)
        self.assertEqual(self.ctx._companion_returns[-1]['result'], 'RETURN_SCROLL_TO_TOWN')
        saved = movement.PositionStore(self.positions.path.with_name('characters.json')).restore(
            movement.Position(2, 'FixtureMage', 0, 101, 100))
        self.assertEqual((saved.map_id, saved.word0, saved.word1), (expected.map_id, expected.x, expected.y))
        self.assertIn((entity.uid, saved.map_id, saved.word0, saved.word1), moves)
        self.assertEqual(self.ctx._companion_inventory.frames[2], self.no_scroll)
        self.assertEqual(self.scrolls, [])

    def test_without_scroll_member_waits_then_is_left_behind(self):
        self.kill_owner()
        self.assertIs(self.view.companions.active.get(2), self.actor)
        self.assertTrue(self.actor.owner_down)
        self.view.companion_ai.step(self.actor.ref, self.fixture.now)
        self.assertEqual(self.actor.action, 'HOLD')
        self.view.companion_ai.sync(self.fixture.now)
        self.assertIn(2, self.view.companions.active)
        self.view.leave_pc(1)
        self.assertNotIn(2, self.view.companions.active)
        self.assertFalse(self.record.summoned)

    def test_member_death_loses_exp_like_an_ordinary_character(self):
        from tools.local_original_session import world_reward
        data = self.view.data
        self.record.level, self.record.exp = 15, data.pc_exp[14] + 50
        expected = world_reward.death_exp_penalty(self.record.exp, data=data)
        self.assertGreater(expected.exp_lost, 0)
        self.view.companions.die(2, self.fixture.now)
        self.assertEqual((self.record.exp, self.record.level), (expected.new_exp, expected.new_level))
        self.view.companions.die(2, self.fixture.now)  # already dead: no second loss
        self.assertEqual(self.record.exp, expected.new_exp)

    def test_low_level_death_has_no_loss_and_no_item_drop_path(self):
        self.record.level, self.record.exp = 5, self.view.data.pc_exp[4]
        exp = self.record.exp
        self.view.companions.die(2, self.fixture.now)
        self.assertEqual(self.record.exp, exp)
        import inspect
        from tools.local_original_session import world_feature_companion, world_companion_runtime
        for module in (world_feature_companion, world_companion_runtime):
            self.assertNotIn('roll_death_penalty', inspect.getsource(module))

    def test_kill_exp_is_always_half_regardless_of_level(self):
        from tools.local_original_session.world_companion import split_exp
        self.assertEqual(split_exp(31, 0, 0)[:2], (15, 15))
        self.assertEqual(split_exp(31, 1, 1)[:2], (16, 16))


class PartyProjectionTests(unittest.TestCase):
    @staticmethod
    def consume(rows, wires, *, owner_uid=1):
        """Native append/erase/status model for the one LOCAL owner group."""
        from tools.local_original_session.hunt_bot import fields, scalar
        for wire in wires:
            opcode, message = int.from_bytes(wire[2:4], 'little'), fields(wire[4:-2])
            if opcode == 0x08a0:
                for child in message.get(2, ()):
                    member = fields(child)
                    rows.append(dict(name=scalar(member, 1), key=scalar(member, 12, 0),
                        uid=scalar(member, 3), hp=scalar(member, 6), mp=scalar(member, 7)))
            elif opcode == 0x08a1:
                for index, row in enumerate(rows):
                    if (row['name'], row['key']) == (scalar(message, 2), scalar(message, 5)):
                        if row['uid'] == owner_uid:  # selected PC clears this group
                            rows.clear()
                        else:
                            rows.pop(index)
                        break
            elif opcode == 0x08a3:
                for child in message.get(1, ()):
                    status = fields(child)
                    row = next((row for row in rows if (row['name'], row['key']) ==
                                (scalar(status, 1), scalar(status, 10))), None)
                    if row is not None:
                        row.update(hp=scalar(status, 3), mp=scalar(status, 4))

    def projection(self):
        from tools.local_original_session.world_feature_companion import CompanionParty
        fixture = fixtures.CompanionWorldViewTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        ctx = SimpleNamespace(world=fixture.view, _companion_revive_exp=False,
            _companion_rows={1: dict(name='FixtureKnight'), 2: dict(name='FixtureMage')})
        party = ctx._companion_party = CompanionParty(ctx)
        ctx._companion_save = fixture.view.companion_save = lambda *args: party.sync()
        fixture.view.drain(1)
        party.sync()
        rows = []
        self.consume(rows, fixture.view.drain(1))
        return fixture, ctx, party, rows

    def resource_projection(self):
        """Real feature save callback; memory commit stub makes no disk claim."""
        from unittest.mock import Mock
        from tools.local_original_session import world_feature_companion as feature
        fixture, ctx, party, rows = self.projection()
        ctx._companion_store = SimpleNamespace(commit=Mock())
        ctx._companion_inventory = None
        ctx._companion_windows, ctx._companion_pet_modes, ctx._companion_views = {}, {}, {}
        ctx._companion_save = lambda uid, receipt=None: feature._companion_save(ctx, uid, receipt)
        fixture.view.companion_save = ctx._companion_save
        fixture.view.events.add('companion_party', 'tick', party.sync, priority=100)
        return fixture, ctx, party, rows

    def consume_resource_update(self, fixture, rows):
        from tools.local_original_session.hunt_bot import fields, scalar
        wires = fixture.view.drain(1)
        statuses = [fields(child) for wire in wires if int.from_bytes(wire[2:4], 'little') == 0x08a3
                    for child in fields(wire[4:-2]).get(1, ())]
        member = next(status for status in statuses if scalar(status, 1) == b'FixtureMage')
        self.assertEqual((scalar(member, 3), scalar(member, 4)),
                         (100 * fixture.record.hp // fixture.record.max_hp,
                          100 * fixture.record.mp // fixture.record.max_mp))
        self.assertFalse(any(int.from_bytes(wire[2:4], 'little') == 0x08a0 for wire in wires))
        self.consume(rows, wires)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['hp'], scalar(member, 3))
        self.assertEqual(rows[1]['mp'], scalar(member, 4))
        return member

    def test_actual_npc_physical_damage_saves_and_decreases_party_percentage(self):
        fixture, ctx, party, rows = self.resource_projection()
        view, record = fixture.view, fixture.record
        record.hp = record.max_hp = 200
        monster, definition = fixture.monster()
        entity = view.entities.resolve(fixture.actor.ref)
        view.entities.move(monster.uid, 0, entity.x + 1, entity.y)
        view.drain(1)
        owner_hp = view.combat.pcs[1].hp
        for attempt in range(30):
            view.npc_attack(monster, definition, fixture.actor.ref.uid,
                            fixture.now + attempt * definition.attack_interval_ms / 1000)
            if record.hp < 200:
                break
        self.assertLess(record.hp, 200)
        self.consume_resource_update(fixture, rows)
        self.assertLess(rows[1]['hp'], 100)
        self.assertEqual(view.combat.pcs[1].hp, owner_hp)
        ctx._companion_store.commit.assert_called()
        self.assertEqual(view.companion_save_errors, [])

    def test_actual_magic_target_damage_finish_saves_party_percentage(self):
        from tools.local_original_session import world_feature_companion as feature
        from tools.local_original_session.world_combat import NpcMagicAttack
        fixture, ctx, party, rows = self.resource_projection()
        view, record = fixture.view, fixture.record
        record.hp = record.max_hp = 200
        source, definition = fixture.monster()
        view.drain(1)
        target = feature.CompanionMonsterTarget(view, fixture.actor, feature.CompanionAilments(view))
        attack = NpcMagicAttack(dict(damage_value=30, damage_dice=1,
            damage_dice_count=0, element_attr_raw=2, skill_level=7), 12)
        swing, wire = target.apply(definition, attack, fixture.now)
        self.assertGreater(swing.damage, 0)
        self.assertIsNone(wire)
        target.finish(source.ref, swing, fixture.now)
        self.consume_resource_update(fixture, rows)
        self.assertLess(rows[1]['hp'], 100)
        ctx._companion_store.commit.assert_called()
        self.assertEqual(view.companion_save_errors, [])

    def test_real_self_heal_and_mp_regen_publish_party_resource_recovery(self):
        from tools.local_original_session.world_feature_companion import CompanionMagic
        from tools.local_original_session import ats_config_codec as codec
        fixture, ctx, party, rows = self.resource_projection()
        view, record, actor = fixture.view, fixture.record, fixture.actor
        root = Path(__file__).parent / 'data' / 'companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        magic = CompanionMagic(view, read('mage_spells'), read('mage_growth'), read('ai_policy'),
                               {2: (8, 7, 16, 18, 8, 18)}, display=False)
        record.hp, record.max_hp, record.mp, record.max_mp = 20, 200, 20, 40
        record.level = 5  # heal's ordinary mage learning level is 4
        record.learned_spells = (0,)
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(sequence_spells=(0,))), {0: 'heal'})
        magic.policy_for = lambda _: policy
        party.sync()
        self.consume(rows, view.drain(1))
        before_hp, before_mp = record.hp, record.mp
        entity = view.entities.resolve(actor.ref)
        self.assertTrue(magic.cast(actor, entity, entity, 'heal', fixture.now))
        self.assertGreater(record.hp, before_hp)
        self.assertLess(record.mp, before_mp)
        self.consume_resource_update(fixture, rows)
        before_hp, before_mp = record.hp, record.mp
        actor.regen_at = fixture.now
        actor.regen_points = magic.growth['mp_regeneration']['timing']['threshold_points']
        magic.regen(actor, fixture.now)
        self.assertEqual(record.hp, before_hp)  # HP's independent threshold is not due
        self.assertGreater(record.mp, before_mp)
        self.consume_resource_update(fixture, rows)
        self.assertEqual(view.companion_save_errors, [])

    def test_natural_hp_recovery_commits_and_updates_existing_party_row(self):
        from tools.local_original_session.world_feature_companion import CompanionMagic
        fixture, ctx, party, rows = self.resource_projection()
        view, record, actor = fixture.view, fixture.record, fixture.actor
        root = Path(__file__).parent / 'data' / 'companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        magic = CompanionMagic(view, read('mage_spells'), read('mage_growth'), read('ai_policy'),
                               {2: (8, 7, 16, 18, 8, 18)})
        record.hp, record.max_hp, record.level = 20, 200, 10
        record.mp = record.max_mp = 40
        party.sync()
        self.consume(rows, view.drain(1))
        ctx._companion_store.commit.reset_mock()
        magic.regen(actor, 10)
        magic.regen(actor, 11)
        magic.regen(actor, 12)
        ctx._companion_store.commit.assert_not_called()
        magic.regen(actor, 13)
        self.assertEqual((record.hp, record.mp), (27, 40))
        ctx._companion_store.commit.assert_called_once()
        self.assertIn(record, tuple(ctx._companion_store.commit.call_args.kwargs['records']))
        self.consume_resource_update(fixture, rows)
        self.assertEqual(rows[1]['hp'], 13)
        self.assertEqual(view.companion_save_errors, [])

    def test_real_hp_potion_spends_one_and_publishes_party_recovery(self):
        from unittest.mock import Mock
        from tools.local_original_session import inventory
        from tools.local_original_session.world_companion_inventory import CompanionInventory
        from tools.local_original_session.world_companion_equipment_tests import item
        fixture, ctx, party, rows = self.resource_projection()
        view, record, actor = fixture.view, fixture.record, fixture.actor
        record.hp, record.max_hp = 20, 200
        party.sync()
        self.consume(rows, view.drain(1))
        # Exercise the real potion producer with its disk CAS boundary stubbed.
        bags = object.__new__(CompanionInventory)
        bags.ctx, bags.save = ctx, ctx._companion_save
        bags.store = SimpleNamespace(replace_kit=Mock())
        bags.frames = {2: inventory.build_kit_frame([item(30, 14, 2)])}
        bags.states = {2: SimpleNamespace(item_uid=30)}
        bags.next_potion, bags.blue_until, bags.events, bags.item_effects = {}, {}, [], {}
        bags.policy_for = lambda _: dict(status='valid', selection_id='fixture',
            potion_hp=dict(threshold=.5, slots=(dict(status='valid', raw={1: 2, 4: 14, 5: 0, 6: 1}),)))
        before = record.hp
        self.assertTrue(bags.potion(actor, fixture.now))
        self.assertGreater(record.hp, before)
        self.assertEqual(dict(inventory.validate_kit_frame(bags.frames[2])[0].raw_fields)[4], 1)
        bags.store.replace_kit.assert_called_once()
        self.consume_resource_update(fixture, rows)
        self.assertEqual(view.companion_save_errors, [])

    def test_death_revive_keeps_one_native_row_and_only_updates_resources(self):
        from tools.local_original_session.world_feature_companion import _companion_revive
        fixture, ctx, party, rows = self.projection()
        view, old = fixture.view, fixture.actor.ref
        for _ in range(2):
            view.companions.die(2, fixture.now)
            party.sync()
            dead = view.drain(1)
            self.assertEqual([int.from_bytes(w[2:4], 'little') for w in dead], [0x08a3])
            self.consume(rows, dead)
            self.assertEqual(rows[1]['hp'], 0)
            _companion_revive(ctx, 1, fixture.record)
            revived = view.drain(1)
            self.assertEqual([int.from_bytes(w[2:4], 'little') for w in revived
                              if 0x08a0 <= int.from_bytes(w[2:4], 'little') <= 0x08a3], [0x08a3])
            self.consume(rows, revived)
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[1]['uid'], rows[1]['hp'], rows[1]['mp']), (old.uid, 25, 100))
        self.assertEqual(fixture.actor.ref.uid, old.uid)
        self.assertGreater(fixture.actor.ref.generation, old.generation)
        self.assertIsNone(view.entities.resolve(old))

    def test_owner_death_restart_replays_removal_dropped_with_outbox(self):
        import asyncio
        from tools.local_original_session import world_feature_companion as feature
        fixture, ctx, party, rows = self.projection()
        view, old = fixture.view, fixture.actor.ref
        # A client that already saw the old duplicate-producing LIST also
        # clears all its stale rows when the owner removal resets this group.
        rows.extend(dict(row) for row in tuple(rows))
        # Ordinary owner death retires the member and queues removal, but the
        # restart may discard that outbox before a socket flush consumes it.
        view.combat.pcs[1].hp, view.combat.pcs[1].dead = 0, True
        view._pc_died(1, fixture.now)
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in view.outbox[1]
                          if 0x08a0 <= int.from_bytes(w[2:4], 'little') <= 0x08a3],
                         [0x08a1, 0x08a1])
        writer = object()
        asyncio.run(feature._companion_before_leave(ctx, writer, 1))
        view.leave_pc(1)
        self.assertNotIn(1, view.outbox)
        # Reuse the ordinary fixture's selected PC profile/status on restart.
        from tools.local_original_session.world_combat import PcProfile, ATHAME
        from tools.local_native_login_self_actor_hook import hook
        view.update_pc(1, 0, 100, 100)
        status = dict(hook.profiles()[0].fields)
        status.update({1: 1, 2: 1, 10: 100, 11: 100, 12: 20, 13: 20, 18: 500})
        view.bind_pc(1, PcProfile(1, 1, 0, 18, 13, con=16, weapon=ATHAME), status)
        party.reset(1)
        actor = view.summon_companion(2, 1)
        wires = view.drain(1)
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in wires
                          if 0x08a0 <= int.from_bytes(w[2:4], 'little') <= 0x08a3],
                         [0x08a1, 0x08a1, 0x08a0, 0x08a3])
        self.consume(rows, wires)
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['uid'] for row in rows], [1, actor.ref.uid])
        self.assertNotEqual(actor.ref.uid, old.uid)
        self.assertIsNone(view.entities.resolve(old))

    def test_repeated_replacement_removes_before_appending_and_leave_preserves_keys(self):
        fixture, ctx, party, rows = self.projection()
        view = fixture.view
        for _ in range(3):
            view.companions.dismiss(2)
            actor = view.summon_companion(2, 1)
            wires = view.drain(1)
            self.assertEqual([int.from_bytes(w[2:4], 'little') for w in wires
                              if 0x08a0 <= int.from_bytes(w[2:4], 'little') <= 0x08a3],
                             [0x08a1, 0x08a1, 0x08a0, 0x08a3])
            self.consume(rows, wires)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]['uid'], actor.ref.uid)
        party.depart(1)
        old_rows = party.sent[1]
        view.leave_pc(1)
        party.sync()
        self.assertEqual(party.sent[1], old_rows)
        self.assertEqual(view.drain(1), [])

    def test_real_owner_death_without_scroll_waits_then_reselect_call_replaces_rows(self):
        import asyncio
        from tools.local_original_session import world_feature_companion as feature
        from tools.local_original_session.world_companion_classes import load_definitions
        from tools.local_original_session.world_combat import PcProfile, ATHAME
        from tools.local_native_login_self_actor_hook import hook
        fixture, ctx, party, rows = self.projection()
        view, old = fixture.view, fixture.actor.ref
        ctx._companion_inventory = None
        ctx._companion_defs = load_definitions()
        ctx._companion_returns = []
        view.companion_owner_death = lambda uid, now: feature._companion_owner_death(ctx, uid, now)
        view.combat.pcs[1].hp, view.combat.pcs[1].dead = 0, True
        view._pc_died(1, fixture.now)
        self.assertIs(view.companions.active[2], fixture.actor)
        self.assertTrue(fixture.actor.owner_down)
        self.assertEqual(fixture.actor.action, 'HOLD')
        self.assertEqual(ctx._companion_returns[-1]['result'], 'WAIT_NO_RETURN_SCROLL')
        self.consume(rows, view.drain(1))
        self.assertEqual(len(rows), 2)
        asyncio.run(feature._companion_before_leave(ctx, object(), 1))
        view.leave_pc(1)
        self.assertFalse(fixture.record.summoned)
        self.assertNotIn(2, view.companions.active)
        self.assertNotIn(1, view.outbox)
        view.update_pc(1, 0, 100, 100)
        status = dict(hook.profiles()[0].fields)
        status.update({1: 1, 2: 1, 10: 100, 11: 100, 12: 20, 13: 20, 18: 500})
        view.bind_pc(1, PcProfile(1, 1, 0, 18, 13, con=16, weapon=ATHAME), status)
        party.reset(1)
        self.consume(rows, view.drain(1))
        self.assertEqual(rows, [])
        actor = feature._companion_call(ctx, 1)
        self.assertNotEqual(actor.ref.uid, old.uid)
        self.assertIsNone(view.entities.resolve(old))
        self.assertTrue(fixture.record.summoned)
        self.consume(rows, view.drain(1))
        self.assertEqual([row['uid'] for row in rows], [1, actor.ref.uid])

    def test_list_then_initial_status_resources_replacement_and_retirement(self):
        from tools.local_original_session.world_feature_companion import CompanionParty
        from tools.local_original_session.hunt_bot import fields, scalar
        fixture = fixtures.CompanionWorldViewTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        view, record = fixture.view, fixture.record
        ctx = SimpleNamespace(world=view, _companion_rows={
            1: dict(name='FixtureKnight'), 2: dict(name='FixtureMage')})
        party = CompanionParty(ctx)
        view.events.add('companion_party', 'tick', party.sync, priority=100)
        view.companion_save = lambda *args: party.sync()
        view.drain(1)

        def frames():
            return [(int.from_bytes(w[2:4], 'little'), fields(w[4:-2]))
                    for w in view.drain(1) if int.from_bytes(w[2:4], 'little') in (0x08a0, 0x08a1, 0x08a3)]
        def children(message, field):
            return [fields(value) for value in message.get(field, [])]
        party.sync()
        initial = frames()
        self.assertEqual([op for op, _ in initial], [0x08a0, 0x08a3])
        listing, updates = initial[0][1], children(initial[1][1], 1)
        members = children(listing, 2)
        self.assertEqual((scalar(listing, 1), scalar(listing, 3), scalar(listing, 4)),
                         (b'FixtureKnight', 0, 1))
        self.assertEqual([scalar(m, 3) for m in members], [1, fixture.actor.ref.uid])
        for member, status in zip(members, updates):
            self.assertEqual((scalar(member, 1), scalar(member, 4)),
                             (scalar(status, 1), scalar(status, 10)))
            self.assertEqual((scalar(member, 6), scalar(member, 7)), (100, 100))
            self.assertEqual((scalar(status, 3), scalar(status, 4)), (100, 100))
            self.assertNotIn(2, status)  # no unproven f2=actor UID
        party.sync()
        self.assertEqual(frames(), [])
        # Server generations invalidate combat references, but are absent from
        # native party rows. Replacing only that reference must not rejoin.
        entity = view.entities.resolve(fixture.actor.ref)
        entity.generation += 1
        fixture.actor.ref = entity.ref
        party.sync()
        self.assertEqual(frames(), [])
        self.assertEqual(party.sent[1][1][2], entity.ref)
        record.hp, record.mp, record.max_mp = 3, 3, 12
        view.combat.pcs[1].hp = 40
        view.events.emit('tick', fixture.now)
        update = frames()
        self.assertEqual([op for op, _ in update], [0x08a3])
        self.assertEqual([(scalar(m, 3), scalar(m, 4)) for m in children(update[0][1], 1)],
                         [(40, 100), (25, 25)])

        old = fixture.actor.ref
        view.companions.dismiss(2)
        self.assertNotIn(1, party.sent)
        removed = frames()
        self.assertEqual([op for op, _ in removed], [0x08a1, 0x08a1])
        self.assertEqual([(scalar(m, 2), scalar(m, 5), scalar(m, 7)) for _, m in removed],
                         [(b'FixtureMage', 0, 1), (b'FixtureKnight', 0, 1)])
        actor = view.summon_companion(2, 1)
        replacement = frames()
        self.assertEqual([op for op, _ in replacement], [0x08a0, 0x08a3])
        self.assertNotEqual(old, actor.ref)
        self.assertEqual(scalar(children(replacement[0][1], 2)[1], 3), actor.ref.uid)
        record.hp = 0
        view.companions.die(2, fixture.now)
        party.sync()
        self.assertEqual(scalar(children(frames()[0][1], 1)[0], 3), 0)
        party.depart(1)
        previous = party.sent[1]
        view.leave_pc(1)
        party.sync()
        self.assertEqual(party.sent[1], previous)
        self.assertEqual(frames(), [])

    def test_enter_restoration_save_publishes_one_list_per_fresh_client(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from tools.local_original_session import world_feature_companion as feature
        from tools.local_original_session.hunt_bot import fields, scalar
        fixture = fixtures.CompanionWorldViewTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        view, record = fixture.view, fixture.record
        writer = object()
        ctx = SimpleNamespace(world=view, _companion_enabled=True,
            _companion_rows={1: dict(name='FixtureKnight'), 2: dict(name='FixtureMage')},
            _companion_store=SimpleNamespace(pending=None, payload={'owners': {}}),
            _world_bound=lambda _: True, _world_pcs={id(writer): (writer, 1)},
            _companion_mapped={}, _world_send=AsyncMock())
        party = ctx._companion_party = feature.CompanionParty(ctx)
        view.companion_save = lambda *args: party.sync()
        party.sync()
        view.drain(1)
        view.companions.dismiss(2)
        record.summoned = True
        view.drain(1)
        with patch.object(feature, '_companion_restore',
                          side_effect=lambda _, uid, member: view.summon_companion(member, uid)), \
             patch.object(feature, '_companion_publish_map'):
            asyncio.run(feature._companion_enter(ctx, writer, {}, None, None))
            sent = ctx._world_send.await_args.args[2]
            lists = [fields(w[4:-2]) for w in sent
                     if int.from_bytes(w[2:4], 'little') == 0x08a0]
            self.assertEqual(len(lists), 1)
            self.assertEqual([scalar(fields(member), 1) for member in lists[0][2]],
                             [b'FixtureKnight', b'FixtureMage'])
            self.assertEqual(sum(int.from_bytes(w[2:4], 'little') == 0x08a3 for w in sent), 1)
            # A later fresh client still needs its initial native rows.
            asyncio.run(feature._companion_enter(ctx, writer, {}, None, None))
            sent = ctx._world_send.await_args.args[2]
            self.assertEqual(sum(int.from_bytes(w[2:4], 'little') == 0x08a0 for w in sent), 1)


class LegacyDismissRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_offscreen_query_and_menu_command_keep_current_owner_and_life_checks(self):
        from unittest.mock import AsyncMock, Mock, patch
        from tools.local_entry_server import protobuf as pb
        from tools.local_original_session import world_feature_companion as feature
        fixture = fixtures.CompanionWorldViewTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        view, actor = fixture.view, fixture.actor
        writer, game = object(), object()
        ctx = SimpleNamespace(world=view, _companion_enabled=True, _companion_pet_ui=True,
            _world_bound=lambda _: True, _world_ready=lambda *_: game,
            _world_pcs={id(writer): (writer, 1)}, _companion_windows={},
            _companion_save=Mock(), _companion_pet_modes={}, _companion_errors=[],
            owner_current=lambda *_: True, _world_send=AsyncMock(),
            realm=SimpleNamespace(registry=SimpleNamespace(resolve=lambda _: game),
                                  service=lambda _: SimpleNamespace(snapshot=lambda: object())))
        view.update_pc_and_drain(1, 0, 150, 100)
        self.assertNotIn(actor.ref.uid, view.visibility.known[1])
        query = SimpleNamespace(opcode=0x4f13, payload=pb.encode_uint32(1, actor.ref.uid))
        command = SimpleNamespace(opcode=0x4f02,
            payload=pb.encode_uint32(1, 2) + pb.encode_uint32(3, actor.ref.uid))
        with patch.object(feature, '_companion_publish_map'):
            self.assertTrue(await feature._companion_frame(ctx, writer, {}, game, query, None))
            self.assertEqual(ctx._companion_windows[id(writer)], actor.ref)
            frames = ctx._world_send.await_args.args[2]
            self.assertEqual(len(fixture.decoded(frames, 0x4f14, 1, actor.ref.uid)), 1)
            self.assertTrue(await feature._companion_frame(ctx, writer, {}, game, command, None))
            self.assertEqual(actor.record.combat_mode, 'ASSIST')
            self.assertFalse(ctx._companion_errors)
            ctx.owner_current = lambda *_: False
            await feature._companion_frame(ctx, writer, {}, game, query, None)
            self.assertEqual(ctx._companion_errors[-1], 'COMPANION_CURRENT_SELECTED_OWNER_REQUIRED')
            ctx.owner_current = lambda *_: True
            actor.record.summoned = False
            await feature._companion_frame(ctx, writer, {}, game, query, None)
            self.assertEqual(ctx._companion_errors[-1], 'COMPANION_LIVING_ACTOR_REQUIRED')

    async def test_mode8_preserves_actor_and_commands(self):
        from dataclasses import asdict
        from unittest.mock import AsyncMock, Mock
        from tools.local_entry_server import protobuf as pb
        from tools.local_original_session import world_feature_companion as feature
        fixture = fixtures.CompanionWorldViewTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        view, actor = fixture.view, fixture.actor
        writer, game = object(), object()
        ctx = SimpleNamespace(world=view, _companion_enabled=True, _companion_pet_ui=True,
            _world_bound=lambda _: True, _world_ready=lambda *_: game,
            _world_pcs={id(writer): (writer, 1)}, _companion_windows={id(writer): actor.ref},
            _companion_save=Mock(), _companion_pet_modes={}, _companion_errors=[],
            owner_current=lambda *_: True, _world_send=AsyncMock(),
            realm=SimpleNamespace(registry=SimpleNamespace(resolve=lambda _: game),
                                  service=lambda _: SimpleNamespace(snapshot=lambda: object())))
        before, ref, handle = asdict(actor.record), actor.ref, actor.handle
        frame = SimpleNamespace(opcode=0x4f02,
                                payload=pb.encode_uint32(1, 8) + pb.encode_uint32(3, ref.uid))
        view.drain(1)
        self.assertTrue(await feature._companion_frame(ctx, writer, {}, game, frame, None))
        self.assertIs(view.companions.active[2], actor)
        self.assertEqual((actor.ref, actor.handle), (ref, handle))
        self.assertEqual(asdict(actor.record), before)
        self.assertEqual(ctx._companion_errors, [])
        ctx._companion_save.assert_called_once_with(1)
        sent = ctx._world_send.await_args.args[2]
        self.assertFalse(any(int.from_bytes(w[2:4], 'little') == 0x4e40 for w in sent))


class SignalAndModelTests(unittest.TestCase):
    def test_item_operations_roundtrip_and_marker_errors_never_fall_back(self):
        from tools.local_original_session import companion_signals as cs
        body = cs.encode_signal('item-take', 77, ('2', '3', '1', '4096', '5'))
        signal = cs.decode_signal(body)
        self.assertEqual((signal.operation, signal.actor_uid, signal.numbers()),
                         ('item-take', 77, (2, 3, 1, 4096, 5)))
        self.assertIsNone(cs.decode_signal(b'\x08\x02\x18\x05'))
        with self.assertRaises(cs.SignalError):
            cs.decode_signal(b'\x08\x07\x12\x15LOCAL_COMPANION_UI_V1\x12\x09item-take\x18\x05')
        f4 = bytes.fromhex('0807 1215 4c4f43414c5f434f4d50414e494f4e5f55495f5631 1209 66342d7069636b7570 1800'.replace(' ', ''))
        self.assertEqual(cs.decode_signal(f4).operation, 'f4-pickup')

    def test_model_frame_layout_matches_signals_contract(self):
        from tools.local_original_session import world_companion_ui as ui
        frame = ui.model_frame(actor=9, generation=2, owner=1, member=2, revision=1,
                               packets=[(0x0964, b'ab'), (0x4E38, b'')])
        self.assertEqual(frame[:8], b'LCMPMD2\x00')
        self.assertEqual(struct.unpack_from('<QQQQQII', frame, 8), (9, 2, 1, 2, 1, 1, 2))
        decoded = ui.decode_model_frame(frame)
        self.assertEqual(decoded['packets'], ((0x0964, b'ab'), (0x4E38, b'')))
        with self.assertRaises(ValueError):
            ui.model_frame(actor=0, generation=1, owner=1, member=2, revision=1, packets=())

    def test_request_literal_and_directory_host(self):
        from tools.local_original_session import companion_bridge_host as host_module
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'context.json').write_text(json.dumps(dict(
                schema='own-key-invoke-primary-v1', pid=123, birth=456, candidate_sha256='a' * 64)))
            Path(directory, 'manual-move-result-7.json').write_text('{}')
            posted = []
            host = host_module.DirectoryHost(directory, poster=lambda m, s: posted.append((m, s)) or True)
            seq, ok = host.publish_request(dict(command='map', actor_uid=9, actor_generation=2,
                owner_uid=1, member_id=2, hold=1, lawful_known=1, lawful=-5))
            self.assertEqual((seq, ok, posted[-1]), (8, True, ('LC-Owned-Companion-v1', 8)))
            text = Path(directory, 'companion-request-8.json').read_text()
            self.assertEqual(text, '{"schema":"own-companion-request-v1","pid":123,"birth":456,'
                '"candidate_sha256":"' + 'a' * 64 + '","seq":8,"command":"map","actor_uid":9,'
                '"actor_generation":2,"owner_uid":1,"member_id":2,"hold":1,"lawful_known":1,'
                '"lawful":-5,"event_seq":0,"ats_epoch":0}\n')
            seq, _ = host.publish_request(dict(command='ats-edit-apply', member_id=2, event_seq=4,
                                                ats_epoch=1, label_hex='동료: A'.encode().hex()))
            self.assertTrue(Path(directory, 'companion-request-9.json').read_text().endswith(
                '"event_seq":4,"ats_epoch":1,"label_hex":"eb8f99eba38c3a2041"}\n'))
            with self.assertRaises(ValueError):
                host_module.request_text(host.identity, 10, dict(command='ats-edit-apply', label_hex='ABC'))
            seq, _ = host.publish_model(b'LCMPMD2\x00')
            self.assertEqual(posted[-1], ('LC-Owned-CompanionModel-v2', 10))
            self.assertTrue(Path(directory, 'companion-model-10.bin').exists())


class AtsCodecTests(unittest.TestCase):
    def test_condition_percent_boundaries_without_integer_rounding(self):
        from tools.local_original_session import ats_config_codec as codec
        record = SimpleNamespace(hp=1, max_hp=3, mp=2, max_mp=3)
        for kind, threshold, expected in ((1, 33, True), (1, 34, False),
                (2, 33, False), (2, 34, True), (3, 66, True), (3, 67, False),
                (4, 66, False), (4, 67, True)):
            with self.subTest(kind=kind, threshold=threshold):
                self.assertEqual(codec.condition_matches(kind, threshold, record), expected)
        record.hp = record.mp = 1
        record.max_hp = record.max_mp = 2
        for kind in range(1, 5):
            self.assertTrue(codec.condition_matches(kind, 50, record))

    def test_condition_time_first_evaluation_integer_seconds_and_count_cap(self):
        from tools.local_original_session import ats_config_codec as codec
        state = {}
        self.assertTrue(codec.condition_matches(5, 5, None, state=state, now=10.25))
        self.assertEqual(state, {'at': 10.25})
        self.assertFalse(codec.condition_matches(5, 5, None, state=state, now=15.24))
        self.assertTrue(codec.condition_matches(5, 5, None, state=state, now=15.25))
        self.assertTrue(codec.condition_matches(6, 1, None, state=state))
        self.assertFalse(codec.condition_matches(6, 0, None, state=state))
        state['count'] = 1
        self.assertFalse(codec.condition_matches(6, 1, None, state=state))

    def test_unknown_conditions_remain_false_on_heal_and_attack(self):
        from tools.local_original_session import ats_config_codec as codec
        for kind in (0, -1, 7, 987):
            self.assertFalse(codec.condition_matches(kind, 50, None, state={}, now=10))
            policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(
                conditional=((kind, 50, 0), (kind, 50, 3)))), {0: 'heal', 3: 'energy_bolt'})
            self.assertEqual(policy['heal_spells'], [])
            self.assertEqual(policy['attack_spells'], [])
            self.assertEqual([row['conditions'] for row in policy['battle_slots']],
                             [[(kind, 50)], [(kind, 50)]])
            self.assertEqual(len(policy['issues']), 2)

    def test_policy_from_companion_scope_blob(self):
        from tools.local_original_session import ats_config_codec as codec
        ats = codec.build_ats(hp_templates=(14,), hp_percent=50.0, mp_templates=(492,), mp_percent=30.0,
                              function_templates=(17,), buff_spells=(3,), sequence_spells=(3,),
                              conditional=((1, 70, 0),), options={1: 6, 7: 50})
        wrapper = codec.wrap_blob(ats)
        keys = {0: 'heal', 3: 'energy_bolt', 4: 'shield'}
        policy = codec.companion_policy(wrapper, keys)
        self.assertEqual(policy['potion_hp']['templates'], [14])
        self.assertEqual(policy['potion_hp']['threshold'], 0.5)
        self.assertAlmostEqual(policy['potion_mp']['threshold'], 0.3)
        self.assertEqual(policy['function_items'], [17])
        self.assertEqual(policy['attack_spells'], ['energy_bolt'])
        self.assertEqual(policy['heal_spells'], [])  # conditional stays an expression
        self.assertEqual(policy['status'], 'valid')
        self.assertEqual(policy['battle_slots'][1]['condition'], 1)
        self.assertEqual(policy['battle_slots'][1]['conditions'], [(1, 70)])
        self.assertEqual(policy['issues'], [])
        self.assertEqual((policy['scan_tiles'], policy['pickup_weight']), (6, 50))
        self.assertEqual(codec.read_noti_field(codec.noti_field(wrapper)), wrapper)

    def test_missing_empty_valid_and_invalid_selection_states(self):
        from tools.local_original_session import ats_config_codec as codec
        keys = {0: 'heal'}
        self.assertEqual(codec.companion_policy(None, keys)['status'], 'missing')
        empty = codec.companion_policy(codec.wrap_blob(codec.build_ats()), keys)
        self.assertEqual(empty['status'], 'empty')
        self.assertEqual(empty['maintain_buffs'], [])
        self.assertEqual(empty['attack_spells'], [])
        valid = codec.companion_policy(codec.wrap_blob(codec.build_ats(sequence_spells=(0,))), keys)
        self.assertEqual(valid['status'], 'valid')
        self.assertEqual(valid['battle_slots'][0]['spell'], 'heal')
        for blob in (b'', b'bad', codec.wrap_blob(b'\x08\x01'),
                     codec.wrap_blob(codec.build_ats(hp_templates=({4: 14},))),
                     codec.wrap_blob(codec.build_ats(sequence_spells=(999,)))):
            with self.subTest(blob=blob):
                invalid = codec.companion_policy(blob, keys)
                self.assertEqual(invalid['status'], 'invalid')
                self.assertTrue(invalid['issues'])

    def test_raw_battle_rows_keep_cross_type_order_and_empty_slots(self):
        from tools.local_original_session import ats_config_codec as c
        spell = c.field(1, 0, 1) + c.field(4, 0, 0)
        condition = c.field(1, 0, 999) + c.field(2, 0, 50) + c.field(3, 2, spell)
        battle = c.field(2, 2, condition) + c.field(1, 2, b'') + c.field(1, 2, spell)
        raw = c.field(1, 2, c.field(2, 2, c.field(2, 2, battle)))
        rows = c.companion_policy(c.wrap_blob(raw), {0: 'heal'})['battle_slots']
        self.assertEqual([r['kind'] for r in rows], ['conditional', 'sequence', 'sequence'])
        self.assertEqual([r['status'] for r in rows], ['valid', 'empty', 'valid'])

    def test_item_identity_preserves_unsigned_opaque64(self):
        from tools.local_original_session import ats_config_codec as c
        identity = (1 << 63) + 7
        policy = c.companion_policy(c.wrap_blob(c.build_ats(
            hp_templates=({4: 14, 5: 0, 6: identity, 7: b'opaque'},), hp_percent=50)), {})
        self.assertEqual(policy['status'], 'valid')
        self.assertEqual(policy['potion_hp']['slots'][0]['raw'][6], identity)

    def test_invalid_saved_policy_is_recorded_once_and_missing_has_no_fallback(self):
        from tools.local_original_session import world_feature_companion_ats as ats
        ctx = SimpleNamespace(_ats_enabled=True, _ats_policies={}, _ats_events=[],
            _ats_store={'characters': {'2': {'companion_ats': 'broken'}}})
        self.assertEqual(ats._ats_policy(ctx, None, 3)['status'], 'missing')
        self.assertEqual(ats._ats_policy(ctx, None, 2)['status'], 'invalid')
        ats._ats_policy(ctx, None, 2)
        self.assertEqual(len(ctx._ats_events), 1)

    def test_select_supplies_full_4ed7_and_companion_save_is_attributed(self):
        from tools.local_original_session import ats_config_codec as codec
        from tools.local_original_session import world_feature_companion_ats as ats
        from tools.local_entry_server import protobuf as pb
        self_cfg, self_ats = codec.wrap_blob(b'\x08\x01'), codec.wrap_blob(codec.build_ats(buff_spells=(4,)))
        mate_ats = codec.wrap_blob(codec.build_ats(sequence_spells=(3,)))
        saved, queued, published = [], [], []
        with tempfile.TemporaryDirectory() as directory:
            writer = object()
            ctx = SimpleNamespace(_ats_enabled=True, _ats_scope={}, _ats_events=[], _ats_policies={},
                _ats_path=Path(directory) / 'ats-scopes.json', _ats_store={'schema': 1, 'characters': {}},
                _world_bound=lambda w: True, _world_pcs={id(writer): (writer, 5)},
                world=SimpleNamespace(_queue=lambda uid, f: queued.append((uid, f)), _announce=lambda: None),
                realm=SimpleNamespace(settings=SimpleNamespace(save=saved.append),
                                      bound_account=lambda w, g: None),
                run_sync_hooks=lambda name, *args: published.append((name, args)),
                _companion_spells={'spells': [dict(id='energy_bolt', classic_key=dict(value=3)),
                                              dict(id='shield', classic_key=dict(value=4))]})
            frame = lambda f2: SimpleNamespace(payload=pb.encode_bytes(1, self_cfg) + pb.encode_bytes(2, f2))
            self.assertFalse(ats._ats_settings_frame(ctx, writer, None, None, frame(self_ats), None))
            signal = SimpleNamespace(operation='ats-select', args=('companion',))
            result = ats._ats_ui_signal(ctx, writer, 5, signal, dict(event_seq=4, ats_epoch=2))
            self.assertEqual(result['status'], 'SUPPLIED')
            wire = queued[-1][1]
            self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x4ED7)
            with pb.parse_message(wire[4:-2]) as message:
                f1, f2 = bytes(message.occurrences(1)[0].value), bytes(message.occurrences(2)[0].value)
            self.assertEqual((f1, f2), (self_cfg.hex().encode(), self_ats.hex().encode()))
            self.assertEqual(published[-1][1][1], 'ats-apply')
            self.assertEqual(published[-1][1][2]['event_seq'], 4)
            # Save while the companion scope is shown: stored as companion, SELF kept.
            self.assertTrue(ats._ats_settings_frame(ctx, writer, None, None, frame(mate_ats), None))
            row = json.loads(ctx._ats_path.read_text())['characters']['5']
            self.assertEqual((row['companion_ats'], row['self_ats']), (mate_ats.hex(), self_ats.hex()))
            with pb.parse_message(saved[-1].raw) as message:
                self.assertEqual(bytes(message.occurrences(2)[0].value), self_ats)
            policy = ats._ats_policy(ctx, None, 5)
            self.assertEqual(policy['attack_spells'], ['energy_bolt'])
            # Reconnect: a fresh login starts in SELF scope; companion is restored on select.
            ctx._ats_scope.clear()
            ats._ats_ui_signal(ctx, writer, 5, signal, {})
            with pb.parse_message(queued[-1][1][4:-2]) as message:
                self.assertEqual(bytes(message.occurrences(2)[0].value), mate_ats.hex().encode())

    def test_owner_edits_member_companion_setting_then_restores(self):
        import asyncio
        from tools.local_original_session import ats_config_codec as codec
        from tools.local_original_session import world_feature_companion_ats as ats
        from tools.local_entry_server import protobuf as pb
        owner_cfg = codec.wrap_blob(b'\x08\x01')
        owner_ats = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=30.0))
        member_self = codec.wrap_blob(codec.build_ats(buff_spells=(4,)))
        edited, late = (codec.wrap_blob(codec.build_ats(sequence_spells=(3,), hp_percent=v)) for v in (60.0, 70.0))
        saved, queued, published = [], [], []

        def fields(wire):
            with pb.parse_message(wire[4:-2]) as message:
                return [bytes(f.value) for f in message.occurrences(1)], [bytes(f.value) for f in message.occurrences(2)]

        def spells(wire):
            with pb.parse_message(wire[4:-2]) as message:
                rows = [bytes(f.value) for f in message.occurrences(1)]
            result = {}
            for row in rows:
                with pb.parse_message(row) as child:
                    result[child.occurrences(1)[0].value] = child.occurrences(2)[0].value
            return result
        with tempfile.TemporaryDirectory() as directory:
            writer = object()
            actor = SimpleNamespace(owner_ref=SimpleNamespace(uid=5), ref=SimpleNamespace(uid=(7 << 32) | 900),
                                    character_id=9, record=SimpleNamespace(learned_spells=(0, 3, 4)))
            ctx = SimpleNamespace(_ats_enabled=True, _ats_scope={}, _ats_edit={}, _ats_events=[], _ats_policies={},
                _ats_path=Path(directory) / 'ats-scopes.json', _ats_store={'schema': 1, 'characters': {
                    '9': {'self_config': owner_cfg.hex(), 'self_ats': member_self.hex()}}},
                _world_bound=lambda w: True, _world_pcs={id(writer): (writer, 5)},
                _world_magic=SimpleNamespace(states={5: SimpleNamespace(learned={1})}),
                world=SimpleNamespace(_queue=lambda uid, f: queued.append((uid, f)), _announce=lambda: None,
                                      companions=SimpleNamespace(active={9: actor}),
                                      companion_looks={9: dict(name='SoloMage')}),
                realm=SimpleNamespace(settings=SimpleNamespace(save=saved.append, saved_raw=lambda: None),
                                      bound_account=lambda w, g: None),
                run_sync_hooks=lambda name, *args: published.append((name, args)))
            frame = lambda f2: SimpleNamespace(payload=pb.encode_bytes(1, owner_cfg) + pb.encode_bytes(2, f2))
            row = lambda uid: json.loads(ctx._ats_path.read_text())['characters'][str(uid)]
            # The owner's own save first (SELF scope, ordinary route continues).
            self.assertFalse(ats._ats_settings_frame(ctx, writer, None, None, frame(owner_ats), None))
            load = SimpleNamespace(operation='settings-load', actor_uid=900, args=())
            result = ats._ats_ui_signal(ctx, writer, 5, load, dict(event_seq=11, ats_epoch=3))
            self.assertEqual(result, dict(status='EDIT_STARTED', member=9))
            noti, spell = queued[-2][1], queued[-1][1]
            self.assertEqual(fields(noti), ([owner_cfg.hex().encode()], [codec.loadable_ats(member_self).hex().encode()]))
            self.assertEqual(int.from_bytes(spell[2:4], 'little'), 0x4E60)
            self.assertEqual(spells(spell), {0: 1, 3: 1, 4: 1, 1: 0})
            request = published[-1][1][2]
            self.assertEqual((published[-1][1][1], request['event_seq'], request['member_id']), ('ats-edit-apply', 11, 9))
            self.assertEqual(bytes.fromhex(request['label_hex']).decode(), '동료: SoloMage')
            # An autosave still carrying the owner's own f2 is not a member save.
            self.assertTrue(ats._ats_settings_frame(ctx, writer, None, None, frame(owner_ats), None))
            self.assertNotIn('companion_ats', row(9))
            # Save while editing: the member's companion setting; owner + sidecar unchanged.
            self.assertTrue(ats._ats_settings_frame(ctx, writer, None, None, frame(edited), None))
            self.assertEqual((row(9)['companion_ats'], row(9)['self_ats'], row(5)['self_ats']),
                             (edited.hex(), member_self.hex(), owner_ats.hex()))
            self.assertEqual(saved, [])  # member edit never rewrites the account sidecar
            # Close: the owner's 4ED7 and spell list come back.
            close = SimpleNamespace(operation='ats-edit-close', actor_uid=0, args=())
            self.assertEqual(ats._ats_ui_signal(ctx, writer, 5, close, {})['status'], 'RESTORING')
            self.assertEqual(fields(queued[-2][1])[1], [codec.loadable_ats(owner_ats).hex().encode()])
            self.assertEqual(spells(queued[-1][1]), {1: 1, 0: 0, 3: 0, 4: 0})
            # Duplicate close while restoring still delivers the owner's load.
            self.assertEqual(ats._ats_ui_signal(ctx, writer, 5, close, {})['status'], 'RESTORING')
            self.assertEqual(fields(queued[-2][1]), ([owner_cfg.hex().encode()], [codec.loadable_ats(owner_ats).hex().encode()]))
            # A late Save composed before the restore was parsed still belongs to the member.
            self.assertTrue(ats._ats_settings_frame(ctx, writer, None, None, frame(late), None))
            self.assertEqual((row(9)['companion_ats'], row(5)['self_ats']), (late.hex(), owner_ats.hex()))
            restored = SimpleNamespace(operation='ats-edit-restored', actor_uid=0, args=())
            self.assertEqual(ats._ats_ui_signal(ctx, writer, 5, restored, {})['status'], 'RESTORED')
            # No server edit remains, but the DLL may still await its load.
            self.assertEqual(ats._ats_ui_signal(ctx, writer, 5, close, {}), dict(status='NO_EDIT', supplied=True))
            self.assertEqual(fields(queued[-2][1]), ([owner_cfg.hex().encode()], [codec.loadable_ats(owner_ats).hex().encode()]))
            mine = codec.wrap_blob(codec.build_ats(hp_percent=40.0))
            self.assertFalse(ats._ats_settings_frame(ctx, writer, None, None, frame(mine), None))
            self.assertEqual((row(9)['companion_ats'], row(5)['self_ats']), (late.hex(), mine.hex()))
            # Disconnect while editing: nothing of the edit survives for the owner.
            ats._ats_ui_signal(ctx, writer, 5, load, {})
            self.assertEqual(fields(queued[-2][1])[1], [codec.loadable_ats(late).hex().encode()])  # saved companion setting
            asyncio.run(ats._ats_after_leave(ctx, writer))
            self.assertEqual((ctx._ats_edit, row(5)['self_ats']), ({}, mine.hex()))
            self.assertEqual(row(5)['respell'], [0, 3, 4])  # erased again at the next entry
            # Without any known owner CharacterConfig the edit is refused with a notice.
            ctx._ats_store['characters']['5'].pop('self_config')
            refused = ats._ats_ui_signal(ctx, writer, 5, load, dict(event_seq=12))
            self.assertEqual(refused['status'], 'REFUSED')
            self.assertEqual(int.from_bytes(queued[-1][1][2:4], 'little'), 0x4EEA)
            self.assertEqual(published[-1][1][1], 'ats-cancel')


    def test_member_edit_f1_never_reaches_owner_store_or_sidecar(self):
        from unittest.mock import patch
        from tools.local_entry_server import protobuf as pb
        from tools.local_original_session import ats_config_codec as codec
        from tools.local_original_session import ats_config_codec_tests as samples
        from tools.local_original_session import settings
        from tools.local_original_session import world_feature_companion_ats as ats

        owner_config = samples.CAPTURED_OWNER_CONFIG
        owner_ats = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=30))
        member_ats = samples.CAPTURED_COMPANION_ATS
        member_config = codec.wrap_blob(codec.field(2, 2, codec.field(1, 2, b'1.0.0'))
                                        + codec.field(88, 2, b'member UI preferences'))
        owner_row = dict(self_config=owner_config.hex(), self_ats=owner_ats.hex(), unknown='keep')
        member_row = dict(self_config=codec.wrap_blob(b'').hex(), self_ats=member_ats.hex())
        load = SimpleNamespace(operation='settings-load', actor_uid=900, args=())

        def noti_config(queued):
            wire = next(wire for _, wire in reversed(queued)
                        if int.from_bytes(wire[2:4], 'little') == 0x4ED7)
            with pb.parse_message(wire[4:-2]) as msg:
                return tuple(codec.read_noti_field(bytes(msg.occurrences(n)[0].value)) for n in (1, 2))

        for phase in ('open', 'restoring'):
            for incoming in ('owner-f2', 'missing-f2', 'member-f2'):
                with self.subTest(phase=phase, incoming=incoming), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)
                    sidecar = settings.SettingsStore(path / 'settings.bin',
                        '00000000-0000-4000-8000-000000000005', profile_path=path / 'characters.json')
                    body = pb.encode_bytes(1, owner_config) + pb.encode_bytes(2, owner_ats)
                    sidecar.save(settings.parse(body))
                    original_sidecar = sidecar.path.read_bytes()
                    queued, writer = [], object()
                    actor = SimpleNamespace(owner_ref=SimpleNamespace(uid=5), ref=SimpleNamespace(uid=900),
                        character_id=9, record=SimpleNamespace(learned_spells=()))
                    ctx = SimpleNamespace(_ats_enabled=True, _ats_scope={}, _ats_edit={},
                        _ats_events=[], _ats_policies={}, _ats_path=path / 'ats-scopes.json',
                        _ats_store={'schema': 1, 'characters': {'5': dict(owner_row), '9': dict(member_row)}},
                        _world_bound=lambda w: True, _world_pcs={id(writer): (writer, 5)},
                        world=SimpleNamespace(_queue=lambda uid, f: queued.append((uid, f)),
                            _announce=lambda: None, companions=SimpleNamespace(active={9: actor})),
                        realm=SimpleNamespace(settings=sidecar, store=SimpleNamespace(path=path / 'characters.json'),
                            bound_account=lambda w, g: None), run_sync_hooks=lambda *args: None)
                    ats._ats_save_store(ctx)
                    self.assertEqual(ats._ats_ui_signal(ctx, writer, 5, load, {})['status'], 'EDIT_STARTED')
                    self.assertEqual(noti_config(queued),
                        (codec.companion_character_config(owner_config), codec.loadable_ats(member_ats)))
                    # The native item UIDs 80/77/79 are absent in this first load,
                    # whose exact field preservation is covered by codec regressions.
                    if phase == 'restoring':
                        self.assertEqual(ats._ats_edit_close(ctx, writer, 5, {})['status'], 'RESTORING')
                        self.assertEqual(noti_config(queued), (owner_config, codec.loadable_ats(owner_ats)))
                    # Use different f1 even for an owner-f2 echo: it is still tainted.
                    payload = pb.encode_bytes(1, member_config)
                    if incoming != 'missing-f2':
                        payload += pb.encode_bytes(2, owner_ats if incoming == 'owner-f2' else member_ats)
                    frame = SimpleNamespace(payload=payload)
                    consumed = ats._ats_settings_frame(ctx, writer, None, None, frame, None)
                    # Mirror the ordinary route: a False return would overwrite the sidecar.
                    if not consumed:
                        sidecar.save(settings.parse(payload))
                    self.assertTrue(consumed)
                    self.assertEqual(ctx._ats_store['characters']['5'], owner_row)
                    persisted = json.loads(ctx._ats_path.read_text(encoding='utf-8'))['characters']
                    self.assertEqual(persisted['5'], owner_row)
                    self.assertEqual(sidecar.path.read_bytes(), original_sidecar)
                    self.assertEqual(sidecar.committed, 1)
                    if incoming == 'owner-f2' and phase == 'restoring':
                        self.assertNotIn(id(writer), ctx._ats_edit)  # existing echo acknowledgement
                    else:
                        self.assertEqual(ctx._ats_edit[id(writer)]['phase'], phase)
                    if incoming == 'member-f2':
                        self.assertEqual(persisted['9'], dict(member_row,
                            companion_config=member_config.hex(), companion_ats=member_ats.hex()))
                        # Original owner f1 is restored even after this saved member f1.
                        self.assertEqual(ats._ats_edit_close(ctx, writer, 5, {})['status'], 'RESTORING')
                        self.assertEqual(noti_config(queued), (owner_config, codec.loadable_ats(owner_ats)))
                        # A real store reload/reopen must send member preferences, not owner f1.
                        with patch.dict('os.environ', SL_COMPANION='1'):
                            ats._ats_initialize(ctx)
                        ats._ats_ui_signal(ctx, writer, 5, load, {})
                        self.assertEqual(noti_config(queued), (member_config, codec.loadable_ats(member_ats)))
                        self.assertEqual(sidecar.path.read_bytes(), original_sidecar)
                    else:
                        self.assertEqual(persisted['9'], member_row)


class BridgeIngestTests(unittest.TestCase):
    def context(self, *, subscribed=True):
        from tools.local_original_session import world_feature_companion_bridge as bridge
        from tools.local_original_session import world_feature_companion_ats as ats
        writer, queued, published = object(), [], []

        async def dispatch(fn, *args):
            return fn(*args)

        ctx = SimpleNamespace(_world_pcs={id(writer): (writer, 5)}, _ats_enabled=False,
            world=SimpleNamespace(runtime=SimpleNamespace(dispatch_now=dispatch),
                companions=SimpleNamespace(active={}), _queue=lambda u, f: queued.append((u, f)),
                _announce=lambda: None),
            collect_sync_hooks=lambda name, *args: ())

        def hooks(name, *args):
            if name == 'companion_ui_refused' and subscribed:
                ats._ats_ui_refused(ctx, *args)
            elif name == 'companion_bridge_publish':
                published.append(args)

        ctx.run_sync_hooks = hooks
        bridge._bridge_initialize(ctx)
        return ctx, writer, queued, published

    def write_signal(self, directory, *, operation='ats-select', actor=0, seq=3):
        from tools.local_original_session import companion_signals as cs
        body = Path(directory, f'companion-signal-{seq}.bin')
        body.write_bytes(cs.encode_signal(operation, actor, ('self',) if operation == 'ats-select' else ()))
        path = Path(directory, f'companion-signal-{seq}.json')
        path.write_text(json.dumps(dict(schema='companion-native-signal-v1', transport='LOCAL_IPC',
            pid=1, birth=2, event_seq=seq, ats_epoch=7, body_file=body.name)), encoding='utf-8')
        return path, body

    def test_ats_failures_cancel_exact_event_once_and_notice_even_without_ats_feature(self):
        from unittest.mock import Mock
        from tools.local_original_session import world_feature_companion_bridge as bridge
        for subscribed, failure in ((True, ValueError('CURRENT_ACTOR_REQUIRED')),
                (True, OSError('SETTINGS_READ_FAILED')), (True, RuntimeError('CALLBACK_FAILED')),
                (True, None), (False, None)):
            with self.subTest(subscribed=subscribed, failure=failure):
                ctx, writer, queued, published = self.context(subscribed=subscribed)
                if failure:
                    ctx.collect_sync_hooks = Mock(side_effect=failure)
                signal = SimpleNamespace(operation='settings-load', actor_uid=99)
                result = bridge._bridge_dispatch(ctx, writer, 5, signal, dict(event_seq=12, ats_epoch=7))
                self.assertIn(result['status'], ('REFUSED', 'FAILED', 'UNHANDLED'))
                self.assertEqual(len(published), 1)
                self.assertEqual((published[0][1], published[0][2]['event_seq'],
                                  published[0][2]['ats_epoch']), ('ats-cancel', 12, 7))
                self.assertEqual([(u, int.from_bytes(f[2:4], 'little')) for u, f in queued], [(5, 0x4EEA)])

    def test_ats_own_refusal_feedback_is_not_duplicated_by_bridge(self):
        from tools.local_original_session import world_feature_companion_bridge as bridge
        from tools.local_original_session import world_feature_companion_ats as ats
        ctx, writer, queued, published = self.context()
        ctx._ats_enabled, ctx._ats_store, ctx._ats_events = True, {'characters': {}}, []
        ctx.collect_sync_hooks = lambda name, *args: (ats._ats_ui_signal(ctx, *args),)
        signal = SimpleNamespace(operation='ats-select', actor_uid=0, args=('self',))
        bridge._bridge_dispatch(ctx, writer, 5, signal, dict(event_seq=9, ats_epoch=4))
        self.assertEqual((len(published), len(queued)), (1, 1))

    def test_registry_without_ats_publishes_cancel_and_declares_notice_opcode(self):
        from types import MethodType
        from tools.local_original_session import world_feature_companion_bridge as bridge, world_registry
        from tools.local_original_session.world_bridge import Context
        ctx, writer, queued, published = self.context()
        ctx._world_registry = world_registry.build_registry((bridge,))
        for name, fn in ctx._world_registry.methods.items():
            setattr(ctx, name, MethodType(fn, ctx))
        ctx.collect_sync_hooks = MethodType(Context.collect_sync_hooks, ctx)
        ctx.run_sync_hooks = MethodType(Context.run_sync_hooks, ctx)
        ctx._companion_bridge_host = SimpleNamespace(installed=True,
            publish_request=lambda request: (published.append(request) or len(published), True))
        self.assertNotIn('companion_ui_signal', ctx._world_registry.hooks)
        self.assertNotIn('companion_ui_refused', ctx._world_registry.hooks)
        self.assertIn(0x4EEA, ctx._world_registry.outgoing_opcodes)
        result = bridge._bridge_dispatch(ctx, writer, 5,
            SimpleNamespace(operation='ats-select', actor_uid=0), dict(event_seq=9, ats_epoch=4))
        self.assertEqual(result['status'], 'UNHANDLED')
        self.assertEqual(published, [dict(command='ats-cancel', event_seq=9, ats_epoch=4)])
        self.assertEqual(len(queued), 1)

    def test_ats_close_without_saved_owner_config_refuses_without_inventing_a_load(self):
        from tools.local_original_session import world_feature_companion_bridge as bridge
        from tools.local_original_session import world_feature_companion_ats as ats
        ctx, writer, queued, published = self.context()
        ctx._ats_enabled, ctx._ats_edit, ctx._ats_store = True, {}, {'characters': {}}
        ctx.realm = SimpleNamespace(settings=None)
        ctx.collect_sync_hooks = lambda name, *args: (ats._ats_ui_signal(ctx, *args),)
        result = bridge._bridge_dispatch(ctx, writer, 5,
            SimpleNamespace(operation='ats-edit-close', actor_uid=0), dict(event_seq=12, ats_epoch=7))
        self.assertEqual(result['error'], 'SELF_CHARACTER_CONFIG_UNKNOWN')
        self.assertEqual([int.from_bytes(f[2:4], 'little') for _, f in queued], [0x4EEA])
        self.assertEqual(published[0][2]['event_seq'], 12)  # no initial edit event can be reconstructed

    def test_ats_close_unsent_owner_load_cancels_matching_close_event_once(self):
        from tools.local_original_session import ats_config_codec as codec
        from tools.local_original_session import world_feature_companion_ats as ats
        from tools.local_original_session import world_feature_companion_bridge as bridge
        for failure in ('missing-config', 'queue-failure', 'rejected'):
            with self.subTest(failure=failure):
                ctx, writer, queued, published = self.context()
                ctx._ats_enabled, ctx._ats_edit, ctx._ats_store = True, {}, {'characters': {}}
                ctx.realm = SimpleNamespace(settings=None)
                meta = dict(event_seq=24, ats_epoch=8)
                signal = SimpleNamespace(operation='ats-edit-close', actor_uid=0)
                if failure == 'queue-failure':
                    ctx._ats_store['characters']['5'] = dict(self_config=codec.wrap_blob(b'').hex())

                    def queue(uid, frame):
                        if int.from_bytes(frame[2:4], 'little') == 0x4ED7:
                            raise OSError('OWNER_LOAD_FAILED')
                        queued.append((uid, frame))

                    ctx.world._queue = queue
                if failure == 'rejected':
                    ctx.collect_sync_hooks = lambda name, *args: (dict(status='REJECTED'),)
                    result = bridge._bridge_dispatch(ctx, writer, 5, signal, meta)
                else:
                    result = ats._ats_edit_close(ctx, writer, 5, meta)
                    # Transport feedback must not send a second cancellation.
                    bridge._bridge_refused(ctx, writer, 5, signal, meta, result)
                self.assertIn(result['status'], ('REFUSED', 'FAILED', 'REJECTED'))
                self.assertEqual(published, [(5, 'ats-cancel', ats._ats_request('ats-cancel', meta))])
                self.assertEqual([int.from_bytes(f[2:4], 'little') for _, f in queued], [0x4EEA])
                self.assertEqual(ctx._ats_edit, {})

    def test_item_storage_failure_keeps_existing_exception_semantics(self):
        from unittest.mock import Mock
        from tools.local_original_session import world_feature_companion_bridge as bridge
        ctx, writer, queued, published = self.context()
        ctx.collect_sync_hooks = Mock(side_effect=OSError('TRANSFER_PARTIAL'))
        with self.assertRaisesRegex(OSError, 'TRANSFER_PARTIAL'):
            bridge._bridge_dispatch(ctx, writer, 5,
                SimpleNamespace(operation='item-give', actor_uid=99), {})
        self.assertEqual((queued, published), ([], []))

    def test_no_owner_cancels_but_notice_is_limited_to_a_single_bound_owner(self):
        import asyncio
        from tools.local_original_session import world_feature_companion_bridge as bridge
        for count in (0, 1, 2):
            with self.subTest(bound_owners=count), tempfile.TemporaryDirectory() as directory:
                ctx, writer, queued, published = self.context()
                if count == 0:
                    ctx._world_pcs.clear()
                elif count == 2:
                    other = object()
                    ctx._world_pcs[id(other)] = (other, 6)
                self.write_signal(directory, operation='settings-load', actor=99)
                self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
                self.assertEqual(ctx._bridge_signals[-1]['status'], 'NO_OWNER')
                self.assertEqual((published[0][1], published[0][2]['event_seq'],
                                  published[0][2]['ats_epoch']), ('ats-cancel', 3, 7))
                self.assertEqual(len(queued), 1 if count == 1 else 0)
                self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
                self.assertEqual(len(published), 1)

    def test_ipc_temporary_json_and_body_read_failures_retry_without_replaying_success(self):
        import asyncio
        from unittest.mock import patch
        from tools.local_original_session import world_feature_companion_bridge as bridge
        with tempfile.TemporaryDirectory() as directory:
            ctx, _, _, _ = self.context()
            calls = []
            ctx.collect_sync_hooks = lambda name, *args: calls.append(args) or (dict(status='SUPPLIED'),)
            path, body = self.write_signal(directory)
            raw = path.read_text(encoding='utf-8')
            path.write_text('{', encoding='utf-8')
            self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
            self.assertNotIn(3, ctx._bridge_seen)
            path.write_text(raw, encoding='utf-8')
            with patch.object(Path, 'read_bytes', side_effect=PermissionError('WRITER_STILL_OPEN')):
                self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
            self.assertNotIn(3, ctx._bridge_seen)
            self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 1)
            self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(ctx._bridge_read_attempts, {})

    def test_ipc_exhausted_reads_and_permanent_rejections_are_terminal(self):
        import asyncio
        from tools.local_original_session import world_feature_companion_bridge as bridge
        for reason in ('read', 'schema', 'identity', 'decode', 'metadata'):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                ctx, _, _, _ = self.context()
                path, body = self.write_signal(directory)
                if reason == 'read':
                    body.unlink()
                elif reason == 'decode':
                    body.write_bytes(b'\xff')
                else:
                    meta = json.loads(path.read_text(encoding='utf-8'))
                    if reason == 'schema':
                        meta['schema'] = 'WRONG'
                    elif reason == 'identity':
                        ctx._companion_bridge_host = SimpleNamespace(identity={'pid': 99, 'birth': 2})
                    else:
                        meta['event_seq'] = 'invalid'
                    path.write_text(json.dumps(meta), encoding='utf-8')
                for _ in range(bridge.READ_ATTEMPTS if reason == 'read' else 1):
                    self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
                self.assertIn(3, ctx._bridge_seen)
                errors = len(ctx._bridge_errors)
                self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
                self.assertEqual(len(ctx._bridge_errors), errors)

    def test_ipc_signal_files_are_dispatched_once_to_the_selected_owner(self):
        import asyncio
        from tools.local_original_session import companion_signals as cs
        from tools.local_original_session import world_feature_companion_bridge as bridge
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'companion-signal-3.bin').write_bytes(cs.encode_signal('ats-select', 0, ('self',)))
            Path(directory, 'companion-signal-3.json').write_text(json.dumps(dict(
                schema='companion-native-signal-v1', pid=1, birth=2, event_seq=3, ats_epoch=1,
                operation='ats-select', actor_uid=0, body_file='companion-signal-3.bin',
                transport='LOCAL_IPC', status='QUEUED', effect='UNKNOWN')))
            seen, writer = [], object()

            async def dispatch(fn, *args):
                return fn(*args)
            ctx = SimpleNamespace(_world_pcs={id(writer): (writer, 5)},
                world=SimpleNamespace(runtime=SimpleNamespace(dispatch_now=dispatch),
                                      companions=SimpleNamespace(active={})),
                collect_sync_hooks=lambda name, *args: seen.append(args) or (dict(status='SUPPLIED'),))
            bridge._bridge_initialize(ctx)
            ctx._companion_bridge_host = None
            self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 1)
            self.assertEqual(asyncio.run(bridge._bridge_ingest(ctx, Path(directory))), 0)
            self.assertEqual(seen[0][1], 5)
            self.assertEqual(seen[0][3]['event_seq'], 3)
            self.assertEqual(ctx._bridge_signals[-1]['status'], 'SUPPLIED')
            self.assertFalse(Path(directory, 'companion-signal-3.json').exists())

    def test_publish_without_host_is_recorded_unattached(self):
        import os
        from tools.local_original_session import world_feature_companion_bridge as bridge
        ctx = SimpleNamespace()
        bridge._bridge_initialize(ctx)
        old = os.environ.pop(bridge.DIRECTORY_ENV, None)
        try:
            bridge._bridge_publish(ctx, 1, 'model', dict(frame=b'x', member=2, revision=1))
        finally:
            if old is not None:
                os.environ[bridge.DIRECTORY_ENV] = old
        self.assertEqual(ctx._bridge_outbox[-1]['status'], 'HOST_UNATTACHED')


if __name__ == '__main__':
    unittest.main()
