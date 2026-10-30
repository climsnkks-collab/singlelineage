"""Saved PC bag/equipment transfer development tests; no game or listener."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import inventory, inventory_store, equipment_store
from tools.local_original_session.game_data import load_stances
from tools.local_original_session import world_companion_integration_tests as fixtures
from tools.local_original_session.world_companion_inventory import CompanionInventory
from tools.local_original_session.world_enchant_inventory import enchanted_name
from tools.local_native_login_local_ack_hook import ack_enter_world as ack


def item(uid, template, count=1, name=b''):
    return {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 71, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: name, 22: 0, 24: False, 25: 0, 26: False}


class CompanionEquipmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name).resolve() / 'characters.json'
        chars = ack.realm.CharacterStore(path)
        chars.create(ack.realm.Creation('FixtureKnight', 1, 0, (18, 13, 16, 10, 10, 10)))
        chars.create(ack.realm.Creation('FixtureMage', 3, 0, (8, 7, 16, 18, 8, 18)))
        self.store = inventory_store.InventoryStore(path, policy=inventory_store.POLICY,
                                                    kit_policy=inventory.KIT_POLICY)
        self.templates = (230, 90, 102, 104, 106, 120, 129, 113)
        fields = [item(10, 7, 100)] + [item(11 + index, template)
            for index, template in enumerate(self.templates)] + [item(30, 14, 20), item(31, 492, 10)]
        owner_frame = inventory.build_kit_frame(fields)
        self.store.grant(1, owner_frame)
        self.ctx = SimpleNamespace(world=self.fixture.view, inventory_store=self.store,
            inventory_frame=owner_frame, _companion_rows={r['uid']: r for r in chars._read()['characters']},
            _world_stances=load_stances(), _companion_save=Mock(),
            _companion_policy={'thresholds': {'hp': {'companion_emergency_enter': .35},
                                             'mp': {'recover_fraction': .4}}},
            _inventory_kit_frame=lambda _: inventory.build_kit_frame([
                item(50, 41), item(51, 103), item(52, 14, 0), item(53, 7, 100)]))
        self.bags = self.new_bags()
        self.bags.equipment.initialize_kit(1, owner_frame,
            initialization=equipment_store.FIRST_ENABLE_EMPTY, weapon_uid=0, slots=())
        self.bags.initialize(2)
        self.record, self.actor = self.fixture.record, self.fixture.actor

    def new_bags(self):
        from tools.local_original_session.world_feature_companion import _companion_owned_actor
        return CompanionInventory(self.ctx, characters=self.ctx._companion_rows,
            policy=self.ctx._companion_policy, save=self.ctx._companion_save,
            owned_actor=lambda uid, actor_uid: _companion_owned_actor(self.ctx, uid, actor_uid),
            report_error=Mock())

    def give(self, source, count=1):
        return self.bags.give(1, self.actor, source, count, self.ctx.inventory_frame)

    def member_item(self, template):
        return next(row.identifier for row in inventory.validate_kit_frame(self.bags.frames[2])
                    if row.template_bits == template)

    def configure_recovery(self, hp=(), mp=(), *, hp_percent=50.0, mp_percent=40.0):
        from tools.local_original_session import ats_config_codec as codec
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.bags.frames[2])]
        def slots(templates):
            return [{4: row[2], 5: row[22], 6: row[3], 7: row[18]}
                    for template in templates
                    for row in rows if row[2] == template and row[4] > 0][:len(templates)]
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(
            hp_templates=slots(hp), hp_percent=hp_percent,
            mp_templates=slots(mp), mp_percent=mp_percent)), {})
        self.bags.policy_for = lambda _: policy
        return policy

    def bridge_context(self, poster):
        from types import MethodType
        from tools.local_original_session import companion_bridge_host, world_registry
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_feature_companion_bridge as bridge
        from tools.local_original_session.world_bridge import Context
        ctx = self.ctx
        ctx._world_registry = world_registry.build_registry((companion, bridge))
        for name, fn in ctx._world_registry.methods.items():
            setattr(ctx, name, MethodType(fn, ctx))
        ctx.run_sync_hooks = MethodType(Context.run_sync_hooks, ctx)
        ctx.collect_sync_hooks = MethodType(Context.collect_sync_hooks, ctx)
        bridge._bridge_initialize(ctx)
        ctx._companion_enabled = True
        ctx._companion_inventory = self.bags
        ctx._companion_views, ctx._companion_mapped, ctx._companion_model_revision = {}, {}, {}
        ctx._companion_published, ctx._companion_ui_events = [], []
        ctx._companion_save = Mock()
        directory = Path(self.temp.name)
        (directory / 'context.json').write_text(json.dumps(dict(
            pid=123, birth=456, candidate_sha256='a' * 64)), encoding='utf-8')
        ctx._companion_bridge_host = companion_bridge_host.DirectoryHost(directory, poster=poster)
        return ctx, directory

    def test_bridge_map_publishes_member_name_as_bounded_utf8_hex(self):
        from tools.local_original_session import companion_bridge_host
        from tools.local_original_session import world_feature_companion as companion
        ctx, directory = self.bridge_context(lambda message, seq: True)
        name = '동료 법사'
        ctx.world.companion_looks[2]['name'] = name
        companion._companion_publish_map(ctx, 1, self.actor)
        host = ctx._companion_bridge_host

        def request():
            return json.loads((directory / f'companion-request-{host.sequence}.json').read_text())

        mapped = request()
        self.assertEqual(mapped['command'], 'map')
        self.assertEqual((mapped['member_id'], mapped['owner_uid']), (2, 1))
        self.assertEqual(bytes.fromhex(mapped['name_hex']).decode('utf-8'), name)
        sequence = host.sequence
        companion._companion_publish_map(ctx, 1, self.actor)
        self.assertEqual(host.sequence, sequence)
        # A name update republishes the same identity; byte truncation cannot
        # leave a partial Korean UTF-8 character at the label_hex length limit.
        ctx.world.companion_looks[2]['name'] = 'A' * 119 + '가'
        companion._companion_publish_map(ctx, 1, self.actor)
        self.assertEqual(host.sequence, sequence + 1)
        self.assertEqual(bytes.fromhex(request()['name_hex']).decode('utf-8'), 'A' * 119)
        for invalid in ('AB', '00' * 121):
            with self.assertRaisesRegex(ValueError, 'COMPANION_HOST_NAME'):
                companion_bridge_host.request_text(host.identity, host.sequence + 1,
                    dict(mapped, name_hex=invalid))
        ctx.world.companion_looks[2].pop('name')
        companion._companion_publish_map(ctx, 1, self.actor)
        self.assertEqual(request()['name_hex'], '')  # DLL uses the original Pet Text fallback
        companion._companion_unmapped(ctx, self.actor)
        self.assertEqual(request()['command'], 'unmap')
        self.assertNotIn(2, ctx._companion_mapped)

    def test_bridge_failed_posts_retry_on_ticks_and_only_success_caches_map(self):
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_feature_companion_bridge as bridge
        posted = []
        outcomes = iter((False, True, False, True))  # install fail; install OK/map fail; map OK
        ctx, _ = self.bridge_context(lambda message, seq: posted.append((message, seq)) or next(outcomes))
        companion._companion_publish_map(ctx, 1, self.actor)
        self.assertFalse(ctx._companion_bridge_host.installed)
        self.assertNotIn(2, ctx._companion_mapped)
        companion._companion_publish_map(ctx, 1, self.actor)
        self.assertEqual(len(posted), 1)  # repeated save waits for a tick
        bridge._bridge_started(ctx)
        self.fixture.view.runtime._hooks[-1](0)
        self.assertTrue(ctx._companion_bridge_host.installed)
        self.assertNotIn(2, ctx._companion_mapped)
        bridge._bridge_tick(ctx, 1)
        self.assertIn(2, ctx._companion_mapped)
        companion._companion_publish_map(ctx, 1, self.actor)
        self.assertEqual(len(posted), 4)
        host = ctx._companion_bridge_host
        host.installed = False
        host.poster = lambda message, seq: False
        ctx._companion_mapped.clear()
        companion._companion_publish_map(ctx, 1, self.actor)
        for now in range(5):
            bridge._bridge_tick(ctx, now)
            companion._companion_publish_map(ctx, 1, self.actor)
        self.assertEqual(host.sequence, 4 + bridge.PUBLISH_ATTEMPTS)
        self.assertFalse(host.installed)
        self.assertNotIn(2, ctx._companion_mapped)
        # File/publication errors follow the same bounded tick retry path.
        bridge._bridge_initialize(ctx)
        host.installed = True
        with patch.object(host, 'publish_request', side_effect=OSError('PUBLISH_FAILED')) as publish:
            companion._companion_publish_map(ctx, 1, self.actor)
            for now in range(5):
                bridge._bridge_tick(ctx, now)
            self.assertEqual(publish.call_count, bridge.PUBLISH_ATTEMPTS)
        self.assertEqual(ctx._bridge_outbox[-1]['status'], 'PUBLISH_FAILED')
        self.assertNotIn(2, ctx._companion_mapped)

    def test_offscreen_menu_signal_uses_current_mapping_and_normal_status_response(self):
        import asyncio
        from tools.local_original_session import companion_signals as signals
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_feature_companion_bridge as bridge
        ctx, directory = self.bridge_context(lambda message, seq: True)
        writer = object()
        ctx._world_pcs = {id(writer): (writer, 1)}
        ctx._world_bound = lambda candidate: candidate is writer
        ctx._world_ready = lambda *_: True
        ctx.owner_current = lambda *_: True
        ctx._claims = {'fixture': [dict(writer=writer, operation_lock=asyncio.Lock())]}
        ctx._companion_windows = {}
        ctx._companion_pet_modes = {}
        ctx.realm = SimpleNamespace(service=lambda _: SimpleNamespace(snapshot=lambda: SimpleNamespace(uid=1)),
                                    registry=SimpleNamespace(resolve=lambda _: object()))
        sent = []
        async def flush(*_):
            self.assertNotIn(id(writer), ctx._companion_windows)
            sent.extend(ctx.world.drain(1))
        ctx._world_flush = flush
        companion._companion_publish_map(ctx, 1, self.actor)
        sequence = ctx._companion_bridge_host.sequence
        # Ordinary visibility culling keeps the server lifetime and DLL map.
        self.fixture.view.update_pc_and_drain(1, 0, 150, 100)
        self.assertNotIn(self.actor.ref.uid, ctx.world.visibility.known[1])
        self.assertIs(ctx.world.companions.active[2], self.actor)
        self.assertEqual(ctx._companion_bridge_host.sequence, sequence)
        with self.assertRaisesRegex(ValueError, 'COMPANION_VISIBLE_ACTOR_REQUIRED'):
            companion._companion_owned_actor(ctx, 1, self.actor.ref.uid)
        body = signals.encode_signal('pet-window-open', self.actor.ref.uid)
        metadata = dict(schema='companion-native-signal-v1', transport='LOCAL_IPC',
            pid=123, birth=456, operation='pet-window-open', native_actor_uid=self.actor.ref.uid,
            owner_uid=1, member_id=2, actor_generation=self.actor.ref.generation)

        def ingest(seq, **changes):
            name = f'companion-signal-{seq}.bin'
            (directory / name).write_bytes(body)
            (directory / f'companion-signal-{seq}.json').write_text(
                json.dumps(dict(metadata, event_seq=seq, body_file=name, **changes)), encoding='utf-8')
            return asyncio.run(bridge._bridge_ingest(ctx, directory))

        self.assertEqual(ingest(1), 1)
        self.assertEqual(ctx._bridge_signals[-1]['status'], 'OK')
        self.assertEqual(ctx._companion_windows[id(writer)], self.actor.ref)
        self.assertEqual(len(self.fixture.decoded(sent, 0x4f14, 1, self.actor.ref.uid)), 1)
        # A previously mapped generation and a different map cannot open it.
        self.assertEqual(ingest(2, actor_generation=self.actor.ref.generation + 1), 1)
        self.assertEqual(ctx._bridge_signals[-1]['status'], 'REFUSED')
        self.assertFalse(ctx.world.drain(1))
        self.assertEqual(len(sent), 1)
        ctx._companion_windows.clear()
        async def failed_flush(*_):
            raise OSError('fixture send failure')
        ctx._world_flush = failed_flush
        with self.assertRaisesRegex(OSError, 'fixture send failure'):
            ingest(3)
        self.assertNotIn(id(writer), ctx._companion_windows)
        self.assertIn(3, ctx._bridge_seen)  # no replay after an uncertain send
        self.assertEqual(len(self.fixture.decoded(ctx.world.drain(1), 0x4f14, 1, self.actor.ref.uid)), 1)
        ctx._world_flush = flush
        entity = ctx.world.entities.resolve(self.actor.ref)
        ctx.world.entities.move(entity.uid, 1, entity.x, entity.y)
        self.assertEqual(ingest(4), 1)
        self.assertEqual(ctx._bridge_signals[-1]['status'], 'REFUSED')
        self.assertFalse(ctx.world.drain(1))

    def test_bridge_dll_model_failure_republishes_current_view_once_with_new_revision(self):
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_feature_companion_bridge as bridge
        from tools.local_original_session import world_companion_ui as ui
        ctx, directory = self.bridge_context(lambda message, seq: True)
        ctx._companion_views[1] = dict(member=2, views=('bag',), epochs={'bag': 7})
        companion._companion_model(ctx, 1, self.actor, {'bag'})
        host = ctx._companion_bridge_host
        initial = host.sequence

        def result(seq, **changes):
            values = dict(schema='own-companion-result-v1', **host.identity, seq=seq,
                          command='model-apply', status='MODEL_APPLIED', window_state='NATIVE_CREATE_FAILED')
            values.update(changes)
            (directory / f'companion-result-{seq}.json').write_text(json.dumps(values), encoding='utf-8')

        result(initial, pid=999)
        bridge._bridge_tick(ctx, 0)
        self.assertEqual(host.sequence, initial)
        result(initial)
        bridge._bridge_tick(ctx, 1)
        self.assertEqual(host.sequence, initial + 1)
        model = ui.decode_model_frame((directory / f'companion-model-{host.sequence}.bin').read_bytes())
        self.assertEqual(model['revision'], 2)
        self.assertEqual(ctx._companion_views[1]['epochs'], {'bag': 7})
        result(host.sequence)
        bridge._bridge_tick(ctx, 2)
        bridge._bridge_tick(ctx, 3)
        self.assertEqual(host.sequence, initial + 1)
        self.assertTrue((directory / f'companion-result-{initial}.json').exists())

    def test_real_companion_model_publishes_worn_item_description_without_save_changes(self):
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_companion_ui as ui
        from tools.local_entry_server import protobuf as pb
        ctx, directory = self.bridge_context(lambda message, seq: True)
        saved, state = self.bags.frames[2], self.bags.states[2]
        saved_files = {path: path.read_bytes() for path in self.store.profile.parent.glob('*.json')}
        model = ui.decode_model_frame(companion._companion_model(ctx, 1, self.actor, {'bag', 'equipment'}))
        body, = [body for opcode, body in model['packets'] if opcode == 0x0964]
        described = {}
        with pb.parse_message(body) as parsed:
            for row in parsed.occurrences(1):
                with pb.parse_message(row.value) as fields:
                    uid = fields.occurrences(1)[0].value
                    described[uid] = len(fields.occurrences(19))
                    self.assertTrue(fields.occurrences(18)[0].value)
        self.assertTrue(described)
        self.assertTrue(all(count > 0 for count in described.values()))
        self.assertEqual((self.bags.frames[2], self.bags.states[2]), (saved, state))
        self.assertEqual({path: path.read_bytes() for path in saved_files}, saved_files)

    def test_bridge_view_epoch_ingest_rejects_old_window_and_notices_without_mutation(self):
        import asyncio
        from tools.local_original_session import companion_signals as cs
        from tools.local_original_session import world_feature_companion_bridge as bridge
        from tools.local_entry_server import protobuf as pb
        ctx, directory = self.bridge_context(lambda message, seq: True)
        writer = object()
        ctx._world_pcs = {id(writer): (writer, 1)}

        def send(seq, operation, epoch, args=()):
            body = directory / f'companion-signal-{seq}.bin'
            body.write_bytes(cs.encode_signal(operation, self.actor.ref.uid & 0xFFFFFFFF, args))
            (directory / f'companion-signal-{seq}.json').write_text(json.dumps(dict(
                schema='companion-native-item-signal-v2' if args else 'companion-native-signal-v1',
                transport='LOCAL_IPC', pid=123, birth=456, event_seq=seq, view_epoch=epoch,
                body_file=body.name)), encoding='utf-8')
            return asyncio.run(bridge._bridge_ingest(ctx, directory))

        self.assertEqual(send(1, 'bag-open-take', 7), 1)
        self.assertEqual(send(2, 'equipment-open', 3), 1)
        self.assertEqual(send(3, 'bag-open-take', 8), 1)
        self.assertEqual(ctx._companion_views[1]['epochs'], {'bag': 8, 'equipment': 3})
        entity = ctx.world.entities.get(self.actor.ref.uid)
        args = tuple(map(str, (2, entity.generation, 7, 30, 1)))
        before = self.store.restore(1), self.store.restore(2)
        ctx.world.drain(1)
        self.assertEqual(send(4, 'item-give', 7, args), 1)
        self.assertEqual(ctx._bridge_signals[-1]['status'], 'REFUSED')
        self.assertEqual(ctx._bridge_signals[-1]['error'], 'COMPANION_SIGNAL_VIEW_EPOCH_MISMATCH')
        notices = [wire for wire in ctx.world.drain(1) if int.from_bytes(wire[2:4], 'little') == 0x4EEA]
        self.assertEqual(len(notices), 1)
        with pb.parse_message(notices[0][4:-2]) as message:
            self.assertIn('이전 동료 창', bytes(message.occurrences(2)[0].value).decode('utf-8'))
        self.assertEqual((self.store.restore(1), self.store.restore(2)), before)
        self.assertFalse(self.bags.intent_path.exists())
        # A current request is still consumed and does not reset either window epoch.
        current = tuple(map(str, (2, entity.generation, 8, 30, 1)))
        self.assertEqual(send(5, 'item-give', 8, current), 1)
        self.assertEqual(ctx._bridge_signals[-1]['status'], 'OK')
        self.assertNotEqual((self.store.restore(1), self.store.restore(2)), before)
        self.assertEqual(ctx._companion_views[1]['epochs'], {'bag': 8, 'equipment': 3})

    def test_eight_slots_use_real_pc_save_and_unequip_changes_profile_and_wield(self):
        for index, template in enumerate(self.templates):
            self.give(11 + index)
            self.bags.set_equipped(2, self.member_item(template), True)
        state = self.bags.states[2]
        self.assertEqual(len(state.slots), 7)
        self.assertEqual(self.bags.equipment.restore(2, self.store.restore(2)), state)
        self.assertEqual(self.ctx.world.companion_looks[2]['stance'], 50)
        self.assertEqual(self.ctx.world.companion_profiles[2].ac, self.bags.calculated(2)[0].ac)
        equipped = {state.weapon_uid, *(v for _, v in state.slots)}
        self.assertEqual(len(equipped), 8)
        self.assertTrue(self.bags.equip(2, state.weapon_uid))
        self.assertEqual(self.bags.states[2].weapon_uid, 0)
        self.assertEqual(self.ctx.world.companion_looks[2]['stance'], 0)
        self.assertTrue(any(int.from_bytes(w[2:4], 'little') == 0x4ed5
                            for w in self.ctx.world.drain(1)))

    def test_give_keeps_bag_save_live_equipment_until_explicit_equip_and_reload(self):
        state = self.bags.states[2]
        look = dict(self.ctx.world.companion_looks[2])
        profile = self.ctx.world.companion_profiles[2]
        for source in (11, 13):  # staff230 and armor102
            self.give(source)
            self.assertEqual(self.bags.states[2], state)
            self.assertEqual(self.ctx.world.companion_profiles[2], profile)
            self.assertEqual(self.ctx.world.companion_looks[2], look)
        self.bags.set_equipped(2, self.member_item(230), True)
        self.bags.set_equipped(2, self.member_item(102), True)
        saved = self.bags.states[2]
        self.assertEqual(saved.weapon_uid, self.member_item(230))
        self.assertNotEqual(self.ctx.world.companion_profiles[2], profile)
        self.assertNotEqual(self.ctx.world.companion_looks[2]['stance'], look['stance'])
        restored = self.new_bags()
        restored.initialize(2)
        self.assertEqual(restored.states[2], saved)

    def test_member_twohand_shield_both_orders_refuse_without_save_or_live_change(self):
        before = self.bags.frames[2]
        frame = inventory.build_kit_frame([
            *(dict(row.raw_fields) for row in inventory.validate_kit_frame(before)),
            item(60, 11), item(61, 113), item(62, 230)])
        self.store.replace_kit(2, before, frame, append=True)
        self.bags.frames[2] = frame
        self.bags.set_equipped(2, self.bags.states[2].weapon_uid, False)
        prior_slots = self.bags.states[2].slots
        for first, second in ((60, 61), (61, 60)):
            with self.subTest(first=first):
                self.bags.set_equipped(2, first, True)
                state, raw = self.bags.states[2], self.bags.equipment.path.read_bytes()
                profile, look = self.ctx.world.companion_profiles[2], dict(self.ctx.world.companion_looks[2])
                with self.assertRaisesRegex(ValueError, 'EQUIPMENT_TWO_HANDED_SHIELD_CONFLICT'):
                    self.bags.set_equipped(2, second, True)
                self.assertEqual((self.bags.states[2], self.bags.equipment.path.read_bytes()), (state, raw))
                self.assertEqual((self.ctx.world.companion_profiles[2], self.ctx.world.companion_looks[2]),
                                 (profile, look))
                self.bags.set_equipped(2, first, False)
        for first, second in ((62, 61), (61, 62)):
            self.bags.set_equipped(2, first, True)
            self.bags.set_equipped(2, second, True)
            self.assertEqual((self.bags.states[2].weapon_uid, self.bags.states[2].slots),
                             (62, tuple(sorted(prior_slots + ((8, 61),)))))
            self.bags.set_equipped(2, first, False)
            self.bags.set_equipped(2, second, False)

    def test_member_class_and_registered_curse_removal_guards_keep_equipment(self):
        before = self.bags.frames[2]
        frame = inventory.build_kit_frame([
            *(dict(row.raw_fields) for row in inventory.validate_kit_frame(before)),
            item(60, 6), item(61, 230)])
        self.store.replace_kit(2, before, frame, append=True)
        self.bags.frames[2] = frame
        state, saved = self.bags.states[2], self.bags.equipment.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'COMPANION_CLASS_CANNOT_EQUIP'):
            self.bags.set_equipped(2, 60, True)
        self.ctx.chain_sync_hooks = Mock(return_value=True)
        for uid, equipped in ((state.weapon_uid, False), (61, True)):
            with self.assertRaisesRegex(ValueError, 'ITEM_USE_CURSED_EQUIPMENT_CANNOT_REMOVE'):
                self.bags.set_equipped(2, uid, equipped)
        self.assertEqual((self.bags.states[2], self.bags.equipment.path.read_bytes()), (state, saved))
        self.assertEqual(self.ctx.chain_sync_hooks.call_args.args[:3],
                         ('equipment_remove_blocked', 2, state.weapon_uid))

    def test_saved_resistance_reaches_registered_npc_consumers_and_bolt_uses_monster_mr(self):
        from types import MethodType
        from tools.local_original_session import world_combat as combat, world_registry
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_feature_magic as magic
        from tools.local_original_session import world_feature_monster_skills as skills
        from tools.local_original_session.world_bridge import Context

        ctx, view = self.ctx, self.ctx.world
        modules = (companion, magic, skills)
        ctx._world_registry = world_registry.build_registry(modules)
        ctx.collect_sync_hooks = MethodType(Context.collect_sync_hooks, ctx)
        for module in modules:
            for fn in module.METHODS:
                setattr(ctx, fn.__name__, MethodType(fn, ctx))
        ctx._companion_enabled = True
        ctx._companion_ailments = companion.CompanionAilments(view)
        ctx._world_magic_initialize()
        self.addCleanup(ctx._world_magic_stopped)
        ctx._monster_skills_initialize()
        self.record.hp = self.record.max_hp = 4000
        owner = view.combat.pcs[1]
        owner_before = owner.hp, owner.profile
        # Fixture supply only; subsequent equipment changes use normal saved CAS.
        before = self.bags.frames[2]
        frame = inventory.build_kit_frame([
            *(dict(row.raw_fields) for row in inventory.validate_kit_frame(before)),
            item(60, 501), item(61, 3937)])
        self.store.replace_kit(2, before, frame, append=True)
        self.bags.frames[2] = frame

        for producer in ('magic', 'monster_skills'):
            if producer == 'monster_skills':
                ctx._monster_skills_started()
                self.addCleanup(ctx._monster_skills_stopped)
            observed = []
            for phase in ('bare', 'equipped', 'restored', 'unequipped'):
                with self.subTest(producer=producer, phase=phase):
                    if phase in ('equipped', 'unequipped'):
                        self.assertTrue(self.bags.equip(2, 60))
                        self.assertTrue(self.bags.equip(2, 61))
                    elif phase == 'restored':
                        self.bags = self.new_bags()
                        self.bags.initialize(2)
                    target = ctx.collect_sync_hooks('npc_magic_target', self.actor.ref.uid)[0]
                    self.assertEqual(target.profile.resist_wind,
                                     20 if phase in ('equipped', 'restored') else 0)
                    enemy, monster = self.fixture.monster(7)  # sourced CallLightning
                    entity = view.entities.resolve(self.actor.ref)
                    view.entities.move(enemy.uid, entity.map_id, entity.x + 1, entity.y)
                    view._refresh(1)
                    hp_before = self.record.hp
                    view.combat.rng = Mock(randint=Mock(
                        side_effect=lambda low, high: 1 if high == 100 else high))
                    events = (ctx._world_magic_events if producer == 'magic'
                              else ctx._world_monster_skills_events)
                    count = len(events)
                    view.ai.on_hit(enemy.uid, entity.uid, self.fixture.now)
                    view.ai._act(enemy.uid, self.fixture.now)
                    self.assertEqual(len(events), count + 1)
                    event = events[-1]
                    self.assertEqual(event['target'], entity.uid)
                    self.assertGreater(event['mp_before'] - event['mp_after'], 0)
                    self.assertEqual(event['amount'], hp_before - self.record.hp)
                    self.assertEqual(event['trace']['mr'], target.profile.mr)
                    self.assertGreater(event['amount'], 0)
                    observed.append(event['amount'])
                    self.assertEqual((owner.hp, owner.profile), owner_before)
            self.assertLess(observed[1], observed[0])
            self.assertEqual(observed[1], observed[2])
            self.assertEqual(observed[0], observed[3])

        root = Path(__file__).parent / 'data' / 'companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        caster = companion.CompanionMagic(view, read('mage_spells'), read('mage_growth'),
            read('ai_policy'), {2: self.ctx._companion_rows[2]['attributes']}, display=False)
        from tools.local_original_session import ats_config_codec as codec
        caster.policy_for = lambda _: codec.companion_policy(codec.wrap_blob(
            codec.build_ats(sequence_spells=(3,))), {3: 'energy_bolt'})
        self.record.level = 5
        self.record.learned_spells = (0, 2, 3)
        self.record.mp = self.record.max_mp = 40
        self.record.combat_mode = 'ASSIST'
        enemy, _ = self.fixture.monster()
        group, slot = view.spawner.slot_for(enemy.uid)
        group.monster = replace(group.monster, mr=100)
        self.actor.target = enemy.ref
        params = caster.spells['energy_bolt']['formula']['parameters']
        dice = lambda: Mock(randint=Mock(side_effect=[5, 100]))
        expected = combat.magic_damage(params, 18, dice(), mr=100)
        self.assertLess(expected, combat.magic_damage(params, 18, dice(), mr=0))
        slot.hp = expected + 50  # survive the bolt: no kill/reward rolls on the mocked rng
        before_hp = slot.hp
        view.combat.rng = dice()
        self.assertTrue(caster.cast(self.actor, entity, enemy, 'energy_bolt', self.fixture.now))
        self.assertEqual(before_hp - slot.hp, expected)
        self.assertEqual(self.record.mp, 37)

    def test_capacity_rejects_before_debit_and_never_uses_owner_capacity(self):
        before = self.ctx.inventory_frame
        self.bags.weights[230] = replace(self.bags.weights[230], raw_weight=100_000_000)
        with self.assertRaisesRegex(ValueError, 'COMPANION_WEIGHT_CAPACITY'):
            self.give(11)
        self.assertEqual(self.store.restore(1), before)
        self.assertFalse(self.bags.intent_path.exists())

    def ground(self, *, owner=1, template=7, count=3):
        from tools.local_original_session.world_entities import Kind
        view = self.ctx.world
        self.ctx.starter_fields = item(100, 7)
        self.ctx.fold_sync_hooks = lambda _name, fields, _ground: fields
        self.bags.install_pickup()
        self.addCleanup(self.bags.pickup_handle.close)
        entity = view.entities.resolve(self.actor.ref)
        corpse = view.entities.add(Kind.NPC, entity.map_id, entity.x, entity.y,
                                  template_id=0)
        corpse = view.entities.kill(corpse.uid)
        return view.ground.spawn_drops(corpse.ref, ((template, count),), owner_uid=owner,
                                      now=self.fixture.now)[0]

    def test_f4_credits_only_saved_member_and_ground_once(self):
        drop = self.ground()
        before = self.ctx.inventory_frame
        self.bags.pickup(self.actor, drop, self.fixture.now)
        self.assertIsNone(self.ctx.world.ground.get(drop.ref))
        self.assertEqual(self.ctx.inventory_frame, before)
        self.assertEqual(self.store.restore(2), self.bags.frames[2])
        with self.assertRaisesRegex(ValueError, 'GROUND_ITEM_NOT_FOUND'):
            self.bags.pickup(self.actor, drop, self.fixture.now)

    def test_player_discard_is_pickable_by_companion_and_keeps_raw_enchant_fields(self):
        # Install the existing follower admission, then drop a real saved owner
        # item through the same ground owner used by the PC packet handler.
        reward = self.ground()
        self.ctx.world.ground._discard(reward.ref)
        view = self.ctx.world
        owner = view.entities.get(1)
        actor = view.entities.resolve(self.actor.ref)
        member = next(row for row in inventory.validate_kit_frame(self.ctx.inventory_frame)
                      if row.identifier == 11)
        fields = dict(member.raw_fields) | {5: 9, 18: b'+9 kept instance'}
        before = self.ctx.inventory_frame
        rows = [fields if row.identifier == 11 else dict(row.raw_fields)
                for row in inventory.validate_kit_frame(before)]
        self.store.replace_kit(1, before, inventory.build_kit_frame(rows))
        self.ctx.inventory_frame = before = self.store.restore(1)
        def debit(_item, _count):
            after = inventory.build_kit_frame([dict(row.raw_fields)
                for row in inventory.validate_kit_frame(before) if row.identifier != 11])
            self.store.commit_ground_kit(1, before, after)
            self.ctx.inventory_frame = after
            return ()
        drop, _ = view.ground.drop_from_pc(owner.ref, fields, 1,
                                          actor.x, actor.y, debit, now=self.fixture.now)
        self.bags.pickup(self.actor, drop, self.fixture.now)
        picked = inventory.validate_kit_frame(self.store.restore(2))[-1]
        self.assertEqual({k: v for k, v in picked.raw_fields if k not in (1, 4)},
                         {k: v for k, v in fields.items() if k not in (1, 4)})
        self.assertIsNone(view.ground.get(drop.ref))
        self.assertNotIn(11, [row.identifier for row in inventory.validate_kit_frame(self.store.restore(1))])

    def test_pickup_write_then_error_updates_member_cache_and_retires_ground(self):
        drop = self.ground()
        original = self.store._atomic_write
        def fail_after(rows):
            original(rows)
            raise OSError('COMPANION_AFTER_REPLACE')
        with patch.object(self.store, '_atomic_write', side_effect=fail_after):
            with self.assertRaisesRegex(RuntimeError, 'GROUND_INVENTORY_COMMIT_COMMITTED'):
                self.bags.pickup(self.actor, drop, self.fixture.now)
        self.assertEqual(self.bags.frames[2], self.store.restore(2))
        self.assertIsNone(self.ctx.world.ground.get(drop.ref))

    def test_ats_forecast_weight_refuses_without_ground_or_save_change(self):
        drop = self.ground(template=14)
        self.bags.policy_for = lambda _: {'pickup_weight': 0}
        before = self.bags.frames[2]
        with self.assertRaisesRegex(ValueError, 'COMPANION_ATS_PICKUP_WEIGHT'):
            self.bags.pickup(self.actor, drop, self.fixture.now)
        self.assertEqual(self.bags.frames[2], before)
        self.assertIsNotNone(self.ctx.world.ground.get(drop.ref))

    def test_ground_admission_uses_member_position_and_owner_priority(self):
        drop = self.ground()
        view = self.ctx.world
        owner = view.entities.get(1)
        view.entities.move(1, owner.map_id, 150, 150, owner.heading)
        self.bags.pickup(self.actor, drop, self.fixture.now)
        self.assertIsNone(view.ground.get(drop.ref))

    def test_f4_snapshot_does_not_autoloot_later_and_hold_does_not_move(self):
        drop = self.ground()
        entity = self.ctx.world.entities.resolve(self.actor.ref)
        self.bags.request_pickup(self.actor, self.fixture.now)
        self.assertEqual(len(self.actor.pickup_refs), 1)
        original = (entity.x, entity.y)
        self.bags.pickup_step(self.actor, entity, self.fixture.now)
        self.assertEqual((entity.x, entity.y), original)
        self.assertEqual(self.actor.pickup_refs, ())
        self.assertIsNone(self.ctx.world.ground.get(drop.ref))

    def test_foreign_owner_exclusive_drop_remains_and_wrapper_restores_pc_base(self):
        from tools.local_original_session.world_entities import Kind
        view = self.ctx.world
        view.entities.add(Kind.PC, 0, 100, 100, uid=3)
        base = view.ground.check_pickup
        drop = self.ground(owner=3)
        before = self.bags.frames[2]
        with self.assertRaisesRegex(ValueError, 'GROUND_OWNER_PRIORITY'):
            self.bags.pickup(self.actor, drop, self.fixture.now)
        self.assertEqual(self.bags.frames[2], before)
        self.assertIsNotNone(view.ground.get(drop.ref))
        self.bags.pickup_handle.close()
        self.assertEqual(view.ground.check_pickup, base)
        with self.assertRaisesRegex(ValueError, 'GROUND_CURRENT_ALIVE_PC_REQUIRED'):
            view.ground.check_pickup(self.actor.ref, drop.ref, drop.count, now=self.fixture.now)

    def test_owner_winning_race_leaves_no_member_credit(self):
        drop = self.ground()
        before = self.bags.frames[2]
        self.ctx.world.ground.pickup(self.ctx.world.entities.get(1).ref, drop.ref,
                                    drop.count, now=self.fixture.now)
        with self.assertRaisesRegex(ValueError, 'GROUND_ITEM_NOT_FOUND'):
            self.bags.pickup(self.actor, drop, self.fixture.now)
        self.assertEqual(self.bags.frames[2], before)

    def test_full_member_bag_refuses_and_keeps_ground(self):
        drop = self.ground(template=14)
        before = self.bags.frames[2]
        rows = [dict(row.raw_fields) for row in inventory.validate_kit_frame(before)]
        while len(rows) < inventory.KIT_MAX_ITEMS:
            rows.append(item(1000+len(rows), 7, name=str(len(rows)).encode()))
        frame = inventory.build_kit_frame(rows)
        self.store.replace_kit(2, before, frame, append=True)
        self.bags.frames[2] = frame
        with self.assertRaisesRegex(ValueError, 'COMPANION_PICKUP_INVENTORY_FULL'):
            self.bags.pickup(self.actor, drop, self.fixture.now)
        self.assertEqual(self.bags.frames[2], frame)
        self.assertIsNotNone(self.ctx.world.ground.get(drop.ref))

    def test_interrupt_after_owner_debit_recovers_forward_once_without_auto_equip(self):
        previous = self.bags.states[2]
        original = self.store.replace_kit
        def fail_target(uid, *args, **kwargs):
            if uid == 2:
                raise OSError('TARGET_WRITE_FAILED')
            return original(uid, *args, **kwargs)
        with patch.object(self.store, 'replace_kit', side_effect=fail_target):
            with self.assertRaisesRegex(OSError, 'TARGET_WRITE_FAILED'):
                self.give(11)
        self.assertTrue(self.bags.intent_path.exists())
        self.assertNotIn(11, [r.identifier for r in inventory.validate_kit_frame(self.store.restore(1))])
        intent = json.loads(self.bags.intent_path.read_text(encoding='utf-8'))
        self.assertEqual(intent['owner_uid'], 1)
        self.assertNotIn('auto_character', intent)
        self.assertNotIn('auto_uid', intent)
        # A pending journal from before this policy change still finishes its
        # rows forward, but its historical auto-equip markers grant no action.
        target_rows = inventory.validate_kit_frame(bytes.fromhex(intent['rows'][1]['after']))
        intent.pop('owner_uid')
        intent.update(auto_character=2, auto_uid=next(r.identifier for r in target_rows if r.template_bits == 230))
        self.bags.intent_path.write_text(json.dumps(intent), encoding='utf-8')
        recovered = self.new_bags()
        recovered.initialize(2)
        self.assertFalse(recovered.intent_path.exists())
        rows = inventory.validate_kit_frame(self.store.restore(2))
        staff = [r for r in rows if r.template_bits == 230]
        self.assertEqual(len(staff), 1)
        self.assertEqual(recovered.states[2], previous)
        self.assertEqual(self.ctx.inventory_frame, self.store.restore(1))
        again = self.new_bags()
        again.initialize(2)
        self.assertEqual(again.frames[2], recovered.frames[2])

    def test_equipped_owner_item_and_excess_quantity_cannot_be_given(self):
        state = self.bags.equipment.restore(1, self.ctx.inventory_frame)
        self.bags.equipment.compare_and_swap_kit(1, self.ctx.inventory_frame, state,
                                               weapon_uid=11, slots=())
        with self.assertRaisesRegex(ValueError, 'UNEQUIP_FIRST'):
            self.give(11)
        with self.assertRaisesRegex(ValueError, 'OWNED_QUANTITY'):
            self.give(30, 21)
        self.assertFalse(self.bags.intent_path.exists())

    def test_bridge_item_refusals_explain_unequip_and_quantity_without_mutating_saves(self):
        from tools.local_original_session import world_feature_companion_bridge as bridge
        from tools.local_entry_server import protobuf as pb
        ctx = self.ctx
        bridge._bridge_initialize(ctx)
        ctx.run_sync_hooks = lambda *args: None

        def rejected(operation, action, expected):
            before = self.store.restore(1), self.store.restore(2)
            ctx.world.drain(1)
            ctx.collect_sync_hooks = lambda *args: (action(),)
            result = bridge._bridge_dispatch(ctx, object(), 1,
                SimpleNamespace(operation=operation, actor_uid=self.actor.ref.uid & 0xFFFFFFFF), {})
            self.assertEqual(result['status'], 'REFUSED')
            notices = [wire for wire in ctx.world.drain(1) if int.from_bytes(wire[2:4], 'little') == 0x4EEA]
            self.assertEqual(len(notices), 1)
            with pb.parse_message(notices[0][4:-2]) as message:
                text = bytes(message.occurrences(2)[0].value).decode('utf-8')
            self.assertIn(expected, text)
            self.assertEqual((self.store.restore(1), self.store.restore(2)), before)
            self.assertFalse(self.bags.intent_path.exists())

        state = self.bags.equipment.restore(1, ctx.inventory_frame)
        worn = self.bags.equipment.compare_and_swap_kit(1, ctx.inventory_frame, state,
                                                       weapon_uid=11, slots=())
        rejected('item-give', lambda: self.give(11), '주인에게 장착된 아이템은 먼저 장착을 해제')
        rejected('item-give', lambda: self.give(30, 21), '수량이 부족')
        self.bags.equipment.compare_and_swap_kit(1, ctx.inventory_frame, worn, weapon_uid=0, slots=())
        self.give(11)
        self.bags.set_equipped(2, self.member_item(230), True)
        rejected('item-take', lambda: self.bags.take(1, self.actor, self.bags.states[2].weapon_uid,
            1, ctx.inventory_frame, owner_max_weight=10000), '동료에게 장착된 아이템은 먼저 장착을 해제')

    def test_enchant_metadata_survives_transfer_and_affects_damage(self):
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.ctx.inventory_frame)]
        rows[1][18] = enchanted_name(self.ctx.world.data.items[230], 3)
        changed = inventory.build_kit_frame(rows)
        self.store.replace_kit(1, self.ctx.inventory_frame, changed)
        self.ctx.inventory_frame = changed
        self.give(11)
        self.bags.set_equipped(2, self.member_item(230), True)
        self.assertEqual(self.ctx.world.companion_profiles[2].weapon.enchant, 3)

    def test_potions_consume_only_member_bag_and_persist_effect_without_refill(self):
        self.record.hp, self.record.mp = 1, 0
        self.give(30, 5)
        self.give(31, 2)
        self.configure_recovery(hp=(14,), mp=(492,))
        owner = self.store.restore(1)
        self.assertTrue(self.bags.potion(self.actor, 10))
        self.assertGreater(self.record.hp, 1)
        self.assertTrue(self.bags.potion(self.actor, 11))
        self.assertEqual(self.record.mp, 0)
        self.assertGreater(self.record.equipment['blue_expires_unix'], 0)
        self.assertEqual(self.store.restore(1), owner)
        frame = self.store.restore(2)
        reopened = self.new_bags()
        reopened.initialize(2)
        self.assertEqual(reopened.frames[2], frame)
        self.assertGreater(reopened.blue_until[2], self.ctx.world.runtime.clock())
        blue_count = sum(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(frame)
                         if r.template_bits == 492)
        self.assertEqual(blue_count, 1)

    def test_no_settings_empty_slots_and_zero_threshold_never_use_default_potions(self):
        self.record.hp, self.record.mp = 1, 0
        self.give(30, 2)
        self.give(31, 2)
        before = self.store.restore(2)
        self.assertFalse(self.bags.potion(self.actor, 10))
        self.configure_recovery()
        self.assertFalse(self.bags.potion(self.actor, 11))
        self.configure_recovery(hp=(14,), hp_percent=0)
        self.assertFalse(self.bags.potion(self.actor, 12))
        self.assertEqual(self.store.restore(2), before)
        self.assertEqual((self.record.hp, self.record.mp), (1, 0))

    def test_recovery_slots_precede_bag_order_and_depleted_stack_never_substitutes(self):
        self.record.hp, self.record.mp = 1, 0
        self.give(30, 1)
        self.give(31, 1)
        before = self.bags.frames[2]
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(before)]
        original = next(r for r in rows if r[2] == 14 and r[4] > 0)
        # Retire the old fixture stack; identity fields on an existing UID are
        # immutable. Append fresh stacks in the intended bag order via CAS.
        rows.remove(original)
        selected = dict(original)
        selected.update({1: 197, 3: 123})
        other = dict(original)
        other.update({1: 199, 3: 456, 4: 5})
        rows.extend((other, selected))
        changed = inventory.build_kit_frame(rows)
        self.store.replace_kit(2, before, changed, append=True)
        self.bags.frames[2] = changed
        policy = self.configure_recovery(hp=(14,))
        policy['potion_hp']['slots'] = [dict(status='valid', raw={1: 2, 4: 14, 5: 0, 6: 123})]
        self.assertTrue(self.bags.potion(self.actor, 10))
        self.record.hp = 1
        self.assertFalse(self.bags.potion(self.actor, 11))
        self.assertEqual(next(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(self.bags.frames[2])
                 if r.identifier == 199), 5)
        reopened = self.new_bags()
        reopened.initialize(2)
        reopened.policy_for = self.bags.policy_for
        self.record.hp = 1
        self.assertFalse(reopened.potion(self.actor, 12))
        # A different stack does not rearm this slot, including after an
        # identical autosave. An explicit changed selection is required.
        before = reopened.frames[2]
        refill = dict(selected)
        refill.update({1: 200, 3: 124, 4: 3})
        after = inventory.build_kit_frame([*(dict(r.raw_fields) for r in
            inventory.validate_kit_frame(before)), refill])
        self.store.replace_kit(2, before, after, append=True)
        reopened.frames[2] = after
        self.assertFalse(reopened.potion(self.actor, 13))
        policy['potion_hp']['slots'][0]['raw'][6] = 124
        policy['selection_id'] += ':new-selection'
        self.assertTrue(reopened.potion(self.actor, 14))

    def test_recovery_slot_order_and_self_threshold(self):
        self.give(30, 2)
        self.give(31, 1)
        self.record.hp, self.record.mp = self.record.max_hp, 0
        self.ctx.world.combat.pcs[1].hp = 1
        policy = self.configure_recovery(hp=(14,))
        self.assertFalse(self.bags.potion(self.actor, 10))
        # Both HP slots are usable; explicitly put the later bag row first.
        before = self.bags.frames[2]
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(before)]
        first = next(r for r in rows if r[2] == 14 and r[4] > 0)
        extra = dict(first)
        extra.update({1: 198, 3: 789, 4: 1})
        after = inventory.build_kit_frame([*rows, extra])
        self.store.replace_kit(2, before, after, append=True)
        self.bags.frames[2] = after
        policy['potion_hp']['slots'].insert(0, dict(status='valid', raw={1: 2, 4: 14, 5: 0, 6: 789}))
        self.record.hp = 1
        self.assertTrue(self.bags.potion(self.actor, 11))
        remaining = {r.identifier: dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(self.bags.frames[2])}
        self.assertNotIn(198, remaining)
        self.assertEqual(remaining[first[1]], 2)


class AtsItemSelectionTests(unittest.TestCase):
    def test_item_lookup_prefers_entity_key_and_depleted_anchor_does_not_rebind(self):
        rows = [item(1, 14, 5), item(2, 14, 1)]
        rows[1][3] = 123
        slot = dict(status='valid', raw={1: 2, 4: 14, 5: 0, 6: 123})
        self.assertIs(CompanionInventory.ats_item(rows, slot), rows[1])
        rows[1][4] = 0
        self.assertIsNone(CompanionInventory.ats_item(rows, slot))
        self.assertIs(CompanionInventory.ats_item(rows[:1], slot), rows[0])
        self.assertEqual(rows[0][4], 5)

    def test_incomplete_ambiguous_or_mismatched_identity_does_not_choose_bag_row(self):
        rows = [item(1, 14, 5), item(2, 14, 5)]
        slot = dict(status='valid', raw={1: 2, 4: 14, 5: 0, 6: 0})
        self.assertIsNone(CompanionInventory.ats_item(rows, slot))
        rows.pop()
        slot['raw'].update({5: 77, 6: 999})
        self.assertIsNone(CompanionInventory.ats_item(rows, slot))
        del slot['raw'][5]
        self.assertIsNone(CompanionInventory.ats_item(rows, slot))


    def test_unresolved_slot_normalizes_like_native_loadable_copy_with_default_metadata(self):
        from tools.local_original_session import ats_config_codec as codec
        row = item(1, 14, 5)
        del row[3], row[22]
        for key in (-1, (1 << 64) - 1, (1 << 63) + 7, 0):
            with self.subTest(key=key):
                saved = {4: 14, 5: 1, 6: key}
                wrapper = codec.wrap_blob(codec.build_ats(hp_templates=(saved,)))
                loaded = codec.decode_options(codec.unwrap_blob(codec.loadable_ats(wrapper)))['hp_slots'][0]
                self.assertEqual((loaded[5], loaded[6]), (0, 1))
                slot = dict(status='valid', raw={1: 2, **saved})
                self.assertIs(CompanionInventory.ats_item([row], slot), row)
                self.assertEqual(slot['raw'], {1: 2, **saved})  # no saved selection mutation

    def test_entity_key_precedes_template_and_subtype_and_fallback_uses_subtype(self):
        rows = [item(1, 14, 5), item(2, 15, 2)]
        rows[1].update({3: 123, 22: 9})
        slot = dict(status='valid', raw={1: 2, 4: 14, 5: 0, 6: 123})
        self.assertIs(CompanionInventory.ats_item(rows, slot), rows[1])
        slot['raw'].update({4: 15, 5: 9, 6: 999})
        self.assertIs(CompanionInventory.ats_item(rows, slot), rows[1])
        slot['raw'][5] = 0
        self.assertIsNone(CompanionInventory.ats_item(rows, slot))

    def test_ambiguous_entity_or_template_match_including_q0_never_picks_first(self):
        rows = [item(1, 14, 0), item(2, 14, 5)]
        slot = dict(status='valid', raw={1: 2, 4: 14, 5: 0, 6: 999})
        self.assertIsNone(CompanionInventory.ats_item(rows, slot))
        rows[0][3] = rows[1][3] = 123
        slot['raw'][6] = 123
        self.assertIsNone(CompanionInventory.ats_item(rows, slot))


class CompanionPotionFramesTests(unittest.TestCase):
    """Existing world visibility and real item frames; only disk CAS is mocked."""
    def setUp(self):
        from tools.local_original_session.world_item_effects import WorldItemEffects, load_effects
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.actor, self.record = self.fixture.view, self.fixture.actor, self.fixture.record
        self.view.update_pc(3, 0, 101, 100)
        self.view.update_pc(4, 0, 200, 200)
        self.pc_effects = WorldItemEffects(self.view.combat)
        self.bags = object.__new__(CompanionInventory)
        self.bags.ctx = SimpleNamespace(world=self.view)
        self.bags.frames = {2: inventory.build_kit_frame([
            item(50, 41), *(item(600 + template, template, 2) for template in (14, 15, 130, 17, 492))])}
        self.bags.states = {2: SimpleNamespace(item_uid=50)}
        self.bags.store = SimpleNamespace(replace_kit=Mock(return_value=True))
        self.bags.next_potion, self.bags.blue_until, self.bags.speed = {}, {}, {}
        self.bags.events, self.bags.item_effects = [], load_effects()
        self.bags.save = Mock()
        self.policy = dict(status='valid', selection_id='fixture', potion_hp={}, potion_mp={})
        self.bags.policy_for = lambda _: self.policy
        for uid in (1, 3, 4):
            self.view.drain(uid)

    def assert_visible_frames(self, expected):
        for uid in (1, 3):
            self.assertEqual(self.view.drain(uid), list(expected))
        self.assertEqual(self.view.drain(4), [])

    def test_heal_and_blue_emit_pc_use_sound_on_companion_actor_to_visible_viewers(self):
        from tools.local_original_session.hunt_bot import fields, scalar
        for index, template in enumerate((14, 15, 130, 492)):
            with self.subTest(template=template):
                self.record.hp, self.record.mp = 1, 0
                kind = 'mp' if template == 492 else 'hp'
                self.policy['potion_hp'], self.policy['potion_mp'] = {}, {}
                self.policy['potion_' + kind] = dict(threshold=0.5, slots=[
                    dict(status='valid', raw={1: 2, 4: template, 5: 1, 6: -1})])
                self.assertTrue(self.bags.potion(self.actor, 10 + index))
                expected = self.pc_effects.use_effect_frame(self.actor.ref.uid, template)
                self.assertIsNotNone(expected)
                self.assertEqual(scalar(fields(expected[4:-2]), 1), self.actor.ref.uid)
                self.assertNotEqual(self.actor.ref.uid, self.actor.character_id)
                self.assert_visible_frames((expected,))
                self.assertEqual(next(dict(r.raw_fields)[4] for r in
                    inventory.validate_kit_frame(self.bags.frames[2]) if r.template_bits == template), 1)
        self.bags.save.assert_called_with(self.actor.owner_ref.uid)

    def test_green_emits_pc_use_sound_then_same_speed_status_once(self):
        from tools.local_original_session.world_combat import speed_frame
        slot = dict(status='valid', raw={1: 2, 4: 17, 5: 1, 6: -1})
        self.assertTrue(self.bags.function_item(self.actor, 10, (slot,)))
        factor = self.bags.speed_factor(2, 10)
        self.assertLess(factor, 1)
        expected = (self.pc_effects.use_effect_frame(self.actor.ref.uid, 17),
                    speed_frame(self.actor.ref.uid, factor))
        self.assert_visible_frames(expected)
        self.assertFalse(self.bags.function_item(self.actor, 11, (slot,)))
        self.assert_visible_frames(())


if __name__ == '__main__':
    unittest.main()
