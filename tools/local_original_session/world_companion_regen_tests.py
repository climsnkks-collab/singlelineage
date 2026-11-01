"""Offline runtime/resource/wire checks; no game, sockets or user saves.

The fixture clock advances the real WorldRuntime, follower AI and production
companion save/party projection. This is a development integration check, not
a formal login/gameplay or native rendering PASS.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from tools.local_original_session.world_companion import CompanionStore
from tools.local_original_session import world_companion_magic_tests as magic_fixtures
from tools.local_original_session.world_feature_companion import CompanionParty, _companion_save


class RuntimeRecoveryTests(unittest.IsolatedAsyncioTestCase):
    setUp = magic_fixtures.MagicTests.setUp
    configure = magic_fixtures.MagicTests.configure

    def resources(self):
        self.record.level = 30
        self.record.hp, self.record.max_hp = 1, 200
        self.record.mp, self.record.max_mp = 0, 314
        self.magic.policy_for = lambda _: None
        self.record.learned_spells = ()
        self.owner_state.profile = replace(self.owner_state.profile, level=30, con=16, wis=18)
        self.owner_state.status_fields.update({10: 1, 11: 200, 12: 0, 13: 314})
        self.owner_state.hp = 1

    async def advance(self, first, last):
        for index in range(first, last + 1):
            self.fixture.now = 10 + index * self.view.runtime.tick_interval
            await self.view.runtime.tick_once(self.fixture.now)

    def party(self, store):
        ctx = SimpleNamespace(world=self.view, _companion_store=store,
            _companion_rows={1: dict(name='FixtureKnight'), 2: dict(name='FixtureMage')},
            _companion_inventory=None, _companion_windows={}, _companion_pet_modes={},
            _companion_views={})
        ctx._companion_party = CompanionParty(ctx)
        ctx._companion_save = lambda uid, receipt=None: _companion_save(ctx, uid, receipt)
        self.view.companion_save = ctx._companion_save
        self.addCleanup(setattr, self.view, 'companion_save', None)
        self.view.events.add('regen_test_party', 'tick', ctx._companion_party.sync, priority=100)
        ctx._companion_party.sync()
        self.view.drain(1)
        return ctx

    def statuses(self, wires):
        from tools.local_original_session.hunt_bot import fields, scalar
        return [values for wire in wires if int.from_bytes(wire[2:4], 'little') == 0x08a3
                for child in fields(wire[4:-2]).get(1, ())
                if scalar(values := fields(child), 1) == b'FixtureMage']

    async def test_lv30_wis18_mp314_runtime_matches_pc_and_saves_party_updates(self):
        from tools.local_original_session.hunt_bot import scalar
        self.resources()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'characters.json'
            store = CompanionStore(path)
            ctx = self.party(store)
            await self.advance(0, 106)  # 15.9 seconds: sixteen MP ticks not reached
            self.assertEqual((self.record.mp, self.owner_state.mp), (0, 0))
            first_hp = self.statuses(self.view.drain(1))
            self.assertTrue(first_hp)
            self.assertTrue(any(scalar(row, 3) > 0 for row in first_hp))
            await self.advance(107, 107)  # 16.05 seconds incl. ordinary polling jitter
            self.assertEqual((self.record.mp, self.owner_state.mp), (3, 3))
            self.assertEqual(self.record.hp, self.owner_state.hp)
            # 3/314 remains 0%; no MP percentage change is expected yet.
            self.assertEqual(ctx._companion_party.percent(self.record.mp, 314), 0)
            saved = CompanionStore(path)
            self.assertEqual((saved.payload['records'][0]['hp'], saved.payload['records'][0]['mp']),
                             (self.record.hp, 3))
            self.assertNotIn('regen_at', saved.payload['records'][0])
            self.view.drain(1)
            await self.advance(108, 214)  # 32.1 seconds, second +3 crosses 1%
            self.assertEqual((self.record.mp, self.owner_state.mp), (6, 6))
            self.assertEqual(self.record.hp, self.owner_state.hp)
            wires = self.view.drain(1)
            rows = self.statuses(wires)
            self.assertTrue(any(scalar(row, 4) == 1 for row in rows))
            self.assertTrue(any(scalar(row, 3) == 100 * self.record.hp // 200 for row in rows))
            self.assertFalse(any(int.from_bytes(wire[2:4], 'little') == 0x08a0 for wire in wires))
            # The existing 08A3 f3 consumer is also the native head HP bar path;
            # actual native rendering is intentionally outside this fixture.
            reopened = CompanionStore(path)
            self.assertEqual((reopened.payload['records'][0]['hp'], reopened.payload['records'][0]['mp']),
                             (self.record.hp, 6))
            self.assertIsNone(store.pending)
            self.assertEqual(self.view.companion_save_errors, [])

    async def test_paralysis_and_silence_do_not_stop_natural_recovery(self):
        self.resources()
        state = {'blocked': True, 'silenced': True}
        self.view.events.add('regen_test_status', 'actor_action_status',
                             lambda value, ref, now: dict(value, **state))
        await self.advance(0, 107)
        self.assertEqual((self.record.mp, self.owner_state.mp), (3, 3))
        self.assertEqual(self.record.hp, self.owner_state.hp)
        self.assertEqual(self.actor.action, 'PARALYZED')
        state['blocked'] = False
        await self.advance(108, 214)
        self.assertEqual((self.record.mp, self.owner_state.mp), (6, 6))
        self.assertFalse(any(event['spell'] != 'recover' for event in self.magic.events))

    async def test_non_spell_class_recovers_on_tick_without_ai_decision(self):
        self.resources()
        self.record.class_id = 2
        # Keep the next AI action far away: the ordinary tick still recovers.
        self.view.companion_ai._schedule(self.actor, 1000)
        await self.advance(0, 107)
        self.assertEqual((self.record.mp, self.owner_state.mp), (3, 3))
        self.assertEqual(self.record.hp, self.owner_state.hp)

    async def test_waiting_at_dead_owner_recovers_without_casting(self):
        self.resources()
        self.owner_state.hp, self.owner_state.dead = 0, True
        self.view.entities.kill(1)
        self.actor.owner_down = True
        await self.advance(0, 107)
        self.assertEqual(self.record.mp, 3)
        self.assertGreater(self.record.hp, 1)
        self.assertEqual(self.actor.action, 'HOLD')

    async def test_pet_recovery_remains_outside_ordinary_character_regen(self):
        self.resources()
        self.record.equipment['_pet'] = {}
        await self.advance(0, 107)
        self.assertEqual((self.record.hp, self.record.mp), (1, 0))

    def test_effective_wis_mp_options_blue_potion_and_clamp(self):
        self.resources()
        calculated = SimpleNamespace(attributes=SimpleNamespace(con=18, wis=15),
            hp_regen_bonus=2, mp_regen_bonus=4, weight=SimpleNamespace(gauge=240))
        self.view.companion_ai.inventory = SimpleNamespace(
            calculated=lambda uid: (calculated, ()), blue_until={2: 100})
        self.record.equipment.update(food=0, weight240=240)
        self.magic.regen(self.actor, 10)
        self.actor.regen_points = 60
        self.magic.regen(self.actor, 11)
        policy = self.view.combat.regen
        self.assertEqual(self.record.mp, policy.mp_amount(15) + 4 + max(15, 11) - 5)
        self.record.mp = 313
        self.actor.regen_points = 60
        self.magic.regen(self.actor, 12)
        self.assertEqual(self.record.mp, 314)
        self.assertEqual(self.record.hp, 1)
        self.magic.regen(self.actor, 13)
        self.assertEqual(self.record.hp, 1 + policy.hp_amount(18) + 2)


if __name__ == '__main__':
    unittest.main()
