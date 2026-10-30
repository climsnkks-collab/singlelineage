"""Optional native remembered places, saved on the selected character.

Protocol evidence: game-core-prep/BOOKMARK.md. Native child words are echoed
opaquely; LOCAL map/x/y production never accepts arbitrary client destinations.
Extensions and 4E41's unrelated coordinate-command contract remain unsupported.
"""
from __future__ import annotations

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, world_bookmark as bookmark
from tools.local_original_session.world_bridge import need


def _bookmark_initialize(ctx):
    ctx._bookmark_errors = []


def _bookmark_error(ctx, error):
    ctx._bookmark_errors = (ctx._bookmark_errors + [str(error)[:96]])[-8:]


async def _bookmark_after_enter(ctx, writer, row, game, operation_lock):
    position = ctx.realm.service(writer).snapshot()
    value = ctx.realm.store.bookmarks(position.uid)
    await ctx._world_send(writer, row, (bookmark.list_frame(value),), operation_lock)


async def _bookmark_request(ctx, writer, row, game, frame, operation_lock):
    if not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False
    written = False

    def apply():
        nonlocal written
        position = ctx.realm.service(writer).snapshot()
        need(ctx.selected_session(writer) is game and ctx.owner_current(writer, row, position)
             and not ctx.world.combat.is_dead(position.uid), 'BOOKMARK_LIVING_SELECTED_PC_REQUIRED')
        values = bookmark.parse_request(frame.opcode, frame.payload)
        if frame.opcode == bookmark.EXTEND:
            raise ValueError('BOOKMARK_EXTENSION_COST_AND_INCREMENT_UNKNOWN')
        if frame.opcode == bookmark.TELEPORT:
            raise ValueError('BOOKMARK_COORDINATE_COMMAND_UNSUPPORTED')
        if frame.opcode == bookmark.ADD:
            # LOCAL supported overworld scope. Active sieges have no runtime in
            # this backend; dungeon/ship/interior maps cannot be remembered.
            need(bookmark.location_allowed(position.map_id, remembering=True),
                 'BOOKMARK_LOCATION_NOT_MARKABLE')
            def transform(value):
                need(all(bookmark.opaque_triple(v) != (position.map_id, position.word0, position.word1)
                         for v in value['entries']), 'BOOKMARK_LOCATION_EXISTS')
                return bookmark.add(value, values[1], position.map_id, position.word0, position.word1)
        elif frame.opcode == bookmark.UPDATE:
            def transform(value):
                return bookmark.rename(value, values[2], values[1])
        else:
            def transform(value):
                return bookmark.delete(value, values[2], values[1])
        # Store failures propagate and must not emit a success-shaped list.
        def prepared(value):
            nonlocal written
            updated = transform(value)
            written = True
            return updated
        value = ctx.realm.store.update_bookmarks(position.uid, prepared)
        # Native UPDATE/DELETE already rename/remove their own map row after
        # sending. C371 belongs to BookmarkCrystalLayout, not this main list.
        if frame.opcode == bookmark.ADD:
            from copy import deepcopy
            added = deepcopy(value)
            added['entries'] = value['entries'][-1:]
            return (bookmark.list_frame(added),)
        return ()

    try:
        frames = await ctx.world.runtime.dispatch_now(apply)
    except (ValueError, UnicodeError, pb.WireError) as error:
        if written:
            raise
        _bookmark_error(ctx, error)
        return True
    await ctx._world_send(writer, row, frames, operation_lock)
    return True


async def _bookmark_item(ctx, writer, row, game, frame, operation_lock):
    if frame.opcode != 0x0960 or not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False
    # Inspect only outer UID first; malformed requests for unrelated items keep
    # their existing owner. This feature does not own another item's parser.
    try:
        with pb.parse_message(frame.payload) as parsed:
            ids = parsed.occurrences(1)
            if len(ids) != 1 or ids[0].wire_type != 0:
                return False
            identifier = ids[0].value
        current = next((v for v in inventory.validate_kit_frame(ctx.inventory_frame)
                        if v.identifier == identifier), None)
        if current is None or current.template_bits not in (23, bookmark.CRYSTAL_TEMPLATE):
            return False
        if current.template_bits == bookmark.CRYSTAL_TEMPLATE:
            # C371 opens a separate crystal list. Neither its server-side item
            # storage nor the read/write/consume request contract is recovered.
            # Claim this owned item only; never invent a main-list refresh or
            # pass it onward as an ordinary consumable.
            _bookmark_error(ctx, 'BOOKMARK_CRYSTAL_STORAGE_AND_USE_CONTRACT_UNKNOWN')
            return True
        identifier, selected = bookmark.parse_item_use(frame.payload)
    except (ValueError, pb.WireError) as error:
        _bookmark_error(ctx, error)
        return True
    # Ordinary raw0 uses preserve the existing random-teleport owner. Native
    # selected f8/9/10 uses need blessed scroll or an actually worn control ring.
    if selected is None:
        return False
    attempted = False

    def apply():
        nonlocal attempted
        from tools.local_original_session import world_enchant_inventory
        from tools.local_original_session.world_item_effects import MapDestination
        position = ctx.realm.service(writer).snapshot()
        need(ctx.selected_session(writer) is game and ctx.owner_current(writer, row, position)
             and not ctx.world.combat.is_dead(position.uid), 'BOOKMARK_LIVING_SELECTED_PC_REQUIRED')
        item = next((v for v in inventory.validate_kit_frame(ctx.inventory_frame)
                     if v.identifier == identifier), None)
        need(item is not None and item.template_bits == 23 and dict(item.raw_fields)[4] > 0,
             'BOOKMARK_OWNED_SCROLL_REQUIRED')
        grade = world_enchant_inventory.instance_grade(item)
        worn = () if grade == 0 else ctx._world_stats_for(position)[1]
        need(grade == 0 or grade == 1 and any(v.item.template_id == 64 for v in worn),
             'BOOKMARK_BLESSED_SCROLL_OR_WORN_CONTROL_RING_REQUIRED')
        value = ctx.realm.store.bookmarks(position.uid)
        matches = [v for v in value['entries'] if bookmark.opaque_triple(v) == selected]
        need(len(matches) == 1, 'BOOKMARK_CURRENT_SAVED_DESTINATION_REQUIRED')
        place = matches[0]
        # L1J's selected-bookmark path uses escapable, not random-teleportable.
        # LOCAL policy, before any consumption; no other feature state is read.
        need(bookmark.location_allowed(position.map_id), 'BOOKMARK_DEPARTURE_NOT_ESCAPABLE')
        need(place['map_id'] in (0, 4) and ctx.realm.serves_map(place['map_id'])
             and (place['map_id'] == position.map_id or ctx._world_map_exp == 2)
             and ctx.world.terrain.can_stand(place['map_id'], place['x'], place['y']) is True,
             'BOOKMARK_DESTINATION_UNAVAILABLE')
        destination = MapDestination(place['map_id'], place['x'], place['y'], 5)
        # Existing kit owner and core relocation retain consumption, storage,
        # visibility, companion transit, and any partial failure semantics.
        attempted = True
        cost = ctx._world_consume_kit(writer, identifier)
        transition = ctx._world_relocate_locked(writer, row, game, destination)
        return (*ctx.world.drain(position.uid), cost, *transition)

    try:
        frames = await ctx.world.runtime.dispatch_now(apply)
    except (ValueError, pb.WireError) as error:
        if attempted:
            raise
        _bookmark_error(ctx, error)
        return True
    await ctx._world_send(writer, row, frames, operation_lock)
    return True


def _bookmark_report(ctx, result):
    result['bookmark_errors'] = list(ctx._bookmark_errors)


def _bookmark_save_boundary(owner, args):
    if len(args) < 4 or args[3].opcode != 0x0960:
        return False
    try:
        identifier, selected = bookmark.parse_item_use(args[3].payload)
        return selected is not None and any(v.identifier == identifier and v.template_bits == 23
            for v in inventory.validate_kit_frame(owner._inventory_current_frame))
    except (ValueError, pb.WireError):
        return False


METHODS = (_bookmark_initialize, _bookmark_after_enter, _bookmark_request, _bookmark_item,
           _bookmark_report)
HOOKS = {'initialize': ('_bookmark_initialize',), 'after_enter': ('_bookmark_after_enter',),
         'pre_dispatch': ('_bookmark_item',), 'report': ('_bookmark_report',)}
FRAMES = {opcode: ('_bookmark_request',) for opcode in
          (bookmark.ADD, bookmark.UPDATE, bookmark.DELETE, bookmark.EXTEND, bookmark.TELEPORT)}
OUTGOING_OPCODES = (bookmark.ADD_NOTI,)
SAVE_BOUNDARIES = {'_bookmark_item': _bookmark_save_boundary}
