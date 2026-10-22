"""Trusted server-side repeat inputs; no JSON authority decoder or stat setter.

Explicit canonical-v3 selected HP1..20 restore; max/MP stay frozen316 policy. The caller supplies exact copied save
expectations. Original aggregate validators, selected Binding, existing RESOURCE
and world response/drain issue fresh authority; no migration or seed occurs.
"""
from dataclasses import replace
import hashlib, sys
from pathlib import Path

def need(ok,code):
    if not ok:raise ValueError(code)

def pin(module):
    from tools.local_original_session.canonical_feature_bootstrap import SourceModule
    path=Path(module.__file__).resolve()
    return SourceModule(module,path,hashlib.sha256(path.read_bytes()).hexdigest())

INPUT_MODE='EXPLICIT_CANONICAL_V3_SELECTED_HP1_TO20_CONTINUOUS_RETALIATION_RESTORE'

def require_expected(expected):
    need(type(expected) is dict and set(expected)=={'uid','revision','digest','values','frame_sha256'},
         'REPEAT_V3_EXPLICIT_EXPECTATIONS_REQUIRED')
    need(type(expected['uid']) is int and 0<expected['uid']<=0xffffffff
         and type(expected['revision']) is int and expected['revision']>=0
         and type(expected['values']) is dict and set(expected['values'])=={'10','11','12','13'}
         and all(type(v) is int for v in expected['values'].values())
         and expected['uid']==1 and expected['revision']>=42
         and 1<=expected['values']['10']<=20
         and {k:v for k,v in expected['values'].items() if k!='10'}=={'11':20,'12':10,'13':10}, 'RESPAWN_HIT_EXPLICIT_FROZEN316_HP20_EXPECTATIONS_REQUIRED')
    need(all(type(expected[n]) is str and len(expected[n])==64
         and all(c in '0123456789abcdef' for c in expected[n]) for n in ('digest','frame_sha256')),
         'REPEAT_V3_EXACT_DIGEST_EXPECTATIONS_REQUIRED')

def require_saved(document,expected):
    require_expected(expected)
    need(type(document) is dict and type(document.get('version')) is int and document['version']==3
         and document.get('pending') is None, 'REPEAT_EXPLICIT_CANONICAL_V3_ONLY')
    need(set(document['participants'])=={'RESOURCE:'+str(expected['uid'])},
         'REPEAT_V3_EXACT_RESOURCE_ONLY_REQUIRED')
    row=document['participants']['RESOURCE:'+str(expected['uid'])]
    resource=row['document']
    need(row['revision']==expected['revision'] and row['digest']==expected['digest']
         and resource['uid']==expected['uid'] and resource['revision']==expected['revision']
         and resource['values']==expected['values'], 'REPEAT_V3_EXACT_SAVED_RESOURCE_REQUIRED')

class CanonicalLegacyInitializer:
    """Nominal bootstrap hook, explicit v3 restore; never legacy migration."""
    def __init__(self, *, profile, expected_inventory_sha256, expected_resource):
        import copy
        require_expected(expected_resource)
        self.profile=Path(profile).resolve()
        self.expected_inventory_sha256=expected_inventory_sha256
        self.expected_resource=copy.deepcopy(expected_resource)
        self.plan=self.broker=self.batch=self.schema=None
        self.consumed=False

    def attach(self,plan,broker,batch,schema):
        need(self.plan is None and plan._broker is None and not broker._started
             and batch.provider.broker is broker and schema is None and plan.profile==self.profile,
             'REPEAT_INITIALIZER_EXACT_COLD_GRAPH_REQUIRED')
        need(getattr(broker.realm,'_canonical_initialize_selected_locked',None) is None,
             'REPEAT_INITIALIZER_SINGLE_OWNER_REQUIRED')
        self.plan,self.broker,self.batch,self.schema=plan,broker,batch,schema
        broker.realm._canonical_initialize_selected_locked=self.selected_locked

    def selected_locked(self,binding):
        provider=self.batch.provider
        provider.current(binding)
        need(provider.broker is self.broker and self.broker._canonical_provider is provider
             and self.plan._broker is self.broker and self.plan._batch is self.batch
             and self.batch.source is self.broker._inventory_store,
             'REPEAT_INITIALIZER_CURRENT_GRAPH_REQUIRED')
        frame,revision=self.batch.restore(binding)
        if self.consumed:return
        need(binding.uid==self.expected_resource['uid']
             and hashlib.sha256(self.batch._raw).hexdigest()==self.expected_inventory_sha256,
             'REPEAT_V3_EXACT_NEW_SAVED_NAMESPACE_REQUIRED')
        require_saved(self.batch.data,self.expected_resource)
        need(hashlib.sha256(frame).hexdigest()==self.expected_resource['frame_sha256'],
             'REPEAT_V3_EXACT_SAVED_FRAME_REQUIRED')
        self.batch.participant(binding,'RESOURCE')
        # This only authenticates existing backing. ResourceOwner.selection_locked
        # still arms restore; original world fields/write/drain issue new Snapshot.
        self.consumed=True

    def detach(self):
        if self.broker is not None:
            method=getattr(self.broker.realm,'_canonical_initialize_selected_locked',None)
            if getattr(method,'__self__',None) is self:
                delattr(self.broker.realm,'_canonical_initialize_selected_locked')
        self.plan=self.broker=self.batch=self.schema=None


# Original respawn217 recipe; frozen316 save has this same selected grid.
BASELINE_PLAYER_GRID=(32577,32945)
BASELINE_NPC_GRID=(32577,32946)

def require_motion_binding(features,position):
    from tools.local_original_session import feature_config as fc,movement,npc
    need(type(features) is fc.Features and type(position) is movement.Position
         and position.uid==1 and position.map_id==0
         and (position.word0,position.word1)==BASELINE_PLAYER_GRID
         and type(features.spawns) is tuple and len(features.spawns)==2
         and all(type(spawn) is npc.NpcSpawn for spawn in features.spawns),
         'RESPAWN_HIT_ORIGINAL_SELECTED_BASELINE_REQUIRED')
    spawn=features.spawns[0]
    need(spawn.uid==2 and spawn.map_id==position.map_id
         and movement.authority.unpack_grid(spawn.fields[1])==BASELINE_NPC_GRID,
         'RESPAWN_HIT_ORIGINAL_217_RECIPE_BINDING_REQUIRED')
    second=features.spawns[1]
    need(second.uid==3 and second.map_id==spawn.map_id and second.policy==spawn.policy
         and dict(second.fields)==dict(spawn.fields) | {2:3,
             1:movement.authority.pack_grid(BASELINE_NPC_GRID[0]+1,BASELINE_NPC_GRID[1])},
         'TWO_ENEMY_EXACT_SECOND_LOCAL_RECIPE_REQUIRED')
    return spawn


def two_enemy_features(base_features):
    """Explicit trial-only clone after the unchanged single-NPC JSON loader."""
    from tools.local_original_session import feature_config as fc,npc,npc_hp,movement
    need(type(base_features) is fc.Features and len(base_features.spawns)==1
         and type(base_features.attack_hp_provider) is npc_hp.ExplicitInputs
         and len(base_features.attack_hp_provider.rows)==1,
         'TWO_ENEMY_SINGLE_PARSED_PARENT_REQUIRED')
    first,=base_features.spawns;row,=base_features.attack_hp_provider.rows
    need(type(first) is npc.NpcSpawn and first.uid==2 and first.map_id==0
         and first.fields[3]==56 and first.fields[39]==0
         and movement.authority.unpack_grid(first.fields[1])==BASELINE_NPC_GRID
         and row.target==npc_hp.Target(2,0,56,0)
         and row.hp==npc_hp.Hp(2,2) and row.hit==npc_hp.Hit(True,1),
         'TWO_ENEMY_EXACT_PARSED_PARENT_RECIPE_REQUIRED')
    second=npc.NpcSpawn(dict(first.fields) | {2:3,
        1:movement.authority.pack_grid(BASELINE_NPC_GRID[0]+1,BASELINE_NPC_GRID[1])},
        map_id=first.map_id,policy=first.policy)
    second_row=replace(row,target=replace(row.target,uid=3))
    return replace(base_features,spawns=(first,second),
        attack_hp_provider=npc_hp.ExplicitInputs((row,second_row)))


def trusted_source():
    """Use the actual registered issuer, never a substitute source filename."""
    module=sys.modules.get(__name__)
    source=Path(__file__).resolve(strict=True)
    need(module is not None and Path(module.__file__).resolve()==source
         and issue.__globals__ is module.__dict__
         and Path(issue.__code__.co_filename).resolve()==source
         and Path(CanonicalLegacyInitializer.__init__.__code__.co_filename).resolve()==source,
         'RESPAWN_HIT_ACTUAL_TRUSTED_ISSUER_REQUIRED')
    return pin(module)


def issue(*,profile,fixture_root,expected_inventory_sha256,base_features,input_mode,expected_resource,local_binding=None):
    from tools.local_original_session import canonical_feature_bootstrap as cb,feature_config as fc
    from tools.local_original_session import inventory,inventory_store,inventory_aggregate
    from tools.local_original_session import hp_resource_document,hp_resource_owner,hp_status
    from tools.local_original_session import skill_buff,canonical_skill,canonical_delivery,skill_cost_delivery
    from tools.local_original_session import broker,npc_player_hit,player_life,npc_session
    from tools.local_original_session import inventory_update,restart
    from tools.local_original_session import movement
    import npc_continuous_retaliation_runtime
    need(type(base_features) is fc.Features and base_features.canonical_bootstrap is None
         and base_features.player_life_policy is None
         and base_features.npc_player_lethal_recovery_input is None
         and base_features.hp_status_input is None,
         'REPEAT_TYPED_SERVER_INPUTS_REQUIRED')
    base_features=two_enemy_features(base_features)
    profile=Path(profile).resolve();root=Path(fixture_root).resolve()
    need(profile.is_relative_to(root) and profile.is_file(), 'REPEAT_OWNED_COPIED_PROFILE_REQUIRED')
    need(type(input_mode) is str and input_mode==INPUT_MODE,'REPEAT_EXPLICIT_V3_MODE_REQUIRED')
    need(type(local_binding) is npc_continuous_retaliation_runtime.Binding, 'RETALIATION_EXPLICIT_BINDING_REQUIRED')
    require_expected(expected_resource)
    raw=profile.with_name('inventory.json').read_bytes()
    need(hashlib.sha256(raw).hexdigest()==expected_inventory_sha256,
         'REPEAT_COPIED_INVENTORY_SOURCE_CHANGED')
    import json
    require_saved(json.loads(raw),expected_resource)
    inventory.validate_frame(base_features.inventory_frame)
    core_path=ROOT/'work/local_original_session/implementation-1/item-equipment-product/use/empty-integration-311-v1/canonical_batch.py'
    core_sha='1844456802b3e22101aea41a14934cb7a8821368a450fce9515b560aa27de823'
    # The catalog authorizes only RESOURCE, using a stable source-policy digest;
    # no SKILL rule, SHOP reward, currency or inventory grant is introduced.
    catalog_digest=hashlib.sha256(hp_resource_document.POLICY.encode()).hexdigest()
    def catalog_factory(api):
        class ResourceCatalog(api.CatalogOwner):
            def current_digest(self,binding):return catalog_digest
        return ResourceCatalog()
    from tools.local_native_login_spawn_render_retry_runtime import spawn_hook
    profile_data=spawn_hook.profiles()[0]
    initializer=CanonicalLegacyInitializer(profile=profile,expected_inventory_sha256=expected_inventory_sha256,expected_resource=expected_resource)
    plan=cb.CanonicalFeatureBootstrap(profile=profile,fixture_root=root,core_path=core_path,core_sha256=core_sha,
        aggregate_source=pin(inventory_aggregate),resource_document_source=pin(hp_resource_document),
        resource_owner_source=pin(hp_resource_owner),status_source=pin(hp_status),
        skill_core_source=pin(skill_buff),skill_schema_source=pin(canonical_skill),
        catalog_owner_factory=catalog_factory,participant_capability_factory=None,
        skill_schema_factory=None,runtime_capability_factory=None,
        catalog_digest=catalog_digest,setup_uid=profile_data.fields[1],shop=None,trade=None,
        original_update_sources=(pin(broker),pin(inventory_store),pin(inventory_update)),
        delivery_sources=(pin(canonical_delivery),pin(skill_cost_delivery)),
        hp_consumer_sources=(pin(npc_player_hit),pin(player_life),pin(npc_session)),
        resource_only=True,legacy_initializer=initializer,legacy_initializer_source=trusted_source())
    try:
        source=inventory_store.InventoryStore(profile,policy=inventory_store.COLLECTION_STORE_POLICY,
            aggregate_capability=plan.capability)
        need(profile_data.fields[1]==expected_resource['uid'],'REPEAT_V3_EXACT_PROFILE_UID_REQUIRED')
        rows,known=source._read()
        need(profile_data.fields[1] in rows and profile_data.fields[1] in known,
             'REPEAT_ORIGINAL_SAVED_CHARACTER_REQUIRED')
        frame=source.restore(profile_data.fields[1])
        need(len(inventory.validate_collection_frame(frame,policy=inventory.COLLECTION_POLICY))==2
             and source.path.read_bytes()==raw,'REPEAT_EXACT_SAVED_TWO_ROW_REQUIRED')
        characters=inventory_store._characters(profile)['characters']
        character=next(row for row in characters if row['uid']==profile_data.fields[1])
        actor=spawn_hook.profiles()[1]
        initial=movement.Position(profile_data.fields[1],character['name'],0,*movement.authority.unpack_grid(actor[1]))
        position=movement.PositionStore(profile).restore(initial)
        require_motion_binding(base_features,position)
        need(hashlib.sha256(frame).hexdigest()==expected_resource['frame_sha256'],
             'REPEAT_V3_EXACT_SAVED_FRAME_REQUIRED')
        need(source.path.read_bytes()==raw,'REPEAT_V3_COLD_SOURCE_CHANGED')
    except BaseException:
        # No broker, namespace or live authority has been acquired yet.
        plan._retire_refs()
        raise
    try:
        features=replace(base_features,canonical_bootstrap=plan,
            inventory_store_policy=inventory_store.COLLECTION_STORE_POLICY,
            inventory_collection_policy=inventory.COLLECTION_POLICY,
            inventory_collection_grant=(inventory_store.SECOND_INSTANCE_POLICY,frozenset()),
            inventory_missing_row_policy=None,
        inventory_reselection_policy=fc.LOCAL_SAVED_ROW_ON_RESELECTION,
            inventory_delivery_policy=fc.LOCAL_WORLD_READY_ONCE,
            inventory_update_policy=broker.INVENTORY_UPDATE_POLICY,
            inventory_custody_policy=None,item_transfer_policy=None,item_use_policy=None,
            item_equipment_policy=None,item_equipment_first_enable=False,
            restart_policy=restart.POLICY,hp_status_policy=hp_status.POLICY,
            player_life_policy=local_binding.life_policy,npc_player_lethal_recovery_input=None,
            interval_ns=local_binding.move_ns)
        plan._continuous_binding=local_binding
        npc_continuous_retaliation_runtime.configuration(features)
        need(plan._factory is None and plan._broker is None,'REPEAT_FRESH_PLAN_REQUIRED')
    except BaseException:
        plan._retire_refs()
        raise
    return plan,features

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/local_original_session/broker.py').is_file())
