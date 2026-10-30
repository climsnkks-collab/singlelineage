"""World feature: items. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_native_login_local_ack_hook import ack_enter_world as ack
from tools.local_original_session.world_bridge import need


async def _world_items_kit_potion(ctx, base, consumer, writer, context, receipt, definition):
    """Own the existing kit potion operation before it can debit inventory."""
    return await consumer._consume_potion(writer, context, receipt, definition)


WRAPS = {'_world_consume_kit_potion': _world_items_kit_potion}


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
            world_enchant_inventory.enchant_level(target, definition), bless=target.bless))
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
    warehouse = self.inventory_transactions.restore_warehouse(ctx.pc_uid)
    ctx.commit_attempted = True
    equipment_change = (dict(equipment_store=effect.store,
        equipment_before=equipment, equipment_after=equipment_after)
        if equipment_after != equipment else {})
    self.inventory_transactions.commit_warehouse(ctx.pc_uid, before, mutation.frame,
        warehouse, warehouse, **equipment_change)
    self.inventory_frame = mutation.frame
    self.run_sync_hooks('inventory_changed', ctx.writer, ctx.row)
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


async def _world_polymorph_use(self, ctx, payload, now):
    """Native local list selection -> existing saved cost and SC4E5C.

    REA 5689D0/AC1530/569260: raw16 opens the original local list, whose
    selection sends scroll UID + self UID + the XML monster name in params.f7.
    No initial raw0 use or server-created list is part of that path.
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
    with pb.parse_message(params, limits=pb.WireLimits(max_body=2048, max_fields=5,
                                                      max_field_bytes=2048)) as parsed:
        expected = {1: 1, 2: uid, 15: 0, 16: 0}
        need(len(parsed.fields) == 5
             and all(len(parsed.occurrences(n)) == 1 for n in (*expected, 7))
             and all(parsed.occurrences(n)[0].wire_type == 0
                     and parsed.occurrences(n)[0].value == value
                     for n, value in expected.items())
             and parsed.occurrences(7)[0].wire_type == 2,
             'POLYMORPH_NATIVE_SELECTION_PARAMS_REQUIRED')
        name = bytes(parsed.occurrences(7)[0].value).decode('utf-8')
    form_key = self._world_poly_catalog.native_names.get(name)
    need(form_key is not None, 'POLYMORPH_UNKNOWN_NATIVE_FORM')
    need(dict(item.raw_fields)[4] > 0, 'WORLD_ITEM_OWNED_POSITIVE_STACK_REQUIRED')
    position = self.realm.service(ctx.writer).snapshot()
    base = self.realm._actor_for(position)[3] if active is None else active.base_sprite_id
    from tools.local_original_session.world_enchant_inventory import instance_grade
    result = world_polymorph.use_scroll(active or world_polymorph.initial_appearance(base),
        self._world_poly_catalog, item_template_id=299, grade=instance_grade(item), form_key=form_key,
        character_level=self._world.combat.pcs[uid].profile.level, now_ms=int(now * 1000),
        weapon_type='unarmed' if worn is None else worn.weapon_type)
    need(result.allowed, result.reason)
    # Takeoff/masks/durations are attributed L1J LOCAL policy. Reuse the
    # existing joint inventory/equipment CAS; never debit before admission.
    changes = ()
    if result.unequip_weapon:
        cost, equipment_after, changes = _world_polymorph_takeoff(self, ctx, item, worn)
    else:
        ctx.commit_attempted = True
        cost = self._world_consume_kit(ctx.writer, item_uid, result.consume_count)
    old = self._world_poly_timers.pop(uid, None)
    if old is not None:
        self._world.runtime.scheduler.cancel(old)
    self._world_polymorphs[uid] = result.state
    self._world_poly_timers[uid] = self._world.runtime.scheduler.schedule(
        result.state.active.expires_at_ms / 1000, None, 'pc_polymorph',
        lambda at: self._world_expire_polymorph(uid, at))
    if changes:
        from tools.local_original_session.item_equipment_effect import _receipt
        await effect._notify_kit(effect._context(ctx.writer), equipment_after,
                                  _receipt('INITIAL_SYNC'), changes)
        if effect._selection is not None:
            effect._selection['state'] = equipment_after
    wire = self._world_polymorph_frame(uid, result.state.current_sprite_id)
    self._world_recalculate_uid(uid)
    from tools.local_original_session.world_status_frames import full_status_frame
    for frame in (*self._world.drain(uid), cost, wire,
                  full_status_frame(self._world.combat.pcs[uid].status_fields)):
        ctx.send_frame(frame)
    return True


def _world_polymorph_takeoff(self, ctx, scroll, weapon):
    """Existing inventory/equipment transaction owner, one scroll and takeoff."""
    from dataclasses import replace
    from tools.local_original_session import (equipment_store, inventory,
        inventory_update, item_transfer_protocol)
    before = self.inventory_frame
    items = inventory.validate_kit_frame(before)
    quantity = dict(scroll.raw_fields)[4]
    removed = quantity == 1 and len(items) > 1
    rows = []
    for item in items:
        fields = dict(item.raw_fields)
        if item.identifier == scroll.identifier:
            if removed:
                continue
            fields[4] = quantity - 1
        rows.append(fields)
    after = inventory.build_kit_frame(rows)
    effect = self._item_equipment_effect
    equipment = effect.store.restore(ctx.pc_uid, before)
    equipment_after = equipment_store.after_removal(equipment, before, after) or equipment
    if equipment_after is equipment:
        equipment_after = replace(equipment, revision=equipment.revision + 1)
    equipment_after = replace(equipment_after, weapon_uid=0)
    changes = ((equipment.weapon_uid, weapon.slot_key, False),)
    ctx.commit_attempted = True
    self.inventory_transactions.commit_inventory(ctx.pc_uid, before, after,
        equipment_store=effect.store, equipment_before=equipment,
        equipment_after=equipment_after)
    self.inventory_frame = after
    self.run_sync_hooks('inventory_changed', ctx.writer, ctx.row)
    wire = (item_transfer_protocol.build_remove(uid=scroll.identifier) if removed else
        inventory_update._encode(inventory_update._values({1: scroll.identifier, 4: quantity - 1})))
    return wire, equipment_after, changes


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
        if kind in ('return_town', 'random_teleport', 'tower_teleport'):
            result = self._world_item_effects.use(uid, item.template_bits, world.runtime.clock(),
                                                  position=destination)
            result = self.fold_sync_hooks('item_destination_policy', result, destination)
            need(result.destination is not None, result.reason or 'WORLD_ITEM_DESTINATION_REQUIRED')
            need(self.realm.serves_map(result.destination.map_id)
                 and (result.destination.map_id == position.map_id or self._world_map_exp == 2)
                 and world.terrain.can_stand(result.destination.map_id,
                     result.destination.x, result.destination.y) is True,
                 'WORLD_MAP_KNOWN_DESTINATION_REQUIRED')
        attempted = True
        # A reusable tower charm proposes zero cost; it must never enter the
        # ordinary one-item debit lane. Ownership was checked above under lock.
        wire = (self._world_consume_kit(writer, item_uid)
                if result is None or result.consume_count else None)
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
        world.broadcast_pc_effects(uid, result.frames)
        return tuple(world.drain(uid)) + (() if wire is None else (wire,)) + result.frames + transition_frames
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
        older = world.drain(uid)
        result = self._world_item_effects.use(uid, template_id, world.runtime.clock())
        world.broadcast_pc_effects(uid, result.frames)
        return older, result
    event = self._world_events.get(uid)
    if event is not None:
        event.clear()
    older, result = await world.runtime.dispatch_now(heal)
    need(result.outcome in ('applied', 'no_effect'),
         result.reason or 'ITEM_USE_POTION_REQUIRES_WORLD_PC')
    await self._world_send(writer, row, tuple(older) + (wire,) + result.frames, row['operation_lock'])
    return dict(healed_hp=result.healed_hp, hp_after=world.combat.hp_of(uid))


async def _world_buff_locked(self, writer, row, wire, buff, template_id=None):
    """Kit speed potion (caller holds the row lock, Store already replaced): timed
    buff in world combat, then the inventory change, the item's 4ED8 use effect
    and SC4E5B (if it took effect)."""
    need(self._world_bound(writer) and row['writer'] is writer and row['operation_lock'].locked(),
         'ITEM_USE_POTION_REQUIRES_WORLD_PC')
    uid = self._world_pcs[id(writer)][1]
    world = self._world

    def apply():
        # Queued tick frames (e.g. an older expiry reset) go before the new buff.
        older, frame = world.drain(uid), world.apply_buff(uid, buff)
        icons = (() if frame is None or template_id is None else
                 self._world_item_effects.icon_frames(uid, template_id, world.runtime.clock()))
        effect = (None if frame is None or template_id is None
                  else self._world_item_effects.use_effect_frame(uid, template_id))
        world.broadcast_pc_effects(uid, tuple(w for w in (effect, frame) if w is not None))
        return older, frame, icons, effect
    event = self._world_events.get(uid)
    if event is not None:
        event.clear()
    older, frame, icons, effect = await world.runtime.dispatch_now(apply)
    frames = tuple(older) + ((wire,) if frame is None else
                             (wire, frame) if effect is None else (wire, effect, frame))
    await self._world_send(writer, row, frames + icons, row['operation_lock'])
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
    self._world_enchant_results = []


def setup_polymorph(self):
    from dataclasses import replace
    from tools.local_original_session import world_polymorph
    from tools.local_original_session.world_handlers import KitItemPolicy
    self._world_poly_catalog = world_polymorph.load_polymorphs()
    self._world_polymorphs, self._world_poly_timers = {}, {}
    definition = self.world.data.items[299]
    policy = self.item_policies.get(299)
    fields = dict(self.starter_fields if policy is None or policy.grant_fields is None
                  else policy.grant_fields)
    fields.update({2: 299, 5: 16, 7: definition.icon})
    self.add_item_policies((KitItemPolicy(299, definition.weight, definition.stackable, fields)
        if policy is None else replace(policy, grant_fields=fields),), replace_existing=True)


def setup_effects(self):
    from tools.local_original_session import world_item_effects
    self._world_item_effects = world_item_effects.WorldItemEffects(self._world.combat,
                                                                self._world.terrain)
    self._world_ailments = {}
    self._world_item_errors = []


def _world_items_initialize(self):
    setup_enchant(self)
    setup_polymorph(self)
    setup_effects(self)


def _world_items_kit_frame(self, frame, character_class):
    from tools.local_original_session import inventory
    rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
    for fields in rows:
        if fields[2] == 299:
            fields[5] = 16
        elif self._world_enchant_exp is not None and fields[2] in (25, 26) and fields.get(18):
            fields[5] = 7
    return inventory.build_kit_frame(rows)


async def _world_items_inventory_delivered(self, writer, row, game, operation_lock):
    """Project the native use code for old saved rows without rewriting saves.

    REA run41: SC0965 ItemInfo.f5 writes ItemEntity+50. The inventory owner
    invokes this hook after its normal initial inventory send/drain.
    """
    from tools.local_original_session import inventory, inventory_update
    frames = tuple(inventory_update._encode(inventory_update._values(
        {1: item.identifier, 5: 16})) for item in inventory.validate_kit_frame(self.inventory_frame)
        if item.template_bits == 299 and dict(item.raw_fields)[5] != 16)
    if frames:
        await self._world_send(writer, row, frames, operation_lock)


def _world_items_pickup_fields(self, fields, ground_item):
    """Keep the actual rolled grade in the existing persisted LOCAL f18 lane."""
    from tools.local_original_session import world_enchant_inventory as enchant
    fields = dict(fields)
    if ground_item.item_id == 299:
        fields[5] = 16
    grade = getattr(ground_item, 'grade', 1)  # Existing tuple-only callers explicitly mean normal.
    if ground_item.item_id in (25, 26):
        fields[18] = enchant.scroll_name(ground_item.item_id, grade)
    elif grade != 1:
        definition = self.world.data.items[ground_item.item_id]
        fields[18] = enchant.enchanted_name(definition, 0, grade=grade)
    return fields


def _world_items_actor(realm, actor, position):
    active = realm._world_context._world_polymorphs.get(position.uid)
    if active is not None:
        actor = dict(actor)
        actor[3] = active.current_sprite_id
    return actor


def _world_items_before_leave(self, writer, uid):
    self._world_ailments.pop(uid, None)
    handle = self._world_poly_timers.pop(uid, None)
    if handle is not None:
        self.world.runtime.scheduler.cancel(handle)
    self._world_polymorphs.pop(uid, None)


def _world_items_cure_poison(self, uid):
    ailments = self._world_ailments.get(uid)
    if ailments is not None:
        ailments.poison = None


def _world_items_report(self, result):
    result.update(item_errors=list(self._world_item_errors),
        polymorph_selection='native_xml_name', active_polymorphs=len(self._world_polymorphs),
        enchant_experiment=self._world_enchant_exp is not None,
        enchant_results=list(self._world_enchant_results))


def _item_use_save_boundary(owner, args, templates):
    # Existing targeted-item save-boundary predicate, shared by saved uses.
    from tools.local_original_session import inventory
    if getattr(owner, '_inventory_kit_policy', None) != inventory.KIT_POLICY or len(args) < 2:
        return False
    pb = ack.realm.pb
    try:
        with pb.parse_message(args[1], limits=pb.WireLimits(
                max_body=4096, max_fields=2, max_field_bytes=2048)) as parsed:
            fields = parsed.occurrences(1)
            if len(fields) != 1 or fields[0].wire_type != 0:
                return False
            uid = fields[0].value
        return any(item.identifier == uid and item.template_bits in templates
                   for item in inventory.validate_kit_frame(owner._inventory_current_frame))
    except (ValueError, pb.WireError):
        return False


def _enchant_save_boundary(owner, args):
    return _item_use_save_boundary(owner, args, (25, 26))


def _polymorph_save_boundary(owner, args):
    return _item_use_save_boundary(owner, args, (299,))


METHODS += (_world_items_initialize, _world_items_kit_frame, _world_items_before_leave,
            _world_items_cure_poison, _world_items_report, _world_items_pickup_fields,
            _world_items_inventory_delivered)
HOOKS = {'initialize': ('_world_items_initialize',),
         'item_use': ('_world_enchant_use', '_world_polymorph_use'),
         'kit_frame': ('_world_items_kit_frame',),
         'inventory_delivered': ('_world_items_inventory_delivered',),
         'pickup_item_fields': ('_world_items_pickup_fields',),
         'before_leave': ('_world_items_before_leave',),
         'cure_poison': ('_world_items_cure_poison',),
         'report': ('_world_items_report',)}
REALM_HOOKS = {'actor_fields': (_world_items_actor,)}
NONCRITICAL_HOOKS = ('before_leave', 'before_enter', 'entry_probe', 'report')
SAVE_BOUNDARIES = {'_world_enchant_use': _enchant_save_boundary,
                   '_world_polymorph_use': _polymorph_save_boundary}


# Consumable lifecycle and its later 0960 lane share this feature's effect
# owner. Removing items therefore removes both dispatchers before any debit.
from tools.local_original_session import world_item_effects as _consumables

METHODS += _consumables.METHODS
HOOKS = {**HOOKS, **{name: HOOKS.get(name, ()) + methods
                    for name, methods in _consumables.HOOKS.items()}}
FRAMES = {**FRAMES, **{opcode: FRAMES.get(opcode, ()) + methods
                      for opcode, methods in _consumables.FRAMES.items()}}


def _world_items_display_fields(self, fields, item):
    """Send-time ItemInfo projection: enchant scrolls 25/26 use f5=7 (targeted
    use, the client picks the item and sends the run393 targeted 0960 params).
    Saved rows keep their stored f5; only the written 0964 bytes change."""
    if fields.get(2) in (25, 26):
        fields[5] = 7
    return fields


METHODS += (_world_items_display_fields,)
HOOKS = {**HOOKS, 'inventory_display_fields': (HOOKS.get('inventory_display_fields', ())
                                               + ('_world_items_display_fields',))}
# Item-use 4ED8 effects (core world_status_frames.effect_frame) with or without magic/companion.
OUTGOING_OPCODES = (0x4ED8, 0x4E91)
