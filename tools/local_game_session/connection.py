"""Drop-in prepared bootstrap_connection hook, without changing frozen brokers."""
import asyncio, inspect, time
from pathlib import Path
import importlib.util, sys

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_operational_game_session', HERE / 'session.py')
session = importlib.util.module_from_spec(_spec);sys.modules[_spec.name] = session
_spec.loader.exec_module(session)

def connection_handler(base, registry, *, grant_own=None):
    """Pass prepared.base plus Registry; use this callable at accepted-peer launch.

    Register the actual writer object only after local OwnSession admission.
    Merely completing VERSION/COUNTS does not register/authenticate a guest.
    """
    async def serve(reader, writer, port, trace, decoder_factory, conversation_factory,
                    guard, wipe, scope, first=None, owner_guard=None, policy=None):
        reason = 'eof';received = frames = 0;sent = 1 if first is not None else 0
        decoder = decoder_factory();summary = trace.endpoints[port];deadline = time.monotonic() + 120
        conversation = None;game = None

        def fixed_guard():
            guard();scope.check()

        async def owner_required(opcode):
            allowed = False
            try:
                if first is not None and owner_guard is not None:
                    answer = owner_guard(dict(first['peer']))
                    if inspect.isawaitable(answer):
                        answer = await asyncio.wait_for(answer, 1.5)
                    allowed = answer is True
            finally:
                trace.emit({'event': 'owner_admission', 'endpoint_port': port,
                            'opcode': opcode, 'allowed': allowed, 'monotonic_ns': time.monotonic_ns()})
            session.need(allowed, 'CURRENT_OWNER_REQUIRED')
            fixed_guard()

        async def send(replies, *, game_reply=False):
            nonlocal sent
            for wire in replies:
                try:
                    session.need(type(wire) in (bytes, bytearray) and 6 <= len(wire) <= 65535,
                                 'SOURCE_REPLY_BOUND')
                    opcode = int.from_bytes(wire[2:4], 'little')
                    session.need(int.from_bytes(wire[:2], 'little') == len(wire) and wire[-2:] == b'\0\0',
                                 'SOURCE_REPLY_FRAME')
                    if game_reply:
                        # No ACK3,026B,world value or response order is invented.
                        decoded = session.wire.validate_frame(wire)
                        session.need(decoded.kind in ('NUM', 'INFO'), 'WORLD_OR_ACK_REPLY_UNBOUND')
                        session.need(sent < 132, 'OWN_ROSTER_REPLY_BOUND')
                    else:
                        session.need(sent < 3 and opcode == (0x4e20, 0x4e35, 0x4f3e)[sent], 'SOURCE_REPLY_SEQUENCE')
                        session.need(opcode != 0x4e20 or wire == base.KEY12, 'SOURCE_KEY12')
                        session.need(opcode != 0x4e35 or (type(wire) is bytearray and len(wire) == 76), 'SOURCE_VERSION38')
                        session.need(opcode != 0x4f3e or wire == b'\x06\0\x3e\x4f\0\0', 'SOURCE_EMPTY_COUNTS')
                    fixed_guard()
                    if game_reply or first['peer']['connection_id'] in (3, 4):
                        await owner_required(opcode)
                    writer.write(wire);await asyncio.wait_for(writer.drain(), 2)
                    sent += 1
                    trace.emit({'event': 'reply_sent', 'endpoint_port': port, 'opcode': opcode, 'frame_size': len(wire)})
                    if opcode == 0x4f3e:summary['counts_ack_sent'] = True
                finally:wipe(wire)

        def emit(row):
            # Reuse the existing metadata filter; never record bodies/references.
            from tools.local_entry_server.cli import safe_event
            safe = safe_event(row)
            if safe:trace.emit({**safe, 'endpoint_port': port})

        try:
            if first is None:
                first = base.write_first_key(writer, port, trace, scope);sent = 1
            await asyncio.wait_for(writer.drain(), 2)
            timing = base.Trace.validate_timing({'schema': 'lc-local-key-timing-v1',
                'connection_id': first['peer']['connection_id'], 'endpoint_port': port,
                'accepted_monotonic_ns': first['peer']['accepted_monotonic_ns'],
                'write_started_monotonic_ns': first['write_started_monotonic_ns'],
                'drain_completed_monotonic_ns': time.monotonic_ns()})
            trace.emit({'event': 'reply_sent', 'endpoint_port': port, 'opcode': 0x4e20, 'frame_size': 12})
            trace.emit({'event': 'key_drained', 'endpoint_port': port, 'key_timing': timing, 'monotonic_ns': timing['drain_completed_monotonic_ns']})
            conversation = conversation_factory(emit)
            opened = await conversation.opened()
            session.need(len(opened) == 1 and opened[0] == base.KEY12, 'FIXED_PINNED_KEY_CONVERSATION')
            while time.monotonic() < deadline:
                fixed_guard()
                raw = await asyncio.wait_for(reader.read(4096), min(15, max(.001, deadline - time.monotonic())))
                if not raw:
                    decoder.finish()
                    summary.update(frames=frames, received_bytes=received, sent_frames=sent, close_reason=reason)
                    if policy:policy.eof(port)
                    break
                received += len(raw);session.need(received <= 65536, 'INPUT_BYTE_BOUND')
                for frame in decoder.feed(raw):
                    frames += 1;session.need(frames <= 16, 'GAME_REQUEST_FRAME_BOUND')
                    trace.emit({'event': 'frame_decoded', 'endpoint_port': port, 'opcode': frame.opcode, 'frame_size': frame.wire_length})
                    if not getattr(conversation, 'ack_prepared', False):
                        await send(await conversation.received(frame))
                    else:
                        # Actual third+ parsed frames now enter the owned
                        # dispatcher instead of unconditional subset closure.
                        await owner_required(frame.opcode)
                        if id(writer) not in registry._sessions:
                            session.need(grant_own is not None, 'OWN_REGISTRATION_HOOK_REQUIRED')
                            # Only the current literal-True owner reaches this;
                            # fixed_guard above checked the retained Source.
                            granted = grant_own(writer, dict(first['peer']))
                            if inspect.isawaitable(granted):
                                await granted
                        game = registry.resolve(writer)
                        await send(await game.received(frame), game_reply=True)
            else:reason = 'session_timeout'
        except asyncio.CancelledError:reason = 'cancelled';raise
        except (OSError, TimeoutError):reason = 'io_failed_or_timeout'
        except (ValueError, RuntimeError):reason = 'source_or_protocol_refused'
        finally:
            registry.close(writer)
            try:decoder.finish()
            except ValueError:pass
            writer.close();positive_close = False
            try:await asyncio.wait_for(writer.wait_closed(), 2);positive_close = True
            except (OSError, TimeoutError, asyncio.CancelledError):pass
            summary.update(frames=frames, received_bytes=received, sent_frames=sent, close_reason=reason)
            if policy:
                if positive_close:policy.closed(port)
                else:policy.failed_close(port)
            trace.emit({'event': 'disconnected', 'endpoint_port': port, 'reason': reason,
                        'received_bytes': received, 'monotonic_ns': time.monotonic_ns()})
    return serve

class OwnedGameAdapter:
    """Concrete local admission/storage hook for the prepared broker callsite."""
    def __init__(self, roster_config, *, source_guard, on_selection=None):
        session.need(callable(source_guard), 'APPROVED_SOURCE_GUARD_REQUIRED')
        # Complete explicit fields are checked before any stream can reply.
        session.prepare_roster(roster_config)
        self.roster_config = roster_config
        self.source_guard = source_guard
        self.on_selection = on_selection
        self.registry = session.Registry()

    def grant(self, writer, peer):
        self.source_guard()
        return self.registry.register_own(writer, self.roster_config, on_selection=self.on_selection)

    def bootstrap_connection(self, base):
        return connection_handler(base, self.registry, grant_own=self.grant)
