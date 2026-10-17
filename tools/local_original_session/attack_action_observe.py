"""One-use attack observation leaf inside the existing retained sample.

prepare() runs under the broker's existing row serialization before its one
scheduled reader.sample(). collect() belongs inside that sample, after
MoveState.sample, using the same proof and its explicit 24-KiB attack total.
The preceding world/input/movement aggregate remains 16 KiB. There is
no sample(), thread, native invocation, packet, clock or memory write here.
Snapshots cannot witness Start, rendering, damage, HP or absence of prediction.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from tools.local_original_session import attack, move_state, npc_observe, observe

need = observe.need
# Explicit attack leaf only: the unchanged 16-KiB preceding observation plus
# its original 8192-B leaf allowance. This is not a gameplay/admission rule.
BYTE_LIMIT = observe.RETAINED_SAMPLE_LIMIT + 8192
MIN_INTERVAL_NS = 500_000_000
METADATA = 'D:/CodexArtifacts/single-lineage/01a120a3-0ca6-7a11-a30b-45f330d3a1a3/source-death-hit/final-metadata.json'
PINS = {
    **attack.SOURCE_PINS,
    'work/online_public_session-v4/source-contract.json':
        '5150ac7b24a0497210615876fb6d1560b21ed5e809809434999bbf26f6a2d222',
    'work/local_server_rea_20261016/run25_attack_self_action/source-evidence.json':
        'fd57e2fe4e5cde4899a1650c5c6d6fa57f6fced0c977f1988f93f3cbda69fa9a',
    'work/local_server_rea_20261016/run25_attack_self_action/findings.md':
        'ddf8029b06fa570dccbaf04386439b92f5927e20435405d8c228fe633fd78b33',
    'work/local_server_rea_20261016/run25_attack_self_action/start/source-evidence.json':
        '908f3bc46b579a0c92581ee3fb898884768b867e58296b279bf58a7e3a1b567b',
    'work/local_server_rea_20261016/run25_attack_self_action/commit/source-evidence.json':
        '2484f2052f413e56ca5d86102776d87afa5f731c0c0c3148ebe512834836e897',
    'work/local_server_rea_20261016/run27_attack_effect/source-evidence.json':
        'b1d5c7504192e21fabd99a8d9a2208cf2f996fed2a1d15fad00dfe53e225a9d4',
    'work/local_server_rea_20261016/run27_attack_effect/findings.md':
        'f2e99ab37f1ca0fb6fa5306b8e898a3de07d873e8a07feae232c8c7e18ed4c4f',
    'work/client_speed_research/code/timing-proof.json':
        'bd5d8d8bf5882d7c0ca4288ed06bbb9e8162016c7bc0899e2ef9fd9a2ec2dc26',
    'work/source_death_hit_research_20261010/SOURCE_MANIFEST.json':
        'ff394c26fd43cada568e80c8872c4f6d71e11a5555fedd85835df4cebf6fa7b1',
    METADATA: 'e48039b5abc35c82de009cc08c241e8f7672b7f6fad4ae1fe6ef0032b6f3b584',
}


def _source():
    documents = {}
    for relative, expected in PINS.items():
        file = observe.ordinary(Path(relative) if Path(relative).is_absolute() else observe.ROOT / relative)
        need(0 < file.stat().st_size <= 2 * 1024 * 1024, 'ATTACK_OBSERVE_SOURCE_BOUND')
        raw = file.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == expected, 'ATTACK_OBSERVE_SOURCE_CHANGED')
        if file.suffix == '.json':
            documents[relative] = json.loads(raw)
    run24 = documents['work/local_server_rea_20261016/run24_normal_attack/source-evidence.json']
    timing = documents['work/client_speed_research/code/timing-proof.json']
    row, = [r for r in timing['action_types'] if r['type_name'] == '.?AVAttackAction@lineage@@']
    need(row['methods'] == run24['known_action_vtable'] and row['table_rva'] == '0x1180b78',
         'ATTACK_OBSERVE_TABLE_SOURCE_CHANGED')
    damaged, = [r for r in documents[METADATA]['RTTI'] if r['name'] == '.?AVDamagedAction@lineage@@']
    need(damaged['vptr_rva'] == '0x1180bc0', 'ATTACK_OBSERVE_DAMAGED_SOURCE_CHANGED')
    action = dict(kind='AttackAction', rva=int(row['table_rva'], 16),
        targets=[int(v, 16) for v in row['methods']], COL_rva=int(row['COL_rva'], 16),
        COL_sha256=row['COL_sha256'], descriptor_rva=int(row['type_descriptor_rva'], 16),
        literal=row['type_name'])
    damage = dict(kind='DamagedAction', rva=int(damaged['vptr_rva'], 16),
        targets=[int(v, 16) for v in damaged['slots8']], COL_rva=int(damaged['COL_rva'], 16),
        COL_sha256=damaged['COL_sha256'], descriptor_rva=int(damaged['descriptor_rva'], 16),
        literal=damaged['name'])
    return action, damage, documents['work/online_public_session-v4/source-contract.json']


def empty(reason='NOT_SAMPLED'):
    return dict(status='UNKNOWN', reason=reason, source_contract_valid=False,
        stable_double_read=False, snapshot_atomic=False, start_observed=False,
        rendered_claimed=False, hp_claimed=False, actor_uid=None, target_uid=None,
        map_id=None, attacker=None, target=None, typed_bytes_requested=0,
        combined_typed_bytes_requested=0, typed_byte_limit=BYTE_LIMIT,
        refused_read_bytes=None, shortfall_at_refused_read=None,
        observation_scope='READONLY_SNAPSHOT', queue_scope='HEAD_ONLY')


class SameQueryCache:
    """Only completed WORLD/MOVE reads from this retained query are reusable.

    MoveState still performs every original physical/readback operation. This
    object captures their bytes; it never services MoveState reads itself.
    Attack's final physical readback is independent of both producer roles.
    """
    def __init__(self, reader, sampler, proof, world):
        self.reader, self.sampler, self.proof = reader, sampler, proof
        self.roles = {'WORLD': dict(world)}
        self._move, self._conflict = {}, False

    def capture(self, role, at, size, image, raw):
        need(role == 'MOVE', 'ATTACK_OBSERVE_CACHE_ROLE_REQUIRED')
        key = at, size, image
        previous = self._move.get(key)
        if previous is not None and previous != raw:
            self._conflict = True
        self._move[key] = raw

    def finish_move(self, row):
        self.roles.pop('MOVE', None)
        if (row.get('status') == 'OBSERVED' and row.get('source_contract_valid') is True
                and row.get('stable_double_read') is True):
            self.roles['MOVE'] = self._move
        else:
            self._move = {}
            self._conflict = False

    def validate(self, reader, sampler, proof):
        need(self.reader is reader and self.sampler is sampler and self.proof is proof
             and set(self.roles) <= {'WORLD', 'MOVE'}, 'ATTACK_OBSERVE_SAME_QUERY_CACHE_REQUIRED')
        need(not self._conflict, 'ATTACK_OBSERVE_CACHE_TYPED_READ_CHANGED')

    def get(self, key):
        values = [role[key] for role in self.roles.values() if key in role]
        need(not values or all(value == values[0] for value in values),
             'ATTACK_OBSERVE_CACHE_TYPED_READ_CHANGED')
        return values[0] if values else None


class _Reads:
    """Same sampler total; cached first values still receive physical readback."""
    def __init__(self, sampler, cache):
        self.s = sampler
        self.cache = cache or {}
        self.records = {}
        self.refused = self.shortfall = None

    def physical(self, at, size, image=False):
        need(type(at) is int and type(size) is int and 0 < size <= 4096
             and 0x10000 <= at <= 0x7fffffffffff - size, 'ATTACK_OBSERVE_READ_BOUND')
        if self.s.total + size > BYTE_LIMIT:
            self.refused, self.shortfall = size, self.s.total + size - BYTE_LIMIT
            raise ValueError('ATTACK_OBSERVE_COMBINED_BYTE_BOUND')
        raw = self.s.read(at, size, image=image)
        need(type(raw) is bytes and len(raw) == size, 'ATTACK_OBSERVE_PARTIAL_READ')
        return raw

    def read(self, at, size, image=False):
        key = at, size, image
        if key not in self.records:
            raw = self.cache.get(key)
            if raw is None:
                raw = self.physical(at, size, image)
            need(type(raw) is bytes and len(raw) == size, 'ATTACK_OBSERVE_PARTIAL_READ')
            self.records[key] = raw
        return self.records[key]

    def number(self, at, fmt):
        return struct.unpack(fmt, self.read(at, struct.calcsize(fmt)))[0]

    @staticmethod
    def pointer_value(value, nullable=False):
        need((nullable and value == 0) or 0x10000 <= value <= 0x7fffffffffff and value % 8 == 0,
             'ATTACK_OBSERVE_POINTER_BOUND')
        return value

    def pointer(self, at, nullable=False):
        return self.pointer_value(self.number(at, '<Q'), nullable)

    def pair(self, raw):
        obj, control = struct.unpack('<QQ', raw)
        self.pointer_value(obj); self.pointer_value(control)
        need(self.number(control + 8, '<i') > 0, 'ATTACK_OBSERVE_PAIR_NOT_POSITIVE')
        return obj

    def vector(self, obj, offset, maximum):
        begin, end = struct.unpack('<QQ', self.read(obj + offset, 16))
        need(begin == end == 0 or 0x10000 <= begin <= end <= 0x7fffffffffff
             and (begin | end) % 8 == 0 and (end - begin) % 16 == 0,
             'ATTACK_OBSERVE_VECTOR_BOUND')
        need((end - begin) // 16 <= maximum, 'ATTACK_OBSERVE_VECTOR_COUNT_BOUND')
        return [self.pair(self.read(at, 16)) for at in range(begin, end, 16)]

    def table(self, obj, row):
        base = self.s.g['base']
        need(self.pointer(obj) == base + row['rva'], 'ATTACK_OBSERVE_TYPE_CHANGED')
        targets = row['targets']
        need(self.read(base + row['rva'], len(targets) * 8, True) ==
             struct.pack('<' + 'Q' * len(targets), *(base + v for v in targets)),
             'ATTACK_OBSERVE_TABLE_CHANGED')

    def normalized_table(self, obj, row):
        base = self.s.g['base']
        need(self.pointer(obj) == base + row['rva'], 'ATTACK_OBSERVE_TYPE_CHANGED')
        raw = self.read(base + row['rva'], row['prefix_bytes'], True)
        values = struct.unpack('<' + 'Q' * (len(raw) // 8), raw)
        need(all(base <= value < base + self.s.g['size'] for value in values),
             'ATTACK_OBSERVE_TABLE_TARGET_BOUND')
        normalized = struct.pack('<' + 'Q' * len(values), *(v - base for v in values))
        need(hashlib.sha256(normalized).hexdigest() == row['normalized_sha256'],
             'ATTACK_OBSERVE_TABLE_CHANGED')

    def rtti(self, row):
        base = self.s.g['base']
        need(struct.unpack('<Q', self.read(base + row['rva'] - 8, 8, True))[0] == base + row['COL_rva'],
             'ATTACK_OBSERVE_COL_POINTER_CHANGED')
        need(hashlib.sha256(self.read(base + row['COL_rva'], 24, True)).hexdigest() == row['COL_sha256'],
             'ATTACK_OBSERVE_COL_CHANGED')
        literal = row['literal'].encode('ascii') + b'\0'
        need(self.read(base + row['descriptor_rva'] + 16, len(literal), True) == literal,
             'ATTACK_OBSERVE_RTTI_CHANGED')

    def verify(self):
        for (at, size, image), expected in self.records.items():
            need(self.physical(at, size, image) == expected, 'ATTACK_OBSERVE_TYPED_READ_CHANGED')


class AttackActionObserver:
    def __init__(self, broker, reader):
        _source()
        self.targets = attack.AttackTargets(broker, reader)
        self.reader = reader
        self.layout = move_state.MoveState()
        self._prepared = None
        self._prepared_sampler = None
        self._last_ns = None
        self._preparing = False

    async def prepare(self, writer, target_uid, *, now_ns):
        """One existing <=2-Hz slot; hold the caller's row lock through collect."""
        need(not self._preparing, 'ATTACK_OBSERVE_PREPARE_INFLIGHT')
        self._prepared = None
        self._prepared_sampler = None
        need(type(now_ns) is int and 0 <= now_ns < (1 << 63), 'ATTACK_OBSERVE_MONOTONIC_NS_REQUIRED')
        need(self._last_ns is None or now_ns - self._last_ns >= MIN_INTERVAL_NS,
             'ATTACK_OBSERVE_CADENCE')
        self._last_ns, self._preparing = now_ns, True
        try:
            bound = await self.targets.authorize(writer, attack.AttackRequest(target_uid))
            await self.targets.checkpoint(bound)
            self._prepared_sampler = self.reader.sampler
            self._prepared = bound
        finally:
            self._preparing = False

    def collect(self, scene_row, world_row, proof, cache=None):
        """Consume the current query's private proof; never call reader.sample."""
        result, reads = empty(), None
        reader, bound = self.reader, self._prepared
        self._prepared = None
        sampler, started = reader.sampler, reader.sampler.total
        previous_bytes, previous_limit = sampler.bytes, sampler.read_limit
        sampler.bytes, sampler.read_limit = 0, 8192
        try:
            need(bound is not None, 'ATTACK_OBSERVE_PREPARE_REQUIRED')
            need(self.targets.reader is reader and reader.sample_byte_limit == observe.RETAINED_SAMPLE_LIMIT
                 and type(sampler) is reader.sampler_module.Sampler
                 and (self._prepared_sampler is None or self._prepared_sampler is sampler)
                 and sampler.b is reader.backend and sampler.c is reader.contract,
                 'ATTACK_OBSERVE_SAME_SAMPLER_REQUIRED')
            if 'move_state' in scene_row:
                move = scene_row['move_state']
                # The extra allowance cannot rescue a preceding budget failure.
                # All other UNKNOWNs retain their original independent meaning.
                reasons = [move.get('reason')]
                reasons += [value.get(key) for value in move.values() if type(value) is dict
                            for key in ('reason', 'queue_reason')]
                need(not any(reason in ('MOVE_COMBINED_BYTE_BOUND', 'RETAINED_SAMPLE_BYTE_BUDGET',
                                        'sample_byte_budget', 'total_byte_budget') for reason in reasons),
                     'ATTACK_OBSERVE_MOVE_PROOF_REQUIRED')
            self.targets.revalidate(bound)
            action_type, damage_type, public = _source()
            move_state.attack_sources_ready()
            monster, common, source_checks = npc_observe._source()
            need(scene_row.get('status') == 'OBSERVED' and scene_row.get('current') == 'Land'
                 and scene_row.get('pending') == 'none' and scene_row.get('root_ready') is True,
                 'ATTACK_OBSERVE_STABLE_LAND_REQUIRED')
            need(world_row.get('status') == 'OBSERVED' and world_row.get('stable_double_read') is True
                 and world_row.get('my_player_uid') == bound.attacker.uid
                 and world_row.get('map_resolved_i32') == bound.map_id,
                 'ATTACK_OBSERVE_SELECTED_WORLD_REQUIRED')
            route, state, raw = proof['route'], proof['state'], proof['raw']
            need(type(route) is tuple and route[1] is True and route[2] == 7
                 and type(raw) is bytes and len(raw) == 36
                 and struct.unpack_from('<I', raw, 32)[0] == 5
                 and proof['scene']['current']['kind'] == 'Land'
                 and proof['scene']['pending']['kind'] == 'none', 'ATTACK_OBSERVE_ROOT_PROOF_REQUIRED')
            need(type(sampler.g['base']) is int and sampler.g['base'] % 65536 == 0
                 and sampler.g['size'] == reader.contract['image_size'], 'ATTACK_OBSERVE_IMAGE_REQUIRED')
            if isinstance(cache, SameQueryCache):
                need(type(cache) is SameQueryCache, 'ATTACK_OBSERVE_SAME_QUERY_CACHE_REQUIRED')
                cache.validate(reader, sampler, proof)
            reads = _Reads(sampler, cache)
            base, tables = sampler.g['base'], self.layout.tables
            def source_code():
                for check in source_checks:
                    need(hashlib.sha256(reads.physical(base + check['rva'], check['length'], True)).hexdigest()
                         == check['sha256'], 'ATTACK_OBSERVE_SOURCE_CODE_CHANGED')
            source_code()
            matches = [reads.pair(pair) for pair, vp in route[-2]
                       if vp == base + tables['ActorSubsystem']['rva']]
            need(len(matches) == 1, 'ATTACK_OBSERVE_UNIQUE_ACTOR_SUBSYSTEM_REQUIRED')
            actor_sub, = matches
            reads.table(actor_sub, tables['ActorSubsystem'])
            map_type = public['Map']['table']
            maps = [reads.pair(pair) for pair, vp in route[-2] if vp == base + map_type['rva']]
            need(len(maps) == 1, 'ATTACK_OBSERVE_UNIQUE_MAP_REQUIRED')
            map_sub, = maps
            reads.normalized_table(map_sub, map_type)
            context = reads.pointer(map_sub + public['Map']['context_pointer'])
            need([reads.number(at, '<i') for at in
                  (map_sub + public['Map']['field718'], map_sub + 0x71c, context)] == [bound.map_id] * 3,
                 'ATTACK_OBSERVE_CURRENT_MAP_CHANGED')
            actors = reads.vector(actor_sub, 0x8a8, 512)
            players = [obj for obj in actors if reads.pointer(obj) == base + tables['MyPlayer']['rva']]
            need(len(players) == 1, 'ATTACK_OBSERVE_UNIQUE_MYPLAYER_REQUIRED')
            actor, = players
            reads.table(actor, tables['MyPlayer'])
            need(reads.number(actor + 0x18, '<Q') == bound.attacker.uid, 'ATTACK_OBSERVE_SELECTED_UID_CHANGED')
            # First UID match follows the existing source lookup, never skip an
            # unsupported actor in favour of a later convenient Monster.
            target = None
            for obj in actors:
                vp = reads.pointer(obj)
                need(base <= vp <= base + sampler.g['size'] - 16, 'ATTACK_OBSERVE_GETTER_BOUND')
                need(struct.unpack('<Q', reads.read(vp + 8, 8, True))[0] == base + common['ID_getter_RVA'],
                     'ATTACK_OBSERVE_UID_GETTER_UNSUPPORTED')
                if reads.number(obj + common['Actor_ID_u64_offset'], '<Q') == bound.target_uid:
                    target = obj
                    break
            need(target is not None, 'ATTACK_OBSERVE_TARGET_NOT_REGISTERED')
            need(reads.pointer(target) == base + monster['rva']
                 and reads.pointer(target + common['Actor_self_pointer_offset']) == target,
                 'ATTACK_OBSERVE_TARGET_TYPE_CHANGED')
            reads.normalized_table(target, monster)
            reads.rtti(monster)
            for anchor in monster['RTTI_graph_anchors']:
                need(hashlib.sha256(reads.read(base + anchor['rva'], anchor['length'], True)).hexdigest() == anchor['sha256'],
                     'ATTACK_OBSERVE_TARGET_HIERARCHY_CHANGED')

            def action_info(ptr, component):
                if not ptr:
                    return dict(status='OBSERVED', present=False, kind='none')
                vp = reads.pointer(ptr)
                row = next((r for r in (action_type, damage_type) if vp == base + r['rva']), None)
                if row is None:
                    return dict(status='UNKNOWN', present=True, kind='unknown', reason='ACTION_TYPE_NOT_PINNED')
                reads.table(ptr, row); reads.rtti(row)
                need(reads.pointer(ptr + 8) == component, 'ATTACK_OBSERVE_ACTION_OWNER_CHANGED')
                out = dict(status='OBSERVED', present=True, kind=row['kind'],
                    direction_i32=reads.number(ptr + 0x18, '<i'), token_u32=reads.number(ptr + 0x20, '<I'),
                    finished=reads.number(ptr + 0x24, '<B') != 0)
                if row['kind'] == 'AttackAction':
                    stored_attacker, stored_target, raw_effect = struct.unpack('<QQi', reads.read(ptr + 0x80, 20))
                    out.update(stored_attacker_uid=stored_attacker, target_uid=stored_target,
                        raw_effect_i32=raw_effect,
                        selected_pair_matches=stored_attacker == bound.attacker.uid and stored_target == bound.target_uid)
                return out

            def component_actions(owner):
                components = reads.vector(owner, 0x20, 128)
                candidates = [obj for obj in components if reads.pointer(obj) == base + tables['ActionComponent']['rva']]
                need(len(candidates) == 1, 'ATTACK_OBSERVE_UNIQUE_ACTION_COMPONENT_REQUIRED')
                obj, = candidates
                reads.table(obj, tables['ActionComponent'])
                need(reads.pointer(obj + 8) == owner, 'ATTACK_OBSERVE_COMPONENT_OWNER_CHANGED')
                current = action_info(reads.pointer(obj + 0xc0, True), obj)
                map_ptr, size, offset, count = struct.unpack('<QQQQ', reads.read(obj + 0xa0, 32))
                if count:
                    need(0 < size <= 4096 and size & (size - 1) == 0 and count <= size * 2,
                         'ATTACK_OBSERVE_QUEUE_BOUND')
                    reads.pointer_value(map_ptr)
                    block = reads.pointer(map_ptr + ((offset >> 1) & (size - 1)) * 8)
                    head = action_info(reads.pointer(block + (offset & 1) * 8, True), obj)
                else:
                    head = dict(status='OBSERVED', present=False, kind='none')
                return dict(current=current, queue_count=count, queue_head=head)

            attacker_actions, target_actions = component_actions(actor), component_actions(target)
            reads.verify()
            need(reads.physical(state + 0x360, 36) == raw, 'ATTACK_OBSERVE_SCENE_CHANGED')
            # route() may perform several reads; keep every byte inside this
            # same total and report the exact first refused read if exhausted.
            original_read = sampler.read
            def root_read(at, size, image=False):
                sampler.read = original_read
                try:
                    return reads.physical(at, size, image)
                finally:
                    sampler.read = root_read
            sampler.read = root_read
            try:
                need(sampler.route() == route, 'ATTACK_OBSERVE_ROOT_CHANGED')
            finally:
                sampler.read = original_read
            source_code()
            _source(); npc_observe._source(); move_state.attack_sources_ready()
            self.targets.revalidate(bound)
            need(reader.sampler is sampler, 'ATTACK_OBSERVE_SAMPLER_CHANGED')
            result.update(status='OBSERVED', reason=None, source_contract_valid=True,
                stable_double_read=True, actor_uid=bound.attacker.uid, target_uid=bound.target_uid,
                map_id=bound.map_id, attacker=attacker_actions, target=target_actions)
        except Exception as error:
            result['reason'] = observe.reason(error)
        finally:
            result['typed_bytes_requested'] = max(0, sampler.total - started)
            result['combined_typed_bytes_requested'] = sampler.total
            if reads is not None:
                result.update(refused_read_bytes=reads.refused, shortfall_at_refused_read=reads.shortfall)
            sampler.bytes, sampler.read_limit = previous_bytes, previous_limit
        return result


# Stable entry points: a caller may schedule this leaf, never replace its
# reader with an instance callback that supplies an arbitrary DTO.
PREPARE_METHOD = AttackActionObserver.prepare
COLLECT_METHOD = AttackActionObserver.collect
