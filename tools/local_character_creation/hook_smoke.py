"""File-only creation hook/source compatibility check; no listener or game."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    fix = load(ROOT / 'tools/local_native_login_screen_runtime/fix.py',
               '_creation_smoke_runtime')
    existing = fix.source_api().game_hook()
    hook_name = ('ack_create_news_diag.py' if '--news-diag' in sys.argv[1:] else
                 'ack_create_news.py' if '--news' in sys.argv[1:] else
                 'ack_create_wait.py' if '--wait' in sys.argv[1:] else 'ack_create.py')
    hook = load(ROOT / 'tools/local_native_login_local_ack_hook' / hook_name,
                '_creation_smoke_hook')
    adapted = hook.wrap(existing.port_adapted_base)
    transport = adapted.transport()
    assert transport.CREATE_ACK_FRAME == hook.realm.create_ack(0)
    assert transport.ACK_FRAME == hook.ACK_FRAME
    assert hook.STORE_PATH.is_relative_to(ROOT)
    assert hash_source(hook.REALM_PATH) == hook.REALM_SHA
    print('FILE_ONLY_CREATE_HOOK_PASS')


def hash_source(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    main()
