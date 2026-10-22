"""Opt-in admitted SELF heal → same RESOURCE+SKILL CastPlan and receipt.

No target inference, bool admission, legacy self-buff proof conversion or new
writer. Scalar metadata and input stats are supplied explicitly at cold bind.
Original input/actor/source epoch proof remains the SourceCastAdmission owner.
"""
from dataclasses import dataclass
from copy import deepcopy
from types import MappingProxyType
from tools.local_original_session.combat_magic import MagicActor, HealingSpell, resolve_heal


def need(value, code):
    if not value:
        raise ValueError(code)


@dataclass(frozen=True)
class SelfHealRule:
    spell_id: int
    spell: HealingSpell
    # Exact configured core rule supplies authoritative costs/cooldown/learned key.
    cost_rule: object


class SelfHealPolicy:
    """Explicit LOCAL extension of selected rule semantics; defaults install none.

    Existing rules continue self buffs unless individually configured here.
    The selected scalar rule creates no buff or invented lifetime. The original
    Rule's duration is not consumed for this immediate-effect policy.
    """
    def __init__(self, owner, rules, *, actor_provider, rng):
        need(not owner.active and not getattr(owner.status.broker, '_started', False),
             'MAGIC_COLD_OWNER_REQUIRED')
        need(type(rules) is tuple and rules and callable(actor_provider),
             'MAGIC_EXPLICIT_SCALAR_POLICY_REQUIRED')
        need(len({r.spell_id for r in rules}) == len(rules), 'MAGIC_DUPLICATE_SCALAR_RULE')
        for r in rules:
            need(type(r) is SelfHealRule and type(r.spell) is HealingSpell
                 and owner.skill_schema.rules.get(r.spell_id) is r.cost_rule,
                 'MAGIC_EXACT_CONFIGURED_COST_RULE_REQUIRED')
            # Do not turn currently established Light/Shield effects into heals.
            need(r.spell_id not in (1, 2), 'MAGIC_EXISTING_BUFF_KEYS_PRESERVED')
        self.owner, self.rules = owner, MappingProxyType({r.spell_id: r for r in rules})
        self.actor_provider, self.rng = actor_provider, rng

    def plan(self, context, *, owner_module, txid, request, now_ms):
        owner = self.owner
        context.current()
        binding, snapshot = context.operation.binding, context.decision.snapshot
        need(context.feature.broker._hp_resource_owner is owner
             and owner.status.current(binding.writer) is snapshot
             and context.operation.payload is request and context.operation.txid == txid
             and context.decision.target_uid == binding.uid,
             'MAGIC_EXACT_ADMITTED_SELF_CAST_REQUIRED')
        owner.provider.current(binding)
        owner.require_hp_quiescent(binding.writer)
        previous = owner.store.lookup(binding, txid=txid, request_sha=owner.batch.request_digest(request))
        if previous is not None:
            return previous  # No reroll, re-debit, heal or response authority.
        need(owner.active and owner._prepared_operation is None, 'MAGIC_ACTIVE_QUIESCENT_OWNER_REQUIRED')
        rule = self.rules.get(context.decision.spell_id)
        need(rule is not None and owner.skill_schema.rules.get(rule.spell_id) is rule.cost_rule,
             'MAGIC_EXACT_COLD_RULE_REQUIRED')
        with owner.store.lock:
            context.current()
            before = owner._participant(binding)
            skill = owner.store.participant(binding, 'SKILL')
            owner.skill_schema.validate(skill['document'])
            skill_after = deepcopy(skill['document'])
            row = skill_after['characters'].get(str(binding.uid))
            need(row is not None and rule.spell_id in row['learned'], 'SKILL_NOT_LEARNED')
            need(type(now_ms) is int and row['clock'] <= now_ms < (1 << 53), 'SKILL_CLOCK_ROLLBACK')
            cost = rule.cost_rule
            need(snapshot.fields[10] > cost.hp_cost and snapshot.fields[12] >= cost.mp_cost,
                 'MAGIC_ALIVE_AND_COST_REQUIRED')
            need(str(rule.spell_id) not in row['buffs'], 'MAGIC_SCALAR_KEY_HAS_ACTIVE_BUFF')
            # Expiry of unrelated buffs belongs to the already-run lifecycle.
            # Expired cooldowns can be removed in this same SKILL transition.
            row['cooldowns'] = {k: v for k, v in row['cooldowns'].items() if v > now_ms}
            need(str(cost.group) not in row['cooldowns'], 'SKILL_COOLDOWN')
            need(now_ms + cost.cooldown_ms < (1 << 53), 'SKILL_TIME_OVERFLOW')
            if cost.cooldown_ms:
                row['cooldowns'][str(cost.group)] = now_ms + cost.cooldown_ms
            row['clock'] = now_ms
            row['revision'] += 1
            actor = self.actor_provider(binding, snapshot)
            need(type(actor) is MagicActor, 'MAGIC_TYPED_CURRENT_STATS_REQUIRED')
            context.current()  # Callback cannot replace selection or status.
            heal = resolve_heal(actor, rule.spell, self.rng)
            values = dict(before['document']['values'])
            values['10'] = min(values['11'], values['10'] - cost.hp_cost + heal.amount)
            values['12'] -= cost.mp_cost
            after = owner.document.next_values(before['document'], values=values)
            result = dict(events=[dict(kind='resource_debit', hp=cost.hp_cost, mp=cost.mp_cost),
                dict(kind='magic_self_heal', spell_id=rule.spell_id, amount=heal.amount,
                     applied_hp=values['10'] - (snapshot.fields[10] - cost.hp_cost),
                     policy='LOCAL_REFERENCE_L1J')])
            op = owner_module.Operation(binding, snapshot, before['document'], after,
                request, txid, 'CAST_COST', result)
            changes = (owner.batch.ParticipantChange('RESOURCE', before['revision'], before['digest'], after),
                owner.batch.ParticipantChange('SKILL', skill['revision'], skill['digest'], skill_after))
            fields = dict(snapshot.fields)
            fields.update({int(k): v for k, v in after['values'].items()})
            fields = owner.shield_status_fields(binding, fields, skill_after)
            plan = owner_module.CastPlan(op, changes, deepcopy(skill['document']), skill_after,
                fields, owner.status_module.frame(fields), now_ms)
            plan.magic_context = context
            owner._prepared_operation = op
            owner._prepared_digest = owner.plan_digest(plan)
            # Canonical buff document's normal seal also protects this CastPlan.
            if hasattr(owner.skill_schema, 'seal_cast_plan'):
                owner.skill_schema.seal_cast_plan(plan, owner)
            return plan


@dataclass(frozen=True)
class AdmittedSelfContext:
    feature: object
    operation: object
    decoded: object
    decision: object
    admission: object
    route_module: object

    def current(self):
        f, r = self.feature, self.route_module
        need(type(self.operation) is r.InputOperation
             and isinstance(self.admission, r.SourceCastAdmission)
             and f.admission is self.admission and type(self.decision) is r.AdmittedCast,
             'MAGIC_GENUINE_SOURCE_ADMISSION_REQUIRED')
        need(all(x is not None for x in (self.decision.original_input_owner,
             self.decision.original_actor_owner, self.decision.source_epoch)),
             'CAST_SOURCE_ACTOR_INPUT_EPOCH_PROOF_REQUIRED')
        f._current(self.operation)
        need(self.admission.current(self.operation, self.decoded, self.decision) is None,
             'CAST_SOURCE_CURRENT_MUST_RAISE_NOT_BOOLEAN')
        need(self.decision.spell_id == self.decoded.request.signed_lookup_key
             and self.decision.target_uid == self.operation.binding.uid
             and f.broker._hp_resource_owner.status.current(self.operation.binding.writer) is self.decision.snapshot,
             'MAGIC_CURRENT_SELF_TARGET_AND_STATUS_REQUIRED')
        return None


def bind_owner(owner, policy):
    need(type(policy) is SelfHealPolicy and policy.owner is owner
         and getattr(owner, '_combat_magic', None) is None and not owner.active,
         'MAGIC_EXACT_COLD_OWNER_POLICY_REQUIRED')
    owner._combat_magic = policy


def preflight_scalar(parent):
    """Existing CostDelivery with one original full 26-field status frame."""
    owner, plan = parent.owner, parent.plan
    context = getattr(plan, 'magic_context', None)
    need(parent.phase == 'PREFLIGHTING' and type(context) is AdmittedSelfContext,
         'MAGIC_ISSUED_CAST_PLAN_REQUIRED')
    owner.validate_plan(plan)
    events = plan.operation.semantic_result['events']
    need(getattr(owner, '_combat_magic', None) is not None
         and context.decision.spell_id in owner._combat_magic.rules
         and context.operation.payload is plan.operation.request
         and context.operation.txid == plan.operation.txid
         and len(events) == 2 and events[0]['kind'] == 'resource_debit'
         and events[1]['kind'] == 'magic_self_heal'
         and events[1]['spell_id'] == context.decision.spell_id,
         'MAGIC_EXACT_SCALAR_RESULT_AND_SOURCE_REQUIRED')
    need(owner.cast_light_wire(plan) is None and plan.status_wire == owner.status_module.frame(plan.status_fields),
         'MAGIC_ORIGINAL_FULL_STATUS_REQUIRED')
    parent.buff_services = parent.preflights = ()
    parent.frames = (plan.status_wire,)
    parent.parts = [None]
    owner.register_delivery_dispatcher()
    parent.phase = 'PREFLIGHTED'
