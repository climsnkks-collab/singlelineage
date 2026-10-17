"""Explicit background manual scenario; ordinary foreground launch disabled.

Reuses launcher ownership/loop/cleanup, owned non-input desktop and frozen probes.
No desktop switch, attach, cursor/focus/global input API or Quit facade.
WINDOW_CLOSE is a trial; only the launcher's actual source-Quit result proves it.
"""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
import importlib.util
import json
from pathlib import Path
import struct
import sys
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.local_original_session import launcher
from tools.local_original_session.commands import _atomic, _closed_health_json

PROFILE = 'sibling-manual-play-spawn'
IMAGE_SHA = '8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684'
DLL_SHA = '1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75'
CONTINUOUS_PROFILE = 'sibling-manual-move-continuous-spawn'
BACKGROUND_PROFILE = 'sibling-background-move-continuous-spawn'
ATTACK_PROFILE = 'sibling-background-move-attack-target-spawn'
ATTACK_DLL_SHA = '2c0bcd6e53eb5d86e4ef87115f899b976a86d5e820912d63ab3de29e1344073d'
SOURCE_QUIT_PROFILE = 'sibling-background-source-quit-spawn'
SOURCE_QUIT_DLL_SHA = 'd5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d'
INVENTORY_UPDATE_PROFILE = 'sibling-background-inventory-update-source-quit-spawn'
USE_ITEM_PROFILE = 'sibling-background-use-item-source-quit-spawn'
USE_ITEM_DLL_SHA = 'fd82765c07762ba4c37127bb4f6584f853cebdc4d7f5db31af65fa7f6471ebab'
SOURCE_RESELECT_PROFILE = 'sibling-background-source-reselect-spawn'
SOURCE_RESELECT_DLL_SHA = 'bd24d868ad95394a9ed48ba1368afce805836ee58e5cb83435295e47746af1a9'
SOURCE_RESTART_PROFILE = 'sibling-background-source-restart-spawn'
SOURCE_RESTART_DLL_SHA = 'f3496b5075f069316b4a65db0242cc11f311bc5a0cc5920cceb3116223460902'
CONTINUOUS_DLL_SHA = '660f98fa25323baeffd1bf9389f78bb9010816607c4e7e5ae48c3446f282dea4'
PROBES = {
    'Login': ('inspect_login_button.py', '92c4b35a8b6cecaa5493cd6c6b1a97d2a827da188718c1045c7bb825f1535692'),
    'Select': ('inspect_character_select.py', '77115a58a1aaf35c065ff5deeb3ec1ab815753b6136bf5f567ad379e3163bdf1'),
}
MESSAGES = {'Login': 'LC-Owned-Auto-OK-CP34', 'Slot': 'LC-Owned-Select-Empty-CP44',
            'SelectOK': 'LC-Owned-Character-OK-CP46'}
EVENTS = {'Login': ('auto-ok-invoke.json', 'ORIGINAL_OK_RETURNED'),
          'Slot': ('auto-create-invoke.json', 'ORIGINAL_SLOT_SELECTED'),
          'SelectOK': ('auto-select-ok-invoke.json', 'ORIGINAL_SELECT_OK_RETURNED')}


def need(value, code):
    if not value:
        raise ValueError(code)


def grid_pair(value):
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(type(x) is int for x in value):
        return tuple(value)
    return None


def binding(owner, reader, kind, *, require_slot_zero=False):
    """Run the existing probe using the retained read-only backend, not attach()."""
    name, pin = PROBES[kind]
    path = ROOT / 'tools/local_native_scene_current' / name
    need(launcher.digest(path) == pin, 'FROZEN_BASELINE_UI_PROBE_CHANGED')
    reader.validate()
    identity = dict(pid=owner.child.pid, birth=str(owner.child.identity['birth']))

    class BorrowedNative:
        def __init__(self, contract, expected):
            need(contract is reader.contract and expected == identity, 'RETAINED_PROBE_IDENTITY_REQUIRED')
        def attach(self): reader.validate()  # No OpenProcess, inventory or second owner.
        def modules(self): reader.validate(); return reader.backend.modules()
        def read(self, *args, **kwargs): reader.validate(); return reader.backend.read(*args, **kwargs)
        def close(self): pass  # RetainedSceneReader owns this duplicate's lifetime.

    def contract(candidate, digest):
        need(candidate == launcher.PRODUCTS[owner.product]['candidate'] and digest == IMAGE_SHA,
             'FROZEN_BASELINE_CANDIDATE_REQUIRED')
        reader.validate()
        return reader.contract

    samplers = []
    def sampler(*args):
        result = reader.sampler_module.Sampler(*args); samplers.append(result); return result

    def load(path, alias):
        if path == reader.watch.NATIVE: return SimpleNamespace(Native=BorrowedNative)
        need(path == reader.watch.SAMPLER, 'EXISTING_PROBE_DEPENDENCY_REQUIRED')
        return SimpleNamespace(Sampler=sampler)

    watch = SimpleNamespace(contract_for=contract, load=load,
                            NATIVE=reader.watch.NATIVE, SAMPLER=reader.watch.SAMPLER)
    previous = sys.modules.get('watch')
    sys.modules['watch'] = watch
    try:
        spec = importlib.util.spec_from_file_location('_manual_baseline_' + kind, path)
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
    finally:
        if previous is None: sys.modules.pop('watch', None)
        else: sys.modules['watch'] = previous
    result = probe.inspect(launcher.PRODUCTS[owner.product]['candidate'], IMAGE_SHA,
                           identity['pid'], identity['birth'], include_transient=True)
    reader.validate()
    layout, button = result.pop('_transient_layout', None), result.pop('_transient_button', None)
    if layout is None and button is None:
        return None  # Valid owner/pins, but this scene's typed UI binding is not ready.
    need(type(layout) is int and type(button) is int, 'FRESH_BOUND_BASELINE_UI_REQUIRED')
    if require_slot_zero:
        need(len(samplers) == 1 and struct.unpack('<i', samplers[0].read(layout + 0x180, 4))[0] == 0,
             'CURRENT_SAVED_SLOT_ZERO_REQUIRED')
    return layout, button  # Ephemeral until the one native message; never recorded.


class Scenario:
    background_confirm_allowed = False
    close_after_failure = False

    def __init__(self, owner, monitor, stop, idle_seconds, *, clock=time.monotonic, confirm_window_close=False,
                 profile=PROFILE, background=False, source_quit_test=False):
        need(owner.product == profile and owner.image_sha == IMAGE_SHA and not owner.internal
             and (background or owner.private_desktop is None), 'EXACT_MANUAL_BASELINE_OWNER_REQUIRED')
        self.background = background
        need(type(source_quit_test) is bool and (not source_quit_test or background
             and profile in (SOURCE_QUIT_PROFILE, USE_ITEM_PROFILE, INVENTORY_UPDATE_PROFILE, SOURCE_RESELECT_PROFILE) and not confirm_window_close),
             'SCENARIO_EXCLUSIVE_SOURCE_QUIT_BACKGROUND_REQUIRED')
        self.source_quit_test = source_quit_test
        self._retained_background_desktop = None
        self.primary_thread_desktop_verified = False
        self.primary_thread_desktop_probe = None
        self.primary_thread_desktop_proof = None
        if background:
            need(profile in (BACKGROUND_PROFILE, ATTACK_PROFILE, SOURCE_QUIT_PROFILE, USE_ITEM_PROFILE, INVENTORY_UPDATE_PROFILE, SOURCE_RESTART_PROFILE, SOURCE_RESELECT_PROFILE) and getattr(owner, 'background', False) is True
                 and (owner.private_desktop is None or type(owner.private_desktop) is launcher.PrivateDesktop),
                 'OWNED_BACKGROUND_MANUAL_DESKTOP_REQUIRED')
            need(not confirm_window_close or self.background_confirm_allowed,
                 'NO_QUIT_ENTER_TRIAL_IN_BACKGROUND_RUN')
        self.profile = profile
        self.owner, self.monitor, self.stop, self.clock = owner, monitor, stop, clock
        self.reader, self.idle_seconds = monitor.reader, idle_seconds
        self.path = monitor.directory / 'manual-baseline-scenario.json'
        self.actions, self.stage, self.last_sample = [], 'LOGIN', -1
        self.land_since, self.idle_key, self.error = None, None, None
        self.idle_last_good, self.idle_paused, self.idle_reason = None, False, 'NO_GOOD_IDLE_SAMPLE'
        self.idle_event_start = 0
        self.alive_rx = self.alive_tx = self.hold_complete = False
        self.confirm_window_close = confirm_window_close
        self.close_started = self.close_hwnd = None
        self.close_enter_claims, self.close_enter_sample, self.close_input_failed = 0, -1, False

    def summary(self):
        return dict(schema='manual-baseline-scenario-v1', profile=self.profile, control_mode='manual',
            stage=self.stage, actions=self.actions, idle_seconds_requested=self.idle_seconds,
            idle_wall_elapsed_seconds=max(0, self.clock() - self.land_since) if self.land_since is not None else 0,
            idle_snapshot_ready=(self.land_since is not None and not self.idle_paused
                                 and 0 <= self.clock() - self.idle_last_good <= 1.5),
            idle_paused=self.idle_paused, idle_reason=self.idle_reason,
            idle_last_good_age_seconds=max(0, self.clock() - self.idle_last_good) if self.idle_last_good is not None else None,
            idle_hold_complete=self.hold_complete, alive_request_seen=self.alive_rx,
            alive_reply_drained_seen=self.alive_tx,
            close_policy='MANUAL_SOURCE_QUIT_TEST' if self.source_quit_test else 'WINDOW_CLOSE_TEST',
            original_quit_capability='UNKNOWN', error=self.error,
            quit_enter_binding='NOT_REQUESTED' if self.source_quit_test else 'UNKNOWN_UI_INPUT_TRIAL',
            source_quit_test=self.source_quit_test,
            confirm_window_close=self.confirm_window_close, close_enter_claims=self.close_enter_claims,
            background_requested=self.background,
            desktop_isolation='OWNED_NON_INPUT_DESKTOP' if self.background else 'NONE',
            desktop_owner_retained=self._retained_background_desktop is not None,
            primary_thread_desktop_required=self.background,
            primary_thread_desktop_verified=self.primary_thread_desktop_verified,
            primary_thread_desktop_probe=self.primary_thread_desktop_probe,
            primary_thread_desktop_proof=self.primary_thread_desktop_proof,
            cursor_focus_global_input=False, direct_packet_sender=False)

    def save(self): _atomic(self.path, self.summary(), 4096, output_only=True)

    def reset_idle(self, reason):
        self.land_since = self.idle_key = self.idle_last_good = None
        self.idle_paused, self.idle_reason = False, reason
        self.alive_rx = self.alive_tx = False

    def close_requested(self, count):
        if not (self.confirm_window_close and (self.hold_complete or self.close_after_failure) and count > 0): return
        try:
            need(self.close_started is None, 'WINDOW_CLOSE_ALREADY_ARMED')
            self.reader.validate()
            self.close_hwnd, self.close_started = self.current_window(), self.clock()
            self.save()
        except Exception as error:
            self.close_input_failed = True
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.save()

    def confirm_close(self, row, broker):
        if (not self.confirm_window_close or self.close_started is None or self.close_input_failed
                or self.close_enter_claims >= 2 or self.clock() - self.close_started < .75): return
        try:
            if self.close_enter_claims:
                scene = row.get('memory', {}).get('scene', {})
                if not (self.monitor.samples > self.close_enter_sample and scene.get('status') == 'OBSERVED'
                        and scene.get('current') == 'Quit' and scene.get('pending') == 'none'
                        and broker.realm.quit_report()['source_quit_response_drained'] is True): return
            self.reader.validate()
            need(self.current_window() == self.close_hwnd, 'CURRENT_PRIMARY_WINDOW_CHANGED')
            self.close_enter_claims += 1
            self.close_enter_sample = self.monitor.samples
            self.actions.append(dict(command='WindowCloseEnter' if self.close_enter_claims == 1 else 'QuitEnter',
                                     status='CLAIMED_NO_RETRY', invoked=None))
            self.save()
            post = self.owner.native.u.PostMessageW
            post.argtypes, post.restype = (W.HWND, W.UINT, W.WPARAM, W.LPARAM), W.BOOL
            if self.background:
                self.background_post(self.close_hwnd, 0x100, 0x0d, 0x001c0001, return_pair=True)
            else:
                for message, bits in ((0x100, 0x001c0001), (0x101, 0xc01c0001)):
                    self.reader.validate()
                    need(self.current_window() == self.close_hwnd, 'CURRENT_PRIMARY_WINDOW_CHANGED')
                    need(post(self.close_hwnd, message, 0x0d, bits), 'OWNED_RETURN_POST_FAILED')
            self.reader.validate()
            need(self.current_window() == self.close_hwnd, 'CURRENT_PRIMARY_WINDOW_CHANGED')
            self.actions[-1]['status'] = 'POSTED_UI_EFFECT_UNKNOWN'
            self.save()
        except Exception as error:
            self.close_input_failed = True
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.save()  # A failed or partial pair is never retried; existing close grace continues.

    def diagnostic(self, leaf, event):
        try: row = _closed_health_json(self.owner.directory / leaf)
        except FileNotFoundError: return False
        if row is None: return False
        need(row.get('schema') == 'own-cp34-auto-ok-v1'
             and type(row.get('pid')) is int and row['pid'] == self.owner.child.pid
             and type(row.get('birth')) is int and row['birth'] == int(self.owner.child.identity['birth'])
             and row.get('candidate_sha256') == IMAGE_SHA, 'FROZEN_CALLBACK_IDENTITY_REQUIRED')
        need(row.get('event') == event and row.get('success') is True
             and type(row.get('reason')) is int and row['reason'] == 0, 'FROZEN_CALLBACK_REFUSED')
        return True

    def background_desktop(self, *, bind=False):
        """Bind after owner.prepare/reader.bind, then reject replacement/loss."""
        owner, desktop = self.owner, self.owner.private_desktop
        need(self.background and getattr(owner, 'background', False) is True and not owner.internal
             and not owner.closed and type(desktop) is launcher.PrivateDesktop,
             'OWNED_BACKGROUND_MANUAL_DESKTOP_REQUIRED')
        self.reader.validate()
        need(self._retained_background_desktop is not None or bind,
             'BACKGROUND_DESKTOP_RUNTIME_BIND_REQUIRED')
        need(self._retained_background_desktop is None or desktop is self._retained_background_desktop,
             'BACKGROUND_RETAINED_DESKTOP_CHANGED')
        desktop.verify_non_input()
        self._retained_background_desktop = desktop
        return desktop

    def current_window(self):
        owner = self.owner
        need(owner.validate(owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        desktop = None
        if self.background:
            self.primary_thread_desktop_verified = False
            self.primary_thread_desktop_proof = None
            desktop = self.background_desktop()
            probe = desktop.probe_thread(owner.child.tid)
            self.primary_thread_desktop_probe = dict(probe)
            need(probe.get('status') == 'UNKNOWN'
                 or probe.get('status') == 'OBSERVED' and probe.get('matches_private') is True,
                 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH')
        rows = owner.native.windows(owner.child)
        user, choices = owner.native.u, []
        user.GetClientRect.argtypes, user.GetClientRect.restype = (W.HWND, C.POINTER(W.RECT)), W.BOOL
        for row in rows:
            if row.get('visible') is not True: continue
            rect = W.RECT()
            need(owner.native.owned_hwnd(owner.child, row['hwnd']) and user.GetClientRect(row['hwnd'], C.byref(rect)),
                 'CURRENT_PRIMARY_CLIENT_RECT_REQUIRED')
            if 320 <= rect.right - rect.left <= 7680 and 200 <= rect.bottom - rect.top <= 4320:
                choices.append(row)
        # Native's visible/client-area selector has only one eligible candidate;
        # its install file has no HWND/TID, so no prior-binding proof is claimed.
        need(len(choices) == 1, 'ONE_CURRENT_PRIMARY_GAME_WINDOW_REQUIRED')
        need(choices[0].get('class') == 'GLFW30', 'CURRENT_GAME_WINDOW_CLASS_REQUIRED')
        hwnd = choices[0]['hwnd']
        if self.background:
            need(desktop.contains(hwnd), 'BACKGROUND_CURRENT_WINDOW_DESKTOP_REQUIRED')
        thread_pid = W.DWORD()
        need(owner.native.owned_hwnd(owner.child, hwnd)
             and user.GetWindowThreadProcessId(hwnd, C.byref(thread_pid)) == owner.child.tid
             and thread_pid.value == owner.child.pid, 'CURRENT_PRIMARY_UI_THREAD_REQUIRED')
        if self.background:
            need(self.background_desktop() is desktop and owner.validate(owner.child) is True,
                 'BACKGROUND_CURRENT_WINDOW_OWNER_CHANGED')
            self.primary_thread_desktop_verified = True
            self.primary_thread_desktop_proof = 'OWNED_DESKTOP_WINDOW_THREAD'
        return hwnd

    def background_post(self, hwnd, message, layout, parameter, *, return_pair=False):
        """Frozen pointer message, once, only on a fresh joined desktop thread."""
        owner, desktop = self.owner, self.background_desktop()
        child, process, job = owner.child, owner.owner_handle, owner.owner_job
        identity = (child.pid, str(child.identity['birth']), owner.image_sha, child.tid)
        need(not return_pair or self.background_confirm_allowed
             and (message, layout, parameter) == (0x100, 0x0d, 0x001c0001),
             'BACKGROUND_EXACT_RETURN_PAIR_REQUIRED')
        payloads = ((message, layout, parameter), (0x101, 0x0d, 0xc01c0001)) if return_pair else ((message, layout, parameter),)
        errors, posted = [], []
        def dispatch(handle):
            try:
                with desktop._lease(), desktop._joined_thread(handle):
                    need(owner.private_desktop is desktop and owner.child is child and not owner.closed
                         and getattr(owner, 'background', False) is True and not owner.internal
                         and process and job and owner.owner_handle == process == child.process
                         and owner.owner_job == job == child.job
                         and (child.pid, str(child.identity['birth']), owner.image_sha, child.tid) == identity,
                         'BACKGROUND_FROZEN_OWNER_CHANGED')
                    self.reader.validate()
                    owner.verify_sources()
                    need(owner.validate(child) is True and desktop.contains(hwnd)
                         and self.current_window() == hwnd, 'BACKGROUND_FROZEN_WINDOW_CHANGED')
                    desktop.verify_non_input()
                    for message, layout, parameter in payloads:
                        self.reader.validate()
                        need(owner.validate(child) is True and self.current_window() == hwnd,
                             'BACKGROUND_FROZEN_WINDOW_CHANGED')
                        need(owner.native.u.PostMessageW(hwnd, message, layout, parameter),
                             'FROZEN_MESSAGE_POST_FAILED')
                    posted.append(True)
            except BaseException as error:
                errors.append(error)
        with desktop._lease() as handle:
            thread = threading.Thread(target=dispatch, args=(handle,), name='local-baseline-frozen-message')
            thread.start(); thread.join()
        if errors:
            raise errors[0]
        need(bool(posted), 'BACKGROUND_FROZEN_MESSAGE_NOT_POSTED')

    def saved_store(self, broker):
        _, refs = broker.realm.store.snapshot()
        need(refs == frozenset((broker.realm.profile_name,))
             and broker.realm.store.select(broker.realm.profile_name)[0] == broker.realm.profile_uid,
             'ONE_FRESH_SAVED_UID_REQUIRED')
        return refs

    def saved_slot(self, broker):
        refs = self.saved_store(broker)
        games = [item[1] for item in broker.realm._account_bound.values()]
        need(len(games) == 1 and games[0].roster.references == refs and games[0].selection is None,
             'ONE_FRESH_OWNED_SAVED_SLOT_REQUIRED')

    def post(self, command, broker):
        owner = self.owner
        if command == 'Login': self.saved_store(broker)
        else: self.saved_slot(broker)
        self.reader.validate()
        bound = binding(owner, self.reader, 'Login' if command == 'Login' else 'Select',
                        require_slot_zero=command == 'SelectOK')
        if bound is None: return False  # No claim/post occurred; a later fresh sample may bind.
        layout, button = bound
        hwnd, user = self.current_window(), owner.native.u
        for name, args, result in (
            ('RegisterWindowMessageW', (W.LPCWSTR,), W.UINT),
            ('PostMessageW', (W.HWND, W.UINT, W.WPARAM, W.LPARAM), W.BOOL)):
            fn = getattr(user, name); fn.argtypes, fn.restype = args, result
        message = int(user.RegisterWindowMessageW(MESSAGES[command]))
        need(0xc000 <= message <= 0xffff, 'FROZEN_MESSAGE_REQUIRED')
        self.actions.append(dict(command=command, status='CLAIMED_NO_RETRY', invoked=None))
        self.save()  # Durable once-claim before any message side effect.
        self.reader.validate()
        need(owner.validate(owner.child) is True and owner.native.owned_hwnd(owner.child, hwnd),
             'CURRENT_PRIMARY_WINDOW_CHANGED')
        parameter = 0 if command == 'SelectOK' else button
        if self.background:
            self.background_post(hwnd, message, layout, parameter)
        else:
            need(user.PostMessageW(hwnd, message, layout, parameter), 'FROZEN_MESSAGE_POST_FAILED')
        self.actions[-1]['status'] = 'POSTED_CALLBACK_UNKNOWN'
        self.reader.validate()
        need(self.current_window() == hwnd, 'CURRENT_PRIMARY_WINDOW_CHANGED')
        self.save()
        return True

    def tick(self, row, broker, state):
        if state == 'CLOSING':
            self.confirm_close(row, broker)
            return
        if state != 'RUNNING' or self.stop.is_set(): return
        if self.monitor.samples == self.last_sample: return
        self.last_sample = self.monitor.samples
        try:
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            if self.background:
                self.background_desktop(bind=True)
            scene = row.get('memory', {}).get('scene', {})
            if self.stage != 'IDLE' and not (scene.get('status') == 'OBSERVED' and scene.get('pending') == 'none'
                                            and scene.get('root_ready') is True): return
            if self.stage == 'LOGIN':
                if scene.get('current') != 'Login': return
                if not self.diagnostic('auto-ok-install.json', 'HOOK_INSTALLED'): return
                if self.post('Login', broker): self.stage = 'WAIT_LOGIN'
            elif self.stage == 'WAIT_LOGIN':
                if not self.diagnostic(*EVENTS['Login']): return
                self.actions[-1].update(status='RETURNED', invoked=True)
                if not any(e[0] == 'tx' and e[2] == 0x264 for e in broker.policy.log): return
                if scene.get('current') != 'CharacterSelect': return
                if self.post('Slot', broker): self.stage = 'WAIT_SLOT'
            elif self.stage == 'WAIT_SLOT':
                if not self.diagnostic(*EVENTS['Slot']): return
                self.actions[-1].update(status='RETURNED', invoked=True)
                need(scene.get('current') == 'CharacterSelect', 'CURRENT_CHARACTER_SELECT_REQUIRED')
                if self.post('SelectOK', broker): self.stage = 'WAIT_LAND'
            elif self.stage == 'WAIT_LAND':
                if not self.diagnostic(*EVENTS['SelectOK']): return
                self.actions[-1].update(status='RETURNED', invoked=True)
                if scene.get('current') == 'Land': self.stage = 'IDLE'
            elif self.stage == 'IDLE':
                world = row.get('memory', {}).get('world', {})
                move = row.get('memory', {}).get('move_state', {})
                services = list(broker.realm._movement.values())
                need(len(services) == 1, 'ONE_SELECTED_BASELINE_SERVICE_REQUIRED')
                service = services[0][1]
                snapshot, now = service.snapshot(), self.clock()
                key = (snapshot.uid, snapshot.map_id, snapshot.packed, service.requests_received,
                       service.committed, id(services[0][0]), id(service))
                expected = grid_pair(snapshot.metadata()['grid'])
                grid = grid_pair(world.get('grid_words'))
                transform = move.get('transform', {})
                current, predicted = grid_pair(transform.get('current_grid')), grid_pair(transform.get('predicted_grid'))
                known_land = (scene.get('status') == 'OBSERVED' and scene.get('current') == 'Land'
                              and scene.get('pending') == 'none' and scene.get('root_ready') is True)
                if self.idle_key is not None and key != self.idle_key:
                    self.reset_idle('IDLE_AUTHORITY_OR_COUNTER_CHANGED')
                if service.requests_received != 0 or service.committed != 0:
                    self.reset_idle('IDLE_MOVEMENT_COUNTER_NONZERO'); self.save(); return
                if (scene.get('status') == 'OBSERVED' and
                    (scene.get('current') not in ('Land', 'unknown', None)
                     or scene.get('pending') not in ('none', 'unknown', None)
                     or scene.get('root_ready') is False)):
                    self.reset_idle('IDLE_OBSERVED_SCENE_CHANGED'); self.save(); return
                if ((world.get('status') == 'OBSERVED' and
                     ((type(world.get('my_player_uid')) is int and world['my_player_uid'] != key[0])
                      or (grid is not None and grid != expected)))
                    or (move.get('status') == 'OBSERVED' and
                        any(value is not None and value != expected for value in (current, predicted)))):
                    self.reset_idle('IDLE_OBSERVED_POSITION_MISMATCH'); self.save(); return
                good = (known_land and world.get('status') == 'OBSERVED'
                        and world.get('stable_double_read') is True
                        and world.get('my_player_uid') == key[0]
                        and grid is not None and grid == expected
                        and move.get('status') == 'OBSERVED' and move.get('stable_double_read') is True
                        and current == grid and predicted == grid)
                # Wall-time hold plus a current valid sample; intermediate UNKNOWN stays unknown.
                if not good:
                    self.idle_paused, self.idle_reason = True, 'IDLE_CURRENT_STATE_UNKNOWN_OR_UNSTABLE'
                    self.save(); return
                if self.land_since is None:
                    self.idle_key, self.land_since = key, now
                    self.idle_event_start = broker.policy.events
                    self.alive_rx = self.alive_tx = False
                self.idle_last_good, self.idle_paused, self.idle_reason = now, False, 'IDLE_GOOD'
                events = list(broker.policy.log)
                fresh = events[max(0, self.idle_event_start - (broker.policy.events - len(events))):]
                self.alive_rx |= any(e[0] == 'rx' and e[2] == 0x4e2a for e in fresh)
                self.alive_tx |= any(e[0] == 'tx' and e[2] == 0x4f57 for e in fresh)
                if self.clock() - self.land_since >= self.idle_seconds and self.alive_rx and self.alive_tx:
                    self.hold_complete, self.stage = True, 'WINDOW_CLOSE_REQUESTED'
                    self.stop.set()  # Existing manual run_session requests owned WM_CLOSE once.
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.stage = 'UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()  # No retry, message fallback, pointer or payload logging.


class ContinuousMoveScenario(Scenario):
    """Explicit adjacent goals through the product's real command ingress.

    The launcher and ManualMoveCommands own exact collision admission, native
    calls and fresh COMMITTED proofs. This observer chooses tile candidates.
    Its ordinary manual launch makes no background/focus guarantee.
    """
    background_profile = BACKGROUND_PROFILE
    source_quit_profile = SOURCE_QUIT_PROFILE

    def __init__(self, *args, retain_move_goal=False, **kwargs):
        need(type(retain_move_goal) is bool, 'EXPLICIT_RETAIN_MOVE_GOAL_BOOL_REQUIRED')
        self.retain_move_goal = retain_move_goal
        self.expected_move_count = 1 if retain_move_goal else 2
        self.observed_move_counters = None
        profile = (self.source_quit_profile if kwargs.get('source_quit_test', False) else self.background_profile
                   if kwargs.get('background', False) else CONTINUOUS_PROFILE)
        super().__init__(*args, profile=profile, **kwargs)
        need(not self.confirm_window_close or self.background_confirm_allowed,
             'NO_QUIT_ENTER_TRIAL_IN_CONTINUOUS_RUN')
        self.path = self.monitor.directory / 'manual-continuous-move-scenario.json'
        self.moves, self.origin, self.move_bound = [], None, None
        self.move_origin, self.move_counter_base = None, (0, 0, 0)
        self.move_started = None
        self.move_event_start = None
        self.last_client_known = False
        self.neighbor_pending = None

    def summary(self):
        row = dict(super().summary(), continuous_moves=self.moves, original_position=self.origin,
                    continuous_moves_complete=len(self.moves) == self.expected_move_count and all(
                        move['status'] == 'COMMITTED' for move in self.moves),
                    retain_move_goal=self.retain_move_goal,
                    movement_destination=('FIRST_ADJACENT_GOAL' if self.retain_move_goal else
                        'SAVED_ATTACK_APPROACH_END' if self.move_origin is not None and self.move_origin != self.origin
                        else 'SAVED_ORIGIN'),
                    expected_move_counters=dict(requests=self.move_counter_base[0] + self.expected_move_count,
                        commits=self.move_counter_base[1] + self.expected_move_count,
                        corrections=self.move_counter_base[2]),
                    observed_move_counters=self.observed_move_counters,
                    final_saved_position=self.moves[-1].get('saved') if self.moves else None,
                    last_monitor_client_known=self.last_client_known,
                    ingress='PRODUCT_COMMAND_REQUEST_MOVEGOAL',
                    background_launch_guaranteed=False,
                    collision_admission='PRODUCT_MANUAL_MOVE_COMMANDS_ONLY',
                    quit_is_movement_success_gate=False)
        if self.move_counter_base != (0, 0, 0):
            # Raw totals remain in the broker. This compact trial projection
            # separates explicit goals from already committed native approach.
            row['move_counter_scope'] = 'EXPLICIT_GOALS_AFTER_APPROACH'
            row['expected_move_counters'] = dict(requests=self.expected_move_count,
                commits=self.expected_move_count, corrections=0)
            if self.observed_move_counters is not None:
                row['observed_move_counters'] = {key: self.observed_move_counters[key] - self.move_counter_base[index]
                    for index, key in enumerate(('requests', 'commits', 'corrections'))}
            row['continuous_moves'] = [dict(move, before=[value - self.move_counter_base[index]
                for index, value in enumerate(move['before'])]) for move in self.moves]
            for key in ('background_launch_guaranteed', 'quit_is_movement_success_gate'):
                row.pop(key)  # Redundant constants; keep the original 4096-B sink.
        return row

    def current(self, row, broker, *, require_idle=True):
        from tools.local_original_session import edge
        binding = launcher.current_manual_binding(broker)
        need(binding is not None, 'CURRENT_SELECTED_MOVE_BINDING_REQUIRED')
        writer = binding.writer
        services = list(broker.realm._movement.values())
        need(len(services) == 1 and type(services[0]) is tuple and len(services[0]) == 3,
             'ONE_CURRENT_SELECTED_MOVE_3TUPLE_REQUIRED')
        actual_writer, service, connection_id = services[0]
        need(actual_writer is writer and broker.realm.service(writer) is service,
             'CURRENT_SELECTED_MOVE_SERVICE_REQUIRED')
        if self.move_bound is None:
            self.move_bound = (writer, service, connection_id)
        need(writer is self.move_bound[0] and service is self.move_bound[1]
             and connection_id == self.move_bound[2], 'CONTINUOUS_MOVE_BINDING_CHANGED')
        position = service.snapshot()
        need(broker.realm.positions.restore(position) == position, 'CURRENT_MOVE_SAVE_REQUIRED')
        proof = broker.realm.edge_passability
        need(type(proof) is edge.EdgeAdapter and proof.reader is self.reader
             and service._edge_passability is proof, 'CURRENT_RETAINED_EDGE_REQUIRED')
        scene, world, motion = (row.get('memory', {}).get(key, {}) for key in ('scene', 'world', 'move_state'))
        transform = motion.get('transform', {})
        action, controller, navigation = (motion.get(key, {}) for key in ('action', 'controller', 'navigation'))
        grid = (position.word0, position.word1)
        known = (scene.get('status') == 'OBSERVED' and scene.get('current') == 'Land'
            and scene.get('pending') == 'none' and scene.get('root_ready') is True
            and world.get('status') == 'OBSERVED' and world.get('stable_double_read') is True
            and world.get('my_player_uid') == position.uid
            and world.get('map_requested_i32') == world.get('map_resolved_i32') == position.map_id
            and grid_pair(world.get('grid_words')) == grid)
        known = known and (not require_idle or (motion.get('status') == 'OBSERVED' and motion.get('stable_double_read') is True
            and motion.get('source_contract_valid') is True and motion.get('actor_uid') == position.uid
            and all(item.get('status') == 'OBSERVED' for item in (transform, action, controller, navigation))
            and grid_pair(transform.get('current_grid')) == grid
            and grid_pair(transform.get('predicted_grid')) == grid
            and controller.get('command_present') is False and navigation.get('active') is False
            and action.get('queue_status') == 'OBSERVED' and type(action.get('queue_count')) is int
            and action['queue_count'] == 0 and action.get('busy_source_eval', {}).get('status') == 'EVALUATED'
            and action['busy_source_eval'].get('value') is False))
        self.last_client_known = known
        self.observed_move_counters = dict(requests=service.requests_received,
            commits=service.committed, corrections=service.corrections_prepared)
        return service, position, proof, known

    def submit(self, row, broker):
        from tools.local_original_session import commands, movement
        service, position, proof, known = self.current(row, broker)
        writer, _, connection = self.move_bound
        game = broker.realm.registry.resolve(writer)
        refs = (writer, service, connection, game, game.selection, position, proof,
                broker.realm.positions, self.reader,
                (service.requests_received, service.committed, service.corrections_prepared),
                broker.realm, broker.realm.registry)
        if self.neighbor_pending is not None:
            started, original = self.neighbor_pending
            need(all(refs[index] is original[index] for index in (0, 1, 3, 4, 5, 6, 7, 8, 10, 11))
                 and refs[2] == original[2] and refs[9] == original[9],
                 'CONTINUOUS_NEIGHBOR_AUTHORITY_CHANGED')
            need(self.clock() - started < 10, 'CONTINUOUS_NEIGHBOR_WINDOW_EXPIRED')
            world = row.get('memory', {}).get('world', {})
            motion = row.get('memory', {}).get('move_state', {})
            transform = motion.get('transform', {})
            need(all(value is None or type(value) is int and value == position.uid
                     for value in (world.get('my_player_uid'), motion.get('actor_uid'),
                                   motion.get('character_data', {}).get('own_uid')))
                 and motion.get('character_data', {}).get('own_uid_matches_actor') is not False
                 and all(value is None or type(value) is int and value == position.map_id
                         for value in (world.get('map_requested_i32'), world.get('map_resolved_i32')))
                 and all(grid is None or grid == (position.word0, position.word1) for grid in
                         (grid_pair(world.get('grid_words')), grid_pair(transform.get('current_grid')),
                          grid_pair(transform.get('predicted_grid'))))
                 and world.get('source_segment_grid_relation_match') is not False,
                 'CONTINUOUS_NEIGHBOR_KNOWN_CONTRADICTION')
        if not known:
            return
        if self.neighbor_pending is None:
            self.neighbor_pending = (self.clock(), refs)
        if self.origin is None:
            need((service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0),
                 'FRESH_CONTINUOUS_MOVE_COUNTERS_REQUIRED')
            self.origin = position.metadata()
            self.land_since = self.clock()
            self.idle_last_good = self.land_since
            self.idle_reason = 'CONTINUOUS_CONSUMER_PROOF_SEPARATE_FROM_MONITOR_IDLE'
            self.move_event_start = broker.policy.events
        neighbors = proof.tile_neighbors(position.uid, position.map_id, position.packed)
        admitted = (neighbors.get('status') in ('OBSERVED', 'OBSERVED_PARTIAL')
             and neighbors.get('stable_double_read') is True and neighbors.get('uid') == position.uid
             and neighbors.get('map_id') == position.map_id
             and grid_pair(neighbors.get('start_grid')) == (position.word0, position.word1))
        if not admitted:
            diagnostic = {key: neighbors.get(key) if type(neighbors.get(key)) is str
                          and len(neighbors[key]) <= 128 else None for key in ('status', 'reason')}
            diagnostic['stable_double_read'] = (neighbors.get('stable_double_read')
                if type(neighbors.get('stable_double_read')) is bool else None)
            for key, lower, upper in (('uid', 1, (1 << 64) - 1), ('map_id', 0, (1 << 31) - 1),
                    *((key, 0, (1 << 32) - 1) for key in ('typed_bytes_requested', 'source_code_bytes_requested',
                       'byte_limit', 'refused_read_bytes', 'shortfall_at_refused_read',
                       'required_total_bytes', 'total_shortfall_bytes'))):
                value = neighbors.get(key)
                diagnostic[key] = value if type(value) is int and lower <= value <= upper else None
            grid = grid_pair(neighbors.get('start_grid'))
            diagnostic['start_grid'] = list(grid) if grid is not None and all(0 <= n <= 65535 for n in grid) else None
            _atomic(self.monitor.directory / 'manual-continuous-neighbor-observation.json', diagnostic, 2048, output_only=True)
        # The same retained selection/Position is rechecked after every query,
        # including UNKNOWN; an UNKNOWN result never supplies a candidate.
        self.reader.validate()
        need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        again, fresh, same_proof, ready = self.current(row, broker)
        need(again is service and fresh is position and same_proof is proof and ready
             and broker.realm.registry.resolve(writer) is game and game.selection is refs[4]
             and broker.realm.positions is refs[7] and broker.realm is refs[10]
             and broker.realm.registry is refs[11]
             and (service.requests_received, service.committed, service.corrections_prepared) == refs[9],
             'CONTINUOUS_MOVE_AUTHORITY_CHANGED')
        need(self.clock() - self.neighbor_pending[0] < 10, 'CONTINUOUS_NEIGHBOR_WINDOW_EXPIRED')
        if (neighbors.get('status') == 'UNKNOWN' and neighbors.get('reason') == 'EDGE_TYPED_READ_CHANGED'
                and neighbors.get('stable_double_read') is False
                and type(neighbors.get('uid')) is int and neighbors['uid'] == position.uid
                and type(neighbors.get('map_id')) is int and neighbors['map_id'] == position.map_id
                and grid_pair(neighbors.get('start_grid')) == (position.word0, position.word1)
                and len(neighbors.get('directions', [])) == 8
                and all(item.get('status') == 'UNKNOWN' and item.get('reason') == 'EDGE_TYPED_READ_CHANGED'
                        and item.get('blocked') is None and item.get('flags_u16') is None
                        for item in neighbors['directions'])):
            return
        need(admitted, 'FRESH_CONTINUOUS_NEIGHBOR_UNKNOWN')
        target = grid_pair((self.move_origin or self.origin)['grid']) if self.moves else None
        choices = [item for item in neighbors.get('directions', [])
                   if item.get('status') == 'OBSERVED' and item.get('blocked') is False
                   and (target is None or grid_pair(item.get('grid_target')) == target)]
        need(bool(choices), 'NO_CURRENT_CLEAR_CONTINUOUS_EDGE')
        choice = choices[0]
        target, direction = grid_pair(choice.get('grid_target')), choice.get('direction')
        need(target is not None and type(direction) is int and 0 <= direction < 8
             and all(0 <= n <= 65535 for n in target)
             and (target[0] - position.word0, target[1] - position.word1) == movement.authority.DELTAS[direction],
             'CURRENT_CONTINUOUS_ADJACENT_TARGET_REQUIRED')
        self.reader.validate()
        again, fresh, same_proof, ready = self.current(row, broker)
        need(again is service and fresh is position and same_proof is proof and ready,
             'CONTINUOUS_MOVE_AUTHORITY_CHANGED')
        need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        need(self.clock() - self.neighbor_pending[0] < 10, 'CONTINUOUS_NEIGHBOR_WINDOW_EXPIRED')
        sequence = self.move_sequence()
        request = dict(schema=commands.REQUEST_SCHEMA, sequence=sequence, command='MoveGoal',
                       uid=position.uid, x=target[0], y=target[1])
        self.moves.append(dict(sequence=sequence, status='CLAIMED_NO_RETRY', initial=position.metadata(),
                               target=list(target), target_selection='COHERENT_TILE_CANDIDATE',
                               collision_admission='NOT_YET_CONSUMED',
                               before=[service.requests_received, service.committed,
                                                          service.corrections_prepared]))
        self.move_started, self.stage = self.clock(), 'MOVE_WAIT'
        self.save()  # Once-claim before publishing; no direct native message/request.
        _atomic(self.monitor.directory / 'command.request.json', request, 1024)
        self.moves[-1]['status'] = 'PUBLISHED'
        self.neighbor_pending = None  # A later MoveGoal gets its own first window.

    def move_sequence(self):
        return len(self.moves) + 1

    def collect(self, row, broker):
        from tools.local_original_session import commands
        service, position, _proof, _known = self.current(row, broker)
        move = self.moves[-1]
        try:
            result = _closed_health_json(self.monitor.directory / 'command.result.json')
        except FileNotFoundError:
            result = None
        if result is not None:
            need(result.get('schema') == commands.RESULT_SCHEMA and type(result.get('sequence')) is int
                 and result['sequence'] <= move['sequence'], 'PRODUCT_MOVE_RESULT_SCHEMA_OR_SEQUENCE')
            if result['sequence'] == move['sequence']:
                need(result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                     and result.get('cleanup_required') is not True, 'PRODUCT_MOVE_RESULT_UNKNOWN')
                move['consumer_status'] = result['status']
                phase = result.get('phase')
                move['collision_admission'] = ('COMMITTED' if result['status'] == 'COMMITTED'
                    else phase if phase in ('ADMISSION', 'NATIVE_WAIT') else 'UNKNOWN')
                if result['status'] == 'COMMITTED':
                    expected = tuple(move['target'])
                    counters = (service.requests_received, service.committed, service.corrections_prepared)
                    before = move['before']
                    need((position.uid, position.map_id) == (self.origin['uid'], self.origin['map_id'])
                         and (position.word0, position.word1) == expected
                         and counters == (before[0] + 1, before[1] + 1, before[2]),
                         'PRODUCT_COMMITTED_AUTHORITY_COUNTER_MISMATCH')
                    move.update(status='COMMITTED', actual=position.metadata(), saved=position.metadata(),
                                consumer_fresh_client_idle_proven=True)
                    self.stage = 'MOVE_READY' if len(self.moves) < self.expected_move_count else 'MOVE_PROVEN'
                    return
        need(self.clock() - self.move_started < 15, 'PRODUCT_MOVE_RESULT_OBSERVATION_EXPIRED')

    def tick(self, row, broker, state):
        if state == 'CLOSING':
            self.confirm_close(row, broker)
            return
        if self.stage in ('LOGIN', 'WAIT_LOGIN', 'WAIT_SLOT', 'WAIT_LAND'):
            super().tick(row, broker, state)
            if self.stage == 'IDLE':
                self.stage = 'MOVE_READY'
                self.save()
            return
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate()
            if self.background:
                self.background_desktop(bind=True)
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh_sample = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'MOVE_READY' and fresh_sample:
                self.submit(row, broker)
            elif self.stage == 'MOVE_WAIT':
                self.collect(row, broker)  # Consumer samples share the monitor's 2 Hz budget.
            if self.move_event_start is not None:
                events = list(broker.policy.log)
                offset = self.move_event_start - (broker.policy.events - len(events))
                need(0 <= offset <= len(events), 'CONTINUOUS_ALIVE_EVENTS_DROPPED')
                self.alive_rx |= any(e[0] == 'rx' and e[2] == 0x4e2a for e in events[offset:])
                self.alive_tx |= any(e[0] == 'tx' and e[2] == 0x4f57 for e in events[offset:])
            if (self.stage == 'MOVE_PROVEN' and self.clock() - self.land_since >= self.idle_seconds
                    and self.alive_rx and self.alive_tx):
                service, position, _proof, _known = self.current(row, broker)
                need(position.metadata() == self.moves[-1]['saved']
                     and (service.requests_received, service.committed, service.corrections_prepared)
                     == (self.move_counter_base[0] + self.expected_move_count,
                         self.move_counter_base[1] + self.expected_move_count, self.move_counter_base[2]),
                     'CONTINUOUS_HOLD_AUTHORITY_CHANGED')
                self.hold_complete = True
                self.finish_hold(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.stage = 'CONTINUOUS_MOVE_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()

    def finish_hold(self, row, broker):
        self.stage = 'WINDOW_CLOSE_REQUESTED'
        self.stop.set()


def attack_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import feature_config, npc
    from tools.local_native_login_spawn_render_retry_runtime import spawn_hook
    need(type(config) is feature_config.Features and len(config.spawns) == 1
         and config.attack_policy == feature_config.ATTACK_INTENT_POLICY
         and config.interval_ns is config.motion_policy is config.goal_policy is config.goal is None,
         'SCENARIO_EXPLICIT_STATIONARY_ATTACK_TARGET_REQUIRED')
    if config.attack_feedback is not None:
        from tools.local_original_session.attack_session import FeedbackConfig
        need(type(config.attack_feedback) is FeedbackConfig,
             'SCENARIO_EXPLICIT_ATTACK_FEEDBACK_CONFIG_REQUIRED')
    if inventory:
        from tools.local_original_session import inventory as inv
        need(config.inventory_policy == inv.POLICY and type(config.inventory_frame) is bytes,
             'SCENARIO_EXPLICIT_INVENTORY_ADD_REQUIRED')
        inv.validate_frame(config.inventory_frame)
        need(config.inventory_delivery_policy == (feature_config.LOCAL_WORLD_READY_ONCE
             if auto_inventory else None), 'SCENARIO_INVENTORY_DELIVERY_MODE_REQUIRED')
        if auto_inventory:
            from tools.local_original_session import inventory_store
            need(config.inventory_store_policy == inventory_store.POLICY,
                 'SCENARIO_AUTO_INVENTORY_STORE_REQUIRED')
    else:
        need(not auto_inventory and config.inventory_policy is config.inventory_frame is None,
             'SCENARIO_EXPLICIT_STATIONARY_ATTACK_TARGET_REQUIRED')
    profile = spawn_hook.profiles()[0]
    npc.prepare(config.spawns, self_uid=profile.fields[1])  # Reuse actual CP73 UID/source validation.
    return config


class AttackTargetScenario(ContinuousMoveScenario):
    """One validated intent, then explicit move/return in one sequence space."""
    background_profile = ATTACK_PROFILE
    background_confirm_allowed = True
    close_after_failure = True
    inventory_required = False
    auto_inventory = False
    ATTACK_SEQUENCE = 1

    def __init__(self, *args, features, **kwargs):
        need(kwargs.get('background') is True, 'SCENARIO_ATTACK_BACKGROUND_REQUIRED')
        self.features = attack_configuration(features, inventory=self.inventory_required,
                                             auto_inventory=self.auto_inventory)
        self.attack = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN', combat_effect='UNKNOWN')
        if self.features.attack_feedback is not None:
            self.attack['feedback'] = dict(state='NOT_REQUESTED', prepared=0, reserved=0,
                write_attempted=0, drained=0, proof_scope='TRANSPORT_DRAIN_ONLY',
                action_snapshot='UNKNOWN', start='UNKNOWN', render='UNKNOWN', hp='UNKNOWN')
            self.attack['attack_observations'] = {}
        self.last_consumer_result = None
        self.attack_started = self.attack_session = self.attack_before = None
        self.attack_projection = None
        self.attack_counters, self.attack_events = (0, 0, 0), None
        self.approach_commits = 0
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-attack-target-scenario.json'

    def summary(self):
        attack = self.attack
        if self.features.attack_feedback is not None:
            attack = dict(attack, attack_observations={stage: item['status']
                for stage, item in self.attack['attack_observations'].items()},
                attack_observations_file='manual-attack-feedback-observations.json')
        return dict(super().summary(), attack_target=attack,
                    last_consumer_result=self.last_consumer_result,
                    move_readiness='FRESH_SELECTED_WORLD_ONLY_CONSUMER_OWNS_TYPED_ADMISSION')

    def save(self):
        if self.features.attack_feedback is not None:
            # Evidence output only: never a receipt, send authority or input.
            detail = dict(schema='manual-attack-feedback-observations-v1',
                    sequence=self.attack.get('sequence'), feedback=self.attack['feedback'],
                    attack_observations=self.attack['attack_observations'])
            if self.approach_commits:
                detail['approach'] = dict(initial_grid=self.origin['grid'],
                    end_grid=list(self.attack_projection[1].metadata()['grid']), commits=self.approach_commits,
                    baseline=list(self.attack_counters), total=self.observed_move_counters)
            _atomic(self.monitor.directory / 'manual-attack-feedback-observations.json', detail, 2048, output_only=True)
        return super().save()

    def current(self, row, broker, **kwargs):
        return super().current(row, broker, require_idle=False)

    def move_sequence(self):
        return len(self.moves) + self.ATTACK_SEQUENCE + 1

    def _result(self):
        from tools.local_original_session.commands import RESULT_SCHEMA
        try:
            result = _closed_health_json(self.monitor.directory / 'command.result.json')
        except FileNotFoundError:
            return None
        if result is None:
            return None
        need(result.get('schema') == RESULT_SCHEMA and type(result.get('sequence')) is int
             and result['sequence'] >= 1, 'SCENARIO_ATTACK_RESULT_SCHEMA_REQUIRED')
        self.last_consumer_result = {key: value for key in
            ('status', 'reason', 'phase', 'command', 'proof_scope', 'combat_effect', 'sequence', 'native_attempted')
            for value in (result.get(key),)
            if value is None or type(value) in (int, bool) or type(value) is str and len(value) <= 120}
        diagnostic = result.get('inventory_pre_write')
        if (type(diagnostic) is dict and set(diagnostic) in (
                {'pre_write_stage', 'typed_read_requests', 'changed_read'},
                {'pre_write_stage', 'typed_read_requests', 'changed_read', 'refused_read'})):
            try:
                encoded = json.dumps(diagnostic, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
                if len(encoded.encode('utf-8')) <= 768:
                    self.last_consumer_result['inventory_pre_write'] = json.loads(encoded)
            except (TypeError, ValueError, OverflowError):
                pass  # Optional output cannot replace the original failure.
        if (self.features.attack_feedback is not None and result.get('command') == 'AttackTarget'
                and result['sequence'] == self.ATTACK_SEQUENCE):
            self.capture_attack_observations(result)
        return result

    def capture_attack_observations(self, result):
        """Copy only the consumer's bounded scalars; never sample or infer Start."""
        observations = result.get('attack_observations')
        if observations is None:
            return
        need(type(observations) is dict, 'SCENARIO_ATTACK_OBSERVATION_SHAPE_REQUIRED')
        keys = {'status', 'reason', 'at_ns', 'strict_idle', 'current_attack', 'queued_attack',
                'current_pair', 'queued_pair', 'damaged_current', 'damaged_queued'}
        byte_ranges = {'combined_bytes': (0, 24576), 'refused_bytes': (1, 4096),
                       'shortfall_bytes': (1, 4096)}
        for stage in ('pre_command', 'post_feedback', 'next_strict_idle'):
            if stage not in observations:
                continue
            snapshot = observations[stage]
            need(type(snapshot) is dict and set(snapshot) in (keys, keys | byte_ranges.keys())
                 and snapshot.get('status') in ('OBSERVED', 'UNKNOWN')
                 and (snapshot.get('reason') is None or type(snapshot.get('reason')) is str
                      and len(snapshot['reason']) <= 120)
                 and type(snapshot.get('at_ns')) is int and snapshot['at_ns'] >= 0
                 and all(snapshot.get(key) is None or type(snapshot.get(key)) is bool
                         for key in keys - {'status', 'reason', 'at_ns'}),
                 'SCENARIO_ATTACK_OBSERVATION_SHAPE_REQUIRED')
            # Diagnostic scalars describe the existing sample; they never grant
            # a read budget. Old 10-key UNKNOWN snapshots remain literal.
            need(all(snapshot[key] is None or type(snapshot[key]) is int and lo <= snapshot[key] <= hi
                     for key, (lo, hi) in byte_ranges.items() if key in snapshot),
                 'SCENARIO_ATTACK_OBSERVATION_BYTE_DIAGNOSTIC_REQUIRED')
            self.attack['attack_observations'][stage] = dict(snapshot)
        post = self.attack['attack_observations'].get('post_feedback')
        if post is not None and post['status'] == 'OBSERVED':
            matching = (post['current_attack'] is True and post['current_pair'] is True
                        or post['queued_attack'] is True and post['queued_pair'] is True)
            self.attack['feedback']['action_snapshot'] = ('MATCHING_CURRENT_OR_QUEUED'
                if matching else 'MATCHING_ATTACK_NOT_OBSERVED')

    def capture_attack_transport(self):
        if self.features.attack_feedback is None or self.attack_session is None:
            return
        session, feedback = self.attack_session, self.attack['feedback']
        # metadata()/current_intent() revalidate source/target; this observer
        # only retains the actual session's existing transport counters.
        state = session._feedback_state
        need(type(state) is str and len(state) <= 32, 'SCENARIO_ATTACK_FEEDBACK_STATE_REQUIRED')
        feedback['state'] = state
        for key in ('prepared', 'reserved', 'write_attempted', 'drained'):
            value = getattr(session, 'feedback_' + key)
            need(type(value) is int and value >= 0, 'SCENARIO_ATTACK_FEEDBACK_COUNTER_REQUIRED')
            feedback[key] = value

    def require_attack_feedback(self, result):
        self.capture_attack_transport()
        feedback, snapshots = self.attack['feedback'], self.attack['attack_observations']
        need(feedback['state'] == 'DRAINED'
             and all(feedback[key] == 1 for key in ('prepared', 'reserved', 'write_attempted', 'drained')),
             'SCENARIO_ATTACK_FEEDBACK_DRAIN_PROOF_REQUIRED')
        need(result.get('observation_scope') == 'READONLY_ACTION_SNAPSHOTS'
             and type(result.get('attack_observations')) is dict
             and set(result['attack_observations']) == {'pre_command', 'post_feedback', 'next_strict_idle'}
             and set(snapshots) == {'pre_command', 'post_feedback', 'next_strict_idle'}
             and all(item['status'] == 'OBSERVED' for item in snapshots.values())
             and snapshots['pre_command']['strict_idle'] is True
             and snapshots['post_feedback']['strict_idle'] is None
             and snapshots['next_strict_idle']['strict_idle'] is True
             and snapshots['pre_command']['at_ns'] < snapshots['post_feedback']['at_ns']
                 < snapshots['next_strict_idle']['at_ns'],
             'SCENARIO_ATTACK_FEEDBACK_SNAPSHOTS_REQUIRED')

    def submit_attack(self, row, broker):
        from tools.local_original_session import attack, attack_session, commands
        service, position, _proof, known = self.current(row, broker)
        if not known:
            return
        spawn, = self.features.spawns
        actual = broker.realm._npc_spawns
        need(len(actual) == 1 and actual[0][0] == spawn and spawn.uid != position.uid
             and spawn.map_id == position.map_id and id(self.move_bound[0]) not in broker.realm._npc_motion,
             'SCENARIO_SAME_STATIONARY_NPC_TARGET_REQUIRED')
        session = broker._attack_session
        need(type(session) is attack_session.AttackSession and broker.realm._attack_session is session
             and session.policy == self.features.attack_policy and not session.closed and not session.fatal
             and session.feedback == self.features.attack_feedback
             and session.accepted_count == 0
             and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0),
             'SCENARIO_CURRENT_FRESH_ATTACK_SESSION_REQUIRED')
        self.attack_session, self.attack_before = session, session.accepted_count
        self.attack_projection = attack.AttackTargets._project(session.targets, self.move_bound[0],
                                                              attack.AttackRequest(spawn.uid))
        self.attack_events = broker.policy.events
        if self.features.attack_feedback is not None:
            self.capture_attack_transport()
            need(self.attack['feedback']['state'] == 'NOT_REQUESTED'
                 and all(self.attack['feedback'][key] == 0
                         for key in ('prepared', 'reserved', 'write_attempted', 'drained')),
                 'SCENARIO_FRESH_ATTACK_FEEDBACK_REQUIRED')
        if self.origin is None:
            self.origin, self.land_since = position.metadata(), self.clock()
            self.idle_last_good = self.land_since
            self.idle_reason = 'CONSUMER_TYPED_ADMISSION_SEPARATE_FROM_SCENARIO_WORLD'
            self.move_event_start = broker.policy.events
        need(position.metadata() == self.origin, 'SCENARIO_ATTACK_AUTHORITY_CHANGED')
        request = dict(schema=commands.REQUEST_SCHEMA, sequence=self.ATTACK_SEQUENCE, command='AttackTarget',
                       uid=position.uid, target_uid=spawn.uid, map_id=position.map_id)
        self.attack.update(status='CLAIMED_NO_RETRY', sequence=self.ATTACK_SEQUENCE, uid=position.uid,
                           target_uid=spawn.uid, map_id=position.map_id)
        self.stage, self.attack_started = 'ATTACK_WAIT', self.clock()
        self.save()
        _atomic(self.monitor.directory / 'command.request.json', request, 1024)
        self.attack['status'] = 'PUBLISHED'

    def collect_attack(self, row, broker):
        from tools.local_original_session import attack
        service, position, _proof, _known = self.current(row, broker)
        need(broker._attack_session is self.attack_session, 'SCENARIO_ATTACK_AUTHORITY_CHANGED')
        counters = (service.requests_received, service.committed, service.corrections_prepared)
        result = self._result()
        if position is not self.attack_projection[1] or counters != self.attack_counters:
            need(self.features.attack_feedback is not None and result is not None
                 and result.get('sequence') == self.ATTACK_SEQUENCE
                 and result.get('native_attempted') is True and result.get('command') == 'AttackTarget',
                 'SCENARIO_ATTACK_AUTHORITY_CHANGED')
            projection, actual, events = attack.AttackTargets.observe_committed_approach(self.attack_session.targets,
                self.move_bound[0], attack.AttackRequest(self.attack['target_uid']),
                self.attack_projection, self.attack_counters, self.attack_events)
            need(projection[1] is position and actual == counters, 'SCENARIO_ATTACK_AUTHORITY_CHANGED')
            self.attack_projection, self.attack_counters, self.attack_events = projection, actual, events
            self.approach_commits += 1
        self.capture_attack_transport()
        if result is not None:
            need(result['sequence'] <= self.ATTACK_SEQUENCE, 'SCENARIO_ATTACK_RESULT_SEQUENCE_REQUIRED')
            if result['sequence'] < self.ATTACK_SEQUENCE:
                need(self.clock() - self.attack_started < 15, 'SCENARIO_ATTACK_OBSERVATION_EXPIRED')
                return  # Prior inventory result while the shared 2 Hz ingress waits for its slot.
            need(result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                 and result.get('cleanup_required') is not True, 'SCENARIO_ATTACK_CONSUMER_REFUSED')
            self.attack['consumer_status'] = result['status']
            if result['status'] == 'COMMITTED':
                need(result.get('command') == 'AttackTarget'
                     and result.get('proof_scope') == 'VALIDATED_ATTACK_INTENT_ONLY'
                     and result.get('combat_effect') == 'UNKNOWN' and result.get('native_attempted') is True
                     and self.attack_session.accepted_count == self.attack_before + 1,
                     'SCENARIO_ATTACK_INTENT_PROOF_REQUIRED')
                if self.features.attack_feedback is not None:
                    self.require_attack_feedback(result)
                    intent = self.attack_session.current_intent()
                    need(intent is not None and intent._bound._writer is self.move_bound[0]
                         and intent._bound.attacker is position
                         and (intent._bound.target_uid, intent._bound.map_id) ==
                             (self.attack['target_uid'], position.map_id),
                         'SCENARIO_ATTACK_INTENT_PROOF_REQUIRED')
                self.move_origin, self.move_counter_base = position.metadata(), counters
                self.attack.update(status='COMMITTED', proof_scope='VALIDATED_ATTACK_INTENT_ONLY')
                self.stage = 'MOVE_READY'
                return
        need(self.clock() - self.attack_started < 15, 'SCENARIO_ATTACK_OBSERVATION_EXPIRED')

    def collect(self, row, broker):
        self._result()  # Preserve actual strict-consumer phase/reason even on refusal.
        return super().collect(row, broker)

    def finalize(self):
        # run_session may terminate on the consumer's UNKNOWN before another
        # monitor tick. Preserve its refusal; never invent a late success.
        try:
            self.capture_attack_transport()
            result = self._result()
            if result is not None and result.get('status') == 'UNKNOWN':
                self.error = self.error or 'SCENARIO_STRICT_CONSUMER_REFUSED'
        except Exception as error:
            self.error = self.error or launcher.safe_error_code(error) or type(error).__name__

    def tick(self, row, broker, state):
        if state == 'CLOSING':
            self.confirm_close(row, broker)
            return
        if self.stage in ('LOGIN', 'WAIT_LOGIN', 'WAIT_SLOT', 'WAIT_LAND'):
            super().tick(row, broker, state)
            if self.stage == 'MOVE_READY':
                self.stage = 'ATTACK_READY'
                self.save()
            return
        if self.stage not in ('ATTACK_READY', 'ATTACK_WAIT'):
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh_sample = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'ATTACK_READY' and fresh_sample:
                self.submit_attack(row, broker)
            elif self.stage == 'ATTACK_WAIT':
                self.collect_attack(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.stage = 'ATTACK_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()


class InventoryAddScenario(AttackTargetScenario):
    """One confirmed public ADD, then attack/move/return in that sequence space."""
    inventory_required = True
    ATTACK_SEQUENCE = 2
    INVENTORY_SEQUENCE = 1

    def __init__(self, *args, **kwargs):
        self.inventory = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN',
                              render='UNKNOWN', equipped='UNKNOWN', save='UNKNOWN')
        self.inventory_started = None
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-attack-inventory-scenario.json'

    def summary(self):
        return dict(super().summary(), inventory_add=self.inventory)

    def submit_attack(self, row, broker):
        need(self.inventory['status'] == 'COMMITTED', 'SCENARIO_INVENTORY_FIRST_REQUIRED')
        return super().submit_attack(row, broker)

    def collect(self, row, broker):
        need(self.inventory['status'] == 'COMMITTED', 'SCENARIO_INVENTORY_FIRST_REQUIRED')
        super().collect(row, broker)

    def inventory_authority(self, row, broker):
        service, position, _proof, known = self.current(row, broker)
        need(self.attack['status'] == 'NOT_REQUESTED' and not self.moves
             and (self.origin is None or position.metadata() == self.origin)
             and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0)
             and broker._inventory_frame == self.features.inventory_frame,
             'SCENARIO_INVENTORY_INITIAL_SELECTED_AUTHORITY_REQUIRED')
        return position, known

    def submit_inventory(self, row, broker):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        position, known = self.inventory_authority(row, broker)
        if not known:
            return
        need(self.inventory['status'] == 'NOT_REQUESTED', 'SCENARIO_INVENTORY_ONCE_REQUIRED')
        self.origin, self.land_since = position.metadata(), self.clock()
        self.idle_last_good = self.land_since
        self.idle_reason = 'CONSUMER_TYPED_ADMISSION_SEPARATE_FROM_SCENARIO_WORLD'
        self.move_event_start = broker.policy.events
        request = dict(schema=REQUEST_SCHEMA, sequence=self.INVENTORY_SEQUENCE, command='AddInventory',
                       uid=position.uid, map_id=position.map_id)
        self.inventory.update(status='CLAIMED_NO_RETRY', sequence=self.INVENTORY_SEQUENCE)
        self.inventory_started, self.stage = self.clock(), 'INVENTORY_WAIT'
        self.save()
        _atomic(self.monitor.directory / 'command.request.json', request, 1024)
        self.inventory['status'] = 'PUBLISHED'

    def collect_inventory(self, row, broker):
        self.inventory_authority(row, broker)
        result = self._result()
        if result is not None:
            need(result['sequence'] <= self.INVENTORY_SEQUENCE, 'SCENARIO_INVENTORY_RESULT_SEQUENCE_REQUIRED')
            if result['sequence'] == self.INVENTORY_SEQUENCE:
                self.inventory['consumer_status'] = result.get('status')
                if result.get('status') in ('PENDING', 'UNKNOWN'):
                    self.inventory['status'] = result['status']
                for key in ('phase', 'reason', 'proof_scope', 'client_inventory', 'transport_proof_scope',
                            'render', 'equipped', 'save', 'all_17_wire_fields_proven',
                            'wire_field18_bytes_observed', 'catalog_live_materialization_proven'):
                    value = result.get(key)
                    if key in result and (value is None or type(value) is bool or type(value) is str and len(value) <= 120):
                        self.inventory[key] = value
                need(result.get('command') == 'AddInventory'
                     and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                     and result.get('cleanup_required') is not True, 'SCENARIO_INVENTORY_CONSUMER_REFUSED')
                if result['status'] == 'COMMITTED':
                    need(result.get('phase') == 'CLIENT_CONFIRMED'
                         and result.get('proof_scope') == 'CLIENT_ITEM_ROW_SCALARS_ONLY'
                         and result.get('client_inventory') == 'ROW_5_SCALARS_MATCHED'
                         and result.get('transport_proof_scope') == 'TRANSPORT_DRAIN_ONLY'
                         and result.get('invoked') is True
                         and all(result.get(key) == 'UNKNOWN' for key in ('render', 'equipped', 'save'))
                         and all(result.get(key) is False for key in ('all_17_wire_fields_proven',
                             'wire_field18_bytes_observed', 'catalog_live_materialization_proven')),
                         'SCENARIO_INVENTORY_CLIENT_ROW_PROOF_REQUIRED')
                    self.inventory['status'] = 'COMMITTED'
                    self.stage = 'ATTACK_READY'
                    return
        need(self.clock() - self.inventory_started < 15, 'SCENARIO_INVENTORY_OBSERVATION_EXPIRED')

    def finalize(self):
        super().finalize()
        if self.last_consumer_result is not None and self.last_consumer_result.get('command') == 'AddInventory':
            if self.last_consumer_result.get('status') == 'UNKNOWN':
                self.inventory.update(status='UNKNOWN', reason=self.last_consumer_result.get('reason'),
                                      phase=self.last_consumer_result.get('phase'))

    def tick(self, row, broker, state):
        if self.stage in ('LOGIN', 'WAIT_LOGIN', 'WAIT_SLOT', 'WAIT_LAND'):
            super().tick(row, broker, state)
            if self.stage == 'ATTACK_READY':
                self.stage = 'INVENTORY_READY'
                self.save()
            return
        if self.stage not in ('INVENTORY_READY', 'INVENTORY_WAIT') or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'INVENTORY_READY' and fresh:
                self.submit_inventory(row, broker)
            elif self.stage == 'INVENTORY_WAIT':
                self.collect_inventory(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.stage = 'INVENTORY_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()


class InventoryAutoScenario(InventoryAddScenario):
    """Observe the product's one restored-row delivery; publish no Add request."""
    auto_inventory = True

    def __init__(self, *args, **kwargs):
        self.auto_inventory_binding = self.auto_inventory_frame = None
        super().__init__(*args, **kwargs)
        self.inventory['delivery_policy'] = self.features.inventory_delivery_policy

    def inventory_authority(self, row, broker):
        from tools.local_original_session.inventory_store import InventoryStore
        service, position, _proof, known = self.current(row, broker)
        need(self.attack['status'] == 'NOT_REQUESTED' and not self.moves
             and (self.origin is None or position.metadata() == self.origin)
             and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0),
             'SCENARIO_INVENTORY_INITIAL_SELECTED_AUTHORITY_REQUIRED')
        if not known and self.auto_inventory_binding is None:
            return position, False
        selected, frame = broker._inventory_selection_binding, broker._inventory_frame
        need(type(broker._inventory_store) is InventoryStore and broker._inventory_restored is True
             and type(selected) is tuple and len(selected) == 11
             and selected[0] is self.move_bound[0] and type(frame) is bytes,
             'SCENARIO_AUTO_INVENTORY_RESTORED_SELECTION_REQUIRED')
        # This source-owned object guard performs no restore, query or send.
        # The adopted saved literal may differ from the configured fallback.
        broker._inventory_selection_frame_current(self.move_bound[0], selected[1], frame)
        if self.auto_inventory_binding is None:
            self.auto_inventory_binding, self.auto_inventory_frame = selected, frame
        need(selected is self.auto_inventory_binding and frame is self.auto_inventory_frame,
             'SCENARIO_AUTO_INVENTORY_SELECTION_CHANGED')
        return position, True

    def submit_inventory(self, row, broker):
        position, known = self.inventory_authority(row, broker)
        if not known:
            return
        need(self.inventory['status'] == 'NOT_REQUESTED', 'SCENARIO_INVENTORY_ONCE_REQUIRED')
        self.origin, self.land_since = position.metadata(), self.clock()
        self.idle_last_good = self.land_since
        self.idle_reason = 'CONSUMER_TYPED_ADMISSION_SEPARATE_FROM_SCENARIO_WORLD'
        self.move_event_start = broker.policy.events
        self.inventory.update(status='WAITING_AUTOMATIC_DELIVERY', sequence=self.INVENTORY_SEQUENCE,
                              selected_frame_restored=True)
        self.inventory_started, self.stage = self.clock(), 'INVENTORY_WAIT'
        self.save()  # Only the existing product poll may claim/send the restored row.

    def _result(self):
        result = super()._result()
        if result is not None and result.get('command') == 'AddInventory':
            need(result['sequence'] == self.INVENTORY_SEQUENCE
                 and type(result.get('last_sequence')) is int
                 and result['last_sequence'] == self.INVENTORY_SEQUENCE
                 and result.get('delivery_policy') == self.features.inventory_delivery_policy
                 and result.get('same_broker_reselection_delivery') ==
                     (self.features.inventory_reselection_policy or 'UNSUPPORTED')
                 and result.get('automatic_retry') is False,
                 'SCENARIO_AUTO_INVENTORY_PUBLIC_RESULT_REQUIRED')
            self.inventory['same_broker_reselection_delivery'] = self.features.inventory_reselection_policy or 'UNSUPPORTED'
        return result


class UseItemScenario(InventoryAutoScenario):
    """One source-validated item intent between Attack2 and Move4/return5."""
    source_quit_profile = USE_ITEM_PROFILE
    USE_SEQUENCE = 3

    def __init__(self, *args, use_item_only=False, **kwargs):
        need(type(use_item_only) is bool, 'SCENARIO_USE_ITEM_ONLY_BOOL_REQUIRED')
        self.use_item_only = use_item_only
        if use_item_only:
            # Auto Add is public1; no skipped Attack/noop claims in this mode.
            self.USE_SEQUENCE = 2
        from tools.local_original_session.item_use_session import POLICY
        need(kwargs.get('source_quit_test') is True and kwargs.get('retain_move_goal', False) is False,
             'SCENARIO_USE_ITEM_ROUNDTRIP_SOURCE_QUIT_REQUIRED')
        self.use_item = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN', accepted_count=0, cs0960=0,
            use_effect='UNKNOWN', ack='UNKNOWN', equipped='UNKNOWN', render='UNKNOWN', hp='UNKNOWN', save='UNKNOWN')
        self.use_started = self.use_session = self.use_event_start = self.use_received_base = None
        super().__init__(*args, **kwargs)
        need(self.features.item_use_policy == POLICY, 'SCENARIO_USE_ITEM_POLICY_REQUIRED')
        if use_item_only:
            self.idle_seconds = 0
        self.path = self.monitor.directory / 'manual-use-item-scenario.json'

    def summary(self):
        row = super().summary()
        # The opt-in evidence file retains the detailed consumer refusal/limits.
        # Avoid duplicating that row in the original bounded 4096-byte summary.
        row.pop('last_consumer_result')
        row['use_item'] = {key: self.use_item[key] for key in
            ('status', 'proof_scope', 'accepted_count', 'cs0960')}
        row['use_item'].update(sequence=self.USE_SEQUENCE, observation_file='manual-use-item-observation.json')
        if getattr(self, 'use_item_only', False):
            row['use_item_only'] = True
            row['verification_scope'] = 'INITIAL_SAVED_ROW_USE_INTENT_QUIT'
        return row

    def save(self):
        _atomic(self.monitor.directory / 'manual-use-item-observation.json',
            dict(schema='manual-use-item-observation-v1', use_item=self.use_item,
                 last_consumer_result=self.last_consumer_result), 2048, output_only=True)
        return super().save()

    def move_sequence(self):
        return len(self.moves) + self.USE_SEQUENCE + 1

    def collect_inventory(self, row, broker):
        super().collect_inventory(row, broker)
        if self.use_item_only and self.stage == 'ATTACK_READY':
            self.inventory['trial_role'] = 'REQUIRED_USE_ITEM_PREPARATION'
            self.stage = 'USE_READY'

    def collect_attack(self, row, broker):
        super().collect_attack(row, broker)
        if self.stage == 'MOVE_READY':
            self.stage = 'USE_READY'

    def use_authority(self, row, broker):
        from tools.local_original_session import inventory, item_use_session
        from tools.local_original_session.broker import PersistentBroker
        service, position, _proof, known = self.current(row, broker)
        attack_ready = (self.attack['status'] == 'NOT_REQUESTED' and self.hold_complete is False
                       and self.move_counter_base == (0, 0, 0) and self.USE_SEQUENCE == 2
                       if self.use_item_only else self.attack['status'] == 'COMMITTED')
        need(self.inventory['status'] == 'COMMITTED' and attack_ready and not self.moves
             and position.metadata() == (self.move_origin or self.origin)
             and (service.requests_received, service.committed, service.corrections_prepared) == self.move_counter_base,
             'SCENARIO_USE_ITEM_INITIAL_AUTHORITY_REQUIRED')
        selected, frame, writer = broker._inventory_selection_binding, broker._inventory_frame, self.move_bound[0]
        need(broker._inventory_restored is True and selected is self.auto_inventory_binding
             and frame is self.auto_inventory_frame and type(selected) is tuple and len(selected) == 11
             and selected[0] is writer and type(frame) is bytes,
             'SCENARIO_USE_ITEM_RESTORED_SELECTION_CHANGED')
        PersistentBroker._inventory_selection_frame_current(broker, writer, selected[1], frame)
        item = inventory.validate_frame(frame)  # Actual restored literal, never config fallback.
        session = broker._item_use_session
        need(type(session) is item_use_session.ItemUseSession and broker.realm._item_use_session is session
             and session.broker is broker and not session.closed and session.policy == self.features.item_use_policy
             and broker.policy.item_use_intent is True
             and type(session.accepted_count) is int and 0 <= session.accepted_count <= 1,
             'SCENARIO_USE_ITEM_CURRENT_SESSION_REQUIRED')
        if self.use_session is not None:
            need(session is self.use_session and self.use_item['item_identifier'] == item.identifier
                 and (self.use_item['uid'], self.use_item['map_id']) == (position.uid, position.map_id),
                 'SCENARIO_USE_ITEM_CURRENT_REQUEST_CHANGED')
        return position, known, session, selected[1], item.identifier

    def submit_use_item(self, row, broker):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        position, known, session, claim, identifier = self.use_authority(row, broker)
        if not known:
            return
        need(self.use_item['status'] == 'NOT_REQUESTED' and session.accepted_count == 0,
             'SCENARIO_USE_ITEM_ONCE_FRESH_REQUIRED')
        self.reader.validate()
        again = self.use_authority(row, broker)
        need(again[0] is position and again[1] and again[2] is session and again[3] is claim
             and again[4] == identifier, 'SCENARIO_USE_ITEM_AUTHORITY_CHANGED')
        request = dict(schema=REQUEST_SCHEMA, sequence=self.USE_SEQUENCE, command='UseItem',
                       uid=position.uid, item_identifier=identifier, map_id=position.map_id)
        self.use_session, self.use_started = session, self.clock()
        self.use_event_start, self.use_received_base = broker.policy.events, claim['policy_row'].received
        self.use_item.update(status='CLAIMED_NO_RETRY', sequence=self.USE_SEQUENCE,
                             uid=position.uid, item_identifier=identifier, map_id=position.map_id)
        self.stage = 'USE_WAIT'
        self.save()
        _atomic(self.monitor.directory / 'command.request.json', request, 1024)
        self.use_item['status'] = 'PUBLISHED'

    def collect_use_item(self, row, broker):
        _position, _known, session, claim, _identifier = self.use_authority(row, broker)
        self.use_item['accepted_count'] = session.accepted_count
        events = list(broker.policy.log)
        offset = self.use_event_start - (broker.policy.events - len(events))
        need(0 <= offset <= len(events), 'SCENARIO_USE_ITEM_RX_EVENTS_DROPPED')
        received = [event for event in events[offset:] if event[0] == 'rx'
                    and event[1] == claim['peer']['endpoint_port'] and event[2] == 0x0960]
        self.use_item['cs0960'] = len(received)
        result = self._result()
        if result is not None:
            need(result['sequence'] <= self.USE_SEQUENCE, 'SCENARIO_USE_ITEM_RESULT_SEQUENCE_REQUIRED')
            if result['sequence'] == self.USE_SEQUENCE:
                for key in ('status', 'reason', 'phase', 'native_attempted'):
                    value = result.get(key)
                    if value is None or type(value) is bool or type(value) is str and len(value) <= 120:
                        self.use_item['consumer_' + key] = value
                need(result.get('command') == 'UseItem' and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                     and result.get('cleanup_required') is not True and result.get('automatic_retry') is False,
                     'SCENARIO_USE_ITEM_CONSUMER_REFUSED')
                if result['status'] == 'COMMITTED':
                    intent = session._current  # Read-only same-writer correlation, never native authority.
                    need(result.get('phase') == 'COMMITTED' and result.get('native_attempted') is True
                         and result.get('proof_scope') == 'VALIDATED_ITEM_USE_INTENT_ONLY'
                         and result.get('reason') is None and result.get('cleanup_required') is False
                         and type(result.get('last_sequence')) is int and result['last_sequence'] == self.USE_SEQUENCE
                         and all(result.get(key) == 'UNKNOWN' for key in ('use_effect', 'ack', 'equipped', 'render', 'save'))
                         and session.accepted_count == 1 and len(received) == 1
                         and intent is not None and intent.writer is self.move_bound[0]
                         and claim['policy_row'].received > self.use_received_base,
                         'SCENARIO_USE_ITEM_RECEIVED_INTENT_PROOF_REQUIRED')
                    self.use_item.update(status='COMMITTED', proof_scope='VALIDATED_ITEM_USE_INTENT_ONLY')
                    if self.use_item_only:
                        self.stage = 'USE_ITEM_COMPLETE_STOP_REQUESTED'
                        self.stop.set()  # Existing launcher/source Quit cleanup, no hold/move/restart.
                    else:
                        self.stage = 'MOVE_READY'
                    return
        need(self.clock() - self.use_started < 15, 'SCENARIO_USE_ITEM_OBSERVATION_EXPIRED')

    def submit(self, row, broker):
        need(self.use_item['status'] == 'COMMITTED', 'SCENARIO_USE_ITEM_FIRST_REQUIRED')
        return super().submit(row, broker)

    def finalize(self):
        super().finalize()
        if self.last_consumer_result is not None and self.last_consumer_result.get('command') == 'UseItem':
            if self.last_consumer_result.get('status') == 'UNKNOWN':
                self.use_item.update(status='UNKNOWN', reason=self.last_consumer_result.get('reason'),
                                     phase=self.last_consumer_result.get('phase'))

    def tick(self, row, broker, state):
        if self.stage not in ('USE_READY', 'USE_WAIT') or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'USE_READY' and fresh:
                self.submit_use_item(row, broker)
            elif self.stage == 'USE_WAIT':
                self.collect_use_item(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.use_item['status'], self.stage = 'UNKNOWN', 'USE_ITEM_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()


class InventoryUpdateScenario(InventoryAutoScenario):
    """One explicit local raw-field update, then the original move/return/Quit."""
    source_quit_profile = INVENTORY_UPDATE_PROFILE
    UPDATE_SEQUENCE = 3

    def __init__(self, *args, **kwargs):
        from tools.local_original_session.broker import INVENTORY_UPDATE_POLICY
        need(kwargs.get('source_quit_test') is True and kwargs.get('retain_move_goal', False) is False,
             'SCENARIO_INVENTORY_UPDATE_ROUNDTRIP_SOURCE_QUIT_REQUIRED')
        self.inventory_update = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN', storage='UNKNOWN',
            tx0965=0, ack='UNKNOWN', effect='UNKNOWN', equipped='UNKNOWN', render='UNKNOWN', hp='UNKNOWN')
        self.update_refs = self.update_old = self.update_operation = self.update_started = None
        self.update_event_start = self.update_sent_base = None
        super().__init__(*args, **kwargs)
        need(self.features.inventory_update_policy == INVENTORY_UPDATE_POLICY,
             'SCENARIO_INVENTORY_UPDATE_POLICY_REQUIRED')
        self.path = self.monitor.directory / 'manual-inventory-update-scenario.json'

    def summary(self):
        row = super().summary()
        row.pop('last_consumer_result')
        for key in ('move_readiness', 'ingress', 'collision_admission'):
            row.pop(key)  # Opt-in omits redundant constants; individual move proofs stay intact.
        row['inventory_update'] = {key: self.inventory_update.get(key) for key in
            ('status', 'before_rawf4', 'after_rawf4', 'proof_scope', 'storage', 'tx0965')}
        row['inventory_update'].update(sequence=self.UPDATE_SEQUENCE,
            observation_file='manual-inventory-update-observation.json')
        return row

    def save(self):
        _atomic(self.monitor.directory / 'manual-inventory-update-observation.json',
            dict(schema='manual-inventory-update-observation-v1', inventory_update=self.inventory_update,
                 last_consumer_result=self.last_consumer_result), 2048, output_only=True)
        return super().save()

    def move_sequence(self):
        return len(self.moves) + self.UPDATE_SEQUENCE + 1

    def collect_attack(self, row, broker):
        super().collect_attack(row, broker)
        if self.stage == 'MOVE_READY':
            self.stage = 'UPDATE_READY'

    def update_current(self, row, broker, *, strict=False):
        from tools.local_original_session import inventory
        from tools.local_original_session.inventory_store import InventoryStore
        from tools.local_original_session.broker import PersistentBroker, INVENTORY_UPDATE_POLICY
        service, position, _proof, known = (ContinuousMoveScenario.current(self, row, broker)
            if strict else self.current(row, broker))
        need(type(broker) is PersistentBroker and broker.inventory_update_policy == self.features.inventory_update_policy
             == INVENTORY_UPDATE_POLICY and broker.policy.inventory_update is True,
             'SCENARIO_INVENTORY_UPDATE_REAL_POLICY_REQUIRED')
        need(self.inventory['status'] == self.attack['status'] == 'COMMITTED' and not self.moves
             and position.metadata() == (self.move_origin or self.origin)
             and (service.requests_received, service.committed, service.corrections_prepared) == self.move_counter_base,
             'SCENARIO_INVENTORY_UPDATE_INITIAL_AUTHORITY_REQUIRED')
        writer, realm = self.move_bound[0], broker.realm
        game = realm.registry.resolve(writer)
        initial, selected = broker._inventory_frame, broker._inventory_selection_binding
        need(broker._inventory_restored is True and selected is self.auto_inventory_binding
             and type(selected) is tuple and len(selected) == 11 and selected[0] is writer
             and initial is self.auto_inventory_frame and broker._inventory_operation_frame is initial
             and type(broker._inventory_store) is InventoryStore
             and type(broker._inventory_service) is inventory.InventoryService
             and broker._inventory_attempted is True and broker._inventory_write_attempted is True
             and broker._inventory_service._claimed is True
             and broker._inventory_prewrite_refusal is None and broker._inventory_admission_expired is False,
             'SCENARIO_INVENTORY_UPDATE_INITIAL_BINDING_CHANGED')
        PersistentBroker._inventory_selection_frame_current(broker, writer, selected[1], initial)
        refs = (realm, realm.registry, game, service, position, game.selection,
                broker._inventory_service, self.reader, broker._inventory_store, selected,
                broker._inventory_delivery_authority, initial, broker._inventory_restore_only)
        if self.update_refs is not None:
            need(all(a is b for a, b in zip(refs, self.update_refs)),
                 'SCENARIO_INVENTORY_UPDATE_SELECTION_CHANGED')
        return position, known, refs, selected[1]

    def submit_inventory_update(self, row, broker):
        from tools.local_original_session import inventory
        from tools.local_original_session.commands import REQUEST_SCHEMA
        from tools.local_original_session.inventory_store import InventoryStore
        position, known, refs, claim = self.update_current(row, broker, strict=True)
        if not known:
            return
        need(self.inventory_update['status'] == 'NOT_REQUESTED' and broker._inventory_update_operation is None,
             'SCENARIO_INVENTORY_UPDATE_ONCE_REQUIRED')
        old = broker._inventory_current_frame
        item = inventory.validate_frame(old)
        before = dict(item.raw_fields)[4]
        need(type(before) is int and 0 <= before < (1 << 64) - 1,
             'SCENARIO_INVENTORY_UPDATE_FIELD4_OVERFLOW')
        need(old is self.auto_inventory_frame and InventoryStore.restore(refs[8], position.uid) == old,
             'SCENARIO_INVENTORY_UPDATE_CURRENT_STORED_FRAME_REQUIRED')
        self.reader.validate()
        again = self.update_current(row, broker, strict=True)
        need(again[0] is position and again[1] and all(a is b for a, b in zip(refs, again[2]))
             and broker._inventory_current_frame is old
             and InventoryStore.restore(refs[8], position.uid) == old,
             'SCENARIO_INVENTORY_UPDATE_PUBLICATION_CHANGED')
        request = dict(schema=REQUEST_SCHEMA, sequence=self.UPDATE_SEQUENCE, command='UpdateInventory',
            uid=position.uid, item_identifier=item.identifier, map_id=position.map_id, field4_u64=before + 1)
        self.update_refs, self.update_old, self.update_started = refs, old, self.clock()
        self.update_event_start, self.update_sent_base = broker.policy.events, claim['policy_row'].sent
        self.inventory_update.update(status='CLAIMED_NO_RETRY', sequence=self.UPDATE_SEQUENCE,
            uid=position.uid, item_identifier=item.identifier, map_id=position.map_id,
            before_rawf4=before, after_rawf4=before + 1)
        self.stage = 'UPDATE_WAIT'
        self.save()
        _atomic(self.monitor.directory / 'command.request.json', request, 1024)
        self.inventory_update['status'] = 'PUBLISHED'

    def collect_inventory_update(self, row, broker):
        from tools.local_original_session import inventory, inventory_update
        from tools.local_original_session.inventory_store import InventoryStore
        need(self.clock() - self.update_started < 15, 'SCENARIO_INVENTORY_UPDATE_OBSERVATION_EXPIRED')
        position, _known, refs, claim = self.update_current(row, broker)
        operation = broker._inventory_update_operation
        if operation is not None:
            need(type(operation) is dict and operation['writer'] is self.move_bound[0]
                 and operation['row'] is claim and operation['lock'] is claim['operation_lock']
                 and len(operation['refs']) == len(refs)
                 and all(a is b for a, b in zip(operation['refs'], refs)) and operation['old'] is self.update_old,
                 'SCENARIO_INVENTORY_UPDATE_OPERATION_CHANGED')
            if self.update_operation is None:
                self.update_operation = operation
            need(operation is self.update_operation, 'SCENARIO_INVENTORY_UPDATE_OPERATION_CHANGED')
            for key in ('phase', 'persist_attempted', 'persisted', 'write_attempted', 'drain_returned',
                        'post_owner_verified', 'sent_before', 'sent_after'):
                value = operation[key]
                need(value is None or type(value) is bool or type(value) is int and 0 <= value < (1 << 64)
                     or type(value) is str and value in ('CLAIMED', 'PERSISTING', 'PERSISTED', 'RESERVING',
                         'WRITE_ATTEMPTED', 'DRAINED', 'TERMINAL'),
                     'SCENARIO_INVENTORY_UPDATE_OPERATION_SCALAR_REQUIRED')
                self.inventory_update['operation_' + key] = value
        events = list(broker.policy.log)
        offset = self.update_event_start - (broker.policy.events - len(events))
        need(0 <= offset <= len(events), 'SCENARIO_INVENTORY_UPDATE_TX_EVENTS_DROPPED')
        sent = [event for event in events[offset:] if event[0] == 'tx'
                and event[1] == claim['peer']['endpoint_port'] and event[2] == 0x0965]
        self.inventory_update['tx0965'] = len(sent)
        result = self._result()
        if result is not None:
            need(result['sequence'] <= self.UPDATE_SEQUENCE, 'SCENARIO_INVENTORY_UPDATE_RESULT_SEQUENCE_REQUIRED')
            if result['sequence'] == self.UPDATE_SEQUENCE:
                for key in ('status', 'reason', 'phase', 'native_attempted'):
                    value = result.get(key)
                    if value is None or type(value) is bool or type(value) is str and len(value) <= 120:
                        self.inventory_update['consumer_' + key] = value
                need(result.get('command') == 'UpdateInventory' and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                     and result.get('cleanup_required') is not True and result.get('automatic_retry') is False,
                     'SCENARIO_INVENTORY_UPDATE_CONSUMER_REFUSED')
                if result['status'] == 'COMMITTED':
                    need(result.get('phase') == 'CLIENT_CONFIRMED' and result.get('native_attempted') is False
                         and result.get('cleanup_required') is False and result.get('reason') is None
                         and result.get('proof_scope') == 'CLIENT_ITEM_FIELD4_MATCHED'
                         and result.get('storage') == 'LOCAL_OPAQUE_FRAME_REPLACED'
                         and result.get('client_inventory') == 'ROW_5_SCALARS_MATCHED'
                         and all(result.get(key) == 'UNKNOWN' for key in ('ack', 'effect', 'equipped', 'render', 'hp')),
                         'SCENARIO_INVENTORY_UPDATE_CLIENT_PROOF_REQUIRED')
                    need(operation is not None and operation['phase'] == 'DRAINED'
                         and all(operation[key] is True for key in ('persist_attempted', 'persisted',
                             'write_attempted', 'drain_returned', 'post_owner_verified'))
                         and type(operation['sent_before']) is int and operation['sent_before'] >= self.update_sent_base
                         and type(operation['sent_after']) is int
                         and operation['sent_after'] == operation['sent_before'] + 1
                         and len(sent) == 1 and sent[0][3] == len(operation['wire'])
                         and broker._inventory_current_frame is operation['new'],
                         'SCENARIO_INVENTORY_UPDATE_DRAIN_PROOF_REQUIRED')
                    old_fields = dict(inventory.validate_frame(self.update_old).raw_fields)
                    new_fields = dict(inventory.validate_frame(operation['new']).raw_fields)
                    expected = dict(old_fields); expected[4] = self.inventory_update['after_rawf4']
                    wire_fields = dict(inventory_update.validate_frame(operation['wire']).raw_fields)
                    need(new_fields == expected and operation['changes'] == ((4, expected[4]),)
                         and wire_fields == {1: old_fields[1], 4: expected[4], 18: old_fields[18]}
                         and InventoryStore.restore(refs[8], position.uid) == operation['new'],
                         'SCENARIO_INVENTORY_UPDATE_CURRENT_FRAME_PROOF_REQUIRED')
                    self.inventory_update.update(status='COMMITTED', proof_scope='CLIENT_ITEM_FIELD4_MATCHED',
                                                 storage='LOCAL_OPAQUE_FRAME_REPLACED')
                    self.stage = 'MOVE_READY'
                    return
        need(self.clock() - self.update_started < 15, 'SCENARIO_INVENTORY_UPDATE_OBSERVATION_EXPIRED')

    def submit(self, row, broker):
        need(self.inventory_update['status'] == 'COMMITTED', 'SCENARIO_INVENTORY_UPDATE_FIRST_REQUIRED')
        return super().submit(row, broker)

    def finalize(self):
        super().finalize()
        if self.last_consumer_result is not None and self.last_consumer_result.get('command') == 'UpdateInventory':
            if self.last_consumer_result.get('status') == 'UNKNOWN':
                self.inventory_update.update(status='UNKNOWN', reason=self.last_consumer_result.get('reason'),
                                             phase=self.last_consumer_result.get('phase'))

    def tick(self, row, broker, state):
        if self.stage not in ('UPDATE_READY', 'UPDATE_WAIT') or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'UPDATE_READY' and fresh:
                self.submit_inventory_update(row, broker)
            elif self.stage == 'UPDATE_WAIT':
                self.collect_inventory_update(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.inventory_update['status'], self.stage = 'UNKNOWN', 'INVENTORY_UPDATE_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()


class SourceRestartScenario(InventoryAutoScenario):
    """Original world trial, then one restart ACK; new UI selection stays unknown."""
    background_profile = SOURCE_RESTART_PROFILE
    RESTART_SEQUENCE = 5

    def __init__(self, *args, **kwargs):
        from tools.local_original_session.restart import POLICY
        need((not kwargs.get('source_quit_test', False) or type(self) is SourceReselectScenario)
             and not kwargs.get('retain_move_goal', False) and not kwargs.get('confirm_window_close', False),
             'SCENARIO_SOURCE_RESTART_ROUNDTRIP_REQUIRED')
        self.source_restart = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN',
            ui='UNKNOWN', inventory_restore='UNKNOWN', land_quit='NOT_REQUESTED')
        self.restart_manual = self.restart_refs = self.restart_started = self.restart_events = None
        super().__init__(*args, **kwargs)
        need(self.features.restart_policy == POLICY, 'SCENARIO_SOURCE_RESTART_POLICY_REQUIRED')
        self.path = self.monitor.directory / 'manual-source-restart-scenario.json'

    def bind_runtime(self, runtime):
        from tools.local_original_session.manual_move_commands import ManualMoveCommands
        manual = runtime.manual
        need(type(runtime) is launcher.ProductFeatures and type(manual) is launcher.ManualMoveRequests
             and type(manual.consumer) is ManualMoveCommands and manual.consumer.reader is self.reader
             and manual.allow_source_restart is True and manual.consumer.allow_source_restart is True,
             'SCENARIO_SOURCE_RESTART_REAL_PRODUCER_REQUIRED')
        self.restart_manual = manual

    def summary(self):
        row = super().summary()
        row.pop('last_consumer_result')
        for key in ('move_readiness', 'ingress', 'collision_admission'):
            row.pop(key)  # Opt-in redundant constants; detailed original proofs stay intact.
        row['source_restart'] = {key: self.source_restart[key] for key in ('status', 'proof_scope')}
        row['source_restart'].update(sequence=self.RESTART_SEQUENCE,
            observation_file='manual-source-restart-observation.json')
        row.update(close_policy='OWNED_CLEANUP_AFTER_RESTART', quit_enter_binding='NOT_REQUESTED')
        return row

    def save(self):
        _atomic(self.monitor.directory / 'manual-source-restart-observation.json',
            dict(schema='manual-source-restart-observation-v1', source_restart=self.source_restart,
                 last_consumer_result=self.last_consumer_result), 2048, output_only=True)
        return super().save()

    def finish_hold(self, row, broker):
        self.stage = 'RESTART_READY'  # Wait for the next original fresh monitor slot.

    def submit_restart(self, row, broker):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        service, position, proof, known = self.current(row, broker)
        if not known: return
        manual = self.restart_manual
        focused = getattr(self, 'inventory_only', False)
        prepared = (type(self) is SourceReselectScenario and self.inventory_only is True
             and manual is not None and manual.sequence == self.INVENTORY_SEQUENCE
             and self.inventory['status'] == 'COMMITTED' and self.attack['status'] == 'NOT_REQUESTED'
             and not self.moves and self.hold_complete is False and position.metadata() == self.origin
             and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0)) if focused else (
             manual is not None and manual.sequence == self.RESTART_SEQUENCE - 1 and self.hold_complete is True
             and self.inventory['status'] == self.attack['status'] == 'COMMITTED'
             and len(self.moves) == 2 and all(move['status'] == 'COMMITTED' for move in self.moves)
             and position.metadata() == self.moves[-1]['saved'])
        need(prepared and self.source_restart['status'] == 'NOT_REQUESTED' and not manual.pending
             and launcher.ManualMoveRequests._actual_manual_producer(manual, asynchronous=True) is manual.consumer
             and manual.consumer.pending is None, 'SCENARIO_SOURCE_RESTART_AFTER_HOLD_REQUIRED')
        writer = self.move_bound[0]
        claims = [claim for rows in broker._claims.values() for claim in rows if claim['writer'] is writer]
        need(len(claims) == 1 and claims[0].get('_restart') is None, 'SCENARIO_SOURCE_RESTART_FRESH_ROW_REQUIRED')
        claim, realm = claims[0], broker.realm
        game = realm.registry.resolve(writer)
        refs = (broker, writer, claim, realm, game, game.selection, service, position, proof,
                realm.settings, realm.store, realm.positions, realm.registry, realm._account_bound[id(writer)])
        self.reader.validate()
        again = self.current(row, broker)
        need(again[0] is service and again[1] is position and again[2] is proof and again[3]
             and realm.registry.resolve(writer) is game and game.selection is refs[5]
             and self.owner.validate(self.owner.child) is True, 'SCENARIO_SOURCE_RESTART_AUTHORITY_CHANGED')
        self.restart_refs, self.restart_started = refs, self.clock()
        self.restart_events = broker.policy.events
        self.source_restart.update(status='CLAIMED_NO_RETRY', sequence=self.RESTART_SEQUENCE,
            settings_before=realm.settings.committed)
        self.stage = 'RESTART_WAIT'
        self.save()
        _atomic(self.monitor.directory / 'command.request.json', dict(schema=REQUEST_SCHEMA,
            sequence=self.RESTART_SEQUENCE, command='SourceRestart', uid=position.uid, map_id=position.map_id), 1024)
        self.source_restart['status'] = 'PUBLISHED'

    def collect_restart(self, broker):
        from tools.local_original_session import restart
        refs, manual = self.restart_refs, self.restart_manual
        original, writer, claim, realm, game, selected, service, position, proof, settings, store, positions, registry, account = refs
        need(broker is original and broker.realm is realm and realm.registry is registry
             and registry.resolve(writer) is game and realm._account_bound.get(id(writer)) is account
             and realm.settings is settings and realm.store is store and realm.positions is positions
             and service.snapshot() is position and positions.restore(position) == position
             and realm.edge_passability is proof and proof.reader is self.reader,
             'SCENARIO_SOURCE_RESTART_AUTHORITY_CHANGED')
        result = self._result()
        need(result is None or result['sequence'] <= self.RESTART_SEQUENCE,
             'SCENARIO_SOURCE_RESTART_RESULT_SEQUENCE_REQUIRED')
        if result is not None and result['sequence'] == self.RESTART_SEQUENCE:
            self.source_restart['consumer_status'] = result.get('status')
            need(result.get('command') == 'SourceRestart' and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                 and result.get('cleanup_required') is not True and result.get('automatic_retry') is False,
                 'SCENARIO_SOURCE_RESTART_CONSUMER_REFUSED')
            if result['status'] == 'COMMITTED':
                state = claim.get('_restart')
                events = list(broker.policy.log)
                offset = self.restart_events - (broker.policy.events - len(events))
                need(0 <= offset <= len(events), 'SCENARIO_SOURCE_RESTART_EVENTS_DROPPED')
                events = events[offset:]
                endpoint = claim['peer']['endpoint_port']
                counts = [len([e for e in events if e[0] == kind and e[1] == endpoint and e[2] == opcode])
                          for kind, opcode in (('rx', 0x4ed6), ('rx', 0x4e33), ('tx', 0x4e3b))]
                need(launcher.ManualMoveRequests._actual_source_restart_commit(manual, manual.consumer.state,
                     asynchronous=True) is True and result.get('phase') == 'COMMITTED'
                     and result.get('proof_scope') == 'LOCAL_RESTART_ACK_DRAIN_ONLY'
                     and result.get('native_attempted') is True and result.get('reason') is None
                     and result.get('cleanup_required') is False and not manual.pending
                     and manual.sequence == self.RESTART_SEQUENCE
                     and result.get('response_drained') is result.get('selection_cleared') is True
                     and result.get('ui') == result.get('inventory_restore') == 'UNKNOWN'
                     and result.get('last_sequence') == self.RESTART_SEQUENCE and counts == [1, 1, 1]
                     and type(state) is dict and state['phase'] == 'DRAINED'
                     and all(state[key] is True for key in ('write_attempted', 'drain_returned', 'response_drained', 'selection_cleared'))
                     and restart.validate_ack(state['frame'], policy=broker.restart_policy) is True
                     and all(a is b for a, b in zip(state['binding'][0][6:11], (realm, game, service, position, selected)))
                     and settings.committed == self.source_restart['settings_before'] + 1
                     and game.selection is None and selected.reference not in registry.selected
                     and all(id(writer) not in mapping for mapping in (realm._movement, realm._world_frames,
                         realm._npc_frames, realm._npc_motion)), 'SCENARIO_SOURCE_RESTART_ACK_DRAIN_PROOF_REQUIRED')
                self.source_restart.update(status='COMMITTED', proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY',
                    settings_commit=1, cs4e33=1, sc4e3b_drained=1, selection_cleared=True,
                    native_sequence=manual.consumer.sequence)
                self.stage = 'RESTART_ACK_PROVEN_CLEANUP_REQUESTED'
                self.finish_restart()
                return
        need(self.clock() - self.restart_started < 15, 'SCENARIO_SOURCE_RESTART_OBSERVATION_EXPIRED')

    def finish_restart(self):
        self.stop.set()

    def finalize(self):
        super().finalize()
        if (self.last_consumer_result is not None and self.last_consumer_result.get('command') == 'SourceRestart'
                and self.last_consumer_result.get('status') == 'UNKNOWN'):
            self.source_restart.update(status='UNKNOWN', reason=self.last_consumer_result.get('reason'),
                                       phase=self.last_consumer_result.get('phase'))

    def tick(self, row, broker, state):
        if self.stage not in ('RESTART_READY', 'RESTART_WAIT') or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set(): return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'RESTART_READY' and fresh: self.submit_restart(row, broker)
            elif self.stage == 'RESTART_WAIT': self.collect_restart(broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.source_restart['status'], self.stage = 'UNKNOWN', 'SOURCE_RESTART_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()



class SourceReselectScenario(SourceRestartScenario):
    """Explicit same-broker reselect, saved-row proof, then a fresh Move pair."""
    background_profile = source_quit_profile = SOURCE_RESELECT_PROFILE
    RESELECT_SEQUENCE = 6
    _first_move_keys = ('continuous_moves', 'continuous_moves_complete', 'movement_destination',
        'expected_move_counters', 'observed_move_counters', 'final_saved_position', 'move_counter_scope')

    def __init__(self, *args, inventory_only=False, **kwargs):
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION
        need(type(inventory_only) is bool, 'SCENARIO_RESELECT_INVENTORY_ONLY_BOOL_REQUIRED')
        self.inventory_only = inventory_only
        need(kwargs.get('source_quit_test') is True, 'SCENARIO_RESELECT_SOURCE_QUIT_REQUIRED')
        self.source_reselect = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN',
            client_inventory='UNKNOWN', ui='UNKNOWN', render='UNKNOWN')
        self.reselect_started = self.reselect_refs = self.reselect_completed = None
        self.first_move_summary = self.first_move_total = None
        super().__init__(*args, **kwargs)
        need(self.features.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION,
             'SCENARIO_RESELECT_SAVED_ROW_POLICY_REQUIRED')
        if self.inventory_only:
            self.inventory['trial_role'] = 'REQUIRED_RESELECT_PREPARATION'
        self.path = self.monitor.directory / 'manual-source-reselect-scenario.json'

    def bind_runtime(self, runtime):
        super().bind_runtime(runtime)
        need(runtime.manual.allow_source_reselect is True
             and runtime.manual.consumer.allow_source_reselect is True,
             'SCENARIO_RESELECT_REAL_PRODUCER_REQUIRED')

    def summary(self):
        row = super().summary()
        if self.first_move_summary is not None:
            for key in self._first_move_keys:
                if key in self.first_move_summary: row[key] = self.first_move_summary[key]
                else: row.pop(key, None)
        row['continuous_moves'] = [{key: move[key] for key in
            ('sequence', 'status', 'initial', 'target', 'before', 'saved', 'consumer_fresh_client_idle_proven')
            if key in move} for move in row['continuous_moves']]
        row['source_reselect'] = dict(status=self.source_reselect['status'],
            proof_scope=self.source_reselect['proof_scope'], sequence=self.RESELECT_SEQUENCE,
            client_inventory=self.source_reselect['client_inventory'],
            additional_moves_complete=self.reselect_completed is not None and len(self.moves) == 2
                and all(move['status'] == 'COMMITTED' for move in self.moves),
            observation_file='manual-source-reselect-observation.json')
        # Only this opt-in omits duplicate constants/Move fields. The complete
        # first Move rows remain in the existing Restart observation sink.
        for key in ('original_quit_capability', 'quit_enter_binding', 'confirm_window_close',
                    'close_enter_claims', 'background_launch_guaranteed', 'quit_is_movement_success_gate',
                    'cursor_focus_global_input', 'direct_packet_sender', 'primary_thread_desktop_required'):
            row.pop(key, None)
        row['move_counter_epoch'] = 'BEFORE_SOURCE_RESTART'
        row['close_policy'] = 'MANUAL_SOURCE_QUIT_AFTER_RESELECT'
        if getattr(self, 'inventory_only', False):
            row['reselect_inventory_only'] = True
            row['verification_scope'] = 'INITIAL_SAVED_ROW_RESTART_RESELECT_SAVED_ROW_QUIT'
            row['idle_seconds_requested'] = 0
        return row

    def collect_inventory(self, row, broker):
        super().collect_inventory(row, broker)
        if self.inventory_only and self.stage == 'ATTACK_READY':
            self.stage = 'RESTART_READY'

    def save(self):
        # Output only. Neither these records nor their scalars authorize action.
        restart_detail = dict(schema='manual-source-restart-observation-v1', source_restart=self.source_restart,
            last_consumer_result=self.last_consumer_result)
        if self.last_consumer_result is not None and 'inventory_pre_write' in self.last_consumer_result:
            # The complete failure belongs to the reselect sink below. Avoid
            # duplicating it alongside the previous full-mode movement rows.
            restart_detail['last_consumer_result'] = {key: value for key, value in self.last_consumer_result.items()
                if key != 'inventory_pre_write'}
        restart_detail['first_movement'] = dict(
            moves=self.first_move_summary['continuous_moves'] if self.first_move_summary is not None else self.moves,
            observed_move_counters=self.first_move_total if self.first_move_summary is not None else self.observed_move_counters)
        _atomic(self.monitor.directory / 'manual-source-restart-observation.json', restart_detail, 2048, output_only=True)
        detail = dict(schema='manual-source-reselect-observation-v1', source_reselect=self.source_reselect,
            last_consumer_result=self.last_consumer_result,
            counter_scope='NEW_SELECTED_MOVEMENT_SERVICE',
            moves=[{key: move[key] for key in ('sequence', 'status', 'initial', 'target', 'before',
                'saved', 'consumer_fresh_client_idle_proven') if key in move} for move in self.moves]
                if self.reselect_completed is not None else [],
            observed_move_counters=self.observed_move_counters if self.reselect_completed is not None else None)
        _atomic(self.monitor.directory / 'manual-source-reselect-observation.json', detail, 2048, output_only=True)
        if self.features.attack_feedback is not None:
            feedback = dict(schema='manual-attack-feedback-observations-v1', sequence=self.attack.get('sequence'),
                feedback=self.attack['feedback'], attack_observations=self.attack['attack_observations'])
            if self.approach_commits:
                feedback['approach'] = dict(initial_grid=self.origin['grid'],
                    end_grid=list(self.attack_projection[1].metadata()['grid']), commits=self.approach_commits,
                    baseline=list(self.attack_counters), total=self.first_move_total or self.observed_move_counters)
            _atomic(self.monitor.directory / 'manual-attack-feedback-observations.json', feedback, 2048, output_only=True)
        return Scenario.save(self)

    def finish_restart(self):
        self.first_move_summary = SourceRestartScenario.summary(self)
        self.first_move_total = self.observed_move_counters
        self.stage = 'RESELECT_READY'  # A distinct fresh monitor tick claims public6.

    def submit_reselect(self, broker):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        manual, refs = self.restart_manual, self.restart_refs
        original, writer, claim, realm, game, selected, service, position, proof, settings, store, positions, registry, account = refs
        need(self.source_reselect['status'] == 'NOT_REQUESTED' and broker is original
             and self.source_restart['status'] == 'COMMITTED' and manual.sequence == self.RESELECT_SEQUENCE - 1
             and not manual.pending and manual.consumer.pending is None
             and launcher.ManualMoveRequests._source_reselect_can_receive(manual) is True,
             'SCENARIO_RESELECT_AFTER_REAL_RESTART_REQUIRED')
        old = manual.consumer._source_restart_completed
        need(type(old) is dict and old['restart_state'] is claim['_restart']
             and old['restart_generation'] is broker._inventory_generation
             and old['restart_generation'].phase == 'RETIRED'
             and realm.registry.resolve(writer) is game and game.selection is None
             and realm.store is store and realm.positions is positions and realm.settings is settings
             and realm._account_bound.get(id(writer)) is account and service.snapshot() is position
             and positions.restore(position) == position,
             'SCENARIO_RESELECT_OLD_LIFETIME_CHANGED')
        self.reader.validate()
        need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        broker.source_guard(); broker.key_guard()
        need(launcher.ManualMoveRequests._source_reselect_can_receive(manual) is True
             and game.selection is None and manual.consumer._source_restart_completed is old
             and broker._inventory_generation is old['restart_generation'],
             'SCENARIO_RESELECT_OLD_LIFETIME_CHANGED')
        self.reselect_refs = (broker, manual, manual.consumer, old, broker._inventory_generation,
            broker._inventory_store, writer, game, position)
        self.reselect_started = self.clock()
        self.source_reselect.update(status='CLAIMED_NO_RETRY', sequence=self.RESELECT_SEQUENCE)
        self.stage = 'RESELECT_WAIT'
        self.save()
        _atomic(self.monitor.directory / 'command.request.json', dict(schema=REQUEST_SCHEMA,
            sequence=self.RESELECT_SEQUENCE, command='SourceReselect', uid=position.uid, map_id=position.map_id), 1024)
        self.source_reselect['status'] = 'PUBLISHED'

    def collect_reselect(self, row, broker):
        from tools.local_original_session import inventory
        original, manual, consumer, old, previous, store, writer, game, position = self.reselect_refs
        need(broker is original and self.restart_manual is manual and manual.consumer is consumer
             and consumer._source_restart_completed is old and old['restart_generation'] is previous
             and broker._inventory_store is store and broker.realm.registry.resolve(writer) is game,
             'SCENARIO_RESELECT_AUTHORITY_CHANGED')
        result = self._result()
        need(result is None or result['sequence'] <= self.RESELECT_SEQUENCE,
             'SCENARIO_RESELECT_RESULT_SEQUENCE_REQUIRED')
        if result is not None and result['sequence'] == self.RESELECT_SEQUENCE:
            need(result.get('command') == 'SourceReselect' and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                 and result.get('cleanup_required') is not True and result.get('automatic_retry') is False,
                 'SCENARIO_RESELECT_CONSUMER_REFUSED')
            self.source_reselect['consumer_status'] = result['status']
            if result['status'] == 'COMMITTED':
                need(result.get('phase') == 'CLIENT_CONFIRMED'
                     and result.get('proof_scope') == 'CLIENT_SAVED_ITEM_ROW_SCALARS_AFTER_RESELECT'
                     and result.get('selection_proof_scope') == 'LOCAL_RESELECT_LAND_READY_ONLY'
                     and result.get('client_inventory') == result.get('inventory_restore') == 'ROW_5_SCALARS_MATCHED'
                     and result.get('native_attempted') is result.get('selection_changed') is result.get('world_ready') is True
                     and result.get('ui') == result.get('render') == result.get('equipped') == result.get('save') == 'UNKNOWN'
                     and result.get('last_sequence') == self.RESELECT_SEQUENCE and result == manual.last_result
                     and manual.sequence == self.RESELECT_SEQUENCE and manual.pending is False,
                     'SCENARIO_RESELECT_CLIENT_PROOF_REQUIRED')
                completed = launcher.ManualMoveRequests._source_reselect_current(manual)
                captured_old, generation, bound, current = completed
                frame = broker._inventory_current_frame
                need(captured_old is old and generation.previous is previous
                     and generation is broker._inventory_generation and generation.phase == 'ACTIVE'
                     and generation.store is store and generation.writer is writer and generation.game is game
                     and generation.selected is game.selection and generation.selected.reference == old['initial'].name
                     and generation.restored is True and generation.attempted is True
                     and frame is generation.frame is generation.operation_frame and type(frame) is bytes
                     and generation.write_attempted is True and generation.delivery_authority is not None
                     and generation.restore_only is True
                     and store.restore(position.uid) == frame
                     and inventory.validate_frame(frame).identifier > 0,
                     'SCENARIO_RESELECT_SAVED_DELIVERY_REQUIRED')
                self.reader.validate()
                need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
                need(launcher.ManualMoveRequests._source_reselect_current(manual) is completed,
                     'SCENARIO_RESELECT_COMPLETION_CHANGED')
                # Only the actual source-owned new lifetime replaces movement
                # observation refs. Global/public/native counters never reset.
                self.move_bound = (writer, generation.mover, generation.row['peer']['connection_id'])
                self.moves, self.move_counter_base = [], (0, 0, 0)
                self.move_origin = current[3].metadata()
                self.observed_move_counters = dict(requests=0, commits=0, corrections=0)
                self.neighbor_pending = None
                self.move_event_start = broker.policy.events
                self.reselect_completed = completed
                _service, fresh, _proof, known = self.current(row, broker)
                need(fresh is current[3], 'SCENARIO_RESELECT_FRESH_LAND_REQUIRED')
                memory = row.get('memory', {})
                world, motion = memory.get('world', {}), memory.get('move_state', {})
                grid = (fresh.word0, fresh.word1)
                need(all(value is None or type(value) is int and value == fresh.uid for value in
                         (world.get('my_player_uid'), motion.get('actor_uid'),
                          motion.get('character_data', {}).get('own_uid')))
                     and motion.get('character_data', {}).get('own_uid_matches_actor') is not False
                     and all(value is None or type(value) is int and value == fresh.map_id for value in
                         (world.get('map_requested_i32'), world.get('map_resolved_i32')))
                     and all(value is None or value == grid for value in
                         (grid_pair(world.get('grid_words')), grid_pair(motion.get('transform', {}).get('current_grid')),
                          grid_pair(motion.get('transform', {}).get('predicted_grid'))))
                     and world.get('source_segment_grid_relation_match') is not False,
                     'SCENARIO_RESELECT_KNOWN_WORLD_CONTRADICTION')
                # The consumer proved fresh Land and the product proved the
                # actual client row. Missing monitor fields remain UNKNOWN;
                # the unchanged Move-ready whole gate waits before publishing.
                self.source_reselect.update(status='COMMITTED', proof_scope=result['proof_scope'],
                    client_inventory='ROW_5_SCALARS_MATCHED', native_sequence=consumer.sequence,
                    select_slot_returned=1, select_ok_returned=1, cs4e28=1, new_land=True,
                    saved_frame_restored=True, add_inventory_drained=1)
                self.stage = 'WINDOW_CLOSE_REQUESTED' if self.inventory_only else 'MOVE_READY'
                if self.inventory_only:
                    self.stop.set()  # Existing source Quit cleanup; no new movement or hold.
                return
        need(self.clock() - self.reselect_started < 15, 'SCENARIO_RESELECT_OBSERVATION_EXPIRED')

    def move_sequence(self):
        return len(self.moves) + 7 if self.reselect_completed is not None else super().move_sequence()

    def finish_hold(self, row, broker):
        if self.reselect_completed is None: return super().finish_hold(row, broker)
        self.stage = 'WINDOW_CLOSE_REQUESTED'
        self.stop.set()

    def tick(self, row, broker, state):
        if self.stage not in ('RESELECT_READY', 'RESELECT_WAIT') or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set(): return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'RESELECT_READY' and fresh: self.submit_reselect(broker)
            elif self.stage == 'RESELECT_WAIT': self.collect_reselect(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.source_reselect['status'], self.stage = 'UNKNOWN', 'SOURCE_RESELECT_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()

def selected_profile(continuous, background=False, *, attack=False, source_quit=False, use_item=False, inventory_update=False,
                     source_restart=False, source_reselect=False):
    need(type(source_reselect) is bool and (not source_reselect or source_restart and source_quit),
         'SCENARIO_RESELECT_RESTART_SOURCE_QUIT_REQUIRED')
    need(type(source_restart) is bool and (not source_restart or attack and background and not continuous
         and (not source_quit or source_reselect) and not (use_item or inventory_update)), 'SCENARIO_SOURCE_RESTART_EXCLUSIVE_BACKGROUND_REQUIRED')
    need(type(inventory_update) is bool and (not inventory_update or source_quit and attack and background
         and not continuous and not use_item), 'SCENARIO_INVENTORY_UPDATE_BACKGROUND_SOURCE_QUIT_REQUIRED')
    need(type(use_item) is bool and (not use_item or source_quit and attack and background and not continuous),
         'SCENARIO_USE_ITEM_SOURCE_QUIT_ATTACK_BACKGROUND_REQUIRED')
    need(type(source_quit) is bool and (not source_quit or attack and background),
         'SCENARIO_SOURCE_QUIT_ATTACK_BACKGROUND_REQUIRED')
    need(not attack or background and not continuous, 'SCENARIO_ATTACK_BACKGROUND_ONLY')
    need(not background or continuous or attack, 'BACKGROUND_CONTINUOUS_MOVE_REQUIRED')
    if source_reselect:
        name, pin = SOURCE_RESELECT_PROFILE, SOURCE_RESELECT_DLL_SHA
    elif source_restart:
        name, pin = SOURCE_RESTART_PROFILE, SOURCE_RESTART_DLL_SHA
    elif inventory_update:
        name, pin = INVENTORY_UPDATE_PROFILE, SOURCE_QUIT_DLL_SHA
    elif use_item:
        name, pin = USE_ITEM_PROFILE, USE_ITEM_DLL_SHA
    elif attack:
        name, pin = (SOURCE_QUIT_PROFILE, SOURCE_QUIT_DLL_SHA) if source_quit else (ATTACK_PROFILE, ATTACK_DLL_SHA)
    else:
        name, pin = ((BACKGROUND_PROFILE if background else CONTINUOUS_PROFILE), CONTINUOUS_DLL_SHA) if continuous else (PROFILE, DLL_SHA)
    profile = launcher.PRODUCTS[name]
    need(profile['image_sha256'] == IMAGE_SHA and profile['bridges']['own-login-bridge-dg49.dll'] == pin
         and not any(profile.get(key) for key in ('internal_only', 'require_lifecycle_health'))
         and (profile.get('background_display_guard') is True if background else not profile.get('background_display_guard')),
         'ORIGINAL_MANUAL_BASELINE_PROFILE_REQUIRED')
    need(not background or profile.get('require_background') is True,
         'OWNED_BACKGROUND_PRODUCT_REQUIRED')
    need(not continuous or profile.get('continuous_manual_move') is True,
         'PRODUCT_CONTINUOUS_MANUAL_CONSUMER_REQUIRED')
    if attack:
        baseline = launcher.PRODUCTS[BACKGROUND_PROFILE]
        need(profile.get('continuous_manual_move') is True and profile.get('continuous_manual_attack') is True
             and profile.get('manual_attack_move_replacement') is True and profile.get('manual_only') is True
             and profile.get('source_build_only') is False
             and profile.get('runtime_verdict') == 'EXPLICIT_BACKGROUND_TEST_CANDIDATE'
             and profile['candidate'] == baseline['candidate'] and profile['image'] == baseline['image']
             and profile.get('world_profile') == baseline.get('world_profile'),
             'SCENARIO_EXACT_ATTACK_REPLACEMENT_PRODUCT_REQUIRED')
    need(not source_quit or profile.get('manual_source_quit') is True
         and (profile.get('require_source_quit') is True or source_reselect), 'SCENARIO_EXPLICIT_SOURCE_QUIT_PRODUCT_REQUIRED')
    need(not use_item or profile.get('manual_use_item') is True,
         'SCENARIO_EXPLICIT_USE_ITEM_PRODUCT_REQUIRED')
    need(not inventory_update or profile.get('manual_inventory_update') is True,
         'SCENARIO_EXPLICIT_INVENTORY_UPDATE_PRODUCT_REQUIRED')
    need(not source_restart or profile.get('manual_source_restart') is True,
         'SCENARIO_EXPLICIT_SOURCE_RESTART_PRODUCT_REQUIRED')
    need(not source_reselect or profile.get('manual_source_reselect') is True,
         'SCENARIO_EXPLICIT_SOURCE_RESELECT_PRODUCT_REQUIRED')
    return name, profile


def main():
    need('--background' in sys.argv[1:] and any(flag in sys.argv[1:] for flag in
         ('--continuous-move-test', '--attack-target-test')),
         'FOCUS_STEALING_LAUNCH_DISABLED')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_name')
    parser.add_argument('--expected-uuid', required=True)
    parser.add_argument('--store', type=Path, default=ROOT / 'work/local_original_session/test-profile/characters.json')
    parser.add_argument('--idle-seconds', type=float, default=60)
    parser.add_argument('--tool-timeout-seconds', type=float, default=180)
    parser.add_argument('--background', action='store_true', help='Require the owned non-input desktop; never switch the input desktop.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--continuous-move-test', action='store_true',
                        help='Two explicit product MoveGoals; actual CLI launch also requires --background.')
    mode.add_argument('--attack-target-test', action='store_true',
                      help='One validated attack intent then explicit move/return; requires background and a stationary-target feature config.')
    parser.add_argument('--feature-config', type=Path)
    inventory_mode = parser.add_mutually_exclusive_group()
    inventory_mode.add_argument('--inventory-add-test', action='store_true',
                        help='Confirm public AddInventory1 before AttackTarget2/MoveGoal3/return4; requires attack/background/config.')
    inventory_mode.add_argument('--inventory-auto-test', action='store_true',
                        help='Observe restored inventory auto delivery1 before AttackTarget2/MoveGoal3/return4; requires attack/background/config.')
    item_mode = parser.add_mutually_exclusive_group()
    item_mode.add_argument('--use-item-test', action='store_true',
                        help='Observe restored inventory1/attack2, then UseItem3/move4/return5; requires auto inventory/background/attack/source Quit/config.')
    parser.add_argument('--use-item-only', action='store_true',
                        help='Limit the UseItem trial to initial saved row, UseItem2, and existing source Quit cleanup; requires --use-item-test.')
    item_mode.add_argument('--inventory-update-test', action='store_true',
                        help='Observe restored inventory1/attack2, then server-only raw field4 update3/move4/return5; requires auto inventory/background/attack/source Quit/config.')
    item_mode.add_argument('--source-restart-test', action='store_true',
                        help='Observe auto inventory1/attack2/move3/return4/world Alive, then one source Restart5; new UI selection stays unknown.')
    parser.add_argument('--source-reselect-test', action='store_true',
                        help='After source Restart5, explicit reselect6/client saved-row proof/move7/return8 and source Quit; requires Restart and source Quit flags.')
    parser.add_argument('--reselect-inventory-only', action='store_true',
                        help='Limit the source reselect trial to initial saved row, Restart5, reselect6/saved row, and existing source Quit cleanup.')
    parser.add_argument('--retain-move-goal', action='store_true',
                        help='Commit only the first adjacent MoveGoal and retain its saved position for the same normal-close/restart trial.')
    parser.add_argument('--source-quit-test', action='store_true',
                        help='Use the pinned source Quit trial after owned WM_CLOSE; requires background/attack/inventory/config.')
    parser.add_argument('--confirm-window-close', action='store_true', help='One owned Enter pair after WM_CLOSE; one more only after observed Quit and source reply drain.')
    args = parser.parse_args()
    inventory_test = args.inventory_add_test or args.inventory_auto_test
    need(not args.use_item_only or args.use_item_test,
         'SCENARIO_USE_ITEM_ONLY_REQUIRES_USE_ITEM')
    need(not args.reselect_inventory_only or args.source_reselect_test,
         'SCENARIO_RESELECT_INVENTORY_ONLY_REQUIRES_RESELECT')
    need(not args.source_reselect_test or args.source_restart_test and args.source_quit_test,
         'SCENARIO_RESELECT_RESTART_SOURCE_QUIT_REQUIRED')
    need(not args.source_restart_test or args.background and args.inventory_auto_test and args.attack_target_test
         and args.feature_config is not None and not args.retain_move_goal and (not args.source_quit_test or args.source_reselect_test)
         and not args.confirm_window_close, 'SCENARIO_SOURCE_RESTART_AUTO_ATTACK_ROUNDTRIP_REQUIRED')
    need(not args.inventory_update_test or args.background and args.source_quit_test and args.inventory_auto_test
         and args.attack_target_test and args.feature_config is not None and not args.retain_move_goal,
         'SCENARIO_INVENTORY_UPDATE_AUTO_ATTACK_SOURCE_QUIT_REQUIRED')
    need(not args.use_item_test or args.background and args.source_quit_test and args.inventory_auto_test
         and args.attack_target_test and args.feature_config is not None and not args.retain_move_goal,
         'SCENARIO_USE_ITEM_AUTO_INVENTORY_ATTACK_SOURCE_QUIT_REQUIRED')
    need(not args.retain_move_goal or args.continuous_move_test or args.attack_target_test,
         'SCENARIO_RETAIN_GOAL_REQUIRES_MOVE_TEST')
    need(not args.source_quit_test or args.background and args.attack_target_test
         and inventory_test and args.feature_config is not None,
         'SCENARIO_SOURCE_QUIT_FEATURE_CONFIG_REQUIRED')
    need(not (args.source_quit_test and args.confirm_window_close), 'SOURCE_QUIT_EXCLUSIVE_CLOSE_TRIAL_REQUIRED')
    need(not inventory_test or args.attack_target_test and args.background
         and args.feature_config is not None, 'SCENARIO_INVENTORY_ATTACK_BACKGROUND_CONFIG_REQUIRED')
    need(args.run_name.replace('-', '').isalnum(), 'FRESH_BASELINE_RUN_NAME_REQUIRED')
    focused = args.reselect_inventory_only or args.use_item_only
    need((60 <= args.idle_seconds <= 120 or focused and args.idle_seconds == 0)
         and 120 <= args.tool_timeout_seconds <= 300,
         'BOUNDED_TOOL_OBSERVATION_REQUIRED')
    if focused:
        args.idle_seconds = 0  # This explicit mode requests no world hold.
    product, profile = selected_profile(args.continuous_move_test, args.background,
        attack=args.attack_target_test, source_quit=args.source_quit_test, use_item=args.use_item_test,
        inventory_update=args.inventory_update_test, source_restart=args.source_restart_test, source_reselect=args.source_reselect_test)
    need(not (args.continuous_move_test and args.confirm_window_close),
         'NO_QUIT_ENTER_TRIAL_IN_CONTINUOUS_RUN')
    need(args.feature_config is None or args.attack_target_test, 'SCENARIO_FEATURE_CONFIG_REQUIRES_ATTACK_TEST')
    expected_features = None
    if args.attack_target_test:
        need(args.feature_config is not None, 'SCENARIO_ATTACK_FEATURE_CONFIG_REQUIRED')
        from tools.local_original_session.feature_config import load
        expected_features = attack_configuration(load(args.feature_config), inventory=inventory_test,
                                                 auto_inventory=args.inventory_auto_test)
        if args.use_item_test:
            from tools.local_original_session.item_use_session import POLICY
            need(expected_features.item_use_policy == POLICY, 'SCENARIO_USE_ITEM_POLICY_REQUIRED')
        if args.inventory_update_test:
            from tools.local_original_session.broker import INVENTORY_UPDATE_POLICY
            need(expected_features.inventory_update_policy == INVENTORY_UPDATE_POLICY,
                 'SCENARIO_INVENTORY_UPDATE_POLICY_REQUIRED')
        if args.source_restart_test:
            from tools.local_original_session.restart import POLICY
            need(expected_features.restart_policy == POLICY, 'SCENARIO_SOURCE_RESTART_POLICY_REQUIRED')
    original, old_argv = launcher.run_session, sys.argv
    scenario_failed = False

    async def run(owner, factory, stop, **kwargs):
        nonlocal scenario_failed
        need(kwargs.get('command_requests') is None and kwargs.get('input_requests') is None,
             'NO_NEW_INTERNAL_OR_MOUSE_FACADE_REQUIRED')
        monitor = kwargs['monitor']
        scenario_type = SourceReselectScenario if args.source_reselect_test else SourceRestartScenario if args.source_restart_test else InventoryUpdateScenario if args.inventory_update_test else UseItemScenario if args.use_item_test else InventoryAutoScenario if args.inventory_auto_test else InventoryAddScenario if args.inventory_add_test else AttackTargetScenario if args.attack_target_test else ContinuousMoveScenario if args.continuous_move_test else Scenario
        feature_options = {}
        if args.use_item_test:
            feature_options['use_item_only'] = args.use_item_only
        if args.source_reselect_test:
            feature_options['inventory_only'] = args.reselect_inventory_only
        if args.continuous_move_test or args.attack_target_test:
            feature_options['retain_move_goal'] = args.retain_move_goal
        if args.attack_target_test:
            actual_features = getattr(kwargs.get('feature_factory'), 'config', None)
            need(actual_features == expected_features, 'SCENARIO_ATTACK_FEATURE_CONFIG_CHANGED')
            feature_options['features'] = actual_features
        scenario, tick = scenario_type(owner, monitor, stop, args.idle_seconds,
                                  background=args.background,
                                  source_quit_test=args.source_quit_test,
                                  confirm_window_close=args.confirm_window_close, **feature_options), monitor.tick
        if args.source_restart_test:
            source_factory = kwargs['feature_factory']
            def capture_features(broker):
                runtime = source_factory(broker)
                scenario.bind_runtime(runtime)
                return runtime
            kwargs['feature_factory'] = capture_features
        original_close = owner.request_close
        def close():
            count = original_close()
            scenario.close_requested(count)
            return count
        def wrapped(broker=None, *, state='RUNNING', force=False):
            row = tick(broker, state=state, force=force)
            scenario.tick(row or {}, broker, state)
            return row
        monitor.tick = wrapped
        owner.request_close = close
        try:
            report = await original(owner, factory, stop, **kwargs)
            if args.attack_target_test:
                scenario.finalize()
            report['normal_input_only'] = False
            report['manual_baseline_scenario'] = scenario.summary()
            scenario.save()
            summary = report['manual_baseline_scenario']
            scenario_failed = (summary.get('error') is not None
                or focused and (summary.get('attack_target', {}).get('status') != 'NOT_REQUESTED'
                    or summary.get('continuous_moves') != [] or summary.get('idle_hold_complete') is not False)
                or not focused and summary.get('idle_hold_complete') is not True
                or not focused and (args.continuous_move_test or args.attack_target_test)
                    and summary.get('continuous_moves_complete') is not True
                or not focused and args.attack_target_test and summary.get('attack_target', {}).get('status') != 'COMMITTED'
                or inventory_test and summary.get('inventory_add', {}).get('status') != 'COMMITTED'
                or args.use_item_test and summary.get('use_item', {}).get('status') != 'COMMITTED'
                or args.inventory_update_test and summary.get('inventory_update', {}).get('status') != 'COMMITTED'
                or args.source_restart_test and summary.get('source_restart', {}).get('status') != 'COMMITTED'
                or args.source_reselect_test and (summary.get('source_reselect', {}).get('status') != 'COMMITTED'
                    or not args.reselect_inventory_only and summary.get('source_reselect', {}).get('additional_moves_complete') is not True))
            return report
        finally:
            monitor.tick = tick
            owner.request_close = original_close

    launcher.run_session = run
    sys.argv = ['launcher', '--run', '--control-mode', 'manual', '--product', product,
        '--image', str(profile['image']), '--expected-uuid', args.expected_uuid, '--store', str(args.store),
        '--run-directory', str(ROOT / 'work/local_original_session/runs' / args.run_name),
        '--test-duration', str(args.tool_timeout_seconds)]  # Explicit tool bound, not game lifetime.
    if args.background:
        sys.argv.append('--background')
    if args.source_quit_test:
        sys.argv.append('--source-quit-test')
    if args.feature_config is not None:
        sys.argv.extend(('--feature-config', str(args.feature_config)))
    try:
        code = launcher.main()
        return 2 if scenario_failed else code
    finally: launcher.run_session, sys.argv = original, old_argv


if __name__ == '__main__': raise SystemExit(main())
