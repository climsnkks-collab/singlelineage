"""Development relocation/re-entry checks; socket scenarios live in hunt_bot_companion."""
from dataclasses import asdict
from types import MethodType, SimpleNamespace
import unittest

from tools.local_original_session import movement
from tools.local_original_session import world_companion_integration_tests as fixtures
from tools.local_original_session.world_feature_companion import (
    _companion_restore, _companion_show_corpses, _companion_revive)
from tools.local_original_session.world_core_maps import _world_relocate_locked
from tools.local_original_session import world_registry, world_feature_companion
from tools.local_original_session.world_maps import MapDestination


class CompanionMovementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view, self.record, self.actor = self.fixture.view, self.fixture.record, self.fixture.actor
        self.view.terrain.can_stand = lambda *_: True
        self.view.drain(1)
        self.writer, self.game = object(), object()
        self.position = movement.Position(1, 'FixtureKnight', 0, 100, 100)
        self.service = SimpleNamespace(snapshot=lambda: self.position, relocate=self.relocate)
        self.ctx = SimpleNamespace(world=self.view, _world=self.view, _world_map_exp=0,
            _world_map_transitions=0, owner_current=lambda *_: True,
            _companion_save=lambda *_: None, _companion_revive_exp=False,
            _companion_enabled=True, _companion_rows={self.record.character_id: {}},
            realm=SimpleNamespace(service=lambda _: self.service, serves_map=lambda _: True,
                registry=SimpleNamespace(resolve=lambda _: self.game), _world_frames={},
                _frames_for=lambda *a, **k: (b'\x06\x00\x95\x4e\0\0',
                    b'\x06\x00\x38\x4e\0\0', b'\x06\x00\x96\x4e\0\0')))
        self.ctx._world_registry = world_registry.build_registry((world_feature_companion,))
        for hook in ('relocate_keeps_self', 'before_relocate', 'after_relocate'):
            for name in self.ctx._world_registry.hooks[hook]:
                setattr(self.ctx, name, MethodType(self.ctx._world_registry.methods[name], self.ctx))
        self.ctx.run_sync_hooks = lambda name, *args: world_registry.run_sync_hooks(name, self.ctx, *args)
        self.ctx.chain_sync_hooks = lambda name, *args: world_registry.chain_sync_hooks(name, self.ctx, *args)
        self.ctx.collect_sync_hooks = lambda name, *args: world_registry.collect_sync_hooks(name, self.ctx, *args)
        self.row = {'operation_lock': SimpleNamespace(locked=lambda: True)}

    def relocate(self, position):
        self.position = position

    def move(self, map_id=0):
        return _world_relocate_locked(self.ctx, self.writer, self.row, self.game,
                                     MapDestination(map_id, 200, 200, 4))

    def decoded(self, wires, opcode, field, value):
        return self.fixture.decoded(wires, opcode, field, value)

    def test_living_same_map_removal_correction_spawn_and_old_target_cleanup(self):
        old, handle = self.actor.ref, self.actor.handle
        monster, _ = self.fixture.monster()
        self.actor.target = monster.ref
        self.view.ai.on_hit(monster.uid, old.uid, self.fixture.now)
        self.actor.next_attack_at = 25
        wires = self.move()
        actor = self.view.companions.active[2]
        entity = self.view.entities.resolve(actor.ref)
        self.assertTrue(handle.cancelled)
        self.assertIsNone(self.view.entities.get(old.uid))
        self.assertIsNone(actor.target)
        self.assertEqual(actor.next_attack_at, 25)
        self.assertFalse(any(b.target == old.uid for b in self.view.ai.brains.values()))
        self.assertFalse(self.view.runtime.scheduler._by_owner.get(old.uid))
        self.assertEqual((entity.map_id, abs(entity.x - 200) <= 1, abs(entity.y - 200) <= 1),
                         (0, True, True))
        removal = self.decoded(wires, 0x4e40, 1, old.uid)
        spawn = self.decoded(wires, 0x4e96, 2, actor.ref.uid)
        self.assertEqual((len(removal), len(spawn)), (1, 1))
        opcodes = [int.from_bytes(w[2:4], 'little') for w in wires]
        self.assertLess(opcodes.index(0x4e40), opcodes.index(0x4ee0))
        self.assertLess(opcodes.index(0x4ee0), opcodes.index(0x4e96))

    def test_corpse_walking_leaves_position_and_reentry_republishes_death(self):
        self.view.companions.die(2)
        corpse = self.view.entities.get(self.actor.ref.uid)
        pose = corpse.map_id, corpse.x, corpse.y
        self.view.update_pc_and_drain(1, 0, 150, 100)
        _companion_show_corpses(self.ctx)
        self.assertEqual((corpse.map_id, corpse.x, corpse.y), pose)
        wires = self.view.update_pc_and_drain(1, 0, 100, 100)
        _companion_show_corpses(self.ctx)
        wires += self.view.drain(1)
        self.assertEqual(len(self.decoded(wires, 0x4e96, 2, corpse.uid)), 1)
        self.assertEqual(len(self.decoded(wires, 0x4e39, 1, corpse.uid)), 1)
        self.assertEqual((self.record.alive, self.record.hp, self.actor.handle), (False, 0, None))

    def test_dead_same_map_teleport_recreates_corpse_then_accepts_scroll_effect(self):
        self.view.companions.die(2)
        before = asdict(self.record)
        wires = self.move()
        actor = self.view.companions.active[2]
        self.assertEqual(asdict(self.record), before)
        self.assertIsNone(actor.handle)
        self.assertIsNone(self.view.entities.resolve(actor.ref))
        opcodes = [int.from_bytes(w[2:4], 'little') for w in wires]
        self.assertLess(opcodes.index(0x4ee0), opcodes.index(0x4e96))
        self.assertLess(opcodes.index(0x4e96), opcodes.index(0x4e39))
        _companion_revive(self.ctx, 1, self.record)
        self.assertTrue(self.record.alive)
        self.assertIsNotNone(actor.handle)

    def test_mapexp2_same_map_companion_travel_keeps_correction_sequence(self):
        self.ctx._world_map_exp = 2
        wires = self.move()
        opcodes = [int.from_bytes(w[2:4], 'little') for w in wires]
        self.assertIn(0x4ee0, opcodes)
        self.assertNotIn(0x4e95, opcodes)
        self.assertLess(opcodes.index(0x4e40), opcodes.index(0x4ee0))
        self.assertLess(opcodes.index(0x4ee0), opcodes.index(0x4e96))

    def test_cross_map_both_lives_follow_and_dead_life_is_unchanged(self):
        self.ctx._world_map_exp = 2
        for dead in (False, True):
            with self.subTest(dead=dead):
                if dead:
                    self.view.companions.die(2)
                before = asdict(self.record)
                old = self.view.companions.active[2].ref
                self.move(1 if not dead else 2)
                actor = self.view.companions.active[2]
                entity = self.view.entities.get(actor.ref.uid)
                self.assertEqual(entity.map_id, 1 if not dead else 2)
                self.assertIsNone(self.view.entities.get(old.uid))
                self.assertEqual(asdict(self.record), before)
                self.view.companion_ai.sync(self.fixture.now)
                self.assertIs(self.view.companions.active[2], actor)

    def test_failed_map_publication_does_not_dismiss_member(self):
        self.ctx._world_map_exp = 2
        def fail(*args, **kwargs):
            raise ValueError('UNSUPPORTED_SOURCE_SCALAR_LAYOUT')
        self.ctx.realm._frames_for = fail
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_SOURCE_SCALAR_LAYOUT'):
            self.move(1)
        self.assertIs(self.view.companions.active[2], self.actor)
        self.assertIsNotNone(self.actor.handle)
        self.assertIsNotNone(self.view.entities.resolve(self.actor.ref))

    def test_restore_dead_without_allocating_live_ai_or_healing(self):
        self.view.companions.die(2)
        self.view.companions.dismiss(2)
        self.view.drain(1)
        before = asdict(self.record)
        actor = _companion_restore(self.ctx, 1, 2)
        self.assertEqual(asdict(self.record), before)
        self.assertEqual((actor.action, actor.target, actor.handle), ('DEAD', None, None))
        wires = self.view.drain(1)
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in wires], [0x4e96, 0x4e39])
        with self.assertRaisesRegex(ValueError, 'RESURRECTION_REQUIRED'):
            self.view.companions.summon(2, 1, 0, 101, 100)


if __name__ == '__main__':
    unittest.main()
