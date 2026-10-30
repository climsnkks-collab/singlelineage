"""Optional Solid Carriage/Counter Barrier, fixed official rules + LOCAL L1J.

Ordinary NPC physical entry only. MonsterSkills._physical is a separate,
currently unconnected consumer (43 default species can use that path).
No NPC lifetime, HP, reward, inventory or timed-buff state is duplicated here.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.local_original_session import inventory, world_combat, world_enchant_inventory
from tools.local_original_session.world_bridge import need

POLICY = 'LOCAL_L1J_KNIGHT_SKILLS'
POLICIES = {
    89: dict(kind='evasion', local_reuse_seconds=3, l1j_skill=90,
             uncancelable=True),
    90: dict(kind='counter_barrier', local_reuse_seconds=1, l1j_skill=91,
             bind_weapon=True, probability_base=20, uncancelable=True),
}


def solid_bonus(level):
    """Official89: 40..49 +15, 50 +20, 51..55 +1/level, cap +25."""
    return 15 if level < 50 else min(25, 20 + level - 50)


def knight_er(level, dexterity, original_dexterity):
    # L1KnightClassFeature38/132; L1PcInstance1550-1554. Java / truncates.
    original = 3 if original_dexterity >= 16 else 1 if original_dexterity >= 14 else 0
    return level // 4 + int((dexterity - 8) / 2) + original


def counter_chance(knight_level, npc_level, original_intelligence=8):
    # SQL skill91 probability20; L1Magic296-302 + KnightClassFeature137.
    original_hit = 2 if original_intelligence >= 12 else 1 if original_intelligence >= 10 else 0
    return 20 + max(0, int((knight_level - max(60, npc_level)) / 4)) + 2 * original_hit


def counter_damage(weapon, enchant):
    # L1Attack1527-1538; no STR, random die, or ordinary melee spell bonuses.
    return max(0, (weapon.dmg_large + enchant + weapon.dmg_bonus) * 2)


def _knight_magic_policies(ctx, policies):
    return {**policies, **POLICIES}


def _service(ctx):
    return next((value for value in ctx.collect_sync_hooks('magic_service')
                 if value is not None), None)


def _equipment(ctx, uid):
    """Read the mandatory equipment/kit owner, including actual item enchant."""
    effect = getattr(ctx, '_item_equipment_effect', None)
    if effect is None:
        return None
    selected, frame = effect.store.peek(uid)
    if selected is None or frame is None or not selected.weapon_uid:
        return None
    member = next((row for row in inventory.validate_kit_frame(frame)
                   if row.identifier == selected.weapon_uid and dict(row.raw_fields)[4] > 0), None)
    weapon = None if member is None else ctx.world.data.items.get(member.template_bits)
    if weapon is None or weapon.kind != 'weapon' or weapon.weapon_type != 'twohand':
        return None
    return selected.weapon_uid, weapon, world_enchant_inventory.enchant_level(member, weapon)


def _knight_cast_admit(ctx, uid, spell, target, now):
    if spell.key == 90:
        need(_equipment(ctx, uid) is not None, 'KNIGHT_WORN_TWO_HANDED_SWORD_REQUIRED')


def _remove_counter(ctx, uid, service):
    state = service.engine.states.get(uid)
    if state is not None and 90 in state.buffs:
        del state.buffs[90]
        state.weapon_uids.pop(90, None)
        service.sync_icons(uid, ctx.world.runtime.clock())
        service.save(uid)


def _knight_equipment_changed(ctx, uid):
    service = _service(ctx)
    if service is None:
        return
    state = service.engine.states.get(uid)
    if state is None or 90 not in state.buffs:
        return
    equipped = _equipment(ctx, uid)
    if equipped is None or state.weapon_uids.get(90) != equipped[0]:
        # L1EquipmentSlot160: removing/replacing the weapon ends CB, even 2h->2h.
        _remove_counter(ctx, uid, service)


def _knight_inventory_changed(ctx, writer, row):
    bound = ctx._world_pcs.get(id(writer))
    if bound is not None:
        _knight_equipment_changed(ctx, bound[1])


def _original(ctx, uid):
    writer = next((writer for writer, selected in ctx._world_pcs.values() if selected == uid), None)
    if writer is None:
        return None
    position = ctx.realm.service(writer).snapshot()
    # Creation owner before permanent/stat/equipment folds: original DEX/INT.
    return ctx.realm.store.select(position.name)[1]


def _knight_initialize(ctx):
    world = ctx.world
    data = json.loads((Path(__file__).parent / 'data/m1/knight_skills.json').read_text(encoding='utf-8'))
    ctx._knight_npc_policy = {int(key): row for key, row in data['npcs'].items()}
    ctx._knight_events = []

    def physical(monster, uid, npc_ref, now):
        service = _service(ctx)
        if service is None:
            return None
        magic, state = service.engine, world.combat.pcs.get(uid)
        target = world.entities.get(uid)
        attacker = None if npc_ref is None else world.entities.resolve(npc_ref)
        found = None if attacker is None else world.spawner.slot_for(attacker.uid)
        if (state is None or state.profile.character_class != 1 or state.dead or state.hp <= 0 or target is None or not target.alive
                or attacker is None or not attacker.alive or attacker.map_id != target.map_id
                or found is None or not found[0].active or found[1].hp <= 0):
            return None
        carriage = magic.active(uid, 'evasion', now)
        barrier = magic.active(uid, 'counter_barrier', now)
        distance = max(abs(attacker.x-target.x), abs(attacker.y-target.y))
        metadata = ctx._knight_npc_policy.get(monster.l1j_npcid)
        short = distance <= 1 or metadata is not None and metadata['bow_action'] <= 0
        original = _original(ctx, uid)
        if original is None:
            return None
        if barrier:
            _knight_equipment_changed(ctx, uid)
            equipped = _equipment(ctx, uid)
            if (magic.active(uid, 'counter_barrier', now) and equipped is not None and short
                    and world.combat.rng.randint(1, 100) <= counter_chance(state.profile.level, monster.level, original[16])):
                damage = counter_damage(equipped[1], equipped[2])
                # Normal shared HP/death/reward owner; no second hit or reward.
                if damage > 0:
                    world._apply_monster_swing(uid, uid, attacker, monster, found[1].hp,
                                              world_combat.Swing(True, damage), now)
                # The caller publishes the real incoming miss. Do not invent a
                # reverse PC swing: L1J actionCounterBarrier uses NPC damage GFX.
                ctx._knight_events.append(dict(kind='counter', uid=uid, npc_uid=attacker.uid,
                    npc_ref=repr(npc_ref), damage=damage, at=now, policy=POLICY))
                del ctx._knight_events[:-32]
                return world_combat.Swing(False, 0)
        if metadata is None or metadata['ranged'] < 10 or distance < 2:
            return None
        swing = world_combat.npc_hits_pc(monster, state.profile, world.combat.rng)
        if not swing.landed:
            return swing
        bonus = solid_bonus(state.profile.level) if carriage else 0
        er = knight_er(state.profile.level, state.profile.dexterity, original[12]) + bonus
        avoided = world.combat.rng.randint(1, 100) <= er
        ctx._knight_events.append(dict(kind='evasion', uid=uid, npc_uid=attacker.uid,
            er=er, bonus=bonus, avoided=avoided, at=now, policy=POLICY))
        del ctx._knight_events[:-32]
        return world_combat.Swing(False, 0) if avoided else swing

    ctx._knight_handles = []
    def subscribe(event, callback):
        ctx._knight_handles.append((event, world.events.add('knight_skills', event, callback)))
    subscribe('npc_physical_swing', physical)
    # A changed persisted weapon can arrive through kit refresh or stats refresh.
    subscribe('tick', lambda now: [
        _knight_equipment_changed(ctx, uid) for uid in tuple(world.combat.pcs)])
    subscribe('close', ctx._knight_events.clear)


def _knight_stopped(ctx):
    for event, handle in ctx._knight_handles:
        ctx.world.events.remove(event, handle)
    ctx._knight_handles = []


def _knight_started(ctx):
    if not ctx._knight_handles:
        _knight_initialize(ctx)


def _knight_report(ctx, result):
    result['knight_skills'] = dict(policy=POLICY, events=list(ctx._knight_events),
        scope='ordinary npc_swing physical; MonsterSkills._physical NOT connected',
        cancellation='LOCAL L1SkillUse174-176 uncancelable; cancel ingress unavailable',
        original_magic_hit='saved creation INT: >=12 +2, >=10 +1, else0',
        presentation='normal incoming miss/death; native NPC counter damage GFX unverified')


METHODS = (_knight_magic_policies, _knight_cast_admit, _knight_initialize,
           _knight_inventory_changed, _knight_equipment_changed, _knight_report,
           _knight_stopped, _knight_started)
HOOKS = {'magic_runtime_policies': ('_knight_magic_policies',),
         'spell_cast_admit': ('_knight_cast_admit',),
         'initialize': ('_knight_initialize',),
         'runtime_started': ('_knight_started',),
         'runtime_stopped': ('_knight_stopped',),
         'inventory_changed': ('_knight_inventory_changed',),
         'stats_changed': ('_knight_equipment_changed',),
         'report': ('_knight_report',)}
NONCRITICAL_HOOKS = ('report',)
