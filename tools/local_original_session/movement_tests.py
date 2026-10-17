"""Bounded movement/storage fixtures only; no sockets, game, native or REA."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.local_original_session import movement as m


def payload(position, direction):
    return m.pb.encode_message([
        m.pb.encode_uint32(1, position.packed),
        m.pb.encode_varint(2 << 3) + m.pb.encode_varint(direction & 0xffffffffffffffff),
    ])


def correction_words(wire):
    assert int.from_bytes(wire[:2], 'little') == len(wire)
    assert int.from_bytes(wire[2:4], 'little') == m.CORRECTION_OPCODE
    assert wire[-2:] == b'\0\0'
    with m.pb.parse_message(wire[4:-2], schema={1: 0, 2: 0}) as parsed:
        assert all(len(parsed.occurrences(n)) == 1 for n in (1, 2))
        return tuple(parsed.occurrences(n)[0].value for n in (1, 2))


class MovementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.profile = Path(self.folder.name) / 'characters.json'
        self.original_profile = b'{"preserved_character_profile":true}\n'
        self.profile.write_bytes(self.original_profile)
        self.selected = m.Position(1, 'SoloKnight', 0, 32571, 32951)
        self.connection = object()
        self.allowed = True
        self.edge = True
        self.edge_calls = []
        self.store = m.PositionStore(self.profile)

        async def owner(connection, selected):
            self.assertIs(connection, self.connection)
            self.assertEqual((selected.uid, selected.name, selected.map_id), (1, 'SoloKnight', 0))
            return self.allowed

        async def edge(uid, map_id, start, direction, destination):
            self.edge_calls.append((uid, map_id, start, direction, destination))
            await asyncio.sleep(0)
            return self.edge

        self.owner_callback, self.edge_callback = owner, edge
        self.service = m.MovementService(self.selected, connection=self.connection,
            owner_guard=owner, edge_passability=edge, store=self.store)

    async def asyncTearDown(self):
        self.assertEqual(self.profile.read_bytes(), self.original_profile)
        self.assertFalse(list(Path(self.folder.name).glob('.positions-*.tmp')))
        self.folder.cleanup()

    async def test_request_and_prepared_counters_distinguish_commit_refusal_and_correction(self):
        first = await self.service.handle_CS4E2B(payload(self.selected, 2))
        self.assertTrue(first.accepted)
        self.assertEqual((self.service.requests_received, self.service.corrections_prepared), (1, 0))
        duplicate = await self.service.handle_CS4E2B(payload(self.selected, 2))
        self.assertEqual(duplicate.reason, 'STALE_START')
        self.assertEqual((self.service.requests_received, self.service.corrections_prepared), (2, 1))
        malformed = await self.service.handle_CS4E2B(object())
        self.assertEqual(malformed.reason, 'MALFORMED_MOVE_PAYLOAD')
        self.allowed = False
        refused = await self.service.handle_CS4E2B(object())
        self.assertEqual(refused.reason, 'OWNER_REFUSED')
        self.service.fatal = True
        fatal = await self.service.handle_CS4E2B(object())
        self.assertTrue(fatal.fatal)
        self.assertEqual((self.service.requests_received, self.service.corrections_prepared,
                          self.service.committed), (5, 1, 1))

    async def test_prepared_counter_requires_completed_frame_and_counters_saturate_without_policy_change(self):
        with mock.patch.object(m, 'correction_frame', side_effect=ValueError('FIXTURE_FRAME_PREPARATION_FAILED')):
            with self.assertRaisesRegex(ValueError, 'FIXTURE_FRAME_PREPARATION_FAILED'):
                await self.service.handle_CS4E2B(payload(self.selected, 8))
        self.assertEqual((self.service.requests_received, self.service.corrections_prepared), (1, 0))
        self.service.requests_received = self.service.corrections_prepared = m.MAX_COUNTER - 1
        for _ in range(2):
            result = await self.service.handle_CS4E2B(payload(self.selected, 8))
            self.assertEqual(result.reason, 'DIRECTION_0_TO_7_REQUIRED')
            self.assertEqual(len(result.replies), 1)
        self.assertEqual((self.service.requests_received, self.service.corrections_prepared),
                         (m.MAX_COUNTER, m.MAX_COUNTER))
        accepted = await self.service.handle_CS4E2B(payload(self.selected, 2))
        self.assertTrue(accepted.accepted)
        self.assertEqual((self.service.requests_received, self.service.corrections_prepared),
                         (m.MAX_COUNTER, m.MAX_COUNTER))

    async def test_once_commit_serializes_same_start_without_echo(self):
        wire = payload(self.selected, 2)
        first, duplicate = await asyncio.gather(self.service.handle_CS4E2B(wire),
                                               self.service.handle_CS4E2B(wire))
        self.assertTrue(first.accepted)
        self.assertEqual(first.replies, ())
        self.assertEqual(duplicate.reason, 'STALE_START')
        self.assertEqual(correction_words(duplicate.replies[0]), (32572, 32951))
        self.assertEqual(self.service.committed, 1)
        self.assertEqual(len(self.edge_calls), 1)
        self.assertEqual(self.store.restore(self.selected), self.service.snapshot())

    async def test_stale_invalid_direction_and_boundary_keep_current(self):
        stale = m.Position(1, 'SoloKnight', 0, 32570, 32951)
        result = await self.service.handle_CS4E2B(payload(stale, 2))
        self.assertEqual(result.reason, 'STALE_START')
        self.assertEqual(correction_words(result.replies[0]), (32571, 32951))
        bad_direction = await self.service.handle_CS4E2B(payload(self.selected, 8))
        self.assertEqual(bad_direction.reason, 'DIRECTION_0_TO_7_REQUIRED')
        self.assertFalse(bad_direction.accepted)
        boundary = m.MovementService(m.Position(2, 'Boundary', 0, 0, 0),
            connection=self.connection, owner_guard=lambda *_: True,
            edge_passability=self.edge_callback, store=self.store)
        result = await boundary.handle_CS4E2B(payload(boundary.snapshot(), 0))
        self.assertEqual(result.reason, 'GRID_BOUNDARY')
        self.assertEqual(correction_words(result.replies[0]), (0, 0))
        self.assertFalse(self.store.path.exists())
        self.assertEqual(self.edge_calls, [])

    async def test_blocked_edge_corrects_without_saving(self):
        self.edge = False
        result = await self.service.handle_CS4E2B(payload(self.selected, 2))
        self.assertEqual(result.reason, 'EDGE_BLOCKED')
        self.assertFalse(result.accepted)
        self.assertFalse(result.unknown)
        self.assertEqual(correction_words(result.replies[0]), (32571, 32951))
        self.assertEqual(self.service.snapshot(), self.selected)
        self.assertFalse(self.store.path.exists())

    async def test_unknown_edge_and_lost_owner_fail_closed(self):
        self.edge = None
        result = await self.service.handle_CS4E2B(payload(self.selected, 2))
        self.assertEqual(result.reason, 'EDGE_UNKNOWN')
        self.assertTrue(result.unknown)
        self.assertEqual(correction_words(result.replies[0]), (32571, 32951))
        self.assertFalse(self.store.path.exists())
        # No body parsing or reflection when the selected owner is unavailable.
        self.allowed = None
        result = await self.service.handle_CS4E2B(object())
        self.assertEqual(result.reason, 'OWNER_UNKNOWN')
        self.assertEqual(result.replies, ())
        self.assertEqual(len(self.edge_calls), 1)
        self.allowed = True
        async def revoked_during_edge(*_):
            self.allowed = False
            return True
        self.service._edge_passability = revoked_during_edge
        result = await self.service.handle_CS4E2B(payload(self.selected, 2))
        self.assertEqual(result.reason, 'OWNER_REFUSED')
        self.assertEqual(result.replies, ())
        self.assertEqual(self.service.snapshot(), self.selected)

    async def test_loopback_walk_allows_identical_body_after_return(self):
        original_body = payload(self.selected, 2)
        first = await self.service.handle_CS4E2B(original_body)
        returned = await self.service.handle_CS4E2B(payload(first.position, 6))
        repeated = await self.service.handle_CS4E2B(original_body)
        self.assertTrue(first.accepted and returned.accepted and repeated.accepted)
        self.assertEqual(returned.position, self.selected)
        self.assertEqual(repeated.position.word0, self.selected.word0 + 1)
        self.assertEqual(self.service.committed, 3)
        self.assertTrue(all(not result.replies for result in (first, returned, repeated)))

    async def test_save_failure_never_promotes_authority_or_original_file(self):
        first = await self.service.handle_CS4E2B(payload(self.selected, 2))
        stored = self.store.path.read_bytes()
        # A real fsync error prevents replacement; memory stays at the old step.
        with mock.patch.object(m.os, 'fsync', side_effect=OSError('fixture fsync failure')):
            result = await self.service.handle_CS4E2B(payload(first.position, 2))
        self.assertEqual(result.reason, 'POSITION_SAVE_FAILED')
        self.assertTrue(result.unknown)
        self.assertEqual(result.replies, ())
        self.assertEqual(self.service.snapshot(), first.position)
        self.assertEqual(self.service.committed, 1)
        self.assertEqual(self.store.path.read_bytes(), stored)
        self.assertTrue(result.fatal and self.service.fatal)
        after_failure = await self.service.handle_CS4E2B(payload(first.position, 2))
        self.assertEqual(after_failure.reason, 'MOVEMENT_FATAL_UNKNOWN')
        self.assertTrue(after_failure.fatal)

    async def test_reload_schema_uid_limit_and_corrupt_store_not_overwritten(self):
        result = await self.service.handle_CS4E2B(payload(self.selected, 3))
        restored = m.MovementService(self.selected, connection=self.connection,
            owner_guard=self.owner_callback, edge_passability=self.edge_callback,
            store=m.PositionStore(self.profile))
        self.assertEqual(restored.snapshot(), result.position)
        data = json.loads(self.store.path.read_bytes())
        self.assertEqual(data, dict(version=1, positions=[dict(uid=1, map_id=0,
                                                             grid=[32572, 32952])]))
        for uid in (2, 3):
            selected = m.Position(uid, 'Character' + str(uid), 0, 10, 10)
            self.store.commit(selected, selected)
        with self.assertRaisesRegex(ValueError, 'POSITION_STORE_UID_LIMIT'):
            fourth = m.Position(4, 'Fourth', 0, 10, 10)
            self.store.commit(fourth, fourth)
        damaged = b'{"version":99,"positions":[]}'
        self.store.path.write_bytes(damaged)
        with self.assertRaisesRegex(ValueError, 'POSITION_STORE_SCHEMA'):
            m.PositionStore(self.profile)
        result = await self.service.handle_CS4E2B(payload(self.service.snapshot(), 2))
        self.assertEqual(result.reason, 'POSITION_SAVE_FAILED')
        self.assertEqual(self.store.path.read_bytes(), damaged)


if __name__ == '__main__':
    unittest.main()
