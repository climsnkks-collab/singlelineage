"""Root-owned production copy -> exact Buff cold factory. No profile writes.

Call load_packet then issue; root alone may invoke Issued.launch. Numeric
cooldowns/groups are explicit local input, never inferred from UI metadata.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import hashlib, importlib.util, json, stat, sys, time, uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/local_original_session/launcher.py').is_file())
JOIN=ROOT/'work/local_original_session/integration-1/spell-observer-binding-serial371-v1'
PASSIVE_ROOT=Path(__file__).resolve().parent
LAUNCHER_SHA='80641fa5bd46aa1e9f4b2fc1f1fb7a9bc70e3977d1706d33843b1ddf0accff2c' # Physical public anchor; selected private launcher is the exact cohort row.
LOADER_SHA='764c80c1ef590da64e88f9491ea3a5de4c1755eb238c1404aa78041781c68a4f'
COHORT_SHA='687b82ebeba6a8050e117a66ea54f7c7dfea6c2655749eec2d8596d87caf563e'
MANIFEST_SHA='fed338417d0812f094860f551845c4ae3f18e27c70b9892310b4d6ae70fe7fc0'
METADATA_SHA='b79b28435eccd5dc7cc093f197c94fe52314259cb0d99ae555fa7763db6a0454'
POST_ROOT=ROOT/'work/local_original_session/integration-1/book-learning-serial305-v1'
BOOK_ROOT=ROOT/'work/local_original_session/implementation-3/skill-buff/spell-normal-learning-v1'
BOOK_ROSTER_ROOT=BOOK_ROOT/'book-roster-consumer-v9'
CAST_ROUTE_SHA='e7b849264303011f10364d6e3014678f93724bb16fbd2ed80bad94108aa7de8d'
LEARNED_ROOT=ROOT/'work/local_original_session/implementation-3/skill-buff/spell-learned-input-v1'
LIFECYCLE_SHA='5aa083585f5041c029a96da4008d2f5687be6fffd3154cd3b5210bbfc57da4c1'
BOOTSTRAP_SHA='5d35af8c4b6ec5d5f5ddc4657ef4fd60617f4b8462276c705d9f8a6e711c8503'
LEARNED_SHA='a4765d540f356823495e9ab6626f9985c8bf289b2b5c0c64de5f812b6cc4098d'
HELPER_SHA='ae46520f7084ce088ddd0b273f2c47cc6ace782e7d2f4ad5def3b830e3dbb610'
INITIALIZER_SHA='cfddd033b3175cb70bf435bfa5995b863f167985a33ad63d17e9b3372bc5d777'
SETTINGS_SHA='c58a4d94f6801a3dc1a1884f901e068f82ffcbd85ecd22c7f9bd51d051d9ca45'
CORE_SHA='2fd02106d855745248e31e6b2d1a63d1903754286b37056b41ae6147250db4c0'
FILES=('characters.json','positions.json','account-settings.bin','inventory.json','equipment.json')
TIME_POLICY='LOCAL_WALL_MS_DEADLINE_NOMINAL_SIMULATION_SECONDS_CEIL_V1'
RULE_POLICY='LOCAL_PRODUCTION_UI_DURATION_SECONDS_X1000_V1'
MULTI_SELF_ROWS=((1,1,4,0,7200),(2,1,2,0,1200),(31,4,10,40,600),(51,7,15,0,64),(53,7,60,0,2400))
MULTI_SELF_IDS=tuple(r[0]for r in MULTI_SELF_ROWS)

def require_actual_public():
    path=ROOT/'work/local_original_session/integration-1/spell-observer-binding-serial371-v1/physical_public_guard.py'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='2444528d134a28d50dfe2dc6c5824c1d3c87288df36ab44d7fc52b91d735c9d4':raise ValueError('SKILL371_PUBLIC_GUARD_SOURCE_CHANGED')
    namespace={'__file__':str(path)}
    exec(compile(raw,str(path),'exec'),namespace)
    namespace['check']()

def need(ok, code):
    if not ok: raise ValueError(code)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def unique(pairs):
    out={}
    for k,v in pairs:
        need(k not in out,'PRODUCTION_DUPLICATE_KEY');out[k]=v
    return out
def decode(raw):
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:need(False,'PRODUCTION_NONFINITE'))
def digest(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':')).encode())
def hashed(path, expected, limit=1048576):
    path=Path(path)
    need(path.is_absolute(),'PRODUCTION_ABSOLUTE_PATH_REQUIRED')
    for p in (path,*path.parents):
        s=p.lstat();need(not stat.S_ISLNK(s.st_mode) and not getattr(s,'st_file_attributes',0)&0x400,'PRODUCTION_REPARSE_REFUSED')
    s=path.stat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=limit,'PRODUCTION_REGULAR_SINGLE_LINK_REQUIRED')
    raw=path.read_bytes();after=path.stat()
    need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and sha(raw)==expected,'PRODUCTION_PREIMAGE_CHANGED')
    return raw

def exact(value,keys,code):need(type(value)is dict and set(value)==set(keys),code)
def integer(v,lo=0,hi=2**63-1):return type(v)is int and lo<=v<=hi

def parse_packet(raw):
    need(type(raw)is bytes and 0<len(raw)<=32768,'PRODUCTION_PACKET_BOUND')
    d=decode(raw)
    exact(d,('schema','copy_root','run_directory','account','setup_uid','files','features','skill_preimage','initial_learned','cooldown_ms','groups','not_after_ms','time_policy','rule_policy','expiry_provenance'),'PRODUCTION_PACKET_SHAPE')
    need(type(d['schema'])is int and d['schema']==1 and d['time_policy']==TIME_POLICY and d['rule_policy']==RULE_POLICY,'PRODUCTION_POLICY_REQUIRED')
    need(type(d['copy_root'])is str and Path(d['copy_root']).is_absolute(),'PRODUCTION_NEW_COPY_REQUIRED')
    need(type(d['run_directory'])is str and Path(d['run_directory']).is_absolute(),'PRODUCTION_FRESH_RUN_DIRECTORY_REQUIRED')
    need(type(d['account'])is str and str(uuid.UUID(d['account']))==d['account'],'PRODUCTION_ACCOUNT_REQUIRED')
    need(d['setup_uid']is None or integer(d['setup_uid'],1,0xffffffff),'PRODUCTION_EXPLICIT_SETUP_UID')
    exact(d['files'],FILES,'PRODUCTION_FIVE_PREIMAGES_REQUIRED')
    exact(d['features'],('path','sha256'),'PRODUCTION_FEATURE_INPUT_REQUIRED')
    for v in (*d['files'].values(),d['features']['sha256']):need(type(v)is str and len(v)==64 and all(c in '0123456789abcdef' for c in v),'PRODUCTION_SHA_REQUIRED')
    for key in ('cooldown_ms','groups'):
        need(type(d[key])is dict and set(d[key])in ({'1','2'},set(map(str,MULTI_SELF_IDS))),'PRODUCTION_EXPLICIT_LOCAL_RULE_POLICY')
        need(all(integer(v,0,0x7fffffff) for v in d[key].values()),'PRODUCTION_LOCAL_RULE_RANGE')
    need(integer(d['not_after_ms'],1),'PRODUCTION_INPUT_DEADLINE')
    need(d['expiry_provenance'] in ('EXISTING_STORED_PRODUCTION_DEADLINES','NO_EXPIRY_TRIAL','CONTROLLED_BACKEND_PREPARATION_SEPARATE'),'PRODUCTION_EXPIRY_PROVENANCE')
    need(type(d['initial_learned'])is list,'PRODUCTION_EXPLICIT_ENTITLEMENTS')
    seen=set()
    for row in d['initial_learned']:
        exact(row,('uid','learned','before_digest'),'PRODUCTION_ENTITLEMENT_SHAPE')
        need(integer(row['uid'],1,0xffffffff) and row['uid']not in seen,'PRODUCTION_ENTITLEMENT_UID');seen.add(row['uid'])
        need(type(row['learned'])is list and len(set(row['learned']))==len(row['learned']) and all(type(x)is int and x in (1,2) for x in row['learned']),'PRODUCTION_ENTITLEMENT_ALLOWLIST')
        need(row['before_digest']is None or type(row['before_digest'])is str and len(row['before_digest'])==64,'PRODUCTION_ENTITLEMENT_PREIMAGE')
    p=d['skill_preimage']
    if p is not None:
        exact(p,('revision','digest','rules'),'PRODUCTION_SKILL_PREIMAGE')
        need(integer(p['revision']) and all(type(p[k])is str and len(p[k])==64 for k in ('digest','rules')),'PRODUCTION_SKILL_PREIMAGE')
    return Packet(raw)

@dataclass(frozen=True,slots=True)
class Packet:
    raw:bytes
    def values(self):return decode(self.raw)

def load_packet(path):
    with Path(path).open('rb') as stream:raw=stream.read(32769)
    return parse_packet(raw)

_MODULES=None
_SELECTED=None

def load_cohort():
    require_actual_public()
    global _MODULES,_SELECTED
    hashed(JOIN/'manifest.json',MANIFEST_SHA)
    hashed(JOIN/'cohort.json',COHORT_SHA)
    hashed(PASSIVE_ROOT/'cohort_loader.py',LOADER_SHA)
    if _MODULES is not None:
        for name,module in _MODULES.items():
            row=_SELECTED[name]
            need(Path(module.__file__).resolve()==Path(row['path']).resolve() and sha(Path(module.__file__).read_bytes())==row['sha256'] and sys.modules.get(module.__name__)is module,'PRODUCTION_CACHED_SOURCE_CHANGED')
        return _MODULES
    hashed(JOIN/'manifest.json',MANIFEST_SHA)
    selected=decode(hashed(JOIN/'cohort.json',COHORT_SHA))['selected']
    # Explicit child source selection; all original 51 parent rows stay unchanged.
    selected.update({'buff_passive': {'path': 'C:\\Users\\Chansol\\Documents\\ChatGPT\\싱글리니지\\work\\local_original_session\\implementation-3\\skill-buff\\spell-normal-learning-v1\\book-client-stat-passive-v23\\buff_passive.py', 'sha256': 'fb801ddf2abbd337236923667cc0b16dc7d0c66fc1c4192447c9933e6a388aef', 'bytes': 22058}, 'observe': {'path': 'C:\\Users\\Chansol\\Documents\\ChatGPT\\싱글리니지\\work\\local_original_session\\implementation-3\\skill-buff\\spell-normal-learning-v1\\book-client-buff-passive-v19\\observe.py', 'sha256': 'f97bfae246c0561021d6c3a034d04aa6fd18b47b593a71e9476aced54e1e0cfa', 'bytes': 45592}})
    # One exact selected source map; no author-old overrides or fallback hashes.
    # Check all aliases before the accepted loader runs; never replace another
    # active cohort in a long-lived interpreter.
    plain={'shop_quest','canonical_port','shop_quest_binding','server_death_event','bootstrap_progress','dialogue_route','trade_request_wire','projection','trade_delivery','trade_ingress'}
    for name,row in selected.items():
        q=name if name in plain else 'tools.local_original_session.'+name
        old=sys.modules.get(q)
        if old is not None:
            need(False,'PRODUCTION_FRESH_INTERPRETER_REQUIRED')
    # Execute the frozen loader itself, with a fresh in-memory selection and
    # only exact public977/c62 descendants plus the owned runtime pair. No source edited.
    path=PASSIVE_ROOT/'cohort_loader.py'
    spec=importlib.util.spec_from_file_location('_production_buff_cohort',path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m
    exec(compile(hashed(path,LOADER_SHA),str(path),'exec'),m.__dict__)
    m.SELECTED=selected
    _MODULES=m.load();_SELECTED=selected
    return _MODULES

def production_rules(mods, packet, *, catalog_frame_keys=False,multi_self=False):
    d=packet.values();path=ROOT/'work/local_original_session/implementation-3/skill-buff/spell_metadata.py'
    raw=hashed(path,METADATA_SHA);spec=importlib.util.spec_from_file_location('_production_spell_metadata',path)
    metadata=importlib.util.module_from_spec(spec);exec(compile(raw,str(path),'exec'),metadata.__dict__)
    catalog=metadata.Catalog(ROOT);rules=[];sources=[]
    rows=MULTI_SELF_ROWS if multi_self else MULTI_SELF_ROWS[:2]
    need(all(set(d[k])==set(str(r[0])for r in rows)for k in ('groups','cooldown_ms')),'PRODUCTION_EXPLICIT_LOCAL_RULE_POLICY')
    for sid,grade,mp,hp,seconds in rows:
        rule,source=catalog.configure(mods['skill_buff'].Rule,spell_id=sid,ui_class='generic',ui_grade=grade,
            mp_cost=mp,hp_cost=hp,cooldown_ms=d['cooldown_ms'][str(sid)],duration_ms=seconds*1000,
            group=d['groups'][str(sid)],policy=metadata.CONFIG_POLICY)
        # HP0 and duration are literal UI evidence, not an invented optional
        # required.hp default. Exact retained source pins checked by Catalog.
        text=source['ui_rows'][0]['explanation_KR']
        if sid in (1,2):need(f'({mp}/0)' in text and f'{seconds:,}' in text,'PRODUCTION_UI_NUMBERS_CHANGED')
        rules.append(rule);sources.append(source)
    if catalog_frame_keys:
        return tuple(rules),mods['buff_skill_document'].catalog_icon_policy(tuple(sources),metadata.PINS)
    return tuple(rules)

@dataclass(frozen=True,slots=True)
class Issued:
    packet:Packet
    plan:object
    features:object
    modules:dict
    def launch(self,argv):
        """Root-only real launcher entry; no execution during issue()."""
        old=sys.argv
        try:
            self.recheck()
            d=self.packet.values()
            args=list(argv)
            need(all(type(x)is str for x in args),'PRODUCTION_STRING_ARGV_REQUIRED')
            protected=('--expected-uuid','--store','--run-directory','--product','--control-mode')
            need(not any(x.startswith('--') and any(f.startswith(x.split('=')[0]) or x.startswith(f+'=') for f in protected) and x not in (*protected,'--run') for x in args),'PRODUCTION_ABBREVIATED_ARGUMENT_REFUSED')
            for flag,expected in (('--expected-uuid',d['account']),('--store',str(Path(d['copy_root'])/'characters.json')),
                                  ('--run-directory',d['run_directory']),('--product',self.plan.runtime_profile()),('--control-mode','manual')):
                need(args.count(flag)==1 and args.index(flag)+1<len(args) and args[args.index(flag)+1]==expected,'PRODUCTION_LAUNCH_ARGUMENT_MISMATCH')
            sys.argv=[str(self.modules['launcher'].__file__),*args]
            return self.modules['launcher'].main(canonical_bootstrap=self.plan,canonical_features=self.features)
        finally:
            sys.argv=old
            # Original main may refuse/return before run_session exists. Only
            # an unstarted READY plan belongs to this adapter's cleanup.
            if self.plan._lifetime_state=='READY' and self.plan._broker is None and self.plan._batch is None:
                primary=sys.exception()
                secondary=cleanup_unstarted(self.plan,self.plan.buff,primary)
                if primary is None and secondary is not None:raise secondary
    def recheck(self):
        validate_copy(self.packet)
        need(type(self.features)is self.modules['feature_config'].Features and self.features.canonical_bootstrap is self.plan,'PRODUCTION_EXACT_TYPED_PLAN_REQUIRED')
        self.plan.buff.source_ready()
        hashed(ROOT/'tools/local_original_session/launcher.py',LAUNCHER_SHA)


def validate_run_directory(run,directory,original):
    need(run.is_absolute() and not run.exists(),'PRODUCTION_FRESH_RUN_DIRECTORY_REQUIRED')
    target=run.resolve()
    for boundary in (directory.resolve(),original.resolve()):
        need(target!=boundary and target not in boundary.parents and boundary not in target.parents,
             'PRODUCTION_RUN_DIRECTORY_COLLISION')
    need(run.parent.is_dir(),'PRODUCTION_RUN_PARENT_REQUIRED')
    for part in (run,*run.parents):
        if not part.exists() and not part.is_symlink():continue
        info=part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,'PRODUCTION_REPARSE_REFUSED')

def validate_copy(packet):
    need(type(packet)is Packet,'PRODUCTION_TYPED_PACKET_REQUIRED');d=parse_packet(packet.raw).values()
    need(time.time_ns()//1000000<d['not_after_ms'],'PRODUCTION_INPUT_EXPIRED')
    directory=Path(d['copy_root'])
    need(directory.is_dir(),'PRODUCTION_NEW_COPY_NOT_MATERIALIZED')
    old=ROOT/'work/local_original_session/validation-profiles/manual-background-item-live-input-233'
    need(directory.resolve()!=old.resolve() and old.resolve()not in directory.resolve().parents and directory.resolve()not in old.resolve().parents,'PRODUCTION_ORIGINAL_COPY_REFUSED')
    validate_run_directory(Path(d['run_directory']),directory,old)
    raws={name:hashed(directory/name,d['files'][name]) for name in FILES}
    inventory=decode(raws['inventory.json'])
    need(inventory.get('version') in (1,3) and type(inventory.get('version'))is int,'PRODUCTION_V1_OR_CANONICAL_V3_REQUIRED')
    need(inventory.get('pending')is None,'PRODUCTION_PENDING_TRANSACTION_REFUSED')
    skill=inventory.get('participants',{}).get('SKILL')
    expected=d['skill_preimage']
    need((skill is None)==(expected is None),'PRODUCTION_SKILL_PREIMAGE_CHANGED')
    if skill is not None:
        need({k:skill[k] for k in ('revision','digest')}=={k:expected[k] for k in ('revision','digest')} and digest(skill['document'])==skill['digest'],'PRODUCTION_SKILL_PREIMAGE_CHANGED')
        need(skill['document']['account']==d['account'] and skill['document']['rules']==expected['rules'],'PRODUCTION_SKILL_ACCOUNT_OR_RULES')
    characters=decode(raws['characters.json'])['characters'];uids={r['uid']for r in characters}
    need((d['setup_uid']is None or d['setup_uid']in uids) and all(r['uid']in uids for r in d['initial_learned']),'PRODUCTION_UNKNOWN_CHARACTER')
    hashed(Path(d['features']['path']),d['features']['sha256'],32768)
    return inventory

def validate_rule_preimage(packet, rules):
    from dataclasses import asdict
    rule_hash=digest([asdict(r)for r in rules])
    previous=packet.values()['skill_preimage']
    need(previous is None or previous['rules']==rule_hash,'PRODUCTION_RULE_MIGRATION_REQUIRED')
    return rule_hash

def cleanup_unstarted(plan,buff,primary):
    # Both steps run. Diagnostics cannot hide the original refusal/cancellation.
    first=None
    for label,step in (('plan',lambda:plan._retire_refs()if plan is not None else None),('buff',buff.close)):
        try:step()
        except BaseException as secondary:
            if first is None:first=secondary
            try:BaseException.add_note(primary,'Production '+label+' cleanup raised '+type(secondary).__name__)
            except BaseException:pass
    return first

def issue(packet,*,book_input=None,catalog_frame_keys=False,multi_self=False):
    inventory=validate_copy(packet);d=packet.values();mods=load_cohort()
    helper=mods['canonical_feature_bootstrap']
    need(type(catalog_frame_keys)is bool and type(multi_self)is bool and (not multi_self or catalog_frame_keys),'BUFF_EXPLICIT_CATALOG_FRAME_KEY_OPT_IN')
    configured=production_rules(mods,packet,catalog_frame_keys=catalog_frame_keys,multi_self=multi_self)
    rules,key_policy=configured if catalog_frame_keys else (configured,None)
    from tools.local_original_session import settings
    hashed(ROOT/'tools/local_original_session/settings.py',SETTINGS_SHA)
    need(Path(settings.__file__).resolve()==(ROOT/'tools/local_original_session/settings.py').resolve(),'PRODUCTION_EXACT_SETTINGS_SOURCE')
    settings.SettingsStore(Path(d['copy_root'])/'account-settings.bin',d['account'],profile_path=Path(d['copy_root'])/'characters.json')
    rule_hash=validate_rule_preimage(packet,rules)
    pins={key:sha(Path(mods[key].__file__).read_bytes()) for key in ('buff_lifecycle','buff_skill_document','cast_route','buff_source_response')}
    buff=mods['buff_bootstrap'].BuffBootstrap(root=ROOT,account=d['account'],rules=rules,
        clock=lambda:time.time_ns()//1000000,allowlist=tuple(r.spell_id for r in rules),module_pins=pins,key_policy=key_policy,
        initial_learned=tuple((r['uid'],tuple(r['learned']),r['before_digest'])for r in d['initial_learned']))
    def pin(name):
        m=mods[name];p=Path(m.__file__).resolve();return helper.SourceModule(m,p,sha(p.read_bytes()))
    def catalog(api):
        class ProductionCatalog(api.CatalogOwner):
            def current_digest(self,binding):return rule_hash
        return ProductionCatalog()
    core=ROOT/'work/local_original_session/implementation-3/skill-buff/buff-effective-stats-v2/canonical_batch.py'
    plan=None
    initializer=None
    try:
        if book_input is not None:
            need(all(not r['learned'] for r in d['initial_learned']),'BOOK_NO_INITIAL_LEARNED_GRANT')
            book_sources=load_book_sources(multi_self=multi_self)
            book_sources['spell_book_policy'].bind_local_book_learning(buff,
                pin('spell_book_learning'),pin('spell_book_delivery'),pin('spell_book_policy'))
        if inventory['version']==1:
            path=ROOT/'work/local_original_session/implementation-3/skill-buff/buff-production-input-v1/full_buff_initializer.py'
            spec=importlib.util.spec_from_file_location('_full_buff_initializer',path)
            module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
            exec(compile(hashed(path,INITIALIZER_SHA),str(path),'exec'),module.__dict__)
            initializer=module.FullBuffInitializer(profile=Path(d['copy_root'])/'characters.json',expected_inventory_sha256=d['files']['inventory.json'],account=d['account'])
            initializer_source=helper.SourceModule(module,path,INITIALIZER_SHA)
        else:initializer_source=None
        plan=helper.CanonicalFeatureBootstrap(profile=Path(d['copy_root'])/'characters.json',fixture_root=Path(d['copy_root']),
            core_path=core,core_sha256=CORE_SHA,aggregate_source=pin('inventory_aggregate'),
            resource_document_source=pin('hp_resource_document'),resource_owner_source=pin('hp_resource_owner'),
            status_source=pin('hp_status'),skill_core_source=pin('skill_buff'),skill_schema_source=pin('buff_skill_document'),
            catalog_owner_factory=catalog,participant_capability_factory=buff.participant_capability_factory,
            skill_schema_factory=buff.skill_schema_factory,runtime_capability_factory=buff.runtime_capability_factory,
            catalog_digest=rule_hash,setup_uid=d['setup_uid'],shop=None,trade=None,
            original_update_sources=(pin('broker'),pin('inventory_store'),pin('inventory_update')),
            delivery_sources=(pin('canonical_delivery'),pin('skill_cost_delivery')),buff=buff,
            full_buff_initializer=initializer,full_buff_initializer_source=initializer_source,
            inventory_observer_source=pin('inventory_observe'))
        base=mods['feature_config'].load(Path(d['features']['path']))
        need(type(base)is mods['feature_config'].Features and base.item_use_policy is None and base.item_equipment_policy is None and not base.spawns,'PRODUCTION_BUFF_ONLY_FEATURES_REQUIRED')
        # Root supplies exact inventory/frame configuration. Full Buff explicitly
        # selects existing status/update policies, without any stat/input value.
        features=replace(base,canonical_bootstrap=plan,hp_status_policy=mods['hp_status'].POLICY,
            inventory_update_policy=mods['broker'].INVENTORY_UPDATE_POLICY,
            item_use_policy=(None if book_input is None else mods['item_use_session'].POLICY),
            item_equipment_policy=(None if book_input is None else mods['item_equipment_effect'].POLICY),
            item_equipment_first_enable=(base.item_equipment_first_enable if book_input is None else False))
        source=mods['inventory_store'].InventoryStore(Path(d['copy_root'])/'characters.json',
            policy=mods['inventory_store'].COLLECTION_STORE_POLICY,custody_policy=base.inventory_custody_policy,
            aggregate_capability=plan.capability)
        need(source.path==Path(d['copy_root'])/'inventory.json','PRODUCTION_SAME_SOURCE_STORE')
        # InventoryStore has no registration or close API; this is an ordinary
        # read object, never a BatchStore/owner. Do not retain it in Issued.
        del source
        validate_copy(packet) # constructor is read-only; no fixture write/seed.
        result=Issued(packet,plan,features,mods);result.recheck();return result
    except BaseException as primary:
        cleanup_unstarted(plan,buff,primary)
        raise

def launch_packet(path, argv, *, catalog_frame_keys=False,multi_self=False):
    """Integration-owned invocation only; delegates directly to original main."""
    return issue(load_packet(path),catalog_frame_keys=catalog_frame_keys,multi_self=multi_self).launch(argv)


_SPELL_SOURCES=None
def spell_sources(*,multi_self=False):
    global _SPELL_SOURCES
    mods=load_cohort()
    rows=(('_buff_spell_runtime_v1',(BOOK_ROOT/'buff-multi-books-v1/spell_runtime.py'if multi_self else ROOT/'work/local_original_session/integration-1/spell-collector-serial366-v1/spell_runtime.py'),('0a3285da9965d0805c1c7b2587c95d80639d247005a1c64d8478b4b351eb540b'if multi_self else 'c3ccd54edf1f81c7ad6950d844ae9c61895beae1d1cc1fdfcb493e0e1e46d0ac')),
          ('_buff_spell_whole_entry_v1',ROOT/'work/local_original_session/implementation-3/skill-buff/spell-normal-learning-v1/spell-native-collector-permission-v1/spell_whole.py','1ed4e1ec9682823db0a4551efb6fd9bb8be95da7a994b1dcb521d0477466f06d'))
    if _SPELL_SOURCES is not None:
        for module,(_,path,pin)in zip(_SPELL_SOURCES,rows):
            hashed(path,pin)
            need(Path(module.__file__).resolve()==path.resolve()and sys.modules.get(module.__name__)is module,'SPELL_SOURCE_MODULE_CHANGED')
        return _SPELL_SOURCES
    modules=[]
    for name,path,pin in rows:
        need(name not in sys.modules,'SPELL_FRESH_SOURCE_NAMESPACE_REQUIRED')
        raw=hashed(path,pin);spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        try:exec(compile(raw,str(path),'exec'),module.__dict__)
        except BaseException:sys.modules.pop(name,None);raise
        modules.append(module)
    _SPELL_SOURCES=tuple(modules);return _SPELL_SOURCES

def make_spell_key(bits,namespace='ORIGINAL_4E60_CONFIG_DWORD',*,multi_self=False):
    # Bits are explicitly source-qualified by root, not a semantic skill ID.
    _,host=spell_sources(multi_self=multi_self);return host.SourceSpellKey32(bits,namespace)

def issue_spell(packet,source_key,*,post_return=False,catalog_frame_keys=False,multi_self=False):
    runtime,host=spell_sources(multi_self=multi_self)
    need(type(source_key)is host.SourceSpellKey32,'SPELL_QUALIFIED_INPUT_REQUIRED')
    source_key.__post_init__()
    issued=issue(packet,catalog_frame_keys=catalog_frame_keys,multi_self=multi_self)
    try:
        helper=issued.modules['canonical_feature_bootstrap']
        def source(module):
            path=Path(module.__file__).resolve();return helper.SourceModule(module,path,sha(path.read_bytes()))
        issued.plan.bind_spell_whole(runtime.Configuration(source(host),source_key,post_return=post_return),source(runtime))
        issued.recheck();return issued
    except BaseException as primary:
        cleanup_unstarted(issued.plan,issued.plan.buff,primary);raise


def learned_source():
    mods=load_cohort();path=ROOT/'work/local_original_session/integration-1/spell-host-binding-serial369-v1/learned_input.py';raw=hashed(path,LEARNED_SHA)
    name='tools.local_original_session.spell_learned_input'
    module=sys.modules.get(name)
    if module is None:
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        try:exec(compile(raw,str(path),'exec'),module.__dict__)
        except BaseException:sys.modules.pop(name,None);raise
    need(Path(module.__file__).resolve()==path.resolve(),'LEARNED_SINGLE_MODULE_GRAPH_REQUIRED')
    return mods['canonical_feature_bootstrap'].SourceModule(module,path,LEARNED_SHA)

def issue_roster(packet,*,roster_key_i32,post_return=False,catalog_frame_keys=False,multi_self=False):
    need(type(roster_key_i32)is int and -(1<<31)<=roster_key_i32<(1<<31),'LEARNED_EXPLICIT_INT32_ROW_KEY_REQUIRED')
    runtime,host=spell_sources(multi_self=multi_self);selector_source=learned_source();issued=issue(packet,catalog_frame_keys=catalog_frame_keys,multi_self=multi_self)
    try:
        helper=issued.modules['canonical_feature_bootstrap']
        def source(module):
            path=Path(module.__file__).resolve();return helper.SourceModule(module,path,sha(path.read_bytes()))
        issued.plan.buff.bind_learned_input(selector_source)
        issued.plan.bind_spell_whole(runtime.Configuration(source(host),None,roster_key_i32,post_return=post_return),source(runtime))
        issued.recheck();return issued
    except BaseException as primary:
        cleanup_unstarted(issued.plan,issued.plan.buff,primary);raise


def load_book_sources(*,multi_self=False):
    """Canonical names only; root loader must select the same dependencies."""
    mods=load_cohort()
    import tools.local_original_session as package
    rows=(('spell_book_learning',BOOK_ROOT/'book-empty-current-v8/book_batch.py','56712592ae2c48482c9da17acfbeeb24c37a92ce4884763c128fc3ff1e3edb6b'),
          ('spell_book_delivery',BOOK_ROSTER_ROOT/'book_delivery.py','ec3c4b8da9405d5d2eee5fd8ff10260e014593fd430fa7cdac04c3c5cbcc6b07'),
          ('spell_book_policy',(BOOK_ROOT/'buff-multi-books-v1/local_book_policy.py'if multi_self else BOOK_ROOT/'local-book-policy-v7a/local_book_policy.py'),('80b8fd98200f5a75849c68938acaedd42d9e87ab4a230c02d8c359c02ff83b68'if multi_self else '62bb6261bbbcd15fd82c93c2bfd1e5522291510182b628dd49f794c6531c2cf1')))
    for name,path,pin in rows:
        raw=hashed(path,pin);qualified='tools.local_original_session.'+name
        module=sys.modules.get(qualified)
        if module is None:
            spec=importlib.util.spec_from_file_location(qualified,path)
            module=importlib.util.module_from_spec(spec);sys.modules[qualified]=module
            setattr(package,name,module)
            try:exec(compile(raw,str(path),'exec'),module.__dict__)
            except BaseException:
                sys.modules.pop(qualified,None)
                if getattr(package,name,None)is module:delattr(package,name)
                raise
        need(Path(module.__file__).resolve()==path.resolve()
             and getattr(package,name,None)is module,'BOOK_SINGLE_CANONICAL_SOURCE_REQUIRED')
        mods[name]=module
        _SELECTED[name]=dict(path=str(path),sha256=pin)
    return mods

def issue_book(packet,*,uid,item_identifier,template,quantity,sequence,roster_key_i32,post_return,catalog_frame_keys=False,multi_self=False):
    # Strict original packet/copy/rules/clock/expiry and real Issued type remain
    # unchanged. Book selection is a separate explicit operating DTO.
    load_book_sources(multi_self=multi_self) # Select the exact cold book policy before DTO creation.
    runtime,host=spell_sources(multi_self=multi_self)
    book=runtime.BookInput(uid,item_identifier,template,quantity,sequence,roster_key_i32)
    book.validate();need(type(post_return)is bool,'BOOK_EXPLICIT_POST_RETURN_REQUIRED')
    selector_source=learned_source();issued=issue(packet,book_input=book,catalog_frame_keys=catalog_frame_keys,multi_self=multi_self)
    try:
        helper=issued.modules['canonical_feature_bootstrap']
        def source(module):
            path=Path(module.__file__).resolve();return helper.SourceModule(module,path,sha(path.read_bytes()))
        issued.plan.buff.bind_learned_input(selector_source)
        issued.plan.bind_spell_whole(runtime.Configuration(source(host),None,roster_key_i32,
            post_return=post_return,book_input=book),source(runtime))
        issued.recheck();return issued
    except BaseException as primary:
        cleanup_unstarted(issued.plan,issued.plan.buff,primary);raise
