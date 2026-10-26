"""Pure M2 service boundary/conservation tests; no game/server/port/store import."""
from dataclasses import FrozenInstanceError, replace
import unittest

from tools.local_original_session import world_town_services as s


def item(uid, item_id=14, count=1, *, stackable=True, variant=b'normal',
         weight=1000, allowed=True, equipped=False, controlled=False):
    return s.ServiceItem(uid, item_id, count, stackable, variant, weight,
                         allowed, equipped, controlled)


def coins(count=100, uid=1):
    return item(uid, 7, count, weight=0)


class TownServicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = s.load_town_services()

    def refuses(self, code, func, *args, **kwargs):
        with self.assertRaisesRegex(s.TownServiceError, '^' + code + '$'):
            func(*args, **kwargs)

    def bank(self, player, warehouse, selections, **kwargs):
        return s.calculate_deposit(self.data, player, warehouse, selections,
                                   level=kwargs.pop('level', 5), **kwargs)

    def withdraw(self, player, warehouse, selections, **kwargs):
        return s.calculate_withdrawal(self.data, player, warehouse, selections,
            level=kwargs.pop('level', 5), max_weight=kwargs.pop('max_weight', 10000), **kwargs)

    def test_actual_configuration_and_known_routes(self):
        self.assertEqual((self.data.warehouse_slots, self.data.player_slots,
                          self.data.withdrawal_fee, self.data.minimum_level), (150, 180, 30, 5))
        routes = s.teleport_destinations(self.data, 50015)
        self.assertEqual(len(routes), 1)
        self.assertEqual((routes[0].map_id, routes[0].x, routes[0].y, routes[0].price),
                         (4, 32608, 32734, 1500))
        self.assertEqual(s.teleport_destinations(self.data, 50017), ())
        self.refuses('UNKNOWN_TELEPORTER', s.teleport_destinations, self.data, 99999)
        with self.assertRaises(TypeError):
            self.data.teleports[(1, 'fake')] = routes[0]

    def test_teleport_funds_and_action_is_npc_specific(self):
        plan = s.calculate_teleport(self.data, 50015, 'teleport island-gludin', adena=1500, level=99)
        self.assertEqual((plan.cost, plan.adena_after), (1500, 0))
        self.refuses('INSUFFICIENT_ADENA', s.calculate_teleport, self.data, 50015,
                     'teleport island-gludin', adena=1499, level=5)
        self.refuses('UNKNOWN_DESTINATION', s.calculate_teleport, self.data, 50016,
                     'teleport island-gludin', adena=10000, level=5)

    def test_novice_limit_uses_config13_not_fallback15(self):
        plan = s.calculate_teleport(self.data, 50016, 'teleport singing-island', adena=0, level=12)
        self.assertEqual((plan.cost, plan.adena_after, plan.destination.map_id), (0, 0, 68))
        self.refuses('DESTINATION_LEVEL_LIMIT', s.calculate_teleport, self.data, 50016,
                     'teleport singing-island', adena=500, level=13)

    def test_inn_explicit_cost_and_full_recovery(self):
        args = dict(adena=10, hp=1, max_hp=200, mp=0, max_mp=20)
        self.refuses('INN_PRICE_UNRESOLVED', s.calculate_inn_rest, self.data, 70012, **args)
        plan = s.calculate_inn_rest(self.data, 70012, **args, price=10)
        self.assertEqual((plan.cost, plan.adena_after, plan.hp_after, plan.mp_after), (10, 0, 200, 20))
        self.refuses('INSUFFICIENT_ADENA', s.calculate_inn_rest, self.data, 70012, **args, price=11)
        self.refuses('UNKNOWN_INN', s.calculate_inn_rest, self.data, 71030, **args, price=5)
        self.refuses('INVALID_INTEGER', s.calculate_inn_rest, self.data, 70012,
                     **dict(args, hp=0), price=5)

    def test_inn_full_player_still_pays_and_zero_mp_valid(self):
        plan = s.calculate_inn_rest(self.data, 70012, adena=9, hp=5, max_hp=5,
                                   mp=0, max_mp=0, price=2)
        self.assertEqual((plan.adena_after, plan.hp_after, plan.mp_after), (7, 5, 0))

    def test_partial_deposit_and_inputs_unchanged(self):
        player = [coins(), item(2, count=10)]
        warehouse = [item(3, count=5)]
        before = (tuple(player), tuple(warehouse))
        plan = self.bank(player, warehouse, [(2, 4)])
        self.assertEqual((plan.fee, plan.adena_after, plan.player_slots_after,
                          plan.warehouse_slots_after), (0, 100, 2, 1))
        self.assertEqual((plan.transfers[0].destination_uid, plan.transfers[0].count), (3, 4))
        self.assertEqual((tuple(player), tuple(warehouse)), before)
        self.assertIs(plan.transfers[0].item, player[1])
        with self.assertRaises(FrozenInstanceError):
            plan.fee = 1

    def test_whole_deposit_frees_slot_and_splits_require_no_uid_issuance(self):
        plan = self.bank([item(2, count=10)], [], [(2, 10)])
        self.assertEqual((plan.player_slots_after, plan.warehouse_slots_after), (0, 1))
        self.assertEqual((plan.transfers[0].destination_uid, plan.transfers[0].new_slot), (None, 0))

    def test_deposit_adena_wallet_conservation(self):
        plan = self.bank([coins(100)], [coins(10, uid=2)], [(1, 40)])
        self.assertEqual((plan.adena_before, plan.adena_after, plan.fee), (100, 60, 0))
        self.assertEqual(plan.transfers[0].destination_uid, 2)

    def test_level_and_eligibility_refusal(self):
        self.refuses('WAREHOUSE_LEVEL_REQUIRED', self.bank, [item(1)], [], [(1, 1)], level=4)
        for field in ('equipped', 'controlled'):
            row = replace(item(1), **{field: True})
            self.refuses('ITEM_NOT_DEPOSITABLE', self.bank, [row], [], [(1, 1)])
        self.refuses('ITEM_NOT_DEPOSITABLE', self.bank, [item(1, allowed=False)], [], [(1, 1)])

    def test_full_warehouse_accepts_only_compatible_merge(self):
        warehouse = [item(1000 + n, 100 + n) for n in range(150)]
        plan = self.bank([item(1, 100)], warehouse, [(1, 1)])
        self.assertEqual(plan.warehouse_slots_after, 150)
        self.refuses('SLOT_LIMIT', self.bank, [item(1, 999)], warehouse, [(1, 1)])
        self.refuses('SLOT_LIMIT', self.bank, [item(1, 100, variant=b'blessed')], warehouse, [(1, 1)])

    def test_batch_slot_limit_cannot_partially_apply(self):
        warehouse = [item(1000 + n, 100 + n) for n in range(149)]
        player = [item(1, 1000), item(2, 1001)]
        before = tuple(player), tuple(warehouse)
        self.refuses('SLOT_LIMIT', self.bank, player, warehouse, [(1, 1), (2, 1)])
        self.assertEqual((tuple(player), tuple(warehouse)), before)

    def test_withdraw_fee_per_uid_not_item_quantity(self):
        player = [coins(100)]
        warehouse = [item(2, count=20)]
        plan = self.withdraw(player, warehouse, [(2, 4), (2, 6)])
        self.assertEqual((plan.fee, plan.adena_after, plan.fee_debits), (30, 70, ((1, 30),)))
        self.assertEqual((len(plan.transfers), plan.transfers[0].count), (1, 10))
        self.assertEqual((player, warehouse), ([coins(100)], [item(2, count=20)]))

    def test_multiple_entries_and_exact_wallet(self):
        plan = self.withdraw([coins(60)], [item(2, 14), item(3, 15)], [(2, 1), (3, 1)])
        self.assertEqual((plan.fee, plan.adena_after, plan.player_slots_after,
                          plan.warehouse_slots_after, plan.fee_debits), (60, 0, 2, 0, ((1, 60),)))

    def test_cannot_pay_fee_with_money_being_withdrawn(self):
        self.refuses('INSUFFICIENT_ADENA', self.withdraw, [], [coins(100, 2)], [(2, 100)])
        plan = self.withdraw([coins(30)], [coins(100, 2)], [(2, 100)])
        self.assertEqual((plan.fee, plan.adena_before, plan.adena_after), (30, 30, 100))
        self.assertEqual((plan.transfers[0].destination_uid, plan.transfers[0].new_slot), (None, 0))

    def test_full_player_before_fee_check(self):
        player = [coins(30)] + [item(1000 + n, 100 + n) for n in range(179)]
        self.refuses('SLOT_LIMIT', self.withdraw, player, [item(2, 999)], [(2, 1)])
        plan = self.withdraw(player, [item(2, 100)], [(2, 1)])
        self.assertEqual(plan.player_slots_after, 179)  # existing stack, wallet removed

    def test_weight_plus_one_and_rounded_gauge(self):
        # L1J round(240 * checkedWeight / maxWeight) must remain <240.
        self.withdraw([coins(50)], [item(2, weight=996000)], [(2, 1)], max_weight=1000)
        self.refuses('OVERWEIGHT', self.withdraw, [coins(50)], [item(2, weight=997000)],
                     [(2, 1)], max_weight=1000)

    def test_each_existing_light_stack_has_minimum_weight_one(self):
        player = [coins(50), item(3, 100, weight=1), item(4, 101, weight=1)]
        self.refuses('OVERWEIGHT', self.withdraw, player, [item(2, weight=995000)],
                     [(2, 1)], max_weight=1000)
        self.withdraw([coins(50)], [item(2, weight=995000)], [(2, 1)], max_weight=1000)

    def test_late_withdrawal_refusal_keeps_fees_and_first_item_unapplied(self):
        player = [coins(100)]
        warehouse = [item(2, 14), item(3, 15, weight=999000)]
        before = tuple(player), tuple(warehouse)
        self.refuses('OVERWEIGHT', self.withdraw, player, warehouse,
                     [(2, 1), (3, 1)], max_weight=1000)
        self.assertEqual((tuple(player), tuple(warehouse)), before)

    def test_adena_stack_limit_is_checked_before_fee(self):
        # As in checkAddItem before consumeItem, the fee cannot make room for
        # an otherwise overflowing incoming Adena stack.
        self.refuses('STACK_LIMIT', self.withdraw, [coins(s.MAX_AMOUNT)],
                     [coins(1, 2)], [(2, 1)])
        self.refuses('OVERWEIGHT', self.withdraw, [coins(50)], [item(2, weight=999000)],
                     [(2, 1)], max_weight=1000)

    def test_2g_stack_overflow_and_insufficient_counts(self):
        self.refuses('STACK_LIMIT', self.bank, [item(1)], [item(2, count=s.MAX_AMOUNT)], [(1, 1)])
        self.refuses('INSUFFICIENT_ITEMS', self.bank, [item(1)], [], [(1, 1), (1, 1)])
        self.refuses('ITEM_NOT_OWNED', self.bank, [item(1)], [], [(999, 1)])

    def test_unknown_and_inconsistent_metadata_refuses(self):
        self.refuses('DUPLICATE_UID', self.bank, [item(1)], [item(1)], [])
        self.refuses('AMBIGUOUS_STACK', self.bank, [item(1), item(2)], [], [])
        self.refuses('INCONSISTENT_ITEM_METADATA', self.bank, [item(1)],
                     [item(2, weight=2000)], [(1, 1)])
        self.refuses('INCOMPATIBLE_ADENA_STACK', self.bank, [coins(10)],
                     [replace(coins(10, 2), variant=b'other')], [(1, 1)])

    def test_integer_and_nonstackable_contracts(self):
        for count in (0, -1, True, 1.5, s.MAX_AMOUNT + 1):
            self.refuses('INVALID_INTEGER', self.bank, [item(1)], [], [(1, count)])
        self.refuses('INVALID_ITEM', self.bank, [item(1, count=2, stackable=False)], [], [])
        self.refuses('INVALID_INTEGER', self.withdraw, [coins()], [], [], max_weight=0)

    def test_empty_selection_has_no_fee(self):
        self.assertEqual(self.bank([], [], []).fee, 0)
        self.assertEqual(self.withdraw([], [], []).fee_debits, ())

    def test_conservation_across_partial_whole_variant_and_fee(self):
        player = [coins(100), item(2, count=3), item(3, 20, stackable=False)]
        warehouse = [item(10, count=4), item(11, 14, count=5, variant=b'blessed')]
        plan = self.withdraw(player, warehouse, [(10, 2), (11, 3)])
        before = {}
        for row in player + warehouse:
            key = row.item_id, row.variant
            before[key] = before.get(key, 0) + row.count
        # Materialize the numeric proposal in independent test-owned dictionaries.
        # No codec/store/UID allocator is invoked; ('new', n) is a plan label.
        projected_player = {r.uid: r for r in player}
        projected_warehouse = {r.uid: r for r in warehouse}
        for uid, count in plan.fee_debits:
            projected_player[uid] = replace(projected_player[uid],
                                            count=projected_player[uid].count - count)
        for line in plan.transfers:
            source = projected_warehouse[line.item.uid]
            if source.count == line.count:
                del projected_warehouse[source.uid]
            else:
                projected_warehouse[source.uid] = replace(source, count=source.count - line.count)
            key = line.destination_uid if line.destination_uid is not None else ('new', line.new_slot)
            if key in projected_player:
                old = projected_player[key]
                projected_player[key] = replace(old, count=old.count + line.count)
            else:
                projected_player[key] = replace(line.item, count=line.count)
        after = {}
        for row in list(projected_player.values()) + list(projected_warehouse.values()):
            key = row.item_id, row.variant
            after[key] = after.get(key, 0) + row.count
        expected = dict(before)
        expected[(7, b'normal')] -= plan.fee
        self.assertEqual(after, expected)
        self.assertEqual(plan.adena_after, after[(7, b'normal')])
        self.assertEqual(sum(line.count for line in plan.transfers), 5)
        self.assertEqual(before[(14, b'normal')], 7)
        self.assertEqual(before[(14, b'blessed')], 5)
        self.assertEqual((plan.player_slots_after, plan.warehouse_slots_after), (4, 2))
        self.assertEqual((plan.transfers[0].destination_uid, plan.transfers[1].new_slot), (2, 1))


if __name__ == '__main__':
    unittest.main()
