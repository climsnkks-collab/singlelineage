"""Persistent selected-owner movement with a separate local positions sidecar.

CS4E2B parsing/deltas use the existing source-bound route and authority helpers.
Successful movement sends no self SC4E2C. SC4EE0 on stale/blocked/unknown edges
is explicit local correction policy based on the verified original consumer;
it does not claim to reconstruct official server acceptance/response policy.
No socket, native process, external sender, or binary analysis is used here.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
import inspect
import json
import os
from pathlib import Path
import stat
import struct
import threading
import time
import uuid

from tools.local_movement_session_route.route import parse_payload, authority, pb
from tools.local_character_creation.realm import MAX_CHARACTERS, _valid_name
from tools.local_original_session.world_terrain import DEFAULT_MAP_IDS, LAZY_MAP_IDS

CORRECTION_OPCODE = 0x4ee0
MAX_COUNTER = (1 << 64) - 1
SUPPORTED_MAP_IDS = frozenset((*DEFAULT_MAP_IDS, *LAZY_MAP_IDS))
_store_lock = threading.RLock()


def need(value, code):
    if not value:
        raise ValueError(code)


@dataclass(frozen=True, slots=True)
class Position:
    uid: int
    name: str = field(repr=False)
    map_id: int
    word0: int
    word1: int

    def __post_init__(self):
        need(type(self.uid) is int and 0 < self.uid <= 0xffffffff, 'SELECTED_UID_U32_REQUIRED')
        need(_valid_name(self.name), 'SELECTED_SAVED_NAME_REQUIRED')
        need(type(self.map_id) is int and -(1 << 31) <= self.map_id < (1 << 31),
             'SELECTED_MAP_INT32_REQUIRED')
        authority.pack_grid(self.word0, self.word1)

    @property
    def packed(self):
        return authority.pack_grid(self.word0, self.word1)

    def metadata(self):
        return dict(uid=self.uid, map_id=self.map_id, grid=[self.word0, self.word1])


def correction_frame(position):
    """SC_MOVE_BACKWARD_NOTI: required int32 f1=word0, f2=word1.

    Consumer/schema: work/local_server_rea_20261016/self_response_findings.md E2
    and response_evidence/backward-static.json. The existing world contract has
    no 4EE0 row, so use its same pure varint/S2C framing without changing it.
    This local grid is uint16; both values also fit the verified signed32 schema.
    """
    need(type(position) is Position, 'AUTHORITY_POSITION_REQUIRED')
    body = pb.encode_message([
        pb.encode_varint(1 << 3) + pb.encode_varint(position.word0),
        pb.encode_varint(2 << 3) + pb.encode_varint(position.word1),
    ])
    return struct.pack('<HH', len(body) + 6, CORRECTION_OPCODE) + body + b'\0\0'


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'POSITION_STORE_DUPLICATE_KEY')
        result[key] = value
    return result


class PositionStore:
    """Version1 sidecar; never reads or rewrites the character-store contents.

    Supply the explicit per-profile character-store path. Only its sibling
    positions.json is written. One current map/grid per saved UID, at most the
    existing local realm's three characters. Malformed existing data refuses;
    it is never replaced by a default empty store. In-process commits serialize
    read/compare/atomic replace, including separate services sharing this store.
    """
    MAX_BYTES = 4096

    def __init__(self, character_store_path):
        profile = Path(character_store_path)
        need(profile.is_absolute() and profile.name.casefold() != 'positions.json',
             'EXPLICIT_CHARACTER_PROFILE_PATH_REQUIRED')
        self.path = profile.with_name('positions.json')
        self._path_check()
        with _store_lock:
            self._read()

    def _path_check(self):
        need(self.path.parent.is_dir(), 'EXISTING_PROFILE_DIRECTORY_REQUIRED')
        for part in (self.path, *self.path.parents):
            if not os.path.lexists(part):
                continue
            info = part.lstat()
            need(not stat.S_ISLNK(info.st_mode)
                 and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'POSITION_STORE_REPARSE_REFUSED')
            if part == self.path:
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                     'POSITION_STORE_REGULAR_SINGLE_FILE_REQUIRED')

    def _read(self):
        self._path_check()
        if not self.path.exists():
            return dict(version=1, positions=[])
        with self.path.open('rb') as stream:
            need(os.fstat(stream.fileno()).st_size <= self.MAX_BYTES, 'POSITION_STORE_SIZE')
            raw = stream.read(self.MAX_BYTES + 1)
        need(len(raw) <= self.MAX_BYTES, 'POSITION_STORE_SIZE')
        try:
            data = json.loads(raw, object_pairs_hook=_unique_object)
        except (ValueError, UnicodeError):
            raise ValueError('POSITION_STORE_JSON') from None
        need(type(data) is dict and set(data) == {'version', 'positions'}
             and type(data['version']) is int and data['version'] == 1
             and type(data['positions']) is list and len(data['positions']) <= MAX_CHARACTERS,
             'POSITION_STORE_SCHEMA')
        seen = set()
        for row in data['positions']:
            need(type(row) is dict and set(row) == {'uid', 'map_id', 'grid'}
                 and type(row['uid']) is int and 0 < row['uid'] <= 0xffffffff
                 and type(row['map_id']) is int and -(1 << 31) <= row['map_id'] < (1 << 31)
                 and type(row['grid']) is list and len(row['grid']) == 2,
                 'POSITION_STORE_ROW')
            authority.pack_grid(*row['grid'])
            need(row['uid'] not in seen, 'POSITION_STORE_DUPLICATE_UID')
            seen.add(row['uid'])
        return data

    def restore(self, selected):
        """Use saved UID/map/grid, retaining the currently selected saved name.

        The caller must build/check its initial world from this returned snapshot,
        including rejecting a stored map it cannot actually load. No client
        request can choose a UID, name, map, or fallback coordinate here.
        """
        need(type(selected) is Position, 'SELECTED_POSITION_REQUIRED')
        with _store_lock:
            row = next((r for r in self._read()['positions'] if r['uid'] == selected.uid), None)
            if row is None:
                return selected
            return replace(selected, map_id=row['map_id'], word0=row['grid'][0], word1=row['grid'][1])

    def _write(self, data):
        raw = (json.dumps(data, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')
        need(len(raw) <= self.MAX_BYTES, 'POSITION_STORE_SIZE')
        temporary = self.path.with_name('.positions-' + uuid.uuid4().hex + '.tmp')
        try:
            self._path_check()
            with temporary.open('xb') as stream:
                need(stream.write(raw) == len(raw), 'POSITION_STORE_PARTIAL_WRITE')
                stream.flush()
                os.fsync(stream.fileno())
            self._path_check()
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def commit(self, expected, updated, *, transition=False):
        """Persist first. On any error the caller must not promote memory.

        Compare any existing UID row to expected to detect another authority
        changing it. An error after an OS replacement has uncertain disk outcome;
        subsequent retries fail the comparison rather than overwrite that state.
        """
        need(type(expected) is Position and type(updated) is Position
             and (updated.uid, updated.name) == (expected.uid, expected.name)
             and (updated.map_id == expected.map_id or transition is True
                  and expected.map_id in SUPPORTED_MAP_IDS and updated.map_id in SUPPORTED_MAP_IDS),
             'SAME_SELECTED_POSITION_REQUIRED')
        with _store_lock:
            data = self._read()
            previous = next((r for r in data['positions'] if r['uid'] == expected.uid), None)
            if previous is not None:
                need(previous == expected.metadata(), 'POSITION_STORE_AUTHORITY_CHANGED')
            else:
                need(len(data['positions']) < MAX_CHARACTERS, 'POSITION_STORE_UID_LIMIT')
            rows = [r for r in data['positions'] if r['uid'] != expected.uid]
            rows.append(updated.metadata())
            self._write(dict(version=1, positions=sorted(rows, key=lambda r: r['uid'])))


@dataclass(frozen=True, slots=True)
class MoveResult:
    accepted: bool
    reason: str
    position: Position
    replies: tuple = field(default=(), repr=False)
    unknown: bool = False
    fatal: bool = False

    def metadata(self):
        return dict(accepted=self.accepted, reason=self.reason, unknown=self.unknown, fatal=self.fatal,
                    authority=self.position.metadata(), reply_count=len(self.replies),
                    own_SC4E2C_count=0, policy='LOCAL_AUTHORITY_WITH_SOURCE_CONSUMER_CORRECTION')


class MovementService:
    """One selected actor and literal admitted connection, serialized per service.

    owner_guard(connection, position) must currently validate the SAME admitted
    writer, selected saved UID/name/map and retained native identity. Return True
    only on a current positive result; False/None/exception authorize no body
    parsing or response. It must not mutate/re-enter this service.

    edge_passability(uid, map_id, start_packed, direction, destination_packed)
    returns True/False/None from current exact-edge tile/navigation/occupancy
    evidence. The callback owns that verification; this service does not turn a
    generic tile flag, old witness, or constructed DTO into live evidence.

    Both callbacks may be synchronous or async. After an awaited edge check,
    owner/selection is checked again before correction or durable commit. With
    a successful store commit there is no await before authority promotion.
    Every move is request driven; no one-step budget, witness deadline, payload
    hash replay set, or gameplay interpretation of transport sequence exists.
    requests_received counts locked dispatch entries; corrections_prepared
    counts completed correction-frame preparation, never transport or client
    consumption. These saturating diagnostics do not change movement policy.
    """
    def __init__(self, selected, *, connection, owner_guard, edge_passability, store, edge_fallback=None):
        need(type(selected) is Position and connection is not None, 'SELECTED_OWNER_REQUIRED')
        need(callable(owner_guard) and callable(edge_passability), 'CURRENT_OWNER_EDGE_CALLBACKS_REQUIRED')
        need(isinstance(store, PositionStore), 'EXPLICIT_POSITION_STORE_REQUIRED')
        need(edge_fallback is None or callable(edge_fallback), 'EDGE_FALLBACK_CALLBACK_REQUIRED')
        self._position = store.restore(selected)
        self._connection = connection
        self._owner_guard, self._edge_passability = owner_guard, edge_passability
        # Optional: edge_fallback(map_id, x, y, direction) -> True/False/None is
        # consulted only when edge_passability returned None (UNKNOWN).
        self._edge_fallback = edge_fallback
        self._store = store
        self._lock = asyncio.Lock()
        self.committed = 0
        self.requests_received = 0
        self.corrections_prepared = 0
        self.correction_reasons = {}  # reason[:detail] -> count; diagnostics only.
        self.edge_fallback_accepted = 0
        self.last_result = None
        self.fatal = False
        # Last self 4E96 resend: (map_id, packed cell, deadline, remaining requests).
        self._published = None
        self.published_adopted = 0

    def snapshot(self):
        return self._position

    PUBLISHED_START_SECONDS = 3.0
    PUBLISHED_START_REQUESTS = 4

    def actor_published(self, position=None):
        """Record a self 4E96 resend at the current (or given) committed cell.

        The client rebuilds a same-UID actor at the published cell (REA272), so
        a following move may start there although later steps had committed.
        Only that exact cell, shortly after and within a few requests, is adopted.
        """
        position = self._position if position is None else position
        self._published = (position.map_id, position.packed,
                           time.monotonic() + self.PUBLISHED_START_SECONDS, self.PUBLISHED_START_REQUESTS)

    def _published_start(self, start):
        published, self._published = self._published, None
        if published is None:
            return False
        map_id, packed, deadline, remaining = published
        if remaining <= 0 or time.monotonic() > deadline or map_id != self._position.map_id:
            return False
        if start != packed:
            if remaining > 1:
                self._published = (map_id, packed, deadline, remaining - 1)
            return False
        return True

    def relocate(self, updated):
        """Owned world operation: existing CAS persists before promotion.

        Caller holds the selected connection/world operation locks and has
        checked current ownership. Same-map teleport and opt-in map experiments
        both retain the existing PositionStore CAS.
        """
        try:
            self._store.commit(self._position, updated, transition=True)
        except BaseException:
            self.fatal = True
            raise
        self._position = updated
        self.committed = min(MAX_COUNTER, self.committed + 1)

    async def _owner(self):
        try:
            result = self._owner_guard(self._connection, self._position)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            return None
        return result if type(result) is bool else None

    def _result(self, reason, *, accepted=False, correction=False, unknown=False, fatal=False, detail=None):
        replies = (correction_frame(self._position),) if correction else ()
        if correction:
            self.corrections_prepared = min(MAX_COUNTER, self.corrections_prepared + 1)
            key = reason if detail is None else reason + ':' + str(detail)[:96]
            if key in self.correction_reasons or len(self.correction_reasons) < 16:
                self.correction_reasons[key] = min(MAX_COUNTER, self.correction_reasons.get(key, 0) + 1)
        result = MoveResult(accepted, reason, self._position, replies, unknown, fatal)
        self.last_result = result.metadata()  # One bounded metadata snapshot.
        return result

    async def handle_CS4E2B(self, payload, *, transition=None):
        async with self._lock:
            self.requests_received = min(MAX_COUNTER, self.requests_received + 1)
            if self.fatal:
                return self._result('MOVEMENT_FATAL_UNKNOWN', unknown=True, fatal=True)
            allowed = await self._owner()
            if allowed is not True:
                return self._result('OWNER_REFUSED' if allowed is False else 'OWNER_UNKNOWN',
                                    unknown=allowed is None)
            try:
                start, direction = parse_payload(payload)
            except ValueError:
                return self._result('MALFORMED_MOVE_PAYLOAD')
            if start != self._position.packed:
                if not self._published_start(start):
                    return self._result('STALE_START', correction=True)
                # Start is exactly the cell of the self 4E96 just resent: adopt
                # it (saved like any move) instead of a backward correction.
                adopted = replace(self._position, word0=authority.unpack_grid(start)[0],
                                  word1=authority.unpack_grid(start)[1])
                try:
                    self._store.commit(self._position, adopted)
                except Exception:
                    self.fatal = True
                    return self._result('POSITION_SAVE_FAILED', unknown=True, fatal=True)
                self._position = adopted
                self.published_adopted = min(MAX_COUNTER, self.published_adopted + 1)
            elif self._published is not None:
                map_id, packed, deadline, remaining = self._published
                self._published = (map_id, packed, deadline, remaining - 1) if remaining > 1 else None
            if not 0 <= direction < len(authority.DELTAS):
                return self._result('DIRECTION_0_TO_7_REQUIRED', correction=True)
            words = authority.unpack_grid(start)
            target = tuple(a + delta for a, delta in zip(words, authority.DELTAS[direction]))
            if any(not 0 <= word <= 65535 for word in target):
                return self._result('GRID_BOUNDARY', correction=True)
            if transition is not None:
                # Explicit LOCAL stair policy (L1J C_MoveChar): an exact next
                # cell can be a transfer trigger rather than a standable tile.
                # Ordinary movement still uses the unchanged edge path below.
                replies = transition(self._position, *target)
                if replies is not None:
                    return replace(self._result('LOCAL_MAP_TRANSITION', accepted=True), replies=tuple(replies))
            destination = authority.pack_grid(*target)
            try:
                edge = self._edge_passability(self._position.uid, self._position.map_id,
                                              start, direction, destination)
                if inspect.isawaitable(edge):
                    edge = await edge
            except Exception:
                edge = None
            detail = fallback_used = None
            if edge is None:
                last = getattr(self._edge_passability, 'last_result', None)
                detail = last.get('reason') if type(last) is dict and type(last.get('reason')) is str else None
                if self._edge_fallback is not None:
                    try:
                        fallback = self._edge_fallback(self._position.map_id, words[0], words[1], direction)
                    except Exception:
                        fallback = None
                    if fallback is True:
                        edge, fallback_used = True, True
                    else:
                        detail = (detail or 'NONE') + ('/FALLBACK_BLOCKED' if fallback is False
                                                       else '/FALLBACK_UNKNOWN')
            # Nothing can commit or emit correction after owner/selection loss.
            allowed = await self._owner()
            if allowed is not True:
                return self._result('OWNER_REFUSED' if allowed is False else 'OWNER_UNKNOWN',
                                    unknown=allowed is None)
            if edge is not True:
                return self._result('EDGE_BLOCKED' if edge is False else 'EDGE_UNKNOWN',
                                    correction=True, unknown=edge is not False, detail=detail)
            updated = replace(self._position, word0=target[0], word1=target[1])
            try:
                self._store.commit(self._position, updated)
            except Exception:
                self.fatal = True
                return self._result('POSITION_SAVE_FAILED', unknown=True, fatal=True)
            self._position = updated
            self.committed = min(MAX_COUNTER, self.committed + 1)
            if fallback_used:
                self.edge_fallback_accepted = min(MAX_COUNTER, self.edge_fallback_accepted + 1)
            return self._result('COMMITTED', accepted=True)
