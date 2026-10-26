# COMPANION-MAGE command wire v2 — original absolute deadline

WRITER_RELEASED. Corrects main's concrete v1 review finding. v1 manifest
`f0d5f95061b40905a82384c883ce6ce7496d14df93ad577c423692ce7d91b7d7`
and all v1 files stay immutable. Existing dirty main and original/common/Test/
queue/ACTIVE files preserved. This worker writes only new private v2; no
branch/worktree/commit, game, DLL, ports, focus/input, Host dispatch or Store save.

v1's independent issuer granted a fresh30s after ACK while ignoring the original
post-resume activation deadline. Its isolated helper also granted a fresh native
deadline after ACK. Although production Session itself never changed State's
deadline, those wrappers could extend the original lifetime. v2 removes that
inconsistency and does not claim v1 satisfied the inherited-deadline contract.

Python command deadline is now `min(original self.deadline, now+30s)`. Every
current check requires the inherited deadline to remain present and command
deadline no later than it. The same authentication tick immediately rechecks
current/deadline after original ACK delivery; an ACK crossing the original
deadline aborts before command bytes are consumed. Original issue/activation/
retained process/handle/PID/birth/Job/key/capability and before-activation refusal
are inherited unchanged. No retry, new capability, reset or adopt API is added.

Native production Session is referenced byte-for-byte from v1 and already does
not change State.deadline. v2 helper now preserves the original bootstrap
absolute deadline through ACK and Session. Only the focused native-deadline
fixture shortens it with a minimum; it never extends it. Every executed PostAck
records no extension and no deadline change inside Session. Compiler dependency
evidence selects exact v1 transport/bootstrap, with no copied unchanged headers,
binaries or cohort graph. The new helper remains an isolated executable.

17 actual isolated retained-process/Job/pipe cases PASS: v1's15 relevant positive
and negative wire cases, plus two delayed ACK cases. Issuer-side test advances
the injected monotonic clock to the original absolute deadline immediately after
real ACK WriteFile succeeds: COMMAND_WIRE_DEADLINE, command frames0/receipts0,
native Refused. Native-side test delays the real ACK for10.15s, beyond the
unchanged native bootstrap10s deadline: native Deadline before PostAck, no
command Session/frames/receipts, cancelled read drained and retained0. This real
wait does not alter OS clocks or production timing. No caller treats native
timeout as successful UI cleanup. Exact per-case first error/cleanup are saved.

Cross-language positive/fragmented cases still use the frozen mode-route-v1
Python codec's exact92B request/96B UNKNOWN response and native CNG HMAC checks.
Actual saved outcomes0 and Host dispatches0. Unknown completion retention is
unchanged and was not forcibly induced. All owned helpers/Jobs/pipes/artifacts
closed. MSVC x64 /std:c++17 /W4 /WX compile/link PASS.

This is still an independent lower-layer primitive, not a selected endpoint or
combined OPEN/mode transport. A separately selected LOP1 predecessor must provide
genuine actual OPEN/current Host→native mapping and a same-State continuation
with only its original remaining deadline. Fresh key delivery, actual owner
consumer/ready receipt, NativeModeEndpoint, immutable Factory/launcher phase
selection and event-loop caller remain unimplemented here. The exact frozen
v1 PAIRED_TRANSPORT.md installation points still apply except its fresh30s
standalone/helper descriptions, explicitly superseded by this correction.

primitive_source_ready:true only; feature/source/test/UI/runtime readiness all
false, RUN_COMMAND:null, game_runtime:UNRUN. This is not a reusable settings UI.

Explicit mutating own-output build/check commands (not a game RUN):

    cmd /c work\local_original_session\implementation-companion\local-ui-command-wire-v2\build.cmd
    python -B work/local_original_session/implementation-companion/local-ui-command-wire-v2/check_transport.py

Post-final read-only verifier:

    python -B work/local_original_session/implementation-companion/local-ui-command-wire-v2/verify_readonly.py

Finalizer is one-time only. Exact parents/outputs/diff and evidence pins are in
parent-pins.json/manifest.json; v1 and all pinned parents retain hashes+mtimes.
Resources0 / WRITER_RELEASED.
