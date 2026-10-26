# COMPANION-MAGE LOCAL F101 empty native builder candidate v1

2026-10-24 KST. SOURCE_ONLY / COMPILE_CHECKED / WRITER_RELEASED. `test_ready:false`, `packet_test_gate:false`, native runtime UNRUN. Owned writes only this new private directory; shared/original/queue/Test files unchanged by this worker. Git `main...origin/main` reused; pre-existing dirty/untracked files preserved; branch/worktree/commit creation 0.

`local_native_f101_empty.hpp` is a bounded in-process C++ candidate: original New707830(nullptr,nullptr), original sender27D620(genuine held Pair.object, LOCAL 0xF101, actual Message*), deleting destructor7153F0(message,1). The object is opaque; no local allocation, vptr/schema/field writes, 0263 carrier/retag, manual Copy/Serialize, raw frame, cipher, socket, invented epoch, automatic hook install or game launch is present. No copied login Message layout is used.

## Source decision

REA291 sender3 supplies a real 24B no-declared-field native class, CS_CHAR_LIST_ENTER_REQ, not an F101 class/registration. New with RDX0 returns zero state; source+8 bit0-clear Copy74EC30 returns through74EC4B; zero-state Serialize74EB90 returns unchanged output through74EC00..08. Actual deleting destructor7153F0 is reused. This suffices for a **conditional compile-only carrier candidate**, not native opcode/consumer acceptance. Native virtual20 required/init is not selected. No new REA/provider query or binary analysis was performed.

REA290 sender supplies RCX=held NetworkSubsystem.object, EDX=opcode16, R8=real Message*, synchronous New/Copy clone into owning internal queue. This makes destruction of this caller-owned temporary after original send returns the relevant local cleanup. Queue clone disposal, exceptions/EH inside native queue, missing-role0 silent return, pop/serializer/framing/socket/partial write/drain remain unproved. `SenderReturned` means only the original function returned; `sender_called` includes unknown partial failure, never wire/server success.

REA291 world3's normal WORLD entry and skill callers share global RVA1668790/getter3EC40; global nonnull/+D8 and retained Pair storage do not authenticate a current WORLD, native epoch, owner thread, producer serialization or retirement. The login producer/caller was read as ABI/ownership precedent only; its login/selected/Connected phases and 0263 Message are not reused as WORLD authority.

## Mandatory unresolved external caller

No `WorldOwner::with_current` implementation or installed `SenderBinding` is supplied. Missing callback/ABI/game/thread/expected epoch fails before creation. The external current owner must synchronously validate the actual same authenticated selected WORLD and caller's real expected identity; run on the actual native owner thread; retain the genuine 3EC40 Pair; and keep current/retirement plus same-manager producer serialization protected through creation, send return and temporary destruction. Pair storage or LOCAL generation cannot substitute for these guarantees. Native owner installation/replacement/retirement and actual consumer/opcode/serializer compatibility remain the first blockers. Do not fill these with a global getter-only callback or permissive stub.

The existing foreground hook's `SenderBinding.try_send` can eventually call `Candidate::Try` and map `sender_called` to `OriginalSendAttempted`, otherwise `RefusedCurrent`. That adapter must preserve actual source-backed expected WORLD identity and real window/thread binding. This unit neither supplies the adapter nor changes/installs the hook. Its local thread equality check does not establish that this is the correct native owner thread. Hook's existing press/repeat gate remains the per-press input boundary. Candidate blocks nested calls, and suppresses repeated callback invocations within a single Try; separate later physical presses may make separate attempts. No retry is performed after a partial/exceptional attempt.

`Retire` only revokes this synchronous candidate and reports CallPending until its current borrow returns; it does not drain the native queue or socket. Candidate/context/API code must remain alive until Closed, and the integrator must serialize destruction against callers (e.g. existing hook Close/lifetime boundary). Context-bearing callbacks must not store/defer BorrowedCall. No asynchronous thread or native release/refcount implementation is invented.

## Focused verification

Run from repository root: `cmd /c work\local_original_session\implementation-companion\local-native-f101-empty-builder-v1\build_check.cmd`.

MSVC x64 `/std:c++17 /W4 /WX /EHsc` compiled successfully. `check.cpp` executes only control-flow doubles and an opaque undereferenced token, never a native Message/vptr: missing/current/thread refusal, owner-held create/send/destroy, duplicate callback once, recursive Busy, partial-send exception no retry, retire-during-create -> no send + destroy within borrow + CallPending/Closed. `verification.txt` records PASS. The C++ exception check is not native SEH/EH validation. It creates no HWND/hook/network/server/port/save; GetCurrentThreadId is used only for local caller equality.

Native F101 accepted by queue consumer/socket/server: UNKNOWN/UNRUN. Actual Ctrl+Shift+M, physical key press, foreground routing, client rendering, companion summon/AI: NOT VERIFIED. Independent normal direct F101 packet Test is not gated by this candidate. Main owns review and any queue registration; this worker did not enqueue or contact Test.
