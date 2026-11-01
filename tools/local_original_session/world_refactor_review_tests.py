"""Regressions for the refactor code review (leave cleanup, pet relocation, report).

Pure fixtures only; no broker socket, client, user save or formal gameplay PASS.
Run: python -X utf8 -B -m unittest tools.local_original_session.world_refactor_review_tests
"""
from __future__ import annotations

import dataclasses
import random
from types import SimpleNamespace as NS
import unittest

from tools.local_original_session import world_bridge, world_core_session, world_handlers
from tools.local_original_session.world_bridge import Context
from tools.local_original_session.world_extensions import WorldEvents


class _Broker(NS):
    """Plain attribute owner; Context forwards reads/writes like PersistentBroker."""


def _leave_owner(writer, *, save_error=None, before_error=None, dead=True):
    reached = []
    owner = _Broker(_world_pcs={id(writer): (writer, 7)}, _world_events={7: object()},
                    _claims={}, _world_names={7: 'Knight'}, _world_respawn={},
                    _world_progress_errors=[], _world_hook_errors=[], failures=[])
    owner._world_registry = world_handlers.build_registry(
        world_handlers.CORE_MODULES + ('world_feature_items',))

    def save(uid):
        reached.append(('save', uid))
        if save_error is not None:
            raise save_error

    def before(writer_, uid):
        reached.append(('before_leave', uid))
        if before_error is not None:
            raise before_error

    async def dispatch_now(function, *args):
        return function(*args)

    owner._world_save_progress = save
    owner._world_items_before_leave = before
    owner._world_consumable_left = lambda writer_: reached.append(('after_leave',))
    owner._world_items_report = lambda result: None
    owner._world = NS(runtime=NS(dispatch_now=dispatch_now),
                      leave_pc=lambda uid: reached.append(('leave_pc', uid)) or dead)
    owner._fail = owner.failures.append
    return owner, reached


class LeaveCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_failure_still_unbinds_records_death_and_runs_after_leave(self):
        writer = object()
        owner, reached = _leave_owner(writer, save_error=OSError('disk'))
        with self.assertRaises(OSError):
            await world_core_session._world_leave(Context(owner), writer)
        self.assertEqual(owner._world_pcs, {})
        self.assertEqual(owner._world_events, {})
        self.assertEqual(owner._world_respawn, {7: 'Knight'})
        self.assertIn(('leave_pc', 7), reached)
        self.assertEqual(reached[-1], ('after_leave',))
        self.assertNotIn(('before_leave', 7), reached)  # the failed save stays a failure

    async def test_bridge_leave_reports_failure_and_commits_dead_respawn(self):
        writer = object()
        owner, _ = _leave_owner(writer, save_error=OSError('disk'))
        owner._world_leave = lambda w: world_core_session._world_leave(Context(owner), w)
        committed = []
        owner._world_commit_respawn = committed.append
        await world_bridge.leave(owner, writer)
        self.assertEqual(owner.failures, ['WORLD_PERSIST_FAILED'])
        self.assertEqual(committed, [7])

    async def test_noncritical_items_before_leave_failure_appears_in_report(self):
        writer = object()
        owner, reached = _leave_owner(writer, before_error=KeyError('poly'))
        await world_core_session._world_leave(Context(owner), writer)
        self.assertEqual(owner._world_pcs, {})
        self.assertEqual(reached[-1], ('after_leave',))
        self.assertEqual(owner.failures, [])
        result = {}
        _report_owner(owner)
        world_bridge.report(owner, result)
        self.assertIn(dict(feature='tools.local_original_session.world_feature_items',
                           hook='before_leave', method='_world_items_before_leave',
                           error='KeyError'), result['world']['hook_errors'])


def _report_owner(owner):
    events, combat_events = WorldEvents(), WorldEvents()
    owner._world = NS(combat=NS(kills=[], events=combat_events), ground={}, reward_errors=[],
                      events=events)
    owner.__dict__.update(_world_pickups=0, _world_pickup_errors=[], _world_respawn_errors=[],
                          _world_handler_errors=[], _world_map_exp=0, _world_map_transitions=0)
    owner._world_respawn = getattr(owner, '_world_respawn', {})
    owner._world_progress_errors = getattr(owner, '_world_progress_errors', [])
    owner._world_hook_errors = getattr(owner, '_world_hook_errors', [])
    return events, combat_events


class ReportTests(unittest.TestCase):
    def test_isolated_world_event_failures_are_reported_as_hook_errors(self):
        owner = _Broker(_world_registry=world_handlers.build_registry(()))
        events, combat_events = _report_owner(owner)
        def fail(*_):
            raise RuntimeError('observer')
        events.add('followers', 'tick', fail, isolate=True)
        combat_events.add('followers', 'pc_hit', fail, isolate=True)
        with self.assertLogs('tools.local_original_session.world_extensions', level='ERROR'):
            events.emit('tick', 1.0)
            combat_events.emit('pc_hit', 1)
        result = {}
        world_bridge.report(owner, result)
        self.assertEqual(result['world']['hook_errors'], [
            dict(feature='followers', hook='tick', method='world_event', error='RuntimeError'),
            dict(feature='followers', hook='pc_hit', method='world_event', error='RuntimeError')])

    def test_no_failures_keep_report_without_hook_errors(self):
        owner = _Broker(_world_registry=world_handlers.build_registry(()))
        _report_owner(owner)
        result = {}
        world_bridge.report(owner, result)
        self.assertNotIn('hook_errors', result['world'])


class _OpenTerrain:
    def passable(self, *_):
        return True

    def can_step(self, *_):
        return True


class PetRelocationTests(unittest.TestCase):
    def setUp(self):
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_companion import CompanionRecord
        from tools.local_original_session.world_combat import PcProfile, ATHAME
        from tools.local_original_session.world_interest_spawn import InterestSpawner
        from tools.local_original_session.world_runtime import WorldRuntime
        from tools.local_original_session.world_visibility import WorldView
        from tools.local_original_session.world_companion_runtime import install_companion_runtime
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        self.now = 10.0
        data = dataclasses.replace(load_m1(), spawns=())
        runtime = WorldRuntime(clock=lambda: self.now)
        spawner = InterestSpawner(runtime.entities, data, passable=lambda *_: True,
                                  rng=random.Random(7))
        self.view = WorldView(runtime, spawner, _OpenTerrain(), data=data, rng=random.Random(7))
        install_companion_runtime(self.view)
        self.view.update_pc(1, 0, 100, 100)
        status = dict(actor_hook.profiles()[0].fields)
        status.update({1: 1, 2: 1, 10: 100, 11: 100, 12: 20, 13: 20, 18: 500})
        self.view.bind_pc(1, PcProfile(1, 1, 0, 18, 13, con=16, weapon=ATHAME), status)
        self.record = CompanionRecord(2, 1, 'development-fixture', hp=12, max_hp=12, mp=8,
                                      max_mp=8, movement_mode='FOLLOW', combat_mode='PASSIVE')
        self.view.companions.register(self.record, roster={
            1: dict(account_id='development-fixture', class_id=1),
            2: dict(account_id='development-fixture', class_id=3)})
        self.view.companion_profiles[2] = PcProfile(1, 3, 0, 8, 7, con=16, wis=18)
        self.view.companion_looks[2] = dict(name='FixturePet', owner_name='FixtureKnight',
                                           sprite_id=734, stance=50)
        self.view.summon_companion(2, 1)
        self.saves = []
        self.view.companion_save = lambda uid, receipt=None: self.saves.append(uid)
        self.ctx = NS(world=self.view, _pet_system=NS(
            records={2: self.record},
            summon=lambda *_: self.fail('living pet must use summon_companion')))

    def tearDown(self):
        self.view.close()

    def test_living_pet_restores_with_owner_heading_refresh_and_save(self):
        from tools.local_original_session import world_feature_pet as pet
        transit = {}
        pet._pet_before_relocate(self.ctx, 1, transit)
        self.assertEqual(self.view.companions.active, {})
        self.view.drain(1)
        self.saves.clear()
        self.view.update_pc(1, 0, 130, 130)
        self.view.entities.move(1, 0, 130, 130, 5)
        self.view.drain(1)
        frames = pet._pet_after_relocate(self.ctx, 1, transit)
        actor = self.view.companions.active[2]
        entity = self.view.entities.get(actor.ref.uid)
        self.assertEqual(entity.heading, 5)
        self.assertEqual(max(abs(entity.x - 130), abs(entity.y - 130)), 1)
        self.assertEqual(self.saves, [1])
        self.assertIn(entity.uid, self.view.visibility.known[1])
        opcodes = [int.from_bytes(wire[2:4], 'little') for wire in frames]
        self.assertIn(0x4f1a, opcodes)  # pet HP bar after the refreshed spawn


if __name__ == '__main__':
    unittest.main()
