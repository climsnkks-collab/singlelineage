"""M5 town/field socket scenario on a retained fresh development profile.

Reuses Matrix's FIRST/login/selection, native-layout LOCAL inventory adapter,
issued NPC/menu/list references and cleanup. No original client is executed;
packet observations do not establish native rendering/input equivalence.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.local_original_session import hunt_bot as hb, inventory
from tools.local_original_session import hunt_bot_play_matrix as matrix


def bag_counts(frame):
    result = Counter()
    if frame is not None:
        for item in inventory.validate_kit_frame(frame):
            fields = dict(item.raw_fields)
            result[fields[2] & 0xffffffff] += fields[4]
    return result


class M5Scenario(matrix.Matrix):
    def __init__(self, args, directory):
        super().__init__(args, 'm5', directory)
        self.map_start = (4, 32608, 32734)

    async def open(self, *, seed, character=None, deliver=True):
        # Reuse the existing fresh pre-login level5 fixture. It establishes the
        # warehouse level requirement; no live HP/EXP/RNG or guard is replaced.
        self.name = 'warehouse_roundtrip' if seed else 'm5'
        try:
            await super().open(seed=seed, character=character, deliver=deliver)
        finally:
            self.name = 'm5'
        if seed:
            self.fixture_notes.append(dict(start=self.map_start,
                reason='explicit fresh Gludin starting snapshot; not a public map-entry claim',
                inventory='existing test_knight starter; no M5 item/UID/reward injection'))

    def saved_counts(self):
        return bag_counts(self.store.restore(self.bot.self_uid))

    def bank_counts(self):
        return bag_counts(self.broker._world_inventory_transactions.restore_warehouse(self.bot.self_uid))

    async def navigate(self, goal, *, radius=0, predicate=None):
        bot, deadline = self.bot, time.monotonic() + self.args.navigation_timeout
        start, moves = bot.position, bot.moves
        while not (predicate() if predicate else hb.distance(bot.position, goal) <= radius):
            if bot.dead:
                raise hb.BotFailure('M5_OWNER_DIED_DURING_NAVIGATION')
            if time.monotonic() >= deadline:
                raise hb.BotFailure('M5_NAVIGATION_DEADLINE')
            if bot.hp < bot.max_hp * .75:
                await self.use(14)
            else:
                await bot.step(goal, radius)
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.05)
        await bot.alive()
        return dict(start=start, finish=bot.position, accepted_steps=bot.moves - moves)

    def position_snapshot(self):
        bot = self.bot
        writer = next(row['writer'] for rows in self.broker._claims.values() for row in rows
                      if self.broker._world_pcs.get(id(row['writer']), (None, None))[1] == bot.self_uid)
        current = self.broker.realm.service(writer).snapshot()
        saved = self.broker.realm.positions.restore(current)
        entity = self.broker._world.entities.get(bot.self_uid)
        return dict(wire=(bot.map_id, *bot.position),
            current=(current.map_id, current.word0, current.word1),
            saved=(saved.map_id, saved.word0, saved.word1),
            entity=(entity.map_id, entity.x, entity.y))

    def current_town_npc(self, npc_id):
        candidates = [(self.broker._world.entities.resolve(ref), npc)
            for ref, npc, _ in self.broker._world.town._owned.values()
            if npc.npc_id == npc_id and npc.spawn['mapid'] == self.bot.map_id]
        candidates = [(e, n) for e, n in candidates if e is not None]
        if not candidates:
            raise matrix.MissingFeature(f'M5 current NPC{npc_id} unavailable')
        return min(candidates, key=lambda pair: hb.distance(self.bot.position, (pair[0].x, pair[0].y)))

    async def approach(self, npc_id):
        entity, npc = self.current_town_npc(npc_id)
        await self.navigate((entity.x, entity.y), radius=2)
        self.record('received_current_npc_' + str(npc_id), entity.uid in self.bot.live_appearances,
                    npc_id=npc_id, uid=entity.uid, placement=npc.key)
        return entity

    async def town_trade(self, npc_id):
        npc = await self.approach(npc_id)
        opened = await self.window(npc.uid, 'buy', 0x4e48)
        rows = [hb.fields(raw) for raw in opened.get(3, ())]
        row = next((row for row in rows if hb.scalar(row, 2) == 14), None)
        if row is None:
            raise matrix.MissingFeature('M5 shop potion14 BUY row unavailable')
        price, before = hb.scalar(row, 4), self.saved_counts()
        await self.trade(hb.scalar(opened, 1), 5, hb.scalar(row, 1), 1)
        after = self.saved_counts()
        self.record('kent_shop_buy_saved', after[14] == before[14] + 1
            and after[7] == before[7] - price and after == Counter(
                {**before, 14: before[14] + 1, 7: before[7] - price}),
            price=price, before=dict(before), after=dict(after))
        uid, item = self.item(14)
        opened = await self.window(npc.uid, 'sell', 0x4ee7)
        rows = [hb.fields(raw) for raw in opened.get(3, ())]
        row = next((row for row in rows if hb.scalar(row, 1) == uid), None)
        if row is None:
            raise matrix.MissingFeature('M5 shop owned potion14 SELL row unavailable')
        price, before = hb.scalar(row, 2), after
        await self.trade(hb.scalar(opened, 1), 6, uid, 1)
        after = self.saved_counts()
        self.record('kent_shop_sell_saved', after[14] == before[14] - 1
            and after[7] == before[7] + price,
            uid=uid, price=price, before=dict(before), after=dict(after))

    async def town_warehouse(self, npc_id):
        npc = await self.approach(npc_id)
        uid, item = self.item(14)
        before, bank_before = self.saved_counts(), self.bank_counts()
        opened = await self.window(npc.uid, 'deposit', 0x4ed2)
        await self.trade(hb.scalar(opened, 4), 1, uid, 2)
        after, bank_after = self.saved_counts(), self.bank_counts()
        self.record('kent_warehouse_deposit_saved', after[14] == before[14] - 2
            and bank_after[14] == bank_before[14] + 2 and after[7] == before[7],
            uid=uid, player=dict(after), warehouse=dict(bank_after))
        await self.barrier(0x097b, label='M5_WAREHOUSE_CLOSE')
        opened = await self.window(npc.uid, 'retrieve', 0x0971)
        issued = [hb.fields(raw) for raw in opened.get(7, ())]
        row = next((row for row in issued if hb.scalar(hb.fields(hb.scalar(row, 2)), 2) == 14), None)
        if row is None:
            raise hb.BotFailure('M5_DEPOSITED_ITEM_NOT_IN_ISSUED_WITHDRAW_LIST')
        await self.trade(hb.scalar(opened, 1), 2, hb.scalar(row, 1), 2)
        after, bank_after = self.saved_counts(), self.bank_counts()
        fee = self.broker._world_services.withdrawal_fee
        self.record('kent_warehouse_withdraw_saved', after[14] == before[14]
            and bank_after == bank_before and after[7] == before[7] - fee,
            issued_reference=hb.scalar(row, 1), fee=fee,
            player=dict(after), warehouse=dict(bank_after))
        await self.barrier(0x097b, label='M5_WAREHOUSE_CLOSE_AFTER_WITHDRAW')

    async def kent_field(self, group_id):
        self.stage = 'kent_field_combat_drop'
        bot = self.bot
        group = next(group for group in bot.data.spawns if group.group_id == group_id)
        await self.navigate(((group.rect.x1 + group.rect.x2) // 2,
                             (group.rect.y1 + group.rect.y2) // 2), radius=3)
        appeared, killed, dropped, picked = set(), set(), {}, set()
        before_swings, before_moves = bot.swings, bot.moves
        deadline = time.monotonic() + self.args.hunt_timeout
        while time.monotonic() < deadline:
            if bot.dead:
                raise hb.BotFailure('M5_OWNER_DIED_DURING_FIELD_HUNT')
            if bot.hp < bot.max_hp * .6:
                await self.use(14)
            issued = {slot.uid for state in self.broker._world.spawner.groups
                      if state.spec.group_id == group_id for slot in state.slots if slot.uid is not None}
            appeared.update(issued.intersection(bot.actors))
            killed.update(appeared.intersection(bot.kills))
            for uid in bot.ground:
                entity = self.broker._world.entities.get(uid)
                item = None if entity is None else self.broker._world.ground.get(entity.ref)
                if item is not None and item.source_ref.uid in killed and item.owner_uid == bot.self_uid:
                    dropped[uid] = dict(source_uid=item.source_ref.uid,
                        source_generation=item.source_ref.generation, owner_uid=item.owner_uid,
                        template=item.item_id, count=item.count)
            loot = [(uid, row) for uid, row in bot.ground.items() if uid in dropped]
            living = [(uid, row) for uid, row in bot.actors.items() if uid in appeared and row['alive']]
            if loot:
                uid, row = min(loot, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, row['position']) <= 1:
                    before, count = self.saved_counts(), bot.pickups
                    await bot.pickup(uid)
                    if bot.pickups > count:
                        picked.add(uid)
                        item, after = dropped[uid], self.saved_counts()
                        expected = before.copy()
                        expected[item['template']] += item['count']
                        self.record('kent_field_drop_pickup_saved', after == expected,
                            ground_uid=uid, before=dict(before), after=dict(after), **item)
                else:
                    await bot.step(row['position'], radius=1)
            elif living:
                uid, row = min(living, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, row['position']) <= 1:
                    await self.owner_attack_current(uid)
                else:
                    await bot.step(row['position'], radius=1)
            else:
                await bot.step(((group.rect.x1 + group.rect.x2) // 2,
                                (group.rect.y1 + group.rect.y2) // 2), radius=1)
            if picked and killed and bot.swings > before_swings:
                self.record('kent_field_received_combat_drop', True,
                    group=group_id, appeared=sorted(appeared), killed=sorted(killed),
                    drops=dropped, picked=sorted(picked), swings=bot.swings - before_swings,
                    accepted_steps=bot.moves - before_moves)
                return
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.04)
        raise hb.BotFailure('M5_FIELD_KILL_DROP_PICKUP_DEADLINE')

    async def m5(self):
        # Public startup module owns these immutable scenario coordinates/IDs.
        from tools.local_original_session.world_feature_m5 import load_m5_policy
        policy = load_m5_policy()
        plan = policy.scenario
        self.stage = 'gludin_to_kent_teleport'
        npc = await self.approach(plan['gludin_teleporter_id'])
        before = self.saved_counts()
        opened = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
            check=lambda batch: hb.find(batch, 0x4e44), label='M5_TELEPORTER_CLICK')
        menu = hb.find(opened, 0x4e44).values
        self.record('current_steve2_local_backend_menu', hb.scalar(menu, 2) == b'steve2',
            stem=hb.scalar(menu, 2).decode('utf-8'), action=plan['kent_action'],
            scope='current extracted resource; direct *2 binding is LOCAL backend policy; native page transition unverified')
        context = hb.scalar(menu, 1)
        payload = hb.uint(1, context) + hb.pb.encode_bytes(2,
            plan['kent_action'].encode()) + hb.uint(4, 0) + hb.uint(5, 0)
        await self.barrier(0x4ed4, payload, label='M5_TELEPORT_KENT')
        destination = policy.return_for(4, *plan['kent_center'])
        position = self.position_snapshot()
        expected = (destination.map_id, destination.x, destination.y)
        trip = self.broker._world_services.teleports[(plan['gludin_teleporter_id'],
                                                     'teleport ' + plan['kent_action'])]
        self.record('gludin_kent_paid_teleport_saved', all(value == expected for value in position.values())
            and self.saved_counts()[7] == before[7] - trip.price,
            price=trip.price, **position)
        await self.one_move()
        self.stage = 'kent_buy_sell'
        await self.town_trade(plan['kent_shop_id'])
        self.stage = 'kent_warehouse'
        await self.town_warehouse(plan['kent_warehouse_id'])
        self.stage = 'kent_field_combat_drop'
        await self.gear()
        # A table's first group is not a suitable target policy: Kent also
        # contains werewolves9, shelobs14 and ogres28. Reuse the bot's level
        # ceiling and choose a current sourced group before sending movement.
        groups = [group for group in self.bot.data.spawns if group.group_id.startswith('m5_kent_')
            and self.bot.data.monsters[group.template_id].level <= (self.bot.level or 1) + 3]
        if not groups:
            raise matrix.MissingFeature('No M5 Kent group within normal bot level ceiling')
        group = min(groups, key=lambda g: hb.distance(self.bot.position,
            ((g.rect.x1 + g.rect.x2) // 2, (g.rect.y1 + g.rect.y2) // 2)))
        self.record('kent_field_normal_bot_target_policy', True, group=group.group_id,
            template=group.template_id, monster_level=self.bot.data.monsters[group.template_id].level,
            player_level=self.bot.level, table_first_group=plan['kent_field_group'])
        await self.kent_field(group.group_id)
        self.stage = 'kent_recall_scroll'
        departure, before = self.position_snapshot(), self.saved_counts()
        await self.use(162)
        position = self.position_snapshot()
        self.record('kent_recall_saved_local_return', all(value == expected for value in position.values())
            and departure != position and self.saved_counts()[162] == before[162] - 1,
            before=departure, after=position, destination=expected)
        self.stage = 'saved_kent_reconnect'
        bag, bank, character = self.saved_counts(), self.bank_counts(), self.bot.character
        self.record('normal_quit_before_kent_reconnect', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('M5_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        self.record('kent_saved_position_inventory_warehouse_restored',
            self.position_snapshot() == position and self.saved_counts() == bag and self.bank_counts() == bank,
            position=self.position_snapshot(), inventory=dict(self.saved_counts()), warehouse=dict(self.bank_counts()))
        self.record('m5_no_handler_errors', not any(self.error_codes().values()), errors=self.error_codes())


def parser():
    result = matrix.parser()
    result.description = __doc__
    result.set_defaults(scenario='m5')
    next(action for action in result._actions if action.dest == 'scenario').choices = ('m5',)
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='m5-bot-', dir=root))
    scene = M5Scenario(args, directory)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1, SL_EXPERIMENT_WAREHOUSE=1,
            SL_WORLD_TOWN_CANDIDATES='', SL_COMPANION=0, SL_SPELL_EXP=0,
            SL_COMPANION_PET_UI=0, SL_COMPANION_REVIVE_EXP=0):
        return await scene.run_matrix()


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(dict(status=result['status'], directory=result['directory'],
        failure=result['failure'], gaps=result['gaps'], checks=len(result['checks']),
        requests=result['requests'], cleanup_complete=result['cleanup_complete']),
        ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
