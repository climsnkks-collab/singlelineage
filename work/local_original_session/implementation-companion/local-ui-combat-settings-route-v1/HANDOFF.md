# COMPANION-MAGE LOCAL combat settings server route v1

**WRITER_RELEASED / PRIVATE CANDIDATE.** Component code implemented;
source_ready=false, test_ready=false, ui_ready=false, runtime_ready=false,
RUN_COMMAND=null. Host/native/Store route/game/packet runtime UNRUN. Owned
runtime resources0. No actual settings input, OPEN, saved runtime result, native
receipt, ACK, attack or attack magic is claimed.

Exact click-OPEN Host parent:
`d16376c297b008e27f999fa3ddc6b57df6f6df4693ccbc263d1334deaaad6da8` / 37377B.
Output Host:
`f03cd8720170fa0f5e0e4346c7826750872f0cb613d81bb3f38294d878ce6307` / 38576B.
New `companion_local_combat_settings.py`:
`180179174baa78139a1149b33ee26d102ca7cc858e1a4e202ad749503c45fe19` / 9209B.
`companion_combat.py` is byte-identical to basic-combat v1:
`b042c0b1356b786173ec220dc344bf216280e11395afc7095741db26ba47767a` / 3273B.
All actual parent and output paths/full pins are in parent-pins.json and manifest.

The new typed server route admits one exact issued CombatSettings request. It
requires genuine current OPEN/display, the original Host row, selection and UI
epoch, active mage lease/actor/owner lifetime, and the displayed expected mage
revision. execute_once calls Host.command outside a held row. Host then uses
its original single row operation; save_locked invokes the existing canonical
update_preferences CAS/atomic writer and observes its persisted require_current
row again. Exact equality permits only that mage's companion.combat and the
idempotent revision delta. Movement/support/progression/player are not replaced.
Host view includes combat_revision and requested/effective preferences from one
canonical mage read. A missing combat Request refuses the combat action; all
old commands retain their original AST logic and behavior.

PREFERENCES_SAVED means canonical preference readback only. Effective combat
stays PASSIVE/behavior_ready=false until COMBAT owner's genuine allied attacker
is coherently joined. Requested ASSIST/DEFEND/distance may be retained but stay
disabled behavior. No target UID, selected-player impersonation, attack handler,
damage formula, native receipt or game opcode was added. Magic policy deferred.
If render or cancellation fails after an observed save, the route retains that
observation and reports UNKNOWN separately; no retry/rollback/reset.

This is a separate candidate from mode-command-route-v1, not a replacement for
its Host. No competing HMAC domain, codec, native endpoint, Factory, cohort or
source loader was invented. PAIRED_COMBAT_CONTRACT.md specifies the future
COMBAT_SETTINGS_V1 typed action and exact join boundary. The first missing
successor is real selected local_ui_selected_open::Bridge + NativeOpenEndpoint,
then authenticated native settings input/result transport, combined mode/combat
Host and immutable source/actor-config/Feature/cohort/caller/RUN. Existing sealed
parents cannot be combined by replacing a path alone. Do not start Test here.

Verification: `python -B <absolute-this-directory>/verify_readonly.py`.
Initial37 source/DTO checks PASS: ten parent pins; three source compile;
unchanged combat bytes; Host only view/command change and all old command logic
AST preserved; one row operation; exact diff; immutable DTO validation; pure
expected CAS preservation/idempotence for all three requested modes; unavailable
effective behavior; absent/forged request and nested-row refusals before Host;
no transport/native imports or second row lock; explicit expected revision CAS.
Final verifier additionally checks all output/manifest pins and preserves every
inspected file hash+mtime. It writes no files/bytecode and invokes no Host, Store,
native OPEN or game path. Existing basic-combat real synthetic-Store tests are
pinned reference evidence only, not rerun or claimed for this route.

Only this new private directory was written. Existing dirs/common/original/
Test/client/API/queue/ACTIVE, game/ports/user Store copies, branches/worktrees
and commits were not changed. Main must review and choose coherent successors.
