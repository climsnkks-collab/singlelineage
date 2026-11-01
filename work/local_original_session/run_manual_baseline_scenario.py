"""Explicit background manual scenario; ordinary foreground launch disabled.

Reuses launcher ownership/loop/cleanup, owned non-input desktop and frozen probes.
No desktop switch, attach, cursor/focus/global input API or Quit facade.
WINDOW_CLOSE is a trial; only the launcher's actual source-Quit result proves it.
"""
from __future__ import annotations

import argparse
import asyncio
import ctypes as C
from ctypes import wintypes as W
import importlib.util
import json
import os
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

ITEM_TRANSFER_PROFILE = 'sibling-background-item-drop-pickup-spawn'
ITEM_TRANSFER_DLL_SHA = '3fb1c60520ed735ca72fb5e35b057715950f8a4e4d2a4bcf591051678bdf792c'
PROFILE = 'sibling-manual-play-spawn'
IMAGE_SHA = '8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684'
DLL_SHA = '1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75'
CONTINUOUS_PROFILE = 'sibling-manual-move-continuous-spawn'
BACKGROUND_PROFILE = 'sibling-background-move-continuous-spawn'
ATTACK_PROFILE = 'sibling-background-move-attack-target-spawn'
ATTACK_DLL_SHA = '2c0bcd6e53eb5d86e4ef87115f899b976a86d5e820912d63ab3de29e1344073d'
SOURCE_QUIT_PROFILE = 'sibling-background-source-quit-spawn'
NPC_RESPAWN_PROFILE = 'sibling-background-npc-respawn-spawn'
NPC_RESPAWN_NEXT_HIT_PROFILE = 'sibling-background-npc-respawn-next-hit'
SOURCE_QUIT_DLL_SHA = 'd5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d'
NPC_RESPAWN_NEXT_HIT_DLL_SHA = '85d2d5d9ba22b847940cc8d7675b5b7973eda8ce4793e477a176c2933fa8e5ca'
INVENTORY_UPDATE_PROFILE = 'sibling-background-inventory-update-source-quit-spawn'
USE_ITEM_PROFILE = 'sibling-background-use-item-source-quit-spawn'
USE_ITEM_UI_PROFILE = 'sibling-background-use-item-ui-observe-spawn'
UI_FRAME_UPDATE_PROFILE = 'sibling-background-item-equipment-ui-update-spawn'
UI_LOOKUP_ROLE_PROFILE = 'sibling-background-inventory-ui-open-selected-slot-lookup-role-spawn'
UI_LOOKUP_ROLE_DLL_SHA = '7eb6ebc5f363a19b5519af9e1392f1e34ec0113b41b13b42ed4eebc41de7b98c'
ORIGINAL_SCREENSHOT_PROFILE = 'sibling-background-original-screenshot-spawn'
HP_STATUS_PNG_PROFILE = 'sibling-background-hp-status-png-spawn'
NPC_PLAYER_HIT_PROFILE = 'sibling-background-npc-player-hit-spawn'
NPC_PLAYER_HIT_REPEATED_PROFILE = 'sibling-background-npc-player-hit-repeated-spawn'
NPC_APPROACH_HIT_PROFILE = 'sibling-background-npc-approach-player-hit-spawn'
PLAYER_DEATH_RECOVERY_PROFILE = 'sibling-background-player-death-recovery-spawn'
NPC_PLAYER_LETHAL_RECOVERY_PROFILE = 'sibling-background-npc-player-lethal-recovery-spawn'
ORIGINAL_SCREENSHOT_DLL_SHA = '5fdf05f2c38b17e2be8674ffb33a7ba0f3276fbad33d212a22d7aedd23d1ecf5'
NPC_APPROACH_HIT_DLL_SHA = '6484117819571a32abe12391ce4af92bc13748d16cf0a4e1fd552901bc86ec7d'
MARK_ON_PROFILE = 'sibling-background-normal-open-use-mark-on-spawn'
MARK_ON_DLL_SHA = 'bbda56d51c26def3aca345126c4dfe1740eb29b0311c10d21eba9ec0693c0b6d'
NORMAL_OPEN_USE_UI_PROFILE = 'sibling-background-normal-open-use-current-ui-spawn'
NORMAL_OPEN_USE_UI_DLL_SHA = '6b308a2cbc37c135d8182bda0903911a1eab7667e0afdcd9e3f816b5cbf9dbe6'
INVENTORY_UI_OPEN_PROFILE = 'sibling-background-inventory-ui-open-spawn'
INVENTORY_UI_OPEN_DLL_SHA = '9492c5d281d0eb4e63b8cbd0b4d83fcda2833c8fb72b2ec0f45d239a6e0c0dc2'
USE_ITEM_UI_DLL_SHA = '0105f7104a0f36d833b85b27eb47d47d8c70c71bfeb2e666d9c8aed3dd7011f2'
USE_ITEM_DLL_SHA = '3db49209c95708c7a6588f55f85a7657612cbd4a7d0a64dd0869258ea20abec3'
SWAP_PROFILE = 'sibling-background-item-equipment-swap-reselect-spawn'
CURRENT_ENTRY_TAIL_PROFILE = 'sibling-background-item-equipment-current-entry-tail-spawn'
CURRENT_ENTRY_TAIL_DLL_SHA = 'b8b6de58da73763384e24c4184535ca011a78029eead04ad2d2d9df765dea4ce'
ZERO_USE_RESELECT_PROFILE = 'sibling-background-item-equipment-zero-use-reselect-spawn'
ZERO_USE_RESELECT_DLL_SHA = 'ff5e1dc82de3bdb19bed5c4f48851fefed1c2e101dffa9decfa0ba2fa6c7d5f1'
RESELECT_EQUIPMENT_PROFILE = 'sibling-background-item-equipment-reselect-restore-spawn'
RESELECT_EQUIPMENT_DLL_SHA = 'bbda56d51c26def3aca345126c4dfe1740eb29b0311c10d21eba9ec0693c0b6d'
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
    summary_byte_limit = 4096
    background_confirm_allowed = False
    close_after_failure = False

    def __init__(self, owner, monitor, stop, idle_seconds, *, clock=time.monotonic, confirm_window_close=False,
                 profile=PROFILE, background=False, source_quit_test=False):
        need(owner.product == profile and owner.image_sha == IMAGE_SHA and not owner.internal
             and (background or owner.private_desktop is None), 'EXACT_MANUAL_BASELINE_OWNER_REQUIRED')
        self.background = background
        need(type(source_quit_test) is bool and (not source_quit_test or background
             and profile in (NPC_RESPAWN_NEXT_HIT_PROFILE, NPC_RESPAWN_PROFILE, SOURCE_QUIT_PROFILE, USE_ITEM_PROFILE, USE_ITEM_UI_PROFILE, INVENTORY_UI_OPEN_PROFILE, UI_LOOKUP_ROLE_PROFILE, NORMAL_OPEN_USE_UI_PROFILE, MARK_ON_PROFILE, ORIGINAL_SCREENSHOT_PROFILE, HP_STATUS_PNG_PROFILE, NPC_PLAYER_HIT_PROFILE, NPC_PLAYER_HIT_REPEATED_PROFILE, NPC_APPROACH_HIT_PROFILE, PLAYER_DEATH_RECOVERY_PROFILE, NPC_PLAYER_LETHAL_RECOVERY_PROFILE, UI_FRAME_UPDATE_PROFILE, INVENTORY_UPDATE_PROFILE, SOURCE_RESELECT_PROFILE, RESELECT_EQUIPMENT_PROFILE, SWAP_PROFILE, CURRENT_ENTRY_TAIL_PROFILE, ZERO_USE_RESELECT_PROFILE, ITEM_TRANSFER_PROFILE) and not confirm_window_close),
             'SCENARIO_EXCLUSIVE_SOURCE_QUIT_BACKGROUND_REQUIRED')
        self.source_quit_test = source_quit_test
        self._retained_background_desktop = None
        self.primary_thread_desktop_verified = False
        self.primary_thread_desktop_probe = None
        self.primary_thread_desktop_proof = None
        if background:
            need(profile in (NPC_RESPAWN_NEXT_HIT_PROFILE, NPC_RESPAWN_PROFILE, BACKGROUND_PROFILE, ATTACK_PROFILE, SOURCE_QUIT_PROFILE, USE_ITEM_PROFILE, USE_ITEM_UI_PROFILE, INVENTORY_UI_OPEN_PROFILE, UI_LOOKUP_ROLE_PROFILE, NORMAL_OPEN_USE_UI_PROFILE, MARK_ON_PROFILE, ORIGINAL_SCREENSHOT_PROFILE, HP_STATUS_PNG_PROFILE, NPC_PLAYER_HIT_PROFILE, NPC_PLAYER_HIT_REPEATED_PROFILE, NPC_APPROACH_HIT_PROFILE, PLAYER_DEATH_RECOVERY_PROFILE, NPC_PLAYER_LETHAL_RECOVERY_PROFILE, UI_FRAME_UPDATE_PROFILE, INVENTORY_UPDATE_PROFILE, SOURCE_RESTART_PROFILE, SOURCE_RESELECT_PROFILE, RESELECT_EQUIPMENT_PROFILE, SWAP_PROFILE, CURRENT_ENTRY_TAIL_PROFILE, ZERO_USE_RESELECT_PROFILE, ITEM_TRANSFER_PROFILE) and getattr(owner, 'background', False) is True
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

    def save(self): _atomic(self.path, self.summary(), self.summary_byte_limit, output_only=True)

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
        # SL_COMPANION=1 adds the companion mage to the test profile; the owner still enters.
        extra = refs - {broker.realm.profile_name}
        need(broker.realm.profile_name in refs
             and (not extra or os.environ.get('SL_COMPANION') == '1' and extra == {'SoloMage'})
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


def attack_configuration(config, *, inventory=False, auto_inventory=False, collection_restore_only=False):
    need(type(collection_restore_only) is bool, 'SCENARIO_COLLECTION_RESTORE_BOOL_REQUIRED')
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
            grant = config.inventory_collection_grant
            collection = (collection_restore_only
                and config.inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
                and config.inventory_collection_policy == inv.COLLECTION_POLICY
                and config.inventory_custody_policy is None and config.inventory_missing_row_policy is None
                and config.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
                and config.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
                and type(grant) is tuple and len(grant) == 2
                and grant[0] == inventory_store.SECOND_INSTANCE_POLICY and type(grant[1]) is frozenset
                and all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in grant[1]))
            need(config.inventory_store_policy == inventory_store.POLICY or collection,
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
    OBSERVATION_SECONDS = 15  # Original attack result deadline, shared by focused completion.
    configuration = staticmethod(attack_configuration)

    def __init__(self, *args, features, **kwargs):
        need(kwargs.get('background') is True, 'SCENARIO_ATTACK_BACKGROUND_REQUIRED')
        self.features = self.configuration(features, inventory=self.inventory_required,
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
        death_keys = {'death_current', 'death_queued'}
        byte_ranges = {'combined_bytes': (0, 24576), 'refused_bytes': (1, 4096),
                       'shortfall_bytes': (1, 4096)}
        for stage in ('pre_command', 'post_feedback', 'next_strict_idle'):
            if stage not in observations:
                continue
            snapshot = observations[stage]
            need(type(snapshot) is dict and set(snapshot) - {'read_field', 'count_refusal', 'count_type_rva'} in
                    (keys, keys | byte_ranges.keys(), keys | death_keys, keys | death_keys | byte_ranges.keys())
                 and snapshot.get('status') in ('OBSERVED', 'UNKNOWN')
                 and (snapshot.get('reason') is None or type(snapshot.get('reason')) is str
                      and len(snapshot['reason']) <= 120)
                 and type(snapshot.get('at_ns')) is int and snapshot['at_ns'] >= 0
                 and all(snapshot.get(key) is None or type(snapshot.get(key)) is bool
                         for key in (keys | death_keys) - {'status', 'reason', 'at_ns'} if key in snapshot),
                 'SCENARIO_ATTACK_OBSERVATION_SHAPE_REQUIRED')
            need('read_field' not in snapshot or type(snapshot['read_field']) is int
                 and 0 <= snapshot['read_field'] <= 7 and snapshot['status'] == 'UNKNOWN'
                 and (snapshot['reason'] == 'ATTACK_OBSERVE_TYPED_READ_CHANGED'
                      or snapshot['reason'] == 'ATTACK_OBSERVE_COUNT_ACTION_UNCLASSIFIED'
                         and snapshot['read_field'] == 1),
                 'SCENARIO_ATTACK_OBSERVATION_READ_FIELD_REQUIRED')
            need('count_refusal' not in snapshot or type(snapshot['count_refusal']) is int
                 and 1 <= snapshot['count_refusal'] <= 8 and snapshot['status'] == 'UNKNOWN'
                 and snapshot['reason'] == 'ATTACK_OBSERVE_COUNT_ACTION_UNCLASSIFIED'
                 and all(snapshot.get(key) is None
                         for key in (keys | death_keys) - {'status', 'reason', 'at_ns'}),
                 'SCENARIO_ATTACK_OBSERVATION_COUNT_REFUSAL_REQUIRED')
            need('count_type_rva' not in snapshot or type(snapshot['count_type_rva']) is int
                 and 0 <= snapshot['count_type_rva'] < 0x3e95000
                 and type(snapshot.get('count_refusal')) is int and snapshot['count_refusal'] in (1, 3, 5, 7)
                 and snapshot['status'] == 'UNKNOWN'
                 and snapshot['reason'] == 'ATTACK_OBSERVE_COUNT_ACTION_UNCLASSIFIED',
                 'SCENARIO_ATTACK_OBSERVATION_COUNT_TYPE_REQUIRED')
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
             and spawn.map_id == position.map_id
             and (id(self.move_bound[0]) not in broker.realm._npc_motion
                  or type(self) is NpcDeadGoalScenario and self.npc_trial.require_attack_target(broker, spawn)),
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
                need(self.clock() - self.attack_started < self.OBSERVATION_SECONDS, 'SCENARIO_ATTACK_OBSERVATION_EXPIRED')
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
        need(self.clock() - self.attack_started < self.OBSERVATION_SECONDS, 'SCENARIO_ATTACK_OBSERVATION_EXPIRED')

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

    def _auto_inventory_restore_mode(self, broker, writer, selected, frame):
        # Existing saved-only behavior is unchanged. A configured first grant
        # is accepted only for the explicit focused effect trial and the real
        # selected-generation producer; its mode is not completion evidence.
        if broker._inventory_restored is True:
            return True
        from tools.local_original_session import inventory
        from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration, INVENTORY_MISSING_ROW_POLICY
        from tools.local_original_session.inventory_store import InventoryStore
        need(getattr(self, 'use_item_effect', False) is True and self.use_item_only is True
             and type(broker) is PersistentBroker
             and getattr(self.features, 'inventory_missing_row_policy', None) == INVENTORY_MISSING_ROW_POLICY
             and broker.inventory_missing_row_policy == INVENTORY_MISSING_ROW_POLICY,
             'SCENARIO_AUTO_INVENTORY_EXPLICIT_FIRST_GRANT_REQUIRED')
        generation = PersistentBroker.inventory_selection_current(broker, writer)
        need(type(generation) is _InventoryGeneration and generation is broker._inventory_generation
             and generation.phase == 'ACTIVE' and generation.mode == 'FIRST_GRANT'
             and generation.writer is writer and generation.row is selected[1]
             and generation.lock is selected[1]['operation_lock']
             and generation.selection_binding is selected and generation.frame is frame
             and generation.service is broker._inventory_service
             and generation.reader is self.reader and generation.store is broker._inventory_store
             and generation.restored is False and broker._inventory_restored is False
             and frame is broker._inventory_config_frame and frame is self.features.inventory_frame,
             'SCENARIO_AUTO_INVENTORY_FIRST_GRANT_SELECTION_REQUIRED')
        if self.inventory['status'] == 'COMMITTED':
            service, row, delivered = generation.service, generation.row, generation.delivery_authority
            observed = service.last_result
            # The original producer sets claimed only after native-empty,
            # Store.grant returns normally, and final source/authority checks.
            # add_inventory publishes delivery/current only after send/drain
            # and its original post-owner checks. Do not invent grant=True.
            PersistentBroker._inventory_operation_mode_current(broker, False, writer, row, frame)
            need(type(service) is inventory.InventoryService and service._claimed is True
                 and service._inflight is False and service._closed is False
                 and generation.attempted is True and generation.write_attempted is True
                 and generation.restore_only is False and generation.current_frame is frame
                 and generation.operation_frame is frame and generation.prewrite_refusal is None
                 and generation.admission_expired is False
                 and type(delivered) is tuple and len(delivered) == 3
                 and delivered is broker._inventory_delivery_authority
                 and type(delivered[1]) is tuple and len(delivered[1]) == 24
                 and delivered[1][16] is row and delivered[1][18] is generation.lock
                 and row['policy_row'].pending_opcode is None and row['policy_row'].pending_size == 0
                 and row['policy_row'].drain_started_ns is None
                 and type(observed) is dict and observed.get('status') == 'OBSERVED'
                 and observed.get('reason') is None and observed.get('inventory_empty') is True
                 and observed.get('source_contract_valid') is True and observed.get('stable_double_read') is True
                 and InventoryStore.restore(generation.store, delivered[0].uid) == frame,
                 'SCENARIO_AUTO_INVENTORY_FIRST_GRANT_COMPLETION_REQUIRED')
        return False

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
        need(type(broker._inventory_store) is InventoryStore
             and type(selected) is tuple and len(selected) == 11
             and selected[0] is self.move_bound[0] and type(frame) is bytes,
             'SCENARIO_AUTO_INVENTORY_RESTORED_SELECTION_REQUIRED')
        self._auto_inventory_restore_mode(broker, self.move_bound[0], selected, frame)
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
                              selected_frame_restored=broker._inventory_restored)
        if getattr(self.features, 'inventory_missing_row_policy', None) is not None:
            self.inventory['delivery_mode'] = broker._inventory_generation.mode
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


def npc_motion_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session.npc_motion_focused import configuration
    return configuration(config, inventory=inventory, auto_inventory=auto_inventory)


def hp_status_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import feature_config as fc, hp_status, inventory as inv, inventory_store
    from tools.local_native_login_spawn_render_retry_runtime import spawn_hook
    need(type(config) is fc.Features and type(config.hp_status_input) is fc.HpStatusInput
         and type(config.hp_status_policy) is str and config.hp_status_policy == hp_status.POLICY
         and config.hp_status_input.scope == fc.HP_STATUS_SCOPE
         and config.hp_status_input.target_uid == spawn_hook.profiles()[0].fields[1]
         and config.hp_status_input.map_id == 0 and not config.spawns
         and all(getattr(config,name) is None for name in ('attack_policy','attack_feedback',
             'interval_ns','motion_policy','goal_policy','goal','attack_hp_provider','npc_death_policy',
             'npc_remove_policy','npc_respawn_policy','npc_respawn_spawn','item_use_policy',
             'item_equipment_policy','inventory_update_policy','inventory_missing_row_policy'))
         and config.item_equipment_first_enable is False,
         'SCENARIO_EXPLICIT_LOCAL_CHARACTER_HP_CONFIG_REQUIRED')
    need(inventory is True and auto_inventory is True and config.inventory_policy == inv.POLICY
         and type(config.inventory_frame) is bytes and config.inventory_store_policy == inventory_store.POLICY
         and config.inventory_delivery_policy == fc.LOCAL_WORLD_READY_ONCE,
         'SCENARIO_HP_STATUS_SAVED_INVENTORY_PREPARATION_REQUIRED')
    inv.validate_frame(config.inventory_frame)
    return config


def hp_status_png_configuration(config, *, inventory=False, auto_inventory=False):
    config=launcher.hp_status_png_config(config)
    hp_status_configuration(config, inventory=inventory, auto_inventory=auto_inventory)
    need(config.hp_status_input.current_hp == 19 and config.hp_status_input.maximum_hp == 20,
         'SCENARIO_HP_PNG_EXPLICIT_19_20_REQUIRED')
    return config



def npc_hp_feedback_configuration(config, *, inventory=True, auto_inventory=True):
    from tools.local_original_session import npc_hp, attack_session
    attack_configuration(config, inventory=inventory, auto_inventory=auto_inventory, collection_restore_only=True)
    need(inventory is auto_inventory is True
         and type(config.attack_hp_provider) is npc_hp.ExplicitInputs
         and type(config.attack_feedback) is attack_session.FeedbackConfig
         and config.npc_death_policy is config.npc_remove_policy is None,
         'SCENARIO_NPC_HP_FEEDBACK_EXPLICIT_NONLETHAL_CONFIG_REQUIRED')
    inputs, = config.attack_hp_provider.rows
    need(inputs.hit.landed is True and 0 < inputs.hit.damage < inputs.hp.current,
         'SCENARIO_NPC_HP_FEEDBACK_NONLETHAL_INPUT_REQUIRED')
    return config


class NpcHpFeedbackOnlyScenario(InventoryAutoScenario):
    """Original inventory/AttackTarget2, dated diagnostic, then existing Quit."""
    configuration = staticmethod(npc_hp_feedback_configuration)

    def __init__(self, *args, **kwargs):
        self.npc_hp_feedback = dict(status='NOT_REQUESTED', local_hp=None,
            passive_diagnostic=None, hp_ui='UNKNOWN', notification='NOT_IMPLEMENTED_SOURCE_CONTRACT_REQUIRED')
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'npc-hp-feedback-only-scenario.json'
        self.npc_inventory_runtime = None
        from tools.local_original_session.hp4ec8_subscribers import Observation
        observation = getattr(self.reader, '_hp4ec8_subscribers', None)
        need(type(observation) is Observation and observation.stage == 'npc-hp-feedback-drained',
             'SCENARIO_NPC_HP_FEEDBACK_EXISTING_STAGE_REQUEST_REQUIRED')

    def bind_runtime(self, runtime):
        from tools.local_original_session import inventory
        need(type(runtime) is launcher.ProductFeatures
             and type(runtime.manual) is launcher.ManualMoveRequests
             and runtime.manual.consumer.reader is self.reader
             and runtime.manual.inventory_collection_policy == inventory.COLLECTION_POLICY,
             'SCENARIO_NPC_HP_COLLECTION_RUNTIME_REQUIRED')
        self.npc_inventory_runtime = runtime

    def collect_inventory(self, row, broker):
        self.inventory_authority(row, broker)  # Original selected11/frame/generation checks.
        result = self._result()
        if result is None or result.get('status') != 'COMMITTED':
            return super().collect_inventory(row, broker)
        from tools.local_original_session import inventory
        from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration
        runtime = self.npc_inventory_runtime
        writer = self.move_bound[0]
        need(type(runtime) is launcher.ProductFeatures and type(broker) is PersistentBroker
             and type(runtime.manual) is launcher.ManualMoveRequests
             and runtime.manual.inventory_broker is broker and runtime.manual.consumer.reader is self.reader,
             'SCENARIO_NPC_HP_COLLECTION_SAME_RUNTIME_REQUIRED')
        generation = PersistentBroker.inventory_selection_current(broker, writer)
        need(type(generation) is _InventoryGeneration and generation.previous is None
             and generation.writer is writer and generation.phase == 'ACTIVE'
             and generation.selection_binding is self.auto_inventory_binding
             and generation.current_frame is self.auto_inventory_frame
             and result == runtime.manual.last_result
             and result.get('sequence') == self.INVENTORY_SEQUENCE
             and result.get('command') == 'AddInventory',
             'SCENARIO_NPC_HP_COLLECTION_CURRENT_RESULT_REQUIRED')
        need(type(result.get('item_count')) is int and result['item_count'] == 2
             and all(result.get(key) == 'UNKNOWN' for key in ('render','equipped','save'))
             and all(result.get(key) is False for key in ('all_17_wire_fields_proven',
                 'wire_field18_bytes_observed','catalog_live_materialization_proven')),
             'SCENARIO_NPC_HP_COLLECTION_OUTPUT_SCOPE_REQUIRED')
        expected = inventory.validate_collection_frame(self.auto_inventory_frame,
            policy=self.features.inventory_collection_policy)
        need(len(expected) == 2
             and launcher.ProductFeatures._equipment_delivery_complete(runtime, broker, generation)
             and launcher.ProductFeatures._equipment_initial_client_ready(runtime, broker, writer, generation),
             'SCENARIO_NPC_HP_COLLECTION_TYPED_COMPLETION_REQUIRED')
        # Same original typed row UID/template/quantity proof and client binding;
        # this is readiness for AttackTarget2, not custody/equipment authority.
        self.inventory.update({key: result[key] for key in ('status','phase','proof_scope',
            'client_inventory','item_count','transport_proof_scope') if key in result})
        self.stage = 'ATTACK_READY'

    def summary(self):
        return dict(super().summary(), npc_hp_feedback_only=self.npc_hp_feedback)

    def collect_attack(self, row, broker):
        super().collect_attack(row, broker)  # Original current intent/drained feedback/action checks.
        if self.attack['status'] != 'COMMITTED':
            return
        from tools.local_original_session import npc_hp
        session, writer = self.attack_session, self.move_bound[0]
        result = session.last_hp_result
        intent = session.current_intent()
        inputs, = self.features.attack_hp_provider.rows
        need(type(result) is npc_hp.Result and result.target == inputs.target
             and result.accepted_ordinal == session.accepted_count == self.attack_before + 1
             and intent is not None and intent.accepted_ordinal == result.accepted_ordinal
             and intent._bound._writer is writer and intent._bound.target_uid == result.target.uid
             and session._feedback_intent is intent and session._feedback_state == 'DRAINED'
             and result.before == inputs.hp and result.hit == inputs.hit
             and result.after.current == inputs.hp.current - inputs.hit.damage,
             'SCENARIO_NPC_HP_FEEDBACK_COMMITTED_RESULT_REQUIRED')
        self.npc_hp_feedback.update(status='WAITING_DIAGNOSTIC', local_hp=result.metadata())
        # The superclass chose MOVE_READY. Intercept within that same call;
        # no tick can dispatch MoveGoal/return/hold in this explicit mode.
        self.stage = 'NPC_HP_DIAGNOSTIC_WAIT'
        self._finish_diagnostic()

    def _finish_diagnostic(self):
        observation = self.reader._hp4ec8_subscribers
        result = observation.result
        expired = self.clock() - self.attack_started >= self.OBSERVATION_SECONDS
        if result is None and not expired:
            return
        snapshot = result if result is not None else observation.waiting
        self.npc_hp_feedback['passive_diagnostic'] = {key: snapshot[key] for key in
            ('status','bytes','attempted','query_complete','owner_validation','stage','trigger') if key in snapshot}
        self.npc_hp_feedback.update(status='COMMITTED',
            diagnostic_outcome='TERMINAL_DIAGNOSTIC' if result is not None else 'WAITING_AT_ORIGINAL_DEADLINE',
            diagnostic_source='FINAL_STATUS_MEMORY_HP4EC8_SUBSCRIBERS',
            completion_scope='LOCAL_HP_COMMIT_FEEDBACK_DRAIN_AND_BOUNDED_OBSERVATION_ONLY')
        self.stage = 'NPC_HP_FEEDBACK_COMPLETE_STOP_REQUESTED'
        self.stop.set()  # Existing SourceQuit request/cleanup; no new launcher path.

    def tick(self, row, broker, state):
        if state == 'CLOSING':
            return super().tick(row, broker, state)
        if self.stage != 'NPC_HP_DIAGNOSTIC_WAIT':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        self._finish_diagnostic()  # Cached observation only; no sample/query/poll.
        self.save()


class HpStatusNotifyScenario(InventoryAutoScenario):
    """One explicit local-character HP update; no attack or NPC dependency."""
    configuration = staticmethod(hp_status_configuration)

    def __init__(self,*args,**kwargs):
        need(kwargs.get('source_quit_test') is True,'SCENARIO_HP_STATUS_SOURCE_QUIT_REQUIRED')
        self.hp_runtime=None
        self.hp_status=dict(status='NOT_REQUESTED',scope='SELECTED_LOCAL_CHARACTER_HP_DISPLAY_ONLY',
            initial_world='REQUIRED_PREPARATION_ONLY',server=None,pre=None,post=None,
            client_hp='UNKNOWN',screen='UNKNOWN',npc_hp_4ec8='NOT_CLAIMED',automatic_retry=False)
        super().__init__(*args,**kwargs)
        self.path=self.monitor.directory/'manual-hp-status-notify-scenario.json'

    def summary(self):
        return dict(super().summary(),hp_status_notify_only=True,
            hp_status_notify=dict(status=self.hp_status['status'],scope=self.hp_status['scope'],
                server_status=None if self.hp_status['server'] is None else self.hp_status['server'].get('status'),
                client_hp=self.hp_status['client_hp'],screen='UNKNOWN',npc_hp_4ec8='NOT_CLAIMED',
                evidence_file='manual-hp-status-notify-observations.json',
                **({'hud_bar':dict(status=self.hp_status['hud_bar']['status'],
                    model=self.hp_status['hud_bar'].get('model'),
                    typed_bytes_requested=self.hp_status['hud_bar'].get('typed_bytes_requested'))}
                   if 'hud_bar' in self.hp_status else {})))

    def save(self):
        _atomic(self.monitor.directory/'manual-hp-status-notify-observations.json',
            dict(schema='manual-hp-status-notify-observations-v1',**self.hp_status),16384,output_only=True)
        return super().save()

    def tick(self,row,broker,state):
        if state=='CLOSING':return super().tick(row,broker,state)
        if self.stage not in ('ATTACK_READY','HP_STATUS_RUN','HP_STATUS_COMPLETE_STOP_REQUESTED',
                              'HP_STATUS_UNKNOWN_STOP_REQUESTED','HP_STATUS_PARTIAL_STOP_REQUESTED'):
            return super().tick(row,broker,state)
        if self.stage!='ATTACK_READY' or state!='RUNNING' or self.stop.is_set():return
        try:
            service,position,_proof,known=self.current(row,broker)
            if not known:return
            need(self.inventory['status']=='COMMITTED' and self.attack['status']=='NOT_REQUESTED'
                 and not self.moves and self.hp_runtime is not None,
                 'SCENARIO_HP_STATUS_CURRENT_PREPARATION_REQUIRED')
            self.hp_runtime.begin(self.move_bound[0],service,position)
            self.save()
        except Exception as error:
            self.hp_runtime.fail(error) if self.hp_runtime is not None else self.stop.set()
            if self.hp_runtime is None:self.error=launcher.safe_error_code(error) or type(error).__name__
            self.save()



def player_death_recovery_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session.player_death_recovery_focused import configuration, broker_options
    from tools.local_original_session.inventory import validate_frame
    configuration(config); broker_options(config)
    need(inventory is True and auto_inventory is False and type(config.inventory_frame) is bytes,
         'SCENARIO_PLAYER_LIFE_EXPLICIT_INVENTORY_PREPARATION_REQUIRED')
    validate_frame(config.inventory_frame)
    return config


class PlayerDeathRecoveryScenario(InventoryAddScenario):
    configuration = staticmethod(player_death_recovery_configuration)
    source_quit_profile = 'sibling-background-player-death-recovery-spawn'

    def __init__(self, *args, **kwargs):
        need(kwargs.get('source_quit_test') is True, 'SCENARIO_PLAYER_LIFE_SOURCE_QUIT_REQUIRED')
        self.life_runtime = None
        self.life_status = dict(status='NOT_REQUESTED', preparation=None, server=None,
            native=None, current_action='UNKNOWN', numeric='UNKNOWN', hud='UNKNOWN', reason=None, quit=None)
        self.life_evidence = {}
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory/'manual-player-death-recovery-scenario.json'

    def summary(self):
        row = super().summary()
        # Raw producer observations remain in separate bounded files. Omit idle
        # telemetry for a mode that explicitly requests no idle hold.
        for key in ('idle_wall_elapsed_seconds','idle_snapshot_ready','idle_paused',
                    'idle_last_good_age_seconds','idle_reason'):
            row.pop(key, None)
        status = self.life_status
        server = status['server']
        row['player_death_recovery'] = dict(status=status['status'],
            preparation=status['preparation'],
            server=None if server is None else {key:server.get(key) for key in
                ('stage','terminal','target_uid','hp','newlife','client_recovery')},
            native=None if status['native'] is None else {key:status['native'].get(key) for key in
                ('status','sequence','native_returned','actual_request_ack')},
            current_action=status['current_action'], numeric=status['numeric'], hud=status['hud'],
            reason=status['reason'], quit=status['quit'], phase_seconds=15, total_seconds=90,
            official_order='UNKNOWN', resource_payload='UNKNOWN', pixels='UNKNOWN',
            delayed_body0_epoch_identifiable=False,
            evidence_prefix='manual-player-life-')
        return row

    def save(self):
        for key, value in self.life_evidence.items():
            _atomic(self.monitor.directory/('manual-player-life-'+key+'.json'), value, 16384, output_only=True)
        return super().save()

    def tick(self, row, broker, state):
        if state == 'CLOSING': return super().tick(row, broker, state)
        if self.stage != 'ATTACK_READY':
            if self.life_runtime is not None and self.life_runtime.phase != 'WAIT_INVENTORY': return
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set(): return
        try:
            service, position, _proof, known = self.current(row, broker)
            if not known: return
            need(self.inventory['status'] == 'COMMITTED' and self.attack['status'] == 'NOT_REQUESTED'
                 and not self.moves and self.life_runtime is not None,
                 'SCENARIO_PLAYER_LIFE_PREPARATION_REQUIRED')
            self.life_runtime.begin(self.move_bound[0], service, position)
            self.save()
        except Exception as error:
            if self.life_runtime is not None: self.life_runtime.fail(error)
            else:
                self.error = launcher.safe_error_code(error) or type(error).__name__
                self.stop.set()
            self.save()


class PlayerDeathRecoveryRuntime:
    """One status-only life cycle, using existing producers and due queries."""
    def __init__(self, original, scenario, broker):
        from tools.local_original_session import player_life as life, player_life_observe as lo
        from tools.local_original_session import player_death_recovery_focused as focused, hp_status_observe as ho
        npc_lethal = type(self) is NpcPlayerLethalRecoveryRuntime
        scenario_type = NpcPlayerLethalRecoveryScenario if npc_lethal else PlayerDeathRecoveryScenario
        button_type = focused.SourceDeadRestartRequests
        if npc_lethal:
            from tools.local_original_session import npc_player_lethal_recovery_focused as focused
            button_type = focused.SourceDeadRestartRequests
        need(type(self) in (PlayerDeathRecoveryRuntime, NpcPlayerLethalRecoveryRuntime)
             and type(original) is launcher.ProductFeatures and type(scenario) is scenario_type
             and type(broker._player_life) is life.Service
             and type(original.player_life_observer) is lo.PlayerLifeObserver
             and broker._player_life_observer is original.player_life_observer
             and type(original.source_dead_restart) is button_type,
             'SCENARIO_PLAYER_LIFE_REAL_FACTORY_REQUIRED')
        self.original,self.manual,self.scenario,self.broker = original,original.manual,scenario,broker
        self.observer,self.button = original.player_life_observer,original.source_dead_restart
        self.life_service = broker._player_life
        from tools.local_original_session.player_death_recovery_focused import PlayerHpOnePreparation
        self.preparation = PlayerHpOnePreparation(broker,scenario.reader)
        self.hp_observer = ho.StatusHpObserver(broker,scenario.reader)
        self.policy = focused.configuration(scenario.features)
        need(self.policy.label == (life.NPC_POLICY_LABEL if npc_lethal else life.POLICY_LABEL)
             and broker._player_life.policy is self.policy,
             'SCENARIO_PLAYER_LIFE_PRODUCTION_LOCAL_POLICY_REQUIRED')
        self.phase = 'WAIT_INVENTORY'
        self.writer=self.row=self.position=self.context=self.result=self.after_context=None
        self.started=self.phase_started=None
        scenario.life_runtime = self

    def _phase(self, phase):
        self.phase,self.phase_started = phase,self.scenario.clock()

    def begin(self, writer, service, position):
        need(self.phase == 'WAIT_INVENTORY' and self.broker.realm.service(writer) is service
             and service.snapshot() is position, 'SCENARIO_PLAYER_LIFE_ONCE_CURRENT_REQUIRED')
        self.writer,self.position = writer,position
        rows = [row for claims in self.broker._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows) == 1, 'SCENARIO_PLAYER_LIFE_CURRENT_WRITER_REQUIRED')
        self.row,self.started = rows[0],self.scenario.clock()
        self._phase('PREPARE_HP1')
        self.scenario.stage='PLAYER_LIFE_RUN'
        self.scenario.life_status['status']='PENDING'

    def current_locked(self):
        need(self.row['operation_lock'].locked() and not self.broker._closing
             and not self.broker.failure.is_set() and not self.original._closed
             and not self.scenario.stop.is_set(), 'SCENARIO_PLAYER_LIFE_CURRENT_OR_CANCELLED')
        now=self.scenario.clock()
        need(0 <= now-self.started < 90 and 0 <= now-self.phase_started < 15,
             'SCENARIO_PLAYER_LIFE_BOUNDED_DEADLINE')
        self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        self.broker.source_guard()
        if self.after_context is not None: ctx=self.after_context
        else: ctx=self.context
        if ctx is not None:
            need(ctx.require_current_locked(self.writer) is self.row, 'SCENARIO_PLAYER_LIFE_CONTEXT_CHANGED')
        else:
            need(self.broker.realm.service(self.writer).snapshot() is self.position,
                 'SCENARIO_PLAYER_LIFE_INITIAL_POSITION_CHANGED')

    async def _capture(self, stage, context):
        async with self.row['operation_lock']:
            self.current_locked()
            try:
                cap=await self.observer.capture_locked(self.writer,context,stage=stage,
                    now_ns=int(self.scenario.clock()*1e9))
            finally:
                self.scenario.life_evidence[stage.lower()]=dict(self.observer.last_result)
            self.current_locked()
            cap.require_stage_locked(self.writer,context,stage=stage)
            return cap

    async def _due(self):
        from tools.local_original_session import hp_status_observe as ho
        phase=self.phase
        if phase=='HP1':
            async with self.row['operation_lock']:
                self.current_locked()
                ready=await self.preparation.sample_one_locked(self.writer,now_ns=int(self.scenario.clock()*1e9))
                self.current_locked()
                self.scenario.life_evidence['hp1']=dict(self.preparation.observation)
            if ready:
                self.context=await self.preparation.life_context_once(self.writer,policy=self.policy)
                self._phase('PRE')
        elif phase in ('PRE','DEAD','RECOVERY','RESTORED'):
            ctx=self.after_context if phase=='RESTORED' else self.context
            try: cap=await self._capture(phase,ctx)
            except ValueError as error:
                # Current stage may legitimately lag the drained producer. No
                # request is repeated and the same explicit deadline remains.
                if str(error) == 'PLAYER_LIFE_'+phase+'_CURRENT_NOT_READY' and phase in ('DEAD','RESTORED'):
                    return
                raise
            if phase=='PRE':
                self.result=await self._lethal(cap)
                self._phase('DEAD')
            elif phase=='DEAD':
                await self.broker.confirm_player_death(self.writer,expected_result=self.result,policy=self.policy)
                async with self.row['operation_lock']:
                    self.current_locked()
                    self.button.publish_locked(self.writer,self.context,self.result)
                self._phase('BUTTON_ACK')
            elif phase=='RECOVERY':
                self.result=await self.broker.recover_player(self.writer,expected_context=self.context,
                    recovery_inputs=cap,policy=self.policy)
                self.after_context=self.result.after_context
                self._phase('RESTORED')
            else:
                await self.broker.confirm_player_recovery(self.writer,expected_result=self.result,policy=self.policy)
                self.scenario.life_status['current_action']='FRESH_CURRENT_QUIET_AFTER_NEW_LIFE'
                self._phase('HP_POST')
        elif phase=='BUTTON_ACK':
            # Keep the real DEAD receipt fresh on the existing due slot while
            # the original callback is pending. No button or wire replay.
            if self.result.metadata()['stage'] != 'ACK_DRAINED':
                await self._capture('DEAD',self.context)
        elif phase in ('HP_POST','HUD'):
            async with self.row['operation_lock']:
                self.current_locked()
                now=int(self.scenario.clock()*1e9)
                raw=await (self.hp_observer.sample(self.writer,now_ns=now) if phase=='HP_POST'
                           else self.hp_observer.sample_hud_bar(self.writer,now_ns=now))
                self.current_locked()
                self.scenario.life_evidence[phase.lower()]=raw
                need(raw.get('status')=='OBSERVED' and raw.get('uid')==self.after_context.target_uid
                     and raw.get('map_id')==self.after_context.map_id and raw.get('sample_monotonic_ns')==now
                     and raw.get('source_contract_valid') is True and raw.get('source_owner_revalidated') is True
                     and raw.get('stable_double_read') is True and raw.get('typed_byte_limit')==16384
                     and type(raw.get('typed_bytes_requested')) is int and 0<=raw['typed_bytes_requested']<=16384
                     and raw.get('max_samples_per_second')==2 and raw.get('snapshot_atomic') is False,
                     'SCENARIO_PLAYER_LIFE_FRESH_HP_HUD_QUERY_REQUIRED')
                snapshot=self.after_context.snapshot
                if phase=='HP_POST':
                    if raw.get('current_hp')==0: return
                    need((raw.get('current_hp'),raw.get('max_hp'))==(snapshot.current_hp,snapshot.maximum_hp),
                         'SCENARIO_PLAYER_LIFE_RESTORED_NUMERIC_MISMATCH')
                    self.scenario.life_status['numeric']='FRESH_CURRENT_MAX_MATCHED'
                    self._phase('HUD')
                else:
                    bar=raw.get('bar',{})
                    need(bar.get('status')=='OBSERVED' and type(bar.get('scale_x')) is float
                         and type(bar.get('scale_y')) is float and type(bar.get('flip_x_u8')) is int
                         and type(bar.get('flip_y_u8')) is int, 'SCENARIO_PLAYER_LIFE_HUD_MODEL_UNKNOWN')
                    actual=(bar['scale_x'],bar['scale_y'])
                    wanted=ho.bar_expected(snapshot.current_hp,snapshot.maximum_hp,bar['flip_x_u8'],bar['flip_y_u8'])
                    if actual != wanted:
                        need(actual==ho.bar_expected(0,snapshot.maximum_hp,bar['flip_x_u8'],bar['flip_y_u8']),
                             'SCENARIO_PLAYER_LIFE_HUD_UNEXPECTED_MODEL')
                        return
                    self.scenario.life_status.update(status='COMMITTED',hud='MODEL_MATCHED')
                    self._phase('DONE');self.scenario.stage='PLAYER_LIFE_COMPLETE_STOP_REQUESTED'
                    self.scenario.stop.set()

    async def _lethal(self, cap):
        return await self.broker.player_lethal_once(self.writer,expected_context=self.context,
            recovery_inputs=cap,policy=self.policy)

    async def poll(self, monitor=None):
        if self.phase=='WAIT_INVENTORY': return await self.original.poll(monitor)
        if self.phase in ('DONE','FAILED'): return {}
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_PLAYER_LIFE_SAME_MONITOR_REQUIRED')
            async with self.row['operation_lock']: self.current_locked()
            if self.phase=='PREPARE_HP1':
                await self.preparation.update_once(self.writer)
                self._phase('HP1')
            elif self.phase=='BUTTON_ACK':
                async with self.row['operation_lock']:
                    self.current_locked()
                    if self.button.poll_locked(): self._phase('RECOVERY')
            if self.phase not in ('DONE','FAILED') and self.scenario.clock()>=monitor.next_memory:
                monitor.next_memory=max(monitor.next_memory,self.scenario.clock()+.5)
                try: await self._due()
                finally: monitor.next_memory=max(monitor.next_memory,self.scenario.clock()+.5)
            self._metadata();self.scenario.save();return {}
        except asyncio.CancelledError:
            self.fail(ValueError('SCENARIO_PLAYER_LIFE_CANCELLED'));self.scenario.save();raise
        except Exception as error:
            self.fail(error);self.scenario.save();return {}

    def _metadata(self):
        status=self.scenario.life_status
        status['preparation']=self.preparation.metadata()
        status['native']=self.button.metadata()
        if self.result is not None: status['server']=self.result.metadata()
        elif self.context is not None and self.broker._player_life is self.life_service:
            cycle=self.life_service._cycles.get(id(self.writer))
            if cycle is not None and cycle.context is self.context:
                # Diagnostic scalar projection only. A terminal Context is not
                # re-admitted, and this report grants no send/current authority.
                status['server']=self.life_service.report(cycle)
        if status['server'] is not None:
            self.scenario.life_evidence['server']=status['server']

    def fail(self, error):
        self._metadata()
        reason=launcher.safe_error_code(error) or type(error).__name__
        self.scenario.life_status.update(status='UNKNOWN',reason=reason)
        self.scenario.error=self.scenario.error or reason
        self.phase='FAILED';self.scenario.stage='PLAYER_LIFE_UNKNOWN_STOP_REQUESTED';self.scenario.stop.set()

    def close(self): return self.original.close()


def npc_player_lethal_recovery_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import npc_player_lethal_recovery_focused as focused, inventory as inv
    focused.configuration(config);focused.broker_options(config)
    need(inventory is True and auto_inventory is False and type(config.inventory_frame) is bytes,
         'SCENARIO_NPC_LETHAL_EXPLICIT_INVENTORY_PREPARATION_REQUIRED')
    inv.validate_frame(config.inventory_frame)
    return config


class NpcPlayerLethalRecoveryScenario(PlayerDeathRecoveryScenario):
    configuration = staticmethod(npc_player_lethal_recovery_configuration)
    source_quit_profile = 'sibling-background-npc-player-lethal-recovery-spawn'

    def summary(self):
        row = super().summary()
        runtime = self.life_runtime
        row['npc_player_lethal_recovery'] = dict(
            status=self.life_status['status'],
            motion_status=None if runtime is None else runtime.motion.trial.result['status'],
            at_goal=False if runtime is None else runtime.motion.trial.at_goal,
            contact_status=None if runtime is None else (runtime.plan.contact_metadata() or {}).get('status'),
            npc_action=self.life_evidence.get('npc-action',{}).get('kind','UNKNOWN'),
            current_npc_attack=self.life_evidence.get('npc-action',{}).get('current_npc_attack',False),
            sequence='4E31_HP0_4E39_RECOVERY', official_damage='UNKNOWN')
        return row


class NpcPlayerLethalRecoveryRuntime(PlayerDeathRecoveryRuntime):
    """Canonical one-step first, actual HP1/PRE, fresh contact and real lethal."""
    def __init__(self, original, scenario, broker):
        super().__init__(original, scenario, broker)
        from tools.local_original_session import npc_player_lethal as lethal
        from tools.local_original_session import npc_player_lethal_recovery_focused as focused
        self.inputs = scenario.features.npc_player_lethal_recovery_input
        need(type(broker._npc_player_lethal) is lethal.Service,
             'SCENARIO_NPC_LETHAL_REAL_SERVICE_REQUIRED')
        self.plan = lethal.Plan(original.npc_session, goal=self.inputs.goal)
        self.motion = focused.ApproachMotionRuntime(original, scenario, goal=self.inputs.goal, plan=self.plan)

    def begin(self, writer, service, position):
        need((position.word0,position.word1) == self.inputs.expected_player_grid,
             'SCENARIO_NPC_LETHAL_EXACT_PLAYER_GRID_REQUIRED')
        super().begin(writer, service, position)
        self.motion.trial.begin(self.broker)
        self._phase('MOTION')
        self.scenario.stage='NPC_LETHAL_MOTION_RUN'

    def current_locked(self):
        super().current_locked()
        if self.phase in ('PREPARE_HP1','HP1','PRE'):
            self.motion.trial.current(self.broker)
            self.plan._check(self.writer, arrived=True)

    async def _capture(self, stage, context):
        cap = await super()._capture(stage, context)
        if stage == 'DEAD':
            raw = self.scenario.life_evidence['dead']
            previous = self.scenario.life_evidence.get('npc-action',{})
            if previous.get('current_npc_attack') is not True:
                self.scenario.life_evidence['npc-action'] = dict(raw.get('npc_action',{}))
        return cap

    async def _lethal(self, cap):
        async with self.row['operation_lock']:
            self.current_locked()
        try:
            return await self.plan.attack(self.writer, expected_context=self.context,
                recovery_inputs=cap, raw_effect=self.inputs.raw_effect)
        finally:
            self.scenario.life_evidence['npc-contact']=self.plan.contact_metadata() or {}

    async def poll(self, monitor=None):
        if self.phase != 'MOTION': return await super().poll(monitor)
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_NPC_LETHAL_SAME_MONITOR_REQUIRED')
            result = await self.motion.poll(monitor)
            if self.motion.trial.phase == 'FAILED':
                raise ValueError('SCENARIO_NPC_LETHAL_MOTION_REFUSED')
            if self.motion.trial.phase == 'DONE':
                async with self.row['operation_lock']:
                    self.plan._check(self.writer, arrived=True)
                self._phase('PREPARE_HP1')
                self.scenario.stage='NPC_LETHAL_HP1_PREPARATION'
            self.scenario.life_evidence['npc-motion'] = dict(self.motion.trial.result)
            self.scenario.save()
            return result
        except asyncio.CancelledError:
            self.fail(ValueError('SCENARIO_NPC_LETHAL_CANCELLED'));self.scenario.save();raise
        except Exception as error:
            self.fail(error);self.scenario.save();return {}

    def close(self):
        try: self.plan.close()
        finally: super().close()


class HpStatusRuntime:
    """Consumes the real status producer and canonical readonly HP observer."""
    def __init__(self,original,scenario,broker):
        from tools.local_original_session import broker as bm,hp_status,hp_status_observe as ho
        need(type(original) is launcher.ProductFeatures and type(broker) is bm.PersistentBroker
             and type(broker._hp_status) is hp_status.Service and broker._hp_status is broker.realm._hp_status,
             'SCENARIO_HP_STATUS_ACTUAL_PRODUCT_REQUIRED')
        self.original,self.manual,self.scenario,self.broker=original,original.manual,scenario,broker
        self.service=broker._hp_status;self.inputs=scenario.features.hp_status_input
        self.png_after_post = type(scenario) is HpStatusPngScenario
        if self.png_after_post:
            scenario.bind_runtime(original)
        self.hud_bar_enabled=self.inputs.observe_hud_bar
        if self.hud_bar_enabled:
            scenario.hp_status['hud_bar']=dict(status='NOT_REQUESTED',value_scope='BAR_POST_MODEL_MATCH_ONLY',
                text='UNKNOWN',callback='UNKNOWN',pixels='UNKNOWN',cpp_lease_proven=False,snapshot_atomic=False)
        self.observer=ho.StatusHpObserver(broker,scenario.reader)
        self.update_method=bm.PersistentBroker.update_hp_status
        self.sample_method=ho.SAMPLE_METHOD
        self.hud_sample_method=ho.HUD_SAMPLE_METHOD
        self.current_method=hp_status.Service.current
        self.phase='WAIT_INVENTORY';self.started_ns=None;self.png_admission_started_ns=None
        self.writer=self.row=self.position=self.move_service=self.refs=self.scalars=None
        self.before=self.after=None;self.update_claimed=self.pre_claimed=False;self.post_samples=0
        scenario.hp_runtime=self

    def _life(self):
        b=self.broker;r=b.realm;reader=self.scenario.reader
        game=r.registry.resolve(self.writer)
        rows=[row for claims in b._claims.values() for row in claims if row['writer'] is self.writer]
        need(len(rows)==1 and rows[0] is self.row and not self.row['failed'] and not self.row['joined'],
             'SCENARIO_HP_STATUS_ROW_CHANGED')
        return (b,b.policy,r,r.registry,game,game.selection,r.service(self.writer),r.service(self.writer).snapshot(),
            self.row,self.row['operation_lock'],self.row['policy_row'],b.source_guard,reader,reader.owner,reader.member,
            reader.backend,reader.sampler,self.original,self.original.manual,self.scenario.features,
            b._hp_status,r._hp_status)

    def _scalar_values(self):
        rd=self.scenario.reader;o,m=rd.owner,rd.member;mv=self.move_service
        return (o.owner_handle,o.owner_job,m.process,m.job,m.pid,m.identity.get('birth'),rd.backend.handle,
            rd.sample_byte_limit,getattr(rd,'closed',False),o.closed,
            mv.requests_received,mv.committed,mv.corrections_prepared)

    def _same(self):
        b=self.broker
        need(self.inputs is self.scenario.features.hp_status_input
             and type(self.hud_bar_enabled) is bool and self.hud_bar_enabled is self.inputs.observe_hud_bar,
             'SCENARIO_HP_STATUS_HUD_PURPOSE_CHANGED')
        need(not b._closing and not b.failure.is_set() and not self.original._closed
             and b._hp_status is b.realm._hp_status is self.service
             and b.realm.service(self.writer) is self.move_service and self.move_service.snapshot() is self.position
             and len(self._life())==len(self.refs) and all(a is c for a,c in zip(self._life(),self.refs))
             and all(type(a) is type(c) and a==c for a,c in zip(self._scalar_values(),self.scalars)),
             'SCENARIO_HP_STATUS_SELECTION_OR_OWNER_CHANGED')
        need(self.position.uid==self.inputs.target_uid and self.position.map_id==self.inputs.map_id,
             'SCENARIO_HP_STATUS_TARGET_CHANGED')

    def current(self):
        from tools.local_original_session import manual_move_commands as mm
        self._same();self.scenario.reader.validate()
        need(self.scenario.owner.validate(self.scenario.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
        self.broker.source_guard();self._same()
        now=int(self.scenario.clock()*1e9)
        need(type(self.started_ns) is int and 0<=now-self.started_ns<15_000_000_000,
             'SCENARIO_HP_STATUS_ORIGINAL_DEADLINE')
        need(not self.scenario.stop.is_set(),'SCENARIO_HP_STATUS_CANCELLED');mm._source_quit_cancel_check()

    def begin(self,writer,move_service,position):
        need(self.phase=='WAIT_INVENTORY','SCENARIO_HP_STATUS_ONCE_REQUIRED')
        self.phase='PRE';self.started_ns=int(self.scenario.clock()*1e9)
        self.writer,self.move_service,self.position=writer,move_service,position
        rows=[row for claims in self.broker._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows)==1,'SCENARIO_HP_STATUS_CURRENT_WRITER_REQUIRED');self.row=rows[0]
        self.refs=self._life();self.scalars=self._scalar_values()
        self.current();self.scenario.stage='HP_STATUS_RUN';self.scenario.hp_status['status']='PENDING'

    def _snapshot(self):
        need(self.row['operation_lock'].locked() and self.service.current.__self__ is self.service
             and self.service.current.__func__ is self.current_method
             and type(self.service).current is self.current_method,
             'SCENARIO_HP_STATUS_CANONICAL_CURRENT_REQUIRED')
        snapshot=self.service.current(self.writer)
        need(snapshot.target_uid==self.inputs.target_uid and snapshot.map_id==self.inputs.map_id,
             'SCENARIO_HP_STATUS_CURRENT_TARGET_REQUIRED')
        return snapshot

    async def _sample(self,stage):
        from tools.local_original_session import hp_status_observe as ho
        need(type(self.observer) is ho.StatusHpObserver and type(self.observer).sample is self.sample_method
             and self.observer.sample.__self__ is self.observer and self.observer.sample.__func__ is self.sample_method,
             'SCENARIO_HP_STATUS_CANONICAL_OBSERVER_REQUIRED')
        if stage=='pre':
            need(not self.pre_claimed,'SCENARIO_HP_STATUS_PRE_QUERY_NO_REPLAY');self.pre_claimed=True
        else:
            self.post_samples+=1;self.scenario.hp_status['post_samples']=self.post_samples
        async with self.row['operation_lock']:
            self.current();snapshot=self._snapshot()
            if stage=='pre':
                self.before=snapshot
                need(snapshot.revision==self.inputs.expected_revision
                     and snapshot.maximum_hp==self.inputs.maximum_hp
                     and snapshot.current_hp!=self.inputs.current_hp,
                     'SCENARIO_HP_STATUS_NO_ACTUAL_CHANGE_OR_STALE_INPUT')
            else:need(snapshot is self.after,'SCENARIO_HP_STATUS_POST_SNAPSHOT_CHANGED')
            sample_ns=int(self.scenario.clock()*1e9)
            if stage=='post':
                need(sample_ns>self.scenario.hp_status['pre']['sample_monotonic_ns']
                     and sample_ns>=self.server_drained_ns,'SCENARIO_HP_STATUS_POST_NOT_FRESH')
            raw=await self.observer.sample(self.writer,now_ns=sample_ns)
            self.current();need(self._snapshot() is snapshot,'SCENARIO_HP_STATUS_SNAPSHOT_CHANGED_DURING_READ')
        self.scenario.hp_status[stage]=raw
        need(type(raw) is dict and type(raw.get('sample_monotonic_ns')) is int
             and raw['sample_monotonic_ns']==sample_ns and raw.get('status')=='OBSERVED'
             and type(raw.get('uid')) is int and raw['uid']==self.inputs.target_uid
             and type(raw.get('map_id')) is int and raw['map_id']==self.inputs.map_id
             and raw.get('observation_scope')=='PASSIVE_READONLY_SNAPSHOT'
             and raw.get('value_scope')=='LOCAL_CHARACTER_CURRENT_MAX_HP'
             and raw.get('original_owning_getter_invoked') is False and raw.get('owning_lease_proven') is False
             and raw.get('source_contract_valid') is True and raw.get('source_owner_revalidated') is True
             and raw.get('stable_double_read') is True and raw.get('snapshot_atomic') is False
             and raw.get('server_authority') is False and raw.get('screen')=='UNKNOWN'
             and type(raw.get('typed_bytes_requested')) is int and 0<=raw['typed_bytes_requested']<=16384
             and raw.get('typed_byte_limit')==16384 and raw.get('max_samples_per_second')==2
             and type(raw.get('current_hp')) is type(raw.get('max_hp')) is int,
             'SCENARIO_HP_STATUS_DIRECT_READ_UNKNOWN')
        if stage=='pre':
            need((raw['current_hp'],raw['max_hp'])==(snapshot.current_hp,snapshot.maximum_hp),
                 'SCENARIO_HP_STATUS_PRE_SERVER_CLIENT_MISMATCH')
            self.phase='UPDATE'
        else:
            observed=(raw['current_hp'],raw['max_hp'])
            self.current()
            if observed==(self.before.current_hp,self.before.maximum_hp):
                self.scenario.hp_status.setdefault('post_wait_initial',dict(raw))
                self.scenario.hp_status['client_hp']='SOURCE_VALID_PREVIOUS_HP_WAITING_SETTER'
                return # Same deadline/2Hz; update is never repeated.
            need(observed==(self.inputs.current_hp,self.inputs.maximum_hp),
                 'SCENARIO_HP_STATUS_POST_UNEXPECTED_HP')
            if self.hud_bar_enabled:
                self.scenario.hp_status.update(numeric_committed=True,
                    client_hp='FRESH_PASSIVE_LOCAL_CHARACTER_FIELDS_MATCHED')
                self.phase='HUD_BAR'
                return
            self.scenario.hp_status.update(status='COMMITTED',client_hp='FRESH_PASSIVE_LOCAL_CHARACTER_FIELDS_MATCHED')
            if self.png_after_post:self.scenario.hp_status['numeric_committed']=True
            self._complete_hp()

    async def _sample_hud_bar(self):
        from tools.local_original_session import hp_status_observe as ho
        need(self.hud_bar_enabled is True and self.phase=='HUD_BAR' and self.update_claimed
             and self.scenario.hp_status.get('numeric_committed') is True,
             'SCENARIO_HP_STATUS_HUD_AFTER_NUMERIC_REQUIRED')
        need(type(self.observer) is ho.StatusHpObserver
             and type(self.observer).sample_hud_bar is self.hud_sample_method
             and self.observer.sample_hud_bar.__self__ is self.observer
             and self.observer.sample_hud_bar.__func__ is self.hud_sample_method,
             'SCENARIO_HP_STATUS_CANONICAL_HUD_OBSERVER_REQUIRED')
        async with self.row['operation_lock']:
            self.current();need(self._snapshot() is self.after,'SCENARIO_HP_STATUS_POST_SNAPSHOT_CHANGED')
            now=int(self.scenario.clock()*1e9)
            need(now>self.scenario.hp_status['post']['sample_monotonic_ns'] and now>=self.server_drained_ns,
                 'SCENARIO_HP_STATUS_HUD_NOT_FRESH')
            raw=await self.observer.sample_hud_bar(self.writer,now_ns=now)
            # Preserve the acquired snapshot before any terminal current-life
            # failure; it grants no current/model completion authority.
            self.scenario.hp_status['hud_bar']['sample']=raw
            self.current();need(self._snapshot() is self.after,'SCENARIO_HP_STATUS_SNAPSHOT_CHANGED_DURING_READ')
        detail=self.scenario.hp_status['hud_bar'];detail['sample']=raw
        need(type(raw) is dict and raw.get('status')=='OBSERVED' and raw.get('sample_monotonic_ns')==now
             and type(raw.get('uid')) is int and raw['uid']==self.inputs.target_uid
             and type(raw.get('map_id')) is int and raw['map_id']==self.inputs.map_id
             and raw.get('observation_scope')=='PASSIVE_READONLY_SNAPSHOT'
             and raw.get('value_scope')=='LOCAL_HP_HUD_BAR_MODEL_ONLY'
             and raw.get('source_contract_valid') is True and raw.get('source_owner_revalidated') is True
             and raw.get('stable_double_read') is True and raw.get('snapshot_atomic') is False
             and raw.get('owning_lease_proven') is False and raw.get('original_owning_getter_invoked') is False
             and raw.get('server_authority') is False and raw.get('screen')=='UNKNOWN'
             and type(raw.get('typed_bytes_requested')) is int and 0<=raw['typed_bytes_requested']<=16384
             and raw.get('typed_byte_limit')==16384 and raw.get('max_samples_per_second')==2,
             'SCENARIO_HP_STATUS_HUD_READ_UNKNOWN')
        bar=raw.get('bar')
        need(type(bar) is dict and bar.get('status')=='OBSERVED'
             and type(bar.get('scale_x')) is type(bar.get('scale_y')) is float
             and type(bar.get('flip_x_u8')) is type(bar.get('flip_y_u8')) is int
             and 0<=bar['flip_x_u8']<=255 and 0<=bar['flip_y_u8']<=255,
             'SCENARIO_HP_STATUS_HUD_MODEL_UNKNOWN')
        model={key:bar[key] for key in ('scale_x','scale_y','flip_x_u8','flip_y_u8')}
        detail.update(model=model,typed_bytes_requested=raw['typed_bytes_requested'])
        actual=(bar['scale_x'],bar['scale_y'])
        wanted=ho.bar_expected(self.after.current_hp,self.after.maximum_hp,bar['flip_x_u8'],bar['flip_y_u8'])
        if actual==wanted:
            detail['status']='MODEL_MATCHED'
            self.scenario.hp_status['status']='COMMITTED'
            self._complete_hp()
            return
        previous=ho.bar_expected(self.before.current_hp,self.before.maximum_hp,bar['flip_x_u8'],bar['flip_y_u8'])
        need(actual==previous,'SCENARIO_HP_STATUS_HUD_UNEXPECTED_MODEL')
        detail['status']='SOURCE_VALID_PREVIOUS_MODEL_WAITING'
        detail.setdefault('initial_wait',dict(raw))

    def _complete_hp(self):
        if self.png_after_post:
            self.phase='PNG_READY';self.scenario.stage='HP_STATUS_PNG_READY'
        else:
            self.phase='DONE';self.scenario.stage='HP_STATUS_COMPLETE_STOP_REQUESTED';self.scenario.stop.set()

    async def _png_current(self, *, starting=False):
        # HP outcome/deadline stay frozen. The existing PNG owns its own once
        # and deadline; its source/current-life gate remains authoritative.
        async with self.row['operation_lock']:
            if starting:self.current()
            else:
                self._same();self.scenario.reader.validate()
                need(self.scenario.owner.validate(self.scenario.owner.child) is True,'RETAINED_BASELINE_OWNER_LOST')
                self.broker.source_guard();self._same()
                need(not self.scenario.stop.is_set(),'SCENARIO_HP_STATUS_CANCELLED')
                from tools.local_original_session import manual_move_commands as mm
                mm._source_quit_cancel_check()
            need(self.scenario.hp_status.get('numeric_committed') is True
                 and self._snapshot() is self.after
                 and (self.after.current_hp,self.after.maximum_hp)==(19,20),
                 'SCENARIO_HP_PNG_CURRENT_NUMERIC_POST_REQUIRED')

    async def _poll_png(self,monitor):
        need(monitor is self.scenario.monitor,'SCENARIO_HP_STATUS_SAME_MONITOR_REQUIRED')
        await self._png_current(starting=self.phase=='PNG_READY')
        if self.phase=='PNG':
            from tools.local_original_session import original_screenshot as screenshot
            row=self.original.original_screenshot.observation()
            if row.get('reason')=='SCREENSHOT_REQUESTED' and row.get('native_sequence') is None:
                # The observer's existing Native-pending clock starts later.
                # Bound only this new pre-admission queue by the same 10s.
                now=screenshot.time.monotonic_ns()
                need(type(self.png_admission_started_ns) is int
                     and 0<=now-self.png_admission_started_ns<screenshot.m.WAIT_NS,
                     'SCENARIO_HP_PNG_ADMISSION_DEADLINE')
        if self.phase=='PNG_READY':
            # Reserve before request: refusal or another poll cannot replay it.
            self.phase='PNG';self.scenario.stage='ORIGINAL_SCREENSHOT_WAIT'
            need(self.scenario.screenshot_requested is False,'SCENARIO_HP_PNG_ONCE_REQUIRED')
            self.scenario.screenshot_requested=True
            from tools.local_original_session import original_screenshot as screenshot
            self.png_admission_started_ns=screenshot.time.monotonic_ns()
            queued=self.original.original_screenshot.request()
            self.scenario.original_screenshot=self.original.original_screenshot.observation()
            need(queued is True,'SCENARIO_SCREENSHOT_REQUEST_REFUSED')
            self.scenario.save()
        return await self.original.poll(monitor)

    async def _update(self):
        from tools.local_original_session import broker as bm
        need(not self.update_claimed,'SCENARIO_HP_STATUS_UPDATE_NO_REPLAY');self.update_claimed=True
        self.current()
        need(type(self.broker) is bm.PersistentBroker and type(self.broker).update_hp_status is self.update_method
             and self.broker.update_hp_status.__self__ is self.broker
             and self.broker.update_hp_status.__func__ is self.update_method,
             'SCENARIO_HP_STATUS_CANONICAL_UPDATE_REQUIRED')
        async with self.row['operation_lock']:
            self.current();need(self._snapshot() is self.before,'SCENARIO_HP_STATUS_EXPECTED_SNAPSHOT_CHANGED')
        result=await self.broker.update_hp_status(self.writer,current_hp=self.inputs.current_hp,
            maximum_hp=self.inputs.maximum_hp,expected_snapshot=self.before,
            expected_revision=self.inputs.expected_revision,policy=self.scenario.features.hp_status_policy)
        self.current();self.server_drained_ns=int(self.scenario.clock()*1e9)
        self.scenario.hp_status['server']=result
        self.scenario.hp_status['server_drained_monotonic_ns']=self.server_drained_ns
        need(type(result) is dict and result.get('status')=='DRAINED','SCENARIO_HP_STATUS_SERVER_DRAIN_REQUIRED')
        async with self.row['operation_lock']:
            self.current();self.after=self._snapshot()
            need(self.after is not self.before and self.after.revision==self.before.revision+1
                 and (self.after.current_hp,self.after.maximum_hp)==(self.inputs.current_hp,self.before.maximum_hp)
                 and {k:v for k,v in self.after.fields.items() if k!=10}=={k:v for k,v in self.before.fields.items() if k!=10},
                 'SCENARIO_HP_STATUS_CURRENT_FULL_FIELDS_CHANGED')
        self.phase='POST'

    async def poll(self,monitor=None):
        if self.phase=='WAIT_INVENTORY':return await self.original.poll(monitor)
        if self.phase in ('DONE','FAILED'):return {}
        try:
            need(monitor is self.scenario.monitor,'SCENARIO_HP_STATUS_SAME_MONITOR_REQUIRED')
            if self.phase in ('PNG_READY','PNG'):
                return await self._poll_png(monitor)
            self.current()
            if self.phase=='UPDATE':await self._update()
            elif self.scenario.clock()>=monitor.next_memory:
                monitor.next_memory=max(monitor.next_memory,self.scenario.clock()+.5)
                try:
                    if self.phase=='HUD_BAR':await self._sample_hud_bar()
                    else:await self._sample('pre' if self.phase=='PRE' else 'post')
                finally:monitor.next_memory=max(monitor.next_memory,self.scenario.clock()+.5)
            self.scenario.save();return {}
        except asyncio.CancelledError:
            self.fail(ValueError('SCENARIO_HP_STATUS_CANCELLED'));self.scenario.save();raise
        except Exception as error:
            self.fail(error);self.scenario.save();return {}

    def fail(self,error):
        reason=launcher.safe_error_code(error) or type(error).__name__
        hud_failed = self.phase=='HUD_BAR' and self.hud_bar_enabled
        if hud_failed:self.scenario.hp_status['hud_bar']['status']='UNKNOWN'
        # After PNG handoff, a PNG/current-owner refusal cannot rewrite the
        # frozen HP model result. Cancellation never starts a new Screenshot.
        if self.phase not in ('PNG_READY','PNG'):
            self.scenario.hp_status.update(status='UNKNOWN',reason=reason)
        elif self.png_after_post:
            self.scenario.png_failure=reason
            if self.scenario.screenshot_requested:
                self.scenario.original_screenshot=self.original.original_screenshot.observation()
        self.scenario.error=self.scenario.error or reason
        if (self.png_after_post and hud_failed
                and self.scenario.hp_status.get('numeric_committed') is True
                and reason!='SCENARIO_HP_STATUS_CANCELLED' and not self.scenario.stop.is_set()):
            self.phase='PNG_READY';self.scenario.stage='HP_STATUS_PNG_READY'
        else:
            self.phase='FAILED';self.scenario.stage='HP_STATUS_UNKNOWN_STOP_REQUESTED';self.scenario.stop.set()

    def close(self):return self.original.close()


def npc_player_hit_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session.npc_player_hit_focused import configuration
    return configuration(config, inventory=inventory, auto_inventory=auto_inventory)


class NpcPlayerHitScenario(HpStatusNotifyScenario):
    configuration = staticmethod(npc_player_hit_configuration)
    source_quit_profile = NPC_PLAYER_HIT_PROFILE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hp_status['scope'] = 'EXPLICIT_LOCAL_NPC_HIT_SELECTED_POSITIVE_HP'
        self.hp_status['npc_player_hit'] = dict(status='NOT_REQUESTED', server=None,
            client_hit='UNKNOWN', own_player_current=None, npc_current=None,
            action_sample=None, pixels='UNKNOWN', automatic_retry=False)
        self.path = self.monitor.directory/'manual-npc-player-hit-scenario.json'

    def summary(self):
        detail = self.hp_status['npc_player_hit']
        return dict(super().summary(), npc_player_hit=dict(
            status=detail['status'], server=detail['server'], client_hit=detail['client_hit'],
            own_player_current=detail['own_player_current'], npc_current=detail['npc_current'],
            pixels='UNKNOWN', evidence_file='manual-hp-status-notify-observations.json'))


class NpcPlayerHitRuntime(HpStatusRuntime):
    """Actual once broker API plus the unchanged HP/HUD/action read consumers."""
    def __init__(self, original, scenario, broker):
        from tools.local_original_session import broker as bm, hp_status, hp_status_observe as ho
        from tools.local_original_session import npc_player_hit, attack_action_observe as ao
        need(type(original) is launcher.ProductFeatures and type(broker) is bm.PersistentBroker
             and type(broker._hp_status) is hp_status.Service
             and broker._hp_status is broker.realm._hp_status
             and type(broker._npc_player_hit) is npc_player_hit.Service
             and broker._npc_player_hit is broker.realm._npc_player_hit,
             'SCENARIO_NPC_PLAYER_HIT_ACTUAL_PRODUCT_REQUIRED')
        self.original, self.manual, self.scenario, self.broker = original, original.manual, scenario, broker
        self.service = broker._hp_status
        self.hit_inputs = scenario.features.npc_player_hit_input
        self.inputs = self.derived_inputs = self.hit_context = self.hit_result = None
        self.png_after_post = False
        self.hud_bar_enabled = True
        scenario.hp_status['hud_bar'] = dict(status='NOT_REQUESTED', value_scope='BAR_POST_MODEL_MATCH_ONLY',
            text='UNKNOWN', callback='UNKNOWN', pixels='UNKNOWN', cpp_lease_proven=False, snapshot_atomic=False)
        self.observer = ho.StatusHpObserver(broker, scenario.reader)
        self.action_observer = ao.AttackActionObserver(broker, scenario.reader)
        self.sample_method, self.hud_sample_method = ho.SAMPLE_METHOD, ho.HUD_SAMPLE_METHOD
        self.current_method = hp_status.Service.current
        self.context_method = bm.PersistentBroker.npc_player_hit_context
        self.hit_method = bm.PersistentBroker.attack_player_once
        self.report_method = bm.PersistentBroker.npc_player_hit_report
        self.phase = 'WAIT_INVENTORY'
        self.started_ns = self.png_admission_started_ns = None
        self.writer = self.row = self.position = self.move_service = self.refs = self.scalars = None
        self.before = self.after = None
        self.update_claimed = self.pre_claimed = False
        self.post_samples = 0
        scenario.hp_runtime = self

    def _same(self):
        b = self.broker
        need(self.hit_inputs is self.scenario.features.npc_player_hit_input
             and self.inputs is self.derived_inputs and self.hud_bar_enabled is True,
             'SCENARIO_NPC_PLAYER_HIT_PURPOSE_CHANGED')
        need(not b._closing and not b.failure.is_set() and not self.original._closed
             and b._hp_status is b.realm._hp_status is self.service
             and b.realm.service(self.writer) is self.move_service and self.move_service.snapshot() is self.position
             and len(self._life()) == len(self.refs) and all(a is c for a, c in zip(self._life(), self.refs))
             and all(type(a) is type(c) and a == c for a, c in zip(self._scalar_values(), self.scalars)),
             'SCENARIO_NPC_PLAYER_HIT_SELECTION_OR_OWNER_CHANGED')
        if self.inputs is not None:
            need((self.position.uid, self.position.map_id) == (self.inputs.target_uid, self.inputs.map_id),
                 'SCENARIO_NPC_PLAYER_HIT_SELECTED_TARGET_CHANGED')

    def begin(self, writer, move_service, position):
        super().begin(writer, move_service, position)
        self.phase = 'CONTEXT'
        self.scenario.hp_status['npc_player_hit']['status'] = 'PENDING'

    async def _context(self):
        from tools.local_original_session import broker as bm, feature_config as fc
        need(type(self.broker).npc_player_hit_context is self.context_method
             and self.broker.npc_player_hit_context.__func__ is self.context_method
             and self.broker.npc_player_hit_context.__self__ is self.broker
             and type(self.broker) is bm.PersistentBroker,
             'SCENARIO_NPC_PLAYER_HIT_CANONICAL_CONTEXT_REQUIRED')
        self.current()
        # Public API owns the existing row lock. This caller holds none.
        context = await self.broker.npc_player_hit_context(self.writer,
            policy=self.scenario.features.npc_player_hit_policy)
        self.current()
        snapshot = context.snapshot
        self.hit_context = context
        self.inputs = self.derived_inputs = fc.HpStatusInput(snapshot.target_uid, snapshot.map_id,
            snapshot.current_hp-1, snapshot.maximum_hp, snapshot.revision, fc.HP_STATUS_SCOPE, True)
        self.phase = 'PRE'

    def _snapshot(self):
        snapshot = super()._snapshot()
        if not self.update_claimed:
            need(self.hit_context is not None and snapshot is self.hit_context.snapshot,
                 'SCENARIO_NPC_PLAYER_HIT_PRE_CONTEXT_CHANGED')
        elif self.hit_result is not None:
            need(self.hit_result.require_current_locked(self.writer) is self.row
                 and snapshot is self.hit_result.after,
                 'SCENARIO_NPC_PLAYER_HIT_CURRENT_RESULT_REQUIRED')
        return snapshot

    async def _update(self):
        from tools.local_original_session import npc_player_hit
        need(not self.update_claimed, 'SCENARIO_NPC_PLAYER_HIT_ONCE_REQUIRED')
        self.update_claimed = True
        self.current()
        need(type(self.broker).attack_player_once is self.hit_method
             and self.broker.attack_player_once.__self__ is self.broker
             and self.broker.attack_player_once.__func__ is self.hit_method,
             'SCENARIO_NPC_PLAYER_HIT_CANONICAL_ONCE_REQUIRED')
        # No row lock is held across either public broker API.
        result = await self.broker.attack_player_once(self.writer, expected_context=self.hit_context,
            raw_effect=self.hit_inputs.raw_effect, direction=self.hit_inputs.direction,
            policy=self.scenario.features.npc_player_hit_policy)
        need(type(result) is npc_player_hit.Result, 'SCENARIO_NPC_PLAYER_HIT_TYPED_RESULT_REQUIRED')
        self.hit_result = result
        metadata = result.metadata()
        self.scenario.hp_status['npc_player_hit']['server'] = metadata
        self.scenario.hp_status['server'] = metadata
        self.current()
        self.server_drained_ns = int(self.scenario.clock()*1e9)
        self.scenario.hp_status['server_drained_monotonic_ns'] = self.server_drained_ns
        need(type(result) is npc_player_hit.Result and result.before is self.before
             and metadata.get('status') == 'COMMITTED'
             and metadata.get('attack_transport') == metadata.get('hp_transport') == 'DRAINED'
             and metadata.get('hp_committed') is True,
             'SCENARIO_NPC_PLAYER_HIT_BOTH_DRAIN_REQUIRED')
        async with self.row['operation_lock']:
            self.current()
            self.after = self._snapshot()
            need(self.after is result.after and self.after is not self.before
                 and self.after.revision == self.before.revision+1
                 and (self.after.current_hp, self.after.maximum_hp) == (self.before.current_hp-1, self.before.maximum_hp)
                 and {k:v for k,v in self.after.fields.items() if k != 10}
                     == {k:v for k,v in self.before.fields.items() if k != 10},
                 'SCENARIO_NPC_PLAYER_HIT_FULL_STATUS_CHANGED')
        self.phase = 'HIT_ACTIONS'

    async def _sample_actions(self):
        from tools.local_original_session import attack_action_observe as ao
        from tools.local_original_session.observe import RetainedSceneReader
        self.current()
        async with self.row['operation_lock']:
            self.current()
            self.hit_result.require_current_locked(self.writer)
            now = int(self.scenario.clock()*1e9)
            need(type(self.action_observer) is ao.AttackActionObserver
                 and self.action_observer.prepare.__self__ is self.action_observer
                 and self.action_observer.prepare.__func__ is ao.AttackActionObserver.prepare
                 and self.scenario.reader.sample.__self__ is self.scenario.reader
                 and self.scenario.reader.sample.__func__ is RetainedSceneReader.sample,
                 'SCENARIO_NPC_PLAYER_HIT_EXISTING_ACTION_QUERY_REQUIRED')
            # Existing own-player -> typed NPC read authority is preserved.
            # No attack dispatch/role reversal/new collector is introduced.
            await self.action_observer.prepare(self.writer, self.hit_context.source_uid, now_ns=now)
            self.current()
            self.hit_result.require_current_locked(self.writer)
            sampled, _count = self.scenario.reader.sample(include_input_state=False,
                attack_action_observer=self.action_observer)
            raw = sampled.get('attack_action', {})
            self.scenario.hp_status['npc_player_hit']['action_sample'] = dict(
                sample_monotonic_ns=now, raw=raw, typed_byte_limit=ao.BYTE_LIMIT)
            self.current()
            self.hit_result.require_current_locked(self.writer)
            self.scenario.hp_status['npc_player_hit']['action_sample']['result_current_revalidated'] = True
        detail = self.scenario.hp_status['npc_player_hit']
        observed = (raw.get('status') == 'OBSERVED' and raw.get('source_contract_valid') is True
            and raw.get('stable_double_read') is True
            and raw.get('actor_uid') == self.after.target_uid
            and raw.get('target_uid') == self.hit_context.source_uid and raw.get('map_id') == self.after.map_id
            and raw.get('typed_byte_limit') == ao.BYTE_LIMIT
            and type(raw.get('combined_typed_bytes_requested')) is int
            and 0 <= raw['combined_typed_bytes_requested'] <= ao.BYTE_LIMIT)
        if observed:
            own = raw.get('attacker', {}).get('current', {})
            npc = raw.get('target', {}).get('current', {})
            detail['own_player_current'] = own.get('kind')
            detail['npc_current'] = npc.get('kind')
            if own.get('status') == 'OBSERVED' and own.get('kind') == 'DamagedAction':
                detail['client_hit'] = 'CURRENT_OWN_DAMAGED_ACTION_OBSERVED'
        self.phase = 'POST'

    def _complete_hp(self):
        detail = self.scenario.hp_status['npc_player_hit']
        detail['status'] = ('COMMITTED' if detail['client_hit'] == 'CURRENT_OWN_DAMAGED_ACTION_OBSERVED'
                            else 'PARTIAL_HIT_UNKNOWN')
        super()._complete_hp()

    async def poll(self, monitor=None):
        if self.phase not in ('CONTEXT', 'HIT_ACTIONS'):
            return await super().poll(monitor)
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_HP_STATUS_SAME_MONITOR_REQUIRED')
            self.current()
            if self.phase == 'CONTEXT':
                await self._context()
            elif self.scenario.clock() >= monitor.next_memory:
                monitor.next_memory = max(monitor.next_memory, self.scenario.clock()+.5)
                try:
                    await self._sample_actions()
                finally:
                    monitor.next_memory = max(monitor.next_memory, self.scenario.clock()+.5)
            self.scenario.save()
            return {}
        except asyncio.CancelledError:
            self.fail(ValueError('SCENARIO_HP_STATUS_CANCELLED'))
            self.scenario.save()
            raise
        except Exception as error:
            self.fail(error)
            self.scenario.save()
            return {}

    def fail(self, error):
        detail = self.scenario.hp_status['npc_player_hit']
        detail['status'] = 'UNKNOWN'
        if (self.update_claimed and type(self.broker).npc_player_hit_report is self.report_method
                and self.broker.npc_player_hit_report.__self__ is self.broker
                and self.broker.npc_player_hit_report.__func__ is self.report_method):
            detail['server'] = self.broker.npc_player_hit_report()
            self.scenario.hp_status['server'] = detail['server']
        return super().fail(error)


def npc_player_hit_repeated_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session.npc_player_hit_focused import repeated_configuration
    return repeated_configuration(config, inventory=inventory, auto_inventory=auto_inventory)


class NpcPlayerHitRepeatedScenario(NpcPlayerHitScenario):
    configuration = staticmethod(npc_player_hit_repeated_configuration)
    source_quit_profile = NPC_PLAYER_HIT_REPEATED_PROFILE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repeat_ordinal = 1
        self.repeat_completed = 0
        self.repeat_status = 'NOT_REQUESTED'
        self.first_preparation = None
        self.path = self.monitor.directory/'manual-npc-player-hit-repeated-scenario.json'

    def summary(self):
        row = super().summary()
        current = row.pop('npc_player_hit')
        evidence = 'manual-npc-player-hit-repeat-%d-observations.json'%self.repeat_ordinal
        current['evidence_file'] = evidence
        row['hp_status_notify']['evidence_file'] = evidence
        server = current.get('server')
        if type(server) is dict:
            current['server'] = {key:server.get(key) for key in ('status', 'source_uid', 'target_uid',
                'damage', 'attack_transport', 'hp_transport', 'hp_committed')}
            if 'phase' in server:
                current['server']['phase'] = server['phase']
            before, after = server.get('before'), server.get('after')
            current['server']['hp'] = [None if type(value) is not dict else value.get('current_hp')
                                       for value in (before, after)]
            current['server']['revision'] = [None if type(value) is not dict else value.get('revision')
                                             for value in (before, after)]
        row['npc_player_hit_repeated'] = dict(status=self.repeat_status,
            explicit_limit=2, completed=self.repeat_completed, active_ordinal=self.repeat_ordinal,
            first_preparation=self.first_preparation, second=current if self.repeat_ordinal == 2 else None,
            per_hit_seconds=15, total_seconds=30, distinct_start='NOT_PROVEN', pixels='UNKNOWN')
        return row

    def save(self):
        _atomic(self.monitor.directory/('manual-npc-player-hit-repeat-%d-observations.json'%self.repeat_ordinal),
            dict(schema='manual-npc-player-hit-repeat-observations-v1', ordinal=self.repeat_ordinal,
                 purpose='REQUIRED_PREPARATION_ONLY' if self.repeat_ordinal == 1 else 'SECOND_POSITIVE_HIT',
                 **self.hp_status), 16384, output_only=True)
        return InventoryAutoScenario.save(self)


class _RepeatedPositiveTrial(NpcPlayerHitRuntime):
    def __init__(self, original, scenario, broker, *, ordinal, previous_result=None):
        super().__init__(original, scenario, broker)
        from tools.local_original_session import broker as bm
        self.hit_inputs = scenario.features.npc_player_hit_repeated_input
        self.context_method = bm.PersistentBroker.npc_player_hit_repeated_context
        self.hit_method = bm.PersistentBroker.attack_player_repeated
        self.ordinal, self.previous_result = ordinal, previous_result

    def _complete_hp(self):
        # Each trial retains its own used once guard and immutable Result.
        detail = self.scenario.hp_status['npc_player_hit']
        detail['status'] = ('COMMITTED' if detail['client_hit'] == 'CURRENT_OWN_DAMAGED_ACTION_OBSERVED'
                            else 'PARTIAL_HIT_UNKNOWN')
        self.phase = 'DONE'
        self.scenario.stage = 'NPC_PLAYER_REPEAT_HIT_%d_COMPLETE'%self.ordinal

    def fail(self, error):
        result = super().fail(error)
        detail = self.scenario.hp_status['npc_player_hit']
        report = detail.get('server')
        if self.hit_result is None and type(report) is dict and self.hit_context is not None:
            snapshot = self.hit_context.snapshot
            before = dict(current_hp=snapshot.current_hp, maximum_hp=snapshot.maximum_hp,
                          revision=snapshot.revision)
            # The last scalar report can still belong to the first completed
            # operation when this request was refused before prepare. This is
            # output classification only; it grants no current authority.
            if report.get('before') != before:
                detail['last_broker_diagnostic'] = report
                detail['server_report_scope'] = 'PREVIOUS_OPERATION_DIAGNOSTIC'
                detail['server'] = self.scenario.hp_status['server'] = None
            else:
                detail['server_report_scope'] = 'CURRENT_CONTEXT_DIAGNOSTIC_ONLY'
        return result

    def _same(self):
        b = self.broker
        need(self.hit_inputs is self.scenario.features.npc_player_hit_repeated_input
             and self.inputs is self.derived_inputs and self.hud_bar_enabled is True,
             'SCENARIO_NPC_PLAYER_HIT_PURPOSE_CHANGED')
        need(not b._closing and not b.failure.is_set() and not self.original._closed
             and b._hp_status is b.realm._hp_status is self.service
             and b.realm.service(self.writer) is self.move_service and self.move_service.snapshot() is self.position
             and len(self._life()) == len(self.refs) and all(a is c for a, c in zip(self._life(), self.refs))
             and all(type(a) is type(c) and a == c for a, c in zip(self._scalar_values(), self.scalars)),
             'SCENARIO_NPC_PLAYER_HIT_SELECTION_OR_OWNER_CHANGED')
        if self.inputs is not None:
            need((self.position.uid, self.position.map_id) == (self.inputs.target_uid, self.inputs.map_id),
                 'SCENARIO_NPC_PLAYER_HIT_SELECTED_TARGET_CHANGED')

    async def _context(self):
        from tools.local_original_session import broker as bm, feature_config as fc
        need(type(self.broker).npc_player_hit_repeated_context is self.context_method
             and self.broker.npc_player_hit_repeated_context.__func__ is self.context_method
             and self.broker.npc_player_hit_repeated_context.__self__ is self.broker
             and type(self.broker) is bm.PersistentBroker,
             'SCENARIO_NPC_PLAYER_HIT_CANONICAL_CONTEXT_REQUIRED')
        self.current()
        # Public API owns the existing row lock. This caller holds none.
        context = await self.broker.npc_player_hit_repeated_context(self.writer,
            policy=self.scenario.features.npc_player_hit_repeated_policy)
        self.current()
        snapshot = context.snapshot
        self.hit_context = context
        self.inputs = self.derived_inputs = fc.HpStatusInput(snapshot.target_uid, snapshot.map_id,
            snapshot.current_hp-1, snapshot.maximum_hp, snapshot.revision, fc.HP_STATUS_SCOPE, True)
        need((snapshot.current_hp, snapshot.maximum_hp) == ((20,20) if self.ordinal == 1 else (19,20)),
             'SCENARIO_NPC_PLAYER_HIT_REPEATED_EXPLICIT_20_19_REQUIRED')
        if self.previous_result is not None:
            need(snapshot is self.previous_result.after,
                 'SCENARIO_NPC_PLAYER_HIT_REPEATED_CONTINUOUS_BEFORE_REQUIRED')
        self.phase = 'PRE'

    async def _update(self):
        from tools.local_original_session import npc_player_hit
        need(not self.update_claimed, 'SCENARIO_NPC_PLAYER_HIT_ONCE_REQUIRED')
        self.update_claimed = True
        self.current()
        need(type(self.broker).attack_player_repeated is self.hit_method
             and self.broker.attack_player_repeated.__self__ is self.broker
             and self.broker.attack_player_repeated.__func__ is self.hit_method,
             'SCENARIO_NPC_PLAYER_HIT_CANONICAL_ONCE_REQUIRED')
        # No row lock is held across either public broker API.
        result = await self.broker.attack_player_repeated(self.writer, expected_context=self.hit_context,
            raw_effect=self.hit_inputs.raw_effect, direction=self.hit_inputs.direction,
            policy=self.scenario.features.npc_player_hit_repeated_policy)
        need(type(result) is npc_player_hit.Result, 'SCENARIO_NPC_PLAYER_HIT_TYPED_RESULT_REQUIRED')
        self.hit_result = result
        metadata = result.metadata()
        self.scenario.hp_status['npc_player_hit']['server'] = metadata
        self.scenario.hp_status['server'] = metadata
        self.current()
        self.server_drained_ns = int(self.scenario.clock()*1e9)
        self.scenario.hp_status['server_drained_monotonic_ns'] = self.server_drained_ns
        need(type(result) is npc_player_hit.Result and result.before is self.before
             and metadata.get('status') == 'COMMITTED'
             and metadata.get('attack_transport') == metadata.get('hp_transport') == 'DRAINED'
             and metadata.get('hp_committed') is True,
             'SCENARIO_NPC_PLAYER_HIT_BOTH_DRAIN_REQUIRED')
        async with self.row['operation_lock']:
            self.current()
            self.after = self._snapshot()
            need(self.after is result.after and self.after is not self.before
                 and self.after.revision == self.before.revision+1
                 and (self.after.current_hp, self.after.maximum_hp) == (self.before.current_hp-1, self.before.maximum_hp)
                 and {k:v for k,v in self.after.fields.items() if k != 10}
                     == {k:v for k,v in self.before.fields.items() if k != 10},
                 'SCENARIO_NPC_PLAYER_HIT_FULL_STATUS_CHANGED')
        self.phase = 'HIT_ACTIONS'


class NpcPlayerHitRepeatedRuntime:
    """Exactly two separate trials over the existing serialized product poll."""
    def __init__(self, original, scenario, broker):
        import copy
        self.original, self.manual, self.scenario, self.broker = original, original.manual, scenario, broker
        self.empty_status = copy.deepcopy(scenario.hp_status)
        self.trials = [_RepeatedPositiveTrial(original, scenario, broker, ordinal=1)]
        self.active = self.trials[0]
        self.phase = 'WAIT_INVENTORY'
        self.started_ns = None
        self.writer = self.move_service = self.position = None
        scenario.hp_runtime = self

    def begin(self, writer, move_service, position):
        need(self.phase == 'WAIT_INVENTORY', 'SCENARIO_NPC_PLAYER_REPEAT_BEGIN_ONCE_REQUIRED')
        self.writer, self.move_service, self.position = writer, move_service, position
        self.started_ns = int(self.scenario.clock()*1e9)
        self.phase = 'RUNNING'
        self.scenario.repeat_status = 'PENDING'
        self.active.begin(writer, move_service, position)

    def current(self):
        now = int(self.scenario.clock()*1e9)
        need(type(self.started_ns) is int and 0 <= now-self.started_ns < 30_000_000_000,
             'SCENARIO_NPC_PLAYER_REPEAT_TOTAL_DEADLINE')
        need(not self.scenario.stop.is_set(), 'SCENARIO_HP_STATUS_CANCELLED')

    async def _completed(self):
        import copy
        active, scenario = self.active, self.scenario
        self.current()
        async with active.row['operation_lock']:
            active.current()
            active.hit_result.require_current_locked(self.writer)
            need(active.hit_result.after is active.after
                 and scenario.hp_status.get('numeric_committed') is True
                 and scenario.hp_status['hud_bar']['status'] == 'MODEL_MATCHED',
                 'SCENARIO_NPC_PLAYER_REPEAT_FRESH_HP_HUD_REQUIRED')
        scenario.repeat_completed = len(self.trials)
        if len(self.trials) == 2:
            scenario.repeat_status = scenario.hp_status['npc_player_hit']['status']
            self.phase = 'DONE'
            scenario.stage = 'NPC_PLAYER_REPEAT_COMPLETE_STOP_REQUESTED'
            scenario.save()
            scenario.stop.set()
            return
        need(len(self.trials) == 1, 'SCENARIO_NPC_PLAYER_REPEAT_EXPLICIT_TWO_LIMIT')
        first = active.hit_result
        scenario.first_preparation = dict(status='REQUIRED_PREPARATION_ONLY',
            before_hp=first.before.current_hp, after_hp=first.after.current_hp,
            before_revision=first.before.revision, after_revision=first.after.revision,
            fresh_hp_hud=True,
            evidence_file='manual-npc-player-hit-repeat-1-observations.json')
        scenario.save()  # Freeze first output before starting a different trial.
        scenario.repeat_ordinal = 2
        scenario.hp_status = copy.deepcopy(self.empty_status)
        second = _RepeatedPositiveTrial(self.original, scenario, self.broker, ordinal=2, previous_result=first)
        self.trials.append(second)
        self.active = second
        scenario.hp_runtime = self
        second.begin(self.writer, self.move_service, self.position)

    async def poll(self, monitor=None):
        if self.phase == 'WAIT_INVENTORY':
            return await self.original.poll(monitor)
        if self.phase in ('DONE', 'FAILED'):
            return {}
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_HP_STATUS_SAME_MONITOR_REQUIRED')
            self.current()
            result = await self.active.poll(monitor)
            if self.active.phase == 'FAILED':
                self.phase = 'FAILED'
                self.scenario.repeat_status = 'UNKNOWN'
                self.scenario.save()
            elif self.active.phase == 'DONE':
                await self._completed()
            return result
        except asyncio.CancelledError:
            self.fail(ValueError('SCENARIO_HP_STATUS_CANCELLED'))
            self.scenario.save()
            raise
        except Exception as error:
            self.fail(error)
            self.scenario.save()
            return {}

    def fail(self, error):
        self.phase = 'FAILED'
        self.scenario.repeat_status = 'UNKNOWN'
        return self.active.fail(error)

    def close(self):
        return self.original.close()


def npc_approach_hit_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session.npc_approach_hit_focused import configuration
    return configuration(config, inventory=inventory, auto_inventory=auto_inventory)


class NpcApproachHitScenario(NpcPlayerHitScenario):
    configuration = staticmethod(npc_approach_hit_configuration)
    source_quit_profile = NPC_APPROACH_HIT_PROFILE

    def __init__(self, *args, **kwargs):
        self.npc_motion_trial = None
        super().__init__(*args, **kwargs)
        self.approach_status = 'NOT_REQUESTED'
        self.contact_evidence = None
        self.path = self.monitor.directory/'manual-npc-approach-hit-scenario.json'

    def summary(self):
        row = super().summary()
        hit = row.pop('npc_player_hit')
        hp = row.pop('hp_status_notify')
        motion = None if self.npc_motion_trial is None else self.npc_motion_trial.result
        server = hit['server']
        compact = None
        if type(server) is dict:
            compact = {key:server.get(key) for key in ('status', 'source_uid', 'target_uid',
                'attack_transport', 'hp_transport', 'hp_committed')}
            for key, field in (('hp', 'current_hp'), ('revision', 'revision')):
                compact[key] = [None if type(server.get(side)) is not dict else server[side].get(field)
                                for side in ('before', 'after')]
            if 'phase' in server: compact['phase'] = server['phase']
        # Full raw producers, budgets and failure diagnostics stay in the files.
        contact = self.contact_evidence
        player = self.features.npc_approach_hit_input.expected_player_grid
        distances = (None if motion is None or motion['server_before'] is None else
            [max(abs(a-b) for a,b in zip(motion[key]['grid'], player)) if motion[key] is not None else None
             for key in ('server_before', 'server_after')])
        row['npc_approach_hit'] = dict(status=self.approach_status,
            motion_status=None if motion is None else motion['status'],
            goal=None if motion is None else motion['goal'],
            at_goal=False if motion is None else motion['at_goal'],
            distance=distances,
            contact=None if contact is None else {key:contact.get(key) for key in
                ('status','predicate_scope','original_arrow_door','typed_bytes_requested','byte_limit','terrain_after_await')},
            server=compact, client_hit=hit['client_hit'],
            own_player_current=hit['own_player_current'], npc_current=hit['npc_current'],
            numeric_status=hp['status'], hud_bar=hp.get('hud_bar'),
            reason=self.hp_status.get('reason') or self.error, motion_seconds=15, hit_seconds=15, total_seconds=30,
            distinct_start='NOT_PROVEN', pixels='UNKNOWN',
            evidence_files=['manual-npc-approach-observations.json', 'manual-npc-contact-observations.json',
                            'manual-npc-approach-hit-observations.json'])
        return row

    def save(self):
        if self.npc_motion_trial is not None:
            _atomic(self.monitor.directory/'manual-npc-approach-observations.json',
                dict(schema='manual-npc-approach-observations-v1', **self.npc_motion_trial.result),
                16384, output_only=True)
        _atomic(self.monitor.directory/'manual-npc-approach-hit-observations.json',
            dict(schema='manual-npc-approach-hit-observations-v1', **self.hp_status), 16384, output_only=True)
        if self.contact_evidence is not None:
            _atomic(self.monitor.directory/'manual-npc-contact-observations.json',
                dict(schema='manual-npc-contact-observations-v1', **self.contact_evidence), 16384, output_only=True)
        return InventoryAutoScenario.save(self)

    def tick(self, row, broker, state):
        if state != 'CLOSING' and self.hp_runtime is not None and self.hp_runtime.phase != 'WAIT_INVENTORY':
            return
        return super().tick(row, broker, state)


class _ApproachHitTrial(NpcPlayerHitRuntime):
    def __init__(self, original, scenario, broker, *, plan, prepare_before_contact=False):
        super().__init__(original, scenario, broker)
        from tools.local_original_session import npc_approach_hit as approach
        need(type(plan) is approach.Plan, 'SCENARIO_APPROACH_TYPED_PLAN_REQUIRED')
        self.plan = plan
        self.hit_inputs = scenario.features.npc_approach_hit_input
        self.context_method = approach.Plan.context
        self.hit_method = approach.Plan.attack
        self.prepare_before_contact = prepare_before_contact
        self.prepared_snapshot = None

    def begin(self, writer, move_service, position):
        super().begin(writer, move_service, position)
        if self.prepare_before_contact:
            self.phase = 'PREPARE'

    async def prepare_hp(self):
        from tools.local_original_session import feature_config as fc
        need(self.prepare_before_contact and self.phase == 'PREPARE'
             and self.prepared_snapshot is None and self.hit_context is None,
             'SCENARIO_APPROACH_HP_PREPARATION_ONCE_REQUIRED')
        async with self.row['operation_lock']:
            self.current()
            need(type(self.service).current is self.current_method
                 and self.service.current.__self__ is self.service
                 and self.service.current.__func__ is self.current_method,
                 'SCENARIO_HP_STATUS_CANONICAL_CURRENT_REQUIRED')
            snapshot = self.service.current(self.writer)
            need((snapshot.target_uid,snapshot.map_id) == (self.position.uid,self.position.map_id),
                 'SCENARIO_HP_STATUS_CURRENT_TARGET_REQUIRED')
            self.prepared_snapshot = snapshot
            self.inputs = self.derived_inputs = fc.HpStatusInput(snapshot.target_uid, snapshot.map_id,
                snapshot.current_hp-1, snapshot.maximum_hp, snapshot.revision, fc.HP_STATUS_SCOPE, True)
            self.current()
        self.phase = 'PRE'

    def _snapshot(self):
        if self.prepare_before_contact and self.hit_context is None:
            snapshot = HpStatusRuntime._snapshot(self)
            need(snapshot is self.prepared_snapshot, 'SCENARIO_APPROACH_HP_PREPARATION_CHANGED')
            return snapshot
        return super()._snapshot()

    def _same(self):
        b = self.broker
        need(self.hit_inputs is self.scenario.features.npc_approach_hit_input
             and self.inputs is self.derived_inputs and self.hud_bar_enabled is True,
             'SCENARIO_NPC_PLAYER_HIT_PURPOSE_CHANGED')
        need(not b._closing and not b.failure.is_set() and not self.original._closed
             and b._hp_status is b.realm._hp_status is self.service
             and b.realm.service(self.writer) is self.move_service and self.move_service.snapshot() is self.position
             and len(self._life()) == len(self.refs) and all(a is c for a, c in zip(self._life(), self.refs))
             and all(type(a) is type(c) and a == c for a, c in zip(self._scalar_values(), self.scalars)),
             'SCENARIO_NPC_PLAYER_HIT_SELECTION_OR_OWNER_CHANGED')
        if self.inputs is not None:
            need((self.position.uid, self.position.map_id) == (self.inputs.target_uid, self.inputs.map_id),
                 'SCENARIO_NPC_PLAYER_HIT_SELECTED_TARGET_CHANGED')

    async def _context(self):
        from tools.local_original_session import feature_config as fc
        need(type(self.plan).context is self.context_method
             and self.plan.context.__self__ is self.plan
             and self.plan.context.__func__ is self.context_method,
             'SCENARIO_APPROACH_CANONICAL_CONTEXT_REQUIRED')
        self.current()
        context = await self.plan.context(self.writer)
        self.current()
        snapshot = context.snapshot
        if self.prepare_before_contact:
            need(self.phase == 'UPDATE' and snapshot is self.before is self.prepared_snapshot,
                 'SCENARIO_APPROACH_PRE_CONTACT_HP_CONTEXT_CHANGED')
            self.hit_context = context
            return # Keep the used PRE observation; Contact -> first write has no typed turn.
        self.hit_context = context
        self.inputs = self.derived_inputs = fc.HpStatusInput(snapshot.target_uid, snapshot.map_id,
            snapshot.current_hp-1, snapshot.maximum_hp, snapshot.revision, fc.HP_STATUS_SCOPE, True)
        self.phase = 'PRE'

    async def _update(self):
        from tools.local_original_session import npc_player_hit
        need(not self.update_claimed, 'SCENARIO_NPC_PLAYER_HIT_ONCE_REQUIRED')
        self.update_claimed = True
        self.current()
        need(type(self.plan).attack is self.hit_method
             and self.plan.attack.__self__ is self.plan
             and self.plan.attack.__func__ is self.hit_method,
             'SCENARIO_APPROACH_CANONICAL_ATTACK_REQUIRED')
        # Only the arrival-bound Plan may dispatch; no generic hit API bypass.
        result = await self.plan.attack(self.writer, expected_context=self.hit_context,
            raw_effect=self.hit_inputs.raw_effect)
        need(type(result) is npc_player_hit.Result, 'SCENARIO_NPC_PLAYER_HIT_TYPED_RESULT_REQUIRED')
        self.hit_result = result
        metadata = result.metadata()
        self.scenario.hp_status['npc_player_hit']['server'] = metadata
        self.scenario.hp_status['server'] = metadata
        self.current()
        self.server_drained_ns = int(self.scenario.clock()*1e9)
        self.scenario.hp_status['server_drained_monotonic_ns'] = self.server_drained_ns
        need(type(result) is npc_player_hit.Result and result.before is self.before
             and metadata.get('status') == 'COMMITTED'
             and metadata.get('attack_transport') == metadata.get('hp_transport') == 'DRAINED'
             and metadata.get('hp_committed') is True,
             'SCENARIO_NPC_PLAYER_HIT_BOTH_DRAIN_REQUIRED')
        async with self.row['operation_lock']:
            self.current()
            self.after = self._snapshot()
            need(self.after is result.after and self.after is not self.before
                 and self.after.revision == self.before.revision+1
                 and (self.after.current_hp, self.after.maximum_hp) == (self.before.current_hp-1, self.before.maximum_hp)
                 and {k:v for k,v in self.after.fields.items() if k != 10}
                     == {k:v for k,v in self.before.fields.items() if k != 10},
                 'SCENARIO_NPC_PLAYER_HIT_FULL_STATUS_CHANGED')
        self.phase = 'HIT_ACTIONS'

    def _complete_hp(self):
        detail = self.scenario.hp_status['npc_player_hit']
        detail['status'] = ('COMMITTED' if detail['client_hit'] == 'CURRENT_OWN_DAMAGED_ACTION_OBSERVED'
                            else 'PARTIAL_HIT_UNKNOWN')
        self.phase = 'DONE'

    def fail(self, error):
        # The last report is diagnostic only; a refused fresh Plan can leave
        # the broker's previous operation report unchanged.
        result = super().fail(error)
        detail = self.scenario.hp_status['npc_player_hit']
        report = detail.get('server')
        if self.hit_result is None and type(report) is dict and self.hit_context is not None:
            snapshot = self.hit_context.snapshot
            before = dict(current_hp=snapshot.current_hp, maximum_hp=snapshot.maximum_hp, revision=snapshot.revision)
            if report.get('before') != before:
                detail['last_broker_diagnostic'] = report
                detail['server_report_scope'] = 'PREVIOUS_OPERATION_DIAGNOSTIC'
                detail['server'] = self.scenario.hp_status['server'] = None
            else: detail['server_report_scope'] = 'CURRENT_CONTEXT_DIAGNOSTIC_ONLY'
        return result


class NpcApproachHitRuntime:
    """One bounded goal, source-bound arrival, then one bounded Plan hit."""
    def __init__(self, original, scenario, broker):
        from tools.local_original_session import npc_approach_hit as approach
        from tools.local_original_session.npc_approach_hit_focused import ApproachMotionRuntime
        self.original, self.manual, self.scenario, self.broker = original, original.manual, scenario, broker
        self.goal = scenario.features.npc_approach_hit_input.goal
        self.plan = approach.Plan(original.npc_session, goal=self.goal,
            policy=scenario.features.npc_approach_hit_policy)
        self.static_contact = scenario.features.npc_approach_hit_policy == approach.STATIC_STEP_CONTACT_POLICY
        self.contact_metadata_method = approach.Plan.contact_metadata
        self.contact_claimed = False
        self.motion = ApproachMotionRuntime(original, scenario, goal=self.goal, plan=self.plan)
        self.hit = None
        self.phase = 'WAIT_INVENTORY'
        self.started_ns = None
        self.writer = self.move_service = self.position = None
        scenario.hp_runtime = self

    def begin(self, writer, move_service, position):
        need(self.phase == 'WAIT_INVENTORY', 'SCENARIO_APPROACH_BEGIN_ONCE_REQUIRED')
        need(move_service is self.broker.realm.service(writer) and move_service.snapshot() is position
             and self.scenario.move_bound[0] is writer
             and (position.word0, position.word1) == self.scenario.features.npc_approach_hit_input.expected_player_grid,
             'SCENARIO_APPROACH_CURRENT_PLAYER_RECIPE_MISMATCH')
        self.writer, self.move_service, self.position = writer, move_service, position
        self.started_ns = int(self.scenario.clock()*1e9)
        self.phase = 'MOTION'
        self.scenario.approach_status = 'PENDING'
        self.motion.trial.begin(self.broker)
        self.scenario.stage = 'NPC_APPROACH_MOTION_RUN'

    def current(self):
        now = int(self.scenario.clock()*1e9)
        need(type(self.started_ns) is int and 0 <= now-self.started_ns < 30_000_000_000,
             'SCENARIO_APPROACH_TOTAL_DEADLINE')
        need(not self.scenario.stop.is_set(), 'SCENARIO_HP_STATUS_CANCELLED')

    def _start_hit(self):
        need(self.hit is None, 'SCENARIO_APPROACH_ONE_HIT_TRIAL_REQUIRED')
        self.hit = _ApproachHitTrial(self.original, self.scenario, self.broker, plan=self.plan,
                                    prepare_before_contact=self.static_contact)
        self.hit.begin(self.writer, self.move_service, self.position)
        self.scenario.hp_runtime = self
        self.phase = 'HP_PREPARE' if self.static_contact else 'HIT'

    async def _contact(self):
        from tools.local_original_session import edge
        need(self.static_contact and not self.contact_claimed,
             'SCENARIO_APPROACH_CONTACT_QUERY_ONCE_REQUIRED')
        self.contact_claimed = True  # Due-turn ingress only; actual query can still be zero.
        need(type(self.plan).contact_metadata is self.contact_metadata_method
             and self.plan.contact_metadata.__self__ is self.plan
             and self.plan.contact_metadata.__func__ is self.contact_metadata_method,
             'SCENARIO_APPROACH_CANONICAL_CONTACT_REQUIRED')
        self.current(); self.motion.trial.current(self.broker)
        try:
            # These APIs own the original row lock. Context is only preparation.
            # Plan.attack privately arms its exact context; the real source query
            # occurs once inside Service.attempt immediately before WRITE_ATTEMPTED.
            await self.hit._context()
            await self.hit._update()
        finally:
            self.scenario.contact_evidence = self.plan.contact_metadata()
        raw = self.scenario.contact_evidence
        need(type(raw) is dict
             and raw.get('predicate_scope') == 'STATIC_SOURCE_STEP_CONTINUE'
             and raw.get('original_arrow_door') == raw.get('terrain_after_await') == 'UNKNOWN'
             and raw.get('stable_double_read') is True and raw.get('snapshot_atomic') is False
             and raw.get('owning_lease') is False and raw.get('aba_excluded') is False
             and type(raw.get('typed_bytes_requested')) is int and 0 <= raw['typed_bytes_requested'] <= edge.LIMIT
             and raw.get('byte_limit') == edge.LIMIT == 40960,
             'SCENARIO_APPROACH_CONTACT_DIRECT_READ_UNKNOWN')
        sample, completed, attempted = (raw.get(key) for key in ('sample_monotonic_ns',
            'completed_monotonic_ns','first_write_attempt_monotonic_ns'))
        need(all(type(value) is int for value in (sample,completed,attempted))
             and 0 <= sample <= completed <= attempted and attempted-completed <= 500_000_000
             and raw.get('freshness_basis') == 'IMMUTABLE_QUERY_VALIDATION_COMPLETED'
             and raw.get('status') == 'OBSERVED_STATIC_CONTINUE',
             'SCENARIO_APPROACH_CONTACT_FIRST_ATTEMPT_DIAGNOSTIC_UNKNOWN')
        self.phase = 'HIT'

    async def poll(self, monitor=None):
        if self.phase == 'WAIT_INVENTORY': return await self.original.poll(monitor)
        if self.phase in ('DONE', 'FAILED'): return {}
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_HP_STATUS_SAME_MONITOR_REQUIRED')
            self.current()
            if self.phase == 'MOTION':
                result = await self.motion.poll(monitor)
                if self.motion.trial.phase == 'FAILED':
                    self.phase = 'FAILED'; self.scenario.approach_status = 'UNKNOWN'
                elif self.motion.trial.phase == 'DONE':
                    self.current()
                    self._start_hit()
            elif self.phase == 'HP_PREPARE':
                result = {}
                if self.hit.phase == 'PREPARE':
                    await self.hit.prepare_hp() # Current server snapshot only; no typed read.
                else:
                    result = await self.hit.poll(monitor)
                    if self.hit.phase == 'FAILED':
                        self.phase = 'FAILED'; self.scenario.approach_status = 'UNKNOWN'
                    elif self.hit.phase == 'UPDATE':
                        self.phase = 'CONTACT'
                        self.scenario.stage = 'NPC_APPROACH_CONTACT_READY'
            elif self.phase == 'CONTACT':
                self.motion.trial.current(self.broker)  # Contact is within the original motion15s.
                result = {}
                if self.scenario.clock() >= monitor.next_memory:
                    monitor.next_memory = max(monitor.next_memory, self.scenario.clock()+.5)
                    try:
                        await self._contact()
                    finally:
                        monitor.next_memory = max(monitor.next_memory, self.scenario.clock()+.5)
            else:
                result = await self.hit.poll(monitor)
                if self.hit.phase == 'FAILED':
                    self.phase = 'FAILED'; self.scenario.approach_status = 'UNKNOWN'
                elif self.hit.phase == 'DONE':
                    self.current()
                    async with self.hit.row['operation_lock']:
                        self.hit.current()
                        self.hit.hit_result.require_current_locked(self.writer)
                    self.phase = 'DONE'
                    self.scenario.approach_status = self.scenario.hp_status['npc_player_hit']['status']
                    self.scenario.stage = 'NPC_APPROACH_HIT_COMPLETE_STOP_REQUESTED'
                    self.scenario.stop.set()
            self.scenario.save()
            return result
        except asyncio.CancelledError:
            self.fail(ValueError('SCENARIO_HP_STATUS_CANCELLED')); self.scenario.save(); raise
        except Exception as error:
            self.fail(error); self.scenario.save(); return {}

    def fail(self, error):
        self.phase = 'FAILED'
        self.scenario.approach_status = 'UNKNOWN'
        if self.hit is not None: self.hit.fail(error)
        elif self.motion.trial.phase != 'DONE': self.motion.trial.fail(error)
        else:
            reason = launcher.safe_error_code(error) or type(error).__name__
            self.scenario.hp_status.update(status='UNKNOWN',reason=reason)
            self.scenario.error = self.scenario.error or reason
            self.scenario.stage = 'NPC_APPROACH_CONTACT_UNKNOWN_STOP_REQUESTED'
            self.scenario.stop.set()

    def close(self):
        self.plan.close()
        return self.original.close()


def npc_respawn_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session.npc_respawn_focused import configuration
    return configuration(config, inventory=inventory, auto_inventory=auto_inventory)


class NpcRespawnScenario(InventoryAutoScenario):
    """Required lethal preparation, one new local NPC generation and fresh pose."""
    configuration = staticmethod(npc_respawn_configuration)
    source_quit_profile = NPC_RESPAWN_PROFILE

    def __init__(self, *args, **kwargs):
        self.respawn_trial = None
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-npc-respawn-scenario.json'
        self.inventory['trial_role'] = 'EXISTING_SOURCE_QUIT_PREPARATION_ONLY'

    def summary(self):
        return dict(super().summary(), npc_respawn_only=True,
            npc_respawn=dict(status='NOT_REQUESTED' if self.respawn_trial is None else self.respawn_trial.result['status'],
                evidence_file='manual-npc-respawn-observations.json',
                scope='CLIENT_REGISTRY_POSE_FRESH_TARGET_LIFE_ONLY', screen='UNKNOWN'),
            trial_preparation='SAVED_ROW_WORLD_ATTACK_DEATH_REMOVE_NOT_FEATURE_RESULTS')

    def save(self):
        if self.respawn_trial is not None:
            _atomic(self.monitor.directory / 'manual-npc-respawn-observations.json',
                dict(schema='manual-npc-respawn-observations-v1', **self.respawn_trial.result),
                16384, output_only=True)
        return super().save()

    def submit_attack(self, row, broker):
        from tools.local_original_session.npc_respawn_focused import publish_preparation_attack
        return publish_preparation_attack(self, row, broker)

    def collect_attack(self, row, broker):
        from tools.local_original_session.npc_respawn_focused import LETHAL_SCOPE, LETHAL_PHASE
        self.current(row, broker)
        need(broker._attack_session is self.attack_session, 'SCENARIO_ATTACK_AUTHORITY_CHANGED')
        result = self._result()
        self.capture_attack_transport()
        if result is None or result['sequence'] < self.ATTACK_SEQUENCE:
            need(self.clock() - self.attack_started < 15, 'SCENARIO_ATTACK_OBSERVATION_EXPIRED')
            return
        need(result['sequence'] == self.ATTACK_SEQUENCE and result.get('status') in ('CLAIMED','PENDING','PREPARED')
             and result.get('cleanup_required') is not True, 'SCENARIO_NPC_RESPAWN_PREPARATION_CONSUMER_REFUSED')
        self.attack['consumer_status'] = result['status']
        if result['status'] != 'PREPARED':
            need(self.clock() - self.attack_started < 15, 'SCENARIO_ATTACK_OBSERVATION_EXPIRED')
            return
        need(result.get('command') == 'AttackTarget' and result.get('native_attempted') is True
             and result.get('phase') == LETHAL_PHASE and result.get('proof_scope') == LETHAL_SCOPE
             and result.get('cleanup_required') is False,
             'SCENARIO_NPC_RESPAWN_EXACT_PREPARATION_RESULT_REQUIRED')
        need(self.respawn_trial is not None, 'SCENARIO_NPC_RESPAWN_RUNTIME_REQUIRED')
        self.attack.update(status='PREPARED', phase=LETHAL_PHASE, proof_scope=LETHAL_SCOPE,
            combat_effect='LOCAL_LETHAL_PREPARATION_ONLY', client_death='UNKNOWN',
            attack_action_complete='NOT_CLAIMED')
        self.respawn_trial.queue_preparation(broker)
        self.stage = 'NPC_RESPAWN_RUN'

    def tick(self, row, broker, state):
        if self.stage == 'NPC_RESPAWN_RUN' and state != 'CLOSING':
            return
        return super().tick(row, broker, state)


class NpcRespawnMotionScenario(NpcRespawnScenario):
    """Required fresh gen1 preparation, then one explicitly supplied local step."""
    summary_byte_limit = 8192

    def __init__(self, *args, npc_respawn_motion_goal, **kwargs):
        need(type(npc_respawn_motion_goal) is tuple and npc_respawn_motion_goal == (32578, 32946)
             and all(type(n) is int for n in npc_respawn_motion_goal),
             'SCENARIO_RESPAWN_MOTION_EXPLICIT_GOAL_REQUIRED')
        self.npc_respawn_motion_goal, self.respawn_motion = npc_respawn_motion_goal, None
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-npc-respawn-motion-scenario.json'

    def summary(self):
        action = self.respawn_motion
        return dict(super().summary(), npc_respawn_motion_only=True,
            npc_respawn_motion=dict(status='NOT_REQUESTED' if action is None else action.result['status'],
                goal=list(self.npc_respawn_motion_goal), evidence_file='manual-npc-respawn-motion-observations.json',
                scope='GEN1_ONE_EXPLICIT_LOCAL_NPC_STEP', screen='UNKNOWN'),
            trial_preparation='FRESH_GEN1_RESPAWN_REQUIRED_PREPARATION_ONLY')

    def save(self):
        if self.respawn_motion is not None:
            _atomic(self.monitor.directory / 'manual-npc-respawn-motion-observations.json',
                dict(schema='manual-npc-respawn-motion-observations-v1', **self.respawn_motion.result),
                16384, output_only=True)
        return super().save()

    def tick(self, row, broker, state):
        if self.stage == 'NPC_RESPAWN_MOTION_RUN' and state != 'CLOSING':
            return
        return super().tick(row, broker, state)


class NpcRespawnNextHitScenario(NpcRespawnScenario):
    """Respawn preparation followed by one normal attack on its new life."""
    source_quit_profile = NPC_RESPAWN_NEXT_HIT_PROFILE

    def __init__(self, *args, **kwargs):
        self.respawn_followup = None
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-npc-respawn-next-hit-scenario.json'

    def summary(self):
        followup = self.respawn_followup
        return dict(super().summary(), npc_respawn_next_hit_only=True,
            npc_respawn_next_hit=dict(status='NOT_REQUESTED' if followup is None else followup.result['status'],
                evidence_file='manual-npc-respawn-next-hit-observations.json',
                scope='ONE_NORMAL_ATTACK_ON_NEW_LOCAL_NPC_LIFE', screen='UNKNOWN'),
            trial_preparation='SAVED_ROW_LETHAL_REMOVE_RESPAWN_REGISTRY_POSE_NOT_FEATURE_RESULTS')

    def save(self):
        if self.respawn_followup is not None:
            _atomic(self.monitor.directory / 'manual-npc-respawn-next-hit-observations.json',
                dict(schema='manual-npc-respawn-next-hit-v1', **self.respawn_followup.result), 16384, output_only=True)
        return super().save()

    def finalize(self):
        if self.respawn_followup is None or self.respawn_followup.phase == 'WAIT_RESPAWN_COMPLETE':
            return super().finalize()
        # Aggregate session counters now include the new hit. Preserve the
        # initial PREPARED evidence while retaining the actual final refusal.
        try:
            result = self._result()
            if result is not None and result.get('status') == 'UNKNOWN':
                self.error = self.error or 'SCENARIO_STRICT_CONSUMER_REFUSED'
        except Exception as error:
            self.error = self.error or launcher.safe_error_code(error) or type(error).__name__

    def tick(self, row, broker, state):
        if self.stage == 'NPC_RESPAWN_NEXT_HIT_RUN' and state != 'CLOSING':
            return
        return super().tick(row, broker, state)


class NpcRespawnNextHitRemoveScenario(NpcRespawnNextHitScenario):
    """Required gen1 hit followed by one explicit removal and fresh absence."""
    summary_byte_limit = 8192
    def __init__(self, *args, **kwargs):
        self.respawn_retire = None
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-npc-respawn-next-hit-remove-scenario.json'

    def summary(self):
        retire = self.respawn_retire
        return dict(super().summary(), npc_respawn_next_hit_remove_only=True,
            npc_respawn_next_hit_remove=dict(status='NOT_REQUESTED' if retire is None else retire.result['status'],
                evidence_file='manual-npc-respawn-next-hit-remove-observations.json',
                scope='GEN1_ORDINAL2_REMOVE_AND_FRESH_UID_ABSENCE', screen='UNKNOWN', free='UNKNOWN'),
            trial_preparation='RESPAWN_AND_NEXT_HIT_REQUIRED_PREPARATION_ONLY')

    def save(self):
        if self.respawn_retire is not None:
            _atomic(self.monitor.directory / 'manual-npc-respawn-next-hit-remove-observations.json',
                dict(schema='manual-npc-retire-second-life-v1', **self.respawn_retire.result), 16384, output_only=True)
        return super().save()

    def tick(self, row, broker, state):
        if self.stage == 'NPC_RETIRE_SECOND_LIFE_RUN' and state != 'CLOSING':
            return
        return super().tick(row, broker, state)


class NpcSecondRespawnScenario(NpcRespawnNextHitRemoveScenario):
    """Required gen1 retirement, then one explicit second local respawn."""
    def __init__(self,*args,**kwargs):
        self.second_respawn=None
        super().__init__(*args,**kwargs)
        self.path=self.monitor.directory/'manual-npc-second-respawn-scenario.json'

    def summary(self):
        action=self.second_respawn
        return dict(super().summary(),npc_second_respawn_only=True,
            npc_second_respawn=dict(status='NOT_REQUESTED' if action is None else action.result['status'],
                evidence_file='manual-npc-second-respawn-observations.json',
                scope='SECOND_EXPLICIT_SAME_UID_LOCAL_LIFE_ONLY',screen='UNKNOWN',hp='LAZY_INITIAL_ON_NEXT_REAL_ATTACK'),
            trial_preparation='GEN1_RETIREMENT_REQUIRED_PREPARATION_ONLY')

    def save(self):
        if self.second_respawn is not None:
            _atomic(self.monitor.directory/'manual-npc-second-respawn-observations.json',
                dict(schema='manual-npc-second-respawn-v1',**self.second_respawn.result),16384,output_only=True)
        return super().save()

    def tick(self,row,broker,state):
        if self.stage=='NPC_SECOND_RESPAWN_RUN' and state!='CLOSING':return
        return super().tick(row,broker,state)


class NpcCurrentLifeNextHitScenario(NpcSecondRespawnScenario):
    """Required second respawn followed by one normal hit on current gen2."""
    def __init__(self,*args,**kwargs):
        self.current_life_hit=None
        super().__init__(*args,**kwargs)
        self.path=self.monitor.directory/'manual-npc-current-life-next-hit-scenario.json'

    def summary(self):
        action=self.current_life_hit
        return dict(super().summary(),npc_current_life_next_hit_only=True,
            npc_current_life_next_hit=dict(status='NOT_REQUESTED' if action is None else action.result['status'],
                evidence_file='manual-npc-current-life-next-hit-observations.json',
                scope='ONE_NORMAL_ATTACK_ON_CURRENT_GEN2_LOCAL_NPC_LIFE',screen='UNKNOWN'),
            trial_preparation='SECOND_RESPAWN_REQUIRED_PREPARATION_ONLY')

    def save(self):
        if self.current_life_hit is not None:
            _atomic(self.monitor.directory/'manual-npc-current-life-next-hit-observations.json',
                dict(schema='manual-npc-current-life-next-hit-v1',**self.current_life_hit.result),16384,output_only=True)
        return super().save()

    def tick(self,row,broker,state):
        if self.stage=='NPC_CURRENT_LIFE_NEXT_HIT_RUN' and state!='CLOSING':return
        return super().tick(row,broker,state)


class NpcCurrentLifeRetireScenario(NpcCurrentLifeNextHitScenario):
    """Required gen2 normal hit, then one current-life removal and absence."""
    def __init__(self,*args,**kwargs):
        self.current_life_retire=None
        super().__init__(*args,**kwargs)
        self.path=self.monitor.directory/'manual-npc-current-life-retire-scenario.json'

    def summary(self):
        action=self.current_life_retire
        return dict(super().summary(),npc_current_life_retire_only=True,
            npc_current_life_retire=dict(status='NOT_REQUESTED' if action is None else action.result['status'],
                evidence_file='manual-npc-current-life-retire-observations.json',
                scope='GEN2_ORDINAL3_REMOVE_AND_FRESH_UID_ABSENCE',screen='UNKNOWN',free='UNKNOWN'),
            trial_preparation='CURRENT_GEN2_NORMAL_HIT_REQUIRED_PREPARATION_ONLY')

    def save(self):
        if self.current_life_retire is not None:
            _atomic(self.monitor.directory/'manual-npc-current-life-retire-observations.json',
                dict(schema='manual-npc-current-life-retire-v1',**self.current_life_retire.result),16384,output_only=True)
        return super().save()

    def tick(self,row,broker,state):
        if self.stage=='NPC_CURRENT_LIFE_RETIRE_RUN' and state!='CLOSING':return
        return super().tick(row,broker,state)


class NpcMotionGoalScenario(InventoryAutoScenario):
    """Saved-row preparation and one explicit NPC goal; no attack command."""
    configuration = staticmethod(npc_motion_configuration)

    def __init__(self, *args, npc_motion_goal, **kwargs):
        from tools.local_original_session.npc_motion_focused import grid
        need(type(npc_motion_goal) is tuple and grid(npc_motion_goal) == npc_motion_goal,
             'SCENARIO_NPC_MOTION_EXPLICIT_GOAL_REQUIRED')
        self.npc_motion_goal, self.npc_motion_trial = npc_motion_goal, None
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-npc-motion-goal-scenario.json'
        self.inventory['trial_role'] = 'EXISTING_SOURCE_QUIT_PREPARATION_ONLY'

    def summary(self):
        return dict(super().summary(), npc_motion_goal_only=True,
            npc_motion_goal=dict(status='NOT_REQUESTED' if self.npc_motion_trial is None
                else self.npc_motion_trial.result['status'],
                evidence_file='manual-npc-motion-goal-observations.json',
                client_pose_authority=False, screen='UNKNOWN'))

    def save(self):
        if self.npc_motion_trial is not None:
            _atomic(self.monitor.directory / 'manual-npc-motion-goal-observations.json',
                dict(schema='manual-npc-motion-goal-observations-v1', **self.npc_motion_trial.result),
                16384, output_only=True)
        return super().save()

    def collect_inventory(self, row, broker):
        super().collect_inventory(row, broker)
        if self.stage == 'ATTACK_READY':
            need(self.npc_motion_trial is not None, 'SCENARIO_NPC_MOTION_RUNTIME_REQUIRED')
            self.npc_motion_trial.begin(broker)
            self.stage = 'NPC_MOTION_RUN'

    def tick(self, row, broker, state):
        if self.stage == 'NPC_MOTION_RUN' and state != 'CLOSING':
            return
        return super().tick(row, broker, state)


class NpcHpDeathScenario(InventoryAutoScenario):
    """Saved-row preparation, normal Attack2, explicit NPC lifetime trial."""
    def __init__(self, *args, **kwargs):
        from tools.local_original_session.npc_combat_focused import configuration
        configuration(kwargs['features'])
        self.npc_trial = None
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-npc-hp-death-scenario.json'
        self.inventory['trial_role'] = 'EXISTING_SOURCE_QUIT_PREPARATION_ONLY'

    def summary(self):
        return dict(super().summary(), npc_hp_death_only=True,
            npc_hp_death=dict(status='NOT_REQUESTED' if self.npc_trial is None else self.npc_trial.result['status'],
                evidence_file='manual-npc-hp-death-observations.json',
                observation_scope='SEPARATE_TRANSPORT_ACTION_AND_REGISTRY', screen='UNKNOWN'),
            trial_preparation='SAVED_ROW_AND_WORLD_NOT_FEATURE_RESULTS')

    def save(self):
        if self.npc_trial is not None:
            _atomic(self.monitor.directory / 'manual-npc-hp-death-observations.json',
                dict(schema='manual-npc-hp-death-observations-v1', **self.npc_trial.result),
                16384, output_only=True)
        return super().save()

    def collect_attack(self, row, broker):
        super().collect_attack(row, broker)
        if self.stage == 'MOVE_READY':
            need(self.npc_trial is not None, 'SCENARIO_NPC_RUNTIME_REQUIRED')
            self.npc_trial.begin(broker)
            self.stage = 'NPC_RUN'

    def tick(self, row, broker, state):
        if self.stage == 'NPC_RUN' and state != 'CLOSING':
            return  # The existing asynchronous feature poll owns continuation.
        return super().tick(row, broker, state)


def npc_dead_goal_configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session.npc_dead_goal_focused import configuration
    return configuration(config, base_configuration=attack_configuration,
                         inventory=inventory, auto_inventory=auto_inventory)


class NpcDeadGoalScenario(NpcHpDeathScenario):
    """One live arrival, original lethal Attack2, original DEAD/IDLE consumer."""
    configuration = staticmethod(npc_dead_goal_configuration)

    def collect_inventory(self, row, broker):
        result = self._result() if self.features.inventory_collection_policy is not None else None
        if result is not None and result.get('status') == 'COMMITTED':
            # Reuse actual257's two-row readiness consumer only at its original
            # COMMITTED branch; pending keeps this scenario's original super.
            NpcHpFeedbackOnlyScenario.collect_inventory(self, row, broker)
        else:
            super().collect_inventory(row, broker)
        if self.stage == 'ATTACK_READY':
            need(self.npc_trial is not None, 'SCENARIO_DEAD_GOAL_RUNTIME_REQUIRED')
            self.npc_trial.arm(broker)

    def collect_attack(self, row, broker):
        # Reuse real command result/once feedback/counter/intent checks, then
        # run only arrival/death cleanup; no full Death/Remove trial repeats.
        InventoryAutoScenario.collect_attack(self, row, broker)
        if self.stage == 'MOVE_READY':
            self.npc_trial.begin(broker)

    def tick(self, row, broker, state):
        if self.stage in ('NPC_DEAD_GOAL_LIVE_READY', 'NPC_DEAD_GOAL_RUN') and state != 'CLOSING':
            return
        return super().tick(row, broker, state)

    def summary(self):
        result = dict(super().summary(), npc_dead_goal_only=True)
        result['npc_hp_death'] = dict(result['npc_hp_death'],
            observation_scope='SERVER_DEAD_GOAL_RUNTIME_CLEANUP')
        return result


class UseItemScenario(InventoryAutoScenario):
    """One source-validated item intent between Attack2 and Move4/return5."""
    source_quit_profile = USE_ITEM_PROFILE
    USE_SEQUENCE = 3

    def __init__(self, *args, use_item_only=False, use_item_effect=False, use_item_ui_observe=False, **kwargs):
        need(type(use_item_only) is bool, 'SCENARIO_USE_ITEM_ONLY_BOOL_REQUIRED')
        need(type(use_item_effect) is bool and (not use_item_effect or use_item_only),
             'SCENARIO_USE_ITEM_EFFECT_FOCUSED_REQUIRED')
        need(type(use_item_ui_observe) is bool and (not use_item_ui_observe or use_item_effect and use_item_only),
             'SCENARIO_USE_ITEM_UI_OBSERVE_EFFECT_FOCUSED_REQUIRED')
        self.use_item_only, self.use_item_effect = use_item_only, use_item_effect
        self.use_item_ui_observe = use_item_ui_observe
        if use_item_ui_observe:
            self.source_quit_profile = USE_ITEM_UI_PROFILE
        self.use_ui = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN', model_uid=None, model_d4=None,
                           pixel_render='UNKNOWN', slot848_visibility='UNKNOWN', effective_visibility='UNKNOWN')
        self.use_ui_queued = False
        self.use_ui_started_ns = self.use_ui_last_query_ns = self.use_ui_last_native_sequence = None
        self.use_ui_observation = None
        self.use_runtime = None
        self.use_effect = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN', client_state='UNKNOWN',
                               render='UNKNOWN', hp='UNKNOWN')
        self.use_effect_initial = self.use_effect_final = self.use_effect_initial_raw = self.use_effect_final_raw = None
        self.use_effect_started = None
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
        if use_item_effect:
            from tools.local_original_session.item_equipment_effect import POLICY as EFFECT_POLICY
            need(self.features.item_equipment_policy == EFFECT_POLICY,
                 'SCENARIO_USE_ITEM_EFFECT_POLICY_REQUIRED')
        else:
            need(self.features.item_equipment_policy is None,
                 'SCENARIO_USE_ITEM_EFFECT_OPT_IN_REQUIRED')
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
        if getattr(self, 'use_item_effect', False):
            row['verification_scope'] = 'INITIAL_SAVED_ROW_USE_EFFECT_QUIT'
            row['use_item_effect'] = {key: self.use_effect[key] for key in ('status', 'proof_scope', 'client_state')}
            row['use_item_effect']['observation_file'] = 'manual-use-item-effect-observation.json'
        if getattr(self, 'use_item_ui_observe', False):
            row['verification_scope'] = 'INITIAL_ROW_USE_EFFECT_READONLY_UI_PRIMITIVE_QUIT'
            row['use_item_ui'] = {key: self.use_ui[key] for key in ('status', 'proof_scope', 'model_uid', 'model_d4')}
            row['use_item_ui']['observation_file'] = 'manual-use-item-ui-observation.json'
        return row

    def save(self):
        if getattr(self, 'use_item_ui_observe', False):
            _atomic(self.monitor.directory / 'manual-use-item-ui-observation.json',
                dict(schema='manual-use-item-ui-observation-v1', ui=self.use_ui,
                     observation=self.use_ui_observation), 4096, output_only=True)
        if getattr(self, 'use_item_effect', False):
            _atomic(self.monitor.directory / 'manual-use-item-effect-observation.json',
                dict(schema='manual-use-item-effect-observation-v1', effect=self.use_effect,
                     initial=self.use_effect_initial, current=self.use_effect_final,
                     initial_raw=self.use_effect_initial_raw, current_raw=self.use_effect_final_raw),
                32768, output_only=True)
        _atomic(self.monitor.directory / 'manual-use-item-observation.json',
            dict(schema='manual-use-item-observation-v1', use_item=self.use_item,
                 last_consumer_result=self.last_consumer_result), 2048, output_only=True)
        return super().save()

    def bind_runtime(self, runtime):
        need(type(runtime) is launcher.ProductFeatures and self.use_runtime is None
             and runtime.equipment_observer is not None,
             'SCENARIO_USE_ITEM_EFFECT_ACTUAL_RUNTIME_REQUIRED')
        self.use_runtime = runtime

    def _effect_current(self, broker):
        runtime = self.use_runtime
        need(type(runtime) is launcher.ProductFeatures, 'SCENARIO_USE_ITEM_EFFECT_RUNTIME_REQUIRED')
        actual, writer, _effect = runtime._equipment_binding()
        need(actual is broker and writer is self.move_bound[0],
             'SCENARIO_USE_ITEM_EFFECT_RUNTIME_BINDING_CHANGED')
        return runtime, writer

    def _effect_receipt(self, receipt, *, initial, position, identifier):
        from tools.local_original_session.item_equipment_effect import POLICY, SCHEMA
        need(type(receipt) is dict, 'SCENARIO_USE_ITEM_EFFECT_RECEIPT_REQUIRED')
        reason = launcher.safe_error_code(ValueError(receipt.get('reason')))
        need(receipt.get('status') == ('SYNCHRONIZED' if initial else 'COMMITTED'),
             reason or 'SCENARIO_USE_ITEM_EFFECT_AUTHORITATIVE_STATUS_REQUIRED')
        need(type(receipt) is dict and receipt.get('schema') == SCHEMA and receipt.get('policy') == POLICY
             and receipt.get('operation') == ('INITIAL_SYNC' if initial else 'ITEM_USE_EFFECT')
             and receipt.get('status') == ('SYNCHRONIZED' if initial else 'COMMITTED')
             and receipt.get('phase') == 'DRAINED' and receipt.get('reason') is None
             and receipt.get('writer_bound') is True and receipt.get('generation_bound') is True
             and type(receipt.get('character_uid')) is int and receipt['character_uid'] == position.uid
             and type(receipt.get('item_uid')) is int and receipt['item_uid'] == identifier
             and type(receipt.get('template')) is int and receipt['template'] == 1
             and receipt.get('inventory_frame_changed') is False and receipt.get('client_state') == 'UNKNOWN'
             and all(receipt.get(k) is True for k in ('write_attempted', 'drain_returned', 'post_owner_verified'))
             and type(receipt.get('notification_opcode')) is int and receipt['notification_opcode'] == 0x097a
             and type(receipt.get('notification_size')) is int and 6 <= receipt['notification_size'] <= 64
             and type(receipt.get('notification_sha256')) is str
             and len(receipt['notification_sha256']) == 64
             and all(c in '0123456789abcdef' for c in receipt['notification_sha256'])
             and type(receipt.get('equipment_key_i32')) is int
             and -(1 << 31) <= receipt['equipment_key_i32'] < (1 << 31)
             and type(receipt.get('after_weapon_uid')) is int and receipt['after_weapon_uid'] in (0, identifier)
             and type(receipt.get('after_revision')) is int and 0 < receipt['after_revision'] < (1 << 64),
             'SCENARIO_USE_ITEM_EFFECT_AUTHORITATIVE_DRAIN_REQUIRED')
        if initial:
            source = ('LOCAL_FIRST_ENABLE_EMPTY' if self.features.item_equipment_first_enable
                      and receipt.get('initialization_source') == 'LOCAL_FIRST_ENABLE_EMPTY'
                      else 'RESTORED_EQUIPMENT_SIDECAR')
            need(receipt.get('accepted_ordinal') is None and receipt.get('initialization_source') == source
                 and receipt.get('persist_attempted') is (source == 'LOCAL_FIRST_ENABLE_EMPTY')
                 and receipt.get('persisted') is (source == 'LOCAL_FIRST_ENABLE_EMPTY'),
                 'SCENARIO_USE_ITEM_EFFECT_INITIALIZATION_REQUIRED')
            if source == 'LOCAL_FIRST_ENABLE_EMPTY':
                need(receipt['after_weapon_uid'] == 0, 'SCENARIO_USE_ITEM_EFFECT_FIRST_ENABLE_EMPTY_REQUIRED')
        else:
            prior = self.use_effect_initial
            from tools.local_original_session import inventory
            quantity = dict(inventory.validate_frame(self.auto_inventory_frame).raw_fields)[4]
            need(type(receipt.get('accepted_ordinal')) is int and receipt['accepted_ordinal'] == 1
                 and receipt['equipment_key_i32'] == prior['equipment_key_i32']
                 and type(receipt.get('before_weapon_uid')) is int
                 and receipt['before_weapon_uid'] == prior['after_weapon_uid']
                 and receipt['after_weapon_uid'] == (identifier if prior['after_weapon_uid'] == 0 else 0)
                 and type(receipt.get('before_revision')) is int
                 and receipt['before_revision'] == prior['after_revision']
                 and receipt['after_revision'] == prior['after_revision'] + 1
                 and receipt.get('persist_attempted') is True and receipt.get('persisted') is True
                 and type(receipt.get('quantity_before')) is int and receipt['quantity_before'] == quantity
                 and type(receipt.get('quantity_after')) is int and receipt['quantity_after'] == quantity,
                 'SCENARIO_USE_ITEM_EFFECT_EXACT_TOGGLE_REQUIRED')

    def _effect_raw(self, raw, receipt, position):
        need(type(raw) is dict and raw.get('status') == 'OBSERVED' and raw.get('reason') is None
             and all(raw.get(k) is True for k in ('source_contract_valid', 'stable_double_read', 'source_owner_revalidated'))
             and raw.get('read_consistency') == 'STRICT_STABLE'
             and all(raw.get(k) is False for k in ('snapshot_atomic', 'equipped_state_proven',
                 'item_uid_equivalence_proven', 'slot_names_proven', 'visible_screen_claimed'))
             and type(raw.get('selected_uid')) is int and raw['selected_uid'] == position.uid
             and type(raw.get('map_id')) is int and raw['map_id'] == position.map_id
             and type(raw.get('rows')) is list and type(raw.get('entry_count')) is int
             and raw['entry_count'] == len(raw['rows']) <= 128
             and type(raw.get('empty')) is bool and raw['empty'] is (not raw['rows'])
             and type(raw.get('typed_bytes_requested')) is int and 0 < raw['typed_bytes_requested'] <= 16384
             and raw.get('typed_byte_limit') == 16384 and raw.get('max_samples_per_second') == 2
             and type(raw.get('query_started_monotonic_ns')) is int and raw['query_started_monotonic_ns'] >= 0,
             'SCENARIO_USE_ITEM_EFFECT_TYPED_CLIENT_REQUIRED')
        rows = raw['rows']
        need(all(type(r) is dict and set(r) == {'rawkey_i32', 'value_u64'}
                 and type(r['rawkey_i32']) is int and -(1 << 31) <= r['rawkey_i32'] < (1 << 31)
                 and type(r['value_u64']) is int and 0 <= r['value_u64'] < (1 << 64) for r in rows)
             and len({r['rawkey_i32'] for r in rows}) == len(rows),
             'SCENARIO_USE_ITEM_EFFECT_CLIENT_ROWS_REQUIRED')
        found = [r['value_u64'] for r in rows if r['rawkey_i32'] == receipt['equipment_key_i32']]
        expected = [] if receipt['after_weapon_uid'] == 0 else [receipt['after_weapon_uid']]
        # A valid previous value may persist until the client's callback runs.
        # Only readonly observation repeats; the same original deadline applies.
        before = ([] if receipt.get('before_weapon_uid') == 0 else [receipt.get('before_weapon_uid')])
        if receipt.get('operation') == 'INITIAL_SYNC':
            before = [receipt['item_uid']] if not expected else []
        need(found == expected or found == before,
             'SCENARIO_USE_ITEM_EFFECT_CLIENT_TOGGLE_MISMATCH')
        return found == expected

    def _prepare_effect(self, row, broker):
        position, known, _session, _claim, identifier = self.use_authority(row, broker)
        runtime, writer = self._effect_current(broker)
        if self.use_effect_started is None:
            self.use_effect_started = self.clock()
            self.use_effect['status'] = 'PREPARING'
        need(self.clock() - self.use_effect_started < 15, 'SCENARIO_USE_ITEM_EFFECT_INITIAL_EXPIRED')
        receipt = runtime.item_equipment_initial
        if receipt is None:
            return False
        self.use_effect_initial = receipt
        self._effect_receipt(receipt, initial=True, position=position, identifier=identifier)
        need(broker.item_equipment_observation(writer) == receipt,
             'SCENARIO_USE_ITEM_EFFECT_INITIAL_RECEIPT_CHANGED')
        if runtime._equipment_sample_ordinal != 0 or runtime.equipment_observation is None:
            return False
        self.use_effect_initial_raw = runtime.equipment_observation
        if self._effect_unknown_raw_for_ui(self.use_effect_initial_raw, runtime, writer, broker, known):
            self.use_effect.update(proof_scope='AUTHORITATIVE_INITIAL_SYNC_DRAIN_ONLY', client_state='UNKNOWN')
        elif not self._effect_raw(self.use_effect_initial_raw, receipt, position):
            self.use_effect['client_state'] = 'WAITING_FIXED_KEY_VALUE'
            return False
        self.use_effect['status'] = 'READY'
        return True

    def _effect_unknown_raw_for_ui(self, raw, runtime, writer, broker, known):
        # UNKNOWN raw stays UNKNOWN. Only explicit UI mode may request an
        # independent fresh UI entry after current canonical authority checks.
        if not (self.use_item_ui_observe and type(raw) is dict and raw.get('status') == 'UNKNOWN'):
            return False
        need(known is True, 'SCENARIO_USE_ITEM_UI_CURRENT_SOURCE_REQUIRED')
        self.reader.validate()
        need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        actual, current_writer, _effect = runtime._equipment_binding(same_selection=True)
        need(actual is broker and current_writer is writer,
             'SCENARIO_USE_ITEM_UI_CURRENT_EFFECT_BINDING_REQUIRED')
        return True

    def _effect_partial_raws_for_ui(self, position, runtime, writer, broker, known):
        initial, current = self.use_effect_initial_raw, self.use_effect_final_raw
        unknown = next((raw for raw in (initial, current)
                        if type(raw) is dict and raw.get('status') == 'UNKNOWN'), None)
        if not self._effect_unknown_raw_for_ui(unknown, runtime, writer, broker, known):
            return False
        # The latest observation is the effect receipt. Revalidate the actual
        # original INITIAL_SYNC cache without preparing/sending it again.
        receipt = self.use_effect_initial
        self._effect_receipt(receipt, initial=True, position=position,
                             identifier=self.use_effect_final['item_uid'])
        generation, effect = runtime._equipment_generation, broker._item_equipment_effect
        life = effect._selection
        expected = (writer, generation, generation.game, generation.selected,
                    generation.service, generation.item_use_session, broker.realm._actor_fields)
        need(runtime.item_equipment_initial == receipt and type(life) is dict
             and life.get('synced') is True and life.get('sync_receipt') == receipt
             and type(life.get('identity')) is tuple and len(life['identity']) == len(expected)
             and all(a is b for a, b in zip(life['identity'], expected)),
             'SCENARIO_USE_ITEM_UI_INITIAL_SYNC_CHANGED')
        # OBSERVED sides retain their original format/source/UID/map/key guards.
        # A valid old value still does not make the combined evidence COMMITTED.
        for raw, source in ((initial, receipt), (current, self.use_effect_final)):
            if type(raw) is not dict or raw.get('status') != 'UNKNOWN':
                self._effect_raw(raw, source, position)
        return True

    def collect_use_effect(self, row, broker):
        position, known, session, _claim, identifier = self.use_authority(row, broker)
        runtime, writer = self._effect_current(broker)
        need(self.clock() - self.use_effect_started < 15, 'SCENARIO_USE_ITEM_EFFECT_OBSERVATION_EXPIRED')
        need(self.use_item['status'] == 'COMMITTED' and session.accepted_count == 1,
             'SCENARIO_USE_ITEM_EFFECT_INTENT_REQUIRED')
        receipt = runtime.item_equipment_current
        if receipt is None:
            return
        self.use_effect_final = receipt
        self._effect_receipt(receipt, initial=False, position=position, identifier=identifier)
        need(broker.item_equipment_observation(writer, accepted_ordinal=1) == receipt,
             'SCENARIO_USE_ITEM_EFFECT_CURRENT_RECEIPT_CHANGED')
        if runtime._equipment_sample_ordinal != 1 or runtime.equipment_observation is None:
            return
        self.use_effect_final_raw = runtime.equipment_observation
        if self._effect_partial_raws_for_ui(position, runtime, writer, broker, known):
            self.use_effect.update(status='PARTIAL', proof_scope='AUTHORITATIVE_TOGGLE_DRAIN_ONLY',
                                   client_state='UNKNOWN')
        else:
            if not self._effect_raw(self.use_effect_final_raw, receipt, position):
                self.use_effect['client_state'] = 'WAITING_FIXED_KEY_VALUE'
                return
            need(self.use_effect_final_raw['query_started_monotonic_ns']
                 > self.use_effect_initial_raw['query_started_monotonic_ns'],
                 'SCENARIO_USE_ITEM_EFFECT_FRESH_CLIENT_REQUIRED')
            self.use_effect.update(status='COMMITTED', proof_scope='AUTHORITATIVE_TOGGLE_DRAIN_TYPED_CLIENT_MATCH',
                                   client_state='FIXED_EQUIPMENT_KEY_VALUE_MATCHED')
        if self.use_item_ui_observe:
            self.use_ui.update(status='WAITING', expected_model_d4=receipt['after_weapon_uid'] == receipt['item_uid'])
            self.use_ui_started_ns = time.monotonic_ns()
            self.stage = 'USE_ITEM_UI_WAIT'
        else:
            self.stage = 'USE_ITEM_EFFECT_COMPLETE_STOP_REQUESTED'
            self.stop.set()

    def collect_use_item_ui(self, row, broker):
        # Only the public request/cache API participates in the existing poll slot.
        position, known, session, _claim, identifier = self.use_authority(row, broker)
        runtime, writer = self._effect_current(broker)
        need(self.clock() - self.use_effect_started < 15,
             'SCENARIO_USE_ITEM_UI_OBSERVATION_EXPIRED')
        need(self.use_effect['status'] in ('COMMITTED', 'PARTIAL') and self.use_item['status'] == 'COMMITTED'
             and session.accepted_count == 1,
             'SCENARIO_USE_ITEM_UI_EFFECT_REQUIRED')
        receipt = self.use_effect_final
        self._effect_receipt(receipt, initial=False, position=position, identifier=identifier)
        need(runtime.item_equipment_current == receipt
             and broker.item_equipment_observation(writer, accepted_ordinal=1) == receipt,
             'SCENARIO_USE_ITEM_UI_EFFECT_CHANGED')
        if self.use_effect['status'] == 'PARTIAL':
            need(self._effect_partial_raws_for_ui(position, runtime, writer, broker, known),
                 'SCENARIO_USE_ITEM_UI_PARTIAL_SOURCE_REQUIRED')
        else:
            need(self._effect_raw(self.use_effect_final_raw, receipt, position),
                 'SCENARIO_USE_ITEM_UI_TYPED_EFFECT_REQUIRED')
        request = getattr(runtime, 'request_item_equipment_ui_observation', None)
        need(callable(request), 'SCENARIO_USE_ITEM_UI_API_UNSUPPORTED')
        if not self.use_ui_queued:
            queued = request()
            self.use_ui_observation = getattr(runtime, 'equipment_ui_observation', None)
            need(type(queued) is bool, 'SCENARIO_USE_ITEM_UI_ADMISSION_BOOL_REQUIRED')
            if not queued:
                value = self.use_ui_observation
                status = value.get('status') if type(value) is dict else 'UNKNOWN'
                reason = value.get('reason') if type(value) is dict else None
                self.use_ui.update(status=status if status in ('UNKNOWN', 'REFUSED', 'CODE_ANCHOR_BLOCKED')
                                   else 'UNKNOWN', reason=reason or 'SCENARIO_USE_ITEM_UI_REQUEST_REFUSED')
                need(False, launcher.safe_error_code(ValueError(reason))
                     or 'SCENARIO_USE_ITEM_UI_REQUEST_REFUSED')
            self.use_ui_queued = True
        value = getattr(runtime, 'equipment_ui_observation', None)
        self.use_ui_observation = value
        fields = {'status', 'reason', 'invoked', 'observed', 'model_uid', 'model_d4',
                  'native_sequence', 'source_pid', 'source_birth', 'source_image_sha256',
                  'player_uid', 'item_identifier', 'map_id', 'query_started_monotonic_ns', 'cleanup_required'}
        need(type(value) is dict and set(value) == fields,
             'SCENARIO_USE_ITEM_UI_PRIMITIVE_SCHEMA_REQUIRED')
        status, reason = value['status'], value['reason']
        if status == 'UNKNOWN' and reason in ('NOT_SAMPLED', 'UI_OBSERVE_REQUESTED', 'UI_OBSERVE_PENDING'):
            need(all(value[k] is False for k in ('invoked', 'observed', 'cleanup_required'))
                 and all(value[k] is None for k in fields - {'status', 'reason', 'invoked', 'observed', 'cleanup_required'}),
                 'SCENARIO_USE_ITEM_UI_PENDING_PRIMITIVES_REQUIRED')
            self.use_ui.update(status='WAITING', reason=reason)
            return
        if status in ('UNKNOWN', 'REFUSED', 'CODE_ANCHOR_BLOCKED'):
            self.use_ui.update(status=status, reason=reason)
            need(False, launcher.safe_error_code(ValueError(reason)) or 'SCENARIO_USE_ITEM_UI_TERMINAL')
        need(status == 'OBSERVED' and type(reason) is int and reason == 0
             and value['invoked'] is False and value['observed'] is True and value['cleanup_required'] is False
             and type(value['model_uid']) is int and value['model_uid'] == identifier
             and type(value['model_d4']) is bool,
             'SCENARIO_USE_ITEM_UI_MODEL_PRIMITIVES_REQUIRED')
        need(type(value['source_pid']) is int and value['source_pid'] == self.owner.child.pid
             and type(value['source_birth']) is int and value['source_birth'] == int(self.owner.child.identity['birth'])
             and value['source_image_sha256'] == self.owner.image_sha
             and type(value['player_uid']) is int and value['player_uid'] == position.uid
             and type(value['item_identifier']) is int and value['item_identifier'] == identifier
             and type(value['map_id']) is int and value['map_id'] == position.map_id,
             'SCENARIO_USE_ITEM_UI_CURRENT_IDENTITY_REQUIRED')
        query, sequence = value['query_started_monotonic_ns'], value['native_sequence']
        need(type(query) is int and self.use_ui_started_ns <= query <= time.monotonic_ns()
             and (query > self.use_effect_final_raw['query_started_monotonic_ns']
                  if type(self.use_effect_final_raw.get('query_started_monotonic_ns')) is int
                  else self.use_effect['status'] == 'PARTIAL')
             and (self.use_ui_last_query_ns is None or query > self.use_ui_last_query_ns)
             and type(sequence) is int and 0 < sequence < (1 << 31)
             and (self.use_ui_last_native_sequence is None or sequence > self.use_ui_last_native_sequence),
             'SCENARIO_USE_ITEM_UI_FRESH_QUERY_REQUIRED')
        # Native queue sequence and public UseItem sequence are different domains.
        self.use_ui_last_query_ns, self.use_ui_last_native_sequence = query, sequence
        self.use_ui.update(model_uid=value['model_uid'], model_d4=value['model_d4'], reason=reason)
        expected = receipt['after_weapon_uid'] == identifier
        if value['model_d4'] is not expected:
            need(value['model_d4'] is (receipt['before_weapon_uid'] == identifier),
                 'SCENARIO_USE_ITEM_UI_MODEL_TOGGLE_MISMATCH')
            self.use_ui.update(status='WAITING', reason='WAITING_MODEL_D4')
            self.use_ui_queued = False  # A valid old model permits one fresh readonly request.
            return
        self.use_ui.update(status='OBSERVED', proof_scope='CURRENT_SLOT_MODEL_UID_D4_MATCHED')
        self.stage = 'USE_ITEM_UI_COMPLETE_STOP_REQUESTED'
        self.stop.set()

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
        need(selected is self.auto_inventory_binding
             and frame is self.auto_inventory_frame and type(selected) is tuple and len(selected) == 11
             and selected[0] is writer and type(frame) is bytes,
             'SCENARIO_USE_ITEM_RESTORED_SELECTION_CHANGED')
        self._auto_inventory_restore_mode(broker, writer, selected, frame)
        PersistentBroker._inventory_selection_frame_current(broker, writer, selected[1], frame)
        item = inventory.validate_frame(frame)  # Actual selected literal; first grant is source-config-bound.
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
        if self.use_item_effect and not self._prepare_effect(row, broker):
            return
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
                    if self.use_item_effect:
                        self.use_effect.update(status='WAITING', accepted_ordinal=1)
                        self.use_effect_started = self.clock()
                        self.stage = 'USE_EFFECT_WAIT'
                    elif self.use_item_only:
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
        if self.stage not in ('USE_READY', 'USE_WAIT', 'USE_EFFECT_WAIT', 'USE_ITEM_UI_WAIT') or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            fresh = self.monitor.samples != self.last_sample
            self.last_sample = self.monitor.samples
            if self.stage == 'USE_READY' and (fresh or self.use_item_effect):
                self.submit_use_item(row, broker)
            elif self.stage == 'USE_WAIT':
                self.collect_use_item(row, broker)
            elif self.stage == 'USE_EFFECT_WAIT':
                self.collect_use_effect(row, broker)
            elif self.stage == 'USE_ITEM_UI_WAIT':
                self.collect_use_item_ui(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            if self.use_item_ui_observe and self.stage == 'USE_ITEM_UI_WAIT':
                if self.use_ui['status'] not in ('UNKNOWN', 'REFUSED', 'CODE_ANCHOR_BLOCKED'):
                    self.use_ui.update(status='UNKNOWN', reason=self.error)
                self.stage = 'USE_ITEM_UI_UNKNOWN_STOP_REQUESTED'
            elif self.use_item_effect:
                self.use_effect.update(status='UNKNOWN', reason=self.error)
                self.stage = 'USE_ITEM_EFFECT_UNKNOWN_STOP_REQUESTED'
            else:
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

    def _update_initial_authority(self, service, position):
        need(self.inventory['status'] == self.attack['status'] == 'COMMITTED' and not self.moves
             and position.metadata() == (self.move_origin or self.origin)
             and (service.requests_received, service.committed, service.corrections_prepared) == self.move_counter_base,
             'SCENARIO_INVENTORY_UPDATE_INITIAL_AUTHORITY_REQUIRED')

    def update_wire_expected(self, old_fields, quantity):
        return {1: old_fields[1], 4: quantity, 18: old_fields[18]}

    def update_current(self, row, broker, *, strict=False):
        from tools.local_original_session import inventory
        from tools.local_original_session.inventory_store import InventoryStore
        from tools.local_original_session.broker import PersistentBroker, INVENTORY_UPDATE_POLICY
        service, position, _proof, known = (ContinuousMoveScenario.current(self, row, broker)
            if strict else self.current(row, broker))
        need(type(broker) is PersistentBroker and broker.inventory_update_policy == self.features.inventory_update_policy
             == INVENTORY_UPDATE_POLICY and broker.policy.inventory_update is True,
             'SCENARIO_INVENTORY_UPDATE_REAL_POLICY_REQUIRED')
        self._update_initial_authority(service, position)
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
                         and wire_fields == self.update_wire_expected(old_fields, expected[4])
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


class InventoryUIFrameUpdateScenario(InventoryUpdateScenario):
    """Two actual readonly UI samples separated by one canonical update; no Use."""
    source_quit_profile = 'sibling-background-item-equipment-ui-update-spawn'
    UPDATE_SEQUENCE = 2

    @staticmethod
    def configuration(config, *, inventory=False, auto_inventory=False):
        from tools.local_original_session import feature_config, inventory as inv, inventory_store
        from tools.local_original_session.broker import INVENTORY_UPDATE_POLICY
        from tools.local_original_session.restart import POLICY as RESTART_POLICY
        need(type(config) is feature_config.Features and inventory and auto_inventory
             and not config.spawns and config.attack_policy is config.attack_feedback is None
             and config.interval_ns is config.motion_policy is config.goal_policy is config.goal is None
             and config.item_use_policy is config.item_equipment_policy is None
             and config.restart_policy == RESTART_POLICY
             and config.item_equipment_first_enable is False and config.inventory_missing_row_policy is None
             and config.inventory_policy == inv.POLICY and type(config.inventory_frame) is bytes
             and config.inventory_store_policy == inventory_store.POLICY
             and config.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
             and config.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
             and config.inventory_update_policy == INVENTORY_UPDATE_POLICY,
             'SCENARIO_UI_UPDATE_SAVED_ROW_ONLY_CONFIGURATION_REQUIRED')
        inv.validate_frame(config.inventory_frame)
        return config

    def __init__(self, *args, **kwargs):
        self.ui_runtime = self.ui_generation = None
        self.ui_initial = self.ui_final = None
        self.ui_started = self.ui_started_ns = None
        self.ui_queued = False
        self.ui_frame_update = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN',
                                    model_d4_before=None, model_d4_after=None)
        super().__init__(*args, **kwargs)
        need(self.features.item_use_policy is None and self.features.item_equipment_policy is None,
             'SCENARIO_UI_UPDATE_NO_USE_EFFECT_POLICY_REQUIRED')
        self.path = self.monitor.directory / 'manual-ui-frame-update-scenario.json'

    def bind_runtime(self, runtime):
        need(type(runtime) is launcher.ProductFeatures and self.ui_runtime is None
             and runtime.equipment_ui_observer is not None and runtime.equipment_observer is None
             and runtime.manual.allow_inventory_update is True and runtime.manual.allow_use_item is False,
             'SCENARIO_UI_UPDATE_ACTUAL_RUNTIME_REQUIRED')
        self.ui_runtime = runtime

    def summary(self):
        row = super().summary()
        row['verification_scope'] = 'SAVED_ROW_READONLY_UI_CANONICAL_UPDATE_FRESH_UI_QUIT'
        row['ui_frame_update'] = dict(self.ui_frame_update,
            observation_file='manual-ui-frame-update-observation.json')
        return row

    def save(self):
        _atomic(self.monitor.directory / 'manual-ui-frame-update-observation.json',
            dict(schema='manual-ui-frame-update-observation-v1', result=self.ui_frame_update,
                 initial=self.ui_initial, current=self.ui_final), 4096, output_only=True)
        return super().save()

    def _update_initial_authority(self, service, position):
        need(self.inventory['status'] == 'COMMITTED' and self.attack['status'] == 'NOT_REQUESTED'
             and not self.moves and self.hold_complete is False
             and position.metadata() == self.origin and self.move_counter_base == (0, 0, 0)
             and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0),
             'SCENARIO_UI_UPDATE_NO_ACTION_AUTHORITY_REQUIRED')

    def update_wire_expected(self, old_fields, quantity):
        return {1: old_fields[1], 4: quantity}  # Current canonical sparse producer; no f18 carry.

    def submit_inventory_update(self, row, broker):
        position, identifier, runtime = self._ui_context(row, broker)
        value = self.ui_initial
        need(self.stage == 'UPDATE_READY' and self.ui_frame_update['status'] == 'INITIAL_OBSERVED'
             and type(value) is dict and value.get('status') == 'OBSERVED' and value.get('observed') is True
             and value.get('model_uid') == identifier and value.get('player_uid') == position.uid
             and value.get('map_id') == position.map_id
             and runtime.equipment_ui_observer.observation() == value,
             'SCENARIO_UI_UPDATE_FIRST_REAL_OBSERVATION_REQUIRED')
        return super().submit_inventory_update(row, broker)

    def collect_inventory(self, row, broker):
        InventoryAutoScenario.collect_inventory(self, row, broker)
        if self.stage == 'ATTACK_READY':
            self._begin_ui_stage('UI_INITIAL_WAIT')

    def _begin_ui_stage(self, stage):
        self.stage = stage
        self.ui_started, self.ui_started_ns = self.clock(), time.monotonic_ns()
        self.ui_queued = False  # Exactly one explicit request in each stage.

    def _ui_context(self, row, broker):
        from tools.local_original_session import inventory
        from tools.local_original_session.broker import PersistentBroker
        position, known, _refs, _claim = self.update_current(row, broker)
        need(known, 'SCENARIO_UI_UPDATE_CURRENT_WORLD_REQUIRED')
        self.reader.validate()
        need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        runtime = self.ui_runtime
        need(type(runtime) is launcher.ProductFeatures and not runtime._closed
             and runtime.manual.inventory_broker is broker
             and runtime.manual.consumer.reader is self.reader,
             'SCENARIO_UI_UPDATE_RUNTIME_CHANGED')
        generation = PersistentBroker.inventory_selection_current(broker, self.move_bound[0])
        need(generation is not None and generation.phase == 'ACTIVE'
             and generation.selection_binding is self.auto_inventory_binding
             and generation.current_frame is broker._inventory_current_frame,
             'SCENARIO_UI_UPDATE_CURRENT_GENERATION_REQUIRED')
        if self.ui_generation is None:
            self.ui_generation = generation
        need(generation is self.ui_generation, 'SCENARIO_UI_UPDATE_GENERATION_CHANGED')
        frame = broker._inventory_current_frame
        if self.stage == 'UI_FINAL_WAIT':
            op = self.update_operation
            need(type(op) is dict and op is broker._inventory_update_operation and op['phase'] == 'DRAINED'
                 and all(op[k] is True for k in ('persisted', 'write_attempted', 'drain_returned', 'post_owner_verified'))
                 and frame is op['new'] and frame is not self.update_old
                 and self.inventory_update['status'] == 'COMMITTED',
                 'SCENARIO_UI_UPDATE_NEW_DRAINED_FRAME_REQUIRED')
        else:
            need(frame is self.auto_inventory_frame, 'SCENARIO_UI_UPDATE_INITIAL_FRAME_CHANGED')
        return position, inventory.validate_frame(frame).identifier, runtime

    def collect_ui_frame(self, row, broker):
        need(self.clock() - self.ui_started < 15, 'SCENARIO_UI_UPDATE_OBSERVATION_EXPIRED')
        position, identifier, runtime = self._ui_context(row, broker)
        queued = True
        if not self.ui_queued:
            # Publication only; ProductFeatures.poll owns the existing serial 2Hz slot.
            queued = runtime.request_item_equipment_ui_observation()
        value = dict(runtime.equipment_ui_observation)
        if self.stage == 'UI_INITIAL_WAIT':
            self.ui_initial = value
        else:
            self.ui_final = value
        need(queued is True, 'SCENARIO_UI_UPDATE_REQUEST_REFUSED')
        self.ui_queued = True
        fields = {'status', 'reason', 'invoked', 'observed', 'model_uid', 'model_d4',
                  'native_sequence', 'source_pid', 'source_birth', 'source_image_sha256',
                  'player_uid', 'item_identifier', 'map_id', 'query_started_monotonic_ns', 'cleanup_required'}
        need(set(value) == fields, 'SCENARIO_UI_UPDATE_PRIMITIVE_SCHEMA_REQUIRED')
        if value['status'] == 'UNKNOWN' and value['reason'] in ('NOT_SAMPLED', 'UI_OBSERVE_REQUESTED', 'UI_OBSERVE_PENDING'):
            need(all(value[k] is False for k in ('invoked', 'observed', 'cleanup_required'))
                 and all(value[k] is None for k in fields - {'status', 'reason', 'invoked', 'observed', 'cleanup_required'}),
                 'SCENARIO_UI_UPDATE_PENDING_NULL_REQUIRED')
            return
        need(value['status'] == 'OBSERVED' and type(value['reason']) is int and value['reason'] == 0
             and value['invoked'] is False and value['observed'] is True and value['cleanup_required'] is False
             and type(value['model_uid']) is int and value['model_uid'] == identifier
             and type(value['model_d4']) is bool,
             'SCENARIO_UI_UPDATE_OBSERVATION_REQUIRED')
        need(type(value['source_pid']) is int and value['source_pid'] == self.owner.child.pid
             and type(value['source_birth']) is int and value['source_birth'] == int(self.owner.child.identity['birth'])
             and value['source_image_sha256'] == self.owner.image_sha
             and type(value['player_uid']) is int and value['player_uid'] == position.uid
             and type(value['item_identifier']) is int and value['item_identifier'] == identifier
             and type(value['map_id']) is int and value['map_id'] == position.map_id,
             'SCENARIO_UI_UPDATE_SOURCE_IDENTITY_REQUIRED')
        query, seq = value['query_started_monotonic_ns'], value['native_sequence']
        need(type(query) is int and self.ui_started_ns <= query <= time.monotonic_ns()
             and type(seq) is int and 0 < seq < (1 << 31), 'SCENARIO_UI_UPDATE_FRESH_SAMPLE_REQUIRED')
        if self.stage == 'UI_INITIAL_WAIT':
            self.ui_frame_update.update(status='INITIAL_OBSERVED', model_d4_before=value['model_d4'])
            self.stage = 'UPDATE_READY'
        else:
            need(query > self.ui_initial['query_started_monotonic_ns']
                 and seq > self.ui_initial['native_sequence'], 'SCENARIO_UI_UPDATE_NEW_SEQUENCE_REQUIRED')
            self.ui_frame_update.update(status='OBSERVED', model_d4_after=value['model_d4'],
                                        proof_scope='SAME_UID_NEW_FRAME_FRESH_UI_PRIMITIVES')
            self.stage = 'UI_FRAME_UPDATE_COMPLETE_STOP_REQUESTED'
            self.stop.set()  # Only the existing source Quit cleanup follows.

    def tick(self, row, broker, state):
        if self.stage not in ('UI_INITIAL_WAIT', 'UPDATE_READY', 'UPDATE_WAIT', 'UI_FINAL_WAIT') or state == 'CLOSING':
            return InventoryAutoScenario.tick(self, row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate()
            self.background_desktop()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            if self.stage in ('UI_INITIAL_WAIT', 'UI_FINAL_WAIT'):
                self.collect_ui_frame(row, broker)
            elif self.stage == 'UPDATE_READY':
                self.submit_inventory_update(row, broker)
            else:
                self.collect_inventory_update(row, broker)
                if self.stage == 'MOVE_READY':
                    self._begin_ui_stage('UI_FINAL_WAIT')
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.ui_frame_update.update(status='UNKNOWN', reason=self.error)
            self.stage = 'UI_FRAME_UPDATE_UNKNOWN_STOP_REQUESTED'
            self.save(); self.stop.set()



class InventoryUIOpenScenario(InventoryAutoScenario):
    """Saved delivery, one explicit normal Open, fresh readonly UID/D4, Quit."""
    source_quit_profile = INVENTORY_UI_OPEN_PROFILE

    @staticmethod
    def configuration(config, *, inventory=False, auto_inventory=False):
        from tools.local_original_session import feature_config, inventory as inv, inventory_store
        from tools.local_original_session.restart import POLICY as RESTART_POLICY
        need(type(config) is feature_config.Features and inventory and auto_inventory
             and not config.spawns and config.attack_policy is config.attack_feedback is None
             and config.interval_ns is config.motion_policy is config.goal_policy is config.goal is None
             and config.item_use_policy is config.item_equipment_policy is config.inventory_update_policy is None
             and config.restart_policy == RESTART_POLICY and config.item_equipment_first_enable is False
             and config.inventory_missing_row_policy is None and config.inventory_policy == inv.POLICY
             and type(config.inventory_frame) is bytes and config.inventory_store_policy == inventory_store.POLICY
             and config.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
             and config.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION,
             'SCENARIO_INVENTORY_OPEN_SAVED_ONLY_CONFIGURATION_REQUIRED')
        inv.validate_frame(config.inventory_frame)
        return config

    def __init__(self, *args, **kwargs):
        self.open_runtime = self.open_generation = None
        self.open_started = self.open_started_ns = self.ui_started = self.ui_started_ns = None
        self.open_queued = self.ui_queued = False
        self.open_observation = self.ui_observation = None
        self.inventory_ui_open = dict(status='NOT_REQUESTED', proof_scope='UNKNOWN', model_uid=None, model_d4=None)
        super().__init__(*args, **kwargs)
        need(kwargs.get('source_quit_test') is True and kwargs.get('retain_move_goal', False) is False,
             'SCENARIO_INVENTORY_OPEN_SOURCE_QUIT_NO_ACTION_REQUIRED')
        self.path = self.monitor.directory / 'manual-inventory-ui-open-scenario.json'

    def bind_runtime(self, runtime):
        need(type(runtime) is launcher.ProductFeatures and self.open_runtime is None
             and runtime.inventory_ui_opener is not None and runtime.equipment_ui_observer is not None
             and runtime.equipment_observer is None and runtime.manual.allow_use_item is False
             and runtime.manual.allow_inventory_update is False,
             'SCENARIO_INVENTORY_OPEN_ACTUAL_RUNTIME_REQUIRED')
        self.open_runtime = runtime

    def summary(self):
        row = super().summary()
        row.pop('last_consumer_result')
        row['inventory_ui_open'] = dict(self.inventory_ui_open,
            observation_file='manual-inventory-ui-open-observation.json')
        row['verification_scope'] = 'SAVED_ROW_ONE_NORMAL_OPEN_FRESH_UI_PRIMITIVE_QUIT'
        return row

    def save(self):
        _atomic(self.monitor.directory / 'manual-inventory-ui-open-observation.json',
            dict(schema='manual-inventory-ui-open-observation-v1', result=self.inventory_ui_open,
                 open=self.open_observation, ui=self.ui_observation), 4096, output_only=True)
        return super().save()

    def collect_inventory(self, row, broker):
        super().collect_inventory(row, broker)
        if self.stage == 'ATTACK_READY':
            self.open_started, self.open_started_ns = self.clock(), time.monotonic_ns()
            self.stage = 'INVENTORY_UI_OPEN_WAIT'

    def open_current(self, row, broker):
        from tools.local_original_session import inventory
        from tools.local_original_session.broker import PersistentBroker
        position, known = self.inventory_authority(row, broker)
        need(known and self.inventory['status'] == 'COMMITTED' and self.attack['status'] == 'NOT_REQUESTED'
             and not self.moves and self.hold_complete is False,
             'SCENARIO_INVENTORY_OPEN_CURRENT_NO_ACTION_REQUIRED')
        self.reader.validate()
        need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        generation = PersistentBroker.inventory_selection_current(broker, self.move_bound[0])
        if self.open_generation is None:
            self.open_generation = generation
        need(generation is not None and generation is self.open_generation and generation.phase == 'ACTIVE'
             and generation.current_frame is broker._inventory_current_frame is self.auto_inventory_frame
             and generation.selection_binding is self.auto_inventory_binding,
             'SCENARIO_INVENTORY_OPEN_CURRENT_GENERATION_REQUIRED')
        runtime = self.open_runtime
        need(type(runtime) is launcher.ProductFeatures and not runtime._closed
             and runtime.manual.inventory_broker is broker and runtime.manual.consumer.reader is self.reader,
             'SCENARIO_INVENTORY_OPEN_RUNTIME_CHANGED')
        return position, inventory.validate_frame(generation.current_frame).identifier, runtime

    def collect_open(self, row, broker):
        need(self.clock() - self.open_started < 15, 'SCENARIO_INVENTORY_OPEN_EXPIRED')
        position, identifier, runtime = self.open_current(row, broker)
        queued = True
        if not self.open_queued:
            queued = runtime.request_inventory_ui_open()
        value = self.open_observation = dict(runtime.inventory_ui_open_observation)
        need(queued is True, 'SCENARIO_INVENTORY_OPEN_REQUEST_REFUSED')
        self.open_queued = True
        if value['status'] == 'UNKNOWN' and value['reason'] in ('NOT_SAMPLED', 'INVENTORY_UI_OPEN_REQUESTED', 'INVENTORY_UI_OPEN_PENDING'):
            need(all(value[k] is None for k in ('opened', 'before_own_visible', 'after_own_visible', 'native_sequence')),
                 'SCENARIO_INVENTORY_OPEN_PENDING_NULL_REQUIRED')
            return
        need(value['status'] == 'RETURNED' and type(value['reason']) is int and value['reason'] == 0
             and value['invoked'] is True and value['opened'] is True
             and value['before_own_visible'] is False and value['after_own_visible'] is True
             and value['cleanup_required'] is False,
             'SCENARIO_INVENTORY_OPEN_RETURN_REQUIRED')
        self._source(value, position, identifier, self.open_started_ns)
        self.inventory_ui_open.update(status='OPEN_RETURNED', proof_scope='ORIGINAL_NORMAL_OPEN_OWN_VISIBILITY')
        self.ui_started, self.ui_started_ns = self.clock(), time.monotonic_ns()
        self.stage = 'INVENTORY_UI_OPEN_OBSERVE_WAIT'

    def _source(self, value, position, identifier, started):
        need(type(value['source_pid']) is int and value['source_pid'] == self.owner.child.pid
             and type(value['source_birth']) is int and value['source_birth'] == int(self.owner.child.identity['birth'])
             and value['source_image_sha256'] == self.owner.image_sha
             and type(value['player_uid']) is int and value['player_uid'] == position.uid
             and type(value['item_identifier']) is int and value['item_identifier'] == identifier
             and type(value['map_id']) is int and value['map_id'] == position.map_id
             and type(value['native_sequence']) is int and 0 < value['native_sequence'] < (1 << 31)
             and type(value['query_started_monotonic_ns']) is int
             and started <= value['query_started_monotonic_ns'] <= time.monotonic_ns(),
             'SCENARIO_INVENTORY_OPEN_FRESH_SOURCE_REQUIRED')

    def collect_open_ui(self, row, broker):
        need(self.clock() - self.ui_started < 15, 'SCENARIO_INVENTORY_OPEN_UI_EXPIRED')
        position, identifier, runtime = self.open_current(row, broker)
        queued = True
        if not self.ui_queued:
            queued = runtime.request_item_equipment_ui_observation()
        value = self.ui_observation = dict(runtime.equipment_ui_observation)
        need(queued is True, 'SCENARIO_INVENTORY_OPEN_UI_REQUEST_REFUSED')
        self.ui_queued = True
        fields = {'status', 'reason', 'invoked', 'observed', 'model_uid', 'model_d4',
                  'native_sequence', 'source_pid', 'source_birth', 'source_image_sha256',
                  'player_uid', 'item_identifier', 'map_id', 'query_started_monotonic_ns', 'cleanup_required'}
        need(set(value) == fields, 'SCENARIO_INVENTORY_OPEN_UI_SCHEMA_REQUIRED')
        if value['status'] == 'UNKNOWN' and value['reason'] in ('NOT_SAMPLED', 'UI_OBSERVE_REQUESTED', 'UI_OBSERVE_PENDING'):
            need(all(value[k] is None for k in ('model_uid', 'model_d4', 'native_sequence')),
                 'SCENARIO_INVENTORY_OPEN_UI_PENDING_NULL_REQUIRED')
            return
        need(value['status'] == 'OBSERVED' and type(value['reason']) is int and value['reason'] == 0
             and value['invoked'] is False and value['observed'] is True and value['cleanup_required'] is False
             and type(value['model_uid']) is int and value['model_uid'] == identifier and type(value['model_d4']) is bool,
             'SCENARIO_INVENTORY_OPEN_UI_OBSERVED_REQUIRED')
        self._source(value, position, identifier, self.ui_started_ns)
        need(value['native_sequence'] > self.open_observation['native_sequence']
             and value['query_started_monotonic_ns'] > self.open_observation['query_started_monotonic_ns'],
             'SCENARIO_INVENTORY_OPEN_POSTCALL_FRESH_REQUIRED')
        self.inventory_ui_open.update(status='OBSERVED', proof_scope='NORMAL_OPEN_THEN_FRESH_SLOT_MODEL_UID_D4',
                                      model_uid=value['model_uid'], model_d4=value['model_d4'])
        self.stage = 'INVENTORY_UI_OPEN_COMPLETE_STOP_REQUESTED'
        self.stop.set()

    def tick(self, row, broker, state):
        if self.stage not in ('INVENTORY_UI_OPEN_WAIT', 'INVENTORY_UI_OPEN_OBSERVE_WAIT') or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.reader.validate();self.background_desktop()
            if self.stage == 'INVENTORY_UI_OPEN_WAIT':self.collect_open(row, broker)
            else:self.collect_open_ui(row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.inventory_ui_open.update(status='UNKNOWN', reason=self.error)
            self.stage = 'INVENTORY_UI_OPEN_UNKNOWN_STOP_REQUESTED'
            self.save();self.stop.set()



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
        if getattr(self, 'collection_swap', False):
            prepared = (type(self) is SourceReselectScenario and self.inventory_only is True
                and manual is not None and (self.collection_swap_flow.zero_restart_prepared(row, broker, manual, position)
                    if self.collection_swap_zero_use else self.collection_swap_flow.restart_prepared(manual, position))
                and self.inventory['status'] == 'COMMITTED' and self.attack['status'] == 'NOT_REQUESTED'
                and not self.moves and self.hold_complete is False and position.metadata() == self.origin
                and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0))
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
                     and result.get('last_sequence') == self.RESTART_SEQUENCE
                     and counts[0] in (0, 1) and counts[1:] == [1, 1]
                     and type(state) is dict and state['phase'] == 'DRAINED'
                     and all(state[key] is True for key in ('write_attempted', 'drain_returned', 'response_drained', 'selection_cleared'))
                     and restart.validate_ack(state['frame'], policy=broker.restart_policy) is True
                     and all(a is b for a, b in zip(state['binding'][0][6:11], (realm, game, service, position, selected)))
                     and type(settings.committed) is int and settings.failed is False and type(settings.last) is dict
                     and settings.committed == self.source_restart['settings_before'] + counts[0]
                     and game.selection is None and selected.reference not in registry.selected
                     and all(id(writer) not in mapping for mapping in (realm._movement, realm._world_frames,
                         realm._npc_frames, realm._npc_motion)), 'SCENARIO_SOURCE_RESTART_ACK_DRAIN_PROOF_REQUIRED')
                self.source_restart.update(status='COMMITTED', proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY',
                    settings_commit=settings.committed - self.source_restart['settings_before'],
                    cs4e33=1, sc4e3b_drained=1, selection_cleared=True,
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

    def __init__(self, *args, inventory_only=False, equipment_restore=False, collection_swap=False, collection_swap_saved_b_tail=False, collection_swap_zero_use=False, **kwargs):
        from tools.local_original_session.item_equipment_reselect_restore import RestoredEquipmentUI
        need(type(equipment_restore) is bool and (not equipment_restore or inventory_only is True),
             'SCENARIO_RESELECT_EQUIPMENT_FOCUSED_REQUIRED')
        need(type(collection_swap) is bool and (not collection_swap or inventory_only is True and equipment_restore is False),
             'SCENARIO_SWAP_EXCLUSIVE_FOCUSED_REQUIRED')
        need(type(collection_swap_saved_b_tail) is bool
             and (not collection_swap_saved_b_tail or collection_swap is True),
             'SCENARIO_SWAP_SAVED_B_TAIL_EXPLICIT_MODE_REQUIRED')
        need(type(collection_swap_zero_use) is bool
             and (not collection_swap_zero_use or collection_swap is True and collection_swap_saved_b_tail is False),
             'SCENARIO_ZERO_USE_RESELECT_EXPLICIT_MODE_REQUIRED')
        from tools.local_original_session.item_equipment_swap import CollectionSwap
        self.collection_swap_zero_use = collection_swap_zero_use
        self.collection_swap = collection_swap
        self.collection_swap_saved_b_tail = collection_swap_saved_b_tail
        self.collection_swap_flow = CollectionSwap(self, saved_b_tail=collection_swap_saved_b_tail, zero_use_tail=collection_swap_zero_use) if collection_swap else None
        self.equipment_restore = equipment_restore
        self.equipment_restore_flow = RestoredEquipmentUI(self) if equipment_restore else None
        self.reselect_started_ns = None
        if collection_swap:
            self.source_quit_profile = self.background_profile = (ZERO_USE_RESELECT_PROFILE if collection_swap_zero_use
                else CURRENT_ENTRY_TAIL_PROFILE if collection_swap_saved_b_tail else SWAP_PROFILE)
        if equipment_restore:
            self.source_quit_profile = self.background_profile = RESELECT_EQUIPMENT_PROFILE
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

    def configuration(self, config, **options):
        if self.collection_swap:
            from tools.local_original_session.item_equipment_swap import configuration
            return configuration(config, **options)
        if self.equipment_restore:
            from tools.local_original_session.item_equipment_reselect_restore import configuration
            return configuration(config, **options)
        return attack_configuration(config, **options)

    _restore_receipt = UseItemScenario._effect_receipt
    _restore_raw = UseItemScenario._effect_raw
    _restore_source = InventoryUIOpenScenario._source

    def bind_runtime(self, runtime):
        super().bind_runtime(runtime)
        if self.collection_swap:
            need(runtime.manual.consumer.use_item_current_entry is self.collection_swap_saved_b_tail
                 and runtime.manual.allow_use_item is (not self.collection_swap_zero_use)
                 and runtime.manual.consumer.allow_use_item is (not self.collection_swap_zero_use)
                 and runtime.manual.consumer.use_item_already_open is (not self.collection_swap_saved_b_tail and not self.collection_swap_zero_use)
                 and runtime.manual.consumer.use_item_entry_policy is None,
                 'SCENARIO_SWAP_SAVED_B_TAIL_CONSUMER_POLICY_CHANGED')
        if self.collection_swap_flow is not None:
            self.collection_swap_flow.bind(runtime)
        if self.equipment_restore_flow is not None:
            self.equipment_restore_flow.bind(runtime)
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
        if self.collection_swap_flow is not None:
            row['item_equipment_swap'] = dict(self.collection_swap_flow.result,
                observation_file='manual-item-equipment-swap-observation.json')
            row['verification_scope'] = ('SAVED_B_ZERO_USE_RESELECT_TWO_ROWS_RESTORE_FRESH_UI'
                if self.collection_swap_zero_use else 'SAVED_B_TWO_ORIGINAL_USES_UNEQUIP_EQUIP_RESELECT_TWO_ROWS_RESTORE_FRESH_UI'
                if self.collection_swap_saved_b_tail else
                'ORIGINAL_USE_B_SWAP_UNEQUIP_EQUIP_RESELECT_TWO_ROWS_RESTORE_FRESH_UI')
        if self.equipment_restore_flow is not None:
            row['reselect_equipment_restore'] = dict(self.equipment_restore_flow.result,
                observation_file='manual-reselect-equipment-ui-observation.json')
            row['verification_scope'] = 'SAME_PROCESS_RESELECT_NEW_LIFE_SAVED_EQUIPMENT_RAW_OPEN_FRESH_UID_D4'
        return row

    def inventory_authority(self, row, broker):
        if self.collection_swap_flow is not None:
            return self.collection_swap_flow.inventory_authority(row, broker)
        return super().inventory_authority(row, broker)

    def submit_inventory(self, row, broker):
        if self.collection_swap_flow is not None:
            self.collection_swap_flow.inventory_started_ns = time.monotonic_ns()
        return super().submit_inventory(row, broker)

    def collect_inventory(self, row, broker):
        if self.collection_swap_flow is not None:
            return self.collection_swap_flow.collect_inventory(row, broker)
        super().collect_inventory(row, broker)
        if self.inventory_only and self.stage == 'ATTACK_READY':
            self.stage = 'RESTART_READY'

    def save(self):
        # Output only. Neither these records nor their scalars authorize action.
        if self.collection_swap_flow is not None:
            _atomic(self.monitor.directory / 'manual-item-equipment-swap-observation.json',
                self.collection_swap_flow.detail(), 32768, output_only=True)
        if self.equipment_restore_flow is not None:
            _atomic(self.monitor.directory / 'manual-reselect-equipment-ui-observation.json',
                self.equipment_restore_flow.detail(), 32768, output_only=True)
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
        if self.equipment_restore or self.collection_swap:
            self.reselect_started_ns = time.monotonic_ns()
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
                     and result.get('proof_scope') == ('CLIENT_SAVED_ITEM_ROWS_SCALARS_AFTER_RESELECT' if self.collection_swap else 'CLIENT_SAVED_ITEM_ROW_SCALARS_AFTER_RESELECT')
                     and result.get('selection_proof_scope') == 'LOCAL_RESELECT_LAND_READY_ONLY'
                     and result.get('client_inventory') == result.get('inventory_restore') == ('ROWS_5_SCALARS_MATCHED' if self.collection_swap else 'ROW_5_SCALARS_MATCHED')
                     and (not self.collection_swap or type(result.get('item_count')) is int and result['item_count'] == 2)
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
                     and (self.collection_swap_flow is not None and self.collection_swap_flow.items ==
                          __import__("tools.local_original_session.item_equipment_swap", fromlist=["collection"]).collection(frame)
                          if self.collection_swap else inventory.validate_frame(frame).identifier > 0),
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
                    client_inventory='ROWS_5_SCALARS_MATCHED' if self.collection_swap else 'ROW_5_SCALARS_MATCHED', native_sequence=consumer.sequence,
                    select_slot_returned=1, select_ok_returned=1, cs4e28=1, new_land=True,
                    saved_frame_restored=True, add_inventory_drained=1)
                if self.collection_swap_flow is not None:
                    self.collection_swap_flow.begin(completed)
                    return
                if self.equipment_restore_flow is not None:
                    self.equipment_restore_flow.begin(completed)
                    return
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
        if self.collection_swap_flow is not None and self.stage.startswith('SWAP_') and state != 'CLOSING':
            if state != 'RUNNING' or self.stop.is_set(): return
            try:
                self.background_desktop()
                self.collection_swap_flow.tick(row, broker)
                self.save()
            except Exception as error:
                self.error = launcher.safe_error_code(error) or type(error).__name__
                self.collection_swap_flow.result.update(status='UNKNOWN', reason=self.error)
                self.stage = 'SWAP_UNKNOWN_STOP_REQUESTED'
                self.save(); self.stop.set()
            return
        if self.stage in ('RESELECT_EQUIPMENT_SYNC_WAIT', 'RESELECT_EQUIPMENT_OPEN_WAIT', 'RESELECT_EQUIPMENT_UI_WAIT') and state != 'CLOSING':
            if state != 'RUNNING' or self.stop.is_set():
                return
            try:
                self.background_desktop()
                self.equipment_restore_flow.tick(row, broker)
                self.save()
            except Exception as error:
                self.error = launcher.safe_error_code(error) or type(error).__name__
                self.equipment_restore_flow.result.update(status='UNKNOWN', reason=self.error)
                self.stage = 'RESELECT_EQUIPMENT_UNKNOWN_STOP_REQUESTED'
                self.save(); self.stop.set()
            return
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

class InventoryUILookupRoleScenario(InventoryUIOpenScenario):
    """Original Open/fresh UI flow plus one optional same-operation scalar."""
    source_quit_profile = UI_LOOKUP_ROLE_PROFILE

    def __init__(self, *args, **kwargs):
        self.lookup_role_observation = None
        super().__init__(*args, **kwargs)

    def bind_runtime(self, runtime):
        super().bind_runtime(runtime)
        need(runtime.ui_lookup_role is not None, 'SCENARIO_UI_ROLE_ACTUAL_CONSUMER_REQUIRED')

    def summary(self):
        row = super().summary()
        row['selected_slot_lookup_role'] = self.lookup_role_observation or {
            'status': 'UNKNOWN', 'reason': 'UI_ROLE_NOT_OBSERVED', 'named_lookup_known': None,
            'native_sequence': None, 'query_started_monotonic_ns': None}
        return row

    def collect_open_ui(self, row, broker):
        super().collect_open_ui(row, broker)
        if self.stage == 'INVENTORY_UI_OPEN_COMPLETE_STOP_REQUESTED':
            self.lookup_role_observation = dict(self.open_runtime.ui_lookup_role_observation)

    def save(self):
        super().save()
        _atomic(self.monitor.directory / 'manual-inventory-ui-lookup-role-observation.json',
                dict(schema='manual-inventory-ui-lookup-role-observation-v1',
                     selected_slot_lookup_role=self.lookup_role_observation,
                     ui=self.ui_observation), 4096, output_only=True)


class NormalOpenUseCurrentUIScenario(InventoryAutoScenario):
    """A distinct saved-row/restore/Open/Use/current-UI flow; no old stop reset."""
    source_quit_profile = NORMAL_OPEN_USE_UI_PROFILE
    USE_SEQUENCE = 2  # Existing public Add1 -> Use2, independent of Native queue seq.
    use_item_only = use_item_effect = use_item_ui_observe = True
    use_authority = UseItemScenario.use_authority
    _effect_current = UseItemScenario._effect_current
    _effect_receipt = UseItemScenario._effect_receipt
    _effect_raw = UseItemScenario._effect_raw
    _effect_unknown_raw_for_ui = UseItemScenario._effect_unknown_raw_for_ui
    _effect_partial_raws_for_ui = UseItemScenario._effect_partial_raws_for_ui
    _open_source = InventoryUIOpenScenario._source

    @staticmethod
    def configuration(config, *, inventory=False, auto_inventory=False):
        from tools.local_original_session import feature_config, inventory as inv, inventory_store, restart
        from tools.local_original_session.item_use_session import POLICY as USE_POLICY
        from tools.local_original_session.item_equipment_effect import POLICY as EFFECT_POLICY
        need(type(config) is feature_config.Features and inventory and auto_inventory
             and config.inventory_policy == inv.POLICY and type(config.inventory_frame) is bytes
             and config.inventory_store_policy == inventory_store.POLICY
             and config.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
             and config.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
             and config.restart_policy == restart.POLICY and config.inventory_missing_row_policy is None
             and config.item_use_policy == USE_POLICY and config.item_equipment_policy == EFFECT_POLICY
             and config.item_equipment_first_enable is False and config.inventory_update_policy is None
             and not config.spawns and config.attack_policy is config.attack_feedback is None
             and config.interval_ns is config.motion_policy is config.goal_policy is config.goal is None,
             'SCENARIO_NORMAL_OPEN_USE_SAVED_RESTORE_CONFIGURATION_REQUIRED')
        inv.validate_frame(config.inventory_frame)
        return config

    def __init__(self, *args, **kwargs):
        self.use_runtime = self.use_session = None
        self.open_queued = self.ui_queued = False
        self.open_observation = self.ui_observation = None
        self.open_started_ns = self.ui_started_ns = None
        self.ui_last_sequence = self.ui_last_query = None
        self.phase_started = None
        self.use_started = self.use_event_start = self.use_received_base = None
        self.use_native_sequence = None
        self.use_item = dict(status='NOT_REQUESTED', accepted_count=0, cs0960=0,
                             proof_scope='UNKNOWN')
        self.use_effect_initial = self.use_effect_final = None
        self.use_effect_initial_raw = self.use_effect_final_raw = None
        self.use_effect = dict(status='NOT_REQUESTED', client_state='UNKNOWN', proof_scope='UNKNOWN')
        self.flow = dict(status='NOT_REQUESTED', open_status='NOT_REQUESTED',
                         ui_status='NOT_REQUESTED', model_uid=None, model_d4=None,
                         pixel_render='UNKNOWN', slot848_visibility='UNKNOWN')
        need(kwargs.get('source_quit_test') is True and kwargs.get('retain_move_goal', False) is False,
             'SCENARIO_NORMAL_OPEN_USE_QUIT_NO_HOLD_REQUIRED')
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-normal-open-use-ui-scenario.json'

    def bind_runtime(self, runtime):
        need(type(runtime) is launcher.ProductFeatures and self.use_runtime is None
             and runtime.inventory_ui_opener is not None and runtime.equipment_ui_observer is not None
             and runtime.equipment_observer is not None and runtime.manual.allow_use_item is True
             and runtime.manual.allow_inventory_update is False and runtime.npc_session is None
             and runtime.manual.consumer.use_item_already_open is True,
             'SCENARIO_NORMAL_OPEN_USE_ACTUAL_RUNTIME_REQUIRED')
        self.use_runtime = runtime

    def summary(self):
        row = super().summary()
        row.pop('last_consumer_result')
        row['normal_open_use_current_ui'] = dict(self.flow,
            effect_status=self.use_effect['status'],
            observation_file='manual-normal-open-use-ui-observation.json')
        row['verification_scope'] = 'SAVED_RESTORE_NORMAL_OPEN_ONE_USE_EFFECT_FRESH_CURRENT_MODEL_D4'
        return row

    def save(self):
        _atomic(self.monitor.directory / 'manual-normal-open-use-ui-observation.json',
            dict(schema='manual-normal-open-use-ui-observation-v1', flow=self.flow,
                 open=self.open_observation, use=self.use_item, effect=self.use_effect,
                 initial=self.use_effect_initial, current=self.use_effect_final,
                 initial_raw=self.use_effect_initial_raw, current_raw=self.use_effect_final_raw,
                 ui=self.ui_observation, last_consumer_result=self.last_consumer_result),
            32768, output_only=True)
        return super().save()

    def _phase(self, name):
        self.stage = 'NORMAL_' + name
        self.phase_started = self.clock()

    def collect_inventory(self, row, broker):
        super().collect_inventory(row, broker)
        if self.stage == 'ATTACK_READY':
            self.inventory['trial_role'] = 'SAVED_ROW_NORMAL_OPEN_USE_PREPARATION'
            self.flow['status'] = 'WAITING_RESTORED_INITIAL_SYNC'
            self._phase('INITIAL_SYNC_WAIT')

    def _authority(self, row, broker):
        position, known, session, claim, identifier = self.use_authority(row, broker)
        need(known is True, 'SCENARIO_NORMAL_OPEN_USE_CURRENT_SOURCE_REQUIRED')
        self.reader.validate()
        need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        runtime, writer = self._effect_current(broker)
        actual, current_writer, _effect = runtime._equipment_binding(same_selection=True)
        need(actual is broker and current_writer is writer,
             'SCENARIO_NORMAL_OPEN_USE_CURRENT_EFFECT_REQUIRED')
        if self.use_effect_initial is not None:
            self._effect_receipt(self.use_effect_initial, initial=True, position=position, identifier=identifier)
            generation, effect = runtime._equipment_generation, broker._item_equipment_effect
            life = effect._selection
            expected = (writer, generation, generation.game, generation.selected,
                        generation.service, generation.item_use_session, broker.realm._actor_fields)
            need(runtime.item_equipment_initial == self.use_effect_initial and type(life) is dict
                 and life.get('synced') is True and life.get('sync_receipt') == self.use_effect_initial
                 and type(life.get('identity')) is tuple and len(life['identity']) == len(expected)
                 and all(a is b for a, b in zip(life['identity'], expected)),
                 'SCENARIO_NORMAL_OPEN_USE_RESTORED_LIFE_CHANGED')
        return position, session, claim, identifier, runtime, writer

    def initial_sync(self, row, broker):
        position, _session, _claim, identifier, runtime, writer = self._authority(row, broker)
        receipt = runtime.item_equipment_initial
        if receipt is None:
            return
        self.use_effect_initial = receipt
        self._effect_receipt(receipt, initial=True, position=position, identifier=identifier)
        need(receipt['initialization_source'] == 'RESTORED_EQUIPMENT_SIDECAR'
             and broker.item_equipment_observation(writer) == receipt,
             'SCENARIO_NORMAL_OPEN_USE_RESTORED_SYNC_REQUIRED')
        if runtime._equipment_sample_ordinal != 0 or runtime.equipment_observation is None:
            return
        raw = self.use_effect_initial_raw = runtime.equipment_observation
        if not self._effect_unknown_raw_for_ui(raw, runtime, writer, broker, True):
            if not self._effect_raw(raw, receipt, position):
                return
        self.flow.update(status='RESTORED_INITIAL_SYNC', initial_weapon_uid=receipt['after_weapon_uid'],
                         initial_revision=receipt['after_revision'])
        self.open_started_ns = time.monotonic_ns()
        self._phase('OPEN_WAIT')

    def collect_open(self, row, broker):
        position, _session, _claim, identifier, runtime, _writer = self._authority(row, broker)
        queued = True
        if not self.open_queued:
            queued = runtime.request_inventory_ui_open()
        value = self.open_observation = runtime.inventory_ui_open_observation
        need(queued is True, 'SCENARIO_NORMAL_OPEN_USE_OPEN_REQUEST_REFUSED')
        self.open_queued = True
        if value['status'] == 'UNKNOWN' and value['reason'] in (
                'NOT_SAMPLED', 'INVENTORY_UI_OPEN_REQUESTED', 'INVENTORY_UI_OPEN_PENDING'):
            need(all(value[k] is None for k in ('opened', 'before_own_visible', 'after_own_visible',
                                                'native_sequence')),
                 'SCENARIO_NORMAL_OPEN_USE_OPEN_PENDING_NULL_REQUIRED')
            return
        need(value['status'] == 'RETURNED' and type(value['reason']) is int and value['reason'] == 0
             and value['invoked'] is True and value['opened'] is True
             and value['before_own_visible'] is False and value['after_own_visible'] is True
             and value['cleanup_required'] is False, 'SCENARIO_NORMAL_OPEN_USE_OPEN_RETURN_REQUIRED')
        self._open_source(value, position, identifier, self.open_started_ns)
        self.flow.update(open_status='RETURNED', status='NORMAL_OPEN_RETURNED')
        # No old Slot/Node/model borrow crosses this mutating call. The original
        # Use consumer and the final UI observer independently acquire fresh state.
        self._authority(row, broker)
        self._phase('USE_READY')

    def submit_use(self, row, broker):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        position, session, claim, identifier, _runtime, _writer = self._authority(row, broker)
        need(self.flow['open_status'] == 'RETURNED' and self.use_item['status'] == 'NOT_REQUESTED'
             and session.accepted_count == 0, 'SCENARIO_NORMAL_OPEN_USE_ONCE_REQUIRED')
        request = dict(schema=REQUEST_SCHEMA, sequence=self.USE_SEQUENCE, command='UseItem',
                       uid=position.uid, item_identifier=identifier, map_id=position.map_id)
        self.use_session, self.use_started = session, self.clock()
        self.use_event_start, self.use_received_base = broker.policy.events, claim['policy_row'].received
        self.use_item.update(status='CLAIMED_NO_RETRY', sequence=self.USE_SEQUENCE,
                             uid=position.uid, item_identifier=identifier, map_id=position.map_id)
        self._phase('USE_WAIT')
        self.save()
        _atomic(self.monitor.directory / 'command.request.json', request, 1024)
        self.use_item['status'] = 'PUBLISHED'

    def collect_use(self, row, broker):
        _position, session, claim, _identifier, _runtime, _writer = self._authority(row, broker)
        self.use_item['accepted_count'] = session.accepted_count
        events = list(broker.policy.log)
        offset = self.use_event_start - (broker.policy.events - len(events))
        need(0 <= offset <= len(events), 'SCENARIO_USE_ITEM_RX_EVENTS_DROPPED')
        received = [e for e in events[offset:] if e[0] == 'rx'
                    and e[1] == claim['peer']['endpoint_port'] and e[2] == 0x0960]
        self.use_item['cs0960'] = len(received)
        result = self._result()
        if result is None or result['sequence'] < self.USE_SEQUENCE:
            return
        need(result['sequence'] == self.USE_SEQUENCE and result.get('command') == 'UseItem'
             and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
             and result.get('cleanup_required') is not True and result.get('automatic_retry') is False,
             'SCENARIO_USE_ITEM_CONSUMER_REFUSED')
        if result['status'] != 'COMMITTED':
            return
        intent = session._current
        need(result.get('phase') == 'COMMITTED' and result.get('native_attempted') is True
             and result.get('proof_scope') == 'VALIDATED_ITEM_USE_INTENT_ONLY'
             and result.get('reason') is None and result.get('cleanup_required') is False
             and type(result.get('last_sequence')) is int and result['last_sequence'] == self.USE_SEQUENCE
             and all(result.get(k) == 'UNKNOWN' for k in ('use_effect', 'ack', 'equipped', 'render', 'save'))
             and session.accepted_count == 1 and len(received) == 1
             and intent is not None and intent.writer is self.move_bound[0]
             and claim['policy_row'].received > self.use_received_base,
             'SCENARIO_USE_ITEM_RECEIVED_INTENT_PROOF_REQUIRED')
        self.use_item.update(status='COMMITTED', proof_scope='VALIDATED_ITEM_USE_INTENT_ONLY')
        manual = self.use_runtime.manual
        need(manual._actual_action_sequence(manual.consumer)
             and type(manual.consumer._action_sequence) is int
             and manual.consumer._action_sequence > self.open_observation['native_sequence'],
             'SCENARIO_NORMAL_OPEN_USE_NATIVE_ACTION_SEQUENCE_REQUIRED')
        self.use_native_sequence = manual.consumer._action_sequence  # Actual original cache, not another counter.
        self._phase('EFFECT_WAIT')

    def collect_effect(self, row, broker):
        position, session, _claim, identifier, runtime, writer = self._authority(row, broker)
        need(self.use_item['status'] == 'COMMITTED' and session.accepted_count == 1,
             'SCENARIO_NORMAL_OPEN_USE_INTENT_REQUIRED')
        receipt = runtime.item_equipment_current
        if receipt is None:
            return
        self.use_effect_final = receipt
        self._effect_receipt(receipt, initial=False, position=position, identifier=identifier)
        need(broker.item_equipment_observation(writer, accepted_ordinal=1) == receipt,
             'SCENARIO_USE_ITEM_EFFECT_CURRENT_RECEIPT_CHANGED')
        if runtime._equipment_sample_ordinal != 1 or runtime.equipment_observation is None:
            return
        self.use_effect_final_raw = runtime.equipment_observation
        if self._effect_partial_raws_for_ui(position, runtime, writer, broker, True):
            self.use_effect.update(status='PARTIAL', client_state='UNKNOWN',
                                   proof_scope='AUTHORITATIVE_TOGGLE_DRAIN_ONLY')
        else:
            if not self._effect_raw(self.use_effect_final_raw, receipt, position):
                return
            need(self.use_effect_final_raw['query_started_monotonic_ns']
                 > self.use_effect_initial_raw['query_started_monotonic_ns'],
                 'SCENARIO_USE_ITEM_EFFECT_FRESH_CLIENT_REQUIRED')
            self.use_effect.update(status='COMMITTED', client_state='FIXED_EQUIPMENT_KEY_VALUE_MATCHED',
                                   proof_scope='AUTHORITATIVE_TOGGLE_DRAIN_TYPED_CLIENT_MATCH')
        self.flow['expected_model_d4'] = receipt['after_weapon_uid'] == identifier
        self.ui_started_ns = time.monotonic_ns()
        # The effect and its fresh UI observation share the existing 15s budget;
        # this transition does not reset the effect observation deadline.
        self.stage = 'NORMAL_UI_WAIT'

    def collect_ui(self, row, broker):
        position, _session, _claim, identifier, runtime, writer = self._authority(row, broker)
        receipt = self.use_effect_final
        self._effect_receipt(receipt, initial=False, position=position, identifier=identifier)
        need(runtime.item_equipment_current == receipt
             and broker.item_equipment_observation(writer, accepted_ordinal=1) == receipt,
             'SCENARIO_USE_ITEM_UI_EFFECT_CHANGED')
        if self.use_effect['status'] == 'PARTIAL':
            need(self._effect_partial_raws_for_ui(position, runtime, writer, broker, True),
                 'SCENARIO_USE_ITEM_UI_PARTIAL_SOURCE_REQUIRED')
        else:
            need(self._effect_raw(self.use_effect_final_raw, receipt, position),
                 'SCENARIO_USE_ITEM_UI_TYPED_EFFECT_REQUIRED')
        queued = True
        if not self.ui_queued:
            queued = runtime.request_item_equipment_ui_observation()
        value = self.ui_observation = runtime.equipment_ui_observation
        need(queued is True, 'SCENARIO_NORMAL_OPEN_USE_UI_REQUEST_REFUSED')
        self.ui_queued = True
        fields = {'status', 'reason', 'invoked', 'observed', 'model_uid', 'model_d4', 'native_sequence',
                  'source_pid', 'source_birth', 'source_image_sha256', 'player_uid', 'item_identifier',
                  'map_id', 'query_started_monotonic_ns', 'cleanup_required'}
        need(type(value) is dict and set(value) == fields, 'SCENARIO_USE_ITEM_UI_PRIMITIVE_SCHEMA_REQUIRED')
        if value['status'] == 'UNKNOWN' and value['reason'] in ('NOT_SAMPLED', 'UI_OBSERVE_REQUESTED', 'UI_OBSERVE_PENDING'):
            need(all(value[k] is False for k in ('invoked', 'observed', 'cleanup_required'))
                 and all(value[k] is None for k in fields - {'status', 'reason', 'invoked', 'observed', 'cleanup_required'}),
                 'SCENARIO_USE_ITEM_UI_PENDING_PRIMITIVES_REQUIRED')
            return
        need(value['status'] == 'OBSERVED' and type(value['reason']) is int and value['reason'] == 0
             and value['invoked'] is False and value['observed'] is True and value['cleanup_required'] is False
             and type(value['model_uid']) is int and value['model_uid'] == identifier
             and type(value['model_d4']) is bool, 'SCENARIO_USE_ITEM_UI_MODEL_PRIMITIVES_REQUIRED')
        self._open_source(value, position, identifier, self.ui_started_ns)
        query, seq = value['query_started_monotonic_ns'], value['native_sequence']
        need(seq > self.use_native_sequence
             and (self.ui_last_sequence is None or seq > self.ui_last_sequence)
             and (self.ui_last_query is None or query > self.ui_last_query),
             'SCENARIO_USE_ITEM_UI_FRESH_QUERY_REQUIRED')
        self.ui_last_sequence, self.ui_last_query = seq, query
        self.flow.update(model_uid=value['model_uid'], model_d4=value['model_d4'])
        if value['model_d4'] is not (receipt['after_weapon_uid'] == identifier):
            need(value['model_d4'] is (receipt['before_weapon_uid'] == identifier),
                 'SCENARIO_USE_ITEM_UI_MODEL_TOGGLE_MISMATCH')
            self.flow.update(ui_status='WAITING_MODEL_D4')
            self.ui_queued = False  # Only a valid old value permits another readonly request.
            return
        self.flow.update(status='OBSERVED', ui_status='OBSERVED',
                         proof_scope='NORMAL_OPEN_USE_EFFECT_CURRENT_SLOT_MODEL_UID_D4')
        self.stage = 'NORMAL_OPEN_USE_UI_COMPLETE_STOP_REQUESTED'
        self.stop.set()

    def tick(self, row, broker, state):
        handlers = {'NORMAL_INITIAL_SYNC_WAIT': self.initial_sync, 'NORMAL_OPEN_WAIT': self.collect_open,
                    'NORMAL_USE_READY': self.submit_use, 'NORMAL_USE_WAIT': self.collect_use,
                    'NORMAL_EFFECT_WAIT': self.collect_effect, 'NORMAL_UI_WAIT': self.collect_ui}
        if self.stage not in handlers or state == 'CLOSING':
            return super().tick(row, broker, state)
        if state != 'RUNNING' or self.stop.is_set():
            return
        try:
            self.background_desktop()
            need(self.clock() - self.phase_started < 15, 'SCENARIO_NORMAL_OPEN_USE_PHASE_EXPIRED')
            handlers[self.stage](row, broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.flow.update(status='UNKNOWN', reason=self.error)
            self.stage = 'NORMAL_OPEN_USE_UI_UNKNOWN_STOP_REQUESTED'
            self.save()
            self.stop.set()


class OriginalScreenshotScenario(InventoryAutoScenario):
    """Minimum saved world/row preparation -> one original request -> Quit."""
    source_quit_profile=ORIGINAL_SCREENSHOT_PROFILE
    configuration=staticmethod(InventoryUIOpenScenario.configuration)

    def __init__(self,*args,**kwargs):
        self.screenshot_runtime=None
        self.original_screenshot=dict(status='NOT_REQUESTED',png_verified=False)
        need(kwargs.get('source_quit_test') is True and not kwargs.get('retain_move_goal',False),
             'SCENARIO_SCREENSHOT_SOURCE_QUIT_NO_MOVE')
        super().__init__(*args,**kwargs)
        self.path=self.monitor.directory/'manual-original-screenshot-scenario.json'

    def bind_runtime(self,runtime):
        need(type(runtime) is launcher.ProductFeatures and self.screenshot_runtime is None
             and getattr(runtime,'original_screenshot',None) is not None
             and runtime.manual.allow_use_item is False and runtime.npc_session is None,
             'SCENARIO_SCREENSHOT_EXPLICIT_RUNTIME')
        self.screenshot_runtime=runtime

    def summary(self):
        row=super().summary()
        row.pop('last_consumer_result',None)
        row['original_screenshot']=dict(self.original_screenshot)
        row['verification_scope']='SAVED_WORLD_ORIGINAL_SCREENSHOT_ONE_FRESH_PNG_EXISTING_QUIT'
        return row

    def collect_inventory(self,row,broker):
        super().collect_inventory(row,broker)
        if self.stage=='ATTACK_READY':
            need(self.screenshot_runtime is not None,'SCENARIO_SCREENSHOT_RUNTIME_REQUIRED')
            self.stage='ORIGINAL_SCREENSHOT_WAIT'
            need(self.screenshot_runtime.original_screenshot.request() is True,
                 'SCENARIO_SCREENSHOT_REQUEST_REFUSED')

    def tick(self,row,broker,state):
        if self.stage!='ORIGINAL_SCREENSHOT_WAIT':return super().tick(row,broker,state)
        if state!='RUNNING' or self.stop.is_set():return
        try:
            self.background_desktop()
            _position,known=self.inventory_authority(row,broker)
            need(known and self.inventory['status']=='COMMITTED' and not self.moves
                 and self.attack['status']=='NOT_REQUESTED','SCENARIO_SCREENSHOT_CURRENT_WORLD')
            result=self.screenshot_runtime.original_screenshot.observation()
            self.original_screenshot=result
            if result['reason'] in ('SCREENSHOT_REQUESTED','SCREENSHOT_PENDING'):return
            need(result['status']=='OBSERVED' and result['png_verified'] is True
                 and result['existing_files_preserved'] is True
                 and result['async_completion']=='CLOSED_STABLE_FRESH_PNG',
                 result.get('reason') or 'SCENARIO_SCREENSHOT_PNG_UNKNOWN')
            self.stage='ORIGINAL_SCREENSHOT_COMPLETE_STOP_REQUESTED'
            self.save();self.stop.set()
        except Exception as error:
            self.error=launcher.safe_error_code(error) or type(error).__name__
            self.original_screenshot=dict(self.original_screenshot,status='UNKNOWN',reason=self.error)
            self.stage='ORIGINAL_SCREENSHOT_UNKNOWN_STOP_REQUESTED'
            self.save();self.stop.set()


class HpStatusPngScenario(HpStatusNotifyScenario):
    """One numeric 19/20 POST, frozen HP result, independent PNG and Quit."""
    summary_byte_limit=8192
    source_quit_profile=HP_STATUS_PNG_PROFILE
    configuration=staticmethod(hp_status_png_configuration)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.screenshot_runtime=None;self.screenshot_requested=False;self.png_failure=None
        self.original_screenshot=dict(status='NOT_REQUESTED',png_verified=False)
        self.path=self.monitor.directory/'manual-hp-status-png-scenario.json'

    bind_runtime=OriginalScreenshotScenario.bind_runtime

    def summary(self):
        row=super().summary()
        row.update(hp_status_png_after_post=True,original_screenshot=dict(self.original_screenshot),
            verification_scope='NUMERIC_HP_19_20_THEN_INDEPENDENT_PNG_EXISTING_QUIT')
        if self.png_failure is not None:row['hp_status_png_failure']=self.png_failure
        return row

    def tick(self,row,broker,state):
        if state=='CLOSING':return super().tick(row,broker,state)
        if self.stage=='ORIGINAL_SCREENSHOT_WAIT':
            hp_error=self.error
            try:return OriginalScreenshotScenario.tick(self,row,broker,state)
            finally:
                if self.stage in ('ORIGINAL_SCREENSHOT_COMPLETE_STOP_REQUESTED','ORIGINAL_SCREENSHOT_UNKNOWN_STOP_REQUESTED'):
                    self.hp_runtime.phase='DONE' # Stop HP polling before the existing Quit loop.
                if hp_error is not None and self.error!=hp_error:
                    self.error=hp_error;self.save()
        if self.stage.startswith('ORIGINAL_SCREENSHOT_'):return
        return super().tick(row,broker,state)


class NormalOpenUseMarkOnScenario(NormalOpenUseCurrentUIScenario):
    """One explicit install, original flow and separately scoped caller data."""
    source_quit_profile = MARK_ON_PROFILE

    def __init__(self, *args, **kwargs):
        self.mark_runtime = None
        self.install_queued = False
        self.install_started_ns = None
        self.install_observation = None
        self.mark = dict(status='NOT_REQUESTED', install_status='NOT_REQUESTED',
                         caller=None, open=None, use=None,
                         proof_scope='NORMAL_CALLER_ONLY_NOT_POST_EFFECT_UI_QUERY')
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-normal-open-use-mark-on-scenario.json'

    def bind_runtime(self, runtime):
        from tools.local_original_session.mark_on_install import InstallMarkOnCaller
        from tools.local_original_session.mark_on_current_indicator import MarkOnCurrentIndicator
        super().bind_runtime(runtime)
        need(type(getattr(runtime,'mark_on_installer',None)) is InstallMarkOnCaller
             and type(getattr(runtime,'mark_on_indicator',None)) is MarkOnCurrentIndicator
             and runtime.mark_on_indicator.observer is runtime.equipment_ui_observer
             and runtime.mark_on_indicator.installer is runtime.mark_on_installer,
             'SCENARIO_MARK_ON_ACTUAL_RUNTIME_REQUIRED')
        self.mark_runtime = runtime

    def initial_sync(self, row, broker):
        super().initial_sync(row,broker)
        if self.stage == 'NORMAL_OPEN_WAIT':
            self.install_started_ns = time.monotonic_ns()
            self._phase('MARK_INSTALL_WAIT')
            self.mark['status'] = 'INSTALL_WAIT'

    def collect_install(self,row,broker):
        position,_session,_claim,identifier,runtime,_writer = self._authority(row,broker)
        need(runtime is self.mark_runtime,'SCENARIO_MARK_ON_RUNTIME_CHANGED')
        queued = True
        if not self.install_queued:
            queued = runtime.request_mark_on_install()
        value = self.install_observation = runtime.mark_on_install_observation
        need(queued is True,'SCENARIO_MARK_ON_INSTALL_REQUEST_REFUSED')
        self.install_queued = True
        if value['status'] == 'UNKNOWN' and value['reason'] in ('NOT_SAMPLED','MARK_ON_INSTALL_REQUESTED','MARK_ON_INSTALL_PENDING'):
            need(value['installed'] is None and value['native_sequence'] is None,
                 'SCENARIO_MARK_ON_INSTALL_PENDING_NULL_REQUIRED')
            return
        self.mark['install_status'] = value['status']
        need(value['status'] == 'RETURNED' and type(value['reason']) is int and value['reason'] == 0
             and value['invoked'] is True and value['installed'] is True and value['cleanup_required'] is False,
             'SCENARIO_MARK_ON_INSTALL_RETURN_REQUIRED')
        self._open_source(value,position,identifier,self.install_started_ns)
        self.mark['status'] = 'INSTALLED'
        self.open_started_ns = time.monotonic_ns()
        self._phase('OPEN_WAIT')

    def collect_open(self,row,broker):
        super().collect_open(row,broker)
        if self.stage == 'NORMAL_USE_READY' and self.mark['open'] is None:
            marker = self.mark_runtime.mark_on_indicator
            self.mark['open'] = marker.consume_action('OpenInventoryUI',self.open_observation['native_sequence'],self.open_observation)
            self.mark['caller'] = marker.consume_caller()

    def collect_use(self,row,broker):
        super().collect_use(row,broker)
        if self.stage == 'NORMAL_EFFECT_WAIT' and self.mark['use'] is None:
            marker = self.mark_runtime.mark_on_indicator
            self.mark['use'] = marker.consume_action('UseItemAlreadyOpen',self.use_native_sequence,self.mark_runtime.manual.last_result)
            self.mark.pop('caller_capture_scope',None)
            self.mark['caller'] = marker.consume_caller()

    def collect_ui(self,row,broker):
        super().collect_ui(row,broker)
        if self.flow['status'] == 'OBSERVED':
            # Original old15/Use/effect result and stop are preserved. This
            # caller timestamp is neither UI query_ns nor post-effect proof.
            self.mark.pop('caller_capture_scope',None)
            self.mark['caller'] = self.mark_runtime.mark_on_indicator.consume_caller()
            self.mark['status'] = self.mark['caller']['status']

    def summary(self):
        result = super().summary()
        caller = self.mark['caller'] or {}
        result['mark_on_current_indicator'] = dict(status=self.mark['status'],
            install_status=self.mark['install_status'],caller_status=caller.get('status','UNKNOWN'),
            native_status=caller.get('native_status'),native_reason=caller.get('native_reason'),
            receiver_stage=caller.get('receiver_stage'),receiver_rva=caller.get('receiver_rva'),
            caller_capture_scope=self.mark.get('caller_capture_scope'),
            mark_own_visible=caller.get('mark_own_visible'),callback_qpc=caller.get('callback_qpc'),
            callback_qpc_frequency=caller.get('callback_qpc_frequency'),
            action_command=caller.get('action_command'),action_seq=caller.get('action_seq'),
            proof_scope=self.mark['proof_scope'],observation_file='manual-mark-on-current-indicator-observation.json')
        return result

    def save(self):
        _atomic(self.monitor.directory / 'manual-mark-on-current-indicator-observation.json',
                dict(schema='manual-mark-on-current-indicator-observation-v1',install=self.install_observation,
                     mark=self.mark,old_ui=self.ui_observation),8192,output_only=True)
        return super().save()

    def tick(self,row,broker,state):
        if self.stage == 'NORMAL_USE_WAIT' and state == 'RUNNING' and not self.stop.is_set():
            runtime = self.mark_runtime
            from tools.local_original_session.mark_on_current_indicator import caller_empty
            captured = getattr(runtime, '_mark_on_use_caller_capture', None)
            runtime._mark_on_use_caller_capture = None
            if captured is None:
                self.mark['caller'] = caller_empty('MARK_ON_EARLY_USE_NOT_CAPTURED')
                self.mark['caller_capture_scope'] = 'NOT_CAPTURED'
            else:
                pending = runtime.manual.consumer.pending
                if (type(captured) is tuple and len(captured) == 3 and captured[0] is pending
                        and type(pending) is dict and pending.get('kind') == 'UseItem'
                        and captured[1] == runtime.manual.consumer.sequence):
                    self.mark['caller'] = dict(captured[2])
                    self.mark['caller_capture_scope'] = 'PRE_MANUAL_USE_POLL_ONLY_NOT_STOP_CURRENT'
                else:
                    self.mark['caller'] = caller_empty('MARK_ON_EARLY_USE_OPERATION_CHANGED')
                    self.mark['caller_capture_scope'] = 'NOT_CAPTURED'
        if self.stage != 'NORMAL_MARK_INSTALL_WAIT':return super().tick(row,broker,state)
        if state != 'RUNNING' or self.stop.is_set():return
        try:
            self.background_desktop()
            need(self.clock()-self.phase_started < 15,'SCENARIO_MARK_ON_INSTALL_EXPIRED')
            self.collect_install(row,broker)
            self.save()
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.mark.update(status='UNKNOWN',reason=self.error)
            self.stage = 'NORMAL_MARK_ON_UNKNOWN_STOP_REQUESTED'
            self.save()
            self.stop.set()




class ItemTransferScenario(ContinuousMoveScenario):
    """Existing saved-world preparation, one explicit UI owner, existing Quit."""
    background_profile = source_quit_profile = ITEM_TRANSFER_PROFILE
    summary_byte_limit = 8192

    def __init__(self, *args, features, **kwargs):
        from tools.local_original_session.item_transfer_runner import configuration
        self.features = configuration(features, inventory=True, auto_inventory=True)
        need(kwargs.get('source_quit_test') is True and not kwargs.get('retain_move_goal', False),
             'SCENARIO_TRANSFER_BACKGROUND_QUIT_REQUIRED')
        self.transfer_runtime = None
        self.inventory = dict(status='NOT_REQUESTED')
        self.transfer_result = dict(status='NOT_REQUESTED', automatic_retry=False,
            scope='EXPLICIT_LOCAL_WHOLE_B_UI_ROUNDTRIP', render='UNKNOWN')
        super().__init__(*args, **kwargs)
        self.path = self.monitor.directory / 'manual-item-transfer-scenario.json'

    def summary(self):
        return dict(super().summary(), attack_target=dict(status='NOT_REQUESTED'),
            inventory_add=self.inventory, item_transfer_ui=self.transfer_result)

    def fail_transfer(self, reason):
        self.error = self.error or reason
        self.transfer_result.update(status='UNKNOWN', automatic_retry=False)
        self.stage = 'ITEM_TRANSFER_UNKNOWN_STOP_REQUESTED'
        self.save(); self.stop.set()

    def tick(self, row, broker, state):
        if self.stage in ('LOGIN','WAIT_LOGIN','WAIT_SLOT','WAIT_LAND'):
            super().tick(row, broker, state)
            if self.stage == 'MOVE_READY':
                self.stage = 'ITEM_TRANSFER_RUN'
                self.save()
        elif state == 'CLOSING':
            self.confirm_close(row, broker)
        # No inherited attack, MoveGoal, idle hold or explicit Add publication.

    def finalize(self):
        try:
            if self.transfer_runtime is not None:
                self.transfer_runtime.finalize()
            if self.transfer_result.get('status') != 'COMPLETE':
                self.fail_transfer('SCENARIO_TRANSFER_INCOMPLETE')
        except Exception as error:
            self.fail_transfer(launcher.safe_error_code(error) or type(error).__name__)


def selected_profile(continuous, background=False, *, attack=False, source_quit=False, use_item=False, inventory_update=False,
                     source_restart=False, source_reselect=False, use_item_ui_observe=False, ui_current_frame_update=False, npc_respawn=False, inventory_ui_open=False, selected_slot_lookup_role=False, npc_respawn_next_hit=False, normal_open_use_ui=False, original_screenshot=False, mark_on=False, hp_status_notify=False, hp_status_png=False, npc_player_hit=False, npc_player_hit_repeated=False, npc_approach_hit=False, reselect_equipment_restore=False, collection_swap=False, collection_swap_saved_b_tail=False, collection_swap_zero_use=False, item_transfer_ui=False, player_death_recovery=False, npc_player_lethal_recovery=False):
    need(type(player_death_recovery) is bool and type(npc_player_lethal_recovery) is bool
         and (not npc_player_lethal_recovery or player_death_recovery),
         'SCENARIO_PLAYER_LIFE_EXPLICIT_BOOL_REQUIRED')
    need(type(item_transfer_ui) is bool, 'SCENARIO_TRANSFER_EXACT_BOOL_REQUIRED')
    if item_transfer_ui:
        need(background and source_quit and not any((continuous,attack,use_item,inventory_update,
             source_restart,source_reselect,use_item_ui_observe,ui_current_frame_update,npc_respawn,
             inventory_ui_open,selected_slot_lookup_role,npc_respawn_next_hit,normal_open_use_ui,
             original_screenshot,mark_on,hp_status_notify,hp_status_png,npc_player_hit,
             npc_player_hit_repeated,npc_approach_hit,reselect_equipment_restore,collection_swap,
             collection_swap_saved_b_tail,collection_swap_zero_use,player_death_recovery)), 'SCENARIO_TRANSFER_EXCLUSIVE_MODE_REQUIRED')
        profile = launcher.PRODUCTS[ITEM_TRANSFER_PROFILE]
        need(profile.get('item_transfer_ui') is True and profile.get('manual_only') is True
             and profile.get('require_source_quit') is True
             and profile.get('item_transfer_entry') == 'CURRENT_SOURCE_BOUND_ITEM_ENTRY_V2'
             and profile.get('item_quantity_popup') == 'CURRENT_PC_ITEM_QUANTITY_POPUP_V1'
             and profile['bridges'].get('own-login-bridge-dg49.dll') == ITEM_TRANSFER_DLL_SHA,
             'SCENARIO_TRANSFER_EXACT_PRODUCT_REQUIRED')
        return ITEM_TRANSFER_PROFILE, profile
    if player_death_recovery:
        from tools.local_original_session.player_death_recovery_focused import DEATH_PROFILE, DEAD_DLL_SHA, DEAD_DLL_PATH
        need(background and source_quit and not any((continuous,attack,use_item,inventory_update,source_restart,source_reselect,use_item_ui_observe,ui_current_frame_update,npc_respawn,inventory_ui_open,selected_slot_lookup_role,npc_respawn_next_hit,normal_open_use_ui,original_screenshot,mark_on,hp_status_notify,hp_status_png,npc_player_hit,npc_player_hit_repeated,npc_approach_hit,reselect_equipment_restore,collection_swap,collection_swap_saved_b_tail,collection_swap_zero_use,item_transfer_ui)), 'SCENARIO_PLAYER_LIFE_EXCLUSIVE_PROFILE_REQUIRED')
        if npc_player_lethal_recovery:
            from tools.local_original_session.npc_player_lethal_recovery_focused import PROFILE as DEATH_PROFILE
        profile=launcher.PRODUCTS[DEATH_PROFILE]
        need(not npc_player_lethal_recovery or profile.get('npc_player_lethal_recovery') is True,
             'SCENARIO_NPC_LETHAL_EXACT_PROFILE_REQUIRED')
        need(profile['image_sha256']==IMAGE_SHA and profile['bridges']['own-login-bridge-dg49.dll']==DEAD_DLL_SHA
             and profile['bridge_artifact']==ROOT/DEAD_DLL_PATH
             and all(profile.get(k) is True for k in ('require_background','background_display_guard','manual_source_quit','require_source_quit','player_death_recovery'))
             and profile.get('continuous_manual_move') is True
             and all(profile.get(k) is False for k in ('continuous_manual_attack','manual_attack_move_replacement')),
             'SCENARIO_PLAYER_LIFE_EXACT_PRODUCT_REQUIRED')
        return DEATH_PROFILE,profile
    need(type(npc_approach_hit) is bool
         and (not npc_approach_hit or hp_status_notify and not any((hp_status_png, npc_player_hit, npc_player_hit_repeated))),
         'SCENARIO_APPROACH_EXPLICIT_MODE_REQUIRED')
    need(type(npc_player_hit_repeated) is bool
         and (not npc_player_hit_repeated or hp_status_notify and not hp_status_png and not npc_player_hit),
         'SCENARIO_NPC_PLAYER_HIT_REPEATED_EXPLICIT_MODE_REQUIRED')
    need(type(npc_player_hit) is bool and (not npc_player_hit or hp_status_notify and not hp_status_png),
         'SCENARIO_NPC_PLAYER_HIT_EXPLICIT_MODE_REQUIRED')
    need(type(hp_status_notify) is bool,'SCENARIO_HP_STATUS_EXPLICIT_MODE_REQUIRED')
    need(type(hp_status_png) is bool and (not hp_status_png or hp_status_notify),
         'SCENARIO_HP_PNG_EXPLICIT_PARENT_REQUIRED')
    need(type(reselect_equipment_restore) is bool, 'SCENARIO_RESELECT_EQUIPMENT_BOOL_REQUIRED')
    need(type(collection_swap) is bool, 'SCENARIO_SWAP_EXPLICIT_BOOL_REQUIRED')
    need(type(collection_swap_saved_b_tail) is bool
         and (not collection_swap_saved_b_tail or collection_swap is True),
         'SCENARIO_SWAP_SAVED_B_TAIL_EXPLICIT_MODE_REQUIRED')
    need(type(collection_swap_zero_use) is bool
         and (not collection_swap_zero_use or collection_swap is True and collection_swap_saved_b_tail is False),
         'SCENARIO_ZERO_USE_RESELECT_EXPLICIT_MODE_REQUIRED')
    if collection_swap:
        need(background and source_quit and source_restart and source_reselect
             and not any((continuous, attack, use_item, inventory_update, use_item_ui_observe,
                 ui_current_frame_update, npc_respawn, inventory_ui_open, selected_slot_lookup_role,
                 npc_respawn_next_hit, normal_open_use_ui, original_screenshot, mark_on, hp_status_notify, reselect_equipment_restore)),
             'SCENARIO_SWAP_EXCLUSIVE_PROFILE_REQUIRED')
        chosen = ZERO_USE_RESELECT_PROFILE if collection_swap_zero_use else CURRENT_ENTRY_TAIL_PROFILE if collection_swap_saved_b_tail else SWAP_PROFILE
        profile = launcher.PRODUCTS[chosen]
        need(profile['image_sha256'] == IMAGE_SHA
             and profile['bridges']['own-login-bridge-dg49.dll'] == (ZERO_USE_RESELECT_DLL_SHA if collection_swap_zero_use
                 else CURRENT_ENTRY_TAIL_DLL_SHA if collection_swap_saved_b_tail else RESELECT_EQUIPMENT_DLL_SHA)
             and all(profile.get(k) is True for k in ('require_background', 'background_display_guard',
                 'manual_source_quit', 'require_source_quit', 'manual_source_restart', 'manual_source_reselect',
                 'inventory_ui_open', 'item_equipment_ui_observe', 'item_equipment_swap_reselect',
                 ))
             and profile.get('manual_use_item') is (not collection_swap_zero_use)
             and (all(profile.get(k) is False for k in ('use_item_current_entry', 'use_item_already_open'))
                  and profile.get('item_equipment_zero_use_reselect') is True if collection_swap_zero_use
                  else (profile.get('use_item_current_entry') is True and profile.get('use_item_already_open') is False
                  if collection_swap_saved_b_tail else profile.get('use_item_already_open') is True))
             and all(profile.get(k) is False for k in ('continuous_manual_move', 'continuous_manual_attack',
                 'manual_attack_move_replacement', 'manual_inventory_update')),
             'SCENARIO_SWAP_EXACT_PRODUCT_REQUIRED')
        return chosen, profile
    if reselect_equipment_restore:
        need(background and source_quit and source_restart and source_reselect
             and not any((continuous, attack, use_item, inventory_update, use_item_ui_observe,
                 ui_current_frame_update, npc_respawn, inventory_ui_open, selected_slot_lookup_role,
                 npc_respawn_next_hit, normal_open_use_ui, original_screenshot, mark_on, hp_status_notify)),
             'SCENARIO_RESELECT_EQUIPMENT_EXCLUSIVE_PROFILE_REQUIRED')
        profile = launcher.PRODUCTS[RESELECT_EQUIPMENT_PROFILE]
        need(profile['image_sha256'] == IMAGE_SHA
             and profile['bridges']['own-login-bridge-dg49.dll'] == RESELECT_EQUIPMENT_DLL_SHA
             and all(profile.get(k) is True for k in ('require_background', 'background_display_guard',
                 'manual_source_quit', 'require_source_quit', 'manual_source_restart', 'manual_source_reselect',
                 'inventory_ui_open', 'item_equipment_ui_observe', 'item_equipment_reselect_restore'))
             and all(profile.get(k) is False for k in ('continuous_manual_move', 'continuous_manual_attack',
                 'manual_attack_move_replacement', 'manual_use_item', 'manual_inventory_update')),
             'SCENARIO_RESELECT_EQUIPMENT_EXACT_PRODUCT_REQUIRED')
        return RESELECT_EQUIPMENT_PROFILE, profile
    if hp_status_notify:
        need(background and source_quit and not any((continuous,attack,use_item,inventory_update,source_restart,
             source_reselect,use_item_ui_observe,ui_current_frame_update,npc_respawn,inventory_ui_open,
             selected_slot_lookup_role,npc_respawn_next_hit,normal_open_use_ui,original_screenshot,mark_on)),
             'SCENARIO_HP_STATUS_EXCLUSIVE_PROFILE_REQUIRED')
        hp_profile=NPC_APPROACH_HIT_PROFILE if npc_approach_hit else NPC_PLAYER_HIT_REPEATED_PROFILE if npc_player_hit_repeated else NPC_PLAYER_HIT_PROFILE if npc_player_hit else HP_STATUS_PNG_PROFILE if hp_status_png else SOURCE_QUIT_PROFILE
        profile=launcher.PRODUCTS[hp_profile]
        need(profile['image_sha256']==IMAGE_SHA
             and profile['bridges']['own-login-bridge-dg49.dll']==(NPC_APPROACH_HIT_DLL_SHA if npc_approach_hit else ORIGINAL_SCREENSHOT_DLL_SHA if hp_status_png or npc_player_hit or npc_player_hit_repeated else SOURCE_QUIT_DLL_SHA)
             and all(profile.get(k) is True for k in ('require_background','background_display_guard',
                 'manual_only','manual_source_quit','require_source_quit'))
             and not any(profile.get(k) for k in ('internal_only','require_lifecycle_health')),
             'SCENARIO_HP_STATUS_EXACT_EXISTING_PROFILE_REQUIRED')
        return hp_profile,profile
    need(type(mark_on) is bool and (not mark_on or normal_open_use_ui), 'SCENARIO_MARK_ON_EXPLICIT_PARENT_REQUIRED')
    need(type(original_screenshot) is bool, 'SCENARIO_SCREENSHOT_EXPLICIT_BOOL')
    if original_screenshot:
        need(background and source_quit and not any((continuous, attack, use_item, inventory_update,
             source_restart, source_reselect, use_item_ui_observe, ui_current_frame_update, npc_respawn,
             inventory_ui_open, selected_slot_lookup_role, npc_respawn_next_hit, normal_open_use_ui)),
             'SCENARIO_SCREENSHOT_EXCLUSIVE_PROFILE')
        profile=launcher.PRODUCTS[ORIGINAL_SCREENSHOT_PROFILE]
        need(profile['image_sha256']==IMAGE_SHA and profile.get('original_screenshot') is True
             and profile['bridges']['own-login-bridge-dg49.dll']==ORIGINAL_SCREENSHOT_DLL_SHA,
             'SCENARIO_SCREENSHOT_EXACT_PRODUCT')
        return ORIGINAL_SCREENSHOT_PROFILE,profile
    need(type(normal_open_use_ui) is bool, 'SCENARIO_NORMAL_OPEN_USE_EXPLICIT_BOOL_REQUIRED')
    if normal_open_use_ui:
        need(background and source_quit and not any((continuous, attack, use_item, inventory_update,
             source_restart, source_reselect, use_item_ui_observe, ui_current_frame_update, npc_respawn,
             inventory_ui_open, selected_slot_lookup_role, npc_respawn_next_hit)),
             'SCENARIO_NORMAL_OPEN_USE_EXCLUSIVE_PROFILE_REQUIRED')
        chosen = MARK_ON_PROFILE if mark_on else NORMAL_OPEN_USE_UI_PROFILE
        profile = launcher.PRODUCTS[chosen]
        need(profile['image_sha256'] == IMAGE_SHA
             and profile['bridges']['own-login-bridge-dg49.dll'] == (MARK_ON_DLL_SHA if mark_on else NORMAL_OPEN_USE_UI_DLL_SHA)
             and (profile.get('mark_on_current_indicator') is True if mark_on else not profile.get('mark_on_current_indicator',False))
             and all(profile.get(k) is True for k in ('normal_open_use_current_ui', 'inventory_ui_open',
                 'manual_use_item', 'use_item_already_open', 'item_equipment_ui_observe', 'manual_source_quit'))
             and all(profile.get(k) is False for k in ('continuous_manual_move', 'continuous_manual_attack',
                 'manual_inventory_update')), 'SCENARIO_NORMAL_OPEN_USE_EXACT_PRODUCT_REQUIRED')
        return chosen, profile
    need(type(npc_respawn_next_hit) is bool and not (npc_respawn and npc_respawn_next_hit),
         'SCENARIO_RESPAWN_HIT_EXCLUSIVE_MODE_REQUIRED')
    need(not npc_respawn_next_hit or background and attack and source_quit
         and not any((continuous,use_item,inventory_update,source_restart,source_reselect,use_item_ui_observe,
                      ui_current_frame_update,inventory_ui_open,selected_slot_lookup_role)),
         'SCENARIO_RESPAWN_HIT_EXCLUSIVE_PROFILE_REQUIRED')
    need(type(npc_respawn) is bool and (not npc_respawn or background and attack and source_quit
         and not any((continuous, use_item, inventory_update, source_restart, source_reselect,
                      use_item_ui_observe, ui_current_frame_update))),
         'SCENARIO_NPC_RESPAWN_EXCLUSIVE_PROFILE_REQUIRED')
    need(not selected_slot_lookup_role or inventory_ui_open, 'SCENARIO_UI_ROLE_EXPLICIT_OPEN_MODE_REQUIRED')
    if inventory_ui_open:
        need(background and source_quit and not any((continuous, attack, use_item, inventory_update,
             source_restart, source_reselect, use_item_ui_observe, ui_current_frame_update, npc_respawn)),
             'SCENARIO_INVENTORY_OPEN_EXCLUSIVE_PROFILE_REQUIRED')
        chosen = UI_LOOKUP_ROLE_PROFILE if selected_slot_lookup_role else INVENTORY_UI_OPEN_PROFILE
        expected_dll = UI_LOOKUP_ROLE_DLL_SHA if selected_slot_lookup_role else INVENTORY_UI_OPEN_DLL_SHA
        profile = launcher.PRODUCTS[chosen]
        need(profile['image_sha256'] == IMAGE_SHA
             and profile['bridges']['own-login-bridge-dg49.dll'] == expected_dll
             and (not selected_slot_lookup_role or profile.get('selected_slot_lookup_role') is True)
             and all(profile.get(k) is True for k in ('require_background', 'background_display_guard',
                 'manual_source_quit', 'require_source_quit', 'inventory_ui_open', 'item_equipment_ui_observe'))
             and all(profile.get(k) is False for k in ('continuous_manual_move', 'continuous_manual_attack',
                 'manual_use_item', 'manual_inventory_update')),
             'SCENARIO_INVENTORY_OPEN_EXACT_PRODUCT_REQUIRED')
        return chosen, profile
    if ui_current_frame_update:
        need(background and source_quit and not any((continuous, attack, use_item, inventory_update,
             source_restart, source_reselect, use_item_ui_observe)), 'SCENARIO_UI_UPDATE_EXCLUSIVE_PROFILE_REQUIRED')
        profile = launcher.PRODUCTS[UI_FRAME_UPDATE_PROFILE]
        need(profile['image_sha256'] == IMAGE_SHA
             and profile['bridges']['own-login-bridge-dg49.dll'] == USE_ITEM_UI_DLL_SHA
             and all(profile.get(k) is True for k in ('require_background', 'background_display_guard',
                 'manual_source_quit', 'require_source_quit', 'manual_inventory_update', 'item_equipment_ui_observe'))
             and all(profile.get(k) is False for k in ('continuous_manual_move', 'continuous_manual_attack', 'manual_use_item')),
             'SCENARIO_UI_UPDATE_EXACT_PRODUCT_REQUIRED')
        return UI_FRAME_UPDATE_PROFILE, profile
    need(type(use_item_ui_observe) is bool and (not use_item_ui_observe or use_item),
         'SCENARIO_USE_ITEM_UI_OBSERVE_USE_REQUIRED')
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
    if npc_respawn_next_hit:
        name, pin = NPC_RESPAWN_NEXT_HIT_PROFILE, NPC_RESPAWN_NEXT_HIT_DLL_SHA
    elif npc_respawn:
        name, pin = NPC_RESPAWN_PROFILE, SOURCE_QUIT_DLL_SHA
    elif source_reselect:
        name, pin = SOURCE_RESELECT_PROFILE, SOURCE_RESELECT_DLL_SHA
    elif source_restart:
        name, pin = SOURCE_RESTART_PROFILE, SOURCE_RESTART_DLL_SHA
    elif inventory_update:
        name, pin = INVENTORY_UPDATE_PROFILE, SOURCE_QUIT_DLL_SHA
    elif use_item_ui_observe:
        name, pin = USE_ITEM_UI_PROFILE, USE_ITEM_UI_DLL_SHA
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
    need(not use_item_ui_observe or profile.get('item_equipment_ui_observe') is True,
         'SCENARIO_EXPLICIT_USE_ITEM_UI_OBSERVE_PRODUCT_REQUIRED')
    need(not inventory_update or profile.get('manual_inventory_update') is True,
         'SCENARIO_EXPLICIT_INVENTORY_UPDATE_PRODUCT_REQUIRED')
    need(not source_restart or profile.get('manual_source_restart') is True,
         'SCENARIO_EXPLICIT_SOURCE_RESTART_PRODUCT_REQUIRED')
    need(not source_reselect or profile.get('manual_source_reselect') is True,
         'SCENARIO_EXPLICIT_SOURCE_RESELECT_PRODUCT_REQUIRED')
    need(not npc_respawn or profile.get('npc_respawn_lifecycle') is True,
         'SCENARIO_EXPLICIT_NPC_RESPAWN_PRODUCT_REQUIRED')
    need(not npc_respawn_next_hit or profile.get('npc_respawn_lifecycle') is True
         and profile.get('allow_respawn_attack') is True, 'SCENARIO_RESPAWN_HIT_EXACT_PRODUCT_REQUIRED')
    return name, profile


def main():
    need('--background' in sys.argv[1:] and any(flag in sys.argv[1:] for flag in
         ('--item-transfer-ui-test', '--item-equipment-swap-reselect-test', '--reselect-equipment-ui-restore-test', '--continuous-move-test', '--attack-target-test', '--ui-current-frame-update-test', '--inventory-ui-open-test', '--normal-open-use-current-ui-test', '--original-screenshot-test', '--hp-status-notify-only', '--hp-status-png-after-post', '--npc-player-hit-only', '--npc-player-hit-repeated-only', '--npc-approach-player-hit-only', '--player-death-recovery-only', '--npc-player-lethal-recovery-only')),
         'FOCUS_STEALING_LAUNCH_DISABLED')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--player-death-recovery-only', action='store_true')
    parser.add_argument('--observe-hp4ec8-subscribers-once', action='store_true')
    parser.add_argument('--npc-hp-feedback-only', action='store_true')
    parser.add_argument('--hp4ec8-observation-stage', choices=('first-land','npc-hp-feedback-drained'))
    parser.add_argument('--npc-player-lethal-recovery-only', action='store_true',
        help='One current NPC approach/contact HP1-to-zero hit and original recovery, then existing Quit.')
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
    mode.add_argument('--npc-approach-player-hit-only', action='store_true',
        help='One explicit nonzero source-bound NPC approach then one positive Plan hit, fresh action/HP/HUD, existing Quit.')
    mode.add_argument('--npc-player-hit-repeated-only', action='store_true',
        help='Two explicit same-NPC positive hits; first is preparation, second is fresh HP19 to18, then Quit.')
    mode.add_argument('--npc-player-hit-only', action='store_true',
        help='One explicit current NPC hit, positive player HP minus one, fresh HP/HUD/action reads, then existing Quit.')
    mode.add_argument('--hp-status-notify-only',action='store_true',
                        help='One explicit positive local-character HP4E38 status update with fresh PRE/POST HP readback, then existing source Quit.')
    mode.add_argument('--hp-status-png-after-post',action='store_true',
        help='One explicit numeric HP19/20 POST, independent existing Screenshot, then Quit; preserves HUD UNKNOWN/CLI failure.')
    mode.add_argument('--item-transfer-ui-test', action='store_true', help='One explicit whole-B UI drop/pickup; original saved Add, optional real Use preparation and existing Quit.')
    parser.add_argument('--feature-config', type=Path)
    parser.add_argument('--npc-current-life-retire-only',action='store_true',
                        help='Required current gen2 normal hit then one ordinal3 removal and fresh UID absence.')
    parser.add_argument('--npc-current-life-next-hit-only',action='store_true',
                        help='Required second respawn then one normal gen2 attack; no further life loop.')
    parser.add_argument('--npc-second-respawn-only', action='store_true',
                        help='Required gen1 retirement then one explicit gen2 respawn; no further attack.')
    parser.add_argument('--npc-respawn-next-hit-remove-only', action='store_true',
                        help='Required respawn/next-hit preparation, one ordinal2 Remove and fresh UID absence; same explicit background profile.')
    parser.add_argument('--npc-respawn-next-hit-only', action='store_true',
                        help='Required respawn preparation then one normal attack on its new local generation; requires explicit background profile.')
    parser.add_argument('--npc-respawn-only', action='store_true',
                        help='Required normal lethal preparation, one explicit same-recipe fresh NPC generation, canonical client registry/pose and source Quit cleanup.')
    parser.add_argument('--npc-dead-goal-only', action='store_true',
                        help='Opt-in current-tile live goal -> original lethal Attack2 -> same product DEAD/IDLE -> source Quit; requires --npc-hp-death-only.')
    parser.add_argument('--npc-hp-death-only', action='store_true',
                        help='Saved-row/world preparation, normal Attack2, lethal local HP, Death snapshot, explicit backend Remove and three-vector UID absence; existing source Quit cleanup only.')
    parser.add_argument('--npc-motion-goal-only', action='store_true',
                        help='Saved-row/world preparation, current NPC pose/idle, one explicit adjacent goal, existing NPC tick/drain, client pose/idle and existing source Quit cleanup.')
    parser.add_argument('--npc-respawn-motion-only', action='store_true',
                        help='After required gen1 respawn, one explicit local NPC step; requires --npc-motion-goal 32578 32946.')
    parser.add_argument('--npc-motion-goal', nargs=2, type=int, metavar=('X', 'Y'),
                        help='Explicit adjacent destination for --npc-motion-goal-only or --npc-respawn-motion-only; config.goal stays None.')
    inventory_mode = parser.add_mutually_exclusive_group()
    inventory_mode.add_argument('--inventory-add-test', action='store_true',
                        help='Confirm public AddInventory1 before AttackTarget2/MoveGoal3/return4; requires attack/background/config.')
    inventory_mode.add_argument('--inventory-auto-test', action='store_true',
                        help='Observe restored inventory auto delivery1 before AttackTarget2/MoveGoal3/return4; requires attack/background/config.')
    parser.add_argument('--reselect-equipment-ui-restore-test', action='store_true',
        help='Saved-only original Restart/Reselect, new equipment sync/raw, one Open/fresh UID-D4, Quit; no Use.')
    parser.add_argument('--mark-on-current-indicator-test', action='store_true')
    parser.add_argument('--selected-slot-lookup-role-test', action='store_true',
                        help='Bind one optional scalar to the same completed UI observation; no extra query.')
    item_mode = parser.add_mutually_exclusive_group()
    item_mode.add_argument('--normal-open-use-current-ui-test', action='store_true')
    item_mode.add_argument('--original-screenshot-test', action='store_true', help='One original Screenshot after saved world preparation, verify fresh PNG, original Quit.')
    item_mode.add_argument('--inventory-ui-open-test', action='store_true',
                        help='Saved inventory, one explicit normal Open, fresh UID/D4 observation, original Quit; no Use/effect/input.')
    item_mode.add_argument('--ui-current-frame-update-test', action='store_true',
                        help='Saved row, readonly UI primitive, one canonical update, fresh UI primitive, source Quit; no Use/Attack/Move.')
    item_mode.add_argument('--use-item-test', action='store_true',
                        help='Observe restored inventory1/attack2, then UseItem3/move4/return5; requires auto inventory/background/attack/source Quit/config.')
    parser.add_argument('--use-item-ui-observe-test', action='store_true',
                        help='Observe fresh readonly UI model UID/D4 after the one focused effect; requires --use-item-effect-test.')
    parser.add_argument('--use-item-effect-test', action='store_true',
                        help='Verify one explicit equipment effect and typed client state; requires --use-item-only and exact item_equipment config.')
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
    parser.add_argument('--item-equipment-swap-reselect-test', action='store_true',
                        help='Three original Use B operations, source Restart/reselect, saved two-row B restore and fresh serial UI.')
    parser.add_argument('--item-equipment-swap-saved-b-tail-test', action='store_true',
                        help='Explicit fresh saved-B input: two original Use B operations then the existing Restart/reselect path; requires swap-reselect-test.')
    parser.add_argument('--item-equipment-zero-use-reselect-test', action='store_true',
        help='Explicit saved-B restore/Open/UI then Restart/reselect; zero Use; requires swap-reselect-test.')
    args = parser.parse_args()
    need(args.hp4ec8_observation_stage is None or args.observe_hp4ec8_subscribers_once,
         'HP4EC8_STAGE_ONCE_FLAG_REQUIRED')
    need(not args.npc_hp_feedback_only or args.background and args.attack_target_test
         and args.inventory_auto_test and args.source_quit_test and args.feature_config is not None
         and args.observe_hp4ec8_subscribers_once
         and args.hp4ec8_observation_stage == 'npc-hp-feedback-drained' and args.idle_seconds == 0
         and not any((args.continuous_move_test,args.confirm_window_close,args.retain_move_goal,
             args.inventory_add_test,args.source_restart_test,args.source_reselect_test,args.reselect_inventory_only,
             args.item_transfer_ui_test,args.item_equipment_swap_reselect_test,
             args.item_equipment_swap_saved_b_tail_test,args.item_equipment_zero_use_reselect_test,
             args.reselect_equipment_ui_restore_test,args.use_item_test,args.use_item_only,
             args.use_item_effect_test,args.use_item_ui_observe_test,args.inventory_ui_open_test,
             args.original_screenshot_test,args.normal_open_use_current_ui_test,args.ui_current_frame_update_test,
             args.inventory_update_test,args.selected_slot_lookup_role_test,args.mark_on_current_indicator_test,
             args.hp_status_notify_only,args.hp_status_png_after_post,args.npc_player_hit_only,
             args.npc_player_hit_repeated_only,args.npc_approach_player_hit_only,
             args.player_death_recovery_only,args.npc_player_lethal_recovery_only,
             args.npc_respawn_only,args.npc_respawn_next_hit_only,args.npc_respawn_next_hit_remove_only,
             args.npc_second_respawn_only,args.npc_current_life_next_hit_only,args.npc_current_life_retire_only,
             args.npc_respawn_motion_only,args.npc_hp_death_only,args.npc_motion_goal_only,args.npc_motion_goal is not None)),
         'SCENARIO_NPC_HP_FEEDBACK_EXACT_CLI_REQUIRED')
    need(not (args.npc_player_lethal_recovery_only and args.player_death_recovery_only),
         'SCENARIO_NPC_LETHAL_EXCLUSIVE_LIFE_CLI_REQUIRED')
    if args.npc_player_lethal_recovery_only: args.player_death_recovery_only = True
    need(not args.item_transfer_ui_test or args.background and args.source_quit_test
         and args.inventory_auto_test and args.feature_config is not None and args.idle_seconds == 0
         and not any((args.source_restart_test,args.source_reselect_test,args.reselect_inventory_only,
             args.item_equipment_swap_reselect_test,args.item_equipment_swap_saved_b_tail_test,
             args.item_equipment_zero_use_reselect_test,args.reselect_equipment_ui_restore_test,
             args.use_item_test,args.use_item_only,args.use_item_effect_test,args.use_item_ui_observe_test,
             args.inventory_ui_open_test,args.original_screenshot_test,args.normal_open_use_current_ui_test,
             args.ui_current_frame_update_test,args.inventory_update_test,args.selected_slot_lookup_role_test,
             args.mark_on_current_indicator_test,args.retain_move_goal,args.confirm_window_close,
             args.npc_respawn_only,args.npc_respawn_next_hit_only,args.npc_respawn_next_hit_remove_only,
             args.npc_second_respawn_only,args.npc_current_life_next_hit_only,args.npc_current_life_retire_only,
             args.npc_respawn_motion_only,args.npc_hp_death_only,args.npc_motion_goal_only,
             args.npc_motion_goal is not None)), 'SCENARIO_TRANSFER_EXACT_CLI_REQUIRED')
    if args.hp_status_png_after_post or args.npc_player_hit_only or args.npc_player_hit_repeated_only or args.npc_approach_player_hit_only:
        args.hp_status_notify_only=True
    need(not args.item_equipment_zero_use_reselect_test or args.item_equipment_swap_reselect_test,
         'SCENARIO_ZERO_USE_RESELECT_REQUIRES_SWAP_TEST')
    need(not (args.item_equipment_zero_use_reselect_test and args.item_equipment_swap_saved_b_tail_test),
         'SCENARIO_ZERO_USE_RESELECT_EXCLUSIVE_REQUIRED')
    need(not args.item_equipment_swap_saved_b_tail_test or args.item_equipment_swap_reselect_test,
         'SCENARIO_SWAP_SAVED_B_TAIL_REQUIRES_SWAP_TEST')
    need(not args.item_equipment_swap_reselect_test or args.background and args.inventory_auto_test
         and args.source_quit_test and args.source_restart_test and args.source_reselect_test
         and args.reselect_inventory_only and args.feature_config is not None and args.idle_seconds == 0
         and not any((args.hp_status_notify_only, args.reselect_equipment_ui_restore_test, args.attack_target_test,
             args.continuous_move_test, args.use_item_test, args.use_item_only, args.use_item_effect_test,
             args.use_item_ui_observe_test, args.inventory_ui_open_test, args.normal_open_use_current_ui_test,
             args.original_screenshot_test, args.ui_current_frame_update_test, args.inventory_update_test,
             args.selected_slot_lookup_role_test, args.mark_on_current_indicator_test, args.npc_respawn_only,
             args.npc_respawn_next_hit_only, args.npc_respawn_next_hit_remove_only, args.npc_second_respawn_only,
             args.npc_current_life_next_hit_only, args.npc_current_life_retire_only, args.npc_respawn_motion_only,
             args.npc_hp_death_only, args.npc_motion_goal_only, args.npc_motion_goal is not None,
             args.retain_move_goal, args.confirm_window_close)), 'SCENARIO_SWAP_EXCLUSIVE_CONFIGURATION_REQUIRED')
    need(not args.player_death_recovery_only or args.background and args.source_quit_test
         and args.inventory_add_test and not args.inventory_auto_test and args.feature_config is not None
         and args.idle_seconds == 0 and not any((args.attack_target_test,args.continuous_move_test,
             args.hp_status_notify_only,args.npc_player_hit_only,args.npc_player_hit_repeated_only,
             args.npc_approach_player_hit_only,args.source_restart_test,args.source_reselect_test,
             args.inventory_update_test,args.use_item_test,args.ui_current_frame_update_test,
             args.inventory_ui_open_test,args.original_screenshot_test,args.normal_open_use_current_ui_test,
             args.reselect_equipment_ui_restore_test,args.item_equipment_swap_reselect_test)),
         'SCENARIO_PLAYER_LIFE_EXPLICIT_PREPARATION_MODE_REQUIRED')
    need(not args.hp_status_notify_only or args.background and args.source_quit_test
         and args.inventory_auto_test and args.feature_config is not None
         and not any((args.attack_target_test,args.continuous_move_test,args.inventory_add_test,
             args.npc_respawn_only,args.npc_respawn_next_hit_only,args.npc_respawn_next_hit_remove_only,
             args.npc_second_respawn_only,args.npc_current_life_next_hit_only,args.npc_current_life_retire_only,
             args.npc_respawn_motion_only,args.npc_hp_death_only,args.npc_motion_goal_only,args.npc_motion_goal is not None,
             args.source_restart_test,args.source_reselect_test,args.reselect_inventory_only,args.use_item_test,
             args.use_item_only,args.use_item_effect_test,args.use_item_ui_observe_test,args.inventory_update_test,
             args.ui_current_frame_update_test,args.inventory_ui_open_test,args.selected_slot_lookup_role_test,
             args.normal_open_use_current_ui_test,args.original_screenshot_test,args.mark_on_current_indicator_test,
             args.retain_move_goal,args.confirm_window_close)),
         'SCENARIO_HP_STATUS_EXCLUSIVE_CONFIGURATION_REQUIRED')
    need(not args.original_screenshot_test or args.background and args.inventory_auto_test and args.source_quit_test, 'SCENARIO_SCREENSHOT_BACKGROUND_SAVED_QUIT_REQUIRED')
    need(not args.mark_on_current_indicator_test or args.normal_open_use_current_ui_test, 'SCENARIO_MARK_ON_EXPLICIT_PARENT_REQUIRED')
    need(not args.selected_slot_lookup_role_test or (args.inventory_ui_open_test or args.original_screenshot_test),
         'SCENARIO_UI_ROLE_EXPLICIT_OPEN_MODE_REQUIRED')
    need(sum((args.npc_respawn_only,args.npc_respawn_next_hit_only,args.npc_respawn_next_hit_remove_only,args.npc_second_respawn_only,args.npc_current_life_next_hit_only,args.npc_current_life_retire_only,args.npc_respawn_motion_only)) <= 1,
         'SCENARIO_RESPAWN_HIT_EXCLUSIVE_MODE_REQUIRED')
    current_life_hit_mode = args.npc_current_life_next_hit_only or args.npc_current_life_retire_only
    second_respawn_mode = args.npc_second_respawn_only or current_life_hit_mode
    retire_mode = args.npc_respawn_next_hit_remove_only or second_respawn_mode
    next_hit_mode = args.npc_respawn_next_hit_only or retire_mode
    respawn_mode = args.npc_respawn_only or args.npc_respawn_motion_only or next_hit_mode
    need(not args.normal_open_use_current_ui_test or args.background and args.inventory_auto_test
         and args.source_quit_test and args.feature_config is not None
         and not any((args.attack_target_test, args.continuous_move_test, args.use_item_only,
             args.use_item_effect_test, args.use_item_ui_observe_test, args.selected_slot_lookup_role_test,
             args.source_reselect_test, args.reselect_inventory_only, args.retain_move_goal, args.confirm_window_close,
             args.npc_hp_death_only, args.npc_motion_goal_only, args.npc_motion_goal is not None)),
         'SCENARIO_NORMAL_OPEN_USE_EXCLUSIVE_CONFIGURATION_REQUIRED')
    need(not args.reselect_equipment_ui_restore_test or args.background and args.inventory_auto_test
         and args.source_quit_test and args.source_restart_test and args.source_reselect_test
         and args.reselect_inventory_only and args.feature_config is not None
         and args.idle_seconds == 0 and not any((args.hp_status_notify_only, args.attack_target_test, args.continuous_move_test,
             args.use_item_test, args.use_item_only, args.use_item_effect_test, args.use_item_ui_observe_test,
             args.inventory_ui_open_test, args.normal_open_use_current_ui_test, args.original_screenshot_test,
             args.ui_current_frame_update_test, args.inventory_update_test, args.selected_slot_lookup_role_test,
             args.mark_on_current_indicator_test, respawn_mode, args.npc_hp_death_only, args.npc_motion_goal_only,
             args.npc_motion_goal is not None, args.retain_move_goal, args.confirm_window_close)),
         'SCENARIO_RESELECT_EQUIPMENT_EXCLUSIVE_CONFIGURATION_REQUIRED')
    inventory_test = args.inventory_add_test or args.inventory_auto_test
    need(not args.inventory_ui_open_test or args.background and args.inventory_auto_test
         and args.source_quit_test and args.feature_config is not None
         and not any((args.continuous_move_test, args.attack_target_test, respawn_mode,
             args.npc_hp_death_only, args.npc_motion_goal_only, args.npc_motion_goal is not None,
             args.use_item_only, args.use_item_effect_test, args.use_item_ui_observe_test,
             args.source_reselect_test, args.reselect_inventory_only, args.retain_move_goal, args.confirm_window_close)),
         'SCENARIO_INVENTORY_OPEN_EXCLUSIVE_BACKGROUND_REQUIRED')
    need(not respawn_mode or args.background and args.attack_target_test
         and args.inventory_auto_test and args.source_quit_test and args.feature_config is not None
         and not any((args.continuous_move_test, args.npc_hp_death_only, args.npc_motion_goal_only,
             args.npc_motion_goal is not None and not args.npc_respawn_motion_only, args.use_item_test, args.use_item_only,
             args.use_item_effect_test, args.use_item_ui_observe_test, args.ui_current_frame_update_test,
             args.inventory_update_test, args.source_restart_test, args.source_reselect_test,
             args.reselect_inventory_only, args.retain_move_goal, args.confirm_window_close)),
         'SCENARIO_NPC_RESPAWN_EXCLUSIVE_PREPARED_SOURCE_QUIT_REQUIRED')
    need(not args.ui_current_frame_update_test or args.background and args.inventory_auto_test
         and args.source_quit_test and args.feature_config is not None
         and not any((args.continuous_move_test, args.attack_target_test, args.npc_hp_death_only,
             args.npc_motion_goal_only, args.use_item_only, args.use_item_effect_test, args.use_item_ui_observe_test,
             args.source_reselect_test, args.reselect_inventory_only, args.retain_move_goal, args.confirm_window_close)),
         'SCENARIO_UI_UPDATE_EXCLUSIVE_BACKGROUND_SOURCE_QUIT_REQUIRED')
    need(not args.npc_motion_goal_only or args.background and args.attack_target_test
         and args.inventory_auto_test and args.source_quit_test and args.feature_config is not None
         and args.npc_motion_goal is not None
         and not any((args.npc_hp_death_only, args.use_item_test, args.inventory_update_test,
                      args.source_restart_test, args.source_reselect_test, args.retain_move_goal, args.confirm_window_close)),
         'SCENARIO_NPC_MOTION_FOCUSED_EXCLUSIVE_SOURCE_QUIT_REQUIRED')
    need(args.npc_motion_goal is None or args.npc_motion_goal_only or args.npc_respawn_motion_only,
         'SCENARIO_NPC_MOTION_GOAL_REQUIRES_FOCUSED_MODE')
    need(not args.npc_respawn_motion_only or args.npc_motion_goal == [32578, 32946],
         'SCENARIO_RESPAWN_MOTION_EXPLICIT_GOAL_REQUIRED')
    if args.npc_motion_goal is not None:
        from tools.local_original_session.npc_motion_focused import grid
        need(grid(args.npc_motion_goal) is not None, 'SCENARIO_NPC_MOTION_EXPLICIT_GOAL_REQUIRED')
    need(not args.npc_dead_goal_only or args.npc_hp_death_only and args.background
         and args.attack_target_test and args.inventory_auto_test and args.source_quit_test
         and args.feature_config is not None and args.idle_seconds == 0
         and not any((respawn_mode, args.npc_motion_goal_only, args.npc_motion_goal is not None,
             args.npc_hp_feedback_only, args.hp_status_notify_only, args.player_death_recovery_only,
             args.npc_approach_player_hit_only, args.continuous_move_test,
             args.observe_hp4ec8_subscribers_once, args.use_item_test, args.inventory_update_test,
             args.source_restart_test, args.source_reselect_test, args.retain_move_goal,
             args.confirm_window_close, args.item_transfer_ui_test,
             args.item_equipment_swap_reselect_test, args.normal_open_use_current_ui_test,
             args.inventory_ui_open_test, args.original_screenshot_test)),
         'SCENARIO_DEAD_GOAL_EXCLUSIVE_PREPARED_SOURCE_QUIT_REQUIRED')
    need(not args.npc_hp_death_only or args.background and args.attack_target_test
         and args.inventory_auto_test and args.source_quit_test and args.feature_config is not None
         and not any((args.use_item_test, args.inventory_update_test, args.source_restart_test,
                      args.source_reselect_test, args.retain_move_goal, args.confirm_window_close)),
         'SCENARIO_NPC_FOCUSED_EXCLUSIVE_PREPARED_SOURCE_QUIT_REQUIRED')
    need(not args.use_item_ui_observe_test or args.use_item_effect_test and args.use_item_only,
         'SCENARIO_USE_ITEM_UI_OBSERVE_EFFECT_FOCUSED_REQUIRED')
    need(not args.use_item_effect_test or args.use_item_only,
         'SCENARIO_USE_ITEM_EFFECT_FOCUSED_REQUIRED')
    need(not args.use_item_only or args.use_item_test,
         'SCENARIO_USE_ITEM_ONLY_REQUIRES_USE_ITEM')
    need(not args.reselect_inventory_only or args.source_reselect_test,
         'SCENARIO_RESELECT_INVENTORY_ONLY_REQUIRES_RESELECT')
    need(not args.source_reselect_test or args.source_restart_test and args.source_quit_test,
         'SCENARIO_RESELECT_RESTART_SOURCE_QUIT_REQUIRED')
    need(not args.source_restart_test or args.background and args.inventory_auto_test and (args.attack_target_test or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test)
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
    need(not args.source_quit_test or args.background and (args.attack_target_test or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.hp_status_notify_only or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test or args.item_transfer_ui_test or args.player_death_recovery_only)
         and inventory_test and args.feature_config is not None,
         'SCENARIO_SOURCE_QUIT_FEATURE_CONFIG_REQUIRED')
    need(not (args.source_quit_test and args.confirm_window_close), 'SOURCE_QUIT_EXCLUSIVE_CLOSE_TRIAL_REQUIRED')
    need(not inventory_test or (args.attack_target_test or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.hp_status_notify_only or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test or args.item_transfer_ui_test or args.player_death_recovery_only) and args.background
         and args.feature_config is not None, 'SCENARIO_INVENTORY_ATTACK_BACKGROUND_CONFIG_REQUIRED')
    need(args.run_name.replace('-', '').isalnum(), 'FRESH_BASELINE_RUN_NAME_REQUIRED')
    focused = args.npc_hp_feedback_only or respawn_mode or args.reselect_inventory_only or args.use_item_only or args.npc_hp_death_only or args.npc_motion_goal_only or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.hp_status_notify_only or args.item_transfer_ui_test or args.player_death_recovery_only
    need((60 <= args.idle_seconds <= 120 or focused and args.idle_seconds == 0)
         and 120 <= args.tool_timeout_seconds <= 300,
         'BOUNDED_TOOL_OBSERVATION_REQUIRED')
    if focused:
        args.idle_seconds = 0  # This explicit mode requests no world hold.
    product, profile = selected_profile(args.continuous_move_test, args.background,
        attack=args.attack_target_test, source_quit=args.source_quit_test, use_item=args.use_item_test,
        inventory_update=args.inventory_update_test, source_restart=args.source_restart_test, source_reselect=args.source_reselect_test,
        use_item_ui_observe=args.use_item_ui_observe_test, ui_current_frame_update=args.ui_current_frame_update_test, npc_respawn=args.npc_respawn_only or args.npc_respawn_motion_only, inventory_ui_open=args.inventory_ui_open_test, selected_slot_lookup_role=args.selected_slot_lookup_role_test, npc_respawn_next_hit=next_hit_mode, normal_open_use_ui=args.normal_open_use_current_ui_test, original_screenshot=args.original_screenshot_test, mark_on=args.mark_on_current_indicator_test, hp_status_notify=args.hp_status_notify_only, hp_status_png=args.hp_status_png_after_post, npc_player_hit=args.npc_player_hit_only, npc_player_hit_repeated=args.npc_player_hit_repeated_only, npc_approach_hit=args.npc_approach_player_hit_only, reselect_equipment_restore=args.reselect_equipment_ui_restore_test, collection_swap=args.item_equipment_swap_reselect_test, collection_swap_saved_b_tail=args.item_equipment_swap_saved_b_tail_test, collection_swap_zero_use=args.item_equipment_zero_use_reselect_test, item_transfer_ui=args.item_transfer_ui_test, player_death_recovery=args.player_death_recovery_only, npc_player_lethal_recovery=args.npc_player_lethal_recovery_only)
    need(not (args.continuous_move_test and args.confirm_window_close),
         'NO_QUIT_ENTER_TRIAL_IN_CONTINUOUS_RUN')
    need(args.feature_config is None or args.attack_target_test or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.hp_status_notify_only or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test or args.item_transfer_ui_test or args.player_death_recovery_only, 'SCENARIO_FEATURE_CONFIG_REQUIRES_ATTACK_TEST')
    expected_features = None
    if args.attack_target_test or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.hp_status_notify_only or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test or args.item_transfer_ui_test or args.player_death_recovery_only:
        need(args.feature_config is not None, 'SCENARIO_ATTACK_FEATURE_CONFIG_REQUIRED')
        from tools.local_original_session.feature_config import load
        from tools.local_original_session.item_equipment_reselect_restore import configuration as restore_configuration
        from tools.local_original_session.item_equipment_swap import configuration as swap_configuration
        from tools.local_original_session.item_transfer_runner import configuration as transfer_configuration
        validator = npc_dead_goal_configuration if args.npc_dead_goal_only else npc_player_lethal_recovery_configuration if args.npc_player_lethal_recovery_only else player_death_recovery_configuration if args.player_death_recovery_only else transfer_configuration if args.item_transfer_ui_test else npc_approach_hit_configuration if args.npc_approach_player_hit_only else npc_player_hit_repeated_configuration if args.npc_player_hit_repeated_only else npc_player_hit_configuration if args.npc_player_hit_only else swap_configuration if args.item_equipment_swap_reselect_test else restore_configuration if args.reselect_equipment_ui_restore_test else hp_status_png_configuration if args.hp_status_png_after_post else hp_status_configuration if args.hp_status_notify_only else OriginalScreenshotScenario.configuration if args.original_screenshot_test else NormalOpenUseCurrentUIScenario.configuration if args.normal_open_use_current_ui_test else InventoryUIOpenScenario.configuration if args.inventory_ui_open_test else npc_respawn_configuration if respawn_mode else InventoryUIFrameUpdateScenario.configuration if args.ui_current_frame_update_test else npc_motion_configuration if args.npc_motion_goal_only else npc_hp_feedback_configuration if args.npc_hp_feedback_only else attack_configuration
        expected_features = validator(load(args.feature_config), inventory=inventory_test,
                                                 auto_inventory=args.inventory_auto_test)
        need(args.hp_status_notify_only or expected_features.hp_status_policy is None and expected_features.hp_status_input is None,
             'SCENARIO_HP_STATUS_EXPLICIT_FLAG_REQUIRED')
        if args.npc_hp_death_only:
            from tools.local_original_session.npc_combat_focused import configuration
            configuration(expected_features)
        if args.use_item_test:
            from tools.local_original_session.item_use_session import POLICY
            need(expected_features.item_use_policy == POLICY, 'SCENARIO_USE_ITEM_POLICY_REQUIRED')
            if args.use_item_effect_test:
                from tools.local_original_session.item_equipment_effect import POLICY as EFFECT_POLICY
                need(expected_features.item_equipment_policy == EFFECT_POLICY,
                     'SCENARIO_USE_ITEM_EFFECT_POLICY_REQUIRED')
            else:
                need(expected_features.item_equipment_policy is None,
                     'SCENARIO_USE_ITEM_EFFECT_OPT_IN_REQUIRED')
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
        scenario_type = NpcHpFeedbackOnlyScenario if args.npc_hp_feedback_only else NpcPlayerLethalRecoveryScenario if args.npc_player_lethal_recovery_only else PlayerDeathRecoveryScenario if args.player_death_recovery_only else ItemTransferScenario if args.item_transfer_ui_test else NpcApproachHitScenario if args.npc_approach_player_hit_only else NpcPlayerHitRepeatedScenario if args.npc_player_hit_repeated_only else NpcPlayerHitScenario if args.npc_player_hit_only else HpStatusPngScenario if args.hp_status_png_after_post else HpStatusNotifyScenario if args.hp_status_notify_only else OriginalScreenshotScenario if args.original_screenshot_test else NormalOpenUseMarkOnScenario if args.mark_on_current_indicator_test else NormalOpenUseCurrentUIScenario if args.normal_open_use_current_ui_test else InventoryUILookupRoleScenario if args.selected_slot_lookup_role_test else InventoryUIOpenScenario if args.inventory_ui_open_test else NpcRespawnMotionScenario if args.npc_respawn_motion_only else NpcCurrentLifeRetireScenario if args.npc_current_life_retire_only else NpcCurrentLifeNextHitScenario if args.npc_current_life_next_hit_only else NpcSecondRespawnScenario if args.npc_second_respawn_only else NpcRespawnNextHitRemoveScenario if args.npc_respawn_next_hit_remove_only else NpcRespawnNextHitScenario if args.npc_respawn_next_hit_only else NpcRespawnScenario if args.npc_respawn_only else InventoryUIFrameUpdateScenario if args.ui_current_frame_update_test else NpcMotionGoalScenario if args.npc_motion_goal_only else NpcDeadGoalScenario if args.npc_dead_goal_only else NpcHpDeathScenario if args.npc_hp_death_only else SourceReselectScenario if args.source_reselect_test else SourceRestartScenario if args.source_restart_test else InventoryUpdateScenario if args.inventory_update_test else UseItemScenario if args.use_item_test else InventoryAutoScenario if args.inventory_auto_test else InventoryAddScenario if args.inventory_add_test else AttackTargetScenario if args.attack_target_test else ContinuousMoveScenario if args.continuous_move_test else Scenario
        feature_options = {}
        if args.npc_motion_goal_only:
            feature_options['npc_motion_goal'] = tuple(args.npc_motion_goal)
        if args.npc_respawn_motion_only:
            feature_options['npc_respawn_motion_goal'] = tuple(args.npc_motion_goal)
        if args.use_item_test:
            feature_options['use_item_only'] = args.use_item_only
            if args.use_item_effect_test:
                feature_options['use_item_effect'] = True
            if args.use_item_ui_observe_test:
                feature_options['use_item_ui_observe'] = True
        if args.source_reselect_test:
            feature_options['inventory_only'] = args.reselect_inventory_only
            if args.item_equipment_swap_reselect_test:
                feature_options['collection_swap'] = True
                if args.item_equipment_swap_saved_b_tail_test:
                    feature_options['collection_swap_saved_b_tail'] = True
                if args.item_equipment_zero_use_reselect_test:
                    feature_options['collection_swap_zero_use'] = True
            if args.reselect_equipment_ui_restore_test:
                feature_options['equipment_restore'] = True
        if args.continuous_move_test or args.attack_target_test:
            feature_options['retain_move_goal'] = args.retain_move_goal
        if args.attack_target_test or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.hp_status_notify_only or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test or args.item_transfer_ui_test or args.player_death_recovery_only:
            actual_features = getattr(kwargs.get('feature_factory'), 'config', None)
            need(actual_features == expected_features, 'SCENARIO_ATTACK_FEATURE_CONFIG_CHANGED')
            feature_options['features'] = actual_features
        if args.item_equipment_swap_reselect_test:
            source_feature_factory = kwargs.get('feature_factory')
            need(type(source_feature_factory) is launcher.ProductFeatureFactory
                 and source_feature_factory.swap_saved_b_tail is args.item_equipment_swap_saved_b_tail_test
                 and source_feature_factory.zero_use_reselect is args.item_equipment_zero_use_reselect_test,
                 'SCENARIO_SWAP_SAVED_B_TAIL_FACTORY_POLICY_CHANGED')
        scenario, tick = scenario_type(owner, monitor, stop, args.idle_seconds,
                                  background=args.background,
                                  source_quit_test=args.source_quit_test,
                                  confirm_window_close=args.confirm_window_close, **feature_options), monitor.tick
        if args.player_death_recovery_only:
            life_source_factory=kwargs['feature_factory']
            def capture_player_life_features(broker):
                runtime_type = NpcPlayerLethalRecoveryRuntime if args.npc_player_lethal_recovery_only else PlayerDeathRecoveryRuntime
                return runtime_type(life_source_factory(broker),scenario,broker)
            kwargs['feature_factory']=capture_player_life_features
        if args.hp_status_notify_only:
            hp_source_factory=kwargs['feature_factory']
            def capture_hp_status_features(broker):
                runtime_type = NpcApproachHitRuntime if args.npc_approach_player_hit_only else NpcPlayerHitRepeatedRuntime if args.npc_player_hit_repeated_only else NpcPlayerHitRuntime if args.npc_player_hit_only else HpStatusRuntime
                return runtime_type(hp_source_factory(broker),scenario,broker)
            kwargs['feature_factory']=capture_hp_status_features
        if respawn_mode:
            source_factory = kwargs['feature_factory']
            def capture_npc_respawn_features(broker):
                from tools.local_original_session.npc_respawn_focused import Runtime
                return Runtime(source_factory(broker), scenario, next_hit=next_hit_mode, retire=retire_mode, second_respawn=second_respawn_mode,current_life_hit=current_life_hit_mode,current_life_retire=args.npc_current_life_retire_only, motion_goal=(scenario.npc_respawn_motion_goal if args.npc_respawn_motion_only else None))
            kwargs['feature_factory'] = capture_npc_respawn_features
        if args.npc_hp_death_only:
            source_factory = kwargs['feature_factory']
            def capture_npc_features(broker):
                if args.npc_dead_goal_only:
                    from tools.local_original_session.npc_dead_goal_focused import Runtime
                else:
                    from tools.local_original_session.npc_combat_focused import Runtime
                return Runtime(source_factory(broker), scenario)
            kwargs['feature_factory'] = capture_npc_features
        if args.npc_motion_goal_only:
            source_factory = kwargs['feature_factory']
            def capture_npc_motion_features(broker):
                from tools.local_original_session.npc_motion_focused import Runtime
                return Runtime(source_factory(broker), scenario, goal=scenario.npc_motion_goal)
            kwargs['feature_factory'] = capture_npc_motion_features
        if args.npc_hp_feedback_only or args.source_restart_test or args.use_item_effect_test or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test:
            source_factory = kwargs['feature_factory']
            def capture_features(broker):
                runtime = source_factory(broker)
                scenario.bind_runtime(runtime)
                return runtime
            kwargs['feature_factory'] = capture_features
        if args.item_transfer_ui_test:
            source_transfer_factory = kwargs['feature_factory']
            need(type(source_transfer_factory) is launcher.ProductFeatureFactory
                 and source_transfer_factory.item_transfer_ui is True
                 and source_transfer_factory._transfer_ui_configured(),
                 'SCENARIO_TRANSFER_ACTUAL_FACTORY_REQUIRED')
            def capture_transfer_features(broker):
                from tools.local_original_session.item_transfer_runner import Runtime
                return Runtime(source_transfer_factory(broker), scenario, broker)
            kwargs['feature_factory'] = capture_transfer_features
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
            if args.player_death_recovery_only:
                quit_report=report.get('source_quit')
                scenario.life_status['quit']=(None if type(quit_report) is not dict else
                    {key:quit_report.get(key) for key in ('status','reason','normal_exit_verified')})
            if args.attack_target_test or args.ui_current_frame_update_test or (args.inventory_ui_open_test or args.original_screenshot_test) or args.normal_open_use_current_ui_test or args.hp_status_notify_only or args.reselect_equipment_ui_restore_test or args.item_equipment_swap_reselect_test or args.item_transfer_ui_test or args.player_death_recovery_only:
                scenario.finalize()
            report['normal_input_only'] = False
            report['manual_baseline_scenario'] = scenario.summary()
            scenario.save()
            summary = report['manual_baseline_scenario']
            scenario_failed = (summary.get('error') is not None
                or focused and not args.npc_hp_feedback_only and not args.npc_hp_death_only and not respawn_mode and (summary.get('attack_target', {}).get('status') != 'NOT_REQUESTED'
                    or summary.get('continuous_moves') != [] or summary.get('idle_hold_complete') is not False)
                or not focused and summary.get('idle_hold_complete') is not True
                or not focused and (args.continuous_move_test or args.attack_target_test)
                    and summary.get('continuous_moves_complete') is not True
                or not focused and args.attack_target_test and summary.get('attack_target', {}).get('status') != 'COMMITTED'
                or inventory_test and summary.get('inventory_add', {}).get('status') != 'COMMITTED'
                or args.npc_hp_feedback_only and (summary.get('npc_hp_feedback_only',{}).get('status') != 'COMMITTED'
                    or summary.get('attack_target',{}).get('status') != 'COMMITTED'
                    or summary.get('continuous_moves') != [] or summary.get('idle_hold_complete') is not False
                    or report.get('normal_exit_verified') is not True)
                or respawn_mode and (summary.get('attack_target', {}).get('status') != 'PREPARED'
                    or summary.get('attack_target', {}).get('phase') != 'LETHAL_PREPARATION_READY'
                    or summary.get('attack_target', {}).get('proof_scope') != 'CURRENT_LETHAL_NPC_DEATH_DRAIN_ONLY'
                    or summary.get('npc_respawn', {}).get('status') != 'COMMITTED'
                    or summary.get('continuous_moves') != [] or summary.get('idle_hold_complete') is not False
                    or report.get('normal_exit_verified') is not True)
                or next_hit_mode and summary.get('npc_respawn_next_hit', {}).get('status') != 'COMMITTED'
                or retire_mode and summary.get('npc_respawn_next_hit_remove', {}).get('status') != 'COMMITTED'
                or second_respawn_mode and summary.get('npc_second_respawn', {}).get('status') != 'COMMITTED'
                or current_life_hit_mode and summary.get('npc_current_life_next_hit', {}).get('status') != 'COMMITTED'
                or args.npc_current_life_retire_only and summary.get('npc_current_life_retire', {}).get('status') != 'COMMITTED'
                or args.npc_respawn_motion_only and summary.get('npc_respawn_motion', {}).get('status') != 'COMMITTED'
                or args.player_death_recovery_only and (summary.get('player_death_recovery',{}).get('status')!='COMMITTED'
                    or report.get('normal_exit_verified') is not True)
                or args.hp_status_notify_only and not args.npc_approach_player_hit_only and (summary.get('hp_status_notify',{}).get('status')!='COMMITTED'
                    or (args.npc_player_hit_only or args.npc_player_hit_repeated_only or args.npc_approach_player_hit_only or expected_features.hp_status_input.observe_hud_bar)
                        and summary.get('hp_status_notify',{}).get('hud_bar',{}).get('status')!='MODEL_MATCHED'
                    or report.get('normal_exit_verified') is not True)
                or args.npc_player_hit_only and summary.get('npc_player_hit',{}).get('status') != 'COMMITTED'
                or args.npc_player_hit_repeated_only and summary.get('npc_player_hit_repeated',{}).get('status') != 'COMMITTED'
                or args.npc_approach_player_hit_only and (summary.get('npc_approach_hit',{}).get('status') != 'COMMITTED'
                    or summary.get('npc_approach_hit',{}).get('numeric_status') != 'COMMITTED'
                    or summary.get('npc_approach_hit',{}).get('hud_bar',{}).get('status') != 'MODEL_MATCHED'
                    or report.get('normal_exit_verified') is not True)
                or args.npc_hp_death_only and (summary.get('attack_target', {}).get('status') != 'COMMITTED'
                    or summary.get('npc_hp_death', {}).get('status') != 'COMMITTED'
                    or summary.get('continuous_moves') != [] or summary.get('idle_hold_complete') is not False
                    or report.get('normal_exit_verified') is not True)
                or args.npc_motion_goal_only and (summary.get('npc_motion_goal', {}).get('status') != 'COMMITTED'
                    or report.get('normal_exit_verified') is not True)
                or args.original_screenshot_test and (summary.get('original_screenshot', {}).get('status') != 'OBSERVED' or report.get('normal_exit_verified') is not True)
                or args.hp_status_png_after_post and (summary.get('original_screenshot',{}).get('status')!='OBSERVED'
                    or summary.get('original_screenshot',{}).get('png_verified') is not True)
                or args.mark_on_current_indicator_test and summary.get('mark_on_current_indicator', {}).get('status') != 'OBSERVED'
                or args.normal_open_use_current_ui_test and (summary.get('normal_open_use_current_ui', {}).get('status') != 'OBSERVED'
                    or summary.get('normal_open_use_current_ui', {}).get('effect_status') != 'COMMITTED')
                or args.inventory_ui_open_test and summary.get('inventory_ui_open', {}).get('status') != 'OBSERVED'
                or args.selected_slot_lookup_role_test and summary.get('selected_slot_lookup_role', {}).get('status') != 'OBSERVED'
                or args.use_item_test and summary.get('use_item', {}).get('status') != 'COMMITTED'
                or args.use_item_effect_test and summary.get('use_item_effect', {}).get('status') != 'COMMITTED'
                or args.use_item_ui_observe_test and summary.get('use_item_ui', {}).get('status') != 'OBSERVED'
                or args.ui_current_frame_update_test and (summary.get('ui_frame_update', {}).get('status') != 'OBSERVED'
                    or summary.get('inventory_update', {}).get('status') != 'COMMITTED')
                or args.inventory_update_test and summary.get('inventory_update', {}).get('status') != 'COMMITTED'
                or args.item_transfer_ui_test and (summary.get('item_transfer_ui', {}).get('status') != 'COMPLETE'
                    or report.get('normal_exit_verified') is not True)
                or args.item_equipment_swap_reselect_test and (summary.get('item_equipment_swap', {}).get('status') != 'OBSERVED'
                    or report.get('normal_exit_verified') is not True)
                or args.reselect_equipment_ui_restore_test and (summary.get('reselect_equipment_restore', {}).get('status') != 'OBSERVED'
                    or report.get('normal_exit_verified') is not True)
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
    if args.hp4ec8_observation_stage is not None:
        sys.argv.extend(['--hp4ec8-observation-stage', args.hp4ec8_observation_stage])
    if args.npc_dead_goal_only:
        sys.argv.append('--npc-dead-goal-only')
    if args.npc_hp_feedback_only:
        sys.argv.append('--npc-hp-feedback-only')
    if args.observe_hp4ec8_subscribers_once:
        sys.argv.append('--observe-hp4ec8-subscribers-once')
    if args.item_transfer_ui_test:
        sys.argv.append('--item-transfer-ui-test')
    if args.background:
        sys.argv.append('--background')
    if args.source_quit_test:
        sys.argv.append('--source-quit-test')
    if args.item_equipment_swap_saved_b_tail_test:
        sys.argv.append('--item-equipment-swap-saved-b-tail-test')
    if args.item_equipment_zero_use_reselect_test:
        sys.argv.append('--item-equipment-zero-use-reselect-test')
    if args.feature_config is not None:
        sys.argv.extend(('--feature-config', str(args.feature_config)))
    try:
        code = launcher.main()
        return 2 if scenario_failed else code
    finally: launcher.run_session, sys.argv = original, old_argv


if __name__ == '__main__': raise SystemExit(main())
