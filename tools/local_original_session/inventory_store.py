"""Explicit local authoritative empty/one-row inventory sidecar.

No sender, receipt, client observation, allocator or equipment semantics.
The caller supplies the current saved character UID, independently of ItemInfo
f1. This file preserves canonical ADD bytes including all raw optional presence.
Caller authority, admission and no-retry lifetime remain outside this store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import uuid

from tools.local_character_creation import realm
from tools.local_original_session import inventory

POLICY = 'LOCAL_OPAQUE_ONE_ROW_PER_SAVED_CHARACTER'
INVENTORY_SOURCE_SHA = '9f22fecc27912ad32c015d894c9fec636b2286c3826ab83487a06969e81b981d'
_lock = threading.RLock()
need = inventory.need
CHARACTER_MAX_BYTES = 65536


@dataclass(frozen=True, slots=True)
class _CharacterSnapshot:
    """Read-only path-shaped input to the unchanged roster validator.

    No filesystem fallback: exists is true because the real file was already
    opened/read within its bound, and read_bytes returns that exact snapshot.
    """
    raw: bytes = field(repr=False)

    def exists(self):
        return True

    def read_bytes(self):
        return self.raw


def _characters(profile):
    with profile.open('rb') as stream:
        need(os.fstat(stream.fileno()).st_size <= CHARACTER_MAX_BYTES,
             'INVENTORY_STORE_CHARACTER_SIZE')
        raw = stream.read(CHARACTER_MAX_BYTES + 1)
    need(len(raw) <= CHARACTER_MAX_BYTES, 'INVENTORY_STORE_CHARACTER_SIZE')
    try:
        json.loads(raw, object_pairs_hook=inventory.movement._unique_object)
    except (ValueError, UnicodeError):
        raise ValueError('INVENTORY_STORE_CHARACTER_JSON') from None
    # Reuse every original schema/row/UID/name/wire validation against the same
    # immutable bytes. CharacterStore's constructor only records its Path; the
    # private validator then sees the snapshot adapter, never another file read.
    validator = realm.CharacterStore(profile)
    validator.path = _CharacterSnapshot(raw)
    return validator._read()


def _source():
    path = inventory.observe.ordinary(inventory.observe.ROOT / 'tools/local_original_session/inventory.py')
    need(0 < path.stat().st_size <= 1048576
         and hashlib.sha256(path.read_bytes()).hexdigest() == INVENTORY_SOURCE_SHA,
         'INVENTORY_STORE_PARENT_SOURCE_CHANGED')


def _frame(value):
    _source()
    # The existing strict validator accepts exact bytes only, full 17 explicit
    # raw fields, one child and explicit outer false. It supplies no defaults.
    return inventory.validate_frame(value)


def _uid(value):
    need(type(value) is int and 0 < value <= 0xffffffff, 'INVENTORY_STORE_CHARACTER_UID_REQUIRED')


class InventoryStore:
    """Version1 local sidecar, max3 characters, at most one item per UID.

    Missing UID data is empty/None and never creates a file on restore.
    Character roster membership is checked on each operation, under the original
    character-store lock. This does not prove a live selected writer or account.
    Root must commit after its current prewrite/once checks, before first write;
    errors must not promote caller state or authorize another send.
    """
    MAX_BYTES = 8192

    def __init__(self, character_store_path, *, policy):
        need(type(policy) is str and policy == POLICY, 'INVENTORY_STORE_EXPLICIT_POLICY_REQUIRED')
        self.profile = Path(character_store_path)
        need(self.profile.is_absolute() and self.profile.name.casefold() != 'inventory.json',
             'INVENTORY_STORE_EXPLICIT_CHARACTER_PROFILE_REQUIRED')
        self.path = self.profile.with_name('inventory.json')
        with _lock, realm._lock:
            self._read()

    def _path_check(self):
        need(self.path.parent.is_dir(), 'INVENTORY_STORE_EXISTING_PROFILE_DIRECTORY_REQUIRED')
        for target in (self.profile, self.path):
            for part in (target, *target.parents):
                if not os.path.lexists(part):
                    continue
                info = part.lstat()
                need(not stat.S_ISLNK(info.st_mode)
                     and not getattr(info, 'st_file_attributes', 0) & 0x400,
                     'INVENTORY_STORE_REPARSE_REFUSED')
                if part == target:
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                         'INVENTORY_STORE_REGULAR_SINGLE_FILE_REQUIRED')
        need(self.profile.is_file(), 'INVENTORY_STORE_CHARACTER_PROFILE_REQUIRED')

    def _read(self):
        _source()
        self._path_check()
        known = {row['uid'] for row in _characters(self.profile)['characters']}
        if not self.path.exists():
            return {}, known
        with self.path.open('rb') as stream:
            need(os.fstat(stream.fileno()).st_size <= self.MAX_BYTES, 'INVENTORY_STORE_SIZE')
            raw = stream.read(self.MAX_BYTES + 1)
        need(len(raw) <= self.MAX_BYTES, 'INVENTORY_STORE_SIZE')
        try:
            data = json.loads(raw, object_pairs_hook=inventory.movement._unique_object)
        except (ValueError, UnicodeError):
            raise ValueError('INVENTORY_STORE_JSON') from None
        need(type(data) is dict and set(data) == {'version', 'inventories'}
             and type(data['version']) is int and data['version'] == 1
             and type(data['inventories']) is list and len(data['inventories']) <= realm.MAX_CHARACTERS,
             'INVENTORY_STORE_SCHEMA')
        restored = {}
        for row in data['inventories']:
            need(type(row) is dict and set(row) == {'uid', 'frame'}, 'INVENTORY_STORE_ROW')
            uid, encoded = row['uid'], row['frame']
            _uid(uid)
            need(uid in known, 'INVENTORY_STORE_UNKNOWN_CHARACTER_UID')
            need(uid not in restored, 'INVENTORY_STORE_DUPLICATE_CHARACTER_UID')
            need(type(encoded) is str and 12 <= len(encoded) <= inventory.MAX_FRAME * 2,
                 'INVENTORY_STORE_FRAME_HEX_REQUIRED')
            try:
                frame = bytes.fromhex(encoded)
            except ValueError:
                raise ValueError('INVENTORY_STORE_FRAME_HEX_REQUIRED') from None
            need(frame.hex() == encoded, 'INVENTORY_STORE_CANONICAL_FRAME_HEX_REQUIRED')
            _frame(frame)
            restored[uid] = frame
        return restored, known

    def restore(self, character_uid):
        """Return immutable canonical bytes or None; never transmit or create."""
        _uid(character_uid)
        with _lock, realm._lock:
            rows, known = self._read()
            need(character_uid in known, 'INVENTORY_STORE_UNKNOWN_CHARACTER_UID')
            return rows.get(character_uid)

    def _write(self, rows):
        data = dict(version=1, inventories=[dict(uid=uid, frame=frame.hex())
                                           for uid, frame in sorted(rows.items())])
        raw = (json.dumps(data, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')
        need(len(raw) <= self.MAX_BYTES, 'INVENTORY_STORE_SIZE')
        temporary = self.path.with_name('.inventory-' + uuid.uuid4().hex + '.tmp')
        created = False
        try:
            self._path_check()
            with temporary.open('xb') as stream:
                created = True
                need(stream.write(raw) == len(raw), 'INVENTORY_STORE_PARTIAL_WRITE')
                stream.flush()
                os.fsync(stream.fileno())
            self._path_check()
            os.replace(temporary, self.path)
        finally:
            if created and temporary.exists():
                temporary.unlink()

    def grant(self, character_uid, frame, *, existing_only=False):
        """Persist before caller promotion; True=new row, False=identical row.

        A failed operation does not return a grant. If the OS replacement took
        effect before an exception, the disk outcome may be the complete new
        row. Reload can identify it; this API never instructs the caller to send
        or retry, including after an ambiguous transport/disk outcome.
        existing_only=True checks the existing canonical row under the same
        locks and never creates a missing file or character row.
        """
        need(type(existing_only) is bool, 'INVENTORY_STORE_EXISTING_ONLY_BOOL_REQUIRED')
        _uid(character_uid)
        item = _frame(frame)
        with _lock, realm._lock:
            rows, known = self._read()
            need(character_uid in known, 'INVENTORY_STORE_UNKNOWN_CHARACTER_UID')
            previous = rows.get(character_uid)
            if previous is not None:
                if previous == frame:
                    return False
                need(_frame(previous).identifier != item.identifier, 'INVENTORY_STORE_ITEM_CONFLICT')
                raise ValueError('INVENTORY_STORE_ONE_ROW_LIMIT')
            need(not existing_only, 'INVENTORY_STORE_EXISTING_ROW_REQUIRED')
            need(len(rows) < realm.MAX_CHARACTERS, 'INVENTORY_STORE_CHARACTER_LIMIT')
            rows[character_uid] = frame
            self._write(rows)
            return True

    def replace_existing(self, character_uid, expected_frame, new_frame):
        """Replace the exact saved row; no selection, send or item-use policy.

        Both inputs are complete canonical ADD frames, preserving every raw
        field. Only the source-confirmed UPDATE callback fields may differ.
        A stale expectation is refused even for a requested no-op. Exceptions
        propagate, including an ambiguous complete replacement before failure;
        callers receive no retry or rollback instruction from this method.
        """
        from tools.local_original_session import inventory_update
        _uid(character_uid)
        expected, replacement = _frame(expected_frame), _frame(new_frame)
        need(inventory_update.source_ready() is True, 'INVENTORY_STORE_UPDATE_SOURCE_REQUIRED')
        need(expected.identifier == replacement.identifier, 'INVENTORY_STORE_ITEM_CONFLICT')
        before, after = dict(expected.raw_fields), dict(replacement.raw_fields)
        need({key for key in before if before[key] != after[key]} <= {4, 5, 7, 18},
             'INVENTORY_STORE_UPDATE_FIELDS_REQUIRED')
        with _lock, realm._lock:
            rows, known = self._read()
            need(character_uid in known, 'INVENTORY_STORE_UNKNOWN_CHARACTER_UID')
            previous = rows.get(character_uid)
            need(previous is not None, 'INVENTORY_STORE_EXISTING_ROW_REQUIRED')
            need(previous == expected_frame, 'INVENTORY_STORE_EXPECTED_FRAME_CHANGED')
            if previous == new_frame:
                return False
            rows[character_uid] = new_frame
            self._write(rows)
            return True
