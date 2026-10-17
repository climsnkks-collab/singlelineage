"""Directional plaintext frame inspection. This module creates no game replies.

The caller must select the cipher-pointer layout explicitly. No live cipher
state, handshake, sequence agreement, or original-client compatibility is inferred.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct
from typing import Literal, Protocol


class FrameError(ValueError):
    """Fixed diagnostic code only; never include input bytes in exceptions."""


@dataclass(frozen=True, slots=True)
class Frame:
    payload: bytes = field(repr=False)
    opcode: int
    wire_length: int
    sequence: int | None = field(default=None, repr=False)
    trailer_length: int = 0


class Decoder(Protocol):
    @property
    def buffered_bytes(self) -> int: ...
    def feed(self, chunk: bytes) -> tuple[Frame, ...]: ...
    def finish(self) -> None: ...


class ObserveDecoder:
    """No retained content and no packet-count inference from TCP chunks."""
    @property
    def buffered_bytes(self) -> int:
        return 0

    def feed(self, chunk: bytes) -> tuple[Frame, ...]:
        return ()

    def finish(self) -> None:
        return None


class _BufferedDecoder:
    def __init__(self, *, max_frame: int, max_buffer: int):
        if not 6 <= max_frame <= 65537 or not max_frame <= max_buffer <= 1 << 20:
            raise ValueError("invalid_decoder_limits")
        self.max_frame = max_frame
        self.max_buffer = max_buffer
        self._buffer = bytearray()

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def finish(self) -> None:
        if self._buffer:
            self._buffer.clear()
            raise FrameError("incomplete_frame_at_eof")

    def _fail(self, reason: str):
        self._buffer.clear()
        raise FrameError(reason)

    def feed(self, chunk: bytes) -> tuple[Frame, ...]:
        if len(self._buffer) + len(chunk) > self.max_buffer:
            self._fail("frame_buffer_limit")
        self._buffer.extend(chunk)
        frames = []
        while len(self._buffer) >= 2:
            declared = struct.unpack_from("<H", self._buffer)[0]
            total = self._total(declared)
            if total < self._minimum:
                self._fail("declared_frame_too_short")
            if total > self.max_frame:
                self._fail("declared_frame_limit")
            if len(self._buffer) < total:
                break
            # Content stays in the codec/handler; metadata logging is separate.
            data = bytes(self._buffer[:total])
            del self._buffer[:total]
            frames.append(self._parse(data))
        return tuple(frames)


class ClientPlaintextDecoder(_BufferedDecoder):
    """C2S header10: null total=declared+2; present-disabled total=declared."""
    _minimum = 10

    def __init__(self, *, cipher_pointer: Literal["null", "present_disabled"] = "null",
                 max_frame: int | None = None, max_buffer: int = 131074):
        if cipher_pointer not in ("null", "present_disabled"):
            raise ValueError("unsupported_cipher_pointer_mode")
        if max_frame is None:
            max_frame = 65537 if cipher_pointer == "null" else 65535
        super().__init__(max_frame=max_frame, max_buffer=max_buffer)
        self.cipher_pointer = cipher_pointer

    def _total(self, declared: int) -> int:
        return declared + 2 if self.cipher_pointer == "null" else declared

    def _parse(self, data: bytes) -> Frame:
        sequence, opcode, payload_length = struct.unpack_from("<IHH", data, 2)
        limit = 65527 if self.cipher_pointer == "null" else 65524
        if payload_length > limit:
            self._fail("payload_length_limit")
        unpadded = 10 + payload_length
        expected = unpadded if self.cipher_pointer == "null" else ((unpadded + 1) & ~3) + 2
        if len(data) != expected:
            self._fail("payload_length_mismatch")
        return Frame(data[10:10 + payload_length], opcode, len(data), sequence,
                     len(data) - unpadded)


class ServerPlaintextDecoder(_BufferedDecoder):
    """S2C inspection: declared is total; final2 bytes have unknown meaning.

    A minimum6 is required here for a complete opcode and trailer. The original
    receive path's behavior on shorter malformed frames is not reproduced.
    """
    _minimum = 6

    def __init__(self, *, max_frame: int = 65535, max_buffer: int = 131070):
        super().__init__(max_frame=max_frame, max_buffer=max_buffer)

    def _total(self, declared: int) -> int:
        return declared

    def _parse(self, data: bytes) -> Frame:
        opcode = struct.unpack_from("<H", data, 2)[0]
        return Frame(data[4:-2], opcode, len(data), trailer_length=2)
