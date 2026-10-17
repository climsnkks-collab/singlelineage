"""CP73 historical identity absence; only query/synchronize retained handles."""
import contextlib
import ctypes as C
import hashlib
from ctypes import wintypes as W
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / 'tools/local_ready_entry_gate'
NATIVE_SHA = '3a0f847caf15ac648664e92a16fa2e82d169fa2e0af4c44658380f75b549c59c'
POLICY_SHA = '06c1bf1d94c04e3337eda2b9acc9eddb16676d0d371af757e358c40dd3b3743d'
PYTHON = 'C:\\Users\\Chansol\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
HISTORICAL_IDENTITIES = ({'pid': 24176, 'birth': '134356955079953043', 'image': PYTHON},
                         {'pid': 43672, 'birth': '134356955078370142', 'image': PYTHON})
RIGHTS = 0x101000


class RetainedKernel:
    """Run original gate on the same handle without reopening or double closing."""
    def __init__(self, kernel, handle, pid, need):
        self.kernel, self.handle, self.pid, self.need = kernel, handle, pid, need
        self.opens = self.closes = 0

    def OpenProcess(self, rights, inherit, pid):
        self.need(rights == RIGHTS and inherit is False and pid == self.pid and self.opens == 0,
                  'PRIOR_RETAINED_OPEN_CONTRACT')
        self.opens += 1
        return self.handle

    def CloseHandle(self, handle):
        self.need(handle == self.handle and self.opens == 1 and self.closes == 0,
                  'PRIOR_RETAINED_CLOSE_CONTRACT')
        self.closes += 1
        return True  # Outer finally owns the sole native close.

    def __getattr__(self, name):
        self.need(name in ('GetProcessTimes', 'QueryFullProcessImageNameW', 'WaitForSingleObject'),
                  'PRIOR_RETAINED_API_CONTRACT')
        return getattr(self.kernel, name)


class RetainedNative:
    def __init__(self, kernel):
        self.k = kernel


def verified_absent(native, ident, original):
    if type(ident) is not dict or ident not in HISTORICAL_IDENTITIES:
        return original(native, ident)
    p = original.__globals__['p']
    p.need(tuple(p.IDENTITIES) == HISTORICAL_IDENTITIES, 'EXACT_HISTORICAL_IDENTITIES_REQUIRED')
    handle = native.k.OpenProcess(RIGHTS, False, ident['pid'])
    if not handle:
        p.need(C.get_last_error() == 87, 'PRIOR_IDENTITY_UNKNOWN')
        return None
    try:
        births = []
        for _ in range(2):
            times = [W.FILETIME() for _ in range(4)]
            p.need(native.k.GetProcessTimes(handle, *(C.byref(t) for t in times)), 'PRIOR_BIRTH_UNKNOWN')
            births.append(str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime))
        p.need(births[0] == births[1], 'PRIOR_RETAINED_BIRTH_CHANGED')
        if births[0] != ident['birth']:
            # The retained handle names another creation epoch. The declared old
            # PID+birth identity is absent; do not query or act on its occupant.
            return None
        kernel = RetainedKernel(native.k, handle, ident['pid'], p.need)
        result = original(RetainedNative(kernel), ident)
        p.need(kernel.opens == kernel.closes == 1, 'PRIOR_ORIGINAL_HANDLE_CONTRACT')
        return result
    finally:
        p.need(native.k.CloseHandle(handle), 'PRIOR_HANDLE_CLOSE_UNKNOWN')


def patch_provider(provider):
    original_module = provider.module

    def module():
        result = original_module()
        wrapped_backend = result.fixed_backend
        backend_function = wrapped_backend.__closure__[0].cell_contents
        namespace = backend_function.__globals__
        original_gate_module = namespace['gate_module']

        @contextlib.contextmanager
        def gate_module():
            with original_gate_module() as gate:
                original_native = gate.Native
                p = original_native.absent.__globals__['p']
                p.need(Path(original_native.absent.__code__.co_filename).resolve() == GATE/'native.py'
                       and Path(p.__file__).resolve() == GATE/'policy.py'
                       and hashlib.sha256((GATE/'native.py').read_bytes()).hexdigest() == NATIVE_SHA
                       and hashlib.sha256((GATE/'policy.py').read_bytes()).hexdigest() == POLICY_SHA
                       and tuple(p.IDENTITIES) == HISTORICAL_IDENTITIES, 'EXACT_ORIGINAL_ABSENCE_GATE_REQUIRED')

                class HistoricalIdentityNative(original_native):
                    def absent(self, ident):
                        return verified_absent(self, ident, original_native.absent)

                gate.Native = HistoricalIdentityNative
                try:
                    yield gate
                finally:
                    gate.Native = original_native

        namespace['gate_module'] = gate_module
        return result

    provider.module = module
    wrapped_context = provider.verified_installed_context
    function = wrapped_context.__closure__[0].cell_contents
    cells = dict(zip(function.__code__.co_freevars, function.__closure__ or ()))
    if 'module' not in cells or cells['module'].cell_contents is not original_module:
        raise ValueError('EXACT_ORIGINAL_CONTEXT_MODULE_CELL_REQUIRED')
    cells['module'].cell_contents = module
    return provider
