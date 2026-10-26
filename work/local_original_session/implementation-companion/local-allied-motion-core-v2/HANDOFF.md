# LOCAL Allied motion core v2 — pending-safe preissued proof

SOURCE_COMPLETE / source_ready:true / test_ready:false / selected:false / runtime:UNRUN / WRITER_RELEASED.

This immutable private descendant changes only v2 files. Parent v1 remains byte-for-byte unchanged and retains its concrete pending-transport defect. `parents.json` pins exact v1 product, existing navigation/Allied/Broker cohort, REA216/314 and the actual canonical_batch 86c0d7d13a9649840cc875c8368b96d9ef698c02dd1241fcd1998063be14c0e9. `allied_motion.diff` is the exact v1→v2 product delta; manifest pins the resulting product. Common/original/Controller/Broker/Test/queue/ACTIVE/account files, games, ports, sockets and runtime remain untouched. Main owns review/queue selection.

## Concrete defect and correction

v1 attempt() executes after policy.begin_write. Its _sender→_current→Root.later_resource→BatchStore._current calls BrokerProvider.current. That source explicitly requires pending_opcode None, pending_size zero and no drain timestamp, so the expected outgoing 4E2C fails BATCH_PENDING_TRANSPORT_REFUSED before write. v2 retains full RESOURCE/navigation validation before reservation and full current/RESOURCE validation after policy.drained, but uses a separately typed DeliveryProof while that exact frame is pending.

The final synchronous begin() must be a hook inside the sealed original Broker._send after its last await/checkpoint and before policy.begin_write. It freshly admits the real issued CLEAR edge, registration/generation/lease/current owner/task/row, live RESOURCE and BatchStore._current while idle. Under existing Store→character→realm locks it captures the exact actual Store/provider/source/path/profile and immutable whole raw preimage in a frozen DeliveryProof. No ledger, actor registration or Store write is added.

begin() records the original sender frame. A call_soon invalidator closes admission if the event loop runs between precheck and attempt. attempt() requires the same exact original sender frame and task, same registration/lease/row/policy/frame, same typed proof, source-sealed Allied/Broker/navigation/core, exact actual Store/provider owner and original canonical Store registry entry. It uses existing Root.later_current (live lease/selection operation, not RESOURCE) and BrokerProvider.delivery_current, whose selected path intentionally omits current()'s idle-transport requirement. Under original locks, original BatchStore._read validates the current document; raw must equal both captured preimage and Store._raw, document must equal Store.data, active and transaction pending must remain absent. The original BatchStore delivery owner validator uses this _read/raw/doc pattern as well. No BatchStore._current or provider.current is called on the pending path.

attempt() then verifies the actual policy reservation fields and advances to WRITE_ATTEMPTED once. The integrating sender must immediately call writer.write without another await or unrelated callback; this source-only child cannot edit that future hook. Any failure/cancellation between begin and actual positive drain must call fail and preserve UNKNOWN/pending. No prewrite rejection permits retry on this core.

drained() still uses original caller code/globals/self/writer/row/wire and full _current→later_resource after policy.drained. It requires actual queued==0, counter+1 and cleared pending fields before committing once. Proof references are cleared on successful completion. Failed/uncertain delivery keeps state/pending/real lease and blocks reconstruction/retry. Controller/Pose and original client movement claims remain absent.

## Unchanged limits

The policy stays EXPLICIT_LOCAL_PLAYER_PRE_STEP_GRID_ONE_STEP_V1. This is a LOCAL start-grid reference choice; original Player sender f2 convention remains UNKNOWN. Required wire fields remain u32/u32/i32 wire0, directions0..7. Navigation only knows initial placement, so one committed step only. Integration must project committed/UNKNOWN motion to every occupancy consumer before runtime; parent registration.placement is not mutated. Cross-core occupancy and repeated movement remain open. Existing Broker both 4E2C interception points still route NPC-only and require a reviewed typed motion descendant. Genuine idle companion.tick_locked remains the prospective caller under _row_operation; no synthetic C2S/ACK/CLIENT_POSE is added.

## Verification

`python -B work/local_original_session/implementation-companion/local-allied-motion-core-v2/inspect_source.py`

43 checks PASS. Existing pure frame/state checks are reused. New isolated pending model executes exact AST-selected original BrokerProvider.current and delivery_current methods: v1's pending refusal is reproduced; the actual v2 _delivery_current method admits the unchanged pending Store model, refuses changed preimage, and refuses expired proof. A real local asyncio event-loop yield confirms call_soon invalidation. The model has explicitly fake fixture objects and creates no live PlayerRegistration/capability/ACK; these are unit checks, not packet/runtime success. No packet caller/RUN exists until Broker/current-occupancy integration, hence test_ready:false.
