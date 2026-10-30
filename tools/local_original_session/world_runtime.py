"""World lifetime: one asyncio task ticking due scheduler entries and tick hooks.

Player requests enter through ``dispatch_now`` without waiting for a tick. Ticks
and requests share one asyncio.Lock so they never mutate world state at once.
``request_wake(at)`` lets an opted-in scheduler kind (``precise_kinds``) run at
its exact deadline between ticks; tick hooks and other entries keep the tick.
Callbacks, hooks and dispatched functions run under that lock and must not call
``dispatch_now``/``tick_once`` themselves (no re-entrant locking).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import heapq
import inspect
import logging
import time

from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_scheduler import Scheduler

LOG = logging.getLogger(__name__)
DEFAULT_TICK = 0.150
MIN_TICK = 0.100
MAX_TICK = 0.200


class WorldRuntime:
    def __init__(self, *, entities: EntityRegistry | None = None,
                 scheduler: Scheduler | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 tick_interval: float = DEFAULT_TICK, logger: logging.Logger = LOG):
        if not MIN_TICK <= tick_interval <= MAX_TICK:
            raise ValueError('WORLD_TICK_INTERVAL_100_200MS')
        self.clock = clock
        self.entities = entities if entities is not None else EntityRegistry()
        self.scheduler = scheduler if scheduler is not None else Scheduler(
            clock=clock, is_current=self.entities.is_current, logger=logger)
        self.tick_interval = tick_interval
        self.lock = asyncio.Lock()
        self._log = logger
        self._hooks: list[Callable[[float], object]] = []
        self._task: asyncio.Task | None = None
        # Scheduler kinds allowed to run at an exact between-tick deadline.
        self.precise_kinds: set[str] = set()
        self._wakes: list[float] = []

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def add_tick_hook(self, hook: Callable[[float], object]) -> None:
        """``hook(now)`` runs every tick after due scheduler entries (spawn, AI)."""
        self._hooks.append(hook)

    def remove_tick_hook(self, hook: Callable[[float], object]) -> None:
        self._hooks.remove(hook)

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> asyncio.Task:
        if self.running:
            raise RuntimeError('WORLD_ALREADY_RUNNING')
        loop = loop if loop is not None else asyncio.get_running_loop()
        self._task = loop.create_task(self._run(), name='world-runtime')
        return self._task

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def tick_once(self, now: float | None = None) -> None:
        async with self.lock:
            if now is None:
                now = self.clock()
            self.scheduler.run_due(now)
            for hook in tuple(self._hooks):
                try:
                    hook(now)
                except Exception:
                    self._log.exception('world tick hook failed: %r', hook)

    def request_wake(self, at: float) -> None:
        """Ask the loop to run ``precise_kinds`` entries due at ``at`` before the next tick."""
        if self.precise_kinds:
            heapq.heappush(self._wakes, at)
            if len(self._wakes) > 4096:  # bounded: duplicates collapse on wake
                self._wakes = sorted(set(self._wakes))[:1024]

    async def precise_once(self, now: float | None = None) -> None:
        async with self.lock:
            if now is None:
                now = self.clock()
            self.scheduler.run_due(now, kinds=frozenset(self.precise_kinds))

    async def dispatch_now(self, fn: Callable, *args, **kwargs):
        """Run a player request immediately under the world lock; errors go to the caller."""
        async with self.lock:
            result = fn(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result

    async def _run(self) -> None:
        while True:
            started = time.monotonic()
            try:
                await self.tick_once()
            except Exception:
                self._log.exception('world tick failed')
            tick_end = started + self.tick_interval
            # Between ticks, wake only for requested precise deadlines.
            while True:
                now = time.monotonic()
                wakes = self._wakes
                while wakes and wakes[0] <= self.clock() - 0.5:
                    heapq.heappop(wakes)  # stale request from an old life
                if not wakes or wakes[0] - self.clock() >= tick_end - now:
                    break
                await asyncio.sleep(max(0.0, wakes[0] - self.clock()))
                due = self.clock()
                while wakes and wakes[0] <= due:
                    heapq.heappop(wakes)
                try:
                    await self.precise_once(due)
                except Exception:
                    self._log.exception('world precise wake failed')
            await asyncio.sleep(max(0.0, tick_end - time.monotonic()))
