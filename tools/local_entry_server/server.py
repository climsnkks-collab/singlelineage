"""Async loopback TCP transport with bounded resource use and safe metadata."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import json
import math
import socket
import struct
from typing import Awaitable, Callable, Sequence, TextIO

from .codecs import Decoder, Frame, FrameError, ObserveDecoder
from .handshake import HandshakeError
from .counts import ACK, CountsPlan, CountsSession, response_opcode_allowed


@dataclass(frozen=True, slots=True)
class Limits:
    read_chunk: int = 4096
    max_connections: int = 16
    max_session_bytes: int = 1 << 20
    max_session_frames: int = 4096
    max_reply_bytes: int = 65537
    max_session_reply_bytes: int = 1 << 20
    idle_timeout: float = 5.0
    session_timeout: float = 60.0
    handler_timeout: float = 2.0
    write_timeout: float = 2.0

    def __post_init__(self):
        for name in ("read_chunk", "max_connections", "max_session_bytes",
                     "max_session_frames", "max_reply_bytes", "max_session_reply_bytes"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 1 << 24:
                raise ValueError("invalid_server_limits")
        if self.read_chunk > 65537 or self.max_connections > 1024:
            raise ValueError("invalid_server_limits")
        for name in ("idle_timeout", "session_timeout", "handler_timeout", "write_timeout"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 < value <= 3600:
                raise ValueError("invalid_server_timeouts")


def loopback_host(host: str) -> str:
    """Literal addresses only: never perform DNS or bind wildcard interfaces."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("loopback_literal_required") from None
    if not address.is_loopback:
        raise ValueError("loopback_binding_required")
    return str(address)


class MetadataLog:
    """Fixed field allowlist, with no content, peers, sequences, or exceptions."""
    fields = frozenset({"session", "mode", "host", "port", "chunk_bytes", "wire_bytes",
                        "opcode", "reason", "received_bytes", "received_chunks",
                        "decoded_frames", "reply_bytes", "compatibility", "stage", "field_count",
                        "field_number", "wire_type", "encoded_length", "value_length"})

    def __init__(self, stream: TextIO | None = None, sink: Callable[[dict], None] | None = None):
        self.stream, self.sink = stream, sink

    def event(self, event: str, **values):
        if any(name not in self.fields for name in values):
            raise ValueError("unsupported_metadata_field")
        row = {"event": event, **values}
        if self.sink:
            self.sink(dict(row))
        if self.stream:
            self.stream.write(json.dumps(row, separators=(",", ":")) + "\n")
            self.stream.flush()


@dataclass(frozen=True, slots=True)
class Session:
    number: int
    mode: str


Handler = Callable[[Frame, Session], Awaitable[Sequence[bytes]]]


class LoopbackServer:
    def __init__(self, *, host: str = "127.0.0.1", port: int = 0,
                 decoder_factory: Callable[[], Decoder] = ObserveDecoder,
                 handler: Handler | None = None, mode: str = "observe",
                 limits: Limits | None = None, log: MetadataLog | None = None,
                 initial_plan: CountsPlan | None = None):
        self.host = loopback_host(host)
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid_port")
        if mode not in ("observe", "inspect_c2s_plaintext", "synthetic_fixture", "reviewed_counts"):
            raise ValueError("invalid_mode")
        if mode != "synthetic_fixture" and handler is not None:
            raise ValueError("inspection_and_observe_modes_do_not_reply")
        if mode == "observe" and decoder_factory is not ObserveDecoder:
            raise ValueError("observe_mode_does_not_decode_frames")
        if mode == "reviewed_counts":
            if not isinstance(initial_plan, CountsPlan) or self.host != '127.0.0.1':
                raise ValueError("reviewed_counts_requires_fixed_ipv4_loopback_and_plan")
            if decoder_factory is ObserveDecoder:
                raise ValueError("experimental_mode_requires_plaintext_decoder")
        elif initial_plan is not None:
            raise ValueError("conditional_plan_only_for_explicit_experimental_mode")
        self.initial_plan = initial_plan
        self.port, self.decoder_factory, self.handler, self.mode = port, decoder_factory, handler, mode
        self.limits, self.log = limits or Limits(), log or MetadataLog()
        self._server: asyncio.Server | None = None
        self._tasks: set[asyncio.Task] = set()
        self._active = 0
        self._accepted_total = 0
        self._next_session = 0

    @property
    def bound_port(self) -> int:
        if self._server is None:
            raise RuntimeError("server_not_started")
        return self._server.sockets[0].getsockname()[1]

    async def start(self):
        if self._server is not None:
            raise RuntimeError("server_already_started")
        listener = socket.socket(socket.AF_INET if ':' not in self.host else socket.AF_INET6, socket.SOCK_STREAM)
        try:
            # Windows exclusive bind prevents later reuse of this owned endpoint.
            # Never request SO_REUSEADDR or SO_REUSEPORT on any platform.
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((self.host, self.port))
            listener.listen(self.limits.max_connections)
            listener.setblocking(False)
            self._server = await asyncio.start_server(self._accept, sock=listener,
                limit=self.limits.read_chunk * 2, reuse_address=False, reuse_port=False)
        except BaseException:
            listener.close()
            raise
        self.log.event("listening", host=self.host, port=self.bound_port, mode=self.mode,
                       compatibility="pending_original_client_verification")
        return self

    def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        if self.mode == "reviewed_counts" and self._accepted_total >= 1:
            writer.close()
            self.log.event("connection_rejected", reason="experimental_connection_limit")
            return
        if self._active >= self.limits.max_connections:
            writer.close()
            self.log.event("connection_rejected", reason="connection_limit")
            return
        self._active += 1
        self._accepted_total += 1
        task = asyncio.create_task(self._connection(reader, writer))
        self._tasks.add(task)
        def completed(done):
            self._tasks.discard(done)
            self._active -= 1
        task.add_done_callback(completed)

    async def _connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._next_session += 1
        session = Session(self._next_session, self.mode)
        received = chunks = frames = replied = 0
        reason = "eof"
        try:
            decoder = self.decoder_factory()
            self.log.event("connected", session=session.number, mode=self.mode)
            deadline = asyncio.get_running_loop().time() + self.limits.session_timeout

            async def send_replies(replies):
                nonlocal reason, replied
                if not isinstance(replies, (tuple, list)):
                    reason = "invalid_handler_result"
                    return False
                for reply in replies:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        reason = "session_timeout"
                        return False
                    if not isinstance(reply, bytes) or not 0 < len(reply) <= self.limits.max_reply_bytes:
                        reason = "reply_limit"
                        return False
                    opcode = None
                    if self.mode == "reviewed_counts":
                        if not response_opcode_allowed(reply):
                            reason = "response_not_allowed"
                            return False
                        opcode = struct.unpack_from('<H', reply, 2)[0]
                    replied += len(reply)
                    if replied > self.limits.max_session_reply_bytes:
                        reason = "session_reply_limit"
                        return False
                    writer.write(reply)
                    write_session_capped = remaining <= self.limits.write_timeout
                    try:
                        await asyncio.wait_for(writer.drain(), min(self.limits.write_timeout, remaining))
                    except TimeoutError:
                        reason = "session_timeout" if write_session_capped else "write_timeout"
                        return False
                    metadata = dict(session=session.number, reply_bytes=len(reply))
                    if opcode is not None:
                        metadata["opcode"] = opcode
                    self.log.event("reply_sent", **metadata)
                    if opcode == ACK:
                        self.log.event('counts_ack_sent', session=session.number,
                            opcode=opcode, reply_bytes=len(reply), stage='counts_ack_written_not_game_processing_proof')
                return True

            conversation = CountsSession(self.initial_plan, session, self.log) if self.initial_plan else None
            if conversation is not None:
                remaining = deadline - asyncio.get_running_loop().time()
                opener_session_capped = remaining <= self.limits.handler_timeout
                try:
                    replies = await asyncio.wait_for(conversation.opened(), min(self.limits.handler_timeout, remaining))
                except TimeoutError:
                    reason = "session_timeout" if opener_session_capped else "handler_timeout"
                    return
                if not await send_replies(replies):
                    return
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    reason = "session_timeout"
                    break
                read_session_capped = remaining <= self.limits.idle_timeout
                try:
                    chunk = await asyncio.wait_for(reader.read(self.limits.read_chunk),
                                                    min(self.limits.idle_timeout, remaining))
                except TimeoutError:
                    reason = "session_timeout" if read_session_capped else "idle_timeout"
                    break
                if not chunk:
                    decoder.finish()
                    break
                received += len(chunk)
                chunks += 1
                if received > self.limits.max_session_bytes:
                    reason = "session_byte_limit"
                    break
                self.log.event("chunk_received", session=session.number, chunk_bytes=len(chunk))
                chunk_frames = decoder.feed(chunk)
                for frame in chunk_frames:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        reason = "session_timeout"
                        return
                    frames += 1
                    if frames > self.limits.max_session_frames:
                        reason = "session_frame_limit"
                        return
                    self.log.event("frame_decoded", session=session.number,
                                   wire_bytes=frame.wire_length, opcode=frame.opcode)
                    if self.handler is None and conversation is None:
                        continue
                    handler_session_capped = remaining <= self.limits.handler_timeout
                    try:
                        action = conversation.received(frame) if conversation else self.handler(frame, session)
                        replies = await asyncio.wait_for(action, min(self.limits.handler_timeout, remaining))
                    except TimeoutError:
                        reason = "session_timeout" if handler_session_capped else "handler_timeout"
                        return
                    if not await send_replies(replies):
                        return
                # Leave no last-frame payload reference between reads.
                if chunk_frames:
                    del frame
                del chunk_frames
                del chunk
        except HandshakeError as error:
            allowed = {"duplicate_session_start", "duplicate_or_out_of_order_message", "unexpected_opcode",
                       "malformed_client_version", "response_not_allowed", "bounded_handshake_completed",
                       "duplicate_client_version_field", "missing_required_client_version_fields",
                       "invalid_client_derived_scalar", "client_build_mismatch"}
            reason = error.args[0] if error.args and error.args[0] in allowed else "handshake_rejected"
        except FrameError as error:
            allowed = {"incomplete_frame_at_eof", "frame_buffer_limit", "declared_frame_too_short",
                       "declared_frame_limit", "payload_length_mismatch", "payload_length_limit"}
            reason = error.args[0] if error.args and error.args[0] in allowed else "invalid_frame"
        except asyncio.CancelledError:
            reason = "server_shutdown"
            raise
        except (ConnectionError, OSError):
            reason = "connection_closed"
        except Exception:
            # User-injected handler exception messages may contain secret input.
            reason = "handler_or_codec_failed"
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), self.limits.write_timeout)
            except (TimeoutError, ConnectionError, OSError):
                pass
            summary = dict(session=session.number, reason=reason, received_bytes=received,
                           received_chunks=chunks, reply_bytes=replied)
            if self.mode != "observe":
                summary["decoded_frames"] = frames
            self.log.event("disconnected", **summary)

    async def close(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def serve_forever(self):
        if self._server is None:
            raise RuntimeError("server_not_started")
        await self._server.serve_forever()
