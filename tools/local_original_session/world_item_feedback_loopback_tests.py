"""Real broker login and item-description drain; no hunt bot or native UI claim."""
import asyncio
import json
from pathlib import Path
import unittest
import uuid

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import broker, broker_tests, inventory, world_registry
from tools.local_original_session.world_consumable_loopback_tests import ConsumableLoopbackTests
from tools.local_own_login_request.codec import LocalLoginRequest


class ItemFeedbackLoopbackTests(ConsumableLoopbackTests):
    async def test_item_description_options_drain_after_real_login(self):
        _, predecessor = await self.bootstrap()
        predecessor.close()
        await predecessor.wait_closed()
        async with asyncio.timeout(3):
            while not self.broker._claims[14030][0]['promotable']:
                await asyncio.sleep(.01)
        reader, writer = await self.bootstrap()
        writer.write(broker_tests.c2s(0x263,
            LocalLoginRequest(0, 'standalone.local', self.uuid).payload()))
        await writer.drain()
        login = []
        async with asyncio.timeout(5):
            while not login or login[-1] != broker.LOGIN_AUTH_FINISH:
                login.append(int.from_bytes((await broker_tests.response(reader))[2:4], 'little'))
        self.assertEqual(login[:2], [0x264, 0x4e21])
        writer.write(broker_tests.c2s(0x4e28, pb.encode_message([
            pb.encode_bytes(1, b'SoloKnight'), pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        await writer.drain()
        async with asyncio.timeout(5):
            while not self.broker._world_pcs:
                await asyncio.sleep(.01)
        server_row = self.broker._claims[14030][-1]
        server_writer = server_row['writer']
        game = self.broker.realm.registry.resolve(server_writer)
        # This existing backend fixture has no LC inventory-admission observer.
        # Restore a test-copy bag, then exercise its production delivery hook.
        # This is a scoped development test, never a native/formal play PASS.
        self.broker._inventory_current_frame = self.broker._inventory_store.restore(1)
        items = inventory.validate_kit_frame(self.broker._inventory_current_frame)
        async with server_row['operation_lock']:
            await world_registry.run_hooks('inventory_delivered', self.broker.realm._world_context,
                server_writer, server_row, game, server_row['operation_lock'])
        descriptions = []
        async with asyncio.timeout(5):
            while len(descriptions) < len(items):
                frame = await broker_tests.response(reader)
                if int.from_bytes(frame[2:4], 'little') != 0x0977:
                    continue
                with pb.parse_message(frame[4:-2]) as message:
                    tokens = []
                    for child in message.occurrences(3):
                        with pb.parse_message(bytes(child.value)) as option:
                            tokens.append(option.occurrences(1)[0].value)
                    descriptions.append(dict(uid=message.occurrences(1)[0].value, tokens=tokens))
        self.assertEqual({r['uid'] for r in descriptions}, {i.identifier for i in items})
        self.assertTrue(any(48 in r['tokens'] for r in descriptions))
        self.assertTrue(any({33, 34, 1321} <= set(r['tokens']) for r in descriptions))
        self.assertIsNone(self.broker.failure_code)
        path = (Path(__file__).resolve().parents[2] / 'work/local_original_session/runs' /
                ('item-feedback-loopback-' + uuid.uuid4().hex + '.json'))
        path.write_text(json.dumps(dict(scope='DEVELOPMENT_REAL_LOGIN_ROUTER_AND_DESCRIPTION_DRAIN',
            formal_pass=False, fixture_bag_delivery=True, source_profile=str(self.profile),
            login_opcodes=login, descriptions=descriptions), indent=2), encoding='utf-8')
        print('item feedback loopback:', path)


if __name__ == '__main__':
    unittest.main()
