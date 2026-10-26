# LOCAL click → native OPEN candidate contract

This is a private server candidate, not a selected/runnable transport. No native
endpoint implementation is supplied. The existing LUI2 display channel and
Checkpoint mailbox do not satisfy any OPEN receipt below.

`CompanionBootstrap.local_open` must be an exact `companion_local_open.OpenPort`
whose own SourceSeal and a separately selected native endpoint SourceSeal are
captured by the real Plan/Factory. A non-None generic interface is insufficient.
The selected `NativeOpenEndpoint` class must define source-owned synchronous,
nonblocking `submit_open(*, intent, model)`, `read_open(*, intent)`, and
`revoke_open(*, intent)`. No callback into Host, row reentry, synchronous native
window creation on the server thread, wait, packet ACK, fallback, or reconnect
may occur in these methods.

The Host-issued `OpenIntent` is retained by object identity. Its row, selected
state/selection, direct lease, companion lease, live actor UID/generation,
owner connection/direct lifetime, and ui_epoch remain server authority. The
sequence is one per retained OpenPort lifetime and is never reset/retried. These
Python object authorities must not be serialized as generic numeric capabilities.
The paired endpoint needs a genuine retained-owner mapping to native values.

`submit_open` may return the literal string `QUEUED` after admitting exactly
this intent to the native command path. It means PENDING only, with no panel
handle or OPEN success. Any exception or other result retains UNKNOWN. Unknown
submission, timeout, stale actual-open evidence, or invalid receipt issues one
best-effort revoke request, retains cancellation errors/intent/handle/evidence,
and prevents a second open. No retry or pending clear is supplied.

`read_open` returns None while no receipt exists. The only accepted success is
an actual exact-source `NativeOpenReceipt` instance with these attributes:

| Field | Required relation |
| --- | --- |
| intent | Same issued Python OpenIntent object |
| operation / phase | `OPEN` / `OPEN` |
| namespace / layout | `local-playable-mage-companion-v1` / `LOCAL` |
| sequence | Same issued server request sequence |
| display_epoch / display_sequence | Positive integers from the exact selected LUI2 publication bound to this Host intent |
| owner_thread / create_thread | Actual retained native owner thread, same positive value |
| created / shown / display_current | Actual native snapshot booleans, all True |
| draw_epoch / draw_sequence | Same exact selected display_epoch/display_sequence |
| panel | Native endpoint's retained actual panel handle/token, never a queued intent |

The endpoint must prove the current Host/selection/ui_epoch → exact native
selected display publication plus retained process/thread association. Merely
copying intent fields into a receipt, authenticating the pipe, receiving LUI2,
seeing OwnerProcessed for Checkpoint, or returning a non-None token does not do
that. The server rechecks current authority before acceptance and every command;
the native endpoint must also refuse stale binding and stale display snapshots.
`display_sequence` is distinct from the OPEN request sequence. The panel worker
confirmed its `draw_sequence` is the LUI2 model sequence, not the OPEN sequence.

The native panel worker is producing `local-ui-panel-owner-v3`: its source-owned
`local_ui_panel::OpenIntent` has a private constructor and grants production
friend access only to `local_ui_selected_open::Bridge`, which remains absent.
Its `Panel.RequestOpen` admits Pending/Busy/Unbound/Revoked/Invalid/AlreadyAttempted;
its actual owner-thread Snapshot retains intent_sequence/intent_epoch, created,
shown, create_thread, draw_epoch/draw_sequence/display_current, and close proof.
This primitive alone cannot produce the required server receipt or mapping.
The final immutable v3 artifact/hash is to be supplied by main; no live worker
file is selected or pinned as a completed consumer here.

`revoke_open` revokes native admission and arranges owner-thread close for the
same exact request. Its return value proves neither close nor destruction. This
candidate deliberately keeps `native_close=UNKNOWN`; it has no CLOSE receipt
acceptor, no port reset and no new selection/scope native-owner allocator.
Fresh configuration retains the old OpenPort and therefore refuses new OPEN
after any attempt. A coherent successor needs actual native close evidence and
source-owned successor allocation; silently making a new OpenPort is forbidden.

Only after actual OPEN can the Host pass the panel to its existing render and
settings command paths. The endpoint does not implement settings events or
mode/gear/inventory/save/basic-combat business actions. Their existing authority
contracts and separate owner paths remain required. Attack magic is later work.

First integration blocker: select and implement the real
`local_ui_selected_open::Bridge` plus paired `NativeOpenEndpoint`, immutable
source capture and Host-to-display binding/actual receipt transport. Next are
coherent Factory/Plan/scope integration, real interface render/command/close,
settings business owners, and Test-owned executable scenario/RUN. These are not
satisfied by this candidate's 186-row source-loader graph.
