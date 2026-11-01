"""Offline M5 source selection. No server/client/port or user-save access."""
from pathlib import Path
import copy
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.local_original_session.world_terrain import WorldTerrain

OUT = Path(__file__).parent
DATA = OUT.parent
SQL = Path('D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql')
UML = Path('C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_0/data/uml')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def source(value, kind, ref, note=None):
    result = dict(value=value, source=kind, ref=ref)
    if note:
        result['note'] = note
    return result

def source_tables():
    tables = defaultdict(list)
    columns = {}
    current = None
    for line_no, line in enumerate(SQL.read_text(encoding='utf-8').splitlines(), 1):
        m = re.match(r'CREATE TABLE `([^`]+)`', line)
        if m:
            current = m[1]
            columns[current] = []
        elif current and line.startswith('  `'):
            columns[current].append(line.split('`')[1])
        elif current and line.startswith(')'):
            current = None
        m = re.match(r'INSERT INTO `([^`]+)` VALUES \((.*)\);', line)
        if m and m[1] in ('npc','npcaction','spawnlist_npc','shop','spawnlist','weapon','armor','etcitem'):
            # Every dump row is a single tuple. Preserve SQL null and escapes.
            values = re.findall(r"'((?:[^'\\]|\\.)*)'|\b(null)\b", m[2], re.I)
            vals = [None if null else value.replace("\\'", "'").replace('\\\\', '\\') for value, null in values]
            assert len(vals) == len(columns[m[1]]), (m[1],line_no,len(vals),columns[m[1]])
            row = dict(zip(columns[m[1]], vals))
            row['source_ref'] = f'l1jdb:{line_no}'
            tables[m[1]].append(row)
    return tables


def main():
    tables = source_tables()
    npcs = {int(r['npcid']): r for r in tables['npc']}
    actions = {int(r['npcid']): r for r in tables['npcaction']}
    native = defaultdict(list)
    sprites = set()
    for i,line in enumerate((ROOT/'work/source_game_data/native-dump-v1.jsonl').read_text(encoding='utf8').splitlines(),1):
        row=json.loads(line)
        if row['table']=='npc' and row.get('name'):
            fields={f['number']:f.get('scalar') for f in row['fields']}
            native[row['name']['reference']].append(dict(id=row['id'], name_token=row['name']['reference'], name_ko=row['name']['KR'], sprite_f2=fields.get(2),source_ref=f'native-dump:{i}'))
            sprites.add(fields.get(2))
    # Source rows for existing selected item mappings retain their prior review.
    sale_templates={}
    for milestone in ('m2','m4'):
        for row in read(DATA/milestone/'shop_sales.json')['sales']:
            sale_templates.setdefault(row['item_id'],row)
    itemrows={}
    for table in ('weapon','armor','etcitem'):
        for row in tables[table]:
            key = int(row['item_id'])
            itemrows[key]=(table,row)
    region_lines=(ROOT/'work/local_resource_provider/assets/data/region.jsonc').read_text(encoding='utf8').splitlines()
    regions={}
    for i,line in enumerate(region_lines,1):
        if line.strip().startswith('{'):
            row=json.loads(line.strip().rstrip(','))
            regions[row['_id']]=(row,i)
    town_specs=[('kent','켄트성 마을',[152],50020,'stanley2',(33050,32782)),
                ('windawood','우드벡 마을',[147,148],50054,'trey2',(32640,33203)),
                ('giran','기란 마을',[160,161],50036,'wilma2',(33438,32796)),
                ('oren','오렌 마을',[168],50051,'kirius2',(34062,32278)),
                ('heine','하이네 마을',[164,165,166],50066,'riol2',(33612,33257))]
    terrain=WorldTerrain.load(map_ids=(4,))
    for line in (ROOT/'work/asset_link_audit_20261007/sprite/current-parsed.jsonl').read_text(encoding='utf8').splitlines():
        sprites.add(json.loads(line)['sprite_id'])
    def inside(ids,x,y):
        return any(r['_bounds']['_left']<=x<=r['_bounds']['_right'] and r['_bounds']['_top']<=y<=r['_bounds']['_bottom'] for r,_ in (regions[k] for k in ids))
    towns=[]; placements=defaultdict(list); town_for={}; terrain_checks=[]
    for tid,name,rids,tele,stem,point in town_specs:
        assert terrain.can_stand(4,*point) is True,(tid,point)
        t=dict(town_id=tid,name_ko=name,map_id=4,region_ids=rids,
               regions=[dict(region_id=k,bounds=regions[k][0]['_bounds'],source_kind='client',source_ref=f'region.jsonc:{regions[k][1]}') for k in rids],
               teleporter_id=tele,menu_stem=stem,return_point=dict(map_id=4,x=point[0],y=point[1],heading=5),
               return_source=dict(kind='local_policy',ref='Teleporter.xml silver-'+{'windawood':'woods','kent':'kent','giran':'giran','oren':'oren','heine':'heine'}[tid],note='Fixed L1J silver destination selected for recall/death; not original Classic GetBack rule'))
        towns.append(t)
        for raw in tables['spawnlist_npc']:
            if int(raw['mapid'])!=4 or not inside(rids,int(raw['locx']),int(raw['locy'])):
                continue
            npc_id=int(raw['npc_templateid']); row={k:(int(v) if k not in ('location','source_ref') else v) for k,v in raw.items() if k!='npc_templateid'}
            row['town_id']=tid
            row['enabled_in_l1j']=row['count']>0
            row['terrain_can_stand']=terrain.can_stand(4,row['locx'],row['locy'])
            row['placement_status']='LOCAL_l1j_center_client_s32_checked'
            placements[npc_id].append(row); town_for[row['id']]=tid
            terrain_checks.append(dict(kind='npc',npc_id=npc_id,spawn_id=row['id'],x=row['locx'],y=row['locy'],can_stand=row['terrain_can_stand']))
    rows=[]; shoprows=[]; allsales=[]
    shop_by_npc=defaultdict(list)
    for r in tables['shop']:
        shop_by_npc[int(r['npc_id'])].append(r)
    existing={}
    for milestone in ('m2','m4'):
        d=read(DATA/milestone/'town_npcs.json')
        for key in ('npcs','special_npcs','adjacent_npcs'):
            for r in d.get(key,[]): existing.setdefault(r['l1j_npc_id'],r)
    for npc_id,spawns in placements.items():
        n=npcs[npc_id]; token=n['nameid']; candidates=native[token]
        exact=[c for c in candidates if c['sprite_f2']==int(n['gfxid'])]
        selected=exact[0] if len(candidates)==len(exact)==1 else None
        a=actions.get(npc_id,{})
        classification=('warehouse' if n['impl']=='L1Dwarf' else 'teleporter' if n['impl']=='L1Teleporter' else 'inn_menu_candidate' if a.get('normal_action','').lower()=='inn' else 'merchant' if shop_by_npc[npc_id] else 'dialogue')
        r=dict(l1j_npc_id=npc_id,l1j_name=n['name'],name_token=token,l1j_impl=n['impl'],classification=classification,l1j_npc_ref=n['source_ref'],l1j_source_row=n,scope='village',spawns=spawns,shop_row_count=len(shop_by_npc[npc_id]),
               dialogue=dict(npcaction_row_present=bool(a),normal_action=a.get('normal_action'),caotic_action=a.get('caotic_action'),teleport_url=a.get('teleport_url'),teleport_urla=a.get('teleport_urla'),source_ref=a.get('source_ref'),status='L1J_source_stems_only'),classic_npc_candidates=candidates,selected_classic_npc_id=selected['id'] if selected else None,selected_classic_sprite_id=selected['sprite_f2'] if selected else None,
               mapping_status='unique_token_and_sprite_catalog_only' if selected else 'unknown_or_ambiguous_native_identity',l1j_gfxid=int(n['gfxid']),
               same_number_classic_sprite_candidate=dict(sprite_id=int(n['gfxid']),source_kind='local_policy',basis='L1J gfx matches a present client NPC sprite; graphic number alone is not identity') if int(n['gfxid']) in sprites else None)
        rows.append(r)
        if shop_by_npc[npc_id]:
            shoprows.append(dict(r,spawn=spawns[0],spawn_ref=spawns[0]['source_ref']))
            for raw in shop_by_npc[npc_id]:
                item=int(raw['item_id']); template=sale_templates.get(item)
                if template:
                    sale=copy.deepcopy(template)
                else:
                    table,ir=itemrows.get(item,('unknown',{}))
                    sale=dict(classic_item_candidates=[],selected_classic_item_id=None,mapping_status='UNRESOLVED_NO_REVIEWED_ITEM_MAPPING',l1j_bless=int(ir.get('bless') or 1),l1j_item_ref=ir.get('source_ref','UNKNOWN'),l1j_item_name=ir.get('name'),l1j_item_table=table)
                sale.update({k:int(raw[k]) for k in ('npc_id','item_id','order_id','selling_price','pack_count','purchasing_price')})
                sale.update(npc_sells_to_player=sale['selling_price']>=0,
                    npc_buys_from_player=sale['purchasing_price']>=0,
                    effective_pack_count=sale['pack_count'] or 1,
                    base_selling_price_per_pack=sale['selling_price'],
                    base_unit_price_fraction=dict(numerator=sale['selling_price'],denominator=sale['pack_count'] or 1))
                sale.update(source_ref=raw['source_ref'],l1j_source_row=raw,price_status='LOCAL_l1j_raw_base_x1_tax0',reused_from='m2/m4 reviewed item mapping only' if template else None)
                allsales.append(sale)
    header=dict(version=1,status='LOCAL_POLICY_SOURCE_STATIC_CHECKED_RUNTIME_UNRUN',reference_paths=dict(l1jdb=str(SQL),native_dump='work/source_game_data/native-dump-v1.jsonl',region='work/local_resource_provider/assets/data/region.jsonc'),scope='five map4 village unions; count0/ambiguous/blocked rows preserved')
    write('town_npcs.json',dict(header,npcs=rows,special_npcs=[],adjacent_npcs=[]))
    write('shop_npcs.json',dict(header,npcs=shoprows))
    write('shop_sales.json',dict(header,sales=allsales))
    write('towns.json',dict(header,towns=towns,windawood_limit='Windawood service village is Woodbec147/148. Castle111 and broad field149 are not the same town region.'))
    # Read current authenticated client resources; no existing client asset is
    # changed. Persist exact text so runtime never needs the provider/decryption.
    sys.path.insert(0,str(ROOT/'tools/local_resource_provider'))
    from provider import AssetProvider, ProviderError
    provider=AssetProvider(); (OUT/'uml').mkdir(exist_ok=True)
    menu_resources={}
    try:
        required=('steve2','stanley2','trey2','wilma2','kirius2','riol2','storage','inn')
        shop_stems={r['dialogue']['normal_action'] for r in rows if r['shop_row_count'] and r['dialogue']['normal_action']}
        for stem in (*required,*sorted(shop_stems|{s+'1' for s in shop_stems if not s[-1].isdigit()})):
            if stem in menu_resources:continue
            try:raw,event=provider.read(f'data/uml/{stem}.uml')
            except (FileNotFoundError,KeyError,ProviderError):
                if stem in required:raise
                continue
            (OUT/'uml'/f'{stem}.uml').write_bytes(raw)
            text=raw.decode('utf8')
            literals=re.findall(r'action="([^"]+)"',text)
            menu_resources[stem]=dict(stem=stem,actions=list(dict.fromkeys(literals)),source_kind='client',asset=f'data/uml/{stem}.uml',artifact=f'uml/{stem}.uml',provider_event=event)
    finally:
        provider.close()
    write('npc_menus.json',dict(header,resources=menu_resources,npc_to_resource_status='LOCAL speaker/role mapping; raw current resource and literal actions are client evidence only'))
    xmlpath=SQL.parents[1]/'data/xml/NpcActions/Teleporter.xml'
    xmltext=xmlpath.read_text(encoding='utf8')
    xml=ET.fromstring(xmltext)
    route_rows=[]
    for npc_id,stem in [(50024,'steve2')]+[(t[3],t[4]) for t in town_specs]:
        routes=[]; unavailable=[]
        for literal in menu_resources[stem]['actions']:
            candidates=[]
            for a in xml.iter('Action'):
                if a.get('Name')!='teleport '+literal or a.get('NpcId')!=str(npc_id):continue
                for trip in a.iter('Teleport'):
                    ref=f'{xmlpath}:action[{a.get("Name")},NpcId={npc_id}]'
                    candidates.append(dict(action='teleport '+literal,name=literal,map_id=int(trip.get('Map')),x=int(trip.get('X')),y=int(trip.get('Y')),heading=int(trip.get('Heading')),price=int(trip.get('Price')),max_level_exclusive=None,source_ref=ref))
            # XML contains repeated lawful branches. Choosing the lowest raw
            # price is an explicit local policy, not inferred lawful behavior.
            available=[r for r in candidates if r['map_id'] in (0,4) and terrain.can_stand(4,r['x'],r['y']) is True] # map0 evaluated below
            available=[r for r in available if r['map_id']==4]
            if available:
                selected=dict(min(available,key=lambda r:r['price']));selected['price_policy']='LOCAL minimum listed XML raw price, x1/tax0; branch not original observation';selected['reference_candidates']=candidates; routes.append(selected)
            else:unavailable.append(dict(action=literal,reason='NO_SUPPORTED_STANDABLE_XML_DESTINATION',reference_candidates=candidates))
        route_rows.append(dict(l1j_npc_id=npc_id,stem=stem,destinations=routes,unavailable=unavailable))
    baseline=read(DATA/'m2/town_services.json')
    # Retain the attributed rental/key policies when rebuilding unrelated M5 data.
    # The source is the existing generated service document, falling back to the
    # checked-in inn definition table if this is the first M5 build.
    inn_keys={70070:(10106,'우드벡'),70031:(10108,'기란'),70065:(10114,'오렌'),70084:(10110,'하이네')}
    rental_sources=dict(baseline['inns'][0]['rental_sources'])
    inns=[]
    for r in rows:
        if r['classification']!='inn_menu_candidate':continue
        key,town_name=inn_keys[r['l1j_npc_id']]
        policy=dict(baseline['inns'][0]['rental_policy'],room_key=key,hall_key=key+1,
            room_name=f'여관 열쇠({town_name} 마을)',hall_name=f'여관 홀 열쇠({town_name} 마을)')
        inns.append(dict(l1j_npc_id=r['l1j_npc_id'],name=r['l1j_name'],price=100,
            price_source='local_policy',runtime_status='LOCAL_RENTAL_KEY_THRESHOLD_RECOVERY_NO_INTERIOR',
            source_ref=r['l1j_npc_ref'],reused_from='m2/town_services.json rental policy',
            rental_policy=policy,rental_sources=rental_sources))
    banks=[dict(l1j_npc_id=r['l1j_npc_id'],name=r['l1j_name'],source_ref=r['l1j_npc_ref']) for r in rows if r['classification']=='warehouse']
    write('town_services.json',dict(header,teleporters=route_rows,inns=inns,warehouse=dict(baseline['warehouse'],npcs=banks),inn_unavailable=[dict(town_id='kent',reason='NO_INN_SOURCE_PLACEMENT_IN_CLIENT_REGION152_UNION')]))
    # Field subsets reuse established template/drop definitions. Select source
    # centres within each named field and outside every village safety margin.
    catalog={}
    for milestone in ('m1','m3','m4'):
        for r in read(DATA/milestone/'monsters.json')['monsters']:
            catalog[r['l1j_npcid']['value']]=r
    fields=[('kent',[153,154]),('windawood',[149]),('giran',[162,163]),('oren',[169,170]),('heine',[167])]
    groups=[]; chosen={}
    for tid,rids in fields:
        candidates=[r for r in tables['spawnlist'] if int(r['mapid'])==4 and int(r['npc_templateid']) in catalog and int(r['count'])>0 and inside(rids,int(r['locx']),int(r['locy']))]
        town=next(t for t in towns if t['town_id']==tid); point=town['return_point']
        candidates.sort(key=lambda r:max(abs(int(r['locx'])-point['x']),abs(int(r['locy'])-point['y'])))
        used=set()
        for raw in candidates:
            template=catalog[int(raw['npc_templateid'])]; tpl=template['template_id']['value']
            if tpl in used: continue
            cx,cy=int(raw['locx']),int(raw['locy']); best=None
            for radius in range(21):
                for dx in range(-radius,radius+1):
                    for dy in range(-radius,radius+1):
                        if max(abs(dx),abs(dy))!=radius:continue
                        x,y=cx+dx,cy+dy
                        if not all(inside(rids,xx,yy) for xx in (x-3,x+3) for yy in (y-3,y+3)):continue
                        if any(inside(t[2],xx,yy) for t in town_specs for xx in (x-14,x,x+14) for yy in (y-14,y,y+14)):continue
                        if all(terrain.can_stand(4,xx,yy) is True for xx in range(x-3,x+4) for yy in range(y-3,y+4)):
                            best=(x,y);break
                    if best:break
                if best:break
            if best is None:continue
            x,y=best;ref=raw['source_ref']; used.add(tpl);chosen[tpl]=template
            groups.append(dict(group_id=source(f'm5_{tid}_{tpl}','local_policy',ref),template_id=source(tpl,'client',template['template_id']['ref']),map_id=source(4,'client','region.jsonc map4'),rect=source(dict(x1=x-3,y1=y-3,x2=x+3,y2=y+3),'local_policy',ref,'7x7 client S32 checked; within20 tiles of source centre; village14 buffer'),target_count=source(2,'local_policy',ref,'finite two per group'),respawn_delay_ms=source(dict(min=int(raw['min_respawn_delay'])*1000,max=int(raw['max_respawn_delay'])*1000),'l1j',ref),town_id=tid,reference_source_row=raw))
            if len(used)>=4:break
    monsterdoc=dict(table='m5_reused_monsters',version=1,
        note='Exact sourced definitions reused; no new monster identity or stat invented.',
        ref_abbrev=read(DATA/'m4/monsters.json')['ref_abbrev'],
        reused_from=['data/m1/monsters.json','data/m3/monsters.json','data/m4/monsters.json'],
        monsters=list(chosen.values()))
    write('monsters.json',monsterdoc);write('spawns.json',dict(header,groups=groups))
    drops={};unresolved=[]
    for milestone in ('m1','m3','m4'):
        d=read(DATA/milestone/'drops.json')
        for tpl in chosen:
            if str(tpl) in d['drops']:drops[str(tpl)]=d['drops'][str(tpl)]
        unresolved.extend(r for r in d.get('unresolved',[]) if r.get('template_id') in chosen)
    write('drops.json',dict(header,drops=drops,unresolved=unresolved,chance_denominator=1000000))
    write('terrain_validation.json',dict(header,npc_centres=terrain_checks,return_points=[dict(town_id=t['town_id'],**t['return_point'],can_stand=True) for t in towns],spawn_rects=[dict(group_id=g['group_id']['value'],cells=49,passable=49,false=0,unknown=0) for g in groups]))
    print(json.dumps(dict(towns=len(towns),npc_templates=len(rows),placements=len(terrain_checks),shop_npcs=len(shoprows),shop_rows=len(allsales),selected_npcs=sum(r['selected_classic_npc_id'] is not None for r in rows),terrain=Counter(str(r['can_stand']) for r in terrain_checks),monster_templates=len(chosen),groups=len(groups)),ensure_ascii=False))

def build_supply_bases():
    """Incremental, placement-only supply additions; preserve reviewed M5 data.

    Run with --supply-bases. Only the six town/shop/service JSON documents are
    written. Existing return points, monster populations and assets are untouched.
    """
    from tools.local_original_session.game_data import load_items
    from tools.local_original_session.world_shop import _LEGACY_ITEM_RULES

    tables = source_tables()
    docs = {name: read(OUT / (name + '.json')) for name in
            ('towns', 'town_npcs', 'shop_npcs', 'shop_sales', 'npc_menus', 'town_services')}
    terrain = WorldTerrain.load(map_ids=(4,))
    npcs = {int(row['npcid']): row for row in tables['npc']}
    actions = {int(row['npcid']): row for row in tables['npcaction']}
    items = {int(row['item_id']): (table, row) for table in ('weapon', 'armor', 'etcitem')
             for row in tables[table]}
    supported = set(load_items()) | set(_LEGACY_ITEM_RULES)
    mappings = {}
    for milestone in ('m5', 'm4', 'm2'):
        for filename, key in (('shop_sales.json', 'sales'), ('shop_buyback_reference.json', 'rows')):
            path = DATA / milestone / filename
            if not path.is_file():
                continue
            for row in read(path)[key]:
                if row['npc_id'] in (70073, 70074, 60024, 70078, 60027):
                    continue  # Never turn this increment's output into its own mapping source.
                selected = row.get('selected_classic_item_id')
                candidates = [c for c in row.get('classic_item_candidates', ()) if c['id'] == selected]
                if selected in supported and len(candidates) == 1:
                    mappings.setdefault(row['item_id'], (row, f'data/{milestone}/{filename}:item_id={row["item_id"]}'))
    regions = {}
    for line_no, line in enumerate((ROOT / 'work/local_resource_provider/assets/data/region.jsonc').read_text(encoding='utf8').splitlines(), 1):
        if line.strip().startswith('{'):
            row = json.loads(line.strip().rstrip(','))
            regions[row['_id']] = (row, line_no)
    sprite_rows = {}
    for line_no, line in enumerate((ROOT / 'work/local_resource_provider/assets/data/list.spr').read_text(encoding='utf8').splitlines(), 1):
        match = re.match(r'#(\d+)\s', line)
        if match:
            sprite_rows[int(match[1])] = dict(sprite_id=int(match[1]), raw_header=line,
                ref=f'work/local_resource_provider/assets/data/list.spr:{line_no}')
    native = defaultdict(list)
    for line_no, line in enumerate((ROOT / 'work/source_game_data/native-dump-v1.jsonl').read_text(encoding='utf8').splitlines(), 1):
        row = json.loads(line)
        if row['table'] == 'npc' and row.get('name'):
            fields = {f['number']: f.get('scalar') for f in row['fields']}
            native[row['name']['reference']].append(dict(id=row['id'], name_token=row['name']['reference'],
                name_ko=row['name']['KR'], sprite_f2=fields.get(2), source_ref=f'native-dump:{line_no}'))

    # Reuse retained plaintext only after exact current signed/authenticated
    # catalog comparison. No claim that this run decrypted an outer archive.
    sys.path.insert(0, str(ROOT / 'tools/local_resource_provider'))
    from provider import AssetProvider
    provider = AssetProvider()
    try:
        def menu_resource(stem):
            asset = f'data/uml/{stem}.uml'
            catalog = provider.catalog[asset]
            path = UML / (stem + '.uml')
            raw = path.read_bytes()
            assert len(raw) == catalog['size'] and hashlib.sha256(raw).hexdigest() == catalog['sha256'], asset
            text = raw.decode('utf8')
            return dict(stem=stem, actions=list(dict.fromkeys(re.findall(r'action="([^"]+)"', text))),
                client_links=list(dict.fromkeys(re.findall(r'link="([^"]+)"', text))),
                source_kind='client', asset=asset, retained_plaintext=str(path),
                catalog_evidence=dict(sha256=catalog['sha256'], size=catalog['size'],
                    catalog_signature_authenticated=True, catalog_AEAD_authenticated=True,
                    retained_plaintext_hash_size_match=True),
                link_boundary='link loads a client-local document; only action literals issue 4ED4')

        # Sequential additions share these documents and do not enter towns[],
        # the existing recall/death consumer's fixed destination collection.
        specs = (('silver_knight', '은기사 마을', 136, (70073, 70074, 60024)),
                 ('fire_farmer', '화전민 마을', 142, (70078, 60027)))
        summaries = []
        for base_id, name, region_id, npc_ids in specs:
            region, line_no = regions[region_id]
            base = dict(town_id=base_id, name_ko=name, map_id=4, region_ids=[region_id],
                regions=[dict(region_id=region_id, bounds=region['_bounds'], source_kind='client',
                    source_ref=f'region.jsonc:{line_no}')], npc_ids=list(npc_ids),
                policy='LOCAL source-backed supply placements only; existing recall/death destinations unchanged')
            bases = docs['towns'].setdefault('supply_bases', [])
            bases[:] = [b for b in bases if b['town_id'] != base_id] + [base]
            for npc_id in npc_ids:
                n, a = npcs[npc_id], actions[npc_id]
                raw_spawns = [r for r in tables['spawnlist_npc'] if int(r['npc_templateid']) == npc_id and int(r['mapid']) == 4]
                assert len(raw_spawns) == 1, npc_id
                raw_spawn = raw_spawns[0]
                spawn = {k: (v if k in ('location', 'source_ref') else int(v))
                         for k, v in raw_spawn.items() if k != 'npc_templateid'}
                x, y = spawn['locx'], spawn['locy']
                bounds = region['_bounds']
                assert bounds['_left'] <= x <= bounds['_right'] and bounds['_top'] <= y <= bounds['_bottom'], npc_id
                assert terrain.can_stand(4, x, y) is True, (npc_id, x, y)
                spawn.update(town_id=base_id, enabled_in_l1j=spawn['count'] > 0,
                    terrain_can_stand=True, placement_status='LOCAL_l1j_center_client_s32_checked')
                shops = [r for r in tables['shop'] if int(r['npc_id']) == npc_id]
                candidates = native[n['nameid']]
                gfx = int(n['gfxid'])
                exact = [c for c in candidates if c['sprite_f2'] == gfx]
                selected = exact[0] if len(candidates) == len(exact) == 1 else None
                visual = sprite_rows[gfx]
                # Glen/Mellin have explicit named retained sprite headers. Orcm
                # uses the source's present orc-merchant visual; warehouses use
                # the existing LOCAL shared dwarf role, never a borrowed ID.
                named = n['name'].lower() in visual['raw_header'].lower()
                row = dict(l1j_npc_id=npc_id, l1j_name=n['name'], name_token=n['nameid'],
                    l1j_impl=n['impl'], classification='warehouse' if n['impl'] == 'L1Dwarf' else 'merchant',
                    l1j_npc_ref=n['source_ref'], l1j_source_row=n, scope='village', spawns=[spawn],
                    shop_row_count=len(shops), dialogue=dict(npcaction_row_present=True,
                        normal_action=a['normal_action'], caotic_action=a['caotic_action'],
                        teleport_url=a['teleport_url'], teleport_urla=a['teleport_urla'],
                        source_ref=a['source_ref'], status='L1J_source_stems_only'),
                    classic_npc_candidates=candidates, selected_classic_npc_id=selected['id'] if selected else None,
                    selected_classic_sprite_id=selected['sprite_f2'] if selected else gfx if named else None,
                    mapping_status='unique_token_and_sprite_catalog_only' if selected else
                        'client_named_sprite_only_no_native_template' if named else 'LOCAL_SOURCE_ROLE_VISUAL_NATIVE_IDENTITY_UNKNOWN',
                    l1j_gfxid=gfx, same_number_classic_sprite_candidate=dict(sprite_id=gfx,
                        source_kind='local_policy', basis='L1J role visual present in fixed client; not native NPC identity'),
                    client_sprite_evidence=visual,
                    supply_placement_policy='Exact L1J fixed centre/heading on current standable terrain; native screen/input unverified')
                target = docs['town_npcs']['npcs']
                target[:] = [r for r in target if r['l1j_npc_id'] != npc_id] + [row]
                stem = 'storage' if n['impl'] == 'L1Dwarf' else {'Glen': 'glen', 'Mellin': 'mellin', 'Orcm': 'orcm1'}[n['name']]
                resource = docs['npc_menus']['resources'].setdefault(stem, menu_resource(stem))
                role = 'warehouse' if n['impl'] == 'L1Dwarf' else 'shop'
                required = ['deposit', 'retrieve'] if role == 'warehouse' else ['buy', 'sell']
                assert set(required) <= set(resource['actions']), (npc_id, stem)
                binding = dict(l1j_npc_id=npc_id, role=role, initial_stem=stem, page_stems=[stem],
                    transitions={}, supported_service_actions=required if role == 'warehouse' else [],
                    status='LOCAL_CANDIDATE_BINDING', source_normal_action=a['normal_action'], source_ref=a['source_ref'],
                    boundary='Current catalog-matching client menu; source-backed LOCAL speaker/role binding. Native identity/input unverified; other actions not implemented.')
                bindings = docs['npc_menus']['runtime_bindings']
                bindings[:] = [b for b in bindings if b['l1j_npc_id'] != npc_id] + [binding]
                if role == 'warehouse':
                    banks = docs['town_services']['warehouse']['npcs']
                    banks[:] = [b for b in banks if b['l1j_npc_id'] != npc_id] + [dict(
                        l1j_npc_id=npc_id, name=n['name'], source_ref=n['source_ref'],
                        note='Existing LOCAL personal warehouse policy and storage menu; native identity unknown')]
                    continue
                merchants = docs['shop_npcs']['npcs']
                merchants[:] = [r for r in merchants if r['l1j_npc_id'] != npc_id] + [dict(row, spawn=spawn, spawn_ref=spawn['source_ref'])]
                sales = docs['shop_sales']['sales']
                sales[:] = [r for r in sales if r['npc_id'] != npc_id]
                supported_count = 0
                for raw in shops:
                    item_id = int(raw['item_id'])
                    template = mappings.get(item_id)
                    if template:
                        sale = copy.deepcopy(template[0])
                        sale['reused_item_mapping_from'] = template[1]
                        supported_count += 1
                    else:
                        table, item = items.get(item_id, ('unknown', {}))
                        sale = dict(classic_item_candidates=[], selected_classic_item_id=None,
                            mapping_status='UNRESOLVED_NO_SUPPORTED_REVIEWED_ITEM_MAPPING',
                            l1j_bless=int(item.get('bless') or 1), l1j_item_ref=item.get('source_ref', 'UNKNOWN'),
                            l1j_item_name=item.get('name'), l1j_item_table=table,
                            deferred_reason='No reviewed Classic mapping with supported item weight/stack policy; source row retained unavailable')
                    sale.update({k: int(raw[k]) for k in ('npc_id', 'item_id', 'order_id', 'selling_price', 'pack_count', 'purchasing_price')})
                    sale.update(npc_sells_to_player=sale['selling_price'] >= 0, npc_buys_from_player=sale['purchasing_price'] >= 0,
                        effective_pack_count=sale['pack_count'] or 1, base_selling_price_per_pack=sale['selling_price'],
                        base_unit_price_fraction=dict(numerator=sale['selling_price'], denominator=sale['pack_count'] or 1),
                        source_ref=raw['source_ref'], l1j_source_row=raw, price_status='LOCAL_l1j_raw_base_x1_tax0',
                        runtime_status='UNRUN')
                    sales.append(sale)
                summaries.append(dict(npc_id=npc_id, rows=len(shops), supported=supported_count,
                                      deferred=len(shops) - supported_count))
        for name, doc in docs.items():
            write(name + '.json', doc)
        print(json.dumps(dict(supply_bases=2, npc_placements=5, shops=summaries,
                             return_destinations='unchanged'), ensure_ascii=False))
    finally:
        provider.close()


if __name__ == '__main__':
    if sys.argv[1:] == ['--supply-bases']:
        build_supply_bases()
    else:
        main()
