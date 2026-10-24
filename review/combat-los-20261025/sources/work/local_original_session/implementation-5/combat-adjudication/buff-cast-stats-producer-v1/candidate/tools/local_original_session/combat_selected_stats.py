"""Existing selected character/equipment/SKILL producer for pure combat inputs.

Default disabled until actual owner selection/setup hooks bind it. Character INFO
is read once at selection. Canonical participant read is confined to existing
selection/commit hooks. capture_locked never opens files or invents NPC stats.
"""
from dataclasses import dataclass, replace, field, asdict
import sys
from tools.local_original_session.combat_magic import Resists
try:
    from .combat_stats import Stats,PcStats,StatModifier,DerivedStats,derive_stats
    from .combat_physical import Weapon
except ImportError:
    from combat_stats import Stats,PcStats,StatModifier,DerivedStats,derive_stats
    from combat_physical import Weapon

LOCAL_CLASS_NAMES = {0:'royal',1:'knight',2:'elf',3:'wizard'}

@dataclass(frozen=True)
class EquipmentRule:
    """Explicit catalog template policy. Weapon fields are never modifiers."""
    template: int
    weapon: Weapon
    modifiers: tuple[StatModifier,...] = ()

@dataclass(frozen=True)
class SkillRule:
    spell_id: int
    modifier: StatModifier
    physical_effect: str | None = None

# Logical spell IDs from canonical SKILL, not opaque icon/W/client IDs.
# Shield -2 is declared LOCAL normalization independently of its UI W projection.
DEFAULT_SKILL_RULES = (SkillRule(1,StatModifier('light:no_combat')),
                       SkillRule(2,StatModifier('shield:LOCAL_ac_minus2',ac=-2)))

@dataclass(frozen=True)
class SelectedStatsSnapshot:
    uid: int
    writer: object
    generation: object
    selection: object
    derived: DerivedStats
    weapon: Weapon
    effects: tuple[str,...]
    equipment_revision: int
    skill_revision: int
    # None means no complete active observation; () means observed none.
    active_skill_ids: tuple[int,...] | None = field(default=None,compare=False)

    armor_revision: int | None = field(default=None,compare=False)
    gear_revision: int | None = field(default=None,compare=False)
    gear_resists: Resists | None = field(default=None,compare=False)

    @property
    def active_skills(self):
        """Compatibility read alias for the 16-policy helper, never a copy.

        A missing complete observation remains unknown rather than observed().
        The original active_skill_ids field/9arg equality stays unchanged.
        """
        if self.active_skill_ids is None:
            raise ValueError('COMBAT_COMPLETE_ACTIVE_SKILL_OBSERVATION_REQUIRED')
        return self.active_skill_ids

@dataclass(frozen=True)
class _CaptureInputs:
    snapshot: SelectedStatsSnapshot
    binding: object
    base: PcStats
    player: PcStats
    equipment: tuple
    skills: tuple
    lifecycle: object
    lifecycle_now: int
    now: int
    clocks: tuple
    rules: object
    rule_items: tuple

class SelectedStatsSource:
    """Projection only; original selected/commit owners retain all authority.

    Root calls selection_locked after canonical selection setup, then equipment
    and skill refresh hooks at their existing committed boundaries. Retirement
    is detected by original generation/selection identity. There is no arbitrary
    snapshot/document setter and no independent store/commit/RNG authority.
    """
    def __init__(self,owner,*,equipment_rules=(),skill_rules=DEFAULT_SKILL_RULES,reference_buff_policy=None,catalyst_buff_policy=None,armor_stats_policy=None,armor_source=None,gear_stats_policy=None,gear_source=None,progression_owner=None,progression_source=None):
        self.resource_only_stats=False  # Explicit full-SKILL scope; no resource-only constructor mode.
        self.owner=owner
        self.broker=owner.status.broker
        if owner.store.provider is not owner.provider or owner.provider.broker is not self.broker:
            raise ValueError('COMBAT_ACTUAL_CANONICAL_OWNER_REQUIRED')
        if not isinstance(equipment_rules,tuple) or not isinstance(skill_rules,tuple):
            raise ValueError('COMBAT_IMMUTABLE_COLD_RULES_REQUIRED')
        if any(type(r) is not EquipmentRule for r in equipment_rules) or len({r.template for r in equipment_rules})!=len(equipment_rules):
            raise ValueError('COMBAT_UNIQUE_EQUIPMENT_RULES_REQUIRED')
        if any(type(r) is not SkillRule for r in skill_rules) or len({r.spell_id for r in skill_rules})!=len(skill_rules):
            raise ValueError('COMBAT_UNIQUE_SKILL_RULES_REQUIRED')
        self._gear_stats=None
        if gear_stats_policy is not None or gear_source is not None:
            if armor_stats_policy is not None or armor_source is not None:
                raise ValueError('COMBAT_GEAR_ARMOR_POLICIES_EXCLUSIVE')
            from tools.local_original_session.combat_full_gear_stats import FullGearStatsProjection
            self._gear_stats=FullGearStatsProjection(owner,policy=gear_stats_policy,source=gear_source)
        self._armor_stats=None
        if armor_stats_policy is not None or armor_source is not None:
            from tools.local_original_session.combat_armor_stats import ArmorStatsProjection
            self._armor_stats=ArmorStatsProjection(owner,policy=armor_stats_policy,source=armor_source)
        self._progression_owner=None
        self._progression_module=None
        self._progression_snapshot=None
        if progression_owner is not None or progression_source is not None:
            from tools.local_original_session.canonical_feature_bootstrap import SourceModule
            if type(progression_source) is not SourceModule:
                raise ValueError('COMBAT_PROGRESSION_EXACT_SOURCE_REQUIRED')
            progression_module=progression_source.check()
            if (progression_module is not sys.modules.get('tools.local_original_session.progression_owner') or
                progression_module.document is not sys.modules.get('tools.local_original_session.progression_document') or
                progression_module.CurrentProgression is not progression_module.document.CurrentProgression or
                type(progression_owner) is not progression_module.ProgressionOwner or
                progression_owner.resource is not owner or progression_owner.broker is not self.broker or
                self.broker._progression_owner is not progression_owner or
                owner._progression_owner is not progression_owner):
                raise ValueError('COMBAT_PROGRESSION_EXACT_OWNER_REQUIRED')
            self._progression_owner=progression_owner
            self._progression_module=progression_module
        self._reference_active_check=None
        self._catalyst_policy=catalyst_buff_policy
        if catalyst_buff_policy is not None:
            from tools.local_original_session import combat_catalyst_reference as catalyst
            catalyst.require_policy(catalyst_buff_policy)
            if reference_buff_policy is not None:
                raise ValueError('COMBAT_CATALYST_POLICY_EXCLUSIVE_SELECTION_REQUIRED')
            rules=catalyst.reference_skill_rules(policy=catalyst_buff_policy)
            if skill_rules is not DEFAULT_SKILL_RULES and skill_rules!=rules:
                raise ValueError('COMBAT_CATALYST_EXACT_RULE_TABLE_REQUIRED')
            skill_rules=rules
            self._reference_active_check=catalyst.validate_active
        if reference_buff_policy is not None:
            from tools.local_original_session import combat_buff_reference as reference
            if reference_buff_policy!=reference.POLICY:
                raise ValueError('COMBAT_BUFF_REFERENCE_EXPLICIT_POLICY_REQUIRED')
            rules=reference.reference_skill_rules(policy=reference_buff_policy)
            if skill_rules is not DEFAULT_SKILL_RULES and skill_rules!=rules:
                raise ValueError('COMBAT_BUFF_REFERENCE_EXACT_RULE_TABLE_REQUIRED')
            skill_rules=rules
            self._reference_active_check=reference.validate_active
        self._equipment_rules={r.template:r for r in equipment_rules}
        self._skill_rules={r.spell_id:r for r in skill_rules}
        self._binding=None
        self._refresh_refusal=None  # Message only; never retain an exception/frame.
        self._base=None
        self._selection=None
        self._equipment=None
        self._skills=None
        self._snapshot=None
        self._snapshot_key=None
        self._captured_player=None
        self._capture_inputs=None
        self._growth_capture_inputs=None

    def magic_target_locked(self,binding,*,base_resists=None,non_gear_base_resists=None):
        """Typed current PC defender projection; no NPC magic caller is added.

        No current CharacterStore field owns selected elfAttr. Active146
        therefore refuses instead of guessing a class/element or using a
        caller-supplied numeric value as source authority.
        """
        if self._catalyst_policy is None:
            raise ValueError('COMBAT_CATALYST_EXPLICIT_POLICY_REQUIRED')
        from tools.local_original_session import combat_catalyst_reference as catalyst
        return catalyst.project_magic_target(self.capture_locked(binding),
            base_resists=base_resists,non_gear_base_resists=non_gear_base_resists,policy=self._catalyst_policy)


    def _current(self,binding,*,progression_fresh=True):
        b=self.broker;g=binding.generation
        game=b.realm.registry.resolve(binding.writer)
        # Preserve the original predicate order and short-circuit reads.
        if self._binding is None:reason='CACHED_BINDING_NONE'
        elif binding.uid!=self._binding.uid:reason='UID_CHANGED'
        elif binding.writer is not self._binding.writer:reason='WRITER_CHANGED'
        elif g is not self._binding.generation:reason='GENERATION_CHANGED'
        elif binding.operation_lock is not self._binding.operation_lock:reason='LOCK_IDENTITY_CHANGED'
        elif b._inventory_generation is not g:reason='CURRENT_GENERATION_CHANGED'
        elif g.phase!='ACTIVE':reason='GENERATION_NOT_ACTIVE'
        elif g.row['writer'] is not binding.writer:reason='ROW_WRITER_CHANGED'
        elif g.row['operation_lock'] is not binding.operation_lock:reason='ROW_LOCK_CHANGED'
        elif not binding.operation_lock.locked():reason='ROW_LOCK_NOT_HELD'
        elif game is None:reason='CURRENT_GAME_MISSING'
        elif game.selection is not self._selection:reason='CURRENT_SELECTION_CHANGED'
        else:reason=None
        if reason is not None:
            message='COMBAT_SELECTED_GENERATION_RETIRED_OR_UNLOCKED:'+reason
            if reason=='CACHED_BINDING_NONE' and self._refresh_refusal is not None:
                message+=':REFRESH_BINDING_OR_SELECTION:'+self._refresh_refusal
            raise ValueError(message)
        if progression_fresh and self._progression_owner is not None:
            self._progression_owner.require_current_locked(binding,self._progression_snapshot)
        return game

    def _progression_read(self,binding):
        current=self._progression_owner.current_locked(binding)
        if (type(current) is not self._progression_module.CurrentProgression or
            current._owner is not self._progression_owner or current._binding is not binding or
            current._generation is not binding.generation or current._row is not binding.generation.row or
            current.uid!=binding.uid):
            raise ValueError('COMBAT_PROGRESSION_SAME_CURRENT_BINDING_REQUIRED')
        return current

    def progression_changed_locked(self,binding):
        """Original progression commit hook; no scalar level/HP or grant input."""
        self._current(binding,progression_fresh=False)
        if self._progression_owner is None:
            raise ValueError('COMBAT_PROGRESSION_EXACT_OWNER_REQUIRED')
        current=self._progression_read(binding)
        if current.reference!=self._selection.reference:
            raise ValueError('COMBAT_PROGRESSION_SELECTED_REFERENCE_CHANGED')
        self._base=PcStats(current.creation,current.permanent,current.character_class,current.level)
        self._progression_snapshot=current
        self._snapshot=self._snapshot_key=None

    def configure_cast_preview_sources(self, *, resource_source, skill_source):
        """Explicit cold opt-in; existing SourceModule checks own file admission."""
        from tools.local_original_session.canonical_feature_bootstrap import SourceModule
        if (hasattr(self,'_cast_preview_sources') or type(resource_source) is not SourceModule
            or type(skill_source) is not SourceModule
            or resource_source.sha256!='de1e70a4995be09a9dbbcccc01ab8759e24ead8e4ecc1857685f71fe4623fa27'
            or skill_source.sha256!='8e710d7d007b919b7dfffcc64935518d5b46099196d3a9e87e834fbfe0f1bb73'):
            raise ValueError('COMBAT_CAST_EXACT_COLD_SOURCES_REQUIRED')
        resource,skill=resource_source.check(),skill_source.check()
        if (type(self.owner) is not resource.ResourceOwner or self.owner.skill_schema is None
            or type(self.owner.skill_schema) is not skill.SkillDocument
            or sys.modules.get('tools.local_original_session.hp_resource_owner') is not resource
            or self.owner._combat_stats is not self):
            raise ValueError('COMBAT_CAST_ACTUAL_OWNER_CLASS_SPACE_REQUIRED')
        functions=(resource.ResourceOwner.validate_plan,resource.ResourceOwner.plan_digest,
                   skill.SkillDocument.cast_event_plans)
        self._cast_preview_sources=(resource_source,skill_source,resource,skill,
            tuple((f,f.__code__) for f in functions),skill._SOURCE)

    def _cast_preview_source_memory(self):
        config=getattr(self,'_cast_preview_sources',None)
        if config is None:raise ValueError('COMBAT_CAST_SOURCE_OPTIN_REQUIRED')
        rs,ss,resource,skill,functions,registry=config
        if (rs.module is not resource or ss.module is not skill
            or rs.sha256!='de1e70a4995be09a9dbbcccc01ab8759e24ead8e4ecc1857685f71fe4623fa27'
            or ss.sha256!='8e710d7d007b919b7dfffcc64935518d5b46099196d3a9e87e834fbfe0f1bb73'
            or sys.modules.get(resource.__name__) is not resource or sys.modules.get(skill.__name__) is not skill
            or type(self.owner) is not resource.ResourceOwner or type(self.owner.skill_schema) is not skill.SkillDocument
            or self.owner._combat_stats is not self or skill._SOURCE is not registry
            or tuple(f for f,c in functions)!=(resource.ResourceOwner.validate_plan,resource.ResourceOwner.plan_digest,skill.SkillDocument.cast_event_plans)
            or any(f.__code__ is not c for f,c in functions)):
            raise ValueError('COMBAT_CAST_SELECTED_SOURCE_CHANGED')
        return resource,skill

    def _cast_after_data(self, inputs, plan):
        before=plan.skill_before['characters'][str(inputs.binding.uid)]
        row=plan.skill_after['characters'][str(inputs.binding.uid)]
        now=plan.accepted_now_ms
        if (type(now) is not int or now<0
            or type(before['clock']) is not int or not 0<=before['clock']<=now
            or type(row['clock']) is not int or row['clock']!=now
            or type(inputs.now) is not int or inputs.now<0):
            raise ValueError('COMBAT_CAST_EXACT_ACCEPTED_CLOCK_REQUIRED')
        before_buffs=tuple(sorted((int(spell),expiry) for spell,expiry in before['buffs'].items()))
        if (before['revision'],before['clock'],before_buffs)!=inputs.skills:
            raise ValueError('COMBAT_CAST_COMPLETE_BEFORE_SKILLS_CHANGED')
        before_active=tuple(spell for spell,expiry in before_buffs if expiry>now)
        if before_active!=inputs.snapshot.active_skills:
            raise ValueError('COMBAT_CAST_BEFORE_ACCEPTED_EXPIRY_CONFLICT')
        active=tuple(sorted(int(spell) for spell,expiry in row['buffs'].items() if expiry>now))
        if inputs.now>now:
            observed_active=tuple(sorted(int(spell) for spell,expiry in row['buffs'].items() if expiry>inputs.now))
            if active!=observed_active:
                raise ValueError('COMBAT_CAST_AFTER_OBSERVATION_EXPIRY_CONFLICT')
        if self._reference_active_check is not None:self._reference_active_check(active)
        modifiers=[]
        for spell in active:
            rule=self._skill_rules.get(spell)
            if rule is None:raise ValueError('COMBAT_ACTIVE_SKILL_POLICY_UNSUPPORTED')
            modifiers.append(replace(rule.modifier,source_id=f'skill:{spell}:{rule.modifier.source_id}'))
        return derive_stats(replace(inputs.player,skills=tuple(modifiers))),active,now

    def preview_cast_context_locked(self,binding,context):
        """Read only the owner's live pre-seal context; no provisional registration."""
        resource,skill=self._cast_preview_source_memory()
        owner=self.owner
        if (type(context) is not resource._CastStatsContext or owner._cast_stats_context is not context
            or context.owner is not owner or context.binding is not binding
            or context.operation is not context.plan.operation
            or context.operation.binding is not binding or owner._prepared_operation is not context.operation
            or owner._cast_stats_plan is not context.plan or owner._cast_stats_enabled is not self
            or context.skill_before is not context.plan.skill_before or context.skill_after is not context.plan.skill_after
            or context.accepted_now_ms!=context.plan.accepted_now_ms or context.plan.phase!='PLANNED'
            or context.plan.stats_preview is not None or skill._SOURCE.get(context.plan) is not None):
            raise ValueError('COMBAT_CAST_SOURCE_BUILD_CONTEXT_REQUIRED')
        plan=context.plan
        events=plan.operation.semantic_result['events']
        if not events or events[-1].get('spell_id') not in (25,41):
            raise ValueError('COMBAT_CAST_STR_DEX_ONLY')
        before=self.capture_locked(binding);inputs=self._capture_inputs
        cap=self.owner.store.capabilities['SKILL'];key=cap.key(binding.uid)
        participant=self.owner.store.data['participants'][key]
        row=plan.skill_before['characters'][str(binding.uid)]
        observed=(row['revision'],row['clock'],tuple(sorted((int(s),e) for s,e in row['buffs'].items())))
        change=next(c for c in plan.changes if c.name=='SKILL')
        if (inputs is None or inputs.snapshot is not before or inputs.binding is not binding
            or observed!=inputs.skills or participant['document']!=plan.skill_before
            or change.expected_revision!=participant['revision'] or change.expected_digest!=participant['digest']
            or change.document!=plan.skill_after):
            raise ValueError('COMBAT_CAST_CURRENT_FULL_SKILL_PREIMAGE_REQUIRED')
        after,active,now=self._cast_after_data(inputs,plan)
        return CastStatsPreview(self,plan,plan.operation,inputs,before,after,active,now,
            cap,key,
            self.owner.batch.digest(plan.skill_before),self.owner.batch.digest(plan.skill_after),
            (self._progression_snapshot,self._gear_stats,self._armor_stats,self._reference_active_check,self._cast_preview_sources))

    def cast_plan_stats_payload(self,preview):
        """Only serialized calculation DATA enters the original source fingerprint."""
        if (type(preview) is not CastStatsPreview or preview.issuer is not self
            or preview.plan.stats_preview is not preview
            or preview.operation is not preview.plan.operation
            or preview.inputs.snapshot is not preview.before):
            raise ValueError('COMBAT_CAST_OWNER_BOUND_DATA_REQUIRED')
        # Fingerprint DATA remains serializable after the producer slot is retired.
        # Native permission/current hooks separately rederive and validate it.
        return dict(uid=preview.before.uid,accepted_now_ms=preview.now,
            before_derived=asdict(preview.before.derived),after_derived=asdict(preview.after),
            active_skills=list(preview.active_skills),before_active_skills=list(preview.before.active_skills),
            equipment_revision=preview.before.equipment_revision,skill_revision=preview.before.skill_revision,
            armor_revision=preview.before.armor_revision,gear_revision=preview.before.gear_revision,
            skill_before_digest=preview.skill_before_digest,skill_after_digest=preview.skill_after_digest)

    def preview_cast_plan_locked(self,binding,plan):
        """Actual registered builder data, revalidated; no second capture or new seal."""
        resource,skill=self._cast_preview_source_memory()
        if type(plan) is not resource.CastPlan or plan.operation.binding is not binding:
            raise ValueError('COMBAT_CAST_REAL_PLAN_BINDING_REQUIRED')
        resource.ResourceOwner.validate_plan(self.owner,plan)
        # validate_plan already consumes the actual sealed preview memory hook.
        return plan.stats_preview

    def _cast_preview_memory(self,binding,preview,*,committed):
        resource,skill=self._cast_preview_source_memory()
        if type(preview) is not CastStatsPreview or preview.issuer is not self:
            raise ValueError('COMBAT_CAST_EXACT_PREVIEW_REQUIRED')
        plan=preview.plan;inputs=preview.inputs
        registered=skill._SOURCE.get(plan)
        self._current(binding,progression_fresh=False)
        if (type(plan) is not resource.CastPlan or plan.operation is not preview.operation
            or plan.operation.binding is not binding or self._capture_inputs is not inputs
            or inputs.binding is not binding or inputs.snapshot is not preview.before
            or self._snapshot is not preview.before or self._base is not inputs.base
            or self._captured_player is not inputs.player or self._equipment is not inputs.equipment
            or self._skills is not inputs.skills or self._skill_rules is not inputs.rules
            or tuple(self._skill_rules.items())!=inputs.rule_items
            or getattr(self.broker,'_buff_lifecycle',None) is not inputs.lifecycle
            or inputs.lifecycle.owner is not self.owner
            or any(getattr(self.owner,name,None) is not clocks or clocks.get(id(binding.writer))!=selected
                   for name,clocks,selected in inputs.clocks)
            or self.owner.store.capabilities['SKILL'] is not preview.skill_capability
            or preview.skill_capability.key(binding.uid)!=preview.skill_key
            or self.owner._cast_stats_plan is not plan or plan.stats_preview is not preview
            or registered is None or registered[0]() is not self.owner
            or self.owner.plan_digest(plan)!=registered[1]
            or self.owner.batch.digest(plan.skill_before)!=preview.skill_before_digest
            or self.owner.batch.digest(plan.skill_after)!=preview.skill_after_digest):
            raise ValueError('COMBAT_CAST_PREVIEW_CURRENT_MEMORY_CHANGED')
        if any(a is not b for a,b in zip(preview.anchors,
               (self._progression_snapshot,self._gear_stats,self._armor_stats,self._reference_active_check,self._cast_preview_sources))):
            raise ValueError('COMBAT_CAST_BASE_POLICY_SOURCE_CHANGED')
        if self._progression_snapshot is not None:
            pkey=self.owner.store.capabilities['PROGRESSION'].key(binding.uid)
            if self.owner.store.data['participants'][pkey]['digest']!=self._progression_snapshot.progression_digest:
                raise ValueError('COMBAT_CAST_PROGRESSION_MEMORY_CHANGED')
        if self._gear_stats is not None:
            current=self._gear_stats.equipment_locked(binding,self._selection)
            if any(a is not b for a,b in zip(current,inputs.equipment)):
                raise ValueError('COMBAT_CAST_GEAR_MEMORY_CHANGED')
        else:
            effect,life,state,weapon,modifiers,preparation=inputs.equipment
            if self.broker._item_equipment_effect is not effect or effect._selection is not life or life.get('state') is not state:
                raise ValueError('COMBAT_CAST_EQUIPMENT_MEMORY_CHANGED')
            if self._preparation(effect,binding,life,state) is not preparation:
                raise ValueError('COMBAT_CAST_PREPARATION_MEMORY_CHANGED')
        if self._armor_stats is not None:
            effect,life,state,weapon,equipment,preparation=inputs.equipment
            armor,revision=self._armor_stats.modifiers_locked(binding,effect,life,state,preparation,self._selection)
            if inputs.player.equipment!=equipment+armor or preview.before.armor_revision!=revision:
                raise ValueError('COMBAT_CAST_ARMOR_MEMORY_CHANGED')
        after,active,now=self._cast_after_data(inputs,plan)
        if (after,active,now)!=(preview.after,preview.active_skills,preview.now):
            raise ValueError('COMBAT_CAST_READONLY_AFTER_CHANGED')
        if not committed:
            row=self.owner.store.data['participants'][preview.skill_key]
            if row['document']!=plan.skill_before or row['digest']!=preview.skill_before_digest:
                raise ValueError('COMBAT_CAST_SKILL_MEMORY_CHANGED')
        if not committed and (plan.phase!='PLANNED' or self.owner._prepared_operation is not plan.operation
                              or self.owner._prepared_digest!=registered[1]):
            raise ValueError('COMBAT_CAST_PRECOMMIT_PLAN_SLOT_CHANGED')
        return resource

    def validate_cast_preview_precommit_memory_locked(self,binding,preview):
        self._cast_preview_memory(binding,preview,committed=False)
        return None

    def validate_cast_preview_commit_memory_locked(self,binding,preview):
        resource=self._cast_preview_memory(binding,preview,committed=True)
        permit=self.owner._projection;op=preview.operation
        if type(permit) is not resource.Projection or permit.operation is not op:
            raise ValueError('COMBAT_CAST_LIVE_NATIVE_PROJECTION_REQUIRED')
        receipt=permit.receipt;store=self.owner.store
        native=store.data['transactions'].get(op.txid)
        skillrow=store.data['participants'].get(preview.skill_key)
        resourcekey=store.capabilities['RESOURCE'].key(binding.uid)
        resourcerow=store.data['participants'].get(resourcekey)
        if (plan_phase_invalid(preview.plan.phase) or native is None or receipt!=native
            or native['phase']!='COMMITTED' or store.data['pending'] is not None or store.active is not None
            or skillrow is None or skillrow['document']!=preview.plan.skill_after
            or skillrow['digest']!=preview.skill_after_digest
            or native['participants'].get(preview.skill_key)!=skillrow['digest']
            or resourcerow is None or resourcerow['document']!=op.after
            or native['participants'].get(resourcekey)!=resourcerow['digest']
            or resourcerow['digest']!=permit.resource_digest):
            raise ValueError('COMBAT_CAST_NATIVE_COMMITTED_PARTICIPANTS_REQUIRED')
        return None

    def preview_progression_locked(self,binding,stage):
        """One original full capture; actual typed award only, no cache level edit."""
        module=self._progression_module
        if (self._progression_owner is None or type(stage) is not module._Award
            or stage.stats is not self or stage.binding is not binding
            or stage.result.levels_gained<=0):
            raise ValueError('COMBAT_ORIGINAL_FULL_SKILL_GROWTH_STAGE_REQUIRED')
        if self._progression_owner.require_award_locked(binding,stage) is not stage:
            raise ValueError('COMBAT_ORIGINAL_GROWTH_STAGE_REQUIRED')
        before=self.capture_locked(binding)
        inputs=self._capture_inputs
        if (inputs is None or inputs.snapshot is not before or inputs.binding is not binding
            or inputs.player.level!=stage.result.before_level):
            raise ValueError('COMBAT_FULL_SKILL_CAPTURE_ALREADY_SEALED_OR_FOREIGN')
        after=derive_stats(replace(inputs.player,level=stage.result.after_level))
        return before,after

    def _record_capture_inputs(self,snapshot,binding,lifecycle,lifecycle_now,now,clocks):
        previous=self._capture_inputs
        proof=getattr(self.owner,'_progression_growth',None)
        module=None if self._progression_owner is None else self._progression_owner.resource_module
        # The original resource permit seals this exact beforeSnapshot. Ordinary
        # observations cannot retime its input record while the permit is live.
        if (previous is not None and self._growth_capture_inputs is None
            and proof is not None and module is not None and type(proof) is module._ProgressionGrowth
            and proof.stats is self and proof.before_stats is previous.snapshot):
            return
        self._capture_inputs=_CaptureInputs(snapshot,binding,self._base,self._captured_player,
            self._equipment,self._skills,lifecycle,lifecycle_now,now,clocks,
            self._skill_rules,tuple(self._skill_rules.items()))

    def capture_locked(self,binding):
        """Original live capture, or one exact committed permit observation."""
        if self._growth_capture_inputs is not None:
            raise ValueError('COMBAT_FULL_SKILL_CAPTURE_REENTRY_REFUSED')
        resource=self.owner;module=(None if self._progression_owner is None else
                                  self._progression_owner.resource_module)
        proof=getattr(resource,'_progression_growth',None)
        caller=sys._getframe(1)
        try:
            if module is not None and proof is not None:
                function=module.ResourceOwner.project_progression_committed
                if caller.f_code is function.__code__ and caller.f_globals is module.__dict__:
                    owner=self._progression_owner;stage=proof.stage;inputs=self._capture_inputs
                    committed=owner._committed_award
                    if not (type(proof) is module._ProgressionGrowth and proof.owner is owner
                        and proof.stats is self and stage is owner._award and stage.stats is self
                        and type(stage) is self._progression_module._Award
                        and stage.binding is binding and proof.operation.binding is binding
                        and proof.operation is resource._operation is resource._prepared_operation
                        and proof.operation is owner._growth_operation
                        and caller.f_locals.get('proof') is proof
                        and caller.f_locals.get('stats') is self
                        and caller.f_locals.get('operation') is proof.operation
                        and caller.f_locals.get('stage') is stage
                        and caller.f_locals.get('progression_owner') is owner
                        and type(committed) is tuple and len(committed)==5
                        and committed[0] is stage and committed[1]['phase']=='COMMITTED'
                        and caller.f_locals.get('receipt')==committed[1]
                        and owner.store._raw is committed[2]
                        and owner.store.data['participants']['PROGRESSION:'+str(binding.uid)] is committed[3]
                        and owner.store.data['participants']['RESOURCE:'+str(binding.uid)] is committed[4]
                        and inputs is not None and inputs.snapshot is proof.before_stats
                        and inputs.binding is binding and inputs.equipment is self._equipment
                        and inputs.skills is self._skills and inputs.rules is self._skill_rules
                        and inputs.rule_items==tuple(self._skill_rules.items())
                        and inputs.lifecycle is self.broker._buff_lifecycle
                        and inputs.player.level==stage.result.before_level
                        and self._base.level==stage.result.after_level==proof.derived.level
                        and self._base.creation==inputs.base.creation
                        and self._base.permanent==inputs.base.permanent
                        and self._base.character_class==inputs.base.character_class
                        and all(getattr(resource,name,None) is clocks
                            and (None if clocks is None else clocks.get(id(binding.writer))) is selected
                            for name,clocks,selected in inputs.clocks)):
                        raise ValueError('COMBAT_FULL_SKILL_EXACT_COMMITTED_CAPTURE_INPUTS_REQUIRED')
                    self._growth_capture_inputs=inputs
            return self._capture_live_locked(binding)
        finally:
            # No staged Award/proof is retained by the Stats cache. This transient
            # view is removed even on failure/cancellation; ordinary clock stays live.
            self._growth_capture_inputs=None
            del caller

    def selection_locked(self,binding):
        """Call inside existing selected lock, after actual canonical setup."""
        self.owner.provider.current(binding)
        b=self.broker;game=b.realm.registry.resolve(binding.writer)
        if (game is None or game.selection is None or b._inventory_generation is not binding.generation or
            binding.generation.phase!='ACTIVE' or not binding.operation_lock.locked()):
            raise ValueError('COMBAT_REAL_SELECTED_BINDING_REQUIRED')
        # Actual CharacterStore owner, not unbound supplied INFO/dictionary.
        uid,info=b.realm.store.select(game.selection.reference)
        if uid!=binding.uid or info[1]!=game.selection.reference or info[3] not in LOCAL_CLASS_NAMES:
            raise ValueError('COMBAT_SELECTED_CHARACTER_INFO_MISMATCH')
        stats=Stats(info[11],info[12],info[13],info[16],info[14],info[15])
        # Default remains creation-only. Explicit progression uses its actual
        # original owner current; raw saved INFO keeps immutable initial level.
        progression=None
        if self._progression_owner is None:
            if info[10]!=1:
                raise ValueError('COMBAT_CREATION_ONLY_STORE_LEVEL_UNSUPPORTED')
        else:
            progression=self._progression_read(binding)
            if (progression.reference!=game.selection.reference or
                progression.character_class!=LOCAL_CLASS_NAMES[info[3]] or
                progression.permanent!=stats or
                info[10]!=self._progression_owner.store.data['participants'][
                    'PROGRESSION:'+str(binding.uid)]['document']['initial']['level']):
                raise ValueError('COMBAT_PROGRESSION_SAVED_INFO_MISMATCH')
        self._binding=binding;self._selection=game.selection
        self._refresh_refusal=None
        self._base=(PcStats(stats,stats,LOCAL_CLASS_NAMES[info[3]],info[10]) if progression is None else
                    PcStats(progression.creation,progression.permanent,progression.character_class,progression.level))
        self._progression_snapshot=progression
        self._capture_inputs=self._captured_player=None
        self._equipment=self._skills=self._snapshot=self._snapshot_key=None
        if self._armor_stats is not None:self._armor_stats.clear()
        if self._gear_stats is not None:self._gear_stats.clear()

    def equipment_changed_locked(self,binding):
        """Call after existing equipment initial sync/commit, no disk sampling."""
        self._current(binding)
        if self._gear_stats is not None:
            self._equipment=self._gear_stats.refresh_locked(binding,self._selection)
            self._snapshot=None
            return
        effect=getattr(self.broker,'_item_equipment_effect',None)
        if getattr(effect,'_gear',None) is not None:
            raise ValueError('COMBAT_FULL_GEAR_STATS_POLICY_UNSUPPORTED')
        life=getattr(effect,'_selection',None)
        if effect is None or effect.broker is not self.broker or not isinstance(life,dict):
            raise ValueError('COMBAT_ACTUAL_EQUIPMENT_SELECTION_REQUIRED')
        identity=life.get('identity');state=life.get('state')
        if (not isinstance(identity,tuple) or len(identity)!=7 or
            identity[0] is not binding.writer or identity[1] is not binding.generation or
            identity[3] is not self._selection or state is None or state.character_uid!=binding.uid):
            raise ValueError('COMBAT_COMMITTED_EQUIPMENT_STATE_REQUIRED')
        # Validate supported real source object type once at its original change
        # boundary, not via serialization/schema on every attack.
        from tools.local_original_session.equipment_store import EquipmentState
        if type(state) is not EquipmentState:
            raise ValueError('COMBAT_SOURCE_EQUIPMENT_STATE_REQUIRED')
        preparation=self._preparation(effect,binding,life,state)
        if state.weapon_uid==0:
            weapon=Weapon('fist',0,0);modifiers=()
        else:
            rule=self._equipment_rules.get(state.template)
            if rule is None:
                raise ValueError('COMBAT_EQUIPPED_TEMPLATE_POLICY_UNSUPPORTED')
            # This source stores a single supported weapon-template family.
            # No opaque ItemInfo field is renamed STR/enchant/damage.
            weapon=rule.weapon
            modifiers=tuple(replace(m,source_id=f'equipment:{state.weapon_uid}:{m.source_id}') for m in rule.modifiers)
        if self._armor_stats is not None:
            self._armor_stats.refresh_locked(binding,effect,life,state,preparation,self._selection)
        self._equipment=(effect,life,state,weapon,modifiers,preparation)
        self._snapshot=None

    @staticmethod
    def _preparation(effect,binding,life,state):
        if life.get('synced') is True:
            return None
        # Accepted empty/unequipped source intentionally has synced=False:
        # use its original typed, source-issued lifetime witness, never a
        # server_ready boolean as a replacement for notification authority.
        module=sys.modules.get(type(effect).__module__)
        accessor=getattr(module,'_SERVER_PREPARATION_ACCESSOR',None)
        method=getattr(effect,'server_preparation_memory',None)
        if (module is None or type(effect) is not getattr(module,'ItemEquipmentEffect',None) or
            accessor is None or getattr(method,'__func__',None) is not accessor):
            raise ValueError('COMBAT_TYPED_ZERO_PREPARATION_REQUIRED')
        record=accessor(effect,binding.writer)
        if (type(record) is not getattr(module,'ServerPreparationMemory',None) or
            record is not effect._server_preparation or record._life is not life or
            record.state is not state or record.writer is not binding.writer or
            record.generation is not binding.generation or state.weapon_uid!=0):
            raise ValueError('COMBAT_TYPED_ZERO_PREPARATION_REQUIRED')
        return record

    def skills_changed_locked(self,binding):
        """Call after existing SKILL setup or canonical commit; one owner read."""
        self._current(binding)
        participant=self.owner.store.participant(binding,'SKILL')
        row=participant['document']['characters'][str(binding.uid)]
        # The original participant reader validates its own schema. Freeze only
        # fields consumed by combat, rather than repeat that validation here.
        buffs=tuple(sorted((int(spell),expiry) for spell,expiry in row['buffs'].items()))
        self._skills=(row['revision'],row['clock'],buffs)
        self._snapshot=None

    def _capture_live_locked(self,binding):
        """Existing operation callback; memory-only, no producer/Store rereads."""
        self._current(binding)
        if self._base is None or self._equipment is None or self._skills is None:
            raise ValueError('COMBAT_SELECTED_PRODUCER_SETUP_INCOMPLETE')
        armor=();armor_revision=None;gear_revision=None;gear_resists=None
        if self._gear_stats is not None:
            current=self._gear_stats.equipment_locked(binding,self._selection)
            if any(a is not b for a,b in zip(current,self._equipment)):
                raise ValueError('COMBAT_FULL_GEAR_EQUIPMENT_CACHE_CHANGED')
            effect,life,state,weapon,equipment,preparation=current
            gear_revision=state.revision
            gear_resists=self._gear_stats._cached.resists
        else:
            effect,life,state,weapon,equipment,preparation=self._equipment
            if getattr(effect,'_gear',None) is not None:
                raise ValueError('COMBAT_FULL_GEAR_STATS_POLICY_UNSUPPORTED')
            if (self.broker._item_equipment_effect is not effect or effect._selection is not life or
                life.get('state') is not state):
                raise ValueError('COMBAT_EQUIPMENT_CHANGED_REFRESH_REQUIRED')
            if self._preparation(effect,binding,life,state) is not preparation:
                raise ValueError('COMBAT_EQUIPMENT_PREPARATION_CHANGED')
            if self._armor_stats is not None:
                armor,armor_revision=self._armor_stats.modifiers_locked(binding,effect,life,state,preparation,self._selection)
            elif getattr(effect,'_armor',None) is not None:
                raise ValueError('COMBAT_ARMOR_STATS_POLICY_UNSUPPORTED')
        revision,clock,buffs=self._skills
        lifecycle=getattr(self.broker,'_buff_lifecycle',None)
        if lifecycle is None or lifecycle.owner is not self.owner:
            raise ValueError('COMBAT_CANONICAL_BUFF_LIFECYCLE_REQUIRED')
        observed=self._growth_capture_inputs
        if observed is None:
            lifecycle_now=lifecycle._now()
            now=max(clock,lifecycle_now)
            clock_inputs=[]
            # Existing owner selected clock is generation-bound. Both known owner
            # versions name their same-purpose field explicitly.
            for field_name in ('_selection_clocks','_shield_world_clock'):
                clocks=getattr(self.owner,field_name,None)
                selected=clocks.get(id(binding.writer)) if clocks is not None else None
                clock_inputs.append((field_name,clocks,selected))
                if selected is not None:
                    if selected[0] is not binding.generation:
                        raise ValueError('COMBAT_SKILL_CLOCK_GENERATION_CHANGED')
                    now=max(now,selected[1])
            active=tuple(spell for spell,expiry in buffs if expiry>now)
            clock_inputs=tuple(clock_inputs)
        else:
            # Source permit consumes a previous actual observation, never sets
            # lifecycle time or writes canonical SKILL expiry/clock.
            lifecycle_now,now,clock_inputs=observed.lifecycle_now,observed.now,observed.clocks
            active=observed.snapshot.active_skills
        if self._reference_active_check is not None:
            self._reference_active_check(active)
        key=(state.revision,revision,active) if armor_revision is None else (state.revision,revision,active,armor_revision)
        if self._snapshot is not None and self._snapshot_key==key:
            self._record_capture_inputs(self._snapshot,binding,lifecycle,lifecycle_now,now,clock_inputs)
            return self._snapshot
        modifiers=[];effects=[]
        for spell in active:
            rule=self._skill_rules.get(spell)
            if rule is None:
                raise ValueError('COMBAT_ACTIVE_SKILL_POLICY_UNSUPPORTED')
            modifiers.append(replace(rule.modifier,source_id=f'skill:{spell}:{rule.modifier.source_id}'))
            if rule.physical_effect is not None:effects.append(rule.physical_effect)
        player=replace(self._base,equipment=equipment+armor,skills=tuple(modifiers))
        derived=derive_stats(player)
        self._captured_player=player
        self._snapshot=SelectedStatsSnapshot(binding.uid,binding.writer,binding.generation,self._selection,
            derived,weapon,tuple(effects),state.revision,revision,active_skill_ids=active,armor_revision=armor_revision,gear_revision=gear_revision,gear_resists=gear_resists)
        self._snapshot_key=key
        self._record_capture_inputs(self._snapshot,binding,lifecycle,lifecycle_now,now,clock_inputs)
        return self._snapshot


def plan_phase_invalid(phase):
    # _commit_and_project projects before _commit_cast_plan changes phase.
    return phase not in ('PLANNED','COMMITTED')


@dataclass(frozen=True)
class CastStatsPreview:
    """Readonly calculated data; never an operation/current/native permit."""
    issuer: object
    plan: object
    operation: object
    inputs: object
    before: SelectedStatsSnapshot
    after: DerivedStats
    active_skills: tuple
    now: int
    skill_capability: object
    skill_key: str
    skill_before_digest: str
    skill_after_digest: str
    anchors: tuple
