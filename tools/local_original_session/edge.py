"""Read-only tile and empty/exact-own-self local edge subset for the realm.

True is this conservative local server policy, not full original Navigation
equivalence. Client action/prediction is not an authoritative server start.
"""
from contextlib import contextmanager
import importlib.util
import hashlib
import json
import struct
import sys
import types

from tools.local_original_session import observe

# Query-tool ceiling, not a game rule: the direct-play last source/typed proof
# required 32814 bytes. Preserve every read and allow one additional maximum
# 4096-byte read of headroom, rounded up to the next 4096-byte boundary.
LIMIT = 40960
PINS = {
    'tools/local_tile_passability_budget/inspect_tile.py':
        'e159a1a5f685f307ce5631841aa870e3358cce91393c4c4ff7cc3eb184e59392',
    'tools/local_full_navigation_reader/inspect_navigation.py':
        '5205eb85d2785bed6b78c3306a636966c90852155ed3006d5d9e96ec61be766a',
}
need = observe.need
LOOKUP_PINS = {
    'work/local_server_rea_20261016/run9_ownself_occupancy/source.json':
        '843802ae58331f15f61981c4d8e30bf12433e9d499c131b63a398b6d9e9c6e0c',
    'work/local_server_rea_20261016/run5_move_update/nav_source.json':
        'eed92e6eda3b30173210ad0e1590fd6ca5671679f333c21e7899d417534db85a',
}


def _lookup_contract():
    """Reuse retained run9 lookup/RTTI and run5 CharacterData source only."""
    documents = []
    for relative, expected in LOOKUP_PINS.items():
        path = observe.ordinary(observe.ROOT / relative)
        need(0 < path.stat().st_size <= 1048576, 'EDGE_LOOKUP_SOURCE_BOUND')
        raw = path.read_bytes()
        need(len(raw) <= 1048576 and hashlib.sha256(raw).hexdigest() == expected,
             'FIXED_EDGE_LOOKUP_SOURCE_REQUIRED')
        document = json.loads(raw)
        need(document['CONTROL_sha256'] ==
             '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af',
             'EDGE_LOOKUP_SOURCE_CONTROL_CHANGED')
        documents.append(document)
    ownself, navigation = documents
    player = ownself['MyPlayer']
    getter = player['uid_getter']
    lookup, = [row for row in ownself['functions'] if row['rva'] == '0x627b0']
    need(player['source_table']['rva'] == 0x11819f0
         and player['slots'][1] == getter['rva'] == '0x40c00'
         and getter['end'] == '0x40c05' and lookup['end'] == '0x62979',
         'EDGE_LOOKUP_SOURCE_LAYOUT_CHANGED')
    character, = navigation['types']['CharacterDataSubsystem']['tables']
    rva, targets = int(character['vptr_rva'], 16), [int(v, 16) for v in character['methods']]
    need(rva == 0x1185340 and len(targets) == 5, 'EDGE_CHARACTER_SOURCE_LAYOUT_CHANGED')
    normalized = struct.pack('<5Q', *targets)
    checks = [dict(rva=int(row['rva'], 16), length=int(row['end'], 16) - int(row['rva'], 16),
                   sha256=row['sha256']) for row in (lookup, getter)]
    return dict(player=player['source_table'], getter_rva=int(getter['rva'], 16),
                character=dict(rva=rva, prefix_bytes=len(normalized),
                               normalized_sha256=hashlib.sha256(normalized).hexdigest()),
                code_checks=checks)


def _load(relative, name):
    path = observe.ordinary(observe.ROOT / relative)
    need(observe.digest(path) == PINS[relative], 'FIXED_EDGE_HELPER_REQUIRED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves postponed annotations through its module registry.
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


class _Budget:
    """All initial reads stay physical; recheck each exact typed span once.

    Duplicate initial values must agree. This is not an atomic/lifetime proof.
    Observer counters/methods are restored by installed().
    """
    def __init__(self, native, sampler, *, diagnostic=None):
        self.native, self.sampler = native, sampler
        self.spent, self.records, self.retain = 0, [], True
        self._retained = {}
        self._diagnostic, self._capture_phases = diagnostic, {}
        self.changed_read1 = None

    def _changed(self, at, before, after, image, comparison):
        if self.changed_read1 is not None:
            return
        key = (at, len(before), image)
        self.changed_read1 = dict(address=hex(at), size=len(before), field_role='UNKNOWN',
            before_sha256=hashlib.sha256(before).hexdigest(),
            after_sha256=hashlib.sha256(after).hexdigest(),
            capture_phase=self._capture_phases.get(key, 'UNKNOWN'), comparison=comparison)
        if self._diagnostic is not None:
            self._diagnostic['changed_read1'] = dict(self.changed_read1)

    def read(self, at, size, image=False):
        need(type(at) is int and type(size) is int and 0 < size <= 4096 and
             0x10000 <= at <= 0x7fffffffffff - size, 'EDGE_TYPED_READ_BOUND')
        need(self.spent + size <= LIMIT, 'EDGE_REQUEST_BYTE_BOUND')
        self.spent += size
        raw = self.native.read(at, size, self.sampler.g['base'] if image else None)
        need(type(raw) is bytes and len(raw) == size, 'EDGE_PARTIAL_TYPED_READ')
        if self.retain:
            key = (at, size, image)
            expected = self._retained.get(key)
            if expected is None:
                self._retained[key] = raw
                self.records.append((at, raw, image))
                self._capture_phases[key] = ('UNKNOWN' if self._diagnostic is None
                                             else self._diagnostic.get('phase', 'UNKNOWN'))
            else:
                if raw != expected:
                    self._changed(at, expected, raw, image, 'INITIAL_DUPLICATE')
                need(raw == expected, 'EDGE_TYPED_READ_CHANGED')
        return raw

    @contextmanager
    def installed(self):
        sampler = self.sampler
        previous = {key: sampler.__dict__[key] for key in ('read', 'bytes', 'read_limit', 'total')
                    if key in sampler.__dict__}
        sampler.read = self.read
        try:
            yield
        finally:
            for key in ('read', 'bytes', 'read_limit', 'total'):
                if key in previous:
                    setattr(sampler, key, previous[key])
                else:
                    sampler.__dict__.pop(key, None)

    def verify(self):
        self.retain = False
        try:
            for at, raw, image in self.records:
                actual = self.read(at, len(raw), image)
                if actual != raw:
                    self._changed(at, raw, actual, image, 'VERIFY_REREAD')
                need(actual == raw, 'EDGE_TYPED_READ_CHANGED')
        finally:
            self.retain = True


class _NeighborBudget(_Budget):
    """Same ceiling, with the exact refused-read shortfall for diagnostics."""
    def __init__(self, native, sampler):
        super().__init__(native, sampler)
        self.refused_read_bytes = self.shortfall_at_refused_read = None

    def read(self, at, size, image=False):
        if type(size) is int and 0 < size <= 4096 and self.spent + size > LIMIT:
            self.refused_read_bytes = size
            self.shortfall_at_refused_read = self.spent + size - LIMIT
        return super().read(at, size, image=image)


def _request(tile, uid, map_id, start, direction, destination):
    need(type(uid) is int and 0 < uid <= 0xffffffffffffffff and
         type(map_id) is int and 0 <= map_id <= 0x7fffffff, 'EDGE_UID_MAP_REQUIRED')
    need(type(start) is int and type(destination) is int and
         0 <= start <= 0xffffffff and 0 <= destination <= 0xffffffff,
         'EDGE_PACKED_U32_REQUIRED')
    grid = (start & 0xffff, start >> 16)
    target = tuple(tile.map_step(grid, direction)['grid_target'])
    need(destination == (target[1] << 16) | target[0], 'EDGE_DESTINATION_MISMATCH')
    return grid, target


def _cached_reads(reads):
    """Private typed-value cache; Budget retains the first value for recheck."""
    original, cache = reads.read, {}
    def read(at, size):
        key = (at, size)
        if key not in cache:
            cache[key] = original(at, size)
        return cache[key]
    reads.read = read
    return reads


def _world(native, sampler, public, world, position_source, uid, map_id, grid, *, cache_reads=False,
           require_current_start=True, observation=None):
    route = sampler.route()
    need(route[1] is True, 'EDGE_READY_ROOT_REQUIRED')
    state = sampler.unique(route[-1], 'GameState')
    scene, raw = sampler.scene(state)
    need(scene['current']['kind'] == 'Land' and scene['pending']['kind'] == 'none',
         'EDGE_STABLE_LAND_REQUIRED')
    reads = world.Reads(sampler)
    if cache_reads:
        _cached_reads(reads)
    registered = []
    for table in (public['Player']['ActorSubsystem'], public['Map']['table']):
        objects = [reads.pair(pair)[0] for pair, vft in route[-2]
                   if vft == sampler.g['base'] + table['rva']]
        need(len(objects) == 1, 'EDGE_UNIQUE_WORLD_OWNER_REQUIRED')
        obj = objects[0]
        need(reads.pointer(obj) == sampler.g['base'] + table['rva'], 'EDGE_WORLD_TYPE_CHANGED')
        world.table(sampler, table)
        registered.append(obj)
    actor_sub, map_sub = registered
    begin, count = world.vector(reads, actor_sub, public['Player']['vector_begin'],
                               public['Player']['vector_end'], public['Player']['max_actor_elements'])
    players = []
    for index in range(count):
        player = reads.pair(reads.read(begin + index * 16, 16))[0]
        if reads.pointer(player) == sampler.g['base'] + public['Player']['MyPlayer']['rva']:
            players.append(player)
    need(len(players) == 1, 'EDGE_UNIQUE_MYPLAYER_REQUIRED')
    world.table(sampler, public['Player']['MyPlayer'])
    actual = struct.unpack('<Q', reads.read(players[0] + public['Player']['ActorID'], 8))[0]
    context = reads.pointer(map_sub + public['Map']['context_pointer'])
    maps = [struct.unpack('<i', reads.read(at, 4))[0] for at in
            (map_sub + public['Map']['field718'], map_sub + 0x71c, context)]
    need(actual == uid and maps == [map_id] * 3, 'EDGE_CURRENT_UID_MAP_MISMATCH')
    segments, current_grid, reason = world.position(sampler, reads, players[0], public, position_source)
    need(reason is None and type(current_grid) is list and len(current_grid) == 2
         and all(type(n) is int and 0 <= n <= 0xffff for n in current_grid)
         and segments == [(n >> 6) + 0x7e00 for n in current_grid], 'EDGE_CLIENT_POSITION_INVALID')
    if observation is not None:
        observation.update(observed_client_grid=list(current_grid), authoritative_start_grid=list(grid),
                           client_grid_used_as_authority=False)
    if require_current_start:
        need(current_grid == list(grid), 'EDGE_CURRENT_START_GRID_MISMATCH')
    return reads, actor_sub, context, route, state, raw, players[0]


def _empty_or_exact_self_store(nav, reads, at, target, player, details):
    """Local-server subset, not a reconstruction of the full original filter.

    Preserve immutable empty_store's full list/bucket/link/vector validation.
    Its nonempty-target exception occurs before the final checks, so it alone
    cannot authorize a candidate. A separate signed-i32 audit query completes
    those checks, then this tail verifies the actual target bucket and vector.
    The audit key is not a spawn/target: actual targets are unsigned-16 grids.
    """
    audit_key = (-0x80000000, -0x80000000)
    need(type(target) is tuple and len(target) == 2 and all(type(n) is int and 0 <= n <= 0xffff for n in target)
         and target != audit_key, 'EDGE_SPATIAL_ACTUAL_TARGET_REQUIRED')
    original_read, nodes = reads.read, {}
    def collect(at, size):
        raw = original_read(at, size)
        if size == 48:
            nodes[at] = raw
        return raw
    reads.read = collect
    try:
        try:
            proof = nav.empty_store(reads, at, target=target)
            need(proof.get('complete') is True, 'EDGE_SPATIAL_COMPLETE_PROOF_REQUIRED')
            details['raw_candidates_by_store'].append(0)
            return 0
        except Exception as error:
            if observe.reason(error) != 'SPATIAL_TARGET_NONEMPTY_UNCLASSIFIED':
                raise
        # This is an ordinary source-validator call, with no altered buffers,
        # need predicates or target equality. A nonempty audit key stays UNKNOWN.
        try:
            proof = nav.empty_store(reads, at, target=audit_key)
        except Exception as error:
            if observe.reason(error) == 'SPATIAL_TARGET_NONEMPTY_UNCLASSIFIED':
                raise ValueError('EDGE_SPATIAL_AUDIT_QUERY_NONEMPTY') from None
            raise
        need(proof.get('complete') is True and proof['global_nodes_read'] == len(nodes),
             'EDGE_SPATIAL_COMPLETE_PROOF_REQUIRED')
        header = reads.read(at, 64)
        head, count, buckets_begin, _, _, mask, _ = struct.unpack_from('<7Q', header, 8)
        current = struct.unpack_from('<Q', reads.read(head, 16))[0]
        index = nav.destination_hash(target) & mask
        bucket_nodes, matches = [], []
        # Follow only the already source-validated node records. No candidate
        # pointer is dereferenced and this is not another structural validator.
        for _ in range(count):
            need(current in nodes, 'EDGE_SPATIAL_VALIDATED_NODE_REQUIRED')
            raw = nodes[current]
            words = struct.unpack_from('<ii', raw, 16)
            if nav.destination_hash(words) & mask == index:
                bucket_nodes.append(current)
            if words == target:
                matches.append(raw)
            current = struct.unpack_from('<Q', raw)[0]
        need(current == head and len(matches) == 1, 'EDGE_SPATIAL_ACTUAL_TARGET_PROOF_REQUIRED')
        actual_range = struct.unpack('<QQ', reads.read(buckets_begin + index * 16, 16))
        expected_range = (bucket_nodes[0], bucket_nodes[-1]) if bucket_nodes else (head, head)
        need(actual_range == expected_range, 'SPATIAL_BUCKET_COMPLETE_RANGE_MISMATCH')
        begin, end, _ = struct.unpack_from('<QQQ', matches[0], 24)
        candidates = (end - begin) // 8  # Original validator proved all bounds.
        details['raw_candidates_by_store'].append(candidates)
        for address in range(begin, end, 4096):
            raw = reads.read(address, min(4096, end - address))
            for value, in struct.iter_unpack('<Q', raw):
                need(value == player, 'SPATIAL_TARGET_FOREIGN_OR_UNKNOWN_CANDIDATE')
        return candidates
    finally:
        reads.read = original_read


def _exact_first_self_lookup(sampler, reads, actors, route, player, uid, nav, world, public, contract):
    """627B0's first UID match in +8A8 resolves to exact current MyPlayer.

    A prefix is supported only when its live virtual+8 is the pinned pure
    40C00 getter and its UID differs. The first earlier UID match or any
    unsupported getter stays UNKNOWN. Secondary actor vectors are not used.
    No virtual call or reference-count increment is performed by this reader.
    All reads share the edge budget and its final typed/root/identity recheck.
    """
    begin, count = world.vector(reads, actors, public['Player']['vector_begin'],
                                public['Player']['vector_end'], public['Player']['max_actor_elements'])
    base, size = sampler.g['base'], sampler.g['size']
    prefix_count = 0
    for index in range(count):
        actor = reads.pair(reads.read(begin + index * 16, 16))[0]
        if actor == player:
            break
        vptr = reads.pointer(actor)
        need(base <= vptr <= base + size - 16, 'EDGE_UID_PREFIX_VTABLE_IMAGE_BOUNDS')
        # Reads.read is a heap-only wrapper. Read this slot through Sampler so
        # the retained Native validates MEM_IMAGE/allocation_base, including
        # the final Budget recheck; a canonical address alone is insufficient.
        getter = struct.unpack('<Q', sampler.read(vptr + 8, 8, image=True))[0]
        need(getter == base + contract['getter_rva'], 'EDGE_UID_PREFIX_GETTER_UNSUPPORTED')
        prefix_uid = struct.unpack('<Q', reads.read(actor + public['Player']['ActorID'], 8))[0]
        need(prefix_uid != uid, 'EDGE_UID_LOOKUP_EARLIER_MATCH')
        prefix_count += 1
    else:
        raise ValueError('EDGE_UID_LOOKUP_SELF_NOT_REGISTERED')
    nav._source_type(reads, sampler, player, contract['player'], world)
    need(reads.pointer(sampler.g['base'] + contract['player']['rva'] + 8)
         == sampler.g['base'] + contract['getter_rva'], 'EDGE_UID_GETTER_SLOT_CHANGED')
    character_table = contract['character']
    objects = [reads.pair(pair)[0] for pair, vft in route[-2]
               if vft == sampler.g['base'] + character_table['rva']]
    need(len(objects) == 1, 'EDGE_UNIQUE_CHARACTER_DATA_REQUIRED')
    character = objects[0]
    need(reads.pointer(character) == sampler.g['base'] + character_table['rva'],
         'EDGE_CHARACTER_DATA_TYPE_CHANGED')
    world.table(sampler, character_table)
    actual = struct.unpack('<Q', reads.read(player + public['Player']['ActorID'], 8))[0]
    own = struct.unpack('<Q', reads.read(character + 0x6d8, 8))[0]
    need(actual == own == uid, 'EDGE_UID_LOOKUP_OWN_UID_MISMATCH')
    return prefix_count


def _check(native, sampler, tile, nav, world, public, position_source, grid, target, direction, uid, map_id,
           details, self_lookup):
    details['phase'] = 'WORLD'
    reads, actors, context, route, state, raw, player = _world(native, sampler, public, world, position_source,
        uid, map_id, grid, cache_reads=True, require_current_start=False, observation=details)
    details['phase'] = 'TILES'
    flags, resources = [], {}
    for segment, local in tile.probe_cells(grid, direction):
        if segment not in resources:
            resources[segment] = tile.lookup_resource(reads, context, (segment[0] << 16) | segment[1])
        cell, _, _ = tile.cell(reads, resources[segment], local)
        flags.append(struct.unpack_from('<H', cell, 4)[0])
    blocked = tile.flag_blocked(direction, flags, 1)
    # Both complete stores must be empty or contain only the exact live player.
    # This is an explicit local-server subset, not the full original filter.
    if not blocked:
        for index, offset in enumerate((0, 0x40)):
            details['phase'] = 'SPATIAL_STORE_' + str(index)
            details['own_self_candidates'] += _empty_or_exact_self_store(
                nav, reads, actors + 0x798 + offset, target, player, details)
        if details['own_self_candidates']:
            self_lookup(reads, actors, route, player)
    return not blocked, route, state, raw


def _retained_method(obj, name, expected, label):
    """Exact current class bound method plus pinned code and helper globals."""
    actual = getattr(obj, name, None)
    code = 'EXACT_RETAINED_EDGE_' + label.upper() + '_'
    need(isinstance(actual, types.MethodType) and actual.__self__ is obj
         and vars(type(obj)).get(name) is actual.__func__
         and actual.__func__.__closure__ is expected.__closure__ is None
         and actual.__func__.__defaults__ == expected.__defaults__
         and actual.__func__.__kwdefaults__ == expected.__kwdefaults__
         and actual.__func__.__code__ == expected.__code__
         and actual.__func__.__code__.co_filename == expected.__code__.co_filename
         and actual.__func__.__code__.co_firstlineno == expected.__code__.co_firstlineno
         and actual.__func__.__code__.co_linetable == expected.__code__.co_linetable
         and actual.__func__.__code__.co_exceptiontable == expected.__code__.co_exceptiontable,
         code + 'METHOD_REQUIRED')
    for helper in ('need', 'require'):
        if helper in expected.__code__.co_names:
            actual_helper = actual.__func__.__globals__.get(helper)
            expected_helper = expected.__globals__.get(helper)
            need(isinstance(actual_helper, types.FunctionType) and isinstance(expected_helper, types.FunctionType)
                 and actual_helper.__closure__ is expected_helper.__closure__ is None
                 and actual_helper.__defaults__ == expected_helper.__defaults__
                 and actual_helper.__kwdefaults__ == expected_helper.__kwdefaults__
                 and actual_helper.__code__ == expected_helper.__code__
                 and actual_helper.__code__.co_filename == expected_helper.__code__.co_filename
                 and actual_helper.__code__.co_firstlineno == expected_helper.__code__.co_firstlineno
                 and actual_helper.__code__.co_linetable == expected_helper.__code__.co_linetable
                 and actual_helper.__code__.co_exceptiontable == expected_helper.__code__.co_exceptiontable,
                 code + 'GLOBAL_REQUIRED')


class EdgeAdapter:
    """Synchronous callback after MovementService's selected owner/start checks.

    No await occurs here; broker rechecks the selected owner before commit.
    Only the retained reader's explicit duplicate validator replaces CP73's
    old attach validator. Original read/identity/token and Sampler pins remain.
    """
    def __init__(self, reader):
        need(type(reader) is observe.RetainedSceneReader, 'PREPARED_RETAINED_READER_REQUIRED')
        self.reader = reader
        self.tile = _load('tools/local_tile_passability_budget/inspect_tile.py', '_edge_tile')
        self.nav = _load('tools/local_full_navigation_reader/inspect_navigation.py', '_edge_nav')
        self.source, self.public, self.world, self.sm, self.nm = self.nav._bindings()
        world_public, self.position_source = self.world.contracts()
        need(world_public == self.public, 'EXACT_EDGE_WORLD_POSITION_CONTRACT_REQUIRED')
        tile_source = self.tile.contract()
        checks = (self.source['live_instruction_anchors'] + tile_source['source_checks']
                  + self.public['Position']['source_checks'])
        self.checks = list({(c['rva'], c['length'], c['sha256']): c for c in checks}.values())
        self.tables = self.source['direction_tables'] + tile_source['tables']
        self.lookup_contract = _lookup_contract()
        self.last_result = dict(status='UNKNOWN', reason='NOT_SAMPLED', typed_bytes_requested=0)

    def _binding(self):
        reader = self.reader
        native, sampler = reader.backend, reader.sampler
        need(sampler is not None and sampler.b is native and sampler.c is native.contract
             and sampler.c is reader.contract, 'EXACT_RETAINED_EDGE_SAMPLER_REQUIRED')
        for label, validator in (('READER_VALIDATE', reader.validate), ('NATIVE_VALIDATE', native.validate)):
            need(isinstance(validator, types.MethodType) and validator.__self__ is reader
                 and validator.__func__ is observe.RetainedSceneReader.validate,
                 'EXACT_RETAINED_EDGE_' + label + '_METHOD_REQUIRED')
        for method in ('read', 'identity', 'token'):
            _retained_method(native, method, getattr(self.nm.Native, method), 'NATIVE_' + method)
        need(type(sampler) is reader.sampler_module.Sampler, 'EXACT_RETAINED_EDGE_SAMPLER_CLASS_REQUIRED')
        for method in ('read', 'pointer', 'boolean', 'table', 'strong_pair', 'route', 'scene', 'unique'):
            _retained_method(sampler, method, getattr(self.sm.Sampler, method), 'SAMPLER_' + method)
        need(sampler.c['bounds']['typed_byte_limit'] == 8192, 'FIXED_EDGE_SAMPLER_CONTRACT_REQUIRED')
        reader.validate()
        return native, sampler

    def _code(self, sampler, budget, checks=None):
        budget.retain = False
        try:
            if checks is None:
                self.world.source_anchors(sampler, self.checks, self.world.empty_diagnostic())
            else:
                # Lookup/getter must be readable current code. The historical
                # generic source helper also accepts dormant pages and bounds
                # checks to one instruction; neither policy applies here.
                for check in checks:
                    rva, length = check['rva'], check['length']
                    need(0 <= rva < sampler.g['size'] and 0 < length <= 4096
                         and rva + length <= sampler.g['size'], 'EDGE_LOOKUP_CODE_BOUNDS')
                    raw = sampler.read(sampler.g['base'] + rva, length, image=True)
                    need(hashlib.sha256(raw).hexdigest() == check['sha256'],
                         'EDGE_LOOKUP_CODE_CHANGED')
        finally:
            budget.retain = True

    def tile_neighbors(self, uid, map_id, packed_start):
        """One retained read of eight mask1 queries, never an edge approval.

        Shares tile resources/cells within this call. All used bytes are checked
        again, along with the same source/direction/owner proofs as __call__.
        No occupancy is read; last_result and the server edge path are untouched.
        """
        rows = [dict(direction=d, status='UNKNOWN', reason='NOT_SAMPLED', grid_target=None,
                     flags_u16=None, blocked=None) for d in range(8)]
        result = dict(status='UNKNOWN', reason='NOT_SAMPLED',
            uid=uid if type(uid) is int and 0 < uid <= 0xffffffffffffffff else None,
            map_id=map_id if type(map_id) is int and 0 <= map_id <= 0x7fffffff else None, start_grid=None,
            directions=rows, stable_double_read=False, snapshot_atomic=False,
            typed_bytes_requested=0, source_code_bytes_requested=0,
            source_code_bytes_planned=2 * sum(check['length'] for check in self.checks),
            unique_cells_read=0, unique_segments_read=0,
            client_direction_selection='UNKNOWN', occupancy='NOT_READ', full_passability='UNKNOWN',
            byte_limit=LIMIT, refused_read_bytes=None, shortfall_at_refused_read=None,
            required_total_bytes=None, total_shortfall_bytes=None)
        budget = None
        resources, cells = {}, {}
        phase = 'REQUEST'
        code_bytes = 0
        try:
            need(type(uid) is int and 0 < uid <= 0xffffffffffffffff
                 and type(map_id) is int and 0 <= map_id <= 0x7fffffff, 'EDGE_UID_MAP_REQUIRED')
            need(type(packed_start) is int and 0 <= packed_start <= 0xffffffff, 'EDGE_PACKED_U32_REQUIRED')
            grid = (packed_start & 0xffff, packed_start >> 16)
            result['start_grid'] = list(grid)
            native, sampler = self._binding()
            budget = _NeighborBudget(native, sampler)
            with budget.installed():
                phase = 'SOURCE_BEFORE'
                before = budget.spent
                try:
                    self._code(sampler, budget)
                finally:
                    code_bytes += budget.spent - before
                phase = 'DIRECTION_TABLES'
                for table in self.tables:
                    raw = sampler.read(sampler.g['base'] + table['rva'], table['length'], image=True)
                    need(hashlib.sha256(raw).hexdigest() == table['sha256'], 'EDGE_DIRECTION_CONSTANT_CHANGED')
                phase = 'WORLD'
                reads, _, context, route, state, scene_raw, _ = _world(native, sampler, self.public, self.world,
                    self.position_source, uid, map_id, grid, require_current_start=True)
                # Cache only typed tile reads through this private Reads object.
                # Root/scene rechecks and Budget.verify always make fresh reads.
                original_read = reads.read
                typed_cache = {}
                def cached_read(at, size):
                    key = (at, size)
                    if key not in typed_cache:
                        typed_cache[key] = original_read(at, size)
                    return typed_cache[key]
                reads.read = cached_read
                phase = 'TILES'
                try:
                    for direction in range(8):
                        row = rows[direction]
                        try:
                            row['grid_target'] = self.tile.map_step(grid, direction)['grid_target']
                            flags = []
                            for segment, local in self.tile.probe_cells(grid, direction):
                                if segment not in resources:
                                    resources[segment] = self.tile.lookup_resource(reads, context,
                                        (segment[0] << 16) | segment[1])
                                key = (segment, local)
                                if key not in cells:
                                    raw, _, _ = self.tile.cell(reads, resources[segment], local)
                                    cells[key] = struct.unpack_from('<H', raw, 4)[0]
                                flags.append(cells[key])
                            row.update(status='OBSERVED', reason=None, flags_u16=flags,
                                       blocked=self.tile.flag_blocked(direction, flags, 1))
                        except Exception as error:
                            if observe.reason(error) == 'EDGE_REQUEST_BYTE_BOUND':
                                raise
                            row.update(reason=observe.reason(error))
                finally:
                    reads.read = original_read
                phase = 'TYPED_RECHECK'
                budget.verify()
                phase = 'WORLD_RECHECK'
                # This is itself a fresh comparison with the initial root/scene;
                # retaining it for another identical verification adds no proof.
                budget.retain = False
                try:
                    need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                         'EDGE_WORLD_OWNER_CHANGED')
                finally:
                    budget.retain = True
                phase = 'SOURCE_AFTER'
                before = budget.spent
                try:
                    self._code(sampler, budget)
                finally:
                    code_bytes += budget.spent - before
                phase = 'IDENTITY_AFTER'
                self.reader.validate()
            result.update(status='OBSERVED' if all(r['status'] == 'OBSERVED' for r in rows) else 'OBSERVED_PARTIAL',
                          reason=None, stable_double_read=True)
        except Exception as error:
            failure = observe.reason(error)
            result.update(status='UNKNOWN', reason=failure, stable_double_read=False)
            for row in rows:
                row.update(status='UNKNOWN', reason=failure, flags_u16=None, blocked=None)
            if budget is not None and failure == 'EDGE_REQUEST_BYTE_BOUND' and phase == 'SOURCE_AFTER':
                # All data/rechecks completed: the sole remaining requests are
                # the known source footer, so the complete shortfall is exact.
                required = budget.spent + result['source_code_bytes_planned'] - code_bytes
                result.update(required_total_bytes=required, total_shortfall_bytes=max(0, required - LIMIT))
        finally:
            result.update(typed_bytes_requested=0 if budget is None else budget.spent,
                          source_code_bytes_requested=code_bytes,
                          unique_cells_read=len(cells), unique_segments_read=len(resources))
            if budget is not None:
                result.update(refused_read_bytes=budget.refused_read_bytes,
                              shortfall_at_refused_read=budget.shortfall_at_refused_read)
        return result

    def __call__(self, uid, map_id, start, direction, destination):
        budget = None
        details = dict(phase='REQUEST', own_self_candidates=0, raw_candidates_by_store=[],
                       local_server_subset='EMPTY_OR_EXACT_OWN_SELF_PREDICTION',
                       official_navigation_equivalence='UNKNOWN', observed_client_grid=None,
                       authoritative_start_grid=None, client_grid_used_as_authority=False,
                       self_uid_lookup='NOT_REQUIRED', lookup_code_bytes_requested=0,
                       uid_lookup_prefix_count=None)
        source_bytes = 0
        source_planned = 2 * sum(check['length'] for check in self.checks)
        lookup_used = False
        try:
            grid, target = _request(self.tile, uid, map_id, start, direction, destination)
            # MovementService already bound this start to selected server
            # authority. Client prediction/current are read-only observations;
            # neither chooses the environment query, destination or commit.
            details['authoritative_start_grid'] = list(grid)
            native, sampler = self._binding()
            budget = _NeighborBudget(native, sampler)
            with budget.installed():
                details['phase'] = 'SOURCE_BEFORE'
                before = budget.spent
                try:
                    self._code(sampler, budget)
                finally:
                    source_bytes += budget.spent - before
                details['phase'] = 'DIRECTION_TABLES'
                for table in self.tables:
                    raw = sampler.read(sampler.g['base'] + table['rva'], table['length'], image=True)
                    need(hashlib.sha256(raw).hexdigest() == table['sha256'],
                         'EDGE_DIRECTION_CONSTANT_CHANGED')
                def self_lookup(reads, actors, route, player):
                    nonlocal source_bytes, source_planned, lookup_used
                    lookup_used = True
                    details.update(phase='UID_LOOKUP_SOURCE_BEFORE', self_uid_lookup='UNKNOWN')
                    source_planned += 2 * sum(c['length'] for c in self.lookup_contract['code_checks'])
                    before = budget.spent
                    try:
                        self._code(sampler, budget, self.lookup_contract['code_checks'])
                    finally:
                        used = budget.spent - before
                        source_bytes += used
                        details['lookup_code_bytes_requested'] += used
                    details['phase'] = 'UID_LOOKUP'
                    prefix_count = _exact_first_self_lookup(sampler, reads, actors, route, player, uid,
                        self.nav, self.world, self.public, self.lookup_contract)
                    details.update(uid_lookup_prefix_count=prefix_count,
                        self_uid_lookup=('EXACT_SELF_AFTER_TYPED_UID_PREFIX' if prefix_count
                                         else 'EXACT_FIRST_REGISTERED_SELF'))
                accepted, route, state, scene_raw = _check(native, sampler, self.tile, self.nav, self.world,
                    self.public, self.position_source, grid, target, direction, uid, map_id, details, self_lookup)
                details['phase'] = 'TYPED_RECHECK'
                budget.verify()
                details['phase'] = 'WORLD_RECHECK'
                budget.retain = False
                try:
                    need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                         'EDGE_WORLD_OWNER_CHANGED')
                finally:
                    budget.retain = True
                details['phase'] = 'SOURCE_AFTER'
                before = budget.spent
                try:
                    self._code(sampler, budget)
                finally:
                    source_bytes += budget.spent - before
                if lookup_used:
                    before = budget.spent
                    try:
                        self._code(sampler, budget, self.lookup_contract['code_checks'])
                    finally:
                        used = budget.spent - before
                        source_bytes += used
                        details['lookup_code_bytes_requested'] += used
                details['phase'] = 'IDENTITY_AFTER'
                self.reader.validate()
            details['phase'] = 'COMPLETE'
            status = ('CLEAR_OWN_SELF_SUBSET' if details['own_self_candidates'] else 'CLEAR_EMPTY_SUBSET') if accepted else 'BLOCKED_MASK1'
            self.last_result = dict(status=status, reason=None, typed_bytes_requested=budget.spent, **details)
            return accepted
        except Exception as error:
            if lookup_used:
                details.update(self_uid_lookup='UNKNOWN', uid_lookup_prefix_count=None)
            self.last_result = dict(status='UNKNOWN', reason=observe.reason(error),
                                    typed_bytes_requested=0 if budget is None else budget.spent, **details)
            if budget is not None and observe.reason(error) == 'EDGE_REQUEST_BYTE_BOUND' and details['phase'] == 'SOURCE_AFTER':
                required = budget.spent + source_planned - source_bytes
                self.last_result.update(required_total_bytes=required, total_shortfall_bytes=max(0, required - LIMIT))
            return None
        finally:
            self.last_result.update(source_code_bytes_requested=source_bytes, source_code_bytes_planned=source_planned,
                refused_read_bytes=None if budget is None else budget.refused_read_bytes,
                shortfall_at_refused_read=None if budget is None else budget.shortfall_at_refused_read)
