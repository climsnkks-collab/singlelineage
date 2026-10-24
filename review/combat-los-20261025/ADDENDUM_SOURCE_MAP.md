# COMBAT review source addendum (NOT EXECUTABLE)

This adds the downstream sources omitted from the original23-file review snapshot. Original S00–22 payloads and SOURCE_INDEX remain unchanged. Main separately updates PLAN/README/status in this reconciliation. Read ADDENDUM_SOURCE_INDEX.json for full original SHA256, original repository-relative path, exact original line ranges/symbol, export SHA256/bytes and explicit transformation/reuse records. No imported/executable product family is published here. `.source.txt` is full source text, `.excerpt.txt` retains original indentation and has missing enclosing/import dependencies; neither is an execution entry.

## Scope and privacy

Only source and sanitized SourceMap metadata are included. The two cohort files were inspected before export:0 hardcoded credential assignments; private local workspace absolute paths were normalized to repository-relative paths. External local absolute paths are omitted where encountered. Sanitized cohort bytes intentionally differ from originals; both hashes are recorded. No saved profiles, actual account data, launcher configuration, native query, execution logs, raw REA/CODE/assembly/binaries/assets, or external D-source contents are included. Public repository source code references to logs/profiles are code only, not their data. All addendum payload private-path/credential/email literal scan counts are0.

## Actual addendum contents

| ID | Material | Export | Original slice | Identity |
|---|---|---|---|---|
| A00 | common29_selected_cohort.sanitized.json | `sources-addendum/common29_selected_cohort.sanitized.json` | full file | sanitized JSON |
| A01 | common29_hp_resource_owner.source.txt | `sources-addendum/common29_hp_resource_owner.source.txt` | full file | original bytes |
| A02 | common29_skill_cost_delivery.source.txt | `sources-addendum/common29_skill_cost_delivery.source.txt` | full file | original bytes |
| A03 | common29_combat_hostile_cast.source.txt | `sources-addendum/common29_combat_hostile_cast.source.txt` | full file | original bytes |
| A04 | common29_broker_cast_skill_locked.excerpt.txt | `sources-addendum/common29_broker_cast_skill_locked.excerpt.txt` | lines2146–2185 / `cast_skill_locked` | exact source excerpt |
| A05 | common29_broker_positive_delivery_send.excerpt.txt | `sources-addendum/common29_broker_positive_delivery_send.excerpt.txt` | lines4778–5689 / `_send` | exact source excerpt |
| A06 | common38_selected_cohort.sanitized.json | `sources-addendum/common38_selected_cohort.sanitized.json` | full file | sanitized JSON |
| A07 | common38_hp_resource_owner.source.txt | `sources-addendum/common38_hp_resource_owner.source.txt` | full file | original bytes |
| A08 | common38_skill_cost_delivery.source.txt | `sources-addendum/common38_skill_cost_delivery.source.txt` | full file | original bytes |
| A09 | common38_combat_hostile_cast.source.txt | `sources-addendum/common38_combat_hostile_cast.source.txt` | full file | original bytes |
| A10 | common38_broker_cast_skill_locked.excerpt.txt | `sources-addendum/common29_broker_cast_skill_locked.excerpt.txt` | lines2146–2185 / `cast_skill_locked` | exact source excerpt; same payload reused |
| A11 | common38_broker_positive_delivery_send.excerpt.txt | `sources-addendum/common38_broker_positive_delivery_send.excerpt.txt` | lines4780–5693 / `_send` | exact source excerpt |
| A12 | strdex9038_broker_cast_postcast.excerpt.txt | `sources-addendum/strdex9038_broker_cast_postcast.excerpt.txt` | lines2146–2177 / `cast_skill_locked` | exact source excerpt |
| A13 | strdex_bf5186_lifecycle.source.txt | `sources-addendum/strdex_bf5186_lifecycle.source.txt` | full file | original bytes |
| A14 | pc_ac682_attack_intent.excerpt.txt | `sources-addendum/pc_ac682_attack_intent.excerpt.txt` | lines877–901 / `attack_intent` | exact source excerpt |
| A15 | pc_ac682__selected_owner_current.excerpt.txt | `sources-addendum/pc_ac682__selected_owner_current.excerpt.txt` | lines3166–3182 / `_selected_owner_current` | exact source excerpt |
| A16 | pc_ac682__row_operation.excerpt.txt | `sources-addendum/pc_ac682__row_operation.excerpt.txt` | lines2077–2106 / `_row_operation` | exact source excerpt |
| A17 | pc_ac682_attack_player_once.excerpt.txt | `sources-addendum/pc_ac682_attack_player_once.excerpt.txt` | lines3270–3274 / `attack_player_once` | exact source excerpt |
| A18 | pc_ac682_attack_player_repeated.excerpt.txt | `sources-addendum/pc_ac682_attack_player_repeated.excerpt.txt` | lines3247–3250 / `attack_player_repeated` | exact source excerpt |
| A19 | pc_ac682__attack_player_current.excerpt.txt | `sources-addendum/pc_ac682__attack_player_current.excerpt.txt` | lines3276–3363 / `_attack_player_current` | exact source excerpt |
| A20 | pc_ac682__player_life_service.excerpt.txt | `sources-addendum/pc_ac682__player_life_service.excerpt.txt` | lines3366–3372 / `_player_life_service` | exact source excerpt |
| A21 | pc_ac682_player_life_context.excerpt.txt | `sources-addendum/pc_ac682_player_life_context.excerpt.txt` | lines3374–3381 / `player_life_context` | exact source excerpt |

## Source ownership / current meaning

- **Common29:** `energybolt-book182-result-join-v1/cohort.json` selects its actual e894 Resource/decb CostDelivery/c055 hostile helper/98a1 Broker. The official Book182 result join exists; an actual persisted input/result/dispatch is not selected in that source-only package. Do not label the downstream commit/delivery implementation absent because the earlier snapshot omitted it.
- **Common38:** `common38-energybolt3-original-caller-v1/cohort.json` selects actual a0d0 Resource/4c7f CostDelivery/e494 hostile helper/aa881 Broker. Native29→38 current input/result is not selected; its actual first guard remains unconditionally unready. It is a separate conditional family, not an automatic replacement of common29.
- Resource/CostDelivery/hostile helpers are full source for each family. Each Broker exports only its exact `cast_skill_locked` and positive `_send` function. `_send` contains multiple real delivery branches; it is retained whole rather than a misleading isolated success statement. Common29/common38 cast function bytes are identical where the index records reuse; distinct full Broker identity/line spans are preserved per entry.
- **STRDEX/Buff:** Broker9038 actual `cast_skill_locked` includes native commit→original send/DONE→postcast refresh. The exact bf5186 lifecycle source includes original remove/expiry/restore and its DONE-boundary refresh. The existing23 already provides related Stats/cold/guards; addendum does not reimplement them or claim missing refresh.
- **Physical dispatcher:** exact historical ac682 is deliberately separate from hostile/Buff Brokers. Exact nested `attack_intent`, selected-owner/current row operation and NPC attack/Life-current functions are provided, including actual acceptance/handle and NPC attack flow. Its current dependencies/AttackSession and Life guards remain in the original snapshot; no arbitrary union of these families is a coherent runtime.

## Terrain decoder discovery (references only, not new REA export)

The original workspace has real cached decoder/reference source beyond exported23: `run283_energybolt3_projectile_los/source/contract.md` and `source-refs.json` describe S32 second-u16-plane→Cell+4, existing terrain query raw mask AND/override-first projection; `run275_heal0_target_distance/source/contract.md` describes raw1/0x40 Map consumers and a DestructibleDoor type exception. Their referenced `original_terrain_query.cpp` and `s32_cell_plane_parser.cpp` are existing external cached text sources. **No D-external file or raw REA text is copied into this package**; only these path names/previous conclusions are referenced.
The repository reference `implementation-2/npc-motion-goal/approach-player-hit/core/references/L1V1Map.java` contains actual L1J arrow bits0x04/0x08, direction/diagonal and DoorTable open/dead/map/edge rules. This is existing reference implementation, not a selected Python current-door producer or proof of NC S32 bit equivalence. MOVE mask1/passable adjacency, distance or test bypass is not projectile clearance. The earlier review must distinguish decoder/reference existence from missing selected/current authority.

## Remaining OPEN (not hidden by this export)

- **U1 / production LOS authority:** supported attack/projectile bit/direction/corner/endpoint policy and same-operation actual map/door/override current/version producer is not supplied by this package. Raw decoder/reference semantics alone cannot issue CLEAR. Normal wall/door tests and current-state revocation remain required; explicit TEST bypass is not their PASS.
- **U2 / family+input readiness:** common29 actual official learned/current result and common38 actual native29→38 input/result/complete RUN selection remain package-specific unready facts. These are not missing Resource/CostDelivery/Broker implementation. Real target class/hidden/status/actor eligibility gaps remain owner-specific.
- **U3 / effects/runtime:** incoming NPC caster authority, independent poison tick/current state and other source-owned effect inputs are not established by these downstream files. No actual cast/HP0/feedback/Stats/expiry/fresh/UI PASS follows from exporting source. Keep actual partial/UNKNOWN/DRAINED semantics and current owner HANDOFF scopes.
- **U4 / review-only fragments:** unexported imports/canonical namespaces/source-role dependencies remain required. Function excerpts and separately selected families must not be run/merged as one product. No synthetic native owner/current/capability or new opcode/field is provided.

## Integrity and review boundary

Existing23 snapshot payload SHA256 values and their original full-source identity were verified against SOURCE_INDEX, including its two declared excerpt records. Every addendum payload was re-read after write and its byte SHA256/length checked; cohort selected-role full-source pins were matched to actual originals. Content-identical payloads are referenced once rather than duplicated. These are file integrity checks only: no tests, source imports, graph, Store/Factory/NativePlan/server/process/network/native memory operation, git mutation or queue action occurred. Main owns final inspection/commit/push.

WRITER_RELEASED.
