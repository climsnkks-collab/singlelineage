"""Bounded retained read-only movement fields; snapshots are not call witnesses.

Saved run5 nav/update leaves and run5_move_update/MOVE_UPDATE_FINDINGS.md
prove field consumers. Root phase7 and subsystem
+10 gate F6F50; actor component +30 gates 41450; Action +44/+45/+48 gate
96EE0. Immediate 9C010->9B660 bypasses those frame gates. No policy verdict,
new attach, game invocation, heap dump, memory write or packet operation.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[2]
CONTROL = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
SOURCES = {
    'work/local_server_rea_20261016/response_evidence/backward-static.json':
        '51dc5d1b4be9963a8da9a2b57411d7ad0fef8fc54b25e43240cdc3eb2382486e',
    'work/local_server_rea_20261016/run5_move_update/nav_source.json':
        'eed92e6eda3b30173210ad0e1590fd6ca5671679f333c21e7899d417534db85a',
    'work/local_server_rea_20261016/run5_move_update/update_source.json':
        '0179e1d2e5e4fca09f3f7f1f2fe5a36fbd0511aae7db1268be05ceb92511b883',
    'work/local_server_rea_20261016/run5_move_update/update_controller_source.json':
        '72ad5a431c699ee63cec5c9abe835d74a7307dc2d6d348df1bd55558365c0192',
    'work/local_server_rea_20261016/run7_navigation_observation/action_types_source.json':
        '05c5f863757c1920a73e63208cf18ad304cc466a65606790b42d4126bdf0f2d4',
}
ATTACK_SOURCES = {
    'work/local_server_rea_20261016/run25_attack_self_action/commit/source-evidence.json':
        '2484f2052f413e56ca5d86102776d87afa5f731c0c0c3148ebe512834836e897',
    'work/local_server_rea_20261016/run26_attack_target_abi/callee/source-evidence.json':
        '72a7bbb4b86bde449882484f666feb9ba211b1bab52b5b95407726488c12e984',
    'work/local_server_rea_20261016/run31_attack_to_move/source-evidence.json':
        '816e0954502589f95cf594e6dd74c83d3ba8850d51938a94abaaf35481ca7f75',
}
SOURCES.update(ATTACK_SOURCES)
GROUPS = ('controller', 'navigation', 'transform', 'action', 'character_data')
FIELDS = {
    'controller': ('status', 'reason', 'component_update_enabled', 'state_i32', 'command_present',
                   'command_kind', 'command_state_i32', 'command_owner_uid', 'goal_segment', 'goal_grid',
                   'command_target_uid', 'target_segment', 'target_grid'),
    'navigation': ('status', 'reason', 'component_update_enabled', 'target_segment', 'target_grid',
                   'direction_i32', 'direction_known', 'active', 'completion', 'slack_i32', 'tolerance'),
    'transform': ('status', 'reason', 'component_update_enabled', 'current_segment', 'current_grid',
                  'predicted_segment', 'predicted_grid'),
    'action': ('status', 'reason', 'component_update_enabled', 'flag44_u8', 'flag45_u8', 'flag48_u8',
               'flag4f_u8', 'timer_f32', 'timer_reason', 'current', 'queue_count', 'queue_head', 'queue_status', 'queue_reason',
               'busy_source_eval'),
    'character_data': ('status', 'reason', 'subsystem_update_enabled', 'own_uid', 'own_uid_matches_actor',
                       'fallback558_nonzero'),
}
ACTION_FIELDS = ('status', 'reason', 'present', 'kind', 'type_table_rva', 'direction_i32', 'token_u32', 'finished',
                 'phase_u32', 'saved_start_grid', 'predicted_target_grid',
                 'target_segment', 'target_grid', 'observation_scope')
BUSY_FIELDS = ('status', 'value', 'reason', 'actual_call_observed')
READBACK_FIELDS = frozenset((
    'TYPE_IDENTITY', 'TYPE_TABLE', 'OWNER_REFCOUNT', 'VECTOR_HEADER', 'RETAINED_PAIR',
    'ACTOR_UID', 'ACTOR_UPDATE_ENABLED', 'COMPONENT_OWNER', 'COMPONENT_ENABLED',
    'CONTROLLER_COMMAND_AND_STATE', 'COMMAND_COL_POINTER', 'COMMAND_COL', 'COMMAND_RTTI',
    'COMMAND_OWNER_UID', 'COMMAND_TARGET_UID', 'COMMAND_COORDINATE', 'COMMAND_STATE',
    'ACTION_OWNER', 'ACTION_CURRENT', 'ACTION_FINISHED', 'ACTION_FIELDS', 'ACTION_SAVED_COORDINATES',
    'ACTION_FLAGS', 'ACTION_TIMER', 'ACTION_QUEUE_HEADER', 'ACTION_QUEUE_BLOCK', 'ACTION_QUEUE_HEAD',
    'NAVIGATION_STATE', 'TRANSFORM_COORDINATES', 'CHARACTER_UID', 'CHARACTER_UPDATE_ENABLED',
    'CHARACTER_FALLBACK'))

def need(value, reason):
    if not value:
        raise ValueError(reason)

def safe_reason(error):
    value = getattr(error, 'reason', str(error) if isinstance(error, ValueError) else '')
    return value if type(value) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', value) else 'MOVE_STATE_READ_FAILED'

def attack_sources_ready():
    # RetainedSceneReader also pins SOURCES with its existing deny-write handles.
    # Recheck these fixed text contracts within this synchronous attack query.
    for relative, expected in ATTACK_SOURCES.items():
        path = ROOT / relative
        need(0 < path.stat().st_size <= 2 * 1024 * 1024, 'MOVE_SOURCE_BYTE_BOUND')
        need(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'MOVE_SOURCE_CHANGED')

def empty(reason='NOT_SAMPLED', requested=0):
    return dict(status='UNKNOWN', reason=reason, source_contract_valid=False,
                stable_double_read=False, snapshot_atomic=False, typed_bytes_requested=requested,
                actor_uid=None, root_phase=None, actor_subsystem_update_enabled=None,
                **{key: dict(status='UNKNOWN', reason=reason) for key in GROUPS})

def public(row):
    result = empty()
    if type(row) is not dict:
        return result
    field = row.get('typed_read_changed_field')
    if (row.get('status') == 'UNKNOWN' and row.get('reason') == 'MOVE_TYPED_READ_CHANGED'
            and type(field) is str and field in READBACK_FIELDS):
        result['typed_read_changed_field'] = field
    for key in result:
        if key not in GROUPS and key in row:
            value = row[key]
            if value is None or type(value) in (bool, int, str):
                result[key] = value
    for group in GROUPS:
        value = row.get(group)
        if type(value) is not dict:
            continue
        filtered = {}
        for key in FIELDS[group]:
            item = value.get(key)
            if key in ('current', 'queue_head') and type(item) is dict:
                filtered[key] = {name: item[name] for name in ACTION_FIELDS if name in item}
            elif key == 'busy_source_eval':
                filtered[key] = ({name: item[name] for name in BUSY_FIELDS if name in item}
                                 if type(item) is dict else dict(status='UNKNOWN', value=None,
                                     reason='ACTION_STATE_UNKNOWN', actual_call_observed=False))
            elif item is None or type(item) in (bool, int, str) or type(item) is float and math.isfinite(item):
                filtered[key] = item
            elif type(item) is list and len(item) == 2 and all(type(n) is int and -(1 << 31) <= n < (1 << 31) for n in item):
                filtered[key] = list(item)
        result[group] = filtered
    return result

def busy_source_eval(current, flag4f, queue_count=None, head=None):
    """Static 99290/99390 evaluation of one stable snapshot, never a call witness.

    Only exact qualified types are used: an arbitrary unrecognized vptr does
    not prove the RTTI Breath/ChangeDirection casts would fail.
    """
    def result(value, reason):
        return dict(status='UNKNOWN' if value is None else 'EVALUATED', value=value,
                    reason=reason, actual_call_observed=False)
    if type(current) is not dict or current.get('status') != 'OBSERVED':
        return result(None, 'CURRENT_ACTION_NOT_SOURCE_QUALIFIED')
    if current.get('present') is False:
        return result(False, 'SOURCE_CURRENT_NULL')
    if current.get('kind') == 'BreathAction':
        return result(False, 'SOURCE_CURRENT_BREATH')
    if current.get('kind') != 'DefaultAction':
        return result(None, 'CURRENT_ACTION_PREDICATE_NOT_SUPPORTED')
    finished = current.get('finished')
    if type(finished) is not bool:
        return result(None, 'SOURCE_FINISHED_UNKNOWN')
    if not finished:
        return result(True, 'SOURCE_DEFAULT_UNFINISHED')
    if type(flag4f) is not int or not 0 <= flag4f <= 255:
        return result(None, 'SOURCE_FLAG4F_UNKNOWN')
    if flag4f:
        return result(False, 'SOURCE_DEFAULT_FINISHED_FLAG4F')
    if type(queue_count) is not int or not 0 <= queue_count <= (1 << 64) - 1:
        return result(None, 'SOURCE_QUEUE_COUNT_UNKNOWN')
    if queue_count == 0:
        return result(False, 'SOURCE_DEFAULT_FINISHED_QUEUE_EMPTY')
    if queue_count > 1:
        return result(True, 'SOURCE_DEFAULT_FINISHED_QUEUE_MULTIPLE')
    if type(head) is not dict or head.get('status') != 'OBSERVED' or head.get('present') is not True:
        return result(None, 'SOURCE_SINGLE_HEAD_TYPE_UNKNOWN')
    if head.get('kind') == 'BreathAction':
        return result(False, 'SOURCE_DEFAULT_FINISHED_SINGLE_BREATH')
    if head.get('kind') in ('DefaultAction', 'MovingAction'):
        return result(True, 'SOURCE_DEFAULT_FINISHED_SINGLE_NONBREATH')
    return result(None, 'SOURCE_SINGLE_HEAD_TYPE_UNKNOWN')

class MoveState:
    def __init__(self):
        documents = []
        for relative, expected in SOURCES.items():
            path = ROOT / relative
            need(0 < path.stat().st_size <= 2 * 1024 * 1024, 'MOVE_SOURCE_BYTE_BOUND')
            raw = path.read_bytes()
            need(hashlib.sha256(raw).hexdigest() == expected, 'MOVE_SOURCE_CHANGED')
            document = json.loads(raw)
            need(document['CONTROL_sha256'] == CONTROL, 'MOVE_SOURCE_CONTROL_CHANGED')
            documents.append(document)
        backward, nav, update, command, action_types, attack_commit, attack_fields, attack_cleanup = documents
        self.tables = {}
        for role in ('ActorControllerComponent', 'NavigationComponent', 'TransformComponent', 'ActionComponent', 'CharacterDataSubsystem'):
            rows = nav['types'][role]['tables']
            need(len(rows) == 1, 'MOVE_SOURCE_TYPE_AMBIGUOUS')
            self.tables[role] = dict(rva=int(rows[0]['vptr_rva'], 16),
                                    targets=[int(v, 16) for v in rows[0]['methods']])
        for role in ('ActorSubsystem', 'MyPlayer'):
            rows = [r for r in update['tables'] if r['role'] == role]
            need(len(rows) == 1, 'MOVE_SOURCE_TYPE_AMBIGUOUS')
            self.tables[role] = dict(rva=int(rows[0]['vptr_rva'], 16),
                                    targets=[int(v, 16) for v in rows[0]['methods']])
        self.tables['MoveCommand'] = dict(rva=int(command['table']['rva'], 16),
                                        targets=[int(v, 16) for v in command['table']['slots']])
        attack_rtti = attack_cleanup['AttackCommand_RTTI']
        attack_targets = [0xa0f50, 0xa0f80, 0xa11a0, 0xa17b0, 0xa1d90]
        attack_slots = [dict(offset=hex(i * 8), target_rva=hex(v)) for i, v in enumerate(attack_targets)]
        need(attack_rtti == dict(vptr_rva='0x1181040', COL_rva='0x127a398',
                 COL_sha256='368d92b41b20feee03a01943e38fe4bc10d3c0542ab6afcbb2f3093bc94e0529',
                 type_descriptor_rva='0x166b830', name='.?AVAttackCommand@ActorControllerComponent@lineage@@')
             and attack_cleanup['table'] == dict(rva='0x1181040', slots=attack_slots,
                 normalized_rva64_sha256='8cb32e2289f8725c6e8f07b2094fb1b68fade52e945dd3c8cf49a155ed8e73ff')
             and [r for r in attack_commit['types'] if r['vptr_rva'] == '0x1181040'] == [dict(
                 vptr_rva='0x1181040', type_descriptor_rva=attack_rtti['type_descriptor_rva'],
                 name=attack_rtti['name'], slots=attack_slots,
                 table40_sha256='1ab4eec07d82e61c967355508f723d310daa6cad7db2fd56960a71f3f2cd4689')],
             'MOVE_ATTACK_SOURCE_TYPE_CHANGED')
        instructions = {r['rva']: (r['mnemonic'], r['op'])
                        for r in attack_fields['windows'][0]['instructions']}
        need(instructions['0xa3742'] == ('mov', 'qword ptr [r14 + 0x18], rax')
             and instructions['0xa37d3'] == ('call', '0x414a0')
             and instructions['0xa37e7'] == ('vmovsd', 'qword ptr [r14 + 0x40], xmm1')
             and instructions['0xa387d'] == ('mov', 'qword ptr [rbx + 0x10], rax'),
             'MOVE_ATTACK_SOURCE_FIELDS_CHANGED')
        self.tables['AttackCommand'] = dict(rva=0x1181040, targets=attack_targets)
        self.attack_rtti = attack_rtti
        expected = {'ActorControllerComponent': 0x1181010, 'NavigationComponent': 0x11816b8,
                    'TransformComponent': 0x1181738, 'ActionComponent': 0x1180df0,
                    'CharacterDataSubsystem': 0x1185340, 'ActorSubsystem': 0x117ead8,
                    'MyPlayer': 0x11819f0, 'MoveCommand': 0x1180ec0}
        need(all(self.tables[k]['rva'] == v for k, v in expected.items()), 'MOVE_SOURCE_TYPES_CHANGED')
        # Pin the concrete gate/owner consumer bodies via the saved source files;
        # static agreement does not claim these bodies ran in this process.
        need({'0x41450', '0xf6f50', '0xed500', '0x96ee0', '0x908a0', '0x94570'} <=
             {f['rva'] for f in update['functions']}, 'MOVE_SOURCE_CONSUMERS_MISSING')
        need(action_types['schema'] == 'actual22-action-type-static-hints-v1'
             and len(action_types['types']) == 2, 'MOVE_ACTION_SOURCE_SCHEMA_CHANGED')
        self.action_tables = {}
        for row in action_types['types']:
            kind = {'.?AVDefaultAction@lineage@@': 'DefaultAction',
                    '.?AVBreathAction@lineage@@': 'BreathAction'}.get(row['type_name'])
            rva = int(row['vptr_rva'], 16)
            need(kind is not None and rva == {'DefaultAction': 0x1180938, 'BreathAction': 0x1180a10}[kind]
                 and len(row['slots']) == 8, 'MOVE_ACTION_SOURCE_TYPE_CHANGED')
            self.action_tables[rva] = dict(kind=kind, targets=[int(v, 16) for v in row['slots']])
        need(len(self.action_tables) == 2, 'MOVE_ACTION_SOURCE_TYPE_CHANGED')
        backward_type = backward.get('backward_action', {})
        backward_slots = [0x954c0, 0x95510, 0x95680, 0x8f8f0, 0x95660, 0x95650, 0x95690, 0x8f900]
        need(backward.get('schema') == 'bounded-self-response-static-v1'
             and backward_type == dict(vptr='0x1180c60', td='0x16d0760',
                 name='.?AVMovingBackAction@lineage@@', slots=[hex(v) for v in backward_slots]),
             'MOVE_BACKWARD_SOURCE_TYPE_CHANGED')
        # 95690 copies ActionData's Coordinate40B to +80. 95510 reads the
        # component owner at +8 and consumes that Coordinate through C0E90.
        need({f['rva']: f['sha256'] for f in backward['functions'] if f['rva'] in
              ('0x95510', '0x95690', '0x977f0')} == {
            '0x95510': 'bc4364f153f19f80eeec2beb81f895edd8f862fc44cbd287c0058f04ca13c7e5',
            '0x95690': '7f8d5c4582b27c5a4684fa0df2df0472f3632dd5032b2028514b189201989f35',
            '0x977f0': 'a094dfd304b790d22b425bf0b3096f6d282397a4c719434328958d51883364b7'},
            'MOVE_BACKWARD_SOURCE_CONSUMERS_CHANGED')
        self.action_tables[0x1180c60] = dict(kind='MovingBackAction', targets=backward_slots)

        need({f['rva']: f['sha256'] for f in action_types['predicate_functions']} == {
            '0x99290': 'fdd8f661329e7f1a97e53658f82b12af9cc3220d5f7e2a85b3406ef0606907ec',
            '0x99390': '8fd0ad30213692a0db3651a9add7d1536194b7bfcaab9c8c274e8a15af9e6375'},
            'MOVE_BUSY_SOURCE_PREDICATE_CHANGED')

    def sample(self, reader, scene_row, world_row, proof, cache=None):
        sampler = reader.sampler
        started, previous_bytes = sampler.total, getattr(sampler, 'bytes', 0)
        previous_limit = getattr(sampler, 'read_limit', 8192)
        sampler.bytes, sampler.read_limit = 0, 8192
        result = empty()
        records = {}
        record_fields, readback_field = {}, None
        attack_observed = False
        base = sampler.g['base']
        try:
            limit = reader.sample_byte_limit
            need(limit == 16384 and sampler.b is reader.backend and sampler.c is reader.contract,
                 'MOVE_EXACT_RETAINED_SAMPLER_REQUIRED')
            need(scene_row.get('status') == 'OBSERVED' and scene_row.get('current') == 'Land'
                 and scene_row.get('pending') == 'none' and scene_row.get('root_ready') is True,
                 'MOVE_STABLE_LAND_REQUIRED')
            need(world_row.get('status') == 'OBSERVED' and world_row.get('stable_double_read') is True,
                 'MOVE_CURRENT_WORLD_PROOF_REQUIRED')
            route, state, raw = proof.get('route'), proof.get('state'), proof.get('raw')
            need(type(route) is tuple and route[1] is True and type(state) is int
                 and type(raw) is bytes and len(raw) == 36, 'MOVE_CURRENT_SCENE_PROOF_REQUIRED')
            scene = proof.get('scene')
            need(type(scene) is dict and scene.get('current', {}).get('kind') == 'Land'
                 and scene.get('pending', {}).get('kind') == 'none'
                 and struct.unpack_from('<I', raw, 32)[0] == 5, 'MOVE_SCENE_PROOF_DISAGREES')
            need(type(base) is int and base % 65536 == 0
                 and sampler.g['size'] == reader.contract['image_size'], 'MOVE_IMAGE_BOUNDS_REQUIRED')
            reader.validate()
            def read(at, size, image=False, *, field='TYPE_IDENTITY'):
                need(type(at) is int and 0x10000 <= at <= 0x7fffffffffff - size
                     and type(size) is int and 0 < size <= 4096, 'MOVE_TYPED_READ_BOUND')
                key = (at, size, image)
                if key in records:
                    return records[key]
                value = (cache or {}).get(key)
                if value is None:
                    need(sampler.total + size <= limit, 'MOVE_COMBINED_BYTE_BOUND')
                    value = sampler.read(at, size, image=image)
                need(type(value) is bytes and len(value) == size, 'MOVE_PARTIAL_TYPED_READ')
                records[key] = value
                record_fields[key] = field
                return value
            def number(at, fmt, field='TYPE_IDENTITY'):
                return struct.unpack(fmt, read(at, struct.calcsize(fmt), field=field))[0]
            def pointer_value(value, nullable=False):
                need((nullable and value == 0) or 0x10000 <= value <= 0x7fffffffffff and value % 8 == 0,
                     'MOVE_POINTER_NONCANONICAL')
                return value
            def pointer(at, nullable=False, field='TYPE_IDENTITY'):
                return pointer_value(number(at, '<Q', field), nullable)
            def pair(raw_pair):
                obj, control = struct.unpack('<QQ', raw_pair)
                pointer_value(obj); pointer_value(control)
                need(number(control + 8, '<i', 'OWNER_REFCOUNT') > 0, 'MOVE_STRONG_OWNER_NOT_POSITIVE')
                return obj
            def table(role):
                row = self.tables[role]
                expected = struct.pack('<' + 'Q' * len(row['targets']), *(base + v for v in row['targets']))
                need(read(base + row['rva'], len(expected), True, field='TYPE_TABLE') == expected, 'MOVE_TYPE_TABLE_CHANGED')
            def typed(obj, role):
                need(pointer(obj) == base + self.tables[role]['rva'], 'MOVE_OBJECT_TYPE_CHANGED')
                table(role)
            def vector(owner, offset, bound):
                begin, end = struct.unpack('<QQ', read(owner + offset, 16, field='VECTOR_HEADER'))
                need((begin == end == 0) or 0x10000 <= begin <= end <= 0x7fffffffffff
                     and (begin | end) % 8 == 0 and (end - begin) % 16 == 0,
                     'MOVE_VECTOR_BOUNDS')
                need((end - begin) // 16 <= bound, 'MOVE_VECTOR_COUNT_BOUND')
                return [pair(read(at, 16, field='RETAINED_PAIR')) for at in range(begin, end, 16)]
            subsystems = {}
            for role in ('ActorSubsystem', 'CharacterDataSubsystem'):
                matches = [pair(p) for p, vp in route[-2] if vp == base + self.tables[role]['rva']]
                need(len(matches) == 1, 'MOVE_UNIQUE_SUBSYSTEM_REQUIRED')
                subsystems[role] = matches[0]; typed(matches[0], role)
            actor_sub = subsystems['ActorSubsystem']
            actors = vector(actor_sub, 0x8a8, 512)  # Existing public world actor bound.
            players = [actor for actor in actors if pointer(actor) == base + self.tables['MyPlayer']['rva']]
            need(len(players) == 1, 'MOVE_UNIQUE_MYPLAYER_REQUIRED')
            actor = players[0]; typed(actor, 'MyPlayer')
            uid = number(actor + 0x18, '<Q', 'ACTOR_UID')
            need(0 <= uid <= (1 << 64) - 1 and uid == world_row.get('my_player_uid'), 'MOVE_CURRENT_UID_MISMATCH')
            components = vector(actor, 0x20, 128)
            component_types = [(obj, pointer(obj)) for obj in components]
            result.update(actor_uid=uid, root_phase=route[2], source_contract_valid=True,
                          actor_subsystem_update_enabled=number(actor_sub + 0x10, '<B', 'ACTOR_UPDATE_ENABLED') != 0)
            def component(role):
                matches = [obj for obj, vp in component_types if vp == base + self.tables[role]['rva']]
                need(len(matches) == 1, 'MOVE_UNIQUE_COMPONENT_REQUIRED')
                obj = matches[0]; typed(obj, role)
                need(pointer(obj + 8, field='COMPONENT_OWNER') == actor, 'MOVE_COMPONENT_BORROWED_ACTOR_MISMATCH')
                return obj, number(obj + 0x30, '<B', 'COMPONENT_ENABLED') != 0
            def action_info(action, owner, *, current=False):
                if not action:
                    return dict(status='OBSERVED', reason=None, present=False, kind='none', type_table_rva=None)
                vp = pointer(action)
                # The already-read vptr supplies a bounded image-relative
                # lookup hint only. It does not validate an unknown action type.
                type_table_rva = vp - base if base <= vp < base + sampler.g['size'] else None
                qualified = self.action_tables.get(type_table_rva)
                if qualified is not None:
                    targets = qualified['targets']
                    expected = struct.pack('<8Q', *(base + target for target in targets))
                    need(read(base + type_table_rva, 64, True, field='TYPE_TABLE') == expected, 'MOVE_ACTION_TYPE_TABLE_CHANGED')
                    if qualified['kind'] == 'MovingBackAction':
                        need(pointer(action + 8, field='ACTION_OWNER') == owner, 'MOVE_ACTION_COMPONENT_OWNER_MISMATCH')
                        coordinate = read(action + 0x80, 40, field='ACTION_SAVED_COORDINATES')
                        # These signed source fields are a read-only target snapshot,
                        # not local map acceptance or a Start/packet-consumption witness.
                        return dict(status='OBSERVED', reason=None, present=True, kind='MovingBackAction',
                            type_table_rva=type_table_rva, observation_scope='READONLY_SNAPSHOT',
                            target_segment=list(struct.unpack_from('<ii', coordinate)),
                            target_grid=list(struct.unpack_from('<ii', coordinate, 8)))
                    # Neither predicate consumes action+8. Lifetime is bound by
                    # the current/head pointer topology and final byte rechecks.
                    finished = (number(action + 0x24, '<B', 'ACTION_FINISHED') != 0
                                if current and qualified['kind'] == 'DefaultAction' else None)
                    return dict(status='OBSERVED', reason=None, present=True, kind=qualified['kind'],
                                type_table_rva=type_table_rva, finished=finished)
                if vp != base + 0x1180ca8:
                    return dict(status='UNKNOWN', reason='ACTION_TYPE_NOT_PINNED', present=True, kind='unknown',
                                type_table_rva=type_table_rva)
                need(struct.unpack('<Q', read(base + 0x1180ca8 + 8, 8, True, field='TYPE_TABLE'))[0] == base + 0x94570,
                     'MOVE_MOVING_START_SLOT_CHANGED')
                need(pointer(action + 8, field='ACTION_OWNER') == owner, 'MOVE_ACTION_COMPONENT_OWNER_MISMATCH')
                fields = read(action + 0x18, 13, field='ACTION_FIELDS')
                saved = read(action + 0x80, 84, field='ACTION_SAVED_COORDINATES')
                return dict(status='OBSERVED', reason=None, present=True, kind='MovingAction', type_table_rva=type_table_rva,
                    direction_i32=struct.unpack_from('<i', fields)[0], token_u32=struct.unpack_from('<I', fields, 8)[0],
                    finished=fields[12] != 0, phase_u32=struct.unpack_from('<I', saved)[0],
                    saved_start_grid=list(struct.unpack_from('<ii', saved, 12)),
                    predicted_target_grid=list(struct.unpack_from('<ii', saved, 52)))
            def controller():
                nonlocal attack_observed
                obj, enabled = component('ActorControllerComponent')
                command, state_i32 = struct.unpack('<Qi', read(obj + 0x58, 12, field='CONTROLLER_COMMAND_AND_STATE'))
                pointer_value(command, True)
                out = dict(status='OBSERVED', reason=None, component_update_enabled=enabled,
                           state_i32=state_i32, command_present=bool(command), command_kind='none')
                if command:
                    command_type = pointer(command)
                    if command_type == base + self.tables['AttackCommand']['rva']:
                        attack_observed = True
                        attack_sources_ready()
                        typed(command, 'AttackCommand')
                        rtti = self.attack_rtti
                        need(struct.unpack('<Q', read(base + self.tables['AttackCommand']['rva'] - 8, 8, True, field='COMMAND_COL_POINTER'))[0]
                             == base + int(rtti['COL_rva'], 16),
                             'MOVE_ATTACK_COL_POINTER_CHANGED')
                        need(hashlib.sha256(read(base + int(rtti['COL_rva'], 16), 24, True, field='COMMAND_COL')).hexdigest()
                             == rtti['COL_sha256'], 'MOVE_ATTACK_COL_CHANGED')
                        literal = rtti['name'].encode('ascii') + b'\0'
                        need(read(base + int(rtti['type_descriptor_rva'], 16) + 16, len(literal), True, field='COMMAND_RTTI') == literal,
                             'MOVE_ATTACK_RTTI_CHANGED')
                        command_uid = number(command + 0x10, '<Q', 'COMMAND_OWNER_UID')
                        need(command_uid == uid, 'MOVE_COMMAND_OWNER_UID_MISMATCH')
                        target_uid = number(command + 0x18, '<Q', 'COMMAND_TARGET_UID')
                        coordinate = read(command + 0x20, 40, field='COMMAND_COORDINATE')
                        out.update(command_kind='AttackCommand', command_owner_uid=command_uid,
                            command_state_i32=number(command + 8, '<i', 'COMMAND_STATE'), command_target_uid=target_uid,
                            target_segment=list(struct.unpack_from('<ii', coordinate)),
                            target_grid=list(struct.unpack_from('<ii', coordinate, 8)))
                    elif command_type != base + self.tables['MoveCommand']['rva']:
                        out.update(command_kind='unknown', reason='COMMAND_TYPE_NOT_PINNED')
                    else:
                        typed(command, 'MoveCommand')
                        command_uid = number(command + 0x10, '<Q', 'COMMAND_OWNER_UID')
                        need(command_uid == uid, 'MOVE_COMMAND_OWNER_UID_MISMATCH')
                        goal = read(command + 0x18, 40, field='COMMAND_COORDINATE')
                        out.update(command_kind='MoveCommand', command_owner_uid=command_uid,
                            command_state_i32=number(command + 8, '<i', 'COMMAND_STATE'),
                            goal_segment=list(struct.unpack_from('<ii', goal)), goal_grid=list(struct.unpack_from('<ii', goal, 8)))
                return out
            def navigation():
                obj, enabled = component('NavigationComponent'); data = read(obj + 0x1c0, 60, field='NAVIGATION_STATE')
                direction = struct.unpack_from('<i', data, 40)[0]
                return dict(status='OBSERVED', reason=None, component_update_enabled=enabled,
                    target_segment=list(struct.unpack_from('<ii', data)), target_grid=list(struct.unpack_from('<ii', data, 8)),
                    direction_i32=direction, direction_known=0 <= direction <= 8, active=data[44] != 0,
                    completion=data[45] != 0, slack_i32=struct.unpack_from('<i', data, 48)[0],
                    tolerance=list(struct.unpack_from('<ii', data, 52)))
            def transform():
                obj, enabled = component('TransformComponent'); data = read(obj + 0x38, 80, field='TRANSFORM_COORDINATES')
                return dict(status='OBSERVED', reason=None, component_update_enabled=enabled,
                    current_segment=list(struct.unpack_from('<ii', data)), current_grid=list(struct.unpack_from('<ii', data, 8)),
                    predicted_segment=list(struct.unpack_from('<ii', data, 40)), predicted_grid=list(struct.unpack_from('<ii', data, 48)))
            def action():
                obj, enabled = component('ActionComponent'); flags = read(obj + 0x44, 12, field='ACTION_FLAGS')
                out = dict(status='OBSERVED', reason=None, component_update_enabled=enabled,
                    flag44_u8=flags[0], flag45_u8=flags[1], flag48_u8=flags[4], flag4f_u8=flags[11],
                    current=action_info(pointer(obj + 0xc0, True, field='ACTION_CURRENT'), obj, current=True))
                # Independent telemetry is not a 99290/99390 input. Do not read
                # it into the strict admission snapshot or claim a stable value.
                out.update(timer_f32=None, timer_reason='ACTION_TIMER_NOT_SAMPLED')
                try:
                    header = read(obj + 0xa0, 32, field='ACTION_QUEUE_HEADER'); map_ptr, map_size, off, count = struct.unpack('<QQQQ', header)
                    out['queue_count'] = count
                    if not count:
                        head = dict(status='OBSERVED', reason=None, present=False, kind='none')
                    else:
                        need(0 < map_size <= 4096 and map_size & (map_size - 1) == 0
                             and count <= map_size * 2, 'MOVE_DEQUE_HEAD_BOUND')
                        pointer_value(map_ptr)
                        block = pointer(map_ptr + ((off >> 1) & (map_size - 1)) * 8, field='ACTION_QUEUE_BLOCK')
                        head = action_info(pointer(block + (off & 1) * 8, True, field='ACTION_QUEUE_HEAD'), obj)
                    out.update(queue_status='OBSERVED', queue_reason=None, queue_head=head)
                except Exception as error:
                    out.update(queue_status='UNKNOWN', queue_reason=safe_reason(error))
                out['busy_source_eval'] = busy_source_eval(out['current'], out['flag4f_u8'],
                                                           out.get('queue_count'), out.get('queue_head'))
                return out
            def character():
                obj = subsystems['CharacterDataSubsystem']; own_uid = number(obj + 0x6d8, '<Q', 'CHARACTER_UID')
                return dict(status='OBSERVED', reason=None, subsystem_update_enabled=number(obj + 0x10, '<B', 'CHARACTER_UPDATE_ENABLED') != 0,
                    own_uid=own_uid, own_uid_matches_actor=own_uid == uid, fallback558_nonzero=number(obj + 0x558, '<B', 'CHARACTER_FALLBACK') != 0)
            for group, collect in (('controller', controller), ('navigation', navigation), ('transform', transform),
                                   ('action', action), ('character_data', character)):
                try:
                    result[group] = collect()
                except Exception as error:
                    result[group] = dict(status='UNKNOWN', reason=safe_reason(error))
            # Same-tick cached world topology is only an initial value. Re-read
            # every used byte directly and verify the full retained root/scene.
            for (at, length, image), expected in records.items():
                need(sampler.total + length <= limit, 'MOVE_COMBINED_BYTE_BOUND')
                if sampler.read(at, length, image=image) != expected:
                    readback_field = record_fields[(at, length, image)]
                    raise ValueError('MOVE_TYPED_READ_CHANGED')
            need(sampler.read(state + 0x360, 36) == raw and sampler.route() == route,
                 'MOVE_ROOT_OR_SCENE_CHANGED')
            reader.validate()
            if attack_observed:
                attack_sources_ready()
            observed = sum(result[group].get('status') == 'OBSERVED' for group in GROUPS)
            result.update(status='OBSERVED' if observed == len(GROUPS) else 'OBSERVED_PARTIAL',
                          reason=None if observed == len(GROUPS) else 'MOVE_FIELDS_PARTIAL', stable_double_read=True)
            result['typed_bytes_requested'] = sampler.total - started
            return public(result)
        except Exception as error:
            out = empty(safe_reason(error), max(0, sampler.total - started))
            if readback_field is not None:
                out['typed_read_changed_field'] = readback_field
            return out
        finally:
            sampler.bytes, sampler.read_limit = previous_bytes, previous_limit
