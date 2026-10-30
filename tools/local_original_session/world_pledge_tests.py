"""Pledge policy, actual profile/inventory persistence and interrupted payment."""
import tempfile
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.local_character_creation.realm import CharacterStore, Creation
from tools.local_original_session import inventory, inventory_store, world_pledge as pledge
from tools.local_original_session.broker import INVENTORY_STARTER_FIELDS


class PledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        self.store = CharacterStore(self.profile)
        self.prince = self.store.create(Creation('Monarch', 0, 0, (18, 12, 16, 9, 12, 8)))[0]
        self.member = self.store.create(Creation('Companion', 3, 0, (8, 7, 16, 18, 8, 18)))[0]
        rows = []
        for uid, template, count in ((100, 7, 10000), (101, 23, 1)):
            row = dict(INVENTORY_STARTER_FIELDS)
            row.update({1: uid, 2: template, 4: count})
            rows.append(row)
        self.frame = inventory.build_kit_frame(rows)
        self.bag = inventory_store.InventoryStore(self.profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        self.bag.grant(self.prince, self.frame)

    def create(self, **options):
        args = dict(uid=self.prince, name='혈맹시험', character_class=0, level=5,
            current_frame=self.bag.restore(self.prince), replace_kit=self.bag.replace_kit)
        args.update(options)
        return pledge.create(self.store, **args)

    def wallet(self):
        return next(dict(v.raw_fields)[4] for v in
            inventory.validate_kit_frame(self.bag.restore(self.prince)) if v.template_bits == 7)

    def test_creation_pays_once_and_persists(self):
        value, frame, wire = self.create()
        self.assertEqual(self.wallet(), 9000)
        self.assertEqual(self.bag.restore(self.prince), frame)
        self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x0965)
        self.assertEqual(pledge.membership(value, self.prince)['name'], '혈맹시험')
        self.assertEqual(CharacterStore(self.profile).pledges(), value)
        with self.assertRaisesRegex(pledge.Refused, 'ALREADY_MEMBER'):
            self.create()
        self.assertEqual(self.wallet(), 9000)

    def test_official_creation_conditions_and_name_refuse_without_cost(self):
        for values, error in ((dict(character_class=1), 'PRINCE'),
                (dict(level=4), 'LEVEL_5'), (dict(name='공백 이름'), 'NAME'),
                (dict(name='가' * 9), 'NAME'), (dict(name='A' * 17), 'NAME')):
            with self.subTest(values=values), self.assertRaisesRegex(pledge.Refused, error):
                self.create(**values)
            self.assertEqual(self.wallet(), 10000)
            self.assertEqual(self.store.pledges(), pledge.empty())
        poor = [dict(v.raw_fields) for v in inventory.validate_kit_frame(self.frame)]
        poor[0][4] = 999
        with self.assertRaisesRegex(pledge.Refused, 'ADENA_1000'):
            self.create(current_frame=inventory.build_kit_frame(poor))
        self.assertEqual(self.store.pledges(), pledge.empty())

    def test_same_account_offline_member_notice_leave_and_disband(self):
        self.create()
        value = self.store.pledge_enroll_character(self.prince, self.member)
        self.assertEqual(pledge.membership(value, self.member)['members'], [self.prince, self.member])
        with self.assertRaisesRegex(pledge.Refused, 'LEADER'):
            self.store.update_pledges(lambda v: pledge.notice(v, self.member, 'invalid'))
        self.store.update_pledges(lambda v: pledge.notice(v, self.prince, '공지\n둘째 줄'))
        self.assertEqual(CharacterStore(self.profile).pledges()['clans'][0]['notice'], '공지\n둘째 줄')
        self.store.update_pledges(lambda v: pledge.leave(v, self.member))
        self.assertIsNone(pledge.membership(self.store.pledges(), self.member))
        self.store.pledge_enroll_character(self.prince, self.member)
        self.store.update_pledges(lambda v: pledge.leave(v, self.prince))
        value = CharacterStore(self.profile).pledges()
        self.assertEqual(value['clans'], [])
        self.assertEqual(value['next_id'], 2)
        self.assertEqual(self.wallet(), 9000)

    def test_off_account_member_is_refused_and_roster_bookmark_preserved(self):
        self.store.update_bookmarks(self.prince, lambda v: __import__(
            'tools.local_original_session.world_bookmark', fromlist=['add']).add(v, 'home', 0, 1, 2))
        roster = self.store.pledge_characters()
        bookmark = self.store.bookmarks(self.prince)
        self.create()
        with self.assertRaisesRegex(ValueError, 'SAVED_CHARACTER'):
            self.store.pledge_enroll_character(self.prince, 999)
        self.assertEqual(self.store.pledge_characters(), roster)
        self.assertEqual(self.store.bookmarks(self.prince), bookmark)

    def test_interrupted_after_payment_same_request_finishes_without_recharge(self):
        original = self.store._write
        def fail_final(data):
            if data.get('pledges', {}).get('clans'):
                raise OSError('TEST_FINAL_CHARACTER_WRITE_FAILED')
            original(data)
        with patch.object(self.store, '_write', side_effect=fail_final):
            with self.assertRaisesRegex(OSError, 'TEST_FINAL'):
                self.create()
        self.assertEqual(self.wallet(), 9000)
        self.assertIsNotNone(CharacterStore(self.profile).pledges()['pending_creation'])
        self.store = CharacterStore(self.profile)
        self.create()
        self.assertEqual(self.wallet(), 9000)
        self.assertIsNone(self.store.pledges()['pending_creation'])
        self.assertEqual(len(self.store.pledges()['clans']), 1)

    def test_interrupted_before_payment_retries_cas_and_unknown_kit_preserves_pending(self):
        def fail_payment(*args):
            raise OSError('TEST_INVENTORY_WRITE_FAILED')
        with self.assertRaisesRegex(OSError, 'TEST_INVENTORY'):
            self.create(replace_kit=fail_payment)
        self.assertEqual(self.wallet(), 10000)
        pending = self.store.pledges()
        different = [dict(v.raw_fields) for v in inventory.validate_kit_frame(self.frame)]
        different[0][4] = 9999
        with self.assertRaisesRegex(pledge.Refused, 'PENDING_INVENTORY_CHANGED'):
            self.create(current_frame=inventory.build_kit_frame(different))
        self.assertEqual(self.store.pledges(), pending)
        self.create()
        self.assertEqual(self.wallet(), 9000)

    def test_native_request_shapes_and_corrupt_profile_are_distinct(self):
        from tools.local_entry_server import protobuf as pb
        from tools.local_character_creation.realm import Refused as StoreRefused
        body = pb.encode_bytes(1, '혈맹시험'.encode('utf-8'))
        self.assertEqual(pledge.parse_request(pledge.JOIN, body)[1], '혈맹시험')
        self.assertEqual(pledge.parse_request(pledge.JOIN, body + b'\x10\x00')[2], 0)
        with self.assertRaises(pb.WireError):
            pledge.parse_request(pledge.NOTICE, pb.encode_bytes(2, b'unknown'))
        with self.assertRaises(UnicodeError):
            pledge.parse_request(pledge.NOTICE, pb.encode_bytes(1, b'\xff'))
        with self.assertRaises(pledge.Refused):
            pledge.parse_request(pledge.CREATE, body + b'\x10\x01')
        data = json.loads(self.profile.read_text(encoding='utf-8'))
        data['pledges'] = dict(next_id=0, clans=[], pending_creation=None)
        self.profile.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(StoreRefused) as caught:
            self.store.pledges()
        self.assertNotIsInstance(caught.exception, pledge.Refused)

    def test_member_page_uses_distinct_saved_uid_keys_without_unknown_enums(self):
        from tools.local_original_session.hunt_bot import fields, scalar
        self.create()
        value = self.store.pledge_enroll_character(self.prince, self.member)
        chars = dict(self.store.pledge_characters())
        info, page = pledge.info_frames(value['clans'][0], chars)
        outer = fields(page[4:-2])
        self.assertEqual((scalar(outer, 1), scalar(outer, 2)), (1, 0))
        rows = [fields(raw) for raw in outer[3]]
        self.assertEqual({scalar(row, 4) for row in rows}, {self.prince, self.member})
        self.assertEqual({scalar(row, 1).decode('utf-8') for row in rows}, {'Monarch', 'Companion'})
        self.assertTrue(all(set(row) == {1, 4} for row in rows))
        self.assertEqual(scalar(fields(info[4:-2]), 1).decode('utf-8'), '혈맹시험')

    def test_optional_registration_can_be_removed_without_duplicate_methods(self):
        from tools.local_original_session import world_handlers
        full = world_handlers.build_registry(world_handlers.CORE_MODULES + world_handlers.FEATURE_MODULES)
        omitted = world_handlers.build_registry(world_handlers.CORE_MODULES + tuple(name
            for name in world_handlers.FEATURE_MODULES if name != 'world_feature_pledge'))
        self.assertIn('_pledge_request', full.methods)
        self.assertNotIn('_pledge_request', omitted.methods)
        self.assertIn(pledge.CREATE, full.frames)
        self.assertNotIn(pledge.CREATE, omitted.frames)
        self.assertNotIn('_pledge_initialize', omitted.hooks.get('initialize', ()))


if __name__ == '__main__':
    unittest.main()
