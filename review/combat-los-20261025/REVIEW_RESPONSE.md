# Web review reconciliation and bounded follow-up

The user supplied a manual review of commit `4f5b0875f59cd67a484824d097c3a0a5652a83a3`. This session did not observe the external UI, account, model or tool-call history. We checked the consequential source findings, rather than treating the reviewer's access claim as independently verified. No game/runtime test or product implementation was performed for this addendum.

## Accepted corrections

1. **PC physical range and cadence are missing in the inspected selected path.** AttackSession, target/request coordinate checks and the inspected upstream Broker dispatcher do not provide distance or server attack-speed admission. Counter capacity is not cadence. The prior plan's claim that PC distance was connected was wrong.
2. **Initial physical LOS/range/cadence must precede `_hp_prepare`, which already resolves the physical decision/RNG.** Do not add dynamic LOS refusal indiscriminately to `AttackTargets.revalidate`: that method is also used after HP commit to deliver the already settled result. Revalidation must follow phase-specific lifetime rules.
3. **NPC attack wire precedes HP/status.** Initial LOS must precede prepare/RNG and the first attack wire. A later failure can coexist with sent attack feedback or committed native HP. Preserve existing partial/UNKNOWN/once behavior; do not infer damage from attack wire alone.
4. **Production LOS is still incomplete.** Unresolved refusal and a narrowly scoped Test-only CLEAR are not a current map/door producer. MOVE flags, adjacency, segment enumeration and empty door lists do not establish attack clearance.
5. **Completion belongs to a selected executable family.** The nonlethal physical adapter, d45 lethal Resource, de1e STRDEX Resource and hostile common29/common38 families cannot be summed into one proven product. Existing limited reported PASS results retain their original scope.

## Scope corrections and extra source

Raw S32/terrain decoder material and L1J arrow/door reference implementations already exist in the original workspace. The missing closure is the explicit attack/projectile policy bound to real current map/door/override data and its actual consumer. This is not a claim that no decoder or no producer exists anywhere in the repository. Raw REA and external local artifacts are not republished here.

Hostile Resource/CostDelivery/Broker implementations and STRDEX postcast/lifecycle refresh also already exist. Their omission from the original 23-source snapshot is not implementation absence. ADDENDUM_SOURCE_MAP.md and ADDENDUM_SOURCE_INDEX.json identify bounded supplementary code, original relative paths, hashes and excerpt ranges. Their named cohorts are reference selections, not proof of current live installation or successful casting. Original S00–S22 references remain stable.

Other outstanding work remains explicit in the revised PLAN.md: actual ammunition consumption and timing, rejected proc/extra-attack consumers, blocked-path detours, actual incoming caster/tick/area/loot consumers, normal recovery and formal PC death return. Reuse implemented math, stats producer/cold/carrier/refresh, mover delta and typed PRE components.

## Next three implementation units

- Bind actual current map/door attack clearance to the existing visibility interface, with real BLOCKED/CLEAR/UNKNOWN and same-operation actor/map/version evidence. Preserve unknown refusal; do not invent bit meanings.
- Add PC range/cadence/LOS at the existing AttackSession final-current/pre-prepare seam, using actual weapon/ammunition/timing input and normal rejection outcomes.
- Add NPC initial LOS before prepare/first wire; retain existing mover fixes and phase-specific current/partial semantics through wire, HP and status.

Exact inputs, ownership and acceptance criteria are in PLAN.md. These are planned units, not completed product changes. Independent ready work is not gated on the entire combat roadmap.

## Follow-up request

Using the connected GitHub app, read this addendum at the new exact commit supplied by the user. Reuse the original review of 4f5b0875; do not repeat the general math/23-file audit. Read the indexed supplementary code and report only conclusions whose uncertainty is actually resolved or changed.

Check the hostile cost/commit/positive-delivery and STRDEX postcast/lifecycle connections in their separate named families. Distinguish omitted implementation from a missing current consumer. Confirm or correct the pre-RNG/pre-wire insertion points and revised roadmap. Cite files/functions/lines actually read. Never infer current installation from a historical cohort.

Keep genuinely unavailable actual map/door authority, selected lethal PRE/current recovery inputs and any unexported tick/AoE/incoming/loot bodies as bounded unknowns. Do not invent CLEAR, refunds, attack-wire semantics or behavior for attached poison versus persistent area, mid-cast door changes, other-target healing/support, diagonal endpoints/layers or formal death return. Do not treat a contract-only route as implemented.

Historical runtime evidence in the initial review is unchanged. Later actual execution state is maintained privately by the responsible owners; this public snapshot does not assert that actual199/200 are the latest project results. No private saved input, native query sample, whole launcher or test logs are supplied.
