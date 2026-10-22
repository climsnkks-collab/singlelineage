"""Current HP1 crosses the original NPC attack/HP0/Death transaction.

Uses the existing retained query slot, typed recovery-input issuer and literal
lethal Plan. No action/native call or fabricated client death input is produced.
"""
from dataclasses import dataclass
import time
from tools.local_original_session import attack, movement, npc_player_lethal, npc_observe, player_life_observe, npc_respawn_focused
need=attack.need

@dataclass(frozen=True, slots=True)
class DeadWait:
 cycle: object
 controller: object
 target: object
 observer: object
 context: object
 attack_context: object
 result: object
 transaction: object
 owned_goal: object
 started_ns: int
 deadline_ns: int


def require_dead_observation_locked(wait,service,writer,result):
 need(type(wait) is DeadWait and type(wait.cycle) is Cycle,
      'CONTINUOUS_LITERAL_DEAD_WAIT_REQUIRED')
 Cycle._dead_final_locked(wait.cycle,wait,service,writer,result)


def confirm_dead_observation_locked(wait,service,writer,result,cap,record,completed_ns):
 need(type(wait) is DeadWait and type(wait.cycle) is Cycle
      and type(cap) is player_life_observe.RecoveryInputs,
      'CONTINUOUS_LITERAL_DEAD_OBSERVATION_REQUIRED')
 Cycle._dead_final_locked(wait.cycle,wait,service,writer,result,
     observation=(cap,record,completed_ns))


class Cycle:
 def __init__(self,controller,target):
  self.controller,self.target=controller,target
  self.context=self.plan=self.attack_context=self.result=None
  self.transaction=None
  self._dead_wait=None;self.dead_pending_reason=None;self.dead_observation=None
  self.stage='ARRIVAL';self.closed=False
  broker=controller.broker
  observer=getattr(broker,'_player_life_observer',None)
  need(type(observer) is player_life_observe.PlayerLifeObserver,
       'CONTINUOUS_ORIGINAL_PLAYER_LIFE_OBSERVER_REQUIRED')
  self.observer=observer
  self.npc_observer=npc_observe.NpcObserver(broker,controller.original.npc_session.factory.reader)

 def _dead_deadline(self,wait):
  need(type(wait) is DeadWait and wait.cycle is self and self._dead_wait is wait,
       'CONTINUOUS_LITERAL_DEAD_WAIT_REQUIRED')
  now=time.monotonic_ns()
  need(type(now) is int and wait.started_ns<=now<wait.deadline_ns,
       'CONTINUOUS_DEAD_CURRENT_DEADLINE')
  return now

 def _dead_final_locked(self,wait,service,writer,result,*,observation=None):
  from tools.local_original_session import player_life
  now=self._dead_deadline(wait) # Finish the clock callback before pure final refs.
  c=wait.controller;t=wait.target;b=c.broker
  need(wait.cycle is self and self.controller is c and self.target is t
       and c.lethal is self and c._busy and not self.closed and self.stage=='DEATH_DRAINED'
       and self._dead_wait is wait and self.observer is wait.observer is b._player_life_observer
       and type(wait.observer) is player_life_observe.PlayerLifeObserver
       and wait.observer.broker is b and wait.observer.reader is c.original.npc_session.factory.reader
       and self.context is wait.context and self.attack_context is wait.attack_context
       and type(result) is player_life.Result and result is wait.result is self.result
       and service is c.life is b._player_life and result._service is service
       and result.context is wait.context and result._cycle is wait.transaction is self.transaction
       and service._cycles.get(id(writer)) is wait.transaction
       and service._contexts.get(id(writer)) is wait.context
       and wait.transaction.context is wait.context and wait.transaction.result is result
       and wait.transaction.stage=='DEATH_DRAINED' and not wait.transaction.terminal
       and wait.context._writer is writer is t.writer and t.row['operation_lock'].locked(),
       'CONTINUOUS_CURRENT_DEAD_WAIT_BINDING_REQUIRED')
  need(c._owned_goal is None and c.original.npc_session._goal is not wait.owned_goal
       and getattr(c,'cleanup_error',None) is None,
       'CONTINUOUS_OWNED_DEAD_GOAL_NOT_RETIRED')
  if observation is not None:
   cap,record,completed=observation
   need(type(cap) is player_life_observe.RecoveryInputs and wait.observer.inputs is cap
        and cap._observer is wait.observer and cap._writer is writer and cap._context is wait.context
        and cap._stage=='DEAD' and cap._record is record
        and any(x is record for x in wait.observer._issued)
        and (cap._f2,cap._f3)==wait.observer._baseline
        and type(completed) is int and wait.observer._last_completed==completed
        and 0<=now-completed<=player_life_observe.MIN_INTERVAL_NS,
        'CONTINUOUS_CURRENT_DEAD_CAP_OR_TTL_CHANGED')
  c._pure_current(t,lethal_context=wait.context)

 def _dead_current_locked(self,wait):
  from tools.local_original_session.repeated_player_life_focused import require_owner_binding
  c=wait.controller;t=wait.target
  require_dead_observation_locked(wait,c.life,t.writer,wait.result)
  require_owner_binding(c.broker,expected=t.owner,selected=True)
  wait.result.require_current_locked(t.writer) # Original post-lethal life/current API.
  require_dead_observation_locked(wait,c.life,t.writer,wait.result)

 async def poll(self,*,now_ns,monitor):
  if self.closed or self.stage=='DEAD_OBSERVED':return self.metadata()
  need(monitor is not None,'CONTINUOUS_ORIGINAL_LIFE_QUERY_MONITOR_REQUIRED')
  wait=self._dead_wait
  if self.stage=='DEATH_DRAINED':self._dead_deadline(wait)
  if now_ns/1e9<monitor.next_memory:return self.metadata()
  c=self.controller;b=c.broker;t=self.target;writer,row=t.writer,t.row
  if self.stage=='ARRIVAL':
   options={} if len(b.realm._npc_spawns)==1 else {'target_uid':t.target_uid}
   self.context=await b.player_life_context(writer,policy=c.life.policy,**options)
   async with b._row_operation(writer,row):
    await b._checkpoint(writer,row)
    snapshot,_,mover,_,_=c.current_locked(t)
    need(snapshot is self.context.snapshot and snapshot.current_hp==1,
         'CONTINUOUS_CURRENT_LETHAL_BOUNDARY_REQUIRED')
    goal=movement.authority.unpack_grid(mover.state.packed)
   self.plan=npc_player_lethal.Plan(c.original.npc_session,goal=goal,
       life_context=self.context,continuous_target=t)
   c._owned_goal=(t,self.plan.goal)
   await self.plan.arrive_current_goal(writer,c.original,self.npc_observer,
       now_ns=now_ns,monitor=monitor)
   c._owned_goal=(t,self.plan.goal)
   self.attack_context=await self.plan.context(writer,life_context=self.context)
   need(type(self.attack_context) is npc_player_lethal.Context and self.attack_context.continuous_target is t,
        'CONTINUOUS_SOURCE_ISSUED_LETHAL_ANCHOR_REQUIRED')
   async with b._row_operation(writer,row):c.lethal_current_locked(t,self.context,self.attack_context)
   self.stage='PRE'
  elif self.stage=='PRE':
   monitor.next_memory=max(monitor.next_memory,now_ns/1e9+.5,time.monotonic()+.5)
   try:
    async with b._row_operation(writer,row):
     await b._checkpoint(writer,row);c.current_locked(t)
     self.plan.prepared_context_locked(writer,life_context=self.context,context=self.attack_context)
     cap=await self.observer.capture_locked(writer,self.context,stage='PRE',now_ns=now_ns)
     try:
      self.result=await self.plan.attack_scoped(writer,expected_context=self.attack_context,
          recovery_inputs=cap,raw_effect=1)
     finally:self.transaction=c.life._cycles.get(id(writer))
   finally:monitor.next_memory=max(monitor.next_memory,time.monotonic()+player_life_observe.MIN_INTERVAL_NS/1e9)
   self.stage='DEATH_DRAINED'
   started=time.monotonic_ns()
   self._dead_wait=DeadWait(self,c,t,self.observer,self.context,self.attack_context,
       self.result,self.transaction,self.plan.goal,started,started+npc_respawn_focused.WAIT_NS)
   c.retire('PLAYER_DEAD') # Preserve this original Death/history; future hits stop.
  elif self.stage=='DEATH_DRAINED':
   interval=player_life_observe.MIN_INTERVAL_NS/1e9
   monitor.next_memory=max(monitor.next_memory,now_ns/1e9+interval,time.monotonic()+interval)
   try:
    async with b._row_operation(writer,row):
     await b._checkpoint(writer,row)
     self._dead_current_locked(wait)
     if b._hp_resource_owner is not None:b._hp_resource_owner.require_hp_quiescent(writer)
     ready=True
     try:
      await self.observer.capture_locked(writer,self.context,stage='DEAD',now_ns=now_ns)
     except ValueError as error:
      if str(error)!='PLAYER_LIFE_DEAD_CURRENT_NOT_READY':raise
      self._dead_current_locked(wait)
      self.dead_pending_reason=str(error)
      ready=False # Same stage/window; no send or new deadline.
     finally:self.dead_observation=dict(self.observer.last_result)
     if ready:
      self._dead_current_locked(wait)
      # Consume the freshly issued cap in this same original row scope, as316.
      # The optional literal wait checks again after _stage callbacks.
      c.life.confirm_death_locked(writer,self.result,dead_observation=wait)
      self.dead_pending_reason=None
      self.stage='DEAD_OBSERVED'
   finally:monitor.next_memory=max(monitor.next_memory,time.monotonic()+interval)
  return self.metadata()

 def metadata(self):
  cycle=self.transaction or self.controller.life._cycles.get(id(self.target.writer))
  return dict(stage=self.stage,dead_pending_reason=self.dead_pending_reason,
              dead_current=self.dead_observation,
              attack=None if self.result is None else self.result.metadata(),
              transaction=None if cycle is None or cycle.context is not self.context else
                dict(stage=cycle.stage,terminal=cycle.terminal,
                     deliveries=[dict(kind=d.kind,phase=d.phase) for d in cycle.deliveries]),
              client_death='OBSERVED' if self.stage=='DEAD_OBSERVED' else 'UNKNOWN')
 def close(self):
  if self.closed:return
  self.closed=True
  if self.plan is not None:
   if self.attack_context is not None:self.plan.retire_prepared_context(self.attack_context)
   self.plan.close()
