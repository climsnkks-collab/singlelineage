# LOP1 paired OPEN candidate

This new phase is explicitly selected **instead of** existing LUI2; it does not
reuse a pipe after another Session has closed and never adds a second reader.
Current LUI2 Session actually waits after DISPLAY_MODEL until its original
30s/cancel/disconnect boundary and rejects unsolicited bytes. That behavior is
unchanged and is recorded by three actual isolated rejection cases.

Native bootstrap still authenticates the same retained server PID/birth and
client pipe. Candidate Python issuer inherits the unchanged real launcher owner,
process handle/birth/Job, private logon DACL and exact broker binding checks. Its
new SelectedOpenTransport is a distinct concrete type. Factory/launcher must
select it and native local_ui_open_transport::Run together before bootstrap.
Neither side is selected in the current graph. There is no live LUI2-to-LOP1
conversion, reauthentication, second capability, reconnect, suffix retry or reset.

The existing broker row checkpoint alone captures source-backed Host/writer/row,
selection/direct lease/companion lease, actual PlayerRegistration actor UID and
generation, UI epoch, pipe, NativeOwner/child/handle/Job and resource lifetimes.
Endpoint submit/read only consume that identity-retained record and the exact
Host OpenIntent; they do not call back into Host or acquire/reenter the row.
Host OpenPort still performs its own live current checks before/after acceptance.
Queued is PENDING; row_checkpoint separately recaptures current state, performs
original prewrite/postwrite owner checks and makes one whole write attempt.

LOP1 envelope is fixed1152 bytes: standard little-endian16-byte header
(magic LOP1/version1/kind1/flags0/open sequence1/body1136), random32-byte
correlation, display sequence1 u32 at48, zero bytes52..127, exact existing
LUI2 DISPLAY_MODEL1024 at128. Sequence domains are distinct even though both
currently start at1. Server authorities stay as Python object identities; the
random value is a per-channel record correlation, never authority to select a
character or replace a lease. Only one OPEN slot is used, within16; no automatic
refresh is provided. Lifetime remains <=30s, display retention250ms.

Native production Bridge owns the sole private OpenIntent constructor access.
Worker admits one exact envelope to fixed storage and publishes its parsed
LUI2 display. Genuine established native owner observes that exact publication,
binds original parent HWND and enqueues Panel.RequestOpen(Pending). Actual owner
CreateWindowEx/NOACTIVATE/ShowWindow and WM_PAINT/GDI/EndPaint must complete before
worker can encode the actual Snapshot. It binds native epoch, display sequence,
owner/create thread, actual process and actual HWND; a two-line Panel descendant
adds the real created HWND to its existing snapshot. No test intent factory is
compiled into this candidate. Native UI controls remain disabled.

Native LOR1 receipt is fixed128 bytes: magic LOR1/version1/kind2/flags0/open
sequence1/body112, exact correlation32, owner/create/PID/actual flags7 at48,
native epoch/draw epoch u64 at64, display/draw sequence u32 at80, actual HWND
u64 at88, zero96..127. Server consumes only exact correlated actual bytes and
can construct its exact nominal NativeOpenReceipt retaining the same OpenIntent.
Receipt reads require live original owner/pipe/current binding and conservative
server send-time+250ms bound; cached reads never refresh that bound. This is a
finite actual native snapshot, not a proof that a window cannot subsequently
close between asynchronous observations. Mode/settings transport remains
unselected; no gameplay command is enabled by this artifact.

Cancel, broken/partial/duplicate/invalid delivery or stale binding burns the
single attempt. Server revocation closes only its channel and retains all
intent/evidence with native_close UNKNOWN. Native Run's terminal guard revokes
publication and panel admission; genuine owner callbacks alone perform DestroyWindow
and WM_NCDESTROY/callback drain. No native CLOSE receipt is accepted by Host.
A successor scope cannot reset this port or reopen after UNKNOWN.

Exchange(State&) does not change State.deadline and can precede a separately
selected command phase on the same original State and remaining lifetime. Run is
a standalone exclusive OPEN session wrapper; it starts the one post-ACK30s bound
and keeps publication admission while receipt is consumed. A future combined
phase orchestrator must own terminal revocation across all phases. Existing
command-wire-v1 is not invoked or selected here. No new game packet or S2C exists.

First remaining blocker: coherent source-selected Factory/Plan/native lifecycle
and launcher must install this distinct pair, its owner OnOwner call and exact
source seals. Current LUI2 NativeInput points at the previous binary; no new DLL
is linked/loaded here. Host interface render/command/close, real settings/save,
scope successor and Test-owned scenario/RUN remain unfinished. Attack magic is
later work. This candidate is not product source_ready/test_ready/UI_ready.
