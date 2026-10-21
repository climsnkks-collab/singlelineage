"""One explicit SHOP scenario on the original feature loop. No input defaults.
Measurements are root input data, never an Actor/node/current capability.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import asyncio,hashlib,json,threading,time,weakref
from types import MethodType


def need(value,reason):
    if not value:raise ValueError(reason)

@dataclass(frozen=True)
class Step:
    label: str
    role: str

@dataclass(frozen=True)
class Spec:
    root: object
    features: object
    steps: tuple
    row_key_u32: int
    quantity_i32: int
    point_directory: Path
    report_path: Path
    def __post_init__(self):
        from tools.local_original_session import canonical_feature_bootstrap as boot,feature_config
        need(type(self.root) is boot.CanonicalFeatureBootstrap and type(self.features) is feature_config.Features
             and self.features.canonical_bootstrap is self.root and self.root.shop_only,
             'DRIVER_EXACT_SHOP_ROOT_FEATURES')
        need(type(self.steps) is tuple and 4<=len(self.steps)<=64
             and all(type(s) is Step and type(s.label) is str and type(s.role) is str and 0<len(s.label)<=80 for s in self.steps),
             'DRIVER_EXPLICIT_BOUNDED_STEPS')
        roles=tuple(s.role for s in self.steps)
        need(roles[:3]==('NPC','BUY','ROW') and roles[-1]=='CONFIRM'
             and all(r=='QUANTITY' for r in roles[3:-1]),'DRIVER_EXPLICIT_CLICK_ORDER')
        need(type(self.row_key_u32) is int and 0<=self.row_key_u32<=0xffffffff
             and type(self.quantity_i32) is int and 1<=self.quantity_i32<=0x7fffffff,
             'DRIVER_EXPLICIT_ROW_QUANTITY')
        need(isinstance(self.point_directory,Path) and self.point_directory.is_absolute()
             and self.point_directory.is_dir() and isinstance(self.report_path,Path)
             and self.report_path.is_absolute() and not self.report_path.exists()
             and self.report_path.parent.is_dir(),'DRIVER_OWNED_INPUT_REPORT_PATHS')


def configure_factory(factory,spec):
    from tools.local_original_session import launcher,canonical_feature_bootstrap as boot
    need(type(spec) is Spec and type(factory) is launcher.ProductFeatureFactory
         and factory.product==launcher.SHOP_INPUT_PROFILE
         and spec.root is factory.config.canonical_bootstrap and spec.features is factory.config
         and not hasattr(factory,'_shop_normal_input_spec'),'DRIVER_EXACT_COLD_FACTORY')
    boot.check_shop_input_factory(factory)
    factory._shop_normal_input_spec=spec


def attach_runtime(factory,runtime,broker):
    from tools.local_original_session import launcher,canonical_feature_bootstrap as boot
    spec=getattr(factory,'_shop_normal_input_spec',None)
    if spec is None:return
    need(type(spec) is Spec and type(runtime) is launcher.ProductFeatures
         and spec.features is factory.config and spec.root is factory.config.canonical_bootstrap
         and not hasattr(runtime,'_shop_normal_input_driver'),'DRIVER_ORIGINAL_RUNTIME')
    boot.check_shop_input_factory(factory,broker=broker)
    runtime._shop_normal_input_driver=Driver(spec,factory,runtime,broker)


def _driver(runtime):
    value=getattr(runtime,'_shop_normal_input_driver',None)
    if value is None:return None
    need(type(value) is Driver and value.runtime() is runtime
         and all(getattr(Driver,n) is f for n,f in _METHODS),'DRIVER_ORIGINAL_METHODS')
    return value

async def poll_runtime(runtime,monitor):
    value=_driver(runtime)
    return None if value is None else await value.poll(monitor)

def terminal(runtime):
    value=_driver(runtime)
    return None if value is None or value.phase not in ('DONE','UNKNOWN') else value.phase

def close_runtime(runtime):
    value=_driver(runtime)
    if value is not None:
        try:value.close()
        finally:runtime._shop_normal_input_driver=None


def retire_pending_for_close(runtime):
    value=_driver(runtime)
    if value is None or value.native_input is None:return
    if value.native_input.pending is not None:
        primary=None
        try:value.native_input.close()
        except BaseException as error:primary=error
        value.phase='UNKNOWN';value.failure=value.failure or 'DRIVER_NATIVE_PENDING_CLOSE_UNKNOWN'
        value.native_phase=None
        try:value._save()
        except BaseException as error:
            if primary is None:primary=error
            else:
                try:BaseException.add_note(primary,'SHOP retirement report also failed; primary preserved.')
                except BaseException:pass
        if primary is not None:raise primary


def validate_measurement(row,prompt,spec,role):
    keys={'schema','step','capture_sequence','image_sha256','pid','birth','hwnd','ui_thread','window_dpi',
          'client_rect','client_x','client_y','provenance','measured_at','row_key_u32','observed_quantity'}
    need(type(row) is dict and set(row)==keys and row['schema']=='shop-normal-input-point-v1',
         'DRIVER_MEASUREMENT_EXACT_SCHEMA')
    for name in ('step','capture_sequence','image_sha256','pid','birth','hwnd','ui_thread','window_dpi','client_rect'):
        need(type(row[name]) is type(prompt[name]) and row[name]==prompt[name],'DRIVER_MEASUREMENT_CAPTURE_MISMATCH')
    need(type(row['client_x']) is int and type(row['client_y']) is int
         and -32768<=row['client_x']<=32767 and -32768<=row['client_y']<=32767,
         'DRIVER_MEASURED_CLIENT_SIGNED16')
    need(type(row['client_rect']) is list and all(type(v) is int for v in row['client_rect']),
         'DRIVER_MEASURED_RECT_TYPES')
    left,top,right,bottom=prompt['client_rect']
    need(left<=row['client_x']<right and top<=row['client_y']<bottom,'DRIVER_MEASUREMENT_CLIENT_RECT')
    need(type(row['provenance']) is str and 0<len(row['provenance'])<=512
         and type(row['measured_at']) is str and 0<len(row['measured_at'])<=100,'DRIVER_MEASUREMENT_PROVENANCE')
    need(row['row_key_u32'] is None or type(row['row_key_u32']) is int,'DRIVER_MEASURED_ROW_TYPE')
    need(row['observed_quantity'] is None or type(row['observed_quantity']) is int
         and 0<=row['observed_quantity']<=0x7fffffff,'DRIVER_MEASURED_QUANTITY_TYPE')
    if role in ('ROW','QUANTITY','CONFIRM'):
        need(row['row_key_u32']==spec.row_key_u32,'DRIVER_EXPLICIT_MEASURED_ROW')
    if role=='CONFIRM':
        need(row['observed_quantity']==spec.quantity_i32,'DRIVER_EXPLICIT_MEASURED_QUANTITY')
    return row['client_x'],row['client_y']


def correlated_event(value,baseline,publication_serial):
    event=json.loads(value)
    need(baseline is not None and publication_serial==baseline[1],'DRIVER_PUBLICATION_CHANGED')
    ordinal=event.get('receive_ordinal')
    return event if type(ordinal) is int and ordinal>baseline[0] else None


def validate_menu_event(event,selected_uid,npc_uid):
    # Menu.uid names the selected player. Response f1 echoes the NPC selector.
    signed=npc_uid if npc_uid<0x80000000 else npc_uid-(1<<32)
    need(type(event.get('uid')) is int and event['uid']==selected_uid,
         'DRIVER_MENU_SELECTION_CHANGED')
    need(type(event.get('f1_i32')) is int and event['f1_i32']==signed,
         'DRIVER_MENU_TARGET_CHANGED')


def client_result_state(result,expected):
    if result.get('status') in ('PENDING','NOT_SAMPLED') or result.get('reason') in (
            'NOT_SAMPLED','INVENTORY_OBSERVE_CALLER_CADENCE_REQUIRED','INVENTORY_OBSERVE_PREVIOUS_FIELD4_PENDING'):
        return 'WAIT_CLIENT'
    need(result.get('status')=='OBSERVED' and result.get('rows')==expected,
         'DRIVER_CLIENT_INVENTORY_UNKNOWN_OR_MISMATCH')
    return 'DONE'


class Driver:
    def __init__(self,spec,factory,runtime,broker):
        self.spec=spec;self.factory=weakref.ref(factory);self.runtime=weakref.ref(runtime);self.broker=weakref.ref(broker)
        self.phase='WAIT_INVENTORY';self.index=0;self.capture=None;self.capture_observer=None
        self.generation=None;self.snapshot=None;self.client=None;self.clicks=[];self.closed=False;self.baseline=None;self.trade_event=None
        self.thread=threading.get_ident();self.task=None;self.prompt=None;self.failure=None;self.geometry_probe=None
        self.native_input=None;self.native_phase=None
        self._save()
    def _save(self):
        # Dedicated report is data, never a source/current receipt.
        path=self.spec.report_path if self.spec is not None else None
        if path is not None:path.write_text(json.dumps(self.report(),ensure_ascii=False,indent=2),encoding='utf-8')
    def report(self):
        return dict(schema='shop-normal-input-driver-v1',phase=self.phase,requested_stage=(None if self.spec is None
            or self.index>=len(self.spec.steps) else self.spec.steps[self.index].role),step_index=self.index,
            prompt=self.prompt,geometry_probe=self.geometry_probe,clicks=list(self.clicks),server_snapshot=self.snapshot,client_inventory=self.client,
            native_input=(None if self.native_input is None else self.native_input.last),
            native_pending_phase=self.native_phase,
            reason=self.failure,closed=self.closed,point_space='WINDOW_CLIENT_PIXELS',
            image_client_relation='GL_CLIENT_CORRESPONDENCE_UNESTABLISHED')
    def _current(self):
        from tools.local_original_session import launcher,canonical_feature_bootstrap as boot
        runtime=self.runtime();factory=self.factory();broker=self.broker()
        need(not self.closed and threading.get_ident()==self.thread and runtime is not None
             and type(runtime) is launcher.ProductFeatures and runtime._shop_normal_input_driver is self
             and not runtime._closed and factory is not None and broker is not None,
             'DRIVER_RUNTIME_CURRENT')
        need(self.spec.root is factory.config.canonical_bootstrap and self.spec.features is factory.config,
             'DRIVER_SPEC_CURRENT')
        self.spec.root.factory_current(factory)
        need(self.spec.root._broker is broker and broker._started and not broker._closing
             and not broker.failure.is_set(),'DRIVER_SAME_LIVE_ROOT_BROKER')
        need(runtime.manual is not None and runtime.manual.inventory_broker is broker,'DRIVER_ORIGINAL_MANUAL_BROKER')
        g=runtime.manual._inventory_generation
        if self.generation is not None:
            need(self.generation() is g and g is not None and g.phase=='ACTIVE','DRIVER_RESELECTED')
        if g is None or g.phase!='ACTIVE' or g.frame is None:return runtime,broker,None
        need(broker.inventory_selection_current(g.writer) is g,'DRIVER_CURRENT_GENERATION')
        if self.generation is None:self.generation=weakref.ref(g)
        need(self.generation() is g,'DRIVER_RESELECTED')
        return runtime,broker,g
    async def _server(self,broker,g):
        from tools.local_original_session.shop_input_receipts import snapshot_locked
        async with broker._row_operation(g.writer,g.row):
            snapshot=snapshot_locked(broker,g.writer,g.row)
        # The source module defines detached JSON only. No borrowed values are kept.
        self.snapshot=(None if snapshot is None else dict(uid=snapshot.uid,connection_id=snapshot.connection_id,
            received_ordinal=snapshot.received_ordinal,sent=snapshot.sent,publication_serial=snapshot.publication_serial,
            menu_json=snapshot.menu_json,listing_json=snapshot.listing_json,trade_json=snapshot.trade_json))
        return snapshot
    def _capture_request(self,runtime):
        observer=runtime.original_screenshot
        if observer._pending is not None or observer._requested:
            self.phase='WAIT_CAPTURE';return
        if observer._attempted and observer.last_result.get('status')!='OBSERVED':
            raise ValueError('DRIVER_CAPTURE_UNKNOWN')
        if runtime.request_original_screenshot():self.phase='WAIT_CAPTURE'
        else:self.phase='WAIT_CAPTURE_ADMISSION' # Same unattempted original request; no reset/new seq.
    def _owned_geometry(self,runtime,capture):
        from tools.local_original_session import launcher
        self._current()
        observer=self.capture_observer
        need(observer is runtime.original_screenshot and observer.capture_observation() is capture,
             'DRIVER_GEOMETRY_CAPTURE_CHANGED')
        unused,life=observer._current()
        need(observer._same(observer._life,life),'DRIVER_GEOMETRY_LIFE_CHANGED')
        owner=runtime.manual.consumer.reader.owner;desktop=owner.private_desktop
        need(type(desktop) is launcher.PrivateDesktop,'DRIVER_GEOMETRY_DESKTOP_REQUIRED')
        geometry=capture.geometry
        self.geometry_probe=dict(status='UNKNOWN',stage=self.phase,attempt_monotonic_ns=time.monotonic_ns())
        try:
            row=desktop.observe_client_geometry(owner,dict(pid=capture.pid,birth=capture.birth,
                candidate_sha256=capture.candidate_sha256),geometry.hwnd,geometry.ui_thread)
            self.geometry_probe.update(observation=row)
            self._current()
            unused,after=observer._current()
            need(observer.capture_observation() is capture and observer._same(life,after)
                 and observer._same(observer._life,after),'DRIVER_GEOMETRY_LIFE_CHANGED')
            matches=(row['status']=='OBSERVED' and row['client_rect']==list(geometry.client_rect)
                 and row['window_dpi']==geometry.window_dpi and row['window_awareness']==geometry.window_awareness
                 and row['thread_awareness']==geometry.thread_awareness
                 and row['awareness_equal'] is geometry.awareness_equal is True)
            self.geometry_probe['current_capture_geometry_match']=matches
            need(matches,'DRIVER_CURRENT_CAPTURE_GEOMETRY_MISMATCH')
            self.geometry_probe['status']='OBSERVED'
            return row
        except BaseException as error:
            try:self.geometry_probe['reason']=str(error)
            except BaseException:pass
            raise
    def _capture_ready(self,runtime):
        from tools.local_original_session import original_screenshot as source
        observer=runtime.original_screenshot;row=observer.observation()
        if observer._pending is not None or observer._requested:return False
        if not observer._attempted:return False
        need(row.get('status')=='OBSERVED' and row.get('png_verified') is True,'DRIVER_CAPTURE_UNKNOWN')
        capture=observer.capture_observation()
        need(type(capture) is source.CaptureObservation,'DRIVER_V6_CONTEXT_REQUIRED')
        self.capture=capture;self.capture_observer=observer
        geometry=capture.geometry
        owned_geometry=self._owned_geometry(runtime,capture)
        self.prompt=dict(step=self.index,capture_sequence=capture.sequence,image_sha256=capture.image_sha256,
            image_path=capture.image_path,file_identity=list(capture.file_identity),pid=capture.pid,birth=capture.birth,
            candidate_sha256=capture.candidate_sha256,hwnd=geometry.hwnd,ui_thread=geometry.ui_thread,
            window_dpi=geometry.window_dpi,client_rect=list(geometry.client_rect),crop=list(geometry.crop),
            geometry={name:getattr(geometry,name) for name in geometry.__dataclass_fields__},
            owned_geometry=owned_geometry,current_capture_geometry_match=True,
            input_path=str(self.spec.point_directory/f'point-{self.index}-{capture.sequence}.json'))
        self.phase='WAIT_MEASUREMENT';return True
    def _click(self,runtime,g,row):
        from tools.local_original_session import commands,original_screenshot as source
        from tools.local_original_session import launcher
        capture=self.capture;observer=self.capture_observer
        need(observer is runtime.original_screenshot and observer.capture_observation() is capture,
             'DRIVER_CAPTURE_REPLACED')
        current,life=observer._current()
        need(observer._same(observer._life,life) and g is self.generation() and life[1] is g,
             'DRIVER_CAPTURE_SELECTION_CHANGED')
        owner=runtime.manual.consumer.reader.owner;desktop=owner.private_desktop
        need(type(desktop) is launcher.PrivateDesktop and owner.child.pid==capture.pid
             and int(owner.child.identity['birth'])==capture.birth and owner.image_sha==capture.candidate_sha256,
             'DRIVER_CAPTURE_OWNER_CHANGED')
        role=self.spec.steps[self.index].role
        x,y=validate_measurement(row,self.prompt,self.spec,role)
        observed=self._owned_geometry(runtime,capture)
        need(all(observed[name]==self.prompt['owned_geometry'][name] for name in (
            'pid','birth','candidate_sha256','hwnd','ui_thread','client_rect','window_dpi',
            'window_awareness','thread_awareness','awareness_equal','desktop_name')),
            'DRIVER_PRECLICK_GEOMETRY_CHANGED')
        from tools.local_original_session import shop_wndproc_input
        if self.native_input is None:self.native_input=shop_wndproc_input.Client(runtime.manual.consumer)
        need(type(self.native_input) is shop_wndproc_input.Client,'DRIVER_ORIGINAL_WNDPROC_CLIENT')
        posted=self.native_input.submit(dict(pid=capture.pid,birth=capture.birth,
            candidate_sha256=capture.candidate_sha256),capture.geometry.hwnd,capture.geometry.ui_thread,
            x,y,list(capture.geometry.client_rect),capture.geometry.window_dpi,
            expected_npc_uid=self.spec.features.spawns[0].uid,point_source=('BODY' if role=='NPC' else 'EXPLICIT'))
        self.clicks.append(dict(step=self.index,role=role,post=posted,measurement=row))
        self.capture=None;self.capture_observer=None;self.prompt=None
        self.native_phase=('WAIT_MENU' if role=='NPC' else 'WAIT_LIST' if role=='BUY' else
                           'WAIT_TRADE' if role=='CONFIRM' else 'NEXT_CAPTURE')
        self.phase='WAIT_NATIVE_RETURN'
        self.index+=1;return True
    async def poll(self,monitor):
        if self.phase in ('DONE','UNKNOWN') or self.closed:return self.report()
        task=asyncio.current_task()
        if self.task is None:self.task=task
        try:
            need(task is self.task,'DRIVER_SAME_LOOP_TASK')
            runtime,broker,g=self._current()
            if g is None:self.phase='WAIT_INVENTORY';self._save();return self.report()
            if self.phase in ('WAIT_INVENTORY','WAIT_CAPTURE_ADMISSION','NEXT_CAPTURE'):
                self._capture_request(runtime)
            elif self.phase=='WAIT_CAPTURE':self._capture_ready(runtime)
            elif self.phase=='WAIT_MEASUREMENT':
                from tools.local_original_session import commands
                try:row=commands._json(Path(self.prompt['input_path']),4096)
                except FileNotFoundError:return self.report()
                validate_measurement(row,self.prompt,self.spec,self.spec.steps[self.index].role)
                snapshot=await self._server(broker,g)
                self._current()
                need(snapshot is not None,'DRIVER_NO_PUBLICATION')
                self.baseline=(snapshot.received_ordinal,snapshot.publication_serial)
                self._click(runtime,g,row)
            elif self.phase=='WAIT_NATIVE_RETURN':
                from tools.local_original_session import shop_wndproc_input
                need(type(self.native_input) is shop_wndproc_input.Client and self.native_phase in (
                    'WAIT_MENU','WAIT_LIST','WAIT_TRADE','NEXT_CAPTURE'),'DRIVER_NATIVE_PENDING_CURRENT')
                outcome=self.native_input.collect()
                self._current()
                if outcome['status']=='WAITING':self._save();return self.report()
                need(outcome['status']=='RETURNED','DRIVER_WNDPROC_NOT_RETURNED')
                self.clicks[-1]['native_return']=outcome
                self.phase=self.native_phase;self.native_phase=None
            elif self.phase in ('WAIT_MENU','WAIT_LIST','WAIT_TRADE'):
                snapshot=await self._server(broker,g)
                self._current()
                field={'WAIT_MENU':'menu_json','WAIT_LIST':'listing_json','WAIT_TRADE':'trade_json'}[self.phase]
                value=None if snapshot is None else getattr(snapshot,field)
                if value is not None:
                    event=correlated_event(value,self.baseline,snapshot.publication_serial)
                    if event is None:return self.report() # Same payload with a newer specific receive is allowed.
                    if self.phase=='WAIT_TRADE':
                        need(event['mode']==5 and event['items']==[[self.spec.row_key_u32,self.spec.quantity_i32]],
                             'DRIVER_ACTUAL_REQUEST_ROW_QUANTITY')
                        need(event['delivery']=='DRAINED' and event['adoption'] is not None and event['matches_current_listing'] is True,
                             'DRIVER_ACTUAL_TRADE_NOT_DRAINED')
                        self.trade_event=event;self.phase='WAIT_CLIENT'
                    else:
                        if self.phase=='WAIT_MENU':
                            need(g.game.selection is g.selected,'DRIVER_MENU_SELECTION_CHANGED')
                            validate_menu_event(event,g.mover.snapshot().uid,self.spec.features.spawns[0].uid)
                        self.phase='NEXT_CAPTURE'
            elif self.phase=='WAIT_CLIENT':
                from tools.local_original_session import inventory_observe,inventory
                observer=runtime.manual._inventory_observer
                need(type(observer) is inventory_observe.InventoryObserver,'DRIVER_EXISTING_CLIENT_OBSERVER_REQUIRED')
                snapshot=await self._server(broker,g)
                current_trade=None if snapshot is None or snapshot.trade_json is None else json.loads(snapshot.trade_json)
                need(current_trade is not None and current_trade['transaction_id']==self.trade_event['transaction_id']
                     and hashlib.sha256(g.current_frame).hexdigest()==self.trade_event['adoption']['frame_sha'],
                     'DRIVER_TRADE_CURRENT_FRAME_CHANGED')
                now=time.monotonic_ns()
                if (monitor is not None and time.monotonic()<monitor.next_memory
                        or observer._last_ns is not None and now-observer._last_ns<inventory_observe.MIN_INTERVAL_NS):
                    return self.report()
                if monitor is not None:monitor.next_memory=max(monitor.next_memory,now/1e9+inventory_observe.MIN_INTERVAL_NS/1e9)
                service=getattr(broker,'_shop_trade_delivery',None)
                adoption=None if service is None else service.last_adoption
                need(adoption is not None and adoption.txid==self.trade_event['transaction_id']
                     and adoption.frame is g.current_frame,'DRIVER_EXACT_SHOP_ADOPTION_REQUIRED')
                result=await inventory_observe.InventoryObserver.sample_shop_adoption(
                    observer,g.writer,now_ns=now,adoption=adoption)
                self._current()
                need(hashlib.sha256(g.current_frame).hexdigest()==self.trade_event['adoption']['frame_sha'],
                     'DRIVER_TRADE_FRAME_CHANGED_DURING_CLIENT_READ')
                self.client=dict(result)
                expected=[inventory_observe.InventoryObserver._row(item) for item in inventory.validate_current_collection_frame(
                    g.current_frame,policy=observer.collection_policy)]
                self.phase=client_result_state(result,expected)
            self._save();return self.report()
        except asyncio.CancelledError as error:
            self.phase='UNKNOWN';self.failure='DRIVER_CANCELLED'
            try:self._save()
            except BaseException:pass
            raise
        except Exception as error:
            self.phase='UNKNOWN'
            try:self.failure=str(error)
            except BaseException:self.failure=type(error).__name__
            partial=getattr(error,'client_click_result',None)
            if partial is not None:
                role=None if self.index>=len(self.spec.steps) else self.spec.steps[self.index].role
                try:detached=asdict(partial)
                except BaseException:detached=dict(status='UNKNOWN',metadata_unavailable=True)
                self.clicks.append(dict(step=self.index,role=role,partial=detached,status='UNKNOWN'))
            try:self._save()
            except BaseException as cleanup:
                try:error.add_note('Driver report cleanup failed: '+type(cleanup).__name__)
                except BaseException:pass
            raise # Existing run_session preserves feature failure and owns normal Quit/cleanup.
    def close(self):
        if self.closed:return
        self.closed=True
        if self.phase!='DONE':self.phase='UNKNOWN';self.failure=self.failure or 'DRIVER_CLOSED_INCOMPLETE'
        primary=None
        try:
            if self.native_input is not None:self.native_input.close()
        except BaseException as error:primary=error
        try:self._save()
        except BaseException as error:
            if primary is None:primary=error
            else:
                try:BaseException.add_note(primary,'SHOP native close also failed; primary preserved.')
                except BaseException:pass
        finally:
            self.native_input=None;self.native_phase=None
            self.capture=self.capture_observer=self.generation=self.prompt=None
            self.spec=None;self.task=None
        if primary is not None:raise primary

_METHODS=tuple((n,v) for n,v in vars(Driver).items() if callable(v))
