"""World feature: combat. Existing packet/store operations, unchanged."""
from __future__ import annotations

import os
import struct
from tools.local_original_session.world_bridge import need

CONTINUE_REQUEST = 0x4E42
CONTINUE_ACK = 0x4F32
FAR_ATTACK = 0x4EE1


def decode_continue(payload):
    """Native required f1 uint32; zero cancels, never a damage request."""
    from tools.local_entry_server import protobuf as pb
    try:
        with pb.parse_message(payload, schema={1: 0},
                limits=pb.WireLimits(max_body=16, max_fields=1, max_field_bytes=16)) as parsed:
            need(len(parsed.fields) == 1 and parsed.fields[0].number == 1,
                 'ATTACK_CONTINUE_REQUIRED_UINT32')
            value = parsed.fields[0].value
            need(0 <= value <= 0xffffffff, 'ATTACK_CONTINUE_REQUIRED_UINT32')
            return value
    except (ValueError, TypeError, BufferError):
        raise ValueError('MALFORMED_ATTACK_CONTINUE_PAYLOAD') from None


def continue_ack(retained):
    """Verified bool consumer, with an explicit LOCAL response policy.

    True means this local server retained a current target; it neither starts a
    swing nor promises a hit. False releases native key3. Official per-request
    response duty and accepted-target response conditions remain unverified.
    """
    from tools.local_entry_server import protobuf as pb
    need(type(retained) is bool, 'ATTACK_CONTINUE_BOOL_REQUIRED')
    body = pb.encode_bool(1, retained)
    return struct.pack('<HH', len(body) + 6, CONTINUE_ACK) + body + b'\0\0'


def _continue_current(ctx, uid, entry):
    writer, pc_ref, target_ref = entry
    bound = ctx._world_pcs.get(id(writer))
    world = ctx._world
    pc, target = world.entities.resolve(pc_ref), world.entities.resolve(target_ref)
    state = world.combat.pcs.get(uid)
    return (bound is not None and bound[0] is writer and bound[1] == uid
            and pc is not None and pc.alive and state is not None
            and not state.dead and state.hp > 0 and target is not None and target.alive
            and pc.map_id == target.map_id and world.spawner.slot_for(target.uid) is not None
            and target.uid in world.visibility.known.get(uid, ()))


def _continue_clear(ctx, uid, *, notify=True):
    if ctx._world_continue_targets.pop(uid, None) is not None and notify:
        ctx._world._queue(uid, continue_ack(False))


def _continue_prune(ctx):
    for uid, entry in tuple(ctx._world_continue_targets.items()):
        if not _continue_current(ctx, uid, entry):
            _continue_clear(ctx, uid)


async def _world_attack_continue(ctx, writer, row, game, frame, operation_lock):
    if not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return True
    uid = ctx._world_pcs[id(writer)][1]
    try:
        target_uid = decode_continue(frame.payload)
    except ValueError as error:
        ctx._world_attack_errors = (ctx._world_attack_errors + [str(error)])[-4:]
        return True  # Malformed input leaves the preceding valid request alone.

    def retain():
        world = ctx._world
        resolved_uid = world.resolve_pc_attack_target(uid, target_uid)
        pc, target = world.entities.get(uid), world.entities.get(resolved_uid)
        entry = None if pc is None or target is None else (writer, pc.ref, target.ref)
        accepted = target_uid != 0 and entry is not None and _continue_current(ctx, uid, entry)
        if accepted:
            ctx._world_continue_targets[uid] = entry
        else:
            _continue_clear(ctx, uid, notify=False)
        return continue_ack(bool(accepted))

    wire = await ctx._world.runtime.dispatch_now(retain)
    await ctx._world_send(writer, row, (wire,), operation_lock)
    return True


async def _world_far_attack(ctx, writer, row, game, frame, operation_lock):
    """Bow ingress only; core 4E30 owns parsing, cadence, LOS, cost and damage.

    4E30 remains the compatible general swing lane. A maintained 4E42 target
    is independent metadata and does not authorize or duplicate either swing.
    Reused 4E31 display is LOCAL behavior, not a verified 4EE1 reply obligation.
    """
    if not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return True
    uid = ctx._world_pcs[id(writer)][1]
    effect = getattr(ctx, '_item_equipment_effect', None)
    weapon, _ = (None, 0) if effect is None else effect.combat_inputs(uid)
    if weapon is None or weapon.weapon_type != 'bow':
        return True
    await ctx._world_attack(writer, row, game, frame, operation_lock)
    return True  # Never fall through to an unrelated legacy attack target.


async def _world_combat_before_leave(ctx, writer, uid):
    await ctx._world.runtime.dispatch_now(lambda: _continue_clear(ctx, uid, notify=False))


def _world_combat_initialize(ctx):
    ctx._world_continue_targets = {}
    world = ctx._world
    owner = 'combat_continue'
    world.events.add(owner, 'tick', lambda now: _continue_prune(ctx))
    world.events.add(owner, 'before_map_change', lambda uid: _continue_clear(ctx, uid))
    world.events.add(owner, 'pc_death', lambda uid: _continue_clear(ctx, uid))
    world.events.add(owner, 'before_pc_leave',
                     lambda uid: _continue_clear(ctx, uid, notify=False))

    def target_died(target_uid, now):
        for uid, entry in tuple(ctx._world_continue_targets.items()):
            if entry[2].uid == target_uid:
                _continue_clear(ctx, uid)

    world.events.add(owner, 'npc_died', target_died)
    world.events.add(owner, 'close', ctx._world_continue_targets.clear)


def _world_prepare_pc_attack(self, pc_uid, target, now):
    """Called after world life/cadence/LOS checks, before hit RNG/cooldown."""
    from tools.local_original_session import inventory, world_ammo, world_combat
    pc = self._world.entities.get(pc_uid)
    effect = getattr(self, '_item_equipment_effect', None)
    weapon, _ = (None, 0) if effect is None else effect.combat_inputs(pc_uid)
    if weapon is None or weapon.weapon_type != 'bow':
        reach = world_combat.MELEE_RANGE if weapon is None else weapon.attack_range
        if max(abs(pc.x - target.x), abs(pc.y - target.y)) > reach:
            return None
        return world_ammo.AttackPreparation(True)
    writer = next((writer for writer, uid in self._world_pcs.values() if uid == pc_uid), None)
    if writer is None or self._inventory_kit_policy != inventory.KIT_POLICY:
        return None
    items = inventory.validate_kit_frame(self.inventory_frame)
    stacks = tuple(world_ammo.AmmoStack(item.identifier, item.template_bits, dict(item.raw_fields)[4])
                   for item in items)
    prepared = world_ammo.prepare_attack(weapon,
        stacks, attacker=(pc.map_id, pc.x, pc.y),
        target=(target.map_id, target.x, target.y), items=self._world.data.items)
    prepared = self.fold_sync_hooks('bow_ammunition', prepared, pc_uid, weapon, stacks, target, now)
    if not prepared.allowed:
        return None
    cost = prepared.cost
    if cost is None:
        return prepared
    try:
        wire = self._world_consume_kit(writer, cost.item_uid, cost.count)
    except ValueError as error:
        self._world_attack_errors = (self._world_attack_errors + [str(error)[:96]])[-4:]
        return None
    self._world._queue(pc_uid, wire)
    return prepared


# Historical import path; the basic attack lane is mandatory core.
from tools.local_original_session.world_core_session import _world_attack


def _world_npc_hit(self, uid):
    """One explicit HP-bar candidate per normal damaging hit; no auto steps."""
    if os.environ.get('SL_EXPERIMENT_HPBAR') not in ('1', '2', '3'):
        return
    from tools.local_original_session.world_hpbar_experiment import build_hpbar_experiment_frames
    entity = self._world.entities.get(uid)
    if entity is None:
        return
    for wire in build_hpbar_experiment_frames(uid):
        for pc_uid in self._world._watchers(entity):
            self._world._queue(pc_uid, wire)


METHODS = (
    _world_prepare_pc_attack,
    _world_npc_hit,
)


def setup_arrow(self):
    self._world_attack_errors = []
    arrow = os.environ.get('SL_EXPERIMENT_ARROW', '0').split(',')
    need(len(arrow) in (1, 2), 'WORLD_ARROW_EXPERIMENT_REQUIRED')
    self._world.arrow_id = int(arrow[0])
    self._world.arrow_mode = int(arrow[1]) if len(arrow) == 2 else 1
    need(-(1 << 31) <= self._world.arrow_id < (1 << 31)
         and self._world.arrow_mode in (1, 2), 'WORLD_ARROW_EXPERIMENT_REQUIRED')


def _world_combat_report(self, result):
    result['attack_errors'] = list(self._world_attack_errors)


METHODS += (setup_arrow, _world_combat_report, _world_combat_initialize,
            _world_attack_continue, _world_far_attack, _world_combat_before_leave)
HOOKS = {'initialize': ('setup_arrow', '_world_combat_initialize'),
         'prepare_attack': ('_world_prepare_pc_attack',),
         'before_leave': ('_world_combat_before_leave',),
         'npc_hit': ('_world_npc_hit',), 'report': ('_world_combat_report',)}
FRAMES = {CONTINUE_REQUEST: ('_world_attack_continue',), FAR_ATTACK: ('_world_far_attack',)}
OUTGOING_OPCODES = (CONTINUE_ACK,)
NONCRITICAL_HOOKS = ('npc_hit', 'report')

# Read-only admission providers use lower priorities; the cost owner runs last.
HOOK_PRIORITY = {'prepare_attack': 100}
