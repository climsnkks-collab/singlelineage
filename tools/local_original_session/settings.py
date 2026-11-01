"""Source-bound 4ED6 opaque settings and an explicit local account sidecar.

The sidecar is local policy, not a reconstruction of the original server store.
No UTF-8 decoding, decompression, invented ACK or settings-value logging.
"""
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import struct
import threading
import uuid

from tools.local_own_login_request.codec import LocalLoginRequest, pb
from tools.local_original_session.input import _ordinary, _read

OPCODE = 0x4ed6
LIMITS = pb.WireLimits()  # Existing present-disabled frame/protobuf budget.
_HEADER = struct.Struct('<8s16sBI')
_MAGIC = b'LCSET01\0'
_lock = threading.RLock()


def need(value, code):
    if not value:
        raise ValueError(code)


@dataclass(frozen=True, repr=False)
class SettingsPayload:
    raw: bytes = field(repr=False)
    field1_count: int
    field2_count: int

    def metadata(self):
        return dict(body_bytes=len(self.raw), field1_present=True, field2_present=self.field2_count > 0,
                    field1_occurrences=self.field1_count, field2_occurrences=self.field2_count,
                    sha256=hashlib.sha256(self.raw).hexdigest())

    def __repr__(self):
        return f'SettingsPayload(body_bytes={len(self.raw)}, field2_present={self.field2_count > 0})'


def parse(payload):
    with pb.parse_message(payload, schema={1: 2, 2: 2}, limits=LIMITS) as message:
        first, second = len(message.occurrences(1)), len(message.occurrences(2))
        need(first > 0, 'SETTINGS_REQUIRED_FIELD1')
        # Preserve the original request, including order/repeated occurrences.
        # Presence is distinct from an explicitly present empty byte string.
        return SettingsPayload(bytes(payload), first, second)


class SettingsStore:
    def __init__(self, path, expected_uuid, *, profile_path):
        LocalLoginRequest(0, 'standalone.local', expected_uuid)
        self.account = uuid.UUID(expected_uuid).bytes
        self.path, profile = Path(path), Path(profile_path)
        need(self.path.is_absolute() and profile.is_absolute() and self.path.parent == profile.parent
             and self.path.name.casefold() not in (profile.name.casefold(), 'positions.json'),
             'EXPLICIT_SEPARATE_SETTINGS_PATH_REQUIRED')
        self.failed, self.committed = False, 0
        self.last = None
        with _lock:
            previous = self._load()
            if previous is not None:
                self.last = previous.metadata()

    def _path_check(self):
        _ordinary(self.path.parent, directory=True)
        _ordinary(self.path, absent=True)

    def _load(self):
        self._path_check()
        try:
            raw = _read(self.path, _HEADER.size + LIMITS.max_body)
        except FileNotFoundError:
            return None
        need(len(raw) >= _HEADER.size, 'SETTINGS_STORE_HEADER_REQUIRED')
        magic, account, presence, size = _HEADER.unpack_from(raw)
        need(magic == _MAGIC and account == self.account and presence in (1, 3)
             and size == len(raw) - _HEADER.size, 'SETTINGS_STORE_IDENTITY_OR_SIZE')
        record = parse(memoryview(raw)[_HEADER.size:])
        need(presence == (1 | (2 if record.field2_count else 0)), 'SETTINGS_STORE_PRESENCE')
        return record

    def save(self, record):
        need(type(record) is SettingsPayload and not self.failed, 'SETTINGS_STORE_FATAL_OR_INVALID')
        # Reparse the immutable bytes rather than trusting caller-built metadata.
        checked = parse(record.raw)
        need(checked == record, 'SETTINGS_RECORD_MISMATCH')
        temporary = self.path.with_name('.settings-' + uuid.uuid4().hex + '.tmp')
        created = False
        try:
            with _lock:
                self._load()  # Refuse malformed/wrong-account existing storage.
                raw = _HEADER.pack(_MAGIC, self.account, 1 | (2 if record.field2_count else 0), len(record.raw)) + record.raw
                self._path_check()
                with temporary.open('xb') as stream:
                    created = True
                    need(stream.write(raw) == len(raw), 'SETTINGS_STORE_PARTIAL_WRITE')
                    stream.flush()
                    os.fsync(stream.fileno())
                self._path_check()
                os.replace(temporary, self.path)
                self.last = record.metadata()
                self.committed += 1
        except BaseException:
            self.failed = True
            raise
        finally:
            if created and temporary.exists():
                _ordinary(temporary)
                temporary.unlink()

    def metadata(self):
        return dict(policy='LOCAL_ACCOUNT_OPAQUE_LAST_REQUEST', committed=self.committed,
                    failed=self.failed, last=dict(self.last) if self.last is not None else None,
                    values_logged=False)

    def saved_raw(self):
        """The last saved 4ED6 body for this account, or None (never a default)."""
        with _lock:
            record = self._load()
        return None if record is None else record.raw


NOTI_OPCODE = 0x4ed7


def _loadable(codec, wrapper):
    """ATS item slots the native loader resolves again; any other blob as saved."""
    try:
        return codec.loadable_ats(wrapper)
    except ValueError:
        return wrapper


def noti_frame(raw):
    """4ED7 for a saved 4ED6 body: hex(f1) and hex(f2), always together.

    Uses the last occurrence of each field, as the client's own save does.
    Returns None when f2 is absent or either wrapper is malformed.
    """
    if raw is None:
        return None
    from tools.local_original_session import ats_config_codec as codec
    try:
        with pb.parse_message(raw, schema={1: 2, 2: 2}, limits=LIMITS) as message:
            first, second = message.occurrences(1), message.occurrences(2)
            if not first or not second:
                return None
            f1, f2 = bytes(first[-1].value), bytes(second[-1].value)
        body = pb.encode_bytes(1, codec.noti_field(f1)) + pb.encode_bytes(2, codec.noti_field(_loadable(codec, f2)))
    except (ValueError, pb.WireError):
        return None
    if len(body) + 6 > 0xffff:
        return None
    return struct.pack('<HH', len(body) + 6, NOTI_OPCODE) + body + b'\0\0'
