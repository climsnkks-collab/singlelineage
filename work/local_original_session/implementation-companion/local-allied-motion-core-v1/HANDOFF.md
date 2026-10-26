# LOCAL Allied initial motion core

SOURCE_COMPLETE / source_ready:true / test_ready:false / selected:false / runtime:UNRUN / WRITER_RELEASED.

Owned changes are only this new private directory. No parent, common, original, Test, queue, ACTIVE, game, process, socket, port or saved account bytes were modified. Main owns review and any queue decision. Existing unrelated dirty checkout remains untouched; no branch/worktree/commit was created.

`allied_motion.py` is an additive source (diff against /dev/null). `parents.json` records the exact full path/size/SHA256 of the inspected parent cohort and dependencies, including Allied later-current 3e87aec8, Broker e0db793f, navigation, REA216/314 and protobuf. `manifest.json` pins the resulting product and `verification.json` records the bounded checks.

The explicit policy is **EXPLICIT_LOCAL_PLAYER_PRE_STEP_GRID_ONE_STEP_V1**. Required SC4E2C fields are f1 uint32 UID, f2 uint32 packedgrid, f3 int32 direction, all wire0. Allowed direction 0..7 uses positive int32 varints, never ZigZag. The report is the initial start grid. This is a LOCAL reference choice prompted by the retained NPC L1J start-grid policy, not an original Player sender convention. REA314 leaves original f2 start/destination UNKNOWN; its remote MovingAction uses current Transform plus direction at Start and the then-current target at End. This core's server post-drain commit is a LOCAL authority policy and does not represent native End, client receipt, rendering or ACK.

`AlliedMotion` requires exact sealed modules, actual navigation and PlayerRegistration, real later canonical owner operation, generation/lease/row and live RESOURCE read. A retained per-registration core registry prevents reconstructing another core to retry uncertain or committed motion. `plan()` consumes only the navigation issuer's exact initial CLEAR decision and freshly rechecks it. `begin()` rechecks again, binds the actual policy row, sent count, same canonical task/current binding and immutable planned frame. Pure `proposal()` is a DTO projection only; it does not grant admission.

The only state commit is `drained()` after an actual original Broker `_send` call: caller code/globals/self/writer/row/frame identity, same canonical task and live registration/resource, previous WRITE_ATTEMPTED, actual local queued==0, sent counter +1, pending opcode/size cleared and drain timestamp cleared. No caller-provided boolean can certify completion. The Broker source is sealed to its exact parent, so an integrated descendant must update that source pin as part of its reviewed change. `attempt()` is the matching future hook after real policy.begin_write, before writer.write. It verifies the exact reserved opcode/frame size and active drain timestamp. Failure/close retains before/after/pending frame and registration/lease, records UNKNOWN and never rolls back or resubmits.

## Deliberate one-step boundary

The navigation parent proves only initial registered placement. This core therefore permits exactly ONE committed step for each registration. It does not modify registration.placement, Controller, AlliedPlayerPort, Pose or Store. It does not make the parent navigation's initial coordinates valid after motion. Before any runtime selection, integration MUST give every subsequent occupancy consumer the committed/UNKNOWN motion state; otherwise another actor could query the stale initial position. General repeated movement and cross-core occupancy are not supplied here. UNKNOWN delivery cannot be treated as absent or known at either endpoint. The registry intentionally retains state across close; later genuine generation teardown/retirement handling must preserve unresolved delivery.

## Broker/caller integration still required

The exact selected Broker currently intercepts every 4E2C in validate_reply and prewrite through its NPC mover, and its allied send operation recognizes publication/removal only. No route was bypassed or modified. A reviewed descendant needs a typed motion operation through both 4E2C gates, final synchronous begin after the last prewrite checkpoint, actual attempt hook, same-frame current/Store admission while drain is pending, real writer.drain/policy.drained then positive completion hook. Every write/drain/cancellation/current failure must call fail before exit, preserving UNKNOWN and pending lifetime. Do not use a new bool ACK, handler-direct transport or skip NPC guards. Original `_serve` idle polling already invokes companion.tick_locked under `_row_operation`; it is the prospective genuine scheduler. No synthetic C2S is needed.

Existing Controller still requires genuine Pose and currently remains AWAITING_POSE. This core supplies no CLIENT_POSE, ACTIVE, native movement or hotkey success. A separate explicitly typed server policy would need review without weakening that original contract. No runnable packet scenario is claimed before these Broker/caller/current-occupancy bindings exist, hence test_ready:false and no gameplay RUN command.

## Focused check

`python -B work/local_original_session/implementation-companion/local-allied-motion-core-v1/inspect_source.py`

35 meaningful pure frame/target/invalid-input/second-step/UNKNOWN retention and source-boundary checks pass. All eight directions have exact required field bytes and one-tile targets. The test's SimpleNamespace is explicitly a pure projection DTO and is never admitted as a live Decision, registration or ACK. Positive runtime drain is not fabricated; its source guard was inspected. No socket/native/game test occurred. Existing packet results remain unchanged.
