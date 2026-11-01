"""Town-owned inn rentals, using the shared inventory CAS and atomic writer.

Client dialogue supplies four hours and a 10A timely key return. Fees, one-person
direct room/hall selection and resting within three tiles of the innkeeper are
explicit LOCAL policy. No unserved inn interior or number-panel packet is made up.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time

from tools.local_original_session import inventory
from tools.local_original_session.world_bridge import need


@dataclass(frozen=True)
class InnDefinition:
    npc_id: int
    price: int
    duration_s: int
    refund: int
    room_key: int
    hall_key: int
    room_name: str
    hall_name: str
    rest_radius: int = 3
    hp_bonus: int = 5
    mp_bonus: int = 3


def definitions(directory):
    raw = json.loads((Path(directory) / 'town_services.json').read_text(encoding='utf-8'))
    return {row['l1j_npc_id']: InnDefinition(row['l1j_npc_id'], **row['rental_policy'])
            for row in raw.get('inns', ()) if 'rental_policy' in row}


def rental_row(row):
    need(type(row) is dict and set(row) == {'uid', 'npc_id', 'placement', 'key_uid',
        'key_template', 'kind', 'expires_at'}, 'INN_RENTAL_ROW')
    need(all(type(row[k]) is int and 0 < row[k] <= 0xffffffff
             for k in ('uid', 'npc_id', 'key_uid', 'key_template'))
         and row['kind'] in ('room', 'hall')
         and type(row['placement']) is list and len(row['placement']) == 4
         and all(type(v) is int and v >= 0 for v in row['placement'])
         and type(row['expires_at']) is int and row['expires_at'] > 0,
         'INN_RENTAL_ROW')
    return dict(row, placement=list(row['placement']))


class InnStore:
    """Same forward-intent pattern as ConsumableStore; no separate currency.

    The intent precedes the existing single inventory CAS (coins and key), then
    the rental snapshot. An uncertain failure keeps the intent and forbids replay
    until startup finishes the exact old/new pair. Return/expiry use the same path.
    """
    def __init__(self, transactions, *, replace_kit=None):
        self.transactions = transactions
        self.replace_kit = replace_kit or transactions.commit_inventory
        self.inventory = transactions.inventory
        self.path = Path(self.inventory.profile).with_name('inn.json')
        self.intent = self.path.with_name('inn-pending.json')
        self.rows, self.pending = {}, None
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            need(raw.get('version') == 1 and type(raw.get('rentals')) is list,
                 'INN_STORE_VERSION')
            for value in raw['rentals']:
                row = rental_row(value)
                need(row['uid'] not in self.rows, 'INN_DUPLICATE_RENTAL')
                self.rows[row['uid']] = row
        if self.intent.exists():
            self.pending = json.loads(self.intent.read_text(encoding='utf-8'))
            need(set(self.pending) == {'version', 'uid', 'rental', 'before', 'after'}
                 and self.pending['version'] == 1, 'INN_INTENT_SCHEMA')
            if self.pending['rental'] is not None:
                need(rental_row(self.pending['rental'])['uid'] == self.pending['uid'],
                     'INN_INTENT_OWNER')
            self._finish()

    @staticmethod
    def _write(path, value):
        from tools.local_original_session.world_warehouse import _atomic_json
        _atomic_json(path, value)

    def _finish(self):
        pending = self.pending
        uid = pending['uid']
        before, after = bytes.fromhex(pending['before']), bytes.fromhex(pending['after'])
        inventory.validate_kit_frame(before)
        inventory.validate_kit_frame(after)
        current = self.inventory.restore(uid)
        need(current in (before, after), 'INN_INVENTORY_CONFLICT')
        if current != after:
            # Use the existing owner, with immediate persistence at this paid boundary.
            immediate = hasattr(self.inventory, '_world_immediate')
            if immediate:
                self.inventory._world_immediate += 1
            try:
                need(self.replace_kit(uid, before, after, append=True) is True,
                     'INN_INVENTORY_COMMIT_REQUIRED')
            finally:
                if immediate:
                    self.inventory._world_immediate -= 1
        rows = dict(self.rows)
        if pending['rental'] is None:
            rows.pop(uid, None)
        else:
            rows[uid] = rental_row(pending['rental'])
        self._write(self.path, dict(version=1, rentals=[v for _, v in sorted(rows.items())]))
        self.rows = rows
        self.intent.unlink()
        self.pending = None

    def commit(self, uid, before, after, rental):
        need(self.pending is None, 'INN_RECOVERY_REQUIRED')
        if rental is not None:
            need(rental_row(rental)['uid'] == uid, 'INN_RENTAL_OWNER')
        persist = getattr(self.inventory, '_world_persist', None)
        need(persist is None or persist.flush_all().ok, 'INN_INVENTORY_FLUSH_REQUIRED')
        need(self.inventory.restore(uid) == before, 'INN_CURRENT_INVENTORY_REQUIRED')
        self.pending = dict(version=1, uid=uid, rental=rental,
                            before=before.hex(), after=after.hex())
        self._write(self.intent, self.pending)
        self._finish()


def key_owned(frame, rental):
    return any(item.identifier == rental['key_uid'] and
               item.template_bits == rental['key_template'] and dict(item.raw_fields)[4] == 1
               for item in inventory.validate_kit_frame(frame))


def inventory_frames(before, after):
    from tools.local_original_session import inventory_update, item_transfer_protocol
    old = {r.identifier: dict(r.raw_fields) for r in inventory.validate_kit_frame(before)}
    new = {r.identifier: dict(r.raw_fields) for r in inventory.validate_kit_frame(after)}
    frames = []
    for uid, previous in old.items():
        if uid not in new:
            frames.append(item_transfer_protocol.build_remove(uid=uid))
        elif previous[4] != new[uid][4]:
            frames.append(inventory_update._encode(inventory_update._values({1: uid, 4: new[uid][4]})))
    frames.extend(inventory.build_add(row) for uid, row in new.items() if uid not in old)
    return tuple(frames)


def rent_plan(frame, definition, *, uid, kind, key_uid, prototype, placement, wall=None):
    need(kind in ('room', 'hall'), 'INN_RENT_KIND')
    rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
    coins = [row for row in rows if row[2] & 0xffffffff == 7]
    need(len(coins) == 1 and coins[0][4] >= definition.price, 'INN_INSUFFICIENT_ADENA')
    need(len(rows) < inventory.KIT_MAX_ITEMS, 'INN_INVENTORY_FULL')
    need(type(key_uid) is int and 0 < key_uid <= 0xffffffff
         and all(row[1] != key_uid for row in rows), 'FRESH_OWNER_ITEM_UID_REQUIRED')
    template = definition.room_key if kind == 'room' else definition.hall_key
    name = definition.room_name if kind == 'room' else definition.hall_name
    coins[0][4] -= definition.price
    # Keep the currency row (including zero) so an existing equipment anchor
    # cannot be removed by renting. Existing kit consumption supports zero rows.
    # Reuse the explicit LOCAL plain-kit wire prototype. Only the key template,
    # name and icon are client-catalog facts; the other raw key flags are LOCAL.
    key = dict(prototype)
    key.update({1: key_uid, 2: template, 4: 1, 7: 59, 18: name.encode('utf-8')})
    rows.append(key)
    rental = dict(uid=uid, npc_id=definition.npc_id, placement=list(placement),
        key_uid=key_uid, key_template=template, kind=kind,
        expires_at=int(time.time() if wall is None else wall) + definition.duration_s)
    return inventory.build_kit_frame(rows), rental


def close_plan(frame, rental, definition, *, refund=False, wall=None, allocate_uid=None,
               coin_fields=None):
    rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
    owned = key_owned(frame, rental)
    need(not refund or owned, 'INN_OWNED_KEY_REQUIRED')
    rows = [row for row in rows if not (row[1] == rental['key_uid']
             and row[2] & 0xffffffff == rental['key_template'])]
    amount = definition.refund if refund and (time.time() if wall is None else wall) < rental['expires_at'] else 0
    if amount:
        coins = [row for row in rows if row[2] & 0xffffffff == 7]
        if coins:
            need(len(coins) == 1 and coins[0][4] + amount <= 2_000_000_000, 'INN_ADENA_CAPACITY')
            coins[0][4] += amount
        else:
            from tools.local_original_session.world_handlers import _starter_fields
            coin = dict(coin_fields) if coin_fields is not None else _starter_fields()
            coin_uid = (max((row[1] for row in rows), default=rental['key_uid']) + 1
                        if allocate_uid is None else allocate_uid())
            need(type(coin_uid) is int and 0 < coin_uid <= 0xffffffff
                 and all(row[1] != coin_uid for row in rows), 'FRESH_OWNER_ITEM_UID_REQUIRED')
            coin.update({1: coin_uid,
                         2: 7, 4: amount})
            rows.append(coin)
    need(rows, 'INN_EMPTY_INVENTORY_UNSUPPORTED')
    return inventory.build_kit_frame(rows), amount


def eligible(rental, definition, frame, position, *, wall=None):
    now = time.time() if wall is None else wall
    _, map_id, x, y = rental['placement']
    return (now < rental['expires_at'] and key_owned(frame, rental)
            and position is not None and position.map_id == map_id
            and max(abs(position.x - x), abs(position.y - y)) <= definition.rest_radius)


def regen_wrapper(ctx):
    def install(base):
        def tick(uid):
            combat = ctx.world.combat
            state = combat.pcs.get(uid)
            rental = ctx._world_inn_store.rows.get(uid)
            definition = None if rental is None else ctx._world_inn_definitions.get(rental['npc_id'])
            active = (definition is not None and state is not None and not state.dead and state.hp > 0
                and eligible(rental, definition, ctx.inventory_frame, ctx.world.entities.get(uid)))
            hp_due = active and state.hp_points + state.regen_state >= combat.regen.hp_threshold(state.profile.level)
            mp_due = active and state.mp_points + state.regen_state >= combat.regen.mp_threshold
            result = base(uid)
            changed = False
            if hp_due and state.hp < state.max_hp:
                state.hp = min(state.max_hp, state.hp + definition.hp_bonus)
                changed = True
            if mp_due and state.mp is not None and state.max_mp is not None and state.mp < state.max_mp:
                state.status_fields[12] = min(state.max_mp, state.mp + definition.mp_bonus)
                changed = True
            if changed:
                from tools.local_original_session.world_combat import status_frame
                return status_frame(state.status_fields, state.hp)
            return result
        return tick
    return install
