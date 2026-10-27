"""M1 world progression: saved cumulative EXP/level/max HP-MP and the EXP display percent.

The character store (tools/local_character_creation/realm.py CharacterStore) has a
closed row schema (uid/name/class/gender/attributes) and always reports level 1,
so progression lives in one sibling sidecar like movement.PositionStore's
positions.json: ``progression.json`` = {version: 1, rows: [{uid, exp, level,
max_hp, max_mp, lawful?}]}. Old rows without lawful read as 0. A missing row means the fresh character (EXP 0, level 1,
SelfInfo maxima). Writes are temp+fsync+replace; the in-memory copy is the
single-process authority after the first read, so request paths do not re-read.

EXP display: SC_STATUS f26 is a double shown as ``{:.4f}%`` with a 0..100 gauge
(game-core-prep/M1_REWARD_PACKETS.md 1(1)). The original percent producer is not
known; LOCAL policy is the progress inside the current level of data/m1/pc_exp:
100 * (exp - need[level]) / (need[level + 1] - need[level]), 0 at the table top.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
import uuid

from tools.local_original_session.game_data import M1Data

MAX_BYTES = 8192
MAX_ROWS = 16
_lock = threading.Lock()


def need(ok, code):
    if not ok:
        raise ValueError(code)


@dataclass(frozen=True, slots=True)
class Progress:
    exp: int
    level: int
    max_hp: int | None = None  # None: keep the SelfInfo baseline value
    max_mp: int | None = None
    lawful: int = 500  # LOCAL fresh baseline; run395 Classic includes 500 in neutral.


def exp_percent(data: M1Data, exp: int, level: int) -> float:
    table = data.pc_exp
    if level >= len(table):
        return 0.0
    low, high = table[level - 1], table[level]
    if high <= low:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (exp - low) / (high - low)))


def _valid_row(row) -> bool:
    return (type(row) is dict and {'uid', 'exp', 'level', 'max_hp', 'max_mp'} <= set(row)
            <= {'uid', 'exp', 'level', 'max_hp', 'max_mp', 'lawful'}
            and type(row.get('lawful', 0)) is int and -32768 <= row.get('lawful', 0) <= 32767
            and type(row['uid']) is int and 0 < row['uid'] <= 0xffffffff
            and type(row['exp']) is int and 0 <= row['exp'] < 1 << 62
            and type(row['level']) is int and 1 <= row['level'] <= 255
            and all(row[k] is None or (type(row[k]) is int and 0 < row[k] <= 0x7fffffff)
                    for k in ('max_hp', 'max_mp')))


class ProgressStore:
    def __init__(self, character_store_path):
        profile = Path(character_store_path)
        need(profile.is_absolute(), 'PROGRESS_STORE_ABSOLUTE_PROFILE_REQUIRED')
        self.path = profile.with_name('progression.json')
        self._rows: dict[int, Progress] | None = None
        self._vitals = None

    def vitals(self, uid):
        """Startup-loaded HP/MP sidecar, independent of the quest Progress schema."""
        if self._vitals is None:
            path = self.path.with_name('vitals.json')
            rows = {}
            if path.exists():
                raw = path.read_bytes()
                need(len(raw) <= MAX_BYTES, 'VITALS_STORE_SIZE')
                body = json.loads(raw)
                need(type(body) is dict and set(body) == {'version', 'rows'}
                     and body['version'] == 1 and type(body['rows']) is list
                     and len(body['rows']) <= MAX_ROWS, 'VITALS_STORE_SCHEMA')
                for row in body['rows']:
                    need(type(row) is dict and set(row) == {'uid', 'hp', 'mp'}
                         and all(type(row[k]) is int and 0 <= row[k] <= 0x7fffffff
                                 for k in ('hp', 'mp'))
                         and type(row['uid']) is int and 0 < row['uid'] <= 0xffffffff
                         and row['uid'] not in rows, 'VITALS_STORE_ROW')
                    rows[row['uid']] = (row['hp'], row['mp'])
            self._vitals = rows
        return self._vitals.get(uid)

    def save_vitals(self, uid, value):
        self.vitals(uid)
        rows = dict(self._vitals)
        rows[uid] = tuple(value)
        need(len(rows) <= MAX_ROWS, 'VITALS_STORE_UID_LIMIT')
        body = dict(version=1, rows=[dict(uid=k, hp=v[0], mp=v[1])
                                     for k, v in sorted(rows.items())])
        raw = (json.dumps(body, separators=(',', ':')) + '\n').encode('ascii')
        need(len(raw) <= MAX_BYTES, 'VITALS_STORE_SIZE')
        path = self.path.with_name('vitals.json')
        temporary = path.with_name('.vitals-' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        self._vitals = rows

    def _load(self) -> dict[int, Progress]:
        if self._rows is not None:
            return self._rows
        rows = {}
        if self.path.exists():
            raw = self.path.read_bytes()
            need(len(raw) <= MAX_BYTES, 'PROGRESS_STORE_SIZE')
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ValueError('PROGRESS_STORE_JSON') from None
            need(type(data) is dict and set(data) == {'version', 'rows'} and data['version'] == 1
                 and type(data['rows']) is list and len(data['rows']) <= MAX_ROWS,
                 'PROGRESS_STORE_SCHEMA')
            for row in data['rows']:
                need(_valid_row(row) and row['uid'] not in rows, 'PROGRESS_STORE_ROW')
                rows[row['uid']] = Progress(row['exp'], row['level'], row['max_hp'], row['max_mp'],
                                             row.get('lawful', 0))
        self._rows = rows
        return rows

    def get(self, uid: int) -> Progress:
        with _lock:
            return self._load().get(uid, Progress(0, 1))

    def stage(self, uid: int, progress: Progress) -> None:
        """Adopt a world snapshot; the bridge owns its pending durable write."""
        from dataclasses import asdict
        need(type(progress) is Progress and _valid_row(dict(uid=uid, **asdict(progress))),
             'PROGRESS_STORE_ROW')
        with _lock:
            rows = dict(self._load())
            rows[uid] = progress
            need(len(rows) <= MAX_ROWS, 'PROGRESS_STORE_UID_LIMIT')
            self._rows = rows

    def commit(self, uid: int, progress: Progress) -> None:
        """Persist first, then adopt in memory. Errors leave the old value."""
        with _lock:
            rows = dict(self._load())
            rows[uid] = progress
            need(len(rows) <= MAX_ROWS, 'PROGRESS_STORE_UID_LIMIT')
            body = dict(version=1, rows=[dict(uid=k, exp=v.exp, level=v.level, max_hp=v.max_hp, max_mp=v.max_mp,
                                             lawful=v.lawful)
                                         for k, v in sorted(rows.items())])
            raw = (json.dumps(body, separators=(',', ':')) + '\n').encode('ascii')
            need(len(raw) <= MAX_BYTES, 'PROGRESS_STORE_SIZE')
            temporary = self.path.with_name('.progression-' + uuid.uuid4().hex + '.tmp')
            try:
                with temporary.open('xb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary.exists():
                    temporary.unlink()
            self._rows = rows
