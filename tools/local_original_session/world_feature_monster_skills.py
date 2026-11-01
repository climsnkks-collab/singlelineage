"""Registration boundary for optional monster special actions."""
from tools.local_original_session.world_monster_skills import MonsterSkills, load_attacks


def _monster_skills_initialize(ctx):
    ctx._world_monster_skills = None
    ctx._world_monster_skills_attacks = load_attacks()
    ctx._world_monster_skills_events = []


def _monster_skills_started(ctx):
    previous = ctx._world_monster_skills
    if previous is not None:
        previous.close()
    provider = next((value for value in ctx.collect_sync_hooks('consumable_magic_provider')
                     if value is not None), None)
    def target(uid):
        return next((value for value in ctx.collect_sync_hooks('npc_magic_target', uid)
                     if value is not None), None)
    def cancel_target(uid):
        return next((value for value in ctx.collect_sync_hooks('cancel_magic_target', uid)
                     if value is not None), None)
    owner = MonsterSkills(ctx.world, ctx._world_monster_skills_attacks,
                          provider=provider, magic_target=target, cancel_target=cancel_target)
    ctx._world_monster_skills = owner
    ctx._world_monster_skills_events = owner.events
    owner.start()


def _monster_skills_haste_replaced(ctx, uid, now):
    owner, entity = ctx._world_monster_skills, ctx.world.entities.get(uid)
    if owner is not None and entity is not None:
        owner.haste.pop(entity.ref, None)


def _monster_skills_player_cancel(ctx, uid, now):
    owner, entity = ctx._world_monster_skills, ctx.world.entities.get(uid)
    if owner is not None and entity is not None:
        owner.haste.pop(entity.ref, None)
        owner.cure_poison(uid)
        ctx.world.events.emit('npc_speed_changed', entity.ref, now)


def _monster_skills_stopped(ctx):
    owner = ctx._world_monster_skills
    if owner is not None:
        owner.close()


def _monster_skills_cure_poison(ctx, uid):
    owner = ctx._world_monster_skills
    if owner is not None:
        owner.cure_poison(uid)


METHODS = (_monster_skills_haste_replaced, _monster_skills_player_cancel,
           _monster_skills_initialize, _monster_skills_started,
           _monster_skills_stopped, _monster_skills_cure_poison)
HOOKS = {'initialize': ('_monster_skills_initialize',),
         'player_cancel_magic': ('_monster_skills_player_cancel',),
         'magic_haste_replaced': ('_monster_skills_haste_replaced',),
         'runtime_started': ('_monster_skills_started',),
         'runtime_stopped': ('_monster_skills_stopped',),
         'cure_poison': ('_monster_skills_cure_poison',)}
