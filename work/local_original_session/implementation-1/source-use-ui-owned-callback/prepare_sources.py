"""Copy accepted literal spans into the new direct-consumer guards. No decode/PE parser."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sha = lambda b: hashlib.sha256(b).hexdigest()


def main():
    accepted = ROOT / 'work/local_server_rea_20261016/run55_current_pc_receiver/source-evidence.json'
    raw = accepted.read_bytes()
    if sha(raw) != 'c91afdcecf00b21d3e152f83e72f78df35b7ee7867db56e4c2fdd298850de663':
        raise ValueError('accepted55 index changed')
    source55 = json.loads(raw)
    accepted56 = (ROOT / 'work/local_server_rea_20261016/run56_owned_slot_callback/source-evidence.json').read_bytes()
    if sha(accepted56) != '1db6241761ad5eaf17df409211bf07dfae1adb4959c7feec82786242cead2129':
        raise ValueError('accepted56 input changed')
    source56 = json.loads(accepted56)
    accepted54 = (ROOT / 'work/local_server_rea_20261016/run54_component_attachment/worker/source-evidence.json').read_bytes()
    if sha(accepted54) != '28016917c6b59618f3115e64d79b956a98cd71ca9cd6a790e8df420ee5dcbfda':
        raise ValueError('accepted54 input changed')
    source54 = json.loads(accepted54)
    source33 = json.loads((ROOT / 'work/local_server_rea_20261016/run33_quit_button_lookup/caller/source-evidence.json').read_bytes())
    spans = []
    with Path(source55['target']['path']).open('rb') as carrier:
        def literal(source, role):
            carrier.seek(source['carrier_file_offset'])
            value = carrier.read(source['length'])
            if len(value) != source['length'] or sha(value) != source['sha256']:
                raise ValueError('accepted literal changed: ' + role)
            return int(source['rva'], 16), value
        for function in source55['new_source']:
            if function['source']['rva'] in ('0xa13b10', '0xa0d5d0', '0xb3a0b0'):
                rva, value = literal(function['source'], function['role'])
                spans.append((rva, value))
        for function in source54['new_file_source']:
            if function['source']['rva'] == '0xc52840':
                rva, value = literal(function['source'], function['role'])
                spans.append((rva, value))
        for function in source56['accepted_reuse']['functions']:
            if function['source']['rva'] in ('0xa56810','0xa0c0b0'):
                rva, value = literal(function['source'], function['role'])
                spans.append((rva, value))
        data = [literal(row['source'], row['role']) for row in source55['Data_keys']]
        data.append(literal(source54['name_key']['source'], 'existing component key'))
    # Existing accepted33's exact Restored reader, only its previously accepted
    # 3BE90 span. No instruction API, function/xref query or PE mapping is used.
    cleanup = next(w for w in source33['windows'] if w['decoded_entry'] == '0x3be90')
    if cleanup['decoded_sha256'] != '2c0bdb43b1f03707e482c74ff0ba9c9424c5203fedbd122dc1448f9b4f3d739e':
        raise ValueError('accepted33 cleanup input changed')
    reader = ROOT / 'work/standalone_boot/child_launch_source.py'
    if sha(reader.read_bytes()) != '74d5087b561614b5322e26bdb74a77f404c8ebab28fecfff1bcd4a2749d6f7e8':
        raise ValueError('accepted literal reader changed')
    spec = importlib.util.spec_from_file_location('_owned_ui_literal_reader', reader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    restored = module.Restored()
    if restored.records != source33['source_records']:
        raise ValueError('accepted33 source records changed')
    start, end = int(cleanup['decoded_entry'], 16), int(cleanup['decoded_end_exclusive'], 16)
    value = restored.read(start, end - start)
    if sha(value) != cleanup['decoded_sha256']:
        raise ValueError('accepted33 cleanup literal changed')
    spans.append((start, value))
    # Reuse only the existing direct allocator prefix, not Quit's cast or any
    # unused child-code preflight. Accepted normal size<1000h allocator contract.
    value = restored.read(0x3c020,16)
    import re
    frozen = (ROOT / 'work/local_original_session/implementation-1/manual-source-reselect/quit_lookup_anchors.hpp').read_text(encoding='utf-8-sig')
    match = re.search(r'\{0x3c020,16,\{([^}]+)\}\}',frozen)
    if not match or value != bytes(int(x.strip(),16) for x in match.group(1).split(',')):
        raise ValueError('accepted allocator prefix changed')
    spans.append((0x3c020,value))

    def entries(rows):
        result = []
        for rva, value in rows:
            for offset in range(0, len(value), 16):
                piece = value[offset:offset + 16]
                result.append('{0x%x,%d,{%s}},' % (rva + offset, len(piece), ','.join('0x%02x' % b for b in piece)))
        return '\n'.join(result) + '\n'
    (HERE / 'owned_ui_code_anchors.inc').write_text(entries(spans), encoding='utf-8')
    (HERE / 'owned_ui_data_anchors.inc').write_text(entries(data), encoding='utf-8')
    print('accepted literal generation: direct code scopes=%d bytes=%d; data scopes=%d; decode0/runtime0' %
          (len(spans), sum(len(value) for _, value in spans), len(data)))


if __name__ == '__main__':
    main()
