"""Exact reviewed CP59 world reader and its source-only dependencies."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PATH = Path(__file__).with_name('world-reader-pins.json')
SHA = '054deea6ee4e0764a879f3fc82f455744f28bb9d2abf853f12de422ba14c0c71'

def pins():
    raw = PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError('EXACT_CP59_WORLD_PINS')
    result = json.loads(raw)
    for path,digest in result.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('CP59_WORLD_DEPENDENCY_CHANGED:' + path)
    return result
