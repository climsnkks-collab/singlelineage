"""Plan default. Arm before official original launch; typed read only."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import source, sampler
import argparse, ctypes as C, hashlib, importlib.util, json, os, time, uuid
ROOT=source.ROOT;WORK=source.WORK
CONTRACT=WORK/'source-contract.json';REVIEW=WORK/'root-review.json';READY=WORK/'ready.json'

def need(ok,reason):
    if not ok: raise sampler.Unknown(reason)
def metadata(path,bound=1024*1024):
    need(path.stat().st_size<=bound,'metadata_byte_bound')
    raw=path.read_bytes();need(len(raw)<=bound,'metadata_byte_bound');return raw
def expected_review():
    raw=metadata(CONTRACT);c=json.loads(raw)
    return dict(schema='lc-online-intro-capture-review-v1',reviewed=True,allow_read=True,
        original_program=str(source.ORIGINAL),original_sha256=source.CONTROL,
        source_sha256=source.hashes(),support_source_sha256=source.SUPPORT,
        contract_sha256=source.sha(raw),**source.BOUNDS,wait_for_unique_original=True,
        game_start_or_termination_allowed=False,memory_write_or_API_call_allowed=False,
        resource_master_or_auth_read_allowed=False,raw_pointer_or_packet_saved=False)

def preflight():
    raw=metadata(CONTRACT);c=json.loads(raw)
    need(c.get('schema')=='lc-online-intro-capture-source-v1' and c['original_sha256']==source.CONTROL
         and Path(c['original_program'])==source.ORIGINAL and c['bounds']==source.BOUNDS
         and c['support_source_sha256']==source.SUPPORT,'fixed_original_contract_required')
    rraw=metadata(REVIEW,32768);r=json.loads(rraw);expected=expected_review()
    need(all(type(r.get(k)) is type(v) and r[k]==v for k,v in expected.items()),'Root_review_required')
    for p,digest in source.SUPPORT.items(): need(source.sha(metadata(ROOT/p))==digest,'support_source_changed')
    # No persistent EXE/SDK pin before launch/update. The running image will be
    # pinned and checked again only after exact-path unique process discovery.
    need(source.sha(metadata(source.ORIGINAL,40*1024*1024))==source.CONTROL,'original_build_changed_reanalysis')
    return c,raw,r,rraw

def publish(path,row,bound=4194304):
    raw=(json.dumps(row,ensure_ascii=True,indent=2)+'\n').encode()
    need(len(raw)<=bound,'report_byte_bound')
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_bytes(raw);os.replace(temporary,path)

def native_class():
    native_path=ROOT/'tools/normal_online_memory/native.py'
    spec=importlib.util.spec_from_file_location('_online_intro_original_native',native_path)
    support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
    class Original(support.Native):
        def discover(self):
            h=self.k.CreateToolhelp32Snapshot(2,0)
            need(h!=C.c_void_p(-1).value,'inventory_denied')
            entry=support.Entry();entry.size=C.sizeof(entry);count=0;found=[]
            try:
                C.set_last_error(0);ok=self.k.Process32FirstW(h,C.byref(entry))
                while ok:
                    count+=1;need(count<=4096,'inventory_bound')
                    if entry.name.casefold()=='lc.exe':
                        q=self.k.OpenProcess(0x101000,False,entry.pid)
                        if not q: raise support.Unknown('LC_query_access_denied',C.get_last_error())
                        try:
                            try:
                                row=self.identity(q,entry.pid)
                                found.append({'pid':row['pid'],'birth':row['birth']})
                                need(len(found)<=4,'original_candidate_count_bound')
                            except support.Unknown as error:
                                if error.reason not in ('not_original_LC','process_exited'): raise
                        finally:self.k.CloseHandle(q)
                    C.set_last_error(0);ok=self.k.Process32NextW(h,C.byref(entry))
                need(C.get_last_error()==18,'inventory_incomplete')
            finally:self.k.CloseHandle(h)
            return found
        def collector_identity(self):
            from ctypes import wintypes as W
            times=[W.FILETIME() for _ in range(4)]
            need(self.k.GetProcessTimes(C.c_void_p(-1),*(C.byref(t) for t in times)),'collector_birth_unknown')
            return {'pid':os.getpid(),'birth':str(times[0].dwHighDateTime<<32|times[0].dwLowDateTime)}
        def validate(self):
            need(self.k.WaitForSingleObject(self.handle,0)==258,'process_exited')
            # A retained read-only handle is never reopened/replaced. Full
            # original path/birth/token identity is checked at attach and every
            # 2s; no disk hashing or module enumeration in sampling.
            if time.monotonic()>=getattr(self,'next_identity_check',0):
                super().validate();self.next_identity_check=time.monotonic()+2
    return Original

def summarize(samples):
    # Poll intervals only. An absent task or cache is never a callback trace.
    result={};previous=None
    for row in samples:
        scene=row.get('scene',{});kind=scene.get('current',{}).get('kind','unknown')
        result[kind]=result.get(kind,0)+1
        if kind!='unknown' and kind!=previous: previous=kind
    return {'scene_sample_counts':result,'event_exact_order_proven':False,
            'timer_expiry_race_cause_proven':False,'actual_widget_activation_proven':False}

def modules_ready(n,clock=None,sleep=None):
    """Only Toolhelp ERROR_BAD_LENGTH during early module initialization."""
    clock=clock or time.monotonic;sleep=sleep or time.sleep
    started=clock();retries=0
    while True:
        n.validate()
        try:
            game=n.modules()['LC']
            return game,{'status':'OBSERVED','retry_count':retries,
                         'delay_seconds':round(clock()-started,6),'terminal_reason':None}
        except Exception as error:
            transient=(getattr(error,'reason',None)=='module_query_denied'
                       and getattr(error,'native_error',None)==24)
            remaining=1.0-(clock()-started)
            if not transient or remaining<=0 or retries>=10:
                error.module_ready_metadata={'status':'REFUSED','retry_count':retries,
                    'delay_seconds':round(clock()-started,6),
                    'terminal_reason':getattr(error,'reason','module_query_failed'),
                    'native_error':getattr(error,'native_error',None)}
                raise
            retries+=1;sleep(min(0.1,remaining))

def watch():
    c,craw,r,rraw=preflight();n=native_class()(c,{'pid':0,'birth':'0'})
    started=time.monotonic();folder=WORK/('session-'+uuid.uuid4().hex);folder.mkdir()
    report=dict(schema='lc-online-intro-capture-session-v1',status='WAITING',
        original_sha256=source.CONTROL,source_sha256=r['source_sha256'],contract_sha256=source.sha(craw),
        review_sha256=source.sha(rraw),bounds=source.BOUNDS,candidate_inventory_changes=[],samples=[],
        game_started_or_modified=False,resource_master_or_auth_read=False,raw_pointer_or_packet_saved=False)
    identity=None
    try:
        # Code/contracts only are pinned while awaiting PURPLE's official start.
        for name,digest in r['source_sha256'].items():n.pin(HERE/name,digest,1024*1024)
        for name,digest in source.SUPPORT.items():n.pin(ROOT/name,digest,1024*1024)
        n.pin(CONTRACT,source.sha(craw),1024*1024);n.pin(REVIEW,source.sha(rraw),32768)
        ready=dict(schema='lc-online-intro-capture-ready-v1',status='READY',collector_identity=n.collector_identity(),
            source_sha256=r['source_sha256'],support_source_sha256=source.SUPPORT,
            contract_sha256=source.sha(craw),review_sha256=source.sha(rraw),**source.BOUNDS,
            process_attached=False,report_path=str(folder/'report.json'))
        publish(READY,ready,32768);publish(folder/'report.json',report)
        previous=None
        while time.monotonic()-started<source.BOUNDS['watch_wait_seconds']:
            found=n.discover()
            if found!=previous:
                need(len(report['candidate_inventory_changes'])<64,'inventory_change_bound')
                report['candidate_inventory_changes'].append({'watch_elapsed_seconds':round(time.monotonic()-started,6),
                    'candidate_count':len(found),'identities':found,'ambiguous':len(found)>1})
                previous=found
            if len(found)==1: identity=found[0];break
            # Multiple official same-path processes are recorded, never chosen
            # by PID order. Wait within the same finite admission interval.
            time.sleep(0.1)
        need(identity is not None,'unique_original_wait_timeout')
        n.expected=identity
        n.pin(source.ORIGINAL,source.CONTROL,40*1024*1024)
        report['identity']=n.attach();game,module_info=modules_ready(n)
        report['module_ready']=module_info;s=sampler.Sampler(n,c,game)
        capture_start=time.monotonic();report['watch_elapsed_seconds']=round(capture_start-started,6)
        report['status']='CAPTURING';publish(folder/'report.json',report)
        last_scene=None;index=0;dropped=0;overruns=0
        while index<source.BOUNDS['sample_limit']:
            remaining=capture_start+index*source.BOUNDS['interval_seconds']-time.monotonic()
            if remaining>0:time.sleep(remaining)
            if time.monotonic()-capture_start>source.BOUNDS['capture_seconds']+0.25:break
            begin=time.monotonic();row=s.sample()
            row.update(index=index,sample_start_elapsed_seconds=round(begin-capture_start,6),
                       sample_end_elapsed_seconds=round(time.monotonic()-capture_start,6))
            report['samples'].append(row)
            if row['observer_duration_seconds']>source.BOUNDS['interval_seconds']:overruns+=1
            report['dropped_schedule_slots']=dropped;report['overrun_samples']=overruns
            kind=row.get('scene',{}).get('current',{}).get('kind','unknown')
            if kind!=last_scene or index%20==0:
                report['summary']=summarize(report['samples']);publish(folder/'report.json',report);last_scene=kind
            if row.get('reason') in ('process_exited','total_byte_budget'):break
            index+=1
            # Do not burst heavy catch-up reads after an overrun. Account for
            # skipped slots explicitly; the gap remains an observation interval.
            next_slot=int((time.monotonic()-capture_start)/source.BOUNDS['interval_seconds'])
            if next_slot>index:
                dropped+=next_slot-index;index=next_slot
        report.update(status='OBSERVED',capture_elapsed_seconds=round(time.monotonic()-capture_start,6),
                      summary=summarize(report['samples']),dropped_schedule_slots=dropped,overrun_samples=overruns)
    except Exception as error:
        report['status']='REFUSED' if not report['samples'] else 'OBSERVED_PARTIAL'
        report['failure']={'reason':getattr(error,'reason','reader_internal_'+type(error).__name__),
                           'native_error':getattr(error,'native_error',None)}
        if hasattr(error,'module_ready_metadata'):report['module_ready']=error.module_ready_metadata
    finally:
        report['native_memory_counts']={'attempts':n.rpm_attempts,'full_successes':n.rpm_successes,'bytes_returned':n.rpm_bytes}
        publish(folder/'report.json',report)
        n.close()
    return dict(status=report['status'],report_path=str(folder/'report.json'),samples=len(report['samples']),
                summary=report.get('summary'),failure=report.get('failure'),game_started_or_modified=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');a=p.parse_args()
    try:
        row=watch() if a.watch else {'status':'PLAN','bounds':source.BOUNDS,'root_review_template':expected_review(),
            'process_attached':False,'game_started_or_modified':False,'actual_widget_activation':'UNKNOWN until separately sourced'}
    except Exception as error:row={'status':'REFUSED','reason':getattr(error,'reason','reader_internal_'+type(error).__name__)}
    print(json.dumps(row));return 0 if row['status'] in ('PLAN','OBSERVED','OBSERVED_PARTIAL') else 2
if __name__=='__main__': raise SystemExit(main())
