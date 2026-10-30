"""Optional pledge backend and preserved native wire shapes.

Rules: official Classic pledge guide (2026-09-01), level5 unpledged prince,
1000 adena, Korean8/ASCII16 name limit. The profile model and positional wire
semantics are LOCAL policy; compiled descriptors alone do not establish them.
"""
from __future__ import annotations

from copy import deepcopy
import struct

from tools.local_entry_server import protobuf as pb

CREATE, JOIN, INFO, LEAVE, NOTICE, LIST = 0x071B, 0x0709, 0x0722, 0x0715, 0x0727, 0x071E
COST, MIN_LEVEL, PRINCE = 1000, 5, 0


class Refused(ValueError):
    """Expected policy refusal; filesystem and inventory owner failures propagate."""


def need(value, code):
    if not value:
        raise Refused(code)


def valid_name(name):
    return (type(name) is str and bool(name)
        and sum(1 if ch.isascii() and ch.isalnum() else 2 for ch in name) <= 16
        and all(ch.isascii() and ch.isalnum() or '\uac00' <= ch <= '\ud7a3' for ch in name))


def empty():
    return dict(next_id=1, clans=[], pending_creation=None)


def validate(value):
    need(type(value) is dict and set(value) == {'next_id', 'clans', 'pending_creation'},
         'PLEDGE_STORE_SCHEMA')
    need(type(value['next_id']) is int and 1 <= value['next_id'] <= 0x7fffffff
         and type(value['clans']) is list, 'PLEDGE_STORE_VALUES')
    ids, names, members = set(), set(), set()
    def clan(row):
        need(type(row) is dict and set(row) == {'id', 'name', 'leader_uid', 'members', 'notice'},
             'PLEDGE_STORE_CLAN')
        need(type(row['id']) is int and 0 < row['id'] < value['next_id']
             and valid_name(row['name']) and type(row['members']) is list
             and bool(row['members']) and len(row['members']) <= 3
             and type(row['leader_uid']) is int and row['leader_uid'] in row['members']
             and all(type(uid) is int and 0 < uid <= 0xffffffff for uid in row['members'])
             and len(set(row['members'])) == len(row['members'])
             and type(row['notice']) is str and len(row['notice']) <= 200
             and len(row['notice'].encode('utf-8')) <= 800
             and not any(ord(ch) < 32 and ch not in '\r\n\t' for ch in row['notice']),
             'PLEDGE_STORE_CLAN_VALUES')
        need(row['id'] not in ids and row['name'].casefold() not in names
             and not members.intersection(row['members']), 'PLEDGE_STORE_DUPLICATE')
        ids.add(row['id']); names.add(row['name'].casefold()); members.update(row['members'])
    for row in value['clans']:
        clan(row)
    pending = value['pending_creation']
    if pending is not None:
        need(type(pending) is dict and set(pending) == {'clan', 'before', 'after'},
             'PLEDGE_PENDING_SCHEMA')
        clan(pending['clan'])
        from tools.local_original_session import inventory
        for key in ('before', 'after'):
            need(type(pending[key]) is str, 'PLEDGE_PENDING_KIT')
            frame = bytes.fromhex(pending[key])
            need(frame.hex() == pending[key], 'PLEDGE_PENDING_KIT')
            inventory.validate_kit_frame(frame)
        before, after, _ = payment(bytes.fromhex(pending['before']))
        need(before.hex() == pending['before'] and after.hex() == pending['after'],
             'PLEDGE_PENDING_PAYMENT')
    return deepcopy(value)


def membership(value, uid):
    return next((row for row in value['clans'] if uid in row['members']), None)


def payment(frame):
    """Prepare the ordinary inventory CAS; adena remains even at quantity0."""
    from tools.local_original_session import inventory, inventory_update
    items = inventory.validate_kit_frame(frame)
    wallets = [item for item in items if item.template_bits == 7]
    need(len(wallets) == 1 and dict(wallets[0].raw_fields)[4] >= COST,
         'PLEDGE_ADENA_1000_REQUIRED')
    wallet = wallets[0]
    rows = [dict(item.raw_fields) for item in items]
    after = next(row for row in rows if row[1] == wallet.identifier)
    after[4] -= COST
    wire = inventory_update._encode(inventory_update._values({1: wallet.identifier, 4: after[4]}))
    return frame, inventory.build_kit_frame(rows), wire


def prepare_creation(value, *, uid, name, character_class, level, frame):
    result = validate(value)
    need(result['pending_creation'] is None, 'PLEDGE_CREATION_PENDING')
    need(character_class == PRINCE, 'PLEDGE_PRINCE_REQUIRED')
    need(level >= MIN_LEVEL, 'PLEDGE_LEVEL_5_REQUIRED')
    need(membership(result, uid) is None, 'PLEDGE_ALREADY_MEMBER')
    need(valid_name(name), 'PLEDGE_NAME_REQUIRED')
    need(all(row['name'].casefold() != name.casefold() for row in result['clans']),
         'PLEDGE_NAME_EXISTS')
    need(result['next_id'] < 0x7fffffff, 'PLEDGE_ID_EXHAUSTED')
    before, after, _ = payment(frame)
    clan = dict(id=result['next_id'], name=name, leader_uid=uid, members=[uid], notice='')
    result['next_id'] += 1
    result['pending_creation'] = dict(clan=clan, before=before.hex(), after=after.hex())
    return validate(result)


def finish_creation(value):
    result = validate(value)
    need(result['pending_creation'] is not None, 'PLEDGE_CREATION_NOT_PENDING')
    result['clans'].append(result['pending_creation']['clan'])
    result['pending_creation'] = None
    return validate(result)


def create(store, *, uid, name, character_class, level, current_frame, replace_kit):
    """Finish one pledge payment through its normal inventory owner.

    pending_creation is part of the existing character document. It records
    only this creation's real before/after kit. It never rolls back inventory.
    The same normal CREATE can finish after a failed final character write;
    an unrelated kit change keeps the pending record and refuses recovery.
    """
    value = store.pledges()
    pending = value['pending_creation']
    if pending is None:
        # The world owner serializes requests; store revalidates the latest
        # document and preserves all unrelated optional character fields.
        value = store.update_pledges(lambda old: prepare_creation(old, uid=uid,
            name=name, character_class=character_class, level=level, frame=current_frame))
        pending = value['pending_creation']
    need(pending['clan']['leader_uid'] == uid and pending['clan']['name'] == name,
         'PLEDGE_DIFFERENT_CREATION_PENDING')
    before, after = bytes.fromhex(pending['before']), bytes.fromhex(pending['after'])
    need(current_frame in (before, after), 'PLEDGE_PENDING_INVENTORY_CHANGED')
    wire = payment(before)[2]
    if current_frame == before:
        need(replace_kit(uid, before, after) is True, 'PLEDGE_PAYMENT_PERSISTED_CHANGE_REQUIRED')
    value = store.update_pledges(finish_creation)
    return value, after, wire


def join(value, leader_uid, member_uid):
    result = validate(value)
    need(result['pending_creation'] is None, 'PLEDGE_CREATION_PENDING')
    clan = membership(result, leader_uid)
    need(clan is not None and clan['leader_uid'] == leader_uid, 'PLEDGE_LEADER_REQUIRED')
    need(membership(result, member_uid) is None, 'PLEDGE_ALREADY_MEMBER')
    clan['members'].append(member_uid)
    return validate(result)


def leave(value, uid):
    result = validate(value)
    need(result['pending_creation'] is None, 'PLEDGE_CREATION_PENDING')
    clan = membership(result, uid)
    need(clan is not None, 'PLEDGE_MEMBERSHIP_REQUIRED')
    if clan['leader_uid'] == uid:
        # LOCAL has no castle/house/pledge warehouse/war ownership subsystem;
        # those absent assets are never manufactured by this backend.
        result['clans'].remove(clan)
    else:
        clan['members'].remove(uid)
    return validate(result)


def notice(value, uid, text):
    result = validate(value)
    need(result['pending_creation'] is None, 'PLEDGE_CREATION_PENDING')
    clan = membership(result, uid)
    need(clan is not None and clan['leader_uid'] == uid, 'PLEDGE_LEADER_REQUIRED')
    clan['notice'] = text
    return validate(result)


def parse_request(opcode, payload):
    """Native compiled field types; field meanings/requiredness are LOCAL.

    CREATE f1=name, f2=0, f3/f4 empty; JOIN f1=pledge name,
    f2=opaque bool, f3 empty; LEAVE f1=pledge name; NOTICE f1=text.
    INFO is empty. No invented packet opcode is introduced.
    """
    schemas = {CREATE: {1: 2, 2: 0, 3: 2, 4: 2}, JOIN: {1: 2, 2: 0, 3: 2},
               INFO: {}, LEAVE: {1: 2}, NOTICE: {1: 2}, LIST: {1: 2}}
    with pb.parse_message(payload, schema=schemas[opcode], limits=pb.WireLimits(
            max_body=1024, max_fields=4, max_field_bytes=800)) as parsed:
        need(len({f.number for f in parsed.fields}) == len(parsed.fields),
             'PLEDGE_REQUEST_DUPLICATE_FIELDS')
        values = {f.number: bytes(f.value).decode('utf-8', 'strict')
                  if f.wire_type == 2 else f.value for f in parsed.fields}
    if opcode not in (INFO, LIST):
        need(1 in values, 'PLEDGE_REQUEST_NAME_OR_TEXT_REQUIRED')
    if opcode == LIST:
        values.setdefault(1, '')
    if opcode == CREATE:
        need(values.get(2, 0) == 0 and not values.get(3, '') and not values.get(4, ''),
             'PLEDGE_CREATE_EXTENSION_UNSUPPORTED')
    if opcode == JOIN:
        # Native UI can omit the bool (defaultfalse). Its meaning is unknown;
        # LOCAL immediate joining accepts either bool, without password mode.
        need(values.get(2, 0) in (0, 1) and not values.get(3, ''), 'PLEDGE_JOIN_MODE_UNSUPPORTED')
    return values


def _body(fields):
    return b''.join(pb.encode_bytes(number, value.encode('utf-8')) if type(value) is str
        else pb.encode_bytes(number, value) if type(value) is bytes
        else pb.encode_varint(number << 3) + pb.encode_varint(value & 0xffffffffffffffff)
        for number, value in fields)


def _frame(opcode, fields):
    body = _body(fields)
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def create_frame(success, name=''):
    # Native5600B0: bool true enters creation-success consumer; f2 is its name.
    return _frame(0x071C, [(1, int(success)), *(((2, name),) if success else ())])


def join_frame(success, name='', *, unknown=False):
    # Native55B2A0: enum0=joined; enum1=application (not success!), enum7=current
    # join unavailable and enum4=nonexistent pledge. See pledge-evidence strings.
    return _frame(0x070A, [(1, 0 if success else 4 if unknown else 7), (2, name)])


def leave_frame(success):
    # Compiled schema is bool; downstream native membership transition remains
    # unverified. The server also publishes its current INFO model separately.
    return _frame(0x0716, [(1, int(success))])


def notice_frame(text):
    # ACK f1 and INFO f7 copy to the same native model+98 string.
    return _frame(0x072B, [(1, text)])


def refusal_frames(opcode, *, name='', reason=''):
    if opcode == CREATE:
        return (create_frame(False),)
    if opcode == JOIN:
        return (join_frame(False, name, unknown=reason == 'PLEDGE_UNKNOWN_NAME'),)
    if opcode == LEAVE:
        return (leave_frame(False),)
    # No success-shaped notice response is sent on refusal or malformed text.
    return ()


def info_frames(clan, characters):
    """Native schema, explicit LOCAL projections for the single-account model.

    INFO f1 uses the same native model string as the LEAVE sender. INFO f7 and
    NOTICE_ACK f1 share the model+98 string. MemberInfo f1 is a LOCAL name
    projection into the preserved string slot. Native page merging deduplicates
    f4 u64, so the saved character UID supplies its distinct LOCAL row key;
    original ID-domain equivalence is unverified. Class/rank/level are omitted.
    """
    info = _frame(0x0723, [(1, '' if clan is None else clan['name']),
                         (7, '' if clan is None else clan['notice'])])
    # Native55CF6F validates page_count>0 and 0<=page_index<page_count. Index0
    # clears the old pages, and one complete page is then consumed by the model.
    rows = [] if clan is None else [_body([(1, characters[uid][1]), (4, uid)])
                                    for uid in clan['members']]
    members = _frame(0x0724, [(1, 1), (2, 0), *((3, row) for row in rows)])
    return info, members


def list_frame(value, search, characters):
    """LOCAL substring search and name projection in BloodPledgeListInfoT f1.

    071E/071F request-response pairing and compiled shapes are preserved. The
    first DTO string is a LOCAL name projection; other metadata is omitted.
    """
    need(type(search) is str and len(search) <= 32, 'PLEDGE_SEARCH_LENGTH')
    return _frame(0x071F, [(1, _body([(1, clan['name'])]))
        for clan in value['clans'] if search.casefold() in clan['name'].casefold()])
