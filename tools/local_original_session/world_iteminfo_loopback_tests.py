"""Owned socket smoke using the existing preserved scenario fixture; no native game."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as scenarios


class ItemInfoLoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_then_direction_alive_and_received_item_descriptions(self):
        root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
        root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='iteminfo-loopback-', dir=root))
        scenario = scenarios.Scenario(scenarios.parser().parse_args([]), 'iteminfo', directory)
        result = {'directory': str(directory), 'scope': 'real decoder/router; native UI unverified'}
        try:
            await scenario.open(seed=True)
            bot, broker = scenario.bot, scenario.broker
            peer = bot.peer
            await peer.wait(0, lambda batch: hb.find(batch, 0x0977), 'ITEM_DESCRIPTION_DELIVERY')
            descriptions = []
            for frame in peer.frames:
                if frame.opcode != 0x0977:
                    continue
                with pb.parse_message(frame.wire[4:-2]) as message:
                    uid = message.occurrences(1)[0].value
                    name = bytes(message.occurrences(2)[0].value)
                    count = message.occurrences(4)[0].value
                    member = bot.inventory.get(uid)
                    self.assertIsNotNone(member)
                    self.assertTrue(name)
                    self.assertGreater(count, 0)
                    descriptions.append({'uid': uid, 'name': name.decode('utf-8'), 'count': count,
                                         'description_children': len(message.occurrences(3))})
            self.assertTrue(descriptions)
            self.assertTrue(any(row['description_children'] for row in descriptions))
            await peer.request(0x7fff, alive=True, check=lambda batch: hb.find(batch, 0x4f57))
            heading = 6
            await peer.request(0x4e2f, hb.uint(1, heading), alive=True,
                               check=lambda batch: hb.find(batch, 0x4f57))
            self.assertIs(bot.peer, peer)
            self.assertIsNone(peer.error)
            pc = broker._world.entities.get(bot.self_uid)
            self.assertIsNotNone(pc)
            self.assertEqual(pc.heading, heading)
            self.assertIsNone(broker.report().get('failure_code'))
            result.update(status='SUCCESS', self_uid=bot.self_uid, heading=pc.heading,
                          descriptions=descriptions, request_counts=dict(bot.request_counts))
        except BaseException as error:
            result.update(status='FAILED', error=f'{type(error).__name__}: {error}')
            raise
        finally:
            clean = await scenario.close()
            result.update(cleanup_complete=clean, epochs=scenario.epochs, checks=scenario.checks)
            (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'iteminfo loopback evidence: {directory}')
            self.assertTrue(clean, scenario.checks)


if __name__ == '__main__':
    unittest.main()
