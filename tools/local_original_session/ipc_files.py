"""Delete-shared bounded live IPC reads; caller serializes local replacements."""
from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import msvcrt
import os
from pathlib import Path
import stat


@contextmanager
def shared_stream(path):
    """Own one READ|WRITE|DELETE-shared handle without granting write access."""
    path = Path(path)
    info = path.lstat()
    if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400 or not stat.S_ISREG(info.st_mode):
        raise ValueError('IPC_ORDINARY_FILE_REQUIRED')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE)
    create.restype = W.HANDLE
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = (W.HANDLE,), W.BOOL
    handle = create(str(path), 0x80000000, 1 | 2 | 4, None, 3, 0x80 | 0x00200000, None)
    if handle == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    # FileIO owns the descriptor, which owns the CreateFile handle.
    with os.fdopen(descriptor, 'rb', buffering=0) as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or getattr(opened, 'st_file_attributes', 0) & 0x400:
            raise ValueError('IPC_ORDINARY_HANDLE_REQUIRED')
        yield stream


def read_shared_text(path, limit=65536):
    if type(limit) is not int or not 0 < limit <= 65536:
        raise ValueError('IPC_READ_BOUND_REQUIRED')
    with shared_stream(path) as stream:
        if os.fstat(stream.fileno()).st_size > limit:
            raise ValueError('IPC_FILE_BYTE_BOUND')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('IPC_FILE_BYTE_BOUND')
    return raw.decode('utf-8')
