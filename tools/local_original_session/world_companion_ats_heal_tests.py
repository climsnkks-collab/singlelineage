"""LOCAL healing selection/save/consumer tests; no game, ports, or user saves."""
import copy
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import world_feature_companion_ats as ats
from tools.local_original_session import world_companion_ats_spell_tests as spells
from tools.local_original_session import world_companion_ats_window_tests as window
from tools.local_original_session import world_companion_magic_tests as magic
from tools.local_original_session.world_feature_companion import CompanionAilments


def slots(hp=None, status=None, percent=50):
    return [dict(spell_row=hp if i == 0 else None, percent=percent) for i in range(4)] + [
        dict(spell_row=status), dict(spell_row=None)]


class HealMetadataTests(unittest.TestCase):
    def setUp(self):
        self.fixture = spells.CompanionATSSpellTests()
        self.fixture.setUp()
        self.fixture.learned = frozenset((0, 2, 8, 18, 34, 36))
        self.ctx = self.fixture.ctx

    def test_view_classifies_five_supported_heals_and_defaults_six_slots(self):
        view = ats._ats_window_view(self.ctx, 9, 1)
        self.assertEqual({r['spell_row']: r.get('heal_kind') for r in view['learned_spells']},
                         {0: 'hp', 2: None, 8: 'status', 18: 'hp', 34: 'hp', 36: 'status'})
        self.assertEqual(view['heal_slots'], [dict(kind='hp', slot=None, percent=50) for _ in range(4)] + [
            dict(kind='status', slot=None) for _ in range(2)])
        self.ctx._ats_store['characters']['9'] = dict(companion_heal=slots(18, 8, 70))
        reopened = ats._ats_window_view(self.ctx, 9, 2)['heal_slots']
        self.assertEqual(reopened[0]['slot']['spell_row'], 18)
        self.assertEqual(reopened[0]['percent'], 70)
        policy = ats._ats_policy(self.ctx, None, 9)
        self.assertEqual(policy['status'], 'valid')
        self.assertEqual(policy['heal_slots'][4]['spell'], 'cure_poison')

    def test_kind_percent_and_learning_validation(self):
        ats._ats_window_check_learned(self.ctx, 9, dict(heal_slots=slots(18, 8, 70)))
        for selected, suffix in ((slots(8), 'KIND'), (slots(status=0), 'KIND'),
                                 (slots(2), 'KIND'), (slots(0, percent=15), 'PERCENT'),
                                 (slots(0)[:5], 'SLOTS_REQUIRED'), (slots(999), 'SPELL_ROW_UNKNOWN')):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, 'ATS_WINDOW_HEAL_' + suffix):
                ats._ats_window_check_learned(self.ctx, 9, dict(heal_slots=selected))
        self.fixture.learned = frozenset((2,))
        with self.assertRaisesRegex(ValueError, 'ATS_WINDOW_HEAL_SPELL_NOT_LEARNED'):
            ats._ats_window_check_learned(self.ctx, 9, dict(heal_slots=slots(0)))


class HealWindowTests(unittest.TestCase):
    def setUp(self):
        self.window = window.CompanionATSWindowTests()
        self.window.setUp()
        self.addCleanup(self.window.doCleanups)
        self.spells = spells.CompanionATSSpellTests()
        self.spells.setUp()
        self.ctx = self.window.ctx
        self.ctx._world_magic = self.spells.ctx._world_magic
        self.ctx._ats_window_ui = self.spells.ctx._ats_window_ui
        self.learned = frozenset((0, 2, 8, 18, 34, 36))
        self.ctx.collect_sync_hooks = lambda *args: (self.learned,)

    def test_metadata_defaults_save_reopen_and_policy_use_same_rows(self):
        view = self.window.open()
        kinds = {r['spell_row']: r.get('heal_kind') for r in view['learned_spells']}
        self.assertEqual(kinds, {0: 'hp', 2: None, 8: 'status', 18: 'hp', 34: 'hp', 36: 'status'})
        self.assertEqual(view['heal_slots'], [dict(kind='hp', slot=None, percent=50) for _ in range(4)] + [
            dict(kind='status', slot=None) for _ in range(2)])
        before = self.ctx._ats_store['characters']['9']['companion_ats']
        old_policy = ats._ats_policy(self.ctx, None, 9)
        selected = slots(18, 8, 70)
        result = self.window.save(dict(heal_slots=selected))
        self.assertEqual(result['status'], 'OK', result)
        self.assertNotIn(9, self.ctx._ats_policies)
        persisted = json.loads(self.ctx._ats_path.read_text(encoding='utf-8'))['characters']['9']
        self.assertEqual(persisted['companion_ats'], before)
        self.assertEqual(persisted['companion_heal'], selected)
        self.ctx._ats_store = json.loads(self.ctx._ats_path.read_text(encoding='utf-8'))
        reopened = self.window.open()['heal_slots']
        self.assertEqual(reopened[0], dict(kind='hp', slot=dict(self.ctx._ats_window_ui[18]), percent=70))
        self.assertEqual(reopened[4]['slot']['spell_row'], 8)
        policy = ats._ats_policy(self.ctx, None, 9)
        self.assertIsNot(policy, old_policy)
        self.assertEqual((policy['heal_slots'][0]['spell'], policy['heal_slots'][4]['spell']),
                         ('extra_heal', 'cure_poison'))

    def test_heal_only_without_blob_stays_local_and_can_drive_ai(self):
        self.ctx._ats_store['characters']['9'].pop('companion_ats')
        self.window.open()
        self.assertEqual(self.window.save(dict(heal_slots=slots(0)))['status'], 'OK')
        self.assertNotIn('companion_ats', self.ctx._ats_store['characters']['9'])
        self.assertEqual(ats._ats_policy(self.ctx, None, 9)['status'], 'valid')

    def test_invalid_kind_percent_learning_and_shape_are_rejected(self):
        self.window.open()
        cases = [(slots(8), 'KIND'), (slots(status=0), 'KIND'),
                 (slots(2), 'KIND'), (slots(0, percent=15), 'PERCENT'),
                 (slots(0)[:5], 'SLOTS_REQUIRED'), (slots(999), 'SPELL_ROW_UNKNOWN')]
        for selected, reason in cases:
            with self.subTest(reason=reason):
                result = self.window.save(dict(heal_slots=selected))
                self.assertEqual(result['reason'], 'ATS_WINDOW_HEAL_' + reason)
        self.learned = frozenset((2,))
        result = self.window.save(dict(heal_slots=slots(0)))
        self.assertEqual(result['reason'], 'ATS_WINDOW_HEAL_SPELL_NOT_LEARNED')

    def test_heal_write_failure_rolls_back_row_blob_and_cached_policy(self):
        self.window.open()
        before = copy.deepcopy(self.ctx._ats_store)
        original = self.ctx._ats_path.read_bytes()
        policy = ats._ats_policy(self.ctx, None, 9)
        with patch.object(ats, '_ats_save_store', side_effect=OSError('injected heal write failure')):
            result = self.window.save(dict(heal_slots=slots(0, 8)))
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(self.ctx._ats_store, before)
        self.assertEqual(self.ctx._ats_path.read_bytes(), original)
        self.assertIs(self.ctx._ats_policies[9], policy)


class HealAITests(unittest.TestCase):
    def setUp(self):
        self.fixture = magic.MagicTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for name in ('view', 'magic', 'actor', 'entity', 'record', 'owner', 'owner_state'):
            setattr(self, name, getattr(self.fixture, name))
        self.record.level = 30
        self.record.learned_spells = (0, 2, 8, 18, 34, 36)
        self.record.mp = self.record.max_mp = 200
        self.actor.shield_until = 0
        self.saved = []
        self.view.companion_save = lambda uid, receipt=None: self.saved.append(uid)
        self.ailments = CompanionAilments(self.view)
        self.magic.ctx = NS(_companion_ailments=self.ailments,
                            collect_sync_hooks=lambda *args: (), run_sync_hooks=lambda *args: None)
        self.fixture.policy['heal_slots'] = []

    def configure(self, hp=0, status=None, percent=50):
        row = dict(companion_heal=slots(hp, status, percent))
        ctx = NS(_world_magic=self.magic.engine)
        self.fixture.policy['heal_slots'] = ats._ats_heal_policy(ctx, row)

    def decision(self, now=10):
        return self.magic.step(self.actor, self.entity, self.owner, None, now, False)

    def other(self, character=3, owner=1):
        from tools.local_original_session.world_companion import CompanionRecord
        record = CompanionRecord(character, owner, 'development-fixture', hp=10, max_hp=100)
        self.view.companions.register(record, roster={
            owner: dict(account_id='development-fixture', class_id=1),
            character: dict(account_id='development-fixture', class_id=3)})
        actor = self.view.companions.summon(character, owner, 0, self.entity.x + 1, self.entity.y)
        return actor, self.view.entities.resolve(actor.ref)

    def test_lowest_hp_party_heals_before_buff_and_persists_other_companion(self):
        other, entity = self.other()
        self.record.hp = self.record.max_hp // 2
        self.owner_state.hp = self.owner_state.max_hp // 4
        self.configure()
        self.assertTrue(self.decision())
        self.assertEqual((self.magic.events[-1]['spell'], self.magic.events[-1]['target']), ('heal', entity.uid))
        self.assertGreater(other.record.hp, 10)
        self.assertEqual(self.record.mp, 196)
        self.assertEqual(self.saved[-1], 1)
        self.assertEqual(self.actor.shield_until, 0)

    def test_percent_inclusive_full_hp_skipped_and_first_slot_wins(self):
        self.configure(hp=18, percent=50)
        self.record.max_hp = 100
        self.record.hp = 51
        self.owner_state.hp = self.owner_state.max_hp
        self.fixture.policy['buff_slots'] = []
        self.fixture.policy['battle_slots'] = []
        self.assertFalse(self.decision())
        self.record.hp = 50
        self.fixture.policy['heal_slots'][1].update(spell='heal', spell_row=0, percent=50)
        self.assertTrue(self.decision(11))
        self.assertEqual(self.magic.events[-1]['spell'], 'extra_heal')
        self.record.hp = self.record.max_hp
        self.assertFalse(self.decision(12))

    def test_map_range_los_and_unlearned_skip_before_buff(self):
        other, entity = self.other()
        self.record.hp = self.record.max_hp
        self.owner_state.hp = self.owner_state.max_hp
        self.configure()
        for mode in ('map', 'range', 'los', 'unlearned'):
            with self.subTest(mode=mode):
                self.magic.engine.states.clear()
                self.record.equipment.pop('magic_buffs', None)
                self.actor.shield_until = self.actor.next_cast_at = 0
                self.magic.cooldowns.clear()
                entity.map_id = 1 if mode == 'map' else 0
                entity.x = self.entity.x + (100 if mode == 'range' else 1)
                self.record.learned_spells = (2,) if mode == 'unlearned' else (0, 2)
                with patch('tools.local_original_session.npc_ai.local_line_clear',
                           side_effect=lambda terrain, map_id, x, y, tx, ty: mode != 'los' or (x, y) == (tx, ty)):
                    self.assertTrue(self.decision(10))
                self.assertEqual(self.magic.events[-1]['spell'], 'shield')
                self.assertEqual(other.record.hp, 10)

    def test_status_slots_cure_other_companion_before_buff(self):
        from tools.local_original_session import world_magic_status as status
        other, entity = self.other()
        for index, name in enumerate(('cure_poison', 'remove_curse')):
            at = 10 + index * 2
            self.configure(hp=None, status=self.magic.rules[name].key)
            row = self.ailments.state(other, at)
            row['poison'] = dict(until=at + 30, next_tick=at + 3, tick_seconds=3, damage=1, source_uid=999)
            if name == 'remove_curse':
                status.apply(row['effects'], 'blind', at, 30)
            self.assertTrue(self.decision(at))
            self.assertEqual((self.magic.events[-1]['spell'], self.magic.events[-1]['target']), (name, entity.uid))
            self.assertIsNone(row['poison'])
            self.assertFalse(any(status.active(row['effects'], k, at) for k in status.CURSES))
            self.assertIsNone(other.record.equipment['monster_ailments']['poison'])
            self.assertEqual(self.saved[-1], 1)
        self.assertEqual(self.actor.shield_until, 0)


if __name__ == '__main__':
    unittest.main()
