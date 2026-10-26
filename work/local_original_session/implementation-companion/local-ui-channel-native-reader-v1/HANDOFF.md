# COMPANION-MAGE LOCAL native reader v1 — first lifecycle missing

LIFECYCLE_NOT_AVAILABLE / source_ready:false / test_ready:false / runtime:UNRUN / RUN_COMMAND:null / WRITER_RELEASED.

Only this new private directory was written. No common/original/Test/queue/ACTIVE edits, branch/worktree/commit, DLL load, game start, pipe connection, port, focus, input, native message or original sender invocation occurred. Existing dirty main and all original exports/hotkey/source remain unchanged. This is the explicitly permitted missing-lifecycle result, not a C++ reader implementation or runtime acceptance.

## Exact first missing contract

There is no selected game-side **non-UI bootstrap execution owner with a start/cancel/drain lifetime** in the pinned native package. Existing entry points are original forwarding callbacks and the WH_GETMESSAGE owner UI callback. File discovery/open/read, named-pipe open and handshake/ACK waiting cannot be inserted there while satisfying the requested no-blocking-owner-thread boundary. Moving those operations to a new worker would require selecting and implementing its actual startup, module retention, cancellation and IO-completion drain first. The supplied package has no such worker to reuse.

This is narrower than a missing selected Host/UI: a handshake-only client already needs this IO lifecycle. A pure parser could compile without it, but would not provide an actual safe reader/handshake caller and was not added as a substitute. No new DllMain, thread launch in forwarding, posted synthetic owner message, retry/poll hook, or unload/close success was invented.

## Source evidence

- `local-native-hotkey-package-v1/diagnostic.cpp:239` includes the existing ABI source, and line 250 includes the companion host lifetime; its six private alias substitutions preserve the parent implementation.
- `local-native-hotkey-package-v1/auto_ok.hpp:370` defines AutoOkGetMessage. BeforeUi/AfterUi execute inside the existing WH_GETMESSAGE callback and return through manual_move::Forward/CallNextHookEx. `InstallAutoOkHook` at line 487 selects the actual HWND/thread and installs this hook; it does not own any auxiliary IO worker.
- `local-native-hotkey-package-v1/host_lifetime.hpp:10` documents process-lifetime sender storage with no unload claim. AfterUi at line 50 is owner-thread-only. Revoke at line 22 only marks revoked/invalidated/finished under a short publication lock and deliberately avoids UI storage/User32. Stop at line 35 retires only the existing hotkey/sender. No auxiliary worker/cancel/completion state exists there.
- `local-native-hotkey-package-v1/abi_bridge_v2.cpp:443` preserves actual Close forwarding after Revoke. Finish at line 450 revokes and releases the existing caller after original callbacks have joined; it does not cancel or join a new reader thread. `integration-1/item-reference-repeat-native-composite-v1/native/caller.cpp:121` confirms that Finish only clears/releases the original retained network/socket pairs.
- `integration-1/item-reference-repeat-native-composite-v1/native/diagnostic.hpp:9` provides exact inherited boundary context validation and real own PID/birth. It performs synchronous context-file IO; calling it on a UI callback is not a solution to the new reader's nonblocking requirement.
- No explicit DllMain/CreateThread/_beginthreadex/QueueUserWorkItem/CreateThreadpoolWork implementation is present in the package's four C++/header entry/lifetime sources or its original caller/probe source. This bounded inspection does not claim that the Windows SDK or unrelated project files contain no such symbols.

## Exact issuer contract to carry forward unchanged

Pinned issuer manifest `da7ba96dcd82df2395c628edf59346057f9246ef456da3ca31ed30e9c3b6136d`; pinned package manifest `00d237ddc928ba6408c2acfab4116aa74692bd7af18dbf8ef658bc866a7815b2`. Full paths/lengths/hashes are in parent-pins.json.

The future reader derives `<OWN_KEY_INVOKE_BOUNDARY_DIR>/local-ui-bootstrap-v1/bootstrap.json` only from the already validated inherited boundary directory. It must preserve the original strict context.json contract and validate its own current PID/birth. The separate bootstrap has exactly schema, endpoint, capability, client_pid, client_birth, server_pid, server_birth, handshake_schema, max_hello_bytes, reconnect. Expected schema is lineage-local-ui-bootstrap-v1; handshake_schema lineage-local-ui-hello-v1; max_hello_bytes 512; reconnect false; capability exactly 64 lowercase hexadecimal characters; endpoint is the exact local pipe prefix plus 48 lowercase hexadecimal characters. Numeric IDs/births must have exact types/ranges and match current process/server instance, with server identity verified through actual pipe server PID and process birth before sending the capability. Unknown/duplicate/extra fields or trailing data must be refused, not silently coerced.

Hello is exactly a JSON object with schema lineage-local-ui-hello-v1 and capability, ASCII and newline-terminated within 512 bytes. Only exact `{"schema":"lineage-local-ui-accepted-v1"}\n` ACK confirms issuer admission. No reconnect/reissue or other payload follows. The issuer v2 activates its 10-second deadline only after original NativeOwner.resume returns successfully; a future native caller needs its own bounded cancellation/drain behavior within this budget. Failure/unknown ACK is not accepted, nor authority for selected character/model/command/UI. Native UI close/drain remains UNKNOWN even after issuer cleanup completes.

## Verification and next owned work

`python -B work/local_original_session/implementation-companion/local-ui-channel-native-reader-v1/verify.py` checks exact parent pins, bounded lifecycle evidence and the unchanged source boundary; it does not run/load native code or connect a pipe. verification.json records this source-inspection result. Compile-only test is NOT_APPLICABLE because no C++ reader was added under the task's explicit lifecycle prerequisite.

Next implementation must first select the actual post-load/non-forwarding worker start owner and its exact cancellation/completion/module-retention contract. Only after that concrete caller exists should a private C++ reader/handshake client be implemented and compile-checked. Host/UI/model/commands remain outside this unit. Full companion runtime remains unselected/UNRUN. Writer and execution resources released.
