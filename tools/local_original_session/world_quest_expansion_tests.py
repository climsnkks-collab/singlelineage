"""Fixed QuestT1/3002/3003 adapter checks; disposable saves, no sockets.

These are development checks. Starting materials are synthetic and do not
establish their normal producers or original-client menu/input equivalence.
"""
from collections import Counter
from dataclasses import replace
import unittest
from types import MethodType, SimpleNamespace as NS
from unittest.mock import patch

from tools.local_original_session import world_quest
from tools.local_original_session.world_quest_tests import _QuestFixture, _item_fields


ZERO = 'royal_zero_search_document'
BONE = 'wizard_gereng_undead_bone'
STAFF = 'wizard_gereng_crystal_staff'
OTH = 'elf_oth_orc_spellbooks'


class FixedExchangeTests(unittest.TestCase):
    def setUp(self):
        self.f = _QuestFixture(self)

    def counts(self):
        result = Counter()
        for row in self.f.rows().values():
            result[row[2] & 0xffffffff] += row[4]
        return result

    def seed_materials(self, *templates):
        f = self.f
        rows = list(f.rows().values())
        identifier = max(r[1] for r in rows)
        for template in templates:
            identifier += 1
            rows.append(_item_fields(identifier, template))
        f.change_inventory(rows)

    def wizard30(self):
        self.f.pc.profile = replace(self.f.pc.profile, level=30)

    def finish_jem(self):
        f = self.f
        for stem, action in (('jem1', 'queststart'), ('jem3', 'questcomplete'),
                             ('jem9', 'queststart'), ('jem4', 'questcomplete')):
            f.call(stem, action)

    def test_gereng_requires_actual_jem_completion_before_acceptance(self):
        self.wizard30()
        self.seed_materials(690, 709)
        f = self.f
        with self.assertRaisesRegex(ValueError, '^QUEST_PREREQUISITE_MISSING$'):
            f.call('gerengt1', 'queststart', npc=70009)
        self.assertFalse(f.store.get(1, BONE).accepted)
        self.assertFalse(f.sent)

    def test_actual_jem_reward_then_two_gereng_turnins_and_restore(self):
        self.wizard30()
        self.seed_materials(690, 709)
        f = self.f
        self.finish_jem()
        self.assertEqual(self.counts()[645], 1)
        f.call('gerengt1', 'queststart', npc=70009)
        f.call('gerengt2', 'questcomplete', npc=70009)
        self.assertEqual(f.ctx.state.menu.fields[2], b'gerengt3')
        intermediate = next(uid for uid, row in f.rows().items() if row[2] == 710)
        self.assertEqual((self.counts()[690], self.counts()[710]), (0, 1))
        f.reopen()
        # Re-click the original entry after reconnect: saved completion chooses
        # the next source-backed queststart page, as existing Jem does.
        f.call('gerengt1', 'queststart', npc=70009)
        self.assertEqual(f.ctx.state.menu.fields[2], b'gerengt3')
        f.call('gerengt3', 'queststart', npc=70009)
        f.call('gerengt4', 'questcomplete', npc=70009)
        self.assertNotIn(intermediate, f.rows())
        self.assertEqual((self.counts()[709], self.counts()[710], self.counts()[711]), (0, 0, 1))
        self.assertEqual(self.counts()[645], 1)
        final = f.adapter.inventory_frame
        f.reopen()
        self.assertEqual(f.adapter.inventory_frame, final)
        self.assertTrue(all(f.store.get(1, q).completed for q in (BONE, STAFF)))
        with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
            f.call('gerengt4', 'questcomplete', npc=70009)
        self.assertEqual(f.sent, [])
        self.assertEqual(f.adapter.inventory_frame, final)

    def test_second_gereng_does_not_accept_synthetic_intermediate_as_prerequisite(self):
        self.wizard30()
        self.seed_materials(710, 709)
        with self.assertRaisesRegex(ValueError, '^QUEST_PREREQUISITE_MISSING$'):
            self.f.call('gerengt3', 'queststart', npc=70009)
        self.assertFalse(self.f.store.get(1, STAFF).accepted)

    def test_zero_class_level_consumption_and_durable_once(self):
        f = self.f
        self.seed_materials(636)
        with self.assertRaisesRegex(ValueError, '^QUEST_INELIGIBLE$'):
            f.call('zero1', 'queststart', npc=70554)
        f.pc.profile = replace(f.pc.profile, character_class=0, level=14)
        with self.assertRaisesRegex(ValueError, '^QUEST_INELIGIBLE$'):
            f.call('zero1', 'queststart', npc=70554)
        f.pc.profile = replace(f.pc.profile, level=15)
        before = self.counts()
        f.call('zero1', 'queststart', npc=70554)
        f.call('zero3', 'questcomplete', npc=70554)
        expected = before.copy()
        expected[636] -= 1
        expected[646] += 1
        self.assertEqual(self.counts(), +expected)
        self.assertEqual(f.ctx.state.menu.fields[2], b'zero7')
        f.reopen()
        self.assertTrue(f.store.get(1, ZERO).completed)
        self.assertEqual(self.counts()[646], 1)
        with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
            f.call('zero3', 'questcomplete', npc=70554)
        self.assertEqual(f.sent, [])

    def test_fixed_gereng_contract_keeps_differences_from_l1j(self):
        definitions = {q.quest_id: q for q in world_quest.load_quests()}
        self.assertEqual([(o.key, o.count) for o in definitions[BONE].objectives], [(690, 1)])
        self.assertEqual([(r.item_id, r.count) for r in definitions[BONE].rewards], [(710, 1)])
        self.assertEqual([(o.key, o.count) for o in definitions[STAFF].objectives], [(709, 1), (710, 1)])
        self.assertEqual([(r.item_id, r.count) for r in definitions[STAFF].rewards], [(711, 1)])

    def test_promoted_quest_replaces_only_same_placement_lore_menu(self):
        from tools.local_original_session.world_town import TownSetup
        from tools.local_original_session.world_town_services import ServiceMenuSource
        f = self.f
        f.host._world_map_exp = 2
        zero_key = (70554, 87516)
        original = ServiceMenuSource(zero_key, 'zero2', {'zero2': ()})
        unrelated = ServiceMenuSource((70012, 87172), 'inn', {'inn': ()})
        setup = TownSetup(f.host._world.town, None, (original, unrelated), None)
        result = f.feature._world_quest_town_setup(f.adapter, setup)
        zero = [source for source in result.sources if source.placement_key == zero_key]
        self.assertEqual(len(zero), 1)
        self.assertEqual(zero[0].stem, 'zero1')
        self.assertEqual(zero[0].pages['zero1'], ('queststart',))
        self.assertIs(next(s for s in result.sources if s.placement_key == unrelated.placement_key),
                      unrelated)

    def test_local_jem_prerequisite_is_registered_and_publishable_without_native_identity(self):
        from tools.local_original_session.world_entities import EntityRegistry
        from tools.local_original_session.world_town import TownConfig, TownNpcs, TownSetup, load_town
        from tools.local_original_session.world_terrain import WorldTerrain
        from tools.local_original_session.world_visibility import town_spawn_frame
        f = self.f
        f.host._world_map_exp = 2
        terrain = WorldTerrain.load()
        self.assertFalse(terrain.can_stand(0, 32587, 32927))
        self.assertTrue(terrain.can_stand(0, 32587, 32926))
        town = TownNpcs(EntityRegistry(), load_town(), TownConfig(), passable=terrain.can_stand)
        town.register()
        result = f.feature._world_quest_town_setup(f.adapter, TownSetup(town, None, (), None))
        entity = next(e for e in town.present(0, 32587, 32927, 1)
                      if town.npc_for(e.uid).npc_id == 70531)
        self.assertEqual((entity.map_id, entity.x, entity.y), (0, 32587, 32926))
        appearance = town.appearance(entity.uid)
        self.assertIsNone(appearance.catalog_template_id)
        self.assertEqual(appearance.sprite_id, 1307)
        self.assertEqual(appearance.mapping_status, 'LOCAL_L1J_actor_identity_unknown')
        self.assertEqual(int.from_bytes(town_spawn_frame(entity, appearance)[2:4], 'little'), 0x4e96)
        self.assertEqual(next(s for s in result.sources if s.placement_key == (70531, 87501)).stem,
                         'jem1')


class OthChoiceTests(unittest.TestCase):
    """Synthetic materials exercise actual store/adapter, never normal drops."""

    def fixture(self):
        f = _QuestFixture(self)
        f.pc.profile = replace(f.pc.profile, character_class=2, level=15)
        f.change_inventory([_item_fields(100, 7, 20),
                            *(_item_fields(200 + t, t, 2) for t in range(640, 644))])
        return f

    @staticmethod
    def counts(f):
        return Counter({row[2]: row[4] for row in f.rows().values()})

    def test_both_binary_choices_consume_each_once_restore_and_block_other_choice(self):
        for choice, reward in ((0, 631), (1, 632)):
            with self.subTest(choice=choice):
                f = self.fixture()
                other = f.inv.restore(2)
                f.call('oth1', 'queststart', npc=70826)
                f.call('oth3', 'questcomplete', npc=70826, cookie=bytes([choice]))
                self.assertEqual(f.ctx.state.menu.fields[2], b'oth6')
                self.assertEqual(self.counts(f), Counter({7: 20, 640: 1, 641: 1, 642: 1, 643: 1, reward: 1}))
                self.assertEqual(f.store.get(1, OTH).cycles, 1)
                self.assertEqual(f.store.reference_steps(1, 'elf'), {'Level15': 255})
                final = f.adapter.inventory_frame
                f.reopen()
                self.assertEqual(f.adapter.inventory_frame, final)
                self.assertTrue(f.store.get(1, OTH).completed)
                self.assertEqual(f.inv.restore(2), other)
                for again in (choice, 1 - choice):
                    with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
                        f.call('oth3', 'questcomplete', npc=70826, cookie=bytes([again]))
                    self.assertFalse(f.sent or f.ctx.commit_attempted)
                    self.assertEqual(f.adapter.inventory_frame, final)
                f.call('oth1', 'queststart', npc=70826)
                self.assertEqual(f.ctx.state.menu.fields[2], b'oth6')
                self.assertEqual(f.adapter.inventory_frame, final)

    def test_invalid_or_missing_choice_cannot_mutate_or_default_to_first_reward(self):
        f = self.fixture()
        f.call('oth1', 'queststart', npc=70826)
        before, state, saved = f.adapter.inventory_frame, f.store.get(1, OTH), f.store.path.read_bytes()
        for cookie in (None, b'', b'0', b'1', b'\x02', b'\xff', b'\x00\x00'):
            with self.subTest(cookie=cookie):
                with self.assertRaisesRegex(ValueError, '^QUEST_(REWARD_CHOICE_REQUIRED|COMPLETE_NATIVE_COOKIE_BYTE_REQUIRED)$'):
                    f.call('oth3', 'questcomplete', npc=70826, cookie=cookie)
                self.assertFalse(f.sent or f.ctx.commit_attempted)
                self.assertEqual(f.adapter.inventory_frame, before)
                self.assertEqual(f.inv.restore(1), before)
                self.assertEqual(f.store.get(1, OTH), state)
                self.assertEqual(f.store.path.read_bytes(), saved)

    def test_wrong_class_level_and_worn_or_missing_book_are_refused(self):
        f = self.fixture()
        for class_id, level in ((1, 15), (2, 14)):
            f.pc.profile = replace(f.pc.profile, character_class=class_id, level=level)
            with self.assertRaisesRegex(ValueError, '^QUEST_INELIGIBLE$'):
                f.call('oth1', 'queststart', npc=70826)
        f.pc.profile = replace(f.pc.profile, character_class=2, level=15)
        # Only one owned copy of each book, with the Duda-Mara copy worn.
        f.change_inventory([_item_fields(100, 7, 20),
                            *(_item_fields(200 + t, t) for t in range(640, 644))])
        f.host._item_equipment_effect = NS(store=NS(restore=lambda uid, frame:
            NS(weapon_uid=0, slots=((0, 840),))))
        f.call('oth1', 'queststart', npc=70826)
        before = f.adapter.inventory_frame
        self.assertEqual(f.store.get(1, OTH).counts, (0, 1, 1, 1))
        with self.assertRaisesRegex(ValueError, '^QUEST_REQUIREMENTS_MISSING$'):
            f.call('oth3', 'questcomplete', npc=70826, cookie=b'\x00')
        self.assertFalse(f.sent or f.ctx.commit_attempted)
        self.assertEqual(f.adapter.inventory_frame, before)
        f.host._item_equipment_effect = None
        f.change_inventory([r for r in f.rows().values() if r[2] != 640])
        before = f.adapter.inventory_frame
        with self.assertRaisesRegex(ValueError, '^QUEST_REQUIREMENTS_MISSING$'):
            f.call('oth3', 'questcomplete', npc=70826, cookie=b'\x01')
        self.assertEqual(f.adapter.inventory_frame, before)

    def test_choice_turnin_save_failure_recovers_forward_without_second_reward(self):
        f = self.fixture()
        f.call('oth1', 'queststart', npc=70826)
        with patch.object(f.store, '_write_rows', side_effect=OSError('TEST_OTH_QUEST_SAVE')):
            with self.assertRaisesRegex(OSError, 'TEST_OTH_QUEST_SAVE'):
                f.call('oth3', 'questcomplete', npc=70826, cookie=b'\x01')
        self.assertFalse(f.sent)
        self.assertTrue(f.ctx.commit_attempted and f.store.intent_path.exists())
        self.assertFalse(f.store.get(1, OTH).completed)
        # Inventory already saved; startup must finish the same chosen reward.
        f.reopen()
        self.assertTrue(f.store.get(1, OTH).completed)
        self.assertFalse(f.store.intent_path.exists())
        self.assertEqual((self.counts(f)[631], self.counts(f)[632]), (0, 1))
        recovered = f.adapter.inventory_frame
        with self.assertRaisesRegex(ValueError, '^QUEST_ALREADY_COMPLETED$'):
            f.call('oth3', 'questcomplete', npc=70826, cookie=b'\x00')
        self.assertEqual(f.adapter.inventory_frame, recovered)

    def test_pure_completion_requires_explicit_numeric_choice(self):
        definition = next(q for q in world_quest.load_quests() if q.quest_id == OTH)
        state = world_quest.accept_quest(definition, world_quest.QuestState(OTH),
            class_key='elf', level=15, reference_steps={'Level15': 0}).state
        for choice in (None, True, '0', 2, 255):
            result = world_quest.complete_quest(definition, state, dict.fromkeys(range(640, 644), 1),
                npc_key='l1j:70826', action='questcomplete', policy='l1j_local',
                reference_steps={'Level15': 0}, completion_choice=choice)
            self.assertEqual(result.reason, 'reward_choice_required')
            self.assertFalse(result.consumed or result.rewards or result.state.completed)
        for choice, reward in ((0, 631), (1, 632)):
            with self.subTest(choice=choice):
                result = world_quest.complete_quest(definition, state, dict.fromkeys(range(640, 644), 1),
                    npc_key='l1j:70826', action='questcomplete', policy='l1j_local',
                    reference_steps={'Level15': 0}, completion_choice=choice)
                self.assertEqual(result.reason, 'completion_proposed')
                self.assertEqual(result.consumed, tuple(world_quest.ItemAmount(t, 1) for t in range(640, 644)))
                self.assertEqual(result.rewards, (world_quest.ItemAmount(reward, 1),))
                self.assertTrue(result.state.completed)
                self.assertEqual(result.state.cycles, 1)
                for again in (choice, 1 - choice):
                    repeated = world_quest.complete_quest(definition, result.state, {},
                        npc_key='l1j:70826', action='questcomplete', policy='l1j_local',
                        reference_steps={'Level15': 255}, completion_choice=again)
                    self.assertEqual(repeated.reason, 'already_completed')
                    self.assertFalse(repeated.consumed or repeated.rewards)


class OthRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_binary_zero_survives_real_haction_decoder_and_current_menu_router(self):
        import asyncio
        from tools.local_original_session import world_feature_town, world_handlers as h
        from tools.local_original_session.world_town import TownSetup
        from tools.local_original_session.world_terrain import WorldTerrain
        f = _QuestFixture(self)
        f.pc.profile = replace(f.pc.profile, character_class=2, level=15)
        f.change_inventory([_item_fields(100, 7, 20),
                            *(_item_fields(200 + t, t) for t in range(640, 644))])
        f.host._world_map_exp = 2
        terrain = WorldTerrain.load(map_ids=(4,))
        town = f.host._world.town
        town.passable = lambda map_id, x, y: terrain.can_stand(map_id, x, y) if map_id == 4 else True
        setup = f.feature._world_quest_town_setup(f.adapter, TownSetup(town, None, f.sources, None))
        npc = next(e for e in town.present(4, 32745, 32452, 1) if town.npc_for(e.uid).npc_id == 70826)
        self.assertEqual((npc.map_id, npc.x, npc.y), (4, 32745, 32452))
        f.host._world.entities.move(1, npc.map_id, npc.x, npc.y)
        f.host._world_handler_bindings = h.prepare_host_bindings(town, sources=setup.sources)
        f.host._world_registry = h.build_registry((world_feature_town, f.feature))
        for name, function in f.host._world_registry.methods.items():
            setattr(f.host, name, MethodType(function, f.adapter))
        writer, lock = object(), asyncio.Lock()
        await lock.acquire()
        try:
            row = dict(writer=writer, operation_lock=lock)
            f.host._world_pcs = {id(writer): (writer, 1)}
            wire = f.host._world_handler_bindings.wire
            def context():
                return h.HostContext(f.host, writer, row, object(), lock)
            ctx = context()
            await h.dispatch(ctx, h.CLICK, wire.click.encode_request(npc.uid))
            self.assertEqual(ctx.state.menu.fields[2], b'oth1')
            ctx.mark_delivered()
            ctx = context()
            await h.dispatch(ctx, h.HACTION, wire.dialogue.encode_haction_normal(npc.uid, b'queststart', None, (0, 0)))
            self.assertEqual(ctx.state.menu.fields[2], b'oth3')
            ctx.mark_delivered()
            for cookie in (None, b'0', b'1', b'\x02'):
                with self.assertRaisesRegex(ValueError, '^QUEST_REWARD_CHOICE_REQUIRED$'):
                    await h.dispatch(context(), h.HACTION,
                        wire.dialogue.encode_haction_normal(npc.uid, b'questcomplete', cookie, (0, 0)))
                self.assertFalse(f.store.get(1, OTH).completed)
            request = wire.dialogue.encode_haction_normal(npc.uid, b'questcomplete', b'\x00', (0, 0))
            self.assertEqual(wire.dialogue.decode_haction_normal(request)[3], b'\x00')
            ctx = context()
            await h.dispatch(ctx, h.HACTION, request)
            self.assertTrue(f.store.get(1, OTH).completed)
            self.assertEqual(ctx.state.menu.fields[2], b'oth6')
            self.assertEqual(OthChoiceTests.counts(f), Counter({7: 20, 631: 1}))
            self.assertEqual(f.inv.restore(1), f.adapter.inventory_frame)
        finally:
            lock.release()


if __name__ == '__main__':
    unittest.main()
