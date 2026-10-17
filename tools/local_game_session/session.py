"""Request-driven owned game dispatch. No listener, vendor auth or guessed replies."""
from __future__ import annotations
import hashlib, importlib.util, struct, sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

def load(relative, digest, alias):
    path = ROOT / relative
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('GAME_CODEC_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module

wire = load('tools/local_character_wire_v2/wire.py', '466d3db45f1765f2cb3ce3e5a25917615ebd07326c428f29b66b80512d372cfc', '_game_character_wire')
world = load('tools/local_world_protocol/model.py', '2d1ebdec0c3fc7830702691d045d89c6dacfdbf706cbf5eb9670be20e3cd5f07', '_game_world_wire')
pb = wire.pb

class Refused(ValueError):
    """Constant codes only; request/DTO values never enter diagnostics."""

def need(ok, code):
    if not ok:
        raise Refused(code)

def i32(value):
    if value <= 0x7fffffff:
        return value
    if 0xffffffff80000000 <= value <= 0xffffffffffffffff:
        return value - (1 << 64)
    raise Refused('SELECT_SIGNED32_REQUIRED')

@dataclass(frozen=True, slots=True)
class Selection:
    reference: str = field(repr=False)
    field2: int = field(repr=False)
    field3: int = field(repr=False)

def selection_request(payload):
    """937B4D/937EEF/937F00 -> 937FA3 opcode4E28; no coordinate labels."""
    with pb.parse_message(payload, schema={1: 2, 2: 0, 3: 0},
                          limits=pb.WireLimits(max_body=512, max_fields=3, max_field_bytes=128)) as parsed:
        need(all(len(parsed.occurrences(n)) == 1 for n in (1, 2, 3)), 'SELECT_REQUIRED_UNIQUE_FIELDS')
        try:
            reference = bytes(parsed.occurrences(1)[0].value).decode('utf-8', 'strict')
        except UnicodeError:
            raise Refused('SELECT_UTF8_REQUIRED') from None
        need(bool(reference) and not any(ord(c) < 32 for c in reference), 'SELECT_REFERENCE_REQUIRED')
        return Selection(reference, i32(parsed.occurrences(2)[0].value), i32(parsed.occurrences(3)[0].value))

@dataclass(frozen=True, slots=True)
class Roster:
    frames: tuple = field(repr=False)
    references: frozenset = field(repr=False)

def prepare_roster(config):
    """Use the existing complete NUM/INFO encoder; never default INFO4/21."""
    keys = {'schema', 'realm', 'source_provenance', 'expected_count', 'display_slots',
            'rows', 'existing_rows', 'mode', 'allow_expected_growth'}
    need(type(config) is dict and set(config) == keys, 'EXPLICIT_ROSTER_REQUIRED')
    need(config['schema'] == 'lc-owned-local-core-roster-v1' and config['realm'] == 'owned-local'
         and config['source_provenance'] == 'explicit_local_game_configuration', 'OWNED_LOCAL_ROSTER_REQUIRED')
    need(config['mode'] == 'initial' and config['existing_rows'] == []
         and config['allow_expected_growth'] is False, 'INITIAL_ROSTER_ONLY')
    need(type(config['rows']) is list, 'ROSTER_ROWS_REQUIRED')
    rows = []
    for row in config['rows']:
        need(type(row) is dict and all(type(k) is str and k.isdecimal() and str(int(k)) == k for k in row), 'ROSTER_FIELD_NUMBERS')
        rows.append({int(k): v for k, v in row.items()})
    result = wire.build_local_roster(expected_count=config['expected_count'],
                                    display_slots=config['display_slots'], rows=rows,
                                    mode='initial', allow_expected_growth=False)
    return Roster(result.frames, frozenset(row[1] for row in rows))

class Registry:
    """Server-local registration capability; no client-supplied session ID/token."""
    def __init__(self):
        self._sessions = {}
        self.selected = {}

    def register_own(self, connection, roster_config, *, on_selection=None):
        need(connection is not None and id(connection) not in self._sessions, 'OWN_CONNECTION_ALREADY_REGISTERED')
        need(len(self._sessions) < 128, 'OWN_SESSION_LIMIT')
        need(on_selection is None or callable(on_selection), 'SELECTION_HANDLER_REQUIRED')
        session = GameSession(self, connection, prepare_roster(roster_config), on_selection)
        self._sessions[id(connection)] = session
        return session

    def resolve(self, connection):
        session = self._sessions.get(id(connection))
        need(session is not None and session.connection is connection and not session.closed, 'REGISTERED_OWN_SESSION_REQUIRED')
        return session

    def close(self, connection):
        session = self._sessions.pop(id(connection), None)
        if session is not None and session.connection is connection:
            session.closed = True

    def select(self, session, selected):
        need(self.resolve(session.connection) is session, 'REGISTERED_OWN_SESSION_REQUIRED')
        # Owned realm state survives the transport close; no vendor token or
        # connection-ID reuse is used as a character identity.
        self.selected[selected.reference] = selected

class GameSession:
    """Actual request dispatcher. Binding/ownership belongs to the Root broker."""
    def __init__(self, registry, connection, roster, on_selection):
        self.registry, self.connection, self.roster = registry, connection, roster
        self.on_selection = on_selection
        self.closed = False
        self.list_sent = False
        self.selection = None
        self.routes = {0x4e28: self._select}

    def opened(self):
        self.registry.resolve(self.connection)
        return ()  # Never unsolicited NUM/INFO/ACK/world.

    def list_request(self, *, source_kind, payload):
        """Typed request hook for a Source-resolved client dispatcher.

        Numeric opcodes of these two classes are still null in the frozen
        contract, so received() deliberately does not guess their wire IDs.
        """
        self.registry.resolve(self.connection)
        need(not self.list_sent and self.selection is None, 'LIST_ORDER_OR_REPLAY')
        if source_kind == 'CS_CHARACTER_LIST_REQ':
            with pb.parse_message(payload, schema={1: 0}, limits=pb.WireLimits(max_body=32, max_fields=1)) as parsed:
                rows = parsed.occurrences(1)
                need(len(rows) == 1 and rows[0].value in (0, 1), 'LIST_CANONICAL_BOOL')
        elif source_kind == 'CS_CHAR_LIST_ENTER_REQ':
            need(len(payload) == 0, 'LIST_ENTER_EMPTY_SCHEMA')
        else:
            raise Refused('LIST_REQUEST_SOURCE_UNBOUND')
        self.list_sent = True
        return self.roster.frames

    async def received(self, frame):
        self.registry.resolve(self.connection)
        handler = self.routes.get(frame.opcode)
        need(handler is not None, 'GAME_REQUEST_OPCODE_UNBOUND')
        return await handler(frame.payload)

    async def _select(self, payload):
        need(self.list_sent and self.selection is None, 'SELECT_ORDER_OR_REPLAY')
        selected = selection_request(payload)
        need(selected.reference in self.roster.references, 'SELECT_NOT_OWNED_REFERENCE')
        # The real callback runs on the real request. It must either raise or
        # complete its local selection work. Wire success values are not guessed.
        import inspect
        if self.on_selection is not None:
            result = self.on_selection(selected)
            if inspect.isawaitable(result):
                result = await result
            need(result is None, 'WORLD_REPLY_SOURCE_UNBOUND')
        self.registry.select(self, selected)
        self.selection = selected
        return ()

class Conversation:
    """Broker hook: retain existing bootstrap and dispatch subsequent requests."""
    def __init__(self, bootstrap, game, *, bootstrap_complete):
        need(callable(bootstrap_complete), 'BOOTSTRAP_STAGE_CHECK_REQUIRED')
        self.bootstrap, self.game, self.bootstrap_complete = bootstrap, game, bootstrap_complete

    async def opened(self):
        return await self.bootstrap.opened()

    async def received(self, frame):
        if not self.bootstrap_complete(self.bootstrap):
            return await self.bootstrap.received(frame)
        return await self.game.received(frame)
