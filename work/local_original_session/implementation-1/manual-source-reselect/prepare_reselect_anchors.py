"""Accepted source metadata literals only; no decode, PE or runtime access."""
import hashlib,importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sha=lambda b:hashlib.sha256(b).hexdigest()
def pin(rel,expected):
    raw=(ROOT/rel).read_bytes()
    if sha(raw)!=expected:raise ValueError('pin:'+rel)
    return json.loads(raw)
def main():
    final=pin('work/local_server_rea_20261016/run45_reselect_saved_uid/source-evidence.json','dd631dc9922e06ddb97a5e65ef17ff11e89a762dbb3badaa1673e92599cf42fd')
    evidence=pin('work/local_server_rea_20261016/run45_reselect_saved_uid/worker/source-evidence.json','ca3ae00f6e497c779f44805eaf2abfe8b3f87c3cd63ac21bee77c680639f491e')
    follow=pin('work/local_character_creation_source/slot-followup.json',final['input_pins']['work/local_character_creation_source/slot-followup.json'])
    path=ROOT/'tools/local_movement_contract/source.py'
    if sha(path.read_bytes())!=final['input_pins']['tools/local_movement_contract/source.py']:raise ValueError('reader')
    spec=importlib.util.spec_from_file_location('_reselect_accepted_reader',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    _,view=m.view()
    if view.records!=evidence['source']['records']:raise ValueError('records')
    chunks=[];ranges=[]
    functions=[(int(evidence['new_direct_boundary']['owner'],16),int(evidence['new_direct_boundary']['end_exclusive'],16),evidence['new_direct_boundary']['whole_code_sha256'])]
    for key in ['0x93a290','0x9398f0','0x8f1b10']:
        f=follow[key];functions.append((int(key,16),int(f['end'],16),f['sha256']))
    for start,end,expected in functions:
        raw=view.read(start,end-start)
        if sha(raw)!=expected:raise ValueError('body:'+hex(start))
        ranges.append(dict(rva=hex(start),size=end-start,sha256=expected))
        for i in range(0,len(raw),16):
            part=raw[i:i+16];chunks.append('{0x%x,%d,{%s}},'%(start+i,len(part),','.join('0x%02x'%b for b in part)))
    (HERE/'reselect_code_anchors.inc').write_text('\n'.join(chunks)+'\n',encoding='utf-8')
    (HERE/'reselect-source-pins.json').write_text(json.dumps(dict(schema='accepted-reselect-source-ranges-v1',ranges=ranges,literal_chunks=len(chunks),decode_calls=0,runtime_actions=0),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PASS',ranges=len(ranges),literal_chunks=len(chunks),decode_calls=0,runtime_actions=0)))
if __name__=='__main__':main()
