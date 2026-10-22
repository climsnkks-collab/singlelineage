"""Unchanged SKILL v1 schema + pinned explicit local stable-key bijection.
Catalog spell IDs and consumer instance keys are separate configured domains.
The key numbers are local backend settings, never original server counters.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib,weakref
from tools.local_original_session.buff_lifecycle import canonical,need,encoded

KEY_CONTRACT_PATH='work/local_server_rea_20261016/run115_buff_self_instance_time/main-review.json'
KEY_CONTRACT_SHA='5bea52822854b59db0e64b4a5c14fbf1326b606abee10dd107889bd3005e4289'
# Explicit server configuration; values have no original numeric-ID meaning.
LOCAL_SELF_KEYS=((1,65537),(2,65538))
def local_self_policy(root,spell_ids):
    raw=(Path(root)/KEY_CONTRACT_PATH).read_bytes()
    need(hashlib.sha256(raw).hexdigest()==KEY_CONTRACT_SHA,'BUFF_KEY_CONTRACT_SOURCE_CHANGED')
    need(type(spell_ids)is tuple and spell_ids and set(spell_ids)<=set(dict(LOCAL_SELF_KEYS)),
         'BUFF_CONFIGURED_LOCAL_SELF_RULES_REQUIRED')
    return InstancePolicy('LOCAL_SINGLE_INSTANCE_SELF_BUFF_KEYS_V1',
        tuple(p for p in LOCAL_SELF_KEYS if p[0]in spell_ids),KEY_CONTRACT_SHA)

def catalog_icon_policy(sources,provenance):
    """Explicit LOCAL mapping from already checked Catalog.configure outputs.
    Catalog icon numbers are not asserted to be original server Buff IDs.
    """
    need(type(sources)is tuple and sources and type(provenance)is dict and provenance,
         'BUFF_CATALOG_ICON_METADATA_REQUIRED')
    pins=tuple(sorted(provenance.items()))
    need(all(type(k)is str and type(v)is str and len(v)==64
             and all(c in '0123456789abcdef'for c in v)for k,v in pins),
         'BUFF_CATALOG_ICON_PROVENANCE_REQUIRED')
    entries=[];selected_rows=[]
    for source in sources:
        need(type(source)is dict and source.get('provenance')==provenance
             and type(source.get('ui_rows'))is list and len(source['ui_rows'])==1,
             'BUFF_CATALOG_ICON_METADATA_REQUIRED')
        row=source['ui_rows'][0];config=row.get('named_UI_configuration',{})
        sid=source.get('spell_id')
        need(row.get('class')=='generic'and type(row.get('grade'))is int and row['grade']>0
             and row.get('spell_id')==sid and config.get('id')==sid
             and config.get('required',{}).get('target')=='self'and 'catalyst'not in config,
             'BUFF_CATALOG_ICON_EXACT_SELF_ROW_REQUIRED')
        entries.append((sid,config.get('icon')))
        selected_rows.append((sid,row['class'],row['grade'],config.get('icon')))
    return InstancePolicy('LOCAL_CATALOG_ICON_SELF_BUFF_KEYS_V1',tuple(entries),KEY_CONTRACT_SHA,pins,tuple(selected_rows))

@dataclass(frozen=True)
class InstancePolicy:
    name:str
    entries:tuple
    source_contract_sha256:str
    metadata_sources:tuple=()
    metadata_rows:tuple=()
    def __post_init__(self):
        need(self.name in ('LOCAL_SINGLE_INSTANCE_SELF_BUFF_KEYS_V1','LOCAL_CATALOG_ICON_SELF_BUFF_KEYS_V1'),
             'BUFF_EXPLICIT_LOCAL_KEY_POLICY')
        need(type(self.metadata_sources)is tuple and
             (bool(self.metadata_sources) if self.name=='LOCAL_CATALOG_ICON_SELF_BUFF_KEYS_V1'else not self.metadata_sources),
             'BUFF_CATALOG_ICON_PROVENANCE_REQUIRED')
        need(type(self.entries)is tuple and 0<len(self.entries)<=128
             and all(type(p)is tuple and len(p)==2 and type(p[0])is int and 0<p[0]<1<<31
                     and type(p[1])is int and 0<p[1]<1<<31 and p[1]!=0x4e41 for p in self.entries)
             and len({p[0]for p in self.entries})==len(self.entries)
             and len({p[1]for p in self.entries})==len(self.entries),'BUFF_DISTINCT_SAFE_KEY_BIJECTION_REQUIRED')
        need(all(type(p)is tuple and len(p)==2 and type(p[0])is str
             and type(p[1])is str and len(p[1])==64
             and all(c in '0123456789abcdef'for c in p[1])for p in self.metadata_sources)
             and len({p[0]for p in self.metadata_sources})==len(self.metadata_sources),
             'BUFF_CATALOG_ICON_PROVENANCE_REQUIRED')
        need(type(self.metadata_rows)is tuple and
             (tuple((r[0],r[3])for r in self.metadata_rows)==self.entries
              and all(type(r)is tuple and len(r)==4 and r[1]=='generic'
                      and type(r[2])is int and r[2]>0 for r in self.metadata_rows)
              if self.name=='LOCAL_CATALOG_ICON_SELF_BUFF_KEYS_V1'else not self.metadata_rows),
             'BUFF_CATALOG_EXACT_SELECTED_ROWS_REQUIRED')
        need(self.source_contract_sha256==KEY_CONTRACT_SHA,'BUFF_ACCEPTED_KEY_SOURCE_PIN_REQUIRED')

@dataclass(frozen=True)
class SourceEvent:
    kind:str
    spell_id:int
    instance_key:int
    expires_ms:int
    accepted_now_ms:int
    previous_expiry_ms:int|None

_SOURCE=weakref.WeakKeyDictionary()
_KEYS=weakref.WeakKeyDictionary()

class SkillDocument(canonical.SkillDocument):
    def __init__(self,*args,key_policy,**kwargs):
        need(type(key_policy)is InstancePolicy,'BUFF_EXACT_INSTANCE_POLICY_REQUIRED')
        super().__init__(*args,**kwargs)
        need({p[0]for p in key_policy.entries}==set(self.rules),'BUFF_EXACT_RULESET_KEY_CONFIGURATION')
        self.key_policy=key_policy
        _KEYS[self]=(key_policy,tuple(sorted(self.rules.items())),
            (key_policy.name,key_policy.entries,key_policy.source_contract_sha256,key_policy.metadata_sources,key_policy.metadata_rows))
    def policy_ready(self,root):
        # Metadata policy was bound once from the checked Catalog output;
        # the response adapter accepts original key contracts at cold init.
        # Legacy callers retain their original key-contract file boundary.
        if self.key_policy.name=='LOCAL_SINGLE_INSTANCE_SELF_BUFF_KEYS_V1':
            need(hashlib.sha256((Path(root)/KEY_CONTRACT_PATH).read_bytes()).hexdigest()==KEY_CONTRACT_SHA,
                 'BUFF_KEY_CONTRACT_SOURCE_CHANGED')
        self.policy_current()
    def policy_current(self):
        p,r,policy=_KEYS[self]
        need(self.key_policy is p and tuple(sorted(self.rules.items()))==r
             and (p.name,p.entries,p.source_contract_sha256,p.metadata_sources,p.metadata_rows)==policy,'BUFF_KEY_POLICY_OR_RULESET_CHANGED')
    def plan_apply(self,document,binding,**kwargs):
        self.validate(document);self.policy_current()
        shadow=object.__new__(self.core.Store)
        shadow.__dict__=dict(rules=self.rules,account=self.account,rule_hash=self.rule_hash,
            data=deepcopy(document),lock=self.batch.inventory_store._lock,failed=False,_prepared_only=True)
        shadow._current=lambda:self.provider.current(binding)
        shadow._save=lambda data:setattr(shadow,'data',self.validate(data))
        result=shadow.apply(binding.uid,**kwargs)
        return result,shadow.data

    def seal_cast_plan(self,plan,owner):
        from tools.local_original_session.hp_resource_owner import ResourceOwner,CastPlan
        need(type(owner)is ResourceOwner and owner.skill_schema is self and type(plan)is CastPlan
             and plan.operation is owner._prepared_operation and plan.phase=='PLANNED','BUFF_EXACT_CAST_SOURCE_PLAN')
        _SOURCE[plan]=(weakref.ref(owner),owner.plan_digest(plan))

    def source_event(self,binding,source_plan,request):
        from tools.local_original_session.buff_lifecycle import EventPlan,_PLANS
        if type(source_plan)is EventPlan:
            plan=source_plan.transition;w=_PLANS.get(plan)
            need(w is not None and w[0].schema is self and w[1]==w[0].fingerprint(plan)
                 and plan.binding is binding and plan.request==request
                 and type(source_plan.index)is int and 0<=source_plan.index<len(plan.events)
                 and plan.events[source_plan.index]is source_plan.event,'BUFF_ISSUED_LIFECYCLE_SOURCE_EVENT')
            e=source_plan.event;before=plan.before['document'];after=plan.after
            kind,spell,expiry,now,previous=e.kind,e.spell_id,e.expires_ms,e.accepted_now_ms,e.previous_expiry_ms
        else:
            w=_SOURCE.get(source_plan);owner=None if w is None else w[0]()
            need(owner is not None and owner.skill_schema is self and w[1]==owner.plan_digest(source_plan)
                 and source_plan.operation.binding is binding and source_plan.operation.request==request
                 and (source_plan.phase=='PLANNED' and owner._prepared_operation is source_plan.operation
                      or source_plan.phase=='COMMITTED' and owner._delivery_active is not None
                      and owner._delivery_active.plan is source_plan),'BUFF_ISSUED_CAST_SOURCE_EVENT')
            events=[e for e in source_plan.operation.semantic_result['events']if e['kind']in ('buff_add','buff_refresh')]
            need(len(events)==1 and not any(e['kind']=='buff_remove'for e in source_plan.operation.semantic_result['events']),
                 'BUFF_EXPIRE_BEFORE_CAST_REQUIRED')
            e=events[0];kind,spell,expiry,now=e['kind'],e['spell_id'],e['expires_ms'],source_plan.accepted_now_ms
            before,after=source_plan.skill_before,source_plan.skill_after
            previous=before['characters'][str(binding.uid)]['buffs'].get(str(spell))
        self.validate(before);self.validate(after)
        self.policy_current()
        return SourceEvent(kind,spell,dict(self.key_policy.entries)[spell],expiry,now,previous)
