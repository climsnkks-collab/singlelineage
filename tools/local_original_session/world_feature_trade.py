"""run406 4EF5 GIVE to an owned Player companion; LOCAL auto equipment.

The two character rows remain ordinary inventory/equipment saves. A short-lived
intent uses the existing warehouse atomic writer solely to finish interrupted
two-row transfers forward. It is not a second bag or an exchange UI protocol.
"""

from tools.local_entry_server import protobuf as pb
from tools.local_original_session.world_bridge import need


# Public compatibility import; the inventory service is not owned by GIVE routing.
from tools.local_original_session.world_companion_inventory import CompanionInventory


async def _companion_give_frame(ctx, writer, row, game, frame, operation_lock):
    bags = next((value for value in ctx.collect_sync_hooks('give_provider')
                 if value is not None), None)
    if bags is None or not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False
    attempted = False
    bags.commit_started = False
    try:
        with pb.parse_message(frame.payload, limits=pb.WireLimits(max_body=128, max_fields=3,
                                                                max_field_bytes=128)) as message:
            need(len(message.fields) == 3 and all(len(message.occurrences(n)) == 1
                and message.occurrences(n)[0].wire_type == 0 for n in (1, 2, 3)),
                'COMPANION_GIVE_FIELDS_REQUIRED')
            target, item, count = (message.occurrences(n)[0].value for n in (1, 2, 3))
        need(0 < target < 1 << 32 and 0 < item < 1 << 32 and 0 < count < 1 << 64,
             'COMPANION_GIVE_RANGE_REQUIRED')
        uid = ctx._world_pcs[id(writer)][1]
        def apply():
            nonlocal attempted
            need(ctx.realm.registry.resolve(writer) is game
                 and ctx.owner_current(writer, row, ctx.realm.service(writer).snapshot())
                 and ctx.world.combat.can_be_attacked(uid), 'COMPANION_CURRENT_LIVING_OWNER_REQUIRED')
            actor = bags.owned_actor(uid, target)
            need(actor.character_id not in ctx.world.pcs, 'COMPANION_MEMBER_SELECTED')
            # Validation failures before the journal are ordinary refusals.
            wire = bags.give(uid, actor, item, count, ctx.inventory_frame)
            attempted = True
            return (wire, *ctx.world.drain(uid))
        frames = await ctx.world.runtime.dispatch_now(apply)
        await ctx._world_send(writer, row, frames, operation_lock)
    except (ValueError, pb.WireError) as error:
        if attempted or bags.commit_started or bags.intent_path.exists():
            raise
        bags.report_error(error)
    return True


METHODS = (_companion_give_frame,)
FRAMES = {0x4ef5: ('_companion_give_frame',)}
OUTGOING_OPCODES = (0x4ed5,)

SAVE_BOUNDARIES = {'_companion_give_frame': True}
