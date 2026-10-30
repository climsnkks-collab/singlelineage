"""Development status/presentation integration; no socket or native-client PASS."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import monster_skills_tests as monsters
from tools.local_original_session import world_feature_magic as magic_feature
from tools.local_original_session import world_feature_weapon_effects as weapon_feature
from tools.local_original_session import world_magic, world_magic_tests
from tools.local_original_session import world_weapon_proc_effects_tests as weapons
from tools.local_original_session import world_pc_response_tests as peers
from tools.local_original_session.world_monster_skills import MonsterSkills, load_attacks


def speed_values(wire):
    """Decode established nested 4E5B keys without a bot or client process."""
    if int.from_bytes(wire[2:4], 'little') != 0x4e5b:
        return None
    with pb.parse_message(wire[4:-2]) as message:
        uid = next(field.value for field in message.fields if field.number == 1)
        bonus = next(field.value for field in message.fields if field.number == 2)
        result = {}
        with pb.parse_message(bonus) as entries:
            for entry in entries.fields:
                with pb.parse_message(entry.value) as pair:
                    fields = {field.number: field.value for field in pair.fields}
                    value = fields[2]
                    result[fields[1]] = value - (1 << 64) if value >= 1 << 63 else value
    return uid, result


class MonsterStatusFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.f = world_magic_tests.WorldConsumerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.ctx, self.view, self.magic = self.f.ctx, self.f.view, self.f.magic
        self.ctx._world_magic_buff_ui = True
        magic_feature._world_magic_consumers(self.ctx)
        self.owner = MonsterSkills(self.view, load_attacks(),
            provider=magic_feature._world_magic_consumable_provider(self.ctx))
        self.owner.start()
        self.addCleanup(self.owner.close)
        self.entity, self.monster = self.f.fixture.monster(7)
        self.now = self.f.fixture.now
        self.target = self.view.entities.get(1)

    def shields(self):
        for kind, key in (('counter_magic', 30), ('erase_magic', 152)):
            self.magic.apply_status(1, kind, self.now, 100, spell=key)
        self.ctx._world_magic_sync_icons(1, self.now)
        self.view.drain(1)
        self.assertEqual(set(self.ctx._world_magic_icons), {(1, 30), (1, 152)})

    def test_monster_counter_consumes_both_states_then_saves_and_removes_actual_hud(self):
        self.shields()
        row = next(row for row in self.owner.attacks[self.monster.l1j_npcid]
                   if row['kind'] == 'magic')
        before = self.view.combat.pcs[1].hp
        self.assertTrue(self.owner.cast(self.entity, self.monster, self.target, row, self.now))
        self.assertEqual(self.owner.events[-1]['outcome'], 'countered')
        self.assertEqual(self.view.combat.pcs[1].hp, before)
        self.assertFalse(self.f.saved[-1].get('statuses', {}).get('effects', {}))
        wires = self.view.drain(1)
        for key in (30, 152):
            self.assertIn(magic_feature.buff_icon_frame(key,
                magic_feature.SPELL_BUFF_ICONS[key], 0, remove=True), wires)
        self.assertFalse(self.ctx._world_magic_icons)

    def test_monster_resisted_status_consumes_erase_and_removes_hud_after_save(self):
        row = next(row for rows in load_attacks().values() for row in rows
                   if row['template_id'] == 2214 and row['kind'] == 'slow')
        monster = monsters.all_data().monsters[2214]
        group, slot = self.view.spawner.slot_for(self.entity.uid)
        group.monster, slot.hp = monster, monster.hp
        self.entity.template_id = monster.template_id
        self.f.state.profile = replace(self.f.state.profile, mr=10000)
        self.magic.apply_status(1, 'erase_magic', self.now, 100, spell=152)
        self.ctx._world_magic_sync_icons(1, self.now)
        self.view.drain(1)
        self.assertTrue(self.owner.cast(self.entity, monster, self.target, row, self.now))
        self.assertEqual(self.owner.events[-1]['outcome'], 'resisted')
        self.assertIsNone(self.magic.status(1, 'erase_magic', self.now))
        self.assertIn(magic_feature.buff_icon_frame(152,
            magic_feature.SPELL_BUFF_ICONS[152], 0, remove=True), self.view.drain(1))

    def test_save_failure_leaves_hud_pending_and_emits_no_removal(self):
        self.shields()
        row = next(row for row in self.owner.attacks[self.monster.l1j_npcid]
                   if row['kind'] == 'magic')
        with patch.object(self.ctx._world_magic_store, 'save', side_effect=OSError('disk-full')):
            with self.assertRaisesRegex(OSError, 'disk-full'):
                self.owner.cast(self.entity, self.monster, self.target, row, self.now)
        self.assertEqual(set(self.ctx._world_magic_icons), {(1, 30), (1, 152)})
        self.assertFalse(any(int.from_bytes(wire[2:4], 'little') == 0x4e91
                             for wire in self.view.drain(1)))


class SplitSpeedFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.f = weapons.WeaponProcTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.view = self.f.world
        _, x, y = self.view.pcs[1]
        self.view.publish_pc_actor(1, peers.actor(1, x, y))
        self.magic = world_magic.PlayerMagic(world_magic.load_catalog())
        context = SimpleNamespace(_world_magic=self.magic)
        self.f.hooks['speed_factors'] = lambda factors, uid, now: (
            magic_feature._world_magic_speed_factors(context, factors, uid, now))
        self.magic.apply_status(1, 'entangle', self.f.now, 10,
                               spell=151, params={'move_multiplier': 2})

    def test_tick_applies_move_only_to_owner_and_visible_peer_then_restores(self):
        _, x, y = self.view.pcs[1]
        peers.bind(self.view, 2, x, y + 1)
        self.view.drain(1)
        self.view.drain(2)
        self.view.events.emit('tick', self.f.now)
        for uid in (1, 2):
            frames = [speed_values(wire) for wire in self.view.drain(uid)
                      if int.from_bytes(wire[2:4], 'little') == 0x4e5b]
            self.assertIn((1, {0: -50, 1: 0}), frames)
        self.f.now += 10
        self.view.events.emit('tick', self.f.now)
        for uid in (1, 2):
            self.assertIn((1, {0: 0, 1: 0}),
                [speed_values(wire) for wire in self.view.drain(uid)
                 if int.from_bytes(wire[2:4], 'little') == 0x4e5b])

    def test_potion_apply_and_expiry_keep_movement_axis_separate(self):
        buff = self.view.data.items[17].buff
        expiry, wire = self.view.combat.apply_buff(1, buff, self.f.now)
        self.assertEqual(speed_values(wire), (1, {0: -33, 1: 34}))
        # Isolate a normal potion expiry while a longer entangle remains.
        self.magic.effects(1)['entangle']['until'] = expiry + 10
        wire = self.view.combat.expire_buff(1, buff.kind, expiry)
        self.assertEqual(speed_values(wire), (1, {0: -50, 1: 0}))

    def test_newly_visible_peer_receives_entangle_even_when_attack_total_is_normal(self):
        _, x, y = self.view.pcs[1]
        wires = peers.bind(self.view, 2, x, y + 1)
        self.assertEqual([speed_values(wire) for wire in wires
                          if int.from_bytes(wire[2:4], 'little') == 0x4e5b],
                         [(1, {0: -50, 1: 0})])

    def test_symmetric_codec_is_unchanged_and_feature_close_releases_wrappers(self):
        from tools.local_original_session.world_combat import speed_frame
        self.assertEqual(weapon_feature._speed_frame(1, (.75, .75)), speed_frame(1, .75))
        self.view.events.emit('close')
        for name in ('apply_buff', 'expire_buff'):
            self.assertNotIn(name, vars(self.view.combat))
        self.assertNotIn('_refresh_pcs', vars(self.view))
        self.assertNotIn('_refresh', vars(self.view))
        self.assertFalse(any(row[1] == 'weapon_effects'
            for row in self.view.events._callbacks.get('tick', ())))


class NpcSpeedFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.f = world_magic_tests.WorldConsumerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.ctx, self.view, self.magic = self.f.ctx, self.f.view, self.f.magic
        magic_feature._world_magic_consumers(self.ctx)
        weapon_feature._world_weapon_effects_initialize(self.ctx)
        self.owner = MonsterSkills(self.view, load_attacks(),
            provider=magic_feature._world_magic_consumable_provider(self.ctx))
        self.owner.start()
        self.addCleanup(self.owner.close)
        self.entity, _ = self.f.fixture.monster(7)
        self.monster = monsters.all_data().monsters[287]
        group, slot = self.view.spawner.slot_for(self.entity.uid)
        group.monster, slot.hp = self.monster, self.monster.hp
        group.spec = replace(group.spec, template_id=self.monster.template_id, map_id=0,
            rect=replace(group.spec.rect, x1=100, y1=100, x2=102, y2=102))
        self.entity.template_id = self.monster.template_id
        self.view.ai.brains[self.entity.uid].monster = self.monster
        self.row = next(row for row in self.owner.attacks[self.monster.l1j_npcid]
                        if row['kind'] == 'haste')
        self.now = self.f.fixture.now
        self.view._refresh(1)
        self.view.drain(1)

    def speeds(self, wires):
        return [value[1] for wire in wires
                if (value := speed_values(wire)) is not None and value[0] == self.entity.uid]

    def haste(self):
        self.assertTrue(self.owner.cast(self.entity, self.monster,
            self.view.entities.get(1), self.row, self.f.fixture.now))

    def test_haste_uses_existing_local_factor_and_expiry_restores_both_axes(self):
        self.haste()
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 33, 1: 33}])
        self.f.fixture.now += self.row['duration_seconds']
        self.owner.tick(self.f.fixture.now)
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 0, 1: 0}])

    def test_haste_clear_restores_live_actor_without_status_owner_access(self):
        self.haste()
        self.view.drain(1)
        self.owner.forget(self.entity.uid)
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 0, 1: 0}])

    def test_owner_close_restores_live_actor_and_releases_speed_contribution(self):
        self.haste()
        self.view.drain(1)
        self.owner.close()
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 0, 1: 0}])
        self.assertFalse(any(row[1] == 'monster_skills'
            for row in self.view.events._callbacks.get('npc_speed_factors', ())))

    def test_berserk_public_ai_reader_and_clear_expiry_project_same_existing_cadence(self):
        self.magic.apply_status(self.entity.uid, 'berserk', self.now, 5,
            target_ref=self.entity.ref, params={'interval_multiplier': .5})
        self.view.events.emit('tick', self.now)
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 100, 1: 100}])
        self.f.fixture.now += 5
        self.view.events.emit('tick', self.f.fixture.now)
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 0, 1: 0}])
        self.magic.apply_status(self.entity.uid, 'berserk', self.f.fixture.now, 5,
            target_ref=self.entity.ref, params={'interval_multiplier': .5})
        self.view.events.emit('tick', self.f.fixture.now)
        self.view.drain(1)
        self.magic.npc_statuses[self.entity.uid]['effects'].clear()
        self.view.events.emit('tick', self.f.fixture.now)
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 0, 1: 0}])

    def test_haste_and_separate_magic_move_attack_factors_compose_once(self):
        self.magic.apply_status(self.entity.uid, 'berserk', self.now, 20,
            target_ref=self.entity.ref, params={'interval_multiplier': .5})
        self.magic.apply_status(self.entity.uid, 'entangle', self.now, 20,
            target_ref=self.entity.ref, params={'move_multiplier': 2})
        self.haste()
        self.assertEqual(self.speeds(self.view.drain(1)), [{0: 33, 1: 167}])

    def test_new_observer_replays_existing_haste_after_npc_spawn(self):
        self.haste()
        self.view.drain(1)
        wires = peers.bind(self.view, 2, 100, 101)
        self.assertEqual(self.speeds(wires), [{0: 33, 1: 33}])
        spawn_index = None
        for index, wire in enumerate(wires):
            if int.from_bytes(wire[2:4], 'little') == 0x4e96:
                with pb.parse_message(wire[4:-2]) as message:
                    fields = {field.number: field.value for field in message.fields}
                    if fields[2] == self.entity.uid:
                        spawn_index = index
        speed_index = next(index for index, wire in enumerate(wires)
            if (value := speed_values(wire)) is not None and value[0] == self.entity.uid)
        self.assertIsNotNone(spawn_index)
        self.assertLess(spawn_index, speed_index)

    def test_dead_or_stale_actor_receives_no_speed_replay(self):
        self.haste()
        self.view.drain(1)
        previous = self.entity.ref
        self.view.spawner.mark_dead(self.entity.uid, self.now)
        self.owner.tick(self.now)
        self.view.events.emit('npc_speed_changed', previous, self.now)
        self.view.events.emit('tick', self.now)
        self.assertEqual(self.speeds(self.view.drain(1)), [])


if __name__ == '__main__':
    unittest.main()
