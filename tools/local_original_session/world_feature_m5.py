"""Optional M5 mainland villages, using the existing town/trade/map owners.

SL_EXPERIMENT_M5=1 plus SL_EXPERIMENT_MAP=2 opts into this LOCAL policy.
The current UML actions are client data; NPC placements, fees and role visuals
are attributed backend choices. No claim of native input/render equivalence.
All reads occur in initialize. Removing this module registration restores the
existing server without a core dependency or method replacement.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
import json
import os
from pathlib import Path
from types import MappingProxyType

from tools.local_original_session import game_data, world_town
from tools.local_original_session.world_maps import load_getback_policy
from tools.local_original_session.world_shop import ShopData
from tools.local_original_session.world_item_effects import ItemEffectResult, movement_requirements

M5_DATA_DIR = Path(__file__).resolve().parent / 'data/m5'


def _read(directory, name):
    return json.loads((Path(directory) / name).read_text(encoding='utf-8'))


@dataclass(frozen=True)
class MainlandPolicy:
    towns: tuple
    scenario: dict
    getback: object

    def return_candidates(self, map_id, x, y, character_class=None):
        return self.getback.candidates_for(map_id, x, y, character_class)

    def return_for(self, map_id, x, y, character_class=None, *, rng=None):
        return self.getback.return_for(map_id, x, y, character_class, rng=rng)


def load_m5_policy(directory=M5_DATA_DIR, *, can_stand=None):
    towns = _read(directory, 'towns.json')['towns']
    towns.insert(0,dict(town_id='gludin',return_point=dict(map_id=4,x=32608,y=32734,heading=5)))
    groups = _read(directory, 'spawns.json')['groups']
    field = next(g['group_id']['value'] for g in groups if g['town_id']=='kent')
    return MainlandPolicy(tuple(world_town._freeze(t) for t in towns),
        MappingProxyType(dict(gludin_teleporter_id=50024,kent_action='gludin-kent',
            kent_center=(33050,32782),kent_shop_id=70018,kent_warehouse_id=60003,
            kent_field_group=field)),
        load_getback_policy(Path(directory) / 'returns.json', can_stand=can_stand))


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


@dataclass(frozen=True, slots=True)
class MainlandReturnResult(ItemEffectResult):
    """Carry the requesting character through UID-free destination hooks."""
    return_uid: int | None = None


class MainlandItemEffects:
    """Delegate effects; retain immutable requester identity for final policy.

    Earlier map/dungeon hooks use dataclasses.replace, preserving return_uid.
    No mutable last-request UID and no effect/cost implementation is replaced.
    """
    def __init__(self, previous, policy):
        self.previous,self.policy=previous,policy

    def __getattr__(self,name):
        return getattr(self.previous,name)

    def __setattr__(self, name, value):
        # The consumable startup and save hooks replace states/store on the
        # effect owner. Keep writes on the same object whose bound methods
        # __getattr__ exposes; otherwise restored rows sit only on this proxy.
        if name in ('previous', 'policy'):
            object.__setattr__(self, name, value)
        else:
            setattr(self.previous, name, value)

    def use(self,uid,template_id,now,*,position=None,ailments=None,**options):
        result=self.previous.use(uid,template_id,now,position=position,ailments=ailments,**options)
        if position is not None and result.kind=='return_town' and result.destination is not None:
            return MainlandReturnResult(**{field.name: getattr(result, field.name)
                for field in fields(ItemEffectResult)}, return_uid=uid)
        return result


def _m5_initialize(ctx):
    ctx._world_m5=None
    if os.environ.get('SL_EXPERIMENT_M5','0')!='1' or ctx._world_map_exp!=2:
        return
    from tools.local_original_session.world_interest_spawn import InterestSpawner
    world=ctx.world
    world.terrain.bounds(4) # explicit startup preload
    policy=load_m5_policy(can_stand=world.terrain.can_stand)
    data=load_m5_data(world.data)
    addition=replace(data,spawns=tuple(s for s in data.spawns
                                      if s.group_id not in {g.spec.group_id for g in world.spawner.groups}))
    extra_spawner=InterestSpawner(world.entities,addition,passable=world.spawner.passable,
                                 rng=world.spawner.rng)
    world.spawner.groups.extend(extra_spawner.groups)
    world.replace_data(data)
    ctx._world_m5=policy
    previous = getattr(ctx, '_world_item_effects', None)
    if previous is not None:
        ctx._world_item_effects = MainlandItemEffects(previous, policy)



def _m5_town_setup(ctx, setup):
    if os.environ.get('SL_EXPERIMENT_M5', '0') != '1' or ctx._world_map_exp != 2:
        return setup
    from tools.local_original_session import world_town_services
    from tools.local_original_session.world_shop_menu import MenuSource
    world = ctx.world
    old=setup.town
    town_data=load_m5_town(old.data)
    menu_document=_read(M5_DATA_DIR,'npc_menus.json')
    resources=menu_document['resources']
    bindings={entry['l1j_npc_id']:entry for entry in menu_document['runtime_bindings']}
    ctx._world_m5_dialogues={}
    routes=world_town_services.load_town_services(M5_DATA_DIR)
    current=setup.services
    services=replace(current,
        teleports=MappingProxyType(dict(current.teleports)|dict(routes.teleports)),
        teleporter_ids=current.teleporter_ids|routes.teleporter_ids,
        inn_ids=current.inn_ids|routes.inn_ids)
    sources=[];visuals={};enabled=set(old.config.candidate_npc_ids)
    source_keys={source.placement_key for source in setup.sources}
    for key,npc in town_data.placements.items():
        if npc.spawn['count']<=0 or npc.spawn['mapid']!=4 or key in source_keys:
            continue
        binding=bindings.get(npc.npc_id)
        if binding is None and npc.shop_row is not None and npc.shop_row['shop_row_count']>0:
            # Preserve the former loader's M2/M4 merchant contribution. These
            # placements are outside the M5 identity table (currently Luth),
            # and retain their existing resource/appearance/experiment policy.
            prior=(npc.row.get('dialogue') or {}).get('normal_action')
            if prior and prior not in resources and prior+'1' in resources:prior+='1'
            if {'buy','sell'}<=set(resources.get(prior,{}).get('actions',())):
                binding={'initial_stem':prior,'role':'shop'}
        if binding is None or binding['initial_stem'] is None:
            continue
        stem,role=binding['initial_stem'],binding['role']
        resource=resources[stem]
        visual=world_town.appearance_for(npc).sprite_id
        candidate=npc.row.get('same_number_classic_sprite_candidate')
        if visual is None:
            if role=='teleport':visual=940
            elif role=='warehouse':visual=143
            elif role in ('shop','inn') and candidate:visual=candidate['sprite_id']
        if visual is None:
            continue # Content evidence does not supply an unselected appearance.
        if role=='shop':
            source=MenuSource(key,stem,tuple(resource['actions']),setup.shop_experiment)
        else:
            # A native <a link> changes the client document without 4ED4. Its
            # descendant actions still echo this current root context. An
            # action=teleportURL instead needs a real server-issued next page.
            def page_actions(page,seen=None):
                seen=set() if seen is None else seen
                if page in seen:return ()
                seen.add(page)
                item=resources[page]
                return tuple(dict.fromkeys((*item['actions'],*(action
                    for linked in item.get('client_links',()) if linked in resources
                    for action in page_actions(linked,seen)))))
            pages=MappingProxyType({page:page_actions(page) for page in binding['page_stems']})
            source=world_town_services.ServiceMenuSource(key,stem,pages,role)
            ctx._world_m5_dialogues[key]=binding
        sources.append(source)
        if world_town.appearance_for(npc).sprite_id is None:visuals[key]=visual
        enabled.add(npc.npc_id)
    # Old selected catalog actors and unknown scope/count rows keep their own
    # rules; services are never allowed to stand on blocked or unknown tiles.
    config=replace(old.config,candidate_npc_ids=frozenset(enabled)|world_town.confirmed_npc_ids(town_data))
    town=MainlandTownNpcs(world.entities,town_data,config,passable=world.terrain.can_stand,
                         local_visuals=visuals)
    # Startup ownership transfer preserves already-issued actors and explicit
    # HostNpcSource UID bindings. Register only reconciles/adds this owner's
    # placements; the detached former owner must no longer remove them.
    town.adopt_registration(old)
    town.register()
    return replace(setup, town=town, services=services,
                   sources=setup.sources + tuple(sources))


def _m5_dialogue_action(ctx,host,interaction,menu,fields,now):
    """Only this feature's prepared menus; existing service owners keep commits."""
    from tools.local_original_session.world_bridge import need
    from tools.local_original_session.world_handlers import Dialogue
    binding=getattr(ctx,'_world_m5_dialogues',{}).get(interaction.npc.key)
    if binding is None:return False
    stem,action=menu.fields[2].decode('utf-8'),fields[2].decode('utf-8')
    destination=binding['transitions'].get(stem,{}).get(action)
    if destination is not None:
        next_menu=Dialogue({1:fields[1],2:destination.encode('utf-8')},menu.source)
        host.send_frame(host.wire.dialogue_frame(next_menu.fields))
        menu.source.delivered=False
        host.pending.append(menu.source)
        host.state.menu,host.state.window=next_menu,None
        return True
    # Unimplemented pet/guild/quest/tax/house actions must never fall through
    # to the generic paid-teleport owner. Local document links issue no packet.
    need(action in binding['supported_service_actions'],'M5_DIALOGUE_ACTION_NOT_READY')
    return False


def _m5_after_death(ctx,uid):
    policy=ctx._world_m5
    if policy is None:return
    entity=ctx.world.entities.get(uid)
    if entity is not None:
        pc = ctx.world.combat.pcs.get(uid)
        character_class = None if pc is None else pc.profile.character_class
        destination=policy.return_for(entity.map_id,entity.x,entity.y,character_class,
                                      rng=ctx.world.combat.rng)
        if destination is not None:
            ctx._world_set_relocation(uid, destination)


def _m5_destination(ctx, result, position):
    policy = ctx._world_m5
    if policy is not None and position is not None and result.kind == 'return_town' and result.destination is not None:
        uid = getattr(result, 'return_uid', getattr(position, 'uid', None))
        pc = ctx.world.combat.pcs.get(uid)
        character_class = None if pc is None else pc.profile.character_class
        x = position.x if hasattr(position, 'x') else position.word0
        y = position.y if hasattr(position, 'y') else position.word1
        destination = policy.return_for(position.map_id, x, y, character_class,
                                        rng=ctx.world.combat.rng)
        if destination is not None:
            return replace(result, destination=destination,
                requirements=movement_requirements(position.map_id, destination))
    return result


METHODS=(_m5_initialize,_m5_after_death,_m5_town_setup,_m5_destination,_m5_dialogue_action)
HOOKS={'initialize':('_m5_initialize',),'after_death':('_m5_after_death',),
       'town_setup':('_m5_town_setup',),'item_destination_policy':('_m5_destination',),
       'service_action':('_m5_dialogue_action',)}
HOOK_PRIORITY={'service_action':10, 'item_destination_policy':30, 'after_death':30}
