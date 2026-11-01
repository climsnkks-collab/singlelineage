"""Pure LOCAL world 4E96 classification regressions; no sockets or game."""
import types
import unittest

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session.game_data import load_m1


class NamedGroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_m1()

    def setUp(self):
        self.bot = hb.HuntBot(types.SimpleNamespace())
        self.bot.data = self.data
        self.bot.self_uid = 1

    def appearance(self, uid, *, name, count, template=0, player=False):
        # Same discriminating fields as world_visibility.ground_frame and
        # MONSTER_BASE_FIELDS; template0 alone is ambiguous with actual Orc0.
        body = (hb.uint(1, hb.pack((32584, 32888))) + hb.uint(2, uid)
                + hb.uint(3, 22) + hb.uint(7, count) + hb.pb.encode_bytes(9, name)
                + hb.uint(16, int(player)) + hb.uint(39, template))
        wire = (len(body) + 6).to_bytes(2, 'little') + b'\x96\x4e' + body + b'\0\0'
        self.bot.apply(hb.Received(1, 0.0, 0x4e96, hb.fields(wire[4:-2]), wire))

    def test_named_ground_template_zero_is_loot_not_orc(self):
        self.assertIn(0, self.data.monsters)  # the collision that caused the stall
        self.appearance(100, name='아데나'.encode(), count=7)
        self.assertEqual(self.bot.ground[100]['count'], 7)
        self.assertIn(100, self.bot.ground_seen)
        self.assertNotIn(100, self.bot.actors)

    def test_actual_monster_zero_stays_attackable_and_separate_from_named_loot(self):
        self.appearance(100, name='아데나'.encode(), count=7)
        self.appearance(200, name=self.data.monsters[0].name_ko.encode(), count=0)
        self.assertEqual(self.bot.actors[200]['template'], 0)
        self.assertTrue(self.bot.actors[200]['alive'])
        self.assertNotIn(200, self.bot.ground)
        self.assertEqual(set(self.bot.actors), {200})
        self.assertEqual(set(self.bot.ground), {100})

    def test_legacy_empty_ground_name_stays_loot(self):
        self.appearance(100, name=b'', count=1)
        self.assertEqual(self.bot.ground[100]['count'], 1)
        self.assertNotIn(100, self.bot.actors)

    def test_self_and_player_branch_do_not_become_loot(self):
        self.appearance(1, name=b'self', count=3)
        self.assertEqual(self.bot.position, (32584, 32888))
        self.appearance(300, name=b'player', count=3, player=True)
        self.assertFalse(self.bot.ground)
        self.assertFalse(self.bot.actors)


if __name__ == '__main__':
    unittest.main()
