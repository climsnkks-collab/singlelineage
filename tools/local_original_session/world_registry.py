"""Startup registration and explicit world extension contracts.

This module has no broker, protocol, data-file or socket dependency. Registration
validates names once. Requests only call the already registered functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from importlib import import_module
import inspect
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class FeatureRegistry:
    methods: Mapping
    realm_methods: Mapping
    frames: Mapping
    hooks: Mapping
    outgoing_opcodes: tuple
    save_boundaries: Mapping
    realm_hooks: Mapping
    hook_policy: Mapping


def _wrap_method(base, wrapper):
    # WRAPS is deliberately different from METHODS: the previous implementation
    # is an explicit argument, and its name stays the save-boundary identity.
    if inspect.iscoroutinefunction(base) or inspect.iscoroutinefunction(wrapper):
        @wraps(base)
        async def call(context, *args, **kwargs):
            value = wrapper(context, lambda *a, **k: base(context, *a, **k), *args, **kwargs)
            return await value if inspect.isawaitable(value) else value
    else:
        @wraps(base)
        def call(context, *args, **kwargs):
            return wrapper(context, lambda *a, **k: base(context, *a, **k), *args, **kwargs)
    return call


def build_registry(modules):
    """Build immutable tables from module objects or local module names.

    METHODS never overrides another METHODS entry. WRAPS is the only explicit
    composition mechanism for a named method. Hook order is declaration order;
    FRAMES can specify FRAME_PRIORITY to retain the existing protocol precedence.
    """
    loaded = tuple(import_module('tools.local_original_session.' + module)
                   if isinstance(module, str) else module for module in modules)
    methods, realm_methods, owners, realm_owners = {}, {}, {}, {}
    hooks, realm_hooks, hook_policy, frames, boundaries = {}, {}, {}, {}, {}
    outgoing, wrappers = [], []
    for order, module in enumerate(loaded):
        owner = module.__name__
        for attr, target, sources in (('METHODS', methods, owners),
                                      ('REALM_METHODS', realm_methods, realm_owners)):
            for function in getattr(module, attr, ()):
                name = function.__name__
                if name in target:
                    raise ValueError(f'DUPLICATE_{attr}: {name}: {sources[name]} / {owner}')
                target[name], sources[name] = function, owner
        for name, wrapper in getattr(module, 'WRAPS', {}).items():
            wrappers.append((owner, name, wrapper))
        priority = getattr(module, 'FRAME_PRIORITY', 20)
        for opcode, names in getattr(module, 'FRAMES', {}).items():
            frames.setdefault(opcode, []).append((priority, order, tuple(names)))
        noncritical = frozenset(getattr(module, 'NONCRITICAL_HOOKS', ()))
        hook_priorities = getattr(module, 'HOOK_PRIORITY', {})
        for hook, names in getattr(module, 'HOOKS', {}).items():
            hooks.setdefault(hook, []).append((hook_priorities.get(hook, 20), order, tuple(names)))
            for name in names:
                hook_policy[(hook, name)] = (owner, hook in noncritical)
        for hook, functions in getattr(module, 'REALM_HOOKS', {}).items():
            realm_hooks.setdefault(hook, []).extend(functions)
        for name, boundary in getattr(module, 'SAVE_BOUNDARIES', {}).items():
            if name in boundaries:
                raise ValueError(f'DUPLICATE_SAVE_BOUNDARY: {name}')
            boundaries[name] = boundary
        outgoing.extend(getattr(module, 'OUTGOING_OPCODES', ()))
    for owner, name, wrapper in wrappers:
        if name not in methods:
            raise ValueError(f'UNKNOWN_WRAP_TARGET: {owner}: {name}')
        methods[name] = _wrap_method(methods[name], wrapper)
    hooks = {hook: tuple(name for _, _, names in sorted(entries) for name in names)
             for hook, entries in hooks.items()}
    for hook, names in hooks.items():
        for name in names:
            if name not in methods:
                raise ValueError(f'UNKNOWN_HOOK_METHOD: {hook}: {name}')
    ordered_frames = {}
    for opcode, entries in frames.items():
        names = tuple(name for _, _, group in sorted(entries) for name in group)
        for name in names:
            if name not in methods:
                raise ValueError(f'UNKNOWN_FRAME_METHOD: {opcode}: {name}')
        ordered_frames[opcode] = names
    for name in boundaries:
        if name not in methods:
            raise ValueError(f'UNKNOWN_SAVE_BOUNDARY: {name}')
    return FeatureRegistry(MappingProxyType(methods), MappingProxyType(realm_methods),
        MappingProxyType(ordered_frames),
        MappingProxyType({key: tuple(value) for key, value in hooks.items()}),
        tuple(dict.fromkeys(outgoing)), MappingProxyType(boundaries),
        MappingProxyType({key: tuple(value) for key, value in realm_hooks.items()}),
        MappingProxyType(hook_policy))


def registry_for(context):
    registry = getattr(context, '_world_registry', None)
    if registry is None:
        from tools.local_original_session.world_handlers import feature_registry
        registry = feature_registry()
    return registry


def has_hooks(name, context):
    return bool(registry_for(context).hooks.get(name, ()))


def _failure(registry, name, method, context, error):
    owner, noncritical = registry.hook_policy.get((name, method), ('unknown', False))
    if not noncritical:
        raise error
    errors = getattr(context, '_world_hook_errors', [])
    context._world_hook_errors = (errors + [dict(feature=owner, hook=name,
        method=method, error=type(error).__name__)])[-16:]


async def _results(name, context, args, kwargs):
    registry = registry_for(context)
    for method in registry.hooks.get(name, ()):
        try:
            value = getattr(context, method)(*args, **kwargs)
            yield await value if inspect.isawaitable(value) else value
        except Exception as error:
            _failure(registry, name, method, context, error)


def _sync_results(name, context, args, kwargs):
    registry = registry_for(context)
    for method in registry.hooks.get(name, ()):
        try:
            yield getattr(context, method)(*args, **kwargs)
        except Exception as error:
            _failure(registry, name, method, context, error)


async def run_hooks(name, context, *args, **kwargs):
    async for _ in _results(name, context, args, kwargs):
        pass


def run_sync_hooks(name, context, *args, **kwargs):
    for _ in _sync_results(name, context, args, kwargs):
        pass


async def chain_hooks(name, context, *args, **kwargs):
    async for value in _results(name, context, args, kwargs):
        if value:
            return True
    return False


def chain_sync_hooks(name, context, *args, **kwargs):
    return any(_sync_results(name, context, args, kwargs))


async def collect_hooks(name, context, *args, **kwargs):
    return tuple([value async for value in _results(name, context, args, kwargs)])


def collect_sync_hooks(name, context, *args, **kwargs):
    return tuple(_sync_results(name, context, args, kwargs))


async def fold_hooks(name, context, value, *args, **kwargs):
    registry = registry_for(context)
    for method in registry.hooks.get(name, ()):
        try:
            result = getattr(context, method)(value, *args, **kwargs)
            value = await result if inspect.isawaitable(result) else result
        except Exception as error:
            _failure(registry, name, method, context, error)
    return value


def fold_sync_hooks(name, context, value, *args, **kwargs):
    registry = registry_for(context)
    for method in registry.hooks.get(name, ()):
        try:
            value = getattr(context, method)(value, *args, **kwargs)
        except Exception as error:
            _failure(registry, name, method, context, error)
    return value


def fold_realm_hooks(name, realm, value, *args, **kwargs):
    context = getattr(realm, '_world_context', None)
    if context is None or context.world is None:
        return value
    for function in registry_for(realm).realm_hooks.get(name, ()):
        value = function(realm, value, *args, **kwargs)
    return value


def prepare_attack(context, *args):
    """All providers must allow; retain the ammunition owner's result.

    A provider returning None refuses. Only one provider owns ammunition costs;
    later policy-only providers must not overwrite its arrow/cost. The bridge
    installs no callback at all when there are no providers, retaining melee.
    """
    from dataclasses import replace
    prepared = None
    for result in _sync_results('prepare_attack', context, args, {}):
        if result is None or not result.allowed:
            return None
        if prepared is None:
            prepared = result
        else:
            prepared = replace(prepared,
                arrow=prepared.arrow if prepared.arrow is not None else result.arrow,
                cost=prepared.cost if prepared.cost is not None else result.cost)
    return prepared
