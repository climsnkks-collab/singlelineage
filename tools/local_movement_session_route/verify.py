"""Synthetic in-memory fixtures only. Writes bounded verification in this dir."""
import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
import route as r

HERE = Path(__file__).resolve().parent


def fixture_world(owner):
    return r.WorldEvidence(owner, object(), object(), 1, 'SoloKnight', 0,
                           r.START, r.CONTROL, 'a' * 64, 'b' * 64, True)


def fixture_wire(start=r.START, direction=0, *, mode='null', payload=None,
                 opcode=r.OPCODE):
    """Fixture-only encoding; no product encoder is added to route.py."""
    if payload is None:
        if direction < 0:
            direction += 1 << 64
        payload = (r.pb.encode_uint32(1, start)
                   + r.pb.encode_varint(2 << 3) + r.pb.encode_varint(direction))
    size = 10 + len(payload)
    total = size if mode == 'null' else ((size + 1) & ~3) + 2
    declared = total - 2 if mode == 'null' else total
    return struct.pack('<HIHH', declared, 7, opcode, len(payload)) + payload + bytes(total-size)


def frame(**kwargs):
    mode = kwargs.get('mode', 'null')
    return r.decode_one_wire(fixture_wire(**kwargs), cipher_pointer=mode)


def setup(*, mode='null', proof_update=None):
    owner = object()
    world = fixture_world(owner)
    holder = {'world': world, 'proof_calls': 0}
    owner_lock = threading.Lock()

    def current(actual):
        return holder['world'] if actual is owner else None

    def proof(w, edge):
        holder['proof_calls'] += 1
        result = r.DirectionalEvidence(w, edge, True, True, True, True,
                                       'c' * 64, 'd' * 64)
        return proof_update(result, holder) if proof_update else result

    route = r.OneSelfMoveRoute(owner, world, current_world=current,
                              verified_edge=proof, cipher_pointer=mode,
                              owner_serialization=owner_lock)
    return owner, world, holder, route


def main():
    checks = []

    def check(name, got, *, accepted=False, reason=None, count=0):
        assert got.accepted is accepted and got.accepted_count == count, (name, got)
        if reason:
            assert got.reason == reason, (name, got.reason)
        assert got.replies == () and got.stop_trial is True
        metadata = got.metadata()
        assert metadata['own_SC4E2C_count'] == metadata['reply_count'] == 0
        assert metadata['denial_or_correction_count'] == 0
        assert metadata['client_reconciliation_proven'] is False
        assert len(json.dumps(metadata)) < 1024
        assert set(type(v) for v in metadata.values()) <= {str, int, bool, type(None)}
        checks.append(name)

    for relative in r.PINS:
        r.checked_source(relative)
        checks.append('pin_' + relative)
    # Verify transitive source artifacts without invoking old static analyzers.
    pins = r.movement_contract['source_pins'] | r.action_contract['pins']
    for relative, expected in pins.items():
        assert hashlib.sha256((r.ROOT / relative).read_bytes()).hexdigest() == expected
    checks.append('transitive_movement_contract_source_pins')
    assert r.movement_contract['C2S']['fields']['1']['type'] == 'uint32'
    assert r.movement_contract['C2S']['fields']['2']['type'] == 'int32'
    assert all(v['required'] is True for v in r.movement_contract['C2S']['fields'].values())
    checks.append('required_uint32_int32_schema_no_UID')
    cp59 = json.loads(r.checked_source('work/local_native_login_world_dormant_runtime/world-read-stability.json'))
    assert len(cp59['samples']) == 5
    for sample in cp59['samples']:
        observation = sample['observation']
        assert observation['status'] == 'OBSERVED' and observation['my_player_uid'] == 1
        assert observation['grid_words'] == list(r.authority.unpack_grid(r.START))
        assert observation['map_requested_i32'] == observation['map_resolved_i32'] == 0
        assert observation['tile_decode_ready'] == 'UNKNOWN'
    checks.append('CP59_historical_baseline_source_only_not_live_passability')

    for mode in ('null', 'present_disabled'):
        for direction, delta in enumerate(r.authority.DELTAS):
            owner, _, holder, route = setup(mode=mode)
            got = route.receive_frame(owner, frame(direction=direction, mode=mode))
            check(f'accepted_{mode}_direction{direction}', got, accepted=True,
                  reason='ACCEPTED_ONE_LOCAL_STEP', count=1)
            assert got.destination == r.authority.pack_grid(32571+delta[0],32951+delta[1])
            assert holder['proof_calls'] == 1
            again = route.receive_frame(owner, frame(direction=direction, mode=mode))
            check(f'duplicate_{mode}_direction{direction}', again,
                  reason='DUPLICATE_ACCEPTED_REQUEST', count=1)
            assert again.authoritative_packed == got.authoritative_packed
            assert holder['proof_calls'] == 1

    owner, _, _, route = setup()
    check('foreign_owner', route.receive_frame(object(), frame()), reason='FOREIGN_OWNER')
    check('foreign_refusal_stops_trial', route.receive_frame(owner, frame()), reason='ROUTE_STOPPED')
    owner, _, holder, route = setup()
    check('stale_start', route.receive_frame(owner, frame(start=r.START-1)), reason='STALE_START')
    assert holder['proof_calls'] == 0
    for direction in (-1, 8, 9):
        owner, _, holder, route = setup()
        check('direction_' + str(direction), route.receive_frame(owner, frame(direction=direction)),
              reason='DIRECTION_0_TO_7_REQUIRED')
        assert holder['proof_calls'] == 0

    invalid_payloads = [b'', b'\x08\x01', b'\x10\x00', b'\x08\x01\x10\x00\x10\x01',
                        b'\x08\x01\x10\x00\x18\x01', b'\x0a\x00\x10\x00', b'\x08\x80',
                        b'\x08' + r.pb.encode_varint(1<<32) + b'\x10\x00',
                        b'\x08\x01\x10' + r.pb.encode_varint(1<<32)]
    for i, payload in enumerate(invalid_payloads):
        owner, _, _, route = setup()
        check(f'malformed_schema_{i}', route.receive_frame(owner, frame(payload=payload)),
              reason='MALFORMED_MOVE_PAYLOAD')

    variants = [
        ('missing_evidence', lambda proof, _: None, 'PASSABILITY_CALLBACK_FAILED'),
        ('naked_true', lambda proof, _: True, 'PASSABILITY_CALLBACK_FAILED'),
        ('tile_not_ready', lambda proof, _: replace(proof, tile_ready=False), 'PASSABILITY_CALLBACK_FAILED'),
        ('unverified', lambda proof, _: replace(proof, independently_verified=False), 'PASSABILITY_CALLBACK_FAILED'),
        ('missing_proof_digest', lambda proof, _: replace(proof,evidence_sha256=''), 'PASSABILITY_CALLBACK_FAILED'),
        ('missing_verifier_pin', lambda proof, _: replace(proof,verifier_source_sha256=''), 'PASSABILITY_CALLBACK_FAILED'),
        ('CP62_tile_only_full_unknown', lambda proof, _: replace(proof,full_navigation_passable=None), 'DESTINATION_PASSABILITY_UNKNOWN'),
        ('tile_unknown', lambda proof, _: replace(proof,tile_passable=None), 'DESTINATION_PASSABILITY_UNKNOWN'),
        ('tile_blocked', lambda proof, _: replace(proof,tile_passable=False), 'DESTINATION_BLOCKED'),
        ('full_navigation_blocked', lambda proof, _: replace(proof,full_navigation_passable=False), 'DESTINATION_BLOCKED'),
        ('copied_world_sample', lambda proof, _: replace(proof,world=replace(proof.world)), 'PASSABILITY_CALLBACK_FAILED'),
        ('foreign_world_owner', lambda proof, _: replace(proof,world=fixture_world(object())), 'PASSABILITY_CALLBACK_FAILED'),
        ('foreign_edge_uid', lambda proof, _: replace(proof,edge=replace(proof.edge,uid=2)), 'PASSABILITY_CALLBACK_FAILED'),
        ('boolean_edge_uid', lambda proof, _: replace(proof,edge=replace(proof.edge,uid=True)), 'PASSABILITY_CALLBACK_FAILED'),
        ('stale_edge_start', lambda proof, _: replace(proof,edge=replace(proof.edge,start_packed=r.START-1)), 'PASSABILITY_CALLBACK_FAILED'),
        ('different_edge_direction', lambda proof, _: replace(proof,edge=replace(proof.edge,direction=2)), 'PASSABILITY_CALLBACK_FAILED'),
    ]
    for name, update, reason in variants:
        owner, _, _, route = setup(proof_update=update)
        got = route.receive_frame(owner, frame())
        check(name, got, reason=reason)
        assert got.authoritative_packed == r.START

    owner, world, holder, route = setup()
    holder['world'] = replace(world)
    check('copied_current_world', route.receive_frame(owner, frame()), reason='CURRENT_SAME_WORLD_SAMPLE_REQUIRED')
    owner, _, holder, route = setup()
    holder['world'] = None
    check('expired_current_world', route.receive_frame(owner, frame()), reason='CURRENT_SAME_WORLD_SAMPLE_REQUIRED')

    def revoke_during_proof(proof, holder):
        holder['world'] = None
        return proof
    owner, _, _, route = setup(proof_update=revoke_during_proof)
    check('revoked_before_commit', route.receive_frame(owner, frame()), reason='CURRENT_SAME_WORLD_SAMPLE_REQUIRED')

    owner, _, _, route = setup()
    first = route.receive_frame(owner, frame())
    check('second_distinct_request', route.receive_frame(owner, frame(direction=2)),
          reason='ONE_STEP_BUDGET_EXHAUSTED', count=1)
    assert route.state_metadata()['authoritative_packed'] == first.destination

    owner, _, holder, route = setup()
    barrier = threading.Barrier(2)
    def concurrent_call():
        barrier.wait(timeout=3)
        return route.receive_frame(owner, frame())
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(concurrent_call) for _ in range(2)]
        results = [f.result(timeout=5) for f in futures]
    assert sum(x.accepted for x in results) == 1
    assert set(x.reason for x in results) == {'ACCEPTED_ONE_LOCAL_STEP','DUPLICATE_ACCEPTED_REQUEST'}
    assert route.state_metadata()['accepted_count'] == 1 and holder['proof_calls'] == 1
    checks.append('two_concurrent_requests_one_atomic_acceptance')

    for mode in ('null', 'present_disabled'):
        wire = fixture_wire(mode=mode)
        decoder = r.codecs.ClientPlaintextDecoder(cipher_pointer=mode,max_frame=32,max_buffer=64)
        assert decoder.feed(wire[:3]) == ()
        frames = decoder.feed(wire[3:])
        assert len(frames) == 1 and r.parse_payload(frames[0].payload) == (r.START,0)
        decoder.finish()
        checks.append('split_C2S_' + mode)
        for i, bad in enumerate((wire[:-1],wire+wire,struct.pack('<H',33)+wire[2:])):
            try:
                r.decode_one_wire(bad,cipher_pointer=mode)
            except ValueError:
                checks.append(f'single_frame_limit_{mode}_{i}')
            else:
                raise AssertionError('MALFORMED_FRAMING_ACCEPTED')
    try:
        r.decode_one_wire(fixture_wire(),cipher_pointer='enabled')
    except ValueError:
        checks.append('enabled_cipher_mode_refused')
    else:
        raise AssertionError('ENABLED_CIPHER_ASSUMED_PLAINTEXT')

    owner, _, _, route = setup()
    check('wrong_opcode',route.receive_frame(owner,frame(opcode=0x4e2c)),reason='SOURCE_DECODED_MOVE_FRAME_REQUIRED')
    for name, kwargs in [('wrong_wire_length',{'wire_length':1}),('bad_trailer',{'trailer_length':9}),('sequence_not_uint32',{'sequence':True})]:
        owner, _, _, route = setup()
        check(name,route.receive_frame(owner,replace(frame(),**kwargs)),reason='SOURCE_DECODED_MOVE_FRAME_REQUIRED')

    owner = object()
    world = fixture_world(owner)
    for i, bad in enumerate((replace(world,selected_uid=True),replace(world,selected_uid=2),
                             replace(world,selected_name='Other'),replace(world,map_id=1),
                             replace(world,start_packed=r.START-1),replace(world,verified_selected_actor_world=False),
                             replace(world,session_token='copied-session-id'),
                             replace(world,sample_token='copied-sample-id'),
                             replace(world,sample_token=world.session_token))):
        try:
            r.OneSelfMoveRoute(owner,bad,current_world=lambda _:bad,verified_edge=lambda *_:None,
                               cipher_pointer='null',owner_serialization=threading.Lock())
        except ValueError:
            checks.append('bad_initial_world_' + str(i))
        else:
            raise AssertionError('UNVERIFIED_INITIAL_WORLD')

    tree = ast.parse((HERE/'route.py').read_text(encoding='utf-8'))
    assert not any(isinstance(n,ast.Import) and any(a.name in ('socket','ctypes','subprocess') for a in n.names) for n in ast.walk(tree))
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('write','send','sendall','encode_uint32','encode_varint') for n in ast.walk(tree))
    checks.append('no_socket_process_UAC_packet_emit_or_product_encoder')
    contract = json.loads((HERE/'integration-contract.json').read_text(encoding='utf-8'))
    assert contract['receive']['opcode'] == r.OPCODE
    assert contract['selected_initial_policy']['grid'] == list(r.authority.unpack_grid(r.START))
    assert contract['external_verification_requirements']['CP62_tile_only_JSON_authorizes_move'] is False
    assert contract['scope']['broker_route_registered'] is False
    checks.append('integration_metadata_live_gate_matches_route')
    output = {
        'schema':'lc-one-self-move-route-verification-v1','status':'PASS',
        'fixture_count':len(checks),'checks':checks,
        'pins':r.PINS,
        'owned_sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                         (HERE/'route.py',HERE/'verify.py',HERE/'README.md',HERE/'integration-contract.json')},
        'live_integration_status':'BLOCKED_EXTERNAL_VERIFIED_FULL_EDGE_AND_OWNER_SAMPLE_REQUIRED',
        'CP59_history_is_current_session_evidence':False,
        'CP62_tile_only_authorizes_move':False,
        'actual_game_process_slot_UAC_online_or_packet_emit_actions':0,
        'fixture_values':'synthetic assertions; acceptance proves route logic only',
    }
    (HERE/'verification.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','fixture_count':len(checks),'actual_actions':0,
                      'path':str(HERE/'verification.json')}))


if __name__ == '__main__':
    main()
