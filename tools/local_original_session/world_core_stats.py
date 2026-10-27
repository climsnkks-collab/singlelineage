"""World core: stats. Existing packet/store operations, unchanged."""
from __future__ import annotations



def _world_stats_for(self, position, *, level=None):
    """One LOCAL calculation for combat and run395 full SelfInfo projection."""
    from tools.local_original_session import inventory, world_stats, world_enchant_inventory
    _, info = self.realm.store.select(position.name)
    if level is None:
        saved = self._world_progress_for(position.uid)
        level = info[10] if saved is None else saved.level
    worn = []
    effect = getattr(self, '_item_equipment_effect', None)
    if effect is not None:
        equipment, frame = effect.store.peek(position.uid)
        if equipment is not None and frame is not None:
            selected = {equipment.weapon_uid, *(uid for _, uid in equipment.slots)} - {0}
            for item in inventory.validate_kit_frame(frame):
                if item.identifier in selected:
                    definition = self._world.data.items[item.template_bits]
                    worn.append(world_stats.EquippedItem(definition,
                        enchant=world_enchant_inventory.enchant_level(item, definition)))
    base = world_stats.CharacterStats(level, info[3], world_stats.Attributes(
        info[11], info[12], info[13], info[14], info[15], info[16]))
    from dataclasses import replace
    from tools.local_original_session import world_weight
    calculated, worn, info = self.fold_sync_hooks('stats_modifiers',
        (world_stats.calculate_stats(base, worn), tuple(worn), info), position, level=level)
    carried = 0
    if effect is not None:
        _, frame = effect.store.peek(position.uid)
        if frame is not None:
            def raw_weight(template):
                definition = self.world.data.items.get(template)
                return (definition.weight if definition is not None else
                        self.fold_sync_hooks('item_weight', 0, template))
            carried = sum(world_weight.stack_weight(raw_weight(item.template_bits),
                dict(item.raw_fields)[4]) for item in inventory.validate_kit_frame(frame)
                if dict(item.raw_fields)[4] > 0)
    capacity = world_weight.maximum_weight(calculated.attributes.strength, calculated.attributes.con)
    capacity = self.fold_sync_hooks('weight_capacity', capacity, calculated, position)
    calculated = replace(calculated, max_weight=capacity,
                         weight=world_weight.weight_state(carried, capacity))
    return calculated, worn, info


def _world_fields_for(self, position, existing):
    from tools.local_original_session import world_stats
    state = self._world.combat.pcs.get(position.uid)
    # Existing live snapshot owns optional presence, EXP and current vitals.
    fields = dict(existing if state is None else state.status_fields)
    calculated, _, _ = self._world_stats_for(position,
        level=fields[2] if state is None else state.profile.level)
    fields = world_stats.self_info_fields(fields, calculated)
    if state is not None:
        fields[10], fields[12] = state.hp, state.mp
    fields[18] = self.world.progress.lawful_of(position.uid, fields[18])
    return fields


def _world_pc_profile(self, writer, position, *, level=None):
    from dataclasses import replace
    from tools.local_original_session import world_combat
    calculated, worn, info = self._world_stats_for(position, level=level)
    weapon = next((entry for entry in worn if entry.item.kind == 'weapon'), None)
    combat_weapon = (world_combat.FIST if weapon is None else replace(
        world_combat.weapon_from_item(weapon.item), enchant=weapon.enchant))
    return world_combat.PcProfile(level=calculated.level, character_class=info[3], gender=info[5],
        strength=calculated.attributes.strength, dexterity=calculated.attributes.dexterity,
        ac=calculated.ac, weapon=combat_weapon, con=calculated.attributes.con,
        wis=calculated.attributes.wis)


def _world_recalculate_uid(self, uid):
    state = self._world.combat.pcs.get(uid)
    writer = next((value[0] for value in self._world_pcs.values() if value[1] == uid), None)
    if state is None or writer is None:
        return False
    position = self.realm.service(writer).snapshot()
    state.profile = self._world_pc_profile(writer, position, level=state.profile.level)
    state.status_fields.update(self._world_fields_for(position, state.status_fields))
    return True


async def _world_refresh_pc(self, writer):
    """Saved equipment -> combat + complete SelfInfo; preserve all optional fields."""
    if not self._world_bound(writer):
        return False
    uid = self._world_pcs[id(writer)][1]
    def refresh():
        from tools.local_original_session.world_status_frames import full_status_frame
        changed = self._world_recalculate_uid(uid)
        if changed:
            self._world._queue(uid, full_status_frame(self._world.combat.pcs[uid].status_fields))
            self._world._announce()
        return changed
    return await self._world.runtime.dispatch_now(refresh)


METHODS = (
    _world_stats_for,
    _world_fields_for,
    _world_pc_profile,
    _world_recalculate_uid,
    _world_refresh_pc,
)
HOOKS = {'stats_changed': ('_world_recalculate_uid',)}


def _world_look(self, name):
    """M1 world: the stored row's class/gender/attributes for the own frames.

    SelfInfo f4..f9 = STR/DEX/INT/WIS/CON/CHA (tools/local_self_info_profile/model.py
    _values/provenance projection of the store's STR/DEX/CON/WIS/CHA/INT). ActorNotify
    f3 is the sprite key (tools/local_self_actor_profile/profile.py require_sprite_key);
    class/gender -> sprite is LOCAL policy from world_combat.PC_SPRITES (list.spr
    #0 prince/#61 knight..., same as L1J C_CreateChar MALE_LIST/FEMALE_LIST). The
    fixed royal profile maps to its own values, so SoloKnight's frames are unchanged.
    """
    looks = getattr(self, '_world_looks', None)
    if looks is None:
        looks = self._world_looks = {}
    if name not in looks:
        from tools.local_original_session.world_combat import PC_SPRITES
        _, info = self.store.select(name)
        looks[name] = (PC_SPRITES.get((info[3], info[5])),
                       {4: info[11], 5: info[12], 6: info[16], 7: info[14], 8: info[13], 9: info[15]})
    return looks[name]


REALM_METHODS = (_world_look,)


def realm_actor(self, position, actor):
    if getattr(self, '_world_hp', None) is not None:
        sprite, _ = self._world_look(position.name)
        if sprite is not None:
            actor[3] = sprite
        # Equipment is read from the saved row, never the clicked inventory item.
        actor[4] = self._world_stance(position.uid)
        from tools.local_original_session.world_registry import fold_realm_hooks
        actor = fold_realm_hooks('actor_fields', self, actor, position)
        import os
        experiment = os.environ.get('SL_EXPERIMENT_ACTOR_F4')
        if experiment is not None and experiment != '':
            actor[4] = int(experiment)
    return actor


def realm_status(self, position, fields, initial):
    world_hp = getattr(self, '_world_hp', None)
    if initial and world_hp is not None:
        progress = getattr(self, '_world_progress', None)
        saved = None if progress is None else progress(position.uid)
        if saved is not None:
            # M1 world: saved level / grown maxima (world_progress sidecar).
            fields = dict(fields)
            fields[2] = saved.level
            fields[18] = saved.lawful
            if saved.max_hp is not None:
                fields[11] = fields[10] = saved.max_hp  # full until the world HP says otherwise
            if saved.max_mp is not None and 13 in fields:
                fields[13] = saved.max_mp
        # M1 world: SelfInfo current HP comes from the world combat authority.
        hp = world_hp(position.uid)
        if type(hp) is int and 0 < hp:
            fields = dict(fields)
            fields[10] = min(hp, fields[11])
        world_mp = getattr(self, '_world_mp', None)
        mp = None if world_mp is None else world_mp(position.uid)
        if type(mp) is int and 0 <= mp and 13 in fields:
            fields = dict(fields)
            fields[12] = min(mp, fields[13])  # current MP (SC4E38 field12)
        _, stats = self._world_look(position.name)
        fields = dict(fields)
        fields.update(stats)
        from tools.local_original_session.world_registry import fold_realm_hooks
        fields = fold_realm_hooks('status_fields', self, fields, position, initial)
    stats_fields = getattr(self, '_world_stats_fields', None)
    if stats_fields is not None:
        fields = stats_fields(position, fields)
    return fields

