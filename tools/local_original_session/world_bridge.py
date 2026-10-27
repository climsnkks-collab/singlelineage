"""Broker/world adapter and Context. No packet loop, file pin or input automation.

The underscore API is a compatibility facade for existing equipment consumers and
loopback fixtures. Feature implementations and registrations live outside broker.
"""
from __future__ import annotations

import asyncio
from functools import wraps
import inspect
import os

from tools.local_native_login_local_ack_hook import ack_enter_world as ack
from tools.local_original_session import movement, npc_motion

RESTART_REQUEST, DEAD_RESTART_REQUEST, ALIVE_REQUEST = 0x4e33, 0x4eec, 0x4e2a
ATTACK_REQUEST, ATTACK_FEEDBACK, ITEM_USE_REQUEST = 0x4e30, 0x4e31, 0x0960
WORLD_SEND_CHUNK = ack.realm.MAX_CHARACTERS + 2
WORLD_OPCODES = (0x4e28, 0x4e2b, ALIVE_REQUEST)
WORLD_SEND_OPCODES = (0x4e96, 0x4e40, npc_motion.OPCODE, ATTACK_FEEDBACK, 0x4e39, 0x4e38, 0x0965, 0x0978,
                      0x4e5b, 0x0964, 0x4e44, 0x4e48, 0x4ee7, 0x4ee0, 0x4f1a, 0x4ec8, 0x4e95, 0x4e5c,
                      0x4ed2, 0x0971, 0x0967)


def need(value, code):
    if not value:
        raise ValueError(code)


class Context:
    """Access the existing send, saves and selected session without owning sockets.

    Legacy names delegate dynamically to the owner, preserving method overrides,
    writer/lock identity and existing inventory-generation property semantics.
    State uses the existing in-memory attributes; save formats are untouched.
    """
    __slots__ = ('broker',)

    def __init__(self, broker):
        object.__setattr__(self, 'broker', broker)

    def __getattr__(self, name):
        return getattr(self.broker, name)

    def __setattr__(self, name, value):
        if name == 'inventory_frame':
            name = '_inventory_current_frame'
        setattr(self.broker, name, value)

    @property
    def world(self):
        return self.broker._world

    @property
    def realm(self):
        return self.broker.realm

    @property
    def inventory_store(self):
        return self.broker._inventory_store

    @property
    def inventory_frame(self):
        return self.broker._inventory_current_frame

    @property
    def starter_fields(self):
        return self.broker.INVENTORY_STARTER_FIELDS

    def selected_session(self, writer):
        return self.realm.registry.resolve(writer)

    def owner_current(self, writer, row, position):
        return self.broker._selected_owner_current(writer, row, position)

    async def send(self, writer, row, frames, **options):
        return await self.broker._send(writer, row, frames, **options)

    async def run_hooks(self, name, *args):
        from tools.local_original_session import world_handlers
        return await world_handlers.run_hooks(name, self, *args)

    def run_sync_hooks(self, name, *args):
        from tools.local_original_session import world_handlers
        return world_handlers.run_sync_hooks(name, self, *args)


def _adapter(function):
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def call(owner, *args, **kwargs):
            boundary = _save_boundary(owner, function.__name__, args)
            flush = _cleanup_persist if function.__name__ == '_world_leave' else _flush_persist
            if boundary:
                flush(owner)
                _immediate_inventory(owner, 1)
            try:
                result = await function(Context(owner), *args, **kwargs)
                if boundary:
                    flush(owner)
                elif function.__name__ == '_world_send':
                    _capture_persist(owner)
                return result
            finally:
                if boundary:
                    _immediate_inventory(owner, -1)
    else:
        @wraps(function)
        def call(owner, *args, **kwargs):
            if function.__name__ == '_world_save_progress' and getattr(owner, '_world_persist', None):
                _capture_persist(owner)
                return
            boundary = _save_boundary(owner, function.__name__, args)
            if boundary:
                _flush_persist(owner)
                _immediate_inventory(owner, 1)
            try:
                result = function(Context(owner), *args, **kwargs)
                if boundary:
                    _flush_persist(owner)
                return result
            finally:
                if boundary:
                    _immediate_inventory(owner, -1)
    return call


def _save_boundary(owner, name, args):
    if getattr(owner, '_world_persist', None) is None:
        return False
    if name == '_world_dispatch':
        from tools.local_original_session.world_handlers import TRADE
        return len(args) > 3 and args[3].opcode == TRADE
    if name == '_world_enchant_use':
        # This candidate is queried for every 0960. Ordinary potions must not
        # flush pending movement/quantity snapshots just because it returns False.
        from tools.local_original_session import inventory
        if getattr(owner, '_inventory_kit_policy', None) != inventory.KIT_POLICY or len(args) < 2:
            return False
        pb = ack.realm.pb
        try:
            with pb.parse_message(args[1], limits=pb.WireLimits(
                    max_body=4096, max_fields=2, max_field_bytes=2048)) as parsed:
                fields = parsed.occurrences(1)
                if len(fields) != 1 or fields[0].wire_type != 0:
                    return False
                uid = fields[0].value
            return any(item.identifier == uid and item.template_bits in (25, 26)
                       for item in inventory.validate_kit_frame(owner._inventory_current_frame))
        except (ValueError, pb.WireError):
            return False  # Original handler retains malformed-request reporting.
    return name in ('_world_leave', '_world_pc_died', '_world_commit_respawn',
                    '_world_relocate_locked', '_world_quest_action',
                    '_world_warehouse_trade',
                    '_companion_give_frame')


def _connect_inventory(broker):
    from tools.local_original_session import inventory
    store = getattr(broker, '_inventory_store', None)
    if (store is not None and getattr(store, '_kit_policy', None) == inventory.KIT_POLICY
            and getattr(store, '_world_persist', None) is None):
        store.enable_world_persist(broker._world_persist)
    return store


def _immediate_inventory(broker, delta):
    store = _connect_inventory(broker)
    if getattr(store, '_world_persist', None) is not None:
        store._world_immediate += delta


def _capture_persist(broker):
    persist = getattr(broker, '_world_persist', None)
    if persist is None or persist.closed:
        return
    _connect_inventory(broker)
    world = broker._world
    from dataclasses import replace
    for uid, dirty in tuple(world.progress_dirty.items()):
        snapshot = replace(dirty, lawful=getattr(broker, '_world_lawful', {}).get(uid, dirty.lawful))
        broker._world_progress.stage(uid, snapshot)
        persist.enqueue(('progress', uid), snapshot, kind='character')
        if world.progress_dirty.get(uid) is dirty:
            world.progress_dirty.pop(uid, None)
    uids = set(world.combat.pcs) | set(world.combat.vitals)
    for uid in uids:
        hp, mp = world.combat.hp_of(uid), world.combat.mp_of(uid)
        if hp is None or mp is None:
            continue
        value = (hp, mp)
        if broker._world_vital_snapshots.get(uid) != value:
            persist.enqueue(('vitals', uid), value, kind='character')
            broker._world_vital_snapshots[uid] = value


def _flush_persist(broker):
    persist = getattr(broker, '_world_persist', None)
    if persist is None:
        return
    _capture_persist(broker)
    result = persist.flush_all()
    broker._world_persist_result = result
    if result.failures:
        raise result.failures[0].error
    need(result.ok, 'WORLD_PERSIST_PENDING')


def _cleanup_persist(broker):
    """Save failure remains fatal, while writer/socket cleanup must continue."""
    try:
        _flush_persist(broker)
    except Exception as error:
        broker._world_progress_errors = (getattr(broker, '_world_progress_errors', [])
                                        + [str(error)[:96]])[-4:]
        broker._fail('WORLD_PERSIST_FAILED')


class _WorldPositions(movement.PositionStore):
    """Selected world memory CAS; disk preimage is compared once per flush.

    Original PositionStore still owns schema/path checks and atomic replacement.
    Expected positions must match the current memory value on every movement.
    External disk changes are rejected at flush, preserving the latest pending
    snapshot for inspection rather than replacing another authority's value.
    """
    def __init__(self, store, persist):
        self.store, self.persist = store, persist
        self._current, self._durable = {}, {}
        self._attempted = {}
        self._transition = set()
        self.path = store.path

    def restore(self, selected):
        need(type(selected) is movement.Position, 'SELECTED_POSITION_REQUIRED')
        if selected.uid not in self._current:
            value = self.store.restore(selected)
            self._current[selected.uid] = self._durable[selected.uid] = value
        value = self._current[selected.uid]
        from dataclasses import replace
        return replace(value, name=selected.name)

    def commit(self, expected, updated, *, transition=False):
        need(type(expected) is movement.Position and type(updated) is movement.Position
             and (updated.uid, updated.name) == (expected.uid, expected.name)
             and (updated.map_id == expected.map_id or transition is True
                  and expected.map_id in movement.SUPPORTED_MAP_IDS
                  and updated.map_id in movement.SUPPORTED_MAP_IDS),
             'SAME_SELECTED_POSITION_REQUIRED')
        need(self.restore(expected) == expected, 'POSITION_STORE_AUTHORITY_CHANGED')
        self.persist.enqueue(('position', updated.uid), updated, kind='character')
        self._current[updated.uid] = updated
        if transition:
            self._transition.add(updated.uid)
            result = self.persist.flush_all()
            if result.failures:
                raise result.failures[0].error
            need(result.ok, 'WORLD_PERSIST_PENDING')

    def flush_snapshot(self, uid, snapshot):
        expected = self._durable[uid]
        # An already completed absolute snapshot is an idempotent acknowledgement,
        # including a previous replace-then-raise outcome, never another move.
        current = self.store.restore(expected)
        if current != snapshot:
            need(current in (expected, self._attempted.get(uid)), 'POSITION_STORE_AUTHORITY_CHANGED')
            self._attempted[uid] = snapshot
            self.store.commit(current, snapshot, transition=uid in self._transition)
        self._durable[uid] = snapshot
        self._attempted.pop(uid, None)
        self._transition.discard(uid)


def _setup_persist(broker):
    from tools.local_original_session.world_persist import WorldPersist
    def save(key, snapshot):
        kind, uid = key
        if kind == 'position':
            broker.realm.positions.flush_snapshot(uid, snapshot)
        elif kind == 'inventory':
            broker._inventory_store.flush_world_snapshot(uid, snapshot)
        elif kind == 'progress':
            broker._world_progress.commit(uid, snapshot)
        elif kind == 'vitals':
            broker._world_progress.save_vitals(uid, snapshot)
        else:
            raise ValueError('WORLD_PERSIST_UNKNOWN_KEY')
    broker._world_persist = WorldPersist(broker._world.runtime.scheduler, save)
    broker._world_vital_snapshots = {}
    broker.realm.positions = _WorldPositions(broker.realm.positions, broker._world_persist)
    broker._world_progress.get(1)  # Sidecars are prepared before request handling.
    broker._world_progress.vitals(1)
    for name, getter in (('_world_hp', broker._world.combat.hp_of),
                         ('_world_mp', broker._world.combat.mp_of)):
        index = 0 if name == '_world_hp' else 1
        def value(uid, getter=getter, index=index):
            current = getter(uid)
            saved = broker._world_progress.vitals(uid)
            return current if current is not None else (None if saved is None else saved[index])
        setattr(broker.realm, name, value)
    _connect_inventory(broker)
    broker._world.runtime.add_tick_hook(lambda now: _capture_persist(broker))


def install_feature_api(broker_type, realm_type, starter_fields):
    """Compatibility aliases only; a new feature needs no broker file changes."""
    from tools.local_original_session.world_handlers import feature_registry
    registry = feature_registry()
    for name, function in registry.methods.items():
        setattr(broker_type, name, _adapter(function))
    for name, function in registry.realm_methods.items():
        setattr(realm_type, name, function)
    broker_type.INVENTORY_STARTER_FIELDS = starter_fields
    broker_type.WORLD_SEND_CHUNK = WORLD_SEND_CHUNK
    broker_type.WORLD_OPCODES = WORLD_OPCODES
    broker_type.WORLD_SEND_OPCODES = WORLD_SEND_OPCODES + registry.outgoing_opcodes


def kit_policy(world_policy, missing, collection, transfer, store_policy):
    if world_policy is None or missing is None or collection is not None or transfer is not None:
        return None
    from tools.local_original_session import inventory, inventory_store
    if store_policy == inventory_store.POLICY:
        return inventory.KIT_POLICY
    return None


def prepare_inventory(broker, world_policy):
    broker._world_warehouse_store = None
    if world_policy is not None and broker._inventory_kit_policy is not None:
        from tools.local_original_session.world_warehouse import WarehouseStore
        broker._world_warehouse_store = WarehouseStore(broker._inventory_store)


def initialize(broker, world_policy, world_handler_sources, world_starter_kit, restart_policy, store_path):
    self = Context(broker)
    self._world = None
    self._world_pcs = {}
    if world_policy is not None:
        from tools.local_original_session import world_visibility, world_interest_spawn
        need(type(world_policy) is str and world_policy == world_visibility.POLICY,
             'WORLD_EXPLICIT_POLICY_REQUIRED')
        from tools.local_original_session.game_data import load_m1
        self._world = world_visibility.WorldView.create(
            data=world_interest_spawn.with_dungeon_data(load_m1()))
        from tools.local_original_session.world_feature_items import setup_enchant
        setup_enchant(self)
        from tools.local_original_session.world_feature_town import setup_warehouse
        setup_warehouse(self)
        from tools.local_original_session.world_feature_town import setup_town
        setup_town(self, world_handler_sources)
        from tools.local_original_session.world_feature_items import setup_polymorph
        setup_polymorph(self)
        from tools.local_original_session.world_feature_alignment import setup_alignment
        setup_alignment(self)
        from tools.local_original_session.world_feature_combat import setup_arrow
        setup_arrow(self)
        from tools.local_original_session.world_feature_items import setup_effects
        setup_effects(self)
        self._world.prepare_pc_attack = lambda *args: self.run_sync_hooks('prepare_attack', *args)
        self._world.on_pc_death = lambda uid: self.run_sync_hooks('after_death', uid)
        self._world.on_npc_hit = lambda uid: self.run_sync_hooks('npc_hit', uid)
        self._world.notify = self._world_wake  # tick -> per-PC wake event, never a send
        self.realm.edge_fallback = self._world_edge_fallback
        self.realm._world_hp = self._world.combat.hp_of  # SelfInfo HP from the world authority
        self.realm._world_mp = self._world.combat.mp_of
        self.realm._world_stats_fields = self._world_fields_for
        self._world.on_stats_changed = lambda uid: self.run_sync_hooks('stats_changed', uid)
        from tools.local_original_session.world_feature_kit import setup_stance
        setup_stance(self)
        self.realm._world_respawn_commit = self._world_commit_respawn
        self.realm._world_unserved_return = self._world_unserved_return
        self.realm._world_dead_restart = restart_policy is not None
        self.realm._world_is_dead = self._world.combat.is_dead
        from tools.local_original_session.world_feature_reward import setup_progress
        setup_progress(self, store_path)
    from tools.local_original_session.world_feature_kit import setup_starter
    setup_starter(self, world_policy, world_starter_kit)
    self._world_events = {}  # pc uid -> asyncio.Event read by that writer's _serve loop
    self._world_names = {}  # pc uid -> selected saved name (for the town respawn commit)
    self._world_respawn = {}  # pc uid -> name: left dead, next entry is at the town point
    self._world_respawn_errors = []
    self._world_progress_errors = []
    self._world_pickups = 0
    self._world_pickup_errors = []
    self._world_handler_errors = []
    self._world_item_errors = []
    self._world_relocations = {}  # restart/reselect fallback
    self._world_map_exp = int(os.environ.get('SL_EXPERIMENT_MAP', '0'))
    need(self._world_map_exp in (0, 1, 2, 3), 'WORLD_MAP_EXPERIMENT_REQUIRED')
    self.realm._world_map_exp = self._world_map_exp if self._world is not None else 0
    self._world_map_transitions = 0
    if self._world is not None:
        self.run_sync_hooks('initialize')
        _setup_persist(broker)


def start(broker, loop):
    if broker._world is not None:
        broker._world.runtime.start(loop)
        Context(broker).run_sync_hooks('runtime_started')


def close(broker):
    world = getattr(broker, '_world', None)
    if world is not None:
        world.close()


async def stop(broker):
    world = getattr(broker, '_world', None)
    if world is not None:
        await world.runtime.stop()
        await Context(broker).run_hooks('runtime_stopped')
        _cleanup_persist(broker)  # Leave still follows; keep producers open.


def event_for(broker, writer):
    bound = broker._world_pcs.get(id(writer)) if broker._world is not None else None
    return None if bound is None else broker._world_events.get(bound[1])


async def receive(broker, writer, row, game, frame, operation_lock):
    from tools.local_original_session.world_handlers import feature_registry
    if frame.opcode in (RESTART_REQUEST, DEAD_RESTART_REQUEST, 0x4e3c):
        # Settle the current life before the existing route can acknowledge exit.
        _flush_persist(broker)
    for name in feature_registry().frames.get(frame.opcode, ()):
        if await getattr(broker, name)(writer, row, game, frame, operation_lock):
            return True
    return False


async def after_request(broker, writer, row, game, opcode, operation_lock):
    await Context(broker).run_hooks('after_request', writer, row, game, opcode, operation_lock)


async def leave(broker, writer):
    if getattr(broker, '_world', None) is None:
        return
    try:
        await broker._world_leave(writer)
    except Exception:
        broker._fail('WORLD_PERSIST_FAILED')
    bound_uids = {uid for _, uid in broker._world_pcs.values()}
    for uid in tuple(broker._world_respawn):
        if uid not in bound_uids:
            try:
                broker._world_commit_respawn(uid)
            except Exception:
                broker._fail('WORLD_PERSIST_FAILED')
    try:
        await Context(broker).run_hooks('after_leave', writer)
    except Exception as error:
        broker._world_progress_errors = (broker._world_progress_errors + [str(error)[:96]])[-4:]
        broker._fail('WORLD_LEAVE_FAILED')
    _cleanup_persist(broker)


def validate_send(broker, row, replies, game, operation_lock, world_operation):
    need(world_operation is None or (broker._world is not None and game is True
         and world_operation is replies and operation_lock is row['operation_lock']
         and operation_lock.locked()), 'WORLD_LOCKED_SEND_REQUIRED')


def validate_frame(broker, wire, world_operation):
    need(int.from_bytes(wire[2:4], 'little') in broker.WORLD_SEND_OPCODES,
         'WORLD_EXACT_PREPARED_FRAME_REQUIRED')


def received_extensions(policy, extension):
    from tools.local_original_session.world_handlers import HANDLERS, feature_registry
    if getattr(policy, 'world', False) is True:
        if getattr(policy, 'restart_enabled', False) is True and DEAD_RESTART_REQUEST not in extension:
            extension += (DEAD_RESTART_REQUEST,)
        extension += tuple(HANDLERS) + (ITEM_USE_REQUEST,)
        extension += tuple(feature_registry().frames)
        if not policy.item_transfer:
            extension += (0x4e3e,)
    return extension


def outgoing_extensions(policy, extension, opcode, size, phase):
    if getattr(policy, 'world', False) is not True:
        return extension
    if phase == 'menu':
        if opcode in (0x4e44, 0x4e48, 0x4ee7, 0x4e5c):
            extension += (opcode,)
        if opcode in (0x4ed2, 0x0971) and os.environ.get('SL_EXPERIMENT_WAREHOUSE', '') not in ('', '0'):
            extension += (opcode,)
        if opcode == 0x0967 and os.environ.get('SL_EXPERIMENT_ENCHANT', '') not in ('', '0'):
            extension += (opcode,)
        if opcode in (0x4f1a, 0x4ec8) and os.environ.get('SL_EXPERIMENT_HPBAR') in ('1', '2', '3'):
            extension += (opcode,)
        from tools.local_original_session.world_handlers import feature_registry
        if opcode in feature_registry().outgoing_opcodes:
            extension += (opcode,)
    elif phase == 'combat':
        if opcode == 0x4e40 and opcode not in extension:
            extension += (opcode,)
            need(type(size) is int and 8 <= size <= 17, 'WORLD_REMOVE_FRAME_BOUND')
        if opcode in (0x4e39, ATTACK_FEEDBACK) and opcode not in extension:
            extension += (opcode,)
            need(type(size) is int and (10 <= size <= 19 if opcode == 0x4e39 else 6 <= size <= 45),
                 'WORLD_COMBAT_FRAME_BOUND')
    return extension


def kit_outgoing_extensions(policy, extension, opcode, size):
    if getattr(policy, 'item_kit', False) is True and opcode in (0x0965, 0x0978) and opcode not in extension:
        extension += (opcode,)
        need(type(size) is int and 6 <= size <= 1024, 'ITEM_KIT_FRAME_BOUND')
    if getattr(policy, 'item_kit', False) is True and opcode == 0x4e5b:
        extension += (opcode,)
        need(type(size) is int and 6 <= size <= 64, 'ITEM_KIT_SPEED_FRAME_BOUND')
    return extension


def actor_fields(realm, position, actor):
    from tools.local_original_session.world_feature_stats import realm_actor
    return realm_actor(realm, position, actor)


def status_fields(realm, position, fields, initial):
    from tools.local_original_session.world_feature_stats import realm_status
    return realm_status(realm, position, fields, initial)


def serves_map(realm, map_id):
    from tools.local_original_session.world_feature_maps import realm_serves_map
    return realm_serves_map(realm, map_id)


def map_frame(realm, position, encode):
    from tools.local_original_session.world_feature_maps import realm_map_frame
    return realm_map_frame(realm, position, encode)


def dead_move(realm, service):
    from tools.local_original_session.world_feature_maps import realm_dead_move
    return realm_dead_move(realm, service)


async def move(service, payload):
    from tools.local_original_session.world_feature_maps import realm_move
    return await realm_move(service, payload)


def bind_restart(realm, game, life_broker, restart_game):
    from tools.local_original_session.world_feature_life import realm_bind_restart
    realm_bind_restart(realm, game, life_broker, restart_game)


def report(broker, result):
    self = Context(broker)
    world = getattr(self, '_world', None)
    if world is not None:
        persist = getattr(broker, '_world_persist', None)
        if persist is not None:
            if getattr(broker, 'cleanup_complete', False) and not persist.closed:
                _capture_persist(broker)
                broker._world_persist_result = persist.shutdown()
                if not broker._world_persist_result.ok:
                    broker._fail('WORLD_PERSIST_FAILED')
                    result['failure_code'] = broker.failure_code
            result['persistence'] = dict(pending=[list(key) for key in persist.pending_keys],
                failures=[dict(key=list(f.key), error=type(f.error).__name__)
                          for f in persist.last_failures], closed=persist.closed)
        result['world'] = dict(kills=len(world.combat.kills), ground_items=len(world.ground),
            pickups=self._world_pickups, pickup_errors=list(self._world_pickup_errors),
            reward_errors=list(world.reward_errors), progress_errors=list(self._world_progress_errors),
            respawn_errors=list(self._world_respawn_errors), pending_respawn=len(self._world_respawn),
            handler_errors=list(self._world_handler_errors), item_errors=list(self._world_item_errors),
            town_npcs=(0 if world.town is None else sum(1 for entity in world.entities
                        if world.town.npc_for(entity.uid) is not None)),
            menu_sources=len(self._world_handler_bindings.sources),
            shop_experiment=self._world_shop_experiment is not None,
            polymorph_experiment=self._world_poly_exp, active_polymorphs=len(self._world_polymorphs),
            alignment_changes=list(self._world_alignment_changes), death_drop_risks=list(self._world_death_risks),
            enchant_experiment=self._world_enchant_exp is not None,
            enchant_results=list(self._world_enchant_results),
            warehouse_experiment=self._world_warehouse_exp,
            warehouse_results=list(self._world_warehouse_results),
            relocation_policy=('LOCAL_SAME_MAP_REMOVE_4EE0_SPAWN' if self._world_map_exp == 0
                               else 'LOCAL_MAP_EXPERIMENT'),
            map_transition='NATIVE_PUBLICATION_UNKNOWN',
            map_experiment=self._world_map_exp, experimental_transitions=self._world_map_transitions)



def defer_equipment_prepare(broker, life):
    from tools.local_original_session.world_feature_kit import defer_equipment_prepare as defer
    return defer(broker, life)


def inventory_items(broker, frame):
    from tools.local_original_session.world_feature_kit import inventory_items as items
    return items(Context(broker), frame)


def starter_frame(broker, name, fallback):
    from tools.local_original_session.world_feature_kit import starter_frame as starter
    return starter(Context(broker), name, fallback)


def first_grant_valid(broker, frame):
    from tools.local_original_session.world_feature_kit import first_grant_valid as valid
    return valid(Context(broker), frame)


def inventory_payload(broker, wire, inventory_wire):
    from tools.local_original_session.world_feature_kit import inventory_payload as payload
    return payload(Context(broker), wire, inventory_wire)
