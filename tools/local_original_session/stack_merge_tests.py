"""Stack regressions using existing save/dispatch fixtures; no native client."""
import hashlib
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_store as store
from tools.local_original_session import equipment_store, world_core_kit
from tools.local_original_session import world_handlers as handlers
from tools.local_original_session import world_shop_warehouse_tests as town_tests
from tools.local_original_session import world_companion_equipment_tests as companion_tests
from tools.local_original_session.world_visibility import item_names


def rows(frame):
    return [dict(row.raw_fields) for row in inventory.validate_kit_frame(frame)]


class StackPropertiesTests(unittest.TestCase):
    def test_currency_label_alias_only_compares_and_preserves_opaque_properties(self):
        plain = {**handlers._starter_fields(), 1: 11, 2: 7, 4: 0}
        named = {**plain, 1: 22, 4: 3, 18: item_names()[7]}
        original_plain, original_named = dict(plain), dict(named)
        self.assertTrue(store.compatible_stack(plain, named))
        for key in plain.keys() - {1, 4, 18}:
            changed = {**named, key: not named[key] if type(named[key]) is bool else named[key] + 1}
            self.assertFalse(store.compatible_stack(plain, changed), key)
        self.assertFalse(store.compatible_stack(plain, {**named, 18: b'+7 original opaque instance'}))
        self.assertEqual((plain, named), (original_plain, original_named))

    def test_plain_label_alias_preserves_real_properties_and_grade_names(self):
        plain = {**handlers._starter_fields(), 1: 11, 2: 14, 4: 2}
        named = {**plain, 1: 22, 4: 9, 18: item_names()[14]}
        self.assertTrue(store.compatible_stack(plain, named))
        for key in plain.keys() - {1, 4, 18}:
            changed = {**named, key: not named[key] if type(named[key]) is bool else named[key] + 1}
            self.assertFalse(store.compatible_stack(plain, changed), key)
        for name in (b'blessed scroll', b'cursed scroll', b'custom potion'):
            self.assertFalse(store.compatible_stack(plain, {**named, 18: name}))
        from tools.local_original_session.world_enchant_inventory import scroll_name
        for template in (25, 26):
            variants = [{**plain, 2: template, 18: scroll_name(template, grade)} for grade in (0, 1, 2)]
            for left in range(3):
                for right in range(3):
                    self.assertEqual(store.compatible_stack(variants[left], variants[right]), left == right)

    def test_currency_repair_is_lowest_uid_stable_and_preserves_other_rows(self):
        base = handlers._starter_fields()
        original = inventory.build_kit_frame([
            {**base, 1: 90, 2: 7, 4: 1000, 18: item_names()[7]},
            {**base, 1: 91, 2: 14, 4: 8, 18: b'variant'},
            {**base, 1: 12, 2: 7, 4: 895, 18: b'', 5: 6}])
        repaired = store.repaired_adena_frame(original)
        actual = rows(repaired)
        self.assertEqual([r[1] for r in actual], [91, 12])
        self.assertEqual(actual[0], rows(original)[1])
        self.assertEqual(actual[1], {**rows(original)[2], 4: 1895})
        self.assertIs(store.repaired_adena_frame(repaired), repaired)

    def test_currency_overflow_refuses_without_splitting_or_clamping(self):
        base = handlers._starter_fields()
        original = inventory.build_kit_frame([
            {**base, 1: 3, 2: 7, 4: 2_000_000_000}, {**base, 1: 2, 2: 7, 4: 1}])
        with self.assertRaisesRegex(ValueError, '^INVENTORY_ADENA_STACK_LIMIT$'):
            store.repaired_adena_frame(original)
        self.assertEqual([r[4] for r in rows(original)], [2_000_000_000, 1])


class TownStackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = town_tests.DefaultTownAssetTests()
        self.addCleanup(self.case.doCleanups)
        await self.case.asyncSetUp()

    def save(self, values):
        case = self.case
        before = case.broker._inventory_current_frame
        after = inventory.build_kit_frame(values)
        case.store.replace_kit(1, before, after, append=True)
        case.broker._inventory_current_frame = after
        return after

    async def test_actual_profile_copy_repair_and_buy_list(self):
        from tools.local_original_session.world_state_services import InventoryTransactions
        from tools.local_original_session.world_persist import WorldPersist
        from tools.local_original_session.world_scheduler import Scheduler
        case = self.case
        source = Path(__file__).resolve().parents[2] / 'work/local_original_session/validation-profiles/manual-test-knight'
        files = ('characters.json', 'inventory.json', 'equipment.json', 'companion.json')
        before_hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files}
        for name in files:
            shutil.copy2(source / name, case.profile.parent / name)
        case.store = case.fresh_store()
        case.broker._inventory_store = case.store
        case.broker._world_inventory_transactions = InventoryTransactions(case.store)
        equipment = equipment_store.EquipmentStore(case.store, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=case.broker._world.data.items)
        case.broker._item_equipment_effect = SimpleNamespace(store=equipment, _selection=None)
        copied = case.store.restore(1)
        # The copied manual profile is mutable. Seed this regression's two
        # legacy currency rows only in its owned temporary save.
        other_rows = [r for r in rows(copied) if r[2] != 7]
        currency = next(r for r in rows(copied) if r[2] == 7)
        first_uid = max(r[1] for r in rows(copied)) + 1
        original = inventory.build_kit_frame(other_rows + [
            {**currency, 1: first_uid, 4: 1000, 18: item_names()[7]},
            {**currency, 1: first_uid + 1, 4: 895, 18: b''}])
        case.store.replace_kit(1, copied, original, append=True)
        self.assertEqual([(r[1], r[4]) for r in rows(original) if r[2] == 7],
                         [(first_uid, 1000), (first_uid + 1, 895)])
        persist = WorldPersist(Scheduler(clock=lambda: 1.0),
            lambda key, frame: case.store.flush_world_snapshot(key[1], frame))
        case.store.enable_world_persist(persist)
        repaired = case.store.repair_adena_kit(1, replace=case.broker._world_replace_kit)
        case.broker._inventory_current_frame = repaired
        self.assertEqual([(r[1], r[4]) for r in rows(repaired) if r[2] == 7], [(first_uid, 1895)])
        self.assertEqual([r for r in rows(original) if r[2] != 7], [r for r in rows(repaired) if r[2] != 7])
        self.assertEqual(case.store._world_rows[1], repaired)
        self.assertEqual(case.store._world_durable[1], repaired)
        self.assertEqual(case.fresh_store().restore(1), repaired)
        self.assertEqual(case.store.repair_adena_kit(1, replace=case.broker._world_replace_kit), repaired)
        equipment.restore(1, repaired)
        opened = await case.open(70014, 'buy')
        self.assertIsNotNone(opened.state.window)
        self.assertEqual(opened.store.snapshot(1, 0).inventory.adena, 1895)
        self.assertEqual(before_hashes, {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files})
        print('profile copy:', case.profile.parent, f'Adena UID{first_uid}=1895; Buy list open; source files unchanged')

    async def test_shop_buy_and_sell_merge_legacy_plain_labels(self):
        case = self.case
        values = rows(case.broker._inventory_current_frame)
        values[0][18] = item_names()[7]
        values[1][18] = item_names()[14]
        self.save(values)
        ctx = await case.open(70014, 'buy')
        window = ctx.state.window
        key = next(k for k, offer in window.rows.items()
            if case.broker._world.town.data.shops.offers[offer].classic_item_id == 14)
        codec = ctx.wire.trade
        await handlers.dispatch(case.context(), handlers.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 5, (codec.Item(key, 2),), 0, 0)))
        self.assertEqual([(r[1], r[4]) for r in rows(case.store.restore(1)) if r[2] == 14], [(102, 12)])
        await case.close()
        ctx = await case.open(70014, 'sell')
        window = ctx.state.window
        key = next(k for k, uid in window.rows.items() if uid == 102)
        await handlers.dispatch(case.context(), handlers.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 6, (codec.Item(key, 2),), 0, 0)))
        self.assertEqual([(r[1], r[4]) for r in rows(case.store.restore(1)) if r[2] == 7], [(101, 964)])

    async def test_warehouse_withdraw_currency_and_potion_plain_labels(self):
        case = self.case
        values = rows(case.broker._inventory_current_frame)
        values[0][18], values[1][18] = item_names()[7], item_names()[14]
        self.save(values)
        await case.open(60001, 'deposit')
        await case.bank_trade(((101, 200), (102, 4)))
        await case.close()
        values = rows(case.store.restore(1))
        values[0][18], values[1][18] = b'', b''
        self.save(values)
        await case.open(60001, 'retrieve')
        await case.bank_trade(((0, 200), (1, 4)))
        actual = rows(case.store.restore(1))
        self.assertEqual([(r[1], r[4]) for r in actual if r[2] == 7], [(101, 940)])
        self.assertEqual([(r[1], r[4]) for r in actual if r[2] == 14], [(102, 10)])

    async def test_warehouse_refuses_incompatible_currency_without_losing_opaque_fields(self):
        case = self.case
        await case.open(60001, 'deposit')
        await case.bank_trade(((101, 200),))
        await case.close()
        values = rows(case.store.restore(1))
        values[0].update({5: 7, 18: b'+7 original opaque instance'})
        before = self.save(values)
        warehouse_before = case.broker._world_inventory_transactions.restore_warehouse(1)
        await case.open(60001, 'deposit')
        with self.assertRaisesRegex(ValueError, '^INCOMPATIBLE_ADENA_STACK$'):
            await case.bank_trade(((101, 10),))
        self.assertEqual(case.store.restore(1), before)
        self.assertEqual(case.broker._world_inventory_transactions.restore_warehouse(1), warehouse_before)

    async def test_repair_moves_deleted_equipment_anchor_through_existing_journal(self):
        case = self.case
        values = rows(case.store.restore(1))
        values.append({**values[0], 1: 99, 4: 5})
        original = self.save(values)
        equipment = equipment_store.EquipmentStore(case.store, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=case.broker._world.data.items)
        equipment.initialize_kit(1, original, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=0, slots=())
        case.broker._item_equipment_effect = SimpleNamespace(store=equipment, _selection=None)
        repaired = case.store.repair_adena_kit(1, replace=case.broker._world_replace_kit)
        state = equipment.restore(1, repaired)
        self.assertNotEqual(state.item_uid, 101)
        self.assertEqual(state.revision, 2)
        self.assertFalse(case.profile.with_name('warehouse-transfer.json').exists())

    async def test_player_pickup_merges_plain_names_and_keeps_grade_variants(self):
        from tools.local_original_session.world_core_reward import _world_pickup_commit
        from tools.local_original_session.world_enchant_inventory import scroll_name
        case = self.case
        values = rows(case.store.restore(1))
        for row in values:
            row[18] = item_names()[row[2]]
        self.save(values)
        owner = SimpleNamespace(inventory_frame=case.store.restore(1), _inventory_store=case.store,
            _inventory_kit_policy=inventory.KIT_POLICY, _world_pcs={id(case.writer): (case.writer, 1)},
            starter_fields=handlers._starter_fields(), fold_sync_hooks=lambda _name, fields, _item: fields)
        for template, count in ((7, 5), (14, 2)):
            wire, = _world_pickup_commit(owner, case.writer, SimpleNamespace(item_id=template, stackable=True), count)
            self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x0965)
        actual = rows(case.store.restore(1))
        self.assertEqual(actual, [{**row, 4: row[4] + {7: 5, 14: 2}.get(row[2], 0)}
                                  for row in values])
        self.assertEqual([(r[1], r[4]) for r in actual if r[2] == 7], [(101, 1005)])
        self.assertEqual([(r[1], r[4]) for r in actual if r[2] == 14], [(102, 12)])
        prototype = {**handlers._starter_fields(), 2: 25, 7: 7}
        for grade in (0, 1, 2, 2):
            item = SimpleNamespace(item_id=25, stackable=True,
                inventory_fields=tuple({**prototype, 18: scroll_name(25, grade)}.items()))
            _world_pickup_commit(owner, case.writer, item, 1)
        scrolls = [r for r in rows(case.store.restore(1)) if r[2] == 25]
        self.assertEqual([(r[18], r[4]) for r in scrolls],
            [(scroll_name(25, grade), count) for grade, count in ((0, 1), (1, 1), (2, 2))])

    async def test_quest_currency_reward_reuses_named_wallet(self):
        from tools.local_original_session.world_feature_quest import _quest_inventory_change
        case = self.case
        values = rows(case.store.restore(1))
        values[0][18] = item_names()[7]
        before = self.save(values)
        prototype = {**handlers._starter_fields(), 2: 7, 7: 5}
        reward = SimpleNamespace(item_id=7, count=895)
        result = SimpleNamespace(consumed=(), rewards=(reward,))
        owner = SimpleNamespace(_world_quest_reward_items={7: (prototype, True)})
        updated, frames = _quest_inventory_change(owner, case.context(), result,
            inventory.validate_kit_frame(before), set())
        self.assertEqual([(r[1], r[4]) for r in rows(updated) if r[2] == 7], [(101, 1895)])
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in frames], [0x0965])


class CompanionStackTests(unittest.TestCase):
    def setUp(self):
        self.case = companion_tests.CompanionEquipmentTests()
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()

    def test_give_take_plain_currency_and_potion_keep_existing_uids(self):
        case = self.case
        original = case.bags.frames[2]
        values = rows(original)
        for row in values:
            if row[2] in (7, 14):
                row[18] = item_names()[row[2]]
        target = inventory.build_kit_frame(values)
        case.store.replace_kit(2, original, target)
        case.bags.frames[2] = target
        coin = next(r[1] for r in values if r[2] == 7)
        potion = next(r[1] for r in values if r[2] == 14)
        case.give(10, 7)
        case.give(30, 3)
        self.assertEqual([(r[1], r[4]) for r in rows(case.bags.frames[2]) if r[2] == 7], [(coin, 107)])
        self.assertEqual([(r[1], r[4]) for r in rows(case.bags.frames[2]) if r[2] == 14], [(potion, 3)])
        case.bags.take(1, case.actor, coin, 7, case.ctx.inventory_frame, owner_max_weight=10000)
        case.bags.take(1, case.actor, potion, 3, case.ctx.inventory_frame, owner_max_weight=10000)
        self.assertEqual([(r[1], r[4]) for r in rows(case.ctx.inventory_frame) if r[2] == 7], [(10, 100)])
        self.assertEqual([(r[1], r[4]) for r in rows(case.ctx.inventory_frame) if r[2] == 14], [(30, 20)])

    def test_companion_pickup_merges_named_currency(self):
        case = self.case
        original = case.bags.frames[2]
        values = rows(original)
        coin = next(row for row in values if row[2] == 7)
        # The general equipment fixture uses icon 71 for every item. A reward
        # pickup uses the actual item icon; keep this label-only case identical.
        coin[7] = case.ctx.world.data.items[7].icon
        coin[18] = item_names()[7]
        target = inventory.build_kit_frame(values)
        case.store.replace_kit(2, original, target)
        case.bags.frames[2] = target
        drop = case.ground()
        case.bags.pickup(case.actor, drop, case.fixture.now)
        self.assertEqual(rows(case.store.restore(2)),
            [{**row, 4: row[4] + (3 if row[1] == coin[1] else 0)} for row in values])
        self.assertEqual([(r[1], r[4]) for r in rows(case.store.restore(2)) if r[2] == 7], [(coin[1], 103)])
        self.assertIsNone(case.ctx.world.ground.get(drop.ref))

    def test_failed_transfer_preserves_journal_then_recovery_precedes_load_repair(self):
        case = self.case
        original = case.bags.frames[2]
        values = rows(original)
        coin = next(row for row in values if row[2] == 7)
        values.append({**coin, 1: 35, 4: 5, 18: item_names()[7]})
        target = inventory.build_kit_frame(values)
        case.store.replace_kit(2, original, target, append=True)
        case.bags.frames[2] = target
        save = case.store.replace_kit
        def fail_target(uid, *args, **kwargs):
            if uid == 2:
                raise OSError('STACK_TARGET_WRITE_FAILED')
            return save(uid, *args, **kwargs)
        with patch.object(case.store, 'replace_kit', side_effect=fail_target):
            with self.assertRaisesRegex(OSError, 'STACK_TARGET_WRITE_FAILED'):
                case.give(10, 7)
        self.assertTrue(case.bags.intent_path.exists())
        recovered = case.new_bags()
        self.assertFalse(recovered.intent_path.exists())
        self.assertEqual(len([r for r in rows(case.store.restore(2)) if r[2] == 7]), 2)
        recovered.initialize(2)
        self.assertEqual([(r[1], r[4]) for r in rows(recovered.frames[2]) if r[2] == 7], [(35, 112)])
        again = case.new_bags()
        again.initialize(2)
        self.assertEqual(again.frames[2], recovered.frames[2])


if __name__ == '__main__':
    unittest.main()
