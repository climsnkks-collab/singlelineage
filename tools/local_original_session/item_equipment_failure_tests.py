"""Development fault injection: current-save resync, no socket/game/profile IO."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock

from tools.local_original_session import inventory, item_equipment_effect as gear


class FailureTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self, stage, *, target=65538):
        writer = object()
        effect = object.__new__(gear.ItemEquipmentEffect)
        self.saved = NS(weapon_uid=65537, slots=((2, 65540),), revision=1, item_uid=65537)
        self.client = {65537: True, 65538: False, 65540: True}
        self.notifications = []
        error = RuntimeError('DEVELOPMENT_' + stage)
        once = {stage: True}

        def fault(at):
            if once.pop(at, False):
                raise error

        broker = NS(_world=object(), _fail=Mock())
        async def checkpoint(*args):
            fault('before_save')
        async def refresh(*args):
            fault('after_notify')
        broker._checkpoint, broker._world_refresh_pc = checkpoint, refresh
        effect.broker = broker
        effect._defs = {3: NS(kind='weapon', slot='weapon', equippable=True, slot_key=9, classes={1}),
                        90: NS(kind='armor', slot='helmet', equippable=True, slot_key=2, classes={1})}
        effect._collection_policy = effect._collection_batch = effect._operation = None
        effect._kit_policy = inventory.KIT_POLICY
        effect._key = lambda: 9
        effect._refresh_stance = AsyncMock()
        item = NS(identifier=target, template_bits=3, raw_fields=((4, 1),))
        context = dict(writer=writer, row={}, character_uid=1, frame=b'fixture', item=item,
                       items=(item, NS(identifier=65537, template_bits=3, raw_fields=((4, 1),)),
                              NS(identifier=65540, template_bits=90, raw_fields=((4, 1),))),
                       selected_class=1, generation=object(), identity=(object(),))
        effect._context = lambda *args, **kwargs: context
        effect._same = lambda *args: None
        effect._kit_params_raw0 = lambda intent: True
        effect.store = NS(restore=lambda *args: self.saved)

        def cas(*args, weapon_uid, slots):
            self.saved = NS(weapon_uid=weapon_uid, slots=slots,
                            revision=self.saved.revision + 1, item_uid=65537)
            return self.saved
        effect.store.compare_and_swap_kit = cas

        async def notify(context, state, receipt, changes):
            fault('before_notify')
            self.notifications.append(changes)
            for uid, key, equipped in changes:
                self.client[uid] = equipped
            receipt.update(write_attempted=True, drain_returned=True, phase='DRAINED')
        effect._notify_kit = notify
        effect._selection = dict(identity=context['identity'], state=self.saved,
                                 synced=True, sync_receipt=None, barrier_active=False)
        effect.first_enable = False
        return effect, writer, context, error

    async def test_original_failure_resyncs_save_then_next_toggle_remains_usable(self):
        for stage in ('before_save', 'before_notify', 'after_notify'):
            with self.subTest(stage=stage):
                effect, writer, context, error = self.fixture(stage)
                receipt = gear._receipt('ITEM_USE_EFFECT', 1)
                receipt.update(item_uid=65538)
                with self.assertRaisesRegex(ValueError, 'EQUIPMENT_WORLD_REQUEST_FAILED') as caught:
                    await effect._consume_kit(writer, context, object(), receipt, effect._selection)
                self.assertIs(caught.exception.__cause__, error)
                self.assertEqual(receipt['status'], 'UNKNOWN')
                self.assertEqual(receipt['resync_status'], 'SYNCHRONIZED')
                self.assertIs(effect._last, receipt)
                effect.broker._fail.assert_not_called()
                worn = {self.saved.weapon_uid, *(uid for _, uid in self.saved.slots)} - {0}
                self.assertEqual({uid for uid, on in self.client.items() if on}, worn)
                self.assertEqual(self.saved.revision, 1 if stage == 'before_save' else 2)
                if stage != 'before_save':
                    self.assertEqual(self.notifications[-1][0], (65537, 9, False))
                # Recovery does not consume another use or write another CAS.
                for ordinal in (2, 3):
                    next_receipt = gear._receipt('ITEM_USE_EFFECT', ordinal)
                    next_receipt.update(item_uid=65538)
                    result = await effect._consume_kit(writer, context, object(), next_receipt,
                                                       effect._selection)
                    self.assertEqual(result['status'], 'COMMITTED')
                    self.assertEqual({uid for uid, on in self.client.items() if on},
                        {self.saved.weapon_uid, *(uid for _, uid in self.saved.slots)} - {0})

    async def test_failed_unequip_publishes_false_for_now_empty_slot(self):
        effect, writer, context, error = self.fixture('before_notify', target=65537)
        receipt = gear._receipt('ITEM_USE_EFFECT', 1)
        receipt.update(item_uid=65537)
        with self.assertRaisesRegex(ValueError, 'EQUIPMENT_WORLD_REQUEST_FAILED') as caught:
            await effect._consume_kit(writer, context, object(), receipt, effect._selection)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(self.saved.weapon_uid, 0)
        self.assertFalse(self.client[65537])
        self.assertEqual(self.notifications[-1][0], (65537, 9, False))

    async def test_legacy_failure_still_stops_broker(self):
        effect, writer, context, error = self.fixture('unused')
        effect.broker._world = None
        receipt = gear._receipt('ITEM_USE_EFFECT', 1)
        receipt['persist_attempted'] = True
        effect._failed(receipt, error)
        effect.broker._fail.assert_called_once_with('EQUIPMENT_EFFECT_OUTCOME_UNKNOWN')
        with self.assertRaises(RuntimeError) as caught:
            effect._raise_request_failure(error)
        self.assertIs(caught.exception, error)

    async def test_initial_sync_failure_restores_once_without_another_save(self):
        for stage in ('before_save', 'after_notify'):
            with self.subTest(stage=stage):
                effect, writer, context, error = self.fixture(stage)
                effect._selection = None
                effect.store.initialize_kit = Mock(side_effect=AssertionError('must restore'))
                with self.assertRaisesRegex(ValueError, 'EQUIPMENT_WORLD_REQUEST_FAILED') as caught:
                    await effect.prepare_locked(writer)
                self.assertIs(caught.exception.__cause__, error)
                self.assertEqual(effect._last['status'], 'UNKNOWN')
                self.assertEqual(effect._last['resync_status'], 'SYNCHRONIZED')
                self.assertTrue(effect._selection['synced'])
                self.assertEqual(self.saved.revision, 1)
                effect.store.initialize_kit.assert_not_called()
                effect.broker._fail.assert_not_called()

    async def test_initial_sync_recovery_failure_does_not_recurse(self):
        effect, writer, context, error = self.fixture('unused')
        effect._selection = None
        effect.broker._checkpoint = AsyncMock(side_effect=error)
        with self.assertRaisesRegex(ValueError, 'EQUIPMENT_WORLD_REQUEST_FAILED') as caught:
            await effect.prepare_locked(writer)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(effect.broker._checkpoint.await_count, 2)
        self.assertEqual(effect._last['resync_status'], 'UNKNOWN')
        self.assertEqual(self.saved.revision, 1)

    async def test_potion_failures_resend_saved_quantity_without_consuming_or_healing_again(self):
        from tools.local_original_session.world_companion_integration_tests import CompanionWorldViewTests
        from tools.local_original_session.world_core_inventory import INVENTORY_STARTER_FIELDS
        from tools.local_original_session import inventory_update, world_status_frames, world_combat
        for stage, quantity, buffed in (('before_save', 2, False), ('after_save', 2, False),
                ('after_effect', 2, False), ('after_effect', 1, False), ('after_effect', 2, True)):
            with self.subTest(stage=stage, quantity=quantity, buffed=buffed):
                effect, writer, context, error = self.fixture('unused')
                fixture = CompanionWorldViewTests();fixture.setUp()
                try:
                    view = fixture.view
                    state = view.combat.pcs[1];state.hp = 50
                    rows = []
                    for uid, template, count in ((65537, 3, 1), (65538, 14, quantity)):
                        row = dict(INVENTORY_STARTER_FIELDS)
                        row.update({1: uid, 2: template, 4: count})
                        rows.append(row)
                    frame = inventory.build_kit_frame(rows)
                    saved = [frame];commits = [];effects = [];sent = []
                    context.update(frame=frame, row={'operation_lock': object()},
                        item=next(item for item in inventory.validate_kit_frame(frame)
                                  if item.identifier == 65538))
                    broker = effect.broker
                    broker._world = view
                    broker._world_bound = lambda writer: True
                    broker._world_pcs = {id(writer): (writer, 1)}
                    broker._inventory_store = NS(restore=lambda uid: saved[0])
                    broker._inventory_current_frame = frame
                    async def checkpoint(*args):
                        if stage == 'before_save':raise error
                    def replace(uid, before, after):
                        self.assertEqual(before, saved[0])
                        commits.append((before, after));saved[0] = after
                        if stage == 'after_save':raise error
                        return True
                    async def use(*args, **kwargs):
                        effects.append('buff' if buffed else 'heal')
                        if buffed:
                            view.combat.apply_buff(1, NS(kind='fixture', classes={1},
                                rate=.75, add_s=30, cap_s=300), fixture.now)
                        else:state.hp += 5
                        raise error
                    async def send(writer, row, frames, lock):
                        sent.extend(frames)
                    broker._checkpoint = checkpoint
                    broker._world_replace_kit = replace
                    broker._world_potion_locked = use
                    broker._world_buff_locked = use
                    broker._world_send = send
                    receipt = gear._receipt('ITEM_USE_EFFECT', 1)
                    receipt.update(item_uid=65538)
                    with self.assertRaisesRegex(ValueError, 'EQUIPMENT_WORLD_REQUEST_FAILED') as caught:
                        await effect._consume_potion(writer, context, receipt,
                            NS(heal_hp=5, buff=object() if buffed else None))
                    self.assertIs(caught.exception.__cause__, error)
                    self.assertEqual(receipt['resync_status'], 'SYNCHRONIZED')
                    expected_quantity = quantity if stage == 'before_save' else quantity - 1
                    self.assertEqual(receipt['resync_quantity'], expected_quantity)
                    self.assertEqual(len(commits), int(stage != 'before_save'))
                    self.assertEqual(len(effects), int(stage == 'after_effect'))
                    self.assertEqual(state.hp, 55 if effects and not buffed else 50)
                    self.assertEqual(state.mp, 20)
                    if buffed:
                        self.assertEqual(state.buffs, {'fixture': (fixture.now + 30, .75)})
                        self.assertIn(world_combat.speed_frame(1, .75), sent)
                    self.assertEqual(broker._inventory_current_frame, saved[0])
                    quantity_wire = next(wire for wire in sent
                        if int.from_bytes(wire[2:4], 'little') in (0x0965, 0x0978))
                    opcode = int.from_bytes(quantity_wire[2:4], 'little')
                    self.assertEqual(opcode, 0x0965 if expected_quantity else 0x0978)
                    if expected_quantity:
                        update = inventory_update.validate_frame(quantity_wire)
                        self.assertEqual(dict(update.raw_fields)[4], expected_quantity)
                    fields = dict(state.status_fields);fields[10], fields[12] = state.hp, state.mp
                    self.assertIn(world_status_frames.full_status_frame(fields), sent)
                    broker._fail.assert_not_called()
                finally:
                    fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
