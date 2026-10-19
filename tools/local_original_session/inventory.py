"""One explicit source-bound ADD to an empty retained Inventory.

No request trigger, automatic bootstrap send, item allocator or save format.
The caller owns the real row lock and native checkpoint. The synchronous
pre-write leaf must run after that checkpoint and immediately before write.
Static catalog membership is separate from live catalog materialization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
import hashlib
import json
import re
import struct

from tools.local_original_session import edge, movement, observe

pb = movement.pb
OPCODE = 0x0964
POLICY = 'EXPLICIT_ONE_ADD_TO_EMPTY_INVENTORY'
MIN_INTERVAL_NS = 500_000_000
BYTE_LIMIT = observe.RETAINED_SAMPLE_LIMIT
U64_MAX = (1 << 64) - 1
MAX_FRAME = 1024
# Exact first local subset: every directly copied scalar/string is explicit.
# These optional fields are not promoted to protobuf-required fields.
FIELD_TYPES = {1: 'u32', 2: 'i32', 3: 'u64', 4: 'u64', 5: 'i32', 7: 'i32',
               9: 'u64', 10: 'u64', 13: 'i32', 14: 'u32', 16: 'i32',
               17: 'i32', 18: 'bytes', 22: 'i32', 24: 'bool', 25: 'i32', 26: 'bool'}
PROOF = 'work/online_inventory_skill_source/source-contract.json'
EVIDENCE = 'work/local_server_rea_20261016/run30_inventory_first_wire/source-evidence.json'
CATALOG_NAMES = 'work/all_table_semantics/item/current-names.json'
MAP_PROOF = 'work/online_world_public_source/map-contract.json'
PUBLIC_PROOF = 'work/online_public_session-v4/source-contract.json'
INTRO_PROOF = 'work/online_intro_capture_20261006/source-contract.json'
WORLD_PROOF = 'work/local_native_world_read_review/source-contract.json'
POSITION_PROOF = 'work/online_world_public_source/position-contract.json'
CLONE_PROOF = 'work/local_native_login_state5_ack_candidate/manifest-final.json'
SIBLING_PROOF = 'work/local_original_session/native-sibling/BUILD_RESULT.json'
# The fixed proof retains both the 530980 allocation/init path and the
# current 718 -> owned-context0 state transition. This query reads the latter;
# it does not execute or inspect an allocation/init operation.
MAP_ALLOCATION_INIT_RVAS = (0x5309b8, 0x5309bd, 0x5309c2, 0x5309c9,
                            0x5309cf, 0x5309d3, 0x5309fd)
MAP_CURRENT_CHECK_RVAS = (0x532791, 0x532818, 0x53281f, 0x53284a, 0x532851, 0x532858)
# Keep the complete Player proof pinned; this passive query does not execute
# the MyPlayer construction/base-construction/vptr-init path.
PLAYER_ALLOCATION_INIT_RVAS = (0xc26e6, 0xc26ec, 0xc26f3)
PLAYER_CURRENT_CHECK_RVAS = (0x60b6a, 0x60b70, 0x60b77, 0x60b83, 0x60b89,
    0x60b8c, 0x60b91, 0x60c17, 0x60c1e, 0x66ca6, 0x66caf, 0x66cb3,
    0x66cb6, 0x66cb9, 0x66cbd, 0x66cc5, 0x40f00, 0x40f03, 0x40c00, 0x40c04)
# All 38 anchors remain pinned. Query guards follow the memory actually read;
# they do not claim to invoke these getters, callbacks, constructors or setters.
INVENTORY_SOURCE_ROLES = {
    'registered_getter': (0x7735e, 0x7736b, 0x77372, 0x77379, 0x773a7),
    'vector_init': (0x4fb4ce, 0x4fb4d5, 0x4fb4dc),
    'append_construction': (0x4f5c2b, 0x4f5c70, 0x4f5c7a),
    'current_vector': (0x4f6609, 0x4f6610, 0x4f6627, 0x4f662a, 0x4f6630),
    'item_storage': (0x5093da, 0x509507, 0x50950a, 0x50950e, 0x509511,
                     0x509515, 0x509519, 0x50951d, 0x509524, 0x509528, 0x50952f),
    'setter_display': (0x50a6e1, 0x50a6eb, 0x50a762, 0x50a767),
    'spell': (0x5b3a21, 0x5b3a28, 0x5b3a2f, 0x5b3a51, 0x5b2319, 0x5b2657, 0x5b265e),
}
# The passive query calls no native Inventory getter or packet callback.
# Registration/vector layout remains in the complete pinned source proof;
# current route, unique type/table and headers/pairs are read and rechecked.
# Item storage-width guards are needed only when interpreting an actual row.
SOURCE_PINS = {
    PROOF: '17c2bcd6f40f90470f77a385dd78668be3a61d2686961fa83c58702dd0fc46a1',
    EVIDENCE: '46d0d2aaaa49f2468ede8ec61383396aae81eda22f2174861a6e082ae3def5d7',
    'work/local_server_rea_20261016/run30_inventory_first_wire/findings.md':
        'b6446c6bac850061d249ec50864a988920811f05739782a1ce87e3dae8e4c0a0',
    CATALOG_NAMES: '3db39c8698e349ae85b9913966023da154d71a764a4fc1e53883b656828880bb',
    'work/all_table_semantics/item/fields.json':
        '646aadb3e5a53938b7aa2798f75a19e9046d3a2daca732e98595d5207d500f5b',
    'work/all_table_semantics/item/verification.json':
        'e4976c163129423fc23d3ce5aff426c6716dc80592bf40c476e2eea0982ac801',
    'work/online_world_public_source/player-contract.json':
        '8f6b372d1902cd21df8be9634f5b8fb3d4729362496795fc0da39b361585cb02',
    MAP_PROOF:
        'f43bd49e8ce078d0c6ca153ce6febcda1433c5f2838115260451b5bca61ea6a3',
    PUBLIC_PROOF: '5150ac7b24a0497210615876fb6d1560b21ed5e809809434999bbf26f6a2d222',
    INTRO_PROOF: '2c9af49767502c0b28f39a24dd24ffe44eb142ed9acf0cd2372dcc11bf87c7e5',
    WORLD_PROOF: '1ed36a8a8a059c141ba98aa9a277cebd0eee7c3011e204de4ef9464580b79784',
    POSITION_PROOF: '07c190452808f2035fa8001e57096b07cdd69207e62f9f3e890391cbc5276e11',
    CLONE_PROOF: '031404ef5508e71af10dd0b29b8f7a3103e1d9c982985099345dd90e123a91c8',
    SIBLING_PROOF: '9ef0bacda87b0d59b2caff2430d3d7eee26ec28271951b9a3c035d3c4578679c',
    'work/local_original_session/native-sibling/source-report.json':
        'ee8b84517eb102c980add8fea305461e2d47b9d6ed61f2f881e7ba5d8eea2472',
    'tools/local_native_login_candidate/rebuild.py':
        'ac6e8d12d3c8486ee4794f93f56761c4556d3f0c11b4aa0fdf418a31a16a28d7',
    'work/local_server_rea_20261016/run3_quit_4ed6/quit/quit_type.json':
        '99a7c06f00ecbbb4e88ff3dd82f1f23fdfd6c2053869b9da586b1cab1db3faa6',
    'work/local_server_rea_20261016/run3_quit_4ed6/quit/quit_state_producers.json':
        '3cfb697421bbb18c88d4492a6edf5357b719de1d00d5e3432a22feafd3c0e2ac',
    'work/local_server_rea_20261016/run3_quit_4ed6/quit/quit_response_transition.json':
        '1344be20822d59984b083d5c4c9e7b3a28719f5dd7205c71e9aa2ae5c086c4b4',
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _source_documents():
    documents = {}
    for relative, expected in SOURCE_PINS.items():
        path = observe.ordinary(observe.ROOT / relative)
        need(0 < path.stat().st_size <= 1048576, 'INVENTORY_SOURCE_BOUND')
        raw = path.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == expected, 'INVENTORY_SOURCE_CHANGED')
        if relative.endswith('.json'):
            documents[relative] = json.loads(raw)
    return documents


def _same_static(actual, expected):
    """Exact types as well as values for these fixed JSON/bytes source caches."""
    kind = type(expected)
    if type(actual) is not kind:
        return False
    if kind is dict:
        return (all(type(k) is str for k in actual) and actual.keys() == expected.keys()
                and all(_same_static(actual[k], v) for k, v in expected.items()))
    if kind in (list, tuple):
        return len(actual) == len(expected) and all(_same_static(a, b) for a, b in zip(actual, expected))
    return kind in (type(None), bool, int, float, str, bytes) and actual == expected


def _freeze_static(value):
    """Immutable type-tagged values of this fixed source-derived reader contract."""
    kind = type(value)
    if kind is dict and all(type(k) is str for k in value):
        return ('dict', tuple((k, _freeze_static(v)) for k, v in sorted(value.items())))
    if kind in (list, tuple):
        return (kind.__name__, tuple(_freeze_static(v) for v in value))
    need(kind in (type(None), bool, int, float, str, bytes), 'INVENTORY_PASSIVE_SOURCE_CACHE_CHANGED')
    return (kind.__name__, value)


def _reader_intro(reader, documents):
    # Reproduce the pinned watch.contract_for/preflight transformations once;
    # no decoder, process query or native call is needed for these known edits.
    image = getattr(reader, 'image', None)
    need(isinstance(image, observe.Path), 'INVENTORY_PREPARED_READER_IMAGE_REQUIRED')
    image = observe.ordinary(image)
    manifest = documents[CLONE_PROOF]
    sibling = documents[SIBLING_PROOF]
    intro = documents[INTRO_PROOF]
    need(image.suffix.casefold() == '.exe'
         and image.stat().st_size == manifest['candidate']['size']
         and manifest['control_ancestor']['sha256'] == intro['original_sha256']
         and manifest['PE']['image_size'] == 65630208
         and sibling['identity_header_only_candidate_sha_changed'] is True
         and sibling['frozen_cp49_cp69_control_and_prior_diagnostic_preserved'] is True,
         'INVENTORY_EXACT_CLONE_SOURCE_REQUIRED')
    row, = intro['tables']['GameState']
    need(row['rva'] == 0x1182e30 and row['targets'][4] == 0x6cfa0,
         'INVENTORY_EXACT_CLONE_SOURCE_REQUIRED')
    row['targets'][4] = 0x6cfa3  # Pinned rebuild.py H bootstrap slot 1182E50.
    digest = observe.digest(image)
    need(digest in (manifest['candidate']['sha256'], sibling['candidate']['sha256']),
         'INVENTORY_EXACT_CLONE_SOURCE_REQUIRED')
    intro.update(original_program=str(image), SDK_program=str(image.with_name('ncplatformsdk-cpp.dll')),
                 original_sha256=digest, image_size=manifest['PE']['image_size'])
    return observe.quit_scene_contract(intro)


def _source():
    documents = _source_documents()
    proof, wire = documents[PROOF], documents[EVIDENCE]
    need(proof['CONTROL'] == wire['CONTROL_sha256'] and wire['wire_binding']['numeric_opcode'] == OPCODE,
         'INVENTORY_SOURCE_CONTROL_CHANGED')
    all_rvas = tuple(rva for rows in INVENTORY_SOURCE_ROLES.values() for rva in rows)
    checks = {r['rva']: r for r in proof['source_checks']}
    need(len(all_rvas) == len(set(all_rvas)) == len(checks) == len(proof['source_checks']) == 38
         and set(checks) == set(all_rvas)
         and proof['owners']['Inventory']['rva'] == 0x11c6878
         and proof['inventory_control']['rva'] == 0x11c66e8
         and 'ItemEntity' in proof['inventory_control']['public_type']
         and all(proof['inventory'][key] == value for key, value in {
             'begin': 0x3d8, 'end': 0x3e0, 'capacity': 0x3e8, 'stride': 16,
             'row_equals_control_plus': 16, 'row_self_pointer': 0, 'row_id_u64': 8,
             'row_template_id_u32': 0x10, 'row_field18_u64': 0x18,
             'row_quantity_i64': 0x28, 'row_field30_bool': 0x30}.items()),
         'INVENTORY_EXACT_QUERY_SOURCE_REQUIRED')
    schema, = [r for r in wire['schemas'] if r['label'] == 'ItemInfo']
    need([r['field'] for r in schema['fields'] if r['required']] == [1]
         and schema['missing_field_numbers'] == [21], 'INVENTORY_REQUIRED_SOURCE_CHANGED')
    cards = {'u32': '0x891', 'i32': '0x1091', 'u64': '0x8d1', 'bool': '0x11', 'bytes': '0x815'}
    descriptors = {r['field']: r for r in schema['fields']}
    need(all(descriptors[n]['type_card'] == cards[kind] and not descriptors[n]['repeated']
             for n, kind in FIELD_TYPES.items()), 'INVENTORY_FIELD_SOURCE_CHANGED')
    names = documents[CATALOG_NAMES]
    keys = frozenset(r['id'] for r in names)
    fields = documents['work/all_table_semantics/item/fields.json']
    catalog, = [r for r in fields if r['type'] == 'CommonItemInfo' and r['field'] == 1]
    verification = documents['work/all_table_semantics/item/verification.json']
    asset = 'work/asset_data_analysis/current/binary-assets/imported/bin/item.bin'
    need(len(names) == len(keys) == catalog['current']['records_total'] == 1266
         and catalog['semantic_status'] == 'confirmed_code'
         and catalog['storage_type'] == 'uint32'
         and all(type(k) is int and 0 < k <= 0xffffffff for k in keys)
         and verification['input_pins_before'][asset]['sha256'] ==
             verification['input_pins_after'][asset]['sha256'] ==
             '2af035c0431eb1b32d03757f289d9bc007a2ee8901a1dfe958aef03021fb875a',
         'INVENTORY_FIXED_CATALOG_CHANGED')
    # Keep the whole 13-anchor file pinned above. Select the exact six current
    # state anchors by RVA, never by a page, readability result or threshold.
    map_proof = documents[MAP_PROOF]
    map_checks = {r['rva']: r for r in map_proof['source_checks']}
    fields = map_proof['public_fields']
    need(len(map_proof['source_checks']) == len(map_checks) == 13
         and set(map_checks) == set(MAP_ALLOCATION_INIT_RVAS + MAP_CURRENT_CHECK_RVAS)
         and map_proof['MapSubsystem']['vptr_rva'] == 0x11c7df0
         and fields['map_state_field718_i32']['offset'] == 0x718
         and fields['map_state_field718_i32']['size'] == 4
         and fields['owned_tile_context_header0_i32']['pointer_offset'] == 0x6e0
         and fields['owned_tile_context_header0_i32']['header_offset'] == 0
         and fields['owned_tile_context_header0_i32']['size'] == 4,
         'INVENTORY_EXACT_CURRENT_MAP_SOURCE_REQUIRED')
    player_proof = documents['work/online_world_public_source/player-contract.json']
    player_checks = {r['rva']: r for r in player_proof['source_checks']}
    need(len(player_proof['source_checks']) == len(player_checks) == 23
         and set(player_checks) == set(PLAYER_ALLOCATION_INIT_RVAS + PLAYER_CURRENT_CHECK_RVAS),
         'INVENTORY_EXACT_CURRENT_PLAYER_SOURCE_REQUIRED')
    core_checks = ([player_checks[rva] for rva in PLAYER_CURRENT_CHECK_RVAS]
                   + [map_checks[rva] for rva in MAP_CURRENT_CHECK_RVAS])
    return proof, keys, core_checks


@dataclass(frozen=True, slots=True)
class ItemInfo:
    raw_fields: tuple = field(repr=False)

    @property
    def identifier(self):
        return dict(self.raw_fields)[1]

    @property
    def template_bits(self):
        return dict(self.raw_fields)[2] & 0xffffffff


def _values(fields, keys):
    need(type(fields) is dict and all(type(k) is int for k in fields)
         and fields.keys() == FIELD_TYPES.keys(), 'INVENTORY_EXPLICIT_RAW_FIELDS_REQUIRED')
    for n, kind in FIELD_TYPES.items():
        value = fields[n]
        if kind == 'bytes':
            need(type(value) is bytes and len(value) <= 256, 'INVENTORY_RAW_BYTES_REQUIRED')
        elif kind == 'bool':
            need(type(value) is bool, 'INVENTORY_CANONICAL_BOOL_REQUIRED')
        else:
            low, high = {'u32': (0, 1 << 32), 'u64': (0, 1 << 64),
                         'i32': (-(1 << 31), 1 << 31)}[kind]
            need(type(value) is int and low <= value < high, 'INVENTORY_RAW_SCALAR_RANGE')
    need(fields[1] != 0, 'INVENTORY_EXPLICIT_NONZERO_IDENTIFIER_POLICY')
    need((fields[2] & 0xffffffff) in keys, 'INVENTORY_TEMPLATE_NOT_IN_FIXED_CATALOG')
    return ItemInfo(tuple(sorted(fields.items())))


def _encode(item):
    encoded = []
    for n, value in item.raw_fields:
        if FIELD_TYPES[n] == 'bytes':
            encoded.append(pb.encode_bytes(n, value))
        else:
            encoded.append(pb.encode_varint(n << 3) + pb.encode_varint(int(value) & U64_MAX))
    child = b''.join(encoded)
    body = pb.encode_bytes(1, child) + pb.encode_bool(2, False)
    return struct.pack('<HH', len(body) + 6, OPCODE) + body + b'\0\0'


def build_add(fields):
    """All values are caller choices; no inferred defaults or starter item."""
    _, keys, _ = _source()
    return _encode(_values(fields, keys))


def validate_frame(wire):
    """Strict local one-row/explicit-false subset, not all ItemInfo schemas."""
    _, keys, _ = _source()
    return _validate_single_frame(wire, keys)


def _validate_single_frame(wire, keys):
    try:
        need(type(wire) is bytes and 6 <= len(wire) <= MAX_FRAME
             and int.from_bytes(wire[:2], 'little') == len(wire)
             and int.from_bytes(wire[2:4], 'little') == OPCODE and wire[-2:] == b'\0\0',
             'INVENTORY_FRAME_REQUIRED')
        limits = pb.WireLimits(max_body=MAX_FRAME, max_fields=32, max_field_bytes=512)
        with pb.parse_message(wire[4:-2], schema={1: 2, 2: 0}, limits=limits) as outer:
            need(len(outer.fields) == 2 and len(outer.occurrences(1)) == 1
                 and len(outer.occurrences(2)) == 1 and outer.occurrences(2)[0].value == 0,
                 'INVENTORY_ONE_ADD_EXPLICIT_FALSE_REQUIRED')
            with pb.parse_message(outer.occurrences(1)[0].value,
                    schema={n: 2 if t == 'bytes' else 0 for n, t in FIELD_TYPES.items()}, limits=limits) as inner:
                need(len(inner.fields) == len(FIELD_TYPES)
                     and len({r.number for r in inner.fields}) == len(inner.fields),
                     'INVENTORY_UNIQUE_EXPLICIT_FIELDS_REQUIRED')
                fields = {}
                for row in inner.fields:
                    kind, value = FIELD_TYPES[row.number], row.value
                    if kind == 'bytes':
                        value = bytes(value)
                    elif kind == 'bool':
                        need(value in (0, 1), 'INVENTORY_CANONICAL_BOOL_REQUIRED')
                        value = bool(value)
                    elif kind == 'i32' and value >= 1 << 31:
                        need(value >= 0xffffffff80000000, 'INVENTORY_SIGNEXTENDED_I32_REQUIRED')
                        value -= 1 << 64
                    fields[row.number] = value
                item = _values(fields, keys)
        need(_encode(item) == wire, 'INVENTORY_CANONICAL_FRAME_REQUIRED')
        return item
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('MALFORMED_INVENTORY_ADD_SUBSET') from None


_REFUSED_READ_FIELDS = ('state', 'protection', 'type', 'guard', 'length_fits',
    'image_allocation_matches', 'requested_bytes', 'at', 'size', 'image_base')


class PreWriteReadRefusal(ValueError):
    """Exact physical unreadability; optional frozen request facts grant no authority."""
    def __init__(self, reason, stage):
        need(reason == 'region_not_readable' and type(stage) is str
             and re.fullmatch(r'(?:SOURCE_BEFORE|AUTHORITY_BEFORE|WORLD_TYPED|INVENTORY_TYPED|'
                              r'EMPTY_VECTOR|FINAL_READBACK|ROOT_RECHECK|SOURCE_AFTER|AUTHORITY_AFTER|'
                              r'CODE_GUARD_(?:BEFORE|AFTER)_[0-9]{4})', stage),
             'INVENTORY_READ_REFUSAL_METADATA_REQUIRED')
        self.reason, self.stage, self._refused_read = reason, stage, None
        super().__init__(reason)

    @property
    def refused_read(self):
        return None if self._refused_read is None else dict(zip(_REFUSED_READ_FIELDS, self._refused_read))


class ReadOnlyPreWriteRefusal(ValueError):
    """A source-owned, unclaimed restore-only attempt; constructor is no proof."""
    def __init__(self, stage):
        need(type(stage) is str and stage in ('WORLD_TYPED', 'INVENTORY_TYPED',
             'EMPTY_VECTOR', 'FINAL_READBACK'), 'INVENTORY_READONLY_REFUSAL_STAGE_REQUIRED')
        self.reason, self.stage = 'EDGE_TYPED_READ_CHANGED', stage
        super().__init__(self.reason)


class _PhysicalBufferChanged(ValueError):
    """Private control flow after an actual full physical buffer comparison."""


class _PhysicalReadBoundary:
    """Forward the already validated original Native.read without mutation."""
    def __init__(self, native, service):
        self._read, self._service = native.read, service
        self._unknown = self._read.__func__.__globals__['Unknown']

    def read(self, at, size, image_base=None):
        try:
            raw = self._read(at, size, image_base)
        except Exception as error:
            if type(error) is self._unknown and error.reason == 'region_not_readable':
                refusal = PreWriteReadRefusal(error.reason, self._service.last_pre_write_stage)
                region = getattr(error, 'region', None)
                # These are only the failed call's existing inputs/VirtualQueryEx
                # result. Never read mutable native.last_region after this call.
                if (type(region) is dict and all(type(k) is str for k in region)
                        and set(region) == set(_REFUSED_READ_FIELDS[:7])
                        and type(at) is int and type(size) is int and 0 < size <= 4096
                        and 0x10000 <= at <= 0x7fffffffffff - size
                        and (image_base is None or type(image_base) is int
                             and 0x10000 <= image_base <= 0x7fffffffffff)
                        and all(type(region[k]) is int and 0 <= region[k] <= 0xffffffff
                                for k in ('state', 'protection', 'type'))
                        and all(type(region[k]) is bool for k in ('guard', 'length_fits'))
                        and (region['image_allocation_matches'] is None if image_base is None
                             else type(region['image_allocation_matches']) is bool)
                        and type(region['requested_bytes']) is int and region['requested_bytes'] == size):
                    refusal._refused_read = tuple(region[k] for k in _REFUSED_READ_FIELDS[:7]) + (at, size, image_base)
                raise refusal from None
            raise
        self._budget.physical_result(at, size, image_base is not None, raw)
        return raw


class _ReadBudget(edge._Budget):
    def __init__(self, native, sampler, service):
        super().__init__(_PhysicalReadBoundary(native, service), sampler)
        self.native._budget = self
        self._service, self._stage, self._ordinal = service, None, 0
        self.read_phase, self.request_count, self.changed_read = 'INITIAL', 0, None
        self._physical_change, self._change_error = None, None

    def physical_result(self, at, size, image, raw):
        expected = self._retained.get((at, size, image))
        if ((self.retain or self.read_phase == 'BUDGET_READBACK')
                and type(raw) is bytes and len(raw) == size
                and expected is not None and raw != expected):
            self._physical_change = (at, size, image, expected, raw)

    def _raise_change(self):
        at, size, image, _, _ = self._physical_change
        self._changed(at, size, image)
        self._change_error = _PhysicalBufferChanged('EDGE_TYPED_READ_CHANGED')
        raise self._change_error

    def stage(self, value):
        self._stage, self._ordinal = value, 0
        self._service.last_pre_write_stage = value

    def read(self, at, size, image=False):
        self.request_count += 1
        need(type(size) is int and self.spent + size <= BYTE_LIMIT, 'INVENTORY_BYTE_BUDGET')
        if self._stage in ('CODE_GUARD_BEFORE', 'CODE_GUARD_AFTER'):
            self._ordinal += 1
            self._service.last_pre_write_stage = f'{self._stage}_{self._ordinal:04d}'
        # Metadata uses only this original physical read and already retained
        # records. No addresses, bytes, additional reads or relaxed comparison.
        self._physical_change = None
        try:
            raw = super().read(at, size, image)
        except ValueError as error:
            if self._physical_change is not None:
                self._raise_change()
            if str(error) == 'EDGE_TYPED_READ_CHANGED':
                self._changed(at, size, image)
            raise
        if self._physical_change is not None:
            # The inherited verify's exact comparison would reject this same
            # physical buffer. A structural witness preserves that refusal.
            self._raise_change()
        return raw

    def _changed(self, at, size, image):
        if self.changed_read is None:
            ordinal = next((n for n, (saved_at, saved, saved_image) in enumerate(self.records, 1)
                            if (saved_at, len(saved), saved_image) == (at, size, image)), None)
            self.changed_read = dict(stage=self._service.last_pre_write_stage,
                comparison=self.read_phase, request_ordinal=self.request_count,
                record_ordinal=ordinal, record_count=len(self.records),
                requested_width=size, typed_bytes_requested=self.spent, image=image)


class InventoryService:
    """NPC-independent actual authority, no cached ready receipt or sender.

    validate_pre_write_locked consumes this service's single send admission.
    Even ambiguous write/drain failure never permits another admission.
    Caller already holds the real row operation_lock and completed its native
    checkpoint. No await may intervene between this leaf and writer.write.
    """
    def __init__(self, broker, reader, *, policy, store=None, collection_policy=None):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker and type(reader) is observe.RetainedSceneReader,
             'INVENTORY_REAL_BROKER_READER_REQUIRED')
        need(policy == POLICY, 'INVENTORY_EXPLICIT_POLICY_REQUIRED')
        _source()
        self.broker, self.reader, self.policy = broker, reader, policy
        self._reader, self._backend = reader, reader.backend
        self._intro_image = getattr(reader, 'image', None)
        self._intro_snapshot = _freeze_static(_reader_intro(reader, _source_documents()))
        if store is not None:
            from tools.local_original_session.inventory_store import InventoryStore
            need(type(store) is InventoryStore, 'INVENTORY_EXACT_STORE_REQUIRED')
        self.store = store
        need(collection_policy is None or type(collection_policy) is str and
             collection_policy == COLLECTION_POLICY and store is not None and
             getattr(broker, '_inventory_collection_policy', None) == collection_policy,
             'INVENTORY_SERVICE_EXPLICIT_COLLECTION_POLICY_REQUIRED')
        self._collection_policy = collection_policy
        self._collection_grant = (getattr(broker, '_inventory_collection_grant', None)
                                  if collection_policy is not None else None)
        self._store_bound = (store, store.profile, str(store.profile), store.path, str(store.path)) if store is not None else None
        self._persistence_store()
        self.proof = edge.EdgeAdapter(reader)
        self._last_ns, self._inflight, self._claimed, self._closed = None, False, False, False
        self._readonly_refusal = None
        self.last_pre_write_stage = 'SOURCE_BEFORE'
        self.last_result = dict(status='UNKNOWN', reason='NOT_SAMPLED', typed_bytes_requested=0)

    def _items_frame(self, frame):
        need(getattr(self.broker, '_inventory_collection_policy', None) == self._collection_policy
             and getattr(self.broker, '_inventory_collection_grant', None) is self._collection_grant,
             'INVENTORY_COLLECTION_CONFIGURATION_CHANGED')
        if self._collection_policy is None:
            return (validate_frame(frame),)
        need(type(self._collection_policy) is str and self._collection_policy == COLLECTION_POLICY,
             'INVENTORY_COLLECTION_EXPLICIT_POLICY_REQUIRED')
        return validate_collection_frame(frame, policy=self._collection_policy)

    def _persistence_store(self):
        bound = self._store_bound
        if bound is None:
            need(self.store is None, 'INVENTORY_STORE_BINDING_CHANGED')
            return None
        from tools.local_original_session.inventory_store import InventoryStore
        store, profile, profile_value, path, path_value = bound
        need(type(store) is InventoryStore and self.store is store
             and store.profile is profile and str(store.profile) == profile_value
             and store.path is path and str(store.path) == path_value
             and store.profile == self.broker.realm.store.path
             and store.path == store.profile.with_name('inventory.json'),
             'INVENTORY_STORE_BINDING_CHANGED')
        grant = store.grant
        need(getattr(grant, '__self__', None) is store
             and getattr(grant, '__func__', None) is InventoryStore.grant,
             'INVENTORY_ORIGINAL_STORE_GRANT_REQUIRED')
        need(getattr(self.broker, '_inventory_collection_policy', None) == self._collection_policy
             and getattr(self.broker, '_inventory_collection_grant', None) is self._collection_grant,
             'INVENTORY_COLLECTION_CONFIGURATION_CHANGED')
        if self._collection_policy is not None:
            from tools.local_original_session.inventory_store import COLLECTION_STORE_POLICY
            method = store.verify_existing_collection
            need(self._collection_policy == COLLECTION_POLICY and store._collection_policy == COLLECTION_STORE_POLICY
                 and method.__self__ is store and method.__func__ is InventoryStore.verify_existing_collection,
                 'INVENTORY_COLLECTION_ORIGINAL_READONLY_STORE_REQUIRED')
        return store

    def _persistence_operation(self, writer, row, actualframe, bound):
        need(self._store_bound is bound, 'INVENTORY_STORE_BINDING_CHANGED')
        store = self._persistence_store()
        broker = self.broker
        need(store is not None and self._inflight and not self._claimed
             and broker._inventory_service is self
             and broker._inventory_attempted is True and broker._inventory_write_attempted is False
             and broker._inventory_delivery_authority is None
             and broker._inventory_frame is actualframe
             and broker._inventory_operation_frame is actualframe
             and row['writer'] is writer and row['operation_lock'].locked(),
             'INVENTORY_DURABLE_ONCE_OPERATION_REQUIRED')
        return store

    def _restore_mode(self, writer, row, actualframe, expected):
        mode = self.broker._inventory_restore_only
        need(type(mode) is bool and mode is expected, 'INVENTORY_RESTORE_MODE_CHANGED')
        if mode:
            from tools.local_original_session.broker import PersistentBroker
            need(self._store_bound is not None, 'INVENTORY_RESTORE_STORE_REQUIRED')
            need(type(self.broker) is PersistentBroker
                 and self.broker._inventory_store is self._persistence_store()
                 and self.broker._inventory_restored is True,
                 'INVENTORY_RESTORE_SELECTED_STORE_REQUIRED')
            current = self.broker._inventory_selection_frame_current
            need(getattr(current, '__self__', None) is self.broker
                 and getattr(current, '__func__', None) is PersistentBroker._inventory_selection_frame_current,
                 'INVENTORY_ORIGINAL_SELECTION_FRAME_CHECK_REQUIRED')
            current(writer, row, actualframe)

    def _current(self, writer, row):
        return self._authority(writer, row)

    def _authority(self, writer, row, *, refusal=None):
        from tools.local_original_session.broker import LocalRealm, _TransportPolicy
        reporting = refusal is not None
        if reporting:
            need(refusal is self._readonly_refusal and refusal[2] is self.last_result
                 and refusal[3] is writer and refusal[4] is row,
                 'INVENTORY_READONLY_REFUSAL_PROOF_REQUIRED')
        broker, reader = self.broker, self.reader
        self._persistence_store()
        need(reader is self._reader and reader.backend is self._backend and not reader.closed,
             'INVENTORY_SAME_RETAINED_READER_REQUIRED')
        policy, owner, member = broker.policy, reader.owner, reader.member
        need(type(policy) is _TransportPolicy and owner is not None and not owner.closed
             and policy.owner is owner and member is owner.child and member is not None
             and policy.handle is owner.owner_handle and policy.job is owner.owner_job
             and member.process == owner.owner_handle and member.job == owner.owner_job,
             'INVENTORY_SAME_RETAINED_OWNER_REQUIRED')
        need((not self._closed or reporting) and not broker._closing and not broker.failure.is_set()
             and policy.state == 'OPEN', 'INVENTORY_LIFETIME_REQUIRED')
        matches = [r for rows in broker._claims.values() for r in rows if r['writer'] is writer]
        need(len(matches) == 1 and matches[0] is row, 'INVENTORY_CURRENT_CLAIM_REQUIRED')
        admitted = policy._connection(writer)
        need(row['policy_row'] is admitted and admitted.writer is writer
             and admitted.stage == 1 and admitted.rx_boot == 2 and admitted.tx_boot == 3
             and not any((row['failed'], row['joined'], admitted.failed, admitted.eof,
                          admitted.task_joined, admitted.registry_removed))
             and (row['operation_lock'].locked() or reporting), 'INVENTORY_CURRENT_LOCKED_ADMISSION_REQUIRED')
        realm = broker.realm
        need(type(realm) is LocalRealm, 'INVENTORY_REAL_REALM_REQUIRED')
        registry = realm.registry
        game = registry.resolve(writer)
        need(game.registry is registry, 'INVENTORY_SAME_REGISTERED_SESSION_REQUIRED')
        realm.bound_account(writer, game)
        service = realm.service(writer)
        position, selected = service.snapshot(), game.selection
        movement_row = realm._movement.get(id(writer))
        need(type(movement_row) is tuple and len(movement_row) == 3
             and movement_row[0] is writer and movement_row[1] is service
             and movement_row[2] == row['peer']['connection_id'],
             'INVENTORY_SAME_SELECTED_CONNECTION_REQUIRED')
        need(type(service) is movement.MovementService and type(position) is movement.Position
             and service._connection is writer and not service.fatal and not realm._settings_failed
             and id(writer) not in realm._quit and selected is not None
             and registry.selected.get(position.name) is selected
             and selected.reference == position.name == realm.profile_name
             and position.uid == realm.profile_uid and position.map_id == 0,
             'INVENTORY_CURRENT_SELECTED_AUTHORITY_REQUIRED')
        saved_uid, _ = realm.store.select(selected.reference)
        need(saved_uid == position.uid and realm.positions.restore(position) == position,
             'INVENTORY_CURRENT_SELECTED_STORAGE_REQUIRED')
        identities = (broker, reader, reader.backend, reader.owner, member, policy,
                      policy.handle, policy.job, owner.owner_handle, owner.owner_job,
                      realm, registry, game, service, position, selected, row, admitted,
                      row['operation_lock'], row['peer'], broker.failure, realm.store, realm.positions,
                      movement_row)
        values = (tuple(sorted(row['peer'].items())), reader.backend.handle,
                  member.pid, tuple(sorted(member.identity.items())))
        return position, identities, values

    def validate_readonly_refusal(self, error, writer, row, frame, *, admission=True):
        """Validate the current source-owned refusal; False only permits reporting."""
        need(type(admission) is bool, 'INVENTORY_READONLY_REFUSAL_MODE_REQUIRED')
        evidence = self._readonly_refusal
        need(type(evidence) is tuple and len(evidence) == 12 and type(error) is ReadOnlyPreWriteRefusal
             and type(error.reason) is str and type(error.stage) is str
             and evidence[0] is error and evidence[2] is self.last_result
             and evidence[3] is writer and evidence[4] is row and evidence[5] is frame,
             'INVENTORY_READONLY_REFUSAL_PROOF_REQUIRED')
        _, budget, result, _, _, _, mode, before, proof, retained, store_bound, origin = evidence
        native, sampler, handle = retained
        change = budget._physical_change
        need(type(budget) is _ReadBudget and type(budget.native) is _PhysicalReadBoundary
             and budget._service is self and budget.native._service is self
             and budget.native._budget is budget and budget.sampler is sampler
             and budget.native._read.__self__ is native and change is not None
             and budget._change_error is origin
             and type(budget._change_error) is _PhysicalBufferChanged
             and change[2] is False
             and type(change[3]) is bytes and type(change[4]) is bytes
             and len(change[3]) == len(change[4]) == change[1]
             and budget._retained.get(change[:3]) is change[3] and change[3] != change[4]
             and result['status'] == 'UNKNOWN' and result['reason'] == error.reason
             and error.reason == 'EDGE_TYPED_READ_CHANGED'
             and error.stage == budget._stage == self.last_pre_write_stage,
             'INVENTORY_READONLY_REFUSAL_PROOF_REQUIRED')
        broker = self.broker
        admitted = row['policy_row']
        need(mode is True and broker._inventory_restore_only is mode
             and broker._inventory_frame is frame and broker._inventory_operation_frame is frame
             and not self._claimed and broker._inventory_service is self
             and broker._inventory_attempted is True and broker._inventory_write_attempted is False
             and broker._inventory_delivery_authority is None
             and admitted.drain_started_ns is None and admitted.pending_opcode is None
             and admitted.pending_size == 0,
             'INVENTORY_READONLY_REFUSAL_NOT_PREWRITE')
        if admission:
            need(not self._closed and not broker._inventory_admission_expired,
                 'INVENTORY_READONLY_REFUSAL_TERMINAL')
        need(self.proof is proof and proof.reader is self.reader
             and self._store_bound is store_bound and store_bound is not None
             and proof._binding() == retained[:2] and native.handle == handle,
             'INVENTORY_READONLY_REFUSAL_BINDING_CHANGED')
        self._same(before, self._authority(writer, row, refusal=evidence))
        self._restore_mode(writer, row, frame, mode)
        _source()
        self._cancelled()
        self._restore_mode(writer, row, frame, mode)
        return True

    @staticmethod
    def _same(before, after):
        need(len(before[1]) == len(after[1]) and all(a is b for a, b in zip(before[1], after[1]))
             and before[2] == after[2], 'INVENTORY_AUTHORITY_CHANGED')

    def _checks(self, sampler, contract, core_checks):
        # Native function bodies are source/layout provenance for this passive
        # query. Actual table/data reads below retain the original Native gate.
        documents = _source_documents()
        intro = documents[INTRO_PROOF]
        need(_same_static(contract, documents[PROOF])
             and _same_static(self.proof.public, documents[PUBLIC_PROOF])
             and _same_static(self.proof.position_source, documents[WORLD_PROOF])
             and self.reader.image is self._intro_image
             and _freeze_static(sampler.c) == self._intro_snapshot
             and _same_static(sampler.image_checks,
                 [(r['rva'], bytes.fromhex(r['bytes_hex'])) for r in intro['checks']]),
             'INVENTORY_PASSIVE_SOURCE_CACHE_CHANGED')
        checks = list(core_checks)
        checks += self.proof.public['Position']['source_checks']
        checks += [dict(rva=rva, length=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                   for rva, raw in sampler.image_checks if 0xd3b00 <= rva < 0xd3c00]
        return list({(c['rva'], c['length'], c['sha256']): c for c in checks}.values())

    def validate_pre_write_locked(self, writer, row, actualframe, *, now_ns):
        budget = None
        persist_started = False
        readonly_grant_completed = False
        collection_granted = False
        store_bound = self._store_bound
        self.last_result = dict(status='UNKNOWN', reason='NOT_SAMPLED', typed_bytes_requested=0,
            typed_byte_limit=BYTE_LIMIT, visible_screen_claimed=False, snapshot_atomic=False,
            catalog_static_key_verified=False, catalog_live_materialization_proven=False,
            refused_read=None)
        need(not self._inflight and not self._claimed, 'INVENTORY_ONE_SEND_ONLY')
        need(type(now_ns) is int and 0 <= now_ns < (1 << 63)
             and (self._last_ns is None or now_ns - self._last_ns >= MIN_INTERVAL_NS),
             'INVENTORY_CALLER_CADENCE_REQUIRED')
        self._last_ns, self._inflight = now_ns, True
        self._readonly_refusal = None
        try:
            self.last_pre_write_stage = 'SOURCE_BEFORE'
            restore_only = self.broker._inventory_restore_only
            self._restore_mode(writer, row, actualframe, restore_only)
            self._cancelled()
            if self._collection_policy is None:
                items = self._items_frame(actualframe)
                contract, _, core_checks = _source()
            else:
                need(getattr(self.broker, '_inventory_collection_policy', None) == self._collection_policy
                     and getattr(self.broker, '_inventory_collection_grant', None) is self._collection_grant,
                     'INVENTORY_COLLECTION_CONFIGURATION_CHANGED')
                contract, collection_keys, core_checks = _source()
                items = _validate_collection_frame(actualframe, self._collection_policy, collection_keys)
            self.last_pre_write_stage = 'AUTHORITY_BEFORE'
            before = self._current(writer, row)
            proof, reader = self.proof, self.reader
            need(proof.reader is reader, 'INVENTORY_SAME_PROOF_READER_REQUIRED')
            native, sampler = proof._binding()
            need(native is reader.backend and sampler is reader.sampler,
                 'INVENTORY_SAME_PROOF_BACKEND_REQUIRED')
            self._same(before, self._current(writer, row))
            need(self._store_bound is store_bound, 'INVENTORY_STORE_BINDING_CHANGED')
            retained = (native, sampler, native.handle)
            budget = _ReadBudget(native, sampler, self)
            self._checks(sampler, contract, core_checks)
            with budget.installed():
                position = before[0]
                budget.stage('WORLD_TYPED')
                reads, _, _, route, state, scene_raw, _ = edge._world(native, sampler,
                    proof.public, proof.world, proof.position_source, position.uid, position.map_id,
                    (position.word0, position.word1), require_current_start=False)
                budget.stage('INVENTORY_TYPED')
                owner_table = contract['owners']['Inventory']
                matches = [reads.pair(pair)[0] for pair, vft in route[-2]
                           if vft == sampler.g['base'] + owner_table['rva']]
                need(len(matches) == 1, 'INVENTORY_UNIQUE_REGISTERED_OWNER_REQUIRED')
                owner, = matches
                need(reads.pointer(owner) == sampler.g['base'] + owner_table['rva'],
                     'INVENTORY_OWNER_TYPE_CHANGED')
                proof.world.table(sampler, owner_table)
                layout = contract['inventory']
                budget.stage('EMPTY_VECTOR')
                begin, end, capacity = struct.unpack('<QQQ', reads.read(owner + layout['begin'], 24))
                need(begin == end == capacity == 0 or
                     (0x10000 <= begin <= end <= capacity <= 0x7fffffffffff
                      and (begin | end | capacity) % 8 == 0
                      and (end - begin) % 16 == 0 and (capacity - begin) % 16 == 0),
                     'INVENTORY_CANONICAL_VECTOR_REQUIRED')
                need(begin == end, 'INVENTORY_EMPTY_ONLY_LOCAL_POLICY')
                if store_bound is not None:
                    self._same(before, self._current(writer, row))
                    self._cancelled()
                    store = self._persistence_operation(writer, row, actualframe, store_bound)
                    self._restore_mode(writer, row, actualframe, restore_only)
                    persist_started = True
                    if self._collection_policy is not None:
                        from tools.local_original_session.broker import PersistentBroker
                        method = self.broker._inventory_collection_before_write_locked
                        need(method.__self__ is self.broker and
                             method.__func__ is PersistentBroker._inventory_collection_before_write_locked,
                             'INVENTORY_COLLECTION_ORIGINAL_ADOPTION_REQUIRED')
                        original = actualframe
                        actualframe = method(writer, row, self, actualframe, items)
                        collection_granted = actualframe is not original
                        need(getattr(self.broker, '_inventory_collection_policy', None) == self._collection_policy
                             and getattr(self.broker, '_inventory_collection_grant', None) is self._collection_grant,
                             'INVENTORY_COLLECTION_CONFIGURATION_CHANGED')
                        items = _validate_collection_frame(actualframe, self._collection_policy, collection_keys)
                        self._restore_mode(writer, row, actualframe, restore_only)
                        need(restore_only is True and store.verify_existing_collection(before[0].uid,
                             actualframe, policy=COLLECTION_POLICY) is False,
                             'INVENTORY_COLLECTION_READONLY_RESULT_REQUIRED')
                        readonly_grant_completed = True
                    elif restore_only:
                        need(store.grant(before[0].uid, actualframe, existing_only=True) is False,
                             'INVENTORY_READONLY_GRANT_RESULT_REQUIRED')
                        readonly_grant_completed = True
                    else:
                        store.grant(before[0].uid, actualframe)
                    self._persistence_operation(writer, row, actualframe, store_bound)
                    self._restore_mode(writer, row, actualframe, restore_only)
                budget.stage('FINAL_READBACK')
                budget.read_phase = 'WORLD_READBACK'
                reads.verify()
                budget.read_phase = 'BUDGET_READBACK'
                budget.verify()
                budget.read_phase = 'INITIAL'
                budget.retain = False
                try:
                    budget.stage('ROOT_RECHECK')
                    need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                         'INVENTORY_WORLD_OWNER_CHANGED')
                finally:
                    budget.retain = True
            self.last_pre_write_stage = 'AUTHORITY_AFTER'
            need(proof._binding() == retained[:2] and native.handle == retained[2],
                 'INVENTORY_RETAINED_BINDING_CHANGED')
            self._same(before, self._current(writer, row))
            need(self._store_bound is store_bound, 'INVENTORY_STORE_BINDING_CHANGED')
            if store_bound is not None:
                need(self.proof is proof, 'INVENTORY_SAME_PROOF_REQUIRED')
                self._persistence_operation(writer, row, actualframe, store_bound)
            self.last_pre_write_stage = 'SOURCE_AFTER'
            contract, _, core_checks = _source()
            self._checks(sampler, contract, core_checks)
            self._cancelled()
            self._restore_mode(writer, row, actualframe, restore_only)
            self._claimed = True
            self.last_result.update(status='OBSERVED', reason=None,
                selected_uid=before[0].uid, map_id=before[0].map_id,
                inventory_empty=True, source_contract_valid=True, stable_double_read=True,
                identifier=items[0].identifier if len(items) == 1 else None, catalog_static_key_verified=True)
            if self._collection_policy is not None:
                self.last_result['identifiers'] = tuple(item.identifier for item in items)
                return actualframe
        except asyncio.CancelledError:
            self._closed = True
            self.last_result['reason'] = 'INVENTORY_CALLER_CANCELLED'
            raise
        except _PhysicalBufferChanged as origin:
            self.last_result['reason'] = 'EDGE_TYPED_READ_CHANGED'
            if collection_granted or restore_only is not True or budget._physical_change[2] is not False:
                if persist_started or restore_only is True:
                    self._closed = True
                raise ValueError('EDGE_TYPED_READ_CHANGED') from None
            try:
                need(budget is not None and budget._change_error is origin
                     and (not persist_started or readonly_grant_completed),
                     'INVENTORY_READONLY_REFUSAL_PROOF_REQUIRED')
                refusal = ReadOnlyPreWriteRefusal(self.last_pre_write_stage)
                self._readonly_refusal = (refusal, budget, self.last_result, writer, row,
                    actualframe, restore_only, before, proof, retained, store_bound, origin)
                self.validate_readonly_refusal(refusal, writer, row, actualframe)
            except BaseException as error:
                self._closed = True
                self._readonly_refusal = None
                self.last_result['reason'] = ('INVENTORY_CALLER_CANCELLED'
                    if isinstance(error, asyncio.CancelledError) else observe.reason(error))
                if isinstance(error, asyncio.CancelledError):
                    raise
                raise ValueError(self.last_result['reason']) from None
            raise refusal from None
        except PreWriteReadRefusal as error:
            if persist_started:
                self._closed = True
            self.last_result['reason'] = error.reason
            self.last_result['refused_read'] = error.refused_read
            raise
        except Exception as error:
            if persist_started:
                self._closed = True
            self.last_result['reason'] = observe.reason(error)
            raise ValueError(self.last_result['reason']) from None
        finally:
            self._inflight = False
            self.last_result['typed_bytes_requested'] = 0 if budget is None else budget.spent
            self.last_result['pre_write_stage'] = self.last_pre_write_stage
            self.last_result['typed_read_requests'] = 0 if budget is None else budget.request_count
            self.last_result['changed_read'] = None if budget is None else budget.changed_read

    def close(self):
        self._closed = True

    @staticmethod
    def _cancelled():
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()


# Explicit collection-only addition; original singleton codec is unchanged.
COLLECTION_POLICY = 'EXPLICIT_ONE_OR_TWO_ITEM_ADD_COLLECTION'


def _collection_items(items, policy, keys):
    need(type(policy) is str and policy == COLLECTION_POLICY,
         'INVENTORY_COLLECTION_EXPLICIT_POLICY_REQUIRED')
    need(type(items) is tuple and 1 <= len(items) <= 2,
         'INVENTORY_COLLECTION_ONE_OR_TWO_REQUIRED')
    validated = []
    for item in items:
        need(type(item) is ItemInfo, 'INVENTORY_COLLECTION_REAL_ITEM_REQUIRED')
        need(type(item.raw_fields) is tuple, 'INVENTORY_COLLECTION_CANONICAL_ITEM_REQUIRED')
        checked = _values(dict(item.raw_fields), keys)
        need(_same_static(checked.raw_fields, item.raw_fields),
             'INVENTORY_COLLECTION_CANONICAL_ITEM_REQUIRED')
        # Reuse the unchanged complete singleton validator/catalog/17 fields.
        canonical = _validate_single_frame(_encode(checked), keys)
        need(_same_static(canonical.raw_fields, item.raw_fields),
             'INVENTORY_COLLECTION_CANONICAL_ITEM_REQUIRED')
        validated.append(canonical)
    need(len({item.identifier for item in validated}) == len(validated),
         'INVENTORY_COLLECTION_DUPLICATE_ITEM_UID')
    return tuple(validated)


def _encode_collection(items):
    children = []
    for item in items:
        single = _encode(item)
        with pb.parse_message(single[4:-2], schema={1: 2, 2: 0}) as message:
            children.append(pb.encode_bytes(1, bytes(message.occurrences(1)[0].value)))
    body = b''.join(children) + pb.encode_bool(2, False)
    wire = struct.pack('<HH', len(body) + 6, OPCODE) + body + b'\0\0'
    need(len(wire) <= MAX_FRAME, 'INVENTORY_COLLECTION_FRAME_SIZE')
    return wire


def build_collection_add(items, *, policy):
    """One source-confirmed repeated0964 frame; no UID allocation or authority."""
    _, keys, _ = _source()
    return _encode_collection(_collection_items(items, policy, keys))


def validate_collection_frame(wire, *, policy):
    """Explicit 1..2-item subset. Does not relax validate_frame's singleton API."""
    need(type(policy) is str and policy == COLLECTION_POLICY,
         'INVENTORY_COLLECTION_EXPLICIT_POLICY_REQUIRED')
    _, keys, _ = _source()
    return _validate_collection_frame(wire, policy, keys)


def _validate_collection_frame(wire, policy, keys):
    need(type(policy) is str and policy == COLLECTION_POLICY,
         'INVENTORY_COLLECTION_EXPLICIT_POLICY_REQUIRED')
    try:
        need(type(wire) is bytes and 6 <= len(wire) <= MAX_FRAME
             and int.from_bytes(wire[:2], 'little') == len(wire)
             and int.from_bytes(wire[2:4], 'little') == OPCODE and wire[-2:] == b'\0\0',
             'INVENTORY_COLLECTION_FRAME_REQUIRED')
        limits = pb.WireLimits(max_body=MAX_FRAME, max_fields=3, max_field_bytes=512)
        with pb.parse_message(wire[4:-2], schema={1: 2, 2: 0}, limits=limits) as outer:
            children, flags = outer.occurrences(1), outer.occurrences(2)
            need(1 <= len(children) <= 2 and len(flags) == 1 and flags[0].value == 0
                 and len(outer.fields) == len(children) + 1,
                 'INVENTORY_COLLECTION_EXPLICIT_FALSE_REQUIRED')
            items = []
            for child in children:
                body = pb.encode_bytes(1, bytes(child.value)) + pb.encode_bool(2, False)
                single = struct.pack('<HH', len(body) + 6, OPCODE) + body + b'\0\0'
                items.append(_validate_single_frame(single, keys))
        result = _collection_items(tuple(items), policy, keys)
        need(_encode_collection(result) == wire, 'INVENTORY_COLLECTION_CANONICAL_FRAME_REQUIRED')
        return result
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('MALFORMED_INVENTORY_COLLECTION_SUBSET') from None
