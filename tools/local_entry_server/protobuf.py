"""Bounded protobuf wire0/wire2 tools for the verified initial message schemas.

No field names, defaults, auth behavior, or response ordering are inferred here.
Parsed values are ephemeral and excluded from repr/metadata. Groups and fixed
wire types are unsupported until a message contract needs and proves them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


class WireError(ValueError):
    """Only constant error codes; never attach input or field values."""


@dataclass(frozen=True, slots=True)
class WireLimits:
    max_body: int = 65524
    max_fields: int = 128
    max_field_bytes: int = 65524

    def __post_init__(self):
        if (type(self.max_body) is not int or not 0 <= self.max_body <= 65524 or
                type(self.max_fields) is not int or not 1 <= self.max_fields <= 1024 or
                type(self.max_field_bytes) is not int or not 0 <= self.max_field_bytes <= self.max_body):
            raise ValueError("invalid_wire_limits")


def _field_number(number: int):
    if type(number) is not int or not 1 <= number < (1 << 29):
        raise WireError("invalid_field_number")


def encode_varint(value: int) -> bytes:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise WireError("varint_value_range")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _varint(data: memoryview, offset: int) -> tuple[int, int]:
    value = 0
    for index in range(10):
        if offset >= len(data):
            raise WireError("truncated_varint")
        octet = data[offset]
        offset += 1
        if index == 9 and octet > 1:
            raise WireError("varint_overflow")
        value |= (octet & 0x7F) << (7 * index)
        if octet < 0x80:
            return value, offset
    raise WireError("varint_overflow")


def encode_uint32(number: int, value: int) -> bytes:
    _field_number(number)
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise WireError("uint32_value_range")
    return encode_varint(number << 3) + encode_varint(value)


def encode_bool(number: int, value: bool) -> bytes:
    _field_number(number)
    if type(value) is not bool:
        raise WireError("bool_value_type")
    return encode_varint(number << 3) + bytes([int(value)])


def encode_bytes(number: int, value: bytes | bytearray | memoryview,
                 *, limits: WireLimits | None = None) -> bytes:
    _field_number(number)
    limits = limits or WireLimits()
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise WireError("bytes_value_type")
    view = _byte_view(value)
    try:
        if len(view) > limits.max_field_bytes:
            raise WireError("field_byte_limit")
        result = encode_varint((number << 3) | 2) + encode_varint(len(view)) + bytes(view)
    finally:
        view.release()
    if len(result) > limits.max_body:
        raise WireError("body_byte_limit")
    return result


def encode_message(fields: Sequence[bytes], *, limits: WireLimits | None = None) -> bytes:
    limits = limits or WireLimits()
    if not isinstance(fields, (tuple, list)) or len(fields) > limits.max_fields:
        raise WireError("field_count_limit")
    total = 0
    for item in fields:
        if not isinstance(item, bytes):
            raise WireError("encoded_field_type")
        total += len(item)
        if total > limits.max_body:
            raise WireError("body_byte_limit")
    return b"".join(fields)


@dataclass(frozen=True, slots=True)
class WireField:
    number: int
    wire_type: int
    encoded_length: int
    value_length: int
    value: int | memoryview = field(repr=False)

    def metadata(self) -> dict[str, int]:
        return {"field_number": self.number, "wire_type": self.wire_type,
                "encoded_length": self.encoded_length, "value_length": self.value_length}


class ParsedMessage:
    """Context-managed borrowed byte views; repr contains metadata only."""
    def __init__(self, fields: tuple[WireField, ...], source: memoryview):
        self.fields = fields
        self._source = source
        self._closed = False

    def __repr__(self):
        return f"ParsedMessage(field_count={len(self.fields)}, closed={self._closed})"

    def metadata(self) -> tuple[dict[str, int], ...]:
        return tuple(item.metadata() for item in self.fields)

    def occurrences(self, number: int) -> tuple[WireField, ...]:
        if self._closed:
            raise WireError("message_closed")
        return tuple(item for item in self.fields if item.number == number)

    def close(self):
        if not self._closed:
            for item in self.fields:
                if isinstance(item.value, memoryview):
                    item.value.release()
            self._source.release()
            self._closed = True

    def __enter__(self):
        if self._closed:
            raise WireError("message_closed")
        return self

    def __exit__(self, *_):
        self.close()


def _byte_view(value) -> memoryview:
    try:
        return memoryview(value).cast("B")
    except (ValueError, TypeError):
        raise WireError("unsupported_buffer_layout") from None


def parse_message(body: bytes | bytearray | memoryview, *,
                  schema: Mapping[int, int] | None = None,
                  limits: WireLimits | None = None) -> ParsedMessage:
    """Preserve repeated/order information; state policy belongs to its contract.

    When schema is supplied it is a field-number -> verified-wire-type allowlist.
    Unknown fields/types fail closed rather than silently inventing semantics.
    """
    limits = limits or WireLimits()
    if not isinstance(body, (bytes, bytearray, memoryview)):
        raise WireError("body_value_type")
    if schema is not None:
        for number, wire_type in schema.items():
            _field_number(number)
            if wire_type not in (0, 2):
                raise WireError("unsupported_schema_wire_type")
    source = _byte_view(body)
    if len(source) > limits.max_body:
        source.release()
        raise WireError("body_byte_limit")
    parsed = []
    offset = 0
    try:
        while offset < len(source):
            if len(parsed) >= limits.max_fields:
                raise WireError("field_count_limit")
            start = offset
            tag, offset = _varint(source, offset)
            number, wire_type = tag >> 3, tag & 7
            _field_number(number)
            if wire_type not in (0, 2):
                raise WireError("unsupported_wire_type")
            if schema is not None:
                if number not in schema:
                    raise WireError("unknown_field_number")
                if schema[number] != wire_type:
                    raise WireError("field_wire_type_mismatch")
            if wire_type == 0:
                value_start = offset
                value, offset = _varint(source, offset)
                value_length = offset - value_start
            else:
                count, offset = _varint(source, offset)
                if count > limits.max_field_bytes:
                    raise WireError("field_byte_limit")
                if count > len(source) - offset:
                    raise WireError("truncated_length_delimited_field")
                value = source[offset:offset + count]
                offset += count
                value_length = count
            parsed.append(WireField(number, wire_type, offset - start, value_length, value))
        return ParsedMessage(tuple(parsed), source)
    except Exception:
        for item in parsed:
            if isinstance(item.value, memoryview):
                item.value.release()
        source.release()
        raise
