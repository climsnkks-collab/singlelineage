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
    self._world_quest_runtime = world_quest.load_runtime()
    if town is None:
        return ()
    return tuple(ServiceMenuSource(key, dialogue.initial, dialogue.pages)
        for key, npc in town.data.placements.items()
        if (dialogue := self._world_quest_dialogues.get(npc.npc_id)) is not None
        and npc.spawn['count'] > 0)


def _world_quest_initialize(self):
    from tools.local_original_session import inventory, world_quest_store
    if not hasattr(self, '_world_quests'):
        setup_quests(self, None)
    self._world_quest_store = None
    from uuid import uuid4
    self._world_quest_event_epoch = uuid4().hex
    self._world_quest_errors = []
    if (getattr(self, '_inventory_store', None) is not None
            and getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY):
        self._world_quest_store = world_quest_store.QuestStore(self.inventory_store, self.progress_store)
    _quest_runtime_data(self)


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


def _quest_inventory_change(self, ctx, result, items, worn, *, issue=False):
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
        held = None if issue else next((row for row in rows if row[2] & 0xffffffff == reward.item_id
            and (reward.item_id == 7 or all(row.get(n) == value for n, value in prototype.items()
                                           if n not in (1, 4)))), None)
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
    saved = self.progress_store.get(uid)
    current_exp = self._world.exp[uid]
    lawful = self.world.progress.lawful_of(uid, saved.lawful)
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


def _quest_jim_admitted(pc, refs, sprite):
    # L1MerchantInstance.java:372-383. The core actor projection supplies the
    # current gfx; transformation scheduling/lifetime remains its owner's job.
    return (_quest_class(pc) == 'knight' and refs.get('Level30') == 6
            and type(sprite) is int and sprite == 2374)


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
    completed = frozenset(qid for qid in self._world_quests if store.get(uid, qid).completed)
    if interaction.npc.npc_id == 70555:
        position = self.realm.service(ctx.writer).snapshot()
        need(position.uid == uid, 'QUEST_CURRENT_ACTOR_REQUIRED')
        sprite = self.realm._actor_for(position).get(3)
        need(_quest_jim_admitted(pc, refs, sprite), 'QUEST_JIM_SKELETON_AND_STEP_REQUIRED')
    # UML page links preserve their source names. They do not accept a quest,
    # issue materials, or advance a shared step.
    if (interaction.npc.npc_id in (70522, 70794, 70555, 70805)
            and action not in ('queststart', 'questcomplete') and action in dialogue.pages):
        _quest_menu(ctx, menu, fields, action)
        return True
    # Classic's link and completion button are real source actions; the saved
    # contract selection below is an explicit LOCAL menu policy.
    if interaction.npc.npc_id == 70811 and stem == 'lyraEv5':
        definition = self._world_quests['mainland_lyra_totem_settlement']
        state = store.get(uid, definition.quest_id)
        need(state.completed and not state.closed, 'QUEST_SETTLED_CONTRACT_REQUIRED')
        if action == 'lyraEv8':
            result = world_quest.accept_quest(definition, state, class_key=class_key,
                level=pc.profile.level, completed_quests=completed)
            need(result.reason == 'accepted', 'QUEST_' + result.reason.upper())
            after, next_stem = result.state, 'lyraEv8'
        else:
            need(action == 'questcomplete', 'QUEST_CONTRACT_ACTION_REQUIRED')
            after, next_stem = replace(state, closed=True), 'lyraEv7'
        ctx.commit_attempted = True
        menu.source.retired = True
        store.commit(uid, state, after, class_key=class_key,
                     reference_before=refs, reference_after=refs)
        _quest_menu(ctx, menu, fields, next_stem)
        return True
    if action == 'queststart':
        route = dialogue.starts.get(stem)
        need(route is not None, 'QUEST_GUNTER_ZERO_PREREQUISITE_UNKNOWN')
        quest_id, next_stem = route
        state = store.get(uid, quest_id)
        definition = self._world_quests[quest_id]
        if definition.settlement_prices and (state.accepted and not state.completed):
            _quest_menu(ctx, menu, fields, 'lyraEv4')
            return True
        if definition.settlement_prices and state.completed and not state.closed:
            _quest_menu(ctx, menu, fields, 'lyraEv5')
            return True
        # LOCAL re-selection uses only the existing second-phase pages/actions.
        if state.completed and not definition.renewable:
            if interaction.npc.npc_id == 70775:
                next_stem = 'mark4'
            elif quest_id == 'ti_jem_cursed_spellbook':
                book = store.get(uid, 'ti_jem_book_of_magic')
                next_stem = 'jem10' if book.completed else 'jem4' if book.accepted else 'jem9'
            else:
                next_stem = self._world_quests[quest_id].result_stem
            _quest_menu(ctx, menu, fields, next_stem)
            return True
        local_refs = dict(refs)
        if definition.required_reference_step is not None:
            # Fresh LOCAL class quest starts at0 (L1Quest.get_step). Persist it
            # with acceptance; never derive it from cookie or menu f1.
            name, _ = definition.required_reference_step
            local_refs.setdefault(name, 0)
        result = world_quest.accept_quest(definition, state, class_key=class_key,
            level=pc.profile.level, reference_steps=local_refs, completed_quests=completed)
        need(result.reason in ('accepted', 'already_accepted'), 'QUEST_' + result.reason.upper())
        items, worn, counts = _quest_inventory(self, uid)
        progress = world_quest.evaluate_quest(definition, result.state, counts)
        accepted = replace(result.state, counts=progress.counts)
        if result.reason == 'accepted' and definition.accepted_reference_step is not None:
            name, step = definition.accepted_reference_step
            local_refs[name] = step
        issuance = {}
        frames = ()
        if result.reason == 'accepted' and result.rewards:
            updated, frames = _quest_inventory_change(self, ctx, result, items, worn, issue=True)
            from tools.local_original_session import inventory
            old_uids = {item.identifier for item in items}
            issued = tuple((item.identifier, item.template_bits, dict(item.raw_fields)[4])
                           for item in inventory.validate_kit_frame(updated)
                           if item.identifier not in old_uids)
            accepted = replace(accepted, issued=issued)
            issuance = dict(inventory_before=self.inventory_frame, inventory_after=updated)
        if accepted != state or local_refs != refs:
            ctx.commit_attempted = True
            menu.source.retired = True
            store.commit(uid, state, accepted, class_key=class_key,
                         reference_before=refs, reference_after=local_refs, **issuance)
            if issuance:
                self.inventory_frame = updated
        for wire in frames:
            ctx.send_frame(wire)
        _quest_menu(ctx, menu, fields, next_stem)
        return True
    need(stem in dialogue.completions,
         'QUEST_COMPLETION_MENU_REQUIRED')
    # DF660 parses decimal with strtol; 5C5950 sends its AL as one byte.
    # Only a source-backed choice quest interprets that byte as a selection.
    need(3 not in fields or len(fields[3]) == 1, 'QUEST_COMPLETE_NATIVE_COOKIE_BYTE_REQUIRED')
    definition = self._world_quests[dialogue.completions[stem]]
    choice = None
    if definition.choice_rewards:
        cookie = fields.get(3)
        need(type(cookie) is bytes and len(cookie) == 1
             and cookie[0] in dict(definition.choice_rewards), 'QUEST_REWARD_CHOICE_REQUIRED')
        choice = cookie[0]
    state = store.get(uid, definition.quest_id)
    items, worn, counts = _quest_inventory(self, uid)
    if any(objective.kind == 'deliver' for objective in definition.objectives):
        current = {item.identifier: item for item in items if item.identifier not in worn}
        need(bool(state.issued) and all(identifier in current
            and current[identifier].template_bits == template
            and dict(current[identifier].raw_fields)[4] == quantity
            for identifier, template, quantity in state.issued), 'QUEST_ISSUED_DELIVERY_REQUIRED')
        # Delivery is the original issued UID, never another equal-template row.
        counts = {template: sum(n for _, t, n in state.issued if t == template)
                  for _, template, _ in state.issued}
    result = world_quest.complete_quest(definition, state, counts,
        npc_key=f'l1j:{interaction.npc.npc_id}', action=action,
        policy='l1j_local', reference_steps=refs, completed_quests=completed,
        completion_choice=choice)
    if definition.settlement_prices and result.reason == 'requirements_missing':
        _quest_menu(ctx, menu, fields, 'lyraEv6')
        return True
    need(result.reason == 'completion_proposed', 'QUEST_' + result.reason.upper())
    if state.issued:
        issued_uids = {identifier for identifier, _, _ in state.issued}
        # Stable order makes the existing consumer select issued rows first.
        items = tuple(sorted(items, key=lambda item: item.identifier not in issued_uids))
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
    dirty = self.world.progress.pending(uid)
    if dirty is not None:
        ctx.commit_attempted = True
        menu.source.retired = True
        self.progress_store.commit(uid, dirty)
        self.world.progress.ack(uid, dirty)
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
    self.world.progress.adopt(uid, progress_after, dirty=False)
    self.world.progress.clear(uid)
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


def _world_quest_menu_sources(self, town):
    return setup_quests(self, town)


def _world_quest_policies(self):
    if not hasattr(self, '_world_quests'):
        setup_quests(self, None)
    return self._world_quest_item_policies


def _quest_runtime_data(self):
    """Contribute sourced item/drop data through the shared catalog owner."""
    from types import MappingProxyType
    from tools.local_original_session import game_data
    world = self.world
    if not hasattr(world, 'replace_data'):
        return  # Arithmetic-only test fixtures do not own a playable world.
    runtime = self._world_quest_runtime
    base = world.data
    items, drops = dict(base.items), dict(base.drops)
    for row in runtime.get('items', ()):
        sources = MappingProxyType({'identity': game_data.Source('client', row['source']),
            'stackable': game_data.Source('l1j', row['stackable_source'])})
        items.setdefault(row['item_id'], replace(base.items[7], template_id=row['item_id'],
            name_token=row['name_token'], name_ko=row['name_ko'], kind='quest',
            stackable=row['stackable'], icon=row['icon'], weight=row['raw_weight'], sources=sources))
    for row in runtime.get('drops', ()):
        if row['template_id'] not in base.monsters:
            continue
        previous = drops.get(row['template_id'], ())
        if any(drop.item_id == row['item_id'] for drop in previous):
            continue
        item = items[row['item_id']]
        source = MappingProxyType({'identity': game_data.Source(row.get('identity_source_kind', 'official'), row['identity_source']),
                                  'roll': game_data.Source('l1j', row['roll_source'])})
        drops[row['template_id']] = previous + (game_data.DropDef(row['item_id'], item.name_token,
            item.name_ko, 1, row['chance'], row['min_count'], row['max_count'], source),)
    world.replace_data(replace(base, items=MappingProxyType(items), drops=MappingProxyType(drops)))


def _world_quest_town_setup(self, setup):
    """Add the sourced Lyra placement without replacing another town subclass."""
    from types import MappingProxyType
    from tools.local_original_session import world_town
    from tools.local_original_session.world_town_services import ServiceMenuSource
    if getattr(self, '_world_map_exp', 0) != 2:
        return setup
    if not hasattr(self, '_world_quests'):
        setup_quests(self, None)
    town = setup.town
    additions = {}
    sources = list(setup.sources)
    for row in self._world_quest_runtime.get('town_npcs', ()):
        spawn = world_town._freeze(row['spawn'])
        npc_id = row['l1j_npc_id']
        key = (npc_id, spawn['id'])
        additions[key] = world_town.TownNpc(key, 'village', world_town._freeze(row), spawn)
        # This feature owns the promoted quest menu for this exact placement.
        # Earlier town providers may already supply its ordinary lore page;
        # replace that source while retaining every unrelated placement.
        sources = [source for source in sources if source.placement_key != key]
        dialogue = self._world_quest_dialogues[npc_id]
        sources.append(ServiceMenuSource(key, dialogue.initial, dialogue.pages))
    if additions:
        town.data = replace(town.data,
            placements=MappingProxyType(dict(town.data.placements) | additions))
        town.register(replace(town.config,
            candidate_npc_ids=town.config.candidate_npc_ids | frozenset(k[0] for k in additions)))
    return replace(setup, sources=tuple(sources))


def _world_quest_after_kill(self, event):
    """Only the core committed-kill hook supplies these progress events."""
    from tools.local_original_session import world_quest
    store = getattr(self, '_world_quest_store', None)
    pc = self.world.combat.pcs.get(event.pc_uid)
    if store is None or pc is None:
        return
    refs = store.reference_steps(event.pc_uid, _quest_class(pc))
    committed = world_quest.QuestEvent('kill', event.template_id,
        f'{self._world_quest_event_epoch}:{event.npc_uid}:{event.at!r}')
    for definition in self._world_quests.values():
        if not any(o.kind == 'kill' and o.key == event.template_id for o in definition.objectives):
            continue
        state = store.get(event.pc_uid, definition.quest_id)
        result = world_quest.on_event(definition, state, committed, {})
        if result.state != state:
            try:
                store.commit(event.pc_uid, state, result.state, class_key=_quest_class(pc),
                             reference_before=refs, reference_after=refs)
            except (ValueError, OSError) as error:
                # Keep the failed intent and let the already-committed kill's
                # existing EXP/drop path finish; recovery belongs to startup.
                self._world_quest_errors = (self._world_quest_errors + [str(error)])[-8:]
                break


def _world_quest_report(self, result):
    result['quest_errors'] = list(self._world_quest_errors)


METHODS = (_world_quest_action, _world_quest_initialize, _world_quest_after_request,
           _world_quest_menu_sources, _world_quest_policies, _world_quest_town_setup,
           _world_quest_after_kill, _world_quest_report)
HOOKS = {'initialize': ('_world_quest_initialize',),
         'menu_sources': ('_world_quest_menu_sources',),
         'item_policies': ('_world_quest_policies',),
         'service_action': ('_world_quest_action',),
         'after_request': ('_world_quest_after_request',),
         'after_kill': ('_world_quest_after_kill',),
         'town_setup': ('_world_quest_town_setup',),
         'report': ('_world_quest_report',)}
FRAMES = {}

HOOK_PRIORITY = {'service_action': 0, 'town_setup': 30, 'initialize': 50}
NONCRITICAL_HOOKS = ('report',)
SAVE_BOUNDARIES = {'_world_quest_action': True}
