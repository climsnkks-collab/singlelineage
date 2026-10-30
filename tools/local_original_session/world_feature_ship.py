"""Optional key4 voyage. Timings and sampling are explicit LOCAL policy.

4EF8/f1=4 is the recovered boarding input. No 4F0E is sent: its f1 meaning
remains unknown. Position and fare use existing owners, not a joint transaction;
relocation precedes fare debit so a failed relocation never loses a ticket.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import json
import math
from pathlib import Path
import random
import time

from tools.local_entry_server import protobuf as pb
from tools.local_original_session.world_bridge import need
from tools.local_original_session.world_maps import MapDestination


@dataclass(frozen=True)
class ShipRoute:
    key: int
    harbor_map: int
    interior_map: int
    ticket_id: int
    dock_box: tuple[int, int, int, int]
    interior_point: tuple[int, int]
    arrival_map: int
    arrival_random: tuple[int, int, int]
    return_point: tuple[int, int]
    interval_seconds: int = 300

    def at_dock(self, position):
        left, top, right, bottom = self.dock_box
        return (position.map_id == self.harbor_map
                and left <= position.word0 <= right and top <= position.word1 <= bottom)

    @property
    def return_destination(self):
        return MapDestination(self.harbor_map, *self.return_point, 4)


@dataclass
class Voyage:
    uid: int
    departure_at: float
    arrival_at: float
    phase: str = 'WAITING'
    task: object = None
    writer: object = None
    in_transfer: bool = False
    error: str | None = None
    departure_deadline: float | None = None
    arrival_deadline: float | None = None


def load_route(path=None):
    path = Path(__file__).with_name('data') / 'm6/ship_routes.json' if path is None else Path(path)
    row = json.loads(path.read_text(encoding='utf-8'))['route']
    return ShipRoute(row['key'], row['harbor_map'], row['interior_map'], row['ticket_id'],
        tuple(row['dock_box']), tuple(row['interior_point']), row['arrival_map'],
        tuple(row['arrival_random']), tuple(row['return_point']),
        row['schedule']['interval_minutes'] * 60)


def parse_portal(payload):
    """Recovered required signed-i32 f1 only; no invented disembark operand."""
    with pb.parse_message(payload, limits=pb.WireLimits(
            max_body=32, max_fields=1, max_field_bytes=16)) as parsed:
        entries = parsed.occurrences(1)
        need(len(entries) == 1 and len(parsed.fields) == 1 and entries[0].wire_type == 0,
             'SHIP_REQUIRED_I32_PORTAL')
        value = entries[0].value
        need(value <= 0x7fffffff or 0xffffffff80000000 <= value <= 0xffffffffffffffff,
             'SHIP_REQUIRED_I32_PORTAL')
        return value if value <= 0x7fffffff else value - (1 << 64)


def next_departure(wall_seconds, interval=300):
    """Strictly next wall-clock five-minute boundary (UTC, also KST aligned).

    LOCAL clock choice: epoch seconds, independent of L1J's sixfold game clock.
    A request exactly at a boundary boards the following departure.
    """
    return (math.floor(wall_seconds / interval) + 1) * interval


def _ticket(ctx, route):
    from tools.local_original_session import inventory
    item = next((item for item in inventory.validate_kit_frame(ctx.inventory_frame)
                 if item.template_bits == route.ticket_id and dict(item.raw_fields)[4] > 0), None)
    need(item is not None, 'SHIP_OWNED_TICKET_REQUIRED')
    return item


def _position(ctx, writer, row, game):
    need(ctx._world_bound(writer) and ctx._world_ready(writer, game) is not None,
         'SHIP_CURRENT_WORLD_REQUIRED')
    position = ctx.realm.service(writer).snapshot()
    need(row['operation_lock'].locked() and ctx.owner_current(writer, row, position),
         'WORLD_MAP_CURRENT_OWNER_REQUIRED')
    state = ctx.world.combat.pcs[position.uid]
    need(not state.dead and state.hp > 0, 'SHIP_LIVING_PC_REQUIRED')
    return position


def _arrival_points(ctx, route):
    need(ctx.realm.serves_map(route.arrival_map), 'SHIP_ARRIVAL_RESOURCE_UNAVAILABLE')
    x, y, radius = route.arrival_random
    # LOCAL uniform selection among actual standable cells of the radius box.
    points = tuple((xx, yy) for xx in range(x - radius, x + radius + 1)
                   for yy in range(y - radius, y + radius + 1)
                   if ctx.world.terrain.can_stand(route.arrival_map, xx, yy) is True)
    need(points, 'SHIP_ARRIVAL_RESOURCE_UNAVAILABLE')
    return points


def _resources(ctx, route):
    need(ctx.realm.serves_map(route.interior_map)
         and ctx.world.terrain.can_stand(route.interior_map, *route.interior_point) is True,
         'SHIP_INTERIOR_RESOURCE_UNAVAILABLE')
    return _arrival_points(ctx, route)


def _error(ctx, error):
    ctx._world_handler_errors = (ctx._world_handler_errors + [str(error)[:96]])[-8:]


def _cancel(voyage):
    task, voyage.task = voyage.task, None
    if task is not None and task is not asyncio.current_task() and not task.done():
        task.cancel()
    return task


def _ship_initialize(ctx):
    ctx._ship_route = load_route() if ctx._world_map_exp == 2 else None
    ctx._ship_voyages = {}
    ctx._ship_failures = []
    ctx._ship_completed = 0


def _launch(ctx, voyage, writer, row, game):
    _cancel(voyage)
    voyage.writer = writer
    if voyage.departure_deadline is None:
        wall, mono = time.time(), ctx.world.runtime.clock()
        voyage.departure_deadline = mono + voyage.departure_at - wall
        voyage.arrival_deadline = mono + voyage.arrival_at - wall
    voyage.task = asyncio.create_task(_run_voyage(ctx, voyage, writer, row, game),
                                      name=f'ship-key4-{voyage.uid}')


async def _wait_until(deadline, clock):
    await asyncio.sleep(max(0.0, deadline - clock()))


async def _run_voyage(ctx, voyage, writer, row, game):
    try:
        while ctx._ship_voyages.get(voyage.uid) is voyage:
            deadline = (voyage.departure_deadline if voyage.phase == 'WAITING'
                        else voyage.arrival_deadline)
            # A single wall->monotonic conversion fixes this voyage's cadence.
            # NTP/local clock changes cannot shorten or extend an underway leg.
            await _wait_until(deadline, ctx.world.runtime.clock)
            if ctx.world.runtime.clock() < deadline:
                continue
            async with row['operation_lock']:
                if ctx._ship_voyages.get(voyage.uid) is not voyage or voyage.writer is not writer:
                    return
                await ctx._ship_step(voyage, writer, row, game)
            if voyage.phase != 'TRAVELLING':
                return
    except asyncio.CancelledError:
        raise
    except Exception as error:
        voyage.error = str(error)[:160]
        ctx._ship_failures = (ctx._ship_failures + [dict(uid=voyage.uid, phase=voyage.phase,
                                                      error=voyage.error)])[-8:]
        _error(ctx, error)
    finally:
        if voyage.task is asyncio.current_task():
            voyage.task = None


async def _ship_step(ctx, voyage, writer, row, game):
    """One scheduled operation, same row/world locks as direct core movement."""
    from tools.local_original_session.world_handlers import HostContext
    context = HostContext(ctx.broker, writer, row, game, row['operation_lock'])

    def transfer():
        route = ctx._ship_route
        position = _position(ctx, writer, row, game)
        need(position.uid == voyage.uid, 'SHIP_CURRENT_VOYAGE_OWNER_REQUIRED')
        ticket = _ticket(ctx, route)
        if voyage.phase == 'WAITING':
            need(route.at_dock(position), 'SHIP_CURRENT_DOCK_REQUIRED')
            _resources(ctx, route)
            destination = MapDestination(route.interior_map, *route.interior_point, 4)
        else:
            need(voyage.phase == 'TRAVELLING' and position.map_id == route.interior_map,
                 'SHIP_CURRENT_INTERIOR_REQUIRED')
            destination = MapDestination(route.arrival_map, *random.choice(_arrival_points(ctx, route)), 4)
        voyage.in_transfer = True
        try:
            for wire in ctx._world_relocate_locked(writer, row, game, destination, context=context):
                context.send_frame(wire)
            if voyage.phase == 'WAITING':
                voyage.phase = 'TRAVELLING'
            else:
                # Existing APIs are not crash-atomic together. A relocation error
                # cannot debit. Never retry an ambiguous debit, including reconnect.
                voyage.phase = 'FARE_ATTEMPTED'
                context.commit_attempted = True
                context.send_frame(ctx._world_consume_kit(writer, ticket.identifier))
                voyage.phase = 'COMPLETED'
                ctx._ship_completed += 1
                ctx._ship_voyages.pop(voyage.uid, None)
        finally:
            voyage.in_transfer = False

    await ctx.world.runtime.dispatch_now(transfer)
    await ctx._world_send(writer, row, tuple(context.frames), row['operation_lock'])


async def _ship_enter(ctx, writer, row, game, frame, operation_lock):
    route = ctx._ship_route
    if route is None or not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False
    try:
        portal = parse_portal(frame.payload)
    except (ValueError, pb.WireError):
        return False
    if portal != route.key:
        return False

    def admission():
        position = _position(ctx, writer, row, game)
        need(route.at_dock(position), 'SHIP_CURRENT_DOCK_REQUIRED')
        _ticket(ctx, route)
        _resources(ctx, route)
        previous = ctx._ship_voyages.get(position.uid)
        if previous is not None:
            need(previous.phase == 'WAITING' and previous.writer is writer,
                 'SHIP_PREVIOUS_VOYAGE_UNRESOLVED')
            if previous.task is not None or previous.error is None:
                return  # repeated boarding never postpones the current departure
            ctx._ship_voyages.pop(position.uid)  # failed, still at dock, no debit
        at = next_departure(time.time(), route.interval_seconds)
        voyage = Voyage(position.uid, at, at + route.interval_seconds)
        ctx._ship_voyages[position.uid] = voyage
        _launch(ctx, voyage, writer, row, game)

    try:
        await ctx.world.runtime.dispatch_now(admission)
    except (ValueError, pb.WireError) as error:
        _error(ctx, error)
    return True


async def _ship_after_enter(ctx, writer, row, game, operation_lock):
    if ctx._ship_route is None:
        return
    position = ctx.realm.service(writer).snapshot()
    voyage = ctx._ship_voyages.get(position.uid)
    if voyage is not None and voyage.phase == 'FARE_ATTEMPTED':
        # Preserve ambiguity; never blindly consume a second ticket.
        return
    if position.map_id != ctx._ship_route.interior_map:
        if voyage is not None:
            _cancel(voyage)
            ctx._ship_voyages.pop(position.uid, None)
        return
    if voyage is None:
        # LOCAL process-restart recovery from the existing saved map83 only.
        at = next_departure(time.time(), ctx._ship_route.interval_seconds)
        voyage = Voyage(position.uid, at - ctx._ship_route.interval_seconds, at, 'TRAVELLING')
        ctx._ship_voyages[position.uid] = voyage
    _launch(ctx, voyage, writer, row, game)


async def _ship_before_leave(ctx, writer, uid):
    voyage = ctx._ship_voyages.get(uid)
    if voyage is None or voyage.writer is not writer:
        return
    task = _cancel(voyage)
    if task is not None and task is not asyncio.current_task():
        await asyncio.gather(task, return_exceptions=True)
    voyage.writer = None
    if voyage.phase == 'WAITING':
        ctx._ship_voyages.pop(uid, None)


def _ship_before_relocate(ctx, uid, transit):
    voyage = ctx._ship_voyages.get(uid)
    if voyage is not None and not voyage.in_transfer and voyage.phase != 'FARE_ATTEMPTED':
        _cancel(voyage)
        ctx._ship_voyages.pop(uid, None)


async def _ship_stopped(ctx):
    tasks = [task for voyage in ctx._ship_voyages.values() if (task := _cancel(voyage)) is not None]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _ship_return_destination(ctx, result, position):
    route = ctx._ship_route
    if (route is not None and position is not None
            and position.map_id in (route.interior_map, route.arrival_map)
            and result.kind == 'return_town' and result.destination is not None):
        from tools.local_original_session.world_item_effects import movement_requirements
        destination = route.return_destination
        return replace(result, destination=destination,
                       requirements=movement_requirements(position.map_id, destination))
    return result


def _ship_report(ctx, result):
    if ctx._ship_route is not None:
        result['ship'] = dict(route_key=ctx._ship_route.key, status='LOCAL_VOYAGE',
            completed=ctx._ship_completed, active=[dict(uid=v.uid, phase=v.phase,
                departure_at=v.departure_at, arrival_at=v.arrival_at, error=v.error)
                for v in ctx._ship_voyages.values()], failures=list(ctx._ship_failures),
            timers=sum(v.task is not None and not v.task.done() for v in ctx._ship_voyages.values()),
            start_notifications='NONE', joint_position_fare_atomic=False)


METHODS = (_ship_initialize, _ship_enter, _ship_step, _ship_after_enter,
           _ship_before_leave, _ship_before_relocate, _ship_stopped,
           _ship_return_destination, _ship_report)
HOOKS = {'initialize': ('_ship_initialize',), 'enter_ship': ('_ship_enter',),
         'after_enter': ('_ship_after_enter',), 'before_leave': ('_ship_before_leave',),
         'before_relocate': ('_ship_before_relocate',), 'runtime_stopped': ('_ship_stopped',),
         'item_destination_policy': ('_ship_return_destination',), 'report': ('_ship_report',)}
SAVE_BOUNDARIES = {'_ship_step': True}
