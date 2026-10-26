# COMPANION-MAGE combined native transport/mailbox lower layer v1

WRITER_RELEASED / source_ready:true **combined independent lower layer only** / test_ready:false / UI_ready:false / game_runtime:UNRUN / panel_runtime:UNRUN.

Only this new private directory was written. Existing main dirty checkout, unrelated tracked changes, original/common/Test/queue/ACTIVE files and both reviewed parents are preserved. No branch/worktree/commit, game launch, production DLL link/load, game port, focus or input action occurred. Main retains final review, selection and queue ownership. This worker owns no remaining execution resources.

## Exact parents and composition

- `../local-ui-post-auth-transport-v1/manifest.json`: SHA256 **3f7a72b248259f19e34e16fb70d2b9b3dc4a8cd995a8334d17c79974323e3077**, exact authenticated pipe REQUEST_MODEL -> UNBOUND/actions0 transport.
- `../local-native-ui-owner-mailbox-v1/manifest.json`: SHA256 **92ae28a78af8d80d27719bd787736a22b73f04f188f760bdb69625d58433aeb3**, exact owner message-only HWND/Checkpoint dispatcher and close-before-unhook adapter.

`parent-pins.json` pins 54 unique parent manifests/source/evidence files. `input-pins.json` pins 124 unique inherited inputs with absolute paths, SHA256 and lengths. Both files were checked against actual bytes. `diff.patch` shows the production delta from transport; `diff-from-mailbox.patch` shows the delta from mailbox. Diagnostic/build only retarget private include/output paths. Compiler sourceDependencies confirms the single production TU actually selects this directory's transport, bootstrap, IO lifecycle, mailbox, host lifecycle, forwarding header and ABI bridge.

All transport/issuer files are byte-identical to the reviewed transport parent: `ui_transport.hpp`, `ui_bootstrap.hpp`, `ui_io_lifecycle.hpp`, `local_ui_channel.py`, `launcher_descendant.py`, `abi_bridge_v2.cpp`, `bridge.def` and the reused transport harness. All mailbox integration files are byte-identical to the reviewed mailbox parent: `ui_owner_mailbox.hpp`, `auto_ok.hpp`, `host_entry.hpp` and `host_lifetime.hpp`. No merged production algorithm was rewritten.

Original ABI/F101 sender remains exact. All 16 original forwarding branches preserve captured hook/code/remove/raw/CallNextHookEx and only use the reviewed BeforeUnhook adapter. That adapter revokes mailbox admission and performs owner close immediately before the original UnhookWindowsHookEx. The bootstrap/IO worker stays one attempt, retained handles/state/OVERLAPPED and cancellation/unknown completion lifetime remain original, and owner Join0/nonowner2000ms remains unchanged. Failed/absent native destroy or unknown IO drain remains retained UNKNOWN, never a fabricated close receipt.

## Two independent channels

Transport remains the same authenticated retained-process pipe, bounded stop-and-wait REQUEST_MODEL, fixed atomic UNBOUND snapshot, actions0, 16 requests and absolute30s lifetime. Its snapshot carries neither selected Host authority nor a panel model. No bridge binds it to the mailbox.

Mailbox remains one bounded immutable Checkpoint request with its own private message-only native owner endpoint, sequence, dispatcher receipts and native owner close. A Checkpoint receipt means only that the owner consumed that independent request. Dispatcher Created/Closed are never panel OPEN/CLOSE. Neither transport authentication/UNBOUND nor Checkpoint processing reports interface.open/interface.close success. No selected Host action, game opcode or callback authority was introduced.

Still missing: actual selected Host registration under the canonical Broker row operation; selected model/generation/revision/epoch authority; coherent panel pending/open/render/destroy/drain; selected lifecycle/API results and a normal game caller/RUN. These stay UNIMPLEMENTED/UNKNOWN. This combined lower layer cannot make a runtime-ready SKU by itself.

## Actual verification and reproduction

From project root:

1. `cmd /c work\local_original_session\implementation-companion\local-ui-native-transport-mailbox-v1\build.cmd`: PASS, MSVC x64 production TU `/c /std:c++17 /W4 /WX`, compile only.
2. `cmd /c work\local_original_session\implementation-companion\local-ui-native-transport-mailbox-v1\build_helper.cmd`: PASS, standalone native executable `/W4 /WX`, user32.lib. No production DLL is linked or loaded.
3. `python -B work/local_original_session/implementation-companion/local-ui-native-transport-mailbox-v1/check_combined.py`: PASS, two new isolated real retained process/Job/named-pipe cases using this directory's exact issuer and both native headers concurrently.
   - `valid`: real authentication, two REQUEST_MODEL/UNBOUND roundtrips; separate worker publishes immutable Checkpoint42 while transport is authenticated; genuine owner hook/message loop records OwnerProcessed; actual owner DestroyWindow/WM_NCDESTROY/depth0 receipt precedes local hook unhook.
   - `cancel-pending-model`: real authentication, no issuer model response; independent Checkpoint42 is processed while transport is authenticated, then cancellation exits the native session and the owner closes the dispatcher before unhook. Native snapshot sequence stays0; no model or Host success is inferred.
   Both report result Cancelled1, retained0/authenticated0/post_request0, dispatcher checkpoint1/closed1/coexist1, two genuine local owner callbacks, cleanup COMPLETE, Host invocations0. Owned helper threads join, child processes are waited on, retained process/Job handles and issuer artifacts are cleaned. The harness has bounded child cleanup; no timeout occurred.
4. `python -B work/local_original_session/implementation-companion/local-ui-native-transport-mailbox-v1/prepare_artifacts.py`, then `python -B work/local_original_session/implementation-companion/local-ui-native-transport-mailbox-v1/verify.py`: PASS, 215 pin/source/recorded-evidence checks. The pin generator only writes this private directory. It checks the exact parent manifests before generating review artifacts. The verifier confirms exact per-parent production bytes, original forwarding/F101 preservation, actual compiler selection, clean logs and the two combined OS results.

Unchanged scope reuses the exact pinned previous 13 transport OS cases and four mailbox native cases (86 checks); none was rerun. Unknown IO drain, native destroy failure and indefinitely absent owner were not induced as OS PASS results. The new isolated local callbacks do not execute original game callbacks, nor prove game scheduling, UI visuals/input, selected Host/model or panel OPEN/CLOSE.

`RUN_COMMAND:null` for game execution. `isolated-verification.json`, `verification.json`, build logs and compiler dependencies hold the actual bounded results. Main reviews/queues the private combined source; no common selection or queue item was edited here. WRITER_RELEASED.
