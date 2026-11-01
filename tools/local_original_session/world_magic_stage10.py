"""Advance Spirit's numeric contribution to the existing resource projection.

Official: maximum HP/MP +20%. LOCAL: L1SkillUse.java2854-2860 uses base
maxima /5 (integer floor), excluding equipment; it never refills current HP/MP.
The core retains base/effective maxima and owns clamp/save/recalculation.
"""


def resource_bonuses(ctx, value, uid, *, base):
    if not ctx._world_magic.active(uid, 'advance_spirit', ctx.world.runtime.clock()):
        return value
    hp, mp = base
    return value[0] + hp // 5, value[1] + (0 if mp is None else mp // 5)


def realm_status(realm, fields, position, initial):
    """Restore Advance before initial SelfInfo clamps saved current resources.

    All data comes from the existing magic/vitals owners. No new save schema or
    resource cache; absent/expired Advance leaves other spells' entry untouched.
    """
    if not initial:
        return fields
    ctx = realm._world_context
    engine, store = ctx._world_magic, ctx._world_magic_store
    uid, now = position.uid, ctx.world.runtime.clock()
    if uid not in engine.states and store is not None:
        row = store.rows.get(uid)
        if row is not None and any(buff['spell'] == 78 for buff in row['buffs']):
            engine.restore(uid, row, now)
    if not engine.active(uid, 'advance_spirit', now):
        return fields
    result = dict(fields)
    hp, mp = realm._world_hp(uid), realm._world_mp(uid)
    if hp is not None and hp > 0:
        result[10] = hp
    if mp is not None and mp >= 0:
        result[12] = mp
    return result
