"""0263 schema with explicit local-only issuer/UUID meanings, not vendor auth."""
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import types
import uuid

ROOT = Path(__file__).resolve().parents[2]
_path = ROOT / 'tools/local_entry_server/protobuf.py'
_raw = _path.read_bytes()
if hashlib.sha256(_raw).hexdigest() != 'c6d00262da031fb03a138c34b6a86dfc88f03e8ead2d6e71ae9bb21cd45de389':
    raise ValueError('FROZEN_PROTOBUF_SOURCE_CHANGED')
pb = types.ModuleType('_local_own_login_protobuf')
pb.__file__ = str(_path)
import sys
sys.modules[pb.__name__] = pb
exec(compile(_raw, str(_path), 'exec'), pb.__dict__)
OPCODE = 0x0263
LIMITS = pb.WireLimits(max_body=512, max_fields=4, max_field_bytes=128)

def need(ok, code):
    if not ok:
        raise ValueError(code)

def text(value, code):
    need(type(value) is str and 0 < len(value.encode('utf-8')) <= 128
         and not any(ord(c) < 32 for c in value), code)
    return value

@dataclass(frozen=True, repr=False)
class LocalLoginRequest:
    socket_address_u32: int = field(repr=False)
    issuer: str = field(repr=False)
    guest_uuid: str = field(repr=False)
    selected_tag: str | None = field(default=None, repr=False)

    def __post_init__(self):
        # Mandatory actual 27EE30 return, never selected-server ID/default0.
        need(type(self.socket_address_u32) is int and 0 <= self.socket_address_u32 <= 0xffffffff,
             'EXPLICIT_SOCKET_ADDRESS_UINT32_REQUIRED')
        need(self.issuer == 'standalone.local', 'OWN_LOCAL_ISSUER_REQUIRED')
        try:
            guest = uuid.UUID(text(self.guest_uuid, 'OWN_UUID_REQUIRED'))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('OWN_UUID_REQUIRED') from None
        need(guest.version == 4 and guest.variant == uuid.RFC_4122
             and str(guest) == self.guest_uuid, 'CANONICAL_OWN_UUID4_REQUIRED')
        if self.selected_tag is not None:
            text(self.selected_tag, 'EXPLICIT_LOCAL_SELECTION_TAG_REQUIRED')

    def payload(self):
        fields = [pb.encode_uint32(1, self.socket_address_u32),
                  pb.encode_bytes(2, self.issuer.encode(), limits=LIMITS),
                  pb.encode_bytes(3, self.guest_uuid.encode(), limits=LIMITS)]
        if self.selected_tag is not None:
            fields.append(pb.encode_bytes(4, self.selected_tag.encode(), limits=LIMITS))
        return pb.encode_message(fields, limits=LIMITS)

def parse(payload):
    with pb.parse_message(payload, schema={1: 0, 2: 2, 3: 2, 4: 2}, limits=LIMITS) as message:
        rows = {n: message.occurrences(n) for n in (1, 2, 3, 4)}
        need(all(len(rows[n]) == 1 for n in (1, 2, 3)) and len(rows[4]) <= 1,
             'OWN_LOGIN_REQUIRED_UNIQUE_FIELDS')
        try:
            values = {n: bytes(rows[n][0].value).decode('utf-8', 'strict')
                      for n in (2, 3, 4) if rows[n]}
        except UnicodeError:
            raise ValueError('OWN_LOGIN_UTF8_REQUIRED') from None
        return LocalLoginRequest(rows[1][0].value, values[2], values[3], values.get(4))
