"""Capture only the exact owned LC window without desktop pixels."""
import argparse
import ctypes as C
import json
import uuid
from ctypes import wintypes as W
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
TARGET=(ROOT/'work/standalone_boot/current-unmodified-clone/LC.exe').resolve()
OUTPUT=ROOT/'work/local_native_scene_current'
user=C.WinDLL('user32',use_last_error=True)
gdi=C.WinDLL('gdi32',use_last_error=True)
kernel=C.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.argtypes=(W.DWORD,W.BOOL,W.DWORD);kernel.OpenProcess.restype=W.HANDLE
kernel.GetProcessTimes.argtypes=(W.HANDLE,*([C.POINTER(W.FILETIME)]*4));kernel.GetProcessTimes.restype=W.BOOL
kernel.QueryFullProcessImageNameW.argtypes=(W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD));kernel.QueryFullProcessImageNameW.restype=W.BOOL
kernel.CloseHandle.argtypes=(W.HANDLE,);kernel.CloseHandle.restype=W.BOOL
user.EnumWindows.argtypes=(C.c_void_p,W.LPARAM);user.EnumWindows.restype=W.BOOL
user.GetWindowThreadProcessId.argtypes=(W.HWND,C.POINTER(W.DWORD));user.GetWindowThreadProcessId.restype=W.DWORD
user.IsWindowVisible.argtypes=(W.HWND,);user.IsWindowVisible.restype=W.BOOL
user.GetWindowRect.argtypes=(W.HWND,C.c_void_p);user.GetWindowRect.restype=W.BOOL
user.GetWindowDC.argtypes=(W.HWND,);user.GetWindowDC.restype=W.HDC
user.PrintWindow.argtypes=(W.HWND,W.HDC,W.UINT);user.PrintWindow.restype=W.BOOL
user.ReleaseDC.argtypes=(W.HWND,W.HDC);user.ReleaseDC.restype=C.c_int
gdi.CreateCompatibleDC.argtypes=(W.HDC,);gdi.CreateCompatibleDC.restype=W.HDC
gdi.CreateCompatibleBitmap.argtypes=(W.HDC,C.c_int,C.c_int);gdi.CreateCompatibleBitmap.restype=W.HBITMAP
gdi.SelectObject.argtypes=(W.HDC,W.HGDIOBJ);gdi.SelectObject.restype=W.HGDIOBJ
gdi.GetDIBits.argtypes=(W.HDC,W.HBITMAP,W.UINT,W.UINT,C.c_void_p,C.c_void_p,W.UINT);gdi.GetDIBits.restype=C.c_int
gdi.DeleteObject.argtypes=(W.HGDIOBJ,);gdi.DeleteObject.restype=W.BOOL
gdi.DeleteDC.argtypes=(W.HDC,);gdi.DeleteDC.restype=W.BOOL

class RECT(C.Structure):
    _fields_=[('left',W.LONG),('top',W.LONG),('right',W.LONG),('bottom',W.LONG)]
class BITMAPINFOHEADER(C.Structure):
    _fields_=[('biSize',W.DWORD),('biWidth',W.LONG),('biHeight',W.LONG),
              ('biPlanes',W.WORD),('biBitCount',W.WORD),('biCompression',W.DWORD),
              ('biSizeImage',W.DWORD),('biXPelsPerMeter',W.LONG),
              ('biYPelsPerMeter',W.LONG),('biClrUsed',W.DWORD),('biClrImportant',W.DWORD)]
class BITMAPINFO(C.Structure):
    _fields_=[('bmiHeader',BITMAPINFOHEADER),('bmiColors',W.DWORD*3)]

def need(ok,reason):
    if not ok:raise ValueError(reason)
def identity(pid,birth):
    handle=kernel.OpenProcess(0x1000,False,pid)
    need(handle,'PROCESS_QUERY_DENIED')
    try:
        times=[W.FILETIME()for _ in range(4)]
        need(kernel.GetProcessTimes(handle,*(C.byref(t)for t in times)),
             'PROCESS_BIRTH_UNKNOWN')
        actual=str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)
        name=C.create_unicode_buffer(32768);length=W.DWORD(len(name))
        need(kernel.QueryFullProcessImageNameW(handle,0,name,C.byref(length)),
             'PROCESS_IMAGE_UNKNOWN')
        need(actual==birth and Path(name.value).resolve()==TARGET,'EXACT_OWNED_LC_REQUIRED')
    finally:kernel.CloseHandle(handle)

def windows(pid):
    found=[]
    CALLBACK=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    def visit(hwnd,unused):
        owner=W.DWORD()
        user.GetWindowThreadProcessId(hwnd,C.byref(owner))
        if owner.value==pid and user.IsWindowVisible(hwnd):
            rect=RECT()
            if user.GetWindowRect(hwnd,C.byref(rect)):
                width=rect.right-rect.left;height=rect.bottom-rect.top
                if 320<=width<=7680 and 200<=height<=4320:
                    found.append((width*height,hwnd,width,height))
        return True
    cb=CALLBACK(visit)
    need(user.EnumWindows(cb,0),'WINDOW_ENUM_FAILED')
    return sorted(found,reverse=True)

def capture(pid,birth):
    identity(pid,birth)
    choices=windows(pid)
    need(choices,'OWNED_WINDOW_NOT_VISIBLE')
    _,hwnd,width,height=choices[0]
    window_dc=user.GetWindowDC(hwnd)
    need(window_dc,'WINDOW_DC_DENIED')
    memory_dc=gdi.CreateCompatibleDC(window_dc)
    bitmap=gdi.CreateCompatibleBitmap(window_dc,width,height)
    need(memory_dc and bitmap,'BITMAP_ALLOCATION_FAILED')
    previous=gdi.SelectObject(memory_dc,bitmap)
    try:
        printed=bool(user.PrintWindow(hwnd,memory_dc,2))
        info=BITMAPINFO()
        info.bmiHeader.biSize=C.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth=width
        info.bmiHeader.biHeight=-height
        info.bmiHeader.biPlanes=1
        info.bmiHeader.biBitCount=32
        info.bmiHeader.biCompression=0
        pixels=C.create_string_buffer(width*height*4)
        copied=gdi.GetDIBits(memory_dc,bitmap,0,height,pixels,C.byref(info),0)
        need(copied==height,'BITMAP_READ_FAILED')
        image=Image.frombytes('RGBA',(width,height),pixels.raw,'raw','BGRA')
        rgb=image.convert('RGB')
        OUTPUT.mkdir(exist_ok=True)
        token=uuid.uuid4().hex
        path=OUTPUT/('screen-'+token+'.png')
        rgb.save(path)
        grayscale=rgb.convert('L')
        extrema=grayscale.getextrema()
        report={'schema':'lc-owned-window-capture-v1','pid':pid,'birth':birth,
                'width':width,'height':height,'printwindow_returned':printed,
                'grayscale_extrema':list(extrema),'visible_character_screen_verified':False,
                'path':str(path)}
        report_path=OUTPUT/('screen-'+token+'.json')
        with report_path.open('x',encoding='utf-8')as stream:
            json.dump(report,stream,indent=2);stream.write('\n')
        return {'status':'CAPTURED','path':str(path),'report':str(report_path),
                'width':width,'height':height,'printwindow_returned':printed,
                'grayscale_extrema':list(extrema)}
    finally:
        gdi.SelectObject(memory_dc,previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory_dc)
        user.ReleaseDC(hwnd,window_dc)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--capture',action='store_true')
    p.add_argument('--pid',type=int)
    p.add_argument('--birth')
    args=p.parse_args()
    if not args.capture:
        print(json.dumps({'status':'PLAN','exact_owned_pid_birth_required':True,
                          'desktop_pixels_captured':False}));return 0
    need(args.pid and args.birth and args.birth.isdecimal(),'EXACT_IDENTITY_REQUIRED')
    print(json.dumps(capture(args.pid,args.birth)))
    return 0
if __name__=='__main__':raise SystemExit(main())
