"""Persistent source-issued retaliation target and per-effect current authority.

Only the original accepted nonlethal feedback DRAINED producer issues a target.
Native command state is never a target or repeated-hit authority.
"""
from dataclasses import dataclass,field
import asyncio,time
from tools.local_original_session import attack,attack_session,npc_hp,npc_player_hit,npc_motion,player_life,movement
from tools.local_original_session import continuous_policy
need=attack.need

def require_resource_npc_pc(broker,binding,*,writer=None):
 """Actual named RESOURCE counter owners; not a life/PRE or current cap."""
 from tools.local_original_session import combat_adapters,combat_selected_stats,hp_resource_owner,hp_status
 need(type(binding) is continuous_policy.Binding and binding.life_policy is None
      and binding.resource_npc_pc_policy==combat_adapters.NPC_PC_RESOURCE_BASE_POLICY
      and type(binding.resource_npc_pc_policy) is str
      and broker._player_life is None and getattr(broker.realm,'_player_life_broker',None) is None,
      'CONTINUOUS_RESOURCE_NAMED_NO_LIFE_REQUIRED')
 hit=broker._npc_player_hit;owner=broker._hp_resource_owner
 stats=getattr(owner,'_combat_stats',None)
 need(type(hit) is npc_player_hit.Service and broker.realm._npc_player_hit is hit
      and hit.broker is broker and hit.combat is broker._attack_session
      and hit.policy==npc_player_hit.REPEATED_POLICY
      and hit.status.repeated_policy==hp_status.REPEATED_POLICY
      and type(hit.adjudicator) is combat_adapters.NpcPcAdjudicator
      and hit.adjudicator.resource_npc_pc_policy==binding.resource_npc_pc_policy
      and hit.adjudicator.recovery_inputs_locked is None
      and type(owner) is hp_resource_owner.ResourceOwner and owner.status is hit.status
      and (hit.status._resource_owner is None or hit.status._resource_owner is owner)
      and type(stats) is combat_selected_stats.SelectedStatsSource
      and stats.owner is owner and stats.broker is broker and stats.resource_only_stats is True
      and owner.skill_schema is None and getattr(broker,'_buff_lifecycle',None) is None,
      'CONTINUOUS_RESOURCE_ACTUAL_COUNTER_OWNERS_REQUIRED')
 if writer is not None:
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  require_owner_binding(broker,expected=owner,selected=True)
  rows=[r for claims in broker._claims.values() for r in claims if r['writer'] is writer]
  need(len(rows)==1 and rows[0]['operation_lock'].locked(),
       'CONTINUOUS_RESOURCE_CURRENT_OWNED_ROW_REQUIRED')
  snapshot=hit.status.current(writer)
  need(type(snapshot) is hp_status.Snapshot and snapshot._service is hit.status
       and snapshot.current_hp>0,'CONTINUOUS_RESOURCE_CURRENT_ALIVE_REQUIRED')
 return owner

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
 aggro: object=field(default=None,repr=False)

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

@dataclass(slots=True)
class AggroState:
 writer: object=field(repr=False)
 uid: int
 generation: object=field(repr=False)
 target: object=field(default=None,repr=False)
 phase: str='WAIT_TARGET'
 reason: object=None
 effects: list=field(default_factory=list,repr=False)
 retired_operations: list=field(default_factory=list,repr=False)
 lease: object=field(default=None,repr=False)
 operation: object=field(default=None,repr=False)
 motion_lease: object=field(default=None,repr=False)
 motion_step: object=field(default=None,repr=False)
 owned_goal: object=field(default=None,repr=False)
 lethal: object=field(default=None,repr=False)
 next_attack_ns: object=None
 next_move_ns: object=None
 next_action_ns: object=None
 quiesced: bool=False
 last_feedback: object=field(default=None,repr=False)

class Controller:
 def __init__(self,original,*,binding,runtime,scenario,packet_runtime=None):
  self.packet_runtime=packet_runtime
  if packet_runtime is None:
   from tools.local_original_session import launcher
   need(type(original) is launcher.ProductFeatures and type(binding) is continuous_policy.Binding,
        'CONTINUOUS_TYPED_RUNTIME_POLICY_REQUIRED')
  else:
   from npc_packet_runtime import PacketNpcRuntime
   need(type(packet_runtime) is PacketNpcRuntime and original is runtime is scenario is packet_runtime
        and packet_runtime.controller is None and type(binding) is continuous_policy.Binding,
        'CONTINUOUS_TYPED_PACKET_RUNTIME_REQUIRED')
  self.npc_session=original.npc_session
  broker=self.npc_session.broker
  self.resource_npc_pc=binding.resource_npc_pc_policy is not None
  if self.resource_npc_pc:
   need(packet_runtime is not None,'CONTINUOUS_RESOURCE_PACKET_RUNTIME_REQUIRED')
   require_resource_npc_pc(broker,binding)
   need(getattr(broker,'_npc_continuous',None) is None
        and broker._attack_session.accepted_count==0,'CONTINUOUS_COLD_LIFE_AND_HIT_REQUIRED')
  else:
   need(getattr(broker,'_npc_continuous',None) is None and type(broker._player_life) is player_life.Service
        and broker._player_life.policy.label==player_life.NPC_POLICY_LABEL
        and broker._player_life.policy.newlife==player_life.REPEATED_NEWLIFE_POLICY
        and type(broker._npc_player_hit) is npc_player_hit.Service
        and broker._npc_player_hit.policy==npc_player_hit.REPEATED_POLICY
        and broker._attack_session.accepted_count==0,'CONTINUOUS_COLD_LIFE_AND_HIT_REQUIRED')
  if packet_runtime is None:
   from tools.local_original_session import npc_continuous_retaliation_runtime
   need(type(runtime) is npc_continuous_retaliation_runtime.Runtime and runtime.original is original
        and runtime.scenario is scenario and scenario.target_runtime is runtime,
        'CONTINUOUS_EXACT_RUNTIME_SCENARIO_STOP_REQUIRED')
  need(type(scenario.stop) is asyncio.Event and not scenario.stop.is_set(),
       'CONTINUOUS_EXACT_RUNTIME_SCENARIO_STOP_REQUIRED')
  self.runtime,self.scenario,self.stop=runtime,scenario,scenario.stop
  self.original,self.broker,self.binding=original,broker,binding
  self.hit=broker._npc_player_hit;self.combat=broker._attack_session;self.life=broker._player_life
  self._states={};self._last_request_uid=None;self._issued=[];self._last_ordinal=0;self._serial=0
  self.closed=False;self.phase='WAIT_TARGET';self.reason=None;self.effects=[];self.retired_operations=[]
  self._busy=False;self._last_ns=None;self._poll_cursor=0;self._poll_next_key=None
  self.lethal=None;self.retired_lethal=None
  self._quiesced=None;self.released_targets=()
  self.released_target=None;self.released_life_record=None
  broker._npc_continuous=self
  if packet_runtime is None:
   self.inventory_owner=InventoryLifetimeOwner(self,original.manual)
   original.manual.transfer_inventory_lifetime(self.inventory_owner)
  else:
   self.inventory_owner=packet_runtime.inventory_borrow

 def _require_runtime_lifetime(self,writer,*,target=None,allow_operation=False,motion_step=None):
  if self.packet_runtime is None:
   need(self.original.npc_session is self.npc_session,'CONTINUOUS_SAME_NATIVE_SESSION_REQUIRED')
   return self.inventory_owner.require_current()
  need(self.runtime is self.original is self.scenario is self.packet_runtime
       and self.packet_runtime.controller is self
       and self.inventory_owner is self.packet_runtime.inventory_borrow
       and self.npc_session is self.packet_runtime.npc_session,
       'CONTINUOUS_SAME_PACKET_LIFETIME_REQUIRED')
  return self.inventory_owner.require_current(writer,target=target,
   allow_operation=allow_operation,motion_step=motion_step)

 def _life_token(self,writer):
  if self.resource_npc_pc:
   require_resource_npc_pc(self.broker,self.binding)
   return None
  return self.life.token(writer)

 def target_for(self,uid):
  active=[s.target for s in self._states.values() if s.uid==uid and s.target is not None]
  need(len(active)<=1,'CONTINUOUS_AMBIGUOUS_NPC_UID')
  return active[0] if active else None

 @property
 def target(self):
  """Last player request display only; never another NPC's aggro authority."""
  return self.target_for(self._last_request_uid)

 def active_targets(self):
  return tuple(s.target for s in self._states.values() if s.target is not None)

 def state_for_exact_receipt(self,target,*,allow_retired_lethal=False):
  need(type(target) is TargetReceipt and target.issuer is self and type(target.aggro) is AggroState,
       'CONTINUOUS_TYPED_AGGRO_RECEIPT_REQUIRED')
  state=target.aggro
  need(self._states.get((id(target.writer),target.target_uid)) is state
       and state.writer is target.writer and state.uid==target.target_uid
       and state.generation is target.generation
       and (state.target is target or allow_retired_lethal and state.reason=='PLAYER_DEAD'
            and self.lethal is not None and self.lethal.target is target),
       'CONTINUOUS_REGISTERED_AGGRO_LEAF_REQUIRED')
  return state

 def quiesce_player(self,runtime,writer,life_token):
  need(runtime is self.runtime and not self._busy and not self.closed
       and self._life_token(writer) is life_token,'CONTINUOUS_CURRENT_PLAYER_QUIESCE_REQUIRED')
  targets=tuple(t for t in self.active_targets() if t.writer is writer and t.life_token is life_token)
  for target in targets:
   state=self.state_for_exact_receipt(target)
   need(target.row['operation_lock'].locked(),'CONTINUOUS_QUIESCE_OWNED_ROW_REQUIRED')
   self.current_locked(target)
   lane=self.npc_session.lane_for(target.target_uid)
   need(lane.goal is None or state.owned_goal==(target,lane.goal),'CONTINUOUS_QUIESCE_FOREIGN_GOAL_REFUSED')
   need(state.lease is state.operation is state.motion_lease is state.motion_step is state.lethal is None,
        'CONTINUOUS_QUIESCE_IN_FLIGHT_REFUSED')
  for target in targets:
   state=self.state_for_exact_receipt(target)
   if state.owned_goal is not None:self.npc_session.retire_continuous_goal(*state.owned_goal)
   state.owned_goal=None;state.quiesced=True
  self._quiesced=(writer,life_token,targets)
  return targets

 def retire_generation(self,writer,generation,reason='NPC_GENERATION_REPLACED'):
  state=self._states.get((id(writer),generation.recipe.uid))
  if state is None:
   return self.npc_session.retire_generation(writer,generation)
  if state.writer is not writer or state.generation is not generation:return False
  self._retire_state(state,reason)
  self._states.pop((id(writer),state.uid),None)
  self.npc_session.retire_generation(writer,generation)
  return True

 def retire_dead_npc(self,writer,uid,notifications,record):
  from tools.local_original_session import npc_death
  need(type(notifications) is npc_death.Notifications and notifications is self.combat._notifications
       and notifications._records.get((id(writer),uid)) is record
       and record.entry.writer is writer and record.entry.target.uid==uid
       and self.combat._hp._entries.get((id(writer),uid)) is record.entry
       and not record.entry.hp.alive and record.result.died,
       'CONTINUOUS_SOURCE_NPC_DEATH_REQUIRED')
  state=self._states.get((id(writer),uid))
  lane=self.npc_session._lanes.get(uid)
  generation=state.generation if state is not None else None if lane is None else lane.generation
  if generation is not None:
   need(generation.writer is writer and generation.recipe.uid==uid
        and attack.registered_npc_generation(self.broker._npc_respawn,self.broker.realm,writer,uid) is generation
        and record.entry.lifetime[5] is generation.frames,'CONTINUOUS_SOURCE_NPC_DEATH_GENERATION_REQUIRED')
   self.retire_generation(writer,generation,'NPC_DEAD')

 def _pure_current(self,target,*,allow_operation=False,motion_step=None,lethal_context=None):
  state=self.state_for_exact_receipt(target,allow_retired_lethal=lethal_context is not None)
  from tools.local_original_session import hp_status,hp_resource_owner,npc_respawn
  b=self.broker;r=b.realm;row=target.row;writer=target.writer
  own_lethal=(lethal_context is not None and self.lethal is not None
              and self.lethal.target is target and self.lethal.context is lethal_context
              and (state.target is target or state.reason=='PLAYER_DEAD' and state.target is None))
  need(type(target) is TargetReceipt and target.issuer is self and (state.target is target or own_lethal)
       and any(x is target for x in self._issued) and not self.closed
       and b._npc_continuous is self and self.binding is target.binding
       and target.runtime is self.runtime and target.scenario is self.scenario and target.stop is self.stop
       and self.runtime.controller is self
       and ((self.packet_runtime is None and self.runtime.original is self.original
             and self.runtime.scenario is self.scenario and self.scenario.target_runtime is self.runtime)
            or self.packet_runtime is self.runtime is self.original is self.scenario)
       and self.scenario.stop is target.stop and type(target.stop) is asyncio.Event
       and not target.stop.is_set() and not self.runtime.closed
       and b._npc_player_hit is r._npc_player_hit is self.hit
       and b._attack_session is r._attack_session is self.combat
       and not self.combat.closed and not self.combat.fatal and not self.hit.closed
       and ((self.resource_npc_pc and b._player_life is self.life is target.life is None
             and target.life_token is None)
            or not self.resource_npc_pc and b._player_life is self.life is target.life and not self.life.closed)
       and not b._closing and not b.failure.is_set() and b.policy.state=='OPEN'
       and not row['failed'] and not row['joined'] and row['operation_lock'].locked(),
       'CONTINUOUS_CURRENT_TARGET_REGISTRATION_REQUIRED')
  self._require_runtime_lifetime(writer,target=target,allow_operation=allow_operation,motion_step=motion_step)
  rows=[x for claims in b._claims.values() for x in claims if x['writer'] is writer]
  admitted=b.policy._connection(writer)
  need(len(rows)==1 and rows[0] is row and row['policy_row'] is admitted
       and admitted.writer is writer and admitted.stage==1
       and not any((admitted.failed,admitted.eof,admitted.task_joined,admitted.registry_removed)),
       'CONTINUOUS_CURRENT_ROW_REQUIRED')
  current=r.registry.resolve(writer);service=r.service(writer);position=service.snapshot()
  need(current is target.game and current.selection is target.selection
       and r.registry.selected.get(position.name) is target.selection
       and service is target.movement
       and ((position.uid,position.map_id)==(1,0) if self.packet_runtime is None else
            (position.uid,position.map_id)==(target.intent._bound.attacker.uid,target.intent._bound.attacker.map_id))
       and not service.fatal and not writer.is_closing(),
       'CONTINUOUS_CURRENT_TARGET_SELECTION_REQUIRED')
  if self.resource_npc_pc:
   need(lethal_context is None and not own_lethal,'CONTINUOUS_RESOURCE_LETHAL_UNSUPPORTED')
   require_resource_npc_pc(b,self.binding)
   cycle=None
  else:
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
  if not self.resource_npc_pc:self.life.check_normal_locked(target.writer)
  self._pure_current(target,allow_operation=allow_operation)
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return snapshot,position,mover,identities,values

 def lethal_current_locked(self,target,life_context,npc_context=None):
  need(not self.resource_npc_pc,'CONTINUOUS_RESOURCE_LETHAL_OR_LIFE_UNSUPPORTED')
  from tools.local_original_session import continuous_lethal,npc_player_lethal
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  need(type(self.lethal) is continuous_lethal.Cycle and self.lethal.target is target
       and self.lethal.context is life_context and not self.lethal.closed
       and life_context._service is self.life and self.life._contexts.get(id(target.writer)) is life_context,
       'CONTINUOUS_EXACT_OWN_LETHAL_LIFE_REQUIRED')
  if self.lethal.adjudicated_operation is not None:
   return self._adjudicated_current_locked(target,life_context,npc_context)
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
       and plan.session is self.npc_session and not plan.closed
       and self.broker.realm.service(target.writer).snapshot() is life_context._position,
       'CONTINUOUS_FINAL_LETHAL_BINDING_CHANGED')
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return self

 def begin_adjudicated_lethal_locked(self,lease,operation,context):
  need(not self.resource_npc_pc,'CONTINUOUS_RESOURCE_LETHAL_OR_LIFE_UNSUPPORTED')
  need(self.packet_runtime is None,'PACKET_NPC_TYPED_PRE_INPUT_UNSUPPLIED')
  from tools.local_original_session import continuous_lethal
  target=lease.target;state=self.state_for_exact_receipt(target)
  self.validate_locked(target.writer,target.row,lease,operation.context,operation)
  need(self.lethal is None and state.lethal is None and operation.adjudication is not None
       and operation.attack_transport=='DRAINED' and operation.phase=='ATTACK_DRAINED'
       and context.source_uid==target.target_uid and context.snapshot is operation.context.snapshot,
       'CONTINUOUS_EXACT_ADJUDICATED_LETHAL_REQUIRED')
  cycle=continuous_lethal.Cycle(self,target,adjudicated_operation=operation)
  cycle.context=context;cycle.attack_context=lease
  cycle.stage='ADJUDICATED_ZERO';self.lethal=state.lethal=cycle
  return cycle

 def _adjudicated_current_locked(self,target,context,lease):
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  cycle=self.lethal;operation=cycle.adjudicated_operation
  need(type(lease) is HitLease and lease is cycle.attack_context and lease.issuer is self
       and lease.target is target and operation is self.hit.operation_for(target.writer)
       and operation.context is lease.context and operation.context.snapshot is context.snapshot
       and operation.context.source_uid==target.target_uid==context.source_uid
       and operation.context.target_uid==context.target_uid
       and operation.adjudication is not None and operation.attack_transport=='DRAINED'
       and operation.phase in ('ATTACK_DRAINED','LETHAL_COMMITTED'),
       'CONTINUOUS_EXACT_ADJUDICATED_OPERATION_REQUIRED')
  transaction=self.life._cycles.get(id(target.writer))
  need(transaction is not None and transaction.context is context
       and transaction.adjudicated_attack is transaction.npc_attack is operation
       and not transaction.terminal,'CONTINUOUS_EXACT_ADJUDICATED_CYCLE_REQUIRED')
  self._pure_current(target,lethal_context=context)
  require_owner_binding(self.broker,expected=target.owner,selected=True)
  row,snapshot,_,_=self.hit._current(target.writer,source_uid=target.target_uid,player_life_context=context)
  _,position,mover=self._pure_current(target,lethal_context=context)
  need(row is target.row and self.life._contexts.get(id(target.writer)) is context
       and self.lethal is cycle and self.hit.operation_for(target.writer) is operation
       and operation.context is lease.context and cycle.adjudicated_operation is operation
       and self.life._cycles.get(id(target.writer)) is transaction
       and transaction.adjudicated_attack is transaction.npc_attack is operation and not transaction.terminal
       and position is context._position is lease.position and mover.state is lease.npc_state
       and self.npc_session.lane_for(target.target_uid).generation is target.generation,
       'CONTINUOUS_FINAL_ADJUDICATED_BINDING_CHANGED')
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return self

 def motion_current_locked(self,writer,row,lease,step=None,wire=None):
  state=self.state_for_exact_receipt(lease.target)
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  need(type(lease) is MotionLease and state.motion_lease is lease and lease.issuer is self
       and lease.target is state.target and writer is lease.target.writer and row is lease.target.row
       and state.phase=='TARGET_ACTIVE' and state.owned_goal==(lease.target,lease.goal)
       and self.npc_session.lane_for(lease.target.target_uid).goal is lease.goal
       and self.npc_session.lane_for(lease.target.target_uid).generation is lease.target.generation,
       'CONTINUOUS_LITERAL_CURRENT_MOTION_LEASE_REQUIRED')
  if step is not None:
   need(state.motion_step is step and step.before is lease.state and step.after.goal is lease.goal,
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
  if not self.resource_npc_pc:self.life.check_normal_locked(writer)
  if wire is not None:need(step is not None and wire is step.frame,'CONTINUOUS_EXACT_MOTION_FRAME_REQUIRED')
  checked_ns=time.monotonic_ns()
  # Callback-bearing checks precede final pure registrations and effect state.
  snapshot,position,mover=self._pure_current(lease.target,motion_step=step)
  need(state.motion_lease is lease and state.motion_step is step and state.target is lease.target
       and snapshot is lease.snapshot and position is lease.position and mover.state is lease.state
       and self.npc_session.lane_for(lease.target.target_uid).goal is lease.goal and state.phase=='TARGET_ACTIVE'
       and self.combat._hp._entries.get((id(writer),mover.state.uid)) is lease.hp_entry
       and lease.hp_entry.hp.alive
       and lease.due_ns==state.next_action_ns and checked_ns>=lease.due_ns,'CONTINUOUS_MOTION_AUTHORITY_CHANGED')
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return self

 def bind_motion_locked(self,writer,row,lease,step):
  state=self.state_for_exact_receipt(lease.target)
  self.motion_current_locked(writer,row,lease)
  need(state.motion_step is None and step.before is lease.state,'CONTINUOUS_FRESH_MOTION_OPERATION_REQUIRED')
  state.motion_step=step

 def feedback_drained_locked(self,writer,row,session,intent,wire,*,now_ns):
  """Synchronous, no send/query/await: consume the exact original drain event."""
  need(not self.closed and self.broker._npc_continuous is self and row['operation_lock'].locked()
       and self.combat is session is self.broker._attack_session
       and session._current is session._feedback_intent is intent and session._feedback_frame is wire
       and session._feedback_state=='DRAINED' and intent._bound._writer is writer
       and intent.accepted_ordinal==session.accepted_count and type(now_ns) is int and now_ns>=0,
       'CONTINUOUS_LITERAL_FEEDBACK_EVENT_REQUIRED')
  if intent.accepted_ordinal==self._last_ordinal:return self.target_for(intent._bound.target_uid)
  need(intent.accepted_ordinal>self._last_ordinal,'CONTINUOUS_FEEDBACK_EVENT_ORDER_REQUIRED')
  result=session.last_hp_result
  uid=intent._bound.request.target_uid
  recipe=attack.npc_recipe(self.broker.realm,uid)
  need(intent._bound.target_uid==uid,'CONTINUOUS_REQUEST_TARGET_UID_REQUIRED')
  need(type(result) is npc_hp.Result and result.accepted_ordinal==intent.accepted_ordinal
       and result.target==npc_hp.Target(uid,recipe.map_id,recipe.fields[3],recipe.fields[39]),'CONTINUOUS_LITERAL_HP_EVENT_REQUIRED')
  self._last_ordinal=intent.accepted_ordinal
  key=(id(writer),uid);state=self._states.get(key)
  if state is not None:state.last_feedback=(intent,result,wire,now_ns)
  self._last_request_uid=uid
  if result.died:
   if state is not None:
    self._retire_state(state,'NPC_DEAD');self._states.pop(key,None)
    self.npc_session.retire_generation(writer,state.generation)
   return None
  need(result.after.alive,'CONTINUOUS_ACCEPTED_NONLETHAL_REQUIRED')
  if not result.hit.landed:
   current=None if state is None else state.target
   if current is not None:self._pure_current(current)
   return current
  realm=self.broker.realm;game=realm.registry.resolve(writer);move=realm.service(writer)
  snapshot=self.hit.status._states.get(id(writer));owner=self.broker._hp_resource_owner
  self._require_runtime_lifetime(writer)
  lifecycle=self.broker._npc_respawn;generation=attack.npc_generation(lifecycle,realm,writer,uid)
  if state is not None:
   current=state.target
   if (current is not None and current.writer is writer and current.selection is game.selection
       and current.generation is generation and current.life_token is self._life_token(writer)):
    self._pure_current(current);return current
   need(state.operation is None and state.motion_step is None and state.lethal is None,
        'CONTINUOUS_GENERATION_SWITCH_IN_FLIGHT_REFUSED')
   self._retire_state(state,'TARGET_SELECTION_OR_GENERATION_REPLACED')
  need(snapshot is not None and snapshot.current_hp>0 and owner is self.hit.status._resource_owner
       and owner.active and result.after.alive,'CONTINUOUS_SOURCE_NONLETHAL_BINDING_REQUIRED')
  self.npc_session.bind_lane(uid,generation)
  state=AggroState(writer,uid,generation)
  state.last_feedback=(intent,result,wire,now_ns)
  self._states[key]=state
  self._serial+=1
  receipt=TargetReceipt(self,writer,row,game,game.selection,move,owner,snapshot._lifetime,
   self.life,self._life_token(writer),lifecycle,generation,attack.npc_mover(realm,writer,uid),intent,result,wire,
   self.binding,self.runtime,self.scenario,self.stop,now_ns,self._serial,state)
  state.target=receipt;self._issued.append(receipt)
  try:self._pure_current(receipt)
  except BaseException:
   state.target=None;self._states.pop(key,None);raise
  state.phase='TARGET_ACTIVE';state.reason=None;state.effects=[]
  self.phase='TARGET_ACTIVE';self.reason=None
  state.next_attack_ns=now_ns;state.next_move_ns=now_ns;state.next_action_ns=now_ns;state.lease=state.operation=None
  return receipt

 def validate_locked(self,writer,row,lease,context,operation=None):
  state=self.state_for_exact_receipt(lease.target)
  need(type(lease) is HitLease and lease is state.lease and lease.issuer is self
       and lease.target is state.target and lease.context is context
       and state.phase=='ATTACKING' and lease.ordinal==len(state.effects)+1,
       'CONTINUOUS_LITERAL_ONCE_HIT_LEASE_REQUIRED')
  snapshot,position,mover,identities,values=self.current_locked(lease.target,allow_operation=True)
  expected=lease.snapshot
  if operation is not None:
   need(type(operation) is npc_player_hit._Prepared and operation is state.operation
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
  need(direction==lease.direction and lease.due_ns==state.next_action_ns and time.monotonic_ns()>=lease.due_ns,
       'CONTINUOUS_CURRENT_RANGE_AND_CADENCE_REQUIRED')
  self._pure_current(lease.target,allow_operation=True)
  need(state.lease is lease and state.phase=='ATTACKING'
       and self.hit.status._states.get(id(writer)) is expected
       and mover.state is lease.npc_state and (operation is None or state.operation is operation),
       'CONTINUOUS_FINAL_EFFECT_REGISTRATION_CHANGED')
  task=asyncio.current_task()
  if task is not None and task.cancelling():raise asyncio.CancelledError()
  return self

 def bind_operation_locked(self,writer,row,lease,context,operation):
  state=self.state_for_exact_receipt(lease.target)
  self.validate_locked(writer,row,lease,context)
  need(state.operation is None and self.hit.operation_for(writer) is operation
       and operation.context is context and operation.phase=='PREPARED_AUTHORITY_ONLY',
       'CONTINUOUS_NEW_ORIGINAL_OPERATION_REQUIRED')
  state.operation=operation

 async def positive(self,target,*,now_ns):
  state=self.state_for_exact_receipt(target)
  need(state.phase=='TARGET_ACTIVE' and state.target is target and state.lease is None
       and now_ns>=state.next_attack_ns,'CONTINUOUS_DUE_TARGET_REQUIRED')
  writer,row=target.writer,target.row
  async with self.broker._row_operation(writer,row):
   await self.broker._checkpoint(writer,row) # New actual owner sample for each automatic effect.
   snapshot,position,mover,_,_=self.current_locked(target)
   need(snapshot.current_hp>(0 if self.hit.adjudicator is not None else 1),'CONTINUOUS_LETHAL_BOUNDARY_REQUIRED')
   from tools.local_original_session.npc_approach_hit import melee_geometry
   _,direction=melee_geometry(movement.authority.unpack_grid(mover.state.packed),(position.word0,position.word1))
  context=await self.broker.npc_player_hit_repeated_context(writer,policy=npc_player_hit.REPEATED_POLICY,target_uid=target.target_uid)
  async with self.broker._row_operation(writer,row):
   snapshot,position,mover,identities,values=self.current_locked(target)
   self.hit.validate_locked(writer,context)
   need(context.snapshot is snapshot and state.phase=='TARGET_ACTIVE' and state.lease is None,
        'CONTINUOUS_FRESH_CURRENT_CONTEXT_REQUIRED')
   lease=HitLease(self,target,context,position,mover.state,snapshot,identities,values,
                  len(state.effects)+1,state.next_attack_ns,direction)
   state.lease=lease;state.operation=None;state.phase='ATTACKING'
  try:
   result=await self.broker.attack_player_repeated(writer,expected_context=context,raw_effect=1,direction=direction,
     policy=npc_player_hit.REPEATED_POLICY,continuous_lease=lease)
   async with self.broker._row_operation(writer,row):
    if self.lethal is not None and self.lethal.adjudicated_operation is state.operation:
     self.lethal.finish_adjudicated_locked(result)
     return result
    self.validate_locked(writer,row,lease,context,state.operation);result.require_current_locked(writer)
    hit=self.hit.reported_hit(state.operation)
    need(result.after.current_hp==snapshot.current_hp-hit.damage
         and (hit.damage!=0 or result.after is snapshot),'CONTINUOUS_EXACT_POSITIVE_RESULT_REQUIRED')
    state.effects.append(result);self.effects.append(result)
    state.next_action_ns=time.monotonic_ns()+self.binding.attack_ns
    state.next_attack_ns=state.next_move_ns=state.next_action_ns
    state.lease=state.operation=None;state.phase='TARGET_ACTIVE'
   return result
  except BaseException:
   self._retire_state(state,'EFFECT_UNKNOWN');raise # Keep original attempted/drained histories.

 async def poll(self,*,now_ns,monitor):
  need(type(now_ns) is int and now_ns>=0,'CONTINUOUS_EXPLICIT_POLL_CLOCK_REQUIRED')
  if self.closed or self._busy:return self.metadata()
  if self.stop.is_set():self.retire('CANCELLED');return self.metadata()
  need(self._last_ns is None or now_ns>=self._last_ns,'CONTINUOUS_MONOTONIC_CLOCK_REQUIRED')
  if self._last_ns==now_ns:return self.metadata()
  self._last_ns=now_ns;self._busy=True
  try:
   if self.lethal is not None:
    await self.lethal.poll(now_ns=now_ns,monitor=monitor)
    return self.metadata()
   # One existing executor, fresh player HP lineage per effect, no NPC Tasks.
   states=tuple(self._states.values())
   if not states:return self.metadata()
   budget=self.binding.action_budget
   start=self._poll_cursor%len(states)
   if budget is not None:
    # Resume at the actual successor, even if earlier dictionary entries left.
    keys=tuple((id(s.writer),s.uid) for s in states)
    if self._poll_next_key in keys:start=keys.index(self._poll_next_key)
   else:self._poll_cursor=(start+1)%len(states)
   dispatched=0
   for offset,state in enumerate(states[start:]+states[:start]):
    if budget is not None:
     next_index=(start+offset+1)%len(states)
     self._poll_cursor=next_index;self._poll_next_key=keys[next_index]
    if state.target is None or state.quiesced or now_ns<state.next_action_ns:continue
    # Bound dispatch work, not wire count: DEAD/noop/blocked still cost a slot.
    dispatched+=1
    await self._poll_state(state,now_ns=now_ns,monitor=monitor)
    if self.lethal is not None or budget is not None and dispatched>=budget:break
   if budget is not None and offset+1==len(states):
    self._poll_cursor=(start+1)%len(states);self._poll_next_key=keys[self._poll_cursor]
   return self.metadata()
  finally:self._busy=False

 async def _poll_state(self,state,*,now_ns,monitor):
  target=state.target
  if target is None:return
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
    session=self.npc_session
    if distance>1 and session.server_navigation:
     # A free neighbouring goal is not an edge or path admission.
     goal=session.factory.adapter.provider.current_melee_goal(
      target.target_uid,position=position,mover_state=mover.state)
   if now_ns<state.next_action_ns:return
   if distance!=1:
    if distance==0:self._retire_state(state,'OVERLAPPING_TARGET');return
    if now_ns<state.next_move_ns:return
    # The original session owns every admitted edge and original MOVE drain.
    # Select the current player's neighbouring cell; no free/fake edge binding.
    if not session.server_navigation:
     delta=tuple((b>a)-(b<a) for a,b in zip(grid,player))
     goal=tuple(v-d for v,d in zip(player,delta))
    need(session.current_binding(target_uid=target.target_uid) is not None,'CONTINUOUS_CURRENT_MOTION_SESSION_REQUIRED')
    need(session.lane_for(target.target_uid).goal is None or state.owned_goal is not None
         and state.owned_goal[0] is target and state.owned_goal[1] is session.lane_for(target.target_uid).goal,
         'CONTINUOUS_FOREIGN_GOAL_REFUSED')
    if session.lane_for(target.target_uid).goal!=goal:
     session.submit_goal(goal=goal,target_uid=target.target_uid);state.owned_goal=(target,goal)
    else:
     need(state.owned_goal is not None and state.owned_goal[0] is target
          and state.owned_goal[1] is session.lane_for(target.target_uid).goal,'CONTINUOUS_FOREIGN_GOAL_REFUSED')
     goal=session.lane_for(target.target_uid).goal
    lease=MotionLease(self,target,position,snapshot,mover.state,
                      self.combat._hp._entries.get((id(writer),mover.state.uid)),goal,state.next_move_ns)
    state.motion_lease=lease;state.motion_step=None
    if session.server_navigation:
     # Server tile/occupancy authority runs in the original broker row scope.
     # Observation slots and render sampling never authorize an NPC action.
     outcome=await session.tick(now_ns=now_ns,target_uid=target.target_uid,continuous_motion_lease=lease)
    else:
     need(monitor is not None,'CONTINUOUS_ORIGINAL_QUERY_MONITOR_REQUIRED')
     if now_ns/1e9<monitor.next_memory:
      state.motion_lease=None
      return
     monitor.next_memory=max(monitor.next_memory,now_ns/1e9+.5)
     try:outcome=await session.tick(now_ns=now_ns,target_uid=target.target_uid,continuous_motion_lease=lease)
     finally:monitor.next_memory=max(monitor.next_memory,time.monotonic()+.5)
    if outcome.status=='DEAD':
     self.retire_generation(writer,state.generation,'NPC_DEAD')
     return
    need(outcome.status in ('MOVED','AT_GOAL','CADENCE','OBSERVATION_CADENCE','BLOCKED'),
         'CONTINUOUS_ORIGINAL_APPROACH_NOT_COMMITTED')
    state.motion_lease=state.motion_step=None
    if outcome.status=='BLOCKED':state.next_action_ns=state.next_move_ns=now_ns+self.binding.move_ns
    if outcome.status=='MOVED':
     state.next_action_ns=time.monotonic_ns()+self.binding.move_ns
     state.next_attack_ns=state.next_move_ns=state.next_action_ns
    async with self.broker._row_operation(writer,row):
     await self.broker._checkpoint(writer,row);self.current_locked(target)
    return # Never move and attack in the same scheduled slot.
   if now_ns<state.next_attack_ns:return
   if snapshot.current_hp==1 and self.hit.adjudicator is None:
    need(self.packet_runtime is None,'PACKET_NPC_TYPED_PRE_INPUT_UNSUPPLIED')
    from tools.local_original_session import continuous_lethal
    self.lethal=state.lethal=continuous_lethal.Cycle(self,target)
    await self.lethal.poll(now_ns=now_ns,monitor=monitor)
   else:await self.positive(target,now_ns=now_ns)
   return # No catch-up loop after a late poll.
  except asyncio.CancelledError:
   self._retire_state(state,'CANCELLED');raise
  except BaseException:
   self._retire_state(state,'CURRENT_TARGET_OR_EFFECT_UNKNOWN');raise


 def complete_recovery_locked(self,cycle):
  need(not self.resource_npc_pc,'CONTINUOUS_RESOURCE_LETHAL_OR_LIFE_UNSUPPORTED')
  from tools.local_original_session import continuous_lethal
  need(type(cycle) is continuous_lethal.Cycle and self.lethal is cycle and self._busy
       and cycle.controller is self and cycle.recovery_complete and cycle.stage=='RESTORED'
       and not cycle.closed and self.broker._npc_continuous is self,
       'CONTINUOUS_EXACT_COMPLETED_RECOVERY_REQUIRED')
  target=cycle.target;writer=target.writer;state=target.aggro
  row,token,cap=self.life.completed_recovery_locked(writer,cycle.result)
  need(row is target.row and row['operation_lock'].locked()
       and self._states.get((id(writer),target.target_uid)) is state
       and state.target is None and state.reason=='PLAYER_DEAD' and state.lethal is cycle
       and state.generation is target.generation and state.owned_goal is None
       and state.operation is state.lease is state.motion_lease is state.motion_step is None
       and token is not target.life_token and cycle.requester.state=='RESTORED_ARMED'
       and cycle.requester._armed[0] is token
       and cap is cycle.transaction.recovery_inputs,
       'CONTINUOUS_RESTORED_RETIRED_STATE_REQUIRED')
  lane=self.npc_session._lanes.get(target.target_uid)
  need(lane is not None and lane.generation is target.generation and lane.goal is None
       and lane.mover is target.generation.mover and lane.mover.pending is None,
       'CONTINUOUS_RESTORED_OLD_LANE_REQUIRED')
  self.npc_session.retire_generation(writer,target.generation)
  self._states.pop((id(writer),target.target_uid));state.lethal=None
  self.lethal=None;self.retired_lethal=cycle
  self.reason='PLAYER_LIFE_RESTORED';self.phase='TARGET_RETIRED'
  cycle.close() # Historical result remains evidence; only a new DRAINED feedback issues aggro.

 def release_player(self,life,writer):
  need(not self.resource_npc_pc,'CONTINUOUS_RESOURCE_LETHAL_OR_LIFE_UNSUPPORTED')
  record=life._tokens.get(id(writer))
  need(life is self.life and life.broker is self.broker and self.broker._npc_continuous is self,
       'CONTINUOUS_REAL_PLAYER_RELEASE_REQUIRED')
  if record is None or record[0] is not writer:return False
  targets=tuple(t for t in self._issued if t.writer is writer and t.selection is record[1] and t.life_token is record[2])
  if not targets:return False
  states=tuple(s for s in self._states.values() if s.writer is writer
               and any(t.aggro is s for t in targets))
  for state in states:
   self._retire_state(state,'PLAYER_SELECTION_RELEASED');self._states.pop((id(writer),state.uid),None)
  self.npc_session.release_continuous_targets(self,writer)
  self.reason='PLAYER_SELECTION_RELEASED';self.phase='TARGET_RETIRED'
  self.released_targets=targets;self.released_target=targets[-1];self.released_life_record=record
  self._quiesced=None
  return True
 def _retire_state(self,state,reason):
  # Exact state only; caller decides NPC-local versus whole-player retirement.
  owned=state.owned_goal
  try:
   if owned is not None:self.npc_session.retire_continuous_goal(*owned)
  except Exception as error:
   self.cleanup_error=type(error).__name__ # Preserve the triggering failure.
  finally:
   state.owned_goal=None
   state.reason=reason;state.target=None;state.phase='TARGET_RETIRED'
   if state.operation is not None:state.retired_operations.append(state.operation);self.retired_operations.append(state.operation)
   state.lease=state.operation=None;state.motion_lease=state.motion_step=None
   if state.lethal is not None and reason!='PLAYER_DEAD':
    self.retired_lethal=state.lethal;state.lethal.close()
    if self.lethal is state.lethal:self.lethal=None
   if reason!='PLAYER_DEAD':state.lethal=None


 def retire(self,reason):
  for state in tuple(self._states.values()):
   self._retire_state(state,reason)
   if reason=='PLAYER_DEAD' and (self.lethal is None or self.lethal.target.aggro is not state):
    self._states.pop((id(state.writer),state.uid),None)
    self.npc_session.retire_generation(state.writer,state.generation)
  self.reason=reason;self.phase='TARGET_RETIRED'
  if reason!='PLAYER_DEAD':
   self._states.clear();self.npc_session.clear_lanes()
 def close(self):
  if self.closed:return
  self.closed=True
  try:self.retire('FEATURE_CLOSED')
  finally:self.inventory_owner.close()

 def metadata(self):
  active=self.active_targets()
  phase='FEATURE_CLOSED' if self.closed else 'TARGET_ACTIVE' if active else self.phase
  return dict(policy=self.binding.policy,phase=phase,reason=None if active else self.reason,
   target_uid=self._last_request_uid,committed_hits=len(self.effects),
   targets=[dict(uid=s.uid,serial=s.target.serial,phase=s.phase,reason=s.reason,
       generation=s.generation.ordinal,committed_hits=len(s.effects),quiesced=s.quiesced,
       next_attack_ns=s.next_attack_ns,next_move_ns=s.next_move_ns,next_action_ns=s.next_action_ns)
       for s in self._states.values() if s.target is not None],
   hp=None if not self.effects else self.effects[-1].after.current_hp,
   lethal=None if self.lethal is None else self.lethal.metadata(),
   retired_lethal=None if self.retired_lethal is None else self.retired_lethal.metadata(),
   partial_history=[dict(phase=op.phase,attack_transport=op.attack_transport,hp_transport=op.hp_transport)
                    for op in self.retired_operations],
   client_action='UNKNOWN',client_hp='UNKNOWN',official_mapping='UNKNOWN',
   closed=self.closed)
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
 target=context.target if type(context) is HitLease else context.continuous_target
 need(type(target) is TargetReceipt and type(target.issuer) is Controller
      and target.issuer.broker is broker and broker._npc_continuous is target.issuer
      and target.writer is writer and target.row is row,
      'CONTINUOUS_REGISTERED_FROZEN_LETHAL_REQUIRED')
 life_context=(target.issuer.lethal.context if type(context) is HitLease else context.life_context)
 return target.issuer.lethal_current_locked(target,life_context,context)
