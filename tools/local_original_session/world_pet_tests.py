"""Pure pet calculations only; no game/server/packet/store or formal PASS.

Run: python -X utf8 -B -m tools.local_original_session.world_pet_tests
No test artifacts are written. Existing AI/entity types are imported read-only.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import unittest

from tools.local_original_session.world_pet import (
    EntityRef, FoodOffer, PetCommand, PetLife, PetOwner, PetState, State,
    TameTarget, activate_pet, ai_intent, award_pet_exp, collar_payload,
    command_pet, create_tamed_pet, exp_percent, level_by_exp, load_pets,
    offer_food,
    restore_collar,
)


class PetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_pets()

    def setUp(self):
        self.owner = PetOwner(1, 20, 6, 'crown', 6, 179)
        self.target = TameTarget(EntityRef(800, 2), 'wolf', 155, 9, 30, 1, 4)
        self.food = FoodOffer(1, 200, 40057, 9, 5)

    def tame(self, *, owner=None, target=None, food=None, **kwargs):
        return offer_food(self.catalog, owner or self.owner, target or self.target,
                          food or self.food, **kwargs)

    def pet(self):
        return create_tamed_pet(self.catalog, self.tame(), pet_id=1001,
                                collar_uid=2001, actor_ref=EntityRef(3001, 1))

    def test_catalog_keeps_backend_and_classic_namespaces_and_duplicates(self):
        self.assertEqual(len(self.catalog.species), 14)
        wolf = self.catalog.species['wolf']
        self.assertEqual(wolf.l1j_npc_id, 45043)
        self.assertEqual(wolf.classic_candidates, (9, 124, 126, 155, 10039, 10077, 10148))
        self.assertEqual(self.catalog.items[40057].classic_candidates, (9,))
        self.assertEqual(self.catalog.items[40056].classic_candidates, (10,))
        self.assertEqual(self.catalog.items[40060].classic_candidates, (37,))
        self.assertEqual(self.catalog.items[40314].classic_candidates, (361,))
        self.assertEqual(self.catalog.species['tiger'].classic_candidates, ())
        self.assertEqual(self.catalog.species['jindo_puppy'].classic_candidates, ())
        with self.assertRaises(TypeError):
            self.catalog.species['invented'] = wolf

    def test_success_transfers_offered_quantity_once_without_mutating_inputs(self):
        result = self.tame(quantity=3)
        self.assertTrue(result.tamed)
        self.assertEqual(result.transfer_count, 3)
        self.assertEqual(self.food.count, 5)
        self.assertEqual(self.target.hp, 9)
        with self.assertRaises(FrozenInstanceError):
            result.target.hp = 1

    def test_hp_boundary_uses_integer_division_and_strict_less_than(self):
        self.assertTrue(self.tame(target=replace(self.target, max_hp=31, hp=9)).tamed)
        at = self.tame(target=replace(self.target, max_hp=31, hp=10))
        self.assertFalse(at.tamed)
        self.assertEqual(at.reason, 'target_hp_too_high')
        self.assertEqual(at.transfer_count, 1)
        tiny = self.tame(target=replace(self.target, max_hp=2, hp=1))
        self.assertFalse(tiny.tamed)

    def test_dead_owned_and_summoned_targets_keep_transfer_on_tame_failure(self):
        for change, reason in (({'hp': 0}, 'target_dead'),
                               ({'master_uid': 99}, 'target_already_owned'),
                               ({'is_summon': True}, 'target_already_owned')):
            with self.subTest(change=change):
                result = self.tame(target=replace(self.target, **change))
                self.assertFalse(result.tamed)
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.transfer_count, 1)

    def test_ordinary_meat_cannot_substitute_for_floating_eye_meat(self):
        result = self.tame(food=replace(self.food, l1j_item_id=40056, classic_template_id=10))
        self.assertFalse(result.tamed)
        self.assertEqual(result.reason, 'wrong_food')
        self.assertEqual(result.transfer_count, 1)

    def test_rabbit_requires_carrot_and_other_species_requires_eye_meat(self):
        rabbit = replace(self.target, species_key='rabbit', classic_template_id=1387)
        carrot = replace(self.food, l1j_item_id=40060, classic_template_id=37)
        self.assertEqual(self.tame(target=rabbit).reason, 'wrong_food')
        self.assertTrue(self.tame(target=rabbit, food=carrot).tamed)
        self.assertEqual(self.tame(food=carrot).reason, 'wrong_food')

    def test_charisma_uses_class_bonus_and_existing_pet_cost(self):
        self.assertTrue(self.tame().tamed)  # 6+6-6 == 6
        low = self.tame(owner=replace(self.owner, charisma=5))
        self.assertEqual(low.reason, 'insufficient_charisma')
        self.assertEqual(low.transfer_count, 1)
        self.assertTrue(self.tame(owner=replace(self.owner, class_key='elf', charisma=0)).tamed)
        self.assertFalse(self.tame(owner=replace(self.owner, class_key='knight')).tamed)
        self.assertEqual(self.tame(owner=replace(self.owner, class_key='unknown')).transfer_count, 0)

    def test_capacity_is_post_transfer_and_exclusive_180(self):
        self.assertTrue(self.tame().tamed)
        result = self.tame(owner=replace(self.owner, inventory_slots_after_transfer=180))
        self.assertEqual(result.reason, 'no_collar_slot')
        self.assertEqual(result.transfer_count, 1)

    def test_ownership_quantity_and_mapping_fail_before_proposed_transfer(self):
        for food, kwargs, reason in (
            (replace(self.food, owner_uid=2), {}, 'food_not_owned'),
            (self.food, {'quantity': 6}, 'insufficient_food'),
            (replace(self.food, classic_template_id=10), {}, 'food_mapping_mismatch'),
            (replace(self.food, l1j_item_id=40314, classic_template_id=361), {}, 'unsupported_food'),
        ):
            with self.subTest(reason=reason):
                result = self.tame(food=food, **kwargs)
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.transfer_count, 0)
        bad = self.tame(target=replace(self.target, classic_template_id=45043))
        self.assertEqual(bad.reason, 'species_mapping_mismatch')
        self.assertEqual(bad.transfer_count, 0)

    def test_tiger_has_exact_one_of_sixteen_success_and_requires_real_draw(self):
        tiger = replace(self.target, species_key='tiger', classic_template_id=None)
        outcomes = [self.tame(target=tiger, tiger_roll=i) for i in range(16)]
        self.assertEqual(sum(r.tamed for r in outcomes), 1)
        self.assertTrue(outcomes[15].tamed)
        self.assertTrue(all(r.transfer_count == 1 for r in outcomes))
        for roll in (None, -1, 16, True):
            with self.subTest(roll=roll), self.assertRaises(ValueError):
                self.tame(target=tiger, tiger_roll=roll)
        # No draw is needed when admission has already failed.
        self.assertEqual(self.tame(target=replace(tiger, hp=10)).reason, 'target_hp_too_high')

    def test_resurrection_exception_is_tiger_raccoon_jindo_not_wolf(self):
        self.assertTrue(self.tame(target=replace(self.target, resurrected=True)).tamed)
        for key in ('tiger', 'raccoon', 'jindo_puppy'):
            target = replace(self.target, species_key=key, classic_template_id=None, resurrected=True)
            result = self.tame(target=target)
            self.assertEqual(result.reason, 'resurrected_target')
            self.assertEqual(result.transfer_count, 1)

    def test_invalid_numeric_snapshots_raise_without_mutation(self):
        for target in (replace(self.target, hp=-1), replace(self.target, hp=31),
                       replace(self.target, max_hp=0), replace(self.target, mp=5)):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.tame(target=target)
        for quantity in (0, -1, True, 1.5):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.tame(quantity=quantity)

    def test_binding_keeps_durable_pet_collar_and_live_actor_separate(self):
        pet = self.pet()
        self.assertEqual((pet.record.pet_id, pet.record.collar_uid, pet.actor_ref),
                         (1001, 2001, EntityRef(3001, 1)))
        self.assertNotEqual(pet.actor_ref, self.target.ref)
        self.assertEqual(pet.record.classic_template_id, 155)
        self.assertEqual((pet.record.exp, pet.record.level), (750, 5))
        self.assertEqual((pet.record.hp, pet.record.mp), (9, 1))  # no tame refill
        self.assertEqual(pet.record.mode, PetCommand.STAY)
        self.assertEqual(pet.life, PetLife.ACTIVE)

    def test_failed_or_unresolved_tame_cannot_create_real_pet(self):
        for outcome in (self.tame(target=replace(self.target, hp=10)),
                        self.tame(food=replace(self.food, classic_template_id=None)),
                        self.tame(target=replace(self.target, classic_template_id=None))):
            with self.subTest(outcome=outcome.reason), self.assertRaises(ValueError):
                create_tamed_pet(self.catalog, outcome, pet_id=1001,
                                 collar_uid=2001, actor_ref=EntityRef(3001, 1))
        with self.assertRaises(ValueError):
            create_tamed_pet(self.catalog, self.tame(), pet_id=1001,
                             collar_uid=2001, actor_ref=self.target.ref)

    def test_commands_enforce_owner_level_and_reject_inactive_pet(self):
        pet = self.pet()
        self.assertEqual(command_pet(pet, replace(self.owner, uid=2), 'attack').reason, 'not_owner')
        self.assertEqual(command_pet(pet, replace(self.owner, level=4), 'attack').reason, 'owner_level_too_low')
        stored = restore_collar(self.catalog, collar_payload(self.catalog, pet), owner_uid=1, collar_uid=2001)
        self.assertEqual(command_pet(stored, self.owner, 'follow').reason, 'pet_not_active')
        self.assertEqual(command_pet(pet, self.owner, 5).reason, 'unknown_command')

    def test_mode_changes_clear_old_attack_target(self):
        pet = command_pet(self.pet(), self.owner, 'attack', target_ref=EntityRef(4001, 2)).state
        self.assertEqual(pet.target_ref, EntityRef(4001, 2))
        for command in ('defend', 'stay', 'follow'):
            with self.subTest(command=command):
                result = command_pet(pet, self.owner, command)
                self.assertTrue(result.allowed)
                self.assertIsNone(result.state.target_ref)
        self.assertIsNotNone(pet.target_ref)
        self.assertFalse(command_pet(pet, self.owner, 'stay', target_ref=EntityRef(4001, 2)).allowed)
        self.assertFalse(command_pet(pet, self.owner, 'attack', target_ref=EntityRef(1, 1)).allowed)
        self.assertFalse(command_pet(pet, self.owner, 'attack', target_ref=pet.actor_ref).allowed)

    def test_ai_modes_reuse_states_without_scheduler_or_ai_loop(self):
        pet, owner_ref, enemy = self.pet(), EntityRef(1, 3), EntityRef(4001, 2)
        idle = ai_intent(pet, owner_ref=owner_ref, master_target=enemy, attacker=enemy)
        self.assertEqual((idle.state, idle.target_ref), (State.IDLE, None))
        attack = command_pet(pet, self.owner, 'attack').state
        intent = ai_intent(attack, owner_ref=owner_ref, master_target=enemy)
        self.assertEqual((intent.state, intent.target_ref), (State.CHASE, enemy))
        self.assertTrue(intent.accept_master_target)
        defense = command_pet(pet, self.owner, 'defend').state
        intent = ai_intent(defense, owner_ref=owner_ref, master_target=enemy)
        self.assertEqual((intent.state, intent.target_ref), (State.RETURN, owner_ref))
        self.assertFalse(intent.accept_master_target)
        self.assertEqual(ai_intent(defense, owner_ref=owner_ref, attacker=enemy).target_ref, enemy)
        follow = command_pet(attack, self.owner, 'follow').state
        intent = ai_intent(follow, owner_ref=owner_ref, master_target=enemy, attacker=enemy)
        self.assertEqual((intent.state, intent.target_ref), (State.RETURN, owner_ref))
        self.assertTrue(intent.follow_owner)
        self.assertFalse(intent.retaliate)

    def test_dismiss_proposes_wild_release_and_collar_removal_once_per_state(self):
        pet = self.pet()
        result = command_pet(pet, replace(self.owner, level=1), 'dismiss')
        self.assertTrue(result.allowed)  # L1J bypasses pet level on liberate
        self.assertEqual(result.state.life, PetLife.RELEASED)
        self.assertTrue(result.release_to_wild)
        self.assertEqual(result.remove_collar_count, 1)
        self.assertEqual(result.state.actor_ref, pet.actor_ref)  # cleanup input
        again = command_pet(result.state, self.owner, 'dismiss')
        self.assertFalse(again.allowed)
        self.assertEqual(again.remove_collar_count, 0)
        with self.assertRaises(ValueError):
            collar_payload(self.catalog, result.state)
        with self.assertRaises(ValueError):
            award_pet_exp(self.catalog, result.state, allocated_exp=1)

    def test_experience_thresholds_and_percent_are_inclusive(self):
        for exp, level, percent in ((0, 1, 0), (124, 1, 99), (125, 2, 0),
                                    (749, 4, 99), (750, 5, 0), (1295, 5, 99), (1296, 6, 0)):
            with self.subTest(exp=exp):
                self.assertEqual(level_by_exp(self.catalog, exp), level)
                self.assertEqual(exp_percent(self.catalog, exp), percent)
        self.assertEqual(level_by_exp(self.catalog, self.catalog.max_exp), 99)
        self.assertEqual(exp_percent(self.catalog, self.catalog.max_exp), 100)

    def test_below_level_boundary_does_not_heal(self):
        pet = self.pet()
        result = award_pet_exp(self.catalog, pet, allocated_exp=545)
        self.assertEqual((result.state.record.exp, result.levels_gained), (1295, 0))
        self.assertEqual((result.state.record.hp, result.state.record.mp), (9, 1))
        self.assertEqual(pet.record.exp, 750)

    def test_one_and_multiple_levels_apply_inclusive_draws_and_refill(self):
        pet = self.pet()
        one = award_pet_exp(self.catalog, pet, allocated_exp=546, growth_rolls=((3, 1),))
        self.assertEqual(one.levels_gained, 1)
        self.assertEqual((one.state.record.level, one.state.record.hp, one.state.record.mp), (6, 33, 5))
        many = award_pet_exp(self.catalog, pet, allocated_exp=1651,
                              growth_rolls=((3, 1), (9, 2)))
        self.assertEqual(many.levels_gained, 2)
        self.assertEqual((many.state.record.level, many.state.record.hp, many.state.record.mp), (7, 42, 7))

    def test_missing_extra_or_out_of_range_growth_draws_reject(self):
        pet = self.pet()
        for allocated, rolls in ((546, ()), (0, ((3, 1),)),
                                 (546, ((2, 1),)), (546, ((10, 1),)),
                                 (546, ((3, 0),)), (546, ((3, True),))):
            with self.subTest(rolls=rolls), self.assertRaises(ValueError):
                award_pet_exp(self.catalog, pet, allocated_exp=allocated, growth_rolls=rolls)
        self.assertEqual((pet.record.exp, pet.record.hp), (750, 9))

    def test_exp_rate_truncation_cap_and_invalid_awards(self):
        result = award_pet_exp(self.catalog, self.pet(), allocated_exp=3,
                                rate_numerator=1, rate_denominator=2)
        self.assertEqual((result.applied_exp, result.state.record.exp), (1, 751))
        pet = self.pet()
        top = replace(pet, record=replace(pet.record, level=99, exp=self.catalog.max_exp - 2))
        cap = award_pet_exp(self.catalog, top, allocated_exp=10)
        self.assertEqual((cap.applied_exp, cap.capped_excess), (2, 8))
        self.assertEqual(cap.state.record.exp, self.catalog.max_exp)
        for kwargs in ({'allocated_exp': -1}, {'allocated_exp': True},
                       {'allocated_exp': 1, 'rate_denominator': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                award_pet_exp(self.catalog, pet, **kwargs)

    def test_collar_json_roundtrip_preserves_identity_damage_and_mode_only(self):
        pet = command_pet(self.pet(), self.owner, 'attack', target_ref=EntityRef(4001, 2)).state
        payload = collar_payload(self.catalog, pet)
        encoded = json.dumps(payload)
        self.assertNotIn('actor_ref', encoded)
        self.assertNotIn('target_ref', encoded)
        restored = restore_collar(self.catalog, json.loads(encoded), owner_uid=1, collar_uid=2001)
        self.assertEqual(restored.record, pet.record)
        self.assertEqual(restored.life, PetLife.STORED)
        self.assertIsNone(restored.actor_ref)
        self.assertIsNone(restored.target_ref)
        payload['pet']['hp'] = 1
        self.assertEqual(restored.record.hp, 9)  # no mutable payload alias
        active = activate_pet(restored, actor_ref=EntityRef(5001, 4))
        self.assertEqual(active.actor_ref, EntityRef(5001, 4))
        self.assertEqual(active.record, pet.record)
        with self.assertRaises(ValueError):
            activate_pet(active, actor_ref=EntityRef(6001, 1))

    def test_collar_custody_schema_and_level_exp_mismatch_reject(self):
        payload = collar_payload(self.catalog, self.pet())
        for owner_uid, collar_uid in ((2, 2001), (1, 2002)):
            with self.subTest(owner_uid=owner_uid), self.assertRaises(ValueError):
                restore_collar(self.catalog, payload, owner_uid=owner_uid, collar_uid=collar_uid)
        for key, value in (('level', 6), ('exp', -1), ('owner_uid', True), ('mode', 'dismiss'),
                           ('species_key', 'invented'), ('hp', 31), ('actor_ref', {'uid': 3001})):
            bad = deepcopy(payload)
            bad['pet'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                restore_collar(self.catalog, bad, owner_uid=1, collar_uid=2001)
        bad = deepcopy(payload)
        bad['version'] = True
        with self.assertRaises(ValueError):
            restore_collar(self.catalog, bad, owner_uid=1, collar_uid=2001)
        self.assertEqual(payload['pet']['level'], 5)

    def test_dead_pet_cannot_command_gain_or_activate_and_keeps_damage_in_save(self):
        pet = self.pet()
        dead = replace(pet, record=replace(pet.record, hp=0))
        self.assertEqual(command_pet(dead, self.owner, 'attack').reason, 'pet_dead')
        self.assertEqual(ai_intent(dead, owner_ref=EntityRef(1, 2)).state, State.IDLE)
        with self.assertRaises(ValueError):
            award_pet_exp(self.catalog, dead, allocated_exp=100)
        stored = restore_collar(self.catalog, collar_payload(self.catalog, dead), owner_uid=1, collar_uid=2001)
        self.assertEqual(stored.record.hp, 0)
        with self.assertRaises(ValueError):
            activate_pet(stored, actor_ref=EntityRef(5001, 1))

    def test_state_rejects_dangling_active_or_saved_actor_references(self):
        pet = self.pet()
        with self.assertRaises(ValueError):
            PetState(pet.record, PetLife.ACTIVE)
        with self.assertRaises(ValueError):
            PetState(pet.record, PetLife.STORED, pet.actor_ref)
        with self.assertRaises(ValueError):
            ai_intent(pet, owner_ref=EntityRef(2, 1))


if __name__ == '__main__':
    unittest.main()
