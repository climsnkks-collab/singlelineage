"""Fixed knight exchange checks; arithmetic and disposable-save development only.

The fixture supplies synthetic materials, level and polymorph. It does not
establish normal producers, terrain/access, initial NPC-menu selection, native
input/rendering or a full gameplay PASS. No sockets or game process are used.
"""
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import world_feature_quest as feature, world_quest as q
from tools.local_original_session.world_quest_store import _state, _state_row

MARK = 'knight_mark_jim_gratitude'
GUNTER = 'knight_gunter_shelob_claw'
SCALE = 'knight_gerard_ramia_scale'
SHIELD = 'knight_gerard_gratitude_shield'
BELT = 'knight_julie_bravery_belt'
HOOD = 'knight_aanon_red_hood'


class KnightPureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs = {d.quest_id: d for d in q.load_quests()}

    def accept(self, quest, step, completed=(), *, level=45, character='knight'):
        d = self.defs[quest]
        return q.accept_quest(d, q.QuestState(quest), class_key=character, level=level,
            reference_steps={'Level30': step}, completed_quests=frozenset(completed))

    def finish(self, quest, state, step, completed, materials, **options):
        d = self.defs[quest]
        args = dict(npc_key=d.recipient_key or d.npc_key, action='questcomplete',
            policy='l1j_local', reference_steps={'Level30': step},
            completed_quests=frozenset(completed))
        args.update(options)
        return q.complete_quest(d, state, materials, **args)

    def test_fixed_materials_prerequisites_and_local_steps(self):
        expected = {MARK: ([(687, 1), (707, 1)], [(688, 1)], (0, 1, 6, 7)),
            GUNTER: ([(121, 1)], [(123, 1)], (1, 2, 2, 3)),
            SCALE: ([(686, 1)], [(687, 1)], (3, 4, 4, 5)),
            SHIELD: ([(688, 1)], [(666, 1)], (5, 6, 7, 255)),
            BELT: ([(335, 20), (334, 1), (12112, 1)], [(770, 1)], None)}
        for quest, (materials, rewards, steps) in expected.items():
            with self.subTest(quest=quest):
                d = self.defs[quest]
                self.assertEqual([(o.key, o.count) for o in d.objectives], materials)
                self.assertEqual([(r.item_id, r.count) for r in d.rewards], rewards)
                if steps:
                    self.assertEqual(tuple(s[1] for s in (d.required_reference_step,
                        d.accepted_reference_step, d.required_completion_step,
                        d.completed_reference_step)), steps)
        self.assertEqual(self.defs[MARK].required_quests, (HOOD,))
        self.assertEqual(self.defs[BELT].required_quests, (SHIELD,))
        self.assertIsNone(self.defs[BELT].required_reference_step)
        self.assertEqual(self.defs[BELT].npc_key, 'l1j:70805')

    def test_mark_cannot_use_fake_materials_to_skip_actual_1001(self):
        self.assertEqual(self.accept(MARK, 0).reason, 'prerequisite_missing')
        self.assertEqual(self.accept(MARK, 0, (HOOD,)).reason, 'accepted')
        self.assertEqual(self.accept(MARK, 0, (HOOD,), level=29).reason, 'ineligible')
        self.assertEqual(self.accept(MARK, 0, (HOOD,), character='wizard').reason, 'ineligible')

    def test_acceptance_and_turnin_steps_are_separate_and_do_not_mutate_snapshot(self):
        refs = {'Level30': 1}
        d = self.defs[GUNTER]
        accepted = q.accept_quest(d, q.QuestState(GUNTER), class_key='knight', level=30,
            reference_steps=refs, completed_quests=frozenset((HOOD,)))
        self.assertEqual(accepted.reason, 'accepted')
        self.assertEqual(refs, {'Level30': 1})
        self.assertEqual(self.finish(GUNTER, accepted.state, 1, (HOOD,), {121: 1}).reason,
                         'reference_step_mismatch')
        result = self.finish(GUNTER, accepted.state, 2, (HOOD,), {121: 1})
        self.assertEqual(result.reason, 'completion_proposed')
        self.assertEqual(result.rewards, (q.ItemAmount(123, 1),))

    def test_jim_fixed_consumes_both_potion_and_key_only_at_six(self):
        state = self.accept(MARK, 0, (HOOD,)).state
        for step in (0, 1, 5, 7, 255):
            result = self.finish(MARK, state, step, (HOOD,), {687: 1, 707: 1})
            self.assertEqual(result.reason, 'reference_step_mismatch')
            self.assertFalse(result.consumed or result.rewards)
        for materials in ({687: 1}, {707: 1}, {}):
            self.assertEqual(self.finish(MARK, state, 6, (HOOD,), materials).reason,
                             'requirements_missing')
        result = self.finish(MARK, state, 6, (HOOD,), {687: 2, 707: 2})
        self.assertEqual(result.consumed, (q.ItemAmount(687, 1), q.ItemAmount(707, 1)))
        self.assertEqual(result.rewards, (q.ItemAmount(688, 1),))
        self.assertEqual(self.finish(MARK, state, 6, (HOOD,), {687: 1, 707: 1},
                                     npc_key='l1j:70775').reason, 'wrong_turn_in')

    def test_jim_uses_current_projected_skeleton_and_actual_step(self):
        pc = NS(profile=NS(character_class=1))
        self.assertTrue(feature._quest_jim_admitted(pc, {'Level30': 6}, 2374))
        for step, sprite in ((5, 2374), (7, 2374), (6, 1), (6, None), (6, '2374')):
            self.assertFalse(feature._quest_jim_admitted(pc, {'Level30': step}, sprite))
        pc.profile.character_class = 3
        self.assertFalse(feature._quest_jim_admitted(pc, {'Level30': 6}, 2374))

    def test_julie_requires_normal_shield_completion_and_level45(self):
        for completed, level, reason in (((), 45, 'prerequisite_missing'),
                ((SHIELD,), 44, 'ineligible'), ((SHIELD,), 45, 'accepted')):
            self.assertEqual(self.accept(BELT, 255, completed, level=level).reason, reason)
        state = self.accept(BELT, 255, (SHIELD,)).state
        materials = {335: 20, 334: 1, 12112: 1}
        for template in materials:
            missing = dict(materials)
            missing[template] -= 1
            result = self.finish(BELT, state, 255, (SHIELD,), missing)
            self.assertEqual(result.reason, 'requirements_missing')
            self.assertFalse(result.rewards or result.consumed)
        result = self.finish(BELT, state, 255, (SHIELD,), materials)
        self.assertEqual(result.rewards, (q.ItemAmount(770, 1),))
        self.assertEqual(self.finish(BELT, result.state, 255, (SHIELD,), materials).reason,
                         'already_completed')
        self.assertEqual(materials, {335: 20, 334: 1, 12112: 1})

    def test_classic_default_still_cannot_award_and_state_format_is_unchanged(self):
        state = self.accept(BELT, 255, (SHIELD,)).state
        result = self.finish(BELT, state, 255, (SHIELD,), {335: 20, 334: 1, 12112: 1},
                             policy='classic')
        self.assertEqual(result.reason, 'policy_unselected')
        self.assertEqual(_state(_state_row(state)), state)
        self.assertEqual(set(_state_row(state)),
                         {'quest_id', 'accepted', 'completed', 'counts', 'seen_events'})

    def test_knight_page_links_do_not_bypass_existing_lyra_renewal_commit(self):
        quest = 'mainland_lyra_totem_settlement'
        state = q.QuestState(quest, accepted=True, completed=True, counts=(1,) * 5, cycles=1)
        commits = []
        store = NS(reference_steps=lambda uid, key: {},
            get=lambda uid, key: state if key == quest else q.QuestState(key),
            commit=lambda *args, **kwargs: commits.append((args, kwargs)))
        pc = NS(dead=False, hp=100, profile=NS(character_class=1, level=45))
        host = NS(_world_quest_dialogues={d.npc_id: d for d in q.load_quest_dialogues()},
            _world_quests=self.defs, _world_quest_store=store,
            _world=NS(combat=NS(pcs={1: pc})))
        source = NS(delivered=True, retired=False)
        menu = NS(fields={1: 811, 2: b'lyraEv5'}, source=source)
        sent = []
        ctx = NS(pc_uid=1, state=NS(menu=menu, window=None),
            wire=NS(dialogue_frame=lambda fields: fields), pending=[], send_frame=sent.append)
        feature._world_quest_action(host, ctx, NS(npc=NS(npc_id=70811)), menu,
                                    {1: 811, 2: b'lyraEv8'}, 0)
        self.assertEqual(len(commits), 1)
        after = commits[0][0][2]
        self.assertTrue(after.accepted)
        self.assertFalse(after.completed)
        self.assertEqual(after.cycles, 1)
        self.assertEqual(ctx.state.menu.fields[2], b'lyraEv8')


class KnightStoreTests(unittest.TestCase):
    """Requires working disposable-save permissions; never a gameplay PASS."""
    def setUp(self):
        from tools.local_original_session.world_quest_tests import _QuestFixture, _item_fields
        self.item = _item_fields
        self.f = _QuestFixture(self)
        self.sprite = 1
        self.f.host.realm = NS(service=lambda writer: NS(snapshot=lambda: NS(uid=1)),
                              _actor_for=lambda position: {3: self.sprite})
        self.f.ctx.writer = object()
        self.f.pc.profile = replace(self.f.pc.profile, character_class=1, level=45)
        # UID 101-103 belong to the existing Jem fixture; replace_kit permits
        # removal and appended UIDs, but cannot change their item templates.
        self.f.change_inventory([self.item(100, 7, 20), self.item(104, 639),
            self.item(105, 633), self.item(106, 650), self.item(107, 121),
            self.item(108, 686), self.item(109, 707), self.item(110, 335, 20),
            self.item(111, 334), self.item(112, 12112)])

    def counts(self):
        result = Counter()
        for row in self.f.rows().values():
            result[row[2]] += row[4]
        return result

    def hood(self):
        for stem, action, npc in (('riky1', 'queststart', 70798),
                ('riky3', 'questcomplete', 70798), ('aanon4', 'queststart', 70802),
                ('aanon5', 'questcomplete', 70802)):
            self.f.call(stem, action, npc=npc)

    def before_jim(self):
        self.hood()
        for stem, action, npc in (('mark1', 'queststart', 70775),
                ('gunterkE1', 'queststart', 70522), ('gunterkE2', 'questcomplete', 70522),
                ('gerardkE1', 'queststart', 70794), ('gerardkE2', 'questcomplete', 70794),
                ('gerardkE3', 'queststart', 70794)):
            self.f.call(stem, action, npc=npc)
        self.sprite = 2374  # Synthetic core projection; not a scroll-use claim.

    def test_full_exchange_restore_once_and_other_character_preserved(self):
        f = self.f
        other = f.inv.restore(2)
        self.before_jim()
        self.assertEqual(f.store.reference_steps(1, 'knight'), {'Level30': 6})
        self.assertEqual((self.counts()[687], self.counts()[688]), (1, 0))
        f.reopen()
        self.assertEqual(f.store.reference_steps(1, 'knight'), {'Level30': 6})
        f.call('jim3', 'questcomplete', npc=70555)
        self.assertEqual((self.counts()[687], self.counts()[707], self.counts()[688]), (0, 0, 1))
        self.assertEqual(f.store.reference_steps(1, 'knight'), {'Level30': 7})
        f.call('gerardkE4', 'questcomplete', npc=70794)
        self.assertEqual(f.store.reference_steps(1, 'knight'), {'Level30': 255})
        f.call('ladark3', 'queststart', npc=70805)
        f.call('ladark7', 'questcomplete', npc=70805)
        self.assertEqual(self.counts(), Counter({7: 20, 652: 1, 123: 1, 666: 1, 770: 1}))
        final = f.adapter.inventory_frame
        f.reopen()
        self.assertEqual(f.adapter.inventory_frame, final)
        self.assertEqual(f.inv.restore(2), other)
        self.assertTrue(all(f.store.get(1, quest).completed for quest in (MARK,GUNTER,SCALE,SHIELD,BELT)))
        with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
            f.call('ladark7', 'questcomplete', npc=70805)
        self.assertFalse(f.sent)
        self.assertEqual(f.adapter.inventory_frame, final)

    def test_missing_key_and_reverted_projection_leave_all_participants_unchanged(self):
        self.before_jim()
        f = self.f
        f.change_inventory([row for row in f.rows().values() if row[2] != 707])
        before, state = f.adapter.inventory_frame, f.store.get(1, MARK)
        with self.assertRaisesRegex(ValueError, '^QUEST_REQUIREMENTS_MISSING$'):
            f.call('jim3', 'questcomplete', npc=70555)
        self.assertEqual(f.adapter.inventory_frame, before)
        self.assertEqual(f.store.get(1, MARK), state)
        self.assertEqual(f.store.reference_steps(1, 'knight'), {'Level30': 6})
        self.sprite = 1
        with self.assertRaisesRegex(ValueError, '^QUEST_JIM_SKELETON_AND_STEP_REQUIRED$'):
            f.call('jim3', 'questcomplete', npc=70555)
        self.assertFalse(f.sent or f.ctx.commit_attempted)

    def test_interrupted_jim_save_recovers_same_consumption_reward_and_step(self):
        self.before_jim()
        f = self.f
        with patch.object(f.store, '_write_rows', side_effect=OSError('TEST_JIM_SAVE')):
            with self.assertRaisesRegex(OSError, 'TEST_JIM_SAVE'):
                f.call('jim3', 'questcomplete', npc=70555)
        self.assertFalse(f.sent)
        self.assertTrue(f.store.intent_path.exists())
        f.reopen()
        self.assertFalse(f.store.intent_path.exists())
        self.assertTrue(f.store.get(1, MARK).completed)
        self.assertEqual(f.store.reference_steps(1, 'knight'), {'Level30': 7})
        self.assertEqual((self.counts()[687], self.counts()[707], self.counts()[688]), (0, 0, 1))
        before = f.adapter.inventory_frame
        with self.assertRaisesRegex(ValueError, '^QUEST_JIM_SKELETON_AND_STEP_REQUIRED$'):
            f.call('jim3', 'questcomplete', npc=70555)
        self.assertEqual(f.adapter.inventory_frame, before)


if __name__ == '__main__':
    unittest.main()
