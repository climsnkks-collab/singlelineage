"""Companion cast/buff development checks; no game, sockets or user saves."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import MethodType, SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import ats_config_codec as codec
from tools.local_original_session import world_feature_magic as feature
from tools.local_original_session import world_feature_companion as companion_feature
from tools.local_original_session import world_magic as rules
from tools.local_original_session import world_magic_tests as player_fixture
from tools.local_original_session.world_feature_companion import CompanionMagic


class CompanionSupportSpellTests(unittest.TestCase):
    def setUp(self):
        self.player = player_fixture.WorldConsumerTests()
        self.player.setUp()
        self.addCleanup(self.player.doCleanups)
        self.view, self.ctx = self.player.view, self.player.ctx
        self.actor = self.player.fixture.actor
        self.record = self.actor.record
        self.entity = self.view.entities.resolve(self.actor.ref)
        self.owner = self.view.entities.get(1)
        self.record.level = 30
        self.record.mp = self.record.max_mp = 314
        self.record.learned_spells = (0, 2, 3, 7, 11, 13, 20, 25)
        self.record.combat_mode, self.record.movement_mode = 'ASSIST', 'HOLD'
        root = Path(__file__).parent / 'data/companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        self.magic = CompanionMagic(self.view, read('mage_spells'), read('mage_growth'),
            read('ai_policy'), {2: (8, 7, 16, 18, 8, 18)}, ctx=self.ctx)
        self.view.companion_ai.magic = self.magic
        self.magic.equipment_uid = lambda rt, kind: 101 if kind == 'weapon' else 102
        self.owner_weapon = 201
        self.ctx._world_magic_weapon_uid = lambda uid: self.owner_weapon
        self.ctx._world_magic_buff_ui = True
        self.player.magic.state(1).learned.clear()  # Receiving never grants learning.
        self.player.magic.state(1).next_cast_at = 999
        from tools.local_original_session import world_registry
        self.ctx._world_registry = world_registry.build_registry((feature, companion_feature))
        self.ctx._companion_enabled = True
        self.ctx._companion_magic_buff_target = MethodType(
            companion_feature._companion_magic_buff_target, self.ctx)
        self.configure()

    def configure(self, **options):
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(**options)),
            {s.key: s.name for s in self.magic.rules.values()})
        self.magic.policy_for = lambda _: policy

    def decision(self, now):
        self.player.fixture.now = now
        return self.magic.step(self.actor, self.entity, self.owner, None, now, False)

    def casts(self):
        return [event for event in self.magic.events if event['spell'] in self.magic.rules]

    def test_default_support_heal_attack_display_reaches_nearby_pc_without_gate(self):
        self.view.update_pc(9, 0, self.entity.x, self.entity.y + 1)
        self.configure(buff_spells=(2,), sequence_spells=(0, 3))
        enemy = self.player.enemy()
        self.actor.target = enemy.ref
        self.view.entities.move(enemy.uid, 0, self.entity.x + 1, self.entity.y)
        self.view.companion_ai.owner_attacked(self.owner.ref, enemy.ref, 10)
        self.view.spawner.slot_for(enemy.uid)[1].hp = 1000
        self.record.hp = 1
        for index, (key, target, gfx) in enumerate(((2, self.entity, 221), (0, self.entity, 744), (3, enemy, 167))):
            with self.subTest(key=key), patch.dict('os.environ', SL_SPELL_EXP='0'):
                self.view.drain(1)
                self.view.drain(9)
                before = self.record.mp
                self.assertTrue(self.magic.cast(self.actor, self.entity, target,
                    self.magic.engine.spells[key].name, 10 + index))
                wires = self.view.drain(1)
                actions = self.player.fixture.decoded(wires, 0x4e31, 2, self.entity.uid)
                effects = self.player.fixture.decoded(wires, 0x4ed8, 1, target.uid)
                from tools.local_original_session.hunt_bot import scalar
                self.assertEqual(len(actions), 1)
                self.assertEqual(scalar(actions[0], 3), target.uid)
                self.assertEqual(scalar(actions[0], 13), 1)
                self.assertEqual([scalar(row, 2) for row in effects], [gfx])
                nearby = self.view.drain(9)
                self.assertEqual(len(self.player.fixture.decoded(
                    nearby, 0x4e31, 2, self.entity.uid)), 1)
                self.assertEqual([scalar(row, 2) for row in self.player.fixture.decoded(
                    nearby, 0x4ed8, 1, target.uid)], [gfx])
                self.assertEqual(self.record.mp, before - self.magic.rules[
                    self.magic.engine.spells[key].name].mp)

    def test_two_recipients_have_independent_refresh_weapon_binding_and_owner_hud(self):
        self.configure(buff_spells=(7, 11))
        self.assertTrue(self.decision(10))
        self.assertEqual((self.casts()[-1]['spell'], self.casts()[-1]['target']),
                         ('enchant_weapon', self.entity.uid))
        self.assertTrue(self.decision(11))
        self.assertEqual((self.casts()[-1]['spell'], self.casts()[-1]['target']), ('holy_weapon', 1))
        owner_state = self.player.magic.state(1)
        self.assertEqual(owner_state.weapon_uids[7], 201)
        self.assertEqual(owner_state.buff_sources[7], self.record.character_id)
        self.assertEqual(owner_state.learned, set())
        self.assertEqual(owner_state.next_cast_at, 999)
        self.assertEqual(self.player.state.mp, 100)
        self.assertEqual(set(self.magic.engine.state(2).buffs), {11})
        owner_wires = self.view.drain(1)
        from tools.local_original_session.hunt_bot import scalar
        actions = self.player.fixture.decoded(owner_wires, 0x4e31, 2, self.entity.uid)
        self.assertTrue(any(scalar(row, 3) == self.owner.uid for row in actions))
        self.assertEqual([scalar(row, 2) for row in self.player.fixture.decoded(
            owner_wires, 0x4ed8, 1, self.owner.uid)], [2165])
        from tools.local_original_session.world_item_effects import buff_icon_frame
        self.assertIn(buff_icon_frame(7, 777, 10), owner_wires)
        saved = self.player.saved[-1]
        self.assertEqual(saved['learned'], [])
        self.assertEqual(saved['buffs'], [dict(spell=7, remaining=10, weapon_uid=201, source_uid=2)])
        self.assertFalse(self.decision(12))
        self.owner_weapon = 202
        self.assertTrue(self.decision(13))
        self.assertEqual(owner_state.weapon_uids[7], 202)
        self.assertTrue(self.decision(22))  # Owner's 10s timer has its own refresh lead.
        self.assertEqual(self.casts()[-1]['target'], 1)
        self.assertEqual(len(self.casts()), 4)
        self.assertEqual(self.record.mp, 314 - self.magic.rules['enchant_weapon'].mp
                         - 3 * self.magic.rules['holy_weapon'].mp)
        self.player.magic.expire(32)
        self.ctx._world_magic_sync_icons(1, 32)
        self.assertNotIn(7, owner_state.buff_sources)
        self.assertIn(buff_icon_frame(7, 777, 0, remove=True), self.view.drain(1))

    def test_self_only_rejected_and_pledge_target_needs_no_clan(self):
        for key in (2, 11, 13, 20):
            self.configure(buff_spells=(key,))
            before = self.record.mp
            self.assertFalse(self.magic.cast(self.actor, self.entity, self.owner,
                self.magic.engine.spells[key].name, 10))
            self.assertEqual(self.record.mp, before)
        self.configure(buff_spells=(25,))
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.owner,
            'enchant_dexterity', 10))
        self.assertEqual(self.player.magic.dexterity_bonus(1, 10), 5)
        self.assertEqual(self.player.magic.state(1).buff_sources[25], 2)
        self.assertEqual(self.player.magic.state(1).learned, set())

    def prepare_player_cast(self):
        self.player.state.profile = replace(self.player.state.profile, level=30)
        state = self.player.magic.state(1)
        state.learned = {2, 7, 25}
        state.next_cast_at = 0

    def add_pc(self, uid=9):
        from tools.local_original_session.world_pc_response_tests import actor
        self.view.update_pc(uid, 0, self.entity.x, self.entity.y + 1,
            actor_fields=actor(uid, self.entity.x, self.entity.y + 1))
        fields = dict(self.player.state.status_fields)
        fields[1] = uid
        self.view.bind_pc(uid, replace(self.player.state.profile), fields)
        self.view._refresh(1)
        return self.view.entities.get(uid)

    def add_companion(self):
        from tools.local_original_session.world_companion import CompanionRecord
        record = CompanionRecord(3, 1, 'development-fixture', hp=12, max_hp=12,
            mp=20, max_mp=20, movement_mode='HOLD', combat_mode='PASSIVE')
        self.view.companions.register(record, roster={
            1: dict(account_id='development-fixture', class_id=1),
            3: dict(account_id='development-fixture', class_id=3)})
        self.view.companion_profiles[3] = replace(self.view.companion_profiles[2])
        self.view.companion_looks[3] = dict(self.view.companion_looks[2], name='OtherMage')
        self.view.companion_max_active = 2  # fixture exercises the existing multi-member configuration.
        member = self.view.summon_companion(3, 1)
        return member, self.view.entities.resolve(member.ref)

    def test_player_pledge_buff_other_pc_cost_effect_icons_and_restore(self):
        self.prepare_player_cast()
        target = self.add_pc()
        recipient = self.player.magic.state(target.uid)
        recipient.next_cast_at = 999
        with patch.object(self.ctx, 'collect_sync_hooks', wraps=self.ctx.collect_sync_hooks) as hooks:
            self.ctx._world_magic_cast(1, 25, target.uid, 10)
        self.assertFalse(any(call.args[0] == 'magic_target_relation' for call in hooks.call_args_list))
        self.assertEqual(self.player.state.mp, 100 - self.player.magic.spells[25].mp)
        self.assertEqual(self.player.magic.state(1).buffs, {})
        self.assertEqual(self.player.magic.state(1).next_cast_at, 11)
        self.assertEqual(recipient.next_cast_at, 999)
        self.assertEqual(recipient.buff_sources, {25: 1})
        self.assertEqual(recipient.learned, set())
        saved = next(row for row in reversed(self.player.saved) if row['uid'] == target.uid)
        fresh = rules.PlayerMagic(rules.load_catalog())
        restored = fresh.restore(target.uid, rules._row(json.loads(json.dumps(saved))),
                                 100, wall=saved['saved_at'] + 2)
        self.assertEqual(restored.buffs, {25: 108})
        self.assertEqual(fresh.dexterity_bonus(target.uid, 100), 5)
        self.assertEqual(fresh.dexterity_bonus(target.uid, 108), 0)
        from tools.local_original_session.world_item_effects import buff_icon_frame
        wires = self.view.drain(target.uid)
        self.assertIn(buff_icon_frame(25, feature.SPELL_BUFF_ICONS[25], 10), wires)
        self.assertTrue(self.player.fixture.decoded(wires, 0x4ed8, 1, target.uid))
        self.assertFalse(self.ctx._world_magic_icons.get((1, 25)))

    def test_player_to_companion_buff_uses_recipient_engine_record_and_profile(self):
        self.prepare_player_cast()
        before_mp = self.record.mp
        self.magic.engine.state(2).next_cast_at = 999
        with patch.object(self.view, '_save_companion') as save:
            self.ctx._world_magic_cast(1, 25, self.entity.uid, 10)
        save.assert_called_once_with(1)
        self.assertEqual(self.record.mp, before_mp)
        self.assertEqual(self.player.magic.state(1).buffs, {})
        self.assertEqual(self.magic.engine.state(2).next_cast_at, 999)
        self.assertEqual(self.magic.engine.state(2).buff_sources, {25: 1})
        profile = self.view.companion_profiles[2]
        self.assertEqual(self.magic.profile(self.actor, profile, 10).dexterity, profile.dexterity + 5)
        saved = rules._row(json.loads(json.dumps(self.record.equipment['magic_buffs'])))
        fresh = rules.PlayerMagic(rules.load_catalog())
        self.assertEqual(fresh.restore(2, saved, 100, wall=saved['saved_at'] + 2).buff_sources, {25: 1})
        self.assertEqual(fresh.dexterity_bonus(2, 100), 5)
        self.assertEqual(fresh.dexterity_bonus(2, 100 + self.magic.rules['enchant_dexterity'].duration), 0)
        # 4E91 has no actor UID; companion effects must never replace owner HUD icons.
        self.assertNotIn((1, 25), self.ctx._world_magic_icons)
        self.assertTrue(self.player.fixture.decoded(self.view.drain(1), 0x4ed8, 1, self.entity.uid))

    def test_companion_other_pc_and_sibling_follow_same_received_buff_rule(self):
        self.configure(buff_spells=(25,))
        target = self.add_pc()
        self.assertTrue(self.magic.cast(self.actor, self.entity, target, 'enchant_dexterity', 10))
        self.assertEqual(self.player.magic.state(target.uid).buff_sources, {25: 2})
        sibling, entity = self.add_companion()
        before = sibling.record.mp
        with patch.object(self.view, '_save_companion') as save:
            self.assertTrue(self.magic.cast(self.actor, self.entity, entity, 'enchant_dexterity', 11))
        self.assertEqual(self.magic.engine.state(3).buff_sources, {25: 2})
        self.assertEqual(sibling.record.mp, before)
        self.assertEqual(sibling.record.equipment['magic_buffs']['buffs'][0]['source_uid'], 2)
        self.assertEqual(save.call_count, 2)  # recipient and caster each retain their save owner.

    def test_companion_auto_buff_includes_current_sibling_after_self_and_owner(self):
        self.configure(buff_spells=(25,))
        sibling, entity = self.add_companion()
        self.assertTrue(self.decision(10))
        self.assertTrue(self.decision(11))
        self.assertTrue(self.decision(12))
        self.assertEqual([row['target'] for row in self.casts()], [self.entity.uid, 1, entity.uid])
        self.assertEqual(self.magic.engine.state(3).buff_sources, {25: 2})

    def test_player_other_targets_reject_self_only_before_cost_and_stale_recipient(self):
        self.prepare_player_cast()
        target = self.add_pc()
        for recipient in (target, self.entity):
            self.view.entities.move(recipient.uid, self.owner.map_id, self.owner.x, self.owner.y)
            before = self.player.state.mp
            with self.assertRaisesRegex(ValueError, 'MAGIC_SELF_TARGET_REQUIRED'):
                self.ctx._world_magic_cast(1, 2, recipient.uid, 10)
            self.assertEqual(self.player.state.mp, before)
        resolved = self.ctx._world_magic_buff_target(self.entity.uid, 25, 1)
        self.view.companions.die(2, 10)
        with self.assertRaisesRegex(ValueError, 'MAGIC_CURRENT_BUFF_TARGET_REQUIRED'):
            resolved.apply(10)

    def test_received_companion_save_failure_propagates_after_real_caster_debit(self):
        self.prepare_player_cast()
        with patch.object(self.ctx, '_companion_save', create=True,
                side_effect=OSError('recipient save interrupted')) as save:
            with self.assertRaisesRegex(OSError, 'recipient save interrupted'):
                self.ctx._world_magic_cast(1, 25, self.entity.uid, 10)
        save.assert_called_once_with(1)
        self.assertEqual(self.player.state.mp, 100 - self.player.magic.spells[25].mp)
        self.assertEqual(self.player.magic.state(1).next_cast_at, 11)
        self.assertEqual(self.magic.engine.state(2).buff_sources, {25: 1})
        self.assertEqual(self.record.equipment['magic_buffs']['buffs'][0]['source_uid'], 1)

    def test_missing_service_range_los_dead_owner_no_mp_debit(self):
        self.configure(buff_spells=(7,))
        for mode in ('service', 'range', 'los', 'dead', 'weapon'):
            with self.subTest(mode=mode):
                before = self.record.mp
                original = self.ctx.collect_sync_hooks
                with patch.object(self.ctx, 'collect_sync_hooks', side_effect=lambda name, *args:
                        () if mode == 'service' and name == 'magic_service' else original(name, *args)), \
                     patch('tools.local_original_session.npc_ai.local_line_clear', return_value=mode != 'los'):
                    self.view.entities.move(1, 0, self.entity.x + (11 if mode == 'range' else 1), self.entity.y)
                    self.player.state.hp = 0 if mode == 'dead' else 100
                    self.owner.alive = mode != 'dead'
                    self.owner_weapon = 0 if mode == 'weapon' else 201
                    self.assertFalse(self.magic.cast(self.actor, self.entity, self.owner, 'holy_weapon', 10))
                    self.assertEqual(self.record.mp, before)

    def test_received_buff_cold_store_restore_without_learning_and_old_self_compatible(self):
        self.configure(buff_spells=(7,))
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.owner, 'holy_weapon', 10))
        row = self.player.saved[-1]
        # A fresh JSON round trip and cold MagicStore use the ordinary disk format.
        with tempfile.TemporaryDirectory() as directory:
            store = rules.MagicStore(NS(profile=Path(directory) / 'inventory.json'))
            store.save(row)
            cold = rules.MagicStore(NS(profile=Path(directory) / 'inventory.json'))
            new_engine = rules.PlayerMagic(rules.load_catalog())
            restored = new_engine.restore(1, cold.rows[1], 100, wall=row['saved_at'] + 2)
            self.assertEqual(restored.learned, set())
            self.assertEqual(restored.buffs[7], 108)
            self.assertEqual(restored.weapon_uids[7], 201)
            self.assertEqual(restored.buff_sources[7], 2)
            self.ctx._world_magic, self.player.magic = new_engine, new_engine
            self.ctx._world_magic_icons.clear()
            self.ctx._world_magic_sync_icons(1, 100)
            from tools.local_original_session.world_item_effects import buff_icon_frame
            self.assertIn(buff_icon_frame(7, 777, 8), self.view.drain(1))
            old = dict(uid=1, learned=[2], buffs=[dict(spell=2, remaining=10)],
                       reuse_remaining=0, saved_at=0)
            store.save(old)
            self.assertEqual(new_engine.restore(1, old, 0, wall=0).buffs, {2: 10})
            invalid = deepcopy(old)
            invalid['learned'] = []
            with self.assertRaisesRegex(ValueError, 'MAGIC_SAVE_BUFF'):
                store.save(invalid)
            invalid['buffs'][0]['source_uid'] = 2  # Shield remains self-only.
            with self.assertRaisesRegex(ValueError, 'RECEIVED_BUFF_TARGET'):
                store.save(invalid)

    def test_received_json_restore_hud_lifetime_and_old_schema_without_disk(self):
        self.configure(buff_spells=(7,))
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.owner, 'holy_weapon', 10))
        row = rules._row(json.loads(json.dumps(self.player.saved[-1])))
        fresh = rules.PlayerMagic(rules.load_catalog())
        state = fresh.restore(1, row, 100, wall=row['saved_at'] + 2)
        self.assertEqual(state.learned, set())
        self.assertEqual((state.buffs, state.weapon_uids, state.buff_sources),
                         ({7: 108}, {7: 201}, {7: 2}))
        self.ctx._world_magic = fresh
        self.ctx._world_magic_icons.clear()
        self.ctx._world_magic_sync_icons(1, 100)
        from tools.local_original_session.world_item_effects import buff_icon_frame
        self.assertIn(buff_icon_frame(7, 777, 8), self.view.drain(1))
        self.assertEqual(fresh.restore(1, row, 100, wall=row['saved_at'] + 11).buffs, {})
        old = dict(uid=1, learned=[2], buffs=[dict(spell=2, remaining=10)],
                   reuse_remaining=0, saved_at=0)
        self.assertEqual(fresh.restore(1, rules._row(old), 0, wall=0).buffs, {2: 10})
        invalid = deepcopy(old)
        invalid['learned'] = []
        with self.assertRaisesRegex(ValueError, 'MAGIC_SAVE_BUFF'):
            rules._row(invalid)
        for source in (0, True, -1, 1, 0x100000000):
            invalid['buffs'] = [dict(spell=7, remaining=10, source_uid=source)]
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'BUFF_SOURCE'):
                rules._row(invalid)
        invalid['buffs'] = [dict(spell=2, remaining=10, source_uid=2)]
        with self.assertRaisesRegex(ValueError, 'RECEIVED_BUFF_TARGET'):
            rules._row(invalid)
        with self.assertRaisesRegex(ValueError, 'SAVED_SPELL_UNSUPPORTED'):
            fresh.restore(1, invalid, 0, wall=0)


if __name__ == '__main__':
    unittest.main()
