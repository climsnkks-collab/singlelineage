"""Pure wire and durable local-state checks; no game or socket."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import realm


def request(name='로컬기사', *, omit=()):
    fields = {1: name, 2: 1, 3: 0, 4: 16, 5: 12, 6: 14,
              7: 9, 8: 10, 9: 8, 10: 1, 11: 2, 12: 1234}
    parts = []
    for number, value in fields.items():
        if number in omit:
            continue
        if number == 1:
            parts.append(realm.pb.encode_bytes(number, value.encode('utf-8')))
        else:
            parts.append(realm.pb.encode_varint(number << 3) +
                         realm.pb.encode_varint(value))
    return realm.pb.encode_message(parts)


class CharacterCreationTests(unittest.TestCase):
    def test_exact_required_fields_and_utf8(self):
        parsed = realm.decode_creation(request(omit=(10, 11, 12)))
        self.assertEqual((parsed.character_class, parsed.gender, parsed.attributes),
                         (1, 0, (16, 12, 14, 9, 10, 8)))
        for missing in range(1, 10):
            with self.subTest(missing=missing), self.assertRaises(realm.Refused):
                realm.decode_creation(request(omit=(missing,)))
        with self.assertRaises(realm.Refused):
            realm.decode_creation(request('  이름'))

    def test_store_survives_restart_and_roster_contains_created_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'characters.json'
            store = realm.CharacterStore(path)
            self.assertEqual(store.roster().expected_count, 0)
            uid, info, roster = store.create(realm.decode_creation(request()))
            self.assertEqual(uid, 1)
            self.assertEqual((info[1], info[3], info[5], info[11]),
                             ('로컬기사', 1, 0, 16))
            self.assertEqual((roster.expected_count, roster.row_count,
                              len(roster.frames)), (1, 1, 2))
            reloaded = realm.CharacterStore(path)
            self.assertEqual(reloaded.select('로컬기사')[0], 1)
            self.assertEqual(reloaded.roster().frames, roster.frames)
            with self.assertRaises(realm.Refused):
                reloaded.create(realm.decode_creation(request('로컬기사')))

    def test_create_ack_wire_shape(self):
        frame = realm.create_ack(0)
        self.assertEqual((int.from_bytes(frame[:2], 'little'),
                          int.from_bytes(frame[2:4], 'little'), len(frame)),
                         (8, 0x4e25, 8))
        self.assertEqual(frame[4:], b'\x08\x00\x00\x00')


if __name__ == '__main__':
    unittest.main()
