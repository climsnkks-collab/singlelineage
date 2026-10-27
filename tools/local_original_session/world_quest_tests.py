"""Offline development tests of quest arithmetic, not a packet/game PASS."""
from dataclasses import replace
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session.world_quest import (
    ItemAmount, Objective, QuestDef, QuestEvent, QuestState, accept_quest,
    complete_quest, evaluate_quest, load_quests, on_event,
    load_quest_dialogues,
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

    def test_run403_dialogues_do_not_invent_gunter_acceptance(self):
        dialogues = {d.npc_id: d for d in load_quest_dialogues()}
        jem, gunter = dialogues[70531], dialogues[70522]
        self.assertEqual(jem.starts['jem1'], ('ti_jem_cursed_spellbook', 'jem3'))
        self.assertEqual(jem.starts['jem9'], ('ti_jem_book_of_magic', 'jem4'))
        self.assertEqual(gunter.pages['gunterp1'], ('queststart',))
        self.assertEqual(gunter.pages['gunterp10'], ('questcomplete',))
        self.assertFalse(gunter.starts)

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
        self.assertEqual(result.state.counts, (1, 1))
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


FIRST_QUEST = 'ti_jem_cursed_spellbook'
SECOND_QUEST = 'ti_jem_book_of_magic'


def _item_fields(uid, template, count=1):
    """Explicit disposable kit metadata, not source-owned acquisition evidence."""
    return {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 1, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'\0quest fixture', 22: 0,
            24: False, 25: 0, 26: False}


def _opcode(wire):
    return int.from_bytes(wire[2:4], 'little')


class _QuestFixture:
    """Actual disposable save owners and codecs; no game, socket or native input."""

    def __init__(self, case):
        from tools.local_original_session import inventory, inventory_store, world_combat
        from tools.local_original_session import world_feature_quest, world_handlers, world_progress
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_bridge import Context
        from tools.local_original_session.world_entities import EntityRegistry, Kind
        from tools.local_original_session.world_runtime import WorldRuntime
        from tools.local_original_session.world_town import TownNpcs, TownConfig, load_town
        self.inventory, self.inventory_store = inventory, inventory_store
        self.feature, self.h, self.progress_module = world_feature_quest, world_handlers, world_progress
        self.temp = tempfile.TemporaryDirectory()
        case.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        roster = inventory_store.realm.CharacterStore(self.profile)
        roster.create(inventory_store.realm.Creation('QuestMage', 3, 0, (13,) * 6))
        roster.create(inventory_store.realm.Creation('QuestRoyal', 0, 0, (13,) * 6))
        self.inv = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                  kit_policy=inventory.KIT_POLICY)
        frame = inventory.build_kit_frame([_item_fields(100, 7, 20), _item_fields(101, 648, 2),
                                           _item_fields(102, 649), _item_fields(103, 647)])
        self.inv.grant(1, frame)
        self.other_inventory = inventory.build_kit_frame([_item_fields(200, 7, 33)])
        self.inv.grant(2, self.other_inventory)
        data = load_m1()
        self.initial_exp = data.pc_exp[14]
        self.progress = world_progress.ProgressStore(self.profile)
        self.progress.commit(1, world_progress.Progress(self.initial_exp, 15, 200, 50, 500))
        fields = {1: 1, 2: 15, 4: 13, 5: 13, 6: 13, 7: 13, 8: 13, 9: 13,
                  10: 23, 11: 200, 12: 7, 13: 50, 14: 10, 15: 0, 16: 0,
                  17: 0, 18: 0, 20: 0}
        pc = world_combat.PcState(world_combat.PcProfile(15, 3, 0, 13, 13, con=13, wis=13),
                                  fields, 23, 200)
        entities = EntityRegistry()
        town = TownNpcs(entities, load_town(), TownConfig(candidate_npc_ids={70531}))
        self.npc, = town.register()
        entities.add(Kind.PC, self.npc.map_id, self.npc.x, self.npc.y, uid=1)
        world = NS(entities=entities, town=town, combat=NS(pcs={1: pc}, rng=random.Random(7)),
                   data=data, exp={1: self.initial_exp}, progress_dirty={}, drain=lambda uid: (),
                   runtime=WorldRuntime(clock=lambda: 0.0))
        self.host = NS(_world=world, _inventory_store=self.inv,
            _inventory_kit_policy=inventory.KIT_POLICY, _inventory_current_frame=frame,
            _world_progress=self.progress, _world_lawful={1: 500}, _item_equipment_effect=None)
        self.adapter = Context(self.host)
        self.sources = self.feature.setup_quests(self.adapter, town)
        self.feature._world_quest_initialize(self.adapter)
        self.host._world_handler_bindings = world_handlers.prepare_host_bindings(town, sources=self.sources)
        self.bindings = self.host._world_handler_bindings
        self.wire = self.bindings.wire
        self.sent = []
        self.ctx = NS(pc_uid=1, row={}, state=NS(menu=None, window=None),
                      pending=[], send_frame=self.sent.append, wire=self.wire, bindings=self.bindings)

    @property
    def store(self):
        return self.host._world_quest_store

    @property
    def pc(self):
        return self.host._world.combat.pcs[1]

    def rows(self):
        return {item.identifier: dict(item.raw_fields)
                for item in self.inventory.validate_kit_frame(self.adapter.inventory_frame)}

    def change_inventory(self, rows):
        before = self.adapter.inventory_frame
        after = self.inventory.build_kit_frame(list(rows))
        self.inv.replace_kit(1, before, after, append=True)
        self.adapter.inventory_frame = after

    def reopen(self):
        """New owners read disk as a reconnect/restart; no old cache is reused."""
        from tools.local_original_session.world_quest_store import QuestStore
        self.inv = self.inventory_store.InventoryStore(self.profile, policy=self.inventory_store.POLICY,
                                                       kit_policy=self.inventory.KIT_POLICY)
        self.progress = self.progress_module.ProgressStore(self.profile)
        self.host._inventory_store = self.inv
        self.host._world_progress = self.progress
        self.host._world_quest_store = QuestStore(self.inv, self.progress)
        self.adapter.inventory_frame = self.inv.restore(1)

    def call(self, stem, action, *, npc=70531, cookie=None):
        from tools.local_original_session.world_handlers import Dialogue
        self.sent.clear()
        self.ctx.pending.clear()
        self.ctx.commit_attempted = False
        source = NS(delivered=True, retired=False)
        menu = Dialogue({1: 811, 2: stem.encode()}, source)
        self.ctx.state.menu = menu
        fields = {1: 811, 2: action.encode(), 4: 0, 5: 0}
        if cookie is not None:
            fields[3] = cookie
        return self.feature._world_quest_action(self.adapter, self.ctx,
            NS(npc=NS(npc_id=npc)), menu, fields, 0)


class QuestFeatureTests(unittest.TestCase):
    """Direct adapter development checks with real saves, not a packet/game PASS."""

    def setUp(self):
        self.f = _QuestFixture(self)

    def test_town_setup_keeps_quest_rows_readable_by_other_shop_snapshots(self):
        from tools.local_original_session import world_feature_town, world_handlers, world_combat
        from tools.local_original_session.world_bridge import Context
        from tools.local_original_session.world_entities import EntityRegistry
        f = self.f
        host = NS(_world=NS(entities=EntityRegistry()), _world_warehouse_exp=False)
        world_feature_town.setup_town(Context(host), ())
        fields = [_item_fields(200 + i, template) for i, template in enumerate((644, 645, 647, 648, 649))]
        fields.append(_item_fields(300, 7, 50))
        host._inventory_current_frame = f.inventory.build_kit_frame(fields)
        host.realm = NS(service=lambda writer: NS(snapshot=lambda: object()))
        host._world_pc_profile = lambda writer, position: world_combat.PcProfile(15, 3, 0, 13, 13, con=13)
        ctx = NS(_owned=lambda: None, pc_uid=1, broker=host, writer=object(),
                 bindings=host._world_handler_bindings)
        snapshot = world_handlers.HostStore(ctx).snapshot(1, 0)
        self.assertEqual((snapshot.inventory.adena, snapshot.inventory.slots_used, snapshot.inventory.current_weight),
                         (50, 6, 20))
        self.assertIs(snapshot.revision, host._inventory_current_frame)

    def test_acceptance_is_durable_and_menu_response_requires_drain(self):
        f = self.f
        self.assertEqual([s.placement_key for s in f.sources], [(70531, 87501)])
        before = f.adapter.inventory_frame
        self.assertTrue(f.call('jem1', 'queststart'))
        self.assertEqual([_opcode(w) for w in f.sent], [0x4e44])
        self.assertEqual(f.ctx.state.menu.fields, {1: 811, 2: b'jem3'})
        self.assertFalse(f.ctx.state.menu.source.delivered)
        self.assertEqual(f.ctx.pending, [f.ctx.state.menu.source])
        self.assertNotIn('_world_quest_preview', f.ctx.row)
        accepted = f.store.get(1, FIRST_QUEST)
        self.assertTrue(accepted.accepted)
        self.assertFalse(accepted.completed)
        self.assertEqual(accepted.counts, (1, 1))
        f.reopen()
        self.assertEqual(f.store.get(1, FIRST_QUEST), accepted)
        self.assertEqual(f.adapter.inventory_frame, before)
        saved = f.store.path.read_bytes()
        f.call('jem1', 'queststart')
        self.assertEqual(f.ctx.state.menu.fields[2], b'jem3')
        self.assertEqual(f.store.path.read_bytes(), saved)
        self.assertFalse(f.ctx.commit_attempted)

    def test_both_jem_exchanges_use_owned_uids_and_persist_once_after_reconnect(self):
        f = self.f
        before = f.rows()
        f.call('jem1', 'queststart')
        f.call('jem3', 'questcomplete', cookie=b'\xff')
        first = f.rows()
        self.assertEqual(first[100], before[100])
        self.assertEqual(first[101], {**before[101], 4: 1})
        self.assertNotIn(102, first)
        self.assertEqual(first[103], before[103])
        reward_uid, = set(first) - set(before)
        self.assertGreater(reward_uid, max(before))
        self.assertEqual((first[reward_uid][2], first[reward_uid][4]), (644, 1))
        self.assertEqual(f.ctx.state.menu.fields[2], b'jem8')
        self.assertEqual([_opcode(w) for w in f.sent], [0x0965, 0x0978, 0x0964, 0x4e44])
        self.assertTrue(f.store.get(1, FIRST_QUEST).completed)
        f.reopen()
        with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
            f.call('jem3', 'questcomplete')
        self.assertEqual(f.sent, [])
        self.assertEqual(f.rows(), first)
        f.call('jem1', 'queststart')
        self.assertEqual(f.ctx.state.menu.fields[2], b'jem9')
        f.call('jem9', 'queststart')
        f.call('jem1', 'queststart')
        self.assertEqual(f.ctx.state.menu.fields[2], b'jem4')
        f.call('jem4', 'questcomplete', cookie=b'\x00')
        second = f.rows()
        self.assertNotIn(reward_uid, second)
        self.assertNotIn(103, second)
        magic_uid, = set(second) - set(first)
        self.assertGreater(magic_uid, reward_uid)
        self.assertEqual((second[magic_uid][2], second[magic_uid][4]), (645, 1))
        self.assertEqual(second[101], first[101])
        self.assertEqual(f.ctx.state.menu.fields[2], b'jem10')
        self.assertEqual(f.store.reference_steps(1, 'wizard'), {'Level15': 255})
        f.reopen()
        self.assertTrue(f.store.get(1, SECOND_QUEST).completed)
        self.assertEqual(f.store.get(1, SECOND_QUEST).counts, (1, 1))
        self.assertEqual(f.inv.restore(2), f.other_inventory)
        for stem in ('jem3', 'jem4'):
            with self.subTest(stem=stem), self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
                f.call(stem, 'questcomplete')
            self.assertEqual(f.sent, [])
            self.assertEqual(f.rows(), second)
        f.call('jem1', 'queststart')
        self.assertEqual(f.ctx.state.menu.fields[2], b'jem10')

    def test_local_wizard_level15_initialization_preserves_royal_reference(self):
        f = self.f
        royal = QuestState('fixture:royal')
        f.store.commit(1, royal, replace(royal, accepted=True), class_key='royal',
                       reference_before={}, reference_after={'Level15': 1})
        f.call('jem1', 'queststart')
        f.call('jem3', 'questcomplete')
        f.call('jem9', 'queststart')
        self.assertEqual(f.store.reference_steps(1, 'wizard'), {'Level15': 0})
        self.assertEqual(f.store.reference_steps(1, 'royal'), {'Level15': 1})
        self.assertEqual(f.store.reference_steps(2, 'wizard'), {})
        f.call('jem4', 'questcomplete')
        self.assertEqual(f.store.reference_steps(1, 'wizard'), {'Level15': 255})
        self.assertEqual(f.store.reference_steps(1, 'royal'), {'Level15': 1})
        f.reopen()
        self.assertEqual(f.store.reference_steps(1, 'wizard'), {'Level15': 255})
        self.assertEqual(f.store.reference_steps(1, 'royal'), {'Level15': 1})

    def test_gunter_zero_is_not_secret_of_life_acceptance(self):
        f = self.f
        with self.assertRaisesRegex(ValueError, '^QUEST_GUNTER_ZERO_PREREQUISITE_UNKNOWN$'):
            f.call('gunterp1', 'queststart', npc=70522)
        self.assertFalse(f.sent or f.ctx.row or f.store.path.exists())

    def test_dedicated_sender_cookie_is_opaque_and_never_a_quest_id(self):
        f = self.f
        for stem, npc in (('jem3', 70531), ('jem4', 70531), ('gunterp10', 70522)):
            for cookie in (None, b'\x00', b'\xff', b'1'):
                with self.subTest(stem=stem, cookie=cookie):
                    with self.assertRaisesRegex(ValueError, '^QUEST_NOT_ACCEPTED$'):
                        f.call(stem, 'questcomplete', npc=npc, cookie=cookie)
                    self.assertEqual(f.sent, [])
        with self.assertRaisesRegex(ValueError, '^QUEST_COMPLETE_NATIVE_COOKIE_BYTE_REQUIRED$'):
            f.call('jem3', 'questcomplete', cookie=b'fake-quest-id')
        self.assertFalse(f.sent or f.ctx.row or f.store.path.exists())

    def test_equipped_material_is_excluded_and_missing_requirements_change_nothing(self):
        f = self.f
        f.host._item_equipment_effect = NS(store=NS(restore=lambda uid, frame:
                                                  NS(weapon_uid=0, slots=((0, 102),))))
        f.call('jem1', 'queststart')
        self.assertEqual(f.store.get(1, FIRST_QUEST).counts, (1, 0))
        before, saved = f.adapter.inventory_frame, f.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, '^QUEST_REQUIREMENTS_MISSING$'):
            f.call('jem3', 'questcomplete')
        self.assertEqual(f.sent, [])
        self.assertFalse(f.ctx.commit_attempted)
        self.assertEqual(f.adapter.inventory_frame, before)
        self.assertEqual(f.inv.restore(1), before)
        self.assertEqual(f.store.path.read_bytes(), saved)

    def test_missing_reward_producer_never_consumes_or_sends_success(self):
        f = self.f
        f.call('jem1', 'queststart')
        before, accepted = f.adapter.inventory_frame, f.store.get(1, FIRST_QUEST)
        f.host._world_quest_reward_items = {}
        with self.assertRaisesRegex(ValueError, '^QUEST_REWARD_ITEM_SOURCE_REQUIRED$'):
            f.call('jem3', 'questcomplete')
        self.assertFalse(f.sent or f.ctx.commit_attempted)
        self.assertEqual(f.inv.restore(1), before)
        self.assertEqual(f.store.get(1, FIRST_QUEST), accepted)

    def test_interrupted_turn_in_has_no_success_and_recovers_forward_once(self):
        f = self.f
        f.call('jem1', 'queststart')
        before, accepted = f.adapter.inventory_frame, f.store.get(1, FIRST_QUEST)
        with patch.object(f.inv, 'replace_kit', side_effect=OSError('TEST_SAVE_INTERRUPTED')):
            with self.assertRaisesRegex(OSError, 'TEST_SAVE_INTERRUPTED'):
                f.call('jem3', 'questcomplete')
        self.assertEqual(f.sent, [])
        self.assertTrue(f.ctx.commit_attempted)
        self.assertTrue(f.ctx.state.menu.source.retired)
        self.assertEqual(f.adapter.inventory_frame, before)
        self.assertEqual(f.inv.restore(1), before)
        self.assertEqual(f.store.get(1, FIRST_QUEST), accepted)
        self.assertTrue(f.store.intent_path.exists())
        f.reopen()
        self.assertTrue(f.store.get(1, FIRST_QUEST).completed)
        self.assertFalse(f.store.intent_path.exists())
        recovered = f.adapter.inventory_frame
        with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
            f.call('jem3', 'questcomplete')
        self.assertFalse(f.sent or f.ctx.commit_attempted)
        self.assertEqual(f.adapter.inventory_frame, recovered)

    def test_positive_exp_is_explicit_synthetic_local_policy_and_preserves_full_status(self):
        from tools.local_original_session.world_m1_reward_tests import status_values
        from tools.local_original_session.world_progress import exp_percent
        f = self.f
        # Shipped Jem policy has no inferred quest EXP. Select a synthetic
        # positive LOCAL reward solely to exercise the existing growth adapter.
        definition = f.host._world_quests[FIRST_QUEST]
        self.assertEqual(definition.experience_reward, 0)
        gained = f.host._world.data.pc_exp[15] - f.initial_exp + 7
        f.host._world_quests[FIRST_QUEST] = replace(definition, experience_reward=gained)
        before = dict(f.pc.status_fields)
        f.call('jem1', 'queststart')
        f.call('jem3', 'questcomplete')
        saved = f.progress.get(1)
        self.assertEqual((saved.exp, saved.level), (f.initial_exp + gained, 16))
        self.assertGreater(saved.max_hp, before[11])
        self.assertGreaterEqual(saved.max_mp, before[13])
        statuses = [status_values(w) for w in f.sent if _opcode(w) == 0x4e38]
        self.assertEqual(len(statuses), 1)
        expected = {**before, 2: 16, 11: saved.max_hp, 13: saved.max_mp,
                    26: exp_percent(f.host._world.data, saved.exp, saved.level)}
        self.assertEqual(statuses[0], expected)
        self.assertEqual((f.pc.hp, f.pc.mp), (before[10], before[12]))
        self.assertEqual((f.pc.profile.level, f.pc.max_hp, f.pc.max_mp),
                         (saved.level, saved.max_hp, saved.max_mp))
        self.assertEqual(f.host._world.exp[1], saved.exp)
        self.assertFalse(any(0x0579 <= _opcode(w) <= 0x0588 for w in f.sent))
        f.reopen()
        self.assertEqual(f.progress.get(1), saved)

    def test_interrupted_exp_turn_in_settles_kill_dirty_before_close_and_recovers_once(self):
        from tools.local_original_session.world_feature_reward import _world_save_progress
        f = self.f
        f.call('jem1', 'queststart')
        # Explicit synthetic LOCAL EXP policy; the live kill projection is
        # newer than ProgressStore and must settle before the quest journal.
        current_exp = f.initial_exp + 3
        gained = f.host._world.data.pc_exp[15] - current_exp + 7
        definition = f.host._world_quests[FIRST_QUEST]
        f.host._world_quests[FIRST_QUEST] = replace(definition, experience_reward=gained)
        dirty = replace(f.progress.get(1), exp=current_exp)
        f.host._world.exp[1] = current_exp
        f.host._world.progress_dirty[1] = dirty
        expected_exp = current_exp + gained
        with patch.object(f.progress, 'commit', wraps=f.progress.commit) as commits, \
                patch.object(f.store, '_write_rows', side_effect=OSError('TEST_QUEST_ROW_SAVE')):
            with self.assertRaisesRegex(OSError, 'TEST_QUEST_ROW_SAVE'):
                f.call('jem3', 'questcomplete')
            # Inventory and EXP reached disk, while the final quest row did
            # not. No success/status/dialogue frame may escape this failure.
            self.assertEqual(f.sent, [])
            self.assertTrue(f.ctx.commit_attempted)
            self.assertTrue(f.ctx.state.menu.source.retired)
            self.assertTrue(f.store.intent_path.exists())
            self.assertFalse(f.store.get(1, FIRST_QUEST).completed)
            self.assertEqual([call.args[1].exp for call in commits.call_args_list],
                             [current_exp, expected_exp])
            partial = f.progress.get(1)
            self.assertEqual((partial.exp, partial.level), (expected_exp, 16))
            self.assertNotIn(1, f.host._world.progress_dirty)
            _world_save_progress(f.adapter, 1)  # the existing leave/close path
            self.assertEqual(commits.call_count, 2)
            self.assertEqual(f.progress.get(1), partial)
        f.reopen()
        self.assertTrue(f.store.get(1, FIRST_QUEST).completed)
        self.assertFalse(f.store.intent_path.exists())
        self.assertEqual(f.progress.get(1), partial)
        reward = [row for row in f.rows().values() if row[2] == 644]
        self.assertEqual(len(reward), 1)
        self.assertEqual(reward[0][4], 1)
        recovered = f.adapter.inventory_frame
        with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
            f.call('jem3', 'questcomplete')
        self.assertFalse(f.sent or f.ctx.commit_attempted)
        self.assertEqual(f.adapter.inventory_frame, recovered)
        self.assertEqual(f.progress.get(1), partial)


class QuestRoutingTests(unittest.IsolatedAsyncioTestCase):
    """Real decoder/router/current-menu checks and real saves; no ports."""

    async def asyncSetUp(self):
        import asyncio
        from tools.local_original_session import world_feature_town as town_feature
        self.f = f = _QuestFixture(self)
        self.h, self.host, self.wire, self.npc = f.h, f.host, f.wire, f.npc
        self.host._world_service_action = lambda *a: town_feature._world_service_action(f.adapter, *a)
        self.host._world_quest_action = lambda *a: f.feature._world_quest_action(f.adapter, *a)
        self.writer = object()
        self.lock = asyncio.Lock()
        await self.lock.acquire()
        self.row = dict(writer=self.writer, operation_lock=self.lock)
        self.host._world_pcs = {id(self.writer): (self.writer, 1)}
        self.host._world_bound = lambda writer: writer is self.writer

    async def asyncTearDown(self):
        self.lock.release()

    def context(self):
        return self.h.HostContext(self.host, self.writer, self.row, object(), self.lock)

    def action(self, name, cookie=None, target=None):
        return self.wire.dialogue.encode_haction_normal(
            self.npc.uid if target is None else target, name, cookie, (0, 0))

    async def select_and_accept(self):
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.CLICK, self.wire.click.encode_request(self.npc.uid))
        ctx.mark_delivered()
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.HACTION, self.action(b'queststart'))
        return ctx

    async def test_real_decoder_current_context_and_drain_before_durable_jem_completion(self):
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.CLICK, self.wire.click.encode_request(self.npc.uid))
        self.assertEqual(ctx.state.menu.fields[2], b'jem1')
        with self.assertRaisesRegex(ValueError, 'DRAINED_CURRENT_MENU_REQUIRED'):
            await self.h.dispatch(self.context(), self.h.HACTION, self.action(b'queststart'))
        self.assertFalse(self.f.store.get(1, FIRST_QUEST).accepted)
        ctx.mark_delivered()
        with self.assertRaisesRegex(ValueError, 'CURRENT_MENU_TARGET_REQUIRED'):
            await self.h.dispatch(self.context(), self.h.HACTION,
                                  self.action(b'queststart', target=self.npc.uid + 1))
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.HACTION, self.action(b'queststart'))
        self.assertEqual(ctx.state.menu.fields[2], b'jem3')
        self.assertEqual([_opcode(w) for w in ctx.frames], [0x4e44])
        self.assertTrue(self.f.store.get(1, FIRST_QUEST).accepted)
        with self.assertRaisesRegex(ValueError, 'DRAINED_CURRENT_MENU_REQUIRED'):
            await self.h.dispatch(self.context(), self.h.HACTION, self.action(b'questcomplete', b'\xff'))
        self.assertFalse(self.f.store.get(1, FIRST_QUEST).completed)
        ctx.mark_delivered()
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.HACTION, self.action(b'questcomplete', b'\xff'))
        self.assertEqual(ctx.state.menu.fields[2], b'jem8')
        self.assertTrue(ctx.commit_attempted)
        self.assertTrue(self.f.store.get(1, FIRST_QUEST).completed)
        self.assertEqual([_opcode(w) for w in ctx.frames], [0x0965, 0x0978, 0x0964, 0x4e44])
        self.assertEqual(self.f.inv.restore(1), self.f.adapter.inventory_frame)
        self.assertFalse(ctx.state.menu.source.delivered)

    async def test_old_menu_source_retires_on_reselection_and_restart_cannot_repeat_reward(self):
        ctx = await self.select_and_accept()
        source = ctx.state.menu.source
        ctx.mark_delivered()
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.CLICK, self.wire.click.encode_request(self.npc.uid))
        self.assertTrue(source.retired)
        self.assertFalse(ctx.current_source(source))
        self.assertFalse(ctx.state.menu.source.delivered)
        ctx.mark_delivered()
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.HACTION, self.action(b'queststart'))
        self.assertEqual(ctx.state.menu.fields[2], b'jem3')
        ctx.mark_delivered()
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.HACTION, self.action(b'questcomplete'))
        reward = self.f.adapter.inventory_frame
        self.f.reopen()
        # A fresh selected writer/row has no inherited menu or source lifetime.
        self.writer = object()
        self.row = dict(writer=self.writer, operation_lock=self.lock)
        self.host._world_pcs = {id(self.writer): (self.writer, 1)}
        ctx = self.context()
        with self.assertRaisesRegex(ValueError, 'CURRENT_MENU_REQUIRED'):
            await self.h.dispatch(ctx, self.h.HACTION, self.action(b'questcomplete'))
        self.assertFalse(ctx.frames or ctx.commit_attempted)
        await self.h.dispatch(ctx, self.h.CLICK, self.wire.click.encode_request(self.npc.uid))
        ctx.mark_delivered()
        ctx = self.context()
        await self.h.dispatch(ctx, self.h.HACTION, self.action(b'queststart'))
        self.assertEqual(ctx.state.menu.fields[2], b'jem9')
        self.assertEqual([_opcode(w) for w in ctx.frames], [0x4e44])
        self.assertEqual(self.f.adapter.inventory_frame, reward)

    async def test_after_request_persists_progress_from_actual_changed_inventory(self):
        f = self.f
        f.change_inventory([_item_fields(100, 7, 20)])
        ctx = await self.select_and_accept()
        self.assertEqual(f.store.get(1, FIRST_QUEST).counts, (0, 0))
        ctx.mark_delivered()
        f.change_inventory([_item_fields(100, 7, 20), _item_fields(301, 648), _item_fields(302, 649)])
        await f.feature._world_quest_after_request(f.adapter, self.writer, self.row,
                                                  object(), 0x4e3e, self.lock)
        self.assertEqual(f.store.get(1, FIRST_QUEST).counts, (1, 1))
        f.change_inventory([_item_fields(100, 7, 20), _item_fields(301, 648)])
        await f.feature._world_quest_after_request(f.adapter, self.writer, self.row,
                                                  object(), 0x4ed1, self.lock)
        self.assertEqual(f.store.get(1, FIRST_QUEST).counts, (1, 0))
        f.reopen()
        self.assertEqual(f.store.get(1, FIRST_QUEST).counts, (1, 0))
        self.assertFalse(f.store.get(1, FIRST_QUEST).completed)
        self.assertEqual(f.progress.get(1).exp, f.initial_exp)
        blocked = self.context()
        with self.assertRaisesRegex(ValueError, '^QUEST_REQUIREMENTS_MISSING$'):
            await self.h.dispatch(blocked, self.h.HACTION, self.action(b'questcomplete'))
        self.assertFalse(blocked.frames or blocked.commit_attempted)


if __name__ == '__main__':
    unittest.main()
