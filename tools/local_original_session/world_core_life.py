"""World core: life. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_original_session import movement


def _world_pc_died(self, uid):
    """Death-once callback from WorldView; keep HP0/status/death wire order."""
    from dataclasses import replace
    from tools.local_original_session import world_reward, world_combat
    from tools.local_original_session.world_progress import exp_percent
    world = self._world
    state = world.combat.pcs[uid]
    try:
        penalty = world_reward.death_exp_penalty(world.exp[uid], data=world.data)
        hp, mp = world_reward.delevel_maxima(
            world_reward.RewardPcState.from_combat(state, exp=world.exp[uid]),
            penalty.new_level, world.combat.rng, data=world.data)
    except ValueError as error:
        # The final supplied level has no next-level threshold. Do not invent one.
        self._world_progress_errors = (self._world_progress_errors + [str(error)[:96]])[-4:]
        return
    world.progress.adopt(uid, replace(world.progress.snapshot(uid),
        exp=penalty.new_exp, level=penalty.new_level, max_hp=hp, max_mp=mp))
    state.status_fields.update({2: penalty.new_level,
        26: exp_percent(world.data, penalty.new_exp, penalty.new_level)})
    self._world_recalculate_uid(uid)
    frames = world.outbox.get(uid, [])
    for index in range(len(frames) - 1, -1, -1):
        if int.from_bytes(frames[index][2:4], 'little') == 0x4e38:
            frames[index] = world_combat.status_frame(state.status_fields, 0)
            break
    world.progress.mark(uid)
    self._world_save_progress(uid)


def _world_commit_respawn(self, uid, *, strict=False):
    """Dead PC's town return: persist data/m1/town.json respawn_point through the
    existing PositionStore before the next selection restores it. Runs only when
    no restart/quit drain binding still compares the old saved position.

    The pending return is dropped only after the town save (or when already in
    town). A failure keeps it for the next selection/cleanup; ``strict`` (the
    selection path) re-raises so the dead PC never enters at the old position.
    """
    name = self._world_respawn.get(uid)
    if name is None or self._world is None:
        return False
    town = self._world.data.town
    try:
        destination = self._world_relocations.get(uid)
        target = (movement.Position(uid, name, town.map_id, town.respawn_x, town.respawn_y)
                  if destination is None else movement.Position(uid, name, destination.map_id,
                                                              destination.x, destination.y))
        current = self.realm.positions.restore(target)
        if current != target:
            # Dungeon death returns to town: a map change is a transition commit.
            self.realm.positions.commit(current, target,
                                        transition=current.map_id != target.map_id)
    except Exception as error:
        self._world_respawn_errors = (self._world_respawn_errors + [type(error).__name__])[-4:]
        if strict:
            raise
        return False
    self._world_respawn.pop(uid, None)
    self._world_relocations.pop(uid, None)
    return True


def _world_unserved_return(self, uid, name):
    """Selection of a PC saved on a map this run does not serve (map experiment
    off): move the saved position to the town respawn point so the entry uses a
    served map instead of failing the broker."""
    if self._world is None:
        return False
    town = self._world.data.town
    target = movement.Position(uid, name, town.map_id, town.respawn_x, town.respawn_y)
    current = self.realm.positions.restore(target)
    if self.realm.serves_map(current.map_id):
        return False
    self.realm.positions.commit(current, target, transition=current.map_id != target.map_id)
    return True


METHODS = (
    _world_pc_died,
    _world_commit_respawn,
    _world_unserved_return,
)
HOOKS = {'after_death': ('_world_pc_died',)}


def realm_bind_restart(realm, game, life_broker, restart_game):
    if life_broker is None and getattr(realm, '_world_dead_restart', False) is True:
        game.routes[0x4eec] = restart_game


def _world_set_relocation(self, uid, destination):
    self._world_relocations[uid] = destination

METHODS += (_world_set_relocation,)
SAVE_BOUNDARIES = {'_world_pc_died': True, '_world_commit_respawn': True}
