"""Lane4 socket integration on preserved fresh fixtures; no native/UI claim.

Only setup supplies a test_knight kit, explicit LOCAL scroll grade, level and
equipment sidecar. Requests use the existing FIRST/login/selection peer and
broker decoder/router. ItemEquipmentEffect's saved combat inputs are attached
without its native preparation; this remains a development fixture boundary.
Run only as the single authorized port owner after source freeze.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from tools.local_original_session import hunt_bot as hb, hunt_bot_scenarios as hs
from tools.local_original_session import inventory, world_enchant_inventory as enchant, test_ports
from tools.local_original_session import broker as host
from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
from tools.local_original_session.world_state_services import InventoryTransactions


class Connection:
    def __init__(self, directory):
        self.directory = directory
        self.broker = self.bot = None
        self.checks = []

    def check(self, name, condition, **details):
        self.checks.append(dict(check=name, success=bool(condition), **details))
        if not condition:
            raise AssertionError(name)

    async def open(self, *, warehouse=False):
        self.directory.mkdir(parents=True, exist_ok=False)
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(
            self.directory, expected, seed=True)
        broker = self.broker
        # Reuse real saved equipment consumption; do not invoke native prepare.
        effect = object.__new__(ItemEquipmentEffect)
        effect.store, effect._defs = self.equipment, broker._world.data.items
        effect._kit_policy, effect._collection_policy = inventory.KIT_POLICY, None
        effect._selection, effect._last = None, dict(status='FIXTURE_SAVED_EQUIPMENT_ONLY')
        broker._item_equipment_effect = effect
        broker._world_pc_profile = host.PersistentBroker._world_pc_profile.__get__(broker)
        before = self.store.restore(1)
        rows = [dict(i.raw_fields) for i in inventory.validate_kit_frame(before)]
        self.weapon_uid = self.equipment.restore(1, before).weapon_uid
        self.armor_uid = self.equipment.restore(1, before).slots[0][1]
        if not warehouse:
            self.destroy_target_uid = next(r[1] for r in rows if r[2] == 41)
            for row in rows:
                if row[1] == self.destroy_target_uid:
                    row[18] = enchant.enchanted_name(broker._world.data.items[41], -7)
            next_uid = max(r[1] for r in rows) + 1
            self.scrolls = (next_uid, next_uid + 1)
            self.cursed_scroll_uid = next_uid + 2
            for uid, template, count, grade in ((next_uid, 25, 1, 1),
                    (next_uid + 1, 26, 2, 1), (next_uid + 2, 25, 1, 2)):
                fields = dict(host.INVENTORY_STARTER_FIELDS)
                fields.update({1: uid, 2: template, 4: count, 7: 0,
                               18: enchant.scroll_name(template, grade)})
                rows.append(fields)
        after = inventory.build_kit_frame(rows)
        self.store.replace_kit(1, before, after, append=True)
        broker._inventory_current_frame = after
        broker._world_inventory_transactions = InventoryTransactions(self.store)
        if warehouse:
            from tools.local_original_session import movement
            from tools.local_original_session.world_progress import Progress
            broker._world_progress.commit(1, Progress(broker._world.data.pc_exp[4], 5))
            from tools.local_original_session.hunt_bot_loopback import START, KNIGHT
            position = broker.realm.positions.restore(movement.Position(1, KNIGHT[0], 0, *START))
            broker.realm.positions.commit(position,
                movement.Position(1, position.name, 0, 32577, 32946))
        await broker.start()
        args = hb.parser().parse_args(['--expected-uuid', expected, '--timeout', '15'])
        args.port = test_ports.port(args.port)
        args.character = None
        self.bot = hs.ScenarioBot(args)
        self.bot.data, self.bot.started = broker._world.data, time.monotonic()
        await self.bot.login()
        await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'KIT')

    async def close(self):
        error = None
        if self.bot is not None:
            try:
                await self.bot.quit_selected()
            except Exception as failure:
                error = str(failure)
            finally:
                for peer in self.bot.peers:
                    await peer.close()
        if self.broker is not None:
            self.report = self.broker.report()
            self.closed = await self.broker.close()
            self.checks.append(dict(check='cleanup', success=bool(
                self.closed.get('cleanup_complete') and not error
                and not self.report.get('failure_code')), quit_error=error,
                failure_code=self.report.get('failure_code'),
                cleanup_complete=self.closed.get('cleanup_complete')))

    async def targeted(self, scroll_uid, target_uid):
        params = b''.join(hb.uint(n, value) for n, value in
            ((1, 1), (2, target_uid), (3, 0), (15, 0), (16, 0)))
        body = hb.uint(1, scroll_uid) + hb.pb.encode_bytes(2, params)
        def complete(batch):
            updates = [f for f in batch if f.opcode in (0x0965, 0x0978)]
            return hb.find([f for f in batch if updates and f.ordinal > updates[-1].ordinal],
                           0x4e38, **{'1': self.bot.self_uid})
        return await self.bot.peer.request(0x0960, body, check=complete, label='TARGETED_ENCHANT')

    async def enchants(self):
        broker, bot = self.broker, self.bot
        uid = bot.self_uid
        full = next(f for f in bot.peer.frames if f.opcode == 0x4e38)
        self.check('fresh_lawful_500', hb.scalar(full.values, 18) == 500,
                   received=hb.scalar(full.values, 18))
        original_ac = broker._world.combat.pcs[uid].profile.ac
        for scroll, target in zip(self.scrolls, (self.weapon_uid, self.armor_uid)):
            old = {i.identifier: i for i in inventory.validate_kit_frame(self.store.restore(uid))}
            count = dict(old[scroll].raw_fields)[4]
            batch = await self.targeted(scroll, target)
            saved = {i.identifier: i for i in inventory.validate_kit_frame(self.store.restore(uid))}
            level = enchant.enchant_level(saved[target], broker._world.data.items[saved[target].template_bits])
            self.check('enchant_saved_and_received_name', level == 1 and
                bot.inventory[target].get(18) == dict(saved[target].raw_fields)[18], target=target, level=level)
            self.check('scroll_quantity_or_remove',
                (scroll not in saved and scroll not in bot.inventory and any(f.opcode == 0x0978 for f in batch))
                if count == 1 else (dict(saved[scroll].raw_fields)[4] == count - 1
                    and bot.inventory[scroll][4] == count - 1 and any(f.opcode == 0x0965 for f in batch)),
                scroll=scroll, quantity_before=count)
            status = [f for f in batch if f.opcode == 0x4e38][-1]
            state = broker._world.combat.pcs[uid]
            self.check('full_status_saved_stats', set(range(4, 15)) <= set(status.values)
                and hb.scalar(status.values, 18) == 500
                and hb.scalar(status.values, 14) == (-state.profile.ac & ((1 << 64) - 1)),
                ac=state.profile.ac, fields=sorted(status.values))
            self.check('default_no_unknown_enchant_packet', not any(f.opcode == 0x0967 for f in batch))
        state = broker._world.combat.pcs[uid]
        self.check('combat_consumes_weapon_enchant_and_armor_ac',
            state.profile.weapon.enchant == 1 and state.profile.ac == original_ac - 1,
            weapon_enchant=state.profile.weapon.enchant, ac_before=original_ac, ac_after=state.profile.ac)
        equipment_before = self.equipment.restore(uid, self.store.restore(uid))
        self.check('destruction_explicit_dev_startstate', self.destroy_target_uid not in
            {equipment_before.weapon_uid, *(member for _, member in equipment_before.slots)}
            and enchant.enchant_level(next(i for i in inventory.validate_kit_frame(self.store.restore(uid))
                if i.identifier == self.destroy_target_uid), broker._world.data.items[41]) == -7,
            template=41, local_level=-7, local_cursed_grade=2)
        batch = await self.targeted(self.cursed_scroll_uid, self.destroy_target_uid)
        saved = {i.identifier: i for i in inventory.validate_kit_frame(self.store.restore(uid))}
        removed = {hb.scalar(f.values, 1) for f in batch if f.opcode == 0x0978}
        expected = {self.cursed_scroll_uid, self.destroy_target_uid}
        self.check('destroyed_target_and_scroll_received_and_saved', expected <= removed
            and not expected.intersection(saved) and not expected.intersection(bot.inventory),
            removed_uids=sorted(removed))
        equipment_after = self.equipment.restore(uid, self.store.restore(uid))
        status = [f for f in batch if f.opcode == 0x4e38][-1]
        self.check('bag_destruction_preserves_equipment_and_full_stats',
            equipment_after == equipment_before and state.profile.weapon.enchant == 1
            and state.profile.ac == original_ac - 1 and set(range(4, 15)) <= set(status.values),
            native_equipped_destruction='UNKNOWN: not exercised; no native097A stand-in')

    async def bank_window(self, action):
        bot = self.bot
        # Resolve only an appearance actually delivered in this selected world.
        npc = next((hb.scalar(f.values, 2) for f in bot.peer.frames
            if f.opcode == 0x4e96 and hb.scalar(f.values, 3) == 143), None)
        self.check('warehouse_received_npc', npc is not None, npc_uid=npc)
        await bot.peer.request(0x4e43, hb.uint(1, npc),
            check=lambda batch: hb.find(batch, 0x4e44), label='WAREHOUSE_CLICK')
        payload = (hb.uint(1, npc) + hb.pb.encode_bytes(2, action.encode())
                   + hb.uint(4, 0) + hb.uint(5, 0))
        opcode = 0x4ed2 if action == 'deposit' else 0x0971
        batch = await bot.peer.request(0x4ed4, payload,
            check=lambda batch: hb.find(batch, opcode), label='WAREHOUSE_' + action.upper())
        return hb.fields(hb.find(batch, opcode).wire[4:-2])

    async def bank_trade(self, context, mode, key, quantity):
        child = hb.uint(1, key) + hb.uint(2, quantity)
        payload = (hb.uint(1, context) + hb.uint(2, mode)
            + hb.pb.encode_bytes(3, child) + hb.uint(4, 0) + hb.uint(5, 0))
        return await self.bot.peer.request(0x4ed1, payload, alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label='WAREHOUSE_TRADE')

    async def banks(self):
        bot, broker = self.bot, self.broker
        before = {i.identifier: i for i in inventory.validate_kit_frame(self.store.restore(1))}
        item = next(i for i in before.values() if i.template_bits == 14)
        coins = next(i for i in before.values() if i.template_bits == 7)
        quantity, cash = dict(item.raw_fields)[4], dict(coins.raw_fields)[4]
        opened = await self.bank_window('deposit')
        batch = await self.bank_trade(hb.scalar(opened, 4), 1, item.identifier, 2)
        saved = inventory.validate_kit_frame(self.store.restore(1))
        bank = inventory.validate_kit_frame(broker._world_inventory_transactions.restore_warehouse(1))
        self.check('deposit_saved_and_received', len(bank) == 1
            and bank[0].template_bits == 14 and dict(bank[0].raw_fields)[4] == 2
            and bot.inventory[item.identifier][4] == quantity - 2,
            bank_uid=bank[0].identifier, player_quantity=bot.inventory[item.identifier][4])
        await bot.peer.request(0x097b, alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label='WAREHOUSE_CLOSE')
        listed = await self.bank_window('retrieve')
        issued = [hb.fields(raw) for raw in listed.get(7, ())]
        key = next(hb.scalar(row, 1) for row in issued
            if hb.scalar(hb.fields(hb.scalar(row, 2)), 1) == bank[0].identifier)
        self.check('reopen_full_saved_iteminfo', len(issued) == 1
            and hb.scalar(hb.fields(hb.scalar(issued[0], 2)), 18)
                == dict(bank[0].raw_fields).get(18), context=hb.scalar(listed, 1), received_key=key)
        await self.bank_trade(hb.scalar(listed, 1), 2, key, 2)
        self.check('withdraw_received_fee_and_inventory',
            bot.inventory[item.identifier][4] == quantity
            and bot.inventory[coins.identifier][4] == cash - 30
            and broker._world_inventory_transactions.restore_warehouse(1) is None,
            quantity=bot.inventory[item.identifier][4], cash_before=cash,
            cash_after=bot.inventory[coins.identifier][4])
        await bot.peer.request(0x097b, alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label='WAREHOUSE_CLOSE')
        reopened = await self.bank_window('retrieve')
        self.check('empty_reopen_no_rows', not reopened.get(7), active=hb.scalar(reopened, 8))
        from tools.local_original_session.inventory_store import InventoryStore, POLICY
        fresh = InventoryStore(self.directory / 'characters.json', policy=POLICY,
                               kit_policy=inventory.KIT_POLICY)
        restored = {i.identifier: dict(i.raw_fields) for i in inventory.validate_kit_frame(fresh.restore(1))}
        self.check('fresh_store_persistence', restored[item.identifier][4] == quantity
            and restored[coins.identifier][4] == cash - 30
            and InventoryTransactions(fresh).restore_warehouse(1) is None,
            saved_cash=restored[coins.identifier][4])


async def run(directory, selected='all'):
    directory.mkdir(parents=True, exist_ok=False)
    sources = {name: hashlib.sha256(Path(__file__).with_name(name + '.py').read_bytes()).hexdigest()
        for name in ('broker', 'world_handlers', 'world_enchant', 'world_enchant_inventory',
                     'world_warehouse', 'world_stats', 'world_status_frames',
                     'world_town_services', 'world_progress', 'world_lane4_connection_tests')}
    results = []
    cases = ('enchants', 'banks') if selected == 'all' else (selected,)
    for name in cases:
        conn, error = Connection(directory / name), None
        old = os.environ.get('SL_EXPERIMENT_WAREHOUSE')
        if name == 'banks':
            os.environ['SL_EXPERIMENT_WAREHOUSE'] = '1'
        try:
            await conn.open(warehouse=name == 'banks')
            await getattr(conn, name)()
        except Exception as failure:
            error = f'{type(failure).__name__}: {failure}'
        finally:
            await conn.close()
            if old is None:
                os.environ.pop('SL_EXPERIMENT_WAREHOUSE', None)
            else:
                os.environ['SL_EXPERIMENT_WAREHOUSE'] = old
        results.append(dict(case=name, error=error, checks=conn.checks,
                            world=getattr(conn, 'report', {}).get('world')))
        if not getattr(conn, 'closed', {}).get('cleanup_complete', False):
            break
    return dict(status='SUCCESS' if len(results) == len(cases) and all(
        r['error'] is None and all(c['success'] for c in r['checks']) for r in results) else 'FAILED',
        scope='development fresh fixture, FIRST/login/selection and raw routed packets; no native input/render proof',
        profile_path=str(directory), source_sha256=sources, results=results)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--case', choices=('all', 'enchants', 'banks'), default='all')
    args = parser.parse_args(argv)
    result = asyncio.run(run(args.output.resolve(), args.case))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
