"""Accessory save/consumer development checks; no listener, game or live profile."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock

from tools.local_original_session import (
    equipment_change, equipment_store, inventory, inventory_store,
    item_equipment_effect as gear, world_core_stats, world_stats,
)
from tools.local_original_session.game_data import load_m1


def item(uid, template):
    return {1: uid, 2: template, 3: 0, 4: 1, 5: 0, 7: 71, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0, 24: False, 25: 0, 26: False}


class AccessoryConsumerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'characters.json'
        self.characters = inventory_store.realm.CharacterStore(self.path)
        self.characters.create(inventory_store.realm.Creation(
            'AccessoryKnight', 1, 0, (18, 13, 16, 10, 10, 10)))
        self.profile_bytes = self.path.read_bytes()
        self.data = load_m1()
        # Three separate instances of the same ring: duplicate-template wearing
        # is an explicit LOCAL policy, not a proven Classic duplicate rule.
        templates = ((1, 7), (101, 15384), (102, 15384), (103, 15384),
                     (201, 306), (202, 744), (301, 102), (401, 11), (402, 113),
                     (403, 230), (404, 3018))
        self.frame = inventory.build_kit_frame([item(uid, template) for uid, template in templates])
        self.inventory = inventory_store.InventoryStore(self.path, policy=inventory_store.POLICY,
                                                        kit_policy=inventory.KIT_POLICY)
        self.inventory.grant(1, self.frame)
        self.store = equipment_store.EquipmentStore(self.inventory, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=self.data.items)
        state = self.store.initialize_kit(1, self.frame,
            initialization=equipment_store.FIRST_ENABLE_EMPTY, weapon_uid=0, slots=())
        self.writer = object()
        self.sent = []
        self.row = dict(operation_lock=object(), policy_row=NS(
            sent=0, drain_started_ns=None, pending_opcode=None))
        members = inventory.validate_kit_frame(self.frame)
        self.context = dict(writer=self.writer, row=self.row, character_uid=1,
            selected_class=1, frame=self.frame, items=members, item=members[0],
            generation=object(), identity=(object(),), service=NS(_current=object()))
        self.effect = effect = object.__new__(gear.ItemEquipmentEffect)
        effect._kit_policy = inventory.KIT_POLICY
        effect._collection_policy = effect._collection_batch = effect._operation = None
        effect._defs = self.data.items
        effect.store = self.store
        effect.first_enable = False
        effect._selection = dict(state=state, identity=self.context['identity'], synced=True,
                                 sync_receipt=None, barrier_active=False)
        effect._context = lambda *args, **kwargs: self.context
        effect._same = lambda *args: None
        effect._kit_params_raw0 = lambda intent: True
        effect._refresh_stance = AsyncMock()
        effect.broker = NS(_world=object(), _checkpoint=AsyncMock(),
                           _world_refresh_pc=AsyncMock(), _send=self.send)

    async def send(self, writer, row, frames, **kwargs):
        # Exercise the existing exact reply/state verification and 097A codec;
        # only the transport drain is a development stub.
        op = kwargs['equipment_operation']
        for frame in frames:
            op['phase'] = 'RESERVING'
            self.effect.attempt(writer, row, op)
            self.sent.append(equipment_change.validate_change(frame))
            row['policy_row'].sent += 1
            op['receipt']['drain_returned'] = True
            self.effect.drained(writer, row, op, 0)

    async def use(self, uid):
        self.context['item'] = next(i for i in self.context['items'] if i.identifier == uid)
        receipt = gear._receipt('ITEM_USE_EFFECT', 1)
        receipt.update(item_uid=uid)
        return await self.effect._consume_kit(self.writer, self.context, object(), receipt,
                                               self.effect._selection)

    def current(self):
        return self.store.restore(1, self.frame)

    async def test_two_rings_toggle_actual_side_then_replace_and_restore(self):
        await self.use(101)
        await self.use(102)
        self.assertEqual(self.current().slots, ((13, 101), (14, 102)))
        self.assertEqual([(x.uid, x.key, x.equipped) for x in self.sent],
                         [(101, 13, True), (102, 14, True)])
        self.sent.clear()
        await self.use(102)
        self.assertEqual(self.current().slots, ((13, 101),))
        self.assertEqual([(x.uid, x.key, x.equipped) for x in self.sent], [(102, 14, False)])
        await self.use(102)
        self.sent.clear()
        await self.use(103)
        self.assertEqual(self.current().slots, ((13, 103), (14, 102)))
        self.assertEqual([(x.uid, x.key, x.equipped) for x in self.sent],
                         [(101, 13, False), (103, 13, True)])
        await self.use(201)
        await self.use(202)
        saved = self.current()
        self.assertEqual(saved.slots, ((11, 201), (12, 202), (13, 103), (14, 102)))
        restored = equipment_store.EquipmentStore(self.inventory, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=self.data.items)
        self.assertEqual(restored.restore(1, self.frame), saved)
        self.assertEqual(self.path.read_bytes(), self.profile_bytes)
        self.sent.clear()
        self.effect._selection = None
        receipt = await self.effect.prepare_locked(self.writer)
        self.assertEqual(receipt['status'], 'SYNCHRONIZED')
        self.assertEqual([(x.uid, x.key, x.equipped) for x in self.sent],
                         [(uid, key, True) for key, uid in saved.slots])
        self.assertEqual(self.current().revision, saved.revision)

    async def test_core_consumes_saved_accessories_and_unequip_rebuilds_base(self):
        for uid in (101, 102, 201, 202):
            await self.use(uid)
        ctx = NS(realm=NS(store=self.characters), _world_progress_for=lambda uid: None,
                 _item_equipment_effect=self.effect, _world=NS(data=self.data),
                 world=NS(data=self.data), item_policies={},
                 fold_sync_hooks=lambda name, value, *args, **kwargs: value)
        position = NS(uid=1, name='AccessoryKnight')
        result, worn, _ = world_core_stats._world_stats_for(ctx, position)
        self.assertEqual(result.attributes.strength, 22)  # two rings + amulet + belt
        self.assertEqual(result.ac, world_stats.base_ac(1, 13) - 2)
        fields = world_stats.self_info_fields({10: 50, 11: 200, 12: 10, 13: 30}, result)
        self.assertEqual((fields[4], fields[14], fields[11], fields[13]), (22, -8, 200, 30))
        self.assertEqual(len(worn), 4)
        for uid in (101, 102, 201, 202):
            await self.use(uid)
        base, worn, _ = world_core_stats._world_stats_for(ctx, position)
        self.assertEqual((base.attributes.strength, base.ac, worn), (18, 10, ()))

    def test_legacy_rows_read_unchanged_and_new_slots_keep_v1_schema(self):
        legacy = dict(character_uid=1, item_uid=1, template=7, weapon_uid=0, revision=1)
        for slots in (None, {'2': 301}):
            row = dict(legacy)
            if slots is not None:
                row['slots'] = slots
            raw = (json.dumps(dict(version=1, policy=equipment_store.POLICY,
                                   equipment=[row]), separators=(',', ':')) + '\n').encode()
            self.store.path.write_bytes(raw)
            state = self.store.restore(1, self.frame)
            self.assertEqual(self.store.path.read_bytes(), raw)
            self.assertEqual(state.slots, () if slots is None else ((2, 301),))
            new = self.store.compare_and_swap_kit(1, self.frame, state, weapon_uid=0,
                                                   slots=state.slots + ((14, 101),))
            self.assertEqual(self.store.restore(1, self.frame), new)
            self.assertEqual(json.loads(self.store.path.read_bytes())['version'], 1)

    def test_same_uid_cannot_fill_both_ring_slots_or_an_unrelated_slot(self):
        for slots in (((13, 101), (14, 101)), ((12, 101),)):
            with self.subTest(slots=slots), self.assertRaisesRegex(
                    ValueError, 'EQUIPMENT_SUPPORTED_ARMOR_REQUIRED'):
                self.store.compare_and_swap_kit(1, self.frame, self.current(),
                                                weapon_uid=0, slots=slots)

    async def test_twohand_shield_refuses_both_orders_and_keeps_save_and_notifications(self):
        for first, second in ((401, 402), (402, 401)):
            with self.subTest(first=first):
                self.assertEqual((await self.use(first))['status'], 'COMMITTED')
                before, saved, sent = self.current(), self.store.path.read_bytes(), list(self.sent)
                result = await self.use(second)
                self.assertEqual((result['status'], result['reason']),
                    ('BLOCKED', 'EQUIPMENT_TWO_HANDED_SHIELD_CONFLICT'))
                self.assertFalse(result['persist_attempted'])
                self.assertEqual((self.current(), self.store.path.read_bytes(), self.sent), (before, saved, sent))
                self.assertEqual((await self.use(first))['status'], 'COMMITTED')

    async def test_onehand_staff_shield_allowed_both_orders_and_restores(self):
        # 10-29 staff decision includes Angel's Staff 3018 (formerly UNKNOWN).
        for first, second in ((403, 402), (402, 403), (404, 402), (402, 404)):
            with self.subTest(first=first):
                self.context['selected_class'] = 3 if 404 in (first, second) else 1
                await self.use(first)
                self.assertEqual((await self.use(second))['status'], 'COMMITTED')
                state = self.current()
                weapon = second if first == 402 else first
                self.assertEqual((state.weapon_uid, state.slots), (weapon, ((8, 402),)))
                self.assertEqual(self.store.restore(1, self.frame), state)
                await self.use(first)
                await self.use(second)

    async def test_unknown_handedness_is_not_onehand_and_legacy_invalid_pair_can_unequip(self):
        # Keep UNKNOWN admission coverage independent of catalog corrections.
        definition = self.data.items[3018]
        sources = dict(definition.sources)
        metadata = json.loads(sources['weapon'].note)
        metadata['two_handed'] = None
        sources['weapon'] = replace(sources['weapon'], note=json.dumps(metadata))
        self.effect._defs = dict(self.data.items)
        self.effect._defs[3018] = replace(definition, sources=sources)
        self.assertIsNone(equipment_store.two_handed(self.effect._defs[3018]))
        self.context['selected_class'] = 3
        await self.use(404)  # unknown is allowed without a shield
        result = await self.use(402)
        self.assertEqual(result['reason'], 'EQUIPMENT_HANDEDNESS_UNKNOWN')
        await self.use(404)
        legacy = self.store.compare_and_swap_kit(1, self.frame, self.current(),
                                                 weapon_uid=401, slots=((8, 402),))
        self.effect._selection['state'] = legacy
        self.assertEqual(self.current(), legacy)  # no rewrite on load
        self.assertEqual((await self.use(402))['status'], 'COMMITTED')
        self.assertEqual((self.current().weapon_uid, self.current().slots), (401, ()))

    async def test_player_conflict_uses_existing_world_notice_queue(self):
        from tools.local_original_session.world_core_inventory import RealmInventoryCore
        from tools.local_entry_server import protobuf as pb
        await self.use(401)
        self.context['item'] = next(i for i in self.context['items'] if i.identifier == 402)
        service = NS(accepted_count=0, _current=object())
        async def accept(*args):
            service.accepted_count += 1
            return ()
        service.handle = accept
        effect = self.effect
        effect.prepare_locked = AsyncMock(return_value={'status': 'SYNCHRONIZED'})
        async def consume(*args, **kwargs):
            return await self.use(402)
        effect.consume_locked = consume
        broker = effect.broker
        broker._item_equipment_effect = effect
        broker._item_use_session = service
        broker._world_bound = lambda writer: writer is self.writer
        broker._world_pcs = {id(self.writer): (self.writer, 1)}
        queued = []
        broker._world = NS(_queue=lambda uid, frame: queued.append((uid, frame)))
        service.broker = broker
        realm = NS(registry=NS(resolve=Mock()), _item_use_session=service)
        broker.realm = realm
        self.assertEqual(await RealmInventoryCore._inventory_use_intent(realm, self.writer, b'fixture'), ())
        uid, frame = queued[0]
        self.assertEqual((uid, int.from_bytes(frame[2:4], 'little')), (1, 0x4EEA))
        with pb.parse_message(frame[4:-2]) as message:
            self.assertEqual(message.occurrences(1)[0].value, 12066)
            self.assertIn('양손 무기와 방패', bytes(message.occurrences(2)[0].value).decode('utf-8'))

    def test_handedness_uses_source_metadata_and_raw_l1j_types(self):
        for template, expected in ((6, True), (11, True), (54, False), (230, False),
                                   (342, False), (3018, False)):
            with self.subTest(template=template):
                self.assertIs(equipment_store.two_handed(self.data.items[template]), expected)


class AccessoryStatsTests(unittest.TestCase):
    def setUp(self):
        self.items = load_m1().items
        self.base = world_stats.CharacterStats(20, 1, world_stats.Attributes(18, 12, 16, 10, 12, 8))

    def test_six_official_attributes_include_penalties_and_repeat_without_accumulation(self):
        names = ('strength', 'dexterity', 'con', 'intelligence', 'wis', 'charisma')
        baseline = world_stats.calculate_stats(self.base)
        for template, name in zip(range(306, 312), names):
            worn = (world_stats.EquippedItem(self.items[template]),)
            result = world_stats.calculate_stats(self.base, worn)
            with self.subTest(template=template):
                self.assertEqual(getattr(result.attributes, name), getattr(baseline.attributes, name) + 1)
                self.assertEqual(world_stats.calculate_stats(self.base, worn), result)
                # magic's registered stats hook recalculates with the same worn
                # entries, so catalog modifiers survive that calculation too.
                magic = world_stats.calculate_stats(self.base, worn,
                    buffs=(world_stats.StatModifiers(dexterity=6),))
                self.assertEqual(magic.attributes.dexterity, result.attributes.dexterity + 6)
        old = world_stats.calculate_stats(self.base, (world_stats.EquippedItem(self.items[508]),))
        self.assertEqual((old.attributes.strength, old.attributes.dexterity), (19, 10))

    def test_accessory_enchant_does_not_improve_ac_and_maxima_are_not_regen(self):
        belt = world_stats.EquippedItem(self.items[744], enchant=9)
        plain = world_stats.calculate_stats(self.base, (replace(belt, enchant=0),))
        self.assertEqual(world_stats.calculate_stats(self.base, (belt,)), plain)
        ring = world_stats.calculate_stats(self.base, (world_stats.EquippedItem(self.items[496]),))
        baseline = world_stats.calculate_stats(self.base)
        self.assertEqual(ring.mr, baseline.mr + 5)
        for template, hp_bonus, mp_bonus in ((502, 30, 0), (503, 0, 30), (504, 15, 15)):
            calculated = world_stats.calculate_stats(self.base,
                (world_stats.EquippedItem(self.items[template]),))
            self.assertEqual((calculated.max_hp_bonus, calculated.max_mp_bonus),
                             (hp_bonus, mp_bonus))
            self.assertEqual(replace(calculated, max_hp_bonus=0, max_mp_bonus=0), baseline)
        hp = world_stats.calculate_stats(self.base, (world_stats.EquippedItem(self.items[936]),))
        mp = world_stats.calculate_stats(self.base, (world_stats.EquippedItem(self.items[937]),))
        self.assertEqual(hp.hp_regen_min, baseline.hp_regen_min + 1)
        self.assertEqual(mp.mp_regen, baseline.mp_regen + 1)


if __name__ == '__main__':
    unittest.main()
