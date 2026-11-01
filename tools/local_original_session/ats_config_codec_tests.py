"""Offline ATS codec regressions; captured bytes are immutable test input."""
import unittest

from tools.local_original_session import ats_config_codec as codec


# Exact characters.2.companion_ats wrapper captured in manual-test-knight's
# 20261029-002942-4e9cd3ab run; no dependency on the mutable saved profile.
CAPTURED_COMPANION_ATS = bytes.fromhex(
    'af03000001b0000000789ce35ac3cec56aa867a86720b4889deb060b971a0793029f06a3c17f1860'
    'b4127ebd73c5ab0d2d0aafd7ec793375af8286a1818126970c501d420daa06065106060f2729bc4a'
    'f0cbaa32302c70d252002a114495e17db3a5e3f5c2b950b768e13564a0648d18ac78391890e44738'
    'd781c18341680113172f07239228ddb842c21c0c020c52835e504a89835f805f825101949e182d52'
    '80c1c6112012c190909ac150c050f19cbd819101006d380ac0'
)

# Exact owner CharacterConfig from the same read-only manual-test-knight
# evidence: top field 2 has three item links followed by 21 empty slots.
CAPTURED_OWNER_CONFIG = bytes.fromhex(
    'e103000001db000000789ce3bac7ccc56aa867a06720c02c502a102990249021902bd0c028d0c828c0'
    '272028b08249805d4053804d80458047805be019a380acc0eaa60620601158c428202e3013c47ec088'
    '41cfc241cb087cbc0f642d501478c32c304d40e23f0c308e3269c014ba008b6021790e268900053e0'
    'd0603062be1d73b57bcdad0a2f07acd9e3753f72a68181a18680ac90215f82a08821508bed9d2f17'
    'ae15cb8024b4d2125a0b4bfc20a26b0bce89b592b5fedd8f066ee0cb81223a011fc1c0c120c0a48d'
    '68f0a505d408a1d1aa34a3086168c61046338c118009bbb3abf'
)


class NativeAtsCodecTests(unittest.TestCase):
    @staticmethod
    def _magic_changes(wrapper):
        view = codec.decode_options(codec.unwrap_blob(wrapper))

        def selected(slot):
            return ({'spell_row': slot[4]} if slot.get(1) == 1 and slot.get(4, -1) >= 0
                    else None)

        return dict(buff_slots=[selected(slot) for slot in view['buff_slots']],
                    battle_slots=[dict(row, slot=selected(row['slot']))
                                  for row in view['battle_slots']])

    def test_window_captured_magic_save_clear_and_policy(self):
        original = CAPTURED_COMPANION_ATS
        changes = self._magic_changes(original)
        self.assertEqual((len(changes['buff_slots']), len(changes['battle_slots'])), (18, 16))
        self.assertIs(codec.apply_window_changes(original, changes), original)
        changes['buff_slots'][2] = {'spell_row': 2, 'name': 'shield', 'icon': 99}
        changes['battle_slots'][0]['slot'] = {'spell_row': 0, 'name': 'heal'}
        # Existing zero-condition row remains zero; no condition editor is implied.
        changes['battle_slots'][8]['slot'] = {'spell_row': 3}
        saved = codec.apply_window_changes(original, changes)
        before = codec.decode_options(codec.unwrap_blob(original))
        after = codec.decode_options(codec.unwrap_blob(saved))
        for key in ('hp_slots', 'mp_slots', 'function_slots', 'hp_percent', 'mp_percent', 'options'):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after['buff_slots'][2], {1: 1, 4: 2})
        self.assertEqual(after['sequence'][0], {1: 1, 4: 0})
        self.assertEqual(after['conditional'][0], {1: 0, 2: 0, 'slot': {1: 1, 4: 3}})
        policy = codec.companion_policy(saved, {0: 'heal', 2: 'shield', 3: 'energy_bolt'})
        self.assertEqual(policy['maintain_buffs'], ['shield'])
        self.assertEqual(policy['heal_spells'], ['heal'])
        self.assertEqual(policy['attack_spells'], [])
        self.assertEqual(policy['battle_slots'][8]['conditions'], [(0, 0)])
        self.assertIn('ATS_CONDITION_UNKNOWN:0', policy['issues'])
        self.assertIs(codec.apply_window_changes(saved, changes), saved)
        cleared = self._magic_changes(original)
        cleared = codec.apply_window_changes(saved, cleared)
        self.assertIs(codec.apply_window_changes(cleared, self._magic_changes(cleared)), cleared)
        policy = codec.companion_policy(cleared, {0: 'heal', 2: 'shield', 3: 'energy_bolt'})
        self.assertEqual((policy['maintain_buffs'], policy['heal_spells'], policy['issues']), ([], [], []))

    def test_window_magic_preserves_unknown_duplicate_wire_and_mixed_row_order(self):
        f = codec.field
        unknown = b'\x98\x86\x00\x81\x00'
        # The effective f4=0 has a noncanonical tag/value; same selection must
        # leave it and display metadata exact. f7 is never synthesized for spells.
        slot = unknown + f(1, 0, 1) + f(4, 0, 8) + b'\xa0\x00\x80\x00' + f(7, 2, b'opaque')
        expected_slot = unknown + f(1, 0, 1) + f(4, 0, 8) + f(4, 0, 2) + f(7, 2, b'opaque')
        cond = f(1, 0, 5) + unknown + f(2, 0, 8) + f(2, 0, 10)
        cond += f(3, 2, slot) + unknown + f(3, 2, slot)
        expected_cond = f(1, 0, 5) + unknown + f(2, 0, 8) + f(2, 0, 10)
        expected_cond += f(3, 2, slot) + unknown + f(3, 2, expected_slot)
        battle = unknown + f(2, 2, cond) + f(1, 2, slot) + f(2, 2, cond)
        new_battle = unknown + f(2, 2, expected_cond) + f(1, 2, slot) + f(2, 2, cond)
        buff = f(7, 2, slot) + unknown + f(7, 2, slot)
        new_buff = f(7, 2, expected_slot) + unknown + f(7, 2, slot)
        option = unknown + f(1, 2, buff) + f(2, 2, battle) + f(2, 2, battle)
        new_option = unknown + f(1, 2, new_buff) + f(2, 2, new_battle) + f(2, 2, battle)
        payload = unknown + f(1, 2, f(2, 2, option) + unknown) + unknown
        expected = unknown + f(1, 2, f(2, 2, new_option) + unknown) + unknown
        wrapper = codec.wrap_blob(payload, raw=True)
        changes = self._magic_changes(wrapper)
        changes['buff_slots'][0].update(name='metadata only', icon=7)
        self.assertIs(codec.apply_window_changes(wrapper, changes), wrapper)
        changes['buff_slots'][0]['spell_row'] = 2
        changes['battle_slots'][0]['slot']['spell_row'] = 2
        saved = codec.apply_window_changes(wrapper, changes)
        self.assertEqual(codec.unwrap_blob(saved), expected)
        policy = codec.companion_policy(saved, {0: 'heal', 2: 'shield'})
        self.assertEqual([r['kind'] for r in policy['battle_slots']],
                         ['conditional', 'sequence', 'conditional'])
        self.assertEqual(policy['battle_slots'][0]['conditions'], [(5, 10)])
        self.assertEqual(policy['battle_slots'][1]['conditions'], [(5, 10)])

    def test_window_magic_rejects_topology_condition_and_invalid_selection(self):
        import copy

        original = CAPTURED_COMPANION_ATS
        base = self._magic_changes(original)
        mutations = [lambda c: c['buff_slots'].pop(),
                     lambda c: c['buff_slots'].append(None),
                     lambda c: c['battle_slots'].pop(),
                     lambda c: c['battle_slots'][0].update(kind='conditional'),
                     lambda c: c['battle_slots'][0].update(index=1),
                     lambda c: c['battle_slots'][8].update(condition=2),
                     lambda c: c['battle_slots'][8].update(value=1),
                     lambda c: c['battle_slots'][8].pop('condition'),
                     lambda c: c['battle_slots'][8].update(value=True),
                     lambda c: c['battle_slots'][8].update(value=1 << 31)]
        for mutate in mutations:
            changes = copy.deepcopy(base)
            mutate(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                codec.apply_window_changes(original, changes)
        for slot in ({'spell_row': -1}, {'spell_row': True}, {'spell_row': 1 << 31},
                     {'spell_row': 0, 'extra': 1}, {'spell_row': 0, 'name': None},
                     {'spell_row': 0, 'name': '\ud800'}, {'spell_row': 0, 'icon': True},
                     {'spell_row': 0, 'icon': -1}, {'spell_row': 0, 'icon': 1 << 31}):
            changes = copy.deepcopy(base)
            changes['buff_slots'][0] = slot
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                codec.apply_window_changes(original, changes)
        with self.assertRaisesRegex(ValueError, 'ATS_WINDOW_SPELL_TOPOLOGY'):
            codec.apply_window_changes(None, {'buff_slots': [{'spell_row': 0}]})
        with self.assertRaisesRegex(ValueError, 'ATS_WINDOW_BATTLE_TOPOLOGY'):
            codec.apply_window_changes(None, {'battle_slots': [base['battle_slots'][0]]})

    def test_window_magic_whole_array_preserves_readonly_items_and_unknown_slots(self):
        f = codec.field
        unknown = b'\x98\x86\x00\x81\x00'
        item = (unknown + f(1, 0, 2) + f(4, 0, 14) + f(5, 0, 9)
                + f(6, 0, 123) + f(7, 2, b'opaque native name') + unknown)
        unresolved = unknown + f(1, 0, 99) + f(4, 0, 999) + f(7, 2, b'opaque')
        empty = f(1, 0, 1) + f(4, 0, -1)
        buff = f(7, 2, item) + f(7, 2, unresolved) + f(7, 2, empty)
        option = f(1, 2, buff) + unknown
        wrapper = codec.wrap_blob(f(1, 2, f(2, 2, option)), raw=True)
        slots = [{'template': 14, 'name': 'catalog name differs'},
                 {'spell_key': 999, 'spell': None, 'status': 'invalid'}, None]
        self.assertIs(codec.apply_window_changes(wrapper, {'buff_slots': slots}), wrapper)
        changed = [*slots[:2], {'spell_row': 0}]
        saved = codec.apply_window_changes(wrapper, {'buff_slots': changed})
        expected_buff = f(7, 2, item) + f(7, 2, unresolved) + f(7, 2, f(1, 0, 1) + f(4, 0, 0))
        self.assertEqual(codec.unwrap_blob(saved), f(1, 2, f(2, 2, f(1, 2, expected_buff) + unknown)))
        policy = codec.companion_policy(saved, {0: 'heal'})
        self.assertEqual(policy['buff_items'], [14])
        self.assertEqual(policy['maintain_buffs'], ['heal'])
        self.assertEqual(policy['buff_slots'][1]['status'], 'invalid')
        for rejected in ([{'template': 17}, slots[1], None],
                         [None, {'template': 14}, None],
                         [slots[0], slots[1], {'template': 14}],
                         [slots[0], dict(slots[1], spell_key=998), None],
                         [slots[0], None, slots[1]],
                         [slots[0], dict(slots[1], spell='heal'), None],
                         [slots[0], dict(slots[1], status='valid'), None],
                         [dict(template=True), slots[1], None]):
            with self.subTest(rejected=rejected), self.assertRaises(ValueError):
                codec.apply_window_changes(wrapper, {'buff_slots': rejected})

    def test_magic_readonly_slots_cannot_be_deleted_or_replaced(self):
        f = codec.field
        for slot in (f(1, 0, 2) + f(4, 0, 14),
                     f(1, 0, 99) + f(4, 0, 999),
                     f(1, 0, 1) + f(4, 0, -2)):
            payload = f(1, 2, f(2, 2, f(1, 2, f(7, 2, slot)) +
                                  f(2, 2, f(1, 2, slot))))
            wrapper = codec.wrap_blob(payload, raw=True)
            for selected in (None, {'spell_row': 0}):
                for changes in ({'buff_slots': [selected]},
                                {'battle_slots': [{'kind': 'sequence', 'index': 0,
                                                   'slot': selected}]}):
                    with self.subTest(slot=slot, changes=changes), self.assertRaises(ValueError):
                        codec.apply_window_changes(wrapper, changes)

    def test_unknown_spell_marker_preserves_bytes_while_other_slots_change(self):
        f = codec.field
        opaque = b'\x98\x86\x00\x81\x00'
        unknown = opaque + f(1, 0, 1) + f(4, 0, 4) + f(4, 0, 54) + f(7, 2, b'opaque')
        empty = f(1, 0, 1) + f(4, 0, -1)
        buff = f(7, 2, unknown) + opaque + f(7, 2, empty)
        battle = f(1, 2, unknown) + f(1, 2, empty)
        wrapper = codec.wrap_blob(f(1, 2, f(2, 2, f(1, 2, buff) + f(2, 2, battle))), raw=True)
        marker = {'spell_row': 54, 'name': None, 'icon': None, 'status': 'UNKNOWN'}
        changes = {'buff_slots': [marker, {'spell_row': 0}],
                   'battle_slots': [{'kind': 'sequence', 'index': 0, 'slot': marker},
                                    {'kind': 'sequence', 'index': 1, 'slot': {'spell_row': 2}}]}
        saved = codec.apply_window_changes(wrapper, changes)
        expected_buff = f(7, 2, unknown) + opaque + f(7, 2, f(1, 0, 1) + f(4, 0, 0))
        expected_battle = f(1, 2, unknown) + f(1, 2, f(1, 0, 1) + f(4, 0, 2))
        self.assertEqual(codec.unwrap_blob(saved), f(1, 2, f(2, 2, f(1, 2, expected_buff) + f(2, 2, expected_battle))))
        for invalid in (dict(marker, spell_row=55), dict(marker, name='changed'),
                        dict(marker, icon=1), dict(marker, extra=1)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                codec.apply_window_changes(wrapper, {'buff_slots': [invalid, None]})
        with self.assertRaises(ValueError):
            codec.apply_window_changes(wrapper, {'buff_slots': [None, marker]})

    def test_window_captured_noop_returns_original_wrapper(self):
        original = CAPTURED_COMPANION_ATS
        self.assertIs(codec.apply_window_changes(original, {}), original)
        view = codec.decode_options(codec.unwrap_blob(original))
        changes = {key: [({'template': slot[4], 'name': 'catalog display name'}
                          if slot.get(1) == 2 and slot.get(4, 0) > 0
                          else None) for slot in view[key]]
                   for key in ('hp_slots', 'mp_slots', 'function_slots')}
        changes.update(hp_percent=view['hp_percent'], mp_percent=view['mp_percent'])
        self.assertIs(codec.apply_window_changes(original, changes), original)

    def test_window_captured_edit_preserves_every_other_field_and_slot(self):
        original = codec.unwrap_blob(CAPTURED_COMPANION_ATS)
        saved = codec.apply_window_changes(CAPTURED_COMPANION_ATS,
            {'hp_slots': [{'template': 14, 'name': 'catalog display name'},
                          {'template': 17, 'name': '초록 물약'}],
             'hp_percent': 25, 'options': {'scan_tiles': 7, 'pickup_weight': 42}})
        updated = codec.unwrap_blob(saved)

        def only(data, number):
            return next(v for n, w, v, _ in codec._field_chunks(data) if (n, w) == (number, 2))

        before, after = original, updated
        for number in (1, 2):
            # The changed ancestor is the only allowed difference at each level.
            self.assertEqual([raw for n, w, _, raw in codec._field_chunks(before) if (n, w) != (number, 2)],
                             [raw for n, w, _, raw in codec._field_chunks(after) if (n, w) != (number, 2)])
            before, after = only(before, number), only(after, number)
        self.assertEqual([raw for n, w, _, raw in codec._field_chunks(before) if (n, w) not in ((1, 2), (3, 2))],
                         [raw for n, w, _, raw in codec._field_chunks(after) if (n, w) not in ((1, 2), (3, 2))])
        before, after = only(before, 1), only(after, 1)
        # BuffData: every non-HP/non-percent row survives exactly, in encounter order.
        self.assertEqual([r for n, w, _, r in codec._field_chunks(before) if (n, w) not in ((1, 2), (2, 5))],
                         [r for n, w, _, r in codec._field_chunks(after) if (n, w) not in ((1, 2), (2, 5))])
        self.assertEqual(codec._children(before, 1)[0], codec._children(after, 1)[0])
        policy = codec.companion_policy(saved, {})
        self.assertEqual(policy['potion_hp']['templates'], [14, 17])
        self.assertEqual(policy['potion_hp']['threshold'], 0.25)
        self.assertEqual((policy['scan_tiles'], policy['pickup_weight']), (7, 42))
        self.assertEqual(codec._slot(codec._children(after, 1)[1])[7], '초록 물약'.encode())

    def test_window_preserves_duplicate_ancestors_and_slot_unknown_wire(self):
        f = codec.field
        unknown = b'\x98\x86\x00\x81\x00'
        empty = f(1, 0, 2) + f(4, 0, -1) + unknown
        slot = unknown + f(1, 0, 2) + f(4, 0, 5) + unknown
        # Noncanonical last f4=14, with earlier duplicate f4 preserved.
        slot += b'\xa0\x00\x8e\x00' + f(5, 0, 9) + f(6, 0, 99) + f(7, 2, b'old') + unknown
        changed_slot = unknown + f(1, 0, 2) + f(4, 0, 5) + unknown
        changed_slot += f(4, 0, 17) + f(5, 0, 0) + f(6, 0, 0) + f(7, 2, b'new') + unknown
        buff = unknown + f(1, 2, slot) + f(7, 2, slot) + f(1, 2, empty) + unknown
        new_buff = unknown + f(1, 2, changed_slot) + f(7, 2, slot) + f(1, 2, empty) + unknown
        opts = unknown + f(1, 0, 1) + f(7, 0, 8) + unknown + f(1, 0, 4)
        new_opts = unknown + f(1, 0, 1) + f(7, 0, 8) + unknown + f(1, 0, 7)
        option = unknown + f(1, 2, buff) + f(2, 2, slot) + f(3, 2, opts) + f(1, 2, buff)
        new_option = unknown + f(1, 2, new_buff) + f(2, 2, slot) + f(3, 2, new_opts) + f(1, 2, buff)
        section = unknown + f(2, 2, option) + f(2, 2, option) + unknown
        new_section = unknown + f(2, 2, new_option) + f(2, 2, option) + unknown
        prefix = unknown + f(1, 2, unknown) + unknown
        suffix = f(1, 2, section) + unknown
        payload = prefix + f(1, 2, section) + suffix
        expected = prefix + f(1, 2, new_section) + suffix
        wrapper = codec.wrap_blob(payload, raw=True)
        saved = codec.apply_window_changes(wrapper, {
            'hp_slots': [{'template': 17, 'name': 'new'}, None], 'options': {'scan_tiles': 7}})
        self.assertEqual(codec.unwrap_blob(saved), expected)

    def test_window_new_tree_and_clear_keep_policy_and_identity_contract(self):
        empty = codec.apply_window_changes(None, {})
        self.assertEqual(codec.unwrap_blob(empty), codec.field(1, 2, codec.field(2, 2, b'')))
        self.assertEqual(codec.companion_policy(empty, {})['status'], 'empty')
        saved = codec.apply_window_changes(None, {
            'hp_slots': [None, {'template': 14}], 'mp_slots': [None, None],
            'function_slots': [None] * 6, 'hp_percent': 80,
            'options': {'scan_tiles': 4, 'pickup_weight': -1}})
        policy = codec.companion_policy(saved, {})
        self.assertEqual((policy['status'], policy['potion_hp']['templates']), ('valid', [14]))
        self.assertEqual(policy['pickup_weight'], -1)
        self.assertEqual(policy['potion_hp']['slots'][0]['status'], 'empty')
        raw = policy['potion_hp']['slots'][1]['raw']
        self.assertEqual((raw[5], raw[6]), (0, 0))
        cleared = codec.apply_window_changes(saved, {'hp_slots': [None, None]})
        self.assertEqual(codec.companion_policy(cleared, {})['potion_hp']['templates'], [])
        self.assertIs(codec.apply_window_changes(cleared, {'hp_slots': [None, None]}), cleared)

    def test_window_rejects_invalid_inputs_and_readonly_edits(self):
        bad = [None, [], {'buff_slots': []}, {'sequence': []}, {'battle_slots': []},
               {'member_id': 2}, {'edit_epoch': 1}, {'hp_slots': []},
               {'mp_slots': [None, None, None]}, {'function_slots': [None] * 5},
               {'hp_slots': [{'template': True}, None]},
               {'hp_slots': [{'template': 0}, None]},
               {'hp_slots': [{'template': 1 << 31}, None]},
               {'hp_slots': [{'template': 14, 'extra': 1}, None]},
               {'hp_slots': [{'template': 14, 'name': None}, None]},
               {'hp_percent': True}, {'hp_percent': float('nan')},
               {'hp_percent': float('inf')}, {'hp_percent': -1}, {'mp_percent': 101},
               {'hp_percent': 10 ** 1000}, {'options': []}, {'options': {'hunt_steps': 0}},
               {'options': {'idle_seconds': 0}}, {'options': {'scan_tiles': 0}},
               {'options': {'scan_tiles': True}}, {'options': {'pickup_weight': 1 << 31}}]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                codec.apply_window_changes(CAPTURED_COMPANION_ATS, changes)
        with self.assertRaises(ValueError):
            codec.apply_window_changes(b'broken', {})

    def test_first_member_config_clears_only_captured_item_links(self):
        original = codec.fields(codec.unwrap_blob(CAPTURED_OWNER_CONFIG))
        cloned = codec.companion_character_config(CAPTURED_OWNER_CONFIG)
        copied = codec.fields(codec.unwrap_blob(cloned))
        self.assertEqual([r for r in copied if r[:2] != (2, 2)],
                         [r for r in original if r[:2] != (2, 2)])
        before = codec.fields(next(v for n, w, v in original if (n, w) == (2, 2)))
        after = codec.fields(next(v for n, w, v in copied if (n, w) == (2, 2)))
        self.assertEqual(before[0], (1, 2, b'1.0.0'))
        self.assertEqual(after[0], before[0])
        self.assertEqual(len(after), len(before))
        self.assertEqual([codec._slot(v)[3] for n, w, v in before[1:4]], [80, 77, 79])
        empty = before[4][2]  # captured native empty slot
        self.assertTrue(all(v == empty for n, w, v in after[1:]))
        self.assertEqual(codec.companion_character_config(cloned), cloned)

    def test_first_member_config_preserves_nonitem_unknown_repeated_wire_bytes(self):
        f = codec.field
        unknown = b'\x98\x86\x00\x81\x00'  # noncanonical tag 99/value 1
        spell = f(1, 0, 1) + f(3, 0, 321) + f(4, 0, 3) + unknown
        empty = f(1, 0, 0) + f(3, 0, 0) + f(4, 0, -1)
        item = f(1, 0, 2) + f(3, 0, 80) + f(4, 0, 14) + f(7, 2, b'item')
        prefix = f(1, 2, b'1.0.0') + unknown + unknown + f(2, 2, spell)
        suffix = f(2, 2, empty) + unknown
        body = unknown + f(2, 2, prefix + f(2, 2, item) + suffix) + f(7, 2, item) + unknown
        expected = unknown + f(2, 2, prefix + f(2, 2, empty) + suffix) + f(7, 2, item) + unknown
        cloned = codec.companion_character_config(codec.wrap_blob(body, raw=True))
        self.assertEqual(codec.unwrap_blob(cloned), expected)

    def test_captured_member_edit_recovers_potion_with_native_empty_rows(self):
        policy = codec.companion_policy(CAPTURED_COMPANION_ATS, {})
        self.assertEqual(policy['status'], 'valid')
        self.assertEqual(policy['issues'], [])
        self.assertEqual(policy['potion_hp']['templates'], [14])
        self.assertEqual(policy['potion_hp']['threshold'], 0.5)
        self.assertEqual(policy['potion_mp']['templates'], [])
        self.assertEqual(policy['function_items'], [17])
        self.assertEqual(policy['potion_hp']['slots'][1]['status'], 'empty')
        self.assertTrue(all(row['status'] == 'empty' for row in policy['potion_mp']['slots']))
        self.assertTrue(all(row['status'] == 'empty' for row in policy['function_slots'][1:]))
        self.assertEqual(len(policy['battle_slots']), 16)
        self.assertTrue(all(row['status'] == 'empty' and row['conditions'] == []
                            and 'spell' not in row for row in policy['battle_slots']))
        self.assertEqual(policy['attack_spells'], [])
        self.assertEqual(policy['heal_spells'], [])

    def test_empty_sentinels_ignore_ancillary_fields_but_not_unknown_selections(self):
        def policy_for(slot):
            battle = codec.field(1, 2, slot)
            payload = codec.field(1, 2, codec.field(2, 2, codec.field(2, 2, battle)))
            return codec.companion_policy(codec.wrap_blob(payload), {0: 'heal'})

        for kind in (1, 2):
            slot = codec.field(1, 0, kind) + codec.field(4, 0, -1)
            slot += codec.field(99, 2, b'unknown ancillary field')
            with self.subTest(kind=kind):
                policy = policy_for(slot)
                self.assertEqual((policy['status'], policy['issues']), ('empty', []))
                self.assertNotIn('spell', policy['battle_slots'][0])
                self.assertNotIn('template', policy['battle_slots'][0])
        for kind, key in ((1, -2), (1, 999), (2, 14), (99, -1)):
            with self.subTest(kind=kind, key=key):
                policy = policy_for(codec.field(1, 0, kind) + codec.field(4, 0, key))
                self.assertEqual(policy['status'], 'invalid')
                self.assertEqual(policy['issues'], ['ATS_SLOT_UNKNOWN'])

    def test_empty_condition_row_does_not_gate_active_spell_zero(self):
        spell = codec.field(1, 0, 1) + codec.field(4, 0, 0)
        empty = codec.field(1, 0, 1) + codec.field(4, 0, -1)
        condition = codec.field(1, 0, 0) + codec.field(2, 0, 0) + codec.field(3, 2, empty)
        battle = codec.field(1, 2, spell) + codec.field(2, 2, condition)
        payload = codec.field(1, 2, codec.field(2, 2, codec.field(2, 2, battle)))
        policy = codec.companion_policy(codec.wrap_blob(payload), {0: 'heal'})
        self.assertEqual((policy['status'], policy['issues']), ('valid', []))
        self.assertEqual(policy['heal_spells'], ['heal'])
        self.assertEqual(policy['battle_slots'][0]['conditions'], [])
        self.assertEqual(policy['battle_slots'][1]['status'], 'empty')
        self.assertNotIn('spell', policy['battle_slots'][1])
        self.assertFalse(codec.condition_matches(0, 0, None))


if __name__ == '__main__':
    unittest.main()
