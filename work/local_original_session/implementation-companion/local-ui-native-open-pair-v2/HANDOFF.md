# COMPANION-MAGE LOP1 original deadline correction v2

WRITER_RELEASED / source_ready=false / test_ready=false / ui_ready=false /
runtime_ready=false / RUN_COMMAND=null / resources0. New private v2 only;
v1 manifest18ef8ec9 and every v1 byte remain unchanged. v1 is unqueued history.

Python SelectedOpenTransport.poll checks original absolute self.deadline immediately
after actual ACK return, clamps phase deadline to min(self.deadline, now+30),
and aborts on doubt. Its authenticated-current override also rechecks original
deadline after inherited owner/pipe checks. ACK/receipt/reread never rearms time.
Native Run refuses zero/expired inherited State.deadline before admission and
only shortens a longer bound to30s. Exchange still never changes State.deadline.
The normal bootstrap starts its existing10s bound; v2 consumes remaining time.

Four focused actual OS cases, real clocks: unchanged positive LOP1 pipe/native
production Bridge/owner CreateWindow/NOACTIVATE/GDI/actual128B receipt/close passes
13 native checks including inherited deadline equality. Three deadline negatives
use disposable retained process+Job, original private bootstrap artifact/DACL/
capability/pipe PID/birth checks and native bootstrap. (1) ACK write succeeds,
then150ms OS delay consumes issuer100ms original bound; post-ACK check aborts.
(2) ACK write delayed10.15s causes native bootstrap Deadline before PostAck.
(3) test-only inherited shortening100ms plus150ms OS delay before Run yields
Deadline unchanged, no publication/panel. All negatives have OPEN0/receipt0,
retained native state0 and COMPLETE issuer cleanup. The owner record is an
explicit isolated harness, not product NativeOwner/Host/Player/lease/Factory proof.
Its issued-pipe latch models original bind_broker; first omitted-latch fixture
refusal is preserved in harness-first-failure.json. Product source unchanged.

V1 malformed/partial/disconnect evidence is reused by exact unchanged source pins,
not rerun or counted as v2 checks. No unchanged panel/binary/cohort copied; native
header references immutable v1 panel and v4 display. MSVC x64 C++17 /W4 /WX builds
two small isolated EXEs; no DLL link/load. Current blockers remain exact Factory/
Plan/launcher/native lifecycle/NativeInput pair selection, real first row-checkpoint
binding and Host acceptance, command/render/close/scope successor, settings/save.
Before first click no checkpoint binding is guaranteed; missing binding retains
refusal/UNKNOWN without synthetic capture/reset. Attack magic remains later.

Existing LUI2, Host4F13/emptyS2C, F101/SHOP ABI, original/common/queue/ACTIVE/Store/
ports/user input untouched. No game/Test/runtime graph run. Manifest has only
lower-case ui_ready, no case-colliding UI_ready key. PowerShell JSON parse checked.
After final only verify_readonly.py may run: reads/hashes/in-memory Python compile,
recorded evidence/exact diff checks; never native/build/regeneration/bytecode or
parent mutating verifier. Main owns review/selection/queue.
