# LMC1/LMA1 independent wire primitive

This is a lower-layer implementation, not NativeModeEndpoint, a selected channel,
a native enabled control, or an actual Host command producer. Fixtures are not
Host authority. Feature/selected source_ready:false, test_ready:false,
UI_ready:false, runtime_ready:false, RUN_COMMAND:null; game runtime UNRUN.

The exact frozen format is owned by mode-route-v1 PAIRED_COMMAND_CONTRACT.md.
This artifact implements exactly its 92-byte LMC1 and96-byte LMA1, HMAC domain
`LOCAL-COMPANION-MODE-V1\0COMMAND\0` / `...\0ACK\0`, one sequence1,
distinct OPEN/display sequences, and reserved/padding rules. UNKNOWN carries
zero before/after/mode. SAVED permits unchanged revision for an idempotent
Store save or exactly+1 for a change. Parsing a SAVED frame never proves Store
or native display success. Tests send UNKNOWN only. Codec SAVED shape checks
do not claim actual saved outcomes.

`command_transport.py::CommandTransport` inherits the exact pinned original
LocalUiChannel. It does not override issue, activate_post_resume, _current,
or original admission. Each isolated attempt actually issues a fresh first-instance
local-only logon-SID-protected pipe/bootstrap, retains actual handle/PID/birth/Job
and key guard, activates once, consumes one capability, and admits command bytes
only after the real native ACK. There is one absolute30s command budget starting
at ACK, not refreshed by activity. `_wire_current` rechecks actual retained owner
and pipe client PID before bytes leave or are exposed. Fixed receive storage is
93 bytes to refuse observed excess; after the sole request, any observed extra
byte revokes. A byte pipe cannot prove the issuance time of bytes which are not
yet observable, so this remains a semantic one-request/no-pipeline contract.
`take_frame` yields authenticated immutable bytes exactly once; it cannot yield
a Host Request/Binding or dispatch. `publish_receipt` takes externally supplied
signed bytes and validates them; there is no generated success reply. Partial
NOWAIT writes retain the exact suffix, without reissuing an action. Invalid,
duplicate or uncertain receipt publication burns the channel. Close revokes,
zeros its key buffer, removes only its own artifacts and cannot reissue.
Python immutable copies/returned bytes follow normal interpreter lifetime;
the key never comes from or reuses the bootstrap capability and is not logged.

`ui_command_wire.hpp::Session` is a separately selected mutually exclusive
post-ACK phase, never a second reader of running LUI2. It validates CNG
HMAC-SHA256 and exact expected binding, sends one92-byte command, receives and
reassembles exactly96-byte receipt, validates current server process/birth and
MAC/fields, refuses observed extra receipt bytes, and returns verified bytes.
It never changes State.deadline. Every I/O uses unchanged ui_bootstrap::Io,
its retained heap OVERLAPPED/buffer/event, cancellation and2s completion drain.
Unknown completion retains original State through the original Run; this path
was not forcibly induced or called PASS. No panel, Host, callback, window
message, retry, reconnect, automatic refresh or successor allocation is added.
The explicit native inputs and Python FixtureBinding are test/lower-layer
values; they do not attest a genuine UI binding. Production has no caller.

The helper is an isolated EXE, not a DLL/NativeInput selection. Only its PostAck
establishes an initial standalone command deadline once (30s or100ms test).
Production Session has no deadline setter. A future LOP1 continuation must keep
the same retained State and its original remaining deadline, without running
that helper setup. Independent CommandTransport is not an adopt/resume API for
a LOP1 issuer, and cannot move another issuer's handles/capability.

## Narrow exact installation points and remaining blocker

1. Original selected issuer `local-ui-selected-model-pair-v2/local_ui_channel.py`
   `bind_broker` (394), `_authenticated_current` (411), `_capture_locked` (458)
   already prove the genuine retained NativeOwner and current canonical Host row.
   Preserve its exact NativeOwner/PersistentBroker/LocalRealm/_TransportPolicy,
   original guard methods, handle/Job and row-task predicates. The capture
   returns exact selected state/direct/companion lease/actor generation/ui_epoch
   and issued pipe references; a display capture alone does not authorize OPEN.
   Reuse those predicates in a new immutable phase owner, not a new numeric UID
   authority or public caller boolean.
2. `local-ui-click-open-bridge-v1/companion_local_open.py` `require_open_locked`
   (210) must first return the real actual panel for its retained issued attempt.
   `local-ui-mode-command-route-v1/companion_local_mode.py` `bind_locked` (170)
   then captures the actual intent/panel/display epoch and canonical revision,
   generating fresh token16/key32. This exact source route is supplied by that
   owner; this wire artifact neither calls nor substitutes for it.
3. The OPEN worker's new LOP1 is a separate candidate. A future selected paired
   continuation must invoke command Session **inside the one original PostAck
   lifetime before it returns/deletes State**, after its real actual OPEN
   receipt, on the same pipe with no second reader and the same remaining budget.
   A genuinely selected issuer phase must retain the original pipe owner and
   current row; this standalone issuer cannot simply replace or adopt it.
4. The missing selected NativeModeEndpoint must deliver the fresh key/token and
   exact actual OPEN mapping to the retained owner command consumer using a new
   explicitly versioned protected binding exchange. No such envelope, consumer
   installation, key-delivery/ready receipt, or producer is supplied here. Do
   not take FixtureBinding, passing HMAC, panel Snapshot flags or an LUI2 model
   as this proof. Native v4 controls stay disabled. No production code enables
   or handles a mode button, and absent `local_ui_selected_open::Bridge` in v4
   still cannot be constructed by this file.
5. Only that proven endpoint may expose exact NativeModeReady/NativeModeFrame
   to mode-route-v1 `receive_once` (208), outside the original Host row. The
   route invokes the original Host command once and generates its Store-backed
   response. This transport only carries that response once; delivery is not
   save/renderer/close success. Revoke must disable actual native consumer and
   preserve UNKNOWN; full native destruction/drain and fresh scope successor
   remain outside this primitive.

Existing LUI2 sources, linked DLL/NativeInput association, 30s/16 request limit,
display retention, panel epoch/revoke/close semantics and selection are unchanged.
No current LUI2 Session is switched midflight; unsolicited LMC bytes still fail
closed there. This one-action primitive is not a reusable settings UI. Actual
product command dispatch remains blocked until the above endpoint/current
binding and phase selection are complete; no command is dispatched here.
