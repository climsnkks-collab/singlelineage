"""Operating SHOP cold input assembly. Never launches, starts sockets or issues input."""
from dataclasses import dataclass,replace
from pathlib import Path
from types import MappingProxyType,ModuleType
import hashlib,importlib.util,json,sys,uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/local_original_session/launcher.py').is_file())
BUFF_ASSEMBLER=ROOT/'work/local_original_session/implementation-3/skill-buff/buff-runtime-item-raw-pin-v1/assembler/assemble.py'
BUFF_ASSEMBLER_SHA='2f6b4ea65d98c4260e611ff8131fc15bbe1f2775b8814e746c77b3e16bafbe7e'
FILES=('characters.json','positions.json','account-settings.bin','inventory.json','equipment.json')
_FILE_MODULE=None
_FILE_METHODS=None

def need(ok,code):
    if not ok:raise ValueError(code)

def _file_api():
    # Reuse original operating regular-file/reparse/stable-read implementation.
    global _FILE_MODULE,_FILE_METHODS
    raw=BUFF_ASSEMBLER.read_bytes();need(hashlib.sha256(raw).hexdigest()==BUFF_ASSEMBLER_SHA,'OPERATING_FILE_SOURCE_CHANGED')
    name='_shop_original_operating_files'
    if _FILE_MODULE is not None:
        need(sys.modules.get(name)is _FILE_MODULE and (_FILE_MODULE.snapshot,_FILE_MODULE.ordinary)==_FILE_METHODS,
             'OPERATING_FILE_METHOD_CHANGED')
        return _FILE_MODULE
    need(name not in sys.modules,'OPERATING_FILE_ALIAS_ALREADY_BOUND')
    spec=importlib.util.spec_from_file_location(name,BUFF_ASSEMBLER);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    try:exec(compile(raw,str(BUFF_ASSEMBLER),'exec'),m.__dict__)
    except BaseException:
        sys.modules.pop(name,None);raise
    _FILE_MODULE=m;_FILE_METHODS=(m.snapshot,m.ordinary);return m

def _launch_arguments(args,expected):
    protected=tuple(expected)
    for argument in args:
        if argument.startswith('--') and argument not in ('--run','--background','--source-quit-test'):
            flag=argument.split('=')[0]
            need(not any(p.startswith(flag) or flag.startswith(p+'=') for p in protected)
                 or argument in protected,'OPERATING_ABBREVIATED_ARGUMENT_REFUSED')
    for flag,value in expected.items():
        need(args.count(flag)==1 and args.index(flag)+1<len(args) and args[args.index(flag)+1]==value,
             'OPERATING_LAUNCH_ARGUMENT_MISMATCH')
    for flag in ('--run','--background','--source-quit-test'):
        need(args.count(flag)==1,'OPERATING_ORIGINAL_BACKGROUND_QUIT_REQUIRED')

@dataclass(frozen=True,slots=True)
class FilePin:
    path: Path
    sha256: str
    def read(self,limit=1048576):
        need(isinstance(self.path,Path) and self.path.is_absolute() and type(self.sha256)is str
             and len(self.sha256)==64 and all(c in '0123456789abcdef' for c in self.sha256),'EXPLICIT_FILE_PIN_REQUIRED')
        return _file_api().snapshot(self.path,expected=self.sha256,limit=limit)

@dataclass(frozen=True,slots=True)
class ModulePin:
    name: str
    module: object
    source: FilePin
    def check(self):
        need(type(self.source)is FilePin and type(self.name)is str and bool(self.name),'EXPLICIT_MODULE_SOURCE_PIN_REQUIRED')
        need(type(self.module)is ModuleType and sys.modules.get(self.module.__name__)is self.module
             and Path(self.module.__file__).resolve()==self.source.path.resolve(),'ORIGINAL_SOURCE_MODULE_REQUIRED')
        self.source.read();return self.module

def _check_stored_profile(realm,path,profile_uid):
    # Original snapshot's second item is the INFO[1] name set, never UIDs.
    # Bind strict stored UID -> exact name/select INFO -> original roster bytes.
    store=realm.CharacterStore(path)
    with realm._lock:
        before=store._read()
        rows=[r for r in before['characters'] if r['uid']==profile_uid]
        need(len(rows)==1,'EXPLICIT_PROFILE_UID_NOT_STORED')
        row=rows[0];info=realm._record_info(row)
        uid,selected=store.select(row['name'])
        need(uid==profile_uid and selected==info,'STORED_PROFILE_SELECTION_CHANGED')
        roster,names=store.snapshot()
        infos=[realm._record_info(r) for r in before['characters']]
        expected=realm.wire.build_local_roster(expected_count=len(infos),display_slots=realm.MAX_CHARACTERS,
            rows=infos,existing_rows=(),mode='initial',allow_expected_growth=False)
        need(names==frozenset(r[1] for r in infos) and row['name'] in names and roster==expected,
             'STORED_PROFILE_ROSTER_CHANGED')
        need(store._read()==before,'STORED_PROFILE_QUERY_CHANGED')

@dataclass(frozen=True,slots=True)
class ProfileInput:
    copy_root: Path
    run_directory: Path
    protected_roots: tuple
    account: str
    profile_uid: int
    map_id: int
    grid: tuple
    setup_uid: int
    files: tuple
    features: FilePin
    resource_setup_provenance: str
    def check(self,modules,*,phase='ASSEMBLY'):
        need(phase in ('ASSEMBLY','FACTORY'),'ORIGINAL_STARTUP_PHASE_REQUIRED')
        need(str(uuid.UUID(self.account))==self.account,'OPERATING_ACCOUNT_REQUIRED')
        need(type(self.profile_uid)is int and 0<self.profile_uid<=0xffffffff
             and type(self.setup_uid)is int and self.setup_uid==self.profile_uid,'EXPLICIT_RESOURCE_SETUP_UID_REQUIRED')
        need(type(self.map_id)is int and -2**31<=self.map_id<2**31 and type(self.grid)is tuple
             and len(self.grid)==2 and all(type(v)is int for v in self.grid),'EXPLICIT_PROFILE_MAP_GRID_REQUIRED')
        need(type(self.resource_setup_provenance)is str and bool(self.resource_setup_provenance),'EXPLICIT_RESOURCE_SETUP_SOURCE_REQUIRED')
        api=_file_api();api.ordinary(self.copy_root,directory=True)
        need(type(self.protected_roots)is tuple and bool(self.protected_roots),'PROTECTED_PROFILE_ROOTS_REQUIRED')
        copy=self.copy_root.resolve();run=self.run_directory.resolve()
        for protected in self.protected_roots:
            protected=Path(protected).resolve(strict=True)
            need(copy!=protected and not copy.is_relative_to(protected) and not protected.is_relative_to(copy),'ORIGINAL_PROFILE_REFUSED')
            need(run!=protected and not run.is_relative_to(protected) and not protected.is_relative_to(run),'ORIGINAL_RUN_ROOT_REFUSED')
        need(not run.is_relative_to(copy) and not copy.is_relative_to(run),'DISJOINT_RUN_REQUIRED')
        if phase=='ASSEMBLY':
            need(not run.exists(),'FRESH_RUN_DIRECTORY_REQUIRED');api.ordinary(self.run_directory,absent=True)
        else:
            api.ordinary(self.run_directory,directory=True)
        need(type(self.files)is tuple and len(self.files)==5 and all(type(p)is FilePin for p in self.files),'FIVE_EXACT_STORE_PREIMAGES_REQUIRED')
        by_name={p.path.name:p for p in self.files}
        need(set(by_name)==set(FILES) and all(p.path==self.copy_root/name for name,p in by_name.items()),'SAME_COPY_STORE_PATHS_REQUIRED')
        for pin in self.files:pin.read()
        # Actual original parsers, read only. No profile/HP/default inventory seed.
        broker=modules['broker']
        _check_stored_profile(broker.ack.realm,self.copy_root/'characters.json',self.profile_uid)
        position=broker.movement.PositionStore(self.copy_root/'characters.json')._read()
        rows=[r for r in position['positions'] if r['uid']==self.profile_uid]
        need(len(rows)==1 and rows[0]['map_id']==self.map_id and tuple(rows[0]['grid'])==self.grid,'STORED_PROFILE_POSITION_CHANGED')
        from tools.local_original_session import settings
        settings.SettingsStore(self.copy_root/'account-settings.bin',self.account,profile_path=self.copy_root/'characters.json')
        need(type(self.features)is FilePin,'EXPLICIT_FEATURE_CONFIG_PIN_REQUIRED')
        self.features.read(32768)
        for pin in self.files:pin.read()
        return self.copy_root/'characters.json'

MIGRATION_POLICY='SHOP_EXPLICIT_COPIED_V1_TO_CANONICAL_V3_V1'

@dataclass(frozen=True,slots=True)
class MigrationInput:
    policy: str
    inventory: FilePin
    profile_uid: int
    catalog_sha256: str
    def check(self,profile,catalog):
        need(self.policy==MIGRATION_POLICY and type(self.inventory)is FilePin
             and type(self.profile_uid)is int and self.profile_uid==profile.profile_uid
             and type(self.catalog_sha256)is str and self.catalog_sha256==catalog.sha
             and not catalog.quests and bool(catalog.offers),
             'SHOP_EXPLICIT_MIGRATION_INPUT_REQUIRED')
        pins=[p for p in profile.files if p.path.name=='inventory.json']
        need(len(pins)==1 and self.inventory==pins[0]
             and self.inventory.path==profile.copy_root/'inventory.json',
             'SHOP_MIGRATION_SAME_PROFILE_PREIMAGE_REQUIRED')
        raw=self.inventory.read()
        data=json.loads(raw)
        need(type(data)is dict and type(data.get('version'))is int and data['version']==1,
             'SHOP_EXPLICIT_RAW_V1_REQUIRED')

@dataclass(frozen=True,slots=True)
class GameInput:
    copy_root: Path
    image: FilePin
    provenance: str
    def check(self,profile,launcher):
        need(type(self.image)is FilePin and type(self.provenance)is str and bool(self.provenance),
             'EXPLICIT_ROOT_GAME_COPY_INPUT_REQUIRED')
        api=_file_api();api.ordinary(self.copy_root,directory=True)
        root=self.copy_root.resolve(strict=True)
        need(self.copy_root.is_absolute() and self.image.path.is_absolute() and self.image.path.parent==root,
             'EXACT_GAME_COPY_IMAGE_REQUIRED')
        for other in profile.protected_roots:
            other=Path(other).resolve()
            need(root!=other and not root.is_relative_to(other) and not other.is_relative_to(root),
                 'PROTECTED_OR_OVERLAPPING_GAME_COPY_REFUSED')
        spec=launcher.PRODUCTS[launcher.SHOP_INPUT_PROFILE]
        need(self.image.sha256==spec['image_sha256'],'ORIGINAL_DESCRIPTOR_IMAGE_SHA_REQUIRED')
        # Original preflight checks executable/bridge bytes and resource directory.
        # Root owns materialization/provenance of the full runtime copy.
        files=launcher.preflight(self.image.path,launcher.SHOP_INPUT_PROFILE)
        need(files.get(self.image.path)==self.image.sha256,'ORIGINAL_IMAGE_PREFLIGHT_REQUIRED')
        return self.image.path

ROOT_NATIVE=ROOT/'work/local_original_session/implementation-4/shop-quest/shop-dispatcher-gate-v19/native394'
ROOT_MANIFEST_SHA='b419f1d20438448af90f9693d0844edf0887f0103bd3687633a851909baa1e33'
ROOT_RECEIPT=ROOT_NATIVE/'build-receipt.json'
ROOT_RECEIPT_SHA='767b535fa0526e5ce329409933f0dd861c132b11ab076b54ae3866b082268638'
ROOT_DLL_SHA='1e18afd8643d5a60e941782726c681b1c0a1e2944f700933dd28d4256de742d6'
ROOT_CAPTURE_SOURCES=(('original_screenshot.hpp','582d065d8bac0a88137e587c34516933382019f22cd2faf264d82e1bc8b61eae'),
    ('direct_gl_png.hpp','bde6c37cf5f63542ccb84e810fa93866e760a004ebaf0aa49306a94a4259e077'))

@dataclass(frozen=True,slots=True)
class NativeInput:
    artifact: FilePin
    compilation_receipt: FilePin
    capture_sources: tuple
    def check(self):
        need(type(self.artifact)is FilePin and type(self.compilation_receipt)is FilePin,'EXPLICIT_COMPILED_NATIVE_PINS_REQUIRED')
        need(self.artifact.path==ROOT_NATIVE/'own-login-bridge-dg49.dll'
             and self.artifact.sha256==ROOT_DLL_SHA,'EXACT_ROOT_NATIVE_ARTIFACT_REQUIRED')
        need(self.compilation_receipt.path==ROOT_RECEIPT
             and self.compilation_receipt.sha256==ROOT_RECEIPT_SHA,'EXACT_ROOT_NATIVE_RECEIPT_REQUIRED')
        raw=self.artifact.read(16*1024*1024)
        receipt=json.loads(self.compilation_receipt.read())
        manifest=json.loads(FilePin(ROOT_NATIVE/'manifest.json',ROOT_MANIFEST_SHA).read())
        need(type(receipt)is dict and receipt.get('status')=='BUILT_SHOP_BODY394_FULL_TU_SOURCE_ONLY'
             and receipt.get('manifest_sha256')==ROOT_MANIFEST_SHA
             and receipt.get('dll_sha256')==self.artifact.sha256
             and type(receipt.get('dll_bytes'))is int and receipt['dll_bytes']==len(raw),
             'ROOT_RECEIPT_DLL_ASSOCIATION_MISMATCH')
        selected=manifest.get('selected_dll')
        need(type(selected)is dict and ROOT/selected['path']==self.artifact.path
             and selected.get('sha256')==self.artifact.sha256 and selected.get('bytes')==len(raw),
             'ROOT_MANIFEST_DLL_ASSOCIATION_MISMATCH')
        expected=tuple((ROOT_NATIVE/name,sha) for name,sha in ROOT_CAPTURE_SOURCES)
        need(type(self.capture_sources)is tuple and len(self.capture_sources)==2
             and all(type(p)is FilePin for p in self.capture_sources)
             and tuple((p.path,p.sha256) for p in self.capture_sources)==expected,'EXACT_ROOT_V6_CAPTURE_SOURCES_REQUIRED')
        files=manifest.get('files');need(type(files)is list,'ROOT_NATIVE_SOURCE_MANIFEST_REQUIRED')
        for pin in self.capture_sources:
            content=pin.read()
            matched=[row for row in files if type(row)is dict and ROOT/row['path']==pin.path]
            need(len(matched)==1 and matched[0].get('sha256')==pin.sha256 and matched[0].get('bytes')==len(content),
                 'ROOT_MANIFEST_CAPTURE_SOURCE_ASSOCIATION_MISMATCH')
        # Accepted root review establishes LF->author CRLF inverse exactness/build
        # closure. This checker does not rebuild/load/analyze PE or prove geometry.

@dataclass(frozen=True,slots=True)
class Field39Policy:
    value: int
    provenance: str

@dataclass(frozen=True,slots=True)
class UninstalledRootInputs:
    native: NativeInput
    field39: Field39Policy

def root_inputs():
    native=NativeInput(FilePin(ROOT_NATIVE/'own-login-bridge-dg49.dll',ROOT_DLL_SHA),
        FilePin(ROOT_RECEIPT,ROOT_RECEIPT_SHA),
        tuple(FilePin(ROOT_NATIVE/name,sha) for name,sha in ROOT_CAPTURE_SOURCES))
    native.check()
    return UninstalledRootInputs(native,Field39Policy(7,'ROOT_LOCAL_OPAQUE_FIELD39_7_V1'))

@dataclass(frozen=True,slots=True)
class HpStatusPolicy:
    policy: str
    provenance: str

def _prepare_features(modules,base,plan,prepared,hp_status_policy):
    # Same typed policy-only preparation as original Buff runtime_input.py:275;
    # no JSON schema coercion, HP value, input/owner or participant seed.
    fc=modules['feature_config']
    need(type(base)is fc.Features and base.canonical_bootstrap is None,'ORIGINAL_OPERATING_FEATURE_CONFIG_REQUIRED')
    need(base.item_transfer_policy is None and base.inventory_custody_policy is None,
         'SHOP_INPUT_UNUSED_ITEM_POLICIES_DISABLED_REQUIRED')
    need(type(hp_status_policy)is HpStatusPolicy and type(hp_status_policy.policy)is str
         and hp_status_policy.policy==modules['hp_status'].POLICY
         and type(hp_status_policy.provenance)is str and bool(hp_status_policy.provenance),
         'EXPLICIT_ROOT_HP_STATUS_POLICY_ONLY_REQUIRED')
    need(base.hp_status_policy is None and base.hp_status_input is None,'SHOP_INPUT_NO_NUMERIC_HP_STATUS_INPUT_REQUIRED')
    features=replace(base,canonical_bootstrap=plan,hp_status_policy=hp_status_policy.policy)
    features=prepared.resource.prepare_features(features)
    modules['server_owned_menu'].validate_menu_config(plan.shop,features)
    return features

@dataclass(frozen=True,slots=True)
class MerchantInput:
    publication_fields: tuple
    map_id: int
    catalog_npc: int
    credit_frames: tuple
    offer_id: str
    row_key_u32: int
    context_i32: int
    outer2_i32: int
    unknown678: tuple
    unknown_provenance: tuple
    publication_provenance: str
    placement_provenance: str
    catalog_provenance: str

def prepare_content(modules,merchant,catalog,content):
    need(type(content)is MerchantInput and type(content.publication_fields)is tuple
         and len(dict(content.publication_fields))==len(content.publication_fields)
         and 39 in dict(content.publication_fields),'EXPLICIT_FULL_PUBLICATION_WITH_F39_REQUIRED')
    need(type(merchant)is ModuleType and Path(merchant.__file__).resolve()==(ROOT/'work/local_original_session/implementation-4/shop-quest/merchant-source-input-v1/merchant_source_input.py').resolve(),'ORIGINAL_MERCHANT_MODULE_REQUIRED')
    FilePin(Path(merchant.__file__).resolve(),'b4a4396f37cd3e2d1754b3f11c65ad032872e8e1c8d8d61ca808bb6368fd8800').read()
    need(type(catalog)is modules['shop_quest'].Catalog,'SAME_ACTUAL_SHOP_CATALOG_REQUIRED')
    values={name:getattr(content,name) for name in MerchantInput.__dataclass_fields__}
    values['publication_fields']=dict(content.publication_fields)
    return merchant.prepare(catalog,**values)

@dataclass(slots=True)
class Prepared:
    modules: object
    profile: ProfileInput
    native: NativeInput
    plan: object
    features: object
    content: object
    def recheck(self,*,phase='ASSEMBLY'):
        self.profile.check(self.modules,phase=phase);self.native.check()
        self.plan._sources_current()
        need(self.features.canonical_bootstrap is self.plan,'SAME_OPERATING_ROOT_PLAN_REQUIRED')
    def feature_factory(self,reader):
        launcher=self.modules['launcher']
        from tools.local_original_session.observe import RetainedSceneReader
        need(type(reader)is RetainedSceneReader,'ACTUAL_ORIGINAL_READER_REQUIRED')
        # Original main constructs the Reader/PFF before NativeOwner/retain.
        # None is a pre-retain state, never current-owner evidence.
        if reader.owner is not None:
            need(type(reader.owner)is launcher.NativeOwner,'ACTUAL_RETAINED_OWNER_REQUIRED')
            reader.validate()
        self.recheck(phase='FACTORY')
        return launcher.ProductFeatureFactory(reader,product=launcher.SHOP_INPUT_PROFILE,
            control_mode='manual',directory=self.profile.run_directory,config=self.features)
    def launch(self,argv,*,game,normal_input_driver=None):
        """Root-only startup; delegates to the new strict SHOP entry, never Buff."""
        old=sys.argv
        try:
            self.recheck();launcher=self.modules['launcher'];args=list(argv)
            need(type(game)is GameInput,'EXPLICIT_GAME_INPUT_REQUIRED')
            image=game.check(self.profile,launcher)
            need(all(type(v)is str for v in args),'OPERATING_STRING_ARGV_REQUIRED')
            expected={'--image':str(image),'--expected-uuid':self.profile.account,'--store':str(self.profile.copy_root/'characters.json'),
                      '--run-directory':str(self.profile.run_directory),'--product':launcher.SHOP_INPUT_PROFILE,
                      '--control-mode':'manual'}
            _launch_arguments(args,expected)
            sys.argv=[str(launcher.__file__),*args]
            kwargs=dict(canonical_bootstrap=self.plan,shop_features=self.features)
            if normal_input_driver is not None:
                driver=self.modules.get('shop_normal_input_driver')
                need(type(driver)is ModuleType and sys.modules.get(driver.__name__)is driver,
                     'ORIGINAL_NORMAL_INPUT_DRIVER_MODULE_REQUIRED')
                need(type(normal_input_driver)is driver.Spec
                     and normal_input_driver.root is self.plan and normal_input_driver.features is self.features,
                     'SAME_PREPARED_NORMAL_INPUT_DRIVER_SPEC_REQUIRED')
                kwargs['normal_input_driver']=normal_input_driver
            return launcher.main(**kwargs)
        finally:
            sys.argv=old
            if self.plan._lifetime_state=='READY' and self.plan._broker is None and self.plan._batch is None:
                _cleanup(self.modules,self.plan,self.plan.shop,sys.exception())

    def close_unstarted(self):
        if self.plan._lifetime_state=='RETIRED':return
        need(self.plan._broker is None and self.plan._batch is None and self.plan._lifetime_state=='READY',
             'OPERATING_ONLY_UNSTARTED_CLEANUP')
        _cleanup(self.modules,self.plan,self.plan.shop,None)

def _cleanup(modules,plan,shop,primary):
    first=None
    for step in (lambda:modules['menu_content_input'].close_root(shop) if shop is not None else None,
                 lambda:plan.trade.close() if plan is not None and plan.trade is not None else None,
                 lambda:shop.detach() if shop is not None else None,
                 lambda:plan._close_npc_factory() if plan is not None else None,
                 lambda:plan._retire_refs() if plan is not None else None):
        try:step()
        except BaseException as error:
            if first is None:first=error
            if primary is not None:
                try:BaseException.add_note(primary,'Operating SHOP cleanup: '+type(error).__name__)
                except BaseException:pass
    if primary is None and first is not None:raise first

def assemble(*,sources,profile,native,catalog,merchant,content,max_writers,core_source,hp_status_policy,migration):
    need(type(sources)is tuple and all(type(p)is ModulePin for p in sources),'EXPLICIT_OPERATING_SOURCE_SET_REQUIRED')
    names=[p.name for p in sources];need(len(names)==len(set(names)),'DUPLICATE_SOURCE_ALIAS')
    modules=MappingProxyType({p.name:p.check() for p in sources})
    need(type(core_source)is FilePin and type(content)is MerchantInput,'EXPLICIT_CORE_AND_CONTENT_INPUT_REQUIRED')
    need(type(profile)is ProfileInput and type(native)is NativeInput,'ACTUAL_PROFILE_AND_COMPILED_NATIVE_INPUT_REQUIRED')
    need(merchant is modules.get('merchant_source_input'),'EXACT_MERCHANT_SOURCE_MODULE_REQUIRED')
    need(type(max_writers)is int and max_writers>0,'EXPLICIT_MAX_WRITERS_REQUIRED')
    need(content.map_id==profile.map_id,'MERCHANT_PROFILE_MAP_MISMATCH')
    native.check();profile_path=profile.check(modules)
    need(type(migration)is MigrationInput,'SHOP_EXPLICIT_MIGRATION_INPUT_REQUIRED')
    migration.check(profile,catalog)
    helper=modules['canonical_feature_bootstrap'];plan=shop=None
    def pin(name):
        source=next(p for p in sources if p.name==name)
        return helper.SourceModule(source.module,source.source.path,source.source.sha256)
    prepared=prepare_content(modules,merchant,catalog,content)
    try:
        shop=helper.ShopProgressBootstrap(core_source=pin('shop_quest'),port_source=pin('canonical_port'),
            bindings_source=pin('shop_quest_binding'),events_source=pin('server_death_event'),
            composer_source=pin('bootstrap_progress'),kill_source=pin('npc_kill_events'),catalog=catalog,
            objectives=(),max_writers=max_writers,menu_mode='server-owned-publication-v1',menu_input=prepared.resource)
        trade=helper.ShopTradeBootstrap(shop=shop,ingress_source=pin('trade_ingress'),delivery_source=pin('trade_delivery'),
            projection_source=pin('projection'),wire_source=pin('trade_request_wire'),broker_source=pin('broker'))
        def catalog_owner(api):
            class ResourceCatalog(api.CatalogOwner):
                def current_digest(self,binding):return catalog.sha
            class ShopCatalog(api.CatalogOwner):
                def current_digest(self,binding):return catalog.sha
            guarded=trade.catalog_owner(api,ShopCatalog())
            return api.ParticipantCatalogOwner(((('RESOURCE',),ResourceCatalog()),(('SHOP-QUEST',),guarded)))
        core_source.read()
        initializer=modules['shop_store_initializer'].ShopStoreInitializer(
            profile=profile_path,expected_inventory_sha256=migration.inventory.sha256,
            profile_uid=migration.profile_uid,account=profile.account,
            catalog_sha256=migration.catalog_sha256)
        plan=helper.CanonicalFeatureBootstrap(profile=profile_path,fixture_root=profile.copy_root,
            core_path=core_source.path,core_sha256=core_source.sha256,
            aggregate_source=pin('inventory_aggregate'),resource_document_source=pin('hp_resource_document'),
            resource_owner_source=pin('hp_resource_owner'),status_source=pin('hp_status'),
            skill_core_source=pin('skill_buff'),skill_schema_source=pin('canonical_skill'),
            catalog_owner_factory=catalog_owner,participant_capability_factory=None,skill_schema_factory=None,
            runtime_capability_factory=None,catalog_digest=catalog.sha,setup_uid=profile.setup_uid,
            shop=shop,trade=trade,shop_only=True,resource_only=False,
            shop_initializer=initializer,shop_initializer_source=pin('shop_store_initializer'),
            original_update_sources=(pin('broker'),pin('inventory_store'),pin('inventory_update')),
            delivery_sources=(pin('canonical_delivery'),pin('skill_cost_delivery')))
        fc=modules['feature_config'];base=fc.load(profile.features.path)
        features=_prepare_features(modules,base,plan,prepared,hp_status_policy)
        # Original store parser/aggregate read capability. No migration/seed/write.
        store=modules['inventory_store'].InventoryStore(profile_path,policy=base.inventory_store_policy,
            custody_policy=base.inventory_custody_policy,aggregate_capability=plan.capability)
        need(type(store.restore(profile.profile_uid))is bytes,'EXISTING_PLAYER_INVENTORY_REQUIRED')
        profile.check(modules)
        modules['launcher'].install_shop_input_profile(bridge_artifact=native.artifact.path,bridge_sha256=native.artifact.sha256)
        return Prepared(modules,profile,native,plan,features,prepared)
    except BaseException as primary:
        _cleanup(modules,plan,shop,primary)
        try:modules['menu_content_input'].close_input(prepared.resource)
        except BaseException as secondary:
            try:BaseException.add_note(primary,'Operating resource input cleanup: '+type(secondary).__name__)
            except BaseException:pass
        raise
