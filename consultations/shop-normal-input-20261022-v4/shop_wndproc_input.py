"""Once-only owned UI-thread whole-WndProc input; return is not game success."""
import json,os,threading
from types import MethodType
from tools.local_original_session import commands,manual_move_commands as original
from tools.local_original_session.broker import PersistentBroker,_InventoryGeneration

MESSAGE='LC-Owned-ShopWholeWndProc-v1'
REQUEST_SCHEMA='own-shop-whole-wndproc-request-v1'
RESULT_SCHEMA='own-shop-whole-wndproc-result-v1'
need=original.need
_TYPE=original.ManualMoveCommands
_CURRENT=_TYPE._current;_WINDOW=_TYPE._window;_CLOCK=_TYPE._clock;_TERMINAL=_TYPE._terminal
_GEN_CURRENT=PersistentBroker.inventory_selection_current

def request(identity,seq,hwnd,ui_thread,x,y,client_rect,window_dpi,player_uid,expected_npc_uid,point_source):
    need(type(identity) is dict and set(identity)=={'pid','birth','candidate_sha256'},'SHOP_WNDPROC_IDENTITY')
    for value,limit in ((identity['pid'],0xffffffff),(identity['birth'],0xffffffffffffffff),
                       (seq,0x7fffffff),(hwnd,0xffffffffffffffff),(ui_thread,0xffffffff),(player_uid,0xffffffffffffffff)):
        need(type(value) is int and 0<value<=limit,'SHOP_WNDPROC_IDENTITY_INTEGER')
    need(type(expected_npc_uid) is int and 0<=expected_npc_uid<=0xffffffffffffffff,'SHOP_WNDPROC_EXPECTED_NPC_UID')
    need(type(point_source) is str and point_source in ('BODY','EXPLICIT'),'SHOP_WNDPROC_POINT_SOURCE')
    digest=identity['candidate_sha256']
    need(type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'SHOP_WNDPROC_IMAGE')
    need(type(x) is int and type(y) is int and -32768<=x<=32767 and -32768<=y<=32767,'SHOP_WNDPROC_SIGNED_CLIENT')
    need(type(client_rect) is list and len(client_rect)==4 and all(type(v) is int and -0x80000000<=v<=0x7fffffff for v in client_rect)
         and client_rect[0]<=x<client_rect[2] and client_rect[1]<=y<client_rect[3]
         and type(window_dpi) is int and 0<window_dpi<=0xffffffff,'SHOP_WNDPROC_CAPTURE_GEOMETRY')
    return dict(schema=REQUEST_SCHEMA,**identity,seq=seq,hwnd=hwnd,ui_thread=ui_thread,x=x,y=y,
                client_rect=list(client_rect),window_dpi=window_dpi,player_uid=player_uid,expected_npc_uid=expected_npc_uid,point_source=point_source)

def result(value,expected):
    fields={'status','reason','attempted_mask','returned_mask','cleanup_up','cleanup_error','exception_code',
            'fault_area','boundary_rva','registration_stage','hover_key0_state','hover_key0_uid','body_state','body_raw_rect','body_query_rect','point_state','point_failure','point_body_failure','effective_point','pre_move_body_query','unwind_proved','exception_address','exception_access_address','exception_operation'}
    need(type(value) is dict and set(value)==set(expected)|fields and value.get('schema')==RESULT_SCHEMA,'SHOP_WNDPROC_RESULT_SCHEMA')
    for name,want in expected.items():
        if name!='schema':need(type(value[name]) is type(want) and value[name]==want,'SHOP_WNDPROC_RESULT_IDENTITY')
    need(type(value['status']) is str and value['status'] in ('RETURNED','REFUSED','UNKNOWN')
         and type(value['reason']) is int and 0<=value['reason']<=0xffffffff,'SHOP_WNDPROC_RESULT_STATUS')
    need(type(value['registration_stage']) is int and 0<=value['registration_stage']<=9,'SHOP_WNDPROC_REGISTRATION_STAGE')
    need(type(value['exception_code']) is int and 0<=value['exception_code']<=0xffffffff,'SHOP_WNDPROC_EXCEPTION_CODE')
    need(type(value['fault_area']) is int and 0<=value['fault_area']<=4
         and type(value['boundary_rva']) is int and 0<=value['boundary_rva']<=0xffffffff
         and type(value['unwind_proved']) is bool,'SHOP_WNDPROC_FAULT_BOUNDARY')
    for name in ('exception_address','exception_access_address','exception_operation'):
        need(type(value[name]) is int and 0<=value[name]<=0xffffffffffffffff,'SHOP_WNDPROC_FAULT_ADDRESS')
    for name in ('attempted_mask','returned_mask'):
        need(type(value[name]) is int and 0<=value[name]<=7,'SHOP_WNDPROC_RESULT_MASK')
    need(value['returned_mask']&~value['attempted_mask']==0
         and type(value['cleanup_up']) is bool and type(value['cleanup_error']) is bool,'SHOP_WNDPROC_RESULT_CLEANUP')
    state=value['hover_key0_state'];uid=value['hover_key0_uid']
    need(type(state) is str and state in ('NOT_ATTEMPTED','OBSERVED','UNKNOWN'),'SHOP_WNDPROC_HOVER_STATE')
    need((type(uid) is int and 0<=uid<=0xffffffffffffffff) if state=='OBSERVED' else uid is None,
         'SHOP_WNDPROC_HOVER_UID')
    need(state=='NOT_ATTEMPTED' or (value['attempted_mask']&1 and value['returned_mask']&1),
         'SHOP_WNDPROC_HOVER_WITHOUT_MOVE_RETURN')
    need(value['status']!='RETURNED' or state!='NOT_ATTEMPTED','SHOP_WNDPROC_HOVER_NOT_PERFORMED')
    body_state=value['body_state']
    need(type(body_state) is str and body_state in ('NOT_ATTEMPTED','OBSERVED','UNKNOWN'),'SHOP_WNDPROC_BODY_STATE')
    for name in ('body_raw_rect','body_query_rect'):
        rect=value[name]
        need((type(rect) is list and len(rect)==4 and all(type(n) is int and -0x80000000<=n<=0x7fffffff for n in rect))
             if body_state=='OBSERVED' else rect is None,'SHOP_WNDPROC_BODY_RECT')
    need(body_state=='NOT_ATTEMPTED' or (value['attempted_mask']&1 and value['returned_mask']&1),
         'SHOP_WNDPROC_BODY_WITHOUT_MOVE_RETURN')
    failure=value['point_failure']
    need(type(failure) is str and failure in ('NONE','G_OWNER','KEY4_PROFILE','SCENE_OWNER','CHILD_MEMBERSHIP','BODY_CACHE','VIEW_MAPPING','POINT_PROJECTION','CURRENT_CHANGED'),'SHOP_WNDPROC_POINT_FAILURE')
    body_failure=value['point_body_failure']
    need(type(body_failure) is str and body_failure in ('NONE', 'CURRENT_INITIAL', 'REGISTRY', 'REGISTRY_UID_MISSING', 'COMPONENTS', 'CURRENT_ACTION_READ', 'CURRENT_ACTION_NULL', 'CURRENT_ACTION_PROFILE', 'ACTION_FIELDS', 'SPR_LOOKUP', 'SPR_MISSING', 'ACTION_LOOKUP', 'ACTION_FRAME', 'COMPONENT_FRAME', 'RESOURCE_KEYS', 'RESOURCE_LOOKUP', 'RESOURCE_MISSING', 'RESOURCE_NULL', 'CHILD_SELECTION', 'CHILD_NULL', 'TILE_GEOMETRY', 'SHAPE_FIELDS', 'RAW_RECT', 'CORRECTION_ACTION', 'CORRECTION_FRAME', 'CORRECTION_KEY', 'CORRECTION_LOOKUP', 'CORRECTION_CHILD', 'CORRECTION_TOP', 'POSE_READ', 'QUERY_MATH', 'CURRENT_FINAL', 'ACTION_REREAD', 'ACTION_CHANGED', 'TOKEN_REREAD', 'TOKEN_CHANGED'),'SHOP_WNDPROC_POINT_BODY_FAILURE')
    need((failure=='BODY_CACHE')==(body_failure!='NONE'),'SHOP_WNDPROC_POINT_BODY_FAILURE_STATE')
    need((failure!='NONE') if value['point_state']=='UNKNOWN' else failure=='NONE','SHOP_WNDPROC_POINT_FAILURE_STATE')
    point_state=value['point_state'];point=value['effective_point'];pre=value['pre_move_body_query']
    need(type(point_state) is str and point_state in ('NOT_ATTEMPTED','READY','UNKNOWN'),'SHOP_WNDPROC_POINT_STATE')
    need((type(point) is list and len(point)==2 and all(type(n) is int and -32768<=n<=32767 for n in point)) if point_state=='READY' else point is None,'SHOP_WNDPROC_EFFECTIVE_POINT')
    if point_state=='READY':
        need(expected['client_rect'][0]<=point[0]<expected['client_rect'][2] and expected['client_rect'][1]<=point[1]<expected['client_rect'][3],'SHOP_WNDPROC_POINT_BOUNDS')
        if expected['point_source']=='BODY':
            need(type(pre) is list and len(pre)==4 and all(type(n) is int and -0x80000000<=n<=0x7fffffff for n in pre) and pre[0]<pre[2] and pre[1]<pre[3],'SHOP_WNDPROC_PRE_BODY_QUERY')
        else:need(point==[expected['x'],expected['y']] and pre is None,'SHOP_WNDPROC_EXPLICIT_POINT')
    else:need(pre is None,'SHOP_WNDPROC_POINT_WITHOUT_READY')
    need(not value['attempted_mask'] or point_state=='READY','SHOP_WNDPROC_ATTEMPT_WITHOUT_POINT')
    need(value['status']!='RETURNED' or point_state=='READY','SHOP_WNDPROC_RETURN_WITHOUT_POINT')
    need(value['status']!='RETURNED' or (value['reason']==0 and value['attempted_mask']==value['returned_mask']==7
         and not value['cleanup_up'] and not value['cleanup_error']),'SHOP_WNDPROC_RETURN_INCOMPLETE')
    need(value['status']!='RETURNED' or (value['exception_code']==0 and value['fault_area']==0
         and value['boundary_rva']==0 and value['registration_stage']==0),'SHOP_WNDPROC_RETURN_FAULT')
    return dict(value)

def clean_refusal(value):
    reason=value['reason']
    boundary=value['boundary_rva']
    return (value['status']=='REFUSED' and reason in (7,8,62004,62005)
        and value['hover_key0_state']=='NOT_ATTEMPTED' and value['hover_key0_uid'] is None
        and value['body_state']=='NOT_ATTEMPTED' and value['body_raw_rect'] is None and value['body_query_rect'] is None
        and (boundary in (0xef5480,0xef4647) if reason in (7,8) else boundary==0)
        and not any(value[k] for k in ('attempted_mask','returned_mask','cleanup_up','cleanup_error',
            'exception_code','fault_area','registration_stage','unwind_proved','exception_address','exception_access_address','exception_operation')))

class Client:
    def __init__(self,manual):
        need(type(manual) is _TYPE,'SHOP_WNDPROC_ORIGINAL_MANUAL')
        self.manual=manual;self.pending=None;self.closed=False;self.last=None
        self.thread=threading.get_ident();self.owns_busy=False
        self.context=(manual.reader,manual.current,manual.clock_ns,manual.reader.owner)
        self._original()
    def _original(self):
        m=self.manual
        need(not self.closed and threading.get_ident()==self.thread==m._thread,'SHOP_WNDPROC_THREAD_OR_CLOSED')
        for name,function in (('_current',_CURRENT),('_window',_WINDOW),('_clock',_CLOCK),('_terminal',_TERMINAL)):
            method=getattr(m,name)
            need(type(method) is MethodType and method.__self__ is m and method.__func__ is function
                 and getattr(type(m),name) is function,'SHOP_WNDPROC_ORIGINAL_METHOD')
        need(all(a is b for a,b in zip((m.reader,m.current,m.clock_ns,m.reader.owner),self.context)),
             'SHOP_WNDPROC_CONTEXT_CHANGED')
    def _current(self,before=None):
        self._original();m=self.manual;current=_CURRENT(m)
        broker=current[0].broker;method=broker.inventory_selection_current
        need(type(broker) is PersistentBroker and type(method) is MethodType and method.__self__ is broker
             and method.__func__ is _GEN_CURRENT and type(broker).inventory_selection_current is _GEN_CURRENT,
             'SHOP_WNDPROC_ORIGINAL_GENERATION')
        generation=method(current[0].writer)
        need(type(generation) is _InventoryGeneration and generation.phase=='ACTIVE' and generation.writer is current[0].writer
             and generation.row is current[1] and generation.selected is generation.game.selection,
             'SHOP_WNDPROC_CURRENT_GENERATION')
        if before is not None:
            old,g=before
            need(generation is g and current[0].writer is old[0].writer and current[0].broker is old[0].broker
                 and current[1] is old[1] and current[2] is old[2] and current[4] is old[4]
                 and current[5:7]==old[5:7]
                 and (current[3].uid,current[3].name,current[3].map_id)==(old[3].uid,old[3].name,old[3].map_id),
                 'SHOP_WNDPROC_SELECTION_CHANGED')
        return current,generation
    def submit(self,identity,hwnd,ui_thread,x,y,client_rect,window_dpi,*,expected_npc_uid,point_source):
        m=self.manual
        try:
            self._original()
            need(self.pending is None and not self.owns_busy and m._busy is False and m.pending is None
                 and m._readonly_pending is None and m._source_quit_owner is None,'SHOP_WNDPROC_SHARED_BUSY')
            m._busy=True;self.owns_busy=True
            started=_CLOCK(m);bound=self._current();current,g=bound
            need(identity==current[6],'SHOP_WNDPROC_CURRENT_IDENTITY')
            need(_WINDOW(m,current)==hwnd,'SHOP_WNDPROC_CURRENT_WINDOW')
            need(type(m.sequence) is int and 0<=m.sequence<0x7fffffff,'SHOP_WNDPROC_SEQUENCE_EXHAUSTED')
            seq=m.sequence+1;row=request(identity,seq,hwnd,ui_thread,x,y,client_rect,window_dpi,current[3].uid,expected_npc_uid,point_source)
            path=current[5]/f'shop-wndproc-request-{seq}.json'
            output=current[5]/f'shop-wndproc-result-{seq}.json'
            need(not any(os.path.lexists(p) for p in (path,output)),'SHOP_WNDPROC_NO_REPLAY')
            # Consume before publication/post; uncertain side effects never rewind.
            m.sequence=seq
            self.pending=(row,bound,output,started)
            original._create_once(path,row)
            message=int(m.reader.owner.native.u.RegisterWindowMessageW(MESSAGE))
            need(0xc000<=message<=0xffff,'SHOP_WNDPROC_REGISTER_MESSAGE')
            self._current(bound)
            need(_WINDOW(m,current)==hwnd and 0<=_CLOCK(m)-started<original.WAIT_NS,'SHOP_WNDPROC_POST_CURRENT')
            owner=m.reader.owner;desktop=owner.private_desktop
            need(desktop is not None and desktop.post_command(owner,identity,hwnd,ui_thread,message,seq) is True,
                 'SHOP_WNDPROC_POST_UNKNOWN')
            self._current(bound)
            return dict(status='POSTED',sequence=seq,automatic_retry=False,game_effect='UNKNOWN')
        except BaseException as primary:
            try:
                if threading.get_ident()==self.thread:self._fail('SHOP_WNDPROC_ADMISSION_UNKNOWN')
            except BaseException:BaseException.add_note(primary,'SHOP WndProc terminal cleanup refused; primary preserved.')
            raise
    def collect(self):
        m=self.manual
        try:
            self._original()
            need(self.pending is not None and self.owns_busy and m._busy is True and m.pending is None,
                 'SHOP_WNDPROC_PENDING')
            row,bound,path,started=self.pending
            need(m.sequence==row['seq'] and 0<=_CLOCK(m)-started<original.WAIT_NS,'SHOP_WNDPROC_ORIGINAL_DEADLINE')
            current,g=self._current(bound)
            need(_WINDOW(m,current)==row['hwnd'],'SHOP_WNDPROC_WINDOW_CHANGED')
            try:value=commands._closed_health_json(path)
            except FileNotFoundError:return dict(status='WAITING',sequence=row['seq'])
            if value is None:return dict(status='WAITING',sequence=row['seq'])
            value=result(value,row)
            self.last=value  # Detached validated output, not current authority.
            self._current(bound)
            if clean_refusal(value):
                # Native consumed this exact valid sequence without invoking any
                # whole message. Close only SHOP; original Manual/Quit stays live.
                self.closed=True;self.pending=None;m._busy=False;self.owns_busy=False
                return dict(value,proof_scope='ORIGINAL_WHOLE_WNDPROC_NOT_INVOKED',game_effect='UNKNOWN')
            need(value['status']=='RETURNED','SHOP_WNDPROC_NATIVE_NOT_RETURNED')
            self.last=value;self.pending=None;m._busy=False;self.owns_busy=False
            return dict(value,proof_scope='ORIGINAL_WHOLE_WNDPROC_RETURN_ONLY',game_effect='UNKNOWN')
        except BaseException as primary:
            try:
                if threading.get_ident()==self.thread:self._fail('SHOP_WNDPROC_RESULT_UNKNOWN')
            except BaseException:BaseException.add_note(primary,'SHOP WndProc terminal cleanup refused; primary preserved.')
            raise
    def _fail(self,reason):
        m=self.manual
        need(threading.get_ident()==self.thread==m._thread,'SHOP_WNDPROC_CLEANUP_THREAD')
        if not self.closed:
            self.closed=True
            acquired=self.owns_busy and m._busy is True and m.pending is None and m._source_quit_owner is None
            if self.pending is not None:
                self.last=dict(status='UNKNOWN',reason=reason,sequence=self.pending[0]['seq'],
                    cancellation='REQUESTED_NOT_CONFIRMED',native_effect='UNKNOWN',
                    native_result=self.last if self.last is not None and self.last.get('seq')==self.pending[0]['seq'] else None)
            try:
                if self.pending is not None:
                    row,bound,path,started=self.pending
                    cancel=bound[0][5]/f"shop-wndproc-cancel-{row['seq']}.json"
                    # Immutable exact-owner/run/sequence cancellation. A dequeue
                    # already inside the original call remains UNKNOWN.
                    original._create_once(cancel,row)
            finally:
                try:
                    if acquired:_TERMINAL(m,reason)
                finally:
                    self.pending=None
                    if acquired:m._busy=False
                    self.owns_busy=False
    def close(self):
        if self.closed:return
        need(threading.get_ident()==self.thread==self.manual._thread,'SHOP_WNDPROC_CLEANUP_THREAD')
        if self.pending is not None:self._fail('SHOP_WNDPROC_CLOSED_PENDING')
        else:self.closed=True
