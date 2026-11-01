"""Explicit instance extension points for the serialized world runtime.

Registration is startup work. Empty event lists retain core behavior. Critical
state/transaction callbacks propagate failures; advisory observers may explicitly
choose isolation. Wrappers compose around the actual preceding implementation.
"""
from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


class WorldEvents:
    def __init__(self):
        self._callbacks = {}
        self.errors = []

    def add(self, owner, event, callback, *, isolate=False, priority=20):
        entries = self._callbacks.setdefault(event, [])
        if any(key == owner and function == callback for _, key, function, _ in entries):
            raise ValueError(f'DUPLICATE_WORLD_EVENT:{owner}:{event}')
        entry = (priority, owner, callback, isolate)
        entries.append(entry)
        entries.sort(key=lambda row: row[0])  # stable; ordering is startup work
        return entry

    def remove(self, event, entry):
        self._callbacks[event].remove(entry)

    def _values(self, event, *args, **kwargs):
        for _, owner, callback, isolate in tuple(self._callbacks.get(event, ())):
            try:
                yield callback(*args, **kwargs)
            except Exception as error:
                if not isolate:
                    raise
                self.errors.append((owner, event, type(error).__name__))
                del self.errors[:-16]
                LOG.exception('Optional world observer failed: %s/%s', owner, event)

    def emit(self, event, *args, **kwargs):
        for _ in self._values(event, *args, **kwargs):
            pass

    def collect(self, event, *args, **kwargs):
        return tuple(self._values(event, *args, **kwargs))

    def first(self, event, *args, default=None, **kwargs):
        for value in self._values(event, *args, **kwargs):
            if value is not None:
                return value
        return default

    def chain(self, event, *args, **kwargs):
        return any(self._values(event, *args, **kwargs))

    def fold(self, event, value, *args, **kwargs):
        for _, owner, callback, isolate in tuple(self._callbacks.get(event, ())):
            try:
                value = callback(value, *args, **kwargs)
            except Exception as error:
                if not isolate:
                    raise
                self.errors.append((owner, event, type(error).__name__))
                del self.errors[:-16]
                LOG.exception('Optional world observer failed: %s/%s', owner, event)
        return value


class _WrapperHandle:
    def __init__(self, registry, key, owner):
        self.registry, self.key, self.owner = registry, key, owner
        self.closed = False

    def close(self):
        if not self.closed:
            self.registry._remove(self.key, self.owner)
            self.closed = True


class _PreparedWrapper:
    """Reserve once at startup, then install once at the owner's activation point."""
    def __init__(self, registry, owner, target, name):
        self.registry, self.owner = registry, owner
        self.target, self.name = target, name
        self.handle = None
        self.closed = False

    def install(self, wrapper):
        self.handle = self.registry._install(self.owner, self.target, self.name, wrapper)
        return self.handle

    def close(self):
        if not self.closed:
            if self.handle is None:
                self.registry._release((id(self.target), self.name), self.owner)
            else:
                self.handle.close()
            self.closed = True


class RuntimeExtensions:
    """Startup-reserved explicit wrappers, removable in any owner order."""
    def __init__(self):
        self._methods = {}
        self._reservations = {}

    def reserve(self, owner, target, name):
        """Validate an owner's slot without reading or replacing its current base."""
        key = (id(target), name)
        owners = self._reservations.setdefault(key, set())
        if owner in owners:
            raise ValueError(f'DUPLICATE_WORLD_WRAPPER:{owner}:{name}')
        owners.add(owner)
        return _PreparedWrapper(self, owner, target, name)

    def wrap(self, owner, target, name, wrapper):
        return self.reserve(owner, target, name).install(wrapper)

    def _install(self, owner, target, name, wrapper):
        # The site was reserved at startup. Capture the actual preceding owner
        # now: another feature may have supplied the base after reservation.
        key = (id(target), name)
        if key not in self._methods:
            self._methods[key] = [target, name, name in vars(target),
                                  getattr(target, name, None), []]
        row = self._methods[key]
        row[4].append((owner, wrapper))
        self._apply(row)
        return _WrapperHandle(self, key, owner)

    def _apply(self, row):
        target, name, own, original, wrappers = row
        if not wrappers:
            if own:
                setattr(target, name, original)
            elif name in vars(target):
                delattr(target, name)
            return
        current = original
        for _, wrapper in wrappers:
            current = wrapper(current)
        setattr(target, name, current)

    def _remove(self, key, owner):
        row = self._methods[key]
        row[4][:] = [(key, wrapper) for key, wrapper in row[4] if key != owner]
        self._apply(row)
        if not row[4]:
            del self._methods[key]
        self._release(key, owner)

    def _release(self, key, owner):
        self._reservations[key].remove(owner)
        if not self._reservations[key]:
            del self._reservations[key]
