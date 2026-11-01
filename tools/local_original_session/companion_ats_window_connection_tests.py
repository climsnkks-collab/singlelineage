"""Focused routing and request-file checks for the dedicated ATS window."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import companion_bridge_host as host
from tools.local_original_session import world_feature_companion as companion
from tools.local_original_session import world_feature_companion_ats as ats


class CompanionATSWindowConnectionTests(unittest.TestCase):
    def test_new_signals_bypass_companion_item_handler(self):
        ctx = SimpleNamespace(_companion_enabled=True)
        for operation in ('ats-window-open', 'ats-window-save'):
            with self.subTest(operation=operation):
                signal = SimpleNamespace(operation=operation, actor_uid=900)
                self.assertIsNone(companion._companion_ui_signal(ctx, object(), 5, signal))

    def test_host_request_has_exact_window_file_key(self):
        identity = dict(pid=123, birth=456, candidate_sha256='a' * 64)
        common = dict(member_id=9, ats_epoch=12345)
        for command, key, basename in (
                ('ats-window-view', 'view_file', 'companion-ats-view-12345-999.json'),
                ('ats-window-result', 'result_file', 'companion-ats-result-12345-1000.json')):
            with self.subTest(command=command):
                request = json.loads(host.request_text(identity, 7, dict(
                    command=command, **common, **{key: basename})))
                self.assertEqual((request['schema'], request['command'], request['member_id'],
                                  request['ats_epoch'], request[key]),
                                 ('own-companion-request-v1', command, 9, 12345, basename))
                self.assertEqual(list(request)[-1], key)
                self.assertNotIn('result_file' if key == 'view_file' else 'view_file', request)

    def test_host_rejects_missing_or_escaping_window_file(self):
        identity = dict(pid=123, birth=456, candidate_sha256='a' * 64)
        for command, key in (('ats-window-view', 'view_file'),
                             ('ats-window-result', 'result_file')):
            for value in (None, '../companion-ats-view-1-2.json', 'companion-ats-view-1-2.json'
                          if key == 'result_file' else 'companion-ats-result-1-2.json'):
                with self.subTest(command=command, value=value), self.assertRaises(ValueError):
                    host.request_text(identity, 7, dict(command=command, **{key: value}))

    def test_open_refusal_result_accepts_zero_epoch_only_for_result(self):
        identity = dict(pid=123, birth=456, candidate_sha256='a' * 64)
        request = json.loads(host.request_text(identity, 7, dict(command='ats-window-result',
            member_id=9, ats_epoch=0, result_file='companion-ats-result-0-123456.json')))
        self.assertEqual((request['ats_epoch'], request['result_file']),
                         (0, 'companion-ats-result-0-123456.json'))
        with self.assertRaisesRegex(ValueError, 'COMPANION_HOST_VIEW_FILE'):
            host.request_text(identity, 8, dict(command='ats-window-view',
                member_id=9, ats_epoch=0, view_file='companion-ats-view-0-123456.json'))
        with self.assertRaisesRegex(ValueError, 'COMPANION_HOST_RESULT_FILE'):
            host.request_text(identity, 9, dict(command='ats-window-result',
                member_id=9, ats_epoch=0, result_file='companion-ats-result-00-123456.json'))

    def test_failed_open_publishes_serializable_zero_epoch_result(self):
        identity = dict(pid=123, birth=456, candidate_sha256='a' * 64)
        posted, notices = [], []
        def publish(name, uid, kind, payload):
            posted.append(json.loads(host.request_text(identity, 7, payload)))
        ctx = SimpleNamespace(run_sync_hooks=publish,
            world=SimpleNamespace(_queue=lambda uid, frame: notices.append(frame),
                                  _announce=lambda: None))
        signal = SimpleNamespace(operation='ats-window-open', args=('9',), actor_uid=900)
        with patch.object(ats, '_ats_window_session', side_effect=ValueError('CURRENT_ACTOR_REQUIRED')), \
                patch.object(ats, '_ats_window_json', return_value='companion-ats-result-0-123456.json'):
            result = ats._ats_window_signal(ctx, object(), 5, signal, dict(event_seq=12))
        self.assertEqual((result['status'], result['edit_epoch'], result.get('delivery_error')),
                         ('REFUSED', 0, None))
        self.assertEqual((posted[0]['command'], posted[0]['ats_epoch'], posted[0]['result_file']),
                         ('ats-window-result', 0, 'companion-ats-result-0-123456.json'))
        self.assertEqual(len(notices), 1)

    def test_ats_payload_files_do_not_advance_host_sequence(self):
        context = dict(pid=123, birth=456, candidate_sha256='a' * 64)
        files = [Path('manual-move-result-7.json'),
                 Path('companion-ats-view-12345-999999999999.json'),
                 Path('companion-ats-result-12345-999999999998.json'),
                 Path('companion-ats-delta-99.json')]
        with patch.object(Path, 'read_text', return_value=json.dumps(context)), \
                patch.object(Path, 'iterdir', return_value=files):
            directory = host.DirectoryHost('unused', poster=lambda *args: True)
        self.assertEqual(directory.sequence, 7)


if __name__ == '__main__':
    unittest.main()
