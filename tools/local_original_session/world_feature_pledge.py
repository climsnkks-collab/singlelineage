"""Optional single-account pledges. Remove its registry entry to omit routing.

No companion feature calls or runtime state are used. Offline same-account
membership is held only in CharacterStore's optional pledge data. Protocol and
policy evidence, plus native UI limits, are recorded in PLEDGE.md.
"""
from __future__ import annotations

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import world_pledge as pledge
from tools.local_original_session.world_bridge import need


def _pledge_initialize(ctx):
    ctx._pledge_events = []


def _pledge_record(ctx, uid, opcode, status):
    ctx._pledge_events = (ctx._pledge_events + [dict(uid=uid,
        opcode=f'{opcode:04X}', status=status)])[-16:]


def _pledge_frames(ctx, uid):
    value = ctx.realm.store.pledges()
    clan = pledge.membership(value, uid)
    characters = {identifier: info for identifier, info in ctx.realm.store.pledge_characters()}
    return pledge.info_frames(clan, characters)


def _pledge_magic_target_relation(ctx, source_uid, target_uid, relation):
    """Read actual durable membership; common ownership alone is no pledge."""
    if relation != 'pledge':
        return False
    value = ctx.realm.store.pledges()
    clan = pledge.membership(value, source_uid)
    return clan is not None and target_uid in clan['members']


async def _pledge_after_enter(ctx, writer, row, game, operation_lock):
    position = ctx.realm.service(writer).snapshot()
    # Empty membership is communicated by the native INFO empty-name path.
    frames = _pledge_frames(ctx, position.uid)
    await ctx._world_send(writer, row, frames, operation_lock)


async def _pledge_request(ctx, writer, row, game, frame, operation_lock):
    if not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False
    position = ctx.realm.service(writer).snapshot()
    uid = position.uid
    requested_name = ''

    def apply():
        nonlocal requested_name
        need(ctx.selected_session(writer) is game and ctx.owner_current(writer, row, position),
             'PLEDGE_CURRENT_SELECTED_PC_REQUIRED')
        values = pledge.parse_request(frame.opcode, frame.payload)
        requested_name = values.get(1, '')
        if frame.opcode == pledge.INFO:
            return _pledge_frames(ctx, uid)
        if frame.opcode == pledge.LIST:
            return (pledge.list_frame(ctx.realm.store.pledges(), values[1],
                ctx.realm.store.pledge_characters()),)
        pledge.need(not ctx.world.combat.is_dead(uid), 'PLEDGE_LIVING_PC_REQUIRED')
        if frame.opcode == pledge.CREATE:
            _, info = ctx.realm.store.select(position.name)
            def replace(identifier, before, after):
                changed = ctx._world_replace_kit(identifier, before, after)
                if changed:
                    # Publish immediately after its durable CAS. A failure of
                    # the following character write must retain this new kit,
                    # allowing the same normal CREATE to finish without cost.
                    ctx.inventory_frame = after
                return changed
            _, _, cost = pledge.create(ctx.realm.store, uid=uid, name=values[1],
                character_class=info[3], level=ctx.world.progress.snapshot(uid).level,
                current_frame=ctx.inventory_frame, replace_kit=replace)
            ctx.run_sync_hooks('inventory_changed', writer, row)
            return (cost, pledge.create_frame(True, values[1]), *_pledge_frames(ctx, uid))
        value = ctx.realm.store.pledges()
        if frame.opcode == pledge.JOIN:
            clan = next((v for v in value['clans'] if v['name'] == values[1]), None)
            pledge.need(clan is not None, 'PLEDGE_UNKNOWN_NAME')
            ctx.realm.store.pledge_enroll_character(clan['leader_uid'], uid)
            return (pledge.join_frame(True, clan['name']), *_pledge_frames(ctx, uid))
        if frame.opcode == pledge.LEAVE:
            clan = pledge.membership(value, uid)
            pledge.need(clan is not None, 'PLEDGE_MEMBERSHIP_REQUIRED')
            pledge.need(values[1] == clan['name'], 'PLEDGE_CURRENT_NAME_REQUIRED')
            ctx.realm.store.update_pledges(lambda v: pledge.leave(v, uid))
            return (pledge.leave_frame(True), *_pledge_frames(ctx, uid))
        ctx.realm.store.update_pledges(lambda v: pledge.notice(v, uid, values[1]))
        return (pledge.notice_frame(values[1]), *_pledge_frames(ctx, uid))

    try:
        frames = await ctx.world.runtime.dispatch_now(apply)
    except (pledge.Refused, pb.WireError, UnicodeError) as error:
        _pledge_record(ctx, uid, frame.opcode, str(error)[:96])
        frames = pledge.refusal_frames(frame.opcode, name=requested_name, reason=str(error))
    else:
        _pledge_record(ctx, uid, frame.opcode, 'saved' if frame.opcode not in
            (pledge.INFO, pledge.LIST) else 'read')
    await ctx._world_send(writer, row, frames, operation_lock)
    return True


def _pledge_report(ctx, result):
    value = ctx.realm.store.pledges()
    result['pledge'] = dict(events=list(ctx._pledge_events),
        clans=[dict(id=clan['id'], name=clan['name'], members=len(clan['members']))
               for clan in value['clans']], pending_creation=value['pending_creation'] is not None)


def _pledge_save_boundary(owner, args):
    return len(args) > 3 and args[3].opcode in (pledge.CREATE, pledge.JOIN, pledge.LEAVE, pledge.NOTICE)


METHODS = (_pledge_initialize, _pledge_record, _pledge_frames, _pledge_after_enter,
           _pledge_request, _pledge_report, _pledge_magic_target_relation)
HOOKS = {'initialize': ('_pledge_initialize',), 'after_enter': ('_pledge_after_enter',),
         'report': ('_pledge_report',),
         'magic_target_relation': ('_pledge_magic_target_relation',)}
FRAMES = {opcode: ('_pledge_request',) for opcode in
          (pledge.CREATE, pledge.JOIN, pledge.INFO, pledge.LEAVE, pledge.NOTICE, pledge.LIST)}
OUTGOING_OPCODES = (0x071C, 0x070A, 0x0723, 0x0724, 0x0716, 0x072B, 0x071F)
SAVE_BOUNDARIES = {'_pledge_request': _pledge_save_boundary}
