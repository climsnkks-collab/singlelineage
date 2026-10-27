"""M3 development checks: no game, sockets, ports or user profiles."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, world_magic as m
from tools.local_original_session import world_feature_magic as f


def fields(uid, template=1, count=1):
    return {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 1, 9: 0, 10: 0,
        13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0, 24: False, 25: 0, 26: False}


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.magic = m.PlayerMagic(m.load_catalog())

    def test_five_tier_catalog_keeps_original_sixteen_and_explicit_supported_subset(self):
        self.assertEqual(set(self.magic.spells), set(range(40)) - {23})
        self.assertEqual({s.key for s in self.magic.spells.values() if s.kind != 'unsupported'},
                         set(range(40)) - {23, 35})
        self.assertEqual(self.magic.spells[2].duration, 1200)
        self.assertEqual(self.magic.spells[5].mp, 3)

    def test_retained_catalyst_and_book_weight_resolve_without_generic_item_guess(self):
        self.assertEqual(self.magic.item_raw_weight(166), 2000)
        self.assertEqual(self.magic.item_raw_weight(164),
                         self.magic.books[164].raw['player_policy']['book_raw_weight']['value'])
        with self.assertRaises(KeyError):
            self.magic.item_raw_weight(0xffffffff)

    def test_learning_is_proposal_class_level_and_duplicate_do_not_mutate(self):
        spell = self.magic.spells[3]
        for cls, level, error in ((3, 3, 'LEVEL_TOO_LOW'), (1, 49, 'LEVEL_TOO_LOW')):
            with self.subTest(cls=cls), self.assertRaisesRegex(ValueError, error):
                self.magic.learn(1, spell, cls, level)
        with self.assertRaisesRegex(ValueError, 'CLASS_NOT_ALLOWED'):
            self.magic.learn(1, self.magic.spells[14], 1, 99)
        self.assertFalse(self.magic.state(1).learned)
        proposed = self.magic.learn(1, spell, 3, 4)
        self.assertEqual(proposed, {3})
        self.assertFalse(self.magic.state(1).learned)
        self.magic.state(1).learned = proposed
        with self.assertRaisesRegex(ValueError, 'ALREADY_LEARNED'):
            self.magic.learn(1, spell, 3, 4)

    def test_admission_and_shared_cooldown_preserve_resources_on_refusal(self):
        self.magic.state(1).learned = {0, 2, 3, 14}
        spell = self.magic.admit_cast(1, 3, 3, 8, 3, True, 100)
        self.magic.committed(1, spell, 100)
        for key, mp, alive, at, reason in ((0, 20, True, 100.9, 'REUSE'),
                (3, 2, True, 101, 'INSUFFICIENT_MP'),
                (3, 20, False, 101, 'LIVING_CASTER'), (1, 20, True, 101, 'NOT_LEARNED')):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.magic.admit_cast(1, key, 3, 8, mp, alive, at)
        self.assertEqual(self.magic.state(1).next_cast_at, 101)
        self.magic.admit_cast(1, 0, 3, 8, 4, True, 101)

    def test_incomplete_effect_books_are_not_consumed_or_learned(self):
        spell = replace(self.magic.spells[1], kind='unsupported')
        with self.assertRaisesRegex(ValueError, 'EFFECT_UNSUPPORTED'):
            self.magic.learn(1, spell, 3, 99)
        self.assertFalse(self.magic.state(1).learned)

    def test_duration_expiry_snapshot_reconnect_and_offline_elapsed(self):
        self.magic.state(1).learned = {2}
        self.magic.committed(1, self.magic.spells[2], 100)
        row = self.magic.snapshot(1, 110, wall=1000)
        fresh = m.PlayerMagic(m.load_catalog())
        fresh.restore(1, row, 500, wall=1005)
        self.assertEqual(fresh.state(1).buffs, {2: 1685})
        self.assertEqual(fresh.ac_bonus(1, 1684.99), -2)
        self.assertEqual(fresh.expire(1685), (1,))
        self.assertEqual(fresh.ac_bonus(1, 1685), 0)
        fresh.restore(1, row, 500, wall=3000)
        self.assertEqual(fresh.state(1).buffs, {})

    def test_every_spell_can_be_learned_and_admitted_after_prior_reuse(self):
        now = 100
        for key, spell in sorted(self.magic.spells.items()):
            if spell.kind == 'unsupported':
                continue
            self.magic.state(1).learned = self.magic.learn(1, spell, 3, 30)
            self.assertIs(self.magic.admit_cast(1, key, 3, 30, spell.mp, True, now), spell)
            self.magic.committed(1, spell, now)
            now += spell.reuse
        self.assertEqual(self.magic.state(1).learned,
                         {key for key, spell in self.magic.spells.items() if spell.kind != 'unsupported'})

    def test_new_tiers_reject_low_level_wrong_class_and_mp_without_commit(self):
        for key in (17, 18, 19, 20, 22, 25, 26, 27, 28, 30, 31, 32, 33, 34, 36, 37, 38, 39):
            spell = self.magic.spells[key]
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'LEVEL_TOO_LOW'):
                    self.magic.learn(1, spell, 3, spell.classes[3] - 1)
                wrong = next(cls for cls in range(4) if cls not in spell.classes)
                with self.assertRaisesRegex(ValueError, 'CLASS_NOT_ALLOWED'):
                    self.magic.learn(1, spell, wrong, 99)
                self.magic.state(1).learned.add(key)
                with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_MP'):
                    self.magic.admit_cast(1, key, 3, 30, spell.mp - 1, True, 100)
                self.assertFalse(self.magic.state(1).next_cast_at)
                self.assertFalse(self.magic.state(1).buffs)

    def test_all_declared_unsupported_books_refuse_learning_and_saved_key_cast(self):
        for key, spell in self.magic.spells.items():
            if spell.kind != 'unsupported':
                continue
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'EFFECT_UNSUPPORTED'):
                    self.magic.learn(1, spell, 3, 99)
                self.assertNotIn(key, self.magic.state(1).learned)
                self.magic.state(1).learned.add(key)
                with self.assertRaisesRegex(ValueError, 'EFFECT_UNSUPPORTED'):
                    self.magic.admit_cast(1, key, 3, 99, 999, True, 100)
                self.assertFalse(self.magic.state(1).next_cast_at)

    def test_five_buffs_weapon_identity_statuses_and_offline_elapsed_restore(self):
        magic = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        state = magic.state(1)
        state.learned = set(range(16))
        for key in (1, 2, 7, 11, 13):
            magic.committed(1, magic.spells[key], 100)
        state.weapon_uids = {7: 456, 11: 456}
        state.invisible_until = 110
        state.poison = dict(until=110, next_tick=103, tick_seconds=3.0, damage=5, source_uid=2)
        row = magic.snapshot(1, 101, wall=1000)
        fresh = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        restored = fresh.restore(1, row, 500, wall=1002)
        self.assertEqual(set(restored.buffs), {1, 2, 7, 11, 13})
        self.assertEqual(set(restored.buffs.values()), {507})
        self.assertEqual(restored.weapon_uids, {7: 456, 11: 456})
        self.assertTrue(fresh.is_lit(1, 506))
        self.assertTrue(fresh.is_poisoned(1, 506))
        self.assertTrue(fresh.is_invisible(1, 506))
        self.assertEqual(fresh.expire(507), (1,))
        self.assertFalse(restored.buffs)
        self.assertFalse(restored.weapon_uids)
        self.assertIsNone(restored.poison)
        self.assertFalse(restored.invisible_until)
        restored = fresh.restore(1, row, 500, wall=1020)
        self.assertFalse(restored.buffs)
        self.assertIsNone(restored.poison)
        self.assertFalse(fresh.is_invisible(1, 500))

    def test_legacy_row_without_statuses_still_restores(self):
        row = dict(uid=1, learned=[2], buffs=[dict(spell=2, remaining=10)],
                   reuse_remaining=0, saved_at=1000)
        state = self.magic.restore(1, row, 500, wall=1001)
        self.assertEqual(state.buffs, {2: 509})
        self.assertIsNone(state.poison)

    def test_new_armor_and_dexterity_saved_identity_expiry_and_offline_reconnect(self):
        magic = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        state = magic.state(1)
        state.learned = {2, 20, 25}
        for key in sorted(state.learned):
            magic.committed(1, magic.spells[key], 100)
        state.armor_uids[20] = 450
        self.assertEqual(magic.ac_bonus(1, 101, armor_uid=450), -5)
        self.assertEqual(magic.ac_bonus(1, 101, armor_uid=451), -2)
        self.assertEqual(magic.dexterity_bonus(1, 101), 5)
        row = magic.snapshot(1, 101, wall=1000)
        fresh = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        restored = fresh.restore(1, row, 500, wall=1002)
        self.assertEqual(restored.armor_uids, {20: 450})
        self.assertEqual(fresh.ac_bonus(1, 506, armor_uid=450), -5)
        self.assertEqual(fresh.dexterity_bonus(1, 506), 5)
        self.assertEqual(fresh.expire(507), (1,))
        self.assertFalse(restored.armor_uids)
        self.assertEqual(fresh.ac_bonus(1, 507, armor_uid=450), 0)
        self.assertEqual(fresh.dexterity_bonus(1, 507), 0)
        restored = fresh.restore(1, row, 500, wall=1020)
        self.assertFalse(restored.buffs)
        self.assertFalse(restored.armor_uids)

    def test_new_statuses_roundtrip_offline_elapsed_and_expiry(self):
        magic = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        state = magic.state(1)
        state.learned = {19, 28, 30, 31, 32, 39}
        kinds = ('blind', 'slow', 'counter_magic', 'meditation', 'paralyze', 'darkness')
        for key, kind in zip(sorted(state.learned), kinds):
            magic.apply_status(1, kind, 100, 10, source_uid=2, spell=key,
                               params={'fixture': 1})
        row = magic.snapshot(1, 101, wall=1000)
        # Exercise the existing durable schema validator as well as restore.
        m._row(row)
        fresh = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        restored = fresh.restore(1, row, 500, wall=1002)
        self.assertEqual(set(restored.effects), set(kinds))
        for kind in kinds:
            self.assertIsNotNone(fresh.status(1, kind, 506.99))
            self.assertEqual(restored.effects[kind]['source_uid'], 2)
            self.assertEqual(restored.effects[kind]['params'], {'fixture': 1})
        self.assertEqual(fresh.expire(507), (1,))
        self.assertFalse(restored.effects)
        self.assertFalse(fresh.restore(1, row, 500, wall=1020).effects)

    def test_counter_magic_is_one_absorption_and_has_real_expiry(self):
        self.magic.state(1)
        self.magic.apply_status(1, 'counter_magic', 100, 10, source_uid=1, spell=30)
        self.assertTrue(self.magic.consume_counter(1, 101))
        self.assertFalse(self.magic.consume_counter(1, 101))
        self.magic.apply_status(1, 'counter_magic', 100, 10, source_uid=1, spell=30)
        self.assertFalse(self.magic.consume_counter(1, 110))

    def test_weapon_damage_permanent_save_reconnect_and_exact_weapon_repair(self):
        self.magic.state(1).learned = {26}
        self.magic.apply_status(1, 'weapon_break', 100, None, source_uid=2, spell=26,
                               params={'weapon_uid': 500, 'damage_multiplier': .5})
        row = self.magic.snapshot(1, 101, wall=1000)
        m._row(row)
        restored = self.magic.restore(1, row, 500, wall=100000)
        self.assertIsNone(restored.effects['weapon_break']['until'])
        self.assertIsNotNone(self.magic.status(1, 'weapon_break', 999999))
        self.magic.clear_weapon_damage(1, 501)
        self.assertIsNotNone(self.magic.status(1, 'weapon_break', 999999))
        self.magic.clear_weapon_damage(1, 500)
        self.assertIsNone(self.magic.status(1, 'weapon_break', 999999))

    def test_npc_statuses_require_current_generation_and_are_not_character_saves(self):
        from tools.local_original_session.world_entities import EntityRef
        ref = EntityRef(123, 1)
        self.magic.apply_status(123, 'slow', 100, 10, source_uid=1,
                               spell=28, target_ref=ref)
        self.assertNotIn(123, self.magic.states)
        self.assertIsNotNone(self.magic.status(123, 'slow', 101))
        self.magic.apply_status(123, 'blind', 101, 10, source_uid=1,
                               spell=19, target_ref=EntityRef(123, 2))
        self.assertIsNone(self.magic.status(123, 'slow', 101))
        self.assertIsNotNone(self.magic.status(123, 'blind', 101))


class StatusAiConsumerTests(unittest.TestCase):
    """Real scheduler/AI with explicit development status input, no sockets."""
    def make(self, **changes):
        from tools.local_original_session.npc_ai_range_tests import AiRangeTests
        self.fixture = AiRangeTests()
        self.fixture.make(**changes)
        self.magic = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        self.magic.state(1)
        self.fixture.view.magic_status = self.status
        return self.fixture

    def status(self, uid, now):
        from tools.local_original_session.world_magic_status import ai_status
        row = self.magic.npc_statuses.get(uid, {})
        return ai_status(row.get('effects', {}), now)

    def apply(self, kind, duration=10):
        fxt = self.fixture
        self.magic.apply_status(fxt.mob.uid, kind, fxt.now, duration,
                               source_uid=1, target_ref=fxt.mob.ref)

    def test_paralyzed_monster_neither_moves_nor_attacks_then_resumes(self):
        fxt = self.make(attack_range=1)
        fxt.move_pc(106, 100)
        self.apply('paralyze', 4)
        fxt.hit()
        fxt.run_due(103.99)
        self.assertEqual((fxt.steps, fxt.attacks), ([], []))
        fxt.run_due(104.5)
        self.assertTrue(fxt.steps)
        self.assertFalse(fxt.attacks)
        # At point blank the same input blocks attacks too.
        fxt.move_pc(fxt.mob.x + 1, fxt.mob.y)
        self.apply('paralyze', 4)
        count = len(fxt.attacks)
        fxt.run_due(107.99)
        self.assertEqual(len(fxt.attacks), count)
        fxt.run_due(109)
        self.assertGreater(len(fxt.attacks), count)

    def test_slow_is_consumed_by_actual_move_and_attack_deadlines(self):
        fxt = self.make(attack_range=1)
        self.apply('slow')
        fxt.hit()
        self.assertEqual(len(fxt.steps), 1)
        move_interval = fxt.brain.monster.move_interval_ms / 1000
        self.assertAlmostEqual(fxt.brain.next_move_at, fxt.now + move_interval * 2)
        fxt.run_due(fxt.now + move_interval)
        self.assertEqual(len(fxt.steps), 1)
        fxt.move_pc(fxt.mob.x + 1, fxt.mob.y)
        fxt.run_due(fxt.brain.next_move_at)
        self.assertEqual(len(fxt.attacks), 1)
        attack_interval = fxt.brain.monster.attack_interval_ms / 1000
        self.assertAlmostEqual(fxt.brain.next_attack_at, fxt.now + attack_interval * 2)

    def test_missing_optional_status_callback_preserves_existing_ai(self):
        fxt = self.make()
        del fxt.view.magic_status
        fxt.hit()
        self.assertEqual((len(fxt.attacks), fxt.steps), (1, []))


class CodecTests(unittest.TestCase):
    def test_cast_native_target_and_optional_metadata(self):
        child = pb.encode_uint32(1, 0x20000000) + pb.encode_uint32(3, 32590) + pb.encode_uint32(4, 32880)
        self.assertEqual(f.decode_cast(pb.encode_uint32(1, 3) + pb.encode_bytes(2, child)),
                         (3, 0x20000000))
        signed = pb.encode_varint(8) + pb.encode_varint((1 << 64) - 3)
        self.assertEqual(f.decode_cast(pb.encode_uint32(1, 3) + pb.encode_bytes(2, signed)),
                         (3, 0xfffffffd))
        self.assertEqual(f.decode_cast(pb.encode_uint32(1, 0)), (0, None))

    def test_malformed_requests_refused_and_available_key_zero_present(self):
        good = pb.encode_uint32(1, 3)
        for raw in (b'', good + good, good + pb.encode_uint32(2, 1),
                good + pb.encode_bytes(2, pb.encode_uint32(1, 1) * 2),
                good + pb.encode_bytes(2, pb.encode_uint32(15, 0))):
            with self.subTest(raw=raw), self.assertRaises((ValueError, pb.WireError)):
                f.decode_cast(raw)
        wire = f.available_frame({0, 2, 3})
        self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x4e60)
        with pb.parse_message(wire[4:-2]) as outer:
            with pb.parse_message(bytes(outer.occurrences(1)[0].value)) as first:
                self.assertEqual(first.occurrences(1)[0].value, 0)
                self.assertEqual(first.occurrences(2)[0].value, 1)


class ResourceMutationTests(unittest.TestCase):
    def test_catalyst_consumption_preserves_unrelated_existing_zero_count_row(self):
        before = inventory.build_kit_frame([fields(10, 123, 0), fields(11, 166, 2)])
        updated, frames = m.material_mutation(before, [{'classic_item_key': 166, 'count': 1}])
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(updated)]
        self.assertEqual([(row[1], row[2], row[4]) for row in rows],
                         [(10, 123, 0), (11, 166, 1)])
        self.assertEqual(len(frames), 1)

    def test_last_singleton_catalyst_keeps_real_uid_as_zero_count_anchor(self):
        before = inventory.build_kit_frame([fields(11, 166, 1)])
        updated, frames = m.material_mutation(before, [{'classic_item_key': 166, 'count': 1}])
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(updated)]
        self.assertEqual([(row[1], row[2], row[4]) for row in rows], [(11, 166, 0)])
        self.assertEqual(len(frames), 1)
        self.assertNotEqual(int.from_bytes(frames[0][2:4], 'little'), 0x0978)


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        # Pure journal tests use an explicit fake CAS participant. Actual
        # InventoryStore/loopback verification remains the integration lane;
        # its unrelated stale source pin must never be patched around here.
        class KitCas:
            def __init__(self, profile):
                self.profile, self.frames = profile, {}
            def grant(self, uid, frame):
                self.frames[uid] = frame
            def restore(self, uid):
                return self.frames.get(uid)
            def replace_kit(self, uid, before, after):
                m.need(self.restore(uid) == before, 'INVENTORY_STORE_EXPECTED_FRAME_CHANGED')
                self.frames[uid] = after
                return before != after
        self.inv = KitCas(self.profile)
        self.before = inventory.build_kit_frame([fields(10), fields(11, 182, 2)])
        self.other = inventory.build_kit_frame([fields(20)])
        self.inv.grant(1, self.before)
        self.inv.grant(2, self.other)
        self.after, _ = m.book_mutation(self.before, 11)
        self.magic = m.PlayerMagic(m.load_catalog())
        self.proposed = self.magic.snapshot(1, 100, wall=1000, learned={3})
        self.store = m.MagicStore(self.inv)

    def assert_finished(self, store):
        self.assertEqual(self.inv.restore(1), self.after)
        self.assertEqual(self.inv.restore(2), self.other)
        self.assertEqual(store.rows[1]['learned'], [3])
        self.assertFalse(store.intent_path.exists())

    def test_one_book_durable_and_other_character_preserved(self):
        self.store.learn(self.proposed, self.before, self.after)
        self.assert_finished(m.MagicStore(self.inv))
        self.assertEqual(dict(inventory.validate_kit_frame(self.after)[1].raw_fields)[4], 1)

    def test_interrupt_before_inventory_completes_forward_once(self):
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('disk write unavailable')):
            with self.assertRaises(OSError):
                self.store.learn(self.proposed, self.before, self.after)
        self.assertEqual(self.inv.restore(1), self.before)
        self.assert_finished(m.MagicStore(self.inv))

    def test_interrupt_after_inventory_does_not_consume_again(self):
        with patch.object(self.store, '_write', side_effect=OSError('magic write unavailable')):
            with self.assertRaises(OSError):
                self.store.learn(self.proposed, self.before, self.after)
        self.assertEqual(self.inv.restore(1), self.after)
        with self.assertRaisesRegex(ValueError, 'RECOVERY_REQUIRED'):
            self.store.save(self.proposed)
        self.assert_finished(m.MagicStore(self.inv))

    def test_changed_inventory_is_not_overwritten_by_learning_recovery(self):
        changed = inventory.build_kit_frame([fields(10), fields(11, 182, 5)])
        self.inv.replace_kit(1, self.before, changed)
        with self.assertRaisesRegex(ValueError, 'EXPECTED_FRAME_CHANGED'):
            self.store.learn(self.proposed, self.before, self.after)
        with self.assertRaisesRegex(ValueError, 'INVENTORY_CONFLICT'):
            m.MagicStore(self.inv)
        self.assertEqual(self.inv.restore(1), changed)

    def test_supplied_kit_owner_migrates_removed_anchor_during_startup_recovery(self):
        self.before = inventory.build_kit_frame([fields(11, 182), fields(10)])
        self.inv.grant(1, self.before)
        self.after, _ = m.book_mutation(self.before, 11)
        anchor, calls = [11], []
        def kit_owner(uid, before, after):
            calls.append((uid, before, after))
            if len(calls) == 1:
                raise OSError('interrupted before joint inventory/equipment save')
            changed = self.inv.replace_kit(uid, before, after)
            anchor[0] = inventory.validate_kit_frame(after)[0].identifier
            return changed
        self.store = m.MagicStore(self.inv, replace_kit=kit_owner)
        with self.assertRaises(OSError):
            self.store.learn(self.proposed, self.before, self.after)
        self.assertEqual(anchor[0], 11)
        recovered = m.MagicStore(self.inv, replace_kit=kit_owner)
        self.assert_finished(recovered)
        self.assertEqual(anchor[0], 10)
        self.assertEqual(calls, [(1, self.before, self.after)] * 2)

    def test_completed_kit_owner_is_not_replayed_after_magic_write_failure(self):
        calls = []
        def kit_owner(uid, before, after):
            calls.append(uid)
            return self.inv.replace_kit(uid, before, after)
        self.store = m.MagicStore(self.inv, replace_kit=kit_owner)
        with patch.object(self.store, '_write', side_effect=OSError('magic save interrupted')):
            with self.assertRaises(OSError):
                self.store.learn(self.proposed, self.before, self.after)
        recovered = m.MagicStore(self.inv, replace_kit=kit_owner)
        self.assert_finished(recovered)
        self.assertEqual(calls, [1])


class WorldConsumerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from tools.local_original_session.world_companion_integration_tests import CompanionWorldViewTests
        self.fixture = CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view = self.fixture.view
        self.view.light_sources = {}
        self.state = self.view.combat.pcs[1]
        self.state.profile = replace(self.state.profile, level=8, character_class=3)
        self.state.status_fields[12] = self.state.status_fields[13] = 100
        self.magic = m.PlayerMagic(m.load_catalog(), buff_seconds=10)
        self.magic.state(1).learned = set(range(16))
        self.saved = []
        self.writer = object()
        self.ctx = SimpleNamespace(world=self.view, _world=self.view, _world_magic=self.magic,
            _world_magic_events=[], _world_magic_errors=[], _world_magic_store=SimpleNamespace(
                save=lambda row: self.saved.append(row)), _world_magic_writers={},
            _world_magic_buff_ui=False, _world_magic_icons={}, _world_magic_next_icon=0x31000000,
            _world_pcs={id(self.writer): (self.writer, 1)}, _world_lawful={1: 500},
            realm=SimpleNamespace(service=lambda w: SimpleNamespace(snapshot=lambda: SimpleNamespace(uid=1))))
        for fn in f.METHODS:
            setattr(self.ctx, fn.__name__, MethodType(fn, self.ctx))
        self.ctx._world_stats_for = lambda *args, **kw: (SimpleNamespace(
            attributes=SimpleNamespace(intelligence=18),
            weight=SimpleNamespace(normal_skill_blocked=False)), (), {})
        self.ctx._world_recalculate_uid = lambda uid: setattr(self.state, 'profile',
            replace(self.state.profile, ac=10 + self.magic.ac_bonus(uid, self.fixture.now)))
        self.ctx._world_bound = lambda writer: id(writer) in self.ctx._world_pcs
        self.view.drain(1)

    def enemy(self):
        target, _ = self.fixture.monster()
        self.view.entities.move(target.uid, 0, 103, 100)
        self.view._refresh(1)
        return target

    def test_damage_each_supported_spell_and_reuse_no_extra_mp(self):
        for key in (3, 5, 6, 14, 15):
            target = self.enemy()
            before = self.view.spawner.slot_for(target.uid)[1].hp
            self.fixture.now += 2
            self.ctx._world_magic_cast(1, key, target.uid, self.fixture.now)
            after = self.view.spawner.slot_for(target.uid)[1].hp
            self.assertLess(after, before)
            mp = self.state.mp
            with self.assertRaisesRegex(ValueError, 'REUSE'):
                self.ctx._world_magic_cast(1, key, target.uid, self.fixture.now + .1)
            self.assertEqual(self.state.mp, mp)
        self.assertEqual(self.state.mp, 85)

    def test_refused_target_and_resources_unchanged(self):
        target = self.enemy()
        for mode, reason in (('range', 'OUT_OF_RANGE'), ('map', 'SAME_MAP'), ('ally', 'HOSTILE')):
            self.view.entities.move(target.uid, 0, 103, 100)
            uid = target.uid
            if mode == 'range':
                self.view.entities.move(uid, 0, 115, 100)
            elif mode == 'map':
                self.view.entities.move(uid, 1, 103, 100)
            else:
                uid = self.fixture.actor.ref.uid
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, reason):
                self.ctx._world_magic_cast(1, 3, uid, self.fixture.now)
            self.assertEqual(self.state.mp, 100)
            self.assertFalse(self.magic.state(1).next_cast_at)

    async def test_heal_and_shield_expiry_use_actual_world_tick_without_input(self):
        self.state.hp = 1
        self.ctx._world_magic_cast(1, 0, 1, self.fixture.now)
        self.assertGreater(self.state.hp, 1)
        self.assertEqual(self.state.mp, 96)
        self.fixture.now += 2
        self.ctx._world_magic_cast(1, 2, 1, self.fixture.now)
        self.assertEqual(self.state.profile.ac, 8)
        self.ctx._world_magic_started()
        self.fixture.now += 10
        await self.view.runtime.tick_once(self.fixture.now)
        self.assertEqual(self.state.profile.ac, 10)
        self.assertFalse(self.magic.state(1).buffs)
        self.assertTrue(any(e['outcome'] == 'expired' for e in self.ctx._world_magic_events))

    def test_heal_final_status_consumes_actual_hp_and_debited_mp(self):
        self.state.hp = 1
        self.state.status_fields[10] = 1
        self.ctx._world_magic_cast(1, 0, 1, self.fixture.now)
        self.assertGreater(self.state.hp, 1)
        # The resource owner's HP changes without refreshing the cached field.
        self.assertEqual(self.state.status_fields[10], 1)
        statuses = []
        for wire in self.view.drain(1):
            if int.from_bytes(wire[2:4], 'little') == 0x4e38:
                with pb.parse_message(wire[4:-2]) as message:
                    statuses.append((message.occurrences(10)[0].value,
                                     message.occurrences(12)[0].value))
        self.assertGreaterEqual(len(statuses), 2)
        self.assertTrue(all(hp == self.state.hp for hp, _ in statuses))
        self.assertEqual(statuses[-1], (self.state.hp, self.state.mp))
        self.assertEqual(statuses[-1][1], 96)

    def test_spell_exp_self_support_effects_reach_the_selected_pc(self):
        self.assertNotIn(1, self.view.visibility.known.get(1, ()))
        for key, gfx in ((0, 744), (2, 221)):
            self.fixture.now += 2
            with patch.dict('os.environ', SL_SPELL_EXP='1'):
                self.ctx._world_magic_cast(1, key, 1, self.fixture.now)
            effects = []
            for wire in self.view.drain(1):
                if int.from_bytes(wire[2:4], 'little') == 0x4ed8:
                    with pb.parse_message(wire[4:-2]) as message:
                        effects.append((message.occurrences(1)[0].value,
                                        message.occurrences(2)[0].value))
            self.assertIn((1, gfx), effects)

    async def test_restart_detaches_save_without_resetting_live_deadline(self):
        self.ctx._world_magic_writers[id(self.writer)] = 1
        self.magic.committed(1, self.magic.spells[2], self.fixture.now)
        deadline = self.magic.state(1).buffs[2]
        self.ctx._world_pcs.clear()
        await self.ctx._world_magic_after_request(self.writer, {}, None, 0x4e33, None)
        self.assertTrue(self.saved)
        self.assertEqual(self.magic.state(1).buffs[2], deadline)
        self.assertNotIn(id(self.writer), self.ctx._world_magic_writers)

    def test_cure_poison_clears_pc_and_monster_before_next_damage_tick(self):
        target = self.enemy()
        for uid in (1, target.uid):
            self.fixture.now += 2
            self.ctx._world_magic_apply_poison(uid, 1, self.fixture.now)
            self.assertTrue(self.magic.is_poisoned(uid, self.fixture.now))
            before = self.state.hp if uid == 1 else self.view.spawner.slot_for(uid)[1].hp
            self.ctx._world_magic_cast(1, 8, uid, self.fixture.now)
            self.assertFalse(self.magic.is_poisoned(uid, self.fixture.now))
            self.ctx._world_magic_poison_tick(self.fixture.now + 4)
            after = self.state.hp if uid == 1 else self.view.spawner.slot_for(uid)[1].hp
            self.assertEqual(before, after)

    def test_poison_nonlethal_expiry_and_lethal_monster_cleanup(self):
        target = self.enemy()
        before = self.view.spawner.slot_for(target.uid)[1].hp
        self.ctx._world_magic_apply_poison(target.uid, 1, self.fixture.now, duration=4,
                                         tick_seconds=3, damage=1)
        self.ctx._world_magic_poison_tick(self.fixture.now + 3)
        self.assertEqual(self.view.spawner.slot_for(target.uid)[1].hp, before - 1)
        self.ctx._world_magic_poison_tick(self.fixture.now + 4)
        self.assertNotIn(target.uid, self.magic.npc_poison)
        self.assertEqual(self.view.spawner.slot_for(target.uid)[1].hp, before - 1)
        self.ctx._world_magic_apply_poison(target.uid, 1, self.fixture.now + 5,
                                         tick_seconds=3, damage=before)
        self.ctx._world_magic_poison_tick(self.fixture.now + 8)
        self.assertNotIn(target.uid, self.magic.npc_poison)
        self.assertTrue(any(kill.npc_uid == target.uid and kill.pc_uid == 1
                            for kill in self.view.combat.kills))
        kills = len(self.view.combat.kills)
        self.ctx._world_magic_poison_tick(self.fixture.now + 20)
        self.assertEqual(len(self.view.combat.kills), kills)

    def test_poison_rejects_removed_entity_lifetime(self):
        target = self.enemy()
        self.ctx._world_magic_apply_poison(target.uid, 1, self.fixture.now)
        self.view.entities.remove(target.uid)
        self.ctx._world_magic_poison_tick(self.fixture.now + 3)
        self.assertNotIn(target.uid, self.magic.npc_poison)
        self.assertFalse(self.view.combat.kills)

    def test_pc_poison_lethal_status_precedes_death_and_does_not_repeat(self):
        self.state.hp = 1
        self.ctx._world_magic_apply_poison(1, 2, self.fixture.now, damage=5)
        self.view.drain(1)
        self.ctx._world_magic_poison_tick(self.fixture.now + 3)
        wires = self.view.drain(1)
        opcodes = [int.from_bytes(wire[2:4], 'little') for wire in wires]
        zero_status = []
        deaths = []
        for index, wire in enumerate(wires):
            if opcodes[index] == 0x4e38:
                with pb.parse_message(wire[4:-2]) as msg:
                    if msg.occurrences(10)[0].value == 0:
                        zero_status.append(index)
            elif opcodes[index] == 0x4e39:
                deaths.append(index)
        self.assertTrue(self.state.dead)
        self.assertEqual(self.state.hp, 0)
        self.assertTrue(zero_status)
        self.assertTrue(deaths)
        self.assertLess(zero_status[0], deaths[0])
        self.ctx._world_magic_poison_tick(self.fixture.now + 9)
        self.assertFalse(self.view.drain(1))

    async def test_restart_offline_poison_does_not_replay_overdue_damage(self):
        self.ctx._world_magic_apply_poison(1, 2, self.fixture.now, duration=60)
        profile, status = self.state.profile, dict(self.state.status_fields)
        self.ctx._world_magic_writers[id(self.writer)] = 1
        self.ctx._world_magic_detach(self.writer)
        self.view.combat.forget_pc(1)
        self.fixture.now += 20
        self.ctx._world_magic_tick(self.fixture.now)
        self.state = self.view.combat.bind_pc(1, profile, status)
        self.ctx._world_send = AsyncMock()
        await self.ctx._world_magic_enter(self.writer, {}, None, None)
        self.assertEqual(self.state.hp, 100)
        self.assertEqual(self.magic.state(1).poison['next_tick'], self.fixture.now + 3)
        self.ctx._world_magic_poison_tick(self.fixture.now + 1)
        self.assertEqual(self.state.hp, 100)
        self.ctx._world_magic_poison_tick(self.fixture.now + 3)
        self.assertEqual(self.state.hp, 95)

    def test_chill_touch_heals_only_actual_damage_removed_and_clamps_max_hp(self):
        target = self.enemy()
        self.view.entities.move(target.uid, 0, 101, 100)
        self.state.hp = 1
        before = self.view.spawner.slot_for(target.uid)[1].hp
        self.ctx._world_magic_cast(1, 9, target.uid, self.fixture.now)
        after = self.view.spawner.slot_for(target.uid)[1].hp
        self.assertEqual(self.state.hp - 1, before - after)
        self.assertEqual(self.state.mp, 91)
        self.fixture.now += 2
        target = self.enemy()
        self.view.entities.move(target.uid, 0, 101, 100)
        self.state.hp = self.state.max_hp - 1
        self.ctx._world_magic_cast(1, 9, target.uid, self.fixture.now)
        self.assertEqual(self.state.hp, self.state.max_hp)

    def test_detection_removes_invisibility_and_noop_only_debits_mp(self):
        self.ctx._world_magic_set_invisible(1, self.fixture.now)
        self.assertTrue(self.magic.is_invisible(1, self.fixture.now))
        self.ctx._world_magic_cast(1, 12, 1, self.fixture.now)
        self.assertFalse(self.magic.is_invisible(1, self.fixture.now))
        self.assertEqual(self.state.mp, 92)
        before = self.state.hp
        self.fixture.now += 2
        self.ctx._world_magic_cast(1, 12, 1, self.fixture.now)
        self.assertEqual(self.state.mp, 84)
        self.assertEqual(self.state.hp, before)
        self.assertFalse(self.magic.state(1).buffs)

    def test_weapon_buffs_exact_damage_hit_selected_uid_and_real_swing_consumer(self):
        import random
        from tools.local_original_session import world_combat
        self.ctx._world_magic_weapon_uid = lambda uid: 123
        self.view.combat.magic_profile = self.ctx._world_magic_combat_profile
        base = self.state.profile
        monster = replace(self.fixture.data.monsters[245], ac=-50)
        self.ctx._world_magic_cast(1, 7, 1, self.fixture.now)
        holy = self.ctx._world_magic_combat_profile(1, base, self.fixture.now)
        self.assertEqual(holy.weapon.hit, base.weapon.hit + 1)
        self.assertEqual(holy.weapon.damage, base.weapon.damage + 1)
        self.fixture.now += 2
        self.ctx._world_magic_cast(1, 11, 1, self.fixture.now)
        both = self.ctx._world_magic_combat_profile(1, base, self.fixture.now)
        self.assertEqual(both.weapon.hit, base.weapon.hit + 1)
        self.assertEqual(both.weapon.damage, base.weapon.damage + 3)
        ranged = self.ctx._world_magic_combat_profile(1, base, self.fixture.now, ranged=True)
        self.assertEqual(ranged.weapon.hit, base.weapon.hit)
        self.assertEqual(ranged.weapon.damage, base.weapon.damage + 2)
        # Paired actual combat RNG shows damage and hit effects independently.
        for seed in range(100):
            rng1, rng2 = random.Random(seed), random.Random(seed)
            unbuffed = world_combat.pc_hits_npc(base, monster, rng1)
            buffed = world_combat.pc_hits_npc(both, monster, rng2)
            if unbuffed.landed and buffed.landed:
                self.assertEqual(buffed.damage, unbuffed.damage + 3)
        ordinary = replace(monster, ac=0)
        base_hits = sum(world_combat.pc_hits_npc(base, ordinary, random.Random(seed)).landed
                        for seed in range(1000))
        holy_hits = sum(world_combat.pc_hits_npc(holy, ordinary, random.Random(seed)).landed
                        for seed in range(1000))
        self.assertGreater(holy_hits, base_hits)
        self.view.combat.rng = random.Random(7)
        expected = world_combat.pc_hits_npc(both, ordinary, random.Random(7))
        actual = self.view.combat.try_pc_swing(1, ordinary, self.fixture.now)
        self.assertEqual(actual, expected)
        self.ctx._world_magic_weapon_uid = lambda uid: 124
        self.assertEqual(self.ctx._world_magic_combat_profile(1, base, self.fixture.now), base)
        self.ctx._world_magic_weapon_uid = lambda uid: 123
        self.assertEqual(self.ctx._world_magic_combat_profile(1, base, self.fixture.now + 11), base)

    def prepare_new_tiers(self):
        self.state.profile = replace(self.state.profile, level=30)
        self.state.status_fields[12] = self.state.status_fields[13] = 1000
        self.magic.state(1).learned = {key for key, spell in self.magic.spells.items()
                                     if spell.kind != 'unsupported'}

    def test_counter_absorbs_one_real_damage_cast_without_reflecting_then_next_hits(self):
        self.prepare_new_tiers()
        target = self.enemy()
        self.magic.apply_status(target.uid, 'counter_magic', self.fixture.now, 10,
            source_uid=target.uid, spell=30, target_ref=target.ref)
        before_hp = self.view.spawner.slot_for(target.uid)[1].hp
        caster_hp, before_mp = self.state.hp, self.state.mp
        self.ctx._world_magic_cast(1, 3, target.uid, self.fixture.now)
        self.assertEqual(self.view.spawner.slot_for(target.uid)[1].hp, before_hp)
        self.assertEqual(self.state.hp, caster_hp)
        self.assertEqual(self.state.mp, before_mp - self.magic.spells[3].mp)
        self.assertIsNone(self.magic.status(target.uid, 'counter_magic', self.fixture.now))
        self.fixture.now += 2
        self.ctx._world_magic_cast(1, 3, target.uid, self.fixture.now)
        self.assertLess(self.view.spawner.slot_for(target.uid)[1].hp, before_hp)

    def test_mana_drain_consumes_hp_and_actual_npc_mp_only_once_per_reservoir(self):
        self.prepare_new_tiers()
        self.state.status_fields[12] = 10
        target = self.enemy()
        self.view.entities.move(target.uid, 0, 101, 100)
        before_mp, before_hp = self.state.mp, self.state.hp
        npc = self.view.spawner.slot_for(target.uid)[0].monster
        self.ctx._world_magic_cast(1, 38, target.uid, self.fixture.now)
        drained = self.ctx._world_magic_events[-1]['amount']
        self.assertGreater(drained, 0)
        self.assertLessEqual(drained, npc.mp)
        self.assertEqual(self.state.hp, before_hp - 50)
        self.assertEqual(self.state.mp, min(self.state.max_mp, before_mp + drained))
        remaining = self.magic.npc_mana(target.uid, target.ref, npc.mp)
        self.assertEqual(remaining, npc.mp - drained)
        # Resource refusal precedes another NPC debit.
        self.fixture.now += 2
        with self.assertRaisesRegex(ValueError, 'HP'):
            self.ctx._world_magic_cast(1, 38, target.uid, self.fixture.now)
        self.assertEqual(self.magic.npc_mana(target.uid, target.ref, npc.mp), remaining)

    def test_remove_curse_clears_actual_curses_and_poison_but_preserves_slow(self):
        self.prepare_new_tiers()
        target = self.enemy()
        for kind in ('blind', 'paralyze', 'darkness', 'slow'):
            self.magic.apply_status(target.uid, kind, self.fixture.now, 10,
                source_uid=1, target_ref=target.ref)
        self.ctx._world_magic_apply_poison(target.uid, 1, self.fixture.now)
        before_mp = self.state.mp
        self.ctx._world_magic_cast(1, 36, target.uid, self.fixture.now)
        for kind in ('blind', 'paralyze', 'darkness'):
            self.assertIsNone(self.magic.status(target.uid, kind, self.fixture.now))
        self.assertIsNotNone(self.magic.status(target.uid, 'slow', self.fixture.now))
        self.assertFalse(self.magic.is_poisoned(target.uid, self.fixture.now))
        self.assertEqual(self.state.mp, before_mp - self.magic.spells[36].mp)

    def test_meditation_reconnect_uses_fresh_tick_not_old_clock_or_offline_replay(self):
        self.prepare_new_tiers()
        self.state.status_fields[12] = 10
        self.magic.apply_status(1, 'meditation', 100, 10, source_uid=1, spell=31,
            params={'tick_seconds': 2, 'mp_restore': 5, 'next_tick': 102})
        row = self.magic.snapshot(1, 101, wall=1000)
        self.assertNotIn('next_tick', row['statuses']['effects']['meditation']['params'])
        self.magic.restore(1, row, 500, wall=1002)
        self.fixture.now = 500
        f._world_magic_status_tick(self.ctx, 500)
        self.assertEqual(self.state.mp, 10)
        f._world_magic_status_tick(self.ctx, 501.99)
        self.assertEqual(self.state.mp, 10)
        f._world_magic_status_tick(self.ctx, 502)
        self.assertEqual(self.state.mp, 15)
        self.fixture.now = 508
        self.magic.expire(508)
        f._world_magic_status_tick(self.ctx, 508)
        self.assertEqual(self.state.mp, 15)

    def test_weapon_break_is_consumed_by_real_selected_pc_swing_and_repair(self):
        import random
        from tools.local_original_session import world_combat
        self.prepare_new_tiers()
        selected = [456]
        self.ctx._world_magic_weapon_uid = lambda uid: selected[0]
        monster = self.fixture.data.monsters[245]
        seed, expected = next((seed, swing) for seed in range(100)
            if (swing := world_combat.pc_hits_npc(self.state.profile, monster,
                random.Random(seed))).landed and swing.damage > 0)
        self.magic.apply_status(1, 'weapon_break', self.fixture.now, None,
            source_uid=2, spell=26, params={'weapon_uid': 456, 'damage_multiplier': .5})
        f._world_magic_consumers(self.ctx)
        self.view.combat.rng = random.Random(seed)
        actual = self.view.combat.try_pc_swing(1, monster, self.fixture.now)
        self.assertEqual(actual.damage, int(expected.damage * .5))
        self.fixture.now += 10
        self.magic.clear_weapon_damage(1, 456)
        self.view.combat.rng = random.Random(seed)
        repaired = self.view.combat.try_pc_swing(1, monster, self.fixture.now)
        self.assertEqual(repaired.damage, expected.damage)

    def test_status_adapter_stop_restores_existing_optional_world_callback(self):
        original = lambda uid, now: {'fixture': True}
        self.view.magic_status = original
        f._world_magic_consumers(self.ctx)
        self.assertIsNot(self.view.magic_status, original)
        f._world_magic_stopped(self.ctx)
        self.assertIs(self.view.magic_status, original)

    def test_actual_kit_stats_consumes_fifty_catalysts_as_one_hundred_burden(self):
        from tools.local_original_session import world_stats, world_weight
        frame = inventory.build_kit_frame([fields(456, 166, 50)])
        self.ctx._item_equipment_effect = SimpleNamespace(store=SimpleNamespace(
            peek=lambda uid: (None, frame)))
        base = world_stats.calculate_stats(world_stats.CharacterStats(30, 3,
            world_stats.Attributes(8, 7, 16, 18, 8, 18)))
        with patch('tools.local_original_session.world_feature_stats._world_stats_for',
                   return_value=(base, (), {})):
            actual, _, _ = f._world_stats_for(self.ctx, SimpleNamespace(uid=1))
        self.assertEqual(actual.weight, world_weight.weight_state(100, actual.max_weight))
        self.assertGreater(actual.weight.gauge, 0)

    def test_new_direct_damage_and_vampiric_drain_use_actual_hp_and_one_mp_debit(self):
        self.prepare_new_tiers()
        for key in (27, 33, 37):
            with self.subTest(key=key):
                target = self.enemy()
                self.view.entities.move(target.uid, 0, 101, 100)
                self.state.hp = 1
                before = self.view.spawner.slot_for(target.uid)[1].hp
                mp = self.state.mp
                self.fixture.now += 2
                self.ctx._world_magic_cast(1, key, target.uid, self.fixture.now)
                found = self.view.spawner.slot_for(target.uid)
                after = 0 if found is None else found[1].hp
                self.assertLess(after, before)
                self.assertEqual(self.state.mp, mp - self.magic.spells[key].mp)
                if key == 27:
                    self.assertEqual(self.state.hp, min(self.state.max_hp, 1 + before - after))

    def test_new_heal_positive_clamp_and_current_status_hp_mp(self):
        self.prepare_new_tiers()
        for key in (18, 34):
            for hp in (1, self.state.max_hp - 1, self.state.max_hp):
                with self.subTest(key=key, hp=hp):
                    self.fixture.now += 2
                    self.state.hp = hp
                    mp = self.state.mp
                    self.view.drain(1)
                    self.ctx._world_magic_cast(1, key, 1, self.fixture.now)
                    self.assertEqual(self.state.mp, mp - self.magic.spells[key].mp)
                    if hp < self.state.max_hp:
                        self.assertGreater(self.state.hp, hp)
                    self.assertLessEqual(self.state.hp, self.state.max_hp)
                    statuses = self.fixture.decoded(self.view.drain(1), 0x4e38, 1, 1)
                    from tools.local_original_session.hunt_bot import scalar
                    self.assertEqual((scalar(statuses[-1], 10), scalar(statuses[-1], 12)),
                                     (self.state.hp, self.state.mp))

    def test_area_spells_damage_each_current_hostile_once_and_exclude_outside_map_radius(self):
        self.prepare_new_tiers()
        for key in (16, 21, 24, 29):
            with self.subTest(key=key):
                enemies = [self.enemy() for _ in range(4)]
                points = ((103, 100), (104, 100), (110, 100), (104, 100))
                for index, (enemy, point) in enumerate(zip(enemies, points)):
                    self.view.entities.move(enemy.uid, 1 if index == 3 else 0, *point)
                self.view._refresh(1)
                before = [self.view.spawner.slot_for(enemy.uid)[1].hp for enemy in enemies]
                mp, hp = self.state.mp, self.state.hp
                companion_hp = self.fixture.actor.record.hp
                self.fixture.now += 2
                self.ctx._world_magic_cast(1, key, enemies[0].uid, self.fixture.now)
                after = [0 if (slot := self.view.spawner.slot_for(enemy.uid)) is None
                         else slot[1].hp for enemy in enemies]
                self.assertTrue(all(after[index] < before[index] for index in (0, 1)))
                self.assertEqual(after[2:], before[2:])
                self.assertEqual(self.state.hp, hp)
                self.assertEqual(self.fixture.actor.record.hp, companion_hp)
                self.assertEqual(self.state.mp, mp - self.magic.spells[key].mp)
                event = self.ctx._world_magic_events[-1]
                self.assertGreaterEqual(event['amount'], sum(before[i] - after[i] for i in (0, 1)))
                # Remove this development group before testing the next area spell.
                for enemy in enemies:
                    self.view.entities.remove(enemy.uid)

    def test_new_armor_needs_equipped_body_armor_then_binds_exact_uid(self):
        self.prepare_new_tiers()
        with self.assertRaisesRegex(ValueError, 'EQUIPPED_ARMOR'):
            self.ctx._world_magic_cast(1, 20, 1, self.fixture.now)
        self.assertEqual(self.state.mp, 1000)
        frame = inventory.build_kit_frame([fields(450, 103)])
        selected = [450]
        self.ctx._item_equipment_effect = SimpleNamespace(store=SimpleNamespace(peek=lambda uid:
            (SimpleNamespace(slots=((2, selected[0]),)), frame)))
        self.ctx._world_recalculate_uid = lambda uid: setattr(self.state, 'profile', replace(
            self.state.profile, ac=10 + self.magic.ac_bonus(uid, self.fixture.now,
                armor_uid=f._world_magic_armor_uid(self.ctx, uid))))
        self.ctx._world_magic_cast(1, 20, 1, self.fixture.now)
        self.assertEqual(self.magic.state(1).armor_uids, {20: 450})
        self.assertEqual(self.state.profile.ac, 7)
        selected[0] = 451
        self.ctx._world_recalculate_uid(1)
        self.assertEqual(self.state.profile.ac, 10)
        self.assertEqual(self.state.mp, 980)

    def test_new_dexterity_reaches_stats_and_status_without_changing_base_or_stacking(self):
        from tools.local_original_session import world_stats as stats
        self.prepare_new_tiers()
        base = stats.CharacterStats(30, 3, stats.Attributes(8, 7, 16, 18, 8, 18))
        calculated = stats.calculate_stats(base)
        info = {3: 3, 11: 8, 12: 7, 13: 16, 14: 18, 15: 8, 16: 18}
        original = self.ctx._world_stats_for
        self.ctx._world_stats_for = MethodType(f._world_stats_for, self.ctx)
        with patch('tools.local_original_session.world_feature_stats._world_stats_for',
                   return_value=(calculated, (), info)):
            for now in (100, 102):
                self.fixture.now = now
                self.ctx._world_magic_cast(1, 25, 1, now)
                buffed = self.ctx._world_stats_for(SimpleNamespace(uid=1))[0]
                self.assertEqual(buffed.attributes.dexterity, 12)
                self.assertEqual(stats.self_info_fields({}, buffed)[5], 12)
                self.assertEqual(base.attributes.dexterity, 7)
            self.fixture.now = 113
            expired = self.ctx._world_stats_for(SimpleNamespace(uid=1))[0]
            self.assertEqual(expired.attributes.dexterity, 7)
        self.ctx._world_stats_for = original


if __name__ == '__main__':
    unittest.main()
