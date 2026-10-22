"""Explicit source-pinned aggregate schema reader. No runtime/write authority."""
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import threading
import uuid
import weakref

from tools.local_original_session import inventory, item_custody

need = inventory.need
_ISSUED = weakref.WeakValueDictionary()
_MODULES = {}
_MODULE_LOCK = threading.RLock()


def _source_bytes(path):
    inventory.observe.ordinary(path)
    with path.open('rb') as stream:
        raw = stream.read(1048577)
    need(0 < len(raw) <= 1048576, 'INVENTORY_AGGREGATE_SOURCE_SIZE')
    return raw


def _module_bindings(m):
    return (m.BatchStore, m.BatchStore._validate, m.BatchStore._validate_canonical,
            m.DocumentCapability, m.DocumentCapability.check, m.DocumentCapability.change,
            m.DocumentCapability.authority, m.DocumentCapability.key,
            m.encoded, m.digest, m.unique, m.MAX_BYTES, m.MAX_TRANSACTIONS, m.POLICY)


def _load_module(path, expected_sha256):
    # One exact source module/class space also preserves core._OWNERS. Loading
    # another version for the same live profile is unsupported; the factory
    # selects one version and closes the old writer before a version switch.
    key = (os.path.normcase(str(path.resolve())), expected_sha256)
    with _MODULE_LOCK:
        raw = _source_bytes(path)
        need(hashlib.sha256(raw).hexdigest() == expected_sha256,
             'INVENTORY_AGGREGATE_SOURCE_PIN')
        cached = _MODULES.get(key)
        if cached is not None:
            need(_module_bindings(cached[0]) == cached[1], 'INVENTORY_AGGREGATE_VALIDATOR_CHANGED')
            return cached[0]
        name = '_inventory_aggregate_core_' + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            # Compile the HASHED bytes themselves, never a possibly stale pyc.
            exec(compile(raw, str(path), 'exec'), module.__dict__)
            bindings = _module_bindings(module)
            need(hashlib.sha256(_source_bytes(path)).hexdigest() == expected_sha256,
                 'INVENTORY_AGGREGATE_SOURCE_PIN')
            _MODULES[key] = (module, bindings)
            return module
        except BaseException:
            sys.modules.pop(name, None)
            raise


@dataclass(frozen=True, slots=True, weakref_slot=True)
class AggregateReadCapability:
    canonical_module: object
    source_path: Path
    source_sha256: str
    capabilities: tuple
    _bindings: tuple

    @classmethod
    def load(cls, source_path, *, expected_sha256, capability_factory):
        """Load exact reviewed source, then construct validators from THAT module.

        Factory is a trusted server configuration callback, never saved/client
        data. Returned module is also the module to use for BatchStore/Provider;
        DocumentCapability classes from another import are deliberately refused.
        """
        path = Path(source_path)
        need(path.is_absolute() and type(expected_sha256) is str and
             len(expected_sha256) == 64 and
             hashlib.sha256(_source_bytes(path)).hexdigest() == expected_sha256,
             'INVENTORY_AGGREGATE_SOURCE_PIN')
        module = _load_module(path, expected_sha256)
        caps = capability_factory(module)
        need(type(caps) is tuple and
             all(type(c) is module.DocumentCapability for c in caps) and
             len({c.name for c in caps}) == len(caps),
             'INVENTORY_AGGREGATE_EXACT_CAPABILITIES')
        bindings = (_module_bindings(module),
                    tuple((c.name, c.scope, c.validate, c.validate_change,
                           c.validate_authority) for c in caps))
        value = cls(module, path, expected_sha256, caps, bindings)
        _ISSUED[id(value)] = value
        return value

    def check(self):
        need(_ISSUED.get(id(self)) is self, 'INVENTORY_AGGREGATE_SOURCE_BOOTSTRAP_REQUIRED')
        m = self.canonical_module
        need(hashlib.sha256(_source_bytes(self.source_path)).hexdigest() == self.source_sha256,
             'INVENTORY_AGGREGATE_SOURCE_PIN')
        need((_module_bindings(m),
              tuple((c.name, c.scope, c.validate, c.validate_change,
                     c.validate_authority) for c in self.capabilities)) == self._bindings,
             'INVENTORY_AGGREGATE_VALIDATOR_CHANGED')
        return m

    @property
    def max_bytes(self):
        return self.check().MAX_BYTES

    def project(self, store, document, raw):
        """Strict full aggregate validation and canonical projection only."""
        m = self.check()
        class Projection:
            _validate_canonical = m.BatchStore._validate_canonical
        view = Projection()
        view.source, view.profile = store, store.profile
        view.capabilities = {c.name: c for c in self.capabilities}
        m.BatchStore._validate(view, document, raw)
        need(type(document) is dict and type(document.get('version')) is int and
             document['version'] == 3, 'INVENTORY_AGGREGATE_EXACT_V3')
        rows = view._validate_canonical(document['canonical'])
        from tools.local_original_session import inventory_store
        known = {r['uid'] for r in inventory_store._characters(store.profile)['characters']}
        snapshot = None
        if document['canonical']['version'] == 2:
            snapshot = item_custody.decode(document['canonical'], raw, known, str(store.profile))
        return rows, known, snapshot
