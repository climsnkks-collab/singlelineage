"""Private original-popup client. Native return is not backend transfer authority.

Uses the actual retained ManualMoveCommands identity/window/current resolver and
its sequence/busy domain. No focus, mouse, packet sender, process launch or retry.
Factory/profile installation and final DLL pin are root-owned integration work.
"""
import json
import os
import threading
from tools.local_original_session import item_transfer_frame as frame
from types import MethodType
from tools.local_original_session import commands, manual_move_commands as original
from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration

CAPABILITY = 'CURRENT_PC_ITEM_QUANTITY_POPUP_V1'
MESSAGE = 'LC-Owned-ItemQuantityPopup-v1'
REQUEST_SCHEMA = 'own-item-quantity-popup-request-v1'
RESULT_SCHEMA = 'own-item-quantity-popup-result-v1'
need = original.need
_MANUAL_TYPE = original.ManualMoveCommands
_CURRENT = _MANUAL_TYPE._current
_WINDOW = _MANUAL_TYPE._window
_CLOCK = _MANUAL_TYPE._clock
_TERMINAL = _MANUAL_TYPE._terminal
_GEN_CURRENT = PersistentBroker.inventory_selection_current


def request(identity, sequence, *, player_uid, anchor_inventory_uid, map_id,
            action, kind, payload_uid, quantity):
    need(type(identity) is dict and set(identity) == {'pid','birth','candidate_sha256'}, 'POPUP_EXACT_IDENTITY')
    for value, maximum in ((identity['pid'],0xffffffff),(identity['birth'],0xffffffffffffffff),
        (sequence,0x7fffffff),(player_uid,0xffffffffffffffff),
        (anchor_inventory_uid,0xffffffffffffffff),(payload_uid,0xffffffffffffffff),(quantity,0x7fffffff)):
        need(type(value) is int and 0 < value <= maximum,'POPUP_EXACT_POSITIVE_INTEGER')
    need(type(map_id) is int and 0 <= map_id <= 0x7fffffff and type(action) is int and action in (1,2)
         and type(kind) is int and kind in (1,2),'POPUP_EXACT_ACTION_KIND_MAP')
    h=identity['candidate_sha256']
    need(type(h) is str and len(h)==64 and all(c in '0123456789abcdef' for c in h),'POPUP_EXACT_IMAGE_SHA')
    return dict(schema=REQUEST_SCHEMA,**identity,seq=sequence,command='ItemQuantityPopup',
        player_uid=player_uid,anchor_inventory_uid=anchor_inventory_uid,map_id=map_id,
        action=action,kind=kind,payload_uid=payload_uid,quantity=quantity)


def result(row, expected):
    keys=set(expected)|{'status','reason','invoked'}
    need(type(row) is dict and set(row)==keys and row.get('schema')==RESULT_SCHEMA,'POPUP_EXACT_RESULT_SCHEMA')
    for key,value in expected.items():
        if key!='schema':need(type(row[key]) is type(value) and row[key]==value,'POPUP_RESULT_IDENTITY_CHANGED')
    need(type(row['status']) is str and row['status'] in ('RETURNED','REFUSED','UNKNOWN','BLOCKED_SOURCE_BINDING')
         and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
         and type(row['invoked']) is bool,'POPUP_EXACT_RESULT_FIELDS')
    return dict(row)


class PopupHost:
    def __init__(self, manual, *, capability):
        need(type(manual) is _MANUAL_TYPE and type(capability) is str and capability==CAPABILITY,'POPUP_EXPLICIT_ACTUAL_CONSUMER')
        self.manual=manual;self.pending=None;self.terminal=False;self.last=None
        self._thread=threading.get_ident();self._claimed=set();self._frame=None
        self._native_return=None  # Successful native settlement; exit-only recheck, never backend authority.
        self._native_refusal=None  # Immutable output only; never an ordinary rearm.
        self._context=(manual.reader,manual.current,manual.clock_ns,manual.reader.owner)
        self._original()

    def _original(self):
        m=self.manual
        need(type(m) is _MANUAL_TYPE and type(m)._current is _CURRENT and type(m)._window is _WINDOW and type(m)._clock is _CLOCK
             and type(m._current) is MethodType and m._current.__self__ is m and m._current.__func__ is _CURRENT
             and type(m._window) is MethodType and m._window.__self__ is m and m._window.__func__ is _WINDOW
             and type(m._clock) is MethodType and m._clock.__self__ is m and m._clock.__func__ is _CLOCK,
             'POPUP_ORIGINAL_CONSUMER_METHODS')
        need(threading.get_ident()==self._thread==m._thread and not self.terminal,'POPUP_THREAD_OR_TERMINAL')
        need(all(a is b for a,b in zip((m.reader,m.current,m.clock_ns,m.reader.owner),self._context)),
             'POPUP_ORIGINAL_CONTEXT_CHANGED')

    def _current(self, expected=None, *, after_command=False):
        self._original();m=self.manual;current=_CURRENT(m)
        broker=current[0].broker;method=broker.inventory_selection_current
        need(type(broker) is PersistentBroker and type(broker).inventory_selection_current is _GEN_CURRENT
             and type(method) is MethodType and method.__self__ is broker and method.__func__ is _GEN_CURRENT,
             'POPUP_ORIGINAL_GENERATION_METHOD')
        generation=method(current[0].writer)
        need(type(generation) is _InventoryGeneration and generation.row is current[1] and generation.writer is current[0].writer,
             'POPUP_CURRENT_GENERATION_REQUIRED')
        values=(current,generation,generation.frame,generation.selected)
        if expected is not None:
            old,gen,frame,selected=expected
            need(current[0].writer is old[0].writer and current[0].broker is old[0].broker
                 and all(a is b for a,b in zip(current[1:5],old[1:5])) and current[5:]==old[5:]
                 and generation is gen and (after_command or generation.frame is frame) and generation.selected is selected,
                 'POPUP_CURRENT_BINDING_CHANGED')
        return values

    def submit(self, *, anchor_inventory_uid, action, kind, payload_uid, quantity):
        m=self.manual
        try:
            self._original()
            need(self.pending is None and m.pending is None and m._busy is False,'POPUP_SHARED_BUSY_OR_PENDING')
            # This same original busy domain remains held until collect/fatal.
            # An intervening ordinary consumer command refuses, never races.
            m._busy=True
            started=m._clock()
            bound=self._current();current=bound[0];position=current[3]
            boundary,identity=current[5:7]
            need(type(m.sequence) is int and 0 <= m.sequence < 0x7fffffff,'POPUP_SEQUENCE_EXHAUSTED')
            sequence=m.sequence+1
            row=request(identity,sequence,player_uid=position.uid,anchor_inventory_uid=anchor_inventory_uid,
                map_id=position.map_id,action=action,kind=kind,payload_uid=payload_uid,quantity=quantity)
            need(len((json.dumps(row,separators=(',',':'))+'\n').encode('ascii'))<=512,'POPUP_REQUEST_BOUND')
            path=boundary/f'item-quantity-popup-request-{sequence}.json'
            output=boundary/f'item-quantity-popup-result-{sequence}.json'
            claim=boundary/f'item-quantity-popup-claim-{sequence}.json'
            need(sequence not in self._claimed and not any(os.path.lexists(p) for p in (path,output,claim)),
                 'POPUP_NO_REPLAY')
            hwnd=_WINDOW(m,current)
            self._current(bound)
            # Consume before disk publication or Post attempt. Never unlink or
            # rewind this claim/sequence after any uncertain side effect.
            self._claimed.add(sequence);m.sequence=sequence
            self._frame=frame.FrameClaim(row,started,original.WAIT_NS,m.clock_ns)
            original._create_once(claim,dict(schema='own-item-quantity-popup-frame-claim-v1',**identity,seq=sequence,action=action,token=self._frame.token))
            original._create_once(path,row)
            user=m.reader.owner.native.u
            message=int(user.RegisterWindowMessageW(MESSAGE))
            need(message>=0xc000,'POPUP_REGISTER_MESSAGE')
            need(0 <= m._clock()-started < original.WAIT_NS,'POPUP_ORIGINAL_DEADLINE')
            checked=self._current(bound);need(_WINDOW(m,checked[0])==hwnd,'POPUP_WINDOW_CHANGED')
            owner=m.reader.owner;desktop=getattr(owner,'private_desktop',None)
            need(desktop is not None,'POPUP_OWNED_NON_INPUT_DESKTOP_REQUIRED')
            self.pending=(row,bound,output,hwnd,started)
            need(desktop.post_command(owner,identity,hwnd,owner.child.tid,message,sequence) is True,'POPUP_POST_UNKNOWN')
            self._current(bound,after_command=True)
            return dict(status='POSTED',sequence=sequence,automatic_retry=False,backend_effect='UNKNOWN')
        except BaseException:
            self.cancel()
            self.terminal=True
            if type(m) is _MANUAL_TYPE:_TERMINAL(m,'POPUP_ADMISSION_OR_POST_UNKNOWN')
            raise

    def collect(self):
        m=self.manual
        try:
            self._original()
            need(self.pending is not None and m._busy is True and m.pending is None,'POPUP_PENDING_REQUIRED')
            row,bound,path,hwnd,started=self.pending
            need(m.sequence==row['seq'],'POPUP_SEQUENCE_CHANGED')
            need(0 <= m._clock()-started < original.WAIT_NS,'POPUP_ORIGINAL_DEADLINE')
            current=self._current(bound,after_command=True);need(_WINDOW(m,current[0])==hwnd,'POPUP_WINDOW_CHANGED')
            if not os.path.lexists(path):return dict(status='WAITING',sequence=row['seq'],automatic_retry=False)
            commands._ordinary(path)
            with path.open('rb') as stream:raw=stream.read(769)
            need(0 < len(raw) <= 768 and b'\x00' not in raw,'POPUP_RESULT_BOUND')
            value=json.loads(raw,object_pairs_hook=commands._unique_object)
            value=result(value,row)
            self._current(bound,after_command=True)
            if value['status']=='REFUSED' and value['invoked'] is False:
                self._native_refusal=(self.pending,tuple(value.items()),commands._ordinary(path).stat())
                raise ValueError('POPUP_NATIVE_REFUSED')
            if value['status']!='RETURNED' or value['invoked'] is not True:
                raise ValueError('POPUP_NATIVE_UNKNOWN')
            settled=(self.pending,tuple(value.items()),commands._ordinary(path).stat())
            self.last=value;self.pending=None;m._busy=False
            cleaned=self.cancel()
            self._native_return=settled if cleaned else None  # Exit-only publication requires close returned.
            return dict(value,proof_scope='ORIGINAL_POPUP_ENTRY_RETURN_ONLY',backend_effect='UNKNOWN')
        except BaseException:
            self.cancel()
            self.terminal=True
            if type(m) is _MANUAL_TYPE:_TERMINAL(m,'POPUP_RESULT_OR_CURRENT_UNKNOWN')
            raise

    def native_refusal(self):
        return None if self._native_refusal is None else dict(self._native_refusal[1])

    def source_quit_return(self, source_quit):
        """Recheck this issued, cleaned RETURNED output only for terminal Quit."""
        from tools.local_original_session.manual_source_quit import SourceQuitRequests
        m=self.manual
        need(type(source_quit) is SourceQuitRequests and source_quit.consumer is m
             and source_quit._busy is True and source_quit._failure_domain == 'BACKEND'
             and type(m) is _MANUAL_TYPE and m.state['status'] == 'UNKNOWN'
             and m._busy is False and m._readonly_pending is None
             and (m._source_quit_owner is None or m._source_quit_owner is source_quit)
             and threading.get_ident()==self._thread==m._thread,'POPUP_EXIT_EXACT_SETTLED_OWNER')
        need(all(a is b for a,b in zip((m.reader,m.current,m.clock_ns,m.reader.owner),self._context)),
             'POPUP_EXIT_ORIGINAL_CONTEXT_CHANGED')
        need(not self.terminal and self.pending is None and self._frame is None
             and self._native_refusal is None and self._native_return is not None,
             'POPUP_EXIT_CLEANED_RETURN_REQUIRED')
        pending,items,old=self._native_return
        row,bound,path,hwnd,started=pending
        expected=dict(items)
        before=commands._ordinary(path).stat()
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
             (old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns),'POPUP_EXIT_RETURN_CHANGED')
        value=commands._closed_health_json(path);after=commands._ordinary(path).stat()
        need((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==
             (old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns),'POPUP_EXIT_RETURN_CHANGED')
        need(result(value,row)==expected and expected['status']=='RETURNED'
             and expected['invoked'] is True and expected['reason']==0,'POPUP_EXIT_RETURN_CHANGED')
        return pending

    def source_quit_refusal(self):
        """Recheck exact settled Popup output while ordinary commands stay terminal."""
        m=self.manual
        need(type(m) is _MANUAL_TYPE and self.terminal and m._busy is True
             and m._readonly_pending is None and threading.get_ident()==self._thread==m._thread,
             'POPUP_EXIT_EXACT_TERMINAL_OWNER')
        need(all(a is b for a,b in zip((m.reader,m.current,m.clock_ns,m.reader.owner),self._context)),
             'POPUP_EXIT_ORIGINAL_CONTEXT_CHANGED')
        need(self._frame is None and self._native_refusal is not None
             and self.pending is self._native_refusal[0],'POPUP_EXIT_SETTLED_REFUSAL_REQUIRED')
        row,bound,path,hwnd,started=self.pending
        expected=dict(self._native_refusal[1]);old=self._native_refusal[2]
        before=commands._ordinary(path).stat()
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
             (old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns),'POPUP_EXIT_RESULT_CHANGED')
        value=commands._closed_health_json(path);after=commands._ordinary(path).stat()
        need((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==
             (old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns),'POPUP_EXIT_RESULT_CHANGED')
        need(result(value,row)==expected and expected['command']=='ItemQuantityPopup'
             and expected['status']=='REFUSED' and expected['invoked'] is False,'POPUP_EXIT_RESULT_CHANGED')
        return self.pending

    def cancel(self):
        # Same pending word. Claimed execution stays UNKNOWN/no retry.
        cleaned=True
        if self._frame is not None:
            try:self._frame.close()
            except BaseException:cleaned=False
            self._frame=None
        return cleaned  # Existing callers may ignore this; no ordinary result changes.
