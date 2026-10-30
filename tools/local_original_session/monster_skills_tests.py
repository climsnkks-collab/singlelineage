"""Development fake-clock tests; no game, socket or formal packet PASS."""
from dataclasses import replace
import json
from pathlib import Path
import random
import unittest

from tools.local_original_session import game_data, world_magic, world_magic_status
from tools.local_original_session import world_monster_skills as skills
from tools.local_original_session.world_ai_tests import FakeClock, GridTerrain, status_fields
from tools.local_original_session.world_combat import PcProfile, Swing
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_visibility import WorldView


def all_data():
    base = game_data.load_m1()
    monsters = {}
    for path in (Path(__file__).parent / 'data').glob('m*/monsters.json'):
        monsters.update(game_data._monsters(json.loads(path.read_text(encoding='utf-8'))))
    for name in ('catalog/map0/monsters.json', 'm6/map_expansion2_population.json'):
        path = Path(__file__).parent / 'data' / name
        monsters.update(game_data._monsters(json.loads(path.read_text(encoding='utf-8'))))
    monsters.update(base.monsters)
    return replace(base, monsters=monsters, spawns=base.spawns[:1])


class MonsterSkillsTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.data = all_data()
        self.view = WorldView.create(data=self.data, terrain=GridTerrain(),
                                     clock=self.clock, rng=random.Random(3))
        self.view.bind_pc(1, PcProfile(60, 1, 0, 18, 18), status_fields(1000000))
        spec = self.data.spawns[0]
        self.view.update_pc(1, spec.map_id, spec.rect.x1, spec.rect.y1, reset=True)
        self.group = self.view.spawner.groups[0]
        self.entity = self.view.entities.get(self.group.slots[0].uid)
        self.slot = self.group.slots[0]
        self.magic = world_magic.PlayerMagic(world_magic.load_catalog())
        self.saved = []
        self.owner = skills.MonsterSkills(self.view, skills.load_attacks(),
            provider=(self.magic, lambda uid, now: self.saved.append(self.magic.snapshot(uid, now))),
            # Admission/cost matrix only; dedicated Cancel tests use the real
            # registered owner callback and persisted/4E91 consumers.
            cancel_target=lambda uid: (lambda now: ()) if uid == 1 else None)
        self.owner.start()

    def tearDown(self):
        self.owner.close()
        self.view.close()

    def configure(self, row, distance=None):
        monster = self.data.monsters[row['template_id']]
        self.group.monster = monster
        self.group.spec = replace(self.group.spec, template_id=monster.template_id)
        self.slot.hp = 1 if row.get('trigger_hp_percent') or row['kind'] == 'heal' else monster.hp
        self.entity.template_id = monster.template_id
        target = self.view.entities.get(1)
        d = row['min_distance'] if distance is None else distance
        self.view.entities.move(1, self.entity.map_id, self.entity.x + max(1, d), self.entity.y)
        self.view.pcs[1] = self.entity.map_id, target.x, target.y
        self.magic.state(1).effects.clear()
        self.magic.state(1).poison = None
        self.view.combat.pcs[1].hp = self.view.combat.pcs[1].max_hp
        self.view.combat.pcs[1].dead = False
        self.owner.forget(self.entity.uid)
        self.owner.resources.forget(self.entity.uid)
        return monster, target

    def row(self, template, kind):
        return next(row for rows in self.owner.attacks.values() for row in rows
                    if row['template_id'] == template and row['kind'] == kind)

    def test_every_enabled_action_has_range_mana_and_lifetime_admission(self):
        for rows in self.owner.attacks.values():
            for row in rows:
                with self.subTest(action=row['id']):
                    monster, target = self.configure(row)
                    self.assertTrue(self.owner._eligible(self.entity, monster, target, row,
                        self.clock(), on_hit=row.get('on_hit', False)))
                    self.view.entities.move(1, self.entity.map_id,
                        self.entity.x + row['max_distance'] + 1, self.entity.y)
                    # Support distance is measured to the beneficiary, which
                    # can be the caster; enemy displacement does not change it.
                    self.assertEqual(self.owner._eligible(self.entity, monster, target, row,
                        self.clock(), on_hit=row.get('on_hit', False)), row['kind'] in skills.SUPPORT_KINDS)
                    self.view.entities.move(1, self.entity.map_id, self.entity.x + max(1, row['min_distance']), self.entity.y)
                    self.owner.cooldowns[self.entity.ref, row['id']] = self.clock() + 1
                    self.assertFalse(self.owner.cast(self.entity, monster, target, row, self.clock()))
                    self.owner.cooldowns.clear()
                    self.owner.resources.spend_mana(self.entity.ref, monster.mp, monster.mp)
                    if row['mp_cost']:
                        self.assertFalse(self.owner.cast(self.entity, monster, target, row, self.clock()))

    def test_every_enabled_action_commits_once_and_cooldown_is_shared_with_ai(self):
        for rows in self.owner.attacks.values():
            for row in rows:
                with self.subTest(action=row['id']):
                    monster, target = self.configure(row)
                    before = len(self.owner.events)
                    self.assertTrue(self.owner.cast(self.entity, monster, target, row, self.clock()))
                    event = self.owner.events[-1]
                    self.assertEqual(event['id'], row['id'])
                    self.assertEqual(event['mp_after'], monster.mp-row['mp_cost'])
                    if max(row['reuse_seconds'], row['cast_interval_seconds']) > 0:
                        self.assertFalse(self.owner.cast(self.entity, monster, target, row, self.clock()))
                    self.assertTrue(self.owner.events)

    def test_delayed_paralysis_cannot_be_refreshed_and_survives_snapshot(self):
        row = self.row(28, 'paralysis')
        monster, target = self.configure(row)
        self.assertTrue(self.owner.cast(self.entity, monster, target, row, 100))
        self.assertFalse(world_magic_status.ai_status(self.magic.effects(1), 119)['blocked'])
        self.assertTrue(world_magic_status.ai_status(self.magic.effects(1), 120)['blocked'])
        self.assertFalse(self.owner.cast(self.entity, monster, target, row, 121))
        restored = world_magic_status.restore(world_magic_status.snapshot(self.magic.effects(1), 110), 500, 5)
        self.assertTrue(world_magic_status.ai_status(restored, 505)['blocked'])
        self.assertFalse(world_magic_status.ai_status(self.magic.effects(1), 165)['blocked'])
        self.owner.cure_poison(1)
        self.assertNotIn('paralyze', self.magic.effects(1))

    def test_poison_contact_requires_actual_landed_damage_and_cure_owner(self):
        row = self.row(31, 'poison')
        monster, target = self.configure(row)
        self.owner._on_hit(self.entity, monster, target, Swing(False, 0), 100)
        self.assertIsNone(self.magic.state(1).poison)
        self.assertTrue(self.owner.cast(self.entity, monster, target, row, 100))
        self.assertEqual(self.magic.state(1).poison['next_tick'], 103)
        self.assertEqual(self.magic.state(1).poison['damage'], 5)
        self.assertIsNone(self.owner.events[-1].get('trace'))
        self.assertNotIn(0x4ed8, [int.from_bytes(w[2:4], 'little') for w in self.view.drain(1)])

    def test_silence_blocks_only_spell_admission_and_cure_removes_it(self):
        row = self.row(115, 'silence')
        monster, target = self.configure(row)
        self.owner.cast(self.entity, monster, target, row, 100)
        self.assertFalse(world_magic_status.ai_status(self.magic.effects(1), 100)['blocked'])
        with self.assertRaisesRegex(ValueError, 'MAGIC_CASTER_SILENCED'):
            self.magic.admit_cast(1, 999, 1, 60, 100, True, 100)
        self.owner.cure_poison(1)
        self.assertIsNone(self.magic.status(1, 'silence', 100))

    def test_slow_uses_target_mr_and_counter(self):
        row = self.row(2214, 'slow')
        monster, target = self.configure(row)
        self.view.combat.pcs[1].profile = replace(self.view.combat.pcs[1].profile, mr=10000)
        self.owner.cast(self.entity, monster, target, row, 100)
        self.assertEqual(self.owner.events[-1]['outcome'], 'resisted')
        self.assertIsNone(self.magic.status(1, 'slow', 100))
        monster, target = self.configure(row)
        self.magic.apply_status(1, 'counter_magic', 100, 10)
        self.owner.cast(self.entity, monster, target, row, 100)
        self.assertEqual(self.owner.events[-1]['outcome'], 'countered')
        self.assertIsNone(self.magic.status(1, 'counter_magic', 100))

    def test_elemental_resistance_and_drain_use_actual_hp(self):
        row = self.row(7, 'magic')
        damages = []
        for resist in (0, 100):
            monster, target = self.configure(row)
            self.view.combat.rng.seed(9)
            self.view.combat.pcs[1].profile = replace(self.view.combat.pcs[1].profile, resist_wind=resist)
            self.owner.cast(self.entity, monster, target, row, 100)
            damages.append(self.owner.events[-1]['amount'])
        self.assertGreater(damages[0], damages[1])
        drain = next(r for rows in self.owner.attacks.values() for r in rows if r.get('drain'))
        monster, target = self.configure(drain)
        self.slot.hp = monster.hp-1
        self.view.combat.pcs[1].hp = 1
        self.owner.cast(self.entity, monster, target, drain, 100)
        self.assertLessEqual(self.owner.events[-1]['drain_restored'], 1)
        self.assertLessEqual(self.slot.hp, monster.hp)

    def test_natural_ai_casts_at_skill_range_before_melee_and_never_double_spends(self):
        row = self.row(7, 'magic')
        row = dict(row, chance_percent=100)
        monster, target = self.configure(row, distance=4)
        self.owner.attacks = {monster.l1j_npcid: (row,)}
        self.view.ai.brains[self.entity.uid].monster = replace(monster, attack_range=1)
        brain = self.view.ai.brains[self.entity.uid]
        self.view.ai.on_hit(self.entity.uid, 1, 100)
        self.view.ai._act(self.entity.uid, 100)
        self.assertEqual(len(self.owner.events), 1)
        self.assertEqual(self.owner.events[-1]['mp_after'], monster.mp-row['mp_cost'])
        self.assertEqual((self.entity.x+4, self.entity.y), (target.x, target.y))
        self.view.ai._act(self.entity.uid, 100.1)
        self.assertEqual(len(self.owner.events), 1)

    def test_ordinary_ranged_row_keeps_base_ai_cadence_and_range(self):
        row = self.row(1, 'physical')
        monster, target = self.configure(row, distance=8)
        self.owner.attacks = {monster.l1j_npcid: (row,)}
        brain = self.view.ai.brains[self.entity.uid]
        brain.monster = replace(monster, attack_range=1)
        self.view.ai.on_hit(self.entity.uid, 1, 100)
        self.view.ai._act(self.entity.uid, 100)
        hp = self.view.combat.pcs[1].hp
        self.assertEqual(brain.next_attack_at, 100+monster.attack_interval_ms/1000)
        self.view.ai._act(self.entity.uid, 100.1)
        self.assertEqual(self.view.combat.pcs[1].hp, hp)
        self.assertEqual(brain.monster.attack_range, 1)

    def test_summon_slots_die_without_respawn_and_end_with_parent(self):
        row = self.row(24, 'summon')
        monster, target = self.configure(row)
        self.owner.cast(self.entity, monster, target, row, 100)
        refs = [self.view.entities.get(uid).ref for uid in self.owner.events[-1]['summoned_uids']]
        self.assertTrue(refs)
        groups = self.owner.summons[self.entity.ref]
        self.view.spawner.mark_dead(refs[0].uid, 100)
        self.view.spawner._refill(groups[0], 100000, retry_now=True)
        self.assertIsNone(self.view.entities.get(refs[0].uid))
        self.assertLess(sum(s.uid is not None for s in groups[0].slots), len(refs))
        self.group.active = False
        self.owner.tick(101)
        self.assertFalse(self.owner.summons)
        self.assertTrue(all(self.view.entities.get(r.uid) is None for r in refs))

    def test_summon_corpse_suppresses_only_ground_drops_and_keeps_core_experience(self):
        from tools.local_original_session.world_reward import on_kill, RewardPcState
        row = self.row(24, 'summon')
        monster, target = self.configure(row)
        self.owner.cast(self.entity, monster, target, row, 100)
        summon = self.view.entities.get(self.owner.events[-1]['summoned_uids'][0])
        group, slot = self.view.spawner.slot_for(summon.uid)
        item = next(i.template_id for i in self.data.items.values() if i.stackable)
        drop = replace(next(r for rows in self.data.drops.values() for r in rows),
            item_id=item, chance=game_data.CHANCE_DENOMINATOR, min_count=1, max_count=1)
        data = replace(self.view.data, drops={group.monster.template_id: (drop,), monster.template_id: (drop,)})
        self.view.replace_data(data)
        state = self.view.combat.pcs[1]
        state.profile = replace(state.profile, level=1)
        before_exp = self.view.exp[1]
        expected = on_kill(RewardPcState.from_combat(state, exp=before_exp),
                           group.monster, random.Random(1), data=data)
        living_ref = summon.ref
        self.view._apply_monster_swing(1, 1, summon, group.monster, slot.hp, Swing(True, slot.hp), 100)
        self.assertFalse(summon.alive)
        self.assertNotEqual(summon.ref, living_ref)
        self.assertEqual(self.view.exp[1], expected.new_exp)
        self.assertEqual(self.view.combat.kills[-1].npc_uid, summon.uid)
        self.assertEqual(len(self.view.ground), 0)
        # Ownership remains through the corpse generation, including repeated
        # reward publication attempts. The live-generation guard still refuses.
        self.assertEqual(self.view.ground.spawn_reward(summon.ref, expected, owner_uid=1, now=101), ())
        with self.assertRaisesRegex(ValueError, 'CURRENT_DEAD_NPC'):
            self.view.ground.spawn_reward(living_ref, expected, owner_uid=1, now=101)
        # The same real core kill/reward path on an ordinary NPC still spawns.
        normal_hp = self.slot.hp
        before_exp = self.view.exp[1]
        expected = on_kill(RewardPcState.from_combat(state, exp=before_exp),
                           monster, random.Random(1), data=data)
        self.view._apply_monster_swing(1, 1, self.entity, monster, normal_hp, Swing(True, normal_hp), 102)
        self.assertEqual(self.view.exp[1], expected.new_exp)
        self.assertEqual(len(self.view.ground), 1)
        self.assertFalse(self.view.reward_errors)

    def test_generation_change_discards_cooldown_and_old_ref_cannot_cast(self):
        row = self.row(7, 'magic')
        monster, target = self.configure(row)
        self.owner.cast(self.entity, monster, target, row, 100)
        ref = self.entity.ref
        self.view.spawner.mark_dead(self.entity.uid, 100)
        self.owner.tick(100)
        self.assertFalse(self.owner.cooldowns)
        self.assertFalse(self.view.entities.is_current(ref))
        self.assertFalse(self.owner.cast(self.entity, monster, target, row, 1000))

    def test_close_restart_restores_actual_wrappers_and_status_feature_absence(self):
        self.owner.close()
        self.assertNotIn('npc_attack', vars(self.view))
        self.assertNotIn('admit_cast', vars(self.magic))
        self.assertNotIn('spawn_reward', vars(self.view.ground))
        self.owner.start()
        self.owner.close()
        self.owner = skills.MonsterSkills(self.view, skills.load_attacks())
        self.owner.start()
        row = self.row(28, 'paralysis')
        monster, target = self.configure(row)
        self.assertFalse(self.owner.cast(self.entity, monster, target, row, 100))
        hp = self.view.combat.pcs[1].hp
        self.view.combat.rng.seed(3)
        self.view.npc_attack(self.entity, monster, 1, 100)
        self.assertLessEqual(self.view.combat.pcs[1].hp, hp)


if __name__ == '__main__':
    unittest.main()
