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
from tools.local_original_session.world_maps import (DungeonPolicy, MapDestination,
    MapTransition, load_dungeon_policy)


def load_island_policy(directory=None):
    """Compose the sourced map70 population/link fragment at startup."""
    directory = Path(__file__).resolve().parent / 'data/m6' if directory is None else Path(directory)
    policy = load_dungeon_policy(directory)
    island = game_data._read(directory, 'forgotten_island_spawns.json')
    transitions = dict(policy.transitions)
    for row in island['transitions']:
        transitions[tuple(row['origin'])] = MapTransition(
            MapDestination(*row['destination']), row['ref'], row['source'],
            row['native_trigger_status'], tuple(row['reference_origin']), row['local_basis'])
    return DungeonPolicy(policy.maps + (70, 83), MappingProxyType(transitions), policy.returns)


def load_dungeon_data(base, directory=None):
    directory = Path(__file__).resolve().parent / 'data/m6' if directory is None else Path(directory)
    monsters = game_data._monsters(game_data._read(directory, 'monsters.json'))
    spawns = game_data._spawns(game_data._read(directory, 'spawns.json'))
    spawns += game_data._spawns(game_data._read(directory, 'map_expansion2.json'))
    spawns += game_data._spawns(game_data._read(directory, 'map_expansion3.json'))
    spawns += game_data._spawns(game_data._read(directory, 'map_expansion4.json'))
    spawns += game_data._spawns(game_data._read(directory, 'map_expansion5.json'))
    spawns += game_data._spawns(game_data._read(directory, 'map_expansion6.json'))
    spawns += game_data._spawns(game_data._read(directory, 'forgotten_island_spawns.json'))
    drops, unresolved = game_data._drops(game_data._read(directory, 'drops.json'))
    population = game_data._read(directory, 'map_expansion2_population.json')
    monsters = dict(monsters) | dict(game_data._monsters(population))
    spawns += game_data._spawns(population)
    population_drops, population_unresolved = game_data._drops(population)
    drops = dict(drops) | dict(population_drops)
    unresolved += population_unresolved
    map0 = game_data._read(directory, 'map0_population.json')
    monsters = dict(monsters) | dict(game_data._monsters(map0))
    map0_groups = game_data._spawns(map0)
    replacements = {spec.group_id: spec for spec in map0_groups}
    existing_ids = {spec.group_id for spec in base.spawns}
    base_spawns = tuple(replacements.get(spec.group_id, spec) for spec in base.spawns)
    spawns += tuple(spec for spec in map0_groups if spec.group_id not in existing_ids)
    # Existing template policies have priority; no shared-world balance rewrite.
    return replace(base,
        monsters=MappingProxyType(dict(monsters) | dict(base.monsters)),
        spawns=base_spawns + spawns,
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
    if self._world_map_exp != 2:
        self._world_dungeon_policy = None
        return
    policy = getattr(self, '_world_dungeon_policy', None) or load_island_policy()
    world = self.world
    data = load_dungeon_data(world.data)
    from tools.local_original_session.world_interest_spawn import Group, Slot
    # initialize runs before the world runtime starts and before a PC binds.
    # Preserve the existing spawner, callbacks, RNG, slots and runtime tick hook.
    # Map0 replacements retain group identity. There are no live UIDs at this
    # startup stage; size the empty slots from the selected population policy.
    specs = {spec.group_id: spec for spec in data.spawns}
    for group in world.spawner.groups:
        spec = specs[group.spec.group_id]
        if spec != group.spec:
            group.spec = spec
            group.monster = data.monsters[spec.template_id]
            group.slots = [Slot(index) for index in range(spec.target_count)]
    additions = data.spawns[len(world.data.spawns):]
    world.spawner.groups.extend(Group(spec, data.monsters[spec.template_id],
        [Slot(index) for index in range(spec.target_count)]) for spec in additions)
    world.replace_data(data)
    for map_id in policy.maps:
        world.terrain.bounds(map_id)
    self._world_dungeon_policy = policy


def _world_dungeons_town_setup(self, setup):
    if self._world_map_exp != 2:
        return setup
    policy = getattr(self, '_world_dungeon_policy', None) or load_island_policy()
    self._world_dungeon_policy = policy
    return self.fold_sync_hooks('dungeon_town_setup', setup, policy)


def _world_dungeons_death(self, uid):
    policy = self._world_dungeon_policy
    if policy is None:
        return
    entity = self.world.entities.get(uid)
    destination = None if entity is None else policy.return_for(entity.map_id)
    if destination is not None:
        # The existing life owner consumes this on reselect/cleanup.
        self._world_set_relocation(uid, destination)


def _world_dungeons_destination(self, result, position):
    policy = self._world_dungeon_policy
    destination = None if policy is None or position is None else policy.return_for(position.map_id)
    if destination is not None and result.kind == 'return_town' and result.destination is not None:
        from tools.local_original_session.world_item_effects import movement_requirements
        return replace(result, destination=destination,
                       requirements=movement_requirements(position.map_id, destination))
    return result


def _world_dungeons_transition(self, destination, map_id, x, y):
    policy = self._world_dungeon_policy
    if destination is None and policy is not None:
        from tools.local_original_session.world_maps import resolve_transition
        return resolve_transition(map_id, x, y, extra=policy.transitions)
    return destination


def _world_dungeons_serves_map(realm, served, map_id):
    policy = realm._world_context._world_dungeon_policy
    return served or policy is not None and map_id in policy.maps


METHODS = (_world_dungeons_initialize, _world_dungeons_death, _world_dungeons_destination,
           _world_dungeons_transition, _world_dungeons_town_setup)
HOOKS = {'initialize': ('_world_dungeons_initialize',),
         'town_setup': ('_world_dungeons_town_setup',),
         'after_death': ('_world_dungeons_death',),
         'item_destination_policy': ('_world_dungeons_destination',),
         'map_transition': ('_world_dungeons_transition',)}
REALM_HOOKS = {'serves_map': (_world_dungeons_serves_map,)}
