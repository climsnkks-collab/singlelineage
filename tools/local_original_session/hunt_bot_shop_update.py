"""New shop items through owned FIRST/login/select/world and issued trade lists.

Reuses Matrix's socket peer, LOCAL native-layout inventory adapter, retained
fresh test profile and normal Quit/FIRST cleanup. This is packet/save evidence;
no original client runs and no native shop rendering/input claim is made.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.local_original_session import hunt_bot as hb, inventory
from tools.local_original_session import hunt_bot_play_matrix as matrix


def counts(frame):
    result = Counter()
    for item in inventory.validate_kit_frame(frame):
        row = dict(item.raw_fields)
        result[row[2] & 0xffffffff] += row[4]
    return result


class ShopUpdateScenario(matrix.Matrix):
    def __init__(self, args, directory):
        super().__init__(args, 'shop_update', directory)
        self.map_start = (args.start_map, args.start_x, args.start_y)

    async def open(self, *, seed, character=None, deliver=True):
        # Matrix owns the pre-login initialization slot and persistence rules.
        # Only an explicitly requested buyback-only fixture uses that slot.
        self.name = 'enchant_poly' if seed and self.args.buyback_template else 'shop_update'
        try:
            await super().open(seed=seed, character=character, deliver=deliver)
        finally:
            self.name = 'shop_update'
        if seed:
            self.fixture_notes.append(dict(start=self.map_start,
                inventory='fresh test_knight; no new BUY item injected',
                scope='explicit saved-map starting fixture; no public map-entry claim'))

    def initialize_enchant_fixture(self):
        """One fresh pre-login supply, never an acquisition or UID issuance claim."""
        from tools.local_original_session import equipment_store
        frame = self.broker._inventory_kit_frame(1)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        by_template = {row[2]: row for row in rows}
        template = self.args.buyback_template
        policy = self.broker._world_handler_bindings.item_policies.get(template)
        if policy is None or policy.grant_fields is None:
            raise matrix.MissingFeature(f'Buyback fixture policy unavailable: {template}')
        row = dict(policy.grant_fields)
        row.update({1: max(item[1] for item in rows) + 1, 2: template, 4: 1, 18: b''})
        rows.append(row)
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1, frame)
        data = self.broker._world.data
        worn = [entry.template_id for entry in data.starter.entries(1, 'test_knight') if entry.equipped]
        self.equipment.initialize_kit(1, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=next(by_template[t][1] for t in worn if data.items[t].kind == 'weapon'),
            slots=tuple((data.items[t].slot_key, by_template[t][1]) for t in worn if data.items[t].kind == 'armor'))
        self.fixture_notes.append(dict(pre_login_buyback_only_supply=dict(
            template=template, uid=row[1], count=1),
            source='startup-prepared product KitItemPolicy, fresh kit UID suffix, InventoryStore.grant',
            scope='explicit test supply only; no natural acquisition or product UID issuance claim'))

    def saved_counts(self):
        return counts(self.store.restore(self.bot.self_uid))

    def received_counts(self):
        result = Counter()
        for row in self.bot.inventory.values():
            result[row[2] & 0xffffffff] += row[4]
        return result

    async def approach_shop(self, npc_id):
        sources = self.broker._world_handler_bindings.sources
        candidates = [(self.broker._world.entities.resolve(ref), npc)
            for ref, npc, _ in self.broker._world.town._owned.values()
            if npc.npc_id == npc_id and npc.spawn['mapid'] == self.bot.map_id
            and npc.key in sources]
        candidates = [(entity, npc) for entity, npc in candidates if entity is not None]
        if not candidates:
            raise matrix.MissingFeature(f'Current shop menu NPC{npc_id} unavailable')
        entity, npc = min(candidates, key=lambda pair: hb.distance(self.bot.position, (pair[0].x, pair[0].y)))
        await self.navigate((entity.x, entity.y), radius=2)
        self.record('received_current_shop_' + str(npc_id), entity.uid in self.bot.live_appearances,
            npc_id=npc_id, uid=entity.uid, placement=npc.key)
        return entity

    async def sell_issued(self, npc, template, label, *, buyback_only=False):
        if buyback_only:
            opened = await self.window(npc.uid, 'buy', 0x4e48)
            offered = [hb.fields(raw) for raw in opened.get(3, ())]
            self.record(label + '_absent_from_buy', not any(hb.scalar(row, 2) == template for row in offered),
                template=template)
        opened = await self.window(npc.uid, 'sell', 0x4ee7)
        rows = [hb.fields(raw) for raw in opened.get(3, ())]
        row = next((row for row in rows if
            (item := self.bot.inventory.get(hb.scalar(row, 1))) is not None
            and item[2] & 0xffffffff == template and item[4] > 0), None)
        if row is None:
            raise matrix.MissingFeature(f'Owned template{template} absent from issued SELL list')
        uid, price = hb.scalar(row, 1), hb.scalar(row, 2)
        before = self.saved_counts()
        await self.trade(hb.scalar(opened, 1), 6, uid, 1)
        expected = before.copy()
        expected[template] -= 1
        expected[7] += price
        self.record(label + '_removed_credited_saved', self.saved_counts() == expected
            and self.received_counts() == expected,
            template=template, uid=uid, issued_unit_price=price,
            before=dict(before), after=dict(self.saved_counts()))

    async def shop_update(self):
        self.stage = 'new_item_buy_sell'
        npc = await self.approach_shop(self.args.npc)
        opened = await self.window(npc.uid, 'buy', 0x4e48)
        rows = [hb.fields(raw) for raw in opened.get(3, ())]
        row = next((row for row in rows if hb.scalar(row, 2) == self.args.template), None)
        if row is None:
            raise matrix.MissingFeature(f'New template{self.args.template} absent from issued BUY list')
        before, price = self.saved_counts(), hb.scalar(row, 4)
        before_uids = set(self.bot.inventory)
        await self.trade(hb.scalar(opened, 1), 5, hb.scalar(row, 1), 1)
        expected = before.copy()
        # Selected new item is a one-per-pack weapon; no setup copy is injected.
        expected[self.args.template] += 1
        expected[7] -= price
        self.record('new_item_purchased_debited_saved', self.saved_counts() == expected
            and self.received_counts() == expected,
            template=self.args.template, issued_row=hb.scalar(row, 1), issued_price=price,
            issued_new_uids=sorted(set(self.bot.inventory) - before_uids),
            before=dict(before), after=dict(self.saved_counts()))
        await self.sell_issued(npc, self.args.template, 'new_item_sell')
        if self.args.buyback_template:
            self.stage = 'buyback_only_sell'
            buyer = await self.approach_shop(self.args.buyback_npc or self.args.npc)
            await self.sell_issued(buyer, self.args.buyback_template, 'buyback_only', buyback_only=True)
        self.stage = 'saved_reconnect'
        before_frame, character = self.store.restore(self.bot.self_uid), self.bot.character
        self.record('normal_quit_before_reconnect', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('SHOP_UPDATE_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        self.record('shop_trade_inventory_restored', self.store.restore(self.bot.self_uid) == before_frame
            and self.received_counts() == counts(before_frame), after=dict(self.saved_counts()))
        self.record('shop_update_no_handler_errors', not any(self.error_codes().values()), errors=self.error_codes())


def parser():
    result = matrix.parser()
    result.description = __doc__
    result.set_defaults(scenario='shop_update')
    next(action for action in result._actions if action.dest == 'scenario').choices = ('shop_update',)
    result.add_argument('--npc', type=int, default=70016)
    result.add_argument('--template', type=int, default=13)
    result.add_argument('--buyback-npc', type=int, default=70018)
    result.add_argument('--buyback-template', type=int, default=40)
    result.add_argument('--start-map', type=int, default=4)
    result.add_argument('--start-x', type=int, default=33050)
    result.add_argument('--start-y', type=int, default=32782)
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2]
    runs = root / 'work/local_original_session/runs'
    runs.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='shop-update-bot-', dir=runs))
    # Extend the existing per-run manifest only for sources changed by this task.
    files = [Path(__file__), Path(__file__).with_name('world_shop.py'),
        Path(__file__).with_name('world_shop_menu.py')]
    for region in ('m2', 'm4', 'm5'):
        files.extend(Path(__file__).parent.glob('data/' + region + '/shop*.json'))
    files.extend(Path(__file__).parent.glob('data/shop_item*.json'))
    for path in files:
        matrix.SOURCE_SHA256[str(path.relative_to(root))] = dict(file=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), basis='initial shop scenario source')
    scene = ShopUpdateScenario(args, directory)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1, SL_EXPERIMENT_WAREHOUSE=1,
            SL_WORLD_TOWN_CANDIDATES='', SL_COMPANION=0, SL_SPELL_EXP=0,
            SL_COMPANION_PET_UI=0, SL_COMPANION_REVIVE_EXP=0):
        return await scene.run_matrix()


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(dict(status=result['status'], directory=result['directory'],
        failure=result['failure'], gaps=result['gaps'], checks=len(result['checks']),
        requests=result['requests'], cleanup_complete=result['cleanup_complete']), ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
