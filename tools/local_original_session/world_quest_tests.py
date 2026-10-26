"""Offline development tests of quest arithmetic, not a packet/game PASS."""
from dataclasses import replace
import unittest

from tools.local_original_session.world_quest import (
    ItemAmount, Objective, QuestDef, QuestEvent, QuestState, accept_quest,
    complete_quest, evaluate_quest, load_quests, on_event,
)


class QuestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quests = {q.quest_id: q for q in load_quests()}

    def setUp(self):
        self.quest = self.quests['ti_jem_cursed_spellbook']
        self.empty = QuestState(self.quest.quest_id)
        self.active = accept_quest(self.quest, self.empty,
                                   class_key='wizard', level=15).state
        self.inventory = {648: 1, 649: 1}

    def finish(self, state=None, inventory=None, **kwargs):
        options = dict(npc_key=self.quest.npc_key, action='questcomplete', policy='l1j_local')
        options.update(kwargs)
        return complete_quest(self.quest, state or self.active,
                              self.inventory if inventory is None else inventory, **options)

    def test_data_local_policy_and_classic_template_namespace(self):
        self.assertEqual(len(self.quests), 3)
        self.assertEqual(self.quest.objectives, (Objective('collect', 648, 1), Objective('collect', 649, 1)))
        self.assertEqual(self.quest.rewards, (ItemAmount(644, 1),))
        self.assertTrue(all(q.calculation_policy == 'l1j_local' for q in self.quests.values()))

    def test_accept_eligibility_and_no_input_mutation(self):
        self.assertEqual(accept_quest(self.quest, self.empty, class_key='knight', level=15).reason, 'ineligible')
        self.assertEqual(accept_quest(self.quest, self.empty, class_key='wizard', level=14).reason, 'ineligible')
        self.assertFalse(self.empty.accepted)
        self.assertTrue(self.active.accepted)
        self.assertEqual(accept_quest(self.quest, self.active, class_key='wizard', level=15).reason, 'already_accepted')

    def test_inventory_rechecked_after_item_loss(self):
        self.assertTrue(evaluate_quest(self.quest, self.active, self.inventory).conditions_met)
        lost = {648: 1, 649: 0}
        self.assertFalse(evaluate_quest(self.quest, self.active, lost).conditions_met)
        result = self.finish(inventory=lost)
        self.assertEqual(result.reason, 'requirements_missing')
        self.assertEqual((result.consumed, result.rewards), ((), ()))

    def test_default_classic_never_emits_candidate_rewards(self):
        result = complete_quest(self.quest, self.active, self.inventory,
                                npc_key=self.quest.npc_key, action='questcomplete')
        self.assertEqual(result.reason, 'policy_unselected')
        self.assertFalse(result.state.completed)
        self.assertEqual((result.consumed, result.rewards), ((), ()))

    def test_exact_consumption_reward_and_returned_state(self):
        inventory = {648: 4, 649: 2, 7: 500}
        result = self.finish(inventory=inventory)
        self.assertEqual(result.reason, 'completion_proposed')
        self.assertEqual(result.consumed, (ItemAmount(648, 1), ItemAmount(649, 1)))
        self.assertEqual(result.rewards, (ItemAmount(644, 1),))
        self.assertTrue(result.state.completed)
        self.assertFalse(self.active.completed)
        self.assertEqual(inventory, {648: 4, 649: 2, 7: 500})

    def test_duplicate_completion_and_reaccept_refused(self):
        completed = self.finish().state
        again = self.finish(state=completed)
        self.assertEqual(again.reason, 'already_completed')
        self.assertEqual((again.consumed, again.rewards), ((), ()))
        self.assertEqual(accept_quest(self.quest, completed, class_key='wizard', level=15).reason, 'already_completed')

    def test_wrong_turn_in_or_l1j_action_cannot_complete(self):
        for options in ({'npc_key': 'l1j:70522'}, {'action': 'request cursed spellbook'}):
            with self.subTest(options=options):
                result = self.finish(**options)
                self.assertEqual(result.reason, 'wrong_turn_in')
                self.assertFalse(result.rewards)

    def test_no_turn_in_before_acceptance(self):
        self.assertEqual(self.finish(state=self.empty).reason, 'not_accepted')

    def test_book_phase_requires_previous_material_in_current_inventory(self):
        book = self.quests['ti_jem_book_of_magic']
        state = accept_quest(book, QuestState(book.quest_id), class_key='wizard', level=15,
                              reference_steps={'Level15': 0}).state
        self.assertFalse(evaluate_quest(book, state, {647: 1}).conditions_met)
        first = self.finish()
        # Simulate the external owner's successful atomic application to a NEW
        # inventory snapshot. Calculation itself never makes this item available.
        after_owner_commit = {644: first.rewards[0].count, 647: 1}
        result = complete_quest(book, state, after_owner_commit,
                                npc_key=book.npc_key, action='questcomplete', policy='l1j_local',
                                reference_steps={'Level15': 0})
        self.assertEqual(result.consumed, (ItemAmount(644, 1), ItemAmount(647, 1)))
        self.assertEqual(result.rewards, (ItemAmount(645, 1),))
        self.assertFalse(evaluate_quest(book, state, {647: 1}).conditions_met)

    def test_reference_step_required_at_acceptance_and_rechecked_at_completion(self):
        for quest_id, step, inventory, class_key in (
            ('ti_jem_book_of_magic', 0, {644: 1, 647: 1}, 'wizard'),
            ('ti_gunter_secret_of_life', 1, {677: 1}, 'royal'),
        ):
            with self.subTest(quest_id=quest_id):
                definition = self.quests[quest_id]
                empty = QuestState(quest_id)
                self.assertEqual(accept_quest(definition, empty, class_key=class_key, level=15).reason,
                                 'reference_state_required')
                self.assertEqual(accept_quest(definition, empty, class_key=class_key, level=15,
                                             reference_steps={'Level15': 255}).reason, 'reference_step_mismatch')
                state = accept_quest(definition, empty, class_key=class_key, level=15,
                                     reference_steps={'Level15': step}).state
                self.assertTrue(state.accepted)
                for snapshot, expected in ((None, 'reference_state_required'),
                                           ({'Level15': 255}, 'reference_step_mismatch')):
                    blocked = complete_quest(definition, state, inventory, npc_key=definition.npc_key,
                                              action='questcomplete', policy='l1j_local', reference_steps=snapshot)
                    self.assertEqual(blocked.reason, expected)
                    self.assertFalse(blocked.consumed or blocked.rewards)
                result = complete_quest(definition, state, inventory, npc_key=definition.npc_key,
                                         action='questcomplete', policy='l1j_local',
                                         reference_steps={'Level15': step})
                self.assertEqual(result.reason, 'completion_proposed')

    def event_fixture(self):
        # Synthetic pure API fixture only; NOT an extra shipped quest.
        definition = QuestDef('test:events', 'fixture', 'test:npc', ('wizard',), 1,
                              (Objective('kill', 0, 2), Objective('talk', 'test:recipient', 1)),
                              (ItemAmount(7, 1),), 'finish', 'l1j_local')
        state = accept_quest(definition, QuestState(definition.quest_id), class_key='wizard', level=1).state
        return definition, state

    def test_events_match_identity_deduplicate_and_clamp(self):
        definition, state = self.event_fixture()
        event = QuestEvent('kill', 0, 'actual-death:1')
        state = on_event(definition, state, event, {}).state
        self.assertEqual(on_event(definition, state, event, {}).reason, 'duplicate_event')
        unrelated = on_event(definition, state, QuestEvent('kill', 245, 'other'), {})
        self.assertEqual(unrelated.reason, 'unrelated_event')
        self.assertEqual(unrelated.state, state)
        for event_id in ('actual-death:2', 'actual-death:3'):
            state = on_event(definition, state, QuestEvent('kill', 0, event_id), {}).state
        self.assertEqual(state.counts, (2, 0))
        self.assertFalse(evaluate_quest(definition, state, {}).conditions_met)
        state = on_event(definition, state, QuestEvent('talk', 'test:recipient', 'dialogue:1'), {}).state
        self.assertTrue(evaluate_quest(definition, state, {}).conditions_met)
        result = complete_quest(definition, state, {}, npc_key='test:npc', action='finish', policy='l1j_local')
        self.assertEqual(result.rewards, (ItemAmount(7, 1),))
        self.assertEqual(on_event(definition, result.state, QuestEvent('kill', 0, 'late'), {}).reason, 'inactive')

    def test_collect_progress_ignores_historical_counts(self):
        state = replace(self.active, counts=(100, 100))
        self.assertEqual(evaluate_quest(self.quest, state, {}).counts, (0, 0))
        self.assertFalse(evaluate_quest(self.quest, state, {}).conditions_met)

    def test_same_template_material_requirements_aggregate(self):
        definition = replace(self.quest, objectives=(Objective('collect', 648, 2), Objective('collect', 648, 3)))
        self.assertFalse(evaluate_quest(definition, self.active, {648: 3}).conditions_met)
        result = complete_quest(definition, self.active, {648: 5}, npc_key=definition.npc_key,
                                action='questcomplete', policy='l1j_local')
        self.assertEqual(result.consumed, (ItemAmount(648, 5),))

    def test_unresolved_objective_or_reward_never_partially_turns_in(self):
        definition = replace(self.quest, objectives=(Objective('collect', None, 1),))
        state = replace(self.active, counts=(0,))
        self.assertTrue(evaluate_quest(definition, state, self.inventory).unresolved)
        result = complete_quest(definition, state, self.inventory, npc_key=definition.npc_key,
                                action='questcomplete', policy='l1j_local')
        self.assertEqual(result.reason, 'unresolved')
        self.assertFalse(result.consumed or result.rewards)
        definition = replace(self.quest, rewards=(ItemAmount(None, 1),))
        result = complete_quest(definition, self.active, self.inventory, npc_key=definition.npc_key,
                                action='questcomplete', policy='l1j_local')
        self.assertEqual(result.reason, 'unresolved_reward')
        self.assertFalse(result.consumed or result.rewards)

    def test_wrong_state_and_invalid_quantities_refused(self):
        with self.assertRaises(ValueError):
            evaluate_quest(self.quest, QuestState('foreign'), {})
        for inventory in ({648: -1}, {648: True}, {True: 1}):
            with self.subTest(inventory=inventory), self.assertRaises(ValueError):
                evaluate_quest(self.quest, self.active, inventory)
        with self.assertRaises(ValueError):
            evaluate_quest(self.quest, replace(self.active, counts=(1,)), {})

    def test_inactive_event_never_counts(self):
        definition, state = self.event_fixture()
        result = on_event(definition, replace(state, accepted=False), QuestEvent('kill', 0, 'before'), {})
        self.assertEqual(result.reason, 'inactive')
        self.assertEqual(result.state.counts, (0, 0))


if __name__ == '__main__':
    unittest.main()
