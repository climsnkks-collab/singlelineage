"""Passive same-edge static source step contact, never original attack LOS.

M1/M40 are raw source predicate masks. No meaning for arrow/door is assigned.
The original 1/4000 helper whitelist and original queue mutator stay untouched.
"""
from dataclasses import dataclass, field
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import struct
import time

from tools.local_original_session import attack, edge, movement, npc_observe, observe

need=attack.need
PREDICATE_SCOPE='STATIC_SOURCE_STEP_CONTINUE'
ORIGINAL_ARROW_DOOR='UNKNOWN'
LIMIT=edge.LIMIT  # Reuse original exact-edge 40960B query; separate from pose16K.
SOURCE_ROOT='work/local_server_rea_20261016/run99_npc_adjacent_attack_los/'
SOURCE_PINS={
    SOURCE_ROOT+'implementation-conditions.md':'b99363fc6ebcf846f721340268aaf588e168b51a3848d2e9431ee820ee6799f7',
    SOURCE_ROOT+'findings.md':'6e417a4703b76ca33922032470d618088d7b72c7314e0e6fc685073c51f65b98',
    SOURCE_ROOT+'source-evidence.json':'46dc641d505eff35ce918ba9c88ea2d1e20fc614d4ed3ddd337cf9c160dfe0f1',
    SOURCE_ROOT+'main-review.json':'d9017e189a8f9b2ce3c8b437fde384d8f074f0a873829dcdb28f2d601bac3d4e',
}
_COLD_SOURCE='work/local_server_rea_20261016/daybreak_page_noaccess_handoff/designated-01a14ed2/contact-current-binding-239/contact-cold-code.json'
_COLD_SHA='20905ac41c0eabe219f172b475bb08f7d6175ebf48aa35eeb665d3f24b68cd06'
_UNION_SOURCE='work/local_original_session/implementation-2/npc-motion-goal/approach-player-hit/core/contact-source-union.json'
_UNION_SHA='80544c14f0e81d3faa839f988999877af4d80bb41ebdbbc79414e220833b1aec'
_PHYSICAL_SHA='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684'
_CARRIER_SHA='c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9'


def _cold_code_source(checks,reader,sampler):
    """Exact finite source bytes for unreadable CODE only, with current owner."""
    image=observe.ROOT/'work/standalone_boot/current-unmodified-clone/LC.guard.exe'
    need(reader.image==image and reader.owner is not None
         and reader.owner.image==image and reader.owner.child is reader.member
         and reader.owner.image_sha==_PHYSICAL_SHA
         and reader.backend.contract['original_program']==str(image)
         and Path(reader.member.identity.get('image',''))==image
         and reader.backend.expected==dict(pid=reader.member.pid,birth=reader.member.identity['birth'])
         and sampler.g['size']==reader.backend.contract['image_size'],
         'NPC_CONTACT_COLD_IMAGE_IDENTITY')
    union=observe.ordinary(observe.ROOT/_UNION_SOURCE).read_bytes()
    need(hashlib.sha256(union).hexdigest()==_UNION_SHA,'NPC_CONTACT_UNION_CHANGED')
    raw=observe.ordinary(observe.ROOT/_COLD_SOURCE).read_bytes()
    need(0<len(raw)<=500000 and hashlib.sha256(raw).hexdigest()==_COLD_SHA,
         'NPC_CONTACT_COLD_SOURCE_CHANGED')
    document=json.loads(raw)
    need(type(document) is dict and set(document)=={
        'schema','physical_image_sha256','derived_carrier_sha256','source_union_sha256','checks'}
        and document['schema']=='contact-cold-code-source-v1'
        and document['physical_image_sha256']==_PHYSICAL_SHA
        and document['derived_carrier_sha256']==_CARRIER_SHA
        and document['source_union_sha256']==_UNION_SHA
        and type(document['checks']) is list and len(document['checks'])==len(checks)==2965
        and sum(c['length'] for c in checks)==11427,
        'NPC_CONTACT_COLD_SOURCE_CONTRACT')
    accepted={}
    for actual,expected in zip(document['checks'],checks):
        need(type(actual) is dict and set(actual)=={'rva','length','sha256','bytes_hex'}
             and type(actual['rva']) is int and type(actual['length']) is int
             and type(actual['sha256']) is str and type(actual['bytes_hex']) is str
             and (actual['rva'],actual['length'],actual['sha256'])==
                 (expected['rva'],expected['length'],expected['sha256']),
             'NPC_CONTACT_COLD_CHECK_CHANGED')
        span=bytes.fromhex(actual['bytes_hex'])
        need(len(span)==expected['length'] and hashlib.sha256(span).hexdigest()==expected['sha256'],
             'NPC_CONTACT_COLD_BYTES_CHANGED')
        key=(sampler.g['base']+expected['rva'],expected['length'],True)
        need(key not in accepted or accepted[key]==span,'NPC_CONTACT_COLD_DUPLICATE_CONFLICT')
        accepted[key]=span
    return accepted


class _ContactBudget(edge._Budget):
    def __init__(self,native,sampler):
        super().__init__(native,sampler)
        self._cold_allowed=None
        self._cold_used=set()
        self._first_code_failure=None

    @contextmanager
    def cold_code(self,accepted):
        need(self._cold_allowed is None and type(accepted) is dict,'NPC_CONTACT_COLD_SCOPE')
        self._cold_allowed=accepted
        try:yield
        finally:self._cold_allowed=None

    def read(self,at,size,image=False):
        key=(at,size,image)
        try:return super().read(at,size,image)
        except Exception as error:
            if self._cold_allowed is None or self.retain or not image or key not in self._cold_allowed:
                raise
            region=getattr(error,'region',None)
            if self._first_code_failure is None:
                self._first_code_failure=dict(rva=at-self.sampler.g['base'],length=size,
                    reason=observe.reason(error),state=region.get('state') if type(region) is dict else None,
                    protection=region.get('protection') if type(region) is dict else None)
            if (observe.reason(error)!='region_not_readable' or type(region) is not dict or
                type(region.get('state')) is not int or region['state']!=0x1000 or
                type(region.get('type')) is not int or region['type']!=0x1000000 or
                type(region.get('protection')) is not int or region['protection']!=1 or
                region.get('guard') is not False or region.get('length_fits') is not True or
                region.get('image_allocation_matches') is not True or
                type(region.get('requested_bytes')) is not int or region['requested_bytes']!=size):
                raise
            raw=self._cold_allowed[key]
            need(type(raw) is bytes and len(raw)==size,'NPC_CONTACT_COLD_BYTES')
            self._cold_used.add(key)
            return raw

    def first_cold_code_rva(self):
        return self._first_code_failure['rva'] if self._cold_used else None


def source_ready():
    for relative,expected in SOURCE_PINS.items():
        raw=observe.ordinary(observe.ROOT/relative).read_bytes()
        need(0<len(raw)<=1048576 and hashlib.sha256(raw).hexdigest()==expected,
             'NPC_CONTACT_SOURCE_CHANGED')


def mask40(direction, flags):
    """Narrow source mask40 combination; do not broaden tile.flag_blocked."""
    need(type(direction) is int and 0<=direction<8 and len(flags)==(4 if direction%2 else 1)
         and all(type(v) is int and 0<=v<=65535 for v in flags),'NPC_CONTACT_MASK40_INPUT')
    values=[bool(v&0x40) for v in flags]
    if not direction%2: return values[0]
    a,b,c,d=values
    return (a or c) and (b or d) if direction in (3,7) else (a or b) and (c or d)


@dataclass(frozen=True,slots=True)
class Contact:
    _adapter: object=field(repr=False)
    _plan: object=field(repr=False)
    _writer: object=field(repr=False)
    _arrival: object=field(repr=False)
    _reader_refs: tuple=field(repr=False)
    flags: tuple
    m1: bool
    m40: bool|None
    admitted: bool
    now_ns: int
    typed_bytes: int
    source_bytes: int
    sample_monotonic_ns: int
    completed_monotonic_ns: int
    code_validation_scope: str
    live_code_bytes_verified: bool
    cold_code_anchor_count: int
    first_cold_code_rva: int|None

    def metadata(self):
        return dict(status='OBSERVED_STATIC_CONTINUE' if self.admitted else 'BLOCKED_STATIC_STEP',
            reason=None,predicate_scope=PREDICATE_SCOPE,original_arrow_door=ORIGINAL_ARROW_DOOR,
            flags_u16=list(self.flags),m1=self.m1,m40=self.m40,m40_evaluated=self.m1,
            sampled_ns=self.now_ns,typed_bytes_requested=self.typed_bytes,byte_limit=LIMIT,
            source_check_bytes_requested=self.source_bytes,
            sample_monotonic_ns=self.sample_monotonic_ns,
            completed_monotonic_ns=self.completed_monotonic_ns,
            freshness_budget_ns=npc_observe.MIN_INTERVAL_NS,
            freshness_basis='IMMUTABLE_QUERY_VALIDATION_COMPLETED',
            first_write_attempt_monotonic_ns=self._plan.contact_consumed_monotonic_ns,
            query_role=self._plan.contact_query_role,
            code_validation_scope=self.code_validation_scope,
            live_code_bytes_verified=self.live_code_bytes_verified,
            cold_code_anchor_count=self.cold_code_anchor_count,
            first_cold_code_rva=self.first_cold_code_rva,
            admission_consumed=self._plan.contact_consumed_by is not None,
            stable_double_read=True,snapshot_atomic=False,owning_lease=False,aba_excluded=False,
            temporal_scope='BOUNDED_PASSIVE_STATIC_OBSERVATION',terrain_after_await='UNKNOWN')

    def require_current_locked(self,writer):
        self._plan._check(writer,arrived=True)
        return self._require_binding_locked(writer)

    def _require_binding_locked(self,writer):
        # Arrival has just checked the complete domain projection with no await.
        plan,adapter=self._plan,self._adapter
        need(plan.contact is self and plan.arrival is self._arrival and self._writer is writer
             and self.admitted is True,'NPC_CONTACT_CURRENT_ADMITTED_RECEIPT_REQUIRED')
        if plan.contact_consumed_by is None:
            age=time.monotonic_ns()-self.completed_monotonic_ns
            if not 0<=age<=npc_observe.MIN_INTERVAL_NS:
                plan.phase=plan.arrival.phase='FAILED'
                raise ValueError('NPC_CONTACT_FIRST_ATTACK_FRESHNESS_EXPIRED')
        source_ready()
        reader=adapter.proof.reader
        native,sampler=adapter.proof._binding()
        if self.cold_code_anchor_count:
            need(reader.owner is not None and reader.owner.image_sha==_PHYSICAL_SHA
                 and hashlib.sha256(observe.ordinary(observe.ROOT/_COLD_SOURCE).read_bytes()).hexdigest()==_COLD_SHA,
                 'NPC_CONTACT_COLD_SOURCE_CHANGED')
        refs=(reader,reader.owner,reader.member,native,sampler)
        need(len(refs)==len(self._reader_refs) and all(a is b for a,b in zip(refs,self._reader_refs)),
             'NPC_CONTACT_RETAINED_READER_CHANGED')
        return plan.row

    def consume_attack_locked(self,writer,context,operation):
        self._require_binding_locked(writer)
        need(context._approach is self._arrival and operation.context is context
             and self._plan.contact_query_role=='JIT_FIRST_ATTACK_ATTEMPT'
             and self._plan.contact_consumed_by is None,'NPC_CONTACT_ATTACK_ONCE_REQUIRED')
        # Recheck actual time at final consumption, after reader/source guards.
        now=time.monotonic_ns()
        if not 0<=now-self.completed_monotonic_ns<=npc_observe.MIN_INTERVAL_NS:
            self._plan.phase=self._plan.arrival.phase='FAILED'
            raise ValueError('NPC_CONTACT_FIRST_ATTACK_FRESHNESS_EXPIRED')
        self._plan.contact_consumed_by=operation
        self._plan.contact_consumed_monotonic_ns=now


class ContactAdapter:
    def __init__(self,plan):
        self.plan=plan
        # Reuse this exact session's already prepared retained edge proof.
        self.proof=plan.session.factory.adapter._proof
        self.last_result=dict(status='UNKNOWN',reason='NOT_SAMPLED',predicate_scope=PREDICATE_SCOPE,
            original_arrow_door=ORIGINAL_ARROW_DOOR,terrain_after_await='UNKNOWN',typed_bytes_requested=0,
            code_validation_scope='UNKNOWN',live_code_bytes_verified=False,
            cold_code_anchor_count=0,first_cold_code_rva=None,first_code_failure=None)
        self._budget=None

    def sample_locked(self,writer,*,now_ns):
        sample_monotonic_ns=time.monotonic_ns()
        try:
            contact=self._sample_locked(writer,now_ns=now_ns,sample_monotonic_ns=sample_monotonic_ns)
            self.last_result=contact.metadata()
            return contact
        except BaseException as error:
            self.last_result.update(reason=observe.reason(error),
                typed_bytes_requested=0 if self._budget is None else self._budget.spent)
            if self._budget is not None:
                self.last_result['first_code_failure']=self._budget._first_code_failure
            raise

    def _sample_locked(self,writer,*,now_ns,sample_monotonic_ns):
        source_ready()
        plan,proof=self.plan,self.proof
        plan._check(writer,arrived=True)
        need(type(now_ns) is int and 0<=now_ns<(1<<63),'NPC_CONTACT_CLOCK_REQUIRED')
        reader=proof.reader
        native,sampler=proof._binding()
        retained=(reader,reader.owner,reader.member,native,sampler)
        state=plan.mover.state
        grid=tuple(movement.authority.unpack_grid(state.packed))
        player=(plan.position.word0,plan.position.word1)
        direction=plan.arrival.direction
        edge._request(proof.tile,state.uid,state.map_id,state.packed,direction,
                      movement.authority.pack_grid(*player))
        need(proof.public['Map']['table']['rva']==0x11c7df0
             and proof.public['Map']['context_pointer']==0x6e0,'NPC_CONTACT_TYPED_MAP_SOURCE_REQUIRED')
        budget=_ContactBudget(native,sampler)
        self._budget=budget
        monster,common,inherited=npc_observe._source()
        checks=proof.checks+inherited+proof.public['Position']['source_checks']+proof.lookup_contract['code_checks']
        checks=list({(c['rva'],c['length'],c['sha256']):c for c in checks}.values())
        cold=_cold_code_source(checks,reader,sampler)
        with budget.installed():
            with budget.cold_code(cold):proof._code(sampler,budget,checks)
            for table in proof.tables:
                raw=sampler.read(sampler.g['base']+table['rva'],table['length'],image=True)
                need(hashlib.sha256(raw).hexdigest()==table['sha256'],'NPC_CONTACT_DIRECTION_TABLE_CHANGED')
            reads,actors,context,route,world_state,scene_raw,_=edge._world(
                native,sampler,proof.public,proof.world,proof.position_source,
                plan.position.uid,state.map_id,player)
            _,observed=npc_observe._resolve_monster(reads,sampler,proof,monster,common,actors,state.uid)
            need(observed==list(grid),'NPC_CONTACT_CURRENT_NPC_POSE_REQUIRED')
            flags,resources=[],{}
            for segment,local in proof.tile.probe_cells(grid,direction):
                if segment not in resources:
                    resources[segment]=proof.tile.lookup_resource(reads,context,(segment[0]<<16)|segment[1])
                cell,_,_=proof.tile.cell(reads,resources[segment],local)
                flags.append(struct.unpack_from('<H',cell,4)[0])
            m1=proof.tile.flag_blocked(direction,flags,1)
            m40=mask40(direction,flags) if m1 else None
            admitted=not m1 or m40
            budget.verify()
            budget.retain=False
            try:
                need(sampler.read(world_state+0x360,36)==scene_raw and sampler.route()==route,
                     'NPC_CONTACT_WORLD_CHANGED')
            finally: budget.retain=True
            with budget.cold_code(cold):proof._code(sampler,budget,checks)
            plan._check(writer,arrived=True)
        need(all(a is b for a,b in zip(retained,
            (reader,reader.owner,reader.member,*proof._binding()))),'NPC_CONTACT_RETAINED_READER_CHANGED')
        need(_cold_code_source(checks,reader,sampler)==cold,'NPC_CONTACT_COLD_SOURCE_CHANGED')
        cold_count=len(budget._cold_used)
        return Contact(self,plan,writer,plan.arrival,retained,tuple(flags),m1,m40,
                       admitted,now_ns,budget.spent,
                       2*sum(c['length'] for c in checks)+sum(t['length'] for t in proof.tables),
               sample_monotonic_ns,time.monotonic_ns(),
               'PINNED_COLD_CODE_WITH_CURRENT_IMAGE_VQ' if cold_count else 'LIVE_CODE_HASHES',
               not cold_count,cold_count,
               budget.first_cold_code_rva())
