"""LOCAL test companion, with the run400 native pet UI behind a second opt-in.

Raw0 CS0960 summon/recall is a LOCAL use of client etc item2070 (unicorn horn),
not an official summoning rule. Resurrection uses classic28; targeted run393
and targetless received CS0960 requests use LOCAL target selection. Commands and spell calculations are LOCAL
backend policies. SpellExp gates the unconfirmed display recipe. No automatic
learning, login resurrection, second resource ledger, or dedicated timer loop.
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import struct

from tools.local_entry_server import protobuf as pb
from tools.local_original_session.world_bridge import need
from tools.local_original_session.world_companion import (
    CompanionRecord, CompanionStore, record_from_row)

LEGACY_TOKEN_NAME = '동료 소환/해산'.encode('utf-8')
TOKEN_TEMPLATE = 2070
TOKEN_NAME = '신성한 유니콘의 뿔'.encode('utf-8')
TOKEN_ICON = 2181


def _companion_legacy_token(item):
    return item.template_bits == 1 and dict(item.raw_fields).get(18) == LEGACY_TOKEN_NAME


def _companion_dead_notice():
    # run392 CHAT_EVIDENCE: code12066 SYSTEM_GM '{}' + one argument is the
    # source-supported LOCAL text candidate. Resource lookup/render UNKNOWN;
    # 4E52's unknown required f5 is deliberately not synthesized.
    body = pb.encode_uint32(1, 12066) + pb.encode_bytes(2,
        '동료가 죽었습니다. 시체에 부활 주문서를 사용하세요.'.encode('utf-8'))
    return struct.pack('<HH', len(body) + 6, 0x4eea) + body + b'\0\0'


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


def _companion_nearby_revive_target(ctx, uid):
    """Select one retained owned corpse within three Chebyshev tiles."""
    owner = ctx.world.entities.get(uid)
    if owner is not None:
        for candidate in tuple(ctx.world.companions.active.values()):
            try:
                actor = _companion_revive_target(ctx, uid, candidate.ref.uid)
            except ValueError:
                continue
            corpse = ctx.world.entities.get(actor.ref.uid)
            if max(abs(corpse.x - owner.x), abs(corpse.y - owner.y)) <= 3:
                return actor
    raise ValueError('COMPANION_NEARBY_CORPSE_REQUIRED')


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
                                  hp=max(1, record.effective_max_hp // hp_divisor))
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

    Learning comes from the registered character authority in production.
    Public base MP is selected as LOCAL
    actual debit (no inferred dynamic reductions). LOCAL cast cadence is 1s,
    not an assertion about official reuse or native animation duration.
    Display candidates: REA399/401, action18 attack /19 support, gfx744/221.
    EnergyBolt projectile is deliberately unsupplied: f6 and raw A/B UNKNOWN.
    """
    def __init__(self, view, catalog, growth, policy, attributes, *, display=True,
                 class_ids=frozenset((3,)), policy_for=None,
                 learned_for=None, ctx=None):
        self.view, self.growth, self.policy = view, growth, policy
        self.class_ids = frozenset(class_ids)
        # Optional callable(record) -> normalized ATS companion policy or None.
        self.policy_for = policy_for
        # Production supplies the registered character-learning authority.
        # Standalone WorldView fixtures may supply their own learning input.
        self.learned_for = learned_for
        from tools.local_original_session import world_magic
        self.ctx = ctx
        self.engine = world_magic.PlayerMagic(world_magic.load_catalog())
        supported = {'heal', 'extra_heal', 'greater_heal', 'shield', 'blessed_armor',
            'enchant_dexterity', 'holy_weapon', 'enchant_weapon', 'decrease_weight',
            'energy_bolt', 'ice_dagger', 'fire_arrow', 'lightning', 'fireball',
            'cone_of_cold', 'cure_poison', 'remove_curse'}
        self.spells = {s.name: s.raw for s in self.engine.spells.values() if s.name in supported}
        self.rules = {s.name: s for s in self.engine.spells.values() if s.name in supported}
        self.bonus = self.engine.catalog['formula_policies']['l1j_healing']['magic_bonus_by_int_0_to_50']
        self.attributes, self.display = attributes, display
        self.cooldowns = {}  # same-server dismiss/resummon cannot reset reuse
        self.sequences = {}  # character -> (actor lifetime, target, ATS, next row)
        self.condition_states = {}  # character -> (lifetime/target, spellRowID states)
        self.policy_notes = {}  # bounded per-character unresolved selections
        self.events = []  # bounded development observations, no request-time I/O
        self.hp_regen_points = {}  # character -> (actor lifetime, HP points)
        # The shared basic-swing consumer admits life/range/weight before this
        # callback. Movement and casts already lower the same activity bucket.
        if hasattr(view, 'runtime_extensions'):
            def note_attack(base):
                def wrapped(rt, *args, **kwargs):
                    swing = base(rt, *args, **kwargs)
                    if swing is not None and '_pet' not in rt.record.equipment:
                        rt.regen_activity = min(rt.regen_activity, view.combat.regen.attack_points)
                    return swing
                return wrapped
            view.runtime_extensions.wrap('companion_regen', view.combat,
                                         'companion_swing', note_attack)
            def defense(base):
                def call(monster, uid, profile, now, *args, **kwargs):
                    rt = view.companions.get_actor(uid)
                    if rt is not None:
                        profile = self.profile(rt, profile, now, defense=True)
                    return base(monster, uid, profile, now, *args, **kwargs)
                return call
            view.runtime_extensions.wrap('companion_magic', view.combat,
                                         'npc_companion_swing', defense)
            def offense(base):
                def call(rt, profile, monster):
                    return base(rt, self.profile(rt, profile, view.runtime.clock()), monster)
                return call
            view.runtime_extensions.wrap('companion_magic', view.combat, 'companion_swing', offense)

    def equipment_uid(self, rt, kind):
        bags = getattr(self.view.companion_ai, 'inventory', None)
        if bags is None or not hasattr(bags, 'states'):
            return 0
        state = bags.states[rt.character_id]
        if kind == 'weapon':
            return state.weapon_uid
        from tools.local_original_session import inventory
        selected = {uid for _, uid in state.slots}
        return next((row.identifier for row in inventory.validate_kit_frame(bags.frames[rt.character_id])
            if row.identifier in selected and self.view.data.items[row.template_bits].slot == 'armor'), 0)

    def profile(self, rt, profile, now, *, defense=False):
        self.restore(rt, now)
        state = self.engine.states.get(rt.character_id)
        if state is None:
            return profile
        bags = getattr(self.view.companion_ai, 'inventory', None)
        if bags is not None and hasattr(bags, 'characters'):
            from tools.local_original_session.world_combat import companion_profile
            calculated, worn = bags.calculated(rt.character_id)
            profile = companion_profile(calculated, worn, bags.characters[rt.character_id]['gender'])
            if defense:
                return replace(profile, ac=profile.ac + (2 if rt.shield_until > now else 0))
        elif defense:
            bonus = self.engine.ac_bonus(rt.character_id, now,
                armor_uid=self.equipment_uid(rt, 'armor'))
            # The retained basic defense consumer already applies shield_until.
            if rt.shield_until > now:
                bonus += 2
            return replace(profile, ac=profile.ac + bonus,
                dexterity=profile.dexterity + self.engine.dexterity_bonus(rt.character_id, now))
        hit = damage = 0
        selected = self.equipment_uid(rt, 'weapon')
        for key, until in state.buffs.items():
            spell = self.engine.spells[key]
            if until > now and selected and state.weapon_uids.get(key) == selected:
                hit += spell.raw['player_policy'].get('hit_bonus', 0)
                damage += spell.raw['player_policy'].get('damage_bonus', 0)
        return replace(profile, dexterity=profile.dexterity + (0 if bags is not None and hasattr(bags, 'characters')
            else self.engine.dexterity_bonus(rt.character_id, now)),
            weapon=replace(profile.weapon, hit=profile.weapon.hit + hit, damage=profile.weapon.damage + damage))

    def install_inventory(self):
        bags = getattr(self.view.companion_ai, 'inventory', None)
        if bags is None:
            return
        def calculated(base):
            def call(uid, frame=None):
                value, worn = base(uid, frame)
                rt = self.view.companions.active.get(uid)
                if rt is None:
                    return value, worn
                from tools.local_original_session.world_stats import (
                    Attributes, CharacterStats, StatModifiers, WeightOptions, calculate_stats)
                from tools.local_original_session import world_weight, inventory
                carried = world_weight.inventory_weight((row for row in inventory.validate_kit_frame(
                    bags.frames[uid] if frame is None else frame) if dict(row.raw_fields)[4] > 0), bags.weights)
                now = self.view.runtime.clock()
                self.restore(rt, now)
                result = calculate_stats(CharacterStats(rt.record.level, rt.record.class_id,
                    Attributes(*bags.characters[uid]['attributes'])), worn,
                    buffs=(StatModifiers(dexterity=self.engine.dexterity_bonus(uid, now)),),
                    weight=WeightOptions(carried_weight=carried,
                        decrease_weight=self.engine.active(uid, 'weight', now)))
                return replace(result, ac=result.ac + self.engine.ac_bonus(uid, now,
                    armor_uid=self.equipment_uid(rt, 'armor'))), worn
            return call
        self.view.runtime_extensions.wrap('companion_magic', bags, 'calculated', calculated)

    def restore(self, rt, now):
        if rt.character_id not in self.engine.states:
            saved = rt.record.equipment.get('magic_buffs')
            if saved is not None:
                self.engine.restore(rt.character_id, saved, now)
                rt.shield_until = self.engine.state(rt.character_id).buffs.get(2, 0)
        elif 2 in self.engine.state(rt.character_id).buffs:
            rt.shield_until = self.engine.state(rt.character_id).buffs[2]
        state = self.engine.states.get(rt.character_id)
        if state is not None:
            self.cooldowns[rt.character_id] = max(self.cooldowns.get(rt.character_id, 0), state.next_cast_at)
            rt.next_cast_at = max(rt.next_cast_at, self.cooldowns[rt.character_id])

    def save_buffs(self, record, now):
        if record.character_id in self.engine.states:
            record.equipment['magic_buffs'] = self.engine.snapshot(record.character_id, now,
                learned=record.learned_spells)

    def died(self, record):
        self.engine.states.pop(record.character_id, None)
        record.equipment.pop('magic_buffs', None)

    def ats(self, rt):
        return None if self.policy_for is None else self.policy_for(rt.record)

    def eligible(self, rt, name):
        spell = self.spells.get(name)
        if spell is None:
            return False
        learned = (rt.record.learned_spells if self.learned_for is None else
                   self.learned_for(rt.record))
        if not (spell['classic_key']['value'] in learned
                and rt.record.level >= spell['learn_level_mage']['value']):
            return False
        # A saved companion ATS setting selects which known spells are used.
        ats = self.ats(rt)
        if not ats or ats.get('status') != 'valid':
            return False
        return any(row.get('spell') == name for row in
                   ats.get('buff_slots', []) + ats.get('battle_slots', []) + ats.get('heal_slots', []))

    def reset_sequence(self, rt):
        self.sequences.pop(rt.character_id, None)
        self.condition_states.pop(rt.character_id, None)

    def battle_state(self, rt):
        # LOCAL user policy: target switch, resummon and reconnect start over.
        # Entity generations and owner generations catch implicit transitions
        # as well as the explicit AI reset_sequence call sites.
        context = (rt.ref, rt.owner_ref, rt.target)
        previous = self.condition_states.get(rt.character_id)
        if previous is None or previous[0] != context:
            self.reset_sequence(rt)
            previous = (context, {})
            self.condition_states[rt.character_id] = previous
        return previous[1]

    def cost(self, name):
        return self.spells[name]['mp_cost']['value']

    def event(self, rt, name, now, **values):
        self.events.append(dict(actor=rt.ref.uid, spell=name, at=now, **values))
        del self.events[:-64]

    def regen(self, rt, now):
        record = rt.record
        if (not record.alive or record.hp <= 0
                or self.view.companions.get_actor(rt.ref.uid) is not rt
                or self.view.entities.resolve(rt.ref) is None):
            self.hp_regen_points.pop(rt.character_id, None)
            return
        policy = self.view.combat.regen
        previous = self.hp_regen_points.get(rt.character_id)
        hp_points = previous[1] if previous is not None and previous[0] == rt.ref else 0
        if rt.regen_at is None:
            hp_points = 0
            rt.regen_at = now + policy.tick_ms / 1000
        if now < rt.regen_at:
            self.hp_regen_points[rt.character_id] = (rt.ref, hp_points)
            return
        # Match the PC clock: ordinary polling jitter preserves the deadline;
        # late callbacks give one event, never offline/catch-up resources.
        tick = policy.tick_ms / 1000
        due = rt.regen_at
        rt.regen_at = (due + tick if now - due <= self.view.runtime.tick_interval + 1e-9
                       else now + tick)
        rt.regen_points += rt.regen_activity
        hp_points += rt.regen_activity
        rt.regen_activity = policy.idle_points
        hp_due = hp_points >= policy.hp_threshold(record.level)
        mp_due = rt.regen_points >= policy.mp_threshold
        self.hp_regen_points[rt.character_id] = (rt.ref, 0 if hp_due else hp_points)
        if mp_due:
            rt.regen_points = 0
        if not hp_due and not mp_due:
            return
        bags = getattr(self.view.companion_ai, 'inventory', None)
        calculated = None if bags is None else bags.calculated(rt.character_id)[0]
        before_hp, before_mp = record.hp, record.mp
        if hp_due and record.hp < record.effective_max_hp:
            # Ordinary saved characters use the PC policy and worn options.
            # Spell eligibility, food and burden do not gate PC recovery.
            con = (self.attributes[rt.character_id][2] if calculated is None else
                   calculated.attributes.con)
            base = policy.hp_amount(con)
            bonus = 0 if calculated is None else calculated.hp_regen_bonus
            record.hp = min(record.effective_max_hp, max(0, record.hp + base + bonus))
            if record.hp == 0:
                self.view.companions.die(rt.character_id, now)
        if mp_due and record.alive:
            wis = (self.attributes[rt.character_id][3] if calculated is None else
                   calculated.attributes.wis)
            base = policy.mp_amount(wis)
            bonus = 0 if calculated is None else calculated.mp_regen_bonus
            if bags is not None and now < bags.blue_until.get(rt.character_id, 0):
                base += max(wis, 11) - 5
            record.mp = min(record.effective_max_mp, max(0, record.mp + base + bonus))
        if hp_due and record.alive:
            # Optional underwater environment listener (world_feature_environment).
            worn = () if bags is None else tuple(e.item.template_id for e in bags.calculated(rt.character_id)[1])
            self.view.events.emit('environment_companion_hp_recovery', rt, now, worn)
        if (record.hp, record.mp) != (before_hp, before_mp):
            self.event(rt, 'recover', now, hp_before=before_hp, hp_after=record.hp,
                       mp_before=before_mp, mp_after=record.mp)
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
        if self.ctx is None:
            return
        # Same per-spell action/castgfx table as a player cast (spell_display.json).
        self.ctx.run_sync_hooks('magic_cast_display', actor, target, self.rules[name].key, True)

    def buff_target(self, rt, target, name):
        """Resolve the recipient's own timer/equipment through its buff owner."""
        spell = self.rules[name]
        member = self.view.companions.get_actor(target.uid)
        if member is not None:
            return self.received_buff_target(target.uid, spell.key, rt.character_id)
        if self.ctx is None:
            return None
        collect = getattr(self.ctx, 'collect_sync_hooks', lambda *args: ())
        for service in collect('magic_service'):
            if service is not None and service.buff_target is not None:
                return service.buff_target(target.uid, spell.key, rt.character_id)
        return None

    def received_buff_target(self, uid, key, source_uid):
        """Bind a buff to the current companion and its existing save owner."""
        from tools.local_original_session import world_magic
        view = self.view
        member = view.companions.get_actor(uid)
        entity = view.entities.get(uid)
        spell = self.engine.spells.get(key)
        if (member is None or entity is None or member.ref != entity.ref
                or not view.companions.can_be_attacked(uid)
                or spell is None or spell.name not in self.rules
                or spell.kind not in world_magic.BUFF_KINDS or spell.duration <= 0
                or source_uid != member.character_id and not world_magic.allows_received_buff(spell)):
            return None
        self.restore(member, view.runtime.clock())
        weapon, armor = self.equipment_uid(member, 'weapon'), self.equipment_uid(member, 'armor')
        if spell.kind in ('weapon_hit', 'weapon_damage') and not weapon or spell.kind == 'armor' and not armor:
            return None
        ref = member.ref

        def apply(now):
            need(view.entities.resolve(ref) is entity
                 and view.companions.get_actor(uid) is member
                 and view.companions.can_be_attacked(uid), 'MAGIC_CURRENT_BUFF_TARGET_REQUIRED')
            self.engine.apply_buff(member.character_id, spell, now, weapon_uid=weapon,
                armor_uid=armor, source_uid=source_uid, replace_weapon=True)
            if spell.name == 'shield':
                member.shield_until = self.engine.state(member.character_id).buffs[key]
            bags = getattr(view.companion_ai, 'inventory', None)
            if bags is not None:
                bags.refresh(member.character_id, publish=False)
            if source_uid != member.character_id:
                self.save_buffs(member.record, now)
                # A committed recipient write must expose its real save error;
                # the runtime cleanup wrapper intentionally only logs it.
                save = getattr(self.ctx, '_companion_save', view._save_companion)
                save(member.owner_ref.uid)

        return world_magic.MagicBuffTarget(self.engine.state(member.character_id), weapon,
            armor, apply, spell.duration)

    def ailment(self, rt, target, name, now, *, apply=False):
        from tools.local_original_session import world_magic_status as status
        member = self.view.companions.get_actor(target.uid)
        if member is not None and member.ref == target.ref and member.owner_ref == rt.owner_ref:
            owner = None if self.ctx is None else self.ctx._companion_ailments
            if owner is None:
                return False
            row = owner.state(member, now)
            if name == 'cure_poison':
                active = (row['poison'] is not None and row['poison']['until'] > now or any(
                    status.active(row['effects'], kind, now) and e['params'].get('monster_poison')
                    for kind, e in row['effects'].items()))
                return owner.cure(member, now) if active and apply else bool(active)
            kinds = [k for k in status.CURSES if status.active(row['effects'], k, now)]
            poisoned = row['poison'] is not None and row['poison']['until'] > now
            if apply:
                if poisoned:
                    owner.cure(member, now)
                for kind in kinds:
                    row['effects'].pop(kind, None)
                if kinds:
                    owner.save(member, now)
            return bool(kinds or poisoned)
        if self.ctx is None:
            return False
        for provider in self.ctx.collect_sync_hooks('consumable_magic_provider'):
            if provider is None:
                continue
            engine, save = provider
            poisoned = engine.is_poisoned(target.uid, now)
            active = poisoned if name == 'cure_poison' else poisoned or any(
                status.active(engine.effects(target.uid), k, now) for k in status.CURSES)
            if not active:
                continue
            if apply:
                if poisoned:
                    engine.state(target.uid).poison = None
                    self.ctx.run_sync_hooks('cure_poison', target.uid)
                if name == 'remove_curse':
                    engine.clear_curses(target.uid)
                save(target.uid, now)
            return True
        return False

    def cast(self, rt, actor, target, name, now):
        from tools.local_original_session import world_combat as combat
        from tools.local_original_session.world_magic import BUFF_KINDS
        from tools.local_original_session.npc_ai import distance, local_line_clear
        view, record = self.view, rt.record
        self.restore(rt, now)
        spell = self.rules.get(name)
        status = view.events.fold('actor_action_status', {}, rt.ref, now)
        if (spell is None or status.get('blocked') or status.get('silenced')
                or view.companions.get_actor(actor.uid) is not rt
                or view.entities.resolve(target.ref) is not target
                or not view.companions.can_be_attacked(actor.uid)
                or not target.alive or target.map_id != actor.map_id
                or not self.eligible(rt, name)
                or now < max(rt.next_cast_at, self.cooldowns.get(rt.character_id, 0))
                or record.mp < spell.mp):
            return False
        attack = spell.kind in ('damage', 'area_damage')
        member = view.companions.get_actor(target.uid)
        party_member = (member is not None and member.ref == target.ref
                        and member.owner_ref == rt.owner_ref)
        if attack:
            if record.combat_mode == 'PASSIVE' or rt.target != target.ref or view.companion_ai._hostile(rt, target.ref) is not target:
                return False
        elif not record.support_enabled or (target.ref not in (rt.ref, rt.owner_ref)
                and not (party_member and spell.kind in ('heal', 'cure_poison', 'remove_curse'))
                and spell.kind not in BUFF_KINDS):
            return False
        buff = None
        if spell.kind not in ('heal', 'cure_poison', 'remove_curse') and not attack:
            buff = self.buff_target(rt, target, name)
            if buff is None:
                return False
        bags = getattr(view.companion_ai, 'inventory', None)
        if bags is not None and bags.calculated(rt.character_id)[0].weight.normal_skill_blocked:
            return False
        if (distance(actor.x, actor.y, target.x, target.y) > spell.range
                or not local_line_clear(view.terrain, actor.map_id, actor.x, actor.y, target.x, target.y)):
            return False
        state = self.engine.state(rt.character_id)
        amount, victims = 0, []
        intelligence = (self.attributes[rt.character_id][5] if bags is None else
                        bags.calculated(rt.character_id)[0].attributes.intelligence)
        if attack:
            radius = spell.raw['player_policy'].get('area_radius', 0) if spell.kind == 'area_damage' else 0
            for candidate in sorted(view.entities, key=lambda e: e.uid):
                if (not candidate.alive or candidate.map_id != actor.map_id
                        or distance(candidate.x, candidate.y, target.x, target.y) > radius
                        or not local_line_clear(view.terrain, actor.map_id, actor.x, actor.y, candidate.x, candidate.y)):
                    continue
                found = view.spawner.slot_for(candidate.uid)
                if found is not None and found[0].active and found[1].hp > 0:
                    rolled = combat.magic_damage(spell.raw['formula']['parameters'], intelligence,
                        view.combat.rng, weak_attr=found[0].monster.weak_attr, mr=found[0].monster.mr)
                    victims.append((candidate, found, rolled))
            if not victims:
                return False
        elif spell.kind == 'heal':
            healed = member.record if party_member else view.combat.pcs.get(target.uid)
            if healed is None or healed.hp <= 0 or healed.hp >= getattr(healed, 'effective_max_hp', healed.max_hp):
                return False
            amount = combat.companion_magic_heal(spell.raw['formula']['parameters'], intelligence,
                0, self.bonus, view.combat.rng)
        elif spell.kind in ('cure_poison', 'remove_curse'):
            if not self.ailment(rt, target, name, now):
                return False
        before = record.mp
        spell_state = self.battle_state(rt).setdefault(spell.key, {})
        record.mp -= spell.mp
        rt.next_cast_at = now + spell.reuse
        state.next_cast_at = rt.next_cast_at
        self.cooldowns[rt.character_id] = rt.next_cast_at
        rt.regen_activity, rt.action = min(rt.regen_activity,
                                         view.combat.regen.attack_points), 'CAST'
        self.display_cast(rt, actor, target, name)
        if attack:
            for victim, (group, slot), rolled in victims:
                if victim.alive and slot.hp > 0:
                    view._apply_monster_swing(rt.owner_ref.uid, actor.uid, victim, group.monster,
                        slot.hp, combat.Swing(True, rolled), now)
                    amount += rolled
            view._announce()
        elif spell.kind == 'heal':
            if party_member:
                before_hp = healed.hp
                healed.hp = min(getattr(healed, 'effective_max_hp', healed.max_hp), healed.hp + amount)
                amount = healed.hp - before_hp
            else:
                amount, wire = combat.apply_heal(view.combat, target.uid, amount)
                view._queue(target.uid, wire)
        elif spell.kind in ('cure_poison', 'remove_curse'):
            self.ailment(rt, target, name, now, apply=True)
        else:
            buff.apply(now)
        spell_state['count'] = spell_state.get('count', 0) + 1
        spell_state['at'] = now
        self.event(rt, name, now, target=target.uid, mp_before=before, mp_after=record.mp,
            amount=amount, shield_until=rt.shield_until, victims=[v.uid for v, _, _ in victims])
        self.save_buffs(record, now)
        view._save_companion(rt.owner_ref.uid)
        return True

    def step(self, rt, actor, owner, hostile, now, returning):
        self.restore(rt, now)
        state = self.view.events.fold('actor_action_status', {}, rt.ref, now)
        if state.get('blocked') or state.get('silenced'):
            return False
        if rt.record.class_id not in self.class_ids:
            return False
        rt.next_cast_at = max(rt.next_cast_at, self.cooldowns.get(rt.character_id, 0))
        if rt.shield_until and now >= rt.shield_until:
            rt.shield_until = 0
            self.event(rt, 'shield_expired', now)
        from tools.local_original_session import ats_config_codec as codec
        ats = self.ats(rt)
        rt.emergency_owner = rt.recovering = False
        if not ats or ats.get('status') != 'valid':
            return False
        states = self.battle_state(rt)
        notes = tuple(ats.get('issues', ()))
        unsupported = tuple(row.get('spell') or ('item:' + str(row['template']))
            for row in ats['buff_slots'] + ats['battle_slots']
            if (row.get('spell') and row['spell'] not in self.spells)
            or (row in ats['buff_slots'] and 'template' in row))
        note = (notes, unsupported)
        if (notes or unsupported) and self.policy_notes.get(rt.character_id) != note:
            self.policy_notes[rt.character_id] = note
            self.event(rt, 'ats_unresolved', now, issues=notes, unsupported=unsupported)
        # LOCAL healing selections precede the unchanged native buff/battle rows.
        from tools.local_original_session.npc_ai import distance, local_line_clear
        candidates = [actor] + ([owner] if owner is not None else [])
        candidates += [entity for member in self.view.companions.active.values()
            if member.ref != rt.ref and member.owner_ref == rt.owner_ref
            and (entity := self.view.entities.resolve(member.ref)) is not None]
        for heal_kind in ('hp', 'status'):
            for row in ats.get('heal_slots', []):
                name = row.get('spell')
                spell = self.rules.get(name)
                if (row.get('kind') != heal_kind or spell is None or not self.eligible(rt, name)
                        or (spell.kind != 'heal' if heal_kind == 'hp'
                            else spell.kind not in ('cure_poison', 'remove_curse'))):
                    continue
                eligible = []
                for candidate in candidates:
                    if (candidate.map_id != actor.map_id or not candidate.alive
                            or distance(actor.x, actor.y, candidate.x, candidate.y) > spell.range
                            or not local_line_clear(self.view.terrain, actor.map_id,
                                actor.x, actor.y, candidate.x, candidate.y)):
                        continue
                    member = self.view.companions.get_actor(candidate.uid)
                    subject = member.record if member is not None else self.view.combat.pcs.get(candidate.uid)
                    if subject is None or subject.hp <= 0:
                        continue
                    if heal_kind == 'hp':
                        if subject.hp >= getattr(subject, 'effective_max_hp', subject.max_hp) or subject.hp * 100 > getattr(subject, 'effective_max_hp', subject.max_hp) * row['percent']:
                            continue
                    elif not self.ailment(rt, candidate, name, now):
                        continue
                    eligible.append((subject.hp / getattr(subject, 'effective_max_hp', subject.max_hp), candidate))
                for _, candidate in sorted(eligible, key=lambda item: item[0]):
                    if self.cast(rt, actor, candidate, name, now):
                        return True
        # Preserve every native list's order without injecting default spells.
        for recipient in candidates:
            if recipient is None:
                continue
            rows = []
            for row in ats['buff_slots']:
                name = row.get('spell')
                if (name not in self.rules or self.rules[name].duration <= 0
                        or not rt.record.support_enabled or not self.eligible(rt, name)):
                    continue
                target = self.buff_target(rt, recipient, name)
                if target is not None:
                    rows.append((name, target))
            weapon_rows = [name for name, _ in rows
                if self.rules[name].kind in ('weapon_hit', 'weapon_damage')]
            for name, target in rows:
                if name in weapon_rows and name != weapon_rows[-1]:
                    continue  # Last applicable weapon enchant, separately for each recipient.
                spell = self.rules[name]
                bp = self.policy['thresholds']['buff']
                lead = min(bp['refresh_lead_cap_seconds'],
                           target.duration * bp['refresh_lead_duration_fraction'])
                until = (rt.shield_until if recipient.ref == rt.ref and name == 'shield'
                         else target.state.buffs.get(spell.key, 0))
                bound = (target.state.weapon_uids.get(spell.key) == target.weapon_uid
                    if spell.kind in ('weapon_hit', 'weapon_damage') else
                    target.state.armor_uids.get(spell.key) == target.armor_uid
                    if spell.kind == 'armor' else True)
                if not until or until - now <= lead or not bound:
                    if self.cast(rt, actor, recipient, name, now):
                        return True
        rows = ats['battle_slots']
        sequence = [row for row in rows if row['kind'] == 'sequence']
        context = (rt.ref, rt.target, ats)
        previous = self.sequences.get(rt.character_id)
        cursor = previous[3] if previous is not None and previous[:3] == context else 0
        for row in rows:
            if row['kind'] == 'sequence' and row['index'] < cursor:
                continue
            spell_state = states.setdefault(row['raw'].get(4), {})
            name = row.get('spell')
            if name not in self.spells or not self.eligible(rt, name):
                continue
            kind = self.rules[name].kind
            candidates = [actor]
            if kind in ('damage', 'area_damage'):
                if hostile is None or returning:
                    continue
                candidates = [hostile]
            elif kind in ('heal', 'cure_poison', 'remove_curse'):
                candidates = [actor, owner] if owner is not None else [actor]
                if kind == 'heal':
                    candidates.sort(key=lambda e: (rt.record.hp / rt.record.effective_max_hp if e.ref == rt.ref else
                        self.view.combat.pcs[e.uid].hp / self.view.combat.pcs[e.uid].max_hp))
            target = None
            for candidate in candidates:
                from tools.local_original_session.npc_ai import distance, local_line_clear
                if (candidate.map_id != actor.map_id or not candidate.alive
                        or distance(actor.x, actor.y, candidate.x, candidate.y) > self.rules[name].range
                        or not local_line_clear(self.view.terrain, actor.map_id, actor.x, actor.y, candidate.x, candidate.y)):
                    continue
                subject = (self.view.combat.pcs.get(candidate.uid) if kind == 'heal' and candidate.ref != rt.ref else rt.record)
                if subject is None or not all(codec.condition_matches(k, v, subject if k in (1, 2) else rt.record,
                        state=spell_state, now=now) for k, v in row['conditions']):
                    continue
                if kind == 'heal' and (subject.hp <= 0 or subject.hp >= getattr(subject, 'effective_max_hp', subject.max_hp)):
                    continue
                if kind in ('cure_poison', 'remove_curse') and not self.ailment(rt, candidate, name, now):
                    continue
                target = candidate
                break
            if target is None:
                continue
            if self.cast(rt, actor, target, name, now):
                if row['kind'] == 'sequence':
                    cursor = (row['index'] + 1) % len(sequence)
                self.sequences[rt.character_id] = (*context, cursor)
                return True
        # All remaining sequence rows failed: next decision starts at the top.
        # Melee/follow remain available while casts cannot commit.
        self.sequences[rt.character_id] = (*context, 0)
        return False


def _companion_learned_spells(ctx, record):
    """ATS compatibility projection; companion.json never grants learning."""
    learned = next((value for value in ctx.collect_sync_hooks(
        'character_learned_spells', record.character_id) if value is not None), ())
    record.learned_spells = tuple(sorted(learned))
    return record.learned_spells


def _companion_learning_changed(ctx, uid):
    if not ctx._companion_enabled:
        return
    record = ctx.world.companions.records.get(uid)
    if record is not None:
        _companion_learned_spells(ctx, record)


def _companion_initialize(ctx):
    from tools.local_original_session.world_companion_runtime import install_companion_runtime
    install_companion_runtime(ctx.world)
    ctx._companion_ailments = CompanionAilments(ctx.world, ctx)
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
    ctx._companion_error_params = []
    ctx._companion_untargeted_params = []
    ctx._companion_item_effects = {}
    ctx._companion_antidotes = frozenset()
    ctx._companion_defs = None
    ctx._companion_views = {}
    ctx._companion_model_revision = {}
    ctx._companion_mapped = {}
    ctx._companion_published = []
    ctx._companion_death_penalties = []
    ctx._companion_returns = []
    ctx._companion_party = None
    ctx._companion_ui_events = []
    if not ctx._companion_enabled:
        return
    from tools.local_original_session.world_item_effects import load_effects
    ctx._companion_item_effects = load_effects(owner='companion')
    ctx._companion_antidotes = frozenset(t for t, effect in load_effects().items()
                                       if effect.kind == 'cure_poison')
    need('manual-user-play' not in str(ctx.realm.store.path).lower(), 'COMPANION_TEST_PROFILE_REQUIRED')
    from tools.local_original_session.world_companion_classes import load_definitions
    ctx._companion_defs = load_definitions()
    # Spell-capable class (today the mage row) supplies the magic consumer data.
    magic_class = next(d for d in ctx._companion_defs.classes.values()
                       if d.spells.get('spells'))
    ctx._companion_growth = magic_class.growth
    ctx._companion_spells = magic_class.spells
    ctx._companion_policy = magic_class.policy
    starter = json.loads((Path(__file__).parent / 'data' / 'm1' / 'starter.json').read_text(encoding='utf-8'))
    ctx._companion_supplies = [entry['value'] for entry in
        starter.get('kits', {}).get('test_knight', {}).get('companion_supplies', [])]
    # This real bag row also participates in the player's burden calculation.
    # Preserve native-dump-v1.jsonl:1521 f10=78, using the existing LOCAL
    # raw-weight interpretation. Official display weight0 loses this precision.
    from tools.local_original_session.world_handlers import KitItemPolicy
    ctx.add_item_policies((KitItemPolicy(TOKEN_TEMPLATE, 78, False),),
                          replace_existing=True)
    ctx._companion_store = CompanionStore(ctx.realm.store.path)
    ctx.world.companion_save = ctx._companion_save


def _companion_started(ctx):
    if not ctx._companion_enabled:
        return
    ctx._companion_ailments.start()
    ctx.realm._world_companion_record = ctx.world.companions.records.get
    from tools.local_original_session import world_combat
    from tools.local_native_login_local_ack_hook import ack_enter_world as ack
    rows = ctx.realm.store._read()['characters']
    owner = next((r for r in rows if r['class'] == 1), None)
    need(owner is not None, 'COMPANION_TEST_KNIGHT_REQUIRED')
    defs = ctx._companion_defs
    classes = defs.class_ids - {owner['class']}
    view = ctx.world
    view.companions.allowed_classes = classes
    view.companion_max_active = defs.max_active_per_owner
    view.companion_ai.follow_distance = defs.follow_distance
    view.companion_ai.assist_scan_tiles = defs.assist_scan_tiles
    view.companion_intervals = lambda rt: _companion_intervals(ctx, rt)
    view.companion_owner_death = lambda uid, now: _companion_owner_death(ctx, uid, now)
    def on_death(record, now):
        ctx._companion_ailments.clear(record)
        if view.companion_ai.magic is not None:
            view.companion_ai.magic.died(record)
        _companion_death_penalty(ctx, record, now)
    view.companions.on_death = on_death
    removed = view.companions.on_remove
    def on_remove(actor):
        if view.companion_ai.magic is not None:
            view.companion_ai.magic.reset_sequence(actor)
        if removed is not None:
            removed(actor)
        _companion_unmapped(ctx, actor)
    view.companions.on_remove = on_remove
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
        {r['uid']: r['attributes'] for r in rows},
        class_ids={d.class_id for d in defs.classes.values() if d.spells is ctx._companion_spells},
        policy_for=lambda record: _companion_ats_policy(ctx, record),
        learned_for=lambda record: _companion_learned_spells(ctx, record), ctx=ctx)
    saved = {r['character_id']: r for r in ctx._companion_store.payload['records']}
    for row in rows:
        if row['class'] not in classes or row['uid'] == owner['uid']:
            continue
        definition = defs.classes[row['class']]
        if row['uid'] in saved:
            record = record_from_row(saved[row['uid']])
        else:
            initial = definition.growth['initial_resources']
            progress = ctx._world_progress.get(row['uid'])
            hp = progress.max_hp or initial['hp']['max']
            mp = progress.max_mp if progress.max_mp is not None else (8 if row['attributes'][3] >= 16 else 6)
            weapon = definition.starter_weapon_template
            record = CompanionRecord(row['uid'], owner['uid'], account,
                level=progress.level, exp=progress.exp, hp=hp, mp=mp, max_hp=hp, max_mp=mp,
                equipment={} if weapon is None else {'weapon_template': weapon},
                class_id=row['class'])
        ctx.world.companions.register(record, roster=roster)
        _companion_learned_spells(ctx, record)
        ctx.world.companion_owner_half.setdefault(record.owner_character_id, 0)
        stats = row['attributes']
        weapon_id = record.equipment.get('weapon_template')
        weapon = (world_combat.FIST if weapon_id is None else
                  world_combat.weapon_from_item(ctx.world.data.items[weapon_id]))
        ctx.world.companion_profiles[row['uid']] = world_combat.PcProfile(
            record.level, record.class_id, row['gender'], stats[0], stats[1], weapon=weapon,
            con=stats[2], wis=stats[3])
        weapon_def = None if weapon_id is None else ctx.world.data.items.get(weapon_id)
        ctx.world.companion_looks[row['uid']] = dict(name=row['name'], gender=row['gender'],
            sprite_id=definition.sprite(row['gender']),
            stance=50 if weapon_id == 230 else 0,
            weapon_type=None if weapon_def is None else weapon_def.weapon_type,
            owner_name=ctx._companion_rows[record.owner_character_id]['name'])
    for uid, progress in ctx._companion_store.payload['owners'].items():
        ctx.world.companion_owner_half[int(uid)] = progress['exp_half']
    from tools.local_original_session import inventory
    if ctx._inventory_kit_policy == inventory.KIT_POLICY:
        from tools.local_original_session.world_companion_inventory import CompanionInventory
        ctx._companion_inventory = CompanionInventory(ctx,
            characters=ctx._companion_rows, policy=ctx._companion_policy,
            save=ctx._companion_save,
            owned_actor=lambda uid, target: _companion_owned_actor(ctx, uid, target, living=True),
            report_error=lambda error: _companion_report_give_error(ctx, error))
        for uid in ctx.world.companions.records:
            ctx._companion_inventory.initialize(uid)
        ctx.world.companion_ai.inventory = ctx._companion_inventory
        ctx.world.combat.companion_inventory = ctx._companion_inventory
        ctx.world.companion_ai.magic.install_inventory()
        ctx._companion_inventory.policy_for = lambda record: _companion_ats_policy(ctx, record)
        ctx._companion_inventory.install_pickup()
    ctx.world.companion_ai.policy_for = lambda record: _companion_ats_policy(ctx, record)
    # Old record.equipment is legacy metadata only; normal equipment.json is
    # now the sole worn-item authority, exactly as for direct player selection.
    for record in ctx.world.companions.records.values():
        record.equipment = {key: value for key, value in record.equipment.items()
                            if key not in ('weapon_template', 'slots', 'weight240')}
    ctx._companion_party = CompanionParty(ctx)
    ctx.world.events.add('companion_party', 'tick', ctx._companion_party.sync, priority=100)


def _companion_save(ctx, owner_uid, receipt=None):
    if ctx._companion_store is not None:
        # Quit/Restart also save after the last natural world tick, even if no
        # further player request ran the ordinary inventory/status hook.
        for uid, record in ctx.world.companions.records.items():
            magic = ctx.world.companion_ai.magic
            if magic is not None:
                magic.save_buffs(record, ctx.world.runtime.clock())
            state = ctx.world.combat.pcs.get(uid)
            if state is not None:
                from tools.local_original_session.world_progress import base_maxima
                record.max_hp, record.max_mp = base_maxima(state)
                record.hp, record.mp = state.hp, state.mp
                record.alive = state.hp > 0
                record.level, record.exp = state.profile.level, ctx.world.exp[uid]
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
        owned = {uid: record for uid, record in ctx.world.companions.records.items()
                 if uid in ctx._companion_rows}
        ctx._companion_store.commit(ctx.world, owner_uid, receipt,
            records=owned.values(), reward_receipts=(row for row in ctx.world.companion_reward_receipts
                if row['member_character_id'] in owned))
        _companion_refresh_views(ctx)
        party = getattr(ctx, '_companion_party', None)
        if party is not None:
            party.sync()


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
            state.status_fields.update({2: saved['level'], 11: saved['max_hp'],
                13: saved['max_mp'], 18: saved['lawful']})
            from tools.local_original_session.world_progress import Progress, exp_percent
            state.status_fields[26] = exp_percent(ctx.world.data, saved['exp'], saved['level'])
            ctx.world.progress.adopt(uid, Progress(saved['exp'], saved['level'],
                saved['max_hp'], saved['max_mp'], saved['lawful']))
            ctx._world_recalculate_uid(uid)
            from tools.local_original_session.world_status_frames import full_status_frame
            ctx.world._queue(uid, full_status_frame(state.status_fields))
        # Retire the old native rows before restoration saves append the new
        # list. This also handles reselect in the same client process.
        party = getattr(ctx, '_companion_party', None)
        if party is not None:
            party.reset(uid)
        active = [rt for rt in ctx.world.companions.active.values() if rt.owner_ref.uid == uid]
        # Members out at the last logout come back automatically (결정 3차).
        members = sorted((r for r in ctx.world.companions.records.values()
                          if r.owner_character_id == uid and r.summoned
                          and r.character_id in ctx._companion_rows),
                         key=lambda r: r.character_id)
        if members and not active:
            for member in members[:ctx.world.companion_max_active]:
                _companion_restore(ctx, uid, member.character_id)
        # A new client process has a fresh DLL: republish every owned actor.
        for rt in [rt for rt in ctx.world.companions.active.values() if rt.owner_ref.uid == uid]:
            ctx._companion_mapped.pop(rt.character_id, None)
            _companion_publish_map(ctx, uid, rt)
        if party is not None:
            party.sync()
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
    need(sum(rt.owner_ref.uid == uid for rt in view.companions.active.values())
         < view.companion_max_active, 'COMPANION_ONE_ACTIVE_MEMBER_REQUIRED')
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


def _companion_call(ctx, uid):
    """Summon a saved living mage, or recall its current same-map actor."""
    from tools.local_original_session.npc_ai import DELTAS
    from tools.local_original_session.world_entities import Kind
    from tools.local_original_session.world_visibility import remove_frame
    view = ctx.world
    members = sorted((r for r in view.companions.records.values()
                      if r.owner_character_id == uid), key=lambda r: r.character_id)
    need(members, 'COMPANION_SAVED_MEMBER_REQUIRED')
    living = [r for r in members if r.alive and r.hp > 0]
    need(living, 'COMPANION_TARGETED_SCROLL_REQUIRED')
    first = None
    for member in living:
        actor = view.companions.active.get(member.character_id)
        if actor is None and sum(rt.owner_ref.uid == uid for rt in view.companions.active.values()) \
                >= view.companion_max_active:
            continue
        member.summoned = True
        actor = (view.summon_companion(member.character_id, uid) if actor is None
                 else _companion_recall(ctx, uid, member, actor))
        first = first or actor
    need(first is not None, 'COMPANION_ONE_ACTIVE_MEMBER_REQUIRED')
    return first


def _companion_recall(ctx, uid, member, actor):
    """Move a living current member beside its owner (same identity)."""
    from tools.local_original_session.npc_ai import DELTAS
    from tools.local_original_session.world_entities import Kind
    from tools.local_original_session.world_visibility import remove_frame
    view = ctx.world
    owner = view.entities.get(uid)
    entity = view.entities.resolve(actor.ref)
    need(owner is not None and entity is not None and owner.alive
         and actor.owner_ref == owner.ref and entity.map_id == owner.map_id,
         'COMPANION_CURRENT_LIVING_OWNER_REQUIRED')
    for heading, (dx, dy) in enumerate(DELTAS):
        x, y = owner.x + dx, owner.y + dy
        if (view.terrain is not None
                and view.terrain.can_step(owner.map_id, owner.x, owner.y, heading) is True
                and not any(e.kind is not Kind.ITEM and e.uid != entity.uid
                    for e in view.entities.near(owner.map_id, x, y, 0, alive_only=False))):
            actor = view.companions.recall(member.character_id, uid, owner.map_id, x, y,
                                            now=view.runtime.clock())
            # Reuse existing remove/spawn visibility publication for relocation;
            # do not invent a native companion teleport packet.
            for watcher in view.pcs:
                known = view.visibility.known.get(watcher, set())
                if entity.uid in known:
                    known.discard(entity.uid)
                    view._queue(watcher, remove_frame(entity.uid))
                for wire in view._refresh(watcher):
                    view._queue(watcher, wire)
            view.companion_ai.start(actor.ref, view.runtime.clock())
            view._announce()
            return actor
    raise ValueError('COMPANION_FREE_SPAWN_TILE_REQUIRED')


def _companion_relocate_depart(ctx, uid):
    """End old-map actor/target/timer lifetimes; preserve only saved members."""
    members = tuple(actor for actor in ctx.world.companions.active.values()
                    if actor.owner_ref.uid == uid and actor.character_id in ctx._companion_rows)
    for actor in members:
        ctx.world.companions.dismiss(actor.character_id)
    return members


def _companion_relocate_arrive(ctx, uid, members):
    for previous in members:
        actor = _companion_restore(ctx, uid, previous.character_id)
        # Relocation clears targets/reservations, not already earned cooldowns.
        for field in ('next_move_at', 'next_attack_at', 'next_cast_at', 'shield_until'):
            setattr(actor, field, getattr(previous, field))
        # Departure retired the old UID and unmapped it. Publish the replacement
        # before Ctrl+E needs an identity, even when its native actor is offscreen.
        _companion_publish_map(ctx, uid, actor)
    return tuple(ctx.world.drain(uid))


def _companion_after_move(ctx, writer, row, game, operation_lock):
    # Runs inside the world lock on the handler move path (world_core_maps):
    # synchronous only, never re-enter the runtime.
    if not getattr(ctx, '_companion_enabled', False):
        return
    bound = getattr(ctx, '_world_pcs', {}).get(id(writer))
    if bound is not None:
        # The owner just moved: start following now, not on the next tick.
        ctx.world.companion_ai.owner_moved(bound[1], ctx.world.runtime.clock())
        ctx.world._announce()
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
        from tools.local_original_session.world_core_kit import defer_equipment_prepare
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
            r.template_bits == TOKEN_TEMPLATE or _companion_legacy_token(r) for r in items):
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
    token = next((r for r in items if r.template_bits == TOKEN_TEMPLATE), None)
    legacy = [r for r in items if _companion_legacy_token(r)]
    if legacy or token is None:
        from tools.local_original_session import item_transfer_protocol
        rows = [dict(r.raw_fields) for r in items if not _companion_legacy_token(r)]
        fields = None
        if token is None:
            fields = dict(ctx.starter_fields)
            # Native CommonItem2070/icon2181. Catalog raw f4=0 and ItemInfo f5=0
            # are distinct namespaces; the latter selects evidenced raw0 use.
            fields.update({1: max(r.identifier for r in items) + 1, 2: TOKEN_TEMPLATE,
                           4: 1, 5: 0, 7: TOKEN_ICON, 18: TOKEN_NAME})
            rows.append(fields)
        after = inventory.build_kit_frame(rows)
        # Reuse the inventory/equipment transfer owner when a legacy weapon or
        # equipment anchor leaves. This feature adds no common-core entrypoint.
        from tools.local_original_session import equipment_store
        effect = getattr(ctx, '_item_equipment_effect', None)
        equipment = (effect.store.restore(uid, current) if legacy and effect is not None
                     and type(effect.store) is equipment_store.EquipmentStore else None)
        changed_equipment = equipment_store.after_removal(equipment, current, after)
        if changed_equipment is None:
            changed = ctx.inventory_store.replace_kit(uid, current, after, append=True)
        else:
            changed = ctx.inventory_transactions.commit_inventory(uid, current, after,
                append=True, equipment_store=effect.store, equipment_before=equipment,
                equipment_after=changed_equipment)
            if effect._selection is not None:
                effect._selection['state'] = changed_equipment
        need(changed is True, 'COMPANION_KIT_PERSISTED_CHANGE_REQUIRED')
        ctx.inventory_frame = after
        wires = [item_transfer_protocol.build_remove(uid=r.identifier) for r in legacy]
        if fields is not None:
            wires.append(inventory.build_add(fields))
        await ctx._world_send(writer, row, tuple(wires), operation_lock)
        if changed_equipment is not None and changed_equipment.weapon_uid != equipment.weapon_uid:
            await _companion_refresh_owner_equipment(ctx, writer, row, uid, operation_lock)
    row['_companion_token_sent'] = True


async def _companion_refresh_owner_equipment(ctx, writer, row, uid, operation_lock):
    """Publish the existing stats hook and realm appearance after token unequip."""
    from tools.local_original_session.world_status_frames import full_status_frame
    def refresh():
        ctx.run_sync_hooks('stats_changed', uid)
        return full_status_frame(ctx.world.combat.pcs[uid].status_fields)
    status = await ctx.world.runtime.dispatch_now(refresh)
    service = ctx.realm.service(writer)
    position = service.snapshot()
    frames = ctx.realm._frames_for(position, heading=getattr(service, '_actor_heading', None))
    ctx.realm._world_frames[id(writer)] = (position, frames)
    from tools.local_game_session import session as _session
    from tools.local_original_session.world_core_kit import actor_appearance_changed, remember_self_actor
    actor = _session.world.decode_payload(0x4e96, frames[2][4:-2])
    changed = actor_appearance_changed(service, actor)
    # An unchanged self 4E96 would make the client rebuild the actor at its old cell.
    await ctx._world_send(writer, row, (status, frames[2]) if changed else (status,), operation_lock)
    if changed:
        remember_self_actor(service, actor, published=True)


def _companion_status_frame(ctx, actor):
    record = actor.record
    mode = ctx._companion_pet_modes.get(actor.ref.uid,
        4 if record.combat_mode == 'PASSIVE' else 3 if record.combat_mode == 'DEFEND' else 2)
    child = b''.join(pb.encode_uint32(n, value) for n, value in (
        (1, mode), (2, record.effective_max_hp), (3, record.hp),
        (4, record.effective_max_mp), (5, record.mp), (6, record.level)))
    from tools.local_original_session.world_progress import exp_percent
    child += b'\x51' + struct.pack('<d', exp_percent(ctx.world.data, record.exp, record.level))
    body = pb.encode_uint32(1, actor.ref.uid) + pb.encode_uint32(2, 1) + pb.encode_bytes(3, child)
    return struct.pack('<HH', len(body) + 6, 0x4f14) + body + b'\0\0'


def _companion_owned_actor(ctx, uid, member_uid, *, living=False, visible=True):
    actor = ctx.world.companions.retained_actor(member_uid)
    owner, entity = ctx.world.entities.get(uid), ctx.world.entities.get(member_uid)
    need(actor is not None and owner is not None and entity is not None
         and actor.owner_ref == owner.ref and actor.record.owner_character_id == uid
         and entity.map_id == owner.map_id, 'COMPANION_CURRENT_OWNED_ACTOR_REQUIRED')
    need(not living or ctx.world.companions.can_be_attacked(member_uid), 'COMPANION_LIVING_ACTOR_REQUIRED')
    if visible:
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
    received_params = None
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
                if resurrection is None and item.template_bits != TOKEN_TEMPLATE:
                    return False
                need(dict(item.raw_fields)[4] > 0, 'COMPANION_OWNED_KIT_REQUIRED')
                received_params = bytes(fields[2][0].value)
                with pb.parse_message(received_params) as params:
                    expected = {1: 1, 15: 0, 16: 0}
                    untargeted = (resurrection is not None and item.template_bits == 28
                                  and not params.occurrences(2))
                    target_uid = None
                    if resurrection is not None and not untargeted:
                        expected[3] = 0
                        need(len(params.occurrences(2)) == 1, 'COMPANION_TARGET_UID_REQUIRED')
                        target_uid = params.occurrences(2)[0].value  # run393 int64 varint
                        need(type(target_uid) is int and 0 < target_uid < (1 << 63),
                             'COMPANION_TARGET_UID_REQUIRED')
                        expected[2] = target_uid
                    if untargeted:
                        need(all(len(params.occurrences(n)) == 1
                                 and params.occurrences(n)[0].value == value
                                 for n, value in expected.items())
                             and all(f.wire_type == 0 and (f.number in expected or f.value == 0)
                                     and len(params.occurrences(f.number)) == 1 for f in params.fields),
                             'COMPANION_TARGETED_PARAMS_REQUIRED')
                    else:
                        need(len(params.fields) == len(expected)
                             and all(len(params.occurrences(n)) == 1 for n in expected)
                             and {f.number: f.value for f in params.fields} == expected
                             and all(f.wire_type == 0 for f in params.fields),
                             'COMPANION_TARGETED_PARAMS_REQUIRED' if resurrection is not None
                             else 'COMPANION_RAW0_PARAMS_REQUIRED')
                command = ('resurrect', target_uid, item.identifier, item.template_bits) if resurrection else (
                    'call', item.identifier)
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
                actor = (_companion_nearby_revive_target(ctx, uid) if command[1] is None
                         else _companion_revive_target(ctx, uid, command[1]))
                # Recheck the stack inside the same serialized world callback.
                current = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                    if r.identifier == command[2]), None)
                need(current is not None and current.template_bits == command[3]
                     and dict(current.raw_fields)[4] > 0, 'COMPANION_OWNED_SCROLL_REQUIRED')
                definition = ctx._companion_item_effects[current.template_bits]
                attempted = True
                cost = (ctx._world_consume_kit(writer, current.identifier),)
                _companion_revive(ctx, uid, actor.record, hp_divisor=definition.revive_hp_divisor)
                if command[1] is None:
                    detail = dict(opcode=frame.opcode, params_hex=received_params[:256].hex(),
                                  params_bytes=len(received_params))
                    ctx._companion_untargeted_params = (
                        getattr(ctx, '_companion_untargeted_params', []) + [detail])[-8:]
            elif command[0] == 'call':
                current = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                                if r.identifier == command[1]), None)
                need(current is not None and current.template_bits == TOKEN_TEMPLATE
                     and dict(current.raw_fields)[4] > 0, 'COMPANION_OWNED_KIT_REQUIRED')
                try:
                    actor = _companion_call(ctx, uid)
                except ValueError as error:
                    if str(error) != 'COMPANION_TARGETED_SCROLL_REQUIRED':
                        raise
                    ctx._companion_errors = (ctx._companion_errors + [str(error)])[-8:]
                    cost = (_companion_dead_notice(),)
            else:
                actor = _companion_owned_actor(ctx, uid, command[1], visible=False)
                # Remote menus are for the current summoned living member. The
                # retained visible corpse query keeps its previous behavior.
                if command[0] == 'pet' or actor.record.alive:
                    need(actor.record.summoned and ctx.world.companions.can_be_attacked(actor.ref.uid),
                         'COMPANION_LIVING_ACTOR_REQUIRED')
                else:
                    _companion_owned_actor(ctx, uid, command[1])
                if command[0] == 'pet':
                    need(ctx._companion_windows.get(id(writer)) == actor.ref, 'COMPANION_DRAINED_PET_WINDOW_REQUIRED')
                    mode, targets = command[2:]
                    need(mode in (1, 2, 3, 4, 8), 'COMPANION_PET_COMMAND_UNSUPPORTED')
                    need(len(targets) == (1 if mode == 1 else 0), 'COMPANION_PET_TARGET_FIELDS_REQUIRED')
                    now = ctx.world.runtime.clock()
                    if mode == 8:
                        # Ordinary saved characters have no pet-dismiss action.
                        # Consume the legacy request without changing this lifetime.
                        pass
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
                            # Attack-target designation: focus this monster.
                            ctx.world.companion_ai.focus_target(actor.ref, target.ref, now)
                        ctx._companion_pet_modes[actor.ref.uid] = mode
                        _companion_publish_map(ctx, uid, actor)
            if actor is not None and command[0] in ('query', 'call'):
                # The DLL rewrites the pet window to 7 rows only for mapped actors.
                _companion_publish_map(ctx, uid, actor)
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
        if str(error) == 'COMPANION_NEARBY_CORPSE_REQUIRED':
            body = pb.encode_uint32(1, 12066) + pb.encode_bytes(2,
                '근처에 부활할 동료 시체가 없습니다.'.encode('utf-8'))
            notice = struct.pack('<HH', len(body) + 6, 0x4eea) + body + b'\0\0'
            await ctx._world_send(writer, row, [notice], operation_lock)
        if str(error) in ('COMPANION_TARGET_UID_REQUIRED', 'COMPANION_TARGETED_PARAMS_REQUIRED'):
            detail = dict(error=str(error), opcode=frame.opcode,
                          params_hex=received_params[:256].hex(), params_bytes=len(received_params))
            ctx._companion_error_params = (getattr(ctx, '_companion_error_params', []) + [detail])[-8:]
    return True


async def _companion_before_leave(ctx, writer, uid):
    party = getattr(ctx, '_companion_party', None)
    if party is not None:
        await ctx.world.runtime.dispatch_now(party.depart, uid)


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
    from tools.local_original_session.world_progress import base_maxima
    hp, mp = base_maxima(state)
    changed = (member.hp, member.mp, member.level, member.exp, member.max_hp, member.max_mp) != (
        state.hp, state.mp, state.profile.level, ctx.world.exp[uid], hp, mp)
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
    member.max_hp, member.max_mp = hp, mp
    if bag_changed or equipment_changed or changed:
        bags.refresh(uid, publish=False)
    ctx._companion_save(member.owner_character_id)


def _companion_stopped(ctx):
    ctx._companion_ailments.close()
    bags = ctx._companion_inventory
    if bags is not None and getattr(bags, 'pickup_handle', None) is not None:
        bags.pickup_handle.close()
    if ctx._companion_store is not None:
        ctx._companion_save(0)


METHODS = (_companion_initialize, _companion_started, _companion_save, _companion_before_enter, _companion_enter,
           _companion_kit, _companion_status_frame, _companion_frame, _companion_before_leave,
           _companion_after_leave, _companion_stopped,
           _companion_after_move, _companion_player_inventory)
HOOKS = {'initialize': ('_companion_initialize',), 'runtime_started': ('_companion_started',),
         'before_enter': ('_companion_before_enter',),
         'after_enter': ('_companion_enter',), 'after_request': ('_companion_kit', '_companion_player_inventory'),
         'after_move': ('_companion_after_move',),
         'before_leave': ('_companion_before_leave',),
         'after_leave': ('_companion_after_leave',), 'runtime_stopped': ('_companion_stopped',)}
FRAMES = {opcode: ('_companion_frame',) for opcode in (0x0960, 0x4f13, 0x4f02)}
OUTGOING_OPCODES = (0x4f14, 0x4ed8, 0x4f16, 0x4eea, 0x08a0, 0x08a1, 0x08a3)


def _companion_give_provider(ctx):
    return ctx._companion_inventory


def _companion_report_give_error(ctx, error):
    ctx._companion_errors = (ctx._companion_errors + [str(error)[:96]])[-8:]


def _companion_selected_exp(ctx, value, position):
    member = ctx.world.companions.records.get(position.uid)
    return value if member is None else member.exp


def _companion_realm_status(realm, fields, position, initial):
    provider = getattr(realm, '_world_companion_record', None)
    member = None if not initial or provider is None else provider(position.uid)
    if member is not None:
        fields = dict(fields)
        # Core _world_fields_for projects this initial PC seed exactly once.
        # Keep grown maxima here, while retaining equipped current resources.
        fields.update({2: member.level, 10: member.hp, 11: member.max_hp,
                       12: member.mp, 13: member.max_mp})
    return fields


def _companion_relocate_keeps_self(ctx, uid):
    return any(actor.owner_ref.uid == uid and actor.character_id in ctx._companion_rows
               for actor in ctx.world.companions.active.values())


def _companion_before_relocate(ctx, uid, transit):
    if ctx._companion_enabled:
        transit['companion'] = _companion_relocate_depart(ctx, uid)


def _companion_after_relocate(ctx, uid, transit):
    members = transit.get('companion', ())
    return () if not members else _companion_relocate_arrive(ctx, uid, members)


def _companion_joint_progress_sources(ctx, uid):
    store = ctx._companion_store
    if store is None:
        return None
    row = store.payload['owners'].get(str(uid))
    if row is None:
        return None
    return dict(row), store.path.stat().st_mtime_ns if store.path.exists() else 0


def _companion_joint_progress_adopt(ctx, uid, saved):
    store = ctx._companion_store
    if store is not None and str(uid) in store.payload['owners']:
        store.payload['owners'][str(uid)] = dict(saved)


METHODS += (_companion_give_provider, _companion_selected_exp,
            _companion_relocate_keeps_self, _companion_before_relocate,
            _companion_after_relocate, _companion_joint_progress_sources,
            _companion_joint_progress_adopt)
HOOKS.update(give_provider=('_companion_give_provider',),
    selected_exp=('_companion_selected_exp',),
    relocate_keeps_self=('_companion_relocate_keeps_self',),
    before_relocate=('_companion_before_relocate',),
    after_relocate=('_companion_after_relocate',),
    joint_progress_sources=('_companion_joint_progress_sources',),
    joint_progress_adopt=('_companion_joint_progress_adopt',))
REALM_HOOKS = {'status_fields': (_companion_realm_status,)}


# ---- 1부: class data, speed, owner death, death EXP, ATS policy ------------
def _companion_intervals(ctx, rt):
    """(walk_s, attack_s): class/body/weapon client timing x own speed effects."""
    defs, record = ctx._companion_defs, rt.record
    row = ctx._companion_rows.get(rt.character_id)
    if defs is None or row is None or record.class_id not in defs.classes:
        return None  # pets and unknown actors keep the runtime fallback
    look = ctx.world.companion_looks.get(rt.character_id, {})
    walk, attack = defs.action_ms(record.class_id, row['gender'], look.get('weapon_type'))
    bags = ctx._companion_inventory
    factor = 1.0 if bags is None else bags.speed_factor(rt.character_id, ctx.world.runtime.clock())
    return walk / 1000 * factor, attack / 1000 * factor


def _companion_owner_death(ctx, uid, now):
    """Owner died: each living member reads its own return scroll or waits.

    With a return scroll in its own bag the member spends one and leaves for
    town through the normal destination policy and PositionStore, then retires
    the old actor. It stays summoned for the owner's next entry. Without one it holds beside the
    body; if the owner then leaves the map it is left behind (summoned off).
    """
    view, kept = ctx.world, []
    bags = ctx._companion_inventory
    for actor in tuple(view.companions.active.values()):
        if (actor.owner_ref.uid != uid or actor.character_id not in ctx._companion_rows
                or not actor.record.alive):
            continue
        actor.target = actor.focus = None
        from tools.local_original_session import inventory
        from tools.local_original_session.world_maps import MapDestination
        entity = view.entities.resolve(actor.ref)
        templates = ctx._companion_defs.return_scroll_templates
        owned = () if bags is None else inventory.validate_kit_frame(bags.frames[actor.character_id])
        template = next((template for template in templates
                         if any(item.template_bits == template and dict(item.raw_fields)[4] > 0
                                for item in owned)), None)
        if template is not None:
            position = MapDestination(entity.map_id, entity.x, entity.y, entity.heading)
            destination = ctx._world_return_destination(template, position)
            need(bags.consume_template(actor.character_id, (template,)) == template,
                 'COMPANION_OWNED_RETURN_SCROLL_REQUIRED')
            saved = ctx._world_relocate_saved_character(actor.character_id,
                ctx._companion_rows[actor.character_id]['name'], destination)
            # The same admitted destination changes runtime occupancy before the
            # shared owner-death lifetime removes the old actor and its timers.
            view.entities.move(entity.uid, saved.map_id, saved.word0, saved.word1, destination.heading)
            ctx._companion_returns = (ctx._companion_returns + [dict(
                character_id=actor.character_id, owner=uid, template=template,
                result='RETURN_SCROLL_TO_TOWN', destination=saved.metadata(), at=now)])[-16:]
            continue
        actor.owner_down = True
        actor.action = 'HOLD'
        kept.append(actor.character_id)
        ctx._companion_returns = (ctx._companion_returns + [dict(
            character_id=actor.character_id, owner=uid, template=None,
            result='WAIT_NO_RETURN_SCROLL', at=now)])[-16:]
    view._save_companion(uid)
    return kept


def _companion_death_penalty(ctx, record, now):
    """Same LOCAL EXP/base HP-MP loss as an ordinary saved character."""
    if record.character_id not in ctx._companion_rows:
        return
    from dataclasses import replace as _replace
    from tools.local_original_session import world_reward
    profile = ctx.world.companion_profiles.get(record.character_id)
    try:
        penalty = world_reward.death_exp_penalty(record.exp, data=ctx.world.data)
        hp, mp = record.max_hp, record.max_mp
        if profile is not None:
            hp, mp = world_reward.delevel_maxima(world_reward.RewardPcState.from_companion(
                record, profile, attributes=ctx._companion_rows[record.character_id].get('attributes')),
                penalty.new_level, ctx.world.combat.rng, data=ctx.world.data)
        elif penalty.new_level != penalty.old_level:
            raise ValueError('COMPANION_GROWTH_PROFILE_REQUIRED')
    except ValueError as error:
        ctx._companion_errors = (ctx._companion_errors + [str(error)[:96]])[-8:]
        return
    record.exp, record.level = penalty.new_exp, penalty.new_level
    record.max_hp, record.max_mp = hp, mp
    record.hp, record.mp = min(record.hp, record.effective_max_hp), min(record.mp, record.effective_max_mp)
    if profile is not None:
        ctx.world.companion_profiles[record.character_id] = _replace(profile, level=penalty.new_level)
    ctx._companion_death_penalties = (ctx._companion_death_penalties + [dict(
        character_id=record.character_id, old_exp=penalty.old_exp, new_exp=penalty.new_exp,
        lost=penalty.exp_lost, old_level=penalty.old_level, new_level=penalty.new_level,
        at=now)])[-16:]


def _companion_ats_policy(ctx, record):
    """Normalized saved companion ATS policy from an optional feature, or None."""
    return ctx.fold_sync_hooks('companion_ai_policy', None, record.character_id)


# ---- 2부: pet-window rows and bag/equipment windows -------------------------
def _companion_signal_actor(ctx, uid, low32):
    for actor in ctx.world.companions.active.values():
        if (actor.owner_ref.uid == uid and actor.character_id in ctx._companion_rows
                and actor.ref.uid & 0xFFFFFFFF == low32):
            return actor
    return None


def _companion_lawful(ctx, member):
    try:
        lawful = ctx._world_progress.get(member).lawful
    except Exception:
        return None
    return lawful if type(lawful) is int else None


def _companion_publish(ctx, uid, kind, payload):
    entry = dict(kind=kind, owner=uid, **{k: v for k, v in payload.items() if k != 'frame'})
    if 'frame' in payload:
        entry['frame_bytes'] = len(payload['frame'])
    ctx._companion_published = (ctx._companion_published + [entry])[-32:]
    ctx.run_sync_hooks('companion_bridge_publish', uid, kind, payload)


def _companion_identity(ctx, uid, actor):
    entity = ctx.world.entities.get(actor.ref.uid)
    return None if entity is None else (entity.uid, entity.generation, uid, actor.character_id)


def _companion_publish_map(ctx, uid, actor):
    """Current actor UID64/generation/owner/member/hold mapping for the DLL."""
    from tools.local_original_session import world_companion_ui as ui
    identity = _companion_identity(ctx, uid, actor)
    if identity is None:
        return None
    hold = actor.record.movement_mode == 'HOLD'
    request = ui.map_request(actor=identity[0], generation=identity[1], owner=uid,
        member=actor.character_id, hold=hold, lawful=_companion_lawful(ctx, actor.character_id),
        name=ctx.world.companion_looks.get(actor.character_id, {}).get('name', ''))
    key = identity + (hold, request['name_hex'])
    if ctx._companion_mapped.get(actor.character_id) == key:
        return identity
    previous = ctx._companion_mapped.get(actor.character_id)
    if previous is None or previous[:4] != identity:
        ctx._companion_model_revision.setdefault(identity, 0)  # new mapping starts at zero
    ctx._companion_mapped.pop(actor.character_id, None)
    _companion_publish(ctx, uid, 'map', request)
    return identity


def _companion_unmapped(ctx, actor):
    mapped = ctx._companion_mapped.pop(actor.character_id, None)
    if mapped is None:
        # A failed map can still be pending in the transport when the actor retires.
        mapped = (actor.ref.uid, actor.ref.generation, actor.owner_ref.uid, actor.character_id, False)
    actor_uid, generation, owner, member = mapped[:4]
    ctx._companion_model_revision.pop(mapped[:4], None)
    ctx._companion_views.pop(owner, None)
    _companion_publish(ctx, owner, 'unmap', dict(command='unmap', actor_uid=actor_uid,
        actor_generation=generation, owner_uid=owner, member_id=member, hold=0,
        lawful_known=0, lawful=0, event_seq=0, ats_epoch=0))


def _companion_model(ctx, uid, actor, views):
    """One explicit replace snapshot of the member's real saved bag/gear/status."""
    from tools.local_original_session import world_companion_ui as ui
    from tools.local_original_session.world_progress import exp_percent
    from tools.local_native_login_self_actor_hook import hook as actor_hook
    bags = ctx._companion_inventory
    need(bags is not None, 'COMPANION_INVENTORY_REQUIRED')
    member, record = actor.character_id, actor.record
    identity = _companion_publish_map(ctx, uid, actor)
    need(identity is not None, 'COMPANION_CURRENT_ACTOR_REQUIRED')
    revision = ctx._companion_model_revision.get(identity, 0) + 1
    ctx._companion_model_revision[identity] = revision
    frame, state = bags.frames[member], bags.states[member]
    calculated, _ = bags.calculated(member)
    fields = ui.status_fields(actor_hook.profiles()[0].fields, character_id=member, record=record,
        calculated=calculated, lawful=_companion_lawful(ctx, member),
        exp_percent=exp_percent(ctx.world.data, record.exp, record.level))
    from tools.local_original_session.world_visibility import item_names
    packets = [(0x0964, ui.bag_body(frame, ctx.world.data.items, item_names()))]
    packets += [(0x097A, body) for body in ui.equipment_bodies(frame, state, ctx.world.data.items)]
    packets.append((0x4E38, ui.status_body(fields)))
    model = ui.model_frame(actor=identity[0], generation=identity[1], owner=uid, member=member,
                           revision=revision, packets=packets, replace=True)
    opened = ctx._companion_views.get(uid)
    epochs = dict(opened.get('epochs', {})) if opened and opened['member'] == member else {}
    ctx._companion_views[uid] = dict(member=member, views=tuple(sorted(views)), epochs=epochs,
        fingerprint=opened.get('fingerprint') if opened and opened['member'] == member else None,
        pending_fingerprint=(frame, state, record.level), pending_revision=revision)
    _companion_publish(ctx, uid, 'model', dict(frame=model, member=member, revision=revision,
        views=tuple(sorted(views)), view_epochs=tuple(sorted(epochs.items())),
        packets=tuple(op for op, _ in packets)))
    return model


def _companion_bridge_posted(ctx, uid, kind, payload):
    if kind == 'map':
        ctx._companion_mapped[payload['member_id']] = (
            payload['actor_uid'], payload['actor_generation'], uid, payload['member_id'],
            bool(payload['hold']), payload.get('name_hex', ''))
    elif kind == 'model':
        opened = ctx._companion_views.get(uid)
        if opened and opened['member'] == payload['member'] and opened.get('pending_revision') == payload['revision']:
            opened['fingerprint'] = opened['pending_fingerprint']


def _companion_bridge_model_failed(ctx, uid, payload):
    opened = ctx._companion_views.get(uid)
    if (not opened or opened['member'] != payload['member']
            or tuple(sorted(opened.get('epochs', {}).items())) != payload.get('view_epochs')):
        return
    actor = ctx.world.companions.active.get(opened['member'])
    if actor is not None and actor.owner_ref.uid == uid:
        _companion_model(ctx, uid, actor, opened['views'])


def _companion_refresh_views(ctx):
    """An open bag/equipment view gets the new real result after any change."""
    bags = ctx._companion_inventory
    if bags is None or not ctx._companion_views:
        return
    for uid, opened in tuple(ctx._companion_views.items()):
        actor = ctx.world.companions.active.get(opened['member'])
        member = opened['member']
        if actor is None or member not in bags.frames:
            ctx._companion_views.pop(uid, None)
            continue
        record = actor.record
        # Bag/equipment/level changes only: HP/MP ticks do not flood the DLL.
        fingerprint = (bags.frames[member], bags.states[member], record.level)
        if fingerprint not in (opened.get('fingerprint'), opened.get('pending_fingerprint')):
            _companion_model(ctx, uid, actor, opened['views'])


def _companion_notice(text):
    body = pb.encode_uint32(1, 12066) + pb.encode_bytes(2, text.encode('utf-8'))
    return struct.pack('<HH', len(body) + 6, 0x4eea) + body + b'\0\0'


def _companion_ui_signal(ctx, writer, uid, signal, meta=None):
    """Pet-window LOCAL rows and companion window requests (world lock held).

    Returns a result dict for companion operations, None for operations owned
    by another feature (ATS scope selection). The first three pet rows (target,
    attack, defend) stay on the original 4F02 mode1/2/3 path.
    """
    if not getattr(ctx, '_companion_enabled', False):
        return None
    operation = signal.operation
    if operation in ('ats-select', 'settings-load', 'ats-edit-close', 'ats-edit-restored',
                     'ats-window-open', 'ats-window-save'):
        return None  # ATS scope / owner edit of the member's setting (world_feature_companion_ats)
    if operation == 'f4-pickup':
        bags = ctx._companion_inventory
        need(bags is not None, 'COMPANION_INVENTORY_REQUIRED')
        candidates = 0
        members = []
        for actor in ctx.world.companions.active.values():
            if actor.owner_ref.uid == uid and ctx.world.companions.can_be_attacked(actor.ref.uid):
                candidates += bags.request_pickup(actor, ctx.world.runtime.clock())
                members.append(actor.character_id)
        return dict(status='QUEUED' if candidates else 'NO_ITEMS', candidates=candidates, members=members)
    view = ctx.world
    actor = _companion_signal_actor(ctx, uid, signal.actor_uid)
    need(actor is not None, 'COMPANION_SIGNAL_CURRENT_ACTOR_REQUIRED')
    now = view.runtime.clock()
    result = dict(status='OK', operation=operation, member=actor.character_id)
    if operation == 'pet-window-open':
        bound = ctx._world_pcs.get(id(writer))
        need(bound == (writer, uid) and ctx._world_bound(writer)
             and ctx.realm.service(writer).snapshot().uid == uid
             and view.combat.can_be_attacked(uid), 'COMPANION_CURRENT_SELECTED_OWNER_REQUIRED')
        _companion_owned_actor(ctx, uid, actor.ref.uid, living=True, visible=False)
        need(actor.record.summoned, 'COMPANION_SIGNAL_CURRENT_ACTOR_REQUIRED')
        identity = _companion_identity(ctx, uid, actor)
        need(meta is not None and meta.get('transport') == 'LOCAL_IPC'
             and identity == tuple(meta.get(key) for key in
                 ('native_actor_uid', 'actor_generation', 'owner_uid', 'member_id')),
             'COMPANION_SIGNAL_MEMBER_GENERATION_MISMATCH')
        _companion_publish_map(ctx, uid, actor)
        view._queue(uid, _companion_status_frame(ctx, actor))
    elif operation in ('movement-follow', 'movement-hold'):
        need(view.companions.can_be_attacked(actor.ref.uid), 'COMPANION_LIVING_ACTOR_REQUIRED')
        hold = operation == 'movement-hold'
        # Follow / hold rows: support only (buff/heal), never attack (결정 4차).
        view.companions.set_commands(actor.character_id, combat_mode='PASSIVE',
            movement_mode='HOLD' if hold else 'FOLLOW', now=now)
        view.companion_ai.command_changed(actor.ref, now)
        ctx._companion_pet_modes.pop(actor.ref.uid, None)
        _companion_publish_map(ctx, uid, actor)
        view._queue(uid, _companion_status_frame(ctx, actor))
    elif operation in ('bag-open-take', 'equipment-open'):
        kind = 'bag' if operation == 'bag-open-take' else 'equipment'
        opened = ctx._companion_views.get(uid)
        views = set(opened['views']) if opened and opened['member'] == actor.character_id else set()
        views.add(kind)
        epochs = dict(opened.get('epochs', {})) if opened and opened['member'] == actor.character_id else {}
        epoch = (meta or {}).get('view_epoch', 0)
        need(type(epoch) is int and 0 <= epoch < 1 << 64, 'COMPANION_SIGNAL_VIEW_EPOCH_MISMATCH')
        need(epoch >= epochs.get(kind, 0), 'COMPANION_SIGNAL_VIEW_EPOCH_MISMATCH')
        epochs[kind] = epoch
        ctx._companion_views[uid] = dict(member=actor.character_id, views=tuple(sorted(views)), epochs=epochs)
        _companion_model(ctx, uid, actor, views)
        result['view'] = kind
    else:
        result.update(_companion_item_request(ctx, writer, uid, actor, signal))
    ctx._companion_ui_events = (ctx._companion_ui_events + [dict(result, at=now)])[-32:]
    ctx._companion_save(uid)
    view._announce()
    return result


def _companion_ui_delivered(ctx, writer, uid, signal, meta):
    """Admit legacy menu commands only after the queued 4F14 was sent."""
    if signal.operation != 'pet-window-open':
        return
    actor = _companion_signal_actor(ctx, uid, signal.actor_uid)
    if (actor is not None and ctx._world_pcs.get(id(writer)) == (writer, uid)
            and _companion_identity(ctx, uid, actor) == tuple(meta.get(key) for key in
                ('native_actor_uid', 'actor_generation', 'owner_uid', 'member_id'))):
        ctx._companion_windows[id(writer)] = actor.ref


def _companion_item_request(ctx, writer, uid, actor, signal):
    """item-give/take/equip/unequip on the two real saved characters."""
    view, bags = ctx.world, ctx._companion_inventory
    need(bags is not None, 'COMPANION_INVENTORY_REQUIRED')
    need(view.companions.can_be_attacked(actor.ref.uid), 'COMPANION_LIVING_ACTOR_REQUIRED')
    need(actor.character_id not in view.pcs, 'COMPANION_MEMBER_SELECTED')
    numbers = signal.numbers()
    member, generation, view_epoch, item_uid = numbers[:4]
    entity = view.entities.get(actor.ref.uid)
    need(member == actor.character_id and entity is not None and generation == entity.generation,
         'COMPANION_SIGNAL_MEMBER_GENERATION_MISMATCH')
    opened = ctx._companion_views.get(uid)
    kind = 'equipment' if signal.operation == 'item-unequip' else 'bag'
    need(opened is not None and opened['member'] == member
         and opened.get('epochs', {}).get(kind) == view_epoch,
         'COMPANION_SIGNAL_VIEW_EPOCH_MISMATCH')
    need(item_uid < 1 << 32, 'COMPANION_ITEM_UID_RANGE')
    operation = signal.operation
    frames = ()
    if operation == 'item-give':
        frames = (bags.give(uid, actor, item_uid, numbers[4], ctx.inventory_frame),)
    elif operation == 'item-take':
        position = ctx.realm.service(writer).snapshot()
        calculated, _, _ = ctx._world_stats_for(position)
        frames = bags.take(uid, actor, item_uid, numbers[4], ctx.inventory_frame,
                           owner_max_weight=calculated.max_weight)
    elif operation == 'item-equip':
        bags.set_equipped(actor.character_id, item_uid, True)
    else:
        bags.set_equipped(actor.character_id, item_uid, False, slot_key=numbers[4])
    for frame in frames:
        view._queue(uid, frame)
    opened = ctx._companion_views.get(uid)
    views = set(opened['views']) if opened and opened['member'] == actor.character_id else {'bag'}
    _companion_model(ctx, uid, actor, views)
    return dict(view_epoch=view_epoch, item=item_uid, owner_frames=len(frames))


METHODS += (_companion_ui_signal, _companion_ui_delivered, _companion_ats_policy,
            _companion_learned_spells, _companion_learning_changed,
            _companion_bridge_posted, _companion_bridge_model_failed)
HOOKS.update(companion_ui_signal=('_companion_ui_signal',),
             companion_ui_delivered=('_companion_ui_delivered',),
             companion_bridge_posted=('_companion_bridge_posted',),
             companion_bridge_model_failed=('_companion_bridge_model_failed',),
             magic_learning_changed=('_companion_learning_changed',))


class CompanionAilments:
    """Follower-owned timed effects, persisted in existing LOCAL effect metadata.

    The monster feature contributes through the target adapter. This owner also
    restores/ticks effects when the producer is disabled; no second HP ledger,
    task, or inventory format is introduced. Offline time expires effects but
    never replays poison damage.
    """
    def __init__(self, view, ctx=None):
        self.view, self.ctx = view, ctx
        self.rows, self.subscriptions, self.events = {}, [], []

    def start(self):
        if self.subscriptions:
            return
        for event, callback in (('tick', self.tick), ('actor_action_status', self.action_status),
                                ('close', self.close)):
            entry = self.view.events.add('companion_ailments', event, callback)
            self.subscriptions.append((event, entry))

    def close(self, *_):
        for event, entry in self.subscriptions:
            self.view.events.remove(event, entry)
        self.subscriptions.clear()
        self.rows.clear()

    def clear(self, record):
        """Every death path clears the same saved/cache state before revival."""
        self.rows.pop(record.character_id, None)
        record.equipment.pop('monster_ailments', None)

    def state(self, actor, now):
        import time
        from tools.local_original_session import world_magic_status as status
        key = actor.character_id
        if key not in self.rows:
            saved = actor.record.equipment.get('monster_ailments')
            effects, poison = {}, None
            if saved is not None:
                elapsed = max(0, time.time() - saved['saved_at'])
                effects = status.restore(saved['effects'], now, elapsed)
                raw = saved.get('poison')
                if raw is not None and raw['remaining'] > elapsed:
                    poison = dict(until=now + raw['remaining'] - elapsed,
                        next_tick=now + max(0, raw['tick_remaining'] - elapsed),
                        tick_seconds=raw['tick_seconds'], damage=raw['damage'], source_uid=raw['source_uid'])
            self.rows[key] = dict(effects=effects, poison=poison)
        return self.rows[key]

    def save(self, actor, now):
        import time
        from tools.local_original_session import world_magic_status as status
        row = self.state(actor, now)
        poison = row['poison']
        actor.record.equipment['monster_ailments'] = dict(saved_at=time.time(),
            effects=status.snapshot(row['effects'], now), poison=None if poison is None else dict(
                remaining=max(0, poison['until'] - now),
                tick_remaining=max(0, poison['next_tick'] - now),
                tick_seconds=poison['tick_seconds'], damage=poison['damage'], source_uid=poison['source_uid']))
        self.view._save_companion(actor.owner_ref.uid)

    def cure(self, actor, now):
        row = self.state(actor, now)
        changed = row['poison'] is not None
        row['poison'] = None
        for kind in ('paralyze', 'silence'):
            effect = row['effects'].get(kind)
            if effect is not None and effect['params'].get('monster_poison'):
                del row['effects'][kind]
                changed = True
        if changed:
            self.save(actor, now)
        return changed

    def action_status(self, current, ref, now):
        from tools.local_original_session import world_magic_status as status
        actor = self.view.companions.get_actor(ref.uid)
        if actor is None or actor.ref != ref:
            return current
        row = self.state(actor, now)
        expired = bool(status.expire(row['effects'], now))
        if row['poison'] is not None and row['poison']['until'] <= now:
            row['poison'], expired = None, True
        if expired:
            self.save(actor, now)
        # Existing saved ATS function slots explicitly opt into antidote use.
        ctx = self.ctx
        bags = None if ctx is None else ctx._companion_inventory
        poisoned = row['poison'] is not None or any(
            e['params'].get('monster_poison') for e in row['effects'].values())
        if bags is not None and poisoned and now >= bags.next_potion.get(actor.character_id, 0):
            policy = _companion_ats_policy(ctx, actor.record) or {}
            slots = [s for s in policy.get('function_slots', ())
                     if s.get('template') in ctx._companion_antidotes] if policy.get('status') == 'valid' else []
            used = bags.consume_ats_item(actor.character_id, slots)
            if used is not None:
                bags.next_potion[actor.character_id] = now + 1
                self.cure(actor, now)
                bags.events.append(dict(character_id=actor.character_id, template=used,
                                        consumed=1, poison_cured=True, at=now))
                del bags.events[:-32]
                bags.save(actor.owner_ref.uid)
        own = status.ai_status(row['effects'], now)
        return dict(current, blocked=current.get('blocked', False) or own['blocked'],
            silenced=current.get('silenced', False) or status.active(row['effects'], 'silence', now) is not None,
            move_factor=current.get('move_factor', 1) * own['move_factor'],
            attack_factor=current.get('attack_factor', 1) * own['attack_factor'])

    def tick(self, now):
        from tools.local_original_session import world_magic_status as status
        for actor in tuple(self.view.companions.active.values()):
            if not self.view.companions.can_be_attacked(actor.ref.uid):
                continue
            row = self.state(actor, now)
            changed = bool(status.expire(row['effects'], now))
            poison = row['poison']
            if poison is not None:
                if now >= poison['until']:
                    row['poison'], changed = None, True
                elif now >= poison['next_tick']:
                    poison['next_tick'] = now + poison['tick_seconds']
                    before = actor.record.hp
                    target = CompanionMonsterTarget(self.view, actor, self)
                    target.damage(poison['damage'], now)
                    if not actor.record.alive:
                        from tools.local_original_session.world_combat import Swing
                        target.finish(None, Swing(True, before), now)
                    self.events.append(dict(kind='poison_tick', target=actor.ref.uid,
                        hp_before=before, hp_after=actor.record.hp, at=now))
                    del self.events[:-64]
                    changed = True
            if changed:
                self.save(actor, now)


from tools.local_original_session.world_companion_runtime import CompanionMagicTarget


class CompanionMonsterTarget(CompanionMagicTarget):
    """Selector-free damage/status consumer exposed by npc_magic_target."""
    def __init__(self, view, actor, ailments):
        super().__init__(view, actor)
        self.owner = ailments

    def current(self):
        return (self.view.companions.get_actor(self.actor.ref.uid) is self.actor
                and self.view.entities.resolve(self.actor.ref) is not None
                and self.view.combat.can_be_attacked(self.actor.owner_ref.uid))

    def ailments(self, now):
        return self.owner.state(self.actor, now)

    def damage(self, amount, now):
        if not self.current():
            return 0
        before = self.hp
        self.actor.record.hp = max(0, before - amount)
        if self.hp == 0:
            self.view.companions.die(self.actor.character_id, now)
        return before - self.hp

    def physical(self, monster, now, *, leverage=10, factor=1):
        from tools.local_original_session import world_combat as combat
        if not self.current():
            return None
        profile = replace(self.profile, level=self.actor.record.level)
        magic = self.view.companion_ai.magic
        if magic is not None:
            profile = magic.profile(self.actor, profile, now, defense=True)
        if self.actor.shield_until > now:
            profile = replace(profile, ac=profile.ac - 2)
        swing = combat.npc_hits_pc(monster, profile, self.view.combat.rng)
        swing = replace(swing, damage=max(0, int(swing.damage * leverage / 10 * factor)))
        if swing.landed and swing.damage > 0:
            self.damage(swing.damage, now)
        return swing

    def apply(self, monster, attack, now):
        if not self.current():
            return None
        return super().apply(monster, attack, now)

    def finish(self, source_ref, swing, now):
        from tools.local_original_session import world_combat as combat
        target = self.view.entities.get(self.actor.ref.uid)
        if not self.actor.record.alive and target is not None:
            self.ailments(now).update(effects={}, poison=None)
            for uid in self.view._watchers(target):
                self.view._queue(uid, combat.death_frame(target.uid))
        elif swing.landed and swing.damage > 0:
            self.view.companion_ai.on_hit(self.actor.ref, source_ref, now)
        self.save(now)

    def apply_status(self, kind, now, duration, **kwargs):
        from tools.local_original_session import world_magic_status as status
        status.apply(self.ailments(now)['effects'], kind, now, duration, **kwargs)

    def save(self, now):
        self.owner.save(self.actor, now)

    def cure_poison(self, now):
        return self.owner.cure(self.actor, now)


def _companion_npc_magic_target(ctx, uid):
    """Target contribution only; an installed producer owns NPC costs/reuse."""
    if not getattr(ctx, '_companion_enabled', False):
        return None
    actor = ctx.world.companions.get_actor(uid)
    if actor is None or not ctx.world.companions.can_be_attacked(uid):
        return None
    return CompanionMonsterTarget(ctx.world, actor, ctx._companion_ailments)


def _companion_magic_buff_target(ctx, uid, key, source_uid):
    if not getattr(ctx, '_companion_enabled', False):
        return None
    magic = getattr(ctx.world.companion_ai, 'magic', None)
    return None if magic is None else magic.received_buff_target(uid, key, source_uid)


def _companion_cure_poison(ctx, uid):
    target = _companion_npc_magic_target(ctx, uid)
    if target is not None:
        target.cure_poison(ctx.world.runtime.clock())


def _companion_cancel_magic_target(ctx, uid):
    """LOCAL magic buffs only; owner HUD icons never represent this actor.

    4E91 has no actor UID. CompanionMagic publishes no companion buff icons,
    so deleting an owner's same-key icon here would corrupt the owner's HUD.
    """
    target = _companion_npc_magic_target(ctx, uid)
    magic = ctx.world.companion_ai.magic
    if target is None or magic is None:
        return None
    actor, view = target.actor, ctx.world

    def cancel(now):
        if not target.current() or not view.companions.can_be_attacked(uid):
            raise ValueError('MAGIC_CANCEL_CURRENT_TARGET_REQUIRED')
        magic.restore(actor, now)
        state = magic.engine.state(actor.character_id)
        removed = tuple(sorted(state.buffs))
        state.buffs.clear()
        state.weapon_uids.clear()
        state.armor_uids.clear()
        for kind in ('counter_magic', 'meditation', 'berserk', 'water_life'):
            state.effects.pop(kind, None)
        state.invisible_until = 0.0
        actor.shield_until = 0
        bags = getattr(view.companion_ai, 'inventory', None)
        if bags is not None:
            bags.refresh(actor.character_id, publish=False)
        # With no inventory adapter, profile() computes current magic bonuses
        # from the preserved base profile on each actual swing.
        magic.save_buffs(actor.record, now)
        # The optional runtime notification wrapper logs save failures. A
        # committed hostile action must propagate the actual store failure.
        ctx._companion_save(actor.owner_ref.uid)
        return removed

    return cancel


METHODS += (_companion_npc_magic_target, _companion_cure_poison, _companion_magic_buff_target)
METHODS += (_companion_cancel_magic_target,)
HOOKS.update(npc_magic_target=('_companion_npc_magic_target',))
HOOKS.update(magic_buff_target=('_companion_magic_buff_target',))
HOOKS.update(cure_poison=('_companion_cure_poison',))
HOOKS.update(cancel_magic_target=('_companion_cancel_magic_target',))


def _companion_report(ctx, result):
    """Report-only: this feature's bounded request errors (0960/4F13/4F02)."""
    result['companion_errors'] = list(getattr(ctx, '_companion_errors', ())[-8:])
    result['companion_error_params'] = list(getattr(ctx, '_companion_error_params', ())[-8:])
    result['companion_untargeted_params'] = list(getattr(ctx, '_companion_untargeted_params', ())[-8:])


METHODS += (_companion_report,)
HOOKS.update(report=HOOKS.get('report', ()) + ('_companion_report',))
NONCRITICAL_HOOKS = ('report',)  # this module had no other noncritical hook


class CompanionParty:
    """Display projection only, using PARTY_COMPANION_EVIDENCE section 4.

    LOCAL wire policy: group name = owner's saved name, group f3/member f4/
    status f10 = 0, group kind f4 = 1; floor percentages, maxMP0 = 0%.
    These key values are not observed official-server values. Native 08A0
    appends rows (5548A0/9CCE60); 08A1 removes by member name/f12 key, using
    f2/f5 and group selector f7 (551230..5513AE/9CD960). Enum values 1..3
    are accepted (DEA870/DE5FAF); old LIST f4=0 left the typed default 1.
    08A3 HP/MP updates reach PlayerActorHud through 555800 -> party+260 ->
    996E10 -> 996F00/996F50 -> C1E820. Remote head MP visibility is separate:
    init 996275/993910 hides it and membership 9838D0 enables only head HP.
    Queued packets do not prove native rendering.
    Cache holds delivery projections, never a second HP/MP authority.
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self.sent = {}
        self.departing = set()
        # Removal can be queued immediately before leave_pc drops the outbox.
        # Keep its keys until next entry, where replay is harmless if delivered.
        self.retired = {}

    def depart(self, uid):
        self.departing.add(uid)

    def remove(self, uid, rows):
        remembered = self.retired.setdefault(uid, {})
        # Self removal clears the group/map entry and all eight native slots
        # (5512CF/5514C5/9CD9C8), so remove other members before the owner.
        for row in sorted(rows, key=lambda row: row[0] == uid):
            name = row[1]
            body = (pb.encode_bytes(2, name.encode('utf-8')) + pb.encode_uint32(5, 0)
                    + pb.encode_uint32(7, 1))
            self.ctx.world._queue(uid, self.frame(0x08a1, body))
            remembered[name] = row

    def reset(self, uid):
        rows = dict(self.retired.pop(uid, {}))
        rows.update((row[1], row) for row in self.sent.pop(uid, ()))
        self.remove(uid, rows.values())
        self.retired.pop(uid, None)
        self.departing.discard(uid)

    @staticmethod
    def percent(current, maximum):
        return max(0, min(100, 100 * current // maximum)) if maximum > 0 else 0

    @staticmethod
    def frame(opcode, body):
        return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'

    @staticmethod
    def member(row):
        _, name, ref, hp, mp = row[:5]
        return (pb.encode_bytes(1, name.encode('utf-8')) + pb.encode_uint32(3, ref.uid)
                + pb.encode_uint32(4, 0) + pb.encode_uint32(6, hp) + pb.encode_uint32(7, mp))

    @staticmethod
    def status(row):
        _, name, _, hp, mp = row[:5]
        return (pb.encode_bytes(1, name.encode('utf-8')) + pb.encode_uint32(3, hp)
                + pb.encode_uint32(4, mp) + pb.encode_uint32(10, 0))

    def sync(self, now=None):
        ctx, current = self.ctx, {}
        view = ctx.world
        for actor in view.companions.active.values():
            if actor.character_id not in ctx._companion_rows:
                continue  # shared follower service also owns ordinary pets
            owner = view.entities.get(actor.owner_ref.uid)
            # Death invalidates the living ref's generation, retaining the same
            # corpse UID. Its HP0 still belongs in the party projection.
            entity = view.entities.get(actor.ref.uid)
            state = view.combat.pcs.get(actor.owner_ref.uid)
            if (owner is None or entity is None or owner.uid not in view.pcs or state is None
                    or (owner.alive and owner.ref != actor.owner_ref)
                    or (actor.record.alive and entity.ref != actor.ref)):
                continue
            record = actor.record
            current.setdefault(owner.uid, []).append((record.character_id,
                ctx._companion_rows[record.character_id]['name'], actor.ref,
                self.percent(record.hp, record.effective_max_hp), self.percent(record.mp, record.effective_max_mp),
                (record.mp, record.effective_max_mp)))
        for uid in tuple(self.sent):
            if uid not in current and uid not in self.departing and uid in view.pcs:
                self.remove(uid, self.sent.pop(uid))
        for uid, members in current.items():
            if uid in self.departing:
                continue
            owner = view.entities.get(uid)
            state = view.combat.pcs[uid]
            rows = ((uid, ctx._companion_rows[uid]['name'], owner.ref,
                     self.percent(state.hp, state.max_hp), self.percent(state.mp, state.max_mp),
                     (state.mp, state.max_mp)),
                    *sorted(members, key=lambda row: row[0]))
            previous = self.sent.get(uid, ())
            # Native rows contain the UID, not our server reference generation.
            # LIST appends even an identical UID, so retire its previous rows
            # before sending a replacement. Generation changes need no LIST.
            identity = lambda values: tuple((row[0], row[1], row[2].uid) for row in values)
            changed = identity(rows) != identity(previous)
            if changed:
                self.remove(uid, previous)
                body = pb.encode_bytes(1, rows[0][1].encode('utf-8'))
                body += b''.join(pb.encode_bytes(2, self.member(row)) for row in rows)
                body += pb.encode_uint32(3, 0) + pb.encode_uint32(4, 1)
                view._queue(uid, self.frame(0x08a0, body))
            # Keep the last projected current/max MP as well as the wire percent.
            # Recovery, absorption and casting must publish even when integer
            # rounding leaves the same percent (e.g. 0 -> 3 of maxMP314).
            # The native party/head consumers both use status f4, not raw MP.
            updates = rows if changed else tuple(row for row, old in zip(rows, previous)
                                                 if row[3:] != old[3:])
            if updates:
                body = b''.join(pb.encode_bytes(1, self.status(row)) for row in updates)
                view._queue(uid, self.frame(0x08a3, body))
            self.sent[uid] = rows
