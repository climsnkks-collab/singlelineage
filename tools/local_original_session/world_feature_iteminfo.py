"""Fixed client item names and the source-confirmed direction notification.

4E2F is CS_CHANGE_DIRECTION_NOTI, not an item-information request. ItemInfo
f18 is the existing name string; 0977 reruns the native name/description
consumer without migrating inventory/equipment saves. Official server values
for extra descriptions are not fabricated here.
"""
from __future__ import annotations

from tools.local_entry_server import protobuf as pb

DIRECTION = 0x4E2F
DIRECTION_NOTICE = 0x4E2E
CHANGE_DESC = 0x0977


def decode_direction(payload: bytes) -> int:
    """Native schema 15EE458: required int32 f1; LOCAL normal heading 0..7."""
    with pb.parse_message(payload, limits=pb.WireLimits(
            max_body=32, max_fields=2, max_field_bytes=32)) as parsed:
        if (len(parsed.fields) != 1 or parsed.fields[0].number != 1
                or parsed.fields[0].wire_type != 0 or not 0 <= parsed.fields[0].value <= 7):
            raise ValueError('DIRECTION_SINGLE_NORMAL_HEADING_REQUIRED')
        return parsed.fields[0].value


def direction_notice(uid: int, direction: int) -> bytes:
    """SC schema 15EE4B0: required int32 UID/f1 and direction/f2."""
    if type(uid) is not int or not 0 < uid < (1 << 32):
        raise ValueError('DIRECTION_UID_REQUIRED')
    if type(direction) is not int or not 0 <= direction <= 7:
        raise ValueError('DIRECTION_NORMAL_HEADING_REQUIRED')
    signed_uid = uid if uid < (1 << 31) else uid - (1 << 32)
    body = (b'\x08' + pb.encode_varint(signed_uid & ((1 << 64) - 1))
            + b'\x10' + pb.encode_varint(direction))
    return (len(body) + 6).to_bytes(2, 'little') + b'\x2e\x4e' + body + b'\0\0'


def backend_descriptions(item, definition):
    """Compatibility entrypoint; the shared pure projection owns the tags."""
    from tools.local_original_session.inventory import backend_descriptions as project
    return project(item, definition)


def name_updates(items, names, known, definitions=None):
    """Existing ItemInfo rows -> normal 0977; preserve custom f18 names."""
    updates, current = [], {}
    for item in items:
        fields = dict(item.raw_fields)
        name = fields[18] or names.get(item.template_bits, b'')
        descriptions = backend_descriptions(item, (definitions or {}).get(item.template_bits))
        state = (name, fields[4], descriptions)
        current[item.identifier] = state
        if name and known.get(item.identifier) != state:
            updates.append(description_notice(item.identifier, name, fields[4], descriptions))
    return tuple(updates), current


def description_notice(uid: int, name: bytes, count: int, descriptions=()) -> bytes:
    """SC_CHANGE_ITEM_DESC_NOTI schema1604CF8; values stay source-owned.

    f2 must be supplied: the native consumer copies its empty default even
    when absent. f3/f5 are repeated ItemDescription; absence is kept when no
    source-owned per-instance description has been supplied.
    """
    if (type(uid) is not int or not 0 < uid < 1 << 32 or type(name) is not bytes
            or not name or len(name) > 256 or type(count) is not int or not 0 <= count < 1 << 64):
        raise ValueError('ITEMINFO_CURRENT_NAME_QUANTITY_REQUIRED')
    # 50A6B0 returns immediately when the quantity is unchanged. Its native
    # suffix is " (" + decimal Q + ")" for Q>1 (11C6E58/11AE9C4), so a full
    # name replacement must already include it. Keep canonical saved f18 bare.
    display = name + (b' (' + str(count).encode('ascii') + b')' if count > 1 else b'')
    body = b'\x08' + pb.encode_varint(uid) + pb.encode_bytes(2, display)
    from tools.local_original_session.inventory import description_body
    for token, value in descriptions:
        body += pb.encode_bytes(3, description_body(token, value))
    body += b'\x20' + pb.encode_varint(count)
    return (len(body) + 6).to_bytes(2, 'little') + CHANGE_DESC.to_bytes(2, 'little') + body + b'\0\0'


def _iteminfo_initialize(ctx):
    from tools.local_original_session.world_visibility import item_names
    ctx._iteminfo_names = item_names()
    ctx._iteminfo_errors = []
    _iteminfo_started(ctx)


def _iteminfo_started(ctx):
    # All optional features finish their startup catalog additions first.
    ctx._iteminfo_definitions = dict(ctx.world.data.items)
    # The core starter and ordinary grants must describe the same plain item.
    # Preserve explicit variant names so the existing resale checks still reject
    # unknown/enchant variants rather than treating every named starter as one.
    from dataclasses import replace
    policies = []
    for policy in ctx.item_policies.values():
        fields = policy.grant_fields
        name = ctx._iteminfo_names.get(policy.template_id)
        if fields is not None and not fields.get(18) and name:
            policies.append(replace(policy, grant_fields={**fields, 18: name},
                                    plain_names=tuple(dict.fromkeys((*policy.plain_names, b'', name)))))
    ctx.add_item_policies(policies, replace_existing=True)
    # Reuse the final startup catalog through the existing town owner API. A
    # BUY row describes the actual plain grant prototype, never a made-up UID
    # or an owned player's strengthened instance. This adds no request I/O.
    bindings = getattr(getattr(ctx, 'broker', None), '_world_handler_bindings', None)
    if bindings is not None and bindings.town is not None:
        from dataclasses import replace
        from types import MappingProxyType
        from tools.local_original_session import inventory
        from tools.local_original_session.world_shop_menu import MenuSource
        prepared = {}
        for template, policy in ctx.item_policies.items():
            if policy.grant_fields is not None:
                prototype = inventory.ItemInfo(tuple(sorted(policy.grant_fields.items())))
                prepared[template] = backend_descriptions(
                    prototype, ctx._iteminfo_definitions.get(template))
        descriptions = MappingProxyType(prepared)
        sources = tuple(replace(source, descriptions=descriptions)
                        if isinstance(source, MenuSource) else source
                        for source in bindings.sources.values())
        ctx.configure_town(bindings.town, sources, refresh_policies=False)


def _iteminfo_owner(ctx, writer, row, game):
    bound = getattr(ctx, '_world_pcs', {}).get(id(writer))
    if (ctx.world is None or bound is None or bound[0] is not writer
            or game is None or game.selection is None
            or ctx.selected_session(writer) is not game):
        return None
    service = ctx.realm.service(writer)
    position = service.snapshot()
    if service.fatal or not ctx.owner_current(writer, row, position):
        return None
    return position, service


async def _iteminfo_direction(ctx, writer, row, game, frame, operation_lock):
    if frame.opcode != DIRECTION or ctx.world is None:
        return False
    try:
        direction = decode_direction(frame.payload)

        def apply():
            owner = _iteminfo_owner(ctx, writer, row, game)
            if owner is None:
                raise ValueError('DIRECTION_CURRENT_SELECTED_OWNER_REQUIRED')
            position, service = owner
            pc = ctx.world.entities.get(position.uid)
            state = ctx.world.combat.pcs.get(position.uid)
            if pc is None or state is None or state.dead or state.hp <= 0:
                raise ValueError('DIRECTION_CURRENT_LIVING_PC_REQUIRED')
            # No movement, attack, save, item use or invented item-info ACK.
            pc.heading = direction
            service._actor_heading = direction
            notice = direction_notice(position.uid, direction)
            # Only clients to whom this same actor was actually published may
            # consume its UID. The current single-player view has no PC peer
            # spawn; this also supports an already-published observer safely.
            for observer in ctx.world.pcs:
                if (observer != position.uid and position.uid in
                        ctx.world.visibility.known.get(observer, ())):
                    ctx.world._queue(observer, notice)
            ctx.world._announce()

        await ctx.world.runtime.dispatch_now(apply)
    except (ValueError, pb.WireError) as error:
        ctx._iteminfo_errors = (ctx._iteminfo_errors + [str(error)[:96]])[-8:]
    return True


async def _iteminfo_display(ctx, writer, row, game, operation_lock):
    from tools.local_original_session import inventory
    # Display is optional in unit/headless entry contexts that have no real
    # transport claim. A real row still goes through the existing owner check.
    if (not {'policy_row', 'writer', 'joined', 'failed'} <= row.keys()
            or row.get('operation_lock') is not operation_lock):
        return
    if (getattr(ctx, '_inventory_kit_policy', None) != inventory.KIT_POLICY
            or _iteminfo_owner(ctx, writer, row, game) is None
            or type(ctx.inventory_frame) is not bytes):
        return
    # current_frame is installed only after the initial 0964 drain. If manual
    # inventory admission follows after_enter, after_request completes this.
    before = ctx.inventory_frame
    if row.get('_iteminfo_frame') is before:
        return
    items = inventory.validate_kit_frame(before)
    frames, names = name_updates(items, ctx._iteminfo_names, row.get('_iteminfo_names', {}),
                                getattr(ctx, '_iteminfo_definitions', {}))
    for start in range(0, len(frames), ctx.WORLD_SEND_CHUNK):
        chunk = frames[start:start + ctx.WORLD_SEND_CHUNK]
        await ctx.send(writer, row, chunk, game=True, operation_lock=operation_lock,
                       world_operation=chunk)
    # Record only after drain; partial failures retain the owner's send error.
    row['_iteminfo_frame'], row['_iteminfo_names'] = before, names


async def _iteminfo_after_request(ctx, writer, row, game, opcode, operation_lock):
    await _iteminfo_display(ctx, writer, row, game, operation_lock)


async def _iteminfo_enter(ctx, writer, row, game, operation_lock):
    row.pop('_iteminfo_frame', None)
    row.pop('_iteminfo_names', None)
    await _iteminfo_display(ctx, writer, row, game, operation_lock)


async def _iteminfo_delivered(ctx, writer, row, game, operation_lock):
    # The initial 0964 is the world select's own follow-up: world-handled
    # requests skip after_request, so publish names right after its drain.
    await _iteminfo_display(ctx, writer, row, game, operation_lock)


def _iteminfo_kit_name(ctx, name, template_id):
    """Core starter kit fold: names are prepared at startup; keep an earlier name."""
    return name or getattr(ctx, '_iteminfo_names', {}).get(template_id, b'')


def _iteminfo_display_fields(ctx, fields, item):
    """Creation-time f19 for the original ItemEntity before UI metadata build.

    Later 0977 still refreshes the same owned item after state changes. Keep
    all display fields supplied by earlier hooks and preserve saved names.
    """
    name = fields.get(18) or getattr(ctx, '_iteminfo_names', {}).get(item.template_bits)
    if name:
        fields = {**fields, 18: name}
    descriptions = backend_descriptions(item,
        getattr(ctx, '_iteminfo_definitions', {}).get(item.template_bits))
    return {**fields, 19: descriptions} if descriptions else fields


METHODS = (_iteminfo_initialize, _iteminfo_direction, _iteminfo_display,
           _iteminfo_after_request, _iteminfo_enter, _iteminfo_started, _iteminfo_kit_name,
           _iteminfo_delivered, _iteminfo_display_fields)
HOOKS = {'initialize': ('_iteminfo_initialize',), 'after_enter': ('_iteminfo_enter',),
         'runtime_started': ('_iteminfo_started',),
         'after_request': ('_iteminfo_after_request',),
         'inventory_delivered': ('_iteminfo_delivered',),
         'inventory_display_fields': ('_iteminfo_display_fields',),
         'kit_item_name': ('_iteminfo_kit_name',)}
FRAMES = {DIRECTION: ('_iteminfo_direction',)}
OUTGOING_OPCODES = (DIRECTION_NOTICE, CHANGE_DESC)
NONCRITICAL_HOOKS = ('inventory_delivered',)  # a name notice never fails the inventory delivery
