# Incoming magic target facts — no admitted incoming caster yet

READONLY_DATA_LEAF_WRITTEN / WRITER_RELEASED. source_ready=false / incoming_admission_ready=false / SKILL_consume_ready=false / test_ready=false / runtime UNRUN. No actual incoming spell, cost/HP/CAS/once/remove authority was created.

## Current callee finding

Selected c7fb SelectedStatsSource.magic_target_locked146–157 calls catalyst17e.project_magic_target110; active30 explicitly raises COUNTER_MAGIC_ADMITTED_SKILL_JOINT_REMOVE_REQUIRED139–140. This guard is unchanged. Helper counter_magic_decision169–199 is pure intent: named source exclusions first; ATTACK checks before damage RNG; CURSE/PROBABILITY consume intent only after actual successful status probability. Its booleans/JavaID are DATA, not incoming admission or canonical removal. No automatic logical+1 mapping exists here.

Existing magic cast-owner0d96 is admitted self-heal contact. Hostile-owner4d3e is explicitly nonlethal PC→NPC and its real SourceNpcCastAdmission/feedback are still OPEN. It cannot stand in for NPC→PC. Actual adapter7e715 supplies physical PcNpc/NpcPc contexts, not an incoming magic operation. Formal NPC v13 selected170 is physical counterattack only: Controller41e:628 invokes attack_player_repeated, Hit a960:433–464 prepares physical operation/capture_npc_locked/hit_for_operation. Runtime d00 generation/current is not caster permission. This statement is limited to those selected/read sources; it is not a repository-wide absence claim.

## Actual new read API

Canonical future alias: tools.local_original_session.combat_incoming_target_facts.

IncomingTargetFactsSource(selected_stats, *, selected_source, catalyst_source) requires actual nominal SourceModule objects with exact c7fb and17e hashes, actual c7fb SelectedStatsSource and its selected catalyst policy. File checks occur only at cold construction; hot source checks use held module/function/property code identities.

capture_locked(binding) calls the unchanged selected capture once with the PROVIDED actual current target binding. It emits frozen public IncomingTargetFacts(reader,binding,snapshot,target_uid,skill_revision,active_skill_ids,counter_magic_active). The FULL original active tuple is retained; active30 remains present. Missing observation raises through the original active_skills property. No active30 filtering, arbitrary snapshot/document setter, target projection, caster, new binding, RNG, cost, HP writer, SKILL mutation or once ledger exists. Facts are deliberately public DATA, not opaque capability.

require_current_locked(binding,facts) rereads the original current selected cache and requires exact snapshot identity plus active tuple/revision/target identity. Dataclass equality alone is not used because the parent's active/resist fields exclude comparison. Existing generation/selection/row/gear/progression/clock guards run through original capture. A planned SKILL mutation may intentionally make these BEFORE facts stale; the future admitted operation must bind expected preimage and validate its genuine postcommit receipt rather than pretending old facts remain current. close() only retires this read source.

counter_magic_present(tuple) is a pure DATA predicate: observed empty tuple=False, tuple containing30=True, unknown/wrong shape refuses. It is not a boolean caster proof or a removal command. Existing17e pure decision can later consume real admitted reference fields; no new raw-ID/bool action adapter was added.

## First required implementation contact

Actual Attack/CAST owner must first supply source-issued incoming NPC spell selection/referenceJavaID/branch, real caster and target generations, original canonical target binding/held operation and once-current source. For CURSE/PROBABILITY, it must supply the actual same-operation StatusResult/RNG identity; not a raw success bool. NPC MP/cost/cooldown/CAST action and feedback are external producer responsibilities; no selected-PC identity/MP/capability is borrowed. Then COMBAT can add a narrow admitted incoming consumer before damage RNG or after status success, followed by SKILL same-plan expected-revision remove30 with original cost/HP/CAS/once/partial semantics. No standalone remove30.

Default magic_target_locked still refuses active30 even for status target preparation. A future admission-aware target entry must preserve the observed30 state and admit the exact stage/exclusion proof; this read leaf is not a permissive projection around that guard. Active146's actual selected-element issuer is also not invented. No imaginary caster interface/Protocol/stub/future pin is shipped.

Verification: four changed data/syntax/source-contact groups, nine pure data inputs; original c7fb/17e and physical/cast source unchanged. No product import graph, canonical positive fixture, Store/Factory/profile/copy/server/ports/game/REA/Pro/queue/Test activity. Missing action consumer means no runnable gameplay caller and test_ready remains false.
