"""LOCAL craft calculations and existing save owner; no client or socket PASS."""
from pathlib import Path
import asyncio
import json
import tempfile
from types import MethodType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock

from tools.local_original_session import inventory, inventory_store
from tools.local_original_session import world_craft as craft
from tools.local_original_session.world_handlers import KitItemPolicy, _starter_fields
from tools.local_original_session.world_state_services import InventoryTransactions
from tools.local_entry_server import protobuf as pb


def row(uid, template, count=1, **changes):
    result = _starter_fields()
    result.update({1: uid, 2: template, 4: count, 7: template, 18: b''})
    result.update({int(key): value for key, value in changes.items()})
    return result


def kit(*rows):
    return inventory.build_kit_frame(list(rows))


def counts(frame):
    result = {}
    for item in inventory.validate_kit_frame(frame):
        result[item.template_bits] = result.get(item.template_bits, 0) + dict(item.raw_fields)[4]
    return {key: value for key, value in result.items() if value}


def request_payload(target=2, recipe=27, count=1, inputs=((1, 7, 10, 0, 1), (2, 408, 2, 0, 1))):
    payload = b''.join(pb.encode_varint(number << 3) + pb.encode_varint(value)
                       for number, value in ((1, target), (2, recipe), (3, count)))
    for row in inputs:
        payload += pb.encode_bytes(4, b''.join(pb.encode_varint(number << 3) + pb.encode_varint(value)
                         for number, value in enumerate(row, 1)))
    return payload


class CraftTests(unittest.TestCase):
    def setUp(self):
        self.recipe = craft.Recipe('local:test', 70598, craft.Material(385, 1),
            (craft.Material(7, 10), craft.Material(408, 2)))
        self.policies = {template: KitItemPolicy(template, 1, stackable,
            row(1, template), (b'',))
            for template, stackable in ((7, True), (408, True), (385, False))}
        self.before = kit(row(101, 7, 25), row(102, 408, 5))

    def make(self, frame=None, **options):
        return craft.calculate_craft(self.before if frame is None else frame,
            self.recipe, options.pop('count', 1), self.policies, **options)

    def test_insufficient_material_keeps_input_and_never_allocates_reward(self):
        before = kit(row(101, 7, 25), row(102, 408, 1))
        allocate = Mock(return_value=200)
        with self.assertRaises(ValueError):
            self.make(before, allocate_uid=allocate)
        self.assertEqual(counts(before), {7: 25, 408: 1})
        allocate.assert_not_called()

    def test_exact_consumption_output_and_quantity_frames(self):
        plan = self.make(allocate_uid=lambda: 200)
        self.assertEqual(plan.before, self.before)
        self.assertEqual((plan.recipe_id, plan.count), ('local:test', 1))
        self.assertEqual(counts(plan.after), {7: 15, 408: 3, 385: 1})
        self.assertEqual(counts(self.before), {7: 25, 408: 5})
        result = next(item for item in inventory.validate_kit_frame(plan.after)
            if item.template_bits == 385)
        self.assertEqual(result.identifier, 200)
        self.assertTrue(plan.frames)
        self.assertTrue(all(isinstance(frame, bytes) for frame in plan.frames))

    def test_repeated_count_scales_materials_and_separate_nonstackable_uids(self):
        allocated = iter((200, 201))
        plan = self.make(count=2, allocate_uid=lambda: next(allocated))
        self.assertEqual(counts(plan.after), {7: 5, 408: 1, 385: 2})
        result = [item for item in inventory.validate_kit_frame(plan.after)
                  if item.template_bits == 385]
        self.assertEqual([(r.identifier, dict(r.raw_fields)[4]) for r in result], [(200, 1), (201, 1)])

    def test_exact_material_stacks_are_removed_before_reward_is_appended(self):
        before = kit(row(101, 7, 10), row(102, 408, 2))
        plan = self.make(before, allocate_uid=lambda: 200)
        self.assertEqual(counts(plan.after), {385: 1})
        self.assertEqual([item.identifier for item in inventory.validate_kit_frame(plan.after)], [200])
        self.assertEqual(len(plan.frames), 3)

    def test_unrelated_zero_quantity_anchor_is_preserved(self):
        anchor = row(99, 7, 0)
        before = kit(anchor, row(101, 7, 25), row(102, 408, 5))
        plan = self.make(before, allocate_uid=lambda: 200)
        actual = {item.identifier: dict(item.raw_fields)
                  for item in inventory.validate_kit_frame(plan.after)}
        self.assertEqual(actual[99], anchor)

    def test_worn_or_modified_material_cannot_be_consumed(self):
        with self.assertRaises(ValueError):
            self.make(excluded_uids=(102,))
        modified = kit(row(101, 7, 25), row(102, 408, 5, **{'5': 1}))
        with self.assertRaises(ValueError):
            self.make(modified)
        self.assertEqual(counts(modified), {7: 25, 408: 5})

    def test_invalid_quantity_and_colliding_reward_uid_refuse(self):
        for quantity in (0, -1, True):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.make(count=quantity)
        with self.assertRaises(ValueError):
            self.make(allocate_uid=lambda: 101)

    def test_weight_limit_refusal_preserves_current_inventory(self):
        with self.assertRaises(ValueError):
            self.make(max_weight=0)
        self.assertEqual(counts(self.before), {7: 25, 408: 5})

    def test_shipped_moria_recipes_keep_classic_ids_and_local_quantities(self):
        recipes = {recipe.id: recipe for recipe in craft.load_recipes()}
        cap = recipes['moria_magician_cap']
        dress = recipes['moria_magician_dress']
        self.assertEqual((cap.npc_template_id, cap.result), (346, craft.Material(385, 1)))
        self.assertEqual((dress.npc_template_id, dress.result), (346, craft.Material(386, 1)))
        self.assertEqual({m.template_id: m.quantity for m in cap.materials},
                         {172: 2, 166: 20, 379: 1, 378: 1, 376: 1})
        self.assertEqual({m.template_id: m.quantity for m in dress.materials},
                         {179: 1, 166: 25, 379: 2, 376: 4})

    def feature_case(self, *, failure=None):
        from tools.local_original_session import world_feature_craft as feature
        from tools.local_original_session.world_entities import Kind
        source = NS(delivered=True, retired=False)
        interaction = NS(ref=NS(uid=2), npc=NS(npc_id=70598))
        menu = NS(source=source, fields={1: 2})
        state = NS(menu=menu, interaction=interaction)
        def clear():
            state.menu = state.interaction = None
        state.clear = Mock(side_effect=clear)
        owner = NS(inventory_frame=self.before, _inventory_kit_policy=inventory.KIT_POLICY,
            _world_craft_recipes=(self.recipe,), _world_craft_npcs={70598: 70598},
            _world_craft_results=[], _world_replace_kit=Mock(return_value=True, side_effect=failure),
            run_sync_hooks=Mock(),
            world=NS(entities=NS(resolve=lambda ref: object(),
                get=lambda uid: NS(kind=Kind.PC, alive=True, map_id=4, x=1, y=1)),
                combat=NS(pcs={1: NS(dead=False, hp=20)}), drain=lambda uid: ()))
        host = NS(_owned=Mock(), current_source=lambda current: current is source and not current.retired,
            state=state, pc_uid=1, now=lambda: 0, commit_attempted=False, writer=object(), row={},
            bindings=NS(item_policies=self.policies, allocate_uid=lambda host: 200),
            store=NS(snapshot=lambda uid, now: NS(items=(), inventory=NS(max_weight=100))),
            send_frame=Mock())
        host.world = owner.world
        host.town = NS(entities=owner.world.entities, route_click=Mock(return_value=interaction))
        host.interaction_distance = 15
        owner._world_craft_native = {(70598, 27): dict(id=self.recipe.id, native_catalog=dict(inputs=[
            dict(fields={'3': 1, '1': 7, '2': 10, '4': 0, '5': 1}),
            dict(fields={'3': 2, '1': 408, '2': 2, '4': 0, '5': 1})]))}
        for name in ('_world_craft_list', '_world_craft_select', '_world_craft_make'):
            setattr(owner, name, MethodType(getattr(feature, name), owner))
        listing = feature._world_craft_list(owner, host, interaction, menu)
        selection = feature._world_craft_select(owner, host, listing, 0)
        return feature, owner, host, selection

    def test_internal_provider_saves_before_response_and_retires_selection(self):
        feature, owner, host, selection = self.feature_case()
        def saved(*args, **kwargs):
            host.send_frame.assert_not_called()
            return True
        owner._world_replace_kit.side_effect = saved
        plan = feature._world_craft_make(owner, host, selection, 1)
        owner._world_replace_kit.assert_called_once_with(1, self.before, plan.after, append=True)
        self.assertIs(owner.inventory_frame, plan.after)
        self.assertTrue(selection.listing.source.retired)
        self.assertTrue(host.commit_attempted)
        self.assertIsNone(host.state.menu)
        self.assertEqual(host.send_frame.call_count, len(plan.frames))
        with self.assertRaises(ValueError):
            feature._world_craft_make(owner, host, selection, 1)
        self.assertEqual(owner._world_replace_kit.call_count, 1)

    def test_internal_provider_failed_save_keeps_inventory_and_sends_no_reward(self):
        feature, owner, host, selection = self.feature_case(failure=OSError('save failed'))
        with self.assertRaisesRegex(OSError, 'save failed'):
            feature._world_craft_make(owner, host, selection, 1)
        self.assertIs(owner.inventory_frame, self.before)
        self.assertEqual(owner._world_craft_results, [])
        self.assertTrue(selection.listing.source.retired)
        host.send_frame.assert_not_called()

    def test_native_success_keeps_menu_and_rejects_old_selection_inventory(self):
        feature, owner, host, selection = self.feature_case()
        menu = host.state.menu
        plan = feature._world_craft_make(owner, host, selection, 1, keep_menu=True)
        self.assertIs(host.state.menu, menu)
        self.assertFalse(selection.listing.source.retired)
        owner.run_sync_hooks.assert_called_once_with('inventory_changed', host.writer, host.row)
        self.assertIs(owner.inventory_frame, plan.after)
        with self.assertRaisesRegex(ValueError, 'CRAFT_CURRENT_INVENTORY_REQUIRED'):
            feature._world_craft_make(owner, host, selection, 1, keep_menu=True)
        self.assertEqual(owner._world_replace_kit.call_count, 1)

    def test_native_request_rejects_duplicate_slots_before_cas(self):
        feature, owner, host, _ = self.feature_case()
        duplicate = craft.decode_request(request_payload(inputs=((1, 7, 10, 0, 1), (1, 408, 2, 0, 1))))
        with self.assertRaisesRegex(ValueError, 'CRAFT_CURRENT_INPUTS_REQUIRED'):
            feature._world_craft_request(owner, host, duplicate)
        owner._world_replace_kit.assert_not_called()
        host.send_frame.assert_not_called()
        self.assertIs(owner.inventory_frame, self.before)

    def test_native_uint32_uid_preserves_high_bit_and_rejects_signextended_wire(self):
        decoded = craft.decode_request(request_payload(target=0x80000001))
        self.assertEqual((decoded.target_uid, decoded.recipe_id, decoded.count), (0x80000001, 27, 1))
        self.assertEqual(decoded.inputs, ((1, 7, 10, 0, 1), (2, 408, 2, 0, 1)))
        with self.assertRaises(ValueError):
            craft.decode_request(request_payload(target=0xffffffff80000001))

    def test_native_malformed_fields_and_quantity_are_refused(self):
        for payload in (request_payload(count=0), request_payload() + b'\x08\x02',
                        request_payload() + b'\x30\x01', request_payload() + b'\x20\x01',
                        request_payload(inputs=((1, 7, 10, 0),))):
            with self.subTest(payload_length=len(payload)), self.assertRaises(ValueError):
                craft.decode_request(payload)

    def test_ack_success_is_explicit_zero_refusal_does_not_invent_result_enum(self):
        success = craft.acknowledgement_frame(success=True)
        refusal = craft.acknowledgement_frame(success=False)
        self.assertEqual(success, b'\x08\0\x06\0\x08\0\0\0')
        self.assertEqual(refusal, b'\x06\0\x06\0\0\0')
        with pb.parse_message(success[4:-2]) as message:
            self.assertEqual([(field.number, field.value) for field in message.fields], [(1, 0)])
        with pb.parse_message(refusal[4:-2]) as message:
            self.assertFalse(message.fields)

    def test_optional_registration_removes_craft_methods_hooks_and_save_boundary(self):
        from tools.local_original_session import world_feature_craft as feature
        from tools.local_original_session import world_handlers, world_registry
        enabled = world_registry.build_registry((*world_handlers.CORE_MODULES, feature))
        disabled = world_registry.build_registry(world_handlers.CORE_MODULES)
        names = {method.__name__ for method in feature.METHODS}
        self.assertTrue(names <= set(enabled.methods))
        self.assertTrue(names.isdisjoint(disabled.methods))
        self.assertIn('craft_provider', enabled.hooks)
        self.assertNotIn('craft_provider', disabled.hooks)
        self.assertIn('_world_craft_make', enabled.save_boundaries)
        self.assertNotIn('_world_craft_make', disabled.save_boundaries)
        self.assertIn('_world_attack', disabled.methods)
        self.assertIn('_world_craft_frame', enabled.frames[0x0005])
        self.assertNotIn(0x0005, disabled.frames)
        self.assertIn(0x0006, enabled.outgoing_opcodes)
        self.assertNotIn(0x0006, disabled.outgoing_opcodes)

    def test_local_inventory_refresh_uses_new_observation_and_preserves_refusal(self):
        from tools.local_original_session.hunt_bot_craft import refresh_local_inventory_observation
        class Policy:
            def begin_write(self):
                pass
        policy, row, writer = Policy(), {}, object()
        old_sample, new_sample = object(), object()
        broker = NS(policy=policy, _inventory_before_send=AsyncMock(return_value=b'wire'),
            _sample=AsyncMock(return_value=new_sample), _policy_sample=Mock(return_value=True))
        original = broker._policy_sample
        refresh_local_inventory_observation(broker)
        self.assertEqual(asyncio.run(broker._inventory_before_send(writer, row)), b'wire')
        broker._policy_sample(row, policy.begin_write, writer, old_sample, 0x0964, 1, 0, 123)
        self.assertIs(original.call_args.args[3], new_sample)
        # The freshly queried sample is consumed once; unrelated calls retain
        # their actual supplied sample and the original policy still executes.
        broker._policy_sample(row, policy.begin_write, writer, old_sample, 0x0964, 1, 0, 124)
        self.assertIs(original.call_args.args[3], old_sample)
        broker._sample.side_effect = ValueError('CURRENT_OWNER_REQUIRED')
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
            asyncio.run(broker._inventory_before_send(writer, row))

    def test_plan_saved_and_reopened_by_existing_core_owner_other_character_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'characters.json'
            roster = inventory_store.realm.CharacterStore(path)
            for name in ('Crafter', 'Untouched'):
                roster.create(inventory_store.realm.Creation(name, 1, 0, (13,) * 6))
            store = inventory_store.InventoryStore(path, policy=inventory_store.POLICY,
                                                   kit_policy=inventory.KIT_POLICY)
            store.grant(1, self.before)
            other = kit(row(1000, 7, 77))
            store.grant(2, other)
            plan = self.make(allocate_uid=lambda: 200)
            transactions = InventoryTransactions(store)
            self.assertTrue(transactions.commit_inventory(1, plan.before, plan.after, append=True))
            reopened = inventory_store.InventoryStore(path, policy=inventory_store.POLICY,
                                                      kit_policy=inventory.KIT_POLICY)
            self.assertEqual(reopened.restore(1), plan.after)
            self.assertEqual(reopened.restore(2), other)
            # A stale second application cannot consume or grant a second time.
            with self.assertRaises(ValueError):
                transactions.commit_inventory(1, plan.before, plan.after, append=True)
            self.assertEqual(reopened.restore(1), plan.after)


class Phase2CraftTests(unittest.TestCase):
    """Current native table joins, shared-NPC identity and new registered grants."""

    def setUp(self):
        self.raw = json.loads(craft.DATA_PATH.read_text(encoding='utf-8'))

    def policies(self):
        from tools.local_original_session import world_town, world_feature_m5, world_quest
        from tools.local_original_session.world_handlers import _default_item_policies
        town = world_feature_m5.load_m5_town(world_town.with_gludin_town(world_town.load_town()))
        policies = {p.template_id: p for p in _default_item_policies(NS(data=town))}
        for policy in world_quest.load_inventory_policies():
            policies.setdefault(policy.template_id, policy)
        for item in self.raw['items']:
            prototype = row(1, item['template_id'])
            prototype.update({7: item['icon'], 18: item['name_ko'].encode('utf-8')})
            policies.setdefault(item['template_id'], KitItemPolicy(item['template_id'],
                item['raw_weight'], item['stackable'], prototype))
        return policies

    def test_phase2_counts_shared_recipe_and_existing_policy_scope(self):
        from tools.local_original_session import world_feature_craft as feature
        owner = NS(starter_fields=_starter_fields(), add_item_policies=Mock())
        feature._world_craft_initialize(owner)
        self.assertEqual((len(owner._world_craft_recipes), len(owner._world_craft_npcs),
                          len(owner._world_craft_native)), (93, 21, 93))  # CRAFTING.md phase 3
        self.assertEqual(len({r['native_recipe_id'] for r in self.raw['recipes']}), 64)
        self.assertEqual(len(self.raw['items']), 32)  # No new item policy to admit a recipe.
        self.assertEqual(owner._world_craft_native[70523, 1]['id'], 'ladar_hard_leather')
        self.assertEqual(owner._world_craft_native[70034, 1]['id'], 'vincent_native_1')
        policies = self.policies()
        for recipe in craft.load_recipes():
            for material in (recipe.result, *recipe.materials):
                with self.subTest(recipe=recipe.id, template=material.template_id):
                    self.assertIsNotNone(policies[material.template_id].grant_fields)

    def test_every_shipped_association_matches_native_formula_and_npc_list(self):
        from tools.all_table_semantics.remaining import parse
        root = Path(__file__).resolve().parents[2]
        source = root / 'work/all_table_semantics/inputs/imported/bin'
        def field(raw, n):
            return [value for number, wire, value in parse(raw) if number == n]
        native = {field(entry, 1)[0]: field(entry, 2)[0]
                  for entry in field((source / 'craft.bin').read_bytes(), 2)}
        npc_root = field(field((source / 'npccraftlist.bin').read_bytes(), 2)[0], 2)[0]
        npcs = {field(npc, 1)[0]: {field(ref, 1)[0] for ref in field(npc, 3)}
                for npc in field(npc_root, 2)}
        for recipe in self.raw['recipes']:
            with self.subTest(recipe=recipe['id']):
                key = recipe['native_recipe_id']
                self.assertIn(key, npcs[recipe['npc_template_id']])
                body = native[key]
                materials = {field(item, 1)[0]: field(item, 2)[0]
                    for group in field(body, 7) for item in field(group, 1)}
                outputs = [(field(item, 1)[0], field(item, 2)[0])
                    for group in field(body, 8) for result in field(group, 1)
                    for item in field(result, 6)]
                self.assertEqual(materials, {m['template_id']: m['quantity'] for m in recipe['materials']})
                self.assertEqual(outputs, [(recipe['result']['template_id'], recipe['result']['quantity'])])

    def test_all_new_recipes_consume_exact_inputs_and_repeat_with_registered_prototypes(self):
        policies = self.policies()
        for recipe in craft.load_recipes():
            if not recipe.id.startswith(('vincent_native_', 'hector_native_', 'dio_native_')):
                continue
            with self.subTest(recipe=recipe.id):
                required = {}
                for material in recipe.materials:
                    required[material.template_id] = required.get(material.template_id, 0) + material.quantity * 2
                inputs = []
                for template, amount in required.items():
                    for quantity in ((amount,) if policies[template].stackable else (1,) * amount):
                        inputs.append({**policies[template].grant_fields,
                                       1: 1000 + len(inputs), 4: quantity})
                before = kit(*inputs)
                plan = craft.calculate_craft(before, recipe, 2, policies)
                self.assertEqual(counts(plan.after), {recipe.result.template_id: recipe.result.quantity * 2})
                self.assertEqual(counts(before), required)

    def test_current_npc_resolves_shared_native_recipe_without_other_npc_overwrite(self):
        fixture = CraftTests()
        fixture.setUp()
        feature, owner, host, _ = fixture.feature_case()
        correct = owner._world_craft_native[70598, 27]
        owner._world_craft_native[70034, 27] = dict(correct, id='different_npc_recipe')
        plan = feature._world_craft_request(owner, host, craft.decode_request(request_payload()))
        self.assertEqual(plan.recipe_id, 'local:test')
        owner._world_replace_kit.assert_called_once()

    def test_dio_missing_native_root_does_not_publish_a_substitute_menu(self):
        from tools.local_original_session import world_feature_craft as feature
        from tools.local_original_session.world_town import TownConfig, TownSetup
        npc = NS(npc_id=70027, spawn={'count': 1})
        town = NS(data=NS(placements={(70027, 1): npc}), config=TownConfig(), register=Mock())
        owner = NS(world=NS(runtime_extensions=NS(wrap=Mock(return_value=NS(close=Mock())))))
        configured = feature._world_craft_town_setup(owner, TownSetup(town, None, (), None))
        # CRAFTING.md phase 3: Dio's native root is the retained sebas1 page
        # (sebas1.uml craft_output->sebas2); no substitute stem is invented.
        self.assertEqual([(s.placement_key, s.stem, s.service_kind) for s in configured.sources],
                         [((70027, 1), 'sebas1', 'craft')])
        self.assertEqual(next(n for n in self.raw['npcs'] if n['id'] == 'dio')['menu_stem'], 'sebas1')

    def test_socket_fixture_uses_current_save_cas_and_keeps_one_currency_stack(self):
        from tools.local_original_session.hunt_bot_craft import CraftScenario
        policies = self.policies()
        before = kit({**policies[7].grant_fields, 1: 100, 4: 1000})
        transaction = Mock(return_value=True)
        scene = NS(store=NS(restore=Mock(return_value=before)), fixture_notes=[],
            recipe_set=tuple(r for r in self.raw['recipes'] if r['id'] in
                             ('vincent_native_1', 'hector_native_21', 'hector_native_24')),
            broker=NS(_world_handler_bindings=NS(item_policies=policies),
                      _world_inventory_transactions=NS(commit_inventory=transaction)))
        CraftScenario.initialize_craft_fixture(scene)
        transaction.assert_called_once()
        args, kwargs = transaction.call_args
        self.assertEqual((args[:2], kwargs), ((1, before), {'append': True}))
        after = inventory.validate_kit_frame(args[2])
        coins = [r for r in after if r.template_bits == 7]
        self.assertEqual([(r.identifier, dict(r.raw_fields)[4]) for r in coins], [(100, 34000)])
        self.assertEqual(counts(args[2]), {7: 34000, 332: 20, 333: 310, 129: 1, 128: 1})


if __name__ == '__main__':
    unittest.main()
