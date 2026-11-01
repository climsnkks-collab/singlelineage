"""Private source-owned post-Get three-lookup UID observation only.

No NPC registration, actor removal, memory-free/render or client ACK claim.
Every encountered owning-vector entry must expose the original pure 40C00
UID interface; unsupported entries make the entire observation UNKNOWN.
"""
import asyncio
import struct
from time import monotonic_ns
from types import MethodType

from tools.local_original_session import inventory,edge,npc_observe,observe,item_custody,item_transfer_session,item_ground
from tools.local_original_session.broker import PersistentBroker

BYTE_LIMIT=16384
MIN_INTERVAL_NS=inventory.MIN_INTERVAL_NS
need=inventory.need
_CURRENT=inventory.InventoryService._current
_SAME=inventory.InventoryService._same
_CONTEXT=item_transfer_session.ItemTransferSession.context_locked
_TRANSFER_SAME=item_transfer_session.ItemTransferSession._same
_GENERATION=PersistentBroker.inventory_selection_current
_LOOKUP=npc_observe._registry_lookup_source
_BUDGET=npc_observe._ObservationBudget

def _pins():
 # Python source hash pins were removed; the registry lookup source check stays.
 _LOOKUP()

def _original(owner,name,function):
 method=getattr(owner,name,None)
 need(type(method) is MethodType and method.__self__ is owner and method.__func__ is function,
      'GROUND_RETIREMENT_ORIGINAL_METHOD_REQUIRED')

class GroundRetirementObserver:
 def __init__(self,broker,reader):
  _pins()
  need(type(self) is GroundRetirementObserver and type(broker) is PersistentBroker and type(reader) is observe.RetainedSceneReader,
       'GROUND_RETIREMENT_ACTUAL_BROKER_READER_REQUIRED')
  self.broker=broker;self.reader=reader
  self._authority=inventory.InventoryService(broker,reader,policy=inventory.POLICY)
  self._last_ns=None;self.last_sample_monotonic_ns=None
  self._closed=False;self._inflight=False
  self._methods=_METHODS
  self.last_result=None

 def _context(self,writer,row):
  need(type(self) is GroundRetirementObserver and self._methods is _METHODS
       and not self._closed and self._authority.broker is self.broker and self._authority.reader is self.reader,
       'GROUND_RETIREMENT_LIFETIME_CHANGED')
  _original(self,'_context',self._methods[0]);_original(self,'sample_returned',self._methods[2]);_original(self,'close',self._methods[3])
  need(type(self)._same is self._methods[1] and self._same is self._methods[1],
       'GROUND_RETIREMENT_ORIGINAL_COMPARE_REQUIRED')
  _original(self._authority,'_current',_CURRENT)
  authority=_CURRENT(self._authority,writer,row)
  _original(self.broker,'inventory_selection_current',_GENERATION)
  g=_GENERATION(self.broker,writer);session=None if g is None else g.transfer_session
  need(type(session) is item_transfer_session.ItemTransferSession,
       'GROUND_RETIREMENT_CURRENT_TRANSFER_REQUIRED')
  _original(session,'context_locked',_CONTEXT)
  context=_CONTEXT(session,writer)
  registry=self.broker._item_ground_registry
  need(context.generation is g and g.writer is writer and g.row is row
       and session.phase=='RETURNED' and not session.closed and session.pending is None
       and context.snapshot.phase=='RETURNED' and context.snapshot.owner=='PLAYER'
       and context.snapshot is session._committed and context.membership is session.membership
       and context.membership.phase=='DRAINED' and context.current_frame is g.current_frame
       and context.current_frame==context.snapshot.frame_ab
       and type(registry) is item_ground.GroundRegistry and registry.broker is self.broker
       and registry._generation is g and registry._registration is None and registry._pending is None
       and registry._terminal is True and registry._index==2 and registry._attempted is False
       and registry._ground_attempted is True and registry._ground_drained is True
       and registry._snapshot is context.snapshot and registry._frame is context.current_frame,
       'GROUND_RETIREMENT_ACTUAL_RETURNED_DRAIN_REQUIRED')
  _,b=item_custody._members(context.snapshot.frame_ab)
  need(0<b.identifier<1<<32 and b.identifier!=context.position.uid,
       'GROUND_RETIREMENT_LOCAL_B_UID_REQUIRED')
  refs=(self.broker,self.reader,self._authority,g,session,registry,registry._epoch,
        registry._snapshot,registry._frame,registry._member)
  values=(registry._terminal,registry._index,registry._attempted,registry._ground_attempted,
          registry._ground_drained,b.identifier,dict(b.raw_fields)[4])
  return authority,context,refs,values

 @staticmethod
 def _same(before,after):
  _SAME(before[0],after[0]);_TRANSFER_SAME(before[1],after[1])
  need(len(before[2])==len(after[2])==10 and all(a is b for a,b in zip(before[2],after[2]))
       and before[3]==after[3], 'GROUND_RETIREMENT_CURRENT_CONTEXT_CHANGED')

 def close(self):
  self._closed=True
  self._authority.close() # Private helper only. Reader/broker/registry stay owned by caller.

 async def sample_returned(self,writer,*,now_ns):
  result=dict(status='UNKNOWN',reason='NOT_SAMPLED',uid=None,map_id=None,uid_absent=None,
      vector_counts=None,lookup_scope='THREE_LOOKUP_VECTORS',
      proof_scope='FRESH_POST_GET_LOOKUP_UID_SNAPSHOT_ONLY',snapshot_atomic=False,
      memory_freed='UNKNOWN',render='UNKNOWN',causal_removal='UNKNOWN',all_references_retired='UNKNOWN',
      source_contract_valid=False,stable_double_read=False,query_started_monotonic_ns=None,
      typed_bytes_requested=0,typed_byte_limit=BYTE_LIMIT,max_samples_per_second=2)
  entered=False;budget=None
  methods=_METHODS
  try:
   need(not self._closed and not self._inflight,'GROUND_RETIREMENT_CLOSED_OR_INFLIGHT')
   need(type(now_ns) is int and 0<=now_ns<1<<63,
        'GROUND_RETIREMENT_CURRENT_TIME_REQUIRED')
   need(self._last_ns is None or now_ns-self._last_ns>=MIN_INTERVAL_NS,'GROUND_RETIREMENT_CADENCE')
   self._last_ns=now_ns;self._inflight=True;entered=True
   _pins()
   rows=[r for group in self.broker._claims.values() for r in group if r['writer'] is writer]
   need(len(rows)==1,'GROUND_RETIREMENT_CURRENT_CLAIM_REQUIRED');row,=rows
   lock=row['operation_lock']
   async with lock:
    need(row['operation_lock'] is lock,'GROUND_RETIREMENT_ROW_LOCK_CHANGED')
    before=methods[0](self,writer,row)
    for _ in range(2):
     need(await self.broker._movement_owner(writer,row,before[1].position) is True,
          'GROUND_RETIREMENT_NATIVE_OWNER_REQUIRED')
     methods[1](before,methods[0](self,writer,row))
    self._authority._cancelled()
    proof=self._authority.proof
    need(proof.reader is self.reader,'GROUND_RETIREMENT_SAME_READER_REQUIRED')
    native,sampler=proof._binding()
    retained=(self.reader.owner,self.reader.member,self.reader.backend,self.reader.sampler,native.handle)
    contract,_,checks=inventory._source()
    self._authority._checks(sampler,contract,checks)
    _LOOKUP()
    code=proof.lookup_contract['code_checks']
    need(proof.lookup_contract['getter_rva']==0x40c00,'GROUND_RETIREMENT_PURE_UID_SOURCE_REQUIRED')
    budget=_BUDGET(native,sampler)
    query=monotonic_ns()
    need(type(query) is int and now_ns<=query<1<<63,'GROUND_RETIREMENT_CURRENT_TIME_REQUIRED')
    need(self.last_sample_monotonic_ns is None or query-self.last_sample_monotonic_ns>=MIN_INTERVAL_NS,
         'GROUND_RETIREMENT_QUERY_CADENCE')
    self.last_sample_monotonic_ns=query;result['query_started_monotonic_ns']=query
    with budget.installed():
     proof._code(sampler,budget,code)
     position=before[1].position
     reads,actors,_,route,state,scene,_=edge._world(native,sampler,proof.public,proof.world,
         proof.position_source,position.uid,position.map_id,(position.word0,position.word1),require_current_start=False)
     counts=[];matches=0;target_uid=before[3][5]
     for offset in (0x8a8,0x8c0,0x8d8):
      begin,count=proof.world.vector(reads,actors,offset,offset+8,proof.public['Player']['max_actor_elements'])
      counts.append(count)
      for index in range(count):
       obj=reads.pair(reads.read(begin+index*16,16))[0];vp=reads.pointer(obj)
       base,size=sampler.g['base'],sampler.g['size']
       need(base<=vp<=base+size-16,'GROUND_RETIREMENT_UID_TABLE_IMAGE_BOUNDS')
       getter=struct.unpack('<Q',sampler.read(vp+8,8,image=True))[0]
       need(getter==base+0x40c00,'GROUND_RETIREMENT_UID_GETTER_UNSUPPORTED')
       uid=struct.unpack('<Q',reads.read(obj+0x18,8))[0]
       matches+=uid==target_uid
     budget.verify()
     budget._require_unchanged(not budget.instability_origins,None,None,'registry_strict_count_gate')
     budget.retain=False
     try:need(sampler.read(state+0x360,36)==scene and sampler.route()==route,'GROUND_RETIREMENT_WORLD_OWNER_CHANGED')
     finally:budget.retain=True
     proof._code(sampler,budget,code)
    need(self._authority.proof is proof and proof.reader is self.reader
         and proof._binding()==(native,sampler)
         and all(a is b for a,b in zip(retained[:4],(self.reader.owner,self.reader.member,self.reader.backend,self.reader.sampler)))
         and native.handle==retained[4], 'GROUND_RETIREMENT_RETAINED_CHANGED')
    methods[1](before,methods[0](self,writer,row))
    self._authority._checks(sampler,contract,checks);_pins();self._authority._cancelled()
    finished=monotonic_ns()
    need(type(finished) is int and query<=finished<1<<63 and budget.spent<=BYTE_LIMIT,
         'GROUND_RETIREMENT_MONOTONIC_OR_BUDGET')
    need(matches<=1,'GROUND_RETIREMENT_DUPLICATE_UID')
    result.update(status='OBSERVED',reason=None,uid=target_uid,map_id=position.map_id,
        uid_absent=matches==0,vector_counts=counts,source_contract_valid=True,stable_double_read=True)
  except asyncio.CancelledError:
   result['reason']='GROUND_RETIREMENT_CALLER_CANCELLED';self.close();raise
  except Exception as error:result['reason']=observe.reason(error)
  finally:
   if entered:self._inflight=False
   result['typed_bytes_requested']=0 if budget is None else budget.spent
   self.last_result=result
  return result

_METHODS=(GroundRetirementObserver._context,GroundRetirementObserver._same,
          GroundRetirementObserver.sample_returned,GroundRetirementObserver.close)
