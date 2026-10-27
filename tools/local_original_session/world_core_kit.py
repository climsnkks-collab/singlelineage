"""World core: kit. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_game_session import session
from tools.local_original_session.world_bridge import need


def _inventory_kit_frame(self, character_class):
    """Selected class's data/m1/starter.json entries as one canonical 0964 kit frame."""
    from tools.local_original_session import inventory
    from tools.local_original_session.game_data import load_m1
    data = load_m1()
    starter = data.starter
    entries = starter.entries(character_class, getattr(self, '_world_starter_kit', None))
    need(entries, 'INVENTORY_KIT_CLASS_STARTER_REQUIRED')
    rows = []
    for index, entry in enumerate(entries):
        fields = dict(self.starter_fields)  # Same explicit 17 raw fields as the Athame starter.
        # f7 = inventory icon number: client 509390 copies f7 to ItemEntity+20, B03780 to the
        # slot model+C, and B046F0 shows '<f7>.png' only when it is >0 (f7=0 left every cell blank).
        fields.update({1: starter.uid_base + index, 2: entry.template_id, 4: entry.count,
                       7: data.items[entry.template_id].icon})
        if entry.grade is not None:
            from tools.local_original_session.world_enchant_inventory import scroll_name
            fields[18] = scroll_name(entry.template_id, entry.grade)
        rows.append(fields)
    return self.fold_sync_hooks('kit_frame', inventory.build_kit_frame(rows), character_class)


def _world_consume_kit(self, writer, item_uid, count=1):
    """Existing kit CAS and 0965/0978, before effects or a fired arrow."""
    from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
    need(self._inventory_kit_policy == inventory.KIT_POLICY and self._world_bound(writer),
         'WORLD_ITEM_CURRENT_KIT_REQUIRED')
    current = self.inventory_frame
    items = inventory.validate_kit_frame(current)
    item = next((member for member in items if member.identifier == item_uid), None)
    need(item is not None and count > 0, 'WORLD_ITEM_OWNED_STACK_REQUIRED')
    quantity = dict(item.raw_fields)[4]
    need(quantity >= count, 'WORLD_ITEM_INSUFFICIENT_QUANTITY')
    rows = []
    removed = quantity == count and len(items) > 1
    for member in items:
        fields = dict(member.raw_fields)
        if member.identifier == item_uid:
            if removed:
                continue
            fields[4] = quantity - count
        rows.append(fields)
    updated = inventory.build_kit_frame(rows)
    wire = (item_transfer_protocol.build_remove(uid=item_uid) if removed else
            inventory_update._encode(inventory_update._values({1: item_uid, 4: quantity - count})))
    uid = self._world_pcs[id(writer)][1]
    replace_kit = getattr(self, '_world_replace_kit', None) or self.inventory_store.replace_kit
    need(replace_kit(uid, current, updated) is True,
         'WORLD_ITEM_PERSISTED_CHANGE_REQUIRED')
    self.inventory_frame = updated
    return wire


def _world_replace_kit(self, uid, before, after, *, append=False):
    """Kit CAS that keeps the saved equipment row valid. A removed anchor moves to
    the first remaining item (removed worn members are taken off) and is saved
    with the inventory through the existing warehouse/equipment transfer owner."""
    from tools.local_original_session import equipment_store, inventory
    effect = getattr(self, '_item_equipment_effect', None)
    removed = ({item.identifier for item in inventory.validate_kit_frame(before)}
               - {item.identifier for item in inventory.validate_kit_frame(after)})
    transactions = getattr(self, '_world_inventory_transactions', None)

    def plain():
        if append:
            return self.inventory_store.replace_kit(uid, before, after, append=True)
        return self.inventory_store.replace_kit(uid, before, after)
    if (not removed or transactions is None
            or type(getattr(effect, 'store', None)) is not equipment_store.EquipmentStore):
        return plain()
    equipment = effect.store.restore(uid, before)
    equipment_after = equipment_store.after_removal(equipment, before, after)
    if equipment_after is None:
        return plain()
    changed = transactions.commit_inventory(uid, before, after, append=append,
        equipment_store=effect.store, equipment_before=equipment, equipment_after=equipment_after)
    if effect._selection is not None:
        effect._selection['state'] = equipment_after
    return changed


async def _world_consume_kit_potion(self, consumer, writer, context, receipt, definition):
    """Optional effects wrap this owner entry point before any inventory debit."""
    return consumer._blocked(receipt, 'ITEM_USE_KIT_NO_EFFECT')


def _world_stance_for(self, uid):
    effect = getattr(self, '_item_equipment_effect', None)
    weapon, _ = (None, 0) if effect is None else effect.combat_inputs(uid)
    weapon_type = 'unarmed' if weapon is None else weapon.weapon_type
    return self._world_stances.get(weapon_type, 0)


async def _world_refresh_stance_locked(self, writer, row):
    """After persisted equipment/097A drain, refresh the same self actor.

    Reuse its current position, accepted heading, class sprite and complete
    source DTO through the existing world send lane. Client rendering is unverified.
    """
    if not self._world_bound(writer):
        return None
    service = self.realm.service(writer)
    position = service.snapshot()
    frames = self.realm._frames_for(position, heading=getattr(service, '_actor_heading', None))
    self.realm._world_frames[id(writer)] = (position, frames)
    await self._world_send(writer, row, (frames[2],), row['operation_lock'])
    return session.world.decode_payload(0x4e96, frames[2][4:-2])[4]


METHODS = (
    _inventory_kit_frame,
    _world_consume_kit,
    _world_replace_kit,
    _world_consume_kit_potion,
    _world_stance_for,
    _world_refresh_stance_locked,
)


def setup_stance(self):
    from tools.local_original_session.game_data import load_stances
    self._world_stances = load_stances()
    self.realm._world_stance = self._world_stance_for


def setup_starter(self, world_policy, world_starter_kit):
    # Optional named data/m1/starter.json kit for a missing saved row (manual -TestKnight).
    self._world_starter_kit = None
    if world_starter_kit is not None:
        from tools.local_original_session.game_data import load_m1
        need(world_policy is not None and type(world_starter_kit) is str
             and world_starter_kit in load_m1().starter.kits, 'WORLD_STARTER_KIT_REQUIRED')
        self._world_starter_kit = world_starter_kit



def defer_equipment_prepare(broker, life):
    # Preserve the kit's existing wait for the native inventory delivery check.
    return (getattr(broker, '_inventory_kit_policy', None) is not None
            and not (type(life) is dict and life.get('synced') is True))


def inventory_items(self, frame):
    from tools.local_original_session import inventory
    if getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY:
        return inventory.validate_kit_frame(frame)
    return None


def starter_frame(self, name, fallback):
    from tools.local_original_session import inventory
    if getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY:
        _, info = self.realm.store.select(name)
        frame = self._inventory_kit_frame(info[3])
        self._inventory_config_frame = frame
        return frame
    return fallback


def first_grant_valid(self, frame):
    from tools.local_original_session import inventory
    return (bool(inventory.validate_kit_frame(frame))
            if getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY else
            dict(inventory.validate_frame(frame).raw_fields) == self.starter_fields)


def inventory_payload(self, wire, inventory_wire):
    if not inventory_wire:
        return wire
    from tools.local_original_session import inventory
    if getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY:
        # Consecutive append 0964 frames, written and drained once as before.
        frames = inventory.kit_wire_frames(wire)
        return frames[0] if len(frames) == 1 else b''.join(frames)
    return wire



def _world_kit_initialize(self):
    setup_stance(self)

METHODS += (_world_kit_initialize,)
HOOKS = {'initialize': ('_world_kit_initialize',)}
