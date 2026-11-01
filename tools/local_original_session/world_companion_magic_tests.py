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
from tools.local_original_session import ats_config_codec as codec
from tools.local_original_session import world_feature_magic


class _DisplayCtx:
    """Only the shared magic_cast_display hook a real ctx registers."""
    def __init__(self, view):
        self.world = view

    def run_sync_hooks(self, name, *args):
        if name == 'magic_cast_display':
            world_feature_magic._world_magic_display(self, *args)


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
        self.magic.ctx = _DisplayCtx(self.view)
        self.view.companion_ai.magic = self.magic
        self.configure(sequence_spells=(3,), buff_spells=(2,))
        self.record.level = 5
        self.record.learned_spells = (0, 2, 3)
        self.record.mp = self.record.max_mp = 40
        self.actor.shield_until = 1200
        self.record.combat_mode = 'ASSIST'
        self.record.movement_mode = 'FOLLOW'
        self.owner_state = self.view.combat.pcs[1]
        self.view.drain(1)

    def configure(self, **options):
        self.policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(**options)),
                                             {0: 'heal', 2: 'shield', 3: 'energy_bolt'})
        self.magic.policy_for = lambda _: self.policy

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

    def test_sequence_order_overrides_heal_urgency_and_skips_failed_slot(self):
        self.configure(sequence_spells=(3, 0))
        enemy = self.enemy()
        self.view.spawner.slot_for(enemy.uid)[1].hp = 1000
        self.record.hp = 1
        self.owner_state.hp = self.owner_state.max_hp
        self.step()
        self.assertEqual(self.magic.events[-1]['spell'], 'energy_bolt')
        self.step(11)
        self.assertEqual(self.magic.events[-1]['spell'], 'heal')
        self.assertEqual(self.magic.events[-1]['target'], self.entity.uid)
        self.assertEqual(self.owner_state.hp, self.owner_state.max_hp)
        self.record.mp = 3  # heal costs4: failed first slot skips to bolt3
        self.configure(sequence_spells=(0, 3))
        self.step(12)
        self.assertEqual(self.magic.events[-1]['spell'], 'energy_bolt')
        self.assertEqual(self.record.mp, 0)

    def test_selected_heal_condition_sees_owner_and_self_hp_without_hysteresis(self):
        self.configure(conditional=((2, 50, 0),))
        self.owner_state.hp = 1
        self.step()
        self.assertEqual(self.events('heal')[-1]['target'], self.owner.uid)
        self.assertGreater(self.owner_state.hp, 1)
        self.owner_state.hp = self.owner_state.max_hp
        self.record.hp = 1
        self.step(11)
        self.assertEqual(self.events('heal')[-1]['target'], self.entity.uid)
        self.record.hp = self.record.max_hp
        self.step(12)
        self.assertEqual(len(self.events('heal')), 2)
        self.record.support_enabled = False
        self.record.hp = 1
        self.step(13)
        self.assertEqual(len(self.events('heal')), 2)

    def test_no_ats_has_melee_but_no_default_magic_even_when_owner_hurt(self):
        self.magic.policy_for = lambda _: None
        enemy = self.enemy(self.entity.x + 1, self.entity.y)
        intents = []
        self.view.companion_ai.attack_consumer = intents.append
        self.actor.shield_until = 0
        self.record.hp = self.owner_state.hp = 1
        self.step()
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].target_ref, enemy.ref)
        self.assertEqual(self.record.mp, 40)
        self.assertFalse(any(self.events(name) for name in ('heal', 'shield', 'energy_bolt')))

    def test_empty_and_invalid_ats_never_fill_default_spells(self):
        self.enemy()
        self.actor.shield_until = 0
        self.record.hp = self.owner_state.hp = 1
        for index, wrapper in enumerate((codec.wrap_blob(codec.build_ats()), b'broken')):
            self.policy = codec.companion_policy(wrapper, {})
            self.magic.policy_for = lambda _: self.policy
            self.step(10 + index)
        self.assertEqual(self.record.mp, 40)
        self.assertFalse(any(self.events(name) for name in ('heal', 'shield', 'energy_bolt')))

    def test_unknown_condition_skips_and_records_then_next_sequence_can_cast(self):
        self.configure(conditional=((987, 100, 0),))
        self.record.hp = 1
        self.step()
        self.assertFalse(self.events('heal'))
        self.assertEqual(len(self.events('ats_unresolved')), 1)
        self.step(11)
        self.assertEqual(len(self.events('ats_unresolved')), 1)
        self.configure(sequence_spells=(0,))
        self.step(12)
        self.assertTrue(self.events('heal'))

    def test_cross_type_order_is_row_order_and_all_conditions_see_self(self):
        self.enemy()
        self.record.hp = 1
        self.owner_state.hp = 1
        self.configure(sequence_spells=(3,), conditional=((3, 90, 0),))
        self.step()
        self.assertEqual(self.magic.events[-1]['spell'], 'energy_bolt')
        self.policy['battle_slots'].reverse()  # conditional row is now above sequence
        self.step(11)
        self.assertEqual(self.magic.events[-1]['spell'], 'heal')
        self.assertGreater(self.owner_state.hp, 1)

    def test_all_six_conditions_gate_real_casts(self):
        cases = ((1, 50, 'hp', 20, 10), (2, 50, 'hp', 10, 30),
                 (3, 50, 'mp', 40, 10), (4, 50, 'mp', 10, 40),
                 (5, 5, None, None, None), (6, 1, None, None, None))
        for kind, value, resource, passing, failing in cases:
            with self.subTest(kind=kind):
                self.magic.reset_sequence(self.actor)
                self.configure(conditional=((kind, value, 3),))
                enemy = self.enemy()
                self.view.spawner.slot_for(enemy.uid)[1].hp = 1000
                self.record.max_hp = self.record.max_mp = 40
                self.record.hp = self.record.mp = 40
                if resource:
                    setattr(self.record, resource, passing)
                start = 20 + kind * 10
                before = len(self.events('energy_bolt'))
                self.step(start)
                self.assertEqual(len(self.events('energy_bolt')), before + 1)
                if resource:
                    setattr(self.record, resource, failing)
                self.step(start + 1)
                self.assertEqual(len(self.events('energy_bolt')), before + 1)

    def test_and_applies_to_sequence_and_condition_rows_without_type_bypass(self):
        enemy = self.enemy()
        self.view.spawner.slot_for(enemy.uid)[1].hp = 1000
        self.configure(sequence_spells=(3,), conditional=((1, 50, 3), (4, 25, 3), (6, 1, 3)))
        self.record.max_hp = 40
        self.record.hp, self.record.mp = 30, 40  # MP condition fails
        self.step(10)
        self.assertFalse(self.events('energy_bolt'))
        self.record.mp = 8
        self.step(11)
        self.assertEqual(len(self.events('energy_bolt')), 1)
        self.record.mp = 8
        self.step(12)  # all duplicate rows share spellRowID3's cap
        self.assertEqual(len(self.events('energy_bolt')), 1)
        self.assertEqual(self.magic.battle_state(self.actor)[3]['count'], 1)

    def test_first_time_evaluation_survives_later_and_failure_and_failed_cast(self):
        enemy = self.enemy()
        self.view.spawner.slot_for(enemy.uid)[1].hp = 1000
        self.configure(conditional=((5, 5, 3), (4, 25, 3)))
        self.step(10)  # time passes, MP condition fails
        state = self.magic.battle_state(self.actor)[3]
        self.assertEqual(state, {'at': 10})
        self.record.mp = 2  # predicates pass at15, actual cost check fails
        self.step(14.99)
        self.assertFalse(self.events('energy_bolt'))
        self.step(15)
        self.assertEqual(state, {'at': 10})
        self.record.mp = 8
        self.step(16)
        self.assertEqual(state, {'at': 16, 'count': 1})
        self.step(20.99)
        self.assertEqual(len(self.events('energy_bolt')), 1)
        self.step(21)
        self.assertEqual(state, {'at': 21, 'count': 2})

    def test_spell_row_states_are_independent_and_sequence_casts_count(self):
        enemy = self.enemy()
        self.view.spawner.slot_for(enemy.uid)[1].hp = 1000
        self.record.hp = 1
        self.configure(sequence_spells=(3,), conditional=((6, 1, 0),))
        self.step(10)
        self.step(11)
        states = self.magic.battle_state(self.actor)
        self.assertEqual({key: state['count'] for key, state in states.items() if 'count' in state}, {3: 2})
        self.policy['battle_slots'].reverse()
        self.step(12)
        self.assertEqual(states[0]['count'], 1)
        self.assertEqual(states[3]['count'], 2)
        self.record.hp = 1
        self.step(13)
        self.assertEqual(states[0]['count'], 1)
        self.assertEqual(states[3]['count'], 3)

    def test_time_and_count_reset_on_target_resummon_and_reconnect(self):
        self.configure(conditional=((5, 99, 0), (6, 1, 0)))
        for index, transition in enumerate(('initial', 'target', 'resummon', 'reconnect')):
            with self.subTest(transition=transition):
                now = 10 + index * 2
                if transition == 'target':
                    self.enemy()
                elif transition in ('resummon', 'reconnect'):
                    if transition == 'reconnect':
                        profile = self.view.combat.pcs[1].profile
                        status = dict(self.view.combat.pcs[1].status_fields)
                        self.view.leave_pc(1)
                        self.view.update_pc(1, 0, 100, 100)
                        self.view.bind_pc(1, profile, status)
                        self.owner = self.view.entities.get(1)
                    else:
                        self.view.companions.dismiss(2, now)
                    self.actor = self.view.summon_companion(2, 1)
                    self.entity = self.view.entities.resolve(self.actor.ref)
                self.record.hp = 1
                self.step(now)
                self.assertEqual(len(self.events('heal')), index + 1)
                self.assertEqual(self.magic.battle_state(self.actor)[0], {'at': now, 'count': 1})
                self.record.hp = 1
                self.step(now + 1)
                self.assertEqual(len(self.events('heal')), index + 1)

    def test_sequence_resets_on_target_switch_resummon_and_new_consumer(self):
        self.configure(sequence_spells=(0, 3))
        first = self.enemy()
        self.record.hp = 1
        self.step(10)  # heal -> next is bolt
        self.record.hp = 1
        self.step(11)
        self.assertEqual(self.magic.events[-1]['spell'], 'energy_bolt')
        self.step(12)  # heal -> next is bolt again
        self.record.hp = 1
        second = self.enemy()
        self.assertNotEqual(first.ref, second.ref)
        self.step(13)
        self.assertEqual(self.magic.events[-1]['spell'], 'heal')
        self.view.companions.dismiss(2, 13.1)
        self.actor = self.view.summon_companion(2, 1)
        self.entity = self.view.entities.resolve(self.actor.ref)
        self.record.hp = 1
        self.step(14)
        self.assertEqual(self.magic.events[-1]['spell'], 'heal')
        self.magic.sequences.clear()  # new server/consumer has no sequence state
        self.record.hp = 1
        self.step(15)
        self.assertEqual(self.magic.events[-1]['spell'], 'heal')

    def test_no_implicit_mp_reserve_or_recovery_gate(self):
        self.enemy()
        self.record.mp_reserve = 40  # old non-ATS knob must not suppress selected bolt
        self.record.mp = 3
        self.step()
        self.assertEqual(self.record.mp, 0)
        self.assertTrue(self.events('energy_bolt'))
        self.assertFalse(self.actor.recovering)

    def test_regeneration_without_magic_selection_does_not_grant_spells(self):
        self.magic.policy_for = lambda _: None
        self.record.mp = 0
        for now in range(10, 28):
            self.step(now)
        self.assertTrue(self.events('recover'))
        self.assertFalse(self.events('energy_bolt'))
        self.assertFalse(self.events('heal'))

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
        self.step(13)
        self.assertTrue(self.events('energy_bolt'))

    def test_blocked_melee_approach_does_not_create_magic_retreat(self):
        self.enemy()
        with patch.object(self.view.terrain, 'can_step', return_value=False):
            self.step()
            self.assertEqual(self.actor.action, 'POSITION')
            self.assertIsNotNone(self.actor.target)
            self.assertFalse(self.events('position_abandoned'))
            self.step(13)
            self.assertFalse(self.events('position_abandoned'))
            self.assertEqual(self.record.mp, 40)

    def test_moving_target_uses_ordinary_melee_approach(self):
        enemy = self.enemy(self.entity.x + 20, self.entity.y)
        for index in range(6):
            self.view.entities.move(enemy.uid, 0, enemy.x + 1, enemy.y)
            self.step(10 + index * .7)
        self.assertEqual(self.actor.target, enemy.ref)
        self.assertFalse(self.events('position_abandoned'))
        self.assertEqual(self.record.mp, 40)

    def test_magic_reuse_and_mp_recovery_allow_melee_approach_and_swing(self):
        enemy = self.enemy()
        slot = self.view.spawner.slot_for(enemy.uid)[1]
        slot.hp = 1000  # survive both spells and the real basic attack consumer
        ai = self.view.companion_ai
        intents = []
        consume = ai.attack_consumer
        def attack(intent):
            intents.append(intent)
            consume(intent)
        ai.attack_consumer = attack
        self.step()  # an actual cast consumes this decision
        self.assertEqual(len(self.events('energy_bolt')), 1)
        start = self.entity.x, self.entity.y
        self.actor.next_move_at = 10.15  # a due walk; summon retained its own reuse
        self.step(10.15)  # reuse pending: begin walking toward melee range
        self.assertNotEqual((self.entity.x, self.entity.y), start)
        self.view.entities.move(self.entity.uid, 0, enemy.x - 1, enemy.y)
        self.step(10.3)
        self.assertEqual(len(intents), 1)
        self.assertEqual(len(self.events('energy_bolt')), 1)
        self.assertEqual(self.record.mp, 37)
        due = self.actor.next_attack_at
        self.step(11)  # cast again while the independent melee reuse is pending
        self.assertEqual(len(self.events('energy_bolt')), 2)
        self.assertEqual(self.actor.next_attack_at, due)
        self.record.mp = 0
        self.step(due)
        self.assertFalse(self.actor.recovering)
        self.assertEqual(len(intents), 2)  # no MP still permits a due sword swing
        self.assertEqual(self.record.mp, 0)
        self.view.entities.move(self.entity.uid, 0, enemy.x - 4, enemy.y)
        start = self.entity.x, self.entity.y
        self.step(due + .7)
        self.assertNotEqual((self.entity.x, self.entity.y), start)
        # An explicitly selected self heal can consume a decision.
        self.configure(sequence_spells=(0,))
        self.record.hp = 1
        self.record.mp = 40
        self.owner_state.hp = 1
        self.actor.next_attack_at = 0
        self.step(due + 2)
        self.assertEqual(self.magic.events[-1]['spell'], 'heal')
        self.assertEqual(len(intents), 2)

    def test_dismiss_resummon_cannot_reset_spell_reuse(self):
        self.configure(sequence_spells=(0,))
        self.record.hp = 1
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.entity, 'heal', 10))
        before = self.record.mp
        self.view.companions.dismiss(2, 10.1)
        fresh = self.view.summon_companion(2, 1)
        entity = self.view.entities.resolve(fresh.ref)
        self.assertFalse(self.magic.cast(fresh, entity, entity, 'heal', 10.2))
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

    def test_display_is_default_and_selected_owner_heal_clamps(self):
        self.configure(sequence_spells=(0,))
        self.magic.display = False
        self.record.hp = self.record.max_hp - 1
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.entity, 'heal', 10))
        self.assertEqual(self.record.hp, self.record.max_hp)
        self.assertTrue(self.fixture.decoded(self.view.drain(1), 0x4e31, 2, self.entity.uid))
        self.owner_state.hp = 1
        before = self.record.mp
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.owner, 'heal', 11))
        self.assertEqual(self.record.mp, before - self.magic.cost('heal'))
        self.assertGreater(self.owner_state.hp, 1)

    def test_buff_only_selected_self_shield_refreshes_before_expiry(self):
        self.configure(buff_spells=(2,))
        self.owner_state.hp = 1
        self.actor.shield_until = 0
        self.step(10)
        self.assertEqual(self.magic.events[-1]['spell'], 'shield')
        expires = self.actor.shield_until
        self.step(expires - 60)
        self.assertEqual(len(self.events('shield')), 1)
        self.step(expires - 1)
        self.assertEqual(len(self.events('shield')), 2)
        self.assertGreater(self.actor.shield_until, expires)
        self.assertTrue(all(e['target'] == self.entity.uid for e in self.events('shield')))
        self.configure(sequence_spells=(3,))
        self.actor.shield_until = 0
        self.step(expires + 2)
        self.assertEqual(len(self.events('shield')), 2)

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


class RegenerationTests(unittest.TestCase):
    setUp = MagicTests.setUp
    configure = MagicTests.configure

    def start(self, *, level=10, con=16):
        self.record.level = level
        self.record.hp, self.record.max_hp = 1, 200
        self.record.mp = self.record.max_mp
        self.magic.attributes[2] = (8, 7, con, 18, 8, 18)
        self.actor.regen_at, self.actor.regen_points, self.actor.regen_activity = None, 0, 4
        self.magic.regen(self.actor, 10)

    def tick(self, now, points=4):
        self.actor.regen_activity = min(self.actor.regen_activity, points)
        self.magic.regen(self.actor, now)

    def test_hp_amount_and_level_timing_reuse_actual_pc_policy(self):
        policy = self.view.combat.regen
        for level, con in ((1, 9), (5, 16), (10, 18), (60, 16)):
            with self.subTest(level=level, con=con):
                self.start(level=level, con=con)
                ticks = (policy.hp_threshold(level) + policy.idle_points - 1) // policy.idle_points
                for now in range(11, 10 + ticks):
                    self.tick(now)
                    self.assertEqual(self.record.hp, 1)
                self.tick(10 + ticks - .001)
                self.assertEqual(self.record.hp, 1)
                self.tick(10 + ticks)
                self.assertEqual(self.record.hp, 1 + policy.hp_amount(con))
                self.assertEqual(self.record.mp, self.record.max_mp)

    def test_hp_clamps_and_late_callback_does_not_replay_missed_ticks(self):
        self.start()
        self.tick(1000)
        self.assertEqual(self.record.hp, 1)  # one tick, not 990 ticks
        self.tick(1001)
        self.record.hp = 199
        self.tick(1002)
        self.assertEqual(self.record.hp, 200)
        self.tick(1002)
        self.assertEqual(self.record.hp, 200)

    def test_movement_and_cast_activity_buckets_slow_hp_recovery(self):
        for points, ticks in ((2, 6), (1, 12)):
            with self.subTest(points=points):
                self.start()
                for tick in range(1, ticks):
                    self.tick(10 + tick, points)
                    self.assertEqual(self.record.hp, 1)
                self.tick(10 + ticks, points)
                self.assertEqual(self.record.hp, 8)
                # One busy bucket does not impose a fixed combat lockout.
                self.tick(11 + ticks)
                self.tick(12 + ticks)
                self.assertEqual(self.record.hp, 8)
                self.tick(13 + ticks)
                self.assertEqual(self.record.hp, 15)

    def test_real_movement_cast_and_admitted_basic_swing_lower_shared_activity(self):
        from tools.local_original_session.companion_ai import AttackIntent
        self.start()
        ai = self.view.companion_ai
        self.assertTrue(ai._move(self.actor, self.entity,
            lambda x, y: x == 105, (105, self.entity.y), 10))
        self.assertEqual(self.actor.regen_activity, 2)
        self.tick(11)
        self.assertEqual(self.magic.hp_regen_points[2][1], 2)
        self.assertTrue(self.magic.cast(self.actor, self.entity, self.entity, 'shield', 11))
        self.assertEqual(self.actor.regen_activity, 1)
        self.tick(12)
        self.assertEqual(self.magic.hp_regen_points[2][1], 3)
        enemy, _ = self.fixture.monster()
        self.view.entities.move(enemy.uid, self.entity.map_id, self.entity.x + 1, self.entity.y)
        self.view.spawner.slot_for(enemy.uid)[1].hp = 1000
        self.actor.target = enemy.ref
        before = self.view.spawner.slot_for(enemy.uid)[1].hp
        self.view.companion_attack(AttackIntent(self.actor.ref, enemy.ref, 12))
        self.assertEqual(self.actor.regen_activity, 1)
        self.tick(13)
        self.assertEqual(self.magic.hp_regen_points[2][1], 4)
        self.assertEqual(self.actor.regen_activity, 4)
        self.assertLessEqual(self.view.spawner.slot_for(enemy.uid)[1].hp, before)
        # A rejected dead target cannot turn an idle bucket into an attack.
        self.view.entities.kill(enemy.uid)
        self.view.companion_attack(AttackIntent(self.actor.ref, enemy.ref, 13))
        self.assertEqual(self.actor.regen_activity, 4)

    def test_hp_and_mp_follow_pc_policy_without_companion_food_weight_gates(self):
        for food, weight in ((2, 0), (3, 119), (40, 120)):
            with self.subTest(food=food, weight=weight):
                self.start()
                self.record.mp = 0
                self.record.equipment.update(food=food, weight240=weight)
                self.actor.regen_points = 60
                for now in (11, 12, 13):
                    self.tick(now)
                self.assertEqual(self.record.hp, 8)
                self.assertEqual(self.record.mp, self.view.combat.regen.mp_amount(18))

    def test_effective_con_and_worn_hp_bonus_survive_burden_like_pc(self):
        from types import SimpleNamespace
        self.start(con=10)
        calculated = SimpleNamespace(attributes=SimpleNamespace(con=18, wis=18),
                                     hp_regen_bonus=2, mp_regen_bonus=0,
                                     weight=SimpleNamespace(gauge=119))
        self.view.companion_ai.inventory = SimpleNamespace(
            calculated=lambda uid: (calculated, ()), blue_until={})
        self.record.equipment['weight240'] = 240  # stale metadata is not authority
        for now in (11, 12, 13):
            self.tick(now)
        self.assertEqual(self.record.hp, 1 + self.view.combat.regen.hp_amount(18) + 2)
        calculated.weight.gauge = 120
        for now in (14, 15, 16):
            self.tick(now)
        self.assertEqual(self.record.hp, 23)

    def test_dead_despawned_and_replaced_lifetimes_do_not_recover(self):
        self.start()
        self.tick(11)
        self.tick(12)
        self.view.companions.die(2, 12)
        self.record.mp = 0
        for now in (13, 1000):
            self.magic.regen(self.actor, now)
        self.assertEqual((self.record.hp, self.record.mp), (0, 0))
        self.assertEqual(self.actor.regen_points, 0)
        self.assertNotIn(2, self.magic.hp_regen_points)
        self.view.companions.revive(2, 1000, hp=1)
        self.magic.regen(self.actor, 1000)
        self.tick(1001)
        self.tick(1002)
        self.assertEqual(self.record.hp, 1)
        self.tick(1003)
        self.assertEqual(self.record.hp, 8)
        stale = self.actor
        self.view.companions.dismiss(2, 1003)
        self.magic.regen(stale, 1004)
        self.assertEqual(self.record.hp, 8)
        self.actor = self.view.summon_companion(2, 1)
        self.magic.regen(self.actor, 1004)
        self.tick(1005)
        self.tick(1006)
        self.assertEqual(self.record.hp, 8)
        self.tick(1007)
        self.assertEqual(self.record.hp, 15)


if __name__ == '__main__':
    unittest.main()
