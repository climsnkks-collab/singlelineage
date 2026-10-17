"""Pure owned-session/transport fixtures; no socket, game, slot, or store writes."""
import ast
import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load():
    spec = importlib.util.spec_from_file_location('_map_baseline_fixture_hook', HERE / 'spawn_hook.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_checks():
    hook = load()
    cp56 = hook.load(hook.MAP_SOURCE,'_fixture_cp56')
    hook.map_frame=cp56.map_frame;hook.validate_map_frame=cp56.validate_map_frame;hook.world=cp56.world;hook.ack=cp56.ack
    profile,fields,self_dto,actor_dto=hook.profiles()
    frozen=(profile,fields,self_dto,actor_dto)
    hook.profiles=lambda:frozen
    self_wire,actor_wire=hook.frames()
    hook.validate_world_frame(self_wire);hook.validate_world_frame(actor_wire)
    assert actor_dto.metadata()['SelfInfo_profile_policy_checked'] is True
    checks = []
    wire = hook.map_frame()
    hook.need(len(wire) == 14 and hook.validate_map_frame(wire)['fields'] == [1, 2, 3, 4], 'MAP_FRAME14')
    hook.need(hook.world.decode_payload(0x4e95, wire[4:-2]) == {1: 0, 2: 0, 3: False, 4: False}, 'MAP_BASELINE_DECODE')
    checks.append('opcode_4E95_length14_explicit_fields_and_four_provenance_categories')
    for bad in (wire[:2] + b'\x96\x4e' + wire[4:], wire[:-2] + b'\1\0', wire[:4] + wire[4:-2] + b'\x28\0\0\0'):
        try:
            hook.validate_map_frame(bad)
            raise AssertionError('UNDECLARED_MAP_REPLY_ACCEPTED')
        except ValueError:
            pass
    checks.append('wrong_opcode_trailer_or_additional_fields_refused')
    tree = hook.successor_tree(cp56)
    compile(tree, str(HERE / 'spawn_hook.py'), 'exec')
    checks.append('exact_source_select_transport_review_and_pin_successor_compiles')
    selects = [node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'select']
    hook.need(len(selects) == 1, 'ONE_SELECTION_HOOK')
    select = selects[0]
    stores = []
    writer = object()
    game = types.SimpleNamespace(list_sent=True, selection=None)
    registry = types.SimpleNamespace(resolve=lambda candidate: game if candidate is writer else None)
    owner = types.SimpleNamespace(registry=registry, owners={id(writer): (writer, 1)})
    async def prior_select(payload):
        hook.need(payload == b'owned-selection', 'EXACT_SELECTION_REQUEST')
        game.selection = types.SimpleNamespace(reference='SoloKnight')
        return ()
    store = types.SimpleNamespace(select=lambda name: (stores.append(name) or 1,()))
    factory = ast.parse('def factory(self,writer,game,store,prior_select):\n map_notify_sent=False\n return None').body[0]
    factory.body[-1:] = [select, ast.Return(value=ast.Name(id='select', ctx=ast.Load()))]
    namespace = {'need': hook.need, 'ENTER_ACK_FRAME': hook.ack.ENTER_ACK_FRAME, 'MAP_FRAME': wire,'SELF_FRAME':self_wire,'ACTOR_FRAME':actor_wire,'validate_selected':hook.validate_selected}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])), 'pure_map_select_fixture', 'exec'), namespace)
    receive = namespace['factory'](owner, writer, game, store, prior_select)
    replies = asyncio.run(receive(b'owned-selection'))
    hook.need(replies == (hook.ack.ENTER_ACK_FRAME,wire,self_wire,actor_wire) and stores == ['SoloKnight'], 'OWNED_STORED_ACK_THEN_MAP')
    checks.append('owned_reference_stored_then_ACK_and_one_MAP_reply_same_session')
    try:
        asyncio.run(receive(b'owned-selection'))
        raise AssertionError('MAP_REPLAY_ACCEPTED')
    except ValueError:
        pass
    checks.append('selection_and_MAP_replay_refused')
    game.selection = None
    owner.owners[id(writer)] = (object(), 1)
    receive = namespace['factory'](owner, writer, game, store, prior_select)
    try:
        asyncio.run(receive(b'owned-selection'))
        raise AssertionError('FOREIGN_WRITER_ACCEPTED')
    except ValueError:
        pass
    checks.append('foreign_writer_session_refused_before_selection')
    owner.owners[id(writer)] = (writer, 1)
    async def unknown_select(payload):
        raise ValueError('SELECT_NOT_OWNED_REFERENCE')
    receive = namespace['factory'](owner, writer, game, store, unknown_select)
    try:
        asyncio.run(receive(b'foreign-reference'))
        raise AssertionError('UNKNOWN_REFERENCE_ACCEPTED')
    except ValueError:
        pass
    checks.append('prior_selection_refusal_never_returns_ACK_or_MAP')
    class Receipt:
        pass
    base = types.SimpleNamespace(need=hook.need, namespace={}, ConsumptionExtension=type('Consumption', (), {}),
                                 parent=types.SimpleNamespace(ReceiptRegistry=Receipt, route=types.SimpleNamespace(LoginRegistry=Receipt)),
                                 input_paths=lambda: [], expected_review=lambda *args: {}, pin_context=lambda ctx: None,
                                 identity=lambda row: None)
    api = hook.wrap(base)
    transport = api.transport()
    checks.append('actual_derived_transport_compiles_with_only_exact_MAP_acceptance')
    send_source = next(node for node in ast.walk(ast.parse(hook.ack.CONNECTION.read_bytes()))
                       if isinstance(node, ast.AsyncFunctionDef) and node.name == 'send')
    hook.need(ast.unparse(send_source).index('await owner_required(opcode)')
              < ast.unparse(send_source).index('writer.write(wire)')
              < ast.unparse(send_source).index('await asyncio.wait_for(writer.drain(), 2)'), 'ORIGINAL_OWNER_WRITE_DRAIN_ORDER')
    checks.append('original_same_writer_per_frame_owner_gate_and_serial_write_drain_order_preserved')
    # Actual derived connection handler with injected transport objects only.
    async def stream(deny_frame=None):
        writes = []
        events = []
        class Writer:
            def write(self, raw):
                writes.append(int.from_bytes(raw[2:4], 'little'))
                events.append(('write', writes[-1]))
            async def drain(self):
                events.append(('drain', writes[-1] if writes else None))
            def close(self):
                pass
            async def wait_closed(self):
                pass
        literal = Writer()
        class Reader:
            def __init__(self):
                self.count = 0
            async def read(self, count):
                self.count += 1
                return b'request' if self.count == 1 else b''
        class Decoder:
            def feed(self, raw):
                return [types.SimpleNamespace(opcode=0x4e28, payload=b'owned-selection', wire_length=20)]
            def finish(self):
                pass
        async def received(frame):
            return (hook.ack.ENTER_ACK_FRAME,wire,self_wire,actor_wire)
        async def opened():
            return (b'KEY12fixture',)
        fake_game = types.SimpleNamespace(received=received)
        fake_registry = types.SimpleNamespace(_sessions={id(literal): fake_game}, resolve=lambda candidate: fake_game,
                                              close=lambda candidate: None)
        trace = types.SimpleNamespace(endpoints={14030: {}}, emit=lambda row: None)
        parent = types.SimpleNamespace(KEY12=b'KEY12fixture', Trace=types.SimpleNamespace(validate_timing=lambda row: row))
        owner_calls = 0
        async def allowed(peer):
            nonlocal owner_calls
            owner_calls += 1
            return not (deny_frame is not None and owner_calls == deny_frame)
        first = {'peer': {'connection_id': 1, 'accepted_monotonic_ns': 1}, 'write_started_monotonic_ns': 2}
        scope = types.SimpleNamespace(check=lambda: None)
        conversation = types.SimpleNamespace(ack_prepared=True, opened=opened)
        await transport.connection_handler(parent, fake_registry)(Reader(), literal, 14030, trace, Decoder,
            lambda emit: conversation, lambda: None, lambda raw: None, scope, first=first, owner_guard=allowed)
        return writes, events
    writes, events = asyncio.run(stream())
    hook.need(writes == [0x4e29,0x4e95,0x4e38,0x4e96]
              and events[:4] == [('drain', None), ('write', 0x4e29), ('drain', 0x4e29), ('write', 0x4e95)],
              'ACK_DRAIN_BEFORE_MAP_WRITE')
    checks.append('actual_fixture_ACK_drain_before_MAP_write_on_same_writer')
    writes, _ = asyncio.run(stream(3))
    hook.need(writes == [0x4e29], 'MAP_OWNER_REFUSAL_PREVENTS_WRITE')
    checks.append('MAP_frame_current_owner_refusal_prevents_MAP_write')
    for at,expected in ((4,[0x4e29,0x4e95]),(5,[0x4e29,0x4e95,0x4e38])):
        writes,_=asyncio.run(stream(at));assert writes==expected
        checks.append('current_owner_refused_before_world_frame_'+str(at))
    assert events==[('drain',None),('write',0x4e29),('drain',0x4e29),('write',0x4e95),('drain',0x4e95),('write',0x4e38),('drain',0x4e38),('write',0x4e96),('drain',0x4e96)]
    checks.append('actual_four_frame_same_writer_serial_owner_write_drain_order')
    bad=self_wire[:-2]+b'\1\0'
    try:hook.validate_world_frame(bad);raise AssertionError('undeclared world accepted')
    except ValueError:pass
    checks.append('source_integrated_complete_profiles_and_corrupt_world_frame_refusal')
    return checks


if __name__ == '__main__':
    rows = run_checks()
    print(json.dumps({'status': 'PASS_PURE_SELF_ACTOR_HOOK_FIXTURES', 'checks': rows,
                      'game_slot_socket_native_store_write_actions': 0}))
