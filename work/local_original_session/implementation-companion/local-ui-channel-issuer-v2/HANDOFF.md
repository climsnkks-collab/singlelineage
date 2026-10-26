# COMPANION-MAGE LOCAL channel issuer v2 — post-resume deadline

ISSUER_PRIVATE_FIX / source_ready:false / test_ready:false / game_runtime:UNRUN / WRITER_RELEASED.

Fixed the startup-timeout bug identified by main source review. v1 started its 10-second handshake deadline in LocalUiChannel construction inside prepare(), while the retained child was suspended and real Broker/start/features setup could exceed that interval. v1 is preserved unchanged; only this new v2 directory was written.

## Exact delta

`local_ui_channel.py`: constructor retains the bounded timeout and monotonic clock but leaves deadline None. New `activate_post_resume()` requires ISSUED and no prior deadline, rechecks exact retained owner/process/Job and starts the deadline once. Poll before activation refuses with CHANNEL_NOT_ACTIVATED_AFTER_RESUME without consuming capability, aborting, or accepting a client. Poll after activation uses that new deadline. Close clears the deadline with the prior capability/IO cleanup.

`launcher_descendant.py`: original `super().resume()` must return successfully before explicit `activate_post_resume()`. If original resume raises, activation is not reached. The original prepare → Broker/start/features → resume ordering and inherited run_session tick are preserved. There is no timer during suspended-child preparation. Subsequent admission still requires original exact owner/key_guard plus retained PID/handle/birth/Job and pipe client PID; no admission or owner proof is relaxed.

`check_issuer.py`: injects a monotonic test clock, advances it 25 seconds between issue and activation without sleeping, verifies no deadline and preactivation poll refusal, activates once with a fresh 10-second budget, and refuses second activation. Existing valid capability/wrong capability/wrong process cases run against real disposable Python child handles/Jobs and OS named pipes. New timeout case advances exactly 10 seconds after activation and requires BOOTSTRAP_TIMEOUT, ABORTED and complete exact-artifact cleanup. This tests issuer timing/OS admission only, not an actual resumed game process. Child helpers remain live for the server's retained-process checks.

`diff.patch` contains exact v1→v2 deltas for these three files. `parent-pins.json` pins those exact v1 files, v1 manifest/HANDOFF and original launcher SHA256 `80641fa5bd46aa1e9f4b2fc1f1fb7a9bc70e3977d1706d33843b1ddf0accff2c`. The private descendant still rejects a different actual launcher parent. Wire/bootstrap schemas stay v1 because the message format did not change; v2 identifies this source correction.

## Verification

`python -B work/local_original_session/implementation-companion/local-ui-channel-issuer-v2/check_issuer.py`

Actual isolated final run: valid postactivation admission PASS; wrong capability refusal PASS; wrong client PID refusal PASS; postactivation timeout/abort PASS. Every case simulates the 25-second preparation interval, verifies preactivation refusal and second-activation refusal, consumes/removes only its owned artifacts and reports native_ui_close UNKNOWN. Private Python AST checks and source ordering inspection PASS. `verification.json` contains bounded actual results. No long sleep or OS/game clock manipulation was used.

Unchanged v1 issuer contract: unpredictable first-instance local-only single pipe, logon-SID protected newly created sibling bootstrap, one-use capability and exact owner process admission, no reconnect/reissue, bounded nonblocking poll, exact-file/nonrecursive cleanup with UNKNOWN preserved. Strict diagnostic context.json, environment and original/game ports are unchanged. Close COMPLETE concerns issuer resources only; actual native UI destruction/callback drain is still UNKNOWN. See the pinned v1 HANDOFF for the full unchanged wire/lifetime contract.

No common/original/Test/queue/ACTIVE changes, product selection, game/DLL load, game port, focus/input, branch/worktree/commit or UI/Host execution. Native reader, real selected Host binding, model/command payloads, UI owner dispatch and close/drain remain unimplemented; source_ready/test_ready stay false and full companion RUN_COMMAND:null. All checker helper processes/Jobs/pipes/files and this directory's writer are released.
