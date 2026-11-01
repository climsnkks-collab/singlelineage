"""Offline party/head MP wire checks; no game, bot, sockets or user saves.

Native 08A3 f4 fans out to party and PlayerActorHud MP setters. These tests
verify that input only, not native visibility or rendered pixels.
"""
import unittest

from tools.local_original_session.hunt_bot import fields, scalar
from tools.local_original_session import world_companion_rules_tests as rules
from tools.local_original_session import world_companion_mana_tests as mana


def statuses(wires):
    return [fields(child) for wire in wires
            if int.from_bytes(wire[2:4], 'little') == 0x08a3
            for child in fields(wire[4:-2]).get(1, ())]


class MpDisplayTests(unittest.TestCase):
    consume = staticmethod(rules.PartyProjectionTests.consume)
    projection = rules.PartyProjectionTests.projection
    resource_projection = rules.PartyProjectionTests.resource_projection
    consume_resource_update = rules.PartyProjectionTests.consume_resource_update

    def test_initial_owner_and_companion_use_same_list_then_status_mp_fields(self):
        fixture, ctx, party, _ = self.projection()
        state, record = fixture.view.combat.pcs[1], fixture.record
        state.status_fields.update({12: 37, 13: 100})
        record.mp, record.max_mp = 37, 100
        party.reset(1)
        party.sync()
        wires = fixture.view.drain(1)
        opcodes = [int.from_bytes(wire[2:4], 'little') for wire in wires]
        self.assertEqual(opcodes[-2:], [0x08a0, 0x08a3])
        members = [fields(child) for child in fields(wires[-2][4:-2])[2]]
        updates = statuses(wires)
        self.assertEqual([scalar(row, 7) for row in members], [37, 37])
        self.assertEqual([scalar(row, 4) for row in updates], [37, 37])
        self.assertEqual([scalar(row, 1) for row in members],
                         [b'FixtureKnight', b'FixtureMage'])
        self.assertEqual([scalar(row, 3) for row in members],
                         [1, fixture.actor.ref.uid])
        for row in updates:
            self.assertIn(3, row)  # HP input to party/head HP
            self.assertIn(4, row)  # MP input to party/head MP
            self.assertEqual(scalar(row, 10), 0)  # same existing LOCAL key

    def test_each_current_and_max_mp_change_publishes_even_same_percent_for_both(self):
        fixture, ctx, party, _ = self.projection()
        view, record, state = fixture.view, fixture.record, fixture.view.combat.pcs[1]
        record.mp, record.max_mp = 100, 1000
        state.status_fields.update({12: 100, 13: 1000})
        party.sync()
        view.drain(1)
        for current, maximum in ((101, 1000), (101, 1001), (100, 1001), (0, 1001)):
            with self.subTest(current=current, maximum=maximum):
                record.mp, record.max_mp = current, maximum
                state.status_fields.update({12: current, 13: maximum})
                party.sync()
                wires = view.drain(1)
                self.assertEqual([int.from_bytes(w[2:4], 'little') for w in wires], [0x08a3])
                updates = statuses(wires)
                self.assertEqual([scalar(row, 1) for row in updates],
                                 [b'FixtureKnight', b'FixtureMage'])
                self.assertEqual([scalar(row, 4) for row in updates],
                                 [100 * current // maximum] * 2)
                self.assertTrue(all(4 in row for row in updates))  # explicit zero too
                party.sync()
                self.assertEqual(view.drain(1), [])

    def test_actual_cast_and_recovery_publish_mp_with_unchanged_hp_and_percent(self):
        from pathlib import Path
        import json
        from tools.local_original_session.world_feature_companion import CompanionMagic
        from tools.local_original_session import ats_config_codec as codec

        fixture, ctx, party, rows = self.resource_projection()
        view, record, actor = fixture.view, fixture.record, fixture.actor
        root = Path(__file__).parent / 'data' / 'companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        magic = CompanionMagic(view, read('mage_spells'), read('mage_growth'), read('ai_policy'),
                               {2: (8, 7, 16, 18, 8, 18)}, display=False)
        record.hp = record.max_hp = 200
        record.mp, record.max_mp, record.level = 104, 1000, 5
        record.learned_spells = (2,)
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(buff_spells=(2,))),
                                        {2: 'shield'})
        magic.policy_for = lambda _: policy
        party.sync()
        view.drain(1)
        entity = view.entities.resolve(actor.ref)
        self.assertTrue(magic.cast(actor, entity, entity, 'shield', fixture.now))
        self.assertLess(record.mp, 104)
        self.assertEqual(party.percent(record.mp, 1000), 10)
        self.consume_resource_update(fixture, rows)
        # A real +3 recovery stays in the same integer percentage bucket.
        before = record.mp
        actor.regen_at = fixture.now
        actor.regen_points = magic.growth['mp_regeneration']['timing']['threshold_points']
        magic.regen(actor, fixture.now)
        self.assertGreater(record.mp, before)
        self.assertEqual(party.percent(before, 1000), party.percent(record.mp, 1000))
        self.assertEqual(record.hp, 200)
        self.consume_resource_update(fixture, rows)

    def test_actual_absorption_publishes_explicit_zero_percent(self):
        fixture = mana.CompanionManaTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.record.max_mp = 1000
        fixture.ctx._companion_party.sync()
        fixture.view.drain(1)
        fixture.strike()
        self.assertEqual((fixture.record.mp, fixture.saved_mp(), fixture.remaining()), (3, 3, 97))
        updates = statuses(fixture.view.drain(1))
        self.assertEqual(len(updates), 1)
        self.assertEqual(scalar(updates[0], 1), b'FixtureMage')
        self.assertIn(4, updates[0])
        self.assertEqual(scalar(updates[0], 4), 0)


if __name__ == '__main__':
    unittest.main()
