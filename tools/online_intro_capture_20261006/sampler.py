"""Bounded typed RPM polling; all object addresses remain ephemeral."""
import sys
sys.dont_write_bytecode = True
import math, struct, time

class Unknown(Exception):
    def __init__(self, reason): self.reason = reason
def need(ok, reason):
    if not ok: raise Unknown(reason)
def unknown(reason): return {'status':'UNKNOWN','reason':reason}
def observed(value): return {'status':'OBSERVED','value':value}

class Sampler:
    def __init__(self, backend, contract, game):
        self.b, self.c, self.g = backend, contract, game
        self.total = 0
        self.image_checks = [(x['rva'],bytes.fromhex(x['bytes_hex'])) for x in contract['checks']]

    def read(self, at, size, image=False):
        need(0 < size <= 4096, 'fixed_typed_read_size')
        need(self.bytes+size <= min(self.c['bounds']['typed_byte_limit'],getattr(self,'read_limit',8192)), 'sample_byte_budget')
        need(self.total+size <= self.c['bounds']['total_typed_byte_limit'], 'total_byte_budget')
        self.bytes += size; self.total += size
        return self.b.read(at,size,self.g['base'] if image else None)

    def u64(self, at): return struct.unpack('<Q',self.read(at,8))[0]
    def pointer(self, at, nullable=False):
        p = self.u64(at)
        need((nullable and p == 0) or (0x10000 <= p <= 0x7fffffffffff and p%8==0),'pointer_noncanonical')
        return p
    def boolean(self, at):
        first = self.read(at,1)
        need(first in (b'\0',b'\1'),'bool_noncanonical')
        need(self.read(at,1)==first,'bool_changed')
        return first==b'\1'
    def table(self, row):
        expected = struct.pack('<'+'Q'*len(row['targets']),*(self.g['base']+v for v in row['targets']))
        need(self.read(self.g['base']+row['rva'],len(expected),True)==expected,'public_vtable_changed')
    def type(self, obj, row):
        need(self.pointer(obj)==self.g['base']+row['rva'],'object_vtable_changed')
        self.table(row)
    def strong_pair(self, raw):
        obj,ctrl=struct.unpack('<QQ',raw)
        need(all(0x10000<=p<=0x7fffffffffff and p%8==0 for p in (obj,ctrl)), 'shared_pair_noncanonical')
        need(struct.unpack('<i',self.read(ctrl+8,4))[0]>0,'shared_owner_not_positive')
        return obj,ctrl

    def code(self):
        dormant=0
        for rva,expected in self.image_checks:
            try: need(self.read(self.g['base']+rva,len(expected),True)==expected,'original_live_CODE_mismatch')
            except Exception as error:
                d=getattr(error,'region',None) or {}
                permitted=(getattr(error,'reason',None)=='region_not_readable' and d.get('state')==0x1000
                    and d.get('type')==0x1000000 and d.get('image_allocation_matches') is True
                    and d.get('length_fits') is True and d.get('guard') is False and d.get('protection')==1)
                if not permitted: raise
                dormant+=1
        return {'status':'VALIDATED','dormant_CODE_anchors':dormant,
                'dormant_is_execution_evidence':False}

    def route(self):
        layout=self.c['layout'];root=self.pointer(self.g['base']+layout['Root_slot_rva'])
        ready=self.boolean(root+layout['Root_ready'])
        phase_raw=self.read(root+layout['Root_phase'],4);phase=struct.unpack('<I',phase_raw)[0]
        need(phase<=32,'phase_noncanonical')
        if not ready: return root,ready,phase,None,0,0,(),{}
        gi=self.pointer(root+layout['GI_pointer']);header=self.read(gi+layout['GI_begin'],16)
        begin,end=struct.unpack('<QQ',header)
        need((begin==end==0) or (0x10000<=begin<=end<=0x7fffffffffff and (begin|end)%8==0
             and (end-begin)%16==0 and (end-begin)//16<=128),'GI_vector_bounds')
        objects={role:[] for role in self.c['tables']};rows=[]
        for at in range(begin,end,16):
            pair=self.read(at,16);obj,ctrl=self.strong_pair(pair);vp=self.pointer(obj)
            rows.append((pair,vp))
            for role,tables in self.c['tables'].items():
                row=next((t for t in tables if vp==self.g['base']+t['rva']),None)
                if row is not None:
                    self.table(row);objects[role].append(obj)
        need(self.read(gi+layout['GI_begin'],16)==header,'GI_header_changed')
        return root,ready,phase,gi,begin,end,tuple(rows),objects

    def scene(self,obj):
        raw=self.read(obj+0x360,36);state=struct.unpack_from('<I',raw,32)[0]
        result={};current=None
        for label,pair in (('current',raw[:16]),('pending',raw[16:32])):
            if pair==b'\0'*16: result[label]={'kind':'none','state_id':None};continue
            owner,_=self.strong_pair(pair);content=self.read(owner,20);vp,render,number=struct.unpack('<QQI',content)
            row=next((r for r in self.c['scenes'] if vp==self.g['base']+r['rva']),None)
            need(row is not None and row['state_id']==number,'scene_type_enum_disagree')
            self.table(row);need(self.read(owner,20)==content,'scene_owner_changed')
            result[label]={'kind':row['kind'],'state_id':number}
            if label=='current': current=owner
        need((result['current']['kind']=='none' and state==0) or result['current']['state_id']==state,'current_enum_disagree')
        if result['current']['kind']=='Intro': result['Intro_first_entry_done']=observed(self.boolean(current+0x18))
        need(self.read(obj+0x360,36)==raw,'scene_pair_transition')
        result.update(status='OBSERVED',visible_screen_claimed=False)
        return result,raw

    def unique(self,objects,role):
        members=objects.get(role,[])
        need(len(members)==1, 'concrete_'+role+'_absent_or_duplicate')
        return members[0]

    def cache(self,ui):
        # Public type match only. No UI labels/strings or arbitrary DTO read.
        header=self.read(ui+0x350,16);head,count=struct.unpack('<QQ',header)
        need(0x10000<=head<=0x7fffffffffff and head%8==0 and count<=64,'UI_cache_bounds')
        sentinel=self.read(head,16);node=struct.unpack_from('<Q',sentinel)[0]
        found={k:[] for k in ('CI','BI')};checked=[];seen=set()
        for _ in range(count):
            need(node!=head and node not in seen and 0x10000<=node<=0x7fffffffffff and node%8==0,'UI_cache_cycle_or_short')
            seen.add(node);next_raw=self.read(node,8);pair=self.read(node+0x30,16)
            obj,_=self.strong_pair(pair);vp=self.pointer(obj)
            for kind,row in self.c['widgets'].items():
                if vp==self.g['base']+row['rva']:
                    self.table(row);found[kind].append((node,pair,obj))
            checked.append((node,next_raw,pair));node=struct.unpack('<Q',next_raw)[0]
        need(node==head,'UI_cache_count_mismatch')
        need(self.read(ui+0x350,16)==header and self.read(head,16)==sentinel,'UI_cache_header_changed')
        for node,link,pair in checked:
            need(self.read(node,8)==link and self.read(node+0x30,16)==pair,'UI_cache_owner_changed')
        return found

    def task(self,scheduler,task_id,widget,index):
        if task_id==0: return unknown('timer_ID_zero_not_execution_proof')
        header=self.read(scheduler+0x30,16);head,count=struct.unpack('<QQ',header)
        need(0x10000<=head<=0x7fffffffffff and head%8==0 and count<=64,'Scheduler_registry_bounds')
        sentinel=self.read(head,16);node=struct.unpack_from('<Q',sentinel)[0];found=[];seen=set()
        for _ in range(count):
            need(node!=head and node not in seen and 0x10000<=node<=0x7fffffffffff and node%8==0,'Scheduler_registry_cycle_or_short')
            seen.add(node);link=self.read(node,8);key=self.u64(node+0x10)
            if key==task_id: found.append((node,self.read(node+0x18,16)))
            node=struct.unpack('<Q',link)[0]
        need(node==head,'Scheduler_registry_count_mismatch')
        need(self.read(scheduler+0x30,16)==header and self.read(head,16)==sentinel,'Scheduler_registry_changed')
        if not found: return unknown('timer_not_in_registry_no_callback_history')
        need(len(found)==1,'duplicate_timer_ID')
        node,pair=found[0];obj,ctrl=self.strong_pair(pair);self.type(obj,self.c['one_time_task'])
        closure=self.pointer(obj+0x80);self.type(closure,self.c['closures'][index])
        need(self.pointer(closure+8)==widget,'timer_callback_widget_mismatch')
        raw=self.read(obj+0xb0,4);remaining=struct.unpack('<f',raw)[0]
        need(math.isfinite(remaining),'remaining_nonfinite')
        need(self.read(node+0x18,16)==pair and self.u64(node+0x10)==task_id
             and self.pointer(obj+0x80)==closure and self.pointer(closure+8)==widget
             and self.read(obj+0xb0,4)==raw,'timer_changed_during_read')
        need(struct.unpack('<i',self.read(ctrl+8,4))[0]>0,'timer_owner_changed')
        return dict(status='OBSERVED',remaining_f32=remaining,finished_derived=remaining<=0,
                    callback_execution_proven=False,widget_matches_original_closure=True)

    def sample(self):
        started=time.perf_counter();self.bytes=0;self.read_limit=self.c['bounds']['typed_byte_limit']
        row=dict(schema='lc-online-intro-capture-sample-v1',status='UNKNOWN',
                 scene=unknown('not_observed'),Root_ready=unknown('not_observed'),
                 Root_stage=unknown('not_observed'),FM_available=unknown('not_observed'),
                 UI_ready=unknown('not_observed'),NP_ready=unknown('not_observed'),
                 widgets=unknown('not_observed'),snapshot_atomic=False,raw_pointer_saved=False)
        try:
            self.b.validate();row['CODE']=self.code();route_start_bytes=self.bytes
            route=self.route();route_cost=self.bytes-route_start_bytes
            root,ready,phase,gi,begin,end,owners,objects=route
            # Scene precedes optional widgets and timer observations.
            gs=self.unique(objects,'GameState');scene,scene_raw=self.scene(gs);row['scene']=scene
            row['Root_ready']=observed(ready);row['Root_stage']=observed(phase)
            row['FM_available']=observed(self.boolean(self.g['base']+0x180a328))
            for field,role,offset in (('UI_ready','UI',0x318),('NP_ready','NP',0x498)):
                try: row[field]=observed(self.boolean(self.unique(objects,role)+offset))
                except Exception as error: row[field]=unknown(getattr(error,'reason','typed_read_failed'))
            try:
                # Reserve the measured exact same route cost and scene-pair
                # re-read. Refused optional reads consume none of that budget.
                self.read_limit=self.c['bounds']['typed_byte_limit']-route_cost-128
                ui=self.unique(objects,'UI');found=self.cache(ui);widgets={}
                for kind,entries in found.items():
                    item=dict(cache_presence=observed(bool(entries)),actual_activation=unknown('cache_presence_is_not_active_widget'),
                              cache_matching_count=len(entries))
                    if kind=='BI' and len(entries)==1:
                        node,pair,bi=entries[0];item['FA']=observed(self.boolean(bi+0xfa));item['F9']=observed(self.boolean(bi+0xf9));timers=[]
                        for index,offset in enumerate((0xb8,0x100)):
                            handle=self.read(bi+offset,9);task_id=struct.unpack_from('<Q',handle)[0];flag=handle[8]
                            timer={'ID':task_id,'stored_active':observed(bool(flag)) if flag in (0,1) else unknown('handle_active_noncanonical')}
                            try: timer['task']=self.task(self.unique(objects,'Scheduler'),task_id,bi,index)
                            except Exception as error: timer['task']=unknown(getattr(error,'reason','typed_read_failed'))
                            need(self.read(bi+offset,9)==handle,'BI_timer_handle_changed');timers.append(timer)
                        item['timers']=timers
                        need(self.read(node+0x30,16)==pair,'BI_cache_pair_changed');self.type(bi,self.c['widgets']['BI'])
                    widgets[kind]=item
                row['widgets']={'status':'OBSERVED','types':widgets}
            except Exception as error: row['widgets']=unknown(getattr(error,'reason','typed_read_failed'))
            finally:self.read_limit=self.c['bounds']['typed_byte_limit']
            need(self.read(gs+0x360,36)==scene_raw,'scene_changed_after_optional_read')
            # Re-read Root/GI/types; stale/torn ownership invalidates this sample.
            need(self.route()==route,'Root_GI_owner_changed')
            self.b.validate();row['status']='OBSERVED'
        except Exception as error:
            reason=getattr(error,'reason','typed_sampler_error')
            for field in ('scene','Root_ready','Root_stage','FM_available','UI_ready','NP_ready','widgets'): row[field]=unknown(reason)
            row['reason']=reason
        row['typed_bytes_requested']=self.bytes
        row['observer_duration_seconds']=round(time.perf_counter()-started,6)
        return row
