"""Owned inn rental/recovery/reconnect socket scenario; no original client.

Reuses FIRST/login/selection/world and finally/close from hunt_bot_scenarios.
Only the fresh pre-login test_knight save receives HP1/max200 and MP1/max200
through existing ProgressStore APIs. Its ordinary 1000A kit is unchanged; the
server must issue the key UID, debit cash, recover, persist and remove the key.
Packet success does not establish native UI or official room-map behavior.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import traceback
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session.hunt_bot_consumables import ConsumableBot
from tools.local_original_session.hunt_bot_play_matrix import environment, safe
from tools.local_original_session import test_ports


class InnScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'inn', directory)
        self.fixture = None
        self.handler_epochs, self.actions = [], []
        self.stage = 'startup'

    def record(self, name, ok, **evidence):
        super().record(name, ok, stage=self.stage, **safe(evidence))
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    def saved_bag(self):
        frame = self.store.restore(self.bot.self_uid)
        if frame is None:
            raise hs.Unconfirmed('INN_SAVED_INVENTORY_REQUIRED')
        # Compare as the server displays them (0964 stack-name projection).
        return hb.displayed_rows(frame)

    @staticmethod
    def cash(bag):
        return sum(row[4] for row in bag.values() if row[2] & 0xffffffff == 7)

    @property
    def state(self):
        return self.broker._world.combat.pcs[self.bot.self_uid]

    def inn_npc(self):
        town = self.broker._world.town
        candidates = [(town.entities.resolve(ref), npc)
            for ref, npc, _ in town._owned.values()
            if npc.npc_id == self.args.npc_id and npc.spawn['mapid'] == 0]
        candidates = [(entity, npc) for entity, npc in candidates if entity is not None]
        if not candidates:
            raise hs.Unconfirmed('INN_CURRENT_REGISTERED_NPC_REQUIRED')
        return min(candidates, key=lambda pair: pair[0].uid)

    async def open(self, *, seed, character=None):
        try:
            await self._open(seed=seed, character=character)
        except BaseException:
            (self.directory / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise

    async def _open(self, *, seed, character=None):
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(
            self.directory, expected, seed=seed)
        # hs connects its saved-kit owner after constructing the broker. Reuse
        # the product's startup setup once that real fixture owner is present.
        # This configures the ordinary store/regen adapter before FIRST; it
        # creates no key, rental, response, or active-player success state.
        if getattr(self.broker, '_world_inn_store', None) is None:
            from tools.local_original_session.world_bridge import Context
            from tools.local_original_session.world_feature_town import setup_inn
            setup_inn(Context(self.broker))
        if seed:
            from tools.local_original_session import inventory, movement
            from tools.local_original_session.hunt_bot_loopback import KNIGHT, START
            from tools.local_original_session.world_progress import Progress
            npc, _ = self.inn_npc()
            occupied = {(entity.x, entity.y) for entity in self.broker._world.entities
                        if entity.map_id == npc.map_id}
            candidates = [(npc.x + dx, npc.y + dy) for dx, dy in hb.DELTAS]
            point = next((point for point in candidates if point not in occupied
                and self.broker._world.terrain.can_stand(npc.map_id, *point) is True), None)
            if point is None:
                raise hs.Unconfirmed('INN_PASSABLE_FRESH_START_REQUIRED')
            old = self.broker.realm.positions.restore(movement.Position(1, KNIGHT[0], 0, *START))
            self.broker.realm.positions.commit(old, movement.Position(1, KNIGHT[0], npc.map_id, *point))
            self.broker._world_progress.commit(1, Progress(0, 1, 200, 200))
            self.broker._world_progress.save_vitals(1, (1, 1))
            frame = self.store.restore(1)
            rows = {item.identifier: dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)}
            self.fixture = dict(character=KNIGHT[0], uid=1, kit='test_knight',
                initial_hp=1, max_hp=200, initial_mp=1, max_mp=200,
                position=[npc.map_id, *point], cash=self.cash(rows),
                inventory_sha256=hashlib.sha256(frame).hexdigest(),
                source='existing hs.build_epoch fresh test_knight, ProgressStore.commit/save_vitals, PositionStore.commit before FIRST',
                funding='unchanged ordinary test_knight1000A; no cash/key/rental grant',
                scope='fresh owned saved-map fixture; initial world travel excluded')
            (self.directory / 'starting-fixture.json').write_text(json.dumps(
                self.fixture, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected,
            '--minutes', str(self.args.minutes), '--timeout', str(self.args.timeout)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = ConsumableBot(options)
        original_apply = self.bot.apply
        def apply(frame):
            if frame.opcode == 0x4e44:
                frame.values = hb.fields(frame.wire[4:-2])
            original_apply(frame)
        self.bot.apply = apply
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = self.broker._world.data, time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'INN_KIT_DELIVERY')
        self.record('FIRST_login_selection_world_' + str(len(self.bots)),
            self.bot.selected and self.bot.inventory_received and self.bot.hp > 0,
            uid=self.bot.self_uid, map_id=self.bot.map_id, position=self.bot.position,
            hp=self.bot.hp, max_hp=self.bot.max_hp, mp=self.bot.mp, max_mp=self.bot.max_mp)

    async def close(self):
        if self.broker is not None:
            self.handler_epochs.append(dict(
                errors=list(getattr(self.broker, '_world_handler_errors', ())),
                hook_errors=list(getattr(self.broker, '_world_hook_errors', ())),
                report=self.broker.report().get('world')))
        return await super().close()

    async def click(self):
        npc, placement = self.inn_npc()
        self.record('current_inn_npc_in_service_range', self.bot.map_id == npc.map_id
            and hb.distance(self.bot.position, (npc.x, npc.y)) <= 3,
            npc_id=placement.npc_id, live_uid=npc.uid,
            appearance_received=npc.uid in self.bot.live_appearances,
            scope='current server-issued registered NPC; client appearance separately observed')
        batch = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
            check=lambda frames: hb.find(frames, 0x4e44), label='INN_CLICK')
        menu = hb.find(batch, 0x4e44).values
        self.record('received_current_inn_menu', hb.scalar(menu, 2) == b'inn',
            npc_uid=npc.uid, context=hb.scalar(menu, 1), stem=hb.scalar(menu, 2))
        return menu

    async def action(self, action):
        menu = await self.click()
        payload = (hb.uint(1, hb.scalar(menu, 1))
            + hb.pb.encode_bytes(2, action.encode('utf-8')) + hb.uint(4, 0) + hb.uint(5, 0))
        batch = await self.bot.peer.request(0x4ed4, payload, alive=True,
            check=lambda frames: hb.find(frames, 0x4f57), label='INN_' + action.upper())
        self.actions.append(dict(action=action, context=hb.scalar(menu, 1),
            responses=[dict(ordinal=frame.ordinal, opcode=f'{frame.opcode:04X}') for frame in batch]))
        return batch

    async def inn(self):
        try:
            await self.rental_flow()
        except BaseException:
            (self.directory / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise

    def rental(self):
        store = getattr(self.broker, '_world_inn_store', None)
        if store is None:
            raise hs.Unconfirmed('INN_PRODUCT_RENTAL_STORE_REQUIRED')
        value = store.rows.get(self.bot.self_uid)
        return None if value is None else dict(value, placement=list(value['placement']))

    def saved_rental(self):
        path = self.directory / 'inn.json'
        if not path.exists():
            return None
        return next((value for value in json.loads(path.read_text(encoding='utf-8'))['rentals']
                     if value['uid'] == self.bot.self_uid), None)

    async def rental_flow(self):
        definition = getattr(self.broker, '_world_inn_definitions', {}).get(self.args.npc_id)
        if definition is None:
            raise hs.Unconfirmed('INN_PRODUCT_DEFINITION_REQUIRED')
        kind = self.args.rental_kind
        template = definition.room_key if kind == 'room' else definition.hall_key
        name = definition.room_name if kind == 'room' else definition.hall_name
        self.stage = 'normal_room_rental'
        before = self.saved_bag()
        self.record('fresh_start_has_no_key_or_rental', self.rental() is None
            and self.bot.hp == 1 and self.bot.max_hp == 200
            and self.bot.mp == 1 and self.bot.max_mp == 200
            and not any(row[2] & 0xffffffff == template for row in before.values())
            and before == self.bot.inventory, fixture=self.fixture)
        rented_from = time.time()
        await self.action(kind)
        rented_to = time.time()
        after, rental = self.saved_bag(), self.rental()
        issued = [(uid, row) for uid, row in self.bot.inventory.items()
                  if uid not in before and row.get(2, -1) & 0xffffffff == template]
        self.record('server_issued_named_key_and_exact_rental_fee', len(issued) == 1
            and issued[0][1][4] == 1 and issued[0][1][18] == name.encode('utf-8')
            and self.cash(after) == self.cash(before) - definition.price
            and after == self.bot.inventory and rental is not None,
            cash_before=self.cash(before), cash_after=self.cash(after), price=definition.price,
            key_template=template, key_name=name,
            issued_uid=issued[0][0] if issued else None, rental=rental,
            key_source='new UID actually received in server SC0964 after current menu action; never injected')
        key_uid = issued[0][0]
        self.record('absolute_expiry_and_key_ownership_persisted', self.saved_rental() == rental
            and rental['key_uid'] == key_uid and rental['key_template'] == template
            and rental['kind'] == kind and rental['npc_id'] == self.args.npc_id
            and int(rented_from) + definition.duration_s <= rental['expires_at']
                <= int(rented_to) + definition.duration_s,
            rental=rental, duration_seconds=definition.duration_s,
            expiry_execution='not awaited: this run verifies stored deadline and timely return')

        self.stage = 'inn_threshold_recovery'
        regen, profile = self.broker._world.combat.regen, self.state.profile
        expected_hp = regen.hp_amount(profile.con) + definition.hp_bonus
        expected_mp = regen.mp_amount(profile.wis) + definition.mp_bonus
        marker, hp_before, mp_before = self.bot.peer.ordinal, self.bot.hp, self.bot.mp
        deadline = time.monotonic() + self.args.recovery_timeout
        while self.bot.hp <= hp_before or self.bot.mp <= mp_before:
            if time.monotonic() >= deadline:
                raise hb.BotFailure('INN_POSITIVE_HP_MP_RECOVERY_DEADLINE')
            await self.bot.alive()
            await asyncio.sleep(.25)
        statuses = [frame for frame in self.bot.peer.frames if frame.ordinal > marker
                    and frame.opcode == 0x4e38 and hb.scalar(frame.values, 1) == self.bot.self_uid]
        hp, mp = hp_before, mp_before
        hp_deltas, mp_deltas = [], []
        for frame in statuses:
            next_hp, next_mp = hb.scalar(frame.values, 10, hp), hb.scalar(frame.values, 12, mp)
            if next_hp > hp:
                hp_deltas.append(next_hp - hp)
            if next_mp > mp:
                mp_deltas.append(next_mp - mp)
            hp, mp = next_hp, next_mp
        self.record('positive_wire_recovery_includes_inn_bonus_at_natural_threshold',
            bool(hp_deltas and mp_deltas) and all(value == expected_hp for value in hp_deltas)
            and all(value == expected_mp for value in mp_deltas)
            and self.bot.hp == self.state.hp and self.bot.mp == self.state.mp,
            hp_before=hp_before, hp_after=self.bot.hp, mp_before=mp_before, mp_after=self.bot.mp,
            hp_deltas=hp_deltas, mp_deltas=mp_deltas, expected_hp_per_threshold=expected_hp,
            expected_mp_per_threshold=expected_mp, hp_bonus=definition.hp_bonus,
            mp_bonus=definition.mp_bonus, hp_threshold=regen.hp_threshold(profile.level),
            mp_threshold=regen.mp_threshold, tick_ms=regen.tick_ms,
            rule='existing natural regeneration thresholds plus inn bonus; no live HP/RNG/clock mutation')

        self.stage = 'normal_logout_reconnect'
        character = self.bot.character
        position = (self.bot.map_id, *self.bot.position)
        self.record('normal_quit_before_reconnect', await self.bot.quit_selected())
        vitals = self.broker._world_progress.vitals(self.bot.self_uid)
        after = self.saved_bag()
        self.record('logout_saved_positive_recovered_vitals', vitals is not None
            and vitals[0] > 1 and vitals[1] > 1,
            saved_hp_mp=vitals, rental=self.saved_rental())
        if not await self.close():
            raise hb.BotFailure('INN_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        first_status = next(frame for frame in self.bot.peer.frames
            if frame.opcode == 0x4e38 and hb.scalar(frame.values, 1) == self.bot.self_uid)
        restored = (hb.scalar(first_status.values, 10), hb.scalar(first_status.values, 12))
        self.record('fresh_FIRST_restores_key_rental_cash_position_and_vitals',
            self.saved_bag() == after == self.bot.inventory
            and self.rental() == rental == self.saved_rental()
            and restored == tuple(vitals) and (self.bot.map_id, *self.bot.position) == position,
            key_uid=key_uid, key_template=template, key_name=name,
            saved_hp_mp=vitals, received_initial_hp_mp=restored, position=position,
            cash=self.cash(self.saved_bag()),
            scope='same retained owned save; reconnect uses seed=False without grant/rental/vitals/position mutation')

        self.stage = 'timely_key_return'
        cash_before = self.cash(self.saved_bag())
        await self.action('return')
        final = self.saved_bag()
        expected_cash = cash_before + definition.refund
        self.record('timely_return_removes_actual_key_and_persists_refund',
            key_uid not in self.bot.inventory and key_uid not in final
            and self.cash(final) == expected_cash and final == self.bot.inventory
            and self.rental() is None and self.saved_rental() is None,
            returned_uid=key_uid, cash_before=cash_before, cash_after=self.cash(final),
            refund=definition.refund, actual_expiry_waited=False)
        self.record('no_handler_errors_in_either_epoch',
            not self.broker._world_handler_errors
            and not getattr(self.broker, '_world_hook_errors', ())
            and not any(epoch['errors'] or epoch['hook_errors'] for epoch in self.handler_epochs),
            epochs=[epoch['errors'] for epoch in self.handler_epochs],
            current=self.broker._world_handler_errors)


def parser():
    result = hs.parser()
    result.description = __doc__
    result.set_defaults(scenario='inn')
    next(action for action in result._actions if action.dest == 'scenario').choices = ('inn',)
    result.add_argument('--npc-id', type=int, default=70012)
    result.add_argument('--recovery-timeout', type=hb.positive, default=180)
    result.add_argument('--rental-kind', choices=('room', 'hall'), default='room')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-inn-', dir=root))
    scene = InnScenario(args, directory)
    source_paths = ('hunt_bot_inn.py', 'hunt_bot.py', 'hunt_bot_scenarios.py',
        'hunt_bot_loopback.py', 'hunt_bot_consumables.py', 'broker.py',
        'world_handlers.py', 'world_bridge.py', 'world_core_session.py', 'world_core_kit.py',
        'world_core_stats.py', 'world_runtime.py', 'world_town.py', 'world_town_services.py',
        'world_feature_town.py', 'world_inn.py', 'world_progress.py', 'world_persist.py',
        'inventory.py', 'inventory_store.py', 'equipment_store.py', 'test_ports.py',
        'world_combat.py', 'game_data.py', 'data/m1/starter.json',
        'data/m1/town.json', 'data/m2/town_services.json', 'data/m2/npc_menus.json',
        'data/m2/town_npcs.json', 'data/m4/town_services.json',
        'data/m4/town_npcs.json', 'data/m5/town_services.json')
    def sources():
        return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in source_paths if (Path(__file__).parent / name).exists()}
    started = sources()
    with environment(SL_EXPERIMENT_MAP=2, SL_WORLD_TOWN_CANDIDATES='',
            SL_COMPANION=0, SL_COMPANION_PET_UI=0):
        result = await scene.run()
    result.update(directory=str(directory), fixture=scene.fixture, actions=scene.actions,
        handler_epochs=scene.handler_epochs, source_sha256_start=started, source_sha256=sources(),
        time_scale=os.environ.get('SL_TEST_TIME_SCALE', '1'),
        port_base=os.environ.get('SL_TEST_PORT_BASE', '12000'),
        scope='fresh owned profile; normal FIRST/login/selection/world and actual socket decoder/router; native UI and original-client milestone unverified')
    result['source_changes_during_run'] = [name for name in source_paths
        if started.get(name) != result['source_sha256'].get(name)]
    (directory / 'summary.json').write_text(json.dumps(safe(result), ensure_ascii=False,
        indent=2) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(dict(status=result['status'], directory=result['directory'],
        error=result['error'], checks=len(result['checks']),
        cleanup_complete=result['cleanup_complete']), ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
