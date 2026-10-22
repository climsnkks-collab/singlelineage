"""Private local-server candidate. No original packet numbers or units invented.

All rules below are explicit local policy, not official-server reconstruction.
No runtime game host, process, socket, UI or client-memory access is provided.
The integration owner must hold the selected broker-row lock, establish current
character authority, and join HP/MP with its single authoritative player store. This candidate has no
HP/MP state of its own and refuses casts without a coordinated durable adapter.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import inspect
import os
from pathlib import Path
import threading
import stat
import uuid

POLICY = 'LOCAL_SKILL_SELF_BUFF_V1_WALL_MILLISECONDS'
MAX_TIME = (1 << 53) - 1
MAX_BYTES = 65536
_LOCK = threading.RLock()


def need(value, code):
    if not value:
        raise ValueError(code)


def integer(value, low=0, high=MAX_TIME):
    return type(value) is int and low <= value <= high


@dataclass(frozen=True)
class Rule:
    """Explicit opt-in recipe; no inference from neighboring original IDs.

    Eligibility is an external authoritative learn grant, not a client boolean.
    Only self buffs are supported. Bonus labels are descriptive and are never
    silently applied as AC/damage/stat formulae.
    """
    spell_id: int
    mp_cost: int
    hp_cost: int
    cooldown_ms: int
    duration_ms: int
    group: int

    def __post_init__(self):
        need(integer(self.spell_id, 0, 0x7fffffff)
             and all(integer(x, 0, 0x7fffffff) for x in
                     (self.mp_cost, self.hp_cost, self.cooldown_ms,
                      self.duration_ms, self.group))
             and self.duration_ms > 0, 'SKILL_RULE_INVALID')


def _unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'SKILL_STORE_DUPLICATE_KEY')
        result[key] = value
    return result


class Store:
    """Exclusive candidate sidecar, at most three character records.

    Atomic replace precedes a successful semantic result. A failed save poisons
    this instance because replace/fsync failure can be ambiguous. It never
    rewrites the character, position, inventory or equipment files. One Store
    instance must be shared by all server sessions; same-process stale instances refuse;
    no multi-process writer.
    Wall-clock rollback is refused, expiry continues while disconnected.
    """
    def __init__(self, path, *, account, rules, policy):
        need(policy == POLICY, 'SKILL_EXPLICIT_POLICY_REQUIRED')
        need(type(account) is str and str(uuid.UUID(account)) == account,
             'SKILL_ACCOUNT_INVALID')
        self.path = Path(path)
        need(self.path.is_absolute() and self.path.name == 'skills-v1.json'
             and self.path.parent.is_dir() and not self.path.is_symlink(),
             'SKILL_SEPARATE_PATH_REQUIRED')
        need(type(rules) is tuple and 0 < len(rules) <= 128
             and all(type(r) is Rule for r in rules), 'SKILL_RULES_REQUIRED')
        self.rules = {r.spell_id: r for r in rules}
        need(len(self.rules) == len(rules), 'SKILL_DUPLICATE_RULE')
        self.account = account
        self.rule_hash = hashlib.sha256(json.dumps(
            [asdict(self.rules[k]) for k in sorted(self.rules)],
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.lock = _LOCK
        self._bound_path = self.path
        self.failed = False
        with self.lock:
            self.data = self._load()

    def _validate(self, data):
        need(type(data) is dict and set(data) == {'schema', 'policy', 'account', 'rules', 'characters'}
             and data['schema'] == 1 and type(data['schema']) is int
             and data['policy'] == POLICY and data['account'] == self.account
             and data['rules'] == self.rule_hash, 'SKILL_STORE_BINDING')
        rows = data['characters']
        need(type(rows) is dict and len(rows) <= 3, 'SKILL_STORE_CHARACTERS')
        for uid, row in rows.items():
            need(type(uid) is str and uid.isascii() and uid.isdecimal()
                 and str(int(uid)) == uid and integer(int(uid), 1, 0xffffffff),
                 'SKILL_STORE_UID')
            need(type(row) is dict and set(row) ==
                 {'learned', 'cooldowns', 'buffs', 'revision', 'clock'},
                 'SKILL_STORE_ROW')
            need(integer(row['revision']) and integer(row['clock']), 'SKILL_STORE_SCALARS')
            learned = row['learned']
            need(type(learned) is list and all(integer(k, 0, 0x7fffffff) and k in self.rules for k in learned)
                 and learned == sorted(set(learned)), 'SKILL_STORE_LEARNED')
            for kind in ('cooldowns', 'buffs'):
                entries = row[kind]
                need(type(entries) is dict and len(entries) <= 128, 'SKILL_STORE_ENTRIES')
                for key, value in entries.items():
                    need(type(key) is str and key.isascii() and key.isdecimal()
                         and str(int(key)) == key and integer(value, 1), 'SKILL_STORE_EXPIRY')
                    if kind == 'buffs':
                        need(int(key) in learned, 'SKILL_STORE_BUFF_NOT_LEARNED')
                    else:
                        need(int(key) in {self.rules[k].group for k in learned},
                             'SKILL_STORE_COOLDOWN_GROUP')
        return data

    def _path_check(self):
        need(self.path == self._bound_path and self.path.parent.is_dir(),
             'SKILL_PATH_BINDING_CHANGED')
        for part in (self.path, *self.path.parents):
            if not os.path.lexists(part):
                continue
            info = part.lstat()
            need(not stat.S_ISLNK(info.st_mode)
                 and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'SKILL_REPARSE_REFUSED')
            if part == self.path:
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                     'SKILL_REGULAR_SINGLE_FILE_REQUIRED')

    def _current(self):
        need(self._load() == self.data, 'SKILL_STORE_STALE_INSTANCE')

    def _load(self):
        self._path_check()
        if not self.path.exists():
            return dict(schema=1, policy=POLICY, account=self.account,
                        rules=self.rule_hash, characters={})
        with self.path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        need(len(raw) <= MAX_BYTES, 'SKILL_STORE_SIZE')
        return self._validate(json.loads(raw, object_pairs_hook=_unique))

    def _save(self, data):
        self._current()
        self._validate(data)
        raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode()
        need(len(raw) <= MAX_BYTES, 'SKILL_STORE_SIZE')
        temp = self.path.with_name('.skills-' + uuid.uuid4().hex + '.tmp')
        try:
            self._path_check()
            with temp.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        except BaseException:
            self.failed = True
            raise
        finally:
            temp.unlink(missing_ok=True)
        self.data = data

    def create(self, uid, *, now_ms):
        """Integration-only fresh-character grant; existing UID cannot refill."""
        with self.lock:
            self._ready(uid, now_ms)
            need(str(uid) not in self.data['characters'], 'SKILL_CHARACTER_EXISTS')
            data = deepcopy(self.data)
            data['characters'][str(uid)] = dict(learned=[],
                cooldowns={}, buffs={}, revision=0, clock=now_ms)
            self._save(data)

    def _ready(self, uid, now):
        need(not self.failed, 'SKILL_STORE_POISONED')
        self._current()
        need(integer(uid, 1, 0xffffffff) and integer(now), 'SKILL_CONTEXT_INVALID')

    def apply(self, uid, *, now_ms, command, spell_id=None, target_uid=None,
              expected_revision, learn_grant=False, resources=None):
        """Semantic server operation, called only after broker authority check.

        Revisions serialize stale input. Denial mutates nothing. Expiry events
        are committed with success. Failure to deliver an accepted result must
        poison that network session; a new session restores authoritative state.
        """
        with self.lock:
            self._ready(uid, now_ms)
            original = self.data['characters'].get(str(uid))
            need(original is not None, 'SKILL_CHARACTER_UNKNOWN')
            need(integer(expected_revision) and expected_revision == original['revision'],
                 'SKILL_REVISION_CHANGED')
            need(now_ms >= original['clock'], 'SKILL_CLOCK_ROLLBACK')
            need(command in ('learn', 'cast', 'remove', 'restore', 'tick', 'close'), 'SKILL_COMMAND')
            data = deepcopy(self.data)
            row = data['characters'][str(uid)]
            events = []
            for key, expiry in tuple(row['buffs'].items()):
                if expiry <= now_ms:
                    del row['buffs'][key]
                    events.append(dict(kind='buff_remove', spell_id=int(key), reason='expired'))
            row['cooldowns'] = {k: v for k, v in row['cooldowns'].items() if v > now_ms}
            if command in ('learn', 'cast', 'remove'):
                need(integer(spell_id, 0, 0x7fffffff) and spell_id in self.rules, 'SKILL_UNKNOWN')
                rule = self.rules[spell_id]
                key = str(spell_id)
                if command == 'learn':
                    need(learn_grant is True, 'SKILL_LEARN_GRANT_REQUIRED')
                    need(spell_id not in row['learned'], 'SKILL_ALREADY_LEARNED')
                    row['learned'] = sorted(row['learned'] + [spell_id])
                    events.append(dict(kind='learned', spell_id=spell_id))
                else:
                    need(spell_id in row['learned'], 'SKILL_NOT_LEARNED')
                    if command == 'cast':
                        need(integer(target_uid, 1, 0xffffffff) and target_uid == uid,
                             'SKILL_SELF_TARGET_REQUIRED')
                        need(type(resources) is dict and set(resources) == {'hp', 'mp'}
                             and all(integer(v, 0, 0x7fffffff) for v in resources.values()),
                             'SKILL_SHARED_RESOURCES_REQUIRED')
                        need(resources['hp'] > rule.hp_cost, 'SKILL_HP_OR_DEAD')
                        need(resources['mp'] >= rule.mp_cost, 'SKILL_MP_INSUFFICIENT')
                        need(getattr(self, '_prepared_only', False),
                             'SKILL_ATOMIC_RESOURCE_COMMIT_REQUIRED')
                        need(str(rule.group) not in row['cooldowns'], 'SKILL_COOLDOWN')
                        need(now_ms + max(rule.duration_ms, rule.cooldown_ms) <= MAX_TIME,
                             'SKILL_TIME_OVERFLOW')
                        if rule.cooldown_ms:
                            row['cooldowns'][str(rule.group)] = now_ms + rule.cooldown_ms
                        kind = 'buff_refresh' if key in row['buffs'] else 'buff_add'
                        row['buffs'][key] = now_ms + rule.duration_ms
                        events.extend((dict(kind='resource_debit', hp=rule.hp_cost, mp=rule.mp_cost),
                            dict(kind=kind, spell_id=spell_id, expires_ms=row['buffs'][key])))
                    else:
                        need(key in row['buffs'], 'SKILL_BUFF_ABSENT')
                        del row['buffs'][key]
                        events.append(dict(kind='buff_remove', spell_id=spell_id, reason='explicit'))
            if command == 'restore':
                events.append(dict(kind='snapshot', learned=tuple(row['learned']), buffs=deepcopy(row['buffs']),
                    cooldowns=deepcopy(row['cooldowns'])))
            need(row['revision'] < MAX_TIME, 'SKILL_REVISION_OVERFLOW')
            row['revision'] += 1
            row['clock'] = now_ms
            self._save(data)
            return dict(revision=row['revision'], events=tuple(events))


class Session:
    """Async broker lifetime adapter; caller holds its operation_lock.

    No opcode is handled here until a reviewed codec is injected. authorize,
    encode, resources, commit and abort are synchronous precommit operations;
    deliver is async and must finish the broker's real write/drain. Resource
    reservations are always released on precommit failure. Ambiguous commit (whose reservation must be resolved by the adapter) or
    delivery failure poisons this session and store; reconnect must reload disk.
    """
    def __init__(self, store, uid, *, authorize, encode, deliver,
                 resources=None, commit=None, abort=None):
        need(type(store) is Store and callable(authorize), 'SKILL_SESSION_DEPENDENCIES')
        need(callable(encode), 'SKILL_ORIGINAL_WIRE_CONTRACT_REQUIRED')
        need(inspect.iscoroutinefunction(deliver), 'SKILL_ASYNC_DRAIN_REQUIRED')
        need(integer(uid, 1, 0xffffffff), 'SKILL_CONTEXT_INVALID')
        self.store, self.uid = store, uid
        self.authorize, self.encode, self.deliver = authorize, encode, deliver
        self.resources, self.commit, self.abort = resources, commit, abort
        self.closed = self.busy = False

    @staticmethod
    def _sync(callback, *args):
        result = callback(*args)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            raise ValueError('SKILL_PRECOMMIT_MUST_BE_SYNCHRONOUS')
        return result

    async def dispatch(self, **operation):
        need(not self.closed and not self.busy, 'SKILL_SESSION_CLOSED_OR_BUSY')
        self.busy = True
        reserved = committed = commit_started = False
        reservation = None
        try:
            # No await through prepare/commit: the broker's operation_lock is
            # also mandatory for shared owner/resource/selection serialization.
            with self.store.lock:
                need(self._sync(self.authorize, self.uid) is True,
                     'SKILL_CURRENT_OWNER_REQUIRED')
                shadow = object.__new__(Store)
                shadow.__dict__ = dict(self.store.__dict__)
                shadow.data = deepcopy(self.store.data)
                shadow._prepared_only = True
                shadow._current = lambda: None
                shadow._save = lambda data: setattr(shadow, 'data', shadow._validate(data))
                operation = dict(operation)
                need('resources' not in operation, 'SKILL_CLIENT_RESOURCE_OVERRIDE')
                is_cast = operation.get('command') == 'cast'
                if is_cast:
                    need(callable(self.resources) and callable(self.commit) and callable(self.abort),
                         'SKILL_ATOMIC_RESOURCE_ADAPTER_REQUIRED')
                    reservation, snapshot = self._sync(self.resources, self.uid)
                    reserved = True
                    operation['resources'] = snapshot
                result = shadow.apply(self.uid, **operation)
                frames = self._sync(self.encode, deepcopy(result))
                need(type(frames) is tuple and len(frames) <= 256
                     and all(type(frame) is bytes and 0 < len(frame) <= 65535 for frame in frames),
                     'SKILL_ENCODE_BATCH_INVALID')
                need(not result['events'] or bool(frames), 'SKILL_EVENTS_NOT_ENCODED')
                need(self._sync(self.authorize, self.uid) is True,
                     'SKILL_CURRENT_OWNER_CHANGED')
                self.store._current()
                commit_started = True
                if is_cast:
                    # MUST atomically persist shared resource debit and this
                    # next skill document, compare reservation/revision and
                    # finalize reservation. No default transaction is invented.
                    need(self._sync(self.commit, self.uid, reservation,
                                    deepcopy(shadow.data), deepcopy(result)) is True,
                         'SKILL_ATOMIC_RESOURCE_COMMIT_NOT_CONFIRMED')
                    committed = True
                    need(self.store._load() == shadow.data, 'SKILL_COMMITTED_DOCUMENT_MISMATCH')
                    self.store.data = shadow.data
                else:
                    self.store._save(shadow.data)
                    committed = True
            await self.deliver(frames)
            if operation.get('command') == 'close':
                self.closed = True
            return result
        except BaseException:
            if commit_started:
                self.closed = self.store.failed = True
            raise
        finally:
            if reserved and not commit_started:
                try:
                    self._sync(self.abort, self.uid, reservation)
                except BaseException:
                    self.closed = self.store.failed = True
                    raise
            self.busy = False

    def abandon(self):
        """Disconnect cleanup; never retry an uncertain network delivery."""
        self.closed = True
