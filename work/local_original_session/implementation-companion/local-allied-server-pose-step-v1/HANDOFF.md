# COMPANION-MAGE — explicit LOCAL server pose one step

State: **SOURCE_COMPLETE / WRITER_RELEASED**, source_ready=true (bounded source),
test_ready=false, run_ready=false, selected=false, runtime=UNRUN.

Owned directory only. No common/original/Test/queue/ACTIVE edit, save copy,
game, listener, port, runtime process or packet execution. Existing dirty main
and unrelated files preserved. This artifact is not a finished runtime cohort.

## Lineage and source changes

`parents.json` records exact hashes/bytes for all eight inputs. The six product
files and their hashes are in `manifest.json`; adjacent `.diff` files show each
actual parent delta. `build_private.py` deterministically reconstructs them.

- Controller and Host derive from `local-server-tombstone-retirement-v1/`.
- Allied derives from that same tombstone parent, adding the exact two
  RootPlayers later-current/resource methods from `local-allied-later-current-v1/`
  and using later-resource for the existing server snapshot.
- Navigation, motion and nominal motion registry derive from
  `local-allied-motion-broker-v1/`; their only changes are exact dependency pins
  for the new Allied source and consequent registry/navigation hashes.
- Required **unchanged external Broker** is motion-broker-v1 `broker.py`,
  SHA256 `c422517ebe9e934c0425aaf833efca081f604d747654df9ffb8f66561a48e09d`.
  It provides actual typed `_send(..., allied_motion_operation=core)`.
  New removal v5 Broker `b1fdf585...` is a separate v4 descendant and is **not**
  combined here. Main must compose the two actual deltas and update the motion
  and navigation Broker pins before selecting a runtime cohort.

## Opt-in contract

Pass `pose_policy=LOCAL_SERVER_POSE_ONE_STEP` to both the selected
`CompanionBootstrap` and its actual `AlliedPlayerPort` factory. Host propagates
the policy into Controller, including `fresh_for_scope` successors; Port checks
the same Host policy at construction. Omitting the policy preserves original
Controller CLIENT_POSE activation and unavailable default Port movement.

`ActorSnapshot.server_pose` is a separate nominal `ServerPose`, carrying exact
registration, exact retained `AlliedMotion.State`, originating Port and explicit
policy. It never fills `pose`, which remains `None`. Controller accepts this
only through the actual Port's live validation. Each snapshot and validation
uses exact registration/lease/generation/current selected row/canonical task,
drained phase, same live owner and account RESOURCE. No active pose is admitted
outside that real current operation. Original lease/Store/owner/row/selection
checks and tombstone behavior remain intact.

After real 4E96 drain, spawn projects the initial typed motion state from the
actual registered placement and current RESOURCE. The existing genuine Broker
idle `companion.tick_locked` reaches the ordinary Controller tick. Port.step:

1. Revalidates that exact server pose and zero committed steps.
2. Computes only the existing axis-sign goal direction and one-tile target.
3. Queries the real initial navigation producer; a missing or blocked decision
   raises MotionRefused before planning/sending.
4. Calls the actual typed motion plan and awaits the original Broker `_send`
   once, with its identical frame and exact operation lock.
5. Returns a snapshot only after phase COMMITTED, no pending delivery, and
   state identity exactly `step.after`, then rereads live RESOURCE/current.

Unknown sends propagate into the original Controller UNKNOWN and retained core
state/lease path; no retry/reset/retirement is added. Later snapshots use the
committed state, including XP's server snapshot, rather than stale publication
placement. Later movement attempts return REFUSED before initial navigation,
or ordinary Controller AT_GOAL if already within its target spacing. Other
actors' initial occupancy remains protected by the unchanged nominal registry.
This does not implement ongoing navigation, a second step, Native input/pose,
render or ACK. Original SC4E2C start-grid convention remains explicit LOCAL.

## Verification and first remaining blocker

Non-runtime source check:

```powershell
python work/local_original_session/implementation-companion/local-allied-server-pose-step-v1/verify_focused.py
```

`verification.json`: **37 checks PASS**. Parent/product byte hashes and syntax,
unchanged Controller/Host/Root methods outside declared deltas, direct pins,
single actual typed Broker await, positive commit and pre-navigation second-step
refusal are checked. Isolated Controller doubles cover unchanged default pose,
explicit server activation, lost same-operation admission, one move and later
refusal using the committed grid. These are source/model results, not real live
registration, transport, Store, lease, packet or runtime PASS.

The first runtime selection blocker is a single exact Broker descendant that
contains both motion `c422...` and removal v5 `b1...`, with corresponding direct
pins. The final cold graph must also select these Controller/Host/Allied files,
repin its existing namespace/feature/plan consumers, supply both explicit policy
keywords through the real source factory, and retain the existing genuine idle
scheduler. A normal login/roster/select/WORLD + F101 registration + scheduler
caller/RUN and Test-owned fresh-copy/strictclose observations are not supplied
by this bounded artifact, so test_ready remains false. No synthetic C2S request,
manual handler invocation or fabricated runtime command is supplied.
