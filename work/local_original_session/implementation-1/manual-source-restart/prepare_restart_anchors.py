"""Accepted record literals only; no decode, PE analysis or runtime read."""
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def pin(relative,expected):
    path=ROOT/relative;raw=path.read_bytes()
    if sha(raw)!=expected:raise ValueError('pin:'+relative)
    return json.loads(raw)
def main():
    final=pin('work/local_server_rea_20261016/run44_restart_button_abi/source-evidence.json',
        '3418627d7f05ef4d7f80695a0d6b30db6210539127f18fe03880c497c572781f')
    pin('work/local_server_rea_20261016/run44_restart_button_abi/worker/source-evidence.json',
        'cc82948d3d9607ad00f4e7649a76adcc36c98ea93e3bc35b49cf7840ccd7482c')
    network=pin('work/normal_online_memory/source-contract.json',
        '68526f47876b1b9b3720ef442dd0efd3ac80c26a833a7b47c829982955347aef')
    reader=ROOT/'tools/local_movement_contract/source.py'
    if sha(reader.read_bytes())!='7319028e5b030341d30dc496b38a04a65c7f0ac8e753ddf090654544a9950ade':raise ValueError('reader_pin')
    spec=importlib.util.spec_from_file_location('_restart_fixed_record_reader',reader)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    _,view=module.view()  # Existing pinned record reader. No disasm/owner/graph query.
    if view.records!=final['source_provenance']['source_records']:raise ValueError('records')
    rows=[];entries=[]
    def add(start,length,expected,role):
        raw=view.read(start,length)
        if sha(raw)!=expected:raise ValueError('range:'+hex(start))
        rows.append(dict(rva=start,length=length,sha256=expected,role=role))
        for offset in range(0,length,16):
            chunk=raw[offset:offset+16]
            entries.append('{0x%x,%d,{%s}},'%(start+offset,len(chunk),','.join('0x%02x'%x for x in chunk)))
    for function in final['reused_instruction_evidence']:
        for window in function['windows']:
            add(int(window['start'],16),window['size'],window['sha256'],'accepted_'+function['entry'])
    for function in final['new_exact_callback_owner_boundary']:
        add(int(function['entry'],16),function['size'],function['sha256'],'accepted_owner_or_copy')
    getter=final['reused_GameStateSubsystem_getter']
    add(int(getter['start'],16),int(getter['end'],16)-int(getter['start'],16),getter['sha256'],'accepted_state_getter')
    table=network['vtables']['Network'][0];count=table['prefix_bytes']//8
    methods=tuple(x-0x140000000 for x in struct.unpack('<'+'Q'*count,view.read(table['rva'],count*8)))
    if table['rva']!=0x1199d18 or table['type_descriptor_rva']!=0x1669928 or count!=8 or \
        sha(struct.pack('<8Q',*methods))!=table['normalized_sha256']:raise ValueError('network_table')
    (HERE/'restart_code_anchors.inc').write_text('\n'.join(entries)+'\n',encoding='utf-8')
    (HERE/'restart_network_methods.inc').write_text(','.join('0x%x'%x for x in methods)+'\n',encoding='utf-8')
    (HERE/'restart-source-pins.json').write_text(json.dumps(dict(schema='accepted-restart-source-ranges-v1',
        ranges=rows,network_table=table,decode_calls=0,runtime_actions=0),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PASS',ranges=len(rows),literal_chunks=len(entries),network_slots=len(methods),decode_calls=0,runtime_actions=0)))
if __name__=='__main__':main()
