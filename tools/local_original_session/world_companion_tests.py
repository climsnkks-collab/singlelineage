"""Pure companion state/temporary-file checks; no game, ports or broker."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session.world_companion import (
    CompanionRecord, WorldCompanions, award_split_exp, split_exp,
)
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_scheduler import Scheduler


ROSTER = {11: {'account_id': 'account-a', 'class_id': 0},
          22: {'account_id': 'account-a', 'class_id': 3},
          23: {'account_id': 'account-a', 'class_id': 3},
          31: {'account_id': 'account-b', 'class_id': 0},
          32: {'account_id': 'account-b', 'class_id': 3}}


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.entities = EntityRegistry()
        self.scheduler = Scheduler(clock=lambda: self.now, is_current=self.entities.is_current)
        self.released = []
        self.world = WorldCompanions(self.entities, self.scheduler,
                                    release_target=lambda uid, now: self.released.append((uid, now)))
        self.owner = self.entities.add(Kind.PC, 0, 10, 10, uid=9001)
        self.record = self.world.register(self.member(), roster=ROSTER)

    def member(self, **changes):
        values = dict(character_id=22, owner_character_id=11, account_id='account-a',
                      hp=30, max_hp=40, mp=15, max_mp=20, exp=7, exp_half=1,
                      equipment={'weapon': {'uid': 401, 'template_id': 7}},
                      learned_spells=(0, 1, 2), mp_reserve=5)
        values.update(changes)
        return CompanionRecord(**values)

    def summon(self):
        return self.world.summon(22, self.owner.uid, 0, 11, 10)

    def test_unique_actor_lifetime_and_shared_hp_ledger(self):
        actor = self.summon()
        self.assertIs(actor.record, self.record)
        self.assertEqual(self.entities.resolve(actor.ref).kind, Kind.NPC)
        self.assertEqual(actor.owner_ref.uid, 9001)
        self.assertNotEqual(actor.owner_ref.uid, self.record.owner_character_id)
        with self.assertRaisesRegex(ValueError, 'ALREADY_ACTIVE'):
            self.summon()
        actor.record.hp -= 4
        self.assertEqual(self.record.hp, 26)
        old_ref = actor.ref
        self.world.dismiss(22, self.now)
        self.assertIsNone(self.entities.resolve(old_ref))
        self.assertIsNone(self.world.get_actor(old_ref.uid))
        new_actor = self.summon()
        self.assertNotEqual(new_actor.ref.uid, old_ref.uid)
        self.assertEqual(new_actor.record.hp, 26)
        self.assertEqual(self.released, [(old_ref.uid, self.now)])

    def test_death_invalidates_ref_releases_monsters_and_cancels_schedules(self):
        actor = self.summon()
        called = []
        actor.target = self.owner.ref
        actor.handle = self.scheduler.schedule(11, actor.ref, 'companion-ai', called.append)
        self.scheduler.schedule(11, actor.ref, 'companion-cast', called.append)
        old_ref = actor.ref
        self.world.die(22, 10)
        self.assertIsNone(self.entities.resolve(old_ref))
        self.assertEqual(self.entities.get(old_ref.uid).generation, old_ref.generation + 1)
        self.assertFalse(self.record.alive)
        self.assertEqual(self.record.hp, 0)
        self.assertEqual(actor.action, 'DEAD')
        self.assertIsNone(actor.target)
        self.assertIsNone(actor.handle)
        self.assertFalse(self.world.can_be_attacked(actor.ref.uid))
        # Even an external late producer cannot revive the stale generation.
        self.scheduler.schedule(11, old_ref, 'stale-companion-ai', called.append)
        self.assertEqual(self.scheduler.run_due(20), 0)
        self.assertEqual(called, [])
        self.world.die(22, 20)  # idempotent death never increments generation again
        self.assertEqual(self.released, [(old_ref.uid, 10)])
        self.world.dismiss(22, 20)
        self.assertIsNone(self.entities.get(old_ref.uid))
        self.assertEqual(self.released[-1], (old_ref.uid, 20))
        with self.assertRaisesRegex(ValueError, 'RESURRECTION_REQUIRED'):
            self.summon()

    def test_release_callback_error_does_not_leave_live_or_scheduled_actor(self):
        actor = self.summon()
        self.scheduler.schedule(11, actor.ref, 'companion-ai', lambda now: None)
        self.world.release_target = lambda *args: (_ for _ in ()).throw(RuntimeError('release failed'))
        with self.assertRaisesRegex(RuntimeError, 'release failed'):
            self.world.die(22, 10)
        self.assertFalse(self.record.alive)
        self.assertIsNone(self.entities.resolve(actor.ref))
        self.assertEqual(len(self.scheduler), 0)
        with self.assertRaisesRegex(RuntimeError, 'release failed'):
            self.world.dismiss(22, 10)
        self.assertNotIn(22, self.world.active)
        self.assertIsNone(self.entities.get(actor.ref.uid))

    def test_allies_and_valid_owner_generation(self):
        actor = self.summon()
        second = self.world.register(self.member(character_id=23), roster=ROSTER)
        companion = self.world.summon(second.character_id, self.owner.uid, 0, 12, 10)
        stranger = self.entities.add(Kind.PC, 0, 9, 9)
        monster = self.entities.add(Kind.NPC, 0, 8, 8)
        self.assertTrue(self.world.can_be_attacked(actor.ref.uid))
        self.assertTrue(self.world.are_allies(self.owner.uid, actor.ref.uid))
        self.assertTrue(self.world.are_allies(actor.ref.uid, self.owner.uid))
        self.assertTrue(self.world.are_allies(actor.ref.uid, companion.ref.uid))
        self.assertFalse(self.world.are_allies(stranger.uid, actor.ref.uid))
        self.assertFalse(self.world.are_allies(monster.uid, actor.ref.uid))
        self.entities.deactivate_pc(self.owner.uid)
        self.assertFalse(self.world.can_be_attacked(actor.ref.uid))
        self.entities.activate_pc(self.owner.uid, 0, 10, 10)
        self.assertFalse(self.world.can_be_attacked(actor.ref.uid))  # old owner generation

    def test_registration_rejects_foreign_nonmage_and_missing_saved_member(self):
        for changes, message in (({'character_id': 32}, 'SAME_ACCOUNT'),
                                 ({'character_id': 11, 'owner_character_id': 22}, 'SAVED_MAGE'),
                                 ({'character_id': 99}, 'SAVED_CHARACTER'),
                                 ({'owner_character_id': 22}, 'OWNER_CANNOT')):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, message):
                self.world.register(self.member(**changes), roster=ROSTER)
        self.assertEqual(tuple(self.world.records), (22,))

    def test_summon_rejects_dead_or_wrong_map_owner(self):
        with self.assertRaisesRegex(ValueError, 'OWNER_MAP_MISMATCH'):
            self.world.summon(22, self.owner.uid, 1, 10, 10)
        monster = self.entities.add(Kind.NPC, 0, 10, 9)
        with self.assertRaisesRegex(ValueError, 'LIVE_OWNER'):
            self.world.summon(22, monster.uid, 0, 10, 10)
        self.entities.kill(self.owner.uid)
        with self.assertRaisesRegex(ValueError, 'LIVE_OWNER'):
            self.summon()

    def test_commands_validate_before_mutation_cancel_target_and_wait_for_ai_wake(self):
        actor = self.summon()
        actor.target = self.owner.ref
        actor.handle = self.scheduler.schedule(11, actor.ref, 'companion-ai', lambda now: None)
        self.world.set_commands(22, movement_mode='HOLD', combat_mode='PASSIVE', mp_reserve=9)
        self.assertEqual((self.record.command, self.record.mode, self.record.mp_reserve),
                         ('HOLD', 'PASSIVE', 9))
        self.assertIsNone(actor.target)
        self.assertIsNone(actor.handle)
        self.assertEqual(len(self.scheduler), 0)
        with self.assertRaisesRegex(ValueError, 'INVALID_COMBAT_MODE'):
            self.world.set_commands(22, movement_mode='FOLLOW', combat_mode='bogus')
        self.assertEqual(self.record.movement_mode, 'HOLD')

    def test_each_beneficiary_accumulates_own_half_unit(self):
        self.assertEqual(split_exp(5, 0, 1), (2, 3, 1, 0))
        self.assertEqual(split_exp(5, 1, 0), (3, 2, 0, 1))
        owner = SimpleNamespace(exp=10, exp_half=0)
        self.record.exp, self.record.exp_half = 20, 0
        for _ in range(2):
            award_split_exp(5, owner, self.record)
        self.assertEqual((owner.exp, self.record.exp, owner.exp_half, self.record.exp_half),
                         (15, 25, 0, 0))
        self.assertEqual(split_exp(0, 1, 0), (0, 0, 1, 0))

    def test_command_toggles_preserve_movement_attack_and_cast_cooldowns(self):
        actor = self.summon()
        self.assertEqual((actor.next_move_at, actor.next_attack_at, actor.next_cast_at),
                         (10, 10, 10))
        actor.next_move_at, actor.next_attack_at, actor.next_cast_at = 11, 12, 13
        for movement, combat in (('HOLD', 'PASSIVE'), ('FOLLOW', 'ASSIST')):
            self.world.set_commands(22, movement_mode=movement, combat_mode=combat, now=10.5)
            self.assertEqual((actor.next_move_at, actor.next_attack_at, actor.next_cast_at),
                             (11, 12, 13))

    def test_invalid_xp_never_mutates_either_recipient(self):
        owner = SimpleNamespace(exp=10, exp_half=0)
        for bad in (-1, 1.5, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                award_split_exp(bad, owner, self.record)
        for half in (-1, 2, True, 0.5):
            with self.subTest(half=half), self.assertRaises(ValueError):
                split_exp(3, half, 0)
        self.record.exp_half = 2
        with self.assertRaises(ValueError):
            award_split_exp(3, owner, self.record)
        self.assertEqual((owner.exp, owner.exp_half, self.record.exp), (10, 0, 7))

    def test_save_restore_persistent_fields_without_runtime_or_free_resurrection(self):
        actor = self.summon()
        actor.target = self.owner.ref
        actor.next_attack_at = 91.0
        actor.handle = self.scheduler.schedule(11, actor.ref, 'companion-ai', lambda now: None)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'companion.json'
            self.assertFalse(path.exists())  # no implicit writes on mutations
            self.world.save(path, owner_character_id=11)
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(set(saved), {'schema', 'owner_character_id', 'records'})
            self.assertEqual(set(saved['records'][0]), set(CompanionRecord.__dataclass_fields__))
            restored = WorldCompanions(self.entities, self.scheduler)
            loaded, = restored.load(path, roster=ROSTER)
            self.assertEqual(asdict(loaded), asdict(self.record))
            self.assertEqual(restored.active, {})
            self.world.die(22, 10)
            self.world.save(path, owner_character_id=11)
            restored.load(path, roster=ROSTER)
            self.assertFalse(restored.records[22].alive)
            self.assertEqual(restored.records[22].hp, 0)
            with self.assertRaisesRegex(ValueError, 'RESURRECTION_REQUIRED'):
                restored.summon(22, self.owner.uid, 0, 11, 10)

    def test_atomic_replacement_failure_preserves_previous_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'companion.json'
            self.world.save(path, owner_character_id=11)
            previous = path.read_bytes()
            self.record.hp -= 3
            with patch('tools.local_original_session.world_companion.os.replace', side_effect=OSError('disk')):
                with self.assertRaises(OSError):
                    self.world.save(path, owner_character_id=11)
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['companion.json'])

    def test_load_validation_is_atomic_and_active_restore_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'companion.json'
            self.world.save(path, owner_character_id=11)
            payload = json.loads(path.read_text(encoding='utf-8'))
            payload['records'].append(dict(payload['records'][0], character_id=32))
            path.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SAME_ACCOUNT'):
                self.world.load(path, roster=ROSTER)
            self.assertIs(self.world.records[22], self.record)
            self.world.save(path, owner_character_id=11)
            self.summon()
            with self.assertRaisesRegex(ValueError, 'DISMISS_BEFORE_LOAD'):
                self.world.load(path, roster=ROSTER)
            self.assertIs(self.world.records[22], self.record)

    def test_owner_scoped_save_load_preserves_other_owners(self):
        foreign = self.world.register(self.member(character_id=32, owner_character_id=31,
                                                   account_id='account-b'), roster=ROSTER)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'companion.json'
            self.world.save(path, owner_character_id=11)
            self.assertEqual([row['character_id'] for row in json.loads(path.read_text())['records']], [22])
            self.world.load(path, roster=ROSTER)
            self.assertIs(self.world.records[32], foreign)

    def test_resource_and_half_integrity_validation(self):
        for changes in ({'hp': 41}, {'mp': 21}, {'alive': False}, {'hp': 0},
                        {'exp_half': 2}, {'mp_reserve': -1}, {'level': 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.member(**changes).validate()
        self.member(hp=0, alive=False).validate()


if __name__ == '__main__':
    unittest.main()
