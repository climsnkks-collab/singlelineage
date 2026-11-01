"""Pure SC_STATUS projection of an already committed/approved kill reward.

M1_REWARD_PACKETS.md sections 1(1)-(2) establish full 4E38, f2 level,
f4..14 stats/resources/negated AC and f26 double *display percentage*.
They do not establish a raw-EXP percentage formula or a level-up refill policy.
The caller supplies the percentage and any changed current resources/stats.
This module neither commits the reward nor sends or persists the returned frame.

The full-status envelope is the existing hp_status.frame/player_life_codec
full_status envelope (u16LE length, u16LE opcode, body, two zero bytes).
Those modules import observe/native dependencies, so they are not imported here.
The pure world codec rejects f26's fixed scalar; its schema and scalar/varint
encoder are reused with only the established f26 double encoded as wire1.
Schema loading occurs once at import. Building frames performs no file reads or
hash checks; calling world.encode_payload would reload its contract each time.
"""
from __future__ import annotations

from collections.abc import Mapping
import struct
from typing import TYPE_CHECKING

from tools.local_world_protocol import model as _world

if TYPE_CHECKING:
    from tools.local_original_session.world_reward import KillReward

__all__ = ['build_status_frames', 'full_status_frame', 'effect_frame']

_OPCODE = 0x4E38
_SCHEMA = _world.schema(_OPCODE)
_STATUS_UPDATES = frozenset((*range(4, 11), 12, 14))


def _encode_status(fields: Mapping[int, object]) -> bytes:
    # Same required/type checks and scalar representation as world.encode_payload,
    # using its schema captured above instead of request-path contract reads.
    if any(type(n) is not int or n not in _SCHEMA for n in fields):
        raise _world.ContractError('UNKNOWN_FIELD')
    if any(spec['required'] and n not in fields for n, spec in _SCHEMA.items()):
        raise _world.ContractError('MISSING_REQUIRED_FIELD')
    parts = []
    for number in sorted(fields):
        value = fields[number]
        if number == 26:
            if type(value) not in (int, float):
                raise TypeError('exp_percent must be an explicit number')
            parts.append(_world.wire.encode_varint((26 << 3) | 1)
                         + struct.pack('<d', value))
        else:
            kind = _SCHEMA[number]['kind']
            typed = _world._typed(kind, value)
            if kind == 'string':
                parts.append(_world.wire.encode_bytes(number, typed))
            else:
                parts.append(_world.wire.encode_varint(number << 3)
                             + _world.wire.encode_varint(typed))
    return _world.wire.encode_message(parts)


def full_status_frame(fields: Mapping[int, object]) -> bytes:
    """One full 4E38 from explicit fields (f26 optional), same envelope as below."""
    body = _encode_status(fields)
    return ((len(body) + 6).to_bytes(2, 'little') + _OPCODE.to_bytes(2, 'little')
            + body + b'\0\0')


EFFECT_OPCODE = 0x4ED8


def effect_frame(uid: int, gfx: int) -> bytes:
    """SC_EFFECT_NOTI 4ED8: required uint32 f1 target UID, required int32 f2 gfx.

    Shared core builder for magic, companion and item-use effects; same bytes
    as the former per-feature encoders (both values are positive varints).
    """
    from tools.local_entry_server import protobuf as pb
    if type(uid) is not int or not 0 < uid < (1 << 32) or type(gfx) is not int or not 0 < gfx < (1 << 31):
        raise ValueError('EFFECT_UID_GFX_REQUIRED')
    body = pb.encode_uint32(1, uid) + pb.encode_uint32(2, gfx)
    return ((len(body) + 6).to_bytes(2, 'little') + EFFECT_OPCODE.to_bytes(2, 'little')
            + body + b'\0\0')


def build_status_frames(reward: KillReward, full_status: Mapping[int, object], *,
                        exp_percent: float,
                        status_updates: Mapping[int, int] | None = None) -> list[bytes]:
    """Return one final full 4E38 for every kill, including non-level-up kills.

    ``full_status`` is the caller's existing full-status snapshot. Preserve every
    supported field except f2/new_level, f11/max_hp, known f13/max_mp and f26.
    ``exp_percent`` is required on every call, replaces any old f26, and is sent
    as supplied without clamping or deriving it from reward.new_exp.

    Optional ``status_updates`` contains explicit final f4..9 STR/DEX/INT/WIS/
    CON/CHA, f10 current HP, f12 current MP or f14 negated AC. Omitted values stay
    unchanged: no stat allocation or refill is inferred. Unknown reward.max_mp
    preserves the full-status f13; a missing required field still fails normally.
    Multi-level gains produce the final state once, not invented intermediate
    states or a separate level-up animation. Neither input is modified.

    Example: build_status_frames(reward, snapshot, exp_percent=12.3456,
                                 status_updates={10: current_hp, 12: current_mp})
    """
    if not isinstance(full_status, Mapping):
        raise TypeError('full_status must be a field mapping')
    fields = dict(full_status)
    if status_updates is not None:
        if not isinstance(status_updates, Mapping):
            raise TypeError('status_updates must be a field mapping')
        if any(type(n) is not int or n not in _STATUS_UPDATES for n in status_updates):
            raise ValueError('status_updates accepts only f4..10, f12 and f14')
        fields.update(status_updates)
    fields.update({2: reward.new_level, 11: reward.max_hp, 26: exp_percent})
    if reward.max_mp is not None:
        fields[13] = reward.max_mp
    body = _encode_status(fields)
    return [(len(body) + 6).to_bytes(2, 'little')
            + _OPCODE.to_bytes(2, 'little') + body + b'\0\0']
