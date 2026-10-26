# COMP-03A Heal0 caller private v1

`product_delta_ready:true`; `source_ready:false`; `test_ready:false`; runtime `UNRUN`.
Owner: COMPANION-MAGE 01a16769. Only this new private directory is written.

## Actual new call path

The unchanged default `CompanionBootstrap(shared=configuration)` path remains in use:
`support_factory=None`, `responses=None`, `clock=None`. No alternate source owner,
packet wrapper, response factory or clock is installed.

1. A real cold source supplies the existing `SupportPolicy(0, 'heal', ...)` over
   the installed Rule0 and creates the existing v3 `HealZeroAdmission(schema, policy)`.
2. `SharedSupportConfiguration(..., heal0_admission=admission)` retains that very
   admission. A selected policy0 without it is refused. The policy itself still
   has to prove ally targeting; this caller grants no target permission.
3. `SharedSupport.validate_sources` requires the admission's schema to be the
   same actual RESOURCE owner's SKILL schema and its policy to be the same policy0.
   The actual Rule0 producer remains authoritative, including its cold source pin.
4. Original `CompanionHost` summon preference restore and `action == 'support'`
   restore now pass that same admission into the original `SupportSettings.from_mapping`.
   This is the actual existing Host consumer, not a replacement UI route.
5. Original `SharedSupport.build_port(current)` passes it into the existing
   `CanonicalSupportReader`. That reader requires exact same-admission capabilities,
   real learned0, current companion/selected-owner bindings and existing participants.
6. For key0 only, `SharedSupport.plan` repeats the same canonical reader under the
   owner lock before original `plan_skill`/`resolve_heal`, with no intervening await.
   The actual catalog re-evaluates current target/range/LOS/opt-in. The original
   `choose` over the single scheduled rule must return the same actor/target and
   generation identities. Changed admission returns a prewrite `SupportUnavailable`.
7. The original planner debits its actual Rule cost, invokes the existing resolver
   once, clamps selected owner HP, prepares the original linked RESOURCE/SKILL CAS,
   preflights the existing selected-owner scalar response and drains it through
   the original Broker. This phase is unchanged and unexecuted by this artifact.

`owner_heal0_settings(configuration, mapping)` additionally restores a bounded
single owner Heal0 preference. `build_owner_heal0_caller(shared, current, mapping)`
composes the original scheduler/port for an already installed shared instance. It
is an explicit bounded caller seam for the same Host construction boundary; do not
install it as a second `support_factory`, second scheduler or polling loop. Normal
Host uses the patched restore/build_port path above without invoking this helper.

## Required real inputs and exact unresolved boundaries

Paths below are relative to `work/local_original_session/`; exact absolute paths,
full SHA256 and sizes are recorded in `parents.json`.

| Phase | Real file/symbol | Required input / ownership |
| --- | --- | --- |
| Cold Rule0 | `implementation-3/skill-buff/heal-zero-rule-v1/heal_zero_rule.py::installed_heal_rule`; consumer-v3 `HealZeroAdmission` | Already supplied source. Not a missing-Rule gate. Same actual schema/Rule/cost/recipe/source identity is still required. |
| Cold/current catalog | This descendant `SharedSupportConfiguration.catalog`; v3 `CanonicalSupportReader.__call__` | Actual `catalog(active,caster_binding,owner_binding,frame,now)` producing exact-admission `SpellCapability`, current target opt-in and range/LOS. UI range10 has no supplied metric/geometry/LOS authority. Actual producer file is UNSUPPLIED in the audited inputs. Do not infer target authority from fixture policy. |
| Cold + heal amount | `optional-target-v1/candidate/companion_shared.py::SharedSupport.plan`, original heal branch (preserved) | Actual `healing[0]` of retained `combat_magic.HealingSpell`, same companion `derived_stats` and `magic_context(caster,active)->{'lawful':actual_int}`; the same retained owner RNG. The reference coefficients already have evidence; SQL lawful0/default0/new RNG are not inputs. |
| Learned/current | `companion-heal0-consumer-v3/companion_support.py::CanonicalSupportReader._read`; original `plan_skill` | Existing lawful learned0, actual active lease/caster actor/current owner, same account RESOURCE/SKILL participant rows. No grant, forced HP/MP or selected-player-as-caster substitution. |
| Shared SKILL seal | `companion-skill-graph-v1/buff_skill_document.py::seal_support_plan` (346), `support_event_plans` (392); actual generic-instant schema also exists | A coherent selected schema must retain the original joint/support seals and actual installed InstantRule0 selector. This worker does not merge/rewrite SKILL. Existing manifests describe provenance but do not identify a currently authorized common SKILL writer; exact current owner remains UNKNOWN. Do not assign general heal to BUFF-only/BOOK-only by name. |
| Shared HP/joint commit | `companion-resource-runtime-v1/hp_resource_owner.py::ResourceOwner.bind_companion_support` (240), `plan_companion_support_locked` (254), `commit_companion_support_locked` (262) | Actual same provider/BatchStore/binding/linked RESOURCE/SKILL custody, current status source and callback capture. The historical private parent is evidence, not current common-owner reassignment. Current common HP writer is UNKNOWN from supplied manifests. |
| Scalar response | `optional-target-v1/candidate/companion_response.py::SelectedStatusSupportSource.preflight` (122) | Already supplied original owner-only scalar status consumer; actual same plan/Operation/current/delivery still required. Key0 is never inserted into a timed-buff allowlist. |
| Cold source capture | `companion-factory-v1/canonical_feature_bootstrap.py::bind_companion` (432) | Existing exact SourceModule captures and same selected graph for these descendants/v3/source callbacks. No Factory file is written. |

First blocked phase: `COLD_REAL_HEAL0_CONFIGURATION_AND_COHORT_INPUTS_UNSUPPLIED`.
The earliest missing configuration facts are source-backed ally opt-in/current
catalog range/LOS; lawful/RNG/healing configuration and coherent current custody
are separate required inputs, not substitutes or feature-wide gates.

## RUN, first failure, partial and cleanup

`RUN_COMMAND:null`, `packet_caller:null`, `test_ready:false`. The scenario in
`scenario.json` is a conditional actual-player sequence, not an invented runnable
packet test. Missing normal setting/summon input packet/source and real configuration
must be supplied before Test selection. Existing Test client-v5 is reused then.

Offline verification only, from the project root:

```powershell
python -B work/local_original_session/implementation-companion/plan-comp03a-heal0-caller-v1/verify_caller.py
```

No server, socket, handler, profile copy or Store write is part of this command.
On real execution the first error and raw partial receipt/current/UIDburn remain
the original owner's artifacts; unknown delivery is never replayed. Retire/close
only this scheduler through the original Host lifetime path. Original SharedSupport
owns pending finally/partial and native delivery retirement. No reset/rollback,
refund, extra Heal0, forced full cleanup, old166 release or previous PASS rewrite.
