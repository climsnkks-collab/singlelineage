# Separate LOCAL mode carrier candidate

This is a proposed separate channel. It is **not** a Lineage gameplay opcode,
packet-test-client-v5 request, or an extension of the selected LUI2 wire.
LUI2's existing 20B REQUEST_MODEL / 1024B DISPLAY_MODEL is unchanged and does
not accept these frames. No producer, pipe, native callback, endpoint, event-loop
task, ready receipt, actual OPEN receipt or control enablement is implemented.

## Required actual binding before commands

An exact selected `NativeModeEndpoint` source and the real server Plan/Factory
must retain the existing authenticated process instance, birth, job/owner,
connection lifetime, native owner thread and genuine actual OPEN association.
Transport authentication alone is not mage/selection authority. The actual OPEN
bridge is independently missing from `local-ui-click-open-bridge-v1` and native
v4's `local_ui_selected_open::Bridge` is unimplemented.

After genuine `OpenPort.require_open_locked`, `ModeIngress.bind_locked(writer)`
captures that exact issued Python intent/attempt/receipt, state and ui_epoch,
native panel, display epoch and draw/display sequence, canonical mage revision,
fresh token16 and secret32. Python object references remain server authority;
they must never become generic client-supplied numeric capabilities. Only the
token, key and bounded scalar fields cross the new protected LOCAL connection.
Do not reuse the bootstrap secret or route keys from a previous OPEN/connection.
Do not persist/log/print keys or serialize the Binding/Request object.

`NativeModeEndpoint` is a missing exact-source class with source-defined,
synchronous nonblocking methods:

| Method | Required behavior |
| --- | --- |
| `bind_mode(*, binding)` | Queue a real binding to the exact retained native owner/OPEN and return literal `QUEUED`. Queueing is PENDING only. |
| `read_mode_ready(*, binding)` | None, or exact-source nominal `NativeModeReady` with identical binding, intent and panel and actual `consumer_installed=True`, `key_bound=True`. The future endpoint must prove the owner-thread command consumer and key association, not copy flags from a request. |
| `read_mode(*, binding)` | None, or exact-source nominal `NativeModeFrame` with identical binding and immutable bytes `wire` received from the actual enabled native mode control. |
| `publish_mode_ack(*, binding, wire)` | Admit the exact authenticated response at most once, returning `QUEUED`; this proves neither native reception nor display. |
| `revoke_mode(*, binding)` | Revoke control admission for the exact binding and disable native controls; return is not actual native CLOSE proof. |

Methods must not call Host, acquire its row, block on the native owner, wait,
reconnect, replay or perform Store writes. Actual native peer/current identity,
owner-thread dispatcher, consumer lifetime, authenticated key delivery and
current OPEN/display association belong to that source. They are not supplied
by this candidate's field validation or by seeing LUI2/Checkpoint.

Keep controls disabled until actual paired readiness. Atomically disable mode
controls when the single request is submitted. A binding admits exactly sequence1
and one follow **or** station request. There is no second command, reset,
automatic rebind, retry or successor allocation. Reusable UI requires a later
coherent actual close/scope/OPEN successor; the existing primitive is one-attempt.

## Fixed typed command

Little endian `struct '<4sBBH16sQQQIQ'`, 60B body plus 32B HMAC, exactly **92B**:

| Offset | Value |
| --- | --- |
| 0..3 | ASCII `LMC1` |
| 4 | version1 |
| 5 | action1 FOLLOW or2 STATION |
| 6..7 | reserved0 |
| 8..23 | per-binding token16 |
| 24..31 | request sequence1 |
| 32..39 | exact server OPEN request sequence |
| 40..47 | actual bound display epoch |
| 48..51 | actual bound display/draw sequence, uint32 |
| 52..59 | expected canonical mage revision, uint64 |
| 60..91 | HMAC-SHA256(key32, `LOCAL-COMPANION-MODE-V1\0COMMAND\0` + body) |

OPEN sequence and display sequence are distinct. The namespace/channel and
fresh key/token bind the intent; selection/owner/lease/ui_epoch remain retained
objects and are rechecked at command admission. Fixed length, MAC, magic,
version, reserved bits, action, token, exact first sequence, epoch/display and
revision must all pass. No coordinates, UID injection, follow distance, summon,
dismiss, item, equipment, combat or magic operation is accepted. FOLLOW preserves
the existing distance. STATION uses the original Controller's current actor
anchor. Both invoke the existing Host/Controller behavior.

## Event-loop dispatch and actual observation

The real selected server loop must create/call `await route.receive_once()`
after its original row operation exits. The route rejects a held row before any
endpoint read. It never acquires a row operation around `await Host.command`;
the original Host command owns that single operation. No synchronous native
callback invokes Host. This candidate does not install the loop/caller.

After decoding, Request identity is retained and burned before the await.
Host accepts this optional exact-source issued Request inside its existing
operation, rechecks actual OPEN/row/current selection/owner/direct and companion
leases/actor generation/ui_epoch, verifies current Controller and expected mage
revision, and snapshots the canonical row. It executes its unchanged follow or
station branch. The existing Controller performs `update_preferences` using
its current revision CAS and original atomic Store writer. No replacement save,
forced state or direct handler invocation is introduced.

Before rendering/returning and while still holding the original operation, the
observer requires actual CONFIGURED, the same current owner/lease/actor, active
Controller configuration equal to canonical saved movement, and the exact full
canonical row expected after that movement-only change. Revision is unchanged
for an idempotent save and increases by1 for an actual saved change, matching
the original Store contract. Unrelated preferences/character fields must match.
`Observation(SAVED)` is the resulting source observation, not a claim of native
UI/packet/game/restart success. No runtime instance has produced it here.

Any uncertainty burns admission and retains UNKNOWN, first bounded error,
issued Request, any actual Store observation, revoke failure and ACK failure.
An authenticated admitted command can produce one UNKNOWN response attempt.
Malformed/unauthenticated input produces no actionable Request/response.
No second ACK write follows an uncertain first publication. Cancellation
propagates after revoking admission. No receipt/phase clears old native work.

## Fixed typed result

Little endian `struct '<4sBBH16sQQQQB7x'`, 64B body plus32 MAC, exactly **96B**.
Fields are `LMA1`, version1, status1 SAVED or2 UNKNOWN, reserved0, token16,
request sequence, OPEN sequence, before revision, after revision, effective
mode1 FOLLOW or2 STATION (0 for UNKNOWN), seven zero padding bytes, then
HMAC-SHA256(key32, `LOCAL-COMPANION-MODE-V1\0ACK\0` + body).
UNKNOWN's before/after/mode fields are0 and assert no save outcome; actual saved
evidence, if already observed before a later render/ACK error, remains separately
retained server-side. `ACK_QUEUED` is admission only. There is no actual native
ACK receipt consumer here. Unknown/revoked bindings must remain disabled.

## First blocker and future Test boundary

First: implement/select the real actual native OPEN Bridge + NativeOpenEndpoint
with retained Host-to-display association and owner-thread receipt transport.
Then select a **new separate** exact paired mode command channel/consumer with
the above authenticated current binding; integrate immutable Plan/Factory,
Host/click pins, scope lifetime and event-loop caller. The candidate187-row import
graph is neither that selection nor proof of cold/runtime compatibility.

Only then can Test own a real packet-test-client-v5 scenario: normal login,
character selection/WORLD, legitimate mage summon/current actor, real click,
actual native OPEN receipt, actual native user mode request, this decoder/route,
Controller/Store observation, real ACK, close and fresh save readback. No invented
game packet or direct `Host.command` call substitutes for the native user request.
No caller/RUN is supplied while that route is absent; `test_ready:false`.
