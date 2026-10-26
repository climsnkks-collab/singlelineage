# COMPANION-MAGE basic auto-attack ingress v1

**WRITER_RELEASED. source_ready:false / test_ready:false / run_ready:false.** Source-only event-ingress descendant; no Host/Broker/selected cohort installation, no gameplay RUN. Automatic repetition is NOT implemented. Attack magic deferred. Current modes remain effective PASSIVE in existing UI.

Human policy: real owner's normal attack/positive being-hit selects target, companion repeats at its OWN attack speed on server clock; companion kills use owner/ally 50:50 and odd half accumulation in COMBAT's existing ledger. No cadence/damage/EXP code was invented here.

## Actual delta

`companion_combat_caller.py` descends from v3 caller, with exact same `_active` controller/actor UID/generation/current/direct and companion lease/settings/SharedSupport checks. Cold optional owner now requires actual SourceModule sha84e59e01a60e608977aa9bebb720aa5a3c7f0ee2a25a141673182e80ca355ff9, genuine nominal AlliedAttackSession and exact host/broker. Existing COMBAT SourceSeal supplies unchanged module/function current checks. Default owner=None remains pre-read BLOCKED, without any poll or actor lookup.

ASSIST retains accepted_count+1/current_intent identity/bound writer/ownerUID/original feedback DRAINED; DEFEND additionally demands original source operation COMMITTED and hp_transport DRAINED, then exact source Result/current positive nonlethal before>after>0. The actual source objects go unchanged to real assist_locked/defend_locked. Successful source-return classification now requires both current_result_locked(writer,result) and last_result_locked(writer) identities; an opaque return is no longer accepted. This means one actual issued DRAINED event only, never repeated attacks or whole gameplay PASS.

One local event marker per writer retains exact state/active/mode/event identity, never a cached target UID/admission. Existing per-state attempted-event references remain set before awaits even if callee raises. `retire_locked(writer)` only drops that local marker under the original row; it never calls COMBAT release/close, resets deduplication or destroys unresolved committed partial. Returning after a retired marker refuses local result classification while COMBAT retains its actual partial. A later genuine accepted event may establish a fresh marker, still subject to COMBAT unresolved gate. There is no tick/repeat callback or long-lived target authority.

`release_locked(writer)` is final writer cleanup only: capture original metadata/partial first, then actual COMBAT release under original held row, then local marker drop. NEVER call it for mode changes/transient cancel to bypass unresolved delivery. `close()` calls real owner.close at final scope teardown; no actor removal/native absence assertion. Host integration must call local retire on mode/owner/actor/lease/target invalidation and preserve original actor/lease cleanup; this candidate is not installed.

## Exact first missing API / source incompatibility

FIRST cold construction: admission-v2/allied_actor_inputs.py SOURCE_SHA256['allied_registration'] is None and rejects ALLIED_CURRENT_ACTOR_SOURCE_FAMILY_UNSUPPLIED. Its companion pin16f5e84f is historical; actual motion selected companion is18c0a5a6. Do not hot-swap types. Current publication is actual37a8ecfdc587a67b64c6ce464c63b4f1b1993ec91ee65aadc212a12aea933897 with Core6041; old d149 publication is not compatible.

Further actual target parents differ: selected b65d3306/204d6b52/97f296e7 AttackSession/attack/HP, but admission-v2 AlliedTargetInputs requires73944b06/e925eca0/74dd208b. Cold graph is not coherent. Main/COMBAT/Root must select real descendant sources; this component does not whitelist arbitrary replacements.

Automatic target lifecycle API is absent: AlliedTargetInputs.capture_locked/validate_locked repeatedly validate the ORIGINAL current AttackIntent/positive Result; they grant no persistent target intent and cannot be replayed every poll. AlliedAttackSession _triggers also intentionally refuses the same trigger. No source-approved persistent target generation, reacquire/current-retire, cadence deadline or cancellation ABI exists yet. Preserve UID/gen/map/pose/HP source reads with COMBAT and do not synthesize new triggers or target-only packets.

Actual v2 cadence/credit policy None guards refuse before RNG/HP. Root AlliedBasicTransport is unsupplied; allied lethal notification/remove/credit join also unavailable. COMBAT owns own-speed/server-clock once cadence and existing ledger EXP; no duplicated damage/reward code here. Those are the first dependencies after source-family coherence.

## Broker contacts / authenticated settings

Selected Host d1495c34a0353198f9ffcae0c4e9416957dd8a538392f0c4b612be749b082de6 is unchanged. Its original authenticated command state+ui_epoch/row/lease settings consumer remains owner of saved PASSIVE/ASSIST/DEFEND preferences. This candidate does not add a command/opcode or enable behavior from preferences.

Selected Broker6e703872 event contacts: Realm.attack_intent around927 captures accepted_before and handles original real4E30; its existing companion callback around951 is lethal-only and before original response drain. It CANNOT serve as this nonlethal ASSIST callback. Original _serve around6065 handles actual frame, sends/drains around6071, completes peer then ordinary companion poll; exact same row service/count captured before that dispatch must reach the new source-approved after-drain event edge. _attack_player_current around3487 makes actual Result and COMMITTED after status drain, then returns within its original UNKNOWN try/catch. Companion callback must be after original method return, outside that catch: companion failure cannot relabel already committed owner damage UNKNOWN. No Broker patch installed; no speculative no-drain callback.

## Checks and execution boundary

`python -B "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-companion-basic-auto-attack-v1\verify.py"`: 34 focused checks PASS, including17 exact parents, compile, old `_active` AST equality, source/result/positive-hit guards, no repetition/cancel-to-release, local retire preservation and unavailable/closed pre-read refusal. No positive actor/HP/COMBAT simulations; no graph import, packet/client/game/Store/profile/copy/ports/REA. Existing successful movement/support tests reused, not rerun. `parents.json` records complete absolute input pins; `caller.diff` is the narrow real delta. No gameplay caller/RUN can be honestly supplied until missing source/API is selected, so test_ready remains false.

Writes ONLY this new private directory. Existing common/original/Root/COMBAT/ITEM/GEAR/Test/ACTIVE/queue unchanged. Runtime/writer resources0/released. Main reviews source and supplies actual integration; no messages to external chats.
