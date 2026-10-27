"""Socket-only talking-scroll scenario on a preserved fresh test_knight profile.

Reuses hunt_bot's FIRST/login/selection client and hunt_bot_scenarios' owned
loopback fixture and cleanup. No original game client, user save, native input
or screen is opened. Every post-login action goes through the socket router.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import time
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import test_ports


class TalkScrollScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'talkscroll', directory)
        self.fixture = None
        self.trips = []
        self.handler_epochs = []

    def record(self, name, ok, **evidence):
        super().record(name, ok, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    async def open(self, *, seed, character=None):
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(
            self.directory, expected, seed=seed)
        if seed:
            from tools.local_original_session import inventory
            frame = self.store.restore(1)
            self.fixture = dict(
                character='SoloKnight', uid=1, kit='test_knight',
                inventory_sha256=hashlib.sha256(frame).hexdigest(),
                inventory=[dict(uid=item.identifier, template=item.template_bits,
                    quantity=dict(item.raw_fields)[4]) for item in inventory.validate_kit_frame(frame)],
                initialization='existing fresh loopback test_knight kit + saved equipment first-enable; '
                    'no talking-scroll UID or quantity injected by this scenario')
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected,
            '--minutes', str(self.args.minutes), '--timeout', str(self.args.timeout)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = hs.ScenarioBot(options)
        self.bots.append(self.bot)
        from tools.local_original_session.game_data import load_m1
        self.bot.data, self.bot.started = load_m1(), time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'FIXTURE_KIT_DELIVERY')
        self.record('FIRST_login_selected_world_' + str(len(self.bots)),
            self.bot.selected and self.bot.inventory_received and self.bot.hp > 0,
            character=self.bot.character, uid=self.bot.self_uid,
            map_id=self.bot.map_id, position=self.bot.position)

    async def close(self):
        if self.broker is not None:
            self.handler_epochs.append(dict(
                errors=list(getattr(self.broker, '_world_handler_errors', ())),
                map_transitions=getattr(self.broker, '_world_map_transitions', None)))
        return await super().close()

    def saved_bag(self):
        from tools.local_original_session import inventory
        frame = self.store.restore(self.bot.self_uid)
        if frame is None:
            raise hs.Unconfirmed('SAVED_INVENTORY_UNSUPPLIED')
        return {item.identifier: dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)}

    def position_observation(self):
        bot, broker = self.bot, self.broker
        entity = broker._world.entities.get(bot.self_uid)
        position = next((broker.realm.service(row['writer']).snapshot()
            for rows in broker._claims.values() for row in rows
            if broker._world_pcs.get(id(row['writer']), (None, None))[1] == bot.self_uid), None)
        if position is None or entity is None:
            raise hs.Unconfirmed('CURRENT_POSITION_UNSUPPLIED')
        saved = broker.realm.positions.restore(position)
        return dict(wire=(bot.map_id, *bot.position),
            current=(position.map_id, position.word0, position.word1),
            entity=(entity.map_id, entity.x, entity.y),
            saved=(saved.map_id, saved.word0, saved.word1))

    def received_scroll(self):
        choices = [(uid, fields) for uid, fields in self.bot.inventory.items()
            if fields.get(2, -1) & 0xffffffff == 12273 and fields.get(4, 0) > 0]
        if not choices:
            raise hs.Unconfirmed('RECEIVED_TALKING_SCROLL12273_UNSUPPLIED')
        return min(choices)

    @staticmethod
    def quantity_changed(batch, uid, quantity):
        for frame in batch:
            if frame.opcode == 0x0978 and hb.scalar(frame.values, 1) == uid:
                return True
            if frame.opcode == 0x0965:
                for raw in frame.values.get(1, ()):
                    fields = hb.fields(raw)
                    if hb.scalar(fields, 1) == uid and hb.scalar(fields, 4, quantity) != quantity:
                        return True
        return False

    async def walk_after_arrival(self, trip):
        bot, broker = self.bot, self.broker
        start, before = bot.position, bot.moves
        await asyncio.sleep(max(0, bot.next_move - time.monotonic()))
        for heading, (dx, dy) in enumerate(hb.DELTAS):
            target = (start[0] + dx, start[1] + dy)
            if broker._world_edge_fallback(bot.map_id, *start, heading) is not True:
                continue
            await bot.step(target)
            if bot.moves > before:
                position = self.position_observation()
                expected = (bot.map_id, *target)
                self.record('ordinary_walking_after_trip_' + str(trip),
                    all(tuple(value) == expected for value in position.values()),
                    accepted_steps=bot.moves - before, **position)
                return
        raise hs.Unconfirmed('NO_ACCEPTED_DESTINATION_WALK_STEP')

    async def talkscroll(self):
        # This is the original client's static table, not a server response.
        # Item12273 CommonItemInfo.f53=10 selects group10; f13 carries the
        # zero-based ordinal from that complete group (headings included).
        source = Path(__file__).resolve().parents[2] / 'work/all_table_semantics/travel_review/teleport-ui-joins.json'
        local_rows = json.loads(source.read_text(encoding='utf-8'))
        choices = [next(row for row in local_rows if row['group_id'] == 10
                        and row['ordinal'] == ordinal) for ordinal in self.args.ordinals]
        self.record('client_local_group10_selection_metadata',
            all(not row['is_heading'] and row['f1_signed_destination_key'] == 0 for row in choices),
            source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            group_id=10, ordinals=[row['ordinal'] for row in choices],
            names=[row['f4_KR'] for row in choices],
            scope='static client-local list metadata; no server list packet; native window/click unverified',
            limitation='original group10 Talking Island facilities, not two hunting-area rows; '
                'first ordinal8 attempt failed with NPC_EXPLICIT_SPR56_TEMPLATE0_ONLY and '
                'partial saved relocation (hunt-talkscroll-mkcp__e6); this run covers only selected rows')
        uid, item = self.received_scroll()
        self.record('received_server_issued_talking_scroll',
            item.get(5) == 133 and item.get(7) == 20256 and item[4] == 1,
            uid=uid, template=item[2], raw=item.get(5), icon=item.get(7), quantity=item[4])
        first_count = item[4]
        position_before_rejection, bag_before_rejection = self.position_observation(), self.saved_bag()
        peer_before_rejection = self.bot.peer
        invalid_params = hb.uint(1, 1) + hb.uint(13, 999999) + hb.uint(15, 0) + hb.uint(16, 0)
        rejected = await self.bot.peer.request(0x0960,
            hb.uint(1, uid) + hb.pb.encode_bytes(2, invalid_params), alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label='TALKSCROLL_UNSUPPORTED_CHOICE_ALIVE')
        rejection_code = 'TALKSCROLL_UNKNOWN_NATIVE_DESTINATION'
        self.record('unsupported_choice_refused_without_broker_or_socket_death',
            self.position_observation() == position_before_rejection
            and self.saved_bag() == bag_before_rejection == self.bot.inventory
            and self.bot.peer is peer_before_rejection and self.bot.peer.error is None
            and self.broker.report().get('failure_code') is None
            and self.broker._world_handler_errors == [rejection_code]
            and not self.quantity_changed(rejected, uid, first_count),
            rejected_ordinal=999999, expected_error=rejection_code, quantity=first_count,
            socket_alive_barrier=True, position=position_before_rejection,
            scope='unsupported selection reaches actual decoder/router; only that request is refused')
        original_uid = uid
        for index, choice in enumerate(choices, 1):
            uid, item = self.received_scroll()
            before_bag = self.saved_bag()
            quantity, departure = item[4], (self.bot.map_id, *self.bot.position)
            expected = (choice['f1_signed_destination_key'], choice['f2_x_candidate'], choice['f3_y_candidate'])
            params = (hb.uint(1, 1) + hb.uint(13, choice['ordinal'])
                      + hb.uint(15, 0) + hb.uint(16, 0))

            def arrived(batch):
                return hb.find(batch, 0x4ee0, **{'1': expected[1], '2': expected[2]})

            batch = await self.bot.peer.request(0x0960,
                hb.uint(1, uid) + hb.pb.encode_bytes(2, params), check=arrived,
                label='TALKSCROLL_LOCAL_CHOICE_' + str(choice['ordinal']))
            saved = self.saved_bag()
            position = self.position_observation()
            wire_count = self.bot.inventory.get(uid, {}).get(4, 0)
            saved_count = saved.get(uid, {}).get(4, 0)
            trip = dict(trip=index, uid=uid, ordinal=choice['ordinal'], destination_name=choice['f4_KR'],
                departure=departure, destination=expected, quantity_before=quantity,
                wire_quantity_after=wire_count, saved_quantity_after=saved_count,
                arrival_frame_ordinal=hb.find(batch, 0x4ee0).ordinal,
                local_unused_button_coordinates=[0, 0], **position)
            self.trips.append(trip)
            self.record('choice_arrival_and_reusable_quantity_' + str(index),
                all(tuple(value) == expected for value in position.values())
                and wire_count == saved_count == quantity == first_count
                and saved == before_bag == self.bot.inventory
                and not self.quantity_changed(batch, uid, quantity)
                and uid == original_uid and departure != expected, **trip)
            await self.walk_after_arrival(index)
        before_position = self.position_observation()
        before_bag, character = self.saved_bag(), self.bot.character
        self.record('two_distinct_actual_group10_choices',
            self.trips[0]['destination'] != self.trips[1]['destination']
            and self.received_scroll()[0] == original_uid
            and self.received_scroll()[1][4] == first_count,
            reuse_policy='unlimited uses; official beginner guide APIid24649',
            expiration='UNKNOWN: acquisition time/expiry deadline is not supplied')
        self.record('normal_quit_before_reconnect', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('FIRST_EPOCH_CLOSE_FAILED_NO_RECONNECT')
        await self.open(seed=False, character=character)
        after_position, after_bag = self.position_observation(), self.saved_bag()
        self.record('saved_position_and_inventory_restored_after_fresh_FIRST',
            before_position == after_position and before_bag == after_bag == self.bot.inventory,
            before=before_position, after=after_position, inventory_rows=len(after_bag),
            scroll_quantity_after_reconnect=self.received_scroll()[1][4],
            basis='same preserved profile; no seed/grant/position commit on reconnect')
        self.record('only_expected_request_refusal',
            not self.broker._world_handler_errors
            and self.handler_epochs[0]['errors'] == [rejection_code],
            first_epoch_errors=self.handler_epochs[0]['errors'],
            reconnect_epoch_errors=self.broker._world_handler_errors)


def parser():
    result = hs.parser()
    result.description = __doc__
    next(action for action in result._actions if action.dest == 'scenario').choices = ('talkscroll', 'all')
    result.add_argument('--ordinals', nargs=2, type=int, default=(1, 7),
                        help='two original group10 ordinals; default warehouse1 then dock7')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-talkscroll-', dir=root))
    source_paths = ('hunt_bot_talkscroll.py', 'hunt_bot.py', 'hunt_bot_scenarios.py',
        'hunt_bot_loopback.py', 'world_feature_talkscroll.py', 'world_talkscroll.py',
        'world_handlers.py', 'world_bridge.py', 'world_feature_kit.py', 'world_feature_maps.py',
        'world_feature_items.py', 'broker.py', 'inventory.py', 'inventory_store.py',
        'equipment_store.py', 'world_maps.py', 'npc.py', 'data/m1/starter.json',
        'data/m2/talkscroll.json')
    def sources():
        return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in source_paths if (Path(__file__).parent / name).exists()}
    started_sources = sources()
    scenario = TalkScrollScenario(args, directory)
    result = await scenario.run()
    result.update(scope='owned fresh test profile; normal FIRST/login/selection/world and real '
        'socket decoder/router; native input/rendering and original-client milestone unverified',
        fixture=scenario.fixture, trips=scenario.trips, handler_epochs=scenario.handler_epochs)
    result['source_sha256_start'], result['source_sha256'] = started_sources, sources()
    result['source_changes_during_run'] = [name for name in source_paths
        if started_sources.get(name) != result['source_sha256'].get(name)]
    result['reused_from'] = {name: result['source_sha256'][name]
        for name in ('hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_loopback.py')}
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False,
        indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
