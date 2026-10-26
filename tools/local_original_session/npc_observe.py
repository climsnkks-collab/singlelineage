"""Source-bound current Monster coordinates; no sender, clock, or game call.

Call sample with the caller's monotonic ns, at most twice/second and instead
of another full retained observation for that tick. This independent 16-KiB
observation never borrows the edge query's 32-KiB allowance. Server coordinates
remain authority; a stable client snapshot is neither rendering nor atomicity.
"""
import hashlib
import json
import struct
from contextlib import contextmanager

from tools.local_original_session import attack, edge, observe

need = observe.need
TYPE_PATH = 'work/online_actor_type_coverage/source-contract.json'
SOURCE_PINS = {
    TYPE_PATH: '2525a674d5d3707f974701c2b7c9d93f5edd6e3232838817920588b9e48f81f9',
    'work/local_server_rea_20261016/run22_npc_spawn/source-evidence.json':
        'dde6967e27ce05e96aea719c40e4ab935415eb242f5a0528d9a649d606473c5f',
}
MIN_INTERVAL_NS = 500_000_000
BYTE_LIMIT = observe.RETAINED_SAMPLE_LIMIT


def _source(actor_name='Monster'):
    documents = {}
    for path, expected in SOURCE_PINS.items():
        file = observe.ordinary(observe.ROOT / path)
        need(0 < file.stat().st_size <= 1024 * 1024, 'NPC_OBSERVE_SOURCE_BOUND')
        raw = file.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == expected, 'NPC_OBSERVE_SOURCE_CHANGED')
        documents[path] = json.loads(raw)
    coverage = documents[TYPE_PATH]
    spawn = documents['work/local_server_rea_20261016/run22_npc_spawn/source-evidence.json']
    need(spawn['input_pins'][TYPE_PATH]['sha256'] == SOURCE_PINS[TYPE_PATH]
         and coverage['program_sha256'] == spawn['CONTROL_sha256'], 'NPC_OBSERVE_SOURCE_CONTROL_CHANGED')
    need(type(actor_name) is str and actor_name in ('Monster', 'MyPlayer'),
         'NPC_OBSERVE_SUPPORTED_REGISTRY_TYPE_REQUIRED')
    rows = [r for r in coverage['actor_types'] if r['name'] == actor_name]
    need(len(rows) == 1, 'NPC_OBSERVE_UNIQUE_MONSTER_SOURCE_REQUIRED')
    row, = rows
    common, table, hierarchy = coverage['exact_common_path'], row['table'], row['hierarchy']
    need(row['qualification'] == 'exact_primary_Actor_path' and row['Actor_base_offset'] == 0
         and row['ID_getter_virtual_slot'] == 8 and table['prefix_bytes'] == 40
         and common['Actor_self_pointer_offset'] == 8 and common['Actor_ID_u64_offset'] == 24
         and common['ID_getter_RVA'] == table['methods_RVA'][1]
         and hierarchy['COL_offset'] == 0
         and [r['PMD'] for r in hierarchy['bases'] if r['public_RTTI'] == '.?AVActor@lineage@@']
             == [[0, -1, 0]], 'NPC_OBSERVE_PRIMARY_ACTOR_SOURCE_REQUIRED')
    # Adapt the already proved coverage graph to the existing RTTI reader's
    # schema. Sizes are the coverage producer's fixed 24/16/4*n/28 records.
    anchors = [dict(rva=hierarchy['hierarchy_RVA'], length=16, sha256=hierarchy['hierarchy_sha256']),
               dict(rva=hierarchy['base_array_RVA'], length=4 * hierarchy['base_count'],
                    sha256=hierarchy['base_array_sha256'])]
    for base in hierarchy['bases']:
        anchors.append(dict(rva=base['descriptor_RVA'], length=28, sha256=base['descriptor_sha256']))
        literal = base['public_RTTI'].encode('ascii') + b'\0'
        anchors.append(dict(rva=base['type_descriptor_RVA'] + 16, length=len(literal),
                            sha256=hashlib.sha256(literal).hexdigest()))
    monster = dict(rva=table['rva'], prefix_bytes=40,
        normalized_sha256=table['normalized_RVA_u64_sha256'], COL_rva=hierarchy['COL_RVA'],
        COL_sha256=hierarchy['COL_sha256'], descriptor_rva=hierarchy['type_descriptor_RVA'],
        literal=row['public_RTTI'], RTTI_graph_anchors=anchors)
    return monster, common, coverage['inherited_source_checks']


def _registry_lookup_source():
    """Existing pinned 627B0 text, not a new decoder or runtime call."""
    contract = edge._lookup_contract()
    relative, expected = next(iter(edge.LOOKUP_PINS.items()))
    path = observe.ordinary(observe.ROOT / relative)
    raw = path.read_bytes()
    need(0 < len(raw) <= 1048576 and hashlib.sha256(raw).hexdigest() == expected,
         'NPC_REGISTRY_LOOKUP_SOURCE_CHANGED')
    document = json.loads(raw)
    lookup, = [r for r in document['functions'] if r['rva'] == '0x627b0']
    getter = document['MyPlayer']['uid_getter']
    need(contract['getter_rva'] == 0x40c00 and getter['rva'] == '0x40c00'
         and getter['end'] == '0x40c05'
         and getter['instructions'] == ['mov rax, qword ptr [rcx + 0x18]', 'ret'],
         'NPC_REGISTRY_PURE_UID_GETTER_SOURCE_CHANGED')
    instructions = {r['rva']: r['instruction'] for r in lookup['instructions']}
    required = {
        '0x627d5': 'mov rbx, qword ptr [rcx + 0x8a8]',
        '0x627dc': 'mov rdi, qword ptr [rcx + 0x8b0]',
        '0x6280b': 'mov rbx, qword ptr [r15 + 0x8c0]',
        '0x62812': 'mov rdi, qword ptr [r15 + 0x8c8]',
        '0x6284b': 'mov rbx, qword ptr [r15 + 0x8d8]',
        '0x62852': 'mov rdi, qword ptr [r15 + 0x8e0]',
        **{at: 'call qword ptr [rax + 8]' for at in ('0x627f6', '0x62826', '0x62866')},
        **{at: 'mov rcx, qword ptr [rbx]' for at in ('0x627f0', '0x62820', '0x62860')},
        **{at: 'mov rax, qword ptr [rcx]' for at in ('0x627f3', '0x62823', '0x62863')},
        **{at: 'add rbx, 0x10' for at in ('0x62802', '0x62832', '0x62872')},
    }
    need(all(instructions.get(at) == value for at, value in required.items()),
         'NPC_REGISTRY_THREE_VECTOR_LAYOUT_CHANGED')


class _ObservationBudget(edge._Budget):
    """Same physical reads; only positive shared-owner count drift is named.

    An unstable count is never a strict snapshot. Continue the original query
    only for the original strong_pair predicate (>0), then require every other
    typed span and all original post-checks before exposing that incomplete
    classification. No pointer/UID/coordinate/table drift is admitted here.
    """
    def __init__(self, native, sampler):
        super().__init__(native, sampler)
        self._count_context = None
        self._count_keys, self._other_keys = set(), set()
        self._unstable_keys = set()
        self.instability_origins = set()
        self._typed_read_changed = None

    def _require_unchanged(self, unchanged, key, origin, stage):
        if not unchanged:
            origins = (self.instability_origins if stage == 'registry_strict_count_gate'
                       else {origin})
            shared_count = (stage == 'registry_strict_count_gate' or
                (key in self._count_keys and key not in self._other_keys
                 and key[1] == 4 and not key[2]))
            # Output only: name the failed comparison, never an address/value
            # or publication/readiness authority. Mixed roles stay unclassified.
            self._typed_read_changed = dict(
                typed_read_changed_field=('SHARED_OWNER_COUNT' if shared_count
                                          else 'UNCLASSIFIED_TYPED_SPAN'),
                typed_read_changed_origin=('BOTH' if len(origins) == 2 else next(iter(origins))),
                typed_read_changed_stage=stage)
        need(unchanged, 'EDGE_TYPED_READ_CHANGED')

    def _count_changed(self, key, before, after, origin):
        if (key in self._count_keys and key not in self._other_keys
                and len(before) == len(after) == 4 and not key[2]
                and struct.unpack('<i', before)[0] > 0 and struct.unpack('<i', after)[0] > 0):
            self.instability_origins.add(origin)
            self._unstable_keys.add(key)
            return True
        return False

    def read(self, at, size, image=False):
        # Preserve the original _Budget checks and exactly one Native read.
        # inventory_observe's M1 kit query (up to 180 rows) sets its own larger limit.
        limit = BYTE_LIMIT if getattr(self, 'limit', None) is None else self.limit
        need(type(size) is int and self.spent + size <= limit, 'NPC_OBSERVE_BYTE_BUDGET')
        need(type(at) is int and type(size) is int and 0 < size <= 4096 and
             0x10000 <= at <= 0x7fffffffffff - size, 'EDGE_TYPED_READ_BOUND')
        need(self.spent + size <= (edge.LIMIT if getattr(self, 'byte_limit', None) is None else self.byte_limit),
             'EDGE_REQUEST_BYTE_BOUND')
        self.spent += size
        raw = self.native.read(at, size, self.sampler.g['base'] if image else None)
        need(type(raw) is bytes and len(raw) == size, 'EDGE_PARTIAL_TYPED_READ')
        if self.retain:
            key = (at, size, image)
            (self._count_keys if key == self._count_context else self._other_keys).add(key)
            self._require_unchanged(key not in self._unstable_keys or key not in self._other_keys,
                 key, 'INITIAL_DUPLICATE', 'count_role_collision')
            expected = self._retained.get(key)
            if expected is None:
                self._retained[key] = raw
                self.records.append((at, raw, image))
            else:
                self._require_unchanged(raw == expected or self._count_changed(key, expected, raw, 'INITIAL_DUPLICATE'),
                     key, 'INITIAL_DUPLICATE', 'typed_compare')
        return raw

    @contextmanager
    def installed(self):
        sampler = self.sampler
        present, original = 'strong_pair' in sampler.__dict__, sampler.strong_pair
        def strong_pair(raw):
            previous = self._count_context
            # Original strong_pair still validates pair bounds and count. This
            # context labels its existing scalar read; it adds no read itself.
            self._count_context = ((struct.unpack('<QQ', raw)[1] + 8, 4, False)
                                   if type(raw) is bytes and len(raw) == 16 else None)
            try:
                return original(raw)
            finally:
                self._count_context = previous
        sampler.strong_pair = strong_pair
        try:
            with super().installed():
                yield
        finally:
            if present:
                sampler.strong_pair = original
            else:
                sampler.__dict__.pop('strong_pair', None)

    def verify(self):
        self.retain = False
        try:
            for at, expected, image in self.records:
                actual = self.read(at, len(expected), image)
                self._require_unchanged(actual == expected or self._count_changed(
                    (at, len(expected), image), expected, actual, 'FINAL_READBACK'),
                     (at, len(expected), image), 'FINAL_READBACK', 'typed_compare')
            self._require_unchanged(not self._unstable_keys.intersection(self._other_keys),
                None, 'FINAL_READBACK', 'count_role_collision')
        finally:
            self.retain = True


def _resolve_monster(reads, sampler, proof, contract, common, actors, uid):
    """Private same-query exact pointer plus current grid; never public data.

    Caller owns source-before/after, typed/root rechecks, current authority and
    its existing read budget. The pointer is valid only inside that proof.
    """
    world, base, size = proof.world, sampler.g['base'], sampler.g['size']
    public = proof.public['Player']
    begin, count = world.vector(reads, actors, public['vector_begin'], public['vector_end'],
                                public['max_actor_elements'])
    for index in range(count):
        obj = reads.pair(reads.read(begin + index * 16, 16))[0]
        vp = reads.pointer(obj)
        need(base <= vp <= base + size - 16, 'NPC_OBSERVE_GETTER_TABLE_BOUNDS')
        getter = struct.unpack('<Q', sampler.read(vp + 8, 8, image=True))[0]
        need(getter == base + common['ID_getter_RVA'], 'NPC_OBSERVE_UID_GETTER_UNSUPPORTED')
        actual = struct.unpack('<Q', reads.read(obj + common['Actor_ID_u64_offset'], 8))[0]
        if actual != uid:
            continue
        # Exactly the source lookup's first UID match. An earlier non-Monster
        # match is UNKNOWN, never skipped in favour of a later Monster.
        proof.nav._source_type(reads, sampler, obj, contract, world)
        need(reads.pointer(obj + common['Actor_self_pointer_offset']) == obj,
             'NPC_OBSERVE_PRIMARY_ACTOR_SELF_CHANGED')
        segment, grid, reason = world.position(sampler, reads, obj, proof.public, proof.position_source)
        need(reason is None and type(grid) is list and len(grid) == 2
             and all(type(v) is int and 0 <= v <= 65535 for v in grid)
             and segment == [(v >> 6) + 0x7e00 for v in grid], 'NPC_OBSERVE_CURRENT_GRID_INVALID')
        return obj, grid
    raise ValueError('NPC_OBSERVE_UID_NOT_REGISTERED')


def _monster(reads, sampler, proof, contract, common, actors, uid):
    return _resolve_monster(reads, sampler, proof, contract, common, actors, uid)[1]


DIRECT_MOTION_SCOPE = 'READONLY_DIRECT_NPC_MOTION_STOP'
DIRECT_MOTION_PINS = {
    'work/local_server_rea_20261016/run77_npc_motion_components/findings.md':
        '198aa5316a1122e3cbae575f16dbae53227385f4bfd0ff88922f8d26ce2b6589',
    'work/local_server_rea_20261016/run77_npc_motion_components/source-evidence.json':
        'ab167c749e3c83b626e1582cd831b03e53beeed40017d27e99377326aaf29d4f',
    'work/local_server_rea_20261016/run77_npc_motion_components/main-review.json':
        '5a557fdef7a84c3f684ffcaa32bde613802952366f9e80c608358fcccdee3645',
}


def _direct_motion_source():
    """Accepted run77 source, including the source-bound Speed table/owner path."""
    documents = {}
    for path, expected in DIRECT_MOTION_PINS.items():
        file = observe.ordinary(observe.ROOT / path)
        need(0 < file.stat().st_size <= 1024 * 1024, 'NPC_DIRECT_MOTION_SOURCE_BOUND')
        raw = file.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == expected, 'NPC_DIRECT_MOTION_SOURCE_CHANGED')
        if file.suffix == '.json':
            documents[path] = json.loads(raw)
    source = documents['work/local_server_rea_20261016/run77_npc_motion_components/source-evidence.json']
    need(source['CONTROL_sha256'] == '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af',
         'NPC_DIRECT_MOTION_CONTROL_CHANGED')
    children = {}
    for suffix in ('initialization/source-evidence.json', 'consumer/source-evidence.json'):
        path = 'work/local_server_rea_20261016/run77_npc_motion_components/' + suffix
        rows = [row for row in source['worker_artifacts'] if row['path'].replace('\\', '/') == path]
        need(len(rows) == 1, 'NPC_DIRECT_MOTION_CHILD_SOURCE_REQUIRED')
        pin, = rows
        file = observe.ordinary(observe.ROOT / path)
        need(file.stat().st_size == pin['bytes'] and 0 < pin['bytes'] <= 1024 * 1024,
             'NPC_DIRECT_MOTION_SOURCE_BOUND')
        raw = file.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == pin['sha256'], 'NPC_DIRECT_MOTION_SOURCE_CHANGED')
        children[suffix] = json.loads(raw)
        need(children[suffix]['CONTROL_sha256'] == source['CONTROL_sha256'],
             'NPC_DIRECT_MOTION_CONTROL_CHANGED')
    initialization = children['initialization/source-evidence.json']
    speed, = [row for row in initialization['constructor_components'] if row['type'] == 'SpeedComponent']
    targets = [0x40dd0, 0xc0090, 0x40c30, 0x40c40, 0x40c50]
    need(speed['vptr_rva'] == '0x117de30' and speed['constructor_rva'] == '0x40c70'
         and speed['slots'] == {hex(i * 8): hex(v) for i, v in enumerate(targets)}
         and speed['type_descriptor_name'] == '.?AVSpeedComponent@lineage@@',
         'NPC_DIRECT_MOTION_SPEED_SOURCE_CHANGED')
    ctor, = [row for row in initialization['windows'] if row['label'] == 'S16_Speed_ctor_identity']
    getter, = [row for row in children['consumer/source-evidence.json']['functions'] if row['start'] == '0x58190']
    checks = [dict(rva=int(row['start'], 16), length=row['length'], sha256=row['sha256'])
              for row in (ctor, getter)]
    return dict(rva=0x117de30, targets=targets), checks


def _motion_source():
    """Reuse the existing Actor component/predicate sources, without MyPlayer substitution."""
    from tools.local_original_session import move_state
    layout = move_state.MoveState()  # Checks the existing exact saved-source pins.
    checks = []
    selected = {
        'work/local_server_rea_20261016/run5_move_update/update_source.json':
            ('functions', {'0x41450', '0x96ee0', '0x908a0', '0x94570'}),
        'work/local_server_rea_20261016/run7_navigation_observation/action_types_source.json':
            ('predicate_functions', {'0x99290', '0x99390'}),
    }
    for path, (key, wanted) in selected.items():
        raw = observe.ordinary(observe.ROOT / path).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == move_state.SOURCES[path], 'NPC_MOTION_SOURCE_CHANGED')
        functions = [row for row in json.loads(raw)[key] if row['rva'] in wanted]
        need({row['rva'] for row in functions} == wanted, 'NPC_MOTION_SOURCE_CONSUMER_MISSING')
        checks.extend(dict(rva=int(row['rva'], 16), length=int(row['end'], 16) - int(row['rva'], 16),
                           sha256=row['sha256']) for row in functions)
    # Existing exact type source used by the attack observer. Reuse its row
    # only for source-qualified MovingAction non-idle, never as a busy=false.
    timing_path = 'work/client_speed_research/code/timing-proof.json'
    raw = observe.ordinary(observe.ROOT / timing_path).read_bytes()
    need(hashlib.sha256(raw).hexdigest() ==
         'bd5d8d8bf5882d7c0ca4288ed06bbb9e8162016c7bc0899e2ef9fd9a2ec2dc26',
         'NPC_MOTION_SOURCE_CHANGED')
    rows = [row for row in json.loads(raw)['action_types']
            if row['type_name'] == '.?AVMovingAction@lineage@@']
    need(len(rows) == 1, 'NPC_MOTION_UNIQUE_MOVING_SOURCE_REQUIRED')
    moving, = rows
    slots = [0x94520, 0x94570, 0x949d0, 0x949c0, 0x94b30, 0x94d50, 0x907f0, 0x8f900]
    need(moving['table_rva'] == '0x1180ca8' and moving['methods'] == [hex(v) for v in slots],
         'NPC_MOTION_MOVING_SOURCE_CHANGED')
    layout.action_tables[0x1180ca8] = dict(kind='MovingAction', targets=slots)
    speed, direct_checks = _direct_motion_source()
    layout.tables['SpeedComponent'] = speed
    checks.extend(direct_checks)
    return layout, checks


def _motion_fields(reads, sampler, proof, actor, grid, actors, layout, diagnostic):
    """Same-query NPC snapshot. No pointers escape; no Start/frame/AI claim.

    Current null/exact Breath/Default use the original busy predicate. Exact
    MovingAction only proves non-idle. Unknown types never become pending.
    """
    from tools.local_original_session import move_state
    base = sampler.g['base']
    begin, count = proof.world.vector(reads, actor, 0x20, 0x28, 128)
    components = [reads.pair(reads.read(begin + i * 16, 16))[0] for i in range(count)]
    typed = [(obj, reads.pointer(obj)) for obj in components]

    def component(role):
        table = layout.tables[role]
        matches = [obj for obj, vp in typed if vp == base + table['rva']]
        if len(matches) != 1:
            # Unverified hints from this query's already-read vptrs. No object
            # pointer, extra read, type grant, or source/readback success escapes.
            diagnostic.update(component_contract=dict(role=role, match_count=len(matches),
                expected_table_rva=table['rva'], component_count=len(typed),
                observed_table_rvas=[vp - base if base <= vp < base + sampler.g['size'] else None
                                     for _, vp in typed[:8]], truncated=len(typed) > 8))
        need(len(matches) == 1, 'NPC_MOTION_UNIQUE_COMPONENT_REQUIRED')
        obj, = matches
        expected = struct.pack('<' + 'Q' * len(table['targets']), *(base + v for v in table['targets']))
        need(sampler.read(base + table['rva'], len(expected), image=True) == expected,
             'NPC_MOTION_COMPONENT_TABLE_CHANGED')
        need(reads.pointer(obj + 8) == actor, 'NPC_MOTION_COMPONENT_OWNER_CHANGED')
        # 41474 gates update dispatch, not snapshot readability or ownership.
        # Keep the physical read/recheck without making nonzero an idle grant.
        reads.read(obj + 0x30, 1)
        return obj

    transform = component('TransformComponent')
    coordinates = reads.read(transform + 0x38, 80)
    current = list(struct.unpack_from('<ii', coordinates, 8))
    predicted = list(struct.unpack_from('<ii', coordinates, 48))
    need(current == grid and all(0 <= v <= 65535 for v in predicted)
         and list(struct.unpack_from('<ii', coordinates, 40)) == [(v >> 6) + 0x7e00 for v in predicted],
         'NPC_MOTION_TRANSFORM_COORDINATES_INVALID')
    # The direct remote MovingAction interval dereferences Speed, with no null
    # fallback. Only existence/type/borrowed owner is read; no speed scalar.
    component('SpeedComponent')
    action = component('ActionComponent')
    flags = reads.read(action + 0x44, 12)
    pointer = struct.unpack('<Q', reads.read(action + 0xc0, 8))[0]
    need(pointer == 0 or 0x10000 <= pointer <= 0x7fffffffffff and pointer % 8 == 0,
         'NPC_MOTION_CURRENT_POINTER_INVALID')
    current_action = dict(status='OBSERVED', reason=None, present=bool(pointer), kind='none')
    if pointer:
        vp = reads.pointer(pointer)
        qualified = layout.action_tables.get(vp - base)
        need(qualified is not None and qualified['kind'] in ('BreathAction', 'DefaultAction', 'MovingAction'),
             'NPC_MOTION_ACTION_TYPE_UNSUPPORTED')
        expected = struct.pack('<8Q', *(base + v for v in qualified['targets']))
        need(sampler.read(vp, 64, image=True) == expected, 'NPC_MOTION_ACTION_TABLE_CHANGED')
        if qualified['kind'] == 'MovingAction':
            need(reads.pointer(pointer + 8) == action, 'NPC_MOTION_MOVING_OWNER_CHANGED')
        # 99290/99390 do not consume action+8 for Breath/Default. The retained
        # actor component pair/current pointer topology is physically rechecked.
        current_action.update(kind=qualified['kind'], finished=(reads.read(pointer + 0x24, 1) != b'\0'
                              if qualified['kind'] == 'DefaultAction' else None))
    header = reads.read(action + 0xa0, 32)
    map_pointer, map_size, offset, queue_count = struct.unpack('<QQQQ', header)
    if queue_count:
        need(0x10000 <= map_pointer <= 0x7fffffffffff and map_pointer % 8 == 0
             and 0 < map_size <= 4096 and map_size & (map_size - 1) == 0
             and queue_count <= map_size * 2, 'NPC_MOTION_QUEUE_BOUNDS')
    busy = move_state.busy_source_eval(current_action, flags[11], queue_count)
    # F6F83 gates subsystem update dispatch. False still permits an owned,
    # source-qualified idle snapshot; any byte drift remains UNKNOWN.
    reads.read(actors + 0x10, 1)
    # A nonempty exact queue rules out strict idle without interpreting its
    # head, extending a callable whitelist, or granting a retry authority.
    idle = (current_action['kind'] != 'MovingAction' and queue_count == 0 and busy['status'] == 'EVALUATED'
            and busy['value'] is False and predicted == grid)
    return dict(npc_idle=idle, navigation_active=None, action_kind=current_action['kind'],
                action_queue_count=queue_count, client_predicted_grid=predicted)


class NpcObserver:
    """Actual broker/reader authority; caller schedules <=2 Hz with now_ns.

    No attack intent is accepted or action emitted. Both awaited native-owner
    checks precede all memory reads; after them the read/rechecks/result path
    contains no await. Caller should use the existing row serialization.
    """
    def __init__(self, broker, reader):
        _source()
        self.targets = attack.AttackTargets(broker, reader)
        self.proof = edge.EdgeAdapter(reader)
        self._last_ns, self._inflight = None, False

    def _registry_current(self, writer, target_uid):
        """Current selected world only; no target-present or alive grant.

        This is the pre-target part of AttackTargets' existing projection.
        A removed-target tombstone is never queried or overridden here.
        """
        from tools.local_original_session.broker import LocalRealm, _TransportPolicy
        from tools.local_original_session import movement, npc
        targets, reader = self.targets, self.targets.reader
        broker, native = targets.broker, targets._reader_binding()
        policy, retained, member = broker.policy, reader.owner, reader.member
        need(not reader.closed and type(policy) is _TransportPolicy
             and retained is not None and not retained.closed and policy.owner is retained
             and member is not None and retained.child is member
             and attack._handle_value(policy.handle) == attack._handle_value(retained.owner_handle)
             and attack._handle_value(policy.job) == attack._handle_value(retained.owner_job)
             and member.process == retained.owner_handle and member.job == retained.owner_job,
             'NPC_REGISTRY_CURRENT_RETAINED_OWNER_REQUIRED')
        need(not broker._closing and not broker.failure.is_set() and policy.state == 'OPEN',
             'NPC_REGISTRY_CURRENT_BROKER_REQUIRED')
        rows = [r for values in broker._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_REGISTRY_CURRENT_CLAIM_REQUIRED')
        row, = rows
        admitted = policy._connection(writer)
        need(row['policy_row'] is admitted and admitted.writer is writer
             and admitted.stage == 1 and admitted.rx_boot == 2 and admitted.tx_boot == 3
             and not any((row['failed'], row['joined'], admitted.failed, admitted.eof,
                          admitted.task_joined, admitted.registry_removed))
             and row['operation_lock'].locked(), 'NPC_REGISTRY_CURRENT_LOCKED_CLAIM_REQUIRED')
        realm = broker.realm
        need(type(realm) is LocalRealm, 'NPC_REGISTRY_REAL_REALM_REQUIRED')
        game, service = realm.registry.resolve(writer), realm.service(writer)
        position = service.snapshot()
        need(type(service) is movement.MovementService and type(position) is movement.Position
             and service._connection is writer and service._store is realm.positions,
             'NPC_REGISTRY_SELECTED_SERVICE_REQUIRED')
        realm._npc_authority(writer, game, service, position)
        # This is the selected NPC generation owner, not proof that target_uid
        # remains in the client's registry or that its server HP is positive.
        bound = realm._npc_frames.get(id(writer))
        need(type(bound) is tuple and len(bound) == 4 and bound[0] is writer
             and bound[1] is game and bound[2] is service and type(bound[3]) is tuple
             and all(type(frame) is bytes for frame in bound[3]),
             'NPC_REGISTRY_SELECTED_NPC_GENERATION_REQUIRED')
        candidates = [(s, wire) for s, wire in realm._npc_spawns
                      if type(s) is npc.NpcSpawn and s.uid == target_uid]
        need(len(candidates) == 1 and candidates[0][0].map_id == position.map_id
             and target_uid != position.uid, 'NPC_REGISTRY_EXPLICIT_LOCAL_NPC_REQUIRED')
        spawn, wire = candidates[0]
        body = npc.session.world.encode_payload(0x4e96, spawn.fields)
        need(spawn.policy == npc.POLICY and type(wire) is bytes
             and wire == struct.pack('<HH', len(body) + 6, 0x4e96) + body + b'\0\0',
             'NPC_REGISTRY_EXPLICIT_LOCAL_NPC_FRAME_REQUIRED')
        refs = (targets, broker, policy, retained, member, member.identity, native, reader,
                broker.failure, row, row['peer'], row['operation_lock'], admitted, admitted.peer,
                realm, realm.registry, realm.store, realm.positions, game, game.selection,
                service, position, realm._npc_spawns, bound, bound[3], spawn)
        values = tuple(attack._handle_value(v) for v in (
            policy.handle, policy.job, retained.owner_handle, retained.owner_job,
            member.process, member.job, native.handle))
        values += tuple(attack._typed_value(v) for v in (
            member.pid, *(member.identity.get(k) for k in ('pid', 'birth', 'image', 'parent_pid')),
            admitted.peer.port, admitted.peer.client_port, admitted.peer.accepted_ns,
            *row['peer'].keys(), *row['peer'].values(),
            wire, *bound[3], spawn.uid, spawn.map_id, spawn.policy))
        return row, position, refs, values

    def _registry_selection(self, writer, target_uid):
        # Retain both identities and typed scalar values across the validator,
        # exactly as AttackTargets._project does for a present target. The
        # selected-world proof deliberately has no NPC frame/liveness grant.
        before = self._registry_current(writer, target_uid)
        self.targets.reader.validate()
        after = self._registry_current(writer, target_uid)
        need(attack._same_binding(after[2], after[3], before[2], before[3]),
             'NPC_REGISTRY_SELECTION_CHANGED')
        return after

    async def sample_registry(self, writer, target_uid, *, now_ns):
        """Three source lookup vectors in one passive READONLY_SNAPSHOT.

        Exact source pure UID interface for every entry. No remove execution,
        selection-table/other-UID effects, memory-free claim or target grant.
        Shares the existing observer slot/cadence and independent 16-KiB cap.
        """
        result = dict(status='UNKNOWN', reason='NOT_SAMPLED', uid=None, map_id=None,
            lookup_scope='THREE_LOOKUP_VECTORS', observation_scope='READONLY_SNAPSHOT',
            uid_absent=None, vector_counts=None, snapshot_atomic=False,
            source_contract_valid=False, stable_double_read=False,
            typed_bytes_requested=0, typed_byte_limit=BYTE_LIMIT, max_samples_per_second=2)
        budget, entered = None, False
        try:
            need(not self._inflight, 'NPC_OBSERVE_INFLIGHT')
            need(type(now_ns) is int and 0 <= now_ns < (1 << 63), 'NPC_OBSERVE_MONOTONIC_NS_REQUIRED')
            need(self._last_ns is None or now_ns - self._last_ns >= MIN_INTERVAL_NS, 'NPC_OBSERVE_CADENCE')
            need(type(target_uid) is int and 0 < target_uid < attack.U64_MAX, 'NPC_REGISTRY_UID_REQUIRED')
            self._last_ns, self._inflight, entered = now_ns, True, True
            attack.source_ready()
            initial = self._registry_selection(writer, target_uid)
            broker, targets, proof = self.targets.broker, self.targets, self.proof
            reader = targets.reader
            for _ in range(2):
                need(await broker._movement_owner(writer, initial[0], initial[1]) is True,
                     'NPC_REGISTRY_CURRENT_NATIVE_OWNER_REQUIRED')
                after = self._registry_selection(writer, target_uid)
                need(attack._same_binding(after[2], after[3], initial[2], initial[3]),
                     'NPC_REGISTRY_SELECTION_CHANGED')
            need(proof.reader is reader, 'NPC_OBSERVE_SAME_READER_REQUIRED')
            monster, common, inherited = _source()
            player, player_common, _ = _source('MyPlayer')
            need(common == player_common and common['Actor_ID_u64_offset'] == 0x18
                 and common['ID_getter_RVA'] == proof.lookup_contract['getter_rva'] == 0x40c00,
                 'NPC_REGISTRY_COMMON_UID_SOURCE_CHANGED')
            _registry_lookup_source()
            native, sampler = proof._binding()
            retained = (reader.owner, reader.member, reader.backend, reader.sampler)
            checks = inherited + proof.public['Position']['source_checks'] + proof.lookup_contract['code_checks']
            checks = list({(c['rva'], c['length'], c['sha256']): c for c in checks}.values())
            budget = _ObservationBudget(native, sampler)
            with budget.installed():
                proof._code(sampler, budget, checks)
                position = initial[1]
                reads, actors, _, route, state, scene_raw, _ = edge._world(
                    native, sampler, proof.public, proof.world, proof.position_source,
                    position.uid, position.map_id, (position.word0, position.word1), require_current_start=False)
                counts, matches = [], 0
                for vector_index, offset in enumerate((0x8a8, 0x8c0, 0x8d8)):
                    begin, count = proof.world.vector(reads, actors, offset, offset + 8,
                                                      proof.public['Player']['max_actor_elements'])
                    counts.append(count)
                    for index in range(count):
                        obj = reads.pair(reads.read(begin + index * 16, 16))[0]
                        vp = reads.pointer(obj)
                        base, size = sampler.g['base'], sampler.g['size']
                        if not base <= vp <= base + size - 16:
                            # Already-read vptr only; never inspect an unknown
                            # table/object or manufacture a UID for diagnosis.
                            rva = vp - base
                            result.update(unsupported_type_rva=rva if 0 <= rva < size else None,
                                          unsupported_vector_index=vector_index)
                        need(base <= vp <= base + size - 16, 'NPC_REGISTRY_UID_TABLE_IMAGE_BOUNDS')
                        # 627B0 passes this exact owning-vector pair.object to
                        # virtual+8 in all three vectors, without adjusting this.
                        # Reuse the existing edge prefix UID interface: actual
                        # MEM_IMAGE slot must be the exact pure 40C00 entry.
                        # This proves lookup's u64 result, never concrete type.
                        getter = struct.unpack('<Q', sampler.read(vp + 8, 8, image=True))[0]
                        if getter != base + common['ID_getter_RVA']:
                            result.update(unsupported_type_rva=vp - base,
                                          unsupported_vector_index=vector_index)
                        need(getter == base + common['ID_getter_RVA'],
                             'NPC_OBSERVE_UID_GETTER_UNSUPPORTED')
                        actual = struct.unpack('<Q', reads.read(obj + common['Actor_ID_u64_offset'], 8))[0]
                        matches += actual == target_uid
                budget.verify()
                budget._require_unchanged(not budget.instability_origins,
                    None, None, 'registry_strict_count_gate')
                budget.retain = False
                try:
                    need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                         'NPC_OBSERVE_WORLD_OWNER_CHANGED')
                finally:
                    budget.retain = True
                proof._code(sampler, budget, checks)
            need(self.targets is targets and self.proof is proof and targets.reader is reader
                 and proof._binding() == (native, sampler)
                 and all(a is b for a, b in zip(retained,
                     (reader.owner, reader.member, reader.backend, reader.sampler))),
                 'NPC_REGISTRY_RETAINED_QUERY_CHANGED')
            after = self._registry_selection(writer, target_uid)
            need(attack._same_binding(after[2], after[3], initial[2], initial[3]),
                 'NPC_REGISTRY_SELECTION_CHANGED')
            attack.source_ready()
            _source()
            _source('MyPlayer')
            _registry_lookup_source()
            result.update(status='OBSERVED', reason=None, uid=target_uid, map_id=position.map_id,
                uid_absent=matches == 0, vector_counts=counts,
                source_contract_valid=True, stable_double_read=True)
        except Exception as error:
            result['reason'] = observe.reason(error)
            if (result['reason'] == 'EDGE_TYPED_READ_CHANGED' and budget is not None
                    and budget._typed_read_changed is not None):
                result.update(budget._typed_read_changed)
        finally:
            if entered:
                self._inflight = False
            result['typed_bytes_requested'] = 0 if budget is None else budget.spent
        return result

    async def sample(self, writer, target_uid, *, now_ns):
        return await self._sample(writer, target_uid, now_ns=now_ns, motion=False)

    async def sample_motion(self, writer, target_uid, *, now_ns):
        """Pose plus source-evaluated NPC idle in one existing <=2-Hz slot.

        Shares cadence/budget with sample/registry. Every new result field is
        withheld unless the full original source/owner/readback proof finishes.
        """
        return await self._sample(writer, target_uid, now_ns=now_ns, motion=True)

    async def _sample(self, writer, target_uid, *, now_ns, motion):
        # Last entered execution region only: not completion/authority or
        # eligibility to retry, wait, post a command, or reuse a stale sample.
        result = dict(status='UNKNOWN', reason='NOT_SAMPLED', uid=None, map_id=None,
            server_grid=None, client_grid=None, coordinates_match=None,
            source_contract_valid=False, stable_double_read=False, snapshot_atomic=False,
            visible_screen_claimed=False, typed_bytes_requested=0, typed_byte_limit=BYTE_LIMIT,
            max_samples_per_second=2, client_grid_used_as_authority=False,
            observation_stage='REQUEST', read_consistency='NOT_CLASSIFIED', source_owner_revalidated=False)
        if motion:
            result.update(npc_idle=None, navigation_active=None, action_kind=None,
                          action_queue_count=None, client_predicted_grid=None, motion_scope=DIRECT_MOTION_SCOPE)
        budget, entered = None, False
        motion_diagnostic = {}
        try:
            need(not self._inflight, 'NPC_OBSERVE_INFLIGHT')
            need(type(now_ns) is int and 0 <= now_ns < (1 << 63), 'NPC_OBSERVE_MONOTONIC_NS_REQUIRED')
            need(self._last_ns is None or now_ns - self._last_ns >= MIN_INTERVAL_NS,
                 'NPC_OBSERVE_CADENCE')
            self._last_ns, self._inflight, entered = now_ns, True, True
            result['observation_stage'] = 'AUTHORIZE'
            bound = await self.targets.authorize(writer, attack.AttackRequest(target_uid))
            result['observation_stage'] = 'OWNER_CHECKPOINT'
            await self.targets.checkpoint(bound)
            # No await from here through the final authority projection.
            result['observation_stage'] = 'SOURCE_BEFORE'
            targets = self.targets
            reader, proof = targets.reader, self.proof
            need(proof.reader is reader, 'NPC_OBSERVE_SAME_READER_REQUIRED')
            monster, common, inherited = _source()
            if motion:
                motion_layout, motion_checks = _motion_source()
            native, sampler = proof._binding()
            retained = (reader.owner, reader.member, reader.backend, reader.sampler, native.handle)
            checks = inherited + proof.public['Position']['source_checks'] + proof.lookup_contract['code_checks']
            if motion:
                checks = checks + motion_checks
            checks = list({(c['rva'], c['length'], c['sha256']): c for c in checks}.values())
            result.update(uid=bound.target_uid, map_id=bound.map_id,
                          server_grid=[bound.target_x, bound.target_y])
            budget = _ObservationBudget(native, sampler)
            with budget.installed():
                proof._code(sampler, budget, checks)
                result['observation_stage'] = 'WORLD_TYPED'
                reads, actors, _, route, state, scene_raw, _ = edge._world(native, sampler, proof.public,
                    proof.world, proof.position_source, bound.attacker.uid, bound.map_id,
                    (bound.target_x, bound.target_y), require_current_start=False)
                result['observation_stage'] = 'MONSTER_TYPED'
                if motion:
                    actor, grid = _resolve_monster(reads, sampler, proof, monster, common, actors, bound.target_uid)
                    motion_fields = _motion_fields(reads, sampler, proof, actor, grid, actors, motion_layout, motion_diagnostic)
                else:
                    grid = _monster(reads, sampler, proof, monster, common, actors, bound.target_uid)
                result['observation_stage'] = 'FINAL_READBACK'
                budget.verify()
                result['observation_stage'] = 'ROOT_RECHECK'
                budget.retain = False
                try:
                    need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                         'NPC_OBSERVE_WORLD_OWNER_CHANGED')
                finally:
                    budget.retain = True
                result['observation_stage'] = 'SOURCE_AFTER'
                proof._code(sampler, budget, checks)
            # Verify restored methods as well as the exact retained validator.
            result['observation_stage'] = 'AUTHORITY_AFTER'
            need(self.targets is targets and self.proof is proof and targets.reader is reader,
                 'NPC_OBSERVE_PRODUCER_CHANGED')
            need(proof._binding() == (native, sampler), 'NPC_OBSERVE_READER_CHANGED')
            need(all(a is b for a, b in zip(retained,
                (reader.owner, reader.member, reader.backend, reader.sampler, native.handle))),
                 'NPC_OBSERVE_RETAINED_OWNER_CHANGED')
            targets.revalidate(bound)
            _source()
            if motion:
                final_layout, final_checks = _motion_source()
                need(final_checks == motion_checks and final_layout.tables == motion_layout.tables
                     and final_layout.action_tables == motion_layout.action_tables,
                     'NPC_MOTION_SOURCE_CHANGED')
            if budget.instability_origins:
                need(grid == result['server_grid'], 'NPC_OBSERVE_CURRENT_POSITION_MISMATCH')
                origin = ('BOTH' if len(budget.instability_origins) == 2
                          else next(iter(budget.instability_origins)))
                if motion:
                    # The exact strong-pair predicate is count>0, not equality.
                    # Every other used byte, source/root/current owner check
                    # finished above. This remains neither raw-byte stability
                    # nor a real retain/atomic/lifetime proof.
                    result.update(status='OBSERVED', reason=None, client_grid=grid,
                        coordinates_match=True, source_contract_valid=True,
                        stable_double_read=False, observation_stage='COMPLETE',
                        read_consistency='SOURCE_PREDICATE_RECHECKED_SHARED_COUNT_' + origin,
                        source_owner_revalidated=True)
                    result.update(motion_fields)
                    return result
                # All original query/post-checks completed, but raw equality
                # did not. No client coordinates or strict success are emitted.
                result.update(reason='EDGE_TYPED_READ_CHANGED', source_owner_revalidated=True,
                    read_consistency='RECHECKED_SHARED_COUNT_' + origin)
                return result
            result.update(status='OBSERVED', reason=None, client_grid=grid,
                coordinates_match=grid == result['server_grid'], source_contract_valid=True,
                stable_double_read=True, observation_stage='COMPLETE', read_consistency='STRICT_STABLE',
                source_owner_revalidated=True)
            if motion:
                result.update(motion_fields)
        except Exception as error:
            result['reason'] = observe.reason(error)
            if motion and result['reason'] == 'NPC_MOTION_UNIQUE_COMPONENT_REQUIRED':
                result.update(motion_diagnostic)
        finally:
            if entered:
                self._inflight = False
            result['typed_bytes_requested'] = 0 if budget is None else budget.spent
        return result
