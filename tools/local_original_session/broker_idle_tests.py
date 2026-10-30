"""Bounded failure-time metadata; no listeners, game, or native owner."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import uuid

from tools.local_original_session import broker


class FailureTimingTests(unittest.TestCase):
    def test_first_failure_time_survives_cleanup_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            service = broker.PersistentBroker(
                sockets={12000: object(), 14030: object()}, retained_owner=object(),
                owner_handle=object(), owner_job=object(), owner_guard=lambda _: True,
                owner_liveness_guard=lambda: True, source_guard=lambda: None,
                conversation_factory=lambda *_: None, expected_uuid=str(uuid.uuid4()),
                store_path=Path(directory) / 'characters.json')
            self.assertIsNone(service.report()['failure_monotonic_ns'])
            service.last_received_frame = dict(opcode=broker.QUIT_REQUEST, wire_length=10,
                endpoint_port=14030, connection_id=4, received_monotonic_ns=100)
            with mock.patch.object(broker.time, 'monotonic_ns', side_effect=(150, 200)) as clock:
                service._fail('ConnectionResetError')
                service._fail('CLEANUP_FAILURE')
            result = service.report()
            self.assertEqual(result['failure_code'], 'ConnectionResetError')
            self.assertEqual(result['failure_monotonic_ns'], 150)
            self.assertEqual(result['failure_monotonic_ns'] -
                             result['last_received_frame']['received_monotonic_ns'], 50)
            clock.assert_called_once()
            self.assertFalse(result['connections'])


if __name__ == '__main__':
    unittest.main()
