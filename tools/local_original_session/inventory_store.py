"""Explicit local authoritative opaque inventory sidecar.

No sender, client observation or equipment semantics. The original singleton
policy stays strict; an explicit collection opt-in adds one local second-instance
grant with a frozen persistence result, never live admission or send authority.
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
INVENTORY_SOURCE_SHA = '92a80df4fc9fe83f173bd15171500245844b52ca29e544dc08a5877f277ecead'
_lock = threading.RLock()
need = inventory.need
CHARACTER_MAX_BYTES = 65536
COLLECTION_STORE_POLICY = 'LOCAL_OPAQUE_ONE_OR_TWO_ITEMS_PER_SAVED_CHARACTER'
SECOND_INSTANCE_POLICY = 'LOCAL_SECOND_TEMPLATE1_INSTANCE_MAX_UID_PLUS_ONE'


@dataclass(frozen=True, slots=True)
class InstanceGrant:
    character_uid: int
    before_frame: bytes
    after_frame: bytes
    prototype_uid: int
    allocated_uid: int
    policy: str



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
    path = inventory.observe.ordinary(Path(inventory.__file__))
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
    """Version1 local sidecar, max3 characters, singleton by default.

    COLLECTION_STORE_POLICY explicitly admits one/two-item canonical frames.
    Existing singleton methods do not acquire second-instance grant semantics.

    Missing UID data is empty/None and never creates a file on restore.
    Character roster membership is checked on each operation, under the original
    character-store lock. This does not prove a live selected writer or account.
    Root must commit after its current prewrite/once checks, before first write;
    errors must not promote caller state or authorize another send.
    """
    MAX_BYTES = 8192

    def __init__(self, character_store_path, *, policy, custody_policy=None):
        need(type(policy) is str and policy in (POLICY, COLLECTION_STORE_POLICY), 'INVENTORY_STORE_EXPLICIT_POLICY_REQUIRED')
        from tools.local_original_session import item_custody
        need(custody_policy is None or (type(custody_policy) is str and
             custody_policy == item_custody.CUSTODY_POLICY and policy == COLLECTION_STORE_POLICY),
             'INVENTORY_CUSTODY_EXPLICIT_POLICY_REQUIRED')
        self.custody_policy = custody_policy
        self._custody_policy_bound = custody_policy
        self._custody_failed = False
        self._collection_policy = policy
        self.profile = Path(character_store_path)
        need(self.profile.is_absolute() and self.profile.name.casefold() != 'inventory.json',
             'INVENTORY_STORE_EXPLICIT_CHARACTER_PROFILE_REQUIRED')
        self.path = self.profile.with_name('inventory.json')
        self._custody_paths = (self.profile, self.path)
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

    def _read(self, *, _collection_keys=None):
        _source()
        self._custody_binding()
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
        if type(data) is dict and data.get('version') == 2:
            self._custody_binding(required=True)
            from tools.local_original_session import item_custody
            value = item_custody.decode(data, raw, known, str(self.profile))
            return {value.character_uid: item_custody.owned_frame(value)}, known
        need(type(data) is dict and set(data) == {'version', 'inventories'}
             and type(data['version']) is int and data['version'] == 1
             and type(data['inventories']) is list and len(data['inventories']) <= realm.MAX_CHARACTERS,
             'INVENTORY_STORE_SCHEMA')
        collection_keys = _collection_keys
        if self._collection_policy == COLLECTION_STORE_POLICY:
            if collection_keys is None:
                collection_keys = inventory._source()[1]
            need(type(collection_keys) is frozenset, 'INVENTORY_COLLECTION_FIXED_KEYS_REQUIRED')
        else:
            need(collection_keys is None, 'INVENTORY_COLLECTION_EXPLICIT_POLICY_REQUIRED')
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
            if self._collection_policy == COLLECTION_STORE_POLICY:
                _source()
                inventory._validate_collection_frame(frame, inventory.COLLECTION_POLICY, collection_keys)
            else:
                need(self._collection_policy == POLICY, 'INVENTORY_STORE_EXPLICIT_POLICY_REQUIRED')
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
        self._custody_legacy_mutation()
        # A legacy object opened before migration must not overwrite v2.
        if self.path.exists():
            self._read()
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
        self._custody_legacy_mutation()
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
        self._custody_legacy_mutation()
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

    def grant_second_instance(self, character_uid, *, expected_frame, prototype_uid,
                              policy, reserved_uids):
        """Persist one explicit local second instance, never send or admit use.

        Only exact saved1 -> saved2 is supported. No automatic skip/reallocation,
        third item, rollback or retry. A persistence exception grants no result,
        including when an atomic replacement completed before that exception.
        """
        self._custody_legacy_mutation()
        need(type(policy) is str and policy == SECOND_INSTANCE_POLICY and
             self._collection_policy == COLLECTION_STORE_POLICY,
             'INVENTORY_SECOND_INSTANCE_EXPLICIT_POLICY_REQUIRED')
        _uid(character_uid)
        need(type(prototype_uid) is int and 0 < prototype_uid <= 0xffffffff,
             'INVENTORY_SECOND_INSTANCE_PROTOTYPE_UID_REQUIRED')
        need(type(reserved_uids) is frozenset and len(reserved_uids) <= 4096 and
             all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in reserved_uids),
             'INVENTORY_SECOND_INSTANCE_EXPLICIT_RESERVED_UIDS_REQUIRED')
        with _lock, realm._lock:
            keys = inventory._source()[1]
            rows, known = self._read(_collection_keys=keys)
            need(character_uid in known, 'INVENTORY_STORE_UNKNOWN_CHARACTER_UID')
            need(type(expected_frame) is bytes and rows.get(character_uid) == expected_frame,
                 'INVENTORY_STORE_EXPECTED_FRAME_CHANGED')
            prototypes = inventory._validate_collection_frame(expected_frame, inventory.COLLECTION_POLICY, keys)
            need(len(prototypes) == 1, 'INVENTORY_SECOND_INSTANCE_EXACT_ONE_PROTOTYPE_REQUIRED')
            prototype, = prototypes
            need(prototype.identifier == prototype_uid and prototype.template_bits == 1,
                 'INVENTORY_SECOND_INSTANCE_OWNED_TEMPLATE1_REQUIRED')
            used = set()
            for frame in rows.values():
                used.update(item.identifier for item in inventory._validate_collection_frame(
                    frame, inventory.COLLECTION_POLICY, keys))
            candidate = max(used) + 1
            need(0 < candidate <= 0xffffffff, 'INVENTORY_SECOND_INSTANCE_UID_EXHAUSTED')
            need(candidate not in used and candidate not in reserved_uids,
                 'INVENTORY_SECOND_INSTANCE_UID_COLLISION')
            fields = dict(prototype.raw_fields)
            fields[1] = candidate
            # New local instance: same current owned prototype's opaque fields,
            # independent server-allocated identity. No client/model mutation.
            allocated = inventory._validate_single_frame(inventory._encode(inventory._values(fields, keys)), keys)
            after = inventory._encode_collection(inventory._collection_items((prototype, allocated), inventory.COLLECTION_POLICY, keys))
            need(inventory._validate_collection_frame(after, inventory.COLLECTION_POLICY, keys) ==
                 (prototype, allocated), 'INVENTORY_SECOND_INSTANCE_CANONICAL_FRAME_REQUIRED')
            rows[character_uid] = after
            self._write(rows)  # Original locked atomic fsync/replace path, once.
            return InstanceGrant(character_uid, expected_frame, after, prototype_uid, candidate, policy)

    def verify_existing_collection(self, character_uid, expected_frame, *, policy):
        """Strict existing-only check; no create/write/admission or retry."""
        need(type(policy) is str and policy == inventory.COLLECTION_POLICY
             and self._collection_policy == COLLECTION_STORE_POLICY,
             'INVENTORY_COLLECTION_READONLY_EXPLICIT_POLICY_REQUIRED')
        _uid(character_uid)
        with _lock, realm._lock:
            rows, known = self._read()
            need(character_uid in known, 'INVENTORY_STORE_UNKNOWN_CHARACTER_UID')
            need(type(expected_frame) is bytes and rows.get(character_uid) == expected_frame,
                 'INVENTORY_STORE_EXPECTED_FRAME_CHANGED')
            return False


    def _custody_binding(self, *, required=False):
        from tools.local_original_session import item_custody
        need(self.custody_policy == self._custody_policy_bound and
             type(self.custody_policy) is type(self._custody_policy_bound),
             'INVENTORY_CUSTODY_POLICY_CHANGED')
        if self.custody_policy is not None:
            need(type(self.custody_policy) is str and
                 self.custody_policy == item_custody.CUSTODY_POLICY and
                 self._collection_policy == COLLECTION_STORE_POLICY and
                 (self.profile, self.path) == self._custody_paths,
                 'INVENTORY_CUSTODY_BINDING_CHANGED')
            need(not self._custody_failed, 'INVENTORY_CUSTODY_FAILED_NO_RETRY')
        if required:
            need(self.custody_policy == item_custody.CUSTODY_POLICY,
                 'INVENTORY_CUSTODY_EXPLICIT_POLICY_REQUIRED')

    def _custody_legacy_mutation(self):
        self._custody_binding()
        need(self.custody_policy is None, 'INVENTORY_CUSTODY_LEGACY_MUTATION_REFUSED')

    def _custody_file(self):
        # Same original bounded, unique-key JSON/roster/path checks. Not a
        # separate sidecar or a permissive version fallback.
        self._custody_binding(required=True)
        _source()
        self._path_check()
        known = {row['uid'] for row in _characters(self.profile)['characters']}
        with self.path.open('rb') as stream:
            need(os.fstat(stream.fileno()).st_size <= self.MAX_BYTES, 'INVENTORY_STORE_SIZE')
            raw = stream.read(self.MAX_BYTES + 1)
        need(len(raw) <= self.MAX_BYTES, 'INVENTORY_STORE_SIZE')
        try:
            data = json.loads(raw, object_pairs_hook=inventory.movement._unique_object)
        except (ValueError, UnicodeError):
            raise ValueError('INVENTORY_STORE_JSON') from None
        return raw, data, known

    def _custody_value(self):
        from tools.local_original_session import item_custody
        raw, data, known = self._custody_file()
        return item_custody.decode(data, raw, known, str(self.profile))

    def custody_snapshot(self, character_uid):
        """Read actual storage data; no selected/live ground authority."""
        _uid(character_uid)
        with _lock, realm._lock:
            value = self._custody_value()
            need(value.character_uid == character_uid, 'ITEM_CUSTODY_KNOWN_CHARACTER_REQUIRED')
            return value

    def _custody_atomic_write(self, value):
        from tools.local_original_session import item_custody
        raw = item_custody.encode(value)
        need(len(raw) <= self.MAX_BYTES, 'INVENTORY_STORE_SIZE')
        self._custody_binding(required=True)
        temporary = self.path.with_name('.inventory-' + uuid.uuid4().hex + '.tmp')
        created = False
        # Any attempted durable operation is terminal on exception, including
        # replace-then-raise. Reopening reads the durable outcome, never retries.
        self._custody_failed = True
        try:
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
            # The locked synchronous readback is part of this same attempt.
            # Clear only for the original reader; any exception restores the
            # terminal latch before this method can return to its caller.
            self._custody_failed = False
            observed = self._custody_value()
            from dataclasses import replace
            need(observed == replace(value, file_sha256=hashlib.sha256(raw).hexdigest()),
                 'ITEM_CUSTODY_PERSISTED_READBACK_CHANGED')
        except BaseException:
            self._custody_failed = True
            raise
        return observed

    def migrate_collection_custody(self, character_uid, expected_frame):
        """Explicit exact v1 AB -> v2 READY; ownership/equipment unchanged.

        The first scope requires exactly one saved collection; another saved
        row is refused rather than discarded. No old profile auto-conversion.
        """
        from tools.local_original_session import item_custody
        _uid(character_uid)
        with _lock, realm._lock:
            raw, data, known = self._custody_file()
            need(character_uid in known, 'INVENTORY_STORE_UNKNOWN_CHARACTER_UID')
            item_custody._members(expected_frame)
            if type(data) is dict and data.get('version') == item_custody.VERSION:
                value = item_custody.decode(data, raw, known, str(self.profile))
                need(value.character_uid == character_uid and value.frame_ab == expected_frame and
                     value.phase == 'READY', 'ITEM_CUSTODY_INITIALIZATION_ALREADY_ADVANCED')
                return value  # Never resets a transfer or rewrites a marker.
            rows, _ = self._read()
            need(rows == {character_uid: expected_frame}, 'ITEM_CUSTODY_EXACT_V1_AB_REQUIRED')
            # The exact raw preimage is checked immediately before replacement.
            current, _, _ = self._custody_file()
            need(current == raw, 'ITEM_CUSTODY_EXPECTED_FILE_CHANGED')
            value = item_custody.CustodySnapshot(character_uid, expected_frame, 'PLAYER',
                'READY', 1, None, None, str(self.profile), hashlib.sha256(raw).hexdigest())
            return self._custody_atomic_write(value)

    def _commit_custody_storage(self, expected, replacement):
        """Private persistence boundary only; callers gain NO live permission.

        Tests exercise local data/IO here. Production entry is commit_custody,
        whose source-bound operation validator currently refuses all issuance.
        """
        from tools.local_original_session import item_custody, equipment_store
        with _lock, realm._lock:
            self._custody_binding(required=True)
            item_custody.validate_transition(expected, replacement)
            current = self._custody_value()
            need(current == expected, 'ITEM_CUSTODY_EXPECTED_STATE_CHANGED')
            equipment = equipment_store.EquipmentStore(self, policy=equipment_store.POLICY,
                collection_policy=equipment_store.COLLECTION_POLICY)
            actual = equipment.restore(expected.character_uid, item_custody.owned_frame(expected))
            need(actual is not None and
                 item_custody._equipment_guard(actual) == replacement.equipment_guard,
                 'ITEM_CUSTODY_ACTUAL_EQUIPMENT_CHANGED')
            return self._custody_atomic_write(replacement)

    def commit_custody(self, expected, operation):
        """Only the real bound-operation validator may reach durable mutation."""
        from tools.local_original_session import item_transfer_session
        self._custody_binding(required=True)
        replacement = item_transfer_session.validate_custody_operation(operation, self, expected)
        return self._commit_custody_storage(expected, replacement)
