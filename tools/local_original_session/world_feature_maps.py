"""World feature: maps. Existing packet/store operations, unchanged."""
from __future__ import annotations

from tools.local_entry_server.codecs import Frame
from tools.local_original_session import movement
from tools.local_original_session.world_bridge import need
from tools.local_original_session.world_item_effects import WorldItemEffects, movement_requirements


class GludinItemEffects(WorldItemEffects):
    """Keep existing item effects, selecting map4's explicit LOCAL return town."""

    def __init__(self, previous, policy):
        super().__init__(previous.combat, previous.terrain,
                         definitions=previous.definitions, rng=previous.rng)
        self.map_policy = policy

    def use(self, uid, template_id, now, *, position=None, ailments=None):
        from dataclasses import replace
        result = super().use(uid, template_id, now, position=position, ailments=ailments)
        if (position is not None and position.map_id == 4 and result.kind == 'return_town'
                and result.destination is not None):
            destination = self.map_policy.town_return
            return replace(result, destination=destination,
                           requirements=movement_requirements(position.map_id, destination))
        return result


def _world_maps_initialize(self):
    self._world_gludin = None
    if self._world_map_exp != 2:
        return
    from tools.local_original_session.world_maps import load_gludin_policy
    self._world_gludin = load_gludin_policy()
    # Explicit preload: no deferred terrain reads during movement/requests.
    for map_id in (1, 2, 4):
        self._world.terrain.bounds(map_id)
    self._world_item_effects = GludinItemEffects(self._world_item_effects, self._world_gludin)


def _world_maps_death(self, uid):
    if self._world_map_exp != 2 or self._world_gludin is None:
        return
    entity = self._world.entities.get(uid)
    if entity is not None and entity.map_id == 4:
        # Existing life owner saves this pending return at reselect/cleanup.
        # No living relocation, death ACK, new save format or forced revival.
        self._world_relocations[uid] = self._world_gludin.town_return


async def _world_enter_ship(self, writer, row, game, frame, operation_lock):
    """run397 C2S4EF8 schema; MapExp2-only direct harbor LOCAL experiment.

    f1 is an opaque client portal value: no assertion that it is ShipInfo1/2.
    No unsupported START4F0E, voyage timer or ship-interior voyage is used.
    """
    if self._world_map_exp != 2 or not self._world_bound(writer):
        return False
    if self._world_ready(writer, game) is None:
        return False
    from tools.local_original_session import inventory, world_handlers
    from tools.local_original_session.world_bridge import ack
    pb = ack.realm.pb
    context = world_handlers.HostContext(self.broker, writer, row, game, operation_lock)

    def transfer():
        with pb.parse_message(frame.payload, limits=pb.WireLimits(
                max_body=32, max_fields=1, max_field_bytes=16)) as parsed:
            fields = parsed.occurrences(1)
            need(len(fields) == 1 and len(parsed.fields) == 1 and fields[0].wire_type == 0,
                 'BOAT_REQUIRED_I32_PORTAL')
            raw = fields[0].value
            need(raw <= 0x7fffffff or 0xffffffff80000000 <= raw <= 0xffffffffffffffff,
                 'BOAT_REQUIRED_I32_PORTAL')
        position = self.realm.service(writer).snapshot()
        need(self.owner_current(writer, row, position), 'WORLD_MAP_CURRENT_OWNER_REQUIRED')
        state = self._world.combat.pcs[position.uid]
        need(not state.dead and state.hp > 0, 'BOAT_LIVING_PC_REQUIRED')
        route = self._world_gludin.boat_at(position.map_id, position.word0, position.word1)
        need(route is not None, 'BOAT_CURRENT_DOCK_REQUIRED')
        destination = route.destination
        need(self.realm.serves_map(destination.map_id)
             and self._world.terrain.can_stand(destination.map_id, destination.x, destination.y) is True,
             'WORLD_MAP_KNOWN_DESTINATION_REQUIRED')
        items = inventory.validate_kit_frame(self.inventory_frame)
        ticket = next((item for item in items if item.template_bits == route.ticket_id
                       and dict(item.raw_fields)[4] > 0), None)
        need(ticket is not None, 'BOAT_OWNED_TICKET_REQUIRED')
        for wire in self._world.drain(position.uid):
            context.send_frame(wire)
        context.commit_attempted = True
        context.send_frame(self._world_consume_kit(writer, ticket.identifier))
        for wire in self._world_relocate_locked(writer, row, game, destination, context=context):
            context.send_frame(wire)

    try:
        await self._world.runtime.dispatch_now(transfer)
    except (ValueError, pb.WireError) as error:
        if context.commit_attempted:
            raise
        self._world_handler_errors = (self._world_handler_errors + [str(error)[:96]])[-8:]
    await self._world_send(writer, row, tuple(context.frames), operation_lock)
    return True


def _world_edge_fallback(self, map_id, x, y, direction):
    """Player move whose client-memory edge was UNKNOWN: static mask1 terrain
    (world_terrain.can_step) plus a live world NPC standing on the target."""
    world = self._world
    if world is None or world.terrain is None:
        return None
    step = world.terrain.can_step(map_id, x, y, direction)
    if step is not True:
        return step
    from tools.local_original_session.world_entities import Kind
    from tools.local_original_session.world_terrain import DELTAS
    tx, ty = x + DELTAS[direction][0], y + DELTAS[direction][1]
    if any(entity.x == tx and entity.y == ty
           for entity in world.entities.near(map_id, tx, ty, 0, kind=Kind.NPC)):
        return False
    return True


async def _world_move_for_handler(self, writer, row, game, payload, now, context=None):
    """Inside the dispatcher world lock: original movement and committed view."""
    from tools.local_original_session.world_handlers import MovementResult
    service = self.realm.service(writer)
    prior = service.last_result
    if self._world_map_exp == 2:
        from tools.local_original_session.world_maps import resolve_transition

        def stair(position, x, y):
            policy = getattr(self, '_world_dungeon_policy', None)
            destination = resolve_transition(position.map_id, x, y,
                extra=None if policy is None else policy.transitions)
            if destination is None:
                return None
            return self._world_relocate_locked(writer, row, game, destination, context=context)

        service._world_step_transition = stair
    try:
        replies = await game.received(Frame(payload, 0x4e2b, len(payload) + 10))
    finally:
        if self._world_map_exp == 2:
            del service._world_step_transition
    result = service.last_result
    accepted = result is not None and result is not prior and result.get('accepted') is True
    position = service.snapshot()
    frames = self._world.update_pc_and_drain(position.uid, position.map_id,
                                            position.word0, position.word1)
    if accepted:
        await self.run_hooks('after_move', writer, row, game, row['operation_lock'])
    return MovementResult(bool(accepted), tuple(replies) + tuple(frames),
                          transitioned=bool(accepted and result.get('reason') == 'LOCAL_MAP_TRANSITION'))


async def _world_transition_for_handler(self, writer, row, game, destination, now, context=None):
    if self._world_map_exp != 2:
        code = 'MAP_TRANSITION_NATIVE_PUBLICATION_UNKNOWN'
        if code not in self._world_handler_errors:
            self._world_handler_errors = (self._world_handler_errors + [code])[-8:]
        return ()
    return self._world_relocate_locked(writer, row, game, destination, context=context)


def _world_relocate_locked(self, writer, row, game, destination, *, context=None,
                           same_map_correction=False):
    """run380/402 LOCAL candidates, under the row lock and world dispatch.

    1: same-map baseline; 2: dungeon/same-map; 3: same-map minus 4E95.
    1/3 use identical remove/reset/spawn operations. No readiness ACK/wait
    or 4EE0-as-teleport. Values/order are not verified original behavior.
    """
    service = self.realm.service(writer)
    position = service.snapshot()
    need(row['operation_lock'].locked()
         and self.realm.registry.resolve(writer) is game
         and self.owner_current(writer, row, position), 'WORLD_MAP_CURRENT_OWNER_REQUIRED')
    need(self.realm.serves_map(destination.map_id)
         and (destination.map_id == position.map_id or self._world_map_exp == 2)
         and self._world.terrain.can_stand(destination.map_id, destination.x, destination.y) is True,
         'WORLD_MAP_KNOWN_DESTINATION_REQUIRED')
    updated = movement.Position(position.uid, position.name, destination.map_id, destination.x, destination.y)
    world, uid = self._world, position.uid
    from tools.local_original_session.world_feature_companion import (
        _companion_relocate_depart, _companion_relocate_arrive)
    companion_travel = any(actor.owner_ref.uid == uid for actor in world.companions.active.values())
    if destination.map_id == position.map_id and (
            self._world_map_exp == 0 or same_map_correction or companion_travel):
        # run389 same-map LOCAL sequence. Keep MyPlayer and intersection
        # actors; refresh NPC/town/ground known sets and spawn-group interest.
        members = _companion_relocate_depart(self, uid)
        older = tuple(world.drain(uid))
        if context is not None:
            context.commit_attempted = True
        service.relocate(updated)
        service._actor_heading = destination.heading
        nearby = tuple(world.update_pc_and_drain(uid, updated.map_id, updated.word0, updated.word1))
        nearby += _companion_relocate_arrive(self, uid, members)
        removals = tuple(w for w in nearby if int.from_bytes(w[2:4], 'little') == 0x4e40)
        additions = tuple(w for w in nearby if int.from_bytes(w[2:4], 'little') != 0x4e40)
        if context is not None:
            context.begin_click()  # retire the old NPC menu/listing lifetime
        else:
            slot = row.get('_world_handler_state')
            if slot is not None:
                slot[1].clear()
                for source in slot[2]:
                    source.retired = True
                slot[2].clear()
        self._world_map_transitions += 1
        return older + removals + (movement.correction_frame(updated),) + additions
    state = world.combat.pcs[uid]
    fields = dict(state.status_fields)
    fields[10], fields[12] = state.hp, state.mp
    frames = self.realm._frames_for(updated, status_fields=fields, heading=destination.heading)
    map_frame, self_info, self_actor = frames
    members = _companion_relocate_depart(self, uid)
    old_known = set(world.visibility.known.get(uid, ())) | set(world.item_known.get(uid, ()))
    from tools.local_original_session.world_visibility import remove_frame
    removals = tuple(remove_frame(known) for known in sorted(old_known))
    older = tuple(world.drain(uid))
    if context is not None:
        context.commit_attempted = True
    service.relocate(updated)
    service._actor_heading = destination.heading
    self.realm._world_frames[id(writer)] = (updated, frames)
    nearby = tuple(world.update_pc_and_drain(uid, updated.map_id, updated.word0, updated.word1, reset=True))
    nearby += _companion_relocate_arrive(self, uid, members)
    if context is not None:
        context.begin_click()
    else:
        slot = row.get('_world_handler_state')
        if slot is not None:
            slot[1].clear()
            for source in slot[2]:
                source.retired = True
            slot[2].clear()
    self._world_map_transitions += 1
    first = () if self._world_map_exp == 3 else (map_frame,)
    # run402: 4E95 clears Actors. Publish the destination self Actor after
    # cleanup, with SelfInfo UID installed before its factory. 4EE0 cannot
    # replace this cross-map publication. Repeated SelfInfo and the surrounding
    # order remain LOCAL choices; f2=0 is still an UNKNOWN experiment operand.
    return older + removals + first + (self_info, self_actor) + nearby


METHODS = (
    _world_maps_initialize,
    _world_maps_death,
    _world_enter_ship,
    _world_edge_fallback,
    _world_move_for_handler,
    _world_transition_for_handler,
    _world_relocate_locked,
)

HOOKS = {'initialize': ('_world_maps_initialize',), 'after_death': ('_world_maps_death',)}
FRAMES = {0x4ef8: ('_world_enter_ship',)}


def realm_serves_map(realm, map_id):
    return map_id == 0 or (getattr(realm, '_world_map_exp', 0) == 2
        and map_id in (1, 2, 4, *getattr(realm, '_world_dungeon_maps', ())))


def realm_map_frame(realm, position, encode):
    # Existing run380 LOCAL map experiment: preserve required presence/values.
    if position.map_id != 0:
        return encode(0x4e95, {1: position.map_id, 2: 0, 3: False, 4: False})
    return realm.map_frame


def realm_dead_move(realm, service):
    dead = getattr(realm, '_world_is_dead', None)
    return dead is not None and dead(service.snapshot().uid)


async def realm_move(service, payload):
    stair = getattr(service, '_world_step_transition', None)
    return (await service.handle_CS4E2B(payload) if stair is None else
            await service.handle_CS4E2B(payload, transition=stair))
