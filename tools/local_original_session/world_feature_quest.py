"""run403 legacy menus and durable, attributed LOCAL Jem quest policy.

QuestStore owns the inventory/progression/quest forward transaction. run405
does not connect the 05xx progress messages to these menus, so none are emitted.
ItemInfo and full status use the existing kit/status codecs after saving.
"""
from __future__ import annotations

from dataclasses import replace

from tools.local_original_session.world_bridge import need


def setup_quests(self, town):
    from tools.local_original_session import world_quest
    from tools.local_original_session.world_town_services import ServiceMenuSource
    self._world_quests = {q.quest_id: q for q in world_quest.load_quests()}
    self._world_quest_dialogues = {d.npc_id: d for d in world_quest.load_quest_dialogues()}
    self._world_quest_reward_items = world_quest.load_reward_items()
    self._world_quest_item_policies = world_quest.load_inventory_policies()
    return tuple(ServiceMenuSource(key, dialogue.initial, dialogue.pages)
        for key, npc in town.data.placements.items()
        if (dialogue := self._world_quest_dialogues.get(npc.npc_id)) is not None
        and npc.spawn['count'] > 0)


def _world_quest_initialize(self):
    from tools.local_original_session import inventory, world_quest_store
    self._world_quest_store = None
    if (getattr(self, '_inventory_store', None) is not None
            and getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY):
        self._world_quest_store = world_quest_store.QuestStore(self._inventory_store, self._world_progress)


def _quest_class(pc):
    value = {0: 'royal', 1: 'knight', 2: 'elf', 3: 'wizard'}.get(pc.profile.character_class)
    need(value is not None, 'QUEST_CLASS_UNSUPPORTED')
    return value


def _quest_menu(ctx, menu, fields, stem):
    from tools.local_original_session.world_handlers import Dialogue
    next_menu = Dialogue({1: fields[1], 2: stem.encode('utf-8')}, menu.source)
    wire = ctx.wire.dialogue_frame(next_menu.fields)
    menu.source.retired = False
    menu.source.delivered = False
    ctx.pending.append(menu.source)
    ctx.state.menu, ctx.state.window = next_menu, None
    ctx.send_frame(wire)


def _quest_inventory(self, uid):
    """Current owned kit rows; equipped materials never qualify for turn-in."""
    from tools.local_original_session import inventory
    need(getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY,
         'QUEST_KIT_INVENTORY_REQUIRED')
    items = inventory.validate_kit_frame(self.inventory_frame)
    effect = getattr(self, '_item_equipment_effect', None)
    equipment = None if effect is None else effect.store.restore(uid, self.inventory_frame)
    worn = (set() if equipment is None else
            {equipment.weapon_uid, *(identifier for _, identifier in equipment.slots)} - {0})
    counts = {}
    for item in items:
        if item.identifier not in worn:
            counts[item.template_bits] = counts.get(item.template_bits, 0) + dict(item.raw_fields)[4]
    return items, worn, counts


def _quest_inventory_change(self, ctx, result, items, worn):
    """Use the existing plain kit producer, UID rule and quantity/remove codecs."""
    from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
    rows = [dict(item.raw_fields) for item in items]
    before = {row[1]: dict(row) for row in rows}
    for material in result.consumed:
        remaining = material.count
        for row in rows:
            if row[1] not in worn and row[2] & 0xffffffff == material.item_id:
                taken = min(remaining, row[4])
                row[4] -= taken
                remaining -= taken
        need(remaining == 0, 'QUEST_CURRENT_MATERIALS_REQUIRED')
    rows = [row for row in rows if row[4] > 0]
    allocated = set(before)
    for reward in result.rewards:
        policy = self._world_quest_reward_items.get(reward.item_id)
        need(policy is not None, 'QUEST_REWARD_ITEM_SOURCE_REQUIRED')
        prototype, stackable = policy
        held = next((row for row in rows if row[2] & 0xffffffff == reward.item_id
            and all(row.get(n) == value for n, value in prototype.items() if n not in (1, 4))), None)
        if stackable and held is not None:
            held[4] += reward.count
            need(held[4] <= 2_000_000_000, 'QUEST_REWARD_STACK_LIMIT')
            continue
        for count in ((reward.count,) if stackable else (1,) * reward.count):
            need(len(rows) < inventory.KIT_MAX_ITEMS, 'QUEST_INVENTORY_FULL')
            identifier = (max(allocated, default=0) + 1 if ctx.bindings.allocate_uid is None
                          else ctx.bindings.allocate_uid(ctx))
            need(type(identifier) is int and 0 < identifier < 1 << 32 and identifier not in allocated,
                 'QUEST_FRESH_ITEM_UID_REQUIRED')
            allocated.add(identifier)
            rows.append({**prototype, 1: identifier, 4: count})
    need(rows, 'QUEST_EMPTY_INVENTORY_UNSUPPORTED')
    updated = inventory.build_kit_frame(rows)
    after = {row[1]: row for row in rows}
    frames = []
    for identifier, previous in before.items():
        current = after.get(identifier)
        if current is None:
            frames.append(item_transfer_protocol._remove_frame(item_transfer_protocol.RemoveInventory(identifier)))
        elif current[4] != previous[4]:
            frames.append(inventory_update._encode(inventory_update._values({1: identifier, 4: current[4]})))
    frames.extend(inventory.build_add(row) for row in rows if row[1] not in before)
    return updated, tuple(frames)


def _quest_progress(self, uid, definition, pc):
    """Reuse M1 EXP/growth policy without dispatching a kill or creating drops."""
    from tools.local_original_session import world_progress, world_reward
    saved = self._world_progress.get(uid)
    current_exp = self._world.exp[uid]
    lawful = getattr(self, '_world_lawful', {}).get(uid, saved.lawful)
    proposed = world_progress.Progress(current_exp, pc.profile.level, pc.max_hp, pc.max_mp, lawful)
    if definition.experience_reward:
        # Existing exp-only carrier convention, pure calculation DATA only.
        carrier = replace(next(iter(self._world.data.monsters.values())),
                          template_id=-1, kill_exp=definition.experience_reward)
        growth = world_reward.on_kill(world_reward.RewardPcState.from_combat(pc, exp=current_exp),
            carrier, self._world.combat.rng, data=self._world.data)
        proposed = world_progress.Progress(growth.new_exp, growth.new_level,
                                           growth.max_hp, growth.max_mp, lawful)
    return saved, proposed


def _world_quest_action(self, ctx, interaction, menu, fields, now):
    from tools.local_original_session import world_quest, world_progress, world_status_frames
    dialogue = self._world_quest_dialogues.get(interaction.npc.npc_id)
    if dialogue is None:
        return False
    stem, action = menu.fields[2].decode('utf-8'), fields[2].decode('utf-8')
    need(action in dialogue.pages.get(stem, ()), 'QUEST_ACTION_NOT_LISTED')
    store = self._world_quest_store
    need(store is not None, 'QUEST_KIT_STORE_REQUIRED')
    pc, uid = self._world.combat.pcs[ctx.pc_uid], ctx.pc_uid
    need(not pc.dead and pc.hp > 0, 'QUEST_LIVING_PC_REQUIRED')
    class_key = _quest_class(pc)
    refs = store.reference_steps(uid, class_key)
    if action == 'queststart':
        route = dialogue.starts.get(stem)
        need(route is not None, 'QUEST_GUNTER_ZERO_PREREQUISITE_UNKNOWN')
        quest_id, next_stem = route
        state = store.get(uid, quest_id)
        # LOCAL re-selection uses only the existing second-phase pages/actions.
        if state.completed:
            if quest_id == 'ti_jem_cursed_spellbook':
                book = store.get(uid, 'ti_jem_book_of_magic')
                next_stem = 'jem10' if book.completed else 'jem4' if book.accepted else 'jem9'
            else:
                next_stem = self._world_quests[quest_id].result_stem
            _quest_menu(ctx, menu, fields, next_stem)
            return True
        definition = self._world_quests[quest_id]
        local_refs = dict(refs)
        if definition.required_reference_step is not None:
            # Fresh LOCAL class quest starts at0 (L1Quest.get_step). Persist it
            # with acceptance; never derive it from cookie or menu f1.
            name, _ = definition.required_reference_step
            local_refs.setdefault(name, 0)
        result = world_quest.accept_quest(definition, state, class_key=class_key,
            level=pc.profile.level, reference_steps=local_refs)
        need(result.reason in ('accepted', 'already_accepted'), 'QUEST_' + result.reason.upper())
        _, _, counts = _quest_inventory(self, uid)
        progress = world_quest.evaluate_quest(definition, result.state, counts)
        accepted = replace(result.state, counts=progress.counts)
        if accepted != state or local_refs != refs:
            ctx.commit_attempted = True
            menu.source.retired = True
            store.commit(uid, state, accepted, class_key=class_key,
                         reference_before=refs, reference_after=local_refs)
        _quest_menu(ctx, menu, fields, next_stem)
        return True
    need(action == 'questcomplete' and stem in dialogue.completions,
         'QUEST_COMPLETION_MENU_REQUIRED')
    # run403 dedicated sender produces one opaque DF660 AL byte, not quest ID.
    need(3 not in fields or len(fields[3]) == 1, 'QUEST_COMPLETE_NATIVE_COOKIE_BYTE_REQUIRED')
    definition = self._world_quests[dialogue.completions[stem]]
    state = store.get(uid, definition.quest_id)
    items, worn, counts = _quest_inventory(self, uid)
    result = world_quest.complete_quest(definition, state, counts,
        npc_key=f'l1j:{interaction.npc.npc_id}', action=action,
        policy='l1j_local', reference_steps=refs)
    need(result.reason == 'completion_proposed', 'QUEST_' + result.reason.upper())
    updated, frames = _quest_inventory_change(self, ctx, result, items, worn)
    equipment_change = {}
    effect = getattr(self, '_item_equipment_effect', None)
    equipment_after = None
    if effect is not None:
        from tools.local_original_session import inventory
        equipment = effect.store.restore(uid, self.inventory_frame)
        after_items = inventory.validate_kit_frame(updated)
        if equipment is not None and not any(item.identifier == equipment.item_uid for item in after_items):
            first = after_items[0]
            equipment_after = replace(equipment, item_uid=first.identifier,
                                      template=first.template_bits, revision=equipment.revision + 1)
            equipment_change = dict(equipment_store=effect.store,
                equipment_before=equipment, equipment_after=equipment_after)
    # Settle older kill progress before opening the turn-in intent. A failed
    # quest save must not let leave/close write an older dirty projection over
    # a partly committed EXP reward. Failed settlement retains the dirty value.
    dirty = self._world.progress_dirty.get(uid)
    if dirty is not None:
        ctx.commit_attempted = True
        menu.source.retired = True
        self._world_progress.commit(uid, replace(dirty,
            lawful=getattr(self, '_world_lawful', {}).get(uid, dirty.lawful)))
        self._world.progress_dirty.pop(uid, None)
    progress_before, progress_after = _quest_progress(self, uid, definition, pc)
    next_refs = dict(refs)
    if definition.completed_reference_step is not None:
        name, step = definition.completed_reference_step
        next_refs[name] = step
    status = None
    if definition.experience_reward:
        values = dict(pc.status_fields)
        values.update({2: progress_after.level, 11: progress_after.max_hp,
                       26: world_progress.exp_percent(self._world.data, progress_after.exp,
                                                      progress_after.level)})
        if progress_after.max_mp is not None:
            values[13] = progress_after.max_mp
        status = world_status_frames.full_status_frame(values)
    older = tuple(self._world.drain(uid))
    ctx.commit_attempted = True
    menu.source.retired = True
    store.commit(uid, state, result.state, class_key=class_key,
        reference_before=refs, reference_after=next_refs,
        inventory_before=self.inventory_frame, inventory_after=updated,
        progress_before=progress_before, progress_after=progress_after, **equipment_change)
    self.inventory_frame = updated
    if equipment_after is not None and effect._selection is not None:
        effect._selection['state'] = equipment_after
    self._world.exp[uid] = progress_after.exp
    self._world.progress_dirty.pop(uid, None)
    if status is not None:
        pc.profile = replace(pc.profile, level=progress_after.level)
        pc.max_hp = progress_after.max_hp
        pc.status_fields.update(values)
        if getattr(self._world, 'on_stats_changed', None) is not None:
            self._world.on_stats_changed(uid)
        status = world_status_frames.full_status_frame(pc.status_fields)
    for wire in (*older, *frames, *((status,) if status is not None else ())):
        ctx.send_frame(wire)
    # LOCAL response order, not an assertion of official quest reward ordering.
    _quest_menu(ctx, menu, fields, definition.result_stem)
    return True


async def _world_quest_after_request(self, writer, row, game, opcode, operation_lock):
    """Persist collection progress from the actual current kit after mutations."""
    if getattr(self, '_world_quest_store', None) is None or not self._world_bound(writer):
        return
    def synchronize():
        from tools.local_original_session import world_quest
        uid = self._world_pcs[id(writer)][1]
        pc = self._world.combat.pcs[uid]
        class_key = _quest_class(pc)
        store = self._world_quest_store
        active = [(definition, store.get(uid, definition.quest_id))
                  for definition in self._world_quests.values()]
        active = [(d, s) for d, s in active if s.accepted and not s.completed]
        if not active:
            return
        _, _, counts = _quest_inventory(self, uid)
        refs = store.reference_steps(uid, class_key)
        for definition, state in active:
            observed = world_quest.evaluate_quest(definition, state, counts).counts
            if observed != state.counts:
                store.commit(uid, state, replace(state, counts=observed), class_key=class_key,
                             reference_before=refs, reference_after=refs)
    await self._world.runtime.dispatch_now(synchronize)


METHODS = (_world_quest_action, _world_quest_initialize, _world_quest_after_request)
HOOKS = {'initialize': ('_world_quest_initialize',),
         'after_request': ('_world_quest_after_request',)}
FRAMES = {}
