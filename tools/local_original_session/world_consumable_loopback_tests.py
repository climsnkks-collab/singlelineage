"""Real broker TCP entry without LC or hunt_bot; source profile is copied to temp."""
import asyncio
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from unittest import mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import broker, broker_tests, inventory, inventory_store
from tools.local_original_session import test_ports, world_registry, world_visibility
from tools.local_own_login_request.codec import LocalLoginRequest


SOURCE = (Path(__file__).resolve().parents[2] / 'work' / 'local_original_session'
          / 'validation-profiles' / 'play-smoke-claude-20261030-2')


def prepare_fullness(root):
    """Only this fresh test copy: exercise nonzero saved nutrition restoration."""
    path = root / 'consumable-effects.json'
    saved = json.loads(path.read_text(encoding='utf-8'))
    for row in saved['rows']:
        if row['uid'] == 1:
            row['fullness'] = 225
    path.write_text(json.dumps(saved), encoding='utf-8')


class ConsumableLoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for source in SOURCE.iterdir():
            if source.is_file() and source.suffix in ('.json', '.bin'):
                shutil.copy2(source, root / source.name)
        prepare_fullness(root)
        self.profile = root / 'characters.json'
        self.uuid = str(uuid.uuid4())
        self.broker = broker.PersistentBroker(
            sockets=broker_tests.reserve(), listener_ports=test_ports.listener_ports(),
            retained_owner=object(), owner_handle=object(), owner_job=object(),
            owner_guard=lambda *_: True, owner_liveness_guard=lambda: True,
            source_guard=lambda: None, conversation_factory=broker_tests.FixtureConversation,
            expected_uuid=self.uuid, store_path=self.profile,
            world_policy=world_visibility.POLICY, world_starter_kit='test_knight')
        store = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                kit_policy=inventory.KIT_POLICY)
        self.broker._inventory_store = store
        self.broker._inventory_kit_policy = inventory.KIT_POLICY
        self.broker.policy.inventory_add = self.broker.policy.item_kit = True
        self.clients = []
        await self.broker.start()

    async def asyncTearDown(self):
        await self.broker.close()
        for _, writer in self.clients:
            writer.close()
            await writer.wait_closed()

    async def bootstrap(self):
        reader, writer = await asyncio.open_connection('127.0.0.1', test_ports.port(14030))
        self.clients.append((reader, writer))
        self.assertEqual(await broker_tests.response(reader), broker.KEY12)
        writer.write(broker_tests.c2s(0x4e34, broker_tests.version_request()))
        await writer.drain()
        self.assertEqual(len(await broker_tests.response(reader)), 76)
        writer.write(broker_tests.c2s(0x4f3d))
        await writer.drain()
        self.assertEqual(await broker_tests.response(reader), broker.EMPTY_COUNTS)
        return reader, writer

    async def test_reconnect_saved_potions_reach_first_selected_pc(self):
        first_reader, first_writer = await self.bootstrap()
        first_writer.close()
        await first_writer.wait_closed()
        for _ in range(200):
            if self.broker._claims[14030][0]['promotable']:
                break
            await asyncio.sleep(.005)
        else:
            self.fail('bootstrap predecessor did not close')
        reader, writer = await self.bootstrap()
        writer.write(broker_tests.c2s(0x263,
            LocalLoginRequest(0, 'standalone.local', self.uuid).payload()))
        await writer.drain()
        login = [await broker_tests.response(reader) for _ in range(5)]
        self.assertEqual([int.from_bytes(frame[2:4], 'little') for frame in login],
                         [0x264, 0x4e21, 0x4e22, 0x4e22, broker.LOGIN_AUTH_FINISH])
        select = pb.encode_message([pb.encode_bytes(1, b'SoloKnight'),
                                    pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        writer.write(broker_tests.c2s(0x4e28, select))
        await writer.drain()
        for _ in range(300):
            trace = self.broker._world_item_effects.restore_trace
            if any(event['phase'] == 'after_enter' for event in trace):
                break
            await asyncio.sleep(.01)
        else:
            self.fail('world after_enter did not run')
        loaded = next(event for event in trace if event['phase'] == 'runtime_started')
        entered = next(event for event in trace if event['phase'] == 'after_enter')
        self.assertEqual(set(loaded['loaded'][0]['potion_remaining']), {'17', '296'})
        self.assertEqual(entered['saved_templates_before'], [17, 296])
        self.assertEqual(entered['active_templates_after'], [17, 296])
        self.assertEqual(entered['resume_decision']['outcome'], 'ALREADY_BOUND')
        self.assertEqual(entered['owner_before']['effects_id'], loaded['owners'][0]['effects_id'])
        phases = [event['phase'] for event in trace]
        self.assertEqual(phases[:6], ['runtime_started', 'pre_before_enter', 'post_bind_pc',
                                      'post_update_pc', 'pre_after_enter', 'after_enter'])
        bound_pc = next(event['owner'] for event in trace if event['phase'] == 'post_bind_pc')
        bound_event = next(event for event in trace if event['phase'] == 'post_bind_pc')
        self.assertEqual(bound_event['resume_decision']['outcome'], 'RESUMED_SPEED')
        self.assertFalse(bound_pc['state_paused'])
        self.assertEqual(set(bound_pc['state_potions']), {17, 296})
        for event in trace[1:5]:
            self.assertEqual(set(event['owner']['store_potion_remaining']), {'17', '296'})
        server_row = self.broker._claims[14030][-1]
        server_writer = server_row['writer']
        game = self.broker.realm.registry.resolve(server_writer)
        self.broker._inventory_current_frame = self.broker._inventory_store.restore(1)
        before_tx = len(self.broker.policy.log)
        async with server_row['operation_lock']:
            await world_registry.run_hooks('inventory_delivered', self.broker.realm._world_context,
                server_writer, server_row, game, server_row['operation_lock'])
        delivery = next(event for event in trace if event['phase'] == 'inventory_delivered')
        self.assertEqual(delivery['proposed_opcodes'][:6],
                         [0x4ed8, 0x4e5b, 0x4e91] * 2)
        self.assertEqual((delivery['status'], delivery['drained_chunks']), ('DRAINED', 2))
        sent = [opcode for kind, port, opcode, size in list(self.broker.policy.log)[before_tx:]
                if kind == 'tx' and opcode in (0x4ed8, 0x4e5b, 0x4e91)]
        self.assertEqual(sent, [0x4ed8, 0x4e5b, 0x4e91] * 2)
        reported = self.broker.report()['world']['consumable_restore']
        self.assertEqual(reported, trace)
        json.dumps(reported)  # The launcher can persist these facts in result.json.
        # Inspect the real TCP consumer bytes, not only the broker's opcode log.
        # This fixture's restored state contains haste17 and brave296 only.
        tooltips = {}
        latest_hunger = None
        for _ in range(200):
            wire = await asyncio.wait_for(broker_tests.response(reader), 2)
            if int.from_bytes(wire[2:4], 'little') == 0x4e38:
                from tools.local_world_protocol import model as world
                from tools.local_original_session.world_status_frames_tests import decode_status
                # The established full-status decoder handles optional f26 double.
                fields = (decode_status(self, wire) if wire[-12:-10] == b'\xd1\x01'
                          else world.decode_payload(0x4e38, wire[4:-2]))
                latest_hunger = fields[16]
            if int.from_bytes(wire[2:4], 'little') != 0x4e91:
                continue
            with pb.parse_message(wire[4:-2]) as outer:
                with pb.parse_message(bytes(outer.occurrences(2)[0].value)) as child:
                    fields = {field.number: field.value for field in child.fields}
            if fields.get(1) in (223, 224):
                tooltips[fields[1]] = fields[7]
                self.assertNotIn(8, fields)  # no guessed automatic-chat policy
                self.assertNotIn(9, fields)
            if len(tooltips) == 2:
                break
        self.assertEqual(tooltips, {223: 849, 224: 851})
        self.assertEqual(latest_hunger, 100)


class ProductConsumableLoopbackTests(ConsumableLoopbackTests):
    async def asyncSetUp(self):
        from tools.local_original_session import feature_config, inventory_tests, launcher
        companion = mock.patch.dict('os.environ', {'SL_COMPANION': '1'})
        companion.start()
        self.addCleanup(companion.stop)
        fixture = inventory_tests.GateTests('test_real_source_guards_retained_and_npc_free_realm_positive_once')
        await fixture.asyncSetUp()
        self.addCleanup(fixture.doCleanups)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for source in SOURCE.iterdir():
            if source.is_file() and source.suffix in ('.json', '.bin'):
                shutil.copy2(source, root / source.name)
        prepare_fullness(root)
        self.profile = root / 'characters.json'
        self.uuid = str(uuid.uuid4())
        config = feature_config.parse(json.loads((root / 'world-config.json').read_text(encoding='utf-8')))
        run = root / 'run'
        run.mkdir()
        factory = launcher.ProductFeatureFactory(fixture.reader,
            product='sibling-manual-play-companion-nopatch', control_mode='manual',
            directory=run, config=config)
        retained = fixture.reader.owner
        self.broker = broker.PersistentBroker(
            sockets=broker_tests.reserve(), listener_ports=test_ports.listener_ports(),
            retained_owner=retained, owner_handle=retained.owner_handle,
            owner_job=retained.owner_job, owner_guard=lambda *_: True,
            owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=broker_tests.FixtureConversation,
            expected_uuid=self.uuid, store_path=self.profile, **factory.broker_options())
        factory(self.broker)
        self.clients = []
        await self.broker.start()


if __name__ == '__main__':
    unittest.main()
