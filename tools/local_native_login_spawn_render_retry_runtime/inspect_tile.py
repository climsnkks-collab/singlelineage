"""One direction0 tile flag sample on the caller's exact retained read handle.

No process attachment, internal calls, input, memory writes, packets or CLI.
"""
import hashlib
import importlib.util
import json
import re
import struct
import marshal
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'tools/local_native_world_read_dormant/inspect_world.py'
WORLD_SHA = '2efe6636744eb646cb13259531828ecd9c8011b6de49d331e2129c7dc2789dcf'
SOURCE = ROOT / 'work/local_tile_passability_review/source-contract.json'
SOURCE_SHA = '8d91282407797d48bc6fc884bd5ff7ae1beb2f295e5edccff9abae939734e1a2'
LIMIT = 20480
SAMPLER = ROOT / 'tools/online_intro_capture_20261006/sampler.py'
SAMPLER_SHA = '2253337013d3cfc0a12bcc5c6798fb56ebf0de333ed6517950dbc692e9d2cdeb'

def install_tile_read_budget(sampler):
    """Scope CP59's 20KiB typed budget to this call; keep contract/total/native read guards."""
    need(hashlib.sha256(SAMPLER.read_bytes()).hexdigest() == SAMPLER_SHA,
         'FIXED_TYPED_SAMPLER_REQUIRED')
    spec = importlib.util.spec_from_file_location('_cp70_fixed_sampler', SAMPLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = sampler.read
    need(isinstance(original, types.MethodType) and original.__self__ is sampler and
         marshal.dumps(original.__func__.__code__) == marshal.dumps(module.Sampler.read.__code__),
         'EXACT_TYPED_SAMPLER_READ_REQUIRED')
    need(sampler.c is sampler.b.contract and sampler.c['bounds']['typed_byte_limit'] == 8192 and
         type(sampler.total) is int and sampler.total >= 0,
         'FIXED_SCENE_TYPED_BUDGET_REQUIRED')
    had_instance_read = 'read' in sampler.__dict__
    def bounded_read(at, size, image=False):
        module.need(0 < size <= 4096, 'fixed_typed_read_size')
        module.need(sampler.bytes + size <= min(LIMIT, sampler.read_limit), 'sample_byte_budget')
        module.need(sampler.total + size <= sampler.c['bounds']['total_typed_byte_limit'],
                    'total_byte_budget')
        sampler.bytes += size
        sampler.total += size
        return sampler.b.read(at, size, sampler.g['base'] if image else None)
    sampler.read = bounded_read
    def restore():
        if had_instance_read:
            sampler.read = original
        else:
            del sampler.read
    return restore
GRID = [32571, 32950]
SEGMENT = [32764, 32770]
DELTAS = ((0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1))
EVEN = ((0,0),(1,0),(0,1),(-1,0))
ODD = (((1,-1),(1,0),(-1,0),(-1,-1)),
       ((0,0),(0,1),(-2,1),(-2,0)),
       ((2,0),(2,1),(0,1),(0,0)),
       ((1,0),(1,1),(-1,1),(-1,0)))

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def load_world():
    need(hashlib.sha256(WORLD.read_bytes()).hexdigest() == WORLD_SHA,
         'FIXED_CP59_WORLD_READER_REQUIRED')
    spec = importlib.util.spec_from_file_location('_cp61_world_read', WORLD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def contract():
    raw = SOURCE.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == SOURCE_SHA, 'FIXED_TILE_SOURCE_REQUIRED')
    return json.loads(raw)

def map_step(grid, direction):
    need(isinstance(grid, (list, tuple)) and len(grid) == 2 and
         all(type(n) is int and 0 <= n <= 65535 for n in grid), 'GRID_U16_PAIR_REQUIRED')
    need(type(direction) is int and 0 <= direction < 8, 'DIRECTION_0_TO_7_REQUIRED')
    dx, dy = DELTAS[direction]
    target = [grid[0] + dx, grid[1] + dy]
    need(all(0 <= n <= 65535 for n in target), 'ONE_STEP_GRID_BOUNDARY')
    return {'direction': direction, 'grid_start': list(grid), 'grid_target': target,
            'segment_start': [(n >> 6) + 0x7e00 for n in grid],
            'segment_target': [(n >> 6) + 0x7e00 for n in target],
            'type4_start': [2 * grid[0] - 0x8000, grid[1]],
            'direction0_probe_local': [2 * (grid[0] % 64), grid[1] % 64]}

def probe_cells(grid, direction):
    """Original type4 Coordinate offsets; fixed CP59 positive domain only."""
    map_step(grid, direction)
    offsets = [EVEN[direction//2]] if direction % 2 == 0 else [t[direction//2] for t in ODD]
    doubled_x, y = 2 * grid[0] - 0x8000, grid[1]
    cells = []
    for dx, dy in offsets:
        ax, ay = doubled_x + dx, y + dy
        gx = ((ax - 0x8000) >> 1) + 0x8000
        need(0 <= gx <= 65535 and 0 <= ay <= 65535, 'TILE_PROBE_GRID_BOUNDARY')
        sx, sy = (gx >> 6) + 0x7e00, (ay >> 6) + 0x7e00
        lx = (0x7f00 - sx) * 128 + ax
        ly = (0x7e00 - sy) * 64 + ay
        need(0 <= lx < 128 and 0 <= ly < 64, 'TILE_PROBE_LOCAL_BOUNDARY')
        cells.append(((sx,sy),(lx,ly)))
    return cells

def flag_blocked(direction, flags, mask=1):
    need(type(direction) is int and 0 <= direction < 8 and mask in (1,0x4000), 'TILE_COMBINATION_INPUT')
    need(len(flags) == (4 if direction % 2 else 1) and
         all(type(n) is int and 0 <= n <= 65535 for n in flags), 'TILE_FLAGS_REQUIRED')
    values = [bool(n & mask) for n in flags]
    if direction % 2 == 0:
        return values[0]
    a,b,c,d = values
    if direction in (3,7):
        return (a or c) and (b or d)
    return (a or b) and (c or d)

def vector3(reads, at, stride, exact_count, reason):
    begin, end, capacity = struct.unpack('<QQQ', reads.read(at, 24))
    need(0x10000 <= begin <= end <= capacity <= 0x7fffffffffff and
         (begin | end | capacity) % 8 == 0 and
         end - begin == exact_count * stride and
         (capacity - begin) % stride == 0 and capacity - begin <= 65536, reason)
    return begin

def lookup_resource(reads, context, key):
    head, count = struct.unpack('<QQ', reads.read(context + 8, 16))
    need(0x10000 <= head <= 0x7fffffffffff and head % 8 == 0 and 0 < count <= 4096,
         'TILE_SEGMENT_TREE_BOUND')
    header = reads.read(head, 26)
    need(header[25] == 1, 'TILE_SEGMENT_SENTINEL_REQUIRED')
    node = struct.unpack_from('<Q', header, 8)[0]
    seen, lo, hi = set(), -1, 0x100000000
    for _ in range(64):
        if node == head:
            raise ValueError('TILE_SEGMENT_NOT_PRESENT')
        need(node not in seen and len(seen) < count and node % 8 == 0 and
             0x10000 <= node <= 0x7fffffffffff, 'TILE_SEGMENT_CYCLE_OR_BOUND')
        seen.add(node)
        need(reads.read(node + 25, 1) == b'\0', 'TILE_SEGMENT_NODE_REQUIRED')
        value = struct.unpack('<I', reads.read(node + 32, 4))[0]
        need(lo < value < hi, 'TILE_SEGMENT_ORDER_CHANGED')
        if value == key:
            return reads.pair(reads.read(node + 40, 16))[0]
        if key < value:
            hi, node = value, reads.pointer(node)
        else:
            lo, node = value, reads.pointer(node + 16)
    raise ValueError('TILE_SEGMENT_LOOKUP_BOUND')

def cell(reads, resource, local):
    x, y = local
    need(0 <= x < 128 and 0 <= y < 64, 'TILE_CELL_RANGE_REQUIRED')
    head, count = struct.unpack('<QQ', reads.read(resource + 24, 16))
    need(0x10000 <= head <= 0x7fffffffffff and head % 8 == 0 and count <= 8192,
         'TILE_OVERRIDE_TREE_BOUND')
    header = reads.read(head, 26)
    left, node, right = struct.unpack_from('<QQQ', header)
    need(header[25] == 1, 'TILE_OVERRIDE_SENTINEL_REQUIRED')
    need(count != 0 or left == node == right == head, 'EMPTY_OVERRIDE_TREE_INCONSISTENT')
    need(count == 0 or node != head, 'NONEMPTY_OVERRIDE_TREE_INCONSISTENT')
    seen, lo, hi = set(), (-0x80000001,-0x80000001), (0x80000000,0x80000000)
    query = (x,y)
    for _ in range(64):
        if node == head:
            break
        need(node not in seen and len(seen) < count and 0x10000 <= node <= 0x7fffffffffff and
             node % 8 == 0, 'TILE_OVERRIDE_CYCLE_OR_BOUND')
        seen.add(node)
        need(reads.read(node + 25, 1) == b'\0', 'TILE_OVERRIDE_NODE_REQUIRED')
        key = struct.unpack('<ii', reads.read(node + 28, 8))
        need(lo < key < hi, 'TILE_OVERRIDE_SIGNED_ORDER_CHANGED')
        if key == query:
            return reads.read(node + 36, 8), 'OVERRIDE', count
        if query < key:
            hi, node = key, reads.pointer(node)
        else:
            lo, node = key, reads.pointer(node + 16)
    else:
        raise ValueError('TILE_OVERRIDE_LOOKUP_BOUND')
    rows = vector3(reads, resource, 24, 64, 'TILE_MATRIX_ROWS_NOT_READY')
    row = vector3(reads, rows + y * 24, 8, 128, 'TILE_MATRIX_ROW_NOT_READY')
    return reads.read(row + x * 8, 8), 'MATRIX', count

def empty(reason='TILE_NOT_INSPECTED'):
    return {'schema': 'lc-one-step-tile-read-v1', 'status': 'UNKNOWN', 'reason': reason,
            'direction': 0, 'grid_start': list(GRID), 'grid_target': [32571,32949],
            'tile_passability': 'UNKNOWN', 'full_navigation_passability': 'UNKNOWN',
            'flags_u16': None, 'flag1_blocked': None, 'flag4000_actor_query_mode': None,
            'tile_data_source': None, 'decode_completion': 'UNKNOWN', 'render_ready': 'UNKNOWN',
            'stable_double_read': False, 'snapshot_atomic': False, 'typed_bytes_requested': 0,
            'raw_pointers_saved': False, 'game_internal_function_calls': 0,
            'memory_write_input_packet_actions': 0, 'source_sha256': SOURCE_SHA}

def inspect_attached(native, sampler, expected_uid=1, direction=0):
    """One selected direction or all8 (None); CP59 start only, caller guards ownership."""
    row, previous_limit = empty(), getattr(sampler, 'read_limit', LIMIT)
    restore_read = None
    sampler.bytes, sampler.read_limit = 0, LIMIT
    try:
        need(direction is None or type(direction) is int and 0 <= direction < 8,
             'SOURCE_BOUND_DIRECTION_REQUIRED')
        need(type(expected_uid) is int and 0 < expected_uid <= 0xffffffffffffffff,
             'EXPECTED_UID_REQUIRED')
        need(sampler.b is native and sampler.c is native.contract, 'EXACT_RETAINED_TILE_READER_REQUIRED')
        world, source = load_world(), contract()
        restore_read = install_tile_read_budget(sampler)
        baseline = world.inspect_attached(native, sampler, expected_uid=expected_uid,
                                          expected_grid_words=GRID)
        need(baseline['status'] == 'OBSERVED' and baseline['expected_uid_match'] is True and
             baseline['expected_grid_words_match'] is True and baseline['pending'] == 'none' and
             baseline['source_segment_grid_relation_match'] is True and
             baseline['segment_key_words'] == SEGMENT and baseline['map_context_header_i32'] == 0 and
             baseline['coordinate_tile_resource_present'] is True, 'CP59_CURRENT_WORLD_REQUIRED')
        native.validate()
        diagnostic = world.empty_diagnostic()
        world.source_anchors(sampler, source['source_checks'], diagnostic)
        # Static direction constants are essential data, never dormant-exempt.
        for table in source['tables']:
            raw = sampler.read(sampler.g['base'] + table['rva'], table['length'], image=True)
            need(hashlib.sha256(raw).hexdigest() == table['sha256'], 'TILE_DIRECTION_CONSTANT_CHANGED')
        public, world_source = world.contracts()
        route = sampler.route()
        state = sampler.unique(route[-1], 'GameState')
        scene, scene_raw = sampler.scene(state)
        need(scene['current']['kind'] == 'Land' and scene['pending']['kind'] == 'none', 'STABLE_LAND_REQUIRED')
        reads = world.Reads(sampler)
        players, maps = [], []
        base = sampler.g['base']
        for pair, vft in route[-2]:
            if vft == base + public['Player']['ActorSubsystem']['rva']:
                players.append(reads.pair(pair)[0])
            if vft == base + public['Map']['table']['rva']:
                maps.append(reads.pair(pair)[0])
        need(len(players) == len(maps) == 1, 'UNIQUE_WORLD_OWNERS_REQUIRED')
        begin, count = world.vector(reads, players[0], public['Player']['vector_begin'],
                                    public['Player']['vector_end'], public['Player']['max_actor_elements'])
        actors = []
        for index in range(count):
            actor = reads.pair(reads.read(begin + index * 16, 16))[0]
            if reads.pointer(actor) == base + public['Player']['MyPlayer']['rva']:
                actors.append(actor)
        need(len(actors) == 1, 'UNIQUE_MYPLAYER_REQUIRED')
        uid = struct.unpack('<Q', reads.read(actors[0] + public['Player']['ActorID'], 8))[0]
        segments, grids, reason = world.position(sampler, reads, actors[0], public, world_source)
        need(uid == expected_uid and segments == SEGMENT and grids == GRID, 'CURRENT_PLAYER_CHANGED')
        context = reads.pointer(maps[0] + public['Map']['context_pointer'])
        need(reads.read(context, 4) == bytes(4), 'LOCAL_MAP0_REQUIRED')
        directions = list(range(8)) if direction is None else [direction]
        resource_cache, cell_cache, outcomes = {}, {}, []
        for value in directions:
            step = map_step(grids, value)
            probes, flags = [], []
            for segment, local in probe_cells(grids, value):
                key = (segment[0] << 16) | segment[1]
                if key not in resource_cache:
                    resource_cache[key] = lookup_resource(reads, context, key)
                cache_key = (segment,local)
                if cache_key not in cell_cache:
                    raw, data_source, override_count = cell(reads, resource_cache[key], local)
                    cell_cache[cache_key] = (struct.unpack_from('<H',raw,4)[0], data_source, override_count)
                flag, data_source, override_count = cell_cache[cache_key]
                flags.append(flag)
                probes.append({'segment': list(segment), 'local': list(local), 'flags_u16': flag,
                               'data_source': data_source, 'override_count': override_count})
            outcomes.append({'direction': value, 'grid_target': step['grid_target'],
                             'tile_passability': 'BLOCKED' if flag_blocked(value,flags) else 'PASSABLE',
                             'flag1_blocked': flag_blocked(value,flags),
                             'flag4000_actor_query_mode': flag_blocked(value,flags,0x4000),
                             'full_navigation_passability': 'UNKNOWN', 'probes': probes})
        reads.verify()
        need(sampler.read(state + 0x360,36) == scene_raw and sampler.route() == route,
             'TILE_WORLD_OWNER_CHANGED')
        native.validate()
        row.update(status='OBSERVED', reason=None, directions=outcomes, direction=direction,
                   unique_cells_read=len(cell_cache), unique_segments_read=len(resource_cache),
                   tile_passability=outcomes[0]['tile_passability'] if len(outcomes)==1 else 'PER_DIRECTION',
                   stable_double_read=True,
                   source_anchors_dormant=diagnostic['source_anchors_dormant'],
                   dormant_is_execution_evidence=False,
                   full_navigation_reason='ACTOR_OCCUPANCY_AND_ENVIRONMENT_GATE_NOT_READ')
        if len(outcomes)==1:
            selected=outcomes[0]
            row.update(grid_target=selected['grid_target'],flag1_blocked=selected['flag1_blocked'],
                       flag4000_actor_query_mode=selected['flag4000_actor_query_mode'])
            if len(selected['probes'])==1:
                probe=selected['probes'][0]
                row.update(flags_u16=probe['flags_u16'],tile_data_source=probe['data_source'],
                           override_count=probe['override_count'],probe_local=probe['local'])
    except Exception as error:
        reason = getattr(error, 'reason', str(error) if isinstance(error, ValueError) else type(error).__name__)
        if not isinstance(reason, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', reason):
            reason = 'TILE_READ_FAILED'
        row = empty(reason)
    finally:
        if row['status']=='UNKNOWN' and direction is None:
            row.update(direction=None,tile_passability='UNKNOWN',
                       directions=[{'direction': d,'grid_target': map_step(GRID,d)['grid_target'],
                                    'tile_passability':'UNKNOWN','full_navigation_passability':'UNKNOWN',
                                    'probes':[]} for d in range(8)])
        row['typed_bytes_requested'] = sampler.bytes
        sampler.read_limit = previous_limit
        if restore_read is not None:
            restore_read()
    return row

def inspect_all_attached(native, sampler, expected_uid=1):
    return inspect_attached(native, sampler, expected_uid=expected_uid, direction=None)
