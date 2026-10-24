"""BOOK10 packet cold + original owner lifecycle. Only Test executes this code."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import socket
import sys
import traceback


def need(ok, code):
    if not ok:raise ValueError(code)


@dataclass(frozen=True)
class BookEntry:
    selection: object
    plan: object
    basic_inputs: object
    realm_options: object
    controller: object
    scoped: object
    terms: dict


def prepare_entry(modules, sources, operating_sources, *, source, selection,
        account_profile, child_profile, fixture_root, account, target_uid, target_name,
        root_snapshot, currency_frame, inventory_preimage, base_features,
        hp_status_policy, runtime_input, terms, row_policy, shared_terms,
        local_price_policy=None, stats_weight_config=None, stats_gear_initialization=None):
    """One fixed10 Catalog/PreparedBook; no NativeInput/assemble/transport path."""
    from tools.local_original_session import restart
    helper=modules['canonical_feature_bootstrap'];batch=modules['batch_catalog'];cold=modules['batch_cold']
    need(type(source) is helper.SourceModule and source.module is sys.modules[__name__]
         and source.check() is source.module,'BOOK10_ACTUAL_CALLER_SOURCE_REQUIRED')
    need(type(selection) is batch.SelectedBookBatch10 and selection.modules is modules
         and selection.sources is sources,'BOOK10_SINGLE_ORIGINAL_SELECTION_REQUIRED')
    need(type(root_snapshot) is modules['canonical_batch'].partial_stack.Snapshot
         and root_snapshot.character_uid==1 and type(target_uid) is int and target_uid!=1
         and child_profile==modules['character_scope'].scoped_profile(account_profile,target_uid),
         'BOOK10_REAL_ROOT1_AND_DISTINCT_CHILD_PROFILE_REQUIRED')
    row=modules['book_packet_row_terms'];price=modules['book_local_price_input']
    terms=row.merge_packet_row_terms(batch,terms,policy=row_policy,shared=shared_terms,
        book_offers=modules['book_offers'],light_terms=modules['book_batch_light_terms'],
        price_input=price,local_price_policy=local_price_policy)
    def triple(name):
        pin=sources[name];return pin.module,pin.path,pin.sha256
    def setup(profile):
        return modules['item_uid_namespace_root'].Setup(policy_source=triple('item_uid_namespace'),
            core_source=triple('canonical_batch'),broker_source=triple('broker'),
            credit_source=triple('book_credit_source'),profile=profile,
            credit_collection_policy=modules['inventory'].CURRENT_CREDIT_COLLECTION_POLICY)
    child_setup=setup(child_profile)
    try:
        prepared=cold.prepare_batch_cold(selection,
            cold=cold.BatchColdInput(child_setup,currency_frame,terms),runtime=runtime_input)
    except BaseException:
        if child_setup.owner is None and not child_setup.closed:child_setup.close()
        raise
    if prepared.missing:
        if child_setup.owner is None and not child_setup.closed:child_setup.close()
        return None,prepared.missing
    scoped=plan=root_setup=None
    progression=dict(
        progression_source=sources['progression_document'],progression_capability_source=sources['progression_capability'],
        progression_owner_source=sources['progression_owner'])
    realm_source=helper.SourceModule(modules['broker'].ack.realm,
        prepared.normal_book.buff.root/'work/local_original_session/integration-1/progression-realm-info-integration-v1/realm.py',
        'a8540327aa5adcb91b8d88962097a9c9cb5c77c40e225afffc7f49450a94efde')
    try:
        modules['spell_book_policy'].bind_live_progression_levels(prepared.normal_book.buff,sources['book_progression_level'])
        stats_options={}
        gear_options={}
        if stats_weight_config is not None:
            trial=modules['combat_trial_inputs']
            need(type(stats_weight_config) is trial.NonemptyWeightConfig,
                 'BUFF_STATS_ORIGINAL_WEIGHT_CONFIG_REQUIRED')
            gear_plan,gear_basic=modules['gear_cold_input'].gear_cold_options(modules,sources,
                initialization=stats_gear_initialization,first_enable=False)
            gear_options=dict(full_gear_options=gear_plan,full_gear_basic=gear_basic)
            def weight_factory(owner,stats):
                return trial.CurrentInventoryWeight(owner,stats,stats_weight_config)
            stats_options=dict(full_skill_stats_weight_factory=weight_factory,
                full_skill_stats_source=sources['combat_roster_setup'],
                full_skill_catalyst_source=sources['combat_catalyst_reference'],
                full_skill_catalyst_buff_policy=modules['combat_catalyst_reference'].ADVANCE_SPIRIT_POLICY,
                full_skill_gear_stats_policy=modules['combat_full_gear_stats'].POLICY,
                full_skill_gear_source=sources['gear_consumer'])
            if sources['combat_roster_setup'].sha256=='e68710e2fd0dce786b09e6dc1d58166e44e4925e96037a93c57704bc16079691':
                stats_options['cast_stats_sources']=(sources['hp_resource_owner'],sources['combat_selected_stats'],sources['buff_skill_document'])
        else:
            need(stats_gear_initialization is None,'BUFF_STATS_INITIALIZATION_REQUIRES_WEIGHT_CONFIG')
        scoped=cold.prepare_scoped_batch(prepared,profile=child_profile,fixture_root=fixture_root,
            account=account,target_uid=target_uid,target_name=target_name,inventory_preimage=inventory_preimage,
            base_features=base_features,hp_status_policy=hp_status_policy,**progression,**gear_options)
        api=modules['canonical_batch'];inventory=modules['inventory'];root_setup=setup(account_profile)
        definitions=tuple(d for d in root_snapshot.definitions if d.template==1)
        need(len(definitions)==1,'BOOK10_ORIGINAL_ROOT_ATHAME_DEFINITION_REQUIRED')
        digest=hashlib.sha256((modules['hp_resource_document'].POLICY+
            modules['player_life'].REPEATED_NEWLIFE_POLICY).encode()).hexdigest()
        def catalog_factory(api):
            class ResourceCatalog(api.CatalogOwner):
                def current_digest(self,binding):return digest
            return ResourceCatalog()
        core=sources['canonical_batch']
        plan=helper.CanonicalFeatureBootstrap(profile=account_profile,fixture_root=fixture_root,
            core_path=core.path,core_sha256=core.sha256,aggregate_source=sources['inventory_aggregate'],
            resource_document_source=sources['hp_resource_document'],resource_owner_source=sources['hp_resource_owner'],
            status_source=sources['hp_status'],skill_core_source=sources['skill_buff'],skill_schema_source=sources['canonical_skill'],
            catalog_owner_factory=catalog_factory,participant_capability_factory=None,
            skill_schema_factory=None,runtime_capability_factory=None,catalog_digest=digest,
            resource_only=True,setup_uid=1,uid_namespace_setup=root_setup,resource_factory_source=source,
            original_update_sources=(sources['broker'],sources['inventory_store'],sources['inventory_update']),
            delivery_sources=(sources['canonical_delivery'],sources['skill_cost_delivery']),**progression)
        plan.configure_progression_owner((modules,sources),features=None,reward_policy=None)
        controller=modules['character_scope'].CreatedCharacterScopes(root_plan=plan,modules=modules,
            sources=operating_sources,source=sources['character_scope'],actor_source=sources['selected_actor'],
            prototype=inventory.build_add(dict(modules['broker'].INVENTORY_STARTER_FIELDS)),definition=definitions[0],
            credit_collection_policy=inventory.CURRENT_CREDIT_COLLECTION_POLICY,
            policy=modules['character_scope'].POLICY,book_buy=scoped,realm_source=realm_source,**progression,**stats_options)
        basic=modules['packet_server'].PacketBasicInputs(plan=plan,
            inventory_frame=base_features.inventory_frame,inventory_policy=base_features.inventory_policy,
            inventory_store_policy=modules['inventory_store'].COLLECTION_STORE_POLICY,restart_policy=restart.POLICY,
            inventory_reselection_policy=modules['feature_config'].LOCAL_SAVED_ROW_ON_RESELECTION,
            inventory_delivery_policy=modules['feature_config'].LOCAL_WORLD_READY_ONCE,
            hp_status_policy=modules['hp_status'].POLICY,inventory_collection_policy=inventory.COLLECTION_POLICY,
            inventory_collection_grant=None,item_use_policy=modules['item_use_session'].POLICY)
        options=modules['packet_server'].PacketRealmOptions(npc_spawns=scoped.cold.realm_options.npc_spawns,
            uid_namespace_setup=root_setup)
        return BookEntry(selection,plan,basic,options,controller,scoped,terms),()
    except BaseException as primary:
        if scoped is not None:
            try:scoped.close_unstarted()
            except BaseException as error:primary.add_note('BOOK10 child cold cleanup:'+type(error).__name__)
        if scoped is None:
            for cleanup in (lambda:modules['menu_content_input'].close_input(prepared.prepared_book.resource),
                            prepared.normal_book.buff.close):
                try:cleanup()
                except BaseException as error:primary.add_note('BOOK10 pre-handoff cleanup:'+type(error).__name__)
            if child_setup.owner is None and not child_setup.closed:child_setup.close()
        if plan is not None:
            try:modules['operating_input']._cleanup(modules,plan,None,primary)
            except BaseException as error:primary.add_note('BOOK10 root cold cleanup:'+type(error).__name__)
        if root_setup is not None and root_setup.owner is None and not root_setup.closed:root_setup.close()
        raise


def work_templates(batch, case_inputs, carry, *, skill_enabled, numeric_scope=False, defense_scope=False, observe_stats=False):
    """Metadata-only skip: no requests for allPASS or wholly absent case inputs."""
    progress=batch.new_progress(carry);work=[]
    for case in case_inputs:
        t=case['template'];need(type(t) is int and t in batch.TEMPLATES,'BOOK10_CASE_TEMPLATE_REQUIRED')
        row=progress[str(t)]
        if row['LEARN']['status']=='PASS':
            required=('CAST','EFFECT','RESTORE_EFFECT','EXPIRY10S')+(('CATALYST_DEBIT',) if t==601 else ())
            if t==599 and numeric_scope:required+=('NUMERIC_EFFECT',)
            if t in (181,607) and defense_scope:required+=('NUMERIC_EFFECT',)
            if t in (195,205) and observe_stats:required+=('NUMERIC_EFFECT',)
            if skill_enabled and any(row[k]['status']!='PASS' for k in required):work.append(t)
        elif row['BUY']['status']!='PASS':
            if case.get('buy',True):work.append(t)
        elif (case.get('owned_uid') is not None and case.get('owned_provenance') is not None
              and case.get('eligible_input_provenance') is not None):work.append(t)
    return tuple(work)


def _skill_inputs(modules,sources,client,normal_book,*,observe_stats,weight13_scope,defense_scope=None):
    run=modules['batch_run'];outcome=modules['book_outcome']
    advance=outcome.bind_advance_spirit_sources(math_source=sources['advance_spirit_math'],
        schema_source=sources['buff_skill_document'],lifecycle_source=sources['buff_lifecycle'])
    weight=None
    if weight13_scope is not None:
        need(weight13_scope==run.WEIGHT13_NUMERIC_SCOPE,'BOOK10_EXPLICIT_NUMERIC_SCOPE_REQUIRED')
        weight=run.Weight13Inputs(modules['book_weight13_observer'],sources['book_weight13_observer'],weight13_scope)
    defense=None
    if defense_scope is not None:
        need(defense_scope==run.DEFENSE_BUFF_NUMERIC_SCOPE,'BOOK10_EXPLICIT_DEFENSE_SCOPE_REQUIRED')
        defense=run.DefenseBuffInputs(modules['book_defense_buff_observer'],sources['book_defense_buff_observer'],defense_scope)
    return run.SkillAfterLearnInputs(modules['book_skill_domain'],sources['book_skill_domain'],
        (modules,sources),normal_book,modules['book_buff_client'],modules['book_buff_phase'],outcome,
        modules['cast_route'].wire,normal_book.buff.feature.codec,client._game.world,
        normal_book.buff.feature.source_adapter.codec,observe_stats,advance,weight,defense)


async def run_owner(modules,sources,*,entry,session_input,settings_path,cases,carry,
        skill_enabled=True,observe_stats=False,weight13_scope=None,previous=None,defense_scope=None):
    """One original server lifetime; same function serves genuine first/fresh phases."""
    batch=modules['batch_run'];client=server=None;sockets={};run=None;stage='SERVER_PREPARE'
    report=dict(status='UNRUN',first_error=None,cleanup_errors=[],clean_owner_close=False,
        server_snapshot_before_close=None,server_snapshot_after_close=None,client_report=None,
        native_game=False,native_ui='UNRUN',fresh=previous is not None)
    try:
        need(type(entry) is BookEntry,'BOOK10_TYPED_PACKET_ENTRY_REQUIRED')
        if previous is not None:batch._strict_closed(previous.last_flow.client)
        for port in (12000,14030):
            sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM);sockets[port]=sock
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            sock.bind(('127.0.0.1',port));sock.listen();sock.setblocking(False)
        server=modules['packet_server'].PacketServer(sockets=sockets,store_path=entry.plan.profile,
            expected_uuid=entry.scoped.cold.content.normal_book.buff.account,settings_path=settings_path,
            basic_inputs=entry.basic_inputs,realm_options=entry.realm_options)
        await server.prepare();await server.start();stage='NORMAL_WORLD_SESSION'
        client=modules['packet_client'].PacketFlowClient(server,session_input,port=12000)
        async with client.normal_session():
            normal_book=entry.scoped.cold.content.normal_book
            # Use the actual rule source root supplied to the installed Buff context.
            response=modules['buff_lifecycle'].responses.Codec(normal_book.buff.root)
            skill=(_skill_inputs(modules,sources,client,normal_book,observe_stats=observe_stats,
                weight13_scope=weight13_scope,defense_scope=defense_scope) if skill_enabled else None)
            if previous is None:
                stage='BOOK10_ACTIONS'
                adapter=modules['shop_packet_source'].SourceAdapter(server,entry.scoped.cold.content,scoped=True)
                sequence=await modules['shop_flow'].source_sequence(client,adapter,modules,
                    haction_coordinates=None,trade_coordinates=None)
                keys={r.template:r.row_key_u32 for r in entry.scoped.cold.content.prepared.source_input.book_rows}
                actual=[]
                for row in cases:
                    choice=None
                    if row.get('buy',True):
                        coordinates=row.get('buy_coordinates')
                        need(type(coordinates) is tuple and len(coordinates)==2,'BOOK10_EXPLICIT_LOCAL_BUY_COORDINATES_REQUIRED')
                        choice=modules['book_flow'].MerchantChoice(sequence.npc,sequence.choice.command,
                            sequence.choice.argument,row.get('menu_coordinates'),coordinates,row['template'],1,keys[row['template']])
                    actual.append(batch.BookCaseInput(row['template'],choice,adapter.trade,
                        row.get('owned_uid'),row.get('owned_provenance'),row.get('eligible_input_provenance')))
                run=await batch.run_actions(client,cases=tuple(actual),carry=carry,
                    book_flow_module=modules['book_flow'],response_codec=response,
                    trade_request_wire=modules['trade_request_wire'],shop_effect_reader=modules['effect_reader'],skill_inputs=skill)
                if run.stopped_error is not None:report['first_error']=run.stopped_error
            else:
                stage='BOOK10_FRESH'
                final=None if skill is None else batch.FinalRestoreInputs(modules['book_final_restore'],sources['book_final_restore'],
                    sources['batch_run'],skill.domain_module,skill.domain_source,(modules,sources),normal_book,
                    skill.outcome_module,sources['book_outcome'],client._game.world,skill.buff_codec,
                    weight13=skill.weight13)
                report['fresh_observations']=await batch.observe_fresh(client,previous=previous,
                    book_flow_module=modules['book_flow'],response_codec=response,final_restore_inputs=final)
                run=previous
    except BaseException as error:
        if report['first_error'] is None:report['first_error']=dict(stage=stage,type=type(error).__name__,message=str(error),stack=traceback.format_exc())
    finally:
        if client is not None:
            try:await client.close()
            except BaseException as error:report['cleanup_errors'].append(dict(stage='CLIENT_CLOSE',type=type(error).__name__,message=str(error)))
            try:report['client_report']=client.report()
            except BaseException as error:report['cleanup_errors'].append(dict(stage='CLIENT_REPORT',type=type(error).__name__,message=str(error)))
        if server is not None:
            try:report['server_snapshot_before_close']=server.snapshot()
            except BaseException as error:report['cleanup_errors'].append(dict(stage='SERVER_SNAPSHOT_BEFORE_CLOSE',type=type(error).__name__,message=str(error)))
            try:
                if not server.closed:await server.close()
            except BaseException as error:report['cleanup_errors'].append(dict(stage='SERVER_CLOSE',type=type(error).__name__,message=str(error)))
            try:report['server_snapshot_after_close']=server.snapshot()
            except BaseException as error:report['cleanup_errors'].append(dict(stage='SERVER_SNAPSHOT_AFTER_CLOSE',type=type(error).__name__,message=str(error)))
        for sock in sockets.values():
            try:
                if sock.fileno()!=-1:sock.close()
            except BaseException as error:report['cleanup_errors'].append(dict(stage='SOCKET_CLOSE',type=type(error).__name__,message=str(error)))
        try:
            if entry is not None:entry.scoped.close_unstarted()
        except BaseException as error:report['cleanup_errors'].append(dict(stage='COLD_CLOSE',type=type(error).__name__,message=str(error)))
    if entry is not None and entry.plan._lifetime_state=='READY' and entry.plan._broker is None:
        try:
            need(type(entry.plan) is modules['canonical_feature_bootstrap'].CanonicalFeatureBootstrap
                 and entry.basic_inputs.plan is entry.plan,'BOOK10_SAME_UNBOUND_READY_ROOT_REQUIRED')
            setup=entry.plan._uid_namespace_setup
            need(type(setup) is modules['item_uid_namespace_root'].Setup
                 and setup is entry.realm_options.uid_namespace_setup
                 and (setup.owner is None or setup.owner.closed)
                 and (server is None or server.basic_inputs is entry.basic_inputs
                      and server.closed and not server._plan_bound),
                 'BOOK10_READY_ROOT_OWNED_CLOSED_OR_UNCLAIMED_SETUP_REQUIRED')
            modules['operating_input']._cleanup(modules,entry.plan,None,None)
        except BaseException as error:report['cleanup_errors'].append(dict(stage='READY_ROOT_CLEANUP',type=type(error).__name__,message=str(error)))
    if client is not None and report['first_error'] is None and not report['cleanup_errors']:
        try:
            batch._strict_closed(client)
            need(entry.controller.plan._lifetime_state=='RETIRED','BOOK10_REAL_CHILD_PLAN_CLOSE_REQUIRED')
            report['clean_owner_close']=True
            if previous is not None:batch.record_closed_owner_pair(previous,fresh_client=client)
        except BaseException as error:report['first_error']=dict(stage='STRICT_CLOSE',type=type(error).__name__,message=str(error))
    report['status']='FAILED' if report['first_error'] or report['cleanup_errors'] else 'CLOSED_WITH_PARTIAL_OBSERVATIONS'
    if run is not None:report['batch']=run.report()
    return report,run
