"""Persistent owner for the frozen CP69 client. No auto input or game timer."""
from __future__ import annotations
import argparse
import asyncio
import contextlib
import ctypes as C
from ctypes import wintypes as W
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import struct
import sys
import threading
import time
import uuid
from types import MethodType

_MANUAL_REJECTION_SOURCE_SHA = '48848fd9a0ce7c5faed7652a55523fd086222cea0269b5b74bc9885f03ab9f3a'
_INVENTORY_OBSERVER_SOURCE_SHA = '9b920825f04e11759fa74e96ace73d0c50e047005458ec232197cc26ec8c9df6'
_INVENTORY_INCOMPLETE_READS = frozenset(('RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE',
    'RECHECKED_SHARED_COUNT_FINAL_READBACK', 'RECHECKED_SHARED_COUNT_BOTH'))

ROOT = Path(__file__).resolve().parents[2]
CP69 = '656a64e7c686144615f473902590e23ce0024b907e96ad905f42e84084e8da9d'
CANDIDATE = ROOT / 'work/local_native_login_state5_ack_candidate/native-login.candidate.bin'
BRIDGES = {
    'own-login-bridge-cp49.dll': '3a3ba64e7ce9127f7e47f442cd355ab7082aa8a4fa99edb94d97fe10b2b3333b',
    'own-creation-entry001.dll': 'a69237821e4fd158df20ba23ab35bd58b2bb3676773045a4067c6167b179721f',
}
PRODUCTS = {
    'baseline': dict(bridges=dict(BRIDGES), image=None, resource_directory=None,
                     image_sha256=CP69, candidate=CANDIDATE),
    'guard-diagnostic': dict(
        bridges={**BRIDGES, 'own-login-bridge-cp49.dll':
                 '5cd62e7f020943f73c2a8e8ea30dee21de60865c89abaf020b5ca9d8859fed78'},
        image=ROOT / 'work/local_original_session/runtime-guard-diagnostic/LC.local.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256=CP69, candidate=CANDIDATE),
    'sibling-guard-diagnostic': dict(
        bridges={'own-login-bridge-dg49.dll':
                 '2af9a217a78eb061b95aacd725dfba55d806ae878878d3a1ab5e5a6e6701d0d9',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin'),
    'sibling-connect-fix': dict(
        bridges={'own-login-bridge-dg49.dll':
                 '39b5647702ae14b53826bc476668b0b6ed9d75ae9d241e29ed3a5f5be7903013',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin'),
    'sibling-memory-query': dict(
        bridges={'own-login-bridge-dg49.dll':
                 'bdb1d851d618cd0c821e60b0ed6aa8b63d1b60aa16370bd1a373ba03eb90c167',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin'),
    'sibling-source-retry': dict(
        bridges={'own-login-bridge-dg49.dll':
                 '96683321ec773589728675c5ae8d4762653cd487f1de231965b6de1c87da5be9',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin'),
    'sibling-verified-duplicate': dict(
        bridges={'own-login-bridge-dg49.dll':
                 '46cc8a822486bb92785bd44cf492c19a47f7769b415d655e3131fb5d82cf9d67',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin'),
    'sibling-duplicate-diagnostics': dict(
        bridges={'own-login-bridge-dg49.dll':
                 '82adeaa1357dbaf5231b2e83a17fe2baf82a3aba04ca307a1df7e88ceeaa3f0b',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin'),
    'sibling-verified-socket-duplicate': dict(
        bridges={'own-login-bridge-dg49.dll':
                 '1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin'),
    'sibling-internal-command': dict(
        bridges={'own-login-bridge-dg49.dll':
                 '7eac97c31a7a27604ccc73139cccc45b69e0e2471128d6d451b84287f67adc91',
                 'own-creation-entry001.dll': BRIDGES['own-creation-entry001.dll']},
        image=ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe',
        resource_directory=ROOT / 'work/standalone_boot/current-unmodified-clone',
        image_sha256='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684',
        candidate=ROOT / 'work/local_original_session/native-sibling/native-login.candidate.bin',
        background_display_guard=True, internal_only=True),
}

PRODUCTS['sibling-internal-quit'] = {
    **PRODUCTS['sibling-internal-command'],
    'bridges': {**PRODUCTS['sibling-internal-command']['bridges'],
                'own-login-bridge-dg49.dll':
                '0f4fdabc1d9609e53205930aa163b0635fac9c4815c393a86c7ccb0cf5771425'},
}
PRODUCTS['sibling-internal-lifecycle'] = {
    **PRODUCTS['sibling-internal-quit'],
    'bridges': {**PRODUCTS['sibling-internal-quit']['bridges'],
                'own-login-bridge-dg49.dll':
                'd975989c0787133997149c6fa37a79d2eee7d490b0a88c7915828a346546f2b8'},
}
PRODUCTS['sibling-internal-quit-source-retry'] = {
    **PRODUCTS['sibling-internal-lifecycle'],
    'bridges': {**PRODUCTS['sibling-internal-lifecycle']['bridges'],
                'own-login-bridge-dg49.dll':
                '7cd55da18a7d31303164a0b4cdea2f3e64ee21fe360c97ab483ac971b6bd8485'},
}
PRODUCTS['sibling-internal-quit-source-retry-spawn'] = {
    **PRODUCTS['sibling-internal-quit-source-retry'],
    'world_profile': 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73',
}
PRODUCTS['sibling-manual-play-spawn'] = {
    **PRODUCTS['sibling-verified-socket-duplicate'],
    'world_profile': 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73',
}
PRODUCTS['sibling-manual-move-continuous-spawn'] = {
    **PRODUCTS['sibling-manual-play-spawn'],
    'bridges': {**PRODUCTS['sibling-manual-play-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                '660f98fa25323baeffd1bf9389f78bb9010816607c4e7e5ae48c3446f282dea4'},
    'manual_only': True,
    'continuous_manual_move': True,
}
PRODUCTS['sibling-background-move-continuous-spawn'] = {
    **PRODUCTS['sibling-manual-move-continuous-spawn'],
    'background_display_guard': True,
    'require_background': True,
}
PRODUCTS['sibling-manual-move-attack-target-spawn'] = {
    **PRODUCTS['sibling-manual-move-continuous-spawn'],
    'bridges': {**PRODUCTS['sibling-manual-move-continuous-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                'c55d601df697dfad3b1ebb0c80b091930caa1b9fdd00e98cd11b0ba7d79353c7'},
    'continuous_manual_attack': True,
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/manual-attack-target/'
                              'postpredicate-build/own-login-bridge-dg49.dll',
    'runtime_status': 'NOT_FOR_INSTALL_RUNTIME_UNVERIFIED',
    'source_build_only': True,
}
PRODUCTS['sibling-background-move-attack-target-spawn'] = {
    **PRODUCTS['sibling-manual-move-attack-target-spawn'],
    'bridges': {**PRODUCTS['sibling-manual-move-attack-target-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                '2c0bcd6e53eb5d86e4ef87115f899b976a86d5e820912d63ab3de29e1344073d'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/manual-attack-to-move/'
                              'own-login-bridge-dg49.dll',
    'background_display_guard': True,
    'require_background': True,
    'manual_attack_move_replacement': True,
    'source_build_only': False,
    'runtime_status': 'EXPLICIT_BACKGROUND_TEST_CANDIDATE',
    'runtime_verdict': 'EXPLICIT_BACKGROUND_TEST_CANDIDATE',
}
PRODUCTS['sibling-background-source-quit-spawn'] = {
    **PRODUCTS['sibling-background-move-attack-target-spawn'],
    'bridges': {**PRODUCTS['sibling-background-move-attack-target-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                'd5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/manual-source-quit-codegate-bounds/'
                              'own-login-bridge-dg49.dll',
    'manual_source_quit': True,
    'require_source_quit': True,
}
PRODUCTS['sibling-background-use-item-source-quit-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'bridges': {**PRODUCTS['sibling-background-source-quit-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                'fd82765c07762ba4c37127bb4f6584f853cebdc4d7f5db31af65fa7f6471ebab'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/source-use-ui-child-role-split/'
                              'own-login-bridge-dg49.dll',
    'manual_use_item': True,
}
PRODUCTS['sibling-background-source-restart-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'bridges': {**PRODUCTS['sibling-background-source-quit-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                'f3496b5075f069316b4a65db0242cc11f311bc5a0cc5920cceb3116223460902'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/manual-source-restart-code-gate/'
                              'own-login-bridge-dg49.dll',
    'manual_source_restart': True,
    'require_source_quit': False,
}
PRODUCTS['sibling-background-source-reselect-spawn'] = {
    **PRODUCTS['sibling-background-source-restart-spawn'],
    'bridges': {**PRODUCTS['sibling-background-source-restart-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                'bd24d868ad95394a9ed48ba1368afce805836ee58e5cb83435295e47746af1a9'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/manual-source-reselect/'
                              'own-login-bridge-dg49.dll',
    'manual_source_reselect': True,
}
PRODUCTS['sibling-background-inventory-update-source-quit-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'manual_inventory_update': True,
}
PRODUCTS['sibling-internal-lifecycle-integrity-spawn'] = {
    **PRODUCTS['sibling-internal-quit-source-retry-spawn'],
    'bridges': {**PRODUCTS['sibling-internal-quit-source-retry-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                '03f774938515c59c106998cbe7982d8d7ad077ec8c90f30b654fe0f14065647a'},
    'require_lifecycle_health': True,
}
PRODUCTS['sibling-internal-lifecycle-details-spawn'] = {
    **PRODUCTS['sibling-internal-lifecycle-integrity-spawn'],
    'bridges': {**PRODUCTS['sibling-internal-lifecycle-integrity-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                '906953e195688fae8f88c8a2bfcc28b21a26ed95b63dd32c8f9076894d884a5b'},
}
PRODUCTS['sibling-internal-lifecycle-pre-self-spawn'] = {
    **PRODUCTS['sibling-internal-lifecycle-details-spawn'],
    'bridges': {**PRODUCTS['sibling-internal-lifecycle-details-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                'be94dfadedaa689a12bf8ac3002aca60977e158fb51e733332c28117129f0029'},
}


PRODUCTS['sibling-internal-ipc-immutable-spawn'] = {
    **PRODUCTS['sibling-internal-lifecycle-pre-self-spawn'],
    'bridges': {**PRODUCTS['sibling-internal-lifecycle-pre-self-spawn']['bridges'],
                'own-login-bridge-dg49.dll': 'b4796093ad3a7127731781a9902808a4484428635ce2f6814cb6ff7272c073db'},
    'command_result_mode': 'immutable-sequence-v1',
}

PRODUCTS['sibling-internal-virtual-protect-callers-spawn'] = {
    **PRODUCTS['sibling-internal-lifecycle-pre-self-spawn'],
    'bridges': {**PRODUCTS['sibling-internal-lifecycle-pre-self-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                'cab82813a43e0853d05aa38048d8d17b3129655a604540353cf8187d774d02d1'},
}


def need(value, code):
    if not value:
        raise ValueError(code)


def safe_error_code(error):
    if (isinstance(error, ValueError) and len(error.args) == 1
            and type(error.args[0]) is str and re.fullmatch('[A-Z0-9_]{1,96}', error.args[0])):
        return error.args[0]
    return None


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1048576), b''):
            h.update(data)
    return h.hexdigest()


def product_configuration(product, image):
    need(product in PRODUCTS, 'KNOWN_PRODUCT_REQUIRED')
    spec = PRODUCTS[product]
    need(all(type(pin) is str and len(pin) == 64 for pin in spec['bridges'].values()),
         'KNOWN_PRODUCT_BUILD_PENDING')
    need(type(spec['image_sha256']) is str and len(spec['image_sha256']) == 64
         and isinstance(spec['candidate'], Path), 'KNOWN_PRODUCT_BUILD_PENDING')
    need(spec['image'] is None or image == spec['image'], 'KNOWN_PRODUCT_IMAGE_REQUIRED')
    return spec['bridges'], spec['resource_directory'] or image.parent


def preflight(image, product='baseline'):
    """Read only; never installs bytes into the original/fixed slot."""
    image = Path(image).absolute()
    bridges, resource_directory = product_configuration(product, image)
    image_sha = PRODUCTS[product]['image_sha256']
    need(image.resolve(strict=True) == image, 'CANONICAL_IMAGE_REQUIRED')
    for part in (image, *image.parents):
        need(not part.is_symlink() and not getattr(part.stat(), 'st_file_attributes', 0) & 0x400,
             'IMAGE_REPARSE_REFUSED')
    need(image.suffix.casefold() == '.exe' and digest(image) == image_sha, 'PREPARED_PRODUCT_EXE_REQUIRED')
    files = {image: image_sha}
    need(resource_directory.is_dir() and resource_directory.resolve(strict=True) == resource_directory,
         'PRODUCT_RESOURCE_DIRECTORY_REQUIRED')
    for name, expected in bridges.items():
        path = image.parent / name
        need(path.resolve(strict=True) == path and not path.is_symlink()
             and not getattr(path.stat(), 'st_file_attributes', 0) & 0x400
             and digest(path) == expected, 'CP69_BRIDGE_REQUIRED:' + name)
        files[path] = expected
    return files


def verified_nt_image(actual, expected):
    # Both strings must come from current native calls on retained handles.
    need(isinstance(actual, str) and actual.startswith('\\Device\\')
         and isinstance(expected, str) and expected.startswith('\\Device\\')
         and actual.casefold() == expected.casefold(), 'CURRENT_NATIVE_IMAGE_MISMATCH')


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def native_module(image, resource_directory=None):
    """Separate globals; leave every frozen module/file untouched."""
    core = _module('_local_session_core', ROOT / 'tools/clone_observer/core.py')
    previous = sys.modules.get('core')
    try:
        sys.modules['core'] = core
        value = _module('_local_session_native', ROOT / 'tools/clone_observer/windows.py')
    finally:
        if previous is None:
            sys.modules.pop('core', None)
        else:
            sys.modules['core'] = previous
    value.EXE, value.CLONE = str(image), str(resource_directory or image.parent)
    return value


class GenuineConversations:
    """Existing authenticated stored pack; four transient VERSION emissions.

    Uses the same adapter/PreservedConversation as local_ready_entry_prepared.
    No official login/SDK process is attached or started by this resource API.
    """
    def __init__(self):
        names = ('native', 'sampler', 'source', 'producer', 'source_contract',
                 'provider', 'constants', 'session_adapter')
        previous = {name: sys.modules.get(name) for name in names}
        paths = sys.path[:]
        self.resource = None
        self.slots = {}
        self.used = set()
        self.closed = False
        template = None
        try:
            for name in names:
                sys.modules.pop(name, None)
            folder = ROOT / 'tools/preserved_pack_bootstrap'
            sys.path.insert(0, str(folder))
            self.parent = _module('_local_session_preserved_broker', folder / 'broker.py')
            self.resource = self.parent.adapter.load_preserved_session()
            generation = self.parent.adapter.Session(self.resource.original)
            template = generation.version_frame()
            need(type(template) is bytearray and len(template) == 76
                 and int.from_bytes(template[2:4], 'little') == 0x4e35,
                 'GENUINE_VERSION_REQUIRED')
            self.slots = {n: bytearray(template) for n in (1, 2, 3, 4)}
            self.plan = self.parent.load_plan()
            # These are the resource loader's retained read-share handles. Its
            # close() owns their release; never attach to its old metadata PID.
            self.original = self.resource.original
            self.provider = self.original._provider
            self.pins = self.original._pins
            self.check()
        except BaseException:
            self.close()
            raise
        finally:
            if template is not None:
                template[:] = bytes(len(template))
            sys.path[:] = paths
            for name, value in previous.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value

    def check(self):
        need(not self.closed and self.resource is not None and not self.resource.closed
             and self.resource.original is self.original and not self.original.closed
             and self.original._verified is True and self.original._provider is self.provider
             and self.original._pins is self.pins, 'GENUINE_RESOURCE_LIFETIME_REQUIRED')

    def conversation(self, connection_id, sink):
        self.check()
        need(connection_id in self.slots and connection_id not in self.used,
             'GENUINE_VERSION_CONNECTION_REQUIRED')
        from tools.local_entry_server.server import Session, MetadataLog
        outer = self
        class Resource:
            def version_frame(self):
                outer.check()
                need(connection_id not in outer.used, 'VERSION_ALREADY_EMITTED')
                outer.used.add(connection_id)
                return outer.slots[connection_id]
        return self.parent.PreservedConversation(self.plan,
            Session(connection_id, 'reviewed_counts'), MetadataLog(sink=sink), Resource())

    def release(self, connection_id):
        value = self.slots.get(connection_id)
        if value is not None:
            value[:] = bytes(len(value))
        self.used.add(connection_id)

    def close(self):
        if self.closed:
            return
        for value in self.slots.values():
            value[:] = bytes(len(value))
        try:
            if self.resource is not None:
                self.resource.close()
        finally:
            self.closed = True


_desktop_module = _module('_local_session_desktop', ROOT / 'tools/local_original_session/desktop.py')
PrivateDesktop, hidden_desktop_launch = _desktop_module.PrivateDesktop, _desktop_module.hidden_desktop_launch


def observed_member_parent(native, root, member, entry_type):
    """One bounded Toolhelp observation; parent PID is never owner authority."""
    public = dict(pid=int(member.pid), birth=member.identity.get('birth'),
                  observed_parent_pid=None, status='UNKNOWN')
    try:
        handle, pid = member.process, member.pid

        def current():
            need(root.members.get(pid) is member and member.process == handle
                 and native.k.GetProcessId(handle) == pid
                 and native.k.WaitForSingleObject(handle, 0) == 258, 'PARENT_CURRENT_MEMBER_REQUIRED')
            inside = W.BOOL()
            need(native.k.IsProcessInJob(handle, root.job, C.byref(inside)) and inside.value,
                 'PARENT_CURRENT_JOB_REQUIRED')
            identity = native.identity(handle, pid, member.identity.get('parent_pid'), include_token=False)
            need(all(identity.get(key) == member.identity.get(key) for key in ('pid', 'birth', 'image'))
                 and identity.get('birth') is not None and native.k.GetProcessId(handle) == pid
                 and native.k.WaitForSingleObject(handle, 0) == 258, 'PARENT_CURRENT_IDENTITY_REQUIRED')

        current()
        snapshot = native.k.CreateToolhelp32Snapshot(2, 0)
        need(snapshot not in (None, 0, C.c_void_p(-1).value), 'PARENT_SNAPSHOT_UNKNOWN')
        parent, found, count = None, 0, 0
        try:
            entry = entry_type(); entry.size = C.sizeof(entry)
            ok = native.k.Process32FirstW(snapshot, C.byref(entry))
            while ok:
                need(count < 4096, 'PARENT_SNAPSHOT_BOUND')
                count += 1
                if entry.pid == pid:
                    parent, found = int(entry.parent), found + 1
                ok = native.k.Process32NextW(snapshot, C.byref(entry))
            need(C.get_last_error() == 18 and found == 1, 'PARENT_SNAPSHOT_INCOMPLETE')
        finally:
            need(native.k.CloseHandle(snapshot), 'PARENT_SNAPSHOT_CLOSE_UNKNOWN')
        current()
        public.update(observed_parent_pid=parent, status='OBSERVED')
    except Exception:
        pass  # Fast exit, missing row or changed identity stays UNKNOWN.
    return public


def add_process_tree_status(monitor, owner):
    publish = monitor.publish
    def publish_owned(public):
        return publish(dict(public, process_tree=owner.process_tree()))
    monitor.publish = publish_owned


class NativeOwner:
    """Retain CreateProcess handles and a kill-on-close Job for this session only."""
    def __init__(self, image, context_directory, source_guard=lambda: None, product='baseline', *,
                 internal=False, background=False):
        need(type(background) is bool, 'BACKGROUND_BOOL_REQUIRED')
        self.image = Path(image).absolute()
        self.product = product
        self.require_lifecycle_health = PRODUCTS.get(product, {}).get('require_lifecycle_health') is True
        self.command_result_mode = PRODUCTS.get(product, {}).get('command_result_mode')
        self.image_sha = PRODUCTS[product]['image_sha256'] if product in PRODUCTS else None
        _, self.resource_directory = product_configuration(product, self.image)
        need(not PRODUCTS[product].get('internal_only') or internal,
             'INTERNAL_CONTROL_MODE_REQUIRED')
        need(not PRODUCTS[product].get('manual_only') or not internal,
             'MANUAL_CONTROL_MODE_REQUIRED')
        need(not PRODUCTS[product].get('require_background') or background,
             'BACKGROUND_DISPLAY_REQUIRED')
        need(not background or PRODUCTS[product].get('background_display_guard') is True,
             'BACKGROUND_DISPLAY_GUARD_UNVERIFIED')
        self.directory = Path(context_directory).absolute()
        boundary = ROOT / 'work/local_native_login_key_invoke_boundary/runs'
        import re
        need(self.directory.parent == boundary and re.fullmatch('[a-z0-9-]{1,32}', self.directory.name),
             'CP49_NATIVE_BOUNDARY_DIRECTORY_REQUIRED')
        self.files = preflight(self.image, product)
        self.source_guard = source_guard
        module = native_module(self.image, self.resource_directory)
        self._filetime_type = module.FT
        self._entry_type = module.ENTRY
        expected_image = str(self.image)
        self.private_desktop = None
        self.desktop_status = dict(status='NOT_CREATED')
        self.internal = internal
        self.background = background
        self._parent_observations = {}
        if internal:
            need(PRODUCTS[product].get('background_display_guard') is True,
                 'INTERNAL_DISPLAY_GUARD_UNVERIFIED')
        outer = self

        class CurrentIdentity(module.Native):
            image_nt = None
            nt_fallback_count = 0

            def capture_member(native, child, pid):
                try:
                    return super().capture_member(child, pid)
                finally:
                    outer._observe_parent(child, pid, module.ENTRY)

            def create_suspended(native):
                parent = super().create_suspended
                if outer.private_desktop is None:
                    need(not (outer.internal or outer.background), 'PRIVATE_DESKTOP_PREPARE_REQUIRED')
                    return parent()
                return hidden_desktop_launch(native, parent, module.STARTUP, outer.private_desktop)

            def windows(native, child):
                if outer.private_desktop is None:
                    need(not (outer.internal or outer.background), 'PRIVATE_DESKTOP_PREPARE_REQUIRED')
                    return super().windows(child)
                original = native.u.EnumWindows
                native.u.EnumWindows = outer.private_desktop.enum
                try:
                    return super().windows(child)
                finally:
                    native.u.EnumWindows = original

            def identity(native, handle, pid, parent_pid=None, include_token=True):
                need(native.k.GetProcessId(handle) == pid, 'RETAINED_HANDLE_PID_MISMATCH')
                try:
                    return super().identity(handle, pid, parent_pid, include_token)
                except ValueError as error:
                    if error.args != ('native_image_required',):
                        raise
                # CP69 may deny flags=0 after unpacking. Read flags=1 on the SAME
                # retained handle, then compare to the still pinned file handle.
                need(native.image_nt is not None, 'PINNED_NT_IMAGE_REQUIRED')
                name = C.create_unicode_buffer(32768)
                size = W.DWORD(len(name))
                need(native.k.QueryFullProcessImageNameW(handle, 1, name, C.byref(size)),
                     'CURRENT_NATIVE_NT_IMAGE_UNKNOWN')
                verified_nt_image(name.value, native.image_nt)
                times = [module.FT() for _ in range(4)]
                need(native.k.GetProcessTimes(handle, *(C.byref(t) for t in times)),
                     'CURRENT_NATIVE_BIRTH_UNKNOWN')
                need(native.k.WaitForSingleObject(handle, 0) == 258, 'CURRENT_NATIVE_PROCESS_EXITED')
                need(native.k.GetProcessId(handle) == pid, 'RETAINED_HANDLE_PID_MISMATCH')
                native.nt_fallback_count += 1
                return dict(pid=pid, birth=str(times[0].high << 32 | times[0].low),
                            image=expected_image, parent_pid=parent_pid,
                            **(native.token(handle) if include_token else {}))

        self.native = CurrentIdentity('current-resource-analysis')
        self.native.k.GetProcessId.argtypes = (W.HANDLE,)
        self.native.k.GetProcessId.restype = W.DWORD
        self.child = None
        self.owner_handle = None
        self.owner_job = None
        self.retained_owner = self
        self.closed = False
        self.cleanup = None
        self.guard_failure = None
        self._cleanup_requested = False
        self.file_pins = ()
        self.native.u.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        self.native.u.PostMessageW.restype = W.BOOL
        self.native.k.GetFinalPathNameByHandleW.argtypes = (W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD)
        self.native.k.GetFinalPathNameByHandleW.restype = W.DWORD

    @staticmethod
    def ordinary(row):
        need(row.get('elevated') is False and type(row.get('integrity_rid')) is int
             and row['integrity_rid'] <= 8192, 'ORDINARY_TOKEN_REQUIRED')

    def verify_sources_full(self):
        self.source_guard()
        for path, expected in self.files.items():
            need(digest(path) == expected, 'PINNED_PRODUCT_CHANGED')

    def _file_identity(self, handle):
        data = C.create_string_buffer(52)
        need(self.native.k.GetFileInformationByHandle(handle, data), 'PINNED_FILE_HANDLE_UNKNOWN')
        # Last access time may change through reads; file identity/content
        # boundaries are volume/FileID, size, write time, type and link count.
        return bytes(data.raw[:12] + data.raw[20:])

    def verify_sources(self):
        """Constant-size handle checks; never hash 39 MB in a packet callback."""
        self.source_guard()
        need(not self.closed and tuple(self.native.handles) == tuple(h for h, _ in self.file_pins)
             and bool(self.file_pins), 'RETAINED_PRODUCT_PINS_REQUIRED')
        for handle, identity in self.file_pins:
            need(self._file_identity(handle) == identity, 'RETAINED_PRODUCT_FILE_CHANGED')

    def prepare(self):
        self.ordinary(self.native.controller())
        self.verify_sources_full()
        source = self.native.source()
        need(source['sha256'] == self.image_sha and source['path'] == str(self.image), 'CURRENT_PRODUCT_SOURCE_REQUIRED')
        # source()'s first retained file handle pins the executable read/share.
        name = C.create_unicode_buffer(32768)
        size = self.native.k.GetFinalPathNameByHandleW(self.native.handles[0], name, len(name), 2)
        need(0 < size < len(name), 'PINNED_NATIVE_FILE_PATH_UNKNOWN')
        self.native.image_nt = name.value
        self.native.pin_evidence(list(self.files))
        self.file_pins = tuple((h, self._file_identity(h)) for h in self.native.handles)
        self.verify_sources_full()  # Recheck bytes after all deny-write pins exist.
        if self.internal or self.background:
            self.private_desktop = PrivateDesktop(self.native)
        # Environment is inherited only during this synchronous CreateProcess;
        # there is no await or helper spawn while the temporary value is set.
        environment = dict(OWN_KEY_INVOKE_BOUNDARY_DIR=str(self.directory))
        if self.internal:
            environment.update(OWN_INTERNAL_COMMAND_MODE='1', OWN_INTERNAL_COMMAND_DESKTOP=self.private_desktop.name)
        elif self.background:
            environment.update(OWN_INTERNAL_COMMAND_MODE=None, OWN_INTERNAL_COMMAND_DESKTOP=None)
        previous = {key: os.environ.get(key) for key in environment}
        for key, value in environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            self.child = self.native.create_suspended()
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.owner_handle = self.child.process
        if self.private_desktop is not None:
            self.check_created_desktop()
        self.ordinary(self.child.identity)
        need(self.child.identity['image'] == str(self.image), 'EXACT_CREATED_IMAGE_REQUIRED')
        self.native.attach_single_process_job(self.child)
        self.owner_job = self.child.job
        self._observe_parent(self.child, self.child.pid, module_entry_type=self._entry_type)
        self.directory.mkdir(parents=True, exist_ok=False)
        context = dict(schema='own-key-invoke-primary-v1', pid=int(self.child.pid),
                       birth=int(self.child.identity['birth']), candidate_sha256=self.image_sha)
        with (self.directory / 'context.json').open('x', encoding='utf-8') as stream:
            json.dump(context, stream, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        return context

    def validate(self, member):
        need(self.child is not None and self.child.members.get(member.pid) is member,
             'RETAINED_MEMBER_REQUIRED')
        if not self.native.retained_alive(member):
            return False
        need(self.native.k.GetProcessId(member.process) == member.pid, 'RETAINED_HANDLE_PID_MISMATCH')
        need(member.identity['image'] == str(self.image), 'RETAINED_IMAGE_REQUIRED')
        self.ordinary(self.native.token(member.process))
        inside = W.BOOL()
        need(self.native.k.IsProcessInJob(member.process, self.owner_job, C.byref(inside)) and inside.value,
             'RETAINED_JOB_MEMBERSHIP_REQUIRED')
        return True

    def key_guard(self, peer=None):
        return self.child is not None and self.validate(self.child)

    def exit_proof(self):
        """Current signaled-process proof on existing handles, never a PID attach.

        Private owner/handle/Job bindings are for the broker only, never JSON.
        This proves an OS exit; only a separately verified Quit/drain may use it.
        """
        try:
            child, handle, job = self.child, self.owner_handle, self.owner_job
            need(not self.closed and self._cleanup_requested is False and child is not None
                 and handle and job and handle == child.process and job == child.job
                 and child.members.get(child.pid) is child, 'EXIT_RETAINED_CREATION_BINDING_REQUIRED')
            self.verify_sources()
            kernel = self.native.k
            need(kernel.WaitForSingleObject(handle, 0) == 0, 'EXIT_NOT_CURRENTLY_SIGNALED')
            need(kernel.GetProcessId(handle) == child.pid, 'EXIT_CURRENT_PID_MISMATCH')
            times = [self._filetime_type() for _ in range(4)]
            need(kernel.GetProcessTimes(handle, *(C.byref(t) for t in times)), 'EXIT_CURRENT_TIMES_UNKNOWN')
            need(str(times[0].high << 32 | times[0].low) == child.identity['birth'],
                 'EXIT_CURRENT_BIRTH_MISMATCH')
            image, length = C.create_unicode_buffer(32768), W.DWORD(32768)
            if kernel.QueryFullProcessImageNameW(handle, 0, image, C.byref(length)):
                need(image.value.casefold() == str(self.image).casefold(), 'EXIT_CURRENT_IMAGE_MISMATCH')
            else:
                length.value = len(image)
                need(kernel.QueryFullProcessImageNameW(handle, 1, image, C.byref(length)),
                     'EXIT_CURRENT_IMAGE_UNKNOWN')
                expected = C.create_unicode_buffer(32768)
                count = kernel.GetFinalPathNameByHandleW(self.native.handles[0], expected, len(expected), 2)
                need(0 < count < len(expected), 'EXIT_PINNED_IMAGE_UNKNOWN')
                verified_nt_image(image.value, expected.value)
            membership = W.BOOL()
            need(kernel.IsProcessInJob(handle, job, C.byref(membership)) and membership.value,
                 'EXIT_CURRENT_JOB_MEMBERSHIP_UNKNOWN')
            need(self.native.active_job_count(child) == 0, 'EXIT_OWNED_JOB_NOT_EMPTY')
            code = W.DWORD()
            need(kernel.GetExitCodeProcess(handle, C.byref(code)), 'EXIT_CURRENT_CODE_UNKNOWN')
            self.verify_sources()
            need(self.child is child and self.owner_handle is handle and self.owner_job is job
                 and not self.closed and self._cleanup_requested is False
                 and kernel.GetProcessId(handle) == child.pid
                 and kernel.WaitForSingleObject(handle, 0) == 0
                 and self.native.active_job_count(child) == 0, 'EXIT_BINDING_CHANGED')
            return dict(status='VERIFIED', owner=self, handle=handle, job=job,
                        signaled=True, identity_verified=True, job_empty=True,
                        forced_cleanup_requested=False, exit_code=int(code.value), observed_ns=time.monotonic_ns())
        except Exception as error:
            return dict(status='UNKNOWN', reason=safe_error_code(error) or type(error).__name__[:64])

    def resume(self):
        need(self.key_guard(), 'CURRENT_PRIMARY_OWNER_REQUIRED')
        if self.private_desktop is not None:
            self.check_created_desktop()
        self.native.resume(self.child)

    def check_created_desktop(self):
        row = self.private_desktop.probe_thread(self.child.tid)
        self.desktop_status = dict(row)
        need(row.get('status') != 'OBSERVED' or row.get('matches_private') is True,
             'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH')

    def _observe_parent(self, root, pid, module_entry_type):
        if pid in self._parent_observations or len(self._parent_observations) >= 3:
            return
        member = root.members.get(pid)
        self._parent_observations[pid] = (observed_member_parent(self.native, root, member, module_entry_type)
            if member is not None else dict(pid=pid, birth=None, observed_parent_pid=None, status='UNKNOWN'))

    def process_tree(self):
        return [dict(row) for row in self._parent_observations.values()]

    def tick(self):
        events = self.native.job_events(self.child)
        for member in tuple(self.child.members.values())[:3]:
            self._observe_parent(self.child, member.pid, self._entry_type)
        need(not events, 'OWNED_JOB_CONSTRAINT')
        alive = self.native.active_job_count(self.child) != 0
        if alive and self.private_desktop is not None and self.desktop_status.get('status') != 'OBSERVED':
            self.check_created_desktop()
        return alive

    async def guard(self, peer):
        """Fresh exact TCP tuple, current retained primary identity before/after."""
        if not self.key_guard():
            self._guard_false('RETAINED_BEFORE_SNAPSHOT', False, None, None, None, None)
            return False
        need(peer.get('client_host') == peer.get('server_host') == '127.0.0.1'
             and peer.get('server_port') in (12000, 14030), 'LOOPBACK_PEER_REQUIRED')
        ip = C.WinDLL('iphlpapi', use_last_error=True)
        fn = ip.GetExtendedTcpTable
        fn.argtypes = (C.c_void_p, C.POINTER(W.DWORD), W.BOOL, W.ULONG, C.c_int, W.ULONG)
        fn.restype = W.DWORD
        size = W.DWORD()
        need(fn(None, C.byref(size), False, 2, 5, 0) == 122 and 4 <= size.value <= 1048576,
             'TCP_TABLE_SIZE_UNKNOWN')
        capacity = size.value
        data = C.create_string_buffer(capacity)
        need(fn(data, C.byref(size), False, 2, 5, 0) == 0 and size.value <= capacity,
             'TCP_TABLE_UNKNOWN')
        count = struct.unpack_from('<I', data)[0]
        need(count <= 4096 and 4 + 24 * count <= size.value, 'TCP_TABLE_INCOMPLETE')
        found, states, exact_rows, primary_rows = [], [0] * 13, 0, 0
        for n in range(count):
            state, local, lp, remote, rp, pid = struct.unpack_from('<6I', data, 4 + 24 * n)
            if (local.to_bytes(4, 'little') == b'\x7f\0\0\1'
                    and remote.to_bytes(4, 'little') == b'\x7f\0\0\1'
                    and socket.ntohs(lp & 65535) == peer['client_port']
                    and socket.ntohs(rp & 65535) == peer['server_port']):
                states[state if 1 <= state <= 12 else 0] += 1
                exact_rows += 1
                primary_rows += pid == self.child.pid
                if state == 5:
                    found.append(pid)
        if found != [self.child.pid]:
            self._guard_false('ESTABLISHED_TUPLE_MISMATCH', True, None, states,
                              primary_rows == exact_rows if exact_rows else None, len(found))
            return False
        after = self.key_guard()
        if not after:
            self._guard_false('RETAINED_AFTER_SNAPSHOT', True, False, states, True, len(found))
        return after

    def _guard_false(self, reason, before, after, states, primary, established):
        if self.guard_failure is None:
            self.guard_failure = dict(reason=reason, key_guard_before=before, key_guard_after=after,
                tcp_snapshot='OBSERVED' if states is not None else 'UNKNOWN',
                tcp_state_counts=({str(i) if i else 'UNKNOWN': value for i, value in enumerate(states) if value}
                                  if states is not None else None),
                primary_pid_match=primary, established_match_count=established)

    def request_close(self):
        desktop, child = self.private_desktop, self.child
        def post_owned():
            requested = 0
            for member in tuple(child.members.values()):
                if member.identity.get('image') != str(self.image) or not self.validate(member):
                    continue
                for window in self.native.windows(member):
                    hwnd = window['hwnd']
                    if window.get('visible') and self.native.owned_hwnd(member, hwnd):
                        if desktop is not None:
                            need(self.private_desktop is desktop and self.child is child and not self.closed
                                 and self.owner_handle == child.process and self.owner_job == child.job
                                 and self.validate(member) and self.native.owned_hwnd(member, hwnd),
                                 'OWNED_CLOSE_OWNER_CHANGED')
                            desktop.verify_non_input()
                        need(self.native.u.PostMessageW(hwnd, 0x10, 0, 0), 'OWNED_CLOSE_MESSAGE_FAILED')
                        requested += 1
            return requested
        if desktop is None:
            need(not (self.internal or self.background), 'PRIVATE_DESKTOP_PREPARE_REQUIRED')
            return post_owned()
        errors, results = [], []
        def dispatch(handle):
            try:
                with desktop._lease():
                    with desktop._joined_thread(handle):
                        results.append(post_owned())
            except BaseException as error:
                errors.append(error)
        with desktop._lease() as handle:
            thread = threading.Thread(target=dispatch, args=(handle,), name='local-session-close')
            thread.start()
            thread.join()
        if errors:
            raise errors[0]
        return results[0]

    def close(self):
        if self.closed:
            return self.cleanup
        self._cleanup_requested = True
        try:
            if self.child is not None:
                self.cleanup = self.native.cleanup_owned(self.child)
            else:
                self.cleanup = dict(positive_exit=True, owned_job_empty=True, launched=False)
            return self.cleanup
        finally:
            try:
                self.native.close()
            finally:
                try:
                    if self.private_desktop is not None:
                        self.private_desktop.close()
                finally:
                    self.closed = True


def exit_outcome(cleanup):
    """OS cleanup evidence is distinct from the original game's logout flow."""
    if not isinstance(cleanup, dict) or cleanup.get('positive_exit') is not True:
        return 'CLEANUP_UNKNOWN'
    if cleanup.get('launched') is False:
        return 'NOT_LAUNCHED'
    if cleanup.get('forced_exit') is True or cleanup.get('job_members_forced_cleanup') is True:
        return 'FORCED_CLEANUP'
    if cleanup.get('forced_exit') is False and cleanup.get('job_members_forced_cleanup') is False:
        return 'NATIVE_EXIT_NO_FORCE'
    return 'CLEANUP_UNKNOWN'


def source_logout_outcome(report):
    """Classify only source Quit/drain/EOF and the retained no-force OS exit."""
    unknown = dict(normal_exit_verified=False, game_logout_protocol='UNVERIFIED')
    try:
        cleanup, broker, primary = report['cleanup'], report['broker'], report['primary']
        source_quit = report.get('source_quit')
        if source_quit is not None and source_quit.get('first_returned') is not True:
            return unknown
        safe_refusal = (source_quit is not None and source_quit.get('first_returned') is True
                        and report.get('inventory_pre_write_refusal', {}).get('write_attempted') is False)
        if ((report.get('reason') == 'SESSION_FAILURE' and not safe_refusal)
                or report.get('reason') in ('BROKER_FAILURE', 'STARTUP_FAILURE',
                                   'NATIVE_GUARD_INTEGRITY_FAILURE')
                or report.get('broker_close_error') or report.get('close_wait_end') == 'BROKER_FAILURE'
                or exit_outcome(cleanup) != 'NATIVE_EXIT_NO_FORCE'
                or cleanup.get('retained_members_signaled') is not True
                or cleanup.get('owned_job_empty') is not True
                or type(cleanup.get('exit_code')) is not int or cleanup['exit_code'] != 0
                or cleanup.get('method') != 'retained_exact_owned_job_handle'
                or broker.get('failure_code') is not None or broker.get('cleanup_complete') is not True
                or type(broker.get('active_tasks')) is not int or broker['active_tasks'] != 0
                or type(broker.get('registry_sessions')) is not int or broker['registry_sessions'] != 0
                or broker['settings'].get('session_fatal') is not False):
            return unknown
        members = cleanup['final_owned_members']
        if (type(members) is not list or not members or len(members) > 16
                or type(cleanup.get('retained_member_count')) is not int
                or cleanup['retained_member_count'] != len(members)
                or not all(row.get('retained_handle_signaled') is True
                           and row.get('forced_cleanup_requested_while_active') is False
                           and row.get('natural_exit_observed_before_cleanup') is True for row in members)):
            return unknown
        primary_rows = [row for row in members if row.get('pid') == primary['pid']
                        and str(row.get('birth')) == str(primary['birth'])]
        if (len(primary_rows) != 1 or type(primary_rows[0].get('exit_code')) is not int
                or primary_rows[0]['exit_code'] != 0):
            return unknown
        connections, quit_report = broker['connections'], broker['quit']
        flags = ('eof', 'positive_close', 'joined', 'registry_removed', 'bootstrap_complete')
        if (type(connections) is not list or not connections or len(connections) > 4
                or not all(type(row.get('connection_id')) is int and 1 <= row['connection_id'] <= 4
                           and row.get('failed') is False and all(row.get(key) is True for key in flags)
                           for row in connections)
                or len({row['connection_id'] for row in connections}) != len(connections)
                or type(quit_report.get('active')) is not int or quit_report['active'] != 0):
            return unknown
        sessions = quit_report['sessions']
        if type(sessions) is not list or not sessions or len(sessions) > 4:
            return unknown
        for state in sessions:
            cid = state.get('source_connection_id')
            if (type(cid) is int and type(state.get('uid')) is int and state['uid'] > 0
                    and all(state.get(key) is True for key in
                        ('request_verified', 'response_drain_returned', 'response_queue_empty', 'response_drained'))
                    and any(row['connection_id'] == cid for row in connections)):
                return dict(normal_exit_verified=True, game_logout_protocol='SOURCE_QUIT_DRAIN_EOF_EXIT0')
    except (KeyError, TypeError, AttributeError):
        pass
    return unknown


def current_manual_binding(broker):
    """Fresh unique selected writer projection; never retain a prior selection."""
    from tools.local_original_session.broker import PersistentBroker
    from tools.local_original_session.manual_move_commands import ManualMoveBinding
    if (type(broker) is not PersistentBroker or broker._closing or broker.failure.is_set()
            or broker.policy.state != 'OPEN'):
        return None
    candidates = []
    for rows in broker._claims.values():
        for row in rows:
            writer = row['writer']
            if row['failed'] or row['joined']:
                continue
            try:
                policy_row = broker.policy._connection(writer)
                game = broker.realm.registry.resolve(writer)
                service = broker.realm.service(writer)
                position, selected = service.snapshot(), game.selection
                if (row['policy_row'] is policy_row and policy_row.writer is writer
                        and policy_row.stage == 1 and not policy_row.eof
                        and not policy_row.task_joined and not policy_row.registry_removed
                        and selected is not None and selected.reference == position.name
                        and broker.realm.registry.selected.get(position.name) is selected
                        and not service.fatal):
                    candidates.append(writer)
            except (ValueError, KeyError):
                continue
    return ManualMoveBinding(candidates[0], broker) if len(candidates) == 1 else None


_SOURCE_RESTART_MENU_OWNER = NativeOwner
_SOURCE_RESTART_MENU_CLOSE = NativeOwner.request_close
_SOURCE_RESTART_MENU_VERIFY = NativeOwner.verify_sources


class ManualMoveRequests:
    """One public sequence and pending slot for explicit original UI commands."""
    def __init__(self, directory, consumer, *, allow_attack=False, allow_move=True, inventory_broker=None,
                 inventory_delivery_policy=None, allow_use_item=False, allow_inventory_update=False,
                 inventory_reselection_policy=None, allow_source_restart=False, allow_source_reselect=False):
        from tools.local_original_session.input import _ordinary
        need(type(allow_attack) is bool, 'FEATURE_ATTACK_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_move) is bool, 'FEATURE_MOVE_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_use_item) is bool, 'FEATURE_USE_ITEM_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_inventory_update) is bool, 'FEATURE_INVENTORY_UPDATE_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_source_restart) is bool, 'FEATURE_SOURCE_RESTART_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_source_reselect) is bool, 'FEATURE_SOURCE_RESELECT_CAPABILITY_BOOL_REQUIRED')
        self.directory = _ordinary(directory, directory=True)
        self.consumer = consumer
        from tools.local_original_session.manual_move_commands import ManualMoveCommands
        self._manual_producer = ((consumer, ManualMoveCommands, ManualMoveCommands.poll,
                                  ManualMoveCommands.poll_async)
                                 if type(consumer) is ManualMoveCommands else None)
        self._pending_command = None
        self._rejected_native_sequence = None
        self.allow_attack = allow_attack
        self.allow_use_item = allow_use_item
        self.allow_inventory_update = allow_inventory_update
        self.allow_source_restart = allow_source_restart
        self.allow_source_reselect = allow_source_reselect
        self._source_reselect_started_ns = self._source_reselect_native_state = None
        self._source_reselect_old_generation = None
        self._source_reselect_proof = None
        self._source_restart_menu_attempted = False
        self._source_restart_menu = None
        self._inventory_update_frame = self._inventory_update_state = None
        self.allow_move, self.inventory_broker = allow_move, inventory_broker
        from tools.local_original_session.feature_config import LOCAL_WORLD_READY_ONCE
        need(inventory_delivery_policy is None or inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
             and inventory_broker is not None and inventory_broker._inventory_store is not None,
             'FEATURE_EXPLICIT_STORED_INVENTORY_DELIVERY_POLICY_REQUIRED')
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION
        need(inventory_reselection_policy is None or type(inventory_reselection_policy) is str
             and inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
             and inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
             and inventory_broker is not None and inventory_broker._inventory_store is not None,
             'FEATURE_EXPLICIT_INVENTORY_RESELECTION_POLICY_REQUIRED')
        self.inventory_reselection_policy = inventory_reselection_policy
        need(not allow_source_reselect or allow_source_restart is True
             and inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION,
             'FEATURE_SOURCE_RESELECT_REQUIRES_RESTART_RESELECTION')
        self._source_reselect_methods = None
        if allow_source_reselect:
            need(type(consumer) is ManualMoveCommands, 'FEATURE_SOURCE_RESELECT_REAL_CONSUMER_REQUIRED')
            self._source_reselect_methods = (ManualMoveCommands._current, ManualMoveCommands.submit_source_reselect)
        self.inventory_delivery_policy = inventory_delivery_policy
        self._inventory_generation = None
        self._inventory_generation_monitor = self._inventory_generation_sample = None
        self._inventory_previous_sample_ns = None
        self._inventory_auto_selection = None
        self._inventory_request = None
        self._inventory_wait = None
        self._inventory_started_ns = self._inventory_clock_ns = None
        self._inventory_observer = None
        self._inventory_frame = None
        self._inventory_client_binding = None
        if inventory_broker is not None:
            from tools.local_original_session.inventory_observe import InventoryObserver
            need(digest(Path(__file__).with_name('inventory_observe.py')) == _INVENTORY_OBSERVER_SOURCE_SHA,
                 'FEATURE_INVENTORY_OBSERVER_SOURCE_CHANGED')
            self._inventory_observer_type = InventoryObserver
            self._inventory_observer_sample = InventoryObserver.sample
            self._inventory_observer = InventoryObserver(inventory_broker, consumer.reader)
            if inventory_broker._inventory_store is None:
                self._inventory_frame = inventory_broker._inventory_frame
        self._polling = False
        self._resources_closed = False
        self._prewrite_refusal = None
        self.sequence = 0
        self.pending = False
        self.closed = False
        self.last_result = dict(status='NOT_REQUESTED')
        need(not (self.directory / 'command.result.json').exists(), 'FEATURE_FRESH_COMMAND_STATE_REQUIRED')

    def _record(self, row):
        from tools.local_original_session.commands import _atomic, RESULT_SCHEMA
        if self._pending_command == 'SourceReselect' and self._source_reselect_native_state is not None:
            row = dict(row, command='SourceReselect', native_attempted=True,
                       selection_changed=True, world_ready=True, selection_proof_scope='LOCAL_RESELECT_LAND_READY_ONLY',
                       ui='UNKNOWN', inventory_restore=('ROW_5_SCALARS_MATCHED'
                           if row.get('status') == 'COMMITTED' else 'UNKNOWN'))
        if self._inventory_auto_selection is not None and row.get('command') == 'AddInventory':
            row = dict(row, delivery_policy=self.inventory_delivery_policy,
                       same_broker_reselection_delivery=self.inventory_reselection_policy or 'UNSUPPORTED')
        self.last_result = dict(row, schema=RESULT_SCHEMA, sequence=self.sequence,
                                last_sequence=self.sequence, automatic_retry=False)
        _atomic(self.directory / 'command.result.json', self.last_result, 2048)
        return dict(self.last_result)

    def _consume(self, row):
        if self._pending_command == 'SourceReselect' and row.get('command') == 'AddInventory':
            if row.get('status') == 'COMMITTED':
                need(row.get('proof_scope') == 'CLIENT_ITEM_ROW_SCALARS_ONLY'
                     and row.get('client_inventory') == 'ROW_5_SCALARS_MATCHED',
                     'FEATURE_SOURCE_RESELECT_CLIENT_RESTORE_REQUIRED')
                row = dict(row, proof_scope='CLIENT_SAVED_ITEM_ROW_SCALARS_AFTER_RESELECT')
            row = dict(row, command='SourceReselect', native_attempted=True, ack='UNKNOWN', effect='UNKNOWN')
        result = self._record(row)
        need(row.get('cleanup_required') is not True, 'MANUAL_MOVE_TERMINAL_UNKNOWN')
        return result

    @property
    def last_sample_monotonic_ns(self):
        samples = [self.consumer.last_sample_monotonic_ns, self._inventory_previous_sample_ns]
        if self.inventory_broker is not None:
            samples.append(self.inventory_broker.inventory_sample_monotonic_ns)
            samples.append(self._inventory_observer.last_sample_monotonic_ns)
        return max((n for n in samples if n is not None), default=None)

    def _actual_manual_producer(self, *, asynchronous):
        from tools.local_original_session import manual_move_commands
        producer = self._manual_producer
        if producer is None:
            return None
        consumer, cls, poll, poll_async = producer
        if (self.consumer is not consumer or manual_move_commands.ManualMoveCommands is not cls
                or type(consumer) is not cls or cls.poll is not poll or cls.poll_async is not poll_async):
            return None
        method, original = (consumer.poll_async, poll_async) if asynchronous else (consumer.poll, poll)
        if (type(method) is not MethodType or method.__self__ is not consumer
                or method.__func__ is not original
                or original.__globals__.get('ManualMoveCommands') is not cls
                or original.__qualname__ != 'ManualMoveCommands.' + ('poll_async' if asynchronous else 'poll')
                or Path(original.__code__.co_filename).resolve()
                    != Path(__file__).with_name('manual_move_commands.py').resolve()
                or digest(Path(__file__).with_name('manual_move_commands.py')) != _MANUAL_REJECTION_SOURCE_SHA):
            return None
        return consumer

    def _actual_move_rejection(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None:
            return False
        expected = dict(status='REJECTED', phase='REJECTED', reason='EDGE_BLOCKED', command='MoveGoal',
            accepted=False, native_attempted=True, automatic_retry=False, cleanup_required=False,
            proof_scope='SC4EE0_DRAIN_WITH_CLIENT_SETTLED', moving_back_snapshot_observed=True,
            moving_back_start_observed=False, sequence=consumer.sequence)
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and type(consumer.sequence) is int and 1 <= consumer.sequence <= 2147483647
                and consumer.pending is None and type(consumer.state) is dict and consumer.state == result
                and self._inventory_request is None and self._inventory_wait is None)

    def _actual_use_item_commit(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None:
            return False
        expected = dict(status='COMMITTED', reason=None, sequence=consumer.sequence,
            automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
            command='UseItem', proof_scope='VALIDATED_ITEM_USE_INTENT_ONLY',
            use_effect='UNKNOWN', ack='UNKNOWN', equipped='UNKNOWN', render='UNKNOWN', save='UNKNOWN')
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and type(consumer.sequence) is int and 1 <= consumer.sequence <= 2147483647
                and consumer.pending is None and type(consumer.state) is dict and consumer.state == result
                and self._inventory_request is None and self._inventory_wait is None)

    def _actual_source_restart_commit(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None or consumer.allow_source_restart is not True:
            return False
        expected = dict(status='COMMITTED', reason=None, sequence=consumer.sequence,
            automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
            command='SourceRestart', proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY',
            response_drained=True, selection_cleared=True, ui='UNKNOWN', inventory_restore='UNKNOWN')
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and type(consumer.sequence) is int and 1 <= consumer.sequence <= 2147483647
                and consumer.pending is None and type(consumer.state) is dict and consumer.state == result
                and self._inventory_request is None and self._inventory_wait is None)

    def _actual_source_reselect_commit(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None or consumer.allow_source_reselect is not True:
            return False
        expected = dict(status='COMMITTED', reason=None, sequence=consumer.sequence,
            automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
            command='SourceReselect', proof_scope='LOCAL_RESELECT_LAND_READY_ONLY',
            selection_changed=True, world_ready=True, ui='UNKNOWN', inventory_restore='UNKNOWN')
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and type(consumer.sequence) is int and 1 <= consumer.sequence <= 2147483647
                and consumer.pending is None and type(consumer.state) is dict and consumer.state == result)

    def _source_reselect_current(self):
        """Consume the original producer's completed old/new lifetime proof."""
        consumer = self._actual_manual_producer(asynchronous=True)
        need(consumer is self.consumer and consumer is not None and self.allow_source_reselect is True
             and self._actual_source_reselect_commit(consumer.state, asynchronous=True)
             and (self._source_reselect_native_state is None or consumer.state is self._source_reselect_native_state),
             'FEATURE_SOURCE_RESELECT_ACTUAL_COMPLETION_REQUIRED')
        state = consumer.state
        original, submit = self._source_reselect_methods
        current_method = consumer._current
        need(type(consumer)._current is original and type(consumer).submit_source_reselect is submit
             and type(current_method) is MethodType and current_method.__self__ is consumer
             and current_method.__func__ is original, 'FEATURE_SOURCE_RESELECT_ORIGINAL_METHOD_REQUIRED')
        proof = consumer._source_reselect_completed
        need(type(proof) is tuple and len(proof) == 4
             and (self._source_reselect_proof is None or proof is self._source_reselect_proof),
             'FEATURE_SOURCE_RESELECT_REAL_PROOF_REQUIRED')
        old, generation, bound, before = proof
        previous = self._source_reselect_old_generation
        need(type(old) is dict and old is consumer._source_restart_completed
             and previous is not None and old.get('restart_generation') is previous
             and previous.phase == 'RETIRED' and previous.service._closed
             and type(before) is tuple and len(before) == 8 and type(bound) is tuple and len(bound) == 6
             and bound is consumer._bound and type(bound[0]) is tuple and len(bound[0]) == 17,
             'FEATURE_SOURCE_RESELECT_OLD_LIFETIME_REQUIRED')
        writer, broker = before[0].writer, before[0].broker
        need(broker is self.inventory_broker and generation is self._inventory_reselection_current(writer)
             and generation is broker._inventory_generation and generation.previous is previous
             and generation.row is before[1] and generation.mover is before[2]
             and generation.restart_state is previous.restart_state
             and old.get('restart_state') is generation.restart_state
             and generation.row.get('_restart') is generation.restart_state
             and generation.restart_state['phase'] == 'DRAINED'
             and all(generation.restart_state[k] is True for k in
                     ('write_attempted', 'drain_returned', 'response_drained', 'selection_cleared'))
             and generation.restart_state['frame'] is old['completed_restart_frame']
             and generation.restart_state['lock'] is generation.lock is generation.row['operation_lock']
             and bound[0][0] is writer and bound[0][1] is broker
             and bound[0][9] is generation.mover and bound[0][12] is generation.selected,
             'FEATURE_SOURCE_RESELECT_NEW_LIFETIME_REQUIRED')
        actual = original(consumer)
        need(actual[0].writer is writer and actual[0].broker is broker
             and all(a is b for a, b in zip(actual[1:5], before[1:5]))
             and actual[5:] == before[5:] and actual[7] == (0, 0, 0)
             and consumer._source_reselect_completed is proof and consumer._bound is bound
             and consumer._source_restart_completed is old and consumer.state is state
             and self._inventory_reselection_current(writer) is generation,
             'FEATURE_SOURCE_RESELECT_CURRENT_CHANGED')
        return proof

    def _source_reselect_can_receive(self):
        if (self.allow_source_reselect is not True or self.pending
                or self._inventory_request is not None or self._inventory_wait is not None):
            return False
        consumer = self._actual_manual_producer(asynchronous=True)
        if consumer is None or not self._actual_source_restart_commit(consumer.state, asynchronous=True):
            return False
        from tools.local_original_session.commands import RESULT_SCHEMA
        old = self._inventory_generation
        return (self.last_result == dict(consumer.state, schema=RESULT_SCHEMA,
                    sequence=self.sequence, last_sequence=self.sequence)
                and old is not None and old.phase == 'RETIRED'
                and self._inventory_reselection_current(old.writer) is None)

    def _source_reselect_now(self):
        from tools.local_original_session.manual_move_commands import WAIT_NS
        now = self.consumer._clock()
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        need(type(self._source_reselect_started_ns) is int
             and 0 <= now - self._source_reselect_started_ns < WAIT_NS,
             'FEATURE_SOURCE_RESELECT_ORIGINAL_DEADLINE')
        return now

    def _source_reselect_restoring(self):
        if (self._pending_command != 'SourceReselect' or self.pending is not True
                or self._source_reselect_native_state is None):
            return False
        self._source_reselect_current()
        return True

    def _source_restart_handoff(self):
        """Let the same pending producer finish after its ACK clears selection."""
        if (not self.allow_source_restart or not self.pending or self._pending_command != 'SourceRestart'
                or self._inventory_request is not None or self._inventory_wait is not None):
            return False
        consumer = self._actual_manual_producer(asynchronous=True)
        if consumer is None or consumer.allow_source_restart is not True:
            return False
        pending, state = consumer.pending, consumer.state
        return (type(pending) is dict and pending.get('kind') == 'SourceRestart'
                and type(state) is dict and state.get('status') == 'PENDING'
                and state.get('phase') in ('ADMISSION', 'NATIVE_WAIT')
                and state.get('cleanup_required') is False
                or pending is None and self._actual_source_restart_commit(state, asynchronous=True))

    def _source_restart_menu_current(self):
        from tools.local_original_session.manual_move_commands import WAIT_NS
        consumer = self._actual_manual_producer(asynchronous=True)
        need(consumer is self.consumer and consumer is not None and self.allow_source_restart is True
             and consumer.allow_source_restart is True and self.pending is True
             and self._pending_command == 'SourceRestart', 'FEATURE_SOURCE_RESTART_MENU_PRODUCER_REQUIRED')
        pending, reader = consumer.pending, consumer.reader
        need(type(pending) is dict and pending.get('kind') == 'SourceRestart'
             and pending.get('phase') == 'ADMISSION' and pending.get('native_attempted') is False
             and pending.get('request') is None and consumer.state.get('status') == 'PENDING'
             and consumer.state.get('phase') == 'ADMISSION' and consumer.state.get('native_attempted') is False,
             'FEATURE_SOURCE_RESTART_MENU_ADMISSION_REQUIRED')
        owner, cls = reader.owner, _SOURCE_RESTART_MENU_OWNER
        need(NativeOwner is cls and type(owner) is cls and cls.request_close is _SOURCE_RESTART_MENU_CLOSE
             and cls.verify_sources is _SOURCE_RESTART_MENU_VERIFY,
             'FEATURE_SOURCE_RESTART_MENU_OWNER_METHOD_REQUIRED')
        current = consumer._current()
        broker = current[0].broker
        need(type(broker.source_guard) is MethodType and broker.source_guard.__self__ is owner
             and broker.source_guard.__func__ is _SOURCE_RESTART_MENU_VERIFY,
             'FEATURE_SOURCE_RESTART_MENU_SOURCE_REQUIRED')
        def binding(value):
            game = broker.realm.registry.resolve(value[0].writer)
            return ((self.consumer, consumer.pending, consumer.reader, reader.owner, reader.member,
                reader.backend, consumer._bound, value[0].writer, value[0].broker, *value[1:5],
                owner.directory, owner.child, owner.native, owner.private_desktop, consumer.state,
                owner.source_guard, broker.source_guard, consumer.clock_ns, NativeOwner,
                cls.request_close, cls.verify_sources, _SOURCE_RESTART_MENU_CLOSE, _SOURCE_RESTART_MENU_VERIFY,
                broker.realm, game, game.selection, broker.realm.registry.selected.get(value[3].name),
                broker.realm._movement.get(id(value[0].writer)), value[2].snapshot()),
                tuple((type(item), item) for item in (self.sequence, consumer.sequence, pending['started'],
                    value[5], tuple(value[6].items()), value[7], owner.closed, reader.closed,
                    owner.owner_handle, owner.owner_job, reader.member.process, reader.member.job,
                    reader.member.pid, tuple(reader.member.identity.items()),
                    broker._closing, broker.failure.is_set(), broker.policy.state,
                    value[1]['failed'], value[1]['joined'], value[1]['policy_row'].eof,
                    pending.get('phase'), pending.get('native_attempted'), consumer.state.get('status'),
                    consumer.state.get('phase'), consumer.state.get('native_attempted'))))
        before = binding(current)
        _SOURCE_RESTART_MENU_VERIFY(owner)
        after = consumer._current()
        actual = binding(after)
        need(all(a is b for a, b in zip(before[0], actual[0])) and before[1] == actual[1]
             and after[3] is pending['initial'] and after[7] == pending['before'],
             'FEATURE_SOURCE_RESTART_MENU_BINDING_CHANGED')
        now = consumer._clock()
        need(type(pending['started']) is int and 0 <= now - pending['started'] < WAIT_NS,
             'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        final = binding(after)
        need(all(a is b for a, b in zip(actual[0], final[0])) and actual[1] == final[1],
             'FEATURE_SOURCE_RESTART_MENU_BINDING_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return final, now

    def _source_restart_menu_prepare(self):
        from tools.local_original_session.manual_move_commands import SAMPLE_NS
        need(self._source_restart_menu_attempted is False, 'FEATURE_SOURCE_RESTART_MENU_ALREADY_ATTEMPTED')
        before, _ = self._source_restart_menu_current()
        self._source_restart_menu_attempted = True  # Spend before any owned WM_CLOSE side effect.
        requested = _SOURCE_RESTART_MENU_CLOSE(before[0][3])  # Original method; runner wrapper is not delegated to.
        need(type(requested) is int and requested > 0, 'FEATURE_SOURCE_RESTART_MENU_POST_REQUIRED')
        after, now = self._source_restart_menu_current()
        need(all(a is b for a, b in zip(before[0], after[0])) and before[1] == after[1],
             'FEATURE_SOURCE_RESTART_MENU_BINDING_CHANGED')
        self._source_restart_menu = (before, now + SAMPLE_NS)

    def _source_restart_menu_wait(self):
        if self._source_restart_menu is None:
            return False
        before, floor = self._source_restart_menu
        after, now = self._source_restart_menu_current()
        need(all(a is b for a, b in zip(before[0], after[0])) and before[1] == after[1],
             'FEATURE_SOURCE_RESTART_MENU_BINDING_CHANGED')
        if now < floor:
            return True  # No sample timestamp or consumer outcome is fabricated.
        self._source_restart_menu = None
        return False

    def _source_restart_menu_failed(self, error):
        self._record(dict(status='UNKNOWN', command='SourceRestart', phase='ADMISSION',
            reason=('FEATURE_SOURCE_RESTART_MENU_CANCELLED' if isinstance(error, asyncio.CancelledError)
                    else safe_error_code(error) or 'FEATURE_SOURCE_RESTART_MENU_UNKNOWN'),
            native_attempted=False, cleanup_required=True, automatic_retry=False))

    def _receive(self, result, *, asynchronous=False):
        from tools.local_original_session.commands import _json, REQUEST_SCHEMA, MAX_SEQUENCE
        if result.get('status') == 'COMMITTED' and (result.get('command') == 'SourceReselect'
                or self.pending and self._pending_command == 'SourceReselect'):
            if (not self.allow_source_reselect or self.pending and self._pending_command != 'SourceReselect'
                    or not self._actual_source_reselect_commit(result, asynchronous=asynchronous)):
                return self._consume(dict(status='UNKNOWN', command='SourceReselect', cleanup_required=True,
                    reason='FEATURE_SOURCE_RESELECT_COMPLETION_UNKNOWN', automatic_retry=False))
            self._source_reselect_current()
            if self.pending:
                if self._source_reselect_native_state is None:
                    self._source_reselect_native_state = self.consumer.state
                    self._source_reselect_proof = self.consumer._source_reselect_completed
                self._source_reselect_now()
                self._source_reselect_current()
                return self._record(dict(result, status='PENDING', phase='INVENTORY_RESTORE',
                                         inventory_restore='UNKNOWN'))
            need(self.consumer.state is self._source_reselect_native_state
                 and self.last_result.get('command') == 'SourceReselect'
                 and self.last_result.get('status') == 'COMMITTED',
                 'FEATURE_SOURCE_RESELECT_PUBLIC_COMPLETION_REQUIRED')
        if result.get('status') == 'COMMITTED' and (result.get('command') == 'SourceRestart'
                or self.pending and self._pending_command == 'SourceRestart'):
            if (not self.allow_source_restart or self.pending and self._pending_command != 'SourceRestart'
                    or not self._actual_source_restart_commit(result, asynchronous=asynchronous)):
                return self._consume(dict(status='UNKNOWN', command='SourceRestart', cleanup_required=True,
                    reason='FEATURE_MANUAL_SOURCE_RESTART_COMPLETION_UNKNOWN', automatic_retry=False))
        if result.get('status') == 'COMMITTED' and (result.get('command') == 'UseItem'
                or self.pending and self._pending_command == 'UseItem'):
            if (not self.allow_use_item or self.pending and self._pending_command != 'UseItem'
                    or not self._actual_use_item_commit(result, asynchronous=asynchronous)):
                return self._consume(dict(status='UNKNOWN', command='UseItem', cleanup_required=True,
                    reason='FEATURE_MANUAL_USE_ITEM_COMPLETION_UNKNOWN', automatic_retry=False))
        if result.get('status') == 'REJECTED':
            valid = self._actual_move_rejection(result, asynchronous=asynchronous)
            if (not valid or self.pending and self._pending_command != 'MoveGoal'
                    or not self.pending and self._rejected_native_sequence != result.get('sequence')):
                return self._consume(dict(status='UNKNOWN', reason='FEATURE_MANUAL_MOVE_REJECTION_UNKNOWN',
                    command='MoveGoal', cleanup_required=True, automatic_retry=False))
            if self.pending:
                self.pending, self._pending_command = False, None
                self._rejected_native_sequence = result['sequence']
                return self._consume(dict(result, native_sequence=result['sequence']))
            # The same settled native rejection is idle, never an automatic replay.
        if result.get('cleanup_required') is True:
            return self._consume(result)
        if self.pending:
            self.pending = result['status'] != 'COMMITTED'
            if not self.pending:
                self._pending_command = None
            return self._consume(result)
        try:
            request = _json(self.directory / 'command.request.json', 1024)
        except FileNotFoundError:
            return dict(self.last_result)
        fields = {'MoveGoal': {'schema', 'sequence', 'command', 'uid', 'x', 'y'},
                  'AttackTarget': {'schema', 'sequence', 'command', 'uid', 'target_uid', 'map_id'},
                  'AddInventory': {'schema', 'sequence', 'command', 'uid', 'map_id'},
                  'UseItem': {'schema', 'sequence', 'command', 'uid', 'item_identifier', 'map_id'},
                  'SourceRestart': {'schema', 'sequence', 'command', 'uid', 'map_id'},
                  'SourceReselect': {'schema', 'sequence', 'command', 'uid', 'map_id'},
                  'UpdateInventory': {'schema', 'sequence', 'command', 'uid', 'item_identifier', 'map_id', 'field4_u64'}}
        command = request.get('command')
        need(type(command) is str and command in fields
             and set(request) == fields[command] and request['schema'] == REQUEST_SCHEMA,
             'FEATURE_MANUAL_MOVE_SCHEMA_REQUIRED')
        need(command != 'AttackTarget' or self.allow_attack, 'FEATURE_MANUAL_ATTACK_NOT_ENABLED')
        need(command != 'MoveGoal' or self.allow_move, 'FEATURE_MANUAL_MOVE_NOT_ENABLED')
        need(command != 'UseItem' or asynchronous and self.allow_use_item, 'FEATURE_MANUAL_USE_ITEM_NOT_ENABLED')
        need(command != 'SourceRestart' or asynchronous and self.allow_source_restart,
             'FEATURE_MANUAL_SOURCE_RESTART_NOT_ENABLED')
        need(command != 'SourceReselect' or asynchronous and self.allow_source_reselect,
             'FEATURE_MANUAL_SOURCE_RESELECT_NOT_ENABLED')
        need(command != 'UpdateInventory' or asynchronous and self.allow_inventory_update
             and self.inventory_broker is not None, 'FEATURE_INVENTORY_UPDATE_NOT_ENABLED')
        if command == 'UpdateInventory':
            need(all(type(request[k]) is int for k in ('uid', 'item_identifier', 'map_id', 'field4_u64'))
                 and 0 < request['uid'] <= 0xffffffffffffffff
                 and 0 < request['item_identifier'] <= 0xffffffffffffffff
                 and 0 <= request['map_id'] <= 0x7fffffff
                 and 0 <= request['field4_u64'] <= 0xffffffffffffffff,
                 'FEATURE_INVENTORY_UPDATE_UID_MAP_FIELD_REQUIRED')
        if command == 'UseItem':
            need(all(type(request[k]) is int for k in ('uid', 'item_identifier', 'map_id'))
                 and 0 < request['uid'] <= 0xffffffffffffffff
                 and 0 < request['item_identifier'] <= 0xffffffffffffffff
                 and 0 <= request['map_id'] <= 0x7fffffff, 'FEATURE_MANUAL_USE_ITEM_UID_MAP_REQUIRED')
        if command in ('SourceRestart', 'SourceReselect'):
            need(type(request['uid']) is int and 0 < request['uid'] <= 0xffffffffffffffff
                 and type(request['map_id']) is int and 0 <= request['map_id'] <= 0x7fffffff,
                 'FEATURE_MANUAL_SOURCE_RESTART_UID_MAP_REQUIRED')
        need(command != 'AddInventory' or asynchronous and self.inventory_broker is not None,
             'FEATURE_INVENTORY_NOT_ENABLED')
        sequence = request['sequence']
        need(type(sequence) is int and 1 <= sequence <= MAX_SEQUENCE,
             'FEATURE_MANUAL_SEQUENCE_REQUIRED')
        if sequence <= self.sequence:
            return dict(self.last_result)
        if self._source_reselect_can_receive():
            need(command == 'SourceReselect', 'FEATURE_SOURCE_RESELECT_ONLY_WHILE_CLEARED')
        if command == 'SourceRestart':
            need(self._actual_manual_producer(asynchronous=True) is self.consumer
                 and self.consumer.allow_source_restart is True,
                 'FEATURE_MANUAL_SOURCE_RESTART_PRODUCER_REQUIRED')
        if command == 'SourceReselect':
            from tools.local_original_session.commands import RESULT_SCHEMA
            consumer = self._actual_manual_producer(asynchronous=True)
            old = self._inventory_generation
            need(consumer is self.consumer and consumer is not None and consumer.allow_source_reselect is True
                 and self.allow_source_restart is True and self.inventory_reselection_policy is not None
                 and self._actual_source_restart_commit(consumer.state, asynchronous=True)
                 and self.last_result == dict(consumer.state, schema=RESULT_SCHEMA,
                    sequence=self.sequence, last_sequence=self.sequence)
                 and old is not None and old.phase == 'RETIRED' and old.service._closed
                 and self._inventory_reselection_current(old.writer) is None,
                 'FEATURE_SOURCE_RESELECT_PREVIOUS_RESTART_REQUIRED')
            self._source_reselect_started_ns = consumer._clock()  # First public deadline, never renewed by phases.
            self._source_reselect_old_generation = old
            submit = consumer.submit_source_reselect
            need(type(submit) is MethodType and submit.__self__ is consumer
                 and submit.__func__ is self._source_reselect_methods[1]
                 and type(consumer).submit_source_reselect is submit.__func__,
                 'FEATURE_SOURCE_RESELECT_ORIGINAL_METHOD_REQUIRED')
        self.sequence = sequence
        if command in ('AddInventory', 'UpdateInventory'):
            self._inventory_auto_selection = None  # This request has an explicit origin.
            self._inventory_started_ns = self._inventory_clock_ns = time.monotonic_ns()
        self._record(dict(status='CLAIMED', invoked=False, command=command))
        self.pending = True  # Claim before native side effects; never replay.
        self._pending_command = command
        if command in ('AddInventory', 'UpdateInventory'):
            self._inventory_request = request
            return dict(self.last_result)
        if command == 'UseItem':
            return self._consume(self.consumer.submit_use_item(
                request['uid'], request['item_identifier'], request['map_id']))
        if command == 'SourceRestart':
            result = self._consume(self.consumer.submit_source_restart(request['uid'], request['map_id']))
            try:
                self._source_restart_menu_prepare()
            except BaseException as error:
                self._source_restart_menu_failed(error)
                raise
            return result
        if command == 'SourceReselect':
            need(self._actual_manual_producer(asynchronous=True) is submit.__self__
                 and type(submit.__self__).submit_source_reselect is self._source_reselect_methods[1],
                 'FEATURE_SOURCE_RESELECT_PRODUCER_CHANGED')
            return self._consume(submit(request['uid'], request['map_id']))
        if command == 'AttackTarget':
            return self._consume(self.consumer.submit_attack(
                request['uid'], request['target_uid'], request['map_id']))
        return self._consume(self.consumer.submit_goal(request['uid'], request['x'], request['y']))

    def _inventory_unknown(self, reason):
        admission = self._inventory_request is not None
        return self._consume(dict(status='UNKNOWN',
            command='UpdateInventory' if self._pending_command == 'UpdateInventory' else 'AddInventory',
            phase='ADMISSION' if admission else 'CLIENT_WAIT', reason=reason, cleanup_required=True,
            invoked=not admission, proof_scope='UNKNOWN' if admission else 'TRANSPORT_DRAIN_ONLY',
            client_inventory='UNKNOWN', render='UNKNOWN', equipped='UNKNOWN', save='UNKNOWN'))

    def _inventory_diagnostic_capture(self):
        """Objects only: optional diagnostics never sample or alter admission."""
        try:
            from tools.local_original_session.broker import PersistentBroker
            from tools.local_original_session.inventory import InventoryService
            broker, consumer = self.inventory_broker, self.consumer
            service, frame = broker._inventory_service, self._inventory_frame
            if (type(broker) is not PersistentBroker or type(service) is not InventoryService
                    or service.broker is not broker or type(frame) is not bytes):
                return None
            reader = service.reader
            if reader is not consumer.reader or broker._inventory_frame is not frame:
                return None
            return (broker, service, frame, service.last_result, consumer, reader,
                    reader.backend, reader.owner, reader.member, broker._inventory_restore_only)
        except Exception:
            return None

    def _inventory_pre_write_diagnostic(self, error, captured, *, refusal=None):
        """Copy only a current failed prewrite's bounded diagnostic facts."""
        try:
            from tools.local_original_session.broker import PersistentBroker
            from tools.local_original_session.inventory import (
                InventoryService, PreWriteReadRefusal, ReadOnlyPreWriteRefusal)
            if type(captured) is not tuple or len(captured) != 10:
                return None
            broker, service, frame, previous, consumer, reader, backend, owner, member, mode = captured
            if (self.inventory_broker is not broker or type(broker) is not PersistentBroker
                    or broker._inventory_service is not service
                    or type(service) is not InventoryService or service.broker is not broker
                    or self.consumer is not consumer or consumer.reader is not reader
                    or service.reader is not reader or reader.backend is not backend
                    or reader.owner is not owner or reader.member is not member
                    or broker._inventory_frame is not frame or self._inventory_frame is not frame
                    or broker._inventory_operation_frame is not frame
                    or broker._inventory_write_attempted is not False):
                return None
            report = service.last_result
            if type(error) in (PreWriteReadRefusal, ReadOnlyPreWriteRefusal):
                # Caller has just completed the existing refusal-current check.
                # Only the original deadline can publish this retained report.
                if (broker._inventory_admission_expired is not True
                        or type(refusal) is not tuple or len(refusal) != 5
                        or broker._inventory_prewrite_refusal is not refusal
                        or refusal[0] is not error or refusal[2] is not service
                        or type(mode) is not bool or refusal[3] is not mode
                        or broker._inventory_restore_only is not mode or refusal[4] is not frame):
                    return None
                reason = error.reason
            else:
                if report is previous:
                    return None
                reason = safe_error_code(error)
            if (type(report) is not dict or type(reason) is not str
                    or type(report.get('status')) is not str or report['status'] != 'UNKNOWN'
                    or type(report.get('reason')) is not str
                    or report['reason'] != reason):
                return None
            def integer(value, low, high):
                return type(value) is int and low <= value <= high
            def stage(value):
                return (type(value) is str and value in (
                    'SOURCE_BEFORE', 'AUTHORITY_BEFORE', 'WORLD_TYPED', 'INVENTORY_TYPED',
                    'EMPTY_VECTOR', 'FINAL_READBACK', 'ROOT_RECHECK', 'AUTHORITY_AFTER', 'SOURCE_AFTER')
                    or type(value) is str and re.fullmatch(r'CODE_GUARD_(?:BEFORE|AFTER)(?:_[0-9]{4})?', value) is not None)
            current_stage, requests, changed = (report['pre_write_stage'], report['typed_read_requests'],
                                                 report['changed_read'])
            spent = report['typed_bytes_requested']
            if not stage(current_stage) or not integer(requests, 0, 16385) or not integer(spent, 0, 16384):
                return None
            if requests == 0 and (spent != 0 or changed is not None
                                  or current_stage not in ('SOURCE_BEFORE', 'AUTHORITY_BEFORE')):
                return None
            if changed is not None:
                keys = {'stage', 'comparison', 'request_ordinal', 'record_ordinal', 'record_count',
                        'requested_width', 'typed_bytes_requested', 'image'}
                if (type(changed) is not dict or any(type(key) is not str for key in changed)
                        or set(changed) != keys
                        or not stage(changed['stage']) or changed['stage'] != current_stage
                        or type(changed['comparison']) is not str
                        or changed['comparison'] not in ('INITIAL', 'WORLD_READBACK', 'BUDGET_READBACK')
                        or not integer(changed['request_ordinal'], 1, requests)
                        or not integer(changed['record_count'], 0, 16384)
                        or changed['record_ordinal'] is not None
                           and not integer(changed['record_ordinal'], 1, changed['record_count'])
                        or not integer(changed['requested_width'], 1, 4096)
                        or not integer(changed['typed_bytes_requested'], 0, 16384)
                        or changed['typed_bytes_requested'] != spent or type(changed['image']) is not bool):
                    return None
                changed = dict(changed)
            diagnostic = dict(pre_write_stage=current_stage, typed_read_requests=requests, changed_read=changed)
            refused = report.get('refused_read')
            keys = {'at', 'size', 'image_base', 'state', 'protection', 'type', 'guard',
                    'length_fits', 'image_allocation_matches', 'requested_bytes'}
            if (type(error) is PreWriteReadRefusal and type(refused) is dict
                    and all(type(key) is str for key in refused) and set(refused) == keys
                    and refused == error.refused_read
                    and integer(refused['size'], 1, 4096)
                    and integer(refused['at'], 0x10000, 0x7fffffffffff - refused['size'])
                    and (refused['image_base'] is None or integer(refused['image_base'], 0x10000, 0x7fffffffffff))
                    and all(integer(refused[key], 0, 0xffffffff) for key in ('state', 'protection', 'type'))
                    and all(type(refused[key]) is bool for key in ('guard', 'length_fits'))
                    and (refused['image_allocation_matches'] is None if refused['image_base'] is None
                         else type(refused['image_allocation_matches']) is bool)
                    and type(refused['requested_bytes']) is int and refused['requested_bytes'] == refused['size']):
                diagnostic['refused_read'] = dict(refused)  # Output only; never admission or retry authority.
            return diagnostic
        except Exception:
            return None  # Optional metadata must never replace the original failure.

    def _inventory_reselection_current(self, writer):
        from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION
        broker, reader = self.inventory_broker, self.consumer.reader
        method = broker.inventory_selection_current
        need(type(broker) is PersistentBroker and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
             and broker.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
             and getattr(method, '__self__', None) is broker
             and getattr(method, '__func__', None) is PersistentBroker.inventory_selection_current,
             'FEATURE_INVENTORY_ACTUAL_GENERATION_API_REQUIRED')
        generation = method(writer)  # Structural only; never a memory/Store query.
        if generation is None:
            return None
        need(type(generation) is _InventoryGeneration and generation.broker is broker
             and generation.writer is writer and generation.phase == 'ACTIVE'
             and generation.reader is reader and generation.store is broker._inventory_store
             and generation.service is broker._inventory_service
             and generation.service.reader is reader and generation.service._reader is reader
             and generation.service._backend is reader.backend and generation.service.store is generation.store
             and generation.selection_binding is broker._inventory_selection_binding,
             'FEATURE_INVENTORY_CURRENT_GENERATION_REQUIRED')
        binding = generation.selection_binding
        if binding is not None:
            need(type(binding) is tuple and len(binding) == 11 and all(a is b for a, b in zip(binding,
                (writer, generation.row, generation.lock, broker.realm, broker.realm.registry,
                 generation.game, generation.mover, generation.selected, generation.service,
                 generation.store, broker._inventory_frame))), 'FEATURE_INVENTORY_GENERATION_BINDING_CHANGED')
        return generation

    def _inventory_source_restart_reservation(self, generation, previous):
        """Preserve this producer's spent native slot across its real Restart."""
        consumer = self.consumer
        if (self._pending_command == 'SourceReselect' and self._source_reselect_native_state is not None
                and consumer._reservation is True):
            old, current, _bound, _snapshot = self._source_reselect_current()
            return (generation.restart_state if current is generation
                    and old['restart_generation'] is previous else None)
        if (self.allow_source_restart is not True or consumer._reservation is not True
                or previous is None or consumer._source_restart_claimed is not True
                or not self._actual_source_restart_commit(consumer.state, asynchronous=True)):
            return None
        from tools.local_original_session.commands import RESULT_SCHEMA
        if self.last_result != dict(consumer.state, schema=RESULT_SCHEMA, sequence=self.sequence,
                                    last_sequence=self.sequence):
            return None
        state = generation.restart_state
        if (type(state) is not dict or state is not previous.restart_state
                or generation.row.get('_restart') is not state or state.get('phase') != 'DRAINED'
                or state.get('lock') is not generation.lock
                or any(state.get(key) is not True for key in ('write_attempted', 'drain_returned',
                                                               'response_drained', 'selection_cleared'))):
            return None
        binding = state.get('binding')
        if not (type(binding) is tuple and len(binding) == 2 and type(binding[0]) is tuple
                and len(binding[0]) == 23 and all(binding[0][index] is value for index, value in
                    ((0, self.inventory_broker), (2, generation.row), (7, previous.game),
                     (8, previous.mover), (10, previous.selected), (22, generation.lock)))):
            return None
        return state

    def _refresh_inventory_selection(self, monitor):
        if self.inventory_reselection_policy is None:
            return True
        need(self._polling is True, 'FEATURE_COMMAND_POLL_INFLIGHT')
        broker = self.inventory_broker
        binding = current_manual_binding(broker)
        previous = self._inventory_generation
        writer = binding.writer if binding is not None else (None if previous is None else previous.writer)
        if writer is None:
            return False
        generation = self._inventory_reselection_current(writer)
        if generation is None:
            need(not self.pending and self._inventory_request is None and self._inventory_wait is None
                 and self.consumer.pending is None and self.consumer.state['status'] != 'UNKNOWN'
                 and self.last_result.get('status') != 'UNKNOWN',
                 'FEATURE_INVENTORY_RESELECTION_PENDING_OR_TERMINAL')
            if previous is not None and previous.phase == 'RETIRED':
                self._inventory_observer.close()  # Private helper only; no reader/broker close.
            return False  # No current ACTIVE selection: no IPC claim or trigger.
        if generation is previous:
            return True
        reselecting = self._source_reselect_restoring()
        reservation = self.consumer._reservation
        restart_reservation = self._inventory_source_restart_reservation(generation, previous)
        need(not self.closed and not self._resources_closed and (not self.pending or reselecting)
             and self._inventory_request is None and self._inventory_wait is None
             and self._prewrite_refusal is None and self.consumer.pending is None
             and (reservation is False or restart_reservation is not None)
             and self.consumer.state['status'] in ('READY', 'COMMITTED')
             and self.last_result.get('status') != 'UNKNOWN',
             'FEATURE_INVENTORY_RESELECTION_PENDING_OR_TERMINAL')
        need(generation.previous is previous and (previous is None or previous.phase == 'RETIRED'
             and previous.service._closed and previous.writer is writer
             and previous.reader is generation.reader and previous.store is generation.store
             and previous.game is generation.game and previous.selected is not generation.selected),
             'FEATURE_INVENTORY_PREVIOUS_GENERATION_REQUIRED')
        need(not generation.service._claimed and not broker._inventory_attempted
             and not broker._inventory_write_attempted and broker._inventory_delivery_authority is None
             and broker._inventory_current_frame is None and broker._inventory_update_operation is None,
             'FEATURE_INVENTORY_FRESH_GENERATION_REQUIRED')
        from tools.local_original_session.inventory_observe import InventoryObserver
        need(InventoryObserver is self._inventory_observer_type
             and InventoryObserver.sample is self._inventory_observer_sample
             and digest(Path(__file__).with_name('inventory_observe.py')) == _INVENTORY_OBSERVER_SOURCE_SHA,
             'FEATURE_INVENTORY_OBSERVER_SOURCE_CHANGED')
        from tools.local_original_session.observe import SessionMonitor
        monitor_ref = sample_floor = None
        if (type(monitor) is SessionMonitor and monitor.reader is self.consumer.reader
                and monitor.owner is self.consumer.reader.owner):
            need(type(monitor.samples) is int and 0 <= monitor.samples,
                 'FEATURE_INVENTORY_RESELECTION_SAMPLE_REQUIRED')
            monitor_ref, sample_floor = monitor, monitor.samples
        def refs():
            return (generation.writer, generation.row, generation.lock, generation.game,
                generation.selected, generation.mover, generation.reader, generation.store,
                generation.service, generation.item_use_session, generation.selection_binding,
                generation.previous, generation.restart_state, generation.restored, broker._inventory_frame,
                self.consumer.reader.backend, self.consumer.reader.owner, self.consumer.reader.member)
        original = refs()
        consumer, public_sequence, native_sequence = self.consumer, self.sequence, self.consumer.sequence
        sampled = self.last_sample_monotonic_ns
        observer = InventoryObserver(broker, consumer.reader)
        try:
            need(self._inventory_reselection_current(writer) is generation
                 and all(a is b for a, b in zip(original, refs()))
                 and self.consumer is consumer and self.sequence == public_sequence
                 and consumer.sequence == native_sequence and consumer.pending is None
                 and consumer._reservation is reservation
                 and (reservation is False or self._inventory_source_restart_reservation(generation, previous)
                      is restart_reservation and restart_reservation is not None)
                 and (not self.pending or reselecting and self._source_reselect_restoring()) and self._polling is True
                 and not self.closed and not self._resources_closed and self._prewrite_refusal is None
                 and self._inventory_request is None and self._inventory_wait is None
                 and consumer.state['status'] in ('READY', 'COMMITTED')
                 and self.last_result.get('status') != 'UNKNOWN'
                 and not generation.service._claimed and not broker._inventory_attempted
                 and not broker._inventory_write_attempted and broker._inventory_delivery_authority is None
                 and broker._inventory_current_frame is None and broker._inventory_update_operation is None,
                 'FEATURE_INVENTORY_GENERATION_CHANGED')
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        except BaseException:
            observer.close()
            raise
        self._inventory_observer.close()
        self._inventory_observer = observer
        self._inventory_previous_sample_ns = sampled
        self._inventory_generation = generation
        self._inventory_frame = self._inventory_client_binding = None
        self._inventory_update_frame = self._inventory_update_state = None
        self._inventory_auto_selection = None
        self._inventory_started_ns = self._inventory_clock_ns = (self._source_reselect_started_ns if reselecting else None)
        self._inventory_generation_monitor, self._inventory_generation_sample = monitor_ref, sample_floor
        return True

    def _claim_world_inventory(self, monitor):
        """Local trigger only; actual admission still rechecks world/Empty/source.

        Consume the existing monitor result without sampling. No new item is
        created here: only the select-time restored literal can be delivered.
        The broker's once claim is shared with explicit Add. Only the explicit
        reselection policy can provide a new actual generation after Restart.
        """
        reselecting = self._source_reselect_restoring()
        if (self.inventory_delivery_policy is None or self.pending and not reselecting or self.closed
                or self._inventory_auto_selection is not None):
            return
        broker = self.inventory_broker
        if self.inventory_reselection_policy is not None:
            generation = self._inventory_generation
            if generation is None or generation.phase != 'ACTIVE':
                return
            need(self._inventory_reselection_current(generation.writer) is generation,
                 'FEATURE_INVENTORY_GENERATION_CHANGED')
        if broker._inventory_attempted or broker._inventory_restored is not True:
            return
        from tools.local_original_session.observe import SessionMonitor
        if (type(monitor) is not SessionMonitor or monitor.reader is not self.consumer.reader
                or monitor.owner is not self.consumer.reader.owner):
            return
        if self.inventory_reselection_policy is not None:
            need(type(monitor.samples) is int and 0 <= monitor.samples,
                 'FEATURE_INVENTORY_RESELECTION_SAMPLE_REQUIRED')
            if self._inventory_generation_monitor is None:
                self._inventory_generation_monitor, self._inventory_generation_sample = monitor, monitor.samples
                return
            need(monitor is self._inventory_generation_monitor, 'FEATURE_INVENTORY_RESELECTION_MONITOR_CHANGED')
            if monitor.samples <= self._inventory_generation_sample:
                return
        binding = current_manual_binding(broker)
        if binding is None:
            return
        position = broker.realm.service(binding.writer).snapshot()
        scene, world = monitor.last_memory, monitor.last_world
        if not (scene.get('status') == 'OBSERVED' and scene.get('current') == 'Land'
                and scene.get('pending') == 'none' and scene.get('root_ready') is True
                and world.get('status') == 'OBSERVED' and world.get('stable_double_read') is True
                and world.get('scene') == 'Land' and world.get('pending') == 'none'
                and type(world.get('my_player_uid')) is int and world['my_player_uid'] == position.uid
                and type(world.get('map_requested_i32')) is int
                and type(world.get('map_resolved_i32')) is int
                and world['map_requested_i32'] == world['map_resolved_i32'] == position.map_id):
            return
        selected = broker._inventory_selection_binding
        need(selected is not None and selected[0] is binding.writer
             and selected[-1] is broker._inventory_frame,
             'FEATURE_INVENTORY_RESTORED_SELECTION_REQUIRED')
        from tools.local_original_session.commands import MAX_SEQUENCE
        need(type(self.sequence) is int and 0 <= self.sequence < MAX_SEQUENCE,
             'FEATURE_MANUAL_SEQUENCE_REQUIRED')
        self._inventory_auto_selection = selected
        if not reselecting:
            self.sequence += 1  # Share the existing public command sequence atomically.
            self._inventory_started_ns = self._inventory_clock_ns = time.monotonic_ns()
            self.pending, self._pending_command = True, 'AddInventory'
        else:
            self._source_reselect_now()
        self._inventory_request = dict(uid=position.uid, map_id=position.map_id)
        if not reselecting:
            self._record(dict(status='CLAIMED', invoked=False, command='AddInventory'))
        else:
            self._record(dict(self.last_result, status='PENDING', phase='INVENTORY_ADMISSION'))

    def _inventory_now(self):
        from tools.local_original_session.manual_move_commands import WAIT_NS
        now = time.monotonic_ns()
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        if self.closed:
            return self._inventory_unknown('FEATURE_INVENTORY_CLOSED')
        if (type(now) is not int or type(self._inventory_started_ns) is not int
                or type(self._inventory_clock_ns) is not int
                or not 0 <= self._inventory_started_ns <= self._inventory_clock_ns <= now < (1 << 63)):
            self._inventory_unknown('FEATURE_INVENTORY_CLOCK_UNKNOWN')
        self._inventory_clock_ns = now
        if now - self._inventory_started_ns >= WAIT_NS:
            if self._inventory_request is not None:
                # The broker proves the last real typed refusal is still safe to close.
                if self._pending_command != 'UpdateInventory':
                    self.inventory_broker._inventory_admission_time()
                self._inventory_unknown('FEATURE_INVENTORY_ADMISSION_DEADLINE')
            self._inventory_unknown('FEATURE_INVENTORY_CLIENT_DEADLINE')
        return now

    def _inventory_client_current(self):
        """Literal post-drain objects; observation never replaces delivery authority."""
        from tools.local_original_session import inventory, inventory_observe
        broker, observer, reader = self.inventory_broker, self._inventory_observer, self.consumer.reader
        if self._pending_command == 'SourceReselect':
            self._source_reselect_current()
        if self.inventory_reselection_policy is not None:
            need(self._inventory_reselection_current(self._inventory_wait) is self._inventory_generation,
                 'FEATURE_INVENTORY_GENERATION_CHANGED')
        cls, original_sample = self._inventory_observer_type, self._inventory_observer_sample
        sample = observer.sample
        need(inventory_observe.InventoryObserver is cls and cls.sample is original_sample
             and type(observer) is cls and type(sample) is MethodType
             and sample.__self__ is observer and sample.__func__ is original_sample
             and original_sample.__globals__.get('InventoryObserver') is cls
             and original_sample.__qualname__ == 'InventoryObserver.sample'
             and Path(original_sample.__code__.co_filename).resolve()
                 == Path(__file__).with_name('inventory_observe.py').resolve()
             and digest(Path(__file__).with_name('inventory_observe.py')) == _INVENTORY_OBSERVER_SOURCE_SHA,
             'FEATURE_INVENTORY_ACTUAL_OBSERVER_REQUIRED')
        authority = observer._authority
        delivery, service = broker._inventory_delivery_authority, broker._inventory_service
        updating = self._pending_command == 'UpdateInventory'
        current_frame = self._inventory_update_frame if updating else self._inventory_frame
        operation = self._inventory_update_state if updating else None
        if updating:
            need(operation is broker._inventory_update_operation and type(operation) is dict
                 and operation['phase'] == 'DRAINED' and operation['writer'] is self._inventory_wait
                 and operation['new'] is current_frame and broker._inventory_current_frame is current_frame
                 and operation['persisted'] is True and operation['write_attempted'] is True
                 and operation['drain_returned'] is True and operation['post_owner_verified'] is True,
                 'FEATURE_INVENTORY_UPDATE_DRAINED_FRAME_REQUIRED')
        need(type(authority) is inventory.InventoryService and authority.broker is broker
             and authority.reader is reader and authority._reader is reader
             and authority._backend is reader.backend and authority.proof.reader is reader
             and not observer._closed and not authority._closed and not reader.closed
             and service is not None and service.reader is reader and not service._closed
             and service._claimed and delivery is not None
             and broker._inventory_frame is self._inventory_frame
             and broker._inventory_operation_frame is self._inventory_frame,
             'FEATURE_INVENTORY_CLIENT_LIFETIME_CHANGED')
        binding = current_manual_binding(broker)
        need(binding is not None and binding.writer is self._inventory_wait,
             'FEATURE_INVENTORY_CLIENT_SELECTION_CHANGED')
        identities = delivery[1]
        realm, registry, game, movement, position, selected, row, admitted = identities[10:18]
        if updating:
            position = movement.snapshot()
            need((position.uid, position.name, position.map_id)
                 == (delivery[0].uid, delivery[0].name, delivery[0].map_id),
                 'FEATURE_INVENTORY_UPDATE_SELECTED_IDENTITY_CHANGED')
            from tools.local_original_session.inventory_store import InventoryStore
            store = broker._inventory_store
            restore = None if store is None else store.restore
            need(type(store) is InventoryStore and service._persistence_store() is store
                 and getattr(restore, '__self__', None) is store
                 and getattr(restore, '__func__', None) is InventoryStore.restore,
                 'FEATURE_INVENTORY_UPDATE_ORIGINAL_STORE_REQUIRED')
            need(restore(position.uid) == current_frame, 'FEATURE_INVENTORY_UPDATE_STORED_FRAME_CHANGED')
            need(broker._inventory_store is store and service._persistence_store() is store
                 and broker._inventory_update_operation is operation
                 and self._inventory_update_state is operation
                 and broker._inventory_current_frame is self._inventory_update_frame is current_frame
                 and operation['phase'] == 'DRAINED' and operation['new'] is current_frame
                 and broker._inventory_service is service and not service._closed,
                 'FEATURE_INVENTORY_UPDATE_CLIENT_LIFETIME_CHANGED')
        need(identities[0] is broker and identities[1] is reader
             and identities[2] is reader.backend and identities[3] is reader.owner
             and identities[4] is reader.member and identities[5] is broker.policy
             and broker.realm is realm and realm.registry is registry
             and registry.resolve(binding.writer) is game and realm.service(binding.writer) is movement
             and movement.snapshot() is position and game.selection is selected
             and registry.selected.get(position.name) is selected
             and row['writer'] is binding.writer and row['policy_row'] is admitted
             and row['operation_lock'] is identities[18] and row['peer'] is identities[19]
             and not reader.owner.closed and reader.owner.child is reader.member
             and broker.policy.owner is reader.owner
             and reader.member.process == broker.policy.handle
             and reader.member.job == broker.policy.job
             and all(type(a) is type(b) and a == b for a, b in zip(
                 (broker.policy.handle, broker.policy.job, reader.owner.owner_handle, reader.owner.owner_job),
                 identities[6:10]))
             and delivery[2] == (tuple(sorted(row['peer'].items())), reader.backend.handle,
                 reader.member.pid, tuple(sorted(reader.member.identity.items()))),
             'FEATURE_INVENTORY_CLIENT_AUTHORITY_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return (broker, observer, authority, reader, reader.backend, reader.owner, reader.member,
                service, delivery, self._inventory_frame, self._inventory_wait, sample.__func__,
                *((current_frame, position, operation) if updating else ()))

    def _inventory_client_same(self, original):
        current = self._inventory_client_current()
        need(len(current) == len(original) and all(a is b for a, b in zip(current, original)),
             'FEATURE_INVENTORY_CLIENT_BINDING_CHANGED')

    async def _poll_inventory(self):
        from tools.local_original_session import inventory, inventory_observe
        now = self._inventory_now()
        # Even direct callers share the last actual pre-write/observer slot.
        sampled = self.last_sample_monotonic_ns
        if sampled is not None and now - sampled < inventory.MIN_INTERVAL_NS:
            return dict(self.last_result)
        original = self._inventory_client_binding
        need(original is not None, 'FEATURE_INVENTORY_CLIENT_BINDING_REQUIRED')
        self._inventory_client_same(original)
        observer, writer = self._inventory_observer, self._inventory_wait
        sample = observer.sample
        observed = await sample(writer, now_ns=now)
        self._inventory_now()  # Check the original deadline after the owner-check await too.
        self._inventory_client_same(original)
        need(observed is observer.last_result and type(observed) is dict,
             'FEATURE_INVENTORY_ACTUAL_OBSERVATION_REQUIRED')
        if observed['status'] != 'OBSERVED':
            marker = observed.get('read_consistency')
            if (type(observed.get('status')) is str and observed['status'] == 'UNKNOWN'
                    and type(observed.get('reason')) is str and observed['reason'] == 'EDGE_TYPED_READ_CHANGED'
                    and type(marker) is str and marker in _INVENTORY_INCOMPLETE_READS
                    and observed.get('source_owner_revalidated') is True
                    and observed.get('source_contract_valid') is False
                    and observed.get('stable_double_read') is False
                    and observed.get('snapshot_atomic') is False
                    and observed.get('selected_uid') is None and observed.get('map_id') is None
                    and observed.get('entry_count') is None and observed.get('empty') is None
                    and type(observed.get('rows')) is list and observed['rows'] == []
                    and type(observed.get('typed_bytes_requested')) is int
                    and 0 < observed['typed_bytes_requested'] <= inventory_observe.BYTE_LIMIT
                    and type(observed.get('query_started_monotonic_ns')) is int
                    and now <= observed['query_started_monotonic_ns'] <= self._inventory_clock_ns
                    and observed['query_started_monotonic_ns'] == observer.last_sample_monotonic_ns):
                # The actual query finished its source/owner/type rechecks but
                # supplied no strict item snapshot. Keep the same claim/clock.
                return self._record(dict(self.last_result, status='PENDING', phase='CLIENT_WAIT',
                    reason=observed['reason'], read_consistency=marker,
                    source_owner_revalidated=True, source_contract_valid=False,
                    stable_double_read=False, snapshot_atomic=False))
            return self._inventory_unknown(observed['reason'] or 'FEATURE_INVENTORY_CLIENT_UNKNOWN')
        if observed['empty'] is True:
            if observed['reason'] is not None:
                return self._inventory_unknown(observed['reason'])
            return dict(self.last_result)
        updating = self._pending_command == 'UpdateInventory'
        frame = self._inventory_update_frame if updating else self._inventory_frame
        fields = dict(inventory.validate_frame(frame).raw_fields)
        expected = dict(id_u64=fields[1], template_id_u32=fields[2] & 0xffffffff,
            field18_u64=fields[3], field28_i64=fields[4] - (1 << 64) if fields[4] >= 1 << 63 else fields[4],
            field30_bool=fields[24])
        if observed['entry_count'] != 1 or observed['rows'] != [expected]:
            if updating:
                previous_fields = dict(inventory.validate_frame(self._inventory_update_state['old']).raw_fields)
                previous = dict(expected, field28_i64=(previous_fields[4] - (1 << 64)
                    if previous_fields[4] >= 1 << 63 else previous_fields[4]))
                if (observed['reason'] == 'INVENTORY_OBSERVE_PREVIOUS_FIELD4_PENDING'
                        and self._inventory_update_state['changes'] == ((4, fields[4]),)
                        and {k for k in fields if fields[k] != previous_fields[k]} == {4}
                        and previous['field28_i64'] != expected['field28_i64']
                        and observed['source_contract_valid'] is True
                        and observed['stable_double_read'] is True
                        and observed['source_owner_revalidated'] is True
                        and observed['read_consistency'] == 'STRICT_STABLE'
                        and observed['entry_count'] == 1 and observed['rows'] == [previous]):
                    return self._record(dict(self.last_result, status='PENDING', phase='CLIENT_WAIT',
                        reason=observed['reason']))
            return self._inventory_unknown('FEATURE_INVENTORY_CLIENT_ITEM_MISMATCH')
        if observed['reason'] is not None:
            return self._inventory_unknown(observed['reason'])
        self._inventory_now()
        if updating:
            result = self._consume(dict(status='COMMITTED', command='UpdateInventory', invoked=True,
                phase='CLIENT_CONFIRMED', native_attempted=False, automatic_retry=False, cleanup_required=False,
                proof_scope='CLIENT_ITEM_FIELD4_MATCHED',
                storage='LOCAL_OPAQUE_FRAME_REPLACED', client_inventory='ROW_5_SCALARS_MATCHED',
                transport_proof_scope='TRANSPORT_DRAIN_ONLY', ack='UNKNOWN', effect='UNKNOWN', hp='UNKNOWN',
                equipped='UNKNOWN', render='UNKNOWN', save='UNKNOWN'))
        else:
            result = self._consume(dict(status='COMMITTED', command='AddInventory', invoked=True,
            phase='CLIENT_CONFIRMED', proof_scope='CLIENT_ITEM_ROW_SCALARS_ONLY',
            client_inventory='ROW_5_SCALARS_MATCHED', transport_proof_scope='TRANSPORT_DRAIN_ONLY',
            render='UNKNOWN', equipped='UNKNOWN', save='UNKNOWN', all_17_wire_fields_proven=False,
            wire_field18_bytes_observed=False, catalog_live_materialization_proven=False))
        self.pending = False
        self._pending_command = None
        self._inventory_wait = None
        return result

    def poll(self):
        if self.closed:
            return dict(self.last_result)
        need(not self._polling, 'FEATURE_COMMAND_POLL_INFLIGHT')
        if self._inventory_request is not None or self._inventory_wait is not None:
            return dict(self.last_result)
        try:
            return self._receive(self.consumer.poll())
        except Exception:
            self.close()
            raise

    async def poll_async(self, *, monitor=None):
        if self.closed:
            return dict(self.last_result)
        need(not self._polling, 'FEATURE_COMMAND_POLL_INFLIGHT')
        self._polling = True
        menu_waiting = self._source_restart_menu is not None
        update_called, update_previous_operation = False, None
        diagnostic_binding = (self._inventory_diagnostic_capture()
                              if self._inventory_request is not None and self._pending_command != 'UpdateInventory' else None)
        try:
            if self._source_restart_menu_wait():
                return dict(self.last_result)
            if self._pending_command == 'SourceReselect' and self.pending:
                if self._source_reselect_native_state is None:
                    consumer = self._actual_manual_producer(asynchronous=True)
                    need(consumer is self.consumer and consumer is not None,
                         'FEATURE_SOURCE_RESELECT_ACTUAL_PRODUCER_REQUIRED')
                    self._source_reselect_now()
                    result = await consumer.poll_async()
                    need(self._actual_manual_producer(asynchronous=True) is consumer,
                         'FEATURE_SOURCE_RESELECT_PRODUCER_CHANGED')
                    self._source_reselect_now()
                    return self._receive(result, asynchronous=True)
                self._source_reselect_current()
                if self._inventory_request is None and self._inventory_wait is None:
                    self._source_reselect_now()
            elif self._source_reselect_can_receive():
                return self._receive(await self.consumer.poll_async(), asynchronous=True)
            if self.inventory_reselection_policy is not None and self._source_restart_handoff():
                return self._receive(await self.consumer.poll_async(), asynchronous=True)
            if self._refresh_inventory_selection(monitor) is False:
                return dict(self.last_result)
            if self._inventory_wait is not None:
                return await self._poll_inventory()
            result = dict(self.last_result)
            if self._inventory_request is None:
                if not self._source_reselect_restoring():
                    result = self._receive(await self.consumer.poll_async(), asynchronous=True)
                self._claim_world_inventory(monitor)
            if self._inventory_request is not None:
                from tools.local_original_session import inventory
                from tools.local_original_session.manual_move_commands import WAIT_NS
                now = self._inventory_now()
                sampled = self.last_sample_monotonic_ns
                if sampled is not None and now - sampled < inventory.MIN_INTERVAL_NS:
                    return dict(self.last_result)
                request = self._inventory_request
                if self._inventory_auto_selection is not None:
                    need(self.inventory_broker._inventory_selection_binding is self._inventory_auto_selection
                         and self.inventory_broker._inventory_restored is True,
                         'FEATURE_INVENTORY_RESTORED_SELECTION_CHANGED')
                binding = current_manual_binding(self.inventory_broker)
                need(binding is not None, 'FEATURE_INVENTORY_CURRENT_SELECTION_REQUIRED')
                position = self.inventory_broker.realm.service(binding.writer).snapshot()
                need(type(request['uid']) is int and type(request['map_id']) is int
                     and request['uid'] == position.uid and request['map_id'] == position.map_id,
                     'FEATURE_INVENTORY_CURRENT_UID_MAP_REQUIRED')
                if (self._inventory_frame is None and self.inventory_broker._inventory_store is not None
                        and not self.inventory_broker._inventory_attempted):
                    self._inventory_frame = self.inventory_broker._inventory_frame
                if request.get('command') == 'UpdateInventory' and self._inventory_frame is None:
                    self._inventory_frame = self.inventory_broker._inventory_frame
                need(self.inventory_broker._inventory_frame is self._inventory_frame,
                     'FEATURE_INVENTORY_CANONICAL_FRAME_CHANGED')
                options = dict(deadline_ns=self._inventory_started_ns + WAIT_NS)
                if self.inventory_reselection_policy is not None and request.get('command') != 'UpdateInventory':
                    generation = self._inventory_reselection_current(binding.writer)
                    need(generation is self._inventory_generation and generation is not None
                         and generation.restored is True and generation.selection_binding is not None
                         and generation.selection_binding[-1] is self._inventory_frame,
                         'FEATURE_INVENTORY_RESELECTION_SAVED_ROW_REQUIRED')
                    options['restore_only'] = True
                elif self._inventory_auto_selection is not None:
                    options['restore_only'] = True
                diagnostic_binding = (self._inventory_diagnostic_capture()
                                      if request.get('command') != 'UpdateInventory' else None)
                if request.get('command') == 'UpdateInventory':
                    update_previous_operation = self.inventory_broker._inventory_update_operation
                    update_called = True
                    transport = await self.inventory_broker.update_inventory(binding.writer,
                        item_identifier=request['item_identifier'], changes={4: request['field4_u64']},
                        policy=self.inventory_broker.inventory_update_policy, **options)
                    self._inventory_update_frame = self.inventory_broker._inventory_current_frame
                    self._inventory_update_state = self.inventory_broker._inventory_update_operation
                else:
                    transport = await self.inventory_broker.add_inventory(binding.writer, **options)
                if transport['status'] == 'PENDING':
                    self._inventory_now()
                    return self._consume(transport)
                self._inventory_request = None
                self._inventory_wait = binding.writer
                self._inventory_now()
                self._inventory_client_binding = self._inventory_client_current()
                result = self._consume(dict(transport, status='PENDING', phase='CLIENT_WAIT'))
            return result
        except BaseException as error:
            from tools.local_original_session.inventory import PreWriteReadRefusal, ReadOnlyPreWriteRefusal
            if type(error) in (PreWriteReadRefusal, ReadOnlyPreWriteRefusal) and self.inventory_broker is not None:
                try:
                    self.inventory_broker._inventory_refusal_current(error)
                except BaseException:
                    self.close()
                    raise
                self._prewrite_refusal = error
                self.closed = True  # Ingress stops; native ownership is not cancelled.
                row = dict(status='UNKNOWN', command='AddInventory', phase='PRE_WRITE',
                    reason=('FEATURE_INVENTORY_ADMISSION_DEADLINE'
                            if self.inventory_broker._inventory_admission_expired else error.reason),
                    refusal_reason=error.reason, stage=error.stage, write_attempted=False, invoked=False, cleanup_required=True,
                    client_inventory='UNKNOWN', automatic_retry=False)
                if self.inventory_broker._inventory_admission_expired is True:
                    diagnostic = self._inventory_pre_write_diagnostic(error, diagnostic_binding,
                        refusal=self.inventory_broker._inventory_prewrite_refusal)
                    if diagnostic is not None:
                        row['inventory_pre_write'] = diagnostic
                self._record(row)
            else:
                if menu_waiting and self.last_result.get('status') != 'UNKNOWN':
                    self._source_restart_menu_failed(error)
                if (self._inventory_request is not None
                        and not (self._pending_command == 'UpdateInventory'
                                 and self.last_result.get('status') == 'UNKNOWN')):
                    operation = self.inventory_broker._inventory_update_operation
                    attempted = (update_called and operation is not None and operation is not update_previous_operation
                        and operation['write_attempted'] is True
                        if self._pending_command == 'UpdateInventory'
                        else self.inventory_broker._inventory_write_attempted)
                    row = dict(status='UNKNOWN', command=self._pending_command or 'AddInventory', phase='ADMISSION',
                        reason=safe_error_code(error) or 'FEATURE_INVENTORY_ADMISSION_UNKNOWN',
                        write_attempted=attempted, invoked=attempted,
                        cleanup_required=True, client_inventory='UNKNOWN')
                    diagnostic = self._inventory_pre_write_diagnostic(error, diagnostic_binding)
                    if diagnostic is not None:
                        row['inventory_pre_write'] = diagnostic
                    self._record(row)
                elif self._inventory_wait is not None and self.last_result.get('status') != 'UNKNOWN':
                    self._record(dict(status='UNKNOWN', command=self._pending_command or 'AddInventory', phase='CLIENT_WAIT',
                        reason=safe_error_code(error) or 'FEATURE_INVENTORY_CLIENT_UNKNOWN',
                        invoked=True, cleanup_required=True, proof_scope='TRANSPORT_DRAIN_ONLY',
                        client_inventory='UNKNOWN', render='UNKNOWN', equipped='UNKNOWN', save='UNKNOWN'))
                elif (self.pending and self._pending_command == 'SourceReselect'
                      and self.last_result.get('status') != 'UNKNOWN'):
                    producer = self._actual_manual_producer(asynchronous=True)
                    state = producer.state if producer is not None else self.last_result
                    completed = self._actual_source_reselect_commit(state, asynchronous=True)
                    self._record(dict(status='UNKNOWN', command='SourceReselect',
                        phase='INVENTORY_RESTORE' if completed else state.get('phase', 'ADMISSION'),
                        reason=safe_error_code(error) or 'FEATURE_SOURCE_RESELECT_UNKNOWN',
                        native_attempted=state.get('native_attempted') is True,
                        cleanup_required=True, client_inventory='UNKNOWN', proof_scope='UNKNOWN',
                        selection_proof_scope='LOCAL_RESELECT_LAND_READY_ONLY' if completed else 'UNKNOWN',
                        inventory_restore='UNKNOWN', ui='UNKNOWN'))
                self.close()
            raise
        finally:
            self._polling = False

    def quiesce_for_source_quit(self):
        """Hand off this actual native slot; never recover an unknown native result."""
        if (self._polling or self._resources_closed or self.consumer.pending is not None
                or self.consumer.state['status'] not in ('READY', 'COMMITTED')):
            return False
        if self._prewrite_refusal is not None:
            try:
                self.inventory_broker._inventory_refusal_current(self._prewrite_refusal)
            except Exception:
                return False
        elif self.last_result.get('status') == 'NOT_REQUESTED':
            if (self.consumer.state['status'] != 'READY' or self.consumer.sequence != 0
                    or self.consumer._reservation or self.pending
                    or self._inventory_request is not None or self._inventory_wait is not None):
                return False
        elif self.last_result.get('status') != 'COMMITTED' or self.pending:
            return False
        self.closed, self.pending = True, False
        self._inventory_request = self._inventory_wait = None
        return True

    def close(self):
        self.closed = True
        if not self._resources_closed:
            self._resources_closed = True
            try:
                self.consumer.close()
            finally:
                if self._inventory_observer is not None:
                    self._inventory_observer.close()
                if self.inventory_broker is not None:
                    self.inventory_broker._inventory_service.close()


class ProductFeatureFactory:
    """Wire opt-in consumers into the launcher's actual retained lifetime."""
    def __init__(self, reader, *, product, control_mode, directory, config):
        self.reader, self.directory = reader, directory
        self.config, self.product = config, product
        self.manual = PRODUCTS[product].get('continuous_manual_move') is True
        self.inventory = config.inventory_policy is not None or config.inventory_frame is not None
        if self.inventory:
            from tools.local_original_session import inventory
            need(config.inventory_policy == inventory.POLICY and type(config.inventory_frame) is bytes,
                 'FEATURE_EXPLICIT_INVENTORY_CONFIG_REQUIRED')
        from tools.local_original_session.feature_config import LOCAL_WORLD_READY_ONCE
        need(config.inventory_delivery_policy is None or self.inventory
             and config.inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
             and config.inventory_store_policy is not None,
             'FEATURE_EXPLICIT_STORED_INVENTORY_DELIVERY_POLICY_REQUIRED')
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION
        self.inventory_reselection_policy = config.inventory_reselection_policy
        if self.inventory_reselection_policy is not None:
            from tools.local_original_session import inventory_store, restart
            need(type(self.inventory_reselection_policy) is str
                 and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
                 and self.inventory and config.inventory_store_policy == inventory_store.POLICY
                 and config.inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
                 and config.restart_policy == restart.POLICY,
                 'FEATURE_EXPLICIT_STORED_INVENTORY_RESELECTION_POLICY_REQUIRED')
        need(not self.inventory or control_mode == 'manual', 'MANUAL_CONTROL_MODE_REQUIRED')
        from tools.local_original_session.feature_config import ATTACK_INTENT_POLICY
        self.allow_attack = (PRODUCTS[product].get('continuous_manual_attack') is True
                             and config.attack_policy == ATTACK_INTENT_POLICY)
        self.allow_attack_replacement = (PRODUCTS[product].get('manual_attack_move_replacement') is True
                                         and self.allow_attack)
        self.allow_use_item = False
        if PRODUCTS[product].get('manual_use_item') is True and config.item_use_policy is not None:
            from tools.local_original_session.item_use_session import POLICY
            self.allow_use_item = type(config.item_use_policy) is str and config.item_use_policy == POLICY
        from tools.local_original_session.restart import POLICY as RESTART_POLICY
        self.allow_source_restart = (PRODUCTS[product].get('manual_source_restart') is True
            and type(config.restart_policy) is str and config.restart_policy == RESTART_POLICY)
        self.allow_source_reselect = (PRODUCTS[product].get('manual_source_reselect') is True
            and self.allow_source_restart and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION)
        need(not self.manual or control_mode == 'manual', 'MANUAL_CONTROL_MODE_REQUIRED')
        from tools.local_original_session.broker import INVENTORY_UPDATE_POLICY
        self.allow_inventory_update = (PRODUCTS[product].get('manual_inventory_update') is True
            and type(config.inventory_update_policy) is str
            and config.inventory_update_policy == INVENTORY_UPDATE_POLICY)
        self.npc_factory = None
        if config.interval_ns is not None:
            from tools.local_original_session.npc_session import NpcSessionConfig, NpcSessionFactory
            self.npc_factory = NpcSessionFactory(reader, config=NpcSessionConfig(
                spawns=config.spawns, interval_ns=config.interval_ns,
                policy=config.motion_policy, goal_policy=config.goal_policy))

    @property
    def enabled(self):
        return self.manual or self.inventory or self.npc_factory is not None

    def broker_options(self):
        if self.npc_factory is not None:
            options = self.npc_factory.broker_options()
        else:
            options = dict(npc_spawns=self.config.spawns) if self.config.spawns else {}
        if self.config.attack_policy is not None:
            need(bool(self.config.spawns), 'FEATURE_ATTACK_REQUIRES_NPC')
            options.update(attack_policy=self.config.attack_policy, attack_reader=self.reader,
                           attack_feedback=self.config.attack_feedback)
        if self.config.restart_policy is not None:
            options.update(restart_policy=self.config.restart_policy)
        if self.config.item_use_policy is not None:
            options.update(item_use_policy=self.config.item_use_policy)
        if self.config.inventory_update_policy is not None:
            options.update(inventory_update_policy=self.config.inventory_update_policy)
        if self.inventory_reselection_policy is not None:
            options.update(inventory_reselection_policy=self.inventory_reselection_policy,
                           inventory_delivery_policy=self.config.inventory_delivery_policy)
        if self.inventory:
            options.update(inventory_policy=self.config.inventory_policy,
                           inventory_frame=self.config.inventory_frame, inventory_reader=self.reader,
                           inventory_store_policy=self.config.inventory_store_policy)
        return options

    def __call__(self, broker):
        manual = npc_session = None
        try:
            if self.manual or self.inventory:
                from tools.local_original_session.manual_move_commands import ManualMoveCommands
                use_item_options = dict(allow_use_item=True) if self.allow_use_item else {}
                source_restart_options = dict(allow_source_restart=True) if self.allow_source_restart else {}
                source_reselect_options = dict(allow_source_reselect=True) if self.allow_source_reselect else {}
                manual = ManualMoveRequests(self.directory, ManualMoveCommands(
                    self.reader, current=lambda: current_manual_binding(broker),
                    allow_attack=self.allow_attack, allow_attack_replacement=self.allow_attack_replacement,
                    observe_attack_feedback=(self.config.attack_feedback is not None
                        and broker._attack_session is not None
                        and broker._attack_session.feedback is self.config.attack_feedback),
                    **dict(use_item_options, **source_restart_options, **source_reselect_options)),
                    allow_attack=self.allow_attack,
                    allow_move=self.manual, inventory_broker=broker if self.inventory else None,
                    inventory_delivery_policy=self.config.inventory_delivery_policy,
                    **dict(use_item_options, **source_restart_options, **source_reselect_options,
                        **(dict(allow_inventory_update=True) if self.allow_inventory_update else {}),
                        **(dict(inventory_reselection_policy=self.inventory_reselection_policy)
                           if self.inventory_reselection_policy is not None else {})))
            if self.npc_factory is not None:
                npc_session = self.npc_factory.bind(broker)
                if self.config.goal is not None:
                    npc_session.submit_goal(goal=self.config.goal)
            return ProductFeatures(manual, npc_session)
        except BaseException:
            if manual is not None:
                manual.close()
            if npc_session is not None:
                npc_session.close()
            raise


class ProductFeatures:
    def __init__(self, manual, npc_session):
        self.manual, self.npc_session = manual, npc_session

    async def poll(self, monitor=None):
        result = {}
        if self.manual is not None:
            if monitor is None or time.monotonic() >= monitor.next_memory:
                before = self.manual.last_sample_monotonic_ns
                try:
                    result['manual_move'] = await self.manual.poll_async(monitor=monitor)
                finally:
                    sampled = self.manual.last_sample_monotonic_ns
                    if monitor is not None and sampled is not None and sampled != before:
                        monitor.next_memory = sampled / 1e9 + .5
            else:
                result['manual_move'] = dict(self.manual.last_result)
        if self.npc_session is not None:
            outcome = await self.npc_session.tick(now_ns=time.monotonic_ns())
            result['npc'] = dict(status=outcome.status, reason=outcome.reason)
        return result

    def close(self):
        try:
            if self.manual is not None:
                self.manual.close()
        finally:
            if self.npc_session is not None:
                self.npc_session.close()


async def run_session(owner, broker_factory, stop, *, stop_requested=lambda: False,
                      poll_seconds=.1, close_grace_seconds=10, test_duration=None,
                      monitor=None, until_scene=None, input_requests=None, command_requests=None,
                      feature_factory=None, source_quit_directory=None):
    """One asyncio loop; product lifetime has no observation timeout."""
    need(input_requests is None or command_requests is None, 'EXCLUSIVE_SESSION_CONTROL_REQUIRED')
    report = dict(schema='local-original-session-v1', reason='STARTING', cleanup=None,
                  product_lifetime_seconds=None, normal_input_only=True,
                  normal_exit_verified=False, game_logout_protocol='UNVERIFIED')
    from tools.local_original_session.commands import ResultPublicationFailure
    broker = None
    features = None
    source_quit = None
    input_enabled = input_requests is not None
    command_enabled = command_requests is not None
    if command_enabled:
        report.update(normal_input_only=False, control_mode='INTERNAL')
        report['commands'] = dict(status='NOT_REQUESTED', invoked=False,
                                  native_ui_thread_conditional=False, ui_result='UNKNOWN', automatic_retry=False)
    if input_enabled:
        report['input'] = dict(status='NOT_REQUESTED', ui_result='UNKNOWN',
                               automatic_retry=False, disabled=False)

    def poll_input():
        nonlocal input_enabled
        if not input_enabled:
            return
        try:
            row = input_requests.poll()
            if row is not None:
                need(type(row) is dict and row.get('status') in ('POSTED', 'PARTIAL', 'REFUSED'),
                     'INPUT_RESULT_UNKNOWN')
                summary = dict(status=row['status'], ui_result='UNKNOWN', automatic_retry=False,
                               disabled=getattr(input_requests, 'disabled', False) is True)
                sequence = row.get('sequence')
                if type(sequence) is int and 1 <= sequence <= (1 << 53) - 1:
                    summary['sequence'] = sequence
                report['input'] = summary
                if summary['disabled']:
                    input_enabled = False
        except Exception as error:
            input_enabled = False
            report['input'] = dict(status='DISABLED', error_type=type(error).__name__,
                                   ui_result='UNKNOWN', automatic_retry=False, disabled=True)

    def command_result(row):
        if row is not None:
            need(type(row) is dict and row.get('status') in ('QUEUED', 'RETURNED', 'REFUSED', 'UNSUPPORTED'),
                 'COMMAND_RESULT_UNKNOWN')
            summary = dict(status=row['status'], invoked=row.get('invoked') is True,
                           native_ui_thread_conditional=row.get('native_ui_thread_conditional') is True,
                           ui_result='UNKNOWN', automatic_retry=False)
            for key, maximum in (('sequence', 2147483647), ('native_reason', 9)):
                if type(row.get(key)) is int and 0 <= row[key] <= maximum:
                    summary[key] = row[key]
            report['commands'] = summary

    def health_failure(error):
        nonlocal command_enabled
        command_enabled = False
        report.update(reason='NATIVE_GUARD_INTEGRITY_FAILURE',
            native_guard_health=dict(status='FAILED', reason=safe_error_code(error)
                                     or 'COMMAND_INTEGRITY_HEALTH_UNKNOWN'))

    def poll_control():
        nonlocal command_enabled
        if command_requests is None:
            poll_input()
        elif command_enabled:
            try:
                command_result(command_requests.poll())
            except ResultPublicationFailure as error:
                publication_failure(error)
            except Exception as error:
                command_enabled = False
                if (getattr(owner, 'require_lifecycle_health', False) is True
                        and (safe_error_code(error) or '').startswith('COMMAND_INTEGRITY_')):
                    health_failure(error)
                    return
                report['commands'] = dict(status='DISABLED', error_type=type(error).__name__,
                                           invoked=False, native_ui_thread_conditional=False,
                                           ui_result='UNKNOWN', automatic_retry=False)

    def publication_failure(error):
        nonlocal command_enabled
        command_enabled = False
        report.update(reason='NATIVE_COMMAND_RESULT_UNKNOWN', commands=dict(
            status='UNKNOWN', invoked=None, invocation_uncertain=True,
            reason=safe_error_code(error) or 'COMMAND_RESULT_PUBLICATION_UNKNOWN',
            native_ui_thread_conditional=False, ui_result='UNKNOWN', automatic_retry=False))

    def health_ready():
        nonlocal command_enabled
        try:
            check_wait = getattr(command_requests, 'check_result_wait', None)
            if check_wait is not None:
                check_wait()
        except ResultPublicationFailure as error:
            publication_failure(error)
            return False
        if getattr(owner, 'require_lifecycle_health', False) is not True:
            return True
        try:
            need(command_requests is not None, 'COMMAND_INTEGRITY_HANDLER_REQUIRED')
            row = command_requests.checked_health()
            need(type(row) is dict and row.get('status') in ('WAIT', 'VERIFIED'),
                 'COMMAND_INTEGRITY_HEALTH_UNKNOWN')
            report['native_guard_health'] = row
            return row['status'] == 'VERIFIED'
        except Exception as error:
            health_failure(error)
            return False

    primary_resumed = False

    def session_failure_close_allowed():
        """Feature failure may still use normal close on this exact live owner."""
        result = report['session_failure_close'] = dict(attempted=False, refusal_reason=None)
        try:
            need(primary_resumed, 'SESSION_PRIMARY_NOT_RESUMED')
            need(not broker.failure.is_set(), 'SESSION_CLOSE_BROKER_ALREADY_FAILED')
            child, handle, job = owner.child, owner.owner_handle, owner.owner_job
            need(child is not None and not owner.closed and handle and job
                 and child.process == handle and child.job == job
                 and child.members.get(child.pid) is child, 'SESSION_CLOSE_CURRENT_PRIMARY_REQUIRED')
            owner.verify_sources()
            need(owner.key_guard() is True and owner.validate(child) is True,
                 'SESSION_CLOSE_CURRENT_PRIMARY_REQUIRED')
            need(owner.child is child and not owner.closed and owner.owner_handle == handle
                 and owner.owner_job == job and child.process == handle and child.job == job
                 and child.members.get(child.pid) is child and not broker.failure.is_set(),
                 'SESSION_CLOSE_PRIMARY_CHANGED')
            return True
        except Exception as error:
            result['refusal_reason'] = safe_error_code(error) or 'SESSION_CLOSE_SOURCE_OWNER_UNKNOWN'
            result['error_type'] = type(error).__name__
            return False

    started = time.monotonic()
    try:
        report['primary'] = owner.prepare()
        if monitor is not None:
            monitor.bind(owner)
        broker = broker_factory(owner)
        await broker.start()
        if feature_factory is not None:
            features = feature_factory(broker)
            if getattr(features, 'manual', None) is not None:
                report['normal_input_only'] = False
        if source_quit_directory is not None:
            from tools.local_original_session.manual_source_quit import SourceQuitRequests
            need(features is not None and features.manual is not None, 'SOURCE_QUIT_FEATURES_REQUIRED')
            source_quit = SourceQuitRequests(owner, features.manual, broker, source_quit_directory)
            report['source_quit'] = source_quit.report()
        owner.resume()
        primary_resumed = True
        await asyncio.sleep(0)  # Immediate accept/KEY tasks get the first loop turn.
        report['reason'] = 'RUNNING'
        while True:
            if not owner.tick():
                report['reason'] = 'NATIVE_EXIT'
                if monitor is not None:
                    monitor.tick(broker, state='NATIVE_EXIT', force=True)
                break
            if broker.failure.is_set():
                report['reason'] = 'BROKER_FAILURE'
                if monitor is not None:
                    monitor.tick(broker, state='BROKER_FAILURE', force=True)
                break
            integrity_ready = health_ready()
            if report['reason'] in ('NATIVE_GUARD_INTEGRITY_FAILURE', 'NATIVE_COMMAND_RESULT_UNKNOWN'):
                break
            if features is not None and not broker.failure.is_set():
                if stop.is_set() or stop_requested():
                    report['reason'] = 'USER_CLOSE'
                    break
                report['features'] = await features.poll(monitor)
            if monitor is not None:
                observed = monitor.tick(broker)
                if integrity_ready and not broker.failure.is_set():
                    poll_control()
                if report['reason'] in ('NATIVE_GUARD_INTEGRITY_FAILURE', 'NATIVE_COMMAND_RESULT_UNKNOWN'):
                    break
                scene = (observed or {}).get('memory', {}).get('scene', {})
                if (until_scene is not None and scene.get('status') == 'OBSERVED'
                        and scene.get('current') == until_scene and scene.get('pending') == 'none'
                        and scene.get('root_ready') is True):
                    report.update(reason='OBSERVATION_CONDITION', observation_condition=dict(scene=until_scene))
                    break
            if stop.is_set() or stop_requested():
                report['reason'] = 'USER_CLOSE'
                break
            if test_duration is not None and time.monotonic() - started >= test_duration:
                report['reason'] = 'TEST_DURATION'
                break
            await asyncio.sleep(poll_seconds)
    except asyncio.CancelledError:
        report['reason'] = 'USER_INTERRUPT'
    except Exception as error:
        report.update(reason='SESSION_FAILURE', error_type=type(error).__name__,
                      error=str(error)[:160])
        if features is not None and getattr(features, 'manual', None) is not None:
            manual = features.manual
            if getattr(manual, '_prewrite_refusal', None) is error:
                report['inventory_pre_write_refusal'] = dict(manual.last_result)
                report['features'] = dict(manual_move=dict(manual.last_result))
    finally:
        failed_session = report['reason'] == 'SESSION_FAILURE'
        # Leave transport and its resource slots available for native close
        # traffic. The grace is a shutdown bound, never a product lifetime.
        try:
            if broker is not None:
                try:
                    if features is not None and source_quit is None:
                        features.close()
                    recover_failure = failed_session and session_failure_close_allowed()
                    if recover_failure or report['reason'] in ('USER_CLOSE', 'USER_INTERRUPT',
                                                              'TEST_DURATION', 'OBSERVATION_CONDITION'):
                        if recover_failure:
                            report['session_failure_close']['attempted'] = True
                            report['close_via'] = 'OWNED_WINDOW_CLOSE'
                            report['close_windows_requested'] = owner.request_close()
                        elif command_requests is not None:
                            report['close_windows_requested'] = 0
                            report['close_via'] = 'INTERNAL_QUIT'
                            if command_enabled:
                                command_result(command_requests.request_quit())
                        else:
                            report['close_windows_requested'] = owner.request_close()
                        deadline = time.monotonic() + close_grace_seconds
                        if source_quit is not None:
                            report['close_via'] = 'OWNED_WINDOW_CLOSE_THEN_SOURCE_QUIT'
                            report['source_quit'] = source_quit.start(report['close_windows_requested'])
                        report['close_wait_end'] = 'GRACE_EXPIRED'
                        while time.monotonic() < deadline:
                            if not owner.tick():
                                report['close_wait_end'] = 'NATIVE_EXIT'
                                break
                            if broker.failure.is_set():
                                report['close_wait_end'] = 'BROKER_FAILURE'
                                break
                            if source_quit is not None:
                                report['source_quit'] = source_quit.poll()
                            integrity_ready = health_ready()
                            if report['reason'] in ('NATIVE_GUARD_INTEGRITY_FAILURE', 'NATIVE_COMMAND_RESULT_UNKNOWN'):
                                break
                            if monitor is not None:
                                monitor.tick(broker, state='CLOSING')
                                if integrity_ready and not broker.failure.is_set():
                                    poll_control()
                                if report['reason'] in ('NATIVE_GUARD_INTEGRITY_FAILURE', 'NATIVE_COMMAND_RESULT_UNKNOWN'):
                                    break
                            await asyncio.sleep(min(poll_seconds,
                                                    max(0, deadline - time.monotonic())))
                except BaseException as error:
                    report['native_close_error'] = type(error).__name__
                    if (getattr(owner, 'require_lifecycle_health', False) is True
                            and (safe_error_code(error) or '').startswith('COMMAND_INTEGRITY_')):
                        health_failure(error)
                finally:
                    if source_quit is not None:
                        try:
                            report['source_quit'] = source_quit.report()
                            source_quit.close()
                        except BaseException as error:
                            report['source_quit_close_error'] = type(error).__name__
                        finally:
                            try:
                                features.close()
                            except BaseException as error:
                                report['feature_close_error'] = type(error).__name__
                if failed_session and report['reason'] != 'SESSION_FAILURE':
                    report['close_failure_reason'] = report['reason']
                    report['reason'] = 'SESSION_FAILURE'  # Preserve the original feature failure.
                # Broker.close commits/finishes store operations and drains
                # writers/tasks before native handles are released or forced.
                # Repeated cancellation must join this same cleanup operation.
                try:
                    if (report['reason'] == 'NATIVE_EXIT' or report.get('close_wait_end') == 'NATIVE_EXIT'):
                        terminal_join = getattr(broker, 'join_quit_exit', None)
                        if terminal_join is not None:
                            try:
                                report['quit_terminal_join'] = await terminal_join()
                            except BaseException as error:
                                report['quit_terminal_join'] = dict(status='UNKNOWN',
                                    error_type=type(error).__name__)
                    close_task = asyncio.create_task(broker.close())
                    while not close_task.done():
                        try:
                            await asyncio.shield(close_task)
                        except asyncio.CancelledError:
                            report['cleanup_interrupted'] = True
                    report['broker'] = close_task.result()
                except BaseException as error:
                    report['broker_close_error'] = type(error).__name__
        finally:
            try:
                if monitor is not None:
                    try:
                        monitor.tick(broker, state=report['reason'], force=True)
                    except BaseException as error:
                        report['status_error_type'] = type(error).__name__
                    finally:
                        try:
                            monitor.close()
                        except BaseException as error:
                            report['observer_close_error_type'] = type(error).__name__
                report['cleanup'] = owner.close()
            except BaseException as error:
                report['cleanup'] = dict(positive_exit=False, error_type=type(error).__name__)
            finally:
                report['exit_outcome'] = exit_outcome(report['cleanup'])
                guard_failure = getattr(owner, 'guard_failure', None)
                if type(guard_failure) is dict:
                    report['native_owner_failure'] = dict(guard_failure,
                        tcp_state_counts=(dict(guard_failure['tcp_state_counts'])
                                          if guard_failure['tcp_state_counts'] is not None else None))
                report.update(source_logout_outcome(report))
                report['native_exit_observed_without_force'] = report['exit_outcome'] == 'NATIVE_EXIT_NO_FORCE'
                report['user_shutdown_requested'] = report['reason'] in ('USER_CLOSE', 'USER_INTERRUPT')
                report['product_lifetime_seconds'] = round(time.monotonic() - started, 3)
                if monitor is not None:
                    try:
                        monitor.finish(report)
                    except BaseException as error:
                        report['status_error_type'] = type(error).__name__
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--product', choices=tuple(PRODUCTS), default='baseline')
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--expected-uuid')
    parser.add_argument('--store', type=Path)
    parser.add_argument('--run-directory', type=Path)
    parser.add_argument('--feature-config', type=Path,
                        help='Explicit optional local NPC spawn/motion JSON; absent keeps NPCs off')
    parser.add_argument('--test-duration', type=float)
    parser.add_argument('--control-mode', choices=('internal', 'manual'), default='internal',
                        help='Internal commands use a private non-input desktop; manual has no runner input')
    parser.add_argument('--background', action='store_true',
                        help='Use the selected product\'s private non-input desktop without changing DLL control mode')
    parser.add_argument('--source-quit-test', action='store_true',
                        help='Explicit source Quit trial on its pinned background product')
    parser.add_argument('--close-grace-seconds', type=float, default=10,
                        help='Native close/input grace only; 0 < seconds <= 120 (default: 10)')
    parser.add_argument('--until-scene', choices=('Intro', 'Lobby', 'Login', 'CharacterSelect', 'Land'))
    args = parser.parse_args()
    if not 0 < args.close_grace_seconds <= 120:
        parser.error('--close-grace-seconds requires 0 < seconds <= 120')
    if not args.run:
        files = preflight(args.image, args.product)
        from tools.local_original_session.feature_config import load
        load(args.feature_config)
        print(json.dumps(dict(status='PREFLIGHT_FILES_VERIFIED', files=[str(p) for p in files],
                              product=args.product, native_executed=False, resources_verified=False)))
        return 0
    need(args.expected_uuid is not None and args.store is not None and args.run_directory is not None,
         'RUN_UUID_STORE_DIRECTORY_REQUIRED')
    need(args.test_duration is None or args.test_duration > 0, 'POSITIVE_TEST_DURATION_REQUIRED')
    directory = args.run_directory.absolute()
    need(not directory.exists(), 'FRESH_RUN_DIRECTORY_REQUIRED')
    directory.mkdir(parents=True)
    sys.path.insert(0, str(ROOT))
    conversations = reader = None
    try:
        spec = PRODUCTS[args.product]
        need(not spec.get('source_build_only'), 'PRODUCT_RUNTIME_UNVERIFIED')
        need(not spec.get('require_source_quit') or args.source_quit_test,
             'SOURCE_QUIT_EXPLICIT_TEST_REQUIRED')
        need(not args.source_quit_test or spec.get('manual_source_quit') is True
             and args.background and args.control_mode == 'manual', 'SOURCE_QUIT_BACKGROUND_PRODUCT_REQUIRED')
        need(not spec.get('require_background') or args.background, 'BACKGROUND_DISPLAY_REQUIRED')
        need(not args.background or spec.get('background_display_guard') is True,
             'BACKGROUND_DISPLAY_GUARD_UNVERIFIED')
        preflight(args.image, args.product)
        from tools.local_original_session.broker import PersistentBroker
        from tools.local_original_session.observe import RetainedSceneReader, SessionMonitor
        from tools.local_original_session.commands import CommandRequests
        from tools.local_original_session.edge import EdgeAdapter
        from tools.local_original_session.feature_config import load
        need(not spec.get('internal_only') or args.control_mode == 'internal',
             'INTERNAL_CONTROL_MODE_REQUIRED')
        need(not spec.get('manual_only') or args.control_mode == 'manual',
             'MANUAL_CONTROL_MODE_REQUIRED')
        need(args.control_mode != 'internal' or spec.get('background_display_guard') is True,
             'INTERNAL_DISPLAY_GUARD_UNVERIFIED')
        feature_config = load(args.feature_config)
        conversations = GenuineConversations()
        reader = RetainedSceneReader(args.image.absolute(), spec['candidate'],
                                     expected_sha=spec['image_sha256'])
        edge = EdgeAdapter(reader)
        feature_factory = ProductFeatureFactory(reader, product=args.product,
            control_mode=args.control_mode, directory=directory, config=feature_config)
        need(not args.source_quit_test or feature_factory.allow_attack and feature_factory.inventory
             and feature_factory.allow_attack_replacement, 'SOURCE_QUIT_EXPLICIT_FEATURE_CONFIG_REQUIRED')
    except Exception as error:
        # Initialization has not constructed the native owner or reserved any
        # listener. Persist only the exception class, never resource messages,
        # module reprs, key values, or a traceback that might contain content.
        report = dict(schema='local-original-session-v1', reason='STARTUP_FAILURE',
                      product=args.product,
                      phase='BEFORE_NATIVE', error_type=type(error).__name__,
                      native_executed=False, listeners_started=False,
                      exit_outcome='NOT_LAUNCHED', normal_exit_verified=False,
                      game_logout_protocol='UNVERIFIED',
                      cleanup=dict(positive_exit=True, owned_job_empty=True, launched=False))
        code = safe_error_code(error)
        if code is not None:
            report['error_code'] = code
        if conversations is not None:
            try:
                conversations.close()
            except Exception as failure:
                report['resource_cleanup_error_type'] = type(failure).__name__
        path = directory / 'result.json'
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(dict(status='REFUSED', result=str(path), reason='STARTUP_FAILURE',
                              error_type=type(error).__name__, error_code=code, native_executed=False)))
        return 2
    boundary = ROOT / 'work/local_native_login_key_invoke_boundary/runs' / ('ls-' + uuid.uuid4().hex[:24])
    owner = None
    monitor = None
    sockets = {}
    try:
        owner = NativeOwner(args.image, boundary, source_guard=conversations.check, product=args.product,
                            internal=args.control_mode == 'internal', background=args.background)
        monitor = SessionMonitor(owner.image, directory, reader=reader)
        add_process_tree_status(monitor, owner)
        command_requests = CommandRequests(directory, owner) if args.control_mode == 'internal' else None
        (directory / 'boundary-path.txt').write_text(str(boundary), encoding='utf-8')
        for port in (12000, 14030):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets[port] = sock
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(('127.0.0.1', port))
            sock.listen()
            sock.setblocking(False)
        def factory(retained):
            return PersistentBroker(sockets=sockets, owner_guard=retained.guard,
                key_guard=retained.key_guard, source_guard=retained.verify_sources,
                owner_liveness_guard=retained.key_guard,
                owner_exit_proof=retained.exit_proof,
                conversation_factory=conversations.conversation, expected_uuid=args.expected_uuid,
                store_path=args.store.absolute(), retained_owner=retained,
                owner_handle=retained.owner_handle, owner_job=retained.owner_job,
                on_release=conversations.release, edge_passability=edge,
                world_profile=PRODUCTS[args.product].get('world_profile', 'baseline'),
                settings_path=args.store.absolute().with_name('account-settings.bin'),
                **feature_factory.broker_options())
        async def run():
            stop = asyncio.Event()
            try:
                return await run_session(owner, factory, stop,
                    stop_requested=lambda: (directory / 'close.request').exists(),
                    test_duration=args.test_duration, monitor=monitor, until_scene=args.until_scene,
                    command_requests=command_requests, close_grace_seconds=args.close_grace_seconds,
                    feature_factory=feature_factory if feature_factory.enabled else None,
                    source_quit_directory=directory if args.source_quit_test else None)
            finally:
                for sock in sockets.values():
                    sock.close()
        report = asyncio.run(run())
        report['product'] = args.product
        report['control_mode'] = args.control_mode
        report['background'] = args.background
        report['process_tree'] = owner.process_tree()
        report['private_non_input_desktop'] = owner.private_desktop is not None
        if type(owner.desktop_status) is dict:
            report['desktop'] = dict(owner.desktop_status)
        report['resource_directory'] = str(owner.resource_directory)
        report['edge_check'] = dict(edge.last_result)
        (directory / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(dict(status='CLOSED', result=str(directory / 'result.json'),
                              reason=report['reason'], cleanup=report['cleanup'],
                              exit_outcome=report['exit_outcome'],
                              normal_exit_verified=report['normal_exit_verified'],
                              game_logout_protocol=report['game_logout_protocol'])))
        return 0 if (report['cleanup'].get('positive_exit') and report['reason'] not in
                     ('SESSION_FAILURE', 'BROKER_FAILURE', 'NATIVE_GUARD_INTEGRITY_FAILURE', 'NATIVE_COMMAND_RESULT_UNKNOWN')
                     and report.get('close_wait_end') != 'BROKER_FAILURE'
                     and not report.get('broker_close_error')) else 2
    finally:
        for sock in sockets.values():
            sock.close()
        try:
            try:
                if monitor is not None:
                    monitor.close()
                elif reader is not None:
                    reader.close()
            finally:
                if owner is not None and not owner.closed:
                    owner.close()
        finally:
            conversations.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(json.dumps(dict(status='REFUSED', reason=str(error)[:200], automatic_retry=False)))
        raise SystemExit(2)
