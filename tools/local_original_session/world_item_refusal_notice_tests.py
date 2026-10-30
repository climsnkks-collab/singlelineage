"""Development request-route checks; no socket, game or profile writes."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session.world_core_inventory import RealmInventoryCore


class RefusalNoticeTests(unittest.IsolatedAsyncioTestCase):
    async def route(self, reason, *, status='BLOCKED', accepted=True, bound=True):
        writer = object()
        queued = []
        service = NS(accepted_count=0, _current=object())

        async def handle(*args):
            service.accepted_count += int(accepted)
            return ()

        service.handle = handle
        effect = NS(_selection={'synced': True},
                    prepare_locked=AsyncMock(return_value={'status': 'SYNCHRONIZED'}),
                    consume_locked=AsyncMock(return_value={'status': status, 'reason': reason}))
        broker = NS(_item_equipment_effect=effect, _item_use_session=service,
                    _world_bound=lambda w: bound,
                    _world_pcs={id(writer): (writer, 42)},
                    _world=NS(_queue=lambda uid, frame: queued.append((uid, frame))))
        realm = NS(registry=NS(resolve=Mock()), _item_use_session=service)
        broker.realm = realm
        service.broker = broker
        self.assertEqual(await RealmInventoryCore._inventory_use_intent(realm, writer, b'fixture'), ())
        return queued, effect

    async def test_admitted_refusal_queues_one_local_notice_for_selected_owner(self):
        for reason, wording in (
                ('ITEM_USE_KIT_CLASS_NOT_ALLOWED', '직업'),
                ('ITEM_USE_CURSED_EQUIPMENT_CANNOT_REMOVE', '저주'),
                ('ITEM_USE_KIT_NO_EFFECT', '사용할 수 없습니다')):
            with self.subTest(reason=reason):
                queued, effect = await self.route(reason)
                effect.consume_locked.assert_awaited_once()
                self.assertEqual(len(queued), 1)
                uid, frame = queued[0]
                self.assertEqual(uid, 42)
                self.assertEqual(int.from_bytes(frame[2:4], 'little'), 0x4eea)
                with pb.parse_message(frame[4:-2]) as message:
                    self.assertEqual(message.occurrences(1)[0].value, 12066)
                    self.assertIn(wording, bytes(message.occurrences(2)[0].value).decode('utf-8'))

    async def test_no_duplicate_or_success_notice_and_no_unbound_notice(self):
        for options in ({'accepted': False}, {'bound': False}, {'status': 'COMMITTED'}):
            with self.subTest(options=options):
                queued, effect = await self.route('ITEM_USE_KIT_CLASS_NOT_ALLOWED', **options)
                self.assertEqual(queued, [])
                if options.get('accepted') is False:
                    effect.consume_locked.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
