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

    def test_expanded_catalog_retains_five_tiers_and_explicit_supported_subset(self):
        # Evidence catalog stays intact; only the closed job subset is overlaid.
        self.assertTrue((set(range(40)) - {23}) <= set(self.magic.spells))
        self.assertEqual({s.key for s in self.magic.spells.values() if s.kind != 'unsupported'},
                         (set(range(40)) - {23, 35}) | set(m.JOB_POLICIES))
        self.assertEqual(self.magic.spells[2].duration, 1200)
        self.assertEqual(self.magic.spells[5].mp, 3)

    def test_display_content_covers_every_learnable_spell_with_fixed_client_inventory(self):
        supported = {s.key for s in self.magic.spells.values() if s.kind != 'unsupported'}
        self.assertEqual(set(f.SPELL_DISPLAY), supported | {89, 90})
        for key, row in f.SPELL_DISPLAY.items():
            with self.subTest(key=key):
                self.assertEqual(row['skill_id'], key + 1)
                self.assertGreater(row['source_line'], 0)
                self.assertIn(row['action_id'], (18, 19))
                primary, secondary = row['graphics']
                self.assertEqual(primary['status'], 'PRESENT')
                self.assertEqual(primary['gfx'], row['castgfx'])
                self.assertGreater(primary['spr_line'], 0)
                self.assertTrue(primary['catalog_files'])
                self.assertFalse(primary['missing_catalog_files'])
                self.assertTrue(all(p['size'] > 0 for p in primary['catalog_files']))
                self.assertEqual(secondary['status'], 'ZERO_NO_GRAPHIC')
                self.assertEqual(row['castgfx2'], 0)

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
            if spell.kind == 'unsupported' or 3 not in spell.classes:
                continue
            level = max(30, spell.classes[3])
            self.magic.state(1).learned = self.magic.learn(1, spell, 3, level)
            self.assertIs(self.magic.admit_cast(1, key, 3, level, spell.mp, True, now), spell)
            self.magic.committed(1, spell, now)
            now += spell.reuse
        self.assertEqual(self.magic.state(1).learned,
                         {key for key, spell in self.magic.spells.items()
                          if spell.kind != 'unsupported' and 3 in spell.classes})

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
                character_class, minimum = next(iter(spell.classes.items()))
                with self.assertRaisesRegex(ValueError, 'EFFECT_UNSUPPORTED'):
                    self.magic.admit_cast(1, key, character_class, max(99, minimum), 999, True, 100)
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
        from tools.local_original_session import world_registry
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
        magic_rows = {}
        def save_magic(row):
            self.saved.append(row)
            magic_rows[row['uid']] = row
        self.writer = object()
        self.ctx = SimpleNamespace(world=self.view, _world=self.view, _world_magic=self.magic,
            _world_magic_events=[], _world_magic_errors=[], _world_magic_store=SimpleNamespace(
                rows=magic_rows, save=save_magic), _world_magic_writers={},
            _world_magic_buff_ui=False, _world_magic_icons={}, _world_magic_next_icon=0x31000000,
            _world_pcs={id(self.writer): (self.writer, 1)},
            _world_registry=world_registry.build_registry((f,)),
            realm=SimpleNamespace(service=lambda w: SimpleNamespace(
                snapshot=lambda: SimpleNamespace(uid=1, name='MagicMage'))))
        for fn in f.METHODS:
            setattr(self.ctx, fn.__name__, MethodType(fn, self.ctx))
        from tools.local_original_session import world_npc_resources
        self.ctx._world_magic_npc_resources = world_npc_resources.install(self.view)
        self.ctx.collect_sync_hooks = lambda name, *args, **kwargs: world_registry.collect_sync_hooks(
            name, self.ctx, *args, **kwargs)
        self.ctx.run_sync_hooks = lambda name, *args, **kwargs: world_registry.run_sync_hooks(
            name, self.ctx, *args, **kwargs)
        self.ctx.fold_sync_hooks = lambda name, value, *args, **kwargs: world_registry.fold_sync_hooks(
            name, self.ctx, value, *args, **kwargs)
        self.ctx._world_stats_for = lambda *args, **kw: (SimpleNamespace(
            attributes=SimpleNamespace(intelligence=18),
            weight=SimpleNamespace(normal_skill_blocked=False)), (), {})
        self.ctx._world_recalculate_uid = lambda uid: setattr(self.state, 'profile',
            replace(self.state.profile, ac=10 + self.magic.ac_bonus(uid, self.fixture.now)))
        self.ctx._world_bound = lambda writer: id(writer) in self.ctx._world_pcs
        self.view.drain(1)

    def test_icon_catalog_key_refresh_remove_lifecycle_and_explicit_disable(self):
        from tools.local_original_session.world_item_effects import buff_icon_frame
        self.magic.state(1).buffs[2] = 125.25
        self.ctx._world_magic_sync_icons(1, 100)
        self.assertEqual(tuple(self.view.drain(1)), ())
        self.assertEqual(self.ctx._world_magic_icons, {})

        self.ctx._world_magic_buff_ui = True
        self.ctx._world_magic_sync_icons(1, 100)
        key = self.ctx._world_magic_icons[(1, 2)]
        self.assertEqual(key, 485)  # dump2220 / spellicon_00.plist:2581.
        self.assertEqual(tuple(self.view.drain(1)), (buff_icon_frame(2, key, 25.25),))
        self.magic.state(1).buffs[2] = 150.5
        self.ctx._world_magic_sync_icons(1, 110)
        self.assertEqual(self.ctx._world_magic_icons[(1, 2)], key)
        self.assertEqual(tuple(self.view.drain(1)), (buff_icon_frame(2, key, 40.5),))
        self.magic.state(1).buffs.clear()
        self.ctx._world_magic_sync_icons(1, 111)
        self.assertEqual(tuple(self.view.drain(1)), (buff_icon_frame(2, key, 0, remove=True),))
        self.assertEqual(self.ctx._world_magic_icons, {})

    def test_icon_initialization_defaults_on_and_keeps_explicit_disable(self):
        for setting, enabled in (({}, True), ({'SL_PLAYER_MAGIC_BUFF_UI': '0'}, False)):
            ctx = SimpleNamespace(world=self.view)
            with patch.dict('os.environ', setting, clear=True), patch.object(f, '_world_magic_consumers'):
                f._world_magic_initialize(ctx)
            self.assertEqual(ctx._world_magic_buff_ui, enabled)

    def test_icon_keys_have_no_active_spell_or_consumable_collision(self):
        from tools.local_original_session.world_item_effects import CONSUMABLE_BUFF_ICONS
        self.assertEqual(len(f.SPELL_BUFF_ICONS), len(set(f.SPELL_BUFF_ICONS.values())))
        self.assertFalse(set(f.SPELL_BUFF_ICONS.values()) &
                         {row[1] for row in CONSUMABLE_BUFF_ICONS.values()})
        self.assertTrue(all(self.magic.spells[key].kind != 'unsupported' or key in m.OPTIONAL_BUFF_KEYS
                            for key in f.SPELL_BUFF_ICONS))

    async def test_icon_tick_death_restart_and_restore_use_real_deadlines(self):
        from tools.local_original_session.world_item_effects import buff_icon_frame
        self.ctx._world_magic_buff_ui = True
        now = self.fixture.now
        self.magic.committed(1, self.magic.spells[2], now)
        self.ctx._world_magic_sync_icons(1, now)
        self.assertIn(buff_icon_frame(2, 485, 10), self.view.drain(1))
        self.ctx._world_magic_writers[id(self.writer)] = 1
        self.ctx._world_magic_detach(self.writer)
        self.assertFalse(self.ctx._world_magic_icons)
        self.fixture.now = now + 3
        self.ctx._world_send = AsyncMock()
        await self.ctx._world_magic_enter(self.writer, {}, None, None)
        frames = self.ctx._world_send.await_args.args[2]
        self.assertIn(buff_icon_frame(2, 485, 7), frames)
        self.fixture.now = now + 10
        self.ctx._world_magic_tick(self.fixture.now)
        self.assertIn(buff_icon_frame(2, 485, 0, remove=True), self.view.drain(1))
        self.assertFalse(self.ctx._world_magic_icons)

        # Existing saved remaining/offline-elapsed policy owns the deadline.
        self.magic.committed(1, self.magic.spells[2], self.fixture.now)
        saved = self.magic.snapshot(1, self.fixture.now + 1, wall=1000)
        self.magic.restore(1, saved, self.fixture.now, wall=1002)
        self.ctx._world_magic_sync_icons(1, self.fixture.now)
        self.assertIn(buff_icon_frame(2, 485, 7), self.view.drain(1))
        self.ctx._world_magic_died(1)
        self.assertIn(buff_icon_frame(2, 485, 0, remove=True), self.view.drain(1))
        self.assertFalse(self.ctx._world_magic_icons)

    def test_status_icon_removal_preserves_other_buff_and_unmapped_is_omitted(self):
        from tools.local_original_session.world_item_effects import buff_icon_frame
        now = self.fixture.now
        self.ctx._world_magic_buff_ui = True
        self.magic.state(1).buffs.update({2: now + 10, 1: now + 30})
        self.magic.apply_status(1, 'blind', now, 5, source_uid=1, spell=19)
        self.ctx._world_magic_sync_icons(1, now)
        frames = self.view.drain(1)
        self.assertIn(buff_icon_frame(19, 5318, 5), frames)
        self.assertEqual(set(self.ctx._world_magic_icons), {(1, 2), (1, 19)})
        self.magic.state(1).effects.pop('blind')
        self.ctx._world_magic_sync_icons(1, now + 1)
        frames = self.view.drain(1)
        self.assertIn(buff_icon_frame(19, 5318, 0, remove=True), frames)
        self.assertIn(buff_icon_frame(2, 485, 9), frames)
        self.assertEqual(self.ctx._world_magic_icons, {(1, 2): 485})

    def use_core_stats(self, calculated, info=None):
        from tools.local_original_session.world_core_stats import _world_stats_for
        attributes = calculated.attributes
        values = {3: self.state.profile.character_class, 10: calculated.level,
            11: attributes.strength, 12: attributes.dexterity, 13: attributes.con,
            14: attributes.wis, 15: attributes.charisma, 16: attributes.intelligence}
        values.update(info or {})
        self.ctx.realm.store = SimpleNamespace(select=lambda name: (1, values))
        self.ctx._world_progress_for = lambda uid: None
        self.ctx._world_stats_for = MethodType(_world_stats_for, self.ctx)

    def enemy(self):
        target, _ = self.fixture.monster()
        self.view.entities.move(target.uid, 0, 103, 100)
        self.view._refresh(1)
        return target

    def test_job_overlay_preserves_source_and_class_level_costs(self):
        source = m.load_catalog()
        before = json.dumps(source, sort_keys=True)
        magic = m.PlayerMagic(source)
        self.assertEqual(json.dumps(source, sort_keys=True), before)
        for key in m.JOB_POLICIES:
            spell = magic.spells[key]
            cls, minimum = next(iter(spell.classes.items()))
            magic.select_element(1, spell.raw['player_policy'].get('required_element', 'water'))
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'LEVEL_TOO_LOW'):
                    magic.learn(1, spell, cls, minimum - 1)
                with self.assertRaisesRegex(ValueError, 'CLASS_NOT_ALLOWED'):
                    magic.learn(1, spell, 3, 99)
                magic.state(1).learned = magic.learn(1, spell, cls, minimum)
                magic.admit_cast(1, key, cls, minimum, spell.mp, True, 100)
        self.assertEqual(magic.spells[129].raw['hp_cost']['value'], 8)
        self.assertEqual(magic.spells[145].raw['hp_cost']['value'], 50)
        self.assertEqual(magic.spells[136].raw['materials']['value'],
                         [dict(classic_item_key=569, count=1)])

    def test_job_second_profile_bonuses_reach_actual_melee_and_ranged_rolls(self):
        self.ctx._world_magic_started()
        base = self.state.profile
        for key, melee, ranged in ((88, (5, 0), (0, 0)),
                (147, (0, 3), (0, 0)), (162, (3, 5), (0, 0)),
                (148, (0, 0), (5, 0)), (165, (0, 0), (2, 4))):
            self.magic.state(1).buffs.clear()
            self.magic.committed(1, self.magic.spells[key], self.fixture.now)
            for is_ranged, expected in ((False, melee), (True, ranged)):
                profile = self.view.combat.modify_profile(1, base, self.fixture.now, ranged=is_ranged)
                self.assertEqual((profile.weapon.hit - base.weapon.hit,
                                  profile.weapon.damage - base.weapon.damage), expected)
        self.fixture.now += 10
        self.assertEqual(self.view.combat.modify_profile(1, base, self.fixture.now), base)

    def test_job_second_stun_blocks_real_attack_admission_and_entangle_is_move_only(self):
        self.ctx._world_magic_started()
        self.state.profile = replace(self.state.profile, character_class=1, level=60)
        self.magic.state(1).learned.add(86)
        target = self.enemy()
        self.view.entities.move(target.uid, 0, 101, 100)
        self.ctx._world_magic_cast(1, 86, target.uid, self.fixture.now)
        self.assertTrue(self.view.magic_status(target.uid, self.fixture.now)['blocked'])
        self.magic.apply_status(1, 'stun', self.fixture.now, 4, source_uid=2, spell=86)
        monster = self.view.spawner.slot_for(target.uid)[0].monster
        self.assertFalse(self.view.combat.pc_swing_ready(1, self.fixture.now))
        self.assertIsNone(self.view.combat.try_pc_swing(1, monster, self.fixture.now))
        with self.assertRaisesRegex(ValueError, 'CASTER_PARALYZED'):
            self.ctx._world_magic_cast(1, 86, target.uid, self.fixture.now + 2)
        self.fixture.now += 5
        self.magic.apply_status(1, 'entangle', self.fixture.now, 30,
                               params={'move_multiplier': 2})
        self.assertEqual(self.view.combat.speed_factor(1, self.fixture.now), 1)
        self.assertTrue(self.view.combat.pc_swing_ready(1, self.fixture.now))
        self.assertEqual(self.view.magic_status(1, self.fixture.now)['move_factor'], 2)

    def test_job_second_erase_real_npc_damage_and_probability_consume_once(self):
        from tools.local_original_session import world_combat, world_magic_status
        self.prepare_new_tiers()
        target = self.enemy()
        definition = self.view.spawner.slot_for(target.uid)[0].monster
        reference = self.magic.catalog['local_policy']['npc_status_reference'][str(definition.template_id)]
        self.magic.apply_status(target.uid, 'erase_magic', self.fixture.now, 16,
            spell=152, target_ref=target.ref)
        with patch.object(world_combat, 'magic_damage', return_value=1) as damage:
            self.ctx._world_magic_cast(1, 3, target.uid, self.fixture.now)
        # Spell MR is the monster definition's MR (combat/monster stats audit);
        # Erase Magic halves it once.
        self.assertEqual(damage.call_args.kwargs['mr'], definition.mr // 2)
        self.assertTrue(self.ctx._world_magic_events[-1]['erase_consumed'])
        self.fixture.now += 2
        self.magic.apply_status(target.uid, 'erase_magic', self.fixture.now, 16,
            spell=152, target_ref=target.ref)
        slow = self.magic.spells[28]
        self.magic.spells[28] = replace(slow, raw={**slow.raw, 'materials': {'value': []}})
        with patch.object(world_magic_status, 'probability', return_value=False) as probability:
            self.ctx._world_magic_cast(1, 28, target.uid, self.fixture.now)
        self.assertEqual(probability.call_args.args[4], definition.mr // 2)
        self.assertIsNone(self.magic.status(target.uid, 'erase_magic', self.fixture.now))
        self.assertEqual(self.ctx._world_magic_events[-1]['outcome'], 'failed')

    def test_job_second_erase_incoming_npc_spell_uses_half_pc_mr_once(self):
        from tools.local_original_session import world_combat
        from tools.local_original_session.game_data import load_npc_spells
        self.ctx._world_magic_started()
        target = self.enemy()
        definition = self.view.spawner.slot_for(target.uid)[0].monster
        self.state.profile = replace(self.state.profile, mr=100)
        self.magic.apply_status(1, 'erase_magic', self.fixture.now, 16, spell=152)
        with patch.object(world_combat, 'npc_hits_pc', return_value=world_combat.Swing(True, 1)) as hit:
            self.view.combat.npc_magic_swing(definition, 1, object())
            self.assertEqual(hit.call_args.args[1].mr, 50)
            self.assertIsNone(self.magic.status(1, 'erase_magic', self.fixture.now))
            self.view.combat.npc_magic_swing(definition, 1, object())
            self.assertEqual(hit.call_args.args[1].mr, 100)
        target, npc = self.fixture.monster(7)
        self.view._refresh(1)
        self.ctx._world_magic_npc_spells = load_npc_spells()
        self.magic.apply_status(1, 'erase_magic', self.fixture.now, 16, spell=152)
        self.magic.apply_status(1, 'counter_magic', self.fixture.now, 16, spell=30)
        before_hp = self.state.hp
        with patch.object(self.view.combat.rng, 'randint', side_effect=lambda low, high: low):
            self.view.npc_attack(target, npc, 1, self.fixture.now)
        self.assertEqual(self.ctx._world_magic_events[-1]['outcome'], 'npc_countered')
        self.assertEqual(self.state.hp, before_hp)
        self.assertIsNone(self.magic.status(1, 'erase_magic', self.fixture.now))
        self.assertIsNone(self.magic.status(1, 'counter_magic', self.fixture.now))

    def test_job_second_water_life_heal_real_hp_clamp_and_once(self):
        from tools.local_original_session import world_combat
        self.prepare_new_tiers()
        self.state.profile = replace(self.state.profile, character_class=2, level=60)
        self.magic.select_element(1, 'water')
        spell = self.magic.spells[169]
        # Development-only catalyst-free DTO; real kit CAS is tested by jobs.
        self.magic.spells[169] = replace(spell, raw={**spell.raw, 'materials': {'value': []}})
        self.ctx._world_magic_cast(1, 169, 1, self.fixture.now)
        self.assertIn('water_life', self.saved[-1]['statuses']['effects'])
        self.fixture.now += 2
        self.state.hp = self.state.max_hp - 10
        with patch.object(world_combat, 'magic_heal', return_value=8):
            self.ctx._world_magic_cast(1, 0, 1, self.fixture.now)
        self.assertEqual(self.state.hp, self.state.max_hp)
        self.assertIsNone(self.magic.status(1, 'water_life', self.fixture.now))
        self.assertEqual(self.ctx._world_magic_events[-1]['healing_multiplier'], 1.5)
        self.assertNotIn('water_life', self.saved[-1].get('statuses', {}).get('effects', {}))
        self.fixture.now += 2
        self.state.hp = 1
        with patch.object(world_combat, 'magic_heal', return_value=8):
            self.ctx._world_magic_cast(1, 0, 1, self.fixture.now)
        self.assertEqual(self.state.hp, 9)

    def test_hp_to_mp_conversion_refuses_without_mutation_and_clamps(self):
        self.state.profile = replace(self.state.profile, level=30, character_class=2)
        self.magic.state(1).learned = {129, 145}
        for key, cost, restored in ((129, 8, 2), (145, 50, 15)):
            self.state.status_fields[12] = self.state.max_mp
            self.state.hp = cost + 1
            before = self.magic.snapshot(1, self.fixture.now, wall=1)
            with self.assertRaisesRegex(ValueError, 'MP_ALREADY_FULL'):
                self.ctx._world_magic_cast(1, key, 1, self.fixture.now)
            self.assertEqual(before, self.magic.snapshot(1, self.fixture.now, wall=1))
            self.state.status_fields[12] -= 1
            self.state.hp = cost
            with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_HP'):
                self.ctx._world_magic_cast(1, key, 1, self.fixture.now)
            self.assertEqual(self.state.hp, cost)
            self.state.hp = cost + 1
            self.ctx._world_magic_cast(1, key, 1, self.fixture.now)
            self.assertEqual(self.state.hp, 1)
            self.assertEqual(self.state.mp, self.state.max_mp)
            self.assertEqual(self.ctx._world_magic_events[-1]['amount'], 1)
            self.fixture.now += 2

    def test_reduction_applies_before_lethal_physical_and_magic_hp_write(self):
        from tools.local_original_session import world_combat
        self.state.profile = replace(self.state.profile, level=60, character_class=1)
        self.magic.committed(1, self.magic.spells[87], self.fixture.now)
        self.ctx._world_magic_started()
        monster = self.enemy()
        definition = self.view.spawner.slot_for(monster.uid)[0].monster
        with patch.object(world_combat, 'npc_hits_pc', return_value=world_combat.Swing(True, 5)):
            for call in (lambda: self.view.combat.npc_swing(definition, 1),
                         lambda: self.view.combat.npc_magic_swing(definition, 1, object())):
                self.state.hp, self.state.dead = 3, False
                swing, wire = call()
                self.assertEqual(swing.damage, 2)
                self.assertEqual(self.state.hp, 1)
                self.assertFalse(self.state.dead)
                self.assertIsNotNone(wire)
        self.assertEqual(self.magic.reduction(1, 60, self.fixture.now + 10), 0)

    def test_job_stats_project_mr_wis_resist_and_melee_hit_without_stacking(self):
        from tools.local_original_session import world_stats as stats
        base = stats.CharacterStats(30, 2, stats.Attributes(12, 12, 12, 12, 12, 12))
        calculated = stats.calculate_stats(base, ())
        self.state.profile = replace(self.state.profile, level=30, character_class=2)
        self.use_core_stats(calculated)
        for key in (128, 136, 137):
            self.magic.committed(1, self.magic.spells[key], self.fixture.now)
        projected = self.ctx._world_stats_for(SimpleNamespace(uid=1, name='MagicMage'))[0]
        self.assertEqual(projected.attributes.wis, 15)
        self.assertEqual(projected.mr - calculated.mr, 13)  # official MR10 + WIS MR3
        self.assertEqual(projected.resist_fire, 10)
        self.magic.committed(1, self.magic.spells[128], self.fixture.now + 1)
        self.assertEqual(self.magic.job_bonuses(1, self.fixture.now + 2)['mr'], 10)
        self.magic.committed(1, self.magic.spells[88], self.fixture.now)
        projected = self.ctx._world_stats_for(SimpleNamespace(uid=1, name='MagicMage'))[0]
        self.assertEqual(projected.melee_hit - calculated.melee_hit, 5)

    def test_item_sp_hook_reaches_single_area_and_drain_but_not_heal(self):
        from tools.local_original_session import world_combat
        self.prepare_new_tiers()
        self.ctx.fold_sync_hooks = lambda name, value, *args, **kwargs: 2 if name == 'spell_power' else value
        original = world_combat.magic_damage
        for key in (3, 27, 16):
            target = self.enemy()
            self.view.entities.move(target.uid, 0, 101, 100)
            self.view._refresh(1)
            self.fixture.now += 2
            with patch.object(world_combat, 'magic_damage', wraps=original) as observed:
                self.ctx._world_magic_cast(1, key, target.uid, self.fixture.now)
            self.assertTrue(observed.call_args_list)
            self.assertTrue(all(call.kwargs['item_sp'] == 2 for call in observed.call_args_list))
        self.fixture.now += 2
        with patch.object(world_combat, 'magic_heal', wraps=world_combat.magic_heal) as heal:
            self.ctx._world_magic_cast(1, 0, 1, self.fixture.now)
        self.assertEqual(heal.call_args.kwargs, {})

    def test_actual_wisdom_item_hook_damage_increase_expiry_and_optional_removal(self):
        import random
        from tools.local_original_session import world_combat, world_item_effects, world_registry
        effects = world_item_effects.WorldItemEffects(self.view.combat)
        self.ctx._world_item_effects = effects
        provider = world_item_effects._world_consumable_spell_power
        setattr(self.ctx, provider.__name__, MethodType(provider, self.ctx))
        module = SimpleNamespace(__name__='test_items_provider', METHODS=(provider,),
            HOOKS={'spell_power': (provider.__name__,)})
        self.ctx._world_registry = world_registry.build_registry((f, module))
        self.assertEqual(self.ctx.fold_sync_hooks('spell_power', 0, 1, 100), 0)
        effects.use(1, 297, 100)
        sp = self.ctx.fold_sync_hooks('spell_power', 0, 1, 100)
        self.assertEqual(sp, 2)
        parameters = self.magic.spells[3].raw['formula']['parameters']
        base = world_combat.magic_damage(parameters, 18, random.Random(9))
        boosted = world_combat.magic_damage(parameters, 18, random.Random(9), item_sp=sp)
        self.assertGreater(boosted, base)
        self.assertEqual(self.ctx.fold_sync_hooks('spell_power', 0, 1, 400), 0)
        self.ctx._world_registry = world_registry.build_registry((f,))
        self.assertEqual(self.ctx.fold_sync_hooks('spell_power', 0, 1, 101), 0)

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

    def test_default_self_support_effects_reach_the_selected_pc(self):
        self.assertNotIn(1, self.view.visibility.known.get(1, ()))
        for key, gfx in ((0, 744), (2, 221)):
            self.fixture.now += 2
            with patch.dict('os.environ'):
                import os
                os.environ.pop('SL_SPELL_EXP', None)
                self.ctx._world_magic_cast(1, key, 1, self.fixture.now)
            effects = []
            for wire in self.view.drain(1):
                if int.from_bytes(wire[2:4], 'little') == 0x4ed8:
                    with pb.parse_message(wire[4:-2]) as message:
                        effects.append((message.occurrences(1)[0].value,
                                        message.occurrences(2)[0].value))
            self.assertIn((1, gfx), effects)

    def test_shared_display_uses_sql_action_gfx_and_preserves_own_flag_without_projectile_fields(self):
        actor = self.view.entities.get(1)
        for key, expected in ((0, 744), (18, 829), (2, 221), (34, 830), (150, 2249),
                              (3, 167), (17, 754), (38, 2171)):
            with patch.dict('os.environ', SL_SPELL_EXP='1'):
                self.ctx._world_magic_display(actor, actor, key)
            actions, effects = [], []
            for wire in self.view.drain(1):
                with pb.parse_message(wire[4:-2]) as msg:
                    if int.from_bytes(wire[2:4], 'little') == 0x4e31:
                        actions.append((msg.occurrences(1)[0].value,
                                        msg.occurrences(13)[0].value))
                        self.assertEqual({field.number for field in msg.fields}, {1, 2, 3, 4, 5, 13})
                    elif int.from_bytes(wire[2:4], 'little') == 0x4ed8:
                        effects.append(msg.occurrences(2)[0].value)
            self.assertEqual(actions, [(f.SPELL_DISPLAY[key]['action_id'], 1)])
            self.assertEqual(effects, [expected])

    def test_shared_display_hook_has_same_delivery_for_remote_caster_without_mutating_resources(self):
        from tools.local_original_session.world_bridge import Context
        self.assertEqual(f.HOOKS['magic_cast_display'], ('_world_magic_display',))
        # Companion consumes this registered hook with its actual current Actor;
        # no player CS_USE_SPELL request or cost/learning authority is simulated.
        caster = self.view.entities.get(self.fixture.actor.ref.uid)
        target = self.view.entities.get(1)
        before = (self.state.hp, self.state.mp, self.fixture.actor.record.hp,
                  self.fixture.actor.record.mp, set(self.magic.state(1).learned))
        self.view.drain(1)
        context = Context(self.ctx)
        with patch.dict('os.environ', SL_SPELL_EXP='1'):
            context.run_sync_hooks('magic_cast_display', caster, target, 0)
        frames = self.view.drain(1)
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in frames], [0x4e31, 0x4ed8])
        with pb.parse_message(frames[0][4:-2]) as message:
            self.assertEqual(message.occurrences(2)[0].value, caster.uid)
            self.assertEqual(message.occurrences(3)[0].value, target.uid)
        self.assertEqual(before, (self.state.hp, self.state.mp, self.fixture.actor.record.hp,
                        self.fixture.actor.record.mp, set(self.magic.state(1).learned)))

    def test_display_explicit_opt_out_and_unknown_spell_queue_nothing(self):
        actor = self.view.entities.get(1)
        self.view.drain(1)
        with patch.dict('os.environ', SL_SPELL_EXP='0'):
            self.ctx._world_magic_display(actor, actor, 0)
        with patch.dict('os.environ', SL_SPELL_EXP='1'):
            self.ctx._world_magic_display(actor, actor, 0xffffffff)
        self.assertEqual(self.view.drain(1), [])

    def test_teleport_effect_ignores_display_flag(self):
        actor = self.view.entities.get(1)
        with patch.dict('os.environ', SL_SPELL_EXP='0'):
            self.ctx._world_magic_display(actor, actor, 4)
        frames = self.view.drain(1)
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in frames],
                         [0x4e31, 0x4ed8])
        with pb.parse_message(frames[1][4:-2]) as message:
            self.assertEqual((message.occurrences(1)[0].value,
                              message.occurrences(2)[0].value), (1, 169))

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
        self.view.combat.profile_modifiers.append(self.ctx._world_magic_combat_profile)
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
        resources = self.view.extensions['npc_resources']
        remaining = resources.mana_of(target.ref, npc.mp)
        self.assertEqual(remaining, npc.mp - drained)
        # Resource refusal precedes another NPC debit.
        self.fixture.now += 2
        with self.assertRaisesRegex(ValueError, 'HP'):
            self.ctx._world_magic_cast(1, 38, target.uid, self.fixture.now)
        self.assertEqual(resources.mana_of(target.ref, npc.mp), remaining)

    def test_mana_drain_spell_npc_cast_and_weapon_use_same_actual_balance(self):
        from tools.local_original_session import world_combat, world_feature_weapon_effects
        from tools.local_original_session.game_data import load_npc_spells
        self.prepare_new_tiers()
        self.state.status_fields[12] = 10
        target, npc = self.fixture.monster(7)
        self.view._refresh(1)
        self.ctx._world_magic_cast(1, 38, target.uid, self.fixture.now)
        spell_drain = self.ctx._world_magic_events[-1]['amount']
        resources = self.ctx._world_magic_npc_resources
        self.assertEqual(resources.mana_of(target.ref, npc.mp), npc.mp - spell_drain)
        self.ctx._world_magic_npc_spells = load_npc_spells()
        f._world_magic_consumers(self.ctx)
        with patch.object(self.view.combat.rng, 'randint', side_effect=lambda low, high: low):
            self.view.npc_attack(target, npc, 1, self.fixture.now)
        npc_event = self.ctx._world_magic_events[-1]
        self.assertEqual(npc_event['outcome'], 'npc_magic')
        cost = npc_event['mp_before'] - npc_event['mp_after']
        self.assertEqual(cost, 18)
        world_feature_weapon_effects._world_weapon_effects_initialize(self.ctx)
        self.ctx._world_magic_weapon_uid = lambda uid: 0
        # Weapon inputs now come from the core worn-equipment stats; supply the
        # equipped Staff of Mana (342) directly for this shared-balance check.
        staff = dict(template=342, enchant=0, intelligence=12, spellpower=0,
                     berserk=False, original_magic_hit=0)
        with patch.object(world_combat, 'pc_hits_npc', return_value=world_combat.Swing(True, 1)),                 patch.object(world_feature_weapon_effects, '_inputs', lambda ctx, uid: dict(staff)):
            self.view.pc_attack(1, target.uid)
        weapon_event = self.ctx._world_weapon_effects_events[-1]
        self.assertEqual(weapon_event['npc_mp_before'], npc.mp - spell_drain - cost)
        self.assertEqual(resources.mana_of(target.ref, npc.mp), weapon_event['npc_mp_after'])
        # Cost did not count as drain: the remaining cap belongs to both drain consumers.
        further = resources.drain_mana(target.ref, npc.mp, 100)
        self.assertEqual(spell_drain + weapon_event['drained'] + further, 40)
        self.view.entities.kill(target.uid)
        self.view.events.emit('npc_died', target.uid, self.fixture.now)
        self.assertNotIn(target.ref, resources._mana)

    async def test_slow_and_paralysis_corrections_use_existing_movement_diagnostics(self):
        from tools.local_original_session import movement
        from tools.local_original_session.world_handlers import MovementResult
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        position = movement.Position(1, 'MagicMage', 0, 100, 100)
        service = movement.MovementService(position, connection=self.writer,
            owner_guard=lambda *_: True, edge_passability=lambda *_: True,
            store=movement.PositionStore(Path(folder.name) / 'characters.json'))
        self.ctx.realm.service = lambda writer: service
        self.state.profile = replace(self.state.profile, character_class=1)
        base = AsyncMock(return_value=MovementResult(True, ()))
        self.ctx._world_move_for_handler = base
        f._world_magic_consumers(self.ctx)
        self.magic.apply_status(1, 'slow', self.fixture.now, 10, source_uid=2, spell=28,
            params={'interval_multiplier': 2})
        call = self.ctx._world_move_for_handler
        accepted = await call(self.writer, None, None, b'', self.fixture.now)
        self.assertTrue(accepted.accepted)
        slow = await call(self.writer, None, None, b'', self.fixture.now + .01)
        self.assertFalse(slow.accepted)
        self.assertEqual(int.from_bytes(slow.frames[0][2:4], 'little'), 0x4ee0)
        self.magic.apply_status(1, 'paralyze', self.fixture.now, 10, source_uid=2, spell=33)
        paralyzed = await call(self.writer, None, None, b'', self.fixture.now + .02)
        self.assertFalse(paralyzed.accepted)
        self.assertEqual(service.corrections_prepared, 2)
        self.assertEqual(service.correction_reasons, {'MAGIC_SLOW_CADENCE': 1, 'MAGIC_PARALYZED': 1})
        self.assertEqual(service.last_result['reason'], 'MAGIC_PARALYZED')
        base.assert_awaited_once()

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
        self.use_core_stats(base)
        actual, _, _ = self.ctx._world_stats_for(SimpleNamespace(uid=1, name='MagicMage'))
        self.assertEqual(actual.weight, world_weight.weight_state(100, actual.max_weight))
        self.assertGreater(actual.weight.gauge, 0)

    def test_companion_token_registered_weight_survives_player_stats_refresh(self):
        from tools.local_original_session import world_stats, world_weight, world_handlers
        from tools.local_original_session.world_bridge import Context
        from tools.local_original_session.world_feature_companion import _companion_initialize
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            self.ctx.realm.store = SimpleNamespace(path=Path(directory) / 'characters.json')
            self.ctx._companion_save = Mock()
            self.ctx._world_handler_bindings = world_handlers.HostBindings(
                None, None, {}, {}, 1, None, None)
            context = Context(self.ctx)
            with patch.dict('os.environ', {'SL_COMPANION': '1'}):
                _companion_initialize(context)
            self.assertEqual(context.item_policies[2070].raw_weight, 78)
            self.ctx.item_policies = context.item_policies
            frame = inventory.build_kit_frame([fields(456, 2070)])
            self.ctx._item_equipment_effect = SimpleNamespace(store=SimpleNamespace(
                peek=lambda uid: (None, frame)))
            base = world_stats.calculate_stats(world_stats.CharacterStats(30, 1,
                world_stats.Attributes(18, 13, 16, 10, 10, 10)))
            self.use_core_stats(base)
            actual, _, _ = self.ctx._world_stats_for(SimpleNamespace(uid=1, name='MagicMage'))
            self.assertEqual(actual.weight, world_weight.weight_state(1, actual.max_weight))

    def test_optional_stats_modifier_keeps_core_method_and_existing_buff_lifetime(self):
        from tools.local_original_session import world_handlers, world_feature_stats as stats
        self.assertIs(world_handlers.feature_registry().methods['_world_stats_for'],
                      stats._world_stats_for)
        from tools.local_original_session import world_stats
        base = world_stats.calculate_stats(world_stats.CharacterStats(20, 1,
            world_stats.Attributes(18, 13, 16, 10, 10, 10)))
        self.use_core_stats(base)
        position = SimpleNamespace(uid=1, name='FixtureKnight')
        baseline = self.ctx._world_stats_for(position, level=20)[0]
        f._world_magic_consumers(self.ctx)
        self.magic.committed(1, self.magic.spells[2], self.fixture.now)
        projected = self.ctx._world_stats_for(position, level=20)[0]
        self.assertEqual(projected.ac, baseline.ac - 2)
        self.assertEqual(projected.attributes, baseline.attributes)
        self.assertIs(self.ctx._world_stats_for.__func__, stats._world_stats_for)
        f._world_magic_stopped(self.ctx)
        self.assertEqual(self.ctx._world_stats_for(position, level=20)[0], projected)
        self.fixture.now += 11
        restored = self.ctx._world_stats_for(position, level=20)[0]
        self.assertEqual(restored, baseline)

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
        self.use_core_stats(calculated, info)
        for now in (100, 102):
            self.fixture.now = now
            self.ctx._world_magic_cast(1, 25, 1, now)
            buffed = self.ctx._world_stats_for(SimpleNamespace(uid=1, name='MagicMage'))[0]
            self.assertEqual(buffed.attributes.dexterity, 12)
            self.assertEqual(stats.self_info_fields({}, buffed)[5], 12)
            self.assertEqual(base.attributes.dexterity, 7)
        self.fixture.now = 113
        expired = self.ctx._world_stats_for(SimpleNamespace(uid=1, name='MagicMage'))[0]
        self.assertEqual(expired.attributes.dexterity, 7)
        self.ctx._world_stats_for = original


class JobSecondRulesTests(unittest.TestCase):
    def setUp(self):
        self.magic = m.PlayerMagic(m.load_catalog())

    def test_selected_element_is_explicit_persisted_and_offline_independent(self):
        magic = self.magic
        for key in (146, 147, 148, 150, 151, 162, 165, 167, 169):
            spell = magic.spells[key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'ELF_ELEMENT_REQUIRED'):
                magic.learn(1, spell, 2, 60)
            element = spell.raw['player_policy'].get('required_element', 'water')
            magic.select_element(1, element)
            magic.state(1).learned.add(key)
            magic.admit_cast(1, key, 2, 60, 100, True, 100)
            magic.select_element(1, None)
        magic.select_element(1, 'fire')
        row = magic.snapshot(1, 100, wall=1000)
        m._row(row)
        fresh = m.PlayerMagic(m.load_catalog())
        self.assertEqual(fresh.restore(1, row, 500, wall=2000).elf_element, 'fire')
        self.assertIsNone(m.PlayerMagic(m.load_catalog()).restore(1,
            {k: v for k, v in row.items() if k != 'elf_element'}, 500, wall=2000).elf_element)
        with self.assertRaisesRegex(ValueError, 'ELF_ELEMENT_VALUE'):
            magic.select_element(1, 'lightning')

    def test_element_attack_and_armor_families_replace_and_change_school_clears(self):
        magic = self.magic
        magic.select_element(1, 'fire')
        magic.state(1).learned.update((147, 162, 146, 150, 167))
        for key in (147, 162, 146):
            magic.committed(1, magic.spells[key], 100)
        bonuses = magic.job_bonuses(1, 101)
        self.assertEqual((bonuses['melee_hit'], bonuses['melee_damage'], bonuses['resist_fire']), (3, 5, 50))
        self.assertNotIn(147, magic.state(1).buffs)
        magic.committed(1, magic.spells[150], 100)
        magic.committed(1, magic.spells[167], 100)
        self.assertEqual(magic.ac_bonus(1, 101), -7)
        magic.state(1).learned.add(20)
        magic.committed(1, magic.spells[20], 100)
        magic.state(1).armor_uids[20] = 450
        self.assertEqual(magic.ac_bonus(1, 101, armor_uid=450), -10)
        magic.committed(1, magic.spells[2], 100)
        self.assertEqual(magic.ac_bonus(1, 101, armor_uid=450), -5)
        self.assertNotIn(167, magic.state(1).buffs)
        self.assertEqual(magic.state(1).armor_uids, {20: 450})
        magic.select_element(1, 'water')
        self.assertEqual(set(magic.state(1).buffs), {2, 20})

    def test_stun_entangle_probability_and_exact_movement_attack_split(self):
        from tools.local_original_session import world_magic_status as s
        effects = {}
        s.apply(effects, 'entangle', 100, 30, params={'move_multiplier': 2})
        self.assertEqual(s.ai_status(effects, 101), dict(blocked=False, move_factor=2, attack_factor=1, sight=None))
        s.apply(effects, 'stun', 100, 2)
        self.assertTrue(s.ai_status(effects, 101)['blocked'])
        self.assertFalse(s.ai_status(effects, 102)['blocked'])
        import random
        durations = {s.stun_duration(random.Random(i)) for i in range(100)}
        self.assertEqual(durations, {1, 2, 3, 4})
        self.assertTrue(s.level_probability(50, 2, 99, 1, random.Random(0)))
        self.assertFalse(s.level_probability(50, 2, 1, 99, random.Random(0)))

    def test_erase_once_heal_multiplier_once_expire_and_saved_statuses(self):
        magic = self.magic
        magic.state(1).learned = {152, 169}
        magic.apply_status(1, 'erase_magic', 100, 16, source_uid=2, spell=152)
        magic.apply_status(1, 'water_life', 100, 64, source_uid=1, spell=169,
                           params={'healing_multiplier': 1.5})
        self.assertEqual(magic.effective_mr(1, 101, 101), 50)
        row = magic.snapshot(1, 101, wall=1000)
        m._row(row)
        fresh = m.PlayerMagic(m.load_catalog())
        fresh.restore(1, row, 200, wall=1001)
        self.assertTrue(fresh.consume_erase(1, 200))
        self.assertEqual(fresh.effective_mr(1, 101, 200), 101)
        self.assertFalse(fresh.consume_erase(1, 200))
        self.assertEqual(fresh.healing_amount(1, 11, 200), 16)
        self.assertEqual(fresh.healing_amount(1, 11, 200), 11)
        magic.expire(165)
        self.assertEqual(magic.state(1).effects, {})

    def test_every_job_source_is_closed_or_has_specific_dependency_reason(self):
        keys = {row['classic_key']['value'] for row in m.load_catalog()['spells']
                if row['classic_key']['value'] >= 86}
        self.assertFalse(set(m.JOB_POLICIES) & set(m.JOB_DEFERRED))
        self.assertEqual(keys, set(m.JOB_POLICIES) | set(m.JOB_DEFERRED))


if __name__ == '__main__':
    unittest.main()
