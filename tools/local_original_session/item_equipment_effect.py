"""Current selected Athame equipment consumer, explicit local-policy subset.

The accepted run74 wire contract is fixed; the weapon key is still required
before any product notification. This service keeps intent/public commit separate from effects.
"""
import asyncio
import copy
import hashlib
from tools.local_original_session import inventory,item_use_session,observe
from tools.local_original_session.athame_policy import plan_athame_use,plan_athame_collection_use,COLLECTION_POLICY as OWNED_POLICY
from tools.local_original_session.equipment_store import EquipmentStore,POLICY as STORE_POLICY,FIRST_ENABLE_EMPTY
from tools.local_original_session import equipment_change

POLICY='EXPLICIT_LOCAL_ATHAME_EQUIPMENT_EFFECT'
SCHEMA='local-item-equipment-effect-v1'
FORM_POLICY='BASE_PROFILE_ONLY'
SWITCH_POLICY='PINNED_LIMIT_WEAPON_SWITCHING_FALSE'
BARRIER_POLICY='LOCAL_INACTIVE_NO_GRANT_PRODUCER'
need=inventory.need

def _receipt(operation,ordinal=None):
    return dict(schema=SCHEMA,policy=POLICY,operation=operation,status='NOT_PREPARED',phase='EMPTY',reason=None,
        writer_bound=False,generation_bound=False,character_uid=None,item_uid=None,template=None,
        accepted_ordinal=ordinal,before_weapon_uid=None,after_weapon_uid=None,before_revision=None,after_revision=None,
        quantity_before=None,quantity_after=None,inventory_frame_changed=False,
        persist_attempted=False,persisted=False,write_attempted=False,drain_returned=False,
        post_owner_verified=False,notification_opcode=0x097a,notification_size=None,notification_sha256=None,
        equipment_key_i32=None,initialization_source=None,client_state='UNKNOWN')

class ItemEquipmentEffect:
    def __init__(self,broker,*,policy,first_enable):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker,'EQUIPMENT_REAL_BROKER_REQUIRED')
        need(type(policy) is str and policy==POLICY and type(first_enable) is bool,'EQUIPMENT_EXPLICIT_POLICY_REQUIRED')
        self.broker=broker;self.realm=broker.realm;self.policy=policy;self.first_enable=first_enable
        self._collection_policy=getattr(broker,'_inventory_collection_policy',None)
        need(self._collection_policy is None or (type(self._collection_policy) is str and
             self._collection_policy==inventory.COLLECTION_POLICY),'EQUIPMENT_COLLECTION_POLICY_REQUIRED')
        if self._collection_policy is None:
            self.store=EquipmentStore(broker._inventory_store,policy=STORE_POLICY)
        else:
            self.store=EquipmentStore(broker._inventory_store,policy=STORE_POLICY,collection_policy=OWNED_POLICY)
        self._collection_batch=None
        self._selection=None;self._operation=None;self._consumed=None
        self._writer=None;self._generation=None;self._last=_receipt('INITIAL_SYNC')
        self._form_policy=FORM_POLICY;self._switch_policy=SWITCH_POLICY;self._limit_weapon_switching=False
        self._barrier_policy=BARRIER_POLICY
        # The real profile producer has already populated LocalRealm. Bind its
        # selected policy/source snapshot; Actor4 is action and is NOT form.
        from tools.local_original_session.broker import BASELINE_WORLD,CP73_SPAWN_WORLD
        if self.realm.world_profile==BASELINE_WORLD:
            from tools.local_native_login_self_actor_hook import hook as profile_hook
        elif self.realm.world_profile==CP73_SPAWN_WORLD:
            from tools.local_native_login_spawn_render_retry_runtime import spawn_hook as profile_hook
        else:raise ValueError('EQUIPMENT_BASE_PROFILE_POLICY_REQUIRED')
        profile,actor,_,_=profile_hook.profiles()
        self._profile_policy=self.realm.world_profile;self._actor=self.realm._actor_fields
        self._appearance=actor[3];self._profile_uid=profile.fields[1]
        need(self._actor[3]==self._appearance and self.realm.profile_uid==self._profile_uid,
             'EQUIPMENT_ACTUAL_BASE_PROFILE_REQUIRED')

    def observation(self,writer,*,accepted_ordinal=None):
        # Cached receipt + current generation identity only, never an authority
        # grant, Store/native sampling or ownership/selection mutation.
        if accepted_ordinal is not None and not(type(accepted_ordinal) is int and 1<=accepted_ordinal<=equipment_change.U64_MAX):
            missing=_receipt('ITEM_USE_EFFECT')
            missing.update(status='NO_MATCH',reason='EQUIPMENT_RECEIPT_ORDINAL_REQUIRED');return missing
        generation=self.broker._inventory_generation
        if self._writer is not writer or self._generation is not generation or generation.phase!='ACTIVE' or (
           generation.item_use_session is None or generation.item_use_session.closed or
           generation.service is None or generation.service._closed) or (
           accepted_ordinal is not None and self._last['accepted_ordinal']!=accepted_ordinal):
            missing=_receipt('ITEM_USE_EFFECT' if accepted_ordinal is not None else 'INITIAL_SYNC',accepted_ordinal)
            missing.update(status='NO_MATCH',reason='EQUIPMENT_RECEIPT_LIFETIME_MISMATCH');return missing
        return copy.deepcopy(self._last)

    def _key(self):
        return equipment_change.weapon_key_from_source()

    def _context(self,writer,operation=None,*,item_identifier=None):
        broker=self.broker;service=broker._item_use_session
        need(broker.realm is self.realm and broker._item_equipment_effect is self and
             type(service) is item_use_session.ItemUseSession and self.realm._item_use_session is service,
             'EQUIPMENT_CURRENT_SERVICE_REQUIRED')
        need(getattr(broker.policy,'item_equipment_effect',None) is True and self.policy==POLICY and
             self._form_policy==FORM_POLICY and self._switch_policy==SWITCH_POLICY and
             self._limit_weapon_switching is False and self._barrier_policy==BARRIER_POLICY,
             'EQUIPMENT_EXPLICIT_CURRENT_CONFIGURATION_REQUIRED')
        mode=getattr(broker,'_inventory_collection_policy',None)
        need(type(mode) is type(self._collection_policy) and mode==self._collection_policy,
             'EQUIPMENT_COLLECTION_POLICY_CHANGED')
        if self._collection_policy is None:
            projection=item_use_session.ItemUseSession._project(service,writer,equipment_operation=operation)
        else:
            if operation is not None:item_identifier=operation['context']['item'].identifier
            projection=item_use_session.ItemUseSession._project(service,writer,
                equipment_operation=operation,item_identifier=item_identifier)
        row=projection[0];position=projection[1][0];game=self.realm.registry.resolve(writer)
        need(row['writer'] is writer and row['operation_lock'].locked() and
             broker._inventory_generation.item_use_session is service and broker._inventory_generation.phase=='ACTIVE',
             'EQUIPMENT_CURRENT_ROW_GENERATION_REQUIRED')
        uid,info=self.realm.store.select(position.name)
        need(uid==position.uid and info[1]==position.name and game.selection is not None and
             game.selection.reference==position.name and self.realm.store.path==self.store.profile,
             'EQUIPMENT_CURRENT_SELECTED_CHARACTER_REQUIRED')
        need(self.realm.world_profile==self._profile_policy and self.realm._actor_fields is self._actor and
             self.realm._actor_fields[3]==self._appearance and self.realm.profile_uid==uid==self._profile_uid,
             'EQUIPMENT_CURRENT_BASE_PROFILE_REQUIRED')
        identity=(writer,broker._inventory_generation,game,game.selection,broker._inventory_service,service,self._actor)
        items=((projection[6],) if self._collection_policy is None else
               self.store.owned_items(uid,projection[2]))
        need(any(inventory._same_static(item.raw_fields,projection[6].raw_fields) for item in items),
             'EQUIPMENT_SELECTED_OWNED_ITEM_REQUIRED')
        return dict(writer=writer,row=row,projection=projection,service=service,generation=broker._inventory_generation,
                    game=game,selected=game.selection,character_uid=uid,selected_class=info[3],
                    item=projection[6],items=items,frame=projection[2],identity=identity)

    def _same(self,original,current):
        need(all(a is b for a,b in zip(original['identity'],current['identity'])) and
             original['selected_class']==current['selected_class'] and original['character_uid']==current['character_uid'],
             'EQUIPMENT_SELECTION_CHANGED')
        item_use_session.ItemUseSession._same(original['service'],original['projection'],current['projection'])

    def _begin(self,context,operation,ordinal=None):
        receipt=_receipt(operation,ordinal);item=context['item']
        receipt.update(writer_bound=True,generation_bound=True,character_uid=context['character_uid'],
                       item_uid=item.identifier,template=item.template_bits,
                       quantity_before=dict(item.raw_fields)[4],quantity_after=dict(item.raw_fields)[4])
        self._writer=context['writer'];self._generation=context['generation'];self._last=receipt
        return receipt

    def _blocked(self,receipt,reason):
        receipt.update(status='BLOCKED',phase='BLOCKED',reason=reason);return copy.deepcopy(receipt)

    def validate_pending(self,writer,row,operation,admitted):
        # Exact self-owned reservation only; no relaxation of public/default
        # ItemUseSession projection and no temporary policy-field alteration.
        need(operation is self._operation and operation['context']['writer'] is writer and
             operation['context']['row'] is row and operation['lock'] is row['operation_lock'] and
             operation['lock'].locked() and operation['phase'] not in ('TERMINAL','DRAINED'),
             'EQUIPMENT_CURRENT_OPERATION_REQUIRED')
        context=operation['context'];receipt=operation['receipt'];service=context['service']
        need(self.broker._inventory_generation is context['generation'] and context['generation'].phase=='ACTIVE' and
             self.broker._item_use_session is service and not service.closed,
             'EQUIPMENT_OPERATION_GENERATION_REQUIRED')
        if receipt['operation']=='ITEM_USE_EFFECT':
            intent=service._current
            need(intent is operation['intent'] and type(intent) is item_use_session._Intent and
                 intent.writer is writer and type(receipt['accepted_ordinal']) is int and
                 service.accepted_count==intent.accepted_ordinal==receipt['accepted_ordinal'] and
                 intent.frame is context['frame'] and intent.selection_binding is context['projection'][4],
                 'EQUIPMENT_OPERATION_ACCEPTED_INTENT_REQUIRED')
        else:
            need(receipt['operation']=='INITIAL_SYNC' and receipt['accepted_ordinal'] is None and operation['intent'] is None,
                 'EQUIPMENT_OPERATION_INITIAL_SYNC_REQUIRED')
        if admitted.drain_started_ns is None:
            need(admitted.pending_opcode is None and admitted.pending_size==0,'EQUIPMENT_UNRESERVED_POLICY_REQUIRED')
        else:
            need(operation['phase'] in ('RESERVING','WRITE_ATTEMPTED') and
                 admitted.pending_opcode==equipment_change.OPCODE and admitted.pending_size==len(operation['wire']),
                 'EQUIPMENT_EXACT_RESERVATION_REQUIRED')

    def validate_reply(self,writer,wire):
        op=self._operation
        if self._collection_policy is not None:return self._validate_collection_reply(writer,wire,op)
        need(op is not None and wire is op['wire'] and op['context']['writer'] is writer,'EQUIPMENT_EXACT_WIRE_REQUIRED')
        parsed=equipment_change.validate_change(wire)
        need(parsed.key==self._key() and parsed.uid==op['state'].item_uid and
             parsed.equipped==(op['state'].weapon_uid==op['state'].item_uid),'EQUIPMENT_EXACT_STATE_WIRE_REQUIRED')
        self._same(op['context'],self._context(writer,op))
        need(self.store.restore(op['state'].character_uid,op['context']['frame'])==op['state'],
             'EQUIPMENT_CURRENT_PERSISTED_STATE_REQUIRED')
        return op

    def attempt(self,writer,row,op):
        need(op is self.validate_reply(writer,op['wire']) and op['context']['row'] is row and
             op['phase']=='RESERVING' and not op['receipt']['write_attempted'],'EQUIPMENT_SINGLE_WRITE_REQUIRED')
        op['phase']='WRITE_ATTEMPTED';op['receipt'].update(phase='WRITE_ATTEMPTED',write_attempted=True)
        if self._collection_policy is not None:
            aggregate=op['batch']['receipt']
            aggregate['write_attempted']=True
            aggregate['notifications_attempted']+=1

    def drained(self,writer,row,op,queued):
        need(op is self.validate_reply(writer,op['wire']) and op['context']['row'] is row and
             op['phase']=='WRITE_ATTEMPTED' and op['receipt']['drain_returned'] is True and queued==0 and
             row['policy_row'].drain_started_ns is None and row['policy_row'].pending_opcode is None and
             row['policy_row'].sent==op['sent_before']+1,'EQUIPMENT_EXACT_DRAIN_REQUIRED')
        op['receipt']['post_owner_verified']=True

    async def _notify(self,context,state,receipt):
        key=self._key()
        wire=equipment_change.build_change(uid=state.item_uid,key=key,equipped=state.weapon_uid==state.item_uid)
        receipt['equipment_key_i32']=key
        receipt.update(notification_size=len(wire),notification_sha256=hashlib.sha256(wire).hexdigest(),phase='PERSISTED')
        op=dict(context=context,state=state,receipt=receipt,wire=wire,lock=context['row']['operation_lock'],
                phase='PERSISTED',sent_before=context['row']['policy_row'].sent,
                intent=context['service']._current if receipt['operation']=='ITEM_USE_EFFECT' else None)
        self._operation=op
        await self.broker._send(context['writer'],context['row'],(wire,),game=True,operation_lock=op['lock'],equipment_operation=op)
        self._same(context,self._context(context['writer'],op))
        need(all(receipt[k] is True for k in ('write_attempted','drain_returned','post_owner_verified')),
             'EQUIPMENT_DRAINED_NOTIFICATION_REQUIRED')
        op['phase']='DRAINED';receipt['phase']='DRAINED'

    def _failed(self,receipt,error):
        receipt.update(status='UNKNOWN',phase='TERMINAL',reason=observe.reason(error))
        if self._operation is not None:self._operation['phase']='TERMINAL'
        if self._collection_policy is not None and self._collection_batch is not None:
            self._collection_batch['phase']='TERMINAL' 
        if receipt['persist_attempted'] or receipt['write_attempted']:
            self.broker._fail('EQUIPMENT_EFFECT_OUTCOME_UNKNOWN')
        # No retry/rollback or invented client state after ambiguous persistence/send.

    async def prepare_locked(self,writer):
        context=self._context(writer)
        life=self._selection
        if life is not None and all(a is b for a,b in zip(life['identity'],context['identity'])):
            if life['synced']:
                # Reuse the actual historical sync receipt; do not invent another
                # notify/drain or replace the latest effect receipt. Store IO belongs
                # to explicit prepare, never the cached observation API.
                need(self.store.restore(context['character_uid'],context['frame'])==life['state'],
                     'EQUIPMENT_CURRENT_EQUIPMENT_CHANGED')
            if life['sync_receipt'] is not None:
                return copy.deepcopy(life['sync_receipt'])
        receipt=self._begin(context,'INITIAL_SYNC')
        # Actual new local actor-life initialization; not f24/modelB0 interpretation.
        # Both refusal and failure are final for this life: a later poll cannot
        # replay preparation or the received request which encountered it.
        life=dict(identity=context['identity'],barrier_active=False,state=None,synced=False,
                  sync_receipt=receipt)
        self._selection=life
        try:
            try:self._key()
            except ValueError as error:return self._blocked(receipt,observe.reason(error))
            # Fresh native/peer authority BEFORE any durable first-enable write.
            await self.broker._checkpoint(writer,context['row']);self._same(context,self._context(writer))
            state=self.store.restore(context['character_uid'],context['frame'])
            if state is None:
                if not self.first_enable:return self._blocked(receipt,'EQUIPMENT_EXPLICIT_FIRST_ENABLE_REQUIRED')
                receipt.update(persist_attempted=True,initialization_source='LOCAL_FIRST_ENABLE_EMPTY')
                state=self.store.initialize_empty(context['character_uid'],context['frame'],initialization=FIRST_ENABLE_EMPTY)
                receipt['persisted']=True
            else:receipt.update(before_weapon_uid=state.weapon_uid,before_revision=state.revision,initialization_source='RESTORED_EQUIPMENT_SIDECAR')
            receipt.update(after_weapon_uid=state.weapon_uid,after_revision=state.revision)
            await self._notify_selected(context,state,receipt)
            life['state']=state;life['synced']=True;receipt.update(status='SYNCHRONIZED',reason=None)
            life['sync_receipt']=copy.deepcopy(receipt)
            return copy.deepcopy(receipt)
        except BaseException as error:
            self._failed(receipt,error);raise

    async def consume_locked(self,writer,*,accepted_ordinal,expected_intent):
        selected=None
        if self._collection_policy is not None:
            current=self.broker._item_use_session._current
            if type(current) is item_use_session._Intent:selected=current.request.identifier
        context=self._context(writer,item_identifier=selected);service=context['service'];intent=service._current
        need(type(accepted_ordinal) is int and accepted_ordinal==service.accepted_count and
             intent is expected_intent and type(intent) is item_use_session._Intent and
             intent.writer is writer and intent.accepted_ordinal==accepted_ordinal and
             intent.frame is context['frame'] and intent.selection_binding is context['projection'][4],
             'EQUIPMENT_EXACT_NEW_ACCEPTED_INTENT_REQUIRED')
        if self._consumed is not None and self._consumed[0] is service and self._consumed[1]==accepted_ordinal:
            return copy.deepcopy(self._consumed[2])
        receipt=self._begin(context,'ITEM_USE_EFFECT',accepted_ordinal)
        self._consumed=(service,accepted_ordinal,receipt) # Once before persistence/send; intent stays intact.
        try:self._key()
        except ValueError as error:return self._blocked(receipt,observe.reason(error))
        life=self._selection
        if life is None or not life['synced'] or not all(a is b for a,b in zip(life['identity'],context['identity'])):
            return self._blocked(receipt,'EQUIPMENT_INITIAL_SYNC_REQUIRED')
        try:
            old=self.store.restore(context['character_uid'],context['frame'])
            need(old==life['state'],'EQUIPMENT_CURRENT_EQUIPMENT_CHANGED')
            plan=self._plan(context,intent,old,life)
            receipt.update(before_weapon_uid=old.weapon_uid,before_revision=old.revision)
            await self.broker._checkpoint(writer,context['row'])
            self._same(context,self._context(writer,item_identifier=context['item'].identifier))
            receipt['persist_attempted']=True
            new=self.store.compare_and_swap(context['character_uid'],context['frame'],old,plan.weapon_uid_after)
            receipt.update(persisted=True,after_weapon_uid=new.weapon_uid,after_revision=new.revision)
            await self._notify_selected(context,new,receipt)
            life['state']=new;receipt.update(status='COMMITTED',reason=None)
            return copy.deepcopy(receipt)
        except ValueError as error:
            if not receipt['persist_attempted'] and not receipt['write_attempted']:
                return self._blocked(receipt,observe.reason(error))
            self._failed(receipt,error);raise
        except BaseException as error:self._failed(receipt,error);raise

    def _plan(self,context,intent,old,life):
        kwargs=dict(selected_character_uid=context['character_uid'],selected_class=context['selected_class'],
            current_weapon_uid=old.weapon_uid,can_switch_weapon=self._limit_weapon_switching is False,
            equip_admitted=self._form_policy==FORM_POLICY,absolute_barrier_active=life['barrier_active'])
        if self._collection_policy is None:
            return plan_athame_use(intent.request,context['item'],**kwargs)
        return plan_athame_collection_use(intent.request,context['items'],policy=OWNED_POLICY,**kwargs)

    async def _notify_selected(self,context,state,receipt):
        if self._collection_policy is None:return await self._notify(context,state,receipt)
        return await self._notify_collection(context,state,receipt)

    def _collection_changes(self,context,state,receipt):
        owned=tuple(item.identifier for item in context['items'] if item.template_bits==1)
        need(state.item_uid==context['items'][0].identifier and state.weapon_uid in (0,)+owned,
             'EQUIPMENT_COLLECTION_STATE_MEMBER_REQUIRED')
        if receipt['operation']=='INITIAL_SYNC':
            # Restored B is true(B), not false(anchor A). Empty uses false(A).
            return ((state.weapon_uid or state.item_uid,state.weapon_uid!=0),)
        need(receipt['operation']=='ITEM_USE_EFFECT' and receipt['after_weapon_uid']==state.weapon_uid,
             'EQUIPMENT_COLLECTION_EFFECT_STATE_REQUIRED')
        before=receipt['before_weapon_uid'];after=state.weapon_uid
        need(type(before) is int and before in (0,)+owned and before!=after,
             'EQUIPMENT_COLLECTION_BEFORE_STATE_REQUIRED')
        changes=(() if before==0 else ((before,False),))
        if after!=0:changes+=((after,True),)
        return changes

    def _validate_collection_reply(self,writer,wire,op):
        batch=self._collection_batch
        need(op is not None and op is self._operation and batch is not None and op.get('batch') is batch and
             batch['phase']=='PERSISTED' and op['index']==batch['next'] and
             op['context'] is batch['context'] and op['state'] is batch['state'] and
             op['receipt'] is batch['receipt']['notification_records'][op['index']] and
             wire is op['wire'] and op['context']['writer'] is writer,
             'EQUIPMENT_EXACT_COLLECTION_WIRE_REQUIRED')
        changes=self._collection_changes(op['context'],op['state'],batch['receipt'])
        need(changes==batch['changes'] and 0<=op['index']<len(changes),
             'EQUIPMENT_EXACT_COLLECTION_ORDER_REQUIRED')
        uid,equipped=changes[op['index']];parsed=equipment_change.validate_change(wire)
        need(parsed.key==self._key() and parsed.uid==uid and parsed.equipped is equipped,
             'EQUIPMENT_EXACT_COLLECTION_CHANGE_REQUIRED')
        self._same(op['context'],self._context(writer,op))
        need(self.store.restore(op['state'].character_uid,op['context']['frame'])==op['state'],
             'EQUIPMENT_CURRENT_PERSISTED_STATE_REQUIRED')
        return op

    async def _notify_collection(self,context,state,receipt):
        changes=self._collection_changes(context,state,receipt);key=self._key()
        need(1<=len(changes)<=2,'EQUIPMENT_COLLECTION_NOTIFICATION_BOUND')
        receipt.update(equipment_key_i32=key,phase='PERSISTED',notification_count=len(changes),
                       notifications_attempted=0,notifications_drained=0,notification_records=[])
        batch=dict(context=context,state=state,receipt=receipt,changes=changes,next=0,phase='PERSISTED')
        self._collection_batch=batch
        for index,(uid,equipped) in enumerate(changes):
            wire=equipment_change.build_change(uid=uid,key=key,equipped=equipped)
            record=_receipt(receipt['operation'],receipt['accepted_ordinal'])
            record.update(item_uid=uid,notification_uid=uid,notification_equipped=equipped,phase='PERSISTED',
                          notification_size=len(wire),notification_sha256=hashlib.sha256(wire).hexdigest())
            receipt['notification_records'].append(record)
            if len(changes)==1:
                receipt.update(notification_size=record['notification_size'],notification_sha256=record['notification_sha256'])
            op=dict(context=context,state=state,receipt=record,wire=wire,lock=context['row']['operation_lock'],
                    phase='PERSISTED',sent_before=context['row']['policy_row'].sent,
                    intent=context['service']._current if receipt['operation']=='ITEM_USE_EFFECT' else None,
                    batch=batch,index=index)
            record.update(sent_before=op['sent_before'],sent_after=None)
            self._operation=op
            await self.broker._send(context['writer'],context['row'],(wire,),game=True,
                                    operation_lock=op['lock'],equipment_operation=op)
            self._same(context,self._context(context['writer'],op))
            need(all(record[k] is True for k in ('write_attempted','drain_returned','post_owner_verified')),
                 'EQUIPMENT_DRAINED_NOTIFICATION_REQUIRED')
            record.update(status='DRAINED',phase='DRAINED',sent_after=context['row']['policy_row'].sent)
            op['phase']='DRAINED';batch['next']+=1
            receipt['notifications_drained']=batch['next']
        batch['phase']='DRAINED'
        receipt.update(phase='DRAINED',drain_returned=True,post_owner_verified=True)
