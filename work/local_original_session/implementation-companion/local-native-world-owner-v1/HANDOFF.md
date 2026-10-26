# COMPANION-MAGE — native current WORLD owner audit

2026-10-24. SOURCE_ONLY. implementation_complete:false. test_ready:false. runtime:UNRUN. WRITER_RELEASED.

## Result

The supplied source does **not** justify implementing `WorldOwner.with_current`. No adapter, permissive fallback, provider stub, new epoch, hook, raw frame, or product modification was written. The existing empty builder remains unchanged and its external authority remains unimplemented. actual125's one direct F101 / one real 4E96 actor UID is independent packet evidence, not native hotkey success.

The first missing interface is an actual native current-owner borrow/serialization boundary: on the verified owner thread, acquire the genuine global-root NetworkSubsystem Pair and the same current WORLD/selected-character/manager/role0 connection, prevent their reselection/retirement from invalidating that association while the synchronous callback allocates, calls 27D620, and destroys its temporary, then release the borrow. Existing predicates can observe these pieces, but none of the supplied interfaces owns this combined boundary. `expected_epoch` has no supplied native producer; a local counter or character UID must not be inserted into that slot.

## Existing source that can be reused

Paths below are workspace-relative; `manifest.json` pins their exact bytes.

- `tools/local_original_session/native/command_bridge.hpp`: `Find(Pins,5)` retains the actual UI/state/scene/actor subsystem Pairs. `Stable` checks state+360 scene Pair, empty transitions+370/+378, kind5+380. `Handle` checks the registered UI thread and owned desktop. This establishes a genuine scene snapshot, not network/character ownership or exclusion of registry replacement during a callback.
- `tools/local_original_session/native/quit_command.hpp`: `Read`/`Same` tie root/registry/scene/window-owner thread snapshots together. `Prepare` explicitly releases strong references before the final borrowed proof; `Run` intentionally performs no object read or Held release after native Quit. This deliberate terminal-call design is not a callback-held WORLD lifetime interface and cannot be copied into a sender with post-call Message destruction.
- `integration-1/item-reference-repeat-native-composite-v1/native/use_item_binding.hpp`: `Registry` ties the same root/gi/vector and actual state/UI/actor Pairs to character subsystem vft1185340, selected player UID at +6D8, map Pair/context and inventory rows. `Capture`/`Current`/`Boundary` reuse original inventory/item getters and recheck immediately before original item command. Neither the registry reader nor strong references serialize native current network replacement or connection retirement.
- The same composite's `native/abi_bridge_v2.cpp`: actual qualified Selected entry uses root→`api.network` (3EC40) and compares the returned NetworkSubsystem object to the real argument. `BeginActualOwnSelected` retains it. `RetainOriginalRole0` locks the original manager+58 only for key0 tree lookup/retain, then unlocks. `ExactConnectedLocalPeer` checks socket+9 initialized, socket+10 handle, `getpeername` ==127.0.0.1:14030 and unchanged handle. These are useful source-backed predicates, not a held current-WORLD borrow. No extra handshake is requested.
- The same composite's `native/caller.cpp`: `Caller::lock` protects bridge bookkeeping. `AfterOriginalVersionCounts` releases it before original send and explicitly permits concurrent close according to original queue/socket semantics. `CancelAtOriginalSocketClose` changes only the bridge phase; original241990 still runs. `FinishAfterOriginalCallbacksJoined` assumes callbacks already joined. The file explicitly has no reset/reselection/reconnect API. Holding this bridge lock across the callback would neither prove every native producer/retirement path participates nor supply the missing native current epoch.

## Existing final REA contracts

REA290/291 establish original retained 3EC40 Pair, original zero-state Message New/Copy/Serialize/destroy and generic sender ABI. REA294 establishes sameT198 manager, queue consumer and retained connection callback; its lifecycle addendum explicitly leaves original manager ownership/worker retirement open. REA296 world3 connects E05E0 input owner+C0/C8→2784B0→owner+D0 registry install, but does not identify that input owner as global1668790/current WORLD or supply its producer/retirement boundary. REA305 source3 closes concrete connection vptr1198D90/virtual8=241A00 and serialization/framing/socket-shaped send; it leaves connected handle/current-WORLD production and retirement open.

The precise next source edge is the existing E05E0 input owner's C0/C8 Pair producer and normal global/current caller, together with the actual registry replacement/removal/connection retirement participation that can back the synchronous borrow. Reuse a real existing callback/owner interface if supplied; a snapshot retry, extra refcount, bridge SRW lock, root+D8 flag, window-thread identity, or local generation is not that interface.

REA307 `run307_empty_message_current_connection/source3/contract.md` was read only as **provisional, not a final accepted contract**. Its A zero-body/generic-F101 conclusions do not close B. It explicitly leaves actual virtual18 setup caller/connected endpoint and current owner/retirement open. Even if main accepts A, this audit's missing interface is unchanged.

## Focused verification and ownership

`manifest.json` records source SHA256/size and focused source-token observations; `verification.json` records that all pins were reread unchanged after writing this handoff and key source predicates were present. No C++ compile was run because no C++ implementation was authorized by the source audit. Compile success could not resolve a missing lifetime interface. No game, port, socket, hook installation, Test dispatch, shared file, queue, ACTIVE, original, or save writes were performed. Existing main dirty checkout and unrelated changes are preserved. Only this new private directory was written. Reader/writer released; parent may review the recorded gap and decide the next bounded source request.
