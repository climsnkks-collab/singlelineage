"""Persistent saved-character companions and temporary world actors.

LOCAL backend state only; no native UI, packets, damage or level formula. A
CompanionRecord is the sole HP/MP ledger. Never mirror it into PcState/NpcState.
Owner/member IDs identify saved characters; owner_ref.uid is a runtime PC UID.
Caller supplies an authoritative roster (saved ID -> account_id/class_id row),
and must exclude characters selected by another live session before register.

Broker/WorldView hooks: register(record, roster=roster), summon(id, owner_uid,
map_id,x,y), dismiss(id,now), die(id,now); logout/map departure must dismiss.
The summon caller supplies a spawn tile already checked against terrain,
passability and actor occupancy; this state manager has no terrain authority.
world_combat.can_be_attacked(uid) may delegate companion UIDs here; its future
can_attack(attacker_uid,target_uid) must reject are_allies(a,b). Monster incoming
damage must write runtime.record.hp and call die on lethal damage, never allocate
a second HP ledger. world_visibility must publish/remove runtime.ref and read
appearance from the saved member; Kind.NPC alone does not mean hostile monster.
Wire release_target(uid,now) to npc_ai.release_target. AI deadlines use the shared
Scheduler and are cancelled by actor reference on command change/death/dismissal.

snapshot/save/load contain persistent records only, no UID/generation/position,
targets, actions or timer handles. save(path, owner_character_id=...) explicitly
replaces one owner's <character save directory>/companion.json atomically; load
validates all rows before replacing that owner's records and never summons.
The manager never writes automatically or resurrects on load. CompanionStore below
is the joint LOCAL snapshot; WorldView owns real kill-once admission.
mp_reserve is an absolute integer MP amount, not a percentage. Kill-once and a
joint durable owner/member reward commit belong to the world feature caller.
All methods run under the existing single world-thread/runtime lock.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import NamedTuple, Protocol

from tools.local_original_session.world_entities import EntityRef, EntityRegistry, Kind
import time as _time


def replace_file(temporary: Path, path: Path) -> None:
    """os.replace with a short retry for Windows sharing violations.

    A scanner/indexer briefly holding the destination makes MoveFileEx fail
    with ERROR_ACCESS_DENIED even though the save itself is fine. The write
    stays atomic; a persistent failure still propagates as before.
    """
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            _time.sleep(0.005 * (attempt + 1))
from tools.local_original_session.world_scheduler import Handle, Scheduler


def _integer(value, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('COMPANION_INVALID_' + name)
    return value


class CompanionResources:
    """Runtime projection; these slots are deliberately absent from asdict/save.

    max_hp/max_mp remain permanent growth bases. Restore validates scalar/life
    state immediately, then verifies the current resources against actual worn
    equipment when the bag is restored; a saved effective current may exceed
    its growth base. Equipment changes preserve current amounts and clamp only.
    """
    __slots__ = ('_equipment_hp_bonus', '_equipment_mp_bonus', '_resource_restore_pending')

    @property
    def effective_max_hp(self):
        return max(1, self.max_hp + getattr(self, '_equipment_hp_bonus', 0))

    @property
    def effective_max_mp(self):
        return max(0, self.max_mp + getattr(self, '_equipment_mp_bonus', 0))

    def project_resources(self, calculated):
        self._equipment_hp_bonus = calculated.max_hp_bonus
        self._equipment_mp_bonus = calculated.max_mp_bonus
        if getattr(self, '_resource_restore_pending', False):
            # Do not turn a malformed over-cap save into a valid resource value.
            if self.hp > self.effective_max_hp or self.mp > self.effective_max_mp:
                raise ValueError('COMPANION_RESOURCE_ABOVE_MAXIMUM')
            self._resource_restore_pending = False
        self.hp = min(self.hp, self.effective_max_hp)
        self.mp = min(self.mp, self.effective_max_mp)


@dataclass(slots=True)
class CompanionRecord(CompanionResources):
    character_id: int
    owner_character_id: int
    account_id: str
    level: int = 1
    exp: int = 0
    exp_half: int = 0
    hp: int = 1
    mp: int = 0
    max_hp: int = 1
    max_mp: int = 0
    equipment: dict = field(default_factory=dict)
    # Legacy serialized field / ATS view only. The companion feature refreshes
    # this from the registered MagicStore authority, never the reverse.
    learned_spells: tuple[int, ...] = ()
    movement_mode: str = 'FOLLOW'
    combat_mode: str = 'ASSIST'
    support_enabled: bool = True
    mp_reserve: int = 0
    alive: bool = True
    # Saved class of this ordinary character (data/companion/classes.json).
    class_id: int = 3
    # Out (summoned) when the owner last left. Logout keeps it; only an explicit
    # dismissal or being left behind by a dead owner clears it. Fresh LOCAL test
    # members start out, preserving the existing automatic first appearance.
    summoned: bool = True

    @property
    def command(self) -> str:
        return self.movement_mode

    @command.setter
    def command(self, value: str) -> None:
        if value not in ('FOLLOW', 'HOLD'):
            raise ValueError('COMPANION_INVALID_MOVEMENT_MODE')
        self.movement_mode = value

    @property
    def mode(self) -> str:
        return self.combat_mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in ('PASSIVE', 'ASSIST', 'DEFEND'):
            raise ValueError('COMPANION_INVALID_COMBAT_MODE')
        self.combat_mode = value

    def validate(self) -> None:
        _integer(self.character_id, 'CHARACTER_ID', 1)
        _integer(self.owner_character_id, 'OWNER_CHARACTER_ID', 1)
        if self.character_id == self.owner_character_id:
            raise ValueError('COMPANION_OWNER_CANNOT_BE_MEMBER')
        if not isinstance(self.account_id, str) or not self.account_id:
            raise ValueError('COMPANION_INVALID_ACCOUNT_ID')
        _integer(self.level, 'LEVEL', 1)
        for name in ('exp', 'exp_half', 'hp', 'mp', 'max_mp', 'mp_reserve'):
            _integer(getattr(self, name), name.upper())
        _integer(self.max_hp, 'MAX_HP', 1)
        if self.exp_half not in (0, 1):
            raise ValueError('COMPANION_INVALID_EXP_HALF')
        if (not getattr(self, '_resource_restore_pending', False)
                and (self.hp > self.effective_max_hp or self.mp > self.effective_max_mp)):
            raise ValueError('COMPANION_RESOURCE_ABOVE_MAXIMUM')
        if type(self.alive) is not bool or self.alive != (self.hp > 0):
            raise ValueError('COMPANION_LIFE_HP_MISMATCH')
        if type(self.support_enabled) is not bool:
            raise ValueError('COMPANION_INVALID_SUPPORT_ENABLED')
        _integer(self.class_id, 'CLASS_ID')
        if type(self.summoned) is not bool:
            raise ValueError('COMPANION_INVALID_SUMMONED')
        if self.movement_mode not in ('FOLLOW', 'HOLD'):
            raise ValueError('COMPANION_INVALID_MOVEMENT_MODE')
        if self.combat_mode not in ('PASSIVE', 'ASSIST', 'DEFEND'):
            raise ValueError('COMPANION_INVALID_COMBAT_MODE')
        if not isinstance(self.equipment, dict):
            raise ValueError('COMPANION_INVALID_EQUIPMENT')
        # Backward-compatible LOCAL effect/food metadata only. Actual bags and
        # eight worn slots belong to the same PC inventory/equipment stores;
        # this record neither issues items nor owns a second inventory format.
        json.dumps(self.equipment, allow_nan=False)
        if not isinstance(self.learned_spells, (tuple, list)):
            raise ValueError('COMPANION_INVALID_LEARNED_SPELLS')
        for spell in self.learned_spells:
            _integer(spell, 'LEARNED_SPELL')  # Heal0 is a lawful learned key.
        if len(set(self.learned_spells)) != len(self.learned_spells):
            raise ValueError('COMPANION_DUPLICATE_LEARNED_SPELL')


# Fields added after schema1 rows were written; older rows load with defaults.
OPTIONAL_RECORD_FIELDS = frozenset(('class_id', 'summoned'))


def record_from_row(row: Mapping) -> CompanionRecord:
    if (not isinstance(row, Mapping)
            or not set(CompanionRecord.__dataclass_fields__) - OPTIONAL_RECORD_FIELDS <= set(row)
            or not set(row) <= set(CompanionRecord.__dataclass_fields__)):
        raise ValueError('COMPANION_INVALID_RECORD')
    record = CompanionRecord(**row)
    record.learned_spells = tuple(record.learned_spells)
    record._resource_restore_pending = True
    record.validate()
    return record


def _validate_roster(record: CompanionRecord, roster: Mapping,
                     allowed_classes=frozenset((3,))) -> None:
    record.validate()
    owner = roster.get(record.owner_character_id)
    member = roster.get(record.character_id)
    if not isinstance(owner, Mapping) or not isinstance(member, Mapping):
        raise ValueError('COMPANION_SAVED_CHARACTER_REQUIRED')
    if (owner.get('account_id') != record.account_id or
            member.get('account_id') != record.account_id):
        raise ValueError('COMPANION_SAME_ACCOUNT_REQUIRED')
    if (type(member.get('class_id')) is not int or member['class_id'] != record.class_id
            or member['class_id'] not in allowed_classes):
        raise ValueError('COMPANION_SAVED_MAGE_REQUIRED' if allowed_classes == {3}
                         else 'COMPANION_SAVED_CLASS_REQUIRED')


@dataclass(slots=True)
class CompanionRuntime:
    record: CompanionRecord
    ref: EntityRef
    owner_ref: EntityRef
    target: EntityRef | None = None
    action: str = 'FOLLOW'
    next_move_at: float = 0.0
    next_attack_at: float = 0.0
    next_cast_at: float = 0.0
    handle: Handle | None = None
    # Selection-local spell/regen state; never serialize actor identities/timers.
    shield_until: float = 0.0
    emergency_owner: bool = False
    recovering: bool = False
    regen_at: float | None = None
    regen_points: int = 0
    regen_activity: int = 4
    position_key: object = None
    position_started: float = 0.0
    position_attempts: int = 0
    position_failed: object = None
    position_retry_at: float = 0.0
    # Pet-window "attack target" focus: one designated monster wins over the
    # owner's target changes until it dies or the stance changes.
    focus: EntityRef | None = None
    # Owner died on this map: hold in place; departure leaves this member behind.
    owner_down: bool = False
    # One F4 snapshot, selection-local; never restored or auto-renewed.
    pickup_refs: tuple = ()
    pickup_until: float = 0.0

    @property
    def character_id(self) -> int:
        return self.record.character_id


class WorldCompanions:
    def __init__(self, entities: EntityRegistry, scheduler: Scheduler, *,
                 release_target: Callable[[int, float], object] | None = None,
                 allowed_classes=frozenset((3,))):
        self.entities = entities
        self.scheduler = scheduler
        self.release_target = release_target
        self.allowed_classes = frozenset(allowed_classes)
        # Optional callable(record, now): ordinary death consequences (EXP loss)
        # applied once on each alive->dead transition, whatever killed it.
        self.on_death = None
        self.records: dict[int, CompanionRecord] = {}
        self._active: dict[int, CompanionRuntime] = {}
        self.active: Mapping[int, CompanionRuntime] = MappingProxyType(self._active)
        self._actors: dict[int, CompanionRuntime] = {}
        self.on_remove = None  # WorldView publication, not a second lifetime owner.

    def register(self, record: CompanionRecord, *, roster: Mapping) -> CompanionRecord:
        _validate_roster(record, roster, self.allowed_classes)
        if record.character_id in self.records:
            raise ValueError('COMPANION_ALREADY_REGISTERED')
        self.records[record.character_id] = record
        return record

    def summon(self, character_id: int, owner_uid: int, map_id: int, x: int, y: int,
               *, now: float | None = None, heading: int = 0,
               template_id: int | None = None) -> CompanionRuntime:
        """Allocate at the caller's validated spawn tile; bind saved owner in broker."""
        record = self.records[character_id]
        record.validate()
        if not record.alive:
            raise ValueError('COMPANION_RESURRECTION_REQUIRED')
        return self._materialize(character_id, owner_uid, map_id, x, y,
                                 now=now, heading=heading, template_id=template_id)

    def restore_corpse(self, character_id: int, owner_uid: int, map_id: int,
                       x: int, y: int, *, now: float | None = None,
                       heading: int = 0) -> CompanionRuntime:
        """Restore a saved dead member at an admitted tile, without resurrection."""
        record = self.records[character_id]
        record.validate()
        if record.alive or record.hp != 0:
            raise ValueError('COMPANION_DEAD_MEMBER_REQUIRED')
        return self._materialize(character_id, owner_uid, map_id, x, y,
                                 now=now, heading=heading)

    def _materialize(self, character_id, owner_uid, map_id, x, y, *, now=None,
                     heading=0, template_id=None):
        record = self.records[character_id]
        if character_id in self.active:
            raise ValueError('COMPANION_ALREADY_ACTIVE')
        owner = self.entities.get(owner_uid)
        if owner is None or owner.kind is not Kind.PC or not owner.alive:
            raise ValueError('COMPANION_LIVE_OWNER_REQUIRED')
        if owner.map_id != map_id:
            raise ValueError('COMPANION_OWNER_MAP_MISMATCH')
        started_at = self._now(now)
        # The broker must bind owner_uid to record.owner_character_id from its
        # selected character session; EntityRegistry deliberately has no save IDs.
        entity = self.entities.add(Kind.NPC, map_id, x, y, heading=heading,
                                   template_id=template_id)
        # No timing is inferred here. The caller supplies real movement/attack
        # intervals to AI. now only establishes the first eligible deadlines.
        actor = CompanionRuntime(record, entity.ref, owner.ref,
                                 action=record.movement_mode,
                                 next_move_at=started_at, next_attack_at=started_at,
                                 next_cast_at=started_at)
        self._active[character_id] = actor
        self._actors[entity.uid] = actor
        if not record.alive:
            actor.action = 'DEAD'
            self.entities.kill(entity.uid)  # corpse refs cannot admit live AI/attacks
        return actor

    def get_actor(self, uid: int) -> CompanionRuntime | None:
        actor = self._actors.get(uid)
        return actor if actor is not None and self.entities.is_current(actor.ref) else None

    def retained_actor(self, uid: int) -> CompanionRuntime | None:
        """Includes a dead same-map corpse whose original reference is invalid."""
        return self._actors.get(uid)

    @contextmanager
    def without_reward_member(self, character_id: int):
        """Allocate a feature-owned reward while the ordinary splitter skips it.

        The actor remains published and attackable. Only reward enumeration is
        suspended, and the original pop/reinsert order is retained on failure.
        """
        actor = self._active.pop(character_id)
        try:
            yield actor
        finally:
            self._active[character_id] = actor

    def can_be_attacked(self, uid: int) -> bool:
        actor = self.get_actor(uid)
        if actor is None or not actor.record.alive or actor.record.hp <= 0:
            return False
        entity = self.entities.resolve(actor.ref)
        owner = self.entities.resolve(actor.owner_ref)
        return bool(entity and entity.alive and owner and owner.alive and
                    owner.map_id == entity.map_id)

    def _family(self, uid: int) -> EntityRef | None:
        actor = self.get_actor(uid)
        if actor is not None:
            return actor.owner_ref if self.can_be_attacked(uid) else None
        entity = self.entities.get(uid)
        return entity.ref if entity and entity.kind is Kind.PC and entity.alive else None

    def are_allies(self, attacker_uid: int, target_uid: int) -> bool:
        family = self._family(attacker_uid)
        return family is not None and family == self._family(target_uid)

    def _stop(self, actor: CompanionRuntime) -> None:
        actor.pickup_refs = ()
        actor.pickup_until = 0.0
        self.scheduler.cancel_owner(actor.ref)
        actor.handle = None
        actor.target = None
        # Commands may interrupt the action, never reset its earned cooldown.

    def _now(self, now: float | None) -> float:
        value = self.scheduler.clock() if now is None else now
        if not math.isfinite(value):
            raise ValueError('COMPANION_INVALID_TIME')
        return value

    def die(self, character_id: int, now: float | None = None) -> CompanionRuntime | None:
        now = self._now(now)
        record = self.records[character_id]
        actor = self.active.get(character_id)
        was_alive = record.alive
        record.hp = 0
        record.alive = False
        if was_alive and self.on_death is not None:
            self.on_death(record, now)
        if actor is None or actor.action == 'DEAD':
            return actor
        self._stop(actor)
        actor.action = 'DEAD'
        actor.focus = None
        actor.shield_until = 0.0
        actor.emergency_owner = actor.recovering = False
        actor.regen_at, actor.regen_points, actor.regen_activity = None, 0, 4
        actor.position_key = actor.position_failed = None
        actor.position_started = actor.position_retry_at = 0.0
        actor.position_attempts = 0
        entity = self.entities.resolve(actor.ref)
        if entity is not None:
            self.entities.kill(entity.uid)  # invalidates all outstanding refs
        if self.release_target is not None:
            self.release_target(actor.ref.uid, now)
        return actor

    def revive(self, character_id: int, now: float | None = None, *,
               hp: int | None = None) -> CompanionRuntime | None:
        """Caller-admitted resurrection: supplied HP, unchanged MP/EXP/settings.

        A retained corpse keeps its UID/position, but receives a fresh server
        generation so pre-death attacks/casts cannot resume against this life.
        Without a corpse the caller must admit a normal summon tile. Caller
        owns selected-owner admission, durable commit and display publication.
        """
        self._now(now)
        record = self.records[character_id]
        record.validate()
        if record.alive:
            raise ValueError('COMPANION_DEAD_MEMBER_REQUIRED')
        restored_hp = record.effective_max_hp if hp is None else hp
        if type(restored_hp) is not int or not 1 <= restored_hp <= record.effective_max_hp:
            raise ValueError('COMPANION_REVIVE_HP_REQUIRED')
        actor = self.active.get(character_id)
        entity = None
        if actor is not None:
            entity = self.entities.get(actor.ref.uid)
            owner = self.entities.resolve(actor.owner_ref)
            if (entity is None or entity.alive or owner is None or not owner.alive
                    or entity.map_id != owner.map_id):
                raise ValueError('COMPANION_CURRENT_CORPSE_REQUIRED')
            self._stop(actor)
        record.hp, record.alive = restored_hp, True
        if actor is not None:
            # Registry has retained this corpse, not removed/reallocated its UID.
            entity.generation += 1
            entity.alive = True
            actor.ref = entity.ref
            actor.action = record.movement_mode
        return actor

    def dismiss(self, character_id: int, now: float | None = None) -> CompanionRuntime | None:
        now = self._now(now)
        actor = self._active.pop(character_id, None)
        if actor is None:
            return None
        self._stop(actor)
        actor.action = 'DEAD' if not actor.record.alive else 'DISMISSED'
        self._actors.pop(actor.ref.uid, None)
        if self.entities.get(actor.ref.uid) is not None:
            self.entities.remove(actor.ref.uid)
        if self.release_target is not None:
            self.release_target(actor.ref.uid, now)
        if self.on_remove is not None:
            self.on_remove(actor)
        return actor

    def recall(self, character_id: int, owner_uid: int, map_id: int, x: int, y: int,
               *, now: float | None = None) -> CompanionRuntime:
        """Move a living current member to the caller-admitted adjacent tile.

        Keep this actor's identity, saved commands/resources and earned action
        deadlines. The caller admits terrain/occupancy and republishes the move.
        Dead members retain their corpse and require a targeted resurrection.
        """
        now = self._now(now)
        actor = self.active[character_id]
        entity = self.entities.resolve(actor.ref)
        owner = self.entities.get(owner_uid)
        if (not actor.record.alive or actor.record.hp <= 0 or entity is None
                or not entity.alive):
            raise ValueError('COMPANION_RESURRECTION_REQUIRED')
        if (owner is None or not owner.alive or owner.kind is not Kind.PC
                or actor.owner_ref != owner.ref or owner.map_id != map_id
                or entity.map_id != map_id):
            raise ValueError('COMPANION_CURRENT_LIVING_OWNER_REQUIRED')
        self._stop(actor)
        if self.release_target is not None:
            self.release_target(actor.ref.uid, now)
        self.entities.move(entity.uid, map_id, x, y, owner.heading)
        actor.action = actor.record.movement_mode
        actor.position_key = actor.position_failed = None
        actor.position_started = actor.position_retry_at = 0.0
        actor.position_attempts = 0
        return actor

    def set_commands(self, character_id: int, *, movement_mode: str | None = None,
                     combat_mode: str | None = None, support_enabled: bool | None = None,
                     mp_reserve: int | None = None, now: float | None = None) -> None:
        """Keep action deadlines; caller then invokes AI.command_changed(ref,now)."""
        self._now(now)
        record = self.records[character_id]
        candidate = deepcopy(record)
        for key, value in (('movement_mode', movement_mode), ('combat_mode', combat_mode),
                           ('support_enabled', support_enabled), ('mp_reserve', mp_reserve)):
            if value is not None:
                setattr(candidate, key, value)
        candidate.validate()
        record.movement_mode, record.combat_mode = candidate.movement_mode, candidate.combat_mode
        record.support_enabled, record.mp_reserve = candidate.support_enabled, candidate.mp_reserve
        actor = self.active.get(character_id)
        if actor is not None:
            self._stop(actor)
            actor.action = 'DEAD' if not record.alive else record.movement_mode

    def snapshot(self, *, owner_character_id: int) -> dict:
        _integer(owner_character_id, 'OWNER_CHARACTER_ID', 1)
        rows = []
        for character_id, record in sorted(self.records.items()):
            if record.owner_character_id == owner_character_id:
                record.validate()
                rows.append(asdict(record))
        return {'schema': 1, 'owner_character_id': owner_character_id, 'records': rows}

    def save(self, path: str | Path, *, owner_character_id: int) -> None:
        """Explicit absolute snapshot; failed replacement preserves previous file."""
        payload = json.dumps(self.snapshot(owner_character_id=owner_character_id),
                             ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        path = Path(path)
        # Caller owns destination selection and creating the character save dir.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                    dir=path.parent, prefix=path.name + '.', suffix='.tmp',
                    delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            replace_file(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def load(self, path: str | Path, *, roster: Mapping) -> tuple[CompanionRecord, ...]:
        """Read one owner's records atomically in memory; never restore an actor."""
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(payload, dict) or set(payload) != {'schema', 'owner_character_id', 'records'}:
            raise ValueError('COMPANION_INVALID_SNAPSHOT')
        if type(payload['schema']) is not int or payload['schema'] != 1:
            raise ValueError('COMPANION_UNSUPPORTED_SCHEMA')
        owner_id = _integer(payload['owner_character_id'], 'OWNER_CHARACTER_ID', 1)
        if not isinstance(payload['records'], list):
            raise ValueError('COMPANION_INVALID_SNAPSHOT')
        loaded = {}
        for row in payload['records']:
            record = record_from_row(row)
            _validate_roster(record, roster, self.allowed_classes)
            if record.owner_character_id != owner_id or record.character_id in loaded:
                raise ValueError('COMPANION_INVALID_SNAPSHOT_MEMBER')
            existing = self.records.get(record.character_id)
            if existing is not None and existing.owner_character_id != owner_id:
                raise ValueError('COMPANION_ALREADY_REGISTERED')
            loaded[record.character_id] = record
        if any(actor.record.owner_character_id == owner_id or character_id in loaded
               for character_id, actor in self.active.items()):
            raise ValueError('COMPANION_DISMISS_BEFORE_LOAD')
        # Empty snapshots also require a genuine owner roster row.
        if not isinstance(roster.get(owner_id), Mapping):
            raise ValueError('COMPANION_SAVED_CHARACTER_REQUIRED')
        retained = {key: record for key, record in self.records.items()
                    if record.owner_character_id != owner_id}
        retained.update(loaded)
        self.records.clear()
        self.records.update(retained)
        return tuple(loaded.values())


class ExpSplit(NamedTuple):
    owner_exp: int
    companion_exp: int
    owner_half: int
    companion_half: int


def split_exp(kill_exp: int, owner_half: int = 0, companion_half: int = 0) -> ExpSplit:
    """Each beneficiary keeps their own integer half-unit remainder (0 or 1)."""
    _integer(kill_exp, 'KILL_EXP')
    for remainder in (owner_half, companion_half):
        _integer(remainder, 'EXP_HALF')
        if remainder not in (0, 1):
            raise ValueError('COMPANION_INVALID_EXP_HALF')
    owner_exp, owner_remainder = divmod(kill_exp + owner_half, 2)
    companion_exp, companion_remainder = divmod(kill_exp + companion_half, 2)
    return ExpSplit(owner_exp, companion_exp, owner_remainder, companion_remainder)


class ExperienceLedger(Protocol):
    exp: int
    exp_half: int


def award_split_exp(kill_exp: int, owner_ledger: ExperienceLedger,
                    companion_record: CompanionRecord) -> ExpSplit:
    """In-memory arithmetic only; caller owns kill-once, growth and joint save/CAS."""
    if owner_ledger is companion_record:
        raise ValueError('COMPANION_DISTINCT_EXP_LEDGERS_REQUIRED')
    _integer(owner_ledger.exp, 'OWNER_EXP')
    _integer(companion_record.exp, 'EXP')
    result = split_exp(kill_exp, owner_ledger.exp_half, companion_record.exp_half)
    owner_ledger.exp += result.owner_exp
    companion_record.exp += result.companion_exp
    owner_ledger.exp_half = result.owner_half
    companion_record.exp_half = result.companion_half
    return result


class CompanionStore:
    """One LOCAL atomic owner/member snapshot, loaded only during startup.

    The existing progression.json remains the solo projection. For a registered
    companion owner, this joint snapshot is authoritative at re-entry, avoiding
    a crash between two independent owner/member writes. Runtime identities and
    targets never enter this file. No live file read occurs in commit().
    """
    def __init__(self, character_store_path):
        self.path = Path(character_store_path).with_name('companion.json')
        self.pending = None  # latest failed absolute snapshot, including departed owner
        self.payload = {'schema': 1, 'owners': {}, 'records': [], 'rewards': []}
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(payload, dict) or payload.get('schema') != 1
                    or set(payload) != set(self.payload)
                    or not isinstance(payload['owners'], dict)
                    or not isinstance(payload['records'], list)
                    or not isinstance(payload['rewards'], list)):
                raise ValueError('COMPANION_INVALID_JOINT_SAVE')
            for row in payload['records']:
                record_from_row(row).validate()
            for key, row in payload['owners'].items():
                _integer(int(key), 'OWNER_CHARACTER_ID', 1)
                for name in ('exp', 'level', 'exp_half'):
                    _integer(row[name], name.upper(), 1 if name == 'level' else 0)
                if row['exp_half'] not in (0, 1):
                    raise ValueError('COMPANION_INVALID_EXP_HALF')
            self.payload = payload

    def commit(self, world, owner_uid: int, receipt=None, *, records=None,
               reward_receipts=None) -> None:
        # Each feature submits its owned projection; never swap the live roster
        # or receipt ledger merely to call the unchanged joint-file serializer.
        owned = tuple(world.companions.records.values() if records is None else records)
        records = [asdict(record) for record in owned]
        for record in owned:
            record.validate()
        previous = self.payload if self.pending is None else self.pending
        owners = deepcopy(previous['owners'])
        from tools.local_original_session.world_progress import base_maxima
        for uid, state in world.combat.pcs.items():
            if any(record.owner_character_id == uid for record in owned):
                hp, mp = base_maxima(state)
                owners[str(uid)] = dict(exp=world.exp[uid], level=state.profile.level,
                    max_hp=hp, max_mp=mp,
                    lawful=state.status_fields.get(18, 500),
                    exp_half=world.companion_owner_half.get(uid, 0))
        # Preserve an earlier failed absolute save on the next ordinary commit;
        # never recompute or replay its kill reward to recover a lost response.
        by_kill = {row['kill_id']: deepcopy(row) for row in previous['rewards']}
        submitted_receipts = tuple(world.companion_reward_receipts if reward_receipts is None else reward_receipts)
        for row in submitted_receipts:
            by_kill[row['kill_id']] = {**row, 'joint_commit_count': 1, 'durable': True}
        rewards = list(by_kill.values())[-32:]
        payload = dict(schema=1, owners=owners, records=records, rewards=rewards)
        self.pending = payload
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                    prefix=self.path.name + '.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            replace_file(temporary, self.path)
            self.payload = payload
            self.pending = None
            for row in submitted_receipts:
                row.update(joint_commit_count=1, durable=True)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
