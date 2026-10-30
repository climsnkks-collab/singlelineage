"""Optional physical weapon effects, with explicit L1J backend policies.

Official details establish effect names, not Classic numeric parameters.
L1WeaponSkill.java:233-286,333-425,428-433,475-518 supplies the adopted
SQL (USE_INT_PROCS=false) and INT special-case policies. No player spell
cost, learned spell, optional feature method or private state is consumed.
"""
from __future__ import annotations

from dataclasses import replace
import math

from tools.local_original_session.world_npc_resources import (
    MANA_DRAIN_POLICY as POLICY, STAFF_OF_MANA, PER_HIT_CAP, mana_drain_roll)
OWNER = 'weapon_effects'
# (name, chance, damage multiplier, SQL fixed, SQL random, gfx, element, radius)
# 2072's random=0 gate produces zero damage, including SQL fixed=8.
PROCS = {
    1094: ('cone_of_cold', 25, None, 95, 55, 1810, 'water', 0),
    1096: ('eruption', 14, 1.8, 0, 0, 129, 'earth', 0),
    2072: ('moonlight_eruption', 10, None, 8, 0, None, 'none', 0),
    3019: ('cold_chaser', 5, 1.4, 0, 0, 1804, 'water', 3),
    3020: ('electric_shock', 4, 2., 0, 0, 10, 'wind', 0),
}
UNKNOWN = {
    789: 'official Fire Arrow exists; supplied L1J184 has no proc numeric producer',
    3018: 'official Turn Undead exists; L1J261 Disease identity conflict; '
          'weapon chance/success formula UNKNOWN',
}


def _speed_frame(uid, factors):
    """Established 4E5B move key0/attack key1, with independent totals.

    REA206/324 identify the two consumers. Reuse the existing interval-to-bonus
    conversion; no additional speed keys or NPC-specific values are inferred.
    """
    from tools.local_original_session import world_combat as combat
    move, attack = factors
    if move == attack:
        return combat.speed_frame(uid, attack)
    codec = combat.attack
    bonus = b''.join(codec.pb.encode_bytes(1, codec._field(1, key)
                        + codec._field(2, combat.speed_percent(factor)))
                    for key, factor in ((combat.SPEED_MOVE_KEY, move),
                                        (combat.SPEED_ATTACK_KEY, attack)))
    body = codec._field(1, uid) + codec.pb.encode_bytes(2, bonus)
    return ((len(body) + 6).to_bytes(2, 'little')
            + combat.SPEED_OPCODE.to_bytes(2, 'little') + body + b'\0\0')


def _world_weapon_bow_ammunition(ctx, value, uid, weapon, stacks, target, now):
    """Read-only proposal; the combat feature remains the sole cost writer.

    L1J190/205 SQL range=-1; reuse the ordinary bow's ammo selection without
    changing world_ammo's default catalog. Sayha alone allows no-arrow shots.
    """
    if weapon.template_id not in (568, 2072):
        return value
    from tools.local_original_session import world_ammo
    pc = ctx.world.entities.get(uid)
    if pc is None:
        return value
    proposal = world_ammo.prepare_attack(replace(weapon, template_id=11), stacks,
        attacker=(pc.map_id, pc.x, pc.y), target=(target.map_id, target.x, target.y),
        items=ctx.world.data.items)
    if weapon.template_id == 568 and proposal.reason == 'NO_ARROW':
        return replace(proposal, allowed=True, reason=None,
            arrow=world_ammo.ArrowDef(190, 'Sayha virtual arrow (LOCAL)', 15, 15))
    return proposal


def proc_damage(spec, intelligence, spellpower, rng, *, berserk=False):
    """L1J special cases or effective SQL path, before target reduction."""
    _, _, multiplier, fixed, random, *_ = spec
    if multiplier is None:
        return 0. if random <= 0 else fixed + rng.randint(1, random)
    n = max(intelligence, 18) + max(spellpower, 13)
    return n * (multiplier * 1.5 + (.2 if berserk else 0)) + rng.randint(0, n-1) * multiplier * 1.5


def reduce_proc_damage(amount, defense):
    """L1WeaponSkill:475-518; explicit baseline originalMagicHit=0."""
    if defense.get('immune', False):
        return 0
    mr = defense['mr']
    floor = math.floor((mr - defense.get('original_magic_hit', 0)) / (2 if mr <= 100 else 10))
    coefficient = (1 if mr <= 100 else .6) - .01 * floor
    return max(0, int(amount * coefficient * (1-defense.get('resistance', 0)/100)))


def _inputs(ctx, uid):
    """The mandatory core owns saved equipment, stats and selection."""
    state = ctx.world.combat.pcs.get(uid)
    if state is None:
        return None
    writer = next((writer for writer, selected in ctx._world_pcs.values() if selected == uid), None)
    if writer is None:
        return None
    calculated, worn, _ = ctx._world_stats_for(ctx.realm.service(writer).snapshot(), level=state.profile.level)
    weapon = next((row for row in worn if row.item.kind == 'weapon'), None)
    if weapon is None:
        return None
    # Equipment SP is an established item property; active spell SP/berserk and
    # original magic hit require a contributor, never a magic-private lookup.
    import json
    item_sp = 0
    for row in worn:
        note = row.item.sources.get('weapon' if row.item.kind == 'weapon' else 'ac')
        if note is not None:
            try:
                options = json.loads(note.note).get('official_options', ())
            except (ValueError, TypeError):
                options = ()
            item_sp += sum(int(option.get('origin', '0')) for option in options if option.get('name') == 'SP')
    value = dict(template=weapon.item.template_id, enchant=weapon.enchant,
                 intelligence=calculated.attributes.intelligence, spellpower=item_sp,
                 berserk=False, original_magic_hit=0)
    return ctx.fold_sync_hooks('weapon_proc_attacker', value, uid, ctx.world.runtime.clock())


def _world_weapon_effects_initialize(ctx):
    from tools.local_original_session import world_npc_resources
    from tools.local_original_session.world_combat import (
        status_frame, attack_frame, elemental_weakness_multiplier)
    from tools.local_original_session.world_status_frames import effect_frame
    from tools.local_original_session.world_entities import Kind

    world = ctx.world
    resources = world_npc_resources.install(world)
    ctx._world_weapon_effects_events = []
    ctx._world_weapon_effects_totals = dict(drain_count=0, total_drained=0, total_gained=0,
                                          proc_count=0, proc_damage=0)
    active, handles, speeds, npc_speeds = [], [], {}, {}

    def record(event):
        ctx._world_weapon_effects_events.append(event)
        del ctx._world_weapon_effects_events[:-64]

    def companion_hit(actor, target, monster, swing):
        """Consume only an admitted basic hit and the member's actual worn row.

        The follower runtime publishes this event before normal HP/death work;
        this feature owns the optional effect. Pets never inherit PC weapons.
        """
        if '_pet' in actor.record.equipment or not swing.landed:
            return
        bags = getattr(world.combat, 'companion_inventory', None)
        if bags is None:
            return
        _, worn = bags.calculated(actor.character_id)
        weapon = next((row for row in worn if row.item.kind == 'weapon'), None)
        if weapon is None or weapon.item.template_id != STAFF_OF_MANA:
            return
        rolled = mana_drain_roll(weapon.enchant, world.combat.rng)
        npc_before = resources.mana_of(target.ref, monster.mp)
        drained = resources.drain_mana(target.ref, monster.mp, rolled)
        member, before = actor.record, actor.record.mp
        member.mp = min(member.effective_max_mp, before + drained)
        if member.mp != before:
            # Existing absolute snapshot/party projection own save and wire.
            # Preserve failed-save pending state; never retry the physical hit.
            world._save_companion(actor.owner_ref.uid)
        totals = ctx._world_weapon_effects_totals
        totals['drain_count'] += int(drained > 0)
        totals['total_drained'] += drained
        totals['total_gained'] += member.mp - before
        record(dict(companion_uid=actor.ref.uid, member_character_id=actor.character_id,
            owner_uid=actor.owner_ref.uid, npc_uid=target.uid, weapon_template=STAFF_OF_MANA,
            effect='mana_drain', policy=POLICY, rolled=rolled, drained=drained,
            mp_before=before, mp_after=member.mp, npc_mp_before=npc_before,
            npc_mp_after=npc_before-drained, at=world.runtime.clock()))

    def attack(base):
        def call(pc_uid, target_uid):
            pc, target = world.entities.get(pc_uid), world.entities.get(target_uid)
            active.append(None if pc is None or target is None else (pc.ref, target.ref))
            try:
                return base(pc_uid, target_uid)
            finally:
                active.pop()
        return call

    def apply(base):
        def call(owner_uid, attacker_uid, target, monster, hp, swing, now):
            pc = world.entities.get(attacker_uid)
            state = world.combat.pcs.get(attacker_uid)
            eligible = (active and pc is not None and active[-1] == (pc.ref, target.ref)
                        and owner_uid == attacker_uid and state is not None and not state.dead
                        and state.hp > 0 and swing.landed)
            inputs = _inputs(ctx, attacker_uid) if eligible else None
            if inputs is None:
                return base(owner_uid, attacker_uid, target, monster, hp, swing, now)
            template = inputs['template']
            if template == STAFF_OF_MANA and state.mp is not None and state.max_mp is not None:
                rolled = mana_drain_roll(inputs['enchant'], world.combat.rng)
                npc_before = resources.mana_of(target.ref, monster.mp)
                drained = resources.drain_mana(target.ref, monster.mp, rolled)
                before = state.mp
                state.status_fields[12] = min(state.max_mp, before + drained)
                if state.mp != before:
                    world._queue(attacker_uid, status_frame(state.status_fields, state.hp))
                totals = ctx._world_weapon_effects_totals
                totals['drain_count'] += int(drained > 0)
                totals['total_drained'] += drained
                totals['total_gained'] += state.mp - before
                record(dict(pc_uid=attacker_uid, npc_uid=target.uid, weapon_template=template,
                    effect='mana_drain', policy=POLICY, rolled=rolled, drained=drained,
                    mp_before=before, mp_after=state.mp, npc_mp_before=npc_before,
                    npc_mp_after=npc_before-drained, at=now))
            spec = PROCS.get(template)
            if swing.damage <= 0 or spec is None or world.combat.rng.randint(1, 100) > spec[1]:
                return base(owner_uid, attacker_uid, target, monster, hp, swing, now)
            amount = proc_damage(spec, inputs['intelligence'], inputs['spellpower'],
                                 world.combat.rng, berserk=inputs['berserk'])
            victims = [(target.ref, monster, hp)]
            if spec[7]:
                for entity in tuple(world.entities):
                    if (entity.uid == target.uid or not entity.alive or entity.map_id != target.map_id
                            or max(abs(entity.x-target.x), abs(entity.y-target.y)) > spec[7]):
                        continue
                    found = world.spawner.slot_for(entity.uid)
                    if found is not None and found[0].active and found[1].hp > 0:
                        victims.append((entity.ref, found[0].monster, found[1].hp))
            if spec[5] is not None:
                wire = effect_frame(target.uid, spec[5])
                for watcher in world._watchers(target):
                    world._queue(watcher, wire)
            if template == 2072:
                # L1WeaponSkill ArrowType uses S_UseAttackSkill, not SkillSound.
                # gfx6288 in Classic's f7 remains an explicit LOCAL presentation.
                for watcher in world._watchers(target):
                    world._queue(watcher, attack_frame(attacker_uid, target.uid,
                        raw_effect=1, direction=8, self_action=watcher == attacker_uid,
                        ranged=True, arrow_id=world.arrow_id, arrow_mode=world.arrow_mode,
                        projectile=6288))
            damage = 0
            for ref, definition, current_hp in victims:
                current = world.entities.resolve(ref)
                if current is None or not current.alive:
                    continue
                defense = ctx.fold_sync_hooks('weapon_proc_defense', dict(mr=definition.mr,
                    resistance=0, immune=False, original_magic_hit=inputs['original_magic_hit']),
                    attacker_uid, ref, spec[6], now)
                # LOCAL adaptation: reuse general PC->NPC spell weakness for
                # sourced weapon magic, before the existing proc MR/resistance
                # product and its single final int truncation. Physical damage
                # and proc chance/dice remain unchanged; no -50 enchant policy.
                element = {'earth': 1, 'fire': 2, 'water': 4, 'wind': 8}.get(spec[6], 0)
                dealt = reduce_proc_damage(amount * elemental_weakness_multiplier(
                    element, definition.weak_attr), defense)
                damage += dealt
                if ref == target.ref:
                    swing = replace(swing, damage=swing.damage+dealt)
                elif dealt > 0:
                    # Call the preceding core consumer, avoiding recursive procs;
                    # kill/reward/HP/AI/cleanup remain owned by the normal path.
                    base(owner_uid, attacker_uid, current, definition, current_hp,
                         replace(swing, damage=dealt), now)
            totals = ctx._world_weapon_effects_totals
            totals['proc_count'] += 1
            totals['proc_damage'] += damage
            record(dict(pc_uid=attacker_uid, npc_uid=target.uid, weapon_template=template,
                effect=spec[0], policy=('local_policy:L1J_WEAPON_PROCS_SQL' if spec[2] is None
                                       else 'local_policy:L1J_WEAPON_PROCS_INT'), rolled=amount,
                damage=damage, damage_scope='post_defense_pre_hp_clamp_including_overkill',
                victim_count=len(victims), at=now,
                presentation='LOCAL_4E31_ARROW6288' if template == 2072 else 'LOCAL_4ED8_TARGET'))
            return base(owner_uid, attacker_uid, target, monster, hp, swing, now)
        return call

    def haste(factor, uid, now):
        value = _inputs(ctx, uid)
        # Current magic has slow/berserk, but no haste producer. Its existing
        # separate wrapper multiplies this category and brave exactly once.
        return min(factor, world.data.items[17].buff.rate) if (
            value is not None and value['template'] == 144) else factor

    def projectile(value, uid, target_uid, prepared, now):
        inputs = _inputs(ctx, uid)
        return 2349 if (inputs is not None and inputs['template'] == 568
                        and prepared is not None and prepared.arrow is not None
                        and prepared.cost is None) else value

    def speed_factors(uid, now):
        factor = world.combat.speed_factor(uid, now)
        return ctx.fold_sync_hooks('speed_factors', (factor, factor), uid, now)

    def npc_speed_factors(entity, now):
        # The same public reader drives the AI's move/attack intervals, including
        # slow/berserk. The monster owner contributes its separate haste factor
        # through the runtime fold rather than exposing another feature's state.
        reader = getattr(world, 'magic_status', None)
        status = {} if reader is None else reader(entity.uid, now)
        factors = status.get('move_factor', 1.), status.get('attack_factor', 1.)
        return world.events.fold('npc_speed_factors', factors, entity.ref, now)

    def publish_npc_speed(ref, now):
        entity = world.entities.resolve(ref)
        if (world.closed or entity is None or not entity.alive or entity.kind is not Kind.NPC
                or world.spawner.slot_for(entity.uid) is None):
            npc_speeds.pop(ref, None)
            return
        factors = npc_speed_factors(entity, now)
        if npc_speeds.get(ref, (1., 1.)) != factors:
            wire = _speed_frame(entity.uid, factors)
            for watcher in world._watchers(entity):
                world._queue(watcher, wire)
        npc_speeds[ref] = factors

    def apply_buff(base):
        def call(uid, buff, now):
            result = base(uid, buff, now)
            if result is None:
                return None
            expires, _ = result
            return expires, _speed_frame(uid, speed_factors(uid, now))
        return call

    def expire_buff(base):
        def call(uid, kind, now):
            wire = base(uid, kind, now)
            return None if wire is None else _speed_frame(uid, speed_factors(uid, now))
        return call

    def refresh_pcs(base):
        def call(uid):
            known = set(world.pc_known.get(uid, ()))
            frames = base(uid)
            # The core replays the symmetric attack total for a newly visible
            # PC. Follow it with the authoritative split total when necessary,
            # including movement-only states whose attack total remains 1.
            for peer in sorted(world.pc_known.get(uid, set()) - known):
                if peer in world.combat.pcs:
                    factors = speed_factors(peer, world.runtime.clock())
                    if factors[0] != factors[1]:
                        frames.append(_speed_frame(peer, factors))
            return frames
        return call

    def refresh(base):
        def call(uid):
            known = set(world.visibility.known.get(uid, ()))
            frames = base(uid)
            # Actor initialization supplies default keys0..3 (REA206). Replay
            # the currently composed LOCAL cadence only after its spawn frame.
            for npc_uid in sorted(world.visibility.known.get(uid, set()) - known):
                entity = world.entities.get(npc_uid)
                if (entity is not None and entity.alive and entity.kind is Kind.NPC
                        and world.spawner.slot_for(npc_uid) is not None):
                    factors = npc_speed_factors(entity, world.runtime.clock())
                    if factors != (1., 1.):
                        frames.append(_speed_frame(npc_uid, factors))
            return frames
        return call

    def publish_speeds(*_):
        now = world.runtime.clock()
        for uid in tuple(world.combat.pcs):
            factors = speed_factors(uid, now)
            if speeds.get(uid, (1., 1.)) != factors:
                wire = _speed_frame(uid, factors)
                world._queue(uid, wire)
                world.broadcast_pc_effects(uid, (wire,))
            speeds[uid] = factors
        for uid in tuple(speeds):
            if uid not in world.combat.pcs:
                del speeds[uid]
        current = set()
        for entity in world.entities:
            if entity.kind is Kind.NPC and entity.alive and world.spawner.slot_for(entity.uid) is not None:
                current.add(entity.ref)
                publish_npc_speed(entity.ref, now)
        for ref in tuple(npc_speeds):
            if ref not in current:
                del npc_speeds[ref]

    handles.append(world.runtime_extensions.wrap(OWNER, world, 'pc_attack', attack))
    handles.append(world.runtime_extensions.wrap(OWNER, world, '_apply_monster_swing', apply))
    handles.append(world.runtime_extensions.wrap(OWNER, world.combat, 'apply_buff', apply_buff))
    handles.append(world.runtime_extensions.wrap(OWNER, world.combat, 'expire_buff', expire_buff))
    handles.append(world.runtime_extensions.wrap(OWNER, world, '_refresh_pcs', refresh_pcs))
    handles.append(world.runtime_extensions.wrap(OWNER, world, '_refresh', refresh))
    world.combat.haste_modifiers.append(haste)
    world.combat.projectile_modifiers.append(projectile)
    companion_entry = world.events.add(OWNER, 'companion_weapon_hit', companion_hit)
    tick_entry = world.events.add(OWNER, 'tick', publish_speeds)
    leave_entry = world.events.add(OWNER, 'before_pc_leave', lambda uid: speeds.pop(uid, None))
    npc_speed_entry = world.events.add(OWNER, 'npc_speed_changed', publish_npc_speed)

    def close():
        world.events.remove('close', close_entry)
        world.events.remove('companion_weapon_hit', companion_entry)
        world.events.remove('tick', tick_entry)
        world.events.remove('before_pc_leave', leave_entry)
        world.events.remove('npc_speed_changed', npc_speed_entry)
        if haste in world.combat.haste_modifiers:
            world.combat.haste_modifiers.remove(haste)
        if projectile in world.combat.projectile_modifiers:
            world.combat.projectile_modifiers.remove(projectile)
        for handle in reversed(handles):
            handle.close()
        active.clear()
        speeds.clear()
        npc_speeds.clear()
    close_entry = world.events.add(OWNER, 'close', close)


def _world_weapon_effects_report(ctx, result):
    result['weapon_effects'] = dict(policy=POLICY,
        **ctx._world_weapon_effects_totals, events=list(ctx._world_weapon_effects_events),
        unknown=dict(UNKNOWN), missing_contributors=[name for name in
            ('weapon_proc_attacker', 'weapon_proc_defense') if not ctx.has_hooks(name)])


METHODS = (_world_weapon_effects_initialize, _world_weapon_effects_report, _world_weapon_bow_ammunition)
HOOKS = {'initialize': ('_world_weapon_effects_initialize',),
         'report': ('_world_weapon_effects_report',),
         'bow_ammunition': ('_world_weapon_bow_ammunition',)}
NONCRITICAL_HOOKS = ('report',)
