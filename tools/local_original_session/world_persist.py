"""Write-behind absolute snapshots, driven by the existing world Scheduler.

Local backend policy: L1J config/server.properties AutosaveInterval=1200 and
AutosaveIntervalOfInventory=300; Client.java doAutoSave separates these saves.
This module does not change the existing broker/inventory transaction contracts.

Call every method and Scheduler.run_due on the single world thread, under the
WorldRuntime lock. No worker threads or extra locks are created. enqueue only
copies memory and schedules work; save I/O happens synchronously during flush.
Keys are caller-owned, stable hashables: e.g. ('inventory', uid), ('character',
uid). Payload shape, filenames and serialization belong to the injected writer.

The writer MUST be an idempotent atomic replacement of an ABSOLUTE snapshot,
not grant/consume/transaction/CAS execution. A replace-then-raise outcome will
be retried with the latest snapshot. The writer returns None or True on success
and raises (or returns False) on failure. It must not be async. Copies isolate
both caller mutation and writer mutation; payloads must support deepcopy.

Logout/death: enqueue final state, then flush(key), or flush_all for multiple
keys. Creation/deletion may use the same immediate path (a deletion snapshot
must be understood idempotently by the writer). Stop producers before shutdown;
shutdown cancels timers and attempts each pending key ONCE, reporting failures.
Failed snapshots remain in memory for inspection/manual flush, not crash-safe
storage: callers must handle a nonempty shutdown result before process exit.
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from copy import deepcopy
from dataclasses import dataclass
import inspect
import logging
import math

from tools.local_original_session.world_scheduler import Handle, Scheduler

LOG = logging.getLogger(__name__)
INVENTORY_INTERVAL = 300.0
CHARACTER_INTERVAL = 1200.0
RETRY_INTERVAL = 5.0


@dataclass(frozen=True)
class SaveFailure:
    key: Hashable
    error: Exception


@dataclass(frozen=True)
class FlushResult:
    """saved acknowledges attempted versions; pending may contain newer ones.

    A reentrant flush performs no writes and reports the still-pending keys.
    ok therefore means the requested scope has no unsaved snapshots remaining.
    """
    saved: tuple[Hashable, ...] = ()
    failures: tuple[SaveFailure, ...] = ()
    pending: tuple[Hashable, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures and not self.pending


@dataclass
class _Pending:
    snapshot: object
    kind: str
    at: float
    revision: int = 1
    handle: Handle | None = None


class WorldPersist:
    def __init__(self, scheduler: Scheduler,
                 save: Callable[[Hashable, object], object], *,
                 inventory_interval: float = INVENTORY_INTERVAL,
                 character_interval: float = CHARACTER_INTERVAL,
                 retry_interval: float = RETRY_INTERVAL,
                 logger: logging.Logger = LOG):
        for interval in (inventory_interval, character_interval, retry_interval):
            if not math.isfinite(interval) or interval <= 0:
                raise ValueError('PERSIST_INTERVAL_MUST_BE_FINITE_POSITIVE')
        self.scheduler = scheduler
        self._save = save
        self._intervals = {'inventory': inventory_interval,
                           'character': character_interval}
        self.retry_interval = retry_interval
        self._log = logger
        self._pending: dict[Hashable, _Pending] = {}
        self._failures: dict[Hashable, Exception] = {}
        self._flushing = False
        self._closed = False

    @property
    def pending_keys(self) -> tuple[Hashable, ...]:
        return tuple(self._pending)

    @property
    def last_failures(self) -> tuple[SaveFailure, ...]:
        """Latest error per key, cleared only by a successful writer call."""
        return tuple(SaveFailure(key, error)
                     for key, error in self._failures.items())

    @property
    def closed(self) -> bool:
        return self._closed

    def snapshot(self, key: Hashable) -> object:
        """Return an isolated copy of an unsaved snapshot; unknown key raises."""
        return deepcopy(self._pending[key].snapshot)

    def enqueue(self, key: Hashable, snapshot: object, *,
                kind: str = 'inventory') -> None:
        """Keep the latest absolute value; updates never postpone its deadline.

        The first dirty request starts its kind's interval. A clean key starts
        a new interval on its next request. An already failed key keeps its
        retry deadline even when a newer snapshot replaces the failed one.
        Use distinct keys for inventory and character snapshots of one owner.
        """
        if self._closed:
            raise RuntimeError('PERSIST_CLOSED')
        interval = self._intervals[kind]
        entry = self._pending.get(key)
        if entry is not None and entry.kind != kind:
            raise ValueError('PERSIST_KEY_KIND_CHANGED')
        copied = deepcopy(snapshot)  # A failed copy leaves the old value intact.
        if entry is None:
            entry = _Pending(copied, kind, self.scheduler.clock() + interval)
            self._pending[key] = entry
            self._schedule(key, entry)
        else:
            entry.snapshot = copied
            entry.revision += 1

    def flush(self, key: Hashable) -> FlushResult:
        """Immediately attempt this key once, independent of its deadline."""
        return self._flush((key,), all_keys=False)

    def flush_all(self) -> FlushResult:
        """Attempt each key present at entry once; new requests stay pending."""
        return self._flush(tuple(self._pending), all_keys=True)

    def shutdown(self) -> FlushResult:
        """Reject new requests, cancel timers and flush once without retries.

        May be called again or followed by manual flush after failure. Never
        loop until success. Do not invoke shutdown from inside the writer.
        """
        if self._flushing:
            raise RuntimeError('PERSIST_FLUSH_IN_PROGRESS')
        self._closed = True
        for entry in self._pending.values():
            self._cancel(entry)
        return self.flush_all()

    def _cancel(self, entry: _Pending) -> None:
        if entry.handle is not None:
            self.scheduler.cancel(entry.handle)
            entry.handle = None

    def _schedule(self, key: Hashable, entry: _Pending) -> None:
        if self._closed:
            return
        # Persistence survives entity death/removal: no entity generation owner.
        entry.handle = self.scheduler.schedule(
            entry.at, None, 'persist-' + entry.kind,
            lambda now: self._flush((key,), all_keys=False, now=now))

    def _flush(self, keys: tuple[Hashable, ...], *, all_keys: bool,
               now: float | None = None) -> FlushResult:
        def remaining():
            return (tuple(self._pending) if all_keys else
                    tuple(key for key in keys if key in self._pending))

        if self._flushing:
            # A newer write must not complete inside an older writer call.
            return FlushResult(pending=remaining())
        if now is None:
            now = self.scheduler.clock()
        saved = []
        failures = []
        self._flushing = True
        try:
            for key in keys:
                entry = self._pending.get(key)
                if entry is None:
                    continue
                self._cancel(entry)
                revision = entry.revision
                error = None
                try:
                    result = self._save(key, deepcopy(entry.snapshot))
                    if inspect.isawaitable(result):
                        if inspect.iscoroutine(result):
                            result.close()
                        raise TypeError('PERSIST_WRITER_MUST_BE_SYNCHRONOUS')
                    if result is not None and result is not True:
                        raise RuntimeError('PERSIST_WRITER_DID_NOT_ACKNOWLEDGE')
                except Exception as exc:
                    error = exc
                    self._failures[key] = exc
                    failures.append(SaveFailure(key, exc))
                    self._log.exception('world persistence failed: key=%r', key)
                else:
                    saved.append(key)
                    self._failures.pop(key, None)
                    if entry.revision == revision:
                        del self._pending[key]
                if key in self._pending:
                    completed_at = max(now, self.scheduler.clock())
                    entry.at = (completed_at + self.retry_interval if error
                                else max(entry.at, completed_at))
                    self._schedule(key, entry)
        finally:
            self._flushing = False
        return FlushResult(tuple(saved), tuple(failures), remaining())
