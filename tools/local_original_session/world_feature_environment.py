"""Optional underwater backend policy; no second recovery timer or saved state.

Damage occurs at the existing natural HP recovery threshold, after existing
recovery/cap contributions. This LOCAL composition is not L1J's pre-cap net HP
calculation. Map/item correspondences and the reference boundaries are in
data/m1/underwater_policy.json. Removing this feature removes all consumers.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from tools.local_original_session.world_combat import status_frame, death_frame


@dataclass(frozen=True)
class UnderwaterPolicy:
    maps: frozenset[int]
    breathing_equipment: frozenset[int]
    damage: int

    def damage_for(self, map_id, *, breathing=False, worn=(), exempt=False):
        """PC and companion use their own effect and actually worn templates."""
        if (map_id not in self.maps or breathing or exempt
                or self.breathing_equipment.intersection(worn)):
            return 0
        return self.damage


def load_policy(path=None):
    path = Path(__file__).with_name('data') / 'm1/underwater_policy.json' if path is None else Path(path)
    row = json.loads(path.read_text(encoding='utf-8'))
    return UnderwaterPolicy(frozenset(item['map_id'] for item in row['maps']),
        frozenset(item['template_id'] for item in row['breathing_equipment']),
        row['damage_per_hp_recovery'])


class WorldEnvironment:
    def __init__(self, world, policy, *, equipped=lambda uid: (),
                 breathing=lambda uid, now: False, exempt=lambda uid: False):
        self.world, self.policy = world, policy
        self.equipped, self.breathing, self.exempt = equipped, breathing, exempt
        self.handles = []
        self.listeners = []

    def start(self):
        world = self.world
        self.handles = [
            world.runtime_extensions.wrap('environment', world.combat, 'regen_tick', self._recovery),
            world.runtime_extensions.wrap('environment', world, '_regen_tick', self._recovery_life),
        ]
        self.listeners = [
            ('close', world.events.add('environment', 'close', self.close)),
            ('environment_companion_hp_recovery', world.events.add('environment',
                'environment_companion_hp_recovery', self.companion_recovery)),
        ]

    def close(self):
        for handle in reversed(self.handles):
            handle.close()
        self.handles.clear()
        for event, listener in self.listeners:
            self.world.events.remove(event, listener)
        self.listeners.clear()

    def _recovery(self, base):
        def recover(uid):
            world = self.world
            pc = world.combat.pcs.get(uid)
            due = (pc is not None and not pc.dead and pc.hp > 0
                and pc.hp_points + pc.regen_state >= world.combat.regen.hp_threshold(pc.profile.level))
            frame = base(uid)
            position = world.pcs.get(uid)
            if not due or world.closed or position is None or world.combat.pcs.get(uid) is not pc:
                return frame
            damage = self.policy.damage_for(position[0],
                breathing=self.breathing(uid, world.runtime.clock()),
                worn=self.equipped(uid), exempt=self.exempt(uid))
            if not damage:
                return frame
            pc.hp = max(0, pc.hp - damage)
            pc.dead = pc.hp == 0
            return status_frame(pc.status_fields, pc.hp)
        return recover

    def _recovery_life(self, base):
        def recover(uid, due, now):
            world = self.world
            pc = world.combat.pcs.get(uid)
            alive = pc is not None and not pc.dead and pc.hp > 0
            result = base(uid, due, now)
            if alive and world.combat.pcs.get(uid) is pc and pc.dead:
                # Base queued the HP0 status first; the normal death owner emits
                # death-once, saves progress, releases AI and cancels its timer.
                world._pc_died(uid, now)
            return result
        return recover

    def companion_recovery(self, actor, now, worn=(), breathing=False):
        """Caller emits only at its existing hp_due, before its normal save.

        No companion private state/method is accessed. The installed follower
        runtime owns death/cancellation; the recovery caller owns the save.
        This callback is dormant until the companion owner adds the event.
        """
        world = self.world
        followers = world.extensions.get('followers')
        if followers is None or world.closed or not actor.record.alive or actor.record.hp <= 0:
            return 0
        entity = world.entities.resolve(actor.ref)
        if entity is None or followers.companions.get_actor(actor.ref.uid) is not actor:
            return 0
        damage = self.policy.damage_for(entity.map_id, worn=worn,
            breathing=breathing or self.breathing(actor.character_id, now),
            exempt=self.exempt(actor.character_id))
        before = actor.record.hp
        if damage:
            actor.record.hp = max(0, before - damage)
            if not actor.record.hp:
                followers.companions.die(actor.character_id, now)
                for uid in world._watchers(entity):
                    world._queue(uid, death_frame(entity.uid))
        return before - actor.record.hp


def _environment_initialize(ctx):
    ctx._world_environment_policy = load_policy()
    ctx._world_environment = None


def _environment_started(ctx):
    def equipped(uid):
        # EquipmentStore is the existing core inventory/equipment owner.
        effect = getattr(ctx, '_item_equipment_effect', None)
        if effect is None:
            return ()
        state, frame = effect.store.peek(uid)
        if state is None or frame is None:
            return ()
        from tools.local_original_session import inventory
        worn = {state.weapon_uid, *(item_uid for _, item_uid in state.slots)} - {0}
        return tuple(item.template_bits for item in inventory.validate_kit_frame(frame)
            if item.identifier in worn and dict(item.raw_fields)[4] > 0)

    owner = WorldEnvironment(ctx.world, ctx._world_environment_policy, equipped=equipped,
        breathing=lambda uid, now: ctx.chain_sync_hooks('environment_breathing', uid, now),
        exempt=lambda uid: ctx.chain_sync_hooks('environment_damage_exempt', uid))
    ctx._world_environment = owner
    owner.start()


def _environment_stopped(ctx):
    if ctx._world_environment is not None:
        ctx._world_environment.close()


METHODS = (_environment_initialize, _environment_started, _environment_stopped)
HOOKS = {'initialize': ('_environment_initialize',),
         'runtime_started': ('_environment_started',),
         'runtime_stopped': ('_environment_stopped',)}
