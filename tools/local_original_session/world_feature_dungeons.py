"""Optional MapExp2 dungeon data, stairs and return policy.

The existing map feature owns movement/publication and all durable position
changes. This module only installs immutable startup data and a return proposal.
Removing its registration retains the existing map0/1/2/4 behavior.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from tools.local_original_session import game_data
from tools.local_original_session.world_maps import load_dungeon_policy


def load_dungeon_data(base, directory=None):
    directory = Path(__file__).resolve().parent / 'data/m6' if directory is None else Path(directory)
    monsters = game_data._monsters(game_data._read(directory, 'monsters.json'))
    spawns = game_data._spawns(game_data._read(directory, 'spawns.json'))
    drops, unresolved = game_data._drops(game_data._read(directory, 'drops.json'))
    # Existing template policies have priority; no shared-world balance rewrite.
    return replace(base,
        monsters=MappingProxyType(dict(monsters) | dict(base.monsters)),
        spawns=base.spawns + spawns,
        drops=MappingProxyType(dict(drops) | dict(base.drops)),
        drops_unresolved=base.drops_unresolved + unresolved)


class DungeonItemEffects:
    """Compose the previous effect owner; change only sourced return proposals."""

    def __init__(self, previous, policy):
        self.previous, self.policy = previous, policy
        self.combat, self.terrain = previous.combat, previous.terrain
        self.definitions, self.rng = previous.definitions, previous.rng

    def use(self, uid, template_id, now, *, position=None, ailments=None):
        result = self.previous.use(uid, template_id, now, position=position, ailments=ailments)
        destination = None if position is None else self.policy.return_for(position.map_id)
        if (destination is not None and result.kind == 'return_town'
                and result.destination is not None):
            from tools.local_original_session.world_item_effects import movement_requirements
            return replace(result, destination=destination,
                requirements=movement_requirements(position.map_id, destination))
        return result


def _world_dungeons_initialize(self):
    self._world_dungeon_policy = None
    self.realm._world_dungeon_maps = ()
    if self._world_map_exp != 2:
        return
    policy = load_dungeon_policy()
    world = self.world
    data = load_dungeon_data(world.data)
    from tools.local_original_session.world_interest_spawn import Group, Slot
    # initialize runs before the world runtime starts and before a PC binds.
    # Preserve the existing spawner, callbacks, RNG, slots and runtime tick hook.
    additions = data.spawns[len(world.data.spawns):]
    world.spawner.groups.extend(Group(spec, data.monsters[spec.template_id],
        [Slot(index) for index in range(spec.target_count)]) for spec in additions)
    world.data = world.combat.data = world.ground.data = data
    for map_id in policy.maps:
        world.terrain.bounds(map_id)
    self._world_dungeon_policy = policy
    self.realm._world_dungeon_maps = policy.maps
    self._world_item_effects = DungeonItemEffects(self._world_item_effects, policy)


def _world_dungeons_death(self, uid):
    policy = self._world_dungeon_policy
    if policy is None:
        return
    entity = self.world.entities.get(uid)
    destination = None if entity is None else policy.return_for(entity.map_id)
    if destination is not None:
        # The existing life owner consumes this on reselect/cleanup.
        self._world_relocations[uid] = destination


METHODS = (_world_dungeons_initialize, _world_dungeons_death)
HOOKS = {'initialize': ('_world_dungeons_initialize',),
         'after_death': ('_world_dungeons_death',)}
