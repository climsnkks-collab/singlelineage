"""Fifteen owned loopback packet scenarios; no game client or user profile.

    $env:SL_TEST_PORT_BASE='24000'
    python tools/local_original_session/hunt_bot_play_matrix.py --scenario all

Fresh test_knight fixtures, FIRST/login/select/world and ordinary broker routes
are reused from hunt_bot_scenarios/companion. Profiles, requests and partial
failures remain in runs/hunt-play-matrix-*. Packet PASS never means native UI
equivalence. Missing required capabilities are SKIP, observations that fail are
FAIL. A failed substage does not erase earlier evidence or stop other scenarios.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import contextmanager
import dataclasses
import hashlib
import heapq
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
import uuid

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import hunt_bot_companion as hc
from tools.local_original_session import test_ports

NAMES = ('equip_all', 'potions_after_pickup', 'shop_sell_anchor',
    'warehouse_roundtrip', 'scrolls', 'enchant_poly', 'dungeon_items',
    'gludin_items', 'dungeon_death_restart', 'field_death_restart',
    'quit_saved_map', 'companion_full', 'mage_login', 'early_item_use', 'spam')
RAW0 = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
SOURCE_SHA256 = {}


def remember_loaded_sources():
    """One initial file fingerprint per cached module, not a source guard."""
    if 'hunt_bot_play_matrix' not in SOURCE_SHA256:
        path = Path(__file__).resolve()
        SOURCE_SHA256['hunt_bot_play_matrix'] = dict(file=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), basis='initial running harness source')
    core = {'broker', 'inventory', 'inventory_store', 'equipment_store',
            'item_use_session', 'item_equipment_effect', 'world_handlers',
            'hunt_bot', 'hunt_bot_loopback', 'hunt_bot_scenarios', 'hunt_bot_companion',
            'world_bridge', 'world_core_inventory', 'world_core_lifecycle'}
    for name, module in tuple(sys.modules.items()):
        leaf = name.rsplit('.', 1)[-1]
        if not name.startswith('tools.local_original_session.') or not (leaf in core or leaf.startswith('world_feature_')):
            continue
        filename = getattr(module, '__file__', None)
        if filename and name not in SOURCE_SHA256:
            path = Path(filename)
            SOURCE_SHA256[name] = dict(file=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                basis='first post-import on-disk fingerprint; cached module reused for later epochs')


class MissingFeature(RuntimeError):
    pass


def safe(value):
    """Bounded JSON metadata; never serialize frame/image bytes."""
    if isinstance(value, bytes):
        return dict(byte_count=len(value), sha256=hashlib.sha256(value).hexdigest())
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


@contextmanager
def environment(**changes):
    previous = {key: os.environ.get(key) for key in changes}
    try:
        os.environ.update({key: str(value) for key, value in changes.items()})
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class Matrix(hc.CompanionScenario):
    def __init__(self, args, name, directory):
        super().__init__(args, directory)
        self.name, self.directory = name, directory
        self.result_directory = directory
        self.gaps, self.failures, self.server_failures = [], [], []
        self.requests, self.first_failed_request = [], None
        self.stage = 'startup'
        self.map_start = None
        self.fixture_notes = []
        self.epoch_number = 0

    def record(self, name, ok, **evidence):
        status = 'SKIP' if ok is None else 'PASS' if ok else 'FAIL'
        row = dict(check=name, status=status, stage=self.stage, **safe(evidence))
        self.checks.append(row)
        if ok is False:
            self.failures.append(name)
            raise AssertionError(name)

    def missing(self, reason):
        if reason not in self.gaps:
            self.gaps.append(reason)
            self.checks.append(dict(check=self.stage, status='SKIP', reason=reason))

    def error_codes(self):
        if self.broker is None:
            return {}
        return {name: list(getattr(self.broker, name, ())) for name in
            ('_world_handler_errors', '_world_item_errors', '_companion_errors')}

    def travel_heading(self, goal, radius, *, require_reached=False, ignore_actors=False):
        """Terrain-aware A* for long travel; every selected step is a packet.

        The companion helper's radius-limited NPC search can settle in a local
        cul-de-sac after random teleport. This client search admits no server
        movement itself and uses only current terrain/entity observations.
        """
        bot, terrain = self.bot, self.broker._world.terrain
        start, now = bot.position, time.monotonic()
        occupied = {(e.x, e.y) for e in self.broker._world.entities.near(bot.map_id, *start, 32,
                     alive_only=False) if e.uid != bot.self_uid and e.kind.value != 'item'}
        if ignore_actors:
            occupied = set()
        heap = [(hb.distance(start, goal), 0, start, None)]
        costs, best = {start: 0}, None
        for _ in range(20000):
            if not heap:
                break
            _, cost, point, first = heapq.heappop(heap)
            if costs.get(point) != cost:
                continue
            if hb.distance(point, goal) <= radius:
                return first
            if first is not None and (best is None or hb.distance(point, goal) < best[0]):
                best = hb.distance(point, goal), first
            for heading, (dx, dy) in enumerate(hb.DELTAS):
                destination = point[0] + dx, point[1] + dy
                if destination in occupied or bot.blocked_edges.get((point, heading), 0) > now:
                    continue
                if (self.name in ('dungeon_items', 'gludin_items', 'quit_saved_map')
                        and not bot.safe_hunt_cell(destination)):
                    continue
                if terrain.can_step(bot.map_id, *point, heading) is not True:
                    continue
                following = cost + 1
                if following >= costs.get(destination, 1 << 30):
                    continue
                costs[destination] = following
                heapq.heappush(heap, (following + hb.distance(destination, goal), following,
                                     destination, heading if first is None else first))
        if self.name in ('dungeon_items', 'gludin_items', 'quit_saved_map'):
            if not require_reached and not ignore_actors:
                # Follow a complete static route toward a live blocker, then
                # the step wrapper attacks its actually received adjacent UID.
                # Ordinary movement still performs its unchanged occupancy check.
                return self.travel_heading(goal, radius, require_reached=True, ignore_actors=True)
            return None
        return None if require_reached or best is None else best[1]

    def reachable_hunt_goal(self, goal, radius):
        return (hb.distance(self.bot.position, goal) <= radius
                or self.travel_heading(goal, radius, require_reached=True, ignore_actors=True) is not None)

    def instrument(self):
        broker = self.broker
        original = broker._failure_code
        def failure_code(error):
            code = original(error)
            frames = traceback.extract_tb(error.__traceback__)
            self.server_failures.append(dict(code=code, error=str(error),
                request=safe(self.requests[-1]) if self.requests else None,
                traceback=[dict(file=f.filename, line=f.lineno, function=f.name,
                                source=f.line) for f in frames]))
            return code
        broker._failure_code = failure_code
        original_fail = broker._fail
        def fail(code):
            error = sys.exception()
            need_code = str(error) if error is not None else code
            if not self.server_failures or self.server_failures[-1].get('code') != need_code:
                frames = traceback.extract_tb(error.__traceback__) if error is not None else traceback.extract_stack()[:-1]
                self.server_failures.append(dict(code=need_code, broker_failure_code=code,
                    error=need_code, request=safe(getattr(self, 'active_api', None) or getattr(self, 'last_request', None)),
                    traceback=[dict(file=f.filename, line=f.lineno, function=f.name, source=f.line) for f in frames]))
            return original_fail(code)
        broker._fail = fail

    async def api(self, name, operation, *args, **kwargs):
        self.active_api = dict(opcode='API:' + name, stage=self.stage,
            preceded_by_packet=safe(getattr(self, 'last_request', None)))
        try:
            return await operation(*args, **kwargs)
        finally:
            self.active_api = None

    def instrument_peer(self, peer):
        original = peer.request
        async def request(opcode, payload=b'', **options):
            self.sync_native_position()
            row = dict(epoch=self.epoch_number, stage=self.stage,
                       opcode=f'0x{opcode:04X}', label=options.get('label'),
                       payload=safe(hb.fields(payload)), sent_at=time.monotonic())
            if opcode == 0x0960:
                row['item_uid'] = hb.scalar(hb.fields(payload), 1)
                nested = hb.scalar(hb.fields(payload), 2)
                if isinstance(nested, bytes):
                    row['params'] = safe(hb.fields(nested))
            self.requests.append(row)
            self.last_request = row
            before_errors = self.error_codes()
            try:
                batch = await original(opcode, payload, **options)
                row['received_opcodes'] = [f'0x{f.opcode:04X}' for f in batch]
                row['handler_errors_before'] = before_errors
                row['handler_errors_after'] = self.error_codes()
                return batch
            except BaseException as error:
                row['error'] = f'{type(error).__name__}: {error}'
                row['handler_errors_after'] = self.error_codes()
                if self.first_failed_request is None:
                    self.first_failed_request = safe(row)
                raise
            finally:
                with (self.directory / 'requests.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(safe(row), ensure_ascii=False) + '\n')
        peer.request = request

    def sync_native_position(self):
        """Mirror only received position into the LOCAL source-layout RAM peer.

        No product position/HP/readiness/store value is changed. This is the
        synthetic native adapter's movement consumer, not native game evidence.
        """
        memory = getattr(self, 'fixture_memory', None)
        if memory is None or self.bot is None or self.bot.position is None:
            return
        x, y = self.bot.position
        for address in (0x310000 + memory.proof.public['Map']['field718'],
                        0x310000 + 0x71c, 0x330000):
            memory.put(address, '<i', self.bot.map_id)
        memory.put(0x470000 + memory.proof.public['Position']['pair_offset'], '<ii',
                   (x >> 6) + 0x7e00, (y >> 6) + 0x7e00)
        memory.put(0x470000 + memory.proof.position_source['coordinates']['transform_grid_offset'], '<ii', x + 1, y)

    async def open(self, *, seed, character=None, deliver=True):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from tools.local_original_session import (broker as host, inventory, inventory_store,
            movement, restart, world_visibility, item_use_session, item_equipment_effect, observe)
        from tools.local_original_session.broker_tests import FixtureConversation, reserve
        from tools.local_original_session.edge_tests import Tests as EdgeTests
        from tools.local_original_session.inventory_tests import Memory
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.hunt_bot_loopback import KNIGHT, START
        expected = str(uuid.uuid4())
        self.fixture_memory = None
        self.epoch_number += 1
        plain_saved_map_seed = seed and self.name == 'quit_saved_map' and self.map_start[0] == 4
        if seed and not plain_saved_map_seed:
            host.ack.realm.CharacterStore(self.directory / 'characters.json').create(host.ack.realm.Creation(*KNIGHT))
        _, reader, native = EdgeTests.retained_binding(None)
        reader.image = observe.IMAGE.with_name('LC.guard.exe')
        reader.member.identity['image'] = str(reader.image)
        retained = reader.owner
        retained.child, retained.closed = reader.member, False
        retained.owner_handle, retained.owner_job = object(), object()
        reader.member.process, reader.member.job = retained.owner_handle, retained.owner_job
        native.stack = ExitStack()
        self.fixture_reader = reader
        async def owner(peer):
            return True
        sockets = None
        if plain_saved_map_seed:
            self.broker, self.store, self.equipment = await hs.build_epoch(self.directory, expected, seed=True)
        else:
            sockets = reserve()
        try:
            if not plain_saved_map_seed:
                self.broker = host.PersistentBroker(sockets=sockets, listener_ports=test_ports.listener_ports(),
                retained_owner=retained, owner_handle=retained.owner_handle, owner_job=retained.owner_job,
                owner_guard=owner, owner_liveness_guard=lambda: True, source_guard=lambda: None,
                conversation_factory=FixtureConversation, expected_uuid=expected,
                store_path=self.directory / 'characters.json', world_policy=world_visibility.POLICY,
                restart_policy=restart.POLICY, world_starter_kit='test_knight',
                inventory_policy=inventory.POLICY,
                inventory_frame=inventory.build_add(host.INVENTORY_STARTER_FIELDS), inventory_reader=reader,
                inventory_store_policy=inventory_store.POLICY, item_use_policy=item_use_session.POLICY,
                item_equipment_policy=item_equipment_effect.POLICY, item_equipment_first_enable=True,
                inventory_reselection_policy=host.INVENTORY_RESELECTION_POLICY,
                inventory_delivery_policy=host.INVENTORY_RESELECTION_DELIVERY,
                inventory_missing_row_policy=host.INVENTORY_MISSING_ROW_POLICY)
        except BaseException:
            for sock in sockets.values():
                sock.close()
            raise
        if not plain_saved_map_seed:
            self.store, self.equipment = self.broker._inventory_store, self.broker._item_equipment_effect.store
        remember_loaded_sources()
        self.instrument()
        if seed and not plain_saved_map_seed:
            x, y = movement.authority.unpack_grid(self.broker.realm._actor_fields[1])
            self.broker.realm.positions.commit(movement.Position(1, KNIGHT[0], 0, x, y),
                movement.Position(1, KNIGHT[0], 0, *START))
        if seed and self.name in ('companion_full', 'mage_login'):
            self.initialize_mage_fixture()
        if seed and self.name in ('dungeon_items', 'gludin_items', 'quit_saved_map'):
            self.initialize_hunt_fixture()
        if seed and self.name == 'gludin_items':
            self.initialize_boat_fixture()
        if seed and self.map_start is not None:
            current = self.broker.realm.positions.restore(movement.Position(1, 'SoloKnight', 0, 0, 0))
            map_id, x, y = self.map_start
            self.broker.realm.positions.commit(current, movement.Position(1, current.name, map_id, x, y),
                                               transition=current.map_id != map_id)
            self.fixture_notes.append(dict(pre_login_position=self.map_start))
        if seed and self.name == 'warehouse_roundtrip':
            from tools.local_original_session.world_progress import Progress
            self.broker._world_progress.commit(1, Progress(load_m1().pc_exp[4], 5))
            self.fixture_notes.append(dict(pre_login_level=5, reason='ordinary warehouse minimum level'))
        if seed and self.name == 'enchant_poly':
            self.initialize_enchant_fixture()
        if seed and self.map_start is not None and self.map_start[0] == 4:
            self.fixture_notes.append(dict(pre_login_saved_map=self.map_start,
                scope='saved-map fixture; no claim of public map entry',
                missing_entry='Lucas50015 has no native template, sprite or sprite candidate; no SC4E96 actor can supply a public click target',
                boat_tickets='product item/weight definitions124/125 present; gludin_items alone receives one each as explicit pre-login test supplies; no purchase claim'))
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected, '--timeout', str(self.args.timeout),
            '--minutes', str(self.args.minutes), '--potion-threshold', str(self.args.potion_threshold)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = hs.ScenarioBot(options)
        self.bot.heading = self.travel_heading
        if self.name in ('dungeon_death_restart', 'field_death_restart'):
            self.bot.safe_hunt_cell = lambda point: True  # navigation policy only; actual AI damage remains authoritative
        original_step = self.bot.step
        async def step(goal, radius=0):
            if self.name not in ('dungeon_death_restart', 'field_death_restart'):
                await self.owner_potion()
            if (self.name in ('dungeon_items', 'gludin_items', 'quit_saved_map')
                    and hb.distance(self.bot.position, goal) > radius
                    and self.travel_heading(goal, radius, require_reached=True) is None):
                blockers = [(uid, row) for uid, row in self.bot.actors.items()
                            if self.bot.hunt_target(row)
                            and hb.distance(self.bot.position, row['position']) <= 1]
                if blockers:
                    await self.bot.attack(min(blockers, key=lambda pair: pair[0])[0])
                    return
            marker = self.bot.peer.ordinal
            await original_step(goal, radius)
            # Shared HuntBot predicts a same-map step after Alive. A real
            # MapExp transition instead supplies a new map and self Actor.
            batch = [f for f in self.bot.peer.frames if f.ordinal > marker]
            if hb.find(batch, 0x4e95) is not None:
                actor = hb.find(batch, 0x4e96, **{'2': self.bot.self_uid})
                if actor is not None:
                    self.bot.position = hb.unpack(hb.scalar(actor.values, 1))
        self.bot.step = step
        async def connect():
            reader, writer = await asyncio.wait_for(asyncio.open_connection(options.host, options.port), options.timeout)
            peer = hb.Peer(self.bot, reader, writer)
            self.bot.peers.append(peer)
            self.instrument_peer(peer)
            await peer.wait(0, lambda batch: next((f for f in batch if f.wire == hb.KEY12), None), 'KEY12')
            version = b''.join(hb.uint(n, value) for n, value in ((1, 52), (2, 949), (3, 1), (4, 26092901)))
            await peer.request(0x4e34, version, check=lambda batch: hb.find(batch, 0x4e35))
            await peer.request(0x4f3d, check=lambda batch: next(
                (f for f in batch if f.wire == b'\x06\0\x3e\x4f\0\0'), None))
            return peer
        self.bot.connect = connect
        original_apply = self.bot.apply
        def apply(frame):
            if frame.opcode in (0x097a, 0x4e44, 0x4e48, 0x4ee7, 0x4ed2, 0x0971,
                                 0x4f14, 0x4ed8, 0x4f16, 0x4ed5, 0x4e5c):
                frame.values = hb.fields(frame.wire[4:-2])
            original_apply(frame)
        self.bot.apply = apply
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = self.broker._world.data, time.monotonic()
        try:
            await self.bot.login()
        except hb.BotFailure as error:
            # Shared HuntBot predates MapExp map4. Its normal login already
            # observed ACK/map/status/self before this narrow validation.
            if str(error) != 'MAP0_SELF_POSITION_AND_HP_REQUIRED' or self.bot.map_id != 4 or not self.bot.selected:
                raise
            if self.bot.position is None or self.bot.hp is None or not self.bot.max_hp:
                raise
            await self.bot.alive()
        rows = [r for claims in self.broker._claims.values() for r in claims
                if id(r['writer']) in self.broker._world_pcs]
        if len(rows) != 1:
            raise RuntimeError('HARNESS_ONE_SELECTED_SOCKET_REQUIRED')
        writer = rows[0]['writer']
        if not deliver:
            self.record('normal_login_select_world_early_quit_scope', self.bot.selected and
                self.bot.position is not None and self.bot.hp is not None,
                character=self.bot.character, map_id=self.bot.map_id,
                inventory_received=self.bot.inventory_received,
                scope='existing hs.build_epoch saved-map seed; normal world/kit packets then Quit; seed epoch makes no native inventory sync claim. Reconnect epochs use full production inventory policies.')
            return
        self.native_case = SimpleNamespace(reader=reader, native=native, service=self.broker._inventory_service,
                                           realm=self.broker.realm, writer=writer)
        self.fixture_memory = Memory(self.native_case)
        # Memory.proof is the InventoryService's recovered source contract.
        self.fixture_memory.proof = self.native_case.service.proof
        self.sync_native_position()
        generation = self.broker._inventory_generation
        if seed and self.name == 'early_item_use':
            self.stage = 'before_inventory_delivery'
            early = next(item for item in inventory.validate_kit_frame(generation.frame) if item.template_bits == 89)
            received_before = self.bot.inventory_received
            count = self.broker._item_use_session.accepted_count
            await self.barrier(0x0960, hb.uint(1, early.identifier) + hb.pb.encode_bytes(2, RAW0), label='EARLY_BEFORE_ADD_INVENTORY')
            self.record('early_before_delivery_refused_without_crash', not received_before and
                not self.broker.failure.is_set() and self.broker._item_use_session.accepted_count == count,
                uid=early.identifier, uid_source='owned generated kit; deliberately before wire delivery',
                inventory_received_at_send=received_before)
        self.stage = 'INVENTORY_DELIVERY'
        await self.api('AddInventory', self.broker.add_inventory, writer, restore_only=generation.mode != 'FIRST_GRANT')
        await self.api('PrepareItemEquipment', self.broker.prepare_item_equipment, writer,
                       policy=item_equipment_effect.POLICY, first_enable=True)
        await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'KIT_DELIVERY')
        await self.bot.alive()
        if self.name in ('companion_full', 'mage_login'):
            records = [record for record in self.manager.records.values()
                       if record.owner_character_id == self.bot.self_uid]
            if self.member_id is None and records:
                self.member_id = min(r.character_id for r in records)
        self.record('normal_login_select_world', bool(self.bot.selected and self.bot.inventory_received),
                    character=self.bot.character, uid=self.bot.self_uid, map_id=self.bot.map_id)

    def initialize_hunt_fixture(self):
        """Fresh pre-login knight through the existing pure growth policy."""
        import random
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        data = load_m1()
        owner = next(row for row in self.broker.realm.store._read()['characters'] if row['class'] == 1)
        stats = owner['attributes']
        level = 18 if self.name == 'dungeon_items' else 7 if self.name == 'quit_saved_map' else 6
        exp = data.pc_exp[level - 1]
        baseline = actor_hook.profiles()[0].fields
        profile = PcProfile(1, owner['class'], owner['gender'], stats[0], stats[1],
                            con=stats[2], wis=stats[3])
        growth = on_kill(RewardPcState(0, profile, baseline[11], baseline[13]),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x4f574e52), data=data)
        self.broker._world_progress.commit(owner['uid'], Progress(exp, level, growth.max_hp, growth.max_mp))
        self.fixture_notes.append(dict(pre_login_level=level, pre_login_exp=exp,
            pre_login_max_hp=growth.max_hp, pre_login_max_mp=growth.max_mp,
            reason='existing owner danger ceiling admits the scenario maps and their overlapping aggressive spawn groups',
            formula='LOCAL world_reward.on_kill pure growth; same saved knight attributes and baseline'))
        if self.name == 'dungeon_items':
            self.fixture_notes.append(dict(navigation_budget_seconds=self.args.navigation_timeout,
                basis='current S32 static shortest path from32693,32833 to map1 stair32737,32877 is414 steps; original walk interval needs about five minutes plus ordinary NPC combat/potions',
                policy='CLI navigation budget only; unchanged movement speed, occupancy, attack admission and15-second movement stall check'))

    async def close(self):
        # Preserve error/last action before Quit can replace it.
        if self.broker is not None:
            self.epochs.append(dict(epoch=self.epoch_number, before_quit=self.broker.report(),
                                    errors=self.error_codes(), last_request=safe(getattr(self, 'last_request', None))))
        errors = []
        if self.bot is not None:
            try:
                if self.bot.selected and self.bot.peer.error is None and not self.broker.failure.is_set():
                    await self.bot.quit_selected()
            except Exception as error:
                errors.append(f'QUIT: {type(error).__name__}: {error}')
            finally:
                for peer in self.bot.peers:
                    await peer.close()
                self.bot = None
                # Let the owned socket handlers consume normal EOF before
                # broker.close stops the policy. Closing both concurrently
                # manufactures SESSION_STOPPED during otherwise normal Quit.
                tasks = tuple(self.broker._tasks) if self.broker is not None else ()
                if tasks:
                    await asyncio.wait(tasks, timeout=self.args.timeout)
        if self.broker is not None:
            broker, self.broker = self.broker, None
            try:
                closed = await broker.close()
                self.epochs[-1]['closed'] = closed
                self.cleanup_ok &= bool(closed.get('cleanup_complete'))
                if not self.cleanup_ok:
                    errors.append('OWNED_BROKER_CLEANUP_INCOMPLETE')
            except Exception as error:
                self.cleanup_ok = False
                errors.append(f'CLOSE: {type(error).__name__}: {error}')
        reader = getattr(self, 'fixture_reader', None)
        if reader is not None:
            reader.close()
            self.fixture_reader = None
        if errors:
            self.failures.extend(errors)
            self.checks.append(dict(check='cleanup', status='FAIL', errors=errors))
        return not errors

    def item(self, template):
        choices = [(uid, row) for uid, row in self.bot.inventory.items()
                   if row.get(2, -1) & 0xffffffff == template and row.get(4, 0) > 0]
        if not choices:
            raise hb.BotFailure(f'RECEIVED_OWNED_ITEM_{template}_UNAVAILABLE')
        return min(choices)

    async def barrier(self, opcode, payload=b'', label=None):
        return await self.bot.peer.request(opcode, payload, alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label=label)

    async def use(self, template, *, target=None, item_uid=None):
        # Ordinary repeated use stays inside the existing 64-frame/sec budget;
        # the spam scenario separately exercises rapid mixed requests.
        await asyncio.sleep(.2)
        uid, row = self.item(template) if item_uid is None else (item_uid, self.bot.inventory[item_uid])
        if row.get(2) != template or row.get(4, 0) <= 0:
            raise hb.BotFailure('OWNED_EXPLICIT_USE_UID_TEMPLATE_REQUIRED')
        quantity = row[4]
        params = RAW0 if target is None else b''.join(hb.uint(n, v) for n, v in
            ((1, 1), (2, target), (3, 0), (15, 0), (16, 0)))
        batch = await self.barrier(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
                                   label=f'USE_{template}' + ('' if target is None else '_TARGETED'))
        self.record(f'use_{template}_quantity', self.bot.inventory.get(uid, {}).get(4, 0) == quantity - 1,
                    uid=uid, before=quantity, after=self.bot.inventory.get(uid, {}).get(4, 0),
                    errors=self.error_codes())
        return batch

    async def gear(self, templates=(89, 104, 128, 129, 41, 3, 117)):
        self.stage = 'equipment_0960'
        if getattr(self.broker, '_item_use_session', None) is None:
            self.missing('Native equipment0960 requires InventoryService/RetainedSceneReader and completed original inventory delivery; socket-only hs.build_epoch does not supply these. Saved-combat fixture is not equipment intent validation.')
            return False
        for template in templates:
            uid, _ = self.item(template)
            before = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
            await self.barrier(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, RAW0), label=f'EQUIP_{template}')
            after = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
            self.record(f'equipment_{template}_persisted_toggle', before != after,
                        before=dataclasses.asdict(before), after=dataclasses.asdict(after))
        return True

    async def one_move(self):
        start = self.bot.position
        for heading, (dx, dy) in enumerate(hb.DELTAS):
            goal = start[0] + dx, start[1] + dy
            if self.travel_heading(goal, 0) == heading:
                await self.navigate(goal)
                self.record('move_after_action', self.bot.position != start, start=start, finish=self.bot.position)
                return
        raise hs.Unconfirmed('NO_PASSABLE_ADJACENT_CELL_OBSERVED')

    async def attack_once(self):
        """Observe a real own swing; an Alive alone never establishes attack."""
        bot, before = self.bot, self.bot.swings
        until = time.monotonic() + self.args.hunt_timeout
        while bot.swings == before:
            if bot.dead:
                raise hb.BotFailure('OWNER_DIED_BEFORE_ATTACK_OBSERVATION')
            if time.monotonic() >= until:
                raise hs.Unconfirmed('OWN_ATTACK_OBSERVATION_DEADLINE')
            targets = [(uid, row) for uid, row in bot.actors.items() if row['alive'] and
                       bot.hunt_target(row)]
            target = next((pair for pair in sorted(targets,
                key=lambda p: hb.distance(bot.position, p[1]['position']))
                if self.reachable_hunt_goal(pair[1]['position'], 1)), None)
            if target is not None:
                uid, row = target
                if hb.distance(bot.position, row['position']) <= 1:
                    await bot.attack(uid)
                else:
                    await bot.step(row['position'], radius=1)
            else:
                goal = self.hunt_waypoint()
                if goal is not None:
                    await bot.step(goal, radius=1)
                else:
                    await bot.alive()
            if bot.hp < bot.max_hp*.5:
                await self.use(14)
            if time.monotonic()-bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.03)
        self.record('real_own_attack_after_action', bot.swings > before, swings=bot.swings-before)

    def hunt_waypoint(self):
        bot = self.bot
        groups = [g for g in bot.data.spawns if g.map_id == bot.map_id and
                  bot.data.monsters[g.template_id].level <= (bot.level or 1) + 3]
        if not groups:
            raise MissingFeature(f'No level-appropriate product spawn data on map{bot.map_id}')
        goals = [point for g in groups
                 if bot.safe_hunt_cell(point := ((g.rect.x1 + g.rect.x2)//2,
                                                (g.rect.y1 + g.rect.y2)//2))]
        near = False
        for goal in sorted(goals, key=lambda p: hb.distance(bot.position, p)):
            if hb.distance(bot.position, goal) <= 1:
                near = True
            elif self.reachable_hunt_goal(goal, 1):
                return goal
        if near:
            return None  # Wait for ordinary spawn/tick frames within the existing deadline.
        raise hb.BotFailure('NO_REACHABLE_SAFE_CURRENT_MAP_HUNT_GROUP')

    async def hunt_count(self, *, kills=1, pickups=0, seconds=None):
        bot, until = self.bot, time.monotonic() + (seconds or self.args.hunt_timeout)
        before_kills, before_pickups = len(bot.kills), bot.pickups
        while len(bot.kills) - before_kills < kills or bot.pickups - before_pickups < pickups:
            if time.monotonic() >= until:
                raise hs.Unconfirmed(f'HUNT_OBSERVATION_DEADLINE kills={len(bot.kills)-before_kills} pickups={bot.pickups-before_pickups}')
            if bot.dead:
                raise hb.BotFailure('OWNER_DIED_DURING_HUNT')
            if bot.hp < bot.max_hp * .6:
                await self.use(14)
            loot = [(uid, row) for uid, row in bot.ground.items()
                    if bot.pickup_refused[uid] < 3 and bot.safe_hunt_cell(row['position'])]
            pickup = next((pair for pair in sorted(loot,
                key=lambda p: hb.distance(bot.position, p[1]['position']))
                if self.reachable_hunt_goal(pair[1]['position'], 1)), None)
            if pickup is not None:
                uid, row = pickup
                if hb.distance(bot.position, row['position']) <= 1:
                    await bot.pickup(uid)
                else:
                    await bot.step(row['position'], radius=1)
            else:
                targets = [(uid, row) for uid, row in bot.actors.items() if bot.hunt_target(row)]
                target = next((pair for pair in sorted(targets,
                    key=lambda p: hb.distance(bot.position, p[1]['position']))
                    if self.reachable_hunt_goal(pair[1]['position'], 1)), None)
                if target is not None:
                    uid, row = target
                    if hb.distance(bot.position, row['position']) > 1:
                        await bot.step(row['position'], radius=1)
                    else:
                        await bot.attack(uid)
                else:
                    goal = self.hunt_waypoint()
                    if goal is not None:
                        await bot.step(goal, radius=1)
                    else:
                        await bot.alive()
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.03)
        self.record('hunt_and_pickup', len(bot.kills)-before_kills >= kills and bot.pickups-before_pickups >= pickups,
                    kills=len(bot.kills)-before_kills, pickups=bot.pickups-before_pickups)

    async def equip_all(self):
        all_gear = tuple(row[2] for row in self.bot.inventory.values()
                         if self.bot.data.items.get(row.get(2)) is not None
                         and self.bot.data.items[row[2]].kind in ('weapon', 'armor')
                         and 1 in self.bot.data.items[row[2]].classes)
        for order in (all_gear, all_gear, (89, 104, 128, 129, 98, 109, 41, 3, 117),
                      (117, 6, 4, 12, 11, 230, 41, 3),
                      (129, 128, 104, 89, 3, 41, 3, 117)):
            await self.gear(order)

    async def potions_after_pickup(self):
        await self.hunt_count(kills=3, pickups=3)
        for template in (14, 17, 296):
            self.stage = f'drain_potion_{template}'
            while any(row.get(2) == template and row.get(4, 0) > 0 for row in self.bot.inventory.values()):
                await self.use(template)
            self.record(f'potion_{template}_last_unit_removed', not any(
                row.get(2) == template and row.get(4, 0) > 0 for row in self.bot.inventory.values()))
        await self.gear()

    async def window(self, npc, action, opcode):
        await self.bot.peer.request(0x4e43, hb.uint(1, npc),
            check=lambda batch: hb.find(batch, 0x4e44), label='NPC_CLICK')
        payload = hb.uint(1, npc) + hb.pb.encode_bytes(2, action.encode()) + hb.uint(4, 0) + hb.uint(5, 0)
        batch = await self.bot.peer.request(0x4ed4, payload,
            check=lambda batch: hb.find(batch, opcode), label='NPC_ACTION_' + action)
        return hb.find(batch, opcode).values

    async def trade(self, context, mode, key, count):
        payload = (hb.uint(1, context) + hb.uint(2, mode)
            + hb.pb.encode_bytes(3, hb.uint(1, key) + hb.uint(2, count)) + hb.uint(4, 0) + hb.uint(5, 0))
        return await self.barrier(0x4ed1, payload, label='TRADE')

    async def shop_sell_anchor(self):
        sources = self.broker._world_handler_bindings.sources
        town = self.broker._world.town
        anchor = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid)).item_uid
        template = self.bot.inventory[anchor][2]
        buyer_ids = {offer.key[0] for offer in town.data.shops.offers.values()
                     if offer.classic_item_id == template and offer.calculable and offer.purchasing_price >= 0}
        candidates = [(self.broker._world.entities.resolve(ref), sources.get(npc.key))
                      for ref, npc, _ in town._owned.values() if npc.spawn['mapid'] == 0 and npc.npc_id in buyer_ids]
        candidates = [(e, source) for e, source in candidates if e is not None]
        candidates = [(e, s) for e, s in candidates if s is not None and hasattr(s, 'actions') and 'buy' in s.actions]
        if not candidates:
            raise MissingFeature('No available current shop menu source')
        npc, _ = min(candidates, key=lambda pair: hb.distance(self.bot.position, (pair[0].x, pair[0].y)))
        await self.navigate((npc.x, npc.y), radius=2)
        self.record('shop_received_actor', npc.uid in self.bot.live_appearances)
        codec = self.broker._world_handler_bindings.wire.lists
        opened = await self.window(npc.uid, 'buy', codec.OPCODES[codec.BUY])
        rows = [hb.fields(raw) for raw in opened.get(3, ())]
        if not rows:
            raise MissingFeature('Current shop has no buy rows')
        row = rows[0]
        before = dict(self.bot.inventory)
        await self.trade(hb.scalar(opened, 1), 5, hb.scalar(row, 1) & 0xffffffff, 1)
        self.record('shop_purchase_inventory_changed', self.bot.inventory != before)
        anchor = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid)).item_uid
        if not await self.gear((3,)):
            self.missing('Anchor sale requires real unequip0960 before SELL; omitted to preserve equipped-item guard')
            await self.hunt_count()
            return
        opened = await self.window(npc.uid, 'sell', codec.OPCODES[codec.SELL])
        issued = [hb.fields(raw) for raw in opened.get(3, ())]
        row = next((row for row in issued if hb.scalar(row, 1) & 0xffffffff == anchor), None)
        self.record('anchor_listed_after_unequip', row is not None, anchor=anchor)
        await self.trade(hb.scalar(opened, 1), 6, anchor, 1)
        self.record('anchor_sold', anchor not in self.bot.inventory)
        await self.attack_once()
        await self.gear((41, 6))

    async def warehouse_roundtrip(self):
        npcs = [entity for entity in self.broker._world.town.present(0, *self.bot.position, 20)
                if entity.uid in self.bot.live_appearances and self.bot.live_appearances[entity.uid].get(3) == [143]]
        if not npcs:
            raise MissingFeature('Warehouse actor143 not delivered at fixture position')
        npc = npcs[0]
        await self.navigate((npc.x, npc.y), radius=2)
        uid, row = self.item(14)
        before = row[4]
        opened = await self.window(npc.uid, 'deposit', 0x4ed2)
        await self.trade(hb.scalar(opened, 4), 1, uid, 2)
        self.record('warehouse_deposit_debit', self.bot.inventory[uid][4] == before - 2)
        await self.barrier(0x097b, label='WAREHOUSE_CLOSE')
        opened = await self.window(npc.uid, 'retrieve', 0x0971)
        issued = [hb.fields(raw) for raw in opened.get(7, ())]
        if not issued:
            raise hs.Unconfirmed('WAREHOUSE_WITHDRAW_LIST_EMPTY_AFTER_DEPOSIT')
        await self.trade(hb.scalar(opened, 1), 2, hb.scalar(issued[0], 1), 2)
        self.record('warehouse_withdraw_credit', self.bot.inventory[uid][4] == before)
        await self.gear()
        await self.use(14)

    async def scrolls(self):
        await self.attack_once()
        cached = next((uid for uid, attacker in self.bot.last_attacker.items()
                       if attacker == self.bot.self_uid and uid != self.bot.self_uid), None)
        if cached is None:
            raise hs.Unconfirmed('PRE_SCROLL_RECEIVED_ATTACK_TARGET_REQUIRED')
        for _ in range(2):
            for template in (162, 23):
                self.stage = f'scroll_{template}'
                await self.use(template)
                batch = await self.barrier(0x4e30, hb.uint(1, cached), label='POST_SCROLL_CACHED_ATTACK')
                swing = hb.find(batch, 0x4e31, **{'2': self.bot.self_uid, '3': cached})
                self.record('post_scroll_attack_request_and_alive', not self.broker.failure.is_set(),
                    target=cached, uid_source='previously received target with actual initial own swing',
                    observed='OWN_SWING' if swing else 'NO_SWING',
                    scope='ordered real attack request after relocation; stale/out-of-range/cadence refusal is not an attack-effect PASS')
                await self.one_move()
                await self.use(14)

    async def enchant_poly(self):
        normal, cursed, safe_target, destruction_target, unsafe_targets = self.enchant_fixture
        seen = set()
        for scroll, target in ((normal, safe_target), (cursed, destruction_target)):
            await self.use(25, target=target, item_uid=scroll)
            seen.add(self.broker._world_enchant_results[-1]['status'])
        for target in unsafe_targets:
            await self.use(25, target=target, item_uid=normal)
            seen.add(self.broker._world_enchant_results[-1]['status'])
            if 'unchanged' in seen:
                break
        self.record('enchant_success_and_destruction', {'success', 'destroyed'} <= seen, outcomes=sorted(seen))
        if 'unchanged' not in seen:
            self.missing('Finite explicit +9 fixture supply did not produce the supported RNG unchanged branch; raw real outcomes preserved. No result/roll forced.')
        # Remove the actually worn weapon through its real 0960 toggle.
        worn = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid)).weapon_uid
        if worn:
            await self.gear((self.bot.inventory[worn][2],))
        batch = await self.use(299)
        self.record('poly_notification', hb.find(batch, 0x4e5c) is not None)
        await self.attack_once()
        await self.gear((41, 3))

    def initialize_enchant_fixture(self):
        """Explicit pre-login development starts, using the existing typed names.

        Product RNG is untouched. +9 permits the real unchanged branch; -7
        plus a cursed scroll exercises policy destruction. These added dagger
        instances are test supplies, never rewards or a user inventory edit.
        """
        from tools.local_original_session import inventory, world_enchant_inventory as enchant
        from tools.local_original_session import equipment_store
        frame = self.broker._inventory_kit_frame(1)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        by_template = {row[2]: row for row in rows if row[2] not in (25, 26)}
        scrolls = [item for item in inventory.validate_kit_frame(frame) if item.template_bits == 25]
        normal = next(item.identifier for item in scrolls if enchant.scroll_grade(item) == 1)
        cursed = next(item.identifier for item in scrolls if enchant.scroll_grade(item) == 2)
        next_uid = max(row[1] for row in rows)+1
        targets = []
        for index in range(30):
            row = dict(by_template[41])
            row.update({1: next_uid+index, 18: enchant.enchanted_name(self.broker._world.data.items[41], 9)})
            targets.append(row[1])
            rows.append(row)
        for row in rows:
            if row[1] == normal:
                row[4] = 40
            if row[1] == by_template[4][1]:
                row[18] = enchant.enchanted_name(self.broker._world.data.items[4], -7)
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1, frame)
        data = self.broker._world.data
        equipped = [entry.template_id for entry in data.starter.entries(1, 'test_knight') if entry.equipped]
        self.equipment.initialize_kit(1, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=by_template[3][1], slots=tuple((data.items[t].slot_key, by_template[t][1])
                for t in equipped if data.items[t].kind == 'armor'))
        self.enchant_fixture = normal, cursed, by_template[3][1], by_template[4][1], targets
        self.fixture_notes.append(dict(pre_login_enchant_target_levels=[9]*30+[-7],
            ordinary_scroll_count=40, fixture_only=True, rng='unchanged product RNG'))

    async def dungeon_items(self):
        await self.navigate((32478, 32851), predicate=lambda: self.bot.map_id == 1)
        self.record('dungeon_map1', self.bot.map_id == 1)
        await self.use(14)
        await self.gear()
        await self.hunt_count(pickups=1)
        await self.navigate((32737, 32877), predicate=lambda: self.bot.map_id == 2)
        self.record('dungeon_map2', self.bot.map_id == 2)
        await self.use(17)
        await self.gear((41, 3))
        await self.hunt_count(pickups=1)
        await self.use(162)
        self.record('dungeon_return_map0', self.bot.map_id == 0)

    async def gludin_items(self):
        self.record('gludin_map4', self.bot.map_id == 4)
        await self.use(14)
        await self.one_move()
        await self.hunt_count(pickups=1)
        await self.use(162)
        self.record('gludin_return_map4', self.bot.map_id == 4)
        for destination in (0, 4):
            route = next(r for r in self.broker._world_gludin.boats if r.source_map == self.bot.map_id)
            try:
                ticket_uid, ticket = self.item(route.ticket_id)
            except hb.BotFailure:
                self.missing(f'Boat requires received ticket{route.ticket_id}; current fresh fixture has no owned ticket. Boat roundtrip not run.')
                break
            ticket_count = ticket[4]
            terrain = self.broker._world.terrain
            dock_cells = [(x, y) for y in range(route.dock.y1, route.dock.y2 + 1)
                          for x in range(route.dock.x1, route.dock.x2 + 1)
                          if terrain.can_stand(self.bot.map_id, x, y) is True
                          and self.bot.safe_hunt_cell((x, y))]
            goal = next((point for point in sorted(dock_cells,
                key=lambda point: hb.distance(self.bot.position, point))
                if self.reachable_hunt_goal(point, 0)), None)
            if goal is None:
                raise hb.BotFailure('NO_REACHABLE_STANDABLE_CURRENT_DOCK_CELL')
            self.record('boat_dock_goal_' + str(destination), route.dock.contains(*goal),
                        goal=goal, source='current S32 standable cell inside the unchanged source dock box')
            await self.navigate(goal, radius=0)
            await self.barrier(0x4ef8, hb.uint(1, 0), label='BOAT_ENTER')
            self.record('boat_arrive_' + str(destination), self.bot.map_id == destination)
            from tools.local_original_session import inventory
            saved = inventory.validate_kit_frame(self.store.restore(self.bot.self_uid))
            saved_count = next((dict(item.raw_fields)[4] for item in saved if item.identifier == ticket_uid), 0)
            received_count = self.bot.inventory.get(ticket_uid, {}).get(4, 0)
            self.record('boat_ticket_consumed_saved_' + str(destination),
                received_count == saved_count == ticket_count - 1,
                ticket_template=route.ticket_id, ticket_uid=ticket_uid,
                before=ticket_count, received_after=received_count, saved_after=saved_count)
        await self.gear()

    def initialize_boat_fixture(self):
        """Explicit pre-login tickets; no purchase or natural acquisition claim."""
        from tools.local_original_session import inventory, equipment_store
        frame = self.broker._inventory_kit_frame(1)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        by_template = {row[2]: row for row in rows}
        data, supplies = self.broker._world.data, []
        next_uid = max(row[1] for row in rows) + 1
        for offset, template in enumerate((124, 125)):
            row = dict(rows[0])
            row.update({1: next_uid + offset, 2: template, 4: 1, 7: data.items[template].icon})
            rows.append(row)
            supplies.append(dict(template_id=template, uid=row[1], count=1))
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1, frame)
        equipped = [entry.template_id for entry in data.starter.entries(1, 'test_knight') if entry.equipped]
        self.equipment.initialize_kit(1, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=by_template[3][1], slots=tuple((data.items[t].slot_key, by_template[t][1])
                for t in equipped if data.items[t].kind == 'armor'))
        self.fixture_notes.append(dict(pre_login_boat_tickets=supplies,
            source='product item124/125 definitions; existing kit UID suffix and InventoryStore.grant',
            scope='fresh development supplies; no shop purchase or natural acquisition PASS'))

    async def restart_dead(self, dead_requests=False):
        bot = self.bot
        await self.receive_damage(lethal=True)
        self.record('natural_death', bot.hp_zero and bot.own_death_frame and bot.incoming_swings > 0)
        if dead_requests:
            before = {uid: row.copy() for uid, row in bot.inventory.items()}
            uid, _ = self.item(14)
            swings = bot.swings
            await self.barrier(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, RAW0), label='DEAD_ITEM')
            target = next(iter(bot.actors), bot.self_uid)
            await self.barrier(0x4e30, hb.uint(1, target), label='DEAD_ATTACK')
            self.record('dead_item_attack_no_effect', bot.inventory == before and bot.swings == swings)
        await bot.peer.request(0x4eec, check=lambda batch: hb.find(batch, 0x4e3b, **{'1': 1}), label='DEAD_RESTART')
        await bot.reselect()
        await self.restore_selected_delivery()
        self.record('dead_restart_reselect_alive', not bot.dead and bot.hp > 0)
        await self.use(14)
        await self.gear()
        await self.one_move()
        await self.hunt_count()

    async def restore_selected_delivery(self):
        """Normal fresh generation after successful Restart/reselect."""
        from types import SimpleNamespace
        from tools.local_original_session.inventory_tests import Memory
        from tools.local_original_session import item_equipment_effect
        writer = next(writer for writer, uid in self.broker._world_pcs.values() if uid == self.bot.self_uid)
        self.native_case = SimpleNamespace(reader=self.fixture_reader, native=self.fixture_reader.backend,
            service=self.broker._inventory_service, realm=self.broker.realm, writer=writer)
        self.fixture_memory = Memory(self.native_case)
        self.sync_native_position()
        marker = self.bot.peer.ordinal
        await self.api('AddInventory', self.broker.add_inventory, writer, restore_only=True)
        await self.api('PrepareItemEquipment', self.broker.prepare_item_equipment, writer,
                       policy=item_equipment_effect.POLICY, first_enable=True)
        await self.bot.peer.wait(marker, lambda batch: hb.find(batch, 0x0964), 'RESELECT_KIT_DELIVERY')
        await self.bot.alive()

    async def dungeon_death_restart(self):
        await self.navigate((32478, 32851), predicate=lambda: self.bot.map_id == 1)
        await self.restart_dead()

    async def field_death_restart(self):
        await self.restart_dead(dead_requests=True)

    async def quit_saved_map(self):
        root = self.directory
        for map_id in (4, 1):
            if map_id == 1:
                await self.close()
                self.directory = root / 'dungeon'
                self.directory.mkdir()
                self.map_start = (0, 32478, 32852)
                await self.open(seed=True)
                await self.navigate((32478, 32851), predicate=lambda: self.bot.map_id == 1)
            character = self.bot.character
            self.record('saved_map_before_quit_' + str(map_id), self.bot.map_id == map_id)
            await self.close()  # actual Quit ACK precedes every reconnect
            for map_exp in (2, 0):
                label = self.stage = f'saved_map{map_id}_MapExp{map_exp}'
                with environment(SL_EXPERIMENT_MAP=map_exp):
                    try:
                        await self.open(seed=False, character=character)
                        self.record(label + '_selection', self.bot.map_id == (map_id if map_exp else 0),
                                    actual_map=self.bot.map_id)
                        await self.one_move()
                        await self.use(14)
                        await self.attack_once()
                    except Exception as error:
                        stack = traceback.extract_tb(error.__traceback__)
                        origin = stack[-2] if len(stack)>1 and stack[-1].name in ('need', '_need') else stack[-1]
                        detail = dict(check=label, status='FAIL', error=f'{type(error).__name__}: {error}',
                            request=safe(getattr(self, 'last_request', None)),
                            origin=dict(file=origin.filename, line=origin.lineno, function=origin.name),
                            traceback=traceback.format_exc())
                        self.checks.append(detail)
                        self.failures.append(detail['error'])
                    finally:
                        await self.close()

    async def companion_full(self):
        await self.summon()
        await self.command(4)
        for template, count in ((230, 1), (102, 1), (14, 5), (492, 2)):
            uid, row = self.item(template)
            before = row[4]
            await self.barrier(0x4ef5, hb.uint(1, self.actor.ref.uid) + hb.uint(2, uid) + hb.uint(3, count), label='COMPANION_GIVE_' + str(template))
            self.record('companion_give_' + str(template), self.bot.inventory.get(uid, {}).get(4, 0) == before - count)
        anchor = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid)).item_uid
        if await self.gear((3,)):
            await self.barrier(0x4ef5, hb.uint(1, self.actor.ref.uid) + hb.uint(2, anchor) + hb.uint(3, 1), label='COMPANION_GIVE_ANCHOR')
            self.record('owner_anchor_transfer_remaining_row', self.bot.inventory.get(anchor, {}).get(4, 0) == 0)
        await self.command(2)
        await self.hunt_count()
        await self.combat_death()
        await self.teleport_scroll(23)
        await self.revive_brief()
        await self.resummon()
        before = dataclasses.asdict(self.member)
        owner = self.bot.character
        await self.close()
        await self.open(seed=False, character=owner)
        await self.summon()
        self.record('companion_saved_record_restored', all(dataclasses.asdict(self.member)[key] == before[key]
                    for key in hc.PERSISTENT_FIELDS if key not in ('hp', 'mp')))

    async def revive_brief(self):
        await self.revive()

    async def mage_login(self):
        await self.summon()
        owner = self.bot.character
        await self.close()
        await self.open(seed=False, character='SoloMage')
        self.record('mage_real_selected_class', self.broker._world.combat.pcs[self.bot.self_uid].profile.character_class == 3)
        await self.gear((41, 41, 103, 103))
        await self.use(14)
        await self.one_move()
        await self.attack_once()
        await self.close()
        await self.open(seed=False, character=owner)
        self.record('knight_reselected_after_mage', self.bot.character == owner)

    async def early_item_use(self):
        # The actual early send is in open(), immediately before AddInventory.
        await self.gear((89, 104))

    async def spam(self):
        self.stage = 'spam_prepare'
        await self.attack_once()
        cached = next((uid for uid, attacker in self.bot.last_attacker.items()
                       if attacker == self.bot.self_uid and uid != self.bot.self_uid), None)
        if cached is None:
            raise hs.Unconfirmed('SPAM_PREVIOUSLY_RECEIVED_ATTACK_TARGET_REQUIRED')
        self.stage = 'spam'
        start = time.monotonic()
        actions = Counter()
        while time.monotonic() - start < self.args.spam_seconds:
            if self.bot.dead:
                raise hb.BotFailure('OWNER_DIED_DURING_SPAM')
            heading = int((time.monotonic() - start) * 10) % 8
            before = self.bot.position
            payload = hb.uint(1, hb.pack(self.bot.position)) + hb.uint(2, heading)
            batch = await self.barrier(0x4e2b, payload, label='SPAM_MOVE')
            if hb.find(batch, 0x4ee0) is None:
                dx, dy = hb.DELTAS[heading]
                self.bot.position = before[0]+dx, before[1]+dy
            actions['move'] += 1
            targets = [(uid, row) for uid, row in self.bot.actors.items() if row['alive']]
            target = min(targets, key=lambda p: hb.distance(self.bot.position, p[1]['position']))[0] if targets else cached
            if target is not None:
                await self.barrier(0x4e30, hb.uint(1, target), label='SPAM_ATTACK')
                actions['attack'] += 1
            if self.bot.hp < self.bot.max_hp*.65:
                await self.use(14)
            elif actions['move'] % 20 == 0:
                template = 17 if actions['move'] % 40 == 0 else 296
                await self.use(template)
            else:
                await self.gear((89,))
            actions['item'] += 1
            await asyncio.sleep(.12)
        self.record('spam_real_duration_and_requests', time.monotonic()-start >= self.args.spam_seconds and
            all(actions[k] > 0 for k in ('move', 'attack', 'item')), elapsed=time.monotonic()-start, actions=actions)
        await self.gear((89, 104, 128, 129))

    async def run_matrix(self):
        started = time.monotonic()
        failure = None
        failure_origin = None
        try:
            await self.open(seed=True, deliver=self.name != 'quit_saved_map')
            await getattr(self, self.name)()
        except MissingFeature as error:
            self.missing(str(error))
        except Exception as error:
            failure = f'{type(error).__name__}: {error}'
            trace = traceback.extract_tb(error.__traceback__)
            frame = trace[-2] if len(trace) >= 2 and trace[-1].name in ('need', '_need') else trace[-1]
            failure_origin = dict(file=frame.filename, line=frame.lineno, function=frame.name)
            self.failures.append(failure)
            self.checks.append(dict(check=self.stage, status='FAIL', error=failure,
                origin='harness' if isinstance(error, (AttributeError, TypeError, NameError, KeyError)) else 'observation',
                request=safe(self.first_failed_request or getattr(self, 'last_request', None)),
                traceback=traceback.format_exc(), errors=self.error_codes()))
        finally:
            await self.close()
        broker_codes = [epoch.get('before_quit', {}).get('failure_code') for epoch in self.epochs]
        status = 'FAIL' if self.failures or self.server_failures or any(broker_codes) else 'SKIP' if self.gaps else 'PASS'
        result = dict(scenario=self.name, status=status, elapsed_seconds=round(time.monotonic()-started, 3),
            scope='real loopback broker decoder/router packets; no native input/screen equivalence',
            directory=str(self.directory), failure=failure, gaps=self.gaps, failures=self.failures,
            failure_origin=failure_origin or next((c.get('origin') for c in self.checks if isinstance(c.get('origin'), dict)), None),
            first_failed_request=self.first_failed_request, server_failures=self.server_failures,
            checks=self.checks, fixture_notes=self.fixture_notes, epochs=self.epochs,
            cleanup_complete=self.cleanup_ok, requests=len(self.requests),
            source_sha256=dict(SOURCE_SHA256),
            bots=[dict(character=getattr(bot, 'character', None), map_id=bot.map_id, hp=bot.hp,
                dead=bot.dead, kills=len(bot.kills), pickups=bot.pickups, moves=bot.moves,
                swings=bot.swings, request_counts=dict(bot.request_counts), failures=dict(bot.request_failures)) for bot in self.bots])
        (self.result_directory / 'result.json').write_text(json.dumps(safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
        return result


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--scenario', choices=(*NAMES, 'all'), default='all')
    result.add_argument('--timeout', type=hb.positive, default=8)
    result.add_argument('--navigation-timeout', type=hb.positive, default=180)
    result.add_argument('--death-timeout', type=hb.positive, default=180)
    result.add_argument('--hunt-timeout', type=hb.positive, default=180)
    result.add_argument('--spam-seconds', type=hb.positive, default=120,
                        help='default 120; shorter value is explicitly reduced development scope')
    result.add_argument('--minutes', type=hb.positive, default=3)
    result.add_argument('--potion-threshold', type=hb.positive, default=.5)
    result.set_defaults(fixture_level=6, companion_revive_exp=False)
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-play-matrix-', dir=root))
    names = NAMES if args.scenario == 'all' else (args.scenario,)
    results = []
    for name in names:
        profile = directory / name
        profile.mkdir()
        scenario = Matrix(args, name, profile)
        map_exp = name in ('dungeon_items', 'gludin_items', 'dungeon_death_restart', 'field_death_restart', 'quit_saved_map')
        if name in ('dungeon_items', 'dungeon_death_restart'):
            scenario.map_start = (0, 32478, 32852)
        elif name in ('gludin_items', 'quit_saved_map'):
            scenario.map_start = (4, 32608, 32734)
        elif name == 'warehouse_roundtrip':
            scenario.map_start = (0, 32577, 32946)
        elif name == 'shop_sell_anchor':
            scenario.map_start = (0, 32644, 32951)  # current template3 buyback merchant70014 vicinity
        companion = name in ('companion_full', 'mage_login')
        with environment(SL_EXPERIMENT_MAP=2 if map_exp else 0,
                SL_EXPERIMENT_SHOP=1, SL_EXPERIMENT_WAREHOUSE=1,
                SL_EXPERIMENT_ENCHANT=0, SL_EXPERIMENT_POLY='orc',
                SL_COMPANION=int(companion), SL_COMPANION_PET_UI=int(companion),
                SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
            print('START ' + name, flush=True)
            result = await scenario.run_matrix()
        results.append(result)
        print(f"{result['status']:4} {name}: {result['elapsed_seconds']}s requests={result['requests']} "
              f"gaps={len(result['gaps'])} failures={len(result['failures'])}", flush=True)
        # Do not reuse a listener whose owner did not close. Record every
        # remaining scenario explicitly instead of silently truncating all.
        if not result['cleanup_complete']:
            for remaining in names[len(results):]:
                results.append(dict(scenario=remaining, status='FAIL', requests=0,
                    failure='NOT_RUN_PREVIOUS_OWNED_BROKER_CLEANUP_INCOMPLETE', cleanup_complete=False))
            break
    summary = dict(output_directory=str(directory), scope='packet matrix only',
        fixture='fresh test_knight with documented per-scenario pre-login supplies; LOCAL source-backed native identity/RAM adapter; no user save or active HP/RNG/clock manipulation',
        counts=dict(Counter(r['status'] for r in results)), results=results)
    (directory / 'summary.json').write_text(json.dumps(safe(summary), ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nSCENARIO                 STATUS  REQUESTS  REQUEST / NEED / ORIGIN')
    for row in results:
        failures = row.get('server_failures', ())
        detail = failures[0] if failures else None
        if detail:
            request = detail.get('request') or {}
            stack = detail.get('traceback', ())
            # The need() implementation is shared; the immediately preceding
            # caller is the actual guard origin useful to the server writer.
            origin = stack[-2] if len(stack) >= 2 else stack[-1] if stack else {}
            reason = f"{request.get('opcode', '?')} {detail['code']} {Path(origin.get('file', '?')).name}:{origin.get('line', '?')}"
        elif row['status'] == 'FAIL':
            request = row.get('first_failed_request') or next((c.get('request') for c in reversed(row.get('checks', ())) if c.get('request')), {}) or {}
            origin = row.get('failure_origin') or {}
            reason = f"{request.get('opcode', '?')} {row.get('failure') or row.get('failures')} {Path(origin.get('file', '?')).name}:{origin.get('line', '?')}"
        elif row['status'] == 'SKIP':
            reason = '; '.join(row.get('gaps', ()))
        else:
            reason = '-'
        print(f"{row['scenario']:25} {row['status']:6} {row.get('requests', 0):8}  {reason}")
    print('OUTPUT_DIRECTORY=' + str(directory), flush=True)
    print('COUNTS=' + json.dumps(summary['counts']), flush=True)
    return summary


def main(argv=None):
    args = parser().parse_args(argv)
    result = asyncio.run(run(args))
    return 1 if any(row['status'] == 'FAIL' for row in result['results']) else 0


if __name__ == '__main__':
    raise SystemExit(main())

