# COMPANION-MAGE — native owner close v2 inspection

CONTRACT_UNSUPPLIED / source_ready:false / test_ready:false / implementation_complete:false / runtime:UNRUN / WRITER_RELEASED.

This is the requested bounded source inspection, not a replacement hotkey build. Only this new private directory was written. Parent host/package, common/original/Test/queue/ACTIVE, processes, DLL loading, ports, focus, input and saved data were untouched. No C++ implementation, new export, message, callback, acknowledgement, timer, release or runtime command is supplied.

## Result and first missing contract

The actual selected composite has a genuine owner UI callback, `AutoOkGetMessage`, installed by `InstallAutoOkHook` using `choice.thread`. Existing `BeforeUi`/`AfterUi` calls already revoke and close on that owner callback. Normal SourceQuit's final successful approval sets `manual_move::sourceQuitTerminal`; its native original path and terminal handling are preserved. This does not provide a callback after the owner loop has stopped or after its `autoOkHook` has been detached.

The first missing caller is the **lifecycle owner that invokes `OwnLoginFinishAfterCallbacksJoined` while an owner UI dispatch opportunity still exists, joins that owner-thread hotkey closure, and only then completes teardown**. The selected bridge exports this void function at existing ordinal 9, but its body merely calls `Revoke(true)` then the original `FinishAfterOriginalCallbacksJoined(scope.caller)`. There is no selected caller providing an owner dispatch/join, no owner-close receipt, and no result channel on that existing export. Searching the selected host, the local orchestration directory and companion sources found definitions/references, not such a caller. This finding is scoped to the inspected sources; it does not prove absence from every shipped native binary.

The original `caller.cpp` explicitly assumes borrowed hooks are already unregistered and original tasks/callbacks have joined. Its `FinishAfterOriginalCallbacksJoined` cancels caller bookkeeping and releases its socket/network Pair references. Its name and lock do not establish that the companion WH_GETMESSAGE callback ran or joined. Invoking this existing function cannot be used as a fabricated close acknowledgement.

## Exact existing chain

- `local-native-hotkey-host-v1/auto_ok.hpp`: `AutoOkGetMessage` -> existing `BeforeUi`; sixteen existing branches -> `AfterUi` -> original `manual_move::Forward`. `InstallAutoOkHook` records the owner UI thread/window and installs the WH_GETMESSAGE callback.
- `local-native-hotkey-host-v1/host_lifetime.hpp`: nonowner `Revoke` only publishes revoked/invalidated/finished under the short publication lock; it intentionally does not call User32 or touch UI-only Sender storage. `AfterUi` rejects a nonowner/reentrant caller. `Stop` requires `CloseResult::Closed` and `Sender::Retire()` before destroying Sender.
- `local-native-world-current-attempt-v2/local_foreground_hotkey.hpp`: `Close` returns `WrongOwnerThread` when an owner exists on another thread; callback reentry returns `DrainPending` or `UnhookFailed`. A successful unhook clears binding/owner state under its lifetime lock. The module is pinned for process lifetime by Install; successful Close does not unpin it.
- `local-native-world-current-attempt-v2/current_attempt.hpp`: Sender retirement requires no active original send attempt. It expressly does not prove original queued clone drain.
- `item-reference-repeat-native-composite-v1/native/manual_move.hpp`: `DetachTerminal` can remove the actual owner dispatch hook at a quiescent Forward boundary. `Forward` preserves CallNextHookEx. It supplies no future dispatch guarantee or join receipt.
- `item-reference-repeat-native-composite-v1/native/source_quit.hpp`: the real SourceQuit command is authenticated/sequenced and phase-specific. Its existing request and `RETURNED` output describe that original action, not companion closure. Reusing that message merely as a wake-up would misrepresent its contract.

## Required next source input

Supply the real teardown caller path/function and exact parent SHA; its source-backed owner scheduling/join mechanism; lifetime order relative to the final owner callback and original borrowed callback join; and how the owner observes actual `Closed` plus inactive Sender while preserving failed-unhook/reentrant pending results. It must also cover an absent/stopped owner loop explicitly. A void Finish export, a posted message, timeout expiry, process exit, SourceQuit RETURNED or original send return alone cannot establish that receipt. Native queued clone drain remains its own original contract.

Until that input exists, nonowner Finish with no later natural owner callback remains revoked/pending with resident storage until process teardown. It is not Closed, and the package must not be unloaded/reused on that claim. Parent host/package source and export ABI therefore remain byte-identical; no partial source implementation was introduced. Direct packet Test remains independent and is not gated by this missing native UI lifecycle contract.

## Pins, changes and verification

`source-pins.json` records exact SHA256/size for both parent manifests, relevant host/package sources, the current-attempt hotkey/sender and original caller/manual_move/SourceQuit sources. Parent host manifest SHA256 is `059463a3f25842448abfbe04089713574c0329c590aa27a715e7060a0a47d67e`. Package SHA is recorded directly rather than inferred from its DLL hash. Repository HEAD at inspection: `f599fd7af903e0724999fff110601c8a724d52f0`; the existing main dirty checkout was preserved.

Changes: inspection HANDOFF, exact source pins, bounded verification and manifest only. No product diff. Focused verification rehashed every source pin after the report and checked the actual selected source chain. Compile/link were not repeated because there is no C++ delta; the parent's recorded object/package checks are reused without expanding their PASS scope. Runtime owner closure remains UNKNOWN/UNRUN. No new test system, enqueue, root/Test notification or resource ownership was created. Writer released.
