# COMPANION-MAGE basic attack owner v2

**WRITER_RELEASED**. Typed contract only; no genuine basic attack owner could be implemented from the current selected graph. `source_ready:false`, `test_ready:false`, `full_basic_combat_complete:false`, effective **PASSIVE**, packet/game **UNRUN**. v1 `af44ee96f0cc5f6b6d67b2a8ce9d2d2d2a71def907bd7bfcab408fdcb14b9ebf` remains byte-frozen; its settings/CAS implementation and truthful disabled modes are unchanged.

## Delivered

`companion_attack_owner.py` is the smallest typed boundary for a future source implementation. `CompanionBasicAttackOwner.assist_locked` accepts the real current `ActiveCompanion`, v1 settings, and exact real owner `AttackIntent`; `defend_locked` accepts the real current selected-owner `npc_player_hit.Result`. Inputs are annotations under TYPE_CHECKING; they do not construct a current actor, intent or hit. No client target UID or damage scalar is accepted. The contract explicitly requires original row operation, actor UID/generation/lease/current pose, same-character physical gear/resources/stats, target revalidation, real broker send/checkpoint/drain, and one NPC HP/death commit. A future owner's return must be its actual source-issued registered result; no successful result ABI is fabricated here.

The only concrete implementation, `UnavailableCompanionBasicAttackOwner`, raises `COMPANION_BASIC_ATTACKER_BINDING_UNAVAILABLE` before reading arguments, allocating mutable state, or sending. `availability()` states `effective_mode:PASSIVE`, `behavior_ready:false`, available modes PASSIVE only. It is **not installed in Host ticks**; unavailable combat adds no idle read/poll/scheduler, callback, retries or target queue. This is not basic-combat gameplay completion.

## First exact missing source input

**A genuine allied attacker/target admission is absent.** `AttackTargets._project` uses `realm.service(writer).snapshot()` (selected MovementService/Position), `revalidate` demands `selected is bound.attacker`, and the feedback sender encodes `bound.attacker.uid` (attack.py263–276/474–482/501). `AttackSession.current_intent()` revalidates only that sole owner-bound capability; its own docstring explicitly says this observational API cannot grant another request. Passing the companion UID through that handler would impersonate the selected player and was not done.

`CompanionBindings` can issue a same-character resource binding, but no basic attacker/target/NPC HP admission. The existing shared support configuration derives stats for heal/buff, not a physical attacker context. `npc_hp` entries/kill receipts are tied to the real AttackSession/current intent/row, so separate HP writes or a handler direct call would not repair the missing owner. Positive hostile-hit results exist for the selected owner; a hostile-hit producer whose victim is the companion is also absent. No owner result is relabeled.

`source-evidence.json` gives exact pinned source locations, available inputs and ordered missing contracts. `parents.json` pins all ten inputs. The source owner/main must select and implement the actual attacker admission in the owned attack/target/HP/send graph before wiring this interface. Do not enable ASSIST/DEFEND or engagement distance from a stored preference or the presence of this Protocol.

## Verification and execution boundary

`python "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-companion-attack-owner-v2\verify.py"` passed **16** bounded checks: ten exact source/v1 pins, compile, both concrete methods' unconditional first-input refusal, no mutable instance state or argument reads before refusal, effective-PASSIVE metadata. Sentinel arguments deliberately test refusal only; they are not mocked actors/receipts or positive gameplay evidence. No full graph cold import or previous successful test repetition.

No packet-client-v5 gameplay caller/RUN is supplied: actual attacker ownership/behavior route is incomplete. Keep `test_ready:false`; no fabricated opcode or direct-handler scenario. No original/shared/Test/API/client/queue/ACTIVE changes, game/ports/process/focus/Store-copy operations, branch/worktree or commit. Owned writer/runtime resources **0/released**. All writes are in this new v2 directory.
