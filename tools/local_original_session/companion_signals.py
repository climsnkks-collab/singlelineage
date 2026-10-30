"""LOCAL companion bridge 4F02 body codec (product copy of the bridge draft).

Contract: work/local_original_session/companion-bridge/SIGNALS.md. One 4F02
protobuf body: f1=7 once, repeated f2 strings ["LOCAL_COMPANION_UI_V1",
operation, args...], f3 = current companion actor UID low32 (or explicit 0).
The 1차 operations, the 2차 item operations (item-give/take/equip/unequip,
unsigned decimal args) and the owner-edit ATS lifetime (ats-edit-close,
ats-edit-restored; actor 0) are accepted. The independent ATS window uses
ats-window-open(member) / ats-window-save(member, epoch, delta basename), both
with the current actor. Operation names are data only; they never
resolve to methods. A marker body that does not validate is a SignalError and
must not fall back to the ordinary pet mode7 path.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

MARKER = 'LOCAL_COMPANION_UI_V1'
OPCODE = 0x4F02
ACTOR_OPERATIONS = frozenset({
    'settings-load', 'bag-open-take', 'equipment-open', 'pet-window-open',
    'movement-follow', 'movement-hold',
})
# member, generation, viewEpoch, itemUID[, quantity | slotKey]
ITEM_OPERATIONS = {'item-give': 5, 'item-take': 5, 'item-equip': 4, 'item-unequip': 5}
U64 = (1 << 64) - 1


class SignalError(ValueError):
    """Malformed protobuf or invalid LOCAL request; never ordinary-pet fallback."""


@dataclass(frozen=True)
class Signal:
    operation: str
    actor_uid: int
    args: tuple = ()
    unknown_fields: tuple = ()

    def numbers(self):
        """Item operation args as ints (validated by decode)."""
        return tuple(int(value) for value in self.args)


def _validate(operation, actor_uid, args):
    if type(actor_uid) is not int or not 0 <= actor_uid <= 0xFFFFFFFF:
        raise SignalError('actor_uid must be a uint32')
    if operation in ACTOR_OPERATIONS:
        if not actor_uid or args:
            raise SignalError('companion operation requires nonzero actor and no args')
    elif operation in ITEM_OPERATIONS:
        if not actor_uid or len(args) != ITEM_OPERATIONS[operation]:
            raise SignalError('item operation requires actor and exact args')
        for value in args:
            if not value.isascii() or not value.isdecimal() or str(int(value)) != value \
                    or not 0 < int(value) <= U64:
                raise SignalError('item operation args are positive unsigned decimals')
    elif operation == 'ats-select':
        if actor_uid != 0 or args not in (('self',), ('companion',)):
            raise SignalError('ATS requires actor=0 and one self|companion scope')
    elif operation in ('ats-window-open', 'ats-window-save'):
        count = 1 if operation == 'ats-window-open' else 3
        if not actor_uid or len(args) != count:
            raise SignalError('ATS window requires current actor and exact args')
        for value in args[:1 if count == 1 else 2]:
            if (not isinstance(value, str) or not value.isascii() or not value.isdecimal()
                    or str(int(value)) != value or not 0 < int(value) <= U64):
                raise SignalError('ATS window member/epoch must be positive unsigned decimals')
        if count == 3 and re.fullmatch(r'companion-ats-delta-[1-9][0-9]*\.json', args[2]) is None:
            raise SignalError('ATS window delta must be an owned basename')
    elif operation in ('f4-pickup', 'ats-edit-close', 'ats-edit-restored'):
        if actor_uid != 0 or args:
            raise SignalError('F4/ATS edit lifetime requires actor=0 and no args')
    else:
        raise SignalError('unsupported LOCAL operation')


def _varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def encode_signal(operation: str, actor_uid: int, args=()) -> bytes:
    if isinstance(args, (str, bytes)):
        raise SignalError('args must be a sequence of strings')
    args = tuple(args)
    _validate(operation, actor_uid, args)
    out = bytearray(b'\x08\x07')
    for value in (MARKER, operation, *args):
        raw = value.encode('utf-8')
        out += b'\x12' + _varint(len(raw)) + raw
    out += b'\x18' + _varint(actor_uid)
    return bytes(out)


def _read_varint(body, offset):
    value = 0
    for index in range(10):
        if offset >= len(body):
            raise SignalError('truncated varint')
        byte = body[offset]
        offset += 1
        if index == 9 and byte > 1:
            raise SignalError('varint exceeds uint64')
        value |= (byte & 127) << (index * 7)
        if not byte & 128:
            return value, offset
    raise SignalError('unterminated varint')


def _fields(body):
    offset = 0
    while offset < len(body):
        start = offset
        key, offset = _read_varint(body, offset)
        number, wire = key >> 3, key & 7
        if not 1 <= number <= 0x1FFFFFFF:
            raise SignalError('invalid protobuf field number')
        if wire == 0:
            value, offset = _read_varint(body, offset)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, offset = _read_varint(body, offset)
            else:
                size = 8 if wire == 1 else 4
            end = offset + size
            if end > len(body):
                raise SignalError('truncated protobuf field')
            value, offset = body[offset:end], end
        else:
            raise SignalError('unsupported protobuf wire type')
        yield number, wire, value, body[start:offset]


def decode_signal(body: bytes) -> Signal | None:
    """None for a well-formed non-LOCAL body, SignalError for invalid LOCAL data."""
    if not isinstance(body, (bytes, bytearray, memoryview)):
        raise SignalError('body must be bytes')
    body = bytes(body)
    fields = tuple(_fields(body))
    strings = [value for number, wire, value, _ in fields if number == 2 and wire == 2]
    if MARKER.encode() not in strings:
        return None
    modes, actors, texts, unknown = [], [], [], []
    for number, wire, value, raw in fields:
        if number in (1, 3):
            if wire != 0:
                raise SignalError('wrong scalar wire type')
            (modes if number == 1 else actors).append(value)
        elif number == 2:
            if wire != 2:
                raise SignalError('wrong string wire type')
            try:
                texts.append(value.decode('utf-8'))
            except UnicodeDecodeError as error:
                raise SignalError('invalid UTF-8') from error
        else:
            unknown.append(raw)
    if modes != [7] or len(actors) != 1:
        raise SignalError('LOCAL requires single present f1=7 and f3')
    if len(texts) < 2 or texts[0] != MARKER or texts.count(MARKER) != 1:
        raise SignalError('LOCAL marker must occur exactly once at f2[0]')
    operation, args = texts[1], tuple(texts[2:])
    _validate(operation, actors[0], args)
    return Signal(operation, actors[0], args, tuple(unknown))
