"""Virtual clock/reader/capture fixtures, no process or desktop access."""
import importlib.util
import json
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'tools/local_native_login_self_actor_runtime/auto_enter_self_actor.py'


def run_checks():
    spec = importlib.util.spec_from_file_location('_cp57_probe_fixture', HELPER)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    compile(h.land_stability_tree(), str(h.LAND), 'exec')
    checks = ['exact_frozen_first_Land_boundary_compiles_context240_module35_preserved']
    class Native:
        def __init__(self):
            self.handle = object()
            self.expected = {'pid':123,'birth':'12345'}
            self.calls = 0
        def validate(self):
            self.calls += 1
    class Clock:
        def __init__(self):
            self.elapsed = 0
            self.sleeps = []
        def monotonic(self):
            return self.elapsed
        def sleep(self, seconds):
            self.elapsed += seconds
            self.sleeps.append(seconds)
    with tempfile.TemporaryDirectory(prefix='cp57-world-fixture-') as directory:
        d = Path(directory)
        metadata = d/'metadata.jsonl'
        sequence = [dict(event='reply_sent',opcode=op,connection_id=2) for op in h.SEQUENCE]
        def write(rows):
            metadata.write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
        write(sequence)
        assert h.emission(metadata)['status'] == 'EMITTED_METADATA'
        for bad in (sequence[:-1],sequence+sequence[-1:],list(reversed(sequence)),
                    sequence[:-1]+[dict(sequence[-1],connection_id=3)]):
            write(bad)
            assert h.emission(metadata)['status'] == 'UNKNOWN'
        checks.append('exact_one_complete_world_sequence_foreign_connection_duplicate_missing_order_refused')
        write(sequence)
        events = []
        def inspect(native,sampler):
            events.append('sample')
            return {'status':'OBSERVED','my_player_count':1,'actor_count':1,
                    'map_field718':0,'map_field71c':0,'map_context_header_u32':0,
                    'environment_field88_bool':False,'environment_field38_bool':False}
        probe = types.SimpleNamespace(inspect_attached=inspect,empty_result=lambda reason:{'status':'UNKNOWN','reason':reason})
        def capture(pid,birth,*,focus):
            assert focus is False
            events.append('capture')
            return {'status':'CAPTURED','image':'fixture-only.png','width':100,'height':100}
        def loader(path,name):
            if path == h.MAP_PROBE:
                return probe
            if path == h.VISIBLE:
                return types.SimpleNamespace(capture=capture)
            raise AssertionError('UNDECLARED_HELPER_LOAD')
        original_time = h.time
        clock = Clock()
        h.time = clock
        try:
            native = Native()
            h.observe_world(native,object(),lambda *a:{'status':'OBSERVED','current':'Land'},
                            metadata,d/'result.json',loader)
            row=json.loads((d/'self-actor-stability.json').read_bytes())
            screen=json.loads((d/'self-actor-screen-capture.json').read_bytes())
            assert len(row['samples']) == 5 and clock.sleeps == [1.0]*4
            assert events == ['sample']*5+['capture']
            assert all(r['observation']['my_player_count'] == 1 for r in row['samples'])
            assert row['tile_state'] == 'UNKNOWN' and row['world_ready_claim'] is False
            assert screen['focus_attempted'] is False and screen['visible_gameworld_verified'] is False
            checks.append('five_post_emit_same_handle_MyPlayer_Actor_Map_environment_samples_then_owned_crop_no_focus')
            try:
                h.observe_world(native,object(),lambda *a:{'status':'OBSERVED','current':'Land'},metadata,d/'result.json',loader)
                raise AssertionError('OVERWRITE_ACCEPTED')
            except ValueError:
                pass
            checks.append('exclusive_observation_and_screenshot_metadata_output_no_overwrite')
            missing=d/'missing';missing.mkdir()
            clock.sleeps=[]
            events.clear()
            h.observe_world(Native(),object(),lambda *a:{'status':'OBSERVED','current':'Land'},
                            d/'absent',missing/'result.json',loader)
            row=json.loads((missing/'self-actor-stability.json').read_bytes())
            assert len(clock.sleeps) == 24 and clock.sleeps[:20] == [0.1]*20
            assert all(r['observation']['status']=='UNKNOWN' for r in row['samples'])
            assert not events
            checks.append('bounded_missing_emit_wait_2seconds_all_unknown_no_capture_or_consumption_claim')
        finally:
            h.time = original_time
    return checks


if __name__ == '__main__':
    print(json.dumps({'status':'PASS_CP57_POST_EMIT_FIXTURES','checks':run_checks(),
                      'actual_process_game_slot_uac_screenshot_actions':0}))
