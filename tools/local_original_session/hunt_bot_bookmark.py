"""Owned bookmark socket scenario; no original client, global input or user save.

The fresh pre-FIRST fixture adds two LOCAL grade0 teleport23 scrolls to the retained
test_knight kit. Their actual received SC0964 UID, never a fabricated live
reference, is used after ordinary FIRST/login/select/world and reconnect.
SUCCESS concerns the declared LOCAL bookmark policy and packet/storage flow;
native bookmark UI, input and original-server behavior remain unverified.
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


DISABLED_FEATURES = ('world_feature_alignment', 'world_feature_monster_skills')


class BookmarkBot(ConsumableBot):
    def __init__(self, args):
        super().__init__(args)
        self.bookmark_notices = []

    def apply(self, frame):
        if frame.opcode in (0x4e4d, 0xc371, 0x4f60):
            frame.values = hb.fields(frame.wire[4:-2])
            self.bookmark_notices.append(frame)
        super().apply(frame)


def notice_rows(frame):
    """Recovered nested field types; f3..5 meanings checked separately.

    The source inventory identifies id/name strongly. Keep the three signed
    integers positional until their coordinate semantics have been confirmed.
    """
    field = 2 if frame.opcode == 0x4e4d else 1
    result = []
    for raw in frame.values.get(field, ()):
        child = hb.fields(raw)
        name = hb.scalar(child, 2)
        result.append(dict(id=hb.scalar(child, 1),
            name=None if not isinstance(name, bytes) else name.decode('utf-8', 'strict'),
            signed_values=[signed32(hb.scalar(child, number)) for number in (3, 4, 5)]))
    return result


def signed32(value):
    if value is None:
        return None
    value &= 0xffffffff
    return value - (1 << 32) if value & (1 << 31) else value


class BookmarkScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, args.scenario, directory)
        self.fixture = None
        self.handler_epochs, self.actions = [], []
        self.stage = 'startup'

    def record(self, name, ok, **evidence):
        super().record(name, ok, stage=self.stage, **safe(evidence))
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    def saved_bag(self):
        from tools.local_original_session import inventory
        frame = self.store.restore(self.bot.self_uid)
        if frame is None:
            raise hs.Unconfirmed('BOOKMARK_SAVED_INVENTORY_REQUIRED')
        return {item.identifier: dict(item.raw_fields)
                for item in inventory.validate_kit_frame(frame)}

    def saved_bookmarks(self):
        return self.broker.realm.store.bookmarks(self.bot.self_uid)

    def saved_position(self):
        rows = json.loads((self.directory / 'positions.json').read_text(encoding='utf-8'))['positions']
        row = next((row for row in rows if row['uid'] == self.bot.self_uid), None)
        return None if row is None else (row['map_id'], *row['grid'])

    def authority_position(self):
        entity = self.broker._world.entities.get(self.bot.self_uid)
        return None if entity is None else (entity.map_id, entity.x, entity.y)

    def wire_bag_matches_saved(self):
        return self.bot.inventory == hb.displayed_rows(self.store.restore(self.bot.self_uid))

    async def leave_bookmark_cell(self):
        bot = self.bot
        start = bot.position
        occupied = {(entity.x, entity.y) for entity in self.broker._world.entities
                    if entity.map_id == bot.map_id and entity.uid != bot.self_uid}
        goals = [(start[0] + dx, start[1] + dy) for dx, dy in hb.DELTAS]
        goal = next((point for heading, point in enumerate(goals) if point not in occupied
            and bot.terrain.can_step(bot.map_id, *start, heading) is True), None)
        if goal is None:
            raise hs.Unconfirmed('BOOKMARK_ADJACENT_WALKABLE_DESTINATION_REQUIRED')
        move = await self.navigate(goal)
        self.record('normal_walk_before_saved_target_teleport',
            bot.position != start and self.authority_position() == (bot.map_id, *bot.position),
            move=move, authority_position=self.authority_position(),
            scope='normal CS4E2B with ordered ALIVE barrier and no correction; no live position mutation')

    async def mutation(self, opcode, name, identifier=None):
        payload = hb.pb.encode_bytes(1, name.encode('utf-8'))
        if identifier is not None:
            payload += hb.uint(2, identifier)
        batch = await self.bot.peer.request(opcode, payload, alive=True,
            check=lambda frames: hb.find(frames, 0x4f57), label=f'BOOKMARK_{opcode:04X}')
        notices = [frame for frame in batch if frame.opcode in (0x4e4d, 0xc371)]
        self.actions.append(dict(opcode=f'{opcode:04X}', name=name, identifier=identifier,
            notices=[dict(opcode=f'{frame.opcode:04X}', ordinal=frame.ordinal,
                capacity=hb.scalar(frame.values, 1) if frame.opcode == 0x4e4d else None,
                rows=notice_rows(frame)) for frame in notices]))
        if opcode == 0x4e4a:
            self.record('received_ADD_main_list_' + str(len(self.actions)),
                any(frame.opcode == 0x4e4d for frame in notices),
                action=self.actions[-1], scope='actual decoder/router request and SC_ADD_BOOKMARK_NOTI')
        else:
            self.record('mutation_reaches_ordered_ALIVE_barrier_' + str(len(self.actions)),
                hb.find(batch, 0x4f57) is not None,
                action=self.actions[-1],
                scope='native UPDATE/DELETE modify their local row immediately; no server mutation ACK is required or invented')
        return notices

    async def current_main_notice(self):
        batch, notice = await self.bot.peer.wait(0,
            lambda frames: hb.find(frames, 0x4e4d), 'ADD_BOOKMARK_MAIN_LIST')
        return notice

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
        if seed:
            from tools.local_original_session import broker, inventory, movement
            from tools.local_original_session import world_enchant_inventory as enchant
            from tools.local_original_session.hunt_bot_loopback import KNIGHT, START
            before = self.store.restore(1)
            before_items = inventory.validate_kit_frame(before)
            rows = [dict(item.raw_fields) for item in before_items]
            if any(item.template_bits == 23 and item.blessed for item in before_items):
                raise hs.Unconfirmed('FRESH_BLESSED_TELEPORT23_ALREADY_PRESENT')
            item = dict(broker.INVENTORY_STARTER_FIELDS)
            item.update({1: max(row[1] for row in rows) + 1, 2: 23, 4: 2,
                         7: self.broker._world.data.items[23].icon,
                         18: enchant.enchanted_name(self.broker._world.data.items[23], 0, grade=0)})
            rows.append(item)
            crystal = dict(broker.INVENTORY_STARTER_FIELDS)
            crystal.update({1: max(row[1] for row in rows) + 1, 2: 12458, 4: 1,
                            7: 20416, 18: '케플리샤의 기억 저장 구슬'.encode('utf-8')})
            rows.append(crystal)
            after = inventory.build_kit_frame(rows)
            self.store.replace_kit(1, before, after, append=True)
            self.broker._inventory_current_frame = after
            town = self.broker._world.data.town
            departure = (town.map_id, town.respawn_x, town.respawn_y)
            if self.args.scenario == 'bookmark_region':
                from tools.local_original_session import world_bookmark as bookmark
                # Explicit fresh pre-FIRST region fixture. The request uses
                # the row actually received after login; this initial saved
                # bookmark/position preparation is excluded from packet PASS.
                self.broker.realm.store.update_bookmarks(1, lambda value:
                    bookmark.add(value, self.args.bookmark_name, *departure))
                departure = {2: (2, 32665, 32789), 37: (37, 32667, 32868)}[self.args.departure_map]
            old = self.broker.realm.positions.restore(movement.Position(1, KNIGHT[0], 0, *START))
            self.broker.realm.positions.commit(old, movement.Position(
                1, KNIGHT[0], *departure), transition=old.map_id != departure[0])
            self.fixture = dict(character=KNIGHT[0], uid=1, kit='test_knight',
                teleport_template=23, quantity=2, scroll_grade=0,
                preserved_normal_scroll_quantity=sum(dict(item.raw_fields)[4]
                    for item in before_items if item.template_bits == 23 and item.bless == 1),
                grade_contract='existing LOCAL f18 [축복] marker; native grade encoding unverified',
                disabled_features=DISABLED_FEATURES,
                disabled_reason='existing monster/alignment catalog mismatch and concurrently registered missing monster_skills module prevent unrelated world startup',
                crystal_template=12458, crystal_quantity=1,
                position=list(departure),
                inventory_sha256=hashlib.sha256(after).hexdigest(),
                source='hs.build_epoch fresh owned test_knight and pre-FIRST InventoryStore/PositionStore APIs',
                scope='LOCAL fresh pre-FIRST position, optional region bookmark, scroll/crystal supply; no user save or live mutation; preparation excluded')
            (self.directory / 'starting-fixture.json').write_text(json.dumps(
                self.fixture, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected,
            '--minutes', str(self.args.minutes), '--timeout', str(self.args.timeout)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = BookmarkBot(options)
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = self.broker._world.data, time.monotonic()
        self.bot.terrain = self.broker._world.terrain
        try:
            await self.bot.login()
        except hb.BotFailure as error:
            # Reuse hunt_bot_map_expansion2's narrow saved-map expectation.
            # Shared login already received ACK -> map -> status -> own actor;
            # its final (0,1,2) whitelist predates this prepared region fixture.
            if (str(error) != 'MAP0_SELF_POSITION_AND_HP_REQUIRED'
                    or self.args.scenario != 'bookmark_region' or not self.bot.selected
                    or self.bot.position is None
                    or (self.bot.map_id, *self.bot.position) != tuple(self.fixture['position'])
                    or self.bot.hp is None or not self.bot.max_hp):
                raise
            await self.bot.alive()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'BOOKMARK_KIT_DELIVERY')
        self.record('FIRST_login_selection_world_' + str(len(self.bots)),
            self.bot.selected and self.bot.inventory_received and self.bot.hp > 0,
            uid=self.bot.self_uid, map_id=self.bot.map_id, position=self.bot.position)

    async def close(self):
        if self.broker is not None:
            self.handler_epochs.append(dict(
                errors=list(getattr(self.broker, '_world_handler_errors', ())),
                hook_errors=list(getattr(self.broker, '_world_hook_errors', ())),
                report=self.broker.report().get('world')))
        return await super().close()

    async def bookmark(self):
        try:
            await self.bookmark_flow()
        except BaseException:
            (self.directory / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise

    async def bookmark_flow(self):
        self.stage = 'normal_bookmark_mutations'
        bot = self.bot
        self.record('fresh_saved_bookmark_list_is_empty',
            self.saved_bookmarks()['entries'] == [], saved=self.saved_bookmarks(), fixture=self.fixture)
        initial = await self.current_main_notice()
        self.record('initial_SC_ADD_BOOKMARK_NOTI_main_list_is_empty', notice_rows(initial) == [],
            opcode='4E4D', ordinal=initial.ordinal, rows=notice_rows(initial),
            capacity=hb.scalar(initial.values, 1),
            scope='native main map insert path; C371 is BookmarkCrystalLayout and is not a main-list refresh')
        target = (bot.map_id, *bot.position)
        self.record('saved_location_is_current_server_position', self.authority_position() == target,
            target=target, server_position=self.authority_position())
        await self.unsupported_requests()

        notices = await self.mutation(0x4e4a, self.args.bookmark_name)
        first = self.saved_bookmarks()
        rows = first['entries']
        self.record('ADD_persists_current_position', len(rows) == 1
            and rows[0]['name'] == self.args.bookmark_name
            and (rows[0]['map_id'], rows[0]['x'], rows[0]['y']) == target,
            saved=first, target=target)
        entry = rows[0]
        self.record('ADD_notice_contains_server_issued_id_and_name', any(
            row['id'] == entry['id'] and row['name'] == entry['name']
            for frame in notices for row in notice_rows(frame)), server_entry=entry)

        renamed = self.args.bookmark_name + 'R'
        notices = await self.mutation(0x4e4b, renamed, entry['id'])
        changed = self.saved_bookmarks()
        self.record('UPDATE_renames_current_server_id_without_moving_location',
            changed['entries'] == [dict(entry, name=renamed)]
            and changed['next_id'] == first['next_id'], saved=changed)
        self.record('UPDATE_native_no_ACK_contract', not notices,
            received=self.actions[-1]['notices'],
            scope='server save checked after ordered ALIVE; native client-side rename/input unverified')
        notices = await self.mutation(0x4e4c, renamed, entry['id'])
        deleted = self.saved_bookmarks()
        self.record('DELETE_removes_current_name_and_id_without_rewinding_identity',
            deleted['entries'] == [] and deleted['next_id'] == first['next_id'], saved=deleted)
        self.record('DELETE_native_no_ACK_contract', not notices,
            received=self.actions[-1]['notices'],
            scope='server save checked after ordered ALIVE; native client-side deletion/input unverified')
        notices = await self.mutation(0x4e4a, self.args.bookmark_name)
        saved = self.saved_bookmarks()
        self.record('reADD_issues_fresh_identity_at_current_position', len(saved['entries']) == 1
            and saved['entries'][0]['id'] > entry['id']
            and saved['entries'][0]['name'] == self.args.bookmark_name
            and (saved['entries'][0]['map_id'], saved['entries'][0]['x'], saved['entries'][0]['y']) == target,
            saved=saved, previous_id=entry['id'])
        entry = saved['entries'][0]
        self.record('reADD_new_identity_is_actually_received', any(
            row['id'] == entry['id'] and row['name'] == entry['name']
            for frame in notices for row in notice_rows(frame)), server_entry=entry)

        self.stage = 'normal_quit_new_broker_reconnect'
        character, saved_bag = bot.character, self.saved_bag()
        self.record('normal_quit_before_reconnect', await bot.quit_selected())
        self.record('quit_preserves_saved_bookmark_and_position',
            self.saved_bookmarks() == saved and self.saved_position() == target,
            saved_bookmarks=self.saved_bookmarks(), saved_position=self.saved_position())
        if not await self.close():
            raise hb.BotFailure('BOOKMARK_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        restored_notice = await self.current_main_notice()
        restored_rows = notice_rows(restored_notice)
        self.record('fresh_FIRST_delivers_saved_SC_ADD_BOOKMARK_NOTI_main_list',
            self.saved_bookmarks() == saved and len(restored_rows) == 1
            and restored_rows[0]['id'] == entry['id'] and restored_rows[0]['name'] == entry['name']
            and self.saved_bag() == saved_bag and self.wire_bag_matches_saved()
            and (self.bot.map_id, *self.bot.position) == target,
            opcode='4E4D', ordinal=restored_notice.ordinal, received=restored_rows,
            saved=saved, position=(self.bot.map_id, *self.bot.position),
            scope='new broker, retained owned save, seed=False; no bookmark/item/position grants on reconnect')
        await self.leave_bookmark_cell()
        await self.teleport_to(entry, saved, restored_rows[0])

    async def refusal(self, opcode, payload, label, reason):
        before = self.saved_bookmarks(), self.saved_bag(), self.saved_position(), self.authority_position()
        batch = await self.bot.peer.request(opcode, payload, alive=True,
            check=lambda frames: hb.find(frames, 0x4f57), label=label)
        after = self.saved_bookmarks(), self.saved_bag(), self.saved_position(), self.authority_position()
        notices = [frame.opcode for frame in batch if frame.opcode in (0x4e4d, 0xc371, 0x4f60)]
        errors = self.broker.report()['world']['bookmark_errors']
        self.actions.append(dict(opcode=f'{opcode:04X}', label=label,
            refusal=reason, notice_opcodes=notices))
        self.record(label, before == after and not notices and errors[-1:] == [reason]
            and self.wire_bag_matches_saved(), errors=errors, notices=notices,
            scope='ordered ALIVE after actual socket request; unchanged owned save/inventory/position; no invented ACK')

    async def unsupported_requests(self):
        self.stage = 'phase2_unsupported_contracts_no_fake_success'
        await self.refusal(0x4f5f, b'', 'extension_unknown_cost_does_not_expand_or_ACK',
            'BOOKMARK_EXTENSION_COST_AND_INCREMENT_UNKNOWN')
        # Field shape is recovered; coordinate/command privilege is unknown.
        await self.refusal(0x4e41, b''.join(hb.uint(n, value) for n, value in
            ((1, self.bot.map_id), (2, self.bot.position[0]), (3, self.bot.position[1]))),
            'coordinate_request_never_authorizes_client_chosen_destination',
            'BOOKMARK_COORDINATE_COMMAND_UNSUPPORTED')
        crystals = [uid for uid, item in self.bot.inventory.items() if item.get(2) == 12458]
        if len(crystals) != 1:
            raise hs.Unconfirmed('RECEIVED_OWNED_CRYSTAL_UID_REQUIRED')
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        await self.refusal(0x0960, hb.uint(1, crystals[0]) + hb.pb.encode_bytes(2, params),
            'crystal_received_UID_is_preserved_without_fabricated_C371',
            'BOOKMARK_CRYSTAL_STORAGE_AND_USE_CONTRACT_UNKNOWN')

    async def bookmark_region(self):
        self.stage = 'phase2_fresh_region_fixture'
        notice = await self.current_main_notice()
        saved = self.saved_bookmarks()
        received = notice_rows(notice)
        self.record('region_initial_saved_row_is_actually_received', len(received) == 1
            and len(saved['entries']) == 1 and received[0]['id'] == saved['entries'][0]['id']
            and (self.bot.map_id, *self.bot.position) == tuple(self.fixture['position']),
            fixture=self.fixture, received=received,
            scope='LOCAL prepared starting save; initial bookmark creation/travel is outside this scoped packet check')
        await self.refusal(0x4e4a, hb.pb.encode_bytes(1, '금지지역'.encode('utf-8')),
            'region_not_markable_ADD_preserves_saved_rows', 'BOOKMARK_LOCATION_NOT_MARKABLE')
        if self.args.departure_map == 2:
            await self.teleport_to(saved['entries'][0], saved, received[0])
        else:
            uids = [uid for uid, item in self.bot.inventory.items() if item.get(2) == 23
                    and item.get(18, b'').startswith('[축복]'.encode('utf-8'))]
            if len(uids) != 1:
                raise hs.Unconfirmed('RECEIVED_BLESSED_SCROLL_UID_REQUIRED')
            params = hb.uint(1, 1) + b''.join(hb.uint(n, value) for n, value in
                zip((8, 9, 10), received[0]['signed_values']))
            await self.refusal(0x0960, hb.uint(1, uids[0]) + hb.pb.encode_bytes(2, params),
                'non_escapable_departure_keeps_scroll_and_position', 'BOOKMARK_DEPARTURE_NOT_ESCAPABLE')
            self.record('region_normal_quit', await self.bot.quit_selected())

    async def teleport_to(self, entry, saved, received_entry):
        self.stage = 'blessed_scroll_to_received_saved_location'
        bot = self.bot
        from tools.local_original_session import inventory
        canonical_rows = {item.identifier: item for item in inventory.validate_kit_frame(
            self.store.restore(bot.self_uid))}
        choices = [(uid, row) for uid, row in bot.inventory.items()
                   if row.get(2, -1) & 0xffffffff == 23 and row.get(4, 0) > 0
                   and uid in canonical_rows and canonical_rows[uid].blessed]
        if len(choices) != 1:
            raise hs.Unconfirmed('RECEIVED_TELEPORT23_UID_REQUIRED')
        uid, row = choices[0]
        canonical = canonical_rows.get(uid)
        self.record('target_teleport_uses_received_owned_blessed_scroll_UID',
            canonical is not None and canonical.blessed and self.wire_bag_matches_saved(),
            received_uid=uid, template=23, quantity=row[4],
            grade=None if canonical is None else canonical.bless,
            source='actual SC0964 inventory from retained fixture; existing LOCAL f18 grade0 contract')
        quantity, departure = row[4], (bot.map_id, *bot.position)
        target = (entry['map_id'], entry['x'], entry['y'])
        triple = received_entry['signed_values']
        self.record('target_arguments_are_the_actual_received_bookmark_triple',
            received_entry['id'] == entry['id'] and received_entry['name'] == entry['name']
            and len(triple) == 3 and all(type(value) is int and value >= 0 for value in triple),
            received_entry=received_entry,
            contract='native selected sender0x915510 copies SC child f3/f4/f5 into UseItemParam f8/f9/f10')
        params = hb.uint(1, 1) + b''.join(hb.uint(number, value)
            for number, value in zip((8, 9, 10), triple))

        def consumed_then_arrived(batch):
            changed = None
            for frame in batch:
                if frame.opcode == 0x0978 and quantity == 1 and hb.scalar(frame.values, 1) == uid:
                    changed = frame
                elif frame.opcode == 0x0965:
                    for raw in frame.values.get(1, ()):
                        child = hb.fields(raw)
                        if hb.scalar(child, 1) == uid and hb.scalar(child, 4) == quantity - 1:
                            changed = frame
            if changed is None:
                return None
            # This fixture explicitly selects existing MapExp2 publication:
            # cost, 4E95 map reset, own 4E38, then own destination 4E96.
            # Same-map correction 4EE0 belongs to a different core branch.
            maps = hb.find([frame for frame in batch if frame.ordinal > changed.ordinal],
                           0x4e95, **{'1': target[0]})
            if maps is None:
                return None
            status = hb.find([frame for frame in batch if frame.ordinal > maps.ordinal],
                            0x4e38, **{'1': bot.self_uid})
            if status is None:
                return None
            return hb.find([frame for frame in batch if frame.ordinal > status.ordinal],
                           0x4e96, **{'1': hb.pack(target[1:]), '2': bot.self_uid})

        batch = await bot.peer.request(0x0960,
            hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
            check=consumed_then_arrived, label='BOOKMARK_SELECTED_SCROLL_CONSUMED_THEN_SELF_ACTOR')
        self.actions.append(dict(opcode='0960', item_uid=uid, template=23,
            params=dict(f1=1, f8=triple[0], f9=triple[1], f10=triple[2]),
            bookmark_received_id=received_entry['id'],
            responses=[dict(ordinal=frame.ordinal, opcode=f'{frame.opcode:04X}') for frame in batch]))
        after = self.saved_bag()
        wire_quantity = bot.inventory.get(uid, {}).get(4, 0)
        saved_quantity = after.get(uid, {}).get(4, 0)
        self.record('selected_scroll_consumes_exactly_one_and_persists_inventory',
            wire_quantity == saved_quantity == quantity - 1 and self.wire_bag_matches_saved(),
            item_uid=uid, quantity_before=quantity,
            received_quantity_after=wire_quantity, saved_quantity_after=saved_quantity)
        self.record('selected_scroll_relocates_to_bookmark_and_saves_actual_position',
            departure != target and (bot.map_id, *bot.position) == target
            and self.authority_position() == target and self.saved_position() == target
            and self.saved_bookmarks() == saved,
            departure=departure, target=target, wire_position=(bot.map_id, *bot.position),
            authority_position=self.authority_position(), saved_position=self.saved_position(),
            scope='existing LOCAL MapExp2 cost then 4E95/4E38/own4E96 relocation publication and position sidecar; native UI/camera/input unverified')
        self.record('normal_final_quit_preserves_consumption_and_bookmark',
            await bot.quit_selected() and self.saved_bag() == after
            and self.saved_bookmarks() == saved and self.saved_position() == target)
        self.record('no_handler_or_hook_errors_in_either_epoch',
            not getattr(self.broker, '_world_handler_errors', ())
            and not getattr(self.broker, '_world_hook_errors', ())
            and not any(epoch['errors'] or epoch['hook_errors'] for epoch in self.handler_epochs),
            epochs=[dict(errors=epoch['errors'], hook_errors=epoch['hook_errors'])
                    for epoch in self.handler_epochs],
            current_errors=getattr(self.broker, '_world_handler_errors', ()),
            current_hook_errors=getattr(self.broker, '_world_hook_errors', ()))


def parser():
    result = hs.parser()
    result.description = __doc__
    result.set_defaults(scenario='bookmark')
    next(action for action in result._actions if action.dest == 'scenario').choices = ('bookmark', 'bookmark_region')
    result.add_argument('--bookmark-name', default='책갈피시험마을')
    result.add_argument('--departure-map', type=int, choices=(2, 37), default=2)
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-bookmark-', dir=root))
    scene = BookmarkScenario(args, directory)
    source_paths = ('hunt_bot_bookmark.py', 'hunt_bot.py', 'hunt_bot_scenarios.py',
        'hunt_bot_loopback.py', 'hunt_bot_consumables.py', 'hunt_bot_play_matrix.py',
        'broker.py', 'world_handlers.py', 'world_bridge.py', 'world_core_session.py',
        'world_core_kit.py', 'world_core_maps.py', 'world_feature_bookmark.py',
        'world_bookmark.py', 'world_feature_items.py', 'world_item_effects.py',
        'world_enchant_inventory.py',
        'inventory.py', 'inventory_store.py', 'equipment_store.py', 'movement.py', 'test_ports.py',
        '../local_character_creation/realm.py',
        'data/m1/items.json', 'data/m1/item_effects.json', 'data/m1/monsters.json', 'data/m1/starter.json')
    def sources():
        return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in source_paths if (Path(__file__).parent / name).exists()}
    started = sources()
    with environment(SL_EXPERIMENT_MAP=2, SL_WORLD_TOWN_CANDIDATES='',
            SL_COMPANION=0, SL_COMPANION_PET_UI=0, SL_DISABLE_FEATURES=','.join(DISABLED_FEATURES)):
        result = await scene.run()
    result.update(directory=str(directory), fixture=scene.fixture, actions=scene.actions,
        handler_epochs=scene.handler_epochs, source_sha256_start=started, source_sha256=sources(),
        time_scale=os.environ.get('SL_TEST_TIME_SCALE', '1'),
        port_base=os.environ.get('SL_TEST_PORT_BASE', '12000'),
        physical_ports=test_ports.listener_ports(),
        disabled_features=DISABLED_FEATURES,
        unverified_bookmark_crystal='C371 crystal success/consumption is unsupported; only owned-item rejection without C371/debit is exercised',
        scope='fresh owned packet fixture; actual FIRST/login/selection/world and socket decoder/router; native UI and original-client milestone unverified')
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
