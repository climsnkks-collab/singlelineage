"""Unconfirmed HP display candidates from MOB_HPBAR_EVIDENCE.md section 4.

Only the existing pure protobuf wire encoder is reused. These are exploratory
values, not a normal server payload contract or proof of a general monster HP
bar. No transport, observation, game state, persistence or file I/O lives here.
"""
from __future__ import annotations

import os

from tools.local_entry_server import protobuf as wire

__all__ = ['build_hpbar_experiment_frames']


def build_hpbar_experiment_frames(uid: int, *, step: int = 0) -> list[bytes]:
    """Build at most one explicit candidate step; never send or advance it.

    Future caller signature: build_hpbar_experiment_frames(uid: int, *,
    step: int = 0) -> list[bytes]. Example after confirming the previous screen:
    frames = build_hpbar_experiment_frames(current_monster.uid, step=1)

    SL_EXPERIMENT_HPBAR is read on every call: exact '1'/'2'/'3' selects A/B/C;
    unset or any other value returns [] without inspecting uid or step. A/B
    steps 0..2 vary only f4/f2 respectively through 100,50,1. C steps 0..4
    are (true,100),(true,50),(true,1),(true,50),(false,50).

    The caller must use the current live Monster's actual registered UID after
    normal login/world entry. For A/B, uid must also equal the original 64-bit
    actor key; pass that full key, never a masked/truncated surrogate. This
    stateless builder can check the numeric range, not actor identity/liveness.
    C only permits positive signed-int32 UIDs. Invalid enabled input raises
    ValueError; no UID is coerced, masked or truncated.

    A future experiment caller must use the existing authorized send path one
    frame at a time, only after the previous response/screen is checked. Repeat
    the same step for selected/unselected and before/after normal hits; no
    automatic sequence, timer or batch sending. Keep actual HP, saves and
    selection ownership unchanged. Never substitute these display values into
    real HP, fake damage/death, or interpret debug text alone as HP-bar success.
    Normal f2/f3, 4EC8 meanings and actual pixel effects remain unconfirmed.
    """
    mode = os.environ.get('SL_EXPERIMENT_HPBAR')
    if mode not in ('1', '2', '3'):
        return []

    maximum_uid = 0x7FFFFFFF if mode == '3' else 0xFFFFFFFF
    if type(uid) is not int or not 0 < uid <= maximum_uid:
        raise ValueError('uid must be the full positive UID in the candidate range')
    step_count = 5 if mode == '3' else 3
    if type(step) is not int or not 0 <= step < step_count:
        raise ValueError('step outside the selected candidate sequence')

    if mode == '3':
        shown, value = ((True, 100), (True, 50), (True, 1),
                        (True, 50), (False, 50))[step]
        opcode = 0x4EC8
        parts = [wire.encode_uint32(1, uid), wire.encode_bool(2, shown),
                 wire.encode_uint32(3, value)]
    else:
        value = (100, 50, 1)[step]
        fields = {1: uid, 2: value if mode == '2' else 100, 3: 0,
                  4: value if mode == '1' else 50, 5: 100}
        opcode = 0x4F1A
        # All proposed int32 values are nonnegative, so their wire0 encoding
        # equals uint32 encoding. Unknown optional f6/f7 remain absent.
        parts = [wire.encode_uint32(number, value)
                 for number, value in fields.items()]

    body = wire.encode_message(parts)
    # Existing world envelope: u16LE total length/opcode, protobuf, zero trailer.
    return [(len(body) + 6).to_bytes(2, 'little')
            + opcode.to_bytes(2, 'little') + body + b'\0\0']
