"""Development checks for registered follower consumers; no sockets or game."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import world_companion_integration_tests as fixtures
from tools.local_original_session import monster_skills_tests as monster_fixtures
from tools.local_original_session import world_magic, world_magic_status as status
from tools.local_original_session import world_monster_skills as skills
from tools.local_original_session.world_feature_companion import (
    CompanionAilments, CompanionMonsterTarget, CompanionMagic)
from tools.local_original_session.world_combat import Swing, death_frame
from tools.local_original_session.world_interest_spawn import Group, Slot, SlotState
from tools.local_original_session.world_entities import Kind


class CompanionMonsterTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.actor = self.fixture.view, self.fixture.actor
        self.record = self.actor.record
        self.record.hp = self.record.max_hp = 100000
        self.view.replace_data(monster_fixtures.all_data())
        self.ailments = CompanionAilments(self.view)
        self.ailments.start()
        self.addCleanup(self.ailments.close)
        self.adapter = CompanionMonsterTarget(self.view, self.actor, self.ailments)
        self.magic = world_magic.PlayerMagic(world_magic.load_catalog())
        self.owner = skills.MonsterSkills(self.view, skills.load_attacks(),
            provider=(self.magic, lambda *_: None), magic_target=self.target)
        self.owner.start()
        self.addCleanup(self.owner.close)

    def target(self, uid):
        actor = self.view.companions.get_actor(uid)
        return None if actor is None else CompanionMonsterTarget(self.view, actor, self.ailments)

    def row(self, template, kind):
        return next(r for rows in self.owner.attacks.values() for r in rows
                    if r['template_id'] == template and r['kind'] == kind)

    def enemy(self, row, distance=1):
        monster = self.view.data.monsters[row['template_id']]
        target = self.view.entities.resolve(self.actor.ref)
        entity = self.view.entities.add(Kind.NPC, target.map_id, target.x + distance, target.y,
                                        template_id=monster.template_id)
        spec = replace(self.view.data.spawns[0], template_id=monster.template_id)
        slot = Slot(0, SlotState.ALIVE, entity.uid, monster.hp, (entity.x, entity.y))
        group = Group(spec, monster, [slot], True)
        self.view.spawner.groups.append(group)
        self.view.spawner._slots[entity.uid] = group, slot
        self.view.ai.sync(100)
        return entity, monster, target

    def test_physical_magic_drain_target_one_real_ledger_and_no_player_hud(self):
        for template, kind in ((1, 'physical'), (7, 'magic'), (36, 'magic')):
            row = self.row(template, kind)
            entity, monster, target = self.enemy(row, max(1, row['min_distance']))
            before = self.record.hp
            self.view.drain(1)
            self.assertTrue(self.owner.cast(entity, monster, target, row, 100))
            event = self.owner.events[-1]
            self.assertEqual(event['amount'], before - self.record.hp)
            self.assertEqual(event['mp_after'], monster.mp - row['mp_cost'])
            self.assertNotIn(target.uid, self.view.combat.pcs)
            opcodes = [int.from_bytes(w[2:4], 'little') for w in self.view.drain(1)]
            self.assertIn(0x4e31, opcodes)
            self.assertNotIn(0x4e38, opcodes)

    def test_contact_requires_landed_positive_damage_and_poison_ticks_once(self):
        row = self.row(31, 'poison')
        entity, monster, target = self.enemy(row)
        forced = dict(row, chance_percent=100)
        self.owner.attacks = {monster.l1j_npcid: (forced,)}
        for swing in (Swing(False, 9), Swing(True, 0)):
            self.owner._on_hit(entity, monster, target, swing, 100)
            self.assertIsNone(self.adapter.ailments(100)['poison'])
        self.owner._on_hit(entity, monster, target, Swing(True, 1), 100)
        before = self.record.hp
        self.ailments.tick(103)
        self.assertEqual(self.record.hp, before - 5)
        self.ailments.tick(103)
        self.assertEqual(self.record.hp, before - 5)
        self.assertEqual(self.ailments.events[-1]['target'], target.uid)
        self.adapter.cure_poison(104)
        self.ailments.tick(110)
        self.assertEqual(self.record.hp, before - 5)

    def test_npc_attack_contact_path_consumes_physical_once_and_shared_mana_is_not_rolled_twice(self):
        row = dict(self.row(31, 'poison'), chance_percent=100)
        entity, monster, target = self.enemy(row)
        self.owner.attacks = {monster.l1j_npcid: (row,)}
        legacy = []
        self.view.events.add('phase2_test', 'npc_magic_attack', lambda *args: legacy.append(args))
        before = self.record.hp
        with patch('tools.local_original_session.world_combat.npc_hits_pc', return_value=Swing(True, 7)) as hit:
            self.view.npc_attack(entity, monster, target.uid, 100)
        self.assertEqual(hit.call_count, 1)
        self.assertEqual(self.record.hp, before - 7)
        self.assertFalse(legacy)
        self.assertIsNotNone(self.adapter.ailments(100)['poison'])
        self.assertEqual(len(self.owner.events), 1)

    def test_magic_provider_absent_contact_still_consumes_and_slow_safely_refuses(self):
        self.owner.close()
        self.owner = skills.MonsterSkills(self.view, skills.load_attacks(), magic_target=self.target)
        self.owner.start()
        self.addCleanup(self.owner.close)
        row = self.row(31, 'poison')
        entity, monster, target = self.enemy(row)
        self.assertTrue(self.owner.cast(entity, monster, target, row, 100))
        self.assertIsNotNone(self.adapter.ailments(100)['poison'])
        row = self.row(2214, 'slow')
        entity, monster, target = self.enemy(row)
        self.assertFalse(self.owner.cast(entity, monster, target, row, 100))
        self.owner.close()
        self.ailments.tick(103)
        self.assertEqual(self.ailments.events[-1]['kind'], 'poison_tick')

    def test_lethal_poison_publishes_death_and_cancels_actor_life(self):
        row = self.row(31, 'poison')
        entity, monster, target = self.enemy(row)
        self.owner.cast(entity, monster, target, row, 100)
        self.record.hp = 3
        old_ref = self.actor.ref
        self.view.drain(1)
        self.ailments.tick(103)
        self.assertFalse(self.record.alive)
        self.assertEqual(self.record.hp, 0)
        self.assertIsNone(self.view.entities.resolve(old_ref))
        self.assertIsNone(self.actor.handle)
        self.assertIsNone(self.adapter.ailments(103)['poison'])
        self.assertIn(death_frame(target.uid), self.view.drain(1))

    def test_ordinary_attack_death_clears_poison_before_new_life(self):
        # Same death callback as companion feature startup; ordinary damage
        # bypasses the monster feature and must still clear saved ailments.
        self.view.companions.on_death = lambda record, now: self.ailments.clear(record)
        row = self.row(31, 'poison')
        entity, monster, target = self.enemy(row)
        self.owner.cast(entity, monster, target, row, 100)
        self.owner.close()
        self.record.hp = 3
        with patch('tools.local_original_session.world_combat.npc_hits_pc', return_value=Swing(True, 7)):
            self.view.npc_attack(entity, monster, target.uid, 101)
        self.assertFalse(self.record.alive)
        self.assertNotIn('monster_ailments', self.record.equipment)
        self.assertNotIn(self.record.character_id, self.ailments.rows)
        self.actor = self.view.companions.revive(2, 102, hp=10)
        target = self.target(self.actor.ref.uid)
        self.assertEqual(target.ailments(102), {'effects': {}, 'poison': None})

    def prepare_caster(self):
        root = Path(__file__).parent / 'data' / 'companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        caster = CompanionMagic(self.view, read('mage_spells'), read('mage_growth'),
            read('ai_policy'), {2: (8, 7, 16, 18, 8, 18)})
        from tools.local_original_session import ats_config_codec as codec
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(sequence_spells=(3,))),
                                        {3: 'energy_bolt'})
        caster.policy_for = lambda _: policy
        self.record.level = 5
        self.record.learned_spells = (0, 2, 3)
        self.record.mp = self.record.max_mp = 40
        self.record.combat_mode = 'ASSIST'
        self.view.companion_ai.magic = caster
        return caster

    def test_paralysis_delayed_ai_block_and_silence_only_blocks_casts(self):
        caster = self.prepare_caster()
        row = self.row(28, 'paralysis')
        entity, monster, target = self.enemy(row)
        self.owner.cast(entity, monster, target, row, 100)
        self.actor.target = entity.ref
        self.assertFalse(self.ailments.action_status({}, self.actor.ref, 119)['blocked'])
        before = self.record.mp
        self.view.companion_ai.step(self.actor.ref, 120)
        self.assertEqual(self.actor.action, 'PARALYZED')
        self.assertEqual(self.record.mp, before)
        self.adapter.cure_poison(121)
        row = self.row(115, 'silence')
        entity, monster, target = self.enemy(row)
        self.owner.cast(entity, monster, target, row, 122)
        self.actor.target = entity.ref
        self.assertFalse(caster.cast(self.actor, target, entity, 'energy_bolt', 123))
        intents = []
        self.view.companion_ai.attack_consumer = intents.append
        self.view.companion_ai.step(self.actor.ref, 123)
        self.assertTrue(intents)
        self.assertEqual(self.record.mp, before)
        self.adapter.cure_poison(124)
        self.assertFalse(self.ailments.action_status({}, self.actor.ref, 124)['silenced'])

    def test_cure_keeps_nonpoison_status_and_saved_state_restores(self):
        self.adapter.apply_status('paralyze', 100, 30, params={'monster_poison': False})
        self.adapter.apply_status('silence', 100, None, params={'monster_poison': False})
        self.adapter.save(100)
        self.adapter.cure_poison(101)
        self.assertIn('paralyze', self.adapter.ailments(101)['effects'])
        self.ailments.close()
        self.ailments.start()
        with patch('time.time', return_value=self.record.equipment['monster_ailments']['saved_at'] + 5):
            state = self.adapter.ailments(500)
        self.assertTrue(status.ai_status(state['effects'], 500)['blocked'])
        self.assertAlmostEqual(state['effects']['paralyze']['until'], 525, places=3)
        self.assertIn('silence', state['effects'])

    def test_natural_ai_selects_one_companion_special_then_no_legacy_selector(self):
        row = dict(self.row(7, 'magic'), chance_percent=100)
        entity, monster, target = self.enemy(row, 3)
        self.owner.attacks = {monster.l1j_npcid: (row,)}
        brain = self.view.ai.brains[entity.uid]
        self.view.ai.on_hit(entity.uid, target.uid, 100)
        self.view.ai._act(entity.uid, 100)
        self.assertEqual(len(self.owner.events), 1)
        self.assertEqual(self.owner.events[-1]['target'], target.uid)
        self.assertEqual(self.owner.resources.mana_of(entity.ref, monster.mp), monster.mp-row['mp_cost'])
        self.view.ai._act(entity.uid, 100.01)
        self.assertEqual(len(self.owner.events), 1)

    def test_feature_absence_close_restart_and_new_entity_ref(self):
        row = self.row(31, 'poison')
        entity, monster, target = self.enemy(row)
        self.owner.magic_target = lambda _: None
        self.assertFalse(self.owner.cast(entity, monster, target, row, 100))
        self.owner.magic_target = self.target
        self.assertTrue(self.owner.cast(entity, monster, target, row, 100))
        self.owner.close()
        before = self.record.hp
        self.ailments.tick(103)  # producer disabled; target remains its own consumer
        self.assertEqual(self.record.hp, before - 5)
        self.owner.start()
        self.owner.start()
        old = self.actor.ref
        self.view.companions.dismiss(2, 104)
        self.actor = self.view.summon_companion(2, 1)
        self.assertNotEqual(self.actor.ref, old)
        self.assertFalse(self.adapter.current())
        self.assertEqual(self.adapter.damage(100, 105), 0)
        self.assertEqual(self.ailments.action_status({}, old, 105), {})

    def test_ats_antidote_uses_existing_bag_cas_and_does_not_consume_expired_poison(self):
        from tools.local_original_session.world_item_effects import load_effects
        consumed, saved = [], []
        bags = SimpleNamespace(next_potion={}, events=[],
            consume_ats_item=lambda uid, slots: consumed.append((uid, slots)) or (126 if slots else None),
            save=saved.append)
        slots = [dict(status='valid', template=126, raw={1: 2, 4: 126, 5: 0, 6: 0})]
        ctx = SimpleNamespace(_companion_inventory=bags,
            _companion_antidotes=frozenset(t for t, e in load_effects().items() if e.kind == 'cure_poison'),
            fold_sync_hooks=lambda *args: {'status': 'valid', 'function_slots': slots})
        self.ailments.ctx = ctx
        row = self.row(31, 'poison')
        entity, monster, target = self.enemy(row)
        self.owner.cast(entity, monster, target, row, 100)
        self.ailments.action_status({}, self.actor.ref, 101)
        self.assertIsNone(self.adapter.ailments(101)['poison'])
        self.assertTrue(bags.events[-1]['poison_cured'])
        self.assertEqual(consumed, [(2, slots)])
        self.assertEqual(saved, [1])
        self.owner.cast(entity, monster, target, row, 110)
        self.ailments.action_status({}, self.actor.ref, 141)
        self.assertEqual(len(consumed), 1)


if __name__ == '__main__':
    unittest.main()
