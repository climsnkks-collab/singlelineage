"""One original request and bounded fresh-file observation, no image generation.

Source65/66/72: Native compares current provider180A200 String32 on its
normal lifecycle thread. Host never treats an RPM header as a static lease.
Source69: Director+100 view+20/24/28/2C is the original read rectangle.
Source71/72 normal static/lifecycle borrow must precede passive cache reads.
"""
from __future__ import annotations
import asyncio
from contextlib import ExitStack
import ctypes as C
from ctypes import wintypes as W
import hashlib
from io import BytesIO
import json
import msvcrt
import os
from pathlib import Path
import re
import struct
import threading
import time
import math
from dataclasses import dataclass

from tools.local_original_session import commands, manual_move_commands as m, observe
from tools.local_original_session.item_equipment_ui import ItemEquipmentUIObserver, _WINDOW

need = observe.need
MESSAGE='LC-Owned-OriginalScreenshot-v2'
REQUEST='own-original-screenshot-request-v3'
RESULT_V2='own-original-screenshot-result-v2'
RESULT_V3='own-original-screenshot-result-v3'
RESULT='own-original-screenshot-result-v4'
RESULT_V5='own-original-screenshot-result-v5'
RESULT_V6='own-original-screenshot-result-v6'
COMMAND='OriginalScreenshot'
MAX_FILE=64*1024*1024
MAX_FILES=256
MAX_PIXELS=7680*4320 # Existing selected-window consumer bound, not an engine rule.
NAME=re.compile(r'LinC([0-9]+)\.png\Z',re.ASCII) # Counter input; output is minimum four digits.


def _empty(reason='NOT_REQUESTED'):
    return dict(status='UNKNOWN',reason=reason,invoked=False,native_sequence=None,
        normal_returned=False,async_completion='UNKNOWN',original_completion_callback='UNKNOWN',png_verified=False,
        image_path=None,image_sha256=None,width=None,height=None,
        existing_files_preserved=False,backup_directory=None,cleanup_required=False,getter_gate=None,
        protected_dispatch=None,callback_install='UNKNOWN',direct_capture=False,direct_stage=None)


def _valid_callback(row,request):
    if type(row) is not dict or set(row)!={'schema','pid','birth','candidate_sha256','seq',
            'callback_entered','match_code','unpatched','save_bool','original_return'}:return False
    return (row['schema']=='own-original-screenshot-callback-v2' and
        all(type(row[k]) is type(request[k]) and row[k]==request[k]
            for k in ('pid','birth','candidate_sha256','seq')) and
        row['callback_entered'] is True and type(row['match_code']) is int and
        0<=row['match_code']<=5 and type(row['unpatched']) is bool and
        (type(row['save_bool']) is bool if row['match_code']==0 else row['save_bool'] is None) and
        row['original_return']=='UNKNOWN')


def _valid_callback_install(row,request):
    keys={'schema','pid','birth','candidate_sha256','seq','code','cell_first_false',
        'cell_query_bytes','cell_state','cell_type','cell_protect','cell_allocation_matches',
        'cell_region_matches','cell_value','expected_value','target_first_false',
        'target_query_bytes','target_state','target_type','target_protect',
        'target_allocation_matches'}
    if type(row) is not dict or set(row)!=keys:return False
    if (row['schema']!='own-original-screenshot-callback-install-v1' or
        not all(type(row[k]) is type(request[k]) and row[k]==request[k]
            for k in ('pid','birth','candidate_sha256','seq'))):return False
    code,cell,target=row['code'],row['cell_first_false'],row['target_first_false']
    if (type(code) is not int or not 0<=code<=10 or
        type(cell) is not int or not 0<=cell<=9 or
        type(target) is not int or not 0<=target<=7 or
        type(row['expected_value']) is not int or not 0<=row['expected_value']<=0xffffffffffffffff):return False
    for prefix,first in (('cell',cell),('target',target)):
        count=row[f'{prefix}_query_bytes']
        if type(count) is not int or not 0<=count<=48:return False
        if first==1 and count!=0 or first==2 and count==48:return False
        complete=count==48
        if first in (0,3,4,5,6,7,8,9) and prefix=='cell' and first and not complete:return False
        if first in (0,3,4,5,6,7) and prefix=='target' and first and not complete:return False
        for field in ('state','type','protect'):
            value=row[f'{prefix}_{field}']
            if complete:
                if type(value) is not int or not 0<=value<=0xffffffff:return False
            elif value is not None:return False
    if cell==0 and row['cell_query_bytes'] not in (0,48):return False
    if target==0 and row['target_query_bytes'] not in (0,48):return False
    if code==5 and cell==0 or code==10 and (cell!=0 or target==0):return False
    if code in (1,6,7,8,9,10) and row['cell_query_bytes']!=48:return False
    if code in (1,6,8,9) and row['target_query_bytes']!=48:return False
    if code==1 and (cell!=0 or target!=0 or row['target_query_bytes']!=48):return False
    for field,known in (('cell_allocation_matches',row['cell_query_bytes']==48 and cell in (0,6,7,8,9)),
                        ('cell_region_matches',row['cell_query_bytes']==48 and cell in (0,7,8,9)),
                        ('target_allocation_matches',row['target_query_bytes']==48 and target in (0,6,7))):
        value=row[field]
        if known:
            if type(value) is not bool:return False
        elif value is not None:return False
    value=row['cell_value']
    if (type(value) is not int and value is not None or
        value is not None and not 0<=value<=0xffffffffffffffff or
        (value is not None)!=(cell==9 or cell==0 and row['cell_query_bytes']==48)):return False
    return True


_GATE_KEYS={'first_false','query_bytes','state','type','protect','allocation_matches'}


def _valid_getter_gate(gate):
    if type(gate) is not dict or set(gate)!=_GATE_KEYS:return False
    stage=gate['first_false'];n=gate['query_bytes']
    if type(stage) is not int or not 1<=stage<=7 or type(n) is not int or not 0<=n<=48:return False
    raw=(gate['state'],gate['type'],gate['protect'])
    if stage<=2:
        return (n==0 if stage==1 else n!=48) and all(v is None for v in raw) and gate['allocation_matches'] is None
    if n!=48 or not all(type(v) is int and 0<=v<=0xffffffff for v in raw):return False
    state,kind,protect=raw;allocation=gate['allocation_matches']
    if stage<=5 and allocation is not None:return False
    if stage>=6 and type(allocation) is not bool:return False
    if stage==3:return state!=4096
    if state!=4096:return False
    if stage==4:return kind!=16777216
    if kind!=16777216:return False
    if stage==5:return bool(protect&256)
    if protect&256:return False
    if stage==6:return allocation is False
    return allocation is True and (protect&0xff) not in (32,64,128)


_PROTECTED_KEYS={'stage','gateway_status','gateway_returned','outer_attempted','outer_normal_return',
    'owners_released','seen_nodes','handler_matches','key_length','map_count','map_mask','page_size','exception_code',
    'exception_operation','exception_page','pages'}


def _valid_protected(value):
    if type(value) is not dict or set(value)!=_PROTECTED_KEYS:return False
    if (type(value['stage']) is not int or not 0<=value['stage']<=14 or
        type(value['seen_nodes']) is not int or not 0<=value['seen_nodes']<=512 or
        type(value['handler_matches']) is not int or not 0<=value['handler_matches']<=512 or
        type(value['key_length']) is not int or not 0<=value['key_length']<=512 or
        type(value['map_count']) is not int or not 0<=value['map_count']<=0xffffffffffffffff or
        type(value['map_mask']) is not int or not 0<=value['map_mask']<=0xffffffffffffffff or
        type(value['page_size']) is not int or not 0<=value['page_size']<=0xffffffff or
        any(type(value[k]) is not bool for k in ('gateway_returned','outer_attempted','outer_normal_return','owners_released')) or
        value['outer_normal_return'] and not value['outer_attempted'] or
        type(value['exception_code']) is not int or not 0<=value['exception_code']<=0xffffffff or
        type(value['exception_operation']) is not int or not 0<=value['exception_operation']<=0xffffffffffffffff or
        value['exception_page'] is not None and (type(value['exception_page']) is not int or not 0<=value['exception_page']<=6)):
        return False
    gateway=value['gateway_status'];pages=value['pages']
    if gateway is not None and (type(gateway) is not int or not 0<=gateway<=19):return False
    if value['gateway_returned'] is not (gateway is not None):return False
    if type(pages) is not list or len(pages) not in ((0,) if gateway is None else (1,7)):return False
    for page in pages:
        if (type(page) is not list or len(page)!=10 or
            any(type(n) is not int or not 0<=n<=0xffffffff for n in page) or
            any(page[i] not in (0,1) for i in (0,4,5,9))):return False
    if gateway is None and value['outer_normal_return']:return False
    if gateway is None and value['outer_attempted'] and not (value['stage']==12 and value['exception_code']):return False
    if gateway is None and value['exception_code'] and value['stage']!=12:return False
    if value['exception_code']==0 and (value['exception_operation'] or value['exception_page'] is not None):return False
    return True


@dataclass(frozen=True)
class CaptureGeometry:
    hwnd: int
    pid: int
    ui_thread: int
    window_dpi: int
    thread_awareness: int
    window_awareness: int
    awareness_equal: bool
    sample_tick_ms: int
    raw_crop_bits: tuple
    crop: tuple
    client_rect: tuple
    read_size: tuple
    read_fbo: int
    read_buffer: int
    pbo: int
    row_length: int
    skip_rows: int
    skip_pixels: int
    pack_alignment: int

@dataclass(frozen=True)
class CaptureObservation:
    pid: int
    birth: int
    candidate_sha256: str
    sequence: int
    image_path: str
    image_sha256: str
    width: int
    height: int
    file_identity: tuple
    geometry: CaptureGeometry
    relation: str = 'GL_CLIENT_CORRESPONDENCE_UNESTABLISHED'

def _valid_capture_context(value, pid):
    keys=set(CaptureGeometry.__dataclass_fields__)
    if type(value) is not dict or set(value)!=keys:return False
    def integer(x,low,high):return type(x) is int and low<=x<=high
    if type(value['awareness_equal']) is not bool:return False
    for key in keys-{'raw_crop_bits','crop','client_rect','read_size','awareness_equal'}:
        low,high=(0,0x7fffffff)
        if key in ('hwnd','sample_tick_ms'):low,high=(1 if key=='hwnd' else 0,0xffffffffffffffff)
        elif key in ('pid','ui_thread','window_dpi'):low,high=(1,0xffffffff)
        elif key in ('thread_awareness','window_awareness'):low,high=(0,2)
        if not integer(value[key],low,high):return False
    for key,count,low,high in (('raw_crop_bits',4,0,0xffffffff),('crop',4,0,0x7fffffff),
                               ('client_rect',4,-0x80000000,0x7fffffff),('read_size',2,1,0x7fffffff)):
        row=value[key]
        if type(row) is not list or len(row)!=count or not all(integer(x,low,high) for x in row):return False
    floats=struct.unpack('<ffff',struct.pack('<IIII',*value['raw_crop_bits']))
    if not all(math.isfinite(x) and -2147483648<=x<2147483648 for x in floats):return False
    if [int(x) for x in floats]!=value['crop']:return False
    x,y,w,h=value['crop'];left,top,right,bottom=value['client_rect'];rw,rh=value['read_size']
    return (value['pid']==pid and left==top==0 and right>0 and bottom>0
            and w>0 and h>0 and w*h<=MAX_PIXELS and x+w<=rw and y+h<=rh
            and value['read_buffer']>0 and value['pbo']==0 and value['skip_rows']==value['skip_pixels']==0
            and value['row_length'] in (0,w) and value['pack_alignment'] in (1,2,4,8)
            and (value['read_fbo']!=0 or (rw,rh)==(right-left,bottom-top)))

def _capture_geometry(value):
    return CaptureGeometry(**{k:tuple(v) if type(v) is list else v for k,v in value.items()})

def _context_for_pending(row,pending):
    expected={k:v for k,v in pending['request'].items() if k not in ('expected_base','expected_path')}
    need(_valid_native_reply(row,expected),'SCREENSHOT_REPLY_IDENTITY_OR_TYPES')
    if row['schema']!=RESULT_V6:return None
    need(row['status']=='DIRECT_PNG_RETURNED','SCREENSHOT_CONTEXT_NOT_COMPLETE')
    value=_capture_geometry(row['capture_context'])
    need(value.hwnd==pending['window'] and value.ui_thread==pending['ui_thread'],
         'SCREENSHOT_CONTEXT_WINDOW_CHANGED')
    need(value.crop[2:]==pending['dimensions'],'SCREENSHOT_CONTEXT_DIMENSIONS_CHANGED')
    return value

def _detach_capture(context,request,image):
    need(context.crop[2:]==(image['width'],image['height']),'SCREENSHOT_CONTEXT_PNG_MISMATCH')
    return CaptureObservation(request['pid'],request['birth'],request['candidate_sha256'],request['seq'],
        image['image_path'],image['image_sha256'],image['width'],image['height'],tuple(image['file_identity']),context)

def _valid_native_reply(row,request_echo):
    if type(row) is not dict or type(request_echo) is not dict:return False
    schema=row.get('schema')
    if schema==RESULT_V6:
        if set(row)!=(set(request_echo)|{'schema','status','reason','getter_returned','invoked','normal_returned','cleanup_returned','async_completion','png_verified','getter_gate','protected_dispatch','direct_capture','direct_stage','capture_context'}):return False
        legacy=dict(row);context=legacy.pop('capture_context');legacy['schema']=RESULT_V5
        if not _valid_native_reply(legacy,request_echo):return False
        return (_valid_capture_context(context,request_echo['pid']) if row['status']=='DIRECT_PNG_RETURNED' else context is None)
    if schema not in (RESULT_V2,RESULT_V3,RESULT,RESULT_V5):return False
    expected=dict(request_echo,schema=schema)
    flags={'getter_returned','invoked','normal_returned','cleanup_returned'}
    keys=set(expected)|flags|{'status','reason','async_completion','png_verified'}
    if schema in (RESULT_V3,RESULT,RESULT_V5):keys.add('getter_gate')
    if schema in (RESULT,RESULT_V5):keys.add('protected_dispatch')
    if schema==RESULT_V5:keys.update(('direct_capture','direct_stage'))
    if (set(row)!=keys or not all(type(row[k]) is type(v) and row[k]==v for k,v in expected.items())
            or not all(type(row[k]) is bool for k in flags) or type(row['status']) is not str
            or type(row['reason']) is not int or not 0<=row['reason']<=0xffffffff
            or row['async_completion']!='UNKNOWN' or row['png_verified'] is not False):return False
    if schema==RESULT_V5:
        return (row['getter_gate'] is None and row['protected_dispatch'] is None and
            row['direct_capture'] is True and type(row['direct_stage']) is int and
            1<=row['direct_stage']<=25 and not any(row[k] for k in flags) and
            (row['status']=='DIRECT_PNG_RETURNED' and row['reason']==0 and row['direct_stage']==7 or
             row['status']=='UNKNOWN' and row['reason']==50))
    if schema==RESULT:
        protected=row['protected_dispatch']
        if protected is None and row['status']=='DISPATCH_RETURNED':return False
        if protected is not None:
            if (not _valid_protected(protected) or not _valid_getter_gate(row['getter_gate']) or
                row['getter_gate']['first_false']!=7 or (row['getter_gate']['protect']&0xff)!=1 or
                any(row[k] for k in flags)):
                return False
            if row['status']=='DISPATCH_RETURNED':
                return (row['reason']==0 and protected['gateway_status']==0 and
                    protected['outer_attempted'] and protected['outer_normal_return'] and
                    protected['gateway_returned'] and protected['owners_released'] and protected['exception_code']==0 and
                    protected['page_size']==4096 and protected['map_count']==protected['seen_nodes'] and
                    protected['handler_matches']==1 and 1<=protected['key_length']<=128 and
                    len(protected['pages'])==7 and all(
                        page[0]==page[4]==page[5]==page[9]==1 and
                        page[1]==page[6]==4096 and page[2]==page[7]==16777216 and
                        page[3]&256==page[8]&256==0 and
                        page[3]&0xff in (1,16,32,64,128) and
                        page[8]&0xff in (1,16,32,64,128)
                        for page in protected['pages']) and
                    protected['pages'][0][8]&0xff in (16,32,64,128))
            if row['status']=='REFUSED':return row['reason'] in (45,46) and not protected['outer_attempted']
            return row['status']=='UNKNOWN' and row['reason'] in (36,46,47)
    if schema in (RESULT_V3,RESULT):
        if row['reason']==43:
            return (row['status']=='REFUSED' and not any(row[k] for k in flags)
                    and _valid_getter_gate(row['getter_gate']))
        return row['getter_gate'] is None
    return True


def _ordinary_directory(path,*,absent=False):
    path=Path(path).absolute()
    for part in (path,*path.parents):
        if not part.exists():
            need(absent and part==path,'SCREENSHOT_DIRECTORY_MISSING')
            continue
        info=part.lstat()
        need(not part.is_symlink() and not getattr(info,'st_file_attributes',0)&0x400,
             'SCREENSHOT_REPARSE_DIRECTORY')
    if path.exists():
        need(path.is_dir() and path.resolve(strict=True)==path,'SCREENSHOT_ORDINARY_DIRECTORY')
    return path


def _locked_read(path):
    """Open a file only when no writer/delete handle remains; retain protection."""
    path=commands._ordinary(Path(path).absolute())
    k=C.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=(W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE)
    k.CreateFileW.restype=W.HANDLE
    k.CloseHandle.argtypes=(W.HANDLE,);k.CloseHandle.restype=W.BOOL
    handle=k.CreateFileW(str(path),0x80000000,1,None,3,0x80,None) # share READ, no WRITE/DELETE
    if handle==C.c_void_p(-1).value:
        raise OSError(C.get_last_error(),'SCREENSHOT_FILE_NOT_CLOSED')
    try:
        fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except BaseException:
        k.CloseHandle(handle)
        raise
    return os.fdopen(fd,'rb')


def _metadata(stream):
    s=os.fstat(stream.fileno())
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,
            getattr(s,'st_birthtime_ns',s.st_ctime_ns))


def _read_locked(stream):
    before=_metadata(stream)
    need(0<=before[2]<=MAX_FILE,'SCREENSHOT_FILE_BYTE_BOUND')
    stream.seek(0);data=stream.read(MAX_FILE+1)
    need(len(data)==before[2] and _metadata(stream)==before,'SCREENSHOT_FILE_CHANGED')
    return data,before


class CaptureFiles:
    """Preserve actual preexisting files. Never claim exclusive new-name creation."""
    def __init__(self,capture,backup):
        self.capture=_ordinary_directory(capture,absent=True)
        self.backup=_ordinary_directory(backup,absent=True)
        need(not self.backup.exists(),'SCREENSHOT_BACKUP_REPLAY')
        self.backup.mkdir()
        self.stack=ExitStack();self.before={};self.expected=None;self.closed=False
        try:
            entries=[] if not self.capture.exists() else list(self.capture.iterdir())
            need(len(entries)<=MAX_FILES,'SCREENSHOT_CAPTURE_LIST_BOUND')
            maximum=-1;total=0
            for path in sorted(entries):
                if path.is_dir():
                    _ordinary_directory(path)
                    need(NAME.fullmatch(path.name) is None,'SCREENSHOT_COUNTER_DIRECTORY_UNSUPPORTED')
                    continue
                stream=self.stack.enter_context(_locked_read(path))
                data,info=_read_locked(stream);total+=len(data)
                need(total<=512*1024*1024,'SCREENSHOT_BACKUP_TOTAL_BOUND')
                digest=hashlib.sha256(data).hexdigest()
                with (self.backup/path.name).open('xb') as out:
                    need(out.write(data)==len(data),'SCREENSHOT_BACKUP_WRITE')
                    out.flush();os.fsync(out.fileno())
                self.before[path.name]=(info,digest,stream)
                match=NAME.fullmatch(path.name)
                if match:
                    number=int(match[1]);need(number<2147483647,'SCREENSHOT_NAME_COUNTER_BOUND')
                    maximum=max(maximum,number)
            self.expected=self.capture/f'LinC{maximum+1:04d}.png'
            need(not self.expected.exists(),'SCREENSHOT_NEXT_PATH_ALREADY_EXISTS')
            self.check()
        except BaseException:
            self.close()
            raise

    def check(self,*,final=False):
        need(not self.closed,'SCREENSHOT_PROTECTION_CLOSED')
        _ordinary_directory(self.capture,absent=True)
        actual=set() if not self.capture.exists() else {p.name for p in self.capture.iterdir() if not p.is_dir()}
        need(set(self.before)<=actual,'SCREENSHOT_EXISTING_PATH_MISSING')
        for name,(info,digest,stream) in self.before.items():
            need(_metadata(stream)==info,'SCREENSHOT_EXISTING_FILE_CHANGED')
            actual_info=(self.capture/name).stat()
            need((actual_info.st_dev,actual_info.st_ino,actual_info.st_size,actual_info.st_mtime_ns)==info[:4],
                 'SCREENSHOT_EXISTING_PATH_CHANGED')
            if final:
                data,after=_read_locked(stream)
                need(after==info and hashlib.sha256(data).hexdigest()==digest
                     and hashlib.sha256((self.backup/name).read_bytes()).hexdigest()==digest,
                     'SCREENSHOT_EXISTING_FILE_CHANGED')
        return True

    def ready_to_post(self):
        self.check()
        actual=set() if not self.capture.exists() else {p.name for p in self.capture.iterdir() if not p.is_dir()}
        need(actual==set(self.before) and not self.expected.exists(),'SCREENSHOT_CAPTURE_LIST_CHANGED')

    def png(self,dimensions,published_wall_ns):
        self.check()
        actual=set() if not self.capture.exists() else {p.name for p in self.capture.iterdir() if not p.is_dir()}
        fresh=actual-set(self.before)
        if not fresh:
            return None
        need(fresh=={self.expected.name},'SCREENSHOT_NEW_FILE_IDENTITY_AMBIGUOUS')
        with _locked_read(self.expected) as stream:
            data,info=_read_locked(stream)
            # The exact path was absent immediately before the post. Windows
            # creation timestamps can precede precise time_ns within a clock
            # tick; creation identity is retained, never used as a fine clock.
            need(info[3]>=published_wall_ns and info[4]>0,'SCREENSHOT_FILE_NOT_FRESH')
            decoded=_decode_png(data,dimensions)
            self.check(final=True)
            need(_metadata(stream)==info,'SCREENSHOT_FILE_CHANGED')
        return dict(image_path=str(self.expected),image_sha256=hashlib.sha256(data).hexdigest(),
                    width=decoded[0],height=decoded[1],file_bytes=len(data),
                    file_identity=list(info[:2]),existing_files_preserved=True,
                    backup_directory=str(self.backup))

    def close(self):
        if not self.closed:
            self.closed=True;self.stack.close()


def _decode_png(data,dimensions):
    from PIL import Image
    need(data.startswith(b'\x89PNG\r\n\x1a\n'),'SCREENSHOT_PNG_SIGNATURE')
    with Image.open(BytesIO(data)) as image:
        need(image.format=='PNG' and image.size==tuple(dimensions),'SCREENSHOT_PNG_DIMENSIONS')
        need(image.width*image.height<=MAX_PIXELS,'SCREENSHOT_PNG_PIXEL_BOUND')
        image.verify()
    with Image.open(BytesIO(data)) as image:
        image.load();rgba=image.convert('RGBA');extrema=rgba.getextrema()
        need(extrema[3][1]>0 and any(lo!=hi for lo,hi in extrema[:3]),
             'SCREENSHOT_PNG_EMPTY_OR_UNIFORM_CONTENT')
        return image.size


def _image_prefix(image):
    """B69C56..CC equivalent on supported drive spellings, no normalization.

    Native's same-call GetModuleFileNameW + current cache must agree exactly;
    owner.image is only a proposed file-preservation base, never an API result.
    """
    need(type(image) is str and 4<=len(image.encode('utf-16-le'))//2<260
         and image[0].isascii() and image[0].isalpha() and image[1]==':'
         and image[2] in '/\\','SCREENSHOT_MODULE_SPELLING_UNSUPPORTED')
    parts=re.split(r'[/\\]',image[3:])
    need(all(part and part not in ('.','..') and part[-1] not in '. '
             and not any(ord(c)<32 or c in ':"<>|?*' for c in part) for part in parts),
         'SCREENSHOT_MODULE_SPELLING_UNSUPPORTED')
    last=max(image.rfind('/'),image.rfind('\\'))
    return image[:3 if last==2 else last]


def _create_request(path,row):
    commands._ordinary(path,absent=True)
    raw=(json.dumps(row,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')
    need(len(raw)<=2048,'SCREENSHOT_REQUEST_BYTE_BOUND')
    with path.open('xb') as stream:
        need(stream.write(raw)==len(raw),'SCREENSHOT_REQUEST_PARTIAL')
        stream.flush();os.fsync(stream.fileno())


def _base_and_dimensions(reader,current):
    reader.validate();sampler=reader.sampler
    need(sampler is not None and sampler.b is reader.backend,'SCREENSHOT_EXISTING_READER_REQUIRED')
    base=sampler.g['base'];spent=0;records=[]
    def read(at,size,image=False):
        nonlocal spent
        need(type(at) is int and type(size) is int and 0<size<=4096
             and 0x10000<=at<=0x7fffffffffff-size and spent+size<=8192,
             'SCREENSHOT_PASSIVE_READ_BOUND')
        spent+=size;raw=reader.backend.read(at,size,base if image else None)
        need(type(raw) is bytes and len(raw)==size,'SCREENSHOT_PASSIVE_READ_PARTIAL')
        records.append((at,size,image,raw));return raw
    expected_base=_image_prefix(reader.owner.child.identity['image'])
    provider=_ordinary_directory(Path(expected_base))
    director=struct.unpack('<Q',read(base+0x1807fd8,8,True))[0]
    need(struct.unpack('<Q',read(director,8))[0]==base+0x1237f90,'SCREENSHOT_DIRECTOR_TYPE')
    view=struct.unpack('<Q',read(director+0x100,8))[0]
    need(struct.unpack('<Q',read(view,8))[0]==base+0x123a7d8,'SCREENSHOT_VIEW_TYPE')
    rawrect=read(view+0x20,16);x,y,width,height=struct.unpack('<ffff',rawrect)
    need(all(__import__('math').isfinite(n) for n in (x,y,width,height)),'SCREENSHOT_RECTANGLE')
    width,height=int(width),int(height)
    need(width>0 and height>0 and width*height<=MAX_PIXELS,'SCREENSHOT_DIMENSIONS')
    for at,size,image,raw in tuple(records):
        need(read(at,size,image)==raw,'SCREENSHOT_PASSIVE_READ_CHANGED')
    reader.validate()
    return provider/'Capture',(width,height),expected_base


class OriginalScreenshotObserver(ItemEquipmentUIObserver):
    def __init__(self,manual,*,collection_policy=None):
        super().__init__(manual,collection_policy=collection_policy)
        self.last_result=_empty();self._attempted=False;self._files=None
        self._native_complete=False;self._last_collect_ns=None;self._deadline=None
        self._native_context=None;self._capture_observation=None

    def _unknown(self,reason,*,terminal=False):
        self._capture_observation=None;self._native_context=None
        self._terminal|=terminal;self._requested=False
        self.last_result.update(status='UNKNOWN',reason=reason,cleanup_required=terminal)
        if self._native_complete or self._pending is None:
            if self.consumer._readonly_pending is self:self.consumer._readonly_pending=None
            self._pending=None
        if self._files is not None:
            try:self.last_result['existing_files_preserved']=self._files.check(final=True)
            except Exception:self.last_result['existing_files_preserved']=False
            if self._native_complete or self._pending is None:self._files.close()
        return dict(self.last_result)

    def request(self):
        if self._attempted:return False
        queued=super().request()
        self.last_result=_empty('SCREENSHOT_REQUESTED' if queued else 'SCREENSHOT_CURRENT_UNKNOWN')
        return queued

    def observation(self):
        return dict(self.last_result)

    def capture_observation(self):
        """Detached capture-time measurements only, never current point/owner authority."""
        return self._capture_observation

    async def sample(self):
        c,manual=self.consumer,self.manual
        if self._pending is not None or not self._requested or self._closed or self._attempted:return False
        if manual.closed or manual.pending or manual._polling or manual._inventory_request is not None or manual._inventory_wait is not None or c.pending is not None or c._busy or c._readonly_pending is not None:return False
        now=time.monotonic_ns()
        previous=max((n for n in (self.last_sample_monotonic_ns,manual.last_sample_monotonic_ns) if n is not None),default=None)
        if previous is not None and now-previous<m.SAMPLE_NS:return False
        entered=False
        try:
            current,life=self._current()
            need(self._same(life,self._request_life),'SCREENSHOT_SELECTION_CHANGED')
            async with current[1]['operation_lock']:
                need(not c._busy and c.pending is None,'SCREENSHOT_PENDING_CHANGED')
                c._busy,entered=True,True;self._attempted=True;self._requested=False
                started_wall=time.time_ns()
                self.last_sample_monotonic_ns=now;self._deadline=now+m.WAIT_NS
                need(await current[0].broker._movement_owner(current[0].writer,current[1],current[3]) is True,
                     'SCREENSHOT_NATIVE_OWNER_REQUIRED')
                current,after=self._current();need(self._same(life,after),'SCREENSHOT_SELECTION_CHANGED')
                capture,dimensions,expected_base=_base_and_dimensions(c.reader,current)
                need(c.sequence<m.MAX_SEQUENCE,'SCREENSHOT_SEQUENCE_EXHAUSTED')
                seq=c.sequence+1;boundary,identity=current[5],current[6]
                self._files=CaptureFiles(capture,boundary/f'original-screenshot-before-{seq}')
                self._files.ready_to_post()
                hwnd=_WINDOW(c,current)
                request=dict(schema=REQUEST,**identity,seq=seq,command=COMMAND,
                    expected_base=expected_base,expected_path=str(self._files.expected))
                result=boundary/f'original-screenshot-result-{seq}.json';commands._ordinary(result,absent=True)
                c.sequence=seq # Durable reservation consumes the same existing sequence.
                _create_request(boundary/f'original-screenshot-request-{seq}.json',request)
                user=c.reader.owner.native.u;message=int(user.RegisterWindowMessageW(MESSAGE))
                need(0xc000<=message<=0xffff,'SCREENSHOT_MESSAGE')
                final,after=self._current();need(self._same(life,after) and _WINDOW(c,final)==hwnd,'SCREENSHOT_PREPOST_CHANGED')
                self._files.ready_to_post();need(time.monotonic_ns()<self._deadline,'SCREENSHOT_PREPOST_DEADLINE')
                self._life=life;c._readonly_pending=self
                self._pending=dict(request=request,path=result,life=life,dimensions=dimensions,wall=started_wall,
                    window=hwnd,ui_thread=c.reader.owner.child.tid)
                self.last_result=_empty('SCREENSHOT_PENDING');self.last_result.update(native_sequence=seq,
                    backup_directory=str(self._files.backup),existing_files_preserved=True)
                owner=c.reader.owner;desktop=getattr(owner,'private_desktop',None)
                need(desktop.post_command(owner,identity,hwnd,owner.child.tid,message,seq) is True if desktop is not None
                     else user.PostMessageW(hwnd,message,seq,0),'SCREENSHOT_POST_UNKNOWN')
                final,after=self._current();need(self._same(life,after) and _WINDOW(c,final)==hwnd,'SCREENSHOT_POST_CHANGED')
            self.collect();return True
        except asyncio.CancelledError:
            self._unknown('SCREENSHOT_CANCELLED',terminal=self._pending is not None);raise
        except Exception as error:
            self._unknown(observe.reason(error),terminal=self._pending is not None and not self._native_complete)
            return self.last_sample_monotonic_ns==now
        finally:
            if entered:c._busy=False

    def collect(self):
        pending=self._pending
        if pending is None:return self.observation()
        now=time.monotonic_ns()
        if self._last_collect_ns is not None and now-self._last_collect_ns<m.SAMPLE_NS:return self.observation()
        self._last_collect_ns=now
        try:
            if not self._native_complete:
                try:row=commands._json(pending['path'],2048)
                except FileNotFoundError:
                    need(now<self._deadline,'SCREENSHOT_NATIVE_REPLY_DEADLINE');return self.observation()
                except ValueError as error:
                    metadata=getattr(error,'input_read_metadata',None)
                    pending_publication=(type(metadata) is dict and set(metadata)=={'stage','winerror','same_file'}
                        and (error.args==('INPUT_REQUEST_OPEN_FAILED',) and metadata['stage']=='OPEN'
                             and metadata['winerror'] in (32,33) and metadata['same_file'] is False
                             or error.args==('INPUT_REQUEST_CHANGED',) and metadata['stage']=='FINAL_SIZE_OR_MTIME'
                             and metadata['winerror'] is None and metadata['same_file'] is True))
                    if not pending_publication:raise
                    need(now<self._deadline,'SCREENSHOT_NATIVE_REPLY_DEADLINE');return self.observation()
                expected={k:v for k,v in pending['request'].items() if k not in ('expected_base','expected_path')}
                flags={'getter_returned','invoked','normal_returned','cleanup_returned'}
                need(_valid_native_reply(row,expected),'SCREENSHOT_REPLY_IDENTITY_OR_TYPES')
                self.last_result.update(invoked=row['invoked'],normal_returned=row['normal_returned'],
                                        getter_gate=row.get('getter_gate'),
                                        protected_dispatch=row.get('protected_dispatch'),
                                        direct_capture=row.get('direct_capture',False),
                                        direct_stage=row.get('direct_stage'))
                if row['status']=='DIRECT_PNG_RETURNED':
                    need(row['schema'] in (RESULT_V5,RESULT_V6) and row['direct_stage']==7,
                         'SCREENSHOT_DIRECT_REPLY_STAGE')
                    if row['schema']==RESULT_V6:
                        self._native_context=_context_for_pending(row,pending)
                    self._native_complete=True
                elif row['status']=='DISPATCH_RETURNED':
                    need(row['schema']==RESULT and row['protected_dispatch'] is not None,
                         'SCREENSHOT_REPLY_DISPATCH_STAGE')
                    self._native_complete=True
                elif row['status']=='RETURNED':
                    need(row['reason']==0 and all(row[k] is True for k in flags),'SCREENSHOT_REPLY_STAGE')
                    self._native_complete=True
                elif row['status'] in ('REFUSED','UNAVAILABLE'):
                    need(not row['invoked'] and not row['normal_returned'],'SCREENSHOT_REPLY_REFUSAL_STAGE')
                    self._native_complete=True;return self._unknown('SCREENSHOT_NATIVE_'+row['status'])
                else:raise ValueError('SCREENSHOT_NATIVE_COMPLETION_UNKNOWN')
            sidecar=pending['path'].with_name(f"original-screenshot-callback-install-{pending['request']['seq']}.json")
            try:
                install=commands._json(sidecar,1024)
            except (FileNotFoundError,ValueError):
                pass
            else:
                self.last_result['callback_install']=(
                    {k:install[k] for k in ('code','cell_first_false','cell_protect','cell_value',
                        'expected_value','target_first_false','target_protect')}
                    if _valid_callback_install(install,pending['request']) else 'INVALID')
            sidecar=pending['path'].with_name(f"original-screenshot-callback-{pending['request']['seq']}.json")
            try:
                callback=commands._json(sidecar,1024)
            except (FileNotFoundError,ValueError):
                pass
            else:
                self.last_result['original_completion_callback']=(
                    dict(entered=True,match_code=callback['match_code'],unpatched=callback['unpatched'],
                         save_bool=callback['save_bool'],original_return='UNKNOWN')
                    if _valid_callback(callback,pending['request']) else 'INVALID')
            _current,life=self._current();need(self._same(pending['life'],life),'SCREENSHOT_SELECTION_CHANGED')
            need(now<self._deadline,'SCREENSHOT_ASYNC_PNG_DEADLINE')
            try:image=self._files.png(pending['dimensions'],pending['wall'])
            except OSError as error:
                if getattr(error,'errno',None) in (32,33) and now<self._deadline:return self.observation()
                raise
            if image is None:return self.observation()
            need(time.monotonic_ns()<self._deadline,'SCREENSHOT_PNG_DECODE_DEADLINE')
            if self._native_context is not None:
                self._capture_observation=_detach_capture(self._native_context,pending['request'],image)
            self.last_result.update(image,status='OBSERVED',reason=None,png_verified=True,
                async_completion='CLOSED_STABLE_FRESH_PNG',cleanup_required=False)
            self._pending=None
            if self.consumer._readonly_pending is self:self.consumer._readonly_pending=None
            self._files.close();return self.observation()
        except Exception as error:
            return self._unknown(observe.reason(error),terminal=not self._native_complete)

    def close(self):
        self._closed=True;self._requested=False
        if self._files is not None:self._files.close()
        if self._pending is None and self.consumer._readonly_pending is self:self.consumer._readonly_pending=None
