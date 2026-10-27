"""World feature: items. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_native_login_local_ack_hook import ack_enter_world as ack
from tools.local_original_session.world_bridge import need


async def _world_enchant_use(self, ctx, payload, now):
    """run393 targeted 0960 -> one saved LOCAL enchant -> generic projection."""
    from dataclasses import replace
    from tools.local_original_session import inventory, world_enchant, world_enchant_inventory
    from tools.local_original_session.world_status_frames import full_status_frame
    if self._inventory_kit_policy != inventory.KIT_POLICY:
        return False
    pb = ack.realm.pb
    with pb.parse_message(payload, limits=pb.WireLimits(max_body=4096, max_fields=2,
                                                       max_field_bytes=2048)) as parsed:
        if not (len(parsed.fields) == 2 and len(parsed.occurrences(1)) == len(parsed.occurrences(2)) == 1
                and parsed.occurrences(1)[0].wire_type == 0
                and parsed.occurrences(2)[0].wire_type == 2):
            return False
        scroll_uid = parsed.occurrences(1)[0].value
        params = bytes(parsed.occurrences(2)[0].value)
    before = self.inventory_frame
    items = inventory.validate_kit_frame(before)
    scroll = next((item for item in items if item.identifier == scroll_uid), None)
    if scroll is None or scroll.template_bits not in (25, 26):
        return False
    with pb.parse_message(params, limits=pb.WireLimits(max_body=2048, max_fields=5,
                                                      max_field_bytes=2048)) as parsed:
        expected = {1: 1, 3: 0, 15: 0, 16: 0}
        need(len(parsed.fields) == 5 and all(len(parsed.occurrences(n)) == 1 for n in (*expected, 2))
             and all(f.wire_type == 0 for f in parsed.fields)
             and all(parsed.occurrences(n)[0].value == value for n, value in expected.items()),
             'ENCHANT_TARGETED_PARAMS_REQUIRED')
        target_uid = parsed.occurrences(2)[0].value  # int64 varint, never ZigZag or truncated.
    target = next((item for item in items if item.identifier == target_uid), None)
    need(target is not None and target_uid != scroll_uid, 'ENCHANT_OWNED_TARGET_REQUIRED')
    definition = self._world.data.items.get(target.template_bits)
    need(definition is not None and definition.kind in ('weapon', 'armor'), 'ENCHANT_EQUIPMENT_REQUIRED')
    proposal = world_enchant.propose_enchant(
        world_enchant.EnchantScroll(scroll.template_bits, world_enchant_inventory.scroll_grade(scroll)),
        world_enchant.EnchantTarget(target.template_bits, definition.kind,
            world_enchant_inventory.enchant_level(target, definition)))
    need(proposal.accepted, 'ENCHANT_' + proposal.reason.upper())
    rng = self._world.combat.rng
    result = world_enchant.resolve_enchant(proposal,
        outcome_roll=rng.randint(1, 100), blessing_roll=rng.randint(1, 100))
    mutation = world_enchant_inventory.kit_mutation(items, scroll_uid, target_uid, result,
                                                    self._world.data.items)
    result_wire = world_enchant_inventory.result_frame(scroll_uid, target_uid, result,
        self._world_enchant_exp, scroll_template_id=scroll.template_bits)
    effect = self._item_equipment_effect
    equipment = None if effect is None else effect.store.restore(ctx.pc_uid, before)
    equipment_after, changes = equipment, ()
    if equipment is not None:
        removed = set(mutation.removed_uids)
        if equipment.weapon_uid in removed:
            changes += ((equipment.weapon_uid, self._world.data.items[target.template_bits].slot_key, False),)
        changes += tuple((member_uid, key, False) for key, member_uid in equipment.slots
                         if member_uid in removed)
        if changes or equipment.item_uid in removed:
            anchor = inventory.validate_kit_frame(mutation.frame)[0]
            equipment_after = replace(equipment,
                item_uid=anchor.identifier if equipment.item_uid in removed else equipment.item_uid,
                template=anchor.template_bits if equipment.item_uid in removed else equipment.template,
                weapon_uid=0 if equipment.weapon_uid in removed else equipment.weapon_uid,
                slots=tuple((key, member_uid) for key, member_uid in equipment.slots if member_uid not in removed),
                revision=equipment.revision + 1)
    warehouse = self._world_warehouse_store.restore(ctx.pc_uid)
    ctx.commit_attempted = True
    equipment_change = (dict(equipment_store=effect.store,
        equipment_before=equipment, equipment_after=equipment_after)
        if equipment_after != equipment else {})
    self._world_warehouse_store.commit(ctx.pc_uid, before, mutation.frame, warehouse, warehouse,
                                      **equipment_change)
    self.inventory_frame = mutation.frame
    ctx.row.pop('_world_warehouse_window', None)
    if equipment_after != equipment:
        if changes:
            from tools.local_original_session.item_equipment_effect import _receipt
            receipt = _receipt('INITIAL_SYNC')
            await effect._notify_kit(effect._context(ctx.writer), equipment_after, receipt, changes)
        if effect._selection is not None:
            effect._selection['state'] = equipment_after
    self._world_recalculate_uid(ctx.pc_uid)
    for frame in (*self._world.drain(ctx.pc_uid), *mutation.frames,
                  *((result_wire,) if result_wire is not None else ()),
                  full_status_frame(self._world.combat.pcs[ctx.pc_uid].status_fields)):
        ctx.send_frame(frame)
    if changes:
        await self._world_refresh_stance_locked(ctx.writer, ctx.row)
    self._world_enchant_results = (self._world_enchant_results + [dict(
        uid=ctx.pc_uid, scroll_uid=scroll_uid, target_uid=target_uid,
        status=result.status, before=result.level_before, after=result.level_after,
        result_packet=result_wire is not None)])[-16:]
    return True


def _world_polymorph_frame(self, uid, sprite):
    """run390 SC_POLYMORPH_NOTI: only required signed int32 f1/2/3."""
    from tools.local_original_session import attack
    signed_uid = uid if uid < (1 << 31) else uid - (1 << 32)
    body = b''.join(attack._field(n, value) for n, value in
                    ((1, signed_uid), (2, sprite), (3, self._world_stance_for(uid))))
    return (len(body) + 6).to_bytes(2, 'little') + b'\x5c\x4e' + body + b'\0\0'


def _world_expire_polymorph(self, uid, now):
    from tools.local_original_session import world_polymorph
    state = self._world_polymorphs.get(uid)
    if state is None:
        return
    result = world_polymorph.expire_polymorph(state, now_ms=int(now * 1000))
    if result.reason != 'expired':
        return
    wire = self._world_polymorph_frame(uid, result.state.current_sprite_id)
    self._world_polymorphs.pop(uid, None)
    handle = self._world_poly_timers.pop(uid, None)
    if handle is not None:
        self._world.runtime.scheduler.cancel(handle)
    self._world._queue(uid, wire)
    self._world_recalculate_uid(uid)
    from tools.local_original_session.world_status_frames import full_status_frame
    self._world._queue(uid, full_status_frame(self._world.combat.pcs[uid].status_fields))
    self._world._announce()


def _world_polymorph_use(self, ctx, payload, now):
    """Registry 0960 extension; native form selection/zero-stance are EXP only.

    -PolyExp selects one explicit form for raw0 use. It does not pretend to
    decode an unproven native selection operand. Incompatible worn weapons
    must be taken off through the ordinary equipment owner before use.
    """
    from tools.local_original_session import inventory, world_polymorph
    if self._inventory_kit_policy != inventory.KIT_POLICY:
        return False
    pb = ack.realm.pb
    with pb.parse_message(payload, limits=pb.WireLimits(max_body=4096, max_fields=2,
                                                       max_field_bytes=2048)) as parsed:
        fields = parsed.fields
        if not (len(fields) == 2 and len(parsed.occurrences(1)) == len(parsed.occurrences(2)) == 1
                and parsed.occurrences(1)[0].wire_type == 0
                and parsed.occurrences(2)[0].wire_type == 2):
            return False
        item_uid = parsed.occurrences(1)[0].value
        params = bytes(parsed.occurrences(2)[0].value)
    item = next((r for r in inventory.validate_kit_frame(self.inventory_frame)
                 if r.identifier == item_uid), None)
    if item is None:
        return False
    uid = ctx.pc_uid
    self._world_expire_polymorph(uid, now)
    effect = getattr(self, '_item_equipment_effect', None)
    worn, _ = (None, 0) if effect is None else effect.combat_inputs(uid)
    active = self._world_polymorphs.get(uid)
    definition = (getattr(effect, '_defs', None) or {}).get(item.template_bits)
    if active is not None and definition is not None and definition.weapon_type is not None:
        allowed = world_polymorph.weapon_allowed(self._world_poly_catalog.forms[active.active.form_key],
                                                   definition.weapon_type)
        need(definition == worn or allowed is True, 'POLYMORPH_WEAPON_NOT_ALLOWED')
    if item.template_bits != 299:
        return False
    need(self._world_poly_exp, 'POLYMORPH_NOT_READY_ENABLE_POLYEXP')
    with pb.parse_message(params, limits=pb.WireLimits(max_body=2048, max_fields=3,
                                                      max_field_bytes=2048)) as parsed:
        expected = {1: 1, 15: 0, 16: 0}
        need(len(parsed.fields) == 3 and all(len(parsed.occurrences(n)) == 1 for n in expected)
             and all(f.wire_type == 0 and f.value == expected[f.number] for f in parsed.fields),
             'POLYMORPH_SELECTION_PARAMS_UNVERIFIED_RAW0_EXPERIMENT_ONLY')
    need(dict(item.raw_fields)[4] > 0, 'WORLD_ITEM_OWNED_POSITIVE_STACK_REQUIRED')
    position = self.realm.service(ctx.writer).snapshot()
    base = self.realm._actor_for(position)[3] if active is None else active.base_sprite_id
    result = world_polymorph.use_scroll(active or world_polymorph.initial_appearance(base),
        self._world_poly_catalog, item_template_id=299, grade=1, form_key=self._world_poly_exp,
        character_level=self._world.combat.pcs[uid].profile.level, now_ms=int(now * 1000),
        weapon_type='unarmed' if worn is None else worn.weapon_type)
    need(result.allowed, result.reason)
    need(not result.unequip_weapon, 'POLYMORPH_UNEQUIP_WEAPON_BEFORE_USE')
    wire = self._world_polymorph_frame(uid, result.state.current_sprite_id)
    ctx.commit_attempted = True
    cost = self._world_consume_kit(ctx.writer, item_uid, result.consume_count)
    old = self._world_poly_timers.pop(uid, None)
    if old is not None:
        self._world.runtime.scheduler.cancel(old)
    self._world_polymorphs[uid] = result.state
    self._world_poly_timers[uid] = self._world.runtime.scheduler.schedule(
        result.state.active.expires_at_ms / 1000, None, 'pc_polymorph',
        lambda at: self._world_expire_polymorph(uid, at))
    self._world_recalculate_uid(uid)
    from tools.local_original_session.world_status_frames import full_status_frame
    for frame in (*self._world.drain(uid), cost, wire,
                  full_status_frame(self._world.combat.pcs[uid].status_fields)):
        ctx.send_frame(frame)
    return True


async def _world_use_item(self, writer, row, game, frame, operation_lock):
    """One world 0960 lane; equipment and unsupported templates retain their route.

    The reviewed double-click raw0 parameters are parsed with the existing
    protobuf codec. Source preparation stays at startup, never per request.
    """
    from tools.local_original_session import inventory, world_item_effects
    if (not self._world_bound(writer) or self._world_ready(writer, game) is None
            or self._inventory_kit_policy != inventory.KIT_POLICY):
        return False
    pb = ack.realm.pb
    try:
        with pb.parse_message(frame.payload, limits=pb.WireLimits(
                max_body=4096, max_fields=2, max_field_bytes=2048)) as parsed:
            need(len(parsed.occurrences(1)) == len(parsed.occurrences(2)) == 1
                 and len(parsed.fields) == 2, 'WORLD_ITEM_REQUIRED_PARENT_FIELDS')
            identifier, params = parsed.occurrences(1)[0], parsed.occurrences(2)[0]
            need(identifier.wire_type == 0 and params.wire_type == 2,
                 'WORLD_ITEM_PARENT_WIRE_TYPE')
            item_uid, params_raw = identifier.value, bytes(params.value)
        items = inventory.validate_kit_frame(self.inventory_frame)
        item = next((member for member in items if member.identifier == item_uid), None)
        if item is None or item.template_bits not in self._world_item_effects.definitions:
            return False
        with pb.parse_message(params_raw, limits=pb.WireLimits(
                max_body=2048, max_fields=3, max_field_bytes=2048)) as parsed:
            expected = {1: 1, 15: 0, 16: 0}
            need(len(parsed.fields) == 3 and all(len(parsed.occurrences(n)) == 1
                 for n in expected) and all(field.wire_type == 0
                 and field.value == expected[field.number] for field in parsed.fields),
                 'WORLD_ITEM_REVIEWED_RAW0_PARAMS_REQUIRED')
    except (ValueError, pb.WireError) as error:
        self._world_item_errors = (self._world_item_errors + [str(error)[:96]])[-4:]
        return True
    uid = self._world_pcs[id(writer)][1]
    position = self.realm.service(writer).snapshot()
    event = self._world_events.get(uid)
    if event is not None:
        event.clear()
    attempted = False

    async def apply():
        nonlocal attempted
        world = self._world
        need(self.realm.registry.resolve(writer) is game and self._world_bound(writer)
             and not world.combat.is_dead(uid), 'WORLD_ITEM_LIVING_SELECTED_PC_REQUIRED')
        current_item = next((member for member in inventory.validate_kit_frame(
            self.inventory_frame) if member.identifier == item_uid), None)
        need(current_item is not None and current_item.template_bits == item.template_bits
             and dict(current_item.raw_fields)[4] > 0, 'WORLD_ITEM_OWNED_POSITIVE_STACK_REQUIRED')
        kind = self._world_item_effects.definitions[item.template_bits].kind
        destination = world_item_effects.MapDestination(position.map_id, position.word0,
                                                         position.word1, 5)
        result = None
        if kind in ('return_town', 'random_teleport'):
            result = self._world_item_effects.use(uid, item.template_bits, world.runtime.clock(),
                                                  position=destination)
            need(result.destination is not None, result.reason or 'WORLD_ITEM_DESTINATION_REQUIRED')
            need(self.realm.serves_map(result.destination.map_id)
                 and (result.destination.map_id == position.map_id or self._world_map_exp == 2)
                 and world.terrain.can_stand(result.destination.map_id,
                     result.destination.x, result.destination.y) is True,
                 'WORLD_MAP_KNOWN_DESTINATION_REQUIRED')
        attempted = True
        wire = self._world_consume_kit(writer, item_uid)
        if result is None:
            ailments = self._world_ailments.setdefault(uid, world_item_effects.PcAilments())
            result = self._world_item_effects.use(uid, item.template_bits, world.runtime.clock(),
                                                  position=destination, ailments=ailments)
        if result.buff_kind is not None:
            key = (uid, result.buff_kind)
            old = world.buffs.pop(key, None)
            if old is not None:
                world.runtime.scheduler.cancel(old)
            world.buffs[key] = world.runtime.scheduler.schedule(
                result.buff_expires_at, None, 'pc_buff',
                lambda now: world._buff_expired(uid, result.buff_kind, now))
        transition_frames = ()
        if result.destination is not None:
            transition_frames = self._world_relocate_locked(writer, row, game, result.destination)
        return tuple(world.drain(uid)) + (wire,) + result.frames + transition_frames
    try:
        frames = await self._world.runtime.dispatch_now(apply)
    except ValueError as error:
        if attempted:
            raise  # a saved cost / uncertain save is not retried or refunded
        self._world_item_errors = (self._world_item_errors + [str(error)[:96]])[-4:]
        return True
    await self._world_send(writer, row, frames, operation_lock)
    return True


async def _world_potion_locked(self, writer, row, wire, template_id):
    """Kit potion (caller holds the row lock, Store already replaced): heal, then
    send the inventory change and the PC's SC_STATUS through the world lane."""
    need(self._world_bound(writer) and row['writer'] is writer and row['operation_lock'].locked(),
         'ITEM_USE_POTION_REQUIRES_WORLD_PC')
    uid = self._world_pcs[id(writer)][1]
    world = self._world

    def heal():
        # Queued tick frames (older HP/speed) go before the new effect.
        return world.drain(uid), self._world_item_effects.use(uid, template_id, world.runtime.clock())
    event = self._world_events.get(uid)
    if event is not None:
        event.clear()
    older, result = await world.runtime.dispatch_now(heal)
    need(result.outcome in ('applied', 'no_effect'),
         result.reason or 'ITEM_USE_POTION_REQUIRES_WORLD_PC')
    await self._world_send(writer, row, tuple(older) + (wire,) + result.frames, row['operation_lock'])
    return dict(healed_hp=result.healed_hp, hp_after=world.combat.hp_of(uid))


async def _world_buff_locked(self, writer, row, wire, buff):
    """Kit speed potion (caller holds the row lock, Store already replaced): timed
    buff in world combat, then the inventory change and SC4E5B (if it took effect)."""
    need(self._world_bound(writer) and row['writer'] is writer and row['operation_lock'].locked(),
         'ITEM_USE_POTION_REQUIRES_WORLD_PC')
    uid = self._world_pcs[id(writer)][1]
    world = self._world

    def apply():
        # Queued tick frames (e.g. an older expiry reset) go before the new buff.
        return world.drain(uid), world.apply_buff(uid, buff)
    event = self._world_events.get(uid)
    if event is not None:
        event.clear()
    older, frame = await world.runtime.dispatch_now(apply)
    frames = tuple(older) + ((wire,) if frame is None else (wire, frame))
    await self._world_send(writer, row, frames, row['operation_lock'])
    return dict(buff_kind=buff.kind, buff_applied=frame is not None)


METHODS = (
    _world_enchant_use,
    _world_polymorph_frame,
    _world_expire_polymorph,
    _world_polymorph_use,
    _world_use_item,
    _world_potion_locked,
    _world_buff_locked,
)
FRAMES = {0x0960: ('_world_use_item',)}


def setup_enchant(self):
    import os
    from tools.local_original_session import world_enchant, world_enchant_inventory
    world_enchant._policy()  # LOCAL probability table: startup, never first use.
    self._world_enchant_exp = world_enchant_inventory.parse_experiment(
        os.environ.get('SL_EXPERIMENT_ENCHANT'))


def setup_polymorph(self):
    import os
    from tools.local_original_session import world_polymorph
    self._world_poly_catalog = world_polymorph.load_polymorphs()
    self._world_poly_exp = os.environ.get('SL_EXPERIMENT_POLY', '').strip()
    need(not self._world_poly_exp or self._world_poly_exp in self._world_poly_catalog.forms,
         'WORLD_POLY_EXPERIMENT_FORM_REQUIRED')
    self._world_polymorphs, self._world_poly_timers = {}, {}
    self.realm._world_appearance = lambda uid, base: (
        self._world_polymorphs[uid].current_sprite_id if uid in self._world_polymorphs else base)


def setup_effects(self):
    from tools.local_original_session import world_item_effects
    self._world_item_effects = world_item_effects.WorldItemEffects(self._world.combat,
                                                                self._world.terrain)
    self._world_ailments = {}
