"""CP57 owned local ACK→Map→SelfInfo→Actor, source-bound explicit profiles."""
import ast
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
PINS_PATH = SELF.with_name('spawn-profile-pins.json')
PINS_SHA = 'daa164504916dda723a45f296a9d689eb9225656576d04140d9c4a8e572fa486'
MAP_SOURCE = ROOT / 'tools/local_native_login_map_notify_hook/hook.py'
SELF_SOURCE = ROOT / 'tools/local_self_info_profile/model.py'
ACTOR_SOURCE = SELF.with_name('actor_profile.py')


def __getattr__(name):
    if name in ('ACK_SHA','BINDING_SHA','WORLD_SHA','REALM_SHA','baseline'):
        return getattr(load(MAP_SOURCE, '_cp57_frozen_map_api'), name)
    raise AttributeError(name)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def pins():
    need(sha(PINS_PATH) == PINS_SHA, 'EXACT_CP57_DEPENDENCY_PIN_FILE')
    rows = json.loads(PINS_PATH.read_bytes())
    need(all(sha(ROOT / name) == digest for name, digest in rows.items()), 'CP57_PROFILE_SOURCE_CHANGED')
    return rows


def load(path, name):
    need(path.relative_to(ROOT).as_posix() in pins(), 'DECLARED_CP57_PROFILE_SOURCE_REQUIRED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def profiles():
    info = load(SELF_SOURCE, '_cp57_self_profile')
    actor = load(ACTOR_SOURCE, '_cp57_actor_profile')
    profile = info.build_profile()
    fields, provenance = actor.candidate()
    self_dto = info.encode_for_review(profile)
    actor_dto = actor.encode_for_review(fields, provenance, profile.fields)
    need(actor_dto.metadata()['SelfInfo_profile_policy_checked'] is True,
         'SOURCE_BOUND_SELF_INFO_ACTOR_INTEGRATION_REQUIRED')
    return profile, fields, self_dto, actor_dto


def frame(opcode, dto):
    return struct.pack('<HH', len(dto.payload) + 6, opcode) + dto.payload + b'\0\0'


def frames():
    profile, fields, self_dto, actor_dto = profiles()
    return frame(0x4e38, self_dto), frame(0x4e96, actor_dto)


def validate_world_frame(wire, expected=None):
    need(type(wire) is bytes and len(wire) >= 6, 'EXACT_LOCAL_WORLD_FRAME_REQUIRED')
    info, actor = frames() if expected is None else expected
    if wire == info:
        return profiles()[2].metadata()
    if wire == actor:
        return profiles()[3].metadata()
    raise ValueError('UNDECLARED_SELF_OR_ACTOR_FRAME_REFUSED')


def validate_selected(reference, selected):
    profile, actor, _, _ = profiles()
    need(type(selected) is tuple and len(selected) == 2 and selected[0] == profile.fields[1]
         and reference == actor[9] and type(selected[0]) is int,
         'EXACT_PROFILE_OWN_STORED_SELECTION_REQUIRED')


def successor_tree(map_hook):
    tree = map_hook.successor_tree()
    counts = dict(select=0, transport=0, paths=0, review=0, pins=0)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'select':
            need(ast.unparse(node.body[-1]) == 'return (ENTER_ACK_FRAME, MAP_FRAME)', 'EXACT_CP56_MAP_SEQUENCE')
            found = 0
            for index, entry in enumerate(node.body):
                if ast.unparse(entry) == 'store.select(game.selection.reference)':
                    node.body[index:index+1] = ast.parse('selected=store.select(game.selection.reference)\nvalidate_selected(game.selection.reference,selected)').body
                    found += 1
                    break
            need(found == 1, 'EXACT_STORED_SELECTION_VALIDATION_BOUNDARY')
            node.body[-1:] = ast.parse('return (ENTER_ACK_FRAME, MAP_FRAME, SELF_FRAME, ACTOR_FRAME)').body
            counts['select'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'transport':
            # This nested source string modifies only the frozen validator branch.
            # ACK/Map compilation and per-frame owner→write→drain stay unchanged.
            found = 0
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and type(child.value) is str and 'if opcode==0x4e95:' in child.value:
                    child.value = child.value.replace('else:\n pass', 'elif opcode in (0x4e38,0x4e96):\n validate_world_frame(wire)\n session.need(sent<132,\'OWN_ROSTER_REPLY_BOUND\')\nelse:\n pass')
                    found += 1
            need(found == 1, 'ONE_CP56_TRANSPORT_VALIDATION_EXTENSION')
            index = next(i for i, e in enumerate(node.body) if isinstance(e, ast.For))
            metadata_patch = ast.parse("""metadata_count=0
for entry in ast.walk(tree):
 if isinstance(entry,ast.Dict) and [ast.literal_eval(k) for k in entry.keys if isinstance(k,ast.Constant)]==['event','endpoint_port','opcode','frame_size'] and isinstance(entry.values[0],ast.Constant) and entry.values[0].value=='reply_sent' and isinstance(entry.values[2],ast.Name):
  entry.keys.append(ast.Constant(value='connection_id'))
  entry.values.append(ast.parse(\"first['peer']['connection_id']\",mode='eval').body)
  metadata_count+=1
need(metadata_count==1,'ONE_OWN_WORLD_REPLY_CONNECTION_METADATA')
""").body
            node.body[index+2:index+2] = metadata_patch
            # CP56 sets original_branch on the map If. Preserve it on final else.
            for child in ast.walk(node):
                if isinstance(child, ast.Assign) and ast.unparse(child.targets[0]) == 'branch.body[0].orelse':
                    child.targets[0] = ast.parse('branch.body[0].orelse[0].orelse', mode='eval').body
                    child.targets[0].ctx = ast.Store()
            index = next(i for i, e in enumerate(node.body) if isinstance(e, ast.Assign) and ast.unparse(e.targets[0]) == 'module.validate_map_frame')
            node.body.insert(index+1, ast.parse('module.validate_world_frame=validate_world_frame').body[0])
            counts['transport'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'input_paths':
            node.body = ast.parse('return list(dict.fromkeys([*base.input_paths(),REALM_PATH,ACK_SOURCE,MAP_SOURCE,SELF,WORLD_PATH,BINDING,*EVIDENCE_PATHS,PINS_PATH,*PROFILE_PATHS]))').body
            counts['paths'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'expected_review':
            node.body.insert(-1, ast.parse("row.update(schema='native-own-local-self-actor-review-v1',self_info_opcode=0x4e38,actor_opcode=0x4e96,world_reply_sequence='same_owned_writer_ACK_drain_MAP_drain_SELF_drain_ACTOR_drain',self_info_frame_size=len(SELF_FRAME),actor_frame_size=len(ACTOR_FRAME),self_actor_configuration_policy='EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73',normal_server_success_proven=False,myplayer_creation_proven=False,world_ready_claim=False,tileload_claim=False)").body[0])
            counts['review'] += 1
        if isinstance(node, ast.FunctionDef) and node.name == 'pin_context':
            lock = next(e for e in node.body if isinstance(e, ast.With))
            lock.body.insert(-1, ast.parse('for path in (MAP_SOURCE,PINS_PATH,*PROFILE_PATHS):\n held=backing.b.a.add(path)\n backing.pinned_hashes[path]=held.digest()').body[0])
            counts['pins'] += 1
    need(counts == dict(select=1, transport=1, paths=1, review=1, pins=1), 'EXACT_ONE_CP57_SUCCESSOR_SCOPE')
    return ast.fix_missing_locations(tree)


def wrap(base):
    map_hook = load(MAP_SOURCE, '_cp57_frozen_map_hook')
    row, _, _ = map_hook.baseline()
    profile, fields, self_dto, actor_dto = profiles()
    info, actor = frame(0x4e38, self_dto), frame(0x4e96, actor_dto)
    metadata = {info: self_dto.metadata(), actor: actor_dto.metadata()}
    def exact_world_frame(wire):
        need(type(wire) is bytes and wire in metadata, 'UNDECLARED_SELF_OR_ACTOR_FRAME_REFUSED')
        return metadata[wire]
    def exact_selected(reference, selected):
        need(type(selected) is tuple and len(selected) == 2 and type(selected[0]) is int
             and selected[0] == profile.fields[1] and reference == fields[9],
             'EXACT_PROFILE_OWN_STORED_SELECTION_REQUIRED')
    namespace = dict(vars(map_hook.ack), SELF=SELF, ACK_SOURCE=map_hook.ACK_SOURCE,
                     MAP_SOURCE=MAP_SOURCE, WORLD_PATH=map_hook.WORLD_PATH,
                     BINDING=map_hook.BINDING, BASELINE=row, MAP_FRAME=map_hook.map_frame(),
                     SELF_FRAME=info, ACTOR_FRAME=actor, validate_selected=exact_selected,
                     EVIDENCE_PATHS=tuple(ROOT / n for n in row['evidence_pins']),
                     PINS_PATH=PINS_PATH, PROFILE_PATHS=tuple(ROOT / n for n in pins()),
                     validate_map_frame=map_hook.validate_map_frame,
                     validate_world_frame=exact_world_frame)
    exec(compile(successor_tree(map_hook), str(SELF), 'exec'), namespace)
    return namespace['wrap'](base)
