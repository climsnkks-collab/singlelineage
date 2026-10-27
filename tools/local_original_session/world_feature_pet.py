"""Optional native Pet UI over the shared entity, combat and AI owners.

REA396/400 supplies the wire schema, not taming/item-use/server policy.
The targeted food/collar adapters, nearby placements, gather/scatter decisions
and adopted candidate identities below are explicit LOCAL product policy.
Persistent pets use the existing joint CompanionStore and its half EXP ledger.
No player-character roster is fabricated and no second HP ledger is installed.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import struct
from types import MappingProxyType

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
from tools.local_original_session import world_combat as combat
from tools.local_original_session import world_pet as pure
from tools.local_original_session.world_companion import CompanionRecord, CompanionStore, split_exp
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.npc_ai import DELTAS, distance
from tools.local_original_session.world_bridge import need

DATA = Path(__file__).parent / 'data' / 'm1' / 'pet_runtime.json'


def pet_record(record):
    return record is not None and isinstance(record.equipment.get('_pet'), dict)


def frame(opcode, body):
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def pet_status(record, uid, catalog):
    child = b''.join(pb.encode_uint32(n, value) for n, value in (
        (1, record.equipment['_pet']['mode']), (2, record.max_hp), (3, record.hp),
        (4, record.max_mp), (5, record.mp), (6, record.level), (8, 100), (9, 0)))
    child += b'\x51' + struct.pack('<d', float(pure.exp_percent(catalog, record.exp)))
    return frame(0x4f14, pb.encode_uint32(1, uid) + pb.encode_uint32(2, 1)
                 + pb.encode_bytes(3, child))


def pet_hp(record, uid):
    # run396: required f3 is present with explicit LOCAL zero, not claimed as
    # the recovered official producer. f2 is the verified Pet percent input.
    return frame(0x4f1a, b''.join(pb.encode_uint32(n, value) for n, value in (
        (1, uid), (2, 100 * record.hp // record.max_hp), (3, 0))))


class _PetMagic:
    def __init__(self, system, previous):
        self.system, self.previous = system, previous

    def step(self, runtime, actor, owner, target, now, returning):
        if pet_record(runtime.record):
            return self.system.decision(runtime, actor, owner, target, now, returning)
        return False if self.previous is None else self.previous.step(
            runtime, actor, owner, target, now, returning)

    def __getattr__(self, name):
        return getattr(self.previous, name)


class _PetBags:
    """Keep ordinary companion inventory behavior; pets have no PC bags."""
    def __init__(self, previous):
        self.previous = previous

    def potion(self, runtime, now):
        return False if pet_record(runtime.record) else self.previous.potion(runtime, now)

    def __getattr__(self, name):
        return getattr(self.previous, name)


class PetSystem:
    def __init__(self, ctx, raw, catalog):
        self.ctx, self.view, self.raw, self.catalog = ctx, ctx.world, raw, catalog
        self.windows, self.trainer_windows, self.signatures = {}, {}, {}
        self.errors, self.events, self._reward_before = [], [], {}
        self.trainers = {}
        self._records = {}
        self.pending_reward = None
        self.reward_committed = False
        self.reward_save_attempted = False
        self.commit_started = False
        self.owner_restore = {}
        self.installed = False
        self.store = None
        self.adapters = []

    @property
    def records(self):
        return self._records

    def install(self):
        if self.installed:
            return
        v, ctx = self.view, self.ctx
        # Reuse the existing atomic schema in a feature-owned directory. Turning
        # this optional feature off cannot make the ordinary roster writer drop
        # persistent pets it does not understand.
        directory = Path(ctx.realm.store.path).parent / 'pets'
        directory.mkdir(exist_ok=True)
        self.store = CompanionStore(directory / 'characters.json')
        for row in self.store.payload['records']:
            record = CompanionRecord(**row)
            if pet_record(record):
                record.learned_spells = tuple(record.learned_spells)
                self.validate(record)
                need(record.character_id not in v.companions.records, 'PET_ID_COLLISION')
                self._records[record.character_id] = record
                self.profile(record)
        # A newer ordinary progression/death save wins over a stale pet file,
        # including play while this feature was disabled. Only a newer joint
        # pet snapshot repairs the normal projection after a crash window.
        progress = ctx._world_progress
        regular = getattr(ctx, '_companion_store', None)
        pet_time = self.store.path.stat().st_mtime_ns if self.store.path.exists() else 0
        progress_time = progress.path.stat().st_mtime_ns if progress.path.exists() else 0
        for key, saved in self.store.payload['owners'].items():
            uid = int(key)
            regular_time = (regular.path.stat().st_mtime_ns if regular is not None
                and regular.path.exists() and key in regular.payload['owners'] else 0)
            if pet_time >= max(progress_time, regular_time):
                from tools.local_original_session.world_progress import Progress
                self.owner_restore[uid] = saved
                progress.stage(uid, Progress(saved['exp'], saved['level'],
                    saved['max_hp'], saved['max_mp'], saved['lawful']))
                v.companion_owner_half[uid] = saved['exp_half']
                if regular is not None and key in regular.payload['owners']:
                    regular.payload['owners'][key] = dict(saved)
            elif regular is None or key not in regular.payload['owners']:
                v.companion_owner_half[uid] = saved['exp_half']
        self._install_data()
        self._adapt(v, '_spawn_frame', self.spawn)
        self._adapt(v, '_present', self.present)
        self._adapt(v, '_reward', self.reward)
        self._adapt(v.combat, 'companion_swing', self.swing)
        self._adapt(v, 'companion_save', self.save)
        self._adapt(v.companions, 'on_remove', self.removed)
        ai = v.companion_ai
        self.adapters.append((ai, 'magic', ai.magic))
        ai.magic = _PetMagic(self, ai.magic)
        if getattr(ai, 'inventory', None) is not None:
            self.adapters.append((ai, 'inventory', ai.inventory))
            ai.inventory = _PetBags(ai.inventory)
        for name, field in (('move_interval', 'move_ms'), ('attack_interval', 'attack_ms')):
            previous = getattr(ai, name)
            self.adapters.append((ai, name, previous))
            setattr(ai, name, lambda rt, old=previous, key=field: (
                self.species(rt.record)[key] / 1000 if pet_record(rt.record)
                else old(rt) if callable(old) else old))
        self.installed = True
        self.recover_bags()

    def _adapt(self, target, name, consumer):
        previous = getattr(target, name)
        self.adapters.append((target, name, previous))
        setattr(target, name, lambda *a, **k: consumer(previous, *a, **k))

    def close(self):
        if not self.installed:
            return
        try:
            for actor in tuple(self.view.companions.active.values()):
                if pet_record(actor.record):
                    self.view.companions.dismiss(actor.character_id)
            self.save(None, 0)
        finally:
            for uid in tuple(self.trainers):
                if self.view.entities.get(uid) is not None:
                    self.view.entities.remove(uid)
            for target, name, previous in reversed(self.adapters):
                setattr(target, name, previous)
            self.adapters.clear()
            self.windows.clear()
            self.trainer_windows.clear()

    def species(self, record):
        return self.raw['species'][record.equipment['_pet']['species']]

    def validate(self, record):
        record.validate()
        meta = record.equipment['_pet']
        need(meta['species'] in self.raw['species'] and meta['mode'] in range(1, 8)
             and type(meta['collar_uid']) is int and meta['collar_uid'] > 0,
             'PET_SAVED_METADATA_REQUIRED')
        need(record.level == pure.level_by_exp(self.catalog, record.exp), 'PET_SAVED_LEVEL_EXP')

    def profile(self, record):
        s = self.species(record)
        self.view.companion_profiles[record.character_id] = combat.PcProfile(
            record.level, 1, 0, s['str'], s['dex'], ac=s['ac'],
            weapon=replace(combat.FIST, small=s['damage'], large=s['damage']))
        self.view.companion_looks[record.character_id] = dict(name=s['name'],
            sprite_id=s['sprite'], owner_name='', stance=0)

    def _install_data(self):
        from tools.local_original_session.game_data import MonsterDef, DamageDef, Source, SpawnGroupDef, Rect
        from tools.local_original_session.world_interest_spawn import Group, Slot
        from tools.local_original_session.game_data import ItemDef
        v = self.view
        monsters, items = dict(v.data.monsters), dict(v.data.items)
        src = MappingProxyType({'pet': Source('local_policy', self.raw['source'])})
        for key, s in self.raw['species'].items():
            monster = MonsterDef(s['template'], s['token'], s['name'], s['sprite'],
                s['l1j'], s['wild_level'], s['hp'], s['mp'], s['ac'], s['exp'], False,
                s['move_ms'], s['attack_ms'], 1, 13, 20,
                DamageDef(1, s['damage'], s['str'], 'LOCAL_pet_candidate'), 5000, src)
            monsters.setdefault(s['template'], monster)
            for index, placement in enumerate(s['spawns']):
                map_id, x, y = placement
                spec = SpawnGroupDef('pet-' + key + '-' + str(index), s['template'],
                    map_id, Rect(x - 2, y - 2, x + 2, y + 2), 1, 60000, 120000, src)
                v.spawner.groups.append(Group(spec, monster, [Slot(0)]))
        for template, name, icon, weight, stackable in (
                (10, '고기', 124, 10000, True), (9, '괴물 눈 고기', 124, 10000, True),
                (361, '펫 목걸이', 487, 5000, False)):
            items.setdefault(template, ItemDef(template, '$23' if template == 10 else
                '$1173' if template == 361 else '$15654', name, 'pet', None, None,
                stackable, 0, 0, 0, 0, 0, 0, frozenset(range(7)), src,
                icon=icon, weight=weight))
        merged = replace(v.data, monsters=MappingProxyType(monsters), items=MappingProxyType(items))
        v.data = v.combat.data = v.ground.data = merged
        # Native ordinary town lookup remains untouched; feature-owned trainers
        # are published and handled only by this feature's frame routes.
        for spec in self.raw.get('trainers', ()):
            map_id, x, y = spec['position']
            if v.terrain.can_stand(map_id, x, y) is not True:
                self.errors.append('PET_TRAINER_TERRAIN_' + str(map_id))
                continue
            if any(e.kind is not Kind.ITEM for e in v.entities.near(map_id, x, y, 0, alive_only=False)):
                self.errors.append('PET_TRAINER_OCCUPIED_' + str(map_id))
                continue
            entity = v.entities.add(Kind.NPC, map_id, x, y, template_id=spec['template'])
            self.trainers[entity.uid] = (entity.ref, spec)

    def spawn(self, previous, entity):
        if entity.uid in self.trainers:
            return _trainer_frame(entity, self.trainers[entity.uid][1])
        actor = self.view.companions.retained_actor(entity.uid)
        if actor is None or not pet_record(actor.record):
            return previous(entity)
        from tools.local_original_session.world_visibility import MONSTER_BASE_FIELDS
        from tools.local_movement_session_route.route import authority
        from tools.local_game_session import session
        s, meta = self.species(actor.record), actor.record.equipment['_pet']
        owner = self.view.entities.get(actor.owner_ref.uid)
        name = self.ctx._world_names.get(actor.owner_ref.uid, '')
        fields = dict(MONSTER_BASE_FIELDS)
        fields.update({1: authority.pack_grid(entity.x, entity.y), 2: entity.uid,
            3: s['sprite'], 5: entity.heading, 9: s['name'], 16: False, 21: name,
            39: s['template']})
        # The frozen general codec intentionally has no enum67 domain. REA396
        # independently proves this optional Pet1 field; append that bounded
        # sourced field without expanding the generic codec's accepted domain.
        return frame(0x4e96, session.world.encode_payload(0x4e96, fields)
                     + pb.encode_uint32(67, 1))

    def present(self, previous, uid, map_id, x, y):
        from tools.local_original_session.world_visibility import in_screen
        result = previous(uid, map_id, x, y)
        result.extend(entity for ref, _spec in self.trainers.values()
            if (entity := self.view.entities.resolve(ref)) is not None
            and entity.map_id == map_id and in_screen(x, y, entity.x, entity.y))
        return result

    def removed(self, previous, actor):
        try:
            if previous is not None:
                previous(actor)
        finally:
            if pet_record(actor.record):
                self.view.companions.records.pop(actor.character_id, None)

    def as_state(self, record, actor):
        meta = record.equipment['_pet']
        pet = pure.PetRecord(record.character_id, meta['collar_uid'],
            record.owner_character_id, meta['species'], self.species(record)['template'],
            self.species(record)['name'], record.exp, record.level, record.hp,
            record.max_hp, record.mp, record.max_mp, pure.PetCommand.FOLLOW)
        return pure.PetState(pet, pure.PetLife.ACTIVE, actor.ref)

    def reward(self, previous, uid, corpse, monster, now):
        member = next((rt for rt in self.view.companions.active.values()
            if rt.owner_ref.uid == uid and self.view.companions.can_be_attacked(rt.ref.uid)
            and self.view.entities.resolve(rt.ref).map_id == corpse.map_id), None)
        if member is None or not pet_record(member.record):
            return previous(uid, corpse, monster, now)
        v, record = self.view, member.record
        old = self.as_state(record, member)
        old_half, old_pet_half = v.companion_owner_half.get(uid, 0), record.exp_half
        split = split_exp(monster.kill_exp, old_half, record.exp_half)
        new_level = pure.level_by_exp(self.catalog,
            min(self.catalog.max_exp, old.record.exp + split.companion_exp))
        species = self.catalog.species[old.record.species_key]
        rolls = tuple((v.combat.rng.randint(*species.hp_growth),
                       v.combat.rng.randint(*species.mp_growth))
                      for _ in range(new_level - old.record.level))
        grown = pure.award_pet_exp(self.catalog, old,
            allocated_exp=split.companion_exp, growth_rolls=rolls).state.record
        for name in ('exp', 'level', 'hp', 'mp', 'max_hp', 'max_mp'):
            setattr(record, name, getattr(grown, name))
        record.exp_half = split.companion_half
        v.companion_owner_half[uid] = split.owner_half
        self.profile(record)
        receipt = dict(kill_id=f'{v.companion_reward_epoch}:{corpse.uid}:{corpse.generation}',
            target_uid=corpse.uid, owner_character_id=uid, member_character_id=record.character_id,
            kill_exp=monster.kill_exp, owner_exp=split.owner_exp, member_exp=split.companion_exp,
            owner_half=split.owner_half, member_half=split.companion_half,
            kill_once=True, joint_commit_count=0, durable=False)
        v.companion_reward_receipts.append(receipt)
        del v.companion_reward_receipts[:-32]
        self.pending_reward, self.reward_committed, self.reward_save_attempted = receipt, False, False
        # The ordinary reward consumer receives the owner's allocated share and
        # rolls original drops once. It must not run PC/mage growth on pet EXP.
        v.companions.active.pop(record.character_id)
        try:
            return previous(uid, corpse, replace(monster, kill_exp=split.owner_exp), now)
        finally:
            v.companions.active[record.character_id] = member
            if not self.reward_save_attempted:
                for name in ('exp', 'level', 'hp', 'mp', 'max_hp', 'max_mp'):
                    setattr(record, name, getattr(old.record, name))
                record.exp_half = old_pet_half
                v.companion_owner_half[uid] = old_half
                v.companion_reward_receipts.remove(receipt)
                self.profile(record)
            self.pending_reward = None

    def save(self, previous, owner_uid, receipt=None):
        v = self.view
        receipt = self.pending_reward if receipt is None and self.pending_reward is not None else receipt
        for record in self.records.values():
            self.validate(record)
        live_records, rewards = v.companions.records, v.companion_reward_receipts
        v.companions.records = dict(self.records)
        v.companion_reward_receipts = [r for r in rewards if r['member_character_id'] in self.records]
        try:
            if self.pending_reward is not None:
                self.reward_save_attempted = True
            self.store.commit(v, owner_uid, receipt)
            if self.pending_reward is not None:
                self.reward_committed = True
        finally:
            v.companions.records, v.companion_reward_receipts = live_records, rewards
        regular = {key: row for key, row in live_records.items() if not pet_record(row)}
        v.companions.records = regular
        v.companion_reward_receipts = [r for r in rewards if r['member_character_id'] not in self.records]
        try:
            if previous is not None:
                previous(owner_uid, None if receipt is not None and
                         receipt['member_character_id'] in self.records else receipt)
        finally:
            v.companions.records, v.companion_reward_receipts = live_records, rewards
        self.publish_hp()

    def swing(self, previous, actor, profile, monster):
        if not pet_record(actor.record):
            return previous(actor, profile, monster)
        if (self.view.companions.get_actor(actor.ref.uid) is not actor
                or not self.view.companions.can_be_attacked(actor.ref.uid)
                or not self.view.combat.can_be_attacked(actor.owner_ref.uid)):
            return None
        return combat.pc_hits_npc(profile, monster, self.view.combat.rng)

    def publish_hp(self):
        for actor in self.view.companions.active.values():
            if not pet_record(actor.record):
                continue
            signature = (actor.ref, actor.record.hp, actor.record.max_hp,
                         actor.record.mp, actor.record.exp, actor.record.level)
            if self.signatures.get(actor.character_id) == signature:
                continue
            self.signatures[actor.character_id] = signature
            entity = self.view.entities.get(actor.ref.uid)
            if entity is not None:
                for watcher in self.view._watchers(entity):
                    self.view._queue(watcher, pet_hp(actor.record, entity.uid))
            for writer_id, ref in tuple(self.windows.items()):
                if ref.uid == actor.ref.uid:
                    self.view._queue(actor.owner_ref.uid,
                        pet_status(actor.record, actor.ref.uid, self.catalog))

    def decision(self, rt, actor, owner, target, now, returning):
        ai, mode = self.view.companion_ai, rt.record.equipment['_pet']['mode']
        if mode == 5 and (target is None or not ai._attack_position(actor, actor.x, actor.y, target)):
            candidates = self.view.entities.near(actor.map_id, actor.x, actor.y, 8, kind=Kind.NPC)
            # HOLD cannot approach a selected enemy. Prefer an actual attack
            # tile, then nearest distance, rather than pinning the oldest UID
            # at range while an attackable enemy is beside the guarding pet.
            enemy = min((e for e in candidates if ai._hostile(rt, e.ref) is not None),
                key=lambda e: (not ai._attack_position(actor, actor.x, actor.y, e),
                               distance(actor.x, actor.y, e.x, e.y), e.uid), default=None)
            if enemy is not None and (target is None or enemy.ref != target.ref):
                ai._select(rt, enemy.ref, now)
        if mode == 6:
            # Shared ground ownership/admission/retirement, actual owner bag CAS.
            candidates = sorted((e for e in self.view.entities.near(actor.map_id,
                actor.x, actor.y, 8, kind=Kind.ITEM)),
                key=lambda e: (distance(actor.x, actor.y, e.x, e.y), e.uid))
            for entity in candidates:
                item = self.view.ground.get(entity.ref)
                if item is None or (item.owner_uid != owner.uid and now < item.owner_until):
                    continue
                if distance(actor.x, actor.y, entity.x, entity.y) > 1:
                    ai._move(rt, actor, lambda x, y: distance(x, y, entity.x, entity.y) <= 1,
                             (entity.x, entity.y), now)
                else:
                    self.gather(owner.uid, actor, item, now)
                rt.action = 'COLLECT'
                return True
        if mode == 7 and target is None and not returning:
            # One bounded path step per native-data cadence, no random teleport.
            if distance(actor.x, actor.y, owner.x, owner.y) < 4:
                index = rt.record.character_id % 8
                dx, dy = DELTAS[index]
                gx, gy = owner.x + dx * 4, owner.y + dy * 4
                ai._move(rt, actor, lambda x, y: distance(x, y, owner.x, owner.y) >= 4,
                         (gx, gy), now)
            rt.action = 'SCATTER'
            return True
        return False

    def gather(self, uid, actor, item, now):
        # Only this currently selected connection owns its bag and publication.
        bound = next(((writer, uid) for writer, member in self.ctx._world_pcs.values()
                      if member == uid), None)
        if bound is None:
            return
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.ctx.inventory_frame)]
        definition = self.view.data.items.get(item.item_id)
        if definition is None:
            return
        found = next((r for r in rows if r[2] == item.item_id), None) if item.stackable else None
        if found is not None:
            found[4] += item.count
            wire = inventory_update._encode(inventory_update._values({1: found[1], 4: found[4]}))
        else:
            if len(rows) >= inventory.KIT_MAX_ITEMS:
                return
            fields = dict(self.ctx.starter_fields)
            fields.update({1: self.new_uid(rows), 2: item.item_id, 4: item.count, 7: definition.icon})
            rows.append(fields)
            wire = inventory.build_add(fields)
        # The PC-only pickup admission remains unchanged. This bounded LOCAL
        # collector route admits the real pet and its real owner explicitly.
        owner = self.view.entities.get(uid)
        need(self.view.companions.can_be_attacked(actor.uid) and owner is not None
             and owner.alive and self.view.entities.resolve(actor.ref) is actor
             and self.view.ground.get(item.ref) is item and self.view.entities.is_current(item.ref)
             and actor.map_id == owner.map_id == item.map_id
             and distance(actor.x, actor.y, item.x, item.y) <= 1
             and now < item.expires_at and (now >= item.owner_until or uid == item.owner_uid)
             and item.count > 0 and (item.stackable or item.count == 1), 'PET_CURRENT_COLLECTOR_REQUIRED')
        self.commit_bag(uid, rows)
        self.view.ground._discard(item.ref)  # same expiry/visibility lifetime owner
        self.view._queue(uid, wire)

    def new_uid(self, rows):
        used = [r[1] for r in rows]
        used += [r.equipment['_pet']['collar_uid'] for r in self.records.values()]
        result = max(used, default=65536) + 1
        need(result < 1 << 32, 'PET_ITEM_UID_EXHAUSTED')
        return result

    def commit_bag(self, uid, rows):
        before = self.ctx.inventory_frame
        after = inventory.build_kit_frame(rows)
        self.commit_started = True
        need(self.ctx.inventory_store.replace_kit(uid, before, after, append=True) is True,
             'PET_BAG_PERSISTED_CHANGE_REQUIRED')
        self.ctx.inventory_frame = after

    def consume(self, uid, item_uid, *, collar=None, count=1):
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.ctx.inventory_frame)]
        held = next((r for r in rows if r[1] == item_uid), None)
        need(held is not None and type(count) is int and 0 < count <= held[4],
             'PET_CURRENT_OWNED_ITEM_REQUIRED')
        held[4] -= count  # Retain zero row, preserving equipment anchor/UID.
        wire = inventory_update._encode(inventory_update._values({1: item_uid, 4: held[4]}))
        if collar is not None:
            need(len(rows) < inventory.KIT_MAX_ITEMS, 'PET_COLLAR_BAG_CAPACITY_REQUIRED')
            rows.append(collar)
        self.commit_bag(uid, rows)
        return (wire,) + (() if collar is None else (inventory.build_add(collar),))

    def owned(self, uid, actor_uid, *, living=False):
        actor = self.view.companions.retained_actor(actor_uid)
        owner, entity = self.view.entities.get(uid), self.view.entities.get(actor_uid)
        need(actor is not None and pet_record(actor.record) and owner is not None
             and entity is not None and actor.owner_ref == owner.ref
             and actor.record.owner_character_id == uid and entity.map_id == owner.map_id
             and actor_uid in self.view.visibility.known.get(uid, ()), 'PET_CURRENT_OWNED_ACTOR_REQUIRED')
        need(not living or self.view.companions.can_be_attacked(actor_uid), 'PET_LIVING_ACTOR_REQUIRED')
        return actor

    def summon(self, record, uid):
        v = self.view
        owner = v.entities.get(uid)
        need(owner is not None and uid in v.pcs and v.combat.can_be_attacked(uid), 'PET_LIVING_OWNER_REQUIRED')
        need(record.character_id not in v.companions.active, 'PET_ALREADY_ACTIVE')
        need(not any(rt.owner_ref.uid == uid for rt in v.companions.active.values()),
             'PET_ONE_ACTIVE_MEMBER_REQUIRED')
        for heading, (dx, dy) in enumerate(DELTAS):
            x, y = owner.x + dx, owner.y + dy
            if (v.terrain.can_step(owner.map_id, owner.x, owner.y, heading) is True
                    and not any(e.kind is not Kind.ITEM for e in v.entities.near(
                        owner.map_id, x, y, 0, alive_only=False))):
                call = v.companions.summon if record.alive else v.companions.restore_corpse
                v.companions.records[record.character_id] = record
                actor = call(record.character_id, uid, owner.map_id, x, y,
                             now=v.runtime.clock(), heading=heading)
                if record.alive:
                    v.companion_ai.start(actor.ref, v.runtime.clock())
                self.publish(actor)
                return actor
        raise ValueError('PET_FREE_SPAWN_TILE_REQUIRED')

    def publish(self, actor):
        from tools.local_original_session.world_visibility import in_screen
        entity = self.view.entities.get(actor.ref.uid)
        for uid, (map_id, x, y) in self.view.pcs.items():
            if map_id == entity.map_id and in_screen(x, y, entity.x, entity.y):
                self.view.visibility.known.setdefault(uid, set()).add(entity.uid)
                self.view._queue(uid, self.view._spawn_frame(entity))
                self.view._queue(uid, pet_hp(actor.record, entity.uid))
                if not actor.record.alive:
                    self.view._queue(uid, combat.death_frame(entity.uid))

    def command(self, actor, mode, targets):
        need(mode in range(1, 8), 'PET_COMMAND_MODE_REQUIRED')
        need(len(targets) == (1 if mode == 1 else 0), 'PET_COMMAND_TARGET_FIELDS_REQUIRED')
        target = None
        if targets:
            text = targets[0].decode('ascii')
            need(text.isdecimal() and str(int(text)) == text, 'PET_DECIMAL_TARGET_REQUIRED')
            target = self.view.entities.get(int(text))
            need(target is not None and target.uid in self.view.visibility.known.get(actor.owner_ref.uid, ())
                 and self.view.companion_ai._hostile(actor, target.ref) is target, 'PET_HOSTILE_TARGET_REQUIRED')
        meta = actor.record.equipment['_pet']
        now = self.view.runtime.clock()
        self.view.companions.set_commands(actor.character_id,
            movement_mode='HOLD' if mode in (4, 5) else 'FOLLOW',
            combat_mode='PASSIVE' if mode in (4, 6) else 'DEFEND' if mode in (3, 5, 7) else 'ASSIST',
            now=now)
        meta['mode'] = mode
        self.view.companion_ai.command_changed(actor.ref, now)
        if target is not None:
            self.view.companion_ai._select(actor, target.ref, now)

    def tame(self, uid, target_uid, item):
        v = self.view
        need(not any(r.equipment['_pet'].get('pending_bag') for r in self.records.values()),
             'PET_PENDING_BAG_RECOVERY_REQUIRED')
        owner, target = v.entities.get(uid), v.entities.get(target_uid)
        found = v.spawner.slot_for(target_uid)
        need(owner is not None and target is not None and target.alive and found is not None
             and found[0].active and target_uid in v.visibility.known.get(uid, ())
             and target.map_id == owner.map_id
             and distance(owner.x, owner.y, target.x, target.y) <= 3,
             'PET_CURRENT_VISIBLE_WILD_TARGET_REQUIRED')
        key = next((key for key, s in self.raw['species'].items()
                    if s['template'] == target.template_id), None)
        need(key is not None, 'PET_SUPPORTED_WILD_SPECIES_REQUIRED')
        group, slot = found
        state = v.combat.pcs[uid]
        _, info = self.ctx.realm.store.select(self.ctx._world_names[uid])
        classes = ('crown', 'knight', 'elf', 'wizard', 'darkelf', 'dragon_knight', 'illusionist')
        active = [rt for rt in v.companions.active.values() if rt.owner_ref.uid == uid]
        need(not active, 'PET_ONE_ACTIVE_MEMBER_REQUIRED')
        rows = inventory.validate_kit_frame(self.ctx.inventory_frame)
        food_id = 40056 if item.template_bits == 10 else 40057
        # Product's explicit meat10 support does not alter the reusable L1J
        # proposal catalog or equate the two actual inventory item identities.
        species = self.catalog.species[key]
        local_species = replace(species, food_l1j_item_id=food_id)
        catalog = replace(self.catalog, species=MappingProxyType(
            dict(self.catalog.species) | {key: local_species}))
        result = pure.offer_food(catalog,
            pure.PetOwner(uid, state.profile.level, info[15], classes[info[3]],
                used_pet_cost=0, inventory_slots_after_transfer=len(rows)),
            pure.TameTarget(target.ref, key, target.template_id, slot.hp, group.monster.hp,
                group.monster.mp, group.monster.mp),
            pure.FoodOffer(uid, item.identifier, food_id, item.template_bits, dict(item.raw_fields)[4]))
        if not result.tamed:
            wires = self.consume(uid, item.identifier)
            self.events.append(dict(kind='feed', target=target_uid, reason=result.reason, consumed=1))
            del self.events[:-64]
            return wires
        fields = dict(self.ctx.starter_fields)
        fields.update({1: self.new_uid([dict(r.raw_fields) for r in rows]),
                       2: 361, 4: 1, 7: 487, 18: (self.species_name(key) + ' 목걸이').encode('utf-8')})
        pet_id = max([0x60000000, *self.records]) + 1
        need(pet_id < 0x70000000, 'PET_ID_EXHAUSTED')
        record = CompanionRecord(pet_id, uid, 'owned-local-pet', level=species.initial_level,
            exp=species.initial_exp, hp=slot.hp, mp=group.monster.mp,
            max_hp=group.monster.hp, max_mp=group.monster.mp,
            movement_mode='FOLLOW', combat_mode='DEFEND', support_enabled=False,
            equipment={'_pet': dict(species=key, collar_uid=fields[1], mode=3, out=True)})
        self.validate(record)
        self.records[pet_id] = record
        self.profile(record)
        # Save a forward-only absolute bag intent in the existing joint record.
        # On restart its same before/after CAS completes the accepted offering;
        # never issue another UID, collar or debit for an uncertain prior save.
        before = self.ctx.inventory_frame
        updated = [dict(r.raw_fields) for r in rows]
        next(r for r in updated if r[1] == item.identifier)[4] -= 1
        updated.append(fields)
        after = inventory.build_kit_frame(updated)
        record.equipment['_pet']['pending_bag'] = dict(before=before.hex(), after=after.hex())
        self.commit_started = True
        self.view._save_companion(uid)
        need(self.store.pending is None, 'PET_DURABLE_TAME_INTENT_REQUIRED')
        wires = self.consume(uid, item.identifier, collar=fields)
        record.equipment['_pet'].pop('pending_bag')
        self.view._save_companion(uid)
        need(self.store.pending is None, 'PET_DURABLE_TAME_COMPLETION_REQUIRED')
        # End the real wild generation and its slot without kill/loot/EXP.
        now = v.runtime.clock()
        if v.ai is not None:
            v.ai.drop(target_uid)
            v.ai.release_target(target_uid, now)
        v.runtime.scheduler.cancel_owner(target.ref)
        v.companion_ai.release_target(target_uid, now)
        v.spawner._slots.pop(target_uid)
        from tools.local_original_session.world_interest_spawn import SlotState
        slot.state, slot.uid, slot.hp = SlotState.EMPTY, None, 0
        slot.retry_at = now + group.spec.respawn_delay_min_ms / 1000
        v.entities.remove(target_uid)
        for watcher in v.pcs:
            for wire in v._refresh(watcher):
                v._queue(watcher, wire)
        actor = self.summon(record, uid)
        self.view._save_companion(uid)
        self.events.append(dict(kind='tame', target=target_uid, pet_id=pet_id,
                                actor_uid=actor.ref.uid, collar_uid=fields[1], consumed=1))
        del self.events[:-64]
        return wires

    def species_name(self, key):
        return self.raw['species'][key]['name']

    def recover_bags(self):
        for record in self.records.values():
            pending = record.equipment['_pet'].get('pending_bag')
            if pending is None:
                continue
            before, after = bytes.fromhex(pending['before']), bytes.fromhex(pending['after'])
            inventory.validate_kit_frame(before)
            inventory.validate_kit_frame(after)
            current = self.ctx.inventory_store.restore(record.owner_character_id)
            need(current in (before, after), 'PET_TAME_BAG_RECOVERY_CONFLICT')
            if current != after:
                self.ctx.inventory_store.replace_kit(record.owner_character_id, before, after, append=True)
            if self.ctx.inventory_frame == before:
                self.ctx.inventory_frame = after
            record.equipment['_pet'].pop('pending_bag')

    def toggle(self, uid, item_uid):
        record = next((r for r in self.records.values() if r.owner_character_id == uid
                       and r.equipment['_pet']['collar_uid'] == item_uid), None)
        need(record is not None, 'PET_OWNED_REGISTERED_COLLAR_REQUIRED')
        actor = self.view.companions.active.get(record.character_id)
        if actor is not None:
            record.equipment['_pet']['out'] = False
            self.view.companions.dismiss(record.character_id)
            self.windows = {key: ref for key, ref in self.windows.items() if ref.uid != actor.ref.uid}
        else:
            actor = self.summon(record, uid)
            record.equipment['_pet']['out'] = True
        self.view._save_companion(uid)
        return actor

    def revive(self, uid, target_uid, item):
        actor = self.owned(uid, target_uid)
        need(not actor.record.alive and actor.record.hp == 0
             and not self.view.entities.get(target_uid).alive, 'PET_CURRENT_CORPSE_REQUIRED')
        wires = self.consume(uid, item.identifier)
        actor = self.view.companions.revive(actor.character_id, self.view.runtime.clock(),
                                           hp=max(1, actor.record.max_hp // 4))
        self.view._save_companion(uid)
        self.view.companion_ai.start(actor.ref, self.view.runtime.clock())
        self.publish(actor)
        return wires


def _one(message, number, wire):
    values = message.occurrences(number)
    need(len(values) == 1 and values[0].wire_type == wire, 'PET_SINGLE_WIRE_FIELD_REQUIRED')
    return values[0].value


def _params(payload, *, targeted):
    with pb.parse_message(payload, limits=pb.WireLimits(max_body=128, max_fields=5,
                                                       max_field_bytes=16)) as message:
        expected = {1: 1, 15: 0, 16: 0}
        if targeted:
            expected.update({2: _one(message, 2, 0), 3: 0})
            need(0 < expected[2] < 1 << 63, 'PET_TARGET_UID_REQUIRED')
        need(len(message.fields) == len(expected) and all(
            _one(message, n, 0) == value for n, value in expected.items()), 'PET_ITEM_PARAMS_REQUIRED')
        return expected.get(2)


async def _pet_trainer_frame(ctx, writer, row, game, request, operation_lock):
    system = ctx._pet_system
    if system is None or not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False
    system.install()
    bindings = ctx._world_handler_bindings
    wire = bindings.wire
    uid = ctx._world_pcs[id(writer)][1]
    system.commit_started = False
    try:
        if request.opcode == 0x4e43:
            signed = wire.click.decode_request(request.payload)
            target_uid, action = signed & 0xffffffff, None
            if target_uid not in system.trainers:
                system.trainer_windows.pop(id(writer), None)
                return False
        else:
            fields = wire.dialogue.decode_haction_normal(request.payload)
            signed, action = fields[1], fields[2]
            target_uid = signed & 0xffffffff
            if target_uid not in system.trainers:
                return False
            need(action in (b'depositpet', b'retrievepet'), 'PET_TRAINER_ORIGINAL_ACTION_REQUIRED')
        ref, spec = system.trainers[target_uid]

        def apply():
            need(ctx.realm.registry.resolve(writer) is game and ctx.owner_current(
                writer, row, ctx.realm.service(writer).snapshot()) and ctx.world.combat.can_be_attacked(uid),
                'PET_TRAINER_CURRENT_LIVING_OWNER_REQUIRED')
            owner, entity = ctx.world.entities.get(uid), ctx.world.entities.resolve(ref)
            need(entity is not None and owner is not None and owner.map_id == entity.map_id
                 and target_uid in ctx.world.visibility.known.get(uid, ())
                 and distance(owner.x, owner.y, entity.x, entity.y) <= bindings.interaction_distance,
                 'PET_TRAINER_CURRENT_VISIBLE_NEAR_REQUIRED')
            cost = ()
            if action is not None:
                need(system.trainer_windows.get(id(writer)) == (owner.ref, ref),
                     'PET_TRAINER_DRAINED_MENU_REQUIRED')
                items = inventory.validate_kit_frame(ctx.inventory_frame)
                collars = {r.identifier for r in items if r.template_bits == 361
                           and dict(r.raw_fields)[4] == 1}
                if action == b'depositpet':
                    actors = [rt for rt in ctx.world.companions.active.values()
                              if rt.owner_ref == owner.ref and pet_record(rt.record)]
                    need(actors and all(rt.record.equipment['_pet']['collar_uid'] in collars
                                        for rt in actors), 'PET_TRAINER_OWNED_ACTIVE_COLLAR_REQUIRED')
                    for actor in actors:
                        actor.record.equipment['_pet']['out'] = False
                        ctx.world.companions.dismiss(actor.character_id)
                    system.windows.pop(id(writer), None)
                else:
                    candidates = [r for r in system.records.values() if r.owner_character_id == uid
                        and r.equipment['_pet']['collar_uid'] in collars
                        and r.character_id not in ctx.world.companions.active]
                    # Native selection-list producer is unresolved. This LOCAL
                    # menu path accepts a unique real collar, never guesses one.
                    need(len(candidates) == 1, 'PET_TRAINER_UNIQUE_OWNED_COLLAR_REQUIRED')
                    need(not any(rt.owner_ref.uid == uid for rt in ctx.world.companions.active.values()),
                         'PET_ONE_ACTIVE_MEMBER_REQUIRED')
                    coins = [r for r in items if r.template_bits == 7 and dict(r.raw_fields)[4] >= 50]
                    need(len(coins) == 1, 'PET_TRAINER_FEE50_REQUIRED')
                    # Admit a free tile before taking the fee. Materialize the
                    # actual member only once; failed durable cost never replays.
                    actor = system.summon(candidates[0], uid)
                    cost = system.consume(uid, coins[0].identifier, count=50)
                    candidates[0].equipment['_pet']['out'] = True
                ctx.world._save_companion(uid)
                need(system.store.pending is None, 'PET_TRAINER_DURABLE_CHANGE_REQUIRED')
            return (*cost, *ctx.world.drain(uid), wire.dialogue_frame({1: signed, 2: b'dick1'})), owner.ref
        wires, owner_ref = await ctx.world.runtime.dispatch_now(apply)
        await ctx._world_send(writer, row, wires, operation_lock)
        system.trainer_windows[id(writer)] = (owner_ref, ref)
    except (ValueError, pb.WireError, UnicodeError) as error:
        if system.commit_started:
            raise
        system.errors.append(str(error)[:96])
        del system.errors[:-16]
    return True


async def _pet_frame(ctx, writer, row, game, request, operation_lock):
    system = ctx._pet_system
    if (system is None or not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None):
        return False
    system.install()
    uid, attempted = ctx._world_pcs[id(writer)][1], False
    system.commit_started = False
    command = None
    try:
        with pb.parse_message(request.payload, limits=pb.WireLimits(
                max_body=4096, max_fields=8, max_field_bytes=2048)) as message:
            if request.opcode == 0x0960:
                item_uid = _one(message, 1, 0)
                item = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                             if r.identifier == item_uid), None)
                if item is None:
                    return False
                if dict(item.raw_fields).get(18) == '동료 소환/해산'.encode('utf-8'):
                    # Existing active-cap1: the regular token must never dismiss
                    # a pet or treat its durable identity as a saved wizard.
                    if any(rt.owner_ref.uid == uid and pet_record(rt.record)
                           for rt in ctx.world.companions.active.values()):
                        system.errors.append('PET_STORE_BEFORE_COMPANION_TOKEN')
                        return True
                    return False
                if item.template_bits not in (9, 10, 28, 361):
                    return False
                body = _one(message, 2, 2)
                need(len(message.fields) == 2, 'PET_ITEM_USE_FIELDS_REQUIRED')
                if item.template_bits == 361:
                    _params(body, targeted=False)
                    command = ('collar', item)
                else:
                    # Ordinary food consumption has the untargeted recipe and
                    # remains owned by its ordinary item-use feature.
                    try:
                        target_uid = _params(body, targeted=True)
                    except ValueError:
                        if item.template_bits in (9, 10):
                            return False
                        raise
                    target = ctx.world.entities.get(target_uid)
                    if item.template_bits == 28:
                        actor = ctx.world.companions.retained_actor(target_uid)
                        if actor is None or not pet_record(actor.record):
                            return False
                        command = ('revive', item, target_uid)
                    else:
                        found = ctx.world.spawner.slot_for(target_uid)
                        if target is None or found is None or target.template_id not in (
                                s['template'] for s in system.raw['species'].values()):
                            return False
                        command = ('food', item, target_uid)
            elif request.opcode == 0x4f13:
                actor_uid = _one(message, 1, 0)
                actor = ctx.world.companions.retained_actor(actor_uid)
                if actor is None or not pet_record(actor.record):
                    return False
                need(len(message.fields) == 1, 'PET_QUERY_FIELDS_REQUIRED')
                command = ('query', actor_uid)
            elif request.opcode == 0x4f02:
                actor_uid = _one(message, 3, 0)
                actor = ctx.world.companions.retained_actor(actor_uid)
                if actor is None or not pet_record(actor.record):
                    return False
                mode = _one(message, 1, 0)
                targets = message.occurrences(2)
                need(len(message.fields) == 2 + len(targets)
                     and all(f.wire_type == 2 for f in targets), 'PET_COMMAND_FIELDS_REQUIRED')
                command = ('mode', actor_uid, mode, tuple(bytes(f.value) for f in targets))
            else:
                return False

        def apply():
            nonlocal attempted
            need(ctx.realm.registry.resolve(writer) is game and ctx._world_bound(writer)
                 and ctx.owner_current(writer, row, ctx.realm.service(writer).snapshot())
                 and ctx.world.combat.can_be_attacked(uid), 'PET_CURRENT_LIVING_SELECTED_OWNER_REQUIRED')
            cost, actor = (), None
            if command[0] in ('food', 'revive', 'collar'):
                item = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                             if r.identifier == command[1].identifier), None)
                need(item is not None and item.template_bits == command[1].template_bits
                     and dict(item.raw_fields)[4] > 0, 'PET_CURRENT_OWNED_ITEM_REQUIRED')
                if command[0] == 'food':
                    cost = system.tame(uid, command[2], item)
                elif command[0] == 'revive':
                    system.owned(uid, command[2])
                    cost = system.revive(uid, command[2], item)
                else:
                    actor = system.toggle(uid, item.identifier)
            else:
                actor = system.owned(uid, command[1], living=command[0] == 'mode')
                if command[0] == 'mode':
                    need(system.windows.get(id(writer)) == actor.ref, 'PET_DRAINED_CURRENT_WINDOW_REQUIRED')
                    system.command(actor, command[2], command[3])
                    ctx.world._save_companion(uid)
            wires = list(cost) + ctx.world.drain(uid)
            if actor is not None and command[0] in ('query', 'mode'):
                wires.append(pet_status(actor.record, actor.ref.uid, system.catalog))
            return wires, actor.ref if actor is not None else None
        wires, ref = await ctx.world.runtime.dispatch_now(apply)
        await ctx._world_send(writer, row, wires, operation_lock)
        if command[0] == 'query':
            system.windows[id(writer)] = ref
    except (ValueError, pb.WireError, UnicodeError) as error:
        if system.commit_started:
            raise
        system.errors.append(str(error)[:96])
        del system.errors[:-16]
    return True


def _pet_initialize(ctx):
    ctx._pet_system = None
    ctx._pet_enabled = os.environ.get('SL_PET', '0') == '1'
    if ctx._pet_enabled:
        raw = json.loads(DATA.read_text(encoding='utf-8'))
        ctx._pet_system = PetSystem(ctx, raw, pure.load_pets())


def _pet_tick(system, now):
    system.install()
    if system.view.closed:
        return
    from tools.local_original_session.world_visibility import in_screen
    for uid, (map_id, x, y) in system.view.pcs.items():
        known = system.view.visibility.known.setdefault(uid, set())
        for trainer_uid, (ref, spec) in system.trainers.items():
            entity = system.view.entities.resolve(ref)
            if (entity is not None and entity.map_id == map_id
                    and in_screen(x, y, entity.x, entity.y) and trainer_uid not in known):
                known.add(trainer_uid)
                # TownAppearance is intentionally constructed by keyword below.
                system.view._queue(uid, _trainer_frame(entity, spec))
    system.publish_hp()
    system.view._announce()


def _trainer_frame(entity, spec):
    from tools.local_original_session.world_visibility import MONSTER_BASE_FIELDS
    from tools.local_movement_session_route.route import authority
    from tools.local_game_session import session
    fields = dict(MONSTER_BASE_FIELDS)
    fields.update({1: authority.pack_grid(entity.x, entity.y), 2: entity.uid,
        3: spec['sprite'], 5: entity.heading, 9: spec['name']})
    return frame(0x4e96, session.world.encode_payload(0x4e96, fields))


def _pet_started(ctx):
    if ctx._pet_system is not None:
        ctx.world.runtime.add_tick_hook(lambda now: _pet_tick(ctx._pet_system, now))


async def _pet_enter(ctx, writer, row, game, operation_lock):
    system = ctx._pet_system
    if system is None:
        return
    def apply():
        system.install()
        uid = ctx._world_pcs[id(writer)][1]
        saved = system.owner_restore.pop(uid, None)
        if saved is not None:
            from tools.local_original_session.world_progress import Progress, exp_percent
            from tools.local_original_session.world_status_frames import full_status_frame
            state = ctx.world.combat.pcs[uid]
            ctx.world.exp[uid] = saved['exp']
            state.profile = replace(state.profile, level=saved['level'])
            state.max_hp = saved['max_hp']
            state.status_fields.update({2: saved['level'], 11: saved['max_hp'],
                13: saved['max_mp'], 18: saved['lawful'],
                26: exp_percent(ctx.world.data, saved['exp'], saved['level'])})
            ctx._world_lawful[uid] = saved['lawful']
            ctx.world.progress_dirty[uid] = Progress(saved['exp'], saved['level'],
                saved['max_hp'], saved['max_mp'], saved['lawful'])
            ctx.world._queue(uid, full_status_frame(state.status_fields))
        owned = {r.identifier for r in inventory.validate_kit_frame(ctx.inventory_frame)
                 if r.template_bits == 361 and dict(r.raw_fields)[4] == 1}
        for record in system.records.values():
            if (record.owner_character_id == uid and record.equipment['_pet']['collar_uid'] in owned
                    and record.equipment['_pet'].get('out', False)
                    and record.character_id not in ctx.world.companions.active):
                system.summon(record, uid)
        _pet_tick(system, ctx.world.runtime.clock())
        return tuple(ctx.world.drain(uid))
    await ctx._world_send(writer, row, await ctx.world.runtime.dispatch_now(apply), operation_lock)


def _pet_stopped(ctx):
    if ctx._pet_system is not None:
        ctx._pet_system.close()


async def _pet_leave(ctx, writer):
    if ctx._pet_system is not None:
        ctx._pet_system.windows.pop(id(writer), None)
        ctx._pet_system.trainer_windows.pop(id(writer), None)


METHODS = (_pet_initialize, _pet_started, _pet_enter, _pet_stopped, _pet_leave, _pet_frame,
           _pet_trainer_frame)
HOOKS = {'initialize': ('_pet_initialize',), 'runtime_started': ('_pet_started',),
         'after_enter': ('_pet_enter',), 'after_leave': ('_pet_leave',),
         'runtime_stopped': ('_pet_stopped',)}
FRAMES = {opcode: ('_pet_frame',) for opcode in (0x0960, 0x4f13, 0x4f02)}
FRAMES.update({opcode: ('_pet_trainer_frame',) for opcode in (0x4e43, 0x4ed4)})
OUTGOING_OPCODES = (0x4f14, 0x4f1a)
