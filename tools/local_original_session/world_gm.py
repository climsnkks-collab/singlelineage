"""Pure LOCAL test-GM chat decisions; no broker, socket, game, timer or file I/O.

Next world_handlers registration uses this signature::

    async def handle_chat(ctx: Context, text: str, now: float, *,
                          services: GMServices | None = None) -> GMResult

Run under the existing WorldRuntime.dispatch_now/world operation lock. A future
``async def handle_gm(ctx: Context, payload: bytes, now: float) -> None`` wrapper
must bind startup-prepared ``decode_chat(payload) -> str`` and
``encode_system_message(text) -> bytes``. For handled results, enqueue each
result.frames state reply once through ctx.send_frame, then enqueue the encoded
result.message once (including queries/errors). Route unhandled ordinary chat
normally. commit frames must NOT include that system text. Chat/system-message
opcode and body are 미확정 (UNCONFIRMED) in the inspected world_handlers, local_world_protocol and
game-core-prep/shared-api/implementation*/REA run* materials; no opcode is
invented here. SYSTEM_MESSAGE is a symbolic output need, never an encoded frame.

Context currently has no GM service. Pass GMServices explicitly; no ctx.gm or
other fictional service is assumed. ``prepare_chat(ctx, text, snapshot=...)``
only returns proposed state differences/owner operations. It changes nothing,
allocates no UID and generates no packet. ``handle_chat`` may ask the explicit
service for an in-memory snapshot and commit that proposal. Without a service,
mutating commands return GM_BINDING_REQUIRED; .where needs only current Entity.
Neither function sends frames. A proposed result is NOT applied success.

The future service owns test-GM authorization/session selection, snapshot
revision, current PC EntityRef and origin revalidation, existing native/current/
CAS save boundaries, and committed frame production. snapshot is cache-only:
load tables, codecs, terrain, ItemInfo prototypes and saves at startup, never
read a path or wait for input during a command. commit must implement each
operation entirely or refuse BEFORE mutation; never use this module as a new
cross-file transaction protocol. If an existing owner reports a partial/unknown
commit, propagate it to the host's existing partial/close handling, without
rollback, retries or success. GM service exceptions deliberately propagate.

Operation adapters still required:
* position: reuse Context.transition's complete position/map/visibility/save
  operation after checking actual terrain/map resources; do not call a partial
  EntityRegistry.move and claim teleport delivery.
* progression/base_stats and HP/MP: commit existing progression/resource owner
  state together, recalculate equipped/buff stats from the new base, and project
  full status with world_status_frames. No growth roll/refill is implied.
* item_grants/removals: existing item owner creates compatible stacks/real UID/
  ItemInfo and checks capacity, weight, ownership, equipment and save together.
  .clear preserves equipped items; remove each selected bag UID with 0978,
  never empty 0964 or quantity-zero 0965. Preserve UIDburn/history/other stores.
* spawns: current combat/spawn owner places ALL requested monsters on validated
  unoccupied terrain, allocates fresh UIDs and owns AI/corpse cleanup. A request
  contains an anchor, not invented spawn cells or template-as-UID.
* deaths: existing combat kill-once/reward/corpse owner consumes current refs;
  normal EXP/drop policy remains with that owner. EntityRegistry.kill alone is
  insufficient. No death/reward/respawn/current/ownership check is bypassed.
* speed_multiplier: apply both existing server action intervals and client
  4E5B projection, retaining active buff composition. god: wire the boolean to
  every owned damage consumer. Merely storing either value is insufficient.

frame_kinds are projection families to resolve, NOT packets sent or guarantees
that every family produces a packet. Known kinds reuse existing contracts:
4E38 world_status_frames; 4E95/4E96 local_world_protocol/README; 4E39 and 4E5B
world_combat docstring (REA102/206/324); 0964/0965/0978
game-core-prep/M1_REWARD_PACKETS.md section1(4). Visibility/ground-item details
and system text remain owner bindings. Unknown NPC HP-bar 4EC8 is not used.

LOCAL test policy (not original game rules): ASCII decimal coordinates/map
0..65535, item ID 1..u32max, monster template 0..u32max, item count 1..1,000,000,
spawn count 1..50, speed 0.1..10 inclusive (action-speed multiplier, 1=normal),
kill radius 17 Chebyshev tiles on the PC's current map. Kill selects only live
Kind.NPC entries whose template is in the loaded monster catalog, excluding
town NPCs and stale/dead/other-map entries. .clear removes unequipped bag rows,
including bag currency if present, never a separate wallet. .god toggles.
.exp n SETS absolute cumulative EXP (0 <= n < 2**62), never adds n. .level n
sets EXP to that loaded table level's threshold; levels are 1..len(pc_exp).
Both recompute level through M1Data, preserve HP/MP maxima/current values and
creation attributes, and request base-stat recalculation. No delevel HP loss or
level-up RNG is fabricated. .hp/.mp full require known resource maxima and do
not revive a dead PC. All malformed commands return errors without mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import inspect
import math
import re
from typing import TYPE_CHECKING, Awaitable, Protocol

from tools.local_original_session.game_data import M1Data
from tools.local_original_session.world_entities import EntityRef, Kind
from tools.local_original_session.world_maps import MapDestination
from tools.local_original_session.world_progress import Progress
from tools.local_original_session.world_shop import InventoryItem
from tools.local_original_session.world_stats import CharacterStats

if TYPE_CHECKING:
    from tools.local_original_session.world_handlers import Context


MAX_ITEM_COUNT = 1_000_000
MAX_SPAWN_COUNT = 50
KILL_RADIUS = 17
MAX_EXP = (1 << 62) - 1
USAGE = {
    'tele': '.tele x y [map]', 'level': '.level n', 'exp': '.exp n',
    'item': '.item id [count]', 'hp': '.hp full', 'mp': '.mp full',
    'spawn': '.spawn template [count]', 'kill': '.kill',
    'speed': '.speed multiplier', 'god': '.god', 'clear': '.clear', 'where': '.where',
}


class FrameKind(str, Enum):
    SYSTEM_MESSAGE = 'system_message'  # Opcode/body unconfirmed.
    STATUS = 'full_status_4e38'
    MAP = 'map_notify_4e95'
    ACTOR = 'actor_notify_4e96'
    VISIBILITY = 'visibility'
    ITEM_ADD = 'inventory_add_0964'
    ITEM_UPDATE = 'inventory_update_0965'
    ITEM_REMOVE = 'inventory_remove_0978'
    DEATH = 'death_4e39'
    GROUND_ITEMS = 'ground_items'
    SPEED = 'speed_bonus_4e5b'


@dataclass(frozen=True, slots=True)
class GMSnapshot:
    """Already-loaded owner state; revision is the EXISTING commit identity."""
    revision: object
    data: M1Data
    progress: Progress
    base_stats: CharacterStats
    hp: int
    max_hp: int
    mp: int | None
    max_mp: int | None
    inventory: tuple[InventoryItem, ...]
    map_ids: frozenset[int]
    speed_multiplier: float
    god: bool


@dataclass(frozen=True, slots=True)
class Change:
    name: str
    before: object
    after: object


@dataclass(frozen=True, slots=True)
class SpawnRequest:
    template_id: int
    count: int
    anchor: MapDestination


@dataclass(frozen=True, slots=True)
class GMPlan:
    command: str
    pc: EntityRef
    origin: MapDestination
    snapshot: GMSnapshot
    changes: tuple[Change, ...]
    frame_kinds: tuple[FrameKind, ...]


@dataclass(frozen=True, slots=True)
class GMCommit:
    """Only the existing owner's completed commit may supply reply frames."""
    frames: tuple[bytes, ...]


@dataclass(frozen=True, slots=True)
class GMResult:
    handled: bool
    status: str  # ignored / error / query / proposed / committed
    message: str = ''
    plan: GMPlan | None = None
    frames: tuple[bytes, ...] = ()
    frame_kinds: tuple[FrameKind, ...] = ()


class GMServices(Protocol):
    def snapshot(self, ctx: Context, now: float) -> GMSnapshot | Awaitable[GMSnapshot]:
        """Authorize this test connection, then snapshot current cached owners."""
        ...

    def commit(self, ctx: Context, plan: GMPlan, now: float) -> GMCommit | Awaitable[GMCommit]:
        """Revalidate/apply/save/project via existing atomic owner or raise.

        Refuse an unsupported operation before changing anything. Preserve any
        existing partial/unknown save result by raising to the host, not retrying.
        Return only state reply frames from the completed operation. The wrapper
        encodes result.message once separately; omit system text from frames.
        This module never fabricates a commit receipt.
        """
        ...


class GMError(ValueError):
    pass


def _need(value, message):
    if not value:
        raise GMError(message)


def _integer(token: str, low: int, high: int, label: str) -> int:
    _need(re.fullmatch(r'[0-9]+', token) is not None, f'GM_{label}_INTEGER_REQUIRED')
    value = int(token)
    _need(low <= value <= high, f'GM_{label}_RANGE: {low}..{high}')
    return value


def _parse(text: str):
    if not isinstance(text, str):
        raise TypeError('decoded chat text must be str')
    text = text.strip()
    if not text.startswith('.'):
        return None
    _need(len(text) <= 256 and not any(c in text for c in '\0\r\n'), 'GM_COMMAND_TEXT_INVALID')
    words = text[1:].split()
    _need(bool(words) and words[0].lower() in USAGE,
          'GM_UNKNOWN_COMMAND: ' + ', '.join('.' + key for key in USAGE))
    command, args = words[0].lower(), words[1:]
    low, high = {'tele': (2, 3), 'item': (1, 2), 'spawn': (1, 2),
                 'level': (1, 1), 'exp': (1, 1), 'hp': (1, 1), 'mp': (1, 1),
                 'speed': (1, 1)}.get(command, (0, 0))
    _need(low <= len(args) <= high, 'GM_USAGE: ' + USAGE[command])
    # Validate syntax before consulting any owner service.
    if command == 'tele':
        args = tuple(_integer(s, 0, 65535, 'COORDINATE' if i < 2 else 'MAP')
                     for i, s in enumerate(args))
    elif command in ('level', 'exp', 'item', 'spawn'):
        minimum = 0 if command in ('exp', 'spawn') else 1
        maximum = MAX_EXP if command == 'exp' else 255 if command == 'level' else 0xffffffff
        first = _integer(args[0], minimum, maximum, command.upper())
        count = ()
        if command in ('item', 'spawn'):
            count = (_integer(args[1], 1, MAX_ITEM_COUNT if command == 'item' else MAX_SPAWN_COUNT,
                              'COUNT') if len(args) == 2 else 1,)
        args = (first,) + count
    elif command in ('hp', 'mp'):
        _need(args[0].lower() == 'full', 'GM_USAGE: ' + USAGE[command])
        args = ()
    elif command == 'speed':
        _need(re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', args[0]) is not None,
              'GM_SPEED_DECIMAL_REQUIRED')
        value = float(args[0])
        _need(math.isfinite(value) and 0.1 <= value <= 10, 'GM_SPEED_RANGE: 0.1..10')
        args = (value,)
    return command, tuple(args)


def _pc(ctx):
    pc = ctx.world.entities.get(ctx.pc_uid)
    _need(pc is not None and pc.kind is Kind.PC and pc.alive, 'CURRENT_LIVE_PC_REQUIRED')
    _need(ctx.town.entities is ctx.world.entities, 'SAME_WORLD_TOWN_REQUIRED')
    return pc


def _position(pc):
    return MapDestination(pc.map_id, pc.x, pc.y, pc.heading)


def _prepare(ctx, parsed, snapshot):
    command, args = parsed
    pc = _pc(ctx)
    origin = _position(pc)
    if command == 'where':
        return GMResult(True, 'query', f'map={pc.map_id} x={pc.x} y={pc.y} '
                        f'heading={pc.heading} uid={pc.uid} generation={pc.generation}',
                        frame_kinds=(FrameKind.SYSTEM_MESSAGE,))
    _need(isinstance(snapshot, GMSnapshot), 'GM_BINDING_REQUIRED')
    data = snapshot.data
    kinds = (FrameKind.STATUS,)
    if command == 'tele':
        destination = MapDestination(args[2] if len(args) == 3 else pc.map_id,
                                     args[0], args[1], pc.heading)
        _need(destination.map_id in snapshot.map_ids, 'GM_MAP_UNAVAILABLE')
        changes = (Change('position', origin, destination),)
        kinds = (FrameKind.MAP, FrameKind.VISIBILITY)
    elif command in ('level', 'exp'):
        _need(snapshot.base_stats.level == snapshot.progress.level
              == data.level_for_exp(snapshot.progress.exp), 'GM_PROGRESS_SNAPSHOT_INCONSISTENT')
        if command == 'level':
            _need(args[0] <= len(data.pc_exp), f'GM_LEVEL_RANGE: 1..{len(data.pc_exp)}')
            exp = data.exp_for_level(args[0])
        else:
            exp = args[0]
        level = data.level_for_exp(exp)
        changes = (Change('progression', snapshot.progress,
                          replace(snapshot.progress, exp=exp, level=level)),
                   Change('base_stats', snapshot.base_stats,
                          replace(snapshot.base_stats, level=level)))
    elif command in ('hp', 'mp'):
        # Current world_combat death can leave Entity.alive True with PC HP0.
        _need(type(snapshot.hp) is int and snapshot.hp > 0, 'CURRENT_LIVING_RESOURCE_PC_REQUIRED')
        current, maximum = ((snapshot.hp, snapshot.max_hp) if command == 'hp'
                            else (snapshot.mp, snapshot.max_mp))
        _need(type(current) is int and type(maximum) is int
              and 0 <= current <= maximum and maximum >= (1 if command == 'hp' else 0),
              'GM_RESOURCE_MAXIMUM_REQUIRED')
        changes = (Change(command, current, maximum),)
    elif command == 'item':
        _need(args[0] in data.items, 'GM_ITEM_TEMPLATE_UNAVAILABLE')
        changes = (Change('item_grants', (), ((data.items[args[0]], args[1]),)),)
        kinds = (FrameKind.ITEM_ADD, FrameKind.ITEM_UPDATE, FrameKind.STATUS)
    elif command == 'spawn':
        _need(args[0] in data.monsters, 'GM_MONSTER_TEMPLATE_UNAVAILABLE')
        changes = (Change('spawns', (), (SpawnRequest(args[0], args[1], origin),)),)
        kinds = (FrameKind.ACTOR, FrameKind.VISIBILITY)
    elif command == 'kill':
        refs = tuple(entity.ref for entity in ctx.world.entities.near(
            pc.map_id, pc.x, pc.y, KILL_RADIUS, kind=Kind.NPC)
            if entity.template_id in data.monsters)
        changes = (Change('deaths', (), refs),)
        kinds = (FrameKind.DEATH, FrameKind.STATUS, FrameKind.GROUND_ITEMS, FrameKind.VISIBILITY)
    elif command == 'clear':
        removals = tuple((item.uid, item.count) for item in snapshot.inventory if not item.equipped)
        changes = (Change('item_removals', (), removals),)
        kinds = (FrameKind.ITEM_REMOVE, FrameKind.STATUS)
    elif command == 'speed':
        changes = (Change('speed_multiplier', snapshot.speed_multiplier, args[0]),)
        kinds = (FrameKind.SPEED,)
    else:  # god; all other commands were handled above or rejected by _parse.
        _need(type(snapshot.god) is bool, 'GM_GOD_STATE_REQUIRED')
        changes = (Change('god', snapshot.god, not snapshot.god),)
        kinds = ()
    kinds += (FrameKind.SYSTEM_MESSAGE,)
    plan = GMPlan(command, pc.ref, origin, snapshot, changes, kinds)
    return GMResult(True, 'proposed', 'GM_PROPOSED: ' + command, plan=plan, frame_kinds=kinds)


def prepare_chat(ctx: Context, text: str, *, snapshot: GMSnapshot | None = None) -> GMResult:
    """Return a pure query/proposal or useful error; ordinary chat is unhandled."""
    try:
        parsed = _parse(text)
        return GMResult(False, 'ignored') if parsed is None else _prepare(ctx, parsed, snapshot)
    except GMError as error:
        return GMResult(True, 'error', str(error), frame_kinds=(FrameKind.SYSTEM_MESSAGE,))


async def _resolve(value):
    return await value if inspect.isawaitable(value) else value


async def handle_chat(ctx: Context, text: str, now: float, *,
                      services: GMServices | None = None) -> GMResult:
    """Delegate only validated plans; return committed frames without sending.

    Authorization is the explicitly bound service's responsibility. No service
    means no mutation. Query/syntax errors do not consult services. Owner errors
    propagate so a partial failure cannot be reported as a harmless parse error.
    """
    try:
        parsed = _parse(text)
        if parsed is None:
            return GMResult(False, 'ignored')
        if parsed[0] == 'where' or services is None:
            return _prepare(ctx, parsed, None)
        _pc(ctx)
    except GMError as error:
        return GMResult(True, 'error', str(error), frame_kinds=(FrameKind.SYSTEM_MESSAGE,))
    snapshot = await _resolve(services.snapshot(ctx, now))
    try:
        result = _prepare(ctx, parsed, snapshot)
    except GMError as error:
        return GMResult(True, 'error', str(error), frame_kinds=(FrameKind.SYSTEM_MESSAGE,))
    committed = await _resolve(services.commit(ctx, result.plan, now))
    if (not isinstance(committed, GMCommit) or type(committed.frames) is not tuple
            or not all(type(frame) is bytes for frame in committed.frames)):
        raise TypeError('GM_COMMITTED_EXISTING_FRAMES_REQUIRED')
    return replace(result, status='committed', message='GM_COMMITTED: ' + parsed[0],
                   frames=committed.frames)
