"""Development TCP regression on a disposable saved-state copy; no LC or bot.

Normal login/selection/movement route, with explicit prepared status fixtures.
This checks received HUD/speed packets, not native input or rendering.
"""
import asyncio
import contextlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import broker, broker_tests, world_magic
from tools.local_original_session.world_feature_magic import SPELL_BUFF_ICONS
from tools.local_original_session import world_consumable_loopback_tests as fixture
from tools.local_own_login_request.codec import LocalLoginRequest


def values(body):
    with pb.parse_message(body) as message:
        return {f.number: bytes(f.value) if f.wire_type == 2 else f.value
                for f in message.fields}


class StatusFeedbackLoopbackTests(unittest.IsolatedAsyncioTestCase):
    bootstrap = fixture.ConsumableLoopbackTests.bootstrap

    async def asyncSetUp(self):
        prepared = tempfile.TemporaryDirectory()
        self.addCleanup(prepared.cleanup)
        root = Path(prepared.name)
        for source in fixture.SOURCE.iterdir():
            if source.is_file() and source.suffix in ('.json', '.bin'):
                shutil.copy2(source, root / source.name)
        engine = world_magic.PlayerMagic(world_magic.load_catalog())
        now = time.monotonic()
        engine.apply_status(1, 'meditation', now, 300, spell=31,
                            params={'tick_seconds': 10, 'mp_restore': 5})
        engine.apply_status(1, 'entangle', now, 5, spell=151,
                            params={'move_multiplier': 2})
        engine.state(1).invisible_until = now + 3
        engine.apply_status(1, 'paralyze', now, 3, spell=32, onset=6)
        engine.apply_status(1, 'stun', now, 3, spell=86, onset=8)
        engine.apply_status(1, 'blind', now, 8, spell=19)
        engine.apply_status(1, 'darkness', now, 10, spell=39)
        engine.state(1).poison = dict(until=now + 8, next_tick=now + 3,
            tick_seconds=3, damage=1, source_uid=1)
        payload = json.loads((root / 'magic.json').read_text(encoding='utf-8'))
        payload['rows'] = [r for r in payload['rows'] if r['uid'] != 1]
        payload['rows'].append(engine.snapshot(1, now))
        (root / 'magic.json').write_text(json.dumps(payload), encoding='utf-8')
        # The source fixture remains untouched; all writes belong to this copy.
        with patch.object(fixture, 'SOURCE', root):
            try:
                await fixture.ConsumableLoopbackTests.asyncSetUp(self)
            except BaseException:
                if hasattr(self, 'broker'):
                    await self.broker.close()
                raise
        self.frames, self.pump = [], None

    async def asyncTearDown(self):
        print('STATUS_FEEDBACK_DIAGNOSTICS', json.dumps({
            'broker_failure': self.broker.failure_code,
            'magic_errors': self.broker._world_magic_errors,
            'state_packets': [{
                'opcode': hex(int.from_bytes(frame[2:4], 'little')),
                'fields': values(frame[4:-2])}
                for frame in self.frames
                if int.from_bytes(frame[2:4], 'little') in (0x4eeb, 0x4f03, 0x4f04, 0x4f05)]},
            ensure_ascii=False))
        if self.pump is not None:
            self.pump.cancel()
            with contextlib.suppress(asyncio.CancelledError, asyncio.IncompleteReadError):
                await self.pump
        await fixture.ConsumableLoopbackTests.asyncTearDown(self)

    async def wait_for(self, predicate, timeout=8):
        async with asyncio.timeout(timeout):
            while not predicate():
                self.assertFalse(self.broker.failure.is_set(), self.broker.failure_code)
                await asyncio.sleep(.02)

    def icons(self, operation, key):
        result = []
        for frame in self.frames:
            if int.from_bytes(frame[2:4], 'little') != 0x4e91:
                continue
            row = values(frame[4:-2])
            child = values(row[2])
            matches = (child.get(4) == SPELL_BUFF_ICONS[key]
                       if operation == 3 else child.get(1) == key)
            if row.get(1) == operation and matches:
                result.append(frame)
        return result

    def speeds(self):
        result = []
        for frame in self.frames:
            if int.from_bytes(frame[2:4], 'little') != 0x4e5b:
                continue
            row = values(frame[4:-2])
            if row.get(1) != 1:
                continue
            with pb.parse_message(row[2]) as message:
                result.append({values(bytes(f.value))[1]: values(bytes(f.value))[2]
                               for f in message.occurrences(1)})
        return result

    def invisible(self, active):
        return [frame for frame in self.frames
                if int.from_bytes(frame[2:4], 'little') == 0x4f04
                and values(frame[4:-2]) == {1: 1, 2: int(active)}]

    def state_packet(self, opcode, fields, *, since=0):
        return [frame for frame in self.frames[since:]
                if int.from_bytes(frame[2:4], 'little') == opcode
                and values(frame[4:-2]) == fields]

    async def test_login_status_publication_movement_cancel_overlap_and_expiry(self):
        _, predecessor = await self.bootstrap()
        predecessor.close()
        await predecessor.wait_closed()
        await self.wait_for(lambda: self.broker._claims[14030][0]['promotable'])
        reader, writer = await self.bootstrap()
        writer.write(broker_tests.c2s(0x263,
            LocalLoginRequest(0, 'standalone.local', self.uuid).payload()))
        await writer.drain()
        login = []
        for _ in range(15):
            wire = await broker_tests.response(reader)
            login.append(int.from_bytes(wire[2:4], 'little'))
            if login[-1] == broker.LOGIN_AUTH_FINISH:
                break
        self.assertEqual(login[:2], [0x264, 0x4e21])
        self.assertEqual(login[-1], broker.LOGIN_AUTH_FINISH)

        async def receive():
            while True:
                head = await reader.readexactly(2)
                self.frames.append(head + await reader.readexactly(int.from_bytes(head, 'little') - 2))
        self.pump = asyncio.create_task(receive())
        writer.write(broker_tests.c2s(0x4e28, pb.encode_message([
            pb.encode_bytes(1, b'SoloKnight'), pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        await writer.drain()
        await self.wait_for(lambda: self.icons(1, 31) and self.speeds())
        await self.wait_for(lambda: self.invisible(True))
        await self.wait_for(lambda: self.state_packet(0x4f03, {1: 1}))
        await self.wait_for(lambda: self.state_packet(0x4f05, {1: 1, 2: 1, 3: 0}))
        # The saved potion factor may be present. Entangle alone changes the
        # relationship between the independently encoded move/attack totals.
        await self.wait_for(lambda: any(r[0] != r[1] for r in self.speeds()))
        server_writer = self.broker._claims[14030][-1]['writer']
        service = self.broker.realm.service(server_writer)
        start = service.snapshot()
        entity = self.broker._world.entities.get(1)
        heading = next(h for h in range(8) if self.broker._world.terrain.can_step(
            entity.map_id, entity.x, entity.y, h))
        writer.write(broker_tests.c2s(0x4e2b, pb.encode_message([
            pb.encode_uint32(1, start.packed), pb.encode_uint32(2, heading)])))
        await writer.drain()
        await self.wait_for(lambda: service.snapshot().packed != start.packed)
        await self.wait_for(lambda: self.icons(3, 31))
        await self.wait_for(lambda: self.icons(3, 151), timeout=10)
        await self.wait_for(lambda: self.speeds()[-1][0] == self.speeds()[-1][1])
        await self.wait_for(lambda: self.invisible(False))
        await self.wait_for(lambda: self.state_packet(0x4eeb, {1: 2}))
        await self.wait_for(lambda: self.state_packet(0x4f05, {1: 1, 2: 1, 3: 1}))

        async def step_while_blocked():
            before = service.snapshot().packed
            corrections = sum(int.from_bytes(f[2:4], 'little') == 0x4ee0 for f in self.frames)
            writer.write(broker_tests.c2s(0x4e2b, pb.encode_message([
                pb.encode_uint32(1, before), pb.encode_uint32(2, heading)])))
            await writer.drain()
            await self.wait_for(lambda: sum(int.from_bytes(f[2:4], 'little') == 0x4ee0
                                            for f in self.frames) > corrections)
            self.assertEqual(service.snapshot().packed, before)

        await step_while_blocked()
        await self.wait_for(lambda: self.state_packet(0x4eeb, {1: 0}))
        overlap_start = len(self.frames)
        await self.wait_for(lambda: self.state_packet(0x4eeb, {1: 3}, since=overlap_start))
        await step_while_blocked()  # Stun still owns the other native lock key.
        await self.wait_for(lambda: self.state_packet(0x4eeb, {1: 1}, since=overlap_start))
        await self.wait_for(lambda: self.state_packet(0x4f03, {1: 0}))
        await self.wait_for(lambda: self.state_packet(0x4f05, {1: 1, 2: 0, 3: 0}))
        before = service.snapshot().packed
        writer.write(broker_tests.c2s(0x4e2b, pb.encode_message([
            pb.encode_uint32(1, before), pb.encode_uint32(2, heading)])))
        await writer.drain()
        await self.wait_for(lambda: service.snapshot().packed != before)
        self.assertFalse(self.broker._world_magic_errors)
        print('STATUS_FEEDBACK_LOOPBACK: login, prepared HUD, move cancel/remove, '
              'separate speed totals, native status packets, overlap and expiry recovery received; '
              'native UI unverified')


if __name__ == '__main__':
    unittest.main(verbosity=2)
