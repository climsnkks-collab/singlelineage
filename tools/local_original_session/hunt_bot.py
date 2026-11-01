"""Socket-only M1 hunting regression client for an already running -World broker.

Example (SL_EXPECTED_UUID must be the launcher's actual --expected-uuid)::

    python -B -m tools.local_original_session.hunt_bot --minutes 3

Use a fresh, owned packet-test PersistentBroker with no attached game client.
The broker must admit this socket owner: normal native-client owner checks may
reject a Python process. This client neither changes those checks nor starts a
broker, game, listener, profile or timer. It uses the FIRST bootstrap/close and
second active connection on 12000 (14030 is the other broker endpoint).
--skip-first-bootstrap is only for a server whose FIRST connection already
closed normally; it does not make an occupied/third connection admissible.

Wire references: broker_tests.c2s/version_request; world_spawn_tests
BrokerWorldTests.bootstrap/selected; world_ai_tests BrokerCombatTests and
BrokerLifeTests; movement.correction_frame; item_equipment_effect._kit_params_raw0
and _consume_potion. Only the pure protobuf module is imported here: importing
the broker, session or test fixtures would pull in native/source-pin loaders.
Results describe received socket frames, not native input/rendering equivalence
or verified reward/storage behavior. There is deliberately no PASS label.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
import heapq
import ipaddress
import json
import math
import os
import statistics
import struct
import time
import uuid

from tools.local_entry_server import protobuf as pb


KEY12 = b'\x0c\0\x20\x4e\x08\0\x10\0\x18\x01\0\0'
DELTAS = ((0, -1), (1, -1), (1, 0), (1, 1),
          (0, 1), (-1, 1), (-1, 0), (-1, -1))
# These frames carry the protobuf fields actually consumed below. VERSION is
# intentionally opaque (the real response includes resource material).
DECODED = {0x0264, 0x4e21, 0x4e22, 0x4e29, 0x4e95, 0x4e96,
           0x4e38, 0x4e2c, 0x4ee0, 0x4e31, 0x4e39, 0x4e40,
           0x0964, 0x0965, 0x0978, 0x4e5b, 0x4eef, 0x4f57, 0x4f32, 0x4e2e}


class BotFailure(RuntimeError):
    pass


def c2s(opcode: int, payload: bytes = b'', sequence: int = 1) -> bytes:
    """Same plaintext/alignment layout as broker_tests.c2s, no test import."""
    size = ((10 + len(payload) + 1) & ~3) + 2
    return (struct.pack('<HIHH', size, sequence, opcode, len(payload))
            + payload + bytes(size - 10 - len(payload)))


def _varint(body: bytes, i: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if i >= len(body) or shift > 63:
            raise BotFailure('MALFORMED_VARINT')
        byte = body[i]
        i += 1
        value |= (byte & 0x7f) << shift
        shift += 7
        if byte < 0x80:
            return value, i


def fields(body: bytes) -> dict:
    """Flat protobuf fields -> {number: [values]}. Wire1 is read as a double
    (SC4E38 f26 EXP percent), which the pure entry-server parser does not admit."""
    result, i = defaultdict(list), 0
    while i < len(body):
        key, i = _varint(body, i)
        number, kind = key >> 3, key & 7
        if kind == 0:
            value, i = _varint(body, i)
        elif kind == 1:
            value = struct.unpack_from('<d', body, i)[0]
            i += 8
        elif kind == 2:
            size, i = _varint(body, i)
            value = bytes(body[i:i + size])
            i += size
        elif kind == 5:
            value = struct.unpack_from('<I', body, i)[0]
            i += 4
        else:
            raise BotFailure('UNSUPPORTED_WIRE_TYPE')
        if i > len(body):
            raise BotFailure('TRUNCATED_FIELD')
        result[number].append(value)
    return dict(result)


def scalar(value: dict, number: int, default=None):
    rows = value.get(number, ())
    return rows[-1] if rows else default


def relabel(name, count):
    """Client-like quantity suffix after a 0965 f4 change: 'base (Q)' for Q>1."""
    import re
    from tools.local_original_session.world_core_kit import display_name
    if type(name) is not bytes or not name:
        return name
    return display_name(re.sub(rb' \([0-9]+\)$', b'', name), count)


def displayed_rows(frame):
    """Saved kit rows as the server writes them: core 0964 display projection
    (stack suffix) plus the items feature's display fields (enchant f5=7)."""
    from tools.local_original_session import inventory, world_core_kit, world_feature_items

    class _Display:
        def fold_sync_hooks(self, name, value, *args):
            if name == 'inventory_display_fields':
                return world_feature_items._world_items_display_fields(self, value, *args)
            return value
    shown = world_core_kit.display_frame(_Display(), frame)
    return {item.identifier: dict(item.raw_fields) for item in inventory.validate_kit_frame(shown)}


def uint(number: int, value: int) -> bytes:
    return pb.encode_varint(number << 3) + pb.encode_varint(value)


def unpack(packed: int) -> tuple[int, int]:
    return packed & 65535, packed >> 16


def pack(point: tuple[int, int]) -> int:
    return point[0] | (point[1] << 16)


def distance(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


@dataclass
class Received:
    ordinal: int
    at: float
    opcode: int
    values: dict
    wire: bytes


def find(batch, opcode, **wanted):
    return next((frame for frame in batch if frame.opcode == opcode
                 and all(scalar(frame.values, int(key)) == value
                         for key, value in wanted.items())), None)


class Peer:
    """One socket reader; broadcasts update the view even between requests."""
    def __init__(self, bot, reader, writer):
        self.bot, self.reader, self.writer = bot, reader, writer
        self.frames = deque(maxlen=2048)
        self.ordinal = 0
        self.changed = asyncio.Event()
        self.error = None
        self.task = asyncio.create_task(self.pump())

    async def pump(self):
        try:
            while True:
                header = await self.reader.readexactly(2)
                size = int.from_bytes(header, 'little')
                if size < 6:
                    raise BotFailure('INVALID_SERVER_FRAME_LENGTH')
                wire = header + await self.reader.readexactly(size - 2)
                at = time.monotonic()
                opcode = int.from_bytes(wire[2:4], 'little')
                self.bot.frame_counts[f'0x{opcode:04X}'] += 1
                values = fields(wire[4:-2]) if opcode in DECODED else {}
                self.ordinal += 1
                frame = Received(self.ordinal, at, opcode, values, wire)
                self.bot.apply(frame)
                self.frames.append(frame)
                self.changed.set()
        except asyncio.CancelledError:
            raise
        except asyncio.IncompleteReadError:
            self.error = 'SERVER_EOF'
        except Exception as error:
            self.error = f'READER_{type(error).__name__}: {str(error)[:160]}'
        finally:
            self.changed.set()

    async def wait(self, marker, check, label, timeout=None):
        until = time.monotonic() + (self.bot.args.timeout if timeout is None else timeout)
        while True:
            self.changed.clear()
            batch = [frame for frame in self.frames if frame.ordinal > marker]
            matched = check(batch)
            if matched is not None:
                return batch, matched
            if self.error:
                raise BotFailure(f'{label}: {self.error}')
            remaining = until - time.monotonic()
            if remaining <= 0:
                raise BotFailure(f'{label}: RESPONSE_TIMEOUT')
            try:
                await asyncio.wait_for(self.changed.wait(), remaining)
            except asyncio.TimeoutError:
                raise BotFailure(f'{label}: RESPONSE_TIMEOUT') from None

    async def request(self, opcode, payload=b'', *, check=None, alive=False, label=None):
        label = label or f'0x{opcode:04X}'
        marker, started = self.ordinal, time.monotonic()
        self.bot.request_counts[label] += 1
        self.writer.write(c2s(opcode, payload))
        if alive:
            # Same ordered processing barrier used by BrokerCombatTests.
            # It is a liveness reply, never an attack/heal acknowledgement.
            self.writer.write(c2s(0x4e2a))
        try:
            await asyncio.wait_for(self.writer.drain(), self.bot.args.timeout)
            batch, matched = await self.wait(marker, check, label)
        except BaseException:
            self.bot.request_failures[label] += 1
            raise
        self.bot.latencies[label].append((matched.at - started) * 1000)
        return batch

    async def close(self):
        try:
            self.writer.close()
            await asyncio.wait_for(self.writer.wait_closed(), self.bot.args.timeout)
        except (OSError, asyncio.TimeoutError):
            pass
        finally:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


class HuntBot:
    def __init__(self, args):
        self.args = args
        self.frame_counts, self.request_counts, self.request_failures = Counter(), Counter(), Counter()
        self.latencies = defaultdict(list)
        self.peers = []
        self.peer = None
        self.roster, self.actors, self.inventory = {}, {}, {}
        self.inventory_received = False
        self.self_uid = self.position = self.map_id = self.sprite = None
        self.hp = self.max_hp = None
        self.dead = self.selected = False
        self.deaths, self.kills, self.last_attacker = set(), set(), {}
        self.potions_used = self.corrections = self.moves = self.swings = 0
        self.ground = {}  # world ground drops: uid -> position/count/graphic
        self.ground_seen = set()
        self.pickups = 0
        self.pickup_refused = Counter()
        self.level = self.exp_percent = None
        self.start_level = None
        self.blocked_edges = {}
        self.accepted_starts = deque(maxlen=16)  # (map, start), accepted wire steps only
        self.stalled_since = None
        self.attack_refused_since = self.attack_refused_uid = None
        self.next_move = self.next_attack = 0.0
        self.last_alive = 0.0
        self.speed = {0: 0, 1: 0}
        self.started = self.hunt_started = self.hunt_finished = None
        self.stop_reason = self.failure = self.cleanup_failure = None
        self.data = None

    def apply(self, frame):
        op, f = frame.opcode, frame.values
        if op == 0x4e22:
            reference = scalar(f, 1)
            if isinstance(reference, bytes):
                self.roster[reference.decode('utf-8', 'strict')] = f
        elif op == 0x4e95:
            self.map_id = scalar(f, 1)
        elif op == 0x4e38:
            uid = scalar(f, 1)
            if self.self_uid is None:
                self.self_uid = uid
            if uid == self.self_uid:
                self.hp, self.max_hp = scalar(f, 10), scalar(f, 11)
                self.level = scalar(f, 2, self.level)
                if self.start_level is None:
                    self.start_level = self.level
                self.exp_percent = scalar(f, 26, self.exp_percent)
                if self.hp == 0:
                    self.dead = True
        elif op == 0x4e96:
            uid, packed = scalar(f, 2), scalar(f, 1)
            if uid == self.self_uid:
                self.position, self.sprite = unpack(packed), scalar(f, 3)
            elif scalar(f, 16) == 0 and scalar(f, 7, 0) > 0:
                # Existing LOCAL world recipes: ground f7 is positive quantity;
                # MONSTER_BASE_FIELDS.f7 is zero, including monster template0.
                # A catalog name in f9 does not change a drop into a monster.
                self.ground[uid] = dict(position=unpack(packed), count=scalar(f, 7), graphic=scalar(f, 3))
                self.ground_seen.add(uid)
            elif (self.data is not None and scalar(f, 16) == 0
                  and scalar(f, 39) in self.data.monsters):
                self.actors[uid] = dict(position=unpack(packed), template=scalar(f, 39),
                                        alive=uid not in self.deaths)
        elif op == 0x4e2c:
            uid, packed, heading = scalar(f, 1), scalar(f, 2), scalar(f, 3)
            if uid in self.actors and isinstance(heading, int) and 0 <= heading < 8:
                # SC4E2C contains the PRE-step position, not the destination.
                x, y = unpack(packed)
                dx, dy = DELTAS[heading]
                self.actors[uid]['position'] = (x + dx, y + dy)
        elif op == 0x4ee0:
            self.position = (scalar(f, 1), scalar(f, 2))
            self.corrections += 1
        elif op == 0x4e31:
            actor, target = scalar(f, 2), scalar(f, 3)
            self.last_attacker[target] = actor
            if actor == self.self_uid:
                self.swings += 1
        elif op == 0x4e39 and scalar(f, 2) == 8:
            # SC_ACTION_NOTI also carries pickup selector15. Only DeathAction8
            # ends an actor's life; a pickup must not kill the owner or target.
            uid = scalar(f, 1)
            self.deaths.add(uid)
            if uid == self.self_uid:
                self.dead = True
            elif uid in self.actors:
                self.actors[uid]['alive'] = False
                # Death has no killer field. Count only tracked monsters whose
                # most recent observed attack came from this selected actor.
                if self.last_attacker.get(uid) == self.self_uid:
                    self.kills.add(uid)
        elif op == 0x4e40:
            self.actors.pop(scalar(f, 1), None)
            self.ground.pop(scalar(f, 1), None)
        elif op in (0x0964, 0x0965):
            self.inventory_received = True
            for raw in f.get(1, ()):
                child = fields(raw)
                uid = scalar(child, 1)
                old = self.inventory.setdefault(uid, {})
                old.update({key: scalar(child, key) for key in child})
                if op == 0x0965 and 4 in child and 18 not in child and 18 in old:
                    old[18] = relabel(old[18], old[4])  # native quantity suffix update
        elif op == 0x0978:
            self.inventory.pop(scalar(f, 1), None)
        elif op == 0x4e5b and scalar(f, 1) == self.self_uid:
            for raw in f.get(2, ()):
                entries = fields(raw)
                for nested in entries.get(1, ()):
                    pair = fields(nested)
                    key = scalar(pair, 1)
                    if key in self.speed:
                        self.speed[key] = scalar(pair, 2, 0)

    async def connect(self):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.args.host, self.args.port), self.args.timeout)
        peer = Peer(self, reader, writer)
        self.peers.append(peer)
        await peer.wait(0, lambda batch: next((f for f in batch if f.wire == KEY12), None), 'KEY12')
        version = b''.join(uint(n, v) for n, v in ((1, 52), (2, 949), (3, 1), (4, 26092901)))
        await peer.request(0x4e34, version, check=lambda batch: find(batch, 0x4e35))
        await peer.request(0x4f3d, check=lambda batch: next(
            (f for f in batch if f.wire == b'\x06\0\x3e\x4f\0\0'), None))
        return peer

    async def login(self):
        if not self.args.skip_first_bootstrap:
            first = await self.connect()
            await first.close()
            # Allow the existing server to consume EOF and finish FIRST/close.
            # No reconnect retry: a rejected claim is reported as the failure.
            await asyncio.sleep(.1)
        self.peer = await self.connect()
        address = int.from_bytes(ipaddress.IPv4Address(self.args.host).packed, 'little')
        payload = (uint(1, address) + pb.encode_bytes(2, b'standalone.local')
                   + pb.encode_bytes(3, self.args.expected_uuid.encode('ascii')))

        def roster_ready(batch):
            ack = find(batch, 0x0264, **{'1': 0})
            after = [] if ack is None else [f for f in batch if f.ordinal > ack.ordinal]
            number = find(after, 0x4e21)
            if number is None:
                return None
            count = scalar(number.values, 1)
            infos = [f for f in after if f.opcode == 0x4e22 and f.ordinal > number.ordinal]
            if not isinstance(count, int) or count > 3:
                raise BotFailure('INVALID_CHARACTER_COUNT')
            return (infos[count - 1] if count else number) if len(infos) >= count else None

        await self.peer.request(0x0263, payload, check=roster_ready)
        if not self.roster:
            raise BotFailure('NO_SAVED_CHARACTER: character creation is outside this client')
        name = self.args.character or next(iter(self.roster))
        if name not in self.roster:
            raise BotFailure('CHARACTER_REFERENCE_NOT_IN_RECEIVED_ROSTER')
        self.character = name
        payload = pb.encode_bytes(1, name.encode('utf-8')) + uint(2, 0) + uint(3, 0)

        def entered(batch):
            ack = find(batch, 0x4e29, **{'2': 3})
            if ack is None:
                return None
            map_frame = find([f for f in batch if f.ordinal > ack.ordinal], 0x4e95)
            if map_frame is None:
                return None
            status = find([f for f in batch if f.ordinal > map_frame.ordinal], 0x4e38)
            if status is None:
                return None
            return find([f for f in batch if f.ordinal > status.ordinal], 0x4e96,
                        **{'2': scalar(status.values, 1)})

        await self.peer.request(0x4e28, payload, check=entered)
        self.selected = True
        allowed_maps = (0, 1, 2) if os.environ.get('SL_EXPERIMENT_MAP') == '2' else (0,)
        if self.map_id not in allowed_maps or self.position is None or self.hp is None or not self.max_hp:
            raise BotFailure('MAP0_SELF_POSITION_AND_HP_REQUIRED')
        await self.alive()

    async def alive(self):
        await self.peer.request(0x4e2a, check=lambda batch: find(batch, 0x4f57))
        self.last_alive = time.monotonic()

    def interval(self, action):
        row = self.data.action_speed.pc.get(self.sprite)
        base = (row.walk_ms if action == 0 else row.attack_ms) if row is not None else (667 if action == 0 else 1000)
        return base / 1000 * 100 / (100 + self.speed[action]) + .05

    def heading(self, goal, radius):
        return self.route_heading(goal, radius)

    def route_heading(self, goal, radius, *, occupied=None, excluded=(),
                      ignore_actors=False, max_nodes=10000):
        """Plan a complete route; replan a blocked next step from current observations.

        Keep the detour between accepted steps instead of repeatedly choosing a
        locally closer cul-de-sac. A small moving-goal change may reuse the
        distant part of that detour; its final approach is planned afresh.
        Only living actors occupy movement cells, matching the LOCAL server's
        player-step fallback; corpse retention separately constrains spawning.
        When distant actors cut every route, a weighted complete route permits
        staging toward them. Occupied neighbouring cells remain impassable.
        """
        start, now = self.position, time.monotonic()
        terrain = getattr(self, 'terrain', None)
        occupied = (set() if ignore_actors else
                    {v['position'] for v in self.actors.values() if v['alive']}
                    if occupied is None else set(occupied))
        excluded = frozenset(excluded)
        key = (self.map_id, self.level, radius, excluded, ignore_actors)
        recent_costs = Counter()
        for recency, (map_id, point) in enumerate(self.accepted_starts, 1):
            if map_id == self.map_id:
                recent_costs[point] += recency

        def repeated_soft_reverse(dest):
            # A single retreat is allowed. Stop only an already observed
            # A->B->A->B cycle from taking another speculative B->A step.
            return list(self.accepted_starts)[-3:] == [
                (self.map_id, dest), (self.map_id, start), (self.map_id, dest)]

        cached = getattr(self, '_navigation_route', None)
        if cached is not None and cached[0] == key:
            old_goal, route, weighted = cached[1:]
            heading = route.get(start)
            if (heading is not None and
                    (old_goal == goal or (distance(old_goal, goal) <= 2 and distance(start, goal) > 4))):
                dx, dy = DELTAS[heading]
                dest = start[0] + dx, start[1] + dy
                if (dest not in occupied and self.safe_hunt_cell(dest)
                        and self.blocked_edges.get((start, heading), 0) <= now
                        and dest not in recent_costs
                        and not (weighted and repeated_soft_reverse(dest))):
                    return heading
        self._navigation_route = None
        heuristic = lambda point: max(0, distance(point, goal) - radius)
        # Prefer progress among equal A* scores; a flat open room should not
        # consume the whole search budget before taking its first packet step.
        for weighted in ((False, True) if occupied else (False,)):
            heap = [(heuristic(start), heuristic(start), 0, start)]
            costs, parents = {start: 0}, {}
            for _ in range(max_nodes):
                if not heap:
                    break
                _, _, cost, point = heapq.heappop(heap)
                if cost != costs[point]:
                    continue
                if distance(point, goal) <= radius:
                    route = {}
                    while point != start:
                        previous, heading = parents[point]
                        route[previous] = heading
                        point = previous
                    first = route.get(start)
                    if weighted and first is not None:
                        dx, dy = DELTAS[first]
                        if repeated_soft_reverse((start[0]+dx, start[1]+dy)):
                            return None
                    self._navigation_route = key, goal, route, weighted
                    return first
                for heading, (dx, dy) in enumerate(DELTAS):
                    dest = (point[0] + dx, point[1] + dy)
                    if (not all(0 <= word <= 65535 for word in dest)
                            or (dest in occupied and (not weighted or distance(start, dest) <= 1))
                            or (dest in excluded and dest != goal)
                            or not self.safe_hunt_cell(dest)
                            or (terrain is not None and terrain.can_step(self.map_id, *point, heading) is not True)
                            or self.blocked_edges.get((point, heading), 0) > now):
                        continue
                    new_cost = cost + 1 + (4 if dest in occupied else 0) + recent_costs[dest]
                    if new_cost >= costs.get(dest, math.inf):
                        continue
                    costs[dest] = new_cost
                    parents[dest] = point, heading
                    remaining = heuristic(dest)
                    heapq.heappush(heap, (new_cost + remaining, remaining, new_cost, dest))
        return None

    def safe_hunt_cell(self, point):
        """Avoid received strong actors' actual reach, allowing outward retreat."""
        if self.data is None:
            return True
        ceiling = (self.level or 1) + 3
        for actor in self.actors.values():
            monster = self.data.monsters[actor['template']]
            if not actor['alive'] or monster.level <= ceiling:
                continue
            reach = max(monster.attack_range,
                        monster.perception_range if monster.aggressive else 0) + 2
            if (distance(point, actor['position']) <= reach
                    and distance(point, actor['position']) <= distance(self.position, actor['position'])):
                return False
        return True

    async def retreat_threat(self):
        if self.safe_hunt_cell(self.position):
            return False
        threats = [actor['position'] for actor in self.actors.values() if actor['alive']
                   and self.data.monsters[actor['template']].level > (self.level or 1) + 3]
        choices = [(self.position[0] + dx, self.position[1] + dy) for dx, dy in DELTAS]
        choices.sort(key=lambda point: min(distance(point, threat) for threat in threats), reverse=True)
        for point in choices:
            if self.safe_hunt_cell(point) and self.heading(point, 0) is not None:
                await self.step(point, radius=0)
                return True
        await self.alive()
        return True

    def hunt_target(self, actor):
        return (actor['alive'] and self.data.monsters[actor['template']].level <= (self.level or 1) + 3
                and self.safe_hunt_cell(actor['position']))

    async def step(self, goal, radius=0):
        if distance(self.position, goal) <= radius:
            self.stalled_since = None
            return
        now = time.monotonic()
        if now < self.next_move:
            return
        heading = self.heading(goal, radius)
        if heading is None:
            self.stalled_since = self.stalled_since or now
        else:
            start = self.position
            start_map = self.map_id
            payload = uint(1, pack(start)) + uint(2, heading)
            batch = await self.peer.request(0x4e2b, payload, alive=True,
                check=lambda batch: find(batch, 0x4f57), label='0x4E2B_to_ALIVE_barrier')
            if find(batch, 0x4ee0) is not None:
                self.blocked_edges[(start, heading)] = now + 60
                self.stalled_since = self.stalled_since or now
            else:
                # Accepted movement deliberately has no self echo. The matching
                # ordered Alive and absence of 4EE0 permit this local prediction.
                dx, dy = DELTAS[heading]
                self.position = (start[0] + dx, start[1] + dy)
                self.accepted_starts.append((start_map, start))
                self.moves += 1
                self.stalled_since = None
                self.attack_refused_since = None
            self.next_move = now + self.interval(0)
            self.last_alive = time.monotonic()
        if self.stalled_since is not None and now - self.stalled_since >= 15:
            raise BotFailure('NAVIGATION_STALLED: no accepted step for 15 seconds')

    async def attack(self, uid):
        now = time.monotonic()
        if now < self.next_attack:
            return
        if self.attack_refused_uid != uid:
            self.attack_refused_uid, self.attack_refused_since = uid, None
        # AI can move/kill the target between selection and dispatch, and the
        # server can legitimately refuse an early swing. Alive closes this
        # ordered request batch; its latency is explicitly a processing barrier.
        batch = await self.peer.request(0x4e30, uint(1, uid), alive=True,
            check=lambda batch: find(batch, 0x4f57), label='0x4E30_to_ALIVE_barrier')
        swing = find(batch, 0x4e31, **{'1': 1, '2': self.self_uid, '3': uid})
        target = self.actors.get(uid)
        if (swing is not None or self.dead or target is None or not target['alive']
                or distance(self.position, target['position']) > 1):
            self.attack_refused_since = None
        else:
            self.attack_refused_since = self.attack_refused_since or now
            if time.monotonic() - self.attack_refused_since >= 15:
                raise BotFailure('ATTACK_STALLED: no own swing against the same adjacent living target for 15 seconds')
        # Only apply() counts received own swing/death frames. A bare Alive
        # never increments those counts; the next loop uses the updated view.
        self.next_attack = now + self.interval(1)
        self.last_alive = time.monotonic()

    async def potion(self):
        candidates = [(uid, item) for uid, item in self.inventory.items()
                      if item.get(2, -1) & 0xffffffff == 14 and item.get(4, 0) > 0]
        if not candidates:
            raise BotFailure('LOW_HP_NO_RECEIVED_POTION14: no supplied UID/count; no grant attempted')
        uid, item = min(candidates, key=lambda pair: pair[0])
        quantity = item[4]
        params = uint(1, 1) + uint(15, 0) + uint(16, 0)
        payload = uint(1, uid) + pb.encode_bytes(2, params)

        def consumed_then_status(batch):
            changed = None
            for frame in batch:
                if frame.opcode == 0x0978 and quantity == 1 and scalar(frame.values, 1) == uid:
                    changed = frame
                elif frame.opcode == 0x0965:
                    for raw in frame.values.get(1, ()):
                        child = fields(raw)
                        if scalar(child, 1) == uid and scalar(child, 4) == quantity - 1:
                            changed = frame
                if (changed is not None and frame.ordinal > changed.ordinal and frame.opcode == 0x4e38
                        and scalar(frame.values, 1) == self.self_uid):
                    return frame
            return None

        # A random positive heal is not guaranteed. Quantity consumption followed
        # by own status is observed; idle regeneration alone cannot satisfy this.
        await self.peer.request(0x0960, payload, check=consumed_then_status)
        self.potions_used += 1

    async def pickup(self, uid):
        """CS4E3E for a visible ground drop: x/y/UID/whole count (item_transfer_protocol GET)."""
        item = self.ground[uid]
        (x, y), count = item['position'], item['count']
        child = uint(1, x) + uint(2, y) + uint(3, uid) + uint(4, count)
        before = len([v for v in self.inventory.values()])
        batch = await self.peer.request(0x4e3e, pb.encode_bytes(1, child), alive=True,
            check=lambda batch: find(batch, 0x4f57), label='0x4E3E_to_ALIVE_barrier')
        removed = find(batch, 0x4e40, **{'1': uid})
        added = next((frame for frame in batch if frame.opcode in (0x0964, 0x0965)), None)
        if removed is not None and added is not None:
            self.pickups += 1
        else:
            self.pickup_refused[uid] += 1
        self.last_alive = time.monotonic()
        return before

    async def hunt(self):
        self.hunt_started = time.monotonic()
        deadline = self.hunt_started + self.args.minutes * 60
        groups = [g for g in self.data.spawns if g.map_id == self.map_id
                  and self.data.monsters[g.template_id].level <= (self.level or 1) + 3]
        if not groups:
            raise BotFailure('NO_MAP0_SPAWN_DATA')
        waypoints = [point for g in groups
                     if self.safe_hunt_cell(point := ((g.rect.x1 + g.rect.x2) // 2,
                                                      (g.rect.y1 + g.rect.y2) // 2))]
        if not waypoints:
            raise BotFailure('NO_SAFE_CURRENT_MAP_HUNT_WAYPOINT')
        waypoint = 0
        reached_north = False
        def reachable(goal, radius):
            return distance(self.position, goal) <= radius or self.heading(goal, radius) is not None
        while True:
            now = time.monotonic()
            if self.dead:
                raise BotFailure('PLAYER_DEAD')
            if now >= deadline:
                self.stop_reason = 'minutes'
                return
            if self.args.kills is not None and len(self.kills) >= self.args.kills:
                self.stop_reason = 'kills'
                return
            if self.hp is not None and self.hp <= self.max_hp * self.args.potion_threshold:
                await self.potion()
                continue
            if self.peer.error:
                raise BotFailure(self.peer.error)
            if await self.retreat_threat():
                await asyncio.sleep(.05)
                continue
            if not reached_north:
                reached_north = any(g.rect.contains(*self.position) for g in groups)
            loot = [(uid, item) for uid, item in self.ground.items()
                    if self.pickup_refused[uid] < 3 and distance(self.position, item['position']) <= 6
                    and self.safe_hunt_cell(item['position'])]
            adjacent = [uid for uid, actor in self.actors.items() if actor['alive']
                        and distance(self.position, actor['position']) <= 1]
            pickup = next((pair for pair in sorted(loot,
                key=lambda pair: (distance(self.position, pair[1]['position']), pair[0]))
                if reachable(pair[1]['position'], 1)), None) if not adjacent else None
            if pickup is not None:
                uid, item = pickup
                if distance(self.position, item['position']) <= 1:
                    await self.pickup(uid)
                else:
                    await self.step(item['position'], radius=1)
                if time.monotonic() - self.last_alive >= 1:
                    await self.alive()
                await asyncio.sleep(.05)
                continue
            candidates = [(uid, actor) for uid, actor in self.actors.items() if self.hunt_target(actor)]
            target = next((pair for pair in sorted(candidates,
                key=lambda pair: (distance(self.position, pair[1]['position']), pair[0]))
                if reachable(pair[1]['position'], 1)), None)
            if target is not None:
                uid, actor = target
                if distance(self.position, actor['position']) > 1:
                    await self.step(actor['position'], radius=1)
                else:
                    await self.attack(uid)
            else:
                for _ in waypoints:
                    goal = waypoints[waypoint]
                    if distance(self.position, goal) <= 2:
                        reached_north = True
                    elif reachable(goal, 2):
                        await self.step(goal, radius=2)
                        break
                    waypoint = (waypoint + 1) % len(waypoints)
                else:
                    raise BotFailure('NO_REACHABLE_CURRENT_MAP_HUNT_WAYPOINT')
            if time.monotonic() - self.last_alive >= 1:
                await self.alive()
            await asyncio.sleep(.05)

    async def run(self):
        self.started = time.monotonic()
        try:
            if self.args.expected_uuid is None:
                raise BotFailure('EXPECTED_UUID_REQUIRED: pass --expected-uuid or SL_EXPECTED_UUID from launcher')
            identity = uuid.UUID(self.args.expected_uuid)
            if identity.version != 4 or str(identity) != self.args.expected_uuid:
                raise BotFailure('CANONICAL_LAUNCHER_UUID4_REQUIRED')
            from tools.local_original_session.game_data import load_m1
            self.data = load_m1()
            await self.login()
            await self.hunt()
            if not self.kills:
                raise BotFailure('NO_KILL_OBSERVED_BEFORE_LIMIT')
        except asyncio.CancelledError:
            self.failure = 'CANCELLED'
        except KeyboardInterrupt:
            self.failure = 'INTERRUPTED'
        except Exception as error:
            self.failure = f'{type(error).__name__}: {str(error)[:240]}'
        finally:
            self.hunt_finished = time.monotonic()
            if self.selected and self.peer is not None and self.peer.error is None:
                try:
                    await self.peer.request(0x4e3c, check=lambda batch: find(batch, 0x4eef, **{'1': 45}))
                except Exception as error:
                    self.cleanup_failure = f'QUIT: {type(error).__name__}: {str(error)[:160]}'
            for peer in self.peers:
                await peer.close()
        return self.summary()

    def summary(self):
        now = time.monotonic()
        return dict(
            outcome='FAILED' if self.failure or self.cleanup_failure else 'FINISHED',
            scope='socket packet regression only; native play/rewards/storage unverified',
            stop_reason=self.stop_reason, failure=bool(self.failure or self.cleanup_failure),
            failure_reason=self.failure, cleanup_failure=self.cleanup_failure,
            elapsed_seconds=round(now - self.started, 3) if self.started is not None else 0,
            hunt_seconds=round((self.hunt_finished or now) - self.hunt_started, 3) if self.hunt_started is not None else 0,
            kills=len(self.kills), kill_basis='tracked death with last observed attacker equal to selected PC',
            dead=self.dead, deaths=int(self.self_uid in self.deaths), hp=self.hp, max_hp=self.max_hp, map_id=self.map_id,
            position=self.position, character=getattr(self, 'character', None),
            moves=self.moves, corrections=self.corrections, own_swings=self.swings,
            potions_used=self.potions_used,
            level_start=self.start_level, level=self.level,
            exp_percent=None if self.exp_percent is None else round(self.exp_percent, 4),
            ground_drops_seen=len(self.ground_seen), pickups=self.pickups,
            pickup_refusals=sum(self.pickup_refused.values()),
            adena=sum(v.get(4, 0) for v in self.inventory.values() if v.get(2, -1) & 0xffffffff == 7)
                  if self.inventory_received else None,
            inventory_rows=len(self.inventory) if self.inventory_received else None,
            inventory_received=self.inventory_received,
            potion14_remaining=sum(v.get(4, 0) for v in self.inventory.values()
                                   if v.get(2, -1) & 0xffffffff == 14) if self.inventory_received else None,
            frame_counts=dict(sorted(self.frame_counts.items())),
            request_latency_ms={label: dict(requests=self.request_counts[label],
                responses=len(self.latencies[label]), failures=self.request_failures[label],
                median=round(statistics.median(self.latencies[label]), 3) if self.latencies[label] else None,
                max=round(max(self.latencies[label]), 3) if self.latencies[label] else None)
                for label in sorted(self.request_counts)},
            latency_basis='monotonic send to last required correlated receive; move/attack labels explicitly use Alive barrier',
        )


def positive(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError('must be a finite number greater than zero')
    return result


def parser():
    result = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    result.add_argument('--minutes', type=positive, default=3, help='hunt for N real minutes after world entry (default: 3)')
    result.add_argument('--kills', type=int, help='also stop after N observed kills; minutes OR kills ends the run')
    result.add_argument('--host', default='127.0.0.1', help='IPv4 loopback broker host (default: 127.0.0.1)')
    result.add_argument('--port', type=int, choices=(12000, 14030), default=12000)
    result.add_argument('--expected-uuid', default=os.environ.get('SL_EXPECTED_UUID'), help="actual launcher UUID4; default SL_EXPECTED_UUID")
    result.add_argument('--character', help='exact reference from the received roster; default first saved character')
    result.add_argument('--timeout', type=positive, default=15, help='connection/request timeout in seconds (default: 15)')
    result.add_argument('--potion-threshold', type=positive, default=.5, help='use supplied potion14 at this HP fraction (default: .5)')
    result.add_argument('--skip-first-bootstrap', action='store_true', help='FIRST bootstrap already closed on this otherwise fresh endpoint')
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        host = ipaddress.IPv4Address(args.host)
        if not host.is_loopback:
            raise ValueError()
    except ValueError:
        cli.error('--host must be a numeric IPv4 loopback address')
    if args.kills is not None and args.kills < 1:
        cli.error('--kills must be greater than zero')
    if args.potion_threshold > 1:
        cli.error('--potion-threshold must be in (0, 1]')
    bot = HuntBot(args)
    try:
        summary = asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.failure = bot.failure or 'INTERRUPTED'
        summary = bot.summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary['failure'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
