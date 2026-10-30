"""Attributed LOCAL crafting plans; no guessed Classic request/response wire.

The original ``request_craft`` is a client command, not a HACTION literal.
This module changes a canonical kit only after all materials, prototypes,
quantities and capacity have been checked. The caller owns its ordinary CAS.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from tools.local_original_session import inventory
from tools.local_original_session.world_bridge import need

DATA_PATH = Path(__file__).resolve().parent / 'data/crafting.json'
MAX_AMOUNT = 2_000_000_000
MAKE_REQUEST = 0x0005
MAKE_ACK = 0x0006


@dataclass(frozen=True, slots=True)
class CraftRequest:
    target_uid: int
    recipe_id: int
    count: int
    inputs: tuple[tuple[int, int, int, int, int], ...]
    extra: int | None = None


def decode_request(payload):
    """Exact preserved 5c4520 producer: NPC, recipe, count and input slots.

    Field meanings are bound by the original stores at 5c490c/16/22 and
    5c49e3..5c4a0c, not by protobuf field numbers or message names alone.
    """
    from tools.local_entry_server import protobuf as pb
    limits = pb.WireLimits(max_body=16384, max_fields=200, max_field_bytes=1024)
    with pb.parse_message(payload, limits=limits) as message:
        need(all(f.number in (1, 2, 3, 4, 5) for f in message.fields), 'CRAFT_REQUEST_FIELDS')
        values = {}
        for n in (1, 2, 3):
            fields = message.occurrences(n)
            need(len(fields) == 1 and fields[0].wire_type == 0
                 and 0 < fields[0].value < 1 << 32, 'CRAFT_REQUEST_VALUES')
            values[n] = fields[0].value
        slots = []
        for field in message.occurrences(4):
            need(field.wire_type == 2, 'CRAFT_INPUT_WIRE')
            with pb.parse_message(bytes(field.value), limits=limits) as nested:
                need(len(nested.fields) == 5 and all(f.number in (1, 2, 3, 4, 5)
                     for f in nested.fields), 'CRAFT_INPUT_FIELDS')
                row = []
                for n in (1, 2, 3, 4, 5):
                    fields = nested.occurrences(n)
                    need(len(fields) == 1 and fields[0].wire_type == 0,
                         'CRAFT_INPUT_VALUES')
                    value = fields[0].value
                    need(0 <= value < (1 << (63 if n == 3 else 32)), 'CRAFT_INPUT_RANGE')
                    row.append(value)
                need(row[1] > 0 and row[2] > 0, 'CRAFT_INPUT_POSITIVE_AMOUNT')
                slots.append(tuple(row))
        extra = message.occurrences(5)
        need(len(extra) <= 1 and (not extra or extra[0].wire_type == 0), 'CRAFT_EXTRA_FIELD')
        return CraftRequest(values[1], values[2], values[3], tuple(slots),
                            extra[0].value if extra else None)


def acknowledgement_frame(*, success):
    """4d1a10: explicit enum0 selects _s; absence resets pending without a page.

    Empty refusal ACK native-parser admission remains unobserved. No guessed
    failure enum, probability payload or fabricated reward ItemInfo is emitted.
    """
    from tools.local_entry_server import protobuf as pb
    need(type(success) is bool, 'CRAFT_ACK_RESULT_REQUIRED')
    body = pb.encode_uint32(1, 0) if success else b''
    return ((len(body) + 6).to_bytes(2, 'little') + MAKE_ACK.to_bytes(2, 'little')
            + body + b'\0\0')


@dataclass(frozen=True, slots=True)
class Material:
    template_id: int
    quantity: int

    def __post_init__(self):
        need(type(self.template_id) is int and 0 < self.template_id < 1 << 32
             and type(self.quantity) is int and 0 < self.quantity <= MAX_AMOUNT,
             'CRAFT_ITEM_AMOUNT_REQUIRED')


@dataclass(frozen=True, slots=True)
class Recipe:
    id: str
    npc_template_id: int
    result: Material
    materials: tuple[Material, ...]

    def __post_init__(self):
        need(type(self.id) is str and bool(self.id)
             and type(self.npc_template_id) is int and self.npc_template_id > 0
             and type(self.result) is Material and type(self.materials) is tuple
             and bool(self.materials) and all(type(m) is Material for m in self.materials),
             'CRAFT_RECIPE_REQUIRED')


@dataclass(frozen=True, slots=True)
class CraftPlan:
    before: bytes
    after: bytes
    frames: tuple[bytes, ...]
    recipe_id: str
    count: int


def load_recipes(path=DATA_PATH):
    """Startup only. L1J action text is retained in data, never a wire action."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    need(raw['version'] == 1 and raw['policy'] == 'local_policy', 'CRAFT_POLICY_REQUIRED')
    recipes = tuple(Recipe(row['id'], row['npc_template_id'],
                          Material(row['result']['template_id'], row['result']['quantity']),
                          tuple(Material(m['template_id'], m['quantity']) for m in row['materials']))
                    for row in raw['recipes'])
    need(len({r.id for r in recipes}) == len(recipes), 'CRAFT_RECIPE_ID_UNIQUE_REQUIRED')
    return recipes


def _plain(row, policy):
    prototype = policy.grant_fields
    return prototype is not None and all(
        row.get(n) == value or n == 18 and row.get(n) in policy.plain_names
        for n, value in prototype.items() if n not in (1, 4, 7))


def inventory_frames(before, after):
    """Use the existing quantity/remove/add producers, after a successful save."""
    from tools.local_original_session import inventory_update, item_transfer_protocol
    old = {r.identifier: dict(r.raw_fields) for r in inventory.validate_kit_frame(before)}
    new = {r.identifier: dict(r.raw_fields) for r in inventory.validate_kit_frame(after)}
    frames = []
    for uid, row in old.items():
        if uid not in new:
            frames.append(item_transfer_protocol.build_remove(uid=uid))
        elif row[4] != new[uid][4]:
            frames.append(inventory_update._encode(inventory_update._values({1: uid, 4: new[uid][4]})))
    frames.extend(inventory.build_add(row) for uid, row in new.items() if uid not in old)
    return tuple(frames)


def calculate_craft(frame, recipe, count, policies, *, excluded_uids=(),
                    allocate_uid=None, max_weight=None):
    """One all-or-nothing LOCAL plan. No save or input mutation occurs here.

    Plain variants alone qualify; the owner excludes equipped/controlled rows.
    Output UID allocation follows the existing grant producer after refusals.
    """
    from tools.local_original_session.world_weight import stack_weight
    need(type(recipe) is Recipe and type(count) is int and 0 < count <= MAX_AMOUNT,
         'CRAFT_POSITIVE_COUNT_REQUIRED')
    rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
    original_uids = {row[1] for row in rows}
    excluded = frozenset(excluded_uids)
    consumed = set()
    required = {}
    for material in recipe.materials:
        amount = material.quantity * count
        required[material.template_id] = required.get(material.template_id, 0) + amount
        need(required[material.template_id] <= MAX_AMOUNT, 'CRAFT_MATERIAL_COUNT_LIMIT')
    for template, amount in required.items():
        policy = policies.get(template)
        need(policy is not None and policy.grant_fields is not None,
             'CRAFT_MATERIAL_POLICY_REQUIRED')
        available = [row for row in rows if row[2] & 0xffffffff == template
                     and row[1] not in excluded and _plain(row, policy)]
        need(sum(row[4] for row in available) >= amount, 'CRAFT_INSUFFICIENT_MATERIALS')
        for row in available:
            taken = min(amount, row[4])
            row[4] -= taken
            amount -= taken
            if taken:
                consumed.add(row[1])
    # Preserve unrelated zero-quantity core anchors exactly as supplied.
    rows = [row for row in rows if row[4] > 0 or row[1] not in consumed]
    result, quantity = recipe.result, recipe.result.quantity * count
    need(quantity <= MAX_AMOUNT, 'CRAFT_RESULT_COUNT_LIMIT')
    policy = policies.get(result.template_id)
    need(policy is not None and policy.grant_fields is not None,
         'CRAFT_RESULT_POLICY_REQUIRED')
    prototype = dict(policy.grant_fields)
    need(prototype.get(2, 0) & 0xffffffff == result.template_id,
         'CRAFT_RESULT_TEMPLATE_REQUIRED')
    held = next((row for row in rows if policy.stackable and row[1] not in excluded
                 and row[2] & 0xffffffff == result.template_id
                 and all(row.get(n) == value for n, value in prototype.items()
                         if n not in (1, 4))), None)
    if held is not None:
        need(held[4] + quantity <= MAX_AMOUNT, 'CRAFT_RESULT_STACK_LIMIT')
        held[4] += quantity
        grants = ()
    else:
        slots = 1 if policy.stackable else quantity
        need(len(rows) + slots <= inventory.KIT_MAX_ITEMS, 'CRAFT_INVENTORY_FULL')
        grants = (quantity,) if policy.stackable else (1,) * quantity
    if max_weight is not None:
        need(type(max_weight) is int and max_weight >= 0, 'CRAFT_CAPACITY_REQUIRED')
        need(all(row[2] & 0xffffffff in policies for row in rows), 'CRAFT_WEIGHT_POLICY_REQUIRED')
        weight = sum(stack_weight(policies[row[2] & 0xffffffff].raw_weight, row[4])
                     for row in rows)
        weight += sum(stack_weight(policy.raw_weight, n) for n in grants)
        need(weight <= max_weight, 'CRAFT_WEIGHT_LIMIT')
    allocated = set(original_uids)
    for amount in grants:
        uid = max(allocated, default=0) + 1 if allocate_uid is None else allocate_uid()
        need(type(uid) is int and 0 < uid < 1 << 32 and uid not in allocated,
             'CRAFT_FRESH_ITEM_UID_REQUIRED')
        allocated.add(uid)
        rows.append({**prototype, 1: uid, 4: amount})
    after = inventory.build_kit_frame(rows)
    return CraftPlan(frame, after, inventory_frames(frame, after), recipe.id, count)
