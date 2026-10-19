"""One explicit MoveGoal or opt-in AttackTarget/UseItem intent, with no replay.

The launcher owns process cleanup and must have loaded the continuous manual
bridge. RETURNED is only a native return. Move COMMITTED requires the same real
service's one request/commit, saved authority, fresh client agreement and idle/empty queue.
Attack COMMITTED means VALIDATED_ATTACK_INTENT_ONLY with combat_effect UNKNOWN.
UseItem COMMITTED means VALIDATED_ITEM_USE_INTENT_ONLY; effects remain UNKNOWN.
This module never launches, attaches, sends packets or
changes focus. A boundary belongs to one adapter instance for its entire life.
"""
from __future__ import annotations

import copy
import ctypes as C
import asyncio
from ctypes import wintypes as W
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import threading
import time
from types import MethodType

from tools.local_original_session import commands, edge, movement, observe, move_state
from tools.local_original_session import attack, attack_session, npc_observe, attack_action_observe, npc_respawn

MESSAGE = 'LC-Owned-Manual-Move-v1'
ATTACK_MESSAGE = 'LC-Owned-Manual-AttackTarget-v1'
USE_ITEM_ALREADY_OPEN_MESSAGE = 'LC-Owned-Manual-UseItemAlreadyOpen-v1'
USE_ITEM_MESSAGE = 'LC-Owned-Manual-UseItem-v1'
FIRST_ALREADY_OPEN_THEN_NORMAL = 'FIRST_ALREADY_OPEN_THEN_NORMAL'
CURRENT_ENTRY_ONCE = 'CURRENT_ENTRY_ONCE'
USE_ITEM_CURRENT_ENTRY_MESSAGE = 'LC-Owned-Manual-UseItemCurrentEntry-v1'
USE_ITEM_IMAGE_SHA = '8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684'
SOURCE_QUIT_MESSAGE = 'LC-Owned-Manual-SourceQuit-v1'
SOURCE_RESTART_MESSAGE = 'LC-Owned-Manual-SourceRestart-v1'
SOURCE_RESELECT_MESSAGE = 'LC-Owned-Manual-SourceReselect-v1'
# Diagnostic last-entered region only; never completion or admission evidence.
_NPC_OBSERVATION_STAGES = frozenset(('REQUEST', 'AUTHORIZE', 'OWNER_CHECKPOINT',
    'SOURCE_BEFORE', 'WORLD_TYPED', 'MONSTER_TYPED', 'FINAL_READBACK', 'ROOT_RECHECK',
    'SOURCE_AFTER', 'AUTHORITY_AFTER', 'COMPLETE'))
_NPC_OBSERVER_TYPE = npc_observe.NpcObserver
_NPC_OBSERVER_SAMPLE = _NPC_OBSERVER_TYPE.sample
_ACTION_OBSERVER_TYPE = attack_action_observe.AttackActionObserver
_ACTION_OBSERVER_PREPARE = _ACTION_OBSERVER_TYPE.prepare
_ACTION_OBSERVER_COLLECT = _ACTION_OBSERVER_TYPE.collect
_NPC_INCOMPLETE_READS = frozenset(('RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE',
    'RECHECKED_SHARED_COUNT_FINAL_READBACK', 'RECHECKED_SHARED_COUNT_BOTH'))
_RESPAWN_REQUIRE_CURRENT = npc_respawn.Service.require_current
_RESPAWN_CURRENT_GENERATION = npc_respawn.Service.current_generation
WAIT_NS = commands.TOOL_RESULT_WAIT_NS
SAMPLE_NS = 500_000_000
MAX_SEQUENCE = commands.MAX_SEQUENCE
need = observe.need


@dataclass(frozen=True, slots=True)
class ManualMoveBinding:
    writer: object
    broker: object


def _create_once(path, row):
    """Never replace a durable reservation, even after a partial write/crash."""
    commands._ordinary(path, absent=True)
    raw = (json.dumps(row, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')
    need(len(raw) <= 1024, 'MANUAL_MOVE_CLAIM_BOUND')
    with path.open('xb') as stream:
        need(stream.write(raw) == len(raw), 'MANUAL_MOVE_CLAIM_PARTIAL')
        stream.flush()
        os.fsync(stream.fileno())


def _grid(value):
    return (tuple(value) if type(value) is list and len(value) == 2
            and all(type(n) is int and 0 <= n <= 65535 for n in value) else None)


def _rechecked_npc_incomplete(row, target_uid, map_id, server_grid):
    """Classification only; caller must bind the actual producer and live claim."""
    marker = row.get('read_consistency')
    return (type(row.get('status')) is str and row['status'] == 'UNKNOWN'
        and type(row.get('reason')) is str and row['reason'] == 'EDGE_TYPED_READ_CHANGED'
        and row.get('stable_double_read') is False and row.get('source_contract_valid') is False
        and 'client_grid' in row and row['client_grid'] is None
        and 'coordinates_match' in row and row['coordinates_match'] is None
        and row.get('snapshot_atomic') is False and row.get('source_owner_revalidated') is True
        and type(marker) is str and marker in _NPC_INCOMPLETE_READS
        and type(row.get('uid')) is int and row['uid'] == target_uid
        and type(row.get('map_id')) is int and row['map_id'] == map_id
        and _grid(row.get('server_grid')) == server_grid)


def _source_quit_cancel_check():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    if task is not None and task.cancelling():
        raise asyncio.CancelledError()


def _rechecked_action_count_incomplete(row, actor_uid, target_uid, map_id):
    """Exact discarded producer shape; no action/idle or wait authority alone."""
    if type(row) is not dict:
        return False
    expected = attack_action_observe.empty('ATTACK_OBSERVE_TYPED_READ_CHANGED')
    expected.update(actor_uid=actor_uid, target_uid=target_uid, map_id=map_id,
        read_consistency='RECHECKED_SHARED_COUNT_FINAL_READBACK', source_owner_revalidated=True,
        typed_read_changed_field='SHARED_OWNER_COUNT', typed_read_changed_origin='FINAL_PHYSICAL_READBACK')
    for key in ('typed_bytes_requested', 'combined_typed_bytes_requested'):
        value = row.get(key)
        if type(value) is not int or not 0 <= value <= attack_action_observe.BYTE_LIMIT:
            return False
        expected[key] = value
    return (row['typed_bytes_requested'] <= row['combined_typed_bytes_requested']
        and set(row) == set(expected) and all(type(row[key]) is type(value) and row[key] == value
                                            for key, value in expected.items()))


@dataclass(frozen=True, slots=True)
class _LethalPreparation:
    _consumer: object = field(repr=False)
    writer: object = field(repr=False)
    row: object = field(repr=False)
    session: object = field(repr=False)
    intent: object = field(repr=False)
    hp_result: object = field(repr=False)
    hp_entry: object = field(repr=False)
    notification_record: object = field(repr=False)
    lifetime: tuple = field(repr=False)
    sequence: int
    target_uid: int
    accepted_ordinal: int
    originalstarted_ns: int
    _pending: object = field(repr=False)
    _state: object = field(repr=False)
    _state_data: object = field(repr=False)
    _native: object = field(repr=False)
    _request: object = field(repr=False)
    _result_identity: object = field(repr=False)
    _death: object = field(repr=False)
    _death_wire: object = field(repr=False)
    _feedback_wire: object = field(repr=False)


@dataclass(frozen=True, slots=True)
class _RespawnAttackClaim:
    receipt: object = field(repr=False)
    service: object = field(repr=False)
    generation: object = field(repr=False)
    old_generation: object = field(repr=False)
    old_proof: object = field(repr=False)
    root_proof: object = field(repr=False)
    writer: object = field(repr=False)
    row: object = field(repr=False)
    broker: object = field(repr=False)
    session: object = field(repr=False)
    source_guard: object = field(repr=False)
    provider: object = field(repr=False)
    player_uid: object = field(repr=False)
    accepted_before: object = field(repr=False)
    feedback_before: object = field(repr=False)
    native_before: object = field(repr=False)


@dataclass(frozen=True, slots=True)
class _RespawnAttackCompleted:
    _consumer: object = field(repr=False)
    claim: object = field(repr=False)
    receipt: object = field(repr=False)
    generation: object = field(repr=False)
    writer: object = field(repr=False)
    row: object = field(repr=False)
    session: object = field(repr=False)
    intent: object = field(repr=False)
    hp_result: object = field(repr=False)
    hp_entry: object = field(repr=False)
    lifetime: object = field(repr=False)
    sequence: object = field(repr=False)
    accepted_ordinal: object = field(repr=False)
    _pending: object = field(repr=False)
    _state: object = field(repr=False)
    _state_data: object = field(repr=False)


class ManualMoveCommands:
    """Sync MoveGoal and awaited optional intents in the existing loop.

    current() resolves the *current* writer and real PersistentBroker. It is a
    registry resolver, never an authority/edge verdict. Invoke only on the
    constructor thread. poll_async awaits Attack ownership with shared busy held;
    no background task or message pump is created. Coordinate direct
    reader sampling with SessionMonitor's existing 2/s schedule. last_sample_ns
    identifies the actual sample; poll never backfills UNKNOWN from cached rows.
    All UNKNOWN states are terminal and require launcher-owned cleanup.
    """
    def __init__(self, reader, *, current, clock_ns=time.monotonic_ns, allow_attack=False,
                 allow_attack_replacement=False, observe_attack_feedback=False, allow_use_item=False,
                 allow_source_restart=False, allow_source_reselect=False, lethal_attack_preparation=False,
                 allow_respawn_attack=False, use_item_already_open=False, use_item_entry_policy=None,
                 use_item_current_entry=False):
        need(type(reader) is observe.RetainedSceneReader and callable(current)
             and callable(clock_ns), 'MANUAL_MOVE_RETAINED_READER_RESOLVER_REQUIRED')
        need(type(allow_attack) is bool, 'MANUAL_ATTACK_EXPLICIT_BOOL_REQUIRED')
        need(type(lethal_attack_preparation) is bool and (not lethal_attack_preparation
             or allow_attack is True and observe_attack_feedback is True and allow_attack_replacement is False),
             'MANUAL_LETHAL_PREPARATION_EXPLICIT_MODE_REQUIRED')
        self.lethal_attack_preparation = self._lethal_mode = lethal_attack_preparation
        self._attack_purpose = (lethal_attack_preparation, reader, current, clock_ns)
        self._lethal_preparation_completed = None
        need(type(allow_respawn_attack) is bool and (not allow_respawn_attack or lethal_attack_preparation is True),
             'MANUAL_RESPAWN_ATTACK_EXPLICIT_MODE_REQUIRED')
        self.allow_respawn_attack = allow_respawn_attack
        self._respawn_attack_options = (allow_respawn_attack, self._attack_purpose)
        self._respawn_attack_claimed = False
        self._respawn_attack_claim = self._respawn_attack_completed = None
        self._respawn_attack_claims = self._respawn_attack_completions = ()
        self._respawn_post_discarded = None  # Output-only last discarded post summary.
        self._respawn_post_discarded_claim = None  # Diagnostic origin, never authority.
        need(type(allow_attack_replacement) is bool, 'MANUAL_MOVE_REPLACEMENT_EXPLICIT_BOOL_REQUIRED')
        need(type(observe_attack_feedback) is bool, 'MANUAL_ATTACK_OBSERVATION_EXPLICIT_BOOL_REQUIRED')
        need(type(allow_use_item) is bool, 'MANUAL_USE_ITEM_EXPLICIT_BOOL_REQUIRED')
        need(type(use_item_already_open) is bool and (not use_item_already_open or allow_use_item is True),
             'MANUAL_USE_ITEM_ALREADY_OPEN_EXPLICIT_CAP_REQUIRED')
        self.use_item_already_open = use_item_already_open
        need(use_item_entry_policy is None or type(use_item_entry_policy) is str
             and use_item_entry_policy == FIRST_ALREADY_OPEN_THEN_NORMAL
             and allow_use_item is True and use_item_already_open is True,
             'MANUAL_USE_ITEM_ENTRY_POLICY_REQUIRED')
        need(type(use_item_current_entry) is bool and (not use_item_current_entry
             or allow_use_item is True and use_item_already_open is False and use_item_entry_policy is None),
             'MANUAL_USE_ITEM_CURRENT_ENTRY_CAP_REQUIRED')
        self.use_item_current_entry = self._use_item_current_entry_bound = use_item_current_entry
        self.use_item_entry_policy = self._item_use_entry_policy_bound = use_item_entry_policy
        self._item_use_entry_generation_type = self._item_use_entry_generation_current = None
        if use_item_entry_policy is not None or use_item_current_entry:
            from tools.local_original_session.broker import _InventoryGeneration, PersistentBroker
            self._item_use_entry_generation_type = _InventoryGeneration
            self._item_use_entry_generation_current = PersistentBroker.inventory_selection_current
        need(type(allow_source_restart) is bool, 'MANUAL_SOURCE_RESTART_EXPLICIT_BOOL_REQUIRED')
        need(type(allow_source_reselect) is bool and (not allow_source_reselect or allow_source_restart),
             'MANUAL_SOURCE_RESELECT_EXPLICIT_RESTART_BOOL_REQUIRED')
        self.allow_source_reselect, self._source_reselect_claimed = allow_source_reselect, False
        self._source_restart_completed = self._source_reselect_completed = None
        self.allow_source_restart, self._source_restart_claimed = allow_source_restart, False
        if allow_source_restart:
            from tools.local_original_session.broker import PersistentBroker
            self._restart_class = PersistentBroker
            self._restart_current_method = PersistentBroker._restart_current
            self._restart_same_method = PersistentBroker._restart_same
            self._restart_checkpoint = PersistentBroker._checkpoint
        if allow_source_reselect:
            from tools.local_original_session.broker import _InventoryGeneration
            self._reselect_generation_type = _InventoryGeneration
            self._reselect_generation_method = PersistentBroker.inventory_selection_current
        self.allow_use_item = allow_use_item
        self._item_use_type = self._item_use_validate = self._item_use_matches = None
        self._item_use_project = self._item_use_authority = None
        if allow_use_item:
            from tools.local_original_session.item_use_session import ItemUseSession
            self._item_use_type = ItemUseSession
            self._item_use_validate = ItemUseSession.validate_native_request
            self._item_use_matches = ItemUseSession.matches_received
            self._item_use_project = ItemUseSession._project
            self._item_use_authority = ItemUseSession._current_authority
        self.observe_attack_feedback = observe_attack_feedback
        self._attack_action_observer = None
        self._attack_observations = None
        self._last_attack_action = None
        self.allow_attack_replacement = allow_attack_replacement
        self.reader, self.current, self.clock_ns = reader, current, clock_ns
        self.allow_attack, self._attack_observer = allow_attack, None
        self._thread = threading.get_ident()
        self._busy = False
        self.pending = None
        self.sequence = 0
        self._action_sequence = None  # Cache of _publish assignment, never a second counter.
        self._action_bound = None
        self._readonly_pending = None
        self.last_sample_ns = None
        self._now = None
        self._bound = None
        self._window_bound = None
        self._window_observation = None
        self._sampler = None
        self._reservation = False
        self._observation = None
        self.state = dict(status='READY', reason=None, sequence=0, automatic_retry=False,
                          cleanup_required=False, phase='IDLE', native_attempted=False)

    def _terminal(self, reason):
        if not self._respawn_attack_claimed:
            self._lethal_preparation_completed = None
        if not self._respawn_attack_completions:
            self._respawn_attack_completed = None
        self._action_sequence = self._action_bound = None
        self.state = dict(status='UNKNOWN', reason=reason, sequence=self.sequence,
                          automatic_retry=False, cleanup_required=True,
                          phase=self.pending['phase'] if self.pending is not None else self.state['phase'],
                          native_attempted=(self.pending['native_attempted'] if self.pending is not None
                                            else self.state['native_attempted']))
        if self.pending is not None:
            refusal = self.pending.pop('_native_refusal', None)
            request = self.pending.get('request')
            if (reason == 'MANUAL_ATTACK_NATIVE_NOT_RETURNED'
                    and self.pending.get('kind') == 'AttackTarget'
                    and type(refusal) is tuple and len(refusal) == 3
                    and type(request) is dict and refusal[0] is request
                    and type(refusal[1]) is int and refusal[1] == self.sequence == request.get('seq')
                    and type(refusal[2]) is dict and set(refusal[2]) == {'status', 'reason', 'invoked'}
                    and refusal[2]['status'] == 'CODE_ANCHOR_BLOCKED'
                    and type(refusal[2]['reason']) is int and refusal[2]['reason'] == 12
                    and refusal[2]['invoked'] is False):
                self.state['native_refusal'] = dict(refusal[2])  # Output only; never completion authority.
        if self._observation is not None and self._attack_observations is None:
            self.state['observation'] = dict(self._observation)
        elif (self._observation is not None and self.pending is not None
              and self.pending.get('kind') == 'AttackTarget' and self.pending['phase'] == 'ADMISSION'
              and self.pending['native_attempted'] is False):
            diagnostic = {key: self._observation[key] for group in ('scene', 'world', 'move_state')
                          for field in ('status', 'reason') for key in (group + '_' + field,)
                          if key in self._observation}
            if diagnostic:
                self.state['observation'] = diagnostic
        if self._window_observation is not None:
            self.state['window_observation'] = dict(self._window_observation)
        if self.pending is not None and self.pending.get('kind') in ('AttackTarget', 'UseItem', 'SourceRestart', 'SourceReselect'):
            self.state['command'] = self.pending['kind']
        if self._attack_observations is not None:
            self.state['attack_observations'] = dict(self._attack_observations)
        return dict(self.state)

    def _reason(self, error):
        reason = error.args[0] if isinstance(error, ValueError) and len(error.args) == 1 else None
        return (reason if type(reason) is str and re.fullmatch('[A-Z][A-Z0-9_]{0,110}', reason)
                else 'MANUAL_MOVE_OPERATION_UNKNOWN')

    def _clock(self):
        now = self.clock_ns()
        need(type(now) is int and 0 < now < (1 << 63)
             and (self._now is None or now >= self._now), 'MANUAL_MOVE_CLOCK_UNKNOWN')
        self._now = now
        return now

    def _current(self):
        from tools.local_original_session.broker import LocalRealm, PersistentBroker, _TransportPolicy
        need(self.state['status'] != 'UNKNOWN', 'MANUAL_MOVE_TERMINAL')
        binding = self.current()
        need(type(binding) is ManualMoveBinding, 'MANUAL_MOVE_CURRENT_BINDING_REQUIRED')
        broker, writer, reader = binding.broker, binding.writer, self.reader
        need(type(broker) is PersistentBroker, 'MANUAL_MOVE_REAL_BROKER_REQUIRED')
        owner, member, policy = reader.owner, reader.member, broker.policy
        need(not reader.closed and owner is not None and not owner.closed
             and member is not None and member is owner.child
             and type(policy) is _TransportPolicy and policy.owner is owner
             and policy.handle is owner.owner_handle and policy.job is owner.owner_job
             and member.process == owner.owner_handle and member.job == owner.owner_job
             and member.process and member.job, 'MANUAL_MOVE_RETAINED_OWNER_REQUIRED')
        reader.validate()
        need(owner.validate(member) is True, 'MANUAL_MOVE_OWNER_LOST')
        need(not broker._closing and not broker.failure.is_set() and policy.state == 'OPEN',
             'MANUAL_MOVE_BROKER_LIFETIME_LOST')
        claims = [row for rows in broker._claims.values() for row in rows if row['writer'] is writer]
        need(len(claims) == 1, 'MANUAL_MOVE_CURRENT_CLAIM_REQUIRED')
        row = claims[0]
        policy_row = policy._connection(writer)
        need(row['policy_row'] is policy_row and policy_row.writer is writer
             and policy_row.stage == 1 and not row['failed'] and not row['joined']
             and not policy_row.eof and not policy_row.task_joined and not policy_row.registry_removed,
             'MANUAL_MOVE_CURRENT_CLAIM_REQUIRED')
        need(not policy_row.failed and not writer.is_closing()
             and all(other is row or other.get('joined') is True
                     for other in broker._claims[row['peer']['endpoint_port']]),
             'MANUAL_MOVE_EXCLUSIVE_ENDPOINT_REQUIRED')
        realm = broker.realm
        need(type(realm) is LocalRealm, 'MANUAL_MOVE_REAL_REALM_REQUIRED')
        service = realm.service(writer)
        movement_row = realm._movement.get(id(writer))
        need(type(movement_row) is tuple and len(movement_row) == 3
             and movement_row[0] is writer and movement_row[1] is service
             and movement_row[2] == row['peer']['connection_id']
             and type(service) is movement.MovementService and service._connection is writer
             and service._store is realm.positions
             and not service.fatal, 'MANUAL_MOVE_CURRENT_SERVICE_REQUIRED')
        position = service.snapshot()
        game = realm.registry.resolve(writer)
        selected = game.selection
        need(type(position) is movement.Position and selected is not None
             and selected.reference == position.name
             and realm.registry.selected.get(position.name) is selected
             and realm.store.select(selected.reference)[0] == position.uid == realm.profile_uid
             and position.name == realm.profile_name
             and realm.positions.restore(position) == position,
             'MANUAL_MOVE_CURRENT_SELECTION_REQUIRED')
        proof = realm.edge_passability
        need(type(proof) is edge.EdgeAdapter and proof.reader is reader
             and service._edge_passability is proof, 'MANUAL_MOVE_EXACT_EDGE_REQUIRED')
        boundary = commands._ordinary(Path(owner.directory).absolute(), directory=True)
        identity = dict(pid=member.pid, birth=int(member.identity['birth']),
                        candidate_sha256=owner.image_sha)
        need(type(identity['pid']) is int and 0 < identity['pid'] <= 0xffffffff
             and 0 < identity['birth'] <= 0xffffffffffffffff
             and type(owner.image_sha) is str and re.fullmatch('[0-9a-f]{64}', owner.image_sha),
             'MANUAL_MOVE_IDENTITY_REQUIRED')
        need(self._sampler is None or reader.sampler is self._sampler, 'MANUAL_MOVE_SAMPLER_CHANGED')
        # RetainedSceneReader.bind stores DuplicateHandle(...).value as an int.
        # The backend object alone cannot pin a replacement read-only handle.
        read_handle = reader.backend.handle
        need(type(read_handle) is int and 0 < read_handle < 0xffffffffffffffff,
             'MANUAL_MOVE_READ_HANDLE_REQUIRED')
        retained = (writer, broker, policy, owner, member, reader.backend,
                    policy.handle, policy.job, realm, service, row, policy_row, selected,
                    broker.failure, game, proof, service._store)
        info = boundary.stat()
        directory_identity = (info.st_dev, info.st_ino)
        key = (retained, boundary, identity, member.tid, directory_identity, read_handle)
        if self._bound is None:
            self._bound = key
        else:
            before, old_boundary, old_identity, tid, old_directory_identity, old_read_handle = self._bound
            need(read_handle == old_read_handle, 'MANUAL_MOVE_READ_HANDLE_CHANGED')
            need(all(a is b for a, b in zip(retained, before)) and len(retained) == len(before)
                 and boundary == old_boundary and identity == old_identity and member.tid == tid
                 and directory_identity == old_directory_identity,
                 'MANUAL_MOVE_BOUNDARY_OR_LIFETIME_CHANGED')
        counters = (service.requests_received, service.committed, service.corrections_prepared)
        need(all(type(n) is int and 0 <= n < movement.MAX_COUNTER for n in counters),
             'MANUAL_MOVE_COUNTER_UNKNOWN')
        # Resolver/owner/read callbacks may cancel or reject reentry. A valid
        # returned binding must never revive that terminal state at the caller.
        need(self.state['status'] != 'UNKNOWN', 'MANUAL_MOVE_TERMINAL')
        return binding, row, service, position, proof, boundary, identity, counters

    def _window(self, current):
        self._window_observation = None
        owner = self.reader.owner
        user, choices = owner.native.u, []
        for name, args, result in (
            ('RegisterWindowMessageW', (W.LPCWSTR,), W.UINT),
            ('GetClientRect', (W.HWND, C.POINTER(W.RECT)), W.BOOL),
            ('GetWindowThreadProcessId', (W.HWND, C.POINTER(W.DWORD)), W.DWORD),
            ('PostMessageW', (W.HWND, W.UINT, W.WPARAM, W.LPARAM), W.BOOL),
        ):
            fn = getattr(user, name)
            fn.argtypes, fn.restype = args, result
        rows = owner.native.windows(owner.child)
        candidates = []
        for index, row in enumerate(rows):
            name = row.get('class')
            errors = row.get('public_metadata_errors', [])
            need(type(name) is str and bool(name) and type(errors) is list
                 and all(type(error) is dict and error.get('operation') != 'class' for error in errors),
                 'MANUAL_MOVE_WINDOW_CLASS_UNKNOWN')
            if self._window_bound is not None and row['hwnd'] == self._window_bound[0]:
                need(name == 'GLFW30', 'MANUAL_MOVE_BOUND_WINDOW_CLASS_CHANGED')
            if name == 'GLFW30':
                candidates.append((index, row))
        # Hidden/small GLFW rows still make the target ambiguous. Only known
        # other classes may be excluded before the target's fresh native proof.
        need(len(candidates) == 1 and candidates[0][1].get('visible') is True,
             'MANUAL_MOVE_UNIQUE_WINDOW_REQUIRED')
        for index, row in candidates:
            rect = W.RECT()
            # Preserve query order/short circuit. Error belongs to this composite
            # operation only; owned_hwnd's internal failed API is not identified.
            # Winerror 0 is unknown error detail, never evidence of guard success.
            C.set_last_error(0)
            owned = owner.native.owned_hwnd(owner.child, row['hwnd'])
            error = C.get_last_error()
            if not owned:
                self._window_failure('OWNED_HWND', error, index, rows, row)
                need(False, 'MANUAL_MOVE_WINDOW_UNKNOWN')
            C.set_last_error(0)
            client_rect = user.GetClientRect(row['hwnd'], C.byref(rect))
            error = C.get_last_error()
            if not client_rect:
                self._window_failure('GET_CLIENT_RECT', error, index, rows, row)
                need(False, 'MANUAL_MOVE_WINDOW_UNKNOWN')
            if 320 <= rect.right - rect.left <= 7680 and 200 <= rect.bottom - rect.top <= 4320:
                choices.append(row)
        need(len(choices) == 1 and choices[0].get('class') == 'GLFW30',
             'MANUAL_MOVE_UNIQUE_WINDOW_REQUIRED')
        hwnd, pid = choices[0]['hwnd'], W.DWORD()
        tid = int(user.GetWindowThreadProcessId(hwnd, C.byref(pid)))
        need(type(hwnd) is int and hwnd > 0 and tid == owner.child.tid
             and pid.value == current[6]['pid'], 'MANUAL_MOVE_CURRENT_UI_THREAD_REQUIRED')
        if self._window_bound is None:
            self._window_bound = (hwnd, tid)
        need(self._window_bound == (hwnd, tid), 'MANUAL_MOVE_WINDOW_CHANGED')
        return hwnd

    def _window_failure(self, operation, error, index, rows, row):
        # Fixed typed diagnostics only: no HWND, address, caption or extra query.
        self._window_observation = dict(operation=operation, returned=False,
            winerror=error if type(error) is int and 0 <= error <= 0xffffffff else None,
            row_index=min(index, 7), row_count=min(len(rows), 8) if type(rows) is list else None,
            window_class=('GLFW30' if row.get('class') == 'GLFW30' else
                          'other' if type(row.get('class')) is str else 'unknown'),
            known_bound_match=(row['hwnd'] == self._window_bound[0] if self._window_bound is not None else None),
            primary_tid_match=None)

    def _observe(self, current, now, *, waiting=False, allow_attack_command=False, admitting=False, rejecting=False,
                 attack_action_observer=None, _sampled=None):
        self.last_sample_ns = now
        kwargs = {} if attack_action_observer is None else dict(attack_action_observer=attack_action_observer)
        if _sampled is None:
            row, _count = self.reader.sample(include_input_state=False, **kwargs)  # One existing read slot.
        else:
            row = _sampled  # Only the synchronous same-slot feedback collector supplies this.
        if attack_action_observer is not None:
            self._last_attack_action = row.get('attack_action')
        if self._sampler is None:
            self._sampler = self.reader.sampler
        need(self._sampler is not None, 'MANUAL_MOVE_SAMPLER_REQUIRED')
        after = self._current()
        need(after[3] is current[3] and after[7] == current[7], 'MANUAL_MOVE_AUTHORITY_CHANGED_DURING_READ')
        position = after[3]
        world, motion = row.get('world', {}), row.get('move_state', {})
        controller, navigation = motion.get('controller', {}), motion.get('navigation', {})
        transform, action = motion.get('transform', {}), motion.get('action', {})
        busy = action.get('busy_source_eval', {})
        def symbol(value):
            return value if type(value) is str and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,95}', value) else None
        self._observation = {name + '_' + key: symbol(item.get(key))
            for name, item in (('scene', row), ('world', world), ('move_state', motion),
                               ('controller', controller), ('navigation', navigation),
                               ('transform', transform), ('action', action), ('busy', busy))
            for key in ('status', 'reason')}
        self._observation.update(scene_current=symbol(row.get('current')),
                                 scene_pending=symbol(row.get('pending')))
        field = motion.get('typed_read_changed_field')
        if type(field) is str and field in move_state.READBACK_FIELDS:
            self._observation['move_state_typed_read_changed_field'] = field
        self.state['observation'] = dict(self._observation)
        # Even a partial producer can retain a positive contradiction. Inspect
        # these before the narrow read-changed allowlist; UNKNOWN is not a pass.
        need(row.get('current') in (None, 'unknown', 'Land')
             and row.get('pending') in (None, 'unknown', 'none')
             and row.get('root_ready') is not False,
             'MANUAL_MOVE_KNOWN_SCENE_CONTRADICTION')
        need(all(value is None or type(value) is int and value == position.uid
                 for value in (world.get('my_player_uid'), motion.get('actor_uid'),
                               motion.get('character_data', {}).get('own_uid')))
             and motion.get('character_data', {}).get('own_uid_matches_actor') is not False,
             'MANUAL_MOVE_KNOWN_UID_CONTRADICTION')
        need(all(value is None or type(value) is int and value == position.map_id
                 for value in (world.get('map_requested_i32'), world.get('map_resolved_i32'))),
             'MANUAL_MOVE_KNOWN_MAP_CONTRADICTION')
        need(world.get('scene') in (None, 'unknown', 'Land')
             and world.get('pending') in (None, 'unknown', 'none'),
             'MANUAL_MOVE_KNOWN_SCENE_CONTRADICTION')
        need(world.get('source_segment_grid_relation_match') is not False,
             'MANUAL_MOVE_KNOWN_SOURCE_CONTRADICTION')
        scene_known = (row.get('status') == 'OBSERVED' and row.get('root_ready') is True
                       and row.get('current') == 'Land' and row.get('pending') == 'none')
        world_known = (world.get('status') == 'OBSERVED' and world.get('stable_double_read') is True
                       and world.get('my_player_uid') == position.uid
                       and world.get('map_requested_i32') == world.get('map_resolved_i32') == position.map_id)
        def empty_motion(reason):
            return (motion.get('status') == 'UNKNOWN' and motion.get('reason') == reason
                    and motion.get('source_contract_valid') is False
                    and motion.get('stable_double_read') is False
                    and all(motion.get(group, {}).get('status') == 'UNKNOWN'
                            and motion[group].get('reason') == reason for group in
                            ('controller', 'navigation', 'transform', 'action', 'character_data')))
        # Actual producers discard their failed double-read bytes. Only these
        # precise non-atomic failures may wait; owner/type/source failures refuse.
        move_changed = world_known and empty_motion('MOVE_TYPED_READ_CHANGED')
        world_changed = (world.get('status') == 'UNKNOWN'
                         and world.get('reason') == 'WORLD_TYPED_READ_CHANGED'
                         and world.get('stable_double_read') is False
                         and empty_motion('MOVE_CURRENT_WORLD_PROOF_REQUIRED'))
        if admitting and scene_known and move_changed:
            self.state['reason'] = 'MANUAL_MOVE_TYPED_READ_CHANGED_ADMISSION'
            return False, False  # No native reservation; a new strict read is still required.
        if waiting and scene_known and (move_changed or world_changed):
            self.state['reason'] = 'MANUAL_MOVE_NONATOMIC_OBSERVATION_PENDING'
            return False, False
        need(row.get('status') == 'OBSERVED' and row.get('root_ready') is True
             and row.get('current') == 'Land' and row.get('pending') == 'none'
             and world.get('status') == 'OBSERVED' and world.get('stable_double_read') is True
             and world.get('my_player_uid') == position.uid
             and world.get('map_requested_i32') == world.get('map_resolved_i32') == position.map_id
             and motion.get('status') == 'OBSERVED' and motion.get('stable_double_read') is True
             and motion.get('source_contract_valid') is True and motion.get('actor_uid') == position.uid,
             'MANUAL_MOVE_SCENE_ACTOR_UNKNOWN')
        need(all(item.get('status') == 'OBSERVED' for item in (controller, navigation, transform, action))
             and type(controller.get('command_present')) is bool
             and type(navigation.get('active')) is bool
             and action.get('queue_status') == 'OBSERVED'
             and type(action.get('queue_count')) is int and action['queue_count'] >= 0,
             'MANUAL_MOVE_IDLE_QUEUE_UNKNOWN')
        current_action = action.get('current', {})
        moving = (current_action.get('status') == 'OBSERVED' and current_action.get('present') is True
                  and current_action.get('kind') == 'MovingAction'
                  and type(current_action.get('type_table_rva')) is int
                  and current_action['type_table_rva'] == 0x1180ca8
                  and type(current_action.get('finished')) is bool
                  and all(type(current_action.get(key)) is int and 0 <= current_action[key] <= 0xffffffff
                          for key in ('phase_u32', 'token_u32'))
                  and type(current_action.get('direction_i32')) is int
                  and 0 <= current_action['direction_i32'] < len(movement.authority.DELTAS)
                  and _grid(current_action.get('saved_start_grid')) is not None
                  and _grid(current_action.get('predicted_target_grid')) is not None
                  and busy == dict(status='UNKNOWN', value=None,
                       reason='CURRENT_ACTION_PREDICATE_NOT_SUPPORTED', actual_call_observed=False))
        backward = False
        if rejecting:
            # The producer proves type/owner/Coordinate, never a Start call.
            for candidate in (current_action, action.get('queue_head', {})):
                if candidate.get('kind') == 'MovingBackAction':
                    need(candidate.get('status') == 'OBSERVED' and candidate.get('present') is True
                         and type(candidate.get('type_table_rva')) is int
                         and candidate['type_table_rva'] == 0x1180c60
                         and candidate.get('observation_scope') == 'READONLY_SNAPSHOT'
                         and _grid(candidate.get('target_grid')) == (position.word0, position.word1)
                         and type(candidate.get('target_segment')) is list
                         and len(candidate['target_segment']) == 2
                         and all(type(n) is int and -(1 << 31) <= n < (1 << 31)
                                 for n in candidate['target_segment'])
                         and candidate['target_segment'] == [(n >> 6) + 0x7e00
                             for n in (position.word0, position.word1)],
                         'MANUAL_MOVE_BACKWARD_TARGET_UNKNOWN')
                    backward = True
            if current_action.get('kind') == 'MovingBackAction':
                need(busy == dict(status='UNKNOWN', value=None,
                     reason='CURRENT_ACTION_PREDICATE_NOT_SUPPORTED', actual_call_observed=False),
                     'MANUAL_MOVE_IDLE_QUEUE_UNKNOWN')
        need(busy.get('status') == 'EVALUATED' and type(busy.get('value')) is bool
             or waiting and moving or rejecting and backward
                and current_action.get('kind') == 'MovingBackAction', 'MANUAL_MOVE_IDLE_QUEUE_UNKNOWN')
        grids = tuple(_grid(value) for value in (world.get('grid_words'), transform.get('current_grid'),
                                                transform.get('predicted_grid')))
        need(all(value is not None for value in grids), 'MANUAL_MOVE_CLIENT_GRID_UNKNOWN')
        if backward:
            if self.pending.get('backward_sample_ns') is None:
                self.pending['backward_sample_ns'] = now
            self.state['reason'] = 'MANUAL_MOVE_TYPED_BACKWARD_PENDING'
            return False, False
        if waiting and moving:
            self.state['reason'] = 'MANUAL_MOVE_TYPED_MOVING_PENDING'
            return False, False  # Source-qualified motion is never idle/completion.
        self.state['reason'] = None
        matches = all(value == (position.word0, position.word1) for value in grids)
        # Only Move admission opts into replacement of a source-qualified command.
        # Raw command state stays opaque; busy/queue/Nav and completion stay strict.
        command_ready = (controller['command_present'] is False or allow_attack_command
                         and controller['command_present'] is True
                         and controller.get('command_kind') == 'AttackCommand'
                         and type(controller.get('command_owner_uid')) is int
                         and controller['command_owner_uid'] == position.uid
                         and type(controller.get('command_state_i32')) is int)
        idle = (command_ready and navigation['active'] is False
                and action['queue_count'] == 0 and action['busy_source_eval']['value'] is False)
        if (admitting and self.pending is not None and self.pending.get('kind') == 'MoveGoal'
                and self.pending['phase'] == 'ADMISSION' and self.pending['native_attempted'] is False):
            self._observation.update(grid_matches=matches, command_ready=command_ready,
                command_present=controller['command_present'], navigation_active=navigation['active'],
                queue_count=action['queue_count'] if action['queue_count'] <= 0xffffffffffffffff else None,
                busy_value=busy['value'])
            self.state['observation'] = dict(self._observation)
            head = action.get('queue_head', {})
            command_known = (controller['command_present'] is False or
                controller.get('command_kind') in ('MoveCommand', 'AttackCommand')
                and type(controller.get('command_owner_uid')) is int
                and controller['command_owner_uid'] == position.uid
                and type(controller.get('command_state_i32')) is int)
            queue_known = (action['queue_count'] == 0 or action['queue_count'] <= 8192
                and head.get('status') == 'OBSERVED' and head.get('present') is True
                and head.get('kind') in ('DefaultAction', 'BreathAction', 'MovingAction', 'MovingBackAction'))
            if (matches and not idle and world.get('source_segment_grid_relation_match') is True
                    and current_action.get('status') == 'OBSERVED' and current_action.get('present') is True
                    and current_action.get('kind') == 'BreathAction'
                    and type(current_action.get('type_table_rva')) is int
                    and current_action['type_table_rva'] == 0x1180a10
                    and busy == dict(status='EVALUATED', value=False, reason='SOURCE_CURRENT_BREATH',
                                     actual_call_observed=False)
                    and busy.get('actual_call_observed') is False and command_known and queue_known):
                # Breath's source predicate is not the combined idle verdict.
                # Wait without a native claim until a fresh full read passes
                # every original command/Nav/queue/grid gate.
                self.state['reason'] = 'MANUAL_MOVE_SETTLING_ADMISSION_PENDING'
        return matches, idle

    def _enter(self):
        need(threading.get_ident() == self._thread and not self._busy, 'MANUAL_MOVE_REENTRANT_OR_THREAD')
        need(self._readonly_pending is None, 'MANUAL_MOVE_READONLY_PENDING')
        self._busy = True

    def _pending_state(self, reason=None):
        self.state = dict(status='PENDING', reason=reason, sequence=self.sequence,
                          automatic_retry=False, cleanup_required=False,
                          phase=self.pending['phase'], native_attempted=self.pending['native_attempted'])
        if self._observation is not None and self._attack_observations is None:
            self.state['observation'] = dict(self._observation)
        if self.pending.get('kind') in ('AttackTarget', 'UseItem', 'SourceRestart', 'SourceReselect'):
            self.state['command'] = self.pending['kind']
        if self._attack_observations is not None:
            self.state['attack_observations'] = dict(self._attack_observations)

    def _attack_current(self, *, admission=False, _pending=None):
        """Read real session/target authority; no caller capability or verdict."""
        pending, current = self.pending if _pending is None else _pending, self._current()
        need(self.allow_attack is True and pending is not None and pending.get('kind') == 'AttackTarget',
             'MANUAL_ATTACK_DISABLED_OR_PENDING_CHANGED')
        self._attack_purpose_current(pending)
        approach_allowed = (self.observe_attack_feedback and not admission
            and pending['phase'] == 'NATIVE_WAIT' and pending['native_attempted'] is True)
        if not approach_allowed:
            need(current[3] is pending['initial'] and current[7] == pending['before'],
                 'MANUAL_ATTACK_PLAYER_AUTHORITY_CHANGED')
        broker = current[0].broker
        session = broker._attack_session
        need(type(session) is attack_session.AttackSession and session is pending['attack_session']
             and broker.realm._attack_session is session and not session.closed and not session.fatal
             and broker.policy.attack_intent is True
             and session.policy == attack_session.EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT,
             'MANUAL_ATTACK_REAL_SESSION_REQUIRED')
        targets = session.targets
        observer = self._attack_observer
        need(type(targets) is attack.AttackTargets and targets is pending['attack_targets']
             and targets.broker is broker and targets.reader is self.reader
             and npc_observe.NpcObserver is _NPC_OBSERVER_TYPE
             and _NPC_OBSERVER_TYPE.sample is _NPC_OBSERVER_SAMPLE
             and type(observer) is _NPC_OBSERVER_TYPE and observer is pending['observer']
             and type(observer.sample) is MethodType and observer.sample.__self__ is observer
             and observer.sample.__func__ is _NPC_OBSERVER_SAMPLE
             and type(observer.targets) is attack.AttackTargets and observer.targets.broker is broker
             and observer.targets.reader is self.reader and observer.proof.reader is self.reader,
             'MANUAL_ATTACK_SAME_OBSERVER_TARGETS_REQUIRED')
        projection = targets._project(current[0].writer, pending['attack_request'])
        original = pending['attack_projection']
        if current[3] is not pending['initial'] or current[7] != pending['before']:
            need(approach_allowed, 'MANUAL_ATTACK_PLAYER_AUTHORITY_CHANGED')
            advanced, counters, events = attack.AttackTargets.observe_committed_approach(targets,
                current[0].writer, pending['attack_request'], original, pending['before'],
                pending['approach_event_start'])
            need(advanced[1] is current[3] and counters == current[7],
                 'MANUAL_ATTACK_PLAYER_AUTHORITY_CHANGED')
            if session.accepted_count != pending['attack_before']:
                intent = session.current_intent()
                need(type(intent) is attack_session.AttackIntent
                     and intent.accepted_ordinal == pending['attack_before'] + 1
                     and intent._bound._writer is current[0].writer
                     and intent._bound._authority is targets and intent._bound.attacker is current[3]
                     and (intent._bound.target_uid, intent._bound.map_id) ==
                         (pending['target_uid'], current[3].map_id),
                     'MANUAL_ATTACK_CURRENT_INTENT_UNKNOWN')
            pending.update(initial=current[3], before=counters, attack_projection=advanced,
                           approach_event_start=events, approach_commits=pending['approach_commits'] + 1,
                           npc_ready=False, npc_completed_ns=None, feedback_action_next=False)
            for stage in ('post_command', 'post_feedback', 'next_strict_idle'):
                self._attack_observations.pop(stage, None)
            projection, original = advanced, advanced
        need(projection[0] is current[1] and projection[1] is pending['initial']
             and projection[2:5] == original[2:5]
             and targets.same_authority(projection, original),
             'MANUAL_ATTACK_TARGET_AUTHORITY_CHANGED')
        count, before = session.accepted_count, pending['attack_before']
        need(type(count) is int and before <= count <= before + (0 if admission else 1),
             'MANUAL_ATTACK_INTENT_COUNTER_AMBIGUOUS')
        if admission and pending['npc_ready']:
            need(0 <= self._now - pending['npc_completed_ns'] <= 1_000_000_000,
                 'MANUAL_ATTACK_NPC_PROOF_STALE')
        need(self.state['status'] != 'UNKNOWN', 'MANUAL_MOVE_TERMINAL')
        return current

    def submit_attack(self, player_uid, target_uid, map_id):
        return self._submit_attack(player_uid, target_uid, map_id)

    def submit_respawn_attack(self, player_uid, target_uid, map_id, *, receipt):
        return self._submit_attack(player_uid, target_uid, map_id, _respawn_receipt=receipt)

    def _submit_attack(self, player_uid, target_uid, map_id, *, _respawn_receipt=None):
        """Accept one explicit intent only; native publication is async-polled."""
        if self.state['status'] == 'UNKNOWN':
            return dict(self.state)
        if self._busy or threading.get_ident() != self._thread:
            return self._terminal('MANUAL_MOVE_REENTRANT_OR_THREAD')
        if self.pending is not None:
            return dict(self.state, reason='MANUAL_MOVE_PENDING', accepted=False)
        entered = False
        try:
            self._enter()
            entered = True
            claim = (None if _respawn_receipt is None else
                     self._claim_respawn_attack(_respawn_receipt, player_uid, target_uid, map_id))
            if claim is None:
                self.state.update(phase='ADMISSION', native_attempted=False)
            else:
                self.state = dict(status='PENDING', reason=None, sequence=self.sequence,
                    automatic_retry=False, cleanup_required=False, phase='ADMISSION',
                    native_attempted=False, command='AttackTarget')
            self._observation = None
            self._attack_observations = {} if self.observe_attack_feedback else None
            need(self.allow_attack is True, 'MANUAL_ATTACK_DISABLED')
            need(not self._lethal_mode or self._lethal_preparation_completed is None or claim is not None,
                 'MANUAL_LETHAL_PREPARATION_ALREADY_COMPLETED')
            need(all(type(n) is int for n in (player_uid, target_uid, map_id))
                 and 0 < player_uid <= 0xffffffff and 0 < target_uid <= 0xffffffff
                 and target_uid != player_uid and 0 <= map_id <= 0x7fffffff,
                 'MANUAL_ATTACK_UID_MAP_REQUIRED')
            now, current = self._clock(), self._current()
            need((current[3].uid, current[3].map_id) == (player_uid, map_id),
                 'MANUAL_ATTACK_SELECTED_UID_MAP_REQUIRED')
            session = current[0].broker._attack_session
            need(type(session) is attack_session.AttackSession
                 and current[0].broker.realm._attack_session is session
                 and current[0].broker.policy.attack_intent is True
                 and session.policy == attack_session.EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT
                 and not session.closed and not session.fatal
                 and type(session.accepted_count) is int
                 and 0 <= session.accepted_count < session.counter_limit,
                 'MANUAL_ATTACK_REAL_SESSION_REQUIRED')
            targets = session.targets
            need(type(targets) is attack.AttackTargets and targets.broker is current[0].broker
                 and targets.reader is self.reader, 'MANUAL_ATTACK_SAME_TARGETS_REQUIRED')
            request = attack.AttackRequest(target_uid)
            projection = targets._project(current[0].writer, request)
            if self._attack_observer is None:
                self._attack_observer = npc_observe.NpcObserver(current[0].broker, self.reader)
            if self.observe_attack_feedback:
                need(type(session.feedback) is attack_session.FeedbackConfig,
                     'MANUAL_ATTACK_FEEDBACK_CONFIG_REQUIRED')
                if self._attack_action_observer is None:
                    self._attack_action_observer = attack_action_observe.AttackActionObserver(current[0].broker, self.reader)
            self.pending = dict(kind='AttackTarget', phase='ADMISSION', native_attempted=False,
                request=None, initial=current[3], before=current[7], started=now,
                target_uid=target_uid, attack_request=request, attack_session=session,
                attack_targets=targets, attack_projection=projection, observer=self._attack_observer,
                attack_before=session.accepted_count, npc_ready=False, native=None, result_identity=None,
                lethal_preparation=self._lethal_mode if claim is None else False,
                attack_purpose=self._attack_purpose if claim is None else claim)
            if claim is not None:
                self.pending['respawn_attack'] = claim
            if self._lethal_mode and claim is None:
                self.pending.update(lethal_preparation=True,
                    lethal_source=(self.reader, self.current, self.clock_ns, current[0].broker, current[0].broker.source_guard))
            if self.observe_attack_feedback:
                self.pending.update(action_observer=self._attack_action_observer,
                    feedback_before=session.feedback_drained, feedback_action_next=False,
                    feedback_intent=None, feedback_frame=None, approach_commits=0)
            self._attack_current(admission=True)
            self._pending_state()
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered:
                self._busy = False
        return dict(self.state)

    def _attack_result(self, current, *, _pending=None):
        pending = self.pending if _pending is None else _pending
        path = current[5] / ('attack-target-result-' + str(self.sequence) + '.json')
        try:
            row = commands._closed_health_json(path)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeError):
            row = None
        if row is None:
            need(pending['native'] is None, 'MANUAL_ATTACK_IMMUTABLE_RESULT_DISAPPEARED')
            return
        expected = dict(pending['request'], schema='own-attack-target-result-v1')
        need(set(row) == set(expected) | {'status', 'reason', 'invoked'}
             and all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items())
             and type(row['reason']) is int and type(row['invoked']) is bool,
             'MANUAL_ATTACK_RESULT_IDENTITY_OR_SCHEMA')
        if row['status'] == 'CODE_ANCHOR_BLOCKED' and row['reason'] == 12 and row['invoked'] is False:
            pending['_native_refusal'] = (pending['request'], self.sequence,
                dict(status=row['status'], reason=row['reason'], invoked=row['invoked']))
        need(row['status'] == 'RETURNED' and row['invoked'] is True and row['reason'] == 0,
             'MANUAL_ATTACK_NATIVE_NOT_RETURNED')
        info = commands._ordinary(path).stat()
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        need(pending['native'] is None or row == pending['native']
             and pending['result_identity'] == identity, 'MANUAL_ATTACK_IMMUTABLE_RESULT_CHANGED')
        pending.update(native=dict(row), result_identity=identity)

    def submit_source_restart(self, uid, map_id):
        if self.state['status'] == 'UNKNOWN':
            return dict(self.state)
        if self._busy or threading.get_ident() != self._thread:
            return self._terminal('MANUAL_MOVE_REENTRANT_OR_THREAD')
        if self.pending is not None:
            return dict(self.state, reason='MANUAL_MOVE_PENDING', accepted=False)
        entered = False
        try:
            self._enter(); entered = True
            need(self.allow_source_restart is True and not self._source_restart_claimed,
                 'MANUAL_SOURCE_RESTART_DISABLED_OR_CLAIMED')
            need(type(uid) is int and 0 < uid <= 0xffffffff and type(map_id) is int and 0 <= map_id <= 0x7fffffff,
                 'MANUAL_SOURCE_RESTART_UID_MAP_REQUIRED')
            current, now = self._current(), self._clock()
            need((current[3].uid, current[3].map_id) == (uid, map_id)
                 and current[6]['candidate_sha256'] == USE_ITEM_IMAGE_SHA,
                 'MANUAL_SOURCE_RESTART_CURRENT_PLAYER_REQUIRED')
            from tools.local_original_session import restart, settings
            broker = current[0].broker
            store = broker.realm.settings
            need(broker.restart_policy == restart.POLICY and broker.policy.restart_enabled is True
                 and broker.realm._restart_broker is broker and type(store) is settings.SettingsStore
                 and current[1].get('_restart') is None, 'MANUAL_SOURCE_RESTART_FRESH_POLICY_REQUIRED')
            self._source_restart_claimed = True
            self.pending = dict(kind='SourceRestart', phase='ADMISSION', native_attempted=False,
                initial=current[3], before=current[7], started=now, request=None, native=None, result_identity=None,
                restart_current=current, restart_binding=None, restart_state=None, checked_ns=None,
                bound=self._bound, contract=self.reader.contract, settings_store=store,
                settings_before=store.committed)
            if self.allow_source_reselect:
                self.pending['restart_generation'] = broker._inventory_generation
            self._observation = self._attack_observations = None
            self._pending_state('MANUAL_SOURCE_RESTART_ADMISSION_PENDING')
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered: self._busy = False
        return dict(self.state)

    def _source_restart_current(self):
        """Original broker authority across its expected selection-only clear."""
        from tools.local_original_session.broker import PersistentBroker
        pending = self.pending
        need(self.allow_source_restart and pending is not None and pending['kind'] == 'SourceRestart'
             and PersistentBroker is self._restart_class
             and PersistentBroker._restart_current is self._restart_current_method
             and PersistentBroker._restart_same is self._restart_same_method
             and PersistentBroker._checkpoint is self._restart_checkpoint,
             'MANUAL_SOURCE_RESTART_ORIGINAL_PRODUCER_REQUIRED')
        current, bound = pending['restart_current'], pending['bound']
        self._restart_owner_current(current, bound, pending['contract'])
        broker, writer, row = current[0].broker, current[0].writer, current[1]
        state = row.get('_restart')
        cleared = state is not None and state.get('phase') == 'DRAINED'
        actual = self._restart_current_method(broker, writer, row, state=state, cleared=cleared)
        original = pending['restart_binding']
        need(original is not None, 'MANUAL_SOURCE_RESTART_BINDING_REQUIRED')
        # Any new settings request must precede 4E33; an existing valid
        # opaque value need not be saved again for this Restart.
        # Keep every object and immutable peer/handle value fixed; settings
        # changes require that real receive and the original Store validation.
        prefix = 2 + 2 * len(row['peer']) + 3
        need(len(actual[0]) == len(original[0]) and all(a is b for a, b in zip(actual[0], original[0]))
             and actual[1][:prefix] == original[1][:prefix], 'MANUAL_SOURCE_RESTART_AUTHORITY_CHANGED')
        store, before = pending['settings_store'], pending['settings_before']
        need(broker.realm.settings is store and type(before) is int and before >= 0
             and type(store.committed) is int and store.committed in (before, before + 1),
             'MANUAL_SOURCE_RESTART_SETTINGS_UNKNOWN')
        if pending['native_attempted'] is False:
            self._restart_same_method(original, actual)
            need(state is None, 'MANUAL_SOURCE_RESTART_PREPOST_CHANGED')
        else:
            events, policy = list(broker.policy.log), broker.policy
            offset = pending['event_start'] - (policy.events - len(events))
            need(0 <= offset <= len(events), 'MANUAL_SOURCE_RESTART_EVENTS_DROPPED')
            settings_rx = [index for index, event in enumerate(events[offset:]) if event[0] == 'rx'
                           and event[1] == row['peer']['endpoint_port'] and event[2] == 0x4ed6]
            restart_rx = [index for index, event in enumerate(events[offset:]) if event[0] == 'rx'
                          and event[1] == row['peer']['endpoint_port'] and event[2] == 0x4e33]
            need(len(settings_rx) <= 1 and len(restart_rx) <= 1
                 and store.committed == before + len(settings_rx)
                 and (not settings_rx or not restart_rx or settings_rx[0] < restart_rx[0]),
                 'MANUAL_SOURCE_RESTART_SETTINGS_UNKNOWN')
            if store.committed == before:
                self._restart_same_method(original, actual)
            if state is not None:
                # _restart_current just validated this same Store's account,
                # failure latch and actual _load metadata == last. A valid
                # existing opaque value does not require another 4ED6/save.
                need(type(store.last) is dict, 'MANUAL_SOURCE_RESTART_SETTINGS_UNKNOWN')
                need(type(state) is dict and (pending['restart_state'] is None or pending['restart_state'] is state)
                     and state['lock'] is row['operation_lock'] and len(restart_rx) == 1,
                     'MANUAL_SOURCE_RESTART_FRAME_CHANGED')
                self._restart_same_method(state['binding'], actual)
                pending['restart_state'] = state
        need(self.state['status'] != 'UNKNOWN', 'MANUAL_MOVE_TERMINAL')
        return current, state

    def _restart_owner_current(self, current, bound, contract):
        """Same retained owner/boundary check for the two expected transitions."""
        from tools.local_original_session.broker import PersistentBroker
        broker = current[0].broker
        owner, member = bound[0][3:5]
        boundary = commands._ordinary(Path(owner.directory).absolute(), directory=True)
        info = boundary.stat()
        need(type(broker) is PersistentBroker and self._bound is bound and not self.reader.closed
             and self.reader.owner is owner and self.reader.member is member and owner.child is member
             and not owner.closed and self.reader.backend is bound[0][5]
             and owner.owner_handle == bound[0][6] and owner.owner_job == bound[0][7]
             and member.process == owner.owner_handle and member.job == owner.owner_job
             and member.tid == bound[3] and boundary == bound[1]
             and (info.st_dev, info.st_ino) == bound[4]
             and type(member.pid) is int and member.pid == current[6]['pid']
             and int(member.identity['birth']) == current[6]['birth'] and owner.image_sha == current[6]['candidate_sha256']
             and self.reader.contract is contract and type(self.reader.backend.handle) is int
             and self.reader.backend.handle == bound[-1]
             and (self._sampler is None or self.reader.sampler is self._sampler),
             'MANUAL_SOURCE_RESTART_OWNER_CHANGED')
        self.reader.validate()
        need(owner.validate(member) is True, 'MANUAL_MOVE_OWNER_LOST')

    def _source_restart_result(self, current):
        pending = self.pending
        path = current[5] / ('source-restart-result-' + str(self.sequence) + '.json')
        try: row = commands._closed_health_json(path)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeError): row = None
        if row is None:
            need(pending['native'] is None, 'MANUAL_SOURCE_RESTART_RESULT_DISAPPEARED')
            return
        expected = dict(pending['request'], schema='own-source-restart-result-v1')
        need(set(row) == set(expected) | {'status', 'reason', 'invoked'}
             and all(type(row.get(key)) is type(value) and row[key] == value for key, value in expected.items())
             and type(row['status']) is str and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
             and type(row['invoked']) is bool, 'MANUAL_SOURCE_RESTART_RESULT_IDENTITY_OR_SCHEMA')
        need(row['status'] == 'RETURNED' and row['reason'] == 0 and row['invoked'] is True,
             'MANUAL_SOURCE_RESTART_NATIVE_NOT_RETURNED')
        info = commands._ordinary(path).stat()
        identity = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
        need(info.st_size <= 767 and (pending['native'] is None or pending['native'] == row
             and pending['result_identity'] == identity), 'MANUAL_SOURCE_RESTART_IMMUTABLE_RESULT_CHANGED')
        pending.update(native=dict(row), result_identity=identity)

    async def _poll_source_restart(self):
        entered = False
        try:
            self._enter(); entered = True
            pending, now = self.pending, self._clock()
            need(now - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            current = pending['restart_current']
            broker, writer, row = current[0].broker, current[0].writer, current[1]
            async with row['operation_lock']:
                if pending['phase'] == 'ADMISSION':
                    current = self._current()
                    need(current[3] is pending['initial'] and current[7] == pending['before'],
                         'MANUAL_SOURCE_RESTART_PREPOST_CHANGED')
                    actual = self._restart_current_method(broker, writer, row)
                    if pending['restart_binding'] is None: pending['restart_binding'] = actual
                    self._restart_same_method(pending['restart_binding'], actual)
                self._source_restart_current()
                if pending['checked_ns'] is not None and now - pending['checked_ns'] < SAMPLE_NS:
                    return dict(self.state)
                await self._restart_checkpoint(broker, writer, row)
                current, state = self._source_restart_current()
                pending['checked_ns'] = self._clock()
                need(pending['checked_ns'] - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                if pending['phase'] == 'ADMISSION':
                    current = self._admission_current()
                    hwnd = self._window(current)
                    observed = self._observe(current, now, admitting=True)
                    if self.state.get('reason') == 'MANUAL_MOVE_TYPED_READ_CHANGED_ADMISSION':
                        self._pending_state('MANUAL_SOURCE_RESTART_ADMISSION_PENDING')
                        return dict(self.state)
                    need(observed == (True, True), 'MANUAL_SOURCE_RESTART_PLAYER_IDLE_REQUIRED')
                    self._publish(current, hwnd)
                else:
                    self._source_restart_result(current)
                    if state is not None:
                        from tools.local_original_session import restart
                        need(state['phase'] in ('PREPARED', 'RESERVED', 'WRITE_ATTEMPTED', 'DRAINED')
                             and type(state['frame']) is bytes
                             and restart.validate_ack(state['frame'], policy=broker.restart_policy) is True
                             and all(type(state[key]) is bool for key in
                                 ('write_attempted', 'drain_returned', 'response_drained', 'selection_cleared')),
                             'MANUAL_SOURCE_RESTART_ACK_UNKNOWN')
                        need(state['phase'] == 'DRAINED' or not state['selection_cleared'],
                             'MANUAL_SOURCE_RESTART_ACK_UNKNOWN')
                    if pending['native'] is None or state is None or state['phase'] != 'DRAINED':
                        self._pending_state('MANUAL_SOURCE_RESTART_ACK_DRAIN_PENDING')
                        return dict(self.state)
                    need(all(state[key] is True for key in ('write_attempted', 'drain_returned',
                        'response_drained', 'selection_cleared')) and row['policy_row'].drain_started_ns is None
                        and row['policy_row'].pending_opcode is None, 'MANUAL_SOURCE_RESTART_DRAIN_UNKNOWN')
                    events = list(broker.policy.log)
                    offset = pending['event_start'] - (broker.policy.events - len(events))
                    need(0 <= offset <= len(events) and len([e for e in events[offset:] if e[0] == 'tx'
                         and e[1] == row['peer']['endpoint_port'] and e[2] == 0x4e3b and e[3] == len(state['frame'])]) == 1,
                         'MANUAL_SOURCE_RESTART_ACK_TRANSPORT_UNKNOWN')
                    self._source_restart_current()
                    need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                    self._source_restart_current()
                    task = asyncio.current_task()
                    if task is not None and task.cancelling(): raise asyncio.CancelledError()
                    if self.allow_source_reselect:
                        pending['completed_restart_frame'] = state['frame']
                        self._source_restart_completed = pending
                    self.pending = None
                    self.state = dict(status='COMMITTED', reason=None, sequence=self.sequence,
                        automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
                        command='SourceRestart', proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY', response_drained=True,
                        selection_cleared=True, ui='UNKNOWN', inventory_restore='UNKNOWN')
        except asyncio.CancelledError:
            self._terminal('MANUAL_SOURCE_RESTART_CANCELLED')
            raise
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered: self._busy = False
        return dict(self.state)

    def submit_source_reselect(self, uid, map_id):
        if self.state['status'] == 'UNKNOWN': return dict(self.state)
        if self._busy or threading.get_ident() != self._thread:
            return self._terminal('MANUAL_MOVE_REENTRANT_OR_THREAD')
        if self.pending is not None: return dict(self.state, reason='MANUAL_MOVE_PENDING', accepted=False)
        entered = False
        try:
            self._enter(); entered = True
            old = self._source_restart_completed
            need(self.allow_source_reselect is True and not self._source_reselect_claimed
                 and self._source_restart_claimed is True and type(old) is dict,
                 'MANUAL_SOURCE_RESELECT_RESTART_REQUIRED')
            expected = dict(status='COMMITTED', reason=None, sequence=self.sequence, automatic_retry=False,
                cleanup_required=False, phase='COMMITTED', native_attempted=True, command='SourceRestart',
                proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY', response_drained=True, selection_cleared=True,
                ui='UNKNOWN', inventory_restore='UNKNOWN')
            need(self.state == expected and old['request']['seq'] == self.sequence
                 and old['native'] is not None and type(uid) is int and 0 < uid <= 0xffffffffffffffff
                 and type(map_id) is int and 0 <= map_id <= 0x7fffffff
                 and (uid, map_id) == (old['initial'].uid, old['initial'].map_id),
                 'MANUAL_SOURCE_RESELECT_SAVED_PLAYER_REQUIRED')
            current, bound = old['restart_current'], old['bound']
            broker, writer, claim = current[0].broker, current[0].writer, current[1]
            reference = old['initial'].name
            from tools.local_original_session.broker import ack
            need(type(reference) is str and type(broker.realm.store) is ack.realm.CharacterStore,
                 'MANUAL_SOURCE_RESELECT_CANONICAL_REFERENCE_REQUIRED')
            raw = reference.encode('utf-8', errors='strict')
            need(1 <= len(raw) <= 32
                 and all(value >= 32 and value != 127 for value in raw)
                 and raw.decode('utf-8', errors='strict') == reference
                 and ack.realm.CharacterStore.select(broker.realm.store, reference)[0] == uid,
                 'MANUAL_SOURCE_RESELECT_CANONICAL_REFERENCE_REQUIRED')
            self._restart_owner_current(current, bound, old['contract'])
            need(self._reservation is True and not os.path.lexists(current[5] / 'source-reselect-request.json')
                 and not any(current[5].glob('source-reselect-result-*.json')),
                 'MANUAL_SOURCE_RESELECT_BOUNDARY_ALREADY_USED')
            self._source_reselect_claimed = True
            self.pending = dict(kind='SourceReselect', phase='ADMISSION', native_attempted=False,
                initial=old['initial'], before=old['before'], started=self._clock(), request=None,
                native=None, result_identity=None, source_phase='SelectSlot', phase_posted=False,
                claimed_phases=set(), old_restart=old, uid=uid, map_id=map_id, reference=reference,
                reference_hex=raw.hex(), checked_ns=None, first_returned=None,
                event_start=broker.policy.events, reselect_event_start=broker.policy.events,
                new_binding=None, new_generation=None)
            self._observation = self._attack_observations = None
            self._pending_state('MANUAL_SOURCE_RESELECT_SCENE_PENDING')
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered: self._busy = False
        return dict(self.state)

    def _source_reselect_current(self):
        """Keep the cleared Restart, then recognize only its actual new selection."""
        from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration
        from tools.local_original_session import restart
        pending, old = self.pending, self.pending['old_restart']
        need(self.allow_source_reselect is True and self.allow_source_restart is True
             and pending['kind'] == 'SourceReselect' and self._source_restart_completed is old
             and PersistentBroker is self._restart_class
             and PersistentBroker._restart_current is self._restart_current_method
             and PersistentBroker._restart_same is self._restart_same_method
             and PersistentBroker._checkpoint is self._restart_checkpoint
             and _InventoryGeneration is self._reselect_generation_type
             and PersistentBroker.inventory_selection_current is self._reselect_generation_method,
             'MANUAL_SOURCE_RESELECT_ORIGINAL_PRODUCER_REQUIRED')
        current, bound = old['restart_current'], old['bound']
        self._restart_owner_current(current, bound, old['contract'])
        if pending['first_returned'] is not None:
            self._source_reselect_result(current, previous=pending['first_returned'])
        broker, writer, claim = current[0].broker, current[0].writer, current[1]
        state, previous, realm = old['restart_state'], old['restart_generation'], broker.realm
        need(type(state) is dict and claim.get('_restart') is state and state['phase'] == 'DRAINED'
             and state['frame'] is old['completed_restart_frame']
             and restart.validate_ack(state['frame'], policy=broker.restart_policy) is True
             and all(state[key] is True for key in ('write_attempted', 'drain_returned', 'response_drained', 'selection_cleared'))
             and state['lock'] is claim['operation_lock'] and type(previous) is _InventoryGeneration
             and previous.phase == 'RETIRED' and previous.restart_state is state
             and previous.writer is writer and previous.row is claim and previous.lock is state['lock']
             and previous.game is state['binding'][0][7] and previous.selected is state['binding'][0][10]
             and previous.mover is current[2] and previous.reader is self.reader
             and previous.service._closed is True and realm.store is state['binding'][0][12]
             and realm.positions is state['binding'][0][13] and realm.settings is state['binding'][0][14]
             and realm.positions.restore(old['initial']) == old['initial'],
             'MANUAL_SOURCE_RESELECT_OLD_RESTART_CHANGED')
        need(realm.store.select(pending['reference'])[0] == pending['uid']
             and pending['reference'].encode('utf-8').hex() == pending['reference_hex'],
             'MANUAL_SOURCE_RESELECT_STORE_PAIR_CHANGED')
        broker.source_guard(); broker.key_guard()
        game = realm.registry.resolve(writer)
        if game.selection is None:
            need(broker._inventory_generation is previous and pending['new_binding'] is None,
                 'MANUAL_SOURCE_RESELECT_NEW_SELECTION_DISAPPEARED')
            self._restart_same_method(state['binding'], self._restart_current_method(
                broker, writer, claim, state=state, cleared=True))
            return current, None, None
        need(pending['source_phase'] == 'SelectOK' and pending['phase_posted'] is True,
             'MANUAL_SOURCE_RESELECT_SELECTION_BEFORE_OK')
        generation = self._reselect_generation_method(broker, writer)
        need(type(generation) is _InventoryGeneration and generation is broker._inventory_generation
             and generation.previous is previous and generation.restart_state is state
             and generation.phase == 'ACTIVE' and generation.writer is writer and generation.row is claim
             and generation.game is game and generation.selected is game.selection
             and generation.reader is self.reader and generation.store is previous.store
             and generation.account is previous.account and generation.lock is previous.lock
             and generation.mover is not previous.mover and generation.selected is not previous.selected
             and generation.mover.snapshot() == old['initial']
             and (generation.mover.requests_received, generation.mover.committed, generation.mover.corrections_prepared) == (0, 0, 0)
             and generation.selected.reference == pending['reference']
             and (generation.mover.snapshot().uid, generation.mover.snapshot().map_id) == (pending['uid'], pending['map_id'])
             and generation.current_frame is None and generation.attempted is False,
             'MANUAL_SOURCE_RESELECT_NEW_GENERATION_REQUIRED')
        actual = self._restart_current_method(broker, writer, claim)
        objects = list(state['binding'][0])
        objects[8:11] = [generation.mover, generation.mover.snapshot(), generation.selected]
        self._restart_same_method((tuple(objects), state['binding'][1]), actual)
        if pending['new_binding'] is None:
            pending['new_binding'], pending['new_generation'] = actual, generation
        else:
            need(pending['new_generation'] is generation, 'MANUAL_SOURCE_RESELECT_NEW_GENERATION_CHANGED')
            self._restart_same_method(pending['new_binding'], actual)
        return current, generation, actual

    def _source_reselect_result(self, current, *, previous=None):
        pending = self.pending
        sequence = self.sequence if previous is None else previous[0]['seq']
        path = current[5] / ('source-reselect-result-' + str(sequence) + '.json')
        try: row = commands._closed_health_json(path)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeError): row = None
        if previous is not None:
            need(type(row) is dict and set(row) == set(previous[0])
                 and all(type(row[key]) is type(value) and row[key] == value for key, value in previous[0].items()),
                 'MANUAL_SOURCE_RESELECT_FIRST_RESULT_CHANGED')
            info = commands._ordinary(path).stat()
            need((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) == previous[1],
                 'MANUAL_SOURCE_RESELECT_FIRST_RESULT_CHANGED')
            return True
        if row is None:
            need(pending['native'] is None, 'MANUAL_SOURCE_RESELECT_RESULT_DISAPPEARED')
            return False
        expected = dict(pending['request'], schema='own-source-reselect-result-v1')
        need(set(row) == set(expected) | {'status', 'reason', 'invoked'}
             and all(type(row.get(key)) is type(value) and row[key] == value for key, value in expected.items())
             and type(row['status']) is str and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
             and type(row['invoked']) is bool, 'MANUAL_SOURCE_RESELECT_RESULT_IDENTITY_OR_SCHEMA')
        need(row['status'] == 'RETURNED' and row['reason'] == 0 and row['invoked'] is True,
             'MANUAL_SOURCE_RESELECT_NATIVE_NOT_RETURNED')
        info = commands._ordinary(path).stat()
        identity = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
        need(info.st_size <= 767 and (pending['native'] is None or pending['native'] == row
             and pending['result_identity'] == identity), 'MANUAL_SOURCE_RESELECT_IMMUTABLE_RESULT_CHANGED')
        pending.update(native=dict(row), result_identity=identity)
        return True

    def _source_reselect_transport(self, current, generation):
        """Read only the existing received/drained ring and original world literals."""
        from tools.local_original_session.broker import ack
        pending, broker = self.pending, current[0].broker
        events = list(broker.policy.log)
        offset = pending['reselect_event_start'] - (broker.policy.events - len(events))
        need(0 <= offset <= len(events), 'MANUAL_SOURCE_RESELECT_EVENTS_DROPPED')
        events, endpoint = events[offset:], current[1]['peer']['endpoint_port']
        requests = [event for event in events if event[0] == 'rx' and event[1] == endpoint and event[2] == 0x4e28]
        need(len(requests) <= 1 and (not requests or pending['source_phase'] == 'SelectOK'
             and pending['phase_posted'] is True), 'MANUAL_SOURCE_RESELECT_REQUEST_UNKNOWN')
        if generation is None: return False
        writer, position = generation.writer, generation.mover.snapshot()
        cache = broker.realm._world_frames.get(id(writer))
        need(type(cache) is tuple and len(cache) == 2 and cache[0] is position
             and type(cache[1]) is tuple and cache[1] and all(type(frame) is bytes for frame in cache[1]),
             'MANUAL_SOURCE_RESELECT_WORLD_LITERAL_REQUIRED')
        expected = (ack.ENTER_ACK_FRAME,) + cache[1]
        counts = {}
        for frame in expected:
            key = (int.from_bytes(frame[2:4], 'little'), len(frame))
            counts[key] = counts.get(key, 0) + 1
        for (opcode, size), count in counts.items():
            actual = len([event for event in events if event[0] == 'tx' and event[1] == endpoint
                          and event[2] == opcode and event[3] == size])
            need(actual <= count, 'MANUAL_SOURCE_RESELECT_WORLD_TRANSPORT_AMBIGUOUS')
            if actual != count: return False
        return (len(requests) == 1 and current[1]['policy_row'].pending_opcode is None
                and current[1]['policy_row'].drain_started_ns is None)

    async def _poll_source_reselect(self):
        entered = False
        try:
            self._enter(); entered = True
            pending, now = self.pending, self._clock()
            need(now - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            old = pending['old_restart']
            saved = old['restart_current']
            broker, writer, claim = saved[0].broker, saved[0].writer, saved[1]
            async with claim['operation_lock']:
                current, generation, binding = self._source_reselect_current()
                self._source_reselect_transport(current, generation)
                if pending['checked_ns'] is not None and now - pending['checked_ns'] < SAMPLE_NS:
                    return dict(self.state)
                await self._restart_checkpoint(broker, writer, claim)
                current, generation, binding = self._source_reselect_current()
                pending['checked_ns'] = self._clock()
                need(pending['checked_ns'] - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                if pending['phase'] == 'NATIVE_WAIT':
                    if not self._source_reselect_result(current):
                        self._pending_state('MANUAL_SOURCE_RESELECT_NATIVE_PENDING')
                        return dict(self.state)
                    if pending['source_phase'] == 'SelectSlot':
                        pending['first_returned'] = (pending['native'], pending['result_identity'])
                        pending.update(source_phase='SelectOK', phase='ADMISSION', phase_posted=False,
                                       request=None, native=None, result_identity=None)
                        self._pending_state('MANUAL_SOURCE_RESELECT_SELECT_OK_PENDING')
                        return dict(self.state)  # A distinct later 2Hz slot must reread scene 4.
                self.last_sample_ns = self._clock()
                row, _count = self.reader.sample(include_input_state=False)
                self.last_sample_ns = self._clock()
                current, generation, binding = self._source_reselect_current()
                if pending['phase'] == 'NATIVE_WAIT':
                    need(self._source_reselect_result(current) is True, 'MANUAL_SOURCE_RESELECT_RESULT_DISAPPEARED')
                need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                task = asyncio.current_task()
                if task is not None and task.cancelling(): raise asyncio.CancelledError()
                need(row.get('status') == 'OBSERVED' and row.get('root_ready') is True
                     and row.get('current') in ('CharacterSelect', 'Land')
                     and row.get('pending') in ('none', 'CharacterSelect', 'Land'),
                     'MANUAL_SOURCE_RESELECT_SCENE_UNKNOWN')
                if pending['phase'] == 'ADMISSION':
                    need(generation is None and (pending['source_phase'] == 'SelectSlot'
                         or pending['first_returned'] is not None), 'MANUAL_SOURCE_RESELECT_PHASE_CHANGED')
                    if not (row.get('status') == 'OBSERVED' and row.get('root_ready') is True
                            and row.get('current') == 'CharacterSelect' and row.get('pending') == 'none'):
                        self._pending_state('MANUAL_SOURCE_RESELECT_SCENE_PENDING')
                        return dict(self.state)
                    self._publish(current, self._window(current))
                    return dict(self.state)
                ready = self._source_reselect_transport(current, generation)
                if generation is None or not ready:
                    self._pending_state('MANUAL_SOURCE_RESELECT_WORLD_PENDING')
                    return dict(self.state)
                position, world = generation.mover.snapshot(), row.get('world', {})
                need(all(value is None or type(value) is int and value == pending['uid'] for value in
                         (world.get('my_player_uid'), row.get('move_state', {}).get('actor_uid'),
                          row.get('move_state', {}).get('character_data', {}).get('own_uid')))
                     and row.get('move_state', {}).get('character_data', {}).get('own_uid_matches_actor') is not False
                     and all(value is None or type(value) is int and value == pending['map_id'] for value in
                         (world.get('map_requested_i32'), world.get('map_resolved_i32')))
                     and world.get('source_segment_grid_relation_match') is not False
                     and _grid(world.get('grid_words')) in (None, (position.word0, position.word1)),
                     'MANUAL_SOURCE_RESELECT_KNOWN_WORLD_CONTRADICTION')
                if not (row.get('status') == 'OBSERVED' and row.get('root_ready') is True
                        and row.get('current') == 'Land' and row.get('pending') == 'none'
                        and world.get('status') == 'OBSERVED' and world.get('stable_double_read') is True
                        and type(world.get('my_player_uid')) is int and world['my_player_uid'] == pending['uid']
                        and world.get('map_requested_i32') == world.get('map_resolved_i32') == pending['map_id']
                        and _grid(world.get('grid_words')) == (position.word0, position.word1)):
                    self._pending_state('MANUAL_SOURCE_RESELECT_WORLD_PENDING')
                    return dict(self.state)
                self._source_reselect_current()
                need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                self._source_reselect_current()
                task = asyncio.current_task()
                if task is not None and task.cancelling(): raise asyncio.CancelledError()
                # Advance only the two real changed objects. Never clear the
                # retained binding, reservation or global/native once state.
                bound = old['bound']
                retained = list(bound[0])
                retained[9], retained[12] = generation.mover, generation.selected
                self._bound = (tuple(retained),) + bound[1:]
                fresh = self._current()  # The entire original comparison remains strict.
                need(fresh[2] is generation.mover and fresh[3] is position,
                     'MANUAL_SOURCE_RESELECT_FINAL_BOUND_CHANGED')
                need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                fresh = self._current()
                broker.source_guard(); broker.key_guard()
                self._restart_same_method(binding, self._restart_current_method(broker, writer, claim))
                self._restart_owner_current(fresh, self._bound, old['contract'])
                need(self._source_reselect_result(fresh) is True, 'MANUAL_SOURCE_RESELECT_RESULT_DISAPPEARED')
                if task is not None and task.cancelling(): raise asyncio.CancelledError()
                self._source_reselect_completed = (old, generation, self._bound, fresh)
                self.pending = None
                self.state = dict(status='COMMITTED', reason=None, sequence=self.sequence,
                    automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
                    command='SourceReselect', proof_scope='LOCAL_RESELECT_LAND_READY_ONLY', selection_changed=True,
                    world_ready=True, ui='UNKNOWN', inventory_restore='UNKNOWN')
        except asyncio.CancelledError:
            self._terminal('MANUAL_SOURCE_RESELECT_CANCELLED')
            raise
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered: self._busy = False
        return dict(self.state)

    def _use_item_result(self, current):
        """Callee return/lease cleanup only; never received intent or use effect."""
        pending = self.pending
        already_open = pending.get('already_open_entry', False)
        current_entry = pending.get('current_entry_capability') is CURRENT_ENTRY_ONCE
        path = current[5] / (('use-item-current-entry-result-' if current_entry else 'use-item-already-open-result-' if already_open else 'use-item-result-')
                             + str(self.sequence) + '.json')
        try:
            row = commands._closed_health_json(path)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeError):
            row = None
        if row is None:
            need(pending['native'] is None, 'MANUAL_USE_ITEM_IMMUTABLE_RESULT_DISAPPEARED')
            return
        expected = dict(pending['request'], schema=('own-use-item-current-entry-result-v1' if current_entry
                                                   else 'own-use-item-already-open-result-v1' if already_open else 'own-use-item-result-v1'))
        need(set(row) == set(expected) | {'status', 'reason', 'invoked'}
             and all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items())
             and type(row['status']) is str and row['status'] in
                 ('RETURNED', 'UNKNOWN', 'BLOCKED_SOURCE_BINDING', 'CODE_ANCHOR_BLOCKED', 'REFUSED')
             and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
             and type(row['invoked']) is bool,
             'MANUAL_USE_ITEM_RESULT_IDENTITY_OR_SCHEMA')
        need(row['status'] == 'RETURNED' and row['invoked'] is True and row['reason'] == 0,
             'MANUAL_USE_ITEM_NATIVE_NOT_RETURNED')
        info = commands._ordinary(path).stat()
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        need(info.st_size <= 767 and (pending['native'] is None or row == pending['native']
             and pending['result_identity'] == identity), 'MANUAL_USE_ITEM_IMMUTABLE_RESULT_CHANGED')
        pending.update(native=dict(row), result_identity=identity)

    def _use_item_current(self, *, admission=False):
        """Object/owner pins around the source-owned async/read-only hooks."""
        from tools.local_original_session import item_use_session
        from tools.local_original_session.broker import PersistentBroker
        pending, current = self.pending, self._current()
        need(self.allow_use_item is True and pending is not None and pending.get('kind') == 'UseItem',
             'MANUAL_USE_ITEM_DISABLED_OR_PENDING_CHANGED')
        need(type(self.use_item_current_entry) is bool
             and self.use_item_current_entry is self._use_item_current_entry_bound
             and pending.get('current_entry_capability') is (CURRENT_ENTRY_ONCE if self._use_item_current_entry_bound else None),
             'MANUAL_USE_ITEM_CURRENT_ENTRY_CHANGED')
        need(self.use_item_entry_policy is self._item_use_entry_policy_bound,
             'MANUAL_USE_ITEM_ENTRY_POLICY_CHANGED')
        need(type(self.use_item_already_open) is bool
             and (pending.get('already_open_entry', False) is self.use_item_already_open
                  if self._item_use_entry_policy_bound is None else self.use_item_already_open is True
                  and type(pending.get('already_open_entry')) is bool),
             'MANUAL_USE_ITEM_ENTRY_SELECTION_CHANGED')
        need(current[6]['candidate_sha256'] == USE_ITEM_IMAGE_SHA,
             'MANUAL_USE_ITEM_PROGRAM_IMAGE_REQUIRED')
        need(current[3] is pending['initial'] and current[7] == pending['before'],
             'MANUAL_USE_ITEM_PLAYER_AUTHORITY_CHANGED')
        broker, cls, session = current[0].broker, self._item_use_type, pending['item_session']
        need(item_use_session.ItemUseSession is cls and type(session) is cls
             and broker._item_use_session is session and broker.realm._item_use_session is session
             and session.broker is broker and not session.closed
             and session.policy == item_use_session.POLICY and broker.policy.item_use_intent is True
             and cls.validate_native_request is self._item_use_validate
             and cls.matches_received is self._item_use_matches
             and cls._project is self._item_use_project
             and cls._current_authority is self._item_use_authority,
             'MANUAL_USE_ITEM_REAL_SESSION_REQUIRED')
        for name, function in (('validate_native_request', self._item_use_validate),
                               ('matches_received', self._item_use_matches),
                               ('_project', self._item_use_project),
                               ('_current_authority', self._item_use_authority)):
            method = getattr(session, name)
            need(type(method) is MethodType and method.__self__ is session and method.__func__ is function,
                 'MANUAL_USE_ITEM_ORIGINAL_OBSERVER_REQUIRED')
        refs = (broker._inventory_service, broker._inventory_store, broker._inventory_frame,
                broker._inventory_selection_binding, broker._inventory_delivery_authority,
                broker._inventory_current_frame)
        need(all(a is b for a, b in zip(refs, pending['inventory_refs']))
             and session._service is refs[0] and session._reader is self.reader
             and session._backend is self.reader.backend and session._store is refs[1],
             'MANUAL_USE_ITEM_INVENTORY_BINDING_CHANGED')
        # Pure original object guard: full Store/source/delivery checks remain
        # in the actual ItemUseSession hooks, never a caller-provided verdict.
        PersistentBroker._inventory_selection_frame_current(broker, current[0].writer, current[1], refs[2])
        count, before = session.accepted_count, pending['item_before']
        need(type(count) is int and before <= count <= before + (0 if admission else 1),
             'MANUAL_USE_ITEM_INTENT_COUNTER_AMBIGUOUS')
        need(self.state['status'] != 'UNKNOWN', 'MANUAL_MOVE_TERMINAL')
        if self._item_use_entry_policy_bound is not None:
            entry = pending.get('entry_binding')
            need(type(entry) is tuple and len(entry) == 7
                 and entry[0] is self._item_use_entry_policy_bound
                 and entry[2] is session and type(entry[3]) is int and entry[3] == before
                 and entry[4] is refs[3] and entry[5] is refs[5]
                 and type(entry[6]) is bool and entry[6] is (before == 0)
                 and pending['already_open_entry'] is entry[6],
                 'MANUAL_USE_ITEM_PENDING_ENTRY_CHANGED')
            generation = entry[1]
            need(type(generation) is self._item_use_entry_generation_type
                 and PersistentBroker.inventory_selection_current is self._item_use_entry_generation_current
                 and self._item_use_entry_generation_current(broker, current[0].writer) is generation
                 and generation is broker._inventory_generation and generation.phase == 'ACTIVE'
                 and generation.item_use_session is session and generation.selection_binding is entry[4]
                 and generation.current_frame is entry[5],
                 'MANUAL_USE_ITEM_ENTRY_GENERATION_CHANGED')
        if self._use_item_current_entry_bound:
            entry = pending.get('current_entry_binding')
            need(type(entry) is tuple and len(entry) == 5 and entry[0] is CURRENT_ENTRY_ONCE
                 and entry[2] is session and entry[3] is refs[3] and entry[4] is refs[5],
                 'MANUAL_USE_ITEM_CURRENT_ENTRY_BINDING_CHANGED')
            generation = entry[1]
            need(type(generation) is self._item_use_entry_generation_type
                 and PersistentBroker.inventory_selection_current is self._item_use_entry_generation_current
                 and self._item_use_entry_generation_current(broker, current[0].writer) is generation
                 and generation is broker._inventory_generation and generation.phase == 'ACTIVE'
                 and generation.item_use_session is session and generation.selection_binding is entry[3]
                 and generation.current_frame is entry[4],
                 'MANUAL_USE_ITEM_CURRENT_ENTRY_GENERATION_CHANGED')
        return current

    def submit_use_item(self, player_uid, item_identifier, map_id):
        """One explicit item identity; native alone resolves rawkey/lease/params."""
        if self.state['status'] == 'UNKNOWN':
            return dict(self.state)
        if self._busy or threading.get_ident() != self._thread:
            return self._terminal('MANUAL_MOVE_REENTRANT_OR_THREAD')
        if self.pending is not None:
            return dict(self.state, reason='MANUAL_MOVE_PENDING', accepted=False)
        entered = False
        try:
            self._enter(); entered = True
            self.state.update(phase='ADMISSION', native_attempted=False)
            self._observation = self._attack_observations = self._last_attack_action = None
            need(self.allow_use_item is True, 'MANUAL_USE_ITEM_DISABLED')
            need(all(type(n) is int for n in (player_uid, item_identifier, map_id))
                 and 0 < player_uid <= 0xffffffffffffffff and 0 < item_identifier <= 0xffffffffffffffff
                 and 0 <= map_id <= 0x7fffffff, 'MANUAL_USE_ITEM_UID_MAP_REQUIRED')
            from tools.local_original_session import item_use_session, inventory
            from tools.local_original_session.inventory_store import InventoryStore
            now, current = self._clock(), self._current()
            need(current[6]['candidate_sha256'] == USE_ITEM_IMAGE_SHA,
                 'MANUAL_USE_ITEM_PROGRAM_IMAGE_REQUIRED')
            need((current[3].uid, current[3].map_id) == (player_uid, map_id),
                 'MANUAL_USE_ITEM_SELECTED_UID_MAP_REQUIRED')
            broker, cls = current[0].broker, self._item_use_type
            session = broker._item_use_session
            need(cls is item_use_session.ItemUseSession and type(session) is cls
                 and broker.realm._item_use_session is session and session.broker is broker
                 and not session.closed and session.policy == item_use_session.POLICY
                 and broker.policy.item_use_intent is True
                 and type(session.accepted_count) is int
                 and 0 <= session.accepted_count < item_use_session.U64_MAX,
                 'MANUAL_USE_ITEM_REAL_SESSION_REQUIRED')
            refs = (broker._inventory_service, broker._inventory_store, broker._inventory_frame,
                    broker._inventory_selection_binding, broker._inventory_delivery_authority,
                    broker._inventory_current_frame)
            need(type(refs[0]) is inventory.InventoryService and refs[0].reader is self.reader
                 and refs[0].broker is broker and type(refs[1]) is InventoryStore
                 and type(refs[2]) is bytes and type(refs[3]) is tuple and len(refs[3]) == 11
                 and refs[4] is not None and type(refs[5]) is bytes,
                 'MANUAL_USE_ITEM_DELIVERED_INVENTORY_REQUIRED')
            self.pending = dict(kind='UseItem', phase='ADMISSION', native_attempted=False,
                request=None, initial=current[3], before=current[7], started=now,
                item_identifier=item_identifier, item_session=session, inventory_refs=refs,
                item_before=session.accepted_count, checked_ns=None, native=None, result_identity=None)
            if self.use_item_already_open:
                self.pending['already_open_entry'] = True
            if self._item_use_entry_policy_bound is not None:
                # Selection is made once from this real session's ORIGINAL
                # admission counter, never its later in-flight counter.
                before = self.pending['item_before']
                already_open = before == 0
                self.pending['entry_binding'] = (self._item_use_entry_policy_bound,
                    broker._inventory_generation, session, before, refs[3], refs[5], already_open)
                self.pending['already_open_entry'] = already_open
            if self._use_item_current_entry_bound:
                # The host binds only capability and current authority. The
                # original received counter never chooses a Native entry.
                self.pending['current_entry_capability'] = CURRENT_ENTRY_ONCE
                self.pending['current_entry_binding'] = (CURRENT_ENTRY_ONCE,
                    broker._inventory_generation, session, refs[3], refs[5])
            self._use_item_current(admission=True)
            self._pending_state()
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered:
                self._busy = False
        return dict(self.state)

    async def _poll_use_item(self):
        entered = False
        try:
            self._enter(); entered = True
            pending, now = self.pending, self._clock()
            current = self._use_item_current(admission=pending['phase'] == 'ADMISSION')
            hwnd = self._window(current)
            need(now - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            samples = [value for value in (self.last_sample_ns, pending['checked_ns']) if value is not None]
            if samples and now - max(samples) < SAMPLE_NS:
                return dict(self.state)
            async with current[1]['operation_lock']:
                current = self._use_item_current(admission=pending['phase'] == 'ADMISSION')
                pending['checked_ns'] = now
                if pending['phase'] == 'ADMISSION':
                    observed = self._observe(current, now, admitting=True)
                    if self.state.get('reason') == 'MANUAL_MOVE_TYPED_READ_CHANGED_ADMISSION':
                        self._pending_state('MANUAL_USE_ITEM_PLAYER_ADMISSION_PENDING')
                        return dict(self.state)
                    need(observed == (True, True), 'MANUAL_USE_ITEM_PLAYER_IDLE_REQUIRED')
                    current = self._use_item_current(admission=True)
                    need(await self._item_use_validate(pending['item_session'], current[0].writer,
                         pending['item_identifier']) is True, 'MANUAL_USE_ITEM_CURRENT_ITEM_REQUIRED')
                    current = self._use_item_current(admission=True)
                    need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                    self._publish(current, hwnd)
                else:
                    need(await self._item_use_validate(pending['item_session'], current[0].writer,
                         pending['item_identifier']) is True, 'MANUAL_USE_ITEM_CURRENT_ITEM_REQUIRED')
                    current = self._use_item_current()
                    need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                    self._use_item_result(current)
                    if pending['item_session'].accepted_count != pending['item_before'] + 1 or pending['native'] is None:
                        return dict(self.state)
                    session, policy = pending['item_session'], current[0].broker.policy
                    offset = pending['event_start'] - (policy.events - len(policy.log))
                    need(0 <= offset <= len(policy.log), 'MANUAL_USE_ITEM_RX_PROOF_DROPPED')
                    received = [e for e in list(policy.log)[offset:] if e[0] == 'rx'
                        and e[1] == current[1]['peer']['endpoint_port'] and e[2] == 0x0960]
                    need(len(received) == 1 and current[1]['policy_row'].received > pending['received_base'],
                         'MANUAL_USE_ITEM_CS0960_UNKNOWN')
                    need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                    current = self._use_item_current()
                    need(self._item_use_matches(session, current[0].writer, pending['item_identifier'],
                         pending['item_before'] + 1) is True, 'MANUAL_USE_ITEM_RECEIVED_REQUEST_MISMATCH')
                    task = asyncio.current_task()
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError()
                    need(session.accepted_count == pending['item_before'] + 1
                         and session.last_invalidation is None and self.state['status'] != 'UNKNOWN',
                         'MANUAL_USE_ITEM_CURRENT_INTENT_UNKNOWN')
                    self.pending = None
                    self.state = dict(status='COMMITTED', reason=None, sequence=self.sequence,
                        automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
                        command='UseItem', proof_scope='VALIDATED_ITEM_USE_INTENT_ONLY',
                        use_effect='UNKNOWN', ack='UNKNOWN', equipped='UNKNOWN', render='UNKNOWN', save='UNKNOWN')
        except asyncio.CancelledError:
            self._terminal('MANUAL_USE_ITEM_CANCELLED')
            raise
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered:
                self._busy = False
        return dict(self.state)

    async def _attack_sample(self, current):
        pending = self.pending
        # The original broker row lock serializes this awaited owner proof with
        # native ingress and the real CS4E30 handler. There is no second task.
        async with current[1]['operation_lock']:
            current = self._attack_current(admission=pending['phase'] == 'ADMISSION')
            now = self._clock()
            need(now - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            current = self._attack_current(admission=pending['phase'] == 'ADMISSION')
            self.last_sample_ns = now
            observer = self._attack_observer
            sample = observer.sample  # Exact original bound implementation, checked before/after await.
            row = await sample(current[0].writer, pending['target_uid'], now_ns=now)
            completed = self._clock()
            self.last_sample_ns = completed  # Conservative spacing after the awaited read.
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            need(self.pending is pending, 'MANUAL_ATTACK_PENDING_CHANGED')
            need(self._attack_observer is observer, 'MANUAL_ATTACK_SAME_OBSERVER_TARGETS_REQUIRED')
            self._attack_current(admission=pending['phase'] == 'ADMISSION')
            need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            self._attack_current(admission=pending['phase'] == 'ADMISSION')
        need(type(row) is dict, 'MANUAL_ATTACK_NPC_OBSERVATION_UNKNOWN')
        self._observation = {'npc_' + key: value if type(value) is str
            and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,95}', value) else None
            for key in ('status', 'reason') for value in (row.get(key),)}
        stage = row.get('observation_stage')
        if type(stage) is str and stage in _NPC_OBSERVATION_STAGES:
            self._observation['npc_observation_stage'] = stage
        self.state['observation'] = dict(self._observation)
        projection = pending['attack_projection']
        if _rechecked_npc_incomplete(row, pending['target_uid'], pending['initial'].map_id, projection[2:4]):
            # This exact producer finished all source/authority checks but did
            # not produce a strict snapshot. Keep this same claim/phase/clock;
            # no ready/completion progress, native publication or replay.
            self._observation['npc_read_consistency'] = row['read_consistency']
            self.state['observation'] = dict(self._observation)
            return None
        need(row.get('status') == 'OBSERVED' and row.get('source_contract_valid') is True
             and row.get('stable_double_read') is True and row.get('snapshot_atomic') is False
             and type(row.get('uid')) is int and row['uid'] == pending['target_uid']
             and type(row.get('map_id')) is int and row['map_id'] == pending['initial'].map_id
             and row.get('coordinates_match') is True
             and _grid(row.get('server_grid')) == _grid(row.get('client_grid')) == projection[2:4],
             'MANUAL_ATTACK_NPC_OBSERVATION_UNKNOWN')
        pending['npc_completed_ns'] = completed
        return row

    def _action_projection(self, row, now, strict_idle):
        def kind(group, slot, expected):
            value = (row.get(group) or {}).get(slot, {})
            if value.get('status') != 'OBSERVED':
                return None
            return value.get('present') is True and value.get('kind') == expected
        def pair(slot):
            value = (row.get('attacker') or {}).get(slot, {})
            return (value.get('selected_pair_matches') if value.get('status') == 'OBSERVED'
                    and value.get('kind') == 'AttackAction' else None)
        projected = dict(status=row['status'], reason=row['reason'], at_ns=now, strict_idle=strict_idle,
            current_attack=kind('attacker', 'current', 'AttackAction'),
            queued_attack=kind('attacker', 'queue_head', 'AttackAction'),
            current_pair=pair('current'), queued_pair=pair('queue_head'),
            damaged_current=kind('target', 'current', 'DamagedAction'),
            damaged_queued=kind('target', 'queue_head', 'DamagedAction'),
            death_current=kind('target', 'current', 'DeathAction'),
            death_queued=kind('target', 'queue_head', 'DeathAction'))
        for source, target, minimum, maximum in (
                ('combined_typed_bytes_requested', 'combined_bytes', 0, 24576),
                ('refused_read_bytes', 'refused_bytes', 1, 4096),
                ('shortfall_at_refused_read', 'shortfall_bytes', 1, 4096)):
            value = row.get(source)
            projected[target] = value if type(value) is int and minimum <= value <= maximum else None
        field = row.get('typed_read_changed_field')
        if (row.get('status') == 'UNKNOWN' and row.get('reason') == 'ATTACK_OBSERVE_TYPED_READ_CHANGED'
                and row.get('typed_read_changed_origin') == 'FINAL_PHYSICAL_READBACK'
                and type(field) is str and field in attack_action_observe.READBACK_FIELDS):
            # One small enum combines this known readback origin and field.
            # It carries no raw address/value, admission or retry permission.
            projected['read_field'] = attack_action_observe.READBACK_FIELDS[field]
        if (row.get('status') == 'UNKNOWN'
                and row.get('reason') == 'ATTACK_OBSERVE_COUNT_ACTION_UNCLASSIFIED'):
            if field == 'SHARED_OWNER_COUNT' and row.get('typed_read_changed_origin') == 'FINAL_PHYSICAL_READBACK':
                projected['read_field'] = attack_action_observe.READBACK_FIELDS[field]
            refusal = row.get('count_action_refusal')
            if type(refusal) is int and 1 <= refusal <= 8:
                projected['count_refusal'] = refusal  # Output only; never admission/wait authority.
                rva = row.get('count_action_type_rva')
                if refusal in (1, 3, 5, 7) and type(rva) is int and 0 <= rva < attack_action_observe.READBACK_TYPE_RVA_LIMIT:
                    projected['count_type_rva'] = rva
        return projected

    async def _action_sample(self, current, stage, *, strict_idle=False, feedback_intent=None):
        """One prepared retained read inside the existing row lock and slot."""
        pending, observer = self.pending, self._attack_action_observer
        need(not pending.get('lethal_preparation') or stage == 'pre_command',
             'MANUAL_LETHAL_PREPARATION_POST_SNAPSHOT_FORBIDDEN')
        async with current[1]['operation_lock']:
            current = self._attack_current(admission=pending['phase'] == 'ADMISSION')
            need(attack_action_observe.AttackActionObserver is _ACTION_OBSERVER_TYPE
                 and type(observer) is _ACTION_OBSERVER_TYPE
                 and _ACTION_OBSERVER_TYPE.prepare is _ACTION_OBSERVER_PREPARE
                 and _ACTION_OBSERVER_TYPE.collect is _ACTION_OBSERVER_COLLECT
                 and type(observer.prepare) is MethodType and observer.prepare.__self__ is observer
                 and observer.prepare.__func__ is _ACTION_OBSERVER_PREPARE
                 and type(observer.collect) is MethodType and observer.collect.__self__ is observer
                 and observer.collect.__func__ is _ACTION_OBSERVER_COLLECT
                 and observer is pending['action_observer'] and observer.reader is self.reader
                 and observer.targets.broker is current[0].broker,
                 'MANUAL_ATTACK_ACTION_SAME_OBSERVER_REQUIRED')
            session = pending['attack_session']
            feedback_frame = session._feedback_frame if feedback_intent is not None else None
            if feedback_intent is not None:
                need(session.feedback_drained == pending['feedback_before'] + 1
                     and session.validate_feedback(current[0].writer, session._feedback_frame, state='DRAINED')
                         is feedback_intent, 'MANUAL_ATTACK_CURRENT_FEEDBACK_REQUIRED')
            now = self._clock()
            need(now - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            self.last_sample_ns = now
            await observer.prepare(current[0].writer, pending['target_uid'], now_ns=now)
            need(self.pending is pending, 'MANUAL_ATTACK_PENDING_CHANGED')
            current = self._attack_current(admission=pending['phase'] == 'ADMISSION')
            row, _count = self.reader.sample(include_input_state=False, attack_action_observer=observer)
            self.last_sample_ns = self._clock()
            current = self._attack_current(admission=pending['phase'] == 'ADMISSION')
            raw = row.get('attack_action')
            if type(raw) is dict:
                if stage == 'post_feedback':
                    self._attack_observations.pop('post_command', None)
                self._attack_observations[stage] = self._action_projection(raw, now, None)
            cache_changed = (stage == 'pre_command' and pending['phase'] == 'ADMISSION'
                and pending['native_attempted'] is False and type(raw) is dict
                and raw.get('reason') == 'ATTACK_OBSERVE_CACHE_TYPED_READ_CHANGED')
            rechecked_count = (stage == 'pre_command' and pending['phase'] == 'ADMISSION'
                and pending['native_attempted'] is False
                and _rechecked_action_count_incomplete(raw, pending['initial'].uid,
                                                      pending['target_uid'], pending['initial'].map_id))
            idle_discarded = (stage == 'next_strict_idle' and strict_idle is True
                and self.observe_attack_feedback is True and pending['phase'] == 'NATIVE_WAIT'
                and pending['native_attempted'] is True and feedback_intent is not None
                and pending['feedback_intent'] is feedback_intent
                and pending['feedback_frame'] is session._feedback_frame
                and self._attack_observations.get('post_feedback', {}).get('status') == 'OBSERVED'
                and type(raw) is dict and raw.get('reason') in
                    ('ATTACK_OBSERVE_TYPED_READ_CHANGED', 'ATTACK_OBSERVE_CACHE_TYPED_READ_CHANGED'))
            respawn_post_discarded = (stage == 'post_feedback' and strict_idle is False
                and type(pending.get('respawn_attack')) is _RespawnAttackClaim
                and pending['respawn_attack'] is self._respawn_attack_claim
                and self.observe_attack_feedback is True and pending['phase'] == 'NATIVE_WAIT'
                and pending['native_attempted'] is True and pending['native'] is not None
                and feedback_intent is not None and pending['feedback_intent'] is None
                and pending['feedback_frame'] is None and type(raw) is dict
                and raw.get('status') == 'UNKNOWN'
                and raw.get('reason') == 'ATTACK_OBSERVE_TYPED_READ_CHANGED'
                and raw.get('typed_read_changed_field') == 'ACTION_QUEUE_HEADER'
                and raw.get('typed_read_changed_origin') == 'FINAL_PHYSICAL_READBACK')
            if respawn_post_discarded:
                self._respawn_attack_current(pending['respawn_attack'])
                expected = attack_action_observe.empty('ATTACK_OBSERVE_TYPED_READ_CHANGED')
                typed, combined = (raw.get(key) for key in ('typed_bytes_requested', 'combined_typed_bytes_requested'))
                need(type(typed) is type(combined) is int
                     and 0 <= typed <= combined <= attack_action_observe.BYTE_LIMIT,
                     'MANUAL_RESPAWN_POST_READ_SHAPE_REQUIRED')
                expected.update(typed_bytes_requested=typed, combined_typed_bytes_requested=combined,
                    typed_read_changed_field='ACTION_QUEUE_HEADER',
                    typed_read_changed_origin='FINAL_PHYSICAL_READBACK')
                need(set(raw) == set(expected)
                     and all(type(raw[key]) is type(value) and raw[key] == value
                             for key, value in expected.items()),
                     'MANUAL_RESPAWN_POST_READ_SHAPE_REQUIRED')
            if idle_discarded:
                expected = attack_action_observe.empty(raw['reason'])
                if _rechecked_action_count_incomplete(raw, pending['initial'].uid,
                                                     pending['target_uid'], pending['initial'].map_id):
                    # Preserve the original feedback-bound next-idle discard
                    # only. This never returns to admission or grants a Post.
                    expected.update(actor_uid=pending['initial'].uid, target_uid=pending['target_uid'],
                        map_id=pending['initial'].map_id,
                        read_consistency='RECHECKED_SHARED_COUNT_FINAL_READBACK',
                        source_owner_revalidated=True)
                field, origin = (raw.get(key) for key in ('typed_read_changed_field', 'typed_read_changed_origin'))
                need((field is origin is None) or type(field) is str
                     and field in attack_action_observe.READBACK_FIELDS
                     and type(origin) is str and origin == 'FINAL_PHYSICAL_READBACK',
                     'MANUAL_ATTACK_IDLE_READ_SHAPE_REQUIRED')
                expected.update(typed_read_changed_field=field, typed_read_changed_origin=origin)
                typed, combined = (raw.get(key) for key in ('typed_bytes_requested', 'combined_typed_bytes_requested'))
                need(type(typed) is type(combined) is int and 0 <= typed <= combined <= attack_action_observe.BYTE_LIMIT,
                     'MANUAL_ATTACK_IDLE_READ_SHAPE_REQUIRED')
                expected.update(typed_bytes_requested=typed, combined_typed_bytes_requested=combined)
                need(set(raw) == set(expected) and all(type(raw[key]) is type(value) and raw[key] == value
                     for key, value in expected.items()), 'MANUAL_ATTACK_IDLE_READ_SHAPE_REQUIRED')
            if cache_changed:
                expected = attack_action_observe.empty('ATTACK_OBSERVE_CACHE_TYPED_READ_CHANGED')
                for key in ('typed_bytes_requested', 'combined_typed_bytes_requested'):
                    need(type(raw.get(key)) is int and 0 <= raw[key] <= attack_action_observe.BYTE_LIMIT,
                         'MANUAL_ATTACK_ADMISSION_READ_SHAPE_REQUIRED')
                    expected[key] = raw[key]
                need(set(raw) == set(expected) and all(type(raw[key]) is type(value) and raw[key] == value
                     for key, value in expected.items()), 'MANUAL_ATTACK_ADMISSION_READ_SHAPE_REQUIRED')
            need(cache_changed or idle_discarded or rechecked_count or respawn_post_discarded
                 or type(raw) is dict and raw.get('status') == 'OBSERVED'
                 and raw.get('source_contract_valid') is True and raw.get('stable_double_read') is True
                 and (raw.get('actor_uid'), raw.get('target_uid'), raw.get('map_id')) ==
                    (pending['initial'].uid, pending['target_uid'], pending['initial'].map_id),
                 'MANUAL_ATTACK_ACTION_SNAPSHOT_UNKNOWN')
            idle = None
            if respawn_post_discarded:
                # Discarded action bytes grant no post/latch/idle evidence.
                # Only this query's independent current world/motion permits
                # waiting for the next original NPC and full action slots.
                need(self._observe(current, now, _sampled=row)[0] is True,
                     'MANUAL_RESPAWN_POST_READ_AUTHORITY_UNKNOWN')
                idle = False
            elif idle_discarded:
                # Validate the same query's original scene/world/motion gates,
                # but consume no idle verdict or discarded action bytes.
                need(self._observe(current, now, _sampled=row)[0] is True,
                     'MANUAL_ATTACK_IDLE_READ_AUTHORITY_UNKNOWN')
                idle = False
            elif rechecked_count:
                need(self._observe(current, now, _sampled=row, admitting=True) == (True, True),
                     'MANUAL_ATTACK_ADMISSION_READ_AUTHORITY_UNKNOWN')
                idle = False
            elif strict_idle:
                # MoveState intentionally does not qualify AttackAction. A
                # separately typed, owner-bound Attack snapshot can only wait;
                # eventual completion still uses every original strict gate.
                busy_attack = (stage != 'pre_command' and raw['attacker']['current'].get('kind') == 'AttackAction'
                    and raw['attacker']['current'].get('status') == 'OBSERVED')
                admitting = (stage == 'pre_command' and pending['phase'] == 'ADMISSION'
                             and pending['native_attempted'] is False)
                idle = False if busy_attack else self._observe(current, now, _sampled=row,
                                                               admitting=admitting) == (True, True)
                if admitting and self.state.get('reason') == 'MANUAL_MOVE_TYPED_READ_CHANGED_ADMISSION':
                    # Only the real producer's discarded MoveState shape can
                    # wait. No partial busy/type/owner values become admission.
                    motion = row['move_state']
                    requested = motion.get('typed_bytes_requested')
                    expected = move_state.empty('MOVE_TYPED_READ_CHANGED', requested)
                    field = motion.get('typed_read_changed_field')
                    if 'typed_read_changed_field' in motion:
                        need(type(field) is str and field in move_state.READBACK_FIELDS,
                             'MANUAL_ATTACK_ADMISSION_READ_SHAPE_REQUIRED')
                        expected['typed_read_changed_field'] = field
                    need(type(requested) is int and 0 <= requested <= 16384
                         and set(motion) == set(expected)
                         and all(type(motion[key]) is type(value) and motion[key] == value
                                 for key, value in expected.items())
                         and all(all(type(motion[group][key]) is type(value)
                                     for key, value in expected[group].items()) for group in move_state.GROUPS),
                         'MANUAL_ATTACK_ADMISSION_READ_SHAPE_REQUIRED')
            if feedback_intent is not None:
                need(session.feedback_drained == pending['feedback_before'] + 1
                     and session.validate_feedback(current[0].writer, session._feedback_frame, state='DRAINED')
                         is feedback_intent, 'MANUAL_ATTACK_CURRENT_FEEDBACK_REQUIRED')
            need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            if idle_discarded:
                self._attack_current()
                need(self.pending is pending and pending['feedback_intent'] is feedback_intent
                     and pending['feedback_frame'] is session._feedback_frame
                     and session.validate_feedback(current[0].writer, pending['feedback_frame'], state='DRAINED')
                         is feedback_intent, 'MANUAL_ATTACK_CURRENT_FEEDBACK_REQUIRED')
            if respawn_post_discarded:
                current = self._attack_current()
                self._respawn_attack_current(pending['respawn_attack'])
                self._attack_result(current)
                need(self.pending is pending and pending['feedback_intent'] is None
                     and pending['feedback_frame'] is None
                     and session._feedback_frame is feedback_frame
                     and session.feedback_drained == pending['feedback_before'] + 1
                     and session.validate_feedback(current[0].writer, session._feedback_frame, state='DRAINED')
                         is feedback_intent,
                     'MANUAL_ATTACK_CURRENT_FEEDBACK_REQUIRED')
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            if cache_changed and idle:
                self.state['reason'] = 'MANUAL_ATTACK_CACHE_READ_CHANGED_ADMISSION'
                idle = False  # No action proof or admission; next slot must refresh NPC first.
            if rechecked_count:
                self.state['reason'] = 'MANUAL_ATTACK_RECHECKED_COUNT_ADMISSION'
            self._attack_observations[stage] = self._action_projection(raw, now,
                None if cache_changed or idle_discarded or rechecked_count or respawn_post_discarded else idle)
            self.state['attack_observations'] = dict(self._attack_observations)
            if respawn_post_discarded:
                # Never read by admission, waiting or completion decisions.
                self._respawn_post_discarded_claim = pending['respawn_attack']
                self._respawn_post_discarded = dict(at_ns=now, read_field=3,
                    combined_bytes=raw['combined_typed_bytes_requested'])
            return idle

    def _feedback_intent(self, current, *, _pending=None):
        pending = self.pending if _pending is None else _pending
        session = pending['attack_session']
        if session.accepted_count != pending['attack_before'] + 1 or pending['native'] is None:
            return None
        intent = session.current_intent()
        need(type(intent) is attack_session.AttackIntent and intent.accepted_ordinal == pending['attack_before'] + 1
             and intent._bound._authority is pending['attack_targets']
             and intent._bound._writer is current[0].writer and intent._bound.attacker is pending['initial']
             and (intent._bound.target_uid, intent._bound.map_id) == (pending['target_uid'], pending['initial'].map_id),
             'MANUAL_ATTACK_CURRENT_INTENT_UNKNOWN')
        policy = current[0].broker.policy
        offset = pending['event_start'] - (policy.events - len(policy.log))
        need(0 <= offset <= len(policy.log) and current[1]['policy_row'].received > pending['received_base']
             and any(e[0] == 'rx' and e[1] == current[1]['peer']['endpoint_port'] and e[2] == 0x4e30
                     for e in list(policy.log)[offset:]), 'MANUAL_ATTACK_CS4E30_UNKNOWN')
        pending['attack_targets'].revalidate(intent._bound)
        return intent

    async def _poll_feedback_observation(self, current):
        pending = self.pending
        if not pending['feedback_action_next']:
            if await self._attack_sample(current) is None:
                self._pending_state('MANUAL_ATTACK_NPC_OBSERVATION_PENDING')
                return
            pending['feedback_action_next'] = True
            self._pending_state('MANUAL_ATTACK_ACTION_OBSERVATION_PENDING')
            return
        pending['feedback_action_next'] = False
        intent = self._feedback_intent(self._attack_current())
        if intent is None or pending['attack_session']._feedback_state != 'DRAINED':
            # Command-after/response-before is a raw snapshot only. It is not
            # a proof that client-wide self prediction exists or is absent.
            await self._action_sample(current, 'post_command')
            self._pending_state('MANUAL_ATTACK_FEEDBACK_DRAIN_PENDING')
            return
        if pending['feedback_intent'] is None:
            post = await self._action_sample(current, 'post_feedback', feedback_intent=intent)
            if post is False:
                self._pending_state('MANUAL_RESPAWN_ATTACK_POST_SNAPSHOT_PENDING')
                return  # No latch: next original NPC slot must precede a new Post.
            pending['feedback_intent'], pending['feedback_frame'] = intent, pending['attack_session']._feedback_frame
            self._pending_state('MANUAL_ATTACK_STRICT_IDLE_PENDING')
            return
        need(intent is pending['feedback_intent'] and pending['attack_session']._feedback_frame is pending['feedback_frame'],
             'MANUAL_ATTACK_CURRENT_FEEDBACK_REQUIRED')
        idle = await self._action_sample(current, 'next_strict_idle', strict_idle=True, feedback_intent=intent)
        if not idle:
            self._pending_state('MANUAL_ATTACK_STRICT_IDLE_PENDING')
            return
        async with current[1]['operation_lock']:
            current = self._attack_current()
            session = pending['attack_session']
            need(self.pending is pending and session.current_intent() is intent
                 and session._feedback_frame is pending['feedback_frame']
                 and session.feedback_drained == pending['feedback_before'] + 1
                 and session.validate_feedback(current[0].writer, pending['feedback_frame'], state='DRAINED') is intent,
                 'MANUAL_ATTACK_CURRENT_FEEDBACK_REQUIRED')
            self._attack_current()
            need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            self._attack_current()  # The clock callback cannot change current ownership unnoticed.
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            need(self.pending is pending and session._current is intent
                 and session._feedback_frame is pending['feedback_frame']
                 and session.feedback_drained == pending['feedback_before'] + 1
                 and session.accepted_count == pending['attack_before'] + 1
                 and self.state['status'] != 'UNKNOWN', 'MANUAL_ATTACK_CURRENT_INTENT_UNKNOWN')
            self.pending = None
            self.state = dict(status='COMMITTED', reason=None, sequence=self.sequence,
                automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
                command='AttackTarget', proof_scope='VALIDATED_ATTACK_INTENT_ONLY', combat_effect='UNKNOWN',
                observation_scope='READONLY_ACTION_SNAPSHOTS',
                attack_observations={key: value for key, value in self._attack_observations.items() if key != 'post_command'})
            if pending.get('respawn_attack') is not None:
                self._complete_respawn_attack(pending['respawn_attack'], pending, current)

    def _respawn_attack_current(self, claim):
        from tools.local_original_session import npc_respawn
        need(type(claim) is _RespawnAttackClaim and self._respawn_attack_claim is claim
             and self._respawn_attack_claimed is True and self.allow_respawn_attack is True
             and self._respawn_attack_options[0] is True
             and self._respawn_attack_options[1] is self._attack_purpose
             and self.lethal_attack_preparation is self._lethal_mode is True
             and self._attack_purpose[0] is True and self.allow_attack is True
             and self.observe_attack_feedback is True and self.allow_attack_replacement is False
             and self._lethal_preparation_completed is claim.root_proof
             and type(self._respawn_attack_claims) is tuple
             and self._respawn_attack_claims[-1] is claim
             and len(self._respawn_attack_claims) == claim.generation.ordinal
             and (claim.generation.ordinal == 1 and claim.old_proof is claim.root_proof
                  or claim.generation.ordinal == 2 and type(self._respawn_attack_completions) is tuple
                  and self._respawn_attack_completions[0] is claim.old_proof
                  and claim.old_proof.claim is self._respawn_attack_claims[0]
                  and claim.old_proof.generation is claim.old_generation)
             and self._reservation is True and type(self.sequence) is int
             and claim.native_before <= self.sequence <= claim.native_before + 1
             and self._action_sequence == self.sequence and self._action_bound is self._bound,
             'MANUAL_RESPAWN_ATTACK_ONCE_PURPOSE_REQUIRED')
        current = self._current()
        broker, writer, row = current[0].broker, current[0].writer, current[1]
        service, receipt = claim.service, claim.receipt
        need(type(service) is npc_respawn.Service and type(receipt) is npc_respawn.Receipt
             and service is broker._npc_respawn is broker.realm._npc_respawn
             and service.require_current.__func__ is _RESPAWN_REQUIRE_CURRENT
             and service.current_generation.__func__ is _RESPAWN_CURRENT_GENERATION
             and service._phases.get(id(writer)) == 'COMMITTED'
             and service.require_current(receipt) is claim.generation
             and receipt.generation is claim.generation and receipt.old_generation is claim.old_generation
             and receipt.writer is writer is claim.writer and receipt.row is row is claim.row
             and broker is claim.broker and broker.source_guard is claim.source_guard
             and current[3].map_id == receipt.spawn.map_id and current[3].uid == claim.player_uid
             and type(receipt.generation.ordinal) is type(receipt.old_generation.ordinal) is int
             and receipt.generation.ordinal in (1, 2)
             and receipt.generation.ordinal == receipt.old_generation.ordinal + 1
             and claim.accepted_before == claim.native_before == receipt.generation.ordinal
             and receipt.old_generation.frames is claim.old_proof.lifetime[5]
             and receipt.generation.frames is broker.realm._npc_frames[id(writer)]
             and receipt.mover is receipt.generation.mover is broker.realm.npc_mover(writer)
             and receipt.old_generation.mover.closed is True,
             'MANUAL_RESPAWN_ATTACK_CURRENT_GENERATION_REQUIRED')
        old_source = claim.root_proof._pending['lethal_source']
        need(self.reader is old_source[0] and self.current is old_source[1]
             and self.clock_ns is old_source[2] and broker is old_source[3]
             and broker.source_guard is old_source[4] and claim.session is broker._attack_session
             and claim.session is broker.realm._attack_session and not claim.session.closed and not claim.session.fatal
             and claim.session._hp.provider is claim.provider is claim.session._hp_provider
             and claim.session.accepted_count in (claim.accepted_before, claim.accepted_before + 1)
             and claim.session.feedback_drained in (claim.feedback_before, claim.feedback_before + 1),
             'MANUAL_RESPAWN_ATTACK_SOURCE_OR_COUNTER_CHANGED')
        key = id(writer), receipt.spawn.uid
        if claim.session.accepted_count == claim.accepted_before:
            need(claim.session._current is None and claim.session._hp._entries.get(key) is None
                 and claim.session._notifications._records.get(key) is None,
                 'MANUAL_RESPAWN_ATTACK_FRESH_ENTRY_REQUIRED')
        return current

    def _claim_respawn_attack(self, receipt, player_uid, target_uid, map_id):
        from tools.local_original_session import npc_respawn, npc_hp
        need(self.allow_respawn_attack is self._respawn_attack_options[0] is True
             and type(self._respawn_attack_claims) is type(self._respawn_attack_completions) is tuple
             and len(self._respawn_attack_claims) == len(self._respawn_attack_completions) < 2,
             'MANUAL_RESPAWN_ATTACK_DISABLED_OR_CLAIMED')
        self._respawn_attack_claimed = True  # Historical once; never reset for a new generation.
        if not self._respawn_attack_claims:
            old = root = self.lethal_preparation_settled()
        else:
            old = self._respawn_attack_completed
            need(type(old) is _RespawnAttackCompleted
                 and self._respawn_attack_completions[-1] is old
                 and old._consumer is self and old.claim is self._respawn_attack_claims[-1]
                 and self._respawn_attack_claim is old.claim and self.pending is None
                 and self.state is old._state and self.state == old._state_data
                 and self.state['status'] == self.state['phase'] == 'COMMITTED',
                 'MANUAL_RESPAWN_ATTACK_PREVIOUS_COMPLETION_REQUIRED')
            root = old.claim.root_proof
            need(type(root) is _LethalPreparation and self._lethal_preparation_completed is root,
                 'MANUAL_RESPAWN_ATTACK_ROOT_PREPARATION_REQUIRED')
        current = self._current()
        need(all(type(v) is int for v in (player_uid, target_uid, map_id))
             and type(receipt) is npc_respawn.Receipt and receipt.writer is current[0].writer
             and receipt.row is current[1] and receipt.spawn.uid == target_uid == old.hp_result.target.uid
             and current[3].uid == player_uid and current[3].map_id == map_id == receipt.spawn.map_id
             and old.accepted_ordinal == len(self._respawn_attack_claims) + 1
             and self.sequence == old.sequence
             and self._reservation is True and self._action_sequence == old.sequence
             and self._action_bound is self._bound,
             'MANUAL_RESPAWN_ATTACK_EXPLICIT_RECEIPT_REQUIRED')
        broker, session = current[0].broker, current[0].broker._attack_session
        need(session is old.session and session.accepted_count == old.accepted_ordinal
             and session.feedback_drained == old._pending['feedback_before'] + 1
             and session.last_hp_result is old.hp_result and session._current is None,
             'MANUAL_RESPAWN_ATTACK_RETIRED_OLD_LIFE_REQUIRED')
        need(type(session._hp.provider) is npc_hp.ExplicitInputs and session._hp.provider is session._hp_provider,
             'MANUAL_RESPAWN_ATTACK_EXPLICIT_PROVIDER_REQUIRED')
        claim = _RespawnAttackClaim(receipt, receipt._service, receipt.generation, receipt.old_generation,
            old, root, current[0].writer, current[1], broker, session, broker.source_guard,
            session._hp.provider, player_uid, session.accepted_count, session.feedback_drained, self.sequence)
        self._respawn_attack_claims += (claim,)
        self._respawn_attack_claim = claim
        self._respawn_attack_current(claim)
        claim.source_guard()
        self._respawn_attack_current(claim)
        _source_quit_cancel_check()
        return claim

    def _respawn_attack_result(self, claim, pending, current):
        from tools.local_original_session import npc_hp
        session, writer, row = claim.session, claim.writer, claim.row
        need(row['operation_lock'].locked(), 'MANUAL_RESPAWN_ATTACK_ROW_LOCK_REQUIRED')
        self._respawn_attack_current(claim)
        self._attack_result(current, _pending=pending)
        intent = self._feedback_intent(current, _pending=pending)
        result = session.last_hp_result
        entry = session._hp._entries.get((id(writer), claim.receipt.spawn.uid))
        lifetime, target = session._hp_binding(writer, row, claim.receipt.spawn.uid)
        need(type(intent) is attack_session.AttackIntent and session.current_intent() is intent
             and intent is not claim.old_proof.intent
             and intent.accepted_ordinal == session.accepted_count == claim.accepted_before + 1
             and session.feedback_drained == claim.feedback_before + 1
             and session.validate_feedback(writer, session._feedback_frame, state='DRAINED') is intent
             and type(result) is npc_hp.Result and result is not claim.old_proof.hp_result
             and result.accepted_ordinal == intent.accepted_ordinal and result.hit.landed is True
             and result.before.alive is True and entry is not None and entry is not claim.old_proof.hp_entry
             and entry.writer is writer and entry.row is row and entry.intent is intent
             and entry.hp is result.after and entry.target == result.target == target
             and entry.lifetime[5] is claim.generation.frames and len(entry.lifetime) == len(lifetime)
             and all(a is b for a, b in zip(entry.lifetime, lifetime)),
             'MANUAL_RESPAWN_ATTACK_NEW_LAZY_HP_REQUIRED')
        # This subset consumes the existing immutable explicit provider rows.
        # No initialization call, HP value write or fake attack occurs here.
        provider = session._hp.provider
        need(type(provider) is npc_hp.ExplicitInputs, 'MANUAL_RESPAWN_ATTACK_EXPLICIT_PROVIDER_REQUIRED')
        provider_row, = [r for r in provider.rows if r.target == result.target]
        need(result.before is provider_row.hp and result.hit is provider_row.hit,
             'MANUAL_RESPAWN_ATTACK_LAZY_PROVIDER_INPUT_CHANGED')
        return intent, result, entry

    def _complete_respawn_attack(self, claim, pending, current):
        before = self._respawn_attack_result(claim, pending, current)
        claim.source_guard()
        current = self._attack_current(_pending=pending)
        actual = self._respawn_attack_result(claim, pending, current)
        need(all(a is b for a, b in zip(before, actual))
             and self.state['status'] == self.state['phase'] == 'COMMITTED'
             and self.state['proof_scope'] == 'VALIDATED_ATTACK_INTENT_ONLY'
             and self._attack_observations['post_feedback']['status'] == 'OBSERVED'
             and self._attack_observations['next_strict_idle']['status'] == 'OBSERVED'
             and self._attack_observations['next_strict_idle']['strict_idle'] is True,
             'MANUAL_RESPAWN_ATTACK_ORIGINAL_COMPLETION_REQUIRED')
        need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        current = self._attack_current(_pending=pending)
        final = self._respawn_attack_result(claim, pending, current)
        need(all(a is b for a, b in zip(actual, final)), 'MANUAL_RESPAWN_ATTACK_COMPLETED_LIFE_CHANGED')
        self._attack_result(current, _pending=pending)
        _source_quit_cancel_check()
        intent, result, entry = actual
        self._respawn_attack_completed = _RespawnAttackCompleted(self, claim, claim.receipt,
            claim.generation, claim.writer, claim.row, claim.session, intent, result, entry,
            entry.lifetime, self.sequence, intent.accepted_ordinal, pending, self.state, copy.deepcopy(self.state))
        self._respawn_attack_completions += (self._respawn_attack_completed,)

    def validate_respawn_attack(self, receipt):
        proof = self._respawn_attack_completed
        need(type(self) is ManualMoveCommands and type(proof) is _RespawnAttackCompleted
             and proof._consumer is self and proof.receipt is receipt
             and type(self._respawn_attack_completions) is tuple
             and self._respawn_attack_completions[-1] is proof
             and proof.claim is self._respawn_attack_claims[-1]
             and self.pending is None and self.state is proof._state and self.state == proof._state_data
             and self.sequence == proof.sequence and proof.row['operation_lock'].locked()
             and type(self.validate_respawn_attack) is MethodType
             and self.validate_respawn_attack.__func__ is RESPAWN_ATTACK_VALIDATE,
             'MANUAL_RESPAWN_ATTACK_COMPLETED_PROOF_REQUIRED')
        claim, pending = proof.claim, proof._pending
        current = self._respawn_attack_current(claim)
        actual = self._respawn_attack_result(claim, pending, current)
        expected = proof.intent, proof.hp_result, proof.hp_entry
        claim.source_guard()
        need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        current = self._attack_current(_pending=pending)
        after = self._respawn_attack_result(claim, pending, current)
        self._attack_result(current, _pending=pending)
        _source_quit_cancel_check()
        need(all(a is b is c for a, b, c in zip(actual, after, expected))
             and self._respawn_attack_completed is proof and self.state is proof._state
             and self.state == proof._state_data, 'MANUAL_RESPAWN_ATTACK_COMPLETED_LIFE_CHANGED')
        return proof

    def _attack_purpose_current(self, pending):
        claim = pending.get('respawn_attack')
        if claim is not None:
            need(pending.get('attack_purpose') is claim and pending.get('lethal_preparation') is False,
                 'MANUAL_RESPAWN_ATTACK_ONCE_PURPOSE_REQUIRED')
            self._respawn_attack_current(claim)
            return
        need(pending.get('attack_purpose') is self._attack_purpose
             and pending.get('lethal_preparation') is self._attack_purpose[0]
             and self.lethal_attack_preparation is self._lethal_mode is self._attack_purpose[0],
             'MANUAL_LETHAL_PREPARATION_PURPOSE_CHANGED')

    def _lethal_mode_current(self, pending):
        self._attack_purpose_current(pending)
        need(self.lethal_attack_preparation is self._lethal_mode is True
             and self.allow_attack is self.observe_attack_feedback is True
             and self.allow_attack_replacement is False
             and pending.get('lethal_preparation') is True,
             'MANUAL_LETHAL_PREPARATION_PURPOSE_CHANGED')
        source = pending['lethal_source']
        need(all(a is b for a, b in zip(source,
             (self.reader, self.current, self.clock_ns, source[3], source[3].source_guard)))
             and source[3] is pending['attack_targets'].broker,
             'MANUAL_LETHAL_PREPARATION_SOURCE_CHANGED')

    def _lethal_live(self, pending, current):
        """Original current lethal record, only under the existing row lock."""
        from tools.local_original_session import npc_death, npc_hp
        self._lethal_mode_current(pending)
        writer, row = current[0].writer, current[1]
        need(row['operation_lock'].locked(), 'MANUAL_LETHAL_PREPARATION_ROW_LOCK_REQUIRED')
        need(set(self._attack_observations) == {'pre_command'}
             and self._attack_observations['pre_command'] is pending['lethal_pre_snapshot']
             and self._attack_observations['pre_command'] == pending['lethal_pre_snapshot_data']
             and pending['lethal_pre_snapshot'].get('status') == 'OBSERVED'
             and pending['lethal_pre_snapshot'].get('strict_idle') is True,
             'MANUAL_LETHAL_PREPARATION_PRE_ONLY_REQUIRED')
        self._attack_result(current, _pending=pending)
        intent = self._feedback_intent(current, _pending=pending)
        session = pending['attack_session']
        need(pending['native'] is not None and type(intent) is attack_session.AttackIntent
             and session.feedback_drained == pending['feedback_before'] + 1
             and session.validate_feedback(writer, session._feedback_frame, state='DRAINED') is intent,
             'MANUAL_LETHAL_PREPARATION_DRAINED_FEEDBACK_REQUIRED')
        result = session.last_hp_result
        need(type(result) is npc_hp.Result and result.hit.landed is True and result.died is True
             and result.after.current == 0 and result.after.alive is False
             and result.accepted_ordinal == intent.accepted_ordinal == pending['attack_before'] + 1
             and result.target.uid == pending['target_uid'],
             'MANUAL_LETHAL_PREPARATION_CURRENT_HP_REQUIRED')
        hp, notifications = session._hp, session._notifications
        need(type(hp) is npc_hp.Authority and type(notifications) is npc_death.Notifications
             and notifications.service is session and notifications.death_policy == npc_death.DEATH_POLICY,
             'MANUAL_LETHAL_PREPARATION_REAL_NOTIFICATIONS_REQUIRED')
        key = id(writer), pending['target_uid']
        entry, record = hp._entries.get(key), notifications._records.get(key)
        need(record is not None and record.entry is entry and record.result is result
             and entry.intent is intent and entry.hp is result.after
             and notifications._record_current(writer, pending['target_uid'], record) is row
             and record.death.phase == 'DRAINED' and record.death.write_attempted is True
             and record.death.drained is True and record.remove is None and record.removed is False
             and type(record.death.wire) is bytes
             and npc_death.validate_frame(record.death.wire) == (npc_death.DEATH_OPCODE, pending['target_uid'])
             and record.death.wire == npc_death.frame(npc_death.DEATH_OPCODE, pending['target_uid']),
             'MANUAL_LETHAL_PREPARATION_CURRENT_DEATH_DRAIN_REQUIRED')
        return intent, result, entry, record, entry.lifetime, record.death, record.death.wire, session._feedback_frame

    async def _poll_lethal_preparation(self, current):
        pending = self.pending
        async with current[1]['operation_lock']:
            self._lethal_mode_current(pending)
            current = self._attack_current()
            session = pending['attack_session']
            if pending['native'] is None or session.accepted_count == pending['attack_before']:
                self._pending_state('MANUAL_LETHAL_PREPARATION_RECEIVE_PENDING')
                return
            if session._feedback_state != 'DRAINED':
                need(session._feedback_state in ('PREPARED', 'RESERVED', 'WRITE_ATTEMPTED'),
                     'MANUAL_LETHAL_PREPARATION_FEEDBACK_UNKNOWN')
                self._pending_state('MANUAL_LETHAL_PREPARATION_DRAIN_PENDING')
                return
            before = self._lethal_live(pending, current)
            need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            source_guard = pending['lethal_source'][3].source_guard
            source_guard()
            current = self._attack_current()
            after = self._lethal_live(pending, current)
            need(len(before) == len(after) and all(a is b for a, b in zip(before, after))
                 and self.pending is pending and self._lethal_preparation_completed is None,
                 'MANUAL_LETHAL_PREPARATION_LIFETIME_CHANGED')
            need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            _source_quit_cancel_check()
            self._lethal_mode_current(pending)
            current = self._attack_current()
            final = self._lethal_live(pending, current)
            self._attack_result(current, _pending=pending)
            _source_quit_cancel_check()
            need(all(a is b for a, b in zip(after, final)), 'MANUAL_LETHAL_PREPARATION_LIFETIME_CHANGED')
            # No callback/await between the final current identity check and
            # publishing this distinct, completed native preparation purpose.
            intent, result, entry, record, lifetime, death, wire, feedback = after
            state = dict(status='PREPARED', reason=None, sequence=self.sequence,
                automatic_retry=False, cleanup_required=False, phase='LETHAL_PREPARATION_READY',
                native_attempted=True, command='AttackTarget',
                proof_scope='CURRENT_LETHAL_NPC_DEATH_DRAIN_ONLY', client_death='UNKNOWN',
                attack_observations=dict(self._attack_observations))
            proof = _LethalPreparation(self, current[0].writer, current[1], session, intent, result,
                entry, record, lifetime, self.sequence, pending['target_uid'], intent.accepted_ordinal,
                pending['started'], pending, state, copy.deepcopy(state), dict(pending['native']),
                dict(pending['request']), pending['result_identity'], death, wire, feedback)
            self._lethal_preparation_completed = proof
            self.pending, self.state = None, state

    def lethal_preparation_settled(self):
        """Completed native-purpose evidence, never a current NPC-life grant.

        SourceQuit may call this after its original _enter owns _busy. Removal
        and generation retirement do not invalidate the old native RETURNED.
        """
        proof = self._lethal_preparation_completed
        need(type(self) is ManualMoveCommands and type(proof) is _LethalPreparation
             and proof._consumer is self and threading.get_ident() == self._thread
             and self.pending is None and self._readonly_pending is None
             and self.state is proof._state and self.state == proof._state_data
             and self.sequence == proof.sequence and self.state['status'] == 'PREPARED'
             and self.state['cleanup_required'] is False,
             'MANUAL_LETHAL_PREPARATION_SETTLED_PROOF_REQUIRED')
        need(type(self.lethal_preparation_settled) is MethodType
             and self.lethal_preparation_settled.__func__ is LETHAL_PREPARATION_SETTLED
             and type(self.validate_lethal_preparation) is MethodType
             and self.validate_lethal_preparation.__func__ is LETHAL_PREPARATION_VALIDATE,
             'MANUAL_LETHAL_PREPARATION_ORIGINAL_PRODUCER_REQUIRED')
        pending = proof._pending
        self._lethal_mode_current(pending)
        current = self._current()
        need(current[0].writer is proof.writer and current[1] is proof.row
             and pending['native'] == proof._native and pending['request'] == proof._request
             and pending['result_identity'] == proof._result_identity,
             'MANUAL_LETHAL_PREPARATION_NATIVE_IDENTITY_CHANGED')
        self._attack_result(current, _pending=pending)
        pending['lethal_source'][3].source_guard()
        current = self._current()
        self._attack_result(current, _pending=pending)
        _source_quit_cancel_check()
        self._lethal_mode_current(pending)
        need(self._lethal_preparation_completed is proof and self.state is proof._state
             and self.state == proof._state_data and self.pending is None
             and current[0].writer is proof.writer and current[1] is proof.row
             and pending['native'] == proof._native and pending['request'] == proof._request
             and pending['result_identity'] == proof._result_identity,
             'MANUAL_LETHAL_PREPARATION_SETTLED_CHANGED')
        return proof

    def validate_lethal_preparation(self, writer, *, accepted_ordinal):
        """Current lethal authority before Remove, under the caller row lock."""
        proof = self.lethal_preparation_settled()
        need(writer is proof.writer and type(accepted_ordinal) is int
             and accepted_ordinal == proof.accepted_ordinal
             and proof.row['operation_lock'].locked(), 'MANUAL_LETHAL_PREPARATION_ROW_LOCK_REQUIRED')
        need(self._clock() - proof.originalstarted_ns < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        pending = proof._pending
        current = self._attack_current(_pending=pending)
        actual = self._lethal_live(pending, current)
        expected = (proof.intent, proof.hp_result, proof.hp_entry, proof.notification_record,
                    proof.lifetime, proof._death, proof._death_wire, proof._feedback_wire)
        need(all(a is b for a, b in zip(actual, expected)), 'MANUAL_LETHAL_PREPARATION_LIFETIME_CHANGED')
        pending['lethal_source'][3].source_guard()
        need(self._clock() - proof.originalstarted_ns < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.lethal_preparation_settled()
        current = self._attack_current(_pending=pending)
        actual = self._lethal_live(pending, current)
        self._attack_result(current, _pending=pending)
        _source_quit_cancel_check()
        need(all(a is b for a, b in zip(actual, expected)) and self._lethal_preparation_completed is proof
             and self.state is proof._state and self.state == proof._state_data,
             'MANUAL_LETHAL_PREPARATION_LIFETIME_CHANGED')
        return proof

    async def poll_async(self):
        """Move uses poll unchanged; optional intents await their original owner."""
        if self.state['status'] == 'UNKNOWN' or self.pending is None:
            return dict(self.state)
        if self.pending.get('kind') == 'UseItem':
            return await self._poll_use_item()
        if self.pending.get('kind') == 'SourceRestart':
            return await self._poll_source_restart()
        if self.pending.get('kind') == 'SourceReselect':
            return await self._poll_source_reselect()
        if self.pending.get('kind') != 'AttackTarget':
            return self.poll()
        entered = False
        try:
            self._enter()
            entered = True
            pending = self.pending
            if self.observe_attack_feedback and pending['phase'] == 'ADMISSION':
                self._observation = None  # A failed entry/NPC check has no new player diagnostic.
            now = self._clock()
            current = self._attack_current(admission=pending['phase'] == 'ADMISSION')
            self._window(current)
            need(now - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            if pending['phase'] == 'NATIVE_WAIT':
                self._attack_result(current)
            if self.last_sample_ns is not None and now - self.last_sample_ns < SAMPLE_NS:
                return dict(self.state)
            if pending['phase'] == 'ADMISSION':
                if not pending['npc_ready']:
                    if await self._attack_sample(current) is None:
                        self._pending_state('MANUAL_ATTACK_NPC_OBSERVATION_PENDING')
                        return dict(self.state)
                    pending['npc_ready'] = True  # Never a caller-provided verdict.
                    self._attack_current(admission=True)
                    self._pending_state('MANUAL_ATTACK_PLAYER_ADMISSION_PENDING')
                else:
                    # NPC proof occupied the immediately previous memory slot.
                    # Fresh player/idle is read in this slot before first Post;
                    # server target and native's own typed target gate stay live.
                    idle = (await self._action_sample(current, 'pre_command', strict_idle=True)
                            if self.observe_attack_feedback else self._observe(current, now) == (True, True))
                    if (self.observe_attack_feedback and not idle
                            and self.state.get('reason') in ('MANUAL_MOVE_TYPED_READ_CHANGED_ADMISSION',
                                                            'MANUAL_ATTACK_CACHE_READ_CHANGED_ADMISSION',
                                                            'MANUAL_ATTACK_RECHECKED_COUNT_ADMISSION')):
                        pending['npc_ready'] = False
                        pending['npc_completed_ns'] = None
                        self._pending_state('MANUAL_ATTACK_PLAYER_ADMISSION_PENDING')
                        return dict(self.state)  # Next original slot must refresh NPC, then player.
                    need(idle,
                         'MANUAL_ATTACK_PLAYER_IDLE_REQUIRED')
                    current = self._attack_current(admission=True)
                    hwnd = self._window(current)
                    self._publish(current, hwnd)
            else:
                if pending.get('lethal_preparation'):
                    await self._poll_lethal_preparation(current)
                    return dict(self.state)
                if self.observe_attack_feedback:
                    await self._poll_feedback_observation(current)
                    return dict(self.state)
                if await self._attack_sample(current) is None:
                    self._pending_state('MANUAL_ATTACK_NPC_OBSERVATION_PENDING')
                    return dict(self.state)
                current = self._attack_current()
                session, before = pending['attack_session'], pending['attack_before']
                if session.accepted_count == before + 1 and pending['native'] is not None:
                    intent = session.current_intent()
                    need(type(intent) is attack_session.AttackIntent and intent.accepted_ordinal == before + 1
                         and type(intent._bound) is attack.BoundTarget
                         and intent._bound._authority is pending['attack_targets']
                         and intent._bound._writer is current[0].writer
                         and intent._bound.attacker is pending['initial']
                         and (intent._bound.target_uid, intent._bound.map_id)
                             == (pending['target_uid'], pending['initial'].map_id),
                         'MANUAL_ATTACK_CURRENT_INTENT_UNKNOWN')
                    pending['attack_targets'].revalidate(intent._bound)
                    policy = current[0].broker.policy
                    offset = pending['event_start'] - (policy.events - len(policy.log))
                    need(0 <= offset <= len(policy.log) and current[1]['policy_row'].received > pending['received_base']
                         and any(e[0] == 'rx' and e[1] == current[1]['peer']['endpoint_port'] and e[2] == 0x4e30
                                 for e in list(policy.log)[offset:]), 'MANUAL_ATTACK_CS4E30_UNKNOWN')
                    need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                    self._attack_current()
                    need(session.current_intent() is intent, 'MANUAL_ATTACK_CURRENT_INTENT_UNKNOWN')
                    self._attack_current()
                    task = asyncio.current_task()
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError()
                    need(session._current is intent and session.accepted_count == before + 1
                         and self.state['status'] != 'UNKNOWN',
                         'MANUAL_ATTACK_CURRENT_INTENT_UNKNOWN')
                    self.pending = None
                    self.state = dict(status='COMMITTED', reason=None, sequence=self.sequence,
                        automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
                        command='AttackTarget', proof_scope='VALIDATED_ATTACK_INTENT_ONLY', combat_effect='UNKNOWN')
        except asyncio.CancelledError:
            self._terminal('MANUAL_ATTACK_CANCELLED')
            raise
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered:
                self._busy = False
        return dict(self.state)

    def _admission_current(self):
        if self.pending.get('kind') == 'SourceReselect':
            return self._source_reselect_current()[0]
        if self.pending.get('kind') == 'AttackTarget':
            return self._attack_current(admission=True)
        if self.pending.get('kind') == 'UseItem':
            return self._use_item_current(admission=True)
        current, pending = self._current(), self.pending
        need(current[3] is pending['initial'] and current[7] == pending['before'],
             'MANUAL_MOVE_ADMISSION_AUTHORITY_CHANGED')
        if pending.get('kind') == 'SourceQuit':
            need(self.reader.owner is pending['source_owner']
                 and self.reader.owner.private_desktop is pending['source_desktop'],
                 'SOURCE_QUIT_OWNER_CHANGED')
        if pending.get('kind') == 'SourceRestart':
            self._source_restart_current()
        return current

    def _publish(self, current, hwnd):
        """First native attempt only, after a fully clear fresh admission."""
        pending, position = self.pending, self.pending['initial']
        boundary, identity, counters = current[5:]
        need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        current = self._admission_current()  # Recheck after the clock callback.
        is_attack = pending.get('kind') == 'AttackTarget'
        if is_attack and pending.get('respawn_attack') is None and (self._lethal_mode or pending.get('lethal_preparation')):
            self._lethal_mode_current(pending)
            need(set(self._attack_observations) == {'pre_command'}
                 and self._attack_observations['pre_command'].get('status') == 'OBSERVED'
                 and self._attack_observations['pre_command'].get('strict_idle') is True,
                 'MANUAL_LETHAL_PREPARATION_STRICT_PRE_REQUIRED')
            pending['lethal_pre_snapshot'] = self._attack_observations['pre_command']
            pending['lethal_pre_snapshot_data'] = copy.deepcopy(self._attack_observations['pre_command'])
        is_quit = pending.get('kind') == 'SourceQuit'
        is_use_item = pending.get('kind') == 'UseItem'
        is_already_open = is_use_item and pending.get('already_open_entry', False)
        is_current_entry = is_use_item and pending.get('current_entry_capability') is CURRENT_ENTRY_ONCE
        is_restart = pending.get('kind') == 'SourceRestart'
        is_reselect = pending.get('kind') == 'SourceReselect'
        if not self._reservation:
            need(not os.path.lexists(boundary / 'manual-move-request.json')
                 and not any(boundary.glob('manual-move-result-*.json'))
                 and not os.path.lexists(boundary / 'attack-target-request.json')
                 and not any(boundary.glob('attack-target-result-*.json'))
                 and not os.path.lexists(boundary / 'source-quit-request.json')
                 and not any(boundary.glob('source-quit-result-*.json')),
                 'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
            if self.allow_use_item:
                need(not os.path.lexists(boundary / 'use-item-request.json')
                     and not any(boundary.glob('use-item-result-*.json')),
                     'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
            if self.use_item_already_open:
                need(not any(boundary.glob('use-item-already-open-request-*.json'))
                     and not any(boundary.glob('use-item-already-open-result-*.json')),
                     'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
            if self.use_item_current_entry:
                need(not any(boundary.glob('use-item-current-entry-request-*.json'))
                     and not any(boundary.glob('use-item-current-entry-result-*.json')),
                     'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
            if self.allow_source_restart:
                need(not os.path.lexists(boundary / 'source-restart-request.json')
                     and not any(boundary.glob('source-restart-result-*.json')),
                     'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
            _create_once(boundary / 'manual-move-adapter-owner.json', dict(
                schema='own-manual-move-adapter-owner-v1', **identity))
            self._reservation = True
        # A pre-claim admission timeout consumes no native sequence/claim.
        need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        current = self._admission_current()
        need(self.sequence < MAX_SEQUENCE, 'MANUAL_MOVE_SEQUENCE_EXHAUSTED')
        self.sequence += 1
        self._action_sequence, self._action_bound = self.sequence, self._bound
        pending['phase'] = 'NATIVE_WAIT'
        if is_reselect:
            phase = pending['source_phase']
            need(phase in ('SelectSlot', 'SelectOK') and phase not in pending['claimed_phases']
                 and pending['phase_posted'] is False, 'MANUAL_SOURCE_RESELECT_PHASE_ALREADY_CLAIMED')
            pending['claimed_phases'].add(phase)
            request = dict(schema='own-source-reselect-request-v1', **identity, seq=self.sequence,
                command='SourceReselect', phase=phase, saved_character_uid=pending['uid'],
                canonical_reference_utf8_hex=pending['reference_hex'])
        elif is_restart:
            request = dict(schema='own-source-restart-request-v1', **identity, seq=self.sequence,
                           command='SourceRestart', phase='LandRestart')
        elif is_quit:
            request = dict(schema='own-manual-source-quit-request-v1', **identity, seq=self.sequence,
                           command='SourceQuit', phase=pending['source_phase'])
        elif is_attack:
            request = dict(schema='own-attack-target-request-v1', **identity, seq=self.sequence,
                command='AttackTarget', player_uid=position.uid,
                target_uid=pending['target_uid'], map_id=position.map_id)
        elif is_use_item:
            need(self.allow_use_item is True and identity['candidate_sha256'] == USE_ITEM_IMAGE_SHA,
                 'MANUAL_USE_ITEM_PROGRAM_IMAGE_REQUIRED')
            request = dict(schema=('own-use-item-current-entry-request-v1' if is_current_entry else
                                   'own-use-item-already-open-request-v1' if is_already_open else 'own-use-item-request-v1'), **identity, seq=self.sequence,
                command='UseItemCurrentEntry' if is_current_entry else 'UseItemAlreadyOpen' if is_already_open else 'UseItem', player_uid=position.uid,
                item_identifier=pending['item_identifier'], map_id=position.map_id)
        else:
            x, y = pending['target']
            request = dict(schema='own-internal-command-v1', **identity, seq=self.sequence,
                           command=4, uid=position.uid, x=x, y=y)
        pending.update(request=request, event_start=current[0].broker.policy.events,
                       received_base=current[1]['policy_row'].received,
                       sent_base=current[1]['policy_row'].sent)
        if is_attack and self.observe_attack_feedback:
            pending['approach_event_start'] = pending['event_start']
        _create_once(boundary / ('manual-move-adapter-claim-' + str(self.sequence) + '.json'),
                     dict(schema='own-manual-move-adapter-claim-v1', **identity,
                          seq=self.sequence, queued_monotonic_ns=pending['started']))
        result_path = boundary / (('source-reselect-result-' if is_reselect else 'source-restart-result-' if is_restart else 'source-quit-result-' if is_quit else
                                  'attack-target-result-' if is_attack else
                                  'use-item-current-entry-result-' if is_current_entry else
                                  'use-item-already-open-result-' if is_already_open else
                                  'use-item-result-' if is_use_item else 'manual-move-result-')
                                  + str(self.sequence) + '.json')
        need(not os.path.lexists(result_path), 'MANUAL_MOVE_PREEXISTING_RESULT')
        if is_current_entry:
            _create_once(boundary / ('use-item-current-entry-request-' + str(self.sequence) + '.json'), request)
        elif is_already_open:
            _create_once(boundary / ('use-item-already-open-request-' + str(self.sequence) + '.json'), request)
        else:
            commands._atomic(boundary / ('source-reselect-request.json' if is_reselect else 'source-restart-request.json' if is_restart else 'source-quit-request.json' if is_quit else
                                         'attack-target-request.json' if is_attack else
                                         'use-item-request.json' if is_use_item else 'manual-move-request.json'),
                             request, 512)
        user = self.reader.owner.native.u
        message = int(user.RegisterWindowMessageW(SOURCE_RESELECT_MESSAGE if is_reselect else SOURCE_RESTART_MESSAGE if is_restart else SOURCE_QUIT_MESSAGE if is_quit else
            ATTACK_MESSAGE if is_attack else USE_ITEM_CURRENT_ENTRY_MESSAGE if is_current_entry else USE_ITEM_ALREADY_OPEN_MESSAGE if is_already_open else USE_ITEM_MESSAGE if is_use_item else MESSAGE))
        need(0xc000 <= message <= 0xffff, 'MANUAL_MOVE_MESSAGE_REGISTRATION_FAILED')
        final = self._admission_current()
        need(self._window(final) == hwnd, 'MANUAL_MOVE_PREPOST_CHANGED')
        need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self._admission_current()
        if is_use_item:
            # Publication/registration/window callbacks may have changed the
            # on-disk Store. Reuse the original synchronous projection under
            # the existing row lock at the final Post boundary, not a copy of
            # its authority rules or a cached async admission verdict.
            session = pending['item_session']
            need(self._item_use_project(session, current[0].writer, item_identifier=pending['item_identifier'])[6].identifier
                 == pending['item_identifier'], 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
            need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            self._use_item_current(admission=True)
        if is_attack or is_use_item or is_restart or is_reselect:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        if is_quit:
            _source_quit_cancel_check()
        if is_attack:
            self._attack_purpose_current(pending)
            if pending.get('lethal_preparation'):
                self._lethal_mode_current(pending)
        pending['native_attempted'] = True  # Post attempt, not engine invocation.
        if is_reselect: pending['phase_posted'] = True
        owner = self.reader.owner
        private_desktop = getattr(owner, 'private_desktop', None)
        if private_desktop is not None:
            need(private_desktop.post_command(owner, identity, hwnd, owner.child.tid, message, self.sequence)
                 is True, 'MANUAL_MOVE_POST_UNKNOWN')
        else:
            need(user.PostMessageW(hwnd, message, self.sequence, 0), 'MANUAL_MOVE_POST_UNKNOWN')
        # The existing helper joins without a timeout. A returned dispatch must
        # not renew the original claim or skip the final owner/cancel checks.
        need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        final = self._admission_current()
        need(self._window(final) == hwnd, 'MANUAL_MOVE_POST_BOUNDARY_CHANGED')
        need(self.state['status'] != 'UNKNOWN', 'MANUAL_MOVE_TERMINAL')
        if is_attack or is_use_item or is_restart or is_reselect:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        if is_quit:
            _source_quit_cancel_check()
        self._pending_state()

    def _admit(self, now, current):
        pending, position = self.pending, self.pending['initial']
        observed = self._observe(current, now, allow_attack_command=self.allow_attack_replacement,
                                 admitting=True)
        if self.state.get('reason') in ('MANUAL_MOVE_TYPED_READ_CHANGED_ADMISSION',
                                       'MANUAL_MOVE_SETTLING_ADMISSION_PENDING'):
            reason = self.state['reason']
            current = self._admission_current()
            self._window(current)
            need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            self._admission_current()  # Clock/window callbacks cannot revive a terminal owner.
            need(self.state['status'] != 'UNKNOWN', 'MANUAL_MOVE_TERMINAL')
            self._pending_state(reason)
            return
        need(observed == (True, True), 'MANUAL_MOVE_CLIENT_AUTHORITY_IDLE_REQUIRED')
        current = self._admission_current()
        hwnd = self._window(current)
        current = self._admission_current()
        proof = current[4]
        accepted = proof(position.uid, position.map_id, position.packed, pending['direction'],
                         movement.authority.pack_grid(*pending['target']))
        checked = self._admission_current()
        need(self._window(checked) == hwnd, 'MANUAL_MOVE_WINDOW_CHANGED')
        need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        checked = self._admission_current()
        result = proof.last_result
        self._observation.update({'edge_' + key: value if type(value) is str
            and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,95}', value) else None
            for key in ('status', 'reason', 'phase') for value in (result.get(key),)})
        if accepted is None and result.get('status') == 'UNKNOWN' and result.get('reason') == 'EDGE_TYPED_READ_CHANGED':
            self._pending_state('MANUAL_MOVE_EDGE_READ_CHANGED_ADMISSION')
            return
        need(accepted is True, 'MANUAL_MOVE_CLEAR_EXACT_EDGE_REQUIRED')
        self._publish(checked, hwnd)

    def submit_goal(self, uid, x, y):
        """One explicit adjacent goal, including its pre-native admission wait."""
        if self.state['status'] == 'UNKNOWN':
            return dict(self.state)
        if self._busy or threading.get_ident() != self._thread:
            return self._terminal('MANUAL_MOVE_REENTRANT_OR_THREAD')
        if self.pending is not None:
            return dict(self.state, reason='MANUAL_MOVE_PENDING', accepted=False)
        entered = False
        try:
            self._enter()
            entered = True
            self.state.update(phase='ADMISSION', native_attempted=False)
            self._observation = None
            self._attack_observations = None
            self._last_attack_action = None
            need(all(type(n) is int for n in (uid, x, y)) and 0 < uid <= 0xffffffff
                 and 0 <= x <= 65535 and 0 <= y <= 65535, 'MANUAL_MOVE_GOAL_BOUND')
            now = self._clock()
            current = self._current()
            position = current[3]
            need(position.uid == uid, 'MANUAL_MOVE_SELECTED_UID_REQUIRED')
            delta = (x - position.word0, y - position.word1)
            need(delta in movement.authority.DELTAS, 'MANUAL_MOVE_ADJACENT_GOAL_REQUIRED')
            self.pending = dict(kind='MoveGoal', phase='ADMISSION', native_attempted=False, request=None,
                initial=position, target=(x, y), direction=movement.authority.DELTAS.index(delta),
                before=current[7], started=now, native=None, result_identity=None)
            self._admit(now, current)
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered:
                self._busy = False
        return dict(self.state)

    def _rejection_result(self, current):
        pending, result, position = self.pending, current[2].last_result, current[3]
        need(position is pending['initial'] and type(result) is dict
             and result.get('accepted') is False and result.get('reason') == 'EDGE_BLOCKED'
             and result.get('unknown') is False and result.get('fatal') is False
             and result.get('authority') == position.metadata()
             and type(result.get('reply_count')) is int and result['reply_count'] == 1
             and result.get('own_SC4E2C_count') == 0
             and result.get('policy') == 'LOCAL_AUTHORITY_WITH_SOURCE_CONSUMER_CORRECTION',
             'MANUAL_MOVE_REJECTION_UNKNOWN')

    def _rejection_drained(self, current):
        pending, policy = self.pending, current[0].broker.policy
        offset = pending['event_start'] - (policy.events - len(policy.log))
        need(0 <= offset <= len(policy.log), 'MANUAL_MOVE_RX_PROOF_DROPPED')
        fresh, port, row = list(policy.log)[offset:], current[1]['peer']['endpoint_port'], current[1]['policy_row']
        received = [e for e in fresh if e[0] == 'rx' and e[1] == port and e[2] == 0x4e2b]
        sent = [e for e in fresh if e[0] == 'tx' and e[1] == port and e[2] == movement.CORRECTION_OPCODE]
        need(len(received) == 1 and row.received > pending['received_base'] and len(sent) <= 1
             and type(row.sent) is int and row.sent >= pending['sent_base'],
             'MANUAL_MOVE_REJECTION_TRANSPORT_AMBIGUOUS')
        if sent:
            need(row.sent > pending['sent_base']
                 and fresh.index(received[0]) < fresh.index(sent[0])
                 and sent[0][3] == len(movement.correction_frame(current[3])),
                 'MANUAL_MOVE_REJECTION_TRANSPORT_AMBIGUOUS')
        return bool(sent)

    def poll(self):
        if self.state['status'] == 'UNKNOWN' or self.pending is None:
            return dict(self.state)
        if self.pending.get('kind') in ('AttackTarget', 'SourceQuit', 'UseItem', 'SourceRestart', 'SourceReselect'):
            return dict(self.state)  # Each specialized owner collects its immutable result.
        entered = False
        try:
            self._enter()
            entered = True
            now = self._clock()
            current = self._current()
            self._window(current)
            pending, service, position = self.pending, current[2], current[3]
            need(now - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
            if pending['phase'] == 'ADMISSION':
                current = self._admission_current()
                if self.last_sample_ns is None or now - self.last_sample_ns >= SAMPLE_NS:
                    self._admit(now, current)
                return dict(self.state)
            before, counts = pending['before'], current[7]
            rejected = counts == (before[0] + 1, before[1], before[2] + 1)
            need(rejected or counts[2] == before[2]
                 and all(a <= b <= a + 1 for a, b in zip(before[:2], counts[:2]))
                 and counts[1] - before[1] <= counts[0] - before[0], 'MANUAL_MOVE_SEND_OR_COUNTER_AMBIGUOUS')
            if rejected:
                self._rejection_result(current)
            need((position.uid, position.name, position.map_id) ==
                 (pending['initial'].uid, pending['initial'].name, pending['initial'].map_id)
                 and (position.word0, position.word1) in
                 ((pending['initial'].word0, pending['initial'].word1), pending['target']),
                 'MANUAL_MOVE_AUTHORITY_DIVERGED')
            result_path = current[5] / ('manual-move-result-' + str(self.sequence) + '.json')
            try:
                result = commands._closed_health_json(result_path)
            except (FileNotFoundError, json.JSONDecodeError, UnicodeError):
                result = None  # Missing/partial stays pending only within original deadline.
            if result is not None:
                info = commands._ordinary(result_path).stat()
                result_identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                request = pending['request']
                expected = {k: request[k] for k in ('pid', 'birth', 'candidate_sha256', 'seq', 'command')}
                expected['schema'] = 'own-manual-move-result-v1'
                need(set(result) == set(expected) | {'status', 'reason', 'invoked'}
                     and all(type(result.get(k)) is type(v) and result[k] == v for k, v in expected.items())
                     and type(result['reason']) is int and type(result['invoked']) is bool,
                     'MANUAL_MOVE_RESULT_IDENTITY_OR_SCHEMA')
                need(result['status'] == 'RETURNED' and result['invoked'] is True and result['reason'] == 0,
                     'MANUAL_MOVE_NATIVE_NOT_RETURNED')
                if pending['native'] is not None:
                    need(result == pending['native'] and result_identity == pending['result_identity'],
                         'MANUAL_MOVE_IMMUTABLE_RESULT_CHANGED')
                pending['native'] = dict(result)
                pending['result_identity'] = result_identity
            else:
                need(pending['native'] is None, 'MANUAL_MOVE_IMMUTABLE_RESULT_DISAPPEARED')
            if rejected and not self._rejection_drained(current):
                need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                checked = self._current()
                need(checked[3] is position and checked[7] == counts,
                     'MANUAL_MOVE_AUTHORITY_CHANGED_DURING_READ')
                self._pending_state('MANUAL_MOVE_CORRECTION_DRAIN_PENDING')
                return dict(self.state)
            if self.last_sample_ns is None or now - self.last_sample_ns >= SAMPLE_NS:
                matches, idle = self._observe(current, now, waiting=True, rejecting=rejected)
                current = self._current()
                need(current[3] is position and current[7] == counts, 'MANUAL_MOVE_AUTHORITY_CHANGED_DURING_READ')
                need(self._clock() - pending['started'] < WAIT_NS, 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                current = self._current()
                need(current[3] is position and current[7] == counts, 'MANUAL_MOVE_AUTHORITY_CHANGED_DURING_READ')
                if rejected and pending['native'] is not None and matches and idle:
                    self._rejection_result(current)
                    need(self._rejection_drained(current), 'MANUAL_MOVE_CORRECTION_DRAIN_UNKNOWN')
                    if (type(pending.get('backward_sample_ns')) is int
                            and pending['backward_sample_ns'] < now):
                        # Rejected is not a durable move commit and never replays it.
                        self.pending = None
                        self.state = dict(status='REJECTED', reason='EDGE_BLOCKED', sequence=self.sequence,
                            automatic_retry=False, cleanup_required=False, phase='REJECTED',
                            native_attempted=True, command='MoveGoal', accepted=False,
                            proof_scope='SC4EE0_DRAIN_WITH_CLIENT_SETTLED',
                            moving_back_snapshot_observed=True, moving_back_start_observed=False)
                    else:
                        self.state['reason'] = 'MANUAL_MOVE_BACKWARD_SNAPSHOT_PENDING'
                elif (pending['native'] is not None and matches and idle
                        and (position.word0, position.word1) == pending['target']
                        and counts == (before[0] + 1, before[1] + 1, before[2])):
                    result = service.last_result
                    need(type(result) is dict and result.get('accepted') is True
                         and result.get('reason') == 'COMMITTED' and result.get('unknown') is False
                         and result.get('fatal') is False and result.get('authority') == position.metadata(),
                         'MANUAL_MOVE_SERVICE_COMMIT_UNKNOWN')
                    policy = current[0].broker.policy
                    offset = pending['event_start'] - (policy.events - len(policy.log))
                    need(0 <= offset <= len(policy.log), 'MANUAL_MOVE_RX_PROOF_DROPPED')
                    fresh = list(policy.log)[offset:]
                    need(any(e[0] == 'rx' and e[1] == current[1]['peer']['endpoint_port']
                             and e[2] == 0x4e2b for e in fresh)
                         and current[1]['policy_row'].received > pending['received_base'],
                         'MANUAL_MOVE_CS4E2B_UNKNOWN')
                    self.pending = None
                    self.state = dict(status='COMMITTED', reason=None, sequence=self.sequence,
                                      automatic_retry=False, cleanup_required=False,
                                      phase='COMMITTED', native_attempted=True)
        except BaseException as error:
            self._terminal(self._reason(error))
        finally:
            if entered:
                self._busy = False
        return dict(self.state)

    def cancel(self):
        """Expose a terminal cleanup request; never close the owner/game here."""
        return self._terminal('MANUAL_MOVE_CANCELLED')

    @property
    def last_sample_monotonic_ns(self):
        """Last direct sample attempt, including a failing read; no cached proof."""
        return self.last_sample_ns

    close = cancel

# Exact producer entries for private preparation consumers.
LETHAL_PREPARATION_TYPE = _LethalPreparation
LETHAL_PREPARATION_VALIDATE = ManualMoveCommands.validate_lethal_preparation
LETHAL_PREPARATION_SETTLED = ManualMoveCommands.lethal_preparation_settled

RESPAWN_ATTACK_PROOF_TYPE = _RespawnAttackCompleted
RESPAWN_ATTACK_VALIDATE = ManualMoveCommands.validate_respawn_attack
