"""Focused synthetic tests; no native/process attachment or game execution."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy,json,struct,unittest
import source,sampler,reader

BASE=0x140000000
def q(*values):return struct.pack('<'+'Q'*len(values),*values)
class Memory:
    def __init__(self):self.data={};self.hook=None;self.reads=[]
    def put(self,at,raw):
        for n,b in enumerate(raw):self.data[at+n]=b
    def read(self,at,size,module=None):
        self.reads.append((at,size))
        if self.hook:self.hook(at,size)
        try:return bytes(self.data[at+n] for n in range(size))
        except KeyError:raise sampler.Unknown('fixture_unmapped')
    def validate(self):pass
def contract():
    return json.loads((source.WORK/'source-contract.json').read_bytes())
def make():
    c=contract();b=Memory();s=sampler.Sampler(b,c,{'base':BASE,'size':c['image_size']});s.bytes=0
    return b,s,c
def table(b,row):b.put(BASE+row['rva'],q(*(BASE+x for x in row['targets'])))
def pair(b,obj,ctrl):b.put(ctrl+8,struct.pack('<i',1));return q(obj,ctrl)

class Focused(unittest.TestCase):
    def test_original_NP_not_patched_FM_gate(self):
        c=contract();row=next(x for x in c['checks'] if x['rva']==0x9f99f0)
        self.assertEqual(row['instruction'],'cmp byte ptr [rbx + 0x498], 0')
        self.assertEqual(c['layout']['FileManager_available'],0x128)
    def test_cache_presence_is_not_activation(self):
        b,s,c=make();ui,head,node,bi,ctrl=0x100000,0x110000,0x120000,0x130000,0x140000
        b.put(ui+0x350,q(head,1));b.put(head,q(node,node));b.put(node,q(head,head))
        b.put(node+0x30,pair(b,bi,ctrl));b.put(bi,q(BASE+c['widgets']['BI']['rva']));table(b,c['widgets']['BI'])
        found=s.cache(ui);self.assertEqual(len(found['BI']),1)
        self.assertFalse(c['cache_presence_is_active_widget'])
        self.assertNotIn('actual_activation',found)
    def test_timer_ID_zero_unknown(self):
        _,s,_=make();row=s.task(0x100000,0,0x200000,0)
        self.assertEqual(row['status'],'UNKNOWN');self.assertNotIn('finished_derived',row)
    def test_registry_miss_unknown(self):
        b,s,_=make();scheduler,head=0x100000,0x110000
        b.put(scheduler+0x30,q(head,0));b.put(head,q(head,head))
        row=s.task(scheduler,12,0x200000,0)
        self.assertEqual(row['status'],'UNKNOWN');self.assertNotIn('remaining_f32',row)
    def timer_fixture(self,index,remaining):
        b,s,c=make();scheduler,head,node,obj,ctrl,closure,bi=(0x100000+i*0x10000 for i in range(7))
        b.put(scheduler+0x30,q(head,1));b.put(head,q(node,node));b.put(node,q(head,head,12))
        b.put(node+0x18,pair(b,obj,ctrl));b.put(obj,q(BASE+c['one_time_task']['rva']));table(b,c['one_time_task'])
        b.put(obj+0x80,q(closure));b.put(closure,q(BASE+c['closures'][index]['rva'],bi));table(b,c['closures'][index])
        b.put(obj+0xb0,struct.pack('<f',remaining))
        return b,s,c,scheduler,bi
    def test_both_closure_types_and_finished_derivation(self):
        for index in (0,1):
            b,s,c,scheduler,bi=self.timer_fixture(index,-0.01)
            row=s.task(scheduler,12,bi,index)
            self.assertEqual(row['status'],'OBSERVED');self.assertTrue(row['finished_derived'])
            self.assertFalse(row['callback_execution_proven'])
    def test_wrong_closure_mapping_refused(self):
        b,s,c,scheduler,bi=self.timer_fixture(0,1)
        with self.assertRaises(sampler.Unknown):s.task(scheduler,12,bi,1)
    def test_nonfinite_remaining_refused(self):
        b,s,c,scheduler,bi=self.timer_fixture(0,float('nan'))
        with self.assertRaises(sampler.Unknown):s.task(scheduler,12,bi,0)
    def test_sample_budget_refuses_further_read(self):
        b,s,c=make();s.bytes=c['bounds']['typed_byte_limit']
        with self.assertRaises(sampler.Unknown):s.read(0x100000,1)
        self.assertEqual(b.reads,[])
        self.assertEqual(s.bytes,c['bounds']['typed_byte_limit'])
    def scene_fixture(self):
        b,s,c=make();gs,intro,ctrl=0x100000,0x110000,0x120000
        original=q(intro,ctrl)+b'\0'*16+struct.pack('<I',1)
        b.put(gs+0x360,original);pair(b,intro,ctrl)
        row=next(x for x in c['scenes'] if x['kind']=='Intro');table(b,row)
        b.put(intro,q(BASE+row['rva'],0)+struct.pack('<I',1));b.put(intro+0x18,b'\1')
        return b,s,c,gs,original
    def test_scene_transition_invalidates_typed_scene(self):
        b,s,c,gs,original=self.scene_fixture();count=[0]
        def race(at,size):
            if at==gs+0x360:
                count[0]+=1
                if count[0]==2:b.put(at,b'\0'*36)
        b.hook=race
        with self.assertRaises(sampler.Unknown):s.scene(gs)
    def test_full_sample_scene_change_invalidates_other_fields(self):
        b,s,c,gs,original=self.scene_fixture()
        route=(0x200000,True,7,0x210000,0,0,(),{'GameState':[gs],'UI':[],'NP':[],'Scheduler':[]})
        s.route=lambda:route;s.code=lambda:{'status':'VALIDATED'}
        b.put(BASE+0x180a328,b'\1');count=[0]
        def race(at,size):
            if at==gs+0x360:
                count[0]+=1
                if count[0]==3:b.put(at,b'\0'*36)
        b.hook=race;row=s.sample()
        self.assertEqual(row['status'],'UNKNOWN')
        self.assertEqual(row['FM_available']['status'],'UNKNOWN')
        self.assertEqual(row['scene']['status'],'UNKNOWN')
    def test_optional_budget_keeps_scene_and_readiness(self):
        b,s,c,gs,original=self.scene_fixture();ui=0x300000
        route=(0x200000,True,7,0x210000,0,0,(),{'GameState':[gs],'UI':[ui],'NP':[],'Scheduler':[]})
        s.route=lambda:route;s.code=lambda:{'status':'VALIDATED'}
        b.put(BASE+0x180a328,b'\1');b.put(ui+0x318,b'\1');b.put(0x400000,b'\0'*4096)
        def large_optional(_):
            s.read(0x400000,4096);s.read(0x400000,4096)
            raise AssertionError('optional read should have refused')
        s.cache=large_optional;row=s.sample()
        self.assertEqual(row['status'],'OBSERVED')
        self.assertEqual(row['scene']['current']['kind'],'Intro')
        self.assertEqual(row['FM_available'],sampler.observed(True))
        self.assertEqual(row['UI_ready'],sampler.observed(True))
        self.assertEqual(row['widgets']['status'],'UNKNOWN')
        self.assertLessEqual(row['typed_bytes_requested'],8192)
    def test_polling_summary_does_not_claim_cause(self):
        summary=reader.summarize([{'scene':{'current':{'kind':'Intro'}}},{'scene':{'current':{'kind':'Lobby'}}}])
        self.assertEqual(summary['scene_sample_counts'],{'Intro':1,'Lobby':1})
        self.assertFalse(summary['event_exact_order_proven']);self.assertFalse(summary['timer_expiry_race_cause_proven'])
    def test_module_startup_error24_retries_same_backend(self):
        clock=[0.0];calls=[0];validations=[0]
        class Error(Exception):reason='module_query_denied';native_error=24
        class Backend:
            def validate(self):validations[0]+=1
            def modules(self):
                calls[0]+=1
                if calls[0]==1:raise Error()
                return {'LC':{'base':BASE,'size':65622016}}
        game,metadata=reader.modules_ready(Backend(),lambda:clock[0],lambda seconds:clock.__setitem__(0,clock[0]+seconds))
        self.assertEqual(metadata['retry_count'],1);self.assertEqual(metadata['delay_seconds'],0.1)
        self.assertEqual(calls[0],2);self.assertEqual(validations[0],2)
    def test_module_access_denied_is_not_retried(self):
        calls=[0]
        class Error(Exception):reason='module_query_denied';native_error=5
        class Backend:
            def validate(self):pass
            def modules(self):calls[0]+=1;raise Error()
        with self.assertRaises(Error) as caught:reader.modules_ready(Backend(),lambda:0,lambda _:self.fail('denied must not sleep'))
        self.assertEqual(calls[0],1);self.assertEqual(caught.exception.module_ready_metadata['retry_count'],0)

if __name__=='__main__':unittest.main()
