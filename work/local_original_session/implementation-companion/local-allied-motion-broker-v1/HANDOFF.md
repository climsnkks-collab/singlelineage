# COMPANION-MAGE — private Allied motion Broker v1

State: **SOURCE_COMPLETE / WRITER_RELEASED**, source_ready=true,
test_ready=false, run_ready=false, selected=false, runtime=UNRUN.

Owned directory only: `work/local_original_session/implementation-companion/local-allied-motion-broker-v1/`.
No common/original/Test/client/API/queue/ACTIVE edit, no game, process, port,
runtime output or save-copy operation. The v4 removal trial and its FIRST/close
remain independent and unmodified. Dirty main and its unrelated files preserved.

## Exact lineage

`parents.json` fixes the exact original inputs and `references.json` retains
their historical references without relabeling the original v3 Broker as v4.

- Broker: removal fresh-sample **v4**, `8fe7b3e26c4ae510184604624160445a0c6b28291daafc8feac92be4d3f7a7cc`.
- Navigation: initial-only v1, `58038ab43079578ab7d14dd7aa8fee32a206f550a3eead9d899e4f93e8ee0803`.
- Motion: pending-safe v2, `60e02b95c63b3eb89a8d04344c33cde8c71b54af8e87fafb1acedcfa964ca0b3`.
- Allied API dependency remains exact **later-current v1**,
  `3e87aec85aa85444571e2f4ff4b79613e23db3d9a4ebbd978723e7d050475dee`.
  The v4 trial cohort still selects older `3a2c39a6`; it is not a finished motion
  cohort. Final configuration must select the real later-current source and
  repin its existing consumers; this worker did not edit that configuration.

`manifest.json` holds all final product full hashes and sizes. The three `.diff`
files show exact source deltas. `build_source.py` reproduces those descendants
from the unchanged pinned parents. UTF-8 LF normalization changes some physical
byte counts; source diffs reflect actual text changes.

## Typed exclusive send

The new keyword `allied_motion_operation` accepts the exact selected
`allied_motion.AlliedMotion` instance. Its existing `planned` must be an exact
Step and the single tuple reply must be its identical frame. Admission checks
the actual Broker SourceSeal, Broker/record/root/owner/writer/row identities,
actual records membership, operation-lock identity and held state. Every other
send capability must be absent, game=True, restore-only=False.

The 4E2C exception applies only to that typed exact Player step. Unspecified
4E2C still passes both original NPC reply and post-checkpoint movement gates.
Original 4E96 registration and 4E40 removal branches are retained. AST comparison
confirms every class method except PersistentBroker._send is unchanged.

Within the actual original `_send` frame:

1. Existing checkpoint/sample/current checks run first. `motion.begin(planned)`
   follows the last relevant await and precedes the genuine policy.begin_write.
2. After policy.begin_write, a synchronous cancellation check precedes
   `motion.attempt(writer,row,wire)` directly before original writer.write.
   No await occurs from begin through attempt/write.
3. Genuine writer.drain and original fresh owner sample run. The typed branch
   keeps the exact pending policy and counter and waits for actual queue zero,
   using original policy.checkpoint and fresh sample after yields.
4. Genuine policy.drained precedes `motion.drained`. The core then checks the
   actual sender code/frame/globals, full idle current/RESOURCE, counter and
   zero queue before committing its single local server step.
5. Preflight errors and all per-wire BaseException paths call `motion.fail`.
   Synchronous callback cancellation is checked before begin/attempt/commit.
   Unknown delivery retains core pending data, registration and lease; no retry,
   rollback, fabricated ACK, native absence or lease retirement is introduced.

## Initial-placement occupancy safeguard

The initial-only navigation parent otherwise treated another already moved
Allied actor's retained publication placement as its current obstacle. Root
explicitly requested a source-pinned nominal read API after this was identified.

The new `allied_motion_registry.py` is sealed by both navigation and core. The
core's original retained `_CORES` state now belongs to this module and is bound
once through `register`. `initial_current(record)` is read-only and checks exact
record/root-membership, nominal core/state types, record/generation/lease/row,
initial placement and zero committed steps. Pending, committed, UNKNOWN, closed,
failed or changed-identity cores are refused. An actor with no core registration
remains eligible for its original publication placement. The registry is keyed
by retained record identity and validates the exact record, never by UID alone.

Navigation calls this API on every present Allied record before adding retained
placement to occupancy. Thus this source still supports only an initial one
step; after any progressed/UNKNOWN retained actor, subsequent navigation becomes
UNKNOWN. It does not pretend to implement ongoing multi-actor pose/navigation.

## Verification and remaining boundary

Run only the non-runtime check:

```powershell
python work/local_original_session/implementation-companion/local-allied-motion-broker-v1/verify_source.py
```

Result: **83 checks PASS** in verification.json. These cover parent/reference
hashes, product syntax/hashes, Broker-only method delta, direct pin agreement,
no-await hook placement, original pending-safe Store model, exact selected
SourceSeal implementation and nominal registry failure DTOs, and the exact
compiled `_send` control flow with explicitly isolated transport doubles.

Send-model negatives include mixed operation, equal-but-not-identical frame,
untyped 4E2C, checkpoint/begin/policy-begin/attempt/write/drain/postdrain sample/
policy-drained/commit failures, cancellation at checkpoint, synchronous policy
begin, drain and postdrain sample, invalid queue and nonzero-to-zero queue.
Failures preserve UNKNOWN/pending and prewrite failures perform no write.
These doubles do not construct or claim a real live registry/current/Store/lease.

No finished selected cold runtime cohort was produced. Controller, port,
scheduler, feature configuration, normal packet caller/RUN, real decision and
Test-owned observations remain absent. No new C2S packet or ACK exists. Local
transport commitment is not native pose, input, render or client movement PASS.
