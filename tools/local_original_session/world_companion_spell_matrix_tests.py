"""Lv30/learned38 snapshot unit matrix; direct state/clock is NOT packet PASS."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from tools.local_original_session import world_companion_magic_tests as magic_fixture
from tools.local_original_session import ats_config_codec as codec
from tools.local_original_session.world_feature_companion import CompanionAilments, CompanionMonsterTarget

BASELINE = Path(__file__).resolve().parents[2] / 'work/local_original_session/validation-profiles/manual-test-knight'


class CompanionSpellMatrix(unittest.TestCase):
    def setUp(self):
        self.fixture = magic_fixture.MagicTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for key in ('view', 'actor', 'record', 'entity', 'owner', 'owner_state', 'magic'):
            setattr(self, key, getattr(self.fixture, key))
        saved = json.loads((BASELINE / 'companion.json').read_text(encoding='utf-8'))['records'][0]
        learned = json.loads((BASELINE / 'magic.json').read_text(encoding='utf-8'))['rows'][1]['learned']
        self.record.level = saved['level']
        self.record.learned_spells = tuple(learned)
        self.record.hp = self.record.max_hp = saved['max_hp']
        self.record.mp = self.record.max_mp = saved['max_mp']
        self.assertEqual((self.record.level, len(learned)), (30, 38))
        self.actor.shield_until = 0
        self.actor.regen_at = 1000000000
        self.clock = 10
        self.equipment = {'weapon': 101, 'armor': 102}
        self.magic.equipment_uid = lambda rt, kind: self.equipment[kind]
        self.magic.ctx = NS(_companion_ailments=CompanionAilments(self.view), collect_sync_hooks=lambda *args: (), run_sync_hooks=lambda *args: None)
        self.magic.ctx._companion_ailments.start()
        self.addCleanup(self.magic.ctx._companion_ailments.close)
        self.configure()

    def configure(self, **options):
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(**options)),
            {s.key: s.name for s in self.magic.rules.values()})
        self.magic.policy_for = lambda _: policy
        return policy

    def decision(self, now, enemy=None):
        self.clock = now
        self.fixture.fixture.now = now
        return self.magic.step(self.actor, self.entity, self.owner, enemy, now, False)

    def casts(self, name=None):
        return [e for e in self.magic.events if e['spell'] in self.magic.spells and (name is None or e['spell'] == name)]

    def test_six_buffs_first_active_lead_expired_and_mp(self):
        rows = ('shield', 'blessed_armor', 'enchant_dexterity', 'holy_weapon', 'enchant_weapon', 'decrease_weight')
        for name in rows:
            with self.subTest(name=name):
                spell = self.magic.rules[name]
                self.configure(buff_spells=(spell.key,))
                self.magic.events.clear(); self.magic.engine.states.clear(); self.actor.shield_until = 0
                self.record.equipment.pop('magic_buffs', None)
                self.magic.cooldowns.clear(); self.actor.next_cast_at = 0
                self.record.mp = 314
                self.assertTrue(self.decision(10))
                end = 10 + spell.duration
                self.assertFalse(self.decision(12))
                self.assertFalse(self.decision(end - 11))
                self.assertTrue(self.decision(end - 1))
                self.assertEqual(len(self.casts()), 2)
                self.assertTrue(self.decision(end + spell.duration + 1))
                self.assertEqual(len(self.casts()), 3)
                self.record.mp = 0
                self.assertFalse(self.decision(end + 2 * spell.duration + 2))
                self.assertEqual(len(self.casts()), 3)
                print('BUFF_MATRIX', json.dumps(dict(spell=name, target=self.entity.uid,
                    times=[e['at'] for e in self.casts()], count=3, mp_cost=spell.mp)))

    def test_buff_consumers_bound_equipment_no_stack_and_mp_skip(self):
        profile = self.view.companion_profiles[2]
        for i, name in enumerate(('shield', 'blessed_armor', 'enchant_dexterity', 'holy_weapon', 'decrease_weight')):
            self.configure(buff_spells=(self.magic.rules[name].key,))
            self.assertTrue(self.decision(10 + i))
        defense = self.magic.profile(self.actor, profile, 16, defense=True)
        self.assertEqual(defense.ac, profile.ac - 3)  # retained defense adds shield -2 once
        offense = self.magic.profile(self.actor, profile, 16)
        self.assertEqual((offense.dexterity, offense.weapon.hit, offense.weapon.damage),
            (profile.dexterity + 5, profile.weapon.hit + 1, profile.weapon.damage + 1))
        self.equipment['armor'] = 999
        self.assertEqual(self.magic.profile(self.actor, profile, 16, defense=True).ac, profile.ac)
        self.equipment['weapon'] = 999
        self.assertEqual(self.magic.profile(self.actor, profile, 16).weapon, profile.weapon)
        self.equipment.update(weapon=101, armor=102)
        self.configure(buff_spells=(7, 11))
        self.assertTrue(self.decision(17))
        self.assertEqual(self.casts()[-1]['spell'], 'enchant_weapon')
        self.assertNotIn(7, self.magic.engine.state(2).buffs)
        self.assertFalse(self.decision(18))
        self.assertEqual(self.magic.profile(self.actor, profile, 18).weapon.damage, profile.weapon.damage + 2)
        self.configure(buff_spells=(25,), sequence_spells=(0,))
        self.record.mp = 4; self.record.hp = 1
        self.assertTrue(self.decision(19))
        self.assertEqual(self.casts()[-1]['spell'], 'heal')

    def test_three_heals_owner_self_threshold_and_big_hit_selected_upper(self):
        for i, name in enumerate(('heal', 'extra_heal', 'greater_heal')):
            spell = self.magic.rules[name]
            self.configure(conditional=((2, 50, spell.key),))
            for offset, target in enumerate(('owner', 'self')):
                self.record.mp = 314
                self.record.hp = self.record.max_hp
                self.owner_state.hp = self.owner_state.max_hp
                subject = self.record if target == 'self' else self.owner_state
                subject.hp = subject.max_hp // 2 + 1
                at = 10 + i * 10 + offset * 3
                before = len(self.casts())
                self.assertFalse(self.decision(at))
                subject.hp = subject.max_hp // 2
                self.assertTrue(self.decision(at + 1))
                self.assertEqual(len(self.casts()), before + 1)
                self.assertEqual(self.casts()[-1]['target'], self.entity.uid if target == 'self' else self.owner.uid)
                self.assertGreater(subject.hp, subject.max_hp // 2)
                print('HEAL_MATRIX', json.dumps(self.casts()[-1]))
        self.configure(conditional=((2, 20, 34), (2, 50, 18), (2, 80, 0)))
        self.record.hp = self.record.max_hp
        self.owner_state.hp = 10; self.record.mp = 314
        self.assertTrue(self.decision(50))
        self.assertEqual(self.casts()[-1]['spell'], 'greater_heal')
        self.configure(conditional=((2, 50, 0),))
        self.owner_state.hp = 10
        self.assertTrue(self.decision(51))
        self.assertEqual(self.casts()[-1]['spell'], 'heal')  # no injected stronger spell

    def test_six_attacks_range_mp_reuse_and_sequence_area(self):
        enemy = self.fixture.enemy()
        self.actor.target = enemy.ref
        self.view.spawner.slot_for(enemy.uid)[1].hp = 100000
        names = ('energy_bolt', 'ice_dagger', 'fire_arrow', 'lightning', 'fireball', 'cone_of_cold')
        for i, name in enumerate(names):
            spell = self.magic.rules[name]
            self.configure(sequence_spells=(spell.key,))
            self.view.entities.move(enemy.uid, 0, self.entity.x + spell.range + 1, self.entity.y)
            self.record.mp = 314
            at = 10 + 5 * i
            self.assertFalse(self.decision(at, enemy))
            self.view.entities.move(enemy.uid, 0, self.entity.x + spell.range, self.entity.y)
            self.record.mp = spell.mp - 1
            self.assertFalse(self.decision(at, enemy))
            self.record.mp = 314
            self.assertTrue(self.decision(at, enemy))
            self.assertEqual(self.record.mp, 314 - spell.mp)
            self.assertFalse(self.decision(at + .5, enemy))
            self.assertTrue(self.decision(at + 1, enemy))
            print('ATTACK_MATRIX', json.dumps(dict(spell=name, target=enemy.uid,
                times=[at, at+1], count=2, range=spell.range, mp_cost=spell.mp, reuse=spell.reuse)))
        self.configure(sequence_spells=tuple(self.magic.rules[n].key for n in names))
        self.view.entities.move(enemy.uid, 0, self.entity.x + 3, self.entity.y)
        self.record.mp = 314
        for i, name in enumerate(names):
            self.assertTrue(self.decision(50 + i, enemy))
            self.assertEqual(self.casts()[-1]['spell'], name)
        second, _ = self.fixture.fixture.monster()
        self.view.entities.move(second.uid, 0, enemy.x + 1, enemy.y)
        self.view.spawner.slot_for(second.uid)[1].hp = 10000
        self.configure(sequence_spells=(24,))
        self.assertTrue(self.decision(60, enemy))
        self.assertEqual(set(self.casts()[-1]['victims']), {enemy.uid, second.uid})

    def test_cure_only_active_poison_curse_and_lifecycle(self):
        from tools.local_original_session import world_magic_status as status
        ailments = self.magic.ctx._companion_ailments
        for at, key, kind in ((10, 8, 'poison'), (20, 36, 'curse')):
            self.configure(conditional=((3, 0, key),))
            self.assertFalse(self.decision(at))
            row = ailments.state(self.actor, at)
            if kind == 'poison':
                row['poison'] = dict(until=at+30, next_tick=at+3, tick_seconds=3, damage=2, source_uid=999)
            else:
                status.apply(row['effects'], 'curse', at, 30)
            self.assertTrue(self.decision(at+1))
            self.assertFalse(self.decision(at+2))
            print('CURE_MATRIX', json.dumps(self.casts()[-1]))
        self.configure(buff_spells=(2, 25, 13))
        for at in (30,31,32): self.assertTrue(self.decision(at))
        old = dict(self.magic.engine.state(2).buffs)
        self.view.companions.dismiss(2, 33)
        self.actor = self.view.summon_companion(2, 1)
        self.entity = self.view.entities.resolve(self.actor.ref)
        self.assertEqual(self.magic.engine.state(2).buffs, old)
        self.view.companions.on_death = lambda record, now: self.magic.died(record)
        self.view.companions.die(2, 34)
        self.assertNotIn(2, self.magic.engine.states)
        self.assertNotIn('magic_buffs', self.record.equipment)
        self.actor = self.view.companions.revive(2, 35, hp=1)
        self.entity = self.view.entities.resolve(self.actor.ref)
        self.assertTrue(self.decision(36))
        self.assertEqual(self.casts()[-1]['spell'], 'shield')
        self.assertEqual(self.actor.shield_until, 1236)
        self.assertNotIn(25, self.magic.engine.state(2).buffs)

    def test_real_equipment_calculated_weight_dex_and_both_defense_consumers(self):
        from tools.local_original_session import world_companion_equipment_tests as equipment_fixture
        from tools.local_original_session.world_feature_companion import CompanionMagic
        from tools.local_original_session import world_combat
        fixture = equipment_fixture.CompanionEquipmentTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        view, actor, record, bags = fixture.fixture.view, fixture.actor, fixture.record, fixture.bags
        entity, owner = view.entities.resolve(actor.ref), view.entities.get(1)
        record.level = 30; record.learned_spells = self.record.learned_spells
        record.mp = record.max_mp = 314
        magic = CompanionMagic(view, {}, self.magic.growth, self.magic.policy, self.magic.attributes)
        view.companion_ai.magic = magic
        view.companion_ai.inventory = view.combat.companion_inventory = bags
        bags.set_equipped(2, fixture.member_item(41), True)
        bags.set_equipped(2, fixture.member_item(103), True)
        base, _ = bags.calculated(2)
        magic.install_inventory()
        options = codec.companion_policy(codec.wrap_blob(codec.build_ats(buff_spells=(2,20,25,7,13))),
            {s.key: s.name for s in magic.rules.values()})
        magic.policy_for = lambda _: options
        for now in (10,11,12,13,14):
            fixture.fixture.now = now
            self.assertTrue(magic.step(actor, entity, owner, None, now, False), (now, magic.events, bags.states[2]))
        current, worn = bags.calculated(2)
        self.assertEqual(current.attributes.dexterity, base.attributes.dexterity + 5)
        self.assertEqual(current.max_weight, base.max_weight + 180)
        self.assertEqual(current.ac, base.ac - 5)
        bags.refresh(2, publish=False)
        profile = magic.profile(actor, view.companion_profiles[2], 14)
        self.assertEqual(profile.dexterity, current.attributes.dexterity)
        self.assertEqual(profile.weapon.damage, view.companion_profiles[2].weapon.damage + 1)
        _, monster = fixture.fixture.monster()
        with patch('tools.local_original_session.world_combat.npc_hits_pc', return_value=world_combat.Swing(False, 0)) as hit:
            view.combat.npc_companion_swing(monster, actor.ref.uid, view.companion_profiles[2], 14)
            self.assertEqual(hit.call_args.args[1].ac, current.ac)
            target = CompanionMonsterTarget(view, actor, CompanionAilments(view))
            target.physical(monster, 14)
            self.assertEqual(hit.call_args.args[1].ac, current.ac)
        fixture.fixture.now = 2000
        expired, _ = bags.calculated(2)
        self.assertEqual((expired.ac, expired.max_weight, expired.attributes.dexterity),
            (base.ac, base.max_weight, base.attributes.dexterity))

    def test_actual_cross_map_relocation_keeps_buff_deadline_and_no_early_recast(self):
        from tools.local_original_session import world_companion_movement_tests as movement_fixture
        from tools.local_original_session.world_feature_companion import CompanionMagic
        fixture = movement_fixture.CompanionMovementTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        view, actor, record = fixture.view, fixture.actor, fixture.record
        record.level = 30; record.learned_spells = self.record.learned_spells
        record.mp = record.max_mp = 314
        magic = CompanionMagic(view, {}, self.magic.growth, self.magic.policy, self.magic.attributes)
        view.companion_ai.magic = magic
        options = codec.companion_policy(codec.wrap_blob(codec.build_ats(buff_spells=(2,25,13))),
            {s.key: s.name for s in magic.rules.values()})
        magic.policy_for = lambda _: options
        for now in (10,11,12):
            fixture.fixture.now = now
            self.assertTrue(magic.step(actor, view.entities.resolve(actor.ref), view.entities.get(1), None, now, False))
        deadlines = dict(magic.engine.state(2).buffs)
        fixture.ctx._world_map_exp = 2
        fixture.move(map_id=1)
        fresh = view.companions.active[2]
        self.assertEqual(view.entities.resolve(fresh.ref).map_id, 1)
        fixture.fixture.now = 15
        self.assertFalse(magic.step(fresh, view.entities.resolve(fresh.ref), view.entities.get(1), None, 15, False))
        self.assertEqual(magic.engine.state(2).buffs, deadlines)
        self.assertEqual(fresh.shield_until, deadlines[2])

    def test_remove_curse_poison_only_combined_owner_and_reachable_heal_fallback(self):
        from tools.local_original_session import world_magic, world_magic_status as status
        engine = world_magic.PlayerMagic(world_magic.load_catalog())
        self.magic.ctx.collect_sync_hooks = lambda *args: ((engine, lambda *args: None),)
        self.configure(conditional=((3,0,36),))
        ailments = self.magic.ctx._companion_ailments
        for i, target in enumerate((self.entity, self.owner)):
            for j, combined in enumerate((False, True)):
                now = 10 + i*10 + j*3
                row = ailments.state(self.actor, now) if target is self.entity else vars(engine.state(1))
                row['poison'] = dict(until=now+30,next_tick=now+3,tick_seconds=3,damage=2,source_uid=999)
                if combined: status.apply(row['effects'], 'curse', now, 30)
                self.assertTrue(self.decision(now))
                self.assertEqual(self.casts()[-1]['target'], target.uid)
                self.assertIsNone(row['poison'])
                self.assertNotIn('curse', row['effects'])
                self.assertFalse(self.decision(now+1))
        self.configure(conditional=((2,50,0),))
        self.record.hp = self.record.max_hp // 3
        self.owner_state.hp = 1
        self.view.entities.move(self.owner.uid, 0, self.entity.x+11, self.entity.y)
        self.assertTrue(self.decision(40))
        self.assertEqual(self.casts()[-1]['target'], self.entity.uid)

    def test_cold_snapshot_restore_preserves_buff_and_every_cast_reuse(self):
        self.configure(buff_spells=(2,), sequence_spells=(0,))
        self.assertTrue(self.decision(10))
        self.record.hp = 1
        self.assertTrue(self.decision(11))
        snapshot = self.record.equipment['magic_buffs']
        self.assertEqual(snapshot['reuse_remaining'], 1)
        self.magic.engine.states.clear()
        self.magic.cooldowns.clear()
        self.actor.next_cast_at = self.actor.shield_until = 0
        with patch('tools.local_original_session.world_magic.time.time', return_value=snapshot['saved_at'] + .25):
            self.assertFalse(self.decision(20))
        self.assertEqual(self.actor.next_cast_at, 20.75)
        self.assertAlmostEqual(self.actor.shield_until, 1218.75)
        self.record.hp = 1
        self.assertFalse(self.decision(20.74))
        self.assertTrue(self.decision(20.75))
        self.assertEqual(self.casts()[-1]['spell'], 'heal')


if __name__ == '__main__':
    unittest.main()
