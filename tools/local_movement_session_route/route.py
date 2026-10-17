"""In-memory, serialized one-self-step route; no transport or live verifier.

World and passability DTOs are assertions from independently reviewed owner
verifiers. Identity capabilities correlate them; constructing these DTOs is not
verification. CP59 history and CP62 tile-only JSON cannot mint live evidence.
"""
from dataclasses import dataclass, field
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
CONTROL = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
PINS = {
    'work/local_movement_contract/contract.json': 'ce703ec05387ac8998ac98199ad9938b4e78a87f0e643205c0119cc65fccb51c',
    'work/local_move_action_followup/contract.json': '6f638f78f0ef9b339dd194e08696929155ff1f0eaa9d9338af5a912a610dfd47',
    'tools/local_movement_authority/model.py': '1e4937efc2cda1fd86b0feb5d5e7958631924e9a9f39517e8d88854c74151a77',
    'tools/local_entry_server/codecs.py': '4a43bf7b178281d5c3d44cdcc8a114349103697a09b2a9c9342ff2a038a3dafb',
    'tools/local_entry_server/protobuf.py': 'c6d00262da031fb03a138c34b6a86dfc88f03e8ead2d6e71ae9bb21cd45de389',
    'work/local_native_login_world_dormant_runtime/world-read-stability.json': 'e271dbd01803f9dfcfac770c9e10038d4db4da2f279aa5025dc5f907aa408e29',
}


def checked_source(relative):
    raw = (ROOT / relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINS[relative]:
        raise ValueError('FROZEN_ROUTE_SOURCE_CHANGED')
    return raw


def load(relative, alias):
    # Execute exactly the bytes whose digest was checked, avoiding a reread race.
    raw = checked_source(relative)
    spec = importlib.util.spec_from_file_location(alias, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    exec(compile(raw, str(ROOT / relative), 'exec'), module.__dict__)
    return module


movement_contract = json.loads(checked_source('work/local_movement_contract/contract.json'))
action_contract = json.loads(checked_source('work/local_move_action_followup/contract.json'))
authority = load('tools/local_movement_authority/model.py', '_cp63_authority')
codecs = load('tools/local_entry_server/codecs.py', '_cp63_codecs')
pb = load('tools/local_entry_server/protobuf.py', '_cp63_pb')
if (movement_contract['C2S']['opcode'] != 0x4e2b
        or movement_contract['C2S']['UID_in_message'] is not False
        or tuple((r['word0_delta'], r['word1_delta']) for r in
                 action_contract['direction_table']['entries'][:8]) != authority.DELTAS):
    raise ValueError('FROZEN_MOVE_SEMANTICS_REQUIRED')

OPCODE = 0x4e2b
START = authority.pack_grid(32571, 32951)
LOCK_TYPE = type(threading.Lock())


def digest_ok(value):
    return (type(value) is str and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


@dataclass(frozen=True, slots=True)
class WorldEvidence:
    owner: object = field(repr=False)
    session_token: object = field(repr=False)
    sample_token: object = field(repr=False)
    selected_uid: int
    selected_name: str
    map_id: int
    start_packed: int
    control_sha256: str
    selection_sha256: str
    world_sample_sha256: str
    verified_selected_actor_world: bool


@dataclass(frozen=True, slots=True)
class DirectionalEvidence:
    world: WorldEvidence = field(repr=False)
    edge: authority.Edge
    tile_ready: bool
    tile_passable: bool | None
    full_navigation_passable: bool | None
    independently_verified: bool
    verifier_source_sha256: str
    evidence_sha256: str


@dataclass(frozen=True, slots=True)
class Result:
    accepted: bool
    reason: str
    accepted_count: int
    authoritative_packed: int
    request_start: int | None = None
    request_direction: int | None = None
    destination: int | None = None
    frame_size: int | None = None
    # Empty immutable wire output is unconditional, including all refusals.
    replies: tuple = ()
    stop_trial: bool = True

    def metadata(self):
        return {
            'schema': 'lc-one-self-move-route-result-v1',
            'accepted': self.accepted, 'reason': self.reason,
            'accepted_count': self.accepted_count,
            'selected_uid': 1, 'map_id': 0,
            'authoritative_packed': self.authoritative_packed,
            'request_start_packed': self.request_start,
            'request_direction': self.request_direction,
            'destination_packed': self.destination,
            'opcode': OPCODE, 'frame_size': self.frame_size,
            'reply_count': 0, 'own_SC4E2C_count': 0,
            'denial_or_correction_count': 0,
            'stop_trial': True, 'client_reconciliation_proven': False,
            'client_prediction_or_render_proven': False,
        }


def parse_payload(payload):
    """Required unique field1 uint32, field2 int32; local strict subset.

    Direction0..7 is checked by authority. Negative int32 uses uint64 sign
    extension, never zigzag. Unknown/duplicate fields refuse in this policy.
    """
    try:
        with pb.parse_message(payload, schema={1: 0, 2: 0},
                              limits=pb.WireLimits(max_body=17, max_fields=2,
                                                   max_field_bytes=17)) as parsed:
            if any(len(parsed.occurrences(n)) != 1 for n in (1, 2)):
                raise ValueError('REQUIRED_FIELDS')
            start, direction = (parsed.occurrences(n)[0].value for n in (1, 2))
            if not 0 <= start <= 0xffffffff:
                raise ValueError('UINT32')
            if 0 <= direction <= 0x7fffffff:
                pass
            elif 0xffffffff80000000 <= direction <= 0xffffffffffffffff:
                direction -= 1 << 64
            else:
                raise ValueError('INT32')
            return start, direction
    except (ValueError, TypeError, BufferError):
        raise ValueError('MALFORMED_MOVE_PAYLOAD') from None


def decode_one_wire(wire, *, cipher_pointer):
    """Offline framing helper; the broker already uses the pinned C2S codec.

    Explicit plaintext mode only. No enabled-cipher assumption, encoder, socket,
    stream loop, or synthesized CS packet is present in this module.
    """
    if type(wire) is not bytes or not 10 <= len(wire) <= 32:
        raise ValueError('BOUNDED_SINGLE_C2S_WIRE_REQUIRED')
    decoder = codecs.ClientPlaintextDecoder(cipher_pointer=cipher_pointer,
                                           max_frame=32, max_buffer=64)
    try:
        frames = decoder.feed(wire)
        decoder.finish()
        if len(frames) != 1:
            raise ValueError('ONE_FRAME')
        return frames[0]
    except ValueError:
        raise ValueError('BOUNDED_SINGLE_C2S_WIRE_REQUIRED') from None


class OneSelfMoveRoute:
    """One instance per exact owner; the lock serializes check+commit.

    current_world(owner) must independently revalidate current registry owner,
    selected saved UID/name, retained native identity, source pins, and sample
    freshness, then return the *same* immutable WorldEvidence instance. It must
    return None on owner revocation/change/expiry. verified_edge(world, edge)
    must independently establish loaded source-proven tile + occupancy/environment
    conditions for this exact edge and sample; CP62 tile-only results are not that.
    Callbacks are trusted, synchronous, non-reentrant, and never call this route.
    No such live callbacks are provided by this package.
    """
    def __init__(self, owner, world, *, current_world, verified_edge, cipher_pointer,
                 owner_serialization):
        if cipher_pointer not in ('null', 'present_disabled'):
            raise ValueError('EXPLICIT_PLAINTEXT_CIPHER_MODE_REQUIRED')
        if not callable(current_world) or not callable(verified_edge):
            raise ValueError('EXTERNAL_WORLD_AND_EDGE_VERIFIERS_REQUIRED')
        if type(owner_serialization) is not LOCK_TYPE:
            raise ValueError('SHARED_OWNER_SERIALIZATION_LOCK_REQUIRED')
        if not self._valid_world(world, owner):
            raise ValueError('EXACT_SELECTED_CP59_WORLD_REQUIRED')
        self._owner, self._world = owner, world
        self._current_world, self._verified_edge = current_world, verified_edge
        self._cipher_pointer = cipher_pointer
        # Root must use this same lock for owner/session/world revocation. A
        # route-private lock alone does not serialize changes to the registry.
        self._lock = owner_serialization
        self._stopped = False
        self._state = authority.initialize(
            authority.Selection('CP63_EXACT_OWNER', 1, True, world.selection_sha256),
            authority.ActorGrid('CP63_EXACT_OWNER', 1, START, True,
                                world.world_sample_sha256))
        with self._lock:
            if self._current_world(owner) is not world:
                raise ValueError('CURRENT_SAME_WORLD_SAMPLE_REQUIRED')

    @staticmethod
    def _valid_world(world, owner):
        return (type(world) is WorldEvidence and owner is not None
                and world.owner is owner and type(world.session_token) is object
                and type(world.sample_token) is object
                and world.sample_token is not world.session_token
                and type(world.selected_uid) is int and world.selected_uid == 1
                and type(world.selected_name) is str and world.selected_name == 'SoloKnight'
                and type(world.map_id) is int and world.map_id == 0
                and type(world.start_packed) is int and world.start_packed == START
                and type(world.control_sha256) is str and world.control_sha256 == CONTROL
                and digest_ok(world.selection_sha256)
                and digest_ok(world.world_sample_sha256)
                and world.verified_selected_actor_world is True)

    def state_metadata(self):
        with self._lock:
            return {'accepted_count': self._state.accepted_count,
                    'authoritative_packed': self._state.current_packed,
                    'stopped': self._stopped}

    def receive_frame(self, owner, frame):
        """Broker supplies its already source-bound decoded frame, returns Result.

        It must consume Result.replies (always empty) and honor stop_trial after
        recording bounded metadata. Registration/capture/termination remain Root
        integration work; this helper changes no broker or runtime.
        """
        with self._lock:
            start = direction = frame_size = None

            def result(accepted, reason, destination=None):
                self._stopped = True
                return Result(accepted, reason, self._state.accepted_count,
                              self._state.current_packed, start, direction,
                              destination, frame_size)

            if owner is not self._owner:
                return result(False, 'FOREIGN_OWNER')
            if self._stopped and not self._state.accepted_count:
                return result(False, 'ROUTE_STOPPED')
            # Use shape rather than Frame class identity: frozen broker imports
            # the same pinned codec under a different module alias.
            if (not hasattr(frame, 'payload') or type(frame.payload) is not bytes
                    or type(getattr(frame, 'opcode', None)) is not int
                    or frame.opcode != OPCODE
                    or type(getattr(frame, 'wire_length', None)) is not int
                    or type(getattr(frame, 'sequence', None)) is not int
                    or not 0 <= frame.sequence <= 0xffffffff
                    or type(getattr(frame, 'trailer_length', None)) is not int):
                return result(False, 'SOURCE_DECODED_MOVE_FRAME_REQUIRED')
            size = 10 + len(frame.payload)
            expected = size if self._cipher_pointer == 'null' else ((size + 1) & ~3) + 2
            if (frame.wire_length != expected or not 10 <= expected <= 32
                    or frame.trailer_length != expected - size):
                return result(False, 'SOURCE_DECODED_MOVE_FRAME_REQUIRED')
            frame_size = frame.wire_length
            try:
                start, direction = parse_payload(frame.payload)
            except ValueError:
                return result(False, 'MALFORMED_MOVE_PAYLOAD')
            try:
                if self._current_world(owner) is not self._world:
                    return result(False, 'CURRENT_SAME_WORLD_SAMPLE_REQUIRED')
            except Exception:
                return result(False, 'CURRENT_WORLD_VERIFIER_FAILED')

            def passability(edge):
                proof = self._verified_edge(self._world, edge)
                if (type(proof) is not DirectionalEvidence
                        or proof.world is not self._world
                        or type(proof.edge) is not authority.Edge or proof.edge != edge
                        or not all(type(v) is int for v in (
                            proof.edge.uid, proof.edge.start_packed,
                            proof.edge.destination_packed, proof.edge.direction))
                        or proof.independently_verified is not True
                        or proof.tile_ready is not True
                        or not digest_ok(proof.verifier_source_sha256)
                        or not digest_ok(proof.evidence_sha256)):
                    raise ValueError('EXACT_VERIFIED_EDGE_REQUIRED')
                # A PASSABLE tile without complete navigation checks stays unknown.
                allowed = (proof.full_navigation_passable
                           if proof.tile_passable is True else None)
                if proof.tile_passable is False:
                    allowed = False
                return authority.Passability(edge, allowed, True, True,
                                             proof.evidence_sha256)

            transition = authority.accept_one(
                self._state, authority.Request('CP63_EXACT_OWNER', start, direction,
                                               True, 'SOURCE_PARSED_CS4E2B'), passability)
            if transition.accepted:
                # Revalidate after independent edge verification and before atomic
                # state install. Caller owner registry must share serialization.
                try:
                    if self._current_world(owner) is not self._world:
                        return result(False, 'CURRENT_SAME_WORLD_SAMPLE_REQUIRED')
                except Exception:
                    return result(False, 'CURRENT_WORLD_VERIFIER_FAILED')
                self._state = transition.state
            destination = transition.edge.destination_packed if transition.edge else None
            return result(transition.accepted, transition.reason, destination)
