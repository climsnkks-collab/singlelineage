"""LOCAL test companion, with the run400 native pet UI behind a second opt-in.

Raw0 CS0960 summon/dismiss is a per-instance test-kit meaning (run40 producer),
not an official summoning item. Resurrection uses classic28 and the run393
targeted CS0960 shape. Commands and spell calculations are LOCAL
backend policies. SpellExp gates the unconfirmed display recipe. No automatic
learning, login resurrection, second resource ledger, or dedicated timer loop.
"""
from __future__ import annotations

from dataclasses import replace
import json
import math
import os
from pathlib import Path
import struct

from tools.local_entry_server import protobuf as pb
from tools.local_original_session.world_bridge import need
from tools.local_original_session.world_companion import CompanionRecord, CompanionStore

TOKEN_NAME = '동료 소환/해산'.encode('utf-8')


def companion_revive_frame(entity, look, *, experiment=False):
    """run404: default same-UID replacement, optional in-place DefaultAction.

    4F16 f2/f3 use this actor's selected stance/sprite as LOCAL candidates;
    required f4=0 is an explicit experiment, not an official field value.
    """
    if not experiment:
        from tools.local_original_session.world_visibility import companion_spawn_frame
        return companion_spawn_frame(entity, look)
    body = b''.join(pb.encode_uint32(n, value) for n, value in (
        (1, entity.uid), (2, look.get('stance', 50)), (3, look['sprite_id']), (4, 0)))
    return struct.pack('<HH', len(body) + 6, 0x4f16) + body + b'\0\0'


def _companion_revive_target(ctx, uid, member_uid):
    """Admit only this living owner's visible retained dead companion."""
    actor = _companion_owned_actor(ctx, uid, member_uid)
    record = actor.record
    record.validate()
    need(ctx.world.companions.active.get(record.character_id) is actor
         and not record.alive and record.hp == 0
         and not ctx.world.entities.get(member_uid).alive,
         'COMPANION_DEAD_MEMBER_REQUIRED')
    need(ctx.world.combat.can_be_attacked(uid), 'COMPANION_LIVING_OWNER_REQUIRED')
    return actor


def _companion_revive(ctx, uid, record, *, hp_divisor=4):
    """Publish one accepted targeted scroll effect; caller saves its cost first.

    LOCAL HP=max(1,maxHP//4), following normal L1J40089 NPC/pet resurrection
    (C_ItemUSe.java:1016-1019). MP, growth and settings stay unchanged. The
    Player appearance does not turn this autonomous companion into a PC Y/N
    resurrection recipient. Login restores a missing corpse without reviving it.
    """
    view = ctx.world
    actor = view.companions.active.get(record.character_id)
    need(actor is not None, 'COMPANION_CURRENT_CORPSE_REQUIRED')
    _companion_revive_target(ctx, uid, actor.ref.uid)
    entity = view.entities.get(actor.ref.uid)
    wire = companion_revive_frame(entity, view.companion_looks[record.character_id],
        experiment=ctx._companion_revive_exp)
    watchers = tuple(view._watchers(entity))
    actor = view.companions.revive(record.character_id, view.runtime.clock(),
                                  hp=max(1, record.max_hp // hp_divisor))
    # Persist the life before publishing its replacement/in-place packet.
    try:
        ctx._companion_save(uid)
    finally:
        # Preserve an uncertain absolute save and finish this accepted life;
        # the spent scroll is never retried or refunded after a save failure.
        for watcher in watchers:
            view._queue(watcher, wire)
        for watcher in view.pcs:
            for frame in view._refresh(watcher):
                view._queue(watcher, frame)
        view.companion_ai.start(actor.ref, view.runtime.clock())
        view._announce()
    return actor


class CompanionMagic:
    """Stage4/5 LOCAL consumer on CompanionAI's existing serialized callback.

    Learning remains explicit saved state. Public base MP is selected as LOCAL
    actual debit (no inferred dynamic reductions). LOCAL cast cadence is 1s,
    not an assertion about official reuse or native animation duration.
    Display candidates: REA399/401, action18 attack /19 support, gfx744/221.
    EnergyBolt projectile is deliberately unsupplied: f6 and raw A/B UNKNOWN.
    """
    def __init__(self, view, catalog, growth, policy, attributes, *, display=False):
        self.view, self.growth, self.policy = view, growth, policy
        self.spells = {s['id']: s for s in catalog['spells']
                       if s['id'] in ('energy_bolt', 'heal', 'shield')}
        self.bonus = catalog['formula_policies']['l1j_healing']['magic_bonus_by_int_0_to_50']
        self.attributes, self.display = attributes, display
        self.cooldowns = {}  # same-server dismiss/resummon cannot reset reuse
        self.events = []  # bounded development observations, no request-time I/O

    def eligible(self, rt, name):
        spell = self.spells[name]
        return (spell['classic_key']['value'] in rt.record.learned_spells
                and rt.record.level >= spell['learn_level_mage']['value'])

    def cost(self, name):
        return self.spells[name]['mp_cost']['value']

    def event(self, rt, name, now, **values):
        self.events.append(dict(actor=rt.ref.uid, spell=name, at=now, **values))
        del self.events[:-64]

    def regen(self, rt, now):
        timing = self.growth['mp_regeneration']['timing']
        if rt.regen_at is None:
            rt.regen_at = now + timing['tick_ms'] / 1000
        if now < rt.regen_at:
            return
        # Late callbacks give one real event, never offline/catch-up resources.
        rt.regen_at = now + timing['tick_ms'] / 1000
        rt.regen_points += rt.regen_activity
        rt.regen_activity = timing['points_per_tick']['idle_or_standing']
        if rt.regen_points < timing['threshold_points']:
            return
        rt.regen_points = 0
        record = rt.record
        wis = self.attributes[rt.character_id][3]
        bags = getattr(self.view.companion_ai, 'inventory', None)
        base = 3 if wis >= 17 else 2 if wis >= 15 else 1
        original = 3 if wis == 18 else 2 if wis >= 16 else 1 if wis >= 14 else 0
        if bags is not None and now < bags.blue_until.get(rt.character_id, 0):
            base += max(wis, 11) - 5
        # Selected local baseline has no food/weight owner yet. No gear/effect
        # MPR is inferred. Supplied equipment gates use the documented units.
        burden = (record.equipment.get('weight240', 0) if bags is None else
                  bags.calculated(rt.character_id)[0].weight.gauge)
        if record.equipment.get('food', 40) < 3 or burden >= 120:
            base = original = 0
        before = record.mp
        record.mp = min(record.max_mp, record.mp + base + original)
        if record.mp != before:
            self.event(rt, 'recover', now, mp_before=before, mp_after=record.mp)
            self.view._save_companion(rt.owner_ref.uid)

    def position(self, rt, actor, target, name, now):
        ai = self.view.companion_ai
        limit = self.spells[name]['range_tiles']['value'] or 0
        from tools.local_original_session.npc_ai import distance, local_line_clear
        def reached(x, y):
            owner = self.view.entities.resolve(rt.owner_ref)
            return (owner is not None and distance(x, y, owner.x, owner.y) <= ai.owner_leash
                and distance(x, y, target.x, target.y) <= limit
                and local_line_clear(self.view.terrain, actor.map_id, x, y, target.x, target.y))
        if reached(actor.x, actor.y):
            rt.position_key = None
            return True
        if rt.record.movement_mode == 'HOLD':
            rt.action = 'HOLD'
            return False
        failure = self.policy['thresholds']['failure']
        owner = self.view.entities.resolve(rt.owner_ref)
        key = (name, target.ref)
        geometry = (target.x, target.y, owner.x, owner.y)
        snapshot = key + geometry + (actor.x, actor.y)
        if rt.position_failed == snapshot or now < rt.position_retry_at:
            return False
        if rt.position_key != key:
            rt.position_key, rt.position_started, rt.position_attempts = key, now, 0
        rt.action = 'POSITION'
        exhausted = (now - rt.position_started >= failure['position_budget_seconds']
                     or rt.position_attempts >= failure['position_step_attempt_limit'])
        moved = False if exhausted else ai._move(rt, actor, reached, (target.x, target.y), now,
            tile_allowed=lambda x, y: distance(x, y, owner.x, owner.y) <= ai.owner_leash)
        if moved is not None:
            rt.position_attempts += 1
        if moved is False:
            rt.position_failed = key + geometry + (actor.x, actor.y)
            rt.position_retry_at = now + failure['minimum_retry_seconds']
            rt.position_key = None
            rt.action = 'RETURN'
            if name == 'energy_bolt':
                rt.target = None
            self.event(rt, 'position_abandoned', now, candidate=name)
            return False
        return None  # one bounded movement consumed this decision

    def display_cast(self, rt, actor, target, name):
        if not self.display:
            return
        from tools.local_original_session.npc_ai import heading_to
        kind = 18 if name == 'energy_bolt' else 19
        from tools.local_original_session import attack
        body = b''.join(attack._field(n, value) for n, value in (
            (1, kind), (2, actor.uid), (3, target.uid), (4, 0),
            (5, heading_to(actor.x, actor.y, target.x, target.y))))
        wires = [struct.pack('<HH', len(body) + 6, 0x4e31) + body + b'\0\0']
        gfx = {'heal': 744, 'shield': 221}.get(name)
        if gfx is not None:
            body = pb.encode_uint32(1, target.uid) + pb.encode_uint32(2, gfx)
            wires.append(struct.pack('<HH', len(body) + 6, 0x4ed8) + body + b'\0\0')
        for uid in set(self.view._watchers(actor)) | set(self.view._watchers(target)):
            for wire in wires:
                self.view._queue(uid, wire)

    def cast(self, rt, actor, target, name, now):
        from tools.local_original_session import world_combat as combat
        # Revalidate current generations/commands at this single commit point.
        view, record = self.view, rt.record
        if (view.companions.get_actor(actor.uid) is not rt
                or view.entities.resolve(target.ref) is not target
                or not view.companions.can_be_attacked(actor.uid)
                or not target.alive or target.map_id != actor.map_id
                or not self.eligible(rt, name)
                or now < max(rt.next_cast_at, self.cooldowns.get(rt.character_id, 0))
                or record.mp < self.cost(name)):
            return False
        if name != 'energy_bolt' and not record.support_enabled:
            return False
        if name == 'energy_bolt' and (record.combat_mode == 'PASSIVE' or rt.target != target.ref):
            return False
        bags = getattr(view.companion_ai, 'inventory', None)
        if bags is not None and bags.calculated(rt.character_id)[0].weight.normal_skill_blocked:
            return False
        if ((name == 'heal' and target.ref != rt.owner_ref)
                or (name == 'shield' and target.ref != rt.ref)):
            return False
        from tools.local_original_session.npc_ai import distance, local_line_clear
        limit = self.spells[name]['range_tiles']['value'] or 0
        if (distance(actor.x, actor.y, target.x, target.y) > limit
                or not local_line_clear(view.terrain, actor.map_id, actor.x, actor.y, target.x, target.y)):
            return False
        if name == 'energy_bolt' and view.companion_ai._hostile(rt, target.ref) is not target:
            return False
        if name != 'heal':
            reserve = max(record.mp_reserve,
                self.policy['thresholds']['mp']['heal_reserve_casts'] * self.cost('heal')
                if record.support_enabled and self.eligible(rt, 'heal') else 0)
            if record.mp - self.cost(name) < reserve:
                return False
        intelligence = self.attributes[rt.character_id][5]
        spell = self.spells[name]
        amount = 0
        found = view.spawner.slot_for(target.uid) if name == 'energy_bolt' else None
        if name == 'energy_bolt':
            if found is None or not found[0].active or found[1].hp <= 0:
                return False
            amount = combat.companion_magic_damage(spell['formula']['parameters'], intelligence, view.combat.rng)
        elif name == 'heal':
            owner = view.combat.pcs.get(target.uid)
            if owner is None or owner.dead or owner.hp >= owner.max_hp:
                return False
            amount = combat.companion_magic_heal(spell['formula']['parameters'], intelligence,
                0, self.bonus, view.combat.rng)  # LOCAL neutral caster lawful baseline
        before = record.mp
        record.mp -= self.cost(name)
        rt.next_cast_at = now + 1.0  # explicit LOCAL cadence, not official reuse
        self.cooldowns[rt.character_id] = rt.next_cast_at
        rt.regen_activity = min(rt.regen_activity, 1)
        rt.action = 'CAST'
        self.display_cast(rt, actor, target, name)
        if name == 'energy_bolt':
            group, slot = found
            view._apply_monster_swing(rt.owner_ref.uid, actor.uid, target, group.monster,
                slot.hp, combat.Swing(True, amount), now)
            view._announce()
        elif name == 'heal':
            amount, wire = combat.apply_companion_heal(view.combat, target.uid, amount)
            view._queue(target.uid, wire)
        else:
            rt.shield_until = now + spell['duration_seconds']['value']
        self.event(rt, name, now, target=target.uid, mp_before=before, mp_after=record.mp,
                   amount=amount, shield_until=rt.shield_until)
        view._save_companion(rt.owner_ref.uid)
        return True

    def step(self, rt, actor, owner, hostile, now, returning):
        rt.next_cast_at = max(rt.next_cast_at, self.cooldowns.get(rt.character_id, 0))
        self.regen(rt, now)
        if rt.shield_until and now >= rt.shield_until:
            rt.shield_until = 0
            self.event(rt, 'shield_expired', now)
        record = rt.record
        hp_policy = self.policy['thresholds']['hp']
        state = self.view.combat.pcs[owner.uid]
        ratio = state.hp / state.max_hp
        if ratio <= hp_policy['owner_emergency_enter']:
            rt.emergency_owner = True
        elif ratio >= hp_policy['emergency_exit']:
            rt.emergency_owner = False
        heal = record.support_enabled and self.eligible(rt, 'heal')
        if heal and rt.emergency_owner and record.mp >= self.cost('heal'):
            position = self.position(rt, actor, owner, 'heal', now)
            if position is None:
                return True
            if position and now >= rt.next_cast_at:
                return self.cast(rt, actor, owner, 'heal', now)
            if position:  # a pending urgent heal keeps its priority during reuse
                return True
        attack = self.eligible(rt, 'energy_bolt')
        reserve_policy = self.policy['thresholds']['mp']
        reserve = max(record.mp_reserve,
            reserve_policy['heal_reserve_casts'] * self.cost('heal') if heal else 0)
        resume = max(reserve + self.cost('energy_bolt'),
                     math.ceil(reserve_policy['recover_fraction'] * record.max_mp))
        if rt.recovering and record.mp >= resume:
            rt.recovering = False
        buff = record.support_enabled and self.eligible(rt, 'shield')
        duration = self.spells['shield']['duration_seconds']['value']
        bp = self.policy['thresholds']['buff']
        lead = min(bp['refresh_lead_cap_seconds'], duration * bp['refresh_lead_duration_fraction'])
        # Short effects cannot rearm above lead+hysteresis: wait for expiry.
        due = not rt.shield_until or (duration > lead + bp['refresh_hysteresis_seconds']
                                     and rt.shield_until - now <= lead)
        if buff and due and not rt.recovering and record.mp - self.cost('shield') >= reserve:
            if now >= rt.next_cast_at:
                return self.cast(rt, actor, actor, 'shield', now)
            return True
        if attack and hostile is not None and not returning:
            if record.mp - self.cost('energy_bolt') < reserve:
                rt.recovering = True
            if rt.recovering:
                rt.action = 'RECOVER'
                return True  # rest in place; no offensive/basic attack fallback
            position = self.position(rt, actor, hostile, 'energy_bolt', now)
            if position and now >= rt.next_cast_at:
                self.cast(rt, actor, hostile, 'energy_bolt', now)
            return True
        if rt.emergency_owner and heal and record.mp < self.cost('heal'):
            rt.action = 'RECOVER'
            return True
        return False


def _companion_initialize(ctx):
    ctx._companion_enabled = os.environ.get('SL_COMPANION') == '1'
    ctx._companion_pet_ui = ctx._companion_enabled and os.environ.get('SL_COMPANION_PET_UI') == '1'
    ctx._companion_revive_exp = os.environ.get('SL_COMPANION_REVIVE_EXP') == '1'
    ctx._companion_store = None
    ctx._companion_inventory = None
    ctx._companion_supplies = []
    ctx._companion_roster = {}
    ctx._companion_rows = {}
    ctx._companion_windows = {}
    ctx._companion_pet_modes = {}
    ctx._companion_errors = []
    ctx._companion_item_effects = {}
    if not ctx._companion_enabled:
        return
    from tools.local_original_session.world_item_effects import load_effects
    ctx._companion_item_effects = load_effects(owner='companion')
    need('manual-user-play' not in str(ctx.realm.store.path).lower(), 'COMPANION_TEST_PROFILE_REQUIRED')
    path = Path(__file__).parent / 'data' / 'companion' / 'mage_growth.json'
    ctx._companion_growth = json.loads(path.read_text(encoding='utf-8'))
    ctx._companion_spells = json.loads(path.with_name('mage_spells.json').read_text(encoding='utf-8'))
    ctx._companion_policy = json.loads(path.with_name('ai_policy.json').read_text(encoding='utf-8'))
    starter = json.loads((Path(__file__).parent / 'data' / 'm1' / 'starter.json').read_text(encoding='utf-8'))
    ctx._companion_supplies = [entry['value'] for entry in
        starter.get('kits', {}).get('test_knight', {}).get('companion_supplies', [])]
    ctx._companion_store = CompanionStore(ctx.realm.store.path)
    ctx.world.companion_save = ctx._companion_save


def _companion_started(ctx):
    if not ctx._companion_enabled:
        return
    ctx.realm._world_companion_record = ctx.world.companions.records.get
    from tools.local_original_session import world_combat
    from tools.local_native_login_local_ack_hook import ack_enter_world as ack
    rows = ctx.realm.store._read()['characters']
    owner = next((r for r in rows if r['class'] == 1), None)
    need(owner is not None, 'COMPANION_TEST_KNIGHT_REQUIRED')
    if not any(r['class'] == 3 for r in rows):
        stats = ctx._companion_growth['local_build']['creation_original_stats']
        ctx.realm.store.create(ack.realm.Creation('SoloMage', 3, 0,
            tuple(stats[key] for key in ('STR', 'DEX', 'CON', 'WIS', 'CHA', 'INT'))))
        rows = ctx.realm.store._read()['characters']
    account = 'owned-local-test'
    roster = {r['uid']: dict(account_id=account, class_id=r['class']) for r in rows}
    ctx._companion_roster = roster
    ctx._companion_rows = {r['uid']: r for r in rows}
    ctx.world.companion_ai.magic = CompanionMagic(ctx.world, ctx._companion_spells,
        ctx._companion_growth, ctx._companion_policy,
        {r['uid']: r['attributes'] for r in rows}, display=os.environ.get('SL_SPELL_EXP') == '1')
    saved = {r['character_id']: r for r in ctx._companion_store.payload['records']}
    for row in rows:
        if row['class'] != 3:
            continue
        if row['uid'] in saved:
            record = CompanionRecord(**saved[row['uid']])
            record.learned_spells = tuple(record.learned_spells)
        else:
            initial = ctx._companion_growth['initial_resources']
            progress = ctx._world_progress.get(row['uid'])
            hp = progress.max_hp or initial['hp']['max']
            mp = progress.max_mp if progress.max_mp is not None else (8 if row['attributes'][3] >= 16 else 6)
            record = CompanionRecord(row['uid'], owner['uid'], account,
                level=progress.level, exp=progress.exp, hp=hp, mp=mp, max_hp=hp, max_mp=mp,
                equipment={'weapon_template': 230})
        ctx.world.companions.register(record, roster=roster)
        ctx.world.companion_owner_half.setdefault(record.owner_character_id, 0)
        stats = row['attributes']
        weapon_id = record.equipment.get('weapon_template')
        weapon = (world_combat.FIST if weapon_id is None else
                  world_combat.weapon_from_item(ctx.world.data.items[weapon_id]))
        ctx.world.companion_profiles[row['uid']] = world_combat.PcProfile(
            record.level, 3, row['gender'], stats[0], stats[1], weapon=weapon,
            con=stats[2], wis=stats[3])
        ctx.world.companion_looks[row['uid']] = dict(name=row['name'], gender=row['gender'],
            sprite_id=734 if row['gender'] == 0 else 1186,
            stance=50 if weapon_id == 230 else 0,
            owner_name=ctx._companion_rows[record.owner_character_id]['name'])
    for uid, progress in ctx._companion_store.payload['owners'].items():
        ctx.world.companion_owner_half[int(uid)] = progress['exp_half']
    from tools.local_original_session import inventory
    if ctx._inventory_kit_policy == inventory.KIT_POLICY:
        from tools.local_original_session.world_feature_trade import CompanionInventory
        ctx._companion_inventory = CompanionInventory(ctx)
        for uid in ctx.world.companions.records:
            ctx._companion_inventory.initialize(uid)
        ctx.world.companion_ai.inventory = ctx._companion_inventory
        ctx.world.combat.companion_inventory = ctx._companion_inventory
    # Old record.equipment is legacy metadata only; normal equipment.json is
    # now the sole worn-item authority, exactly as for direct player selection.
    for record in ctx.world.companions.records.values():
        record.equipment = {key: value for key, value in record.equipment.items()
                            if key not in ('weapon_template', 'slots', 'weight240')}


def _companion_save(ctx, owner_uid, receipt=None):
    if ctx._companion_store is not None:
        # Quit/Restart also save after the last natural world tick, even if no
        # further player request ran the ordinary inventory/status hook.
        for uid, record in ctx.world.companions.records.items():
            state = ctx.world.combat.pcs.get(uid)
            if state is not None:
                record.hp, record.mp = state.hp, state.mp
                record.alive = state.hp > 0
                record.level, record.exp = state.profile.level, ctx.world.exp[uid]
                record.max_hp, record.max_mp = state.max_hp, state.max_mp
        bags = getattr(ctx, '_companion_inventory', None)
        if bags is not None:
            for uid, record in ctx.world.companions.records.items():
                if uid in bags.frames and ctx.world.companion_profiles[uid].level != record.level:
                    bags.refresh(uid, publish=False)
        refs = {actor.ref for actor in ctx.world.companions.active.values()}
        uids = {ref.uid for ref in refs}
        for key, ref in tuple(ctx._companion_windows.items()):
            if ref not in refs:
                ctx._companion_windows.pop(key, None)
        for uid in tuple(ctx._companion_pet_modes):
            if uid not in uids:
                ctx._companion_pet_modes.pop(uid, None)
        ctx._companion_store.commit(ctx.world, owner_uid, receipt)


async def _companion_before_enter(ctx, writer, row, game, operation_lock):
    if ctx._companion_enabled:
        uid = ctx.realm.service(writer).snapshot().uid
        # Retire autonomous lifetime before the character entity is activated.
        await ctx.world.runtime.dispatch_now(ctx.world.companions.dismiss, uid)


async def _companion_enter(ctx, writer, row, game, operation_lock):
    if not ctx._companion_enabled or not ctx._world_bound(writer):
        return
    uid = ctx._world_pcs[id(writer)][1]

    def enter():
        # Joint file is authoritative over its ordinary progression projection.
        # No live file read, HP refill or runtime identity restore occurs here.
        canonical = ctx._companion_store.pending or ctx._companion_store.payload
        saved = canonical['owners'].get(str(uid))
        if saved is not None:
            state = ctx.world.combat.pcs[uid]
            ctx.world.exp[uid] = saved['exp']
            state.profile = replace(state.profile, level=saved['level'])
            state.max_hp = saved['max_hp']
            state.status_fields.update({2: saved['level'], 11: saved['max_hp'],
                13: saved['max_mp'], 18: saved['lawful']})
            ctx._world_lawful[uid] = saved['lawful']
            from tools.local_original_session.world_progress import Progress, exp_percent
            state.status_fields[26] = exp_percent(ctx.world.data, saved['exp'], saved['level'])
            ctx._world_recalculate_uid(uid)
            ctx.world.progress_dirty[uid] = Progress(saved['exp'], saved['level'],
                saved['max_hp'], saved['max_mp'], saved['lawful'])
            from tools.local_original_session.world_status_frames import full_status_frame
            ctx.world._queue(uid, full_status_frame(state.status_fields))
        active = [rt for rt in ctx.world.companions.active.values() if rt.owner_ref.uid == uid]
        members = [r for r in ctx.world.companions.records.values()
                   if r.owner_character_id == uid]
        if members and not active:
            _companion_restore(ctx, uid, members[0].character_id)
        return ctx.world.drain(uid)
    frames = await ctx.world.runtime.dispatch_now(enter)
    await ctx._world_send(writer, row, frames, operation_lock)


def _companion_show_corpses(ctx):
    """run404: a newly visible corpse needs Player spawn then raw8 death.

    Walking only changes visibility; it never moves the retained corpse.
    WorldView's generic dead-NPC refresh intentionally excludes unknown dead
    actors, so companion publication belongs to this feature.
    """
    from tools.local_original_session.world_visibility import companion_spawn_frame, in_screen
    from tools.local_original_session import player_life_codec
    view = ctx.world
    for actor in view.companions.active.values():
        if actor.record.alive:
            continue
        corpse = view.entities.get(actor.ref.uid)
        if corpse is None:
            continue
        for watcher, (map_id, x, y) in view.pcs.items():
            known = view.visibility.known.setdefault(watcher, set())
            if (map_id == corpse.map_id and in_screen(x, y, corpse.x, corpse.y)
                    and corpse.uid not in known):
                known.add(corpse.uid)
                view._queue(watcher, companion_spawn_frame(corpse,
                    view.companion_looks[actor.character_id]))
                view._queue(watcher, player_life_codec.death(corpse.uid))
    view._announce()


def _companion_restore(ctx, uid, character_id):
    view = ctx.world
    record = view.companions.records[character_id]
    if record.alive:
        return view.summon_companion(character_id, uid)
    from tools.local_original_session.npc_ai import DELTAS
    from tools.local_original_session.world_entities import Kind
    owner = view.entities.get(uid)
    need(owner is not None and uid in view.pcs and view.combat.can_be_attacked(uid)
         and record.owner_character_id == uid, 'COMPANION_SELECTED_LIVING_OWNER_REQUIRED')
    need(not any(rt.owner_ref.uid == uid for rt in view.companions.active.values()),
         'COMPANION_ONE_ACTIVE_MEMBER_REQUIRED')
    for heading, (dx, dy) in enumerate(DELTAS):
        x, y = owner.x + dx, owner.y + dy
        if (view.terrain is not None
                and view.terrain.can_step(owner.map_id, owner.x, owner.y, heading) is True
                and not any(e.kind is not Kind.ITEM for e in view.entities.near(
                    owner.map_id, x, y, 0, alive_only=False))):
            actor = view.companions.restore_corpse(character_id, uid, owner.map_id, x, y,
                now=view.runtime.clock(), heading=owner.heading)
            _companion_show_corpses(ctx)
            view._save_companion(uid)
            return actor
    raise ValueError('COMPANION_FREE_SPAWN_TILE_REQUIRED')


def _companion_relocate_depart(ctx, uid):
    """End old-map actor/target/timer lifetimes; preserve only saved members."""
    members = tuple(actor for actor in ctx.world.companions.active.values()
                    if actor.owner_ref.uid == uid)
    for actor in members:
        ctx.world.companions.dismiss(actor.character_id)
    return members


def _companion_relocate_arrive(ctx, uid, members):
    for previous in members:
        actor = _companion_restore(ctx, uid, previous.character_id)
        # Relocation clears targets/reservations, not already earned cooldowns.
        for field in ('next_move_at', 'next_attack_at', 'next_cast_at', 'shield_until'):
            setattr(actor, field, getattr(previous, field))
    return tuple(ctx.world.drain(uid))


def _companion_after_move(ctx, writer, row, game, operation_lock):
    if getattr(ctx, '_companion_enabled', False):
        _companion_show_corpses(ctx)


async def _companion_kit(ctx, writer, row, game, opcode, operation_lock):
    from tools.local_original_session import inventory
    if (not ctx._companion_enabled or not ctx._world_bound(writer)
            or ctx._inventory_kit_policy != inventory.KIT_POLICY
            or row.get('_companion_token_sent')):
        return
    # The manual native-inventory lane publishes current_frame only after its
    # initial drain, and equipment sync still owns that initial frame until it
    # finishes. Reuse its existing readiness rule; never mutate its input early.
    if type(ctx.inventory_frame) is not bytes:
        return
    effect = getattr(ctx, '_item_equipment_effect', None)
    if effect is not None:
        from tools.local_original_session.world_feature_kit import defer_equipment_prepare
        if defer_equipment_prepare(ctx.broker, getattr(effect, '_selection', None)):
            return
    uid = ctx._world_pcs[id(writer)][1]
    if not any(r.owner_character_id == uid for r in ctx.world.companions.records.values()):
        return
    current = ctx.inventory_frame
    items = inventory.validate_kit_frame(current)
    # The exact blue-potion metadata is loaded once at startup. It is kept in
    # starter.json beside the named test kit without extending the global M1
    # catalog owned by another worker. These are ordinary player bag items.
    if ctx._world_starter_kit == 'test_knight' and not any(
            dict(r.raw_fields).get(18) == TOKEN_NAME for r in items):
        for supply in ctx._companion_supplies:
            if not any(r.template_bits == supply['item'] for r in items):
                fields = dict(ctx.starter_fields)
                fields.update({1: max(r.identifier for r in items) + 1,
                    2: supply['item'], 4: supply['count'], 5: 0, 7: supply['icon']})
                after = inventory.build_kit_frame([dict(r.raw_fields) for r in items] + [fields])
                ctx.inventory_store.replace_kit(uid, current, after, append=True)
                ctx.inventory_frame = current = after
                items = inventory.validate_kit_frame(current)
                await ctx._world_send(writer, row, (inventory.build_add(fields),), operation_lock)
    token = next((r for r in items if dict(r.raw_fields).get(18) == TOKEN_NAME), None)
    if token is None:
        fields = dict(ctx.starter_fields)
        # Known template1, distinct UID, explicit raw0 instance. Its test meaning
        # is named per-instance; ordinary Athame equipment remains unchanged.
        fields.update({1: max(r.identifier for r in items) + 1, 2: 1, 4: 1,
                       5: 0, 7: ctx.world.data.items[1].icon, 18: TOKEN_NAME})
        after = inventory.build_kit_frame([dict(r.raw_fields) for r in items] + [fields])
        need(ctx.inventory_store.replace_kit(uid, current, after, append=True) is True,
             'COMPANION_KIT_PERSISTED_CHANGE_REQUIRED')
        ctx.inventory_frame = after
        await ctx._world_send(writer, row, (inventory.build_add(fields),), operation_lock)
    row['_companion_token_sent'] = True


def _companion_status_frame(ctx, actor):
    record = actor.record
    mode = ctx._companion_pet_modes.get(actor.ref.uid,
        4 if record.combat_mode == 'PASSIVE' else 3 if record.combat_mode == 'DEFEND' else 2)
    child = b''.join(pb.encode_uint32(n, value) for n, value in (
        (1, mode), (2, record.max_hp), (3, record.hp),
        (4, record.max_mp), (5, record.mp), (6, record.level)))
    from tools.local_original_session.world_progress import exp_percent
    child += b'\x51' + struct.pack('<d', exp_percent(ctx.world.data, record.exp, record.level))
    body = pb.encode_uint32(1, actor.ref.uid) + pb.encode_uint32(2, 1) + pb.encode_bytes(3, child)
    return struct.pack('<HH', len(body) + 6, 0x4f14) + body + b'\0\0'


def _companion_owned_actor(ctx, uid, member_uid, *, living=False):
    actor = ctx.world.companions.retained_actor(member_uid)
    owner, entity = ctx.world.entities.get(uid), ctx.world.entities.get(member_uid)
    need(actor is not None and owner is not None and entity is not None
         and actor.owner_ref == owner.ref and actor.record.owner_character_id == uid
         and entity.map_id == owner.map_id, 'COMPANION_CURRENT_OWNED_ACTOR_REQUIRED')
    need(not living or ctx.world.companions.can_be_attacked(member_uid), 'COMPANION_LIVING_ACTOR_REQUIRED')
    from tools.local_original_session.world_visibility import in_screen
    need(in_screen(owner.x, owner.y, entity.x, entity.y), 'COMPANION_VISIBLE_ACTOR_REQUIRED')
    return actor


async def _companion_frame(ctx, writer, row, game, frame, operation_lock):
    if (not ctx._companion_enabled or not ctx._world_bound(writer)
            or ctx._world_ready(writer, game) is None):
        return False
    if frame.opcode in (0x4f13, 0x4f02) and not ctx._companion_pet_ui:
        return False
    uid = ctx._world_pcs[id(writer)][1]
    attempted = False
    try:
        with pb.parse_message(frame.payload, limits=pb.WireLimits(
                max_body=4096, max_fields=4, max_field_bytes=2048)) as message:
            fields = {n: message.occurrences(n) for n in (1, 2, 3)}
            if frame.opcode == 0x0960:
                from tools.local_original_session import inventory
                if not (len(message.fields) == 2 and len(fields[1]) == len(fields[2]) == 1
                        and fields[1][0].wire_type == 0 and fields[2][0].wire_type == 2):
                    return False
                item = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                    if r.identifier == fields[1][0].value), None)
                if item is None:
                    return False
                resurrection = ctx._companion_item_effects.get(item.template_bits)
                if resurrection is None and dict(item.raw_fields).get(18) != TOKEN_NAME:
                    return False
                need(dict(item.raw_fields)[4] > 0, 'COMPANION_OWNED_KIT_REQUIRED')
                with pb.parse_message(bytes(fields[2][0].value)) as params:
                    expected = {1: 1, 15: 0, 16: 0}
                    if resurrection is not None:
                        expected[3] = 0
                        need(len(params.occurrences(2)) == 1, 'COMPANION_TARGET_UID_REQUIRED')
                        target_uid = params.occurrences(2)[0].value  # run393 int64 varint
                        need(type(target_uid) is int and 0 < target_uid < (1 << 63),
                             'COMPANION_TARGET_UID_REQUIRED')
                        expected[2] = target_uid
                    need(len(params.fields) == len(expected)
                         and all(len(params.occurrences(n)) == 1 for n in expected)
                         and {f.number: f.value for f in params.fields} == expected
                         and all(f.wire_type == 0 for f in params.fields),
                         'COMPANION_TARGETED_PARAMS_REQUIRED' if resurrection is not None
                         else 'COMPANION_RAW0_PARAMS_REQUIRED')
                command = ('resurrect', target_uid, item.identifier, item.template_bits) if resurrection else ('toggle',)
            elif frame.opcode == 0x4f13:
                need(len(message.fields) == len(fields[1]) == 1 and fields[1][0].wire_type == 0,
                     'COMPANION_PET_QUERY_FIELDS_REQUIRED')
                command = ('query', fields[1][0].value)
            else:
                need(len(fields[1]) == len(fields[3]) == 1 and fields[1][0].wire_type == 0
                     and fields[3][0].wire_type == 0 and all(f.wire_type == 2 for f in fields[2])
                     and len(message.fields) == 2 + len(fields[2]), 'COMPANION_PET_COMMAND_FIELDS_REQUIRED')
                command = ('pet', fields[3][0].value, fields[1][0].value,
                           tuple(bytes(f.value) for f in fields[2]))

        def apply():
            nonlocal attempted
            need(ctx.realm.registry.resolve(writer) is game and ctx._world_bound(writer)
                 and ctx.owner_current(writer, row, ctx.realm.service(writer).snapshot()),
                 'COMPANION_CURRENT_SELECTED_OWNER_REQUIRED')
            need(ctx.world.combat.can_be_attacked(uid), 'COMPANION_LIVING_OWNER_REQUIRED')
            actor = None
            cost = ()
            if command[0] == 'resurrect':
                actor = _companion_revive_target(ctx, uid, command[1])
                # Recheck the stack inside the same serialized world callback.
                current = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                    if r.identifier == command[2]), None)
                need(current is not None and current.template_bits == command[3]
                     and dict(current.raw_fields)[4] > 0, 'COMPANION_OWNED_SCROLL_REQUIRED')
                definition = ctx._companion_item_effects[current.template_bits]
                attempted = True
                cost = (ctx._world_consume_kit(writer, current.identifier),)
                _companion_revive(ctx, uid, actor.record, hp_divisor=definition.revive_hp_divisor)
            elif command[0] == 'toggle':
                active = [rt for rt in ctx.world.companions.active.values() if rt.owner_ref.uid == uid]
                need(not active or active[0].record.alive, 'COMPANION_TARGETED_SCROLL_REQUIRED')
                if active:
                    for rt in active:
                        ctx.world.companions.dismiss(rt.character_id)
                    ctx._companion_windows.pop(id(writer), None)
                else:
                    living = next((r for r in ctx.world.companions.records.values()
                        if r.owner_character_id == uid and r.alive), None)
                    if living is not None:
                        actor = ctx.world.summon_companion(living.character_id, uid)
                    else:
                        need(False, 'COMPANION_TARGETED_SCROLL_REQUIRED')
            else:
                actor = _companion_owned_actor(ctx, uid, command[1], living=command[0] == 'pet')
                if command[0] == 'pet':
                    need(ctx._companion_windows.get(id(writer)) == actor.ref, 'COMPANION_DRAINED_PET_WINDOW_REQUIRED')
                    mode, targets = command[2:]
                    need(mode in (1, 2, 3, 4, 8), 'COMPANION_PET_COMMAND_UNSUPPORTED')
                    need(len(targets) == (1 if mode == 1 else 0), 'COMPANION_PET_TARGET_FIELDS_REQUIRED')
                    now = ctx.world.runtime.clock()
                    if mode == 8:
                        ctx.world.companions.dismiss(actor.character_id, now)
                        ctx._companion_windows.pop(id(writer), None)
                        actor = None
                    else:
                        target = None
                        if mode == 1:
                            text = targets[0].decode('ascii')
                            need(text.isdecimal() and str(int(text)) == text, 'COMPANION_PET_DECIMAL_TARGET_REQUIRED')
                            target = ctx.world.entities.get(int(text))
                            need(target is not None and target.uid in ctx.world.visibility.known.get(uid, ())
                                 and ctx.world.companion_ai._hostile(actor, target.ref) is target,
                                 'COMPANION_PET_CURRENT_HOSTILE_TARGET_REQUIRED')
                        ctx.world.companions.set_commands(actor.character_id,
                            movement_mode='HOLD' if mode == 4 else 'FOLLOW',
                            combat_mode={1: 'ASSIST', 2: 'ASSIST', 3: 'DEFEND', 4: 'PASSIVE'}[mode], now=now)
                        ctx.world.companion_ai.command_changed(actor.ref, now)
                        if target is not None:
                            ctx.world.companion_ai._select(actor, target.ref, now)
                        ctx._companion_pet_modes[actor.ref.uid] = mode
            if command[0] != 'resurrect':
                ctx._companion_save(uid)
            frames = list(cost) + ctx.world.drain(uid)
            if actor is not None and command[0] in ('query', 'pet'):
                frames.append(_companion_status_frame(ctx, actor))
            return frames, None if actor is None else actor.ref
        frames, ref = await ctx.world.runtime.dispatch_now(apply)
        await ctx._world_send(writer, row, frames, operation_lock)
        if command[0] == 'query':
            ctx._companion_windows[id(writer)] = ref
    except (ValueError, pb.WireError, UnicodeError) as error:
        if attempted:
            raise  # uncertain saved cost/life must not be swallowed or replayed
        ctx._companion_errors = (ctx._companion_errors + [str(error)[:96]])[-8:]
    return True


async def _companion_after_leave(ctx, writer):
    ctx._companion_windows.pop(id(writer), None)


def _companion_player_inventory(ctx, writer, row, game, opcode, operation_lock):
    """Track the real mage's PC inventory changes under the existing session."""
    bags = ctx._companion_inventory
    if bags is None or not ctx._world_bound(writer):
        return
    uid = ctx._world_pcs[id(writer)][1]
    member = ctx.world.companions.records.get(uid)
    if member is None or type(ctx.inventory_frame) is not bytes:
        return
    state = ctx.world.combat.pcs[uid]
    changed = (member.hp, member.mp, member.level, member.exp, member.max_hp, member.max_mp) != (
        state.hp, state.mp, state.profile.level, ctx.world.exp[uid], state.max_hp, state.max_mp)
    bag_changed = bags.frames[uid] != ctx.inventory_frame
    equipment_changed = False
    if bag_changed or opcode == 0x0960:
        saved = bags.equipment.restore(uid, ctx.inventory_frame)
        equipment_changed = saved != bags.states[uid]
        bags.frames[uid], bags.states[uid] = ctx.inventory_frame, saved
    if not changed and not bag_changed and not equipment_changed:
        return
    member.hp, member.mp = state.hp, state.mp
    member.alive = state.hp > 0
    member.level, member.exp = state.profile.level, ctx.world.exp[uid]
    member.max_hp, member.max_mp = state.max_hp, state.max_mp
    if bag_changed or equipment_changed or changed:
        bags.refresh(uid, publish=False)
    ctx._companion_save(member.owner_character_id)


def _companion_stopped(ctx):
    if ctx._companion_store is not None:
        ctx._companion_save(0)


METHODS = (_companion_initialize, _companion_started, _companion_save, _companion_before_enter, _companion_enter,
           _companion_kit, _companion_status_frame, _companion_frame, _companion_after_leave, _companion_stopped,
           _companion_after_move, _companion_player_inventory)
HOOKS = {'initialize': ('_companion_initialize',), 'runtime_started': ('_companion_started',),
         'before_enter': ('_companion_before_enter',),
         'after_enter': ('_companion_enter',), 'after_request': ('_companion_kit', '_companion_player_inventory'),
         'after_move': ('_companion_after_move',),
         'after_leave': ('_companion_after_leave',), 'runtime_stopped': ('_companion_stopped',)}
FRAMES = {opcode: ('_companion_frame',) for opcode in (0x0960, 0x4f13, 0x4f02)}
OUTGOING_OPCODES = (0x4f14, 0x4ed8, 0x4f16)

# Companion is already registered. Compose its bounded GIVE implementation
# here so this worker does not write the shared FEATURE_MODULES registry.
from tools.local_original_session import world_feature_trade as _trade
METHODS += _trade.METHODS
FRAMES.update(_trade.FRAMES)
OUTGOING_OPCODES += _trade.OUTGOING_OPCODES
