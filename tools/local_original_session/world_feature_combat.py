"""World feature: combat. Existing packet/store operations, unchanged."""
from __future__ import annotations

import os
from tools.local_original_session.world_bridge import need


def _world_prepare_pc_attack(self, pc_uid, target, now):
    """Called after world life/cadence/LOS checks, before hit RNG/cooldown."""
    from tools.local_original_session import inventory, world_ammo, world_combat
    pc = self._world.entities.get(pc_uid)
    effect = getattr(self, '_item_equipment_effect', None)
    weapon, _ = (None, 0) if effect is None else effect.combat_inputs(pc_uid)
    if weapon is None or weapon.weapon_type != 'bow':
        if max(abs(pc.x - target.x), abs(pc.y - target.y)) > world_combat.MELEE_RANGE:
            return None
        return world_ammo.AttackPreparation(True)
    writer = next((writer for writer, uid in self._world_pcs.values() if uid == pc_uid), None)
    if writer is None or self._inventory_kit_policy != inventory.KIT_POLICY:
        return None
    items = inventory.validate_kit_frame(self.inventory_frame)
    prepared = world_ammo.prepare_attack(weapon,
        (world_ammo.AmmoStack(item.identifier, item.template_bits, dict(item.raw_fields)[4])
         for item in items), attacker=(pc.map_id, pc.x, pc.y),
        target=(target.map_id, target.x, target.y), items=self._world.data.items)
    if not prepared.allowed:
        return None
    cost = prepared.cost
    try:
        wire = self._world_consume_kit(writer, cost.item_uid, cost.count)
    except ValueError as error:
        self._world_item_errors = (self._world_item_errors + [str(error)[:96]])[-4:]
        return None
    self._world._queue(pc_uid, wire)
    return prepared


async def _world_attack(self, writer, row, game, frame, operation_lock):
    """CS4E30 on a world monster: immediate swing. False = not ours, keep the original route."""
    from tools.local_original_session import attack
    bound = self._world_pcs.get(id(writer))
    if bound is None or bound[0] is not writer or self._world_ready(writer, game) is None:
        return False
    try:
        request = attack.parse_payload(frame.payload)
    except ValueError:
        return False
    event = self._world_events.get(bound[1])
    if event is not None:
        event.clear()
    frames = await self._world.runtime.dispatch_now(self._world.pc_attack, bound[1],
                                                    request.target_uid)
    if frames is None:
        if event is not None:
            event.set()  # queued frames stay for the next flush
        # Not a world monster. Without the original attack route the request
        # has no handler; answer nothing instead of failing the session.
        return getattr(self, '_attack_session', None) is None
    self._world_save_progress(bound[1])  # kill reward: EXP/level saved before the status is sent
    await self._world_send(writer, row, frames, operation_lock)
    return True


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
    _world_attack,
    _world_npc_hit,
)
FRAMES = {0x4e30: ('_world_attack',)}
HOOKS = {'prepare_attack': ('_world_prepare_pc_attack',), 'npc_hit': ('_world_npc_hit',)}


def setup_arrow(self):
    arrow = os.environ.get('SL_EXPERIMENT_ARROW', '0').split(',')
    need(len(arrow) in (1, 2), 'WORLD_ARROW_EXPERIMENT_REQUIRED')
    self._world.arrow_id = int(arrow[0])
    self._world.arrow_mode = int(arrow[1]) if len(arrow) == 2 else 1
    need(-(1 << 31) <= self._world.arrow_id < (1 << 31)
         and self._world.arrow_mode in (1, 2), 'WORLD_ARROW_EXPERIMENT_REQUIRED')
