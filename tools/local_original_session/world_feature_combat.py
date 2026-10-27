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


METHODS += (setup_arrow, _world_combat_report)
HOOKS = {'initialize': ('setup_arrow',), 'prepare_attack': ('_world_prepare_pc_attack',),
         'npc_hit': ('_world_npc_hit',), 'report': ('_world_combat_report',)}
NONCRITICAL_HOOKS = ('npc_hit', 'report')

# Read-only admission providers use lower priorities; the cost owner runs last.
HOOK_PRIORITY = {'prepare_attack': 100}
