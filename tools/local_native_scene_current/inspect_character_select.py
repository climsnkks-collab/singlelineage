"""Read the owned CharacterSelect scene's public UI layout class presence."""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import watch


def inspect(candidate, digest, pid, birth, *, include_transient=False):
    contract = watch.contract_for(candidate, digest)
    native_mod = watch.load(watch.NATIVE, '_character_ui_native')
    sampler_mod = watch.load(watch.SAMPLER, '_character_ui_sampler')
    native = native_mod.Native(contract, {'pid': pid, 'birth': birth})
    try:
        native.attach()
        game = native.modules()['LC']
        sampler = sampler_mod.Sampler(native, contract, game)
        sampler.bytes = 0
        sampler.read_limit = 8192
        route = sampler.route()
        state = sampler.unique(route[-1], 'GameState')
        scene, _ = sampler.scene(state)
        if scene['current']['kind'] != 'CharacterSelect':
            raise ValueError('CHARACTER_SELECT_SCENE_REQUIRED')
        sampler.bytes = 0
        ui = sampler.unique(route[-1], 'UI')
        head, count = struct.unpack('<QQ', sampler.read(ui + 0x350, 16))
        if not 0 < count <= 64:
            raise ValueError('BOUNDED_UI_CACHE_REQUIRED')
        node = sampler.pointer(head)
        matches = {'CharacterCreateLayout': 0, 'CharacterSelectLayout': 0}
        slot_rows = []
        select_layout = None
        vtables = {game['base'] + 0x1214c70: 'CharacterCreateLayout',
                   game['base'] + 0x1214f58: 'CharacterSelectLayout'}
        seen = set()
        for _ in range(count):
            if node in seen or node == head:
                raise ValueError('UI_CACHE_CYCLE')
            seen.add(node)
            obj, _ = sampler.strong_pair(sampler.read(node + 0x30, 16))
            label = vtables.get(sampler.pointer(obj))
            if label:
                matches[label] += 1
                if label == 'CharacterSelectLayout':
                    select_layout = obj
                    for index in range(3):
                        button = sampler.pointer(obj + 0xc0 + index * 16, nullable=True)
                        if button:
                            callback = sampler.pointer(button + 0x570, nullable=True)
                            captured = sampler.pointer(button + 0x578, nullable=True)
                            outer = sampler.pointer(button + 0x4f0, nullable=True)
                            bundle = sampler.pointer(button + 0x4f8, nullable=True)
                            selection_bound = False
                            if bundle:
                                selection_bound = (
                                    outer == game['base'] + 0x1217508
                                    and sampler.pointer(bundle + 0x88) == button
                                    and sampler.pointer(bundle + 8) == game['base'] + 0x1214eb0
                                    and sampler.pointer(bundle + 0x48) == game['base'] + 0x1214e78
                                    and sampler.pointer(bundle + 0x10) == obj
                                    and struct.unpack('<i', sampler.read(bundle + 0x18, 4))[0] == index)
                            slot_rows.append({'index': index,
                                              'button_in_image': game['base'] <= sampler.pointer(button) < game['base'] + contract['image_size'],
                                              'callback_table_rva': hex(callback - game['base']) if game['base'] <= callback < game['base'] + contract['image_size'] else None,
                                              'callback_captures_layout': captured == obj,
                                              'selection_event_bound': selection_bound})
                        else:
                            slot_rows.append({'index': index, 'button_present': False})
            node = sampler.pointer(node)
        if node != head:
            raise ValueError('UI_CACHE_COUNT_CHANGED')
        result = {'schema': 'lc-owned-character-select-layout-presence-v1',
                'scene': 'CharacterSelect', 'ui_cache_count': count,
                'matches': matches, 'slots': slot_rows, 'raw_pointers_saved': False,
                'visible_ui_proven': False}
        if include_transient and matches['CharacterSelectLayout'] == 1 and select_layout:
            first = next((x for x in slot_rows if x.get('index') == 0), None)
            if (first and first.get('selection_event_bound') is True):
                result['_transient_layout'] = select_layout
                result['_transient_button'] = sampler.pointer(select_layout + 0xc0)
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
    with a.output.open('x', encoding='utf-8') as stream:
        json.dump(row, stream, indent=2)
        stream.write('\n')
    print(json.dumps(row))


if __name__ == '__main__':
    main()
