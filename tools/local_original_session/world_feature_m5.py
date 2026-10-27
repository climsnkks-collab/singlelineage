"""Optional M5 mainland villages, using the existing town/trade/map owners.

SL_EXPERIMENT_M5=1 plus SL_EXPERIMENT_MAP=2 opts into this LOCAL policy.
The current UML actions are client data; NPC placements, fees and role visuals
are attributed backend choices. No claim of native input/render equivalence.
All reads occur in initialize. Removing this module registration restores the
existing server without a core dependency or method replacement.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
from types import MappingProxyType

from tools.local_original_session import game_data, world_town
from tools.local_original_session.world_maps import MapDestination
from tools.local_original_session.world_shop import ShopData
from tools.local_original_session.world_item_effects import movement_requirements

M5_DATA_DIR = Path(__file__).resolve().parent / 'data/m5'


def _read(directory, name):
    return json.loads((Path(directory) / name).read_text(encoding='utf-8'))


@dataclass(frozen=True)
class MainlandPolicy:
    towns: tuple
    scenario: dict

    def return_for(self, map_id, x, y):
        """Nearest fixed map4 town point; distance and tie order are LOCAL.

        Gludin participates so the existing west-mainland behavior is retained.
        No per-character bind point or official GetBack classification is claimed.
        """
        if map_id != 4:
            return None
        town = min(self.towns, key=lambda t:max(abs(x-t['return_point']['x']),
                                               abs(y-t['return_point']['y'])))
        return MapDestination(**town['return_point'])


def load_m5_policy(directory=M5_DATA_DIR):
    towns = _read(directory, 'towns.json')['towns']
    towns.insert(0,dict(town_id='gludin',return_point=dict(map_id=4,x=32608,y=32734,heading=5)))
    groups = _read(directory, 'spawns.json')['groups']
    field = next(g['group_id']['value'] for g in groups if g['town_id']=='kent')
    return MainlandPolicy(tuple(world_town._freeze(t) for t in towns),
        MappingProxyType(dict(gludin_teleporter_id=50024,kent_action='gludin-kent',
            kent_center=(33050,32782),kent_shop_id=70018,kent_warehouse_id=60003,
            kent_field_group=field)))


def load_m5_data(base, directory=M5_DATA_DIR):
    """Use the established M1 parser; retain existing shared template policy."""
    directory=Path(directory)
    monsters=game_data._monsters(_read(directory,'monsters.json'))
    spawns=game_data._spawns(_read(directory,'spawns.json'))
    drops, unresolved=game_data._drops(_read(directory,'drops.json'))
    new=set(monsters)-set(base.monsters)
    return replace(base, monsters=MappingProxyType(dict(monsters)|dict(base.monsters)),
        spawns=base.spawns+spawns,
        drops=MappingProxyType(dict(drops)|dict(base.drops)),
        drops_unresolved=base.drops_unresolved+tuple(r for r in unresolved if r.template_id in new))


def load_m5_town(base, directory=M5_DATA_DIR):
    extra=world_town.load_town(directory)
    return world_town.TownData(MappingProxyType(dict(extra.placements)|dict(base.placements)),
        ShopData(MappingProxyType(dict(extra.shops.npcs)|dict(base.shops.npcs)),
                 MappingProxyType(dict(extra.shops.offers)|dict(base.shops.offers))),
        MappingProxyType(dict(base.source_documents)|{'m5':extra.source_documents}))


class MainlandTownNpcs(world_town.TownNpcs):
    """Preserve catalog unknowns; show only explicitly chosen LOCAL visuals."""
    def __init__(self,*args,local_visuals=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.local_visuals=local_visuals or {}

    def appearance(self,uid):
        result=super().appearance(uid)
        npc=self.npc_for(uid)
        if result is not None and result.sprite_id is None and npc is not None:
            visual=self.local_visuals.get(npc.key)
            if visual is not None:
                return replace(result,sprite_id=visual,
                    mapping_status='LOCAL_M5_ROLE_VISUAL_NATIVE_IDENTITY_UNKNOWN')
        return result


class MainlandItemEffects:
    """Delegate every effect to its current owner and select only return point."""
    def __init__(self, previous, policy):
        self.previous,self.policy=previous,policy

    def __getattr__(self,name):
        return getattr(self.previous,name)

    def use(self,uid,template_id,now,*,position=None,ailments=None):
        result=self.previous.use(uid,template_id,now,position=position,ailments=ailments)
        if position is not None and result.kind=='return_town' and result.destination is not None:
            destination=self.policy.return_for(position.map_id,position.x,position.y)
            if destination is not None:
                return replace(result,destination=destination,
                    requirements=movement_requirements(position.map_id,destination))
        return result


def _m5_initialize(ctx):
    ctx._world_m5=None
    if os.environ.get('SL_EXPERIMENT_M5','0')!='1' or ctx._world_map_exp!=2:
        return
    from tools.local_original_session import world_handlers, world_town_services
    from tools.local_original_session.world_interest_spawn import InterestSpawner
    from tools.local_original_session.world_shop_menu import MenuSource
    world=ctx.world
    policy=load_m5_policy()
    world.terrain.bounds(4) # explicit startup preload
    data=load_m5_data(world.data)
    addition=replace(data,spawns=tuple(s for s in data.spawns
                                      if s.group_id not in {g.spec.group_id for g in world.spawner.groups}))
    extra_spawner=InterestSpawner(world.entities,addition,passable=world.spawner.passable,
                                 rng=world.spawner.rng)
    world.spawner.groups.extend(extra_spawner.groups)
    world.data=world.combat.data=world.ground.data=data

    old=world.town
    town_data=load_m5_town(old.data)
    raw_services=_read(M5_DATA_DIR,'town_services.json')
    resources=_read(M5_DATA_DIR,'npc_menus.json')['resources']
    routes=world_town_services.load_town_services(M5_DATA_DIR)
    current=ctx._world_services
    ctx._world_services=replace(current,
        teleports=MappingProxyType(dict(current.teleports)|dict(routes.teleports)),
        teleporter_ids=current.teleporter_ids|routes.teleporter_ids,
        inn_ids=current.inn_ids|routes.inn_ids)
    route_stems={r['l1j_npc_id']:r['stem'] for r in raw_services['teleporters']}
    bank_ids={r['l1j_npc_id'] for r in raw_services['warehouse']['npcs']}
    inn_ids=routes.inn_ids
    sources=[];visuals={};enabled=set(old.config.candidate_npc_ids)
    existing_bindings=ctx._world_handler_bindings
    source_keys=set(existing_bindings.sources)
    for key,npc in town_data.placements.items():
        if npc.spawn['count']<=0 or npc.spawn['mapid']!=4:
            continue
        # Preserve explicitly supplied existing owners. Gludin Steve has no
        # prior normal-server binding; old M2 menus/quests retain their owners.
        if key in source_keys:
            continue
        stem=route_stems.get(npc.npc_id)
        if npc.npc_id in bank_ids:
            stem='storage'
        elif npc.npc_id in inn_ids:
            stem='inn'
        if stem is not None:
            resource=resources[stem]
            sources.append(world_town_services.ServiceMenuSource(key,stem,
                MappingProxyType({stem:tuple(resource['actions'])})))
            candidate=npc.row.get('same_number_classic_sprite_candidate')
            visual=(940 if npc.npc_id in route_stems else 143 if stem=='storage'
                    else candidate['sprite_id'] if candidate else None)
        elif npc.shop_row is not None and npc.shop_row['shop_row_count']>0:
            stem=(npc.row.get('dialogue') or {}).get('normal_action')
            if stem and stem not in resources and stem+'1' in resources:
                stem=stem+'1' # current native speaker suffix; still LOCAL binding
            resource=resources.get(stem,{})
            if not {'buy','sell'}<=set(resource.get('actions',())):
                continue
            sources.append(MenuSource(key,stem,tuple(resource['actions']),ctx._world_shop_experiment))
            candidate=npc.row.get('same_number_classic_sprite_candidate')
            visual=candidate['sprite_id'] if candidate else None
        else:
            continue
        if visual is None and world_town.appearance_for(npc).sprite_id is None:
            sources.pop() # Keep unavailable service data without invisible blockers.
            continue
        if visual is not None:visuals[key]=visual
        enabled.add(npc.npc_id)
    # Old selected catalog actors and unknown scope/count rows keep their own
    # rules; services are never allowed to stand on blocked or unknown tiles.
    config=replace(old.config,candidate_npc_ids=frozenset(enabled)|world_town.confirmed_npc_ids(town_data))
    town=MainlandTownNpcs(world.entities,town_data,config,passable=world.terrain.can_stand,
                         local_visuals=visuals)
    # Startup ownership transfer preserves already-issued actors and explicit
    # HostNpcSource UID bindings. Register only reconciles/adds this owner's
    # placements; the detached former owner must no longer remove them.
    town._owned=old._owned
    old._owned={}
    world.town=town
    town.register()
    # HostBindings is immutable. Keep the exact existing transport, policies,
    # custom UID allocator, seller callback, distance and externally supplied
    # resources, adding only new placement-key sources and the replacement town.
    ctx._world_handler_bindings=replace(existing_bindings,town=town,
        sources=MappingProxyType(dict(existing_bindings.sources)|{s.placement_key:s for s in sources}))
    ctx._world_m5=policy
    ctx._world_item_effects=MainlandItemEffects(ctx._world_item_effects,policy)


def _m5_after_death(ctx,uid):
    policy=ctx._world_m5
    if policy is None:return
    entity=ctx.world.entities.get(uid)
    if entity is not None:
        destination=policy.return_for(entity.map_id,entity.x,entity.y)
        if destination is not None:
            ctx._world_relocations[uid]=destination


METHODS=(_m5_initialize,_m5_after_death)
HOOKS={'initialize':('_m5_initialize',),'after_death':('_m5_after_death',)}
