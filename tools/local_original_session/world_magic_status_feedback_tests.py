"""Status publication development checks; no game, ports or user saves."""
import unittest

from tools.local_original_session import world_feature_magic as magic_feature
from tools.local_original_session.world_item_effects import buff_icon_frame
from tools.local_original_session import world_magic_tests
from tools.local_entry_server import protobuf as pb


class MagicStatusFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.fixture = world_magic_tests.WorldConsumerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.ctx, self.view = self.fixture.ctx, self.fixture.view
        self.magic, self.now = self.fixture.magic, self.fixture.fixture.now
        self.ctx._world_magic_buff_ui = True
        magic_feature._world_magic_consumers(self.ctx)
        self.addCleanup(self.ctx._world_magic_stopped)

    def meditation(self):
        self.magic.apply_status(1, 'meditation', self.now, 30, spell=31,
            params={'tick_seconds': 10, 'mp_restore': 5})
        self.magic.state(1).buffs[2] = self.now + 30
        self.ctx._world_magic_sync_icons(1, self.now)
        self.view.drain(1)

    def assert_meditation_removed(self):
        self.assertIsNone(self.magic.status(1, 'meditation', self.now))
        frames = self.view.drain(1)
        self.assertEqual(frames.count(buff_icon_frame(31, 795, 0, remove=True)), 1)
        self.assertIn((1, 2), self.ctx._world_magic_icons)
        self.assertTrue(self.fixture.saved)

    def test_activity_removes_meditation_hud_immediately_and_once(self):
        self.meditation()
        self.view.combat.note_activity(1, 1)
        self.assert_meditation_removed()
        self.view.combat.note_activity(1, 1)
        self.assertEqual(self.view.drain(1), [])

    def test_ordinary_attack_removes_meditation_hud_before_next_tick(self):
        self.meditation()
        target = self.fixture.enemy()
        # pc_attack drains its owner's outbox; inspect the returned real path.
        frames = self.view.pc_attack(1, target.uid)
        self.assertIsNone(self.magic.status(1, 'meditation', self.now))
        self.assertIn(buff_icon_frame(31, 795, 0, remove=True), frames)
        self.assertIn((1, 2), self.ctx._world_magic_icons)

    def test_external_consume_event_removes_only_consumed_status(self):
        self.magic.apply_status(1, 'counter_magic', self.now, 30, spell=30)
        self.magic.state(1).buffs[2] = self.now + 30
        self.ctx._world_magic_sync_icons(1, self.now)
        self.view.drain(1)
        self.assertTrue(self.magic.consume_counter(1, self.now))
        self.view.events.emit('magic_status_changed', 1, self.now)
        self.assertIn(buff_icon_frame(30, 748, 0, remove=True), self.view.drain(1))
        self.assertIn((1, 2), self.ctx._world_magic_icons)

    def test_entangle_changes_only_move_axis_and_restores_on_expiry(self):
        self.magic.apply_status(1, 'slow', self.now, 30,
            params={'interval_multiplier': 2})
        self.magic.apply_status(1, 'entangle', self.now, 10,
            params={'move_multiplier': 2})
        factors = self.ctx.fold_sync_hooks('speed_factors', (1.5, 1.5), 1, self.now)
        self.assertEqual(factors, (3, 1.5))
        self.assertEqual(self.ctx.fold_sync_hooks('speed_factors', (1.5, 1.5),
            1, self.now + 10), (1.5, 1.5))
        self.assertEqual(self.ctx.fold_sync_hooks('speed_factors', (1.5, 1.5),
            99999, self.now), (1.5, 1.5))

    def test_stop_releases_status_event_consumer(self):
        self.ctx._world_magic_stopped()
        self.assertFalse(self.view.events._callbacks['magic_status_changed'])
        # Stop is also the registered fixture cleanup.
        self.view.events.emit('magic_status_changed', 1, self.now)

    def observer(self, x=101):
        from tools.local_original_session.world_visibility import MONSTER_BASE_FIELDS
        from tools.local_movement_session_route.route import authority
        def actor(uid, px):
            fields = dict(MONSTER_BASE_FIELDS)
            fields.update({1: authority.pack_grid(px, 100), 2: uid, 3: 734,
                           5: 0, 9: 'StatusFixture', 16: True, 21: ''})
            return fields
        self.view.pc_actors[1] = actor(1, 100)
        status = dict(self.fixture.state.status_fields)
        status[1] = 3
        self.view.bind_pc(3, self.fixture.state.profile, status)
        self.view.update_pc(3, 0, x, 100, actor_fields=actor(3, x))
        self.view.drain(1)
        self.view.drain(3)

    def test_invisible_required_fields_select_proven_positive_and_clear_branches(self):
        for active, expected in ((True, 1), (False, 0)):
            wire = magic_feature.invisible_frame(0x100000003, active)
            self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x4f04)
            with pb.parse_message(wire[4:-2]) as message:
                self.assertEqual([(f.number, f.value) for f in message.fields],
                                 [(1, 0x100000003), (2, expected)])

    def test_invisible_apply_expiry_and_detection_reach_owner_and_current_observer(self):
        self.observer()
        self.ctx._world_magic_set_invisible(1, self.now, duration=2)
        for uid in (1, 3):
            self.assertIn(magic_feature.invisible_frame(1, True), self.view.drain(uid))
        self.fixture.fixture.now += 2
        self.ctx._world_magic_tick(self.fixture.fixture.now)
        for uid in (1, 3):
            self.assertIn(magic_feature.invisible_frame(1, False), self.view.drain(uid))
        self.ctx._world_magic_set_invisible(1, self.fixture.fixture.now)
        self.view.drain(1)
        self.view.drain(3)
        self.ctx._world_magic_cast(1, 12, 1, self.fixture.fixture.now)
        for uid in (1, 3):
            self.assertIn(magic_feature.invisible_frame(1, False), self.view.drain(uid))

    def test_invisible_observer_reentry_replays_after_actor_and_expiry_clears(self):
        self.observer(x=200)
        self.ctx._world_magic_set_invisible(1, self.now, duration=2)
        self.assertEqual(self.view.drain(3), [])
        frames = self.view.update_pc(3, 0, 101, 100)
        invis = magic_feature.invisible_frame(1, True)
        self.assertIn(invis, frames)
        actor_index = next(i for i, wire in enumerate(frames)
                           if int.from_bytes(wire[2:4], 'little') == 0x4e96)
        self.assertLess(actor_index, frames.index(invis))
        self.fixture.fixture.now += 2
        self.ctx._world_magic_tick(self.fixture.fixture.now)
        self.assertIn(magic_feature.invisible_frame(1, False), self.view.drain(3))

    def test_npc_invisible_reentry_expiry_and_detection_use_current_actor(self):
        self.observer()
        target = self.fixture.enemy()
        self.ctx._world_magic_set_invisible(target.uid, self.now, duration=2)
        self.assertIn(magic_feature.invisible_frame(target.uid, True), self.view.drain(1))
        # Keep this manually inserted NPC's interest group fixed; only the
        # observer screen changes, as in the core visibility diff.
        self.view.pcs[1] = (0, 200, 100)
        self.view.entities.move(1, 0, 200, 100)
        self.view._refresh(1)
        self.view.pcs[1] = (0, 100, 100)
        self.view.entities.move(1, 0, 100, 100)
        frames = self.view._refresh(1)
        self.assertIn(magic_feature.invisible_frame(target.uid, True), frames)
        self.fixture.fixture.now += 2
        self.ctx._world_magic_tick(self.fixture.fixture.now)
        self.assertIn(magic_feature.invisible_frame(target.uid, False), self.view.drain(1))
        self.ctx._world_magic_set_invisible(target.uid, self.fixture.fixture.now)
        self.view.drain(1)
        self.ctx._world_magic_cast(1, 12, 1, self.fixture.fixture.now)
        self.assertIn(magic_feature.invisible_frame(target.uid, False), self.view.drain(1))

    def test_invisible_restart_retains_deadline_and_replays_new_native_scene(self):
        self.ctx._world_magic_set_invisible(1, self.now)
        deadline = self.magic.state(1).invisible_until
        self.ctx._world_magic_writers[id(self.fixture.writer)] = 1
        self.ctx._world_magic_detach(self.fixture.writer)
        self.assertNotIn(1, self.ctx._world_magic_invisible)
        self.assertEqual(self.magic.state(1).invisible_until, deadline)
        frames = self.ctx._world_magic_after_relocate(1, {})
        self.assertIn(magic_feature.invisible_frame(1, True), frames)

    def test_lock_keys_overlap_onset_and_paired_release_without_unlocking_survivor(self):
        self.magic.apply_status(1, 'stun', self.now, 5)
        self.magic.apply_status(1, 'paralyze', self.now, 2, onset=1)
        self.ctx._world_magic_sync_icons(1, self.now)
        frames = self.view.drain(1)
        self.assertIn(magic_feature.paralyse_frame(0, True), frames)
        self.assertNotIn(magic_feature.paralyse_frame(2, True), frames)
        self.fixture.fixture.now = self.now + 1
        self.ctx._world_magic_tick(self.now + 1)
        frames = self.view.drain(1)
        self.assertIn(magic_feature.paralyse_frame(2, True), frames)
        self.assertIn(magic_feature._frame(0x4eea, pb.encode_uint32(1, 213)), frames)
        self.assertIn(magic_feature.poison_frame(1, False, True), frames)
        self.fixture.fixture.now = self.now + 3
        self.ctx._world_magic_tick(self.now + 3)
        frames = self.view.drain(1)
        self.assertIn(magic_feature.paralyse_frame(2, False), frames)
        self.assertNotIn(magic_feature._frame(0x4eea, pb.encode_uint32(1, 112)), frames)
        self.assertNotIn(magic_feature.paralyse_frame(0, False), frames)
        self.assertIn(magic_feature.poison_frame(1, False, False), frames)
        self.assertFalse(self.view.combat.pc_swing_ready(1, self.now + 3))
        self.fixture.fixture.now = self.now + 5
        self.ctx._world_magic_tick(self.now + 5)
        frames = self.view.drain(1)
        self.assertIn(magic_feature.paralyse_frame(0, False), frames)
        self.assertIn(magic_feature._frame(0x4eea, pb.encode_uint32(1, 2196)), frames)
        self.assertTrue(self.view.combat.pc_swing_ready(1, self.now + 5))

    def test_poison_and_stone_full_truth_survives_cure_and_later_expiry(self):
        self.observer()
        self.magic.apply_status(1, 'paralyze', self.now, 3)
        self.ctx._world_magic_apply_poison(1, 3, self.now, duration=6)
        for uid in (1, 3):
            self.assertIn(magic_feature.poison_frame(1, True, True), self.view.drain(uid))
        self.magic.state(1).poison = None  # existing external cure authority
        self.ctx._world_magic_tick(self.now)
        for uid in (1, 3):
            self.assertIn(magic_feature.poison_frame(1, False, True), self.view.drain(uid))
        self.fixture.fixture.now += 3
        self.ctx._world_magic_tick(self.fixture.fixture.now)
        frames = self.view.drain(1)
        self.assertLess(frames.index(magic_feature.paralyse_frame(2, False)),
                        frames.index(magic_feature.poison_frame(1, False, False)))
        self.assertIn(magic_feature.poison_frame(1, False, False), self.view.drain(3))

    def test_blind_and_darkness_share_lighting_mode_until_both_clear(self):
        self.magic.apply_status(1, 'blind', self.now, 2)
        self.magic.apply_status(1, 'darkness', self.now, 4)
        self.ctx._world_magic_sync_icons(1, self.now)
        self.assertIn(magic_feature.blind_frame(True), self.view.drain(1))
        self.fixture.fixture.now += 2
        self.ctx._world_magic_tick(self.fixture.fixture.now)
        self.assertNotIn(magic_feature.blind_frame(False), self.view.drain(1))
        self.fixture.fixture.now += 2
        self.ctx._world_magic_tick(self.fixture.fixture.now)
        self.assertIn(magic_feature.blind_frame(False), self.view.drain(1))

    def test_feedback_replay_new_actor_includes_combined_poison_and_stone(self):
        self.observer(x=200)
        self.magic.apply_status(1, 'paralyze', self.now, 4)
        self.ctx._world_magic_apply_poison(1, 3, self.now, duration=4)
        self.view.drain(1)
        frames = self.view.update_pc(3, 0, 101, 100)
        self.assertIn(magic_feature.poison_frame(1, True, True), frames)
        self.assertNotIn(magic_feature.paralyse_frame(2, True), frames)

    def test_death_releases_both_lock_keys_and_all_private_visual_state(self):
        for kind in ('stun', 'paralyze', 'blind'):
            self.magic.apply_status(1, kind, self.now, 4)
        self.ctx._world_magic_apply_poison(1, 3, self.now)
        self.ctx._world_magic_set_invisible(1, self.now)
        self.view.drain(1)
        self.ctx._world_magic_died(1)
        frames = self.view.drain(1)
        for wire in (magic_feature.paralyse_frame(0, False),
                     magic_feature.paralyse_frame(2, False), magic_feature.blind_frame(False),
                     magic_feature.poison_frame(1, False, False),
                     magic_feature.invisible_frame(1, False)):
            self.assertIn(wire, frames)

    def test_new_scene_replay_resets_inactive_owned_keys_and_keeps_saved_deadlines(self):
        self.magic.apply_status(1, 'stun', self.now, 4)
        original = self.magic.snapshot(1, self.now, wall=1000)
        frames = self.ctx._world_magic_after_relocate(1, {})
        for wire in (magic_feature.paralyse_frame(0, True),
                     magic_feature.paralyse_frame(2, False), magic_feature.blind_frame(False),
                     magic_feature.poison_frame(1, False, False)):
            self.assertIn(wire, frames)
        self.assertLess(frames.index(magic_feature.paralyse_frame(0, True)),
                        frames.index(magic_feature.paralyse_frame(2, False)))
        self.assertLess(frames.index(magic_feature.paralyse_frame(2, False)),
                        frames.index(magic_feature.poison_frame(1, False, False)))
        self.assertEqual(self.magic.snapshot(1, self.now, wall=1000), original)
        repeated = self.ctx._world_magic_after_relocate(1, {})
        self.assertFalse(any(int.from_bytes(wire[2:4], 'little') == 0x4eea for wire in repeated))
        self.assertNotIn('before_leave', magic_feature.HOOKS)


if __name__ == '__main__':
    unittest.main()
