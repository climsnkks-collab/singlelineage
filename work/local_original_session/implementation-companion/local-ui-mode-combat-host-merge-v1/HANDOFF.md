# COMPANION-MAGE mode/combat Host merge v1

**PRIVATE CANDIDATE / WRITER_RELEASED.** source_ready=false, test_ready=false,
ui_ready=false, runtime_ready=false, RUN_COMMAND=null. Host/Store/native/game/
packet runtime UNRUN. Host calls0, Store calls0, native OPEN receipts0, owned
runtime resources0. This component implements the combined server source;
it does not establish an actual in-game settings/save result.

Shared click-OPEN Host parent:
`d16376c297b008e27f999fa3ddc6b57df6f6df4693ccbc263d1334deaaad6da8` /37377B.
Actual mode Host input:
`d1a1c7e1032ad78c7c57f744d1b6ccbaba3f4644638ff4bbfc909806a6e47af4` /38040B.
Actual combat Host input:
`f03cd8720170fa0f5e0e4346c7826750872f0cb613d81bb3f38294d878ce6307` /38576B.
Merged Host:
`e14e5251d611d322a3ffe1e060b020c1124b792ee85f6543a51c7dc4fc70c96e` /39496B.
Full absolute input/output pins and exact diffs from all three Hosts are retained.

Host.command keeps its original one row operation and every original command
branch. Optional exact-module mode_request and combat_request hooks coexist.
Two new narrow guards reject simultaneous requests and a mode request paired
with any action except follow/station. The existing combat action/request
equivalence guard remains: combat requires its typed request, and other actions
cannot consume one. Old commands without optional requests keep their original
logic. Exact route types, issued identity, actual current OPEN/display, retained
epoch, lease/actor and source checks remain in their original owner components;
no additional TCP/owner validator, row acquisition or save writer was added.

Mode begin/finish and combat save_locked retain the actual finished source
semantics. The route modules are byte-identical copies of their pinned parents:
mode `725849f60eaeda96e152cd24081fe66c6ad4dc9eae8605eb84d55119447f1bae`,
combat route `180179174baa78139a1149b33ee26d102ca7cc858e1a4e202ad749503c45fe19`,
combat DTO `b042c0b1356b786173ec220dc344bf216280e11395afc7095741db26ba47767a`.
Only genuine canonical CAS/readback may produce SAVED/PREFERENCES_SAVED.
An already observed write survives subsequent render/cancellation doubt as a
retained observation alongside UNKNOWN. No cached view or ACK is a save result.
These properties are source preservation claims, not newly observed runtime.

Host.view exactly reuses the finished combat Host's display implementation:
one canonical mage require_current read supplies combat preferences and revision.
Requested ASSIST/DEFEND/distance can be represented; effective mode is PASSIVE
and behavior_ready remains false until COMBAT supplies a genuine allied attacker.
Attack magic policy is deferred by the user. No attack authority was invented.

Candidate cohort189 rows changes only Host/click versus the shared parent,
adds mode/combat-route/combat-DTO, and keeps all184 other descriptors identical.
The five candidate modules point at this private directory. Actor-click changes
only its expected Host SHA. Loader places both routes and combat DTO before Host;
it is candidate import metadata only. Inherited dependency/Factory/Plan/actor-
config/native references are not newly validated, selected or made coherent by
this merge. The inherited loader's missing local dependencies.json is not
fabricated. Full cold graph import remains UNRUN and the candidate is not ready.

First integration gap: real selected local_ui_selected_open::Bridge and exact
NativeOpenEndpoint/owner-thread OPEN receipt. Then actual authenticated native
mode/combat settings input/result transport and a coherent immutable full graph,
caller and RUN remain required. The existing mode codec is an unselected proposal;
combat allocates no new wire. LUI2 is untouched. Controls stay disabled.

Verification: `python -B <absolute-this-directory>/verify_readonly.py`.
The read-only verifier compiles private source without running it; checks full
input/output pins, exact deltas, original Host AST, one operation, one mage read,
unchanged real observation modules, descriptor changes and click/loader repins.
Only extracted boolean/type admission predicates and isolated DTO modules are
executed for conflict/mismatch/forged/subclass negatives. It never imports or
calls Host, CanonicalCharacterStore, native OPEN/endpoint or a game path. Existing
codec/CAS/runtime-parent evidence is reused, not rerun or expanded. Every inspected
file's hash+mtime must remain unchanged. Frozen final pins include this verifier;
no output regeneration, bytecode or other file write occurs during verification.

Only this new private directory was written. No original/common/Test/client/API,
queue/ACTIVE, game/ports/Store copy, branch/worktree/commit or other worker files
were modified. Root reviews/selects successors. Writer released; resources0.
