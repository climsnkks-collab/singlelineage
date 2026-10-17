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


def _source():
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
    rows = [r for r in coverage['actor_types'] if r['name'] == 'Monster']
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
        need(type(size) is int and self.spent + size <= BYTE_LIMIT, 'NPC_OBSERVE_BYTE_BUDGET')
        need(type(at) is int and type(size) is int and 0 < size <= 4096 and
             0x10000 <= at <= 0x7fffffffffff - size, 'EDGE_TYPED_READ_BOUND')
        need(self.spent + size <= edge.LIMIT, 'EDGE_REQUEST_BYTE_BOUND')
        self.spent += size
        raw = self.native.read(at, size, self.sampler.g['base'] if image else None)
        need(type(raw) is bytes and len(raw) == size, 'EDGE_PARTIAL_TYPED_READ')
        if self.retain:
            key = (at, size, image)
            (self._count_keys if key == self._count_context else self._other_keys).add(key)
            need(key not in self._unstable_keys or key not in self._other_keys,
                 'EDGE_TYPED_READ_CHANGED')
            expected = self._retained.get(key)
            if expected is None:
                self._retained[key] = raw
                self.records.append((at, raw, image))
            else:
                need(raw == expected or self._count_changed(key, expected, raw, 'INITIAL_DUPLICATE'),
                     'EDGE_TYPED_READ_CHANGED')
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
                need(actual == expected or self._count_changed(
                    (at, len(expected), image), expected, actual, 'FINAL_READBACK'),
                     'EDGE_TYPED_READ_CHANGED')
            need(not self._unstable_keys.intersection(self._other_keys), 'EDGE_TYPED_READ_CHANGED')
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

    async def sample(self, writer, target_uid, *, now_ns):
        # Last entered execution region only: not completion/authority or
        # eligibility to retry, wait, post a command, or reuse a stale sample.
        result = dict(status='UNKNOWN', reason='NOT_SAMPLED', uid=None, map_id=None,
            server_grid=None, client_grid=None, coordinates_match=None,
            source_contract_valid=False, stable_double_read=False, snapshot_atomic=False,
            visible_screen_claimed=False, typed_bytes_requested=0, typed_byte_limit=BYTE_LIMIT,
            max_samples_per_second=2, client_grid_used_as_authority=False,
            observation_stage='REQUEST', read_consistency='NOT_CLASSIFIED', source_owner_revalidated=False)
        budget, entered = None, False
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
            native, sampler = proof._binding()
            retained = (reader.owner, reader.member, reader.backend, reader.sampler, native.handle)
            checks = inherited + proof.public['Position']['source_checks'] + proof.lookup_contract['code_checks']
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
            if budget.instability_origins:
                need(grid == result['server_grid'], 'NPC_OBSERVE_CURRENT_POSITION_MISMATCH')
                # All original query/post-checks completed, but raw equality
                # did not. No client coordinates or strict success are emitted.
                origin = ('BOTH' if len(budget.instability_origins) == 2
                          else next(iter(budget.instability_origins)))
                result.update(reason='EDGE_TYPED_READ_CHANGED', source_owner_revalidated=True,
                    read_consistency='RECHECKED_SHARED_COUNT_' + origin)
                return result
            result.update(status='OBSERVED', reason=None, client_grid=grid,
                coordinates_match=grid == result['server_grid'], source_contract_valid=True,
                stable_double_read=True, observation_stage='COMPLETE', read_consistency='STRICT_STABLE',
                source_owner_revalidated=True)
        except Exception as error:
            result['reason'] = observe.reason(error)
        finally:
            if entered:
                self._inflight = False
            result['typed_bytes_requested'] = 0 if budget is None else budget.spent
        return result
