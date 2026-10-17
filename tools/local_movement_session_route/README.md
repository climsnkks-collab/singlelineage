# CP63 one self movement session route

`route.py` is an in-memory adapter for one source-bound `CS_MOVE_NOTI 0x4E2B`.
It does not register a broker route, create sockets, emit packets, operate a
process, change a slot, perform UAC/online work, or persist authority state.
Successful synthetic fixtures prove the adapter logic only. Live integration is
**blocked** until Root supplies reviewed independent evidence verifiers.

The frozen source pins include both movement contracts, the pure authority model,
the C2S codec and protobuf reader. The movement contract proves required field1
`uint32` packed current/start grid and required field2 `int32` direction. No UID
is on this message: UID1 belongs to the selected `SoloKnight` owner. The initial
local policy requires map0/start `(32571,32951)`, never derived from the CS body.
The proven direction table permits0..7; axis compass names remain unasserted.

The existing C2S codec has a10-byte header: uint16 declared length, uint32 sequence,
uint16 opcode and uint16 body length. Explicit plaintext `null` totals declared+2;
`present_disabled` totals declared and uses its pinned padding calculation. Enabled
cipher has no supported contract here. Sequence is framing metadata only and is
not an authority sequence or replay proof. Maximum single frame32B/body17B;
unknown fields, duplicates, omitted required fields and invalid scalar encodings
refuse under this explicit local subset. Negative int32 uses64-bit sign extension.
`decode_one_wire` supports a complete wire fixture; actual broker stream framing
remains the existing pinned decoder. `receive_frame` accepts its decoded shape
under the trusted integration boundary (module aliases can differ).

`OneSelfMoveRoute` requires an exact owner object and immutable `WorldEvidence`,
containing opaque session/sample identity capabilities and SHA256 evidence refs.
`current_world(owner)` must independently revalidate the registry and retained
native identity, selected saved UID/name, map/start state, source pins and freshness,
returning the *same instance*. A copied DTO, matching PID, connection ID, hash or
JSON string is not a live binding. The owner/session/world registry and route must
share the supplied `owner_serialization` lock, including revocation; callbacks
are synchronous/non-reentrant and run inside this lock. Root must supply this
serialization in live integration; a private route lock would not protect registry
changes. The route rechecks world evidence after edge verification before commit.

`verified_edge(world, edge)` must return independently verified directional evidence
for the same immutable world instance, exact UID/start/destination/direction and
loaded tile, with full navigation passability True. The verifier must review source
and independently establish occupancy/environment conditions in the same sample.
This module does not decode flags or infer these conditions. CP62's proposed
`tile-passability.json` reports tile-level PASSABLE/BLOCKED but full navigation is
UNKNOWN and has no live owner/session capability. It cannot authorize this route.
Historical CP59 world-read stability is preserved context, not current evidence.
No live evidence factory, JSON importer or approved verifier is provided here.

The route holds its lock across receive, exact start comparison, verification and
immutable authority-state installation. At most one request commits. Duplicate,
stale/foreign, unknown/blocked tile, expired sample or malformed payload stops the
trial with no guessed denial/correction. `Result.replies` is always `()` and
`stop_trial=True`; no own `SC4E2C` echo is produced because the frozen action
contract shows relative-step/retransmission risk. Root must record result metadata
and honor the stop condition. An accepted local state is separate from client
prediction, input delivery, completion, visible rendering and ACK consumption.

CP61's command bridge is separately prepared source work. Its original command may
return without sending or may choose a different direction, so only an actual
source-decoded CS frame can enter this adapter. Registering the route on the exact
selected broker owner, establishing live sample correlation, triggering the bridge,
and stopping after one result are deferred Root integration work after CP62.

Run `python tools/local_movement_session_route/verify.py`. The verifier writes only
this directory's bounded `verification.json`; its wire encoders are synthetic
fixture helpers and are not imported by the product adapter.
