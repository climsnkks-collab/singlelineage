# COMPANION-MAGE Heal0 consumer v2

WRITER_RELEASED. source_ready:false / test_ready:false / run_ready:false. Runtime UNRUN.

Two private exact descendants of companion-heal0-consumer-v1. v1 is untouched.
parents.json pins both v1 parents, actual SKILL heal_zero_rule.py SHA6d79470d2d2582da5ed16217ccb904d69ab75b4b1a35c232fe2fc80855242a87,
and actual generic-instant-core-v1 skill_buff.py SHA6064dd5ecafbc6aee448e52a1da36d717b679ddafe2cc25d1af6ebb006fba89d.

Correction: HealZeroAdmission now requires actual core.InstantRule and delegates to
companion_spell_rules.installed_zero_rule. That helper requires the exact original
SourceModule type and pinned Heal producer hash, then uses the producer's
installed_heal_rule(schema, recipe=..., cost_rule=SAME_object, current_spell_key=0).
The producer retains/checks original schema.instant_rule(0), selected schema/core
and source recipe identity. No duck-typed Rule or hand-built selector is accepted.

SupportPolicy adds optional heal0_recipe/heal0_source cold authority fields. They
are mandatory for key0; positive-ID behavior is unchanged. plan_skill's zero branch
uses that SAME installed producer and exact InstantRule; positive branch keeps Rule.
All existing source policy/current, real learned membership, resource cost/cooldown,
range and canonical commit checks remain. No offset/Light1, automatic grant, target,
range metric, healing amount or production cooldown/group is invented. New source
files do not install or enable an existing shared feature.

Minimal check command:
python -B work/local_original_session/implementation-companion/companion-heal0-consumer-v2/verify_consumer.py

verification.json: exact pins, syntax, positive settings roundtrip and missing
zero-authority refusals pass. The actual generic InstantRule constructor accepts
explicit Heal0 shape; the constructor's zero cooldown/group values are isolated
shape-test fixtures, not production policy. Actual installed schema/recipe/current
learned graph was not forged to manufacture a successful admission.

required-skill-api.json gives exact next caller contract. Coherent selected schema,
real recipe, same installed object, existing SharedSupport Plan cold wiring and
current target/range/heal consumer remain to be assembled by feature main. Runtime
and playable packet caller/RUN_COMMAND remain unready. No shared/prior source,
queue, Test copy, handler, game/server/socket/ports/save was modified or executed.
