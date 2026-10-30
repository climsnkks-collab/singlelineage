"""Runner binding only: original client-confirmed Add, UI owner, existing Quit.

No migration, sender, Native return gate, memory provider or retry is installed.
"""
import asyncio
import sys,time
from pathlib import Path
from types import MethodType
from tools.local_original_session import ground_client_retirement as retirement

from tools.local_original_session import item_custody, item_transfer_session, inventory as inv
from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration
from tools.local_original_session.item_transfer_ui import ItemTransferUI
from tools.local_original_session.manual_move_commands import WAIT_NS

_STOP_IS_SET = asyncio.Event.is_set

_RETIREMENT_CLASS=retirement.GroundRetirementObserver
_RETIREMENT_SAMPLE=_RETIREMENT_CLASS.sample_returned
_RETIREMENT_CLOSE=_RETIREMENT_CLASS.close

def retirement_source():
    need(sys.modules.get('tools.local_original_session.ground_client_retirement') is retirement
         and retirement.GroundRetirementObserver is _RETIREMENT_CLASS
         and _RETIREMENT_CLASS.sample_returned is _RETIREMENT_SAMPLE
         and _RETIREMENT_SAMPLE.__globals__.get('GroundRetirementObserver') is _RETIREMENT_CLASS
         and _RETIREMENT_SAMPLE.__qualname__=='GroundRetirementObserver.sample_returned'
         and Path(_RETIREMENT_SAMPLE.__code__.co_filename).resolve()==Path(retirement.__file__).resolve(),
         'SCENARIO_GROUND_RETIREMENT_SOURCE_CHANGED')

PROFILE = item_transfer_session.PROFILE
DLL_SHA = '20e52b0bdacd36fcd4d37ce27bc61dff70cdeaafcafe60aca38faa92c74e52b4'
EXPECTED_UIDS = (65537, 65538)
WHOLE_QUANTITY = 3


def need(value, code):
    if not value:
        raise ValueError(code)


def configuration(features, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import item_use_session, item_equipment_effect
    item_transfer_session.configuration(features)
    need(inventory is True and auto_inventory is True
         and features.item_use_policy == item_use_session.POLICY
         and features.item_equipment_policy == item_equipment_effect.POLICY
         and features.item_equipment_first_enable is False,
         'SCENARIO_TRANSFER_REAL_EQUIPMENT_RESTORE_REQUIRED')
    one = inv.validate_frame(features.inventory_frame)
    fields = dict(one.raw_fields)
    need(fields[1] == EXPECTED_UIDS[0] and fields[2] == 1 and fields[4] == WHOLE_QUANTITY,
         'SCENARIO_TRANSFER_EXACT_SINGLE_A_CONFIG_REQUIRED')
    return features


class Runtime:
    def __init__(self, original, scenario, broker):
        from tools.local_original_session import launcher
        need(type(original) is launcher.ProductFeatures
             and type(original.item_transfer_ui) is ItemTransferUI
             and type(broker) is PersistentBroker
             and original.item_transfer_ui.broker is broker
             and original.manual.inventory_broker is broker
             and original.manual.consumer.reader is scenario.reader,
             'SCENARIO_TRANSFER_ACTUAL_RUNTIME_REQUIRED')
        self.original, self.scenario, self.broker = original, scenario, broker
        self.manual, self.npc_session = original.manual, original.npc_session
        retirement_source()
        self._retirement=_RETIREMENT_CLASS(broker,scenario.reader)
        self._retirement_result=None
        self._retirement_capture=None
        self.requested = False
        scenario.transfer_runtime = self
        ui = original.item_transfer_ui
        need(ui._post_ret_runtime is None and type(scenario.stop) is asyncio.Event,
             'SCENARIO_TRANSFER_POST_RET_ONCE_REQUIRED')
        self._post_ret_bound = (scenario, type(scenario), scenario.stop, original, ui,
                                self.manual, broker, scenario.reader)
        ui._post_ret_runtime = self

    def require_post_ret_current(self, ui):
        # 완료된 Native 대기 예산 대신 기존 실행/취소/동일 기능 수명을 결속한다.
        # 이 참조 비교는 fresh backend/관측 권위가 아니며 _context가 뒤따른다.
        from tools.local_original_session.launcher import ProductFeatures
        need(type(self) is Runtime and type(ui) is ItemTransferUI
             and type(self.original) is ProductFeatures,
             'SCENARIO_TRANSFER_POST_RET_TYPED_RUNTIME_REQUIRED')
        bound = self._post_ret_bound
        scenario = self.scenario
        need(len(bound) == 8 and scenario is bound[0] and type(scenario) is bound[1]
             and scenario.stop is bound[2] and type(scenario.stop) is asyncio.Event
             and self.original is bound[3] and ui is bound[4]
             and self.manual is bound[5] and self.broker is bound[6]
             and scenario.reader is bound[7] is ui.consumer.reader
             and scenario.transfer_runtime is self and ui._post_ret_runtime is self
             and self.original.item_transfer_ui is ui and ui.runtime is self.original
             and self.original.manual is self.manual is ui.manual
             and self.manual.consumer is ui.consumer
             and self.manual.inventory_broker is self.broker is ui.broker,
             'SCENARIO_TRANSFER_POST_RET_SAME_FLOW_REQUIRED')
        inv.InventoryService._cancelled()
        stop_method = scenario.stop.is_set
        need(type(stop_method) is MethodType and stop_method.__self__ is scenario.stop
             and stop_method.__func__ is _STOP_IS_SET and asyncio.Event.is_set is _STOP_IS_SET,
             'SCENARIO_TRANSFER_POST_RET_ORIGINAL_STOP_REQUIRED')
        need(not _STOP_IS_SET(scenario.stop) and not self.original._closed and not ui.closed
             and scenario.stage == 'ITEM_TRANSFER_RUN' and self.requested
             and not self.broker._closing and not self.broker.failure.is_set(),
             'SCENARIO_TRANSFER_POST_RET_LIFETIME_ENDED')
        refs = ui._refs
        g = self.broker._inventory_generation
        need(type(refs) is tuple and len(refs) == 11 and g is refs[3]
             and type(g) is _InventoryGeneration and g.phase == 'ACTIVE'
             and g.row is refs[2] and g.writer is refs[1] and g.selected is refs[4]
             and g.transfer_session is refs[9] and not g.transfer_session.closed,
             'SCENARIO_TRANSFER_POST_RET_OPERATION_CHANGED')

    def defer_status_tick(self, monitor):
        # Scheduling only: never admission, query freshness or completion proof.
        from tools.local_original_session.launcher import ProductFeatures, ManualMoveRequests
        original, ui = self.original, self.original.item_transfer_ui
        need(type(self) is Runtime and type(original) is ProductFeatures
             and type(ui) is ItemTransferUI and original.manual is self.manual
             and type(self.manual) is ManualMoveRequests and ui.runtime is original
             and ui.manual is self.manual and ui.consumer is self.manual.consumer
             and ui.broker is self.broker is self.manual.inventory_broker
             and self.scenario.reader is ui.consumer.reader
             and monitor is self.scenario.monitor,
             'SCENARIO_TRANSFER_STATUS_SAME_TYPED_FLOW_REQUIRED')
        need(type(ui.started) is bool, 'SCENARIO_TRANSFER_STATUS_STARTED_BOOL_REQUIRED')
        return (self.requested and ui.started and not ui.closed and not original._closed
                and self.scenario.stage == 'ITEM_TRANSFER_RUN' and not self.scenario.stop.is_set()
                and ui.phase in ('INITIAL','INITIAL_SYNC','OPEN','PREPARE_USE','PREPARE_USE_BACKEND',
                    'DROP_ENTRY','DROP_ENTRY_WAIT','DROP_POPUP_WAIT','DROP_BACKEND','DROP_CLIENT',
                    'GET_ENTRY_WAIT','GET_POPUP_WAIT','RETURN_BACKEND','RETURN_CLIENT','DONE'))

    async def _start_after_actual_add(self):
        from tools.local_original_session import launcher
        ui, broker = self.original.item_transfer_ui, self.broker
        need(not self.requested and ui.started is False,
             'SCENARIO_TRANSFER_ONCE_REQUIRED')
        binding = launcher.current_manual_binding(broker)
        if binding is None:
            return
        generation = PersistentBroker.inventory_selection_current(broker, binding.writer)
        if generation is None or not self.original._equipment_initial_client_ready(
                broker, binding.writer, generation):
            return
        need(type(generation) is _InventoryGeneration and generation.phase == 'ACTIVE'
             and generation.previous is None and generation.writer is binding.writer,
             'SCENARIO_TRANSFER_FRESH_GENERATION_REQUIRED')
        need(type(generation.transfer_session) is item_transfer_session.ItemTransferSession
             and generation.transfer_session.broker is broker,
             'SCENARIO_TRANSFER_ORIGINAL_SESSION_REQUIRED')
        async with generation.row['operation_lock']:
            context = item_transfer_session.ItemTransferSession.context_locked(
                generation.transfer_session, binding.writer)
            a, b = item_custody._members(context.snapshot.frame_ab)
            need((a.identifier, b.identifier) == EXPECTED_UIDS
                 and all(dict(member.raw_fields)[2] == 1 for member in (a,b))
                 and dict(a.raw_fields)[4] == WHOLE_QUANTITY
                 and dict(b.raw_fields)[4] in (1, WHOLE_QUANTITY)
                 and context.current_frame is context.initial_frame
                 and context.snapshot.phase == 'READY' and context.snapshot.owner == 'PLAYER'
                 and context.membership.phase == 'READY'
                 and context.item_use_session.accepted_count == 0
                 and context.item_use_session._current is None
                 and context.equipment.item_uid == a.identifier
                 and context.equipment.weapon_uid in (0, a.identifier, b.identifier)
                 and (dict(b.raw_fields)[4] != 1 or context.equipment.weapon_uid == 0),
                 'SCENARIO_TRANSFER_EXACT_FRESH_AB_INPUT_REQUIRED')
            prepare = context.equipment.weapon_uid == b.identifier
        self.requested = True  # Spend before public once-request, never retry.
        need(self.original.request_item_transfer_roundtrip(prepare_use=prepare) is True,
             'SCENARIO_TRANSFER_PUBLIC_ONCE_REQUEST_REQUIRED')
        self.scenario.transfer_result.update(status='PENDING', phase=ui.phase,
            prepare_use=prepare, equipped_before=context.equipment.weapon_uid)
        actual = self.manual.last_result
        self.scenario.inventory = {name: actual[name] for name in
            ('status','phase','proof_scope','client_inventory','item_count','transport_proof_scope')
            if name in actual}

    async def _poll_ground_retirement(self,monitor):
        ui=self.original.item_transfer_ui
        if not self.requested or ui.phase!='DONE':return
        retirement_source()
        observer=self._retirement
        method=observer.sample_returned
        need(type(observer) is _RETIREMENT_CLASS and type(method) is MethodType
             and method.__self__ is observer and method.__func__ is _RETIREMENT_SAMPLE
             and observer.close.__func__ is _RETIREMENT_CLOSE,
             'SCENARIO_GROUND_RETIREMENT_ORIGINAL_ENGINE_REQUIRED')
        before=await ui._context() # Includes the existing original UI deadline.
        now=time.monotonic_ns();last=self.manual.last_sample_monotonic_ns
        sampled=observer.last_sample_monotonic_ns
        if sampled is not None:last=max(last,sampled) if last is not None else sampled
        if (monitor is not None and time.monotonic()<monitor.next_memory
                or last is not None and now-last<retirement.MIN_INTERVAL_NS):return
        try:
            result=await _RETIREMENT_SAMPLE(observer,before.writer,now_ns=now)
        finally:
            queried=observer.last_sample_monotonic_ns
            if type(queried) is int:
                previous=self.manual._inventory_previous_sample_ns
                self.manual._inventory_previous_sample_ns=max(v for v in (previous,queried) if v is not None)
                if monitor is not None:monitor.next_memory=max(monitor.next_memory,queried/1e9+.5)
        after=await ui._context()
        item_transfer_session.ItemTransferSession._same(before,after)
        retirement_source()
        _,other=item_custody._members(before.snapshot.frame_ab)
        need(self._retirement is observer and observer.sample_returned.__func__ is _RETIREMENT_SAMPLE
             and observer.sample_returned.__self__ is observer and result is observer.last_result
             and result.get('status')=='OBSERVED' and result.get('reason') is None
             and result.get('source_contract_valid') is True and result.get('stable_double_read') is True
             and result.get('uid')==other.identifier and result.get('map_id')==before.position.map_id
             and type(result.get('vector_counts')) is list and len(result['vector_counts'])==3
             and all(type(n) is int and 0<=n for n in result['vector_counts'])
             and result.get('snapshot_atomic') is False
             and type(result.get('typed_bytes_requested')) is int and 0<result['typed_bytes_requested']<=retirement.BYTE_LIMIT
             and type(result.get('query_started_monotonic_ns')) is int
             and result['query_started_monotonic_ns']==observer.last_sample_monotonic_ns
             and now<=result['query_started_monotonic_ns'],
             'SCENARIO_GROUND_RETIREMENT_FRESH_QUERY_REQUIRED')
        self._retirement_result=result
        self._retirement_capture=(result,after.generation,after,self.manual.consumer,self.manual.consumer.sequence,asyncio.current_task())
        if result['uid_absent'] is True:_RETIREMENT_CLOSE(observer)

    def _capture(self):
        if self.scenario.stop.is_set() or self.scenario.transfer_result.get('status') == 'UNKNOWN':
            return # Preserve terminal outcome before consuming historical UI data.
        ui = self.original.item_transfer_ui
        if self.requested:
            if ui.phase == 'DONE':
                need(ui.last.get('status') == 'COMPLETE' and type(ui.last.get('client_return')) is dict
                     and ui.last['client_return'].get('client_inventory') == 'POST_RETURN_ROWS_5_SCALARS_MATCHED',
                     'SCENARIO_TRANSFER_DONE_CLIENT_RETURN_REQUIRED')
                if self.scenario.stop.is_set():return # Historical report only, no new stop authority.
                token=self._retirement_capture
                if token is None or self._retirement_result is None or self._retirement_result.get('uid_absent') is not True:
                    self.scenario.transfer_result.update(dict(ui.last,status='PENDING',phase='GROUND_CLIENT_RETIREMENT_WAIT'))
                    self.scenario.transfer_result['ground_retirement']=dict(self._retirement_result or {},status='PENDING')
                    return
                result,g,context,owner,sequence,task=token
                need(result is self._retirement_result is self._retirement.last_result
                     and g is self.broker._inventory_generation and g.phase=='ACTIVE'
                     and g.current_frame is context.current_frame and g.selection_binding is context.selection_binding
                     and g.transfer_session is context.session and context.session._committed is context.snapshot
                     and context.session.membership is context.membership and context.session.phase=='RETURNED'
                     and context.membership.phase=='DRAINED' and self.manual.consumer is owner
                     and owner.sequence==sequence and task is asyncio.current_task() and not task.cancelling()
                     and not ui.closed, 'SCENARIO_GROUND_RETIREMENT_SAME_COMPLETION_OPERATION_REQUIRED')
                self._retirement_capture=None
                self.scenario.transfer_result.update(ui.last)
                self.scenario.transfer_result['ground_retirement']=dict(result)
                self.scenario.stage = 'ITEM_TRANSFER_COMPLETE_STOP_REQUESTED'
                self.scenario.stop.set()
            else:
                self.scenario.transfer_result.update(ui.last)
                if ui.closed or ui.last.get('status') == 'UNKNOWN':
                    raise ValueError('SCENARIO_TRANSFER_UI_UNKNOWN')

    async def poll(self, monitor=None):
        if self.scenario.stop.is_set():
            return {}
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_TRANSFER_SAME_MONITOR_REQUIRED')
            result = await self.original.poll(monitor)
            if self.scenario.stage == 'ITEM_TRANSFER_RUN' and not self.requested:
                await self._start_after_actual_add()
            await self._poll_ground_retirement(monitor)
            self._capture()
            if not STATUS_TICK_DEFER_METHOD(self, monitor):
                self.scenario.save()
            return result
        except asyncio.CancelledError:
            self._copy_failure_progress()
            self.scenario.fail_transfer('SCENARIO_TRANSFER_CANCELLED')
            raise
        except Exception as error:
            from tools.local_original_session import launcher
            self.original.item_transfer_ui.close()
            self._copy_failure_progress()
            self.scenario.fail_transfer(launcher.safe_error_code(error) or type(error).__name__)
            return {}

    def _copy_failure_progress(self):
        progress = self.original.item_transfer_ui.last.get('backend_progress')
        if type(progress) is dict:
            self.scenario.transfer_result['backend_progress'] = {
                key: dict(value) if type(value) is dict else value
                for key, value in progress.items()}

    def finalize(self):
        self._capture()

    def close(self):
        try:_RETIREMENT_CLOSE(self._retirement)
        finally:self.original.close()  # Original SourceQuit/owner cleanup retains all pending claims.

POST_RET_CURRENT_METHOD = Runtime.require_post_ret_current
STATUS_TICK_DEFER_METHOD = Runtime.defer_status_tick
