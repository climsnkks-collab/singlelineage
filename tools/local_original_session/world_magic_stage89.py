"""Small adapters for the existing player-magic owners (Classic stages8/9).

No standalone feature, timer, HP ledger or companion dependency. Numeric
policies and their scope live in the source-attributed player_spells catalog.
"""
from tools.local_original_session.world_bridge import need
from tools.local_original_session.world_interest_spawn import SlotState


POTION_KINDS = frozenset(('heal', 'speed', 'mana_regen', 'cure_poison',
                          'wisdom', 'underwater_breath'))


def resurrection_target(ctx, uid, target, now, policy):
    """Admit a current corpse before cost; return its actual life-owner action."""
    view = ctx.world
    need(not target.alive, 'MAGIC_DEAD_TARGET_REQUIRED')
    # Autonomous actors keep their own ownership, save and AI; optional hooks
    # never turn their HP into a PlayerMagic/PC shadow value.
    for action in ctx.collect_sync_hooks('magic_resurrection_target', uid, target.uid):
        if action is not None:
            return action
    found = view.spawner.slot_for(target.uid)
    need(found is not None, 'MAGIC_RESURRECTION_PC_ACCEPTANCE_OR_NPC_OWNER_UNAVAILABLE')
    group, slot = found
    source = policy['npc_resurrection_reference'].get(str(group.monster.l1j_npcid))
    need(source is not None, 'MAGIC_NPC_RESURRECTION_RULE_UNKNOWN')
    need(not source['cant_resurrect'], 'MAGIC_NPC_CANNOT_RESURRECT')
    need(group.active and slot.state is SlotState.WAIT and slot.hp == 0
         and slot.corpse_at > now, 'MAGIC_CURRENT_NPC_CORPSE_REQUIRED')
    need(not any(e.uid != target.uid and e.alive and e.map_id == target.map_id
                 and (e.x, e.y) == (target.x, target.y) for e in view.entities),
         'MAGIC_CORPSE_TILE_OCCUPIED')
    ref = target.ref

    def apply(at):
        from tools.local_original_session.world_visibility import remove_frame
        watchers = tuple(view._watchers(target))
        entity = view.spawner.revive(ref, max(1, group.monster.hp // policy['revive_hp_divisor']), at)
        # The existing same-UID remove/spawn lane replaces the native corpse.
        for watcher in watchers:
            view._queue(watcher, remove_frame(entity.uid))
            view._queue(watcher, view._spawn_frame(entity))
        if view.ai is not None:
            view.ai.sync(at)
        view._announce()
        return view.spawner.slot_for(entity.uid)[1].hp
    return apply


def group_relocations(ctx, uid, caster, destination, radius):
    """Registered current group recipients, never an inference from proximity.

    PC party/clan membership has no native producer yet. Providers may return a
    current owner action; that owner retains its own row lock and save/wires.
    Ordinary companion/pet transit already runs in core relocation hooks.
    """
    from tools.local_original_session.npc_ai import distance
    members = {member for name in ('party_members', 'clan_members')
               for group in ctx.collect_sync_hooks(name, uid) for member in group}
    actions = []
    for member in sorted(members - {uid}):
        target = ctx.world.entities.get(member)
        if (target is None or not target.alive or target.map_id != caster.map_id
                or distance(caster.x, caster.y, target.x, target.y) > radius):
            continue
        action = next((a for a in ctx.collect_sync_hooks(
            'mass_teleport_recipient', uid, target.ref, destination) if a is not None), None)
        need(action is not None, 'MAGIC_GROUP_TELEPORT_RECIPIENT_OWNER_UNAVAILABLE')
        actions.append(action)
    return actions
