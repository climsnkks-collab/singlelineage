"""Stage4/5 development checks on real WorldView; socket scenario is separate.

No game/render claim. Direct fixture clock/resource changes below are local
unit inputs, never a formal gameplay PASS or changes to a user profile.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from tools.local_original_session import world_companion_integration_tests as fixtures
from tools.local_original_session.world_feature_companion import CompanionMagic


class MagicTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.actor, self.record = self.fixture.view, self.fixture.actor, self.fixture.record
        self.entity = self.view.entities.resolve(self.actor.ref)
        self.owner = self.view.entities.get(1)
        root = Path(__file__).parent / 'data' / 'companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        self.magic = CompanionMagic(self.view, read('mage_spells'), read('mage_growth'),
            read('ai_policy'), {2: (8, 7, 16, 18, 8, 18)}, display=True)
        self.view.companion_ai.magic = self.magic
        self.record.level = 5
        self.record.learned_spells = (0, 2, 3)
        self.record.mp = self.record.max_mp = 40
        self.actor.shield_until = 1200
        self.record.combat_mode = 'ASSIST'
        self.record.movement_mode = 'FOLLOW'
        self.owner_state = self.view.combat.pcs[1]
        self.view.drain(1)

    def step(self, now=10):
        self.fixture.now = now
        self.view.companion_ai.step(self.actor.ref, now)

    def enemy(self, x=None, y=None):
        enemy, _ = self.fixture.monster()
        self.view.entities.move(enemy.uid, 0,
            self.entity.x + 4 if x is None else x, self.entity.y if y is None else y)
        self.view.companion_ai.owner_attacked(self.owner.ref, enemy.ref, self.fixture.now)
        return enemy

    def events(self, name):
        return [e for e in self.magic.events if e['spell'] == name]

    def test_bolt_debits_once_uses_real_monster_hp_and_cooldown(self):
        enemy = self.enemy()
        before = self.view.spawner.slot_for(enemy.uid)[1].hp
        self.step()
        self.assertEqual(self.record.mp, 37)
        after = self.view.spawner.slot_for(enemy.uid)[1].hp
        self.assertLess(after, before)
        self.step(10.2)
        self.assertEqual(self.record.mp, 37)
        self.assertEqual(len(self.events('energy_bolt')), 1)
        cast = self.fixture.decoded(self.view.drain(1), 0x4e31, 2, self.actor.ref.uid)
        self.assertEqual(len(cast), 1)
        from tools.local_original_session.hunt_bot import scalar
        self.assertEqual(scalar(cast[0], 1), 18)
        self.assertNotIn(6, cast[0])  # no guessed projectile UID/raw coords
        self.assertNotIn(7, cast[0])

    def test_priority_emergency_heal_then_self_shield_then_attack(self):
        self.enemy()
        self.actor.shield_until = 0
        self.owner_state.hp = 35
        self.step()
        self.assertEqual(self.magic.events[-1]['spell'], 'heal')
        self.assertGreater(self.owner_state.hp, 35)
        self.assertEqual(self.record.mp, 36)
        frames = self.view.drain(1)
        self.assertTrue(self.fixture.decoded(frames, 0x4e38, 1, 1))
        self.assertTrue(self.fixture.decoded(frames, 0x4ed8, 1, 1))
        self.owner_state.hp = 55
        self.step(11)
        self.assertEqual(self.magic.events[-1]['spell'], 'shield')
        self.assertEqual(self.magic.events[-1]['target'], self.entity.uid)
        self.assertEqual(self.actor.shield_until, 1211)
        self.step(12)
        self.assertEqual(self.magic.events[-1]['spell'], 'energy_bolt')

    def test_heal_hysteresis_and_support_off(self):
        self.owner_state.hp = 35
        self.step()
        self.assertTrue(self.actor.emergency_owner)
        self.owner_state.hp = 50
        self.step(11)
        self.assertEqual(len(self.events('heal')), 2)
        self.record.support_enabled = False
        self.owner_state.hp = 1
        self.step(12)
        self.assertEqual(len(self.events('heal')), 2)
        self.assertEqual(self.owner_state.hp, 1)

    def test_recover_preserves_reserve_then_resumes_after_actual_regen(self):
        self.enemy()
        self.record.mp = 10  # reserve8 + bolt3: insufficient
        self.step()
        self.assertEqual(self.actor.action, 'RECOVER')
        self.assertEqual(self.record.mp, 10)
        for now in range(11, 27):
            self.step(now)
        self.assertTrue(self.events('recover'))
        # T=max(8+3, ceil(.4*40))=16; one idle recovery grants6.
        self.assertTrue(self.events('energy_bolt'))
        self.assertEqual(self.events('energy_bolt')[0]['mp_before'], 16)
        self.assertGreaterEqual(self.record.mp, 8)

    def test_unreachable_reserve_never_clamped_away(self):
        self.enemy()
        self.record.max_mp = self.record.mp = 8
        self.step()
        self.assertEqual(self.actor.action, 'RECOVER')
        self.assertFalse(self.events('energy_bolt'))
        self.owner_state.hp = 1
        self.step(11)
        self.assertEqual(self.record.mp, 4)
        self.assertTrue(self.events('heal'))

    def test_position_range_and_hold(self):
        enemy = self.enemy(self.entity.x + 11, self.entity.y)
        position = self.entity.x, self.entity.y
        self.record.movement_mode = 'HOLD'
        self.step()
        self.assertEqual((self.entity.x, self.entity.y), position)
        self.assertEqual(self.record.mp, 40)
        self.record.movement_mode = 'FOLLOW'
        self.step(11)
        self.assertEqual(self.actor.action, 'POSITION')
        self.assertNotEqual((self.entity.x, self.entity.y), position)
        self.step(12)
        self.assertTrue(self.events('energy_bolt'))

    def test_blocked_position_abandons_without_spend_or_repeat(self):
        self.enemy()
        with patch.object(self.view.terrain, 'can_step', return_value=False):
            self.step()
            self.assertEqual(self.actor.action, 'RETURN')
            self.assertIsNone(self.actor.target)
            self.assertEqual(len(self.events('position_abandoned')), 1)
            self.step(13)
            self.assertEqual(len(self.events('position_abandoned')), 1)
            self.assertEqual(self.record.mp, 40)

    def test_moving_target_cannot_reset_position_budget(self):
        enemy = self.enemy(self.entity.x + 20, self.entity.y)
        for index in range(6):
            self.view.entities.move(enemy.uid, 0, enemy.x + 1, enemy.y)
            self.step(10 + index * .7)
        self.assertIsNone(self.actor.target)
        self.assertTrue(self.events('position_abandoned'))
        self.assertEqual(self.record.mp, 40)

    def test_dismiss_resummon_cannot_reset_spell_reuse(self):
        self.owner_state.hp = 1
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.owner, 'heal', 10))
        before = self.record.mp
        self.view.companions.dismiss(2, 10.1)
        fresh = self.view.summon_companion(2, 1)
        entity = self.view.entities.resolve(fresh.ref)
        self.assertFalse(self.magic.cast(fresh, entity, self.owner, 'heal', 10.2))
        self.assertEqual(self.record.mp, before)

    def test_stale_target_and_unlearned_spell_never_spend(self):
        enemy = self.enemy()
        self.view.entities.kill(enemy.uid)
        self.step()
        self.assertEqual(self.record.mp, 40)
        self.record.learned_spells = ()
        self.assertFalse(self.magic.eligible(self.actor, 'heal'))
        self.assertFalse(self.magic.cast(self.actor, self.entity, self.owner, 'heal', 11))

    def test_shield_affects_incoming_ac_then_expires_without_stacking(self):
        enemy, monster = self.fixture.monster()
        profile = self.view.companion_profiles[2]
        from tools.local_original_session.world_combat import Swing
        with patch('tools.local_original_session.world_combat.npc_hits_pc', return_value=Swing(False, 0)) as hit:
            self.view.combat.npc_companion_swing(monster, self.entity.uid, profile, 10)
            self.assertEqual(hit.call_args.args[1].ac, profile.ac - 2)
            self.view.combat.npc_companion_swing(monster, self.entity.uid, profile, 1200)
            self.assertEqual(hit.call_args.args[1].ac, profile.ac)
        self.record.support_enabled = False
        self.step(1201)
        self.assertEqual(self.actor.shield_until, 0)
        self.assertTrue(self.events('shield_expired'))

    def test_display_requires_opt_in_and_heal_clamps_without_resurrection(self):
        self.magic.display = False
        self.owner_state.hp = 99
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.owner, 'heal', 10))
        self.assertEqual(self.owner_state.hp, 100)
        self.assertFalse(self.fixture.decoded(self.view.drain(1), 0x4e31, 2, self.entity.uid))
        self.owner_state.dead, self.owner_state.hp = True, 0
        before = self.record.mp
        self.assertFalse(self.magic.cast(self.actor, self.entity, self.owner, 'heal', 11))
        self.assertEqual(self.record.mp, before)

    def test_l1j_formula_dice_narrowing_and_mr_branches(self):
        from tools.local_original_session.world_combat import companion_magic_damage, companion_magic_heal
        from unittest.mock import Mock
        p = self.magic.spells['energy_bolt']['formula']['parameters']
        # (8+5)*1.5625 ->20, noncritical, MR100=>.5 / MR101=>.5.
        self.assertEqual(companion_magic_damage(p, 18, Mock(randint=Mock(side_effect=[5, 100])), mr=100), 10)
        self.assertEqual(companion_magic_damage(p, 18, Mock(randint=Mock(side_effect=[5, 100])), mr=101), 10)
        h = self.magic.spells['heal']['formula']['parameters']
        rng = Mock(randint=Mock(return_value=4))
        self.assertEqual(companion_magic_heal(h, 18, 0, self.magic.bonus, rng), 20)
        self.assertEqual(rng.randint.call_count, 5)  # base2 + INT18 bonus3


if __name__ == '__main__':
    unittest.main()
