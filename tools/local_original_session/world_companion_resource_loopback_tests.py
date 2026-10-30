"""Isolated real-broker TCP resource caps; no LC/hunt_bot or source-save writes.

Copied manual-test-knight starts at 480 MP solely in this disposable fixture.
Support is disabled in the copied member to isolate recovery from spending.
Production clock/regen, login/selection decoder/router, pet/party wire and joint
save run unchanged. This is development loopback, not native rendering PASS.
"""
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import uuid

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import broker, broker_tests, inventory, inventory_store
from tools.local_original_session import test_ports, world_visibility
from tools.local_original_session.world_companion_resource_tests import SOURCE, values
from tools.local_original_session import world_consumable_loopback_tests as loopback_fixture
from tools.local_own_login_request.codec import LocalLoginRequest


class CompanionResourceLoopbackTests(unittest.IsolatedAsyncioTestCase):
    bootstrap = loopback_fixture.ConsumableLoopbackTests.bootstrap

    async def asyncSetUp(self):
        environment = patch.dict(os.environ, SL_COMPANION='1', SL_COMPANION_PET_UI='1')
        environment.start()
        self.addCleanup(environment.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.report = dict(scope='DEVELOPMENT_REAL_BROKER_TCP_NOT_NATIVE_OR_FORMAL_PASS',
            source=str(SOURCE), fixture_mp=480, fixture_commands=['HOLD', 'PASSIVE'], fixture_support_enabled=False,
            listener_ports=test_ports.listener_ports(), source_files={})
        for source in SOURCE.iterdir():
            if source.is_file() and source.suffix in ('.json', '.bin'):
                shutil.copy2(source, root / source.name)
                if source.name in ('characters.json', 'inventory.json', 'equipment.json', 'companion.json'):
                    self.report['source_files'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        path = root / 'companion.json'
        payload = json.loads(path.read_text(encoding='utf-8'))
        next(r for r in payload['records'] if r['character_id'] == 2).update(
            mp=480, movement_mode='HOLD', combat_mode='PASSIVE', support_enabled=False)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        self.profile = root / 'characters.json'
        self.uuid = str(uuid.uuid4())
        self.broker = broker.PersistentBroker(sockets=broker_tests.reserve(),
            listener_ports=test_ports.listener_ports(), retained_owner=object(), owner_handle=object(),
            owner_job=object(), owner_guard=lambda *_: True, owner_liveness_guard=lambda: True,
            source_guard=lambda: None, conversation_factory=broker_tests.FixtureConversation,
            expected_uuid=self.uuid, store_path=self.profile,
            world_policy=world_visibility.POLICY, world_starter_kit='test_knight')
        self.broker._inventory_store = inventory_store.InventoryStore(self.profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        self.broker._inventory_kit_policy = inventory.KIT_POLICY
        self.broker.policy.inventory_add = self.broker.policy.item_kit = True
        self.clients, self.pump, self.frames = [], None, []
        await self.broker.start()

    async def asyncTearDown(self):
        view = self.broker._world
        actor = view.companions.active.get(2)
        if actor is not None:
            self.report.update(final_mp=actor.record.mp, final_action=actor.action,
                regen_points=actor.regen_points, regen_activity=actor.regen_activity,
                regen_at=actor.regen_at,
                magic_events=list(view.companion_ai.magic.events))
        if self.pump is not None:
            self.pump.cancel()
            with contextlib.suppress(asyncio.CancelledError, asyncio.IncompleteReadError):
                await self.pump
        await self.broker.close()
        for _, writer in self.clients:
            writer.close()
            await writer.wait_closed()
        self.report['cleanup_complete'] = self.broker.cleanup_complete
        self.report['broker_failure'] = self.broker.failure_code
        log = Path(__file__).resolve().parents[2] / 'work' / 'local_original_session' / 'runs'
        log /= 'companion-equipment-caps-loopback-' + uuid.uuid4().hex + '.json'
        log.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('UTF8_RESULT', log)

    async def wait_for(self, condition, timeout=5):
        async with asyncio.timeout(timeout):
            while not condition():
                if self.broker.failure.is_set():
                    self.fail(self.broker.failure_code)
                await asyncio.sleep(.02)

    async def test_login_natural_cap_pet_party_and_saved_base_current(self):
        _, predecessor = await self.bootstrap()
        predecessor.close()
        await predecessor.wait_closed()
        await self.wait_for(lambda: self.broker._claims[14030][0]['promotable'])
        reader, writer = await self.bootstrap()
        writer.write(broker_tests.c2s(0x263, LocalLoginRequest(0, 'standalone.local', self.uuid).payload()))
        await writer.drain()
        login = []
        for _ in range(15):
            wire = await broker_tests.response(reader)
            login.append(int.from_bytes(wire[2:4], 'little'))
            if login[-1] == broker.LOGIN_AUTH_FINISH:
                break
        self.assertEqual(login[:2], [0x264, 0x4e21])
        self.assertEqual(login[-1], broker.LOGIN_AUTH_FINISH)
        self.assertTrue(all(op == 0x4e22 for op in login[2:-1]))
        async def receive():
            while True:
                header = await reader.readexactly(2)
                self.frames.append(header + await reader.readexactly(int.from_bytes(header, 'little') - 2))
        self.pump = asyncio.create_task(receive())
        writer.write(broker_tests.c2s(0x4e28, pb.encode_message([
            pb.encode_bytes(1, b'SoloKnight'), pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        await writer.drain()
        view = self.broker._world
        await self.wait_for(lambda: 2 in view.companions.active)
        actor = view.companions.active[2]
        record = actor.record
        self.assertEqual((record.max_mp, record.effective_max_mp, record.mp), (314, 489, 480))
        self.report.update(login_opcodes=login, before_mp=record.mp, base_max_mp=record.max_mp,
                           effective_max_mp=record.effective_max_mp)
        # No regen call, accelerated clock or ready-state override: wait for the
        # production runtime's natural MP event and its normal save/party work.
        await self.wait_for(lambda: record.mp == 489, 25)
        writer.write(broker_tests.c2s(0x4f13, pb.encode_uint32(1, actor.ref.uid)))
        await writer.drain()
        await self.wait_for(lambda: any(int.from_bytes(f[2:4], 'little') == 0x4f14 for f in self.frames))
        pet = values(next(f for f in reversed(self.frames) if int.from_bytes(f[2:4], 'little') == 0x4f14)[4:-2])
        resources = values(pet[3][:-9])
        self.assertEqual((resources[4], resources[5]), (489, 489))
        party = []
        for wire in self.frames:
            if int.from_bytes(wire[2:4], 'little') == 0x08a3:
                with pb.parse_message(wire[4:-2]) as message:
                    party.extend(values(bytes(f.value)) for f in message.occurrences(1))
        mage = [r for r in party if r[1] == b'SoloMage']
        self.assertTrue(mage)
        self.assertEqual(mage[0][4], 100 * 480 // 489)
        self.assertEqual(mage[-1][4], 100)
        saved = json.loads(self.profile.with_name('companion.json').read_text(encoding='utf-8'))
        member = next(r for r in saved['records'] if r['character_id'] == 2)
        self.assertEqual((member['max_mp'], member['mp']), (314, 489))
        self.assertEqual(view.companion_save_errors, [])
        self.assertEqual(self.broker._companion_errors, [])
        self.report.update(after_mp=record.mp, pet_max_mp=resources[4], pet_mp=resources[5],
            party_percent_first=mage[0][4], party_percent_last=mage[-1][4],
            saved_base_mp=member['max_mp'], saved_current_mp=member['mp'], frame_count=len(self.frames),
            outcome='PASS_WITHIN_DEVELOPMENT_SCOPE')


if __name__ == '__main__':
    unittest.main(verbosity=2)
