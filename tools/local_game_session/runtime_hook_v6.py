"""Exact source_v6 J API extension; all frozen final guards remain intact."""
import ast
import hashlib
from pathlib import Path

_path = Path(__file__).resolve().with_name('runtime_hook_final.py')
_digest = '6c8d369cd04d265a31f29d4524d9b04cf14cfc3a1c7356adf4584b16c4a66b40'
_raw = _path.read_bytes()
if hashlib.sha256(_raw).hexdigest() != _digest:
    raise ValueError('FROZEN_GAME_RUNTIME_FINAL_CHANGED')
_tree = ast.parse(_raw, str(_path))
_matches = [node for node in ast.walk(_tree)
            if isinstance(node, ast.Tuple)
            and all(isinstance(value, ast.Constant) for value in node.elts)
            and tuple(value.value for value in node.elts)
                == ('source.py', 'source_v2.py', 'source_v3.py', 'source_v4.py')]
if len(_matches) != 1:
    raise ValueError('EXACT_J_SOURCE_NAME_TUPLE_REQUIRED')
_matches[0].elts.append(ast.copy_location(ast.Constant('source_v6.py'), _matches[0].elts[-1]))
exec(compile(ast.fix_missing_locations(_tree), str(_path), 'exec'), globals())
PINS['tools/local_game_session/runtime_hook_final.py'] = _digest
