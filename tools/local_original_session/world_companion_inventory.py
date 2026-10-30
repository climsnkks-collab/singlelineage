"""run406 4EF5 GIVE to an owned Player companion; explicit equipment only.

The two character rows remain ordinary inventory/equipment saves. A short-lived
intent uses the existing warehouse atomic writer solely to finish interrupted
two-row transfers forward. It is not a second bag or an exchange UI protocol.
The bridge bag/equipment windows reuse the same owner: take (member -> owner,
the reverse of give, debit before credit), explicit equip/unequip, and the
member's own speed-potion effects, all on the ordinary saved character rows.
"""
from dataclasses import replace
import json
from pathlib import Path
import struct
import time

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, equipment_store, world_weight
from tools.local_original_session.world_bridge import need
from tools.local_original_session.inventory_store import compatible_stack, repaired_adena_frame


class CompanionInventory:
    def __init__(self, ctx, *, characters, policy, save, owned_actor, report_error):
        self.characters, self.policy, self.save = characters, policy, save
        self.owned_actor, self.report_error = owned_actor, report_error
        self.ctx = ctx
        self.store = ctx.inventory_store
        self.equipment = equipment_store.EquipmentStore(self.store,
            policy=equipment_store.POLICY, kit_policy=inventory.KIT_POLICY,
            item_defs=ctx.world.data.items)
        self.intent_path = Path(self.store.path).with_name('companion-transfer.json')
        self.frames = {}
        self.states = {}
        self.weights = world_weight.load_weight_catalog()
        # Exact native1298 / official492 mapping, absent from the M1 subset.
        self.weights = dict(self.weights)
        from tools.local_original_session.game_data import Source
        blue = replace(ctx.world.data.items[14], template_id=492, name_token='$232',
            name_ko='파란 물약', icon=75, weight=7000, heal_hp=0, heal_hp_range=None)
        self.weights[492] = world_weight.ItemWeight(blue, 7000,
            Source('client', 'native-dump-v1.jsonl:1298; official raw/item/492.json weight7'))
        self.blue_until = {}  # real-time effect; no offline recovery or refill
        self.speed = {}  # uid -> {kind: (expires, rate)} speed potion effects
        from tools.local_original_session.world_item_effects import load_effects
        self.item_effects = load_effects()
        self.next_potion = {}
        self.policy_for = None  # optional callable(record) -> LOCAL ATS AI policy
        self.events = []
        self.commit_started = False
        self.recovered = None
        if self.intent_path.exists():
            intent = json.loads(self.intent_path.read_text(encoding='utf-8'))
            self._finish(intent)
            owner = intent.get('owner_uid', intent['rows'][0]['uid'])
            source = next(row for row in intent['rows'] if row['uid'] == owner)
            if ctx.inventory_frame == bytes.fromhex(source['before']):
                ctx.inventory_frame = bytes.fromhex(source['after'])
            self.recovered = intent
            # Both durable rows now equal their after-images. Retire the
            # finished intent before load repair can change either preimage.
            self.intent_path.unlink()

    def _finish(self, intent):
        for row in intent['rows']:
            uid = row['uid']
            before, after = bytes.fromhex(row['before']), bytes.fromhex(row['after'])
            current = self.store.restore(uid)
            need(current in (before, after), 'COMPANION_TRANSFER_RECOVERY_CONFLICT')
            if current != after:
                self.store.replace_kit(uid, before, after, append=True)

    def install_pickup(self):
        """Extend ground admission only for this service's current followers."""
        view = self.ctx.world
        def wrapper(base):
            def check(ref, item_ref, count, *, now=None):
                actor = view.companions.get_actor(ref.uid)
                if actor is None:
                    return base(ref, item_ref, count, now=now)
                now = view.ground._now(now)
                entity = view.entities.resolve(ref)
                owner = view.entities.resolve(actor.owner_ref)
                need(actor.ref == ref and entity is not None and entity.alive
                     and view.companions.can_be_attacked(ref.uid)
                     and owner is not None and owner.alive and owner.uid in view.pcs
                     and view.combat.can_be_attacked(owner.uid)
                     and actor.character_id not in view.pcs, 'COMPANION_PICKUP_CURRENT_LIFE_REQUIRED')
                item = view.ground.get(item_ref)
                need(item is not None, 'GROUND_ITEM_NOT_FOUND')
                need(now < item.expires_at, 'GROUND_ITEM_EXPIRED')
                need(entity.map_id == owner.map_id == item.map_id
                     and max(abs(entity.x-item.x), abs(entity.y-item.y)) <= 1,
                     'GROUND_PICKUP_TOO_FAR')
                need(now >= item.owner_until or item.owner_uid == owner.uid, 'GROUND_OWNER_PRIORITY')
                need(type(count) is int and 0 < count <= min(item.count, 2_000_000_000)
                     and (item.stackable or count == 1), 'GROUND_COUNT_INVALID')
                return item
            return check
        self.pickup_handle = view.runtime_extensions.wrap('companion-pickup', view.ground,
                                                         'check_pickup', wrapper)

    def request_pickup(self, actor, now):
        view = self.ctx.world
        entity = view.entities.resolve(actor.ref)
        need(entity is not None and view.companions.can_be_attacked(actor.ref.uid),
             'COMPANION_LIVING_ACTOR_REQUIRED')
        # LOCAL: companion-centered 1-cell snapshot, one success per signal.
        actor.pickup_refs = tuple(other.ref for other in view.entities.near(
            entity.map_id, entity.x, entity.y, 1) if other.kind.value == 'item'
            and (item := view.ground.get(other.ref)) is not None
            and now < item.expires_at
            and (now >= item.owner_until or item.owner_uid == actor.owner_ref.uid))
        actor.pickup_until = now + 10
        view.companion_ai.start(actor.ref, now + view.runtime.tick_interval)
        return len(actor.pickup_refs)

    def pickup_step(self, actor, entity, now):
        if not actor.pickup_refs:
            return False
        if now >= actor.pickup_until:
            actor.pickup_refs = ()
            return False
        view = self.ctx.world
        while actor.pickup_refs:
            item = view.ground.get(actor.pickup_refs[0])
            if item is None:
                actor.pickup_refs = actor.pickup_refs[1:]
                continue
            occupied = any(other.kind.value != 'item' and other.uid != entity.uid
                for other in view.entities.near(item.map_id, item.x, item.y, 0, alive_only=False))
            if ((entity.x, entity.y) != (item.x, item.y) and not occupied
                    and actor.record.movement_mode != 'HOLD'):
                actor.action = 'PICKUP'
                view.companion_ai._move(actor, entity, lambda x, y: (x, y) == (item.x, item.y),
                                       (item.x, item.y), now)
                return True
            try:
                actor.pickup_refs = ()  # uncertain saved credit must never auto-retry
                self.pickup(actor, item, now)
            except ValueError as error:
                self.events.append(dict(event='pickup_refused', member=actor.character_id,
                                        ground=item.ref.uid, error=str(error)))
                del self.events[:-32]
            actor.pickup_refs = ()
            return True
        return False

    def pickup(self, actor, item, now):
        """Existing bag CAS before existing ground consume, under world lock."""
        ctx, uid = self.ctx, actor.character_id
        ctx.world.ground.check_pickup(actor.ref, item.ref, item.count, now=now)
        need(not self.intent_path.exists(), 'COMPANION_TRANSFER_RECOVERY_REQUIRED')
        definition = ctx.world.data.items.get(item.item_id)
        need(definition is not None, 'COMPANION_PICKUP_KNOWN_ITEM_REQUIRED')
        before = self.frames[uid]
        rows = [dict(row.raw_fields) for row in inventory.validate_kit_frame(before)]
        fields = dict(item.inventory_fields)
        if not fields:
            fields = dict(ctx.starter_fields)
            fields.update({2: item.item_id, 7: definition.icon, 18: b''})
            fields = ctx.fold_sync_hooks('pickup_item_fields', fields, item)
        fields[4] = item.count
        need(item.grade == 1 or fields[18] != b'', 'COMPANION_PICKUP_GRADE_MAPPING_REQUIRED')
        held = next((r for r in rows if item.stackable and compatible_stack(r, fields)), None)
        if held is not None:
            held[4] += item.count
            need(held[4] <= 2_000_000_000, 'COMPANION_PICKUP_STACK_LIMIT')
        else:
            need(len(rows) < inventory.KIT_MAX_ITEMS, 'COMPANION_PICKUP_INVENTORY_FULL')
            used = {r[1] for r in rows}
            used.update(row.identifier for frame in (*self.frames.values(), ctx.inventory_frame)
                        for row in inventory.validate_kit_frame(frame))
            fields[1] = max(used, default=0) + 1
            rows.append(fields)
        after = inventory.build_kit_frame(rows)
        calculated, _ = self.calculated(uid, after)
        carried = world_weight.inventory_weight((r for r in inventory.validate_kit_frame(before)
            if dict(r.raw_fields)[4] > 0), self.weights)
        need(world_weight.can_add_weight(carried, self._raw_weight(item.item_id), item.count,
                                        calculated.max_weight), 'COMPANION_WEIGHT_CAPACITY')
        policy = None if self.policy_for is None else self.policy_for(actor.record)
        limit = None if policy is None else policy.get('pickup_weight')
        need(limit is None or calculated.weight.gauge * 100 <= limit * 240,
             'COMPANION_ATS_PICKUP_WEIGHT')
        def commit(_item, _count):
            from tools.local_original_session.world_ground_items import GroundCommitError
            try:
                need(self.store.commit_ground_kit(uid, before, after, append=True),
                     'COMPANION_PICKUP_PERSISTED_CHANGE_REQUIRED')
            except GroundCommitError as error:
                if error.outcome == 'COMMITTED':
                    self.frames[uid] = after
                raise
            self.frames[uid] = after
        ctx.world.ground.transfer_pickup(actor.ref, item.ref, item.count, commit, now=now)
        self.refresh(uid)
        self.save(actor.owner_ref.uid)
        self.events.append(dict(event='pickup', member=uid, ground=item.ref.uid,
                                template=item.item_id, count=item.count, grade=item.grade))
        del self.events[:-32]
        ctx.world._announce()

    def initialize(self, uid):
        ctx = self.ctx
        frame = self.store.restore(uid)
        if frame is None:
            fields = [dict(r.raw_fields) for r in inventory.validate_kit_frame(
                ctx._inventory_kit_frame(3))]
            # New character instances get their own UIDs; no parallel ledger.
            for index, row in enumerate(fields):
                row[1] = 0x20000000 + uid * inventory.KIT_MAX_ITEMS + index
            frame = inventory.build_kit_frame(fields)
            self.store.grant(uid, frame)
        state = self.equipment.restore(uid, frame)
        repaired = repaired_adena_frame(frame)
        if repaired != frame:
            replacement = equipment_store.after_removal(state, frame, repaired)
            if replacement is None:
                self.store.replace_kit(uid, frame, repaired)
            else:
                transactions = getattr(ctx, 'inventory_transactions', None)
                if transactions is None:
                    from tools.local_original_session.world_state_services import InventoryTransactions
                    transactions = InventoryTransactions(self.store)
                transactions.commit_inventory(uid, frame, repaired,
                    equipment_store=self.equipment, equipment_before=state, equipment_after=replacement)
                state = replacement
            frame = repaired
        if state is None:
            items = inventory.validate_kit_frame(frame)
            entries = ctx.world.data.starter.entries(3)
            worn = {entry.template_id for entry in entries if entry.equipped}
            state = self.equipment.initialize_kit(uid, frame,
                initialization=equipment_store.FIRST_ENABLE_EMPTY,
                weapon_uid=next((r.identifier for r in items if r.template_bits in worn
                    and ctx.world.data.items[r.template_bits].kind == 'weapon'), 0),
                slots=tuple((ctx.world.data.items[r.template_bits].slot_key, r.identifier)
                    for r in items if r.template_bits in worn
                    and ctx.world.data.items[r.template_bits].kind == 'armor'))
        self.frames[uid], self.states[uid] = frame, state
        expires = ctx.world.companions.records[uid].equipment.get('blue_expires_unix', 0)
        self.blue_until[uid] = ctx.world.runtime.clock() + max(0, min(600, expires - time.time()))
        now = ctx.world.runtime.clock()
        saved_speed = ctx.world.companions.records[uid].equipment.get('speed_expires_unix', {})
        self.speed[uid] = {kind: (now + max(0, min(1800, row[0] - time.time())), row[1])
                           for kind, row in (saved_speed.items() if isinstance(saved_speed, dict) else ())
                           if isinstance(row, list) and len(row) == 2 and row[0] > time.time()}
        self.refresh(uid, publish=False)
        if self.recovered is not None and uid in {row['uid'] for row in self.recovered['rows']}:
            if all(row['uid'] in self.frames or row['uid'] == self.recovered.get('owner_uid',
                   self.recovered['rows'][0]['uid']) for row in self.recovered['rows']):
                if self.intent_path.exists():
                    self.intent_path.unlink()
                self.recovered = None

    def calculated(self, uid, frame=None):
        """Same saved bag/eight slots/enchant/base calculation as a PC of its class."""
        from tools.local_original_session import world_enchant_inventory
        from tools.local_original_session.world_stats import (
            Attributes, CharacterStats, EquippedItem, WeightOptions, calculate_stats)
        record = self.ctx.world.companions.records[uid]
        definitions = self.ctx.world.data.items
        rows = inventory.validate_kit_frame(self.frames[uid] if frame is None else frame)
        state = self.states[uid]
        selected = {state.weapon_uid, *(item for _, item in state.slots)} - {0}
        worn = tuple(EquippedItem(definitions[row.template_bits],
            enchant=world_enchant_inventory.enchant_level(row, definitions[row.template_bits]))
            for row in rows if row.identifier in selected and dict(row.raw_fields)[4] > 0)
        carried = world_weight.inventory_weight(
            (row for row in rows if dict(row.raw_fields)[4] > 0), self.weights)
        base = CharacterStats(record.level, record.class_id,
                              Attributes(*self.characters[uid]['attributes']))
        return calculate_stats(base, worn, weight=WeightOptions(carried_weight=carried)), worn

    def refresh(self, uid, *, publish=True):
        from tools.local_original_session import world_combat
        ctx = self.ctx
        calculated, worn = self.calculated(uid)
        row = self.characters[uid]
        record = ctx.world.companions.records[uid]
        record.project_resources(calculated)
        ctx.world.companion_profiles[uid] = replace(world_combat.companion_profile(
            calculated, worn, row['gender']), character_class=record.class_id)
        by_uid = {r.identifier: r for r in inventory.validate_kit_frame(self.frames[uid])}
        weapon = by_uid.get(self.states[uid].weapon_uid)
        definition = None if weapon is None else ctx.world.data.items[weapon.template_bits]
        stance = ctx._world_stances.get('unarmed' if definition is None else definition.weapon_type, 0)
        look = ctx.world.companion_looks[uid]
        look['weapon_type'] = None if definition is None else definition.weapon_type
        old_stance, look['stance'] = look['stance'], stance
        actor = ctx.world.companions.active.get(uid)
        if publish and actor is not None and old_stance != stance:
            entity = ctx.world.entities.get(actor.ref.uid)
            body = pb.encode_uint32(1, entity.uid) + pb.encode_uint32(2, stance)
            wire = struct.pack('<HH', len(body) + 6, 0x4ed5) + body + b'\0\0'
            for watcher in ctx.world._watchers(entity):
                ctx.world._queue(watcher, wire)
            ctx.world._announce()

    def equip(self, uid, item_uid):
        """Same eight slots/CAS as PC. Explicit caller may toggle equipment."""
        items = inventory.validate_kit_frame(self.frames[uid])
        record = self.ctx.world.companions.records[uid]
        state = self.states[uid]
        key, current_uid, weapon_uid, slots, _ = equipment_store.kit_equip_plan(
            state, items, self.ctx.world.data.items, item_uid, record.class_id,
            class_error='COMPANION_CLASS_CANNOT_EQUIP')
        remove_blocked = getattr(self.ctx, 'chain_sync_hooks', None)
        need(not current_uid or remove_blocked is None or not remove_blocked(
            'equipment_remove_blocked', uid, current_uid, items),
            'ITEM_USE_CURSED_EQUIPMENT_CANNOT_REMOVE')
        self.states[uid] = self.equipment.compare_and_swap_kit(uid, self.frames[uid], state,
            weapon_uid=weapon_uid, slots=slots)
        self.refresh(uid)
        return True

    def give(self, owner_uid, actor, source_uid, count, before):
        ctx, uid = self.ctx, actor.character_id
        need(not self.intent_path.exists(), 'COMPANION_TRANSFER_RECOVERY_REQUIRED')
        items = inventory.validate_kit_frame(before)
        item = next((r for r in items if r.identifier == source_uid), None)
        need(item is not None and type(count) is int and 0 < count <= dict(item.raw_fields)[4],
             'COMPANION_GIVE_OWNED_QUANTITY_REQUIRED')
        state = self.equipment.restore(owner_uid, before)
        need(state is not None and source_uid not in {state.weapon_uid, *(v for _, v in state.slots)},
             'COMPANION_GIVE_UNEQUIP_FIRST')
        definition = ctx.world.data.items.get(item.template_bits)
        need(definition is not None or item.template_bits == 492, 'COMPANION_GIVE_KNOWN_ITEM_REQUIRED')
        need((definition is None or definition.stackable) or count == 1,
             'COMPANION_GIVE_NONSTACK_QUANTITY')
        target = self.frames[uid]
        carried = world_weight.inventory_weight((r for r in inventory.validate_kit_frame(target)
            if dict(r.raw_fields)[4]), self.weights)
        need(world_weight.can_add_weight(carried, self.weights[item.template_bits].raw_weight,
            count, self.calculated(uid)[0].max_weight), 'COMPANION_WEIGHT_CAPACITY')
        # Preserve exact per-instance metadata (including enchant/grade); merge
        # only stackables whose complete non-UID/count fields agree.
        incoming = dict(item.raw_fields)
        target_rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(target)]
        merged = next((r for r in target_rows if (definition is None or definition.stackable)
            and compatible_stack(r, incoming)), None)
        if merged is not None:
            merged[4] += count
            need(merged[4] <= 2_000_000_000, 'COMPANION_GIVE_STACK_LIMIT')
            target_uid = merged[1]
        else:
            used = {r[1] for r in target_rows} | {r.identifier for r in items}
            used.update(r.identifier for frame in self.frames.values()
                        for r in inventory.validate_kit_frame(frame))
            target_uid = max(used) + 1
            incoming.update({1: target_uid, 4: count})
            target_rows.append(incoming)
        after_target = inventory.build_kit_frame(target_rows)
        # EquipmentStore's anchor must remain in its row even at Q0.
        after_rows = []
        for member in items:
            fields = dict(member.raw_fields)
            if member.identifier == source_uid:
                fields[4] -= count
                if not fields[4] and source_uid != state.item_uid:
                    continue
            after_rows.append(fields)
        after_owner = inventory.build_kit_frame(after_rows)
        intent = dict(owner_uid=owner_uid,
                      rows=[dict(uid=owner_uid, before=before.hex(), after=after_owner.hex()),
                            dict(uid=uid, before=target.hex(), after=after_target.hex())])
        from tools.local_original_session.world_warehouse import _atomic_json
        self.commit_started = True
        _atomic_json(self.intent_path, intent)
        self._finish(intent)  # each existing public CAS, debit before credit
        self.frames[uid] = after_target
        ctx.inventory_frame = after_owner
        self.refresh(uid)
        self.intent_path.unlink()
        from tools.local_original_session import inventory_update, item_transfer_protocol
        quantity = dict(item.raw_fields)[4] - count
        return (inventory_update._encode(inventory_update._values({1: source_uid, 4: quantity}))
                if quantity or source_uid == state.item_uid else item_transfer_protocol.build_remove(uid=source_uid))

    def _ats(self, record):
        return None if self.policy_for is None else self.policy_for(record)

    def potion(self, rt, now):
        record, uid = rt.record, rt.character_id
        if not record.alive or now < self.next_potion.get(uid, 0):
            return False
        ats = self._ats(record)
        if not ats or ats.get('status') != 'valid':
            return False
        hp_rule, mp_rule = ats.get('potion_hp') or {}, ats.get('potion_mp') or {}
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.frames[uid])]
        hp_enter, mp_enter = hp_rule.get('threshold'), mp_rule.get('threshold')
        heal = hp_enter is not None and record.hp / record.effective_max_hp <= hp_enter
        mana = (mp_enter is not None and record.effective_max_mp > 0
                and record.mp / record.effective_max_mp <= mp_enter and now >= self.blue_until.get(uid, 0))
        definitions = self.ctx.world.data.items
        selection = ats['selection_id']
        recovery_state = record.equipment.get('ats_recovery', {})
        exhausted = (list(recovery_state.get('exhausted', ()))
                     if recovery_state.get('selection') == selection else [])
        item = None
        used_slot = None
        for kind, rule, enabled, recovery in (('hp', hp_rule, heal, True), ('mp', mp_rule, mana, False)):
            if not enabled:
                continue
            for index, slot in enumerate(rule.get('slots', ())):
                key = f'{kind}:{index}'
                if key in exhausted:
                    continue
                candidate = self.ats_item(rows, slot)
                if candidate is None:
                    continue
                template = candidate[2]
                if ((recovery and template in definitions and definitions[template].heal_hp_range is not None)
                        or (not recovery and template == 492)):
                    item = candidate
                    used_slot = key
                    break
            if item is not None:
                break
        if item is None:
            return self.function_item(rt, now, ats.get('function_slots', ()))
        item[4] -= 1
        after = inventory.build_kit_frame([r for r in rows if r[4] or r[1] == self.states[uid].item_uid])
        self.store.replace_kit(uid, self.frames[uid], after)
        self.frames[uid] = after
        if item[4] == 0:
            record.equipment['ats_recovery'] = dict(selection=selection, exhausted=exhausted + [used_slot])
        hp_before, mp_before = record.hp, record.mp
        if item[2] != 492:
            low, high = self.ctx.world.data.items[item[2]].heal_hp_range
            record.hp = min(record.effective_max_hp, record.hp + self.ctx.world.combat.rng.randint(low, high))
        else:
            # L1J C_ItemUSe.useBluePotion:600s; MpRegeneration:wis-5.
            # A recovery effect, never an instant invented MP potion.
            self.blue_until[uid] = now + 600
            record.equipment['blue_expires_unix'] = time.time() + 600
        self.next_potion[uid] = now + 1  # explicit LOCAL item-use cadence
        self.events.append(dict(character_id=uid, template=item[2], at=now,
            hp_before=hp_before, hp_after=record.hp, mp_before=mp_before, mp_after=record.mp))
        del self.events[:-32]
        self.save(rt.owner_ref.uid)
        self._publish_use(rt, item[2], now)
        return True

    # ---- speed potions (ATS function item slots) ---------------------------
    def speed_factor(self, uid, now):
        """Product of active speed-effect rates, the PC AcceleratorChecker rule."""
        factor = 1.0
        for expires, rate in self.speed.get(uid, {}).values():
            if expires > now:
                factor *= rate
        return factor

    @staticmethod
    def ats_item(rows, slot):
        """Resolve the native-loadable slot: entity key, then template + f22.

        Mirror loadable_ats' unresolved f5/f6 rewrite without changing the save.
        Keep f7 opaque: its equivalence to ItemInfo f18 is unconfirmed.
        Retain unique-row admission and depleted anchors: a found Q0 entity
        cannot rebind to another stack, and ambiguity cannot pick by bag order.
        """
        raw = slot.get('raw', {})
        if slot.get('status') != 'valid' or raw.get(1) != 2 or not {4, 5, 6} <= raw.keys():
            return None
        from tools.local_original_session.ats_config_codec import _int32
        key, subtype = raw[6], raw[5]
        if raw[4] > 0 and _int32(key) <= 0:
            key, subtype = 1, 0  # same f5=0/f6=1 as loadable_ats
        matches = [r for r in rows if r.get(3, 0) == key] if _int32(key) > 0 else []
        if not matches:
            matches = [r for r in rows if (r[2], r.get(22, 0)) == (raw[4], subtype)]
        return matches[0] if len(matches) == 1 and matches[0][4] > 0 else None

    def function_item(self, rt, now, slots):
        """Use one configured speed item when its effect is absent (LOCAL cadence)."""
        record, uid = rt.record, rt.character_id
        if not record.alive or not slots or now < self.next_potion.get(uid, 0):
            return False
        definitions = self.ctx.world.data.items
        effects = self.speed.setdefault(uid, {})
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.frames[uid])]
        for slot in slots:
            item = self.ats_item(rows, slot)
            if item is None:
                continue
            template = item[2]
            definition = definitions.get(template)
            buff = None if definition is None else definition.buff
            if buff is None or record.class_id not in buff.classes:
                continue
            if effects.get(buff.kind, (0, 0))[0] > now:
                continue
            item[4] -= 1
            after = inventory.build_kit_frame([r for r in rows if r[4] or r[1] == self.states[uid].item_uid])
            self.store.replace_kit(uid, self.frames[uid], after)
            self.frames[uid] = after
            remaining = max(0.0, effects.get(buff.kind, (now, buff.rate))[0] - now)
            effects[buff.kind] = (now + min(remaining + buff.add_s, buff.cap_s), buff.rate)
            record.equipment['speed_expires_unix'] = {
                kind: [time.time() + expires - now, rate] for kind, (expires, rate) in effects.items()
                if expires > now}
            self.next_potion[uid] = now + 1
            self.events.append(dict(character_id=uid, template=template, at=now,
                                    speed=buff.kind, factor=self.speed_factor(uid, now)))
            del self.events[:-32]
            self.save(rt.owner_ref.uid)
            self._publish_use(rt, template, now, speed=True)
            return True
        return False

    def _publish_use(self, rt, template, now, *, speed=False):
        from tools.local_original_session import world_combat
        from tools.local_original_session.world_item_effects import item_use_effect_frame
        view = self.ctx.world
        entity = view.entities.resolve(rt.ref)
        if entity is None:
            return
        effect = item_use_effect_frame(entity.uid, self.item_effects.get(template))
        frames = (() if effect is None else (effect,))
        if speed:
            frames += (world_combat.speed_frame(entity.uid, self.speed_factor(rt.character_id, now)),)
        for watcher in view._watchers(entity):
            for wire in frames:
                view._queue(watcher, wire)
        if frames:
            view._announce()

    def consume_template(self, uid, templates):
        """Spend one of the first owned template (e.g. a return scroll)."""
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.frames[uid])]
        for template in templates:
            item = next((r for r in rows if r[2] == template and r[4] > 0), None)
            if item is None:
                continue
            item[4] -= 1
            after = inventory.build_kit_frame([r for r in rows if r[4] or r[1] == self.states[uid].item_uid])
            self.store.replace_kit(uid, self.frames[uid], after)
            self.frames[uid] = after
            self.events.append(dict(character_id=uid, template=template, consumed=1))
            del self.events[:-32]
            return template
        return None

    def consume_ats_item(self, uid, slots):
        """Spend only an exact configured item query, in ATS slot order."""
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.frames[uid])]
        for slot in slots:
            item = self.ats_item(rows, slot)
            if item is None:
                continue
            item[4] -= 1
            after = inventory.build_kit_frame([r for r in rows if r[4] or r[1] == self.states[uid].item_uid])
            self.store.replace_kit(uid, self.frames[uid], after)
            self.frames[uid] = after
            self.events.append(dict(character_id=uid, template=item[2], consumed=1))
            del self.events[:-32]
            return item[2]
        return None

    # ---- bridge bag/equipment window requests ------------------------------
    def set_equipped(self, uid, item_uid, equipped, slot_key=None):
        """Explicit equip/unequip on the same eight slots and CAS as a PC.

        Unlike the toggle ``equip``, a repeated request for the current state
        changes nothing. Unequip names the current slot key of that item.
        """
        items = {r.identifier: r for r in inventory.validate_kit_frame(self.frames[uid])}
        item = items.get(item_uid)
        need(item is not None and dict(item.raw_fields)[4] > 0, 'COMPANION_EQUIP_OWNED_ITEM_REQUIRED')
        definition = self.ctx.world.data.items.get(item.template_bits)
        need(definition is not None and definition.equippable, 'COMPANION_EQUIPPABLE_ITEM_REQUIRED')
        state = self.states[uid]
        if definition.kind == 'weapon':
            worn, key = state.weapon_uid == item_uid, 9
        else:
            slots = dict(state.slots)
            key = next((k for k, v in slots.items() if v == item_uid), definition.slot_key)
            worn = slots.get(key) == item_uid
        if equipped == worn:
            return False
        if not equipped:
            need(slot_key is None or slot_key == key, 'COMPANION_UNEQUIP_SLOT_MISMATCH')
        record = self.ctx.world.companions.records[uid]
        need(record.class_id in definition.classes, 'COMPANION_CLASS_CANNOT_EQUIP')
        return self.equip(uid, item_uid)

    def _raw_weight(self, template):
        known = self.weights.get(template)
        if known is not None:
            return known.raw_weight
        definition = self.ctx.world.data.items.get(template)
        if definition is not None:
            return definition.weight
        policy = self.ctx.item_policies.get(template)
        current = 0 if policy is None else policy.raw_weight
        return self.ctx.fold_sync_hooks('item_weight', current, template)

    def take(self, owner_uid, actor, source_uid, count, before, *, owner_max_weight):
        """Member bag -> owner bag, the reverse of give with the same durability.

        Worn items must be unequipped first. Debit (member) then credit (owner)
        through one durable intent; returns the owner's 0964/0965 frames.
        """
        ctx, uid = self.ctx, actor.character_id
        need(not self.intent_path.exists(), 'COMPANION_TRANSFER_RECOVERY_REQUIRED')
        source = self.frames[uid]
        items = inventory.validate_kit_frame(source)
        item = next((r for r in items if r.identifier == source_uid), None)
        need(item is not None and type(count) is int and 0 < count <= dict(item.raw_fields)[4],
             'COMPANION_TAKE_OWNED_QUANTITY_REQUIRED')
        state = self.states[uid]
        need(source_uid not in {state.weapon_uid, *(v for _, v in state.slots)},
             'COMPANION_TAKE_UNEQUIP_FIRST')
        definition = ctx.world.data.items.get(item.template_bits)
        need(definition is not None or item.template_bits == 492, 'COMPANION_TAKE_KNOWN_ITEM_REQUIRED')
        need((definition is None or definition.stackable) or count == 1,
             'COMPANION_TAKE_NONSTACK_QUANTITY')
        owner_rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(before)]
        # Owner rows may hold feature items outside the companion weight catalog
        # (summon token): same raw-weight sources as the owner's own stats.
        carried = sum(world_weight.stack_weight(self._raw_weight(r.template_bits), dict(r.raw_fields)[4])
                      for r in inventory.validate_kit_frame(before) if dict(r.raw_fields)[4])
        need(world_weight.can_add_weight(carried, self._raw_weight(item.template_bits),
            count, owner_max_weight), 'COMPANION_TAKE_OWNER_WEIGHT_CAPACITY')
        incoming = dict(item.raw_fields)
        merged = next((r for r in owner_rows if (definition is None or definition.stackable)
            and compatible_stack(r, incoming)), None)
        if merged is not None:
            merged[4] += count
            need(merged[4] <= 2_000_000_000, 'COMPANION_TAKE_STACK_LIMIT')
            target_uid, new_row = merged[1], False
        else:
            used = {r[1] for r in owner_rows}
            used.update(r.identifier for frame in self.frames.values()
                        for r in inventory.validate_kit_frame(frame))
            target_uid, new_row = max(used) + 1, True
            incoming.update({1: target_uid, 4: count})
            owner_rows.append(incoming)
        after_owner = inventory.build_kit_frame(owner_rows)
        member_rows = []
        for row in items:
            fields = dict(row.raw_fields)
            if row.identifier == source_uid:
                fields[4] -= count
                if not fields[4] and source_uid != state.item_uid:
                    continue
            member_rows.append(fields)
        after_member = inventory.build_kit_frame(member_rows)
        intent = dict(kind='take', owner_uid=owner_uid,
                      rows=[dict(uid=uid, before=source.hex(), after=after_member.hex()),
                            dict(uid=owner_uid, before=before.hex(), after=after_owner.hex())])
        from tools.local_original_session.world_warehouse import _atomic_json
        self.commit_started = True
        _atomic_json(self.intent_path, intent)
        self._finish(intent)  # member debit, then owner credit
        self.frames[uid] = after_member
        ctx.inventory_frame = after_owner
        self.refresh(uid)
        self.intent_path.unlink()
        from tools.local_original_session import inventory_update
        credited = next(r for r in owner_rows if r[1] == target_uid)
        return (inventory.build_add(credited) if new_row else
                inventory_update._encode(inventory_update._values({1: target_uid, 4: credited[4]})),)
