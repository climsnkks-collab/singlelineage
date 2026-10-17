"""Bind the frozen prepared serve_both to the request-driven owned game route."""
import ast
import copy
import hashlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BROKER = 'tools/local_ready_entry_prepared/broker.py'
SCOPE = 'tools/local_ready_entry_prepared/scope.py'
PINS = {
    BROKER: 'df64f07566198986a96c83489a32bc69366315c75d3ba974fcec71a1912ae6e5',
    'tools/local_game_session/connection.py': 'bb50d27c2070505e2b1d6c4a12a29cff72c08520a14a5b1a2a7905533595072e',
    'tools/local_game_session/session.py': '81da91b9577e6033cb53738367605c56c1828efe7e3bc3e91c8aa6b15fbeff1e',
    'tools/local_character_wire_v2/wire.py': '466d3db45f1765f2cb3ce3e5a25917615ebd07326c428f29b66b80512d372cfc',
    'tools/local_world_protocol/model.py': '2d1ebdec0c3fc7830702691d045d89c6dacfdbf706cbf5eb9670be20e3cd5f07',
    'tools/local_entry_server/protobuf.py': 'c6d00262da031fb03a138c34b6a86dfc88f03e8ead2d6e71ae9bb21cd45de389',
    SCOPE: '4367dd1eb26566063294eb5efb847d1adc2992ba29a8850b429a971d8d7a93a2',
}

def need(ok, code):
    if not ok:
        raise ValueError(code)

def checked_sources():
    rows = {}
    for name, digest in PINS.items():
        path = ROOT / name
        for part in (path, *path.parents):
            stat = part.lstat()
            need(not part.is_symlink() and not getattr(stat, 'st_file_attributes', 0) & 0x400,
                 'GAME_RUNTIME_SOURCE_REPARSE')
        need(path.is_file() and path.stat().st_nlink == 1 and path.stat().st_size <= 2097152,
             'GAME_RUNTIME_SOURCE_BOUND')
        raw = path.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == digest, 'GAME_RUNTIME_SOURCE_CHANGED')
        rows[name] = raw
    return rows

def input_paths():
    return [ROOT / name for name in PINS] + [Path(__file__).resolve()]

def backing_context(ctx):
    if type(ctx).__name__ != 'PreparedContext':
        return ctx
    need(Path(type(ctx).__init__.__code__.co_filename).resolve() == ROOT / SCOPE,
         'EXACT_PREPARED_CONTEXT_SOURCE_REQUIRED')
    parent = ctx.parent
    need(ctx.proof is parent.proof and ctx.lock is parent.lock
         and ctx.pinned_hashes is parent.pinned_hashes, 'EXACT_PREPARED_PARENT_REQUIRED')
    return parent

def pin_context(ctx):
    """Use the existing deny-write/delete pins before PreparedScope captures them."""
    checked_sources()
    backing = backing_context(ctx)
    with backing.lock:
        need(getattr(ctx, 'scope', None) is None, 'GAME_RUNTIME_PIN_BEFORE_SCOPE_REQUIRED')
        for path in input_paths():
            for directory in reversed(path.parents):
                if directory == ROOT or ROOT in directory.parents:
                    backing.b.a.add(directory)
            pin = backing.b.a.add(path)
            backing.pinned_hashes[path] = pin.digest()
        ctx.verify_sources()
        checked_sources()

def bind_serve_both(prepared, ctx, approved_config, *, on_selection=None):
    """Return the concrete original-signature async serve_both; do not listen here.

    Call pin_context before ctx.open. Supply the prepared module already loaded
    by the approved runtime and the explicit config returned by its source.
    """
    rows = checked_sources()
    ctx.verify_sources()
    backing = backing_context(ctx)
    need(Path(prepared.__file__).resolve() == ROOT / BROKER, 'EXACT_PREPARED_MODULE_REQUIRED')
    for path in input_paths():
        need(path in backing.b.a.pins and path in backing.pinned_hashes,
             'GAME_RUNTIME_RETAINED_PIN_REQUIRED')
        if path != Path(__file__).resolve():
            need(backing.pinned_hashes[path] == PINS[path.relative_to(ROOT).as_posix()],
                 'GAME_RUNTIME_PIN_DIGEST_CHANGED')
    config = copy.deepcopy(approved_config)
    need(config == prepared.source.approved(ctx.proof), 'EXPLICIT_APPROVED_CONFIG_REQUIRED')
    filename = str(ROOT / BROKER)
    tree = ast.parse(rows[BROKER], filename=filename)
    # The approved J loader substitutes its source API by removing only this
    # module-level import. That changes compiler optimizations, not function AST.
    source_path = Path(prepared.source.__file__).resolve()
    is_j = source_path.parent == ROOT / 'tools/local_selected_client_fix'
    if is_j:
        need(source_path.name in ('source.py', 'source_v2.py', 'source_v3.py', 'source_v4.py')
             and prepared.source.FAMILY == 'LOCAL_SELECTED_J_TIMEOUT_RESET'
             and prepared.source.CLIENT_SHA == ctx.proof.get('current_sha256'),
             'EXACT_APPROVED_J_SOURCE_REQUIRED')
        need(source_path in backing.b.a.pins and source_path in backing.pinned_hashes
             and hashlib.sha256(source_path.read_bytes()).hexdigest() == backing.pinned_hashes[source_path],
             'APPROVED_J_SOURCE_RETAINED_PIN_REQUIRED')
        for node in list(tree.body):
            if isinstance(node, ast.Import) and any(alias.name == 'source' for alias in node.names):
                node.names = [alias for alias in node.names if alias.name != 'source']
                if not node.names:
                    tree.body.remove(node)
    original = compile(ast.fix_missing_locations(tree), filename, 'exec')
    for name in ('serve_both', 'run_conversation', 'finish_cleanup'):
        expected = next(code for code in original.co_consts
                        if isinstance(code, types.CodeType) and code.co_name == name)
        actual = getattr(prepared, name)
        need(actual.__code__ == expected and actual.__code__.co_filename == filename
             and actual.__globals__ is prepared.__dict__,
             'EXACT_PREPARED_FUNCTION_REQUIRED')

    module = types.ModuleType('_owned_game_runtime_connection')
    module.__file__ = str(ROOT / 'tools/local_game_session/connection.py')
    sys.modules[module.__name__] = module
    exec(compile(rows['tools/local_game_session/connection.py'], module.__file__, 'exec'), module.__dict__)
    game = module.OwnedGameAdapter(config, source_guard=ctx.verify_sources, on_selection=on_selection)
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                    and node.name == 'serve_both')
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == 'bootstrap_connection'
             and isinstance(node.func.value, ast.Name) and node.func.value.id == 'base']
    need(len(calls) == 1, 'EXACT_BOOTSTRAP_CALLSITE_REQUIRED')
    calls[0].func = ast.copy_location(ast.Name(id='_owned_game_bootstrap', ctx=ast.Load()), calls[0].func)
    namespace = dict(prepared.__dict__)
    namespace['_owned_game_bootstrap'] = game.bootstrap_connection(prepared.base)
    # Compile the whole syntax tree to preserve the original module symbol
    # table/optimizations, but execute no imports or other top-level statements.
    amended = compile(ast.fix_missing_locations(tree), filename, 'exec')
    code = next(value for value in amended.co_consts
                if isinstance(value, types.CodeType) and value.co_name == 'serve_both')
    operation = types.FunctionType(code, namespace, 'serve_both', prepared.serve_both.__defaults__)

    bound_ctx = ctx
    async def serve_both(parent, resource, ctx, trace, stop=None, pins=None, owner_guard=None, pool=None):
        need(ctx is bound_ctx, 'EXACT_BOUND_CONTEXT_REQUIRED')
        ctx.verify_sources()
        return await operation(parent, resource, ctx, trace, stop, pins, owner_guard, pool)
    serve_both.owned_game_adapter = game
    return serve_both
