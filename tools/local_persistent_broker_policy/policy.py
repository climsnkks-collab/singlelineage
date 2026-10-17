"""Pure decisions only. Evidence objects are synthetic adapter inputs, not admission.

No imports of native/runtime modules, sockets, files, packet DTOs, or asyncio.
Root must retain and validate actual handles, tuple polls, codec and source scopes.
"""
from collections import deque
from dataclasses import dataclass, field

PORTS = (12000, 14030)
MAX_COUNTER = (1 << 64) - 1
BOOT_C2S = (0x4e34, 0x4f3d)
BOOT_S2C = (0x4e20, 0x4e35, 0x4f3e)
# Exact existing route overlays; no heartbeat, movement, combat or guessed IDs.
GAME_C2S = frozenset((0x263, 0x267, 0x4e24, 0x4e28))
GAME_S2C = frozenset((0x264, 0x4e25, 0x4e29, 0x4e21, 0x4e22,
                       0x4e95, 0x4e38, 0x4e96))


class Refused(ValueError):
    """Fixed codes only; do not interpolate evidence, DTOs or identities."""


def need(ok, code):
    if not ok:
        raise Refused(code)


@dataclass(frozen=True, slots=True)
class Peer:
    port: int
    client_port: int
    accepted_ns: int

    def validate(self):
        need(type(self.port) is int and self.port in PORTS, 'ENDPOINT_REQUIRED')
        need(type(self.client_port) is int and 0 < self.client_port <= 65535,
             'CLIENT_PORT_REQUIRED')
        need(type(self.accepted_ns) is int and 0 <= self.accepted_ns < (1 << 63), 'ACCEPT_CLOCK_REQUIRED')


@dataclass(frozen=True, slots=True)
class OwnerSample:
    """Root polls exact loopback tuple and retained handle identity/Job together.

    Booleans here model an adapter contract only. Never accept this from JSON,
    CLI, a historical receipt or a client, or treat it as native authorization.
    """
    owner: object = field(repr=False)
    handle: object = field(repr=False)
    job: object = field(repr=False)
    peer: Peer
    observed_ns: int
    exact_identity_and_tuple: bool
    alive: bool


@dataclass(slots=True)
class Bucket:
    capacity: int
    per_second: int
    now: int
    tokens: float = field(init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def take(self, amount, now):
        need(now >= self.now, 'CLOCK_REGRESSION')
        self.tokens = min(self.capacity, self.tokens + (now - self.now) / 1e9 * self.per_second)
        self.now = now
        need(amount <= self.tokens, 'RATE_BOUND')
        self.tokens -= amount


@dataclass(slots=True)
class Connection:
    writer: object = field(repr=False)
    peer: Peer
    stage: int
    rx_bytes: Bucket = field(repr=False)
    rx_frames: Bucket = field(repr=False)
    tx_bytes: Bucket = field(repr=False)
    tx_frames: Bucket = field(repr=False)
    rx_boot: int = 0
    tx_boot: int = 0
    buffered: int = 0
    partial_started_ns: int | None = None
    drain_started_ns: int | None = None
    pending_size: int = 0
    pending_opcode: int | None = None
    received: int = 0
    sent: int = 0
    eof: bool = False
    positive_close: bool = False
    registry_removed: bool = False
    task_joined: bool = False
    failed: bool = False


class PersistentPolicy:
    """One exact owned session, two source-supported sequential streams/port.

    Active second stream has no total deadline/byte/frame/idle quota. Sliding
    resource bounds are provisional product policy, not normal client pacing
    evidence. Failed connection operations require fail()/stop() in Root.
    """
    READ_SIZE = 4096
    MAX_FRAME = 65535                 # present_disabled mode only
    MAX_BUFFER = MAX_FRAME + READ_SIZE
    WRITE_HIGH = 131070               # adapter transport high watermark
    WRITE_LOW = 65535
    POLL_NS = 100_000_000             # scheduler yield / stop / owner check
    FRESH_NS = 250_000_000            # preserve existing owner freshness
    BOOT_NS = 15_000_000_000
    PARTIAL_NS = 10_000_000_000
    DRAIN_NS = 2_000_000_000
    CLOSE_NS = 2_000_000_000
    LOG_ROWS = 256
    EVENTS = frozenset(('accepted', 'rx', 'tx', 'eof', 'closed', 'failed', 'stopped', 'released'))
    STOP_REASONS = frozenset(('positive_owner_exit', 'explicit_session_exit', 'cancelled',
                              'owner_unknown', 'source_refused', 'broker_failed'))

    def __init__(self, owner, handle, job, reservations, now=0):
        need(owner is not None and handle is not None and job is not None, 'RETAINED_OWNER_REQUIRED')
        need(type(reservations) is dict and set(reservations) == set(PORTS), 'BOTH_RESERVATIONS_REQUIRED')
        need(all(s is not None for s in reservations.values()) and
             reservations[12000] is not reservations[14030], 'DISTINCT_RESERVED_SOCKETS_REQUIRED')
        need(type(now) is int and 0 <= now < (1 << 63), 'CLOCK_REQUIRED')
        self.owner, self.handle, self.job = owner, handle, job
        self.reservations = dict(reservations)
        self.now = now
        self.rows = {p: [] for p in PORTS}  # at most 2/port
        self.log = deque(maxlen=self.LOG_ROWS)
        self.events = self.dropped = 0
        self.state = 'OPEN'
        self.stop_reason = None

    def _time(self, now):
        need(type(now) is int and self.now <= now < (1 << 63), 'CLOCK_REGRESSION')
        self.now = now

    def _emit(self, event, port=0, opcode=0, size=0):
        need(event in self.EVENTS, 'LOG_EVENT_REQUIRED')
        if len(self.log) == self.LOG_ROWS:
            self.dropped = min(MAX_COUNTER, self.dropped + 1)
        self.events = min(MAX_COUNTER, self.events + 1)
        self.log.append((event, port, opcode, size))  # no bodies/refs/peer/identities

    def _open(self):
        need(self.state == 'OPEN', 'SESSION_STOPPED')

    def _connection(self, writer):
        for rows in self.rows.values():
            for row in rows:
                if row.writer is writer:
                    need(not row.positive_close and not row.failed, 'CONNECTION_CLOSED_OR_FAILED')
                    return row
        raise Refused('LITERAL_WRITER_REQUIRED')

    def _owner(self, sample, peer):
        need(type(sample) is OwnerSample and sample.owner is self.owner and
             sample.handle is self.handle and sample.job is self.job,
             'EXACT_RETAINED_OWNER_REQUIRED')
        need(sample.peer == peer and type(sample.observed_ns) is int and
             peer.accepted_ns <= sample.observed_ns <= self.now and
             self.now - sample.observed_ns <= self.FRESH_NS and
             sample.exact_identity_and_tuple is True and sample.alive is True,
             'CURRENT_OWNER_REQUIRED')

    def admit(self, writer, peer, sample, now, *, key_already_drained=False):
        self._time(now); self._open(); peer.validate(); self._owner(sample, peer)
        need(writer is not None, 'WRITER_REQUIRED')
        need(not any(r.writer is writer for rows in self.rows.values() for r in rows), 'WRITER_REUSE_REFUSED')
        rows = self.rows[peer.port]
        need(len(rows) < 2, 'APPLICATION_RECONNECT_UNBOUND')
        if rows:
            previous = rows[-1]
            need(previous.positive_close and previous.registry_removed and previous.task_joined and
                 previous.eof and not previous.failed and previous.rx_boot == 2 and previous.tx_boot == 3,
                 'BOOTSTRAP_PREDECESSOR_NOT_COMPLETE_CLOSED')
            need(previous.peer.client_port != peer.client_port, 'ACCEPTED_TUPLE_REUSED')
        row = Connection(writer, peer, len(rows), Bucket(131070, 65536, now),
                         Bucket(128, 64, now), Bucket(131070, 65536, now), Bucket(128, 64, now))
        need(type(key_already_drained) is bool, 'KEY_ADOPTION_BOOL_REQUIRED')
        if key_already_drained:
            # Root preserves source-scoped immediate KEY before any owner wait.
            # Adoption requires actual first KEY12 write/drain in that same writer.
            row.tx_boot, row.sent = 1, 1
        rows.append(row); self._emit('accepted', peer.port)
        return row

    def checkpoint(self, writer, sample, now):
        self._time(now); self._open()
        row = self._connection(writer); self._owner(sample, row.peer)
        need(not row.eof, 'EOF_ALREADY_SEEN')
        if row.rx_boot < 2 or row.tx_boot < 3:
            need(now - row.peer.accepted_ns < self.BOOT_NS, 'BOOTSTRAP_TIMEOUT')
        if row.partial_started_ns is not None:
            need(now - row.partial_started_ns < self.PARTIAL_NS, 'PARTIAL_FRAME_TIMEOUT')
        if row.drain_started_ns is not None:
            need(now - row.drain_started_ns < self.DRAIN_NS, 'DRAIN_TIMEOUT')
        return row

    def received_chunk(self, writer, sample, size, buffered_after, now, *, decoded_frames=0):
        row = self.checkpoint(writer, sample, now)
        need(row.drain_started_ns is None, 'READ_PAUSED_UNTIL_DRAIN')
        need(type(size) is int and 0 < size <= self.READ_SIZE, 'READ_CHUNK_BOUND')
        need(type(buffered_after) is int and 0 <= buffered_after <= self.MAX_BUFFER, 'DECODER_BUFFER_BOUND')
        need(type(decoded_frames) is int and 0 <= decoded_frames <= 410, 'DECODED_CHUNK_FRAME_BOUND')
        row.rx_bytes.take(size, now)
        row.buffered = buffered_after
        if buffered_after and (row.partial_started_ns is None or decoded_frames):
            row.partial_started_ns = now
        elif not buffered_after:
            row.partial_started_ns = None

    def received_frame(self, writer, sample, opcode, size, now):
        row = self.checkpoint(writer, sample, now)
        need(row.drain_started_ns is None, 'DISPATCH_PAUSED_UNTIL_DRAIN')
        need(type(opcode) is int and type(size) is int and 10 <= size <= self.MAX_FRAME, 'CLIENT_FRAME_BOUND')
        if row.rx_boot < 2:
            need(opcode == BOOT_C2S[row.rx_boot], 'BOOTSTRAP_REQUEST_SEQUENCE')
            need(row.tx_boot == row.rx_boot + 1, 'BOOTSTRAP_REPLY_NOT_DRAINED')
        else:
            need(row.stage == 1 and row.tx_boot == 3 and opcode in GAME_C2S, 'GAME_OPCODE_UNBOUND')
        row.rx_frames.take(1, now)
        if row.rx_boot < 2:
            row.rx_boot += 1
        row.received = min(MAX_COUNTER, row.received + 1)
        self._emit('rx', row.peer.port, opcode, size)

    def begin_write(self, writer, sample, opcode, size, queued_bytes, now):
        row = self.checkpoint(writer, sample, now)
        need(row.drain_started_ns is None, 'ONE_WRITE_DRAIN_REQUIRED')
        need(type(size) is int and 6 <= size <= self.MAX_FRAME and type(opcode) is int, 'SERVER_FRAME_BOUND')
        need(type(queued_bytes) is int and 0 <= queued_bytes and
             queued_bytes + size <= self.WRITE_HIGH, 'TRANSPORT_BACKPRESSURE_BOUND')
        if row.tx_boot < 3:
            need(opcode == BOOT_S2C[row.tx_boot] and row.rx_boot == row.tx_boot, 'BOOTSTRAP_REPLY_SEQUENCE')
        else:
            need(row.stage == 1 and opcode in GAME_S2C, 'SERVER_OPCODE_UNBOUND')
        row.tx_frames.take(1, now); row.tx_bytes.take(size, now)
        row.drain_started_ns, row.pending_size, row.pending_opcode = now, size, opcode

    def drained(self, writer, sample, queued_bytes, now):
        row = self.checkpoint(writer, sample, now)
        need(row.drain_started_ns is not None and type(queued_bytes) is int and
             0 <= queued_bytes <= self.WRITE_LOW, 'POSITIVE_DRAIN_REQUIRED')
        if row.tx_boot < 3:
            row.tx_boot += 1
        self._emit('tx', row.peer.port, row.pending_opcode, row.pending_size)
        row.sent = min(MAX_COUNTER, row.sent + 1)
        row.drain_started_ns = row.pending_opcode = None
        row.pending_size = 0

    def eof(self, writer, sample, decoder_empty, now):
        row = self.checkpoint(writer, sample, now)
        need(decoder_empty is True and row.buffered == 0 and row.drain_started_ns is None, 'COMPLETE_EOF_REQUIRED')
        row.eof = True; self._emit('eof', row.peer.port)

    def fail(self, writer):
        row = self._connection(writer)
        row.failed = True; self._emit('failed', row.peer.port)
        self.stop('broker_failed')

    def stop(self, reason, *, owner=None, handle=None, positive_exit=False):
        need(reason in self.STOP_REASONS, 'STOP_REASON_REQUIRED')
        if reason == 'positive_owner_exit':
            need(owner is self.owner and handle is self.handle and positive_exit is True,
                 'POSITIVE_EXACT_OWNER_EXIT_REQUIRED')
        if self.state == 'OPEN':
            self.state, self.stop_reason = 'CLOSING', reason
            self._emit('stopped')
        return ('stop_accepts', 'cancel_read_dispatch_tasks', 'remove_literal_registry_writers',
                'wipe_decoder_and_reply_buffers', 'close_writers', 'wait_positive_writer_close',
                'join_connection_tasks', 'close_listeners_and_reserved_sockets')

    def closed(self, writer, *, positive_close, registry_removed, decoder_empty, task_joined):
        # Can be called after stop/fail; retain failures for audit and block promotion.
        row = next((r for rows in self.rows.values() for r in rows if r.writer is writer), None)
        need(row is not None, 'LITERAL_WRITER_REQUIRED')
        need(positive_close is True and registry_removed is True and decoder_empty is True and task_joined is True,
             'POSITIVE_CONNECTION_CLEANUP_REQUIRED')
        need(not row.positive_close, 'CONNECTION_ALREADY_CLOSED')
        row.positive_close = row.registry_removed = row.task_joined = True
        row.buffered = row.pending_size = 0
        row.drain_started_ns = row.partial_started_ns = row.pending_opcode = None
        self._emit('closed', row.peer.port)

    def release(self, reservations, *, listeners_closed, tasks_joined):
        need(self.state == 'CLOSING', 'STOP_BEFORE_RELEASE_REQUIRED')
        need(type(reservations) is dict and set(reservations) == set(PORTS) and
             all(reservations[p] is self.reservations[p] for p in PORTS), 'SAME_RESERVATIONS_REQUIRED')
        need(listeners_closed is True and tasks_joined is True and
             all(r.positive_close and r.registry_removed and r.task_joined
                 for rows in self.rows.values() for r in rows), 'POSITIVE_BROKER_CLEANUP_REQUIRED')
        self.rows = {p: [] for p in PORTS}
        self.reservations.clear()
        self.owner = self.handle = self.job = None
        self.state = 'CLOSED'; self._emit('released')
