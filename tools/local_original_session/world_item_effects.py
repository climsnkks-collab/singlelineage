"""M1 consumable effects, independent of broker, inventory and persistence.

Call under the existing world lock, after the caller admits the owned item use.
The pure ``use`` changes combat/ailment/item-effect state and proposes cost.
The optional 0960 adapter below commits real kit cost and durable item state.
Neither path commits a position. ``consume_count`` describes
the caller's inventory proposal; for destination_proposed it must wait for the
actual relocation to succeed. A movement proposal has unresolved wire needs
and is not a successful native teleport. Apply a destination through the
existing position owner and EntityRegistry.move, never by editing Entity fields.

Healing uses official inclusive endpoints and a LOCAL uniform integer draw;
the source does not specify the distribution. SC4E38/4E5B encoding and speed
reuse WorldCombat. Legacy scalar definitions retain its Gaussian policy.
This is not full L1J effects (DECAY_POTION, POLLUTE_WATER, barriers, etc.).
Teleport proposals carry the existing 4ED8/gfx169 visual frame; the caller
still owns position commit and map publication.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import time
from types import MappingProxyType
from typing import Mapping, Protocol

from tools.local_original_session.game_data import M1_DATA_DIR
from tools.local_original_session.world_combat import WorldCombat, status_frame
from tools.local_original_session.world_maps import MapDestination
from tools.local_original_session.world_buff_frames import buff_icon_frame

DEFAULT_PATH = M1_DATA_DIR / 'item_effects.json'

# Fixed-client item -> CommonSpell -> BuffIconInfo.f4 evidence (W68).
# Template eligibility is deliberate: other items sharing 'brave' are not mapped.
CONSUMABLE_BUFF_ICONS = MappingProxyType({
    17: (223, 481, 'haste'), 495: (226, 481, 'haste'),
    296: (224, 486, 'brave'), 492: (232, 5399, 'mana_regen'),
    297: (231, 484, 'wisdom'),
    # item.f41 -> CommonSpell.f3/f7, native-dump rows1024/1507/1254-1255
    # and2332/2448/2336. These happen to share K with other admitted items.
    86: (225, 486, 'brave'), 1408: (1062, 486, 'brave'),
    417: (229, 552, 'breath'), 418: (229, 552, 'breath'),
})
# Existing consumable definitions mapped to CharBuffTable's saved statuses:
# haste1001, brave1000 / elfbrave1016, blue1002. Wisdom keeps its legacy save.
SAVED_POTIONS = MappingProxyType({17: 'haste', 495: 'haste', 296: 'brave',
                                86: 'brave', 1408: 'brave', 492: 'mana_regen'})


class Terrain(Protocol):
    def bounds(self, map_id: int) -> tuple[int, int, int, int] | None: ...
    def can_stand(self, map_id: int, x: int, y: int) -> bool | None: ...


@dataclass(frozen=True, slots=True)
class ItemEffectDef:
    template_id: int
    name_ko: str
    kind: str
    reference_id: int
    heal_hp: int = 0
    buff_template_id: int | None = None
    buff_add_s: int | None = None
    teleport_radius: int = 200
    heal_hp_range: tuple[int, int] | None = None
    revive_hp_divisor: int = 4
    buff_classes: tuple[int, ...] | None = None
    duration_s: int = 0
    duration_cap_s: int = 0
    nutrition: int = 0
    use_gfx: int | None = None  # SC_EFFECT_NOTI 4ED8 gfx shown on the user at use
    destination: tuple[int, int, int] | None = None
    entry_bounds: tuple[int, int, int, int, int] | None = None
    consume_count: int = 1


def load_effects(path: str | Path = DEFAULT_PATH, *, owner='items') -> Mapping[int, ItemEffectDef]:
    """Load explicit classic IDs for their existing dispatcher, at startup.

    Targeted companion effects must not enter the earlier raw0 potion lane.
    There is no numeric L1J-to-classic conversion.
    """
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    return MappingProxyType({row['template_id']: ItemEffectDef(
        row['template_id'], row['name_ko'], row['kind'], row['l1j_item_id'],
        row.get('heal_hp', 0), row.get('buff_template_id'), row.get('buff_add_s'),
        row.get('teleport_radius', 200),
        None if 'heal_hp_range' not in row else
        (row['heal_hp_range']['min'], row['heal_hp_range']['max']),
        row.get('revive_hp_divisor', 4),
        None if 'buff_classes' not in row else tuple(row['buff_classes']),
        row.get('duration_s', 0), row.get('duration_cap_s', 0), row.get('nutrition', 0),
        row.get('use_gfx'),
        None if 'destination' not in row else tuple(row['destination']),
        None if 'entry_bounds' not in row else tuple(row['entry_bounds']),
        row.get('consume_count', 1))
        for row in raw['effects'] if row.get('dispatch_owner', 'items') == owner})


@dataclass(slots=True)
class PcAilments:
    """Optional caller-owned poison state; PcState currently has no poison field.

    None = healthy. The poison owner must also stop its damage/timer when the
    effect result reports poison_cured; this module runs no poison ticker.
    """
    poison: str | None = None


@dataclass(frozen=True, slots=True)
class FrameRequirement:
    kind: str
    opcode: int | None
    unresolved: str


@dataclass(frozen=True, slots=True)
class ItemEffectResult:
    template_id: int
    kind: str
    outcome: str  # applied / no_effect / destination_proposed / refused / unsupported
    consume_count: int = 0  # proposal only; this module never changes inventory
    frames: tuple[bytes, ...] = ()
    requirements: tuple[FrameRequirement, ...] = ()
    destination: MapDestination | None = None
    healed_hp: int = 0
    buff_kind: str | None = None
    buff_expires_at: float | None = None  # caller uses its existing expiry scheduler
    poison_cured: bool = False
    reason: str = ''


@dataclass(slots=True)
class PendingPotion:
    """Session effect belongs to a particular binding, never a reusable UID."""
    state: object
    until: float
    regen_handle: object = None


@dataclass(slots=True)
class ConsumableState:
    """LOCAL item authority; no guessed native flag or spell formula override."""
    fullness: int = 0
    wisdom_until: float = 0.0
    breath_until: float = 0.0
    identified: set[int] = field(default_factory=set)
    curses: set[int] = field(default_factory=set)
    potions: dict[int, float] = field(default_factory=dict)
    potions_paused: bool = False


def consumable_snapshot(uid, state, now, *, wall=None):
    return dict(uid=uid, fullness=state.fullness,
        wisdom_remaining=max(0.0, state.wisdom_until - now),
        breath_remaining=max(0.0, state.breath_until - now),
        identified=sorted(state.identified), curses=sorted(state.curses),
        potion_remaining={str(template): remaining for template, value in sorted(state.potions.items())
                          if (remaining := max(0.0, value if state.potions_paused else value - now)) > 0},
        saved_at=time.time() if wall is None else wall)


def consumable_restore(row, now, *, wall=None):
    """Legacy wisdom/breath tick offline; saved L1J potions pause until binding."""
    required = {'uid', 'fullness', 'wisdom_remaining', 'breath_remaining',
                'identified', 'curses', 'saved_at'}
    if (type(row) is not dict or set(row) not in (required, required | {'potion_remaining'})
            or type(row['uid']) is not int or not 0 < row['uid'] <= 0xffffffff
            or type(row['fullness']) is not int or not 0 <= row['fullness'] <= 225
            or any(type(row[k]) not in (int, float) or not math.isfinite(row[k])
                   or row[k] < 0 for k in ('wisdom_remaining', 'breath_remaining', 'saved_at'))
            or any(type(row[k]) is not list
                   or any(type(v) is not int or not 0 < v <= 0xffffffff for v in row[k])
                   or len(set(row[k])) != len(row[k])
                   for k in ('identified', 'curses'))):
        raise ValueError('CONSUMABLE_SAVE_ROW')
    potions = row.get('potion_remaining', {})
    if (type(potions) is not dict
            or any(key not in {str(template) for template in SAVED_POTIONS}
                   or type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                   for key, value in potions.items())
            or len({SAVED_POTIONS[int(key)] for key in potions}) != len(potions)):
        raise ValueError('CONSUMABLE_SAVE_POTIONS')
    elapsed = max(0.0, (time.time() if wall is None else wall) - row['saved_at'])
    return ConsumableState(row['fullness'],
        now + max(0.0, row['wisdom_remaining'] - elapsed),
        now + max(0.0, row['breath_remaining'] - elapsed),
        set(row['identified']), set(row['curses']),
        {int(key): value for key, value in potions.items()}, True)


class ConsumableStore:
    """Optional profile participant, using existing atomic writer and kit CAS.

    A forward intent preserves a consumed item's new effect after interrupted
    saving. Recovery accepts only the exact before/after kit. No core or magic
    save format changes, new UID, refund, or in-session retry are introduced.
    """
    def __init__(self, inventory_store):
        self.inventory = inventory_store
        self.path = Path(inventory_store.profile).with_name('consumable-effects.json')
        self.intent = self.path.with_name('consumable-effects-pending.json')
        self.rows, self.pending = {}, None
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if raw.get('version') != 1 or type(raw.get('rows')) is not list:
                raise ValueError('CONSUMABLE_SAVE_VERSION')
            for row in raw['rows']:
                consumable_restore(row, 0)
                if row['uid'] in self.rows:
                    raise ValueError('CONSUMABLE_SAVE_DUPLICATE_UID')
                self.rows[row['uid']] = row
        if self.intent.exists():
            self.pending = json.loads(self.intent.read_text(encoding='utf-8'))
            if set(self.pending) != {'version', 'state', 'before', 'after'} or self.pending['version'] != 1:
                raise ValueError('CONSUMABLE_INTENT_SCHEMA')
            consumable_restore(self.pending['state'], 0)
            self._finish()

    def _write(self, path, value):
        from tools.local_original_session.world_warehouse import _atomic_json
        _atomic_json(path, value)

    def save(self, uid, state, now):
        if self.pending is not None:
            raise ValueError('CONSUMABLE_RECOVERY_REQUIRED')
        rows = dict(self.rows)
        rows[uid] = consumable_snapshot(uid, state, now)
        self._write(self.path, dict(version=1, rows=[v for _, v in sorted(rows.items())]))
        self.rows = rows

    def _finish(self):
        from tools.local_original_session import inventory
        pending = self.pending
        row = pending['state']
        before, after = bytes.fromhex(pending['before']), bytes.fromhex(pending['after'])
        inventory.validate_kit_frame(before)
        inventory.validate_kit_frame(after)
        current = self.inventory.restore(row['uid'])
        if current not in (before, after):
            raise ValueError('CONSUMABLE_INVENTORY_CONFLICT')
        if current == before:
            immediate = hasattr(self.inventory, '_world_immediate')
            if immediate:
                self.inventory._world_immediate += 1
            try:
                if self.inventory.replace_kit(row['uid'], before, after) is not True:
                    raise ValueError('CONSUMABLE_INVENTORY_COMMIT_REQUIRED')
            finally:
                if immediate:
                    self.inventory._world_immediate -= 1
        rows = dict(self.rows)
        rows[row['uid']] = row
        self._write(self.path, dict(version=1, rows=[v for _, v in sorted(rows.items())]))
        self.rows = rows
        self.intent.unlink()
        self.pending = None

    def commit(self, uid, before, after, state, now):
        if self.pending is not None:
            raise ValueError('CONSUMABLE_RECOVERY_REQUIRED')
        persist = getattr(self.inventory, '_world_persist', None)
        if persist is not None and not persist.flush_all().ok:
            raise ValueError('CONSUMABLE_INVENTORY_FLUSH_REQUIRED')
        self.pending = dict(version=1, state=consumable_snapshot(uid, state, now),
                            before=before.hex(), after=after.hex())
        self._write(self.intent, self.pending)
        self._finish()


def random_destination(position: MapDestination, terrain: Terrain, rng: random.Random,
                       radius: int = 200) -> MapDestination | None:
    """Uniform sample of known standable cells in the same-map square.

    L1J randomLocation(200,true) supplies the radius only. This bounded scan is
    LOCAL selection policy; unknown/unloaded cells and the current cell cannot
    be destinations. Static can_stand does not establish doors/actor occupancy.
    Short uniform rejection sampling avoids a full scan on ordinary open maps.
    If all attempts fail, reservoir sampling still finds a sparse destination.
    Each path selects uniformly among eligible cells, so their mixture does too.
    """
    bounds = terrain.bounds(position.map_id)
    if bounds is None:
        return None
    x1, y1, x2, y2 = bounds
    x1, y1 = max(x1, position.x - radius), max(y1, position.y - radius)
    x2, y2 = min(x2, position.x + radius), min(y2, position.y + radius)
    if x1 > x2 or y1 > y2:
        return None
    for _ in range(32):
        x, y = rng.randint(x1, x2), rng.randint(y1, y2)
        if (x, y) != (position.x, position.y) and terrain.can_stand(position.map_id, x, y) is True:
            return MapDestination(position.map_id, x, y, 5)
    found, chosen = 0, None
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            if (x, y) == (position.x, position.y):
                continue
            if terrain.can_stand(position.map_id, x, y) is True:
                found += 1
                if rng.randrange(found) == 0:
                    chosen = MapDestination(position.map_id, x, y, 5)
    return chosen


def movement_requirements(source_map: int, destination: MapDestination) -> tuple[FrameRequirement, ...]:
    requirements = [FrameRequirement('teleport', None,
        'Native teleport publication/order UNKNOWN. 4E2C is walking; '
        '4EE0 is position correction, not a verified teleport producer.')]
    if source_map != destination.map_id:
        requirements.append(FrameRequirement('map_notify', 0x4E95,
            'REA273: f1 map ID known; required f2 meaning/value, f3/f4 normal '
            'values and actor/currentPlayer re-establishment order UNKNOWN. '
            '03EB is not a map ACK.'))
    return tuple(requirements)


def return_town_result(template_id, position, town):
    """Shared ordinary return-scroll destination proposal; no cost or movement."""
    destination = MapDestination(town.map_id, town.respawn_x, town.respawn_y, 5)
    return ItemEffectResult(template_id, 'return_town', 'destination_proposed', 1,
        requirements=movement_requirements(position.map_id, destination), destination=destination,
        reason='POSITION_AND_NATIVE_WIRE_NOT_COMMITTED')


def item_use_effect_frame(uid: int, definition: ItemEffectDef | None, result=None):
    """Shared PC/companion 4ED8 use sound, from the existing item definition."""
    if definition is None or definition.use_gfx is None:
        return None
    if result is not None and not (result.outcome == 'applied' or result.outcome == 'no_effect'
                                   and result.kind in ('heal', 'cure_poison')):
        return None
    from tools.local_original_session.world_status_frames import effect_frame
    return effect_frame(uid, definition.use_gfx)


def teleport_effect_frame(uid: int) -> bytes:
    """Existing self teleport effect (SC_EFFECT_NOTI 4ED8, gfx 169)."""
    from tools.local_original_session.world_status_frames import effect_frame
    return effect_frame(uid, 169)


class WorldItemEffects:
    """Effect dispatcher; shares the combat RNG unless explicitly supplied."""

    def __init__(self, combat: WorldCombat, terrain: Terrain | None = None, *,
                 definitions: Mapping[int, ItemEffectDef] | None = None,
                 rng: random.Random | None = None):
        self.combat, self.terrain = combat, terrain
        self.definitions = load_effects() if definitions is None else definitions
        self.extended = load_effects(owner='consumables')
        self.unsupported = load_effects(owner='unsupported')
        self.rng = combat.rng if rng is None else rng
        self.active: dict[int, dict[str, PendingPotion]] = {}
        self.world = None
        self.magic = None
        self.magic_save = None
        self.cure_poison = None
        self.states: dict[int, ConsumableState] = {}
        self.store = None
        self.observers = {}
        # Only published PC icons, scoped to the exact combat binding. No save
        # authority lives here; every deadline is read from its existing owner.
        self.icons = {}
        self.bindings = {}
        self.entry_loaded_uids = set()
        self.leave_listener = None
        self.restore_trace = []
        self.last_resume_decision = None

    def remember_potion(self, uid, template_id, now):
        """Retain the admitted item's identity, including speed's legacy kit lane."""
        kind = SAVED_POTIONS.get(template_id)
        if kind is None:
            return
        pc = self.combat.pcs.get(uid)
        if pc is None:
            return
        if kind == 'mana_regen':
            effect = self.active.get(uid, {}).get(kind)
            until = effect.until if effect is not None and effect.state is pc else 0
        else:
            until = pc.buffs.get(kind, (0, 0))[0]
        if until <= now:
            return
        state = self.state(uid)
        state.potions = {template: value for template, value in state.potions.items()
                         if SAVED_POTIONS[template] != kind}
        state.potions[template_id] = until
        state.potions_paused = False

    def capture_potions(self, uid, *, pause=False):
        """Capture before combat forgets this binding; expired/dead effects stay gone."""
        state, pc = self.state(uid), self.combat.pcs.get(uid)
        if state.potions_paused or pc is None:
            return
        now = self.world.runtime.clock()
        for template in tuple(state.potions):
            kind = SAVED_POTIONS[template]
            effect = self.active.get(uid, {}).get(kind)
            if kind == 'mana_regen':
                until = effect.until if effect is not None and effect.state is pc else 0
            else:
                until = pc.buffs.get(kind, (0, 0))[0]
            if pc.dead or pc.hp <= 0 or until <= now:
                del state.potions[template]
            else:
                state.potions[template] = until - now if pause else until
        state.potions_paused = pause
        if pause:
            self.bindings.pop(uid, None)

    def restore_potions(self, uid, now):
        """Run once after PC binding, using existing speed/regen lifetime owners."""
        pc = self.combat.pcs.get(uid)
        decision = dict(uid=uid, source=type(self).restore_potions.__code__.co_filename,
            source_line=type(self).restore_potions.__code__.co_firstlineno,
            at_call=_consumable_owner_snapshot(self, uid))
        self.last_resume_decision = decision
        if pc is None or pc.dead or pc.hp <= 0 or self.bindings.get(uid) is pc:
            decision['outcome'] = ('NO_PC' if pc is None else 'DEAD' if pc.dead else
                                   'HP_ZERO' if pc.hp <= 0 else 'ALREADY_BOUND')
            return ()
        if uid not in self.entry_loaded_uids:
            # Startup reads the profile before a selected PC exists. Adopt that
            # durable row at its first real binding; later same-broker reselects
            # retain the in-memory state if a leave save was interrupted.
            saved = (None if self.store is None else
                     getattr(self.store, 'rows', {}).get(uid))
            decision['selected_store_row'] = (None if saved is None else
                dict(id=hex(id(saved)), potion_remaining=dict(saved.get('potion_remaining', {}))))
            if saved is not None:
                self.states[uid] = consumable_restore(saved, now)
                decision['adopted_state'] = _consumable_owner_snapshot(self, uid)
            self.entry_loaded_uids.add(uid)
        state = self.state(uid)
        self.bindings[uid] = pc
        decision['after_binding'] = _consumable_owner_snapshot(self, uid)
        if not state.potions_paused:
            decision['outcome'] = 'NOT_PAUSED'
            return ()
        pending, state.potions = state.potions, {}
        state.potions_paused = False
        decision['pending'] = dict(pending)
        speed = False
        for template, remaining in pending.items():
            if remaining <= 0:
                continue
            definition, kind = self.definitions[template], SAVED_POTIONS[template]
            if kind == 'mana_regen':
                self.active.setdefault(uid, {})[kind] = PendingPotion(
                    pc, now + remaining, self.world.regen.get(uid))
            else:
                buff = self.combat.data.items[definition.buff_template_id].buff
                if definition.buff_classes is not None:
                    buff = replace(buff, classes=frozenset(definition.buff_classes))
                # Reuse rate, class admission and expiry scheduling, without
                # adding a fresh potion's duration or replaying its use sound.
                if self.world.apply_buff(uid, replace(buff, add_s=remaining)) is None:
                    continue
                speed = True
            self.remember_potion(uid, template, now)
        if not speed:
            decision['outcome'] = 'RESUMED_NO_SPEED'
            decision['after_resume'] = _consumable_owner_snapshot(self, uid)
            return ()
        from tools.local_original_session.world_combat import speed_frame
        decision['outcome'] = 'RESUMED_SPEED'
        decision['after_resume'] = _consumable_owner_snapshot(self, uid)
        return (speed_frame(uid, self.combat.speed_factor(uid, now)),)

    def _icon_deadline(self, uid, template_id):
        pc = self.combat.pcs.get(uid)
        if pc is None or pc.dead or pc.hp <= 0:
            return 0.0
        kind = CONSUMABLE_BUFF_ICONS[template_id][2]
        if kind in ('haste', 'brave'):
            return pc.buffs.get(kind, (0.0, 0))[0]
        if kind == 'wisdom':
            return self.state(uid).wisdom_until
        if kind == 'breath':
            return self.state(uid).breath_until
        effect = self.active.get(uid, {}).get(kind)
        return effect.until if effect is not None and effect.state is pc else 0.0

    def icon_frames(self, uid, template_id, now, *, remember=True):
        """Owner-only publication proposal after successful PC admission.

        Transactional callers use remember=False while proposing, then remember
        only after their durable commit. Companion use never calls this path.
        """
        if remember:
            self.remember_potion(uid, template_id, now)
        mapping = CONSUMABLE_BUFF_ICONS.get(template_id)
        if mapping is None:
            return ()
        until = self._icon_deadline(uid, template_id)
        if until <= now:
            return ()
        catalog, key, _ = mapping
        if remember:
            self.icons.setdefault(uid, {})[key] = (self.combat.pcs[uid], template_id)
        return (buff_icon_frame(catalog, key, until - now),)

    def resend_icons(self, uid, now, *, remember=True, skip_saved=False):
        """Re-enter only effects that still have real authority at this clock.

        Saved potions have already been restored to this binding's owners.
        Relocation uses remember=False to replay display without changing state.
        """
        pc = self.combat.pcs.get(uid)
        templates = [template for binding, template in self.icons.get(uid, {}).values()
                     if binding is pc]
        state = self.state(uid) if remember else self.states.get(uid)
        templates.extend(template for template in (() if state is None else state.potions)
                         if template in CONSUMABLE_BUFF_ICONS and template not in templates)
        if state is not None and state.wisdom_until > now and 297 not in templates:
            templates.append(297)
        if (state is not None and state.breath_until > now
                and not any(template in templates for template in (417, 418))):
            templates.append(417)  # both items own the same saved breath deadline/K
        if skip_saved:
            templates = [template for template in templates if template not in SAVED_POTIONS]
        return tuple(wire for template in templates
                     for wire in self.icon_frames(uid, template, now, remember=remember))

    def replay_saved_potions(self, uid, now):
        """Rebuild each saved item's use display from its current effect owner."""
        pc = self.combat.pcs.get(uid)
        if pc is None or pc.dead or pc.hp <= 0:
            return ()
        from tools.local_original_session.world_combat import speed_frame

        frames = []
        for template in tuple(self.state(uid).potions):
            kind = SAVED_POTIONS[template]
            if kind in ('haste', 'brave'):
                if pc.buffs.get(kind, (0,))[0] <= now:
                    continue
            else:
                effect = self.active.get(uid, {}).get(kind)
                if effect is None or effect.state is not pc or effect.until <= now:
                    continue
            use_effect = self.use_effect_frame(uid, template)
            if use_effect is not None:
                frames.append(use_effect)
            if kind in ('haste', 'brave'):
                frames.append(speed_frame(uid, self.combat.speed_factor(uid, now)))
            frames.extend(self.icon_frames(uid, template, now))
        return tuple(frames)

    def remove_icons(self, uid):
        """Remove this binding's HUD rows through the existing owner outbox."""
        rows = self.icons.pop(uid, {})
        pc = self.combat.pcs.get(uid)
        if self.world is not None and not self.world.closed:
            for key, (binding, template) in rows.items():
                if binding is pc:
                    self.world._queue(uid, buff_icon_frame(
                        CONSUMABLE_BUFF_ICONS[template][0], key, 0, remove=True))

    def _expire_icons(self, now):
        queued = False
        for uid, rows in tuple(self.icons.items()):
            pc = self.combat.pcs.get(uid)
            for key, (binding, template) in tuple(rows.items()):
                if binding is pc and self._icon_deadline(uid, template) > now:
                    continue
                del rows[key]
                # A reused UID belongs to a new client binding, never to the
                # old potion's cleanup. No broadcast to nearby players.
                if binding is pc and not self.world.closed:
                    self.world._queue(uid, buff_icon_frame(
                        CONSUMABLE_BUFF_ICONS[template][0], key, 0, remove=True))
                    queued = True
            if not rows:
                self.icons.pop(uid, None)
        if queued:
            self.world._announce()

    def state(self, uid):
        return self.states.setdefault(uid, ConsumableState())

    def project_fullness(self, uid, *, commit=True):
        """LOCAL225 nutrition -> fixed-client0..100 percent, with floor policy.

        CONTROL9A92B2 formats info+B4 as {}%;9A9353..9A93B8 decodes that
        same Hungry value and clamps it to0..100 for the gauge. The100.0
        constant is126ED50.225 and integer rounding remain server policy.
        A transactional proposal must not change the live full status early.
        """
        pc = self.combat.pcs.get(uid)
        if pc is None:
            return None
        percent = self.state(uid).fullness * 100 // 225
        if pc.status_fields.get(16) == percent:
            return None
        fields = dict(pc.status_fields)
        fields[16] = percent
        if commit:
            pc.status_fields[16] = percent
        return status_frame(fields, pc.hp)

    def spell_power(self, uid, now):
        """Official SP+2; the optional spell_power hook supplies damage consumers."""
        pc = self.combat.pcs.get(uid)
        return 2 if (pc is not None and pc.profile.character_class == 3
                     and self.state(uid).wisdom_until > now) else 0

    def can_breathe(self, uid, now):
        return self.state(uid).breath_until > now

    def can_unequip(self, uid, item_uid):
        """Legacy saved curses and explicit saved instance grade share authority."""
        frame = getattr(self, 'inventory_frame', lambda: None)()
        if frame is not None:
            from tools.local_original_session import inventory
            item = next((item for item in inventory.validate_kit_frame(frame)
                         if item.identifier == item_uid), None)
            if item is not None and item.cursed:
                return False
        return item_uid not in self.state(uid).curses

    def item_label(self, uid, item_uid):
        """Explicit LOCAL inspection label; canonical equipment f18 stays intact."""
        return '확인됨' if item_uid in self.state(uid).identified else '미확인'

    def _observe(self, uid, now):
        world, pc = self.world, self.combat.pcs.get(uid)
        if world is None or world.closed or pc is None or pc.dead:
            self.observers.pop(uid, None)
            return
        previous = self.observers.get(uid)
        current = world.regen.get(uid)
        if previous is None or previous[0] is not pc:
            self.observers[uid] = (pc, current, now + 300)
            frame = self.project_fullness(uid)
            if frame is not None:
                world._queue(uid, frame)
                world._announce()
            return
        _, handle, hunger_at = previous
        state, changed = self.state(uid), False
        if now >= hunger_at:
            # One live depletion per boundary. Never replay a stalled/offline clock.
            state.fullness = max(0, state.fullness - 1)
            hunger_at, changed = now + 300, True
        if (handle is not None and handle.done and not handle.cancelled
                and current is not handle and pc.hp_points == 0):
            # Existing natural HP threshold is the actual consumer. Nutrition
            # adds one HP at that threshold; it creates no second regen timer.
            if state.fullness >= 3 and 0 < pc.hp < pc.max_hp:
                pc.hp = min(pc.max_hp, pc.hp + 1)
                world._queue(uid, status_frame(pc.status_fields, pc.hp))
                world._announce()
        self.observers[uid] = (pc, current, hunger_at)
        if changed and self.store is not None:
            self.capture_potions(uid)
            self.store.save(uid, state, now)
        if changed:
            frame = self.project_fullness(uid)
            if frame is not None:
                world._queue(uid, frame)
                world._announce()

    def attach(self, world, *, magic=None, magic_save=None, cure_poison=None):
        """Optional lifecycle integration; no combat method or class is replaced."""
        if self.world is not None:
            self.detach()
        self.world, self.magic, self.magic_save = world, magic, magic_save
        self.cure_poison = cure_poison
        world.runtime.add_tick_hook(self.tick)
        self.leave_listener = world.events.add('consumable-effects', 'before_pc_leave',
                                              lambda uid: self.capture_potions(uid, pause=True))

    def detach(self):
        if self.world is not None:
            self.world.runtime.remove_tick_hook(self.tick)
            self.world.events.remove('before_pc_leave', self.leave_listener)
        self.active.clear()
        self.observers.clear()
        self.icons.clear()
        self.bindings.clear()
        self.leave_listener = None
        self.world = self.magic = self.magic_save = None
        self.cure_poison = None

    def tick(self, now):
        """Add blue's bonus only after the existing natural MP recovery fired.

        WorldRuntime runs scheduled recovery before hooks. The captured handle
        being done proves that recovery actually ran; mp_points == 0 proves its
        MP threshold was reached (including a full-MP recovery). No second
        recovery timer, activity accounting, threshold or catch-up is created.
        """
        world = self.world
        if world is None:
            return
        self._expire_icons(now)
        for uid in tuple(self.combat.pcs):
            self._observe(uid, now)
        for uid, effects in tuple(self.active.items()):
            for kind, effect in tuple(effects.items()):
                state = self.combat.pcs.get(uid)
                if (world.closed or state is not effect.state or state.dead
                        or state.hp <= 0 or now >= effect.until):
                    del effects[kind]
                    continue
                handle = effect.regen_handle
                current = world.regen.get(uid)
                if (kind == 'mana_regen' and handle is not None and handle.done
                        and not handle.cancelled and current is not handle
                        and state.mp_points == 0 and state.mp is not None
                        and state.max_mp is not None):
                    before = state.mp
                    state.status_fields[12] = min(state.max_mp,
                        before + max(state.profile.wis, 11) - 5)
                    if state.mp != before:
                        world._queue(uid, status_frame(state.status_fields, state.hp))
                        world._announce()
                effect.regen_handle = current
            if not effects:
                self.active.pop(uid, None)

    def use(self, uid: int, template_id: int, now: float, *,
            position: MapDestination | None = None,
            ailments: PcAilments | None = None,
            owned_uids: tuple[int, ...] = (), target_uid: int | None = None,
            equipped_uids: tuple[int, ...] = (), remember_icon: bool = True) -> ItemEffectResult:
        result = self._use(uid, template_id, now, position=position, ailments=ailments,
                           owned_uids=owned_uids, target_uid=target_uid, equipped_uids=equipped_uids)
        frame = (teleport_effect_frame(uid)
                 if result.outcome == 'destination_proposed'
                 and result.kind in ('return_town', 'random_teleport', 'tower_teleport')
                 else self.use_effect_frame(uid, template_id, result))
        icons = (self.icon_frames(uid, template_id, now, remember=remember_icon)
                 if result.outcome == 'applied' else ())
        if result.outcome == 'applied' and result.kind == 'food':
            hunger = self.project_fullness(uid, commit=remember_icon)
            if hunger is not None:
                result = replace(result, frames=result.frames + (hunger,))
        return replace(result, frames=(() if frame is None else (frame,)) + result.frames + icons)

    def use_effect_frame(self, uid: int, template_id: int, result=None):
        """Leading 4ED8 for a consumed use (L1J C_ItemUSe S_SkillSound), or None.

        Heal and cure-poison show their sound even without a change (L1J sends
        it unconditionally); other kinds only when the effect applied.
        """
        definition = self.definitions.get(template_id) or self.extended.get(template_id)
        return item_use_effect_frame(uid, definition, result)

    def _use(self, uid: int, template_id: int, now: float, *,
             position: MapDestination | None = None,
             ailments: PcAilments | None = None,
             owned_uids: tuple[int, ...] = (), target_uid: int | None = None,
             equipped_uids: tuple[int, ...] = ()) -> ItemEffectResult:
        definition = self.definitions.get(template_id) or self.extended.get(template_id)
        if definition is None:
            return ItemEffectResult(template_id, 'unknown', 'unsupported', reason='CLASSIC_ITEM_NOT_SUPPORTED')
        kind = definition.kind
        state = self.combat.pcs.get(uid)
        if state is None or state.dead or state.hp <= 0:
            return ItemEffectResult(template_id, kind, 'refused', reason='LIVING_BOUND_PC_REQUIRED')
        if kind in ('food', 'wisdom', 'underwater_breath', 'identify', 'remove_curse'):
            item_state = self.state(uid)
            if kind == 'food':
                if item_state.fullness >= 225:
                    return ItemEffectResult(template_id, kind, 'refused', reason='FOOD_ALREADY_FULL')
                item_state.fullness = min(225, item_state.fullness + definition.nutrition)
            elif kind == 'wisdom':
                if state.profile.character_class != 3:
                    return ItemEffectResult(template_id, kind, 'refused', reason='WISDOM_MAGE_REQUIRED')
                item_state.wisdom_until = now + definition.duration_s
            elif kind == 'underwater_breath':
                # LOCAL refresh policy: a shorter item never shortens Eva.
                item_state.breath_until = max(item_state.breath_until, now + definition.duration_s)
            else:
                targets = set(owned_uids)
                if target_uid is not None:
                    if target_uid not in targets:
                        return ItemEffectResult(template_id, kind, 'refused', reason='OWNED_ITEM_TARGET_REQUIRED')
                    targets = {target_uid}
                if kind == 'identify':
                    # No pre-existing unidentified model: explicitly mark owned
                    # rows as identified rather than claiming hidden-stat discovery.
                    item_state.identified.update(targets)
                else:
                    targets.intersection_update(equipped_uids)
                    removed = targets & item_state.curses
                    if not removed:
                        return ItemEffectResult(template_id, kind, 'refused', reason='NO_OWNED_CURSED_ITEM')
                    item_state.curses.difference_update(removed)
            return ItemEffectResult(template_id, kind, 'applied', 1,
                reason={'wisdom': 'SP_STATE_AVAILABLE_TO_REGISTERED_DAMAGE_CONSUMERS',
                        'underwater_breath': 'BREATH_STATE_AVAILABLE_TO_REGISTERED_ENVIRONMENT_CONSUMERS',
                        'identify': 'LOCAL_IDENTIFIED_ITEM_LABEL',
                        'remove_curse': 'LOCAL_ITEM_CURSE_REMOVED',
                        'food': 'LOCAL_FULLNESS_AND_NATURAL_HP_BONUS'}[kind])
        if kind == 'heal':
            if definition.heal_hp_range is None:
                healed, frame = self.combat.heal(uid, definition.heal_hp)
            else:
                before = state.hp
                amount = self.rng.randint(*definition.heal_hp_range)
                state.hp = min(state.max_hp, before + amount)
                healed = state.hp - before
                frame = status_frame(state.status_fields, state.hp)
            return ItemEffectResult(template_id, kind, 'applied' if healed else 'no_effect',
                                    1, (frame,), healed_hp=healed)
        if kind == 'speed':
            # Use the existing data definition/rate and existing stacking and
            # class handling. Greater haste differs only in added duration.
            buff = self.combat.data.items[definition.buff_template_id].buff
            if definition.buff_add_s is not None:
                buff = replace(buff, add_s=definition.buff_add_s)
            if definition.buff_classes is not None:
                buff = replace(buff, classes=frozenset(definition.buff_classes))
            effect = self.combat.apply_buff(uid, buff, now)
            if effect is None:
                return ItemEffectResult(template_id, kind, 'no_effect', 1, reason='CLASS_HAS_NO_EFFECT')
            expiry, frame = effect
            requirements = (() if template_id in CONSUMABLE_BUFF_ICONS else
                (FrameRequirement('speed_buff_icon', 0x4E91,
                    'Consumable BuffIconInfo catalog and K remain UNSUPPLIED '
                    'for this template; f2=1/f3 simulation seconds are known.'),))
            return ItemEffectResult(template_id, kind, 'applied', 1, (frame,),
                requirements=requirements,
                buff_kind=buff.kind, buff_expires_at=expiry)
        if kind == 'mana_regen':
            if self.world is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='RECOVERY_RUNTIME_UNSUPPLIED')
            effects = self.active.setdefault(uid, {})
            previous = effects.get(kind)
            remaining = (max(0.0, previous.until - now)
                         if previous is not None and previous.state is state else 0.0)
            until = now + min(remaining + definition.duration_s, definition.duration_cap_s)
            effects[kind] = PendingPotion(state, until, self.world.regen.get(uid))
            # buff_kind is intentionally absent: that existing result field is
            # the speed owner's scheduler, not a mana expiry callback.
            return ItemEffectResult(template_id, kind, 'applied', 1)
        if kind == 'blind':
            if self.magic is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='MAGIC_STATUS_OWNER_UNSUPPLIED')
            effects = self.magic.state(uid).effects
            effects.pop('darkness', None)
            self.magic.apply_status(uid, 'blind', now, definition.duration_s, source_uid=uid)
            if self.magic_save is not None:
                self.magic_save(uid, now)
            return ItemEffectResult(template_id, kind, 'applied', 1,
                requirements=(FrameRequirement('blind_display', None,
                    'Server sight=1 uses existing magic consumers; native curse display wire UNKNOWN.'),))
        if kind == 'cure_poison':
            if ailments is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='POISON_STATE_UNSUPPLIED')
            cured = ailments.poison is not None
            ailments.poison = None
            magic_state = None if self.magic is None else self.magic.states.get(uid)
            previous_effects = None if magic_state is None else dict(magic_state.effects)
            if magic_state is not None:
                cured = cured or magic_state.poison is not None
                magic_state.poison = None
            if self.cure_poison is not None:
                self.cure_poison(uid)
            if magic_state is not None:
                cured = cured or previous_effects != magic_state.effects
                if self.magic_save is not None:
                    self.magic_save(uid, now)
            return ItemEffectResult(template_id, kind, 'applied' if cured else 'no_effect', 1,
                requirements=(FrameRequirement('poison_status', None,
                    'Native poison-state display/sound wire UNKNOWN; poison owner must cancel its ticker.'),),
                poison_cured=cured)
        if position is None:
            return ItemEffectResult(template_id, kind, 'refused', reason='CURRENT_POSITION_REQUIRED')
        if kind == 'return_town':
            return return_town_result(template_id, position, self.combat.data.town)
        elif kind == 'tower_teleport':
            if definition.entry_bounds is not None:
                map_id, min_x, min_y, max_x, max_y = definition.entry_bounds
                if not (position.map_id == map_id and min_x <= position.x <= max_x
                        and min_y <= position.y <= max_y):
                    return ItemEffectResult(template_id, kind, 'refused',
                                            reason='TOWER_CHARM_ENTRY_AREA_REQUIRED')
            else:
                # LOCAL L1J escapable policy, shared with remembered places.
                # Tower101..120: l1jdb_m10.sql:19289..19308, escapable=1.
                from tools.local_original_session.world_bookmark import location_allowed
                try:
                    allowed = (101 <= position.map_id <= 120
                               or location_allowed(position.map_id))
                except ValueError:
                    return ItemEffectResult(template_id, kind, 'refused',
                                            reason='TOWER_DEPARTURE_POLICY_UNKNOWN')
                if not allowed:
                    return ItemEffectResult(template_id, kind, 'refused',
                                            reason='TOWER_DEPARTURE_NOT_ESCAPABLE')
            if definition.destination is None:
                return ItemEffectResult(template_id, kind, 'unsupported',
                                        reason='TOWER_DESTINATION_UNSUPPLIED')
            destination = MapDestination(*definition.destination, 5)
            return ItemEffectResult(template_id, kind, 'destination_proposed',
                definition.consume_count, destination=destination,
                requirements=movement_requirements(position.map_id, destination),
                reason='LOCAL_TOWER_DESTINATION_MAPPING_POSITION_NOT_COMMITTED')
        elif kind == 'random_teleport':
            if self.terrain is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='TERRAIN_UNSUPPLIED')
            destination = random_destination(position, self.terrain, self.rng, definition.teleport_radius)
            if destination is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='NO_KNOWN_STANDABLE_DESTINATION')
        else:
            return ItemEffectResult(template_id, kind, 'unsupported', reason='EFFECT_NOT_SUPPORTED')
        return ItemEffectResult(template_id, kind, 'destination_proposed', 1,
            requirements=movement_requirements(position.map_id, destination), destination=destination,
            reason='POSITION_AND_NATIVE_WIRE_NOT_COMMITTED')


def _consumable_trace(effects, **event):
    """Bounded packet/lifetime facts for the existing broker result JSON."""
    effects.restore_trace.append(event)
    del effects.restore_trace[:-16]
    return event


def _consumable_owner_snapshot(effects, uid):
    """Read-only object/row facts; no state() creation or save writes."""
    store = effects.store
    rows = None if store is None else getattr(store, 'rows', None)
    row = rows.get(uid) if type(rows) is dict else None
    state = effects.states.get(uid)
    pc = effects.combat.pcs.get(uid)
    binding = effects.bindings.get(uid)
    ref = lambda value: None if value is None else hex(id(value))
    return dict(uid=uid, effects_id=ref(effects), store_id=ref(store),
        rows_id=ref(rows), store_row_id=ref(row),
        store_potion_remaining=(dict(row.get('potion_remaining', {})) if row is not None else None),
        states_id=ref(effects.states), state_id=ref(state),
        state_potions=(dict(state.potions) if state is not None else None),
        state_paused=(state.potions_paused if state is not None else None),
        pc_id=ref(pc), pc_hp=(pc.hp if pc is not None else None),
        pc_dead=(pc.dead if pc is not None else None), binding_id=ref(binding),
        binding_is_pc=(binding is pc if pc is not None else False),
        entry_loaded=uid in effects.entry_loaded_uids)


def _world_consumable_started(ctx):
    effects = ctx._world_item_effects
    effects.inventory_frame = lambda: ctx.inventory_frame
    provider = next((value for value in
        ctx.collect_sync_hooks('consumable_magic_provider') if value is not None), None)
    magic, save = (None, None) if provider is None else provider
    effects.attach(ctx.world, magic=magic, magic_save=save,
                   cure_poison=lambda uid: ctx.run_sync_hooks('cure_poison', uid))
    effects.entry_loaded_uids.clear()
    effects.last_resume_decision = None
    inventory_store = getattr(ctx, 'inventory_store', None)
    if inventory_store is not None:
        effects.store = ConsumableStore(inventory_store)
        now = ctx.world.runtime.clock()
        effects.states = {uid: consumable_restore(row, now)
                          for uid, row in effects.store.rows.items()}
    _consumable_trace(effects, phase='runtime_started', store_present=effects.store is not None,
        loaded=[dict(uid=uid, potion_remaining=dict(row.get('potion_remaining', {})))
                for uid, row in sorted(effects.store.rows.items())]
               if effects.store is not None else [],
        owners=[_consumable_owner_snapshot(effects, uid) for uid in sorted(effects.states)])


def _world_consumable_before_enter(ctx, writer, row, game, operation_lock):
    uid = ctx.realm.service(writer).snapshot().uid
    _consumable_trace(ctx._world_item_effects, phase='pre_before_enter',
                      owner=_consumable_owner_snapshot(ctx._world_item_effects, uid))


def _world_consumable_entry_probe(ctx, phase, uid):
    effects = ctx._world_item_effects
    _consumable_trace(effects, phase=phase,
        owner=_consumable_owner_snapshot(effects, uid),
        resume_decision=(effects.last_resume_decision if phase == 'post_bind_pc' else None))


def _world_consumable_pc_bound(ctx, uid):
    effects = ctx._world_item_effects
    effects.restore_potions(uid, ctx.world.runtime.clock())
    frame = effects.project_fullness(uid)
    if frame is not None:
        ctx.world._queue(uid, frame)


def _world_consumable_stopped(ctx):
    effects = ctx._world_item_effects
    try:
        if effects.store is not None:
            for uid in tuple(ctx.world.combat.pcs):
                effects.capture_potions(uid)
                effects.store.save(uid, effects.state(uid), ctx.world.runtime.clock())
    finally:
        effects.detach()


async def _world_consumable_before_leave(ctx, writer, uid):
    effects = ctx._world_item_effects
    event = _consumable_trace(effects, phase='before_leave', uid=uid, stage='STARTED',
                              owner_before=_consumable_owner_snapshot(effects, uid))
    def save():
        effects.capture_potions(uid)
        event['stage'] = 'CAPTURED'
        event['potion_remaining'] = consumable_snapshot(
            uid, effects.state(uid), ctx.world.runtime.clock())['potion_remaining']
        if effects.store is not None:
            effects.store.save(uid, effects.state(uid), ctx.world.runtime.clock())
        event['stage'] = 'SAVED'
        event['owner_after'] = _consumable_owner_snapshot(effects, uid)
    try:
        await ctx.world.runtime.dispatch_now(save)
    except BaseException as error:
        event['error'] = type(error).__name__
        event['detail'] = str(error)[:120]
        raise


def _world_consumable_died(ctx, uid):
    effects = ctx._world_item_effects
    event = _consumable_trace(effects, phase='after_death', uid=uid,
                              owner_before=_consumable_owner_snapshot(effects, uid))
    effects.remove_icons(uid)
    effects.active.pop(uid, None)
    state = effects.states.get(uid)
    if state is not None:
        state.wisdom_until = state.breath_until = 0
        state.potions.clear()
        if effects.store is not None:
            effects.store.save(uid, state, ctx.world.runtime.clock())
    effects.observers.pop(uid, None)
    event['owner_after'] = _consumable_owner_snapshot(effects, uid)


def _world_consumable_left(ctx, *args):
    effects = ctx._world_item_effects
    for uid, rows in tuple(effects.active.items()):
        if any(row.state is not ctx.world.combat.pcs.get(uid) for row in rows.values()):
            effects.active.pop(uid, None)
    for uid in tuple(effects.observers):
        if uid not in ctx.world.combat.pcs:
            effects.observers.pop(uid, None)
    for uid, rows in tuple(effects.icons.items()):
        if any(binding is not ctx.world.combat.pcs.get(uid) for binding, _ in rows.values()):
            effects.icons.pop(uid, None)


def _consumable_params(payload):
    """Existing raw0 and targeted ItemUse recipes; no invented target field."""
    from tools.local_entry_server import protobuf as pb
    with pb.parse_message(payload, limits=pb.WireLimits(
            max_body=128, max_fields=5, max_field_bytes=16)) as parsed:
        values = {}
        for member in parsed.fields:
            if member.wire_type != 0 or member.number in values:
                raise ValueError('CONSUMABLE_ITEM_PARAMS')
            values[member.number] = member.value
        expected = {1: 1, 15: 0, 16: 0}
        if 2 in values:
            expected.update({2: values[2], 3: 0})
            if not 0 < values[2] <= 0xffffffff:
                raise ValueError('CONSUMABLE_TARGET_UID')
        if values != expected:
            raise ValueError('CONSUMABLE_ITEM_PARAMS')
        return values.get(2)


def consumable_mutation(before, item_uid, kind, previous, proposed, targets, *, definitions=None):
    """Existing kit DTOs only: real quantity; canonical names stay intact.

    Keep a drained Q0 row so this optional participant never moves the saved
    equipment anchor. No UID allocation, equipment mutation or guessed flags.
    """
    from tools.local_original_session import inventory, inventory_update
    rows, frames = [], []
    for item in inventory.validate_kit_frame(before):
        values = dict(item.raw_fields)
        changed = {1: item.identifier}
        if item.identifier == item_uid:
            if values[4] <= 0:
                raise ValueError('CONSUMABLE_POSITIVE_STACK_REQUIRED')
            values[4] -= 1
            changed[4] = values[4]
        if kind == 'remove_curse' and item.identifier in targets and item.cursed:
            from tools.local_original_session import world_enchant_inventory as enchant
            if definitions is None or item.template_bits not in definitions:
                raise ValueError('CURSE_ITEM_DEFINITION_REQUIRED')
            definition = definitions[item.template_bits]
            values[18] = enchant.enchanted_name(definition, enchant.enchant_level(item, definition))
            changed[18] = values[18]
        rows.append(values)
        if len(changed) > 1:
            frames.append(inventory_update._encode(inventory_update._values(changed)))
    return inventory.build_kit_frame(rows), tuple(frames)


def identified_projection(frame, state):
    """Display-only 0965; saved kit/enchantment names remain owner-canonical."""
    from tools.local_original_session import inventory, inventory_update
    frames = []
    for item in inventory.validate_kit_frame(frame):
        if item.identifier not in state.identified or dict(item.raw_fields)[4] <= 0:
            continue
        name = dict(item.raw_fields)[18]
        label = (name + b' ' + '[확인됨]'.encode('utf-8')).strip()
        # The 0965 callback (4F7670) copies f18 verbatim and its unchanged
        # quantity adds no suffix: a stack label must already carry " (Q)".
        from tools.local_original_session.world_core_kit import display_name
        label = display_name(label, dict(item.raw_fields)[4])
        # Native max string size is owned by the existing codec. If a canonical
        # name is already at its bound the LOCAL query remains the label source.
        if len(label) <= inventory_update.MAX_BYTES:
            frames.append(inventory_update._encode(inventory_update._values({1: item.identifier, 18: label})))
    return tuple(frames)


async def _world_consumable_enter(ctx, writer, row, game, operation_lock, *, phase='direct'):
    effects = ctx._world_item_effects
    bound = getattr(ctx, '_world_pcs', {}).get(id(writer))
    if bound is None or bound[0] is not writer:
        _consumable_trace(effects, phase=phase, status='NO_BOUND_PC')
        return
    event = _consumable_trace(effects, phase=phase, uid=bound[1], status='ENTERED',
                              drained_chunks=0,
                              owner_before=_consumable_owner_snapshot(effects, bound[1]))
    def enter():
        now = ctx.world.runtime.clock()
        state = effects.state(bound[1])
        event['saved_templates_before'] = sorted(state.potions)
        event['paused_before'] = state.potions_paused
        effects.restore_potions(bound[1], now)
        event['resume_decision'] = effects.last_resume_decision
        state = effects.state(bound[1])
        event['active_templates_after'] = sorted(state.potions)
        event['owner_after'] = _consumable_owner_snapshot(effects, bound[1])
        effects._observe(bound[1], now)
        # Selection precedes AddInventory. Restore the server deadlines now,
        # then publish the client HUD only after that kit has drained.
        event['inventory_frame_present'] = ctx.inventory_frame is not None
        if ctx.inventory_frame is None:
            return ()
        wires = (effects.replay_saved_potions(bound[1], now)
                 + effects.resend_icons(bound[1], now, skip_saved=True))
        return wires + identified_projection(ctx.inventory_frame, effects.state(bound[1]))
    wires = await ctx.world.runtime.dispatch_now(enter)
    from tools.local_original_session.world_bridge import WORLD_SEND_CHUNK
    event['proposed_opcodes'] = [int.from_bytes(wire[2:4], 'little') for wire in wires]
    event['status'] = 'NO_FRAMES' if not wires else 'SENDING'
    for start in range(0, len(wires), WORLD_SEND_CHUNK):
        chunk = tuple(wires[start:start + WORLD_SEND_CHUNK])
        try:
            await ctx.send(writer, row, chunk, game=True, operation_lock=operation_lock, world_operation=chunk)
        except BaseException as error:
            event['status'] = 'SEND_FAILED'
            event['error'] = type(error).__name__
            event['detail'] = str(error)[:120]
            raise
        event['drained_chunks'] += 1
    if wires:
        event['status'] = 'DRAINED'


async def _world_consumable_after_enter(ctx, writer, row, game, operation_lock):
    await _world_consumable_enter(ctx, writer, row, game, operation_lock, phase='after_enter')


async def _world_consumable_inventory_delivered(ctx, writer, row, game, operation_lock):
    await _world_consumable_enter(ctx, writer, row, game, operation_lock, phase='inventory_delivered')


def _world_consumable_report(ctx, result):
    result['consumable_restore'] = [dict(event) for event in ctx._world_item_effects.restore_trace]


def _world_consumable_after_relocate(ctx, uid, transit):
    """Replay current speed and item HUD after the new self Actor."""
    effects = ctx._world_item_effects
    now = ctx.world.runtime.clock()
    factor = effects.combat.speed_factor(uid, now)
    from tools.local_original_session.world_combat import speed_frame
    speed = () if factor == 1 else (speed_frame(uid, factor),)
    return speed + effects.resend_icons(uid, now, remember=False)


async def _world_consumable_unsupported(ctx, writer, row, game, frame, operation_lock):
    """Optional second-wave lane, after existing handlers declined its rows.

    New definitions deliberately have their own dispatcher owner: the legacy
    item lane spends before applying. Admission and refusal happen here first.
    """
    from tools.local_entry_server import protobuf as pb
    from tools.local_original_session import inventory
    if ctx.selected_session(writer) is not game:
        return False
    try:
        with pb.parse_message(frame.payload, limits=pb.WireLimits(
                max_body=4096, max_fields=2, max_field_bytes=2048)) as parsed:
            values = parsed.occurrences(1)
            if len(values) != 1 or values[0].wire_type != 0:
                return False
            item_uid = values[0].value
        item = next((item for item in inventory.validate_kit_frame(ctx.inventory_frame)
                     if item.identifier == item_uid), None)
    except (ValueError, pb.WireError):
        return False
    effects = ctx._world_item_effects
    if item is None or item.template_bits not in (effects.extended.keys() | effects.unsupported.keys()):
        return False

    def refuse(reason):
        ctx._world_item_errors = (ctx._world_item_errors + [reason])[-4:]

    if item.template_bits in effects.unsupported:
        reason = {806: 'CLAN_MEMBERSHIP_AND_HOME_DESTINATION_UNSUPPLIED',
                  15400: 'TOWER_FLOOR1_DESTINATION_AND_ENTRY_UNSUPPLIED',
                  15457: 'TOWER_SEAL_RELEASE_RESULT_UNSUPPLIED'}.get(
                      item.template_bits, f'ITEM_EFFECT_UNSUPPORTED:{item.template_bits}')
        refuse(reason)
        return True
    bound = getattr(ctx, '_world_pcs', {}).get(id(writer))
    if (bound is None or bound[0] is not writer or effects.store is None
            or row.get('writer') is not writer or not operation_lock.locked()
            or ctx.world is None or ctx.world.closed or game.selection is None):
        refuse('CONSUMABLE_CURRENT_WORLD_OWNER_REQUIRED')
        return True
    try:
        with pb.parse_message(frame.payload) as parsed:
            members = parsed.occurrences(2)
            if len(parsed.fields) != 2 or len(members) != 1 or members[0].wire_type != 2:
                raise ValueError('CONSUMABLE_PARENT_FIELDS')
            target_uid = _consumable_params(bytes(members[0].value))
    except (ValueError, pb.WireError) as error:
        refuse(str(error))
        return True
    uid, attempted = bound[1], False

    def apply():
        nonlocal attempted
        if ctx.selected_session(writer) is not game or getattr(ctx, '_world_pcs', {}).get(id(writer)) != bound:
            raise ValueError('CONSUMABLE_CURRENT_WORLD_OWNER_REQUIRED')
        position = ctx.realm.service(writer).snapshot()
        if position.uid != uid or not ctx.owner_current(writer, row, position):
            raise ValueError('CONSUMABLE_CURRENT_SELECTION_REQUIRED')
        before = ctx.inventory_frame
        members = inventory.validate_kit_frame(before)
        current = next((v for v in members if v.identifier == item_uid), None)
        if current is None or current.template_bits != item.template_bits or dict(current.raw_fields)[4] <= 0:
            raise ValueError('CONSUMABLE_OWNED_POSITIVE_STACK_REQUIRED')
        if effects.store.pending is not None:
            raise ValueError('CONSUMABLE_RECOVERY_REQUIRED')
        owned = tuple(v.identifier for v in members if dict(v.raw_fields)[4] > 0)
        equipment_owner = getattr(ctx, '_item_equipment_effect', None)
        equipment = None
        if equipment_owner is not None:
            equipment, _ = equipment_owner.store.peek(uid)
        elif item.template_bits == 24:
            # Headless/local hosts may consume the ordinary saved equipment
            # without an interactive equipment service. Read that same owner;
            # an absent service is not evidence that the saved PC is unworn.
            from tools.local_original_session import equipment_store
            equipment, _ = equipment_store.EquipmentStore(ctx.inventory_store,
                policy=equipment_store.POLICY, kit_policy=inventory.KIT_POLICY,
                item_defs=ctx.world.data.items).peek(uid)
        worn = (() if equipment is None else
                (equipment.weapon_uid, *(v for _, v in equipment.slots)))
        previous = effects.state(uid)
        effects.capture_potions(uid)
        proposed = deepcopy(previous)
        proposed.curses.update(v.identifier for v in members if v.cursed)
        effects.states[uid] = proposed
        now = ctx.world.runtime.clock()
        try:
            result = effects.use(uid, item.template_bits, now, owned_uids=owned,
                                 target_uid=target_uid, equipped_uids=worn, remember_icon=False)
            if result.outcome != 'applied':
                raise ValueError(result.reason)
            targets = set(owned) if target_uid is None else {target_uid}
            after, wires = consumable_mutation(before, item_uid, result.kind, previous, proposed,
                targets & set(worn) if result.kind == 'remove_curse' else targets,
                definitions=ctx.world.data.items)
        except Exception:
            effects.states[uid] = previous
            raise
        effects.states[uid] = previous
        attempted = True
        effects.store.commit(uid, before, after, proposed, now)
        effects.states[uid] = proposed
        if result.kind == 'food':
            effects.project_fullness(uid)  # only after the durable kit/state commit
        effects.icon_frames(uid, item.template_bits, now)  # committed result.frames owns sending
        ctx.inventory_frame = after
        effects._observe(uid, now)
        labels = identified_projection(after, proposed) if result.kind == 'identify' else ()
        ctx.world.broadcast_pc_effects(uid, result.frames)
        return (*ctx.world.drain(uid), *wires, *result.frames, *labels)

    try:
        wires = await ctx.world.runtime.dispatch_now(apply)
    except ValueError as error:
        if attempted:
            raise  # forward intent/partial save belongs to startup recovery
        refuse(str(error))
        return True
    if wires:
        from tools.local_original_session.world_bridge import WORLD_SEND_CHUNK
        for start in range(0, len(wires), WORLD_SEND_CHUNK):
            chunk = tuple(wires[start:start + WORLD_SEND_CHUNK])
            await ctx.send(writer, row, chunk, game=True, operation_lock=operation_lock,
                           world_operation=chunk)
    return True


def _world_consumable_breathing(ctx, uid, now):
    return ctx._world_item_effects.can_breathe(uid, now)


def _world_consumable_spell_power(ctx, value, uid, now):
    """Optional items contribution; consumers do not access this feature's state."""
    return value + ctx._world_item_effects.spell_power(uid, now)


def _world_curse_targets(ctx, uid):
    """Registered query: owned, positive, currently worn cursed item UIDs."""
    from tools.local_original_session import inventory, equipment_store
    if ctx.inventory_frame is None or uid not in ctx.world.combat.pcs:
        return ()
    owner = getattr(ctx, '_item_equipment_effect', None)
    store = (owner.store if owner is not None else equipment_store.EquipmentStore(
        ctx.inventory_store, policy=equipment_store.POLICY, kit_policy=inventory.KIT_POLICY,
        item_defs=ctx.world.data.items))
    equipment, _ = store.peek(uid)
    if equipment is None:
        return ()
    worn = {equipment.weapon_uid, *(member for _, member in equipment.slots)}
    legacy = ctx._world_item_effects.state(uid).curses
    return tuple(item.identifier for item in inventory.validate_kit_frame(ctx.inventory_frame)
                 if item.identifier in worn and dict(item.raw_fields)[4] > 0
                 and (item.cursed or item.identifier in legacy))


def _world_remove_curse(ctx, uid):
    """Action under caller's world/row lock; returns inventory wires, no send.

    Existing forward intent commits names and legacy state together. The magic
    owner retains its spell cost/save and packet publication contract.
    """
    targets = set(_world_curse_targets(ctx, uid))
    if not targets:
        return ()
    effects = ctx._world_item_effects
    if effects.store is None:
        raise ValueError('CURSE_SAVE_OWNER_REQUIRED')
    previous = effects.state(uid)
    proposed = deepcopy(previous)
    proposed.curses.difference_update(targets)
    before = ctx.inventory_frame
    after, wires = consumable_mutation(before, None, 'remove_curse', previous, proposed,
                                      targets, definitions=ctx.world.data.items)
    effects.store.commit(uid, before, after, proposed, ctx.world.runtime.clock())
    effects.states[uid] = proposed
    ctx.inventory_frame = after
    return wires


def _world_equipment_remove_blocked(ctx, uid, item_uid, owned_items):
    """LOCAL L1J C_ItemUSe.java3348/3394: worn curse blocks off/replacement.

    C_ItemUSe.java596..620 removes curse from equipped instances. Actual drop
    grades come from fixed-client f21 via DropDef/GroundItem; native flag wire
    remains unknown. Curse grade alone adds no unsupported stat penalty.
    """
    item = next((item for item in owned_items if item.identifier == item_uid), None)
    return item is not None and (item.cursed or item_uid in ctx._world_item_effects.state(uid).curses)


METHODS = (_world_consumable_spell_power, _world_consumable_started, _world_consumable_stopped, _world_consumable_died,
           _world_consumable_before_leave, _world_consumable_left, _world_consumable_enter,
           _world_consumable_after_enter, _world_consumable_inventory_delivered,
           _world_consumable_before_enter, _world_consumable_entry_probe,
           _world_consumable_pc_bound,
           _world_consumable_report, _world_consumable_unsupported)
METHODS += (_world_consumable_after_relocate,
            _world_curse_targets, _world_remove_curse, _world_equipment_remove_blocked,
            _world_consumable_breathing)
HOOKS = {'spell_power': ('_world_consumable_spell_power',),
         'environment_breathing': ('_world_consumable_breathing',),
         'curse_targets': ('_world_curse_targets',),
         'remove_curse': ('_world_remove_curse',),
         'equipment_remove_blocked': ('_world_equipment_remove_blocked',),
         'runtime_started': ('_world_consumable_started',),
         'runtime_stopped': ('_world_consumable_stopped',),
         'before_enter': ('_world_consumable_before_enter',),
         'entry_probe': ('_world_consumable_entry_probe',),
         'pc_bound': ('_world_consumable_pc_bound',),
         'after_enter': ('_world_consumable_after_enter',),
         'after_relocate': ('_world_consumable_after_relocate',),
         'inventory_delivered': ('_world_consumable_inventory_delivered',),
         'after_death': ('_world_consumable_died',),
         'before_leave': ('_world_consumable_before_leave',),
         'after_leave': ('_world_consumable_left',),
         'after_request': ('_world_consumable_left',),
         'report': ('_world_consumable_report',)}
FRAMES = {0x0960: ('_world_consumable_unsupported',)}
