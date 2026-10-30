"""Pure town visibility, recovery cadence and broker seam regressions.

In-memory registry/scheduler and existing codecs only; no broker, socket, game,
native initialization, saved profile or user-play resources.
"""
from dataclasses import replace
import random
import unittest
from unittest.mock import Mock

from tools.local_game_session import session
from tools.local_original_session import world_combat as wc
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_ammo import AttackPreparation, L1J_ARROWS
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import Group, InterestSpawner, Slot, SlotState
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_town import TownConfig, TownNpcs, attach_view, confirmed_npc_ids, load_town
from tools.local_original_session.world_visibility import WorldView


class Terrain:
    def passable(self, *_):
        return True

    def can_step(self, *_):
        return True


class WorldVisibilityRegressionTests(unittest.TestCase):
    def make(self):
        self.now = 100.0
        data = replace(load_m1(), spawns=())
        runtime = WorldRuntime(clock=lambda: self.now)
        view = WorldView(runtime, InterestSpawner(runtime.entities, data, passable=lambda *_: True), Terrain(),
                         data=data, rng=random.Random(7))
        return view

    def bind(self, view, x=100, y=100):
        fields = {1: 1, 2: 10, 4: 13, 5: 13, 6: 10, 7: 15,
                  8: 12, 9: 10, 10: 30, 11: 30, 12: 2, 13: 10, 14: -10,
                  15: 0, 16: 0, 17: 0, 18: 0, 20: 0}
        view.bind_pc(1, wc.PcProfile(10, 1, 0, 13, 13, weapon=wc.ATHAME,
                                     con=12, wis=15), fields)
        return view.update_pc(1, 0, x, y, reset=True)

    def target(self, view):
        data = load_m1()
        monster = data.monsters[data.spawns[0].template_id]
        entity = view.entities.add(Kind.NPC, 0, 103, 100, template_id=monster.template_id)
        slot = Slot(0, SlotState.ALIVE, entity.uid, 10000, (103, 100))
        view.spawner._slots[entity.uid] = (Group(data.spawns[0], monster, [slot], True), slot)
        return entity, slot

    def product_town(self, view):
        data = load_town()
        return TownNpcs(view.entities, data,
                        TownConfig(candidate_npc_ids=confirmed_npc_ids(data)))

    def test_confirmed_catalog_defaults_and_unknown_candidate_optin(self):
        view = self.make()
        town = self.product_town(view)
        selected = town.register()
        self.assertEqual({town.npc_for(e.uid).npc_id for e in selected},
                         {70523, 70525, 70100, 70101, 70102, 70529, 70538, 70537})  # +Farlin (NPC appearance)
        self.assertTrue(all(town.appearance(e.uid).sprite_id is not None for e in selected))
        self.assertEqual(town.register(), ())
        added = town.register(TownConfig(candidate_npc_ids=confirmed_npc_ids(town.data) | {70014}))
        self.assertEqual([town.npc_for(e.uid).npc_id for e in added], [70014])
        self.assertIsNone(town.appearance(added[0].uid).sprite_id)
        self.assertFalse(any(town.npc_for(e.uid).spawn['count'] == 0 for e in view.entities))

    def test_town_enter_exit_reset_disable_reuses_actor_remove_codecs(self):
        view = self.make()
        attach_view(view, self.product_town(view))
        entities = view.town.register()
        radars = [e for e in entities if view.town.npc_for(e.uid).npc_id == 70523]
        radar, = radars
        frames = self.bind(view, radar.x, radar.y)
        actors = [session.world.decode_payload(0x4e96, f[4:-2]) for f in frames]
        actor = next(row for row in actors if row[2] == radar.uid)
        self.assertEqual((actor[3], actor[5], actor[9]),
                         (988, radar.heading, '가죽 세공사^라다르'))
        self.assertNotIn(39, actor)
        self.assertEqual(view.update_pc(1, 0, radar.x, radar.y), [])
        exit_frames = view.update_pc(1, 1, radar.x, radar.y)
        self.assertEqual(len(exit_frames), len(frames))
        self.assertTrue(all(int.from_bytes(f[2:4], 'little') == 0x4e40 for f in exit_frames))
        self.assertEqual(len(view.update_pc(1, 0, radar.x, radar.y, reset=True)), len(frames))
        view.town.register(TownConfig(candidate_npc_ids=confirmed_npc_ids(view.town.data),
                                     disabled_npc_ids={70523}))
        removed = view.update_pc(1, 0, radar.x, radar.y)
        self.assertEqual(len(removed), 1)
        self.assertEqual(int.from_bytes(removed[0][2:4], 'little'), 0x4e40)
        self.assertNotIn(radar.uid, view.visibility.known[1])
        view.close()
        self.assertTrue(view.closed)
        self.assertFalse(any(e.kind is Kind.NPC for e in view.entities))
        self.assertIsNotNone(view.entities.get(1))  # broker still persists the PC

    def test_unknown_sprite_optin_does_not_invent_actor(self):
        view = self.make()
        attach_view(view, TownNpcs(view.entities, load_town(), TownConfig(enable_candidates=True)))
        view.town.register()
        pandora = next(e for e in view.entities if view.town.npc_for(e.uid).npc_id == 70014)
        frames = self.bind(view, pandora.x, pandora.y)
        self.assertNotIn(pandora.uid,
                         [session.world.decode_payload(0x4e96, f[4:-2])[2] for f in frames])

    def test_poll_jitter_keeps_original_hp_mp_cadence(self):
        view = self.make()
        self.bind(view)
        view.combat.pcs[1].hp = 20
        start, statuses = self.now, []
        for _ in range(220):  # Existing LifeTests uses the same 150 ms polling.
            self.now += .15
            view.runtime.scheduler.run_due(self.now)
            for frame in view.drain(1):
                statuses.append((round(self.now - start),
                                 session.world.decode_payload(0x4e38, frame[4:-2])))
        hp = [(t, fields[10]) for t, fields in statuses if t < 13]
        self.assertEqual(hp, [(3, 23), (6, 26), (9, 29), (12, 30)])
        self.assertEqual([(t, fields[12]) for t, fields in statuses if t >= 13],
                         [(16, 4), (32, 6)])

    def test_large_delay_does_not_replay_or_compress_next_interval(self):
        view = self.make()
        self.bind(view)
        self.now = 110.0
        self.assertEqual(view.runtime.scheduler.run_due(), 1)
        state = view.combat.pcs[1]
        points = (state.hp_points, state.mp_points)
        self.assertEqual(view.regen[1].at, 111.0)
        self.now = 110.15
        self.assertEqual(view.runtime.scheduler.run_due(), 0)
        self.assertEqual((state.hp_points, state.mp_points), points)
        self.now = 111.0
        self.assertEqual(view.runtime.scheduler.run_due(), 1)

    def test_delay_beyond_runtime_poll_waits_full_recovery_interval(self):
        for delay in (.4, .9):
            with self.subTest(delay=delay):
                view = self.make()
                self.bind(view)
                due = view.regen[1].at
                self.now = due + delay
                self.assertEqual(view.runtime.scheduler.run_due(), 1)
                state = view.combat.pcs[1]
                points = (state.hp_points, state.mp_points)
                next_at = self.now + view.combat.regen.tick_ms / 1000
                self.assertAlmostEqual(view.regen[1].at, next_at)
                self.now = due + 1
                self.assertEqual(view.runtime.scheduler.run_due(), 0)
                self.assertEqual((state.hp_points, state.mp_points), points)
                self.now = next_at
                self.assertEqual(view.runtime.scheduler.run_due(), 1)

    def test_attack_prepare_after_admission_and_arrow_forwarded_once(self):
        view = self.make()
        self.bind(view)
        target, slot = self.target(view)
        self.assertEqual(view.pc_attack(1, target.uid), [])  # default melee reach
        prepare = view.prepare_pc_attack = Mock(return_value=AttackPreparation(False))
        self.assertEqual(view.pc_attack(1, target.uid), [])
        self.assertEqual(slot.hp, 10000)
        prepare.assert_called_once_with(1, target, self.now)
        arrow = L1J_ARROWS[40743]
        prepare.return_value = AttackPreparation(True, arrow=arrow)
        swing = view.combat.try_pc_swing = Mock(return_value=wc.Swing(True, 3))
        hit = view.on_npc_hit = Mock()
        self.assertTrue(view.pc_attack(1, target.uid))
        swing.assert_called_once_with(1, view.spawner.monster_for(target.uid), self.now, arrow=arrow)
        hit.assert_called_once_with(target.uid)
        self.assertEqual(slot.hp, 9997)
        view.combat.pcs[1].next_attack_at = self.now + 10
        prepare.reset_mock()
        self.assertEqual(view.pc_attack(1, target.uid), [])
        prepare.assert_not_called()

    def test_death_callback_precedes_own_death_and_can_replace_hp0(self):
        view = self.make()
        self.bind(view)
        view._queue(1, b'old-hp0')

        def died(uid):
            self.assertEqual(view.outbox[uid], [b'old-hp0'])
            view.outbox[uid][-1] = b'committed-hp0'

        view.on_pc_death = died
        view._pc_died(1, self.now)
        frames = view.drain(1)
        self.assertEqual(frames[0], b'committed-hp0')
        self.assertEqual(int.from_bytes(frames[1][2:4], 'little'), 0x4e39)
        self.assertNotIn(1, view.regen)


if __name__ == '__main__':
    unittest.main(verbosity=2)
