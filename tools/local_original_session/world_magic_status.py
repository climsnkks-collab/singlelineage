"""Pure timed magic states. Deadlines are monotonic; saved times are remaining.

NPC rows are owned by an EntityRef, never by a reusable UID alone. Constants
below are backend adapters, not claims about the Classic server formula.
"""
from __future__ import annotations

import math

KINDS = frozenset(('blind', 'weak_elemental', 'weapon_break', 'slow',
                   'counter_magic', 'meditation', 'paralyze', 'darkness', 'curse', 'berserk'))
CURSES = frozenset(('blind', 'paralyze', 'darkness', 'curse'))


def active(effects, kind, now):
    row = effects.get(kind)
    return row if row is not None and row['starts_at'] <= now and (
        row['until'] is None or now < row['until']) else None


def apply(effects, kind, now, duration, *, source_uid=0, spell=0, params=None, onset=0):
    if kind not in KINDS or duration is not None and duration <= 0 or onset < 0:
        raise ValueError('MAGIC_STATUS_PARAMETERS')
    effects[kind] = dict(until=None if duration is None else now + onset + duration, starts_at=now + onset,
                         source_uid=source_uid, spell=spell, params=dict(params or {}))
    return effects[kind]


def expire(effects, now):
    expired = tuple(kind for kind, row in effects.items() if row['until'] is not None and row['until'] <= now)
    for kind in expired:
        del effects[kind]
    return expired


def snapshot(effects, now):
    return {kind: dict(remaining=0 if row['until'] is None else row['until'] - now,
        onset_remaining=max(0.0, row['starts_at'] - now), source_uid=row['source_uid'],
        spell=row['spell'], params={k: v for k, v in row['params'].items() if k != 'next_tick'},
        **({'permanent': True} if row['until'] is None else {}))
        for kind, row in sorted(effects.items()) if row['until'] is None or row['until'] > now}


def validate(rows):
    def number(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    if type(rows) is not dict or not rows.keys() <= KINDS:
        raise ValueError('MAGIC_SAVE_EFFECTS')
    for row in rows.values():
        if (type(row) is not dict or not {'remaining', 'onset_remaining', 'source_uid', 'spell', 'params'} <= set(row)
                <= {'remaining', 'onset_remaining', 'source_uid', 'spell', 'params', 'permanent'}
                or 'permanent' in row and row['permanent'] is not True
                or not number(row['remaining']) or not number(row['onset_remaining'])
                or not row.get('permanent') and row['onset_remaining'] > row['remaining']
                or type(row['source_uid']) is not int or not 0 <= row['source_uid'] <= 0xffffffff
                or type(row['spell']) is not int or not 0 <= row['spell'] <= 0xffffffff
                or type(row['params']) is not dict
                or any(type(k) is not str or type(v) not in (int, float, bool, str)
                       or type(v) in (int, float) and not math.isfinite(v)
                       for k, v in row['params'].items())):
            raise ValueError('MAGIC_SAVE_EFFECT')
    return rows


def restore(rows, now, elapsed):
    validate(rows)
    return {kind: dict(until=None if row.get('permanent') else now + row['remaining'] - elapsed,
        starts_at=now + max(0.0, row['onset_remaining'] - elapsed),
        source_uid=row['source_uid'], spell=row['spell'], params=dict(row['params']))
        for kind, row in rows.items() if row.get('permanent') or row['remaining'] > elapsed}


def ai_status(effects, now):
    slow = active(effects, 'slow', now)
    sight = 1 if active(effects, 'blind', now) or active(effects, 'darkness', now) else None
    factor = 1.0 if slow is None else slow['params'].get('interval_multiplier', 2.0)
    berserk = active(effects, 'berserk', now)
    if berserk is not None:
        factor *= berserk['params'].get('interval_multiplier', .5)
    return dict(blocked=bool(active(effects, 'paralyze', now)),
                move_factor=factor, attack_factor=factor, sight=sight)


def probability(dice, intelligence, level, character_class, mr, bonus_table, rng):
    """L1J general probability subset: originalMagicHit=0, leverage=10.

    L1Character.getMagicLevel is level//4 for this retained reference. PC resist
    additions are absent from the current PC model and are explicitly zero.
    """
    bonus = bonus_table[intelligence] if intelligence <= 50 else intelligence - 25
    count = max(1, bonus + level // 4 + (1 if character_class == 3 else -1))
    chance = sum(rng.randint(1, dice) for _ in range(count)) - mr
    return rng.randint(1, 100) <= chance
