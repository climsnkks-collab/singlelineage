"""Development tests for the independent companion ATS JSON window.

No game, listener, official login, or native UI is started by this module.
"""
import asyncio
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import ats_config_codec as codec
from tools.local_original_session import ats_config_codec_tests as samples
from tools.local_original_session import companion_signals as signals
from tools.local_original_session import world_feature_companion_ats as ats


class CompanionATSWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.writer, self.game = object(), object()
        self.owner_ref, self.actor_ref = NS(uid=5, generation=1), NS(uid=900, generation=7)
        self.actor = NS(owner_ref=self.owner_ref, ref=self.actor_ref, character_id=9,
                        record=NS(owner_character_id=5))
        self.queued, self.published = [], []
        self.sidecar = self.directory / 'settings-sidecar.bin'
        self.sidecar.write_bytes(b'owner-account-sidecar-test-fixture')
        owner = dict(self_config=samples.CAPTURED_OWNER_CONFIG.hex(),
                     self_ats=codec.wrap_blob(codec.build_ats(hp_percent=7)).hex(), untouched='owner')
        self.ctx = NS(_ats_enabled=True, _ats_scope={}, _ats_edit={}, _ats_events=[],
            _ats_window_edits={}, _ats_window_epoch=1000, _ats_policies={},
            _ats_path=self.directory / 'ats-scopes.json',
            _ats_store=dict(schema=1, characters={'5': owner, '9': {
                'companion_ats': samples.CAPTURED_COMPANION_ATS.hex(),
                'self_ats': codec.wrap_blob(codec.build_ats(hp_percent=12)).hex(), 'untouched': 'member'}}),
            _world_bound=lambda writer: writer is self.writer,
            _world_ready=lambda writer, game: True,
            _world_pcs={id(self.writer): (self.writer, 5)},
            _companion_bridge_host=NS(directory=self.directory),
            _companion_spells={'spells': []},
            realm=NS(registry=NS(resolve=lambda writer: self.game),
                     settings=NS(save=lambda value: self.fail('sidecar write'))),
            world=NS(companions=NS(active={9: self.actor}), pcs={},
                entities={5: NS(ref=self.owner_ref), 900: NS(ref=self.actor_ref)},
                companion_looks={9: dict(name='SoloMage')},
                _queue=lambda uid, frame: self.queued.append((uid, frame)), _announce=lambda: None),
            run_sync_hooks=lambda name, *args: self.published.append((name, args)))
        ats._ats_save_store(self.ctx)
        self.original_owner = copy.deepcopy(owner)

    def signal(self, operation, args, actor=900):
        body = signals.encode_signal(operation, actor, tuple(str(v) for v in args))
        return signals.decode_signal(body)

    def open(self):
        result = ats._ats_ui_signal(self.ctx, self.writer, 5,
            self.signal('ats-window-open', (9,)), dict(event_seq=17))
        self.assertEqual(result['status'], 'SUPPLIED', result)
        self.epoch = result['edit_epoch']
        return json.loads((self.directory / result['view_file']).read_text(encoding='utf-8'))

    def save(self, changes, *, epoch=None, file='companion-ats-delta-18.json', metadata=None):
        epoch = self.epoch if epoch is None else epoch
        delta = dict(member_id=9, edit_epoch=epoch, **changes)
        if metadata:
            delta.update(metadata)
        (self.directory / file).write_text(json.dumps(delta), encoding='utf-8')
        return ats._ats_ui_signal(self.ctx, self.writer, 5,
            self.signal('ats-window-save', (9, epoch, file)), dict(event_seq=18))

    def result_json(self):
        request = self.published[-1][1][2]
        self.assertEqual(request['command'], 'ats-window-result')
        return json.loads((self.directory / request['result_file']).read_text(encoding='utf-8'))

    def test_view_is_saved_companion_only_and_no_native_model_frames(self):
        view = self.open()
        parsed = codec.decode_options(codec.unwrap_blob(samples.CAPTURED_COMPANION_ATS))
        self.assertEqual(view['schema'], 'companion-ats-view-v1')
        self.assertEqual((view['member_id'], view['name']), (9, 'SoloMage'))
        self.assertEqual(view['hp_percent'], parsed['hp_percent'])
        self.assertEqual([len(view[key]) for key in ('hp_slots', 'mp_slots', 'function_slots')], [2, 2, 6])
        self.assertEqual(set(view['options']) - {'scan_tiles', 'pickup_weight'}, set())
        self.assertIn('battle_slots', view)
        self.assertEqual(self.queued, [])  # no 4ED7/4E60/4ED6 traffic
        self.assertEqual(self.ctx._ats_edit, {})
        self.assertEqual(self.ctx._ats_store['characters']['5'], self.original_owner)
        self.assertEqual(self.published[-1][1][1], 'ats-window-view')
        self.assertEqual(self.published[-1][1][2]['ats_epoch'], self.epoch)

    def test_missing_companion_never_falls_back_to_self_or_owner(self):
        self.ctx._ats_store['characters']['9'].pop('companion_ats')
        view = self.open()
        self.assertEqual(view['hp_slots'], [None, None])
        self.assertEqual(view['hp_percent'], None)
        self.assertEqual(view['options'], {})

    def test_partial_save_keeps_capture_fields_and_owner_and_updates_ai_policy(self):
        view = self.open()
        before = codec.decode_options(codec.unwrap_blob(samples.CAPTURED_COMPANION_ATS))
        old_member = copy.deepcopy(self.ctx._ats_store['characters']['9'])
        ats._ats_policy(self.ctx, None, 9)
        result = self.save(dict(hp_slots=[None, dict(template=14, name='빨간 물약')], hp_percent=61,
                                options=dict(scan_tiles=6, pickup_weight=75)))
        self.assertEqual(result['status'], 'OK', result)
        self.assertTrue(result['saved'])
        self.assertNotIn(9, self.ctx._ats_policies)
        saved = json.loads(self.ctx._ats_path.read_text(encoding='utf-8'))['characters']
        self.assertEqual(saved['5'], self.original_owner)
        self.assertEqual({k: v for k, v in saved['9'].items() if k != 'companion_ats'},
                         {k: v for k, v in old_member.items() if k != 'companion_ats'})
        updated = bytes.fromhex(saved['9']['companion_ats'])
        after = codec.decode_options(codec.unwrap_blob(updated))
        for key in ('mp_slots', 'mp_percent', 'function_slots', 'buff_slots', 'sequence', 'conditional', 'battle_slots'):
            self.assertEqual(after[key], before[key], key)
        # Unknown top-level chunk and opaque character tree in the real capture survive exactly.
        chunks = lambda blob: tuple(codec._field_chunks(codec.unwrap_blob(blob)))
        self.assertEqual([(n,w,v,raw) for n,w,v,raw in chunks(updated) if n != 1],
                         [(n,w,v,raw) for n,w,v,raw in chunks(samples.CAPTURED_COMPANION_ATS) if n != 1])
        def readonly_option_chunks(wrapper):
            section = codec._children(codec.unwrap_blob(wrapper), 1)[0]
            option = codec._children(section, 2)[0]
            return [raw for n,w,v,raw in codec._field_chunks(option) if n not in (1, 3)]
        self.assertEqual(readonly_option_chunks(updated), readonly_option_chunks(samples.CAPTURED_COMPANION_ATS))
        self.assertEqual(self.sidecar.read_bytes(), b'owner-account-sidecar-test-fixture')
        policy = ats._ats_policy(self.ctx, None, 9)
        self.assertEqual(policy['potion_hp']['templates'], [14])
        self.assertEqual(policy['potion_hp']['threshold'], .61)
        self.assertEqual((policy['scan_tiles'], policy['pickup_weight']), (6, 75))
        payload = self.result_json()
        self.assertEqual(payload['status'], 'OK')
        self.assertEqual(payload['view']['hp_percent'], 61)
        self.assertIn('동료 설정이 저장되었습니다.'.encode(), self.queued[-1][1])
        self.assertEqual(self.open()['hp_slots'], payload['view']['hp_slots'])

    def test_old_epoch_rejected_after_new_open_without_mutating_save(self):
        self.open()
        epoch = self.epoch
        self.open()
        original = self.ctx._ats_path.read_bytes()
        result = self.save(dict(hp_percent=1), epoch=epoch)
        self.assertEqual(result['reason'], 'ATS_WINDOW_EDIT_EPOCH_MISMATCH')
        self.assertEqual(self.ctx._ats_path.read_bytes(), original)

    def test_session_owner_and_actor_changes_reject(self):
        for change in ('session', 'owner', 'actor', 'selected', 'member'):
            with self.subTest(change=change):
                self.setUp()
                self.open()
                if change == 'session':
                    self.game = object()
                elif change == 'owner':
                    self.actor.record.owner_character_id = 6
                elif change == 'actor':
                    self.actor.ref = NS(uid=900, generation=8)
                    self.ctx.world.entities[900].ref = self.actor.ref
                elif change == 'selected':
                    self.ctx.world.pcs[9] = object()
                else:
                    self.actor.character_id = 10
                result = self.save(dict(hp_percent=2))
                self.assertEqual(result['status'], 'REFUSED', result)
                self.assertEqual(json.loads(self.ctx._ats_path.read_text())['characters']['5'], self.original_owner)

    def test_readonly_and_identity_mismatch_rejected(self):
        self.open()
        for changes, metadata in ((dict(buff_slots=[]), None), (dict(battle_slots=[]), None),
                                  (dict(options=dict(hunt_steps=1)), None),
                                  (dict(hp_percent=20), dict(member_id=5)),
                                  (dict(hp_percent=20), dict(edit_epoch=True))):
            with self.subTest(changes=changes, metadata=metadata):
                original = self.ctx._ats_path.read_bytes()
                result = self.save(changes, metadata=metadata)
                self.assertEqual(result['status'], 'REFUSED', result)
                self.assertEqual(self.ctx._ats_path.read_bytes(), original)

    def test_failed_durable_save_restores_memory_and_cached_policy(self):
        self.open()
        old = copy.deepcopy(self.ctx._ats_store)
        original = self.ctx._ats_path.read_bytes()
        old_policy = ats._ats_policy(self.ctx, None, 9)
        with patch.object(ats, '_ats_save_store', side_effect=OSError('unit injected write failure')):
            result = self.save(dict(hp_percent=10))
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(self.ctx._ats_store, old)
        self.assertIs(self.ctx._ats_policies[9], old_policy)
        self.assertEqual(self.ctx._ats_path.read_bytes(), original)

    def test_result_delivery_failure_does_not_relabel_committed_save(self):
        self.open()
        self.ctx.run_sync_hooks = lambda *args: (_ for _ in ()).throw(OSError('unit post failure'))
        result = self.save(dict(hp_percent=44))
        self.assertEqual(result['status'], 'OK')
        self.assertTrue(result['saved'])
        self.assertIn('delivery_error', result)
        self.assertEqual(codec.companion_policy(bytes.fromhex(json.loads(
            self.ctx._ats_path.read_text())['characters']['9']['companion_ats']), {})['potion_hp']['threshold'], .44)

    def test_delta_basename_no_traversal_and_resolved_path_stays_inside_directory(self):
        self.open()
        for name in ('../companion-ats-delta-1.json', 'C:\\outside.json', 'arbitrary.json'):
            with self.assertRaises(signals.SignalError):
                self.signal('ats-window-save', (9, self.epoch, name))
        # The strict resolved parent check also handles filesystem redirections.
        with patch.object(Path, 'resolve', autospec=True) as resolve:
            resolve.side_effect = (self.directory, self.directory.parent / 'outside.json')
            result = self.save(dict(hp_percent=1))
        self.assertEqual(result['reason'], 'ATS_WINDOW_DELTA_DIRECTORY_REQUIRED')

    def test_leave_discards_window_epoch_and_no_shared_spell_restore(self):
        self.open()
        asyncio.run(ats._ats_after_leave(self.ctx, self.writer))
        self.assertEqual(self.ctx._ats_window_edits, {})
        result = self.save(dict(hp_percent=1))
        self.assertEqual(result['reason'], 'ATS_WINDOW_EDIT_EPOCH_MISMATCH')
        self.assertEqual(self.ctx._ats_store['characters']['5'], self.original_owner)

    def test_disabled_feature_refusal_gets_json_and_notice(self):
        self.ctx._ats_enabled = False
        signal = self.signal('ats-window-open', (9,))
        self.assertIsNone(ats._ats_ui_signal(self.ctx, self.writer, 5, signal, {}))
        result = dict(status='UNHANDLED')
        ats._ats_ui_refused(self.ctx, self.writer, 5, signal, {}, result)
        self.assertTrue(result['feedback_sent'])
        self.assertEqual(self.result_json()['status'], 'UNHANDLED')


if __name__ == '__main__':
    unittest.main()
