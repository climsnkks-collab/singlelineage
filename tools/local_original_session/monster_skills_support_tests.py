"""Development NPC support consumers; fake clock, no socket or native PASS."""
from dataclasses import replace
import json
import unittest

from tools.local_original_session import monster_skills_tests as fixture
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import Group, Slot, SlotState


class MonsterSupportTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.MonsterSkillsTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.owner, self.view = self.f.owner, self.f.view

    def prepare(self, template, kind, distance=1):
        row = self.f.row(template, kind)
        monster, target = self.f.configure(row, distance)
        brain = self.view.ai.brains[self.f.entity.uid]
        brain.monster = monster
        brain.next_move_at = brain.next_attack_at = 100
        # configure changes a whole spawn group's definition. Its other slots
        # retain old species HP in this development fixture unless normalized.
        for slot in self.f.group.slots:
            if slot is not self.f.slot:
                slot.hp = monster.hp
        return row, monster, target

    def ally(self, npc_id, hp_ratio, *, distance=2, map_id=None):
        monster = replace(self.f.group.monster, l1j_npcid=npc_id, hp=1000)
        source = self.f.entity
        entity = self.view.entities.add(Kind.NPC,
            source.map_id if map_id is None else map_id, source.x, source.y + distance,
            template_id=monster.template_id)
        slot = Slot(0, state=SlotState.ALIVE, uid=entity.uid,
                    hp=int(monster.hp * hp_ratio), home=(entity.x, entity.y))
        group = Group(replace(self.f.group.spec, group_id=f'support-{entity.uid}'),
                      monster, [slot], True)
        self.view.spawner.groups.append(group)
        self.view.spawner._slots[entity.uid] = group, slot
        return entity, group, slot

    def test_haste_targets_self_pays_once_and_feeds_actual_move_and_attack_deadlines(self):
        for template in (287, 760):
            with self.subTest(template=template):
                row, monster, target = self.prepare(template, 'haste', distance=6)
                self.assertTrue(self.owner.cast(self.f.entity, monster, target, row, 100))
                event = self.owner.events[-1]
                self.assertEqual(event['target'], self.f.entity.uid)
                self.assertEqual(event['mp_before'] - event['mp_after'], 40)
                self.assertFalse(self.owner.cast(self.f.entity, monster, target, row, 102))
                brain = self.view.ai.brains[self.f.entity.uid]
                # Existing AI, terrain move and attack consumers, no alternate
                # speed simulator: only remove competing specials for isolation.
                self.owner.attacks = {}
                self.view.ai.on_hit(self.f.entity.uid, target.uid, 102)
                self.view.ai._act(self.f.entity.uid, 102)
                self.assertEqual(brain.next_move_at, 102 + int(monster.move_interval_ms * .75) / 1000)
                self.view.entities.move(target.uid, self.f.entity.map_id,
                    self.f.entity.x + 1, self.f.entity.y)
                self.view.ai._act(self.f.entity.uid, 104)
                self.assertEqual(brain.next_attack_at,
                    104 + int(monster.attack_interval_ms * .75) / 1000)
                self.assertIs(brain.monster, monster)
                self.owner.tick(1300)
                self.assertFalse(self.owner.haste)
                self.view.ai._act(self.f.entity.uid, 1301)
                self.assertEqual(brain.next_attack_at, 1301 + monster.attack_interval_ms / 1000)
                self.owner.attacks = fixture.skills.load_attacks()

    def test_haste_generation_and_close_cleanup_preserve_life_count(self):
        row, monster, target = self.prepare(287, 'haste')
        self.owner.cast(self.f.entity, monster, target, row, 100)
        self.f.group.active = False
        self.owner.tick(101)
        self.assertTrue(self.owner.haste)
        self.assertEqual(self.owner.counts[self.f.entity.ref, row['id']], 1)
        self.view.spawner.mark_dead(self.f.entity.uid, 102)
        self.owner.tick(102)
        self.assertFalse(self.owner.haste)
        self.assertFalse(self.owner.cast(self.f.entity, monster, target, row, 103))
        self.owner.close()
        self.assertNotIn('_act', vars(self.view.ai))

    def test_heal_lowest_family_ratio_not_hostile_and_clamps_actual_slot_hp(self):
        from tools.local_original_session import hunt_bot as hb
        row, monster, hostile = self.prepare(902, 'heal')
        self.f.slot.hp = monster.hp // 2
        ally, group, slot = self.ally(45680, .1)
        self.ally(123456, .001)  # unknown family cannot win
        self.ally(45680, .001, map_id=self.f.entity.map_id + 1)
        self.ally(45680, .001, distance=row['max_distance'] + 1)
        self.view._refresh(1)
        self.view.drain(1)
        hostile_hp = self.view.combat.pcs[hostile.uid].hp
        self.assertTrue(self.owner.cast(self.f.entity, monster, hostile, row, 100))
        event = self.owner.events[-1]
        self.assertEqual((event['target'], event['outcome']), (ally.uid, 'healed'))
        effects = [hb.fields(wire[4:-2]) for wire in self.view.drain(1)
                   if int.from_bytes(wire[2:4], 'little') == 0x4ed8]
        self.assertTrue(any(hb.scalar(fields, 1) == ally.uid
                            and hb.scalar(fields, 2) == row['effect_id'] for fields in effects))
        self.assertEqual(event['mp_before'] - event['mp_after'], 48)
        self.assertEqual(slot.hp, event['hp_before'] + event['amount'])
        self.assertLessEqual(slot.hp, group.monster.hp)
        self.assertEqual(self.view.combat.pcs[hostile.uid].hp, hostile_hp)
        self.assertFalse(self.owner.cast(self.f.entity, monster, hostile, row, 100.1))
        # FullHeal is sourced dice, not an unconditional full-HP assignment.
        self.assertGreaterEqual(event['rolled_heal'], 22 * 5)
        self.assertLessEqual(event['rolled_heal'], 22 * 12 * 5)
        self.f.slot.hp = monster.hp
        slot.hp = 900
        self.assertTrue(self.owner.cast(self.f.entity, monster, hostile, row, 102))
        self.assertEqual(slot.hp, group.monster.hp)
        mana = self.owner.resources.mana_of(self.f.entity.ref, monster.mp)
        self.assertFalse(self.owner.cast(self.f.entity, monster, hostile, row, 104))
        self.assertEqual(self.owner.resources.mana_of(self.f.entity.ref, monster.mp), mana)

    def test_heal_self_and_admission_los_dormancy_dead_mana_and_missing_family(self):
        row, monster, hostile = self.prepare(902, 'heal')
        self.assertTrue(self.owner.cast(self.f.entity, monster, hostile, row, 100))
        self.assertEqual(self.owner.events[-1]['target'], self.f.entity.uid)
        self.assertGreater(self.f.slot.hp, 1)
        self.assertFalse(self.owner.cast(self.f.entity, monster, hostile,
            dict(row, family=''), 102))
        self.f.slot.hp = monster.hp
        ally, group, slot = self.ally(45680, .1)
        group.active = False
        self.assertFalse(self.owner.cast(self.f.entity, monster, hostile, row, 102))
        group.active = True
        ally.alive = False
        self.assertFalse(self.owner.cast(self.f.entity, monster, hostile, row, 102))
        ally.alive = True
        self.view.terrain.blocked = lambda x, y: True
        self.assertFalse(self.owner.cast(self.f.entity, monster, hostile, row, 102))
        self.view.terrain.blocked = lambda x, y: False
        self.owner.resources.spend_mana(self.f.entity.ref, monster.mp, monster.mp - 48)
        self.assertFalse(self.owner.cast(self.f.entity, monster, hostile, row, 102))

    def test_natural_ai_selects_support_before_damage_with_same_cooldown(self):
        row, monster, hostile = self.prepare(902, 'heal', distance=3)
        row = dict(row, chance_percent=100)
        self.owner.attacks = {monster.l1j_npcid: (row,)}
        self.view.ai.on_hit(self.f.entity.uid, hostile.uid, 100)
        before = self.f.slot.hp
        self.view.ai._act(self.f.entity.uid, 100)
        self.assertGreater(self.f.slot.hp, before)
        self.assertEqual(len(self.owner.events), 1)
        self.view.ai._act(self.f.entity.uid, 100.1)
        self.assertEqual(len(self.owner.events), 1)

    def test_natural_ai_haste_uses_self_effect_target_and_one_life_cost(self):
        from tools.local_original_session import hunt_bot as hb
        row, monster, hostile = self.prepare(287, 'haste', distance=3)
        self.owner.attacks = {monster.l1j_npcid: (dict(row, chance_percent=100),)}
        self.view._refresh(1)
        self.view.drain(1)
        self.view.ai.on_hit(self.f.entity.uid, hostile.uid, 100)
        self.view.ai._act(self.f.entity.uid, 100)
        self.assertEqual(self.owner.events[-1]['target'], self.f.entity.uid)
        effects = [hb.fields(wire[4:-2]) for wire in self.view.drain(1)
                   if int.from_bytes(wire[2:4], 'little') == 0x4ed8]
        self.assertTrue(any(hb.scalar(fields, 1) == self.f.entity.uid
                            and hb.scalar(fields, 2) == row['effect_id'] for fields in effects))
        self.view.ai._act(self.f.entity.uid, 103)
        self.assertEqual(len(self.owner.events), 1)
        self.assertEqual(self.owner.resources.mana_of(self.f.entity.ref, monster.mp), monster.mp - 40)

    def test_catalog_promotes_supported_support_and_explicit_buff_only_cancel(self):
        raw = json.loads(fixture.skills.DATA_PATH.read_text(encoding='utf-8'))
        promoted = {'287:mob:0', '760:mob:0', '902:mob:0'}
        self.assertTrue(promoted <= {r['id'] for r in raw['attacks']})
        self.assertFalse(promoted & {r['id'] for r in raw['omitted']})
        cancel = next(r for r in raw['attacks'] if r['id'] == '454:mob:2')
        self.assertEqual((cancel['kind'], cancel['cancel_scope']), ('cancel', 'magic_buffs_only'))
        self.assertEqual((cancel['mp_cost'], cancel['max_distance']), (40, 6))
        self.assertNotIn(cancel['id'], {r['id'] for r in raw['omitted']})


if __name__ == '__main__':
    unittest.main()
