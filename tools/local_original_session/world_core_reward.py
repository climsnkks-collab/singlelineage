"""World core: reward. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_original_session.world_bridge import need


def _world_progress_for(self, uid):
    try:
        return self._world_progress.get(uid)
    except Exception as error:  # unreadable sidecar: baseline values, never a session failure
        self._world_progress_errors = (self._world_progress_errors + [type(error).__name__])[-4:]
        return None


def _world_save_progress(self, uid):
    dirty = self._world.progress.pending(uid)
    if dirty is None:
        return
    try:
        self._world_progress.commit(uid, dirty)
        self._world.progress.ack(uid, dirty)
    except Exception as error:  # the next kill retries with the newer value
        self._world_progress_errors = (self._world_progress_errors + [type(error).__name__])[-4:]


def _world_pickup_commit(self, writer, item, count):
    """Synchronous durable insert of a picked ground item into the M1 kit row.

    Same saved kit row and send lane as the kit potion (replace_kit): a
    stackable template already held gets SC0965 with the new absolute count,
    anything else is appended as a new ItemInfo with SC0964 (outer f2 false =
    append; run30/run41, M1_REWARD_PACKETS 2(4)). Adena is template 7.
    Runs under the world lock, before the ground item is consumed.
    """
    from tools.local_original_session import inventory, inventory_update, world_visibility
    from tools.local_original_session.game_data import load_m1
    current = self.inventory_frame
    store = getattr(self, '_inventory_store', None)
    need(type(current) is bytes and store is not None
         and getattr(self, '_inventory_kit_policy', None) == inventory.KIT_POLICY,
         'WORLD_PICKUP_KIT_INVENTORY_REQUIRED')
    uid = self._world_pcs[id(writer)][1]
    items = inventory.validate_kit_frame(current)
    rows = [dict(member.raw_fields) for member in items]
    held = next((fields for fields in rows if fields[2] & 0xffffffff == item.item_id), None)
    if item.stackable and held is not None:
        held[4] += count
        need(held[4] <= (1 << 31) - 1, 'WORLD_PICKUP_STACK_LIMIT')
        wire = inventory_update._encode(inventory_update._values({1: held[1], 4: held[4]}))
    else:
        need(len(rows) < inventory.KIT_MAX_ITEMS, 'WORLD_PICKUP_INVENTORY_FULL')
        fields = dict(self.starter_fields)  # same 17 explicit raw fields as the kit rows
        definition = load_m1().items.get(item.item_id)
        icon = definition.icon if definition is not None else world_visibility.item_gfx()[item.item_id][0]
        fields.update({1: max(member.identifier for member in items) + 1, 2: item.item_id,
                       4: count, 7: icon})
        rows.append(fields)
        wire = inventory.build_add(fields)
    # Saved kit row up to inventory.KIT_MAX_FRAME (delivered as split 0964 frames);
    # the bag limit is KIT_MAX_ITEMS (L1J 180) above: a full bag keeps the drop.
    try:
        new_frame = inventory.build_kit_frame(rows)
    except ValueError as error:
        if error.args != ('INVENTORY_COLLECTION_FRAME_SIZE',):
            raise
        raise ValueError('WORLD_PICKUP_INVENTORY_FULL') from None
    need(store.replace_kit(uid, current, new_frame, append=True) is True,
         'WORLD_PICKUP_PERSISTED_CHANGE_REQUIRED')
    self.inventory_frame = new_frame
    return (wire,)


async def _world_pickup(self, writer, row, game, frame, operation_lock):
    """CS4E3E on a world ground drop. False = not ours (original transfer route)."""
    from tools.local_original_session import item_transfer_protocol
    bound = self._world_pcs.get(id(writer))
    if bound is None or bound[0] is not writer or self._world_ready(writer, game) is None:
        return getattr(self, '_item_transfer_broker', None) is None
    try:
        request = item_transfer_protocol.parse_get_payload_prevalidated(frame.payload)
    except ValueError:
        return getattr(self, '_item_transfer_broker', None) is None
    event = self._world_events.get(bound[1])
    if event is not None:
        event.clear()

    def commit(item, count):
        return self._world_pickup_commit(writer, item, count)
    try:
        frames = await self._world.runtime.dispatch_now(
            self._world.pc_pickup, bound[1], request.uid, request.quantity, commit)
    except ValueError as error:  # inventory insert refused: the item stays on the ground
        self._world_pickup_errors = (self._world_pickup_errors + [str(error)[:64]])[-4:]
        if event is not None:
            event.set()
        return True
    if frames is None:
        if event is not None:
            event.set()
        return getattr(self, '_item_transfer_broker', None) is None
    if any(int.from_bytes(wire[2:4], 'little') in (0x0964, 0x0965) for wire in frames):
        self._world_pickups += 1
    await self._world_send(writer, row, frames, operation_lock)
    return True


METHODS = (
    _world_progress_for,
    _world_save_progress,
    _world_pickup_commit,
    _world_pickup,
)
FRAMES = {0x4e3e: ('_world_pickup',)}


def setup_progress(self, store_path):
    from tools.local_original_session import inventory_update, item_transfer_protocol, world_progress
    self._world_progress = world_progress.ProgressStore(store_path)
    self.world.progress.attach_store(self._world_progress)
    self.realm._world_progress = self._world_progress_for
    inventory_update.source_ready()  # 0965 pickup quantity frames: contract once
    item_transfer_protocol.source_ready()  # 4E3E pickup request: contract once



def _world_reward_initialize(self):
    setup_progress(self, self.world_options['store_path'])

METHODS += (_world_reward_initialize,)
HOOKS = {'initialize': ('_world_reward_initialize',)}
