"""Companion bag/equipment window projections for the bridge DLL (LOCAL).

Pure builders, no I/O. The bridge candidate (companion-bridge/SIGNALS.md,
3차) applies one ``LCMPMD2`` frame to its own companion view: the member's
real saved bag rows as an 0964 body, each worn item as an 097A(true) body, and
the member's status as a 4E38 body. These bodies are never sent to the owner's
socket: original 0964/097A/4E38 have no view/owner field, so the server only
publishes them through the bridge model file. Identity, revision and the
explicit snapshot replace are LOCAL host contracts.
"""
from __future__ import annotations

import struct

from tools.local_entry_server import protobuf as pb

MODEL_MAGIC = b'LCMPMD2\x00'
_HEADER = struct.Struct('<8sQQQQQII')
_PACKET = struct.Struct('<HHI')
U64 = (1 << 64) - 1


def model_frame(*, actor: int, generation: int, owner: int, member: int, revision: int,
                packets, replace: bool = True) -> bytes:
    """One frame: header56 + (opcode, 0, length, protobuf body) packets."""
    for name, value in (('actor', actor), ('generation', generation), ('owner', owner),
                        ('member', member), ('revision', revision)):
        if type(value) is not int or not 0 < value <= U64:
            raise ValueError('COMPANION_MODEL_IDENTITY_' + name.upper())
    packets = tuple(packets)
    out = [_HEADER.pack(MODEL_MAGIC, actor, generation, owner, member, revision,
                        1 if replace else 0, len(packets))]
    for opcode, body in packets:
        if type(opcode) is not int or not 0 < opcode <= 0xffff or type(body) is not bytes:
            raise ValueError('COMPANION_MODEL_PACKET')
        out.append(_PACKET.pack(opcode, 0, len(body)) + body)
    return b''.join(out)


def decode_model_frame(frame: bytes):
    """Inverse of model_frame (tests and diagnostics)."""
    if len(frame) < _HEADER.size:
        raise ValueError('COMPANION_MODEL_TRUNCATED')
    magic, actor, generation, owner, member, revision, replace, count = _HEADER.unpack_from(frame)
    if magic != MODEL_MAGIC or replace not in (0, 1):
        raise ValueError('COMPANION_MODEL_HEADER')
    offset, packets = _HEADER.size, []
    for _ in range(count):
        if offset + _PACKET.size > len(frame):
            raise ValueError('COMPANION_MODEL_TRUNCATED')
        opcode, reserved, length = _PACKET.unpack_from(frame, offset)
        offset += _PACKET.size
        if reserved or offset + length > len(frame):
            raise ValueError('COMPANION_MODEL_PACKET')
        packets.append((opcode, frame[offset:offset + length]))
        offset += length
    if offset != len(frame):
        raise ValueError('COMPANION_MODEL_TRAILING')
    return dict(actor=actor, generation=generation, owner=owner, member=member,
                revision=revision, replace=bool(replace), packets=tuple(packets))


def bag_body(kit_frame: bytes, item_defs=None, names=None) -> bytes:
    """The member's saved kit rows with a positive quantity, one 0964 body.

    Q0 equipment anchors stay in the saved row (EquipmentStore contract) but
    are not shown; the frame keeps each row's full raw ItemInfo fields.
    """
    from tools.local_original_session import inventory
    rows = [(inventory.display_fields(r, (item_defs or {}).get(r.template_bits), names)
             if item_defs is not None or names is not None else dict(r.raw_fields))
            for r in inventory.validate_kit_frame(kit_frame)
            if dict(r.raw_fields)[4] > 0]
    if not rows:
        return pb.encode_bool(2, False)
    # LCMPMD2 carries one complete body, not owner-socket ADD packets. Both
    # native bag metadata and equipment bindings use these same ItemEntities.
    frame, = inventory.display_kit_frames(rows, limit=65535)
    return frame[4:-2]


def equipment_bodies(kit_frame: bytes, state, item_defs) -> tuple:
    """097A(uid, key, true) bodies for the member's currently worn items."""
    from tools.local_original_session import equipment_change, inventory
    rows = {r.identifier: r for r in inventory.validate_kit_frame(kit_frame)
            if dict(r.raw_fields)[4] > 0}
    worn = []
    if state.weapon_uid and state.weapon_uid in rows:
        worn.append((state.weapon_uid, 9))  # explicit LOCAL single-weapon key9
    for key, uid in sorted(state.slots):
        if uid in rows:
            worn.append((uid, key))
    return tuple(equipment_change.build_change(uid=uid, key=key, equipped=True)[4:-2]
                 for uid, key in worn)


def status_body(fields) -> bytes:
    from tools.local_original_session.world_status_frames import full_status_frame
    return full_status_frame(fields)[4:-2]


def status_fields(base, *, character_id, record, calculated, lawful, exp_percent):
    """Full SelfInfo-shaped fields for the member's own status projection."""
    from tools.local_original_session import world_stats
    fields = world_stats.self_info_fields(dict(base), calculated)
    fields.update({1: character_id, 2: record.level, 10: record.hp, 11: record.effective_max_hp,
                   12: record.mp, 13: record.effective_max_mp, 26: exp_percent})
    if lawful is not None:
        fields[18] = lawful
    return fields


def map_request(*, actor: int, generation: int, owner: int, member: int, hold: bool,
                lawful: int | None, name: str | bytes = '') -> dict:
    """Field values of an own-companion-request-v1 ``map`` (SIGNALS.md)."""
    from tools.local_original_session.companion_bridge_host import LABEL_BYTES
    if isinstance(name, bytes):
        name = name.decode('utf-8', 'replace')
    # Match label_hex's byte bound, retaining only complete UTF-8 characters.
    name_hex = str(name or '').encode('utf-8')[:LABEL_BYTES].decode('utf-8', 'ignore').encode('utf-8').hex()
    return dict(command='map', actor_uid=actor, actor_generation=generation, owner_uid=owner,
                member_id=member, hold=1 if hold else 0,
                lawful_known=0 if lawful is None else 1, lawful=0 if lawful is None else lawful,
                event_seq=0, ats_epoch=0, name_hex=name_hex)
