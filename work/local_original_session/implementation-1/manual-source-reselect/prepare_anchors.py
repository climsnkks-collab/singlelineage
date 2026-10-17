"""Extract only accepted literal ranges; no decode, runtime or original writes."""
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sha = lambda b: hashlib.sha256(b).hexdigest()

def pinned(relative, expected):
    path = ROOT / relative
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError('source_pin:' + relative)
    return path, json.loads(raw)

def main():
    _, final = pinned('work/local_server_rea_20261016/run40_item_raw0_branch/source-evidence.json',
        '0f9b83dc5ec9ac8f4d07cf0efc508ff521ef5a0ba1186be16a24a7afd19ee567')
    _, accepted = pinned('work/local_server_rea_20261016/run40_item_raw0_branch/worker/source-evidence.json',
        'd74eae6753bba10803c22bd0ccb86e47016af92efc50912a1b3d4ce258f04c23')
    _, inventory = pinned('work/online_inventory_skill_source/source-contract.json',
        '17c2bcd6f40f90470f77a385dd78668be3a61d2686961fa83c58702dd0fc46a1')
    _, discovery = pinned('work/online_inventory_skill_source/discovery.json',
        '40b527878600b6616185f7285e6418c43f4674040669188ce7b493b5a3a6d651')
    _, sender = pinned('work/local_server_rea_20261016/run37_item_command_sender/worker/source-evidence.json',
        '9ae9425c6c5b322ee0577ad718424fc46e71ac456b316162482f6ff7b1792b7c')
    reader = ROOT / 'work/standalone_boot/child_launch_source.py'
    if sha(reader.read_bytes()) != '74d5087b561614b5322e26bdb74a77f404c8ebab28fecfff1bcd4a2749d6f7e8':
        raise ValueError('reader_pin')
    spec = importlib.util.spec_from_file_location('_accepted_literal_reader', reader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    view = module.Restored()  # Pinned file read only; no md.disasm/owner/graph query.
    if view.records != final['source_records']:
        raise ValueError('source_records')
    rows = []
    def add(rva, length, expected, role, executable=True):
        raw = view.read(rva, length)
        if sha(raw) != expected:
            raise ValueError('literal_pin:' + hex(rva))
        rows.append(dict(rva=rva, length=length, sha256=expected, role=role,
                         executable=executable))
        for offset in range(0, length, 16):
            chunk = raw[offset:offset+16]
            entries.append('{0x%x,%d,{%s}},' %
                (rva+offset, len(chunk), ','.join('0x%02x' % b for b in chunk)))
    entries = []
    for scope in accepted['reused_scopes']:
        if scope['label'] in ('common_entry', 'raw0_call', 'common_cleanup'):
            add(int(scope['rva'], 16), scope['length'], scope['sha256'], scope['label'])
    function = final['new_functions'][0]
    add(int(function['rva'], 16), function['length'], function['sha256'], 'raw0_helper')
    for check in inventory['source_checks']:
        add(check['rva'], check['length'], check['sha256'], 'inventory_layout')
    getter = next(f for f in discovery['functions'] if f['rva'] == '0x77340')
    lookup = sender['retained_lookup']
    for function, role in ((getter, 'original_owner_getter'), (lookup, 'original_item_lookup')):
        start, end = int(function['start_rva'],16), int(function['end_rva'],16)
        add(start, end-start, function['sha256'], role)
    (HERE/'use_item_code_anchors.inc').write_text('\n'.join(entries)+'\n', encoding='utf-8')
    data = []
    for rva, length, expected, role in (
        (0x4fe2b8, 1, sha(view.read(0x4fe2b8, 1)), 'raw0_selector'),
        (0x4fe264, 4, final['raw0_table']['jump_entry4_sha256'], 'raw0_jump')):
        raw = view.read(rva, length)
        if sha(raw) != expected:
            raise ValueError('data_pin')
        if role == 'raw0_selector' and raw != b'\0':
            raise ValueError('selector0')
        data.append('{0x%x,%d,{%s}},' % (rva, length, ','.join('0x%02x' % b for b in raw)))
        rows.append(dict(rva=rva, length=length, sha256=expected, role=role, executable=False))
    if sha(view.read(0x4fe2b8,145)) != final['raw0_table']['selector145_sha256']:
        raise ValueError('full_selector_parent_pin')
    (HERE/'use_item_data_anchors.inc').write_text('\n'.join(data)+'\n', encoding='utf-8')
    tables=[]
    for role, table in (('Inventory',inventory['owners']['Inventory']),
                        ('ItemControl',inventory['inventory_control'])):
        count=table['prefix_bytes']//8
        slots=tuple(x-0x140000000 for x in struct.unpack('<'+'Q'*count,view.read(table['rva'],count*8)))
        if sha(struct.pack('<'+'Q'*count,*slots))!=table['normalized_sha256']:
            raise ValueError('table_pin:'+role)
        tables.append('{0x%x,%d,{%s}},' % (table['rva'],count,','.join('0x%x'%x for x in slots)))
    (HERE/'use_item_table_anchors.inc').write_text('\n'.join(tables)+'\n',encoding='utf-8')
    (HERE/'source-anchors.json').write_text(json.dumps(dict(schema='accepted-use-item-literals-v1',
        rows=rows, instruction_decode_calls=0, runtime_actions=0), indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status='PASS', literal_chunks=len(entries), data_chunks=len(data),
        accepted_ranges=len(rows), instruction_decode_calls=0, runtime_actions=0)))

if __name__ == '__main__':
    main()
