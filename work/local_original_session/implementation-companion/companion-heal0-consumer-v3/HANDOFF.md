# COMPANION-MAGE Heal0 consumer v3

WRITER_RELEASED. source_ready:false / test_ready:false / run_ready:false. Runtime UNRUN.
v2 remains immutable and untouched. Only companion_spell_rules.py changes from v2;
companion_support.py is byte-identical and its diff is empty. Exact v2 parents,
Heal0 producer and generic InstantRule core pins are in parents.json.

SupportPolicy now checks the pinned original SourceModule once at cold creation,
then retains (same SourceModule, exact producer module, path, sha, exact installed
selector function) in a frozen init=False private tuple. Positive-ID construction
performs no new source operation. No generic cache or shared writer was added.

installed_zero_rule performs cheap nominal type, pinned sha and retained module,
path, SourceModule and selector identity checks. It calls the retained producer's
installed_heal_rule without SourceModule.check/file reread. The original producer
still checks the actual recipe metadata binding, selected nominal schema/core,
original bound schema.instant_rule method and SAME schema.rules[0]/cost_rule.
HealZeroAdmission and original current/learned/cost/Plan checks remain in place.

Verification command:
python -B work/local_original_session/implementation-companion/companion-heal0-consumer-v3/verify_consumer.py

Regression reuses SKILL's original check_heal.py retained-source fixture: actual
metadata SourceModule/recipe, generic InstantRule and actual SkillDocument selector.
Counting the producer SourceModule.check shows exactly 1 cold call after admission,
3 repeated current + 3 helper calls, replaced actual installed Rule refusal and
changed producer-module refusal. Rule replacement raises
SKILL_EXACT_SELECTED_INSTANT_RULE_REQUIRED. Positive settings restore still passes.
The existing fixture is a pure source-seam check; its timing, target opt-in and
learned rows are not selected product authority or an actual game/packet result.

Same v2 caller contract: create SupportPolicy with actual same installed cost_rule,
heal0_recipe and pinned heal0_source, then HealZeroAdmission(schema, policy); wire
same admission into catalog, settings restore and canonical reader. Coherent
selected graph/normal Plan/caller and real current target/range/heal source remain
unready. No packet RUN_COMMAND is claimed. No v1/v2/common/queue/Test, sockets,
ports, saves, handlers or runtime processes were modified or executed.
