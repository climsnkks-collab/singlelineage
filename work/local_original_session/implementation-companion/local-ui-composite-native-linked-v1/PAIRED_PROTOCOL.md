# Unselected LOCAL OPEN plus one mode command

One issuer, protected authenticated pipe, native State, original absolute deadline
and native terminal guard. The new native Run calls OPEN **Exchange**, then the
unchanged LMC1/LMA1 Session. It calls neither standalone Run. Bootstrap/receipt/
binding/ready/ACK never reset the deadline or reconnect. The native link worker's
LOP1-only DLL is a separate immutable candidate, not a selected composite DLL.

Order: actual LOP1 1152B -> actual owner-created/drawn LOR1 128B -> fresh LMB2 128B
-> owner-installed controls' authenticated LMR2 96B -> one LMC1 92B -> one LMA1
96B -> native verification LMZ2 96B. Each side has one sequential reader. Existing
LUI2 is not used concurrently. No inventory/gear/combat message is accepted.

LMB2 uses `<4sBBH32s32s16sQQIQIQ`: magic, version2, kind1, reserved0, exact OPEN
nonce32, fresh binding secret32, token16, OPEN sequence, actual draw epoch,
actual draw sequence, canonical expected revision, owner thread, native HWND.
The key crosses only the existing authenticated protected pipe, after actual
OPEN. No secret, complete binding or command key is written to evidence or logs.
The receiver compares nonce/owner/HWND/epoch/sequence to its own current actual
OPEN receipt. Those scalar fields do not supply server selection/lease authority.

LMR2's body is `<4sBBH16sQQIQIQ>` (64B): magic, version2, kind2, reserved0,
token and the same bounded OPEN/display/revision/owner/HWND fields. Its tag is
HMAC-SHA256(key, `LOCAL-COMPANION-MODE-V1\0BIND_READY\0` + body).
It is sent only after the established owner creates both actual native controls
and confirms their current display/key installation. Queueing LMB2 proves no
readiness. Only owner callbacks call User32/GDI and build a mode request.
The genuine WM_COMMAND path checks exact control HWND/action/current display,
burns its one submission before publishing, and disables both controls.

LMC1/LMA1 are unchanged mode-route-v1 92B/96B commands/results. Session validates
HMAC, token, sequence1, actual OPEN/display and revision. Server NativeModeEndpoint
requires exact source ModeIngress.Binding identity, route.endpoint, current
NativeOpenEndpoint receipt and intent; syntax projections supply no authority.
QUEUED ACK is distinct from native reception.

LMZ2 body64 is magic/version2/status-from-verified-LMA1/reserved0, token16,
sequence1 u64, and32B keyed digest of the exact96B ACK using `ACK_RECEIVED\0`.
Its32B tag uses `ACK_RECEIPT\0`. The common domain prefix includes its null byte.
This is a native **worker verification** receipt, never ACK rendering, Store
success, UI interaction or saved settings. UNKNOWN remains UNKNOWN.

All OPEN/display/command uncertainty terminates admission, retaining first
failure/evidence. There is no command replay/rebind/retry/automatic successor.
The original250ms native display retention and original native bootstrap10s
deadline remain unchanged. Thus this is not a reusable settings panel: a human
session needs a genuine authorized current display/scope successor contract;
this source cannot extend time or mint one from the old display/receipt.

Factory/Plan/launcher/composite DLL/Host/click/scope/event-loop caller selection
is absent. The endpoint is source, not installed runtime. Final feature source,
Test/UI/runtime readiness are false; RUN_COMMAND is null. The main must select
an exact immutable graph and provide genuine normal gameplay preparation before
Test. No direct Host invocation or fixture can satisfy that boundary.

Isolated evidence: five actual authenticated process/Job/pipe/owner-desktop cases
cover OPEN plus real mode readiness and four refusals. One later focused case
reuses that same real OPEN/ready path then supplies a macro-gated **test-only**
signed command from the helper, receives UNKNOWN and verifies actual LMZ2.
It exercises the concrete phase seam without input events, Host or Store.
Production compilation explicitly excludes the macro. Native user command
production and real Host/Controller save/ACK rendering remain UNRUN.
