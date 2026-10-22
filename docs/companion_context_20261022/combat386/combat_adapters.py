"""Cold-bound LOCAL policy adapters consumed by existing attack owners.

Snapshot callbacks are supplied by actual character/equipment/SKILL owners;
they must return immutable typed inputs from their current selected authority.
No wire fields, status W, test row, UID cache, balance or new sender is used.
"""
from dataclasses import dataclass
from tools.local_original_session import npc_hp
from tools.local_original_session import combat_physical as physical


def need(value,code):
    if not value: raise ValueError(code)


@dataclass(frozen=True,slots=True)
class Decision:
    context: object
    result: physical.PhysicalResult
    source_uid: int
    target_uid: int
    accepted_ordinal: int | None
    target: object = None


def _supported(result):
    need(type(result) is physical.PhysicalResult,'COMBAT_TYPED_RESULT_REQUIRED')
    need(not result.extra_attacks and not result.consume_effects,
         'COMBAT_EXISTING_EFFECT_CONSUMER_REQUIRED')
    return result


class PcNpcProvider:
    policy=npc_hp.POLICY

    def __init__(self, hp_inputs, *, snapshot_locked, rng):
        need(getattr(hp_inputs,'policy',None)==npc_hp.POLICY
             and callable(snapshot_locked) and callable(getattr(rng,'randint',None)),
             'COMBAT_EXPLICIT_PC_NPC_OWNERS_REQUIRED')
        self.hp_inputs,self.snapshot_locked,self.rng=hp_inputs,snapshot_locked,rng

    def initial_hp(self,target): return self.hp_inputs.initial_hp(target)

    def resolve_hit(self,*args,**kwargs):
        raise ValueError('COMBAT_REAL_INTENT_CAPTURE_REQUIRED')

    def capture_locked(self,writer,row,intent,target):
        need(row['operation_lock'].locked(),'COMBAT_EXISTING_ROW_LOCK_REQUIRED')
        context=self.snapshot_locked(writer,row,intent,target)
        need(type(context) is physical.PcNpcContext,'COMBAT_TYPED_PC_NPC_SNAPSHOT_REQUIRED')
        result=_supported(physical.resolve_pc_npc(context,self.rng))
        return Decision(context,result,intent._bound.attacker.uid,target.uid,
                        intent.accepted_ordinal,target)

    def hit_for_intent(self,intent,target,hp):
        decision=intent.adjudication
        need(type(decision) is Decision and decision.target==target
             and decision.target_uid==target.uid
             and decision.source_uid==intent._bound.attacker.uid
             and decision.accepted_ordinal==intent.accepted_ordinal
             and type(decision.context) is physical.PcNpcContext,
             'COMBAT_EXACT_INTENT_DECISION_REQUIRED')
        return npc_hp.Hit(decision.result.landed,decision.result.damage)


class NpcPcAdjudicator:
    def __init__(self, *, snapshot_locked, rng, recovery_inputs_locked):
        need(callable(snapshot_locked) and callable(recovery_inputs_locked)
             and callable(getattr(rng,'randint',None)),
             'COMBAT_EXPLICIT_NPC_PC_OWNERS_REQUIRED')
        self.snapshot_locked,self.rng,self.recovery_inputs_locked=(
            snapshot_locked,rng,recovery_inputs_locked)

    def bind_cold(self,service):
        need(service.adjudicator is None and not service._contexts and not service._operations
             and not service._repeated_histories and not service.broker._started,
             'COMBAT_COLD_NPC_SERVICE_REQUIRED')
        service.adjudicator=self

    def capture_npc_locked(self,writer,service,operation):
        row=service.validate_locked(writer,operation.context)
        need(row['operation_lock'].locked(),'COMBAT_EXISTING_ROW_LOCK_REQUIRED')
        context=self.snapshot_locked(writer,service,operation)
        need(type(context) is physical.NpcPcContext,'COMBAT_TYPED_NPC_PC_SNAPSHOT_REQUIRED')
        result=_supported(physical.resolve_npc_pc(context,self.rng))
        return Decision(context,result,operation.context.source_uid,
                        operation.context.target_uid,None)

    def hit_for_operation(self,writer,service,operation):
        decision=operation.adjudication
        need(service.adjudicator is self and service.operation_for(writer) is operation
             and operation.context._writer is writer and type(decision) is Decision
             and decision.source_uid==operation.context.source_uid
             and decision.target_uid==operation.context.target_uid
             and type(decision.context) is physical.NpcPcContext,
             'COMBAT_EXACT_NPC_DECISION_REQUIRED')
        return npc_hp.Hit(decision.result.landed,decision.result.damage)


@dataclass(frozen=True,slots=True)
class NpcRule:
    target: npc_hp.Target
    defense: physical.NpcDefense
    offense: physical.NpcOffense
    ranged_template: int


class SelectedCombatInputs:
    """Concrete current character/equipment/SKILL -> direction input consumer.

    The selected-stat source is refreshed by its original selection/equipment/
    SKILL change hooks, not read from files for an attack. NPC numbers and
    current distance are supplied by the existing selected NPC owner. Missing
    catalog rules fail instead of turning the old fixed test input into stats.
    """
    def __init__(self, selected_stats, *, npc_rules, distance_locked, weight240_locked):
        from tools.local_original_session.combat_selected_stats import SelectedStatsSource
        need(type(selected_stats) is SelectedStatsSource and type(npc_rules) is tuple
             and all(type(r) is NpcRule for r in npc_rules)
             and len({r.target for r in npc_rules})==len(npc_rules)
             and callable(distance_locked) and callable(weight240_locked),
             'COMBAT_EXACT_SELECTED_INPUT_SOURCES_REQUIRED')
        self.stats,self.rules,self.distance_locked=selected_stats,npc_rules,distance_locked
        self.weight240_locked=weight240_locked

    def _selected(self,writer,row):
        binding=self.stats.owner._binding(writer)
        need(binding.generation.row is row and binding.operation_lock is row['operation_lock'],
             'COMBAT_SELECTED_SAME_OPERATION_REQUIRED')
        return self.stats.capture_locked(binding)

    def _rule(self,target):
        rows=tuple(r for r in self.rules if r.target==target)
        need(len(rows)==1,'COMBAT_CURRENT_NPC_TEMPLATE_POLICY_REQUIRED')
        return rows[0]

    def pc_snapshot_locked(self,writer,row,intent,target):
        selected=self._selected(writer,row)
        need(selected.uid==intent._bound.attacker.uid,'COMBAT_SELECTED_ATTACKER_REQUIRED')
        rule=self._rule(target)
        weight=self.weight240_locked(writer,row,intent)
        need(type(weight) is int and 0<=weight<=240,'COMBAT_CURRENT_WEIGHT240_REQUIRED')
        return physical.PcNpcContext(selected.derived,selected.weapon,rule.defense,
            ranged=selected.weapon.kind in ('bow','gauntlet'),weight240=weight,effects=selected.effects)

    def npc_snapshot_locked(self,writer,service,operation):
        row=service.validate_locked(writer,operation.context)
        selected=self._selected(writer,row)
        need(selected.uid==operation.context.target_uid,'COMBAT_SELECTED_DEFENDER_REQUIRED')
        _,target=service.combat._hp_binding(writer,row,operation.context.source_uid)
        rule=self._rule(target)
        distance=self.distance_locked(writer,service,operation)
        need(type(distance) is int and distance>=0,'COMBAT_CURRENT_DISTANCE_REQUIRED')
        return physical.NpcPcContext(rule.offense,selected.derived,
            ranged=rule.ranged_template>=10 and distance>=2,distance=distance,
            ranged_template=rule.ranged_template)


def refresh_selected_stats(owner,writer,event):
    """Actual owner change boundary; a view error never replays a real commit."""
    source=getattr(owner,'_combat_stats',None)
    if source is None:return
    try:
        binding=owner._binding(writer)
        if event=='selection':source.selection_locked(binding)
    except Exception:
        # Existing durable receipt/transport remains the original owner's fact.
        # No fallback combat values or successful view are published.
        source._snapshot=None
        source._binding=None
        return
    for selected,method,attribute in (
        (event in ('selection','equipment'),source.equipment_changed_locked,'_equipment'),
        (event in ('selection','skills'),source.skills_changed_locked,'_skills')):
        if selected:
            try:method(binding)
            except Exception:
                source._snapshot=None
                setattr(source,attribute,None)


def bind_cold(owner,selected_stats,inputs,*,rng,recovery_inputs_locked):
    """Attach only after actual canonical/NPC service creation, before start."""
    from tools.local_original_session import attack_session
    broker=owner.status.broker
    combat=broker._attack_session
    hit=broker._npc_player_hit
    generation=getattr(broker,'_inventory_generation',None)
    need(not broker._started and generation is not None
         and generation.broker is broker and generation.phase=='ACTIVE'
         and all(getattr(generation,name) is None for name in
                 ('writer','row','lock','game','selected','mover','frame','selection_binding','current_frame'))
         and not generation.restored and not generation.attempted and not generation.write_attempted
         and getattr(owner,'_combat_stats',None) is None
         and selected_stats.owner is owner and inputs.stats is selected_stats
         and type(combat) is attack_session.AttackSession
         and type(combat._hp) is npc_hp.Authority and not combat._hp._entries
         and combat._current is None and combat.accepted_count==0
         and combat._hp.provider is combat._hp_provider,
         'COMBAT_EXACT_COLD_EXISTING_OWNERS_REQUIRED')
    provider=PcNpcProvider(combat._hp_provider,snapshot_locked=inputs.pc_snapshot_locked,rng=rng)
    adjudicator=NpcPcAdjudicator(snapshot_locked=inputs.npc_snapshot_locked,rng=rng,
        recovery_inputs_locked=recovery_inputs_locked)
    adjudicator.bind_cold(hit)
    combat._hp_provider=combat._hp.provider=provider
    owner._combat_stats=selected_stats
    return provider,adjudicator
