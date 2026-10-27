"""World core: session. Existing packet/store operations, unchanged."""
from __future__ import annotations

import asyncio
from tools.local_game_session import session
from tools.local_original_session.world_bridge import need, RESTART_REQUEST, DEAD_RESTART_REQUEST


def _world_wake(self, pc_uid):
    event = self._world_events.get(pc_uid)
    if event is not None:
        event.set()


def _world_ready(self, writer, game):
    if (self._closing or self.failure.is_set() or game is None or game.selection is None
            or id(writer) not in self.realm._movement or id(writer) in self.realm._quit):
        return None
    service = self.realm.service(writer)
    return None if service.fatal else service


async def _world_send(self, writer, row, frames, operation_lock):
    for start in range(0, len(frames), self.WORLD_SEND_CHUNK):
        chunk = tuple(frames[start:start + self.WORLD_SEND_CHUNK])
        await self.send(writer, row, chunk, game=True, operation_lock=operation_lock,
                         world_operation=chunk)


def _world_bound(self, writer):
    bound = getattr(self, '_world_pcs', {}).get(id(writer))
    return (getattr(self, '_world', None) is not None and bound is not None and bound[0] is writer
            and self._world.combat.pcs.get(bound[1]) is not None)


async def _world_dispatch(self, writer, row, game, frame, operation_lock):
    from tools.local_original_session import world_handlers
    if await self.chain_hooks('pre_dispatch', writer, row, game, frame, operation_lock):
        return True
    if frame.opcode not in world_handlers.HANDLERS:
        return False
    if not self._world_bound(writer) or self._world_ready(writer, game) is None:
        return False
    uid = self._world_pcs[id(writer)][1]
    if self._world.combat.is_dead(uid):
        await self._world_flush(writer, row, game, operation_lock)
        return True
    context = world_handlers.HostContext(self.broker, writer, row, game, operation_lock)
    delivered = False
    try:
        handled = await self._world.runtime.dispatch_now(world_handlers.dispatch, context,
                                                          frame.opcode, frame.payload)
        if not handled:
            return False
        delivered = True
    except (world_handlers.HandlerError, ValueError) as error:
        if getattr(context, 'commit_attempted', False):
            raise  # ambiguous persistence is never turned into a harmless refusal
        self._world_handler_errors = (self._world_handler_errors + [str(error)[:96]])[-8:]
    # A failed optional stair publication must not discard the accepted move.
    await self._world_send(writer, row, tuple(context.frames), operation_lock)
    if delivered:
        context.mark_delivered()
    return True


async def _world_after_request(self, writer, row, game, opcode, operation_lock):
    """After a request: select/move/alive refresh the PC's screen; any request flushes queued world frames."""
    if (opcode in (RESTART_REQUEST, DEAD_RESTART_REQUEST) and game is not None
            and game.selection is None
            and self._world_pcs.get(id(writer), (None,))[0] is writer):
        # Restart back to character select: drop the PC, its known set and outbox;
        # the next select (0x4e28) binds and resets it again.
        await self._world_leave(writer)
        return
    service = self._world_ready(writer, game)
    if service is None:
        return
    position = service.snapshot()
    bound = self._world_pcs.get(id(writer))
    if opcode == 0x4e28:
        frame = self.realm.world_frames(writer)[1]  # the SC_STATUS this client just received
        status = session.world.decode_payload(0x4e38, frame[4:-2])
        saved = self._world_progress_for(position.uid)
        status[18] = status[18] if saved is None else saved.lawful
        await self.run_hooks('before_enter', writer, row, game, operation_lock)
        selected_exp = self.fold_sync_hooks('selected_exp', 0 if saved is None else saved.exp, position)
        exp_status = await self._world.runtime.dispatch_now(
            self._world.bind_pc, position.uid,
            self._world_pc_profile(writer, position, level=status[2]), status,
            selected_exp)
        self._world_events[position.uid] = asyncio.Event()
        self._world_names[position.uid] = position.name
    elif opcode not in self.WORLD_OPCODES:
        if bound is None or bound[0] is not writer:
            return
        await self._world_flush(writer, row, game, operation_lock)
        return
    event = self._world_events.get(position.uid)
    if event is not None:
        event.clear()  # before draining: a later tick sets it again
    frames = await self._world.runtime.dispatch_now(
        self._world.update_pc_and_drain, position.uid, position.map_id, position.word0,
        position.word1, reset=opcode == 0x4e28)
    if opcode == 0x4e28 and exp_status is not None:
        frames = [exp_status] + frames  # same full SC_STATUS plus the saved f26 EXP percent
    self._world_pcs[id(writer)] = (writer, position.uid)
    await self._world_send(writer, row, frames, operation_lock)
    if opcode == 0x4e28:
        await self.run_hooks('after_enter', writer, row, game, operation_lock)
    elif opcode == 0x4e2b:
        await self.run_hooks('after_move', writer, row, game, operation_lock)


async def _world_flush(self, writer, row, game, operation_lock):
    """Send world frames queued by ticks (AI, corpse removal, respawn) through _send."""
    bound = self._world_pcs.get(id(writer))
    if bound is None or bound[0] is not writer or self._world_ready(writer, game) is None:
        return
    event = self._world_events.get(bound[1])
    if event is not None:
        event.clear()
    frames = await self._world.runtime.dispatch_now(self._world.drain, bound[1])
    self._world_save_progress(bound[1])
    await self._world_send(writer, row, frames, operation_lock)


async def _world_leave(self, writer):
    bound = self._world_pcs.get(id(writer))
    if bound is not None and bound[0] is writer:
        self._world_save_progress(bound[1])
        await self.run_hooks('before_leave', writer, bound[1])
        self._world_pcs.pop(id(writer), None)
        self._world_events.pop(bound[1], None)
        row = next((row for rows in self._claims.values() for row in rows
                    if row['writer'] is writer), None)
        if row is not None:
            row.pop('_world_handler_state', None)
        try:
            dead = await self._world.runtime.dispatch_now(self._world.leave_pc, bound[1])
        except Exception:
            dead = False  # Writer cleanup continues; a stale PC only keeps its groups active.
        name = self._world_names.get(bound[1])
        if dead is True and name is not None:
            self._world_respawn[bound[1]] = name  # committed at reselect or writer cleanup
    try:
        await self.run_hooks('after_leave', writer)
    except Exception as error:
        self._world_progress_errors = (self._world_progress_errors + [str(error)[:96]])[-4:]
        self._fail('WORLD_LEAVE_FAILED')


METHODS = (
    _world_wake,
    _world_ready,
    _world_send,
    _world_bound,
    _world_dispatch,
    _world_after_request,
    _world_flush,
    _world_leave,
)
from tools.local_original_session.world_handlers import HANDLERS
FRAMES = {opcode: ('_world_dispatch',) for opcode in HANDLERS}
HOOKS = {'after_request': ('_world_after_request',)}


FRAME_PRIORITY = 10

def _dispatch_save_boundary(owner, args):
    from tools.local_original_session.world_handlers import TRADE
    return len(args) > 3 and args[3].opcode == TRADE

SAVE_BOUNDARIES = {'_world_dispatch': _dispatch_save_boundary, '_world_leave': True}


async def _world_attack(self, writer, row, game, frame, operation_lock):
    """CS4E30 on a world monster: immediate swing. False = not ours, keep the original route."""
    from tools.local_original_session import attack
    bound = self._world_pcs.get(id(writer))
    if bound is None or bound[0] is not writer or self._world_ready(writer, game) is None:
        return False
    try:
        request = attack.parse_payload(frame.payload)
    except ValueError:
        return False
    event = self._world_events.get(bound[1])
    if event is not None:
        event.clear()
    frames = await self._world.runtime.dispatch_now(self._world.pc_attack, bound[1],
                                                    request.target_uid)
    if frames is None:
        if event is not None:
            event.set()  # queued frames stay for the next flush
        # Not a world monster. Without the original attack route the request
        # has no handler; answer nothing instead of failing the session.
        return getattr(self, '_attack_session', None) is None
    self._world_save_progress(bound[1])  # kill reward: EXP/level saved before the status is sent
    await self._world_send(writer, row, frames, operation_lock)
    return True

METHODS += (_world_attack,)
FRAMES[0x4e30] = ('_world_attack',)
