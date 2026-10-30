"""MapExp5 paid Dream Island entry through the existing town-service owner.

The actual current phantasmisland UML/action is retained. Eldin's identity,
placement,1000A price and role sprite are attributed LOCAL backend policy.
No direct calls to other optional features, request-time IO or new save owner.
"""
from dataclasses import replace
import json
from pathlib import Path
from types import MappingProxyType


def _map_expansion5_town_setup(ctx, setup, policy):
    if 303 not in policy.maps:
        return setup
    from tools.local_original_session import world_town
    from tools.local_original_session.world_town_services import ServiceMenuSource, TeleportDestination
    document = json.loads((Path(__file__).parent/'data/m6/map_expansion5.json').read_text(encoding='utf-8'))
    town = setup.town
    additions, teleports, sources = {}, {}, []
    for row in document['teleporters']:
        mid,x,y = row['position']
        key = row['npc_id'],row['placement_id']
        spawn = world_town._freeze(dict(id=row['placement_id'],count=1,npc_templateid=row['npc_id'],
            mapid=mid,locx=x,locy=y,randomx=0,randomy=0,heading=4,source_ref=row['spawn_ref']))
        metadata = world_town._freeze(dict(l1j_name=row['name'],l1j_impl='L1Teleporter',
            classification='teleport',mapping_status='LOCAL_MAP5_ROLE_VISUAL_NATIVE_IDENTITY_UNKNOWN',
            selected_classic_npc_id=None,classic_npc_candidates=[],
            selected_classic_sprite_id=row['sprite'],appearance_policy=row['appearance_policy'],
            dialogue=dict(normal_action=row['stem']),source_ref=row['npc_ref']))
        additions[key] = world_town.TownNpc(key,'village',metadata,spawn)
        action = 'teleport '+row['action']
        teleports[(row['npc_id'],action)] = TeleportDestination(row['npc_id'],action,
            '몽환의 섬',*row['destination'],row['price'],None,row['ref'])
        sources.append(ServiceMenuSource(key,row['stem'],MappingProxyType({row['stem']:(row['action'],)}),'teleport'))
    town.data = replace(town.data,placements=MappingProxyType(dict(town.data.placements)|additions))
    town.register(replace(town.config,candidate_npc_ids=town.config.candidate_npc_ids|frozenset(k[0] for k in additions)))
    services = replace(setup.services,teleports=MappingProxyType(dict(setup.services.teleports)|teleports),
        teleporter_ids=setup.services.teleporter_ids|frozenset(k[0] for k in additions))
    return replace(setup,services=services,sources=setup.sources+tuple(sources))


METHODS = (_map_expansion5_town_setup,)
HOOKS = {'dungeon_town_setup':('_map_expansion5_town_setup',)}
