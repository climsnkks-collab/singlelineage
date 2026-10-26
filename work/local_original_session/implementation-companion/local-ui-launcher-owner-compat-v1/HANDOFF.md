# COMPANION-MAGE LOCAL launcher original-owner composition v1

WRITER_RELEASED / composition_source_ready:true / source_ready:false / test_ready:false / game_runtime:UNRUN / RUN_COMMAND:null.

The selected native source path **does enable inventory_owner_guard**. The selected Host cohort remains COLD_IMPORT_ONLY_ACCOUNT_CLICK_COMPONENT and run_ready:false; there is no completed executable native UI scenario or native run result.

## Exact selected source finding

`companion-account-click-host-v1/cohort.json` selects `integration-1/adena-book-integration-v1/launcher.py`, SHA256 `1cc72cdccbb703e8b85485a3ba677ef14fbe1b7ee18920869921337b8750ec11`, 354494 bytes; and `integration-1/packet-gameplay-shared-v21/operating_input.py`, SHA256 `241f5a3047143ab389c617e21a0c4005788afb9d97147a15f9416ce8bfcc69cc`, 52437 bytes. These are the actual cohort selections, rather than the older manual396 ancestor or current common launcher. All absolute paths/bytes/full hashes are in parent-pins.json.

Selected operating_input.py:344-365 constructs ProductFeatureFactory with launcher.SHOP_INPUT_PROFILE and requires the same --product. Selected launcher.py:583 defines canonical-shop-input-v1; :3675 onwards checks the shop factory and requires type(retained) is NativeOwner, returning its exact original synchronous guard. Its main factory :5492 passes that result to the selected Broker. Selected `companion-account-click-broker-v1/product/broker.py`:1870-1880 checks the non-None guard's exact original owner type, bound self/function and synchronous nature. Thus this native source path activates the condition; this is not an observed runtime constructor success. The separate canonical-selected-features-v1 branch returns None after its bootstrap check and must not be confused with this selected SHOP path.

Issuer-v2's NativeOwner subclass cannot pass those exact-type checks. Its launcher_descendant.py additionally hardpins the current common launcher SHA80641f, differing from selected SHA1cc72c. Subclass compatibility and that parent pin are independent source incompatibilities. No original type/guard, Feature/Broker contract, or source seal was weakened.

## Private composition

session_composition.py contains the selected parent's original run_session body plus a small sidecar delta. Import requires the caller's existing source-selection mechanism to have loaded the exact selected launcher under tools.local_original_session.launcher. It refuses a different launcher path/hash or issuer-v2 hash. It supplies no alternate module installer, monkeypatch, replacement main, or second owner.

The caller must construct the **original selected NativeOwner**, retain the original Broker/Feature factories, and call this private run_session directly. The owner object passed to broker_factory, monitor, features and existing source-quit/startup hooks remains that same original object. Original bound guard, process, child handle, Job, and original cleanup remain unchanged. The session rejects a subclass/wrapper before prepare.

The selected source run_session and common80641f run_session have identical AST. The private function issues LocalUiChannel immediately after original prepare returns, while the retained child is suspended, then runs original monitor/Broker.start/features setup. It rechecks issuer current state immediately before original owner.resume. primary_resumed is set immediately after that real resume returns, preserving the parent's failure-close boundary even if subsequent issuer activation fails. Only then does the issuer start its post-resume deadline. No channel poll occurs before activation.

Both original owner.tick call sites, including the close-grace loop, now call a small helper: original tick first, then issuer poll if alive; if exited, issuer close and False. Original session catches/close logic, Broker.close draining, monitor teardown, process/Job cleanup, exit outcome and Store behavior otherwise remain intact. Final cleanup revokes issuer before owner.close and retries exact-file cleanup after it. A finally chain guarantees the original owner.close is attempted even if the first issuer.close raises; the second issuer.close is attempted even if original cleanup raises. A failure is not converted to completion.

The final report adds local_ui_channel using the issuer's actual sanitized report. COMPLETE and UNKNOWN cleanup remain distinct from original report.cleanup. Even COMPLETE issuer cleanup reports native_ui_close UNKNOWN; it is not native UI destruction/callback drain. If issuer construction never completes, state/cleanup are NOT_CREATED with native_ui_close UNKNOWN. Issuer-v2 still owns single-use capability, exact retained process/Job checks and nonrecursive artifact deletion; it is imported directly from its pinned file, not copied or modified.

## Bounded verification and remaining boundary

`python -B work/local_original_session/implementation-companion/local-ui-launcher-owner-compat-v1/verify_source.py`

Actual PASS: seven exact parent/input pins; actual cohort launcher/operating/Broker mapping; selected source guard activation; private syntax; reverse only the listed sidecar edits and the entire run_session AST equals the selected parent's original; prepare/issue/Broker/features/resume/activation order; both tick sites; no owner class or method replacement. Seven isolated helper control-flow checks cover live/exit ticks, absent channel, normal cleanup, first issuer-close exception, original-close exception, and UNKNOWN issuer cleanup. Those checks use explicitly named doubles only for the two small helper bodies; they never import or execute product modules, forge a product owner, exercise original owner guards, or claim OS/process/pipe results. Existing issuer-v2 real disposable process/Job admission checks are reused without rerun.

session.diff is the exact function delta. verification.json is the actual bounded check output. manifest.json pins this private artifact. No full executable SKU, loader entry, actual game profile/selected UI graph, selected Host model/command transport, or native UI outcome is delivered by this composition. Main must integrate a concrete selected caller separately; source_ready/test_ready stay false. Full companion/native UI game RUN_COMMAND is null. No native UI/run success claim.

Only this new directory was written. Existing dirty main, original/common/Test/queue/ACTIVE and other workers' paths remain untouched. No game/DLL, ports, pipe connection, focus/input, profile/Store mutation, branch/worktree/commit, or product-process creation. Writer and owned execution resources released.
