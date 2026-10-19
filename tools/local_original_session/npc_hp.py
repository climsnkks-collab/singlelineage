"""Explicit backend HP inputs for a selected local NPC; no protocol or save.

Only AttackSession consumes this state under the existing broker row lock.
Provider outputs are local policy, never decoded from CS4E30/SC4E31. No
official damage formula, NPC reference mapping, removal or respawn is implied.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from tools.local_original_session.attack import U64_MAX, need

POLICY = 'EXPLICIT_LOCAL_NPC_HP_INPUT'


@dataclass(frozen=True, slots=True)
class Target:
    uid: int
    map_id: int
    sprite_id: int
    template_id: int


@dataclass(frozen=True, slots=True)
class Hp:
    current: int
    maximum: int

    def __post_init__(self):
        need(type(self.current) is int and type(self.maximum) is int
             and 0 <= self.current <= self.maximum <= U64_MAX and self.maximum > 0,
             'NPC_HP_EXPLICIT_RANGE_REQUIRED')

    @property
    def alive(self):
        return self.current > 0


@dataclass(frozen=True, slots=True)
class Hit:
    landed: bool
    damage: int

    def __post_init__(self):
        need(type(self.landed) is bool and type(self.damage) is int
             and 0 <= self.damage <= U64_MAX and (self.landed or self.damage == 0),
             'NPC_HP_EXPLICIT_HIT_DAMAGE_REQUIRED')


@dataclass(frozen=True, slots=True)
class Inputs:
    """One exact local actor mapping, with every gameplay number explicit."""
    target: Target
    hp: Hp
    hit: Hit

    def __post_init__(self):
        need(type(self.target) is Target and type(self.hp) is Hp and type(self.hit) is Hit
             and self.hp.alive, 'NPC_HP_EXPLICIT_LIVE_INPUTS_REQUIRED')
        need(all(type(n) is int for n in (self.target.uid, self.target.map_id,
                 self.target.sprite_id, self.target.template_id))
             and 0 < self.target.uid < U64_MAX and self.target.map_id >= 0
             and self.target.sprite_id >= 0 and self.target.template_id >= 0,
             'NPC_HP_EXPLICIT_TARGET_REQUIRED')


@dataclass(frozen=True, slots=True)
class ExplicitInputs:
    """Optional fixed local backend provider. No default rows or numbers.

    A different trusted synchronous backend provider may implement the same
    policy/initial_hp/resolve_hit interface. Nothing accepts a wire provider.
    """
    rows: tuple[Inputs, ...]
    policy: str = field(default=POLICY, init=False)

    def __post_init__(self):
        need(type(self.rows) is tuple and len(self.rows) > 0
             and all(type(row) is Inputs for row in self.rows)
             and len({(r.target.uid, r.target.map_id) for r in self.rows}) == len(self.rows),
             'NPC_HP_EXPLICIT_UNIQUE_INPUTS_REQUIRED')

    def _row(self, target):
        matches = [row for row in self.rows if row.target == target]
        need(len(matches) == 1, 'NPC_HP_EXPLICIT_TARGET_INPUT_REQUIRED')
        return matches[0]

    def initial_hp(self, target):
        return self._row(target).hp

    def resolve_hit(self, target, hp, *, attacker_uid, accepted_ordinal):
        return self._row(target).hit


@dataclass(frozen=True, slots=True)
class Result:
    accepted_ordinal: int
    target: Target
    before: Hp
    after: Hp
    hit: Hit

    @property
    def died(self):
        return self.before.alive and not self.after.alive

    def metadata(self):
        return dict(accepted_ordinal=self.accepted_ordinal, target_uid=self.target.uid,
                    map_id=self.target.map_id, hp_before=self.before.current,
                    hp=self.after.current, max_hp=self.after.maximum, alive=self.after.alive,
                    hit=self.hit.landed, damage=self.hit.damage, died=self.died,
                    notification='NOT_IMPLEMENTED_SOURCE_CONTRACT_REQUIRED')


@dataclass(frozen=True, slots=True)
class _Entry:
    writer: object
    row: object
    lock: object
    lifetime: tuple
    target: Target
    hp: Hp
    intent: object


class Authority:
    """Selection-lifetime HP, independent of moving Position/motion.State.

    _prepare is side-effect free, including a first spawn's initial HP. Only
    _commit stores the one accepted immutable intent under the same row lock.
    Provider failure/cancellation before commit leaves previous HP untouched.
    """
    def __init__(self, provider):
        need(getattr(provider, 'policy', None) == POLICY
             and callable(getattr(provider, 'initial_hp', None))
             and callable(getattr(provider, 'resolve_hit', None)),
             'NPC_HP_EXPLICIT_BACKEND_PROVIDER_REQUIRED')
        self.provider = provider
        self._entries = {}

    def _prepare(self, writer, row, lifetime, target, intent):
        need(row['operation_lock'].locked(), 'NPC_HP_EXISTING_ROW_LOCK_REQUIRED')
        key = (id(writer), target.uid)
        previous = self._entries.get(key)
        if previous is not None:
            need(previous.writer is writer and previous.row is row
                 and len(previous.lifetime) == len(lifetime)
                 and all(a is b for a, b in zip(previous.lifetime, lifetime))
                 and previous.target == target, 'NPC_HP_SELECTION_LIFETIME_CHANGED')
            need(previous.intent is not intent, 'NPC_HP_INTENT_ALREADY_CONSUMED')
            hp = previous.hp
        else:
            hp = self.provider.initial_hp(target)
            need(type(hp) is Hp and hp.alive, 'NPC_HP_EXPLICIT_INITIAL_HP_REQUIRED')
        need(hp.alive, 'ATTACK_LOCAL_TARGET_DEAD')
        hit = self.provider.resolve_hit(target, hp, attacker_uid=intent._bound.attacker.uid,
                                        accepted_ordinal=intent.accepted_ordinal)
        need(type(hit) is Hit, 'NPC_HP_EXPLICIT_HIT_REQUIRED')
        after = Hp(max(0, hp.current - hit.damage), hp.maximum)
        result = Result(intent.accepted_ordinal, target, hp, after, hit)
        replacement = _Entry(writer, row, row['operation_lock'], lifetime, target, after, intent)
        return key, previous, replacement, result

    def _commit(self, prepared):
        key, previous, replacement, result = prepared
        need(self._entries.get(key) is previous
             and replacement.row['operation_lock'] is replacement.lock
             and replacement.lock.locked(), 'NPC_HP_CURRENT_ONCE_COMMIT_REQUIRED')
        self._entries[key] = replacement
        return result

    def _require_alive(self, writer, row, lifetime, target):
        entry = self._entries.get((id(writer), target.uid))
        if entry is not None:
            need(entry.writer is writer and entry.row is row
                 and entry.lock is row['operation_lock'] and entry.lock.locked()
                 and len(entry.lifetime) == len(lifetime)
                 and all(a is b for a, b in zip(entry.lifetime, lifetime))
                 and entry.target == target, 'NPC_HP_SELECTION_LIFETIME_CHANGED')
            need(entry.hp.alive, 'NPC_HP_DEAD_MOTION_REFUSED')

    def release(self, writer):
        for key, entry in tuple(self._entries.items()):
            if entry.writer is writer:
                del self._entries[key]

    def close(self):
        self._entries.clear()

    def metadata(self):
        return dict(policy=POLICY, states=[dict(target_uid=e.target.uid, map_id=e.target.map_id,
                    hp=e.hp.current, max_hp=e.hp.maximum, alive=e.hp.alive,
                    last_accepted_ordinal=e.intent.accepted_ordinal) for e in self._entries.values()],
                    scope='CURRENT_SELECTION_MEMORY_ONLY',
                    notification='NOT_IMPLEMENTED_SOURCE_CONTRACT_REQUIRED')
