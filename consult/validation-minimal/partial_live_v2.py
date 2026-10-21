"""Explicit v2 original-Broker caller/send adapter; no namespace registration.

Construction requires the normal selected BrokerProvider/BatchStore and actual
LocalFactsPort. A client packet, DTO or generic fixture is not this authority.
"""
import asyncio
from dataclasses import dataclass
import json
import threading
from types import MethodType
from tools.local_original_session import inventory, item_custody
import partial_wire_v2 as wire

POLICY=wire.POLICY
need=inventory.need


def _source_run(function,*args,**kwargs):
    # Required exact selected Inventory port. No default/fallback and no live
    # current/Root/operation/CAS caching: only synchronous static source data.
    return inventory.run_source_contract(function,*args,**kwargs)


@dataclass(frozen=True,slots=True)
class Membership:
    snapshot: object
    frame: bytes
    phase: str


@dataclass(frozen=True,slots=True)
class Context:
    writer: object
    row: object
    inventory_service: object
    authority: tuple
    position: object


@dataclass(frozen=True,slots=True,init=False)
class PartialBoundOperation:
    session: object
    context: Context
    wires: tuple
    membership: Membership
    continuation: object
    def __new__(cls):raise ValueError('PARTIAL_LIVE_PRIVATE_OPERATION_ISSUANCE')


def is_current_partial(broker,session,operation=None):
    if type(session) is not PartialLiveSession:return False
    manager=session.manager
    if not (getattr(broker,'_inventory_partial_policy',None)==POLICY and
            getattr(broker,'_partial_feature',None) is manager and manager.broker is broker and
            manager.sessions.get(id(session.generation)) is session and not manager.closed and
            session.generation.broker is broker and broker._inventory_generation is session.generation and
            session.generation.transfer_session is session and not session.closed):return False
    if operation is None:return True
    return (type(operation) is PartialBoundOperation and session.pending is operation and
            session._issued is operation and operation.session is session)


def is_partial_store(broker,store):
    core=getattr(broker,'_inventory_partial_core',None)
    return (getattr(broker,'_inventory_partial_policy',None)==POLICY and core is not None and
            type(store) is core.PartialInventorySource and broker._inventory_store is store and
            store.partial_policy==core.partial_stack.POLICY)


def partial_delivery_allowed(provider,binding,session):
    """Only the registered same-op committed delivery, within original scope.

    Called *after* original provider scope/task/thread/row/generation checks.
    This does not replace those checks or normal current's idle transport gate.
    """
    if not is_current_partial(provider.broker,session,session.pending):return False
    op=session.pending;g=session.generation;m=session.membership
    if not (session.manager.provider is provider and session.binding is binding and
            binding.generation is g and binding.writer is g.writer and binding.operation_lock is g.lock and
            session.phase=='COMMITTING' and session._dispatch_active and session._committed is not None and
            m is op.membership and m.snapshot is session._committed and
            m.frame is provider.broker._inventory_current_frame and
            session.manager.batch.data['canonical']==session._committed_canonical and
            op.context.writer is g.writer and op.context.row is g.row and
            op.context.position is g.mover.snapshot() and 0<=session._send_index<=len(op.wires)):
        return False
    if session._send_index==len(op.wires):
        return session._wire_phase is None and g.row['policy_row'].sent==session._initial_sent+len(op.wires)
    return session._wire_phase in (None,'WRITE_ATTEMPTED')


class PartialLiveSession:
    def __init__(self,manager,generation):
        from tools.local_original_session.broker import PersistentBroker,_InventoryGeneration
        need(type(manager) is PartialRuntime and type(manager.broker) is PersistentBroker and
             type(generation) is _InventoryGeneration and generation.broker is manager.broker and
             manager.broker._inventory_generation is generation and generation.phase=='ACTIVE',
             'PARTIAL_LIVE_ACTUAL_BROKER_GENERATION')
        self.manager,self.broker,self.generation=manager,manager.broker,generation
        self.pending=self._issued=self.binding=self._committed=self.membership=None
        self.closed=False;self.phase='READY';self._dispatch_active=False
        self._send_index=0;self._wire_phase=None;self._sent_before=self._drain_started=None;self._initial_sent=None
        self._storage_owner=None;self._namespace_check=None;self._committed_canonical=None

    def _registered(self,writer):
        need(is_current_partial(self.broker,self) and self.generation.writer is writer and
             self.generation.phase=='ACTIVE' and self.broker.inventory_selection_current(writer) is self.generation,
             'PARTIAL_LIVE_CURRENT_REGISTERED_GENERATION')
        return self.generation

    def validate_use_locked(self,writer,*,read_only_initialization=False):
        g=self._registered(writer)
        need(g.lock.locked() and self.pending is None,'PARTIAL_LIVE_CURRENT_IDLE_ROW')
        need(read_only_initialization is True,'PARTIAL_NATIVE_CURRENT_INPUT_SOURCE_REQUIRED')

    def helper_open_allowed(self,writer):
        self._registered(writer)
        raise ValueError('PARTIAL_NATIVE_CURRENT_INPUT_SOURCE_REQUIRED')

    def _context(self,writer,*,delivery=False):
        g=self._registered(writer);p=self.manager.provider;b=self.broker
        need(g.lock is g.row['operation_lock'] and g.lock.locked() and
             g.service is b._inventory_service and g.store is self.manager.batch.source is b._inventory_store and
             g.delivery_authority is not None and g.current_frame is b._inventory_current_frame and
             g.service._claimed and not g.service._closed and not g.service._inflight,
             'PARTIAL_LIVE_ORIGINAL_INITIAL_DELIVERY_REQUIRED')
        if delivery:
            position=self.manager.facts.delivery_position(self.binding)
        else:
            position=self.manager.facts.actual_position(self.binding)
        method=g.service._current
        need(type(method) is MethodType and method.__func__ is inventory.InventoryService._current,
             'PARTIAL_LIVE_ORIGINAL_INVENTORY_AUTHORITY')
        authority=method(writer,g.row)
        return Context(writer,g.row,g.service,authority,position)

    def _bind_current(self,writer):
        """Refresh Root's record for this normal freshly acquired row scope.

        Prior Binding/current-record identity is not carried into another
        connection_operation. Snapshot clones remain semantic source data.
        """
        g=self._registered(writer);b=self.broker
        need(self.pending is None and self.phase=='READY' and not self._dispatch_active and
             g.delivery_authority is not None and g.service._claimed and not g.service._inflight,
             'PARTIAL_CURRENT_ORIGINAL_INITIAL_DELIVERY_REQUIRED')
        binding=self.manager.provider.bind_selected(writer)
        self.binding=binding
        with self.manager.batch.lock,self.manager.core.inventory_store.realm._lock:
            self.manager.provider.current(binding)
            snapshot=self.manager.batch.source.partial_snapshot(binding.uid)
            raw,document=_source_run(self.manager.batch._read)
            need(raw==self.manager.batch._raw and document==self.manager.batch.data and
                 document['canonical']==_source_run(self.manager.core.partial_stack.encode,snapshot) and
                 self.manager.core.partial_stack.owned_frame(snapshot)==b._inventory_current_frame,
                 'PARTIAL_CURRENT_EXACT_CANONICAL_MEMBERSHIP')
            self._committed=snapshot
            phase=self.membership.phase
            need(phase in ('INITIAL_PENDING','DRAINED'),'PARTIAL_CURRENT_EXISTING_MEMBERSHIP_PHASE')
            self.membership=Membership(snapshot,b._inventory_current_frame,phase)
            self.manager.batch.partial_record('record_selected',binding,self.manager.batch)
        return binding

    async def handle(self,writer,payload,*,kind):
        g=self._registered(writer)
        need(self.pending is None and self.phase=='READY','PARTIAL_LIVE_NO_PENDING_REPLAY')
        self.binding=_source_run(self._bind_current,writer) # Existing held _row_operation scope.
        context=_source_run(self._context,writer)
        await self.broker._checkpoint(writer,g.row)
        after=_source_run(self._context,writer)
        g.service._same(context.authority,after.authority)
        need(context.position is after.position,'PARTIAL_PRECOMMIT_CURRENT_POSITION_CHANGED')
        self.broker.source_guard();context=after
        storage=self.manager.core.PartialStorageOwner(self.manager.batch,facts=self.manager.facts,
                    policy=self.manager.core.partial_stack.POLICY)
        planner=wire.PartialWireOwner(self.manager.core,storage,spawn_port=self.manager.spawn,policy=POLICY)
        self._storage_owner=storage
        try:
            ticket=_source_run(planner.prepare_payload,self.binding,payload,kind=kind)
            result=_source_run(planner.commit,self.binding,ticket)
            await self._send_committed(context,result.snapshot,result.plan.frames,result.continuation)
            return ()
        except BaseException:
            self.closed=True;self.phase='TERMINAL';g.row['failed']=True
            self.broker._fail('PARTIAL_TRANSFER_OUTCOME_UNKNOWN')
            raise
        finally:
            self._dispatch_active=False;self._storage_owner=None;planner.close()

    async def _send_committed(self,context,snapshot,frames,continuation):
        g=self.generation;b=self.broker;binding=self.binding
        need(type(frames) is tuple and 0<len(frames)<=5 and self.pending is None,
             'PARTIAL_LIVE_BOUNDED_FRESH_DELIVERY')
        frame=_source_run(self.manager.core.partial_stack.owned_frame,snapshot)
        b._inventory_current_frame=frame
        self._committed=snapshot;self._committed_canonical=_source_run(self.manager.core.partial_stack.encode,snapshot)
        self.membership=Membership(snapshot,frame,'COMMITTING')
        operation=object.__new__(PartialBoundOperation)
        for name,value in dict(session=self,context=context,wires=frames,
                membership=self.membership,continuation=continuation).items():
            object.__setattr__(operation,name,value)
        self.pending=self._issued=operation;self.phase='COMMITTING'
        self._send_index=0;self._wire_phase=None;self._initial_sent=g.row['policy_row'].sent
        self._dispatch_active=True
        try:
            with self.manager.batch.lock,self.manager.core.inventory_store.realm._lock:
                self.manager.provider.delivery_current(self.binding)
                raw,document=_source_run(self.manager.batch._read)
                need(raw==self.manager.batch._raw and document==self.manager.batch.data and
                     document['canonical']==_source_run(self.manager.core.partial_stack.encode,snapshot),
                     'PARTIAL_DELIVERY_EXACT_COMMITTED_PREIMAGE')
                self.manager.batch.partial_record('record_delivery',self.binding,self.manager.batch,operation,snapshot)
            from partial_delivery_current_v2 import DeliveryCurrent
            self._namespace_check=_source_run(DeliveryCurrent,self,operation,self.manager.facts_module)
            await b._send(context.writer,g.row,frames,game=True,operation_lock=g.lock,
                          item_transfer_operation=operation)
            need(self._send_index==len(frames) and self._wire_phase is None,
                 'PARTIAL_LIVE_ALL_ORIGINAL_DRAINS_REQUIRED')
            _source_run(self.manager.facts.delivery_current,self.binding)
            self.manager.last_continuation=continuation
            self.membership=Membership(snapshot,frame,'DRAINED')
            self.pending=self._issued=None;self.phase='READY'
            with self.manager.batch.lock,self.manager.core.inventory_store.realm._lock:
                self.manager.provider.current(self.binding)
                raw,document=_source_run(self.manager.batch._read)
                need(raw==self.manager.batch._raw and document==self.manager.batch.data and
                     document['canonical']==_source_run(self.manager.core.partial_stack.encode,snapshot),
                     'PARTIAL_DRAINED_EXACT_COMMITTED_PREIMAGE')
                self.manager.batch.partial_record('record_selected',self.binding,self.manager.batch)
        finally:
            self._dispatch_active=False
            if self._namespace_check is not None:self._namespace_check.close();self._namespace_check=None

    async def recover_ground_locked(self,writer):
        """Existing equipment-sync caller, new selection's fresh4E96 only.

        Requires complete source inputs for every saved ground stack. Authoritative
        saved XY is encoded directly; another map is unconfirmed/refused.
        """
        from tools.local_original_session import item_ground_wire
        g=self._registered(writer)
        need(self.pending is None and self.phase=='READY','PARTIAL_RESTORE_IDLE_GENERATION')
        self.binding=_source_run(self._bind_current,writer)
        context=_source_run(self._context,writer)
        await self.broker._checkpoint(writer,g.row)
        after=_source_run(self._context,writer)
        g.service._same(context.authority,after.authority)
        need(context.position is after.position,'PARTIAL_RESTORE_CURRENT_POSITION_CHANGED')
        self.broker.source_guard();context=after
        snapshot=_source_run(self.manager.batch.source.partial_snapshot,self.binding.uid)
        ground=tuple(s for s in snapshot.stacks if s.owner=='GROUND')
        need(len(ground)<=5,'PARTIAL_RESTORE_ORIGINAL_REPLY_BOUND')
        frames=[]
        for stack in ground:
            effect=wire.Effect('GROUND','SPAWN',stack.uid,stack.quantity,False,False)
            need(_source_run(self.manager.spawn.current,self.binding) is True,'PARTIAL_RESTORE_CURRENT_BORROW')
            supplied=_source_run(self.manager.spawn.complete_saved,self.binding,stack,snapshot.character_uid)
            need(type(supplied) is wire.SpawnInput and supplied.position is context.position,
                 'PARTIAL_RESTORE_SAME_CURRENT_POSITION_BORROW')
            expected=item_ground_wire.local_candidate(wire.item_ground.PROFILE,actor_uid=stack.uid,
                packed_position=wire.movement.authority.pack_grid(*stack.location[1:]),quantity=stack.quantity)
            need(supplied.candidate==expected and supplied.source is wire.item_ground.require_ground_source(),
                 'PARTIAL_RESTORE_COMPLETE_SOURCE_RECIPE')
            frames.append(item_ground_wire.build_candidate(supplied.candidate))
        try:
            if frames:
                await self._send_committed(context,snapshot,tuple(frames),
                    tuple((s.uid,s.quantity,'FRESH_CURRENT_PAIR_LOOKUP_REQUIRED') for s in ground))
        except BaseException:
            self.closed=True;self.phase='TERMINAL';g.row['failed']=True
            self.broker._fail('PARTIAL_RESTORE_OUTCOME_UNKNOWN');raise

    def validate_wire(self,writer,row,packet,operation):
        need(is_current_partial(self.broker,self,operation) and self.phase=='COMMITTING' and
             operation.context.writer is writer and operation.context.row is row and
             self._send_index<len(operation.wires) and packet is operation.wires[self._send_index],
             'PARTIAL_LIVE_EXACT_ORDERED_ISSUED_WIRE')
        if self._wire_phase=='WRITE_ATTEMPTED':
            need(self._namespace_check is not None,'PARTIAL_POST_CURRENT_PREPARED_BORROW_REQUIRED')
            self.validate_write_binding(writer,row,packet,operation)
            self._namespace_check.check()
            return operation.context
        context=self._context(writer,delivery=True)
        # Full actual readonly equipment/schema checks remain prewrite.
        reader=self.manager.facts.reader
        equipment_raw=reader.path.read_bytes()
        state=reader.restore(self.binding.uid,self.membership.frame)
        need(reader.path.read_bytes()==equipment_raw and
             self.manager.core.item_custody._equipment_guard(state)==self._committed.equipment_guard,
             'PARTIAL_PREWRITE_CURRENT_READONLY_EQUIPMENT_CHANGED')
        need(self._namespace_check is not None,'PARTIAL_PREWRITE_NAMESPACE_BORROW_REQUIRED')
        self._namespace_check.bind_equipment(reader,equipment_raw)
        need(context.position is operation.context.position and
             self.manager.batch.source.partial_snapshot(self.binding.uid)==self._committed,
             'PARTIAL_LIVE_CURRENT_COMMITTED_PROJECTION')
        return context

    def validate_write_binding(self,writer,row,packet,operation):
        # Original Broker uses this after its awaited current-owner query. No
        # file/native reads/callbacks are introduced in the final write leaf.
        g=self.generation
        need(is_current_partial(self.broker,self,operation) and self._dispatch_active and
             self.phase=='COMMITTING' and g.phase=='ACTIVE' and g.writer is writer and g.row is row and
             g.lock is row['operation_lock'] and g.lock.locked() and
             g.mover.snapshot() is operation.context.position and self.membership is operation.membership and
             self.membership.snapshot is self._committed and
             self.membership.frame is self.broker._inventory_current_frame and
             self._send_index<len(operation.wires) and packet is operation.wires[self._send_index],
             'PARTIAL_LIVE_WRITE_BINDING_CHANGED')

    def attempt(self,writer,row,packet,operation):
        self.validate_write_binding(writer,row,packet,operation)
        policy=row['policy_row']
        need(self._wire_phase is None and policy.pending_opcode==int.from_bytes(packet[2:4],'little') and
             policy.pending_size==len(packet) and policy.drain_started_ns is not None,
             'PARTIAL_LIVE_SINGLE_ORIGINAL_RESERVED_WRITE')
        self._wire_phase='WRITE_ATTEMPTED';self._sent_before=policy.sent;self._drain_started=policy.drain_started_ns

    def drained(self,writer,row,packet,operation,queued):
        self.validate_write_binding(writer,row,packet,operation);policy=row['policy_row']
        need(self._wire_phase=='WRITE_ATTEMPTED' and queued==0 and policy.pending_opcode is None and
             policy.pending_size==0 and policy.drain_started_ns is None and policy.sent==self._sent_before+1,
             'PARTIAL_LIVE_ORIGINAL_DRAIN_REQUIRED')
        self._send_index+=1;self._wire_phase=None

    def release(self,writer):
        if writer is self.generation.writer:
            try:
                if self.manager.batch._partial_recorder is not None:
                    with self.manager.batch.lock,self.manager.core.inventory_store.realm._lock:
                        self.manager.batch.partial_record('record_retire',self.generation,self)
            finally:
                self.closed=True;self.phase='TERMINAL';self._dispatch_active=False
                self.pending=self._issued=None


class PartialRuntime:
    def __init__(self,core,provider,batch,facts_module):
        from tools.local_original_session.broker import PersistentBroker
        need(type(provider) is core.BrokerProvider and type(provider.broker) is PersistentBroker and
             type(batch) is core.BatchStore and batch.provider is provider and
             type(batch.source) is core.PartialInventorySource and facts_module.core is core,
             'PARTIAL_LIVE_SINGLE_ACTUAL_SOURCE_COHORT')
        self.core,self.provider,self.batch,self.facts_module=core,provider,batch,facts_module
        self.broker=provider.broker;self.facts=self.spawn=None;self.ready=False
        self.recorder=None;self.namespace_owner=self._ownedcarry=self._borrow_close=None
        self.sessions={};self.closed=False;self.last_continuation=None

    def configure_recorder(self,recorder,*,source):
        need(not self.closed and self.recorder is None and not self.ready and not self.sessions,
             'PARTIAL_COLD_SINGLE_RECORDER')
        self.batch.attach_partial_recorder(recorder,source=source);self.recorder=recorder

    def configure_facts(self,facts):
        need(not self.closed and self.recorder is not None and not self.ready and self.facts is None and not self.sessions and
             not self.broker._started and not self.broker.realm.registry._sessions and
             type(facts) is self.facts_module.LocalFactsPort and facts.provider is self.provider and
             facts.source is self.batch.source,'PARTIAL_COLD_SINGLE_FACTS_CONNECTION')
        owner=facts.reservation_owner
        need(owner.root_owner is self.recorder and owner.provider is self.provider and owner.batch is self.batch,
             'PARTIAL_SAME_ROOT_RESERVATION_BRIDGE')
        method=owner.ownedcarry
        need(type(method) is MethodType and method.__self__ is owner and
             not asyncio.iscoroutinefunction(method),'PARTIAL_ACTUAL_NAMESPACE_OWNEDCARRY_PORT_REQUIRED')
        need(type(owner.close) is MethodType and owner.close.__self__ is owner,
             'PARTIAL_BORROW_ORIGINAL_CLOSE_REQUIRED')
        self.namespace_owner,self._ownedcarry,self._borrow_close=owner,method,owner.close
        self.facts=facts;self.spawn=wire.SourceProfileSpawnPort(self.facts_module,facts);self.ready=True

    def validate_carry_delivery(self,binding,operation,snapshot):
        need(self.ready and is_current_partial(self.broker,operation.session,operation) and
             operation.membership.snapshot is snapshot,'PARTIAL_NAMESPACE_SAME_COMMITTED_DELIVERY')
        method=self.namespace_owner.ownedcarry
        need(type(method) is MethodType and method.__self__ is self.namespace_owner and
             method.__func__ is self._ownedcarry.__func__,'PARTIAL_NAMESPACE_OWNEDCARRY_SOURCE_CHANGED')
        for stack in snapshot.stacks:
            if snapshot.domain.first<=stack.uid<=snapshot.domain.last:
                need(method(binding,stack,binding.generation,self.batch.profile,issued_transfer=operation) is True,
                     'PARTIAL_NAMESPACE_ACTUAL_CARRY_REPRESENTATION_REQUIRED')

    def namespace_issuance(self,binding):
        # Pure query of existing issuer state. No provider/Facts/Store callback,
        # registration, allocation or file IO; root still owns current-record authority.
        p=self.provider
        need(not self.closed and type(binding) is self.core.Binding and p._bound is binding and
             p._scope is binding.owned_scope and type(p._scope) is tuple and
             p._scope[0] is asyncio.current_task() and p._scope[1]==threading.get_ident() and
             p._scope[2] is binding.writer and p._scope[3] is binding.generation.row and
             p._scope[4] is binding.operation_lock and binding.operation_lock.locked(),
             'PARTIAL_NAMESPACE_ACTUAL_ISSUER_SCOPE')
        session=self.sessions.get(id(binding.generation));issued=None
        if session is not None:
            need(is_current_partial(self.broker,session) and session.generation is binding.generation,
                 'PARTIAL_NAMESPACE_CURRENT_SESSION')
            if session.pending is not None:
                need(is_current_partial(self.broker,session,session.pending) and session.binding is binding,
                     'PARTIAL_NAMESPACE_EXACT_LIVE_ISSUANCE')
                issued=session.pending
            elif session._storage_owner is not None:
                owner=session._storage_owner
                need(type(owner) is self.core.PartialStorageOwner and owner.store is self.batch and
                     not owner.closed,'PARTIAL_NAMESPACE_STORAGE_ISSUER')
                if owner.pending is not None:
                    record=owner._records.get(id(owner.pending))
                    need(type(record) is dict and record['operation'] is owner.pending and
                         record['binding'] is binding and type(record['used']) is bool and
                         (not record['used'] or record['new']==self.core.encoded(self.batch.data)),
                         'PARTIAL_NAMESPACE_STORAGE_ISSUED_OPERATION')
                    issued=owner.pending
        return binding.generation,issued

    def selected_ready_locked(self,writer,generation):
        need(self.ready and not self.closed and generation.transfer_session is None,'PARTIAL_LIVE_FRESH_SELECTION')
        session=PartialLiveSession(self,generation);self.sessions[id(generation)]=session
        generation.transfer_session=session
        binding=self.provider.bind_selected(writer)
        # Existing v4 reselection may already contain reserved carry rows. The
        # ordinary source getter produces semantic rows before Root publishes
        # their restore provenance; no previous client Pair is transported.
        canonical=self.batch.data.get('canonical',self.batch.data)
        if canonical.get('version')==self.core.partial_stack.VERSION:
            snapshot=self.batch.source.partial_snapshot(binding.uid)
            need(self.core.partial_stack.owned_frame(snapshot)==generation.frame,
                 'PARTIAL_RESTORED_INITIAL_FRAME_CHANGED')
            session.membership=Membership(snapshot,generation.frame,'INITIAL_PENDING')
        with self.batch.lock,self.core.inventory_store.realm._lock:
            self.batch.partial_record('record_selected',binding,self.batch)
        self.facts.current(binding) # Registered namespace before ANY migration IO.
        if self.batch.data.get('version')!=3:
            self.batch.migrate_partial_envelope(binding)
            with self.batch.lock,self.core.inventory_store.realm._lock:
                self.batch.partial_record('record_selected',binding,self.batch)
        if self.batch.data['canonical'].get('version')==item_custody.VERSION:
            owner=self.core.PartialStorageOwner(self.batch,facts=self.facts,policy=self.core.partial_stack.POLICY)
            session._storage_owner=owner
            try:owner.commit(binding,owner.prepare_migration(binding))
            finally:session._storage_owner=None;owner.close()
        snapshot=self.batch.source.partial_snapshot(binding.uid)
        need(self.core.partial_stack.owned_frame(snapshot)==generation.frame,
             'PARTIAL_LIVE_MIGRATION_INITIAL_FRAME_CHANGED')
        session.membership=Membership(snapshot,generation.frame,'INITIAL_PENDING')
        # Same port, now with the exact source-produced restored snapshot in the
        # normal caller's local and session membership. Earlier publish had no
        # owned-stack identity and granted no carry restore authority.
        with self.batch.lock,self.core.inventory_store.realm._lock:
            self.provider.current(binding)
            raw,document=self.batch._read()
            need(raw==self.batch._raw and document==self.batch.data and
                 document['canonical']==self.core.partial_stack.encode(snapshot),
                 'PARTIAL_SELECTED_EXACT_RESTORED_PREIMAGE')
            self.batch.partial_record('record_selected',binding,self.batch)
        return session

    def close(self):
        if self.closed:return
        self.closed=True;self.ready=False;error=None
        for session in tuple(self.sessions.values()):
            try:session.release(session.generation.writer)
            except BaseException as failure:
                if error is None:error=failure
        self.sessions.clear()
        if self.facts is not None:
            try:self.facts.close()
            except BaseException as failure:
                if error is None:error=failure
        if self._borrow_close is not None:
            try:self._borrow_close()
            except BaseException as failure:
                if error is None:error=failure
        if error is not None:raise error


def attach_runtime(broker,api,provider,batch,facts_module,*,facts_factory,root_source):
    """Root original factory caller, after owner.attach(provider,batch).

    Consumes the original objects only. No interval registration, another core
    load, provider/batch construction, signature fallback or implicit facts.
    """
    from tools.local_original_session.canonical_feature_bootstrap import SourceModule
    need(type(root_source) is SourceModule and callable(facts_factory) and
         type(provider) is api.BrokerProvider and type(batch) is api.BatchStore and
         provider.broker is broker and batch.provider is provider and
         broker._canonical_provider is provider and broker._partial_feature is None,
         'PARTIAL_ROOT_ORIGINAL_FACTORY_ATTACH_REQUIRED')
    owner=broker.realm.uid_namespace_owner
    need(owner is not None and owner.provider is provider and owner.store is batch and
         root_source.check().RootNamespaceRecorder in type(owner).__mro__,
         'PARTIAL_ROOT_ALREADY_ATTACHED_OWNER_REQUIRED')
    runtime=PartialRuntime(api,provider,batch,facts_module)
    facts=None
    try:
        runtime.configure_recorder(owner,source=root_source)
        facts=facts_factory(api,provider,runtime,owner)
        runtime.configure_facts(facts)
        broker._partial_feature=runtime
        return runtime
    except BaseException as primary:
        steps=[]
        if facts is not None and runtime.facts is None:
            # Factory completed but configure rejected: retire only its borrowed
            # Facts/bridge resources, never the actual shared Root owner.
            steps.extend((facts.close,facts.reservation_owner.close))
        steps.append(runtime.close)
        for close in steps:
            try:close()
            except BaseException:primary.add_note('PARTIAL_ATTACH_BORROW_CLEANUP_UNKNOWN')
        raise
