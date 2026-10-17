"""Read one exact owned clone's public scene state with candidate vtable pins."""
import argparse
import hashlib
import importlib.util
import json
import os
import struct
import time
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TARGET=ROOT/'work/standalone_boot/current-unmodified-clone/LC.exe'
SDK=TARGET.with_name('ncplatformsdk-cpp.dll')
CONTRACT=ROOT/'work/online_intro_capture_20261006/source-contract.json'
NATIVE=ROOT/'tools/normal_online_memory/native.py'
SAMPLER=ROOT/'tools/online_intro_capture_20261006/sampler.py'
FRAMES=ROOT/'tools/local_native_login_key_invoke_candidate/frames.py'
OUTPUT=ROOT/'work/local_native_scene_current'
PINS={NATIVE:'449e4d39e88e4cf4889193ba88a8498f196bec1325bb56e6ff1399598bec4c28',
      SAMPLER:'2253337013d3cfc0a12bcc5c6798fb56ebf0de333ed6517950dbc692e9d2cdeb',
      CONTRACT:'2c9af49767502c0b28f39a24dd24ffe44eb142ed9acf0cd2372dcc11bf87c7e5'}
SAMPLES=121
INTERVAL=.25

def need(ok,reason):
    if not ok:raise ValueError(reason)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def contract_for(candidate,expected_sha,installed=True):
    need(os.name=='nt','WINDOWS_REQUIRED')
    need(all(sha(path)==digest for path,digest in PINS.items()),'FROZEN_SCENE_READER_CHANGED')
    need(candidate.is_file() and candidate.name=='native-login.candidate.bin'
         and ROOT/'work' in candidate.parents,'WORKSPACE_CANDIDATE_REQUIRED')
    need(sha(candidate)==expected_sha,'EXACT_CANDIDATE_SOURCE_REQUIRED')
    if installed:need(sha(TARGET)==expected_sha,'EXACT_INSTALLED_CANDIDATE_REQUIRED')
    raw=candidate.read_bytes()
    pe=struct.unpack_from('<I',raw,0x3c)[0]
    image_size=struct.unpack_from('<I',raw,pe+24+0x38)[0]
    source=json.loads(CONTRACT.read_bytes())
    need(source['original_sha256']=='9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
         and source['image_size']==65622016 and image_size==65630208,
         'EXACT_SCENE_LAYOUT_REQUIRED')
    frames_module=load(FRAMES,'_current_scene_frames')
    changed=[]
    with frames_module.Frames(raw) as frames:
        for group in source['tables'].values():
            for row in group:
                values=struct.unpack('<'+'Q'*len(row['targets']),frames.read(row['rva'],8*len(row['targets'])))
                current=[v-0x140000000 for v in values]
                diffs=[i for i,(a,b) in enumerate(zip(current,row['targets'])) if a!=b]
                if diffs:
                    need(row['rva']==0x1182e30 and diffs==[4], 'UNDECLARED_PUBLIC_VTABLE_CHANGE')
                    changed.append((row['rva'],diffs))
                    row['targets']=current
        for row in source['scenes']:
            values=struct.unpack('<'+'Q'*len(row['targets']),frames.read(row['rva'],8*len(row['targets'])))
            need([v-0x140000000 for v in values]==row['targets'],'SCENE_VTABLE_SOURCE_CHANGED')
    need(changed==[(0x1182e30,[4])],'EXACT_ONE_GAMESTATE_VTABLE_CHANGE')
    source.update(original_program=str(TARGET),SDK_program=str(SDK),
                  original_sha256=expected_sha,image_size=image_size)
    return source

def sample(native,sampler):
    sampler.bytes=0
    sampler.read_limit=8192
    try:
        native.validate()
        route=sampler.route()
        state=sampler.unique(route[-1],'GameState')
        scene,raw=sampler.scene(state)
        need(sampler.read(state+0x360,36)==raw,'SCENE_CHANGED_AFTER_READ')
        need(sampler.route()==route,'ROOT_OWNER_CHANGED_AFTER_READ')
        native.validate()
        return {'status':'OBSERVED','current':scene['current']['kind'],
                'pending':scene['pending']['kind'],'root_ready':route[1],
                'root_phase':route[2],'visible_ui_proven':False}
    except Exception as error:
        return {'status':'UNKNOWN','reason':getattr(error,'reason',type(error).__name__),
                'current':'unknown','pending':'unknown','visible_ui_proven':False}

def watch(candidate,expected_sha,pid,birth):
    need(type(pid)is int and pid>0 and type(birth)is str and birth.isdecimal(),
         'EXACT_OWNED_IDENTITY_REQUIRED')
    contract=contract_for(candidate,expected_sha)
    native_module=load(NATIVE,'_current_scene_native')
    sampler_module=load(SAMPLER,'_current_scene_sampler')
    native=native_module.Native(contract,{'pid':pid,'birth':birth})
    try:
        attached=native.attach()
        need(attached['birth']==birth,'PID_BIRTH_CHANGED')
        game=native.modules()['LC']
        sampler=sampler_module.Sampler(native,contract,game)
        OUTPUT.mkdir(exist_ok=True)
        token=uuid.uuid4().hex
        stream_path=OUTPUT/('session-'+token+'.jsonl')
        rows=[];began=time.monotonic()
        with stream_path.open('x',encoding='utf-8')as stream:
            for index in range(SAMPLES):
                pause=began+index*INTERVAL-time.monotonic()
                if pause>0:time.sleep(pause)
                row=sample(native,sampler)
                row['elapsed_seconds']=round(time.monotonic()-began,3)
                row['monotonic_ns']=time.monotonic_ns()
                rows.append(row)
                stream.write(json.dumps(row)+'\n');stream.flush()
                if row['status']=='UNKNOWN' and row['reason']=='process_exited':break
        observed=[row for row in rows if row['status']=='OBSERVED']
        report={'schema':'lc-current-candidate-scene-watch-v1',
                'candidate_sha256':expected_sha,'identity':{'pid':pid,'birth':birth},
                'samples':len(rows),'observed_samples':len(observed),
                'last_observed':observed[-1] if observed else None,
                'character_select_memory_seen':any(row['current']=='CharacterSelect' for row in observed) if observed else None,
                'first_character_select_monotonic_ns':next((row['monotonic_ns'] for row in observed
                    if row['current']=='CharacterSelect'),None),
                'actual_visible_screen_proven':False,'memory_write_or_game_control':False,
                'raw_pointer_or_packet_saved':False,'sample_stream':str(stream_path)}
        path=OUTPUT/('session-'+token+'.json')
        with path.open('x',encoding='utf-8')as stream:
            json.dump(report,stream,indent=2);stream.write('\n')
        return {'status':'RECORDED','path':str(path),'samples':len(rows),
                'observed':len(observed),'character_select_memory_seen':report['character_select_memory_seen']}
    finally:native.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--sha')
    parser.add_argument('--pid',type=int)
    parser.add_argument('--birth')
    args=parser.parse_args()
    if args.preflight:
        need(args.candidate is not None and args.sha is not None,'EXACT_CANDIDATE_REQUIRED')
        contract_for(args.candidate.resolve(),args.sha,installed=False)
        print(json.dumps({'status':'STATIC_SCENE_CONTRACT_REVIEWED','candidate_sha256':args.sha,
                          'one_game_state_vtable_slot_updated':True,'game_or_memory_access':False}))
        return 0
    if not args.watch:
        print(json.dumps({'status':'PLAN','read_only':True,'exact_pid_birth_required':True,
                          'max_samples':SAMPLES}));return 0
    need(args.candidate is not None and args.sha is not None,'EXACT_CANDIDATE_REQUIRED')
    print(json.dumps(watch(args.candidate.resolve(),args.sha,args.pid,args.birth)))
    return 0
if __name__=='__main__':raise SystemExit(main())
