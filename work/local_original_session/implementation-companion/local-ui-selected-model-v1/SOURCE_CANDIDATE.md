# Selected Host read-only model: source candidate, not installed

This is a source finding and a bounded proposed integration, not an implemented or selected producer. No model bytes, gameplay commands, native controls, OPEN/CLOSE acknowledgements, new channel, callbacks, or UID authority are supplied.

## First blocker in the actual selected caller

The selected Host cohort is `COLD_IMPORT_ONLY_ACCOUNT_CLICK_COMPONENT`, `run_ready:false`. Its selected `operating_input.Prepared.launch` calls the selected `launcher.main` (operating_input.py:356–378). That main calls its own original `run_session` (launcher.py:5510), not `local-ui-launcher-owner-compat-v1/session_composition.py:run_session`. There is no caller argument selecting a sidecar session. The sidecar itself is not a replacement main/installer.

The actual selected native graph also pins native394 DLL/receipt/manifest (operating_input.py:212–230), not the post-auth transport's private native source. Therefore the actual selected caller does not issue the retained local channel, select its paired native consumer, or invoke a selected Host model producer. Registering a model at that point would require inventing a missing caller/selection, replacing a source guard, or treating a cold component as a running Host. This artifact does none of those things.

There is a second independent composition gap: owner-compatible sidecar manifest eb498c49 loads issuer-v2 `LocalUiChannel`, while post-auth manifest 3f7a72b2 adds `LocalUiTransport` in a separate source. The sidecar does not instantiate that subclass. Transport REQUEST_MODEL currently builds only its fixed UNBOUND result; it cannot call Host.view. Its success is retained-process authentication plus UNBOUND transport only.

## Smallest source-backed candidate after that caller exists

Use one read-only synchronous producer reached by the existing original Broker row operation. The source has two existing sites: Broker.py:5734–5741 (read-poll after checkpoint) and :5832–5838 (after actual replies/drain and packet WORLD continuation). Neither site currently publishes a LOCAL model. Do not insert a second task/lock/queue or invoke the producer from launcher `_tick`, which is outside `_row_operation`.

The candidate must use the existing Host object in both `broker._companion_host` and `broker.realm._companion_host`, and require `host._row(writer) is row`. It must additionally require the original canonical provider to be present and `broker._canonical_operation_task is asyncio.current_task()`; a locked row alone does not prove ownership by this task. The exact selected Broker, Host, CharacterStore, RESOURCE service and original NativeOwner class spaces must remain the cohort's objects.

Before projection, obtain `broker.inventory_selection_current(writer)`. Require the same row/writer/selected generation and `generation.user_start_done == 'DRAINED'`, not ATTEMPTED/UNKNOWN. This reuses original completed WORLD + current selected-generation authority. Require `host._state(writer).selection is generation.selected`, exact current direct lease via `host.characters.require_current(state.direct)`, and original `host.current_owner(writer)` plus `broker._hp_status.current(writer)`. The latter must be the existing canonical RESOURCE projection, not saved/profile HP, a UID match, or a caller boolean. `Host.current_owner` already reads movement/current RESOURCE and canonical direct ownership; `Host.view` by itself does not.

The original native owner must be exactly `type(owner) is selected_launcher.NativeOwner`, `owner is broker.policy.owner is channel.owner`, with exact retained handle/Job identities matching `channel.handle/job`, and the original synchronous bound owner guard. Run that original guard against the row's actual peer to link this writer's original TCP tuple to the retained process. Preserve channel `_current`, actual connected client PID, birth/Job/key checks, original one-use capability and original absolute deadlines; no UID or Python id can replace those checks. The exact original channel and pipe are selected once by the missing real caller. A new channel after a selection change is not allowed.

Capture the exact server references for row, selection, direct lease, controller held character lease, actor generation, UI epoch and RESOURCE lifetime before `Host.view(writer)`, then recheck them synchronously before admission. `Host.view` is the source-backed read-only field producer (Host.py:419–431). Its UIDs/names/level/support fields are display data only. Actor authority, when an actor is represented, comes from the existing current participant/root registration: the click feature's `_current_locked` demonstrates the exact DRAINED registration/lease/selection/generation checks. Do not treat `view()['companion_uid']` or an inactive cached actor as authority. A missing/uncertain actor is not a made-up current actor.

## Unresolved native and revocation boundary

No bytes should leave the row operation until an exact paired native model consumer and its invalidation behavior are selected in the real caller. The current 24-byte UNBOUND model has no selected data contract or revision/epoch invalidation. Do not change that wire spec merely to accommodate a hypothetical producer.

Any future selected wire must revoke the original attempt on owner/selection/epoch/held-lease/actor-generation change; invalidate pending and native cached selected data; recheck authority before each deferred/partial write; preserve sequence/deadline/one-outstanding/cancel/drain/unknown retention; and prevent a native stale model from surviving server revocation. A producer-only patch cannot establish that end-to-end property. No current model/token/cache is created here, and no candidate projection is represented as native consumption, UI success, panel open/close, or callback drain.

## Exact delta and checks

Product/source delta is empty (`diff.patch` is zero bytes). Only this new private report directory is written. `verification.json` checks exact parent/input hashes and the stated source call chain using Python AST/text; no product modules are imported. No MSVC or OS run is needed for a report with no changed native/runtime path. Existing transport verification remains its own narrower result, without rerun or scope expansion.

`source_ready:false`, `producer_implemented:false`, `selected_binding:UNREACHABLE_FROM_SELECTED_CALLER`, `test_ready:false`, `ui_ready:false`, `game_runtime:UNRUN`, `RUN_COMMAND:null`, `WRITER_RELEASED`.
