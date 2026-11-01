"""One explicit local Map0 baseline after the owned stored selection ACK."""
import ast
import hashlib
import importlib.util
import json
import struct
import sys
import types
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
ACK_SOURCE = ROOT / 'tools/local_native_login_local_ack_hook/ack_enter_world.py'
ACK_SHA = '2da189d4669c9b3c827b1ed579390a9312da6cef12e03f1349c23076e5d52ac4'
WORLD_PATH = ROOT / 'tools/local_world_protocol/model.py'
WORLD_SHA = '2d1ebdec0c3fc7830702691d045d89c6dacfdbf706cbf5eb9670be20e3cd5f07'
BINDING = SELF.with_name('baseline.json')
BINDING_SHA = 'f44a4f3895f961f396fe7816b5940860e641978f5d4a53061e9f4866fe8f53f9'
MAP_OPCODE = 0x4e95


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def load(path, digest, name):
    # Python source hash pin removed (source pins reduced); digest kept for reference.
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ack = load(ACK_SOURCE, ACK_SHA, '_cp56_frozen_enter_ack')
world = load(WORLD_PATH, WORLD_SHA, '_cp56_world_payload')
REALM_SHA = ack.REALM_SHA


def baseline():
    need(sha(BINDING) == BINDING_SHA, 'EXACT_EXPLICIT_LOCAL_MAP_BINDING_REQUIRED')
    row = json.loads(BINDING.read_bytes())
    need(row['schema'] == 'owned-local-map-baseline-v1'
         and row['status'] == 'EXPLICIT_LOCAL_SOURCE_BASELINE' and row['realm'] == 'owned-local'
         and row['fields'] == {'1': 0, '2': 0, '3': False, '4': False}
         and row['field_provenance'] == {'1': 'local_game_configuration', '2': 'source_literal',
                                        '3': 'source_literal', '4': 'source_literal'}
         and row['normal_server_values_proven'] is False and row['field2_game_label'] == 'UNKNOWN'
         and row['world_ready_claim'] is False and row['tileload_claim'] is False
         and row['online_identifiers_used'] is False, 'EXPLICIT_LOCAL_BASELINE_ONLY')
    for name, digest in row['evidence_pins'].items():
        need(sha(ROOT / name) == digest, 'LOCAL_MAP_SOURCE_EVIDENCE_CHANGED')
    values = {int(name): value for name, value in row['fields'].items()}
    provenance = {int(name): value for name, value in row['field_provenance'].items()}
    dto = world.encode_with_provenance(MAP_OPCODE, values, provenance)
    need(world.decode_payload(MAP_OPCODE, dto.payload) == values, 'MAP_BASELINE_PAYLOAD_ROUNDTRIP')
    return row, values, dto


def map_frame():
    row, values, dto = baseline()
    return struct.pack('<HH', len(dto.payload) + 6, MAP_OPCODE) + dto.payload + b'\0\0'


def validate_map_frame(wire):
    row, values, dto = baseline()
    need(type(wire) is bytes and 6 <= len(wire) <= 70
         and int.from_bytes(wire[:2], 'little') == len(wire)
         and int.from_bytes(wire[2:4], 'little') == MAP_OPCODE and wire[-2:] == b'\0\0'
         and wire == map_frame(), 'EXACT_LOCAL_MAP_FRAME_REQUIRED')
    need(world.decode_payload(MAP_OPCODE, wire[4:-2]) == values, 'EXACT_LOCAL_MAP_PAYLOAD_REQUIRED')
    return dto.metadata()


def successor_tree():
    need(sha(ACK_SOURCE) == ACK_SHA, 'FROZEN_LOCAL_ENTER_ACK_HOOK')
    tree = ast.parse(ACK_SOURCE.read_bytes(), str(ACK_SOURCE))
    wrap = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'wrap')
    counts = {'select': 0, 'transport': 0, 'paths': 0, 'review': 0, 'pins': 0}
    for node in ast.walk(wrap):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'select':
            ret = node.body[-1]
            need(isinstance(ret, ast.Return) and ast.unparse(ret.value) == '(ENTER_ACK_FRAME,)',
                 'EXACT_AFTER_OWN_STORED_SELECTION_ACK')
            node.body.insert(0, ast.parse("nonlocal map_notify_sent").body[0])
            node.body.insert(1, ast.parse("need(not map_notify_sent,'MAP_NOTIFY_REPLAY_REFUSED')").body[0])
            node.body[-1:] = ast.parse('map_notify_sent=True\nreturn (ENTER_ACK_FRAME,MAP_FRAME)').body
            counts['select'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'register_own':
            index = next(index for index, entry in enumerate(node.body)
                         if isinstance(entry, ast.Assign) and ast.unparse(entry) == 'prior_select = game.routes[20008]')
            node.body.insert(index, ast.parse('map_notify_sent=False').body[0])
        if isinstance(node, ast.FunctionDef) and node.name == 'transport':
            index = next(index for index, entry in enumerate(node.body)
                         if isinstance(entry, ast.For))
            # Extend the frozen connection compiler only at its game_reply
            # validation branch; the same writer/owner/drain loop is retained.
            patch = ast.parse("""for branch in ast.walk(tree):
 if isinstance(branch,ast.If) and isinstance(branch.test,ast.Name) and branch.test.id=='game_reply':
  original_branch=branch.body[:2]
  branch.body[:2]=ast.parse('if opcode==0x4e95:\\n validate_map_frame(wire)\\nelse:\\n pass').body
  branch.body[0].orelse=original_branch
""").body[0]
            patch.body[0].body[2:2]=ast.parse("branch.body[0].body.append(ast.parse(\"session.need(sent<132,'OWN_ROSTER_REPLY_BOUND')\").body[0])").body
            node.body.insert(index+1, patch)
            module_index = next(index for index, entry in enumerate(node.body)
                                if isinstance(entry, ast.Assign) and ast.unparse(entry.targets[0]) == 'module')
            node.body.insert(module_index + 1, ast.parse('module.validate_map_frame=validate_map_frame').body[0])
            counts['transport'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'input_paths':
            node.body = ast.parse('return list(dict.fromkeys([*base.input_paths(),REALM_PATH,ACK_SOURCE,SELF,WORLD_PATH,BINDING,*EVIDENCE_PATHS]))').body
            counts['paths'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'expected_review':
            node.body.insert(-1, ast.parse("row.update(schema='native-own-local-map-baseline-review-v1',map_notify_opcode=0x4e95,map_binding_status='EXPLICIT_LOCAL_SOURCE_BASELINE',map_field_provenance=BASELINE['field_provenance'],map_field_evidence=BASELINE['field_evidence'],map_normal_server_values_proven=False,map_field2_game_label='UNKNOWN',map_world_ready_claim=False,map_tileload_claim=False,map_reply_sequence='same_owned_writer_ACK_drain_then_one_MAP',map_frame_size=len(MAP_FRAME))").body[0])
            counts['review'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'pin_context':
            locked=next(entry for entry in node.body if isinstance(entry,ast.With))
            locked.body.insert(-1, ast.parse("for path in (ACK_SOURCE,WORLD_PATH,BINDING,*EVIDENCE_PATHS):\n held=backing.b.a.add(path)\n backing.pinned_hashes[path]=held.digest()").body[0])
            counts['pins'] += 1
    need(counts == {'select': 1, 'transport': 1, 'paths': 1, 'review': 1, 'pins': 1},
         'EXACT_ONE_MAP_SUCCESSOR_SCOPE')
    return ast.fix_missing_locations(ast.Module(body=[wrap], type_ignores=[]))


def wrap(base):
    row, _, _ = baseline()
    namespace = dict(vars(ack), SELF=SELF, ACK_SOURCE=ACK_SOURCE, WORLD_PATH=WORLD_PATH,
                     BINDING=BINDING, BASELINE=row, MAP_FRAME=map_frame(),
                     EVIDENCE_PATHS=tuple(ROOT / name for name in row['evidence_pins']),
                     validate_map_frame=validate_map_frame)
    exec(compile(successor_tree(), str(SELF), 'exec'), namespace)
    return namespace['wrap'](base)


def plan():
    row, _, dto = baseline()
    return {'status': row['status'], 'opcode': MAP_OPCODE, 'frame_length': len(map_frame()),
            'field_numbers': [1, 2, 3, 4], 'field_provenance': row['field_provenance'],
            'normal_server_values_proven': False, 'field2_game_label': 'UNKNOWN',
            'world_ready_claim': False, 'tileload_claim': False, 'game_slot_actions': 0}
