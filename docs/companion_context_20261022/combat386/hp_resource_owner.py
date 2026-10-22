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
    def bind_light_policy(self, policy, module):
        need(self._light_policy is None and self._light is None and not self.active
             and not self.status.broker._started and type(policy)is module.LightPolicy,
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
            result=self.validate_projection(writer, snapshot)
            if getattr(self,'_combat_stats',None) is not None:
                from tools.local_original_session.combat_adapters import refresh_selected_stats
                refresh_selected_stats(self,writer,'selection')
            return result
        need(self._world_setup is not None, 'RESOURCE_WORLD_SETUP_NOT_AUTHORIZED')
        binding, request = self._world_setup
        self.provider.current(binding)
        need(binding.writer is writer and snapshot is self.status._resource_raw_current(writer)
             and id(writer) not in self.status._world, 'RESOURCE_EXACT_COMPLETED_WORLD_REQUIRED')
        self._arming = (binding, snapshot)
        receipt = self.seed_locked(binding, txid='RESOURCE_SEED:' + str(binding.uid), request=request)
        self._world_setup = None
        if getattr(self,'_combat_stats',None) is not None:
            from tools.local_original_session.combat_adapters import refresh_selected_stats
            refresh_selected_stats(self,writer,'selection')
        return receipt

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
        if op.reason in ('HP_EFFECT', 'PLAYER_LIFE'):
            need(self._hp_producer is not None and self._hp_producer[0] is op,
                 'RESOURCE_HP_ACTUAL_PRODUCER_REQUIRED')
            proof = self._hp_producer[1]
            current = self._verified_hp_producer(op.binding.writer, op.binding.generation.row,
                op.snapshot, proof[3] if op.reason == 'PLAYER_LIFE' else None)
            need(len(current) == len(proof) and all(a is b for a,b in zip(current[:4],proof[:4]))
                 and current[4:] == proof[4:], 'RESOURCE_HP_PRODUCER_CHANGED_BEFORE_COMMIT')
        return True

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
        if skill is not None:fields=self.shield_status_fields(binding,fields,skill)
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

    def plan_magic_cast_locked(self, context, *, txid, request, now_ms):
        import sys
        from tools.local_original_session.combat_magic_cast import AdmittedSelfContext
        need(type(context) is AdmittedSelfContext and getattr(self, '_combat_magic', None) is not None,
             'MAGIC_EXACT_ADMITTED_POLICY_REQUIRED')
        return self._combat_magic.plan(context, owner_module=sys.modules[__name__],
            txid=txid, request=request, now_ms=now_ms)


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
            if lifecycle is not None:
                from tools.local_original_session.buff_skill_document import SkillDocument as BuffSkillDocument
                need(type(self.skill_schema)is BuffSkillDocument and lifecycle.schema is self.skill_schema,
                     'BUFF_EXACT_CONFIGURED_CAST_DOCUMENT_REQUIRED')
                result,skill_after=self.skill_schema.plan_apply(skill['document'],binding,
                    command='cast',spell_id=spell_id,target_uid=target_uid,now_ms=now_ms,
                    expected_revision=row['revision'],resources=dict(hp=snapshot.fields[10],mp=snapshot.fields[12]))
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
            debit, = [event for event in result['events'] if event['kind'] == 'resource_debit']
            values = dict(before['document']['values'])
            values['10'] -= debit['hp']
            values['12'] -= debit['mp']
            after = self.document.next_values(before['document'], values=values)
            op = Operation(binding, snapshot, before['document'], after, request, txid, 'CAST_COST', result)
            changes = (self.batch.ParticipantChange('RESOURCE', before['revision'], before['digest'], after),
                       self.batch.ParticipantChange('SKILL', skill['revision'], skill['digest'], skill_after))
            fields = dict(snapshot.fields)
            fields.update({int(n): value for n, value in after['values'].items()})
            fields=self.shield_status_fields(binding,fields,skill_after)
            plan = CastPlan(op, changes, deepcopy(skill['document']), deepcopy(skill_after),
                            fields, self.status_module.frame(fields), now_ms)
            self._prepared_operation = op
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
            accepted_now_ms=plan.accepted_now_ms))

    def validate_plan(self, plan):
        need(type(plan) is CastPlan and plan.phase == 'PLANNED'
             and plan.operation is self._prepared_operation
             and self.plan_digest(plan) == self._prepared_digest,
             'RESOURCE_SOURCE_CALLBACK_CHANGED_CAST_PLAN')
        self.provider.current(plan.operation.binding)
        context = getattr(plan, 'magic_context', None)
        if context is not None:
            need(context.current() is None and context.operation.binding is plan.operation.binding
                 and context.decision.snapshot is plan.operation.snapshot,
                 'MAGIC_CAST_SOURCE_CONTEXT_CHANGED')
        return None

    def discard_cast_plan(self, plan):
        need(type(plan) is CastPlan and plan.operation is self._prepared_operation
             and plan.phase == 'PLANNED', 'RESOURCE_EXACT_UNCOMMITTED_CAST_PLAN')
        plan.phase = 'TERMINAL'
        self._prepared_operation = self._prepared_digest = None

    def commit_cast_locked(self, plan, reply_parent):
        # One concrete parent controls all preflighted source frames and the
        # single global receipt. Missing/unknown response semantics refuse
        # before BatchStore.prepare or any resource debit.
        from tools.local_original_session.skill_cost_delivery import CostDelivery
        need(type(reply_parent) is CostDelivery and reply_parent.owner is self
             and reply_parent.plan is plan, 'RESOURCE_EXACT_SOURCE_REPLY_PLAN_REQUIRED')
        self.validate_plan(plan)
        need(reply_parent.validate_precommit(plan) is None,
             'RESOURCE_REPLY_PREFLIGHT_MUST_RAISE_NOT_BOOLEAN')
        receipt, delivery, result = self._commit_cast_plan(plan)
        reply_parent.bind_committed(receipt, delivery)
        return receipt, delivery, result

    def _commit_cast_plan(self, plan):
        # Private owner commit primitive; tests exercise atomicity with this
        # explicitly. Actual route uses commit_cast_locked only after complete
        # concrete source response preflight, never this primitive directly.
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
                    receipt, delivery = self._commit_and_project(op, plan.changes, status_wire=plan.status_wire)
                plan.phase = 'COMMITTED'
                if getattr(self,'_combat_stats',None) is not None:
                    from tools.local_original_session.combat_adapters import refresh_selected_stats
                    refresh_selected_stats(self,op.binding.writer,'skills')
                return receipt, delivery, deepcopy(op.semantic_result)
            except BaseException:
                plan.phase = 'TERMINAL'
                raise

    def _commit_and_project(self, operation, changes, *, status_wire):
        binding = operation.binding
        with self._staged_operation(operation):
            _, revision = self.store.restore(binding)
            reservation = self.store.prepare(binding, txid=operation.txid, request=operation.request,
                catalog_digest=self.catalog_digest, expected_revision=revision,
                changes=(), participants=changes)
            receipt = self.store.commit(binding, reservation)
        need(receipt['phase'] == 'COMMITTED', 'RESOURCE_COMMIT_CONFIRMATION_REQUIRED')
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
        need(op.reason != 'CAST_COST', 'RESOURCE_COST_PARENT_REPLY_BATCH_REQUIRED')
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
                 and producer.hp_operation is None and before.current_hp > 0
                 and service.validate_locked(writer, producer.context) is row,
                 'RESOURCE_HP_VALIDATED_DRAINED_NPC_ATTACK')
            hit = service.decision_locked(writer,producer)
            need(hit.landed and 0 < hit.damage < before.current_hp,'RESOURCE_HP_NONLETHAL_DECISION_REQUIRED')
            context, value, reason = producer.context, before.current_hp - hit.damage, 'HP_EFFECT'
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
                need(before is life_context.snapshot and (before.current_hp == 1
                     or service.adjudicated_lethal_locked(writer,producer))
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
                revision=participant['document']['revision'], before=before.current_hp,
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
            need(not broker._started and not broker._closing
                 and not broker.failure.is_set() and not broker._tasks
                 and not broker.realm.registry._sessions
                 and not any(broker._claims.values())
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
