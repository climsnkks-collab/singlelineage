"""Persistent CP69 transport adapter; native ownership and resources stay in caller.

Call start/close in the launcher's running event loop. The two already reserved
loopback sockets transfer to this adapter. No process launch, automatic retry,
packet payload logging, self movement echo, or implicit character-store path.
"""
from __future__ import annotations

import asyncio
from collections import deque
import copy
import inspect
import os
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
from tools.local_original_session import movement, settings, npc, npc_motion, world_bridge
from tools.local_original_session.world_core_inventory import (
    InventoryCore, RealmInventoryCore, _InventoryGeneration, _inventory_property,
    INVENTORY_UPDATE_POLICY, INVENTORY_RESELECTION_POLICY, INVENTORY_RESELECTION_DELIVERY,
    INVENTORY_MISSING_ROW_POLICY, INVENTORY_STARTER_FIELDS,
)
from tools.local_original_session.world_core_lifecycle import (
    BrokerLifecycle, RealmLifecycle, _ClosingQuitOwnerGuard, _TerminalQuitReceipt,
)
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
# CS_DEAD_RESTART_REQ, body0: the original Restart button while the own Action
# is dead (run102 findings.md "DeathAction과 own UI": ACBF10 +46==0 -> 4EEC).
DEAD_RESTART_REQUEST = 0x4eec
RESTART_ACK = 0x4e3b
ITEM_USE_REQUEST = 0x0960
ATTACK_INTENT_POLICY = 'EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT'
# Exact accepted configured starter, compared only; no default frame producer.
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
    def __init__(self, *args, attack_intent=False, attack_feedback=False, inventory_add=False, restart_enabled=False, item_use_intent=False, inventory_update=False, item_transfer=False, item_equipment_effect=False, npc_death=False, npc_remove=False, player_life=False, world=False, item_kit=False, **kwargs):
        need(type(attack_feedback) is bool and (not attack_feedback or attack_intent),
             'EXPLICIT_ATTACK_FEEDBACK_SWITCH_REQUIRED')
        super().__init__(*args, **kwargs)
        self._quit_drained = {}
        self.player_life = player_life
        self.attack_intent = attack_intent
        self.attack_feedback = attack_feedback
        self.inventory_add = inventory_add
        self.restart_enabled = restart_enabled
        self.item_use_intent = item_use_intent
        self.item_transfer = item_transfer
        self.inventory_update = inventory_update
        self.item_equipment_effect = item_equipment_effect
        need(type(npc_death) is bool and type(npc_remove) is bool
             and (not npc_death or attack_feedback) and (not npc_remove or npc_death),
             'NPC_DEATH_EXPLICIT_TRANSPORT_SWITCH_REQUIRED')
        self.npc_death, self.npc_remove = npc_death, npc_remove
        self.world = world
        need(type(item_kit) is bool and (not item_kit or world and inventory_add),
             'ITEM_KIT_EXPLICIT_TRANSPORT_SWITCH_REQUIRED')
        self.item_kit = item_kit  # M1 kit potion: SC0965 quantity / SC0978 removal.

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
        need(raw_size == 10 and self._quit_drained.get(id(writer)) is writer
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
        extension = (0x4e2b, settings.OPCODE, QUIT_REQUEST, ALIVE_REQUEST)
        if getattr(self, 'player_life', False) is True: extension += (0x4eec,)
        if getattr(self, 'attack_intent', False) is True or getattr(self, 'world', False) is True:
            extension += (ATTACK_REQUEST,)
        if getattr(self, 'restart_enabled', False) is True:
            extension += (RESTART_REQUEST,)
        if getattr(self, 'item_use_intent', False) is True:
            extension += (ITEM_USE_REQUEST,)
        extension = world_bridge.received_extensions(self, extension)
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

    def begin_write(self, writer, sample, opcode, size, queued_bytes, now):
        if getattr(self, 'world', False) is True and type(size) is int and 0 < size:
            # World play: the server's own reply burst (rapid potions plus world
            # ticks) is never refused by its outgoing rate budget; dropping or
            # failing an already decided reply would desync or end the session.
            for rows in self.rows.values():
                for current in rows:
                    if current.writer is writer:
                        current.tx_frames.tokens = max(current.tx_frames.tokens, 1.0)
                        current.tx_bytes.tokens = max(current.tx_bytes.tokens, float(min(size, current.tx_bytes.capacity)))
        extension = (movement.CORRECTION_OPCODE, QUIT_SUCCESS_OPCODE, ALIVE_RESPONSE, npc_motion.OPCODE)
        extension = world_bridge.outgoing_extensions(self, extension, opcode, size, 'menu')
        if self.player_life and opcode in (0x4e39,0x4eed,0x4f16):
            extension += (opcode,)
            need(type(size) is int and 8 <= size <= 32, 'PLAYER_LIFE_FRAME_BOUND')
        if getattr(self, 'npc_death', False) is True and opcode == 0x4e39:
            extension += (opcode,)
            need(type(size) is int and 10 <= size <= 19, 'NPC_DEATH_FRAME_BOUND')
        if getattr(self, 'npc_remove', False) is True and opcode == 0x4e40:
            extension += (opcode,)
            need(type(size) is int and 8 <= size <= 17, 'NPC_REMOVE_FRAME_BOUND')
        extension = world_bridge.outgoing_extensions(self, extension, opcode, size, 'combat')
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
                # M1 kit delivery is one write of several <= MAX_FRAME 0964 frames
                # (inventory.kit_wire_frames); any other 0964 stays one frame.
                limit = (inventory.KIT_MAX_FRAME + inventory.MAX_FRAME
                         if getattr(self, 'item_kit', False) is True else inventory.MAX_FRAME)
                need(type(size) is int and 6 <= size <= limit, 'INVENTORY_FRAME_BOUND')
        if self.item_transfer and opcode in (0x0978, 0x4e96, 0x4e40):
            extension += (opcode,)
            need(type(size) is int and 6 <= size <= self.MAX_FRAME, 'ITEM_TRANSFER_FRAME_BOUND')
        extension = world_bridge.kit_outgoing_extensions(self, extension, opcode, size)
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


class LocalRealm(RealmInventoryCore, RealmLifecycle):
    """Reuse the verified own-login/create/select schemas and CP57 world DTOs.

    CP57 SelfInfo/Actor retain the default explicit local baseline. The optional
    CP73 spawn experiment uses CP74's pinned DTO producer. A different
    stored selection gets its own UID/name and world projection from that baseline.
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
        self.edge_fallback = None  # World mode: static terrain when the client-memory edge is UNKNOWN.
        self.store.snapshot()  # Reject malformed storage before listening.
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
        self._profile_self_fields = dict(self._self_fields)
        self._profile_actor_fields = dict(self._actor_fields)
        self._hp_status = None
        self._npc_player_hit = None
        self._npc_spawns = npc.prepare(npc_spawns, self_uid=self.profile_uid)
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


    def world_profile_report(self):
        return dict(profile=self.world_profile,
                    fallback_policy=(self.world_profile if self.world_profile == CP73_SPAWN_WORLD
                                     else 'EXPLICIT_LOCAL_SOURCE_BASELINE'),
                    fallback_is_original_spawn=False, uid=self.profile_uid, map_id=0,
                    fallback_grid=list(movement.authority.unpack_grid(self._actor_fields[1])),
                    position_policy='SAVED_UID_POSITION_FIRST_ELSE_PROFILE_FALLBACK')

    def _actor_for(self, position, *, heading=None):
        actor = dict(self._actor_fields)
        actor[1] = position.packed
        if heading is not None:
            actor[5] = heading
        actor = world_bridge.actor_fields(self, position, actor)
        return actor

    def _frames_for(self, position, *, status_fields=None, heading=None):
        need(position.uid == self.profile_uid and position.name == self.profile_name
             and self.serves_map(position.map_id), 'EXACT_PROFILE_OWN_STORED_SELECTION_REQUIRED')
        actor = self._actor_for(position, heading=heading)
        fields = self._self_fields if status_fields is None else status_fields
        fields = world_bridge.status_fields(self, position, fields, status_fields is None)
        # The status encoder below validates f26's established double layout;
        # the generic world codec only knows the other scalar layouts.
        session.world.validate_self_spawn({n: v for n, v in fields.items() if n != 26},
                                          actor, this_is_self=True)
        def encode(opcode, fields):
            if opcode == 0x4e38:
                from tools.local_original_session.world_status_frames import full_status_frame
                return full_status_frame(fields)
            body = session.world.encode_payload(opcode, fields)
            return (len(body) + 6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little') + body + b'\0\0'
        # SelfInfo has no grid field. Preserve its source field numbers/values.
        map_frame = world_bridge.map_frame(self, position, encode)
        return map_frame, encode(0x4e38, fields), encode(0x4e96, actor)

    def serves_map(self, map_id):
        return world_bridge.serves_map(self, map_id)


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
            cached = (service.snapshot(), self._frames_for(service.snapshot(), status_fields=fields,
                      heading=getattr(service, '_actor_heading', None)))
            self._world_frames[id(writer)] = cached
        return cached[1]

    def grant(self, writer, *, movement_owner_guard=None, account_owner_guard=None,
              closing_quit_owner_guard=None, connection_id=None):
        empty = dict(schema='lc-owned-local-core-roster-v1', realm='owned-local',
                     source_provenance='explicit_local_game_configuration',
                     expected_count=0, display_slots=3, rows=[], existing_rows=[],
                     mode='initial', allow_expected_growth=False)

        def selection(selected):
            result = self.store.select(selected.reference)
            need(callable(movement_owner_guard), 'SELECTED_MOVEMENT_OWNER_GUARD_REQUIRED')
            need(id(writer) not in self._movement, 'MOVEMENT_WRITER_REUSE_REFUSED')
            if self._movement:
                raise session.Refused('MOVEMENT_SESSION_LIMIT')
            respawn = getattr(self, '_world_respawn_commit', None)
            if respawn is not None:
                # M1 world: a PC that died re-enters at the town point. A failed town
                # save fails this selection (pending kept) instead of a normal entry.
                respawn(result[0], strict=True)
            unserved = getattr(self, '_world_unserved_return', None)
            if unserved is not None:
                # World: a saved map this run does not serve (map experiment off)
                # enters at the town point instead of failing the selection.
                unserved(result[0], selected.reference)
            words = movement.authority.unpack_grid(self._profile_actor_fields[1])
            initial = movement.Position(result[0], selected.reference, 0, *words)
            service = movement.MovementService(initial, connection=writer,
                owner_guard=movement_owner_guard, edge_passability=self.edge_passability,
                store=self.positions, edge_fallback=getattr(self, 'edge_fallback', None))
            previous = (self.profile_uid, self.profile_name, self._self_fields, self._actor_fields)
            if (result[0], selected.reference) != (self.profile_uid, self.profile_name):
                self.profile_uid, self.profile_name = result[0], selected.reference
                self._self_fields, self._actor_fields = (dict(self._profile_self_fields),
                                                        dict(self._profile_actor_fields))
                self._self_fields[1] = self._actor_fields[2] = result[0]
                self._actor_fields[9] = selected.reference
            try:
                frames = self._frames_for(service.snapshot())  # Reject unserved saved maps.
            except BaseException:
                self.profile_uid, self.profile_name, self._self_fields, self._actor_fields = previous
                raise
            self._movement[id(writer)] = (writer, service, connection_id)
            self._world_frames[id(writer)] = (service.snapshot(), frames)

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
            try:
                replies = await prior_select(payload)
            except session.Refused as error:
                if str(error) not in ('SELECT_NOT_OWNED_REFERENCE', 'MOVEMENT_SESSION_LIMIT'):
                    raise
                # No refusal reply is established by the selection protocol.
                # Keep the unselected session usable, without an Enter ACK.
                return ()
            need(replies == () and game.selection is not None, 'EXACT_OWNED_SELECTION_REQUIRED')
            if self._inventory_broker is not None:
                await self._inventory_broker._restore_inventory_selection(writer)
            if self._npc_spawns:
                service = self.service(writer)
                position = service.snapshot()
                need(await movement_owner_guard(writer, position) is True,
                     'NPC_CURRENT_SELECTED_OWNER_REQUIRED')
                self._npc_authority(writer, game, service, position)
                need(self._trial_target_hidden()
                     or all(spawn.map_id == position.map_id for spawn, _ in self._npc_spawns),
                     'NPC_SELECTED_MAP_REQUIRED')
                self._npc_frames[id(writer)] = (writer, game, service,
                                                tuple(spawn.frame() if self._npc_respawn is not None else frame
                                                      for spawn, frame in self._npc_spawns))
                if self._npc_motion_interval_ns is not None:
                    self._npc_motion[id(writer)] = (writer, npc_motion.NpcMotion(
                        self._npc_spawns[0][0], self_uid=position.uid,
                        interval_ns=self._npc_motion_interval_ns, policy=self._npc_motion_policy))
            # World mode spawns its own monsters; the legacy trial target stays unsent
            # (the headless attack smoke keeps it with SL_KEEP_TRIAL_TARGET=1).
            hidden = self._trial_target_hidden()
            trial = () if not self._npc_spawns or hidden else self._npc_frames[id(writer)][3]
            return (ack.ENTER_ACK_FRAME,) + self.world_frames(writer) + trial

        async def move(payload):
            self.registry.resolve(writer)
            need(game.selection is not None, 'SELECTED_MOVEMENT_REQUIRED')
            service = self.service(writer)
            if world_bridge.dead_move(self, service):
                return ()
            result = await world_bridge.move(service, payload)
            if result.fatal or result.reason in ('OWNER_REFUSED', 'OWNER_UNKNOWN'):
                raise ValueError(result.reason)
            if result.accepted and result.reason != 'LOCAL_MAP_TRANSITION':
                # The accepted request is the current heading; attack direction8
                # means keep this transform. It belongs to this movement life.
                _, service._actor_heading = movement.parse_payload(payload)
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
            return await self._inventory_use_intent(writer, payload)

        async def attack_intent(payload):
            self.registry.resolve(writer)
            service = self._attack_session
            need(service is not None and service.targets.broker.realm is self
                 and service.targets.broker._attack_session is service,
                 'ATTACK_SAME_REAL_BROKER_SESSION_REQUIRED')
            # _serve already holds this row's operation_lock. The session
            # checkpoints native ownership without reacquiring that lock.
            replies = await service.handle(writer, payload)
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
            return await self._quit_game(writer, game, payload, movement_owner_guard,
                closing_quit_owner_guard, connection_id)

        async def duplicate_quit(payload):
            return await self._duplicate_quit(writer, game, payload, movement_owner_guard,
                closing_quit_owner_guard, connection_id)

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
            return await self._inventory_transfer(writer, payload, kind='DROP')

        async def item_pickup(payload):
            return await self._inventory_transfer(writer, payload, kind='PICKUP')

        game.routes.update({0x263: receive_login, 0x267: read_news,
                            ack.realm.CREATE_OPCODE: create, 0x4e28: select, 0x4e2b: move,
                            settings.OPCODE: save_settings, QUIT_REQUEST: quit_game,
                            ALIVE_REQUEST: alive})
        life_broker = getattr(self, '_player_life_broker', None)
        if life_broker is not None:
            async def dead_restart(payload):
                return await life_broker._player_life.request_locked(writer,payload)
            game.routes[0x4eec] = dead_restart
        if self._restart_broker is not None:
            game.routes[RESTART_REQUEST] = restart_game
            world_bridge.bind_restart(self, game, life_broker, restart_game)
        if self._attack_session is not None:
            game.routes[ATTACK_REQUEST] = attack_intent
        if self._item_use_session is not None:
            game.routes[ITEM_USE_REQUEST] = item_use_intent
        if self._item_transfer_broker is not None:
            game.routes[0x4e3f], game.routes[0x4e3e] = item_drop, item_pickup
        for opcode, handler in tuple(game.routes.items()):
            async def terminal_guard(payload, operation=handler, route_opcode=opcode):
                need(not self._settings_failed, 'SETTINGS_PERSISTENCE_FATAL')
                if id(writer) in self._quit and route_opcode == QUIT_REQUEST:
                    return await duplicate_quit(payload)
                quit_state = self._quit.get(id(writer))
                if (route_opcode == ALIVE_REQUEST and quit_state is not None
                        and quit_state.get('request_verified') is True):
                    # The client may send one more keepalive after the Quit ACK
                    # while it closes: no reply, no effect, normal close follows.
                    return ()
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
        need(bound is not None and bound[0] is writer and wire in bound[3]
             and (self._npc_respawn is None or any(wire is item for item in bound[3])
                  and self.npc_mover(writer).spawn_drained is False),
             'EXACT_SELECTED_NPC_FRAME_REQUIRED')
        _, game, service, _ = bound
        self._npc_authority(writer, game, service, service.snapshot())
        notifications = (None if self._attack_session is None else self._attack_session._notifications)
        if notifications is not None:
            for spawn, prepared in self._npc_spawns:
                if wire == prepared:
                    notifications.require_not_removed_spawn(writer, spawn.uid)
        need(self._trial_target_hidden()
             or all(spawn.map_id == service.snapshot().map_id for spawn, _ in self._npc_spawns),
             'NPC_SELECTED_MAP_REQUIRED')

    def _trial_target_hidden(self):
        # World mode never sends the legacy trial target (unless the headless
        # attack smoke keeps it with SL_KEEP_TRIAL_TARGET=1), so its map is moot.
        return bool(getattr(self, '_world_hp', None)) and os.environ.get('SL_KEEP_TRIAL_TARGET') != '1'

    def npc_mover(self, writer):
        bound = self._npc_motion.get(id(writer))
        need(bound is not None and bound[0] is writer, 'NPC_MOVE_SAME_BOUND_WRITER_REQUIRED')
        spawn = self._npc_frames.get(id(writer))
        need(spawn is not None and spawn[0] is writer, 'NPC_MOVE_BOUND_SPAWN_REQUIRED')
        _, game, service, _ = spawn
        self._npc_authority(writer, game, service, service.snapshot())
        need(bound[1].state.map_id == service.snapshot().map_id, 'NPC_MOVE_SAME_MAP_REQUIRED')
        return bound[1]


    def close(self, writer):
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
        mover = self._npc_motion.pop(id(writer), None)
        if mover is not None and mover[0] is writer:
            mover[1].close()
        self.registry.close(writer)

    @staticmethod
    def _movement_metadata(row, *, closed=False):
        _, service, cid = row
        return dict(connection_id=cid, committed=service.committed,
                    requests_received=getattr(service, 'requests_received', None),
                    corrections_prepared=getattr(service, 'corrections_prepared', None),
                    correction_reasons=dict(getattr(service, 'correction_reasons', None) or {}),
                    edge_fallback_accepted=getattr(service, 'edge_fallback_accepted', None),
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
            self.npc_mover(writer).validate_frame(wire)
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


class PersistentBroker(InventoryCore, BrokerLifecycle):
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

    def __init__(self, *, sockets, retained_owner, owner_handle, owner_job,
                 owner_guard, owner_liveness_guard, source_guard, conversation_factory, expected_uuid,
                 store_path, on_accept=None, key_guard=None, on_release=None, edge_passability=None,
                 settings_path=None, owner_exit_proof=None, world_profile=BASELINE_WORLD, npc_spawns=(),
                 npc_motion_interval_ns=None, npc_edge_passability=None, npc_motion_policy=None,
                 attack_policy=None, attack_reader=None, attack_feedback=None, attack_hp_provider=None,
                 restart_policy=None, npc_death_policy=None, npc_remove_policy=None, npc_respawn_policy=None,
                 inventory_policy=None, inventory_frame=None, inventory_reader=None, inventory_store_policy=None,
                 item_use_policy=None, inventory_update_policy=None,
                 item_equipment_policy=None, item_equipment_first_enable=False,
                 inventory_reselection_policy=None, inventory_delivery_policy=None,
                 inventory_missing_row_policy=None, hp_status_policy=None,
                 inventory_collection_policy=None, inventory_collection_grant=None,
                 inventory_owner_guard=None, npc_player_hit_policy=None, npc_player_hit_repeated_policy=None,
                 inventory_custody_policy=None, item_transfer_policy=None, player_life_policy=None,
                 world_policy=None, world_starter_kit=None, world_handler_sources=(), listener_ports=None):
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
                 and attack_policy == ATTACK_INTENT_POLICY and len(npc_spawns) == 1
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
        inventory_enabled = self._configure_inventory(
            inventory_policy=inventory_policy, inventory_frame=inventory_frame, inventory_reader=inventory_reader,
            inventory_store_policy=inventory_store_policy, item_use_policy=item_use_policy, inventory_update_policy=inventory_update_policy,
            item_equipment_policy=item_equipment_policy, item_equipment_first_enable=item_equipment_first_enable, inventory_reselection_policy=inventory_reselection_policy,
            inventory_delivery_policy=inventory_delivery_policy, inventory_missing_row_policy=inventory_missing_row_policy, inventory_collection_policy=inventory_collection_policy,
            inventory_collection_grant=inventory_collection_grant, inventory_owner_guard=inventory_owner_guard, retained_owner=retained_owner,
            restart_policy=restart_policy, world_policy=world_policy, item_transfer_policy=item_transfer_policy,
        )
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
        self.sockets = dict(sockets)
        self._listener_ports = dict(zip(PORTS, PORTS)) if listener_ports is None else dict(listener_ports)
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
                                      inventory_update=inventory_update_policy is not None,
                                      world=world_policy is not None,
                                      item_kit=self._inventory_kit_policy is not None)
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
        self._initialize_inventory(
            inventory_enabled=inventory_enabled, inventory_frame=inventory_frame, inventory_reader=inventory_reader,
            inventory_policy=inventory_policy, inventory_store_policy=inventory_store_policy, inventory_custody_policy=inventory_custody_policy,
            inventory_reselection_policy=inventory_reselection_policy, inventory_update_policy=inventory_update_policy, world_policy=world_policy,
            item_use_policy=item_use_policy, item_equipment_policy=item_equipment_policy, item_equipment_first_enable=item_equipment_first_enable,
            item_transfer_policy=item_transfer_policy,
        )
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
        world_bridge.initialize(self, world_policy, world_handler_sources,
                                world_starter_kit, restart_policy, store_path)
        self._npc_player_lethal = None
        if player_life_policy is not None and player_life_policy.label == player_life.NPC_POLICY_LABEL:
            from tools.local_original_session import npc_player_lethal
            self._npc_player_lethal = npc_player_lethal.Service(self)

    async def start(self):
        need(not self._started and not self._closing, 'BROKER_ALREADY_STARTED_OR_CLOSED')
        self._loop = asyncio.get_running_loop()
        self.source_guard()
        # Validate both before handing either one to asyncio (no rebind window).
        for port, sock in self.sockets.items():
            need(isinstance(sock, socket.socket) and sock.family == socket.AF_INET
                 and sock.type & socket.SOCK_STREAM and sock.getsockname() == ('127.0.0.1', self._listener_ports[port])
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
        world_bridge.start(self, self._loop)
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

    def _world_record_dropped(self, opcode, code):
        errors = getattr(self, '_world_handler_errors', None)
        if errors is not None:
            self._world_handler_errors = (errors + ['%s@0x%04x' % (code, opcode)])[-8:]
        self._world_dropped_requests = min(MAX_COUNTER, getattr(self, '_world_dropped_requests', 0) + 1)

    def _world_request_survivable(self, writer, row, frame, error):
        """World mode only: a request refused mid-handling is dropped, not fatal.

        A broken connection/write (drain pending), Quit, a failed broker or a
        failed/closed world save stays on the original terminal path.
        """
        if self._world is None or frame.opcode == QUIT_REQUEST:
            return False
        code = self._failure_code(error)
        policy_row = row.get('policy_row')
        persist = getattr(self, '_world_persist', None)
        if (self._closing or self.failure.is_set() or row.get('failed') or id(writer) in self.realm._quit
                or policy_row is None or policy_row.drain_started_ns is not None
                or getattr(self.policy, 'state', 'OPEN') != 'OPEN'
                or code.startswith('WORLD_PERSIST')
                or persist is not None and (persist.closed or persist.last_failures)):
            return False
        self._world_record_dropped(frame.opcode, code)
        return True


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
                 and server[1] == self._listener_ports[port], 'EXACT_ACCEPTED_LOOPBACK_REQUIRED')
            cid = (1 if port == 12000 else 2) + (2 if len(rows) == 2 else 0)
            peer = dict(schema='lc-local-accepted-peer-v1', connection_id=cid,
                        endpoint_port=port, client_host=client[0], client_port=client[1],
                        server_host=server[0], server_port=port,
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

    async def _checkpoint(self, writer, row):
        sample = await self._sample(row)
        self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
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
                or service.snapshot() is not position or not self.realm.serves_map(position.map_id)):
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
                    or service.snapshot() is not position or not self.realm.serves_map(position.map_id)):
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

    async def npc_player_hit_repeated_context(self, writer, *, policy):
        service = self._npc_player_hit_repeated_service(policy)
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_PLAYER_HIT_CURRENT_ROW_REQUIRED')
        row, = rows
        async with row['operation_lock']:
            await self._checkpoint(writer, row)
            return service.capture_locked(writer)

    async def attack_player_repeated(self, writer, *, expected_context, raw_effect, direction, policy):
        service = self._npc_player_hit_repeated_service(policy)
        return await self._attack_player_current(writer, service=service, expected_context=expected_context,
            raw_effect=raw_effect, direction=direction, repeated=True)

    async def npc_player_hit_context(self, writer, *, policy):
        service = self._npc_player_hit_service(policy)
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_PLAYER_HIT_CURRENT_ROW_REQUIRED')
        row, = rows
        async with row['operation_lock']:
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

    async def _attack_player_current(self, writer, *, service, expected_context, raw_effect, direction, repeated):
        from tools.local_original_session import npc_player_hit
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_PLAYER_HIT_CURRENT_ROW_REQUIRED')
        row, = rows
        operation = None
        async with row['operation_lock']:
            # Invalid/stale requests do not consume a different active request.
            service.validate_locked(writer, expected_context)
            if repeated:
                service.require_repeated_ready(writer, row, expected_context.snapshot)
            else:
                need(id(writer) not in service._operations, 'NPC_PLAYER_HIT_ONCE_REQUEST_REQUIRED')
            await self._checkpoint(writer, row)
            service.validate_locked(writer, expected_context)
            need(id(writer) not in service.status._operations, 'HP_STATUS_CURRENT_SNAPSHOT_ONCE_REQUIRED')
            operation = service.prepare_locked(writer, expected_context=expected_context)
            try:
                wire = service.build_locked(writer, operation, raw_effect=raw_effect, direction=direction)
                await self._send(writer, row, (wire,), game=True, operation_lock=row['operation_lock'],
                                 npc_player_hit_operation=operation)
                service.validate_locked(writer, expected_context)
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
                                 status_operation=status, npc_player_hit_operation=operation)
                result = npc_player_hit.Result(before, status.result.after, expected_context.source_uid,
                                               service, operation)
                operation.result = result
                operation.phase = 'COMMITTED'
                service.last_result = result.metadata()
                return result
            except BaseException:
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

    async def player_life_context(self, writer, *, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with row['operation_lock']:
            await self._checkpoint(writer,row)
            return service.capture_locked(writer)

    async def player_lethal_once(self, writer, *, expected_context, recovery_inputs, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with row['operation_lock']:
            service.current_locked(writer,expected_context)
            await self._checkpoint(writer,row)
            return await service.lethal_locked(writer,expected_context,recovery_inputs)

    async def npc_lethal_context(self, writer, *, expected_context, arrival, policy):
        from tools.local_original_session import npc_player_lethal
        life = self._player_life_service(policy)
        service = self._npc_player_lethal
        need(type(service) is npc_player_lethal.Service and service.life is life,
             'NPC_LETHAL_EXACT_EXPLICIT_SERVICE_REQUIRED')
        row = life.status._checked(writer)[3]
        async with row['operation_lock']:
            await self._checkpoint(writer,row)
            return service.capture_locked(writer,life_context=expected_context,arrival=arrival)

    async def npc_lethal_player(self, writer, *, expected_context, recovery_inputs, raw_effect, direction, policy):
        from tools.local_original_session import npc_player_lethal
        life = self._player_life_service(policy)
        service = self._npc_player_lethal
        need(type(service) is npc_player_lethal.Service and service.life is life,
             'NPC_LETHAL_EXACT_EXPLICIT_SERVICE_REQUIRED')
        row = life.status._checked(writer)[3]
        async with row['operation_lock']:
            service.validate_locked(writer,expected_context)
            await self._checkpoint(writer,row)
            return await life.lethal_npc_locked(writer,expected_context,recovery_inputs,
                raw_effect=raw_effect,direction=direction)

    async def confirm_player_death(self, writer, *, expected_result, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with row['operation_lock']:
            await self._checkpoint(writer,row)
            service.confirm_death_locked(writer,expected_result)

    async def recover_player(self, writer, *, expected_context, recovery_inputs, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with row['operation_lock']:
            service.current_locked(writer,expected_context)
            await self._checkpoint(writer,row)
            return await service.recover_locked(writer,expected_context,recovery_inputs)

    async def confirm_player_recovery(self, writer, *, expected_result, policy):
        service = self._player_life_service(policy)
        row = service.status._checked(writer)[3]
        async with row['operation_lock']:
            await self._checkpoint(writer,row)
            return service.confirm_recovery_locked(writer,expected_result)

    async def update_hp_status(self, writer, *, current_hp, maximum_hp,
                               expected_snapshot, expected_revision, policy):
        """One explicit positive local-character HP display update per selection."""
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
        need(service is not None, 'NPC_RESPAWN_ENABLED_SERVICE_REQUIRED')
        return await service.run(writer, ticket=ticket, spawn=spawn, now_ns=now_ns,
                                 prepared_adapter=prepared_adapter, adopt_generation=adopt_generation)

    async def step_npc(self, writer, *, goal, direction, now_ns, expected_mover=None):
        """Explicit local AI producer; no timer, self echo or player-edge reuse."""
        row = next((row for rows in self._claims.values() for row in rows
                    if row['writer'] is writer), None)
        need(row is not None, 'NPC_MOVE_CURRENT_CLAIM_REQUIRED')
        async with row['operation_lock']:
            mover = self.realm.npc_mover(writer)
            if self._npc_respawn is not None:
                need(expected_mover is mover, 'NPC_MOVE_SAME_OWNED_GENERATION_REQUIRED')
            selected = self.realm.service(writer).snapshot()
            need(await self._movement_owner(writer, row, selected) is True,
                 'NPC_MOVE_CURRENT_OWNER_REQUIRED')
            need(self.realm.npc_mover(writer) is mover and mover.spawn_drained,
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
                 and self.realm.npc_mover(writer) is mover, 'NPC_MOVE_CURRENT_OWNER_REQUIRED')
            if attack_session is not None:
                attack_session.require_live_npc_motion(writer, row, mover.state.uid)
            mover.begin(step)  # Explicit local reference + original consumer pins.
            try:
                await self._send(writer, row, (step.frame,), game=True)
                need(not self._closing and not self.failure.is_set()
                     and not row['joined'] and not row['failed']
                     and self.realm.npc_mover(writer) is mover, 'NPC_MOVE_POST_DRAIN_OWNER_REQUIRED')
                mover.commit(step)  # Once, after positive write/drain and current lifetime.
            except BaseException:
                mover.fail()  # Delivery may have occurred; no automatic retry/rollback.
                row['failed'] = True
                self._fail('NPC_MOVE_SEND_OUTCOME_UNKNOWN')
                raise
            return mover.state


    async def _send(self, writer, row, replies, *, game=False, inventory_service=None,
                    inventory_authority=None, operation_lock=None, inventory_restore_only=False,
                    inventory_update_operation=None, inventory_update_request=None, equipment_operation=None,
                    npc_respawn_operation=None, status_operation=None, npc_player_hit_operation=None,
                    item_transfer_operation=None, player_life_operation=None, npc_player_lethal_operation=None,
                    world_operation=None):
        need(type(replies) in (tuple, list) and len(replies) <= ack.realm.MAX_CHARACTERS + 2,
             'BOUNDED_ROUTE_REPLIES_REQUIRED')
        world_bridge.validate_send(self, row, replies, game, operation_lock, world_operation)
        transfer = self._inventory_generation.transfer_session if item_transfer_operation is not None else None
        if item_transfer_operation is not None:
            from tools.local_original_session.item_transfer_session import ItemTransferSession
            need(type(transfer) is ItemTransferSession and game is True and
                 operation_lock is row['operation_lock'] and operation_lock.locked() and
                 inventory_service is None and equipment_operation is None and inventory_update_operation is None,
                 'ITEM_TRANSFER_ORIGINAL_LOCKED_SEND_REQUIRED')
        life = getattr(self,'_player_life',None)
        if npc_player_lethal_operation is not None:
            lethal = self._npc_player_lethal
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
                        if game and status_service is not None and status_operation is None
                        and world_operation is None else None)
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
                if status_operation is not None:
                    need(status_service is not None and status_service is self.realm._hp_status
                         and game is True and len(replies) == 1
                         and operation_lock is row['operation_lock'] and operation_lock.locked()
                         and status_service.validate(writer, wire, phase='PREPARED') is status_operation,
                         'HP_STATUS_EXACT_SEND_CAPABILITY_REQUIRED')
                    status_sent = row['policy_row'].sent
                elif (game and world_operation is None and int.from_bytes(wire[2:4], 'little') == 0x4e38
                      and status_service is not None and id(writer) in status_service._states):
                    raise ValueError('HP_STATUS_EXACT_SEND_CAPABILITY_REQUIRED')
                inventory_wire = inventory_service is not None
                effect_op = equipment_operation
                if effect_op is not None:
                    effect = self._item_equipment_effect
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
                elif world_operation is not None:
                    world_bridge.validate_frame(self, wire, world_operation)
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
                if player_life_operation is None and transfer is None and world_operation is None and game and int.from_bytes(wire[2:4], 'little') in (0x4e39, 0x4e40):
                    notification_service = self._attack_session._notifications
                    actual_row, record, notification_delivery = notification_service.reserve(writer, wire)
                    notification_policy_row, notification_sent = row['policy_row'], row['policy_row'].sent
                if player_hit is not None and npc_player_hit_operation.phase == 'ATTACK':
                    player_hit.reserve(writer, row, wire, npc_player_hit_operation)
                if game and world_operation is None and int.from_bytes(wire[2:4], 'little') == ATTACK_FEEDBACK and player_hit is None and npc_player_lethal_operation is None:
                    feedback_service = self._attack_session
                    need(feedback_service is not None and feedback_service is self.realm._attack_session,
                         'ATTACK_FEEDBACK_SAME_SERVICE_REQUIRED')
                    feedback_intent = feedback_service.validate_feedback(writer, wire, state='PREPARED')
                    feedback_policy_row = row['policy_row']
                    feedback_sent = feedback_policy_row.sent
                    feedback_service.reserve_feedback(writer, wire)
                if status_operation is not None:
                    status_service.reserve(writer, wire)
                if game and int.from_bytes(wire[2:4], 'little') == RESTART_ACK:
                    actual_row, restart_state = self._validate_restart(writer, wire, phase='PREPARED')
                    restart_policy_row = row['policy_row']
                    restart_sent = restart_policy_row.sent
                    restart_state['phase'] = 'RESERVED'
                row['await_phase'] = 'WRITE_CHECKPOINT'
                sample = await self._checkpoint(writer, row)
                if player_life_operation is not None:
                    life.validate(writer,row,wire,player_life_operation,'RESERVED')
                elif life is not None and game and not (status_operation is not None and status_operation.life_context is not None):
                    if not (type(wire) is bytes and wire in (QUIT_SUCCESS_FRAME,ALIVE_FRAME)):
                        life.check_normal_locked(writer)
                if player_hit is not None:
                    player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                opcode = int.from_bytes(wire[2:4], 'little')
                if update_state is not None:
                    self._inventory_update_current(writer, row, update_state, inventory_update_request)
                if inventory_wire:
                    wire = await self._inventory_before_send(writer, row, wire, inventory_service,
                        inventory_authority, inventory_restore_only)
                # A checkpoint awaits native ownership; selection/realm lifetime
                # can change there. Recheck opt-in NPC authority at the write.
                if game and opcode == 0x4e96 and any(
                        wire == prepared for _, prepared in self.realm._npc_spawns):
                    self.realm._validate_npc_reply(writer, wire)
                if game and world_operation is None and opcode == npc_motion.OPCODE:
                    self.realm.npc_mover(writer).validate_frame(wire)
                if feedback_service is not None:
                    need(feedback_service is self._attack_session
                         and feedback_service.validate_feedback(writer, wire, state='RESERVED') is feedback_intent
                         and row['policy_row'] is feedback_policy_row,
                         'ATTACK_FEEDBACK_SAME_SERVICE_INTENT_REQUIRED')
                if restart_state is not None:
                    self._validate_restart(writer, wire, phase='RESERVED')
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
                payload = world_bridge.inventory_payload(self, wire, inventory_wire)
                self._policy_sample(row, self.policy.begin_write, writer, sample, opcode, len(payload),
                                        writer.transport.get_write_buffer_size(), time.monotonic_ns())
                if inventory_wire or update_state is not None:
                    self._inventory_send_attempt(writer, row, wire, inventory_wire, inventory_service,
                        inventory_authority, inventory_restore_only, update_state, inventory_update_request)
                if feedback_service is not None:
                    # Final source/current-target validation follows synchronous
                    # policy callbacks, then cancel/once-mark without an await.
                    feedback_service.feedback_attempt(writer, wire)
                if restart_state is not None:
                    self._validate_restart(writer, wire, phase='RESERVED')
                    task = asyncio.current_task()
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError()
                    restart_state['phase'] = 'WRITE_ATTEMPTED'
                    restart_state['write_attempted'] = True
                if effect_op is not None:
                    effect.attempt(writer, row, effect_op)
                if notification_service is not None:
                    actual_row, record, actual_delivery = notification_service.attempt(writer, wire)
                if npc_respawn_operation is not None:
                    self._npc_respawn.attempt(writer, row, wire)
                if player_hit is not None:
                    player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                    if npc_player_hit_operation.phase == 'ATTACK':
                        player_hit.attempt(writer, row, wire, npc_player_hit_operation)
                if status_operation is not None:
                    status_drain_started = row['policy_row'].drain_started_ns
                    status_service.attempt(writer, wire)
                    if player_hit is not None:
                        player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                        npc_player_hit_operation.hp_transport = 'WRITE_ATTEMPTED'
                        player_hit.remember(npc_player_hit_operation)
                if world_status is not None:
                    status_service.validate_world_pending(writer, row, replies, wire, world_status)
                if transfer is not None:
                    transfer.attempt(writer,row,wire,item_transfer_operation)
                if player_life_operation is not None:
                    life.attempt(writer,row,wire,player_life_operation)
                writer.write(payload)
                row['await_phase'] = 'WRITE_DRAIN'
                await asyncio.wait_for(writer.drain(), self.policy.DRAIN_NS / 1e9)
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
                except ValueError as error:
                    if not quit_reply or error.args != ('CURRENT_OWNER_REQUIRED',):
                        raise
                    proof = await self._quit_exit(writer, row)
                    self.policy.quit_drained_after_exit(writer, proof=proof, queued_bytes=queued,
                                                       now=time.monotonic_ns())
                else:
                    if restart_state is not None:
                        # drain() may return below the low watermark while the
                        # ACK is still queued. Keep its original reservation and
                        # deadline; owner sampling can let that queue finish.
                        while True:
                            self._validate_restart(writer, wire, phase='WRITE_ATTEMPTED')
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            if queued == 0:
                                break
                            await asyncio.sleep(0)
                            sample = await self._sample(row)
                    if world_status is not None:
                        # Reuse the original NPC/equipment conditional drain
                        # progress: one reservation, original deadline, no resend.
                        while True:
                            status_service.validate_world_pending(writer, row, replies, wire, world_status)
                            sample = await self._sample(row, synchronous_exact=True)
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            if queued == 0:
                                break
                            await asyncio.sleep(0)
                            sample = await self._sample(row)
                    if status_operation is not None:
                        while True:
                            need(row['policy_row'].pending_opcode == opcode
                                 and row['policy_row'].pending_size == len(wire)
                                 and row['policy_row'].drain_started_ns == status_drain_started
                                 and row['policy_row'].sent == status_sent
                                 and status_service.validate(writer, wire, phase='WRITE_ATTEMPTED') is status_operation,
                                 'HP_STATUS_SAME_PENDING_DRAIN_REQUIRED')
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
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
                            need(effect_op['phase'] == 'WRITE_ATTEMPTED'
                                 and row['policy_row'].pending_opcode == opcode
                                 and row['policy_row'].pending_size == len(wire)
                                 and row['policy_row'].drain_started_ns is not None,
                                 'EQUIPMENT_SAME_PENDING_DRAIN_REQUIRED')
                            # Original owner/freshness/deadline checks retain
                            # the original reservation's DRAIN_NS, never reset.
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
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
                            if queued == 0:break
                            await asyncio.sleep(0)
                            sample = await self._sample(row)
                    if notification_service is not None:
                        while True:
                            need(notification_delivery.phase == 'WRITE_ATTEMPTED'
                                 and notification_policy_row.pending_opcode == opcode
                                 and notification_policy_row.pending_size == len(wire)
                                 and notification_policy_row.drain_started_ns is not None,
                                 'NPC_DEATH_SAME_PENDING_DRAIN_REQUIRED')
                            self._policy_sample(row, self.policy.checkpoint, writer, sample, time.monotonic_ns())
                            queued = writer.transport.get_write_buffer_size()
                            if queued == 0:
                                break
                            await asyncio.sleep(0)  # Same reservation; no write/drain/deadline replay.
                            sample = await self._sample(row)
                    if player_hit is not None:
                        player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                    self._policy_sample(row, self.policy.drained, writer, sample, queued, time.monotonic_ns())
                    if quit_reply and queued == 0:
                        self.policy.mark_quit_drained(writer)
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
                    need(queued == 0 and feedback_policy_row.drain_started_ns is None
                         and feedback_policy_row.pending_opcode is None
                         and feedback_policy_row.sent == feedback_sent + 1,
                         'ATTACK_FEEDBACK_EXACT_DRAIN_REQUIRED')
                    feedback_service.feedback_drain(writer, wire)
                    await self._npc_death_after_feedback_locked(writer, row, feedback_intent)
                if notification_service is not None:
                    need(queued == 0 and notification_policy_row.drain_started_ns is None
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
                        npc_player_hit_operation.hp_transport = 'DRAINED'
                        player_hit.remember(npc_player_hit_operation)
                if restart_state is not None:
                    self._validate_restart(writer, wire, phase='WRITE_ATTEMPTED')
                    need(queued == 0 and restart_policy_row.drain_started_ns is None
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
                    self.realm.npc_mover(writer).spawn_drained = True
                if player_life_operation is not None:
                    life.drained(writer,row,wire,player_life_operation)
                if world_status is not None:
                    status_service.world_frame_drained(writer, row, wire, world_status, queued)
            except BaseException:
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
        world_wait = world_wait_event = None
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
                waits = (read_task,)
                world_event = world_bridge.event_for(self, writer)
                if world_event is not None:
                    # Tick-time world frames wake this loop; they are sent below
                    # under the row lock through _send, like a request's replies.
                    if world_wait is None or world_wait_event is not world_event:
                        if world_wait is not None:
                            world_wait.cancel()
                        world_wait = asyncio.ensure_future(world_event.wait())
                        world_wait_event = world_event
                    waits = (read_task, world_wait)
                completed, _ = await asyncio.wait(waits, timeout=self.policy.POLL_NS / 1e9,
                                                  return_when=asyncio.FIRST_COMPLETED)
                world_ready = world_wait is not None and world_wait.done()
                if world_ready:
                    world_wait = world_wait_event = None
                if read_task not in completed:
                    row['await_phase'] = 'READ_POLL_CHECKPOINT'
                    operation_lock = row['operation_lock']
                    async with operation_lock:
                        if world_ready:
                            await self._world_flush(writer, row, game, operation_lock)
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
                    async with row['operation_lock']:
                        decoder.finish()
                        await self._complete_eof(writer, row, decoder_empty=decoder.buffered_bytes == 0)
                    break
                operation_lock = row['operation_lock']
                async with operation_lock:
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
                        try:
                            self._policy_sample(row, self.policy.received_frame, writer, sample, frame.opcode,
                                                frame.wire_length, time.monotonic_ns())
                        except ValueError as error:
                            # World play: a request over the receive rate is dropped alone.
                            if self._world is None or error.args != ('RATE_BOUND',):
                                raise
                            self._world_record_dropped(frame.opcode, 'RATE_BOUND')
                            continue
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
                            peer = row['peer']
                            row['_quit_frame_owner'] = ((writer, row, peer, tuple(sorted(peer.items())),
                                row['policy_row'], operation_lock, writer.transport, sample,
                                frame.opcode, frame.wire_length)
                                if self._source_quit_closing is not None and frame.opcode == QUIT_REQUEST
                                   and frame.wire_length == 10 else None)
                            try:
                                if (self._world is not None
                                        and await world_bridge.receive(self, writer, row, game, frame, operation_lock)):
                                    continue
                                try:
                                    replies = await game.received(frame)
                                finally:
                                    row['_quit_frame_owner'] = None  # Never survives this original dispatch.
                                await self._send(writer, row, replies, game=True, operation_lock=operation_lock)
                                if self._world is not None:
                                    await world_bridge.after_request(self, writer, row, game, frame.opcode,
                                                                     operation_lock)
                            except ValueError as error:
                                # World play safety net: one refused request (need failure)
                                # is dropped and recorded; the broker keeps serving.
                                if not self._world_request_survivable(writer, row, frame, error):
                                    raise
                            finally:
                                row['_quit_frame_owner'] = None
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
                if world_wait is not None:
                    world_wait.cancel()
                    await asyncio.gather(world_wait, return_exceptions=True)
                self.realm.close(writer)
                await world_bridge.leave(self, writer)
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
            world_bridge.close(self)
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
        await world_bridge.stop(self)
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
        world_bridge.report(self, result)
        return result


# Existing native consumers and test fixtures retain their dynamic method API.
world_bridge.install_feature_api(PersistentBroker, LocalRealm, INVENTORY_STARTER_FIELDS)
