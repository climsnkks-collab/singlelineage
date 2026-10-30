"""Quest persistence/recovery on disposable profiles; no game or port tests."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import equipment_store, inventory, inventory_store, world_progress
from tools.local_original_session import world_quest_store as q
from tools.local_original_session.world_quest import QuestState


def fields(uid, count=1):
    return {1: uid, 2: 1, 3: 0, 4: count, 5: 0, 7: 1, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'\0quest metadata', 22: 0,
            24: False, 25: 0, 26: False}


def kit(*rows):
    return inventory.build_kit_frame(list(rows))


class QuestStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        roster = inventory_store.realm.CharacterStore(self.profile)
        roster.create(inventory_store.realm.Creation('QuestOne', 0, 0, (13,) * 6))
        roster.create(inventory_store.realm.Creation('QuestTwo', 0, 0, (13,) * 6))
        self.inv = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                  kit_policy=inventory.KIT_POLICY)
        self.before = kit(fields(10, 10), fields(11))
        self.after = kit(fields(10, 5), fields(11), fields(12, 2))
        self.inv.grant(1, self.before)
        self.inv.grant(2, kit(fields(20)))
        self.other_inventory = self.inv.restore(2)
        self.progress = world_progress.ProgressStore(self.profile)
        self.store = q.QuestStore(self.inv, self.progress)
        self.empty = QuestState('local_material')
        self.accepted = replace(self.empty, accepted=True, counts=(0,))
        self.complete = replace(self.accepted, completed=True)
        self.pbefore = world_progress.Progress(0, 1)
        self.pafter = world_progress.Progress(200, 2, 30, 12)

    def accept(self):
        return self.store.commit(1, self.empty, self.accepted, class_key='knight',
            reference_before={}, reference_after={'Level15': 0})

    def complete_quest(self, **kwargs):
        return self.store.commit(1, self.accepted, self.complete, class_key='knight',
            reference_before={'Level15': 0}, reference_after={'Level15': 255},
            inventory_before=self.before, inventory_after=self.after,
            progress_before=self.pbefore, progress_after=self.pafter, **kwargs)

    def anchor_equipment(self):
        armor = fields(13)
        armor[2] = 2
        before = kit(fields(10, 10), fields(11), armor)
        self.inv.replace_kit(1, self.before, before, append=True)
        self.before = before
        # Consume the entire unequipped anchor; weapon and armor survive.
        self.after = kit(fields(11), armor, fields(14, 2))
        definitions = {1: SimpleNamespace(kind='weapon'),
                       2: SimpleNamespace(kind='armor', slot_key=1)}
        equip = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=definitions)
        old = equip.initialize_kit(1, self.before, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                                   weapon_uid=11, slots=((1, 13),))
        other = equip.initialize_kit(2, self.other_inventory, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                                     weapon_uid=20, slots=())
        new = replace(old, item_uid=11, template=1, revision=old.revision + 1)
        return equip, old, new, other, definitions

    def recover(self):
        # A fresh progression owner must read an ambiguous disk outcome again.
        self.progress = world_progress.ProgressStore(self.profile)
        self.store = q.QuestStore(self.inv, self.progress)
        return self.store

    def assert_completed(self):
        self.assertEqual(self.inv.restore(1), self.after)
        self.assertEqual(self.inv.restore(2), self.other_inventory)
        self.assertEqual(self.progress.get(1), self.pafter)
        self.assertEqual(self.store.get(1, self.empty.quest_id), self.complete)
        self.assertEqual(self.store.reference_steps(1, 'knight'), {'Level15': 255})
        self.assertFalse(self.store.intent_path.exists())

    def test_acceptance_roundtrip_preserves_other_quests_classes_and_characters(self):
        self.assertEqual(self.store.get(1, self.empty.quest_id), self.empty)
        self.assertEqual(self.store.reference_steps(1, 'knight'), {})
        self.assertFalse(self.store.path.exists())
        self.assertTrue(self.accept())
        another = QuestState('another', True, counts=(1,), seen_events=('real-event',))
        self.store.commit(1, QuestState('another'), another, class_key='mage',
                          reference_before={}, reference_after={'Level15': 4})
        other = QuestState('other_pc', True)
        self.store.commit(2, QuestState('other_pc'), other, class_key='knight',
                          reference_before={}, reference_after={'Level15': 7})
        data = json.loads(self.store.path.read_bytes())
        self.assertEqual(set(data), {'version', 'rows'})
        self.assertEqual(data['version'], 1)
        self.recover()
        self.assertEqual(self.store.get(1, self.empty.quest_id), self.accepted)
        self.assertEqual(self.store.get(1, 'another'), another)
        self.assertEqual(self.store.get(2, 'other_pc'), other)
        self.assertEqual(self.store.reference_steps(1, 'mage'), {'Level15': 4})
        self.assertEqual(self.store.reference_steps(2, 'knight'), {'Level15': 7})
        self.assertEqual(self.inv.restore(1), self.before)
        self.assertFalse(self.progress.path.exists())

    def test_cache_reads_and_acceptance_add_no_request_file_reads(self):
        with patch.object(Path, 'open', side_effect=AssertionError('REQUEST_READ')):
            self.assertEqual(self.store.get(1, self.empty.quest_id), self.empty)
            self.assertEqual(self.store.reference_steps(1, 'knight'), {})
            self.assertFalse(self.store.commit(1, self.empty, self.empty, class_key='knight',
                                               reference_before={}, reference_after={}))
        # Acceptance writes files but must not read even inventory or progression.
        original = Path.open
        def write_only(path, mode='r', *args, **kwargs):
            if 'r' in mode or '+' in mode:
                raise AssertionError('REQUEST_READ')
            return original(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', write_only), \
                patch.object(self.inv, 'restore', side_effect=AssertionError('REQUEST_RESTORE')), \
                patch.object(self.progress, '_load', side_effect=AssertionError('REQUEST_LOAD')):
            self.assertTrue(self.accept())
        refs = self.store.reference_steps(1, 'knight')
        refs['Level15'] = 99
        self.assertEqual(self.store.reference_steps(1, 'knight'), {'Level15': 0})

    def test_completion_orders_inventory_then_exp_then_quest_and_refuses_duplicate(self):
        self.accept()
        events = []
        save_inventory, save_progress, save_quests = self.inv.replace_kit, self.progress.commit, self.store._write_rows
        def inv(*args, **kwargs):
            events.append('inventory')
            return save_inventory(*args, **kwargs)
        def progress(*args, **kwargs):
            self.assertEqual(self.inv.restore(1), self.after)
            events.append('progress')
            return save_progress(*args, **kwargs)
        def quests(*args, **kwargs):
            self.assertEqual(self.progress.get(1), self.pafter)
            events.append('quests')
            return save_quests(*args, **kwargs)
        with patch.object(self.inv, 'replace_kit', side_effect=inv), \
                patch.object(self.progress, 'commit', side_effect=progress), \
                patch.object(self.store, '_write_rows', side_effect=quests):
            self.assertTrue(self.complete_quest())
        self.assertEqual(events, ['inventory', 'progress', 'quests'])
        with self.assertRaisesRegex(ValueError, 'EXPECTED_STATE_CHANGED'):
            self.complete_quest()
        self.assert_completed()
        self.recover()
        self.assert_completed()

    def test_each_save_interruption_stays_pending_and_recovers_forward(self):
        self.accept()
        for index, (owner, method) in enumerate((('inv', 'replace_kit'), ('progress', 'commit'),
                                               ('store', '_write_rows'))):
            with self.subTest(stage=method):
                if index:
                    # Independent disposable profiles, never rewind an old save.
                    self.setUp()
                    self.accept()
                with patch.object(getattr(self, owner), method, side_effect=OSError('interrupted')):
                    with self.assertRaises(OSError):
                        self.complete_quest()
                self.assertTrue(self.store.intent_path.exists())
                with self.assertRaisesRegex(ValueError, 'RECOVERY_REQUIRED'):
                    self.complete_quest()
                self.recover()
                self.assert_completed()

    def test_uncertain_intent_write_blocks_live_retry_even_before_disk_intent_exists(self):
        with patch.object(q, '_atomic_json', side_effect=OSError('intent interrupted')):
            with self.assertRaises(OSError):
                self.accept()
        self.assertFalse(self.store.intent_path.exists())
        with self.assertRaisesRegex(ValueError, 'RECOVERY_REQUIRED'):
            self.accept()
        self.recover()
        self.assertEqual(self.store.get(1, self.empty.quest_id), self.empty)
        self.assertTrue(self.accept())

    def test_ambiguous_progress_replace_recovers_disk_value_without_repeating_award(self):
        self.accept()
        original = world_progress.os.replace
        def interrupted(source, target):
            original(source, target)
            if Path(target) == self.progress.path:
                raise OSError('after progression replace')
        with patch.object(world_progress.os, 'replace', side_effect=interrupted):
            with self.assertRaises(OSError):
                self.complete_quest()
        self.assertEqual(self.progress.get(1), self.pbefore)  # Old live cache is unusable.
        with patch.object(world_progress.ProgressStore, 'commit', side_effect=AssertionError('REPEATED_EXP')):
            self.recover()
        self.assert_completed()

    def test_intent_cleanup_failure_does_not_repeat_any_participant(self):
        self.accept()
        original = Path.unlink
        def interrupted(path, *args, **kwargs):
            if path == self.store.intent_path:
                raise OSError('after all saves')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', interrupted):
            with self.assertRaises(OSError):
                self.complete_quest()
        with patch.object(self.inv, 'replace_kit', side_effect=AssertionError('REPEATED_INVENTORY')), \
                patch.object(world_progress.ProgressStore, 'commit', side_effect=AssertionError('REPEATED_EXP')):
            self.recover()
        self.assert_completed()

    def test_ambiguous_quest_replace_recovers_complete_row_without_repeating_rewards(self):
        self.accept()
        original = world_progress.os.replace
        def interrupted(source, target):
            original(source, target)
            if Path(target) == self.store.path:
                raise OSError('after quest replace')
        with patch.object(world_progress.os, 'replace', side_effect=interrupted):
            with self.assertRaises(OSError):
                self.complete_quest()
        self.assertEqual(self.store.get(1, self.empty.quest_id), self.accepted)
        with patch.object(self.inv, 'replace_kit', side_effect=AssertionError('REPEATED_INVENTORY')), \
                patch.object(world_progress.ProgressStore, 'commit', side_effect=AssertionError('REPEATED_EXP')):
            self.recover()
        self.assert_completed()

    def test_inventory_conflict_preserves_intent_and_does_not_award_exp(self):
        self.accept()
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.complete_quest()
        intent = self.store.intent_path.read_bytes()
        unrelated = kit(fields(10, 9), fields(11))
        self.inv.replace_kit(1, self.before, unrelated)
        with self.assertRaisesRegex(ValueError, 'RECOVERY_INVENTORY_CONFLICT'):
            self.recover()
        self.assertEqual(self.store.intent_path.read_bytes(), intent)
        self.assertEqual(self.inv.restore(1), unrelated)
        self.assertFalse(self.progress.path.exists())

    def test_progress_conflict_is_checked_before_any_inventory_forward_write(self):
        self.accept()
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.complete_quest()
        unrelated = replace(self.pbefore, exp=30)
        self.progress.commit(1, unrelated)
        with patch.object(self.inv, 'replace_kit', side_effect=AssertionError('FORWARDED_BEFORE_CHECK')):
            with self.assertRaisesRegex(ValueError, 'RECOVERY_PROGRESS_CONFLICT'):
                self.recover()
        self.assertEqual(self.inv.restore(1), self.before)
        self.assertEqual(world_progress.ProgressStore(self.profile).get(1), unrelated)

    def test_quest_row_conflict_is_preserved_before_inventory_or_exp_forward_write(self):
        self.accept()
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.complete_quest()
        data = json.loads(self.store.path.read_bytes())
        data['rows'][0]['reference_steps']['knight']['Level15'] = 4
        self.store.path.write_text(json.dumps(data), encoding='utf-8')
        intent = self.store.intent_path.read_bytes()
        with patch.object(self.inv, 'replace_kit', side_effect=AssertionError('FORWARDED_BEFORE_CHECK')):
            with self.assertRaisesRegex(ValueError, 'RECOVERY_STATE_CONFLICT'):
                self.recover()
        self.assertEqual(self.store.intent_path.read_bytes(), intent)
        self.assertEqual(self.inv.restore(1), self.before)
        self.assertFalse(self.progress.path.exists())

    def test_stale_references_and_progress_fail_before_creating_intent(self):
        self.accept()
        with self.assertRaisesRegex(ValueError, 'EXPECTED_REFERENCE_CHANGED'):
            self.store.commit(1, self.accepted, self.complete, class_key='knight',
                              reference_before={'Level15': 1}, reference_after={'Level15': 255})
        self.progress.commit(1, replace(self.pbefore, exp=1))
        with self.assertRaisesRegex(ValueError, 'EXPECTED_PROGRESS_CHANGED'):
            self.complete_quest()
        self.assertFalse(self.store.intent_path.exists())
        self.assertEqual(self.inv.restore(1), self.before)

    def test_surviving_anchor_saves_equipment_first_and_preserves_worn_and_other_character(self):
        self.accept()
        equip, old, new, other, definitions = self.anchor_equipment()
        events = []
        atomic, inventory_save, progress_save, quest_save = (
            q._atomic_raw, self.inv.replace_kit, self.progress.commit, self.store._write_rows)
        def inv(*args, **kwargs):
            events.append('inventory')
            return inventory_save(*args, **kwargs)
        def equipment(path, raw):
            self.assertEqual(self.inv.restore(1), self.before)
            events.append('equipment')
            return atomic(path, raw)
        def progress(*args, **kwargs):
            self.assertEqual(equip.restore(1, self.after), new)
            events.append('progress')
            return progress_save(*args, **kwargs)
        def quests(*args, **kwargs):
            events.append('quests')
            return quest_save(*args, **kwargs)
        with patch.object(self.inv, 'replace_kit', side_effect=inv), \
                patch.object(q, '_atomic_raw', side_effect=equipment), \
                patch.object(self.progress, 'commit', side_effect=progress), \
                patch.object(self.store, '_write_rows', side_effect=quests):
            self.complete_quest(equipment_store=equip, equipment_before=old, equipment_after=new)
        self.assertEqual(events, ['equipment', 'inventory', 'progress', 'quests'])
        fresh = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=definitions)
        self.assertEqual(fresh.restore(1, self.after), new)
        self.assertEqual((new.weapon_uid, new.slots), (11, ((1, 13),)))
        self.assertEqual(fresh.restore(2, self.other_inventory), other)
        self.assert_completed()

    def test_surviving_anchor_interruption_allows_equipment_constructor_before_recovery(self):
        self.accept()
        equip, old, new, other, definitions = self.anchor_equipment()
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('inventory interrupted')):
            with self.assertRaises(OSError):
                self.complete_quest(equipment_store=equip, equipment_before=old, equipment_after=new)
        self.assertEqual(self.inv.restore(1), self.before)
        self.assertFalse(self.progress.path.exists())
        with self.assertRaisesRegex(ValueError, 'RECOVERY_REQUIRED'):
            self.complete_quest(equipment_store=equip, equipment_before=old, equipment_after=new)
        # Match production startup: equipment must load before QuestStore.
        boot_equipment = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=definitions)
        self.assertEqual(boot_equipment.restore(1, self.before), new)
        with patch.object(q, '_atomic_raw', side_effect=AssertionError('REPEATED_EQUIPMENT')):
            self.recover()
        fresh = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=definitions)
        self.assertEqual(fresh.restore(1, self.after), new)
        self.assertEqual(fresh.restore(2, self.other_inventory), other)
        self.assert_completed()

    def test_equipment_recovery_conflict_is_preserved_before_inventory_or_exp_forward(self):
        self.accept()
        equip, old, new, other, definitions = self.anchor_equipment()
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('inventory interrupted')):
            with self.assertRaises(OSError):
                self.complete_quest(equipment_store=equip, equipment_before=old, equipment_after=new)
        intent = self.store.intent_path.read_bytes()
        data = json.loads(equip.path.read_bytes())
        data['equipment'][0]['revision'] += 2
        equip.path.write_text(json.dumps(data), encoding='utf-8')
        unrelated = equip.path.read_bytes()
        with patch.object(self.inv, 'replace_kit', side_effect=AssertionError('FORWARDED_BEFORE_CHECK')):
            with self.assertRaisesRegex(ValueError, 'RECOVERY_EQUIPMENT_CONFLICT'):
                self.recover()
        self.assertEqual(equip.path.read_bytes(), unrelated)
        self.assertEqual(self.store.intent_path.read_bytes(), intent)
        self.assertEqual(self.inv.restore(1), self.before)
        self.assertFalse(self.progress.path.exists())

    def test_disjoint_anchors_stage_keeps_bootable_equipment_at_every_interruption(self):
        for index, interrupted in enumerate(('stage', 'equipment', 'final', 'progress')):
            with self.subTest(stage=interrupted):
                if index:
                    self.setUp()
                self.accept()
                definitions = {1: SimpleNamespace(kind='weapon')}
                equip = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
                    kit_policy=inventory.KIT_POLICY, item_defs=definitions)
                old = equip.initialize_kit(1, self.before, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                                           weapon_uid=0, slots=())
                # All previous materials disappear; both rewards are fresh UIDs.
                self.after = kit(fields(30, 2), fields(31, 3))
                new = replace(old, item_uid=30, template=1, revision=old.revision + 1)
                stage = kit(fields(10, 10), fields(30, 2))
                events = []
                inventory_save, equipment_save, progress_save = (
                    self.inv.replace_kit, q._atomic_raw, self.progress.commit)
                def save_inventory(uid, before, after, **kwargs):
                    name = 'stage' if after == stage else 'final'
                    events.append(name)
                    result = inventory_save(uid, before, after, **kwargs)
                    if interrupted == name:
                        raise OSError('after ' + name)
                    return result
                def save_equipment(path, raw):
                    events.append('equipment')
                    result = equipment_save(path, raw)
                    if interrupted == 'equipment':
                        raise OSError('after equipment')
                    return result
                def save_progress(*args, **kwargs):
                    events.append('progress')
                    result = progress_save(*args, **kwargs)
                    if interrupted == 'progress':
                        raise OSError('after progress')
                    return result
                with patch.object(self.inv, 'replace_kit', side_effect=save_inventory), \
                        patch.object(q, '_atomic_raw', side_effect=save_equipment), \
                        patch.object(self.progress, 'commit', side_effect=save_progress):
                    with self.assertRaises(OSError):
                        self.complete_quest(equipment_store=equip, equipment_before=old, equipment_after=new)
                self.assertEqual(events, ['stage', 'equipment', 'final', 'progress'][:len(events)])
                intent = json.loads(self.store.intent_path.read_bytes())
                self.assertEqual(bytes.fromhex(intent['inventory_stage']), stage)
                boot_equipment = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
                    kit_policy=inventory.KIT_POLICY, item_defs=definitions)
                current = self.inv.restore(1)
                self.assertEqual(boot_equipment.restore(1, current), old if interrupted == 'stage' else new)
                with patch.object(self.inv, 'replace_kit', wraps=self.inv.replace_kit) as cas, \
                        patch.object(world_progress.ProgressStore, 'commit', autospec=True,
                                     side_effect=world_progress.ProgressStore.commit) as exp:
                    self.recover()
                self.assertEqual(cas.call_count, 1 if interrupted in ('stage', 'equipment') else 0)
                self.assertEqual(exp.call_count, 0 if interrupted == 'progress' else 1)
                self.assertEqual(boot_equipment.restore(1, self.after), new)
                self.assert_completed()

    def test_profile_owner_and_duplicate_or_invalid_save_rows_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'PROGRESS_OWNER'):
            q.QuestStore(self.inv, world_progress.ProgressStore(self.profile.parent / 'other' / 'characters.json'))
        self.accept()
        data = json.loads(self.store.path.read_bytes())
        data['rows'].append(data['rows'][0])
        self.store.path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_CHARACTER'):
            self.recover()

    def test_issued_uids_cycles_and_closed_survive_interrupted_forward_save(self):
        accepted = replace(self.accepted, issued=((11, 1, 1),), cycles=2)
        self.store.commit(1, self.empty, accepted, class_key='knight',
                          reference_before={}, reference_after={})
        completed = replace(accepted, completed=True, closed=True, cycles=3)
        original = self.store._write_rows
        def fail_after_rows(rows):
            original(rows)
            raise OSError('after quest row including issued UID and cycle')
        with patch.object(self.store, '_write_rows', side_effect=fail_after_rows):
            with self.assertRaisesRegex(OSError, 'after quest row'):
                self.store.commit(1, accepted, completed, class_key='knight',
                    reference_before={}, reference_after={},
                    inventory_before=self.before, inventory_after=self.after)
        self.assertTrue(self.store.intent_path.exists())
        self.recover()
        self.assertEqual(self.store.get(1, self.empty.quest_id), completed)
        self.assertEqual(self.inv.restore(1), self.after)
        self.assertFalse(self.store.intent_path.exists())


if __name__ == '__main__':
    unittest.main()
