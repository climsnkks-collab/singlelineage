"""CP56 read-only Map request/resolution/header and environment stabilization."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import watch

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'work/online_public_session-v4/source-contract.json'
PUBLIC_SHA = '5150ac7b24a0497210615876fb6d1560b21ed5e809809434999bbf26f6a2d222'
READ_LIMIT = 8192
OLD = ROOT / 'tools/local_native_scene_current/inspect_land.py'
OLD_SHA = '2ed3e2c3caaf3508dbf50f356783710dac638c9a275d858cf45c2d007fea9273'
watch.need(watch.sha(OLD) == OLD_SHA, 'FROZEN_CP55_LAND_READER_REQUIRED')
MAP_SOURCE = ROOT / 'work/online_world_packet_source/converters.json'
MAP_SOURCE_SHA = '4416a87bed2e260fd08a63167665a04eefc6b2984b7a1c66c73c5709b3282313'


def empty_result(reason='LAND_NOT_INSPECTED'):
    return {'schema': 'lc-owned-land-map-public-presence-v1', 'status': 'UNKNOWN',
            'reason': reason, 'scene': 'unknown', 'pending': 'unknown',
            'actor_subsystem_count': None, 'map_subsystem_count': None,
            'my_player_count': None, 'actor_count': None,
            'map_context_present': None, 'map_field718': None,
            'map_field71c': None, 'map_context_header_u32': None,
            'world_environment_count': None, 'environment_field88_bool': None,
            'environment_field38_bool': None,
            'source_contract_sha256': PUBLIC_SHA, 'typed_bytes_requested': 0,
            'snapshot_atomic': False, 'raw_pointers_saved': False,
            'memory_write_or_game_control': False, 'visible_ui_proven': False,
            'actual_gameplay_proven': False, 'map_id_semantics_proven': False}


def public_contract():
    raw = PUBLIC.read_bytes()
    watch.need(hashlib.sha256(raw).hexdigest() == PUBLIC_SHA,
               'FIXED_PUBLIC_WORLD_CONTRACT_REQUIRED')
    return json.loads(raw)


def table(sampler, row):
    base, size = sampler.g['base'], sampler.g['size']
    raw = sampler.read(base + row['rva'], row['prefix_bytes'], image=True)
    values = struct.unpack('<' + 'Q' * (len(raw) // 8), raw)
    watch.need(all(base <= value < base + size for value in values),
               'PUBLIC_LAND_VTABLE_BOUNDS_REQUIRED')
    normalized = struct.pack('<' + 'Q' * len(values), *(v - base for v in values))
    watch.need(hashlib.sha256(normalized).hexdigest() == row['normalized_sha256'],
               'PUBLIC_LAND_VTABLE_SOURCE_CHANGED')


def inspect_attached(native, sampler):
    """Use the caller's retained handle; never reopen a process by PID here."""
    result = empty_result()
    sampler.bytes = 0
    sampler.read_limit = READ_LIMIT
    try:
        public = public_contract()
        watch.need(watch.sha(MAP_SOURCE) == MAP_SOURCE_SHA, 'SOURCE_BOUND_MAP_REQUEST_FIELD_REQUIRED')
        watch.need(sampler.b is native and sampler.c is native.contract,
                   'EXACT_RETAINED_LAND_READER_REQUIRED')
        native.validate()
        route = sampler.route()
        state = sampler.unique(route[-1], 'GameState')
        scene, scene_raw = sampler.scene(state)
        watch.need(scene['current']['kind'] == 'Land', 'LAND_SCENE_REQUIRED')
        base = sampler.g['base']
        actor_type = public['Player']['ActorSubsystem']
        map_type = public['Map']['table']
        actors = [sampler.strong_pair(pair)[0] for pair, vft in route[-2]
                  if vft == base + actor_type['rva']]
        maps = [sampler.strong_pair(pair)[0] for pair, vft in route[-2]
                if vft == base + map_type['rva']]
        result.update(scene='Land', pending=scene['pending']['kind'],
                      actor_subsystem_count=len(actors), map_subsystem_count=len(maps))
        actor_snapshot = None
        map_snapshot = None
        environment_snapshot = None
        environment_type = public['WorldEnvironment']['owner']
        environments = [sampler.strong_pair(pair)[0] for pair, vft in route[-2]
                        if vft == base + environment_type['rva']]
        result['world_environment_count'] = len(environments)
        if len(environments) == 1:
            environment = environments[0]
            table(sampler, environment_type)
            flag88 = sampler.read(environment + 0x88, 1)
            flag38 = sampler.read(environment + 0x38, 1)
            watch.need(flag88 in (b'\0', b'\1') and flag38 in (b'\0', b'\1'),
                       'CANONICAL_ENVIRONMENT_BOOL_REQUIRED')
            result.update(environment_field88_bool=bool(flag88[0]),
                          environment_field38_bool=bool(flag38[0]))
            environment_snapshot = (environment, flag88, flag38)
        if len(maps) == 1:
            map_sub = maps[0]
            table(sampler, map_type)
            context = sampler.pointer(map_sub + public['Map']['context_pointer'], nullable=True)
            field_raw = sampler.read(map_sub + public['Map']['field718'], 4)
            requested_raw = sampler.read(map_sub + 0x71c, 4)
            header_raw = sampler.read(context + public['Map']['context_header'], 4) if context else None
            result.update(map_context_present=bool(context),
                          map_field718=struct.unpack('<i', field_raw)[0],
                          map_field71c=struct.unpack('<i', requested_raw)[0],
                          map_context_header_u32=struct.unpack('<I', header_raw)[0] if header_raw else None)
            map_snapshot = (map_sub, context, field_raw, requested_raw, header_raw)
        if len(actors) == 1:
            actor = actors[0]
            table(sampler, actor_type)
            player = public['Player']
            header = sampler.read(actor + player['vector_begin'], 16)
            begin, end = struct.unpack('<QQ', header)
            stride = player['stride']
            watch.need(stride == 16 and player['vector_end'] == player['vector_begin'] + 8
                       and (begin == end == 0 or 0x10000 <= begin <= end <= 0x7fffffffffff
                            and (begin | end) % 8 == 0 and (end - begin) % stride == 0
                            and (end - begin) // stride <= player['max_actor_elements']),
                       'BOUNDED_ACTOR_VECTOR_REQUIRED')
            entries = []
            my_player = 0
            for at in range(begin, end, stride):
                pair = sampler.read(at, stride)
                obj, _ = sampler.strong_pair(pair)
                vft = sampler.pointer(obj)
                entries.append((at, pair, obj, vft))
                if vft == base + player['MyPlayer']['rva']:
                    table(sampler, player['MyPlayer'])
                    my_player += 1
            result.update(my_player_count=my_player, actor_count=(end - begin) // stride)
            actor_snapshot = (actor, header, entries)
        if actor_snapshot:
            actor, header, entries = actor_snapshot
            watch.need(sampler.pointer(actor) == base + actor_type['rva']
                       and sampler.read(actor + public['Player']['vector_begin'], 16) == header,
                       'ACTOR_VECTOR_CHANGED_AFTER_READ')
            for at, pair, obj, vft in entries:
                watch.need(sampler.read(at, 16) == pair and sampler.pointer(obj) == vft,
                           'ACTOR_OWNER_CHANGED_AFTER_READ')
                sampler.strong_pair(pair)
        if map_snapshot:
            map_sub, context, field_raw, requested_raw, header_raw = map_snapshot
            watch.need(sampler.pointer(map_sub) == base + map_type['rva']
                       and sampler.pointer(map_sub + public['Map']['context_pointer'], nullable=True) == context
                       and sampler.read(map_sub + public['Map']['field718'], 4) == field_raw,
                       'MAP_CONTEXT_CHANGED_AFTER_READ')
            watch.need(sampler.read(map_sub + 0x71c, 4) == requested_raw
                       and (not context or sampler.read(context + public['Map']['context_header'], 4) == header_raw),
                       'MAP_REQUEST_OR_HEADER_CHANGED_AFTER_READ')
        if environment_snapshot:
            environment, flag88, flag38 = environment_snapshot
            watch.need(sampler.pointer(environment) == base + environment_type['rva']
                       and sampler.read(environment + 0x88, 1) == flag88
                       and sampler.read(environment + 0x38, 1) == flag38,
                       'ENVIRONMENT_OWNER_OR_FLAGS_CHANGED_AFTER_READ')
        watch.need(sampler.read(state + 0x360, 36) == scene_raw, 'LAND_SCENE_CHANGED_AFTER_READ')
        watch.need(sampler.route() == route, 'LAND_ROOT_OWNER_CHANGED_AFTER_READ')
        native.validate()
        result.update(status='OBSERVED' if len(actors) == len(maps) == 1 else 'OBSERVED_PARTIAL',
                      reason=None if len(actors) == len(maps) == 1 else 'SUBSYSTEM_ABSENT_OR_DUPLICATE')
    except Exception as error:
        # A torn read must not turn unknown presence into false or a zero count.
        result = empty_result(getattr(error, 'reason', str(error)
                              if isinstance(error, ValueError) else type(error).__name__))
    result['typed_bytes_requested'] = sampler.bytes
    return result


def inspect(candidate: Path, digest: str, pid: int, birth: str):
    native = None
    try:
        watch.need(type(pid) is int and pid > 0 and type(birth) is str and birth.isdecimal(),
                   'EXACT_OWNED_IDENTITY_REQUIRED')
        public_contract()
        contract = watch.contract_for(candidate, digest)
        native_mod = watch.load(watch.NATIVE, '_land_public_native')
        sampler_mod = watch.load(watch.SAMPLER, '_land_public_sampler')
        native = native_mod.Native(contract, {'pid': pid, 'birth': birth})
        attached = native.attach()
        watch.need(attached['birth'] == birth, 'PID_BIRTH_CHANGED')
        sampler = sampler_mod.Sampler(native, contract, native.modules()['LC'])
        return inspect_attached(native, sampler)
    except Exception as error:
        return empty_result(getattr(error, 'reason', str(error)
                            if isinstance(error, ValueError) else type(error).__name__))
    finally:
        if native is not None:
            native.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--sha', required=True)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--birth', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    watch.need(not a.output.exists(), 'CREATE_NEW_LAND_RESULT_REQUIRED')
    row = inspect(a.candidate.resolve(), a.sha, a.pid, a.birth)
    row.update(candidate_sha256=a.sha, identity={'pid': a.pid, 'birth': a.birth})
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as stream:
        json.dump(row, stream, indent=2)
        stream.write('\n')
    print(json.dumps(row))


if __name__ == '__main__':
    main()
