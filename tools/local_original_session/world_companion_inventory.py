"""run406 4EF5 GIVE to an owned Player companion; LOCAL auto equipment.

The two character rows remain ordinary inventory/equipment saves. A short-lived
intent uses the existing warehouse atomic writer solely to finish interrupted
two-row transfers forward. It is not a second bag or an exchange UI protocol.
"""
from dataclasses import replace
import json
from pathlib import Path
import struct
import time

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, equipment_store, world_weight
from tools.local_original_session.world_bridge import need


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
        self.next_potion = {}
        self.events = []
        self.commit_started = False
        self.recovered = None
        if self.intent_path.exists():
            intent = json.loads(self.intent_path.read_text(encoding='utf-8'))
            self._finish(intent)
            source = intent['rows'][0]
            if ctx.inventory_frame == bytes.fromhex(source['before']):
                ctx.inventory_frame = bytes.fromhex(source['after'])
            self.recovered = intent

    def _finish(self, intent):
        for row in intent['rows']:
            uid = row['uid']
            before, after = bytes.fromhex(row['before']), bytes.fromhex(row['after'])
            current = self.store.restore(uid)
            need(current in (before, after), 'COMPANION_TRANSFER_RECOVERY_CONFLICT')
            if current != after:
                self.store.replace_kit(uid, before, after, append=True)

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
        self.refresh(uid, publish=False)
        if self.recovered is not None and self.recovered['auto_character'] == uid:
            self.equip(uid, self.recovered['auto_uid'], automatic=True)
            self.intent_path.unlink()
            self.recovered = None

    def calculated(self, uid, frame=None):
        from tools.local_original_session.world_stats import companion_stats
        return companion_stats(self.ctx.world.companions.records[uid],
            self.characters[uid]['attributes'],
            self.frames[uid] if frame is None else frame, self.states[uid],
            self.ctx.world.data.items, self.weights)

    def refresh(self, uid, *, publish=True):
        from tools.local_original_session import world_combat
        ctx = self.ctx
        calculated, worn = self.calculated(uid)
        row = self.characters[uid]
        ctx.world.companion_profiles[uid] = world_combat.companion_profile(
            calculated, worn, row['gender'])
        by_uid = {r.identifier: r for r in inventory.validate_kit_frame(self.frames[uid])}
        weapon = by_uid.get(self.states[uid].weapon_uid)
        definition = None if weapon is None else ctx.world.data.items[weapon.template_bits]
        stance = ctx._world_stances.get('unarmed' if definition is None else definition.weapon_type, 0)
        look = ctx.world.companion_looks[uid]
        old_stance, look['stance'] = look['stance'], stance
        actor = ctx.world.companions.active.get(uid)
        if publish and actor is not None and old_stance != stance:
            entity = ctx.world.entities.get(actor.ref.uid)
            body = pb.encode_uint32(1, entity.uid) + pb.encode_uint32(2, stance)
            wire = struct.pack('<HH', len(body) + 6, 0x4ed5) + body + b'\0\0'
            for watcher in ctx.world._watchers(entity):
                ctx.world._queue(watcher, wire)
            ctx.world._announce()

    def equip(self, uid, item_uid, *, automatic=False):
        """Same eight slots/CAS as PC. Explicit caller may toggle equipment."""
        from tools.local_original_session.world_enchant_inventory import enchant_level
        items = {r.identifier: r for r in inventory.validate_kit_frame(self.frames[uid])}
        item = items[item_uid]
        definition = self.ctx.world.data.items.get(item.template_bits)
        if definition is None or not definition.equippable or 3 not in definition.classes:
            return False
        need(dict(item.raw_fields)[4] > 0, 'COMPANION_EQUIP_OWNED_ITEM_REQUIRED')
        state = self.states[uid]
        slots = dict(state.slots)
        current_uid = state.weapon_uid if definition.kind == 'weapon' else slots.get(definition.slot_key, 0)
        if automatic:
            if current_uid:
                current = items[current_uid]
                other = self.ctx.world.data.items[current.template_bits]
                score = lambda r, d: ((d.dmg_small + d.dmg_large) / 2 + d.dmg_bonus + enchant_level(r, d)
                    if d.kind == 'weapon' else -d.ac + enchant_level(r, d))
                if score(item, definition) <= score(current, other):
                    return False
            chosen = item_uid
        else:
            chosen = 0 if current_uid == item_uid else item_uid
        weapon_uid = state.weapon_uid
        if definition.kind == 'weapon':
            weapon_uid = chosen
        elif chosen:
            slots[definition.slot_key] = chosen
        else:
            slots.pop(definition.slot_key, None)
        self.states[uid] = self.equipment.compare_and_swap_kit(uid, self.frames[uid], state,
            weapon_uid=weapon_uid, slots=tuple(slots.items()))
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
        comparable = lambda r: {k: v for k, v in r.items() if k not in (1, 4)}
        merged = next((r for r in target_rows if (definition is None or definition.stackable)
            and comparable(r) == comparable(incoming)), None)
        if merged is not None:
            merged[4] += count
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
        intent = dict(auto_character=uid, auto_uid=target_uid,
                      rows=[dict(uid=owner_uid, before=before.hex(), after=after_owner.hex()),
                            dict(uid=uid, before=target.hex(), after=after_target.hex())])
        from tools.local_original_session.world_warehouse import _atomic_json
        self.commit_started = True
        _atomic_json(self.intent_path, intent)
        self._finish(intent)  # each existing public CAS, debit before credit
        self.frames[uid] = after_target
        ctx.inventory_frame = after_owner
        if definition is not None and definition.equippable:
            self.equip(uid, target_uid, automatic=True)
        self.refresh(uid)
        self.intent_path.unlink()
        from tools.local_original_session import inventory_update, item_transfer_protocol
        quantity = dict(item.raw_fields)[4] - count
        return (inventory_update._encode(inventory_update._values({1: source_uid, 4: quantity}))
                if quantity or source_uid == state.item_uid else item_transfer_protocol.build_remove(uid=source_uid))

    def potion(self, rt, now):
        record, uid = rt.record, rt.character_id
        if not record.alive or now < self.next_potion.get(uid, 0):
            return False
        policy = self.policy['thresholds']
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.frames[uid])]
        heal = record.hp / record.max_hp <= policy['hp']['companion_emergency_enter']
        mana = (record.max_mp > 0 and record.mp / record.max_mp <= policy['mp']['recover_fraction']
                and now >= self.blue_until.get(uid, 0))
        item = next((r for r in rows if r[4] > 0 and
            ((heal and r[2] == 14) or (mana and r[2] == 492))), None)
        if item is None:
            return False
        item[4] -= 1
        after = inventory.build_kit_frame([r for r in rows if r[4] or r[1] == self.states[uid].item_uid])
        self.store.replace_kit(uid, self.frames[uid], after)
        self.frames[uid] = after
        hp_before, mp_before = record.hp, record.mp
        if item[2] == 14:
            low, high = self.ctx.world.data.items[14].heal_hp_range
            record.hp = min(record.max_hp, record.hp + self.ctx.world.combat.rng.randint(low, high))
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
        return True


