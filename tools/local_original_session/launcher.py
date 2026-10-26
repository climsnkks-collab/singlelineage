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
from types import MethodType, SimpleNamespace

_MANUAL_REJECTION_SOURCE_SHA = '25e86cb8741ffeac9a7560d08b6f15a9302f109cf17ea8627d8d7f552086655d'
_INVENTORY_OBSERVER_SOURCE_SHA = 'b26765c2f20765966f7ebeb46968a1e77bed4f9e9b17e7aa0cacc106a9e29c6c'
_INVENTORY_INCOMPLETE_READS = frozenset(('RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE',
    'RECHECKED_SHARED_COUNT_FINAL_READBACK', 'RECHECKED_SHARED_COUNT_BOTH'))

from tools.local_original_session import observe as _root_anchor
ROOT = _root_anchor.ROOT
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
PRODUCTS['sibling-background-npc-respawn-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'npc_respawn_lifecycle': True,
}
PRODUCTS['sibling-background-npc-respawn-next-hit'] = {
    **PRODUCTS['sibling-background-npc-respawn-spawn'],
    'allow_respawn_attack': True,
    'bridges': {**PRODUCTS['sibling-background-npc-respawn-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                '85d2d5d9ba22b847940cc8d7675b5b7973eda8ce4793e477a176c2933fa8e5ca'},
    'bridge_artifact': ROOT / 'work/local_server_rea_20261016/daybreak_page_noaccess_handoff/designated-01a14ed2/'
                              'npc-code-anchor-gate/native/own-login-bridge-dg49.dll',
}
PRODUCTS['sibling-background-use-item-source-quit-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'bridges': {**PRODUCTS['sibling-background-source-quit-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                '3db49209c95708c7a6588f55f85a7657612cbd4a7d0a64dd0869258ea20abec3'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/source-use-ui-matched-slot-binding/integration/'
                              'own-login-bridge-dg49.dll',
    'manual_use_item': True,
}
PRODUCTS['sibling-background-item-equipment-ui-observe-spawn'] = {
    **PRODUCTS['sibling-background-use-item-source-quit-spawn'],
    'bridges': {**PRODUCTS['sibling-background-use-item-source-quit-spawn']['bridges'],
                'own-login-bridge-dg49.dll':
                '0105f7104a0f36d833b85b27eb47d47d8c70c71bfeb2e666d9c8aed3dd7011f2'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-ui-observe/closed-ui-current-model/native/'
                              'own-login-bridge-dg49.dll',
    'item_equipment_ui_observe': True,
    'manual_use_item': False,
}
PRODUCTS['sibling-background-item-equipment-ui-update-spawn'] = {
    **PRODUCTS['sibling-background-item-equipment-ui-observe-spawn'],
    'manual_inventory_update': True,
    'continuous_manual_move': False,
    'continuous_manual_attack': False,
    'manual_attack_move_replacement': False,
}
PRODUCTS['sibling-background-inventory-ui-open-spawn'] = {
    **PRODUCTS['sibling-background-item-equipment-ui-observe-spawn'],
    'bridges': {**PRODUCTS['sibling-background-item-equipment-ui-observe-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '9492c5d281d0eb4e63b8cbd0b4d83fcda2833c8fb72b2ec0f45d239a6e0c0dc2'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-ui-observe/inventory-ui-open/native/own-login-bridge-dg49.dll',
    'inventory_ui_open': True,
    'manual_inventory_update': False,
    'continuous_manual_move': False,
    'continuous_manual_attack': False,
    'manual_attack_move_replacement': False,
}
PRODUCTS['sibling-background-inventory-ui-open-selected-slot-lookup-role-spawn'] = {
    **PRODUCTS['sibling-background-inventory-ui-open-spawn'],
    'bridges': {**PRODUCTS['sibling-background-inventory-ui-open-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '7eb6ebc5f363a19b5519af9e1392f1e34ec0113b41b13b42ed4eebc41de7b98c'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-ui-observe/inventory-ui-open/selected-slot-lookup-role/native/own-login-bridge-dg49.dll',
    'selected_slot_lookup_role': True,
}
PRODUCTS['sibling-background-normal-open-use-current-ui-spawn'] = {
    **PRODUCTS['sibling-background-inventory-ui-open-spawn'],
    'bridges': {**PRODUCTS['sibling-background-inventory-ui-open-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '6b308a2cbc37c135d8182bda0903911a1eab7667e0afdcd9e3f816b5cbf9dbe6'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-ui-observe/normal-open-use-current-ui/own-state-after-open/reported-own-phase/own-login-bridge-dg49.dll',
    'normal_open_use_current_ui': True,
    'manual_use_item': True,
    'use_item_already_open': True,
}
PRODUCTS['sibling-background-normal-open-use-mark-on-spawn'] = {
    **PRODUCTS['sibling-background-normal-open-use-current-ui-spawn'],
    'bridges': {**PRODUCTS['sibling-background-normal-open-use-current-ui-spawn']['bridges'],
        'own-login-bridge-dg49.dll': 'bbda56d51c26def3aca345126c4dfe1740eb29b0311c10d21eba9ec0693c0b6d'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-ui-observe/normal-open-use-current-ui/mark-on-current-indicator/receiver-bounded-observation/native/own-login-bridge-dg49.dll',
    'mark_on_current_indicator': True,
}
PRODUCTS['sibling-background-original-screenshot-spawn'] = {
    **PRODUCTS['sibling-background-inventory-ui-open-spawn'],
    'bridges': {**PRODUCTS['sibling-background-inventory-ui-open-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '5fdf05f2c38b17e2be8674ffb33a7ba0f3276fbad33d212a22d7aedd23d1ecf5'},
    'bridge_artifact': ROOT / 'work/local_server_rea_20261016/daybreak_page_noaccess_handoff/designated-01a14ed2/screenshot-direct-png-fallback/native/own-login-bridge-dg49.dll',
    'original_screenshot': True,
}
# Explicit HP numeric POST and independent PNG share the existing Native.
PRODUCTS['sibling-background-hp-status-png-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'bridges': dict(PRODUCTS['sibling-background-original-screenshot-spawn']['bridges']),
    'bridge_artifact': PRODUCTS['sibling-background-original-screenshot-spawn']['bridge_artifact'],
    'original_screenshot': True,
    'hp_status_png_after_post': True,
}
# One named local NPC hit; retains the proved background/Quit and Native.
PRODUCTS['sibling-background-npc-player-hit-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'bridges': dict(PRODUCTS['sibling-background-original-screenshot-spawn']['bridges']),
    'bridge_artifact': PRODUCTS['sibling-background-original-screenshot-spawn']['bridge_artifact'],
    'continuous_manual_attack': False,
    'manual_attack_move_replacement': False,
    'npc_player_hit': True,
}
PRODUCTS['sibling-background-npc-player-hit-repeated-spawn'] = {
    **PRODUCTS['sibling-background-npc-player-hit-spawn'],
    'npc_player_hit': False,
    'npc_player_hit_repeated': True,
}
PRODUCTS['sibling-background-npc-approach-player-hit-spawn'] = {
    **PRODUCTS['sibling-background-npc-player-hit-repeated-spawn'],
    'bridges': {**PRODUCTS['sibling-background-npc-player-hit-repeated-spawn']['bridges'],
        'own-login-bridge-dg49.dll': '6484117819571a32abe12391ce4af92bc13748d16cf0a4e1fd552901bc86ec7d'},
    'bridge_artifact': ROOT / 'work/local_server_rea_20261016/daybreak_page_noaccess_handoff/designated-01a14ed2/source-quit-guard-236/native/own-login-bridge-dg49.dll',
    'npc_player_hit_repeated': False,
    'npc_approach_hit': True,
}
PRODUCTS['sibling-background-player-death-recovery-spawn'] = {
    **PRODUCTS['sibling-background-npc-player-hit-spawn'],
    'bridges': {**PRODUCTS['sibling-background-npc-player-hit-spawn']['bridges'],
        'own-login-bridge-dg49.dll': 'a91192f93a46349ee4de977cfc08d37171126812b87bb6d7982bb37e60b8e5d5'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-2/combat-hp-death/player-death-recovery/native-dead-restart/native/own-login-bridge-dg49.dll',
    'npc_player_hit': False,
    'player_death_recovery': True,
    'continuous_manual_attack': False,
    'manual_attack_move_replacement': False,
}
PRODUCTS['sibling-background-npc-player-lethal-recovery-spawn'] = {
    **PRODUCTS['sibling-background-player-death-recovery-spawn'],
    'npc_player_lethal_recovery': True,
}
PRODUCTS['sibling-background-use-item-ui-observe-spawn'] = {
    **PRODUCTS['sibling-background-use-item-source-quit-spawn'],
    'bridges': dict(PRODUCTS['sibling-background-item-equipment-ui-observe-spawn']['bridges']),
    'bridge_artifact': PRODUCTS['sibling-background-item-equipment-ui-observe-spawn']['bridge_artifact'],
    'item_equipment_ui_observe': True,
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

PRODUCTS['sibling-background-item-equipment-reselect-restore-spawn'] = {
    **PRODUCTS['sibling-background-source-reselect-spawn'],
    'bridges': {**PRODUCTS['sibling-background-source-reselect-spawn']['bridges'],
        'own-login-bridge-dg49.dll': 'bbda56d51c26def3aca345126c4dfe1740eb29b0311c10d21eba9ec0693c0b6d'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-ui-observe/normal-open-use-current-ui/mark-on-current-indicator/receiver-bounded-observation/native/own-login-bridge-dg49.dll',
    'item_equipment_reselect_restore': True,
    'inventory_ui_open': True,
    'item_equipment_ui_observe': True,
    'require_source_quit': True,
    'continuous_manual_move': False,
    'continuous_manual_attack': False,
    'manual_attack_move_replacement': False,
    'manual_use_item': False,
    'manual_inventory_update': False,
}
PRODUCTS['sibling-background-item-equipment-swap-reselect-spawn'] = {
    **PRODUCTS['sibling-background-item-equipment-reselect-restore-spawn'],
    'item_equipment_reselect_restore': False,
    'item_equipment_swap_reselect': True,
    'manual_use_item': True,
    'use_item_already_open': True,
}
PRODUCTS['sibling-background-item-equipment-current-entry-tail-spawn'] = {
    **PRODUCTS['sibling-background-item-equipment-swap-reselect-spawn'],
    'bridges': {**PRODUCTS['sibling-background-item-equipment-swap-reselect-spawn']['bridges'],
        'own-login-bridge-dg49.dll': 'b8b6de58da73763384e24c4184535ca011a78029eead04ad2d2d9df765dea4ce'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-swap/current-entry/native/own-login-bridge-dg49.dll',
    'use_item_already_open': False,
    'use_item_current_entry': True,
}
PRODUCTS['sibling-background-item-equipment-zero-use-reselect-spawn'] = {
    **PRODUCTS['sibling-background-item-equipment-current-entry-tail-spawn'],
    'bridges': {**PRODUCTS['sibling-background-item-equipment-current-entry-tail-spawn']['bridges'],
        'own-login-bridge-dg49.dll': 'ff5e1dc82de3bdb19bed5c4f48851fefed1c2e101dffa9decfa0ba2fa6c7d5f1'},
    'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-swap/actual232-followup/reselect-open/native/own-login-bridge-dg49.dll',
    'manual_use_item': False,
    'use_item_already_open': False,
    'use_item_current_entry': False,
    'item_equipment_zero_use_reselect': True,
}
# Explicit additive Native closure; old descriptors keep independent pins.
ITEM_TRANSFER_UI_DLL_SHA = '9c4fc7a0c45e86df38502b59f2622df84cc29c071fa086129541b0471aeddf20'
if ITEM_TRANSFER_UI_DLL_SHA is not None:
    PRODUCTS['sibling-background-item-drop-pickup-spawn'] = {
        **PRODUCTS['sibling-background-item-equipment-current-entry-tail-spawn'],
        'bridges': {**PRODUCTS['sibling-background-item-equipment-current-entry-tail-spawn']['bridges'],
            'own-login-bridge-dg49.dll': ITEM_TRANSFER_UI_DLL_SHA},
        'bridge_artifact': ROOT / 'work/local_original_session/implementation-1/item-equipment-product/popup-helper-high/popup-stored-input-consumption-352-v1/own-login-bridge-dg49.dll',
        'item_equipment_swap_reselect': False,
        'item_equipment_ui_observe': False,
        'item_transfer_ui': True,
        'item_quantity_popup': 'CURRENT_PC_ITEM_QUANTITY_POPUP_V1',
        'item_transfer_entry': 'CURRENT_SOURCE_BOUND_ITEM_ENTRY_V2',
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


# Programmatic fixture profile. It borrows no Native bridge/image permission;
# runtime installation remains an explicit root integration step.
PRODUCTS['sibling-background-repeated-player-life-spawn'] = {
    **PRODUCTS['sibling-background-npc-player-lethal-recovery-spawn'],
    'bridges': {**PRODUCTS['sibling-background-npc-player-lethal-recovery-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '18164426c1b9397c8e4216ad083842dbf2ed7a662acfa49bde39fbec2f2e0e80'},
    'bridge_artifact': ROOT / 'work/local_original_session/integration-1/item-reference-repeat-native-composite-v1/native/own-login-bridge-dg49.dll',
    'player_life_repeat': True,
}

# Explicit canonical positive-hit / original217 respawn composition.
PRODUCTS['sibling-background-npc-respawn-target-hit-spawn'] = {
    **PRODUCTS['sibling-background-npc-respawn-spawn'],
    'bridges': {**PRODUCTS['sibling-background-npc-respawn-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '18164426c1b9397c8e4216ad083842dbf2ed7a662acfa49bde39fbec2f2e0e80'},
    'bridge_artifact': ROOT / 'work/local_original_session/integration-1/item-reference-repeat-native-composite-v1/native/own-login-bridge-dg49.dll',
    'npc_respawn_target_hit': True,
    'manual_attack_move_replacement': False,
    'continuous_manual_move': False,
}

# Explicit opt-in one adjacent retaliation; separate from respawn validation.
PRODUCTS['sibling-background-npc-single-retaliation-spawn'] = {
    **PRODUCTS['sibling-background-npc-respawn-target-hit-spawn'],
    'npc_retaliation': True,
}

PRODUCTS['sibling-background-npc-continuous-retaliation-spawn'] = {**PRODUCTS['sibling-background-npc-single-retaliation-spawn'], 'npc_continuous_retaliation': True}

# Explicit Buff physical runtime identity. Typed cold admission is separate.
# Source-only canonical validation retains its original descriptor and guards.
PRODUCTS['sibling-background-skill-buff-spawn'] = {
    **PRODUCTS['sibling-background-source-quit-spawn'],
    'bridges': {**PRODUCTS['sibling-background-source-quit-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '18164426c1b9397c8e4216ad083842dbf2ed7a662acfa49bde39fbec2f2e0e80'},
    'bridge_artifact': ROOT / 'work/local_original_session/integration-1/item-reference-repeat-native-composite-v1/native/own-login-bridge-dg49.dll',
    'continuous_manual_move': False,
    'continuous_manual_attack': False,
    'manual_attack_move_replacement': False,
    'manual_use_item': False,
    'use_item_already_open': False,
    'use_item_current_entry': False,
    'item_transfer_ui': False,
    'item_equipment_swap_reselect': False,
    'player_life_repeat': False,
    'player_death_recovery': False,
    'npc_respawn_lifecycle': False,
    'allow_respawn_attack': False,
    'skill_buff_runtime': True,
    'native_spell_input_enabled': False,
    'runtime_status': 'EXPLICIT_BUFF_COLD_RUNTIME_CANDIDATE',
    'runtime_verdict': 'ROSTER_RESTORE_BACKEND_ONLY_NATIVE_SPELL_UNVERIFIED',
}
PRODUCTS['sibling-background-skill-buff-whole-entry-spawn'] = {
    **PRODUCTS['sibling-background-skill-buff-spawn'],
    'bridges': {**PRODUCTS['sibling-background-skill-buff-spawn']['bridges'],
                'own-login-bridge-dg49.dll': '1c90b0847aef947dd64eb2658bcf9bd79a4ee3dfc94d55aa1fe396b02b279955'},
    'bridge_artifact': ROOT / 'work/local_server_rea_20261016/daybreak_page_noaccess_handoff/designated-01a14ed2/source-spell-director-return-current-350-v1/native/own-login-bridge-director350.dll',
    'native_spell_input_enabled': True,
    'runtime_verdict': 'EXPLICIT_SOURCE_QUALIFIED_WHOLE_ENTRY_RUNTIME_UNVERIFIED',
}



PRODUCTS['canonical-selected-features-v1'] = {
    **PRODUCTS['baseline'], 'source_build_only': True, 'canonical_validation_only': True,
}


SHOP_INPUT_PROFILE = 'canonical-shop-input-v1'
_SHOP_INPUT_NATIVE = None


def install_shop_input_profile(*, bridge_artifact, bridge_sha256):
    """Root cold input: exact built V6 DLL, never an inferred Native selection."""
    global _SHOP_INPUT_NATIVE
    need(_SHOP_INPUT_NATIVE is None and SHOP_INPUT_PROFILE not in PRODUCTS,
         'SHOP_INPUT_PROFILE_ALREADY_REGISTERED')
    need(isinstance(bridge_artifact, Path) and bridge_artifact.is_absolute()
         and type(bridge_sha256) is str and re.fullmatch('[0-9a-f]{64}', bridge_sha256) is not None
         and bridge_sha256 not in {value for spec in PRODUCTS.values()
             for value in spec.get('bridges', {}).values()}
         and digest(bridge_artifact) == bridge_sha256,
         'SHOP_INPUT_EXPLICIT_BUILT_V6_NATIVE_REQUIRED')
    spec = {**PRODUCTS['sibling-background-source-quit-spawn'],
        'bridges': {**PRODUCTS['sibling-background-source-quit-spawn']['bridges'],
                    'own-login-bridge-dg49.dll': bridge_sha256},
        'bridge_artifact': bridge_artifact, 'original_screenshot': True,
        'continuous_manual_move': True, 'continuous_manual_attack': False,
        'manual_attack_move_replacement': False, 'manual_use_item': False,
        'manual_inventory_update': False, 'shop_input_profile': True}
    _SHOP_INPUT_NATIVE = (bridge_artifact, bridge_sha256, spec, spec['bridges'], tuple(spec.items()), tuple(spec['bridges'].items()))
    PRODUCTS[SHOP_INPUT_PROFILE] = spec


def _shop_input_native_current():
    evidence = _SHOP_INPUT_NATIVE
    need(type(evidence) is tuple and len(evidence) == 6
         and PRODUCTS.get(SHOP_INPUT_PROFILE) is evidence[2]
         and evidence[2]['bridges'] is evidence[3]
         and tuple(evidence[2].items()) == evidence[4]
         and tuple(evidence[3].items()) == evidence[5]
         and digest(evidence[0]) == evidence[1], 'SHOP_INPUT_NATIVE_DESCRIPTOR_CHANGED_OR_ABSENT')
    return evidence[2]


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
        return self.guard_exact_sync(peer)

    def guard_exact_sync(self, peer):
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

    @staticmethod
    def _quit_closing_tcp_state(data, size, peer, primary_pid):
        """One exact game tuple for the drained duplicate Quit only.

        Return 5 for the existing live path or 7 for its CLOSE_WAIT transition.
        Neither value is a general OwnerSample or permission for another opcode.
        """
        if (type(peer) is not dict or peer.get('schema') != 'lc-local-accepted-peer-v1'
                or peer.get('connection_id') != 4 or peer.get('endpoint_port') != 14030
                or peer.get('server_port') != 14030
                or peer.get('client_host') != '127.0.0.1'
                or peer.get('server_host') != '127.0.0.1'
                or type(peer.get('client_port')) is not int
                or not 1 <= peer['client_port'] <= 65535
                or type(peer.get('accepted_monotonic_ns')) is not int
                or peer['accepted_monotonic_ns'] <= 0
                or type(primary_pid) is not int or primary_pid <= 0):
            return None
        if len(data) < 4 or type(size) is not int or not 4 <= size <= len(data):
            return None
        count = struct.unpack_from('<I', data)[0]
        if count > 4096 or 4 + 24 * count > size:
            return None
        matched = []
        for n in range(count):
            state, local, lp, remote, rp, pid = struct.unpack_from('<6I', data, 4 + 24 * n)
            if (local.to_bytes(4, 'little') == b'\x7f\0\0\1'
                    and remote.to_bytes(4, 'little') == b'\x7f\0\0\1'
                    and socket.ntohs(lp & 65535) == peer['client_port']
                    and socket.ntohs(rp & 65535) == peer['server_port']):
                matched.append((state, pid))
        return matched[0][0] if len(matched) == 1 and matched[0][1] == primary_pid \
            and matched[0][0] in (5, 7) else None

    def quit_closing_tuple_state_sync(self, peer):
        """Current retained primary and TCP witness; only the broker's duplicate Quit uses it."""
        child, handle, job = self.child, self.owner_handle, self.owner_job
        if (child is None or self.closed or self._cleanup_requested is not False
                or not handle or not job or handle is not child.process or job is not child.job
                or child.members.get(child.pid) is not child or not self.key_guard()):
            return None
        self.verify_sources()

        def birth_current():
            times = [self._filetime_type() for _ in range(4)]
            kernel = self.native.k
            return (kernel.GetProcessId(handle) == child.pid
                    and kernel.WaitForSingleObject(handle, 0) == 258
                    and kernel.GetProcessTimes(handle, *(C.byref(t) for t in times))
                    and str(times[0].high << 32 | times[0].low) == child.identity['birth'])

        if not birth_current():
            return None
        ip = C.WinDLL('iphlpapi', use_last_error=True)
        fn = ip.GetExtendedTcpTable
        fn.argtypes = (C.c_void_p, C.POINTER(W.DWORD), W.BOOL, W.ULONG, C.c_int, W.ULONG)
        fn.restype = W.DWORD
        size = W.DWORD()
        if fn(None, C.byref(size), False, 2, 5, 0) != 122 or not 4 <= size.value <= 1048576:
            return None
        capacity = size.value
        data = C.create_string_buffer(capacity)
        if fn(data, C.byref(size), False, 2, 5, 0) != 0 or size.value > capacity:
            return None
        state = self._quit_closing_tcp_state(data.raw, size.value, peer, child.pid)
        if (state is None or self.child is not child or self.owner_handle is not handle
                or self.owner_job is not job or not self.key_guard() or not birth_current()):
            return None
        self.verify_sources()
        return state

    def quit_frame_retained_sync(self, sample, peer):
        """Retained primary proof for this frame's already-checked duplicate Quit.

        The broker alone binds the sample to the same accepted row and callback
        interval. This method never constructs a new live TCP OwnerSample.
        """
        from tools.local_persistent_broker_policy.policy import OwnerSample, Peer
        child, handle, job = self.child, self.owner_handle, self.owner_job
        if (type(peer) is not dict or peer.get('schema') != 'lc-local-accepted-peer-v1'
                or peer.get('connection_id') != 4 or peer.get('endpoint_port') != 14030
                or peer.get('server_port') != 14030
                or peer.get('client_host') != '127.0.0.1'
                or peer.get('server_host') != '127.0.0.1'
                or type(peer.get('client_port')) is not int
                or not 1 <= peer['client_port'] <= 65535
                or type(peer.get('accepted_monotonic_ns')) is not int
                or peer['accepted_monotonic_ns'] <= 0
                or type(sample) is not OwnerSample or type(sample.peer) is not Peer
                or sample.peer.port != peer['server_port']
                or sample.peer.client_port != peer['client_port']
                or sample.peer.accepted_ns != peer['accepted_monotonic_ns']
                or sample.owner is not self or sample.handle is not handle or sample.job is not job
                or sample.exact_identity_and_tuple is not True or sample.alive is not True
                or child is None or self.closed or self._cleanup_requested is not False
                or not handle or not job or handle is not child.process or job is not child.job
                or child.members.get(child.pid) is not child):
            return False

        def current():
            now = time.monotonic_ns()
            if (type(sample.observed_ns) is not int
                    or not 0 < sample.observed_ns <= now
                    or self.child is not child or self.owner_handle is not handle
                    or self.owner_job is not job or self.closed
                    or self._cleanup_requested is not False or not self.key_guard()):
                return False
            times = [self._filetime_type() for _ in range(4)]
            kernel = self.native.k
            return (kernel.GetProcessId(handle) == child.pid
                    and kernel.WaitForSingleObject(handle, 0) == 258
                    and kernel.GetProcessTimes(handle, *(C.byref(t) for t in times))
                    and str(times[0].high << 32 | times[0].low) == child.identity['birth'])

        if not current():
            return False
        self.verify_sources()
        if not current():
            return False
        self.verify_sources()
        return current()

    def quit_terminal_retained_sync(self, peer):
        """Current retained primary for a broker-proven drained duplicate Quit.

        The broker binds the accepted frame or terminal read and first ACK drain.
        This grants no OwnerSample and cannot authorize another opcode.
        """
        child, handle, job = self.child, self.owner_handle, self.owner_job
        if (type(peer) is not dict or peer.get('schema') != 'lc-local-accepted-peer-v1'
                or peer.get('connection_id') != 4 or peer.get('endpoint_port') != 14030
                or peer.get('server_port') != 14030
                or peer.get('client_host') != '127.0.0.1'
                or peer.get('server_host') != '127.0.0.1'
                or type(peer.get('client_port')) is not int
                or not 1 <= peer['client_port'] <= 65535
                or type(peer.get('accepted_monotonic_ns')) is not int
                or peer['accepted_monotonic_ns'] <= 0
                or child is None or self.closed or self._cleanup_requested is not False
                or not handle or not job or handle is not child.process or job is not child.job
                or child.members.get(child.pid) is not child):
            return False

        def current():
            if (self.child is not child or self.owner_handle is not handle
                    or self.owner_job is not job or self.closed
                    or self._cleanup_requested is not False or not self.key_guard()):
                return False
            return True  # key_guard validated retained PID/birth/image/token/Job.

        if not current():
            return False
        self.verify_sources()
        if not current():
            return False
        self.verify_sources()
        return current()

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
                 inventory_reselection_policy=None, allow_source_restart=False, allow_source_reselect=False,
                 inventory_missing_row_policy=None, lethal_attack_preparation=False, allow_respawn_attack=False):
        from tools.local_original_session.input import _ordinary
        need(type(allow_attack) is bool, 'FEATURE_ATTACK_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_move) is bool, 'FEATURE_MOVE_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_use_item) is bool, 'FEATURE_USE_ITEM_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_inventory_update) is bool, 'FEATURE_INVENTORY_UPDATE_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_source_restart) is bool, 'FEATURE_SOURCE_RESTART_CAPABILITY_BOOL_REQUIRED')
        need(type(allow_source_reselect) is bool, 'FEATURE_SOURCE_RESELECT_CAPABILITY_BOOL_REQUIRED')
        self.directory = _ordinary(directory, directory=True)
        self.consumer = consumer
        self._spell_whole_runtime=None
        from tools.local_original_session.manual_move_commands import ManualMoveCommands
        self._manual_producer = ((consumer, ManualMoveCommands, ManualMoveCommands.poll,
                                  ManualMoveCommands.poll_async)
                                 if type(consumer) is ManualMoveCommands else None)
        need(type(lethal_attack_preparation) is bool, 'FEATURE_LETHAL_PREPARATION_BOOL_REQUIRED')
        self._lethal_preparation_methods = None
        self._lethal_preparation_proof = self._lethal_preparation_state = None
        if lethal_attack_preparation:
            need(type(consumer) is ManualMoveCommands and allow_attack is True
                 and consumer.lethal_attack_preparation is True,
                 'FEATURE_LETHAL_PREPARATION_REAL_CONSUMER_REQUIRED')
            self._lethal_preparation_methods = (ManualMoveCommands.lethal_preparation_settled,
                                               ManualMoveCommands.validate_lethal_preparation)
        need(type(allow_respawn_attack) is bool and (not allow_respawn_attack
             or lethal_attack_preparation is True and consumer.allow_respawn_attack is True),
             'FEATURE_RESPAWN_ATTACK_EXPLICIT_CAPABILITY_REQUIRED')
        self.allow_respawn_attack = allow_respawn_attack
        self._respawn_attack_methods = ((ManualMoveCommands.submit_respawn_attack,
                                        ManualMoveCommands.validate_respawn_attack)
                                       if allow_respawn_attack else None)
        self._respawn_attack_arm = self._respawn_attack_completed = None
        self._respawn_attack_submitted = False
        self._respawn_attack_arms = self._respawn_attack_submissions = self._respawn_attack_completions = ()
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
        self.inventory_missing_row_policy = inventory_missing_row_policy
        need(inventory_missing_row_policy is None or type(inventory_missing_row_policy) is str
             and inventory_missing_row_policy == 'EXPLICIT_LOCAL_CONFIGURED_STARTER_IF_MISSING'
             and inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
             and getattr(inventory_broker, 'inventory_missing_row_policy', None) == inventory_missing_row_policy,
             'FEATURE_EXPLICIT_MISSING_ROW_POLICY_REQUIRED')
        need(not allow_source_reselect or allow_source_restart is True
             and inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION,
             'FEATURE_SOURCE_RESELECT_REQUIRES_RESTART_RESELECTION')
        self._source_reselect_methods = None
        if allow_source_reselect:
            need(type(consumer) is ManualMoveCommands, 'FEATURE_SOURCE_RESELECT_REAL_CONSUMER_REQUIRED')
            self._source_reselect_methods = (ManualMoveCommands._current, ManualMoveCommands.submit_source_reselect)
        self.inventory_delivery_policy = inventory_delivery_policy
        self._inventory_owned_service = (None if inventory_broker is None else inventory_broker._inventory_service)
        self._inventory_lifetime_owner = None
        self._inventory_generation = None
        self._inventory_generation_monitor = self._inventory_generation_sample = None
        self._inventory_previous_sample_ns = None
        self._inventory_auto_selection = None
        self._inventory_request = None
        self._inventory_wait = None
        self._inventory_started_ns = self._inventory_clock_ns = None
        self._inventory_observer = None
        self.inventory_collection_policy = getattr(inventory_broker, '_inventory_collection_policy', None)
        if self.inventory_collection_policy is not None:
            from tools.local_original_session import inventory
            need(type(self.inventory_collection_policy) is str
                 and self.inventory_collection_policy == inventory.COLLECTION_POLICY
                 and not allow_inventory_update, 'FEATURE_COLLECTION_UPDATE_UNSUPPORTED')
        self._inventory_frame = None
        self._inventory_client_binding = None
        if inventory_broker is not None:
            from tools.local_original_session.inventory_observe import InventoryObserver
            need(digest(Path(__file__).with_name('inventory_observe.py')) == _INVENTORY_OBSERVER_SOURCE_SHA,
                 'FEATURE_INVENTORY_OBSERVER_SOURCE_CHANGED')
            self._inventory_observer_type = InventoryObserver
            self._inventory_observer_sample = InventoryObserver.sample
            self._inventory_observer = InventoryObserver(inventory_broker, consumer.reader, collection_policy=self.inventory_collection_policy)
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
                       ui='UNKNOWN', inventory_restore=(('ROWS_5_SCALARS_MATCHED'
                           if self.inventory_collection_policy is not None else 'ROW_5_SCALARS_MATCHED')
                           if row.get('status') == 'COMMITTED' else 'UNKNOWN'))
        if self._inventory_auto_selection is not None and row.get('command') == 'AddInventory':
            row = dict(row, delivery_policy=self.inventory_delivery_policy,
                       same_broker_reselection_delivery=self.inventory_reselection_policy or 'UNSUPPORTED')
        self.last_result = dict(row, schema=RESULT_SCHEMA, sequence=self.sequence,
                                last_sequence=self.sequence, automatic_retry=False)
        # The same published result is not rewritten (fsync ~5 ms, spikes to ~500 ms).
        if getattr(self, '_published_result', None) != self.last_result:
            _atomic(self.directory / 'command.result.json', self.last_result, 2048)
            self._published_result = dict(self.last_result)
        return dict(self.last_result)

    def _consume(self, row):
        if self._pending_command == 'SourceReselect' and row.get('command') == 'AddInventory':
            if row.get('status') == 'COMMITTED':
                if self.inventory_collection_policy is not None:
                    from tools.local_original_session import inventory
                    expected_count=len(inventory.validate_current_collection_frame(
                        self._inventory_frame,policy=self.inventory_collection_policy))
                    need(row.get('proof_scope') == 'CLIENT_ITEM_ROWS_SCALARS_ONLY'
                         and row.get('client_inventory') == 'ROWS_5_SCALARS_MATCHED'
                         and type(row.get('item_count')) is int and row['item_count'] == expected_count,
                         'FEATURE_SOURCE_RESELECT_CLIENT_RESTORE_REQUIRED')
                    row = dict(row, proof_scope='CLIENT_SAVED_ITEM_ROWS_SCALARS_AFTER_RESELECT')
                else:
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

    def _lethal_producer(self):
        consumer = self._actual_manual_producer(asynchronous=True)
        methods = self._lethal_preparation_methods
        need(consumer is not None and methods is not None
             and consumer.lethal_attack_preparation is True,
             'FEATURE_LETHAL_PREPARATION_ACTUAL_PRODUCER_REQUIRED')
        for name, original in zip(('lethal_preparation_settled', 'validate_lethal_preparation'), methods):
            method = getattr(consumer, name)
            need(type(method) is MethodType and method.__self__ is consumer
                 and method.__func__ is original and getattr(type(consumer), name) is original
                 and original.__globals__.get('ManualMoveCommands') is type(consumer)
                 and Path(original.__code__.co_filename).resolve()
                     == Path(__file__).with_name('manual_move_commands.py').resolve(),
                 'FEATURE_LETHAL_PREPARATION_METHOD_CHANGED')
        return consumer

    def lethal_preparation_settled(self):
        """Retained native completion only; never grants a current NPC life."""
        consumer = self._lethal_producer()
        need(self._lethal_preparation_proof is not None
             and consumer.state is self._lethal_preparation_state
             and self.last_result.get('status') == 'PREPARED' and not self.pending
             and self._inventory_request is None and self._inventory_wait is None,
             'FEATURE_LETHAL_PREPARATION_PUBLIC_COMPLETION_REQUIRED')
        proof = consumer.lethal_preparation_settled()
        need(proof is self._lethal_preparation_proof
             and proof is consumer._lethal_preparation_completed,
             'FEATURE_LETHAL_PREPARATION_PROOF_CHANGED')
        return proof

    def validate_lethal_preparation(self, writer, *, accepted_ordinal):
        """Delegate the current-life validator under the caller's row lock."""
        proof = self.lethal_preparation_settled()
        consumer = self._lethal_producer()
        need(consumer.validate_lethal_preparation(writer, accepted_ordinal=accepted_ordinal) is proof,
             'FEATURE_LETHAL_PREPARATION_CURRENT_PROOF_CHANGED')
        return proof

    def _receive_lethal_preparation(self, result):
        consumer = self._lethal_producer()
        need(type(result) is dict and consumer.state == result
             and result.get('status') == 'PREPARED'
             and result.get('command') == 'AttackTarget'
             and result.get('phase') == 'LETHAL_PREPARATION_READY'
             and result.get('proof_scope') == 'CURRENT_LETHAL_NPC_DEATH_DRAIN_ONLY'
             and result.get('cleanup_required') is False and result.get('native_attempted') is True
             and consumer.pending is None and self._actual_action_sequence(consumer)
             and self._inventory_request is None and self._inventory_wait is None,
             'FEATURE_LETHAL_PREPARATION_COMPLETION_REQUIRED')
        proof = consumer.lethal_preparation_settled()
        need(proof is not None and proof is consumer._lethal_preparation_completed,
             'FEATURE_LETHAL_PREPARATION_PRIVATE_PROOF_REQUIRED')
        if self.pending:
            need(self._pending_command == 'AttackTarget' and self._lethal_preparation_proof is None,
                 'FEATURE_LETHAL_PREPARATION_PENDING_REQUIRED')
            self._lethal_preparation_proof, self._lethal_preparation_state = proof, consumer.state
            self.pending, self._pending_command = False, None
            return self._consume(result)
        need(proof is self._lethal_preparation_proof and consumer.state is self._lethal_preparation_state,
             'FEATURE_LETHAL_PREPARATION_COMPLETION_CHANGED')
        return dict(self.last_result)

    def _respawn_attack_producer(self):
        consumer = self._actual_manual_producer(asynchronous=True)
        need(self.allow_respawn_attack is True and consumer is not None
             and consumer.allow_respawn_attack is True and self._respawn_attack_methods is not None,
             'FEATURE_RESPAWN_ATTACK_ACTUAL_PRODUCER_REQUIRED')
        for name, original in zip(('submit_respawn_attack', 'validate_respawn_attack'), self._respawn_attack_methods):
            method = getattr(consumer, name)
            need(type(method) is MethodType and method.__self__ is consumer
                 and method.__func__ is original and getattr(type(consumer), name) is original
                 and original.__globals__.get('ManualMoveCommands') is type(consumer)
                 and Path(original.__code__.co_filename).resolve()
                     == Path(__file__).with_name('manual_move_commands.py').resolve(),
                 'FEATURE_RESPAWN_ATTACK_METHOD_CHANGED')
        return consumer

    def _arm_respawn_attack(self, runtime, receipt, summary):
        need(type(runtime) is ProductFeatures and runtime.manual is self
             and len(self._respawn_attack_arms) < 2
             and (self._respawn_attack_arm is None or receipt.generation.ordinal == 2
                  and self._respawn_attack_arm is self._respawn_attack_arms[-1]
                  and self._respawn_attack_arm[1].generation is receipt.old_generation
                  and self._respawn_attack_submitted_current())
             and not self.pending and not self.closed
             and not self._resources_closed and not self._polling,
             'FEATURE_RESPAWN_ATTACK_ONCE_INGRESS_REQUIRED')
        consumer = self._respawn_attack_producer()
        proof = (self.lethal_preparation_settled() if not self._respawn_attack_arms
                 else self._respawn_attack_arms[-1][3])
        from tools.local_original_session.commands import REQUEST_SCHEMA
        request = dict(schema=REQUEST_SCHEMA, sequence=summary['public_sequence'],
            command='AttackTarget', uid=runtime.npc_session.broker.realm.service(receipt.writer).snapshot().uid,
            target_uid=receipt.recipe.uid, map_id=receipt.recipe.map_id)
        self._respawn_attack_arm = (runtime, receipt, consumer, proof, request, dict(summary))
        self._respawn_attack_arms += (self._respawn_attack_arm,)

    def _respawn_attack_submitted_current(self):
        return any(arm is self._respawn_attack_arm for arm in self._respawn_attack_submissions)

    def _respawn_attack_current(self):
        arm = self._respawn_attack_arm
        need(type(arm) is tuple and len(arm) == 6, 'FEATURE_RESPAWN_ATTACK_ARM_REQUIRED')
        runtime, receipt, consumer, proof, request, summary = arm
        need(runtime.manual is self and any(arm is value for value in self._respawn_attack_arms)
             and any(receipt is value for value in runtime._respawn_attack_ready_receipts)
             and self._respawn_attack_producer() is consumer
             and self._lethal_preparation_proof is proof and consumer._lethal_preparation_completed is proof,
             'FEATURE_RESPAWN_ATTACK_ARM_CHANGED')
        runtime._respawn_attack_binding(receipt)
        return arm

    def validate_respawn_attack(self, receipt):
        arm = self._respawn_attack_current()
        need(receipt is arm[1] and self._respawn_attack_submitted_current()
             and self._respawn_attack_completed is not None and not self.pending
             and self.last_result.get('status') == 'COMMITTED'
             and self.last_result.get('sequence') == arm[5]['public_sequence'],
             'FEATURE_RESPAWN_ATTACK_PUBLIC_COMPLETION_REQUIRED')
        proof = arm[2].validate_respawn_attack(receipt)
        need(proof is self._respawn_attack_completed and proof is arm[2]._respawn_attack_completed,
             'FEATURE_RESPAWN_ATTACK_COMPLETION_CHANGED')
        return proof

    async def _receive_manual_async(self, result):
        if (self._respawn_attack_arm is not None and self._respawn_attack_submitted_current()
                and result.get('status') == 'COMMITTED'):
            arm = self._respawn_attack_current()
            consumer, receipt = arm[2], arm[1]
            state = consumer.state
            need(type(result) is dict and result == state and consumer.pending is None
                 and result.get('command') == 'AttackTarget',
                 'FEATURE_RESPAWN_ATTACK_NATIVE_COMPLETION_REQUIRED')
            async with receipt.row['operation_lock']:
                self._respawn_attack_current()
                proof = consumer.validate_respawn_attack(receipt)
                need(proof is consumer._respawn_attack_completed and proof is not None
                     and consumer.state is state and result == state
                     and self.sequence == arm[5]['public_sequence']
                     and proof.sequence == consumer._action_sequence == arm[5]['native_sequence']
                     and proof.accepted_ordinal == arm[5]['accepted_ordinal'],
                     'FEATURE_RESPAWN_ATTACK_PROOF_REQUIRED')
                self._respawn_attack_completed = proof
                if not any(proof is value for value in self._respawn_attack_completions):
                    self._respawn_attack_completions += (proof,)
        return self._receive(result, asynchronous=True)

    def _actual_action_sequence(self, consumer, *, transition=None):
        # Cache of the original _publish assignment, never another counter.
        bound = consumer._action_bound
        if (type(consumer._action_sequence) is not int
                or not 1 <= consumer._action_sequence <= consumer.sequence <= 2147483647
                or bound is None):
            return False
        if transition == 'SourceRestart':
            # Original normal Restart clears selection but retains this bound.
            # Exact producer/state/ACK completion checks stay at the call site.
            return bound is consumer._bound
        if transition == 'SourceReselect':
            # Reuse the original completed old/new lifetime proof; publication
            # uses old bound, completion installs the verified new bound.
            proof = consumer._source_reselect_completed
            return (type(proof) is tuple and len(proof) == 4
                    and proof[0] is consumer._source_restart_completed
                    and type(proof[0]) is dict and proof[0].get('bound') is bound
                    and proof[2] is consumer._bound)
        if bound is not consumer._bound:
            return False
        retained = bound[0]
        writer, broker, selected = retained[0], retained[1], retained[12]
        game = broker.realm.registry.resolve(writer)
        return game is retained[14] and game.selection is selected

    def _actual_move_rejection(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None:
            return False
        expected = dict(status='REJECTED', phase='REJECTED', reason='EDGE_BLOCKED', command='MoveGoal',
            accepted=False, native_attempted=True, automatic_retry=False, cleanup_required=False,
            proof_scope='SC4EE0_DRAIN_WITH_CLIENT_SETTLED', moving_back_snapshot_observed=True,
            moving_back_start_observed=False, sequence=consumer._action_sequence)
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and self._actual_action_sequence(consumer)
                and consumer.pending is None and type(consumer.state) is dict and consumer.state == result
                and self._inventory_request is None and self._inventory_wait is None)

    def _actual_use_item_commit(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None:
            return False
        expected = dict(status='COMMITTED', reason=None, sequence=consumer._action_sequence,
            automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
            command='UseItem', proof_scope='VALIDATED_ITEM_USE_INTENT_ONLY',
            use_effect='UNKNOWN', ack='UNKNOWN', equipped='UNKNOWN', render='UNKNOWN', save='UNKNOWN')
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and self._actual_action_sequence(consumer)
                and consumer.pending is None and type(consumer.state) is dict and consumer.state == result
                and self._inventory_request is None and self._inventory_wait is None)

    def _actual_source_restart_commit(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None or consumer.allow_source_restart is not True:
            return False
        expected = dict(status='COMMITTED', reason=None, sequence=consumer._action_sequence,
            automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
            command='SourceRestart', proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY',
            response_drained=True, selection_cleared=True, ui='UNKNOWN', inventory_restore='UNKNOWN')
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and self._actual_action_sequence(consumer, transition='SourceRestart')
                and consumer.pending is None and type(consumer.state) is dict and consumer.state == result
                and self._inventory_request is None and self._inventory_wait is None)

    def _actual_source_reselect_commit(self, result, *, asynchronous):
        consumer = self._actual_manual_producer(asynchronous=asynchronous)
        if consumer is None or consumer.allow_source_reselect is not True:
            return False
        expected = dict(status='COMMITTED', reason=None, sequence=consumer._action_sequence,
            automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
            command='SourceReselect', proof_scope='LOCAL_RESELECT_LAND_READY_ONLY',
            selection_changed=True, world_ready=True, ui='UNKNOWN', inventory_restore='UNKNOWN')
        return (type(result) is dict and set(result) == set(expected)
                and all(type(result[k]) is type(v) and result[k] == v for k, v in expected.items())
                and self._actual_action_sequence(consumer, transition='SourceReselect')
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
        if result.get('status') == 'PREPARED':
            try:
                settled = self._receive_lethal_preparation(result)
                if self._respawn_attack_arm is None:
                    return settled
                self._respawn_attack_current()
            except Exception:
                return self._consume(dict(status='UNKNOWN', command='AttackTarget', cleanup_required=True,
                    reason='FEATURE_LETHAL_PREPARATION_COMPLETION_UNKNOWN', automatic_retry=False))
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
        if (self._respawn_attack_arm is not None and self._respawn_attack_submitted_current()
                and result.get('status') == 'COMMITTED'):
            arm = self._respawn_attack_current()
            need(self._respawn_attack_completed is not None
                 and self._respawn_attack_completed is arm[2]._respawn_attack_completed
                 and result == arm[2].state,
                 'FEATURE_RESPAWN_ATTACK_VALIDATED_COMPLETION_REQUIRED')
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
        if self._respawn_attack_arm is not None:
            arm = self._respawn_attack_current()
            need(asynchronous and not self._respawn_attack_submitted_current()
                 and set(request) == set(arm[4])
                 and all(type(request[k]) is type(v) and request[k] == v for k, v in arm[4].items()),
                 'FEATURE_RESPAWN_ATTACK_EXACT_ONCE_REQUEST_REQUIRED')
            need((arm[1].generation.ordinal == 2
                  or self.lethal_preparation_settled() is arm[3])
                 and self.consumer.sequence + 1 == arm[5]['native_sequence'],
                 'FEATURE_RESPAWN_ATTACK_SETTLED_DISPATCH_REQUIRED')
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
            if self._respawn_attack_arm is not None:
                arm = self._respawn_attack_current()
                need(self.consumer._lethal_preparation_completed is arm[3]
                     and self.consumer.sequence + 1 == arm[5]['native_sequence'],
                     'FEATURE_RESPAWN_ATTACK_SETTLED_DISPATCH_REQUIRED')
                self._respawn_attack_submitted = True
                self._respawn_attack_submissions += (arm,)
                return self._consume(self.consumer.submit_respawn_attack(
                    request['uid'], request['target_uid'], request['map_id'], receipt=arm[1]))
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

    def _inventory_generation_restore_only(self, generation):
        # Mode/row/binding are produced by the original selected callback.
        # This consumer selects its existing grant path, never creates a row or
        # promotes FIRST_GRANT to _inventory_restored=True.
        if generation is None or generation.frame is None:
            return None
        mode = getattr(generation, 'mode', None)
        if generation.restored is True:
            need(mode == 'RESTORED_EXISTING' or mode is None and self.inventory_missing_row_policy is None,
                 'FEATURE_INVENTORY_RESTORED_MODE_REQUIRED')
            return True
        if mode != 'FIRST_GRANT':
            return None
        broker = self.inventory_broker
        need(self.inventory_missing_row_policy == 'EXPLICIT_LOCAL_CONFIGURED_STARTER_IF_MISSING'
             and broker.inventory_missing_row_policy == self.inventory_missing_row_policy
             and generation.restored is False and broker._inventory_restored is False
             and generation.frame is broker._inventory_config_frame
             and generation.selection_binding is broker._inventory_selection_binding
             and generation.selection_binding[-1] is generation.frame,
             'FEATURE_INVENTORY_EXPLICIT_FIRST_GRANT_MODE_REQUIRED')
        return False

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
        lifetime_owner = self._inventory_lifetime_owner
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
        if lifetime_owner is not None:
            self._inventory_transferred_generation(lifetime_owner, generation)
        consumer, public_sequence, native_sequence = self.consumer, self.sequence, self.consumer.sequence
        sampled = self.last_sample_monotonic_ns
        observer = InventoryObserver(broker, consumer.reader, collection_policy=self.inventory_collection_policy)
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
        if lifetime_owner is not None:
            try:
                self._inventory_transferred_generation(lifetime_owner, generation)
            except BaseException:
                observer.close()
                raise
        else:
            need(self._inventory_lifetime_owner is None, 'CONTINUOUS_INVENTORY_TRANSFER_CHANGED')
        self._inventory_observer.close()
        self._inventory_observer = observer
        self._inventory_previous_sample_ns = sampled
        self._inventory_generation = generation
        self._inventory_frame = self._inventory_client_binding = None
        self._inventory_update_frame = self._inventory_update_state = None
        self._inventory_auto_selection = None
        self._inventory_started_ns = self._inventory_clock_ns = (self._source_reselect_started_ns if reselecting else None)
        self._inventory_generation_monitor, self._inventory_generation_sample = monitor_ref, sample_floor
        if lifetime_owner is None:
            self._inventory_owned_service = original[8]  # Actual service from the fully validated fresh generation.
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
        if broker._inventory_attempted:
            return
        if self.inventory_reselection_policy is not None:
            if self._inventory_generation_restore_only(generation) is None:
                return
        elif broker._inventory_restored is not True:
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
        else:
            # A committed normal move replaces Position between client samples.
            # Keep the delivered selection/owner fixed, as the observer does;
            # its locked before/after proof still fixes Position within a query.
            position = movement.snapshot()
            need(delivery[0] is identities[14]
                 and type(delivery[0]) is type(position) is inventory.movement.Position
                 and (position.uid, position.name, position.map_id)
                     == (delivery[0].uid, delivery[0].name, delivery[0].map_id),
                 'FEATURE_INVENTORY_CLIENT_AUTHORITY_CHANGED')
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
                    and 0 < observed['typed_bytes_requested'] <= (inventory_observe.KIT_BYTE_LIMIT
                        if getattr(self.inventory_broker, '_inventory_kit_policy', None) == inventory.KIT_POLICY
                        else inventory_observe.BYTE_LIMIT)
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
        updating = self._pending_command == 'UpdateInventory'
        frame = self._inventory_update_frame if updating else self._inventory_frame
        if observed['empty'] is True:
            if observed['reason'] is not None:
                return self._inventory_unknown(observed['reason'])
            if (self.inventory_collection_policy is None or inventory.validate_current_collection_frame(
                    frame,policy=self.inventory_collection_policy)):
                return dict(self.last_result)
        kit = getattr(self.inventory_broker, '_inventory_kit_policy', None) == inventory.KIT_POLICY
        if self.inventory_collection_policy is not None or kit:
            need(not updating, 'FEATURE_COLLECTION_UPDATE_UNSUPPORTED')
            items = (inventory.validate_kit_frame(frame) if kit else
                     inventory.validate_current_collection_frame(frame, policy=self.inventory_collection_policy))
            if not items:
                need(observed.get('empty') is True and observed.get('source_contract_valid') is True
                     and observed.get('stable_double_read') is True
                     and observed.get('source_owner_revalidated') is True
                     and observed.get('read_consistency') == 'STRICT_STABLE'
                     and type(observed.get('query_started_monotonic_ns')) is int
                     and observed['query_started_monotonic_ns'] == observer.last_sample_monotonic_ns
                     and now <= observed['query_started_monotonic_ns'],
                     'FEATURE_EMPTY_COLLECTION_FRESH_QUERY_REQUIRED')
            expected_rows = []
            for item in items:
                fields = dict(item.raw_fields)
                expected_rows.append(dict(id_u64=fields[1], template_id_u32=fields[2] & 0xffffffff,
                    field18_u64=fields[3], field28_i64=fields[4] - (1 << 64) if fields[4] >= 1 << 63 else fields[4],
                    field30_bool=fields[24]))
            if observed['entry_count'] != len(items) or observed['rows'] != expected_rows:
                return self._inventory_unknown('FEATURE_INVENTORY_CLIENT_ITEM_MISMATCH')
            if observed['reason'] is not None:
                return self._inventory_unknown(observed['reason'])
            self._inventory_now()
            result = self._consume(dict(status='COMMITTED', command='AddInventory', invoked=True,
                phase='CLIENT_CONFIRMED', proof_scope='CLIENT_ITEM_ROWS_SCALARS_ONLY',
                client_inventory='ROWS_5_SCALARS_MATCHED', item_count=len(items),
                transport_proof_scope='TRANSPORT_DRAIN_ONLY', render='UNKNOWN', equipped='UNKNOWN', save='UNKNOWN',
                all_17_wire_fields_proven=False, wire_field18_bytes_observed=False,
                catalog_live_materialization_proven=False))
            self.pending = False
            self._pending_command = None
            self._inventory_wait = None
            return result
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
        if self.consumer._readonly_pending is not None:
            return dict(self.last_result)  # Native queue occupied; collect first.
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
                    result = await self._receive_manual_async(await self.consumer.poll_async())
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
                         and (self._inventory_generation_restore_only(self._inventory_generation) is not None
                              if self.inventory_reselection_policy is not None
                              else self.inventory_broker._inventory_restored is True),
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
                         and generation.selection_binding is not None
                         and generation.selection_binding[-1] is self._inventory_frame,
                         'FEATURE_INVENTORY_RESELECTION_SAVED_ROW_REQUIRED')
                    mode = self._inventory_generation_restore_only(generation)
                    need(type(mode) is bool, 'FEATURE_INVENTORY_CURRENT_DELIVERY_MODE_REQUIRED')
                    options['restore_only'] = mode
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
                    collection_before = (None if self.inventory_collection_policy is None else
                        (self._inventory_generation, self._inventory_generation.selection_binding, self._inventory_frame))
                    transport = await self.inventory_broker.add_inventory(binding.writer, **options)
                    if self.inventory_collection_policy is not None and transport['status'] == 'COMMITTED':
                        # Actual empty-vector/prewrite grant can replace saved1
                        # with saved2 in this SAME first ADD. Adopt only its real
                        # immutable result and the returned post-drain objects.
                        from tools.local_original_session import inventory_store
                        generation, old_binding, old_frame = collection_before
                        broker = self.inventory_broker
                        new_frame, new_binding = broker._inventory_frame, broker._inventory_selection_binding
                        need(generation is self._inventory_generation is broker._inventory_generation
                             and generation is self._inventory_reselection_current(binding.writer)
                             and generation.phase == 'ACTIVE' and generation.writer is binding.writer
                             and generation.current_frame is generation.frame is generation.operation_frame is new_frame
                             and broker._inventory_current_frame is broker._inventory_operation_frame is new_frame
                             and generation.delivery_authority is broker._inventory_delivery_authority
                             and generation.delivery_authority is not None and generation.write_attempted is True
                             and generation.attempted is True and generation.selection_binding is new_binding
                             and type(old_binding) is tuple and len(old_binding) == 11
                             and type(new_binding) is tuple and len(new_binding) == 11
                             and all(a is b for a,b in zip(old_binding[:10],new_binding[:10]))
                             and old_binding[10] is old_frame and new_binding[10] is new_frame,
                             'FEATURE_COLLECTION_ADD_LIFETIME_CHANGED')
                        if new_frame is not old_frame:
                            grant = generation.collection_grant
                            need(type(grant) is inventory_store.InstanceGrant
                                 and grant.before_frame is old_frame and grant.after_frame is new_frame
                                 and grant.character_uid == position.uid
                                 and grant.prototype_uid == inventory.validate_frame(old_frame).identifier
                                 and grant.policy == inventory_store.SECOND_INSTANCE_POLICY
                                 and grant.policy == broker._inventory_collection_grant[0],
                                 'FEATURE_COLLECTION_ACTUAL_GRANT_REQUIRED')
                        else:
                            need(generation.collection_grant is None and new_binding is old_binding,
                                 'FEATURE_COLLECTION_RESTORE_FRAME_CHANGED')
                        need(self._inventory_auto_selection is None or self._inventory_auto_selection is old_binding,
                             'FEATURE_COLLECTION_AUTO_SELECTION_CHANGED')
                        self._inventory_frame = new_frame
                        if self._inventory_auto_selection is not None:
                            self._inventory_auto_selection = new_binding
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

    def _spell_whole_callback_quiesced(self):
        runtime=self._spell_whole_runtime
        if runtime is None:return False
        try:
            source=runtime.features.selection._spell_source
            need(type(runtime)is source.check().Runtime,'SPELL_QUIT_EXACT_RUNTIME_REQUIRED')
            return runtime.quiesce_ready(self) is True
        except Exception:return False

    def quiesce_for_source_quit(self, *, source_quit=None):
        """Hand off this actual native slot; never recover an unknown native result."""
        terminal_exit = source_quit is not None and self.consumer._source_quit_terminal_current(source_quit)
        prepared = False
        if self.consumer.state['status'] == 'PREPARED':
            try:
                prepared = self.lethal_preparation_settled() is self._lethal_preparation_proof
            except Exception:
                return False
        if (self._polling or self._resources_closed or self.consumer.pending is not None
                or self.consumer._readonly_pending is not None
                or self.consumer.state['status'] not in ('READY', 'COMMITTED') and not prepared and not terminal_exit):
            return False
        if terminal_exit:
            if (self.last_result.get('status') != 'COMMITTED' or self.pending
                    or self._inventory_request is not None or self._inventory_wait is not None):
                return False
        elif self._prewrite_refusal is not None:
            try:
                self.inventory_broker._inventory_refusal_current(self._prewrite_refusal)
            except Exception:
                return False
        elif self.last_result.get('status') == 'NOT_REQUESTED':
            if (self.consumer.state['status'] != 'READY' or (self.consumer.sequence != 0 and not self._spell_whole_callback_quiesced())
                    or self.consumer._reservation or self.pending
                    or self._inventory_request is not None or self._inventory_wait is not None):
                return False
        elif self.last_result.get('status') != 'COMMITTED' and not prepared or self.pending:
            return False
        self.closed, self.pending = True, False
        self._inventory_request = self._inventory_wait = None
        return True

    def transfer_inventory_lifetime(self, owner):
        """Transfer the live shared service once to the whole feature owner."""
        from tools.local_original_session import npc_continuous_retaliation as continuous
        need(type(self) is ManualMoveRequests and type(owner) is continuous.InventoryLifetimeOwner
             and owner.manual is self and owner.controller.broker is self.inventory_broker
             and getattr(self.inventory_broker, '_npc_continuous', None) is owner.controller
             and not owner.controller.closed and not owner.closed and not owner.claimed
             and owner.service is self._inventory_owned_service is self.inventory_broker._inventory_service
             and owner.service is not None and not owner.service._closed
             and self._inventory_lifetime_owner is None
             and not self.closed and not self._resources_closed and not self._polling
             and not self.pending and self._pending_command is None
             and self._inventory_request is None and self._inventory_wait is None
             and self.consumer.pending is None and self.consumer._readonly_pending is None
             and self.consumer.state.get('status') != 'UNKNOWN'
             and not self.consumer._busy and not self.consumer._reservation,
             'CONTINUOUS_EXACT_LIVE_INVENTORY_TRANSFER_REQUIRED')
        owner.claim(self)
        self._inventory_lifetime_owner = owner
        self._inventory_owned_service = None
        return owner

    def _inventory_transferred_generation(self, owner, generation):
        """Keep ownership transfer bound to this original ACTIVE service."""
        from tools.local_original_session import npc_continuous_retaliation as continuous
        from tools.local_original_session import inventory
        need(type(owner) is continuous.InventoryLifetimeOwner
             and self._inventory_lifetime_owner is owner and owner.manual is self
             and type(owner.controller) is continuous.Controller
             and owner.controller.inventory_owner is owner
             and owner.controller.broker is self.inventory_broker
             and self.inventory_broker._npc_continuous is owner.controller
             and not owner.controller.closed and owner.claimed and not owner.closed
             and self._inventory_owned_service is None
             and type(owner.service) is inventory.InventoryService
             and owner.service is generation.service is self.inventory_broker._inventory_service
             and not owner.service._closed and generation is self.inventory_broker._inventory_generation
             and generation.phase == 'ACTIVE',
             'CONTINUOUS_TRANSFERRED_INVENTORY_GENERATION_REQUIRED')
        continuous.InventoryLifetimeOwner.require_current(owner)
        return owner

    def _close_transferred_inventory(self, owner):
        """Close command resources; the literal feature owner closes its service."""
        from tools.local_original_session import npc_continuous_retaliation as continuous
        def refs():
            # Cleanup consumes stored ownership even after current registration
            # or service liveness was lost; it never closes any generation here.
            need(type(owner) is continuous.InventoryLifetimeOwner
                 and self._inventory_lifetime_owner is owner and owner.manual is self
                 and type(owner.controller) is continuous.Controller
                 and owner.controller.inventory_owner is owner
                 and owner.controller.broker is self.inventory_broker
                 and owner.claimed and self._inventory_owned_service is None,
                 'CONTINUOUS_EXACT_COMMAND_CLOSE_OWNER_REQUIRED')
        self.closed = True
        refs()
        if not self._resources_closed:
            self._resources_closed = True
            try:
                self.consumer.close()
            finally:
                try:
                    if self._inventory_observer is not None:
                        self._inventory_observer.close()
                finally:
                    refs()
                    continuous.InventoryLifetimeOwner.command_close(owner, self)

    def close(self):
        if self._inventory_lifetime_owner is not None:
            return self._close_transferred_inventory(self._inventory_lifetime_owner)
        self.closed = True
        if not self._resources_closed:
            self._resources_closed = True
            try:
                self.consumer.close()
            finally:
                if self._inventory_observer is not None:
                    self._inventory_observer.close()
                if self._inventory_owned_service is not None:
                    self._inventory_owned_service.close()


def hp_status_png_config(config):
    # Require Screenshot's existing initial saved-row generation contract.
    # No configuration policy, generation or Restart/Reselect is synthesized.
    from tools.local_original_session import feature_config, restart
    need(type(config) is feature_config.Features
         and config.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
         and config.restart_policy == restart.POLICY,
         'FEATURE_HP_PNG_EXISTING_GENERATION_CONFIG_REQUIRED')
    return config

class ProductFeatureFactory:
    """Wire opt-in consumers into the launcher's actual retained lifetime."""
    def __init__(self, reader, *, product, control_mode, directory, config, swap_saved_b_tail=False,
                 zero_use_reselect=False, item_transfer_ui=False, npc_hp_feedback_only=False, npc_dead_goal_only=False):
        need(type(npc_dead_goal_only) is bool, 'FEATURE_NPC_DEAD_GOAL_EXACT_BOOL_REQUIRED')
        self.npc_dead_goal_only = self._npc_dead_goal_only_bound = npc_dead_goal_only
        self._npc_dead_goal_context = (reader, product, config, control_mode)
        if product in ('canonical-selected-features-v1','sibling-background-npc-continuous-retaliation-spawn','sibling-background-npc-single-retaliation-spawn','sibling-background-npc-respawn-target-hit-spawn','sibling-background-repeated-player-life-spawn','sibling-background-skill-buff-spawn','sibling-background-skill-buff-whole-entry-spawn'):
            need(not npc_dead_goal_only, 'CANONICAL_NO_NPC_DEAD_GOAL_TEST_REQUIRED')
        if product == 'sibling-background-npc-continuous-retaliation-spawn':
            from tools.local_original_session.npc_continuous_retaliation_runtime import configure_factory
            need(not npc_dead_goal_only,'CONTINUOUS_NO_DEAD_GOAL_REQUIRED')
            configure_factory(self,reader=reader,product=product,control_mode=control_mode,directory=directory,
                config=config,flags=(swap_saved_b_tail,zero_use_reselect,item_transfer_ui,npc_hp_feedback_only))
            return
        if product == 'sibling-background-npc-single-retaliation-spawn':
            from tools.local_original_session.npc_retaliation_runtime import configure_factory
            need(not npc_dead_goal_only, 'RETALIATION_NO_DEAD_GOAL_REQUIRED')
            configure_factory(self,reader=reader,product=product,control_mode=control_mode,directory=directory,
                config=config,flags=(swap_saved_b_tail,zero_use_reselect,item_transfer_ui,npc_hp_feedback_only))
            return
        if product == 'sibling-background-npc-respawn-target-hit-spawn':
            from tools.local_original_session.npc_respawn_hit_runtime import configure_factory
            need(not npc_dead_goal_only, 'RESPAWN_HIT_NO_DEAD_GOAL_REQUIRED')
            configure_factory(self,reader=reader,product=product,control_mode=control_mode,directory=directory,
                config=config,flags=(swap_saved_b_tail,zero_use_reselect,item_transfer_ui,npc_hp_feedback_only))
            return
        if product == 'sibling-background-repeated-player-life-spawn':
            from tools.local_original_session.repeated_player_life_focused import configure_factory
            configure_factory(self,reader=reader,product=product,control_mode=control_mode,directory=directory,
                config=config,flags=(swap_saved_b_tail,zero_use_reselect,item_transfer_ui,npc_hp_feedback_only))
            return
        if product == SHOP_INPUT_PROFILE:
            from tools.local_original_session.canonical_feature_bootstrap import configure_shop_input_factory
            need(not npc_dead_goal_only, 'SHOP_INPUT_NO_DEAD_GOAL_FEATURE_REQUIRED')
            configure_shop_input_factory(self,reader=reader,product=product,control_mode=control_mode,
                directory=directory,config=config,flags=(swap_saved_b_tail,zero_use_reselect,
                                                       item_transfer_ui,npc_hp_feedback_only))
            return
        if product in ('canonical-selected-features-v1','sibling-background-skill-buff-spawn','sibling-background-skill-buff-whole-entry-spawn'):
            from tools.local_original_session.canonical_feature_bootstrap import configure_factory
            configure_factory(self, reader=reader, product=product, control_mode=control_mode,
                directory=directory, config=config, flags=(swap_saved_b_tail, zero_use_reselect,
                                                           item_transfer_ui, npc_hp_feedback_only))
            return
        need(getattr(config, 'canonical_bootstrap', None) is None,
             'CANONICAL_BOOTSTRAP_DEDICATED_PROFILE_REQUIRED')
        need(type(npc_hp_feedback_only) is bool, 'FEATURE_NPC_HP_FEEDBACK_EXACT_BOOL_REQUIRED')
        self.npc_hp_feedback_only = self._npc_hp_feedback_only_bound = npc_hp_feedback_only
        self._npc_hp_feedback_context = (reader, product, config, control_mode)
        self._npc_hp_feedback_observation = getattr(reader, '_hp4ec8_subscribers', None) if npc_hp_feedback_only else None
        life_enabled = getattr(config, 'player_life_policy', None) is not None
        need((getattr(config, 'npc_player_lethal_recovery_input', None) is not None)
             is (product == 'sibling-background-npc-player-lethal-recovery-spawn'),
             'FEATURE_NPC_LETHAL_EXACT_PRODUCT_CONFIGURATION_REQUIRED')
        need((product in ('sibling-background-player-death-recovery-spawn',
                         'sibling-background-npc-player-lethal-recovery-spawn')) is life_enabled,
             'FEATURE_PLAYER_LIFE_EXACT_DEDICATED_PROFILE_REQUIRED')
        if life_enabled:
            from tools.local_original_session import player_death_recovery_focused as life_focused
            from tools.local_original_session.player_death_recovery_focused import DEAD_DLL_SHA, DEAD_DLL_PATH
            npc_lethal = product == 'sibling-background-npc-player-lethal-recovery-spawn'
            if npc_lethal:
                from tools.local_original_session import npc_player_lethal_recovery_focused as life_focused
            life_focused.configuration(config);life_focused.broker_options(config)
            from tools.local_original_session import player_life
            need(config.player_life_policy.label == (player_life.NPC_POLICY_LABEL if npc_lethal else player_life.POLICY_LABEL),
                 'FEATURE_PLAYER_LIFE_PRODUCTION_LOCAL_POLICY_REQUIRED')
            from tools.local_original_session.player_life_observe import source_ready
            source_ready()
            need(PRODUCTS[product].get('player_death_recovery') is True
                 and PRODUCTS[product]['bridges']['own-login-bridge-dg49.dll'] == DEAD_DLL_SHA
                 and PRODUCTS[product]['bridge_artifact'] == ROOT/DEAD_DLL_PATH
                 and PRODUCTS[product].get('continuous_manual_attack') is False
                 and PRODUCTS[product].get('manual_attack_move_replacement') is False,
                 'FEATURE_PLAYER_LIFE_EXACT_NATIVE_BINDING_REQUIRED')
        if (getattr(config, 'item_transfer_policy', None) is not None
                or getattr(config, 'inventory_custody_policy', None) is not None):
            from tools.local_original_session.item_transfer_session import factory_preflight
            factory_preflight(config, product=product, control_mode=control_mode,
                swap_saved_b_tail=swap_saved_b_tail, zero_use_reselect=zero_use_reselect)
        if product == 'sibling-background-hp-status-png-spawn':config = hp_status_png_config(config)
        self.reader, self.directory = reader, directory
        self.config, self.product = config, product
        self._npc_dead_goal_preflight()
        self._npc_hp_feedback_preflight()
        if self.npc_hp_feedback_only:
            need(self._npc_hp_feedback_observation.result is None
                 and self._npc_hp_feedback_observation.trigger is None,
                 'FEATURE_NPC_HP_FEEDBACK_FRESH_ONCE_REQUIRED')
        need(type(item_transfer_ui) is bool, 'FEATURE_ITEM_TRANSFER_UI_BOOL_REQUIRED')
        need(product != 'sibling-background-item-drop-pickup-spawn'
             or type(ITEM_TRANSFER_UI_DLL_SHA) is str and product in PRODUCTS,
             'FEATURE_ITEM_TRANSFER_UI_NATIVE_NOT_REGISTERED')
        self.item_transfer_ui = self._item_transfer_ui_bound = item_transfer_ui
        self._transfer_ui_spec = PRODUCTS[product]
        self._transfer_ui_context = (product, config, control_mode)
        need((product == 'sibling-background-item-drop-pickup-spawn') is item_transfer_ui,
             'FEATURE_ITEM_TRANSFER_UI_EXACT_PRODUCT_REQUIRED')
        need(type(swap_saved_b_tail) is bool, 'FEATURE_SWAP_SAVED_B_TAIL_BOOL_REQUIRED')
        self.swap_saved_b_tail = self._swap_saved_b_tail_bound = swap_saved_b_tail
        need(type(zero_use_reselect) is bool and (not zero_use_reselect or swap_saved_b_tail is False),
             'FEATURE_ZERO_USE_RESELECT_BOOL_EXCLUSIVE_REQUIRED')
        self.zero_use_reselect = self._zero_use_reselect_bound = zero_use_reselect
        self._zero_use_context = (product, config, control_mode)
        self.zero_use_profile = product == 'sibling-background-item-equipment-zero-use-reselect-spawn'
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
                 and self.inventory and (config.inventory_store_policy == inventory_store.POLICY
                 or (self.npc_hp_feedback_only or self.npc_dead_goal_only or product in ('sibling-background-item-equipment-swap-reselect-spawn', 'sibling-background-item-equipment-current-entry-tail-spawn', 'sibling-background-item-equipment-zero-use-reselect-spawn', 'sibling-background-item-drop-pickup-spawn'))
                 and config.inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY)
                 and config.inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
                 and config.restart_policy == restart.POLICY,
                 'FEATURE_EXPLICIT_STORED_INVENTORY_RESELECTION_POLICY_REQUIRED')
        self.inventory_missing_row_policy = getattr(config, 'inventory_missing_row_policy', None)
        need(self.inventory_missing_row_policy is None or type(self.inventory_missing_row_policy) is str
             and self.inventory_missing_row_policy == 'EXPLICIT_LOCAL_CONFIGURED_STARTER_IF_MISSING'
             and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION,
             'FEATURE_EXPLICIT_MISSING_ROW_POLICY_REQUIRED')
        need(not self.inventory or control_mode == 'manual', 'MANUAL_CONTROL_MODE_REQUIRED')
        from tools.local_original_session.feature_config import ATTACK_INTENT_POLICY
        self.allow_attack = (PRODUCTS[product].get('continuous_manual_attack') is True
                             and config.attack_policy == ATTACK_INTENT_POLICY)
        self.allow_attack_replacement = (PRODUCTS[product].get('manual_attack_move_replacement') is True
                                         and self.allow_attack)
        # Backend CS0960 policy and optional NativeUse IPC capability differ.
        from tools.local_original_session.item_use_session import POLICY as ITEM_USE_POLICY
        self.item_use_enabled = type(config.item_use_policy) is str and config.item_use_policy == ITEM_USE_POLICY
        self.allow_use_item = PRODUCTS[product].get('manual_use_item') is True and self.item_use_enabled
        self.mark_on_current_indicator = PRODUCTS[product].get('mark_on_current_indicator') is True
        need(not self.mark_on_current_indicator or product == 'sibling-background-normal-open-use-mark-on-spawn', 'FEATURE_MARK_ON_EXACT_PRODUCT_REQUIRED')
        self.normal_open_use_current_ui = PRODUCTS[product].get('normal_open_use_current_ui') is True
        self.use_item_already_open = PRODUCTS[product].get('use_item_already_open') is True
        self.use_item_current_entry = PRODUCTS[product].get('use_item_current_entry') is True
        self.allow_selected_slot_lookup_role = PRODUCTS[product].get('selected_slot_lookup_role') is True
        self.swap_reselect = PRODUCTS[product].get('item_equipment_swap_reselect') is True
        self.inventory_collection_policy = getattr(config, 'inventory_collection_policy', None)
        self.inventory_collection_grant = getattr(config, 'inventory_collection_grant', None)
        need(self.swap_reselect or self.item_transfer_ui or self.npc_hp_feedback_only or self.npc_dead_goal_only or self.inventory_collection_policy is None
             and self.inventory_collection_grant is None, 'FEATURE_COLLECTION_EXACT_SWAP_PRODUCT_REQUIRED')
        self.reselect_equipment_restore = PRODUCTS[product].get('item_equipment_reselect_restore') is True
        self.allow_inventory_ui_open = PRODUCTS[product].get('inventory_ui_open') is True
        self.allow_equipment_ui_observe = PRODUCTS[product].get('item_equipment_ui_observe') is True
        self.item_equipment_policy = config.item_equipment_policy
        if self.item_equipment_policy is not None:
            from tools.local_original_session.item_equipment_effect import POLICY
            need(type(self.item_equipment_policy) is str and self.item_equipment_policy == POLICY
                 and type(config.item_equipment_first_enable) is bool and self.item_use_enabled
                 and self.inventory and config.inventory_store_policy is not None
                 and config.inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
                 and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION,
                 'FEATURE_EXPLICIT_ITEM_EQUIPMENT_CONFIG_REQUIRED')
        else:
            need(config.item_equipment_first_enable is False,
                 'FEATURE_ITEM_EQUIPMENT_FIRST_ENABLE_WITHOUT_POLICY')
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
        need(not self.use_item_already_open or (self.normal_open_use_current_ui or self.swap_reselect)
             and self.allow_use_item and self.allow_inventory_ui_open,
             'FEATURE_EXPLICIT_ALREADY_OPEN_USE_PRODUCT_REQUIRED')
        if self.allow_inventory_ui_open:
            need(self._transfer_ui_configured() if self.item_transfer_ui
                 else self._zero_use_reselect_configured() if self.zero_use_profile
                 else self._swap_reselect_configured() if self.swap_reselect
                 else self._reselect_equipment_restore_configured() if self.reselect_equipment_restore
                 else self._normal_open_use_configured() if self.normal_open_use_current_ui
                 else self._inventory_ui_open_configured(), 'FEATURE_EXPLICIT_SAVED_INVENTORY_UI_OPEN_REQUIRED')
        self.ui_inventory_update_only = product == 'sibling-background-item-equipment-ui-update-spawn'
        if self.ui_inventory_update_only:
            need(self._ui_inventory_update_configured(), 'FEATURE_UI_UPDATE_ONLY_CONFIG_REQUIRED')
        need(self.zero_use_profile is self.zero_use_reselect
             and (not self.zero_use_reselect or self._zero_use_reselect_configured()),
             'FEATURE_ZERO_USE_RESELECT_PRODUCT_REQUIRED')
        need(self._transfer_ui_configured() if self.item_transfer_ui else
             self.use_item_current_entry is self.swap_saved_b_tail
             and (not self.use_item_current_entry or product == 'sibling-background-item-equipment-current-entry-tail-spawn'),
             'FEATURE_SWAP_CURRENT_ENTRY_TAIL_PRODUCT_REQUIRED')
        need(not self.swap_saved_b_tail or self.swap_reselect and self._swap_reselect_configured(),
             'FEATURE_SWAP_SAVED_B_TAIL_PRODUCT_REQUIRED')
        self.npc_factory = None
        self.lethal_attack_preparation = False
        self.allow_respawn_attack = PRODUCTS[product].get('allow_respawn_attack') is True
        self.npc_respawn_policy = config.npc_respawn_policy
        self.npc_respawn_spawn = config.npc_respawn_spawn
        if (PRODUCTS[product].get('npc_respawn_lifecycle') is True
                or self.npc_respawn_policy is not None or self.npc_respawn_spawn is not None):
            from tools.local_original_session import feature_config, npc_respawn, npc_hp, npc_death, npc, attack_session
            need(type(config) is feature_config.Features
                 and product in ('sibling-background-npc-respawn-spawn', 'sibling-background-npc-respawn-next-hit')
                 and PRODUCTS[product].get('npc_respawn_lifecycle') is True
                 and type(self.npc_respawn_policy) is str and self.npc_respawn_policy == npc_respawn.POLICY
                 and type(self.npc_respawn_spawn) is npc.NpcSpawn and len(config.spawns) == 1
                 and config.interval_ns is not None
                 and type(config.attack_hp_provider) is npc_hp.ExplicitInputs
                 and config.npc_death_policy == npc_death.DEATH_POLICY
                 and config.npc_remove_policy == npc_death.REMOVE_POLICY
                 and type(config.attack_feedback) is attack_session.FeedbackConfig
                 and self.allow_attack and config.goal is None,
                 'FEATURE_EXPLICIT_NPC_RESPAWN_PRODUCT_REQUIRED')
            recipe = config.spawns[0]
            need(dict(recipe.fields) == dict(self.npc_respawn_spawn.fields)
                 and recipe.map_id == self.npc_respawn_spawn.map_id
                 and recipe.policy == self.npc_respawn_spawn.policy,
                 'FEATURE_NPC_RESPAWN_EXACT_ORIGINAL_RECIPE_REQUIRED')
            rows = config.attack_hp_provider.rows
            need(type(rows) is tuple and len(rows) == 1 and type(rows[0]) is npc_hp.Inputs
                 and rows[0].target == npc_hp.Target(recipe.uid, recipe.map_id,
                                                    recipe.fields[3], recipe.fields[39])
                 and rows[0].hit.landed is True and rows[0].hit.damage >= rows[0].hp.current,
                 'FEATURE_NPC_RESPAWN_EXPLICIT_LETHAL_PREPARATION_REQUIRED')
            self.lethal_attack_preparation = True
            self.allow_attack_replacement = False
        need(not self.allow_respawn_attack or product == 'sibling-background-npc-respawn-next-hit'
             and self.lethal_attack_preparation is True,
             'FEATURE_RESPAWN_ATTACK_EXACT_PRODUCT_REQUIRED')
        if config.interval_ns is not None:
            from tools.local_original_session.npc_session import NpcSessionConfig, NpcSessionFactory
            self.npc_factory = NpcSessionFactory(reader, config=NpcSessionConfig(
                spawns=config.spawns, interval_ns=config.interval_ns,
                policy=config.motion_policy, goal_policy=config.goal_policy,
                respawn_policy=self.npc_respawn_policy))

        self.npc_player_hit_policy = getattr(config, 'npc_player_hit_policy', None)
        self.npc_player_hit_input = getattr(config, 'npc_player_hit_input', None)
        self.npc_player_hit_enabled = self.npc_player_hit_policy is not None or self.npc_player_hit_input is not None
        need((product == 'sibling-background-npc-player-hit-spawn') is self.npc_player_hit_enabled,
             'FEATURE_NPC_PLAYER_HIT_EXPLICIT_PRODUCT_REQUIRED')
        self.npc_approach_hit_policy = config.npc_approach_hit_policy
        self.npc_approach_hit_input = config.npc_approach_hit_input
        self.npc_approach_hit_enabled = (self.npc_approach_hit_policy is not None
                                         or self.npc_approach_hit_input is not None)
        need((product == 'sibling-background-npc-approach-player-hit-spawn') is self.npc_approach_hit_enabled,
             'FEATURE_NPC_APPROACH_EXPLICIT_PRODUCT_REQUIRED')
        self.npc_player_hit_repeated_policy = config.npc_player_hit_repeated_policy
        self.npc_player_hit_repeated_input = config.npc_player_hit_repeated_input
        self.npc_player_hit_repeated_enabled = (self.npc_player_hit_repeated_policy is not None
                                              or self.npc_player_hit_repeated_input is not None)
        need((product in ('sibling-background-npc-player-hit-repeated-spawn',
                           'sibling-background-npc-approach-player-hit-spawn')) is self.npc_player_hit_repeated_enabled
             and not (self.npc_player_hit_enabled and self.npc_player_hit_repeated_enabled),
             'FEATURE_NPC_PLAYER_HIT_REPEATED_EXCLUSIVE_PRODUCT_REQUIRED')
        self.hp_status_policy = getattr(config, 'hp_status_policy', None)
        self.hp_status_input = getattr(config, 'hp_status_input', None)
        self.hp_status_enabled = self.hp_status_policy is not None or self.hp_status_input is not None
        need(not self.hp_status_enabled or self._hp_status_configured(),
             'FEATURE_EXACT_HP_STATUS_SOURCE_QUIT_CONFIG_REQUIRED')

    def _transfer_ui_configured(self):
        from tools.local_original_session.item_transfer_ui import configured
        return configured(self)

    def _npc_player_hit_configured(self):
        from tools.local_original_session.npc_player_hit_focused import configuration
        try:
            configuration(self.config, inventory=self.inventory, auto_inventory=True)
        except (ValueError, TypeError, AttributeError):
            return False
        return (self.product == 'sibling-background-npc-player-hit-spawn'
            and self.manual and not self.allow_attack and not self.allow_use_item
            and self.npc_factory is not None
            and self.npc_player_hit_policy is self.config.npc_player_hit_policy
            and self.npc_player_hit_input is self.config.npc_player_hit_input)

    def _npc_approach_hit_configured(self):
        from tools.local_original_session.npc_approach_hit_focused import configuration
        try:
            configuration(self.config, inventory=self.inventory, auto_inventory=True)
        except (ValueError, TypeError, AttributeError):
            return False
        return (self.product == 'sibling-background-npc-approach-player-hit-spawn'
            and self.manual and not self.allow_attack and not self.allow_use_item
            and self.npc_factory is not None
            and self.npc_approach_hit_policy is self.config.npc_approach_hit_policy
            and self.npc_approach_hit_input is self.config.npc_approach_hit_input)

    def _npc_player_hit_repeated_configured(self):
        if self.npc_approach_hit_enabled:
            return self._npc_approach_hit_configured()
        from tools.local_original_session.npc_player_hit_focused import repeated_configuration
        try:
            repeated_configuration(self.config, inventory=self.inventory, auto_inventory=True)
        except (ValueError, TypeError, AttributeError):
            return False
        return (self.product == 'sibling-background-npc-player-hit-repeated-spawn'
            and self.manual and not self.allow_attack and not self.allow_use_item
            and self.npc_factory is not None
            and self.npc_player_hit_repeated_policy is self.config.npc_player_hit_repeated_policy
            and self.npc_player_hit_repeated_input is self.config.npc_player_hit_repeated_input)

    def _hp_status_configured(self):
        if self.npc_player_hit_repeated_enabled:
            return self._npc_player_hit_repeated_configured()
        if self.npc_player_hit_enabled:
            return self._npc_player_hit_configured()
        from tools.local_original_session import feature_config, hp_status, inventory, inventory_store, restart
        from tools.local_native_login_spawn_render_retry_runtime import spawn_hook
        c = self.config
        return (self.product in ('sibling-background-source-quit-spawn', 'sibling-background-hp-status-png-spawn')
            and type(c) is feature_config.Features
            and type(c.hp_status_policy) is str and c.hp_status_policy == hp_status.POLICY
            and type(c.hp_status_input) is feature_config.HpStatusInput
            and (self.product != 'sibling-background-hp-status-png-spawn'
                 or c.hp_status_input.current_hp == 19 and c.hp_status_input.maximum_hp == 20
                 and c.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
                 and c.restart_policy == restart.POLICY)
            and type(c.hp_status_input.observe_hud_bar) is bool
            and c.hp_status_input.scope == feature_config.HP_STATUS_SCOPE
            and c.hp_status_input.target_uid == spawn_hook.profiles()[0].fields[1]
            and c.hp_status_input.map_id == 0
            and self.manual and self.inventory and not self.allow_attack and not self.allow_use_item
            and c.inventory_policy == inventory.POLICY and type(c.inventory_frame) is bytes
            and c.inventory_store_policy == inventory_store.POLICY
            and c.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
            and c.inventory_missing_row_policy is None and not c.spawns
            and all(getattr(c, name) is None for name in ('interval_ns','motion_policy','goal_policy','goal',
                'attack_policy','attack_feedback','attack_hp_provider','npc_death_policy','npc_remove_policy',
                'npc_respawn_policy','npc_respawn_spawn','item_use_policy','item_equipment_policy','inventory_update_policy'))
            and c.item_equipment_first_enable is False)

    def _swap_reselect_configured(self):
        from tools.local_original_session import inventory, inventory_store, restart, item_use_session, item_equipment_effect
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION, LOCAL_WORLD_READY_ONCE
        c = self.config
        grant = self.inventory_collection_grant
        return (self.product in ('sibling-background-item-equipment-swap-reselect-spawn', 'sibling-background-item-equipment-current-entry-tail-spawn') and self.swap_reselect
            and self.inventory and self.allow_use_item
            and (self.use_item_already_open if self.product == 'sibling-background-item-equipment-swap-reselect-spawn'
                 else self.use_item_current_entry and self.swap_saved_b_tail)
            and self.allow_source_restart and self.allow_source_reselect
            and self.allow_inventory_ui_open and self.allow_equipment_ui_observe
            and not self.reselect_equipment_restore and not self.normal_open_use_current_ui
            and not self.mark_on_current_indicator and not self.allow_selected_slot_lookup_role
            and not self.manual and not self.allow_attack and not self.allow_attack_replacement
            and not self.allow_inventory_update and c.inventory_update_policy is None
            and type(self.inventory_collection_policy) is str and self.inventory_collection_policy == inventory.COLLECTION_POLICY
            and type(grant) is tuple and len(grant) == 2
            and type(grant[0]) is str and grant[0] == inventory_store.SECOND_INSTANCE_POLICY
            and type(grant[1]) is frozenset and len(grant[1]) <= 4096
            and all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in grant[1])
            and c.inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
            and c.inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
            and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
            and c.inventory_missing_row_policy is None and c.item_equipment_first_enable is False
            and c.restart_policy == restart.POLICY and c.item_use_policy == item_use_session.POLICY
            and c.item_equipment_policy == item_equipment_effect.POLICY
            and not c.spawns and all(getattr(c, name) is None for name in
                ('interval_ns','motion_policy','goal_policy','goal','attack_policy','attack_feedback',
                 'attack_hp_provider','npc_death_policy','npc_remove_policy','npc_respawn_policy','npc_respawn_spawn',
                 'hp_status_policy','hp_status_input')))

    def _zero_use_reselect_configured(self):
        from tools.local_original_session.item_equipment_swap import configuration
        configuration(self.config, inventory=self.inventory, auto_inventory=True)
        c, context = self.config, self._zero_use_context
        return (self.product == 'sibling-background-item-equipment-zero-use-reselect-spawn' and self.zero_use_profile is True
            and self.zero_use_reselect is self._zero_use_reselect_bound is True
            and self.swap_saved_b_tail is self._swap_saved_b_tail_bound is False
            and context[0] == self.product and context[1] is c and context[2] == 'manual'
            and PRODUCTS[self.product].get('item_equipment_zero_use_reselect') is True
            and self.swap_reselect and self.inventory and self.item_use_enabled
            and self.allow_use_item is self.use_item_already_open is self.use_item_current_entry is False
            and self.allow_source_restart and self.allow_source_reselect
            and self.allow_inventory_ui_open and self.allow_equipment_ui_observe
            and not self.reselect_equipment_restore and not self.normal_open_use_current_ui
            and not self.mark_on_current_indicator and not self.allow_selected_slot_lookup_role
            and not self.manual and not self.allow_attack and not self.allow_attack_replacement
            and not self.allow_inventory_update
            and self.inventory_collection_policy == c.inventory_collection_policy
            and self.inventory_collection_grant is c.inventory_collection_grant
            and self.inventory_reselection_policy == c.inventory_reselection_policy
            and self.item_equipment_policy == c.item_equipment_policy)

    def _reselect_equipment_restore_configured(self):
        from tools.local_original_session.item_equipment_reselect_restore import PROFILE, configuration
        configuration(self.config, inventory=self.inventory, auto_inventory=True)
        return (self.product == PROFILE and self.reselect_equipment_restore
            and self.allow_source_restart and self.allow_source_reselect
            and self.allow_inventory_ui_open and self.allow_equipment_ui_observe
            and not self.allow_use_item and not self.use_item_already_open
            and not self.normal_open_use_current_ui and not self.mark_on_current_indicator
            and not self.allow_selected_slot_lookup_role and not self.allow_inventory_update
            and not self.manual and not self.allow_attack and not self.allow_attack_replacement)


    def _normal_open_use_configured(self):
        from tools.local_original_session import inventory_store, restart
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION, LOCAL_WORLD_READY_ONCE
        from tools.local_original_session.item_use_session import POLICY as USE_POLICY
        from tools.local_original_session.item_equipment_effect import POLICY as EFFECT_POLICY
        c = self.config
        return (self.product in ('sibling-background-normal-open-use-current-ui-spawn', 'sibling-background-normal-open-use-mark-on-spawn')
            and self.mark_on_current_indicator is (self.product == 'sibling-background-normal-open-use-mark-on-spawn') and self.normal_open_use_current_ui
            and self.use_item_already_open and self.allow_inventory_ui_open and self.allow_use_item
            and self.allow_equipment_ui_observe and not self.allow_selected_slot_lookup_role
            and self.inventory and not self.manual and not self.allow_attack and not self.allow_attack_replacement
            and not self.allow_inventory_update and c.inventory_missing_row_policy is None
            and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
            and c.inventory_store_policy == inventory_store.POLICY and c.inventory_delivery_policy == LOCAL_WORLD_READY_ONCE
            and c.restart_policy == restart.POLICY and c.item_use_policy == USE_POLICY
            and c.item_equipment_policy == EFFECT_POLICY and c.item_equipment_first_enable is False
            and c.inventory_update_policy is None and not c.spawns
            and c.attack_policy is c.attack_feedback is c.interval_ns is c.motion_policy is c.goal_policy is c.goal is None
            and c.attack_hp_provider is c.npc_death_policy is c.npc_remove_policy is c.npc_respawn_policy is None)

    def _inventory_ui_open_configured(self):
        from tools.local_original_session import inventory_store, restart
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION, LOCAL_WORLD_READY_ONCE
        c = self.config
        return (self.product in ('sibling-background-inventory-ui-open-spawn', 'sibling-background-inventory-ui-open-selected-slot-lookup-role-spawn', 'sibling-background-original-screenshot-spawn')
            and (self.allow_selected_slot_lookup_role is (self.product == 'sibling-background-inventory-ui-open-selected-slot-lookup-role-spawn'))
            and self.allow_inventory_ui_open and self.inventory and self.allow_equipment_ui_observe
            and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
            and c.inventory_store_policy == inventory_store.POLICY
            and c.inventory_delivery_policy == LOCAL_WORLD_READY_ONCE and c.inventory_missing_row_policy is None
            and c.restart_policy == restart.POLICY and c.item_use_policy is None
            and c.item_equipment_policy is None and c.item_equipment_first_enable is False
            and c.inventory_update_policy is None and not self.allow_use_item and not self.allow_inventory_update
            and not self.manual and not self.allow_attack and c.attack_policy is None and c.attack_feedback is None
            and not c.spawns and c.interval_ns is c.motion_policy is c.goal_policy is c.goal is None
            and c.attack_hp_provider is c.npc_death_policy is c.npc_remove_policy is None
            and c.npc_respawn_policy is c.npc_respawn_spawn is None)

    def _ui_inventory_update_configured(self):
        # One exact configuration predicate for Factory and pre-Native Quit.
        from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION
        config = self.config
        return (self.product == 'sibling-background-item-equipment-ui-update-spawn'
            and self.ui_inventory_update_only and self.inventory and self.allow_inventory_update
            and self.allow_equipment_ui_observe
            and self.inventory_reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
            and config.inventory_missing_row_policy is None
            and config.item_use_policy is None and self.item_equipment_policy is None
            and config.item_equipment_first_enable is False
            and not self.allow_use_item and not self.manual and not self.allow_attack
            and config.attack_policy is None and config.attack_feedback is None
            and not config.spawns and config.interval_ns is None
            and config.attack_hp_provider is None and config.npc_death_policy is None
            and config.npc_remove_policy is None)

    @property
    def enabled(self):
        return self.manual or self.inventory or self.npc_factory is not None

    def _transfer_preflight_current(self):
        need(self.item_transfer_ui is self._item_transfer_ui_bound
             and (not self.item_transfer_ui or self._transfer_ui_configured()),
             'FEATURE_ITEM_TRANSFER_UI_BINDING_CHANGED')
        original = self._zero_use_context
        old, current = original[1], self.config
        if any(getattr(c,n,None) is not None for c in (old,current)
               for n in ('item_transfer_policy','inventory_custody_policy')):
            need(current is old and self.product == original[0],
                 'FEATURE_ITEM_TRANSFER_CONFIG_BINDING_CHANGED')
            from tools.local_original_session.item_transfer_session import factory_preflight
            factory_preflight(current,product=self.product,control_mode=original[2],
                swap_saved_b_tail=self.swap_saved_b_tail,zero_use_reselect=self.zero_use_reselect)
            return True
        return False

    def inventory_owner_guard(self, retained):
        if self.product == SHOP_INPUT_PROFILE:
            from tools.local_original_session.canonical_feature_bootstrap import check_shop_input_factory
            check_shop_input_factory(self)
            need(type(retained) is NativeOwner, 'FEATURE_INVENTORY_SYNC_NATIVE_OWNER_REQUIRED')
            guard = retained.guard_exact_sync
            need(getattr(guard, '__self__', None) is retained
                 and getattr(guard, '__func__', None) is NativeOwner.guard_exact_sync
                 and not asyncio.iscoroutinefunction(guard), 'FEATURE_INVENTORY_SYNC_ORIGINAL_GUARD_REQUIRED')
            return guard
        if self.product in ('canonical-selected-features-v1','sibling-background-npc-continuous-retaliation-spawn','sibling-background-npc-single-retaliation-spawn','sibling-background-npc-respawn-target-hit-spawn','sibling-background-repeated-player-life-spawn','sibling-background-skill-buff-spawn','sibling-background-skill-buff-whole-entry-spawn'):
            self.config.canonical_bootstrap.factory_current(self)
            if self.product in ('sibling-background-npc-continuous-retaliation-spawn','sibling-background-npc-single-retaliation-spawn','sibling-background-npc-respawn-target-hit-spawn','sibling-background-repeated-player-life-spawn','sibling-background-skill-buff-spawn','sibling-background-skill-buff-whole-entry-spawn'):
                need(type(retained) is NativeOwner, 'FEATURE_INVENTORY_SYNC_NATIVE_OWNER_REQUIRED')
                guard = retained.guard_exact_sync
                need(getattr(guard, '__self__', None) is retained
                     and getattr(guard, '__func__', None) is NativeOwner.guard_exact_sync
                     and not asyncio.iscoroutinefunction(guard),
                     'FEATURE_INVENTORY_SYNC_ORIGINAL_GUARD_REQUIRED')
                return guard
            return None
        if self._transfer_preflight_current():
            need(type(retained) is NativeOwner, 'FEATURE_INVENTORY_SYNC_NATIVE_OWNER_REQUIRED')
            guard=retained.guard_exact_sync
            need(getattr(guard,'__self__',None) is retained and
                 getattr(guard,'__func__',None) is NativeOwner.guard_exact_sync and
                 not asyncio.iscoroutinefunction(guard), 'FEATURE_INVENTORY_SYNC_ORIGINAL_GUARD_REQUIRED')
            return guard
        """Explicit current-entry or zero-Use saved-B restore, each exact opt-in."""
        need(self.zero_use_reselect is self._zero_use_reselect_bound,
             'FEATURE_ZERO_USE_RESELECT_BINDING_CHANGED')
        if self.product == 'sibling-background-item-equipment-zero-use-reselect-spawn':
            need(self.zero_use_reselect is True and self._zero_use_reselect_configured(),
                 'FEATURE_INVENTORY_SYNC_OWNER_EXACT_ZERO_REQUIRED')
            need(type(retained) is NativeOwner, 'FEATURE_INVENTORY_SYNC_NATIVE_OWNER_REQUIRED')
            guard = retained.guard_exact_sync
            need(getattr(guard, '__self__', None) is retained
                 and getattr(guard, '__func__', None) is NativeOwner.guard_exact_sync
                 and not asyncio.iscoroutinefunction(guard),
                 'FEATURE_INVENTORY_SYNC_ORIGINAL_GUARD_REQUIRED')
            return guard
        need(self.zero_use_reselect is False, 'FEATURE_ZERO_USE_RESELECT_PRODUCT_REQUIRED')
        if self.product != 'sibling-background-item-equipment-current-entry-tail-spawn':
            need(self.swap_saved_b_tail is self._swap_saved_b_tail_bound is False,
                 'FEATURE_SWAP_SAVED_B_TAIL_BINDING_CHANGED')
            return None
        need(self.swap_saved_b_tail is self._swap_saved_b_tail_bound is True
             and self._swap_reselect_configured(),
             'FEATURE_INVENTORY_SYNC_OWNER_EXACT_TAIL_REQUIRED')
        need(type(retained) is NativeOwner, 'FEATURE_INVENTORY_SYNC_NATIVE_OWNER_REQUIRED')
        guard = retained.guard_exact_sync
        need(getattr(guard, '__self__', None) is retained
             and getattr(guard, '__func__', None) is NativeOwner.guard_exact_sync
             and not asyncio.iscoroutinefunction(guard),
             'FEATURE_INVENTORY_SYNC_ORIGINAL_GUARD_REQUIRED')
        return guard

    def _npc_dead_goal_preflight(self):
        need(self.npc_dead_goal_only is self._npc_dead_goal_only_bound,
             'FEATURE_NPC_DEAD_GOAL_MODE_CHANGED')
        if not self.npc_dead_goal_only:
            return
        reader, product, config, control_mode = self._npc_dead_goal_context
        need(reader is self.reader and config is self.config and product == self.product
             and product == 'sibling-background-source-quit-spawn' and control_mode == 'manual',
             'FEATURE_NPC_DEAD_GOAL_EXACT_PRODUCT_REQUIRED')
        if self.config.inventory_collection_policy is None:
            return  # Existing singleton opt-in and all default behavior stay intact.
        from tools.local_original_session.npc_dead_goal_focused import collection_configuration
        collection_configuration(self.config)
        if hasattr(self, 'inventory_collection_policy'):
            need(type(self.inventory_collection_policy) is str
                 and self.inventory_collection_policy == config.inventory_collection_policy
                 and self.inventory_collection_grant is config.inventory_collection_grant
                 and type(self.inventory_reselection_policy) is str
                 and self.inventory_reselection_policy == config.inventory_reselection_policy
                 and self.inventory is self.manual is self.allow_attack is True,
                 'FEATURE_NPC_DEAD_GOAL_COLLECTION_BINDING_CHANGED')

    def _npc_hp_feedback_preflight(self):
        need(self.npc_hp_feedback_only is self._npc_hp_feedback_only_bound,
             'FEATURE_NPC_HP_FEEDBACK_CAPABILITY_CHANGED')
        if not self.npc_hp_feedback_only:
            return
        from tools.local_original_session import feature_config, npc_hp, attack_session, inventory, inventory_store, restart
        from tools.local_original_session.hp4ec8_subscribers import Observation
        reader, product, config, control_mode = self._npc_hp_feedback_context
        spec = PRODUCTS[product]
        observation = self._npc_hp_feedback_observation
        need(reader is self.reader and config is self.config and product == self.product
             and product == 'sibling-background-source-quit-spawn' and control_mode == 'manual'
             and spec['bridges'].get('own-login-bridge-dg49.dll') == 'd5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d'
             and all(spec.get(key) is True for key in ('require_background','background_display_guard',
                 'manual_only','manual_source_quit','require_source_quit','continuous_manual_move',
                 'continuous_manual_attack','manual_attack_move_replacement'))
             and type(observation) is Observation and observation.reader is reader
             and getattr(reader, '_hp4ec8_subscribers', None) is observation
             and observation.stage == 'npc-hp-feedback-drained',
             'FEATURE_NPC_HP_FEEDBACK_EXACT_PRODUCT_STAGE_REQUIRED')
        need(type(config) is feature_config.Features and len(config.spawns) == 1
             and config.attack_policy == feature_config.ATTACK_INTENT_POLICY
             and type(config.attack_hp_provider) is npc_hp.ExplicitInputs
             and type(config.attack_feedback) is attack_session.FeedbackConfig
             and config.interval_ns is config.motion_policy is config.goal_policy is config.goal is None
             and config.npc_death_policy is config.npc_remove_policy is config.player_life_policy is None,
             'FEATURE_NPC_HP_FEEDBACK_EXPLICIT_NONLETHAL_REQUIRED')
        inputs, = config.attack_hp_provider.rows
        spawn, = config.spawns
        need(inputs.target == npc_hp.Target(spawn.uid, spawn.map_id, spawn.fields[3], spawn.fields[39])
             and inputs.hit.landed is True and 0 < inputs.hit.damage < inputs.hp.current,
             'FEATURE_NPC_HP_FEEDBACK_EXACT_HP_TARGET_REQUIRED')
        grant = config.inventory_collection_grant
        need(config.inventory_policy == inventory.POLICY and type(config.inventory_frame) is bytes
             and config.inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
             and config.inventory_collection_policy == inventory.COLLECTION_POLICY
             and config.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
             and config.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
             and config.restart_policy == restart.POLICY
             and type(grant) is tuple and len(grant) == 2 and grant[0] == inventory_store.SECOND_INSTANCE_POLICY
             and type(grant[1]) is frozenset and len(grant[1]) <= 4096
             and all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in grant[1])
             and config.inventory_missing_row_policy is config.inventory_custody_policy is config.item_transfer_policy is None
             and config.item_use_policy is config.item_equipment_policy is config.inventory_update_policy is None,
             'FEATURE_NPC_HP_FEEDBACK_EXISTING_COLLECTION_REQUIRED')
        # Constructor calls this before derived attrs exist. Current consumers
        # must forward the same configured collection/reselection objects.
        if hasattr(self, 'inventory_collection_policy'):
            need(type(self.inventory_collection_policy) is str
                 and self.inventory_collection_policy == config.inventory_collection_policy
                 and self.inventory_collection_grant is config.inventory_collection_grant
                 and type(self.inventory_reselection_policy) is str
                 and self.inventory_reselection_policy == config.inventory_reselection_policy
                 and self.inventory is self.manual is self.allow_attack is True,
                 'FEATURE_NPC_HP_FEEDBACK_COLLECTION_BINDING_CHANGED')

    def broker_options(self):
        if self.product == SHOP_INPUT_PROFILE:
            from tools.local_original_session.canonical_feature_bootstrap import check_shop_input_factory
            check_shop_input_factory(self)
            return self.config.canonical_bootstrap.factory_options(self)
        if self.product in ('canonical-selected-features-v1','sibling-background-npc-continuous-retaliation-spawn','sibling-background-npc-single-retaliation-spawn','sibling-background-npc-respawn-target-hit-spawn','sibling-background-repeated-player-life-spawn','sibling-background-skill-buff-spawn','sibling-background-skill-buff-whole-entry-spawn'):
            return self.config.canonical_bootstrap.factory_options(self)
        self._npc_dead_goal_preflight()
        self._npc_hp_feedback_preflight()
        self._transfer_preflight_current()
        if self.npc_factory is not None:
            options = self.npc_factory.broker_options()
        else:
            options = dict(npc_spawns=self.config.spawns) if self.config.spawns else {}
        if self.npc_player_hit_repeated_enabled:
            need(self._npc_player_hit_repeated_configured(), 'FEATURE_NPC_PLAYER_HIT_REPEATED_CURRENT_CONFIG_REQUIRED')
            options['npc_player_hit_repeated_policy'] = self.npc_player_hit_repeated_policy
        if self.npc_player_hit_enabled:
            need(self._npc_player_hit_configured(), 'FEATURE_NPC_PLAYER_HIT_CURRENT_CONFIG_REQUIRED')
            options['npc_player_hit_policy'] = self.npc_player_hit_policy
        if self.hp_status_enabled:
            options['hp_status_policy'] = self.hp_status_policy
        if self.config.player_life_policy is not None:
            from tools.local_original_session import player_death_recovery_focused as life_focused
            if self.product == 'sibling-background-npc-player-lethal-recovery-spawn':
                from tools.local_original_session import npc_player_lethal_recovery_focused as life_focused
            options.update(life_focused.broker_options(self.config))
        if self.config.attack_policy is not None:
            need(bool(self.config.spawns), 'FEATURE_ATTACK_REQUIRES_NPC')
            options.update(attack_policy=self.config.attack_policy, attack_reader=self.reader,
                           attack_feedback=self.config.attack_feedback)
        if self.config.attack_hp_provider is not None:
            need(self.config.attack_policy is not None and bool(self.config.spawns),
                 'FEATURE_NPC_HP_REQUIRES_NPC_ATTACK')
            options['attack_hp_provider'] = self.config.attack_hp_provider
        if self.config.npc_death_policy is not None:
            options['npc_death_policy'] = self.config.npc_death_policy
        if self.config.npc_remove_policy is not None:
            options['npc_remove_policy'] = self.config.npc_remove_policy
        if self.config.restart_policy is not None:
            options.update(restart_policy=self.config.restart_policy)
        if self.config.item_use_policy is not None:
            options.update(item_use_policy=self.config.item_use_policy)
        if self.item_equipment_policy is not None:
            options.update(item_equipment_policy=self.item_equipment_policy,
                           item_equipment_first_enable=self.config.item_equipment_first_enable)
        if self.config.inventory_update_policy is not None:
            options.update(inventory_update_policy=self.config.inventory_update_policy)
        if self.inventory_reselection_policy is not None:
            options.update(inventory_reselection_policy=self.inventory_reselection_policy,
                           inventory_delivery_policy=self.config.inventory_delivery_policy)
        if self.inventory_missing_row_policy is not None:
            options['inventory_missing_row_policy'] = self.inventory_missing_row_policy
        if getattr(self.config, 'item_transfer_policy', None) is not None:
            options.update(item_transfer_policy=self.config.item_transfer_policy,
                           inventory_custody_policy=self.config.inventory_custody_policy,
                           inventory_collection_policy=self.config.inventory_collection_policy,
                           inventory_collection_grant=None)
        elif self.swap_reselect or self.npc_hp_feedback_only or self.npc_dead_goal_only:
            options.update(inventory_collection_policy=self.inventory_collection_policy,
                           inventory_collection_grant=self.inventory_collection_grant)
        if self.inventory:
            options.update(inventory_policy=self.config.inventory_policy,
                           inventory_frame=self.config.inventory_frame, inventory_reader=self.reader,
                           inventory_store_policy=self.config.inventory_store_policy)
        if getattr(self.config, 'world_policy', None) is not None:
            options['world_policy'] = self.config.world_policy
        if getattr(self.config, 'world_starter_kit', None) is not None:
            options['world_starter_kit'] = self.config.world_starter_kit
        return options

    def __call__(self, broker):
        if self.product == SHOP_INPUT_PROFILE:
            from tools.local_original_session.canonical_feature_bootstrap import check_shop_input_factory
            check_shop_input_factory(self,broker=broker)
        if self.product == 'sibling-background-npc-continuous-retaliation-spawn':
            from tools.local_original_session.npc_continuous_retaliation_runtime import build_runtime
            return build_runtime(self,broker)
        if self.product == 'sibling-background-npc-single-retaliation-spawn':
            from tools.local_original_session.npc_retaliation_runtime import build_runtime
            return build_runtime(self,broker)
        if self.product == 'sibling-background-npc-respawn-target-hit-spawn':
            from tools.local_original_session.npc_respawn_hit_runtime import build_runtime
            return build_runtime(self,broker)
        if self.product == 'sibling-background-repeated-player-life-spawn':
            from tools.local_original_session.repeated_player_life_focused import build_runtime
            return build_runtime(self,broker)
        if self.product in ('canonical-selected-features-v1','sibling-background-skill-buff-spawn','sibling-background-skill-buff-whole-entry-spawn'):
            from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatures
            return CanonicalFeatures(self.config.canonical_bootstrap, broker)
        self._npc_dead_goal_preflight()
        self._npc_hp_feedback_preflight()
        self._transfer_preflight_current()
        manual = npc_session = equipment_observer = ui_observer = ui_opener = ui_role = None
        try:
            need(self.zero_use_reselect is self._zero_use_reselect_bound
                 and self.zero_use_profile is self.zero_use_reselect
                 and (not self.zero_use_reselect or self._zero_use_reselect_configured()),
                 'FEATURE_ZERO_USE_RESELECT_POLICY_CHANGED')
            need(self._transfer_ui_configured() if self.item_transfer_ui else
                 self.swap_saved_b_tail is self._swap_saved_b_tail_bound
                 and self.use_item_current_entry is self.swap_saved_b_tail
                 and (not self.swap_saved_b_tail or self.swap_reselect and self._swap_reselect_configured()),
                 'FEATURE_SWAP_SAVED_B_TAIL_POLICY_CHANGED')
            if self.manual or self.inventory:
                from tools.local_original_session.manual_move_commands import ManualMoveCommands
                use_item_options = dict(allow_use_item=True) if self.allow_use_item else {}
                native_use_item_options = dict(use_item_options)
                if self.use_item_already_open:
                    native_use_item_options['use_item_already_open'] = True
                if self.use_item_current_entry:
                    native_use_item_options['use_item_current_entry'] = True
                if self.swap_saved_b_tail and not self.use_item_current_entry:
                    from tools.local_original_session.manual_move_commands import FIRST_ALREADY_OPEN_THEN_NORMAL
                    native_use_item_options['use_item_entry_policy'] = FIRST_ALREADY_OPEN_THEN_NORMAL
                source_restart_options = dict(allow_source_restart=True) if self.allow_source_restart else {}
                source_reselect_options = dict(allow_source_reselect=True) if self.allow_source_reselect else {}
                lethal_options = dict(lethal_attack_preparation=True) if self.lethal_attack_preparation else {}
                if self.allow_respawn_attack:
                    lethal_options['allow_respawn_attack'] = True
                manual = ManualMoveRequests(self.directory, ManualMoveCommands(
                    self.reader, current=lambda: current_manual_binding(broker),
                    allow_attack=self.allow_attack, allow_attack_replacement=self.allow_attack_replacement,
                    observe_attack_feedback=(self.config.attack_feedback is not None
                        and broker._attack_session is not None
                        and broker._attack_session.feedback is self.config.attack_feedback),
                    **dict(native_use_item_options, **source_restart_options, **source_reselect_options, **lethal_options)),
                    allow_attack=self.allow_attack,
                    allow_move=self.manual, inventory_broker=broker if self.inventory else None,
                    inventory_delivery_policy=self.config.inventory_delivery_policy,
                    inventory_missing_row_policy=self.inventory_missing_row_policy,
                    **dict(({} if self.item_transfer_ui else use_item_options), **source_restart_options, **source_reselect_options, **lethal_options,
                        **(dict(allow_inventory_update=True) if self.allow_inventory_update else {}),
                        **(dict(inventory_reselection_policy=self.inventory_reselection_policy)
                           if self.inventory_reselection_policy is not None else {})))
            if self.npc_factory is not None:
                npc_session = self.npc_factory.bind(broker)
                if self.config.goal is not None:
                    npc_session.submit_goal(goal=self.config.goal)
            if self.item_equipment_policy is not None and not self.item_transfer_ui:
                from tools.local_original_session.equipment_observe import EquipmentObserver
                equipment_observer = EquipmentObserver(broker, self.reader)
            if self.allow_equipment_ui_observe:
                from tools.local_original_session.item_equipment_ui import ItemEquipmentUIObserver
                need(equipment_observer is not None or (self.ui_inventory_update_only or self.allow_inventory_ui_open)
                     and manual is not None and manual.inventory_broker is broker
                     and manual.consumer.reader is self.reader
                     and (manual.allow_inventory_update is True or self.allow_inventory_ui_open) and manual.allow_use_item is False
                     and broker._item_equipment_effect is None and broker._item_use_session is None,
                     'FEATURE_UI_OBSERVE_EQUIPMENT_POLICY_REQUIRED')
                ui_observer = ItemEquipmentUIObserver(manual, collection_policy=self.inventory_collection_policy)
            if self.allow_inventory_ui_open:
                from tools.local_original_session.inventory_ui_open import InventoryUIOpen
                ui_opener = InventoryUIOpen(manual, collection_policy=self.inventory_collection_policy)
            if self.allow_selected_slot_lookup_role:
                from tools.local_original_session.item_equipment_ui_lookup_role import SelectedSlotLookupRole
                ui_role = SelectedSlotLookupRole(ui_observer)
            runtime = ProductFeatures(manual, npc_session, equipment_observer=equipment_observer,
                                   equipment_ui_observer=ui_observer, inventory_ui_opener=ui_opener, ui_lookup_role=ui_role,
                                   npc_respawn_policy=self.npc_respawn_policy,
                                   npc_respawn_spawn=self.npc_respawn_spawn,
                                   allow_respawn_attack=self.allow_respawn_attack,
                                   equipment_swap_reselect=self.swap_reselect,
                                   equipment_zero_use_reselect=self.zero_use_reselect)
            if self.item_transfer_ui:
                from tools.local_original_session.item_transfer_ui import ItemTransferUI
                runtime.item_transfer_ui = ItemTransferUI(runtime, broker)
            if self.mark_on_current_indicator:
                from tools.local_original_session.mark_on_install import InstallMarkOnCaller
                from tools.local_original_session.mark_on_current_indicator import MarkOnCurrentIndicator
                runtime.mark_on_installer = InstallMarkOnCaller(manual)
                runtime.mark_on_install_observation = runtime.mark_on_installer.observation()
                runtime.mark_on_indicator = MarkOnCurrentIndicator(ui_observer,runtime.mark_on_installer,ui_opener)
            if PRODUCTS[self.product].get('original_screenshot') is True:
                from tools.local_original_session.original_screenshot import OriginalScreenshotObserver
                if self.product == SHOP_INPUT_PROFILE:
                    runtime.original_screenshot = OriginalScreenshotObserver(manual,
                        collection_policy=self.inventory_collection_policy)
                else:
                    runtime.original_screenshot = OriginalScreenshotObserver(manual)
            if self.config.player_life_policy is not None:
                from tools.local_original_session import player_life, player_life_observe
                from tools.local_original_session.player_death_recovery_focused import SourceDeadRestartRequests
                if self.product == 'sibling-background-npc-player-lethal-recovery-spawn':
                    from tools.local_original_session.npc_player_lethal_recovery_focused import SourceDeadRestartRequests
                need(type(broker._player_life) is player_life.Service
                     and broker._player_life.policy is self.config.player_life_policy
                     and broker._player_life_observer is None and manual is not None,
                     'FEATURE_PLAYER_LIFE_REAL_SERVICE_REQUIRED')
                runtime.player_life_observer = player_life_observe.PlayerLifeObserver(broker,self.reader)
                broker._player_life_observer = runtime.player_life_observer
                runtime.source_dead_restart = SourceDeadRestartRequests(manual,broker)
            if self.product == SHOP_INPUT_PROFILE and getattr(self,'_shop_normal_input_spec',None) is not None:
                from tools.local_original_session import shop_normal_input_driver
                shop_normal_input_driver.attach_runtime(self,runtime,broker)
            return runtime
        except BaseException as primary:
            if self.product == SHOP_INPUT_PROFILE:
                for owned in (getattr(locals().get('runtime'), 'original_screenshot', None),
                              manual, npc_session, equipment_observer):
                    if owned is not None:
                        try:
                            owned.close()
                        except BaseException as cleanup:
                            try:
                                primary.add_note('SHOP input constructor cleanup: ' + repr(cleanup))
                            except BaseException:
                                pass
                raise
            if manual is not None:
                manual.close()
            if npc_session is not None:
                npc_session.close()
            if equipment_observer is not None:
                equipment_observer.close()
            raise


class ProductFeatures:
    def __init__(self, manual, npc_session, *, equipment_observer=None, equipment_ui_observer=None,
                 npc_respawn_policy=None, npc_respawn_spawn=None, inventory_ui_opener=None, ui_lookup_role=None,
                 allow_respawn_attack=False, equipment_swap_reselect=False, equipment_zero_use_reselect=False):
        need(type(equipment_swap_reselect) is bool, 'FEATURE_EQUIPMENT_SWAP_EXPLICIT_BOOL_REQUIRED')
        if equipment_swap_reselect:
            from tools.local_original_session import inventory
            need(type(manual) is ManualMoveRequests and equipment_observer is not None
                 and manual.inventory_collection_policy == inventory.COLLECTION_POLICY,
                 'FEATURE_EQUIPMENT_SWAP_COLLECTION_REQUIRED')
        need(type(equipment_zero_use_reselect) is bool and (not equipment_zero_use_reselect
             or equipment_swap_reselect and manual.allow_use_item is False
             and manual.consumer.allow_use_item is False), 'FEATURE_ZERO_USE_RESELECT_RUNTIME_REQUIRED')
        self._equipment_zero_use_reselect = self._equipment_zero_use_reselect_bound = equipment_zero_use_reselect
        self._equipment_swap_reselect = equipment_swap_reselect
        self.manual, self.npc_session = manual, npc_session
        self._closed = False
        self.item_transfer_ui = None
        self._equipment_turn = False
        self._npc_turn = False
        self._npc_poll_monitor = SimpleNamespace(next_memory=0.0)
        self._npc_bound_monitor = self._npc_poll_monitor
        self._npc_respawn_policy, self._npc_respawn_spawn = npc_respawn_policy, npc_respawn_spawn
        self._npc_respawning = False
        self._npc_respawn_receipt = None
        need(type(allow_respawn_attack) is bool and (not allow_respawn_attack
             or type(manual) is ManualMoveRequests and manual.allow_respawn_attack is True),
             'FEATURE_RESPAWN_ATTACK_EXPLICIT_RUNTIME_REQUIRED')
        self._allow_respawn_attack = allow_respawn_attack
        self._respawn_attack_attempted = False
        self._respawn_attack_ready = False
        self._respawn_attack_receipt = self._respawn_attack_refs = None
        self._respawn_attack_attempts = self._respawn_attack_ready_receipts = self._respawn_attack_bindings = ()
        self.ui_lookup_role = ui_lookup_role
        self.ui_lookup_role_observation = None
        self.inventory_ui_opener = inventory_ui_opener
        self.inventory_ui_open_observation = None
        self.equipment_ui_observer = equipment_ui_observer
        self.equipment_ui_observation = None
        self._ui_turn = False
        self.equipment_observer = equipment_observer
        self.item_equipment_initial = self.item_equipment_current = self.equipment_observation = None
        self._equipment_prepared = False
        self._equipment_sample_ordinal = self._equipment_complete_ordinal = None
        self._equipment_writer = self._equipment_generation = self._equipment_effect = None
        if equipment_observer is not None:
            from tools.local_original_session import equipment_observe
            need(type(equipment_observer) is equipment_observe.EquipmentObserver and manual is not None,
                 'FEATURE_ITEM_EQUIPMENT_ACTUAL_OBSERVER_REQUIRED')
            self._equipment_sample = equipment_observe.SAMPLE_METHOD
            self._equipment_close = equipment_observe.CLOSE_METHOD
            self._equipment_binding(current=False)

    def _equipment_binding(self, *, current=True, same_selection=False):
        from tools.local_original_session import equipment_observe, item_equipment_effect
        from tools.local_original_session.broker import PersistentBroker
        observer, manual = self.equipment_observer, self.manual
        need(type(observer) is equipment_observe.EquipmentObserver
             and equipment_observe.SAMPLE_METHOD is self._equipment_sample
             and equipment_observe.CLOSE_METHOD is self._equipment_close,
             'FEATURE_ITEM_EQUIPMENT_OBSERVER_CHANGED')
        for name, function in (('sample', self._equipment_sample), ('close', self._equipment_close)):
            method = getattr(observer, name)
            need(getattr(method, '__self__', None) is observer
                 and getattr(method, '__func__', None) is function,
                 'FEATURE_ITEM_EQUIPMENT_ORIGINAL_OBSERVER_REQUIRED')
        broker = manual.inventory_broker
        need(type(broker) is PersistentBroker and observer._authority.broker is broker
             and observer._authority.reader is manual.consumer.reader,
             'FEATURE_ITEM_EQUIPMENT_RETAINED_BINDING_CHANGED')
        effect = broker._item_equipment_effect
        need(type(effect) is item_equipment_effect.ItemEquipmentEffect and effect.broker is broker
             and effect.policy == item_equipment_effect.POLICY,
             'FEATURE_ITEM_EQUIPMENT_ACTUAL_EFFECT_REQUIRED')
        for name in ('prepare_locked', 'consume_locked', 'observation'):
            method = getattr(effect, name)
            need(getattr(method, '__self__', None) is effect
                 and getattr(method, '__func__', None) is getattr(item_equipment_effect.ItemEquipmentEffect, name),
                 'FEATURE_ITEM_EQUIPMENT_ORIGINAL_EFFECT_REQUIRED')
        for name in ('prepare_item_equipment', 'item_equipment_observation'):
            method = getattr(broker, name)
            need(getattr(method, '__self__', None) is broker
                 and getattr(method, '__func__', None) is getattr(PersistentBroker, name),
                 'FEATURE_ITEM_EQUIPMENT_ORIGINAL_BROKER_REQUIRED')
        if not current:
            return broker, None, effect
        binding = current_manual_binding(broker)
        generation = (None if binding is None else manual._inventory_reselection_current(binding.writer))
        writer = None if generation is None else binding.writer
        if same_selection:
            need(writer is not None and writer is self._equipment_writer
                 and generation is self._equipment_generation and effect is self._equipment_effect,
                 'FEATURE_ITEM_EQUIPMENT_SELECTION_CHANGED')
        return broker, writer, effect

    def _equipment_selection(self, broker, writer, effect):
        # Discard scheduling/receipt caches; never produce a generation or make
        # an old receipt current. Observer cadence remains global across selects.
        generation = None if writer is None else broker._inventory_generation
        if (writer is not self._equipment_writer or generation is not self._equipment_generation
                or effect is not self._equipment_effect):
            self.item_equipment_initial = self.item_equipment_current = self.equipment_observation = None
            self._equipment_prepared = False
            self._equipment_sample_ordinal = self._equipment_complete_ordinal = None
            self._equipment_writer, self._equipment_generation, self._equipment_effect = writer, generation, effect
        return generation

    def _equipment_delivery_complete(self, broker, generation):
        # add_inventory publishes these only after actual _send/drain and final
        # authority checks under its row lock, immediately before COMMITTED.
        # prepare_locked still performs the complete original current projection.
        if generation is None:
            return False
        service, row, frame = generation.service, generation.row, generation.frame
        delivered = generation.delivery_authority
        return (type(frame) is bytes and generation.operation_frame is frame
            and generation.attempted is True and generation.write_attempted is True
            and type(delivered) is tuple and len(delivered) == 3
            and service._claimed is True and not service._inflight and not service._closed
            and generation.prewrite_refusal is None and not generation.admission_expired
            and type(generation.current_frame) is bytes
            and row['policy_row'].pending_opcode is None and row['policy_row'].pending_size == 0
            and row['policy_row'].drain_started_ns is None)

    def _equipment_initial_client_ready(self, broker, writer, generation):
        # Readiness only. Existing original manual client confirmation supplied
        # these objects; no query/Store/send/retry or new authority is produced.
        from tools.local_original_session.commands import RESULT_SCHEMA
        manual = self.manual
        result, bound = manual.last_result, manual._inventory_client_binding
        frame = generation.current_frame
        expected_count=2
        if broker._inventory_collection_policy is not None:
            from tools.local_original_session import inventory
            try:expected_count=len(inventory.validate_current_collection_frame(
                frame,policy=broker._inventory_collection_policy))
            except ValueError:return False
        reader, observer = manual.consumer.reader, manual._inventory_observer
        if not (manual.pending is False and manual._inventory_request is None
                and manual._inventory_wait is None and manual._inventory_generation is generation
                and generation is broker._inventory_generation and generation.phase == 'ACTIVE'
                and generation.writer is writer and type(frame) is bytes
                and frame is generation.frame is generation.operation_frame
                and frame is broker._inventory_current_frame is manual._inventory_frame
                and generation.selection_binding is broker._inventory_selection_binding
                and generation.selection_binding is manual._inventory_auto_selection
                and type(bound) is tuple and len(bound) == 12
                and all(a is b for a, b in zip(bound, (broker, observer, observer._authority,
                    reader, reader.backend, reader.owner, reader.member, generation.service,
                    generation.delivery_authority, frame, writer, manual._inventory_observer_sample)))
                and type(result) is dict and result.get('schema') == RESULT_SCHEMA
                and result.get('status') == 'COMMITTED' and result.get('phase') == 'CLIENT_CONFIRMED'
                and result.get('reason') is None and result.get('automatic_retry') is False
                and result.get('cleanup_required') is not True
                and result.get('client_inventory') == 'ROWS_5_SCALARS_MATCHED'
                and type(result.get('item_count')) is int and result['item_count'] == expected_count
                and result.get('transport_proof_scope') == 'TRANSPORT_DRAIN_ONLY'
                and result.get('invoked') is True
                and type(manual.sequence) is int and manual.sequence > 0
                and type(result.get('sequence')) is int and result['sequence'] == manual.sequence
                and type(result.get('last_sequence')) is int and result['last_sequence'] == manual.sequence):
            return False
        if result.get('command') == 'AddInventory':
            return (generation.previous is None
                and result.get('proof_scope') == 'CLIENT_ITEM_ROWS_SCALARS_ONLY')
        if result.get('command') != 'SourceReselect':
            return False
        proof = manual._source_reselect_proof
        return (type(proof) is tuple and len(proof) == 4
            and proof is manual.consumer._source_reselect_completed and proof[1] is generation
            and type(proof[0]) is dict and proof[0].get('restart_generation') is generation.previous
            and generation.previous is not None and generation.previous.phase == 'RETIRED'
            and result.get('proof_scope') == 'CLIENT_SAVED_ITEM_ROWS_SCALARS_AFTER_RESELECT'
            and result.get('inventory_restore') == 'ROWS_5_SCALARS_MATCHED'
            and result.get('native_attempted') is result.get('selection_changed') is result.get('world_ready') is True)

    async def _poll_equipment(self, monitor, *, sample=True):
        # Preparation/cache progression is independent of manual command output.
        # Sampling alone consumes the existing serial 2Hz typed-query slot.
        broker, writer, effect = self._equipment_binding()
        generation = self._equipment_selection(broker, writer, effect)
        if writer is None or not self._equipment_delivery_complete(broker, generation):
            return False
        if (not self._equipment_prepared and getattr(broker, '_inventory_kit_policy', None) is not None
                and getattr(self.manual, 'pending', None) is True
                and getattr(self.manual, '_pending_command', None) == 'AddInventory'):
            # M1 kit: the initial 097A sync (~1.4 s per worn item, row lock held) plus early
            # player Use/move ran the one-shot AddInventory client check past its 10 s window
            # (FEATURE_INVENTORY_CLIENT_DEADLINE -> session close). Let that check finish first;
            # a Use before the sync is refused as EQUIPMENT_INITIAL_SYNC_REQUIRED (no failure).
            # The delivery above is already written, so only the pending client check (automatic
            # or explicit AddInventory) waits; an explicit Add no longer blocks the sync forever.
            return False
        if not self._equipment_prepared:
            self._equipment_prepared = True  # No retry after failed/unknown prepare.
            initial = await broker.prepare_item_equipment(writer, policy=effect.policy, first_enable=effect.first_enable)
            self._equipment_binding(same_selection=True)
            # Handler-first may already have a newer ITEM_USE_EFFECT receipt.
            # Preserve actual historical INITIAL_SYNC from the prepare result.
            self.item_equipment_initial = initial
        session = broker._item_use_session
        intent = session._current
        ordinal = 0
        count = session.accepted_count
        need(type(count) is int and 0 <= count <= (1 << 64) - 1,
             'FEATURE_ITEM_EQUIPMENT_ACCEPTED_COUNTER_REQUIRED')
        if intent is not None:
            need(intent.writer is writer and type(intent.accepted_ordinal) is int
                 and intent.accepted_ordinal == count,
                 'FEATURE_ITEM_EQUIPMENT_CURRENT_INTENT_REQUIRED')
        # A later inventory update/rejected request may clear public _Intent.
        # The actual latest same-generation equipment receipt is still history,
        # not a new intent/admission or a reason to replay the old empty sync.
        if count:
            cached = broker.item_equipment_observation(writer, accepted_ordinal=count)
            if cached.get('status') != 'NO_MATCH':
                ordinal = count
                self.item_equipment_current = cached
        if ordinal == 0:
            self.item_equipment_current = None
        if not sample:
            return False
        receipt = self.item_equipment_initial if ordinal == 0 else self.item_equipment_current
        if (self._equipment_complete_ordinal == ordinal or type(receipt) is not dict
                or not all(receipt.get(k) is True for k in ('writer_bound', 'generation_bound',
                    'write_attempted', 'drain_returned', 'post_owner_verified'))):
            return False
        if (self._equipment_swap_reselect or self.item_transfer_ui is not None) and ordinal == 0:
            if not self._equipment_initial_client_ready(broker, writer, generation):
                return False  # Original ingress must finish same-life plural client proof first.
        now = time.monotonic_ns()
        sampled = max((n for n in (self.manual.last_sample_monotonic_ns,
            self.equipment_observer.last_sample_monotonic_ns) if n is not None), default=None)
        if sampled is not None and now - sampled < 500_000_000:
            if monitor is not None:
                monitor.next_memory = max(monitor.next_memory, sampled / 1e9 + .5)
            return True  # Reserve this due slot until the previous real query's cadence permits it.
        self._equipment_sample_ordinal = ordinal  # Read-only polling never replays prepare/use/send.
        before = self.equipment_observer.last_sample_monotonic_ns
        try:
            self.equipment_observation = await self.equipment_observer.sample(writer, now_ns=now)
            self._equipment_binding(same_selection=True)
            raw = self.equipment_observation
            found = ([r.get('value_u64') for r in raw.get('rows', [])
                      if type(r) is dict and r.get('rawkey_i32') == receipt.get('equipment_key_i32')]
                     if type(raw) is dict else None)
            expected = [] if receipt.get('after_weapon_uid') == 0 else [receipt.get('after_weapon_uid')]
            # M1 kit: headless runs never reached found == expected here, so this
            # diagnostic sample (~60-90 ms on the event loop) repeated every slot
            # for the whole session; keep one actual sample per receipt instead.
            if (type(raw) is not dict or raw.get('status') != 'OBSERVED' or found == expected
                    or getattr(broker, '_inventory_kit_policy', None) is not None):
                # This scheduling marker grants no semantic proof. The runner
                # validates the strict source/owner/raw fields independently.
                self._equipment_complete_ordinal = ordinal

        finally:
            sampled = self.equipment_observer.last_sample_monotonic_ns
            if monitor is not None and sampled is not None and sampled != before:
                monitor.next_memory = max(monitor.next_memory, sampled / 1e9 + .5, time.monotonic() + .5)
        return True

    def request_item_equipment_ui_observation(self, item_identifier=None):
        """Explicit read-only request; no input/Use/effect permission or query."""
        if self._closed or self.equipment_ui_observer is None:
            return False
        queued = self.equipment_ui_observer.request(item_identifier=item_identifier)
        self.equipment_ui_observation = self.equipment_ui_observer.observation()
        self._refresh_ui_lookup_role()
        return queued

    def _refresh_ui_lookup_role(self):
        if self.ui_lookup_role is not None:
            self.ui_lookup_role_observation = self.ui_lookup_role.consume(self.equipment_ui_observation)

    def request_mark_on_install(self):
        installer = getattr(self, 'mark_on_installer', None)
        if self._closed or installer is None:
            return False
        queued = installer.request()
        self.mark_on_install_observation = installer.observation()
        return queued

    def request_item_transfer_roundtrip(self, *, prepare_use=False):
        need(not self._closed and self.item_transfer_ui is not None,
             'FEATURE_ITEM_TRANSFER_UI_EXPLICIT_RUNTIME_REQUIRED')
        return self.item_transfer_ui.request(prepare_use=prepare_use)

    def request_original_screenshot(self):
        """Serial runtime-loop caller; the original Observer owns current admission.

        Only completed, preserved captures can yield to another one-shot Observer.
        No Native sequence, pending state or historical result is reset here.
        """
        if self._closed:
            return False
        old = getattr(self, 'original_screenshot', None)
        if old is None:
            return False
        from tools.local_original_session import original_screenshot as source
        cls = source.OriginalScreenshotObserver
        need(digest(Path(source.__file__)) ==
             'd90ed7e331a6697949be94ae908943f241fec0c30527599d988c3ce1cb06b357',
             'FEATURE_SCREENSHOT_SOURCE_CHANGED')
        need(type(old) is cls and old.manual is self.manual
             and old.consumer is self.manual.consumer and old._thread == threading.get_ident(),
             'FEATURE_SCREENSHOT_ORIGINAL_OWNER_REQUIRED')
        originals = tuple(getattr(cls, name) for name in ('__init__', 'request', 'sample', 'collect', 'close'))
        for name, function in zip(('__init__', 'request', 'sample', 'collect', 'close'), originals):
            method = getattr(old, name)
            need(type(method) is MethodType and method.__self__ is old and method.__func__ is function
                 and function.__globals__ is vars(source)
                 and function.__qualname__ == 'OriginalScreenshotObserver.' + name
                 and Path(function.__code__.co_filename).resolve() == Path(source.__file__).resolve(),
                 'FEATURE_SCREENSHOT_ORIGINAL_METHOD_REQUIRED')
        manual, consumer = self.manual, old.consumer
        if (old._terminal or old._requested or old._pending is not None
                or manual.closed or manual._resources_closed or manual.pending or manual._polling
                or manual._inventory_request is not None or manual._inventory_wait is not None
                or consumer.pending is not None or consumer._busy or consumer._readonly_pending is not None):
            return False
        if not old._attempted:
            return False if old._closed else originals[1](old)
        result, files = old.last_result, old._files
        if not (type(result) is dict and result.get('status') == 'OBSERVED'
                and result.get('png_verified') is True
                and result.get('async_completion') == 'CLOSED_STABLE_FRESH_PNG'
                and result.get('existing_files_preserved') is True
                and result.get('cleanup_required') is False and old._native_complete is True
                and type(files) is source.CaptureFiles and files.closed is True):
            return False
        originals[4](old)  # Failure leaves the original slot and result intact.
        fresh = None
        try:
            fresh = cls(manual, collection_policy=old.collection_policy)  # Original policy revalidation.
            queued = originals[1](fresh)  # Original ACTIVE inventory/current owner admission.
            need(not self._closed and self.manual is manual and self.original_screenshot is old
                 and manual.consumer is consumer and not manual.closed and not manual._resources_closed
                 and tuple(getattr(cls, n) for n in ('__init__', 'request', 'sample', 'collect', 'close')) == originals,
                 'FEATURE_SCREENSHOT_RUNTIME_CHANGED')
            self.original_screenshot = fresh  # Publish exactly once, also on a refused current request.
            return queued
        except BaseException as error:
            if fresh is not None:
                try:
                    originals[4](fresh)
                except BaseException as cleanup:
                    try:
                        error.add_note('Fresh screenshot cleanup failed: ' + repr(cleanup))
                    except BaseException:
                        pass  # Diagnostic metadata must never replace the primary error.
            raise

    def request_inventory_ui_open(self):
        """One explicit action request; never a Use/effect or readonly proof."""
        if self._closed or self.inventory_ui_opener is None:
            return False
        queued = self.inventory_ui_opener.request()
        self.inventory_ui_open_observation = self.inventory_ui_opener.observation()
        return queued

    def retire_inventory_ui_open_after_reselect(self, completed, *, current_after_reselect=False):
        from tools.local_original_session.inventory_ui_open import InventoryUIOpen
        need(not self._closed and type(self.inventory_ui_opener) is InventoryUIOpen,
             'FEATURE_INVENTORY_UI_OPEN_RETIRE_CURRENT_REQUIRED')
        need(type(current_after_reselect) is bool
             and self._equipment_zero_use_reselect is self._equipment_zero_use_reselect_bound
             and current_after_reselect is self._equipment_zero_use_reselect,
             'FEATURE_INVENTORY_UI_CURRENT_ZERO_USE_REQUIRED')
        old = self.inventory_ui_opener
        fresh = old.retire_after_reselect(completed, current_after_reselect=current_after_reselect)
        self.inventory_ui_opener = fresh
        self.inventory_ui_open_observation = fresh.observation()
        return True

    async def _poll_equipment_slot(self, monitor):
        installer = getattr(self, 'mark_on_installer', None)
        if installer is not None and installer._requested:
            used = await installer.sample()
            self.mark_on_install_observation = installer.observation()
            if used:
                if monitor is not None:
                    monitor.next_memory = max(monitor.next_memory, installer.last_sample_monotonic_ns / 1e9 + .5)
                return True
        screenshot = getattr(self, 'original_screenshot', None)
        if screenshot is not None and (screenshot._requested or screenshot._pending is not None):
            used = await screenshot.sample() if screenshot._requested else False
            if monitor is not None:
                monitor.next_memory = max(monitor.next_memory, time.monotonic() + .5)
            return used or screenshot._pending is not None
        opener = self.inventory_ui_opener
        if opener is not None and opener._requested:
            used = await opener.sample()
            self.inventory_ui_open_observation = opener.observation()
            if used:
                if monitor is not None:
                    monitor.next_memory = max(monitor.next_memory, opener.last_sample_monotonic_ns / 1e9 + .5)
                return True
        ui = self.equipment_ui_observer
        if ui is not None and ui._requested and self._ui_turn:
            self._ui_turn = False
            used = await ui.sample()
            self.equipment_ui_observation = ui.observation()
            self._refresh_ui_lookup_role()
            if used:
                if monitor is not None:
                    monitor.next_memory = max(monitor.next_memory, ui.last_sample_monotonic_ns / 1e9 + .5)
                return True
        used = (await self._poll_equipment(monitor)
                if self.equipment_observer is not None else False)
        if ui is not None:
            self._ui_turn = True
            if not used and ui._requested:
                used = await ui.sample()
                self.equipment_ui_observation = ui.observation()
                self._refresh_ui_lookup_role()
                if used and monitor is not None:
                    monitor.next_memory = max(monitor.next_memory, ui.last_sample_monotonic_ns / 1e9 + .5)
        return used

    def _respawn_attack_binding(self, receipt):
        from tools.local_original_session import npc_respawn, npc_session
        method = self._respawn_attack_binding
        need(type(method) is MethodType and method.__self__ is self
             and method.__func__ is type(self)._respawn_attack_binding
             and method.__func__.__globals__.get('ProductFeatures') is type(self)
             and Path(method.__func__.__code__.co_filename).resolve() == Path(__file__).resolve(),
             'FEATURE_RESPAWN_ATTACK_CANONICAL_RUNTIME_REQUIRED')
        need(self._allow_respawn_attack is True and not self._closed and not self._npc_respawning
             and type(receipt) is npc_respawn.Receipt and receipt is self._npc_respawn_receipt
             and self._respawn_attack_receipt is receipt and receipt.generation.ordinal in (1, 2),
             'FEATURE_RESPAWN_ATTACK_ADOPTED_RECEIPT_REQUIRED')
        current, manual = self.npc_session, self.manual
        need(type(current) is npc_session.NpcSession and type(manual) is ManualMoveRequests
             and not current._closed and not current.factory._closed
             and current.factory._session is current
             and current._generation is receipt.generation and current._owned_mover is receipt.mover
             and current.factory.adapter is receipt.adapter
             and current.factory.config.spawns == (receipt.recipe,)
             and current.factory.config.spawns[0] is receipt.recipe,
             'FEATURE_RESPAWN_ATTACK_CURRENT_SESSION_REQUIRED')
        broker, writer = current.broker, receipt.writer
        service = broker._npc_respawn
        need(type(service) is npc_respawn.Service and service is receipt._service
             and service.reader is manual.consumer.reader is current.factory.reader
             and broker.realm._npc_respawn is service,
             'FEATURE_RESPAWN_ATTACK_CURRENT_SERVICE_REQUIRED')
        service.require_current(receipt)
        need(receipt.metadata()['status'] == 'COMMITTED', 'FEATURE_RESPAWN_ATTACK_COMMITTED_RECEIPT_REQUIRED')
        broker.source_guard()
        binding = current.current_binding()
        need(binding is not None and binding.owner is writer
             and broker.realm._npc_frames.get(id(writer)) is receipt.generation.frames
             and broker.realm.npc_mover(writer) is receipt.mover
             and broker.realm.npc_edge_passability is receipt.adapter,
             'FEATURE_RESPAWN_ATTACK_CURRENT_GENERATION_REQUIRED')
        game = broker.realm.registry.resolve(writer)
        refs = (receipt, current, current.factory, receipt.generation, receipt.mover,
                receipt.generation.frames, writer, receipt.row, service, broker,
                broker._attack_session, manual, manual.consumer, game, game.selection,
                broker.source_guard, receipt.adapter, manual._lethal_preparation_proof)
        saved = next((value for value in self._respawn_attack_bindings if value[0] is receipt), None)
        need(self.npc_session is current and self.manual is manual and not self._closed
             and not self._npc_respawning and self._npc_respawn_receipt is receipt
             and self._respawn_attack_receipt is receipt
             and (saved is None or len(saved) == len(refs)
                  and all(a is b for a, b in zip(saved, refs))),
             'FEATURE_RESPAWN_ATTACK_BINDING_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return refs

    def _respawn_attack_baseline(self, receipt):
        from tools.local_original_session import manual_move_commands as m
        manual, consumer = self.manual, self.manual._respawn_attack_producer()
        session, ordinal = self.npc_session.broker._attack_session, receipt.generation.ordinal
        need(not manual.closed and not manual._resources_closed and not manual.pending
             and not manual._polling and consumer.pending is None and not consumer._busy
             and all(type(n) is int for n in (manual.sequence, consumer.sequence,
                                             session.accepted_count, session.feedback_drained))
             and manual.sequence == ordinal + 1 and consumer.sequence == ordinal
             and session.accepted_count == session.feedback_drained == ordinal,
             'FEATURE_RESPAWN_ATTACK_PREPARED_BASELINE_REQUIRED')
        if ordinal == 1:
            return manual.lethal_preparation_settled()
        arm, proof = manual._respawn_attack_arm, manual._respawn_attack_completed
        need(type(arm) is tuple and len(arm) == 6 and len(manual._respawn_attack_arms) == 1
             and arm is manual._respawn_attack_arms[0] and arm[0] is self and arm[2] is consumer
             and arm[1].generation is receipt.old_generation and arm[1].generation.ordinal == 1
             and type(proof) is m.RESPAWN_ATTACK_PROOF_TYPE
             and proof is consumer._respawn_attack_completed
             and type(manual._respawn_attack_completions) is tuple
             and len(manual._respawn_attack_completions) == 1
             and manual._respawn_attack_completions[0] is proof
             and type(consumer._respawn_attack_completions) is tuple
             and len(consumer._respawn_attack_completions) == 1
             and consumer._respawn_attack_completions[0] is proof
             and proof.receipt is arm[1] and proof.generation is receipt.old_generation
             and proof._consumer is consumer and proof.sequence == proof.accepted_ordinal == 2
             and consumer.state is proof._state and consumer.state == proof._state_data
             and consumer.state.get('status') == consumer.state.get('phase') == 'COMMITTED'
             and manual.last_result.get('status') == 'COMMITTED'
             and manual.last_result.get('command') == 'AttackTarget'
             and manual.last_result.get('sequence') == arm[5]['public_sequence'] == 3
             and manual._respawn_attack_submitted_current()
             and arm[3] is manual._lethal_preparation_proof is consumer._lethal_preparation_completed,
             'FEATURE_RESPAWN_ATTACK_PREVIOUS_COMPLETION_REQUIRED')
        return proof  # Historical completion identity, never its retired current-life authority.

    async def arm_respawn_attack(self, receipt):
        """One explicit normal attack on this product's committed new life."""
        from tools.local_original_session import npc_respawn
        expected = 2 if self._respawn_attack_attempted else 1
        need(self._allow_respawn_attack is True and expected not in self._respawn_attack_attempts
             and not (expected == 2 and type(receipt) is npc_respawn.Receipt
                      and receipt.generation.ordinal == 1),
             'FEATURE_RESPAWN_ATTACK_ONCE_ARM_REQUIRED')
        self._respawn_attack_attempted = True  # An invalid/cancelled attempt cannot rearm.
        self._respawn_attack_attempts += (expected,)
        self._respawn_attack_receipt = receipt
        need(type(receipt) is npc_respawn.Receipt and receipt.generation.ordinal == expected,
             'FEATURE_RESPAWN_ATTACK_EXPLICIT_GENERATION_REQUIRED')
        refs = self._respawn_attack_binding(receipt)
        self._respawn_attack_refs = refs
        self._respawn_attack_bindings += (refs,)
        manual, consumer, session = self.manual, self.manual._respawn_attack_producer(), refs[10]
        proof = self._respawn_attack_baseline(receipt)
        async with receipt.row['operation_lock']:
            self._respawn_attack_binding(receipt)
            need(self._respawn_attack_baseline(receipt) is proof,
                 'FEATURE_RESPAWN_ATTACK_BASELINE_CHANGED')
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            summary = dict(status='ARMED', public_sequence=manual.sequence + 1,
                native_sequence=consumer.sequence + 1, accepted_ordinal=session.accepted_count + 1,
                generation=receipt.generation.ordinal)
            manual._arm_respawn_attack(self, receipt, summary)
            self._respawn_attack_binding(receipt)
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            self._respawn_attack_ready = True
            self._respawn_attack_ready_receipts += (receipt,)
        return summary

    async def respawn_npc(self, *, writer, target_uid, accepted_ordinal, spawn, now_ns, policy,
                          monitor=None):
        """Explicit backend trigger; prepare first, adopt under the core row lock.

        No timer, automatic goal, HP seed, reader query or send lives here.
        Core owns the fresh absence query, one spawn/drain and terminal outcome.
        """
        from tools.local_original_session import npc_respawn, npc_session
        need(not self._closed and not self._npc_respawning
             and type(policy) is str and policy == self._npc_respawn_policy == npc_respawn.POLICY
             and spawn is self._npc_respawn_spawn,
             'FEATURE_EXPLICIT_CURRENT_RESPAWN_REQUIRED')
        old = self.npc_session
        need(type(old) is npc_session.NpcSession and not old._closed and not old.factory._closed
             and old.factory._session is old and old.factory.config.respawn_policy == policy,
             'FEATURE_RESPAWN_ORIGINAL_SESSION_REQUIRED')
        slot = self._npc_bound_monitor
        need(monitor is None or monitor is slot, 'FEATURE_RESPAWN_SAME_QUERY_MONITOR_REQUIRED')
        need(time.monotonic() >= slot.next_memory, 'FEATURE_RESPAWN_QUERY_SLOT_NOT_DUE')
        binding = old.current_binding()
        need(binding is not None and binding.owner is writer,
             'FEATURE_RESPAWN_CURRENT_SELECTED_BINDING_REQUIRED')
        service = old.broker._npc_respawn
        need(type(service) is npc_respawn.Service and service.policy == policy
             and service.current_generation(writer) is old._generation
             and old._owned_mover is old._generation.mover,
             'FEATURE_RESPAWN_OWNED_GENERATION_REQUIRED')
        previous = None
        if old._generation.ordinal != 0:
            # Only this explicit second life may consume the original seed
            # again. The prior committed receipt, not equal spawn values,
            # authorizes preparing a fresh object for the existing core path.
            previous = self._npc_respawn_receipt
            need(old._generation.ordinal == 1 and type(previous) is npc_respawn.Receipt
                 and previous._service is service and previous.writer is writer
                 and previous.generation is old._generation and previous.spawn is spawn
                 and previous.recipe is old.factory.config.spawns[0]
                 and previous.mover is old._owned_mover and previous.adapter is old.factory.adapter,
                 'FEATURE_RESPAWN_SECOND_CURRENT_RECEIPT_REQUIRED')
            service.require_current(previous)
            need(previous.metadata()['status'] == 'COMMITTED',
                 'FEATURE_RESPAWN_SECOND_COMMITTED_RECEIPT_REQUIRED')
            from tools.local_original_session import npc
            spawn = npc.NpcSpawn(dict(previous.recipe.fields), map_id=previous.recipe.map_id,
                                 policy=previous.recipe.policy)
        fresh = npc_session.NpcSessionFactory(old.factory.reader, config=old.factory.config)
        adopted = None
        self._npc_respawning = True
        try:
            # This public API owns the hidden core absence query's slot.
            # The focused caller checks due but does not pre-reserve this one.
            slot.next_memory = max(slot.next_memory, time.monotonic() + .5)
            ticket = service.trigger(writer, target_uid, accepted_ordinal)

            def adopt(receipt):
                nonlocal adopted
                need(type(receipt) is npc_respawn.Receipt and self.npc_session is old
                     and (previous is None or self._npc_respawn_receipt is previous)
                     and receipt.writer is writer and receipt.old_generation is old._generation
                     and receipt.recipe is old.factory.config.spawns[0]
                     and receipt.spawn is spawn and receipt.adapter is fresh.adapter
                     and receipt.row['operation_lock'].locked()
                     and adopted is None and fresh._session is None and not fresh._closed,
                     'FEATURE_RESPAWN_ONCE_ADOPT_BINDING_REQUIRED')
                old.factory.close()  # Permanently retire old goal and edge-proof resolver.
                old.broker.realm.npc_edge_passability = fresh.adapter
                adopted = fresh.bind(old.broker, generation=receipt.generation)
                service.require_current(receipt)
                need(adopted._generation is receipt.generation and adopted._owned_mover is receipt.mover,
                     'FEATURE_RESPAWN_FRESH_OWNED_GENERATION_REQUIRED')
                self.npc_session = adopted
                self._npc_turn = False
                return adopted

            receipt = await old.broker.respawn_npc(writer, ticket=ticket, spawn=spawn, now_ns=now_ns,
                prepared_adapter=fresh.adapter, adopt_generation=adopt)
            need(adopted is self.npc_session and adopted is not None,
                 'FEATURE_RESPAWN_ADOPTION_REQUIRED')
            service.require_current(receipt)
            self._npc_respawn_receipt = receipt
            return receipt
        except BaseException:
            fresh.close()  # A prepared or post-drain failed generation is never reused.
            raise
        finally:
            slot.next_memory = max(slot.next_memory, time.monotonic() + .5)
            self._npc_respawning = False

    async def _poll_npc(self, monitor, *, reserve):
        now = time.monotonic_ns()
        reserved = reserve and now / 1e9 >= monitor.next_memory
        if reserved:
            # Reserve before tick/await: UNKNOWN and failed typed queries use
            # the same serial 2Hz slot as manual/inventory/equipment/pose.
            monitor.next_memory = max(monitor.next_memory, now / 1e9 + .5)
            self._npc_turn = False
        try:
            outcome = await self.npc_session.tick(now_ns=now, allow_edge_query=reserved)
            result = dict(status=outcome.status, reason=outcome.reason, typed_slot_reserved=reserved)
            if reserved and outcome.status == 'UNKNOWN' and outcome.reason == 'EDGE_TYPED_READ_CHANGED':
                changed = self.npc_session.factory.adapter.last_result.get('changed_read1')
                if type(changed) is dict:
                    result['changed_read1'] = {key: changed[key] for key in
                        ('address', 'size', 'field_role', 'before_sha256', 'after_sha256',
                         'capture_phase', 'comparison')}
            return result
        finally:
            if reserved:
                monitor.next_memory = max(monitor.next_memory, time.monotonic() + .5)

    async def poll(self, monitor=None, *, npc_poll=True):
        need(type(npc_poll) is bool, 'FEATURE_NPC_POLL_EXPLICIT_BOOL_REQUIRED')
        # One-poll evidence transfer only; never reuse a prior poll as fresh.
        if getattr(self, 'mark_on_indicator', None) is not None:
            self._mark_on_use_caller_capture = None
        if self._closed:
            return {}
        if self.item_transfer_ui is not None and self.item_transfer_ui.started:
            return dict(item_transfer_ui=await self.item_transfer_ui.poll(monitor))
        result = {}
        npc_pending = False
        if npc_poll and self.npc_session is not None:
            if self._npc_respawn_policy is not None:
                if monitor is not None and self._npc_bound_monitor is self._npc_poll_monitor:
                    monitor.next_memory = max(monitor.next_memory, self._npc_poll_monitor.next_memory)
                    self._npc_bound_monitor = monitor
                need(monitor is None or monitor is self._npc_bound_monitor,
                     'FEATURE_RESPAWN_SAME_QUERY_MONITOR_REQUIRED')
                monitor = self._npc_bound_monitor
            if monitor is None:
                monitor = self._npc_poll_monitor
            npc_pending = self.npc_session.edge_query_pending(now_ns=time.monotonic_ns())
            if npc_pending and (self.manual is None or self._npc_turn):
                if time.monotonic() >= monitor.next_memory:
                    result['npc'] = await self._poll_npc(monitor, reserve=True)
        screenshot = getattr(self, 'original_screenshot', None)
        if screenshot is not None:
            screenshot.collect()
        installer = getattr(self, 'mark_on_installer', None)
        if installer is not None:
            installer.collect()
            self.mark_on_install_observation = installer.observation()
        if self.inventory_ui_opener is not None:
            self.inventory_ui_opener.collect()
            self.inventory_ui_open_observation = self.inventory_ui_opener.observation()
        if self.equipment_ui_observer is not None:
            self.equipment_ui_observer.collect()
            self.equipment_ui_observation = self.equipment_ui_observer.observation()
            self._refresh_ui_lookup_role()
        if self.manual is not None:
            raw_enabled = self.equipment_observer is not None
            enabled = (raw_enabled or self.equipment_ui_observer is not None
                       or self.inventory_ui_opener is not None or screenshot is not None)
            if raw_enabled:
                # No typed query: consume already published post-drain state on
                # the first poll, including Add CLIENT_WAIT or unrelated output.
                await self._poll_equipment(monitor, sample=False)
            due = monitor is None or time.monotonic() >= monitor.next_memory
            if due and npc_pending:
                self._npc_turn = True  # Next due slot permits NPC before ingress.
            equipment_slot = False
            if due and enabled and self._equipment_turn:
                self._equipment_turn = False  # Next due always permits ingress.
                equipment_slot = await self._poll_equipment_slot(monitor)
            if due and not equipment_slot:
                before = self.manual.last_sample_monotonic_ns
                marker = getattr(self, 'mark_on_indicator', None)
                if marker is not None:
                    consumer = self.manual.consumer
                    pending = consumer.pending
                    if type(pending) is dict and pending.get('kind') == 'UseItem':
                        # The original Current still decides eligibility here.
                        # Native UNKNOWN may close that authority in poll_async;
                        # retain only this pre-consumption callback snapshot.
                        self._mark_on_use_caller_capture = (pending, consumer.sequence, marker.consume_caller())
                try:
                    result['manual_move'] = await self.manual.poll_async(monitor=monitor)
                finally:
                    sampled = self.manual.last_sample_monotonic_ns
                    used = sampled is not None and sampled != before
                    if monitor is not None and used:
                        monitor.next_memory = sampled / 1e9 + .5
                self._equipment_turn = used  # Fair next slot if manual queried.
                if enabled:
                    # Same-task postdrain Add can prepare before a later public
                    # Add result/typed client read, using the real broker receipt.
                    if raw_enabled:
                        await self._poll_equipment(monitor, sample=False)
                    if not used:
                        await self._poll_equipment_slot(monitor)
            else:
                result['manual_move'] = dict(self.manual.last_result)
            if raw_enabled:
                result['item_equipment'] = self.item_equipment_current or self.item_equipment_initial
                result['equipment_raw'] = self.equipment_observation
            if self.equipment_ui_observer is not None:
                result['equipment_ui'] = self.equipment_ui_observation
            if self.ui_lookup_role is not None:
                result['selected_slot_lookup_role'] = self.ui_lookup_role_observation
            if self.inventory_ui_opener is not None:
                result['inventory_ui_open'] = self.inventory_ui_open_observation
        if npc_poll and self.npc_session is not None:
            if 'npc' not in result:
                result['npc'] = await self._poll_npc(monitor, reserve=npc_pending)
        if getattr(self,'_shop_normal_input_driver',None) is not None:
            from tools.local_original_session import shop_normal_input_driver
            from tools.local_original_session import shop_startup_caller
            if shop_startup_caller.ready(self):
                result['shop_normal_input'] = await shop_normal_input_driver.poll_runtime(self,monitor)
            else:
                result['shop_normal_input'] = dict(phase='WAIT_STARTUP_HANDOFF')
        return result

    def close(self):
        if getattr(self,'_shop_normal_input_driver',None) is None:
            return self._close_without_shop_normal_input()
        from tools.local_original_session import shop_normal_input_driver
        primary = None
        try:
            shop_normal_input_driver.close_runtime(self)
        except BaseException as error:
            primary = error
        try:
            result = self._close_without_shop_normal_input()
        except BaseException as cleanup:
            if primary is None:
                raise
            try:
                primary.add_note('Original feature cleanup failed: ' + type(cleanup).__name__)
            except BaseException:
                pass
        if primary is not None:
            raise primary
        return result

    def _close_without_shop_normal_input(self):
        if self._closed:
            return
        self._closed = True
        if self.item_transfer_ui is not None:
            self.item_transfer_ui.close()
        installer = getattr(self, 'mark_on_installer', None)
        if installer is not None:
            installer.close()
        marker = getattr(self, 'mark_on_indicator', None)
        if marker is not None:
            marker.close()
        screenshot = getattr(self, 'original_screenshot', None)
        if screenshot is not None:
            screenshot.close()
        if self.ui_lookup_role is not None:
            self.ui_lookup_role.close()
        if self.inventory_ui_opener is not None:
            self.inventory_ui_opener.close()
            self.inventory_ui_open_observation = self.inventory_ui_opener.observation()
        if self.equipment_ui_observer is not None:
            self.equipment_ui_observer.close()
            self.equipment_ui_observation = self.equipment_ui_observer.observation()
            self._refresh_ui_lookup_role()
        try:
            if self.manual is not None:
                self.manual.close()
        finally:
            try:
                if self.npc_session is not None:
                    self.npc_session.close()
            finally:
                if self.equipment_observer is not None:
                    # Use the retained original close even after a failed binding.
                    self._equipment_close(self.equipment_observer)


def _defer_feature_status_tick(features, monitor):
    # Only the exact selected ITEM wrapper has this scheduling contract.
    if features is None or type(features).__module__ != 'tools.local_original_session.item_transfer_runner':
        return False
    from tools.local_original_session.item_transfer_runner import Runtime, STATUS_TICK_DEFER_METHOD
    method = features.defer_status_tick
    need(type(features) is Runtime and Runtime.defer_status_tick is STATUS_TICK_DEFER_METHOD
         and type(method) is MethodType and method.__self__ is features
         and method.__func__ is STATUS_TICK_DEFER_METHOD,
         'FEATURE_STATUS_ORIGINAL_ITEM_SCHEDULER_REQUIRED')
    value = STATUS_TICK_DEFER_METHOD(features, monitor)
    need(type(value) is bool, 'FEATURE_STATUS_DEFER_BOOL_REQUIRED')
    return value


async def run_session(owner, broker_factory, stop, *, stop_requested=lambda: False,
                      poll_seconds=.1, close_grace_seconds=10, test_duration=None,
                      monitor=None, until_scene=None, input_requests=None, command_requests=None,
                      feature_factory=None, source_quit_directory=None, canonical_bootstrap=None):
    """One asyncio loop; product lifetime has no observation timeout."""
    need(input_requests is None or command_requests is None, 'EXCLUSIVE_SESSION_CONTROL_REQUIRED')
    if canonical_bootstrap is not None:
        from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap
        need(type(canonical_bootstrap) is CanonicalFeatureBootstrap,
             'CANONICAL_EXACT_BOOTSTRAP_SELECTION_REQUIRED')
    report = dict(schema='local-original-session-v1', reason='STARTING', cleanup=None,
                  product_lifetime_seconds=None, normal_input_only=True,
                  normal_exit_verified=False, game_logout_protocol='UNVERIFIED')
    from tools.local_original_session.commands import ResultPublicationFailure
    broker = None
    features = None
    source_quit = None
    shop_startup = None
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
    # Event-loop stall measurement (report only): the broker, world ticks and this
    # loop share one asyncio loop; synchronous memory reads/fsync stall all of them.
    loop_lag = dict(max_ms=0.0, over_50ms=0, over_200ms=0, samples=0,
                    monitor_tick_max_ms=0.0, monitor_tick_over_50ms=0,
                    features_poll_max_ms=0.0, features_poll_over_50ms=0)
    report['loop_lag'] = loop_lag

    async def watch_loop_lag():
        while True:
            before = time.perf_counter()
            await asyncio.sleep(.01)
            late = (time.perf_counter() - before - .01) * 1000
            loop_lag['samples'] += 1
            loop_lag['max_ms'] = max(loop_lag['max_ms'], round(late, 1))
            loop_lag['over_50ms'] += late > 50
            loop_lag['over_200ms'] += late > 200

    def timed(name, value):
        elapsed = (time.perf_counter() - value) * 1000
        loop_lag[name + '_max_ms'] = max(loop_lag[name + '_max_ms'], round(elapsed, 1))
        loop_lag[name + '_over_50ms'] += elapsed > 50
    lag_task = asyncio.create_task(watch_loop_lag())
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
            source_quit = SourceQuitRequests(owner, features.manual, broker, source_quit_directory, features=features)
            broker.bind_source_quit_closing(source_quit)
            report['source_quit'] = source_quit.report()
        if feature_factory is not None and getattr(feature_factory,'_shop_normal_input_spec',None) is not None:
            from tools.local_original_session import shop_startup_caller
            shop_startup = shop_startup_caller.attach(owner,monitor,stop,features,feature_factory,
                source_quit=source_quit,command_requests=command_requests,input_requests=input_requests)
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
                poll_started = time.perf_counter()
                report['features'] = await features.poll(monitor)
                timed('features_poll', poll_started)
                if getattr(features,'_shop_normal_input_driver',None) is not None:
                    from tools.local_original_session import shop_normal_input_driver
                    ended = shop_normal_input_driver.terminal(features)
                    if ended is not None:
                        report['reason'] = 'SHOP_INPUT_COMPLETE' if ended == 'DONE' else 'SHOP_INPUT_UNKNOWN'
                        break
            if monitor is not None:
                # A diagnostic tick is synchronous (window/memory/fsync). Do
                # not interpose it inside the selected ITEM's original window.
                # Feature queries keep the unchanged shared next_memory slot.
                tick_started = time.perf_counter()
                observed = (None if _defer_feature_status_tick(features, monitor)
                            else monitor.tick(broker))
                timed('monitor_tick', tick_started)
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
        lag_task.cancel()
        failed_session = report['reason'] == 'SESSION_FAILURE'
        # Leave transport and its resource slots available for native close
        # traffic. The grace is a shutdown bound, never a product lifetime.
        try:
            if broker is not None:
                try:
                    if features is not None and source_quit is None:
                        features.close()
                    if features is not None and getattr(features, '_shop_normal_input_driver', None) is not None:
                        from tools.local_original_session import shop_normal_input_driver
                        shop_normal_input_driver.retire_pending_for_close(features)
                    recover_failure = failed_session and session_failure_close_allowed()
                    if recover_failure or report['reason'] in ('USER_CLOSE', 'USER_INTERRUPT',
                                                              'TEST_DURATION', 'OBSERVATION_CONDITION',
                                                              'SHOP_INPUT_COMPLETE', 'SHOP_INPUT_UNKNOWN'):
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
                            report['source_quit'] = source_quit.close()
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
                    if canonical_bootstrap is not None:
                        canonical_bootstrap.close(broker)
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
                            try:
                                if shop_startup is not None:
                                    shop_startup.close()
                            finally:
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


def main(*, canonical_bootstrap=None, repeated_features=None, canonical_features=None, shop_features=None, normal_input_driver=None, npc_respawn_hit_features=None, npc_retaliation_features=None):
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
    parser.add_argument('--item-equipment-swap-saved-b-tail-test', action='store_true',
                        help='Explicit saved-B tail entry policy on the original swap profile only')
    parser.add_argument('--item-transfer-ui-test', action='store_true')
    parser.add_argument('--observe-hp4ec8-subscribers-once', action='store_true')
    parser.add_argument('--npc-dead-goal-only', action='store_true')
    parser.add_argument('--npc-hp-feedback-only', action='store_true')
    parser.add_argument('--hp4ec8-observation-stage', choices=('first-land','npc-hp-feedback-drained'))
    parser.add_argument('--item-equipment-zero-use-reselect-test', action='store_true',
                        help='Explicit saved-B zero-Use Restart/reselect profile only')
    parser.add_argument('--close-grace-seconds', type=float, default=10,
                        help='Native close/input grace only; 0 < seconds <= 120 (default: 10)')
    parser.add_argument('--until-scene', choices=('Intro', 'Lobby', 'Login', 'CharacterSelect', 'Land'))
    args = parser.parse_args()
    if normal_input_driver is not None:
        from tools.local_original_session.shop_normal_input_driver import Spec
        need(type(normal_input_driver) is Spec and shop_features is not None
             and normal_input_driver.root is canonical_bootstrap and normal_input_driver.features is shop_features,
             'SHOP_DRIVER_EXACT_TYPED_FEATURES_REQUIRED')
    if shop_features is not None:
        from tools.local_original_session.feature_config import Features
        from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap, _shop_input_selection
        need(type(shop_features) is Features and type(canonical_bootstrap) is CanonicalFeatureBootstrap
             and shop_features.canonical_bootstrap is canonical_bootstrap
             and canonical_bootstrap.shop_only and not canonical_bootstrap.resource_only
             and canonical_bootstrap._lifetime_state == 'READY'
             and repeated_features is None and canonical_features is None
             and args.product == SHOP_INPUT_PROFILE and args.run and args.background
             and args.source_quit_test and args.control_mode == 'manual',
             'SHOP_INPUT_TRUSTED_FEATURE_MODE_REQUIRED')
        _shop_input_native_current()
        _shop_input_selection(canonical_bootstrap,shop_features)
    if canonical_features is not None:
        from tools.local_original_session.feature_config import Features
        from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap, PROFILE
        from tools.local_original_session.buff_bootstrap import BuffBootstrap
        need(type(canonical_features) is Features and type(canonical_bootstrap) is CanonicalFeatureBootstrap
             and canonical_features.canonical_bootstrap is canonical_bootstrap
             and type(canonical_bootstrap.buff) is BuffBootstrap and not canonical_bootstrap.resource_only
             and canonical_bootstrap.shop is None and canonical_bootstrap.trade is None
             and canonical_bootstrap._lifetime_state == 'READY' and repeated_features is None
             and args.run and args.background and args.source_quit_test and args.control_mode == 'manual'
             and args.product == canonical_bootstrap.runtime_profile(),
             'CANONICAL_BUFF_TRUSTED_FEATURE_MODE_REQUIRED')
        canonical_bootstrap.buff.source_ready()
    if npc_retaliation_features is not None:
        if args.product == 'sibling-background-npc-continuous-retaliation-spawn':
            from tools.local_original_session.npc_continuous_retaliation_runtime import configuration, PROFILE as retaliation_profile
        else:
            from tools.local_original_session.npc_retaliation_runtime import configuration, PROFILE as retaliation_profile
        configuration(npc_retaliation_features)
        need(npc_retaliation_features.canonical_bootstrap is canonical_bootstrap
             and args.product == retaliation_profile and args.run and args.background and args.source_quit_test
             and args.control_mode == 'manual' and repeated_features is canonical_features is shop_features is npc_respawn_hit_features is None,
             'RETALIATION_TRUSTED_TYPED_MODE_REQUIRED')
    need(args.product not in ('sibling-background-npc-single-retaliation-spawn','sibling-background-npc-continuous-retaliation-spawn') or npc_retaliation_features is not None,
         'RETALIATION_TYPED_SOURCE_PLAN_REQUIRED')
    if npc_respawn_hit_features is not None:
        from tools.local_original_session.npc_respawn_hit_runtime import configuration, PROFILE as hit_profile
        configuration(npc_respawn_hit_features)
        need(npc_respawn_hit_features.canonical_bootstrap is canonical_bootstrap
             and args.product == hit_profile and args.run and args.background and args.source_quit_test
             and args.control_mode == 'manual' and repeated_features is canonical_features is shop_features is None,
             'RESPAWN_HIT_TRUSTED_FEATURE_MODE_REQUIRED')
    need(args.product != 'sibling-background-npc-respawn-target-hit-spawn' or npc_respawn_hit_features is not None,
         'RESPAWN_HIT_TYPED_SOURCE_PLAN_REQUIRED')
    need(args.product != SHOP_INPUT_PROFILE or shop_features is not None, 'SHOP_INPUT_TYPED_FEATURES_REQUIRED')
    need(repeated_features is None or args.run and args.source_quit_test and args.background
         and args.control_mode == 'manual' and args.product == 'sibling-background-repeated-player-life-spawn',
         'REPEAT_TRUSTED_FEATURE_MODE_REQUIRED')
    need(not args.observe_hp4ec8_subscribers_once or args.run and args.background and args.feature_config is not None,
         'HP4EC8_EXISTING_FEATURE_RUN_REQUIRED')
    need(args.hp4ec8_observation_stage is None or args.observe_hp4ec8_subscribers_once,
         'HP4EC8_STAGE_ONCE_FLAG_REQUIRED')
    need(not args.npc_dead_goal_only or args.run and args.background and args.source_quit_test
         and args.product == 'sibling-background-source-quit-spawn'
         and args.control_mode == 'manual' and args.feature_config is not None
         and not args.npc_hp_feedback_only, 'FEATURE_NPC_DEAD_GOAL_EXPLICIT_CLI_REQUIRED')
    need(not args.npc_hp_feedback_only or args.run and args.background and args.source_quit_test
         and args.control_mode == 'manual' and args.product == 'sibling-background-source-quit-spawn'
         and args.feature_config is not None and args.observe_hp4ec8_subscribers_once
         and args.hp4ec8_observation_stage == 'npc-hp-feedback-drained'
         and not any((args.item_transfer_ui_test,args.item_equipment_zero_use_reselect_test,args.item_equipment_swap_saved_b_tail_test)),
         'FEATURE_NPC_HP_FEEDBACK_EXACT_CLI_REQUIRED')
    need(not (args.item_equipment_zero_use_reselect_test and args.item_equipment_swap_saved_b_tail_test),
         'FEATURE_ZERO_USE_RESELECT_EXCLUSIVE_REQUIRED')
    need(not args.item_equipment_zero_use_reselect_test or args.run
         and args.product == 'sibling-background-item-equipment-zero-use-reselect-spawn'
         and args.source_quit_test and args.background and args.control_mode == 'manual',
         'FEATURE_ZERO_USE_RESELECT_CLI_REQUIRED')
    need(not args.item_equipment_swap_saved_b_tail_test or args.run
         and args.product == 'sibling-background-item-equipment-current-entry-tail-spawn'
         and args.source_quit_test and args.background and args.control_mode == 'manual',
         'FEATURE_SWAP_SAVED_B_TAIL_CLI_REQUIRED')
    need(not args.item_transfer_ui_test or args.run and args.source_quit_test
         and args.background and args.control_mode == 'manual'
         and args.product == 'sibling-background-item-drop-pickup-spawn'
         and not args.item_equipment_zero_use_reselect_test
         and not args.item_equipment_swap_saved_b_tail_test, 'FEATURE_ITEM_TRANSFER_UI_CLI_REQUIRED')
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
        if npc_retaliation_features is not None:
            feature_config = npc_retaliation_features
        elif npc_respawn_hit_features is not None:
            feature_config = npc_respawn_hit_features
        elif shop_features is not None:
            feature_config = shop_features
        elif canonical_features is not None:
            feature_config = canonical_features
        elif repeated_features is not None:
            from tools.local_original_session.feature_config import Features
            from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap
            need(type(repeated_features) is Features and type(canonical_bootstrap) is CanonicalFeatureBootstrap
                 and repeated_features.canonical_bootstrap is canonical_bootstrap,
                 'REPEAT_EXACT_TRUSTED_FEATURE_SOURCE_PLAN_REQUIRED')
            feature_config = repeated_features
        else:
            feature_config = load(args.feature_config)
        if canonical_bootstrap is not None and repeated_features is None and canonical_features is None and shop_features is None and npc_respawn_hit_features is None and npc_retaliation_features is None:
            from dataclasses import replace
            from tools.local_original_session.canonical_feature_bootstrap import CanonicalFeatureBootstrap, PROFILE
            need(type(canonical_bootstrap) is CanonicalFeatureBootstrap and args.product in (PROFILE,SHOP_INPUT_PROFILE,'sibling-background-repeated-player-life-spawn'),
                 'CANONICAL_EXACT_BOOTSTRAP_SELECTION_REQUIRED')
            feature_config = replace(feature_config, canonical_bootstrap=canonical_bootstrap)
        conversations = GenuineConversations()
        reader = RetainedSceneReader(args.image.absolute(), spec['candidate'],
                                     expected_sha=spec['image_sha256'])
        edge = EdgeAdapter(reader)
        if args.npc_hp_feedback_only:
            reader.request_hp4ec8_subscribers_once(stage='npc-hp-feedback-drained')
        feature_factory = ProductFeatureFactory(reader, product=args.product,
            control_mode=args.control_mode, directory=directory, config=feature_config,
            swap_saved_b_tail=args.item_equipment_swap_saved_b_tail_test,
            zero_use_reselect=args.item_equipment_zero_use_reselect_test,
            item_transfer_ui=args.item_transfer_ui_test, npc_hp_feedback_only=args.npc_hp_feedback_only,
            npc_dead_goal_only=args.npc_dead_goal_only)
        if normal_input_driver is not None:
            from tools.local_original_session import shop_normal_input_driver
            shop_normal_input_driver.configure_factory(feature_factory,normal_input_driver)
        if args.observe_hp4ec8_subscribers_once:
            need(feature_factory.enabled,'HP4EC8_ENABLED_FEATURE_REQUIRED')
            stage = args.hp4ec8_observation_stage or 'first-land'
            if stage == 'npc-hp-feedback-drained':
                from tools.local_original_session import attack_session, npc_hp
                need(feature_factory.manual and feature_factory.allow_attack
                     and not feature_factory.lethal_attack_preparation
                     and type(feature_config.attack_hp_provider) is npc_hp.ExplicitInputs
                     and type(feature_config.attack_feedback) is attack_session.FeedbackConfig,
                     'HP4EC8_NPC_STAGE_CANONICAL_HP_FEEDBACK_REQUIRED')
            if not args.npc_hp_feedback_only:
                reader.request_hp4ec8_subscribers_once(stage=stage)
        if args.product == SHOP_INPUT_PROFILE:
            from tools.local_original_session.canonical_feature_bootstrap import check_shop_input_factory
        need(not args.source_quit_test or
             (npc_retaliation_features is feature_factory.config
              if args.product in ('sibling-background-npc-single-retaliation-spawn','sibling-background-npc-continuous-retaliation-spawn')
              else npc_respawn_hit_features is feature_factory.config
              if args.product == 'sibling-background-npc-respawn-target-hit-spawn'
              else check_shop_input_factory(feature_factory) is feature_factory.config.canonical_bootstrap
              if args.product == SHOP_INPUT_PROFILE
              else feature_factory.config.canonical_bootstrap.full_buff_configured(feature_factory)
              if args.product in ('sibling-background-skill-buff-spawn','sibling-background-skill-buff-whole-entry-spawn')
              else feature_factory.config.player_life_policy is not None
              if args.product in ('sibling-background-player-death-recovery-spawn',
                                  'sibling-background-npc-player-lethal-recovery-spawn',
                                  'sibling-background-repeated-player-life-spawn')
              else feature_factory._transfer_ui_configured() if feature_factory.item_transfer_ui
              else feature_factory._zero_use_reselect_configured() if feature_factory.zero_use_profile
              else feature_factory._swap_reselect_configured() if feature_factory.swap_reselect
              else feature_factory._reselect_equipment_restore_configured() if feature_factory.reselect_equipment_restore
              else feature_factory._normal_open_use_configured() if feature_factory.normal_open_use_current_ui
              else feature_factory._inventory_ui_open_configured() if feature_factory.allow_inventory_ui_open
              else feature_factory._hp_status_configured() if feature_factory.hp_status_enabled
              else feature_factory._ui_inventory_update_configured() if feature_factory.ui_inventory_update_only
              else feature_factory.allow_attack and feature_factory.inventory
                   and (feature_factory.allow_attack_replacement or feature_factory.lethal_attack_preparation)),
             'SOURCE_QUIT_EXPLICIT_FEATURE_CONFIG_REQUIRED')
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
            options = dict(sockets=sockets, owner_guard=retained.guard,
                inventory_owner_guard=feature_factory.inventory_owner_guard(retained),
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
            if canonical_bootstrap is None:
                return PersistentBroker(**options)
            from tools.local_original_session.canonical_feature_bootstrap import create_broker
            return create_broker(canonical_bootstrap, options)
        async def run():
            stop = asyncio.Event()
            try:
                return await run_session(owner, factory, stop,
                    stop_requested=lambda: (directory / 'close.request').exists(),
                    test_duration=args.test_duration, monitor=monitor, until_scene=args.until_scene,
                    command_requests=command_requests, close_grace_seconds=args.close_grace_seconds,
                    feature_factory=feature_factory if feature_factory.enabled else None,
                    canonical_bootstrap=canonical_bootstrap,
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
        # The direct CLI and package importer must share the same strict owner class.
        import tools.local_original_session as _owner_package
        _owner_module = sys.modules[__name__]
        _owner_canonical = 'tools.local_original_session.launcher'
        _owner_registered = sys.modules.get(_owner_canonical)
        _owner_attribute = getattr(_owner_package, 'launcher', None)
        need((_owner_registered is None or _owner_registered is _owner_module)
             and (_owner_attribute is None or _owner_attribute is _owner_module),
             'NATIVE_OWNER_MODULE_ALIAS_CONFLICT')
        sys.modules[_owner_canonical] = _owner_module
        _owner_package.launcher = _owner_module
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(json.dumps(dict(status='REFUSED', reason=str(error)[:200], automatic_retry=False)))
        raise SystemExit(2)
