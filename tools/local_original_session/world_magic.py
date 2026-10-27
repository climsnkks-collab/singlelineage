"""Player magic rules and durable learning, using the retained spell data.

Numbers labelled LOCAL in player_spells.json remain backend policy. Runtime
UIDs, sessions, MP, HP, damage, and packets belong to the existing world owner.
The short learning intent uses InventoryStore's normal kit CAS and completes
forward on startup, so a crash cannot consume the same book twice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import time

from tools.local_original_session import world_magic_status as magic_status


BUFF_KINDS = frozenset(('shield', 'light', 'weapon_hit', 'weapon_damage',
                        'weight', 'armor', 'dexterity'))


def need(value, code):
    if not value:
        raise ValueError(code)


@dataclass(frozen=True)
class Spell:
    key: int
    name: str
    book: int | None
    classes: dict
    kind: str
    mp: int
    range: int
    duration: float
    reuse: float
    raw: dict = field(repr=False)


@dataclass
class MagicState:
    learned: set[int] = field(default_factory=set)
    buffs: dict[int, float] = field(default_factory=dict)
    next_cast_at: float = 0.0
    weapon_uids: dict[int, int] = field(default_factory=dict)
    poison: dict | None = None
    invisible_until: float = 0.0
    armor_uids: dict[int, int] = field(default_factory=dict)
    effects: dict[str, dict] = field(default_factory=dict)


class PlayerMagic:
    def __init__(self, catalog, *, buff_seconds=None):
        self.catalog = catalog
        self.spells = {}
        self.books = {}
        self.states: dict[int, MagicState] = {}
        # NPCs have their world EntityRef lifetime, not a durable character UID.
        self.npc_poison = {}
        self.npc_invisible = {}
        self.npc_statuses = {}
        for raw in catalog['spells']:
            policy = raw['player_policy']
            key = raw['classic_key']['value']
            duration = (raw.get('duration_seconds') or {}).get('value') or 0
            if buff_seconds is not None and duration:
                duration = buff_seconds
            spell = Spell(key, raw['id'], policy.get('book_classic_key'),
                {int(k): v for k, v in policy['allowed_class_min_levels'].items()},
                policy['kind'] if policy.get('supported', False) else 'unsupported',
                raw['mp_cost']['value'], raw['range_tiles']['value'] or 0,
                duration, policy.get('local_reuse_seconds',
                    catalog.get('local_policy', {}).get('default_reuse_seconds', 1.0)), raw)
            need(key not in self.spells, 'MAGIC_DUPLICATE_SPELL')
            self.spells[key] = spell
            if spell.book is not None:
                need(spell.book not in self.books, 'MAGIC_DUPLICATE_BOOK')
                self.books[spell.book] = spell

    def state(self, uid):
        return self.states.setdefault(uid, MagicState())

    def item_raw_weight(self, template):
        """Only source-backed magic items supplement the ordinary M1 table.

        Books and catalysts are separate domains. Unknown inventory templates
        retain a lookup failure instead of silently becoming weightless.
        """
        book = self.books.get(template)
        if book is not None:
            return book.raw['player_policy']['book_raw_weight']['value']
        return self.catalog['local_policy']['material_raw_weights'][str(template)]['value']

    def eligibility(self, spell, character_class, level):
        minimum = spell.classes.get(character_class)
        need(minimum is not None, 'MAGIC_CLASS_NOT_ALLOWED')
        need(level >= minimum, 'MAGIC_LEVEL_TOO_LOW')

    def learn(self, uid, spell, character_class, level):
        # Incomplete effects do not spend a player's book. Existing saved
        # learned keys remain readable, but are not permission to fake a cast.
        need(spell.kind != 'unsupported', 'MAGIC_EFFECT_UNSUPPORTED')
        self.eligibility(spell, character_class, level)
        need(spell.key not in self.state(uid).learned, 'MAGIC_ALREADY_LEARNED')
        # Proposal only: the inventory/learning save must finish before adopting.
        return self.state(uid).learned | {spell.key}

    def admit_cast(self, uid, key, character_class, level, mp, alive, now):
        spell = self.spells.get(key)
        need(spell is not None, 'MAGIC_UNKNOWN_SPELL')
        need(alive, 'MAGIC_LIVING_CASTER_REQUIRED')
        need(self.status(uid, 'paralyze', now) is None, 'MAGIC_CASTER_PARALYZED')
        need(key in self.state(uid).learned, 'MAGIC_NOT_LEARNED')
        self.eligibility(spell, character_class, level)
        need(spell.kind != 'unsupported', 'MAGIC_EFFECT_UNSUPPORTED')
        need(now >= self.state(uid).next_cast_at, 'MAGIC_REUSE_NOT_READY')
        need(type(mp) is int and mp >= spell.mp, 'MAGIC_INSUFFICIENT_MP')
        return spell

    def committed(self, uid, spell, now):
        state = self.state(uid)
        state.next_cast_at = now + spell.reuse
        if spell.kind in BUFF_KINDS:
            state.buffs[spell.key] = now + spell.duration

    def expire(self, now):
        changed = []
        for uid, state in self.states.items():
            expired = [key for key, until in state.buffs.items() if until <= now]
            for key in expired:
                del state.buffs[key]
                state.weapon_uids.pop(key, None)
                state.armor_uids.pop(key, None)
            invisible_expired = bool(state.invisible_until and state.invisible_until <= now)
            if invisible_expired:
                state.invisible_until = 0.0
            poison_expired = state.poison is not None and state.poison['until'] <= now
            if poison_expired:
                state.poison = None
            effects_expired = magic_status.expire(state.effects, now)
            if expired or invisible_expired or poison_expired or effects_expired:
                changed.append(uid)
        return tuple(changed)

    def effects(self, uid, *, target_ref=None):
        if target_ref is None:
            state = self.states.get(uid)
            return {} if state is None else state.effects
        row = self.npc_statuses.get(uid)
        if row is None or row['ref'] != target_ref:
            row = self.npc_statuses[uid] = dict(ref=target_ref, effects={})
        return row['effects']

    def apply_status(self, uid, kind, now, duration, *, source_uid=0, spell=0,
                     params=None, target_ref=None, onset=0):
        if target_ref is None:
            self.state(uid)
        return magic_status.apply(self.effects(uid, target_ref=target_ref), kind,
            now, duration, source_uid=source_uid, spell=spell, params=params, onset=onset)

    def status(self, uid, kind, now):
        state = self.states.get(uid)
        effects = state.effects if state is not None else self.npc_statuses.get(uid, {}).get('effects', {})
        return magic_status.active(effects, kind, now)

    def consume_counter(self, uid, now):
        if self.status(uid, 'counter_magic', now) is None:
            return False
        effects = (self.states[uid].effects if uid in self.states
                   else self.npc_statuses[uid]['effects'])
        del effects['counter_magic']
        return True

    def clear_curses(self, uid):
        effects = (self.states[uid].effects if uid in self.states
                   else self.npc_statuses.get(uid, {}).get('effects', {}))
        removed = tuple(kind for kind in effects if kind in magic_status.CURSES)
        for kind in removed:
            del effects[kind]
        return removed

    def npc_mana(self, uid, target_ref, initial):
        self.effects(uid, target_ref=target_ref)
        return self.npc_statuses[uid].setdefault('mana', initial)

    def clear_weapon_damage(self, uid, weapon_uid):
        """Pure repair producer; does not manufacture an item or repair action."""
        effects = self.effects(uid)
        effect = effects.get('weapon_break')
        if effect is not None and effect['params'].get('weapon_uid') == weapon_uid:
            del effects['weapon_break']
            return True
        return False

    def ac_bonus(self, uid, now, *, armor_uid=0):
        state = self.states.get(uid)
        if state is None:
            return 0
        return sum(self.spells[key].raw['player_policy'].get('ac_bonus', -2)
            for key, until in state.buffs.items() if until > now and (
                self.spells[key].kind == 'shield' or self.spells[key].kind == 'armor'
                and armor_uid and state.armor_uids.get(key) == armor_uid))

    def dexterity_bonus(self, uid, now):
        state = self.states.get(uid)
        return 0 if state is None else sum(
            self.spells[key].raw['player_policy'].get('dexterity_bonus', 0)
            for key, until in state.buffs.items()
            if until > now and self.spells[key].kind == 'dexterity')

    def active(self, uid, kind, now):
        state = self.states.get(uid)
        return state is not None and any(until > now and self.spells[key].kind == kind
                                        for key, until in state.buffs.items())

    def is_lit(self, uid, now):
        return self.active(uid, 'light', now)

    def is_poisoned(self, uid, now):
        state = self.states.get(uid)
        poison = self.npc_poison.get(uid) if state is None else state.poison
        return poison is not None and poison['until'] > now

    def is_invisible(self, uid, now):
        state = self.states.get(uid)
        return (self.npc_invisible.get(uid, {}).get('until', 0) > now if state is None
                else state.invisible_until > now)

    def snapshot(self, uid, now, *, wall=None, learned=None):
        state = self.state(uid)
        row = dict(uid=uid, learned=sorted(state.learned if learned is None else learned),
            buffs=[dict(spell=key, remaining=until - now, **(
                       {'weapon_uid': state.weapon_uids[key]} if key in state.weapon_uids else {}), **(
                       {'armor_uid': state.armor_uids[key]} if key in state.armor_uids else {}))
                   for key, until in sorted(state.buffs.items()) if until > now],
            reuse_remaining=max(0.0, state.next_cast_at - now),
            saved_at=time.time() if wall is None else wall)
        statuses = {}
        if state.poison is not None and state.poison['until'] > now:
            poison = state.poison
            statuses['poison'] = dict(remaining=poison['until'] - now,
                next_remaining=max(0.0, poison['next_tick'] - now),
                tick_seconds=poison['tick_seconds'], damage=poison['damage'],
                source_uid=poison['source_uid'])
        if state.invisible_until > now:
            statuses['invisible_remaining'] = state.invisible_until - now
        effects = magic_status.snapshot(state.effects, now)
        if effects:
            statuses['effects'] = effects
        if statuses:
            row['statuses'] = statuses
        return row

    def restore(self, uid, row, now, *, wall=None):
        elapsed = max(0.0, (time.time() if wall is None else wall) - row['saved_at'])
        state = MagicState(set(row['learned']), {
            buff['spell']: now + buff['remaining'] - elapsed for buff in row['buffs']
            if buff['remaining'] > elapsed},
            now + max(0.0, row['reuse_remaining'] - elapsed))
        need(state.learned <= self.spells.keys()
             and all(key in state.learned and self.spells[key].kind in BUFF_KINDS
                     for key in state.buffs), 'MAGIC_SAVED_SPELL_UNSUPPORTED')
        state.weapon_uids = {buff['spell']: buff['weapon_uid'] for buff in row['buffs']
                             if buff['spell'] in state.buffs and 'weapon_uid' in buff}
        state.armor_uids = {buff['spell']: buff['armor_uid'] for buff in row['buffs']
                            if buff['spell'] in state.buffs and 'armor_uid' in buff}
        statuses = row.get('statuses', {})
        state.effects = magic_status.restore(statuses.get('effects', {}), now, elapsed)
        invisible_remaining = max(0.0, statuses.get('invisible_remaining', 0) - elapsed)
        state.invisible_until = now + invisible_remaining if invisible_remaining else 0.0
        poison = statuses.get('poison')
        if poison is not None and poison['remaining'] > elapsed:
            state.poison = dict(until=now + poison['remaining'] - elapsed,
                # Offline time expires poison but never replays damage on login.
                next_tick=now + (poison['next_remaining'] - elapsed
                    if poison['next_remaining'] > elapsed else poison['tick_seconds']),
                tick_seconds=poison['tick_seconds'], damage=poison['damage'],
                source_uid=poison['source_uid'])
        self.states[uid] = state
        return state


def load_catalog():
    return json.loads((Path(__file__).parent / 'data' / 'm3' / 'player_spells.json')
                      .read_text(encoding='utf-8'))


def _row(row):
    required = {'uid', 'learned', 'buffs', 'reuse_remaining', 'saved_at'}
    need(type(row) is dict and required <= set(row) <= required | {'statuses'}, 'MAGIC_SAVE_SCHEMA')
    need(type(row['uid']) is int and 0 < row['uid'] <= 0xffffffff,
         'MAGIC_SAVE_CHARACTER')
    need(type(row['learned']) is list and all(type(k) is int and 0 <= k <= 0xffffffff
         for k in row['learned']) and len(set(row['learned'])) == len(row['learned']),
         'MAGIC_SAVE_LEARNED')
    need(type(row['buffs']) is list, 'MAGIC_SAVE_BUFFS')
    def number(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    need(number(row['saved_at']) and number(row['reuse_remaining']), 'MAGIC_SAVE_TIME')
    for buff in row['buffs']:
        need(type(buff) is dict and {'spell', 'remaining'} <= set(buff) <= {
                 'spell', 'remaining', 'weapon_uid', 'armor_uid'}
             and type(buff['spell']) is int and buff['spell'] in row['learned']
             and number(buff['remaining']), 'MAGIC_SAVE_BUFF')
        need('weapon_uid' not in buff or type(buff['weapon_uid']) is int
             and buff['weapon_uid'] > 0, 'MAGIC_SAVE_WEAPON')
        need('armor_uid' not in buff or type(buff['armor_uid']) is int
             and buff['armor_uid'] > 0, 'MAGIC_SAVE_ARMOR')
    need(len({b['spell'] for b in row['buffs']}) == len(row['buffs']),
         'MAGIC_SAVE_DUPLICATE_BUFF')
    statuses = row.get('statuses', {})
    need(type(statuses) is dict and set(statuses) <= {'poison', 'invisible_remaining', 'effects'},
         'MAGIC_SAVE_STATUSES')
    magic_status.validate(statuses.get('effects', {}))
    need('invisible_remaining' not in statuses or number(statuses['invisible_remaining']),
         'MAGIC_SAVE_INVISIBLE')
    if 'poison' in statuses:
        poison = statuses['poison']
        need(type(poison) is dict and set(poison) == {
            'remaining', 'next_remaining', 'tick_seconds', 'damage', 'source_uid'}
            and all(number(poison[k]) for k in ('remaining', 'next_remaining', 'tick_seconds'))
            and poison['tick_seconds'] > 0 and type(poison['damage']) is int
            and poison['damage'] > 0 and type(poison['source_uid']) is int
            and 0 < poison['source_uid'] <= 0xffffffff, 'MAGIC_SAVE_POISON')
    return row


class MagicStore:
    """One profile's startup cache and interrupted book-learning transaction.

    Ordinary saves never touch inventory. Only learn() participates in the
    existing inventory CAS, and only startup recovery may finish its intent.
    """
    def __init__(self, inventory_store, *, replace_kit=None):
        self.inventory = inventory_store
        # The host supplies its existing equipment-aware kit owner. The same
        # owner is used when startup completes an interrupted learning intent.
        self._replace_kit = replace_kit
        self.path = Path(inventory_store.profile).with_name('magic.json')
        self.intent_path = self.path.with_name('magic-learning.json')
        self.pending = None
        self.rows = {}
        if self.path.exists():
            document = json.loads(self.path.read_text(encoding='utf-8'))
            need(document.get('version') == 1 and type(document.get('rows')) is list,
                 'MAGIC_SAVE_VERSION')
            for raw in document['rows']:
                row = _row(raw)
                need(row['uid'] not in self.rows, 'MAGIC_SAVE_DUPLICATE_CHARACTER')
                self.rows[row['uid']] = row
        if self.intent_path.exists():
            intent = json.loads(self.intent_path.read_text(encoding='utf-8'))
            need(type(intent) is dict and set(intent) == {
                'version', 'before', 'after', 'inventory_before', 'inventory_after'}
                and intent['version'] == 1, 'MAGIC_LEARNING_INTENT_SCHEMA')
            _row(intent['after'])
            if intent['before'] is not None:
                _row(intent['before'])
                need(intent['before']['uid'] == intent['after']['uid'],
                     'MAGIC_LEARNING_CHARACTER')
            self.pending = intent
            self._finish(self.inventory.restore(intent['after']['uid']))

    def _write(self, rows):
        from tools.local_original_session.world_warehouse import _atomic_json
        _atomic_json(self.path, dict(version=1,
            rows=[row for _, row in sorted(rows.items())]))

    def save(self, row):
        _row(row)
        need(self.pending is None, 'MAGIC_LEARNING_RECOVERY_REQUIRED')
        rows = dict(self.rows)
        rows[row['uid']] = row
        self._write(rows)
        self.rows = rows

    def _finish(self, current):
        from tools.local_original_session import inventory
        intent = self.pending
        row, before = intent['after'], intent['before']
        expected, updated = bytes.fromhex(intent['inventory_before']), bytes.fromhex(intent['inventory_after'])
        inventory.validate_kit_frame(expected)
        inventory.validate_kit_frame(updated)
        need(self.rows.get(row['uid']) in (before, row), 'MAGIC_LEARNING_STATE_CONFLICT')
        need(current in (expected, updated), 'MAGIC_LEARNING_INVENTORY_CONFLICT')
        if current == expected:
            replace_kit = self._replace_kit or self.inventory.replace_kit
            need(replace_kit(row['uid'], expected, updated) is True,
                 'MAGIC_LEARNING_PERSISTED_CHANGE_REQUIRED')
        if self.rows.get(row['uid']) != row:
            rows = dict(self.rows)
            rows[row['uid']] = row
            self._write(rows)
            self.rows = rows
        self.intent_path.unlink()
        self.pending = None

    def learn(self, row, expected, updated):
        from tools.local_original_session import inventory
        from tools.local_original_session.world_warehouse import _atomic_json
        _row(row)
        inventory.validate_kit_frame(expected)
        inventory.validate_kit_frame(updated)
        need(self.pending is None, 'MAGIC_LEARNING_RECOVERY_REQUIRED')
        self.pending = dict(version=1, before=self.rows.get(row['uid']), after=row,
                            inventory_before=expected.hex(), inventory_after=updated.hex())
        _atomic_json(self.intent_path, self.pending)
        self._finish(expected)


def book_mutation(frame, item_uid):
    """The existing kit quantity/remove rules, proposed before the joint save."""
    from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
    items = inventory.validate_kit_frame(frame)
    selected = next((item for item in items if item.identifier == item_uid), None)
    need(selected is not None and dict(selected.raw_fields)[4] > 0,
         'MAGIC_OWNED_POSITIVE_BOOK_REQUIRED')
    quantity = dict(selected.raw_fields)[4]
    removed = quantity == 1 and len(items) > 1
    rows = []
    for item in items:
        if item.identifier == item_uid and removed:
            continue
        fields = dict(item.raw_fields)
        if item.identifier == item_uid:
            fields[4] = quantity - 1
        rows.append(fields)
    wire = (item_transfer_protocol.build_remove(uid=item_uid) if removed else
            inventory_update._encode(inventory_update._values({1: item_uid, 4: quantity - 1})))
    return inventory.build_kit_frame(rows), wire


def material_mutation(frame, materials, *, worn=()):
    """Propose positive catalyst debits through the ordinary kit row codecs."""
    from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
    items = inventory.validate_kit_frame(frame)
    rows = [dict(item.raw_fields) for item in items]
    original = {row[1]: dict(row) for row in rows}
    for material in materials:
        remaining = material['count']
        for row in rows:
            if row[1] not in worn and row[2] & 0xffffffff == material['classic_item_key']:
                taken = min(remaining, row[4])
                row[4] -= taken
                remaining -= taken
        need(remaining == 0, 'MAGIC_CURRENT_CATALYST_REQUIRED')
    changed_rows = rows
    rows = [row for row in changed_rows if row[4] > 0 or original[row[1]][4] == 0]
    # Like book_mutation, a completely depleted kit retains one real UID/Q0
    # anchor. Unrelated pre-existing zero rows are never removed by a catalyst.
    if not rows:
        rows = [changed_rows[-1]]
    updated = inventory.build_kit_frame(rows)
    after = {row[1]: row for row in rows}
    frames = []
    for uid, row in original.items():
        if uid not in after:
            frames.append(item_transfer_protocol.build_remove(uid=uid))
        elif row[4] != after[uid][4]:
            frames.append(inventory_update._encode(inventory_update._values({1: uid, 4: after[uid][4]})))
    return updated, tuple(frames)
