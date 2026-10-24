"""Explicit full-SKILL canonical bootstrap contact for a NEW source roster.

Use the original plan.bind_combat_setup with a SourceModule for this module.
Original create_broker creates/attaches ResourceOwner, SKILL and lifecycle before
calling bind_cold. No participant initializer, stat seed or runtime is issued.
"""
from dataclasses import replace
from tools.local_original_session import source_roster_combat as roster
from tools.local_original_session import combat_selected_stats as selected
from tools.local_original_session import combat_trial_inputs as trial


def need(value, reason):
    if not value:
        raise ValueError(reason)


def _bind_cast_stats_cold(owner, stats, sources):
    """Explicit actual SourceModule tuple, after original installed cache only."""
    if sources is None:return
    from tools.local_original_session.canonical_feature_bootstrap import SourceModule
    need(type(sources) is tuple and len(sources)==3
         and all(type(source) is SourceModule for source in sources),
         'COMBAT_CAST_COLD_ACTUAL_SOURCE_TUPLE_REQUIRED')
    resource_source,stats_source,skill_source=sources
    need(resource_source.sha256=='de1e70a4995be09a9dbbcccc01ab8759e24ead8e4ecc1857685f71fe4623fa27'
         and stats_source.sha256=='97dc660f31c6403bc130a5de569f5d35fed54dac6a1d923f22079f97c00907af'
         and skill_source.sha256=='8e710d7d007b919b7dfffcc64935518d5b46099196d3a9e87e834fbfe0f1bb73'
         and stats_source.module is selected and type(stats) is selected.SelectedStatsSource
         and owner._combat_stats is stats and stats.owner is owner
         and type(owner) is resource_source.module.ResourceOwner
         and type(owner.skill_schema) is skill_source.module.SkillDocument,
         'COMBAT_CAST_COLD_EXACT_INSTALLED_CLASS_SPACE_REQUIRED')
    # Existing Stats cold API checks Resource/SKILL SourceModules once; no new file check.
    stats.configure_cast_preview_sources(resource_source=resource_source,skill_source=skill_source)
    owner.enable_cast_stats_preview(stats)


def _prepare_selected_stats_cold(plan, broker, owner, *, weight_factory, equipment_rules=(), reference_buff_policy=None,
        catalyst_buff_policy=None, armor_stats_policy=None, armor_source=None,
        gear_stats_policy=None, gear_source=None, resource_only_stats=False, progression_source=None):
    """Original full-SKILL construction shared by both cold entry points."""
    lifecycle = getattr(broker, '_buff_lifecycle', None)
    need(type(resource_only_stats) is bool, 'COMBAT_EXPLICIT_RESOURCE_ONLY_STATS_REQUIRED')
    if resource_only_stats:
        need(plan.resource_only and plan.buff is None and not broker._started
             and broker._hp_resource_owner is owner and owner.skill_schema is None
             and lifecycle is None and reference_buff_policy is None and catalyst_buff_policy is None,
             'ROSTER_SETUP_EXACT_RESOURCE_ONLY_OWNER_REQUIRED')
    else:
        need(not plan.resource_only
             and plan.buff is not None and not broker._started
             and broker._hp_resource_owner is owner and owner.skill_schema is not None
             and lifecycle is not None and lifecycle.owner is owner,
             'ROSTER_SETUP_REAL_FULL_SKILL_OWNER_REQUIRED')
    armor_options = ({} if armor_stats_policy is None and armor_source is None else
        dict(armor_stats_policy=armor_stats_policy, armor_source=armor_source))
    gear_options = ({} if gear_stats_policy is None and gear_source is None else
        dict(gear_stats_policy=gear_stats_policy, gear_source=gear_source))
    scope_options = dict(resource_only_stats=True) if resource_only_stats else {}
    progression_options = ({} if progression_source is None else
        dict(progression_source=progression_source, progression_owner=broker._progression_owner))
    stats = selected.SelectedStatsSource(owner, equipment_rules=equipment_rules,
        reference_buff_policy=reference_buff_policy,
        catalyst_buff_policy=catalyst_buff_policy, **armor_options, **gear_options, **scope_options, **progression_options)
    weight = weight_factory(owner, stats)
    need(type(weight) in (trial.EmptyInventoryWeight, trial.CurrentInventoryWeight)
         and weight.owner is owner
         and (type(weight) is trial.EmptyInventoryWeight or weight._selected_stats is stats),
         'ROSTER_SETUP_EXISTING_CURRENT_WEIGHT_OWNER_REQUIRED')
    return stats, weight


def install_selected_stats_cold(plan, broker, owner, *, weight_factory, equipment_rules=(), reference_buff_policy=None,
        catalyst_buff_policy=None, armor_stats_policy=None, armor_source=None,
        gear_stats_policy=None, gear_source=None, cast_stats_sources=None):
    """Install existing selected/weight caches after genuine prepare, before start.

    No NPC authority, character selection, refresh, or skill grant is issued.
    The caller owns the exact full-SKILL Plan and explicit source policies.
    """
    from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap
    from tools.local_original_session.buff_bootstrap import BuffBootstrap
    generation = getattr(broker, '_inventory_generation', None)
    buff = plan.buff
    lifecycle = getattr(broker, '_buff_lifecycle', None)
    def current():
        return (type(plan) is CanonicalFeatureBootstrap and plan._lifetime_state == 'BOUND'
         and plan._broker is broker and plan._owner is owner
         and type(plan.buff) is BuffBootstrap and plan.buff.broker is broker
         and lifecycle is not None and plan.buff.service is lifecycle and lifecycle.owner is owner and not plan.buff.closed
         and broker._hp_resource_owner is owner and not plan.resource_only
         and owner.skill_schema is not None
         and not broker._started and not broker._closing
         and generation is not None and broker._inventory_generation is generation
         and broker._buff_lifecycle is lifecycle and plan.buff is buff
         and generation.broker is broker
         and generation.phase == 'ACTIVE'
         and type(generation.frame) is bytes and generation.frame is broker._inventory_config_frame
         and all(getattr(generation, name) is None for name in
                 ('writer', 'row', 'lock', 'game', 'selected', 'mover', 'selection_binding', 'current_frame'))
         and not generation.restored and not generation.attempted and not generation.write_attempted
         and getattr(owner, '_combat_stats', None) is None
         and getattr(owner, '_combat_empty_weight', None) is None)
    need(current(), 'SELECTED_STATS_EXACT_PREPARED_COLD_OWNER_REQUIRED')
    stats, weight = _prepare_selected_stats_cold(plan, broker, owner,
        weight_factory=weight_factory, equipment_rules=equipment_rules,
        reference_buff_policy=reference_buff_policy, catalyst_buff_policy=catalyst_buff_policy,
        armor_stats_policy=armor_stats_policy, armor_source=armor_source,
        gear_stats_policy=gear_stats_policy, gear_source=gear_source)
    need(current(), 'SELECTED_STATS_EXACT_PREPARED_COLD_OWNER_REQUIRED')
    owner._combat_stats, owner._combat_empty_weight = stats, weight
    _bind_cast_stats_cold(owner,stats,cast_stats_sources)
    return stats, weight


def install_selected_stats_full_skill_scoped(plan, broker, owner, *, scope_transition,
        weight_factory, equipment_rules=(), reference_buff_policy=None, catalyst_buff_policy=None,
        armor_stats_policy=None, armor_source=None, gear_stats_policy=None, gear_source=None,
        progression_source=None, cast_stats_sources=None):
    """Original full-SKILL caches in the actual unpublished child attach scope.

    Call after create_broker returns BOUND, before Scope becomes ATTACHED.
    No selection, refresh, NPC, grant or replacement SKILL owner is issued.
    """
    import character_scope
    from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap
    from tools.local_original_session.buff_bootstrap import BuffBootstrap
    token=character_scope.checked_transition(broker,scope_transition)
    controller,generation=token.controller,broker._inventory_generation
    provider,buff,lifecycle=owner.provider,plan.buff,getattr(broker,'_buff_lifecycle',None)
    schema=owner.skill_schema
    frame,ordinal=token.frame,token.ordinal
    def current():
        # Original Scope owns source/function/task/row lock/retirement and
        # unpublished-selection validation. Reuse it, never a startup waiver.
        character_scope.checked_transition(broker,token)
        return (token is scope_transition and token.controller is controller
         and token.phase=='ATTACHING' and token.frame is frame and token.ordinal==ordinal
         and controller.plan is plan and controller.broker is broker
         and type(plan) is CanonicalFeatureBootstrap and plan._lifetime_state=='BOUND'
         and plan._broker is broker and plan._owner is owner
         and plan._character_scopes is controller and plan.profile==controller.selected_profile
         and plan.setup_uid==token.uid==broker.realm.profile_uid and token.uid!=controller.root_uid
         and plan.resource_only is False and plan._without_skill is False
         and type(buff) is BuffBootstrap and plan.buff is plan.normal_buff is buff
         and buff.broker is broker and not buff.closed and buff.service is lifecycle
         and lifecycle is not None and broker._buff_lifecycle is lifecycle
         and lifecycle.owner is owner and lifecycle.schema is schema
         and lifecycle.provider is provider and lifecycle.store is owner.store
         and schema is not None and owner.skill_schema is schema
         and type(owner) is plan.owners.ResourceOwner and broker._hp_resource_owner is owner
         and owner.status is broker._hp_status and owner.status.broker is broker and not owner.status.closed
         and owner.store is plan._batch and owner.store.provider is provider
         and owner.provider is provider is broker._canonical_provider
         and provider is token.new_provider and provider is not token.previous_provider
         and token.new_scope is not None and provider._scope is token.new_scope
         and not owner.store.closed and owner.active is False
         and broker._started is True and not broker._closing
         and broker._inventory_generation is generation and generation.broker is broker
         and generation.scope_previous is token.previous_generation and generation is not token.previous_generation
         and generation.phase=='ACTIVE' and generation.frame is None
         and generation.store is broker._inventory_store
         and all(getattr(generation,name) is None for name in
             ('writer','row','lock','game','selected','mover','selection_binding','current_frame'))
         and not generation.restored and not generation.attempted and not generation.write_attempted
         and getattr(owner,'_combat_stats',None) is None
         and getattr(owner,'_combat_empty_weight',None) is None)
    need(current(),'SELECTED_STATS_EXACT_FULL_SKILL_SCOPE_OWNER_REQUIRED')
    armor_options=({} if armor_stats_policy is None and armor_source is None else
        dict(armor_stats_policy=armor_stats_policy,armor_source=armor_source))
    gear_options=({} if gear_stats_policy is None and gear_source is None else
        dict(gear_stats_policy=gear_stats_policy,gear_source=gear_source))
    progression_options=({} if progression_source is None else
        dict(progression_source=progression_source,progression_owner=broker._progression_owner))
    stats=selected.SelectedStatsSource(owner,equipment_rules=equipment_rules,
        reference_buff_policy=reference_buff_policy,catalyst_buff_policy=catalyst_buff_policy,
        **armor_options,**gear_options,**progression_options)
    weight=weight_factory(owner,stats)
    need(type(weight) in (trial.EmptyInventoryWeight,trial.CurrentInventoryWeight)
         and weight.owner is owner
         and (type(weight) is trial.EmptyInventoryWeight or weight._selected_stats is stats),
         'ROSTER_SETUP_EXISTING_CURRENT_WEIGHT_OWNER_REQUIRED')
    need(current(),'SELECTED_STATS_EXACT_FULL_SKILL_SCOPE_OWNER_REQUIRED')
    owner._combat_stats,owner._combat_empty_weight=stats,weight
    _bind_cast_stats_cold(owner,stats,cast_stats_sources)
    return stats,weight


class CombatSetup:
    def __init__(self, source_roster, *, rng, distance_locked, weight_factory,
                 recovery_inputs_locked, runtime_factory, equipment_rules=(),
                 reference_buff_policy=None, catalyst_buff_policy=None, normal_unequip=False,
                 armor_stats_policy=None, armor_source=None,
                 gear_stats_policy=None, gear_source=None, pc_npc_only=False, resource_only_stats=False,
                 progression_source=None, cast_stats_sources=None):
        need(type(source_roster) is roster.SourceRoster,
             'ROSTER_SETUP_ISSUED_SOURCE_REQUIRED')
        need(type(pc_npc_only) is bool, 'COMBAT_EXPLICIT_SCOPE_REQUIRED')
        need(type(resource_only_stats) is bool and (not resource_only_stats or pc_npc_only
             and reference_buff_policy is None and catalyst_buff_policy is None),
             'COMBAT_RESOURCE_ONLY_REQUIRES_PC_ONLY_NO_SKILL_POLICY')
        self.progression_source = progression_source
        self.cast_stats_sources = cast_stats_sources
        self.resource_only_stats = resource_only_stats
        need(callable(getattr(rng, 'randint', None))
             and all(callable(fn) for fn in (distance_locked, weight_factory))
             and (all(callable(fn) for fn in (recovery_inputs_locked, runtime_factory))
                  if not pc_npc_only else recovery_inputs_locked is None and runtime_factory is None),
             'ROSTER_SETUP_EXPLICIT_EXISTING_INPUT_OWNERS_REQUIRED')
        self.pc_npc_only = pc_npc_only
        need(type(normal_unequip) is bool, 'ROSTER_SETUP_NORMAL_UNEQUIP_EXPLICIT_BOOL_REQUIRED')
        # Permission only: the supplied runtime owns UI/current Use/effect lease.
        self.normal_unequip = normal_unequip
        self.source = source_roster
        self.rng = rng
        self.distance_locked = distance_locked
        self.weight_factory = weight_factory
        self.recovery_inputs_locked = recovery_inputs_locked
        self.runtime_factory = runtime_factory
        self.equipment_rules = equipment_rules
        self.reference_buff_policy = reference_buff_policy
        self.catalyst_buff_policy = catalyst_buff_policy
        self.armor_stats_policy = armor_stats_policy
        self.armor_source = armor_source
        self.gear_stats_policy = gear_stats_policy
        self.gear_source = gear_source
        self.plan = self.features = self.owner = self.published = None
        self.stats = self.weight = None
        self.provider = self.adjudicator = None

    @property
    def use_policy(self):
        # Original full_buff_configured consumes this setup attribute. Its
        # value is still the NPC caller's explicit feature policy, never new.
        return None if self.features is None else self.features.item_use_policy

    def configure_features(self, features):
        """NPC caller retains ALL policies; only new spawn/provider are selected.

        No HP2/Hit1 rows are adopted. Existing trial features may be a caller's
        policy recipe, but its old actor objects/provider never enter this graph.
        """
        from tools.local_original_session.feature_config import Features
        need(type(features) is Features and self.plan is not None
             and features.canonical_bootstrap is self.plan and self.owner is None,
             'ROSTER_SETUP_EXACT_UNBOUND_FEATURES_REQUIRED')
        self.features = replace(features, spawns=self.source.npc_spawns,
                                attack_hp_provider=self.source)
        return self.features

    def require_config(self, config):
        need(config is self.features and config.canonical_bootstrap is self.plan
             and config.spawns is self.source.npc_spawns
             and config.attack_hp_provider is self.source,
             'ROSTER_SETUP_EXACT_COLD_FEATURES_REQUIRED')
        # Same original CombatSetup fields, all supplied by the NPC caller.
        # The NPC owner's separate N configuration branch owns its extra fields.
        return {name:getattr(config, name) for name in (
            'spawns', 'attack_policy', 'attack_hp_provider', 'attack_feedback',
            'npc_death_policy', 'npc_remove_policy', 'npc_player_hit_repeated_policy',
            'interval_ns', 'motion_policy', 'goal_policy', 'player_life_policy',
            'item_use_policy', 'item_equipment_policy', 'item_equipment_first_enable')}

    def bind_cold(self, plan, broker, owner):
        """Original create_broker calls this AFTER full Buff/SKILL attachment."""
        need(plan is self.plan and self.owner is None,
             'ROSTER_SETUP_REAL_FULL_SKILL_OWNER_REQUIRED')
        stats, weight = _prepare_selected_stats_cold(plan, broker, owner,
            weight_factory=self.weight_factory, equipment_rules=self.equipment_rules,
            reference_buff_policy=self.reference_buff_policy,
            catalyst_buff_policy=self.catalyst_buff_policy,
            armor_stats_policy=self.armor_stats_policy, armor_source=self.armor_source,
            gear_stats_policy=self.gear_stats_policy, gear_source=self.gear_source,
            resource_only_stats=self.resource_only_stats, progression_source=self.progression_source)
        published = self.source.register_cold(broker)
        published.install_hp_inputs_cold()
        provider, adjudicator = published.bind_combat_cold(owner, stats, rng=self.rng,
            distance_locked=self.distance_locked, weight240_locked=weight,
            selected_weight240_locked=(weight.with_selected if type(weight) is trial.CurrentInventoryWeight else None),
            recovery_inputs_locked=self.recovery_inputs_locked, pc_npc_only=self.pc_npc_only)
        owner._combat_empty_weight = weight
        _bind_cast_stats_cold(owner,stats,self.cast_stats_sources)
        self.owner, self.published, self.stats, self.weight = owner, published, stats, weight
        self.provider, self.adjudicator = provider, adjudicator

    def bind_scoped(self, plan, broker, owner, *, scope_token, handoff_issuer):
        """Actual create_broker CREATING seam, before BOUND/scope transfer.

        NPC attach owns Session provenance; Root issuer owns the carried lease.
        This constructor performs no selection or current Store/Stats capture.
        """
        from tools.local_original_session import character_scope
        character_scope.checked_transition(broker,scope_token)
        provider=owner.provider
        need(scope_token.phase=='ATTACHING' and not scope_token.recovering
             and plan is self.plan is scope_token.controller.plan and plan._combat_setup is self
             and plan._lifetime_state=='CREATING' and plan._broker is None and plan._owner is None
             and self.features is not None and self.features.canonical_bootstrap is plan
             and self.owner is None and self.published is None and self.stats is None
             and self.provider is None and self.weight is None
             and self.pc_npc_only is True and self.recovery_inputs_locked is None
             and self.runtime_factory is None and self.adjudicator is None
             and owner is broker._hp_resource_owner and owner.status.broker is broker
             and type(owner.store) is plan.api.BatchStore and owner.store.provider is provider
             and owner.store.lock is plan.api.inventory_store._lock
             and provider.source_store is broker._inventory_store
             and provider is broker._canonical_provider is scope_token.new_provider
             and provider.broker is broker and scope_token.new_scope is None
             and provider._scope is None and provider._bound is None
             and scope_token.previous_provider._scope is scope_token.scope,
             'ROSTER_SETUP_ACTUAL_CREATING_SCOPE_OWNER_REQUIRED')
        lifecycle=getattr(broker,'_buff_lifecycle',None)
        need((self.resource_only_stats and plan.resource_only and plan.buff is None
              and owner.skill_schema is None and lifecycle is None
              and self.reference_buff_policy is None and self.catalyst_buff_policy is None)
             or (not self.resource_only_stats and not plan.resource_only
                 and plan.buff is not None and owner.skill_schema is not None
                 and lifecycle is not None and lifecycle.owner is owner),
             'ROSTER_SETUP_EXACT_SCOPED_SKILL_DOMAIN_REQUIRED')
        broker._packet_npc_config.require_scoped_attachment_locked(scope_token,plan=plan,owner=owner)
        armor_options=({} if self.armor_stats_policy is None and self.armor_source is None else
            dict(armor_stats_policy=self.armor_stats_policy,armor_source=self.armor_source))
        gear_options=({} if self.gear_stats_policy is None and self.gear_source is None else
            dict(gear_stats_policy=self.gear_stats_policy,gear_source=self.gear_source))
        progression_options=({} if self.progression_source is None else
            dict(progression_source=self.progression_source,progression_owner=broker._progression_owner))
        scope_options = dict(resource_only_stats=True) if self.resource_only_stats else {}
        stats=selected.SelectedStatsSource(owner,equipment_rules=self.equipment_rules,
            reference_buff_policy=self.reference_buff_policy,catalyst_buff_policy=self.catalyst_buff_policy,
            **scope_options,**armor_options,**gear_options,**progression_options)
        weight=self.weight_factory(owner,stats)
        need(type(weight) in (trial.EmptyInventoryWeight,trial.CurrentInventoryWeight)
             and weight.owner is owner
             and (type(weight) is trial.EmptyInventoryWeight or weight._selected_stats is stats),
             'ROSTER_SETUP_EXISTING_CURRENT_WEIGHT_OWNER_REQUIRED')
        published=self.source.register_scoped(broker,scope_token=scope_token,handoff_issuer=handoff_issuer)
        published.install_hp_inputs_scoped(scope_token,plan=plan,owner=owner)
        combat_provider=published.bind_combat_scoped(owner,stats,scope_token=scope_token,plan=plan,
            rng=self.rng,distance_locked=self.distance_locked,weight240_locked=weight,
            selected_weight240_locked=(weight.with_selected if type(weight) is trial.CurrentInventoryWeight else None))
        owner._combat_empty_weight=weight
        _bind_cast_stats_cold(owner,stats,self.cast_stats_sources)
        self.owner,self.published,self.stats,self.weight=owner,published,stats,weight
        self.provider=combat_provider

    def runtime(self, original):
        need(self.owner is original.broker._hp_resource_owner and self.published is not None,
             'ROSTER_SETUP_BOUND_REAL_RUNTIME_REQUIRED')
        if self.pc_npc_only:
            return original
        return self.runtime_factory(self, original)
