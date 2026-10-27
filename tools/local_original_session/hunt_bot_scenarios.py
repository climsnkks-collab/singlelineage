"""Socket-driven M1 scenarios on an owned, preserved loopback test profile.

    python -X utf8 -B -m tools.local_original_session.hunt_bot_scenarios --scenario all

Runtime opens the test broker endpoints, one broker at a time. SL_TEST_PORT_BASE
shifts their physical ports; the default remains 12000/14030.
Import/help do not import the broker or bind ports. Each scenario gets a fresh
fixture under work/local_original_session/runs; failures and saves are retained.
Reuses hunt_bot's FIRST/login/frame/movement/combat client, loopback's fixture
configuration, and the existing inventory/equipment stores. Only fixture creation
seeds test_knight equipment and one return162. No live HP, death, EXP, response,
clock or readiness is forced. All scenario actions go over the socket router.

SUCCESS is scoped to these local packets and observed sidecars/combat inputs.
It does not establish native input, rendering, equipment notifications, official
server formulas, or the original-client 30-minute milestone. Return162 checks
the run389 LOCAL in-place 4EE0 relocation; native camera/input remain unverified.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import dataclasses
import json
from pathlib import Path
import tempfile
import time
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import test_ports


class Unconfirmed(RuntimeError):
    """A required input or observation was unavailable; never a success."""


class IncompleteCleanup(RuntimeError):
    """A startup failure could not release its owned broker epoch."""


class ScenarioBot(hb.HuntBot):
    def __init__(self, args):
        super().__init__(args)
        self.hp_zero = self.own_death_frame = False
        self.hp_zero_ordinal = self.own_death_ordinal = None
        self.incoming_swings = self.hp_decreases = 0
        self.live_appearances = {}
        self.appearances_seen = set()

    def apply(self, frame):
        if frame.opcode == 0x4e3b:
            frame.values = hb.fields(frame.wire[4:-2])
        before = self.hp
        super().apply(frame)
        f = frame.values
        if frame.opcode == 0x4e38 and hb.scalar(f, 1) == self.self_uid:
            hp = hb.scalar(f, 10)
            self.hp_zero |= hp == 0
            if hp == 0 and self.hp_zero_ordinal is None:
                self.hp_zero_ordinal = frame.ordinal
            self.hp_decreases += before is not None and hp is not None and hp < before
        elif frame.opcode == 0x4e39 and hb.scalar(f, 1) == self.self_uid:
            if hb.scalar(f, 2) == 8:
                self.own_death_frame = True
                self.own_death_ordinal = frame.ordinal
        elif frame.opcode == 0x4e31 and hb.scalar(f, 3) == self.self_uid:
            self.incoming_swings += hb.scalar(f, 2) != self.self_uid
        elif frame.opcode == 0x4e96:
            uid = hb.scalar(f, 2)
            self.live_appearances[uid] = f
            self.appearances_seen.add(uid)
        elif frame.opcode == 0x4e40:
            self.live_appearances.pop(hb.scalar(f, 1), None)

    async def reselect(self):
        """The prior successful Restart ACK is required at the call site."""
        self.selected = self.dead = False
        self.self_uid = self.position = self.hp = self.max_hp = None
        self.actors.clear()
        self.ground.clear()
        self.live_appearances.clear()
        self.inventory.clear()
        self.inventory_received = False
        payload = hb.pb.encode_bytes(1, self.character.encode('utf-8')) + hb.uint(2, 0) + hb.uint(3, 0)

        def entered(batch):
            ack = hb.find(batch, 0x4e29, **{'2': 3})
            if ack is None:
                return None
            maps = hb.find([f for f in batch if f.ordinal > ack.ordinal], 0x4e95)
            status = None if maps is None else hb.find(
                [f for f in batch if f.ordinal > maps.ordinal], 0x4e38)
            return None if status is None else hb.find(
                [f for f in batch if f.ordinal > status.ordinal], 0x4e96,
                **{'2': hb.scalar(status.values, 1)})

        await self.peer.request(0x4e28, payload, check=entered)
        self.selected = True
        await self.alive()

    async def quit_selected(self):
        if self.selected and self.peer is not None and self.peer.error is None:
            await self.peer.request(0x4e3c, check=lambda batch: hb.find(batch, 0x4eef, **{'1': 45}))
            self.selected = False
            return True
        return False


async def build_epoch(directory, expected_uuid, *, seed):
    """Narrow loopback.build variant: startup Restart policy and restore-only epoch.

    The original build always creates/grants/positions, so calling it a second
    time would reset the reconnect fixture. This variant uses the same broker,
    fixture owner, normal guards, reserved sockets, kit frames and class inputs.
    """
    from tools.local_original_session import broker as b, equipment_store, inventory
    from tools.local_original_session import inventory_store, movement, restart
    from tools.local_original_session import world_combat, world_visibility
    from tools.local_original_session.hunt_bot_loopback import START, KNIGHT
    from tools.local_original_session.broker_tests import FixtureConversation, reserve
    from tools.local_original_session.game_data import load_m1
    from tools.local_original_session.world_m1_reward_tests import enable_world_kit

    async def owner(peer):
        return True

    sockets = reserve()
    try:
        broker = b.PersistentBroker(sockets=sockets, listener_ports=test_ports.listener_ports(), retained_owner=object(),
            owner_handle=object(), owner_job=object(), owner_guard=owner,
            owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=FixtureConversation, expected_uuid=expected_uuid,
            store_path=directory / 'characters.json', world_policy=world_visibility.POLICY,
            restart_policy=restart.POLICY)
    except BaseException:
        for sock in sockets.values():
            sock.close()
        raise
    try:
        data = load_m1()
        broker._world_starter_kit = 'test_knight'
        if seed:
            broker.realm.store.create(b.ack.realm.Creation(*KNIGHT))
            x, y = movement.authority.unpack_grid(broker.realm._actor_fields[1])
            broker.realm.positions.commit(movement.Position(1, KNIGHT[0], 0, x, y),
                movement.Position(1, KNIGHT[0], 0, *START))
            store, frame = enable_world_kit(broker, KNIGHT[1])
            rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
            # Explicit fresh-fixture supply only; no dropped UID or user save is used.
            scroll = dict(b.INVENTORY_STARTER_FIELDS)
            scroll.update({1: max(row[1] for row in rows) + 1, 2: 162, 4: 1, 7: 0})
            new_frame = inventory.build_kit_frame(rows if any(r[2] == 162 for r in rows) else rows + [scroll])
            store.replace_kit(1, frame, new_frame, append=True)
            broker._inventory_current_frame = new_frame
        else:
            store = inventory_store.InventoryStore(directory / 'characters.json',
                policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
            frame = store.restore(1)
            if frame is None:
                raise Unconfirmed('RECONNECT_SAVED_KIT_UNSUPPLIED')
            broker._inventory_store = store
            broker._inventory_kit_policy = inventory.KIT_POLICY
            broker._inventory_current_frame = frame
            broker.policy.inventory_add = broker.policy.item_kit = True
        equipment = equipment_store.EquipmentStore(store, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=data.items)
        if seed:
            items = {item.template_bits: item.identifier for item in
                     inventory.validate_kit_frame(broker._inventory_current_frame)}
            equipped = [data.items[entry.template_id] for entry in
                        data.starter.entries(KNIGHT[1], 'test_knight') if entry.equipped]
            weapon = next(item for item in equipped if item.kind == 'weapon')
            equipment.initialize_kit(1, broker._inventory_current_frame,
                initialization=equipment_store.FIRST_ENABLE_EMPTY, weapon_uid=items[weapon.template_id],
                slots=tuple((item.slot_key, items[item.template_id]) for item in equipped if item.kind == 'armor'))
        original_profile = broker._world_pc_profile

        def profile(writer, position, *, level=None):
            state, saved_frame = equipment.peek(position.uid)
            if state is None or saved_frame is None:
                raise Unconfirmed('SAVED_EQUIPMENT_UNSUPPLIED')
            by_uid = {item.identifier: data.items.get(item.template_bits) for item in
                      inventory.validate_kit_frame(saved_frame)}
            worn_weapon = by_uid.get(state.weapon_uid)
            armour = sum(by_uid[uid].ac for _, uid in state.slots)
            return dataclasses.replace(original_profile(writer, position, level=level),
                weapon=world_combat.FIST if worn_weapon is None else world_combat.weapon_from_item(worn_weapon),
                ac=world_combat.DEFAULT_PC_AC + armour)
        broker._world_pc_profile = profile
        original_after = broker._world_after_request

        async def after(writer, row, game, opcode, lock):
            if opcode == 0x4e28 and game.selection is not None:
                # This socket fixture has no native inventory-memory service.
                # Read the selected character's ordinary saved bag at the same
                # boundary as production _restore_inventory_selection.
                uid = broker.realm.service(writer).snapshot().uid
                selected_frame = store.restore(uid)
                if selected_frame is None:
                    raise Unconfirmed('SELECTED_SAVED_KIT_UNSUPPLIED')
                broker._inventory_current_frame = selected_frame
            await original_after(writer, row, game, opcode, lock)
            bound = broker._world_pcs.get(id(writer))
            if opcode == 0x4e28 and bound is not None and bound[0] is writer:
                await broker._world_send(writer, row, inventory.kit_wire_frames(broker._inventory_current_frame), lock)
        broker._world_after_request = after
        return broker, store, equipment
    except BaseException as failure:
        try:
            closed = await broker.close()
        except BaseException as cleanup_error:
            raise IncompleteCleanup(f'{failure}; close: {cleanup_error}') from cleanup_error
        if not closed.get('cleanup_complete'):
            raise IncompleteCleanup(f'{failure}; startup cleanup incomplete') from failure
        raise


class Scenario:
    def __init__(self, args, name, directory):
        self.args, self.name, self.directory = args, name, directory
        self.broker = self.store = self.equipment = self.bot = None
        self.bots, self.epochs, self.checks = [], [], []
        self.cleanup_ok = True

    def record(self, name, ok, **evidence):
        status = 'UNCONFIRMED' if ok is None else ('SUCCESS' if ok else 'FAILED')
        self.checks.append(dict(check=name, status=status, **evidence))

    async def open(self, *, seed, character=None):
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await build_epoch(self.directory, expected, seed=seed)
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected, '--minutes', str(self.args.minutes),
            '--timeout', str(self.args.timeout), '--potion-threshold', str(self.args.potion_threshold)])
        options.port = test_ports.port(options.port)
        options.character = character
        self.bot = ScenarioBot(options)
        self.bots.append(self.bot)
        from tools.local_original_session.game_data import load_m1
        self.bot.data = load_m1()
        self.bot.terrain = self.broker._world.terrain
        self.bot.started = time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'FIXTURE_KIT_DELIVERY')

    async def close(self):
        errors = []
        if self.bot is not None:
            try:
                if self.bot.selected:
                    ok = await self.bot.quit_selected()
                    if not ok:
                        errors.append('SELECTED_QUIT_ACK_UNOBSERVED')
            except Exception as error:
                errors.append(f'QUIT: {type(error).__name__}: {error}')
            finally:
                for peer in self.bot.peers:
                    await peer.close()
                self.bot = None
        if self.broker is not None:
            broker, self.broker = self.broker, None
            try:
                report = broker.report()
                closed = await broker.close()
                self.epochs.append(dict(failure_code=report.get('failure_code'),
                    close_code=closed.get('failure_code'),
                    cleanup_complete=closed.get('cleanup_complete'), world=report.get('world')))
                if report.get('failure_code') or not closed.get('cleanup_complete'):
                    errors.append('BROKER_FAILURE_OR_INCOMPLETE_CLEANUP')
            except Exception as error:
                errors.append(f'BROKER_CLOSE: {type(error).__name__}: {error}')
                self.epochs.append(dict(failure_code=f'CLOSE_{type(error).__name__}',
                                        cleanup_complete=False))
        if errors:
            self.record('cleanup', False, errors=errors)
            self.cleanup_ok = False
        return not errors

    async def navigate(self, goal, *, radius=0, predicate=None):
        bot, until = self.bot, time.monotonic() + self.args.navigation_timeout
        start, moves = bot.position, bot.moves
        while not (predicate() if predicate else hb.distance(bot.position, goal) <= radius):
            if bot.dead:
                raise hb.BotFailure('PLAYER_DIED_DURING_NAVIGATION')
            if time.monotonic() >= until:
                raise hb.BotFailure('NAVIGATION_DEADLINE')
            await bot.step(goal, radius)
            if time.monotonic() - bot.last_alive >= 1:
                await bot.alive()
            await asyncio.sleep(.05)
        await bot.alive()
        return dict(start=start, finish=bot.position, accepted_steps=bot.moves - moves)

    async def receive_damage(self, *, lethal):
        """Approach a received monster, swing once, then let actual AI attack."""
        bot, until = self.bot, time.monotonic() + self.args.death_timeout
        engaged = set()
        while True:
            if lethal and bot.hp_zero and bot.own_death_frame:
                return
            if not lethal and bot.hp_decreases and bot.hp is not None and 0 < bot.hp < bot.max_hp:
                return
            if bot.dead and not lethal:
                raise hb.BotFailure('PLAYER_DIED_BEFORE_POTION')
            if time.monotonic() >= until:
                raise Unconfirmed('NATURAL_DEATH_NOT_OBSERVED' if lethal else 'NATURAL_DAMAGE_NOT_OBSERVED')
            if not bot.dead:
                living = [(uid, row) for uid, row in bot.actors.items() if row['alive']]
                if living:
                    uid, actor = min(living, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                    if hb.distance(bot.position, actor['position']) > 1:
                        await bot.step(actor['position'], radius=1)
                    elif uid not in engaged:
                        before = bot.swings
                        await bot.attack(uid)
                        if bot.swings > before:
                            engaged.add(uid)
                else:
                    groups = [g for g in bot.data.spawns if g.map_id == bot.map_id]
                    if not groups:
                        raise Unconfirmed('HUNTING_SPAWN_INPUT_UNSUPPLIED')
                    g = min(groups, key=lambda g: hb.distance(bot.position, (g.rect.x1, g.rect.y2)))
                    await bot.step(((g.rect.x1 + g.rect.x2) // 2, (g.rect.y1 + g.rect.y2) // 2), radius=2)
            if time.monotonic() - bot.last_alive >= 1:
                await bot.alive()
            await asyncio.sleep(.05)

    async def town(self):
        from tools.local_original_session.world_visibility import in_screen
        bot, town = self.bot, self.bot.data.town
        movement = await self.navigate((town.respawn_x, town.respawn_y))
        self.record('town_position', bot.map_id == town.map_id and
                    bot.position == (town.respawn_x, town.respawn_y), **movement, map_id=bot.map_id)
        registered = self.broker._world.town
        if registered is None:
            raise Unconfirmed('TOWN_NPC_REGISTRY_UNSUPPLIED')
        expected = {e.uid for e in registered.present(bot.map_id, *bot.position, 17)
                    if registered.appearance(e.uid).sprite_id is not None
                    and in_screen(*bot.position, e.x, e.y)}
        received = expected.intersection(bot.live_appearances)
        self.record('town_npc_SC4E96', received == expected if expected else None,
            expected_visible_count=len(expected), received_visible_count=len(received),
            received_uids=sorted(received), missing_uids=sorted(expected - received),
            identity_basis='received wire UID matched read-only current TownNpcs registry; wire f39 is not inferred')

    async def death(self):
        bot = self.bot
        await self.receive_damage(lethal=True)
        self.record('natural_combat_death', bool(bot.incoming_swings and bot.hp_decreases and
            bot.hp_zero and bot.own_death_frame and bot.swings and
            bot.hp_zero_ordinal < bot.own_death_ordinal), incoming_swings=bot.incoming_swings,
            hp_decreases=bot.hp_decreases, hp_zero=bot.hp_zero, own_SC4E39=bot.own_death_frame,
            own_swings=bot.swings, hp_zero_ordinal=bot.hp_zero_ordinal,
            death_action8_ordinal=bot.own_death_ordinal)
        await bot.peer.request(0x4eec, check=lambda batch: hb.find(batch, 0x4e3b, **{'1': 1}))
        self.record('CS4EEC_SC4E3B', True, explicit_success=True)
        await bot.reselect()
        town = bot.data.town
        self.record('reselected_alive_in_town', not bot.dead and bot.hp > 0 and
            bot.map_id == town.map_id and bot.position == (town.respawn_x, town.respawn_y),
            hp=bot.hp, map_id=bot.map_id, position=bot.position)
        groups = [g for g in bot.data.spawns if g.map_id == bot.map_id]
        if not groups:
            raise Unconfirmed('RETURN_HUNTING_SPAWN_INPUT_UNSUPPLIED')
        goals = [(max(g.rect.x1, min(bot.position[0], g.rect.x2)),
                  max(g.rect.y1, min(bot.position[1], g.rect.y2))) for g in groups]
        goal = min(goals, key=lambda point: hb.distance(bot.position, point))
        evidence = await self.navigate(goal, predicate=lambda: any(g.rect.contains(*bot.position) for g in groups))
        self.record('returned_to_hunting_rectangle', not bot.dead, **evidence, map_id=bot.map_id)

    def snapshot(self):
        """Observations only; no handler, grant, save, restore mutation or RNG call."""
        bot = self.bot
        from tools.local_original_session import inventory
        saved_frame = self.store.restore(bot.self_uid)
        if saved_frame is None:
            raise Unconfirmed('SAVED_INVENTORY_UNSUPPLIED')
        equipment = self.equipment.restore(bot.self_uid, saved_frame)
        progress = self.broker._world_progress.get(bot.self_uid)
        state = self.broker._world.combat.pcs.get(bot.self_uid)
        return dict(character=bot.character, uid=bot.self_uid, level=bot.level,
            exp_percent=bot.exp_percent, exact_saved_exp=progress.exp, saved_level=progress.level,
            live_exact_exp=self.broker._world.exp.get(bot.self_uid),
            wire_inventory={str(uid): row for uid, row in sorted(bot.inventory.items())},
            saved_inventory={str(item.identifier): dict(item.raw_fields) for item in inventory.validate_kit_frame(saved_frame)},
            equipment=None if equipment is None else dataclasses.asdict(equipment),
            combat_equipment=None if state is None else dict(ac=state.profile.ac,
                weapon=dataclasses.asdict(state.profile.weapon)))

    async def reconnect(self):
        bot = self.bot
        await bot.hunt()
        bot.hunt_finished = time.monotonic()
        before = self.snapshot()
        self.record('hunt_N_minutes', not bot.dead and bot.stop_reason == 'minutes' and bool(bot.kills),
            requested_minutes=self.args.minutes, kills=len(bot.kills), own_swings=bot.swings,
            elapsed_seconds=round(bot.hunt_finished - bot.hunt_started, 3))
        quit_ack = await bot.quit_selected()
        self.record('normal_CS4E3C_close', quit_ack, observed_SC4EEF_reason=45 if quit_ack else None)
        character = bot.character
        if not await self.close():
            raise hb.BotFailure('FIRST_EPOCH_CLOSE_FAILED_NO_RECONNECT')
        await self.open(seed=False, character=character)
        after = self.snapshot()
        self.record('same_character_new_connection', before['character'] == after['character'] and before['uid'] == after['uid'],
            character=after['character'], uid=after['uid'],
            basis='fresh broker epoch, same preserved profile, normal FIRST then active socket; no replayed grant/START commit')
        self.record('level_and_exact_exp_preserved',
            before['level'] == before['saved_level'] == after['level'] == after['saved_level'] and
            before['exact_saved_exp'] == before['live_exact_exp'] == after['exact_saved_exp'] == after['live_exact_exp'] and
            before['exp_percent'] is not None and after['exp_percent'] is not None and
            before['exp_percent'] == after['exp_percent'],
            before={k: before[k] for k in ('level', 'saved_level', 'exact_saved_exp', 'live_exact_exp', 'exp_percent')},
            after={k: after[k] for k in ('level', 'saved_level', 'exact_saved_exp', 'live_exact_exp', 'exp_percent')},
            exact_exp_basis='existing ProgressStore and read-only world.exp; socket f26 reports percent only')
        self.record('inventory_preserved', before['wire_inventory'] == after['wire_inventory'] ==
            before['saved_inventory'] == after['saved_inventory'], rows=len(after['wire_inventory']),
            counts_before={uid: row.get(4) for uid, row in before['wire_inventory'].items()},
            counts_after={uid: row.get(4) for uid, row in after['wire_inventory'].items()})
        known = all(snapshot[key] is not None for snapshot in (before, after)
                    for key in ('equipment', 'combat_equipment'))
        self.record('equipment_store_and_combat_inputs_preserved',
            before['equipment'] == after['equipment'] and before['combat_equipment'] == after['combat_equipment'] if known else None,
            before=before['equipment'], after=after['equipment'], combat_before=before['combat_equipment'],
            combat_after=after['combat_equipment'],
            basis='initial fixture EquipmentStore.initialize_kit once; subsequent profiles consume saved row; native equip/097A unverified')

    async def items(self):
        bot = self.bot
        await self.receive_damage(lethal=False)
        hp_before = bot.hp
        potion_counts = {uid: item[4] for uid, item in bot.inventory.items()
                         if item.get(2, -1) & 0xffffffff == 14 and item.get(4, 0) > 0}
        if not potion_counts:
            raise Unconfirmed('RECEIVED_POTION14_UID_UNSUPPLIED')
        marker = bot.peer.ordinal
        await bot.potion()
        statuses = [f for f in bot.peer.frames if f.ordinal > marker and f.opcode == 0x4e38
                    and hb.scalar(f.values, 1) == bot.self_uid]
        # The first post-consumption own status is the one required by potion();
        # a later AI/regen status must not substitute for that effect observation.
        changed_at = None
        for frame in bot.peer.frames:
            if frame.ordinal <= marker:
                continue
            if frame.opcode == 0x0978 and hb.scalar(frame.values, 1) in potion_counts:
                changed_at = frame.ordinal
            elif frame.opcode == 0x0965:
                for raw in frame.values.get(1, ()):
                    child = hb.fields(raw)
                    uid = hb.scalar(child, 1)
                    if uid in potion_counts and hb.scalar(child, 4) == potion_counts[uid] - 1:
                        changed_at = frame.ordinal
        effect_status = next((f for f in statuses if changed_at is not None and f.ordinal > changed_at), None)
        hp_after = hb.scalar(effect_status.values, 10) if effect_status else None
        consumed = sum(potion_counts.values()) - sum(item.get(4, 0) for item in bot.inventory.values()
                       if item.get(2, -1) & 0xffffffff == 14)
        self.record('potion14_consumption_and_effect_status', consumed == 1 and effect_status is not None,
            consumed=consumed, hp_before=hp_before, hp_after=hp_after, incoming_swings=bot.incoming_swings,
            net_hp_change=None if hp_after is None else hp_after - hp_before,
            healing_observation='UNCONFIRMED' if hp_after is None else
                ('POSITIVE_HP_CHANGE' if hp_after > hp_before else 'NO_POSITIVE_HP_CHANGE'),
            basis='CS0960 actual UID/raw0; quantity 0965/0978 then first own SC4E38; full-HP clamp and intervening combat/regen can hide healing; net HP is not an exact healing formula')
        choices = [(uid, item) for uid, item in bot.inventory.items()
                   if item.get(2, -1) & 0xffffffff == 162 and item.get(4, 0) > 0]
        if not choices:
            raise Unconfirmed('RECEIVED_RETURN162_UID_UNSUPPLIED')
        uid, item = min(choices)
        quantity, departure = item[4], bot.position
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)

        def consumed_ack(batch):
            changed = None
            for frame in batch:
                if frame.opcode == 0x0978 and quantity == 1 and hb.scalar(frame.values, 1) == uid:
                    changed = frame
                elif frame.opcode == 0x0965:
                    for raw in frame.values.get(1, ()):
                        child = hb.fields(raw)
                        if hb.scalar(child, 1) == uid and hb.scalar(child, 4) == quantity - 1:
                            changed = frame
                if changed is not None and frame.ordinal > changed.ordinal and frame.opcode == 0x4ee0:
                    return frame
            return None
        await bot.peer.request(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, params), check=consumed_ack)
        self.record('return162_consumed_then_4EE0', True, uid=uid, quantity_before=quantity, quantity_after=quantity - 1)
        town = bot.data.town
        self.record('return162_in_place_town', departure != bot.position and
            bot.position == (town.respawn_x, town.respawn_y) and bot.map_id == town.map_id,
            departure=departure, destination=bot.position, map_id=bot.map_id,
            basis='run389 LOCAL 4E40/4EE0/4E96; no Restart/reselect; native camera/input unverified')
        from tools.local_original_session import inventory
        saved_frame = self.store.restore(bot.self_uid)
        wire_quantity = bot.inventory.get(uid, {}).get(4, 0)
        saved_quantity = None if saved_frame is None else next(
            (dict(i.raw_fields)[4] for i in inventory.validate_kit_frame(saved_frame) if i.identifier == uid), 0)
        self.record('return162_consumption_saved_at_arrival',
            wire_quantity == saved_quantity == quantity - 1 if saved_quantity is not None else None,
            quantity_before=quantity, received_quantity_after_reselect=wire_quantity,
            saved_quantity_after_reselect=saved_quantity)

    async def run(self):
        error = None
        try:
            await self.open(seed=True)
            await getattr(self, self.name)()
        except Unconfirmed as failure:
            error = f'{type(failure).__name__}: {failure}'
            self.record('required_observation', None, reason=error)
        except Exception as failure:
            error = f'{type(failure).__name__}: {failure}'
            self.record('scenario_execution', False, reason=error)
            if isinstance(failure, IncompleteCleanup):
                self.cleanup_ok = False
                self.epochs.append(dict(failure_code='STARTUP_CLEANUP_INCOMPLETE', cleanup_complete=False))
        finally:
            await self.close()
        statuses = {check['status'] for check in self.checks}
        status = 'FAILED' if 'FAILED' in statuses else ('UNCONFIRMED' if 'UNCONFIRMED' in statuses else 'SUCCESS')
        counts = Counter()
        for bot in self.bots:
            counts.update(bot.frame_counts)
        return dict(scenario=self.name, status=status, error=error, profile_path=str(self.directory),
            checks=self.checks, frame_counts=dict(sorted(counts.items())), epochs=self.epochs,
            cleanup_complete=self.cleanup_ok,
            final_observations=[dict(epoch=index, character=getattr(bot, 'character', None),
                hp=bot.hp, max_hp=bot.max_hp, map_id=bot.map_id, position=bot.position,
                dead=bot.dead, own_swings=bot.swings, incoming_swings=bot.incoming_swings,
                hp_decreases=bot.hp_decreases, hp_zero=bot.hp_zero,
                own_death_action8=bot.own_death_frame, kills=len(bot.kills), moves=bot.moves,
                level=bot.level, exp_percent=bot.exp_percent, inventory_received=bot.inventory_received,
                request_counts=dict(bot.request_counts), request_failures=dict(bot.request_failures))
                for index, bot in enumerate(self.bots, 1)])


def parser():
    result = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    result.add_argument('--scenario', choices=('death', 'reconnect', 'town', 'items', 'all'), default='all')
    result.add_argument('--minutes', type=hb.positive, default=3, help='reconnect pre-close hunt duration')
    result.add_argument('--timeout', type=hb.positive, default=15, help='socket/request timeout seconds')
    result.add_argument('--death-timeout', type=hb.positive, default=180, help='natural damage/death observation deadline seconds; no forced HP')
    result.add_argument('--navigation-timeout', type=hb.positive, default=180)
    result.add_argument('--potion-threshold', type=hb.positive, default=.5)
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work' / 'local_original_session' / 'runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-scenarios-', dir=root))
    names = ('death', 'reconnect', 'town', 'items') if args.scenario == 'all' else (args.scenario,)
    results = []
    for name in names:
        profile = directory / name
        profile.mkdir()
        result = await Scenario(args, name, profile).run()
        results.append(result)
        if not result['cleanup_complete']:
            break  # do not start another owner while the previous cleanup is incomplete
    return dict(scope='owned loopback fixture, real socket decoder/router, saved sidecar observations; no native screen/input milestone',
        fixture='fresh test_knight + EquipmentStore first-enable + one return162 (icon unspecified); no user save; all profiles retained',
        output_directory=str(directory), results=results,
        status='SUCCESS' if len(results) == len(names) and all(r['status'] == 'SUCCESS' for r in results) else
               ('FAILED' if any(r['status'] == 'FAILED' for r in results) else 'UNCONFIRMED'))


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.potion_threshold > 1:
        cli.error('--potion-threshold must be in (0, 1]')
    try:
        result = asyncio.run(run(args))
    except KeyboardInterrupt:
        result = dict(status='FAILED', error='INTERRUPTED', scope='loopback scenario interrupted; preserved profiles remain under runs')
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
