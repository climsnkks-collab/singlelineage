"""Core equipment contract and local weapon-proc consumers; no socket/client."""
from dataclasses import replace
import random
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import world_combat as wc
from tools.local_original_session import world_feature_weapon_effects as fx
from tools.local_original_session import world_visibility, world_stats, world_registry
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_ai_tests import GridTerrain, status_fields


def weakness(template, monster):
    """Proc element x target weakness, as the feature applies it (monster weakness)."""
    element = {'earth': 1, 'fire': 2, 'water': 4, 'wind': 8}.get(fx.PROCS[template][6], 0)
    return wc.elemental_weakness_multiplier(element, monster.weak_attr)


class WeaponProcTests(unittest.TestCase):
    def setUp(self):
        self.now, self.template, self.enchant = 100., 342, 0
        data = load_m1()
        data = replace(data, spawns=tuple(row for row in data.spawns if row.group_id == 'm1_orc'))
        self.world = world_visibility.WorldView.create(data=data, terrain=GridTerrain(),
            clock=lambda: self.now, rng=random.Random(3))
        fields = status_fields(500)
        fields[12], fields[13] = 0, 100
        self.world.bind_pc(1, wc.PcProfile(30, 3, 0, 13, 13), fields)
        self.world.update_pc(1, 0, 32590, 32880, reset=True)
        self.target = self.world.entities.get(self.world.spawner.groups[0].slots[0].uid)
        self.world.spawner.set_hp(self.target.uid, 10000)
        self.world.update_pc(1, 0, self.target.x-1, self.target.y)
        self.world.drain(1)
        self.hooks = {}
        def fold(name, value, *args):
            return self.hooks[name](value, *args) if name in self.hooks else value
        def stats(position, *, level):
            worn = () if self.template is None else (world_stats.EquippedItem(
                self.world.data.items[self.template], enchant=self.enchant),)
            base = world_stats.CharacterStats(level, 3, world_stats.Attributes(13, 13, 18, 13, 13, 13))
            return world_stats.calculate_stats(base, worn), worn, {}
        writer = object()
        self.ctx = NS(world=self.world, _world_pcs={1: (writer, 1)},
            realm=NS(service=lambda w: NS(snapshot=lambda: NS(uid=1))),
            _world_stats_for=stats, fold_sync_hooks=fold, has_hooks=lambda name: name in self.hooks)
        fx._world_weapon_effects_initialize(self.ctx)

    def tearDown(self):
        self.world.close()

    def attack(self, *, landed=True, damage=1, roll=1):
        with patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(landed, damage)), \
                patch.object(self.world.combat.rng, 'randint', return_value=roll):
            return self.world.pc_attack(1, self.target.uid)

    def events(self):
        return self.ctx._world_weapon_effects_events

    def prepare_bow_owner(self, template, arrows):
        from tools.local_original_session import inventory, world_feature_combat as combat
        from tools.local_original_session.broker import INVENTORY_STARTER_FIELDS
        self.template = template
        self.ctx._world = self.world
        self.ctx._inventory_kit_policy = inventory.KIT_POLICY
        self.ctx._item_equipment_effect = NS(combat_inputs=lambda uid: (self.world.data.items[self.template], 0))
        self.ctx._world_attack_errors = []
        self.ctx.inventory_frame = inventory.build_kit_frame([
            {**INVENTORY_STARTER_FIELDS, 1: 91, 2: 29, 4: arrows}])
        self.costs = []
        def consume(writer, uid, count):
            rows = [dict(row.raw_fields) for row in inventory.validate_kit_frame(self.ctx.inventory_frame)]
            row = next(row for row in rows if row[1] == uid)
            if row[4] < count:
                raise ValueError('FIXTURE_ARROW_EXHAUSTED')
            row[4] -= count
            self.ctx.inventory_frame = inventory.build_kit_frame(rows)
            self.costs.append((uid, count))
            return b'fixture-cost'
        self.ctx._world_consume_kit = consume
        self.hooks['bow_ammunition'] = lambda *args: fx._world_weapon_bow_ammunition(self.ctx, *args)
        self.world.prepare_pc_attack = lambda *args: combat._world_prepare_pc_attack(self.ctx, *args)

    def projectiles(self, wires):
        from tools.local_entry_server import protobuf as pb
        result = []
        for wire in wires:
            if int.from_bytes(wire[2:4], 'little') == 0x4e31:
                with pb.parse_message(wire[4:-2]) as message:
                    result.append(next((f.value for f in message.fields if f.number == 7), None))
        return result

    def test_sayha_real_arrow_first_miss_cost_once_then_virtual_no_uid_cost(self):
        self.prepare_bow_owner(568, 1)
        self.assertEqual(self.projectiles(self.attack(landed=False, damage=0)), [66])
        self.assertEqual(self.costs, [(91, 1)])
        self.attack()  # cadence refusal does not consume twice
        self.assertEqual(self.costs, [(91, 1)])
        self.now += 10
        self.assertEqual(self.projectiles(self.attack()), [2349])
        self.assertEqual(self.costs, [(91, 1)])
        self.now += 10
        self.world.entities.move(1, 0, self.target.x-30, self.target.y)
        self.assertEqual(self.projectiles(self.attack()), [])
        self.assertEqual(self.costs, [(91, 1)])

    def test_virtual_arrow_die_damage_and_no_arrow_moonbow_refusal(self):
        from tools.local_original_session import world_ammo
        self.prepare_bow_owner(568, 0)
        proposal = fx._world_weapon_bow_ammunition(self.ctx,
            world_ammo.AttackPreparation(False), 1, self.world.data.items[568], (), self.target, self.now)
        self.assertTrue(proposal.allowed)
        self.assertIsNone(proposal.cost)
        self.assertEqual((proposal.arrow.small, proposal.arrow.large), (15, 15))
        high = NS(randint=lambda a, b: b)
        profile = wc.PcProfile(30, 2, 0, 13, 18)
        monster = self.world.spawner.slot_for(self.target.uid)[0].monster
        self.assertEqual(wc.pc_hits_npc(profile, monster, high, arrow=proposal.arrow).damage,
                         15+wc.DEX_DMG[18])
        self.template = 2072
        self.assertEqual(self.projectiles(self.attack()), [])
        self.assertEqual(self.costs, [])
        self.assertEqual(self.events(), [])

    def test_moonbow_real_ammo_and_separate_arrow_proc_probability_zero_damage(self):
        self.prepare_bow_owner(2072, 3)
        before = self.world.spawner.slot_for(self.target.uid)[1].hp
        self.assertEqual(self.projectiles(self.attack(roll=11)), [66])
        self.assertEqual(self.events(), [])
        self.now += 10
        wires = self.attack(roll=10)
        self.assertEqual(self.projectiles(wires), [66, 6288])
        self.assertNotIn(0x4ed8, [int.from_bytes(w[2:4], 'little') for w in wires])
        self.assertEqual(self.events()[-1]['damage'], 0)
        self.assertEqual(self.costs, [(91, 1), (91, 1)])
        self.assertEqual(before-self.world.spawner.slot_for(self.target.uid)[1].hp, 2)
        self.now += 10
        self.assertEqual(self.projectiles(self.attack(landed=False, damage=0)), [66])
        self.assertEqual(len(self.events()), 1)

    def test_bow_proposal_exclusion_and_cost_commit_failure_never_fire(self):
        self.prepare_bow_owner(568, 1)
        del self.hooks['bow_ammunition']
        self.assertEqual(self.projectiles(self.attack()), [])
        self.hooks['bow_ammunition'] = lambda *args: fx._world_weapon_bow_ammunition(self.ctx, *args)
        def fail(*args):
            raise ValueError('fixture commit failed')
        self.ctx._world_consume_kit = fail
        self.assertEqual(self.projectiles(self.attack()), [])
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, 0)
        self.assertEqual(self.ctx._world_attack_errors, ['fixture commit failed'])

    def test_each_numeric_proc_hit_miss_and_probability_boundary(self):
        for template, spec in fx.PROCS.items():
            with self.subTest(template=template):
                self.template = template
                before = len(self.events())
                self.now += 10
                self.attack(landed=False, damage=0)
                self.assertEqual(len(self.events()), before)
                self.now += 10
                self.attack(roll=spec[1]+1)
                self.assertEqual(len(self.events()), before)
                self.now += 10
                wires = self.attack(damage=1, roll=spec[1])
                event = self.events()[-1]
                self.assertEqual(event['effect'], spec[0])
                self.assertEqual(event['damage'] > 0, template != 2072)
                self.assertEqual(0x4ed8 in [int.from_bytes(w[2:4], 'little') for w in wires],
                                 template != 2072)

    def test_proc_mr_element_and_immunity_contributor(self):
        self.template = 3020
        self.hooks['weapon_proc_defense'] = lambda value, *args: dict(value, immune=True)
        self.attack()
        self.assertEqual(self.events()[-1]['damage'], 0)
        self.assertEqual(fx.reduce_proc_damage(100, dict(mr=100, resistance=20)), 40)
        self.assertEqual(fx.reduce_proc_damage(100, dict(mr=150, resistance=0)), 44)

    def test_exact_sql_int_and_zero_gate_arithmetic(self):
        low = NS(randint=lambda a, b: a)
        high = NS(randint=lambda a, b: b)
        self.assertEqual(fx.proc_damage(fx.PROCS[1094], 1, 0, low), 96)
        self.assertEqual(fx.proc_damage(fx.PROCS[1094], 1, 0, high), 150)
        self.assertEqual(fx.proc_damage(fx.PROCS[2072], 99, 99, high), 0)
        self.assertAlmostEqual(fx.proc_damage(fx.PROCS[1096], 1, 0, low), 31*1.8*1.5)
        self.assertAlmostEqual(fx.proc_damage(fx.PROCS[3020], 30, 20, high, berserk=True),
                               50*3.2+49*3)

    def test_single_target_hp_consumes_exact_physical_plus_reduced_proc(self):
        self.template = 1094
        before = self.world.spawner.slot_for(self.target.uid)[1].hp
        monster = self.world.spawner.slot_for(self.target.uid)[0].monster
        expected = fx.reduce_proc_damage(96 * weakness(1094, monster), dict(mr=monster.mr, resistance=0))
        self.attack(damage=7, roll=1)
        self.assertEqual(before-self.world.spawner.slot_for(self.target.uid)[1].hp, 7+expected)
        self.assertEqual(self.events()[-1]['damage'], expected)

    def test_mana_drain_core_equipment_actual_resource_and_status(self):
        wires = self.attack()
        event = self.events()[-1]
        self.assertEqual(event['drained'], 1)
        self.assertEqual(self.world.combat.mp_of(1), 1)
        self.assertEqual(event['npc_mp_before']-event['npc_mp_after'], 1)
        self.assertIn(0x4e38, [int.from_bytes(w[2:4], 'little') for w in wires])

    def test_mana_clamps_and_missing_weapon_and_unknowns_remain_inactive(self):
        self.world.combat.pcs[1].status_fields[12] = 100
        self.attack()
        self.assertEqual(self.events()[-1]['total_gained'] if 'total_gained' in self.events()[-1]
                         else self.events()[-1]['mp_after']-self.events()[-1]['mp_before'], 0)
        before = len(self.events())
        for template in (None, 11, 568, 789, 3018):
            self.template = template
            self.now += 10
            self.attack()
        self.assertEqual(len(self.events()), before)
        result = {}
        fx._world_weapon_effects_report(self.ctx, result)
        self.assertEqual(set(result['weapon_effects']['unknown']), {789, 3018})

    def test_cold_chaser_local_radius_three_uses_normal_damage_lifetime(self):
        self.template = 3019
        candidates = [self.world.entities.get(slot.uid) for group in self.world.spawner.groups
                      for slot in group.slots if slot.uid != self.target.uid]
        other = candidates[0]
        self.world.entities.move(other.uid, self.target.map_id, self.target.x+1, self.target.y)
        before = self.world.spawner.slot_for(other.uid)[1].hp
        self.attack()
        self.assertGreaterEqual(self.events()[-1]['victim_count'], 2)
        self.assertLess(self.world.spawner.slot_for(other.uid)[1].hp, before)

    def test_cold_chaser_radius_boundary_secondary_death_reward_and_fixed_main_roll(self):
        self.template = 3019
        candidates = [self.world.entities.get(slot.uid) for group in self.world.spawner.groups
                      for slot in group.slots if slot.uid != self.target.uid]
        inside, outside = candidates[:2]
        self.world.entities.move(inside.uid, self.target.map_id, self.target.x+3, self.target.y)
        self.world.entities.move(outside.uid, self.target.map_id, self.target.x+4, self.target.y)
        self.world.spawner.set_hp(inside.uid, 1)
        outside_hp = self.world.spawner.slot_for(outside.uid)[1].hp
        self.world.exp[1] = self.world.data.pc_exp[29]
        original_exp = self.world.exp[1]
        before = self.world.spawner.slot_for(self.target.uid)[1].hp
        self.attack(roll=1)
        event = self.events()[-1]
        monster = self.world.spawner.slot_for(self.target.uid)[0].monster
        expected = fx.reduce_proc_damage(event['rolled'] * weakness(3019, monster),
                                         dict(mr=monster.mr, resistance=0))
        self.assertEqual(before-self.world.spawner.slot_for(self.target.uid)[1].hp, 1+expected)
        self.assertFalse(inside.alive)
        self.assertEqual(self.world.spawner.slot_for(outside.uid)[1].hp, outside_hp)
        self.assertTrue(any(kill.npc_uid == inside.uid for kill in self.world.combat.kills))
        self.assertGreater(self.world.exp[1], original_exp)

    def test_haste_potion_overlap_brave_remove_and_magic_separate_multipliers(self):
        self.template = 144
        rate = self.world.data.items[17].buff.rate
        state = self.world.combat.pcs[1]
        self.assertAlmostEqual(self.world.combat.speed_factor(1, self.now), rate)
        state.buffs['haste'] = (self.now+100, rate)
        state.buffs['brave'] = (self.now+100, rate)
        self.assertAlmostEqual(self.world.combat.speed_factor(1, self.now), rate*rate)
        self.template = 342
        self.assertAlmostEqual(self.world.combat.speed_factor(1, self.now), rate*rate)
        state.buffs.clear()
        self.template = 144
        self.hooks['consumable_magic_provider'] = lambda *args: None
        self.assertAlmostEqual(self.world.combat.speed_factor(1, self.now), rate)
        from tools.local_original_session import world_magic_status as status
        magic_effects = {}
        status.apply(magic_effects, 'slow', self.now, 100, params={'interval_multiplier': 2})
        status.apply(magic_effects, 'berserk', self.now, 100, params={'interval_multiplier': .5})
        def magic_speed(base):
            return lambda uid, now: base(uid, now)*status.ai_status(magic_effects, now)['attack_factor']
        handle = self.world.runtime_extensions.wrap('magic', self.world.combat, 'speed_factor', magic_speed)
        self.assertAlmostEqual(self.world.combat.speed_factor(1, self.now), rate)
        del magic_effects['berserk']
        self.assertAlmostEqual(self.world.combat.speed_factor(1, self.now), rate*2)
        self.template = None
        self.assertAlmostEqual(self.world.combat.speed_factor(1, self.now), 2)
        handle.close()

    def test_not_direct_spell_or_nonphysical_damage_and_no_context_leak(self):
        self.template = 3020
        group, slot = self.world.spawner.slot_for(self.target.uid)
        self.world._apply_monster_swing(1, 1, self.target, group.monster, slot.hp, wc.Swing(True, 1), self.now)
        self.assertEqual(self.events(), [])
        with patch.object(wc, 'pc_hits_npc', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                self.world.pc_attack(1, self.target.uid)
        self.world._apply_monster_swing(1, 1, self.target, group.monster, slot.hp, wc.Swing(True, 1), self.now)
        self.assertEqual(self.events(), [])

    def test_exclusion_and_shutdown_restore_prior_owners(self):
        from tools.local_original_session.world_handlers import CORE_MODULES, FEATURE_MODULES
        modules = tuple(m for m in FEATURE_MODULES if m != 'world_feature_weapon_effects')
        self.assertNotIn('_world_weapon_effects_initialize', world_registry.build_registry(CORE_MODULES+modules).methods)
        self.assertNotIn('_world_weapon_effects_initialize', world_registry.build_registry(CORE_MODULES).methods)
        self.world.close()
        self.attack()
        self.assertEqual(self.events(), [])


if __name__ == '__main__':
    unittest.main()
