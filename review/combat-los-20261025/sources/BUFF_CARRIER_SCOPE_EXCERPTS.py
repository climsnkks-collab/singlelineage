# REVIEW EXCERPTS ONLY; not an executable carrier.
# Original: work/local_original_session/implementation-3/skill-buff/buff-cast-stats-carrier-v1/character_scope.py
# Original SHA256: 4a25568f51d1cb61b8c28a736ff010a968e24a760887469e798e598f52083fe8

# Original CreatedCharacterScopes.__init__ lines 368-535
    def __init__(self,prepared=None,*,source,actor_source,prototype,definition,credit_collection_policy,policy,
                 root_plan=None,modules=None,sources=None,economy_policy=None,book_buy=None,
                 scoped_stats_weight_factory=None,scoped_gear_stats_policy=None,scoped_gear_source=None,
                 full_skill_stats_weight_factory=None,full_skill_stats_source=None,full_skill_catalyst_source=None,full_skill_catalyst_buff_policy=None,full_skill_gear_stats_policy=None,full_skill_gear_source=None,
                 progression_source=None,progression_capability_source=None,
                 progression_owner_source=None,realm_source=None,scoped_full_gear_options=None,cast_stats_sources=None):
        need(type(policy) is str and policy==POLICY,'CHARACTER_SCOPE_EXPLICIT_POLICY_REQUIRED')
        need(economy_policy is None or type(economy_policy) is str and economy_policy==ECONOMY_POLICY,
             'CHARACTER_SCOPE_EXPLICIT_ECONOMY_POLICY_REQUIRED')
        _STARTER_ECONOMY[self]=economy_policy
        if prepared is not None:
            need(root_plan is None and modules is None and sources is None,'CHARACTER_SCOPE_ONE_COLD_PRODUCER_REQUIRED')
            modules=prepared.modules;root_plan=prepared.plan
        operating=modules['operating_input'];helper=modules['canonical_feature_bootstrap']
        need((prepared is None or type(prepared) is operating.Prepared and prepared.cold_blueprint is not None)
             and type(root_plan) is helper.CanonicalFeatureBootstrap
             and type(source) is helper.SourceModule and source.check() is sys.modules.get(__name__)
             and __name__=='character_scope' and type(actor_source) is helper.SourceModule,
             'CHARACTER_SCOPE_ORIGINAL_COLD_INPUTS_REQUIRED')
        if book_buy is not None:
            need(modules.get('book_buy_inputs') is sys.modules.get('book_buy_inputs')
                 and type(book_buy) is modules['book_buy_inputs'].ScopedBookBuy,
                 'CHARACTER_SCOPE_EXACT_BOOK_BUY_COLD_INPUT_REQUIRED')
        self.book_buy=book_buy
        need((scoped_stats_weight_factory is None and scoped_gear_stats_policy is None and scoped_gear_source is None)
             or (book_buy is not None and callable(scoped_stats_weight_factory)
                 and type(scoped_gear_stats_policy) is str
                 and type(scoped_gear_source) is helper.SourceModule
                 and scoped_gear_source.check() is modules['gear_consumer']),
             'CHARACTER_SCOPE_EXPLICIT_SCOPED_GEAR_STATS_INPUT_REQUIRED')
        self.scoped_stats_weight_factory=scoped_stats_weight_factory
        self.scoped_gear_stats_policy=scoped_gear_stats_policy
        self.scoped_gear_source=scoped_gear_source
        # Separate cold full-SKILL opt-in. Original resource/noSKILL guard above
        # stays exact; the existing COMBAT leaf owns all live graph checks.
        full_skill_disabled=(full_skill_stats_weight_factory is None and full_skill_stats_source is None
            and full_skill_catalyst_source is None and full_skill_catalyst_buff_policy is None
            and full_skill_gear_stats_policy is None and full_skill_gear_source is None)
        legacy_full_skill_setup=(type(full_skill_stats_source) is helper.SourceModule and
            full_skill_stats_source.sha256=='7a7a0fc274dafc597723860568d24543103ae5d5ba44068416abf14a3289ad84')
        progression_full_skill_setup=(type(full_skill_stats_source) is helper.SourceModule and
            full_skill_stats_source.sha256=='9e04d269d1689a441874550f36a35c274e226e91c765018c469ee1677210c54f'
            and progression_owner_source is not None)
        cast_stats_full_skill_setup=(type(full_skill_stats_source) is helper.SourceModule and
            full_skill_stats_source.sha256=='e68710e2fd0dce786b09e6dc1d58166e44e4925e96037a93c57704bc16079691'
            and progression_source is not None and progression_capability_source is not None
            and progression_owner_source is not None)
        need(full_skill_disabled or (callable(full_skill_stats_weight_factory)
             and scoped_stats_weight_factory is None and book_buy is not None
             and getattr(book_buy,'full_book',None) is True
             and type(full_skill_stats_source) is helper.SourceModule
             and (legacy_full_skill_setup or progression_full_skill_setup or cast_stats_full_skill_setup)
             and full_skill_stats_source.check() is modules['combat_roster_setup']
             and type(full_skill_catalyst_source) is helper.SourceModule
             and full_skill_catalyst_source.check() is modules['combat_catalyst_reference']
             and type(full_skill_catalyst_buff_policy) is str
             and (full_skill_catalyst_buff_policy==modules['combat_catalyst_reference'].ENCHANT_DEX_POLICY or (hasattr(modules['combat_catalyst_reference'],'ENCHANT_MIGHTY_POLICY') and full_skill_catalyst_buff_policy==modules['combat_catalyst_reference'].ENCHANT_MIGHTY_POLICY) or (hasattr(modules['combat_catalyst_reference'],'ADVANCE_SPIRIT_POLICY') and full_skill_catalyst_buff_policy==modules['combat_catalyst_reference'].ADVANCE_SPIRIT_POLICY))
             and ((full_skill_gear_stats_policy is None and full_skill_gear_source is None)
                  or (type(full_skill_gear_stats_policy) is str
                      and type(full_skill_gear_source) is helper.SourceModule
                      and full_skill_gear_source.check() is modules['gear_consumer']))),
             'CHARACTER_SCOPE_EXPLICIT_FULL_SKILL_STATS_COLD_INPUT_REQUIRED')
        need((cast_stats_sources is None and not cast_stats_full_skill_setup) or
             (cast_stats_full_skill_setup and not full_skill_disabled
              and type(cast_stats_sources) is tuple and len(cast_stats_sources)==3
              and all(type(p) is helper.SourceModule for p in cast_stats_sources)),
             'CHARACTER_SCOPE_EXACT_CAST_STATS_SOURCES_REQUIRED')
        self.cast_stats_sources=cast_stats_sources
        self.full_skill_stats_inputs=None if full_skill_disabled else (
            full_skill_stats_source,full_skill_stats_weight_factory,full_skill_catalyst_source,
            full_skill_catalyst_buff_policy,full_skill_gear_stats_policy,full_skill_gear_source)
        actor=actor_source.check();plan=root_plan
        if economy_policy is not None:
            need(modules.get('adena_credit_source') is _adena_source(),
                 'CHARACTER_SCOPE_ONE_ADENA_SOURCE_REQUIRED')
        need(plan._lifetime_state=='READY' and plan._broker is None
             and plan._uid_namespace_setup is not None
             and (prepared is None or plan.profile==prepared.profile.copy_root/'characters.json')
             and plan.profile.is_absolute(),'CHARACTER_SCOPE_OWNED_ROOT_PLAN_REQUIRED')
        if prepared is not None:sources=dict(prepared.cold_blueprint.assembly)['sources']
        need(type(sources) is tuple and all(type(p) is operating.ModulePin and p.check() is modules[p.name] for p in sources),
             'CHARACTER_SCOPE_ACTUAL_COLD_MODULE_PINS_REQUIRED')
        need(prepared is not None or plan.resource_only and plan._resource_cold_inputs is not None,
             'CHARACTER_SCOPE_ROOT_RESOURCE_BLUEPRINT_REQUIRED')
        need(getattr(plan,'_combat_setup',None) is None
             and (plan._factory is None or plan._factory.npc_factory is None),
             'CHARACTER_SCOPE_UNCAPTURED_ADDITIONAL_OWNER_REFUSED')
        self.root_prepared=prepared;self.resource_blueprint=plan._resource_cold_inputs
        self.graph_sources=sources;self.modules=modules;self.source=source;self.actor_source=actor_source
        need(plan._progression_source is progression_source, 'CHARACTER_SCOPE_SAME_PROGRESSION_OPT_IN')
        need(plan._progression_capability_source is progression_capability_source,
             'CHARACTER_SCOPE_SAME_PROGRESSION_CAPABILITY_SOURCE')
        self.progression_source=progression_source
        self.progression_capability_source=progression_capability_source
        need(plan._progression_owner_source is progression_owner_source,
             'CHARACTER_SCOPE_SAME_PROGRESSION_OWNER_SOURCE')
        need((progression_owner_source is None and realm_source is None) or
             (type(progression_owner_source) is helper.SourceModule
              and progression_owner_source.sha256=='574d4419f82f43caf1a60fbf3f82cfc0d309a4f1ee5e999c92b34d107f5ad358'
              and progression_owner_source.check() is modules['progression_owner']
              and type(realm_source) is helper.SourceModule
              and realm_source.sha256=='a8540327aa5adcb91b8d88962097a9c9cb5c77c40e225afffc7f49450a94efde'
              and realm_source.check() is modules['broker'].ack.realm),
             'CHARACTER_SCOPE_EXPLICIT_PROGRESSION_READER_SOURCES_REQUIRED')
        need(scoped_full_gear_options is None or (type(scoped_full_gear_options) is dict
             and set(scoped_full_gear_options)=={'full_gear_policy','full_gear_initialization',
                 'full_gear_admission_source','full_gear_definitions'}
             and type(scoped_full_gear_options['full_gear_admission_source']) is helper.SourceModule
             and scoped_full_gear_options['full_gear_admission_source'].check() is modules['fullgear_admission']),
             'CHARACTER_SCOPE_EXPLICIT_CHILD_FULL_GEAR_COLD_OPTIONS_REQUIRED')
        need(scoped_full_gear_options is None,
             'CHARACTER_SCOPE_CHILD_FULL_GEAR_FEATURES_PRODUCER_UNSUPPLIED')
        self.scoped_full_gear_options=scoped_full_gear_options
        self.progression_owner_source=progression_owner_source;self.realm_source=realm_source
        need(progression_owner_source is None or plan._progression_owner_inputs is not None,
             'CHARACTER_SCOPE_TYPED_PROGRESSION_COLD_INPUTS_REQUIRED')
        self.progression_selected_sources=(None if progression_owner_source is None else
            plan._progression_owner_inputs[0])
        if progression_owner_source is not None and book_buy is not None:
            need(book_buy.cold.plan._progression_source is progression_source
                 and book_buy.cold.plan._progression_capability_source is progression_capability_source
                 and book_buy.cold.plan._progression_owner_source is progression_owner_source,
                 'CHARACTER_SCOPE_BOOK_PROGRESSION_COLD_BUILDER_UNSUPPLIED')
            book_buy.cold.plan.configure_progression_owner(self.progression_selected_sources,
                features=book_buy.cold.features,reward_policy=None)
        self.progression_reader=(None if progression_owner_source is None else
            progression_owner_source.module.ProgressionSourceReader(
                core_source=self.progression_selected_sources[1]['canonical_batch'],
                realm_source=realm_source,scope_source=source,capabilities=plan.capability.capabilities))
        own=sys.modules[__name__]
        self.source_functions=tuple((owner,name,getattr(owner,name),getattr(owner,name).__code__)
            for owner,names in ((own,('scope_construction_current','checked_transition','scoped_equipment_profile',
                                      'transfer_connection_scope','finish_scope_chunk','created_scope_current','inventory_store_profile_current','scoped_shop_plan')),
                                (type(self),('selecting','capture_request','require_creation_request_current',
                                             '_project_selected_actor','_construct_graph','_fresh_broker_sources','_recover_previous_graph','_fresh_root_plan','_child_scope','source_current','starter_uid_count','reserve_uid','packet_account_cursor','release_packet_account_cursor','credit_account_cursor','_initialize_created_equipment')),
                                (actor,('selected_actor',)),
                                (modules['broker'].PersistentBroker,('reselect_scoped_equipment_policy',))) for name in names)
        if progression_source is not None:
            self.source_functions+=tuple((progression_source.module,name,getattr(progression_source.module,name),
                getattr(progression_source.module,name).__code__) for name in
                ('seed_for_create_locked','validate_document','validate_transition'))
        if economy_policy is not None:
            self.source_functions+=tuple((owner,name,getattr(owner,name),getattr(owner,name).__code__)
                for owner,names in ((own,('_adena_source','adena_definition','economy_starter_snapshot',
                                          'adena_held_frame','current_adena_frame','ensure_created_scope')),
                                    (_adena_source(),('definition','prototype'))) for name in names)
        if self.full_skill_stats_inputs is not None:
            setup=full_skill_stats_source.module
            function=setup.install_selected_stats_full_skill_scoped
            self.source_functions+=((setup,'install_selected_stats_full_skill_scoped',function,function.__code__),)
        if book_buy is not None:
            cls=type(book_buy)
            self.source_functions+=tuple((cls,name,getattr(cls,name),getattr(cls,name).__code__)
                for name in ('consume','current','close_unstarted'))
        if self.progression_reader is not None:
            cls=progression_owner_source.module.ProgressionSourceReader
            self.source_functions+=tuple((cls,name,getattr(cls,name),getattr(cls,name).__code__)
                for name in ('read_record','require_projection','info_level','close'))
        self.prototype,self.definition=prototype,definition
        self.credit_collection_policy=credit_collection_policy
        self.account_profile=plan.profile;self.root_uid=plan.setup_uid
        need(self.root_uid==1,'CHARACTER_SCOPE_LEGACY_ROOT_IDENTITY_REQUIRED')
        self.plan=plan;self.broker=self.packet_port=None;self.api=plan.api
        self.root_fields=self.root_actor=self.root_name=self.repeated_policy=None
        self.selected_profile=self.account_profile;self.selected_uid=self.root_uid
        self.previous_generation=None;self.pending=None;self.transition=None
        self._configure_setup(plan._uid_namespace_setup)
        plan._character_scopes=self

# Original CreatedCharacterScopes._construct_graph lines 923-1013
    def _construct_graph(self,uid,info,profile,old_setup,projected,token):
        broker=self.broker;realm=broker.realm;api=self.api
        token.phase='CONSTRUCTING'
        if uid==self.root_uid:
            plan=self._fresh_root_plan(old_setup);self._configure_setup(plan._uid_namespace_setup)
            fields,actor=dict(self.root_fields),dict(self.root_actor)
            features=None if self.root_prepared is None else self.root_prepared.features
        else:
            raw=_read(profile.with_name('inventory.json'),api.MAX_BYTES)
            operating=self.modules['operating_input'];by_name={p.name:p for p in self.graph_sources}
            if self.book_buy is None:
                setup=self._new_setup(profile,old_setup)
                digest=hashlib.sha256(POLICY.encode('ascii')).hexdigest()
                plan=operating.assemble_created_character_graph(sources=tuple(by_name.values()),profile=profile,
                    fixture_root=self.account_profile.parent,core_source=by_name['canonical_batch'].source,setup_uid=uid,
                    catalog_digest=digest,resource_policy_digest=digest,uid_namespace_setup=setup,
                    progression_source=self.progression_source,progression_capability_source=self.progression_capability_source,
                    progression_owner_source=self.progression_owner_source,
                    progression_selected_sources=self.progression_selected_sources,
                    full_gear_options=self.scoped_full_gear_options,
                    inventory_preimage=operating.FilePin(profile.with_name('inventory.json'),hashlib.sha256(raw).hexdigest()))
                features=None
            else:
                cold=self.book_buy.consume(self,uid,info,profile,raw)
                plan=cold.plan;features=cold.features
                self._configure_setup(plan._uid_namespace_setup)
                if self.progression_owner_source is not None:
                    need(plan._progression_source is self.progression_source
                         and plan._progression_capability_source is self.progression_capability_source
                         and plan._progression_owner_source is self.progression_owner_source,
                         'CHARACTER_SCOPE_BOOK_PROGRESSION_COLD_BUILDER_UNSUPPLIED')
                    need(plan._progression_owner_inputs is not None
                         and plan._progression_owner_inputs[0] is self.progression_selected_sources
                         and plan._progression_owner_inputs[1] is features
                         and plan._progression_owner_inputs[2] is None,
                         'CHARACTER_SCOPE_BOOK_TYPED_PROGRESSION_INPUTS_CHANGED')
            fields,actor=dict(projected.self_fields),dict(projected.actor_fields)
        try:
            need(plan._gear_options is None or features is not None,
                 'CHARACTER_SCOPE_FULL_GEAR_ACTUAL_FRESH_FEATURES_UNSUPPLIED')
        except BaseException as primary:
            try:plan._retire_refs()
            except BaseException as secondary:primary.add_note('Scoped Gear cold cleanup: '+type(secondary).__name__)
            raise
        self.plan=plan;plan._character_scopes=self
        realm.profile_uid,realm.profile_name=uid,info[1]
        realm._self_fields,realm._actor_fields=fields,actor
        # Original selected_actor data and exact LocalRealm objects, not authority.
        token.equipment_profile=(None if uid==self.root_uid else
            (projected,fields,actor,realm.world_profile,plan))
        realm.positions=self.modules['broker'].movement.PositionStore(profile)
        self._fresh_broker_sources(plan,features,token)
        token.phase='ATTACHING'
        if features is not None and features.item_equipment_policy is not None:
            effect=self.modules['item_equipment_effect'].ItemEquipmentEffect(broker,
                policy=features.item_equipment_policy,first_enable=False)
            broker._item_equipment_effect=broker.realm._item_equipment_effect=effect
        broker.reselect_scoped_equipment_policy(plan,scope_transition=token)
        options={'store_path':profile,'hp_status_policy':plan.status.POLICY}
        if plan._gear_options is not None or plan._armor_options is not None:
            options.update(item_equipment_policy=features.item_equipment_policy,item_equipment_first_enable=False)
        plan.create_broker(options,packet_port=self.packet_port,scope_transition=token)
        gear=getattr(broker,'_packet_gear',None)
        effect=broker._item_equipment_effect
        if effect is not None and effect._gear is not None:
            need(gear is not None,'CHARACTER_SCOPE_COLD_SCOPED_GEAR_BRIDGE_REQUIRED')
            gear.replace_scoped_runtime(effect,effect._gear,broker._packet_inventory,token)
            if self.scoped_stats_weight_factory is not None:
                # Original issuer owns ATTACHING. The COMBAT leaf checks actual
                # BOUND/new owner/provider/pristine generation before/after factory.
                selected={pin.name:pin for pin in self.graph_sources}
                setup=selected['combat_roster_setup'].check()
                setup.install_selected_stats_scoped(plan,broker,plan._owner,
                    scope_transition=token,weight_factory=self.scoped_stats_weight_factory,
                    resource_only_stats=True,shop_resource_stats=True,
                    gear_stats_policy=self.scoped_gear_stats_policy,gear_source=self.scoped_gear_source)
        if uid!=self.root_uid and self.full_skill_stats_inputs is not None:
            setup_source,weight_factory,catalyst_source,catalyst_policy,gear_policy,gear_source=self.full_skill_stats_inputs
            # Original checked_transition in this callee reuses ATTACHING after
            # create_broker's actual new BOUND owner/provider/scope handoff.
            progression_options=({} if setup_source.sha256 not in (
                '9e04d269d1689a441874550f36a35c274e226e91c765018c469ee1677210c54f',
                'e68710e2fd0dce786b09e6dc1d58166e44e4925e96037a93c57704bc16079691')
                or self.progression_owner_source is None else dict(progression_source=self.progression_owner_source))
            cast_stats_options=({} if self.cast_stats_sources is None else dict(cast_stats_sources=self.cast_stats_sources))
            setup_source.module.install_selected_stats_full_skill_scoped(plan,broker,plan._owner,
                scope_transition=token,weight_factory=weight_factory,
                catalyst_buff_policy=catalyst_policy,
                gear_stats_policy=gear_policy,gear_source=gear_source,**progression_options,**cast_stats_options)
        self.selected_uid=uid
        token.phase='ATTACHED'
