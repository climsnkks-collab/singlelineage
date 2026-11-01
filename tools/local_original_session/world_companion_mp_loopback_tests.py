"""Real broker TCP -> natural companion ticks -> party/pet frames -> save.

Development integration only: fixture owner/version, copied validation profile,
and a renewed blue-effect deadline in that disposable copy. No LC or hunt_bot.
Run alone with SL_TEST_PORT_BASE set to an unused isolated base, TMP/TEMP=_work/tmp.
"""
import asyncio
import contextlib
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
import uuid

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import broker, broker_tests
from tools.local_original_session import world_consumable_loopback_tests as fixture
from tools.local_own_login_request.codec import LocalLoginRequest


def values(body):
    with pb.parse_message(body) as message:
        return {field.number: (bytes(field.value) if field.wire_type == 2 else field.value)
                for field in message.fields}


class CompanionMpLoopbackTests(unittest.IsolatedAsyncioTestCase):
    bootstrap = fixture.ConsumableLoopbackTests.bootstrap

    async def asyncSetUp(self):
        environment = patch.dict(os.environ, SL_COMPANION='1', SL_COMPANION_PET_UI='1')
        environment.start()
        self.addCleanup(environment.stop)
        await fixture.ConsumableLoopbackTests.asyncSetUp(self)
        self.pump = None
        self.report = dict(scope='DEVELOPMENT_REAL_BROKER_LOOPBACK_NOT_NATIVE_OR_FORMAL_PASS',
                           source=str(fixture.SOURCE), fixture_blue_deadline_seconds=120)
        self.report_path = (Path(__file__).resolve().parents[2] / 'work' /
            'local_original_session' / 'runs' / ('companion-mp-loopback-' + uuid.uuid4().hex + '.json'))

    async def asyncTearDown(self):
        if getattr(self, 'observed_magic', None) is not None:
            self.report['events'] = list(self.observed_magic.events)
            self.report['final_mp'] = self.observed_actor.record.mp
            self.report['action'] = self.observed_actor.action
        if self.pump is not None:
            self.pump.cancel()
            with contextlib.suppress(asyncio.CancelledError, asyncio.IncompleteReadError):
                await self.pump
        await fixture.ConsumableLoopbackTests.asyncTearDown(self)
        self.report['cleanup_complete'] = self.broker.cleanup_complete
        self.report_path.write_text(json.dumps(self.report, indent=2), encoding='utf-8')
        print('companion MP loopback artifact:', self.report_path)

    async def wait_for(self, condition, timeout):
        async with asyncio.timeout(timeout):
            while not condition():
                if self.broker.failure.is_set():
                    self.fail(self.broker.failure_code)
                await asyncio.sleep(.05)

    async def test_natural_mp_ticks_spend_saved_ats_and_publish_saved_remainder(self):
        _, predecessor = await self.bootstrap()
        predecessor.close()
        await predecessor.wait_closed()
        await self.wait_for(lambda: self.broker._claims[14030][0]['promotable'], 3)
        reader, writer = await self.bootstrap()
        writer.write(broker_tests.c2s(0x263,
            LocalLoginRequest(0, 'standalone.local', self.uuid).payload()))
        await writer.drain()
        login = []
        for _ in range(15):
            frame = await broker_tests.response(reader)
            login.append(int.from_bytes(frame[2:4], 'little'))
            if login[-1] == broker.LOGIN_AUTH_FINISH:
                break
        self.assertEqual(login[:2], [0x264, 0x4e21])
        self.assertEqual(login[-1], broker.LOGIN_AUTH_FINISH)
        self.assertTrue(all(opcode == 0x4e22 for opcode in login[2:-1]))
        frames = []

        async def receive():
            while True:
                header = await reader.readexactly(2)
                frame = header + await reader.readexactly(int.from_bytes(header, 'little') - 2)
                frames.append(frame)

        self.pump = asyncio.create_task(receive())
        writer.write(broker_tests.c2s(0x4e28, pb.encode_message([
            pb.encode_bytes(1, b'SoloKnight'), pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        await writer.drain()
        view = self.broker._world
        await self.wait_for(lambda: 2 in view.companions.active, 5)
        actor = view.companions.active[2]
        record, magic = actor.record, view.companion_ai.magic
        self.observed_magic, self.observed_actor = magic, actor
        policy = magic.ats(actor)
        self.assertEqual(policy['status'], 'valid')
        selected = [row['spell'] for row in policy['buff_slots'] if 'spell' in row]
        selected_heals = [row['spell'] for row in policy.get('heal_slots', []) if row.get('spell')]
        selected_casts = set(selected + selected_heals)
        self.assertTrue(selected)
        self.assertFalse(any(row.get('spell') for row in policy['battle_slots']))

        def prepare():
            # Fixture input only: retain the captured active-blue condition even
            # when this test is rerun after its original wall-clock expiry.
            view.companion_ai.inventory.blue_until[2] = view.runtime.clock() + 120
            record.equipment['blue_expires_unix'] = time.time() + 120
            # Legacy reserve must not override the saved ATS selections.
            record.mp_reserve = record.max_mp
            magic.events.clear()
            return record.mp

        initial_mp = await view.runtime.dispatch_now(prepare)
        self.report.update(initial_mp=initial_mp, max_mp=record.max_mp,
            mp_reserve=record.mp_reserve, selected_buffs=selected,
            selected_heals=policy.get('heal_slots', []),
            saved_ats_potion_mp_threshold=policy['potion_mp']['threshold'])
        self.report['learned_spells'] = list(record.learned_spells)
        self.report['eligible'] = {name: magic.eligible(actor, name) for name in selected}
        self.report['weight_skill_blocked'] = view.companion_ai.inventory.calculated(2)[0].weight.normal_skill_blocked
        self.assertTrue(any(self.report['eligible'].values()), self.report)
        self.assertFalse(self.report['weight_skill_blocked'], self.report)

        def recovered():
            return [event for event in magic.events if event['spell'] == 'recover'
                    and event['mp_after'] > event['mp_before']]

        # Unmodified production clock/task, scheduler and regeneration counters.
        # Polling observes events; it neither calls regen nor advances the clock.
        await self.wait_for(lambda: len(recovered()) >= 2, 45)
        await self.wait_for(lambda: any(event['spell'] in selected_casts for event in magic.events), 3)
        # Saved LOCAL healing rows supplement the opaque native ATS blob. Their
        # repeated 4MP casts can spend the blue-enhanced 16MP recovery at once.
        # Observe four real decisions, without invoking or shortening reuse.
        await asyncio.sleep(4)
        writer.write(broker_tests.c2s(0x4f13, pb.encode_uint32(1, actor.ref.uid)))
        await writer.drain()
        await self.wait_for(lambda: any(int.from_bytes(f[2:4], 'little') == 0x4f14 for f in frames), 3)

        events = list(magic.events)
        casts = [event for event in events if event['spell'] in selected_casts]
        gains = sum(event['mp_after'] - event['mp_before'] for event in events
                    if event['spell'] == 'recover')
        spent = sum(event['mp_before'] - event['mp_after'] for event in casts)
        self.assertGreater(gains, 0)
        self.assertGreater(spent, 0)
        self.assertEqual(initial_mp + gains - spent, record.mp)
        for event in casts:
            self.assertEqual(event['mp_before'] - event['mp_after'], magic.rules[event['spell']].mp)
        self.assertFalse(any(event['spell'] == 'energy_bolt' for event in events))
        pet = values(next(f for f in reversed(frames) if int.from_bytes(f[2:4], 'little') == 0x4f14)[4:-2])
        # SC4F14 child ends in f10 fixed64 EXP; this retained protobuf parser
        # intentionally accepts only varint/bytes. Decode its six resource
        # scalars before the known EXP tail rather than treating it as bytes.
        self.assertEqual(pet[3][-9], 0x51)
        resources = values(pet[3][:-9])
        self.assertEqual(resources[5], record.mp)
        self.assertEqual(resources[4], record.max_mp)
        party = []
        for frame in frames:
            if int.from_bytes(frame[2:4], 'little') != 0x08a3:
                continue
            with pb.parse_message(frame[4:-2]) as message:
                party.extend(values(bytes(field.value)) for field in message.occurrences(1))
        mage_updates = [row for row in party if row[1] == b'SoloMage']
        self.assertTrue(mage_updates)
        self.assertEqual(mage_updates[-1][4], 100 * record.mp // record.max_mp)
        saved = json.loads((self.profile.parent / 'companion.json').read_text(encoding='utf-8'))
        saved_member = next(row for row in saved['records'] if row['character_id'] == 2)
        self.assertEqual(saved_member['mp'], record.mp)
        self.assertEqual(self.broker._companion_errors, [])
        self.assertEqual(view.companion_save_errors, [])
        self.report.update(events=events, gained_mp=gains, spent_mp=spent,
            final_mp=record.mp, pet_status_mp=resources[5], saved_mp=saved_member['mp'],
            party_mp_percent=mage_updates[-1][4], frame_count=len(frames),
            natural_recovery_events=len(recovered()), saved_ats_casts=len(casts))


if __name__ == '__main__':
    unittest.main()
