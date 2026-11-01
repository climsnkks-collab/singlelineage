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
import time
import uuid

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
        self.town_id = 'gludin'
        self.death_active = False

    async def open(self, *, seed, character=None, deliver=True):
        # Reuse the existing fresh pre-login level5 fixture. It establishes the
        # warehouse level requirement; no live HP/EXP/RNG or guard is replaced.
        self.seed_fixture = seed
        self.name = 'warehouse_roundtrip' if seed else 'm5'
        try:
            await super().open(seed=seed, character=character, deliver=deliver)
        finally:
            self.name = 'm5'
        # Aggro perception is not a collision wall. Keep the ordinary level
        # ceiling for targets, but navigate outside actual melee reach plus2;
        # monsters may naturally pursue/hit and ordinary healing stays active.
        def safe_field_cell(point):
            bot = self.bot
            ceiling = (bot.level or 1) + 3
            for actor in bot.actors.values():
                monster = bot.data.monsters[actor['template']]
                if not actor['alive'] or monster.level <= ceiling:
                    continue
                reach = monster.attack_range + 2
                if (hb.distance(point, actor['position']) <= reach
                        and hb.distance(point, actor['position'])
                        <= hb.distance(bot.position, actor['position'])):
                    return False
            return True
        self.bot.safe_hunt_cell = safe_field_cell
        if seed:
            self.fixture_notes.append(dict(navigation_policy=
                'M5 only: received overlevel actual attack range+2, outward retreat allowed; aggro perception is traversable; normal level+3 target ceiling; real damage/healing/death unchanged'))
            self.fixture_notes.append(dict(start=self.map_start,
                reason='explicit fresh Gludin starting snapshot; not a public map-entry claim',
                inventory='existing test_knight starter; no M5 item/UID/reward injection'))

    def instrument(self):
        super().instrument()
        if not self.seed_fixture:
            return
        # Fresh pre-login fixture only. Keep every original UID/count/item;
        # match currency display metadata to the actual pickup base prototype.
        from tools.local_original_session import equipment_store
        frame = self.broker._inventory_kit_frame(1)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        coin = next(row for row in rows if row[2] & 0xffffffff == 7)
        old_name = coin[18]
        coin[18] = self.broker.INVENTORY_STARTER_FIELDS[18]
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1, frame)
        by_template = {row[2]: row for row in rows}
        data = self.broker._world.data
        equipped = [entry.template_id for entry in data.starter.entries(1, 'test_knight') if entry.equipped]
        self.equipment.initialize_kit(1, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=next((by_template[t][1] for t in equipped if data.items[t].kind == 'weapon'), 0),
            slots=tuple((data.items[t].slot_key, by_template[t][1])
                for t in equipped if data.items[t].kind == 'armor'))
        self.fixture_notes.append(dict(pre_login_currency_display=dict(uid=coin[1], count=coin[4],
            original_name=old_name.decode('utf-8'), pickup_base_name=coin[18].decode('utf-8')),
            source='existing test_knight starter plus broker.INVENTORY_STARTER_FIELDS used by world_core_reward._world_pickup_commit',
            scope='fresh development save only; field18 display metadata only; unchanged UID/count/assets/item definitions; no post-login normalization or existing save mutation'))

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

    def return_candidates(self):
        # Snapshot the source GetBack pool without choosing a point or advancing
        # product RNG. Recall and death can return anywhere in this exact pool;
        # paid teleporter arrivals have their own separate fixed assertions.
        bot, world = self.bot, self.broker._world
        character_class = world.combat.pcs[bot.self_uid].profile.character_class
        return tuple(sorted({(point.map_id, point.x, point.y)
            for point in self.broker._world_m5.return_candidates(
                bot.map_id, *bot.position, character_class)}))

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
        self.record(self.town_id + '_shop_buy_saved', after[14] == before[14] + 1
            and after[7] == before[7] - price and after == Counter(
                {**before, 14: before[14] + 1, 7: before[7] - price}),
            price=price, before=dict(before), after=dict(after))
        opened = await self.window(npc.uid, 'sell', 0x4ee7)
        rows = [hb.fields(raw) for raw in opened.get(3, ())]
        # A named starter stack may not match the conservative plain-instance
        # resale policy. Use the actual eligible UID issued in this SELL list.
        row = next((row for row in rows
            if (item := self.bot.inventory.get(hb.scalar(row, 1))) is not None
            and item[2] & 0xffffffff == 14 and item[4] > 0), None)
        if row is None:
            raise matrix.MissingFeature('M5 shop owned potion14 SELL row unavailable')
        uid = hb.scalar(row, 1)
        price, before = hb.scalar(row, 2), after
        await self.trade(hb.scalar(opened, 1), 6, uid, 1)
        after = self.saved_counts()
        self.record(self.town_id + '_shop_sell_saved', after[14] == before[14] - 1
            and after[7] == before[7] + price,
            uid=uid, price=price, before=dict(before), after=dict(after))

    async def town_warehouse(self, npc_id):
        npc = await self.approach(npc_id)
        uid, item = self.item(14)
        before, bank_before = self.saved_counts(), self.bank_counts()
        opened = await self.window(npc.uid, 'deposit', 0x4ed2)
        await self.trade(hb.scalar(opened, 4), 1, uid, 2)
        after, bank_after = self.saved_counts(), self.bank_counts()
        self.record(self.town_id + '_warehouse_deposit_saved', after[14] == before[14] - 2
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
        self.record(self.town_id + '_warehouse_withdraw_saved', after[14] == before[14]
            and bank_after == bank_before and after[7] == before[7] - fee,
            issued_reference=hb.scalar(row, 1), fee=fee,
            player=dict(after), warehouse=dict(bank_after))
        await self.barrier(0x097b, label='M5_WAREHOUSE_CLOSE_AFTER_WITHDRAW')

    async def field_hunt(self, group_id):
        self.stage = self.town_id + '_field_combat_drop'
        bot = self.bot
        group = next(group for group in bot.data.spawns if group.group_id == group_id)
        groups = self.field_groups
        appeared, killed, dropped, picked = set(), set(), {}, set()
        before_swings, before_moves = bot.swings, bot.moves
        deadline = time.monotonic() + self.args.hunt_timeout
        while time.monotonic() < deadline:
            if bot.dead:
                raise hb.BotFailure('M5_OWNER_DIED_DURING_FIELD_HUNT')
            if bot.hp < bot.max_hp * .6:
                await self.use(14)
            issued = {slot.uid for state in self.broker._world.spawner.groups
                      if state.spec.group_id in {g.group_id for g in groups} for slot in state.slots if slot.uid is not None}
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
            living = [(uid, row) for uid, row in bot.actors.items() if uid in appeared and bot.hunt_target(row)
                and self.reachable_hunt_goal(row['position'], 1)]
            if loot:
                uid, row = min(loot, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, row['position']) <= 1:
                    before, count = self.saved_counts(), bot.pickups
                    coin_uids_before = {uid for uid, owned in bot.inventory.items() if owned[2] & 0xffffffff == 7}
                    await bot.pickup(uid)
                    if bot.pickups > count:
                        picked.add(uid)
                        item, after = dropped[uid], self.saved_counts()
                        expected = before.copy()
                        expected[item['template']] += item['count']
                        coin_uids_after = {uid for uid, owned in bot.inventory.items() if owned[2] & 0xffffffff == 7}
                        self.record(self.town_id + '_field_drop_pickup_saved', after == expected
                            and (item['template'] != 7 or coin_uids_before == coin_uids_after and len(coin_uids_after) == 1),
                            ground_uid=uid, before=dict(before), after=dict(after),
                            currency_uids_before=sorted(coin_uids_before), currency_uids_after=sorted(coin_uids_after), **item)
                else:
                    await bot.step(row['position'], radius=1)
            elif living:
                uid, row = min(living, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, row['position']) <= 1:
                    await self.owner_attack_current(uid)
                else:
                    await bot.step(row['position'], radius=1)
            else:
                goal = self.field_goal(groups, min_distance=3)
                if goal is None:
                    await bot.retreat_threat()
                else:
                    await bot.step(goal, radius=2)
            if picked and killed and bot.swings > before_swings:
                self.record(self.town_id + '_field_received_combat_drop', True,
                    group=group_id, eligible_groups=[g.group_id for g in groups], appeared=sorted(appeared), killed=sorted(killed),
                    drops=dropped, picked=sorted(picked), swings=bot.swings - before_swings,
                    accepted_steps=bot.moves - before_moves)
                return
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.04)
        self.navigation_observation = dict(town=self.town_id, position=bot.position,
            map_id=bot.map_id, player_level=bot.level, goal=self.field_goal(groups),
            appeared=sorted(appeared), killed=sorted(killed),
            received_actors=[dict(uid=uid, template=row['template'], position=row['position'],
                alive=row['alive'], level=bot.data.monsters[row['template']].level,
                safe=bot.safe_hunt_cell(row['position']), eligible=bot.hunt_target(row))
                for uid, row in sorted(bot.actors.items(),
                    key=lambda pair: hb.distance(bot.position, pair[1]['position']))[:40]],
            group_uids={state.spec.group_id: [slot.uid for slot in state.slots if slot.uid is not None]
                for state in self.broker._world.spawner.groups
                if state.spec.group_id in {g.group_id for g in groups}})
        raise hb.BotFailure('M5_FIELD_KILL_DROP_PICKUP_DEADLINE')

    def travel_heading(self, goal, radius, **kwargs):
        # Reuse Matrix's cached long terrain routing for mainland distances.
        previous, self.name = self.name, 'gludin_items'
        try:
            return super().travel_heading(goal, radius, **kwargs)
        finally:
            self.name = previous

    async def ensure_gear(self):
        state = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
        worn = set(self.equipped_slots(state).values())
        for template in (89, 104, 128, 129, 41, 3, 117):
            uid, _ = self.item(template)
            if uid not in worn:
                await self.gear_uid(uid)
                state = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
                worn = set(self.equipped_slots(state).values())

    async def owner_potion(self):
        if not self.death_active:
            return await super().owner_potion()

    async def teleport(self, npc_id, action, town_id):
        self.stage = town_id + '_teleport'
        npc = await self.approach(npc_id)
        before = self.saved_counts()
        opened = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
            check=lambda batch: hb.find(batch, 0x4e44), label='M5_TELEPORTER_CLICK')
        menu = hb.find(opened, 0x4e44).values
        first_stem = hb.scalar(menu, 2).decode('utf-8')
        page = await self.bot.peer.request(0x4ed4,
            hb.uint(1, hb.scalar(menu, 1)) + hb.pb.encode_bytes(2, b'teleportURL')
            + hb.uint(4, 0) + hb.uint(5, 0),
            check=lambda batch: hb.find(batch, 0x4e44), label='M5_TELEPORT_DESTINATIONS')
        menu = hb.find(page, 0x4e44).values
        self.record(town_id + '_teleporter_first_to_destinations',
            first_stem.endswith('1') and hb.scalar(menu, 2).decode('utf-8') == first_stem[:-1] + '2',
            first_stem=first_stem, destination_stem=hb.scalar(menu, 2).decode('utf-8'))
        trip = self.broker._world_services.teleports[(npc_id, 'teleport ' + action)]
        payload = hb.uint(1, hb.scalar(menu, 1)) + hb.pb.encode_bytes(2,
            action.encode()) + hb.uint(4, 0) + hb.uint(5, 0)
        await self.barrier(0x4ed4, payload, label='M5_TELEPORT_' + town_id.upper())
        self.town_id = town_id
        position = self.position_snapshot()
        expected = (trip.map_id, trip.x, trip.y)
        self.record(town_id + '_paid_teleport_saved',
            all(value == expected for value in position.values())
            and self.saved_counts()[7] == before[7] - trip.price,
            npc_id=npc_id, action=action, price=trip.price,
            menu_stem=hb.scalar(menu, 2).decode('utf-8'), **position,
            scope='current client menu actions; L1J destination/fee LOCAL backend policy; native input unknown')
        return expected

    async def field_damage_until_death(self):
        # Existing field receive_damage pattern, with the same safe approach
        # cells as this town's hunt. One owned swing then real AI hits only.
        # Passive zero-attack wildlife flees after a hit and cannot supply the
        # incoming damage this encounter needs; ordinary hunts may target it.
        bot = self.bot
        groups = tuple(group for group in self.field_groups
            if bot.data.monsters[group.template_id].attack_interval_ms > 0)
        deadline = time.monotonic() + self.args.death_timeout
        engaged = set()
        while not (bot.hp_zero and bot.own_death_frame):
            if time.monotonic() >= deadline:
                raise hb.BotFailure('M5_NATURAL_FIELD_DEATH_DEADLINE')
            if not bot.dead:
                targets = [(uid, row) for uid, row in bot.actors.items()
                    if bot.hunt_target(row)
                    and bot.data.monsters[row['template']].attack_interval_ms > 0]
                if targets:
                    uid, row = min(targets, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                    if hb.distance(bot.position, row['position']) > 1:
                        await bot.step(row['position'], radius=1)
                    elif uid not in engaged:
                        before = bot.swings
                        await self.owner_attack_current(uid)
                        if bot.swings > before:
                            engaged.add(uid)
                else:
                    goal = self.field_goal(groups, min_distance=3)
                    if goal is None:
                        await bot.retreat_threat()
                    else:
                        await bot.step(goal, radius=2)
            if time.monotonic() - bot.last_alive >= 1:
                await bot.alive()
            await asyncio.sleep(.05)

    async def death_restart(self):
        # Existing field pattern: normal attack once then actual NPC AI damage.
        # Unequip through owned socket item requests and choose not to heal.
        state = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
        for uid in self.equipped_slots(state).values():
            await self.gear_uid(uid)
        self.stage = self.town_id + '_natural_death'
        self.death_active = True
        try:
            await self.field_damage_until_death()
        finally:
            self.death_active = False
        self.record(self.town_id + '_natural_field_death',
            self.bot.hp_zero and self.bot.own_death_frame and self.bot.incoming_swings > 0,
            incoming_swings=self.bot.incoming_swings, hp_zero=self.bot.hp_zero,
            own_death_frame=self.bot.own_death_frame)
        expected = self.return_candidates()
        await self.bot.peer.request(0x4eec,
            check=lambda batch: hb.find(batch, 0x4e3b, **{'1': 1}), label='DEAD_RESTART')
        await self.bot.reselect()
        await self.restore_selected_delivery()
        position = self.position_snapshot()
        self.record(self.town_id + '_death_restart_reselect_saved_return',
            not self.bot.dead and self.bot.hp > 0
            and len(set(position.values())) == 1 and position['wire'] in expected, **position,
            candidates=expected, hp=self.bot.hp, level=self.bot.level)
        await self.use(14)
        await self.ensure_gear()

    def field_goal(self, groups, min_distance=0):
        # Current issued group positions guide navigation only. Combat still
        # requires a received actor and the ordinary socket attack admission.
        world, bot = self.broker._world, self.bot
        group_ids = {group.group_id for group in groups}
        current = {entity.uid: entity for state in world.spawner.groups
            if state.spec.group_id in group_ids for slot in state.slots
            if slot.uid is not None and (entity := world.entities.get(slot.uid)) is not None
            and entity.alive and entity.map_id == bot.map_id
            and bot.safe_hunt_cell((entity.x, entity.y))}
        previous = getattr(self, '_field_waypoint', None)
        if previous is not None and previous[0] == self.town_id and previous[1] in current:
            entity = current[previous[1]]
            point = entity.x, entity.y
            if self.reachable_hunt_goal(point, 1):
                return point
        for entity in sorted(current.values(),
                key=lambda entity: hb.distance(bot.position, (entity.x, entity.y))):
            point = entity.x, entity.y
            if self.reachable_hunt_goal(point, 1):
                self._field_waypoint = self.town_id, entity.uid
                return point
        # Before interest-spawn activation, keep one static reachable waypoint
        # until arrival or an observed threat makes it unsafe.
        previous = getattr(self, '_field_static_waypoint', None)
        if previous is not None and previous[0] == self.town_id:
            point = previous[1]
            if (hb.distance(bot.position, point) > 2 and bot.safe_hunt_cell(point)
                    and self.reachable_hunt_goal(point, 2)):
                return point
        for group in sorted(groups, key=lambda group: hb.distance(bot.position,
                ((group.rect.x1 + group.rect.x2)//2, (group.rect.y1 + group.rect.y2)//2))):
            center = ((group.rect.x1 + group.rect.x2)//2, (group.rect.y1 + group.rect.y2)//2)
            points = [(x, y) for y in range(group.rect.y1, group.rect.y2 + 1)
                for x in range(group.rect.x1, group.rect.x2 + 1)
                if world.terrain.can_stand(bot.map_id, x, y) is True
                and bot.safe_hunt_cell((x, y))
                and hb.distance(bot.position, (x, y)) >= min_distance]
            for point in sorted(points, key=lambda point: (hb.distance(point, center),
                    hb.distance(bot.position, point))):
                if self.reachable_hunt_goal(point, 2):
                    self._field_static_waypoint = self.town_id, point
                    return point
        return None

    async def visit(self, town_id, shop_id, bank_id):
        self.town_id = town_id
        self.stage = town_id + '_buy_sell'
        await self.town_trade(shop_id)
        self.stage = town_id + '_warehouse'
        await self.town_warehouse(bank_id)
        await self.ensure_gear()
        await self.use(17)  # owned haste potion; normal server cadence/effect
        await self.use(296)  # owned knight bravery; actual quantity consumption
        self.stage = town_id + '_field_combat_drop'
        prefix = 'm4_gludio_' if town_id == 'gludin' else 'm5_' + town_id + '_'
        prefixes = (prefix, 'population_' + prefix)
        groups = [g for g in self.bot.data.spawns if g.group_id.startswith(prefixes)
            and self.bot.data.monsters[g.template_id].level <= (self.bot.level or 1) + 3]
        groups.sort(key=lambda g: hb.distance(self.bot.position,
            ((g.rect.x1 + g.rect.x2)//2, (g.rect.y1 + g.rect.y2)//2)))
        group = next((g for g in groups if self.field_goal((g,)) is not None), None)
        if group is None:
            raise matrix.MissingFeature('No reachable normal-level field group for ' + town_id)
        self.record(town_id + '_field_normal_bot_target_policy', True,
            group=group.group_id, template=group.template_id,
            monster_level=self.bot.data.monsters[group.template_id].level,
            player_level=self.bot.level)
        self.field_groups = groups
        await self.field_hunt(group.group_id)
        self.stage = town_id + '_recall_scroll'
        # A pickup can deliver incoming damage in the same batch. Move beyond
        # current attack reach before the ordinary item-use input interval.
        retreat_deadline = time.monotonic() + self.args.timeout
        while not self.bot.safe_hunt_cell(self.bot.position):
            if self.bot.dead:
                raise hb.BotFailure('M5_OWNER_DIED_BEFORE_RECALL')
            if time.monotonic() >= retreat_deadline:
                raise hb.BotFailure('M5_RECALL_RETREAT_DEADLINE')
            await self.bot.retreat_threat()
            await asyncio.sleep(.03)
        if self.bot.dead:
            raise hb.BotFailure('M5_OWNER_DIED_BEFORE_RECALL')
        if self.bot.hp < self.bot.max_hp * .75:
            await self.use(14)
        departure, before = self.position_snapshot(), self.saved_counts()
        expected = self.return_candidates()
        await self.use(162)
        position = self.position_snapshot()
        self.record(town_id + '_recall_saved_local_return',
            len(set(position.values())) == 1 and position['wire'] in expected
            and departure != position and self.saved_counts()[162] == before[162] - 1,
            before=departure, after=position, candidates=expected)
        # Re-enter the same real field using received actors and safe cells.
        await self.death_restart()
        self.record(town_id + '_visit_complete', True)

    async def m5(self):
        self.fixture_notes.append(dict(
            mainland_route='gludin-kent-gludin-woods-gludin-kent-giran-oren-giran-heine',
            source='existing data/m4 and data/m5 client/L1J/local_policy records',
            scope='fresh existing warehouse_roundtrip Lv5 Gludin saved-position fixture; test_knight native-layout LOCAL memory adapter; no original process, native screen/input or public map entry claim'))
        route = (
            (50024, 'gludin-kent', 'kent', 70018, 60003),
            (50020, 'kent-gludin', 'gludin', 70021, 60007),
            (50024, 'gludin-woods', 'windawood', 70072, 60023),
            (50054, 'woods-gludin', 'gludin', None, None),
            (50024, 'gludin-kent', 'kent', None, None),
            (50020, 'kent-giran', 'giran', 70028, 60008),
            (50036, 'giran-oren', 'oren', 70063, 60021),
            (50051, 'oren-giran', 'giran', None, None),
            (50036, 'giran-heine', 'heine', 70082, 60030),
        )
        for npc_id, action, town_id, shop_id, bank_id in route:
            await self.teleport(npc_id, action, town_id)
            if shop_id is not None and town_id in self.args.towns.split(','):
                await self.visit(town_id, shop_id, bank_id)
        position, bag, bank = self.position_snapshot(), self.saved_counts(), self.bank_counts()
        character = self.bot.character
        self.record('normal_quit_before_mainland_reconnect', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('M5_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        self.record('mainland_saved_position_inventory_warehouse_restored',
            self.position_snapshot() == position and self.saved_counts() == bag and self.bank_counts() == bank,
            position=self.position_snapshot(), inventory=dict(self.saved_counts()), warehouse=dict(self.bank_counts()))
        self.record('m5_no_handler_errors', not any(self.error_codes().values()), errors=self.error_codes())


def parser():
    result = matrix.parser()
    result.description = __doc__
    result.set_defaults(scenario='m5')
    result.add_argument('--towns', default='kent,gludin,windawood,giran,oren,heine',
        help='bounded visit subset; route still uses normal issued teleports; default all six')
    result.add_argument('--output-root', type=Path, default=None,
        help='Parent for preserved run evidence; use workspace _work if runs ACL prevents reading.')
    next(action for action in result._actions if action.dest == 'scenario').choices = ('m5',)
    return result


async def run(args):
    root = args.output_root or Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = root / ('m5-bot-' + uuid.uuid4().hex)
    directory.mkdir()
    scene = M5Scenario(args, directory)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1, SL_EXPERIMENT_WAREHOUSE=1,
            SL_WORLD_TOWN_CANDIDATES='', SL_COMPANION=0, SL_SPELL_EXP=0,
            SL_COMPANION_PET_UI=0, SL_COMPANION_REVIVE_EXP=0):
        result = await scene.run_matrix()
    milestones = ('paid_teleport_saved', 'shop_buy_saved', 'shop_sell_saved',
        'warehouse_deposit_saved', 'warehouse_withdraw_saved',
        'field_received_combat_drop', 'recall_saved_local_return',
        'natural_field_death', 'death_restart_reselect_saved_return', 'visit_complete')
    result['town_results'] = {town: {step: next((row['status'] for row in reversed(result['checks'])
        if row['check'] == town + '_' + step), 'UNRUN') for step in milestones}
        for town in ('kent', 'gludin', 'windawood', 'giran', 'oren', 'heine')}
    result['requested_towns'] = args.towns.split(',')
    result['source_evidence_scope'] = dict(
        source_sha256='inherited Matrix startup fingerprints cover imported core/feature modules; hunt_bot_m5 and data files are outside that existing map',
        data_sources='data/m4 and data/m5: retained client menu/region/S32 rows, attributed L1J placements/routes/prices and explicit LOCAL backend policy',
        return_policy='recall/death use the source GetBack candidate pool for departure position/class; all four position projections must agree; paid teleport arrivals checked separately',
        native='original client process, screen, clicks and public initial map-entry not tested')
    (directory / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(dict(status=result['status'], directory=result['directory'],
        failure=result['failure'], gaps=result['gaps'], checks=len(result['checks']),
        requests=result['requests'], cleanup_complete=result['cleanup_complete']),
        ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
