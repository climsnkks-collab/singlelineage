"""World feature: town. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_original_session.world_bridge import need


def _world_service_action(self, ctx, interaction, menu, fields, now):
    """Current/drained native menu -> existing inventory/position owners."""
    from tools.local_original_session import inventory, world_town_services
    from tools.local_original_session.world_handlers import Dialogue
    from tools.local_original_session.world_maps import MapDestination
    owner, uid = menu.source.owner, ctx.pc_uid
    action, stem = fields[2].decode('utf-8'), menu.fields[2].decode('utf-8')
    need(action in owner.pages.get(stem, ()), 'TOWN_SERVICE_ACTION_NOT_LISTED')
    if self._world_quest_action(ctx, interaction, menu, fields, now):
        return
    # run403 proves the four native inputs, not the fee/number-panel consumer,
    # key ownership, refund, destination or recovery contract. The separate
    # explicit LOCAL instant-rest calculator must not consume native room.
    need(interaction.npc.npc_id not in self._world_services.inn_ids,
         'TOWN_SERVICE_NOT_READY_INN_' + action.upper())
    ctx.state.window = None
    if stem == 'storage':
        self._world_warehouse_open(ctx, interaction, action)
        return
    if interaction.npc.npc_id == 50015 and stem == 'lucas1' and action == 'teleportURL':
        next_menu = Dialogue({1: fields[1], 2: b'lucas2'}, menu.source)
        ctx.send_frame(ctx.wire.dialogue_frame(next_menu.fields))
        menu.source.delivered = False
        ctx.pending.append(menu.source)
        ctx.state.menu = next_menu
        return
    state = self._world.combat.pcs[uid]
    need(not state.dead and state.hp > 0, 'TOWN_SERVICE_LIVING_PC_REQUIRED')
    items = inventory.validate_kit_frame(self.inventory_frame)
    coins = [r for r in items if r.template_bits == 7]
    need(len(coins) <= 1, 'UNIQUE_ADENA_STACK_REQUIRED')
    adena = dict(coins[0].raw_fields)[4] if coins else 0
    # Native literal differs from L1J XML's 'teleport ' prefix.
    route = 'teleport ' + action
    trip = self._world_services.teleports.get((interaction.npc.npc_id, route))
    need(trip is not None, 'TOWN_SERVICE_NOT_READY_DESTINATION')
    destination = MapDestination(trip.map_id, trip.x, trip.y, trip.heading)
    position = self.realm.service(ctx.writer).snapshot()
    need(destination.map_id == position.map_id or self._world_map_exp == 2,
         'TOWN_SERVICE_NOT_READY_ENABLE_MAPEXP_2')
    need(self.realm.serves_map(destination.map_id)
         and self._world.terrain.can_stand(destination.map_id, destination.x, destination.y) is True,
         'TOWN_SERVICE_NOT_READY_DESTINATION_DATA')
    proposal = world_town_services.calculate_teleport(self._world_services,
        interaction.npc.npc_id, route, adena=adena, level=state.profile.level)
    for frame in self._world.drain(uid):
        ctx.send_frame(frame)  # older HP/state must precede paid relocation
    if proposal.cost:
        ctx.commit_attempted = True
        ctx.send_frame(self._world_consume_kit(ctx.writer, coins[0].identifier, proposal.cost))
    for frame in self._world_relocate_locked(ctx.writer, ctx.row, ctx.game, destination,
                                             context=ctx, same_map_correction=True):
        ctx.send_frame(frame)
    ctx.state.clear()  # successful service cannot replay the paid menu


def _world_warehouse_open(self, ctx, interaction, action):
    from tools.local_original_session import inventory, world_warehouse
    need(self._world_warehouse_exp and action in ('deposit', 'retrieve'),
         'WAREHOUSE_NOT_READY_ENABLE_WAREHOUSEEXP')
    state = self._world.combat.pcs[ctx.pc_uid]
    need(state.profile.level >= self._world_services.minimum_level, 'WAREHOUSE_LEVEL_REQUIRED')
    direction = 'deposit' if action == 'deposit' else 'withdraw'
    frame = self._world_warehouse_store.restore(ctx.pc_uid)
    items = () if frame is None else inventory.validate_kit_frame(frame)
    current = inventory.validate_kit_frame(self.inventory_frame)
    context = ctx.row.get('_world_warehouse_context', 0) + 1
    need(context < 1 << 32, 'WAREHOUSE_CONTEXT_EXHAUSTED')
    ctx.row['_world_warehouse_context'] = context
    source = ctx._source(interaction, 'warehouse', self.inventory_frame)
    kind, count1, count3, list2, list4, list5, list6 = self._world_warehouse_exp
    rows = ({item.identifier: item.identifier for item in current} if direction == 'deposit'
            else {index: item.identifier for index, item in enumerate(items, 1)})
    if direction == 'deposit':
        wire = world_warehouse.count_frame(context, kind=kind, f1=count1, f3=count3)
    else:
        by_uid = {item.identifier: item for item in items}
        wire = world_warehouse.list_frame(context,
            tuple((key, by_uid[uid]) for key, uid in rows.items()), kind=kind,
            f2=list2, f4=list4, f5=list5, f6=list6)
    ctx.row['_world_warehouse_window'] = dict(source=source, context=context,
        direction=direction, mode=world_warehouse.request_mode(direction, kind), rows=rows,
        warehouse=frame, ref=interaction.ref)
    ctx.send_frame(wire)


def _world_warehouse_trade(self, ctx, payload, now):
    from dataclasses import replace
    from tools.local_original_session import (inventory, inventory_update, item_transfer_protocol,
        world_handlers, world_town_services, world_warehouse)
    window = ctx.row.get('_world_warehouse_window')
    if window is None:
        return False
    request = world_warehouse.decode_request(payload)
    need(self._world_warehouse_exp and ctx.current_source(window['source'])
         and window['source'].delivered, 'WAREHOUSE_DRAINED_CURRENT_LIST_REQUIRED')
    world_handlers._interaction(ctx, window['ref'])
    before = self.inventory_frame
    warehouse_before = self._world_warehouse_store.restore(ctx.pc_uid)
    need(window['source'].inventory is before and window['warehouse'] == warehouse_before
         and request.context_u32 == window['context'] and request.mode == window['mode'],
         'WAREHOUSE_CURRENT_CONTEXT_REQUIRED')
    need(all(row.row_key_u32 in window['rows'] for row in request.items), 'WAREHOUSE_UNKNOWN_ROW')
    selections = tuple((window['rows'][row.row_key_u32], row.quantity) for row in request.items)
    player_items = inventory.validate_kit_frame(before)
    bank_items = () if warehouse_before is None else inventory.validate_kit_frame(warehouse_before)
    equipment = (None if self._item_equipment_effect is None else
                 self._item_equipment_effect.store.restore(ctx.pc_uid, before))
    worn = set() if equipment is None else {equipment.weapon_uid, *(uid for _, uid in equipment.slots)} - {0}

    def service_rows(items):
        result = []
        for item in items:
            definition = self._world.data.items.get(item.template_bits)
            policy = ctx.bindings.item_policies.get(item.template_bits)
            need(definition is not None and policy is not None, 'WAREHOUSE_ITEM_POLICY_REQUIRED')
            fields = dict(item.raw_fields)
            variant = inventory.build_kit_frame([{**fields, 1: 1, 4: 1}])
            # Explicit LOCAL storable M1 definitions, no inferred raw trade flags.
            allowed = definition.kind in ('weapon', 'armor', 'potion', 'scroll', 'ammo', 'currency')
            result.append(world_town_services.ServiceItem(item.identifier, item.template_bits,
                fields[4], definition.stackable, variant, policy.raw_weight,
                allowed, item.identifier in worn))
        return tuple(result)

    state = self._world.combat.pcs[ctx.pc_uid]
    player, bank = service_rows(player_items), service_rows(bank_items)
    if window['direction'] == 'deposit':
        proposal = world_town_services.calculate_deposit(self._world_services, player, bank,
            selections, level=state.profile.level)
    else:
        calculated, _, _ = self._world_stats_for(self.realm.service(ctx.writer).snapshot(),
                                                level=state.profile.level)
        proposal = world_town_services.calculate_withdrawal(self._world_services, player, bank,
            selections, level=state.profile.level, max_weight=int(calculated.max_weight))
    player_rows = [dict(item.raw_fields) for item in player_items]
    bank_rows = [dict(item.raw_fields) for item in bank_items]
    source_rows, destination_rows = (player_rows, bank_rows) if proposal.direction == 'deposit' else (bank_rows, player_rows)
    next_uid = max((row[1] for row in (*player_rows, *bank_rows)), default=65536) + 1
    slots = {}
    for line in proposal.transfers:
        source = next(row for row in source_rows if row[1] == line.item.uid)
        target = next((row for row in destination_rows if row[1] == line.destination_uid), None)
        if target is None and line.new_slot in slots:
            target = slots[line.new_slot]
        if target is None:
            # Moving a complete instance preserves UID. Only a split allocates.
            identifier = source[1] if source[4] == line.count else next_uid
            if identifier == next_uid:
                next_uid += 1
            need(0 < identifier < 1 << 32, 'WAREHOUSE_UID_CAPACITY')
            target = {**source, 1: identifier, 4: 0}
            destination_rows.append(target)
            slots[line.new_slot] = target
        target[4] += line.count
        source[4] -= line.count
    for coin_uid, amount in proposal.fee_debits:
        coin = next(row for row in player_rows if row[1] == coin_uid)
        coin[4] -= amount
    player_rows = [row for row in player_rows if row[4] > 0]
    bank_rows = [row for row in bank_rows if row[4] > 0]
    need(player_rows, 'WAREHOUSE_EMPTY_PLAYER_INVENTORY_UNSUPPORTED')
    after = inventory.build_kit_frame(player_rows)
    warehouse_after = inventory.build_kit_frame(bank_rows) if bank_rows else None
    equipment_change = {}
    equipment_after = equipment
    if equipment is not None and not any(row[1] == equipment.item_uid for row in player_rows):
        equipment_after = replace(equipment, item_uid=player_rows[0][1], template=player_rows[0][2],
                                  revision=equipment.revision + 1)
        equipment_change = dict(equipment_store=self._item_equipment_effect.store,
            equipment_before=equipment, equipment_after=equipment_after)
    older = tuple(self._world.drain(ctx.pc_uid))
    ctx.row.pop('_world_warehouse_window', None)
    window['source'].retired = True  # Ambiguous persistence never permits replay.
    ctx.commit_attempted = True
    self._world_warehouse_store.commit(ctx.pc_uid, before, after, warehouse_before,
                                      warehouse_after, **equipment_change)
    self.inventory_frame = after
    if equipment_after != equipment and self._item_equipment_effect._selection is not None:
        self._item_equipment_effect._selection['state'] = equipment_after
    old_rows = {item.identifier: dict(item.raw_fields) for item in player_items}
    new_rows = {row[1]: row for row in player_rows}
    frames = list(older)
    for identifier, previous in old_rows.items():
        current = new_rows.get(identifier)
        if current is None:
            frames.append(item_transfer_protocol._remove_frame(item_transfer_protocol.RemoveInventory(identifier)))
        elif current[4] != previous[4]:
            frames.append(inventory_update._encode(inventory_update._values({1: identifier, 4: current[4]})))
    frames.extend(inventory.build_add(row) for row in player_rows if row[1] not in old_rows)
    for frame in frames:
        ctx.send_frame(frame)
    ctx.state.clear()
    self._world_warehouse_results = (self._world_warehouse_results + [dict(
        uid=ctx.pc_uid, direction=proposal.direction, fee=proposal.fee,
        player_slots=len(player_rows), warehouse_slots=len(bank_rows))])[-16:]
    return True


METHODS = (
    _world_service_action,
    _world_warehouse_open,
    _world_warehouse_trade,
)


def setup_warehouse(self):
    import os
    self._world_warehouse_exp = os.environ.get('SL_EXPERIMENT_WAREHOUSE', '').strip()
    if self._world_warehouse_exp == '0':
        self._world_warehouse_exp = ''
    if self._world_warehouse_exp:
        parts = (1, 0, 150, 0, 0, 30, 150) if self._world_warehouse_exp == '1' else tuple(
            int(value) for value in self._world_warehouse_exp.split(','))
        need(len(parts) == 7 and parts[0] in (1, 2, 3)
             and all(0 <= value < 1 << 32 for value in parts), 'WAREHOUSE_EXPERIMENT_VALUES')
        self._world_warehouse_exp = parts
    self._world_enchant_results, self._world_warehouse_results = [], []


def setup_town(self, world_handler_sources):
    import os
    from tools.local_original_session import world_town, world_town_services, world_handlers
    candidates = os.environ.get('SL_WORLD_TOWN_CANDIDATES', '')
    town_data = world_town.load_town()
    gludin = os.environ.get('SL_EXPERIMENT_MAP', '0') == '2'
    if gludin:
        town_data = world_town.with_gludin_town(town_data)
        # Startup, before registration/requests; never wait for map4 IO in a
        # click, movement, spawn or return handler.
        self._world.terrain.bounds(4)
    town_config = world_town.TownConfig(enable_candidates=candidates == 'all',
        candidate_npc_ids=world_town.confirmed_npc_ids(town_data) | frozenset(
            int(value.strip()) for value in candidates.split(',')
            if value.strip() and candidates != 'all'))
    self._world.town = world_town.TownNpcs(self._world.entities, town_data, town_config,
        passable=(lambda m, x, y: m != 4 or self._world.terrain.can_stand(m, x, y)) if gludin else None)
    self._world_services = world_town_services.load_town_services(
        experimental=os.environ.get('SL_EXPERIMENT_MAP', '0') in ('1', '2', '3'))
    self._world_inn_price = self._world_services.inn_price
    service_menus = world_town_services.load_service_menus(self._world.town,
        warehouse_experiment=bool(self._world_warehouse_exp))
    from tools.local_original_session.world_feature_quest import setup_quests
    quest_menus = setup_quests(self, self._world.town)
    from dataclasses import replace
    warehouse_keys = frozenset(source.placement_key for source in service_menus
                               if source.stem == 'storage')
    if warehouse_keys:
        town_config = replace(town_config,
            candidate_npc_ids=town_config.candidate_npc_ids | frozenset(k[0] for k in warehouse_keys),
            shop_sprite_candidates=town_config.shop_sprite_candidates | warehouse_keys)
    # Unmapped service actors must not become invisible default blockers.
    # Existing explicit town candidates or MapExp may enable the backend
    # experiment; neither supplies an invented Classic sprite.
    if os.environ.get('SL_EXPERIMENT_MAP', '0') in ('1', '2', '3'):
        town_config = replace(town_config, candidate_npc_ids=town_config.candidate_npc_ids
                              | frozenset(source.placement_key[0] for source in service_menus))
    from tools.local_original_session import world_shop_menu
    self._world_shop_experiment = world_shop_menu.parse_experiment(os.environ.get('SL_EXPERIMENT_SHOP'))
    menu_sources = world_shop_menu.load_menu_sources(self._world.town,
        experiment=self._world_shop_experiment)
    if self._world_shop_experiment is not None:
        from dataclasses import replace
        town_config = replace(town_config,
            candidate_npc_ids=town_config.candidate_npc_ids | frozenset(
                source.placement_key[0] for source in menu_sources),
            shop_sprite_candidates=town_config.shop_sprite_candidates | frozenset(
                source.placement_key for source in menu_sources))
    self._world.town.register(town_config)
    # Explicit externally prepared sources retain priority over JSON menus.
    supplied = {source.placement_key for source in world_handler_sources}
    self._world_handler_bindings = world_handlers.prepare_host_bindings(
        self._world.town, sources=tuple(world_handler_sources) + tuple(
            source for source in (*menu_sources, *service_menus, *quest_menus)
            if source.placement_key not in supplied))
    # Quest-owned rows participate in the same inventory snapshot even at an
    # unrelated shop. Preserve existing item policies/offers and their owners.
    from types import MappingProxyType
    policies = dict(self._world_handler_bindings.item_policies)
    for policy in self._world_quest_item_policies:
        policies.setdefault(policy.template_id, policy)
    self._world_handler_bindings = replace(self._world_handler_bindings,
                                           item_policies=MappingProxyType(policies))
