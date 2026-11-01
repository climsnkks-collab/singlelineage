"""Development-only pure GM checks; no game, broker, socket or saved writes.

Tables/codecs load in test setup/import. Request tests forbid file access. The
explicit memory service below proves only progression/resource owner delegation,
not a production atomic store. Spawn/death lifetime and reward checks use the
real pure world modules without claiming login, wire delivery or gameplay PASS.
"""
from dataclasses import replace
from pathlib import Path
import random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import world_gm as gm
from tools.local_original_session.game_data import Rect, load_m1
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_handlers import HandlerState
from tools.local_original_session.world_interest_spawn import InterestSpawner, SlotState
from tools.local_original_session.world_maps import MapDestination
from tools.local_original_session.world_progress import Progress, exp_percent
from tools.local_original_session.world_reward import RewardPcState, on_kill
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_shop import InventoryItem
from tools.local_original_session.world_stats import (
    Attributes, CharacterStats, calculate_stats, self_info_fields,
)
from tools.local_original_session.world_status_frames import full_status_frame
from tools.local_original_session.world_town import TownNpcs, load_town
from tools.local_world_protocol import model as world_wire


class PureContext:
    """Structural world_handlers.Context; unused services explicitly refuse."""
    def __init__(self, town_data):
        self.world = WorldRuntime(clock=lambda: 100.0)
        self.pc_uid = 1
        self.pc = self.world.entities.add(Kind.PC, 0, 32578, 32946, heading=4, uid=1)
        self.town = TownNpcs(self.world.entities, town_data)
        self.store = self.wire = None
        self.state = HandlerState()
        self.interaction_distance = 1
        self.frames = []

    def now(self):
        return 100.0

    def send_frame(self, frame):
        self.frames.append(frame)

    def current_source(self, source):
        return False

    def dialogue_for(self, interaction, now):
        raise NotImplementedError('TEST_DIALOGUE_UNBOUND')

    def shop_action(self, interaction, menu, fields, now):
        raise NotImplementedError('TEST_SHOP_UNBOUND')

    def move(self, payload, now):
        raise NotImplementedError('TEST_MOVEMENT_UNBOUND')

    def transition(self, destination, now):
        raise NotImplementedError('TEST_ATOMIC_TRANSITION_UNBOUND')


class MemoryResourceService:
    """In-memory test owner, deliberately NOT a production GM service or save."""
    def __init__(self, snapshot):
        self.value = snapshot
        self.calls = []
        self.reject = False
        self.status = {
            1: 1, 2: 1, 4: 13, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15,
            10: 8, 11: 20, 12: 3, 13: 10, 14: -10, 15: 1793000000,
            16: 200, 17: 7, 18: -123, 20: 9,
        }

    async def snapshot(self, ctx, now):
        self.calls.append(('snapshot', now))
        return self.value

    def commit(self, ctx, plan, now):
        self.calls.append(('commit', plan.command, now))
        if self.reject:
            raise ValueError('TEST_COMMIT_REFUSED')
        if plan.snapshot is not self.value:
            raise ValueError('TEST_EXISTING_REVISION_CHANGED')
        pc = ctx.world.entities.resolve(plan.pc)
        if pc is None or not pc.alive or gm._position(pc) != plan.origin:
            raise ValueError('TEST_CURRENT_PC_CHANGED')
        if plan.command not in ('level', 'exp', 'hp', 'mp'):
            raise NotImplementedError('TEST_OWNER_OPERATION_UNBOUND')
        changes = {change.name: change.after for change in plan.changes}
        # Prepare all calculations/encoding before adopting the memory state.
        value = replace(self.value, revision=object(),
                        progress=changes.get('progression', self.value.progress),
                        base_stats=changes.get('base_stats', self.value.base_stats),
                        hp=changes.get('hp', self.value.hp), mp=changes.get('mp', self.value.mp))
        status = self_info_fields(self.status, calculate_stats(value.base_stats))
        status.update({10: value.hp, 11: value.max_hp, 12: value.mp, 13: value.max_mp,
                       26: exp_percent(value.data, value.progress.exp, value.progress.level)})
        frame = full_status_frame(status)
        self.value, self.status = value, status
        return gm.GMCommit((frame,))


class GMFixture:
    @classmethod
    def setUpClass(cls):
        cls.data = load_m1()
        cls.town_data = load_town()

    def setUp(self):
        self.ctx = PureContext(self.town_data)
        self.snapshot = gm.GMSnapshot(
            revision=object(), data=self.data, progress=Progress(0, 1, 20, 10),
            base_stats=CharacterStats(1, 0, Attributes(13, 10, 14, 12, 15, 11)),
            hp=8, max_hp=20, mp=3, max_mp=10,
            inventory=(InventoryItem(101, 14, 5, 1),
                       InventoryItem(102, 14, 1, 1, equipped=True),
                       InventoryItem(103, 7, 42, 1)),
            map_ids=frozenset((0, 1, 2)), speed_multiplier=1.0, god=False,
        )
        self.service = MemoryResourceService(self.snapshot)

    def plan(self, text, snapshot=None):
        result = gm.prepare_chat(self.ctx, text, snapshot=self.snapshot if snapshot is None else snapshot)
        self.assertEqual(result.status, 'proposed', result.message)
        self.assertTrue(result.handled)
        self.assertEqual(result.frames, ())
        return result.plan

    def changes(self, plan):
        return {change.name: change.after for change in plan.changes}


class GMProposalTests(GMFixture, unittest.TestCase):
    def test_every_command_has_explicit_proposal_and_projection_families(self):
        template = next(iter(self.data.monsters))
        item = next(iter(self.data.items))
        commands = ('.tele 1 2', '.level 2', '.exp 125', f'.item {item}',
                    '.hp full', '.mp full', f'.spawn {template}', '.kill',
                    '.speed 2', '.god', '.clear')
        before = tuple((e.uid, e.ref, e.map_id, e.x, e.y, e.alive) for e in self.ctx.world.entities)
        for text in commands:
            with self.subTest(text=text):
                plan = self.plan(text)
                self.assertTrue(plan.changes)
                self.assertIn(gm.FrameKind.SYSTEM_MESSAGE, plan.frame_kinds)
                self.assertIs(plan.snapshot, self.snapshot)
                self.assertEqual(plan.pc, self.ctx.pc.ref)
        self.assertEqual(before, tuple((e.uid, e.ref, e.map_id, e.x, e.y, e.alive)
                                      for e in self.ctx.world.entities))
        self.assertEqual(self.ctx.frames, [])

    def test_regular_chat_is_ignored_without_context_access(self):
        for text in ('hello', '', '  일반 채팅  ', '1. hello'):
            result = gm.prepare_chat(None, text)
            self.assertFalse(result.handled)
            self.assertEqual((result.status, result.plan, result.frames), ('ignored', None, ()))

    def test_where_reads_actual_current_entity_without_binding(self):
        self.ctx.world.entities.move(1, 2, 123, 456, 7)
        result = gm.prepare_chat(self.ctx, ' .WHERE ')
        self.assertEqual((result.handled, result.status, result.plan), (True, 'query', None))
        self.assertIn('map=2 x=123 y=456 heading=7 uid=1 generation=1', result.message)
        self.assertEqual(result.frame_kinds, (gm.FrameKind.SYSTEM_MESSAGE,))

    def test_malformed_commands_return_useful_errors_without_context_or_mutation(self):
        bad = ('.', '.unknown', '.tele', '.tele 1', '.tele -1 2', '.tele 1 65536',
               '.tele 1 2 3 4', '.level 0', '.level 256', '.level +2', '.exp -1',
               f'.exp {1 << 62}', '.exp +10', '.item 0', '.item 14 0',
               '.item 14 1000001', '.item 0xffffffff', '.spawn -1', '.spawn 0 51',
               '.hp 5', '.hp', '.mp full extra', '.god on', '.clear all', '.where now',
               '.speed 0', '.speed -1', '.speed nan', '.speed inf', '.speed 1e2',
               '.speed 10.01', '.exp １２', '.god\0', '.go\nd', '.' + 'a' * 300)
        for text in bad:
            with self.subTest(text=text):
                result = gm.prepare_chat(None, text, snapshot=self.snapshot)
                self.assertEqual(result.status, 'error')
                self.assertTrue(result.message)
                self.assertIsNone(result.plan)
        self.assertEqual(self.ctx.frames, [])

    def test_unbound_mutation_is_explicit_error(self):
        result = gm.prepare_chat(self.ctx, '.god')
        self.assertEqual((result.status, result.message, result.plan),
                         ('error', 'GM_BINDING_REQUIRED', None))

    def test_teleport_preserves_heading_and_uses_map_destination(self):
        current = self.changes(self.plan('.tele 0 65535'))['position']
        self.assertEqual(current, MapDestination(0, 0, 65535, 4))
        self.assertEqual(self.changes(self.plan('.tele 123 456 2'))['position'],
                         MapDestination(2, 123, 456, 4))
        result = gm.prepare_chat(self.ctx, '.tele 1 2 3', snapshot=self.snapshot)
        self.assertEqual(result.message, 'GM_MAP_UNAVAILABLE')
        self.assertEqual((self.ctx.pc.map_id, self.ctx.pc.x), (0, 32578))

    def test_exp_is_absolute_and_level_is_loaded_threshold(self):
        changed = replace(self.snapshot, progress=Progress(124, 1, 20, 10))
        exp = self.changes(self.plan('.exp 125', changed))
        self.assertEqual(exp['progression'], Progress(125, 2, 20, 10))
        self.assertEqual(exp['base_stats'], replace(self.snapshot.base_stats, level=2))
        for level in (1, 2, len(self.data.pc_exp)):
            with self.subTest(level=level):
                proposal = self.changes(self.plan(f'.level {level}'))
                self.assertEqual(proposal['progression'].exp, self.data.exp_for_level(level))
                self.assertEqual(proposal['progression'].level, level)
        top = self.changes(self.plan(f'.exp {gm.MAX_EXP}'))['progression']
        self.assertEqual((top.exp, top.level), (gm.MAX_EXP, len(self.data.pc_exp)))

    def test_level_above_data_and_inconsistent_progress_refuse(self):
        result = gm.prepare_chat(self.ctx, f'.level {len(self.data.pc_exp) + 1}', snapshot=self.snapshot)
        self.assertEqual(result.status, 'error')
        self.assertIn('GM_LEVEL_RANGE', result.message)
        inconsistent = replace(self.snapshot, progress=Progress(125, 1, 20, 10))
        result = gm.prepare_chat(self.ctx, '.exp 100', snapshot=inconsistent)
        self.assertEqual(result.message, 'GM_PROGRESS_SNAPSHOT_INCONSISTENT')

    def test_exp_proposal_is_compatible_with_real_kill_reward_growth(self):
        progression = self.changes(self.plan('.exp 124'))['progression']
        profile = SimpleNamespace(level=progression.level, character_class=0, con=14, wis=12)
        inputs = RewardPcState(progression.exp, profile, progression.max_hp, progression.max_mp)
        monster = replace(next(iter(self.data.monsters.values())), kill_exp=1)
        reward = on_kill(inputs, monster, random.Random(7), data=replace(self.data, drops={}))
        self.assertEqual((reward.new_exp, reward.old_level, reward.new_level), (125, 1, 2))
        self.assertGreater(reward.max_hp, progression.max_hp)
        self.assertEqual(self.snapshot.progress, Progress(0, 1, 20, 10))

    def test_resource_full_preserves_other_resource_and_rejects_unknown_mp(self):
        self.assertEqual(self.plan('.hp full').changes, (gm.Change('hp', 8, 20),))
        self.assertEqual(self.plan('.mp FULL').changes, (gm.Change('mp', 3, 10),))
        result = gm.prepare_chat(self.ctx, '.mp full', snapshot=replace(self.snapshot, mp=None, max_mp=None))
        self.assertEqual(result.message, 'GM_RESOURCE_MAXIMUM_REQUIRED')
        zero = self.plan('.mp full', replace(self.snapshot, mp=0, max_mp=0))
        self.assertEqual(zero.changes, (gm.Change('mp', 0, 0),))

    def test_combat_dead_hp_zero_with_live_entity_is_never_refilled(self):
        self.assertTrue(self.ctx.pc.alive)
        dead = replace(self.snapshot, hp=0)
        for command in ('.hp full', '.mp full'):
            result = gm.prepare_chat(self.ctx, command, snapshot=dead)
            self.assertEqual(result.message, 'CURRENT_LIVING_RESOURCE_PC_REQUIRED')
            self.assertIsNone(result.plan)

    def test_dead_pc_never_revived_and_reselected_lifetime_is_new(self):
        old = self.ctx.pc.ref
        self.ctx.world.entities.deactivate_pc(1)
        result = gm.prepare_chat(self.ctx, '.hp full', snapshot=self.snapshot)
        self.assertEqual(result.message, 'CURRENT_LIVE_PC_REQUIRED')
        self.ctx.world.entities.activate_pc(1, 0, 1, 2)
        self.assertIsNone(self.ctx.world.entities.resolve(old))
        self.assertNotEqual(self.plan('.god').pc, old)

    def test_same_town_world_binding_is_required(self):
        self.ctx.town = SimpleNamespace(entities=object())
        result = gm.prepare_chat(self.ctx, '.where')
        self.assertEqual(result.message, 'SAME_WORLD_TOWN_REQUIRED')

    def test_item_returns_template_and_count_without_creating_uid(self):
        item_id = next(iter(self.data.items))
        for count in (1, gm.MAX_ITEM_COUNT):
            text = f'.item {item_id}' if count == 1 else f'.item {item_id} {count}'
            plan = self.plan(text)
            item, actual = self.changes(plan)['item_grants'][0]
            self.assertIs(item, self.data.items[item_id])
            self.assertEqual(actual, count)
        result = gm.prepare_chat(self.ctx, '.item 4294967295', snapshot=self.snapshot)
        self.assertEqual(result.message, 'GM_ITEM_TEMPLATE_UNAVAILABLE')
        self.assertEqual(len(self.ctx.world.entities), 1)

    def test_clear_keeps_equipped_and_returns_per_uid_removals(self):
        plan = self.plan('.clear')
        self.assertEqual(self.changes(plan)['item_removals'], ((101, 5), (103, 42)))
        self.assertIn(gm.FrameKind.ITEM_REMOVE, plan.frame_kinds)
        self.assertNotIn(gm.FrameKind.ITEM_ADD, plan.frame_kinds)
        self.assertEqual(len(self.snapshot.inventory), 3)

    def test_spawn_template_zero_count_and_unknown_catalog(self):
        self.assertIn(0, self.data.monsters)
        for count in (1, gm.MAX_SPAWN_COUNT):
            plan = self.plan(f'.spawn 0 {count}')
            self.assertEqual(self.changes(plan)['spawns'],
                             (gm.SpawnRequest(0, count, MapDestination(0, 32578, 32946, 4)),))
        result = gm.prepare_chat(self.ctx, '.spawn 4294967295', snapshot=self.snapshot)
        self.assertEqual(result.message, 'GM_MONSTER_TEMPLATE_UNAVAILABLE')

    def test_kill_selects_only_nearby_live_same_map_monster_refs(self):
        entities, pc = self.ctx.world.entities, self.ctx.pc
        selected = entities.add(Kind.NPC, 0, pc.x + 17, pc.y + 17, template_id=0)
        entities.add(Kind.NPC, 0, pc.x + 18, pc.y, template_id=0)
        entities.add(Kind.NPC, 1, pc.x, pc.y, template_id=0)
        dead = entities.add(Kind.NPC, 0, pc.x, pc.y, template_id=0)
        entities.kill(dead.uid)
        entities.add(Kind.NPC, 0, pc.x, pc.y, template_id=70523)  # town
        entities.add(Kind.NPC, 0, pc.x, pc.y)  # no monster catalog identity
        entities.add(Kind.ITEM, 0, pc.x, pc.y, template_id=0)
        refs = self.changes(self.plan('.kill'))['deaths']
        self.assertEqual(refs, (selected.ref,))
        self.assertTrue(selected.alive)

    def test_spawn_request_connects_to_real_spawner_and_death_lifetime(self):
        request = self.changes(self.plan('.spawn 0 2'))['spawns'][0]
        pc = self.ctx.pc
        spec = replace(self.data.spawns[0], template_id=request.template_id,
                       map_id=pc.map_id, target_count=request.count,
                       rect=Rect(pc.x + 1, pc.y + 1, pc.x + 4, pc.y + 4))
        spawner = InterestSpawner(self.ctx.world.entities, replace(self.data, spawns=(spec,)),
                                 passable=lambda *_: True, rng=random.Random(7))
        self.assertTrue(spawner.update_interest([(pc.map_id, pc.x, pc.y)], 100.0))
        refs = self.changes(self.plan('.kill'))['deaths']
        self.assertEqual(len(refs), request.count)
        # Exercise the real lifetime owner, without inventing a GM kill receipt
        # or claiming rewards/atomic production commit from mark_dead alone.
        for ref in refs:
            slot = spawner.mark_dead(ref.uid, 100.0)
            self.assertEqual(slot.state, SlotState.WAIT)
            self.assertIsNone(self.ctx.world.entities.resolve(ref))
            with self.assertRaisesRegex(ValueError, 'WORLD_SPAWN_SLOT_NOT_ALIVE'):
                spawner.mark_dead(ref.uid, 100.0)
        self.assertEqual(self.changes(self.plan('.kill'))['deaths'], ())

    def test_speed_multiplier_and_god_toggle_have_explicit_state_changes(self):
        for value in ('0.1', '1', '2.5', '10'):
            plan = self.plan('.speed ' + value)
            self.assertEqual(plan.changes, (gm.Change('speed_multiplier', 1.0, float(value)),))
            self.assertIn(gm.FrameKind.SPEED, plan.frame_kinds)
        self.assertEqual(self.plan('.god').changes, (gm.Change('god', False, True),))
        self.assertEqual(self.plan('.god', replace(self.snapshot, god=True)).changes,
                         (gm.Change('god', True, False),))

    def test_proposals_do_not_read_paths(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('request-path filesystem access')
        with patch('builtins.open', forbidden), patch.object(Path, 'open', forbidden), \
                patch.object(Path, 'read_text', forbidden), patch.object(Path, 'read_bytes', forbidden):
            for command in ('.where', '.tele 1 2', '.exp 125', '.spawn 0', '.item 14',
                            '.kill', '.speed 2', '.god', '.clear', '.hp full', '.mp full'):
                result = gm.prepare_chat(self.ctx, command, snapshot=self.snapshot)
                self.assertIn(result.status, ('query', 'proposed'), result.message)


class GMServiceTests(GMFixture, unittest.IsolatedAsyncioTestCase):
    async def test_ordinary_chat_and_syntax_errors_never_consult_service(self):
        for command in ('hello', '.god on', '.item 14 0', '.speed nan', '.where'):
            result = await gm.handle_chat(self.ctx, command, 100.0, services=self.service)
            self.assertIn(result.status, ('ignored', 'error', 'query'))
        self.assertEqual(self.service.calls, [])

    async def test_absent_service_does_not_apply_or_infer_context_gm(self):
        self.ctx.gm = self.service  # The API must not discover fictional ctx.gm.
        result = await gm.handle_chat(self.ctx, '.exp 125', 100.0)
        self.assertEqual(result.message, 'GM_BINDING_REQUIRED')
        self.assertEqual(self.service.calls, [])
        self.assertEqual(self.service.value.progress.exp, 0)

    async def test_loaded_catalog_error_never_commits(self):
        result = await gm.handle_chat(self.ctx, '.item 4294967295', 100.0, services=self.service)
        self.assertEqual(result.status, 'error')
        self.assertEqual(self.service.calls, [('snapshot', 100.0)])

    async def test_real_status_encoding_and_stats_consume_committed_progression(self):
        result = await self.ctx.world.dispatch_now(
            gm.handle_chat, self.ctx, '.level 10', 100.0, services=self.service)
        self.assertEqual(result.status, 'committed')
        self.assertEqual(self.service.value.progress, Progress(self.data.exp_for_level(10), 10, 20, 10))
        frame = result.frames[0]
        self.assertEqual(int.from_bytes(frame[:2], 'little'), len(frame))
        self.assertEqual(int.from_bytes(frame[2:4], 'little'), 0x4E38)
        self.assertEqual(frame[-2:], b'\0\0')
        # f26's established double sits last; unchanged decoder consumes rest.
        fields = world_wire.decode_payload(0x4E38, frame[4:-12])
        self.assertEqual((fields[2], fields[10], fields[11], fields[12], fields[13]), (10, 8, 20, 3, 10))
        self.assertEqual(fields[14], -calculate_stats(self.service.value.base_stats).ac)
        self.assertEqual(struct.unpack('<d', frame[-10:-2])[0], 0.0)
        self.assertEqual(self.ctx.frames, [])  # Host retains send/write/drain.

    async def test_full_resources_delegate_once_and_return_existing_frames(self):
        for command, resource in (('.hp full', 'hp'), ('.mp full', 'mp')):
            result = await gm.handle_chat(self.ctx, command, 100.0, services=self.service)
            self.assertEqual(result.status, 'committed')
            self.assertEqual(getattr(self.service.value, resource), getattr(self.service.value, 'max_' + resource))
            self.assertEqual(len(result.frames), 1)
        self.assertEqual([call[1] for call in self.service.calls if call[0] == 'commit'], ['hp', 'mp'])

    async def test_refused_commit_propagates_without_success_or_retry(self):
        self.service.reject = True
        with self.assertRaisesRegex(ValueError, 'TEST_COMMIT_REFUSED'):
            await gm.handle_chat(self.ctx, '.level 2', 100.0, services=self.service)
        self.assertIs(self.service.value, self.snapshot)
        self.assertEqual(len(self.service.calls), 2)
        self.assertEqual(self.ctx.frames, [])

    async def test_stale_pc_generation_is_rejected_by_explicit_commit_owner(self):
        original = self.service.snapshot

        async def rebound(ctx, now):
            value = await original(ctx, now)
            return value

        original_commit = self.service.commit

        def reject_rebound(ctx, plan, now):
            ctx.world.entities.deactivate_pc(ctx.pc_uid)
            ctx.world.entities.activate_pc(ctx.pc_uid, 0, 1, 2)
            return original_commit(ctx, plan, now)

        self.service.snapshot, self.service.commit = rebound, reject_rebound
        with self.assertRaisesRegex(ValueError, 'TEST_CURRENT_PC_CHANGED'):
            await gm.handle_chat(self.ctx, '.hp full', 100.0, services=self.service)
        self.assertIs(self.service.value, self.snapshot)

    async def test_missing_real_damage_consumer_is_not_god_success(self):
        with self.assertRaisesRegex(NotImplementedError, 'TEST_OWNER_OPERATION_UNBOUND'):
            await gm.handle_chat(self.ctx, '.god', 100.0, services=self.service)
        self.assertFalse(self.service.value.god)

    async def test_invalid_commit_receipt_is_not_accepted(self):
        self.service.commit = lambda *_: None
        with self.assertRaisesRegex(TypeError, 'GM_COMMITTED_EXISTING_FRAMES_REQUIRED'):
            await gm.handle_chat(self.ctx, '.hp full', 100.0, services=self.service)

    async def test_bound_request_path_uses_only_loaded_state(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('request-path filesystem access')
        with patch('builtins.open', forbidden), patch.object(Path, 'open', forbidden), \
                patch.object(Path, 'read_text', forbidden), patch.object(Path, 'read_bytes', forbidden):
            result = await gm.handle_chat(self.ctx, '.exp 125', 100.0, services=self.service)
        self.assertEqual(result.status, 'committed')


if __name__ == '__main__':
    unittest.main()
