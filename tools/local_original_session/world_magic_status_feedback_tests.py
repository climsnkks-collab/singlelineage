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

    def test_magic_only_registry_allows_status_notice(self):
        from types import SimpleNamespace
        from tools.local_original_session.world_registry import build_registry
        from tools.local_original_session.world_bridge import validate_frame
        registry = build_registry((magic_feature,))
        broker = SimpleNamespace(WORLD_SEND_OPCODES=registry.outgoing_opcodes)
        notice = magic_feature._frame(0x4eea, pb.encode_uint32(1, 213))
        validate_frame(broker, notice, None)
        self.assertIn(0x4eea, registry.outgoing_opcodes)

    def test_scenario_publication_requires_matching_sent_status_packets(self):
        import asyncio
        import importlib.util
        import time
        from pathlib import Path
        from types import SimpleNamespace
        path = Path(__file__).resolve().parents[2] / 'work/local_original_session/companion-bridge/status_feedback_scenario.py'
        spec = importlib.util.spec_from_file_location('status_publication_test', path)
        scenario = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scenario)
        for kind, lock, code in (('paralyze', 2, 213), ('stun', 0, 999), ('poison', None, None)):
            module = SimpleNamespace(STEP_SETS={})
            scenario.install(module, object, None, None, None, 'knight_status_' + kind)
            expected = ([dict(opcode='0x4f05', fields={'1': 1, '2': 1})] if kind == 'poison' else
                [dict(opcode='0x4eeb', fields={'1': lock}), dict(opcode='0x4eea', fields={'1': code})])
            expected = [dict(p, recipient=1, send_returned=True, monotonic_seconds=time.monotonic()) for p in expected]
            for label, packets, observed in (('empty', [], False),
                    ('not_sent', [dict(p, send_returned=False) for p in expected], False),
                    ('other_recipient', [dict(p, recipient=2) for p in expected], False),
                    ('sent', expected, True)):
                with self.subTest(kind=kind, packets=label):
                    steps = object.__new__(module.Steps)
                    steps.done, steps.index, steps.started = False, 0, time.monotonic()-111
                    steps.steps = (('status_wait', 'active-publication', True),)
                    steps.status_snapshot = lambda native=False: dict(uid=1, active=True, packets=packets)
                    results = []
                    steps.finish = results.append
                    asyncio.run(steps.tick())
                    self.assertEqual(results[0]['status'], 'OBSERVED' if observed else 'UNKNOWN')

    def test_blocked_movement_distinguishes_read_gap_from_coordinate_change(self):
        import copy
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parents[2] / 'work/local_original_session/companion-bridge/status_feedback_scenario.py'
        spec = importlib.util.spec_from_file_location('status_movement_test', path)
        scenario = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scenario)
        transform = dict(status='OBSERVED', current_grid=[100, 100], predicted_grid=[100, 100])
        baseline = dict(server_grid=[100, 100], native_world=dict(grid_words=[100, 100]),
            native_move=dict(transform=transform), movement=dict(requests_received=0, corrections_prepared=0, committed=0))
        after = dict(active=True, movement=dict(baseline['movement']))
        samples = [dict(elapsed=i*.25, server_grid=[100, 100], native_grid=[100, 100],
            transform=copy.deepcopy(transform), move_state=dict(status='OBSERVED')) for i in range(8)]
        self.assertTrue(scenario.blocked_movement_result(after, baseline, samples)['ok'])
        broken = copy.deepcopy(samples)
        broken[3].update(transform=dict(status='UNKNOWN', reason='MOVE_TYPED_READ_CHANGED'),
            move_state=dict(status='UNKNOWN', reason='MOVE_TYPED_READ_CHANGED', typed_read_changed_field='OWNER_REFCOUNT'))
        result = scenario.blocked_movement_result(after, baseline, broken)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'STATUS_MOVE_READ_INCOMPLETE')
        self.assertTrue(result['sampled_position_unchanged'])
        moved = copy.deepcopy(samples)
        moved[3]['transform']['predicted_grid'] = [101, 100]
        result = scenario.blocked_movement_result(after, baseline, moved)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'STATUS_MOVEMENT_CHANGED')

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
            frames = self.view.drain(uid)
            self.assertIn(magic_feature.poison_frame(1, True, True), frames)
            if uid == 1:
                self.assertIn(buff_icon_frame(10, 5319, 6), frames)
        self.magic.state(1).poison = None  # existing external cure authority
        self.ctx._world_magic_tick(self.now)
        for uid in (1, 3):
            frames = self.view.drain(uid)
            self.assertIn(magic_feature.poison_frame(1, False, True), frames)
            if uid == 1:
                self.assertIn(buff_icon_frame(10, 5319, 0, remove=True), frames)
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


class CompanionStatusFeedbackTests(unittest.TestCase):
    """Real monster/ailment/event/observer consumers, without game or sockets."""
    def setUp(self):
        from types import SimpleNamespace as NS, MethodType
        from tools.local_original_session import world_feature_companion as companion
        from tools.local_original_session import world_registry, world_monster_skills
        from tools.local_original_session.monster_skills_tests import all_data
        MagicStatusFeedbackTests.setUp(self)
        self.actor = self.fixture.fixture.actor
        self.record = self.actor.record
        self.record.hp = self.record.max_hp = 100000
        self.view.replace_data(all_data())
        self.ailments = companion.CompanionAilments(self.view)
        self.ailments.start()
        self.addCleanup(self.ailments.close)
        self.ctx._companion_enabled = True
        self.ctx._companion_ailments = self.ailments
        # Register the actual optional target hook without starting unrelated UI.
        hook = companion._companion_npc_magic_target
        self.ctx._companion_npc_magic_target = MethodType(hook, self.ctx)
        contribution = NS(__name__='companion_target_fixture', METHODS=(hook,),
            HOOKS={'npc_magic_target': (hook.__name__,)})
        self.ctx._world_registry = world_registry.build_registry((magic_feature, contribution))
        self.adapter = self.ctx._companion_npc_magic_target(self.actor.ref.uid)
        self.monsters = world_monster_skills.MonsterSkills(self.view,
            world_monster_skills.load_attacks(), provider=(self.magic, lambda *_: None),
            magic_target=self.ctx._companion_npc_magic_target)
        self.monsters.start()
        self.addCleanup(self.monsters.close)
        self.view.drain(1)

    def inflict(self, template=28, kind='paralysis', now=None):
        from dataclasses import replace
        from tools.local_original_session.world_entities import Kind
        from tools.local_original_session.world_interest_spawn import Group, Slot, SlotState
        now = self.now if now is None else now
        self.now = self.fixture.fixture.now = now
        row = next(r for rows in self.monsters.attacks.values() for r in rows
                   if r['template_id'] == template and r['kind'] == kind)
        monster = self.view.data.monsters[template]
        target = self.view.entities.get(self.actor.ref.uid)
        entity = self.view.entities.add(Kind.NPC, target.map_id, target.x + 1, target.y,
                                       template_id=template)
        spec = replace(self.view.data.spawns[0], template_id=template)
        slot = Slot(0, SlotState.ALIVE, entity.uid, monster.hp, (entity.x, entity.y))
        group = Group(spec, monster, [slot], True)
        self.view.spawner.groups.append(group)
        self.view.spawner._slots[entity.uid] = group, slot
        self.assertTrue(self.monsters.cast(entity, monster, target, row, now))
        return row

    def tick(self, now):
        self.fixture.fixture.now = now
        # Exercise the companion owner alone: onset cannot depend on magic's tick.
        self.ailments.tick(now)

    def feedback(self, *, poison=False, stone=False, recipient=1, expected=True):
        from tools.local_original_session.world_feature_magic import poison_frame
        frames = self.view.drain(recipient)
        wire = poison_frame(self.actor.ref.uid, poison, stone)
        self.assertEqual(wire in frames, expected)
        self.assertNotIn(0x4eeb, [int.from_bytes(w[2:4], 'little') for w in frames])
        self.assertNotIn(self.actor.ref.uid, self.magic.npc_statuses)
        self.assertNotIn(self.actor.ref.uid, self.magic.npc_poison)
        return frames

    def test_delayed_paralysis_onset_and_expiry_publish_to_knight(self):
        row = self.inflict()
        self.feedback(stone=True, expected=False)
        onset = self.now + row['delay_seconds']
        self.tick(onset - .01)
        self.feedback(stone=True, expected=False)
        self.tick(onset)
        self.feedback(stone=True)
        self.tick(onset + .1)
        self.feedback(stone=True, expected=False)
        self.tick(onset + row['duration_seconds'])
        self.feedback()

    def test_poison_start_and_expiry_publish_to_knight(self):
        row = self.inflict(31, 'poison')
        self.feedback(poison=True)
        self.tick(self.now + row['duration_seconds'])
        self.feedback()

    def test_antidote_cures_paralysis_and_poison_immediately(self):
        for template, kind in ((28, 'paralysis'), (31, 'poison')):
            with self.subTest(kind=kind):
                self.inflict(template, kind, now=self.fixture.fixture.now + 100)
                self.tick(self.now + 20)
                self.view.drain(1)
                self.assertTrue(self.adapter.cure_poison(self.now + 21))
                self.feedback()

    def test_companion_cure_poison_and_remove_curse_publish_clear(self):
        from tools.local_original_session.world_feature_companion import CompanionMagic
        from types import SimpleNamespace as NS
        healer = object.__new__(CompanionMagic)
        healer.view, healer.ctx = self.view, NS(_companion_ailments=self.ailments)
        for name in ('cure_poison', 'remove_curse'):
            for template, kind in ((28, 'paralysis'), (31, 'poison')):
                with self.subTest(spell=name, kind=kind):
                    self.inflict(template, kind, now=self.fixture.fixture.now + 100)
                    self.tick(self.now + 20)
                    self.view.drain(1)
                    target = self.view.entities.get(self.actor.ref.uid)
                    self.assertTrue(healer.ailment(self.actor, target, name, self.now + 21, apply=True))
                    self.feedback()

    def test_visibility_reentry_replays_active_companion_state(self):
        from tools.local_original_session.world_feature_magic import poison_frame
        self.inflict()
        self.tick(self.now + 20)
        self.feedback(stone=True)
        self.view.update_pc(1, 0, 200, 200)
        self.view.drain(1)
        self.view.update_pc(1, 0, 100, 100)
        frames = self.view.drain(1)
        # update_pc returns its refresh; an explicit refresh also uses the wrapper.
        self.view.visibility.known[1].discard(self.actor.ref.uid)
        frames.extend(self.view._refresh(1))
        self.assertIn(poison_frame(self.actor.ref.uid, False, True), frames)
        self.assertNotIn(0x4eeb, [int.from_bytes(w[2:4], 'little') for w in frames])

    def test_failed_ailment_save_publishes_no_status_event(self):
        from unittest.mock import Mock
        self.view.companion_save = Mock(side_effect=OSError('status-store-failed'))
        events = []
        self.view.events.add('save_failure_fixture', 'magic_status_changed',
                             lambda *args: events.append(args))
        with self.assertRaisesRegex(OSError, 'status-store-failed'):
            self.inflict(31, 'poison')
        self.assertFalse(events)
        self.feedback(poison=True, expected=False)

    def test_death_commit_clears_visible_state_before_actor_generation_changes(self):
        from types import SimpleNamespace as NS
        from unittest.mock import Mock, patch
        from tools.local_original_session import world_feature_companion as companion
        self.inflict(31, 'poison')
        self.feedback(poison=True)
        ctx = NS(world=self.view, _companion_store=Mock(), _companion_inventory=None,
            _companion_rows={self.record.character_id: {}}, _companion_windows={},
            _companion_pet_modes={})
        self.view.companion_save = lambda uid, receipt=None: companion._companion_save(ctx, uid, receipt)
        # Match the feature's on_death order, retaining the runtime save wrapper.
        def on_death(record, now):
            self.ailments.clear(record)
            self.view._save_companion(record.owner_character_id)
        self.view.companions.on_death = on_death
        original_ref = self.actor.ref
        with patch.object(companion, '_companion_refresh_views'):
            self.view.companions.die(self.actor.character_id, self.now + 1)
        self.feedback()
        ctx._companion_store.commit.assert_called_once()
        self.assertIsNone(self.view.entities.resolve(original_ref))
        self.assertNotIn('monster_ailments', self.record.equipment)


if __name__ == '__main__':
    unittest.main()

