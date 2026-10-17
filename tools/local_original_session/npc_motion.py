"""One explicit local Monster step. No timer, autonomous AI or client prediction.

SC4E2C carries UID/reported grid/direction only. Original server field2 policy
remains unknown. The explicitly selected L1J reference policy reports the start
grid; its old wire format is not reused. Cadence and goals are local policy too.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
from pathlib import Path
import struct

from tools.local_original_session import movement, npc

OPCODE = 0x4e2c
ROOT = Path(__file__).resolve().parents[2]
LOCAL_PRE_STEP = 'EXPLICIT_LOCAL_L1J_PRE_STEP_GRID'
REMOTE_CONTRACT_PATH = ROOT / 'work/local_server_rea_20261016/run23_npc_move/source-evidence.json'
REMOTE_CONTRACT_SHA = '19a82a2012d0cc13d320fa244d0e74145dfa2f262d9132f307437a6054a67ab5'
REFERENCE_ROOT = ROOT / 'work/local_original_session/integration-1/npc-motion-reference'
REFERENCE_PINS = {
    'L1NpcInstance.java': '02191de10fab9fa43f6d1198fc4b06bf9ffc247da608488d76a4203abb5d24e3',
    'S_MoveCharPacket.java': '2a774173fa323ceff4ad93f2dd0210ce2a3c0cc6c2138f37f1c32d871a0c9602',
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def source_ready(policy):
    need(policy == LOCAL_PRE_STEP, 'NPC_MOVE_ORIGINAL_SERVER_POLICY_UNKNOWN')
    need(REMOTE_CONTRACT_PATH is not None and REMOTE_CONTRACT_SHA is not None,
         'NPC_MOVE_FIELD2_SOURCE_UNKNOWN_UNSAFE_NOT_SENT')
    need(hashlib.sha256(REMOTE_CONTRACT_PATH.read_bytes()).hexdigest() == REMOTE_CONTRACT_SHA,
         'NPC_MOVE_SOURCE_CHANGED')
    for name, digest in REFERENCE_PINS.items():
        need(hashlib.sha256((REFERENCE_ROOT / name).read_bytes()).hexdigest() == digest,
             'NPC_MOVE_REFERENCE_CHANGED')


def _frame(uid, reported_grid, direction):
    pb = movement.pb
    body = pb.encode_message([pb.encode_uint32(1, uid), pb.encode_uint32(2, reported_grid),
                              pb.encode_uint32(3, direction)])
    return struct.pack('<HH', len(body) + 6, OPCODE) + body + b'\0\0'


@dataclass(frozen=True, slots=True)
class State:
    uid: int
    map_id: int
    packed: int
    direction: int
    goal: tuple | None = None
    last_step_ns: int | None = None


@dataclass(frozen=True, slots=True)
class Step:
    before: State
    after: State
    reported_grid: int
    frame: bytes = field(repr=False)


class NpcMotion:
    def __init__(self, spawn, *, self_uid, interval_ns, policy):
        need(type(spawn) is npc.NpcSpawn and spawn.uid != self_uid,
             'NPC_MOVE_REMOTE_SPAWN_REQUIRED')
        need(type(interval_ns) is int and 0 < interval_ns < (1 << 63),
             'NPC_MOVE_EXPLICIT_LOCAL_INTERVAL_REQUIRED')
        self.interval_ns = interval_ns
        need(policy == LOCAL_PRE_STEP, 'NPC_MOVE_ORIGINAL_SERVER_POLICY_UNKNOWN')
        self.policy = policy
        self.state = State(spawn.uid, spawn.map_id, spawn.fields[1], spawn.fields[5])
        self.pending = None
        self.spawn_drained = False
        self.fatal = self.closed = False

    def plan(self, *, goal, direction, now_ns):
        """Explicit local pre-step grid proposal; no AI direction/timing default."""
        need(not self.closed and not self.fatal and self.pending is None,
             'NPC_MOVE_LIFETIME_OR_PENDING')
        need(type(goal) is tuple and len(goal) == 2, 'NPC_MOVE_EXPLICIT_GOAL_REQUIRED')
        movement.authority.pack_grid(*goal)
        need(type(direction) is int and 0 <= direction <= 7, 'NPC_MOVE_DIRECTION_REQUIRED')
        need(type(now_ns) is int and 0 <= now_ns < (1 << 63), 'NPC_MOVE_LOCAL_CLOCK_REQUIRED')
        if self.state.last_step_ns is not None:
            need(now_ns >= self.state.last_step_ns + self.interval_ns, 'NPC_MOVE_LOCAL_CADENCE')
        start = movement.authority.unpack_grid(self.state.packed)
        delta = movement.authority.DELTAS[direction]
        destination = tuple(a + d for a, d in zip(start, delta))
        packed = movement.authority.pack_grid(*destination)
        # Explicit local goal policy; direction selection/pathfinding is external.
        distance = lambda value: max(abs(a - b) for a, b in zip(value, goal))
        need(distance(destination) < distance(start), 'NPC_MOVE_STEP_MUST_APPROACH_GOAL')
        after = replace(self.state, packed=packed, direction=direction,
                        goal=goal, last_step_ns=now_ns)
        # L1J fixed-commit constructor subtracts heading delta from updated XY.
        # This backend reference chooses pre-step grid; original policy is unknown.
        reported_grid = self.state.packed
        wire = _frame(self.state.uid, reported_grid, direction)
        return Step(self.state, after, reported_grid, wire)

    def begin(self, step):
        source_ready(self.policy)
        need(self.spawn_drained and not self.closed and not self.fatal
             and self.pending is None and type(step) is Step and step.before is self.state,
             'NPC_MOVE_CURRENT_DRAINED_SPAWN_REQUIRED')
        need(step.reported_grid == self.state.packed
             and (step.after.uid, step.after.map_id) == (self.state.uid, self.state.map_id)
             and step.frame == _frame(self.state.uid, self.state.packed, step.after.direction),
             'NPC_MOVE_EXACT_LOCAL_PRE_STEP_REQUIRED')
        self.pending = step

    def validate_frame(self, wire):
        source_ready(self.policy)
        need(not self.closed and not self.fatal and self.spawn_drained
             and self.pending is not None and self.pending.before is self.state
             and wire == self.pending.frame, 'NPC_MOVE_EXACT_PENDING_FRAME_REQUIRED')

    def commit(self, step):
        need(not self.closed and not self.fatal and self.pending is step
             and step.before is self.state, 'NPC_MOVE_COMMIT_ONCE_REQUIRED')
        self.state, self.pending = step.after, None

    def fail(self):
        # A write/drain may already have reached the client. Never retry it.
        self.fatal, self.pending = True, None

    def close(self):
        self.closed, self.pending = True, None
