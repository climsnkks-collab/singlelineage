"""Pure unit coverage; no game, socket, save or formal gameplay PASS."""
import asyncio
import csv
import json
from dataclasses import replace
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, inventory_update, world_feature_iteminfo as feature
from tools.local_original_session import world_feature_kit, world_handlers, world_visibility
from tools.local_original_session.world_entities import EntityRef
from tools.local_original_session.world_ground_items import GroundItem


def item(uid=10, template=1, name=b'', count=3):
    return inventory.ItemInfo(((1, uid), (2, template), (4, count), (18, name)))


def update_fields(frame):
    if int.from_bytes(frame[2:4], 'little') == feature.CHANGE_DESC:
        with pb.parse_message(frame[4:-2]) as parsed:
            return {1: parsed.occurrences(1)[0].value,
                    18: bytes(parsed.occurrences(2)[0].value),
                    4: parsed.occurrences(4)[0].value}
    with pb.parse_message(frame[4:-2]) as outer:
        with pb.parse_message(outer.occurrences(1)[0].value) as inner:
            return {r.number: bytes(r.value) if r.wire_type == 2 else r.value for r in inner.fields}


class DisplayTests(unittest.TestCase):
    def test_plain_sale_accepts_canonical_and_legacy_empty_names_only(self):
        fields = world_handlers._starter_fields()
        fields[2] = 3
        policy = world_handlers.KitItemPolicy(3, 1000, False, fields)
        policies = {3: policy}
        def add(rows, *, replace_existing):
            self.assertTrue(replace_existing)
            policies.update((row.template_id, row) for row in rows)
        ctx = NS(world=NS(data=NS(items={})), item_policies=policies,
                 _iteminfo_names={3: b'canonical'}, add_item_policies=add)
        feature._iteminfo_started(ctx)
        feature._iteminfo_started(ctx)
        self.assertEqual(policies[3].grant_fields[18], b'canonical')
        sale_ctx = NS(bindings=NS(item_policies=policies), pc_uid=1,
                      broker=NS(_item_equipment_effect=None))
        for name, changed, expected in ((b'', {}, 0), (b'canonical', {}, 0),
                (b'custom', {}, 128), (b'+1 canonical', {}, 128),
                (b'canonical', {5: fields[5] + 1}, 128)):
            row = inventory.validate_kit_frame(inventory.build_kit_frame([
                {**fields, 18: name, **changed}]))[0]
            sale = world_handlers._default_sale_item(sale_ctx, row)
            self.assertEqual(sale.l1j_bless, expected)
            self.assertTrue(sale.equipped)  # Unknown equipment remains ineligible.

    def test_catalog_names_use_client_desc(self):
        root = Path(__file__).resolve().parents[2]
        with (root / 'work/source_game_data/raw/desc.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = {int(r['ID']): r['KR'] for r in csv.DictReader(stream)}
        names = world_visibility.item_names()
        for template, desc_id in ((1, 14), (2, 16), (3, 5), (4, 1)):
            self.assertEqual(names[template], rows[desc_id].encode('utf-8'))
        self.assertNotIn(0x7FFFFFFF, names)

    def test_ground_name_and_existing_required_fields(self):
        ground = GroundItem(EntityRef(500, 1), EntityRef(501, 2), 1, 3, 1, False, 0, 100, 101, 0, 10, 600)
        # All static inputs are loaded before publication, so forbid a file read.
        world_visibility.item_names()
        world_visibility.item_gfx()
        with patch.object(Path, 'read_text', side_effect=AssertionError('request file read')):
            frame = world_visibility.ground_frame(ground)
        self.assertEqual(struct.unpack_from('<H', frame, 2)[0], 0x4E96)
        with pb.parse_message(frame[4:-2]) as parsed:
            numbers = [r.number for r in parsed.fields]
            self.assertEqual(len(numbers), len(set(numbers)))
            self.assertTrue(set(range(1, 25)) | {27, 28} <= set(numbers))
            # A stack of 3 shows its quantity first: "3 <name>".
            self.assertEqual(bytes(parsed.occurrences(9)[0].value), b'3 ' + world_visibility.item_names()[1])
            self.assertEqual(parsed.occurrences(7)[0].value, 3)

    def test_patch_only_missing_names_and_keep_custom_grade(self):
        custom = '[축복] 갑옷 마법 주문서'.encode()
        frames, current = feature.name_updates((item(), item(11, 25, custom)), {1: b'name', 25: b'plain'}, {})
        self.assertEqual(len(frames), 2)
        self.assertEqual(update_fields(frames[0]), {1: 10, 18: b'name (3)', 4: 3})
        self.assertEqual(update_fields(frames[1])[18], custom + b' (3)')
        self.assertEqual(current[11], (custom, 3, ()))

    def test_quantity_update_does_not_clear_display_name(self):
        # Mirror the source callback's presence semantics, not a rendered UI.
        frame, = feature.name_updates((item(),), {1: b'name'}, {})[0]
        client_row = update_fields(frame)
        quantity = inventory_update._encode(inventory_update._values({1: 10, 4: 2}))
        client_row.update(update_fields(quantity))
        self.assertEqual(client_row, {1: 10, 4: 2, 18: b'name (3)'})
        frames, _ = feature.name_updates((item(count=2),), {1: b'name'}, {10: (b'name', 2, ())})
        self.assertEqual(frames, ())

    def test_description_notice_exact_schema(self):
        frame = feature.description_notice(10, b'name', 3, ((1321, b'2'),))
        self.assertEqual(int.from_bytes(frame[2:4], 'little'), 0x0977)
        with pb.parse_message(frame[4:-2]) as parsed:
            self.assertEqual([r.number for r in parsed.fields], [1, 2, 3, 4])
            self.assertEqual(parsed.occurrences(1)[0].value, 10)
            self.assertEqual(bytes(parsed.occurrences(2)[0].value), b'name (3)')
            self.assertEqual(parsed.occurrences(4)[0].value, 3)
            with pb.parse_message(parsed.occurrences(3)[0].value) as child:
                self.assertEqual(child.occurrences(1)[0].value, 1321)
                self.assertEqual(bytes(child.occurrences(2)[0].value), b'2')

    def test_quantity_suffix_is_wire_only(self):
        fields = item(name=b'original', count=30)
        frames, _ = feature.name_updates((fields,), {}, {})
        self.assertEqual(update_fields(frames[0])[18], b'original (30)')
        self.assertEqual(dict(fields.raw_fields)[18], b'original')
        wire = feature.description_notice(10, b'original', 1)
        self.assertEqual(update_fields(wire)[18], b'original')

    def test_existing_backend_damage_and_armor_groups(self):
        from tools.local_original_session.game_data import load_m1
        data = load_m1()
        weapon = next(d for d in data.items.values() if d.kind == 'weapon' and d.weapon_type != 'bow')
        armor = next(d for d in data.items.values() if d.kind == 'armor')
        source_item = item(template=weapon.template_id, name=('+3 ' + weapon.name_ko).encode())
        values = dict(feature.backend_descriptions(source_item, weapon))
        self.assertEqual((values[33], values[34], values[1321]),
                         (str(weapon.dmg_small).encode(), str(weapon.dmg_large).encode(), b'3'))
        values = dict(feature.backend_descriptions(
            item(template=armor.template_id, name=('+2 ' + armor.name_ko).encode()), armor))
        self.assertEqual((values[8], values[1417]), (str(armor.ac).encode(), b'-2'))

    def test_potion_healing_is_not_mislabelled_regeneration(self):
        from tools.local_original_session.game_data import load_m1
        potion = next(d for d in load_m1().items.values() if d.kind == 'potion' and d.heal_hp > 0)
        values = dict(feature.backend_descriptions(item(template=potion.template_id), potion))
        self.assertNotIn(140, values)
        self.assertLessEqual(values.keys(), {48})

    def test_item_modifier_tokens_match_fixed_client_labels(self):
        root = Path(__file__).resolve().parents[2]
        with (root / 'work/source_game_data/native-dump-v1.jsonl').open(encoding='utf8') as stream:
            tokens = {r['id']: r['name']['KR'] for r in map(json.loads, stream)
                      if r['table'] == 'token'}
        labels = json.loads((root / 'work/all_table_semantics/inputs/data/item_extra_desc.jsonc')
                            .read_text(encoding='utf-8-sig'))
        label_tags = {r['_tag'] for r in labels}
        expected = {'str': 'strBonus', 'dex': 'dexBonus', 'con': 'conBonus',
                    'int': 'intBonus', 'wis': 'wisBonus', 'cha': 'chaBonus',
                    'max_hp': 'hpBonus', 'max_mp': 'mpBonus', 'hp_regen': 'hpMod',
                    'mp_regen': 'mpMod', 'mr': 'mrBonus', 'melee_hit': 'meleeHit',
                    'ranged_hit': 'rangeHit', 'melee_damage': 'meleeDmg',
                    'ranged_damage': 'rangeDmg', 'resist_fire': 'fireResist',
                    'resist_water': 'waterResist', 'resist_wind': 'airResist',
                    'resist_earth': 'earthResist'}
        self.assertEqual({key: tokens[token] for key, token in inventory.ITEM_MODIFIER_TOKENS.items()},
                         expected)
        self.assertTrue(set(expected.values()) <= label_tags)

    def test_real_item_modifiers_reach_notice_without_changing_saved_iteminfo(self):
        from tools.local_original_session.game_data import load_m1
        data = load_m1()
        definition = next(d for d in data.items.values() if d.modifiers.get('int'))
        fields = {**world_handlers._starter_fields(), 2: definition.template_id,
                  18: definition.name_ko.encode()}
        saved = inventory.build_kit_frame([fields])
        member, = inventory.validate_kit_frame(saved)
        values = inventory.backend_descriptions(member, definition)
        self.assertEqual(dict(values)[40], str(definition.modifiers['int']).encode())
        projected = feature.description_notice(member.identifier, fields[18], fields[4], values)
        with pb.parse_message(projected[4:-2]) as parsed:
            descriptions = {}
            for row in parsed.occurrences(3):
                with pb.parse_message(row.value) as child:
                    descriptions[child.occurrences(1)[0].value] = bytes(child.occurrences(2)[0].value)
            self.assertEqual(descriptions, dict(values))
            self.assertEqual(bytes(parsed.occurrences(2)[0].value), fields[18])
        self.assertEqual(inventory.build_kit_frame([dict(member.raw_fields)]), saved)
        self.assertNotIn(19, dict(member.raw_fields))

    def test_item_options_sum_same_tag_and_leave_unverified_effects_absent(self):
        from tools.local_original_session.game_data import load_m1
        definition = next(d for d in load_m1().items.values() if d.kind == 'weapon')
        definition = replace(definition, hit=2, dmg_bonus=3, weapon_type='bow',
                             modifiers={'ranged_hit': 4, 'ranged_damage': 5,
                                        'str': -1, 'unknown_time': 60, 'weight_bonus': 500},
                             class_modifiers={1: {'str': 9}})
        values = dict(feature.backend_descriptions(item(template=definition.template_id), definition))
        self.assertEqual((values[1358], values[1368], values[37]), (b'6', b'8', b'-1'))
        self.assertNotIn(727, values)  # carryPlus's raw scale is not established here.

    def test_foreign_enchant_name_does_not_invent_level(self):
        from tools.local_original_session.game_data import load_m1
        definition = load_m1().items[1]
        values = dict(feature.backend_descriptions(item(name=b'foreign'), definition))
        self.assertFalse({33, 34, 1321} & values.keys())

    def test_backend_templates_produce_bounded_real_description_children(self):
        from tools.local_original_session.game_data import load_m1
        names = world_visibility.item_names()
        for template, definition in load_m1().items.items():
            name = names.get(template)
            if not name:
                continue
            member = item(template=template)
            frame = feature.description_notice(member.identifier, name, 3,
                feature.backend_descriptions(member, definition))
            self.assertLess(len(frame), inventory.MAX_FRAME)
            with pb.parse_message(frame[4:-2]) as parsed:
                self.assertTrue(parsed.occurrences(2))
                self.assertTrue(parsed.occurrences(4))

    def test_unknown_name_is_not_fabricated(self):
        self.assertEqual(feature.name_updates((item(template=999999),), {}, {})[0], ())

    def test_new_kit_and_optional_feature(self):
        from tools.local_original_session.world_bridge import Context
        owner = NS(INVENTORY_STARTER_FIELDS={18: b''}, _world_starter_kit=None,
                   _iteminfo_names={1: b'name'}, _world_enchant_exp=None,
                   _world_registry=world_handlers.build_registry((feature,)))
        ctx = Context(owner)
        owner._iteminfo_kit_name = lambda name, template: feature._iteminfo_kit_name(ctx, name, template)
        starter = NS(uid_base=10, entries=lambda *_: (NS(template_id=1, count=1, grade=None),))
        data = NS(starter=starter, items={1: NS(icon=20)})
        with patch('tools.local_original_session.game_data.load_m1', return_value=data), \
             patch.object(inventory, 'build_kit_frame', side_effect=lambda rows: rows):
            self.assertEqual(world_feature_kit._inventory_kit_frame(ctx, 1)[0][18], b'name')
            del owner._iteminfo_names
            self.assertEqual(world_feature_kit._inventory_kit_frame(ctx, 1)[0][18], b'')
            # Feature excluded: the core never reads the feature's private names.
            owner._iteminfo_names = {1: b'name'}
            owner._world_registry = world_handlers.build_registry(())
            self.assertEqual(world_feature_kit._inventory_kit_frame(ctx, 1)[0][18], b'')

    def test_registry_does_not_override_existing_methods(self):
        from importlib import import_module
        existing = {f.__name__ for name in world_handlers.FEATURE_MODULES
                    if name != 'world_feature_iteminfo'
                    for f in getattr(import_module('tools.local_original_session.' + name), 'METHODS', ())}
        self.assertFalse(existing & {f.__name__ for f in feature.METHODS})
        self.assertEqual(feature.FRAMES, {0x4E2F: ('_iteminfo_direction',)})

    def test_direction_notice_signed_int32_uid(self):
        frame = feature.direction_notice(0xF0000001, 7)
        self.assertEqual(struct.unpack_from('<H', frame, 2)[0], 0x4E2E)
        with pb.parse_message(frame[4:-2]) as parsed:
            self.assertEqual(parsed.occurrences(1)[0].value, 0xFFFFFFFFF0000001)
            self.assertEqual(parsed.occurrences(2)[0].value, 7)


class InitialDescriptionTests(unittest.TestCase):
    """Real display producers retain save bytes and publish full f19."""
    def setUp(self):
        from tools.local_original_session.game_data import load_m1
        self.data = load_m1()
        self.names = world_visibility.item_names()
        self.definition = self.data.items[1]
        self.fields = {**world_handlers._starter_fields(), 1: 1101, 2: 1,
                       4: 3, 18: b''}
        self.saved = inventory.build_kit_frame([self.fields])
        self.member, = inventory.validate_kit_frame(self.saved)
        self.expected = dict(inventory.backend_descriptions(self.member, self.definition))

    def descriptions(self, body):
        with pb.parse_message(body) as parsed:
            self.assertEqual(parsed.occurrences(1)[0].value, self.fields[1])
            self.assertEqual(parsed.occurrences(4)[0].value, self.fields[4])
            self.assertEqual(bytes(parsed.occurrences(18)[0].value), self.names[1] + b' (3)')
            values = {}
            for row in parsed.occurrences(19):
                with pb.parse_message(row.value) as child:
                    self.assertEqual([r.number for r in child.fields], [1, 2])
                    values[child.occurrences(1)[0].value] = bytes(child.occurrences(2)[0].value)
            self.assertEqual(values, self.expected)
        self.assertEqual(inventory.build_kit_frame([dict(self.member.raw_fields)]), self.saved)
        return values

    def display_context(self):
        from tools.local_original_session.world_bridge import Context
        owner = NS(_inventory_kit_policy=inventory.KIT_POLICY, _world=object(),
                   _iteminfo_definitions=self.data.items, _iteminfo_names=self.names,
                   _world_registry=world_handlers.build_registry((feature,)))
        ctx = Context(owner)
        owner._iteminfo_display_fields = lambda fields, row: feature._iteminfo_display_fields(ctx, fields, row)
        return ctx

    def test_initial_0964_has_description_before_followup_and_rejects_as_saved_row(self):
        from tools.local_original_session import world_core_kit
        owner = self.display_context()
        projected = world_core_kit.inventory_payload(owner, self.saved, True)
        with pb.parse_message(projected[4:-2]) as parsed:
            self.descriptions(parsed.occurrences(1)[0].value)
        with self.assertRaises(ValueError):
            inventory.validate_kit_frame(projected)
        self.assertEqual(dict(inventory.validate_kit_frame(self.saved)[0].raw_fields), self.fields)
        # New owned ADDs use the identical projection before later 0977.
        self.assertEqual(world_core_kit.inventory_payload(owner, self.saved, False), projected)

    def test_projected_initial_delivery_chunks_each_real_description(self):
        from tools.local_original_session import world_core_kit
        saved = inventory.build_kit_frame([{**self.fields, 1: 1101 + i} for i in range(80)])
        payload = world_core_kit.inventory_payload(self.display_context(), saved, True)
        count, offset = 0, 0
        while offset < len(payload):
            length = int.from_bytes(payload[offset:offset + 2], 'little')
            self.assertLessEqual(length, inventory.MAX_FRAME)
            with pb.parse_message(payload[offset + 4:offset + length - 2]) as outer:
                for row in outer.occurrences(1):
                    with pb.parse_message(row.value) as child:
                        self.assertEqual(child.occurrences(1)[0].value, 1101 + count)
                        self.assertEqual(len(child.occurrences(19)), len(self.expected))
                    count += 1
                self.assertEqual(outer.occurrences(2)[0].value, 0)
            offset += length
        self.assertEqual(count, 80)
        self.assertEqual(len(inventory.validate_kit_frame(saved)), 80)

    def test_companion_bag_and_equipment_reference_same_described_uid(self):
        from tools.local_original_session import world_companion_ui as ui
        body = ui.bag_body(self.saved, self.data.items, self.names)
        with pb.parse_message(body) as outer:
            self.descriptions(outer.occurrences(1)[0].value)
        state = NS(weapon_uid=self.fields[1], slots=())
        equipment, = ui.equipment_bodies(self.saved, state, self.data.items)
        with pb.parse_message(equipment) as parsed:
            self.assertEqual(parsed.occurrences(1)[0].value, self.fields[1])
        self.assertNotIn(19, dict(self.member.raw_fields))

    def test_warehouse_actual_open_supplies_description_to_issued_row(self):
        from tools.local_original_session import world_feature_town as town
        sent = []
        owner = NS(_world_warehouse_exp=(1, 0, 150, 0, 7, 30, 150),
                   _world=NS(combat=NS(pcs={7: NS(profile=NS(level=30))}), data=self.data),
                   _world_services=NS(minimum_level=1), inventory_frame=self.saved,
                   inventory_transactions=NS(restore_warehouse=lambda _: self.saved))
        ctx = NS(pc_uid=7, row={}, _source=lambda *args: object(), send_frame=sent.append)
        town._world_warehouse_open(owner, ctx, NS(ref=object()), 'retrieve')
        with pb.parse_message(sent[0][4:-2]) as outer:
            with pb.parse_message(outer.occurrences(7)[0].value) as row:
                self.assertEqual(row.occurrences(1)[0].value, 0)
                self.descriptions(row.occurrences(2)[0].value)
        self.assertIs(ctx.row['_world_warehouse_window']['warehouse'], self.saved)
        self.assertEqual(ctx.row['_world_warehouse_window']['rows'], {0: self.fields[1]})

    def test_description_projection_preserves_explicit_variant_and_raw_fields(self):
        fields = {**self.fields, 18: b'+2 ' + self.definition.name_ko.encode()}
        member, = inventory.validate_kit_frame(inventory.build_kit_frame([fields]))
        projected = inventory.display_fields(member, self.definition, self.names)
        self.assertEqual(projected[18], fields[18] + b' (3)')
        self.assertEqual(dict(projected[19])[1321], b'2')
        self.assertEqual({n: v for n, v in projected.items() if n not in (18, 19)},
                         {n: v for n, v in fields.items() if n != 18})
        self.assertEqual(dict(member.raw_fields), fields)


class HookTests(unittest.IsolatedAsyncioTestCase):
    def context(self):
        writer, lock = object(), object()
        game = NS(selection=object())
        position = NS(uid=7)
        service = NS(fatal=False, snapshot=lambda: position)
        pc = NS(heading=0)
        async def dispatch(fn):
            return fn()
        queued = []
        world = NS(entities=NS(get=lambda _: pc), runtime=NS(dispatch_now=dispatch),
                   combat=NS(pcs={7: NS(dead=False, hp=5)}), pcs={7: (), 8: (), 9: ()},
                   visibility=NS(known={7: {7}, 8: {7}, 9: set()}),
                   _queue=lambda uid, frame: queued.append((uid, frame)),
                   _announce=lambda: None, queued=queued)
        sent = []
        async def send(*args, **kw):
            sent.append((args, kw))
        ctx = NS(world=world, _world_pcs={id(writer): (writer, 7)},
                 realm=NS(service=lambda _: service), selected_session=lambda _: game,
                 owner_current=lambda *_: True, _iteminfo_errors=[], _iteminfo_names={1: b'name'},
                 _inventory_kit_policy=inventory.KIT_POLICY, inventory_frame=None,
                 WORLD_SEND_CHUNK=2, send=send)
        row = dict(policy_row=object(), writer=writer, joined=False, failed=False,
                   operation_lock=lock)
        return ctx, writer, row, game, lock, pc, service, sent

    async def test_direction_changes_only_heading(self):
        ctx, writer, row, game, lock, pc, service, sent = self.context()
        frame = NS(opcode=0x4E2F, payload=pb.encode_uint32(1, 6))
        self.assertTrue(await feature._iteminfo_direction(ctx, writer, row, game, frame, lock))
        self.assertEqual((pc.heading, service._actor_heading), (6, 6))
        self.assertEqual(sent, [])
        self.assertEqual(ctx.world.queued, [(8, feature.direction_notice(7, 6))])

    async def test_invalid_direction_is_request_local(self):
        ctx, writer, row, game, lock, pc, service, sent = self.context()
        for payload in (b'', b'\x08\x08', b'\x08\x01\x08\x02', b'\x0a\x00', b'\x08\xff'):
            self.assertTrue(await feature._iteminfo_direction(ctx, writer, row, game,
                NS(opcode=0x4E2F, payload=payload), lock))
        self.assertEqual(pc.heading, 0)
        self.assertEqual(len(ctx._iteminfo_errors), 5)
        self.assertTrue(await feature._iteminfo_direction(ctx, writer, row, game,
            NS(opcode=0x4E2F, payload=b'\x08\x03'), lock))
        self.assertEqual(pc.heading, 3)

    async def test_stale_owner_cannot_turn(self):
        ctx, writer, row, game, lock, pc, service, sent = self.context()
        ctx.selected_session = lambda _: NS(selection=object())
        await feature._iteminfo_direction(ctx, writer, row, game,
            NS(opcode=0x4E2F, payload=b'\x08\x02'), lock)
        self.assertEqual(pc.heading, 0)
        self.assertEqual(sent, [])

    async def test_late_inventory_display_and_reentry(self):
        ctx, writer, row, game, lock, pc, service, sent = self.context()
        await feature._iteminfo_enter(ctx, writer, row, game, lock)
        self.assertEqual(sent, [])
        before = b'current saved frame'
        ctx.inventory_frame = before
        with patch.object(inventory, 'validate_kit_frame', return_value=(item(),)):
            await feature._iteminfo_after_request(ctx, writer, row, game, 0x4E2A, lock)
            await feature._iteminfo_after_request(ctx, writer, row, game, 0x4E2A, lock)
            self.assertEqual(len(sent), 1)
            await feature._iteminfo_enter(ctx, writer, row, game, lock)
        self.assertEqual(len(sent), 2)
        self.assertIs(ctx.inventory_frame, before)
        self.assertIs(sent[0][1]['operation_lock'], lock)
        self.assertIs(sent[0][0][2], sent[0][1]['world_operation'])

    async def test_optional_display_without_transport_row_skips_owner_and_send(self):
        ctx, writer, row, game, lock, pc, service, sent = self.context()
        ctx.owner_current = lambda *_: self.fail('optional display required transport owner')
        ctx.inventory_frame = b'current saved frame'
        await feature._iteminfo_enter(ctx, writer, {}, game, lock)
        await feature._iteminfo_after_request(ctx, writer, {}, game, 0x4E2A, lock)
        self.assertEqual(sent, [])

    async def test_real_transport_row_still_requires_current_owner(self):
        ctx, writer, row, game, lock, pc, service, sent = self.context()
        calls = []
        ctx.owner_current = lambda *_: calls.append(True) or False
        ctx.inventory_frame = b'current saved frame'
        await feature._iteminfo_enter(ctx, writer, row, game, lock)
        self.assertEqual(calls, [True])
        self.assertEqual(sent, [])


if __name__ == '__main__':
    unittest.main()
