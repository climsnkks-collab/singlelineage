# COMPANION-MAGE private LOP1 native linked candidate v1

WRITER_RELEASED / resources0. `source_ready:false`, `test_ready:false`, `ui_ready:false`,
`runtime_ready:false`, `RUN_COMMAND:null`. The private x64 DLL actually links; it has
not been loaded. No game, game ports, Store, user input, focus, original/common/Test,
queue, ACTIVE or Git changes. Existing unrelated dirty main checkout is preserved.

The selected SHOP `shop-dispatcher-gate-v19/native394` original native ABI and
`local-ui-native-lui2-linked-v1` adaptation precedent are retained. Diagnostic source
inverts to exact SHOP source; auto_ok inverts to exact original including all 17
Forward paths; ABI source/F101 is byte-identical to the LUI2 precedent. All four
linked object/library inputs are unchanged. Actual MSVC x64 C++17 /fp:strict /W4 /WX
compile and /WX /INCREMENTAL:NO link exit0 produced
`own-login-bridge-companion-lop1-v1.dll`. Static PE comparison verifies AMD64 PE32+
DLL, all 27 original exports and ordinals, and every original SHOP import preserved.
The compiler graph preserves all 333 original include paths except the same two
explicit private source adapters. Full compiler/source/library/toolchain hashes
and actual sourceDependencies are in build-receipt/ledgers.

This candidate changes the one existing IO lifecycle's post-ACK phase from LUI2
Run to LOP1 Run. There is no second reader, reconnect, command composition, mode
selection or Host OPEN fabrication. Corrected v2 Bridge/Exchange/Run is byte-exact
after inverse removal of one owner-wake include/call. Original bootstrap's absolute
deadline is inherited unchanged or shortened only; ACK/receipt never rearms time.
Immutable v1 owner panel and v4 publication/bootstrap/display remain exact external
compiler inputs. Existing owner hook/current sender and off-thread retirement stay
in place; the panel has no command/settings authority and its controls are disabled.

The concrete new wake is one Checkpoint publish to the already-established private
message-only mailbox immediately after valid LOP1 publication. It uses existing
PostMessageW, no pointer/model/input/UID/Host payload, retry, focus or second pipe.
Actual mailbox WM_APP dispatch invokes PanelCheckpoint outside the mailbox lock;
production checks the original established owner and invokes Bridge.OnOwner using
the original game HWND/terminal state. Genuine WH_GETMESSAGE ticks also service
it. Close/Selected/Finish revoke off-thread without panel User32/GDI; terminal
mailbox/owner callback and original BeforeUnhook close on the owner. Existing
native panel timer drains expiry/phase revoke. Module/code stays pinned on unknown
join/close; no unload or timeout-to-CLOSED claim. Scheduling cannot guarantee a
250ms callback: a late/absent callback still refuses expired display, never extends it.

Two bounded new isolated actual OS checks, no DLL/game loading:

- Message-only checkpoint delivery: actual owner callback1, elapsed0ms, no OPEN,
  actual mailbox CLOSED, activation unchanged, desktop/thread resources released.
- New LOP1 Admit integration: explicit isolated envelope made from the exact v2
  display fixture, worker Admit -> Publish -> actual WM_APP -> Bridge.OnOwner ->
  owner CreateWindow/ShowWindow(NOACTIVATE)/GDI WM_PAINT -> actual 128B LOR1 receipt
  in15ms. No manual Bridge.OnOwner tick. Callback2 is terminal close; actual panel
  CLOSED/destroy returned/NCDESTROY/callback drain and mailbox CLOSED, activation
  unchanged and all owned resources released. Result and receipt are preserved.

The isolated callback's owner/game fixture is not production NativeOwner/Host/
Factory/Plan/launcher/NativeInput selection or a clicked mage. Existing parent v2
deadline/pipe negatives and v1 malformed/partial/disconnect tests are reused by
pins; no prior mutating verifier or unchanged runtime checks were rerun. Product
OPEN/panel/game runtime remains UNRUN. Actual selected NativeInput/launcher/Host,
first checkpoint/caller, command/settings/save and source admission remain open.
Another worker's OPEN->command composition is not selected by this LOP1-only DLL.

`prepare_private.py` and build scripts are development writers. `finalize_once.py`
writes receipts once and refuses a finalized candidate. After finalization use only:

    python -B work/local_original_session/implementation-companion/local-ui-lop1-native-linked-v1/verify_readonly.py

It only reads/hashes/recomputes deterministic static evidence, checks full file
coverage, and verifies all private file bytes/mtimes are unchanged. It never builds,
loads, runs a native check, calls a parent verifier or rewrites reports. Main owns
review/selection/queue. WRITER_RELEASED.
