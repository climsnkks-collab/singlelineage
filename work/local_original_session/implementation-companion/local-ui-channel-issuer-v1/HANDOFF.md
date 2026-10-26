# COMPANION-MAGE LOCAL launcher channel issuer v1

ISSUER_IMPLEMENTED_PRIVATE / source_ready:false / test_ready:false / game_runtime:UNRUN / WRITER_RELEASED.

Implemented the bounded launcher-owned producer missing from the prior transport audit. This is a private issuer/bootstrap and opt-in NativeOwner descendant. It does not implement Host selection binding, native bootstrap reader, model/command framing, owner-thread dispatch, panel or ATS UI. No product selection was changed. UI readiness remains false even though the isolated OS issuer check passed.

Only this new directory was written; main dirty checkout and unrelated files were retained. No common/original/Test/queue/ACTIVE edits, game/DLL load, game socket/port, focus/input, branch/worktree/commit or REA action. The short check created disposable Python helper processes, a separate unnamed Job per helper, uniquely random local pipes and temporary bootstrap files; all were closed/removed.

## Exact parents and actual wiring

`parent-pins.json` pins the actual current `tools/local_original_session/launcher.py` (357918 bytes, SHA256 `80641fa5bd46aa1e9f4b2fc1f1fb7a9bc70e3977d1706d33843b1ddf0accff2c`) plus both prior HANDOFFs. The private descendant imports the real launcher and refuses a different parent hash before constructing its real NativeOwner. It adds no replacement process launcher and no synthetic production owner.

The descendant inherits original `prepare()`, then issues the channel while the real child is still suspended. Original strict `context.json` is returned unchanged. The existing `run_session` broker_factory/start/features sequence remains before `resume()`. The descendant requires the issued channel and exact owner again before original resume. Its inherited run_session loop calls the overridden `tick()`, which performs one bounded nonblocking admission poll after the original owned-Job check. It closes/revokes before original owner.close and retries exact-artifact cleanup after that original process/Job cleanup. Admission failure or timeout raises into the original session failure/finally path; it does not continue with an unauthenticated UI endpoint.

This descendant is **not installed or selected** by any common launcher or selected DLL. A later coherent source must instantiate this NativeOwner in the existing owner slot; the native reader must be supplied before that source can use the mandatory 10-second handshake. Loading the private module through an importer requires its directory on Python's import path, as in the standalone checker. No new launcher CLI/run command is claimed.

## Bootstrap / pipe contract

`local_ui_channel.py` captures the owner's exact child object, primary handle, Job, PID and creation FILETIME. Issue/admission recheck those captured objects against current owner/child/member bindings and original owner.key_guard(), retained handle GetProcessId/GetProcessTimes/liveness and IsProcessInJob. No PID supplied by a JSON message is accepted. GetNamedPipeClientProcessId must equal that retained primary PID, with original retained ownership checked before and after.

The endpoint is a random 192-bit suffix under the Windows local pipe namespace. CreateNamedPipe uses DUPLEX, FILE_FLAG_FIRST_PIPE_INSTANCE, a single instance, PIPE_NOWAIT and PIPE_REJECT_REMOTE_CLIENTS. The pipe and a newly created exact `owner.directory/local-ui-bootstrap-v1/` directory/file receive an explicit protected DACL granting only the launch controller's unique logon SID. There is no Everyone/Authenticated Users fallback and no inherited permissive bootstrap DACL. Handles are noninheritable. The issuer does not change the ACL on any existing directory.

The separate versioned `bootstrap.json` contains schema, random endpoint, 256-bit capability, expected client PID/birth, launch-controller server PID/birth, handshake schema/max length and reconnect:false. It is created CREATE_NEW, flushed and retained without write/delete sharing. A native reader must open it read-only with FILE_SHARE_READ|FILE_SHARE_WRITE to coexist with the issuer's retained write handle; it may not request write access. The native reader derives this sibling path from its already inherited boundary directory; no environment or strict diagnostic context modification is needed. A future reader must validate its own PID/birth and retain/query the pipe server process using GetNamedPipeServerProcessId plus birth/liveness against this bootstrap before revealing the capability. That native implementation is still OPEN.

Handshake is ASCII JSON `{"schema":"lineage-local-ui-hello-v1","capability":<exact 64-hex string>}` plus one newline, at most 512 bytes. No other fields, payload tail or second newline are accepted during admission. The pipe uses bounded nonblocking reads. The server compares a SHA256 capability digest in constant time, rechecks the real owner, consumes the capability and writes `{"schema":"lineage-local-ui-accepted-v1"}` plus newline. Failed/partial ACK is UNKNOWN and aborts; no command may be retried as a result. There is no reconnect, second instance or reissue on an issuer object, including after failed authentication. Capability/endpoint/hello body never enter the issuer report.

An AUTHENTICATED report means retained process plus bootstrap possession only. It creates no broker row/selection/character/actor authority and delivers no UI model. There is deliberately no generic payload API in this unit. The selected Host callback/epoch must later be retained server-side under the actual row operation. Existing original game packets, F101 and game TCP ownership checks are unchanged.

## Close, abort and unknown

`close()` immediately removes acceptance and consumes remaining capability, closes only its handles and removes only its own exact file and empty created directory. It never recursively deletes. Handle/file/directory cleanup failure yields CLOSED_UNKNOWN/cleanup:UNKNOWN and can be retried; no fallback path is used. `abort(reason)` follows the same cleanup and preserves ABORTED when cleanup completes. EOF/malformed hello/wrong PID/wrong capability/owner change/timeout fail closed; the capability is never reused. Once authenticated the issuer poll only rechecks retained ownership; it is not a payload/EOF monitor. Later transport integration must implement connection loss/drain behavior before it can carry commands.

Transport resource cleanup COMPLETE does not imply native control destruction, callback drain or original game logout. `native_ui_close` remains UNKNOWN in every issuer result. This unit has no native close acknowledgement. It neither unloads/reuses native storage nor claims to complete Host retirement. Actual owner-thread destroy/drain stays a separate missing contract.

## Verification and limits

Run from project root:

`python -B work/local_original_session/implementation-companion/local-ui-channel-issuer-v1/check_issuer.py`

`verification.json` records actual isolated Windows tests: (1) retained Python helper PID/handle/birth/Job plus valid capability accepted and consumed, issuer reissue refused; (2) wrong capability rejected; (3) controller holding the artifact rejected because its pipe-client PID differs from the retained helper. Each checks exact artifact cleanup COMPLETE and native_ui_close UNKNOWN. The helper checks the real pipe server PID/retained birth before sending its capability. Harness owner is explicitly an isolated adapter using real OS handles/Job, not a product NativeOwner or genuine selected game session. Private source AST parsed successfully. The first harness attempt lacked PROCESS_TERMINATE access required by AssignProcessToJobObject and failed before issuing a pipe; its helper was terminated and handles closed, then the harness rights were corrected. Final three-case run passed.

No production NativeOwner was constructed, game resumed or DLL loaded, and no visible UI/input/Host command/selection/retirement success is inferred. Full companion `RUN_COMMAND:null`. `source_ready:false/test_ready:false` until the genuine native reader, selected Host adapter, dispatch and drain are coherently supplied and the exact selected source/caller/RUN exists. This unit is ready for source review as an issuer only.

All writer/process/Job/pipe/file resources released; no queue registration or notification was emitted by the private product code.
