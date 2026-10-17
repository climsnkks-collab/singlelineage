"""One-shot, explicitly gated local key/version experiment.

This is a limited harness policy, not an auth server or a claim of native-client
compatibility. No entitlement messages, arbitrary replay, or request values are
used in responses. Pending version proof always means no version response.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import struct
from typing import TYPE_CHECKING

from .codecs import Frame
from .protobuf import WireError, encode_bool, encode_message, encode_uint32, parse_message

if TYPE_CHECKING:
    from .server import MetadataLog, Session

KEY_OPCODE = 0x4E20
CLIENT_VERSION_OPCODE = 0x4E34
SERVER_VERSION_OPCODE = 0x4E35
COMPLETION_OPCODE = 0x4F3D
CLIENT_FIELDS = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 2, 7: 0, 8: 0, 9: 0, 10: 0, 11: 2}
_PLAN_APPROVAL = object()
IGNORED_TRAILER_SEMANTICS = (
    "ignored_by_verified_receive_chain: L−6 payload copied to owned vector, L consumed, "
    "queued object exposes only opcode/vector; parser sees exactly this vector and length. "
    "Literal accumulator references have no extra reader; arbitrary alias paths outside "
    "this chain were not exhaustively modeled."
)


class HandshakeError(ValueError):
    """Constant status only; no message body or values in errors."""


def _require(condition):
    if not condition:
        raise ValueError("unsupported_conditional_response_contract")


@dataclass(frozen=True, slots=True)
class InitialPlan:
    version_response_allowed: bool
    _approval: object = field(default=None, repr=False)

    def __post_init__(self):
        if self._approval is not _PLAN_APPROVAL:
            raise ValueError("conditional_plan_not_validated")

    @classmethod
    def from_contract(cls, document: dict) -> "InitialPlan":
        """Called only after the base source/build/framing contract gate passes."""
        try:
            _require(document["source"]["sha256"] == "9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af")
            _require(document["source"]["version"] == "26.09.29.2001")
            s2c = document["framing"]["s2c"]
            _require(s2c["status"] == "verified_static" and s2c["endianness"] == "little")
            _require([(f["name"], f["offset"], f["width"]) for f in s2c["fields"]] == [
                ("declared_length", 0, 2), ("opcode", 2, 2),
                ("payload", 4, "max(declared_length - 6, 0)"),
                ("uninterpreted_final_bytes", "declared_length - 2", 2)])
            _require(s2c["wire_length"] == "declared_length" and s2c["decode_consumes"] == "declared_length")
            _require(s2c["minimum_supported_length"] == 6 and s2c["present_enabled_cipher"]["status"] == "unsupported")
            _require(s2c["uninterpreted_final_bytes_semantics"] == IGNORED_TRAILER_SEMANTICS)
            _require(s2c["controlled_local_encoding"]["trailer_hex"] == "0000")
            _require(s2c["controlled_local_encoding"]["official_trailer_value_known"] is False)
            config = document["conditional_responses"]
            _require(config["mode"] == "controlled_localhost_key_version")
            _require(config["status"] in ("key_only_static_ready", "static_ready"))
            _require(config["require_explicit_mode"] is True and config["bind_policy"] == "ipv4_loopback_only")
            trailer = config["trailer"]
            _require(trailer["policy"] == "ignored_by_verified_receive_chain")
            _require(trailer["local_value_hex"] == "0000" and trailer["official_value_known"] is False)
            key = config["SC_KEY_NOTI"]
            _require(key["status"] == "static_ready" and key["opcode"] == KEY_OPCODE and key["emit"] == "once_after_accept")
            _require(key["required_fields"] == [1, 2, 3] and key["expected_next_opcode"] == CLIENT_VERSION_OPCODE)
            fields = key["fields"]
            _require(set(fields) == {"1", "2", "3"})
            _require(type(fields["1"]) is int and fields["1"] == 0)
            _require(type(fields["2"]) is int and fields["2"] == 0 and fields["3"] is True)
            version = config["SC_SERVER_VERSION_INFO"]
            _require(version["opcode"] == SERVER_VERSION_OPCODE)
            allowed = version["status"] == "static_ready"
            if allowed:
                _require(config["status"] == "static_ready")
                _require(version["emit"] == "once_after_first_valid_CS_CLIENT_VERSION_INFO")
                _require(set(version["fields"]) == {"1"})
                _require(type(version["fields"]["1"]) is int and version["fields"]["1"] == 0)
                _require(version["required_fields"] == [1] and version["expected_next_opcode"] == COMPLETION_OPCODE)
                _require(document["response_allowlist"] == ["SC_KEY_NOTI", "SC_SERVER_VERSION_INFO"])
            else:
                _require(version["status"] == "pending_proof")
                _require(document["response_allowlist"] == ["SC_KEY_NOTI"])
            client = config["CS_CLIENT_VERSION_INFO"]
            _require(client["opcode"] == CLIENT_VERSION_OPCODE and client["required_fields"] == [1, 2, 3, 4])
            _require(client["required_wire_type"] == 0 and client["fixed_client_values"] == {"1": 52, "2": 949, "4": 26092901})
            completion = config["completion_observation"]
            _require(completion["opcode"] == COMPLETION_OPCODE and completion["reply_allowed"] is False)
            policy = config["session_policy"]
            _require(policy["duplicate"] == "close_without_second_reply")
            _require(policy["unexpected_opcode"] == "close_without_reply" and policy["timeouts"] == "bounded")
            _require(policy["policy_source"] == "local_experiment_restriction_not_native_client_contract")
            _require(policy["connection_count"] == "one" and policy["secret_persistence"] == "none")
            messages = {item["name"]: item for item in document["messages"]}
            version_schema = messages["CS_CLIENT_VERSION_INFO"]
            _require(version_schema["direction"] == "c2s" and version_schema["opcode"] == CLIENT_VERSION_OPCODE)
            _require({item["number"]: item["wire_type"] for item in version_schema["fields"]} == CLIENT_FIELDS)
            return cls(allowed, _PLAN_APPROVAL)
        except (KeyError, TypeError, AttributeError):
            raise ValueError("unsupported_conditional_response_contract") from None


class Stage(Enum):
    NEW = "new"
    WAIT_VERSION = "waiting_client_version"
    VERSION_OBSERVED = "client_version_observed_no_version_response"
    VERSION_REPLIED = "version_response_sent"
    COMPLETED = "character_count_request_observed_no_reply"
    REJECTED = "rejected"


def _s2c(payload: bytes, opcode: int) -> bytes:
    if opcode not in (KEY_OPCODE, SERVER_VERSION_OPCODE) or len(payload) > 65529:
        raise HandshakeError("response_not_allowed")
    # Local zeros only after the receive-chain contract approves an ignored footer.
    return struct.pack("<HH", len(payload) + 6, opcode) + payload + b"\0\0"


class InitialSession:
    """Connection-local state; retains no incoming fields, tokens, or payload."""
    def __init__(self, plan: InitialPlan, session: "Session", log: "MetadataLog"):
        self.plan, self.session, self.log = plan, session, log
        self.stage = Stage.NEW

    def _transition(self, stage: Stage, reason: str):
        self.stage = stage
        self.log.event("session_transition", session=self.session.number, stage=stage.value, reason=reason)

    def _reject(self, reason: str):
        self._transition(Stage.REJECTED, reason)
        raise HandshakeError(reason)

    async def opened(self) -> tuple[bytes, ...]:
        if self.stage != Stage.NEW:
            self._reject("duplicate_session_start")
        payload = encode_message([encode_uint32(1, 0), encode_uint32(2, 0), encode_bool(3, True)])
        self._transition(Stage.WAIT_VERSION, "conditional_key_notif")
        return (_s2c(payload, KEY_OPCODE),)

    async def received(self, frame: Frame) -> tuple[bytes, ...]:
        if self.stage == Stage.VERSION_REPLIED and frame.opcode == COMPLETION_OPCODE:
            self._transition(Stage.COMPLETED, "bounded_handshake_completed")
            raise HandshakeError("bounded_handshake_completed")
        if self.stage != Stage.WAIT_VERSION:
            self._reject("duplicate_or_out_of_order_message")
        if frame.opcode != CLIENT_VERSION_OPCODE:
            self._reject("unexpected_opcode")
        try:
            with parse_message(frame.payload, schema=CLIENT_FIELDS) as message:
                numbers = [item.number for item in message.fields]
                if len(numbers) != len(set(numbers)):
                    self._reject("duplicate_client_version_field")
                if not {1, 2, 3, 4} <= set(numbers):
                    self._reject("missing_required_client_version_fields")
                if not 0 <= message.occurrences(3)[0].value <= 0xFFFFFFFF:
                    self._reject("invalid_client_derived_scalar")
                for number, expected in ((1, 52), (2, 949), (4, 26092901)):
                    if message.occurrences(number)[0].value != expected:
                        self._reject("client_build_mismatch")
                self.log.event("protobuf_message", session=self.session.number, opcode=frame.opcode,
                               field_count=len(message.fields))
                for metadata in message.metadata():
                    self.log.event("protobuf_field", session=self.session.number, **metadata)
                # No scalar/string/bytes values are interpreted, copied, echoed,
                # retained, or used as an authentication/entitlement decision.
        except WireError:
            self._reject("malformed_client_version")
        del message
        if not self.plan.version_response_allowed:
            self._transition(Stage.VERSION_OBSERVED, "version_response_proof_pending")
            return ()
        # Required field1 is explicitly present. Other fields, including map13,
        # remain omitted; no content master or auth material is assumed available.
        payload = encode_uint32(1, 0)
        self._transition(Stage.VERSION_REPLIED, "conditional_version_response")
        return (_s2c(payload, SERVER_VERSION_OPCODE),)
