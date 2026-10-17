"""Read the exact owned Login scene's widget cache and Bt_Ok callback pins."""
from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path

import watch


LAYOUT_VFT = 0x1230558
OK_CALLBACK_VFT = 0x1230760


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def inspect(candidate: Path, digest: str, pid: int, birth: str,
            *, include_transient: bool = False):
    contract = watch.contract_for(candidate, digest)
    native_mod = watch.load(watch.NATIVE, '_login_button_native')
    sampler_mod = watch.load(watch.SAMPLER, '_login_button_sampler')
    native = native_mod.Native(contract, {'pid': pid, 'birth': birth})
    try:
        native.attach()
        modules = native.modules()
        base = modules['LC']['base']
        sampler = sampler_mod.Sampler(native, contract, modules['LC'])
        sampler.bytes = 0
        sampler.read_limit = 8192
        route = sampler.route()
        state = sampler.unique(route[-1], 'GameState')
        scene, raw = sampler.scene(state)
        need(scene['current']['kind'] == 'Login', 'LOGIN_SCENE_REQUIRED')
        scene_owner, _ = sampler.strong_pair(raw[:16])
        render = sampler.pointer(scene_owner + 8, nullable=True)
        render_vft = sampler.pointer(render) if render else None
        sampler.bytes = 0
        ui = sampler.unique(route[-1], 'UI')
        head, count = struct.unpack('<QQ', sampler.read(ui + 0x350, 16))
        need(0 < count <= 64, 'BOUNDED_UI_CACHE_REQUIRED')
        node = sampler.pointer(head)
        seen = set()
        matches = []
        classes = {}
        for _ in range(count):
            need(node not in seen and node != head, 'UI_CACHE_CYCLE')
            seen.add(node)
            pair = sampler.read(node + 0x30, 16)
            obj, _ = sampler.strong_pair(pair)
            vft = sampler.pointer(obj)
            rel = vft - base if base <= vft < base + contract['image_size'] else None
            if rel is not None:
                classes[hex(rel)] = classes.get(hex(rel), 0) + 1
            if vft == base + LAYOUT_VFT:
                matches.append(obj)
            node = sampler.pointer(node)
        need(node == head, 'UI_CACHE_COUNT_CHANGED')
        result = {'schema': 'lc-login-button-memory-probe-v1',
                  'candidate_sha256': digest,
                  'scene': scene['current']['kind'],
                  'scene_render_is_login_layout': render_vft == base + LAYOUT_VFT,
                  'ui_cache_count': count,
                  'login_layout_matches': len(matches),
                  'button_observations': []}
        sampler.bytes = 0
        for layout in matches[:2]:
            button = sampler.pointer(layout + 0xe0)
            button_vft = sampler.pointer(button)
            callback = sampler.read(button + 0x4f0, 24)
            closure_vft, captured_layout, extra = struct.unpack('<QQQ', callback)
            raw_button = sampler.read(button, 0x4f0)
            offset_hits = []
            for offset in range(0, len(raw_button) - 8, 4):
                x, y = struct.unpack_from('<ff', raw_button, offset)
                if (math.isfinite(x) and math.isfinite(y)
                        and abs(x - 380) < 0.1 and abs(y + 244) < 0.1):
                    offset_hits.append(offset)
            result['button_observations'].append({
                'button_vft_in_image': base <= button_vft < base + contract['image_size'],
                'callback_vft_matches': closure_vft == base + OK_CALLBACK_VFT,
                'callback_captures_layout': captured_layout == layout,
                'csb_position_offset_hits': offset_hits,
                'extra_word_nonzero': extra != 0})
        # Keep class counts bounded without exposing memory addresses.
        result['ui_class_count'] = len(classes)
        if include_transient and len(matches) == 1 and len(result['button_observations']) == 1:
            observed = result['button_observations'][0]
            if observed['callback_vft_matches'] and observed['callback_captures_layout']:
                result['_transient_layout'] = matches[0]
                result['_transient_button'] = sampler.pointer(matches[0] + 0xe0)
        return result
    finally:
        native.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--sha', required=True)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--birth', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    row = inspect(a.candidate.resolve(), a.sha, a.pid, a.birth)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(row, f, indent=2)
        f.write('\n')
    print(json.dumps({'status': 'RECORDED',
                      'scene': row['scene'],
                      'layout_matches': row['login_layout_matches'],
                      'output': str(a.output)}))


if __name__ == '__main__':
    main()
