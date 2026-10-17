"""CP59 world read with precise source-anchor dormancy handling only."""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCH = ROOT / 'tools/local_native_scene_current/watch.py'
WATCH_SHA = 'a748265c8e0f155e4722e0771e54de73e2c4e7aed830ef821ca36031b10c24a6'
PUBLIC = ROOT / 'work/online_public_session-v4/source-contract.json'
PUBLIC_SHA = '5150ac7b24a0497210615876fb6d1560b21ed5e809809434999bbf26f6a2d222'
SOURCE = ROOT / 'work/local_native_world_read_review/source-contract.json'
SOURCE_SHA = '1ed36a8a8a059c141ba98aa9a277cebd0eee7c3011e204de4ef9464580b79784'
PRODUCER = ROOT / 'tools/local_native_world_read/source.py'
PRODUCER_SHA = '6eacf1becbe2603648f31b41bcdc973caf4bec7dc7af5553b7ff55aefd9e76ce'
READ_LIMIT = 20480
TILE_COUNT_LIMIT = 4096
TILE_LOOKUP_LIMIT = 64


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def pinned_json(path, digest):
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == digest, 'FIXED_WORLD_SOURCE_REQUIRED')
    return json.loads(raw)


def contracts():
    need(hashlib.sha256(WATCH.read_bytes()).hexdigest() == WATCH_SHA and
         hashlib.sha256(PRODUCER.read_bytes()).hexdigest() == PRODUCER_SHA,
         'FIXED_WORLD_READER_PRODUCER_REQUIRED')
    return pinned_json(PUBLIC, PUBLIC_SHA), pinned_json(SOURCE, SOURCE_SHA)


def empty_result(reason='WORLD_NOT_INSPECTED'):
    return {'schema': 'lc-owned-world-dormant-read-v1', 'status': 'UNKNOWN', 'reason': reason,
            'scene': 'unknown', 'pending': 'unknown',
            'actor_count': None, 'my_player_count': None, 'my_player_uid': None,
            'expected_uid_match': None, 'segment_key_words': None, 'grid_words': None,
            'coordinate_status': 'UNKNOWN', 'coordinate_reason': reason,
            'coordinate_axis_names': None, 'coordinate_scale_units': None,
            'source_segment_grid_relation_match': None,
            'expected_grid_words_match': None,
            'expected_grid_comparison_is_local_hypothesis': True,
            'map_requested_i32': None, 'map_resolved_i32': None,
            'map_context_present': None, 'map_context_header_i32': None,
            'tile_entry_count': None, 'coordinate_tile_entry_present': None,
            'coordinate_tile_resource_present': None, 'tile_lookup_nodes_read': None,
            'scene_object_present': None, 'land_game_layer_present': None,
            'tile_decode_ready': 'UNKNOWN', 'render_ready': 'UNKNOWN',
            'visible_ui_proven': False, 'actual_gameplay_proven': False,
            'standalone_completion_proven': False, 'snapshot_atomic': False,
            'stable_double_read': False, 'raw_pointers_saved': False,
            'memory_write_or_game_control': False,
            'public_source_sha256': PUBLIC_SHA, 'world_source_sha256': SOURCE_SHA,
            'typed_bytes_requested': 0,
            'diagnostic': empty_diagnostic()}


def table(sampler, row):
    base, size = sampler.g['base'], sampler.g['size']
    raw = sampler.read(base + row['rva'], row['prefix_bytes'], image=True)
    values = struct.unpack('<' + 'Q' * (len(raw) // 8), raw)
    need(all(base <= p < base + size for p in values), 'WORLD_VTABLE_TARGET_BOUNDS')
    normalized = struct.pack('<' + 'Q' * len(values), *(p - base for p in values))
    need(hashlib.sha256(normalized).hexdigest() == row['normalized_sha256'], 'WORLD_VTABLE_SOURCE_CHANGED')


class Reads:
    """Keep typed bytes privately for final rechecks; never return addresses."""
    def __init__(self, sampler):
        self.sampler, self.snapshots, self.owners = sampler, [], []

    def read(self, at, size):
        raw = self.sampler.read(at, size)
        self.snapshots.append((at, raw))
        return raw

    def pointer(self, at, nullable=False):
        value = struct.unpack('<Q', self.read(at, 8))[0]
        need(nullable and value == 0 or 0x10000 <= value <= 0x7fffffffffff and value % 8 == 0,
             'WORLD_POINTER_NONCANONICAL')
        return value

    def pair(self, raw):
        obj, control = self.sampler.strong_pair(raw)
        self.owners.append(raw)
        return obj, control

    def verify(self):
        for at, raw in self.snapshots:
            need(self.sampler.read(at, len(raw)) == raw, 'WORLD_TYPED_READ_CHANGED')
        for raw in self.owners:
            self.sampler.strong_pair(raw)


def vector(reads, owner, begin_offset, end_offset, limit):
    need(end_offset == begin_offset + 8, 'SOURCE_VECTOR_LAYOUT_REQUIRED')
    begin, end = struct.unpack('<QQ', reads.read(owner + begin_offset, 16))
    need(begin == end == 0 or 0x10000 <= begin <= end <= 0x7fffffffffff and
         (begin | end) % 8 == 0 and (end - begin) % 16 == 0, 'WORLD_VECTOR_BOUNDS')
    count = (end - begin) // 16
    need(count <= limit, 'WORLD_VECTOR_COUNT_BOUND')
    return begin, count


def position(sampler, reads, actor, public, source):
    contract = public['Position']
    begin, count = vector(reads, actor, contract['component_begin'], contract['component_end'],
                          contract['max_components'])
    matches = []
    for index in range(count):
        pair = reads.read(begin + index * 16, 16)
        obj, control = reads.pair(pair)
        vft = reads.pointer(obj)
        if vft == sampler.g['base'] + contract['Transform']['rva']:
            matches.append((obj, control))
    if len(matches) != 1:
        return None, None, 'TRANSFORM_ABSENT_OR_DUPLICATE'
    obj, _ = matches[0]
    table(sampler, contract['Transform'])
    need(reads.pointer(obj + contract['borrowed_Actor']) == actor, 'TRANSFORM_BORROWED_ACTOR_MISMATCH')
    raw = reads.read(obj + contract['pair_offset'], contract['pair_bytes'])
    need(len(raw) == 8 and contract['pair_offset'] == source['coordinates']['transform_segment_offset'],
         'SOURCE_COORDINATE_PAIR_REQUIRED')
    grid_raw = reads.read(obj + source['coordinates']['transform_grid_offset'], source['coordinates']['width'])
    return list(struct.unpack('<ii', raw)), list(struct.unpack('<ii', grid_raw)), None


def tile_state(reads, context, words, contract, row):
    head, count = struct.unpack('<QQ', reads.read(context + contract['tree_head'], 16))
    need(0x10000 <= head <= 0x7fffffffffff and head % 8 == 0 and count <= TILE_COUNT_LIMIT,
         'TILE_TREE_COUNT_OR_HEAD_BOUND')
    header = reads.read(head, 26)
    left, root, right = struct.unpack_from('<QQQ', header)
    need(header[contract['sentinel_byte']] == 1, 'TILE_TREE_SENTINEL_REQUIRED')
    need(all(0x10000 <= value <= 0x7fffffffffff and value % 8 == 0
             for value in (left, root, right)), 'TILE_TREE_HEADER_POINTER_BOUND')
    need(count != 0 or left == root == right == head, 'EMPTY_TILE_TREE_INCONSISTENT')
    need(count == 0 or root != head, 'NONEMPTY_TILE_TREE_INCONSISTENT')
    row['tile_entry_count'] = count
    if words is None:
        return
    # This is precisely the source's low32 key, with unknown axes/units.
    key = (((words[0] & 0xffffffff) << 16) | (words[1] & 0xffffffff)) & 0xffffffff
    current, seen, lower, upper = root, set(), -1, 0x100000000
    found = False
    resource = False
    for _ in range(TILE_LOOKUP_LIMIT):
        if current == head:
            break
        need(0x10000 <= current <= 0x7fffffffffff and current % 8 == 0 and current not in seen,
             'TILE_LOOKUP_POINTER_OR_CYCLE')
        need(len(seen) < count, 'TILE_LOOKUP_EXCEEDS_ENTRY_COUNT')
        seen.add(current)
        flag = reads.read(current + contract['sentinel_byte'], 1)
        need(flag == b'\0', 'TILE_NODE_SENTINEL_UNEXPECTED')
        node_key = struct.unpack('<I', reads.read(current + contract['key_u32'], 4))[0]
        need(lower < node_key < upper, 'TILE_TREE_UNSIGNED_ORDER_CHANGED')
        if node_key == key:
            found = True
            pair = reads.read(current + contract['shared_pair'], 16)
            if pair != b'\0' * 16:
                reads.pair(pair)
                resource = True
            break
        if key < node_key:
            upper = node_key
            current = reads.pointer(current + contract['left'])
        else:
            lower = node_key
            current = reads.pointer(current + contract['right'])
    else:
        raise ValueError('TILE_LOOKUP_NODE_BOUND')
    row.update(coordinate_tile_entry_present=found, coordinate_tile_resource_present=resource,
               tile_lookup_nodes_read=len(seen))


def empty_diagnostic():
    return {'stage': 'NOT_INSPECTED', 'source_anchor_total': None,
            'source_anchors_checked': 0, 'source_anchors_readable': 0,
            'source_anchors_dormant': 0, 'source_anchor_index': None,
            'source_anchors_all_live_hash_verified': False,
            'failure_region_conditions': None,
            'dormant_is_execution_evidence': False,
            'dormancy_exception_scope': 'SOURCE_INSTRUCTION_ANCHORS_ONLY'}


def source_anchors(sampler, checks, diagnostic):
    diagnostic.update(stage='SOURCE_ANCHORS', source_anchor_total=len(checks))
    base, size = sampler.g['base'], sampler.g['size']
    for index, check in enumerate(checks):
        diagnostic['source_anchor_index'] = index
        rva, length = check['rva'], check['length']
        need(type(rva) is int and type(length) is int and 0 <= rva < size and
             0 < length <= 15 and rva + length <= size, 'SOURCE_ANCHOR_IMAGE_BOUNDS')
        try:
            raw = sampler.read(base + rva, length, image=True)
            need(hashlib.sha256(raw).hexdigest() == check['sha256'], 'WORLD_RUNTIME_SOURCE_CHANGED')
            diagnostic['source_anchors_readable'] += 1
        except Exception as error:
            region = getattr(error, 'region', None)
            permitted = (getattr(error, 'reason', None) == 'region_not_readable' and
                         isinstance(region, dict) and
                         type(region.get('state')) is int and region['state'] == 0x1000 and
                         type(region.get('type')) is int and region['type'] == 0x1000000 and
                         region.get('image_allocation_matches') is True and
                         region.get('length_fits') is True and region.get('guard') is False and
                         type(region.get('protection')) is int and region['protection'] == 1 and
                         type(region.get('requested_bytes')) is int and region['requested_bytes'] == length)
            if not permitted:
                raise
            diagnostic['source_anchors_dormant'] += 1
        diagnostic['source_anchors_checked'] += 1
    diagnostic['source_anchor_index'] = None
    diagnostic['source_anchors_all_live_hash_verified'] = diagnostic['source_anchors_dormant'] == 0


def inspect_attached(native, sampler, expected_uid=None, expected_grid_words=None):
    """One exact retained-handle sample. Expectations compare; mismatches are observations."""
    row = empty_result()
    diagnostic = empty_diagnostic()
    previous_limit = getattr(sampler, 'read_limit', READ_LIMIT)
    sampler.bytes, sampler.read_limit = 0, READ_LIMIT
    try:
        diagnostic['stage'] = 'SOURCE_CONTRACTS'
        public, source = contracts()
        diagnostic['stage'] = 'HANDLE_AND_EXPECTATIONS'
        need(sampler.b is native and sampler.c is native.contract, 'EXACT_RETAINED_WORLD_READER_REQUIRED')
        need(expected_uid is None or type(expected_uid) is int and 0 <= expected_uid <= 0xffffffffffffffff,
             'EXPECTED_UID_U64_REQUIRED')
        need(expected_grid_words is None or isinstance(expected_grid_words, (tuple, list)) and
             len(expected_grid_words) == 2 and all(type(v) is int and 0 <= v <= 0xffff
                                                for v in expected_grid_words),
             'EXPECTED_GRID_U16_PAIR_REQUIRED')
        diagnostic['stage'] = 'IDENTITY_BEFORE_READ'
        native.validate()
        base = sampler.g['base']
        source_anchors(sampler, source['source_checks'] + source['inherited_source_checks'], diagnostic)
        diagnostic['stage'] = 'ROOT_ROUTE_INITIAL'
        route = sampler.route()
        state = sampler.unique(route[-1], 'GameState')
        diagnostic['stage'] = 'LAND_SCENE'
        scene, scene_raw = sampler.scene(state)
        need(scene['current']['kind'] == 'Land', 'LAND_SCENE_REQUIRED')
        diagnostic['stage'] = 'LAND_OBJECTS'
        reads = Reads(sampler)
        current_pair = reads.read(state + 0x360, 16)
        land, _ = reads.pair(current_pair)
        scene_obj = reads.pointer(land + source['scene']['scene_object_pointer'], nullable=True)
        layer = reads.pointer(land + source['scene']['land_game_layer_pointer'], nullable=True)
        if layer:
            need(reads.pointer(layer) == base + source['GameLayer']['rva'], 'EXACT_LAND_GAME_LAYER_REQUIRED')
            table(sampler, source['GameLayer'])
        row.update(scene='Land', pending=scene['pending']['kind'], scene_object_present=bool(scene_obj),
                   land_game_layer_present=bool(layer))
        diagnostic['stage'] = 'REGISTERED_OWNERS'
        players, maps = [], []
        for pair, vft in route[-2]:
            if vft == base + public['Player']['ActorSubsystem']['rva']:
                players.append(reads.pair(pair)[0])
            if vft == base + public['Map']['table']['rva']:
                maps.append(reads.pair(pair)[0])
        diagnostic['stage'] = 'ACTOR_UID_POSITION'
        if len(players) == 1:
            actor_sub = players[0]
            table(sampler, public['Player']['ActorSubsystem'])
            need(reads.pointer(actor_sub) == base + public['Player']['ActorSubsystem']['rva'],
                 'ACTOR_SUBSYSTEM_OWNER_CHANGED')
            begin, count = vector(reads, actor_sub, public['Player']['vector_begin'],
                                   public['Player']['vector_end'], public['Player']['max_actor_elements'])
            matches = []
            for index in range(count):
                obj, _ = reads.pair(reads.read(begin + index * 16, 16))
                if reads.pointer(obj) == base + public['Player']['MyPlayer']['rva']:
                    matches.append(obj)
            row.update(actor_count=count, my_player_count=len(matches))
            if len(matches) == 1:
                actor = matches[0]
                table(sampler, public['Player']['MyPlayer'])
                uid = struct.unpack('<Q', reads.read(actor + public['Player']['ActorID'], 8))[0]
                segments, grids, reason = position(sampler, reads, actor, public, source)
                row.update(my_player_uid=uid, expected_uid_match=None if expected_uid is None else uid == expected_uid,
                           segment_key_words=segments, grid_words=grids,
                           coordinate_status='OBSERVED' if segments is not None else 'UNKNOWN',
                           coordinate_reason=reason,
                           source_segment_grid_relation_match=None if grids is None else
                           all(0 <= grid <= 0xffff and segment == (grid >> 6) + 0x7e00
                               for segment, grid in zip(segments, grids)),
                           expected_grid_words_match=None if grids is None or expected_grid_words is None
                           else grids == list(expected_grid_words))
        diagnostic['stage'] = 'MAP_TILE'
        if len(maps) == 1:
            obj = maps[0]
            table(sampler, public['Map']['table'])
            need(reads.pointer(obj) == base + public['Map']['table']['rva'], 'MAP_SUBSYSTEM_OWNER_CHANGED')
            context = reads.pointer(obj + public['Map']['context_pointer'], nullable=True)
            row.update(map_context_present=bool(context),
                       map_resolved_i32=struct.unpack('<i', reads.read(obj + public['Map']['field718'], 4))[0],
                       map_requested_i32=struct.unpack('<i', reads.read(obj + 0x71c, 4))[0])
            if context:
                row['map_context_header_i32'] = struct.unpack('<i', reads.read(context, 4))[0]
                tile_state(reads, context, row['segment_key_words'], source['tile_context'], row)
        diagnostic['stage'] = 'TYPED_RECHECK'
        reads.verify()
        diagnostic['stage'] = 'SCENE_RECHECK'
        need(sampler.read(state + 0x360, 36) == scene_raw, 'WORLD_SCENE_CHANGED_AFTER_READ')
        diagnostic['stage'] = 'ROOT_ROUTE_FINAL'
        need(sampler.route() == route, 'WORLD_ROOT_OWNER_CHANGED_AFTER_READ')
        diagnostic['stage'] = 'IDENTITY_AFTER_READ'
        native.validate()
        row.update(status='OBSERVED' if len(players) == len(maps) == 1 and row['my_player_count'] == 1
                   else 'OBSERVED_PARTIAL', reason=None, stable_double_read=True)
        diagnostic['stage'] = 'COMPLETE'
    except Exception as error:
        region = getattr(error, 'region', None)
        if isinstance(region, dict):
            # Native.read supplies these non-address conditions. Omit all other keys.
            diagnostic['failure_region_conditions'] = {
                key: region.get(key) if type(region.get(key)) is int and 0 <= region[key] <= maximum else None
                for key, maximum in (('state', 0xffffffff), ('type', 0xffffffff),
                                     ('protection', 0xffffffff), ('requested_bytes', 4096))}
            diagnostic['failure_region_conditions'].update({
                key: region.get(key) if type(region.get(key)) is bool else None
                for key in ('image_allocation_matches', 'length_fits', 'guard')})
        reason = getattr(error, 'reason', str(error) if isinstance(error, ValueError) else type(error).__name__)
        # Error messages may include addresses. Emit only a bounded symbolic reason.
        if not isinstance(reason, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', reason):
            reason = 'WORLD_READ_FAILED'
        row = empty_result(reason)
    finally:
        row['typed_bytes_requested'] = sampler.bytes
        row['diagnostic'] = diagnostic
        sampler.read_limit = previous_limit
    return row
