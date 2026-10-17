"""Read bytes/AST only; no imports of the frozen/native runtime modules."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def verify():
    basis = json.loads((HERE / 'source-basis.json').read_bytes())
    if basis['schema'] != 'persistent-broker-source-basis-v1' or basis['executable_admission'] is not False:
        raise ValueError('READ_ONLY_BASIS_REQUIRED')
    checks = 0
    for name, row in basis['sources'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError('SOURCE_OUTSIDE_ROOT')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('SOURCE_ANCHOR_CHANGED:' + name)
        for text in row['anchors']:
            if text not in raw.decode('utf-8-sig'):
                raise ValueError('SOURCE_TEXT_ANCHOR_CHANGED:' + name)
            checks += 1
    return {'status': 'PASS_READ_ONLY_SOURCE_PINS', 'sources': len(basis['sources']),
            'text_anchors': checks, 'native_actions': 0, 'production_adapters': 0,
            'executable_admission': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
