"""Persistent source-issued retaliation target and per-effect current authority.

Only the original accepted nonlethal feedback DRAINED producer issues a target.
Native command state is never a target or repeated-hit authority.
"""
from dataclasses import dataclass,field
import asyncio,time
from tools.local_original_session import attack,attack_session,npc_hp,npc_player_hit,npc_motion,player_life,movement
from tools.local_original_session import continuous_policy
need=attack.need

@dataclass(frozen=True,slots=True)
class TargetReceipt:
 issuer: object=field(repr=False)
 writer: object=field(repr=False)
 row: object=field(repr=False)
 game: object=field(repr=False)
 selection: object=field(repr=False)
 movement: object=field(repr=False)
 owner: object=field(repr=False)
 hp_lifetime: tuple=field(repr=False)
 life: object=field(repr=False)
 life_token: object=field(repr=False)
 lifecycle: object=field(repr=False)
 generation: object=field(repr=False)
 mover: object=field(repr=False)
 intent: object=field(repr=False)
 hp_result: object=field(repr=False)
 feedback: bytes=field(repr=False)
 binding: object=field(repr=False)
 runtime: object=field(repr=False)
 scenario: object=field(repr=False)
 stop: object=field(repr=False)
 issued_ns: int
 serial: int

 @property
 def target_uid(self):
  return self.hp_result.target.uid

@dataclass(frozen=True,slots=True)
class HitLease:
 issuer: object=field(repr=False)
 target: TargetReceipt=field(repr=False)
 context: object=field(repr=False)
 position: object=field(repr=False)
 npc_state: object=field(repr=False)
 snapshot: object=field(repr=False)
 identities: tuple=field(repr=False)
 values: tuple=field(repr=False)
 ordinal: int
 due_ns: int
 direction: int

@dataclass(frozen=True,slots=True)
class MotionLease:
 issuer: object=field(repr=False)
 target: TargetReceipt=field(repr=False)
 position: object=field(repr=False)
 snapshot: object=field(repr=False)
 state: object=field(repr=False)
 hp_entry: object=field(repr=False)
 goal: tuple
 due_ns: int

class InventoryLifetimeOwner:
 """Explicit transfer from command wrapper to the whole feature lifetime."""
 def __init__(self,controller,manual):
  from tools.local_original_session import launcher,inventory
  need(type(controller) is Controller and type(manual) is launcher.ManualMoveRequests
       and manual.inventory_broker is controller.broker
       and type(manual._inventory_owned_service) is inventory.InventoryService
       and manual._inventory_owned_service is controller.broker._inventory_service
       and not manual.closed,'CONTINUOUS_SHARED_INVENTORY_TRANSFER_REQUIRED')
  self.controller,self.manual,self.service=controller,manual,manual._inventory_owned_service
  self.claimed=False;self.closed=False;self.command_closed=False
 def claim(self,manual):
  need(manual is self.manual and not self.claimed and not self.closed
       and self.controller.broker._npc_continuous is self.controller
       and manual._inventory_owned_service is self.service
       and self.controller.broker._inventory_service is self.service and not self.service._closed,
       'CONTINUOUS_EXACT_SHARED_INVENTORY_OWNER_REQUIRED')
  self.claimed=True
 def require_current(self):
  need(self.claimed and not self.closed and self.controller.inventory_owner is self
       and self.manual._inventory_lifetime_owner is self
       and self.manual._inventory_owned_service is None
       and self.controller.broker._inventory_service is self.service and not self.service._closed,
       'CONTINUOUS_SHARED_INVENTORY_LIFETIME_REQUIRED')
 def command_close(self,manual):
  need(manual is self.manual and self.claimed and manual._inventory_lifetime_owner is self
       and manual._inventory_owned_service is None,'CONTINUOUS_COMMAND_CLOSE_OWNER_REQUIRED')
  self.command_closed=True
 def close(self):
  if self.closed:return
  self.closed=True
  self.service.close() # Original owner closes the real service exactly once here.

class Controller:
 def __init__(self,original,*,binding,runtime,scenario):
  from tools.local_original_session import launcher
  need(type(original) is launcher.ProductFeatures and type(binding) is continuous_policy.Binding,
       'CONTINUOUS_TYPED_RUNTIME_POLICY_REQUIRED')
  broker=original.npc_session.broker
  need(getattr(broker,'_npc_continuous',None) is None and type(broker._player_life) is player_life.Service
       and broker._player_life.policy.label==player_life.NPC_POLICY_LABEL
       and broker._player_life.policy.newlife==player_life.REPEATED_NEWLIFE_POLICY
       and type(broker._npc_player_hit) is npc_player_hit.Service
       and broker._npc_player_hit.policy==npc_player_hit.REPEATED_POLICY
       and broker._attack_session.accepted_count==0,'CONTINUOUS_COLD_LIFE_AND_HIT_REQUIRED')
  from tools.local_original_session import npc_continuous_retaliation_runtime
  need(type(runtime) is npc_continuous_retaliation_runtime.Runtime and runtime.original is original
       and runtime.scenario is scenario and scenario.target_runtime is runtime
       and type(scenario.stop) is asyncio.Event and not scenario.stop.is_set(),
       'CONTINUOUS_EXACT_RUNTIME_SCENARIO_STOP_REQUIRED')
  self.runtime,self.scenario,self.stop=runtime,scenario,scenario.stop
  self.original,self.broker,self.binding=original,broker,binding
  self.hit=broker._npc_player_hit;self.combat=broker._attack_session;self.life=broker._player_life
  self.target=None;self._issued=[];self._last_ordinal=0;self._serial=0
  self.closed=False;self.phase='WAIT_TARGET';self.reason=None;self.effects=[];self.retired_operations=[]
  self.lease=self.operation=None;self._busy=False;self._last_ns=None
  self.next_attack_ns=None;self.next_move_ns=None;self.next_action_ns=None;self.lethal=None;self.retired_lethal=None
  self._owned_goal=None;self.motion_lease=None;self.motion_step=None
  self.released_target=None;self.released_life_record=None
  broker._npc_continuous=self
  self.inventory_owner=InventoryLifetimeOwner(self,original.manual)
  original.manual.transfer_inventory_lifetime(self.inventory_owner)

 def _pure_current(self,target,*,allow_operation=False,motion_step=None,lethal_context=None):
  from tools.local_original_session import hp_status,hp_resource_owner,npc_respawn
  b=self.broker;r=b.realm;row=target.row;writer=target.writer
  own_lethal=(lethal_context is not None and self.lethal is not None
              and self.lethal.target is target and self.lethal.context is lethal_context
              and (self.target is target or self.reason=='PLAYER_DEAD' and self.target is None))
  need(type(target) is TargetReceipt and target.issuer is self and (self.target is target or own_lethal)
       and any(x is target for x in self._issued) and not self.closed
       and b._npc_continuous is self and self.binding is target.binding
       and target.runtime is self.runtime and target.scenario is self.scenario and target.stop is self.stop
       and self.runtime.controller is self and self.runtime.original is self.original
       and self.runtime.scenario is self.scenario and self.scenario.target_runtime is self.runtime
       and self.scenario.stop is target.stop and type(target.stop) is asyncio.Event
       and not target.stop.is_set() and not self.runtime.closed
       and b._npc_player_hit is r._npc_player_hit is self.hit
       and b._attack_session is r._attack_session is self.combat
       and not self.combat.closed and not self.combat.fatal and not self.hit.closed
       and self.combat._feedback_state=='DRAINED'
       and b._player_life is self.life is target.life and not self.life.closed
       and not b._closing and not b.failure.is_set() and b.policy.state=='OPEN'
       and not row['failed'] and not row['joined'] and row['operation_lock'].locked(),
       'CONTINUOUS_CURRENT_TARGET_REGISTRATION_REQUIRED')
  self.inventory_owner.require_current()
  rows=[x for claims in b._claims.values() for x in claims if x['writer'] is writer]
  admitted=b.policy._connection(writer)
  need(len(rows)==1 and rows[0] is row and row['policy_row'] is admitted
       and admitted.writer is writer and admitted.stage==1
       and not any((admitted.failed,admitted.eof,admitted.task_joined,admitted.registry_removed)),
       'CONTINUOUS_CURRENT_ROW_REQUIRED')
  current=r.registry.resolve(writer);service=r.service(writer);position=service.snapshot()
  need(current is target.game and current.selection is target.selection
       and r.registry.selected.get(position.name) is target.selection
       and service is target.movement and (position.uid,position.map_id)==(1,0)
       and not service.fatal and not writer.is_closing(),
       'CONTINUOUS_CURRENT_TARGET_SELECTION_REQUIRED')
  life_record=self.life._tokens.get(id(writer))
  need(life_record is not None and life_record[0] is writer and life_record[1] is target.selection
       and life_record[2] is target.life_token,'CONTINUOUS_CURRENT_PLAYER_LIFE_REQUIRED')
  cycle=self.life._cycles.get(id(writer))
  need((cycle is None or cycle.stage=='NEW_LIFE' and not cycle.terminal) if not own_lethal else
       (cycle is None or type(cycle) is player_life._Cycle and cycle.context is lethal_context and not cycle.terminal),
       'CONTINUOUS_PLAYER_DEAD_OR_PENDING')
  need(type(target.owner) is hp_resource_owner.ResourceOwner and target.owner.active
       and b._hp_resource_owner is target.owner and self.hit.status._resource_owner is target.owner
       and target.owner.status is self.hit.status and not target.owner.store.closed and not target.owner.store.failed,
       'CONTINUOUS_CURRENT_RESOURCE_OWNER_REQUIRED')
  snapshot=self.hit.status._states.get(id(writer))
  need(type(snapshot) is hp_status.Snapshot and snapshot._lifetime is target.hp_lifetime
       and (snapshot.current_hp>0 or own_lethal and snapshot.current_hp==0
            and cycle is not None and cycle.status is not None
            and cycle.status.result.after is snapshot),'CONTINUOUS_CURRENT_ALIVE_PLAYER_REQUIRED')
  lifecycle=b._npc_respawn;mover=attack.npc_mover(r,writer,target.target_uid)
  need(type(lifecycle) is npc_respawn.Service and lifecycle is target.lifecycle is r._npc_respawn
       and attack.registered_npc_generation(lifecycle,r,writer,target.target_uid) is target.generation
       and mover is target.mover is target.generation.mover
       and type(mover) is npc_motion.NpcMotion and mover.spawn_drained
       and not mover.closed and not mover.fatal and mover.pending is motion_step
       and (mover.state.uid,mover.state.map_id)==(target.target_uid,position.map_id),
       'CONTINUOUS_CURRENT_NPC_GENERATION_REQUIRED')
  return snapshot,position,mover

 def current_locked(self,target,*,allow_operation=False):
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  snapshot,position,mover=self._pure_current(target,allow_operation=allow_operation)
  require_owner_binding(self.broker,expected=target.owner,selected=True)
  row,actual,identities,values=self.hit._current(target.writer,source_uid=target.target_uid)
  need(row is target.row and actual is snapshot,'CONTINUOUS_CURRENT_SNAPSHOT_CHANGED')
  self.life.check_normal_locked(target.writer)
  self._pure_current(target,allow_operation=allow_operation)
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return snapshot,position,mover,identities,values

 def lethal_current_locked(self,target,life_context,npc_context=None):
  from tools.local_original_session import continuous_lethal,npc_player_lethal
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  need(type(self.lethal) is continuous_lethal.Cycle and self.lethal.target is target
       and self.lethal.context is life_context and not self.lethal.closed
       and life_context._service is self.life and self.life._contexts.get(id(target.writer)) is life_context,
       'CONTINUOUS_EXACT_OWN_LETHAL_LIFE_REQUIRED')
  if npc_context is not None:
   need(type(npc_context) is npc_player_lethal.Context and npc_context.continuous_target is target
        and npc_context.life_context is life_context and npc_context._service is self.broker._npc_player_lethal
        and npc_context._service._contexts.get(id(target.writer)) is npc_context,
        'CONTINUOUS_FROZEN_LETHAL_CONTEXT_REQUIRED')
  cycle=self.life._cycles.get(id(target.writer))
  if npc_context is None and self.lethal.attack_context is not None:npc_context=self.lethal.attack_context
  if cycle is not None:
   original=self.broker._npc_player_lethal.operation_for(target.writer)
   need(original is not None and original.context is npc_context and original.cycle is cycle
        and cycle.npc_attack is original and original.attack_transport=='DRAINED',
        'CONTINUOUS_EXACT_DRAINED_LETHAL_CYCLE_REQUIRED')
  self._pure_current(target,lethal_context=life_context)
  require_owner_binding(self.broker,expected=target.owner,selected=True)
  row,snapshot,_,_=self.hit._current(target.writer,source_uid=target.target_uid,player_life_context=life_context)
  self._pure_current(target,lethal_context=life_context)
  plan=self.lethal.plan
  need(row is target.row and self.life._contexts.get(id(target.writer)) is life_context
       and plan is not None and plan._continuous_authority is target and plan._continuous_target is target
       and plan.session is self.original.npc_session and not plan.closed
       and self.broker.realm.service(target.writer).snapshot() is life_context._position,
       'CONTINUOUS_FINAL_LETHAL_BINDING_CHANGED')
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return self

 def motion_current_locked(self,writer,row,lease,step=None,wire=None):
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  need(type(lease) is MotionLease and self.motion_lease is lease and lease.issuer is self
       and lease.target is self.target and writer is lease.target.writer and row is lease.target.row
       and self.phase=='TARGET_ACTIVE' and self._owned_goal==(lease.target,lease.goal)
       and self.original.npc_session._goal is lease.goal
       and self.original.npc_session._generation is lease.target.generation,
       'CONTINUOUS_LITERAL_CURRENT_MOTION_LEASE_REQUIRED')
  if step is not None:
   need(self.motion_step is step and step.before is lease.state and step.after.goal is lease.goal,
        'CONTINUOUS_EXACT_MOTION_OPERATION_REQUIRED')
  snapshot,position,mover=self._pure_current(lease.target,motion_step=step)
  require_owner_binding(self.broker,expected=lease.target.owner,selected=True)
  if step is None:self.combat.require_live_npc_motion(writer,row,mover.state.uid)
  else:
   attack.source_ready()
   if self.combat._notifications is not None:
    need(not self.combat._notifications.is_removed(writer,mover.state.uid),'NPC_HP_DEAD_MOTION_REFUSED')
   projection=self.combat.targets._project(writer,attack.AttackRequest(mover.state.uid),_motion_lease=lease)
   need(projection[0] is row,'CONTINUOUS_MOTION_CURRENT_PROJECTED_ROW_REQUIRED')
   lifetime,source=self.combat._hp_binding(writer,row,mover.state.uid)
   need(type(lease.hp_entry) is npc_hp._Entry and self.combat._hp._entries.get((id(writer),source.uid)) is lease.hp_entry,
        'CONTINUOUS_REGISTERED_LIVE_HP_ENTRY_REQUIRED')
   self.combat._hp._require_alive(writer,row,lifetime,source)
  self.life.check_normal_locked(writer)
  if wire is not None:need(step is not None and wire is step.frame,'CONTINUOUS_EXACT_MOTION_FRAME_REQUIRED')
  checked_ns=time.monotonic_ns()
  # Callback-bearing checks precede final pure registrations and effect state.
  snapshot,position,mover=self._pure_current(lease.target,motion_step=step)
  need(self.motion_lease is lease and self.motion_step is step and self.target is lease.target
       and snapshot is lease.snapshot and position is lease.position and mover.state is lease.state
       and self.original.npc_session._goal is lease.goal and self.phase=='TARGET_ACTIVE'
       and self.combat._hp._entries.get((id(writer),mover.state.uid)) is lease.hp_entry
       and lease.hp_entry.hp.alive
       and lease.due_ns==self.next_action_ns and checked_ns>=lease.due_ns,'CONTINUOUS_MOTION_AUTHORITY_CHANGED')
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return self

 def bind_motion_locked(self,writer,row,lease,step):
  self.motion_current_locked(writer,row,lease)
  need(self.motion_step is None and step.before is lease.state,'CONTINUOUS_FRESH_MOTION_OPERATION_REQUIRED')
  self.motion_step=step

 def feedback_drained_locked(self,writer,row,session,intent,wire,*,now_ns):
  """Synchronous, no send/query/await: consume the exact original drain event."""
  need(not self.closed and self.broker._npc_continuous is self and row['operation_lock'].locked()
       and self.combat is session is self.broker._attack_session
       and session._current is session._feedback_intent is intent and session._feedback_frame is wire
       and session._feedback_state=='DRAINED' and intent._bound._writer is writer
       and intent.accepted_ordinal==session.accepted_count and type(now_ns) is int and now_ns>=0,
       'CONTINUOUS_LITERAL_FEEDBACK_EVENT_REQUIRED')
  if intent.accepted_ordinal==self._last_ordinal:return self.target
  need(intent.accepted_ordinal>self._last_ordinal,'CONTINUOUS_FEEDBACK_EVENT_ORDER_REQUIRED')
  result=session.last_hp_result
  uid=intent._bound.request.target_uid
  recipe=attack.npc_recipe(self.broker.realm,uid)
  need(intent._bound.target_uid==uid,'CONTINUOUS_REQUEST_TARGET_UID_REQUIRED')
  need(type(result) is npc_hp.Result and result.accepted_ordinal==intent.accepted_ordinal
       and result.target==npc_hp.Target(uid,recipe.map_id,recipe.fields[3],recipe.fields[39]),'CONTINUOUS_LITERAL_HP_EVENT_REQUIRED')
  self._last_ordinal=intent.accepted_ordinal
  if result.died:
   if self.target is not None and self.target.target_uid==uid:self.retire('NPC_DEAD')
   return None
  need(result.hit.landed and result.hit.damage==1 and result.after.alive,
       'CONTINUOUS_ACCEPTED_NONLETHAL_REQUIRED')
  realm=self.broker.realm;game=realm.registry.resolve(writer);move=realm.service(writer)
  snapshot=self.hit.status._states.get(id(writer));owner=self.broker._hp_resource_owner
  self.inventory_owner.require_current()
  lifecycle=self.broker._npc_respawn;generation=attack.npc_generation(lifecycle,realm,writer,uid)
  if self.target is not None:
   current=self.target
   if (current.writer is writer and current.selection is game.selection and current.target_uid==uid
       and current.generation is generation and current.life_token is self.life.token(writer)):
    self._pure_current(current);return current # A new hit does not reset attack cadence.
   need(not self._busy and self.operation is None and self.motion_step is None and self.lethal is None
        and current.mover.pending is None, 'CONTINUOUS_TARGET_SWITCH_IN_FLIGHT_REFUSED')
   self.retire('TARGET_SELECTION_OR_GENERATION_REPLACED')
   need(self.original.npc_session._goal is None,'CONTINUOUS_TARGET_SWITCH_OLD_GOAL_REQUIRED')
  need(snapshot is not None and snapshot.current_hp>0 and owner is self.hit.status._resource_owner
       and owner.active and result.after==npc_hp.Hp(1,2) and result.before==npc_hp.Hp(2,2),
       'CONTINUOUS_EXPLICIT_FIRST_EVENT_BINDING_REQUIRED')
  self.original.npc_session.select_target(uid,generation=generation)
  self._serial+=1
  receipt=TargetReceipt(self,writer,row,game,game.selection,move,owner,snapshot._lifetime,
   self.life,self.life.token(writer),lifecycle,generation,attack.npc_mover(realm,writer,uid),intent,result,wire,
   self.binding,self.runtime,self.scenario,self.stop,now_ns,self._serial)
  self.target=receipt;self._issued.append(receipt)
  try:self._pure_current(receipt)
  except BaseException:
   self.target=None;raise
  self.phase='TARGET_ACTIVE';self.reason=None;self.effects=[]
  self.next_attack_ns=now_ns;self.next_move_ns=now_ns;self.next_action_ns=now_ns;self.lease=self.operation=None
  return receipt

 def validate_locked(self,writer,row,lease,context,operation=None):
  need(type(lease) is HitLease and lease is self.lease and lease.issuer is self
       and lease.target is self.target and lease.context is context
       and self.phase=='ATTACKING' and lease.ordinal==len(self.effects)+1,
       'CONTINUOUS_LITERAL_ONCE_HIT_LEASE_REQUIRED')
  snapshot,position,mover,identities,values=self.current_locked(lease.target,allow_operation=True)
  expected=lease.snapshot
  if operation is not None:
   need(type(operation) is npc_player_hit._Prepared and operation is self.operation
        and self.hit.operation_for(writer) is operation and operation.context is context,
        'CONTINUOUS_LITERAL_EFFECT_OPERATION_REQUIRED')
   if operation.hp_operation is not None:expected=operation.hp_operation.result.after
  need(writer is lease.target.writer and row is lease.target.row and snapshot is expected
       and position is lease.position and mover.state is lease.npc_state
       and len(identities)==len(lease.identities) and all(a is b for a,b in zip(identities,lease.identities))
       and values==(*lease.values[:3],snapshot.revision,*lease.values[4:]),
       'CONTINUOUS_EFFECT_AUTHORITY_CHANGED')
  from tools.local_original_session.npc_approach_hit import melee_geometry
  _,direction=melee_geometry(movement.authority.unpack_grid(mover.state.packed),(position.word0,position.word1))
  need(direction==lease.direction and lease.due_ns==self.next_action_ns and time.monotonic_ns()>=lease.due_ns,
       'CONTINUOUS_CURRENT_RANGE_AND_CADENCE_REQUIRED')
  self._pure_current(lease.target,allow_operation=True)
  need(self.lease is lease and self.phase=='ATTACKING'
       and self.hit.status._states.get(id(writer)) is expected
       and mover.state is lease.npc_state and (operation is None or self.operation is operation),
       'CONTINUOUS_FINAL_EFFECT_REGISTRATION_CHANGED')
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return self

 def bind_operation_locked(self,writer,row,lease,context,operation):
  self.validate_locked(writer,row,lease,context)
  need(self.operation is None and self.hit.operation_for(writer) is operation
       and operation.context is context and operation.phase=='PREPARED_AUTHORITY_ONLY',
       'CONTINUOUS_NEW_ORIGINAL_OPERATION_REQUIRED')
  self.operation=operation

 async def positive(self,target,*,now_ns):
  need(self.phase=='TARGET_ACTIVE' and self.target is target and self.lease is None
       and now_ns>=self.next_attack_ns,'CONTINUOUS_DUE_TARGET_REQUIRED')
  writer,row=target.writer,target.row
  async with self.broker._row_operation(writer,row):
   await self.broker._checkpoint(writer,row) # New actual owner sample for each automatic effect.
   snapshot,position,mover,_,_=self.current_locked(target)
   need(snapshot.current_hp>1,'CONTINUOUS_LETHAL_BOUNDARY_REQUIRED')
   from tools.local_original_session.npc_approach_hit import melee_geometry
   _,direction=melee_geometry(movement.authority.unpack_grid(mover.state.packed),(position.word0,position.word1))
  context=await self.broker.npc_player_hit_repeated_context(writer,policy=npc_player_hit.REPEATED_POLICY,target_uid=target.target_uid)
  async with self.broker._row_operation(writer,row):
   snapshot,position,mover,identities,values=self.current_locked(target)
   self.hit.validate_locked(writer,context)
   need(context.snapshot is snapshot and self.phase=='TARGET_ACTIVE' and self.lease is None,
        'CONTINUOUS_FRESH_CURRENT_CONTEXT_REQUIRED')
   lease=HitLease(self,target,context,position,mover.state,snapshot,identities,values,
                  len(self.effects)+1,self.next_attack_ns,direction)
   self.lease=lease;self.operation=None;self.phase='ATTACKING'
  try:
   result=await self.broker.attack_player_repeated(writer,expected_context=context,raw_effect=1,direction=direction,
     policy=npc_player_hit.REPEATED_POLICY,continuous_lease=lease)
   async with self.broker._row_operation(writer,row):
    self.validate_locked(writer,row,lease,context,self.operation);result.require_current_locked(writer)
    need(result.after.current_hp==snapshot.current_hp-1,'CONTINUOUS_EXACT_POSITIVE_RESULT_REQUIRED')
    self.effects.append(result)
    self.next_action_ns=time.monotonic_ns()+self.binding.attack_ns
    self.next_attack_ns=self.next_move_ns=self.next_action_ns
    self.lease=self.operation=None;self.phase='TARGET_ACTIVE'
   return result
  except BaseException:
   self.retire('EFFECT_UNKNOWN');raise # Keep original attempted/drained histories.

 async def poll(self,*,now_ns,monitor):
  need(type(now_ns) is int and now_ns>=0,'CONTINUOUS_EXPLICIT_POLL_CLOCK_REQUIRED')
  if self.closed or self._busy:return self.metadata()
  if self.stop.is_set():self.retire('CANCELLED');return self.metadata()
  if self._last_ns is not None:
   need(now_ns>=self._last_ns,'CONTINUOUS_MONOTONIC_CLOCK_REQUIRED')
   if now_ns==self._last_ns:return self.metadata()
  self._last_ns=now_ns
  if self.lethal is not None:
   self._busy=True
   try:await self.lethal.poll(now_ns=now_ns,monitor=monitor)
   except BaseException:
    self.retire('LETHAL_OUTCOME_UNKNOWN');raise
   finally:self._busy=False
   return self.metadata()
  target=self.target
  if target is None:return self.metadata()
  self._busy=True
  try:
   writer,row=target.writer,target.row
   # No current owner cache is promoted into a new tick. The original broker
   # sample/checkpoint refreshes process/peer/Job/owner authority under scope.
   async with self.broker._row_operation(writer,row):
    await self.broker._checkpoint(writer,row)
    snapshot,position,mover,_,_=self.current_locked(target)
    grid=movement.authority.unpack_grid(mover.state.packed)
    player=(position.word0,position.word1)
    distance=max(abs(a-b) for a,b in zip(grid,player))
   if now_ns<self.next_action_ns:return self.metadata()
   if distance!=1:
    if distance==0:self.retire('OVERLAPPING_TARGET');return self.metadata()
    if now_ns<self.next_move_ns:return self.metadata()
    # The original session owns every admitted edge and original MOVE drain.
    # Select the current player's neighbouring cell; no free/fake edge binding.
    delta=tuple((b>a)-(b<a) for a,b in zip(grid,player))
    goal=tuple(v-d for v,d in zip(player,delta))
    session=self.original.npc_session
    need(session.current_binding() is not None,'CONTINUOUS_CURRENT_MOTION_SESSION_REQUIRED')
    need(session._goal is None or self._owned_goal is not None
         and self._owned_goal[0] is target and self._owned_goal[1] is session._goal,
         'CONTINUOUS_FOREIGN_GOAL_REFUSED')
    if session._goal!=goal:
     session.submit_goal(goal=goal);self._owned_goal=(target,goal)
    else:
     need(self._owned_goal is not None and self._owned_goal[0] is target
          and self._owned_goal[1] is session._goal,'CONTINUOUS_FOREIGN_GOAL_REFUSED')
     goal=session._goal
    lease=MotionLease(self,target,position,snapshot,mover.state,
                      self.combat._hp._entries.get((id(writer),mover.state.uid)),goal,self.next_move_ns)
    self.motion_lease=lease;self.motion_step=None
    need(monitor is not None,'CONTINUOUS_ORIGINAL_QUERY_MONITOR_REQUIRED')
    if now_ns/1e9<monitor.next_memory:
     self.motion_lease=None
     return self.metadata()
    monitor.next_memory=max(monitor.next_memory,now_ns/1e9+.5)
    try:outcome=await session.tick(now_ns=now_ns,continuous_motion_lease=lease)
    finally:monitor.next_memory=max(monitor.next_memory,time.monotonic()+.5)
    need(outcome.status in ('MOVED','AT_GOAL','CADENCE','OBSERVATION_CADENCE'),
         'CONTINUOUS_ORIGINAL_APPROACH_NOT_COMMITTED')
    self.motion_lease=self.motion_step=None
    if outcome.status=='MOVED':
     self.next_action_ns=time.monotonic_ns()+self.binding.move_ns
     self.next_attack_ns=self.next_move_ns=self.next_action_ns
    async with self.broker._row_operation(writer,row):
     await self.broker._checkpoint(writer,row);self.current_locked(target)
    return self.metadata() # Never move and attack in the same scheduled slot.
   if now_ns<self.next_attack_ns:return self.metadata()
   if snapshot.current_hp==1:
    from tools.local_original_session import continuous_lethal
    self.lethal=continuous_lethal.Cycle(self,target)
    await self.lethal.poll(now_ns=now_ns,monitor=monitor)
   else:await self.positive(target,now_ns=now_ns)
   return self.metadata() # No catch-up loop after a late poll.
  except asyncio.CancelledError:
   self.retire('CANCELLED');raise
  except BaseException:
   self.retire('CURRENT_TARGET_OR_EFFECT_UNKNOWN');raise
  finally:self._busy=False

 def release_player(self,life,writer):
  """Consume the real Service.release event before its exact life token is removed.

  AttackSession may already be released. Do not query current combat/world here.
  """
  target=self.target
  if target is None:
   target=next((issued for issued in reversed(self._issued) if issued.writer is writer),None)
  if target is None or target.writer is not writer:return False
  record=life._tokens.get(id(writer))
  need(life is self.life is target.life and life.broker is self.broker
       and self.broker._npc_continuous is self and not self.closed
       and type(target) is TargetReceipt and target.issuer is self
       and any(target is issued for issued in self._issued),'CONTINUOUS_REAL_PLAYER_RELEASE_REQUIRED')
  if (record is None or record[0] is not writer or record[1] is not target.selection
      or record[2] is not target.life_token):return False
  self.retire('PLAYER_SELECTION_RELEASED')
  self.original.npc_session.release_continuous_targets(self,writer)
  self.released_target=target;self.released_life_record=record
  return True

 def retire(self,reason):
  owned=self._owned_goal
  try:
   if owned is not None:self.original.npc_session.retire_continuous_goal(*owned)
  except Exception as error:
   self.cleanup_error=type(error).__name__ # Preserve the triggering failure.
  finally:
   self._owned_goal=None
   self.reason=reason;self.target=None;self.phase='TARGET_RETIRED'
   if self.operation is not None:self.retired_operations.append(self.operation)
   self.lease=self.operation=None;self.motion_lease=self.motion_step=None
   if self.lethal is not None and reason!='PLAYER_DEAD':
    self.retired_lethal=self.lethal;self.lethal.close()
   if reason!='PLAYER_DEAD':self.lethal=None
 def close(self):
  if self.closed:return
  self.closed=True
  try:self.retire('FEATURE_CLOSED')
  finally:self.inventory_owner.close()

 def metadata(self):
  return dict(policy=self.binding.policy,phase=self.phase,reason=self.reason,
   target_serial=None if self.target is None else self.target.serial,
   target_uid=None if self.target is None else self.target.target_uid,
   committed_hits=len(self.effects),next_attack_ns=self.next_attack_ns,next_action_ns=self.next_action_ns,
   hp=None if not self.effects else self.effects[-1].after.current_hp,
   lethal=None if self.lethal is None else self.lethal.metadata(),
   retired_lethal=None if self.retired_lethal is None else self.retired_lethal.metadata(),
   partial_history=[dict(phase=op.phase,attack_transport=op.attack_transport,hp_transport=op.hp_transport)
                    for op in self.retired_operations],
   client_action='UNKNOWN',client_hp='UNKNOWN',official_mapping='UNKNOWN')

def feedback_drained(broker,writer,row,session,intent,wire,*,now_ns):
 controller=getattr(broker,'_npc_continuous',None)
 need(type(controller) is Controller and controller.broker is broker,'CONTINUOUS_REGISTERED_PRODUCT_REQUIRED')
 return controller.feedback_drained_locked(writer,row,session,intent,wire,now_ns=now_ns)

def validate(broker,writer,row,lease,context,operation=None):
 need(type(lease) is HitLease and type(lease.issuer) is Controller and lease.issuer.broker is broker
      and broker._npc_continuous is lease.issuer,'CONTINUOUS_REGISTERED_LITERAL_LEASE_REQUIRED')
 return lease.issuer.validate_locked(writer,row,lease,context,operation)


def validate_motion(broker,writer,row,lease,step=None,wire=None):
 need(type(lease) is MotionLease and type(lease.issuer) is Controller
      and lease.issuer.broker is broker and broker._npc_continuous is lease.issuer,
      'CONTINUOUS_REGISTERED_LITERAL_MOTION_REQUIRED')
 return lease.issuer.motion_current_locked(writer,row,lease,step,wire)


def validate_lethal(broker,writer,row,context):
 target=context.continuous_target
 need(type(target) is TargetReceipt and type(target.issuer) is Controller
      and target.issuer.broker is broker and broker._npc_continuous is target.issuer
      and target.writer is writer and target.row is row,
      'CONTINUOUS_REGISTERED_FROZEN_LETHAL_REQUIRED')
 return target.issuer.lethal_current_locked(target,context.life_context,context)
