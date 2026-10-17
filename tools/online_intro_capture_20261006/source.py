"""File-only original CONTROL source for a narrow online Intro observation."""
import sys
sys.dont_write_bytecode = True
import hashlib, importlib.util, json, re, struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = ROOT / 'work/online_intro_capture_20261006'
CONTROL = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
ORIGINAL = Path('D:/Lineage Classic/LC.exe')
BASE = 0x140000000
SUPPORT = {'tools/normal_online_memory/native.py': '449e4d39e88e4cf4889193ba88a8498f196bec1325bb56e6ff1399598bec4c28'}
BOUNDS = dict(watch_wait_seconds=300, capture_seconds=90, interval_seconds=0.25,
              sample_limit=361, typed_byte_limit=8192,
              total_typed_byte_limit=4194304, report_byte_limit=4194304)
NAMES = ('source.py', 'reader.py', 'sampler.py', 'tests.py')

def sha(raw): return hashlib.sha256(raw).hexdigest()
def hashes(): return {n: sha((HERE/n).read_bytes()) for n in NAMES}
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def build():
    if sha(ORIGINAL.read_bytes()) != CONTROL:
        raise ValueError('original_build_changed_reanalysis')
    # This loader reads recovered CODE/public RTTI only; it never reads the key.
    original_source = ROOT/'tools/normal_online_memory/source.py'
    if sha(original_source.read_bytes()) != '6d6b5291386a9b44e7834885d95754167648d93f22a448e5eaaba528e1fe83a9':
        raise ValueError('original_source_changed')
    original = load('_intro_original_source', original_source)
    v, _ = original.load_view()
    parent_raw = (ROOT/'work/normal_online_memory/source-contract.json').read_bytes()
    if sha(parent_raw) != '68526f47876b1b9b3720ef442dd0efd3ac80c26a833a7b47c829982955347aef':
        raise ValueError('original_parent_contract_changed')
    parent = json.loads(parent_raw)
    if parent['original_sha256'] != CONTROL: raise ValueError('original_contract_required')

    def table(at, count=3):
        values = struct.unpack('<'+'Q'*count, v.read(at, count*8))
        if not all(BASE <= x < BASE+parent['image_size'] for x in values):
            raise ValueError('source_table_target_range')
        return {'rva': at, 'targets': [x-BASE for x in values]}

    def rtti_tables(name):
        tag = name.encode()+b'\0'; types = []
        for section, raw in v.sections[1:]:
            for hit in re.finditer(re.escape(tag), raw): types.append(section+hit.start()-16)
        matches = []
        for typ in types:
            for section, raw in v.sections[1:]:
                for hit in re.finditer(re.escape(struct.pack('<I', typ)), raw):
                    col = section+hit.start()-12
                    try: fields = struct.unpack('<6I', v.read(col, 24))
                    except ValueError: continue
                    if fields[0] != 1 or fields[1] != 0 or fields[3] != typ or fields[5] != col: continue
                    for start, data in v.sections[1:]:
                        for found in re.finditer(re.escape(struct.pack('<Q', BASE+col)), data):
                            candidate = table(start+found.start()+8)
                            if candidate not in matches: matches.append(candidate)
        if len(matches) != 1: raise ValueError('unique_public_RTTI_table_required_'+name)
        return matches[0]

    tables = {role: [table(row['rva'], 8) for row in rows]
              for role, rows in parent['vtables'].items() if role in ('UI','NP','GameState')}
    tables['Scheduler'] = [rtti_tables('.?AVScheduleSubsystem@lineage@@')]
    widgets = {kind: rtti_tables('.?AV'+kind+'Layout@ui@lineage@@') for kind in ('CI','BI')}
    scenes = [dict(table(at,4), kind=kind, state_id=n) for n,kind,at in
              ((1,'Intro',0x11879b8),(2,'Lobby',0x1187e80),(3,'Login',0x1187f48),
               (4,'CharacterSelect',0x1187778),(5,'Land',0x1186f18))]
    checks = []
    expected = {
        0x9f99a9: 'cmp byte ptr [rcx + 0xfa], 0',
        0x9f99cf: 'cmp byte ptr [rax + 0x318], 0',
        0x9f99f0: 'cmp byte ptr [rbx + 0x498], 0',
        0x9fa688: 'cmp byte ptr [rsi + 0xf9], 0',
        0x9fd834: 'mov byte ptr [rax + 0xfa], 1',
        0xb38b8a: 'lea rcx, [rsi + 0x348]',
        0xb38b9f: 'mov rdx, qword ptr [rsi + 0x350]',
        0xb38bc3: 'mov rcx, qword ptr [rdx + 0x30]',
        0xb38bca: 'mov rcx, qword ptr [rdx + 0x38]',
        0xb46335: 'cmp rcx, qword ptr [rax + 0x10]',
    }
    for at, text in expected.items():
        ins = next(v.md.disasm(v.read(at,15),at,count=1))
        if ins.mnemonic+' '+ins.op_str != text: raise ValueError('original_instruction_'+hex(at))
        checks.append({'rva': at, 'bytes_hex': bytes(ins.bytes).hex(), 'instruction': text})
    # Existing original parent anchors establish Root/GI/FM/UI; fresh original
    # instruction bytes also bind scene pairs, timer handles, task float and map.
    addresses = [0xd3b2e,0xd3b3e,0xd3b4b,0xd3b52,0xd3b59,0xd3be3,
                 0xed594,0x2737da,0xb6d98b,0x140511,0x1404ec,
                 0x14ae02,0x14b41e,0x9f9581,0x9f958c,0x9f9680,
                 0x9f97c7,0xb4e1c5,0xb4e1cf,0xb4e295,0xb4e2d4,
                 0x9fd8c0,0x9fd8c4,0x9fd830,0xb4542d,0xb45b13]
    for at in addresses:
        ins = next(v.md.disasm(v.read(at,15),at,count=1))
        checks.append({'rva':at,'bytes_hex':bytes(ins.bytes).hex(),
                       'instruction': ins.mnemonic+' '+ins.op_str})
    # Current unmodified inline FM is availability+128; no master32 bytes.
    return dict(schema='lc-online-intro-capture-source-v1', original_program=str(ORIGINAL),
                original_sha256=CONTROL, image_size=parent['image_size'],
                SDK_program=parent['SDK_program'], tables=tables, widgets=widgets,
                scenes=scenes, one_time_task=table(0x1237ad0),
                closures=[table(0x12217b0),table(0x1221820)], checks=checks,
                layout=parent['layout'], bounds=BOUNDS, support_source_sha256=SUPPORT,
                parent_contract_sha256=sha(parent_raw), restored_records=v.records,
                runtime_cause_proven=False, cache_presence_is_active_widget=False,
                source_notes=['Original callback gates NP+498, not patched local FM.',
                              'UI cache map head+350/count+358; node pair+30/+38.',
                              'Scheduler map head+30/count+38; node ID+10/pair+18.',
                              'BI handle IDs+B8/+100, stored active byte+8.',
                              'Task remaining+B0 <=0 is derived finished, not callback evidence.'])

if __name__ == '__main__':
    WORK.mkdir(parents=True, exist_ok=True)
    row = build(); path = WORK/'source-contract.json'
    path.write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'SOURCE_READY','path':str(path),'checks':len(row['checks']),
                      'contract_sha256':sha(path.read_bytes()),'native_queries':0}))
