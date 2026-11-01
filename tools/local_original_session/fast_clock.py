"""Test-only accelerated virtual time for in-process bot/server checks.

    SL_TEST_TIME_SCALE=10 python -X utf8 -B <wrapper that calls enable_from_env()
                                             before importing broker/bot modules>

Off unless SL_TEST_TIME_SCALE is set to a number other than 1: importing this
module alone changes nothing. When enabled (enable()/enable_from_env()), the
process-wide clocks time.monotonic/_ns, perf_counter/_ns and time/_ns become one
virtual clock, and asyncio's loop.time() (which reads time.monotonic) follows it,
so every asyncio.sleep, wait_for, call_later and asyncio.timeout deadline, the
WorldRuntime tick, scheduler entries, policy ns buckets and bot pacing share it.

Modes (SL_TEST_TIME_MODE):
* ``idle`` (default): virtual time runs 1:1 while Python code runs and K times
  faster only while the event loop waits in its poll. CPU work, file IO and
  in-flight loopback IO keep their real duration, so "processing finished before
  the next timer" orderings and short real-time grace sleeps stay as at K=1.
  A poll never credits past the deadline it was asked to wait for. Real speedup
  is (busy + idle) / (busy + idle / K).
* ``scaled``: virtual = origin + real * K everywhere. Also multiplies CPU/IO
  time by K (a 10 ms save looks like 100 ms), which breaks real-time grace gaps.

The loop policy wraps each new loop's selector/IocpProactor so the blocking poll
waits timeout/K real seconds. Function defaults already bound to the original
clocks (``clock=time.monotonic``) in loaded ``tools.*`` modules are rebound, but
call enable() before importing them anyway. On Windows the process timer
resolution is raised to 1 ms (timeBeginPeriod, per process since Win10 2004).

Short real waits (< 3 ms) are sliced into non-blocking polls plus ~0.5 ms
high-resolution sleeps, because the OS poll only waits whole milliseconds.

Not virtualised: time.sleep, threading.Event/Condition/Lock timeouts, socket
timeouts, datetime.now(), other processes. One event loop per process: two
loops polling in parallel threads would both credit idle time.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time as _time

ENV = 'SL_TEST_TIME_SCALE'
MODE_ENV = 'SL_TEST_TIME_MODE'
MODES = ('idle', 'scaled')
MAX_SCALE = 1000.0

_ORIGINAL = {name: getattr(_time, name) for name in (
    'monotonic', 'monotonic_ns', 'perf_counter', 'perf_counter_ns', 'time', 'time_ns')}
# Real elapsed time comes from perf_counter_ns (QueryPerformanceCounter): on
# Windows before Python 3.13 time.monotonic ticks in ~15.6 ms steps, too coarse
# to measure polls of timeout/K. Origins come from the original monotonic/time.
_real_ns = _ORIGINAL['perf_counter_ns']
_real_monotonic_ns = _ORIGINAL['monotonic_ns']
_real_time_ns = _ORIGINAL['time_ns']
_real_sleep = _time.sleep
SHORT_POLL = 0.003   # real seconds: below this, slice the wait instead of one OS poll
SLICE = 0.0005

_state: dict | None = None


def scale_from_env(environ=None) -> float | None:
    """Return K when acceleration is requested, else None (unset, empty or 1)."""
    raw = (os.environ if environ is None else environ).get(ENV, '').strip()
    if not raw:
        return None
    try:
        scale = float(raw)
    except ValueError as error:
        raise ValueError(f'{ENV} must be a number') from error
    if not 1.0 <= scale <= MAX_SCALE:
        raise ValueError(f'{ENV} must be between 1 and {MAX_SCALE:g}')
    return None if scale == 1.0 else scale


class VirtualClock:
    """Monotonic and wall views of one virtual timeline (never goes backwards)."""

    def __init__(self, scale: float, mode: str = 'idle'):
        if mode not in MODES:
            raise ValueError(f'time mode must be one of {MODES}')
        self.scale = float(scale)
        self.mode = mode
        self.real_start_ns = _real_ns()
        self.real_origin_ns = _real_monotonic_ns()
        self.wall_origin_ns = _real_time_ns()
        self._extra_ns = 0          # idle mode: virtual - real
        self._lock = threading.Lock()
        self.polls = 0
        self.idle_real_ns = 0

    def elapsed_ns(self) -> int:
        real = _real_ns() - self.real_start_ns
        if self.mode == 'scaled':
            return int(real * self.scale)
        return real + self._extra_ns

    def monotonic_ns(self) -> int:
        return self.real_origin_ns + self.elapsed_ns()

    def monotonic(self) -> float:
        return self.monotonic_ns() / 1e9

    def time_ns(self) -> int:
        return self.wall_origin_ns + self.elapsed_ns()

    def time(self) -> float:
        return self.time_ns() / 1e9

    def credit_poll(self, waited_ns: int, timeout: float | None) -> None:
        """idle mode: a poll that really waited ``waited_ns`` counts as K times that,
        capped so virtual time does not pass the poll's own (virtual) deadline."""
        with self._lock:
            self.polls += 1
            self.idle_real_ns += waited_ns
            if self.mode != 'idle' or waited_ns <= 0:
                return
            extra = waited_ns * (self.scale - 1.0)
            if timeout is not None:
                extra = min(extra, timeout * 1e9 - waited_ns)
            if extra > 0:
                self._extra_ns += int(extra)

    def real_elapsed(self) -> float:
        return (_real_ns() - self.real_start_ns) / 1e9

    def virtual_elapsed(self) -> float:
        return self.elapsed_ns() / 1e9


class _ScaledPoll:
    """Selector/IocpProactor proxy: the loop's blocking poll waits timeout/K."""

    def __init__(self, inner, clock: VirtualClock):
        self._fast_inner = inner
        self._fast_clock = clock

    def select(self, timeout=None):
        clock = self._fast_clock
        real_timeout = timeout / clock.scale if timeout is not None and timeout > 0 else timeout
        started = _real_ns()
        try:
            if real_timeout is None or real_timeout <= 0 or real_timeout >= SHORT_POLL:
                return self._fast_inner.select(real_timeout)
            # The OS poll waits whole milliseconds (+~1 ms jitter). Short waits are
            # sliced: non-blocking poll, then high-resolution time.sleep slices
            # (~0.5 ms on Windows), so ready IO is seen within one slice.
            deadline = started + int(real_timeout * 1e9)
            while True:
                events = self._fast_inner.select(0)
                remaining = (deadline - _real_ns()) / 1e9
                if events or remaining <= 0:
                    return events
                _real_sleep(min(remaining, SLICE))
        finally:
            clock.credit_poll(_real_ns() - started, timeout)

    def __getattr__(self, name):
        return getattr(self._fast_inner, name)


def install_loop(loop: asyncio.AbstractEventLoop) -> asyncio.AbstractEventLoop:
    """Make a not-yet-running loop poll at virtual speed (no-op when disabled)."""
    selector = getattr(loop, '_selector', None)
    if _state is not None and selector is not None and not isinstance(selector, _ScaledPoll):
        loop._selector = _ScaledPoll(selector, _state['clock'])
    return loop


def _policy_class(base: type) -> type:
    class FastEventLoopPolicy(base):
        def new_event_loop(self):
            return install_loop(super().new_event_loop())
    return FastEventLoopPolicy


def _rebind_defaults(mapping: dict) -> int:
    """Swap original clock objects held in defaults/globals of loaded tools.* modules."""
    changed = 0

    def swap_function(fn):
        nonlocal changed
        fn = getattr(fn, '__func__', fn)
        defaults = getattr(fn, '__defaults__', None)
        if defaults and any(id(v) in mapping for v in defaults):
            fn.__defaults__ = tuple(mapping.get(id(v), v) for v in defaults)
            changed += 1
        kwdefaults = getattr(fn, '__kwdefaults__', None)
        if kwdefaults and any(id(v) in mapping for v in kwdefaults.values()):
            fn.__kwdefaults__ = {k: mapping.get(id(v), v) for k, v in kwdefaults.items()}
            changed += 1

    for name, module in tuple(sys.modules.items()):
        if module is None or not name.startswith('tools.') or name == __name__:
            continue
        namespace = getattr(module, '__dict__', {})
        for key, value in tuple(namespace.items()):
            if id(value) in mapping:
                namespace[key] = mapping[id(value)]
                changed += 1
            elif isinstance(value, type) and value.__module__ == name:
                for member in vars(value).values():
                    if callable(getattr(member, '__func__', member)):
                        swap_function(member)
            elif callable(value) and getattr(value, '__module__', None) == name:
                swap_function(value)
    return changed


def _timer_resolution(enable: bool) -> bool:
    """1 ms process timer resolution. Windows 11 silently drops it after a few
    seconds for windowless processes unless this process opts out of timer
    power throttling (PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION)."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        winmm = ctypes.WinDLL('winmm')
        if not enable:
            return winmm.timeEndPeriod(1) == 0

        class Throttling(ctypes.Structure):
            _fields_ = [('Version', wintypes.ULONG), ('ControlMask', wintypes.ULONG),
                        ('StateMask', wintypes.ULONG)]
        kernel32 = ctypes.WinDLL('kernel32')
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                   ctypes.c_void_p, wintypes.DWORD]
        state = Throttling(1, 0x4, 0)   # version 1, IGNORE_TIMER_RESOLUTION, not throttled
        kernel32.SetProcessInformation(kernel32.GetCurrentProcess(), 4,   # ProcessPowerThrottling
                                       ctypes.byref(state), ctypes.sizeof(state))
        return winmm.timeBeginPeriod(1) == 0
    except (OSError, AttributeError):
        return False


def enable(scale: float, mode: str = 'idle') -> dict:
    """Turn on virtual time at K=scale for this whole process (idempotent for same K)."""
    global _state
    scale = float(scale)
    if not 1.0 < scale <= MAX_SCALE:
        raise ValueError(f'time scale must be in (1, {MAX_SCALE:g}]')
    if _state is not None:
        if (_state['scale'], _state['mode']) != (scale, mode):
            raise RuntimeError('FAST_CLOCK_ALREADY_ENABLED_WITH_OTHER_SETTINGS')
        return _state
    clock = VirtualClock(scale, mode)
    virtual = dict(monotonic=clock.monotonic, monotonic_ns=clock.monotonic_ns,
                   perf_counter=clock.monotonic, perf_counter_ns=clock.monotonic_ns,
                   time=clock.time, time_ns=clock.time_ns)
    for name, fn in virtual.items():
        setattr(_time, name, fn)
    rebound = _rebind_defaults({id(_ORIGINAL[name]): fn for name, fn in virtual.items()})
    previous_policy = asyncio.get_event_loop_policy()
    asyncio.set_event_loop_policy(_policy_class(type(previous_policy))())
    _state = dict(scale=scale, mode=mode, clock=clock, rebound=rebound,
                  previous_policy=previous_policy, timer_1ms=_timer_resolution(True))
    return _state


def enable_from_env(environ=None) -> dict | None:
    """enable(K, mode) when SL_TEST_TIME_SCALE asks for it; otherwise do nothing."""
    environ = os.environ if environ is None else environ
    scale = scale_from_env(environ)
    if scale is None:
        return None
    mode = environ.get(MODE_ENV, '').strip() or 'idle'
    if mode not in MODES:
        raise ValueError(f'{MODE_ENV} must be one of {MODES}')
    return enable(scale, mode)


def disable() -> None:
    """Restore real clocks and the previous loop policy (rebound defaults stay virtual)."""
    global _state
    if _state is None:
        return
    for name, fn in _ORIGINAL.items():
        setattr(_time, name, fn)
    asyncio.set_event_loop_policy(_state['previous_policy'])
    if _state['timer_1ms']:
        _timer_resolution(False)
    _state = None


def enabled() -> bool:
    return _state is not None


def real_monotonic() -> float:
    """A real high-resolution clock (perf_counter), unaffected by acceleration."""
    return _real_ns() / 1e9


def report() -> dict:
    if _state is None:
        return dict(enabled=False, scale=1.0)
    clock = _state['clock']
    real, virtual = clock.real_elapsed(), clock.virtual_elapsed()
    return dict(enabled=True, scale=clock.scale, mode=clock.mode, real_seconds=round(real, 3),
                virtual_seconds=round(virtual, 3), speedup=round(virtual / real, 2) if real else None,
                poll_idle_real_fraction=round(clock.idle_real_ns / 1e9 / real, 3) if real else None,
                polls=clock.polls, rebound_defaults=_state['rebound'], timer_1ms=_state['timer_1ms'])
