"""Monotonic-deadline scheduler for world actions, recovery, expiry and respawn.

One-shot entries only: a repeating action reschedules itself from its callback,
so a late tick runs each due entry once and never replays missed repeats.
Entries whose owner generation changed are skipped at run time.
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
import heapq
import itertools
import logging
import time

LOG = logging.getLogger(__name__)


def _owner_key(owner):
    # Entity references cancel by UID so any generation's handles go together.
    return getattr(owner, 'uid', owner)


@dataclass(eq=False, slots=True)
class Handle:
    at: float
    seq: int
    owner: Hashable | None
    kind: str
    callback: Callable[[float], object] = field(repr=False)
    cancelled: bool = False
    done: bool = False


class Scheduler:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 is_current: Callable[[object], bool] | None = None,
                 logger: logging.Logger = LOG):
        self.clock = clock
        self._is_current = is_current
        self._log = logger
        self._heap: list[tuple[float, int, Handle]] = []
        self._seq = itertools.count()
        self._by_owner: dict[object, set[Handle]] = {}

    def __len__(self) -> int:
        return sum(1 for _, _, handle in self._heap if not handle.cancelled)

    def schedule(self, at: float, owner_ref: Hashable | None, kind: str,
                 callback: Callable[[float], object]) -> Handle:
        """Run ``callback(now)`` once at monotonic ``at``. ``owner_ref`` may be None."""
        handle = Handle(at, next(self._seq), owner_ref, kind, callback)
        heapq.heappush(self._heap, (at, handle.seq, handle))
        if owner_ref is not None:
            self._by_owner.setdefault(_owner_key(owner_ref), set()).add(handle)
        return handle

    def _forget(self, handle: Handle) -> None:
        if handle.owner is None:
            return
        key = _owner_key(handle.owner)
        handles = self._by_owner.get(key)
        if handles is not None:
            handles.discard(handle)
            if not handles:
                del self._by_owner[key]

    def cancel(self, handle: Handle) -> bool:
        if handle.cancelled or handle.done:
            return False
        handle.cancelled = True
        self._forget(handle)
        return True

    def cancel_owner(self, owner_ref) -> int:
        """Cancel every pending entry of this entity (dormancy, death, removal)."""
        handles = self._by_owner.pop(_owner_key(owner_ref), set())
        for handle in handles:
            handle.cancelled = True
        return len(handles)

    def next_deadline(self) -> float | None:
        while self._heap and self._heap[0][2].cancelled:
            heapq.heappop(self._heap)
        return self._heap[0][0] if self._heap else None

    def run_due(self, now: float | None = None, *, kinds=None) -> int:
        """Run entries due at ``now`` in (deadline, insertion) order; return count run.

        Entries scheduled by these callbacks wait for the next call even if due.
        ``kinds`` limits an early (between-tick) wake to the opted-in entry
        kinds; every other due entry keeps waiting for its ordinary tick.
        """
        if now is None:
            now = self.clock()
        limit = next(self._seq)
        deferred = []
        ran = 0
        while self._heap and self._heap[0][0] <= now:
            item = heapq.heappop(self._heap)
            handle = item[2]
            if handle.cancelled:
                continue
            if handle.seq > limit or (kinds is not None and handle.kind not in kinds):
                deferred.append(item)
                continue
            handle.done = True
            self._forget(handle)
            if (handle.owner is not None and self._is_current is not None
                    and not self._is_current(handle.owner)):
                continue
            ran += 1
            try:
                handle.callback(now)
            except Exception:
                self._log.exception('world scheduler callback failed: kind=%s', handle.kind)
        for item in deferred:
            heapq.heappush(self._heap, item)
        return ran
