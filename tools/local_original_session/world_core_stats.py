"""World core stats and equipment projections using existing packets/stores."""
from __future__ import annotations

from dataclasses import fields, replace
from tools.local_original_session.world_combat import PcState


class EquipmentPcState(PcState):
    """Core-owned runtime metadata; saved and wire schemas retain their keys."""

    @property
    def max_hp(self):
        return self._effective_max_hp

    @max_hp.setter
    def max_hp(self, value):
        self._effective_max_hp = value
        if hasattr(self, 'base_max_hp'):
            # Existing reward/quest writers assign a new BASE maximum here.
            self.base_max_hp = value
            self.resource_base_written = True

    def set_base_maxima(self, hp, mp):
        if hp is not None:
            self.base_max_hp = hp
            self._effective_max_hp = max(1, hp + self.equipment_hp_bonus)
        if mp is not None:
            self.base_max_mp = mp
            self.status_fields[13] = max(0, mp + self.equipment_mp_bonus)
        self.resource_base_written = False


def _resource_state(state):
    if isinstance(state, EquipmentPcState):
        return state
    result = EquipmentPcState(**{member.name: getattr(state, member.name) for member in fields(PcState)})
    result.base_max_hp, result.base_max_mp = state.max_hp, state.max_mp
    result.equipment_hp_bonus = result.equipment_mp_bonus = 0
    result.equipment_level = state.profile.level
    result.equipment_calculated = None
    result.resource_base_written = False
    return result


def project_resources(state, calculated, *, base=None):
    """Rebuild effective caps from growth bases, never from a previous bonus."""
    if base is not None:
        state.base_max_hp, state.base_max_mp = base
    else:
        # Reward/quest consumers publish new BASE maxima before stats_changed.
        base_written = state.resource_base_written
        if not base_written and state.status_fields[11] != max(1, state.base_max_hp + state.equipment_hp_bonus):
            state.base_max_hp = state.status_fields[11]
        if state.base_max_mp is not None and (base_written or
                state.status_fields.get(13) != max(0, state.base_max_mp + state.equipment_mp_bonus)):
            state.base_max_mp = state.status_fields.get(13)
    state.equipment_hp_bonus = calculated.max_hp_bonus
    state.equipment_mp_bonus = calculated.max_mp_bonus
    state.equipment_level = state.profile.level
    state.equipment_calculated = calculated
    state._effective_max_hp = max(1, state.base_max_hp + calculated.max_hp_bonus)
    state.resource_base_written = False
    state.status_fields[11] = state.max_hp
    state.hp = max(0, min(state.hp, state.max_hp))
    state.status_fields[10] = state.hp
    if state.base_max_mp is not None:
        state.status_fields[13] = max(0, state.base_max_mp + calculated.max_mp_bonus)
        state.status_fields[12] = max(0, min(state.mp, state.max_mp))



def _world_stats_for(self, position, *, level=None):
    """One LOCAL calculation for combat and run395 full SelfInfo projection."""
    from tools.local_original_session import inventory, world_stats, world_enchant_inventory
    _, info = self.realm.store.select(position.name)
    # Permanent growth is folded before equipment and derived AC/MR/hit/weight.
    # Providers return a copied character-info mapping; the creation row stays intact.
    info = self.fold_sync_hooks('base_attributes', info, position)
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
                if item.identifier in selected and dict(item.raw_fields)[4] > 0:
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
                if definition is not None:
                    return definition.weight
                policy = self.item_policies.get(template)
                current = 0 if policy is None else policy.raw_weight
                return self.fold_sync_hooks('item_weight', current, template)
            carried = sum(world_weight.stack_weight(raw_weight(item.template_bits),
                dict(item.raw_fields)[4]) for item in inventory.validate_kit_frame(frame)
                if dict(item.raw_fields)[4] > 0)
    capacity = world_weight.maximum_weight(calculated.attributes.strength, calculated.attributes.con)
    capacity = self.fold_sync_hooks('weight_capacity', capacity, calculated, position)
    # Hooks own their capacity effects (the magic hook rebuilds the base).
    # Add official fixed equipment capacity once, after those calculations.
    capacity += calculated.weight_bonus
    calculated = replace(calculated, max_weight=capacity,
                         weight=world_weight.weight_state(carried, capacity),
                         carried_weight=carried)
    return calculated, worn, info


def _world_fields_for(self, position, existing):
    from tools.local_original_session import world_stats
    state = self._world.combat.pcs.get(position.uid)
    # Existing live snapshot owns optional presence, EXP and current vitals.
    fields = dict(existing if state is None else state.status_fields)
    calculated, _, info = self._world_stats_for(position,
        level=fields[2] if state is None else state.profile.level)
    fields = world_stats.self_info_fields(fields, calculated)
    if state is not None:
        if isinstance(state, EquipmentPcState):
            state.base_growth_con, state.base_growth_wis = info[13], info[14]
            project_resources(state, calculated)
            fields[11] = state.max_hp
            if state.max_mp is not None:
                fields[13] = state.max_mp
        fields[10], fields[12] = state.hp, state.mp
    else:
        # Preserve the pre-projection bases for the imminent bind wrapper.
        pending = getattr(self, '_world_equipment_pending', None)
        if pending is None:
            pending = self._world_equipment_pending = {}
        pending[position.uid] = (fields[11], fields.get(13), calculated, info[13], info[14])
        fields[11] = max(1, fields[11] + calculated.max_hp_bonus)
        fields[10] = min(fields[10], fields[11])
        if 13 in fields:
            fields[13] = max(0, fields[13] + calculated.max_mp_bonus)
            fields[12] = min(fields[12], fields[13])
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
        wis=calculated.attributes.wis, mr=calculated.mr,
        resist_earth=calculated.resist_earth, resist_fire=calculated.resist_fire,
        resist_water=calculated.resist_water, resist_wind=calculated.resist_wind)


def _world_recalculate_uid(self, uid):
    state = self._world.combat.pcs.get(uid)
    writer = next((value[0] for value in self._world_pcs.values() if value[1] == uid), None)
    if state is None or writer is None:
        return False
    position = self.realm.service(writer).snapshot()
    state = self._world.combat.pcs[uid] = _resource_state(state)
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


def _world_weight_initialize(self):
    """Use the existing serialized world tick for every committed bag owner.

    World-handled requests bypass broker.after_request; HostStore.commit and
    kit costs do not all emit inventory_changed. The existing WorldView.tick
    emits this event and then announces its outbox, including idle players.
    No separate timer, inventory write or weight cache is introduced.
    """
    world = self.world

    def refresh(now):
        from tools.local_original_session import world_stats
        from tools.local_original_session.world_status_frames import full_status_frame
        for writer, uid in tuple(self._world_pcs.values()):
            state = world.combat.pcs.get(uid)
            if state is None:
                continue
            position = self.realm.service(writer).snapshot()
            calculated, _, _ = self._world_stats_for(position, level=state.profile.level)
            percent = world_stats.self_info_fields(state.status_fields, calculated)[17]
            if state.status_fields[17] != percent:
                state.status_fields[17] = percent
                world._queue(uid, full_status_frame(state.status_fields))

    tick_entry = world.events.add('weight_projection', 'tick', refresh)

    def close():
        world.events.remove('tick', tick_entry)
        world.events.remove('close', close_entry)

    close_entry = world.events.add('weight_projection', 'close', close)


METHODS = (
    _world_stats_for,
    _world_fields_for,
    _world_pc_profile,
    _world_recalculate_uid,
    _world_refresh_pc,
    _world_weight_initialize,
)
HOOKS = {'stats_changed': ('_world_recalculate_uid',)}


def _world_equipment_initialize(self):
    self._world_equipment_pending = {}
    combat = self.world.combat

    def bind(base):
        def wrapped(uid, profile, status_fields):
            state = _resource_state(base(uid, profile, status_fields))
            combat.pcs[uid] = state
            pending = self._world_equipment_pending.pop(uid, None)
            if pending is not None:
                hp, mp, calculated, con, wis = pending
                state.base_growth_con, state.base_growth_wis = con, wis
                project_resources(state, calculated, base=(hp, mp))
            return state
        return wrapped

    def regenerate(base):
        def wrapped(uid):
            state = combat.pcs.get(uid)
            calculated = None if state is None else getattr(state, 'equipment_calculated', None)
            if calculated is None or state.dead:
                return base(uid)
            hp, mp = state.hp, state.mp
            hp_due = state.hp_points + state.regen_state >= combat.regen.hp_threshold(state.profile.level)
            mp_due = state.mp_points + state.regen_state >= combat.regen.mp_threshold
            frame = base(uid)
            # Preserve the existing timer/base regen policy and add worn options.
            if hp_due and hp < state.max_hp:
                state.hp = min(state.max_hp, max(0, hp + combat.regen.hp_amount(state.profile.con)
                    + calculated.hp_regen_bonus))
            if mp_due and mp is not None and mp < state.max_mp:
                state.status_fields[12] = min(state.max_mp, max(0, mp + combat.regen.mp_amount(state.profile.wis)
                    + calculated.mp_regen_bonus))
            if state.hp != hp or state.mp != mp:
                from tools.local_original_session.world_combat import status_frame
                return status_frame(state.status_fields, state.hp)
            return frame
        return wrapped

    self.world.runtime_extensions.wrap('equipment_stats', combat, 'bind_pc', bind)
    self.world.runtime_extensions.wrap('equipment_stats', combat, 'regen_tick', regenerate)

    def attack_bonus(uid, profile, now, *, ranged=False):
        state = combat.pcs.get(uid)
        calculated = None if state is None else getattr(state, 'equipment_calculated', None)
        if calculated is None:
            return profile
        mode = 'ranged' if ranged else 'melee'
        return replace(profile, weapon=replace(profile.weapon,
            hit=profile.weapon.hit + getattr(calculated, 'equipment_' + mode + '_hit'),
            damage=profile.weapon.damage + getattr(calculated, 'equipment_' + mode + '_damage')))

    combat.profile_modifiers.append(attack_bonus)


METHODS += (_world_equipment_initialize,)
HOOKS['initialize'] = ('_world_equipment_initialize', '_world_weight_initialize')


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
