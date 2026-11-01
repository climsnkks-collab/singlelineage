"""ATS settings blob codec and companion AI policy reading (LOCAL).

Wire contract from game-core-prep/ATS_COMPANION_TOGGLE_DESIGN.md 2장 and the
offline draft ats-toggle-analysis/ats_blob_draft.py (restored static evidence):
C->S 4ED6 f1/f2 carry a raw wrapper W = u32 N + u8 flag + (zlib or raw); S->C
4ED7 carries ASCII hex(W) per field. Unknown/repeated fields are preserved by
keeping original wrapper bytes. First member edits clone CharacterConfig,
clearing its item shortcut links while retaining other serialized fields.

``companion_policy`` turns a saved companion-scope ATSConfig into a LOCAL AI
policy: recovery slots/percent -> potions, the six function slots -> function
items (speed potions), buff list -> maintained buffs, battle sequence /
conditional list -> attack and heal spells, options f1/f7 -> scan range and
pickup weight. kind1 slot f4 is read as the client spell key (the catalog
``classic_key``) and kind2 slot f4 as the item template: both are LOCAL
readings of UNKNOWN-named fields, documented in the design.
"""
from __future__ import annotations

import re
import hashlib
import struct
import zlib

COMPRESS_CAPACITY = 0xED4

# LC 26.09.29.2001, RVA449BB0; see ATS_COMPANION_TOGGLE_DESIGN 2장.
# State belongs to one spellRowID in one companion/target lifetime.
def _percent(current, maximum):
    return struct.unpack('<f', struct.pack('<f', current * 100 / maximum))[0]


def _elapsed(record, value, state, now):
    if state is None or now is None:
        return False
    if 'at' not in state:
        state['at'] = now  # retained even if a later AND condition fails
        return True
    return int(now - state['at']) >= value


CONDITION_PREDICATES = {
    1: lambda r, v, s, n: getattr(r, 'effective_max_hp', r.max_hp) > 0 and _percent(r.hp, getattr(r, 'effective_max_hp', r.max_hp)) >= v,
    2: lambda r, v, s, n: getattr(r, 'effective_max_hp', r.max_hp) > 0 and _percent(r.hp, getattr(r, 'effective_max_hp', r.max_hp)) <= v,
    3: lambda r, v, s, n: getattr(r, 'effective_max_mp', r.max_mp) > 0 and _percent(r.mp, getattr(r, 'effective_max_mp', r.max_mp)) >= v,
    4: lambda r, v, s, n: getattr(r, 'effective_max_mp', r.max_mp) > 0 and _percent(r.mp, getattr(r, 'effective_max_mp', r.max_mp)) <= v,
    5: _elapsed,
    6: lambda r, v, s, n: s is not None and s.get('count', 0) < v,
}


def condition_matches(kind, value, record, *, state=None, now=None):
    predicate = CONDITION_PREDICATES.get(kind)
    return (False if predicate is None or type(value) is not int else
            bool(predicate(record, value, state, now)))


def wrap_blob(payload: bytes, *, raw=False) -> bytes:
    header = struct.pack('<I', len(payload))
    compressed = zlib.compress(payload)
    if not raw and len(compressed) <= COMPRESS_CAPACITY:
        return header + b'\x01' + struct.pack('<I', len(compressed)) + compressed
    return header + b'\x00' + payload


def unwrap_blob(blob: bytes, *, max_size=1 << 20) -> bytes:
    if len(blob) < 5:
        raise ValueError('ATS_BLOB_TRUNCATED')
    size = struct.unpack_from('<I', blob)[0]
    if size > max_size:
        raise ValueError('ATS_BLOB_SIZE')
    if blob[4] != 1:
        if len(blob) != 5 + size:
            raise ValueError('ATS_BLOB_RAW_LENGTH')
        return bytes(blob[5:])
    if len(blob) < 9:
        raise ValueError('ATS_BLOB_TRUNCATED')
    compressed = struct.unpack_from('<I', blob, 5)[0]
    if len(blob) != 9 + compressed:
        raise ValueError('ATS_BLOB_COMPRESSED_LENGTH')
    decoder = zlib.decompressobj()
    payload = decoder.decompress(bytes(blob[9:]), size + 1)
    if len(payload) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('ATS_BLOB_STREAM')
    return payload


def noti_field(wrapper: bytes) -> bytes:
    """4ED7 field value for an existing 4ED6 wrapper: its ASCII hex."""
    unwrap_blob(wrapper)  # refuse to forward a malformed wrapper
    return bytes(wrapper).hex().encode('ascii')


def read_noti_field(text: bytes) -> bytes:
    if not text or len(text) % 2 or re.fullmatch(rb'[0-9A-Fa-f]+', text) is None:
        raise ValueError('ATS_NOTI_HEX_REQUIRED')
    return bytes.fromhex(text.decode('ascii'))


def _varint(data, pos):
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise ValueError('ATS_VARINT_TRUNCATED')
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            return value & 0xFFFFFFFFFFFFFFFF, pos
    raise ValueError('ATS_VARINT_LONG')


def varint(value):
    value &= 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def _field_chunks(data: bytes):
    """Yield decoded fields and their exact wire bytes, including noncanonical tags."""
    pos = 0
    while pos < len(data):
        start = pos
        tag, pos = _varint(data, pos)
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value, pos = _varint(data, pos)
        elif wire in (1, 2, 5):
            size = 8 if wire == 1 else 4 if wire == 5 else None
            if size is None:
                size, pos = _varint(data, pos)
            if size > len(data) - pos:
                raise ValueError('ATS_FIELD_TRUNCATED')
            value, pos = bytes(data[pos:pos + size]), pos + size
        else:
            raise ValueError('ATS_WIRE_UNSUPPORTED')
        yield number, wire, value, bytes(data[start:pos])


def fields(data: bytes):
    """[(number, wire, value)] in order; groups refused."""
    return [(n, w, v) for n, w, v, _ in _field_chunks(data)]


def field(number, wire, value):
    tag = varint(number << 3 | wire)
    if wire == 0:
        return tag + varint(value)
    if wire == 2:
        return tag + varint(len(value)) + value
    return tag + value


def _int32(value):
    value &= 0xFFFFFFFFFFFFFFFF
    return value - (1 << 64) if value >= 1 << 63 else value


def _slot(data):
    values = {}
    for number, wire, value in fields(data):
        if wire == 0:
            values[number] = value if number == 6 else _int32(value)
        elif wire == 2 and number == 7:
            values[number] = value
    return values


def _float(raw):
    return struct.unpack('<f', raw)[0]


def companion_character_config(wrapper: bytes) -> bytes:
    """Clone f1 without the owner's inventory links in CharacterConfig field 2.

    The captured field 2 contains a version (child f1) and repeated shortcut
    slots (child f2). Only kind2 item slots become the native empty encoding.
    All other field chunks retain their original bytes and encounter order.
    """
    empty = field(1, 0, 0) + field(3, 0, 0) + field(4, 0, -1)
    payload = unwrap_blob(wrapper)
    result = []
    for number, wire, value, chunk in _field_chunks(payload):
        if (number, wire) == (2, 2):
            children = []
            for n, w, v, raw in _field_chunks(value):
                children.append(field(2, 2, empty) if (n, w) == (2, 2)
                                and _slot(v).get(1) == 2 else raw)
            rewritten = b''.join(children)
            if rewritten != value:
                chunk = field(2, 2, rewritten)
        result.append(chunk)
    rewritten = b''.join(result)
    return wrap_blob(rewritten) if rewritten != payload else wrapper


def _rewrite(data, path, edit):
    """Rewrite the length-delimited children on ``path``; other chunks keep their bytes."""
    result = []
    for number, wire, value, chunk in _field_chunks(data):
        if wire == 2 and path and number in path[0]:
            value2 = _rewrite(value, path[1:], edit) if len(path) > 1 else edit(value)
            if value2 != value:
                chunk = field(number, 2, value2)
        result.append(chunk)
    return b''.join(result)


def loadable_ats(wrapper: bytes) -> bytes:
    """4ED7 copy whose item slots the native loader resolves again.

    4302F0 restores slot f5 only when signed f6 > 0; otherwise the lookup keeps
    f22=1 and misses inventory items whose ItemInfo f22 is 0, hiding the icon
    (W52, B046F0/42C4A0). A positive f6 that matches no ItemEntity key falls
    through to the template + f22 (+ name) lookup.
    """
    def item(value):
        slot = _slot(value)
        if slot.get(1) != 2 or slot.get(4, -1) <= 0 or _int32(slot.get(6, -1)) > 0:
            return value
        kept = b''.join(raw for n, w, v, raw in _field_chunks(value) if n not in (5, 6))
        return kept + field(5, 0, 0) + field(6, 0, 1)
    payload = unwrap_blob(wrapper)
    rewritten = _rewrite(payload, ({1}, {2}, {1}, {1, 3, 5}), item)
    return wrap_blob(rewritten) if rewritten != payload else wrapper


def _children(data, number, wire=2):
    return [value for n, w, value in fields(data) if n == number and w == wire]


def decode_options(ats: bytes) -> dict:
    """Readable view of the ATSConfig tree used by the companion policy."""
    sections = _children(ats, 1)
    option = next((v for s in sections for v in _children(s, 2)), None)
    result = dict(hp_slots=[], hp_percent=None, mp_slots=[], mp_percent=None,
                  function_slots=[], buff_slots=[], sequence=[], conditional=[], battle_slots=[], options={})
    if option is None:
        return result
    buff = next(iter(_children(option, 1)), None)
    battle = next(iter(_children(option, 2)), None)
    opts = next(iter(_children(option, 3)), None)
    if buff is not None:
        for number, wire, value in fields(buff):
            if number in (1, 3, 5, 7) and wire == 2:
                key = {1: 'hp_slots', 3: 'mp_slots', 5: 'function_slots', 7: 'buff_slots'}[number]
                result[key].append(_slot(value))
            elif number in (2, 4) and wire == 5:
                result['hp_percent' if number == 2 else 'mp_percent'] = _float(value)
    if battle is not None:
        for number, wire, value in fields(battle):
            if number == 1 and wire == 2:
                slot = _slot(value)
                result['battle_slots'].append(dict(kind='sequence', index=len(result['sequence']), slot=slot))
                result['sequence'].append(slot)
            elif number == 2 and wire == 2:
                entry = {}
                for n, w, v in fields(value):
                    if n in (1, 2) and w == 0:
                        entry[n] = _int32(v)
                    elif n == 3 and w == 2:
                        entry['slot'] = _slot(v)
                result['conditional'].append(entry)
                result['battle_slots'].append(dict(kind='conditional', index=len(result['conditional']) - 1,
                    slot=entry.get('slot', {}), condition=entry.get(1), value=entry.get(2)))
    if opts is not None:
        result['options'] = {n: _int32(v) for n, w, v in fields(opts) if w == 0}
    return result


def companion_policy(ats_wrapper: bytes | None, spells_by_key) -> dict:
    """Saved selections, including empty/invalid states; never AI defaults.

    Battle rows retain protobuf encounter order across both row types. Their
    native visual ordering still needs a real sample; no type-based priority
    is introduced here. Conditions are grouped by raw spellRowID, including
    for a sequence row that selects the same spell.
    """
    result = dict(source='LOCAL_ATS_COMPANION_SCOPE', status='missing', issues=[],
        potion_hp=dict(slots=[], templates=[], threshold=None),
        potion_mp=dict(slots=[], templates=[], threshold=None),
        function_slots=[], function_items=[], buff_slots=[], buff_items=[],
        battle_slots=[], maintain_buffs=[], attack_spells=[], heal_spells=[],
        scan_tiles=None, pickup_weight=None)
    if ats_wrapper is None:
        return result
    try:
        payload = unwrap_blob(ats_wrapper)
        result['selection_id'] = hashlib.sha256(payload).hexdigest()
        view = decode_options(payload)
        if payload and not any(_children(s, 2) for s in _children(payload, 1)):
            raise ValueError('ATS_OPTION_UNKNOWN')
    except (ValueError, zlib.error, struct.error) as error:
        result.update(status='invalid', issues=[str(error)])
        return result

    def selection(slot):
        chosen = dict(raw=dict(slot), status='empty')
        if not slot or slot.get(1, 0) == 0:
            return chosen
        # Native saved item/spell rows retain their kind when unselected;
        # f4=-1 is the empty selection sentinel, not an unknown template/key.
        # Ancillary identity/label fields do not make that slot a selection.
        if slot.get(1) in (1, 2) and slot.get(4) == -1:
            return chosen
        if slot.get(1) == 1 and slot.get(4) in spells_by_key:
            chosen.update(status='valid', spell=spells_by_key[slot[4]])
        elif slot.get(1) == 2 and slot.get(4, 0) > 0 and {5, 6} <= slot.keys():
            chosen.update(status='valid', template=slot[4])
        else:
            chosen['status'] = 'invalid'
            result['issues'].append('ATS_SLOT_UNKNOWN')
        return chosen

    for kind in ('hp', 'mp'):
        slots = [selection(s) for s in view[kind + '_slots']]
        value = view[kind + '_percent']
        result['potion_' + kind] = dict(slots=slots,
            templates=[s['template'] for s in slots if 'template' in s],
            threshold=value / 100 if value is not None and 0 <= value <= 100 else None)
    for kind in ('function', 'buff'):
        slots = [selection(s) for s in view[kind + '_slots']]
        result[kind + '_slots'] = slots
        result[kind + '_items'] = [s['template'] for s in slots if 'template' in s]
    result['maintain_buffs'] = [s['spell'] for s in result['buff_slots'] if 'spell' in s]
    for row in view['battle_slots']:
        selected = selection(row['slot'])
        entry = dict(row, **selected)
        result['battle_slots'].append(entry)
        spell = selected.get('spell')
        # Flat summaries contain unconditional selections only; conditional
        # expressions must never become unconditional attack/heal candidates.
        if spell is not None and row['kind'] == 'sequence':
            result['heal_spells' if 'heal' in spell else 'attack_spells'].append(spell)
        if (row['kind'] == 'conditional' and selected['status'] != 'empty'
                and row['condition'] not in CONDITION_PREDICATES):
            result['issues'].append('ATS_CONDITION_UNKNOWN:' + str(row['condition']))
    conditions = {}
    for row in result['battle_slots']:
        if (row['kind'] == 'conditional' and row['status'] != 'empty'
                and row['raw'].get(1) == 1):
            conditions.setdefault(row['raw'].get(4), []).append(
                (row.get('condition'), row.get('value')))
    for row in result['battle_slots']:
        row['conditions'] = conditions.get(row['raw'].get(4), [])
    slots = (result['potion_hp']['slots'] + result['potion_mp']['slots']
             + result['function_slots'] + result['buff_slots'] + result['battle_slots'])
    result['status'] = ('invalid' if any(s['status'] == 'invalid' for s in slots) else
                        'valid' if any(s['status'] == 'valid' for s in slots) else 'empty')
    options = view['options']
    result['scan_tiles'] = options.get(1) if type(options.get(1)) is int and options[1] > 0 else None
    result['pickup_weight'] = options.get(7) if type(options.get(7)) is int else None
    return result


def build_ats(*, hp_templates=(), hp_percent=None, mp_templates=(), mp_percent=None,
              function_templates=(), buff_spells=(), sequence_spells=(), conditional=(),
              options=None) -> bytes:
    """Synthetic ATSConfig protobuf (tests/fixtures only; not a native sample)."""
    def item(template):
        # Integer shorthand is explicitly a synthetic zero-identity fixture.
        values = {1: 2, **template} if isinstance(template, dict) else {1: 2, 4: template, 5: 0, 6: 0, 7: b''}
        return b''.join(field(n, 2 if isinstance(v, bytes) else 0, v) for n, v in values.items())
    spell = lambda key: field(1, 0, 1) + field(4, 0, key)
    buff = b''.join(field(1, 2, item(t)) for t in hp_templates)
    if hp_percent is not None:
        buff += field(2, 5, struct.pack('<f', hp_percent))
    buff += b''.join(field(3, 2, item(t)) for t in mp_templates)
    if mp_percent is not None:
        buff += field(4, 5, struct.pack('<f', mp_percent))
    buff += b''.join(field(5, 2, item(t)) for t in function_templates)
    buff += b''.join(field(7, 2, spell(k)) for k in buff_spells)
    battle = b''.join(field(1, 2, spell(k)) for k in sequence_spells)
    battle += b''.join(field(2, 2, field(1, 0, c) + field(2, 0, v) + field(3, 2, spell(k)))
                       for c, v, k in conditional)
    opts = b''.join(field(n, 0, v) for n, v in sorted((options or {}).items()))
    option = field(1, 2, buff) + field(2, 2, battle) + field(3, 2, opts)
    return field(1, 2, field(2, 2, option))


def _window_validate_changes(changes):
    """Validate the editable, LOCAL companion-window subset before touching bytes."""
    import math

    counts = {'hp_slots': 2, 'mp_slots': 2, 'function_slots': 6}
    allowed = set(counts) | {'hp_percent', 'mp_percent', 'options', 'buff_slots', 'battle_slots'}
    if type(changes) is not dict or any(key not in allowed for key in changes):
        raise ValueError('ATS_WINDOW_KEYS')
    for key, value in changes.items():
        if key in counts:
            if type(value) is not list or len(value) != counts[key]:
                raise ValueError('ATS_WINDOW_SLOT_COUNT:' + key)
            for slot in value:
                if slot is None:
                    continue
                if (type(slot) is not dict or set(slot) - {'template', 'name'}
                        or type(slot.get('template')) is not int
                        or not 0 < slot['template'] <= 0x7fffffff
                        or ('name' in slot and type(slot['name']) is not str)):
                    raise ValueError('ATS_WINDOW_SLOT:' + key)
                if 'name' in slot:
                    try:
                        slot['name'].encode('utf-8')
                    except UnicodeEncodeError as error:
                        raise ValueError('ATS_WINDOW_SLOT_NAME') from error
        elif key == 'buff_slots':
            if type(value) is not list:
                raise ValueError('ATS_WINDOW_SLOT_COUNT:' + key)
            for slot in value:
                _window_validate_spell(slot)
        elif key == 'battle_slots':
            if type(value) is not list:
                raise ValueError('ATS_WINDOW_SLOT_COUNT:' + key)
            for row in value:
                if (type(row) is not dict or row.get('kind') not in ('sequence', 'conditional')
                        or type(row.get('index')) is not int or row['index'] < 0):
                    raise ValueError('ATS_WINDOW_BATTLE_ROW')
                keys = {'kind', 'index', 'slot'}
                if row['kind'] == 'conditional':
                    keys |= {'condition', 'value'}
                    for name in ('condition', 'value'):
                        number = row.get(name)
                        if number is not None and (type(number) is not int
                                                  or not -0x80000000 <= number <= 0x7fffffff):
                            raise ValueError('ATS_WINDOW_BATTLE_CONDITION')
                if set(row) != keys:
                    raise ValueError('ATS_WINDOW_BATTLE_ROW')
                _window_validate_spell(row['slot'])
        elif key in ('hp_percent', 'mp_percent'):
            if (type(value) not in (int, float) or not 0 <= value <= 100
                    or not math.isfinite(value)):
                raise ValueError('ATS_WINDOW_PERCENT:' + key)
        else:
            if type(value) is not dict or set(value) - {'scan_tiles', 'pickup_weight'}:
                raise ValueError('ATS_WINDOW_OPTIONS')
            for name, number in value.items():
                minimum = 1 if name == 'scan_tiles' else -0x80000000
                if type(number) is not int or not minimum <= number <= 0x7fffffff:
                    raise ValueError('ATS_WINDOW_OPTION:' + name)


def _window_validate_spell(slot):
    if slot is None:
        return
    if type(slot) is dict and slot.get('status') == 'UNKNOWN':
        if (set(slot) != {'spell_row', 'name', 'icon', 'status'}
                or type(slot['spell_row']) is not int
                or not 0 <= slot['spell_row'] <= 0x7fffffff
                or slot['name'] is not None or slot['icon'] is not None):
            raise ValueError('ATS_WINDOW_READONLY_SLOT')
        return
    if type(slot) is dict and 'template' in slot:
        # The whole-array view can include native kind2 buff selections. This
        # is a preservation token, not permission to register an item here.
        if (set(slot) - {'template', 'name'} or type(slot['template']) is not int
                or not 0 < slot['template'] <= 0x7fffffff
                or ('name' in slot and type(slot['name']) is not str)):
            raise ValueError('ATS_WINDOW_READONLY_ITEM')
    elif type(slot) is dict and 'spell_key' in slot:
        # Preserve the existing server view for unresolved slots. The codec
        # has no spell catalog and cannot resolve these display identities.
        if (set(slot) != {'spell_key', 'spell', 'status'} or slot['spell'] is not None
                or slot['status'] != 'invalid' or (slot['spell_key'] is not None
                and type(slot['spell_key']) is not int)):
            raise ValueError('ATS_WINDOW_READONLY_SLOT')
        return
    elif (type(slot) is not dict or set(slot) - {'spell_row', 'name', 'icon'}
            or type(slot.get('spell_row')) is not int
            or not 0 <= slot['spell_row'] <= 0x7fffffff
            or ('name' in slot and type(slot['name']) is not str)
            or ('icon' in slot and (type(slot['icon']) is not int
                                   or not 0 <= slot['icon'] <= 0x7fffffff))):
        raise ValueError('ATS_WINDOW_SPELL_SLOT')
    if 'name' in slot:
        try:
            slot['name'].encode('utf-8')
        except UnicodeEncodeError as error:
            raise ValueError('ATS_WINDOW_SLOT_NAME') from error


def _window_set_scalars(data, replacements):
    """Change only the last effective occurrence; retain all other wire chunks."""
    chunks = list(_field_chunks(data))
    last = {(n, w): index for index, (n, w, _, _) in enumerate(chunks)}
    result = []
    for index, (number, wire, value, raw) in enumerate(chunks):
        key = (number, wire)
        if key in replacements and last[key] == index and replacements[key] != value:
            raw = field(number, wire, replacements[key])
        result.append(raw)
    for (number, wire), value in replacements.items():
        if (number, wire) not in last:
            result.append(field(number, wire, value))
    return b''.join(result)


def _window_slot(data, selected):
    slot = _slot(data)
    empty = not slot or slot.get(1, 0) == 0 or (
        slot.get(1) in (1, 2) and slot.get(4) == -1)
    if selected is None:
        # Native empty kind1/kind2 sentinels and their ancillary fields stay exact.
        return data if empty else _window_set_scalars(data, {(1, 0): 0, (4, 0): -1})
    template = selected['template']
    same = slot.get(1) == 2 and slot.get(4) == template
    replacements = {(1, 0): 2, (4, 0): template}
    # This window never emits 4ED7/native inventory lookup identities. A new
    # LOCAL selection uses zero identities; existing same-template ones survive.
    for number in (5, 6):
        if not same or number not in slot:
            replacements[number, 0] = 0
    # name is display metadata, not an editor for the opaque native f7. An
    # unchanged selection must survive a catalog label/encoding difference.
    if not same:
        replacements[7, 2] = selected.get('name', '').encode('utf-8')
    return _window_set_scalars(data, replacements)


def _window_spell_slot(data, selected):
    # Only f1/f4 have a confirmed magic selection meaning. Metadata is supplied
    # separately by the server; opaque f5/f6/f7 and unknown fields stay exact.
    slot = _slot(data)
    empty = not slot or slot.get(1, 0) == 0 or (
        slot.get(1) in (1, 2) and slot.get(4) == -1)
    kind, key = slot.get(1, 0), slot.get(4)
    readonly = not empty and (kind != 1 or type(key) is not int or key < 0)
    if readonly and (selected is None or ('template' not in selected and 'spell_key' not in selected)):
        raise ValueError('ATS_WINDOW_READONLY_SLOT_CHANGED')
    if selected is None:
        return data if empty else _window_set_scalars(data, {(1, 0): 0, (4, 0): -1})
    if selected.get('status') == 'UNKNOWN':
        if kind != 1 or key != selected['spell_row']:
            raise ValueError('ATS_WINDOW_READONLY_SLOT_CHANGED')
        return data
    if 'template' in selected:
        if slot.get(1) != 2 or slot.get(4) != selected['template']:
            raise ValueError('ATS_WINDOW_READONLY_ITEM_CHANGED')
        return data
    if 'spell_key' in selected:
        if empty or slot.get(4) != selected['spell_key']:
            raise ValueError('ATS_WINDOW_READONLY_SLOT_CHANGED')
        return data
    return _window_set_scalars(data, {(1, 0): 1, (4, 0): selected['spell_row']})


def _window_slots(data, number, selections, *, spell=False):
    chunks = list(_field_chunks(data))
    existing = [value for n, w, value, _ in chunks if (n, w) == (number, 2)]
    if spell and len(existing) != len(selections):
        raise ValueError('ATS_WINDOW_SPELL_TOPOLOGY')
    if len(existing) > len(selections):
        raise ValueError('ATS_WINDOW_EXISTING_SLOT_COUNT')
    result, index = [], 0
    for n, w, value, raw in chunks:
        if (n, w) == (number, 2):
            rewritten = (_window_spell_slot if spell else _window_slot)(value, selections[index])
            if rewritten != value:
                raw = field(n, w, rewritten)
            index += 1
        result.append(raw)
    # Omitted trailing empty slots have the same view and need no new bytes.
    stop = max([index] + [i + 1 for i, slot in enumerate(selections) if slot is not None])
    for selected in selections[index:stop]:
        slot = _window_slot(b'', selected) if selected is not None else (
            field(1, 0, 0) + field(4, 0, -1))
        result.append(field(number, 2, slot))
    return b''.join(result)


def _window_battle(data, rows):
    """Keep row topology/conditions; patch only the effective slot selection."""
    chunks = list(_field_chunks(data))
    existing = [(n, v) for n, w, v, _ in chunks if w == 2 and n in (1, 2)]
    if len(existing) != len(rows):
        raise ValueError('ATS_WINDOW_BATTLE_TOPOLOGY')
    result, counts, index = [], {1: 0, 2: 0}, 0
    for n, w, value, raw in chunks:
        if w == 2 and n in (1, 2):
            row = rows[index]
            kind = 'sequence' if n == 1 else 'conditional'
            if row['kind'] != kind or row['index'] != counts[n]:
                raise ValueError('ATS_WINDOW_BATTLE_TOPOLOGY')
            if n == 1:
                rewritten = _window_spell_slot(value, row['slot'])
            else:
                children = list(_field_chunks(value))
                conditions = {k: _int32(v) for k, wire, v, _ in children
                              if wire == 0 and k in (1, 2)}
                if (row['condition'] != conditions.get(1)
                        or row['value'] != conditions.get(2)):
                    raise ValueError('ATS_WINDOW_BATTLE_CONDITION_READONLY')
                # decode_options uses the last f3 child. Earlier repeated f3
                # messages retain their bytes, just like repeated scalar fields.
                last = next((i for i in range(len(children) - 1, -1, -1)
                             if children[i][:2] == (3, 2)), None)
                if last is None:
                    if row['slot'] is not None:
                        raise ValueError('ATS_WINDOW_BATTLE_SLOT_MISSING')
                    rewritten = value
                else:
                    child = _window_spell_slot(children[last][2], row['slot'])
                    rewritten = b''.join(field(3, 2, child) if i == last
                                        and child != v else chunk
                                        for i, (k, wire, v, chunk) in enumerate(children))
            if rewritten != value:
                raw = field(n, w, rewritten)
            counts[n] += 1
            index += 1
        result.append(raw)
    return b''.join(result)


def _window_edit_child(data, number, edit):
    """Edit the first child as decode_options does; duplicate messages stay exact."""
    result, found = [], False
    for n, w, value, raw in _field_chunks(data):
        if not found and (n, w) == (number, 2):
            found = True
            rewritten = edit(value)
            if rewritten != value:
                raw = field(n, w, rewritten)
        result.append(raw)
    if not found:
        rewritten = edit(b'')
        if rewritten:
            result.append(field(number, 2, rewritten))
    return b''.join(result)


def apply_window_changes(wrapper: bytes | None, changes: dict) -> bytes:
    """Patch only editable companion ATS window values, preserving unrelated wire.

    ``changes`` excludes member_id/edit_epoch (validated by the server). Only
    scan_tiles (OptionData f1) and pickup_weight (f7) have named policy meanings;
    other option numbers remain opaque/read-only. buff_slots is a full array
    of None or {spell_row, optional name/icon}; battle_slots is a full array
    of {kind, index, slot, and condition/value for conditional rows}, matching
    decode_options encounter order. Only existing magic slots are editable:
    row count/order, kind/index, conditions and condition values cannot change.
    name/icon are validated display metadata and never written into the blob.
    Existing kind2 selections may be echoed as {template, optional name}; an
    unresolved server view {spell_key, spell: None, status: 'invalid'} may also
    be echoed. An unknown kind1 spell may be echoed as {spell_row, name: None,
    icon: None, status: 'UNKNOWN'}. These read-only tokens are checked against
    the original slot and preserve its ancillary bytes. The server identifies
    unknown kind1 spells, validates learned ownership and maps spell_row IDs.
    None starts a minimal companion tree, never an owner configuration clone.
    """
    _window_validate_changes(changes)
    if wrapper is not None and type(wrapper) is not bytes:
        raise ValueError('ATS_WINDOW_WRAPPER')
    payload = unwrap_blob(wrapper) if wrapper is not None else b''
    if wrapper is not None and not changes:
        return wrapper

    def buff(data):
        for key, number in (('hp_slots', 1), ('mp_slots', 3), ('function_slots', 5)):
            if key in changes:
                data = _window_slots(data, number, changes[key])
        if 'buff_slots' in changes:
            data = _window_slots(data, 7, changes['buff_slots'], spell=True)
        percentages = {(number, 5): struct.pack('<f', changes[key])
                       for key, number in (('hp_percent', 2), ('mp_percent', 4))
                       if key in changes}
        return _window_set_scalars(data, percentages)

    def option(data):
        if any(key in changes for key in ('hp_slots', 'mp_slots', 'function_slots',
                                          'hp_percent', 'mp_percent', 'buff_slots')):
            data = _window_edit_child(data, 1, buff)
        if 'battle_slots' in changes:
            data = _window_edit_child(data, 2, lambda value: _window_battle(value, changes['battle_slots']))
        if changes.get('options'):
            replacements = {({'scan_tiles': 1, 'pickup_weight': 7}[key], 0): value & 0xffffffffffffffff
                            for key, value in changes['options'].items()}
            data = _window_edit_child(data, 3, lambda value: _window_set_scalars(value, replacements))
        return data

    chunks = list(_field_chunks(payload))
    sections = [(i, value) for i, (n, w, value, _) in enumerate(chunks) if (n, w) == (1, 2)]
    # decode_options searches all sections for the first option, not necessarily
    # the first section. Preserve every other section/option occurrence verbatim.
    selected = next(((i, value) for i, value in sections if _children(value, 2)),
                    sections[0] if sections else None)
    if selected is None:
        new_option = option(b'')
        rewritten = (payload if wrapper is not None and not new_option else
                     payload + field(1, 2, field(2, 2, new_option)))
    else:
        index, section = selected
        section2 = _window_edit_child(section, 2, option)
        rewritten = b''.join(field(n, w, section2) if i == index and section2 != section else raw
                             for i, (n, w, _, raw) in enumerate(chunks))
    return (wrapper if wrapper is not None and rewritten == payload else wrap_blob(rewritten))
