# COMPANION-MAGE basic combat preferences v1

State: **WRITER_RELEASED**. Private component source is implemented; selected source graph is incomplete. `test_ready:false`, `full_basic_combat_complete:false`, packet/game/runtime **UNRUN**.

## Delivered change

- Exact parent account-click Host `5c56104199997441567e7078b8e3f9fc9f8f2e22fd18d39fffc737d489d02731` / 36010 bytes. Only Host `view` / `command` and one import changed; all spawn/motion/support/kill/retirement methods retain their original AST.
- `companion_combat.py` implements immutable `CombatSettings(mode, engagement_distance)`; modes PASSIVE/ASSIST/DEFEND, local requested distance 1..8 grid cells. Unknown keys, target UID injection, bool distance and invalid modes refuse. No attack magic settings.
- `command(action='combat', values={'mode': 'DEFEND', 'engagement_distance': 4})` uses original row operation + callback epoch, live controller active/is_current, canonical companion role lease, and existing revision CAS/atomic writer. It preserves movement/support and the selected player's character. Result is **PREFERENCES_SAVED**, never an attack receipt or combat-complete result.
- Canonical preferences live only in that mage's existing `preferences.companion.combat`. Fresh `view` reads the canonical current mage role each time. Existing saves lacking this key use local PASSIVE/distance1 defaults without writing/migration.
- `view.combat` and command result expose `requested`, `effective_mode:'PASSIVE'`, `behavior_ready:false`, `behavior_reason:'COMPANION_BASIC_ATTACK_PRODUCER_UNAVAILABLE'`. `available_modes:['PASSIVE']`; ASSIST/DEFEND options and distance are disabled with reason. Requested ASSIST/DEFEND can be preserved by a caller, but must never be shown as effective behavior.

## Exact missing real behavior

The selected `CompanionActorPort` has no attack producer (companion.py lines152-183). The real `AttackTargets._project` obtains the selected player's `MovementService`/`Position`, revalidates `selected is bound.attacker`, and writes `bound.attacker.uid` in feedback (attack.py lines263-276/474-482/501). Neither a server snapshot nor actor motion grants the mage a real attacker/target/resource contract. No direct AttackSession handler call, fabricated request/result, target UID injection, RNG/equipment/damage duplication or selected-player impersonation was added. ASSIST/DEFEND/distance behavior is **not implemented**. The source controller/tick/Host.after_attack and shared support remain unchanged.

## Integration boundary

This is an unselected private Host descendant. `parents.json` pins the real account-click selected graph and exact inputs. `blockers.json` lists source evidence and integration prerequisites. Install `companion_combat` under the existing package class space before Host; merge the two Host method deltas into the main's selected Host/UI descendant. The existing account-click actor config and click Feature pin the old Host path/SHA, so they and the cohort/loader must be updated coherently by their owner. This artifact does not silently bypass those seals or claim cold-cohort compatibility.

Do not start Test from this directory. A normal-session packet caller/RUN was deliberately not supplied: no selected complete source graph or source-backed settings command transport / real companion attack producer is ready. Keep `test_ready:false` until the functional owner supplies the actual normal-session scenario through packet-test-client-v5.

## Verification

Run: `python "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-companion-basic-combat-v1\verify.py"`

28 bounded checks PASS: exact eight input pins; changed sources compile; invalid DTO inputs refused; all three requested modes clearly remain effective PASSIVE with disabled unavailable options; **existing real CanonicalCharacterStore** on a newly created synthetic private fixture verifies companion-only save, unrelated movement/support/player preservation, idempotence, stale revision rejection, direct-role rejection, released-lease rejection with unchanged bytes, and reopen restoration. Host changed-method AST is limited to view/command, keeping original row-operation/epoch checks. These are unit/source checks and synthetic Store observations, **not** packet, game save, UI or basic-attack runtime evidence. No original/user/Test Store was copied/opened; fixture is removed after verification.

No shared source/Test/client/API/queue/ACTIVE edits, game/port/process/focus/Store-copy operations, branch/worktree/commit, or original file modification. Owned writer and runtime resources are released. Implementation/source investigation was the main work; bounded validation and handoff only, no broader recheck.
