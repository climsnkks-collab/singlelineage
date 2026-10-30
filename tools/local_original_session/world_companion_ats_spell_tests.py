"""Pure companion ATS spell metadata, learning, and policy checks."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from tools.local_original_session import ats_config_codec as codec
from tools.local_original_session.ats_config_codec_tests import CAPTURED_COMPANION_ATS
from tools.local_original_session import world_feature_companion_ats as ats


ROOT = Path(__file__).resolve().parents[2]


class CompanionATSSpellTests(unittest.TestCase):
    def setUp(self):
        catalog = json.loads((ROOT / 'tools/local_original_session/data/m3/player_spells.json').read_text(
            encoding='utf-8'))
        ui_rows = json.loads((ROOT / 'work/all_table_semantics/spell_token/spell-ui-joins.json').read_text(
            encoding='utf-8'))
        ui = {row['spell_id']: dict(spell_row=row['spell_id'], name=row['name_KR'],
                                   icon=row['named_UI_configuration']['icon'])
              for row in ui_rows if type(row.get('spell_id')) is int and row['spell_id'] >= 0
              and row.get('named_UI_configuration', {}).get('id') == row['spell_id']}
        self.learned = frozenset((0, 2, 3, 54, 86, 999))
        self.ctx = NS(_world_magic=NS(catalog=catalog), _ats_window_ui=ui,
            _ats_enabled=True, _ats_events=[], _ats_policies={},
            _ats_store={'characters': {'9': {'companion_ats': CAPTURED_COMPANION_ATS.hex()}}},
            world=NS(companion_looks={9: {'name': 'SoloMage'}}, data=NS(items={})),
            collect_sync_hooks=lambda name, uid: (self.learned,)
                if (name, uid) == ('character_learned_spells', 9) else ())

    def test_learned_view_joins_all_player_magic_keys_and_reports_unknown(self):
        known = ats._ats_window_spell_catalog(self.ctx)
        self.assertEqual(len(known), 80)
        view = ats._ats_window_view(self.ctx, 9, 7)
        self.assertEqual(view['learned_spells'], [
            dict(spell_row=0, name='힐', icon=383, heal_kind='hp'),
            dict(spell_row=2, name='실드', icon=385),
            dict(spell_row=3, name='에너지 볼트', icon=386),
            dict(spell_row=86, name='쇼크 스턴', icon=1624)])
        self.assertEqual(view['learned_spells_unknown'], [54, 999])

    def test_save_requires_current_member_learning_and_known_ui_row(self):
        change = {'buff_slots': [{'spell_row': 0}]}
        ats._ats_window_check_learned(self.ctx, 9, change)
        self.learned = frozenset((2,))
        with self.assertRaisesRegex(ValueError, 'ATS_WINDOW_SPELL_NOT_LEARNED'):
            ats._ats_window_check_learned(self.ctx, 9, change)
        with self.assertRaisesRegex(ValueError, 'ATS_WINDOW_SPELL_NOT_LEARNED'):
            ats._ats_window_check_learned(self.ctx, 9, {'battle_slots': [
                dict(kind='sequence', index=0, slot=dict(spell_row=3))]})
        self.learned = frozenset((999,))
        with self.assertRaisesRegex(ValueError, 'ATS_WINDOW_SPELL_ROW_UNKNOWN'):
            ats._ats_window_check_learned(self.ctx, 9, {'buff_slots': [{'spell_row': 999}]})

    def test_unmapped_saved_magic_is_readonly_while_sibling_spell_changes(self):
        f = codec.field
        unknown = f(1, 0, 1) + f(4, 0, 54) + f(99, 0, 7)
        empty = f(1, 0, 0) + f(4, 0, -1)
        raw = f(1, 2, f(2, 2, f(1, 2, f(7, 2, unknown) + f(7, 2, empty))))
        wrapper = codec.wrap_blob(raw)
        self.ctx._ats_store['characters']['9']['companion_ats'] = wrapper.hex()
        view = ats._ats_window_view(self.ctx, 9, 7)
        marker = dict(spell_row=54, name=None, icon=None, status='UNKNOWN')
        self.assertEqual(view['buff_slots'][0], marker)
        changes = {'buff_slots': [marker, {'spell_row': 0}]}
        ats._ats_window_check_learned(self.ctx, 9, changes, wrapper)
        saved = codec.apply_window_changes(wrapper, changes)
        before = codec.decode_options(codec.unwrap_blob(wrapper))['buff_slots']
        after = codec.decode_options(codec.unwrap_blob(saved))['buff_slots']
        self.assertEqual((after[0], after[1][4]), (before[0], 0))
        for proposed in (None, {'spell_row': 0}):
            with self.subTest(proposed=proposed), self.assertRaisesRegex(
                    ValueError, 'ATS_WINDOW_SPELL_READONLY'):
                ats._ats_window_check_learned(self.ctx, 9,
                    {'buff_slots': [proposed, {'spell_row': 0}]}, wrapper)

    def test_saved_magic_view_and_ai_policy_use_client_rows(self):
        raw = codec.decode_options(codec.unwrap_blob(CAPTURED_COMPANION_ATS))
        buff = [None] * len(raw['buff_slots'])
        buff[0] = dict(spell_row=2)
        battle = [dict(kind=row['kind'], index=row['index'], slot=None,
                       **({key: row.get(key) for key in ('condition', 'value')}
                          if row['kind'] == 'conditional' else {}))
                  for row in raw['battle_slots']]
        battle[0]['slot'] = dict(spell_row=3)
        updated = codec.apply_window_changes(CAPTURED_COMPANION_ATS,
                                             {'buff_slots': buff, 'battle_slots': battle})
        self.ctx._ats_store['characters']['9']['companion_ats'] = updated.hex()
        view = ats._ats_window_view(self.ctx, 9, 8)
        self.assertEqual(view['buff_slots'][0], dict(spell_row=2, name='실드', icon=385))
        self.assertEqual(view['battle_slots'][0]['slot'],
                         dict(spell_row=3, name='에너지 볼트', icon=386))
        policy = ats._ats_policy(self.ctx, None, 9)
        self.assertEqual(policy['maintain_buffs'], ['shield'])
        self.assertEqual(policy['attack_spells'], ['energy_bolt'])


if __name__ == '__main__':
    unittest.main()
