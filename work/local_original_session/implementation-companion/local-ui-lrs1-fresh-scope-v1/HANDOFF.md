# COMPANION-MAGE: fresh native scope boundary v1

WRITER_RELEASED. Only this new private directory changed. This is a fail-closed
source slice, not an implemented fresh owner or a selected full cohort.
source_ready/test_ready/ui_ready/UI_ready/runtime_ready/action_ready/save_ready
are false. RUN_COMMAND=null. Runtime/real close/native reissue/selected save
readback remain UNRUN. Resources, game processes, ports, native loads, Store
copies, packets and common/Test/queue/ACTIVE/other-worker writes: 0.

Parent: `local-ui-lrs1-interface-cold-v2/manifest.json`, exact
`d1ba24f10040ef74ccc91a4c51e17e9e266570cc9c6c12ce05ca70daefc316a2` / 16888 B.
The sole candidate delta is LocalUiColdFactory.fresh_for_scope. Every other
Factory byte is unchanged. Host53b93746, NativeInterface d65562fb, original
Scope30a5e2de, Plan9c3659d1, launcher/native/transport and all their original
gates remain untouched. In particular no Host repin is imposed on the inventory
or native-input worker. Exact parents/contacts are in parent-pins.json and
missing-api-contract.json; the lean unified diff is supplied beside the source.

## Actual missing boundary

Selected native `ui_io_lifecycle.hpp:27,50-53,70,96` explicitly makes the
Lifecycle one attempt per process: attempted_ is permanent, Revoke is terminal,
and the host is a process-lifetime global. SelectedOpen Bridge Admit also
refuses admitted/revoked state (`ui_selected_open.hpp:22`), its Revoke reaches
the Panel, and actual LRS1 Closed revokes that bridge before the authenticated
LSR1 close receipt (`ui_reusable_settings.hpp:19-20,50-51`). Python channel
replacement cannot create a new State/native owner/bridge/Panel lifetime.

Exact launcher NativeOwner has no retained-child/current-Job fresh LRS1 issuer.
Its prepare() creates a suspended **new game process** and attaches that process
to a Job; resume() only resumes that original child. The initial run_session
path issues a channel before that resume. The existing sole _local_ui_tick
retains its one channel and Factory. Recalling prepare(), resetting a deadline,
rewriting bootstrap, calling Start again, or constructing new Python wrappers
would not issue a genuine fresh native owner inside the current game Job.

This is the exact first missing API: a selected launcher/native issuer that
creates an independent LRS1 epoch inside the same retained process/Job, with
new State/owner/bridge/Panel/channel/capability/nonce/key/deadline and captured
new interface/session/Host/current selection, and transfers the sole launcher
loop's ownership after authenticated old close. No hypothetical callable is
implemented or accepted here. missing-api-contract.json states the necessary
inputs/output lifetime and original save/packet preservation boundaries.

## Candidate behavior

The original Scope _construct_graph calls Factory.fresh_for_scope before the
old CompanionBootstrap.fresh_for_scope and before plan.bind_companion. The
candidate retains that source-owned checked_transition and original closed
Host/batch/CONSTRUCTING checks. It then requires the original Plan RETIRED,
native_ui retired, no selected old Host, and a CLOSED real selected session.

The close receipt must be the exact nominal NativeCloseReceipt retained by
Factory, NativeInterface, NativeOpenEndpoint and OpenPort's original attempt.
Its transport/session/intent/opened/wire/sequence must match the original
selected session and consumed close. UNKNOWN, missing close or unstarted
session never qualifies. No HMAC/parser/row checks are replaced: the original
SettingsSession/OpenPort consumers remain the sole receipt issuers.

Even after these conditions, the method always raises:

    LOCAL_UI_LRS1_CURRENT_JOB_FRESH_NATIVE_OWNER_ISSUER_UNSUPPLIED

There is no return, retry/recovery branch, owner-field mutation, constructor,
channel/pipe call, state/deadline reset, or Store operation in this method.
This prevents a synthetic successor from being mistaken for persistence/UI
success. It does not solve the native epoch gap. Original Scope failure and
recovery remain unchanged; a failure after retirement may also refuse recovery
and fail the broker, while preserving the original error/close/save evidence.
No old native authority is silently resurrected.

Normal login/selection/WORLD/direct packet sequencing, canonical per-character
save readback, inventory/equipment ownership, actor callbacks/leases and UID
burn remain original. No fresh command/reselect/quit/Store/UI runtime result is
claimed. A future genuine issuer must use those existing constructors and
contracts; this slice cannot be selected alone as a runnable full graph.

## Focused verification

`verify_readonly.py` passes 10 focused source checks: 17 exact parent pins,
compile without imports/bytecode, method-only inverse equality, original Scope
call order, retired/authentic receipt contacts, terminal refusal without side
effects, actual NativeOwner creation and native process-once contracts, and
unchanged inspected bytes/size/mtime. It executes no module/nominal constructor,
structural receipt fixture, graph, Store, native code or packet. Existing parent
checks are reused; no replay or new full test framework was added.

After freeze, the same read-only verifier additionally checks the artifact
manifest pins. It writes no output file:

    python -B C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/implementation-companion/local-ui-lrs1-fresh-scope-v1/verify_readonly.py

Parent main owns review/selection and any coordination. No queue registration
or Test dispatch is made by this worker. The appropriate continuation is the
genuine same-process native epoch issuer, not removal of Host's original fresh
native_ui refusal or an affirmative readiness flag.
