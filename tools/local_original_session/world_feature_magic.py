"""M3 player books, MP spells and real-clock effects on the existing world lane.

4EE6/4E60 and raw0 0960 are retained contracts. No unknown success ACK,
delay-clock unit or projectile parameter is invented. Default cast display uses
the user-adopted L1J content table with fixed-client inventory checks. HUD keys use the fixed-client
CommonSpell/received-f4 namespace and existing effect deadlines.
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import struct

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import world_magic, world_npc_resources
from tools.local_original_session import world_magic_status as magic_status
from tools.local_original_session.world_bridge import need

CAST, AVAILABLE = 0x4ee6, 0x4e60
HOSTILE_STATUS = frozenset(('blind', 'weapon_break', 'slow', 'paralyze', 'darkness',
                            'stun', 'entangle', 'erase_magic'))
HOSTILE = HOSTILE_STATUS | {'turn_undead', 'mana_drain'}

# Content only: protocol comes from REA399/401, not the L1J packet classes.
# Keep file I/O out of the cast path; each row retains its SQL line and actual
# fixed-client SPR/file alias + catalog existence evidence.
SPELL_DISPLAY = {row['key']: row for row in json.loads(
    (Path(__file__).parent / 'data/m1/spell_display.json').read_text(encoding='utf-8'))['spells']}

# CommonSpell.f3 -> received BuffIconInfo.f4 comparison: RVA44378C..443797,
# 443889..443890; f4 -> row+10: 462BD3..462BE6/46024C..46024F.
# Positive f4 -> K: 462D20..462D2C. Exact dump/atlas rows are recorded in
# BUFF_GAMETIME_EVIDENCE.md, "마법 HUD 기본 송신". No unknown/transient K.
SPELL_BUFF_ICONS = {
    2: 485, 7: 777, 10: 5319, 11: 5265, 13: 757, 19: 5318,
    20: 5316, 25: 483, 28: 480, 30: 748, 31: 795, 32: 5270,
    39: 751, 86: 1626, 87: 1889, 88: 1883, 89: 20161, 90: 20479, 128: 813, 136: 745,
    137: 804, 147: 774, 148: 855, 150: 763, 151: 766, 152: 1834,
    162: 738, 165: 827, 167: 783, 169: 1758,
}


def _frame(opcode, body):
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def available_frame(keys):
    return _frame(AVAILABLE, b''.join(pb.encode_bytes(1,
        pb.encode_uint32(1, key) + pb.encode_uint32(2, 1)) for key in sorted(keys)))


def buff_icon_frame(key, instance, remaining, *, remove=False):
    """4E91 with explicit catalog and fixed-client image/row K, not a UID."""
    from tools.local_original_session.world_item_effects import buff_icon_frame as encode_icon
    return encode_icon(key, instance, remaining, remove=remove)


def invisible_frame(uid, active):
    """4F04 required uint64 actor UID / int32 positive predicate.

    Fixed-client schemas.json and function-516c0.txt in
    runs/status-feedback-contract-20261030: f2 > 0 sets component+44;
    nonpositive clears it, then 9FB20/62180 refresh the current actor.
    1/0 select those proven branches; original server issuance is unobserved.
    """
    return _frame(0x4f04, pb.encode_varint(1 << 3) + pb.encode_varint(uid)
                  + pb.encode_uint32(2, int(active)))


def paralyse_frame(key, active):
    """115850/C19B0/C1CC0: even inserts key, paired odd deletes that key.

    key0 changes the common action gate; key2 also sets/clears Stone bit8.
    These are exact consumer effects, not original-server spell enum labels.
    """
    return _frame(0x4eeb, pb.encode_uint32(1, key if active else key + 1))


def blind_frame(active):
    """116B40 +890 -> B9D90 lighting mode1 / original mode0 restoration."""
    return _frame(0x4f03, pb.encode_uint32(1, int(active)))


def poison_frame(uid, poisoned, stone):
    """518D0: required f2/f3 independently replace Poison/Stone visual bits.

    9BE080 selects Common_Hp_Bar[_Head]_Poison/Stone assets. Always publish
    both current truths, including after 4EEB key2 changes the same Stone bit.
    """
    return _frame(0x4f05, pb.encode_varint(1 << 3) + pb.encode_varint(uid)
                  + pb.encode_bool(2, bool(poisoned)) + pb.encode_bool(3, bool(stone)))


def decode_cast(payload):
    """Retained UseSpellParam target is signed int32, coordinates are raw DWORDs.

    Coordinates are client-local metadata; entity/map/range come from the world.
    Other optional fields have no player-M3 consumer, so refuse their use.
    """
    with pb.parse_message(payload, limits=pb.WireLimits(
            max_body=4096, max_fields=2, max_field_bytes=2048)) as message:
        keys, params = message.occurrences(1), message.occurrences(2)
        need(len(keys) == 1 and keys[0].wire_type == 0
             and 0 <= keys[0].value <= 0xffffffff and len(params) <= 1
             and len(message.fields) == 1 + len(params)
             and all(p.wire_type == 2 for p in params), 'MAGIC_CAST_PARENT_FIELDS')
        key, target = keys[0].value, None
        if params:
            with pb.parse_message(bytes(params[0].value), limits=pb.WireLimits(
                    max_body=2048, max_fields=3, max_field_bytes=1024)) as child:
                need(all(f.number in (1, 3, 4) and f.wire_type == 0 for f in child.fields)
                     and all(len(child.occurrences(n)) <= 1 for n in (1, 3, 4)),
                     'MAGIC_CAST_PARAM_FIELDS')
                for field in child.fields:
                    if field.number == 1:
                        value = field.value
                        need(0 <= value <= 0xffffffff or (1 << 64) - (1 << 31) <= value < (1 << 64),
                             'MAGIC_TARGET_INT32_REQUIRED')
                        target = value & 0xffffffff
                    else:
                        need(0 <= field.value <= 0xffffffff, 'MAGIC_COORDINATE_UINT32_REQUIRED')
        return key, target


def decode_book(payload):
    with pb.parse_message(payload, limits=pb.WireLimits(
            max_body=4096, max_fields=2, max_field_bytes=2048)) as message:
        ids, params = message.occurrences(1), message.occurrences(2)
        need(len(message.fields) == 2 and len(ids) == len(params) == 1
             and ids[0].wire_type == 0 and params[0].wire_type == 2,
             'MAGIC_BOOK_PARENT_FIELDS')
        identifier = ids[0].value
        with pb.parse_message(bytes(params[0].value), limits=pb.WireLimits(
                max_body=2048, max_fields=3, max_field_bytes=1024)) as child:
            expected = {1: 1, 15: 0, 16: 0}
            need(len(child.fields) == 3 and all(len(child.occurrences(n)) == 1 for n in expected)
                 and all(f.wire_type == 0 and f.value == expected.get(f.number)
                         for f in child.fields), 'MAGIC_BOOK_RAW0_PARAMS_REQUIRED')
        return identifier


def _world_magic_initialize(ctx):
    from tools.local_original_session import inventory
    from tools.local_original_session.game_data import load_npc_spells
    override = os.environ.get('SL_PLAYER_MAGIC_BUFF_SECONDS')
    need(override in (None, '10'), 'MAGIC_TEST_DURATION_10_SECONDS_ONLY')
    policies = (ctx.fold_sync_hooks('magic_runtime_policies', {})
                if hasattr(ctx, 'fold_sync_hooks') else {})
    ctx._world_magic = world_magic.PlayerMagic(world_magic.load_catalog(),
        buff_seconds=None if override is None else 10, runtime_policies=policies)
    ctx._world_magic_store = None
    ctx._world_magic_writers = {}
    ctx._world_magic_errors = []
    ctx._world_magic_events = []
    ctx._world_magic_npc_spells = load_npc_spells()
    ctx._world_magic_buff_ui = os.environ.get('SL_PLAYER_MAGIC_BUFF_UI') != '0'
    ctx._world_magic_icons = {}
    ctx._world_magic_feedback = {}
    _world_magic_consumers(ctx)
    # Server lighting consumer: a lit actor is present only until its real
    # deadline. Native light-level publication remains unverified.
    ctx.world.light_sources = {}
    if (getattr(ctx, '_inventory_store', None) is not None
            and getattr(ctx, '_inventory_kit_policy', None) == inventory.KIT_POLICY):
        ctx._world_magic_store = world_magic.MagicStore(ctx.inventory_store,
            replace_kit=ctx._world_replace_kit)


def _world_magic_started(ctx):
    # Existing packet fixtures, like production starter setup, may bind the
    # ordinary kit store after broker construction but before runtime.start().
    from tools.local_original_session import inventory
    if (ctx._world_magic_store is None and getattr(ctx, '_inventory_store', None) is not None
            and getattr(ctx, '_inventory_kit_policy', None) == inventory.KIT_POLICY):
        ctx._world_magic_store = world_magic.MagicStore(ctx.inventory_store,
            replace_kit=ctx._world_replace_kit)
    _world_magic_consumers(ctx)
    ctx.world.runtime.add_tick_hook(ctx._world_magic_tick)
    # A companion may have registered before this late-bound store was ready.
    if ctx._world_magic_store is not None:
        for uid in ctx._world_magic_store.rows.keys() | ctx._world_magic.states.keys():
            ctx.run_sync_hooks('magic_learning_changed', uid)


def _world_magic_learned_spells(ctx, uid):
    """Read-only character learning authority, including never-selected members.

    Do not restore an offline character's timed effects just to list spells.
    In-process state follows committed learning; cold rows come from MagicStore.
    """
    state = ctx._world_magic.states.get(uid)
    if state is not None:
        return frozenset(state.learned)
    store = ctx._world_magic_store
    row = None if store is None else store.rows.get(uid)
    return frozenset(() if row is None else row['learned'])


def _world_magic_consumable_provider(ctx):
    magic = getattr(ctx, '_world_magic', None)
    if magic is None:
        return None
    store = ctx._world_magic_store

    def save(uid, now):
        if store is not None and uid in magic.states:
            store.save(magic.snapshot(uid, now))

    return magic, save


def _world_magic_service(ctx):
    return world_magic.MagicService(ctx._world_magic, ctx._world_magic_save,
                                   ctx._world_magic_sync_icons, ctx._world_magic_buff_target)


def _world_magic_buff_target(ctx, uid, key, source_uid):
    """Current-PC buff recipient; caller owns admission, cost, reuse/display.

    Source is a durable character UID, distinct from a companion actor UID.
    LOCAL policy treats pledge targets as other PCs/companions without a clan.
    """
    view, engine = ctx.world, ctx._world_magic
    entity = view.entities.get(uid)
    spell = engine.spells.get(key)
    if uid not in view.combat.pcs:
        return next((target for target in ctx.collect_sync_hooks(
            'magic_buff_target', uid, key, source_uid) if target is not None), None)
    if (entity is None or not entity.alive or not view.combat.can_be_attacked(uid)
            or spell is None or spell.kind not in world_magic.BUFF_KINDS or spell.duration <= 0):
        return None
    if source_uid != uid and not world_magic.allows_received_buff(spell):
        return None
    weapon = ctx._world_magic_weapon_uid(uid) if spell.kind in ('weapon_hit', 'weapon_damage') else 0
    armor = ctx._world_magic_armor_uid(uid) if spell.kind == 'armor' else 0
    if spell.kind in ('weapon_hit', 'weapon_damage') and not weapon or spell.kind == 'armor' and not armor:
        return None
    ref = entity.ref

    def apply(now):
        need(view.entities.resolve(ref) is entity and entity.alive and view.combat.can_be_attacked(uid),
             'MAGIC_CURRENT_BUFF_TARGET_REQUIRED')
        engine.apply_buff(uid, spell, now, weapon_uid=weapon, armor_uid=armor,
                          source_uid=source_uid)
        ctx._world_recalculate_uid(uid)
        ctx._world_magic_save(uid)
        ctx._world_magic_sync_icons(uid, now)
        pc = view.combat.pcs[uid]
        from tools.local_original_session.world_combat import status_frame
        view._queue(uid, status_frame(pc.status_fields, pc.hp))
        view._announce()

    return world_magic.MagicBuffTarget(engine.state(uid), weapon, armor, apply, spell.duration)


def _world_magic_cancel_target(ctx, uid):
    """Registered LOCAL buff-only Cancel; caller owns admission/cost/display.

    Return a lifetime-bound callable(now), or None. Poison, hostile effects,
    physical weapon damage, learning, reuse and other features' effects survive.
    This deliberately implements less than L1J's full CANCELLATION policy.
    """
    view = ctx.world
    entity = view.entities.get(uid)
    if (entity is None or not entity.alive or uid not in view.combat.pcs
            or not view.combat.can_be_attacked(uid)):
        return None
    ref = entity.ref

    def cancel(now):
        need(view.entities.resolve(ref) is entity and entity.alive and view.combat.can_be_attacked(uid),
             'MAGIC_CANCEL_CURRENT_TARGET_REQUIRED')
        state = ctx._world_magic.state(uid)
        removed = tuple(sorted(state.buffs))
        state.buffs.clear()
        state.weapon_uids.clear()
        state.armor_uids.clear()
        state.buff_sources.clear()
        for kind in ('counter_magic', 'meditation', 'berserk', 'water_life'):
            state.effects.pop(kind, None)
        state.invisible_until = 0.0
        view.light_sources.pop(uid, None)
        ctx._world_recalculate_uid(uid)
        ctx._world_magic_save(uid)
        ctx._world_magic_sync_icons(uid, now)
        ctx._world_magic_sync_invisible(uid, now)
        from tools.local_original_session.world_combat import status_frame
        pc = view.combat.pcs[uid]
        view._queue(uid, status_frame(pc.status_fields, pc.hp))
        view._announce()
        return removed

    return cancel


def _world_magic_consumers(ctx):
    """Optional instance adapters; retain and restore the actual bound owners.

    Nothing is installed on a class or required by a feature-free world. The
    NPC AI has one optional read-only callback; resource owners stay unchanged.
    """
    if getattr(ctx, '_world_magic_adapters', None):
        return
    view, engine = ctx.world, ctx._world_magic
    ctx._world_magic_npc_resources = world_npc_resources.install(view)
    installed = ctx._world_magic_adapters = []
    # Other producers own status mutation/save; this feature owns its HUD rows.
    ctx._world_magic_status_event = view.events.add('magic', 'magic_status_changed',
        lambda uid, now: ctx._world_magic_sync_icons(uid, now))
    ctx._world_magic_invisible = getattr(ctx, '_world_magic_invisible', {})
    ctx._world_magic_feedback = getattr(ctx, '_world_magic_feedback', {})

    def install(owner, name, wrapper):
        if hasattr(owner, name):
            installed.append(view.runtime_extensions.wrap('magic', owner, name, wrapper))

    def current_effects(uid, now):
        if uid in engine.states:
            return engine.states[uid].effects
        row = engine.npc_statuses.get(uid)
        target = None if row is None else view.entities.resolve(row['ref'])
        if target is None or not target.alive:
            return {}
        return row['effects']

    ctx._world_magic_profile_modifier = ctx._world_magic_combat_profile
    view.combat.profile_modifiers.append(ctx._world_magic_profile_modifier)
    installed.append(view.runtime_extensions.wrap('magic', view, 'magic_status',
        lambda previous: lambda uid, now: magic_status.ai_status(current_effects(uid, now), now)))

    def ready(base):
        return lambda uid, now: (not magic_status.ai_status(current_effects(uid, now), now)['blocked'] and base(uid, now))
    install(view.combat, 'pc_swing_ready', ready)

    def player_swing(base):
        def call(uid, monster, now, *, arrow=None):
            swing = base(uid, monster, now, arrow=arrow)
            effect = engine.status(uid, 'weapon_break', now)
            if (swing is not None and effect is not None and effect['params'].get('weapon_uid')
                    == ctx._world_magic_weapon_uid(uid)):
                swing = replace(swing, damage=int(swing.damage * effect['params'].get('damage_multiplier', .5)))
            return swing
        return call
    install(view.combat, 'try_pc_swing', player_swing)

    def speed(base):
        return lambda uid, now: base(uid, now) * magic_status.ai_status(
            current_effects(uid, now), now)['attack_factor']
    install(view.combat, 'speed_factor', speed)

    def activity(base):
        def call(uid, points):
            now = view.runtime.clock()
            effects = current_effects(uid, now)
            if effects.pop('meditation', None) is not None:
                ctx._world_magic_save(uid)
                ctx._world_magic_sync_icons(uid, now)
            return base(uid, points)
        return call
    install(view.combat, 'note_activity', activity)

    def pc_attack(base):
        def call(uid, target_uid):
            now = view.runtime.clock()
            status = magic_status.ai_status(current_effects(uid, now), now)
            caster, target = view.entities.get(uid), view.entities.get(target_uid)
            if (status['blocked'] or status['sight'] is not None and caster is not None
                    and target is not None and max(abs(caster.x - target.x),
                                                   abs(caster.y - target.y)) > status['sight']):
                return view.drain(uid)
            # Ordinary swings set regen_state directly, so end meditation here.
            effects = current_effects(uid, now)
            if effects.pop('meditation', None) is not None:
                ctx._world_magic_save(uid)
                ctx._world_magic_sync_icons(uid, now)
            return base(uid, target_uid)
        return call
    install(view, 'pc_attack', pc_attack)

    def npc_attack(base):
        def call(entity, monster, target_uid, now):
            # This context exists only during the synchronous authoritative swing.
            previous = getattr(engine, '_attacking_npc', None)
            engine._attacking_npc = entity.ref
            try:
                return base(entity, monster, target_uid, now)
            finally:
                engine._attacking_npc = previous
        return call
    install(view, 'npc_attack', npc_attack)

    def npc_swing(base):
        def call(monster, uid):
            from tools.local_original_session import world_combat
            ref = getattr(engine, '_attacking_npc', None)
            selected = ctx._world_magic_npc_swing(monster, uid, ref, view.runtime.clock())
            if selected is not None:
                return selected
            row = None if ref is None else engine.npc_statuses.get(ref.uid)
            effect = (None if row is None or row['ref'] != ref else
                      magic_status.active(row['effects'], 'weapon_break', view.runtime.clock()))
            state = view.combat.pcs[uid]
            reduction = engine.reduction(uid, state.profile.level, view.runtime.clock())
            physical = view.events.first('npc_physical_swing', monster, uid, ref,
                                         view.runtime.clock())
            if physical is None and effect is None and not reduction:
                return base(monster, uid)
            swing = (physical if physical is not None else
                     world_combat.npc_hits_pc(monster, state.profile, view.combat.rng))
            damage = (swing.damage if effect is None else
                      int(swing.damage * effect['params'].get('damage_multiplier', .5)))
            swing = replace(swing, damage=max(0, damage - reduction))
            if not swing.landed or swing.damage <= 0:
                return swing, None
            state.hp = max(0, state.hp - swing.damage)
            state.dead = state.hp == 0
            return swing, world_combat.status_frame(state.status_fields, state.hp)
        return call
    install(view.combat, 'npc_swing', npc_swing)

    def reduced_magic(base):
        def call(monster, uid, attack):
            from tools.local_original_session import world_combat
            state = view.combat.pcs[uid]
            now = view.runtime.clock()
            reduction = engine.reduction(uid, state.profile.level, now)
            erased = engine.status(uid, 'erase_magic', now) is not None
            if not reduction and not erased:
                return base(monster, uid, attack)
            # Consume one real incoming magic attempt using the same HP owner.
            profile = replace(state.profile, mr=engine.effective_mr(uid, state.profile.mr, now))
            swing = world_combat.npc_hits_pc(monster, profile, view.combat.rng, magic=attack)
            if engine.consume_erase(uid, now):
                ctx._world_magic_save(uid)
                ctx._world_magic_sync_icons(uid, now)
            swing = replace(swing, damage=max(0, swing.damage - reduction))
            if not swing.landed or not swing.damage:
                return swing, None
            state.hp = max(0, state.hp - swing.damage)
            state.dead = state.hp == 0
            return swing, world_combat.status_frame(state.status_fields, state.hp)
        return call
    install(view.combat, 'npc_magic_swing', reduced_magic)

    def npc_companion(base):
        def call(monster, uid, profile, now):
            from tools.local_original_session import world_combat
            ref = getattr(engine, '_attacking_npc', None)
            selected = ctx._world_magic_npc_swing(monster, uid, ref, now)
            if selected is not None:
                return selected[0]
            row = None if ref is None else engine.npc_statuses.get(ref.uid)
            effect = (None if row is None or row['ref'] != ref else
                      magic_status.active(row['effects'], 'weapon_break', now))
            if effect is None:
                return base(monster, uid, profile, now)
            manager = view.combat.companions
            if manager is None or not manager.can_be_attacked(uid):
                return None
            actor = manager.get_actor(uid)
            if actor is None or not view.combat.can_be_attacked(actor.owner_ref.uid):
                return None
            if actor.shield_until > now:
                profile = replace(profile, ac=profile.ac - 2)
            swing = world_combat.npc_hits_pc(monster, profile, view.combat.rng)
            swing = replace(swing, damage=int(swing.damage * effect['params'].get('damage_multiplier', .5)))
            if swing.landed and swing.damage > 0:
                actor.record.hp = max(0, actor.record.hp - swing.damage)
                if actor.record.hp == 0:
                    manager.die(actor.record.character_id, now)
            return swing
        return call
    install(view.combat, 'npc_companion_swing', npc_companion)

    def move(base):
        next_move = {}
        async def call(writer, row, game, payload, now, context=None):
            from tools.local_original_session import world_combat
            from tools.local_original_session.world_handlers import MovementResult
            service = ctx.realm.service(writer)
            position = service.snapshot()
            uid = position.uid
            status = magic_status.ai_status(current_effects(uid, now), now)
            if status['blocked'] or status['move_factor'] > 1 and now < next_move.get(uid, 0):
                reason = 'MAGIC_PARALYZED' if status['blocked'] else 'MAGIC_SLOW_CADENCE'
                correction = service._result(reason, correction=True)
                return MovementResult(False, correction.replies)
            result = await base(writer, row, game, payload, now, context=context)
            if result.accepted:
                state = view.combat.pcs.get(uid)
                if state is not None:
                    sprite = world_combat.PC_SPRITES.get((state.profile.character_class, state.profile.gender))
                    action = view.data.action_speed.pc.get(sprite)
                    if action is not None:
                        next_move[uid] = now + action.walk_ms / 1000 * view.combat.speed_factor(uid, now) * (
                            status['move_factor'] / status['attack_factor'])
            return result
        return call
    # Context delegates writes to the broker, but not deletions. Record the
    # actual instance owner so stop restores the same binding it replaced.
    from tools.local_original_session.world_bridge import Context
    install(ctx.broker if isinstance(ctx, Context) else ctx, '_world_move_for_handler', move)

    def refresh_pcs(base):
        def call(uid):
            known = set(view.pc_known.get(uid, ()))
            frames = base(uid)
            for peer in sorted(view.pc_known.get(uid, set()) - known):
                frames.extend(ctx._world_magic_replay_invisible(peer, view.runtime.clock()))
                frames.extend(ctx._world_magic_replay_feedback(peer, view.runtime.clock()))
            return frames
        return call
    install(view, '_refresh_pcs', refresh_pcs)

    def refresh(base):
        def call(uid):
            known = set(view.visibility.known.get(uid, ()))
            frames = base(uid)
            for target in sorted(view.visibility.known.get(uid, set()) - known):
                frames.extend(ctx._world_magic_replay_invisible(target, view.runtime.clock()))
                frames.extend(ctx._world_magic_replay_feedback(target, view.runtime.clock()))
            return frames
        return call
    install(view, '_refresh', refresh)


def _world_magic_npc_swing(ctx, monster, uid, ref, now):
    """Select a sourced spell on the ordinary AI swing; None keeps physical.

    MP belongs to the shared NPC resource owner; reuse follows EntityRef life.
    Core range/LOS/cadence and the core HP/status/death consumer stay in place.
    Area spell definitions apply only to the selected target (LOCAL).
    """
    from tools.local_original_session import world_combat
    definitions = getattr(ctx, '_world_magic_npc_spells', {}).get(monster.l1j_npcid, ())
    if ref is None or not definitions:
        return None
    view, engine = ctx.world, ctx._world_magic
    entity, target = view.entities.resolve(ref), view.entities.get(uid)
    found = view.spawner.slot_for(ref.uid)
    if entity is None or target is None or found is None or not entity.alive:
        return None
    state = view.combat.pcs.get(uid)
    adapter = None
    if state is None:
        adapter = next((value for value in ctx.collect_sync_hooks('npc_magic_target', uid)
                        if value is not None), None)
        if adapter is None:
            return None
    resources = ctx._world_magic_npc_resources
    mana = resources.mana_of(ref, monster.mp)
    engine.effects(ref.uid, target_ref=ref)
    row = engine.npc_statuses[ref.uid]
    if row.get('next_cast_at', 0) > now:
        return None
    distance = max(abs(entity.x - target.x), abs(entity.y - target.y))
    for spell in definitions:
        if (mana < spell.mp_cost or distance > spell.max_distance
                or view.combat.rng.randint(1, 100) > spell.chance_percent):
            continue
        if not resources.spend_mana(ref, monster.mp, spell.mp_cost):
            continue
        row['next_cast_at'] = now + max(spell.reuse_seconds, spell.cast_interval_seconds)
        before = state.hp if adapter is None else adapter.hp
        profile = state.profile if adapter is None else adapter.profile
        trace = {}
        countered = engine.consume_counter(uid, now) if adapter is None else adapter.counter(now)
        if countered:
            result = world_combat.Swing(True, 0), None
            if adapter is None:
                # A countered NPC spell is still the next hostile attempt.
                # The ordinary non-counter branch consumes in reduced_magic.
                engine.consume_erase(uid, now)
                ctx._world_magic_save(uid)
                ctx._world_magic_sync_icons(uid, now)
        else:
            attack = world_combat.NpcMagicAttack(spell.parameters, spell.intelligence,
                leverage=spell.leverage, trace=trace)
            result = (view.combat.npc_magic_swing(monster, uid, attack) if adapter is None
                      else adapter.apply(monster, attack, now))
        after = state.hp if adapter is None else adapter.hp
        group, slot = found
        restored = 0
        if spell.drain:
            restored = min(monster.hp - slot.hp, before - after)
            slot.hp += restored
        ctx._world_magic_events.append(dict(outcome='npc_countered' if countered else 'npc_magic',
            npc_uid=ref.uid, npc_generation=ref.generation, target=uid,
            template_id=monster.template_id, l1j_npcid=monster.l1j_npcid,
            skill_id=spell.skill_id, classic_key=spell.classic_key, spell=spell.spell_name,
            parameters=dict(spell.parameters), intelligence=spell.intelligence,
            leverage=spell.leverage, hp_before=before, hp_after=after,
            amount=before-after, rolled_damage=result[0].damage, drain_restored=restored,
            mp_before=mana, mp_after=resources.mana_of(ref, monster.mp), next_cast_at=row['next_cast_at'],
            resist_earth=profile.resist_earth, resist_fire=profile.resist_fire,
            resist_water=profile.resist_water, resist_wind=profile.resist_wind,
            trace=trace, source_refs=spell.source_refs, policy='local_policy', at=now))
        del ctx._world_magic_events[:-64]
        return result
    return None


def _world_magic_status_tick(ctx, now):
    from tools.local_original_session.world_combat import status_frame
    engine, view = ctx._world_magic, ctx.world
    for uid, row in tuple(engine.npc_statuses.items()):
        target = view.entities.resolve(row['ref'])
        found = view.spawner.slot_for(uid)
        if target is None or not target.alive or found is None or not found[0].active or found[1].hp <= 0:
            del engine.npc_statuses[uid]
        else:
            magic_status.expire(row['effects'], now)
    for uid, state in tuple(engine.states.items()):
        meditation = state.effects.get('meditation')
        if meditation is None or meditation['starts_at'] > now:
            continue
        pc = view.combat.pcs.get(uid)
        if pc is None or pc.dead:
            # No deferred offline recovery. The live deadline still elapses.
            meditation['params']['next_tick'] = now + meditation['params']['tick_seconds']
            continue
        params = meditation['params']
        due = params.setdefault('next_tick', now + params['tick_seconds'])
        cutoff = min(now, meditation['until'])
        if due <= cutoff:
            ticks = int((cutoff - due) // params['tick_seconds']) + 1
            params['next_tick'] = due + ticks * params['tick_seconds']
            before = pc.mp
            pc.status_fields[12] = min(pc.max_mp, pc.mp + ticks * params['mp_restore'])
            if pc.mp != before:
                view._queue(uid, status_frame(pc.status_fields, pc.hp))
                view._announce()
            ctx._world_magic_save(uid)


def _world_magic_save(ctx, uid, *, learned=None):
    store = ctx._world_magic_store
    if store is not None and uid in ctx._world_magic.states:
        store.save(ctx._world_magic.snapshot(uid, ctx.world.runtime.clock(), learned=learned))


def _world_magic_tick(ctx, now):
    from tools.local_original_session.world_combat import status_frame
    ctx._world_magic_poison_tick(now)
    _world_magic_status_tick(ctx, now)
    ctx.world.light_sources = {uid: max(until for key, until in state.buffs.items()
        if until > now and ctx._world_magic.spells[key].kind == 'light')
        for uid, state in ctx._world_magic.states.items()
        if uid in ctx.world.pcs and ctx._world_magic.is_lit(uid, now)}
    for uid in ctx._world_magic.expire(now):
        ctx._world_magic_save(uid)
        ctx._world_magic_sync_icons(uid, now)
        ctx._world_magic_sync_invisible(uid, now)
        if uid in ctx.world.combat.pcs:
            ctx._world_recalculate_uid(uid)
            state = ctx.world.combat.pcs[uid]
            ctx.world._queue(uid, status_frame(state.status_fields, state.hp))
            ctx.world._announce()
        ctx._world_magic_events.append(dict(uid=uid, outcome='expired', at=now))
        del ctx._world_magic_events[:-64]
    # Onset and external cure/item producers need publication even when they
    # did not expire a row. No ledger mutation or deferred damage is added.
    for uid in (set(ctx._world_magic.states) | set(ctx._world_magic.npc_statuses)
                | set(ctx._world_magic.npc_poison) | set(getattr(ctx, '_world_magic_feedback', {}))):
        ctx._world_magic_sync_feedback(uid, now)


def _world_magic_icon_deadlines(ctx, uid):
    state = ctx._world_magic.states.get(uid)
    if state is None:
        return None
    active = dict(state.buffs)
    active.update({row['spell']: row['until'] for row in state.effects.values()
                   if row['spell'] in ctx._world_magic.spells and row['until'] is not None})
    return active


def _world_magic_sync_icons(ctx, uid, now):
    """Normal packet publication; no native callback/update invocation."""
    ctx._world_magic_sync_feedback(uid, now)
    if not getattr(ctx, '_world_magic_buff_ui', False):
        return
    active = _world_magic_icon_deadlines(ctx, uid)
    if active is None:
        return
    for (owner, key), instance in tuple(ctx._world_magic_icons.items()):
        if owner == uid and active.get(key, 0) <= now:
            ctx.world._queue(uid, buff_icon_frame(key, instance, 0, remove=True))
            del ctx._world_magic_icons[(owner, key)]
    for key, until in active.items():
        if until <= now or key not in SPELL_BUFF_ICONS or ctx._world_magic.spells[key].kind == 'unsupported':
            continue
        instance = ctx._world_magic_icons.get((uid, key))
        if instance is None:
            instance = SPELL_BUFF_ICONS[key]
            ctx._world_magic_icons[(uid, key)] = instance
        ctx.world._queue(uid, buff_icon_frame(key, instance, until - now))


def _world_magic_after_relocate(ctx, uid, transit):
    """Replay active spell HUD rows without changing their deadlines or keys."""
    invisible = ctx._world_magic_replay_invisible(uid, ctx.world.runtime.clock())
    private, actor = _world_magic_feedback_frames(ctx, uid, ctx.world.runtime.clock(), force=True)
    invisible += private + actor
    if not getattr(ctx, '_world_magic_buff_ui', False):
        return invisible
    active = _world_magic_icon_deadlines(ctx, uid)
    if active is None:
        return invisible
    now = ctx.world.runtime.clock()
    return invisible + tuple(buff_icon_frame(key,
        ctx._world_magic_icons.get((uid, key), SPELL_BUFF_ICONS[key]), until - now)
        for key, until in active.items()
        if until > now and key in SPELL_BUFF_ICONS
        and ctx._world_magic.spells[key].kind != 'unsupported')


def _world_magic_stats(ctx, value, position, *, level=None):
    """Add only this feature's modifiers to the core base/equipment result."""
    calculated, worn, info = value
    magic = ctx._world_magic
    now = ctx.world.runtime.clock()
    bonus = magic.ac_bonus(position.uid, now,
        armor_uid=_world_magic_armor_uid(ctx, position.uid))
    dexterity = magic.dexterity_bonus(position.uid, now)
    bonuses = magic.job_bonuses(position.uid, now)
    if dexterity or any(bonuses.values()):
        from tools.local_original_session import world_stats
        base = world_stats.CharacterStats(calculated.level, info[3],
            world_stats.Attributes(info[11], info[12], info[13], info[14], info[15], info[16]))
        calculated = world_stats.calculate_stats(base, worn,
            buffs=(world_stats.StatModifiers(dexterity=dexterity, **bonuses),))
    return replace(calculated, ac=calculated.ac + bonus), worn, info


def _world_magic_select_element(ctx, uid, element):
    # Trusted registered selection producer only; no cast infers a school.
    ctx._world_magic.select_element(uid, element)
    ctx._world_magic_save(uid)
    if uid in ctx.world.combat.pcs:
        ctx._world_recalculate_uid(uid)
        ctx._world_magic_sync_icons(uid, ctx.world.runtime.clock())


def _world_magic_weight_capacity(ctx, capacity, calculated, position):
    from tools.local_original_session import world_weight
    return world_weight.maximum_weight(calculated.attributes.strength,
        calculated.attributes.con, decrease_weight=ctx._world_magic.active(
            position.uid, 'weight', ctx.world.runtime.clock()))


def _world_magic_speed_factors(ctx, factors, uid, now):
    """LOCAL cadence projection: entangle changes only the movement axis.

    The common publisher supplies the already composed attack interval factor;
    slow/berserk are included there, so only the movement-only ratio is added.
    4E5B key0/key1 consumption is retained from REA206/324; spell rates remain
    the existing backend policy, not a claim about the original server table.
    """
    state = ctx._world_magic.states.get(uid)
    if state is None:
        return factors
    status = magic_status.ai_status(state.effects, now)
    move, attack = factors
    return move * status['move_factor'] / status['attack_factor'], attack


def _world_magic_item_weight(ctx, current, template_id):
    policy = getattr(ctx, 'item_policies', {}).get(template_id)
    if policy is not None:
        return policy.raw_weight
    return ctx._world_magic.item_raw_weight(template_id) or current


def _world_magic_weapon_uid(ctx, uid):
    effect = getattr(ctx, '_item_equipment_effect', None)
    if effect is None:
        return 0
    equipment, _ = effect.store.peek(uid)
    return 0 if equipment is None else equipment.weapon_uid


def _world_magic_armor_uid(ctx, uid):
    """Read the existing equipped body-armor owner without changing its kit."""
    from tools.local_original_session import inventory
    effect = getattr(ctx, '_item_equipment_effect', None)
    if effect is None:
        return 0
    equipment, frame = effect.store.peek(uid)
    if equipment is None or frame is None:
        return 0
    selected = {member_uid for _, member_uid in equipment.slots}
    for item in inventory.validate_kit_frame(frame):
        definition = ctx.world.data.items.get(item.template_bits)
        if (item.identifier in selected and definition is not None
                and definition.kind == 'armor' and definition.slot == 'armor'):
            return item.identifier
    return 0


def _world_magic_combat_profile(ctx, uid, profile, now, *, ranged=False):
    """Apply the saved spell to its selected weapon; never mutate base stats."""
    engine, selected = ctx._world_magic, ctx._world_magic_weapon_uid(uid)
    state = engine.states.get(uid)
    if state is None:
        return profile
    bonuses = engine.job_bonuses(uid, now)
    hit = bonuses['ranged_hit' if ranged else 'melee_hit']
    damage = bonuses['ranged_damage' if ranged else 'melee_damage']
    for key, until in state.buffs.items():
        if until <= now or state.weapon_uids.get(key) != selected:
            continue
        spell = engine.spells[key]
        if ranged and spell.kind == 'weapon_hit':
            continue  # Holy Weapon's sourced +1/+1 is explicitly melee-only.
        if spell.kind in ('weapon_hit', 'weapon_damage'):
            policy = spell.raw['player_policy']
            hit += policy.get('hit_bonus', 0)
            damage += policy.get('damage_bonus', 0)
    return replace(profile, weapon=replace(profile.weapon,
        hit=profile.weapon.hit + hit, damage=profile.weapon.damage + damage))


def _world_magic_feedback_state(ctx, uid, now):
    target = ctx.world.entities.get(uid)
    if target is None:
        return None, magic_status.client_feedback({}, now)
    engine = ctx._world_magic
    state = engine.states.get(uid)
    if state is not None:
        effects, poison = state.effects, state.poison
    else:
        row = engine.npc_statuses.get(uid)
        effects = {} if row is None or row['ref'] != target.ref else row['effects']
        poison = engine.npc_poison.get(uid)
        if poison is not None and poison['target_ref'] != target.ref:
            poison = None
    if not target.alive:
        effects, poison = {}, None
    return target, magic_status.client_feedback(effects, now,
        poisoned=poison is not None and poison['until'] > now)


def _world_magic_feedback_frames(ctx, uid, now, *, force=False):
    target, desired = _world_magic_feedback_state(ctx, uid, now)
    cache = getattr(ctx, '_world_magic_feedback', None)
    if cache is None:
        cache = ctx._world_magic_feedback = {}
    empty = magic_status.client_feedback({}, now)
    previous = cache.get(uid)
    before = empty if previous is None or target is None or previous[0] != target.ref else previous[1]
    if target is None:
        cache.pop(uid, None)
        return (), ()
    private, actor = [], []
    if uid in ctx.world.pcs:
        # Add replacement owners before releasing old ones; the native common
        # action gate therefore remains locked while either status is active.
        # force is used only after the new self Actor: reset our inactive keys,
        # rather than sending a late 4EEB after Restart has removed that Actor.
        for key in sorted(desired['locks'] if force else desired['locks'] - before['locks']):
            private.append(paralyse_frame(key, True))
        for key in sorted(({0, 2} if force else before['locks']) - desired['locks']):
            private.append(paralyse_frame(key, False))
        if desired['blind'] != before['blind'] or force:
            private.append(blind_frame(desired['blind']))
        # Fixed-client string.csv IDs: 213/112 paralyze onset/release,
        # 999/2196 stun onset/release, 3061 poison description. Their TYPEs
        # belong to string_type.jsonc's spell channel. 4EEA f1 is the existing
        # SC_MESSAGE_CODE_NOTI contract (CHAT_ATTACK_CONTRACTS 2.3).
        # Publishing on actual state transitions is LOCAL backend policy.
        # Force/replay alone never repeats a notice or changes a deadline.
        if target.alive:
            for key in sorted(desired['locks'] - before['locks']):
                code = {0: 999, 2: 213}[key]
                private.append(_frame(0x4eea, pb.encode_uint32(1, code)))
            if before['locks'] and not desired['locks']:
                # The source release strings promise movement. A remaining
                # overlapping lock must not publish that promise early.
                code = 112 if 2 in before['locks'] else 2196
                private.append(_frame(0x4eea, pb.encode_uint32(1, code)))
            if desired['poison'] and not before['poison']:
                private.append(_frame(0x4eea, pb.encode_uint32(1, 3061)))
    if ((desired['poison'], desired['stone']) != (before['poison'], before['stone'])
            or force
            or uid in ctx.world.pcs and 2 in (desired['locks'] ^ before['locks'])):
        actor.append(poison_frame(uid, desired['poison'], desired['stone']))
    if any(desired.values()):
        cache[uid] = target.ref, desired
    else:
        cache.pop(uid, None)
    return tuple(private), tuple(actor)


def _world_magic_sync_feedback(ctx, uid, now, *, force=False):
    private, actor = _world_magic_feedback_frames(ctx, uid, now, force=force)
    view, target = ctx.world, ctx.world.entities.get(uid)
    if uid in view.pcs:
        for wire in private:
            view._queue(uid, wire)
    if target is not None:
        recipients = set(view._watchers(target)) | ({uid} if uid in view.pcs else set())
        for watcher in recipients:
            for wire in actor:
                view._queue(watcher, wire)
    if private or actor:
        view._announce()


def _world_magic_replay_feedback(ctx, uid, now):
    target, desired = _world_magic_feedback_state(ctx, uid, now)
    if target is None or not target.alive or not (desired['poison'] or desired['stone']):
        return ()
    if not hasattr(ctx, '_world_magic_feedback'):
        ctx._world_magic_feedback = {}
    # A replay to one observer must not replace the owner's lock/blind history.
    previous = ctx._world_magic_feedback.get(uid)
    if previous is None or previous[0] != target.ref:
        before = magic_status.client_feedback({}, now)
        before.update(poison=desired['poison'], stone=desired['stone'])
        ctx._world_magic_feedback[uid] = target.ref, before
    return (poison_frame(uid, desired['poison'], desired['stone']),)


def _world_magic_apply_poison(ctx, target_uid, source_uid, now, *, duration=30,
                            tick_seconds=3.0, damage=5):
    """One LOCAL infection, owned by current PC or the current NPC EntityRef."""
    poison = dict(until=now + duration, next_tick=now + tick_seconds,
                  tick_seconds=tick_seconds, damage=damage, source_uid=source_uid)
    if target_uid in ctx.world.combat.pcs:
        ctx._world_magic.state(target_uid).poison = poison
        ctx._world_magic_save(target_uid)
    else:
        target = ctx.world.entities.get(target_uid)
        need(target is not None and target.alive, 'MAGIC_POISON_CURRENT_TARGET_REQUIRED')
        ctx._world_magic.npc_poison[target_uid] = dict(poison, target_ref=target.ref)
    ctx._world_magic_sync_feedback(target_uid, now)


def _world_magic_set_invisible(ctx, uid, now, duration=30):
    """Existing/future status producer API, not an added invisibility spell."""
    if uid in ctx.world.combat.pcs:
        ctx._world_magic.state(uid).invisible_until = now + duration
        ctx._world_magic_save(uid)
    else:
        target = ctx.world.entities.get(uid)
        need(target is not None and target.alive, 'MAGIC_INVISIBLE_CURRENT_TARGET_REQUIRED')
        ctx._world_magic.npc_invisible[uid] = dict(until=now + duration, target_ref=target.ref)
    ctx._world_magic_sync_invisible(uid, now)


def _world_magic_sync_invisible(ctx, uid, now, *, force=False):
    """Publish to clients which already own the same current actor lifetime."""
    view = ctx.world
    target = view.entities.get(uid)
    published = getattr(ctx, '_world_magic_invisible', None)
    if published is None:
        published = ctx._world_magic_invisible = {}
    prior = published.get(uid)
    if target is None or not target.alive:
        published.pop(uid, None)
        return
    active = ctx._world_magic.is_invisible(uid, now)
    if not force and prior == (target.ref, active):
        return
    if active or prior == (target.ref, True):
        wire = invisible_frame(uid, active)
        for watcher in set(view._watchers(target)) | ({uid} if uid in view.pcs else set()):
            view._queue(watcher, wire)
        view._announce()
    if active:
        published[uid] = target.ref, True
    else:
        published.pop(uid, None)


def _world_magic_replay_invisible(ctx, uid, now):
    """A fresh Actor must precede its active state in the same reply batch."""
    target = ctx.world.entities.get(uid)
    if target is None or not target.alive or not ctx._world_magic.is_invisible(uid, now):
        return ()
    if not hasattr(ctx, '_world_magic_invisible'):
        ctx._world_magic_invisible = {}
    ctx._world_magic_invisible[uid] = target.ref, True
    return (invisible_frame(uid, True),)


def _world_magic_poison_tick(ctx, now):
    from tools.local_original_session import world_combat
    engine, view = ctx._world_magic, ctx.world
    for uid, invisible in tuple(engine.npc_invisible.items()):
        if invisible['until'] <= now or view.entities.resolve(invisible['target_ref']) is None:
            del engine.npc_invisible[uid]
            ctx._world_magic_sync_invisible(uid, now)
    for uid, state in tuple(engine.states.items()):
        poison, pc = state.poison, view.combat.pcs.get(uid)
        if poison is None:
            continue
        if pc is None:
            # An unselected character is not taking damage. Retain the real
            # expiry but never accumulate deferred offline poison ticks.
            poison['next_tick'] = max(poison['next_tick'], now + poison['tick_seconds'])
            continue
        if pc.dead:
            continue
        changed = False
        while poison['next_tick'] <= min(now, poison['until']) and not pc.dead:
            pc.hp = max(0, pc.hp - poison['damage'])
            poison['next_tick'] += poison['tick_seconds']
            changed = True
            if pc.hp == 0:
                pc.dead = True
        if changed:
            view._queue(uid, world_combat.status_frame(pc.status_fields, pc.hp))
            if pc.dead:
                # The death hook owns buff/status cleanup and its one save.
                view._pc_died(uid, now)
            else:
                ctx._world_magic_save(uid)
            view._announce()
    for uid, poison in tuple(engine.npc_poison.items()):
        target = view.entities.resolve(poison['target_ref'])
        found = view.spawner.slot_for(uid)
        if target is None or not target.alive or found is None or not found[0].active:
            del engine.npc_poison[uid]
            continue
        while poison['next_tick'] <= min(now, poison['until']):
            group, slot = found
            if slot.hp <= 0:
                break
            amount = min(slot.hp, poison['damage'])
            view._apply_monster_swing(poison['source_uid'], poison['source_uid'], target,
                group.monster, slot.hp, world_combat.Swing(True, amount), now)
            poison['next_tick'] += poison['tick_seconds']
            ctx._world_magic_events.append(dict(uid=poison['source_uid'], target=uid,
                outcome='poison_tick', amount=amount, at=now))
            del ctx._world_magic_events[:-64]
            view._announce()
            found = view.spawner.slot_for(uid)
            if found is None or found[1].hp <= 0:
                break
        if poison['until'] <= now or found is None or found[1].hp <= 0:
            engine.npc_poison.pop(uid, None)


async def _world_magic_enter(ctx, writer, row, game, operation_lock):
    if not ctx._world_bound(writer) or ctx._world_magic_store is None:
        return
    uid = ctx._world_pcs[id(writer)][1]
    def enter():
        engine = ctx._world_magic
        if uid not in engine.states:
            saved = ctx._world_magic_store.rows.get(uid)
            if saved is None:
                engine.state(uid)
            else:
                engine.restore(uid, saved, ctx.world.runtime.clock())
        # Existing in-process state retains monotonic deadlines through Restart.
        poison = engine.state(uid).poison
        if poison is not None:
            # Restart/login never replays time spent outside the world. The
            # next live tick starts a fresh interval; the expiry is unchanged.
            poison['next_tick'] = max(poison['next_tick'],
                ctx.world.runtime.clock() + poison['tick_seconds'])
        meditation = engine.status(uid, 'meditation', ctx.world.runtime.clock())
        if meditation is not None:
            meditation['params']['next_tick'] = ctx.world.runtime.clock() + meditation['params']['tick_seconds']
        ctx._world_magic_tick(ctx.world.runtime.clock())
        ctx._world_magic_writers[id(writer)] = uid
        ctx._world_magic_sync_feedback(uid, ctx.world.runtime.clock(), force=True)
        ctx._world_magic_sync_icons(uid, ctx.world.runtime.clock())
        ctx._world_magic_sync_invisible(uid, ctx.world.runtime.clock(), force=True)
        ctx._world_recalculate_uid(uid)
        from tools.local_original_session.world_combat import status_frame
        state = ctx.world.combat.pcs[uid]
        return (*ctx.world.drain(uid), available_frame(engine.state(uid).learned),
                status_frame(state.status_fields, state.hp))
    frames = await ctx.world.runtime.dispatch_now(enter)
    await ctx._world_send(writer, row, frames, operation_lock)


def _world_magic_detach(ctx, writer):
    uid = ctx._world_magic_writers.pop(id(writer), None)
    if uid is not None:
        ctx._world_magic_save(uid)
        ctx.world.light_sources.pop(uid, None)
        getattr(ctx, '_world_magic_invisible', {}).pop(uid, None)
        getattr(ctx, '_world_magic_feedback', {}).pop(uid, None)
        # A reselected native scene owns a new UI lifetime; republish its rows.
        for pair in tuple(ctx._world_magic_icons):
            if pair[0] == uid:
                del ctx._world_magic_icons[pair]


async def _world_magic_after_request(ctx, writer, row, game, opcode, operation_lock):
    # Session feature calls _world_leave itself on Restart; bridge's socket-close
    # after_leave hook is therefore insufficient for the selection-screen path.
    if id(writer) in ctx._world_magic_writers and not ctx._world_bound(writer):
        ctx._world_magic_detach(writer)


def _world_magic_after_leave(ctx, writer):
    ctx._world_magic_detach(writer)


def _world_magic_stopped(ctx):
    for uid in tuple(ctx._world_magic.states):
        ctx._world_magic_save(uid)
    ctx.world.light_sources.clear()
    ctx._world_magic.npc_poison.clear()
    ctx._world_magic.npc_invisible.clear()
    ctx._world_magic.npc_statuses.clear()
    getattr(ctx, '_world_magic_invisible', {}).clear()
    getattr(ctx, '_world_magic_feedback', {}).clear()
    for handle in reversed(getattr(ctx, '_world_magic_adapters', ())):
        handle.close()
    ctx._world_magic_adapters = []
    entry = getattr(ctx, '_world_magic_status_event', None)
    if entry is not None:
        ctx.world.events.remove('magic_status_changed', entry)
        ctx._world_magic_status_event = None
    modifier = getattr(ctx, '_world_magic_profile_modifier', None)
    if modifier in ctx.world.combat.profile_modifiers:
        ctx.world.combat.profile_modifiers.remove(modifier)


def _world_magic_died(ctx, uid):
    state = ctx._world_magic.states.get(uid)
    if state is not None:
        state.buffs.clear()
        state.weapon_uids.clear()
        state.armor_uids.clear()
        state.buff_sources.clear()
        state.poison = None
        state.invisible_until = 0.0
        # A damaged physical weapon remains damaged after the character dies;
        # its selected item UID and repair producer, not the PC life, own it.
        state.effects = {kind: row for kind, row in state.effects.items()
                         if kind == 'weapon_break' and row['until'] is None}
        ctx.world.light_sources.pop(uid, None)
        ctx._world_recalculate_uid(uid)
        ctx._world_magic_save(uid)
        ctx._world_magic_sync_icons(uid, ctx.world.runtime.clock())
        ctx._world_magic_sync_invisible(uid, ctx.world.runtime.clock())


def _world_magic_display(ctx, caster, target, spell, force=False):
    """Publish committed cast display; companions force their visible actions.

    This projects an admitted cast only, with no learning/cost/state mutation.
    Projectile graphics use the existing target-effect lane, not flight fields.
    """
    key = getattr(spell, 'key', spell)
    if not force and os.environ.get('SL_SPELL_EXP') == '0' and key != 4:
        return
    row = SPELL_DISPLAY.get(key)
    if row is None:
        return  # No generic kind-based graphic or action guess.
    from tools.local_original_session import attack
    from tools.local_original_session.npc_ai import heading_to
    body = b''.join(attack._field(n, value) for n, value in (
        (1, row['action_id']), (2, caster.uid), (3, target.uid),
        (4, 0), (5, heading_to(caster.x, caster.y, target.x, target.y)),
        (13, 1)))  # RVA977A0 own caster skips the action if f13 is absent/false.
    frames = [_frame(0x4e31, body)]
    graphic = next(g for g in row['graphics'] if g['field'] == 'castgfx')
    if graphic['status'] == 'PRESENT':
        from tools.local_original_session.world_status_frames import effect_frame
        # Sprite key stays distinct from its file alias (e.g. 829/830 -> 744).
        # All adopted castgfx2 values are zero; no secondary-effect rule needed.
        frames.append(effect_frame(target.uid, graphic['gfx']))
    recipients = (set(ctx.world._watchers(caster)) | set(ctx.world._watchers(target))
                  | ({caster.uid, target.uid} & ctx.world.pcs.keys()))
    # A PC never needs its own UID in visibility.known. Its normal outbox is
    # nevertheless an effect recipient, including self-target Heal and Shield.
    for watcher in recipients:
        for wire in frames:
            ctx.world._queue(watcher, wire)


def _world_magic_cast(ctx, uid, key, target_uid, now, *, row=None, game=None):
    from tools.local_original_session import world_combat
    from tools.local_original_session.npc_ai import distance, local_line_clear
    view, engine = ctx.world, ctx._world_magic
    state, caster = view.combat.pcs[uid], view.entities.get(uid)
    spell = engine.admit_cast(uid, key, state.profile.character_class,
        state.profile.level, state.mp, not state.dead and state.hp > 0, now)
    need(caster is not None and caster.alive, 'MAGIC_CURRENT_CASTER_REQUIRED')
    if target_uid is None:
        need(spell.kind not in {'damage', 'area_damage', 'drain', 'poison', 'weak_elemental'} | HOSTILE,
             'MAGIC_TARGET_REQUIRED')
        target_uid = uid  # explicit LOCAL self default for optional UseSpellParam
    target = view.entities.get(target_uid)
    need(target is not None and target.alive and caster.map_id == target.map_id,
         'MAGIC_LIVING_SAME_MAP_TARGET_REQUIRED')
    known = view.pc_known if target_uid in view.combat.pcs else view.visibility.known
    need(target_uid == uid or target_uid in known.get(uid, ()),
         'MAGIC_VISIBLE_TARGET_REQUIRED')
    need(distance(caster.x, caster.y, target.x, target.y) <= spell.range,
         'MAGIC_TARGET_OUT_OF_RANGE')
    need(local_line_clear(view.terrain, caster.map_id, caster.x, caster.y, target.x, target.y),
         'MAGIC_TARGET_LINE_BLOCKED')
    sight = magic_status.ai_status(engine.state(uid).effects, now)['sight']
    need(sight is None or distance(caster.x, caster.y, target.x, target.y) <= sight,
         'MAGIC_CASTER_SIGHT_BLOCKED')
    writer = next((value[0] for value in ctx._world_pcs.values() if value[1] == uid), None)
    need(writer is not None, 'MAGIC_CURRENT_WRITER_REQUIRED')
    calculated, _, info = ctx._world_stats_for(ctx.realm.service(writer).snapshot(), level=state.profile.level)
    need(not calculated.weight.normal_skill_blocked, 'MAGIC_WEIGHT_BLOCKED')
    intelligence = calculated.attributes.intelligence
    item_sp = ctx.fold_sync_hooks('spell_power', 0, uid, now)
    found, amount, destination, weapon_uid, armor_uid = None, 0, None, 0, 0
    received_buff = None
    policy = spell.raw['player_policy']
    ctx.run_sync_hooks('spell_cast_admit', uid, spell, target, now)
    npc_reference = {}
    outcome = 'cast'
    erase_consumed, healing_multiplier = False, 1.0
    victims = []
    if spell.kind in ('damage', 'area_damage', 'drain', 'poison'):
        found = view.spawner.slot_for(target_uid)
        need(found is not None and found[0].active and found[1].hp > 0,
             'MAGIC_CURRENT_HOSTILE_MONSTER_REQUIRED')
        if spell.kind == 'area_damage':
            # The official target radius selects actual current monsters.
            # Chebyshev tiles, hostile NPC-only scope and LOS are LOCAL policy.
            # Snapshot EntityRefs before a kill mutates the spawn registry.
            radius = spell.raw['player_policy']['area_radius']
            for candidate in sorted(view.entities, key=lambda entity: entity.uid):
                if (not candidate.alive or candidate.map_id != caster.map_id
                        or candidate.uid not in view.visibility.known.get(uid, ())
                        or distance(target.x, target.y, candidate.x, candidate.y) > radius
                        or not local_line_clear(view.terrain, caster.map_id,
                            caster.x, caster.y, candidate.x, candidate.y)):
                    continue
                candidate_slot = view.spawner.slot_for(candidate.uid)
                if (candidate_slot is None or not candidate_slot[0].active
                        or candidate_slot[1].hp <= 0):
                    continue
                engine.effects(candidate.uid, target_ref=candidate.ref)
                rolled = world_combat.magic_damage(spell.raw['formula']['parameters'],
                    intelligence, view.combat.rng, item_sp=item_sp,
                    weak_attr=candidate_slot[0].monster.weak_attr,
                    mr=engine.effective_mr(candidate.uid, candidate_slot[0].monster.mr, now))
                victims.append((candidate.ref, rolled))
        elif spell.kind != 'poison':
            engine.effects(target_uid, target_ref=target.ref)
            npc_reference = engine.catalog.get('local_policy', {}).get('npc_status_reference', {}).get(
                str(found[0].monster.template_id), {})
            amount = world_combat.magic_damage(spell.raw['formula']['parameters'],
                intelligence, view.combat.rng, item_sp=item_sp,
                weak_attr=found[0].monster.weak_attr,
                mr=engine.effective_mr(target_uid, found[0].monster.mr, now))
    elif spell.kind in HOSTILE | {'weak_elemental'}:
        found = view.spawner.slot_for(target_uid)
        target_pc = view.combat.pcs.get(target_uid)
        need(found is not None and found[0].active and found[1].hp > 0
             or target_pc is not None and not target_pc.dead and target_pc.hp > 0,
             'MAGIC_CURRENT_STATUS_TARGET_REQUIRED')
        if found is not None:
            npc_reference = engine.catalog.get('local_policy', {}).get('npc_status_reference', {}).get(
                str(found[0].monster.template_id), {})
        if spell.kind == 'turn_undead':
            need(found is not None and npc_reference, 'MAGIC_NPC_STATUS_REFERENCE_REQUIRED')
        if spell.kind == 'turn_undead':
            need(npc_reference.get('undead') in (1, 3) and npc_reference.get('is_tu'),
                 'MAGIC_TURN_UNDEAD_TARGET_REQUIRED')
        if spell.kind == 'weak_elemental':
            need(found is not None, 'MAGIC_CURRENT_STATUS_TARGET_REQUIRED')
            amount = found[0].monster.weak_attr
        if spell.kind == 'weapon_break' and target_pc is not None:
            weapon_uid = ctx._world_magic_weapon_uid(target_uid)
            need(weapon_uid > 0, 'MAGIC_EQUIPPED_WEAPON_REQUIRED')
        if spell.kind in ('slow', 'mana_drain') and found is not None:
            need(npc_reference.get('is_erase', True), 'MAGIC_TARGET_RESISTS_STATUS')
    elif spell.kind == 'water_life':
        healed = view.combat.pcs.get(target_uid)
        need(healed is not None and not healed.dead and healed.hp > 0,
             'MAGIC_LIVING_PC_HEAL_TARGET_REQUIRED')
    elif spell.kind == 'hp_to_mp':
        need(target_uid == uid, 'MAGIC_SELF_TARGET_REQUIRED')
        need(state.mp < state.max_mp, 'MAGIC_MP_ALREADY_FULL')
    elif spell.kind == 'heal':
        healed = view.combat.pcs.get(target_uid)
        need(healed is not None and not healed.dead and healed.hp > 0,
             'MAGIC_LIVING_PC_HEAL_TARGET_REQUIRED')
        amount = world_combat.magic_heal(spell.raw['formula']['parameters'], intelligence,
            view.progress.lawful_of(uid, state.status_fields.get(18, 0)),
            engine.catalog['formula_policies']['l1j_healing']['magic_bonus_by_int_0_to_50'],
            view.combat.rng)
    elif spell.kind in ('cure_poison', 'remove_curse'):
        need(target_uid in view.combat.pcs or view.spawner.slot_for(target_uid) is not None,
             'MAGIC_CURE_CURRENT_TARGET_REQUIRED')
    elif spell.kind in world_magic.BUFF_KINDS and target_uid != uid:
        need(world_magic.allows_received_buff(spell), 'MAGIC_SELF_TARGET_REQUIRED')
        received_buff = ctx._world_magic_buff_target(target_uid, key, uid)
        need(received_buff is not None, 'MAGIC_CURRENT_BUFF_TARGET_REQUIRED')
    else:
        need(target_uid == uid, 'MAGIC_SELF_TARGET_REQUIRED')
        if spell.kind in ('weapon_hit', 'weapon_damage') or policy.get('bind_weapon'):
            weapon_uid = ctx._world_magic_weapon_uid(uid)
            need(weapon_uid > 0, 'MAGIC_EQUIPPED_WEAPON_REQUIRED')
        if spell.kind == 'armor':
            armor_uid = _world_magic_armor_uid(ctx, uid)
            need(armor_uid > 0, 'MAGIC_EQUIPPED_ARMOR_REQUIRED')
        if spell.kind == 'teleport':
            from tools.local_original_session.world_item_effects import MapDestination, random_destination
            need(row is not None and game is not None and row['operation_lock'].locked()
                 and ctx.realm.registry.resolve(writer) is game, 'MAGIC_TELEPORT_CURRENT_REQUEST_REQUIRED')
            destination = random_destination(MapDestination(caster.map_id, caster.x, caster.y, caster.heading),
                view.terrain, view.combat.rng, spell.raw['player_policy'].get('teleport_radius', 200))
            need(destination is not None and ctx.realm.serves_map(destination.map_id),
                 'MAGIC_TELEPORT_DESTINATION_UNAVAILABLE')
    if found is not None and target_uid not in view.combat.pcs:
        engine.effects(target_uid, target_ref=target.ref)
    # Validate every resource before the one kit CAS and live HP/MP debit.
    hp_cost = (spell.raw.get('hp_cost') or {}).get('value') or 0
    need(state.hp > hp_cost, 'MAGIC_INSUFFICIENT_HP')
    materials = (spell.raw.get('materials') or {}).get('value') or []
    kit_before = kit_after = None
    material_frames = ()
    if materials:
        from tools.local_original_session import inventory
        need(getattr(ctx, '_inventory_kit_policy', None) == inventory.KIT_POLICY,
             'MAGIC_KIT_INVENTORY_REQUIRED')
        kit_before = ctx.inventory_frame
        equipment = getattr(ctx, '_item_equipment_effect', None)
        selected = None if equipment is None else equipment.store.peek(uid)[0]
        worn = (() if selected is None else
                {selected.weapon_uid, *(item_uid for _, item_uid in selected.slots)} - {0})
        kit_after, material_frames = world_magic.material_mutation(kit_before, materials, worn=worn)
    success = True
    if spell.kind in HOSTILE and 'probability_base' in policy:
        defender = view.combat.pcs.get(target_uid)
        target_level = defender.profile.level if defender is not None else found[0].monster.level
        success = magic_status.level_probability(policy['probability_base'],
            policy.get('probability_level_factor', 0), state.profile.level, target_level,
            view.combat.rng, dice=policy.get('probability_dice', 0))
    elif spell.kind in HOSTILE and policy.get('probability_dice'):
        defender = view.combat.pcs.get(target_uid)
        base_mr = defender.profile.mr if defender is not None else found[0].monster.mr
        success = magic_status.probability(policy['probability_dice'], intelligence,
            state.profile.level, state.profile.character_class, engine.effective_mr(target_uid, base_mr, now),
            engine.catalog['formula_policies']['l1j_healing']['magic_bonus_by_int_0_to_50'],
            view.combat.rng)
    # Ordinary positive catalyst consumption reuses the existing synchronous kit
    # owner, including equipment anchors and its CAS. No inventory shadow ledger.
    if materials:
        from tools.local_original_session.world_bridge import _flush_persist, _immediate_inventory
        _flush_persist(ctx.broker)
        _immediate_inventory(ctx.broker, 1)
        try:
            # Mark the attempted persistence boundary before invoking it: an
            # owner may have committed a partial write before raising.
            ctx._world_magic_resource_commits = getattr(ctx, '_world_magic_resource_commits', 0) + 1
            need(ctx._world_replace_kit(uid, kit_before, kit_after) is True,
                 'MAGIC_CATALYST_PERSISTED_CHANGE_REQUIRED')
        finally:
            _immediate_inventory(ctx.broker, -1)
        ctx.inventory_frame = kit_after
        for wire in material_frames:
            view._queue(uid, wire)
    before = state.mp
    state.status_fields[12] = before - spell.mp
    state.hp -= hp_cost
    view.combat.note_activity(uid, 1)
    if received_buff is None:
        engine.committed(uid, spell, now)
    else:
        # Reuse belongs to the caster; the recipient alone owns this effect.
        engine.state(uid).next_cast_at = now + spell.reuse
    if weapon_uid and (spell.kind in ('weapon_hit', 'weapon_damage') or policy.get('bind_weapon')):
        engine.state(uid).weapon_uids[spell.key] = weapon_uid
    if armor_uid:
        engine.state(uid).armor_uids[spell.key] = armor_uid
    ctx._world_magic_save(uid)
    ctx._world_magic_display(caster, target, spell)
    # Counter Magic absorbs one eligible hostile spell. It never reflects HP
    # damage, and resource use/reuse belong to the already committed attempt.
    if found is not None and target_uid not in view.combat.pcs:
        engine.effects(target_uid, target_ref=target.ref)
    counter_policy = next((candidate.raw['player_policy'] for candidate in engine.spells.values()
                           if candidate.kind == 'counter_magic'), {})
    offensive = spell.kind != 'area_damage' and spell.kind in counter_policy.get('eligible_incoming_kinds',
        tuple(HOSTILE | {'damage', 'drain', 'poison'}))
    # LOCAL L1SkillUse: erase/stun do not consume the marker. Other real
    # hostile attempts consume it once, including failed/countered attempts.
    if spell.kind in HOSTILE | {'damage', 'drain', 'poison'} and spell.kind not in ('erase_magic', 'stun'):
        erase_consumed = engine.consume_erase(target_uid, now)
        if erase_consumed:
            ctx._world_magic_save(target_uid)
            ctx._world_magic_sync_icons(target_uid, now)
    if offensive and engine.consume_counter(target_uid, now):
        outcome = 'countered'
        ctx._world_magic_save(target_uid)
        ctx._world_magic_sync_icons(target_uid, now)
    elif not success:
        outcome = 'failed'
        if spell.kind == 'turn_undead':
            engine.apply_status(target_uid, 'berserk', now,
                policy.get('berserk_duration_seconds', 30), source_uid=uid, spell=spell.key,
                params={'interval_multiplier': policy.get('berserk_interval_multiplier', .5)},
                target_ref=target.ref)
    elif spell.kind == 'turn_undead':
        group, slot = found
        amount = slot.hp
        view._apply_monster_swing(uid, uid, target, group.monster, slot.hp,
                                 world_combat.Swing(True, amount), now)
    elif spell.kind == 'mana_drain':
        rolled = view.combat.rng.randint(1, policy.get('drain_dice', 10)) - 1 + policy.get('drain_base', 5)
        rolled += intelligence // policy.get('drain_int_divisor', 2)
        if found is not None:
            amount = ctx._world_magic_npc_resources.drain_mana(
                target.ref, found[0].monster.mp, rolled)
        else:
            target_state = view.combat.pcs[target_uid]
            amount = min(target_state.mp, rolled)
            target_state.status_fields[12] -= amount
            view._queue(target_uid, world_combat.status_frame(target_state.status_fields, target_state.hp))
        state.status_fields[12] = min(state.max_mp, state.mp + amount)
    elif spell.kind in HOSTILE_STATUS:
        params = {k: policy[k] for k in ('interval_multiplier', 'damage_multiplier', 'move_multiplier') if k in policy}
        if weapon_uid:
            params['weapon_uid'] = weapon_uid
        duration = (magic_status.stun_duration(view.combat.rng) if spell.kind == 'stun' else
                    None if spell.kind == 'weapon_break' and not spell.duration else spell.duration)
        engine.apply_status(target_uid, spell.kind, now, duration, source_uid=uid,
            spell=spell.key, params=params, target_ref=None if target_uid in view.combat.pcs else target.ref,
            onset=policy.get('onset_seconds', 0))
        ctx._world_magic_save(target_uid)
        if target_uid in view.combat.pcs:
            ctx._world_magic_sync_icons(target_uid, now)
        else:
            ctx._world_magic_sync_feedback(target_uid, now)
    elif spell.kind == 'weak_elemental':
        # This spell reveals an existing weakness, it does not lower resistance.
        engine.apply_status(uid, 'weak_elemental', now, max(spell.duration, 1), source_uid=uid,
            spell=spell.key, params={'target_uid': target_uid, 'weak_attr': amount})
        ctx._world_magic_save(uid)
    elif spell.kind == 'water_life':
        engine.apply_status(target_uid, 'water_life', now, spell.duration, source_uid=uid,
            spell=spell.key, params={'healing_multiplier': policy['healing_multiplier']})
        ctx._world_magic_save(target_uid)
        ctx._world_magic_sync_icons(target_uid, now)
    elif spell.kind in ('counter_magic', 'meditation'):
        params = ({'tick_seconds': policy.get('tick_seconds', 10), 'mp_restore': policy.get('mp_restore', 5),
                   'next_tick': now + policy.get('tick_seconds', 10)} if spell.kind == 'meditation' else {})
        engine.apply_status(uid, spell.kind, now, spell.duration, source_uid=uid, spell=spell.key, params=params)
        ctx._world_magic_save(uid)
        ctx._world_magic_sync_icons(uid, now)
    elif spell.kind == 'remove_curse':
        amount = len(engine.clear_curses(target_uid))
        if target_uid in view.combat.pcs:
            poisoned = engine.state(target_uid).poison is not None
            engine.state(target_uid).poison = None
            ctx.run_sync_hooks('cure_poison', target_uid)
            ctx._world_magic_save(target_uid)
            ctx._world_magic_sync_icons(target_uid, now)
        else:
            poisoned = engine.npc_poison.pop(target_uid, None) is not None
        amount += int(poisoned)
        ctx._world_magic_sync_feedback(target_uid, now)
    elif spell.kind == 'area_damage':
        for victim_ref, rolled in victims:
            victim = view.entities.resolve(victim_ref)
            current = view.spawner.slot_for(victim_ref.uid)
            if (victim is None or not victim.alive or current is None
                    or not current[0].active or current[1].hp <= 0):
                continue
            engine.effects(victim.uid, target_ref=victim.ref)
            erase_consumed = engine.consume_erase(victim.uid, now) or erase_consumed
            if engine.consume_counter(victim.uid, now):
                continue
            group, slot = current
            dealt = min(slot.hp, rolled)
            view._apply_monster_swing(uid, uid, victim, group.monster, slot.hp,
                                     world_combat.Swing(True, dealt), now)
            amount += dealt
    elif spell.kind in ('damage', 'drain'):
        group, slot = found
        amount = min(slot.hp, amount)
        view._apply_monster_swing(uid, uid, target, group.monster, slot.hp,
                                 world_combat.Swing(True, amount), now)
        if spell.kind == 'drain':
            # Heal from HP actually removed, including overkill and maxHP clamp.
            healed, wire = world_combat.apply_heal(view.combat, uid,
                int(amount * spell.raw['player_policy'].get('drain_ratio', 1.0)))
            view._queue(uid, wire)
    elif spell.kind == 'poison':
        policy = spell.raw['player_policy']
        ctx._world_magic_apply_poison(target_uid, uid, now, duration=spell.duration,
            tick_seconds=policy['tick_seconds'], damage=policy['tick_damage'])
    elif spell.kind == 'cure_poison':
        if target_uid in view.combat.pcs:
            engine.state(target_uid).poison = None
            ctx.run_sync_hooks('cure_poison', target_uid)
            ctx._world_magic_save(target_uid)
        else:
            engine.npc_poison.pop(target_uid, None)
        ctx._world_magic_sync_feedback(target_uid, now)
    elif spell.kind == 'detect':
        from tools.local_original_session.world_visibility import in_screen
        for detected_uid in tuple(engine.states):
            detected = view.entities.get(detected_uid)
            if (detected is not None and detected.map_id == caster.map_id
                    and in_screen(caster.x, caster.y, detected.x, detected.y)
                    and engine.is_invisible(detected_uid, now)):
                engine.state(detected_uid).invisible_until = 0.0
                ctx._world_magic_save(detected_uid)
                ctx._world_magic_sync_invisible(detected_uid, now)
        for detected_uid, status in tuple(engine.npc_invisible.items()):
            detected = view.entities.resolve(status['target_ref'])
            if (detected is None or status['until'] <= now
                    or detected.map_id == caster.map_id
                    and in_screen(caster.x, caster.y, detected.x, detected.y)):
                del engine.npc_invisible[detected_uid]
                ctx._world_magic_sync_invisible(detected_uid, now)
    elif spell.kind == 'teleport':
        for wire in ctx._world_relocate_locked(writer, row, game, destination):
            view._queue(uid, wire)
    elif spell.kind == 'hp_to_mp':
        amount = min(policy['mp_restore'], state.max_mp - state.mp)
        state.status_fields[12] += amount
    elif spell.kind == 'heal':
        water_life = engine.status(target_uid, 'water_life', now)
        healing_multiplier = 1.0 if water_life is None else water_life['params'].get('healing_multiplier', 1.5)
        amount = engine.healing_amount(target_uid, amount, now)
        ctx._world_magic_save(target_uid)
        ctx._world_magic_sync_icons(target_uid, now)
        amount, wire = world_combat.apply_heal(view.combat, target_uid, amount)
        view._queue(target_uid, wire)
    elif received_buff is not None:
        received_buff.apply(now)
    else:
        ctx._world_recalculate_uid(uid)
        ctx._world_magic_sync_icons(uid, now)
        if spell.kind == 'light':
            view.light_sources[uid] = engine.state(uid).buffs[spell.key]
    # PcState.hp is the current HP owner; status_fields[10] is an older
    # projection until another stats refresh. Keep the heal's final response
    # on that owner instead of overwriting its already queued current-HP frame.
    view._queue(uid, world_combat.status_frame(state.status_fields, state.hp))
    view._announce()
    ctx._world_magic_events.append(dict(uid=uid, key=key, spell=spell.name, target=target_uid,
        outcome=outcome, amount=amount, mp_before=before, mp_after=state.mp, hp_cost=hp_cost,
        item_sp=item_sp, erase_consumed=erase_consumed, healing_multiplier=healing_multiplier, at=now))
    del ctx._world_magic_events[:-64]


async def _world_magic_frame(ctx, writer, row, game, frame, operation_lock):
    from tools.local_original_session import inventory
    if (not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None
            or ctx._world_magic_store is None):
        return False
    if frame.opcode == 0x0960:
        # Only claim an owned spellbook. Other items retain their existing lane.
        try:
            with pb.parse_message(frame.payload) as message:
                ids = message.occurrences(1)
                if len(ids) != 1 or ids[0].wire_type != 0:
                    return False
                item = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                    if r.identifier == ids[0].value), None)
            if item is None or item.template_bits not in ctx._world_magic.books:
                return False
            item_uid = decode_book(frame.payload)
            request = ('book', item_uid, item.template_bits)
        except (ValueError, pb.WireError) as error:
            ctx._world_magic_errors = (ctx._world_magic_errors + [str(error)[:96]])[-8:]
            return True
    else:
        try:
            request = ('cast', *decode_cast(frame.payload))
        except (ValueError, pb.WireError) as error:
            ctx._world_magic_errors = (ctx._world_magic_errors + [str(error)[:96]])[-8:]
            return True
    uid = ctx._world_pcs[id(writer)][1]
    attempted = False
    def apply():
        nonlocal attempted
        need(ctx.realm.registry.resolve(writer) is game and ctx._world_bound(writer)
             and ctx.owner_current(writer, row, ctx.realm.service(writer).snapshot()),
             'MAGIC_CURRENT_SELECTED_OWNER_REQUIRED')
        state = ctx.world.combat.pcs[uid]
        need(not state.dead and state.hp > 0, 'MAGIC_LIVING_CASTER_REQUIRED')
        now = ctx.world.runtime.clock()
        if request[0] == 'book':
            current = next((r for r in inventory.validate_kit_frame(ctx.inventory_frame)
                if r.identifier == request[1]), None)
            need(current is not None and current.template_bits == request[2]
                 and dict(current.raw_fields)[4] > 0, 'MAGIC_OWNED_POSITIVE_BOOK_REQUIRED')
            spell = ctx._world_magic.books[current.template_bits]
            learned = ctx._world_magic.learn(uid, spell, state.profile.character_class, state.profile.level)
            before = ctx.inventory_frame
            updated, wire = world_magic.book_mutation(before, current.identifier)
            proposed = ctx._world_magic.snapshot(uid, now, learned=learned)
            attempted = True
            # Books join two durable files. Reuse the existing boundary that
            # settles queued snapshots and makes inventory CAS synchronous.
            from tools.local_original_session.world_bridge import _flush_persist, _immediate_inventory
            _flush_persist(ctx.broker)
            _immediate_inventory(ctx.broker, 1)
            try:
                ctx._world_magic_store.learn(proposed, before, updated)
            finally:
                _immediate_inventory(ctx.broker, -1)
            ctx.inventory_frame = updated
            ctx._world_magic.state(uid).learned = learned
            ctx.run_sync_hooks('magic_learning_changed', uid)
            ctx.world._queue(uid, wire)
            ctx.world._queue(uid, available_frame(learned))
            ctx._world_magic_events.append(dict(uid=uid, key=spell.key, spell=spell.name,
                outcome='learned', book_uid=current.identifier, at=now))
            del ctx._world_magic_events[:-64]
        else:
            # admit/target failures must remain harmless; persistence exceptions
            # after an MP debit must reach the owner rather than claim refusal.
            before, hp_before = state.mp, state.hp
            resource_before = getattr(ctx, '_world_magic_resource_commits', 0)
            try:
                ctx._world_magic_cast(uid, request[1], request[2], now, row=row, game=game)
            finally:
                attempted = (state.mp != before or state.hp != hp_before
                    or getattr(ctx, '_world_magic_resource_commits', 0) != resource_before)
        return tuple(ctx.world.drain(uid))
    try:
        frames = await ctx.world.runtime.dispatch_now(apply)
    except ValueError as error:
        if attempted:
            raise
        ctx._world_magic_errors = (ctx._world_magic_errors + [str(error)[:96]])[-8:]
        return True
    await ctx._world_send(writer, row, frames, operation_lock)
    return True


METHODS = (_world_magic_initialize, _world_magic_started, _world_magic_save,
    _world_magic_learned_spells,
    _world_magic_npc_swing,
    _world_magic_consumable_provider,
    _world_magic_service, _world_magic_buff_target,
    _world_magic_cancel_target,
    _world_magic_tick, _world_magic_stats, _world_magic_weight_capacity, _world_magic_select_element,
    _world_magic_speed_factors,
    _world_magic_item_weight, _world_magic_enter, _world_magic_detach,
    _world_magic_weapon_uid, _world_magic_armor_uid,
    _world_magic_combat_profile, _world_magic_apply_poison,
    _world_magic_set_invisible, _world_magic_poison_tick,
    _world_magic_sync_invisible,
    _world_magic_replay_invisible,
    _world_magic_sync_feedback, _world_magic_replay_feedback,
    _world_magic_sync_icons, _world_magic_after_relocate,
    _world_magic_after_request, _world_magic_after_leave, _world_magic_stopped,
    _world_magic_died, _world_magic_display, _world_magic_cast, _world_magic_frame)
HOOKS = {'stats_modifiers': ('_world_magic_stats',),
    'speed_factors': ('_world_magic_speed_factors',),
    'magic_cast_display': ('_world_magic_display',),
    'character_learned_spells': ('_world_magic_learned_spells',),
    'elf_element_selected': ('_world_magic_select_element',),
    'consumable_magic_provider': ('_world_magic_consumable_provider',),
    'magic_service': ('_world_magic_service',),
    'cancel_magic_target': ('_world_magic_cancel_target',),
    'weight_capacity': ('_world_magic_weight_capacity',), 'item_weight': ('_world_magic_item_weight',),
    'initialize': ('_world_magic_initialize',), 'runtime_started': ('_world_magic_started',),
    'after_enter': ('_world_magic_enter',), 'after_request': ('_world_magic_after_request',),
    'after_relocate': ('_world_magic_after_relocate',),
    'after_leave': ('_world_magic_after_leave',), 'after_death': ('_world_magic_died',),
    'runtime_stopped': ('_world_magic_stopped',)}
FRAMES = {CAST: ('_world_magic_frame',), 0x0960: ('_world_magic_frame',)}
OUTGOING_OPCODES = (AVAILABLE, 0x4e91, 0x4e31, 0x4ed8, 0x4eeb, 0x4f03, 0x4f04, 0x4f05)
