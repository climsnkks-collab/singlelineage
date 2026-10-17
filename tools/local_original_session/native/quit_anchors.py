"""Copy only already documented CONTROL RVA spans; no decoding or execution."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
READER = ROOT / 'tools/local_movement_contract/source.py'
READER_SHA = '7319028e5b030341d30dc496b38a04a65c7f0ac8e753ddf090654544a9950ade'


def generate():
    if hashlib.sha256(READER.read_bytes()).hexdigest() != READER_SHA:
        raise ValueError('QUIT_READER_PIN')
    spec = importlib.util.spec_from_file_location('_quit_anchor_reader', READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, view = module.view()
    spans = [(1, 0x944b80, 12), (2, 0xacbda0, 0x11a),
             (2, 0x13c0d0, 0x376), (3, 0xacb2a0, 12)]
    rows, proof = [], []
    for route, rva, size in spans:
        raw = view.read(rva, size)
        digest = hashlib.sha256(raw).hexdigest()
        if rva == 0xacbda0 and digest != 'a51c6b51da1214a38c9546658c62dc343ee13be7ba6ff4cbb2f1d329ae4885c5':
            raise ValueError('LAND_QUIT_FULL_BODY_PIN')
        if rva == 0x13c0d0 and digest != '1f3b44ffef39cc13016f0127f4a485410ce3db62a262abd2182767e7723f69a5':
            raise ValueError('GAME_STATE_QUIT_FULL_BODY_PIN')
        proof.append({'route': route, 'rva': hex(rva), 'bytes': size, 'sha256': digest})
        for offset in range(0, size, 32):
            chunk = raw[offset:offset+32]
            rows.append(' {%d,0x%x,%d,{%s}},' % (route, rva+offset, len(chunk), ','.join('0x%02x' % b for b in chunk)))
    text = ('#pragma once\n// Fixed documented CONTROL bytes; no new decode.\n'
            'namespace internal_quit_source {\n'
            'struct Anchor {unsigned route;uintptr_t rva;size_t size;unsigned char bytes[32];};\n'
            'static constexpr Anchor anchors[]={\n'+'\n'.join(rows)+'\n};\n}\n')
    return text, {'reader_sha256': READER_SHA, 'CONTROL_sha256': '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af', 'spans': proof, 'new_decode_or_process_actions': 0}


if __name__ == '__main__':
    text, proof = generate()
    target = Path(__file__).with_name('quit_source_anchors.hpp')
    target.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'proof': proof}))
