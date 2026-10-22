"""Persistent CP69 transport adapter; native ownership and resources stay in caller.

Call start/close in the launcher's running event loop. The two already reserved
loopback sockets transfer to this adapter. No process launch, automatic retry,
packet payload logging, self movement echo, or implicit character-store path.
"""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
import copy
import inspect
import re
import socket
import time
from pathlib import Path

from tools.local_entry_server.codecs import ClientPlaintextDecoder, Frame
from tools.local_game_session import session
from tools.local_own_login_request import codec as login
from tools.local_native_login_local_ack_hook import ack_enter_world as ack
from tools.local_native_login_map_notify_hook import hook as map_hook
from tools.local_native_login_self_actor_hook import hook as actor_hook
from tools.local_original_session import movement, settings, npc, npc_motion
from tools.local_persistent_broker_policy.policy import (
    PersistentPolicy, OwnerSample, Peer, MAX_COUNTER, PORTS,
)

KEY12 = b'\x0c\0\x20\x4e\x08\0\x10\0\x18\x01\0\0'
EMPTY_COUNTS = b'\x06\0\x3e\x4f\0\0'
QUIT_REQUEST = 0x4e3c
QUIT_SUCCESS_OPCODE = 0x4eef
QUIT_SUCCESS_FRAME = b'\x08\0\xef\x4e\x08\x2d\0\0'
ALIVE_REQUEST = 0x4e2a
ALIVE_RESPONSE = 0x4f57
ALIVE_FRAME = b'\x06\0\x57\x4f\0\0'  # SC_ALIVE_NOTI: empty protobuf body.
ATTACK_REQUEST = 0x4e30
ATTACK_FEEDBACK = 0x4e31
RESTART_REQUEST = 0x4e33
RESTART_ACK = 0x4e3b
ITEM_USE_REQUEST = 0x0960
ATTACK_INTENT_POLICY = 'EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT'
INVENTORY_UPDATE_POLICY = 'EXPLICIT_LOCAL_OPAQUE_CURRENT_ITEM_UPDATE'
INVENTORY_RESELECTION_POLICY = 'LOCAL_SAVED_ROW_ON_RESELECTION'
INVENTORY_RESELECTION_DELIVERY = 'LOCAL_WORLD_READY_ONCE'
INVENTORY_MISSING_ROW_POLICY = 'EXPLICIT_LOCAL_CONFIGURED_STARTER_IF_MISSING'
# Exact accepted configured starter, compared only; no default frame producer.
INVENTORY_STARTER_FIELDS = {1: 65537, 2: 1, 3: 0, 4: 1, 5: 0, 7: 0,
    9: 0, 10: 0, 13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0,
    24: False, 25: 0, 26: False}
BASELINE_WORLD = 'baseline'
CP73_SPAWN_WORLD = 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73'


def need(value, code):
    if not value:
        raise ValueError(code)


def alive_request_metadata(payload):
    """CS_ALIVE_NOTI optional int64/int32/bytes; never retain their values.

    Reuse the frozen codec's wire0/2 limit. Other wire types remain unsupported;
    this is not a complete replacement for the original protobuf parser.
    """
    known = {1: 0, 2: 0, 3: 2}
    with ack.realm.pb.parse_message(payload, limits=ack.realm.pb.WireLimits()) as message:
        counts = {number: 0 for number in known}
        unknown = 0
        for field in message.fields:
            if known.get(field.number) == field.wire_type:
                counts[field.number] += 1
            else:
                unknown += 1  # Includes a known number with a different wire tag.
        return dict(body_bytes=len(payload), field1_count=counts[1], field2_count=counts[2],
                    field3_count=counts[3], unknown_field_count=unknown)


async def _finish_cleanup(operation):
    """Finish owned cleanup even if the caller is cancelled more than once."""
    task = asyncio.create_task(operation)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError()
    return result


class _TransportPolicy(PersistentPolicy):
    def __init__(self, *args, attack_intent=False, attack_feedback=False, inventory_add=False, restart_enabled=False, item_use_intent=False, inventory_update=False, item_transfer=False, item_equipment_effect=False, npc_death=False, npc_remove=False, player_life=False, **kwargs):
        need(type(attack_intent) is bool, 'EXPLICIT_ATTACK_INTENT_SWITCH_REQUIRED')
        need(type(inventory_add) is bool, 'EXPLICIT_INVENTORY_SWITCH_REQUIRED')
        need(type(attack_feedback) is bool and (not attack_feedback or attack_intent),
             'EXPLICIT_ATTACK_FEEDBACK_SWITCH_REQUIRED')
        need(type(restart_enabled) is bool, 'EXPLICIT_RESTART_SWITCH_REQUIRED')
        need(type(item_use_intent) is bool, 'EXPLICIT_ITEM_USE_INTENT_SWITCH_REQUIRED')
        need(type(inventory_update) is bool, 'EXPLICIT_INVENTORY_UPDATE_SWITCH_REQUIRED')
        super().__init__(*args, **kwargs)
        self._quit_drained = {}
        need(type(player_life) is bool, 'PLAYER_LIFE_EXPLICIT_TRANSPORT_SWITCH_REQUIRED')
        self.player_life = player_life
        self.attack_intent = attack_intent
        self.attack_feedback = attack_feedback
        self.inventory_add = inventory_add
        self.restart_enabled = restart_enabled
        self.item_use_intent = item_use_intent
        need(type(item_transfer) is bool, 'EXPLICIT_ITEM_TRANSFER_SWITCH_REQUIRED')
        self.item_transfer = item_transfer
        self.inventory_update = inventory_update
        need(type(item_equipment_effect) is bool, 'EQUIPMENT_EXPLICIT_TRANSPORT_SWITCH_REQUIRED')
        self.item_equipment_effect = item_equipment_effect
        need(type(npc_death) is bool and type(npc_remove) is bool
             and (not npc_death or attack_feedback) and (not npc_remove or npc_death),
             'NPC_DEATH_EXPLICIT_TRANSPORT_SWITCH_REQUIRED')
        self.npc_death, self.npc_remove = npc_death, npc_remove

    def _verified_exit(self, proof, now):
        need(type(proof) is dict and proof.get('status') == 'VERIFIED'
             and proof.get('owner') is self.owner and proof.get('handle') is self.handle
             and proof.get('job') is self.job and proof.get('signaled') is True
             and proof.get('identity_verified') is True and proof.get('job_empty') is True
             and proof.get('forced_cleanup_requested') is False
             and type(proof.get('exit_code')) is int and proof['exit_code'] == 0
             and type(proof.get('observed_ns')) is int and 0 <= proof['observed_ns'] <= now
             and now - proof['observed_ns'] <= self.FRESH_NS, 'QUIT_RETAINED_EXIT_UNVERIFIED')

    def mark_quit_drained(self, writer):
        row = self._connection(writer)
        need(row.stage == 1 and row.rx_boot == 2 and row.tx_boot == 3
             and row.drain_started_ns is None, 'QUIT_DRAIN_STATE_REQUIRED')
        self._quit_drained[id(writer)] = writer

    def received_drained_quit_terminal(self, writer, receipt, *, raw_size, now):
        """Account only one decoded no-effect Quit after first ACK drain."""
        self._time(now); self._open()
        row = self._connection(writer)
        need(type(receipt) is _TerminalQuitReceipt and receipt.writer is writer
             and receipt.policy_row is row and receipt.frame.opcode == QUIT_REQUEST
             and receipt.frame.payload == b'' and receipt.frame.wire_length == raw_size == 10
             and self._quit_drained.get(id(writer)) is writer
             and row.stage == 1 and row.rx_boot == 2 and row.tx_boot == 3
             and not row.eof and row.buffered == 0 and row.drain_started_ns is None
             and row.pending_opcode is None and row.pending_size == 0,
             'QUIT_TERMINAL_EXACT_NOEFFECT_RECEIPT_REQUIRED')
        row.rx_bytes.take(raw_size, now)
        row.rx_frames.take(1, now)
        row.received = min(MAX_COUNTER, row.received + 1)
        self._emit('rx', row.peer.port, QUIT_REQUEST, raw_size)

    def quit_drained_after_exit(self, writer, *, proof, queued_bytes, now):
        self._time(now); self._open(); self._verified_exit(proof, now)
        row = self._connection(writer)
        need(row.stage == 1 and row.rx_boot == 2 and row.tx_boot == 3
             and row.pending_opcode == QUIT_SUCCESS_OPCODE and row.pending_size == len(QUIT_SUCCESS_FRAME)
             and row.drain_started_ns is not None and now - row.drain_started_ns <= self.DRAIN_NS
             and type(queued_bytes) is int and queued_bytes == 0, 'EXACT_QUIT_DRAIN_REQUIRED')
        self._emit('tx', row.peer.port, row.pending_opcode, row.pending_size)
        row.sent = min(MAX_COUNTER, row.sent + 1)
        row.drain_started_ns = row.pending_opcode = None
        row.pending_size = 0
        self.mark_quit_drained(writer)

    def eof_after_quit_exit(self, writer, *, proof, decoder_empty, now):
        self._time(now); self._open(); self._verified_exit(proof, now)
        row = self._connection(writer)
        need(self._quit_drained.get(id(writer)) is writer and not row.eof
             and decoder_empty is True and row.buffered == 0 and row.drain_started_ns is None,
             'EXACT_DRAINED_QUIT_EOF_REQUIRED')
        row.eof = True
        self._emit('eof', row.peer.port)

    def received_frame(self, writer, sample, opcode, size, now):
        action=getattr(self,'_haction_list_feature',None)
        if opcode==0x4ed4 and action is not None:
            from tools.local_original_session.haction_list_ingress import Feature
            need(type(action) is Feature and action.attached and not action.closed,'HACTION_CURRENT_FEATURE')
            row=self.checkpoint(writer,sample,now)
            action.header_locked(writer,row,opcode,size)
            row.rx_frames.take(1,now);row.received+=1
            self._emit('rx',row.peer.port,opcode,size)
            return
        trade = getattr(self, '_shop_trade_feature', None)
        if opcode == 0x4ed1 and trade is not None:
            from tools.local_original_session.trade_ingress import Feature
            need(type(trade) is Feature and trade.attached and not trade.closed,
                 'TRADE_CURRENT_FEATURE_REQUIRED')
            row = self.checkpoint(writer, sample, now)
            need(row.drain_started_ns is None, 'DISPATCH_PAUSED_UNTIL_DRAIN')
            need(row.rx_boot == 2 and row.tx_boot == 3 and row.stage == 1, 'GAME_OPCODE_UNBOUND')
            trade.header_locked(writer, row, opcode, size)
            row.rx_frames.take(1, now)
            row.received += 1
            self._emit('rx', row.peer.port, opcode, size)
            return
        cast = getattr(self, '_cast_feature', None)
        if opcode == 0x4ee6 and cast is not None:
            from tools.local_original_session.cast_route import Feature
            need(type(cast) is Feature and cast.attached and not cast.closed,
                 'CAST_CURRENT_FEATURE_REQUIRED')
            row = self.checkpoint(writer, sample, now)
            need(row.drain_started_ns is None, 'DISPATCH_PAUSED_UNTIL_DRAIN')
            need(row.rx_boot == 2 and row.tx_boot == 3 and row.stage == 1, 'GAME_OPCODE_UNBOUND')
            cast.header_locked(writer, row, opcode, size)
            row.rx_frames.take(1, now)
            row.received += 1  # Header refuses saturation; no new input identifier.
            self._emit('rx', row.peer.port, opcode, size)
            return
        dialogue = getattr(self, '_dialogue_feature', None)
        if opcode == 0x4e43 and dialogue is not None:
            need(dialogue.attached and not dialogue.closed, 'DIALOGUE_CURRENT_FEATURE_REQUIRED')
            row = self.checkpoint(writer, sample, now)
            need(row.drain_started_ns is None, 'DISPATCH_PAUSED_UNTIL_DRAIN')
            need(type(opcode) is int and type(size) is int and 8 <= size <= 17, 'DIALOGUE_CLIENT_FRAME_BOUND')
            need(row.rx_boot == 2 and row.tx_boot == 3 and row.stage == 1, 'GAME_OPCODE_UNBOUND')
            row.rx_frames.take(1, now)
            row.received = min(MAX_COUNTER, row.received + 1)
            self._emit('rx', row.peer.port, opcode, size)
            return
        extension = (0x4e2b, settings.OPCODE, QUIT_REQUEST, ALIVE_REQUEST)
        if getattr(self, 'player_life', False) is True: extension += (0x4eec,)
        if getattr(self, 'attack_intent', False) is True:
            extension += (ATTACK_REQUEST,)
        if getattr(self, 'restart_enabled', False) is True:
            extension += (RESTART_REQUEST,)
        if getattr(self, 'item_use_intent', False) is True:
            extension += (ITEM_USE_REQUEST,)
        if self.item_transfer:
            extension += (0x4e3f, 0x4e3e)
        if opcode not in extension:
            return super().received_frame(writer, sample, opcode, size, now)
        # Only these source-bound game opcodes extend the frozen policy. Preserve its
        # exact current-owner, stage, rate, drain and size checks.
        row = self.checkpoint(writer, sample, now)
        need(row.drain_started_ns is None, 'DISPATCH_PAUSED_UNTIL_DRAIN')
        need(type(opcode) is int and type(size) is int and 10 <= size <= self.MAX_FRAME,
             'CLIENT_FRAME_BOUND')
        need(row.rx_boot == 2 and row.tx_boot == 3 and row.stage == 1, 'GAME_OPCODE_UNBOUND')
        row.rx_frames.take(1, now)
        row.received = min(MAX_COUNTER, row.received + 1)
        self._emit('rx', row.peer.port, opcode, size)

    def begin_write(self, writer, sample, opcode, size, queued_bytes, now, *, dialogue_send_operation=None, trade_delivery_part=None, action_list_send_operation=None):
        if action_list_send_operation is not None:
            need(trade_delivery_part is None and dialogue_send_operation is None
                 and getattr(self,"_skill_write_operation",None) is None,"HACTION_EXCLUSIVE_POLICY")
            action=getattr(self,"_haction_list_feature",None)
            need(action is not None,"HACTION_CONFIGURED")
            action.policy_begin(action_list_send_operation,writer,opcode,size)
        if trade_delivery_part is not None:
            need(dialogue_send_operation is None and getattr(self,'_skill_write_operation',None) is None,
                 'SHOP_GENERIC_EXCLUSIVE_POLICY_OPERATION')
            delivery=getattr(self,'_shop_trade_delivery',None)
            need(delivery is not None,'SHOP_DELIVERY_CONFIGURED')
            delivery.policy_begin(trade_delivery_part,writer,opcode,size)
        if dialogue_send_operation is not None:
            need(getattr(self, '_skill_write_operation', None) is None, 'DIALOGUE_SKILL_EXCLUSIVE_POLICY_OPERATION_REQUIRED')
            dialogue = getattr(self, '_dialogue_feature', None)
            need(dialogue is not None, 'DIALOGUE_CURRENT_FEATURE_REQUIRED')
            dialogue.policy_begin(dialogue_send_operation, writer, opcode, size)
        else:
            need(opcode not in (0x4e44, 0x4e45), 'DIALOGUE_EXACT_OPERATION_REQUIRED')
        extension = (movement.CORRECTION_OPCODE, QUIT_SUCCESS_OPCODE, ALIVE_RESPONSE, npc_motion.OPCODE)
        if self.player_life and opcode in (0x4e39,0x4eed,0x4f16):
            extension += (opcode,)
            need(type(size) is int and 8 <= size <= 32, 'PLAYER_LIFE_FRAME_BOUND')
        if getattr(self, 'npc_death', False) is True and opcode == 0x4e39:
            extension += (opcode,)
            need(type(size) is int and 10 <= size <= 19, 'NPC_DEATH_FRAME_BOUND')
        if getattr(self, 'npc_remove', False) is True and opcode == 0x4e40:
            extension += (opcode,)
            need(type(size) is int and 8 <= size <= 17, 'NPC_REMOVE_FRAME_BOUND')
        if getattr(self, 'attack_feedback', False) is True:
            extension += (ATTACK_FEEDBACK,)
            if opcode == ATTACK_FEEDBACK:
                need(type(size) is int and 6 <= size <= 45, 'ATTACK_FEEDBACK_FRAME_BOUND')
        if getattr(self, 'restart_enabled', False) is True:
            extension += (RESTART_ACK,)
            if opcode == RESTART_ACK:
                need(type(size) is int and size == 8, 'RESTART_ACK_FRAME_BOUND')
        if getattr(self, 'inventory_update', False) is True:
            from tools.local_original_session import inventory_update
            extension += (inventory_update.OPCODE,)
            if opcode == inventory_update.OPCODE:
                need(type(size) is int and 6 <= size <= inventory_update.MAX_FRAME, 'INVENTORY_UPDATE_FRAME_BOUND')
        if getattr(self, 'item_equipment_effect', False) is True:
            from tools.local_original_session import equipment_change
            extension += (equipment_change.OPCODE,)
            if opcode == equipment_change.OPCODE:
                need(type(size) is int and 6 <= size <= equipment_change.MAX_FRAME, 'EQUIPMENT_FRAME_BOUND')
        if getattr(self, 'inventory_add', False) is True:
            from tools.local_original_session import inventory
            extension += (inventory.OPCODE,)
            if opcode == inventory.OPCODE:
                need(type(size) is int and 6 <= size <= inventory.MAX_FRAME, 'INVENTORY_FRAME_BOUND')
        if self.item_transfer and opcode in (0x0978, 0x4e96, 0x4e40):
            extension += (opcode,)
            need(type(size) is int and 6 <= size <= self.MAX_FRAME, 'ITEM_TRANSFER_FRAME_BOUND')
        skill = getattr(self, '_skill_write_operation', None)
        if skill is not None and opcode == 0x4e91:
            from tools.local_original_session.skill_cost_delivery import CostDelivery
            need(type(skill) is CostDelivery and skill.phase == 'SENDING'
                 and skill.binding.writer is writer and skill.frames[skill.index][2:4] == b'\x91\x4e'
                 and len(skill.frames[skill.index]) == size, 'RESOURCE_EXACT_BUFF_POLICY_OPERATION_REQUIRED')
            extension += (opcode,)
        if dialogue_send_operation is not None:
            need(opcode in (0x4e44, 0x4e45), 'DIALOGUE_RESPONSE_OPCODE_REQUIRED')
            extension += (opcode,)
        if trade_delivery_part is not None:
            need(opcode in (0x0964,0x0965,0x0978),'SHOP_TYPED_INVENTORY_ONLY')
            extension+=(opcode,)
        if action_list_send_operation is not None:
            need(opcode in (0x4eef,0x4e48,0x4ee7),'HACTION_TYPED_REPLY_ONLY')
            extension+=(opcode,)
        if opcode in (0x4e48,0x4ee7):need(action_list_send_operation is not None,'HACTION_LIST_CAP_REQUIRED')
        if opcode not in extension:
            return super().begin_write(writer, sample, opcode, size, queued_bytes, now)
        row = self.checkpoint(writer, sample, now)
        need(row.drain_started_ns is None, 'ONE_WRITE_DRAIN_REQUIRED')
        need(type(size) is int and 6 <= size <= self.MAX_FRAME and type(opcode) is int,
             'SERVER_FRAME_BOUND')
        need(type(queued_bytes) is int and 0 <= queued_bytes
             and queued_bytes + size <= self.WRITE_HIGH, 'TRANSPORT_BACKPRESSURE_BOUND')
        need(row.rx_boot == 2 and row.tx_boot == 3 and row.stage == 1, 'SERVER_OPCODE_UNBOUND')
        row.tx_frames.take(1, now)
        row.tx_bytes.take(size, now)
        row.drain_started_ns, row.pending_size, row.pending_opcode = now, size, opcode

    def eof_retained(self, writer, *, retained_alive, decoder_empty, now):
        """Terminal EOF requires native liveness, not a departed TCP tuple.

        The adapter calls this only after actual reader EOF and its trusted
        retained-process callback. It admits no read payload, dispatch or write;
        those continue to require the unchanged current exact-tuple checkpoint.
        No OwnerSample purporting to prove a live tuple is constructed here.
        """
        self._time(now)
        self._open()
        row = self._connection(writer)
        need(retained_alive is True, 'CURRENT_RETAINED_OWNER_REQUIRED')
        need(not row.eof and decoder_empty is True and row.buffered == 0
             and row.drain_started_ns is None, 'COMPLETE_EOF_REQUIRED')
        row.eof = True
        self._emit('eof', row.peer.port)


class LocalRealm:
    """Reuse the verified own-login/create/select schemas and CP57 world DTOs.

    CP57 SelfInfo/Actor retain the default explicit local baseline. The optional
    CP73 spawn experiment uses CP74's pinned DTO producer. A different
    saved name/UID is refused rather than silently given that baseline identity.
    CharacterStore's existing format is unchanged; positions use its explicit
    sibling sidecar. Only restored map0 is supported by the current map profile.
    """
    def __init__(self, expected_uuid, store_path, *, edge_passability=None, settings_path=None,
                 world_profile=BASELINE_WORLD, npc_spawns=(), npc_motion_interval_ns=None,
                 npc_edge_passability=None, npc_motion_policy=None):
        need(type(world_profile) is str and world_profile in (BASELINE_WORLD, CP73_SPAWN_WORLD),
             'KNOWN_LOCAL_WORLD_PROFILE_REQUIRED')
        profile_hook = actor_hook
        if world_profile == CP73_SPAWN_WORLD:
            from tools.local_native_login_spawn_render_retry_runtime import spawn_hook
            profile_hook = spawn_hook  # Existing CP74 profiles/frames validate all pinned sources.
        self.world_profile = world_profile
        # Validate the canonical UUID without inventing socket-address semantics.
        login.LocalLoginRequest(0, 'standalone.local', expected_uuid)
        need(isinstance(store_path, Path) and store_path.is_absolute(),
             'EXPLICIT_ABSOLUTE_STORE_PATH_REQUIRED')
        self.expected_uuid = expected_uuid
        self.store = ack.realm.CharacterStore(store_path)
        self.positions = movement.PositionStore(store_path)
        self.settings = (settings.SettingsStore(settings_path, expected_uuid, profile_path=store_path)
                         if settings_path is not None else None)
        self._settings_failed = False
        self._account_bound, self._quit = {}, {}
        self._quit_closed = deque(maxlen=4)
        need(edge_passability is None or callable(edge_passability), 'EDGE_CALLBACK_REQUIRED')
        self.edge_passability = edge_passability or (lambda *_: None)
        _roster, character_uids = self.store.snapshot()  # 기존 cold 읽기의 실제 UID 집합을 재사용한다.
        self.registry = session.Registry()
        self.login_consumed = False
        self.map_frame = map_hook.map_frame()
        self.self_frame, self.actor_frame = profile_hook.frames()
        # Validate before sockets become visible; no repeated source hashing in
        # a per-packet loop. The launcher retains and checks the source context.
        map_hook.validate_map_frame(self.map_frame)
        profile_hook.validate_world_frame(self.self_frame, (self.self_frame, self.actor_frame))
        profile_hook.validate_world_frame(self.actor_frame, (self.self_frame, self.actor_frame))
        profile, actor, _, _ = profile_hook.profiles()
        self.profile_uid, self.profile_name = profile.fields[1], actor[9]
        self._self_fields, self._actor_fields = dict(profile.fields), dict(actor)
        self._hp_status = None
        self._hp_resource_owner = None
        self._canonical_provider = None
        self._npc_player_hit = None
        if len(npc_spawns)==2:
            need(self.profile_uid==1 and tuple(spawn.uid for spawn in npc_spawns)==(2,3)
                 and 3 not in character_uids and not self.registry._sessions and not self.registry.selected
                 and not getattr(self,'_npc_spawns',()) and not getattr(self,'_npc_frames',{}),
                 'NPC_TWO_EXPLICIT_COLD_UID3_UNUSED_REQUIRED')
        self._npc_spawns = npc.prepare(npc_spawns, self_uid=self.profile_uid)
        self._npc_frames_by_uid = {}
        self._npc_frames = {}
        self._npc_respawn = None
        need((npc_motion_interval_ns is None and npc_edge_passability is None and npc_motion_policy is None)
             or (bool(self._npc_spawns) and type(npc_motion_interval_ns) is int
                 and 0 < npc_motion_interval_ns < (1 << 63) and callable(npc_edge_passability)
                 and npc_motion_policy == npc_motion.LOCAL_PRE_STEP),
             'NPC_MOVE_EXPLICIT_POLICY_INTERVAL_AND_NPC_EDGE_REQUIRED')
        self._npc_motion_interval_ns = npc_motion_interval_ns
        self._npc_motion_policy = npc_motion_policy
        self.npc_edge_passability = npc_edge_passability  # Never use the player-only edge adapter.
        self._npc_motion = {}
        self._attack_session = None  # Bound by the real broker, before accepts.
        self._item_use_session = None
        self._restart_broker = None
        self._item_transfer_broker = None
        self._inventory_broker = None
        self._inventory_update_broker = None
        words = movement.authority.unpack_grid(actor[1])
        _, self.self_frame, self.actor_frame = self._frames_for(
            movement.Position(self.profile_uid, self.profile_name, 0, *words))
        self._movement = {}  # At most the two current endpoint game writers.
        self._world_frames = {}
        self._movement_closed = deque(maxlen=4)

    def bind_attack_session(self, service):
        from tools.local_original_session.attack_session import AttackSession
        need(type(service) is AttackSession and service.policy == ATTACK_INTENT_POLICY
             and service.targets.broker.realm is self
             and service.targets.broker._attack_session is service
             and self._attack_session is None and not self.registry._sessions
             and bool(self._npc_spawns), 'ATTACK_SAME_REAL_BROKER_SESSION_REQUIRED')
        self._attack_session = service

    def bind_item_use_session(self, service):
        from tools.local_original_session.item_use_session import ItemUseSession, POLICY
        need(type(service) is ItemUseSession and service.policy == POLICY
             and service.broker.realm is self and service.broker._item_use_session is service
             and self._item_use_session is None and not self.registry._sessions,
             'ITEM_USE_SAME_REAL_BROKER_SESSION_REQUIRED')
        self._item_use_session = service

    def _replace_item_use_selection(self, broker, writer, old, new):
        """Opt-in same-account/new-selection replacement; ordinary bind stays strict."""
        from tools.local_original_session.item_use_session import ItemUseSession, POLICY
        generation = broker._inventory_generation
        need(broker.realm is self and broker.inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
             and type(generation) is _InventoryGeneration and generation.broker is broker
             and generation.phase == 'PREPARING' and generation.writer is writer
             and generation.lock is generation.row['operation_lock'] and generation.lock.locked()
             and self.registry.resolve(writer) is generation.game
             and generation.game.selection is generation.selected
             and generation.previous is not None and generation.previous.phase == 'RETIRED'
             and generation.previous.item_use_session is old and old is self._item_use_session
             and type(old) is ItemUseSession and old.closed
             and type(new) is ItemUseSession and new.policy == POLICY
             and new.broker is broker and new._service is generation.service
             and broker._item_use_session is new,
             'ITEM_USE_RESELECTION_REPLACEMENT_REQUIRED')
        self._item_use_session = new

    def world_profile_report(self):
        return dict(profile=self.world_profile,
                    fallback_policy=(self.world_profile if self.world_profile == CP73_SPAWN_WORLD
                                     else 'EXPLICIT_LOCAL_SOURCE_BASELINE'),
                    fallback_is_original_spawn=False, uid=self.profile_uid, map_id=0,
                    fallback_grid=list(movement.authority.unpack_grid(self._actor_fields[1])),
                    position_policy='SAVED_UID_POSITION_FIRST_ELSE_PROFILE_FALLBACK')

    def _frames_for(self, position, *, status_fields=None):
        need(position.uid == self.profile_uid and position.name == self.profile_name
             and position.map_id == 0, 'EXACT_PROFILE_OWN_STORED_SELECTION_REQUIRED')
        actor = dict(self._actor_fields)
        actor[1] = position.packed  # Existing ActorNotify field1 packed grid.
        fields = self._self_fields if status_fields is None else status_fields
        session.world.validate_self_spawn(fields, actor, this_is_self=True)
        def encode(opcode, fields):
            body = session.world.encode_payload(opcode, fields)
            return (len(body) + 6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little') + body + b'\0\0'
        # SelfInfo has no grid field. Preserve its source field numbers/values.
        return self.map_frame, encode(0x4e38, fields), encode(0x4e96, actor)

    def service(self, writer):
        row = self._movement.get(id(writer))
        need(row is not None and row[0] is writer, 'SAME_SELECTED_MOVEMENT_WRITER_REQUIRED')
        return row[1]

    def world_frames(self, writer):
        service = self.service(writer)
        cached = self._world_frames.get(id(writer))
        if cached is None or cached[0] is not service.snapshot():
            status = getattr(self, '_hp_status', None)
            fields = None if status is None else status.fields_for(writer)
            cached = (service.snapshot(), self._frames_for(service.snapshot(), status_fields=fields))
            self._world_frames[id(writer)] = cached
        return cached[1]

    def grant(self, writer, *, movement_owner_guard=None, account_owner_guard=None,
              closing_quit_owner_guard=None, connection_id=None):
        need(closing_quit_owner_guard is None or
             (type(closing_quit_owner_guard) is _ClosingQuitOwnerGuard
              and closing_quit_owner_guard.broker.realm is self
              and closing_quit_owner_guard.writer is writer
              and closing_quit_owner_guard.row['writer'] is writer
              and closing_quit_owner_guard.broker._source_quit_closing is not None),
             'QUIT_CLOSING_CALLBACK_REQUIRED')
        empty = dict(schema='lc-owned-local-core-roster-v1', realm='owned-local',
                     source_provenance='explicit_local_game_configuration',
                     expected_count=0, display_slots=3, rows=[], existing_rows=[],
                     mode='initial', allow_expected_growth=False)

        def selection(selected):
            result = self.store.select(selected.reference)
            need(type(result[0]) is int and result[0] == self.profile_uid
                 and selected.reference == self.profile_name,
                 'EXACT_PROFILE_OWN_STORED_SELECTION_REQUIRED')
            need(callable(movement_owner_guard), 'SELECTED_MOVEMENT_OWNER_GUARD_REQUIRED')
            need(id(writer) not in self._movement, 'MOVEMENT_WRITER_REUSE_REFUSED')
            need(len(self._movement) < 2, 'MOVEMENT_SESSION_LIMIT')
            words = movement.authority.unpack_grid(self._actor_fields[1])
            initial = movement.Position(result[0], selected.reference, 0, *words)
            service = movement.MovementService(initial, connection=writer,
                owner_guard=movement_owner_guard, edge_passability=self.edge_passability,
                store=self.positions)
            self._frames_for(service.snapshot())  # Preserve saved-map/spawn validation.
            self._movement[id(writer)] = (writer, service, connection_id)
            # First cache materialization belongs to world_frames AFTER the
            # selected inventory Binding and RESOURCE restore hook below.
            # Do not cache profile HP/MP while selection is still being bound.

        game = self.registry.register_own(writer, empty, on_selection=selection)

        def refresh():
            roster, references = self.store.snapshot()
            game.roster = session.Roster(roster.frames, references)
        refresh()

        async def receive_login(payload):
            self.registry.resolve(writer)
            need(not self.login_consumed and not game.list_sent and game.selection is None,
                 'OWN_LOGIN_ORDER_OR_REPLAY')
            request = login.parse(payload)
            need(request.guest_uuid == self.expected_uuid and request.issuer == 'standalone.local',
                 'OWN_LOGIN_IDENTITY_MISMATCH')
            self.login_consumed = True
            game.list_sent = True
            self._account_bound[id(writer)] = (writer, game)
            return (ack.ACK_FRAME,) + game.roster.frames

        async def create(payload):
            self.registry.resolve(writer)
            need(game.list_sent and game.selection is None, 'CREATE_OWN_SESSION_ORDER_REQUIRED')
            self.store.create(ack.realm.decode_creation(payload))
            refresh()
            return (ack.realm.create_ack(0),) + game.roster.frames

        prior_select = game.routes[0x4e28]

        async def select(payload):
            self.registry.resolve(writer)
            need(game.list_sent and game.selection is None, 'ENTER_OWN_SESSION_ORDER_REQUIRED')
            replies = await prior_select(payload)
            need(replies == () and game.selection is not None, 'EXACT_OWNED_SELECTION_REQUIRED')
            if self._inventory_broker is not None:
                await self._inventory_broker._restore_inventory_selection(writer)
            canonical_provider = getattr(self, '_canonical_provider', None)
            if canonical_provider is not None:
                selected_binding = canonical_provider.bind_selected(writer)
                initialize = getattr(self, '_canonical_initialize_selected_locked', None)
                if initialize is not None:
                    initialize(selected_binding)
                    canonical_provider.current(selected_binding)
            resource_owner = getattr(self, '_hp_resource_owner', None)
            if resource_owner is not None:
                resource_owner.selection_locked(writer, payload)
            if self._npc_spawns:
                service = self.service(writer)
                position = service.snapshot()
                need(await movement_owner_guard(writer, position) is True,
                     'NPC_CURRENT_SELECTED_OWNER_REQUIRED')
                self._npc_authority(writer, game, service, position)
                need(all(spawn.map_id == position.map_id for spawn, _ in self._npc_spawns),
                     'NPC_SELECTED_MAP_REQUIRED')
                self._npc_frames[id(writer)] = (writer, game, service,
                                                tuple(spawn.frame() if self._npc_respawn is not None else frame
                                                      for spawn, frame in self._npc_spawns))
                if len(self._npc_spawns)>1:
                    for (spawn,_),wire in zip(self._npc_spawns,self._npc_frames[id(writer)][3]):
                        self._npc_frames_by_uid[(id(writer),spawn.uid)]=(writer,game,service,(wire,))
                if self._npc_motion_interval_ns is not None:
                    movers={spawn.uid:npc_motion.NpcMotion(spawn,self_uid=position.uid,
                        interval_ns=self._npc_motion_interval_ns,policy=self._npc_motion_policy)
                        for spawn,_ in self._npc_spawns}
                    self._npc_motion[id(writer)]=(writer,next(iter(movers.values())) if len(movers)==1 else movers)
            shop_selected = getattr(self, '_shop_quest_selected_locked', None)
            if shop_selected is not None:
                canonical_provider = getattr(self, '_canonical_provider', None)
                need(canonical_provider is not None, 'SHOP_QUEST_CANONICAL_CONNECTION_SCOPE_REQUIRED')
                binding = canonical_provider.bind_selected(writer)
                shop_selected(binding)
                canonical_provider.current(binding)
            return ((ack.ENTER_ACK_FRAME,) + self.world_frames(writer)
                    + (self._npc_frames[id(writer)][3] if self._npc_spawns else ()))

        async def move(payload):
            self.registry.resolve(writer)
            need(game.selection is not None, 'SELECTED_MOVEMENT_REQUIRED')
            result = await self.service(writer).handle_CS4E2B(payload)
            if result.fatal or result.reason in ('OWNER_REFUSED', 'OWNER_UNKNOWN'):
                raise ValueError(result.reason)
            return result.replies

        async def alive(payload):
            # Explicit local selected-account policy, not original server policy.
            self.bound_account(writer, game)
            need(game.selection is not None and callable(movement_owner_guard),
                 'ALIVE_SELECTED_OWNER_REQUIRED')
            service = self.service(writer)
            position, selected = service.snapshot(), game.selection
            need(not service.fatal and not self._settings_failed, 'ALIVE_SELECTED_STORAGE_FATAL')
            alive_request_metadata(payload)  # Borrowed values are discarded on return.
            need(await movement_owner_guard(writer, position) is True, 'ALIVE_CURRENT_SELECTED_OWNER_REQUIRED')
            self.bound_account(writer, game)
            need(self.service(writer) is service and not service.fatal and not self._settings_failed
                 and service.snapshot() is position and game.selection is selected
                 and selected.reference == position.name
                 and self.registry.selected.get(position.name) is selected,
                 'ALIVE_CURRENT_SELECTED_AUTHORITY_REQUIRED')
            return (ALIVE_FRAME,)  # Same-session typed reply; no echoed ID or payload.

        async def item_use_intent(payload):
            self.registry.resolve(writer)
            service = self._item_use_session
            need(service is not None and service.broker.realm is self
                 and service.broker._item_use_session is service,
                 'ITEM_USE_SAME_REAL_BROKER_SESSION_REQUIRED')
            accepted_before = service.accepted_count
            replies = await service.handle(writer, payload)  # Existing _serve row lock, same immutable payload.
            effect = getattr(service.broker, '_item_equipment_effect', None)
            if effect is not None and service.accepted_count == accepted_before + 1:
                from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
                from tools.local_original_session.item_use_session import _Intent
                need(type(effect) is ItemEquipmentEffect and effect.consume_locked.__func__ is ItemEquipmentEffect.consume_locked,
                     'EQUIPMENT_ORIGINAL_EFFECT_CONSUMER_REQUIRED')
                need(effect.prepare_locked.__func__ is ItemEquipmentEffect.prepare_locked,
                     'EQUIPMENT_ORIGINAL_PREPARE_REQUIRED')
                ordinal, intent = service.accepted_count, service._current
                need(type(intent) is _Intent and intent.writer is writer and intent.accepted_ordinal == ordinal
                     and intent.frame is service.broker._inventory_current_frame
                     and intent.selection_binding is service.broker._inventory_selection_binding,
                     'EQUIPMENT_EXACT_NEW_ACCEPTED_INTENT_REQUIRED')
                # The received request already owns the real row lock. Initial
                # sync may not have reached the feature poll yet; finish it here
                # before consuming this same accepted intent, without re-locking.
                initial = await effect.prepare_locked(writer)
                if initial['status'] == 'SYNCHRONIZED':
                    effect_outcome=await effect.consume_locked(writer, accepted_ordinal=ordinal, expected_intent=intent)
                    if (effect_outcome['status'],effect_outcome['phase'])==('COMMITTED','DRAINED') and service.broker._canonical_provider is not None:
                        await service.complete_backend_received(writer,ordinal,intent,effect=effect,source_owner=service.broker)
            need(type(replies) is tuple and replies == (), 'ITEM_USE_INTENT_REPLY_FORBIDDEN')
            return replies

        async def attack_intent(payload):
            self.registry.resolve(writer)
            service = self._attack_session
            need(service is not None and service.targets.broker.realm is self
                 and service.targets.broker._attack_session is service,
                 'ATTACK_SAME_REAL_BROKER_SESSION_REQUIRED')
            # _serve already holds this row's operation_lock. The session
            # checkpoints native ownership without reacquiring that lock.
            accepted_before = service.accepted_count
            replies = await service.handle(writer, payload)
            shop_hook = getattr(self, '_shop_quest_after_attack_locked', None)
            result = service.last_hp_result
            if (shop_hook is not None and service.accepted_count == accepted_before + 1
                    and result is not None and result.died
                    and result.accepted_ordinal == service.accepted_count):
                canonical_provider = getattr(self, '_canonical_provider', None)
                need(canonical_provider is not None, 'SHOP_QUEST_CANONICAL_CONNECTION_SCOPE_REQUIRED')
                binding = canonical_provider.bind_selected(writer)
                await shop_hook(binding, service, accepted_before)
                canonical_provider.current(binding)
            need(type(replies) is tuple and (replies == () or len(replies) == 1),
                 'ATTACK_BOUNDED_FEEDBACK_REQUIRED')
            for wire in replies:
                service.validate_feedback(writer, wire, state='PREPARED')
            return replies

        async def save_settings(payload):
            self.bound_account(writer, game)
            need(callable(account_owner_guard) and await account_owner_guard(writer) is True,
                 'SETTINGS_ACCOUNT_OWNER_REQUIRED')
            self.bound_account(writer, game)
            try:
                need(self.settings is not None, 'EXPLICIT_SETTINGS_STORAGE_REQUIRED')
                self.settings.save(settings.parse(payload))
            except BaseException:
                self._settings_failed = True
                raise ValueError('SETTINGS_PERSISTENCE_FATAL') from None
            return ()  # No source evidence requires an ACK or automatic echo.

        async def quit_game(payload):
            self.bound_account(writer, game)
            need(type(payload) in (bytes, bytearray, memoryview) and len(payload) == 0,
                 'QUIT_EMPTY_SOURCE_BODY_REQUIRED')
            need(game.selection is not None and callable(movement_owner_guard), 'QUIT_SELECTED_OWNER_REQUIRED')
            service = self.service(writer)
            position = service.snapshot()
            need(not service.fatal, 'QUIT_SELECTED_STORAGE_FATAL')
            state = dict(writer=writer, uid=position.uid, source_connection_id=connection_id,
                         selected=game.selection, position=position,
                         duplicate_requests=0, request_verified=False,
                         response_drain_returned=False, response_queue_empty=False, response_drained=False)
            self._quit[id(writer)] = state  # Block parallel requests until the first response drains.
            need(await movement_owner_guard(writer, position) is True, 'QUIT_CURRENT_SELECTED_OWNER_REQUIRED')
            self.bound_account(writer, game)
            need(service.snapshot() is position and not self._settings_failed,
                 'QUIT_CURRENT_SELECTED_AUTHORITY_REQUIRED')
            state['request_verified'] = True
            return (QUIT_SUCCESS_FRAME,)

        async def duplicate_quit(payload):
            state = self._quit.get(id(writer))
            need(state is not None and state['writer'] is writer and state['request_verified'] is True
                 and state['response_drain_returned'] is True and state['response_drained'] is True
                 and state['response_queue_empty'] is True, 'QUIT_TERMINAL_SESSION')
            need(type(payload) in (bytes, bytearray, memoryview) and len(payload) == 0,
                 'QUIT_EMPTY_SOURCE_BODY_REQUIRED')
            self.bound_account(writer, game)
            service = self.service(writer)
            position, selected = state['position'], state['selected']

            def exact():
                self.bound_account(writer, game)
                return (self._quit.get(id(writer)) is state and not self._settings_failed
                        and state['writer'] is writer and state['request_verified'] is True
                        and state['response_drain_returned'] is True
                        and state['response_drained'] is True and state['response_queue_empty'] is True
                        and not service.fatal and self.service(writer) is service
                        and service.snapshot() is position and position.uid == state['uid']
                        and game.selection is selected and selected is not None
                        and selected.reference == position.name
                        and self.registry.selected.get(position.name) is selected)

            need(exact() and callable(movement_owner_guard), 'QUIT_CURRENT_SELECTED_AUTHORITY_REQUIRED')
            duplicate_owner = closing_quit_owner_guard or movement_owner_guard
            need(await duplicate_owner(writer, position) is True, 'QUIT_CURRENT_SELECTED_OWNER_REQUIRED')
            need(exact(), 'QUIT_CURRENT_SELECTED_AUTHORITY_REQUIRED')
            # Explicit local idempotency: preserve the first terminal state and
            # its one ACK. This does not assert why the original retries Quit.
            state['duplicate_requests'] = min(MAX_COUNTER, state['duplicate_requests'] + 1)
            return ()

        read_news_seen = False

        async def read_news(payload):
            nonlocal read_news_seen
            self.registry.resolve(writer)
            need(game.list_sent and game.selection is None and not read_news_seen,
                 'READ_NEWS_OWN_SESSION_ORDER_REQUIRED')
            with ack.realm.pb.parse_message(payload, schema={1: 0, 2: 0, 3: 0},
                 limits=ack.realm.pb.WireLimits(max_body=64, max_fields=3, max_field_bytes=64)) as parsed:
                need(len(parsed.occurrences(1)) <= 1
                     and all(len(parsed.occurrences(n)) == 1 for n in (2, 3)),
                     'READ_NEWS_SOURCE_FIELDS_REQUIRED')
                if parsed.occurrences(1):
                    need(parsed.occurrences(1)[0].value in (0, 1), 'READ_NEWS_BOOL_REQUIRED')
                for n in (2, 3):
                    ack.realm._i32(parsed.occurrences(n)[0].value)
            read_news_seen = True
            return ()

        async def restart_game(payload):
            need(self._restart_broker is not None and self._restart_broker.realm is self,
                 'RESTART_REAL_BROKER_REQUIRED')
            return await self._restart_broker._prepare_restart(writer, payload)

        async def item_drop(payload):
            broker = self._item_transfer_broker
            need(broker is not None and broker.realm is self, 'ITEM_TRANSFER_REAL_BROKER_REQUIRED')
            service = broker._inventory_generation.transfer_session
            need(service is not None, 'ITEM_TRANSFER_CURRENT_SELECTED_SESSION_REQUIRED')
            return await service.handle(writer, payload, kind='DROP')

        async def item_pickup(payload):
            broker = self._item_transfer_broker
            need(broker is not None and broker.realm is self, 'ITEM_TRANSFER_REAL_BROKER_REQUIRED')
            service = broker._inventory_generation.transfer_session
            need(service is not None, 'ITEM_TRANSFER_CURRENT_SELECTED_SESSION_REQUIRED')
            return await service.handle(writer, payload, kind='PICKUP')

        game.routes.update({0x263: receive_login, 0x267: read_news,
                            ack.realm.CREATE_OPCODE: create, 0x4e28: select, 0x4e2b: move,
                            settings.OPCODE: save_settings, QUIT_REQUEST: quit_game,
                            ALIVE_REQUEST: alive})
        dialogue = getattr(self, '_dialogue_feature', None)
        if dialogue is not None:
            async def dialogue_request(payload):
                await dialogue.dispatch_locked(writer, 0x4e43, payload)
                return ()
            game.routes[0x4e43] = dialogue_request
        cast = getattr(self, '_cast_feature', None)
        if cast is not None:
            async def cast_request(payload):
                return await cast.dispatch_locked(writer, payload)
            game.routes[0x4ee6] = cast_request
        life_broker = getattr(self, '_player_life_broker', None)
        if life_broker is not None:
            async def dead_restart(payload):
                return await life_broker._player_life.request_locked(writer,payload)
            game.routes[0x4eec] = dead_restart
        if self._restart_broker is not None:
            game.routes[RESTART_REQUEST] = restart_game
        if self._attack_session is not None:
            game.routes[ATTACK_REQUEST] = attack_intent
        if self._item_use_session is not None:
            game.routes[ITEM_USE_REQUEST] = item_use_intent
        if self._item_transfer_broker is not None:
            game.routes[0x4e3f], game.routes[0x4e3e] = item_drop, item_pickup
        trade = getattr(self, '_shop_trade_feature', None)
        if trade is not None:
            async def trade_request(payload):
                provider = self._canonical_provider
                need(provider is not None, 'TRADE_CANONICAL_CONNECTION_SCOPE_REQUIRED')
                from tools.local_original_session import trade_ingress as trade_source
                need(type(trade) is trade_source.Feature, 'TRADE_EXACT_PREBIND_FEATURE')
                getter = trade.prebind_retirement_memory
                need(inspect.ismethod(getter) and getter.__self__ is trade
                     and getter.__func__ is trade_source.Feature.prebind_retirement_memory,
                     'TRADE_ORIGINAL_PREBIND_ACCESSOR')
                prebind = getter(writer, payload=payload)
                if prebind is not None:
                    retirement, before_bind, finish = prebind  # private-issued original bound callees
                    original_error = None
                    try:before_bind(writer, payload)
                    except BaseException as error:
                        original_error = error
                        raise
                    finally:
                        try:finish(writer, payload=payload)
                        except BaseException:
                            if original_error is None:raise
                            BaseException.add_note(original_error, 'SHOP admitted history cleanup refused; original failure preserved.')
                binding = provider.bind_selected(writer)
                await trade.dispatch_locked(binding, payload)
                provider.current(binding)
                return ()  # Original 4ED1 waits for no invented ACK.
            game.routes[0x4ed1] = trade_request
        action=getattr(self,'_haction_list_feature',None)
        if action is not None:
            async def action_request(payload):
                provider=self._canonical_provider
                need(provider is not None,'HACTION_CANONICAL_CONNECTION_SCOPE')
                binding=provider.bind_selected(writer)
                await action.dispatch_locked(binding,payload)
                provider.current(binding)
                return ()
            game.routes[0x4ed4]=action_request
        for opcode, handler in tuple(game.routes.items()):
            async def terminal_guard(payload, operation=handler, route_opcode=opcode):
                need(not self._settings_failed, 'SETTINGS_PERSISTENCE_FATAL')
                if id(writer) in self._quit and route_opcode == QUIT_REQUEST:
                    return await duplicate_quit(payload)
                need(id(writer) not in self._quit, 'QUIT_TERMINAL_SESSION')
                life_broker = getattr(self,'_player_life_broker',None)
                if life_broker is not None and route_opcode not in (0x4eec,QUIT_REQUEST,ALIVE_REQUEST,settings.OPCODE):
                    life_broker._player_life.check_normal_locked(writer)
                return await operation(payload)
            game.routes[opcode] = terminal_guard
        return game

    def bound_account(self, writer, game):
        bound = self._account_bound.get(id(writer))
        need(self.registry.resolve(writer) is game
             and bound is not None and bound[0] is writer and bound[1] is game and game.list_sent,
             'SAME_0263_BOUND_ACCOUNT_WRITER_REQUIRED')

    def _npc_authority(self, writer, game, service, position):
        self.bound_account(writer, game)
        selected = game.selection
        need(selected is not None and self.registry.selected.get(position.name) is selected
             and selected.reference == position.name and position.uid == self.profile_uid
             and self.service(writer) is service and service.snapshot() is position
             and not service.fatal and not self._settings_failed and id(writer) not in self._quit,
             'NPC_CURRENT_SELECTED_AUTHORITY_REQUIRED')
        saved_uid, _ = self.store.select(selected.reference)
        need(saved_uid == position.uid and self.positions.restore(position) == position,
             'NPC_CURRENT_SELECTED_STORAGE_REQUIRED')

    def _validate_npc_reply(self, writer, wire):
        if self._npc_respawn is not None and self._npc_respawn._pending is not None:
            self._npc_respawn.validate_pending_spawn(writer, wire)
            return
        bound = self._npc_frames.get(id(writer))
        need(bound is not None and bound[0] is writer and wire in bound[3],
             'EXACT_SELECTED_NPC_FRAME_REQUIRED')
        matched=[spawn.uid for (spawn,_),published in zip(self._npc_spawns,bound[3]) if wire==published]
        need(len(matched)==1 and (self._npc_respawn is None or any(wire is item for item in bound[3])
             and self.npc_mover(writer,target_uid=matched[0]).spawn_drained is False),
             'EXACT_SELECTED_NPC_FRAME_REQUIRED')
        _, game, service, _ = bound
        self._npc_authority(writer, game, service, service.snapshot())
        notifications = (None if self._attack_session is None else self._attack_session._notifications)
        if notifications is not None:
            for spawn, prepared in self._npc_spawns:
                if wire == prepared:
                    notifications.require_not_removed_spawn(writer, spawn.uid)
        need(all(spawn.map_id == service.snapshot().map_id for spawn, _ in self._npc_spawns),
             'NPC_SELECTED_MAP_REQUIRED')

    def npc_target_uid(self,target_uid=None):
        uids=tuple(spawn.uid for spawn,_ in self._npc_spawns)
        if target_uid is None:
            need(len(uids)==1,'NPC_EXPLICIT_TARGET_UID_REQUIRED')
            return uids[0]
        need(type(target_uid) is int and target_uid in uids,'NPC_CURRENT_TARGET_UID_REQUIRED')
        return target_uid

    def npc_key(self,writer,target_uid=None):
        uid=self.npc_target_uid(target_uid)
        return id(writer) if len(self._npc_spawns)==1 else (id(writer),uid)

    def npc_frames(self,writer,*,target_uid=None):
        uid=self.npc_target_uid(target_uid)
        all_frames=self._npc_frames.get(id(writer))
        need(all_frames is not None and all_frames[0] is writer,'NPC_SAME_WRITER_FRAMES_REQUIRED')
        if len(self._npc_spawns)==1:return all_frames
        bound=self._npc_frames_by_uid.get((id(writer),uid))
        need(bound is not None and all(a is b for a,b in zip(bound[:3],all_frames[:3]))
             and len(bound[3])==1 and any(bound[3][0] is wire for wire in all_frames[3]),
             'NPC_SAME_UID_FRAMES_REQUIRED')
        return bound

    def _replace_npc(self,writer,target_uid,wire,mover,*,frames=None):
        old=self.npc_frames(writer,target_uid=target_uid);whole=self._npc_frames[id(writer)]
        need(mover.state.uid==target_uid and sum(item is old[3][0] for item in whole[3])==1,
             'NPC_REPLACE_EXACT_UID_REQUIRED')
        if frames is None:frames=(writer,old[1],old[2],(wire,))
        need(all(a is b for a,b in zip(frames[:3],old[:3])) and len(frames[3])==1
             and frames[3][0] is wire,'NPC_REPLACE_CURRENT_FRAMES_REQUIRED')
        if len(self._npc_spawns)==1:
            self._npc_frames[id(writer)]=frames;self._npc_motion[id(writer)]=(writer,mover)
        else:
            bound=self._npc_motion[id(writer)]
            need(bound[0] is writer and target_uid in bound[1],'NPC_REPLACE_SAME_MOVER_SET_REQUIRED')
            self._npc_frames_by_uid[(id(writer),target_uid)]=frames
            self._npc_frames[id(writer)]=(writer,whole[1],whole[2],tuple(
                wire if item is old[3][0] else item for item in whole[3]))
            bound[1][target_uid]=mover
        return frames

    def _release_npc_motion(self,writer):
        bound=self._npc_motion.pop(id(writer),None)
        if bound is not None and bound[0] is writer:
            movers=bound[1].values() if type(bound[1]) is dict else (bound[1],)
            for mover in movers:mover.close()
        for key in tuple(self._npc_frames_by_uid):
            if key[0]==id(writer):del self._npc_frames_by_uid[key]

    def npc_motion_for_frame(self,writer,wire):
        bound=self._npc_motion.get(id(writer))
        need(bound is not None and bound[0] is writer,'NPC_MOVE_SAME_BOUND_WRITER_REQUIRED')
        movers=bound[1].values() if type(bound[1]) is dict else (bound[1],)
        matches=[m for m in movers if m.pending is not None and wire==m.pending.frame]
        need(len(matches)==1,'NPC_MOVE_EXACT_PENDING_UID_REQUIRED')
        return self.npc_mover(writer,target_uid=matches[0].state.uid)

    def npc_mover(self, writer, *, target_uid=None):
        bound = self._npc_motion.get(id(writer))
        need(bound is not None and bound[0] is writer, 'NPC_MOVE_SAME_BOUND_WRITER_REQUIRED')
        spawn = self._npc_frames.get(id(writer))
        need(spawn is not None and spawn[0] is writer, 'NPC_MOVE_BOUND_SPAWN_REQUIRED')
        _, game, service, _ = spawn
        self._npc_authority(writer, game, service, service.snapshot())
        uid=self.npc_target_uid(target_uid)
        mover=bound[1] if type(bound[1]) is not dict else bound[1].get(uid)
        need(mover is not None and mover.state.uid==uid
             and mover.state.map_id == service.snapshot().map_id, 'NPC_MOVE_SAME_MAP_REQUIRED')
        return mover

    def quit_state(self, writer):
        state = self._quit.get(id(writer))
        need(state is not None and state['writer'] is writer and state['request_verified'] is True,
             'VERIFIED_SELECTED_QUIT_REQUEST_REQUIRED')
        return state

    def quit_response_drained(self, writer, wire, queued_bytes):
        need(wire == QUIT_SUCCESS_FRAME, 'EXACT_QUIT_SUCCESS_RESPONSE_REQUIRED')
        state = self.quit_state(writer)
        state['response_drain_returned'] = True
        state['response_queue_empty'] = type(queued_bytes) is int and queued_bytes == 0

    @staticmethod
    def _quit_metadata(state):
        return {key: state[key] for key in ('uid', 'source_connection_id', 'request_verified', 'response_drain_returned',
                                           'response_queue_empty', 'response_drained', 'duplicate_requests')}

    def quit_report(self):
        sessions = [*list(self._quit_closed), *(self._quit_metadata(state) for state in self._quit.values())]
        return dict(active=len(self._quit), sessions=sessions, scope='SOURCE_QUIT_RESPONSE_DRAIN_ONLY',
                    source_quit_response_drained=any(all(row[key] is True for key in
                        ('request_verified', 'response_drain_returned', 'response_queue_empty', 'response_drained'))
                        for row in sessions),
                    duplicate_policy='LOCAL_DRAINED_EMPTY_QUIT_NO_EFFECT')

    def close(self, writer):
        trade = getattr(self, '_shop_trade_feature', None)
        if trade is not None: trade.retire(writer)
        action=getattr(self,"_haction_list_feature",None)
        if action is not None:action.retire(writer)
        cast = getattr(self, '_cast_feature', None)
        if cast is not None:
            cast.retire_writer(writer)
        shop_retire = getattr(self, '_shop_quest_retire_writer', None)
        if shop_retire is not None:
            shop_retire(writer)
        transfer_broker = self._item_transfer_broker
        if transfer_broker is not None:
            transfer = transfer_broker._inventory_generation.transfer_session
            if transfer is not None:transfer.release(writer)
        life = getattr(self,'_player_life',None)
        life_broker = getattr(self,'_player_life_broker',None)
        if life is None and life_broker is not None: life = life_broker._player_life
        if life is not None: life.release(writer)
        player_hit = getattr(self, '_npc_player_hit', None)
        if player_hit is not None:
            player_hit.release(writer)
        status = getattr(self, '_hp_status', None)
        if status is not None:
            status.release(writer)
        if self._npc_respawn is not None:
            self._npc_respawn.release(writer)
        if self._item_use_session is not None:
            self._item_use_session.release(writer)
        if self._attack_session is not None:
            self._attack_session.release(writer)
        self._account_bound.pop(id(writer), None)
        state = self._quit.pop(id(writer), None)
        if state is not None and state['writer'] is writer:
            self._quit_closed.append(self._quit_metadata(state))
        row = self._movement.pop(id(writer), None)
        if row is not None and row[0] is writer:
            self._movement_closed.append(self._movement_metadata(row, closed=True))
        self._world_frames.pop(id(writer), None)
        self._npc_frames.pop(id(writer), None)
        self._release_npc_motion(writer)
        self.registry.close(writer)

    @staticmethod
    def _movement_metadata(row, *, closed=False):
        _, service, cid = row
        return dict(connection_id=cid, committed=service.committed,
                    requests_received=getattr(service, 'requests_received', None),
                    corrections_prepared=getattr(service, 'corrections_prepared', None),
                    authority=service.snapshot().metadata(),
                    last_result=copy.deepcopy(service.last_result), fatal=service.fatal,
                    closed=closed)

    def movement_report(self):
        sessions = [*copy.deepcopy(list(self._movement_closed)),
                    *(self._movement_metadata(row) for row in self._movement.values())]
        return dict(committed=min(MAX_COUNTER, sum(row['committed'] for row in sessions)),
                    active_services=len(self._movement), sessions=sessions)

    def edge_report(self):
        from tools.local_original_session import edge
        row = getattr(self.edge_passability, 'last_result', None)
        if type(row) is not dict:
            return dict(status='UNKNOWN', reason='NOT_SAMPLED', typed_bytes_requested=0)
        status, code, requested = (row.get('status'), row.get('reason'), row.get('typed_bytes_requested'))
        return dict(status=status if status in ('UNKNOWN', 'CLEAR_EMPTY_SUBSET',
                                               'CLEAR_OWN_SELF_SUBSET', 'BLOCKED_MASK1') else 'UNKNOWN',
                    reason=code if code is None or type(code) is str
                    and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}', code) else 'EDGE_READ_FAILED',
                    typed_bytes_requested=requested if type(requested) is int
                    and 0 <= requested <= edge.LIMIT else None)

    def validate_reply(self, wire, *, writer=None):
        need(type(wire) in (bytes, bytearray) and 6 <= len(wire) <= 65535
             and int.from_bytes(wire[:2], 'little') == len(wire) and wire[-2:] == b'\0\0',
             'SOURCE_REPLY_FRAME_REQUIRED')
        opcode = int.from_bytes(wire[2:4], 'little')
        if opcode in (0x264, 0x4e25, 0x4e29):
            need(wire == {0x264: ack.ACK_FRAME, 0x4e25: ack.realm.create_ack(0),
                          0x4e29: ack.ENTER_ACK_FRAME}[opcode], 'EXACT_LOCAL_ACK_REQUIRED')
        elif opcode in (0x4e95, 0x4e38, 0x4e96):
            frames = self.world_frames(writer)
            if self._npc_spawns and opcode == 0x4e96 and wire != frames[2]:
                self._validate_npc_reply(writer, wire)
            else:
                need(wire == frames[(0x4e95, 0x4e38, 0x4e96).index(opcode)], 'EXACT_LOCAL_WORLD_REQUIRED')
                status = getattr(self, '_hp_status', None)
                if opcode == 0x4e38 and status is not None and id(writer) in status._states:
                    status.validate(writer, wire, phase='PREPARED')
        elif opcode == movement.CORRECTION_OPCODE:
            need(wire == movement.correction_frame(self.service(writer).snapshot()),
                 'EXACT_CURRENT_MOVEMENT_CORRECTION_REQUIRED')
        elif opcode == npc_motion.OPCODE:
            self.npc_motion_for_frame(writer,wire).validate_frame(wire)
        elif opcode == QUIT_SUCCESS_OPCODE:
            state = self.quit_state(writer)
            need(wire == QUIT_SUCCESS_FRAME and state['response_drained'] is False,
                 'EXACT_QUIT_SUCCESS_RESPONSE_REQUIRED')
        elif opcode == 0x097a:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            effect = getattr(self, '_item_equipment_effect', None)
            need(type(effect) is ItemEquipmentEffect, 'EQUIPMENT_NOTIFY_ENABLED_REQUIRED')
            effect.validate_reply(writer, wire)
        elif opcode == 0x0965:
            need(self._inventory_update_broker is not None, 'INVENTORY_UPDATE_DISABLED')
            self._inventory_update_broker._validate_inventory_update_reply(writer, wire)
        elif opcode == RESTART_ACK:
            need(self._restart_broker is not None, 'RESTART_DISABLED')
            self._restart_broker._validate_restart(writer, wire, phase='PREPARED')
        elif opcode in (0x4e39, 0x4e40):
            need(self._attack_session is not None and self._attack_session._notifications is not None,
                 'NPC_DEATH_NOTIFICATIONS_DISABLED')
            self._attack_session._notifications.validate(writer, wire, phase='PREPARED')
        elif opcode == ATTACK_FEEDBACK:
            player_hit = getattr(self, '_npc_player_hit', None)
            operation = None if player_hit is None else player_hit.operation_for(writer)
            if operation is not None and operation.wire is wire:
                row = player_hit.validate_locked(writer, operation.context)
                player_hit.validate_delivery(writer, row, wire, operation)
            else:
                need(self._attack_session is not None, 'ATTACK_FEEDBACK_DISABLED')
                self._attack_session.validate_feedback(writer, wire, state='PREPARED')
        elif opcode == ALIVE_RESPONSE:
            need(wire == ALIVE_FRAME, 'EXACT_ALIVE_RESPONSE_REQUIRED')
            game = self.registry.resolve(writer)
            self.bound_account(writer, game)
            service = self.service(writer)
            position, selected = service.snapshot(), game.selection
            need(selected is not None and selected.reference == position.name
                 and self.registry.selected.get(position.name) is selected
                 and not service.fatal and not self._settings_failed and id(writer) not in self._quit,
                 'ALIVE_REPLY_SELECTED_AUTHORITY_REQUIRED')
        else:
            need(session.wire.validate_frame(wire).kind in ('NUM', 'INFO'),
                 'WORLD_OR_ACK_REPLY_UNBOUND')


class _InventoryGeneration:
    """One actual selection's mutable inventory lifetime; retired instances stay closed."""
    def __init__(self, broker, *, previous=None, restart_state=None):
        self.broker, self.previous, self.restart_state = broker, previous, restart_state
        self.writer = self.row = self.lock = self.game = self.selected = self.mover = None
        self.reader = self.store = self.account = None
        self.phase = 'ACTIVE'
        self.service = self.item_use_session = None
        self.frame = self.selection_binding = self.delivery_authority = self.current_frame = None
        self.update_operation = self.prewrite_refusal = self.operation_frame = None
        self.restored = self.attempted = self.restore_only = self.write_attempted = False
        self.deadline_ns = self.admission_clock_ns = self.sample_monotonic_ns = None
        self.admission_expired = False
        self.mode = None  # Actual restore provenance, never an inferred saved row.
        self.collection_grant = None  # Actual same-life durable grant; never a send capability.
        self.transfer_session = None


def _inventory_property(name):
    # Only the fixed declarations below use this facade. No attribute magic,
    # registry, copied receipt or caller-selected storage key is accepted.
    def get(broker):
        return getattr(broker._inventory_generation, name)
    def set_(broker, value):
        if '_inventory_generation' not in broker.__dict__:
            broker._inventory_generation = _InventoryGeneration(broker)
        setattr(broker._inventory_generation, name, value)
    return property(get, set_)


class _ClosingQuitOwnerGuard:
    """The real accepted game row's no-effect duplicate Quit capability only."""
    __slots__ = ('broker', 'row', 'writer')

    def __init__(self, broker, row, writer):
        need(type(broker) is PersistentBroker and row['writer'] is writer
             and broker._source_quit_closing is not None,
             'QUIT_CLOSING_REAL_BROKER_ROW_REQUIRED')
        self.broker, self.row, self.writer = broker, row, writer

    async def __call__(self, writer, position):
        need(writer is self.writer and self.row['writer'] is writer,
             'QUIT_CLOSING_WRITER_CHANGED')
        return await self.broker._quit_duplicate_owner(writer, self.row, position)


class _TerminalQuitReceipt:
    """One decoded empty Quit on the same retained read, never an OwnerSample."""
    __slots__ = ('broker', 'writer', 'row', 'peer', 'peer_values', 'policy_row',
                 'operation_lock', 'transport', 'read_task', 'decoder', 'frame')

    def __init__(self, broker, writer, row, read_task, decoder, frame):
        need(type(broker) is PersistentBroker and row['writer'] is writer
             and row['_read_task'] is read_task and row['operation_lock'].locked()
             and type(decoder) is ClientPlaintextDecoder and type(frame) is Frame
             and frame.opcode == QUIT_REQUEST and frame.wire_length == 10
             and frame.payload == b'' and decoder.buffered_bytes == 0,
             'QUIT_TERMINAL_SAME_READER_FRAME_REQUIRED')
        self.broker, self.writer, self.row = broker, writer, row
        self.peer, self.peer_values = row['peer'], tuple(sorted(row['peer'].items()))
        self.policy_row, self.operation_lock = row['policy_row'], row['operation_lock']
        self.transport, self.read_task = writer.transport, read_task
        self.decoder, self.frame = decoder, frame


class PersistentBroker:
    SHOP_TRADE_DELIVERY_V1 = True
    SHOP_TRADE_V1 = True
    HACTION_LIST_V1 = True
    DIALOGUE_SEND_V1 = True
    """One retained owner, two sequential streams/endpoint, no session deadline.

    owner_guard(peer) must validate the current exact TCP tuple AND the retained
    native process identity/handle/Job, returning literal True. This is a trusted
    in-process capability, never a JSON/CLI supplied flag. owner_liveness_guard()
    validates the same retained process identity/handle/Job without a TCP query;
    it authorizes only terminal reader EOF with an empty decoder. on_accept(peer) is a
    synchronous registration callback, called immediately after KEY write.
    conversation_factory(cid, sink) supplies the preserved KEY/VERSION/COUNTS
    conversation and owns genuine VERSION resource lifetime. source_guard and
    optional cheap key_guard validate that retained context without per-frame
    file hashing. Sockets must already be exclusively reserved by the launcher.
    """
    _inventory_service = _inventory_property('service')
    _item_use_session = _inventory_property('item_use_session')
    _inventory_frame = _inventory_property('frame')
    _inventory_selection_binding = _inventory_property('selection_binding')
    _inventory_restored = _inventory_property('restored')
    _inventory_attempted = _inventory_property('attempted')
    _inventory_restore_only = _inventory_property('restore_only')
    _inventory_delivery_authority = _inventory_property('delivery_authority')
    _inventory_current_frame = _inventory_property('current_frame')
    _inventory_update_operation = _inventory_property('update_operation')
    _inventory_prewrite_refusal = _inventory_property('prewrite_refusal')
    _inventory_write_attempted = _inventory_property('write_attempted')
    _inventory_operation_frame = _inventory_property('operation_frame')
    _inventory_deadline_ns = _inventory_property('deadline_ns')
    _inventory_admission_clock_ns = _inventory_property('admission_clock_ns')
    _inventory_admission_expired = _inventory_property('admission_expired')
    inventory_sample_monotonic_ns = _inventory_property('sample_monotonic_ns')

    def __init__(self, *, sockets, retained_owner, owner_handle, owner_job,
                 owner_guard, owner_liveness_guard, source_guard, conversation_factory, expected_uuid,
                 store_path, on_accept=None, key_guard=None, on_release=None, edge_passability=None,
                 settings_path=None, owner_exit_proof=None, world_profile=BASELINE_WORLD, npc_spawns=(),
                 npc_motion_interval_ns=None, npc_edge_passability=None, npc_motion_policy=None,
                 attack_policy=None, attack_reader=None, attack_feedback=None, attack_hp_provider=None,
                 restart_policy=None, npc_death_policy=None, npc_remove_policy=None, npc_respawn_policy=None,
                 inventory_policy=None, inventory_frame=None, inventory_reader=None, inventory_store_policy=None,
                 inventory_aggregate_capability=None,
                 item_use_policy=None, inventory_update_policy=None,
                 item_equipment_policy=None, item_equipment_first_enable=False,
                 inventory_reselection_policy=None, inventory_delivery_policy=None,
                 inventory_missing_row_policy=None, hp_status_policy=None,
                 inventory_collection_policy=None, inventory_collection_grant=None,
                 inventory_owner_guard=None, npc_player_hit_policy=None, npc_player_hit_repeated_policy=None,
                 inventory_custody_policy=None, item_transfer_policy=None, player_life_policy=None):
        self._inventory_update_owner = None
        self._canonical_provider = None
        # One provider/Store owns one operation scope across all connection rows.
        # Other Tasks wait; recursive entry by its current Task is still refused.
        self._canonical_operation_gate = asyncio.Lock()
        self._canonical_operation_task = None
        self._hp_resource_owner = None
        if item_transfer_policy is not None or inventory_custody_policy is not None:
            from tools.local_original_session import item_transfer_session
            item_transfer_session.validate_mode(policy=item_transfer_policy,
                custody_policy=inventory_custody_policy, inventory_policy=inventory_policy,
                frame=inventory_frame, store_policy=inventory_store_policy,
                collection_policy=inventory_collection_policy, collection_grant=inventory_collection_grant,
                reselection_policy=inventory_reselection_policy, delivery_policy=inventory_delivery_policy,
                missing_row_policy=inventory_missing_row_policy, restart_policy=restart_policy)
            need(not npc_spawns and attack_policy is None and inventory_update_policy is None
                 and item_equipment_first_enable is False,
                 'ITEM_TRANSFER_NO_OTHER_MUTATION_POLICY_REQUIRED')
            item_transfer_session.require_ground_source()
            need(inventory_owner_guard is not None, 'ITEM_TRANSFER_EXACT_OWNER_GUARD_REQUIRED')
        self.item_transfer_policy = self._item_transfer_policy_bound = item_transfer_policy
        self.inventory_custody_policy = self._inventory_custody_policy_bound = inventory_custody_policy
        self._item_ground_registry = None
        need(npc_player_hit_policy is None or npc_player_hit_repeated_policy is None,
             'NPC_PLAYER_HIT_EXCLUSIVE_POLICY_REQUIRED')
        if npc_player_hit_repeated_policy is not None:
            from tools.local_original_session import npc_player_hit
            need(type(npc_player_hit_repeated_policy) is str
                 and npc_player_hit_repeated_policy == npc_player_hit.REPEATED_POLICY
                 and hp_status_policy is not None and attack_hp_provider is not None
                 and attack_policy == ATTACK_INTENT_POLICY
                 and (len(npc_spawns) == 1 or len(npc_spawns) == 2
                      and tuple(spawn.uid for spawn in npc_spawns) == (2,3))
                 and npc_motion_interval_ns is not None, 'NPC_PLAYER_HIT_REPEATED_DEPENDENCIES_REQUIRED')
            npc_player_hit.source_ready()
        if npc_player_hit_policy is not None:
            from tools.local_original_session import npc_player_hit
            need(type(npc_player_hit_policy) is str and npc_player_hit_policy == npc_player_hit.POLICY
                 and hp_status_policy is not None and attack_hp_provider is not None
                 and attack_policy == ATTACK_INTENT_POLICY and len(npc_spawns) == 1
                 and npc_motion_interval_ns is not None,
                 'NPC_PLAYER_HIT_EXPLICIT_DEPENDENCIES_REQUIRED')
            npc_player_hit.source_ready()
        if hp_status_policy is not None:
            from tools.local_original_session import hp_status
            need(type(hp_status_policy) is str and hp_status_policy == hp_status.POLICY,
                 'HP_STATUS_EXPLICIT_POLICY_REQUIRED')
            hp_status.source_ready()
        need(attack_hp_provider is None or attack_policy == ATTACK_INTENT_POLICY,
             'NPC_HP_REQUIRES_INTENT_POLICY')
        if npc_death_policy is not None or npc_remove_policy is not None:
            from tools.local_original_session import npc_death
            need(type(npc_death_policy) is str and npc_death_policy == npc_death.DEATH_POLICY
                 and (npc_remove_policy is None or type(npc_remove_policy) is str
                      and npc_remove_policy == npc_death.REMOVE_POLICY)
                 and attack_hp_provider is not None and attack_feedback is not None,
                 'NPC_DEATH_REQUIRES_EXPLICIT_HP_AND_FEEDBACK')
        if restart_policy is not None:
            from tools.local_original_session import restart
            need(type(restart_policy) is str and restart_policy == restart.POLICY,
                 'EXPLICIT_RESTART_POLICY_REQUIRED')
            restart.source_ready()
        self.restart_policy = restart_policy
        inventory_enabled = any(v is not None for v in (inventory_policy, inventory_frame, inventory_reader))
        if inventory_enabled:
            from tools.local_original_session import inventory
            need(type(inventory_policy) is str and inventory_policy == inventory.POLICY
                 and type(inventory_frame) is bytes and inventory_reader is not None,
                 'INVENTORY_EXPLICIT_POLICY_FRAME_READER_REQUIRED')
            inventory.validate_frame(inventory_frame)
        need(inventory_aggregate_capability is None or inventory_store_policy is not None,
             'CANONICAL_AGGREGATE_REQUIRES_ENABLED_INVENTORY_STORE')
        if inventory_store_policy is not None:
            from tools.local_original_session import inventory_store
            need(inventory_enabled and type(inventory_store_policy) is str
                 and inventory_store_policy in (inventory_store.POLICY, inventory_store.COLLECTION_STORE_POLICY),
                 'INVENTORY_STORE_REQUIRES_EXPLICIT_INVENTORY_POLICY')
        if item_use_policy is not None:
            from tools.local_original_session import item_use_session
            need(type(item_use_policy) is str and item_use_policy == item_use_session.POLICY,
                 'EXPLICIT_ITEM_USE_INTENT_POLICY_REQUIRED')
            need(inventory_enabled and inventory_store_policy is not None,
                 'ITEM_USE_REQUIRES_STORED_INVENTORY')
        if inventory_update_policy is not None:
            from tools.local_original_session import inventory_update
            need(type(inventory_update_policy) is str and inventory_update_policy == INVENTORY_UPDATE_POLICY,
                 'EXPLICIT_INVENTORY_UPDATE_POLICY_REQUIRED')
            need(inventory_enabled and inventory_store_policy is not None,
                 'INVENTORY_UPDATE_REQUIRES_STORED_INVENTORY')
            inventory_update.source_ready()
        self.inventory_update_policy = inventory_update_policy
        if item_equipment_policy is not None:
            from tools.local_original_session.item_equipment_effect import POLICY as EQUIPMENT_POLICY
            need(type(item_equipment_policy) is str and item_equipment_policy == EQUIPMENT_POLICY and
                 item_use_policy is not None and inventory_store_policy is not None and
                 type(item_equipment_first_enable) is bool, 'EQUIPMENT_EXPLICIT_POLICY_REQUIRED')
        else:
            need(item_equipment_first_enable is False, 'EQUIPMENT_FIRST_ENABLE_REQUIRES_POLICY')
        self.item_equipment_policy = item_equipment_policy
        self.item_equipment_first_enable = item_equipment_first_enable
        if inventory_reselection_policy is not None:
            need(type(inventory_reselection_policy) is str
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and type(inventory_delivery_policy) is str
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and restart_policy is not None and inventory_enabled
                 and inventory_store_policy is not None,
                 'INVENTORY_RESELECTION_EXPLICIT_STORED_RESTART_DELIVERY_REQUIRED')
        if inventory_missing_row_policy is not None:
            need(type(inventory_missing_row_policy) is str
                 and inventory_missing_row_policy == INVENTORY_MISSING_ROW_POLICY
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and inventory_store_policy is not None and inventory_enabled,
                 'INVENTORY_MISSING_ROW_EXPLICIT_POLICY_REQUIRED')
            need(dict(inventory.validate_frame(inventory_frame).raw_fields) == INVENTORY_STARTER_FIELDS,
                 'INVENTORY_MISSING_ROW_EXACT_ATHAME_STARTER_REQUIRED')
        if inventory_collection_policy is not None:
            need(type(inventory_collection_policy) is str and inventory_collection_policy == inventory.COLLECTION_POLICY
                 and inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and inventory_missing_row_policy is None,
                 'INVENTORY_COLLECTION_EXPLICIT_RESTORE_ONLY_REQUIRED')
            if item_transfer_policy is not None:
                need(inventory_collection_grant is None, 'ITEM_TRANSFER_READONLY_NO_GRANT_REQUIRED')
            else:
                need(type(inventory_collection_grant) is tuple and len(inventory_collection_grant) == 2
                     and type(inventory_collection_grant[0]) is str
                     and inventory_collection_grant[0] == inventory_store.SECOND_INSTANCE_POLICY
                     and type(inventory_collection_grant[1]) is frozenset
                     and len(inventory_collection_grant[1]) <= 4096
                     and all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in inventory_collection_grant[1]),
                     'INVENTORY_COLLECTION_EXPLICIT_GRANT_OPTIONS_REQUIRED')
        else:
            need(inventory_collection_grant is None and
                 (inventory_store_policy is None or inventory_store_policy == inventory_store.POLICY),
                 'INVENTORY_COLLECTION_POLICY_REQUIRED')
        if inventory_owner_guard is not None:
            from tools.local_original_session.launcher import NativeOwner
            need(inventory_collection_policy == inventory.COLLECTION_POLICY
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and inventory_missing_row_policy is None,
                 'INVENTORY_SYNC_OWNER_EXPLICIT_COLLECTION_REQUIRED')
            need(type(retained_owner) is NativeOwner
                 and getattr(inventory_owner_guard, '__self__', None) is retained_owner
                 and getattr(inventory_owner_guard, '__func__', None) is NativeOwner.guard_exact_sync
                 and not inspect.iscoroutinefunction(inventory_owner_guard),
                 'INVENTORY_SYNC_ORIGINAL_OWNER_GUARD_REQUIRED')
        self._inventory_owner_guard = inventory_owner_guard
        self._inventory_owner_guard_binding = (inventory_owner_guard.__self__, inventory_owner_guard.__func__) \
            if inventory_owner_guard is not None else None
        self._inventory_collection_policy = inventory_collection_policy
        self._inventory_collection_grant = inventory_collection_grant
        self.inventory_missing_row_policy = inventory_missing_row_policy
        self.inventory_reselection_policy = inventory_reselection_policy
        self.inventory_delivery_policy = inventory_delivery_policy
        self._inventory_reader = inventory_reader
        self._inventory_item_use_policy = item_use_policy
        self._inventory_generation = _InventoryGeneration(self)
        need((attack_policy is None and attack_reader is None)
             or (type(attack_policy) is str and attack_policy == ATTACK_INTENT_POLICY
                 and attack_reader is not None and bool(npc_spawns)),
             'ATTACK_EXPLICIT_POLICY_READER_AND_NPC_REQUIRED')
        need(attack_feedback is None or attack_policy is not None,
             'ATTACK_FEEDBACK_REQUIRES_INTENT_POLICY')
        need(type(sockets) is dict and set(sockets) == set(PORTS), 'BOTH_RESERVED_SOCKETS_REQUIRED')
        need(all(callable(x) for x in (owner_guard, owner_liveness_guard,
                                       source_guard, conversation_factory)),
             'RETAINED_CALLBACKS_REQUIRED')
        need(on_accept is None or callable(on_accept), 'ACCEPT_CALLBACK_REQUIRED')
        need(on_release is None or callable(on_release), 'RELEASE_CALLBACK_REQUIRED')
        need(key_guard is None or callable(key_guard), 'KEY_GUARD_REQUIRED')
        need(owner_exit_proof is None or callable(owner_exit_proof), 'RETAINED_EXIT_CALLBACK_REQUIRED')
        self.sockets = dict(sockets)
        self.owner_guard, self.source_guard = owner_guard, source_guard
        self.owner_liveness_guard = owner_liveness_guard
        self.owner_exit_proof = owner_exit_proof
        self.key_guard = key_guard or source_guard
        self.conversation_factory = conversation_factory
        self.on_accept, self.on_release = on_accept, on_release
        self.policy = _TransportPolicy(retained_owner, owner_handle, owner_job,
                                      self.sockets, now=time.monotonic_ns(),
                                      attack_intent=attack_policy is not None,
                                      attack_feedback=attack_feedback is not None or npc_player_hit_policy is not None or npc_player_hit_repeated_policy is not None,
                                      player_life=player_life_policy is not None,
                                       npc_death=npc_death_policy is not None,
                                      npc_remove=npc_remove_policy is not None,
                                      inventory_add=inventory_enabled,
                                      restart_enabled=restart_policy is not None,
                                      item_use_intent=item_use_policy is not None,
                                      item_transfer=item_transfer_policy is not None,
                                      item_equipment_effect=item_equipment_policy is not None,
                                      inventory_update=inventory_update_policy is not None)
        self.realm = LocalRealm(expected_uuid, Path(store_path), edge_passability=edge_passability,
                                settings_path=settings_path, world_profile=world_profile, npc_spawns=npc_spawns,
                                npc_motion_interval_ns=npc_motion_interval_ns,
                                npc_edge_passability=npc_edge_passability,
                                npc_motion_policy=npc_motion_policy)
        if restart_policy is not None:
            self.realm._restart_broker = self
        self.failure = asyncio.Event()
        self.failure_code = None
        self.owner_failure = None
        self.last_received_frame = None
        self.cleanup_complete = False
        self._servers = []
        self._tasks = set()
        self._claims = {p: [] for p in PORTS}
        self._closing = False
        self._started = False
        self._source_quit_closing = None
        self._loop = None
        self._close_task = None
        self._hp_status = None
        self._npc_player_hit = None
        if hp_status_policy is not None:
            self._hp_status = hp_status.Service(self, policy=hp_status_policy,
                repeated_policy=hp_status.REPEATED_POLICY if npc_player_hit_repeated_policy is not None else None)
            self.realm._hp_status = self._hp_status
        self._rejected = 0
        self._attack_session = None
        self._item_use_session = None
        self._inventory_service = None
        self._inventory_frame = inventory_frame
        self._inventory_config_frame = inventory_frame
        self._inventory_store = None
        self._inventory_selection_binding = None
        self._inventory_restored = False
        self._inventory_attempted = False
        self._inventory_restore_only = False
        self._inventory_delivery_authority = None
        self._inventory_current_frame = None
        self._inventory_update_operation = None
        self._inventory_prewrite_refusal = None
        self._inventory_write_attempted = False
        self._inventory_operation_frame = None
        self._inventory_deadline_ns = None
        self._inventory_admission_clock_ns = None
        self._inventory_admission_expired = False
        self.inventory_sample_monotonic_ns = None
        if inventory_enabled:
            if inventory_store_policy is not None:
                if inventory_aggregate_capability is None:
                    self._inventory_store = inventory_store.InventoryStore(self.realm.store.path,
                        policy=inventory_store_policy, custody_policy=inventory_custody_policy)
                else:
                    self._inventory_store = inventory_store.InventoryStore(self.realm.store.path,
                        policy=inventory_store_policy, custody_policy=inventory_custody_policy,
                        aggregate_capability=inventory_aggregate_capability)
            self._inventory_service = inventory.InventoryService(self, inventory_reader, policy=inventory_policy,
                                                               store=self._inventory_store, collection_policy=self._inventory_collection_policy)
            self._inventory_generation.reader = inventory_reader
            self._inventory_generation.store = self._inventory_store
            if inventory_reselection_policy is not None:
                self._inventory_service._inventory_generation = self._inventory_generation
            if self._inventory_store is not None:
                self.realm._inventory_broker = self
        if inventory_update_policy is not None:
            self.realm._inventory_update_broker = self
        if item_use_policy is not None:
            self._item_use_session = item_use_session.ItemUseSession(self, policy=item_use_policy)
            self.realm.bind_item_use_session(self._item_use_session)
        self._item_equipment_effect = None
        self.realm._item_equipment_effect = None
        if item_equipment_policy is not None:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            self._item_equipment_effect = ItemEquipmentEffect(self, policy=item_equipment_policy,
                                                            first_enable=item_equipment_first_enable)
            self.realm._item_equipment_effect = self._item_equipment_effect
        if item_transfer_policy is not None:
            from tools.local_original_session.item_ground import GroundRegistry
            self._item_ground_registry = GroundRegistry(self)
            self.realm._item_transfer_broker = self
        if attack_policy is not None:
            from tools.local_original_session.attack import AttackTargets
            from tools.local_original_session.attack_session import AttackSession
            self._attack_session = AttackSession(AttackTargets(self, attack_reader), policy=attack_policy,
                                                 feedback=attack_feedback, hp_provider=attack_hp_provider,
                                                 death_policy=npc_death_policy, remove_policy=npc_remove_policy)
            self.realm.bind_attack_session(self._attack_session)
        self._npc_respawn = None
        if npc_respawn_policy is not None:
            from tools.local_original_session import npc_respawn
            self._npc_respawn = npc_respawn.Service(self, attack_reader, policy=npc_respawn_policy)
            self.realm._npc_respawn = self._npc_respawn
        if npc_player_hit_policy is not None or npc_player_hit_repeated_policy is not None:
            self._npc_player_hit = npc_player_hit.Service(self,
                policy=npc_player_hit_policy if npc_player_hit_policy is not None else npc_player_hit_repeated_policy)
            self.realm._npc_player_hit = self._npc_player_hit
        self._player_life = None
        self._player_life_observer = None
        if player_life_policy is not None:
            from tools.local_original_session import player_life
            self._player_life = player_life.Service(self,policy=player_life_policy)
            self.realm._player_life_broker = self
        self._npc_player_lethal = None
        if player_life_policy is not None and player_life_policy.label == player_life.NPC_POLICY_LABEL:
            from tools.local_original_session import npc_player_lethal
            self._npc_player_lethal = npc_player_lethal.Service(self)

    def bind_canonical_runtime(self, provider):
        from tools.local_original_session.canonical_batch import BrokerProvider
        need(type(provider) is BrokerProvider and provider.broker is self
             and provider.source_store is self._inventory_store
             and not self._started and not self._closing and not self.realm.registry._sessions
             and self._canonical_provider is None,
             'CANONICAL_EXACT_UNSTARTED_BROKER_PROVIDER_REQUIRED')
        self._canonical_provider = provider
        self.realm._canonical_provider = provider

    def bind_resource_runtime(self, owner):
        from tools.local_original_session.hp_resource_owner import ResourceOwner
        need(type(owner) is ResourceOwner and owner.status is self._hp_status
             and owner.status.broker is self and owner.provider.broker is self
             and owner.provider.source_store is self._inventory_store
             and not self._started and not self._closing and not self.realm.registry._sessions
             and self._hp_resource_owner is None,
             'RESOURCE_EXACT_UNSTARTED_BROKER_RUNTIME_REQUIRED')
        if self._canonical_provider is None:
            self.bind_canonical_runtime(owner.provider)
        need(self._canonical_provider is owner.provider, 'RESOURCE_SAME_CANONICAL_PROVIDER_REQUIRED')
        self._hp_resource_owner = owner
        self.realm._hp_resource_owner = owner

    async def cast_skill_locked(self, binding, plan, *, source_adapter, legacy_bindings):
        """Server-only semantic caller; original target admission remains required.

        Default unresolved response producer refuses before any prepare/debit.
        This never acquires a second scope, guesses target/clock, or sends raw
        packets outside the existing _send/checkpoint/drain path.
        """
        from tools.local_original_session.skill_cost_delivery import CostDelivery, optional_buff
        owner = self._hp_resource_owner
        need(owner is not None and owner.provider is self._canonical_provider
             and plan.operation.binding is binding, 'RESOURCE_CURRENT_SERVER_CAST_PLAN_REQUIRED')
        owner.provider.current(binding)
        parent = CostDelivery(owner, plan)
        try:
            service = optional_buff.OptionalScopedService(parent=parent, root=owner.status_module.observe.ROOT,
                broker=self, store=owner.store, owned_provider=owner.provider,
                legacy_bindings=legacy_bindings, source_adapter=source_adapter)
            parent.preflight(service)
            receipt = owner.commit_cast_locked(plan, reply_parent=parent)
            await self._send(binding.writer, binding.generation.row, parent.frames, game=True,
                operation_lock=binding.operation_lock, skill_operation=parent)
            return receipt
        except BaseException as error:
            parent.failed(error)
            raise

    def bind_original_update_runtime(self, owner):
        from tools.local_original_session.canonical_batch import OriginalUpdateOwner, BatchStore, BrokerProvider
        need(type(owner) is OriginalUpdateOwner and type(owner.store) is BatchStore
             and type(owner.provider) is BrokerProvider and owner.broker is self
             and owner.provider is self._canonical_provider and owner.provider.broker is self
             and owner.store.provider is owner.provider
             and owner.store.source is self._inventory_store
             and owner.provider.source_store is self._inventory_store
             and owner.store._original_update_owner is owner
             and not owner.closed and not owner.store.closed and not owner.store.failed
             and not self._started and not self._closing and not self.realm.registry._sessions
             and self._inventory_update_owner is None,
             'INVENTORY_UPDATE_EXACT_UNSTARTED_CANONICAL_OWNER_REQUIRED')
        owner._source_check()  # Existing pinned actual-source validator, no caller boolean.
        self._inventory_update_owner = owner

    @asynccontextmanager
    async def _row_operation(self, writer, row):
        provider = self._canonical_provider
        if provider is None:
            async with row['operation_lock']:
                yield
        else:
            # This REPLACES the real outer acquisition, including preselection,
            # read-poll and EOF. It never adopts/reacquires a held legacy lock.
            task = asyncio.current_task()
            need(self._canonical_operation_task is not task,
                 'BATCH_OPERATION_SCOPE_ALREADY_ACTIVE')
            async with self._canonical_operation_gate:
                need(self._canonical_operation_task is None and self._canonical_provider is provider,
                     'RESOURCE_SAME_CANONICAL_PROVIDER_REQUIRED')
                self._canonical_operation_task = task
                try:
                    async with provider.connection_operation(writer, row):
                        yield
                finally:
                    self._canonical_operation_task = None

    async def start(self):
        need(not self._started and not self._closing, 'BROKER_ALREADY_STARTED_OR_CLOSED')
        self._loop = asyncio.get_running_loop()
        self.source_guard()
        # Validate both before handing either one to asyncio (no rebind window).
        for port, sock in self.sockets.items():
            need(isinstance(sock, socket.socket) and sock.family == socket.AF_INET
                 and sock.type & socket.SOCK_STREAM and sock.getsockname() == ('127.0.0.1', port)
                 and sock.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN),
                 'EXACT_RESERVED_LOOPBACK_LISTENER_REQUIRED')
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                need(sock.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE) == 1,
                     'EXCLUSIVE_RESERVED_LISTENER_REQUIRED')
            sock.setblocking(False)
        self._started = True
        try:
            for port, sock in self.sockets.items():
                server = await asyncio.start_server(
                    lambda r, w, p=port: self._accept(p, r, w), sock=sock,
                    limit=PersistentPolicy.MAX_BUFFER)
                self._servers.append(server)
        except BaseException:
            await self.close()
            raise
        return self

    def _fail(self, code):
        if self.failure_code is None:
            self.failure_code = code
        self.failure.set()
        life = getattr(self,'_player_life',None)
        if life is not None: life.close()
        player_hit = getattr(self, '_npc_player_hit', None)
        if player_hit is not None:
            player_hit.close()
        status = getattr(self, '_hp_status', None)
        if status is not None:
            status.close()
        item_use = getattr(self, '_item_use_session', None)
        if item_use is not None:
            item_use.close()
        attack_session = getattr(self, '_attack_session', None)
        if attack_session is not None:
            attack_session.fail()
        inventory_service = getattr(self, '_inventory_service', None)
        if inventory_service is not None and self._inventory_generation.phase != 'RETIRED':
            if getattr(self, 'inventory_reselection_policy', None) is not None:
                self._inventory_generation.phase = 'TERMINAL'
            self._inventory_delivery_authority = None
            self._inventory_prewrite_refusal = None
            inventory_service.close()
        self.policy.stop('broker_failed')
        # Stop accepting immediately. Caller awaits close() on this same loop.
        for server in self._servers:
            server.close()

    @staticmethod
    def _failure_code(failure):
        # Only trusted fixed diagnostic codes can cross the metadata boundary.
        code = failure.args[0] if len(failure.args) == 1 else None
        if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            return code
        return type(failure).__name__

    def bind_source_quit_closing(self, source_quit):
        """Bind the existing SourceQuit object before the primary is resumed.

        This is an owner receipt for one later no-effect duplicate Quit, never
        an owner sample for an ordinary frame or a transport policy change.
        """
        from tools.local_original_session.manual_source_quit import SourceQuitRequests
        need(type(source_quit) is SourceQuitRequests and source_quit.broker is self
             and source_quit.owner is self.policy.owner
             and source_quit.requests.consumer is source_quit.consumer
             and source_quit.consumer.reader.owner is self.policy.owner
             and source_quit._started is False and source_quit._closed is False
             and self._source_quit_closing is None and not self._closing
             and not self.failure.is_set(), 'QUIT_CLOSING_SOURCE_BINDING_REQUIRED')
        self._source_quit_closing = source_quit

    def _accept(self, port, reader, writer):
        rows = self._claims[port]
        if (self._closing or self.failure.is_set() or len(rows) >= 2
                or (rows and not rows[-1]['promotable'])):
            self._rejected = min(MAX_COUNTER, self._rejected + 1)
            writer.transport.abort()  # No pending/rejected-writer task queue.
            return
        accepted_ns = time.monotonic_ns()
        client, server = writer.get_extra_info('peername'), writer.get_extra_info('sockname')
        row = dict(writer=writer, peer=None, policy_row=None, eof=False,
                   positive_close=False, registry_removed=False, decoder_empty=False,
                   joined=False, promotable=False, boot_complete=False, failed=False,
                   operation_lock=asyncio.Lock(), _quit_frame_owner=None)
        rows.append(row)
        try:
            need(client and server and client[0] == server[0] == '127.0.0.1'
                 and server[1] == port, 'EXACT_ACCEPTED_LOOPBACK_REQUIRED')
            cid = (1 if port == 12000 else 2) + (2 if len(rows) == 2 else 0)
            peer = dict(schema='lc-local-accepted-peer-v1', connection_id=cid,
                        endpoint_port=port, client_host=client[0], client_port=client[1],
                        server_host=server[0], server_port=server[1],
                        accepted_monotonic_ns=accepted_ns)
            row['peer'] = peer
            self.key_guard()
            writer.transport.set_write_buffer_limits(high=self.policy.WRITE_HIGH,
                                                     low=self.policy.WRITE_LOW)
            writer.write(KEY12)  # Intentionally before any owner-poll await.
            if self.on_accept is not None:
                need(not inspect.isawaitable(self.on_accept(dict(peer))), 'SYNC_ACCEPT_CALLBACK_REQUIRED')
            task = asyncio.create_task(self._serve(reader, writer, row))
            row['task'] = task
            self._tasks.add(task)
            task.add_done_callback(lambda completed: self._joined(completed, row))
        except BaseException:
            row['failed'] = True
            writer.transport.abort()
            self._fail('ACCEPT_OR_FAST_KEY_FAILED')

    async def _sample(self, row, *, synchronous_exact=False):
        need(type(synchronous_exact) is bool, 'OWNER_SAMPLE_MODE_REQUIRED')
        if synchronous_exact:
            # The actual launcher binds NativeOwner.guard, an async wrapper whose
            # whole body calls this same synchronous guard. After an expensive
            # source validation, obtain a NEW exact tuple/handle/Job result with
            # no event-loop yield between that result and policy consumption.
            from tools.local_original_session.launcher import NativeOwner
            owner, guard = self.policy.owner, self.owner_guard
            direct = getattr(owner, 'guard_exact_sync', None)
            need(type(owner) is NativeOwner and getattr(guard, '__self__', None) is owner
                 and getattr(guard, '__func__', None) is NativeOwner.guard
                 and getattr(direct, '__self__', None) is owner
                 and getattr(direct, '__func__', None) is NativeOwner.guard_exact_sync
                 and self.policy.handle is owner.owner_handle
                 and self.policy.job is owner.owner_job
                 and row['operation_lock'].locked(),
                 'OWNER_EXACT_SYNC_SOURCE_REQUIRED')
            result = direct(dict(row['peer']))
        else:
            result = self.owner_guard(dict(row['peer']))
        if inspect.isawaitable(result):
            result = await asyncio.wait_for(result, 1.5)
        if result is not True:
            self._owner_failure(row, 'CALLBACK_FALSE' if result is False else 'CALLBACK_UNKNOWN')
        need(result is True, 'CURRENT_OWNER_REQUIRED')
        self.source_guard()
        p = row['peer']
        peer = Peer(p['server_port'], p['client_port'], p['accepted_monotonic_ns'])
        return OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                           peer, time.monotonic_ns(), True, True)

    async def _world_post_drain_checkpoint(self, writer, row, sample):
        """Requery an exact world owner sample that ages out at final consumption."""
        policy, policy_row = self.policy, row['policy_row']
        def exact_aged(now):
            return (self.policy is policy and policy_row is row['policy_row']
                and type(sample) is OwnerSample and policy_row is not None
                and sample.owner is policy.owner and sample.handle is policy.handle
                and sample.job is policy.job and sample.peer == policy_row.peer
                and sample.exact_identity_and_tuple is True and sample.alive is True
                and type(sample.observed_ns) is int
                and 0 < sample.observed_ns <= now
                and now - sample.observed_ns >= policy.FRESH_NS)
        if exact_aged(time.monotonic_ns()):
            sample = await self._sample(row, synchronous_exact=True)
        at = time.monotonic_ns()
        try:
            policy.checkpoint(writer, sample, at)
        except ValueError as error:
            if (error.args != ('CURRENT_OWNER_REQUIRED',) or not exact_aged(at)
                    or at - sample.observed_ns <= policy.FRESH_NS
                    or row['writer'] is not writer or not row['operation_lock'].locked()
                    or policy_row.drain_started_ns is None):
                # Preserve the original bounded owner-failure report and error.
                self._policy_sample(row, policy.checkpoint, writer, sample, at)
                raise
            sample = await self._sample(row, synchronous_exact=True)
            need(self.policy is policy and row['policy_row'] is policy_row
                 and row['writer'] is writer and row['operation_lock'].locked()
                 and policy_row.drain_started_ns is not None,
                 'WORLD_SAME_POST_DRAIN_RESERVATION_REQUIRED')
            self._policy_sample(row, policy.checkpoint, writer, sample, time.monotonic_ns())
        return sample

    async def _checkpoint(self, writer, row):
        sample = await self._sample(row)
        self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
        return sample

    def _inventory_owner_checkpoint_sync(self, writer, row, service, authority, wire, mode, operation_lock, *, item_transfer_operation=None):
        """A new exact owner query after the claimed leaf; never restamp old evidence."""
        guard = self._inventory_owner_guard
        policy, peer, policy_row = self.policy, row['peer'], row['policy_row']
        source_guard = self.source_guard
        owner, handle, job = policy.owner, policy.handle, policy.job
        binding = self._inventory_owner_guard_binding
        peer_values = tuple(sorted(peer.items()))
        transfer = self._inventory_generation.transfer_session if item_transfer_operation is not None else None
        transfer_binding = None if transfer is None else (transfer, transfer.membership,
            transfer.membership.snapshot, transfer.membership.frame, self._inventory_generation,
            transfer._send_index)
        def current(*, authority_check=True):
            need(self.policy is policy and policy.owner is owner
                 and policy.handle is handle and policy.job is job
                 and self.source_guard is source_guard and self._inventory_owner_guard is guard
                 and self._inventory_owner_guard_binding is binding
                 and binding is not None and binding[0] is owner
                 and getattr(guard, '__self__', None) is owner
                 and getattr(guard, '__func__', None) is binding[1]
                 and getattr(type(owner), 'guard_exact_sync', None) is binding[1]
                 and owner.owner_handle is handle and owner.owner_job is job
                 and not owner.closed and owner.child is service.reader.member,
                 'INVENTORY_SYNC_OWNER_BINDING_CHANGED')
            need(row['writer'] is writer and row['peer'] is peer
                 and tuple(sorted(peer.items())) == peer_values
                 and row['policy_row'] is policy_row and policy_row.writer is writer
                 and policy._connection(writer) is policy_row
                 and row['operation_lock'] is operation_lock and operation_lock.locked()
                 and not row['failed'] and not row['joined']
                 and not self._closing and not self.failure.is_set()
                 and policy.state == 'OPEN' and not policy_row.eof and not policy_row.failed
                 and policy_row.drain_started_ns is None and policy_row.pending_opcode is None
                 and policy_row.pending_size == 0,
                 'INVENTORY_SYNC_CURRENT_UNRESERVED_LOCK_REQUIRED')
            need(service is self._inventory_service and service._claimed is True
                 and service._inflight is False and not service._closed
                 and mode is True and self._inventory_collection_policy is not None,
                 'INVENTORY_SYNC_CLAIMED_RESTORE_REQUIRED')
            if item_transfer_operation is None:
                self._inventory_operation_mode_current(mode, writer, row, wire)
            else:
                from tools.local_original_session.item_transfer_session import ItemTransferSession, BoundTransferOperation
                need(type(transfer) is ItemTransferSession and type(item_transfer_operation) is BoundTransferOperation and
                     self._inventory_generation.transfer_session is transfer and transfer.pending is item_transfer_operation and
                     transfer.phase == 'COMMITTING' and not transfer.closed and
                     transfer_binding[0] is transfer and transfer_binding[1] is transfer.membership and
                     transfer_binding[2] is transfer.membership.snapshot is transfer._committed and
                     transfer_binding[3] is transfer.membership.frame is self._inventory_current_frame and
                     transfer_binding[4] is self._inventory_generation is transfer.generation and
                     transfer_binding[5] == transfer._send_index and transfer._wire_phase is None and
                     wire is item_transfer_operation.wires[transfer._send_index] and
                     item_transfer_operation.context.writer is writer and item_transfer_operation.context.row is row,
                     'ITEM_TRANSFER_SYNC_ORIGINAL_OPERATION_CHANGED')
            if authority_check:
                service._same(authority, service._current(writer, row))
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        current()
        result = guard(dict(peer))
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            result = None  # Never await or retry this synchronous authority boundary.
        if result is not True:
            self._owner_failure(row, 'CALLBACK_FALSE' if result is False else 'CALLBACK_UNKNOWN')
        need(result is True, 'CURRENT_OWNER_REQUIRED')
        source_guard()
        current()
        sample = OwnerSample(owner, handle, job,
            Peer(peer['server_port'], peer['client_port'], peer['accepted_monotonic_ns']),
            time.monotonic_ns(), True, True)
        self._policy_sample(row, policy.checkpoint, writer, sample, time.monotonic_ns())
        # The policy callback must not replace authority or cancel before reservation.
        current(authority_check=False)
        return sample

    def _owner_failure(self, row, scope):
        if self.owner_failure is not None:
            return
        policy_row, read_task = row.get('policy_row'), row.get('_read_task')
        self.owner_failure = dict(scope=scope, connection_id=row['peer'].get('connection_id'),
            rx_boot=policy_row.rx_boot if policy_row is not None else None,
            tx_boot=policy_row.tx_boot if policy_row is not None else None,
            await_phase=row.get('await_phase', 'UNKNOWN'),
            read_task_done=read_task.done() if read_task is not None else None)

    def _policy_sample(self, row, operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except ValueError as error:
            if error.args == ('CURRENT_OWNER_REQUIRED',):
                try:
                    if self.owner_failure is None:
                        self._owner_failure(row, 'POLICY_FRESHNESS')
                        diagnostic = dict(operation=None, observed_ns=None, now_ns=None,
                            fresh_ns=None, age_ns=None, peer_equal=None,
                            observed_ns_is_int=None, accepted_le_observed=None,
                            observed_le_now=None, age_within_freshness=None,
                            exact_identity_and_tuple_is_true=None, alive_is_true=None)
                        # Only the six existing, exact bound policy calls. Never
                        # invoke a callback, clock or owner query for diagnostics.
                        calls = (
                            ('checkpoint', PersistentPolicy.checkpoint, 3, ()),
                            ('begin_write', _TransportPolicy.begin_write, 6, ()),
                            ('drained', PersistentPolicy.drained, 4, ()),
                            ('admit', PersistentPolicy.admit, 4, ('key_already_drained',)),
                            ('received_chunk', PersistentPolicy.received_chunk, 5, ('decoded_frames',)),
                            ('received_frame', _TransportPolicy.received_frame, 5, ()),
                        )
                        for name, function, count, keys in calls:
                            if (not inspect.ismethod(operation) or operation.__self__ is not self.policy
                                    or operation.__func__ is not function or len(args) != count
                                    or tuple(kwargs) != keys or args[0] is not row['writer']):
                                continue
                            if (name == 'admit' and type(kwargs['key_already_drained']) is not bool
                                    or name == 'received_chunk' and type(kwargs['decoded_frames']) is not int):
                                break
                            sample = args[2] if name == 'admit' else args[1]
                            peer = args[1] if name == 'admit' else row['policy_row'].peer
                            now, fresh = args[-1], self.policy.FRESH_NS
                            if (type(sample) is not OwnerSample or type(sample.peer) is not Peer
                                    or type(peer) is not Peer or type(now) is not int
                                    or not 0 <= now < (1 << 63) or type(fresh) is not int
                                    or not 0 <= fresh < (1 << 63)):
                                break
                            observed = sample.observed_ns
                            integer = type(observed) is int
                            bounded = integer and 0 <= observed < (1 << 63)
                            age = now - observed if bounded else None
                            diagnostic.update(operation=name,
                                observed_ns=observed if bounded else None, now_ns=now,
                                fresh_ns=fresh, age_ns=age, peer_equal=sample.peer == peer,
                                observed_ns_is_int=integer,
                                accepted_le_observed=(peer.accepted_ns <= observed
                                    if integer and type(peer.accepted_ns) is int else None),
                                observed_le_now=observed <= now if integer else None,
                                age_within_freshness=age <= fresh if age is not None else None,
                                exact_identity_and_tuple_is_true=sample.exact_identity_and_tuple is True,
                                alive_is_true=sample.alive is True)
                            break
                        self.owner_failure['policy_sample'] = diagnostic
                except Exception:
                    pass  # Optional metadata must preserve the original refusal.
            raise

    async def _account_owner(self, writer, row):
        def exact():
            policy_row = row['policy_row']
            if (row['writer'] is not writer or policy_row is None or policy_row.writer is not writer
                    or policy_row.stage != 1 or row['joined'] or row['failed']
                    or self._closing or self.failure.is_set()):
                return False
            game = self.realm.registry.resolve(writer)
            self.realm.bound_account(writer, game)
            return True
        if not exact():
            return False
        await self._checkpoint(writer, row)
        return exact()

    async def _quit_exit(self, writer, row):
        state = self.realm.quit_state(writer)
        need(row['writer'] is writer and row['policy_row'] is not None
             and row['policy_row'].writer is writer and not row['failed'] and not row['joined']
             and not self._closing and not self.failure.is_set()
             and state['response_drain_returned'] is True and state['response_queue_empty'] is True
             and not self.realm._settings_failed and callable(self.owner_exit_proof),
             'VERIFIED_QUIT_DRAIN_EXIT_REQUIRED')
        game = self.realm.registry.resolve(writer)
        self.realm.bound_account(writer, game)
        service = self.realm.service(writer)
        position, selected = service.snapshot(), game.selection
        need(selected is not None and not service.fatal and position.uid == state['uid']
             and selected.reference == position.name
             and self.realm.registry.selected.get(position.name) is selected,
             'QUIT_SAME_SELECTED_AUTHORITY_REQUIRED')
        proof = self.owner_exit_proof()
        if inspect.isawaitable(proof):
            proof = await asyncio.wait_for(proof, 1.5)
        self.source_guard()
        need(row['writer'] is writer and row['policy_row'] is not None
             and row['policy_row'].writer is writer
             and not row['failed'] and not row['joined'] and not self._closing
             and not self.failure.is_set() and not self.realm._settings_failed
             and self.realm.registry.resolve(writer) is game
             and self.realm.service(writer) is service and not service.fatal
             and service.snapshot() is position and game.selection is selected
             and self.realm.registry.selected.get(position.name) is selected,
             'QUIT_SAME_SELECTED_AUTHORITY_REQUIRED')
        # Do not serialize this dict: owner/handle/Job bindings are private.
        self.policy._verified_exit(proof, time.monotonic_ns())
        return proof

    async def _complete_eof(self, writer, row, *, decoder_empty, _binding_check=None):
        alive = self.owner_liveness_guard()
        if inspect.isawaitable(alive):
            alive = await asyncio.wait_for(alive, 1.5)
        self.source_guard()
        if _binding_check is not None:
            need(_binding_check() is True, 'BOOTSTRAP_EOF_BINDING_CHANGED')
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        if alive is True or id(writer) not in self.realm._quit:
            # Ordinary EOF keeps the prior live-owner contract unchanged.
            self.policy.eof_retained(writer, retained_alive=alive, decoder_empty=decoder_empty,
                                     now=time.monotonic_ns())
        else:
            need(alive is False, 'CURRENT_RETAINED_OWNER_UNKNOWN')
            proof = await self._quit_exit(writer, row)
            need(self.realm.quit_state(writer)['response_drained'] is True,
                 'EXACT_DRAINED_QUIT_EOF_REQUIRED')
            self.policy.eof_after_quit_exit(writer, proof=proof, decoder_empty=decoder_empty,
                                           now=time.monotonic_ns())
            row['quit_terminal_exit'] = True
        row['eof'] = True
        row['boot_complete'] = row['policy_row'].rx_boot == 2 and row['policy_row'].tx_boot == 3

    async def _drained_quit_read_eof(self, writer, row, read_task, *, decoder,
                                     decoder_empty, quit_binding, binding_check, original_error):
        """Same retained read: actual EOF or one parsed no-effect duplicate Quit."""
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        try:
            raw = await asyncio.wait_for(asyncio.shield(read_task), self.policy.CLOSE_NS / 1e9)
        except asyncio.TimeoutError:
            raise original_error  # Same strict owner failure; no inferred EOF.
        need(type(raw) is bytes, 'QUIT_TERMINAL_READ_BYTES_REQUIRED')
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        current = binding_check()
        need(current is not None and quit_binding is not None
             and len(current) == len(quit_binding)
             and all(a is b for a, b in zip(quit_binding, current)),
             'QUIT_EOF_BINDING_CHANGED')
        if raw:
            need(len(raw) == 10 and type(decoder) is ClientPlaintextDecoder
                 and decoder.cipher_pointer == 'present_disabled'
                 and decoder_empty is True and decoder.buffered_bytes == 0,
                 'QUIT_TERMINAL_EXACT_FRAME_REQUIRED')
            frames = decoder.feed(raw)  # The same original C2S parser, no invented frame.
            need(len(frames) == 1 and type(frames[0]) is Frame
                 and frames[0].opcode == QUIT_REQUEST and frames[0].wire_length == 10
                 and frames[0].payload == b'' and decoder.buffered_bytes == 0,
                 'QUIT_TERMINAL_EXACT_FRAME_REQUIRED')
            frame = frames[0]
            receipt = _TerminalQuitReceipt(self, writer, row, read_task, decoder, frame)
            row['_quit_frame_owner'] = receipt
            row['await_phase'] = 'TERMINAL_QUIT_DISPATCH'
            try:
                need(self._quit_closing_witness(writer, row, quit_binding[4]),
                     'QUIT_TERMINAL_SOURCE_WRITER_REQUIRED')
                from tools.local_original_session.launcher import NativeOwner
                owner = self.policy.owner
                callback = getattr(owner, 'quit_terminal_retained_sync', None)
                target = getattr(NativeOwner, 'quit_terminal_retained_sync', None)
                need(type(owner) is NativeOwner
                     and target is not None
                     and getattr(callback, '__self__', None) is owner
                     and getattr(callback, '__func__', None) is target
                     and callback(row['peer']) is True,
                     'QUIT_TERMINAL_RETAINED_PRIMARY_REQUIRED')
                self.source_guard()
                current = binding_check()
                need(current is not None and len(current) == len(quit_binding)
                     and all(a is b for a, b in zip(quit_binding, current))
                     and self._quit_closing_witness(writer, row, quit_binding[4]),
                     'QUIT_TERMINAL_BINDING_CHANGED')
                self.policy.received_drained_quit_terminal(writer, receipt,
                    raw_size=len(raw), now=time.monotonic_ns())
                replies = await quit_binding[2].received(frame)
                need(type(replies) is tuple and replies == (),
                     'QUIT_TERMINAL_NOEFFECT_REPLY_REQUIRED')
                current = binding_check()
                need(current is not None and len(current) == len(quit_binding)
                     and all(a is b for a, b in zip(quit_binding, current))
                     and self.realm.quit_state(writer)['duplicate_requests'] == 1,
                     'QUIT_TERMINAL_NOEFFECT_CHANGED')
            finally:
                row['_quit_frame_owner'] = None
                row['await_phase'] = 'READ_POLL_CHECKPOINT'
            return 'QUIT_DUPLICATE_CONTINUE'  # Continue ordinary read; EOF is still unproved.
        await self._complete_eof(writer, row, decoder_empty=decoder_empty)
        current = binding_check(eof=True)
        need(current is not None and len(current) == len(quit_binding)
             and all(a is b for a, b in zip(quit_binding, current)),
             'QUIT_EOF_BINDING_CHANGED')
        return True

    async def _poll_checkpoint(self, writer, row, read_task, *, decoder,
                               decoder_empty, operation_lock=None):
        policy, policy_row = self.policy, row['policy_row']
        pending_bootstrap = (not read_task.done() and policy_row.stage == 0
                             and operation_lock is not None)
        peer, peer_values = row['peer'], tuple(sorted(row['peer'].items()))

        def first_bootstrap_eof():
            # Only an actual read that completed while the poll awaited its
            # owner can take the already-existing terminal EOF path.
            if (not pending_bootstrap or not read_task.done() or read_task.cancelled()
                    or read_task.exception() is not None):
                return False
            raw = read_task.result()
            claims = self._claims.get(peer.get('endpoint_port'), ())
            return (type(raw) is bytes and raw == b'' and decoder_empty is True
                    and len(claims) == 1 and claims[0] is row and row['writer'] is writer
                    and row['_read_task'] is read_task and row['policy_row'] is policy_row
                    and row['operation_lock'] is operation_lock and operation_lock.locked()
                    and row['peer'] is peer and tuple(sorted(peer.items())) == peer_values
                    and self.policy is policy and policy._connection(writer) is policy_row
                    and policy_row.stage == 0 and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
                    and policy_row.buffered == 0 and policy_row.drain_started_ns is None
                    and not row['failed'] and not row['joined'] and not self._closing
                    and not self.failure.is_set())

        bootstrap_peer, bootstrap_claims = policy_row.peer, self._claims.get(14030)
        bootstrap_refs = (policy.owner, policy.handle, policy.job, self.realm, self.failure,
                          self.source_guard, self.owner_liveness_guard, self.owner_guard)
        bootstrap_phase = row.get('await_phase')

        def late_bootstrap_binding(*, eof=False):
            claims = self._claims.get(14030)
            return (pending_bootstrap and claims is bootstrap_claims
                    and claims is not None and len(claims) == 1 and claims[0] is row
                    and row['writer'] is writer and row.get('_read_task') is read_task
                    and row['policy_row'] is policy_row and row['operation_lock'] is operation_lock
                    and operation_lock.locked() and row['peer'] is peer
                    and tuple(sorted(peer.items())) == peer_values and peer.get('endpoint_port') == 14030
                    and row.get('await_phase') == bootstrap_phase
                    and self.policy is policy and policy._connection(writer) is policy_row
                    and policy_row.writer is writer and policy_row.peer is bootstrap_peer
                    and (bootstrap_peer.port, bootstrap_peer.client_port, bootstrap_peer.accepted_ns)
                        == (peer.get('server_port'), peer.get('client_port'), peer.get('accepted_monotonic_ns'))
                    and all(a is b for a, b in zip(bootstrap_refs,
                        (policy.owner, policy.handle, policy.job, self.realm, self.failure,
                         self.source_guard, self.owner_liveness_guard, self.owner_guard)))
                    and policy.state == 'OPEN' and policy_row.stage == 0
                    and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
                    and decoder_empty is True and policy_row.buffered == 0
                    and policy_row.partial_started_ns is None and policy_row.drain_started_ns is None
                    and policy_row.pending_opcode is None and policy_row.pending_size == 0
                    and policy_row.eof is eof and row['eof'] is eof
                    and not any((policy_row.failed, policy_row.positive_close,
                                 row['failed'], row['joined'], self._closing, self.failure.is_set()))
                    and id(writer) not in self.realm.registry._sessions
                    and id(writer) not in self.realm._movement and id(writer) not in self.realm._quit
                    and row.get('_restart') is None)

        late_bootstrap_initial = late_bootstrap_binding()

        def late_bootstrap_eof():
            return (late_bootstrap_initial and late_bootstrap_binding()
                    and read_task.done() and not read_task.cancelled()
                    and read_task.exception() is None and type(read_task.result()) is bytes
                    and read_task.result() == b'')

        pending_quit = (not read_task.done() and policy_row.stage == 1
                        and operation_lock is not None)
        quit_policy_peer = policy_row.peer

        def drained_quit_binding(*, eof=False):
            if not pending_quit:
                return None
            try:
                claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
                realm = self.realm
                state = realm._quit.get(id(writer))
                if (len(claims) != 1 or claims[0] is not row or row['writer'] is not writer
                        or row['_read_task'] is not read_task or row['policy_row'] is not policy_row
                        or row['operation_lock'] is not operation_lock or not operation_lock.locked()
                        or row['peer'] is not peer or tuple(sorted(peer.items())) != peer_values
                        or self.policy is not policy or policy._connection(writer) is not policy_row
                        or policy_row.writer is not writer or policy_row.stage != 1
                        or policy_row.peer is not quit_policy_peer
                        or (quit_policy_peer.port, quit_policy_peer.client_port, quit_policy_peer.accepted_ns)
                           != (peer.get('server_port'), peer.get('client_port'), peer.get('accepted_monotonic_ns'))
                        or policy_row.rx_boot != 2 or policy_row.tx_boot != 3
                        or decoder_empty is not True or policy_row.buffered != 0
                        or policy_row.drain_started_ns is not None or policy_row.pending_size != 0
                        or policy_row.pending_opcode is not None or policy_row.eof is not eof
                        or row['eof'] is not eof or row['failed'] or row['joined']
                        or policy_row.task_joined or policy_row.registry_removed
                        or self._closing or self.failure.is_set() or policy.state != 'OPEN'
                        or type(realm) is not LocalRealm or realm._settings_failed
                        or state is None or state['writer'] is not writer
                        or not all(state[key] is True for key in ('request_verified',
                            'response_drain_returned', 'response_queue_empty', 'response_drained'))
                        or policy._quit_drained.get(id(writer)) is not writer
                        or type(state['source_connection_id']) is not int
                        or state['source_connection_id'] != peer.get('connection_id')):
                    return None
                registry = realm.registry
                game = registry.resolve(writer)
                realm.bound_account(writer, game)
                service = realm.service(writer)
                position, selected = service.snapshot(), game.selection
                if (selected is None or service.fatal or state['selected'] is not selected
                        or state['position'] is not position or position.uid != state['uid']
                        or selected.reference != position.name
                        or registry.selected.get(position.name) is not selected
                        or realm.store.select(selected.reference)[0] != position.uid
                        or realm.positions.restore(position) != position):
                    return None
                return (realm, registry, game, service, position, selected, state,
                        realm.store, realm.positions, policy.owner, policy.handle, policy.job,
                        self.owner_liveness_guard, self.source_guard)
            except (ValueError, KeyError, AttributeError):
                return None  # This handoff is off; the original exit-only refusal still applies.

        quit_binding = drained_quit_binding()

        def drained_quit_eof():
            if (quit_binding is None or not read_task.done() or read_task.cancelled()
                    or read_task.exception() is not None):
                return False
            raw = read_task.result()
            current = drained_quit_binding()
            return (type(raw) is bytes and raw == b'' and current is not None
                    and all(a is b for a, b in zip(quit_binding, current)))

        restart_state = row.get('_restart')
        restart_frame = None if restart_state is None else restart_state['frame']
        pending_restart = (not read_task.done() and operation_lock is not None
                           and restart_state is not None and restart_state['phase'] == 'DRAINED')

        def drained_restart_binding(*, eof=False):
            if not pending_restart:
                return None
            try:
                from tools.local_original_session import restart
                need(restart_state['frame'] is restart_frame
                     and restart.validate_ack(restart_frame, policy=self.restart_policy) is True
                     and row.get('_restart') is restart_state
                     and restart_state['lock'] is operation_lock
                     and row['operation_lock'] is operation_lock and operation_lock.locked()
                     and row.get('_read_task') is read_task and row['policy_row'] is policy_row
                     and self.policy is policy and row['peer'] is peer
                     and tuple(sorted(peer.items())) == peer_values
                     and policy_row.peer is quit_policy_peer
                     and decoder_empty is True and policy_row.buffered == 0
                     and policy_row.drain_started_ns is None and policy_row.pending_opcode is None
                     and policy_row.pending_size == 0 and restart_state['write_attempted'] is True
                     and restart_state['drain_returned'] is True
                     and restart_state['response_drained'] is True,
                     'RESTART_DRAINED_ACCOUNT_EOF_REQUIRED')
                current = self._restart_current(writer, row, state=restart_state, cleared=True, eof=eof)
                self._restart_same(restart_state['binding'], current)
                return current
            except (ValueError, KeyError, AttributeError):
                return None  # No new send/dispatch or inferred native-exit authority.

        restart_binding = drained_restart_binding()

        def drained_restart_eof():
            if (restart_binding is None or not read_task.done() or read_task.cancelled()
                    or read_task.exception() is not None):
                return False
            raw = read_task.result()
            current = drained_restart_binding()
            return (type(raw) is bytes and raw == b'' and current is not None
                    and len(current[0]) == len(restart_binding[0])
                    and all(a is b for a, b in zip(current[0], restart_binding[0]))
                    and current[1] == restart_binding[1])

        try:
            await self._checkpoint(writer, row)
            return False
        except ValueError as error:
            if error.args != ('CURRENT_OWNER_REQUIRED',):
                raise
            if first_bootstrap_eof():
                await self._complete_eof(writer, row, decoder_empty=decoder_empty)
                need(first_bootstrap_eof(), 'BOOTSTRAP_EOF_BINDING_CHANGED')
                return True  # Ends this old stream; never dispatches or writes.
            if late_bootstrap_initial and not read_task.done() and late_bootstrap_binding():
                # The first bootstrap stream may finish its actual EOF one event-loop
                # turn after the failed tuple poll. Wait only for that retained read.
                alive = self.owner_liveness_guard()
                if inspect.isawaitable(alive):
                    alive = await asyncio.wait_for(alive, 1.5)
                self.source_guard()
                need(alive is True, 'CURRENT_RETAINED_OWNER_REQUIRED')
                need(late_bootstrap_binding(), 'BOOTSTRAP_EOF_BINDING_CHANGED')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                try:
                    raw = await asyncio.wait_for(asyncio.shield(read_task), self.policy.CLOSE_NS / 1e9)
                except asyncio.TimeoutError:
                    raise error  # The same strict owner failure remains terminal; no inferred EOF.
                need(type(raw) is bytes and raw == b'' and late_bootstrap_eof(),
                     'BOOTSTRAP_TERMINAL_EOF_REQUIRED')
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                await self._complete_eof(writer, row, decoder_empty=decoder_empty,
                                         _binding_check=late_bootstrap_eof)
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                need(late_bootstrap_binding(eof=True), 'BOOTSTRAP_EOF_BINDING_CHANGED')
                return True  # Terminal old stream only; no live owner sample or dispatch.
            if drained_quit_eof():
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                await self._complete_eof(writer, row, decoder_empty=decoder_empty)
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                current = drained_quit_binding(eof=True)
                need(current is not None and all(a is b for a, b in zip(quit_binding, current)),
                     'QUIT_EOF_BINDING_CHANGED')
                return True  # EOF closes only this drained stream, not the native process.
            if drained_restart_eof():
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                await self._complete_eof(writer, row, decoder_empty=decoder_empty)
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                current = drained_restart_binding(eof=True)
                need(current is not None, 'RESTART_EOF_BINDING_CHANGED')
                self._restart_same(restart_binding, current)
                row['account_terminal_reason'] = 'DRAINED_RESTART_ACTUAL_EOF'
                return True
            state = self.realm._quit.get(id(writer))
            if (state is None or state['writer'] is not writer
                    or state['response_drained'] is not True):
                raise  # Ordinary polls retain the original strict-live refusal.
            # Only a fully drained source Quit can enter this terminal read.
            # No live OwnerSample, payload dispatch or write is permitted here.
            need(decoder_empty is True and row['policy_row'].buffered == 0,
                 'EXACT_DRAINED_QUIT_EOF_REQUIRED')
            return await self._drained_quit_read_eof(writer, row, read_task,
                decoder=decoder, decoder_empty=decoder_empty, quit_binding=quit_binding,
                binding_check=drained_quit_binding, original_error=error)

    async def join_quit_exit(self):
        """Give only proven terminal Quit tasks the existing close bound to join."""
        async def join():
            tasks = []
            for rows in self._claims.values():
                for row in rows:
                    task = row.get('task')
                    state = self.realm._quit.get(id(row['writer']))
                    if (task is not None and not task.done() and state is not None
                            and state['writer'] is row['writer']
                            and state['response_drained'] is True):
                        await self._quit_exit(row['writer'], row)
                        tasks.append(task)
            if tasks:
                await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            return dict(eligible=len(tasks), joined=sum(task.done() for task in tasks))
        try:
            return await asyncio.wait_for(join(), self.policy.CLOSE_NS / 1e9)
        except (ValueError, TimeoutError):
            return dict(status='UNKNOWN')

    def _quit_closing_witness(self, writer, row, position):
        """First-ACK drain and this exact frame's already-proved owner sample."""
        from tools.local_original_session.manual_source_quit import SourceQuitRequests
        source = self._source_quit_closing
        if type(source) is not SourceQuitRequests:
            return False
        try:
            policy, realm = self.policy, self.realm
            peer, policy_row = row['peer'], row['policy_row']
            state = realm._quit.get(id(writer))
            evidence = source._drain_evidence
            receipt = row['_quit_frame_owner']
            late = source._requests.get('Quit6Approval')
            first = source._requests.get('FirstLandQuit')
            first_returned = source._returned.get('FirstLandQuit')
            claims = [claim for rows in self._claims.values() for claim in rows
                      if claim['writer'] is writer]
            frame_receipt = type(receipt) is tuple and len(receipt) == 10
            terminal_receipt = type(receipt) is _TerminalQuitReceipt
            sample = receipt[7] if frame_receipt else None
            return (source.broker is self and source.owner is policy.owner
                    and source.consumer.reader.owner is policy.owner
                    and source.requests.consumer is source.consumer
                    and source._started is True and source._closed is False
                    and source._claimed == {'FirstLandQuit', 'Quit6Approval'}
                    and type(first) is dict and type(late) is dict
                    and type(first_returned) is tuple and len(first_returned) == 2
                    and first_returned[0]['status'] == 'RETURNED'
                    and type(first['seq']) is int and type(late['seq']) is int
                    and 0 < first['seq'] < late['seq'] == source.consumer.sequence
                    and type(evidence) is tuple and len(evidence) == 5
                    and evidence[0] is writer and evidence[1] is row
                    and evidence[2] is realm and evidence[3] is state
                    and evidence[4] == peer['connection_id'] == 4
                    and state is not None and state['writer'] is writer
                    and state['position'] is position
                    and state['source_connection_id'] == peer['connection_id']
                    and all(state[key] is True for key in ('request_verified',
                        'response_drain_returned', 'response_queue_empty', 'response_drained'))
                    and policy._quit_drained.get(id(writer)) is writer
                    and len(claims) == 1 and claims[0] is row
                    and row['writer'] is writer
                    and row['await_phase'] == ('FRAME_DISPATCH' if frame_receipt
                                                 else 'TERMINAL_QUIT_DISPATCH')
                    and row['operation_lock'].locked() and not row['failed']
                    and not row['joined'] and not row['eof']
                    and policy_row is policy._connection(writer)
                    and policy_row.writer is writer and policy_row.stage == 1
                    and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
                    and not policy_row.eof and policy_row.drain_started_ns is None
                    and policy_row.pending_opcode is None and policy_row.pending_size == 0
                    and policy_row.buffered == 0 and policy.state == 'OPEN'
                    and not self._closing and not self.failure.is_set()
                    and ((frame_receipt
                          and receipt[0] is writer and receipt[1] is row and receipt[2] is peer
                          and receipt[3] == tuple(sorted(peer.items()))
                          and receipt[4] is policy_row and receipt[5] is row['operation_lock']
                          and receipt[6] is writer.transport
                          and receipt[8] == QUIT_REQUEST and receipt[9] == 10
                          and type(sample) is OwnerSample and sample.owner is policy.owner
                          and sample.handle is policy.handle and sample.job is policy.job
                          and sample.exact_identity_and_tuple is True and sample.alive is True
                          and sample.peer.port == peer['server_port'] == peer['endpoint_port'] == 14030
                          and sample.peer.client_port == peer['client_port']
                          and sample.peer.accepted_ns == peer['accepted_monotonic_ns']
                          and type(sample.observed_ns) is int
                          and 0 < sample.observed_ns <= time.monotonic_ns())
                         or (terminal_receipt and receipt.broker is self
                             and receipt.writer is writer and receipt.row is row
                             and receipt.peer is peer and receipt.peer_values == tuple(sorted(peer.items()))
                             and receipt.policy_row is policy_row
                             and receipt.operation_lock is row['operation_lock']
                             and receipt.transport is writer.transport
                             and receipt.read_task is row['_read_task']
                             and receipt.read_task.done() and not receipt.read_task.cancelled()
                             and receipt.read_task.exception() is None
                             and type(receipt.read_task.result()) is bytes
                             and len(receipt.read_task.result()) == 10
                             and type(receipt.decoder) is ClientPlaintextDecoder
                             and receipt.decoder.buffered_bytes == 0
                             and type(receipt.frame) is Frame
                             and receipt.frame.opcode == QUIT_REQUEST
                             and receipt.frame.wire_length == 10
                             and receipt.frame.payload == b''
                             and state['duplicate_requests'] == 0)))
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    async def _quit_duplicate_owner(self, writer, row, position):
        """No-effect duplicate Quit using the strict sample from this frame."""
        if not self._selected_owner_current(writer, row, position):
            self._owner_failure(row, 'QUIT_SELECTED_CURRENT_FALSE')
            return False
        if self._source_quit_closing is None:
            return await self._movement_owner(writer, row, position)
        if not self._quit_closing_witness(writer, row, position):
            self._owner_failure(row, 'QUIT_SOURCE_FRAME_WITNESS_FALSE')
            return False
        from tools.local_original_session.launcher import NativeOwner
        owner = self.policy.owner
        receipt = row['_quit_frame_owner']
        terminal = type(receipt) is _TerminalQuitReceipt
        method = 'quit_terminal_retained_sync' if terminal else 'quit_frame_retained_sync'
        target = getattr(NativeOwner, method, None)
        callback = getattr(owner, method, None)
        if (type(owner) is not NativeOwner or target is None
                or getattr(callback, '__self__', None) is not owner
                or getattr(callback, '__func__', None) is not target):
            self._owner_failure(row, 'QUIT_NATIVE_CALLBACK_BINDING_FALSE')
            return False
        if terminal:
            if callback(row['peer']) is not True:
                self._owner_failure(row, 'QUIT_RETAINED_PRIMARY_FALSE')
                return False
        else:
            # The original received_frame policy just admitted this exact
            # OwnerSample and _quit_closing_witness bound it to this one Quit.
            sample = receipt[7]
            now = time.monotonic_ns()
            if (type(sample.observed_ns) is not int or not 0 < sample.observed_ns <= now
                    or now - sample.observed_ns > self.policy.FRESH_NS):
                self._owner_failure(row, 'QUIT_FRAME_SAMPLE_NOT_FRESH')
                return False
            if callback(sample, row['peer']) is not True:
                self._owner_failure(row, 'QUIT_FRAME_RETAINED_FALSE')
                return False
        self.source_guard()
        current = (self._quit_closing_witness(writer, row, position)
                   and self._selected_owner_current(writer, row, position))
        if not current:
            self._owner_failure(row, 'QUIT_POST_CURRENT_FALSE')
        return current

    def _selected_owner_current(self, writer, row, position):
        policy_row = row['policy_row']
        if (row['writer'] is not writer or policy_row is None or policy_row.writer is not writer
                or policy_row.stage != 1 or row['joined'] or row['failed']
                or self._closing or self.failure.is_set()):
            return False
        game = self.realm.registry.resolve(writer)
        service = self.realm.service(writer)
        selected = game.selection
        if (selected is None or selected.reference != position.name
                or self.realm.registry.selected.get(position.name) is not selected
                or service.snapshot() is not position or position.map_id != 0):
            return False
        saved_uid, _ = self.realm.store.select(selected.reference)
        return (saved_uid == position.uid == self.realm.profile_uid
                and position.name == self.realm.profile_name
                and self.realm.positions.restore(position) == position)

    async def _movement_owner(self, writer, row, position):
        def exact_selection():
            policy_row = row['policy_row']
            if (row['writer'] is not writer or policy_row is None or policy_row.writer is not writer
                    or policy_row.stage != 1 or row['joined'] or row['failed']
                    or self._closing or self.failure.is_set()):
                return False
            game = self.realm.registry.resolve(writer)
            service = self.realm.service(writer)
            selected = game.selection
            if (selected is None or selected.reference != position.name
                    or self.realm.registry.selected.get(position.name) is not selected
                    or service.snapshot() is not position or position.map_id != 0):
                return False
            saved_uid, _ = self.realm.store.select(selected.reference)
            return (saved_uid == position.uid == self.realm.profile_uid
                    and position.name == self.realm.profile_name
                    and self.realm.positions.restore(position) == position)
        if not exact_selection():
            return False
        await self._checkpoint(writer, row)  # Exact tuple + retained native owner.
        return exact_selection()  # Recheck mutable selection after that await.

    async def _send_npc_notification_locked(self, writer, row, delivery):
        need(row['operation_lock'].locked(), 'NPC_DEATH_EXISTING_ROW_LOCK_REQUIRED')
        try:
            await self._send(writer, row, (delivery.wire,), game=True,
                             operation_lock=row['operation_lock'])
        except BaseException:
            self._attack_session.fail()
            row['failed'] = True
            self._fail('NPC_NOTIFICATION_SEND_OUTCOME_UNKNOWN')
            raise

    def _npc_player_hit_service(self, policy):
        from tools.local_original_session import npc_player_hit
        service = getattr(self, '_npc_player_hit', None)
        need(type(policy) is str and policy == npc_player_hit.POLICY
             and type(service) is npc_player_hit.Service and service is self.realm._npc_player_hit
             and service.policy == policy,
             'NPC_PLAYER_HIT_ENABLED_SERVICE_REQUIRED')
        return service

    def _npc_player_hit_repeated_service(self, policy):
        from tools.local_original_session import npc_player_hit
        service = getattr(self, '_npc_player_hit', None)
        need(type(policy) is str and policy == npc_player_hit.REPEATED_POLICY
             and type(service) is npc_player_hit.Service and service is self.realm._npc_player_hit
             and service.policy == policy, 'NPC_PLAYER_HIT_REPEATED_SERVICE_REQUIRED')
        return service

    async def npc_player_hit_repeated_context(self, writer, *, policy, target_uid=None):
        service = self._npc_player_hit_repeated_service(policy)
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_PLAYER_HIT_CURRENT_ROW_REQUIRED')
        row, = rows
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            await self._checkpoint(writer, row)
            return service.capture_locked(writer,source_uid=target_uid)

    async def attack_player_repeated(self, writer, *, expected_context, raw_effect, direction, policy, retaliation_lease=None, continuous_lease=None):
        service = self._npc_player_hit_repeated_service(policy)
        return await self._attack_player_current(writer, service=service, expected_context=expected_context,
            raw_effect=raw_effect, direction=direction, repeated=True, retaliation_lease=retaliation_lease,continuous_lease=continuous_lease)

    async def npc_player_hit_context(self, writer, *, policy):
        service = self._npc_player_hit_service(policy)
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_PLAYER_HIT_CURRENT_ROW_REQUIRED')
        row, = rows
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            await self._checkpoint(writer, row)
            return service.capture_locked(writer)

    def npc_player_hit_report(self):
        service = getattr(self, '_npc_player_hit', None)
        return None if service is None or service.last_result is None else dict(service.last_result,
            before=dict(service.last_result['before']),
            after=None if service.last_result['after'] is None else dict(service.last_result['after']))

    async def attack_player_once(self, writer, *, expected_context, raw_effect, direction, policy):
        from tools.local_original_session import npc_player_hit
        service = self._npc_player_hit_service(policy)
        return await self._attack_player_current(writer, service=service, expected_context=expected_context,
            raw_effect=raw_effect, direction=direction, repeated=False)

    async def _attack_player_current(self, writer, *, service, expected_context, raw_effect, direction, repeated, retaliation_lease=None, continuous_lease=None):
        from tools.local_original_session import npc_player_hit
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_PLAYER_HIT_CURRENT_ROW_REQUIRED')
        row, = rows
        operation = None
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            # Invalid/stale requests do not consume a different active request.
            service.validate_locked(writer, expected_context)
            if retaliation_lease is not None:
                from tools.local_original_session import npc_retaliation
                need(repeated is True, 'RETALIATION_REPEATED_PRODUCER_REQUIRED')
                npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context)
            if continuous_lease is not None:
                from tools.local_original_session import npc_continuous_retaliation
                need(repeated is True, 'RETALIATION_REPEATED_PRODUCER_REQUIRED')
                npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context)
            if repeated:
                service.require_repeated_ready(writer, row, expected_context.snapshot,source_uid=expected_context.source_uid)
            else:
                need(id(writer) not in service._operations, 'NPC_PLAYER_HIT_ONCE_REQUEST_REQUIRED')
            await self._checkpoint(writer, row)
            service.validate_locked(writer, expected_context)
            need(id(writer) not in service.status._operations, 'HP_STATUS_CURRENT_SNAPSHOT_ONCE_REQUIRED')
            if retaliation_lease is not None:
                npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context)
            if continuous_lease is not None:
                npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context)
            operation = service.prepare_locked(writer, expected_context=expected_context)
            try:
                if retaliation_lease is not None:
                    npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context).bind_operation_locked(
                        writer,row,retaliation_lease,expected_context,operation)
                if continuous_lease is not None:
                    npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context).bind_operation_locked(
                        writer,row,continuous_lease,expected_context,operation)
                wire = service.build_locked(writer, operation, raw_effect=raw_effect, direction=direction)
                await self._send(writer, row, (wire,), game=True, operation_lock=row['operation_lock'],
                                 npc_player_hit_operation=operation,retaliation_lease=retaliation_lease,continuous_lease=continuous_lease)
                service.validate_locked(writer, expected_context)
                if retaliation_lease is not None:
                    npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context,operation)
                if continuous_lease is not None:
                    npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context,operation)
                before = expected_context.snapshot
                if repeated:
                    from tools.local_original_session import hp_status
                    status = service.status.prepare_repeated(writer, row, expected_snapshot=before,
                        expected_revision=before.revision, policy=hp_status.REPEATED_POLICY)
                else:
                    status = service.status.prepare(writer, row, current_hp=before.current_hp-1,
                        maximum_hp=before.maximum_hp, expected_snapshot=before, expected_revision=before.revision)
                operation.hp_operation, operation.phase, operation.hp_transport = status, 'STATUS', 'PREPARED'
                service.remember(operation)
                await self._send(writer, row, (status.wire,), game=True, operation_lock=row['operation_lock'],
                                 status_operation=status, npc_player_hit_operation=operation,retaliation_lease=retaliation_lease,continuous_lease=continuous_lease)
                result = npc_player_hit.Result(before, status.result.after, expected_context.source_uid,
                                               service, operation)
                operation.result = result
                operation.phase = 'COMMITTED'
                service.last_result = result.metadata()
                return result
            except BaseException as error:
                if self._hp_resource_owner is not None:
                    try: self._hp_resource_owner.fail_active_hp(writer,error)
                    except BaseException: pass
                service.terminal(operation)  # Preserve both partial transports and committed HP.
                row['failed'] = True
                self._fail('NPC_PLAYER_HIT_OUTCOME_UNKNOWN')
                raise

    def _player_life_service(self, policy):
        from tools.local_original_session import player_life
        service = self._player_life
        need(type(service) is player_life.Service and type(policy) is player_life.Policy
             and service.policy is policy and self.realm._player_life_broker is self,
             'PLAYER_LIFE_EXACT_EXPLICIT_POLICY_REQUIRED')
        return service

    async def player_life_context(self, writer, *, policy, target_uid=None):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            await self._checkpoint(writer,row)
            return service.capture_locked(writer,source_uid=target_uid)

    async def player_lethal_once(self, writer, *, expected_context, recovery_inputs, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            service.current_locked(writer,expected_context)
            await self._checkpoint(writer,row)
            try:
                return await service.lethal_locked(writer,expected_context,recovery_inputs)
            except BaseException as error:
                if self._hp_resource_owner is not None:
                    try: self._hp_resource_owner.fail_active_hp(writer,error)
                    except BaseException: pass
                raise

    async def npc_lethal_context(self, writer, *, expected_context, arrival, policy):
        from tools.local_original_session import npc_player_lethal
        life = self._player_life_service(policy)
        service = self._npc_player_lethal
        need(type(service) is npc_player_lethal.Service and service.life is life,
             'NPC_LETHAL_EXACT_EXPLICIT_SERVICE_REQUIRED')
        row = life.status._checked(writer)[3]
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            await self._checkpoint(writer,row)
            return service.capture_locked(writer,life_context=expected_context,arrival=arrival)

    async def npc_lethal_player(self, writer, *, expected_context, recovery_inputs, raw_effect, direction, policy):
        from tools.local_original_session import npc_player_lethal
        life = self._player_life_service(policy)
        service = self._npc_player_lethal
        need(type(service) is npc_player_lethal.Service and service.life is life,
             'NPC_LETHAL_EXACT_EXPLICIT_SERVICE_REQUIRED')
        row = life.status._checked(writer)[3]
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            service.validate_locked(writer,expected_context)
            await self._checkpoint(writer,row)
            try:
                return await life.lethal_npc_locked(writer,expected_context,recovery_inputs,
                    raw_effect=raw_effect,direction=direction)
            except BaseException as error:
                if self._hp_resource_owner is not None:
                    try: self._hp_resource_owner.fail_active_hp(writer,error)
                    except BaseException: pass
                raise

    async def npc_lethal_player_scoped(self, writer, *, expected_context, recovery_inputs,
                                      raw_effect, direction, policy):
        """Consume the original typed PRE in its caller's current row scope.

        The repeat host performs the original checkpoint before its query. The
        leaf and original send still revalidate every current/send authority.
        """
        from tools.local_original_session import npc_player_lethal, player_life
        life = self._player_life_service(policy)
        service = self._npc_player_lethal
        need(type(service) is npc_player_lethal.Service and service.life is life
             and life.policy.newlife == player_life.REPEATED_NEWLIFE_POLICY,
             'NPC_LETHAL_EXACT_EXPLICIT_SERVICE_REQUIRED')
        row = life.status._checked(writer)[3]
        task=asyncio.current_task()
        need(self._canonical_provider is not None
             and self._canonical_operation_task is task
             and task is not None and row['operation_lock'].locked(),
             'BATCH_OPERATION_SCOPE_REQUIRED')
        if self._hp_resource_owner is not None:
            self._hp_resource_owner.require_hp_quiescent(writer)
        if task.cancelling(): raise asyncio.CancelledError()
        try:
            return await life.lethal_npc_locked(writer,expected_context,recovery_inputs,
                raw_effect=raw_effect,direction=direction)
        except BaseException as error:
            if self._hp_resource_owner is not None:
                try: self._hp_resource_owner.fail_active_hp(writer,error)
                except BaseException: pass
            raise

    async def confirm_player_death(self, writer, *, expected_result, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            await self._checkpoint(writer,row)
            service.confirm_death_locked(writer,expected_result)

    async def recover_player(self, writer, *, expected_context, recovery_inputs, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            service.current_locked(writer,expected_context)
            await self._checkpoint(writer,row)
            try:
                return await service.recover_locked(writer,expected_context,recovery_inputs)
            except BaseException as error:
                if self._hp_resource_owner is not None:
                    try: self._hp_resource_owner.fail_active_hp(writer,error)
                    except BaseException: pass
                raise

    async def confirm_player_recovery(self, writer, *, expected_result, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            await self._checkpoint(writer,row)
            return service.confirm_recovery_locked(writer,expected_result)

    async def update_hp_status(self, writer, *, current_hp, maximum_hp,
                               expected_snapshot, expected_revision, policy):
        """One explicit positive local-character HP display update per selection."""
        need(self._hp_resource_owner is None, 'RESOURCE_LEGACY_HP_PRODUCER_UNAVAILABLE')
        from tools.local_original_session import hp_status
        service = getattr(self, '_hp_status', None)
        need(type(policy) is str and policy == hp_status.POLICY
             and type(service) is hp_status.Service and service is self.realm._hp_status,
             'HP_STATUS_ENABLED_SERVICE_REQUIRED')
        hp_status.hp_pair(current_hp, maximum_hp)
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'HP_STATUS_CURRENT_ROW_REQUIRED')
        row, = rows
        try:
            async with row['operation_lock']:
                need(service.current(writer) is expected_snapshot,
                     'HP_STATUS_CURRENT_SNAPSHOT_ONCE_REQUIRED')
                await self._checkpoint(writer, row)
                need(service.current(writer) is expected_snapshot,
                     'HP_STATUS_CURRENT_SNAPSHOT_ONCE_REQUIRED')
                operation = service.prepare(writer, row, current_hp=current_hp, maximum_hp=maximum_hp,
                    expected_snapshot=expected_snapshot, expected_revision=expected_revision)
                await self._send(writer, row, (operation.wire,), game=True,
                                 operation_lock=row['operation_lock'], status_operation=operation)
                return service.summary(writer)
        except BaseException:
            # Preserve the committed HP, never roll back/replay an ambiguous send.
            service.release(writer)
            row['failed'] = True
            self._fail('HP_STATUS_UPDATE_OUTCOME_UNKNOWN')
            raise

    async def _npc_death_after_feedback_locked(self, writer, row, intent):
        notifications = self._attack_session._notifications
        if notifications is not None:
            delivery = notifications.prepare_death(writer, row, intent)
            if delivery is not None:
                await self._send_npc_notification_locked(writer, row, delivery)

    async def remove_dead_npc(self, writer, target_uid, accepted_ordinal, *, policy):
        """Separate explicit backend lifetime decision; no timer or auto-chain."""
        service = self._attack_session
        need(service is not None and service._notifications is not None,
             'NPC_REMOVE_NOTIFICATIONS_DISABLED')
        rows = [row for claims in self._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows) == 1, 'NPC_REMOVE_CURRENT_CLAIM_REQUIRED')
        row, = rows
        async with row['operation_lock']:
            delivery = service._notifications.prepare_remove(writer, row, uid=target_uid,
                                accepted_ordinal=accepted_ordinal, policy=policy)
            await self._send_npc_notification_locked(writer, row, delivery)
            return dict(status='DRAINED',
                        target_uid=target_uid, accepted_ordinal=accepted_ordinal,
                        client_registry='UNKNOWN', screen='UNKNOWN')

    async def respawn_npc(self, writer, *, ticket, spawn, now_ns, prepared_adapter, adopt_generation):
        from tools.local_original_session import npc_respawn
        service = self._npc_respawn
        need(type(service) is npc_respawn.Service and service is self.realm._npc_respawn
             and service.run.__func__ is npc_respawn.Service.run, 'NPC_RESPAWN_ENABLED_SERVICE_REQUIRED')
        return await service.run(writer, ticket=ticket, spawn=spawn, now_ns=now_ns,
                                 prepared_adapter=prepared_adapter, adopt_generation=adopt_generation)

    async def step_npc(self, writer, *, goal, direction, now_ns, expected_mover=None, continuous_motion_lease=None, target_uid=None):
        """Explicit local AI producer; no timer, self echo or player-edge reuse."""
        row = next((row for rows in self._claims.values() for row in rows
                    if row['writer'] is writer), None)
        need(row is not None, 'NPC_MOVE_CURRENT_CLAIM_REQUIRED')
        scope = (self._row_operation(writer,row) if continuous_motion_lease is not None else row['operation_lock'])
        async with scope:
            if continuous_motion_lease is not None:
                from tools.local_original_session import npc_continuous_retaliation
                npc_continuous_retaliation.validate_motion(self,writer,row,continuous_motion_lease)
            mover = self.realm.npc_mover(writer,target_uid=target_uid)
            if self._npc_respawn is not None:
                need(expected_mover is mover, 'NPC_MOVE_SAME_OWNED_GENERATION_REQUIRED')
            selected = self.realm.service(writer).snapshot()
            need(await self._movement_owner(writer, row, selected) is True,
                 'NPC_MOVE_CURRENT_OWNER_REQUIRED')
            need(self.realm.npc_mover(writer,target_uid=target_uid) is mover and mover.spawn_drained,
                 'NPC_MOVE_DRAINED_SPAWN_REQUIRED')
            attack_session = getattr(self, '_attack_session', None)
            if attack_session is not None:
                attack_session.require_live_npc_motion(writer, row, mover.state.uid)
            step = mover.plan(goal=goal, direction=direction, now_ns=now_ns)
            edge = self.realm.npc_edge_passability(mover.state.uid, mover.state.map_id,
                mover.state.packed, direction, step.after.packed)
            if inspect.isawaitable(edge):
                edge = await edge
            need(edge is True, 'NPC_MOVE_EDGE_BLOCKED_OR_UNKNOWN')
            need(await self._movement_owner(writer, row, selected) is True
                 and self.realm.npc_mover(writer,target_uid=target_uid) is mover, 'NPC_MOVE_CURRENT_OWNER_REQUIRED')
            if attack_session is not None:
                attack_session.require_live_npc_motion(writer, row, mover.state.uid)
            if continuous_motion_lease is not None:
                npc_continuous_retaliation.validate_motion(self,writer,row,continuous_motion_lease).bind_motion_locked(
                    writer,row,continuous_motion_lease,step)
            mover.begin(step)  # Explicit local reference + original consumer pins.
            try:
                await self._send(writer, row, (step.frame,), game=True,
                                 continuous_motion_lease=continuous_motion_lease)
                need(not self._closing and not self.failure.is_set()
                     and not row['joined'] and not row['failed']
                     and self.realm.npc_mover(writer,target_uid=target_uid) is mover, 'NPC_MOVE_POST_DRAIN_OWNER_REQUIRED')
                mover.commit(step)  # Once, after positive write/drain and current lifetime.
            except BaseException:
                mover.fail()  # Delivery may have occurred; no automatic retry/rollback.
                row['failed'] = True
                self._fail('NPC_MOVE_SEND_OUTCOME_UNKNOWN')
                raise
            return mover.state

    def _inventory_items(self, frame):
        from tools.local_original_session import inventory
        policy = self._inventory_collection_policy
        if policy is None:
            return (inventory.validate_frame(frame),)
        need(type(policy) is str and policy == inventory.COLLECTION_POLICY,
             'INVENTORY_COLLECTION_EXPLICIT_POLICY_REQUIRED')
        store = self._inventory_store
        if store is not None and getattr(store, '_aggregate_capability', None) is not None:
            return inventory.validate_current_collection_frame(frame, policy=policy)
        return inventory.validate_collection_frame(frame, policy=policy)

    def _inventory_collection_before_write_locked(self, writer, row, service, frame, items):
        """Called only from the original leaf AFTER its real empty-vector read.

        Synchronous same-row adoption before first write. No independent empty
        authority, re-lock, query, timer, send, rollback or retry is produced.
        """
        from tools.local_original_session import inventory, inventory_store
        need(type(service) is inventory.InventoryService and service is self._inventory_service
             and service.broker is self and service._inflight and not service._claimed
             and self._inventory_collection_policy == inventory.COLLECTION_POLICY
             and service._collection_policy == self._inventory_collection_policy,
             'INVENTORY_COLLECTION_ORIGINAL_EMPTY_LEAF_REQUIRED')
        generation = self.inventory_selection_current(writer)
        need(generation is self._inventory_generation and generation.row is row
             and row['operation_lock'].locked() and generation.phase == 'ACTIVE'
             and generation.mode == 'RESTORED_EXISTING' and generation.restored is True
             and generation.attempted is True and generation.write_attempted is False
             and generation.delivery_authority is None and generation.current_frame is None
             and self._inventory_restore_only is True
             and frame is generation.frame and frame is generation.operation_frame,
             'INVENTORY_COLLECTION_BEFORE_FIRST_DELIVERY_REQUIRED')
        self._inventory_selection_frame_current(writer, row, frame)
        need(type(items) is tuple and 0 <= len(items) <= 2
             and (items or (self._inventory_store is not None and
                  getattr(self._inventory_store, '_aggregate_capability', None) is not None))
             and all(type(item) is inventory.ItemInfo for item in items),
             'INVENTORY_COLLECTION_REAL_PARSED_ITEMS_REQUIRED')
        if self.item_transfer_policy is not None:
            from tools.local_original_session import item_custody
            snapshot = self._inventory_store.custody_snapshot(self.realm.service(writer).snapshot().uid)
            need(self._inventory_collection_grant is None and
                 frame == item_custody.owned_frame(snapshot), 'ITEM_TRANSFER_EXACT_READONLY_CUSTODY_REQUIRED')
            return frame  # A-only is a real custody projection, NEVER a second grant.
        if len(items) == 2:
            return frame  # Existing saved2: no grant, only strict read-only verification.
        store = self._inventory_store
        aggregate = getattr(store, '_aggregate_capability', None)
        if aggregate is not None:
            # Existing canonical singleton, AFTER the original real empty-vector
            # leaf: strict read only, never a second-instance grant or a claim.
            from tools.local_original_session.inventory_aggregate import AggregateReadCapability
            restore, binding_check = store.restore, store._aggregate_binding
            need(type(store) is inventory_store.InventoryStore
                 and store is service._persistence_store()
                 and type(aggregate) is AggregateReadCapability
                 and restore.__self__ is store
                 and restore.__func__ is inventory_store.InventoryStore.restore
                 and binding_check.__self__ is store
                 and binding_check.__func__ is inventory_store.InventoryStore._aggregate_binding
                 and binding_check() is aggregate,
                 'INVENTORY_CANONICAL_ORIGINAL_RESTORE_REQUIRED')
            service._cancelled()
            self._inventory_admission_time()
            authority = service._current(writer, row)
            bound = self._inventory_selection_binding
            canonical_frame = restore(authority[0].uid)  # Strict current cap/schema/source read.
            need(type(canonical_frame) is bytes and canonical_frame == frame,
                 'INVENTORY_CANONICAL_RESTORE_FRAME_CHANGED')
            canonical_items = self._inventory_items(canonical_frame)
            need(0 <= len(canonical_items) <= 1 and canonical_items == items,
                 'INVENTORY_CANONICAL_RESTORE_EXACT_CURRENT_REQUIRED')
            service._cancelled()
            self._inventory_admission_time()
            service._same(authority, service._current(writer, row))
            need(self.inventory_selection_current(writer) is generation
                 and self._inventory_selection_binding is bound
                 and generation.frame is frame and generation.operation_frame is frame
                 and store is service._persistence_store()
                 and store.restore == restore and store._aggregate_binding == binding_check
                 and binding_check() is aggregate,
                 'INVENTORY_CANONICAL_RESTORE_BINDING_CHANGED')
            self._inventory_selection_frame_current(writer, row, frame)
            return frame  # Original literal identity; no new grant/write/claim.
        options = self._inventory_collection_grant
        need(type(options) is tuple and len(options) == 2 and
             options[0] == inventory_store.SECOND_INSTANCE_POLICY and type(options[1]) is frozenset
             and generation.collection_grant is None,
             'INVENTORY_COLLECTION_EXACT_GRANT_OPTIONS_REQUIRED')
        store = self._inventory_store
        method = store.grant_second_instance
        need(type(store) is inventory_store.InventoryStore and store is service._persistence_store()
             and method.__self__ is store and method.__func__ is inventory_store.InventoryStore.grant_second_instance,
             'INVENTORY_COLLECTION_ORIGINAL_GRANT_REQUIRED')
        # Revalidate the actual selection/source/cancel boundary before durable IO.
        service._cancelled()
        self._inventory_admission_time()
        authority = service._current(writer, row)
        bound = self._inventory_selection_binding
        grant = method(authority[0].uid, expected_frame=frame, prototype_uid=items[0].identifier,
                       policy=options[0], reserved_uids=options[1])
        need(type(grant) is inventory_store.InstanceGrant and grant.before_frame is frame
             and grant.character_uid == authority[0].uid and grant.prototype_uid == items[0].identifier
             and grant.policy == options[0] and self._inventory_collection_grant is options,
             'INVENTORY_COLLECTION_REAL_GRANT_RESULT_REQUIRED')
        service._same(authority, service._current(writer, row))
        need(self._inventory_generation is generation and self._inventory_selection_binding is bound
             and generation.frame is frame and generation.operation_frame is frame,
             'INVENTORY_COLLECTION_GRANT_BINDING_CHANGED')
        after = grant.after_frame
        # The exact original Store method validated the generated collection.
        # The leaf next parses that same after frame and verifies disk equality;
        # repeating source IO/codec here supplies no additional native authority.
        # Exactly one initial literal is now adopted. The old frame1/binding is
        # not accepted by _send, policy reservation or post-drain publication.
        generation.collection_grant = grant
        self._inventory_frame = self._inventory_operation_frame = after
        self._inventory_selection_binding = bound[:10] + (after,)
        self._inventory_selection_frame_current(writer, row, after)
        return after

    def _inventory_selection_frame_current(self, writer, row, frame):
        """Keep the selected generation's one adopted literal, not restore-read identity."""
        store = getattr(self, '_inventory_store', None)
        if store is None:
            return
        service = self._inventory_service
        bound = self._inventory_selection_binding
        need(bound is not None and len(bound) == 11 and all(a is b for a, b in zip(bound,
            (writer, row, row['operation_lock'], self.realm, self.realm.registry,
             self.realm.registry.resolve(writer), self.realm.service(writer),
             self.realm.registry.resolve(writer).selection, service, store, frame)))
             and frame is self._inventory_frame and service._persistence_store() is store,
             'INVENTORY_SELECTED_STORE_FRAME_CHANGED')

    def inventory_selection_current(self, writer):
        """Structural current-generation observation only; no Store/native reads."""
        if getattr(self, 'inventory_reselection_policy', None) is None:
            return None
        from tools.local_original_session import inventory
        generation = self._inventory_generation
        need(type(generation) is _InventoryGeneration and generation.broker is self,
             'INVENTORY_RESELECTION_REAL_GENERATION_REQUIRED')
        if generation.writer is None or generation.phase in ('RETIRED', 'PREPARING'):
            return None
        need(type(self.inventory_reselection_policy) is str
             and self.inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
             and type(self.inventory_delivery_policy) is str
             and self.inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
             and self.restart_policy == 'EXPLICIT_LOCAL_SELECTED_RESTART'
             and self.policy.restart_enabled is True
             and generation.phase == 'ACTIVE' and not self._closing and not self.failure.is_set(),
             'INVENTORY_RESELECTION_GENERATION_NOT_ACTIVE')
        row, game, service = generation.row, generation.game, generation.service
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        need(generation.writer is writer and len(claims) == 1 and claims[0] is row
             and row['writer'] is writer and generation.lock is row['operation_lock']
             and not row['failed'] and not row['joined']
             and self.realm.registry.resolve(writer) is game
             and self.realm._account_bound.get(id(writer)) is generation.account
             and game.selection is generation.selected
             and self.realm.registry.selected.get(generation.selected.reference) is generation.selected
             and self.realm.service(writer) is generation.mover
             and type(service) is inventory.InventoryService and service is self._inventory_service
             and getattr(service, '_inventory_generation', None) is generation
             and not service._closed and generation.reader is self._inventory_reader
             and service.reader is generation.reader and generation.store is self._inventory_store
             and service.store is generation.store
             and self.realm._item_use_session is generation.item_use_session,
             'INVENTORY_RESELECTION_CURRENT_SELECTION_REQUIRED')
        previous = generation.previous
        if previous is not None:
            need(type(previous) is _InventoryGeneration and previous.broker is self
                 and previous.phase == 'RETIRED' and previous.service._closed
                 and previous.writer is writer and previous.game is game
                 and previous.selected is not generation.selected
                 and previous.reader is generation.reader and previous.store is generation.store
                 and generation.restart_state is previous.restart_state
                 and generation.restart_state['phase'] == 'DRAINED'
                 and generation.restart_state['selection_cleared'] is True,
                 'INVENTORY_RESELECTION_PREVIOUS_LIFETIME_REQUIRED')
        if generation.selection_binding is None:
            need(generation.frame is None and not generation.restored
                 and generation.current_frame is None and not generation.attempted,
                 'INVENTORY_RESELECTION_EMPTY_ROW_REQUIRED')
        else:
            self._inventory_selection_frame_current(writer, row, generation.frame)
            need(generation.selection_binding[7] is generation.selected
                 and generation.selection_binding[8] is service,
                 'INVENTORY_RESELECTION_SAME_BINDING_REQUIRED')
        return generation

    def _inventory_selection_start(self, writer, row):
        """Create one fresh lifetime at the actual selected callback, never reset old once."""
        from tools.local_original_session import inventory
        previous = self._inventory_generation
        game = self.realm.registry.resolve(writer)
        selected, mover = game.selection, self.realm.service(writer)
        account = self.realm._account_bound.get(id(writer))
        need(type(self.inventory_reselection_policy) is str
             and self.inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
             and type(self.inventory_delivery_policy) is str
             and self.inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
             and self.restart_policy == 'EXPLICIT_LOCAL_SELECTED_RESTART'
             and self.policy.restart_enabled is True
             and selected is not None and account is not None and row['writer'] is writer
             and row['operation_lock'].locked(), 'INVENTORY_RESELECTION_SELECTED_LOCK_REQUIRED')
        if previous.writer is None:
            generation = previous
        elif previous.phase == 'RETIRED':
            restart_state = row.get('_restart')
            need(previous.writer is writer and previous.game is game and previous.account is account
                 and previous.selected is not selected and previous.service._closed
                 and previous.reader is self._inventory_reader and previous.store is self._inventory_store
                 and restart_state is previous.restart_state and restart_state['phase'] == 'DRAINED'
                 and restart_state['selection_cleared'] is True,
                 'INVENTORY_RESELECTION_DRAINED_NEW_SELECTION_REQUIRED')
            generation = _InventoryGeneration(self, previous=previous, restart_state=restart_state)
            generation.phase = 'PREPARING'
            self._inventory_generation = generation
        else:
            need(previous.phase == 'ACTIVE' and previous.writer is writer
                 and previous.game is game and previous.selected is selected,
                 'INVENTORY_RESELECTION_NEW_GENERATION_REQUIRED')
            return previous
        generation.writer, generation.row, generation.lock = writer, row, row['operation_lock']
        generation.game, generation.selected, generation.mover = game, selected, mover
        generation.account, generation.reader, generation.store = account, self._inventory_reader, self._inventory_store
        generation.phase = 'PREPARING'
        try:
            if generation.previous is not None:
                generation.service = inventory.InventoryService(self, generation.reader,
                    policy=inventory.POLICY, store=generation.store, collection_policy=self._inventory_collection_policy)
                generation.service._inventory_generation = generation
                if self._inventory_item_use_policy is not None:
                    from tools.local_original_session.item_use_session import ItemUseSession
                    old = previous.item_use_session
                    generation.item_use_session = ItemUseSession(self, policy=self._inventory_item_use_policy)
                    self.realm._replace_item_use_selection(self, writer, old, generation.item_use_session)
                else:
                    need(self.realm._item_use_session is None, 'ITEM_USE_RESELECTION_DISABLED_REQUIRED')
            return generation
        except BaseException:
            generation.phase = 'TERMINAL'
            if generation.service is not None:
                generation.service.close()
            if generation.item_use_session is not None:
                generation.item_use_session.close()
            raise

    async def _restore_inventory_selection(self, writer):
        """Select-time read only. No grant, memory query, automatic delivery or retry."""
        from tools.local_original_session.inventory_store import InventoryStore
        generation = None
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
            need(len(rows) == 1, 'INVENTORY_CURRENT_CLAIM_REQUIRED')
            generation = self._inventory_selection_start(writer, rows[0])
        service, store = self._inventory_service, self._inventory_store
        fallback_config, configured_current = self._inventory_config_frame, self._inventory_frame
        missing_policy = getattr(self, 'inventory_missing_row_policy', None)
        need(service is not None and type(store) is InventoryStore
             and service._persistence_store() is store, 'INVENTORY_EXACT_SELECTED_STORE_REQUIRED')
        # This broker's original once/closed/delivery state is never reset by
        # game Restart/reselect. Redelivery in that lifetime is not supported.
        if self._inventory_attempted:
            return
        rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
        need(len(rows) == 1, 'INVENTORY_CURRENT_CLAIM_REQUIRED')
        row, = rows
        lock = row['operation_lock']
        try:
            before = service._current(writer, row)
            game, selected = self.realm.registry.resolve(writer), self.realm.registry.resolve(writer).selection
            mover = self.realm.service(writer)
            restore = store.restore
            need(getattr(restore, '__self__', None) is store
                 and getattr(restore, '__func__', None) is InventoryStore.restore,
                 'INVENTORY_ORIGINAL_STORE_RESTORE_REQUIRED')
            restored = restore(before[0].uid)
            if self.item_transfer_policy is not None:
                from tools.local_original_session.item_transfer_session import restore_owned_custody
                _, custody_frame = restore_owned_custody(store,before[0].uid)
                need(custody_frame == restored, 'ITEM_TRANSFER_READONLY_RESTORE_CHANGED')
            need(restored is None or type(restored) is bytes, 'INVENTORY_CANONICAL_RESTORE_BYTES_REQUIRED')
            if restored is not None:
                from tools.local_original_session import inventory
                self._inventory_items(restored)
            await self._checkpoint(writer, row)  # After file IO: current native tuple/source.
            self.source_guard()
            self.key_guard()
            service.reader.validate()
            need(self._inventory_service is service and self._inventory_store is store
                 and service._persistence_store() is store and row['operation_lock'] is lock
                 and lock.locked() and not self._inventory_attempted,
                 'INVENTORY_SELECTED_RESTORE_BINDING_CHANGED')
            service._same(before, service._current(writer, row))
            need(self._inventory_config_frame is fallback_config
                 and self._inventory_frame is configured_current,
                 'INVENTORY_SELECTED_CONFIG_FRAME_CHANGED')
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            need(getattr(self, 'inventory_missing_row_policy', None) == missing_policy
                 and (missing_policy is None or type(missing_policy) is str
                      and missing_policy == INVENTORY_MISSING_ROW_POLICY),
                 'INVENTORY_MISSING_ROW_POLICY_CHANGED')
            mode = 'RESTORED_EXISTING' if restored is not None else None
            frame = None if generation is not None and restored is None else (fallback_config if restored is None else restored)
            if generation is not None and restored is None and missing_policy is not None:
                from tools.local_original_session import inventory
                need(before[0].uid == self.realm.profile_uid == 1
                     and dict(inventory.validate_frame(fallback_config).raw_fields) == INVENTORY_STARTER_FIELDS,
                     'INVENTORY_MISSING_ROW_CURRENT_ATHAME_STARTER_REQUIRED')
                frame, mode = fallback_config, 'FIRST_GRANT'
            self._inventory_frame = frame  # Adopt this object exactly once for this selection.
            self._inventory_selection_binding = (None if frame is None else
                (writer, row, lock, self.realm, self.realm.registry, game, mover, selected, service, store, frame))
            self._inventory_restored = restored is not None
            if generation is not None:
                need(self._inventory_generation is generation
                     and type(self.inventory_reselection_policy) is str
                     and self.inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                     and self.inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                     and self.policy.restart_enabled is True,
                     'INVENTORY_RESELECTION_GENERATION_CHANGED')
                generation.mode = mode
                generation.phase = 'ACTIVE'
                if self.item_transfer_policy is not None:
                    from tools.local_original_session.item_transfer_session import ItemTransferSession
                    need(generation.transfer_session is None, 'ITEM_TRANSFER_FRESH_SESSION_REQUIRED')
                    generation.transfer_session = ItemTransferSession(self, generation)
        except BaseException:
            if generation is not None:
                generation.phase = 'TERMINAL'
                if generation.item_use_session is not None:
                    generation.item_use_session.close()
            service.close()  # Failed IO/authority/cancel grants no later send in this broker.
            raise

    def _inventory_operation_mode_current(self, mode, writer, row, frame):
        need(type(mode) is bool and self._inventory_restore_only is mode,
             'INVENTORY_RESTORE_MODE_CHANGED')
        need(frame is self._inventory_operation_frame and frame is self._inventory_frame,
             'INVENTORY_EXPLICIT_FRAME_REQUIRED')
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            generation = self._inventory_generation
            need(self.inventory_selection_current(writer) is generation
                 and generation.phase == 'ACTIVE' and generation.row is row,
                 'INVENTORY_CURRENT_DELIVERY_GENERATION_REQUIRED')
            if generation.mode == 'FIRST_GRANT':
                from tools.local_original_session import inventory
                need(mode is False and generation.restored is False
                     and getattr(self, 'inventory_missing_row_policy', None) == INVENTORY_MISSING_ROW_POLICY
                     and frame is self._inventory_config_frame
                     and dict(inventory.validate_frame(frame).raw_fields) == INVENTORY_STARTER_FIELDS,
                     'INVENTORY_FIRST_GRANT_MODE_REQUIRED')
            else:
                need(generation.mode == 'RESTORED_EXISTING' and mode is True
                     and generation.restored is True, 'INVENTORY_RESTORED_EXISTING_MODE_REQUIRED')
        if mode:
            need(self._inventory_store is not None and self._inventory_restored is True,
                 'INVENTORY_RESTORE_SELECTED_STORE_REQUIRED')
            self._inventory_selection_frame_current(writer, row, frame)
            need(self._inventory_restore_only is mode, 'INVENTORY_RESTORE_MODE_CHANGED')

    def _inventory_refusal_current(self, error):
        """Recheck the actual refused send lifetime without reopening its service."""
        evidence = self._inventory_prewrite_refusal
        need(evidence is not None and evidence[0] is error
             and len(evidence) == 5 and evidence[2] is self._inventory_service
             and type(evidence[3]) is bool and self._inventory_restore_only is evidence[3],
             'INVENTORY_PRE_WRITE_PROOF_REQUIRED')
        self.source_guard()
        need(self.key_guard() is True, 'INVENTORY_REFUSAL_OWNER_UNKNOWN')
        authority = evidence[1]
        need(not self._inventory_write_attempted
             and self._inventory_frame is evidence[4]
             and self._inventory_operation_frame is evidence[4],
             'INVENTORY_PRE_WRITE_PROOF_REQUIRED')
        (broker, reader, backend, owner, member, policy, handle, job, owner_handle,
         owner_job, realm, registry, game, movement, position, selected, row,
         admitted, lock, peer, failure, store, positions, movement_row) = authority[1]
        need(broker is self and self._inventory_service.reader is reader
             and reader is self._inventory_service._reader and reader.backend is backend
             and not reader.closed and reader.owner is owner and reader.member is member
             and not owner.closed and owner.child is member
             and self.policy is policy and policy.owner is owner and policy.handle is handle
             and policy.job is job and owner.owner_handle is owner_handle and owner.owner_job is owner_job
             and member.process == handle and member.job == job
             and not self._closing and self.failure is failure and not failure.is_set()
             and policy.state == 'OPEN', 'INVENTORY_REFUSAL_OWNER_CHANGED')
        matches = [r for rows in self._claims.values() for r in rows if r['writer'] is row['writer']]
        need(len(matches) == 1 and matches[0] is row, 'INVENTORY_REFUSAL_CLAIM_CHANGED')
        need(self.realm is realm and realm.registry is registry and registry.resolve(row['writer']) is game
             and realm.service(row['writer']) is movement and movement.snapshot() is position
             and game.selection is selected and registry.selected.get(position.name) is selected
             and realm.store is store and realm.positions is positions
             and realm._movement.get(id(row['writer'])) is movement_row
             and row['operation_lock'] is lock and row['peer'] is peer
             and row['policy_row'] is admitted and policy._connection(row['writer']) is admitted
             and not any((row['failed'], row['joined'], admitted.failed, admitted.eof,
                          admitted.task_joined, admitted.registry_removed))
             and admitted.drain_started_ns is None and not movement.fatal and not realm._settings_failed
             and id(row['writer']) not in realm._quit, 'INVENTORY_REFUSAL_AUTHORITY_CHANGED')
        need(authority[2] == (tuple(sorted(peer.items())), backend.handle,
             member.pid, tuple(sorted(member.identity.items()))), 'INVENTORY_REFUSAL_AUTHORITY_CHANGED')
        self._inventory_operation_mode_current(evidence[3], row['writer'], row, evidence[4])
        realm.bound_account(row['writer'], game)
        saved_uid, _ = store.select(selected.reference)
        need(saved_uid == position.uid and positions.restore(position) == position,
             'INVENTORY_REFUSAL_STORAGE_CHANGED')
        self._inventory_operation_mode_current(evidence[3], row['writer'], row, evidence[4])
        from tools.local_original_session import inventory
        if type(error) is inventory.ReadOnlyPreWriteRefusal:
            need(type(self._inventory_admission_expired) is bool, 'INVENTORY_ADMISSION_EXPIRY_REQUIRED')
            need(inventory.InventoryService.validate_readonly_refusal(
                evidence[2], error, row['writer'], row, evidence[4],
                admission=False if self._inventory_admission_expired is True else True) is True,
                'INVENTORY_READONLY_REFUSAL_UNPROVEN')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return True

    def _inventory_admission_time(self):
        now = time.monotonic_ns()
        need(type(now) is int and 0 <= now < (1 << 63)
             and (self._inventory_admission_clock_ns is None or now >= self._inventory_admission_clock_ns),
             'INVENTORY_ADMISSION_CLOCK_UNKNOWN')
        self._inventory_admission_clock_ns = now
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        if self._inventory_deadline_ns is not None and now >= self._inventory_deadline_ns:
            evidence = self._inventory_prewrite_refusal
            if evidence is not None:
                self._inventory_refusal_current(evidence[0])
                self._inventory_admission_expired = True
                self._inventory_service.close()
                raise evidence[0]
            raise ValueError('INVENTORY_ADMISSION_DEADLINE')
        return now

    async def add_inventory(self, writer, *, deadline_ns=None, restore_only=False):
        """One explicit configured ADD; no trigger, timer or delivery retry."""
        from tools.local_original_session import inventory
        need(type(restore_only) is bool, 'INVENTORY_RESTORE_MODE_REQUIRED')
        generation = self._inventory_generation
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            need(generation.phase == 'ACTIVE' and self.inventory_selection_current(writer) is generation
                 and type(generation.frame) is bytes and generation.selection_binding is not None,
                 'INVENTORY_RESELECTION_SAVED_ROW_RESTORE_ONLY_REQUIRED')
            if generation.mode == 'FIRST_GRANT':
                need(restore_only is False and generation.restored is False
                     and getattr(self, 'inventory_missing_row_policy', None) == INVENTORY_MISSING_ROW_POLICY
                     and generation.frame is self._inventory_config_frame,
                     'INVENTORY_FIRST_GRANT_MODE_REQUIRED')
            else:
                need(generation.mode == 'RESTORED_EXISTING' and restore_only is True
                     and generation.restored is True,
                     'INVENTORY_RESELECTION_SAVED_ROW_RESTORE_ONLY_REQUIRED')
        service = self._inventory_service
        previous = self._inventory_prewrite_refusal
        continuation = (self._inventory_attempted and previous is not None
                        and self._inventory_deadline_ns is not None)
        need(service is not None and not self._inventory_write_attempted
             and (not self._inventory_attempted
                  or continuation and not service._closed and not service._claimed),
             'INVENTORY_EXPLICIT_ONCE_OPERATION_REQUIRED')
        if not self._inventory_attempted:
            self._inventory_attempted = True  # One command, before any await/cancellation.
            self._inventory_operation_frame = self._inventory_frame
            self._inventory_restore_only = restore_only
            self._inventory_deadline_ns = deadline_ns
        operation_frame = self._inventory_operation_frame if previous is None else None
        row = None
        try:
            need(deadline_ns is None or type(deadline_ns) is int and 0 <= deadline_ns < (1 << 63),
                 'INVENTORY_ADMISSION_DEADLINE_REQUIRED')
            need(deadline_ns == self._inventory_deadline_ns, 'INVENTORY_ORIGINAL_DEADLINE_REQUIRED')
            need(self._inventory_restore_only is restore_only, 'INVENTORY_RESTORE_MODE_CHANGED')
            if continuation:
                row = previous[1][1][16]
                need(len(previous) == 5 and previous[3] is restore_only, 'INVENTORY_ORIGINAL_RESTORE_MODE_REQUIRED')
                operation_frame = previous[4]
                self._inventory_refusal_current(previous[0])
                need(row['writer'] is writer, 'INVENTORY_ORIGINAL_WRITER_REQUIRED')
            self._inventory_admission_time()
            rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
            need(len(rows) == 1, 'INVENTORY_CURRENT_CLAIM_REQUIRED')
            row, = rows
            operation_lock = row['operation_lock']
            # Capture real authority before waiting; never switch to a new selection.
            game = self.realm.registry.resolve(writer)
            registry, selected = self.realm.registry, game.selection
            movement = self.realm.service(writer)
            position = movement.snapshot()
            reader = service.reader
            retained = (reader.backend, reader.owner, reader.member, self.policy,
                        self.policy.owner, self.policy.handle, self.policy.job)
            async with operation_lock:
                need(row['operation_lock'] is operation_lock, 'INVENTORY_OPERATION_LOCK_CHANGED')
                need(self.realm.registry is registry and registry.resolve(writer) is game
                     and game.selection is selected and self.realm.service(writer) is movement
                     and movement.snapshot() is position, 'INVENTORY_AUTHORITY_CHANGED')
                need(all(a is b for a, b in zip(retained,
                    (reader.backend, reader.owner, reader.member, self.policy,
                     self.policy.owner, self.policy.handle, self.policy.job))),
                    'INVENTORY_AUTHORITY_CHANGED')
                self._inventory_operation_mode_current(restore_only, writer, row, operation_frame)
                self._inventory_selection_frame_current(writer, row, operation_frame)
                authority = service._current(writer, row)
                if previous is not None:
                    service._same(previous[1], authority)
                self._inventory_admission_time()
                await self._send(writer, row, (operation_frame,), game=True,
                                 inventory_service=service, inventory_authority=authority,
                                 inventory_restore_only=restore_only, operation_lock=operation_lock)
                if self._inventory_collection_policy is not None:
                    operation_frame = self._inventory_operation_frame
                    need(operation_frame is self._inventory_frame, 'INVENTORY_COLLECTION_EXACT_INITIAL_WIRE_REQUIRED')
                service._same(authority, service._current(writer, row))
                self._inventory_operation_mode_current(restore_only, writer, row, operation_frame)
                self._inventory_delivery_authority = authority
                need(self._inventory_current_frame is None, 'INVENTORY_INITIAL_CURRENT_ALREADY_SET')
                self._inventory_current_frame = operation_frame
                self._inventory_prewrite_refusal = None
            return dict(status='COMMITTED', command='AddInventory',
                        proof_scope='TRANSPORT_DRAIN_ONLY', client_inventory='UNKNOWN', invoked=True)
        except BaseException as error:
            evidence = self._inventory_prewrite_refusal
            if evidence is not None and evidence[0] is error:
                try:
                    self._inventory_refusal_current(error)
                except BaseException:
                    self._inventory_prewrite_refusal = None
                    service.close()
                    if row is not None:
                        row['failed'] = True
                        self._fail('INVENTORY_SEND_OUTCOME_UNKNOWN')
                    raise  # Preserve cancellation/fresh-authority failure from this checkpoint.
                else:
                    if (self._inventory_deadline_ns is not None
                            and not service._closed and not service._claimed
                            and not self._inventory_admission_expired
                            and (type(error) is inventory.ReadOnlyPreWriteRefusal
                                 or type(error) is inventory.PreWriteReadRefusal
                                 and re.fullmatch(r'CODE_GUARD_BEFORE_[0-9]{4}', error.stage))):
                        return dict(status='PENDING', command='AddInventory', phase='ADMISSION',
                            reason=('INVENTORY_READONLY_ADMISSION_WAIT'
                                    if type(error) is inventory.ReadOnlyPreWriteRefusal
                                    else 'INVENTORY_CODE_PAGE_ADMISSION_WAIT'), refusal_reason=error.reason,
                            stage=error.stage, invoked=False, write_attempted=False,
                            client_inventory='UNKNOWN')
                    service.close()
                    raise
            service.close()  # Includes pre-write refusal; this explicit operation never retries.
            if row is not None:
                row['failed'] = True
                self._fail('INVENTORY_SEND_OUTCOME_UNKNOWN')
            raise

    async def prepare_item_equipment(self, writer, *, policy, first_enable):
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        effect = self._item_equipment_effect
        need(type(effect) is ItemEquipmentEffect and type(policy) is str and policy == effect.policy and
             type(first_enable) is bool and first_enable is effect.first_enable,
             'EQUIPMENT_SAME_CONFIGURED_EFFECT_REQUIRED')
        need(effect.prepare_locked.__func__ is ItemEquipmentEffect.prepare_locked,
             'EQUIPMENT_ORIGINAL_PREPARE_REQUIRED')
        rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
        need(len(rows) == 1, 'EQUIPMENT_CURRENT_CLAIM_REQUIRED')
        async with rows[0]['operation_lock']:
            return await effect.prepare_locked(writer)

    def item_equipment_observation(self, writer, *, accepted_ordinal=None):
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        effect = self._item_equipment_effect
        need(type(effect) is ItemEquipmentEffect and effect.observation.__func__ is ItemEquipmentEffect.observation,
             'EQUIPMENT_ORIGINAL_OBSERVATION_REQUIRED')
        return effect.observation(writer, accepted_ordinal=accepted_ordinal)

    def _validate_inventory_update_reply(self, writer, wire):
        state = self._inventory_update_operation
        need(state is not None and wire is state['wire'] and state['writer'] is writer,
             'INVENTORY_UPDATE_EXACT_WIRE_REQUIRED')
        self._inventory_update_current(writer, state['row'], state)

    def _inventory_update_time(self, state):
        now = time.monotonic_ns()
        need(type(now) is int and state['last_ns'] <= now < state['deadline_ns'],
             'INVENTORY_UPDATE_OPERATION_DEADLINE')
        state['last_ns'] = now
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return now

    def _inventory_update_current(self, writer, row, state, request=None):
        from tools.local_original_session import inventory, inventory_update, observe
        from tools.local_original_session.inventory_store import InventoryStore
        request = state['request'] if request is None else request
        def original_request():
            need(state['request'] is request and state['old'] is request[0]
                 and state['new'] is request[1] and state['wire'] is request[2]
                 and state['changes'] is request[3] and state['refs'] is request[4]
                 and state['policy'] is request[5] and type(state['deadline_ns']) is int
                 and state['deadline_ns'] == request[6] and state['item_use'] is request[7]
                 and self._item_use_session is request[7] and self.realm._item_use_session is request[7],
                 'INVENTORY_UPDATE_ORIGINAL_REQUEST_REQUIRED')
        original_request()
        self._inventory_update_time(state)
        need(state is self._inventory_update_operation and state['writer'] is writer
             and state['row'] is row and state['lock'] is row['operation_lock'] and state['lock'].locked()
             and state['phase'] not in ('TERMINAL', 'DRAINED')
             and self.inventory_update_policy == INVENTORY_UPDATE_POLICY
             and self.policy.inventory_update is True, 'INVENTORY_UPDATE_CURRENT_OPERATION_REQUIRED')
        (realm, registry, game, mover, position, selected, service, reader, store,
         binding, delivery, initial, mode) = state['refs']
        for instance, cls, names in ((service, inventory.InventoryService,
                ('_current', '_authority', '_persistence_store')),
                (store, InventoryStore, ('restore', 'replace_existing'))):
            for name in names:
                method = getattr(instance, name)
                need(getattr(method, '__self__', None) is instance
                     and getattr(method, '__func__', None) is getattr(cls, name),
                     'INVENTORY_UPDATE_ORIGINAL_METHOD_REQUIRED')
        need(self.realm is realm and realm.registry is registry and registry.resolve(writer) is game
             and realm.service(writer) is mover and mover.snapshot() is position
             and game.selection is selected and registry.selected.get(position.name) is selected
             and self._inventory_service is service and type(service) is inventory.InventoryService
             and service.reader is reader and reader is service._reader and reader.backend is service._backend
             and type(store) is InventoryStore and self._inventory_store is store
             and service._persistence_store() is store and self._inventory_selection_binding is binding
             and self._inventory_delivery_authority is delivery
             and self._inventory_frame is initial and self._inventory_operation_frame is initial
             and self._inventory_current_frame is state['old'] and self._inventory_restore_only is mode
             and self._inventory_attempted is True and self._inventory_write_attempted is True
             and self._inventory_prewrite_refusal is None and self._inventory_admission_expired is False
             and service._claimed is True and not service._closed and not service._inflight,
             'INVENTORY_UPDATE_DELIVERED_SELECTION_REQUIRED')
        admitted = row['policy_row']
        if state['phase'] in ('RESERVING', 'WRITE_ATTEMPTED') and admitted.drain_started_ns is not None:
            need(admitted.pending_opcode == 0x0965 and admitted.pending_size == len(state['wire']),
                 'INVENTORY_UPDATE_CURRENT_RESERVATION_REQUIRED')
        else:
            need(admitted.drain_started_ns is None and admitted.pending_opcode is None
                 and admitted.pending_size == 0, 'INVENTORY_UPDATE_UNRESERVED_POLICY_REQUIRED')
        self._inventory_operation_mode_current(mode, writer, row, initial)
        self._inventory_selection_frame_current(writer, row, initial)
        self.source_guard()
        need(self.key_guard() is True, 'INVENTORY_UPDATE_RETAINED_OWNER_REQUIRED')
        observe.RetainedSceneReader.validate(reader)
        authority = inventory.InventoryService._current(service, writer, row)
        need(type(delivery) is tuple and len(delivery) == 3
             and len(delivery[1]) == len(authority[1]) == 24
             and all(a is b for index, (a, b) in enumerate(zip(delivery[1], authority[1])) if index != 14)
             and delivery[2] == authority[2]
             and (delivery[0].uid, delivery[0].name, delivery[0].map_id)
                 == (position.uid, position.name, position.map_id),
             'INVENTORY_UPDATE_INITIAL_DELIVERY_CHANGED')
        if state['authority'] is not None:
            inventory.InventoryService._same(state['authority'], authority)
        expected = state['new'] if state['persisted'] else state['old']
        need(InventoryStore.restore(store, position.uid) == expected,
             'INVENTORY_UPDATE_STORED_FRAME_CHANGED')
        inventory.validate_frame(state['old'])
        if state['new'] is not None:
            inventory.validate_frame(state['new'])
            inventory_update.validate_frame(state['wire'])
        self.source_guard()
        inventory.InventoryService._same(authority, inventory.InventoryService._current(service, writer, row))
        need(self._inventory_update_operation is state and self._inventory_service is service
             and self._inventory_store is store and service._persistence_store() is store
             and self._inventory_selection_binding is binding and self._inventory_delivery_authority is delivery
             and self._inventory_frame is initial and self._inventory_operation_frame is initial
             and self._inventory_current_frame is state['old'] and self._inventory_restore_only is mode,
             'INVENTORY_UPDATE_OPERATION_CHANGED')
        original_request()
        self._inventory_update_time(state)
        return authority

    async def update_inventory(self, writer, *, item_identifier, changes, policy, deadline_ns=None):
        """One explicit local opaque update; persistence precedes its one transport attempt."""
        from tools.local_original_session import inventory, inventory_update
        from tools.local_original_session.inventory_store import InventoryStore
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            need(self.inventory_selection_current(writer) is self._inventory_generation
                 and self._inventory_generation.phase == 'ACTIVE',
                 'INVENTORY_RESELECTION_UPDATE_ACTIVE_REQUIRED')
        need(type(policy) is str and policy == INVENTORY_UPDATE_POLICY
             and self.inventory_update_policy == policy and self.policy.inventory_update is True,
             'INVENTORY_UPDATE_EXPLICIT_POLICY_REQUIRED')
        need(type(changes) is dict and changes and all(type(k) is int for k in changes)
             and changes.keys() <= {4, 5, 7, 18}, 'INVENTORY_UPDATE_EXPLICIT_CHANGES_REQUIRED')
        frozen_changes = tuple(sorted(changes.items()))  # Scalars/bytes validated before the first await.
        old = self._inventory_current_frame
        old_item = inventory.validate_frame(old)
        need(type(item_identifier) is int and item_identifier == old_item.identifier,
             'INVENTORY_UPDATE_SAME_ITEM_REQUIRED')
        fields = dict(old_item.raw_fields)
        need(all(fields[k] != value for k, value in frozen_changes), 'INVENTORY_UPDATE_ACTUAL_CHANGE_REQUIRED')
        updated = dict(fields); updated.update(frozen_changes)
        new = inventory.build_add(updated)
        wire_fields = {1: item_identifier, **dict(frozen_changes)}
        wire = inventory_update.build_update(wire_fields)
        inventory_update.validate_frame(wire)
        need(new != old, 'INVENTORY_UPDATE_ACTUAL_CHANGE_REQUIRED')
        previous = self._inventory_update_operation
        need(previous is None or previous['phase'] == 'DRAINED', 'INVENTORY_UPDATE_OPERATION_PENDING_OR_TERMINAL')
        rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
        need(len(rows) == 1, 'INVENTORY_UPDATE_CURRENT_CLAIM_REQUIRED')
        row, = rows
        lock = row['operation_lock']
        game, mover = self.realm.registry.resolve(writer), self.realm.service(writer)
        service = self._inventory_service
        now = time.monotonic_ns()
        need(type(now) is int and 0 <= now < (1 << 63)
             and (deadline_ns is None or type(deadline_ns) is int and now < deadline_ns <= now + 10_000_000_000),
             'INVENTORY_UPDATE_ORIGINAL_DEADLINE_REQUIRED')
        state = dict(writer=writer, row=row, lock=lock, old=old, new=new, wire=wire,
            changes=frozen_changes, policy=policy, phase='CLAIMED', persisted=False,
            persist_attempted=False, write_attempted=False, drain_returned=False, post_owner_verified=False,
            item_use=self._item_use_session,
            sent_after=None, authority=None, sent_before=None, deadline_ns=now + 10_000_000_000 if deadline_ns is None else deadline_ns, last_ns=now,
            refs=(self.realm, self.realm.registry, game, mover, mover.snapshot(), game.selection,
                  service, service.reader, self._inventory_store, self._inventory_selection_binding,
                  self._inventory_delivery_authority, self._inventory_frame, self._inventory_restore_only))
        request = state['request'] = (old, new, wire, frozen_changes, state['refs'], policy, state['deadline_ns'], state['item_use'])
        self._inventory_update_operation = state
        try:
            async with self._row_operation(writer, row):
                state['authority'] = self._inventory_update_current(writer, row, state, request)
                state['sent_before'] = row['policy_row'].sent
                await self._checkpoint(writer, row)
                self._inventory_update_current(writer, row, state, request)
                self._inventory_update_time(state)
                owner = self._inventory_update_owner
                if owner is None:
                    state['phase'], state['persist_attempted'] = 'PERSISTING', True
                    need(InventoryStore.replace_existing(state['refs'][8], state['authority'][0].uid, old, new) is True,
                         'INVENTORY_UPDATE_PERSISTED_CHANGE_REQUIRED')
                else:
                    from tools.local_original_session.canonical_batch import OriginalUpdateOwner
                    need(type(owner) is OriginalUpdateOwner and owner.broker is self
                         and owner.provider is self._canonical_provider
                         and owner.store.source is state['refs'][8],
                         'INVENTORY_UPDATE_SAME_TYPED_OWNER_REQUIRED')
                    with owner.issued_locked(writer, state, request) as cap:
                        state['phase'], state['persist_attempted'] = 'PERSISTING', True
                        need(owner.store.replace_original_update_locked(cap) is True,
                             'INVENTORY_UPDATE_PERSISTED_CHANGE_REQUIRED')
                state['persisted'], state['phase'] = True, 'PERSISTED'
                self._inventory_update_current(writer, row, state, request)
                await self._send(writer, row, (wire,), game=True, operation_lock=lock,
                                 inventory_update_operation=state, inventory_update_request=request)
                self._inventory_update_current(writer, row, state, request)
                need(state['phase'] == 'WRITE_ATTEMPTED' and state['drain_returned'] is True
                     and state['post_owner_verified'] is True
                     and state['sent_after'] == state['sent_before'] + 1,
                     'INVENTORY_UPDATE_EXACT_DRAIN_REQUIRED')
                need(state['old'] is old and state['new'] is new and state['wire'] is wire
                     and state['changes'] is frozen_changes, 'INVENTORY_UPDATE_ORIGINAL_REQUEST_REQUIRED')
                if state['item_use'] is not None:
                    from tools.local_original_session.item_use_session import ItemUseSession
                    need(type(state['item_use']) is ItemUseSession, 'INVENTORY_UPDATE_REAL_ITEM_USE_SESSION_REQUIRED')
                    ItemUseSession.release(state['item_use'], writer)
                self._inventory_update_time(state)
                self._inventory_current_frame = new
                state['phase'] = 'DRAINED'
            return dict(status='COMMITTED', command='UpdateInventory', proof_scope='TRANSPORT_DRAIN_ONLY',
                        storage='LOCAL_OPAQUE_FRAME_REPLACED', client_inventory='UNKNOWN', invoked=True)
        except BaseException:
            state['phase'] = 'TERMINAL'
            if state['persist_attempted']:
                self._fail('INVENTORY_UPDATE_OUTCOME_UNKNOWN')
                row['failed'] = True
            else:
                self._inventory_update_operation = previous  # No write/IO attempt; ordinary refusal only.
            raise

    def _restart_current(self, writer, row, *, state=None, cleared=False, eof=False):
        """Actual current account/selection; no caller-supplied authorization."""
        from tools.local_original_session import restart
        need(self.restart_policy == restart.POLICY and self.policy.restart_enabled is True
             and not self._closing and not self.failure.is_set() and self.policy.state == 'OPEN',
             'RESTART_CURRENT_BROKER_REQUIRED')
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        policy_row = self.policy._connection(writer)
        need(len(claims) == 1 and claims[0] is row and row['writer'] is writer
             and row['policy_row'] is policy_row and policy_row.writer is writer
             and policy_row.stage == 1 and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
             and not any((row['failed'], row['joined'], policy_row.failed,
                          policy_row.task_joined, policy_row.registry_removed))
             and row['eof'] is eof and policy_row.eof is eof
             and row['operation_lock'].locked(), 'RESTART_CURRENT_ROW_REQUIRED')
        realm = self.realm
        need(type(realm) is LocalRealm and realm._restart_broker is self
             and not realm._settings_failed and id(writer) not in realm._quit,
             'RESTART_CURRENT_REALM_REQUIRED')
        game = realm.registry.resolve(writer)
        realm.bound_account(writer, game)
        if cleared:
            need(state is not None and row.get('_restart') is state and state['phase'] == 'DRAINED'
                 and state['selection_cleared'] is True, 'RESTART_DRAINED_STATE_REQUIRED')
            service, position, selected = state['binding'][0][8:11]
            need(game.selection is None and selected.reference not in realm.registry.selected
                 and all(id(writer) not in mapping for mapping in (
                     realm._movement, realm._world_frames, realm._npc_frames, realm._npc_motion)),
                 'RESTART_CLEARED_SELECTION_REQUIRED')
        else:
            service = realm.service(writer)
            position, selected = service.snapshot(), game.selection
            need(selected is not None and realm.registry.selected.get(position.name) is selected
                 and selected.reference == position.name, 'RESTART_CURRENT_SELECTION_REQUIRED')
        need(type(service) is movement.MovementService and service._connection is writer
             and not service.fatal and service.snapshot() is position
             and realm.store.select(selected.reference)[0] == position.uid
             and realm.positions.restore(position) == position, 'RESTART_COMMITTED_POSITION_REQUIRED')
        account = realm._account_bound[id(writer)]
        settings_store = realm.settings
        if settings_store is not None:
            need(type(settings_store) is settings.SettingsStore and not settings_store.failed,
                 'RESTART_CURRENT_SETTINGS_REQUIRED')
            record = settings_store._load()
            need((None if record is None else record.metadata()) == settings_store.last,
                 'RESTART_COMMITTED_SETTINGS_REQUIRED')
        objects = (self, self.policy, row, row['peer'], policy_row, policy_row.peer,
                   realm, game, service, position, selected, realm.registry, realm.store,
                   realm.positions, settings_store, account, game.roster, self.policy.owner,
                   self.source_guard, self.key_guard, self.owner_guard, self.owner_liveness_guard,
                   row['operation_lock'])
        values = tuple((type(v), v) for v in (self.policy.handle, self.policy.job,
            *row['peer'].keys(), *row['peer'].values(), policy_row.peer.port,
            policy_row.peer.client_port, policy_row.peer.accepted_ns,
            None if settings_store is None else settings_store.committed,
            *((settings_store.last or {}).keys() if settings_store is not None else ()),
            *((settings_store.last or {}).values() if settings_store is not None else ())))
        return objects, values

    @staticmethod
    def _restart_same(before, after):
        need(len(before[0]) == len(after[0]) and all(a is b for a, b in zip(before[0], after[0]))
             and before[1] == after[1], 'RESTART_AUTHORITY_CHANGED')

    def _validate_restart(self, writer, wire, *, phase):
        from tools.local_original_session import restart
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        need(len(claims) == 1, 'RESTART_CURRENT_ROW_REQUIRED')
        row = claims[0]
        state = row.get('_restart')
        need(state is not None and state['phase'] == phase and wire is state['frame']
             and type(wire) is bytes and row['operation_lock'] is state['lock'],
             'RESTART_CURRENT_FRAME_REQUIRED')
        need(restart.validate_ack(wire, policy=self.restart_policy) is True,
             'RESTART_EXPLICIT_SUCCESS_REQUIRED')
        self.source_guard()
        self.key_guard()
        self._restart_same(state['binding'], self._restart_current(writer, row))
        need(row.get('_restart') is state, 'RESTART_CURRENT_FRAME_REQUIRED')
        return row, state

    async def _prepare_restart(self, writer, payload):
        from tools.local_original_session import restart
        restart.parse_request(payload)
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        need(len(claims) == 1, 'RESTART_CURRENT_ROW_REQUIRED')
        row = claims[0]
        before = self._restart_current(writer, row)
        previous = row.get('_restart')
        need(previous is None or previous['phase'] == 'DRAINED', 'RESTART_PREVIOUS_OUTCOME_UNRESOLVED')
        frame = restart.build_ack(success=True, policy=self.restart_policy)
        state = dict(phase='PREPARING', frame=frame, binding=before,
                     lock=row['operation_lock'], write_attempted=False, drain_returned=False,
                     response_drained=False, selection_cleared=False)
        row['_restart'] = state
        try:
            need(row['policy_row'].drain_started_ns is None, 'RESTART_UNRESERVED_POLICY_REQUIRED')
            await self._checkpoint(writer, row)
            self._restart_same(before, self._restart_current(writer, row))
            need(row.get('_restart') is state, 'RESTART_CURRENT_FRAME_REQUIRED')
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            state['phase'] = 'PREPARED'
            return (frame,)
        except BaseException:
            state['phase'] = 'TERMINAL'
            raise

    def _restart_selection_drained(self, writer, row, state):
        self._restart_same(state['binding'], self._restart_current(writer, row))
        realm, game, service, position, selected = state['binding'][0][6:11]
        metadata = realm._movement_metadata(realm._movement[id(writer)], closed=True)
        mover = realm._npc_motion.get(id(writer))
        if mover is not None:
            need(mover[0] is writer, 'RESTART_SAME_NPC_MOVER_REQUIRED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        inventory_generation = None
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            inventory_generation = self.inventory_selection_current(writer)
            need(inventory_generation is not None and inventory_generation.row is row
                 and inventory_generation.lock.locked(), 'INVENTORY_RESELECTION_RETIRE_CURRENT_REQUIRED')
        if inventory_generation is not None and inventory_generation.transfer_session is not None:
            inventory_generation.transfer_session.release(writer)
        equipment_retirement = None
        canonical_provider = getattr(self, '_canonical_provider', None)
        effect = self._item_equipment_effect
        if effect is not None and type(effect._last) is dict and (
                effect._last.get('status'), effect._last.get('phase')) in (
                ('RESTORED_EMPTY', 'NO_NOTIFICATIONS'), ('RESTORED_UNEQUIPPED', 'NO_NOTIFICATIONS')):
            prepare_retirement = getattr(canonical_provider, 'prepare_zero_equipment_retirement', None)
            need(prepare_retirement is not None
                 and getattr(prepare_retirement, '__self__', None) is canonical_provider
                 and getattr(prepare_retirement, '__func__', None) is getattr(
                     type(canonical_provider), 'prepare_zero_equipment_retirement', None),
                 'EQUIPMENT_ZERO_RESTART_CANONICAL_CONSUMER_REQUIRED')
            equipment_retirement = prepare_retirement(writer, row, inventory_generation, state)
        # All fallible authority/storage/source checks precede this synchronous
        # selection-only cleanup. The real registered game/account are retained.
        if realm._item_use_session is not None:
            realm._item_use_session.release(writer)
        if realm._attack_session is not None:
            realm._attack_session.release(writer)
        life = getattr(self,'_player_life',None)
        life_broker = getattr(self,'_player_life_broker',None)
        if life is None and life_broker is not None: life = life_broker._player_life
        if life is not None: life.release(writer)
        player_hit = getattr(self, '_npc_player_hit', None)
        if player_hit is not None:
            player_hit.release(writer)
        status = getattr(self, '_hp_status', None)
        if status is not None:
            status.release(writer)
        realm._release_npc_motion(writer)
        realm._npc_frames.pop(id(writer), None)
        realm._world_frames.pop(id(writer), None)
        realm._movement.pop(id(writer))
        realm._movement_closed.append(metadata)
        realm.registry.selected.pop(selected.reference)
        game.selection = None
        state['phase'] = 'DRAINED'
        state['selection_cleared'] = True
        if inventory_generation is not None:
            inventory_generation.service.close()
            if inventory_generation.item_use_session is not None:
                inventory_generation.item_use_session.close()
            inventory_generation.restart_state = state
            inventory_generation.phase = 'RETIRED'
        if equipment_retirement is not None:
            finish, effect, token = equipment_retirement
            finish(effect, token)  # Original prevalidated memory-only source finisher.

    def _shop_trade_projection_drained(self,parent):
        from trade_delivery import TradeDelivery
        need(type(parent) is TradeDelivery and parent.service is getattr(self,'_shop_trade_delivery',None),
             'SHOP_EXACT_COMPLETE_GENERIC_PARENT')
        binding,before,after,revision=parent.service.materialization(parent)
        need(self._inventory_generation is binding.generation and binding.generation.phase=='ACTIVE'
             and self._inventory_current_frame==before and type(after) is bytes,
             'SHOP_CURRENT_GENERATION_FRAME_CAS')
        # Retire actual old Use intent. Initial collection/membership and
        # original Update authority are not rewritten or fabricated.
        if self._item_use_session is not None:self._item_use_session.release(binding.writer)
        # Recheck after the external owner release before the RAM CAS.
        binding,before,after,revision=parent.service.materialization(parent)
        need(self._inventory_generation is binding.generation and self._inventory_current_frame==before,
             'SHOP_POST_RELEASE_CURRENT_FRAME_CAS')
        self._inventory_current_frame=after
        need(binding.generation.current_frame is after,'SHOP_MATERIALIZED_CURRENT_FRAME')
        parent.service.record_adoption(parent)

    def _two_npc_selection_bundle(self, writer, row, replies, *, game, operation_lock):
        """원 선택의 현재 cache bundle에만 추가 NPC 한 frame을 허용한다."""
        realm = self.realm
        if not (game is True and len(replies) == 6 and realm.profile_uid == 1
                and tuple(spawn.uid for spawn,_ in realm._npc_spawns) == (2,3)
                and row['writer'] is writer and operation_lock is row['operation_lock']
                and operation_lock is not None and operation_lock.locked()):
            return False
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        if len(claims) != 1 or claims[0] is not row:
            return False
        motion = realm._movement.get(id(writer))
        bound = realm._npc_frames.get(id(writer))
        cached = realm._world_frames.get(id(writer))
        account = realm._account_bound.get(id(writer))
        if motion is None or bound is None or cached is None or account is None:
            return False
        selected_game, service = bound[1], bound[2]
        position = service.snapshot()
        if not (motion[0] is bound[0] is account[0] is writer
                and motion[1] is service and account[1] is selected_game
                and realm.registry.resolve(writer) is selected_game and selected_game.list_sent
                and selected_game.selection is not None
                and realm.registry.selected.get(position.name) is selected_game.selection
                and selected_game.selection.reference == position.name and position.uid == realm.profile_uid
                and cached[0] is position and len(cached[1]) == 3 and len(bound[3]) == 2
                and not service.fatal and not realm._settings_failed and id(writer) not in realm._quit):
            return False
        for (spawn,_),wire in zip(realm._npc_spawns,bound[3]):
            component = realm._npc_frames_by_uid.get((id(writer),spawn.uid))
            if not (component is not None and len(component[3]) == 1
                    and all(a is b for a,b in zip(component[:3],bound[:3]))
                    and component[3][0] is wire and spawn.map_id == position.map_id):
                return False
        expected = (ack.ENTER_ACK_FRAME,) + cached[1] + bound[3]
        return all(actual is source for actual,source in zip(replies,expected))

    async def _send(self, writer, row, replies, *, game=False, inventory_service=None,
                    inventory_authority=None, operation_lock=None, inventory_restore_only=False,
                    inventory_update_operation=None, inventory_update_request=None, equipment_operation=None,
                    npc_respawn_operation=None, status_operation=None, npc_player_hit_operation=None,
                    item_transfer_operation=None, player_life_operation=None, npc_player_lethal_operation=None,
                    skill_operation=None, dialogue_send_operation=None, trade_delivery_part=None, action_list_send_operation=None, retaliation_lease=None, continuous_lease=None, continuous_motion_lease=None, continuous_lethal_context=None):
        if continuous_lethal_context is not None:
            from tools.local_original_session import npc_continuous_retaliation
            npc_continuous_retaliation.validate_lethal(self,writer,row,continuous_lethal_context)
        if retaliation_lease is not None:
            from tools.local_original_session import npc_retaliation
            need(npc_player_hit_operation is not None and game is True and len(replies)==1,
                 'RETALIATION_ORIGINAL_SINGLE_HIT_SEND_REQUIRED')
            npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
        if continuous_lease is not None:
            from tools.local_original_session import npc_continuous_retaliation
            need(npc_player_hit_operation is not None and game is True and len(replies)==1,
                 'RETALIATION_ORIGINAL_SINGLE_HIT_SEND_REQUIRED')
            npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
        if continuous_motion_lease is not None:
            from tools.local_original_session import npc_continuous_retaliation
            need(game is True and len(replies)==1 and continuous_lease is retaliation_lease is None,
                 'CONTINUOUS_MOTION_SINGLE_FRAME_REQUIRED')
            npc_continuous_retaliation.validate_motion(self,writer,row,continuous_motion_lease,
                continuous_motion_lease.issuer.motion_step,replies[0])
        action=getattr(self,'_haction_list_feature',None) if action_list_send_operation is not None else None
        if action_list_send_operation is not None:
            need(action is not None and game is True and len(replies)==1
                 and operation_lock is row['operation_lock'] and operation_lock.locked()
                 and all(v is None for v in (trade_delivery_part,dialogue_send_operation,skill_operation,
                     inventory_service,inventory_authority,inventory_update_operation,inventory_update_request,
                     equipment_operation,npc_respawn_operation,status_operation,npc_player_hit_operation,
                     item_transfer_operation,player_life_operation,npc_player_lethal_operation)),
                 'HACTION_EXCLUSIVE_READONLY_ORIGINAL_SEND')
            action.validate(action_list_send_operation,writer,row,replies[0])
        trade_delivery=getattr(self,'_shop_trade_delivery',None) if trade_delivery_part is not None else None
        if trade_delivery_part is not None:
            need(trade_delivery is not None and game is True and len(replies)==1
                 and operation_lock is row['operation_lock'] and operation_lock.locked()
                 and all(value is None for value in (skill_operation,dialogue_send_operation,inventory_service,
                     inventory_authority,inventory_update_operation,inventory_update_request,equipment_operation,
                     npc_respawn_operation,status_operation,npc_player_hit_operation,item_transfer_operation,
                     player_life_operation,npc_player_lethal_operation)),'SHOP_EXCLUSIVE_GENERIC_INVENTORY_SEND')
            trade_delivery.validate(trade_delivery_part,writer,row,replies[0])
        if skill_operation is not None:
            from tools.local_original_session.skill_cost_delivery import CostDelivery
            need(type(skill_operation) is CostDelivery and skill_operation.owner is self._hp_resource_owner
                 and game is True and operation_lock is row['operation_lock']
                 and all(value is None for value in (inventory_service, inventory_update_operation,
                     equipment_operation, npc_respawn_operation, status_operation, npc_player_hit_operation,
                     item_transfer_operation, player_life_operation, npc_player_lethal_operation, dialogue_send_operation)),
                 'RESOURCE_EXCLUSIVE_ORIGINAL_SEND_OPERATION_REQUIRED')
            skill_operation.validate_batch(writer, row, replies)
        need(type(replies) in (tuple, list)
             and (len(replies) <= ack.realm.MAX_CHARACTERS + 2
                  or self._two_npc_selection_bundle(writer,row,replies,game=game,operation_lock=operation_lock)),
             'BOUNDED_ROUTE_REPLIES_REQUIRED')
        dialogue = getattr(self, '_dialogue_feature', None) if dialogue_send_operation is not None else None
        if dialogue_send_operation is not None:
            need(dialogue is not None and game is True and len(replies) == 1
                 and operation_lock is row['operation_lock'] and operation_lock.locked()
                 and all(value is None for value in (skill_operation, inventory_service, inventory_authority,
                     inventory_update_operation, inventory_update_request, equipment_operation,
                     npc_respawn_operation, status_operation, npc_player_hit_operation,
                     item_transfer_operation, player_life_operation, npc_player_lethal_operation)),
                 'DIALOGUE_EXCLUSIVE_ORIGINAL_LOCKED_SEND_REQUIRED')
            dialogue.validate(dialogue_send_operation, writer, row, replies[0])
        readonly=action if action is not None else dialogue
        readonly_operation=action_list_send_operation if action is not None else dialogue_send_operation
        transfer = self._inventory_generation.transfer_session if item_transfer_operation is not None else None
        if item_transfer_operation is not None:
            from tools.local_original_session.item_transfer_session import ItemTransferSession
            need(type(transfer) is ItemTransferSession and game is True and
                 operation_lock is row['operation_lock'] and operation_lock.locked() and
                 inventory_service is None and equipment_operation is None and inventory_update_operation is None,
                 'ITEM_TRANSFER_ORIGINAL_LOCKED_SEND_REQUIRED')
        life = getattr(self,'_player_life',None)
        if npc_player_lethal_operation is not None:
            from tools.local_original_session import npc_player_lethal
            lethal = self._npc_player_lethal
            need(type(lethal) is npc_player_lethal.Service
                 and type(npc_player_lethal_operation) is npc_player_lethal._Attack
                 and player_life_operation is None and npc_player_hit_operation is None
                 and status_operation is None and item_transfer_operation is None
                 and inventory_service is None and equipment_operation is None
                 and inventory_update_operation is None, 'NPC_LETHAL_EXCLUSIVE_SEND_OPERATION_REQUIRED')
            life,player_life_operation = lethal,npc_player_lethal_operation
        if player_life_operation is not None:
            need(life is not None and game is True and len(replies) == 1
                 and operation_lock is row['operation_lock'] and operation_lock.locked()
                 and status_operation is None, 'PLAYER_LIFE_ORIGINAL_LOCKED_SEND_REQUIRED')
            life.validate(writer,row,replies[0],player_life_operation,'PREPARED')
        elif life is not None and game and not (status_operation is not None and status_operation.life_context is not None):
            # Empty route replies (including the already-sent dead ACK) emit nothing.
            if replies and not all(type(wire) is bytes and wire in (QUIT_SUCCESS_FRAME,ALIVE_FRAME)
                                   for wire in replies):
                life.check_normal_locked(writer)
        status_service = getattr(self, '_hp_status', None)
        player_hit = getattr(self, '_npc_player_hit', None) if npc_player_hit_operation is not None else None
        if npc_player_hit_operation is not None:
            need(player_hit is not None and player_hit is self.realm._npc_player_hit and game is True
                 and len(replies) == 1 and operation_lock is row['operation_lock'] and operation_lock.locked(),
                 'NPC_PLAYER_HIT_ORIGINAL_LOCKED_SEND_REQUIRED')
            player_hit.validate_delivery(writer, row, replies[0], npc_player_hit_operation)
        world_status = (status_service.begin_world(writer, row, replies)
                        if game and status_service is not None and status_operation is None and skill_operation is None and readonly is None and trade_delivery is None else None)
        hp_source_read = None
        if self._hp_resource_owner is not None and status_operation is None and len(replies) == 1 and any(
                v is not None for v in (npc_player_hit_operation,npc_player_lethal_operation,player_life_operation)):
            hp_source_read = self._hp_resource_owner.begin_hp_source_read(writer,row,replies[0],
                npc=npc_player_hit_operation,lethal=npc_player_lethal_operation,
                life_delivery=player_life_operation if npc_player_lethal_operation is None else None)
        for wire in replies:
            feedback_service = feedback_intent = feedback_policy_row = None
            feedback_sent = None
            notification_service = notification_delivery = notification_policy_row = None
            notification_sent = None
            restart_state = restart_policy_row = None
            restart_sent = None
            try:
                status_sent = None
                status_drain_started = None
                if skill_operation is not None:
                    skill_operation.reserve(writer, row, wire)
                elif status_operation is not None:
                    need(status_service is not None and status_service is self.realm._hp_status
                         and game is True and len(replies) == 1
                         and operation_lock is row['operation_lock'] and operation_lock.locked()
                         and status_service.validate(writer, wire, phase='PREPARED') is status_operation,
                         'HP_STATUS_EXACT_SEND_CAPABILITY_REQUIRED')
                    status_sent = row['policy_row'].sent
                elif (game and int.from_bytes(wire[2:4], 'little') == 0x4e38
                      and status_service is not None and id(writer) in status_service._states):
                    raise ValueError('HP_STATUS_EXACT_SEND_CAPABILITY_REQUIRED')
                inventory_wire = inventory_service is not None
                effect_op = equipment_operation
                if effect_op is not None:
                    from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
                    effect = self._item_equipment_effect
                    need(type(effect) is ItemEquipmentEffect and effect.broker is self and
                         effect is self.realm._item_equipment_effect and
                         effect.validate_reply.__func__ is ItemEquipmentEffect.validate_reply and
                         effect.attempt.__func__ is ItemEquipmentEffect.attempt and
                         effect.drained.__func__ is ItemEquipmentEffect.drained,
                         'EQUIPMENT_ORIGINAL_SEND_CONSUMER_REQUIRED')
                    need(game is True and operation_lock is effect_op['lock'] and not inventory_wire and
                         inventory_update_operation is None and wire is effect_op['wire'], 'EQUIPMENT_EXACT_SEND_REQUIRED')
                    effect.validate_reply(writer, wire)
                update_state = inventory_update_operation
                if update_state is not None:
                    need(game is True and not inventory_wire and wire is update_state['wire']
                         and operation_lock is update_state['lock'], 'INVENTORY_UPDATE_EXACT_WIRE_REQUIRED')
                    self._inventory_update_current(writer, row, update_state, inventory_update_request)
                if game and int.from_bytes(wire[2:4], 'little') == 0x4e96 and self._npc_respawn is not None and self._npc_respawn._pending is not None:
                    need(npc_respawn_operation is self._npc_respawn._pending,
                         'NPC_RESPAWN_EXACT_SEND_CAPABILITY_REQUIRED')
                if npc_respawn_operation is not None:
                    need(game is True and not inventory_wire and effect_op is None and update_state is None
                         and operation_lock is row['operation_lock'] and operation_lock.locked()
                         and self._npc_respawn._pending is npc_respawn_operation,
                         'NPC_RESPAWN_ORIGINAL_LOCKED_SEND_REQUIRED')
                    self._npc_respawn.reserve(writer, row, wire)
                if inventory_wire:
                    from tools.local_original_session import inventory
                    need(game is True and type(inventory_service) is inventory.InventoryService
                         and inventory_service is self._inventory_service
                         and inventory_service.broker is self and self._inventory_attempted
                         and wire == self._inventory_frame, 'INVENTORY_EXPLICIT_FRAME_REQUIRED')
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                    self._inventory_items(wire)
                elif transfer is not None:
                    transfer.validate_wire(writer,row,wire,item_transfer_operation)
                elif game and status_operation is not None and status_operation.life_context is not None:
                    status_service.validate(writer,wire,phase='PREPARED')
                elif game and player_life_operation is not None:
                    life.validate(writer,row,wire,player_life_operation,'PREPARED')
                elif skill_operation is not None:
                    pass  # Exact preflighted source wire is validated by the concrete parent.
                elif trade_delivery is not None:
                    trade_delivery.validate(trade_delivery_part,writer,row,wire)
                elif readonly is not None:
                    readonly.validate(readonly_operation, writer, row, wire)
                elif game:
                    self.realm.validate_reply(wire, writer=writer)
                else:
                    need(type(wire) in (bytes, bytearray) and len(wire) >= 6
                         and int.from_bytes(wire[:2], 'little') == len(wire)
                         and wire[-2:] == b'\0\0', 'SOURCE_BOOT_REPLY_REQUIRED')
                    op = int.from_bytes(wire[2:4], 'little')
                    need((op == 0x4e35 and type(wire) is bytearray and len(wire) == 76)
                         or (op == 0x4f3e and wire == EMPTY_COUNTS), 'EXACT_BOOT_REPLY_REQUIRED')
                if player_life_operation is not None:
                    life.reserve(writer,row,wire,player_life_operation)
                if player_life_operation is None and transfer is None and game and int.from_bytes(wire[2:4], 'little') in (0x4e39, 0x4e40):
                    notification_service = self._attack_session._notifications
                    actual_row, record, notification_delivery = notification_service.reserve(writer, wire)
                    need(actual_row is row and operation_lock is row['operation_lock']
                         and operation_lock is record.entry.lock and operation_lock.locked(),
                         'NPC_DEATH_SAME_ROW_LOCK_REQUIRED')
                    notification_policy_row, notification_sent = row['policy_row'], row['policy_row'].sent
                if player_hit is not None and npc_player_hit_operation.phase == 'ATTACK':
                    player_hit.reserve(writer, row, wire, npc_player_hit_operation)
                if game and int.from_bytes(wire[2:4], 'little') == ATTACK_FEEDBACK and player_hit is None and npc_player_lethal_operation is None:
                    feedback_service = self._attack_session
                    need(feedback_service is not None and feedback_service is self.realm._attack_session,
                         'ATTACK_FEEDBACK_SAME_SERVICE_REQUIRED')
                    feedback_intent = feedback_service.validate_feedback(writer, wire, state='PREPARED')
                    need(feedback_service._feedback_row is row
                         and operation_lock is feedback_service._feedback_lock
                         and row['operation_lock'] is operation_lock and operation_lock.locked(),
                         'ATTACK_FEEDBACK_SAME_ROW_LOCK_REQUIRED')
                    feedback_policy_row = row['policy_row']
                    feedback_sent = feedback_policy_row.sent
                    feedback_service.reserve_feedback(writer, wire)
                if status_operation is not None:
                    status_service.reserve(writer, wire)
                if game and int.from_bytes(wire[2:4], 'little') == RESTART_ACK:
                    actual_row, restart_state = self._validate_restart(writer, wire, phase='PREPARED')
                    need(actual_row is row and operation_lock is restart_state['lock']
                         and operation_lock is row['operation_lock'] and operation_lock.locked(),
                         'RESTART_SAME_OPERATION_LOCK_REQUIRED')
                    restart_policy_row = row['policy_row']
                    restart_sent = restart_policy_row.sent
                    restart_state['phase'] = 'RESERVED'
                row['await_phase'] = 'WRITE_CHECKPOINT'
                sample = await self._checkpoint(writer, row)
                if skill_operation is not None:
                    skill_operation.before_write_checkpoint(writer, row, wire)
                if player_life_operation is not None:
                    life.validate(writer,row,wire,player_life_operation,'RESERVED')
                elif life is not None and game and not (status_operation is not None and status_operation.life_context is not None):
                    if not (type(wire) is bytes and wire in (QUIT_SUCCESS_FRAME,ALIVE_FRAME)):
                        life.check_normal_locked(writer)
                if player_hit is not None:
                    player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                    if retaliation_lease is not None:
                        from tools.local_original_session import npc_retaliation
                        npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                    if continuous_lease is not None:
                        from tools.local_original_session import npc_continuous_retaliation
                        npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                opcode = int.from_bytes(wire[2:4], 'little')
                if update_state is not None:
                    self._inventory_update_current(writer, row, update_state, inventory_update_request)
                if inventory_wire:
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                    need(inventory_service is self._inventory_service and wire == self._inventory_frame,
                         'INVENTORY_EXPLICIT_FRAME_REQUIRED')
                    self._inventory_selection_frame_current(writer, row, wire)
                    inventory_service._same(inventory_authority, inventory_service._current(writer, row))
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                    self.inventory_sample_monotonic_ns = self._inventory_admission_time()
                    try:
                        prepared_wire = inventory_service.validate_pre_write_locked(writer, row, wire,
                            now_ns=self.inventory_sample_monotonic_ns)
                        if self._inventory_collection_policy is not None:
                            need(type(prepared_wire) is bytes and prepared_wire is self._inventory_frame
                                 and prepared_wire is self._inventory_operation_frame
                                 and inventory_service._claimed is True
                                 and inventory_service.last_result.get('status') == 'OBSERVED',
                                 'INVENTORY_COLLECTION_EXACT_INITIAL_WIRE_REQUIRED')
                            wire = prepared_wire
                            self._inventory_selection_frame_current(writer, row, wire)
                    except (inventory.PreWriteReadRefusal, inventory.ReadOnlyPreWriteRefusal) as error:
                        # Only the original leaf's exact refusal precedes reservation/write.
                        readonly = type(error) is inventory.ReadOnlyPreWriteRefusal
                        if readonly:
                            need(inventory.InventoryService.validate_readonly_refusal(
                                inventory_service, error, writer, row, wire) is True,
                                'INVENTORY_READONLY_REFUSAL_UNPROVEN')
                        else:
                            need(type(error) is inventory.PreWriteReadRefusal
                                 and error.reason == 'region_not_readable'
                                 and error.stage == inventory_service.last_pre_write_stage,
                                 'INVENTORY_PRE_WRITE_REFUSAL_UNPROVEN')
                        need(row['policy_row'].drain_started_ns is None,
                             'INVENTORY_PRE_WRITE_REFUSAL_UNPROVEN')
                        inventory_service._same(inventory_authority, inventory_service._current(writer, row))
                        await self._checkpoint(writer, row)
                        inventory_service._same(inventory_authority, inventory_service._current(writer, row))
                        need(row['policy_row'].drain_started_ns is None,
                             'INVENTORY_PRE_WRITE_REFUSAL_UNPROVEN')
                        task = asyncio.current_task()
                        if task is not None and task.cancelling():
                            raise asyncio.CancelledError()
                        self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                        if readonly:
                            need(inventory.InventoryService.validate_readonly_refusal(
                                inventory_service, error, writer, row, wire) is True,
                                'INVENTORY_READONLY_REFUSAL_UNPROVEN')
                        self._inventory_prewrite_refusal = (error, inventory_authority, inventory_service,
                                                           inventory_restore_only, wire)
                        self._inventory_admission_time()
                        raise
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                    self._inventory_prewrite_refusal = None  # A successful leaf consumes admission.
                    self._inventory_admission_time()
                # A checkpoint awaits native ownership; selection/realm lifetime
                # can change there. Recheck opt-in NPC authority at the write.
                if game and opcode == 0x4e96 and any(
                        wire == prepared for _, prepared in self.realm._npc_spawns):
                    self.realm._validate_npc_reply(writer, wire)
                if game and opcode == npc_motion.OPCODE:
                    self.realm.npc_motion_for_frame(writer,wire).validate_frame(wire)
                if feedback_service is not None:
                    need(feedback_service is self._attack_session
                         and feedback_service.validate_feedback(writer, wire, state='RESERVED') is feedback_intent
                         and row['policy_row'] is feedback_policy_row,
                         'ATTACK_FEEDBACK_SAME_SERVICE_INTENT_REQUIRED')
                if restart_state is not None:
                    actual_row, actual_state = self._validate_restart(writer, wire, phase='RESERVED')
                    need(actual_row is row and actual_state is restart_state
                         and row['policy_row'] is restart_policy_row, 'RESTART_AUTHORITY_CHANGED')
                if update_state is not None:
                    need(update_state['phase'] == 'PERSISTED' and wire is update_state['wire'],
                         'INVENTORY_UPDATE_EXACT_WIRE_REQUIRED')
                    update_state['phase'] = 'RESERVING'
                if effect_op is not None:
                    need(effect_op['phase'] == 'PERSISTED', 'EQUIPMENT_PERSISTED_SEND_REQUIRED')
                    effect_op['phase'] = 'RESERVING'
                if inventory_wire and getattr(self, '_inventory_owner_guard', None) is not None:
                    sample = self._inventory_owner_checkpoint_sync(writer, row, inventory_service,
                        inventory_authority, wire, inventory_restore_only, operation_lock)
                if transfer is not None:
                    context = transfer.validate_wire(writer,row,wire,item_transfer_operation)
                    sample = self._inventory_owner_checkpoint_sync(writer,row,context.inventory_service,
                        context.authority,wire,True,operation_lock,item_transfer_operation=item_transfer_operation)
                self.policy._skill_write_operation = skill_operation
                if trade_delivery is not None:
                    self._policy_sample(row,self.policy.begin_write,writer,sample,opcode,len(wire),
                        writer.transport.get_write_buffer_size(),time.monotonic_ns(),trade_delivery_part=trade_delivery_part)
                    trade_delivery.reserved(trade_delivery_part,writer,row,wire)
                elif readonly is not None:
                    self._policy_sample(row, self.policy.begin_write, writer, sample, opcode, len(wire),
                        writer.transport.get_write_buffer_size(), time.monotonic_ns(),
                        **({"action_list_send_operation":readonly_operation} if action is not None
                           else {"dialogue_send_operation":readonly_operation}))
                    readonly.reserved(readonly_operation, writer, row, wire)
                else:
                    self._policy_sample(row, self.policy.begin_write, writer, sample, opcode, len(wire),
                                            writer.transport.get_write_buffer_size(), time.monotonic_ns())
                if update_state is not None:
                    self._inventory_update_current(writer, row, update_state, inventory_update_request)
                    need(update_state['phase'] == 'RESERVING' and not update_state['write_attempted']
                         and wire is update_state['wire']
                         and row['policy_row'].pending_opcode == 0x0965
                         and row['policy_row'].pending_size == len(wire)
                         and row['policy_row'].drain_started_ns is not None,
                         'INVENTORY_UPDATE_SINGLE_WRITE_REQUIRED')
                    self._inventory_update_time(update_state)
                    update_state['phase'], update_state['write_attempted'] = 'WRITE_ATTEMPTED', True
                if inventory_wire:
                    # Synchronous policy/source callbacks may cancel without yielding.
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                    need(inventory_service is self._inventory_service and wire == self._inventory_frame,
                         'INVENTORY_EXPLICIT_FRAME_REQUIRED')
                    inventory_service._same(inventory_authority, inventory_service._current(writer, row))
                    self._inventory_selection_frame_current(writer, row, wire)
                    task = asyncio.current_task()
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError()
                if inventory_wire:
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                    self._inventory_admission_time()
                    self._inventory_write_attempted = True
                if feedback_service is not None:
                    # Final source/current-target validation follows synchronous
                    # policy callbacks, then cancel/once-mark without an await.
                    need(feedback_service is self._attack_session
                         and feedback_service._feedback_intent is feedback_intent
                         and row['policy_row'] is feedback_policy_row,
                         'ATTACK_FEEDBACK_SAME_SERVICE_INTENT_REQUIRED')
                    feedback_service.feedback_attempt(writer, wire)
                if restart_state is not None:
                    actual_row, actual_state = self._validate_restart(writer, wire, phase='RESERVED')
                    need(actual_row is row and actual_state is restart_state
                         and row['policy_row'] is restart_policy_row, 'RESTART_AUTHORITY_CHANGED')
                    task = asyncio.current_task()
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError()
                    restart_state['phase'] = 'WRITE_ATTEMPTED'
                    restart_state['write_attempted'] = True
                if effect_op is not None:
                    effect.attempt(writer, row, effect_op)
                if notification_service is not None:
                    actual_row, record, actual_delivery = notification_service.attempt(writer, wire)
                    need(actual_row is row and actual_delivery is notification_delivery
                         and row['policy_row'] is notification_policy_row
                         and operation_lock is row['operation_lock'] is record.entry.lock,
                         'NPC_DEATH_SAME_PENDING_SEND_REQUIRED')
                if npc_respawn_operation is not None:
                    self._npc_respawn.attempt(writer, row, wire)
                if hp_source_read is not None:
                    hp_source_read.consume('BEGIN_WRITE')
                    hp_read_owner = self._hp_resource_owner
                    hp_read_policy_row = row['policy_row']
                    hp_read_sent = hp_read_policy_row.sent
                    hp_read_drain_started = hp_read_policy_row.drain_started_ns
                if player_hit is not None:
                    player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                    if retaliation_lease is not None:
                        from tools.local_original_session import npc_retaliation
                        npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                    if continuous_lease is not None:
                        from tools.local_original_session import npc_continuous_retaliation
                        npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                    if npc_player_hit_operation.phase == 'ATTACK':
                        player_hit.attempt(writer, row, wire, npc_player_hit_operation)
                if status_operation is not None:
                    status_drain_started = row['policy_row'].drain_started_ns
                    status_service.attempt(writer, wire)
                    if player_hit is not None:
                        player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                        if retaliation_lease is not None:
                            from tools.local_original_session import npc_retaliation
                            npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                        if continuous_lease is not None:
                            from tools.local_original_session import npc_continuous_retaliation
                            npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                        npc_player_hit_operation.hp_transport = 'WRITE_ATTEMPTED'
                        player_hit.remember(npc_player_hit_operation)
                if world_status is not None:
                    status_service.validate_world_pending(writer, row, replies, wire, world_status)
                if transfer is not None:
                    transfer.attempt(writer,row,wire,item_transfer_operation)
                if player_life_operation is not None:
                    life.attempt(writer,row,wire,player_life_operation)
                if skill_operation is not None:
                    skill_operation.attempt(writer, row, wire)
                if readonly is not None:
                    readonly.attempt(readonly_operation, writer, row, wire)
                if retaliation_lease is not None:
                    need(player_hit is not None and npc_player_hit_operation is not None, 'RETALIATION_HIT_SEND_ONLY_REQUIRED')
                    npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                if continuous_lease is not None:
                    need(player_hit is not None and npc_player_hit_operation is not None, 'RETALIATION_HIT_SEND_ONLY_REQUIRED')
                    npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                if continuous_motion_lease is not None:
                    npc_continuous_retaliation.validate_motion(self,writer,row,continuous_motion_lease,
                        continuous_motion_lease.issuer.motion_step,wire)
                if continuous_lethal_context is not None:
                    npc_continuous_retaliation.validate_lethal(self,writer,row,continuous_lethal_context)
                if trade_delivery is not None:trade_delivery.write(trade_delivery_part,writer,row,wire)
                else:writer.write(wire)
                row['await_phase'] = 'WRITE_DRAIN' 
                await asyncio.wait_for(writer.drain(), self.policy.DRAIN_NS / 1e9)
                if trade_delivery is not None:
                    trade_delivery.validate(trade_delivery_part,writer,row,wire,'DRAIN_PENDING')
                if hp_source_read is not None: hp_source_read.consume('DRAIN_PENDING')
                hp_owner = self._hp_resource_owner
                if status_operation is not None and hp_owner is not None and hp_owner._hp_effect is not None:
                    hp_owner._hp_effect.drain_returned()
                if world_status is not None:
                    world_status['resource_drain_returned'] = True
                if skill_operation is not None:
                    skill_operation.drain_returned(writer, row, wire)
                if readonly is not None:
                    readonly.validate(readonly_operation, writer, row, wire)
                if player_life_operation is not None: player_life_operation.drain_returned = True
                if effect_op is not None:
                    effect_op['receipt']['drain_returned'] = True
                if inventory_wire:
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                if update_state is not None:
                    update_state['drain_returned'] = True
                    self._inventory_update_current(writer, row, update_state, inventory_update_request)
                queued = writer.transport.get_write_buffer_size()
                if restart_state is not None:
                    restart_state['drain_returned'] = True
                quit_reply = game and wire == QUIT_SUCCESS_FRAME
                if quit_reply:
                    self.realm.quit_response_drained(writer, wire, queued)
                if transfer is not None:
                    # Full source/Store validation precedes the fresh owner
                    # await; only bound refs/reservation are checked afterwards.
                    transfer.validate_wire(writer,row,wire,item_transfer_operation)
                try:
                    row['await_phase'] = 'POST_DRAIN_OWNER'
                    sample = await self._sample(row)
                    if readonly is not None:
                        readonly.validate(readonly_operation, writer, row, wire)
                except ValueError as error:
                    if not quit_reply or error.args != ('CURRENT_OWNER_REQUIRED',):
                        raise
                    proof = await self._quit_exit(writer, row)
                    self.policy.quit_drained_after_exit(writer, proof=proof, queued_bytes=queued,
                                                       now=time.monotonic_ns())
                else:
                    if skill_operation is not None:
                        while True:
                            skill_operation.validate_pending_drain(writer, row, wire)
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            need(type(queued) is int and 0 <= queued <= self.policy.WRITE_HIGH,
                                 'RESOURCE_CURRENT_DRAIN_QUEUE_REQUIRED')
                            if queued == 0:
                                break
                            await asyncio.sleep(0)
                            sample = await self._sample(row)
                    if world_status is not None:
                        # Reuse the original NPC/equipment conditional drain
                        # progress: one reservation, original deadline, no resend.
                        while True:
                            need(operation_lock is row['operation_lock'] and operation_lock.locked(),
                                 'HP_STATUS_SAME_WORLD_RESERVATION_REQUIRED')
                            status_service.validate_world_pending(writer, row, replies, wire, world_status)
                            sample = await self._sample(row, synchronous_exact=True)
                            sample = await self._world_post_drain_checkpoint(writer, row, sample)
                            queued = writer.transport.get_write_buffer_size()
                            need(type(queued) is int and 0 <= queued <= self.policy.WRITE_HIGH,
                                 'HP_STATUS_WORLD_CURRENT_QUEUE_REQUIRED')
                            if queued == 0:
                                break
                            await asyncio.sleep(0)
                            sample = await self._sample(row)
                    if status_operation is not None:
                        while True:
                            need(operation_lock is row['operation_lock'] and operation_lock.locked()
                                 and row['policy_row'].pending_opcode == opcode
                                 and row['policy_row'].pending_size == len(wire)
                                 and row['policy_row'].drain_started_ns == status_drain_started
                                 and row['policy_row'].sent == status_sent
                                 and status_service.validate(writer, wire, phase='WRITE_ATTEMPTED') is status_operation,
                                 'HP_STATUS_SAME_PENDING_DRAIN_REQUIRED')
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            need(type(queued) is int and 0 <= queued <= self.policy.WRITE_HIGH,
                                 'HP_STATUS_CURRENT_DRAIN_QUEUE_REQUIRED')
                            if queued == 0:
                                break
                            await asyncio.sleep(0)
                            sample = await self._sample(row)
                    if effect_op is not None:
                        # StreamWriter.drain may return below the transport's
                        # low-water mark while this exact write is still queued.
                        # The prior queued value predates the owner await: only
                        # a fresh post-owner zero completes equipment delivery.
                        while True:
                            need(operation_lock is row['operation_lock'] is effect_op['lock']
                                 and operation_lock.locked() and equipment_operation is effect_op
                                 and effect_op['phase'] == 'WRITE_ATTEMPTED'
                                 and wire is effect_op['wire']
                                 and row['policy_row'].pending_opcode == opcode
                                 and row['policy_row'].pending_size == len(wire)
                                 and row['policy_row'].drain_started_ns is not None,
                                 'EQUIPMENT_SAME_PENDING_DRAIN_REQUIRED')
                            # Original owner/freshness/deadline checks retain
                            # the original reservation's DRAIN_NS, never reset.
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            need(type(queued) is int and 0 <= queued <= self.policy.WRITE_HIGH,
                                 'EQUIPMENT_CURRENT_DRAIN_QUEUE_REQUIRED')
                            if queued == 0:
                                break
                            await asyncio.sleep(0)  # Conditional progress only; no write/drain replay.
                            sample = await self._sample(row)
                    if transfer is not None:
                        while True:
                            transfer.validate_write_binding(writer,row,wire,item_transfer_operation)
                            need(transfer._wire_phase == 'WRITE_ATTEMPTED' and
                                 row['policy_row'].drain_started_ns == transfer._drain_started and
                                 row['policy_row'].sent == transfer._sent_before,
                                 'ITEM_TRANSFER_SAME_PENDING_DRAIN_REQUIRED')
                            self._policy_sample(row,self.policy.checkpoint,writer,sample,time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            need(type(queued) is int and 0 <= queued <= self.policy.WRITE_HIGH,
                                 'ITEM_TRANSFER_CURRENT_QUEUE_REQUIRED')
                            if queued == 0:break
                            await asyncio.sleep(0)
                            sample = await self._sample(row)
                    if notification_service is not None:
                        while True:
                            need(operation_lock is row['operation_lock'] is record.entry.lock
                                 and notification_delivery.phase == 'WRITE_ATTEMPTED'
                                 and row['policy_row'] is notification_policy_row
                                 and notification_policy_row.pending_opcode == opcode
                                 and notification_policy_row.pending_size == len(wire)
                                 and notification_policy_row.drain_started_ns is not None,
                                 'NPC_DEATH_SAME_PENDING_DRAIN_REQUIRED')
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            need(type(queued) is int and 0 <= queued <= self.policy.WRITE_HIGH,
                                 'NPC_DEATH_CURRENT_QUEUE_REQUIRED')
                            if queued == 0:
                                break
                            await asyncio.sleep(0)  # Same reservation; no write/drain/deadline replay.
                            sample = await self._sample(row)
                    if hp_source_read is not None:
                        # drain() can return below low-water while this exact
                        # frame remains queued. Keep its original reservation
                        # until the current zero queue proves AFTER_DRAIN.
                        while True:
                            need(operation_lock is row['operation_lock'] and operation_lock.locked()
                                 and self._hp_resource_owner is hp_read_owner
                                 and row['policy_row'] is hp_read_policy_row
                                 and hp_read_policy_row.pending_opcode == opcode
                                 and hp_read_policy_row.pending_size == len(wire)
                                 and hp_read_policy_row.drain_started_ns == hp_read_drain_started
                                 and hp_read_policy_row.sent == hp_read_sent,
                                 'RESOURCE_HP_SAME_PENDING_DRAIN_REQUIRED')
                            hp_source_read.consume('DRAIN_PENDING')
                            self._policy_sample(row,self.policy.checkpoint,writer,sample,time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            need(type(queued) is int and 0 <= queued <= self.policy.WRITE_HIGH,
                                 'RESOURCE_HP_CURRENT_DRAIN_QUEUE_REQUIRED')
                            if queued == 0: break
                            await asyncio.sleep(0)  # Same reservation/deadline; never resend.
                            sample = await self._sample(row)
                    if player_hit is not None:
                        player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                        if retaliation_lease is not None:
                            from tools.local_original_session import npc_retaliation
                            npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                        if continuous_lease is not None:
                            from tools.local_original_session import npc_continuous_retaliation
                            npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                    if trade_delivery is not None:
                        sample,queued=await trade_delivery.queue_zero(trade_delivery_part,writer,row,wire,sample)
                    if readonly is not None:
                        sample, queued = await readonly.queue_zero(readonly_operation, writer, row, wire, sample)
                    self._policy_sample(row, self.policy.drained, writer, sample, queued, time.monotonic_ns())
                    if hp_source_read is not None: hp_source_read.consume('AFTER_DRAIN')
                    if trade_delivery is not None:
                        trade_delivery.drained(trade_delivery_part,writer,row,wire,queued)
                    if readonly is not None:
                        readonly.drained(readonly_operation, writer, row, wire, queued)
                    if quit_reply and queued == 0:
                        self.policy.mark_quit_drained(writer)
                if skill_operation is not None:
                    skill_operation.drained(writer, row, wire, queued)
                if inventory_wire:
                    self._inventory_operation_mode_current(inventory_restore_only, writer, row, wire)
                if update_state is not None:
                    self._inventory_update_current(writer, row, update_state, inventory_update_request)
                    need(queued == 0 and row['policy_row'].drain_started_ns is None
                         and row['policy_row'].pending_opcode is None
                         and row['policy_row'].sent == update_state['sent_before'] + 1
                         and wire is update_state['wire'], 'INVENTORY_UPDATE_EXACT_DRAIN_REQUIRED')
                    update_state['sent_after'] = row['policy_row'].sent
                    update_state['post_owner_verified'] = True
                if transfer is not None:
                    transfer.drained(writer,row,wire,item_transfer_operation,queued)
                if effect_op is not None:
                    effect.drained(writer, row, effect_op, queued)
                if feedback_service is not None:
                    need(feedback_service is self._attack_session
                         and feedback_service._feedback_intent is feedback_intent
                         and row['policy_row'] is feedback_policy_row
                         and queued == 0 and feedback_policy_row.drain_started_ns is None
                         and feedback_policy_row.pending_opcode is None
                         and feedback_policy_row.sent == feedback_sent + 1,
                         'ATTACK_FEEDBACK_EXACT_DRAIN_REQUIRED')
                    feedback_service.feedback_drain(writer, wire)
                    if getattr(self,'_npc_continuous',None) is not None:
                        from tools.local_original_session import npc_continuous_retaliation
                        npc_continuous_retaliation.feedback_drained(self,writer,row,feedback_service,
                            feedback_intent,wire,now_ns=time.monotonic_ns())
                    await self._npc_death_after_feedback_locked(writer, row, feedback_intent)
                if notification_service is not None:
                    need(notification_service is self._attack_session._notifications
                         and row['policy_row'] is notification_policy_row and queued == 0
                         and notification_policy_row.drain_started_ns is None
                         and notification_policy_row.pending_opcode is None
                         and notification_policy_row.sent == notification_sent + 1,
                         'NPC_DEATH_EXACT_DRAIN_REQUIRED')
                    notification_service.drained(writer, wire)
                if player_hit is not None and npc_player_hit_operation.phase == 'ATTACK':
                    player_hit.drained(writer, row, wire, npc_player_hit_operation)
                if status_operation is not None:
                    need(queued == 0 and row['policy_row'].pending_opcode is None
                         and row['policy_row'].drain_started_ns is None
                         and row['policy_row'].sent == status_sent + 1,
                         'HP_STATUS_EXACT_DRAIN_REQUIRED')
                    status_service.drained(writer, wire)
                    if player_hit is not None:
                        player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                        if retaliation_lease is not None:
                            from tools.local_original_session import npc_retaliation
                            npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                        if continuous_lease is not None:
                            from tools.local_original_session import npc_continuous_retaliation
                            npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                        npc_player_hit_operation.hp_transport = 'DRAINED'
                        player_hit.remember(npc_player_hit_operation)
                if restart_state is not None:
                    actual_row, actual_state = self._validate_restart(writer, wire, phase='WRITE_ATTEMPTED')
                    need(actual_row is row and actual_state is restart_state
                         and row['policy_row'] is restart_policy_row and queued == 0
                         and restart_policy_row.drain_started_ns is None
                         and restart_policy_row.pending_opcode is None
                         and restart_policy_row.sent == restart_sent + 1, 'RESTART_EXACT_DRAIN_REQUIRED')
                    task = asyncio.current_task()
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError()
                    restart_state['response_drained'] = True
                    self._restart_selection_drained(writer, row, restart_state)
                if npc_respawn_operation is not None:
                    self._npc_respawn.drained(writer, row, wire, queued)
                if quit_reply:
                    self.realm.quit_state(writer)['response_drained'] = queued == 0
                if npc_respawn_operation is None and game and opcode == 0x4e96 and id(writer) in self.realm._npc_motion and any(
                        wire == prepared for _, prepared in self.realm._npc_spawns):
                    matched=[spawn.uid for spawn,prepared in self.realm._npc_spawns if wire==prepared]
                    need(len(matched)==1,'NPC_SPAWN_EXACT_DRAINED_UID_REQUIRED')
                    self.realm.npc_mover(writer,target_uid=matched[0]).spawn_drained = True
                if player_life_operation is not None:
                    life.drained(writer,row,wire,player_life_operation)
                if world_status is not None:
                    status_service.world_frame_drained(writer, row, wire, world_status, queued)
            except BaseException as error:
                if hp_source_read is not None and hasattr(hp_source_read,'failed'):
                    try: hp_source_read.failed(error)
                    except BaseException: pass
                hp_owner = self._hp_resource_owner
                if status_operation is not None and hp_owner is not None and hp_owner._hp_effect is not None:
                    try: hp_owner._hp_effect.failed(error)
                    except BaseException: pass  # Preserve original send/cancel exception.
                if skill_operation is not None:
                    skill_operation.failed(error)
                if player_life_operation is not None: life.terminal(writer)
                if player_hit is not None:
                    player_hit.terminal(npc_player_hit_operation)
                if status_service is not None and (world_status is not None or status_operation is not None):
                    status_service.release(writer)
                if notification_service is not None:
                    self._attack_session.fail()
                if restart_state is not None:
                    restart_state['phase'] = 'TERMINAL'
                if feedback_service is not None:
                    feedback_service.fail()  # Once-only ambiguous/cancelled frame is terminal.
                raise
            finally:
                if hp_source_read is not None: hp_source_read.retire()
                self.policy._skill_write_operation = None
                if isinstance(wire, bytearray):
                    wire[:] = b'\0' * len(wire)
        if world_status is not None:
            try:
                status_service.finish_world(writer, row, world_status)
            except BaseException:
                status_service.release(writer)
                raise

    async def _serve(self, reader, writer, row):
        decoder = ClientPlaintextDecoder(cipher_pointer='present_disabled',
                                         max_buffer=self.policy.MAX_BUFFER)
        read_task = None
        conversation = None
        try:
            row['await_phase'] = 'INITIAL_DRAIN'
            await asyncio.wait_for(writer.drain(), self.policy.DRAIN_NS / 1e9)
            row['await_phase'] = 'INITIAL_OWNER'
            sample = await self._sample(row)
            row['policy_row'] = self._policy_sample(row, self.policy.admit, writer, sample.peer, sample,
                                                  time.monotonic_ns(), key_already_drained=True)
            conversation = self.conversation_factory(row['peer']['connection_id'], lambda _: None)
            row['await_phase'] = 'CONVERSATION_OPEN'
            opened = await conversation.opened()
            need(type(opened) in (tuple, list) and len(opened) == 1 and opened[0] == KEY12,
                 'FIXED_PINNED_KEY_CONVERSATION_REQUIRED')
            game = None
            while not self._closing and not self.failure.is_set():
                if read_task is None:
                    read_task = asyncio.create_task(reader.read(self.policy.READ_SIZE))
                    row['_read_task'] = read_task
                row['await_phase'] = 'READ_WAIT'
                completed, _ = await asyncio.wait((read_task,), timeout=self.policy.POLL_NS / 1e9)
                if not completed:
                    row['await_phase'] = 'READ_POLL_CHECKPOINT'
                    operation_lock = row['operation_lock']
                    async with self._row_operation(writer, row):
                        outcome = await self._poll_checkpoint(writer, row, read_task,
                            decoder=decoder, decoder_empty=decoder.buffered_bytes == 0,
                            operation_lock=operation_lock)
                        if outcome is True:
                            break
                        if outcome == 'QUIT_DUPLICATE_CONTINUE':
                            read_task = None
                            row['_read_task'] = None
                    continue  # Owner/source/partial/bootstrap checks; no idle limit.
                raw = read_task.result()
                read_task = None
                row['_read_task'] = None
                if not raw:
                    row['await_phase'] = 'READ_EOF'
                    async with self._row_operation(writer, row):
                        decoder.finish()
                        await self._complete_eof(writer, row, decoder_empty=decoder.buffered_bytes == 0)
                    break
                operation_lock = row['operation_lock']
                async with self._row_operation(writer, row):
                    need(row['operation_lock'] is operation_lock, 'SAME_OPERATION_LOCK_REQUIRED')
                    row['await_phase'] = 'CHUNK_CHECKPOINT'
                    sample = await self._checkpoint(writer, row)
                    decoded = decoder.feed(raw)
                    self._policy_sample(row, self.policy.received_chunk, writer, sample, len(raw), decoder.buffered_bytes,
                                               time.monotonic_ns(), decoded_frames=len(decoded))
                    life = getattr(self,'_player_life',None)
                    batch_life = None if life is None else life.token(writer) if game is not None and game.selection is not None else None
                    for frame in decoded:
                        if batch_life is not None:
                            need(life.token(writer) is batch_life,'PLAYER_LIFE_OLD_BATCH_REQUEST')
                        row['await_phase'] = 'FRAME_CHECKPOINT'
                        sample = await self._checkpoint(writer, row)
                        # Keep one bounded metadata row even when policy refuses
                        # this opcode before emitting its accepted-rx event.
                        self.last_received_frame = dict(
                            opcode=frame.opcode, wire_length=frame.wire_length,
                            endpoint_port=row['peer']['endpoint_port'],
                            connection_id=row['peer']['connection_id'])
                        self._policy_sample(row, self.policy.received_frame, writer, sample, frame.opcode, frame.wire_length,
                                                   time.monotonic_ns())
                        cast = getattr(self, '_cast_feature', None)
                        if cast is not None and frame.opcode == 0x4ee6:
                            cast.received_locked(writer, row, frame)
                        trade = getattr(self, '_shop_trade_feature', None)
                        if frame.opcode == 0x4ed1 and trade is not None:
                            trade.frame_locked(writer, row, frame)
                        action=getattr(self,"_haction_list_feature",None)
                        if frame.opcode==0x4ed4 and action is not None:action.frame_locked(writer,row,frame)
                        row['await_phase'] = 'FRAME_DISPATCH'
                        if not getattr(conversation, 'ack_prepared', False):
                            await self._send(writer, row, await conversation.received(frame))
                        else:
                            if game is None:
                                async def movement_owner(connection, position):
                                    return await self._movement_owner(connection, row, position)
                                async def account_owner(connection):
                                    return await self._account_owner(connection, row)
                                game = self.realm.grant(writer, movement_owner_guard=movement_owner,
                                                        account_owner_guard=account_owner,
                                                        closing_quit_owner_guard=(_ClosingQuitOwnerGuard(self,row,writer)
                                                            if self._source_quit_closing is not None else None),
                                                        connection_id=row['peer']['connection_id'])
                            need(self.realm.registry.resolve(writer) is game, 'SAME_REGISTERED_WRITER_REQUIRED')
                            peer = row['peer']
                            row['_quit_frame_owner'] = ((writer, row, peer, tuple(sorted(peer.items())),
                                row['policy_row'], operation_lock, writer.transport, sample,
                                frame.opcode, frame.wire_length)
                                if self._source_quit_closing is not None and frame.opcode == QUIT_REQUEST
                                   and frame.wire_length == 10 else None)
                            try:
                                replies = await game.received(frame)
                            finally:
                                row['_quit_frame_owner'] = None  # Never survives this original dispatch.
                            need(row['operation_lock'] is operation_lock, 'SAME_OPERATION_LOCK_REQUIRED')
                            await self._send(writer, row, replies, game=True, operation_lock=operation_lock)
        except asyncio.CancelledError:
            raise
        except Exception as failure:
            row['failed'] = True
            self._fail(self._failure_code(failure))
        finally:
            async def cleanup():
                if read_task is not None:
                    read_task.cancel()
                    await asyncio.gather(read_task, return_exceptions=True)
                self.realm.close(writer)
                row['registry_removed'] = (id(writer) not in self.realm.registry._sessions
                                           and id(writer) not in self.realm._movement
                                           and id(writer) not in self.realm._world_frames
                                           and id(writer) not in self.realm._npc_frames
                                           and id(writer) not in self.realm._npc_motion)
                try:
                    decoder.finish()
                except ValueError:
                    pass  # finish() clears partial content even on EOF refusal.
                row['decoder_empty'] = decoder.buffered_bytes == 0
                try:
                    if conversation is not None and self.on_release is not None:
                        answer = self.on_release(row['peer']['connection_id'])
                        if inspect.isawaitable(answer):
                            await answer
                except BaseException as failure:
                    row['failed'] = True
                    row['release_failed'] = True
                    self._fail(self._failure_code(failure))
                finally:
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), self.policy.CLOSE_NS / 1e9)
                        row['positive_close'] = True
                    except (OSError, TimeoutError):
                        self._fail('WRITER_CLOSE_UNKNOWN')
            await _finish_cleanup(cleanup())

    def _joined(self, task, row):
        if row['joined']:
            return
        self._tasks.discard(task)
        row['joined'] = True
        if not task.cancelled() and task.exception() is not None:
            row['failed'] = True
            self._fail('CONNECTION_CLEANUP_FAILED')
        good = row['positive_close'] and row['registry_removed'] and row['decoder_empty']
        if row['policy_row'] is not None and good:
            self.policy.closed(row['writer'], positive_close=True, registry_removed=True,
                               decoder_empty=True, task_joined=True)
        row['promotable'] = (good and row['eof'] and row['boot_complete']
                             and not row['failed'] and not self._closing
                             and id(row['writer']) not in self.policy._quit_drained)

    async def close(self):
        if self._loop is not None:
            need(asyncio.get_running_loop() is self._loop, 'SAME_RUNNING_LOOP_REQUIRED')
        if self._close_task is None:
            transfer = getattr(self._inventory_generation,'transfer_session',None)
            if transfer is not None:transfer.release(self._inventory_generation.writer)
            self._closing = True
            trade = getattr(self, '_shop_trade_feature', None)
            if trade is not None: trade.close()
            action=getattr(self,"_haction_list_feature",None)
            if action is not None:action.close()
            cast = getattr(self, '_cast_feature', None)
            if cast is not None:
                cast.close()
            shop_close = getattr(self.realm, '_shop_quest_close', None)
            if shop_close is not None:
                shop_close()
            item_use = getattr(self, '_item_use_session', None)
            if item_use is not None:
                item_use.close()
            attack_session = getattr(self, '_attack_session', None)
            if attack_session is not None:
                attack_session.close()
            player_hit = getattr(self, '_npc_player_hit', None)
            if player_hit is not None:
                player_hit.close()
            status = getattr(self, '_hp_status', None)
            if status is not None:
                status.close()
            inventory_service = getattr(self, '_inventory_service', None)
            if inventory_service is not None and self._inventory_generation.phase != 'RETIRED':
                if getattr(self, 'inventory_reselection_policy', None) is not None:
                    self._inventory_generation.phase = 'TERMINAL'
                self._inventory_delivery_authority = None
                inventory_service.close()
            self.policy.stop('explicit_session_exit')
            self._close_task = asyncio.create_task(self._close())
        # This wrapper also shields the shared cleanup task from repeat cancel.
        async def join():
            return await asyncio.shield(self._close_task)
        return await _finish_cleanup(join())

    async def _close(self):
        for server in self._servers:
            server.close()
        # An accept callback can have just scheduled _serve without running it.
        # Let it install its finally before cancellation; cancelling a never-
        # started coroutine would otherwise bypass writer cleanup entirely.
        await asyncio.sleep(0)
        tasks = tuple(self._tasks)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        # A completed Task's callbacks may still be queued when gather observes
        # it already done. Finalize those exact tasks before reporting/release.
        for rows in self._claims.values():
            for row in rows:
                task = row.get('task')
                if task is not None and task.done():
                    self._joined(task, row)
        owner = self._inventory_update_owner
        if owner is not None:
            owner.close()  # Original tasks/context finally have already joined.
            self._inventory_update_owner = None
        for server in self._servers:
            await server.wait_closed()
        for sock in self.sockets.values():
            sock.close()
        # Accepted fast-key failure before task creation is not positive cleanup.
        good = all(row['joined'] and row['positive_close'] and row['registry_removed']
                   and row['decoder_empty'] and not row.get('release_failed', False)
                   for rows in self._claims.values() for row in rows)
        if good:
            self.policy.release(self.sockets, listeners_closed=True, tasks_joined=not self._tasks)
        self._source_quit_closing = None  # No terminal receipt survives joined tasks.
        self.cleanup_complete = good
        return self.report()

    def report(self):
        result = dict(schema='lc-original-persistent-broker-v1',
                    state=self.policy.state, failure_code=self.failure_code,
                    last_received_frame=(dict(self.last_received_frame)
                                         if self.last_received_frame is not None else None),
                    owner_failure=dict(self.owner_failure) if self.owner_failure is not None else None,
                    cleanup_complete=self.cleanup_complete, rejected_connections=self._rejected,
                    active_tasks=len(self._tasks), registry_sessions=len(self.realm.registry._sessions),
                    movement=self.realm.movement_report(),
                    world_profile=self.realm.world_profile_report(),
                    settings=dict((self.realm.settings.metadata() if self.realm.settings is not None
                                   else dict(policy='DISABLED')), session_fatal=self.realm._settings_failed),
                    quit=self.realm.quit_report(),
                    inventory_persistence=dict(enabled=getattr(self, '_inventory_store', None) is not None,
                        selected_frame_restored=getattr(self, '_inventory_restored', False),
                        same_broker_redelivery=('LOCAL_SAVED_ROW_ON_RESELECTION'
                            if getattr(self, 'inventory_reselection_policy', None) == INVENTORY_RESELECTION_POLICY
                            else 'UNSUPPORTED_ONCE_STATE_PRESERVED'),
                        reselection_policy=getattr(self, 'inventory_reselection_policy', None)),
                    restart=dict(policy=getattr(self, 'restart_policy', None),
                        scope='LOCAL_SELECTED_RESTART_ACK_DRAIN_ONLY', official_predicate='UNKNOWN',
                        connections=[dict(connection_id=r['peer'].get('connection_id'),
                            phase=r['_restart']['phase'], write_attempted=r['_restart']['write_attempted'],
                            drain_returned=r['_restart']['drain_returned'],
                            response_drained=r['_restart']['response_drained'],
                            selection_cleared=r['_restart']['selection_cleared'],
                            account_terminal_reason=r.get('account_terminal_reason'))
                            for rows in self._claims.values() for r in rows if '_restart' in r]),
                    edge_check=self.realm.edge_report(),
                    events=self.policy.events, dropped_events=self.policy.dropped,
                    ring=list(self.policy.log),
                    connections=[dict(port=port, stage=index,
                                      connection_id=row['peer'].get('connection_id') if row['peer'] else None,
                                      eof=row['eof'],
                                      bootstrap_complete=row['boot_complete'],
                                      positive_close=row['positive_close'], joined=row['joined'],
                                      registry_removed=row['registry_removed'], failed=row['failed'])
                                 for port, rows in self._claims.items() for index, row in enumerate(rows)],
                    game_world_ready_claim=False, packet_values_logged=False)
        attack_session = getattr(self, '_attack_session', None)
        if attack_session is not None:
            result['attack_intent'] = attack_session.metadata()
        item_use = getattr(self, '_item_use_session', None)
        if item_use is not None:
            result['item_use_intent'] = item_use.metadata()
        effect = getattr(self, '_item_equipment_effect', None)
        if effect is not None:
            result['item_equipment_effect'] = dict(effect._last)
        return result
