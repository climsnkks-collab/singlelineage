"""World feature: town. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_original_session.world_bridge import need


def _shop_sale_item(ctx, row):
    """Missing equipment records have no worn slots under the LOCAL shop policy.

    Keep the existing producer's plain/variant and recorded wearing decisions.
    Store read failures still propagate; only a genuinely absent row is empty.
    """
    from dataclasses import replace
    from tools.local_original_session import world_handlers
    item = world_handlers._default_sale_item(ctx, row)
    if item.equipped:
        effect = getattr(ctx.broker, '_item_equipment_effect', None)
        state = (None if effect is None else
                 effect.store.restore(ctx.pc_uid, ctx.broker._inventory_current_frame))
        if state is None:
            item = replace(item, equipped=False)
    return item


def _world_service_action(self, ctx, interaction, menu, fields, now):
    """Current/drained native menu -> existing inventory/position owners."""
    from tools.local_original_session import inventory, world_town_services
    from tools.local_original_session.world_handlers import Dialogue
    from tools.local_original_session.world_maps import MapDestination
    owner, uid = menu.source.owner, ctx.pc_uid
    action, stem = fields[2].decode('utf-8'), menu.fields[2].decode('utf-8')
    if interaction.npc.npc_id in self._world_inn_definitions:
        return self._world_inn_action(ctx, interaction, menu, action, now)
    ctx.state.window = None
    if stem == 'storage' or owner.service_kind == 'warehouse':
        self._world_warehouse_open(ctx, interaction, action)
        return True
    if interaction.npc.npc_id == 50015 and stem == 'lucas1' and action == 'teleportURL':
        next_menu = Dialogue({1: fields[1], 2: b'lucas2'}, menu.source)
        ctx.send_frame(ctx.wire.dialogue_frame(next_menu.fields))
        menu.source.delivered = False
        ctx.pending.append(menu.source)
        ctx.state.menu = next_menu
        return True
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
    return True


def _world_warehouse_open(self, ctx, interaction, action):
    from tools.local_original_session import inventory, world_warehouse
    need(self._world_warehouse_exp and action in ('deposit', 'retrieve'),
         'WAREHOUSE_NOT_READY_ENABLE_WAREHOUSEEXP')
    state = self._world.combat.pcs[ctx.pc_uid]
    need(state.profile.level >= self._world_services.minimum_level, 'WAREHOUSE_LEVEL_REQUIRED')
    direction = 'deposit' if action == 'deposit' else 'withdraw'
    frame = self.inventory_transactions.restore_warehouse(ctx.pc_uid)
    items = () if frame is None else inventory.validate_kit_frame(frame)
    current = inventory.validate_kit_frame(self.inventory_frame)
    context = ctx.row.get('_world_warehouse_context', 0) + 1
    need(context < 1 << 32, 'WAREHOUSE_CONTEXT_EXHAUSTED')
    ctx.row['_world_warehouse_context'] = context
    source = ctx._source(interaction, 'warehouse', self.inventory_frame)
    kind, _, count3, _, list4, list5, list6 = self._world_warehouse_exp
    # Both native count/limit displays use the saved occupied row count.
    # Item quantity and the number of carried inventory rows are unrelated.
    occupied = len(items)
    rows = ({item.identifier: item.identifier for item in current} if direction == 'deposit'
            # Native Count_Up/Down (B1C050/B1BE30 -> B1BD90) index the row widget
            # vector window+100 by this key, so keys are 0-based row positions.
            else {index: item.identifier for index, item in enumerate(items)})
    if direction == 'deposit':
        wire = world_warehouse.count_frame(context, kind=kind, f1=occupied, f3=count3)
    else:
        from tools.local_original_session.world_visibility import item_names
        by_uid = {item.identifier: item for item in items}
        wire = world_warehouse.list_frame(context,
            tuple((key, by_uid[uid]) for key, uid in rows.items()), kind=kind,
            f2=occupied, f4=list4, f5=list5, f6=list6,
            item_defs=self._world.data.items, names=item_names())
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
    warehouse_before = self.inventory_transactions.restore_warehouse(ctx.pc_uid)
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
            from tools.local_original_session.inventory_store import stack_fields
            variant = inventory.build_kit_frame([{**stack_fields(fields), 1: 1, 4: 1}])
            # Explicit LOCAL storable M1 definitions, no inferred raw trade flags.
            allowed = definition.kind in ('weapon', 'armor', 'potion', 'scroll', 'ammo', 'currency', 'misc')
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
    self.inventory_transactions.commit_warehouse(ctx.pc_uid, before, after, warehouse_before,
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
    self._world_warehouse_exp = os.environ.get('SL_EXPERIMENT_WAREHOUSE', '1').strip()
    if self._world_warehouse_exp.lower() in ('0', 'off'):
        self._world_warehouse_exp = ''
    elif not self._world_warehouse_exp:
        self._world_warehouse_exp = '1'
    if self._world_warehouse_exp:
        # kind1 is our LOCAL personal scope, not a recovered official enum name.
        # Count placeholders are replaced with occupied saved rows when opened.
        parts = (1, 0, 150, 0, 7, 30, 150) if self._world_warehouse_exp == '1' else tuple(
            int(value) for value in self._world_warehouse_exp.split(','))
        need(len(parts) == 7 and parts[0] in (1, 2, 3)
             and all(0 <= value < 1 << 32 for value in parts), 'WAREHOUSE_EXPERIMENT_VALUES')
        self._world_warehouse_exp = parts
    self._world_warehouse_results = []


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
    # Preserve accepted fixed map0 services; random range candidates use the
    # actual terrain on map0 too, before M5 adopts these issued registrations.
    town = world_town.TownNpcs(self._world.entities, town_data, town_config,
        passable=(lambda m, x, y: m != 4 or self._world.terrain.can_stand(m, x, y)) if gludin else None,
        random_passable=self._world.terrain.can_stand if gludin else None)
    self._world_services = world_town_services.load_town_services(
        experimental=os.environ.get('SL_EXPERIMENT_MAP', '0') in ('1', '2', '3'))
    self._world_inn_price = self._world_services.inn_price
    service_menus = world_town_services.load_service_menus(town,
        warehouse_experiment=bool(self._world_warehouse_exp))
    extra_menus = tuple(source for group in self.collect_sync_hooks('menu_sources', town)
                        for source in group)
    from dataclasses import replace
    warehouse_keys = frozenset(source.placement_key for source in service_menus
                               if source.stem == 'storage')
    inn_keys = frozenset(source.placement_key for source in service_menus if source.stem == 'inn')
    # Explicit LOCAL catalog visuals, following the existing selected service
    # sprite path; numeric sprite correspondence does not establish NPC identity.
    town_config = replace(town_config,
        candidate_npc_ids=town_config.candidate_npc_ids | frozenset(k[0] for k in inn_keys),
        shop_sprite_candidates=town_config.shop_sprite_candidates | inn_keys)
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
    menu_sources = world_shop_menu.load_menu_sources(town,
        experiment=self._world_shop_experiment)
    if self._world_shop_experiment is not None:
        from dataclasses import replace
        town_config = replace(town_config,
            candidate_npc_ids=town_config.candidate_npc_ids | frozenset(
                source.placement_key[0] for source in menu_sources),
            shop_sprite_candidates=town_config.shop_sprite_candidates | frozenset(
                source.placement_key for source in menu_sources))
    town.register(town_config)
    # Explicit externally prepared sources retain priority over JSON menus.
    supplied = {source.placement_key for source in world_handler_sources}
    sources = tuple(world_handler_sources) + tuple(
        source for source in (*menu_sources, *service_menus, *extra_menus)
        if source.placement_key not in supplied)
    self.configure_town(town, sources)
    configured = self.fold_sync_hooks('town_setup', world_town.TownSetup(
        town, self._world_services, sources, self._world_shop_experiment))
    self._world_services = configured.services
    world_town.attach_view(self.world, configured.town)
    self.configure_town(configured.town, configured.sources, refresh_policies=False)
    bindings = self._world_handler_bindings
    if bindings.sale_item is world_handlers._default_sale_item:
        self._world_handler_bindings = replace(bindings, sale_item=_shop_sale_item)
    for policies in self.collect_sync_hooks('item_policies'):
        self.add_item_policies(policies)


def _world_town_initialize(self):
    setup_warehouse(self)
    setup_town(self, self.world_options['world_handler_sources'])
    setup_inn(self)


def setup_inn(self):
    """Startup-only rental store/wrapper wiring; also reused by kit fixtures."""
    from tools.local_original_session import world_inn
    from pathlib import Path
    root = Path(__file__).resolve().parent / 'data'
    self._world_inn_definitions = {}
    for name in ('m2', 'm4', 'm5'):
        self._world_inn_definitions.update(world_inn.definitions(root / name))
    self._world_inn_definitions = {npc_id: definition for npc_id, definition
        in self._world_inn_definitions.items() if any(npc.npc_id == npc_id
            for npc in self.world.town.data.placements.values())}
    self._world_inn_store = (world_inn.InnStore(self.inventory_transactions,
                                             replace_kit=self._world_inn_replace_kit)
                             if self.inventory_transactions is not None else None)
    self._world_inn_results = []
    self._world_inn_timers = {}
    self._world_inn_regen = (self.world.runtime_extensions.wrap('town-inn', self.world.combat,
        'regen_tick', world_inn.regen_wrapper(self)) if self._world_inn_store is not None else None)


def _world_inn_replace_kit(self, uid, before, after, *, append=False):
    from tools.local_original_session import inventory
    removed = ({item.identifier for item in inventory.validate_kit_frame(before)}
               - {item.identifier for item in inventory.validate_kit_frame(after)})
    if removed:
        # The core owner moves a removed equipment anchor and uses the existing
        # inventory/warehouse/equipment transaction. Its startup recovery runs
        # before InnStore's forward intent, so the same exact old/new pair holds.
        return self._world_replace_kit(uid, before, after, append=append)
    return self.inventory_transactions.commit_inventory(uid, before, after, append=append)


def _world_inn_action(self, ctx, interaction, menu, action, now):
    from tools.local_original_session import inventory, world_inn
    import time
    need(self._world_inn_store is not None, 'INN_KIT_INVENTORY_REQUIRED')
    state = self.world.combat.pcs[ctx.pc_uid]
    need(not state.dead and state.hp > 0, 'INN_LIVING_PC_REQUIRED')
    definition = self._world_inn_definitions[interaction.npc.npc_id]
    rental = self._world_inn_store.rows.get(ctx.pc_uid)
    wall = time.time()
    if action == 'enter':
        need(rental is not None and rental['npc_id'] == definition.npc_id
             and wall < rental['expires_at'] and world_inn.key_owned(self.inventory_frame, rental),
             'INN_CURRENT_OWNED_RENTAL_REQUIRED')
        # The supplied maps do not serve an inn interior. Keep the rental/key;
        # only the explicitly configured nearby rest policy is available.
        raise ValueError('INN_INTERIOR_MAP_UNSUPPORTED_RENTAL_REST_ONLY')
    need(action in ('room', 'hall', 'return'), 'INN_ACTION_NOT_SUPPORTED')
    before = self.inventory_frame
    if action in ('room', 'hall'):
        need(rental is None, 'INN_ACTIVE_RENTAL_EXISTS')
        items = inventory.validate_kit_frame(before)
        key_uid = (max(item.identifier for item in items) + 1 if ctx.bindings.allocate_uid is None
                   else ctx.bindings.allocate_uid(ctx))
        spawn = interaction.npc.spawn
        after, next_rental = world_inn.rent_plan(before, definition, uid=ctx.pc_uid,
            kind=action, key_uid=key_uid, prototype=self.starter_fields,
            placement=(interaction.npc.key[1], spawn['mapid'], spawn['locx'], spawn['locy']), wall=wall)
        amount = -definition.price
    else:
        need(rental is not None and rental['npc_id'] == definition.npc_id
             and rental['placement'][0] == interaction.npc.key[1], 'INN_SAME_INN_REQUIRED')
        allocate_uid = (None if ctx.bindings.allocate_uid is None else
                        lambda: ctx.bindings.allocate_uid(ctx))
        after, amount = world_inn.close_plan(before, rental, definition, refund=True,
            wall=wall, allocate_uid=allocate_uid, coin_fields=ctx.bindings.item_policies[7].grant_fields)
        next_rental = None
    older = tuple(self.world.drain(ctx.pc_uid))
    # A failed/ambiguous commit cannot replay the paid menu.
    menu.source.retired = True
    ctx.state.clear()
    ctx.commit_attempted = True
    self._world_inn_store.commit(ctx.pc_uid, before, after, next_rental)
    self.inventory_frame = after
    for frame in (*older, *world_inn.inventory_frames(before, after)):
        ctx.send_frame(frame)
    self._world_inn_results = (self._world_inn_results + [dict(uid=ctx.pc_uid,
        npc_id=definition.npc_id, action=action, adena_delta=amount,
        key_uid=(next_rental or rental)['key_uid'],
        expires_at=(next_rental or rental)['expires_at'])])[-16:]
    self._world_inn_schedule(ctx.writer, ctx.pc_uid)
    return True


def _world_inn_expire(self, writer, uid):
    from tools.local_original_session import world_inn
    import time
    rental = self._world_inn_store.rows.get(uid)
    if rental is None or time.time() < rental['expires_at'] or not self._world_bound(writer):
        return ()
    before = self.inventory_frame
    after, _ = world_inn.close_plan(before, rental, self._world_inn_definitions[rental['npc_id']])
    self._world_inn_store.commit(uid, before, after, None)
    self.inventory_frame = after
    return world_inn.inventory_frames(before, after)


def _world_inn_schedule(self, writer, uid):
    import time
    handle = self._world_inn_timers.pop(uid, None)
    if handle is not None:
        self.world.runtime.scheduler.cancel(handle)
    rental = self._world_inn_store.rows.get(uid)
    if rental is None:
        return
    def expire(now):
        self._world_inn_timers.pop(uid, None)
        frames = self._world_inn_expire(writer, uid)
        for frame in frames:
            self.world._queue(uid, frame)
        # Wall clock can move back; keep the absolute saved expiry authoritative.
        if uid in self._world_inn_store.rows and self._world_bound(writer):
            self._world_inn_schedule(writer, uid)
    at = self.world.runtime.clock() + max(0.0, rental['expires_at'] - time.time())
    self._world_inn_timers[uid] = self.world.runtime.scheduler.schedule(at, None, 'inn_expiry', expire)


async def _world_inn_after_enter(self, writer, row, game, operation_lock):
    if self._world_inn_store is None:
        return
    uid = self.realm.service(writer).snapshot().uid
    frames = await self.world.runtime.dispatch_now(self._world_inn_expire, writer, uid)
    if frames:
        await self._world_send(writer, row, frames, operation_lock)
    self._world_inn_schedule(writer, uid)


def _world_inn_before_leave(self, writer, uid):
    handle = self._world_inn_timers.pop(uid, None)
    if handle is not None:
        self.world.runtime.scheduler.cancel(handle)


def _world_inn_runtime_stopped(self):
    for handle in self._world_inn_timers.values():
        self.world.runtime.scheduler.cancel(handle)
    self._world_inn_timers.clear()
    if self._world_inn_regen is not None:
        self._world_inn_regen.close()


def _world_town_begin_click(self, host):
    host.row.pop('_world_warehouse_window', None)


def _world_town_inventory_changed(self, writer, row):
    row.pop('_world_warehouse_window', None)


def _world_town_warehouse_close(self, host, payload, now):
    from tools.local_original_session.world_warehouse import close_body
    close_body(payload)
    host.row.pop('_world_warehouse_window', None)
    host.begin_click()
    return True


def _world_town_report(self, result):
    town = self.world.town
    result.update(town_npcs=sum(1 for entity in self.world.entities
                              if town.npc_for(entity.uid) is not None),
        menu_sources=len(self._world_handler_bindings.sources),
        shop_experiment=self._world_shop_experiment is not None,
        warehouse_experiment=self._world_warehouse_exp,
        warehouse_results=list(self._world_warehouse_results),
        inn_results=list(self._world_inn_results),
        inn_rentals=list(self._world_inn_store.rows.values()) if self._world_inn_store else [])


METHODS += (_world_town_initialize, _world_town_begin_click,
            _world_town_inventory_changed, _world_town_warehouse_close, _world_town_report,
            _world_inn_action, _world_inn_replace_kit, _world_inn_expire, _world_inn_schedule,
            _world_inn_after_enter, _world_inn_before_leave, _world_inn_runtime_stopped)
HOOKS = {'initialize': ('_world_town_initialize',),
         'service_action': ('_world_service_action',),
         'warehouse_trade': ('_world_warehouse_trade',),
         'warehouse_close': ('_world_town_warehouse_close',),
         'begin_click': ('_world_town_begin_click',),
         'inventory_changed': ('_world_town_inventory_changed',),
         'report': ('_world_town_report',),
         'after_enter': ('_world_inn_after_enter',),
         'before_leave': ('_world_inn_before_leave',),
         'runtime_stopped': ('_world_inn_runtime_stopped',)}
NONCRITICAL_HOOKS = ('report',)
# Register through the existing feature send contract, including an unset env.
OUTGOING_OPCODES = (0x4ED2, 0x0971)
SAVE_BOUNDARIES = {'_world_warehouse_trade': True, '_world_inn_action': True}
