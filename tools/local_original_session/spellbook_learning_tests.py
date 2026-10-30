"""Development checks for existing learning owner; no sockets/native client.

Temporary real inventory/magic stores exercise the existing 0960 handler.
Owner readiness and runtime dispatch are isolated fixture boundaries, so these
checks are not normal-login/direct-packet or original-input PASS evidence.
"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import game_data, inventory, inventory_store
from tools.local_original_session import world_feature_magic as feature
from tools.local_original_session import world_magic as magic


DATA = Path(__file__).parent / 'data/m1/items_ext'


def book_rows():
    rows = []
    for filename in ('spellbooks.json', 'misc.json'):
        document = json.loads((DATA / filename).read_text(encoding='utf-8'))
        rows.extend(item for item in document['items'] if filename == 'spellbooks.json'
                    or item.get('catalog_kind', {}).get('value') == 'spellbook')
    return rows


def fields(uid, template, count):
    return {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 1, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0, 24: False, 25: 0, 26: False}


class MetadataTests(unittest.TestCase):
    def test_target_books_match_current_runtime_and_keep_unimplemented_books_inert(self):
        engine = magic.PlayerMagic(magic.load_catalog())
        loaded = game_data.load_m1()
        counts = dict(supported=0, conditional=0, deferred=0)
        for item in book_rows():
            book = item['id']['value']
            policy = item['learning_policy']['value']
            counts[policy['status']] += 1
            with self.subTest(book=book):
                self.assertIn(book, loaded.items)
                self.assertTrue(policy['reason'])
                spell = engine.books.get(book)
                self.assertEqual(item['use_enabled']['value'],
                                 spell is not None and spell.kind != 'unsupported')
                if spell is None:
                    self.assertEqual(policy['status'], 'deferred')
                    self.assertIn('Outside current player_spells', policy['reason'])
                else:
                    self.assertEqual(policy['spell_key'], spell.key)
                    self.assertEqual(policy['allowed_class_min_levels'],
                                     {str(k): v for k, v in spell.classes.items()})
                    if spell.kind == 'unsupported':
                        self.assertEqual(policy['reason'], magic.JOB_DEFERRED[spell.key])
        self.assertEqual(counts, dict(supported=14, conditional=8, deferred=23))

    def test_all_nine_conditional_spells_need_existing_selected_element(self):
        engine = magic.PlayerMagic(magic.load_catalog())
        conditional = []
        for spell in engine.spells.values():
            policy = spell.raw['player_policy']
            if not (policy.get('required_element') or policy.get('own_element_resist')):
                continue
            conditional.append(spell.key)
            cls, level = next(iter(spell.classes.items()))
            with self.subTest(key=spell.key):
                with self.assertRaisesRegex(ValueError, 'MAGIC_ELF_ELEMENT_REQUIRED'):
                    engine.learn(1, spell, cls, level)
                selected = policy.get('required_element', 'water')
                engine.select_element(1, selected)
                self.assertEqual(engine.learn(1, spell, cls, level), {spell.key})
                engine.select_element(1, None)
                self.assertFalse(engine.state(1).learned)
        self.assertEqual(set(conditional), {146, 147, 148, 150, 151, 162, 165, 167, 169})


class LearningHandlerTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self, book, count=2):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        profile = Path(temp.name) / 'characters.json'
        roster = inventory_store.realm.CharacterStore(profile)
        roster.create(inventory_store.realm.Creation('BookLearner', 0, 0, (13,) * 6))
        store = inventory_store.InventoryStore(profile, policy=inventory_store.POLICY,
                                               kit_policy=inventory.KIT_POLICY)
        before = inventory.build_kit_frame([fields(10, 1, 1), fields(11, book, count)])
        store.grant(1, before)
        engine = magic.PlayerMagic(magic.load_catalog())
        spell = engine.books.get(book)
        cls, level = next(iter(spell.classes.items())) if spell else (3, 99)
        state = SimpleNamespace(profile=SimpleNamespace(character_class=cls, level=level),
                                dead=False, hp=100)
        queued, sent = [], []
        async def dispatch(apply):
            return apply()
        world = SimpleNamespace(combat=SimpleNamespace(pcs={1: state}),
            runtime=SimpleNamespace(clock=lambda: 100, dispatch_now=dispatch),
            _queue=lambda uid, wire: queued.append(wire))
        def drain(uid):
            frames = tuple(queued)
            queued.clear()
            return frames
        world.drain = drain
        writer, row, game = object(), object(), object()
        ctx = SimpleNamespace(world=world, _world_magic=engine,
            _world_magic_store=magic.MagicStore(store), inventory_frame=before,
            _world_magic_errors=[], _world_magic_events=[],
            run_sync_hooks=lambda *args: None,
            _world_pcs={id(writer): (writer, 1)}, broker=SimpleNamespace(),
            _world_bound=lambda w: w is writer, _world_ready=lambda w, g: True,
            owner_current=lambda *args: True,
            realm=SimpleNamespace(registry=SimpleNamespace(resolve=lambda w: game),
                service=lambda w: SimpleNamespace(snapshot=lambda: None)))
        async def send(w, r, frames, lock):
            # Existing handler publishes only after both durable stores settle.
            self.assertEqual(store.restore(1), ctx.inventory_frame)
            self.assertEqual(magic.MagicStore(store).rows[1]['learned'],
                             sorted(engine.state(1).learned))
            sent.extend(frames)
        ctx._world_send = send
        frame = SimpleNamespace(opcode=0x0960, payload=pb.encode_uint32(1, 11)
            + pb.encode_bytes(2, pb.encode_uint32(1, 1)
                              + pb.encode_uint32(15, 0) + pb.encode_uint32(16, 0)))
        async def use():
            return await feature._world_magic_frame(ctx, writer, row, game, frame, None)
        return SimpleNamespace(ctx=ctx, engine=engine, spell=spell, state=state,
                               store=store, before=before, sent=sent, use=use)

    async def test_companion_learning_uses_magic_store_after_direct_learning_and_reload(self):
        from types import MethodType
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_registry
        from tools.local_original_session.world_bridge import Context
        from tools.local_original_session.world_companion import CompanionRecord

        engine = magic.PlayerMagic(magic.load_catalog())
        book = next(key for key, spell in engine.books.items() if spell.key == 3)
        case = self.fixture(book)
        ctx = case.ctx
        record = CompanionRecord(1, 2, 'fixture', level=5, learned_spells=(0, 2, 3))
        ctx._companion_enabled = True
        ctx.world.companions = SimpleNamespace(records={1: record})
        ctx._world_registry = world_registry.build_registry((feature, companion))
        ctx.collect_sync_hooks = MethodType(Context.collect_sync_hooks, ctx)
        ctx.run_sync_hooks = MethodType(Context.run_sync_hooks, ctx)
        for module in (feature, companion):
            for fn in module.METHODS:
                setattr(ctx, fn.__name__, MethodType(fn, ctx))
        root = Path(__file__).parent / 'data/companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        consumer = companion.CompanionMagic(ctx.world, read('mage_spells'),
            read('mage_growth'), read('ai_policy'), {1: (8, 7, 16, 18, 8, 18)},
            learned_for=lambda row: companion._companion_learned_spells(ctx, row))
        from tools.local_original_session import ats_config_codec as codec
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(sequence_spells=(3,))),
                                        {3: 'energy_bolt'})
        consumer.policy_for = lambda _: policy
        rt = SimpleNamespace(record=record)
        # Old companion.json learning is never imported or granted for free.
        self.assertFalse(consumer.eligible(rt, 'energy_bolt'))
        self.assertEqual(record.learned_spells, ())
        self.assertEqual(ctx._world_magic_store.rows, {})
        self.assertTrue(await case.use())  # real existing 0960 learning/CAS owner
        self.assertFalse(ctx._world_magic_errors)
        self.assertEqual(record.learned_spells, (3,))  # ATS's existing list reader
        self.assertTrue(consumer.eligible(rt, 'energy_bolt'))
        self.assertFalse(consumer.eligible(rt, 'heal'))
        remaining = next(row for row in inventory.validate_kit_frame(case.store.restore(1))
                         if row.identifier == 11)
        self.assertEqual(dict(remaining.raw_fields)[4], 1)
        # A never-selected companion reads the same durable row after restart.
        ctx._world_magic = magic.PlayerMagic(magic.load_catalog())
        ctx._world_magic_store = magic.MagicStore(case.store)
        record.learned_spells = (0, 2)
        companion._companion_learning_changed(ctx, 1)
        self.assertEqual(record.learned_spells, (3,))
        self.assertTrue(consumer.eligible(rt, 'energy_bolt'))
        self.assertNotIn(1, ctx._world_magic.states)  # no offline effect restore
        # Optional magic removal cannot fall back to companion.json authority.
        ctx._world_registry = world_registry.build_registry((companion,))
        self.assertFalse(consumer.eligible(rt, 'energy_bolt'))
        self.assertEqual(record.learned_spells, ())

    async def test_every_enabled_target_book_uses_existing_debit_4e60_and_restore(self):
        for index, item in enumerate(i for i in book_rows() if i['use_enabled']['value']):
            with self.subTest(book=item['id']['value']):
                count = 1 if index % 2 else 2
                case = self.fixture(item['id']['value'], count)
                policy = case.spell.raw['player_policy']
                if policy.get('required_element') or policy.get('own_element_resist'):
                    case.engine.select_element(1, policy.get('required_element', 'water'))
                self.assertTrue(await case.use())
                self.assertFalse(case.ctx._world_magic_errors)
                rows = inventory.validate_kit_frame(case.store.restore(1))
                remaining = next((dict(r.raw_fields)[4] for r in rows if r.identifier == 11), 0)
                self.assertEqual(remaining, count - 1)
                available = [wire for wire in case.sent if int.from_bytes(wire[2:4], 'little') == 0x4e60]
                self.assertEqual(available, [feature.available_frame({case.spell.key})])
                restored = magic.PlayerMagic(magic.load_catalog())
                restored.restore(1, magic.MagicStore(case.store).rows[1], 200)
                self.assertEqual(restored.state(1).learned, {case.spell.key})
                self.assertEqual(restored.state(1).elf_element, case.engine.state(1).elf_element)
                if count == 2:
                    before = case.store.restore(1)
                    case.sent.clear()
                    self.assertTrue(await case.use())
                    self.assertIn('MAGIC_ALREADY_LEARNED', case.ctx._world_magic_errors)
                    self.assertEqual(case.store.restore(1), before)
                    self.assertFalse(case.sent)

    async def test_class_level_and_missing_element_refusals_do_not_consume_or_save(self):
        for item in (i for i in book_rows() if i['use_enabled']['value']):
            for reason in ('MAGIC_CLASS_NOT_ALLOWED', 'MAGIC_LEVEL_TOO_LOW', 'MAGIC_ELF_ELEMENT_REQUIRED'):
                case = self.fixture(item['id']['value'])
                policy = case.spell.raw['player_policy']
                conditional = policy.get('required_element') or policy.get('own_element_resist')
                if reason.endswith('ELEMENT_REQUIRED') and not conditional:
                    continue
                if not reason.endswith('ELEMENT_REQUIRED') and conditional:
                    case.engine.select_element(1, policy.get('required_element', 'water'))
                if reason.endswith('CLASS_NOT_ALLOWED'):
                    case.state.profile.character_class = next(c for c in range(4) if c not in case.spell.classes)
                elif reason.endswith('LEVEL_TOO_LOW'):
                    case.state.profile.level -= 1
                with self.subTest(book=item['id']['value'], reason=reason):
                    self.assertTrue(await case.use())
                    self.assertIn(reason, case.ctx._world_magic_errors)
                    self.assertEqual(case.store.restore(1), case.before)
                    self.assertFalse(case.engine.state(1).learned)
                    self.assertFalse(case.ctx._world_magic_store.path.exists())
                    self.assertFalse(case.sent)

    async def test_deferred_books_remain_unlearned_and_unconsumed(self):
        for item in (i for i in book_rows() if not i['use_enabled']['value']):
            with self.subTest(book=item['id']['value']):
                case = self.fixture(item['id']['value'])
                claimed = await case.use()
                self.assertEqual(claimed, case.spell is not None)
                if claimed:
                    self.assertIn('MAGIC_EFFECT_UNSUPPORTED', case.ctx._world_magic_errors)
                self.assertEqual(case.store.restore(1), case.before)
                self.assertFalse(case.engine.state(1).learned)
                self.assertFalse(case.ctx._world_magic_store.path.exists())
                self.assertFalse(case.sent)


if __name__ == '__main__':
    unittest.main()
