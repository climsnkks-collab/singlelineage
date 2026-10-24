"""Single canonical backing for the existing hp_status.Service projection.

ITEM owns namespace/CAS/one-replace/receipt. This owner computes RESOURCE and
SKILL transitions, binds the exact live Service Snapshot and installs a status
projection only after confirmed canonical commit. No independent balances.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import asyncio
import json
import weakref

from tools.local_original_session import hp_resource_document as document_module

SHIELD_SOURCE_PINS=(
 ('work/local_server_rea_20261016/run162_shield_effective_ac/main-review.json','3dc74f8d09274e9bf5f5469a10091b21254fd9759d7ff93527ad1338f69652d4'),
 ('work/local_server_rea_20261016/run162_shield_effective_ac/worker/packet.json','1d0062feddfcddb435d8eb61a203a95b4546287f9165e20a3e91c6c78a9c9c7e'))


def need(value, code):
    if not value:
        raise ValueError(code)


@dataclass(frozen=True)
class Operation:
    binding: object = field(repr=False)
    snapshot: object = field(repr=False)
    before: dict | None = field(repr=False)
    after: dict = field(repr=False)
    request: bytes = field(repr=False)
    txid: str
    reason: str
    semantic_result: dict | None = field(default=None, repr=False)


@dataclass(eq=False)
class CastPlan:
    operation: Operation = field(repr=False)
    changes: tuple = field(repr=False)
    skill_before: dict = field(repr=False)
    skill_after: dict = field(repr=False)
    status_fields: dict = field(repr=False)
    status_wire: bytes = field(repr=False)
    accepted_now_ms: int
    phase: str = 'PLANNED'
    catalyst: object = field(default=None,repr=False)
    advance_spirit: object = field(default=None,repr=False)
    stats_preview: object = field(default=None,repr=False)


@dataclass(frozen=True, eq=False)
class _CastStatsContext:
    owner: object
    plan: object
    operation: object
    binding: object
    skill_before: object
    skill_after: object
    accepted_now_ms: int
    slot: object


@dataclass(frozen=True)
class CatalystDebit:
    owner_ref: object = field(repr=False)
    binding: object = field(repr=False)
    recipe: tuple
    item_uid: int
    before_inventory: bytes = field(repr=False)
    after_inventory: bytes = field(repr=False)
    inventory_wire: bytes = field(repr=False)
    asset_revision: int

@dataclass(frozen=True)
class Projection:
    operation: Operation = field(repr=False)
    receipt: dict = field(repr=False)
    fields: dict = field(repr=False)
    resource_digest: str
    wire: bytes = field(repr=False)
    skill_plan: object = field(default=None, repr=False)
    skill_parent: object = field(default=None, repr=False)


class ResourceOwner:
    def require_exclusive(self,binding,document,*,now_ms=None):
        row=document['characters'].get(str(binding.uid))
        if row is None:return
        now=row['clock'];selected=self._shield_world_clock.get(id(binding.writer))
        if selected is not None:
            need(selected[0]is binding.generation,'BUFF_EXCLUSIVE_SELECTED_CLOCK_GENERATION_REQUIRED')
            now=max(now,selected[1])
        if now_ms is not None:now=max(now,now_ms)
        self.skill_schema.require_exclusive(binding,document,now_ms=now)

    def bind_catalyst_policy(self,key_policy,module):
        import sys
        fn=module.adopt_cast_drained
        need(self._catalyst_binding is None and (not self.status.broker._started
             or (not self.status.broker._closing and _scope_construction_current(self.status.broker)))
             and self._delivery_active is None and self.skill_schema.key_policy is key_policy
             and key_policy.catalyst_recipes and sys.modules.get('tools.local_original_session.cast_inventory_adoption')is module
             and callable(fn)and fn.__globals__ is vars(module),'CATALYST_EXACT_COLD_ADOPTION_REQUIRED')
        self._catalyst_binding=(key_policy,module,fn,fn.__code__)

    def catalyst_current(self):
        import sys
        bound=self._catalyst_binding
        need(bound is not None,'CATALYST_ADOPTION_SOURCE_UNBOUND')
        p,m,f,c=bound
        need(self.skill_schema.key_policy is p and sys.modules.get('tools.local_original_session.cast_inventory_adoption')is m
             and m.adopt_cast_drained is f and f.__code__ is c and f.__globals__ is vars(m),
             'CATALYST_ADOPTION_SOURCE_CHANGED')
        self.skill_schema.policy_current()
        return f

    def plan_catalyst(self,binding,spell_id):
        recipe=dict(self.skill_schema.key_policy.catalyst_recipes).get(spell_id)
        if recipe is None:return None
        self.catalyst_current();self.provider.current(binding)
        from tools.local_original_session import inventory,inventory_update,item_transfer_protocol
        frame,revision=self.store.restore(binding)
        need(type(frame)is bytes and frame==binding.generation.current_frame,'CATALYST_CURRENT_CANONICAL_FRAME_REQUIRED')
        frame=binding.generation.current_frame # Preserve the exact selected before-frame reference.
        items=inventory.validate_current_collection_frame(frame,policy=inventory.COLLECTION_POLICY)
        selected=tuple(i for i in items if i.template_bits==recipe[1]and dict(i.raw_fields)[4]>=recipe[2])
        need(selected,'CATALYST_INSUFFICIENT_QUANTITY')
        item=min(selected,key=lambda i:i.identifier);fields=dict(item.raw_fields) # Explicit LOCAL lowest-UID eligible stack.
        need(fields[4]>=recipe[2],'CATALYST_INSUFFICIENT_QUANTITY')
        if fields[4]==recipe[2]:
            after_items=tuple(i for i in items if i is not item)
            wire=item_transfer_protocol.build_remove(uid=item.identifier);item_transfer_protocol.parse_remove_frame(wire)
        else:
            fields[4]-=recipe[2];changed=inventory.validate_frame(inventory.build_add(fields))
            after_items=tuple(changed if i is item else i for i in items)
            wire=inventory_update.build_update({1:item.identifier,4:fields[4]})
            need(inventory_update.validate_frame(wire).present_fields==frozenset((1,4)),'CATALYST_QUANTITY_ONLY_UPDATE_REQUIRED')
        after=inventory.build_current_collection(after_items,policy=inventory.COLLECTION_POLICY)
        return CatalystDebit(weakref.ref(self),binding,recipe,item.identifier,frame,after,wire,revision)

    def bind_light_policy(self, policy, module):
        need(self._light_policy is None and self._light is None and not self.active
             and (not self.status.broker._started or (not self.status.broker._closing
                  and _scope_construction_current(self.status.broker))) and type(policy)is module.LightPolicy,
             'LIGHT_EXACT_COLD_POLICY_REQUIRED')
        policy.source_ready(self.status_module.observe.ROOT)
        self._light_policy,self._light=policy,module

    def light_wire(self, binding, document):
        return None if self._light is None else self._light.policy_wire(self,binding,document)

    def cast_light_wire(self, plan):
        if not any(e.get('spell_id')==1 for e in plan.operation.semantic_result['events']):return None
        return self.light_wire(plan.operation.binding,plan.skill_after)

    def light_actor_fields(self, writer, fields):
        result=dict(fields)
        if self._light_policy is None:return result
        record=self._world_reads.get(id(writer))
        if record is None:
            binding=self._binding(writer);skill=self.store.participant(binding,'SKILL')['document']
        else:
            binding=record['binding'];skill=record['skill']['document']
        wire,scalar=self.light_wire(binding,skill)
        need(result==self.status.broker.realm._actor_fields,'LIGHT_FULL_ACTOR_BASE_REQUIRED')
        result[6]=scalar
        return result

    def shield_status_fields(self, binding, fields, skill_document):
        """Absolute SC_STATUS W from existing LOCAL base and canonical SKILL.
        Display is wrap32(-W); LOCAL Shield -2 means baseW+2, not wire-2.
        No new clock sample/base/save/stacking or client setter is introduced.
        """
        from tools.local_original_session import buff_lifecycle
        lifecycle = getattr(self.status.broker, '_buff_lifecycle', None)
        if lifecycle is None:return dict(fields)
        need(type(lifecycle) is buff_lifecycle.Service and lifecycle.owner is self
             and lifecycle.schema is self.skill_schema, 'SHIELD_CANONICAL_OWNER_REQUIRED')
        need(self._shield_source_pins==SHIELD_SOURCE_PINS,'SHIELD_TYPED_SOURCE_WITNESS_CHANGED')
        self.skill_schema.validate(skill_document)
        row=skill_document['characters'].get(str(binding.uid))
        need(row is not None and fields[1]==binding.uid,'SHIELD_SELECTED_SKILL_REQUIRED')
        base=self.status._profile_fields[14]
        need(type(base)is int and -(1<<31)<=base<(1<<31),'SHIELD_EXISTING_BASE_W_INT32')
        selected_clock=self._shield_world_clock.get(id(binding.writer))
        now=row['clock']
        if selected_clock is not None:
            need(selected_clock[0]is binding.generation,'SHIELD_WORLD_CLOCK_GENERATION_CHANGED')
            now=max(now,selected_clock[1])
        active=row['buffs'].get('2',0)>now
        bits=(base+(2 if active else 0))&0xffffffff
        result=dict(fields);result[14]=bits if bits<(1<<31)else bits-(1<<32)
        return result

    def project_buff_commit(self, service, plan, parent, receipt, fields, wire):
        """SKILL-only receipt authorizes the same typed full-status projection."""
        from tools.local_original_session.buff_lifecycle import Service,Delivery,_PLANS
        witness=_PLANS.get(plan)
        need(type(service)is Service and type(parent)is Delivery and parent.service is service
             and parent.owner is self and parent.plan is plan and witness is not None
             and witness[0]is service and witness[1]==service.fingerprint(plan),
             'SHIELD_ISSUED_LIFECYCLE_PLAN_REQUIRED')
        if getattr(plan, 'resource_stage', None) is not None:
            return self._project_advance_spirit_buff_commit(service, plan, parent, receipt, fields, wire)
        binding=plan.binding;self.provider.current(binding)
        resource=self._participant(binding)
        operation=Operation(binding,plan.snapshot,resource['document'],resource['document'],
            plan.request,plan.txid,'BUFF_STATUS',dict(kind='LOCAL_SHIELD_ABSOLUTE_STATUS'))
        permit=Projection(operation,deepcopy(receipt),fields,resource['digest'],wire,plan,parent)
        self._projection=permit
        try:
            return self.status.project_resource_commit(binding.writer,binding.generation.row,
                plan.snapshot,fields,resource['document']['revision'],permit)
        finally:self._projection=None

    def __init__(self, status, status_module, batch, store, document, *, core, skill_schema=None,
                 catalog_digest, setup_uid=None):
        need(type(store) is batch.BatchStore and document.provider is store.provider
             and document.status is status, 'RESOURCE_CANONICAL_OWNER_REQUIRED')
        need(store.lock is batch.inventory_store._lock, 'RESOURCE_CANONICAL_LOCK_REQUIRED')
        self.status, self.status_module, self.batch, self.store = status, status_module, batch, store
        for relative,expected in SHIELD_SOURCE_PINS:
            need(hashlib.sha256((status_module.observe.ROOT/relative).read_bytes()).hexdigest()==expected,'SHIELD_TYPED_SOURCE_PIN')
        self._shield_source_pins=SHIELD_SOURCE_PINS
        self._shield_world_clock={}
        self._light_policy=self._light=None
        self._catalyst_binding=self._catalyst_prepared=None
        self._advance_spirit_prepared = None
        self._advance_spirit_operation = None
        self._cast_stats_enabled = self._cast_stats_context = self._cast_stats_plan = None
        self.provider, self.document, self.core, self.skill_schema = store.provider, document, core, skill_schema
        document.owner = self
        self.catalog_digest = catalog_digest
        self.active = False
        self._arming = None
        self._operation = self._projection = None
        self._prepared_operation = None
        self._prepared_digest = None
        self._deliveries = {}
        self._delivery_active = None
        self._delivery_dispatcher = None
        need(setup_uid is None or type(setup_uid) is int and 0 < setup_uid <= 0xffffffff,
             'RESOURCE_EXPLICIT_SETUP_UID_REQUIRED')
        self.setup_uid = setup_uid
        self._world_setup = None
        self._world_reads = {}
        self._hp_effect = None
        self._hp_read = None
        self._hp_producer = None
        self._hp_edges = {}
        self._hp_receipts = {}
        self._hp_baselines = {}
        self._hp_baseline_projection = None

    def selection_locked(self, writer, exact_selection_request):
        binding = self._binding(writer)
        lifecycle=getattr(self.status.broker,'_buff_lifecycle',None)
        if lifecycle is not None:
            self._shield_world_clock[id(writer)]=(binding.generation,lifecycle._now())
        try:
            self._participant(binding)
        except ValueError as error:
            if error.args != ('BATCH_PARTICIPANT_NOT_INSTALLED',):
                raise
            need(binding.uid == self.setup_uid and type(exact_selection_request) is bytes
                 and len(exact_selection_request) > 0 and not self.active
                 and self._world_setup is None, 'RESOURCE_MISSING_EXPLICIT_WORLD_SETUP_REQUIRED')
            need(self.status._resource_owner is None and id(writer) not in self.status._states,
                 'RESOURCE_INITIAL_WORLD_INTERCEPTOR_REQUIRED')
            self._world_setup = (binding, exact_selection_request)
            self.status.bind_resource_seed_world(self, writer)
            return
        if self.status._resource_owner is None:
            self.status.bind_resource_restore_owner(self, writer)
        else:
            need(self.status._resource_owner is self and self.active,
                 'RESOURCE_EXISTING_RESTORE_OWNER_REQUIRED')

    def world_completed(self, writer, snapshot):
        self._hp_baselines[id(writer)] = snapshot
        self.release_world_projection(writer)
        if self.active:
            return self.validate_projection(writer, snapshot)
        need(self._world_setup is not None, 'RESOURCE_WORLD_SETUP_NOT_AUTHORIZED')
        binding, request = self._world_setup
        self.provider.current(binding)
        need(binding.writer is writer and snapshot is self.status._resource_raw_current(writer)
             and id(writer) not in self.status._world, 'RESOURCE_EXACT_COMPLETED_WORLD_REQUIRED')
        self._arming = (binding, snapshot)
        if self.provider._packet_port is not None:
            return None  # common after-world hook owns the real drained receipt
        receipt = self.seed_locked(binding, txid='RESOURCE_SEED:' + str(binding.uid), request=request)
        self._world_setup = None
        return receipt

    def packet_world_completed(self, context):
        port = self.provider._packet_port
        need(port is not None and port.resource is self
             and port.server.check_current(context) is context,
             'RESOURCE_ORIGINAL_PACKET_WORLD_REQUIRED')
        if self.active:
            return  # original world_completed already validated restored values
        need(self._world_setup is not None and self._arming is not None,
             'RESOURCE_PACKET_WORLD_SETUP_REQUIRED')
        binding, request = self._world_setup
        need(port.selected_current(binding,world_required=True) is context
             and self._arming[0] is binding
             and self._arming[1] is self.status._resource_raw_current(context.writer)
             and context.writer is binding.writer and id(context.writer) not in self.status._world,
             'RESOURCE_SAME_COMPLETED_PACKET_WORLD_REQUIRED')
        self.seed_locked(binding, txid='RESOURCE_SEED:' + str(binding.uid), request=request)
        self._world_setup = None

    def packet_retire_selection(self, writer):
        self.release_world_projection(writer)
        if self._world_setup is not None and self._world_setup[0].writer is writer:
            need(self._prepared_operation is None and self._operation is None,
                 'RESOURCE_PACKET_PENDING_OPERATION_NOT_RETIRED')
            self._world_setup = None
            if self._arming is not None and self._arming[0].writer is writer:
                self._arming = None

    def _binding(self, writer):
        binding = self.provider.bind(writer)
        self.provider.current(binding)
        return binding

    @staticmethod
    def _same_operation(a, b):
        return (a.uid == b.uid and a.writer is b.writer and a.generation is b.generation
                and a.operation_lock is b.operation_lock and a.owned_scope is b.owned_scope)

    def arm(self, writer, snapshot):
        need(not self.active and self._arming is None and self.status._resource_owner is None,
             'RESOURCE_OWNER_ALREADY_ARMED')
        binding = self._binding(writer)
        need(snapshot is self.status._resource_raw_current(writer) and snapshot.target_uid == binding.uid
             and id(writer) not in self.status._world, 'RESOURCE_SEED_WORLD_DRAIN_REQUIRED')
        prior = [self.status._operations.get(id(writer))]
        prior.extend(self.status._repeated_histories.get(id(writer), ())[-1:])
        prior.extend(self.status._life_deliveries.get(id(writer), ())[-1:])
        need(all(item is None or item.phase == 'DRAINED' for item in prior),
             'RESOURCE_SEED_PREVIOUS_STATUS_DRAIN_REQUIRED')
        self._arming = (binding, snapshot)

    def authorize_stage(self, stage):
        op = self._operation
        need(type(op) is Operation and op is self._prepared_operation and stage.binding is op.binding
             and stage.snapshot is op.snapshot and stage.before == op.before
             and stage.after == op.after and stage.reason == op.reason
             and type(op.request) is bytes and len(op.request) > 0,
             'RESOURCE_OWNER_EXACT_COMPUTED_OPERATION_REQUIRED')
        self.provider.current(op.binding)
        if op.reason == 'BUFF_MAXIMUM':
            need(self._advance_spirit_operation is not None, 'ADVANCE_SPIRIT_LIFECYCLE_PRODUCER_REQUIRED')
        if self._advance_spirit_operation is not None:
            issued_op, advance = self._advance_spirit_operation
            need(issued_op is op, 'ADVANCE_SPIRIT_EXACT_RESOURCE_STAGE_REQUIRED')
            if type(advance) is AdvanceSpiritCastInput:
                need(op.reason == 'CAST_COST', 'ADVANCE_SPIRIT_CAST_REASON_REQUIRED')
                self._validate_advance_spirit_cast(advance, op.binding, op.before, result=op.semantic_result)
            else:
                need(type(advance) is AdvanceSpiritLifecycleInput and op.reason == 'BUFF_MAXIMUM',
                     'ADVANCE_SPIRIT_LIFECYCLE_REASON_REQUIRED')
                self._require_advance_spirit_lifecycle(advance.service, advance.plan)
        if op.reason == 'CONSUMABLE_HEAL':
            from tools.local_original_session.consumable_healing import HealingBatch
            healing=getattr(self.status.broker,'_consumable_healing',None)
            need(type(healing) is HealingBatch and healing.service.owner is self,
                 'RESOURCE_ACTUAL_HEALING_PRODUCER_REQUIRED')
            healing.authorize_resource_stage(op)
        if op.reason in ('HP_EFFECT', 'PLAYER_LIFE'):
            need(self._hp_producer is not None and self._hp_producer[0] is op,
                 'RESOURCE_HP_ACTUAL_PRODUCER_REQUIRED')
            proof = self._hp_producer[1]
            current = self._verified_hp_producer(op.binding.writer, op.binding.generation.row,
                op.snapshot, proof[3] if op.reason == 'PLAYER_LIFE' else None)
            need(len(current) == len(proof) and all(a is b for a,b in zip(current[:4],proof[:4]))
                 and current[4:] == proof[4:], 'RESOURCE_HP_PRODUCER_CHANGED_BEFORE_COMMIT')
        return True

    def healing_operation(self, batch, binding, intent, snapshot, before, decision, *, txid, request):
        from tools.local_original_session.consumable_healing import HealingBatch, HealDecision
        need(type(batch) is HealingBatch and batch is getattr(self.status.broker,'_consumable_healing',None)
             and batch.service.owner is self and type(decision) is HealDecision
             and self._prepared_operation is None and self._operation is None,
             'RESOURCE_SINGLE_NORMAL_HEALING_PRODUCER_REQUIRED')
        batch.received_context(batch._received)
        self.require_hp_quiescent(binding.writer)
        need(self.status.current(binding.writer) is snapshot and snapshot.current_hp > 0
             and self._participant(binding) == before,
             'RESOURCE_CURRENT_LIVING_HEALING_PREIMAGE_REQUIRED')
        values=dict(before['document']['values'])
        hp=min(values['11'],values['10']+decision.heal)
        need(type(decision.heal) is int and hp >= 0,'RESOURCE_HEALING_RESULT_DOMAIN_REQUIRED')
        values['10']=hp
        after=self.document.next_values(before['document'],values=values)
        return Operation(binding,snapshot,before['document'],after,request,txid,'CONSUMABLE_HEAL')

    def project_healing_committed(self, batch, staged, receipt):
        from tools.local_original_session.consumable_healing import HealingBatch, PreparedHealing
        need(type(batch) is HealingBatch and batch.service.owner is self
             and batch._prepared is staged and type(staged) is PreparedHealing
             and receipt['phase']=='COMMITTED', 'RESOURCE_EXACT_HEALING_COMMIT_REQUIRED')
        op=staged.operation
        resource=self._participant(op.binding)
        need(resource['document']==op.after,'RESOURCE_HEALING_READBACK_REQUIRED')
        permit=Projection(op,deepcopy(receipt),dict(staged.status_fields),resource['digest'],staged.status_wire)
        self._projection=permit
        try:
            return self.status.project_resource_commit(op.binding.writer,op.binding.generation.row,
                op.snapshot,dict(staged.status_fields),op.after['revision'],permit)
        finally:self._projection=None

    def _participant(self, binding):
        self.provider.current(binding)
        row = self.store.participant(binding, 'RESOURCE')
        self.document.validate(row['document'])
        need(row['document']['uid'] == binding.uid, 'RESOURCE_CHARACTER_NAMESPACE_REQUIRED')
        return row

    @contextmanager
    def _staged_operation(self, operation):
        need(self._operation is None and self._projection is None, 'RESOURCE_OPERATION_REENTRY_REFUSED')
        need(operation is self._prepared_operation, 'RESOURCE_OWNER_COMPUTED_PLAN_REQUIRED')
        self._operation = operation
        try:
            with self.document.staged(operation.binding, operation.snapshot, operation.before,
                                      operation.after, reason=operation.reason):
                yield
        finally:
            self._operation = None
            self._prepared_operation = None
            self._prepared_digest = None
            if self._advance_spirit_operation is not None and self._advance_spirit_operation[0] is operation:
                self._advance_spirit_operation = None

    def seed_locked(self, binding, *, txid, request):
        self.provider.current(binding)
        need(self.status._resource_owner is self and not self.active and self._arming is not None
             and self._same_operation(binding, self._arming[0]), 'RESOURCE_EXACT_ARMED_SEED_REQUIRED')
        snapshot = self._arming[1]
        previous = self.store.lookup(binding, txid=txid, request_sha=self.batch.request_digest(request))
        need(previous is None, 'RESOURCE_SEED_RECEIPT_RECOVERY_REQUIRED')
        try:
            self.store.participant(binding, 'RESOURCE')
        except ValueError as error:
            if error.args != ('BATCH_PARTICIPANT_NOT_INSTALLED',):
                raise
        else:
            raise ValueError('RESOURCE_EXISTING_DOCUMENT_RESTORE_REQUIRED')
        after = self.document.seed(binding, snapshot)
        op = Operation(binding, snapshot, None, after, request, txid, 'SEED')
        need(self._prepared_operation is None, 'RESOURCE_OPERATION_REENTRY_REFUSED')
        self._prepared_operation = op
        with self.store.lock, self._staged_operation(op):
            _, revision = self.store.restore(binding)
            change = self.batch.ParticipantChange('RESOURCE', -1, self.batch.digest(None), after)
            reservation = self.store.prepare(binding, txid=txid, request=request,
                catalog_digest=self.catalog_digest, expected_revision=revision,
                changes=(), participants=(change,))
            receipt = self.store.commit(binding, reservation)
            need(receipt['phase'] == 'COMMITTED' and self._participant(binding)['document'] == after,
                 'RESOURCE_SEED_COMMIT_READBACK_REQUIRED')
            self.active = True
            self._hp_baselines[id(binding.writer)] = snapshot
            self._arming = None
            self.validate_projection(binding.writer, snapshot)
            return receipt

    def arm_restore(self, writer):
        """Before FIRST outgoing world frame; only existing RESOURCE may bind."""
        need(not self.active and self._arming is None and self.status._resource_owner is None,
             'RESOURCE_OWNER_ALREADY_ARMED')
        binding = self._binding(writer)
        self._participant(binding)  # Missing is refused, never seeded from profile.
        self.active = True

    def validate_projection(self, writer, snapshot):
        if self._hp_read is not None and self._hp_read.writer is writer:
            return self._hp_read.validate_snapshot(snapshot)
        if self._hp_effect is not None and self._hp_effect.delivery is not None and self._hp_effect.writer is writer:
            return self._hp_effect.validate_projection(snapshot)
        if not self.active:
            need(self._arming is not None and self._arming[1] is snapshot,
                 'RESOURCE_SEEDING_RAW_BORROW_REQUIRED')
            self.provider.current(self._arming[0])
            return True
        if self._delivery_active is not None and self._delivery_active.binding.writer is writer:
            return self._delivery_active.validate_projection(snapshot)
        binding = self._binding(writer)
        doc = self._participant(binding)['document']
        need(snapshot.target_uid == binding.uid
             and {str(n): snapshot.fields[n] for n in document_module.RESOURCE_FIELDS} == doc['values'],
             'RESOURCE_CANONICAL_PROJECTION_MISMATCH')
        if getattr(self.status.broker,'_buff_lifecycle',None) is not None:
            skill=self.store.participant(binding,'SKILL')['document']
            need(snapshot.fields[14]==self.shield_status_fields(binding,snapshot.fields,skill)[14],
                 'SHIELD_CANONICAL_STATUS_MISMATCH')
        return True

    def world_fields(self, writer, base_fields):
        if not self.active:
            need(self._world_setup is not None and self._world_setup[0].writer is writer,
                 'RESOURCE_MISSING_BACKING_WORLD_REFUSED')
            if id(writer) in self.status._world:
                self.provider.delivery_current(self._world_setup[0])
            else:
                self.provider.current(self._world_setup[0])
            need(base_fields[1] == self.setup_uid, 'RESOURCE_INITIAL_WORLD_SELECTED_UID_REQUIRED')
            # Existing full source world response only. No RESOURCE document is
            # created or balance authority claimed until its exact drain.
            return dict(base_fields)
        record = self._world_reads.get(id(writer))
        if record is None:
            binding = self._binding(writer)
            doc = self._participant(binding)['document']
            skill = (self.store.participant(binding,'SKILL')['document']
                     if getattr(self.status.broker,'_buff_lifecycle',None) is not None else None)
        else:
            binding, pending = record['binding'], record['pending']
            index = min(pending['index'], len(pending['replies']) - 1)
            policy = binding.generation.row['policy_row']
            phase = ('BEFORE_RESERVE' if policy.pending_opcode is None and policy.sent == pending['sent'] + index
                     else 'AFTER_DRAIN' if policy.pending_opcode is None and policy.sent == pending['sent'] + index + 1
                     else 'DRAIN_PENDING' if pending.get('resource_drain_returned') else 'BEGIN_WRITE')
            doc = self.store.participant_for_projection(record['cap'], 'RESOURCE',
                participant=pending, index=index, wire=pending['replies'][index], phase=phase)['document']
            skill = (self.store.participant_for_projection(record['cap'],'SKILL',participant=pending,
                index=index,wire=pending['replies'][index],phase=phase)['document']if 'skill'in record else None)
        need(base_fields[1] == binding.uid, 'RESOURCE_WORLD_SELECTED_UID_REQUIRED')
        fields = dict(base_fields)
        fields.update({int(n): value for n, value in doc['values'].items()})
        if skill is not None:
            self.require_exclusive(binding,skill)
            fields=self.shield_status_fields(binding,fields,skill)
        self.status_module.session.world.validate_input(0x4e38, fields)
        return fields

    def open_world_projection(self, writer, pending):
        if not self.active:
            # Missing backing is explicit initial setup, never a projection cap.
            need(self._world_setup is not None and self._world_setup[0].writer is writer,
                 'RESOURCE_INITIAL_WORLD_SETUP_REQUIRED')
            return
        binding = self._binding(writer)
        participant = self._participant(binding)
        record = dict(binding=binding, pending=pending, participant=deepcopy(participant),
                      fields=dict(pending['fields']), cap=None)
        need(id(writer) not in self._world_reads, 'RESOURCE_WORLD_PROJECTION_REENTRY')
        self._world_reads[id(writer)] = record
        try:
            names=('RESOURCE',)
            if getattr(self.status.broker,'_buff_lifecycle',None) is not None:
                record['skill']=deepcopy(self.store.participant(binding,'SKILL'));names+=('SKILL',)
            record['cap'] = self.store.open_projection_read(binding, self.register_delivery_dispatcher(),
                pending, names, pending['replies'])
        except BaseException:
            self._world_reads.pop(id(writer), None)
            raise

    def validate_projection_read(self, pending, binding, *, participants, index, wire, phase):
        if type(pending) is HPProducerRead:
            return pending.validate_memory(binding, participants=participants,index=index,wire=wire,phase=phase)
        record = self._world_reads.get(id(binding.writer))
        need(record is not None and record['pending'] is pending and record['binding'] is binding
             and self.status._world.get(id(binding.writer)) is pending
             and self.status._resource_owner is self and not self.status.closed
             and participants == dict({'RESOURCE': record['participant']},**({'SKILL':record['skill']}if 'skill'in record else {}))
             and pending['fields'] == record['fields']
             and pending['lifetime'][2] is binding.writer
             and pending['lifetime'][3] is binding.generation.row
             and pending['lifetime'][4] is binding.operation_lock
             and type(index) is int and 0 <= index < len(pending['replies'])
             and wire is pending['replies'][index]
             and (pending['index'] == index or
                  phase == 'AFTER_DRAIN' and pending['index'] == index + 1)
             and phase in ('BEFORE_RESERVE', 'BEFORE_WRITE_CHECKPOINT', 'BEGIN_WRITE',
                           'DRAIN_PENDING', 'AFTER_DRAIN'),
             'RESOURCE_EXACT_ORIGINAL_WORLD_PROJECTION_REQUIRED')
        need(pending['reply_object'] is not None
             and len(pending['reply_object']) == len(pending['replies'])
             and all(a is b for a,b in zip(pending['reply_object'], pending['replies'])),
             'RESOURCE_WORLD_IMMUTABLE_BATCH_REQUIRED')
        return True

    def release_world_projection(self, writer):
        record = self._world_reads.pop(id(writer), None)
        if record is not None and record['cap'] is not None:
            self.store.retire_delivery(record['cap'])

    def world_projection_pending(self, writer, pending, wire):
        record = self._world_reads.get(id(writer))
        if record is None:
            need(not self.active and self._world_setup is not None
                 and self._world_setup[0].writer is writer,
                 'RESOURCE_EXPLICIT_INITIAL_WORLD_SETUP_REQUIRED')
            self.provider.delivery_current(self._world_setup[0])
            return
        need(record['pending'] is pending and wire is pending['replies'][pending['index']],
             'RESOURCE_EXACT_WORLD_PENDING_FRAME_REQUIRED')
        phase = 'DRAIN_PENDING' if pending.get('resource_drain_returned') else 'BEGIN_WRITE'
        row = self.store.participant_for_projection(record['cap'], 'RESOURCE', participant=pending,
            index=pending['index'], wire=wire, phase=phase)
        need(row == record['participant'], 'RESOURCE_WORLD_PARTICIPANT_CHANGED')

    def world_projection_drained(self, writer, pending):
        record = self._world_reads.get(id(writer))
        if record is None:
            return
        index = pending['index']
        self.store.participant_for_projection(record['cap'], 'RESOURCE', participant=pending,
            index=index, wire=pending['replies'][index], phase='AFTER_DRAIN')

    def resource_revision(self, writer):
        return self._participant(self._binding(writer))['document']['revision']

    def prepare_advance_spirit_lifecycle_locked(self, service, plan):
        """Original sealed Service plan only; subtract the persisted amount once."""
        from tools.local_original_session.buff_lifecycle import Service, Plan, _PLANS
        from tools.local_original_session import advance_spirit_math as math
        witness = _PLANS.get(plan)
        need(type(service) is Service and service is getattr(self.status.broker, '_buff_lifecycle', None)
             and service.owner is self and service.schema is self.skill_schema
             and type(plan) is Plan and witness is not None and witness[0] is service
             and witness[1] == service.fingerprint(plan) and service.pending.get(id(plan.binding.writer)) is plan
             and getattr(plan, 'resource_stage', None) is None
             and self._advance_spirit_operation is None and self._prepared_operation is None,
             'ADVANCE_SPIRIT_ORIGINAL_LIFECYCLE_PLAN_REQUIRED')
        binding = plan.binding
        events = tuple(e for e in plan.events if e.kind == 'buff_remove' and e.spell_id == 78)
        before_row = plan.before['document']['characters'][str(binding.uid)]
        after_row = plan.after['characters'][str(binding.uid)]
        need(len(events) == 1 and '78' in before_row['buffs'] and '78' not in after_row['buffs']
             and 'applied_hpmp' not in after_row
             and events[0].previous_expiry_ms == before_row['buffs']['78'],
             'ADVANCE_SPIRIT_ACTUAL_REMOVAL_REQUIRED')
        saved = before_row['applied_hpmp']['78']
        need(saved['base_key'] == self.store.capabilities['PROGRESSION'].key(binding.uid),
             'ADVANCE_SPIRIT_REMOVAL_SAVED_NAMESPACE_REQUIRED')
        self.provider.current(binding)
        need(self.status._states.get(id(binding.writer)) is plan.snapshot,
             'ADVANCE_SPIRIT_LIFECYCLE_SAME_SNAPSHOT_REQUIRED')
        before = self._participant(binding)
        previous = math.AppliedBonus(saved['hp'], saved['mp'])
        values = before['document']['values']
        change = math.replace_applied(maximum_hp=values['11'], maximum_mp=values['13'],
            current_hp=values['10'], current_mp=values['12'], previous=previous, following=math.AppliedBonus(0, 0))
        values = dict(values)
        values.update({'10': change.current_hp, '11': change.maximum_hp,
                       '12': change.current_mp, '13': change.maximum_mp})
        after = self.document.next_values(before['document'], values=values)
        operation = Operation(binding, plan.snapshot, before['document'], after, plan.request, plan.txid,
                              'BUFF_MAXIMUM', dict(kind='ADVANCE_SPIRIT_SAVED_REMOVAL'))
        stage = AdvanceSpiritLifecycleInput(weakref.ref(self), service, plan, operation, deepcopy(before),
            deepcopy(after), self.batch.digest(before), self.batch.digest(after),
            self.batch.digest(plan.before), self.batch.digest(plan.after))
        self._advance_spirit_operation = (operation, stage)
        self._prepared_operation = operation
        return stage

    def _require_advance_spirit_lifecycle(self, service, plan):
        from tools.local_original_session.buff_lifecycle import Service, Plan, _PLANS
        stage = getattr(plan, 'resource_stage', None)
        witness = _PLANS.get(plan)
        need(type(stage) is AdvanceSpiritLifecycleInput and stage.owner_ref() is self
             and stage.service is service and stage.plan is plan and type(service) is Service and type(plan) is Plan
             and service is getattr(self.status.broker, '_buff_lifecycle', None)
             and service.owner is self and service.schema is self.skill_schema
             and witness is not None and witness[0] is service and witness[1] == service.fingerprint(plan)
             and service.pending.get(id(plan.binding.writer)) is plan
             and plan.resource_before is stage.resource_before and plan.resource_after is stage.resource_after
             and stage.operation.binding is plan.binding and stage.operation.snapshot is plan.snapshot
             and stage.operation.before == stage.resource_before['document']
             and stage.operation.after == stage.resource_after and stage.operation.reason == 'BUFF_MAXIMUM'
             and stage.operation.txid == plan.txid and stage.operation.request == plan.request
             and self.batch.digest(stage.resource_before) == stage.resource_before_digest
             and self.batch.digest(stage.resource_after) == stage.resource_after_digest
             and self.batch.digest(plan.before) == stage.skill_before_digest
             and self.batch.digest(plan.after) == stage.skill_after_digest,
             'ADVANCE_SPIRIT_EXACT_LIFECYCLE_STAGE_REQUIRED')
        return stage

    def validate_advance_spirit_lifecycle_locked(self, service, plan):
        stage = self._require_advance_spirit_lifecycle(service, plan)
        self.provider.current(plan.binding)
        need(self._prepared_operation is stage.operation
             and self._advance_spirit_operation is not None
             and self._advance_spirit_operation[0] is stage.operation
             and self._advance_spirit_operation[1] is stage
             and self.status._states.get(id(plan.binding.writer)) is plan.snapshot
             and self.store.data['participants'][self.store.capabilities['RESOURCE'].key(plan.binding.uid)]
                 == stage.resource_before
             and self.store.data['participants'][self.store.capabilities['SKILL'].key(plan.binding.uid)] == plan.before,
             'ADVANCE_SPIRIT_LIFECYCLE_CURRENT_BEFORE_CHANGED')
        return True

    def discard_advance_spirit_lifecycle_locked(self, service, plan):
        # Same original owned stage only; cleanup never reacquires current/Store.
        issued = self._advance_spirit_operation
        stage = getattr(plan, 'resource_stage', None)
        if stage is None and issued is not None and type(issued[1]) is AdvanceSpiritLifecycleInput:
            if issued[1].service is service and issued[1].plan is plan:stage = issued[1]
        if stage is None:return
        need(type(stage) is AdvanceSpiritLifecycleInput and stage.owner_ref() is self
             and stage.service is service and stage.plan is plan,
             'ADVANCE_SPIRIT_FOREIGN_LIFECYCLE_DISCARD_REFUSED')
        if self._prepared_operation is stage.operation:
            self._prepared_operation = self._prepared_digest = None
        if issued is not None and issued[0] is stage.operation and issued[1] is stage:
            self._advance_spirit_operation = None

    def _project_advance_spirit_buff_commit(self, service, plan, parent, receipt, fields, wire):
        stage = self._require_advance_spirit_lifecycle(service, plan)
        op = stage.operation
        self.provider.current(op.binding)
        resource = self._participant(op.binding)
        need(receipt['phase'] == 'COMMITTED' and resource['document'] == stage.resource_after,
             'ADVANCE_SPIRIT_JOINT_RESOURCE_COMMIT_REQUIRED')
        expected = dict(op.snapshot.fields)
        expected.update({int(n): value for n,value in stage.resource_after['values'].items()})
        expected = self.shield_status_fields(op.binding, expected, plan.after)
        need(fields == expected and wire == self.status_module.frame(fields),
             'ADVANCE_SPIRIT_FULL_STATUS_AFTER_REQUIRED')
        permit = Projection(op, deepcopy(receipt), fields, resource['digest'], wire, plan, parent)
        self._projection = permit
        try:
            return self.status.project_resource_commit(op.binding.writer, op.binding.generation.row,
                op.snapshot, fields, op.after['revision'], permit)
        finally:self._projection = None

    def prepare_advance_spirit_cast_locked(self, binding, skill_before, shadow_after, result, *, now_ms):
        """Called only by the actual schema after original learned/cost admission."""
        from tools.local_original_session.buff_skill_document import SkillDocument
        from tools.local_original_session.progression_owner import ProgressionOwner
        from tools.local_original_session import advance_spirit_math as math
        context = self._advance_spirit_prepared
        need(type(context) is _AdvanceSpiritCastContext and context.owner is self
             and context.binding is binding and context.skill_before is skill_before
             and context.now_ms == now_ms and context.stage is None
             and type(self.skill_schema) is SkillDocument and self.skill_schema.core is self.core
             and self.skill_schema.plan_apply.__func__ is context.schema_function
             and context.schema_function.__code__ is context.schema_code,
             'ADVANCE_SPIRIT_ORIGINAL_ADMITTED_CAST_CONTEXT_REQUIRED')
        need(type(shadow_after) is dict and type(result) is dict
             and self.batch.digest(skill_before) == context.skill_before_digest
             and self.status._states.get(id(binding.writer)) is context.snapshot,
             'ADVANCE_SPIRIT_SAME_ADMITTED_SHADOW_REQUIRED')
        before_row = skill_before['characters'][str(binding.uid)]
        after_row = shadow_after['characters'][str(binding.uid)]
        events = [e for e in result['events'] if e['kind'] in ('buff_add','buff_refresh')
                  and e['spell_id'] == 78]
        need('78' in after_row['buffs'] and after_row['buffs']['78'] > now_ms and len(events) == 1,
             'ADVANCE_SPIRIT_ACTUAL_ACCEPTED_EVENT_REQUIRED')
        old = before_row.get('applied_hpmp')
        key = self.store.capabilities['PROGRESSION'].key(binding.uid)
        current = None
        if events[0]['kind'] == 'buff_refresh':
            # Fixed L1SkillUse1747-1752 refreshes the timer and continues before
            # Advance Spirit2854-2859; retain the original complete contribution.
            need('78' in before_row['buffs'] and before_row['buffs']['78'] > now_ms
                 and type(old) is dict and set(old) == {'78'},
                 'ADVANCE_SPIRIT_ACTIVE_REFRESH_SAVED_APPLIED_REQUIRED')
            saved = old['78']
            need(saved['base_key'] == key, 'ADVANCE_SPIRIT_SAVED_BASE_NAMESPACE_CHANGED')
            previous = following = math.AppliedBonus(saved['hp'], saved['mp'])
            base_revision, base_digest = saved['base_revision'], saved['base_digest']
        else:
            need('78' not in before_row['buffs'] and old is None,
                 'ADVANCE_SPIRIT_REMOVE_BEFORE_NEW_CAST_REQUIRED')
            previous = math.AppliedBonus(0, 0)
            progression = getattr(self, '_progression_owner', None)
            need(type(progression) is ProgressionOwner and progression.resource is self
                 and progression.broker is self.status.broker,
                 'ADVANCE_SPIRIT_CANONICAL_CURRENT_BASE_REQUIRED')
            current = progression.require_current_locked(binding)
            following = math.bonus_from_base(base_max_hp=current.base_max_hp, base_max_mp=current.base_max_mp)
            base_revision, base_digest = current.progression_revision, current.progression_digest
        debit, = [e for e in result['events'] if e['kind'] == 'resource_debit']
        values = context.resource_before['document']['values']
        change = math.replace_applied(maximum_hp=values['11'], maximum_mp=values['13'],
            current_hp=values['10']-debit['hp'], current_mp=values['12']-debit['mp'],
            previous=previous, following=following)
        stage = AdvanceSpiritCastInput(weakref.ref(self), binding, context.snapshot, current,
            key, base_revision, base_digest, previous, following, change,
            self.batch.digest(context.resource_before['document']), context.skill_before_digest,
            self.batch.digest(result), now_ms, shadow_after)
        context.stage = stage
        return stage.saved_record()

    def _validate_advance_spirit_cast(self, stage, binding, before, *, result, skill_after=None):
        need(type(stage) is AdvanceSpiritCastInput and stage.owner_ref() is self
             and stage.binding is binding and stage.snapshot is self.status._states.get(id(binding.writer))
             and self.batch.digest(before) == stage.resource_before_digest
             and self.batch.digest(result) == stage.result_digest,
             'ADVANCE_SPIRIT_SAME_COMPUTED_CAST_REQUIRED')
        key = self.store.capabilities['PROGRESSION'].key(binding.uid)
        need(key == stage.base_key, 'ADVANCE_SPIRIT_BASE_NAMESPACE_CHANGED')
        if stage.current is not None:
            from tools.local_original_session.progression_owner import ProgressionOwner
            progression = getattr(self, '_progression_owner', None)
            need(type(progression) is ProgressionOwner and progression.resource is self
                 and progression.broker is self.status.broker
                 and stage.current._owner is progression and stage.current._binding is binding,
                 'ADVANCE_SPIRIT_SAME_CURRENT_BASE_OWNER_REQUIRED')
            progression._anchors(binding)
            participant = self.store.data['participants'][key]
            need((participant['revision'], participant['digest']) == (stage.base_revision, stage.base_digest)
                 and participant['document']['base_max_hp'] == stage.current.base_max_hp
                 and participant['document']['base_max_mp'] == stage.current.base_max_mp,
                 'ADVANCE_SPIRIT_CURRENT_BASE_CHANGED')
        if skill_after is not None:
            need(skill_after == stage.skill_after_source
                 and skill_after['characters'][str(binding.uid)]['applied_hpmp'] == {'78': stage.saved_record()},
                 'ADVANCE_SPIRIT_FINAL_SAVED_RECORD_CHANGED')
        return True

    def enable_cast_stats_preview(self, stats):
        """Cold explicit owner opt-in; actual selected Stats supplies its Source seal."""
        from tools.local_original_session.combat_selected_stats import SelectedStatsSource
        need(self._cast_stats_enabled is None and type(stats) is SelectedStatsSource
             and stats is self._combat_stats and stats.owner is self
             and stats._cast_preview_source_memory()[0].ResourceOwner is type(self),
             'RESOURCE_CAST_STATS_ACTUAL_SELECTED_SOURCE_REQUIRED')
        self._cast_stats_enabled=stats

    def _cast_stats_payload(self, plan):
        from tools.local_original_session.combat_selected_stats import SelectedStatsSource
        stats=self._cast_stats_enabled
        need(type(stats) is SelectedStatsSource and stats is self._combat_stats
             and plan.stats_preview is not None,
             'RESOURCE_CAST_STATS_OWNED_PLAN_REQUIRED')
        return stats.cast_plan_stats_payload(plan.stats_preview)

    @contextmanager
    def _cast_stats_build(self, plan, spell_id):
        if self._cast_stats_enabled is None or spell_id not in (25,41):
            yield
            return
        need(self._cast_stats_plan is None and self._cast_stats_context is None,
             'RESOURCE_CAST_STATS_BUILD_REENTRY')
        self._cast_stats_plan=plan
        try:
            context=_CastStatsContext(self,plan,plan.operation,plan.operation.binding,
                plan.skill_before,plan.skill_after,plan.accepted_now_ms,object())
            self._cast_stats_context=context
            try:
                plan.stats_preview=self._cast_stats_enabled.preview_cast_context_locked(context.binding,context)
            finally:
                self._cast_stats_context=None
            yield
        except BaseException:
            self.skill_schema.release_cast_events(plan)
            self._prepared_operation=self._prepared_digest=None
            self._cast_stats_plan=None
            plan.phase='TERMINAL'
            raise
        finally:
            self._cast_stats_context=None

    def _clear_cast_stats_plan(self, plan):
        if self._cast_stats_plan is plan:
            self._cast_stats_plan=None
            self._cast_stats_context=None

    def plan_cast_locked(self, binding, *, txid, request, spell_id, target_uid, now_ms):
        """Server semantic action only after original target admission.

        This does not infer no-target=self or decode a raw UID. The original
        route remains disabled until that source-specific admission is closed.
        Costs come solely from the configured core.Rule and accepted snapshot.
        """
        self.provider.current(binding)
        self.require_hp_quiescent(binding.writer)
        need(self.active and self.skill_schema is not None, 'RESOURCE_SKILL_PARTICIPANT_REQUIRED')
        previous = self.store.lookup(binding, txid=txid, request_sha=self.batch.request_digest(request))
        if previous is not None:
            return previous  # Receipt only; no projection/re-debit/send.
        need(self._prepared_operation is None, 'RESOURCE_OPERATION_REENTRY_REFUSED')
        with self.store.lock:
            snapshot = self.status.current(binding.writer)
            before = self._participant(binding)
            skill = self.store.participant(binding, 'SKILL')
            self.skill_schema.validate(skill['document'])
            row = skill['document']['characters'].get(str(binding.uid))
            need(row is not None, 'RESOURCE_LEARNED_CHARACTER_REQUIRED')
            lifecycle=getattr(self.status.broker,'_buff_lifecycle',None)
            need(spell_id != 78 or lifecycle is not None, 'ADVANCE_SPIRIT_FULL_BUFF_REQUIRED')
            catalyst=self.plan_catalyst(binding,spell_id)if lifecycle is not None else None
            if lifecycle is not None:
                from tools.local_original_session.buff_skill_document import SkillDocument as BuffSkillDocument
                need(type(self.skill_schema)is BuffSkillDocument and lifecycle.schema is self.skill_schema,
                     'BUFF_EXACT_CONFIGURED_CAST_DOCUMENT_REQUIRED')
                need(self._catalyst_prepared is None,'CATALYST_PLAN_REENTRY_REFUSED')
                self._catalyst_prepared=catalyst
                advance_context = None
                if spell_id == 78:
                    need(self._advance_spirit_prepared is None and self._advance_spirit_operation is None,
                         'ADVANCE_SPIRIT_CAST_REENTRY_REFUSED')
                    method = self.skill_schema.plan_apply.__func__
                    advance_context = _AdvanceSpiritCastContext(self, binding, snapshot, before,
                        skill['document'], self.batch.digest(skill['document']), now_ms, method, method.__code__)
                    self._advance_spirit_prepared = advance_context
                try:
                    result,skill_after=self.skill_schema.plan_apply(skill['document'],binding,catalyst=catalyst,
                        command='cast',spell_id=spell_id,target_uid=target_uid,now_ms=now_ms,
                        expected_revision=row['revision'],resources=dict(hp=snapshot.fields[10],mp=snapshot.fields[12]),
                        **({'resource_owner': self} if advance_context is not None else {}))
                finally:
                    self._catalyst_prepared=None
                    if advance_context is not None:self._advance_spirit_prepared=None
                if advance_context is not None:
                    need(type(advance_context.stage) is AdvanceSpiritCastInput,
                         'ADVANCE_SPIRIT_SCHEMA_DID_NOT_PREPARE_RESOURCE')
            else:
                shadow = object.__new__(self.core.Store)
                shadow.__dict__ = dict(rules=self.skill_schema.rules, account=self.skill_schema.account,
                    rule_hash=self.skill_schema.rule_hash, data=deepcopy(skill['document']),
                    lock=self.store.lock, failed=False, _prepared_only=True)
                shadow._current = lambda: self.provider.current(binding)
                shadow._save = lambda data: setattr(shadow, 'data', self.skill_schema.validate(data))
                result = shadow.apply(binding.uid, command='cast', spell_id=spell_id, target_uid=target_uid,
                    now_ms=now_ms, expected_revision=row['revision'],
                    resources=dict(hp=snapshot.fields[10], mp=snapshot.fields[12]))
                skill_after=shadow.data
            self.require_exclusive(binding,skill_after,now_ms=now_ms)
            debit, = [event for event in result['events'] if event['kind'] == 'resource_debit']
            values = dict(before['document']['values'])
            values['10'] -= debit['hp']
            values['12'] -= debit['mp']
            advance = None if lifecycle is None or spell_id != 78 else advance_context.stage
            if advance is not None:
                need(skill_after is advance.skill_after_source, 'ADVANCE_SPIRIT_SAME_SCHEMA_AFTER_OBJECT_REQUIRED')
                self._validate_advance_spirit_cast(advance, binding, before['document'],
                    result=result, skill_after=skill_after)
                values.update({'10': advance.change.current_hp, '11': advance.change.maximum_hp,
                               '12': advance.change.current_mp, '13': advance.change.maximum_mp})
            after = self.document.next_values(before['document'], values=values)
            op = Operation(binding, snapshot, before['document'], after, request, txid, 'CAST_COST', result)
            changes = (self.batch.ParticipantChange('RESOURCE', before['revision'], before['digest'], after),
                       self.batch.ParticipantChange('SKILL', skill['revision'], skill['digest'], skill_after))
            fields = dict(snapshot.fields)
            fields.update({int(n): value for n, value in after['values'].items()})
            fields=self.shield_status_fields(binding,fields,skill_after)
            plan = CastPlan(op, changes, deepcopy(skill['document']), deepcopy(skill_after),
                            fields, self.status_module.frame(fields), now_ms,catalyst=catalyst,advance_spirit=advance)
            if advance is not None:self._advance_spirit_operation = (op, advance)
            self._prepared_operation = op
            with self._cast_stats_build(plan,spell_id):
                self._prepared_digest = self.plan_digest(plan)
                if lifecycle is not None:self.skill_schema.seal_cast_plan(plan,self)
                return plan

    def plan_digest(self, plan):
        op = plan.operation
        return self.batch.digest(dict(uid=op.binding.uid, txid=op.txid,
            request_sha=self.batch.request_digest(op.request), snapshot_revision=op.snapshot.revision,
            snapshot_wire_sha=hashlib.sha256(self.status_module.frame(op.snapshot.fields)).hexdigest(),
            before=op.before, after=op.after, semantic_result=op.semantic_result,
            skill_before=plan.skill_before, skill_after=plan.skill_after,
            changes=[dict(name=c.name, revision=c.expected_revision, digest=c.expected_digest,
                          document=c.document, markers=c.reward_markers) for c in plan.changes],
            status_fields=plan.status_fields, status_wire_sha=hashlib.sha256(plan.status_wire).hexdigest(),
            light_wire_sha=(None if self.cast_light_wire(plan)is None else hashlib.sha256(self.cast_light_wire(plan)[0]).hexdigest()),
            catalyst=(None if plan.catalyst is None else dict(recipe=plan.catalyst.recipe,item_uid=plan.catalyst.item_uid,
                before=plan.catalyst.before_inventory.hex(),after=plan.catalyst.after_inventory.hex(),
                wire=plan.catalyst.inventory_wire.hex(),revision=plan.catalyst.asset_revision)),
            accepted_now_ms=plan.accepted_now_ms,
            **({} if plan.stats_preview is None else {'stats_preview': self._cast_stats_payload(plan)}),
            **({} if plan.advance_spirit is None else {'advance_spirit': plan.advance_spirit.digest_payload()})))

    def validate_plan(self, plan):
        need(type(plan) is CastPlan and plan.phase == 'PLANNED'
             and plan.operation is self._prepared_operation
             and self.plan_digest(plan) == self._prepared_digest,
             'RESOURCE_SOURCE_CALLBACK_CHANGED_CAST_PLAN')
        self.provider.current(plan.operation.binding)
        if plan.advance_spirit is not None:
            need(self._advance_spirit_operation is not None
                 and self._advance_spirit_operation[0] is plan.operation
                 and self._advance_spirit_operation[1] is plan.advance_spirit,
                 'ADVANCE_SPIRIT_ISSUED_CAST_PLAN_REQUIRED')
            self._validate_advance_spirit_cast(plan.advance_spirit, plan.operation.binding,
                plan.operation.before, result=plan.operation.semantic_result, skill_after=plan.skill_after)
        if plan.stats_preview is not None:
            need(self._cast_stats_plan is plan and self._cast_stats_enabled is self._combat_stats,
                 'RESOURCE_CAST_STATS_CURRENT_PENDING_PLAN_REQUIRED')
            self._cast_stats_enabled.validate_cast_preview_precommit_memory_locked(plan.operation.binding,plan.stats_preview)
        return None

    def discard_cast_plan(self, plan):
        need(type(plan) is CastPlan and plan.operation is self._prepared_operation
             and plan.phase == 'PLANNED', 'RESOURCE_EXACT_UNCOMMITTED_CAST_PLAN')
        plan.phase = 'TERMINAL'
        self._clear_cast_stats_plan(plan)
        self._prepared_operation = self._prepared_digest = None
        if self._advance_spirit_operation is not None and self._advance_spirit_operation[0] is plan.operation:
            self._advance_spirit_operation = None

    def commit_cast_locked(self, plan, reply_parent):
        # One concrete parent controls all preflighted source frames and the
        # single global receipt. Missing/unknown response semantics refuse
        # before BatchStore.prepare or any resource debit.
        try:
            from tools.local_original_session.skill_cost_delivery import CostDelivery
            need(type(reply_parent) is CostDelivery and reply_parent.owner is self
                 and reply_parent.plan is plan, 'RESOURCE_EXACT_SOURCE_REPLY_PLAN_REQUIRED')
            self.validate_plan(plan)
            need(reply_parent.validate_precommit(plan) is None,
                 'RESOURCE_REPLY_PREFLIGHT_MUST_RAISE_NOT_BOOLEAN')
            receipt, delivery, result = self._commit_cast_plan(plan)
            reply_parent.bind_committed(receipt, delivery)
            return receipt, delivery, result

        except BaseException:
            self._clear_cast_stats_plan(plan)
            raise

    def _commit_cast_plan(self, plan):
        # Private owner commit primitive; tests exercise atomicity with this
        # explicitly. Actual route uses commit_cast_locked only after complete
        # concrete source response preflight, never this primitive directly.
        try:
            self.validate_plan(plan)
            op = plan.operation
            with self.store.lock:
                self.provider.current(op.binding)
                need(self.status.current(op.binding.writer) is op.snapshot
                     and self._participant(op.binding)['document'] == op.before
                     and self.store.participant(op.binding, 'SKILL')['document'] == plan.skill_before,
                     'RESOURCE_CAST_PLAN_SNAPSHOT_OR_DOCUMENT_CHANGED')
                need(plan.status_wire == self.status_module.frame(plan.status_fields)
                     and {str(n): plan.status_fields[n] for n in document_module.RESOURCE_FIELDS} == op.after['values'],
                     'RESOURCE_CAST_PLAN_STATUS_CHANGED')
                try:
                    with self.skill_schema.authorize_staged(op.binding, plan.skill_before, plan.skill_after):
                        receipt, delivery = self._commit_and_project(op, plan.changes, status_wire=plan.status_wire,catalyst=plan.catalyst)
                    plan.phase = 'COMMITTED'
                    return receipt, delivery, deepcopy(op.semantic_result)
                except BaseException:
                    plan.phase = 'TERMINAL'
                    raise

        finally:
            self._clear_cast_stats_plan(plan)

    def _commit_and_project(self, operation, changes, *, status_wire,catalyst=None):
        binding = operation.binding
        with self._staged_operation(operation):
            frame, revision = self.store.restore(binding)
            asset_changes=()
            if catalyst is not None:
                self.catalyst_current()
                need(type(catalyst)is CatalystDebit and catalyst.owner_ref()is self and catalyst.binding is binding
                     and frame==catalyst.before_inventory and revision==catalyst.asset_revision,
                     'CATALYST_PRECOMMIT_ASSET_PREIMAGE_CHANGED')
                asset_changes=(self.batch.QuantityChange(catalyst.item_uid,debit=catalyst.recipe[2]),)
            reservation = self.store.prepare(binding, txid=operation.txid, request=operation.request,
                catalog_digest=self.catalog_digest, expected_revision=revision,
                changes=asset_changes, participants=changes)
            receipt = self.store.commit(binding, reservation)
        need(receipt['phase'] == 'COMMITTED', 'RESOURCE_COMMIT_CONFIRMATION_REQUIRED')
        if catalyst is not None:
            frame,revision=self.store.restore(binding)
            need(frame==catalyst.after_inventory and revision==receipt['asset_revision'],
                 'CATALYST_JOINT_ASSET_READBACK_REQUIRED')
        resource = self._participant(binding)
        need(resource['document'] == operation.after, 'RESOURCE_COMMIT_READBACK_REQUIRED')
        fields = dict(operation.snapshot.fields)
        fields.update({int(n): value for n, value in operation.after['values'].items()})
        if getattr(self.status.broker,'_buff_lifecycle',None) is not None:
            fields=self.shield_status_fields(binding,fields,self.store.participant(binding,'SKILL')['document'])
        need(status_wire == self.status_module.frame(fields), 'RESOURCE_PREENCODED_STATUS_CHANGED')
        permit = Projection(operation, deepcopy(receipt), fields, resource['digest'], status_wire)
        self._projection = permit
        try:
            stats_plan=self._cast_stats_plan
            if stats_plan is not None and stats_plan.operation is operation:
                self._cast_stats_enabled.validate_cast_preview_commit_memory_locked(binding,stats_plan.stats_preview)
            delivery = self.status.project_resource_commit(binding.writer, binding.generation.row,
                operation.snapshot, fields, operation.after['revision'], permit)
        finally:
            self._projection = None
        return receipt, delivery

    def authorize_projection(self, writer, row, before, fields, revision, permit):
        need(type(permit) is Projection and self._projection is permit,
             'RESOURCE_EXACT_COMMIT_PROJECTION_PERMIT_REQUIRED')
        op = permit.operation
        self.provider.current(op.binding)
        need(op.binding.writer is writer and op.binding.generation.row is row
             and op.snapshot is before and permit.fields == fields
             and op.after['revision'] == revision, 'RESOURCE_PROJECTION_OPERATION_CHANGED')
        receipt = self.store.recover(op.binding, txid=op.txid, request=op.request)
        if permit.skill_plan is not None:
            plan,parent=permit.skill_plan,permit.skill_parent
            from tools.local_original_session.buff_lifecycle import _PLANS
            witness=_PLANS.get(plan)
            if getattr(plan, 'resource_stage', None) is not None:
                stage = self._require_advance_spirit_lifecycle(parent.service, plan)
                expected = dict(before.fields)
                expected.update({int(n): value for n,value in stage.resource_after['values'].items()})
                expected = self.shield_status_fields(op.binding, expected, plan.after)
                resource_key = self.store.capabilities['RESOURCE'].key(op.binding.uid)
                skill_key = self.store.capabilities['SKILL'].key(op.binding.uid)
                need(parent.owner is self and parent.plan is plan and op is stage.operation
                     and op.snapshot is plan.snapshot and receipt == permit.receipt
                     and receipt['phase'] == 'COMMITTED'
                     and receipt['participants'].get(resource_key) == permit.resource_digest
                     and receipt['participants'].get(skill_key) == self.batch.digest(plan.after)
                     and self._participant(op.binding)['document'] == stage.resource_after
                     and self.store.participant(op.binding, 'SKILL')['document'] == plan.after
                     and fields == expected and permit.wire == self.status_module.frame(fields),
                     'ADVANCE_SPIRIT_EXACT_JOINT_RECEIPT_PROJECTION_REQUIRED')
                return True
            need(witness is not None and witness[0]is parent.service and parent.plan is plan
                 and parent.owner is self and witness[1]==parent.service.fingerprint(plan)
                 and op.snapshot is plan.snapshot and receipt==permit.receipt
                 and receipt['phase']=='COMMITTED' and op.after==op.before
                 and self._participant(op.binding)['document']==op.after
                 and self.store.participant(op.binding,'SKILL')['document']==plan.after
                 and fields==self.shield_status_fields(op.binding,dict(before.fields),plan.after)
                 and permit.wire==self.status_module.frame(fields),'SHIELD_EXACT_SKILL_RECEIPT_PROJECTION')
            return True
        need(receipt == permit.receipt and receipt['phase'] == 'COMMITTED'
             and receipt['participants'].get('RESOURCE:' + str(op.binding.uid)) == permit.resource_digest
             and self._participant(op.binding)['document'] == op.after,
             'RESOURCE_EXACT_DURABLE_PROJECTION_RECEIPT_REQUIRED')
        return True

    def projection_installed(self, writer, delivery, permit):
        need(self._projection is permit and delivery.resource_context is permit,
             'RESOURCE_PROJECTION_INSTALLATION_CHANGED')
        self.validate_projection(writer, delivery.result.after)
        self._deliveries[id(writer)] = delivery
        self._hp_edges.setdefault(id(writer), []).append(delivery)
        self._hp_receipts[id(delivery)] = _HPLineage(delivery,delivery.result,delivery.result.before,
            delivery.result.after,writer,delivery.row,permit.operation.txid,permit.operation.request)

    def mark_delivery(self, writer, delivery, state):
        need(self._deliveries.get(id(writer)) is delivery, 'RESOURCE_CURRENT_STATUS_DELIVERY_REQUIRED')
        op = delivery.resource_context.operation
        need(op.reason not in ('CAST_COST','CONSUMABLE_HEAL'), 'RESOURCE_COST_PARENT_REPLY_BATCH_REQUIRED')
        self.provider.current(op.binding)
        self.validate_projection(writer, delivery.result.after)
        self.store.delivery(op.binding, txid=op.txid, request=op.request, state=state)

    def _issued_hp_delivery(self, writer, delivery):
        record=self._hp_receipts.get(id(delivery))
        need(type(delivery) is self.status_module._Delivery and type(record) is _HPLineage
             and record.delivery is delivery and record.writer is writer and delivery.writer is writer
             and delivery.row is record.row and delivery.result is record.result
             and delivery.result.before is record.before and delivery.result.after is record.after
             and any(item is delivery for item in self._hp_edges.get(id(writer), ())),
             'RESOURCE_EXACT_OWNER_ISSUED_HP_PREDECESSOR_REQUIRED')
        return record

    def require_hp_quiescent(self, writer):
        need(self._hp_effect is None, 'RESOURCE_HP_EFFECT_PENDING')
        history = self._hp_edges.get(id(writer), ())
        if history:
            last=history[-1]
            record=self._issued_hp_delivery(writer,last)
            need(last.phase == 'DRAINED','RESOURCE_COMMITTED_STATUS_UNDELIVERED')
            receipt=self.store.recover(self._binding(writer),txid=record.txid,request=record.request)
            need(receipt['phase'] == 'COMMITTED' and receipt['delivery'] == 'DRAINED',
                 'RESOURCE_COMMITTED_RECEIPT_UNDELIVERED')

    def hp_lineage_ready(self, writer, snapshot, previous):
        self.require_hp_quiescent(writer)
        self.validate_projection(writer, snapshot)
        if previous is not None:
            record=self._issued_hp_delivery(writer,previous)
            start=record.after
            need(previous.phase == 'DRAINED','RESOURCE_HP_LINEAGE_UNDRAINED')
        else:start=self._hp_baselines.get(id(writer))
        need(start is not None,'RESOURCE_HP_LINEAGE_BASELINE_REQUIRED')
        if start is snapshot:return True
        for delivery in self._hp_edges.get(id(writer), ()):
            record=self._issued_hp_delivery(writer,delivery)
            if record.before is start:
                need(delivery.phase == 'DRAINED', 'RESOURCE_HP_LINEAGE_UNDRAINED')
                start=record.after
                if start is snapshot:return True
        raise ValueError('RESOURCE_HP_LINEAGE_EXACT_BRIDGE_REQUIRED')

    def _verified_hp_producer(self, writer, row, before, life_context):
        from tools.local_original_session import npc_player_hit, player_life
        broker = self.status.broker
        binding = self.provider.bind_selected(writer)
        self.provider.current(binding)
        need(binding.generation.row is row and binding.operation_lock is row['operation_lock']
             and self.status._states.get(id(writer)) is before,
             'RESOURCE_HP_EXACT_OWNED_ROW_SNAPSHOT')
        self.require_hp_quiescent(writer)
        if life_context is None:
            service = broker._npc_player_hit
            need(type(service) is npc_player_hit.Service and service.status is self.status
                 and service is broker.realm._npc_player_hit, 'RESOURCE_HP_EXACT_NPC_PRODUCER')
            producer = service.operation_for(writer)
            need(type(producer) is npc_player_hit._Prepared and producer.context.snapshot is before
                 and producer.phase == 'ATTACK_DRAINED' and producer.attack_transport == 'DRAINED'
                 and producer.hp_operation is None and before.current_hp > 1
                 and service.validate_locked(writer, producer.context) is row,
                 'RESOURCE_HP_VALIDATED_DRAINED_NPC_ATTACK')
            context, value, reason = producer.context, before.current_hp - 1, 'HP_EFFECT'
        else:
            service = broker._player_life
            need(type(service) is player_life.Service and service.status is self.status
                 and type(life_context) is player_life.Context
                 and service.current_locked(writer, life_context) is row,
                 'RESOURCE_HP_EXACT_LIFE_PRODUCER')
            producer = service._cycles.get(id(writer))
            need(type(producer) is player_life._Cycle and producer.context is life_context
                 and not producer.terminal, 'RESOURCE_HP_EXACT_LIFE_CYCLE')
            if producer.stage == 'PREPARED':
                need(before is life_context.snapshot and before.current_hp == 1
                     and (service.policy.label != player_life.NPC_POLICY_LABEL
                          or producer.npc_attack is not None and producer.npc_attack.attack_transport == 'DRAINED'),
                     'RESOURCE_HP_LIFE_ZERO_PRECONDITION')
                value = 0
            else:
                need(producer.stage == 'INIT_DRAINED' and before.current_hp == 0
                     and producer.status is self.status._life_deliveries[id(writer)][-1]
                     and producer.status.phase == 'DRAINED', 'RESOURCE_HP_LIFE_RESTORE_PRECONDITION')
                value = before.maximum_hp
            context, reason = life_context, 'PLAYER_LIFE'
        return binding, service, producer, context, value, reason

    def commit_hp_locked(self, writer, row, before, *, current_hp, maximum_hp, life_context):
        with self.store.lock:
            proof = self._verified_hp_producer(writer, row, before, life_context)
            binding, service, producer, context, value, reason = proof
            need(current_hp == value and maximum_hp == before.maximum_hp
                 and self._prepared_operation is None and self._hp_producer is None,
                 'RESOURCE_HP_COMPUTED_TRANSITION_REQUIRED')
            participant = self._participant(binding)
            values = dict(participant['document']['values']); values['10'] = value
            after = self.document.next_values(participant['document'], values=values)
            # Existing actual producer and canonical next revision identify the
            # local once operation. Neither client ID nor a new nonce is used.
            txid = 'hp-' + str(binding.uid) + '-' + str(after['revision'])
            request = self.batch.encoded(dict(kind=reason, uid=binding.uid,
                revision=participant['document']['revision'], before=value + 1 if reason == 'HP_EFFECT' else before.current_hp,
                after=value, generation=binding.generation_key))
            need(self.store.lookup(binding, txid=txid, request_sha=self.batch.request_digest(request)) is None,
                 'RESOURCE_HP_RECEIPT_RECOVERY_REQUIRED')
            op = Operation(binding, before, participant['document'], after, request, txid, reason)
            self._prepared_operation = op
            self._hp_producer = (op, proof)
            fields = dict(before.fields); fields[10] = value
            try:
                receipt, delivery = self._commit_and_project(op,
                    (self.batch.ParticipantChange('RESOURCE', participant['revision'], participant['digest'], after),),
                    status_wire=self.status_module.frame(fields))
                delivery.life_context = life_context
                parent = HPEffectDelivery(self, binding, service, producer, context, delivery, receipt)
                self._hp_effect = parent
                try: parent.open()
                except BaseException as error:
                    parent.failed(error);raise
                return delivery
            finally:
                self._hp_producer = None
                if self._prepared_operation is op: self._prepared_operation = None

    def new_life_baseline_locked(self, writer, life, cycle):
        from tools.local_original_session import player_life
        binding = self.provider.bind_selected(writer)
        self.provider.current(binding)
        need(type(life) is player_life.Service and life is self.status.broker._player_life
             and life.status is self.status and type(cycle) is player_life._Cycle
             and life._cycles.get(id(writer)) is cycle and cycle.stage == 'NEW_LIFE'
             and not cycle.terminal and cycle.status.phase == 'DRAINED'
             and life.token(writer) is cycle.new_token and cycle.new_token is not None
             and self.status._states.get(id(writer)) is cycle.status.result.after
             and cycle.status.result.after.current_hp == cycle.context.snapshot.maximum_hp,
             'RESOURCE_EXACT_DRAINED_NEW_LIFE_BASELINE_REQUIRED')
        self.require_hp_quiescent(writer)
        before = self.status.current(writer)
        self.validate_projection(writer, before)
        # Service remains the sole Snapshot issuer. No balance/CAS mutation.
        need(self._hp_baseline_projection is None,'RESOURCE_NEW_LIFE_PROJECTION_REENTRY')
        self._hp_baseline_projection=(writer,before,cycle)
        try: snapshot = self.status.install_resource_new_life(self, writer, before, cycle)
        finally: self._hp_baseline_projection=None
        self._hp_baselines[id(writer)] = snapshot
        for old in self._hp_edges.pop(id(writer), ()):
            self._hp_receipts.pop(id(old),None)
        return snapshot

    def fail_active_hp(self, writer, error):
        need(isinstance(error,BaseException),'RESOURCE_HP_ACTUAL_EXCEPTION_REQUIRED')
        parent=self._hp_effect
        try:
            if parent is not None and parent.writer is writer:parent.failed(error)
        finally:
            reader=self._hp_read
            if reader is not None and reader.writer is writer:reader.retire()

    def release_hp_selection(self, writer):
        plan=self._cast_stats_plan
        if plan is not None and plan.operation.binding.writer is writer:
            self._clear_cast_stats_plan(plan)
        self._shield_world_clock.pop(id(writer),None)
        if self._hp_read is not None and self._hp_read.writer is writer:
            self._hp_read.retire()
        if self._hp_effect is not None and self._hp_effect.writer is writer:
            self._hp_effect.retire()
        for old in self._hp_edges.pop(id(writer), ()):
            self._hp_receipts.pop(id(old),None)
        self._hp_baselines.pop(id(writer), None)

    def begin_hp_source_read(self, writer, row, wire, *, npc=None, lethal=None, life_delivery=None):
        from tools.local_original_session import npc_player_hit, npc_player_lethal, player_life
        if life_delivery is not None and self._hp_effect is not None:
            parent=self._hp_effect
            parent.attach_death(writer,row,wire,life_delivery)
            return parent
        self.require_hp_quiescent(writer)
        need(self._hp_read is None and sum(v is not None for v in (npc,lethal,life_delivery)) == 1,
             'RESOURCE_HP_SOURCE_READ_SINGLE_PRODUCER')
        broker=self.status.broker
        binding=self.provider.bind_selected(writer);self.provider.current(binding)
        need(binding.generation.row is row and binding.operation_lock is row['operation_lock'],
             'RESOURCE_HP_SOURCE_READ_OWNED_ROW')
        if npc is not None:
            service=broker._npc_player_hit
            need(type(service) is npc_player_hit.Service and type(npc) is npc_player_hit._Prepared
                 and service.operation_for(writer) is npc and npc.phase == 'ATTACK'
                 and npc.attack_transport == 'PREPARED', 'RESOURCE_HP_NPC_SOURCE_READ')
            service.validate_delivery(writer,row,wire,npc)
            snapshot=npc.context.snapshot;operation=npc
        elif lethal is not None:
            service=broker._npc_player_lethal
            need(type(service) is npc_player_lethal.Service and type(lethal) is npc_player_lethal._Attack,
                 'RESOURCE_HP_LETHAL_SOURCE_READ')
            service.validate(writer,row,wire,lethal,'PREPARED')
            snapshot=lethal.context.life_context.snapshot;operation=lethal
        else:
            service=broker._player_life
            need(type(service) is player_life.Service and type(life_delivery) is player_life._Delivery,
                 'RESOURCE_HP_LIFE_SOURCE_READ')
            service.validate(writer,row,wire,life_delivery,'PREPARED')
            snapshot=self.status.current_player_life(writer,life_delivery.context);operation=life_delivery
        need(self.status._states.get(id(writer)) is snapshot,'RESOURCE_HP_SOURCE_CURRENT_SNAPSHOT')
        participant=self._participant(binding)
        parent=object.__new__(HPProducerRead);parent.writer=writer;parent.cap=None
        _HP_READS[parent]=_HPReadProof(self,binding,service,operation,snapshot,wire,
            self.batch.encoded({'RESOURCE':participant}))
        self._hp_read=parent
        try:
            parent.cap=self.store.open_projection_read(binding,self.register_delivery_dispatcher(),parent,
                ('RESOURCE',),(wire,))
            return parent
        except BaseException:
            parent.retire();raise

    def bind_delivery_dispatcher(self, root_composite):
        """Cold root-owned routing; this owner never closes the composite."""
        from tools.local_original_session.broker import PersistentBroker
        broker = self.status.broker
        def cold():
            fields = vars(root_composite)
            need(isinstance(root_composite, self.batch.DeliveryOwner)
                 and fields.get('store') is self.store
                 and fields.get('provider') is self.provider
                 and fields.get('resource_owner') is self,
                 'RESOURCE_EXACT_ROOT_DELIVERY_RUNTIME_REQUIRED')
            need(type(self.store) is self.batch.BatchStore
                 and type(self.provider) is self.batch.BrokerProvider
                 and type(self.status) is self.status_module.Service
                 and type(broker) is PersistentBroker
                 and self.store.provider is self.provider
                 and self.provider.broker is broker
                 and self.provider.source_store is broker._inventory_store
                 and broker._canonical_provider is self.provider
                 and broker.realm._canonical_provider is self.provider
                 and broker._hp_status is self.status
                 and broker._hp_resource_owner is self
                 and broker.realm._hp_resource_owner is self,
                 'RESOURCE_SAME_ATTACHED_DELIVERY_RUNTIME_REQUIRED')
            need(not broker._closing and not broker.failure.is_set()
                 and ((not broker._started and not broker._tasks and not broker.realm.registry._sessions
                       and not any(broker._claims.values())) or _scope_construction_current(broker))
                 and not self.status.closed and not self.status._states
                 and not self.status._world and not self.status._operations
                 and self.provider._scope is None and self.provider._bound is None
                 and not self.active and self._arming is None
                 and self._operation is None and self._projection is None
                 and self._prepared_operation is None and self._prepared_digest is None
                 and not self._deliveries and self._delivery_active is None
                 and self._world_setup is None and not self._world_reads
                 and not self.store.failed and not self.store.closed
                 and self.store.active is None and not self.store._delivery_caps,
                 'RESOURCE_COLD_DELIVERY_BOOTSTRAP_REQUIRED')
        with self.store.lock:
            cold()
            need(self._delivery_dispatcher is None and self.store._delivery_owner is None,
                 'RESOURCE_SINGLE_DELIVERY_DISPATCHER_REQUIRED')
            self.store.register_delivery_owner(root_composite)
            cold()
            need(self.store._delivery_owner is root_composite,
                 'RESOURCE_REGISTERED_DELIVERY_DISPATCHER_CHANGED')
            self._delivery_dispatcher = root_composite
        return root_composite

    def register_delivery_dispatcher(self):
        if self._delivery_dispatcher is not None:
            return self._delivery_dispatcher
        owner = self
        need(hasattr(self.batch, 'DeliveryOwner') and hasattr(self.store, 'open_delivery'),
             'RESOURCE_CANONICAL_PENDING_DELIVERY_PORT_UNAVAILABLE')
        class Dispatcher(self.batch.DeliveryOwner):
            def validate_operation(self, parent, binding, **context):
                return owner.validate_operation(parent, binding, **context)

            def validate_projection_read(self, parent, binding, **context):
                return owner.validate_projection_read(parent, binding, **context)
        dispatcher = Dispatcher()
        self.store.register_delivery_owner(dispatcher)
        self._delivery_dispatcher = dispatcher
        return dispatcher

    def validate_operation(self, parent, binding, *, txid, request, receipt,
                           participant, index, wire, phase):
        if getattr(self.status.broker,'_buff_lifecycle',None) is not None:
            from tools.local_original_session.buff_lifecycle import Delivery as BuffLifecycleDelivery
            if type(parent) is BuffLifecycleDelivery:
                need(parent.owner is self and self._delivery_active is parent,
                     'BUFF_EXACT_SINGLE_OWNER_PARENT_REQUIRED')
                return parent.validate_memory(binding,txid=txid,request=request,receipt=receipt,
                    participant=participant,index=index,wire=wire,phase=phase)
        healing = getattr(self.status.broker,'_consumable_healing',None)
        if healing is not None:
            from tools.local_original_session.consumable_delivery import HealingDelivery
            if type(parent) is HealingDelivery:
                need(parent.owner is self and self._delivery_active is parent and parent.batch is healing,
                     'HEALING_EXACT_SINGLE_OWNER_PARENT_REQUIRED')
                return parent.validate_memory(binding,txid=txid,request=request,receipt=receipt,
                    participant=participant,index=index,wire=wire,phase=phase)
        book = getattr(self.status.broker, '_book_learning', None)
        if book is not None:
            from tools.local_original_session.spell_book_delivery import BookDelivery
            if type(parent) is BookDelivery:
                need(parent.owner is self and self._delivery_active is parent and parent.batch is book,
                     'BOOK_EXACT_SINGLE_OWNER_PARENT_REQUIRED')
                return parent.validate_memory(binding, txid=txid, request=request, receipt=receipt,
                    participant=participant, index=index, wire=wire, phase=phase)
        if type(parent) is HPEffectDelivery:
            return parent.validate_memory(binding, txid=txid, request=request, receipt=receipt,
                participant=participant, index=index, wire=wire, phase=phase)
        # ITEM invokes this pure owner callback inside its constrained delivery
        # capability. Never call provider.current/store/parent.current here.
        from tools.local_original_session.skill_cost_delivery import CostDelivery
        need(type(parent) is CostDelivery and self._delivery_active is parent
             and parent.owner is self and parent.binding is binding,
             'RESOURCE_CURRENT_CONCRETE_PARENT_OPERATION_REQUIRED')
        parent.validate_memory(binding, txid=txid, request=request, receipt=receipt,
            participant=participant, index=index, wire=wire, phase=phase)
        snapshot = self.status._states.get(id(binding.writer))
        need(type(snapshot) is self.status_module.Snapshot
             and snapshot._service is self.status and not self.status.closed
             and self.status._profile is self.status.broker.realm._self_fields
             and dict(self.status._profile) == self.status._profile_fields
             and parent.status_delivery is not None and snapshot is parent.status_delivery.result.after
             and snapshot.fields == parent.plan.status_fields,
             'RESOURCE_PARENT_RAW_STATUS_PROJECTION_CHANGED')
        return True

    def release_delivery(self, writer, delivery):
        # Cleanup may occur outside the owned scope. If WRITE_ATTEMPTED cannot
        # be changed under a genuine current binding, retain that durable phase
        # for explicit fresh-owner UNKNOWN recovery; never mark it DRAINED.
        if delivery.phase == 'WRITE_ATTEMPTED':
            try:
                self.mark_delivery(writer, delivery, 'UNKNOWN')
            except (ValueError, RuntimeError):
                pass
        if self._deliveries.get(id(writer)) is delivery:
            self._deliveries.pop(id(writer))


@dataclass(frozen=True)
class _HPDeliveryProof:
    owner: object
    binding: object
    service: object
    producer: object
    context: object
    delivery: object
    receipt_raw: bytes
    resource_raw: bytes
    wire: bytes
    frames: tuple
    parts: object

_HP_ISSUED = weakref.WeakKeyDictionary()
_HP_DEATH_PARTS = weakref.WeakKeyDictionary()

class HPEffectDelivery:
    """One actual validated HP producer, one canonical receipt, one full status."""
    def __init__(self, owner, binding, service, producer, context, delivery, receipt):
        need(owner._hp_producer is not None and owner._hp_producer[1][2] is producer,
             'RESOURCE_HP_DELIVERY_PRIVATE_PRODUCER_REQUIRED')
        self.owner, self.binding, self.writer = owner, binding, binding.writer
        self.delivery, self.cap = delivery, None
        self.phase, self.failure, self.index = 'OPENING', None, 0
        frames=(delivery.wire,)
        if delivery.life_context is not None and delivery.result.after.current_hp == 0:
            from tools.local_original_session import player_life_codec
            frames += (player_life_codec.death(binding.uid),)
        self.parts=[delivery]+[None]*(len(frames)-1)
        _HP_ISSUED[self] = _HPDeliveryProof(owner,binding,service,producer,context,delivery,
            owner.batch.encoded(receipt),owner.batch.encoded(delivery.resource_context.operation.after),delivery.wire,frames,self.parts)

    def proof(self):
        proof = _HP_ISSUED.get(self)
        need(type(proof) is _HPDeliveryProof and proof.owner._hp_effect is self
             and self.owner is proof.owner and self.binding is proof.binding
             and self.writer is proof.binding.writer and self.delivery is proof.delivery
             and self.delivery.wire is proof.wire
             and self.parts is proof.parts and len(self.parts) == len(proof.frames)
             and self.parts[0] is proof.delivery
             and (len(proof.frames) == 1 or self.parts[1] is _HP_DEATH_PARTS.get(self)),
             'RESOURCE_HP_EXACT_ISSUED_PARENT_REQUIRED')
        return proof

    def open(self):
        p=self.proof();owner=p.owner
        self.cap=owner.store.open_delivery(p.binding,owner.register_delivery_dispatcher(),self,
            txid=self.delivery.resource_context.operation.txid,
            request=self.delivery.resource_context.operation.request,
            receipt=json.loads(p.receipt_raw),frames=p.frames)
        self.phase='PREPARED'

    def validate_memory(self,binding,*,txid,request,receipt,participant,index,wire,phase):
        p=self.proof();op=p.delivery.resource_context.operation
        need(binding is p.binding and type(index) is int and 0 <= index < len(p.frames)
             and index == self.index and wire is p.frames[index] and txid == op.txid and request == op.request
             and p.owner.batch.encoded(receipt) == p.receipt_raw
             and (participant is self.parts[index] and participant is not None
                  or participant is None and self.phase == 'OPENING' and index == 0)
             and p.owner.status._states.get(id(self.writer)) is p.delivery.result.after,
             'RESOURCE_HP_FIXED_RECEIPT_PARTICIPANT_REQUIRED')
        if phase == 'UNKNOWN':
            need(self.phase == 'FAILING' and isinstance(self.failure,BaseException),
                 'RESOURCE_HP_ACTUAL_FAILURE_REQUIRED')
        else:
            need(phase in ('BEFORE_RESERVE','BEFORE_WRITE_CHECKPOINT','BEGIN_WRITE','DRAIN_PENDING','AFTER_DRAIN'),
                 'RESOURCE_HP_DELIVERY_PHASE_REQUIRED')
        return True

    def validate_projection(self,snapshot):
        p=self.proof()
        need(snapshot is p.delivery.result.after and snapshot._service is p.owner.status
             and snapshot.fields == p.delivery.resource_context.fields,
             'RESOURCE_HP_EXACT_CURRENT_PROJECTION_REQUIRED')
        return True

    def check(self,phase):
        p=self.proof()
        resource=p.owner.store.participant_for_delivery(self.cap,'RESOURCE',participant=self.parts[self.index],
            index=self.index,wire=p.frames[self.index],phase=phase)
        need(p.owner.batch.encoded(resource['document']) == p.resource_raw,
             'RESOURCE_HP_PENDING_CANONICAL_RESOURCE_CHANGED')
        actual=p.owner.store.receipt_for_delivery(self.cap,participant=self.parts[self.index],index=self.index,wire=p.frames[self.index],phase=phase)
        expected=json.loads(p.receipt_raw);expected['delivery']=actual['delivery']
        need(actual == expected,'RESOURCE_HP_PENDING_RECEIPT_CHANGED')

    def reserve(self):
        need(self.phase == 'PREPARED','RESOURCE_HP_SINGLE_RESERVATION_REQUIRED')
        self.check('BEFORE_RESERVE');self.phase='RESERVED'

    def attempt(self):
        need(self.phase == 'RESERVED','RESOURCE_HP_SINGLE_WRITE_REQUIRED')
        p=self.proof()
        p.owner.store.mark_delivery(self.cap,participant=self.parts[self.index],index=self.index,wire=p.frames[self.index],
            phase='BEGIN_WRITE',state='WRITE_ATTEMPTED')
        self.phase='WRITE_ATTEMPTED'

    def drain_returned(self):
        need(self.phase == 'WRITE_ATTEMPTED','RESOURCE_HP_PENDING_DRAIN_REQUIRED')
        self.check('DRAIN_PENDING')

    def drained(self):
        p=self.proof()
        p.owner.store.mark_delivery(self.cap,participant=self.parts[self.index],index=self.index,wire=p.frames[self.index],
            phase='AFTER_DRAIN',state='DRAINED')
        self.index+=1
        if self.index == len(p.frames):
            self.phase='DRAINED';self.retire()
        else:self.phase='BETWEEN'

    def attach_death(self,writer,row,wire,part):
        from tools.local_original_session import player_life
        p=self.proof()
        need(self.phase == 'BETWEEN' and self.index == 1 and len(p.frames) == 2
             and writer is self.writer and row is p.binding.generation.row
             and type(part) is player_life._Delivery and part.kind == 'DEATH'
             and part.context is p.context and wire == p.frames[1]
             and part.wire is wire and self.parts[1] is None,
             'RESOURCE_HP_EXACT_ZERO_DEATH_CONTINUATION')
        p.service.validate(writer,row,wire,part,'PREPARED')
        # Source-created bytes may be equal rather than the preencoded object;
        # ITEM's exact cap wire is the fixed preencoded image.
        need(wire == p.frames[1],'RESOURCE_HP_FIXED_DEATH_WIRE')
        self.parts[1]=part
        _HP_DEATH_PARTS[self]=part
        self.phase='RESERVED'

    def consume(self,phase):
        if phase == 'BEGIN_WRITE':self.attempt()
        elif phase == 'DRAIN_PENDING':self.drain_returned()
        elif phase == 'AFTER_DRAIN':self.drained()
        else:raise ValueError('RESOURCE_HP_DEATH_PHASE_REQUIRED')

    def failed(self,error):
        if self.phase in ('DRAINED','TERMINAL'):return
        self.failure=error;self.phase='FAILING'
        try:
            if self.cap is not None:
                p=self.proof()
                try:p.owner.store.terminal_unknown(self.cap,index=self.index,wire=p.frames[self.index],participant=self.parts[self.index])
                except BaseException:pass # Preserve original send/cancel, durable ambiguity.
        finally:
            self.phase='TERMINAL';self.retire()

    def retire(self):
        p=_HP_ISSUED.pop(self,None)
        _HP_DEATH_PARTS.pop(self,None)
        if p is None:return
        try:
            if self.cap is not None:p.owner.store.retire_delivery(self.cap)
        finally:
            if p.owner._hp_effect is self:p.owner._hp_effect=None
            p.owner._deliveries.pop(id(self.writer),None)
            p.owner.status._resource_deliveries.pop(id(self.writer),None)
            p.delivery.resource_context=None
            self.owner=self.binding=self.writer=self.delivery=self.cap=self.failure=None
            self.parts=[]


@dataclass(frozen=True)
class _HPReadProof:
    owner: object
    binding: object
    service: object
    operation: object
    snapshot: object
    wire: bytes
    participants_raw: bytes

_HP_READS=weakref.WeakKeyDictionary()

class HPProducerRead:
    def __init__(self,*args,**kwargs):raise TypeError('actual HP source operation issuer only')
    def proof(self):
        p=_HP_READS.get(self)
        need(type(p) is _HPReadProof and p.owner._hp_read is self and self.writer is p.binding.writer
             and p.owner.status._states.get(id(self.writer)) is p.snapshot,
             'RESOURCE_HP_EXACT_SOURCE_READ_PARENT')
        return p
    def validate_snapshot(self,snapshot):
        need(self.proof().snapshot is snapshot,'RESOURCE_HP_FIXED_SOURCE_READ_SNAPSHOT')
        return True
    def validate_memory(self,binding,*,participants,index,wire,phase):
        p=self.proof()
        need(binding is p.binding and type(index) is int and index == 0 and wire is p.wire
             and p.owner.batch.encoded(participants) == p.participants_raw
             and phase in ('BEFORE_RESERVE','BEFORE_WRITE_CHECKPOINT','BEGIN_WRITE','DRAIN_PENDING','AFTER_DRAIN'),
             'RESOURCE_HP_FIXED_SOURCE_READ_PHASE')
        return True
    def consume(self,phase):
        p=self.proof()
        row=p.owner.store.participant_for_projection(self.cap,'RESOURCE',participant=self,
            index=0,wire=p.wire,phase=phase)
        need(p.owner.batch.encoded({'RESOURCE':row}) == p.participants_raw,
             'RESOURCE_HP_SOURCE_CANONICAL_PREIMAGE_CHANGED')
    def retire(self):
        p=_HP_READS.pop(self,None)
        if p is None:return
        try:
            if self.cap is not None:p.owner.store.retire_delivery(self.cap)
        finally:
            if p.owner._hp_read is self:p.owner._hp_read=None
            self.cap=self.writer=None


@dataclass(frozen=True)
class _HPLineage:
    delivery: object
    result: object
    before: object
    after: object
    writer: object
    row: object
    txid: str
    request: bytes


def _scope_construction_current(broker):
    # Source/module selection and the actual live token belong to root.
    import sys,types
    scope=sys.modules.get('character_scope')
    need(type(scope) is types.ModuleType,'SCOPE_CONSTRUCTION_SELECTED_SOURCE_REQUIRED')
    method=getattr(scope,'scope_construction_current',None)
    need(type(method) is types.FunctionType and method.__globals__ is vars(scope),
         'SCOPE_CONSTRUCTION_EXACT_SOURCE_FUNCTION_REQUIRED')
    result=method(broker)
    need(type(result) is bool,'SCOPE_CONSTRUCTION_EXACT_CURRENT_RESULT_REQUIRED')
    return result


@dataclass(eq=False)
class _AdvanceSpiritCastContext:
    owner: object
    binding: object
    snapshot: object
    resource_before: object
    skill_before: object
    skill_before_digest: str
    now_ms: int
    schema_function: object
    schema_code: object
    stage: object = None


@dataclass(frozen=True, slots=True)
class AdvanceSpiritCastInput:
    """Computed numeric input; authority is the original owner-held cast context."""
    owner_ref: object
    binding: object
    snapshot: object
    current: object
    base_key: str
    base_revision: int
    base_digest: str
    previous: object
    following: object
    change: object
    resource_before_digest: str
    skill_before_digest: str
    result_digest: str
    accepted_now_ms: int
    skill_after_source: object

    def digest_payload(self):
        return dict(saved=self.saved_record(), base_hp=None if self.current is None else self.current.base_max_hp,
            base_mp=None if self.current is None else self.current.base_max_mp,
            previous=(self.previous.hp,self.previous.mp),
            change=(self.change.current_hp,self.change.maximum_hp,self.change.current_mp,self.change.maximum_mp),
            resource_before=self.resource_before_digest, skill_before=self.skill_before_digest,
            result=self.result_digest, now=self.accepted_now_ms,
            skill_after=self.owner_ref().batch.digest(self.skill_after_source))

    def saved_record(self):
        return dict(hp=self.following.hp, mp=self.following.mp, base_key=self.base_key,
                    base_revision=self.base_revision, base_digest=self.base_digest)



@dataclass(frozen=True, slots=True)
class AdvanceSpiritLifecycleInput:
    owner_ref: object
    service: object
    plan: object
    operation: object
    resource_before: object
    resource_after: object
    resource_before_digest: str
    resource_after_digest: str
    skill_before_digest: str
    skill_after_digest: str
