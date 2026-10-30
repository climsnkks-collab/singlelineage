"""Bounded, read-only CP69 scene/world observation using existing readers."""
from __future__ import annotations

import argparse
import ast
import ctypes as C
from ctypes import wintypes as W
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from types import MethodType

from tools.local_original_session import input_state, move_state

MAX_COUNTER = (1 << 64) - 1
STATUS_LIMIT = 32768
# Saved same-profile evidence: scene 4197 B (cursor-close-13), complete world
# leaf 6073 B (boot-02), complete input leaf 2244 B (input-memory-12): 12514 B.
# This is one observation tick's tool allowance, never a gameplay condition.
# Frozen per-leaf 8192 B, <=4096 B reads and <=2 samples/second stay unchanged.
RETAINED_SAMPLE_LIMIT = 16384

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / 'work/standalone_boot/current-unmodified-clone/LC.local.exe'
CANDIDATE = ROOT / 'work/local_native_login_state5_ack_candidate/native-login.candidate.bin'
CP69 = '656a64e7c686144615f473902590e23ce0024b907e96ad905f42e84084e8da9d'
SDK_SHA = '2ed4967506682b2ef1418ceef317136b2deeb333e722bdab9d5752fe5dc6a01d'
SOURCES = {
    'tools/local_native_scene_current/watch.py': 'a748265c8e0f155e4722e0771e54de73e2c4e7aed830ef821ca36031b10c24a6',
    'tools/normal_online_memory/native.py': '449e4d39e88e4cf4889193ba88a8498f196bec1325bb56e6ff1399598bec4c28',
    'tools/online_intro_capture_20261006/sampler.py': '2253337013d3cfc0a12bcc5c6798fb56ebf0de333ed6517950dbc692e9d2cdeb',
    'tools/local_native_world_read_dormant/inspect_world.py': '2efe6636744eb646cb13259531828ecd9c8011b6de49d331e2129c7dc2789dcf',
}
QUIT_SOURCES = {
    'work/local_server_rea_20261016/run3_quit_4ed6/quit/quit_type.json':
        '99a7c06f00ecbbb4e88ff3dd82f1f23fdfd6c2053869b9da586b1cab1db3faa6',
    'work/local_server_rea_20261016/run3_quit_4ed6/quit/quit_state_producers.json':
        '3cfb697421bbb18c88d4492a6edf5357b719de1d00d5e3432a22feafd3c0e2ac',
    'work/local_server_rea_20261016/run3_quit_4ed6/quit/quit_response_transition.json':
        '1344be20822d59984b083d5c4c9e7b3a28719f5dd7205c71e9aa2ae5c086c4b4',
}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def ordinary(path):
    path = Path(path).absolute()
    need(path.resolve(strict=True) == path and path.is_file(), 'EXACT_SOURCE_PATH_REQUIRED')
    for part in (path, *path.parents):
        info = part.lstat()
        need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'SOURCE_REPARSE_REFUSED')
    need(path.stat().st_nlink == 1, 'SOURCE_MULTIPLE_LINKS_REFUSED')
    return path


def load(relative, alias):
    path = ordinary(ROOT / relative)
    need(digest(path) == SOURCES[relative], 'EXISTING_READER_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def attachment_type(native_module, image):
    """Specialize only the existing inventory basename to the exact pinned image."""
    path = ROOT / 'tools/normal_online_memory/native.py'
    need(digest(path) == SOURCES['tools/normal_online_memory/native.py'],
         'EXISTING_NATIVE_SOURCE_CHANGED')
    tree = ast.parse(path.read_bytes(), str(path))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Native')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'attach')
    literals = [node for node in ast.walk(method) if isinstance(node, ast.Constant) and node.value == 'lc.exe']
    need(len(literals) == 1, 'ONE_INVENTORY_BASENAME_REQUIRED')
    literals[0].value = image.name.casefold()
    namespace = {'__name__': '_session_exact_image_native', '__file__': str(path)}
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec', dont_inherit=True), namespace)
    return namespace['Native']


def quit_scene_contract(contract):
    """Add only the saved QuitState type to the frozen generic scene reader.

    GameStateSubsystem owns current/pending strong pairs and enum; QuitState
    is their separate scene object. This never invokes the subsystem or scene.
    The existing Sampler performs all live type/enum/owner/table re-reads.
    """
    documents = []
    for relative, expected in QUIT_SOURCES.items():
        path = ordinary(ROOT / relative)
        need(0 < path.stat().st_size <= 1048576, 'QUIT_SOURCE_BYTE_BOUND')
        need(digest(path) == expected, 'QUIT_SOURCE_CHANGED')
        documents.append(json.loads(path.read_bytes()))
    types, producers, transition = documents
    for document in (producers, transition):
        need(document.get('CONTROL_sha256') == input_state.CONTROL_SHA,
             'QUIT_SOURCE_CONTROL_CHANGED')
    matches = [row for row in types if row.get('name') == '.?AVQuitState@lineage@@']
    need(len(matches) == 1 and len(matches[0]['tables']) == 1, 'QUIT_SOURCE_TYPE_CHANGED')
    table = matches[0]['tables'][0]
    targets = [0x155820, 0x13a0f0, 0x155880, 0x155b80, 0x155b90]
    need(table['vptr_rva'] == '0x1188110' and table['COL'] == '0x1285e70'
         and [int(value, 16) for value in table['methods']] == targets
         and table['table48_sha256'] ==
         '94acc9526fb4fd0ad0a6658a4d473cbd44bf73908371e182b687eb3eb4b5c6bb',
         'QUIT_SOURCE_TABLE_CHANGED')
    instructions = {function['rva']: {item['rva']: item['instruction']
                    for item in function['instructions']} for function in producers['functions']}
    need(instructions['0x13b880']['0x13b89a'] == 'mov r13, rcx'
         and instructions['0x13b880']['0x13ba74'] == 'lea rcx, [r13 + 0x370]',
         'QUIT_SUBSYSTEM_RECEIVER_SOURCE_CHANGED')
    response = next(function for function in transition['functions'] if function['rva'] == '0x13e390')
    response = {item['rva']: item['instruction'] for item in response['instructions']}
    need(response['0x13e3b8'] == 'mov edx, 6' and response['0x13e3bd'] == 'call 0x13b880',
         'QUIT_ENUM_SOURCE_CHANGED')
    row = dict(kind='Quit', state_id=6, rva=0x1188110, targets=targets)
    existing = [scene for scene in contract['scenes']
                if scene.get('state_id') == 6 or scene.get('kind') == 'Quit'
                or scene.get('rva') == row['rva']]
    if existing:
        need(len(existing) == 1 and all(existing[0].get(key) == value for key, value in row.items()),
             'QUIT_SCENE_CONTRACT_DISAGREES')
        return contract
    return dict(contract, scenes=[*contract['scenes'], row])


def preflight(image=IMAGE, candidate=CANDIDATE, expected_sha=CP69):
    image, candidate = ordinary(image), ordinary(candidate)
    need(image.suffix.casefold() == '.exe' and digest(image) == expected_sha and digest(candidate) == expected_sha,
         'EXACT_PRODUCT_IMAGE_REQUIRED')
    sdk = ordinary(image.with_name('ncplatformsdk-cpp.dll'))
    need(digest(sdk) == SDK_SHA, 'EXACT_CLIENT_SDK_REQUIRED')
    watch = load('tools/local_native_scene_current/watch.py', '_session_scene_watch')
    contract = watch.contract_for(candidate, expected_sha, installed=False)
    contract.update(original_program=str(image), SDK_program=str(sdk))
    contract = quit_scene_contract(contract)
    world = load('tools/local_native_world_read_dormant/inspect_world.py', '_session_world_read')
    world.contracts()
    native = load('tools/normal_online_memory/native.py', '_session_read_native')
    sampler = load('tools/online_intro_capture_20261006/sampler.py', '_session_read_sampler')
    return image, sdk, contract, watch, world, native, sampler


def reason(error):
    value = getattr(error, 'reason', str(error) if isinstance(error, ValueError) else type(error).__name__)
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', value) else 'READ_FAILED'


def public_world(row):
    keys = ('status', 'reason', 'scene', 'pending', 'actor_count', 'my_player_count', 'my_player_uid',
            'expected_uid_match', 'segment_key_words', 'grid_words', 'coordinate_status',
            'coordinate_reason', 'coordinate_axis_names', 'coordinate_scale_units',
            'source_segment_grid_relation_match', 'map_requested_i32', 'map_resolved_i32',
            'map_context_present', 'tile_entry_count', 'coordinate_tile_entry_present',
            'coordinate_tile_resource_present', 'scene_object_present', 'land_game_layer_present',
            'tile_decode_ready', 'render_ready', 'stable_double_read', 'typed_bytes_requested')
    return {key: row.get(key) for key in keys}


class RetainedSceneReader:
    """One prepared source scope; duplicate the owner's process handle read-only.

    Never attaches/reopens a PID, changes privilege, writes memory or invokes
    game code. The existing watch/Sampler performs the same stable owner/scene
    leaves with their original 8192-byte bounds. Each scheduled observation
    shares one 16-KiB aggregate; session counters saturate.
    """
    sample_byte_limit = RETAINED_SAMPLE_LIMIT

    def __init__(self, image, candidate=CANDIDATE, *, expected_sha=CP69):
        image, sdk, contract, watch, world, native, sampler = preflight(image, candidate, expected_sha)
        self.image, self.contract, self.watch, self.sampler_module = image, contract, watch, sampler
        self.world = world
        self.backend = native.Native(contract, {})
        self.owner = self.member = self.sampler = None
        self.closed = False
        try:
            self.backend.pin(image, expected_sha)
            self.backend.pin(sdk, SDK_SHA)
            for path, expected in SOURCES.items():
                self.backend.pin(ROOT / path, expected, 1048576)
            for path, expected in input_state.SOURCES.items():
                self.backend.pin(ROOT / path, expected, 4 * 1024 * 1024)
            for path, expected in QUIT_SOURCES.items():
                self.backend.pin(ROOT / path, expected, 1048576)
            self.input_state = input_state.InputState()
            for path, expected in move_state.SOURCES.items():
                self.backend.pin(ROOT / path, expected, 2 * 1024 * 1024)
            self.move_state = move_state.MoveState()
            self.backend.validate = self.validate
        except BaseException:
            self.close()
            raise

    def bind(self, owner):
        need(self.owner is None and owner.validate(owner.child), 'CURRENT_RETAINED_PRIMARY_REQUIRED')
        self.owner, self.member = owner, owner.child
        kernel = owner.native.k
        kernel.DuplicateHandle.argtypes = (W.HANDLE, W.HANDLE, W.HANDLE,
            C.POINTER(W.HANDLE), W.DWORD, W.BOOL, W.DWORD)
        kernel.DuplicateHandle.restype = W.BOOL
        duplicate = W.HANDLE()
        need(kernel.DuplicateHandle(kernel.GetCurrentProcess(), self.member.process,
            kernel.GetCurrentProcess(), C.byref(duplicate), 0x101010, False, 0),
            'RETAINED_READONLY_DUPLICATE_FAILED')
        self.backend.handle = duplicate.value
        self.backend.stack.callback(kernel.CloseHandle, duplicate.value)
        self.backend.expected = dict(pid=self.member.pid, birth=self.member.identity['birth'])
        self.validate()

    def validate(self):
        need(not self.closed and self.owner is not None and self.owner.validate(self.member),
             'RETAINED_PRIMARY_NOT_LIVE')
        actual = self.owner.native.identity(self.backend.handle, self.member.pid,
            self.member.identity.get('parent_pid'), include_token=False)
        need(all(actual.get(key) == self.member.identity.get(key)
                 for key in ('pid', 'birth', 'image', 'parent_pid')),
             'READONLY_DUPLICATE_IDENTITY_CHANGED')
        inside = W.BOOL()
        need(self.owner.native.k.IsProcessInJob(self.backend.handle, self.owner.owner_job,
             C.byref(inside)) and inside.value, 'READONLY_DUPLICATE_JOB_CHANGED')

    def request_hp4ec8_subscribers_once(self,*,stage="first-land"):
        need(getattr(self,'_hp4ec8_subscribers',None) is None,'HP4EC8_ONCE_REQUEST_REQUIRED')
        from tools.local_original_session.hp4ec8_subscribers import Observation
        self._hp4ec8_subscribers = Observation(self,stage=stage)

    def sample(self, *, include_input_state=True, attack_action_observer=None, player_life_observer=None):
        need(type(include_input_state) is bool, 'RETAINED_INPUT_SELECTION_BOOL_REQUIRED')
        if attack_action_observer is not None:
            from tools.local_original_session.attack_action_observe import AttackActionObserver, COLLECT_METHOD, PREPARE_METHOD
            need(type(attack_action_observer) is AttackActionObserver
                 and attack_action_observer.reader is self
                 and AttackActionObserver.prepare is PREPARE_METHOD and AttackActionObserver.collect is COLLECT_METHOD
                 and type(attack_action_observer.collect) is MethodType
                 and attack_action_observer.collect.__self__ is attack_action_observer
                 and attack_action_observer.collect.__func__ is COLLECT_METHOD
                 and type(attack_action_observer.prepare) is MethodType
                 and attack_action_observer.prepare.__self__ is attack_action_observer
                 and attack_action_observer.prepare.__func__ is PREPARE_METHOD,
                 'RETAINED_ATTACK_SAME_OBSERVER_REQUIRED')
        need(attack_action_observer is None or player_life_observer is None,
             'RETAINED_SINGLE_ACTION_LEAF_REQUIRED')
        if player_life_observer is not None:
            from tools.local_original_session.player_life_observe import PlayerLifeObserver, COLLECT_METHOD, PREPARE_METHOD
            need(type(player_life_observer) is PlayerLifeObserver
                 and player_life_observer.reader is self
                 and type(player_life_observer).collect is COLLECT_METHOD
                 and type(player_life_observer).prepare is PREPARE_METHOD
                 and type(player_life_observer.collect) is MethodType
                 and player_life_observer.collect.__self__ is player_life_observer
                 and player_life_observer.collect.__func__ is COLLECT_METHOD
                 and type(player_life_observer.prepare) is MethodType
                 and player_life_observer.prepare.__self__ is player_life_observer
                 and player_life_observer.prepare.__func__ is PREPARE_METHOD,
                 'RETAINED_PLAYER_LIFE_SAME_OBSERVER_REQUIRED')
        action_leaf = attack_action_observer if attack_action_observer is not None else player_life_observer
        self.validate()
        if self.sampler is None:
            game = self.backend.modules()['LC']
            self.sampler = self.sampler_module.Sampler(self.backend, self.contract, game)
        # The legacy 4-MB capture cap is a per-capture guard, not a product
        # session deadline. Retain each frozen leaf's 8192-B allowance inside
        # one measured 16-KiB aggregate and at most two samples/second.
        self.sampler.total = 0
        # Keep the frozen watch's already double-checked route/scene proof
        # private for this synchronous input leaf; no extra initial root scan.
        proof = {}
        route_method, scene_method = self.sampler.route, self.sampler.scene
        route_present, scene_present = ('route' in self.sampler.__dict__, 'scene' in self.sampler.__dict__)
        def capture_route():
            value = route_method()
            proof['route'] = value
            return value
        def capture_scene(state):
            scene, raw = scene_method(state)
            proof.update(state=state, scene=scene, raw=raw)
            return scene, raw
        self.sampler.route, self.sampler.scene = capture_route, capture_scene
        try:
            row = self.watch.sample(self.backend, self.sampler)
        finally:
            for name, present, method in (('route', route_present, route_method),
                                           ('scene', scene_present, scene_method)):
                if present:
                    setattr(self.sampler, name, method)
                else:
                    self.sampler.__dict__.pop(name, None)
        world = self.world.empty_result('LAND_NOT_OBSERVED')
        # One combined scene/input/world allowance. Legacy leaves may reset
        # their per-leaf bytes/read_limit; they cannot reset this tick's total.
        read = self.sampler.read
        world_cache = {}
        collecting_world = False
        collecting_move = False
        collecting_attack = False
        attack_cache = None
        hp4ec8_query = object()
        def bounded_read(at, size, image=False):
            # Only the explicit attack leaf may use its additional original
            # 8192-B allowance. Legacy leaves and MoveState retain 16 KiB.
            active_limit = self.sample_byte_limit + (8192 if collecting_attack else 0)
            need(self.sampler.total + size <= active_limit,
                 'RETAINED_SAMPLE_BYTE_BUDGET')
            value = read(at, size, image=image)
            if collecting_world:
                world_cache[(at, size, image)] = value
            if collecting_move and attack_cache is not None:
                attack_cache.capture('MOVE', at, size, image, value)
            return value
        self.sampler.read = bounded_read
        try:
            if row.get('status') == 'OBSERVED' and row.get('current') == 'Land':
                # No fixed/profile UID is an expectation: the current broker
                # report does not prove a fresh selected-connection identity.
                collecting_world = True
                try:
                    world = self.world.inspect_attached(self.backend, self.sampler)
                finally:
                    collecting_world = False
            # Full diagnostics retain scene -> world -> input -> move order.
            # An explicit movement consumer can skip cursor/host diagnostics,
            # leaving their allowance for the same typed movement probe.
            internal = getattr(getattr(self, 'owner', None), 'internal', False) is True
            probe = getattr(self, 'input_state', None)
            if not include_input_state:
                row['input_state'] = input_state.empty('MOVEMENT_INPUT_NOT_REQUIRED')
            elif internal:
                row['input_state'] = input_state.empty('INTERNAL_COMMAND_INPUT_NOT_REQUIRED')
            else:
                row['input_state'] = (probe.sample(self, row, proof) if probe is not None
                                      else input_state.empty('INPUT_READER_UNAVAILABLE'))
            movement_probe = getattr(self, 'move_state', None)
            if action_leaf is not None:
                from tools.local_original_session.attack_action_observe import SameQueryCache
                attack_cache = SameQueryCache(self, self.sampler, proof, world_cache)
            collecting_move = True
            try:
                row['move_state'] = (movement_probe.sample(self, row, world, proof, world_cache)
                                     if movement_probe is not None else move_state.empty('MOVE_READER_UNAVAILABLE'))
            finally:
                collecting_move = False
            if action_leaf is not None:
                attack_cache.finish_move(row['move_state'])
                collecting_attack = True
                try:
                    key = 'attack_action' if attack_action_observer is not None else 'player_life'
                    row[key] = action_leaf.collect(row, world, proof, attack_cache)
                finally:
                    collecting_attack = False
            hp4ec8 = getattr(self,'_hp4ec8_subscribers',None)
            if (hp4ec8 is not None and hp4ec8.result is None
                    and row.get('status') == 'OBSERVED' and row.get('current') == 'Land'
                    and world.get('status') == 'OBSERVED'):
                hp4ec8.collect(self.sampler,total_limit=self.sample_byte_limit,query=hp4ec8_query)
        finally:
            self.sampler.read = read
            self.sampler.bytes = self.sampler.total
        try:
            self.validate()
        except Exception:
            hp4ec8 = getattr(self,'_hp4ec8_subscribers',None)
            if hp4ec8 is not None: hp4ec8.failed_final_check(hp4ec8_query)
            raise
        hp4ec8 = getattr(self,'_hp4ec8_subscribers',None)
        if hp4ec8 is not None:
            hp4ec8.finish(hp4ec8_query)
            row['hp4ec8_subscribers'] = hp4ec8.result if hp4ec8.result is not None else dict(hp4ec8.waiting)
        row['world'] = public_world(world)
        return row, self.sampler.bytes

    def close(self):
        if not self.closed:
            self.backend.close()
            self.closed = True


PUBLIC_CAPTIONS = frozenset(('Lineage Classic', 'Lineage', '리니지 클래식', '리니지',
    'NC', 'PURPLE', '알림', 'Notice', 'Error', 'Lineage Classic - 26.09.29.2001 [LIVE]'))
PUBLIC_CLASSES = frozenset(('#32770', 'GLFW30', 'Static', 'Button', 'Edit', 'ComboBox',
    'ComboBoxEx32', 'ListBox', 'IME', 'MSCTFIME UI', 'Intermediate D3D Window'))
KNOWN_ERRORS = frozenset(('리니지 클래식 실행은 게임 런처를 통해 실행 부탁드립니다.',))


def window_health(owner, row):
    """Read-only current primary metadata; hung=false is not rendering evidence.

    IsHungAppWindow is a Windows responsiveness heuristic. No input messages,
    target invocation, attach, foreground action or DPI context change occurs.
    """
    unknown = dict(status='UNKNOWN', is_hung=None, dpi=None, render_verified=False)
    member = row.get('owned_member')
    if owner is None or type(member) is not dict:
        return dict(unknown, reason='CURRENT_PRIMARY_ONLY')
    try:
        child = owner.child
        need(member.get('pid') == child.pid and member.get('birth') == child.identity['birth']
             and member.get('image_basename') == Path(child.identity['image']).name,
             'CURRENT_PRIMARY_ONLY')
        hwnd = row.get('hwnd')
        expected_class = row.get('class')
        need(type(hwnd) is int and hwnd > 0 and expected_class in PUBLIC_CLASSES,
             'CURRENT_WINDOW_METADATA_REQUIRED')
        need(owner.validate(child) is True and owner.native.owned_hwnd(child, hwnd),
             'CURRENT_WINDOW_OWNER_LOST')
        user = owner.native.u
        for name, args, result in (
            ('IsHungAppWindow', (W.HWND,), W.BOOL),
            ('GetDpiForWindow', (W.HWND,), W.UINT),
            ('GetClassNameW', (W.HWND, W.LPWSTR, C.c_int), C.c_int),
        ):
            function = getattr(user, name)
            function.argtypes, function.restype = args, result
        def same_class():
            name = C.create_unicode_buffer(128)
            length = user.GetClassNameW(hwnd, name, len(name))
            return 0 < length < len(name) - 1 and name.value == expected_class
        need(same_class(), 'CURRENT_WINDOW_CLASS_CHANGED')
        dpi = user.GetDpiForWindow(hwnd)
        need(type(dpi) is int and 48 <= dpi <= 1536, 'CURRENT_WINDOW_DPI_UNKNOWN')
        hung = user.IsHungAppWindow(hwnd)
        need(type(hung) in (int, bool) and hung in (0, 1), 'CURRENT_WINDOW_HUNG_UNKNOWN')
        need(owner.child is child and owner.validate(child) is True
             and owner.native.owned_hwnd(child, hwnd), 'CURRENT_WINDOW_OWNER_LOST')
        need(same_class() and user.GetDpiForWindow(hwnd) == dpi,
             'CURRENT_WINDOW_METADATA_CHANGED')
        need(owner.child is child and owner.validate(child) is True
             and owner.native.owned_hwnd(child, hwnd), 'CURRENT_WINDOW_OWNER_LOST')
        return dict(status='OBSERVED', is_hung=bool(hung), dpi=dpi, render_verified=False)
    except Exception as error:
        code = error.args[0] if len(error.args) == 1 else None
        allowed = {'CURRENT_PRIMARY_ONLY', 'CURRENT_WINDOW_METADATA_REQUIRED',
                   'CURRENT_WINDOW_OWNER_LOST', 'CURRENT_WINDOW_CLASS_CHANGED',
                   'CURRENT_WINDOW_DPI_UNKNOWN', 'CURRENT_WINDOW_HUNG_UNKNOWN',
                   'CURRENT_WINDOW_METADATA_CHANGED'}
        return dict(unknown, reason=code if type(code) is str and code in allowed else 'WINDOW_HEALTH_UNKNOWN')


def public_windows(rows, owner=None):
    """Only known public captions/errors; no unknown text, text hash or HWND."""
    result = []
    for row in rows[:8]:
        item = dict(window_class=row.get('class') if row.get('class') in PUBLIC_CLASSES else 'other',
                    visible=row.get('visible') is True)
        if row.get('title') in PUBLIC_CAPTIONS:
            item['public_caption'] = row['title']
        geometry = row.get('geometry')
        if (type(geometry) is dict and set(geometry) == {'left', 'top', 'width', 'height'}
                and all(type(value) is int and abs(value) <= 1000000 for value in geometry.values())):
            item['geometry'] = geometry
        errors = sorted({child.get('text', '').strip() for child in row.get('children', [])[:64]
                         if child.get('class') == 'Static'
                         and child.get('text', '').strip() in KNOWN_ERRORS})
        if errors:
            item['known_error_text'] = errors
        if owner is not None:
            item['window_health'] = window_health(owner, row)
        result.append(item)
    return result


def public_movement(row):
    if type(row) is not dict:
        return dict(committed=0, active_services=0, sessions=[])
    def count(value, maximum=MAX_COUNTER):
        return value if type(value) is int and 0 <= value <= maximum else None
    def position(value):
        if type(value) is not dict:
            return None
        grid = value.get('grid')
        map_id = value.get('map_id')
        return dict(uid=count(value.get('uid')), map_id=map_id if type(map_id) is int
                    and -0x80000000 <= map_id <= 0x7fffffff else None,
                    grid=list(grid) if type(grid) is list and len(grid) == 2
                    and all(type(n) is int and 0 <= n <= 65535 for n in grid) else None)
    sessions = []
    source_sessions = row.get('sessions')
    for session in (source_sessions if type(source_sessions) is list else [])[:6]:
        if type(session) is not dict:
            continue
        last = session.get('last_result')
        if type(last) is dict:
            last = dict(accepted=last.get('accepted') is True,
                        reason=reason(ValueError(last.get('reason'))),
                        unknown=last.get('unknown') is True, fatal=last.get('fatal') is True,
                        authority=position(last.get('authority')),
                        reply_count=count(last.get('reply_count'), 1),
                        own_SC4E2C_count=count(last.get('own_SC4E2C_count'), 0))
        else:
            last = None
        sessions.append(dict(connection_id=count(session.get('connection_id')),
                             committed=count(session.get('committed')),
                             requests_received=count(session.get('requests_received')),
                             corrections_prepared=count(session.get('corrections_prepared')),
                             authority=position(session.get('authority')), last_result=last,
                             fatal=session.get('fatal') is True, closed=session.get('closed') is True))
    return dict(committed=count(row.get('committed')), active_services=count(row.get('active_services'), 2),
                sessions=sessions)


def broker_status(broker):
    if broker is None:
        return dict(state='NOT_STARTED', failure_code=None, connections=[])
    report = broker.report()
    keys = ('state', 'failure_code', 'last_received_frame', 'active_tasks',
            'registry_sessions', 'events', 'dropped_events', 'cleanup_complete')
    row = {key: report.get(key) for key in keys}
    row['connections'] = report.get('connections', [])[:4]
    row['movement'] = public_movement(report.get('movement'))
    edge = report.get('edge_check')
    if type(edge) is dict:
        row['edge_check'] = {key: edge.get(key) for key in ('status', 'reason', 'typed_bytes_requested')}
    else:
        row['edge_check'] = dict(status='UNKNOWN', reason='NOT_SAMPLED', typed_bytes_requested=0)
    return row


def bridge_status(owner):
    """Two current-context diagnostic files; never guard/admission evidence."""
    if owner is None or not hasattr(owner, 'directory'):
        return dict(status='UNKNOWN', reason='CURRENT_CONTEXT_UNAVAILABLE', probes=[])
    probes = []
    for index in (0, 1):
        path = owner.directory / ('connect-probe-' + str(index) + '.json')
        try:
            need(not path.is_symlink() and not getattr(path.stat(), 'st_file_attributes', 0) & 0x400,
                 'DIAGNOSTIC_REPARSE_REFUSED')
            with path.open('rb') as stream:
                raw = stream.read(8193)
            need(len(raw) <= 8192, 'DIAGNOSTIC_BYTE_BOUND')
            row = json.loads(raw)
            need(type(row) is dict and row.get('schema') == 'own-cp13-connect-probe-v1'
                 and type(row.get('pid')) is int and row['pid'] == owner.child.pid
                 and type(row.get('birth')) is int and row['birth'] == int(owner.child.identity['birth'])
                 and row.get('candidate_sha256') == owner.image_sha,
                 'DIAGNOSTIC_CONTEXT_MISMATCH')
            fields = {}
            for key in ('binding_reason', 'binding_stage', 'failed_record_id', 'source_check_step', 'phase'):
                if key in row:
                    need(type(row[key]) is int and -1 <= row[key] <= 65535, 'DIAGNOSTIC_FIELD_TYPE')
                    fields[key] = row[key]
            for key in ('source_check_passed', 'wrapper_selected', 'current_original_verified',
                        'prior_all_roles_verified', 'connect_role_revalidated',
                        'fresh_verified_duplicate'):
                if key in row:
                    need(type(row[key]) is bool, 'DIAGNOSTIC_FIELD_TYPE')
                    fields[key] = row[key]
            probes.append(dict(status='OBSERVED', index=index, **fields))
        except FileNotFoundError:
            probes.append(dict(status='UNKNOWN', index=index, reason='NOT_EMITTED'))
        except Exception as error:
            probes.append(dict(status='UNKNOWN', index=index, reason=reason(error)))
    return dict(status='OBSERVED' if any(p['status'] == 'OBSERVED' for p in probes) else 'UNKNOWN',
                probes=probes, admission_evidence=False)


def first_key_drained(broker):
    # Policy rows are installed only after this literal writer's KEY drain and
    # current owner admission. Do not put typed memory/window work before it.
    policy = getattr(broker, 'policy', None)
    return any(row.tx_boot >= 1 for rows in getattr(policy, 'rows', {}).values() for row in rows)


class SessionMonitor:
    """Single bounded status file in the launcher's existing event loop."""
    def __init__(self, image, directory, *, reader=None, clock=time.monotonic, interval=.75):
        need(.5 <= interval <= 1, 'STATUS_INTERVAL_BOUND')
        self.reader = reader if reader is not None else RetainedSceneReader(image)
        self.directory, self.clock, self.interval = Path(directory), clock, interval
        self.owner = None
        self.bound_at = None
        self.started = clock()
        self.next_tick = self.next_memory = self.started
        self.last_state = self.last_row = None
        self.last_memory = dict(status='UNKNOWN', reason='NOT_SAMPLED', current='unknown', pending='unknown')
        self.last_world = public_world(dict(status='UNKNOWN', reason='NOT_SAMPLED'))
        self.last_input_state = input_state.empty()
        self.last_move_state = move_state.empty()
        self.first_scene = self.last_observed_scene = None
        self.first_error = None
        self.samples = self.total_bytes = self.revision = 0
        # Steady in-world status (RUNNING, Land observed) refreshes the public
        # window list and the scene sample less often: both run synchronously
        # on the shared event loop (measured 20-100 ms per tick).
        self.last_windows, self.windows_at, self.memory_at = [], None, None

    STEADY_WINDOWS_SECONDS = 3.0
    STEADY_MEMORY_SECONDS = 2.0

    def bind(self, owner):
        self.owner = owner
        self.reader.bind(owner)
        self.bound_at = self.clock()

    def tick(self, broker=None, *, state='RUNNING', force=False):
        now = self.clock()
        if not force and now < self.next_tick:
            return self.last_row
        self.next_tick = now + self.interval
        windows = []
        steady = (state == 'RUNNING' and not force and self.last_observed_scene is not None
                  and self.last_observed_scene.get('current') == 'Land')
        try:
            alive = self.owner.validate(self.owner.child)
            heavy_ready = state != 'RUNNING' or broker is None or first_key_drained(broker)
            # A pre-connect initialization dialog may prevent KEY entirely.
            # After five quiet seconds inspect only bounded known public UI;
            # typed memory still waits for actual first KEY drain/admission.
            quiet_window_fallback = (self.bound_at is not None and now - self.bound_at >= 5
                and not broker_status(broker).get('connections'))
            if alive and (heavy_ready or quiet_window_fallback):
                if (steady and self.windows_at is not None
                        and now - self.windows_at < self.STEADY_WINDOWS_SECONDS):
                    windows = self.last_windows
                else:
                    windows = public_windows(self.owner.native.job_windows(self.owner.child), self.owner)
                    self.last_windows, self.windows_at = windows, now
            if not alive:
                self.last_memory = dict(status='UNKNOWN', reason='PROCESS_EXITED', current='unknown', pending='unknown')
                self.last_world = public_world(dict(status='UNKNOWN', reason='PROCESS_EXITED'))
                self.last_input_state = input_state.empty('PROCESS_EXITED')
                self.last_move_state = move_state.empty('PROCESS_EXITED')
            elif not heavy_ready:
                self.last_memory = dict(status='UNKNOWN', reason='WAITING_FIRST_KEY_DRAIN', current='unknown', pending='unknown')
                self.last_world = public_world(dict(status='UNKNOWN', reason='WAITING_FIRST_KEY_DRAIN'))
                self.last_input_state = input_state.empty('WAITING_FIRST_KEY_DRAIN')
                self.last_move_state = move_state.empty('WAITING_FIRST_KEY_DRAIN')
            elif now >= self.next_memory and not (
                    # The 2 s steady period starts only once the world scene is
                    # stably double-read; until then (entry, inventory admission)
                    # keep the ordinary 0.5 s sampling.
                    steady and self.last_world.get('stable_double_read') is True
                    and self.memory_at is not None
                    and now - self.memory_at < self.STEADY_MEMORY_SECONDS):
                self.next_memory = now + .5
                self.memory_at = now
                try:
                    hp4ec8 = getattr(self.reader,'_hp4ec8_subscribers',None)
                    # Host/cursor diagnostics are public status only. Existing
                    # feature ingress already proves its own world/move/owner.
                    scene, count = (self.reader.sample(include_input_state=False)
                        if hp4ec8 is not None and hp4ec8.result is None else self.reader.sample())
                    self.last_memory = {key: scene.get(key) for key in
                        ('status', 'reason', 'current', 'pending', 'root_ready', 'root_phase') if key in scene}
                    self.last_world = public_world(scene.get('world') or
                        dict(status='UNKNOWN', reason='WORLD_NOT_INSPECTED'))
                    self.last_input_state = input_state.public(scene.get('input_state'))
                    self.last_move_state = move_state.public(scene.get('move_state'))
                    self.samples = min(MAX_COUNTER, self.samples + 1)
                    self.total_bytes = min(MAX_COUNTER, self.total_bytes + count)
                except Exception as error:
                    self.last_memory = dict(status='UNKNOWN', reason=reason(error), current='unknown', pending='unknown')
                    self.last_world = public_world(dict(status='UNKNOWN', reason=reason(error)))
                    self.last_input_state = input_state.empty(reason(error))
                    self.last_move_state = move_state.empty(reason(error))
        except Exception as error:
            self.last_memory = dict(status='UNKNOWN', reason=reason(error), current='unknown', pending='unknown')
            self.last_world = public_world(dict(status='UNKNOWN', reason=reason(error)))
            self.last_input_state = input_state.empty(reason(error))
            self.last_move_state = move_state.empty(reason(error))
        current = self.last_memory
        if current.get('status') == 'OBSERVED':
            self.last_observed_scene = dict(current)
            if self.first_scene is None:
                self.first_scene = dict(current)
        errors = [text for window in windows for text in window.get('known_error_text', [])]
        if errors and self.first_error is None:
            self.first_error = errors[0]
        public = dict(schema='local-original-session-status-v1', state=state,
            memory=dict(scene=current, first_observed_scene=self.first_scene,
                        last_observed_scene=self.last_observed_scene, world=self.last_world,
                        input_state=self.last_input_state, move_state=self.last_move_state),
            windows=windows, first_known_error=self.first_error, broker=broker_status(broker),
            bridge=bridge_status(self.owner),
            visible_ui_proven=False, memory_write_or_game_control=False)
        return self.publish(public)

    def publish(self, public):
        hp4ec8 = getattr(self.reader,'_hp4ec8_subscribers',None)
        if hp4ec8 is not None:
            public.setdefault('memory',{})['hp4ec8_subscribers'] = (
                hp4ec8.result if hp4ec8.result is not None else dict(hp4ec8.waiting))
        now = self.clock()
        encoded = json.dumps(public, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        if encoded != self.last_state:
            self.revision = min(MAX_COUNTER, self.revision + 1)
            public.update(revision=self.revision, elapsed_seconds=round(now - self.started, 3),
                          memory_samples=self.samples, typed_bytes_requested_total=self.total_bytes)
            raw = (json.dumps(public, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
            need(len(raw) <= STATUS_LIMIT, 'STATUS_FILE_BYTE_BOUND')
            path = self.directory / 'status.json'
            temporary = self.directory / 'status.json.tmp'
            # Live status only: os.replace keeps readers atomic; no per-tick fsync
            # (measured up to ~600 ms on the shared event loop).
            with temporary.open('wb') as stream:
                stream.write(raw)
            os.replace(temporary, path)
            self.last_state, self.last_row = encoded, public
        return self.last_row

    def finish(self, report):
        previous = self.last_row or {}
        keep = ('schema', 'memory', 'windows', 'bridge', 'first_known_error', 'visible_ui_proven',
                'memory_write_or_game_control')
        public = {key: previous[key] for key in keep if key in previous}
        verified = (report.get('normal_exit_verified') is True
                    and report.get('game_logout_protocol') == 'SOURCE_QUIT_DRAIN_EOF_EXIT0')
        public.update(schema='local-original-session-status-v1', state='CLOSED',
            reason=report.get('reason'), exit_outcome=report.get('exit_outcome'),
            normal_exit_verified=verified,
            game_logout_protocol='SOURCE_QUIT_DRAIN_EOF_EXIT0' if verified else 'UNVERIFIED',
            windows_observation='LAST_BEFORE_CLEANUP',
            broker=report.get('broker', previous.get('broker', {})))
        # The final broker report contains a bounded event ring useful in the
        # result, but the live status file only needs the same narrow summary.
        full = public['broker']
        keys = ('state', 'failure_code', 'last_received_frame', 'active_tasks',
                'registry_sessions', 'events', 'dropped_events', 'cleanup_complete', 'connections')
        public['broker'] = {key: full.get(key) for key in keys if key in full}
        return self.publish(public)

    def close(self):
        self.reader.close()


def observe(image, candidate, pid, birth, samples=1, interval=.5, expected_uid=None, expected_sha=CP69):
    need(type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdecimal() and int(birth) > 0,
         'EXACT_PID_BIRTH_REQUIRED')
    need(type(samples) is int and 1 <= samples <= 120 and .25 <= interval <= 10,
         'BOUNDED_OBSERVATION_REQUIRED')
    image, sdk, contract, watch, world, native_module, sampler_module = preflight(image, candidate, expected_sha)
    native = attachment_type(native_module, image)(contract, {'pid': pid, 'birth': birth})
    try:
        # These read-share handles keep both exact images fixed throughout attachment.
        native.pin(image, expected_sha)
        native.pin(sdk, SDK_SHA)
        attached = native.attach()
        need(attached['birth'] == birth and attached['elevated'] is False and attached['integrity_rid'] <= 8192,
             'EXACT_MEDIUM_PROCESS_REQUIRED')
        game = native.modules()['LC']
        sampler = sampler_module.Sampler(native, contract, game)
        began = time.monotonic()
        for index in range(samples):
            remaining = began + index * interval - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            scene = watch.sample(native, sampler)
            world_row = world.empty_result('LAND_NOT_OBSERVED')
            if scene['status'] == 'OBSERVED' and scene['current'] == 'Land':
                world_row = world.inspect_attached(native, sampler, expected_uid=expected_uid)
            row = {'schema': 'local-original-session-observation-v1', 'sample': index,
                   'elapsed_seconds': round(time.monotonic() - began, 3), 'pid': pid, 'birth': birth,
                   'scene': scene, 'world': public_world(world_row),
                   'visible_ui_proven': False, 'memory_write_or_game_control': False}
            print(json.dumps(row, ensure_ascii=False, separators=(',', ':')), flush=True)
            if scene.get('reason') == 'process_exited':
                break
    finally:
        native.close()


def main():
    sys.path.insert(0, str(ROOT))
    from tools.local_original_session.launcher import PRODUCTS, product_configuration
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=IMAGE)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--product', choices=tuple(PRODUCTS), default='baseline')
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--birth')
    parser.add_argument('--samples', type=int, default=1)
    parser.add_argument('--interval', type=float, default=.5)
    parser.add_argument('--expected-uid', type=int)
    args = parser.parse_args()
    try:
        product_configuration(args.product, args.image.absolute())
        spec = PRODUCTS[args.product]
        candidate = args.candidate or spec['candidate']
        expected_sha = spec['image_sha256']
        if args.preflight:
            image, sdk, *_ = preflight(args.image, candidate, expected_sha)
            print(json.dumps({'status': 'STATIC_READER_CONTRACT_REVIEWED', 'image': str(image),
                              'sdk': str(sdk), 'candidate_sha256': expected_sha, 'process_or_memory_access': False}))
        else:
            observe(args.image, candidate, args.pid, args.birth, args.samples, args.interval,
                    args.expected_uid, expected_sha)
        return 0
    except Exception as error:
        print(json.dumps({'status': 'UNKNOWN', 'reason': reason(error), 'memory_write_or_game_control': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
