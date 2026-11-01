"""Optional crafting through original request5 and acknowledgement6.

Static native producers/consumers and the retained recipe tables establish the
wire subset. Native menu rendering/input and empty-refusal parser admission
remain unobserved. Internal listing objects are server references only.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from types import MappingProxyType

from tools.local_original_session.world_bridge import need
from tools.local_original_session import world_craft


@dataclass(frozen=True, slots=True)
class CraftListing:
    source: object
    ref: object
    npc_id: int
    recipes: tuple[world_craft.Recipe, ...]
    inventory: bytes


@dataclass(frozen=True, slots=True)
class CraftSelection:
    listing: CraftListing
    recipe: world_craft.Recipe


@dataclass(frozen=True, slots=True)
class CraftProvider:
    listing: object
    select: object
    make: object


def _world_craft_initialize(self):
    from tools.local_original_session.world_handlers import KitItemPolicy
    raw = json.loads(world_craft.DATA_PATH.read_text(encoding='utf-8'))
    self._world_craft_recipes = world_craft.load_recipes()
    self._world_craft_native = MappingProxyType({(r['l1j_npc_id'], r['native_recipe_id']): r
                                                for r in raw['recipes']})
    self._world_craft_npcs = MappingProxyType({n['l1j_npc_id']: n['npc_template_id']
                                             for n in raw['npcs']})
    policies = []
    for item in raw.get('items', ()):
        prototype = dict(self.starter_fields)
        prototype.update({2: item['template_id'], 7: item['icon'],
                          18: item['name_ko'].encode('utf-8')})
        policies.append(KitItemPolicy(item['template_id'], item['raw_weight'],
                                      item['stackable'], prototype))
    # Existing catalog policies retain their original variant/stack contract.
    self.add_item_policies(policies)
    self._world_craft_results = []


def _world_craft_town_setup(self, setup):
    """Publish original roots; the client owns craft_output/input and selection."""
    from dataclasses import replace
    from tools.local_original_session.world_town_services import ServiceMenuSource
    raw = json.loads(world_craft.DATA_PATH.read_text(encoding='utf-8'))
    npcs = {n['l1j_npc_id']: n for n in raw['npcs']}
    sources = {source.placement_key: source for source in setup.sources}
    enabled = set(setup.town.config.candidate_npc_ids)
    for key, npc in setup.town.data.placements.items():
        definition = npcs.get(npc.npc_id)
        if definition is None or npc.spawn['count'] <= 0:
            continue
        stem = definition['menu_stem']
        if stem is None:
            # Dio is already placed, but the retained client has no dio1 UML.
            # Keep its catalog associations without issuing an invented page.
            continue
        sources[key] = ServiceMenuSource(key, stem, MappingProxyType({stem: ()}), 'craft')
        enabled.add(npc.npc_id)
    town = setup.town
    # f39 -> InteractiveNPC+3C (C13F0), then HYPERTEXT consumer5CD1AE
    # -> UMLSubsystem+3C -> craft_output NPC catalog lookupA464A3.
    # Only these source-mapped crafting actors contribute this proven field.
    def appearance_wrapper(base):
        def appearance(uid):
            current = base(uid)
            npc = town.npc_for(uid)
            definition = None if npc is None else npcs.get(npc.npc_id)
            if current is None or definition is None:
                return current
            return replace(current, wire_f39=definition['npc_template_id'],
                           sprite_id=current.sprite_id or definition['sprite_id'])
        return appearance
    self._world_craft_appearance = self.world.runtime_extensions.wrap(
        'craft', town, 'appearance', appearance_wrapper)
    town.register(replace(town.config, candidate_npc_ids=frozenset(enabled)))
    return replace(setup, sources=tuple(sources.values()))


def _world_craft_runtime_stopped(self):
    handle = getattr(self, '_world_craft_appearance', None)
    if handle is not None:
        handle.close()


def _world_craft_request(self, host, request):
    """Client-local list selection is carried by the real native recipe ID."""
    menu, interaction = host.state.menu, host.state.interaction
    need(menu is not None and interaction is not None
         and request.target_uid == menu.fields[1] & 0xffffffff,
         'CRAFT_CURRENT_MENU_TARGET_REQUIRED')
    listing = self._world_craft_list(host, interaction, menu)
    native = self._world_craft_native.get((interaction.npc.npc_id, request.recipe_id))
    need(native is not None, 'CRAFT_NATIVE_RECIPE_REQUIRED')
    index = next((i for i, r in enumerate(listing.recipes) if r.id == native['id']), None)
    need(index is not None, 'CRAFT_NPC_RECIPE_REQUIRED')
    expected = tuple((int(row['fields']['3']), int(row['fields']['1']),
                      int(row['fields']['2']) * request.count,
                      int(row['fields']['4']), int(row['fields']['5']))
                     for row in native['native_catalog']['inputs'])
    need(len(request.inputs) == len(expected)
         and len({row[0] for row in request.inputs}) == len(request.inputs)
         and sorted(request.inputs) == sorted(expected), 'CRAFT_CURRENT_INPUTS_REQUIRED')
    selection = self._world_craft_select(host, listing, index)
    return self._world_craft_make(host, selection, request.count, keep_menu=True)


async def _world_craft_frame(self, writer, row, game, frame, operation_lock):
    from tools.local_original_session.world_handlers import HostContext
    if not self._world_bound(writer) or self._world_ready(writer, game) is None:
        return False
    host = HostContext(self.broker, writer, row, game, operation_lock)
    try:
        request = world_craft.decode_request(frame.payload)
        success = world_craft.acknowledgement_frame(success=True)
        await self.world.runtime.dispatch_now(self._world_craft_request, host, request)
        host.send_frame(success)
    except ValueError as error:
        if host.commit_attempted:
            raise
        self._world_handler_errors = (self._world_handler_errors + [str(error)[:96]])[-8:]
        host.send_frame(world_craft.acknowledgement_frame(success=False))
    await self._world_send(writer, row, tuple(host.frames), operation_lock)
    return True


def _world_craft_list(self, host, interaction, menu):
    """Detach a server recipe listing from an already delivered real NPC menu."""
    host._owned()
    need(host.current_source(menu.source) and menu.source.delivered
         and host.state.interaction is not None
         and host.state.interaction.ref == interaction.ref and host.state.menu is menu,
         'CRAFT_CURRENT_DRAINED_MENU_REQUIRED')
    native_id = self._world_craft_npcs.get(interaction.npc.npc_id)
    need(native_id is not None, 'CRAFT_NPC_NOT_SUPPORTED')
    recipes = tuple(r for r in self._world_craft_recipes if r.npc_template_id == native_id)
    need(recipes, 'CRAFT_NPC_RECIPES_REQUIRED')
    return CraftListing(menu.source, interaction.ref, interaction.npc.npc_id,
                        recipes, self.inventory_frame)


def _world_craft_select(self, host, listing, index):
    """Internal reference selection; index is never declared a native wire key."""
    host._owned()
    need(type(listing) is CraftListing and host.current_source(listing.source)
         and listing.source.delivered and host.state.menu is not None
         and host.state.menu.source is listing.source,
         'CRAFT_CURRENT_LISTING_REQUIRED')
    need(type(index) is int and 0 <= index < len(listing.recipes),
         'CRAFT_LISTED_RECIPE_REQUIRED')
    return CraftSelection(listing, listing.recipes[index])


def _world_craft_make(self, host, selection, count, *, keep_menu=False):
    """Consume materials and grant the result in the existing single kit CAS."""
    from tools.local_original_session import inventory
    from tools.local_original_session.world_handlers import _interaction
    host._owned()
    need(type(selection) is CraftSelection, 'CRAFT_SELECTED_RECIPE_REQUIRED')
    listing, recipe = selection.listing, selection.recipe
    need(host.current_source(listing.source) and listing.source.delivered
         and host.state.menu is not None and host.state.menu.source is listing.source
         and host.state.interaction is not None and host.state.interaction.ref == listing.ref
         and self.world.entities.resolve(listing.ref) is not None
         and recipe in listing.recipes and recipe in self._world_craft_recipes,
         'CRAFT_CURRENT_SELECTION_REQUIRED')
    interaction = _interaction(host, listing.ref)
    need(interaction.npc.npc_id == listing.npc_id
         and self._world_craft_npcs.get(listing.npc_id) == recipe.npc_template_id,
         'CRAFT_SAME_NPC_REQUIRED')
    need(self.inventory_frame is listing.inventory, 'CRAFT_CURRENT_INVENTORY_REQUIRED')
    need(self._inventory_kit_policy == inventory.KIT_POLICY, 'CRAFT_KIT_INVENTORY_REQUIRED')
    state = self.world.combat.pcs[host.pc_uid]
    need(not state.dead and state.hp > 0, 'CRAFT_LIVING_PC_REQUIRED')
    # Reuse the core's established plain/equipped policy rather than reading
    # another optional feature's equipment/quest/pet private state.
    snapshot = host.store.snapshot(host.pc_uid, host.now())
    excluded = tuple(item.uid for item in snapshot.items
                     if item.equipped or item.enchant_level or item.l1j_bless >= 128)
    allocate_uid = (None if host.bindings.allocate_uid is None else
                    lambda: host.bindings.allocate_uid(host))
    plan = world_craft.calculate_craft(self.inventory_frame, recipe, count,
        host.bindings.item_policies, excluded_uids=excluded, allocate_uid=allocate_uid,
        max_weight=snapshot.inventory.max_weight)
    older = tuple(self.world.drain(host.pc_uid))
    # An uncertain CAS cannot replay the selected paid action. Existing failed
    # save/partial preservation propagates to the original request owner.
    host.commit_attempted = True
    saved = False
    try:
        need(self._world_replace_kit(host.pc_uid, plan.before, plan.after, append=True) is True,
             'CRAFT_PERSISTED_CHANGE_REQUIRED')
        saved = True
    finally:
        if not saved or not keep_menu:
            listing.source.retired = True
            host.state.clear()
    self.inventory_frame = plan.after
    self.run_sync_hooks('inventory_changed', host.writer, host.row)
    for frame in (*older, *plan.frames):
        host.send_frame(frame)
    self._world_craft_results = (self._world_craft_results + [dict(
        uid=host.pc_uid, npc_id=listing.npc_id, recipe_id=recipe.id, count=count)])[-16:]
    return plan


def _world_craft_provider(self):
    return CraftProvider(self._world_craft_list, self._world_craft_select,
                         self._world_craft_make)


def _world_craft_report(self, result):
    result['craft_results'] = list(self._world_craft_results)
    result['craft_native_contract'] = 'STATIC_REQUEST5_ACK6; NATIVE_UI_AND_EMPTY_REFUSAL_ACK_UNOBSERVED'


METHODS = (_world_craft_initialize, _world_craft_town_setup, _world_craft_request, _world_craft_frame,
           _world_craft_list, _world_craft_select,
           _world_craft_make, _world_craft_provider, _world_craft_report,
           _world_craft_runtime_stopped)
HOOKS = {'initialize': ('_world_craft_initialize',),
         'town_setup': ('_world_craft_town_setup',),
         'runtime_stopped': ('_world_craft_runtime_stopped',),
         'craft_provider': ('_world_craft_provider',), 'report': ('_world_craft_report',)}
HOOK_PRIORITY = {'initialize': 60, 'town_setup': 40}
NONCRITICAL_HOOKS = ('report',)
SAVE_BOUNDARIES = {'_world_craft_make': True}
FRAMES = {world_craft.MAKE_REQUEST: ('_world_craft_frame',)}
OUTGOING_OPCODES = (world_craft.MAKE_ACK,)
