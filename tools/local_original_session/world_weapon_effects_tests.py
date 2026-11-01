"""Offline effect/resource contracts; no port, client, or saved profile writes."""
from dataclasses import replace
import random
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import world_combat as wc
from tools.local_original_session import world_feature_weapon_effects as effects
from tools.local_original_session import world_npc_resources as resources
from tools.local_original_session import world_registry, world_visibility
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_ai_tests import GridTerrain, status_fields
from tools.local_original_session.world_entities import EntityRegistry, Kind


class NpcResourceTests(unittest.TestCase):
    def setUp(self):
        self.entities = EntityRegistry()
        self.target = self.entities.add(Kind.NPC, 0, 1, 1)
        self.owner = resources.NpcResources(self.entities)

    def test_several_consumers_share_one_balance_and_life_cap(self):
        ref = self.target.ref
        self.assertEqual(self.owner.drain_mana(ref, 50, 9), 9)
        self.assertEqual(self.owner.mana_of(ref, 50), 41)
        self.assertEqual(self.owner.drain_mana(ref, 50, 100), 31)
        self.assertEqual(self.owner.drain_mana(ref, 50, 1), 0)
        self.assertEqual(self.owner.mana_of(ref, 50), 10)
        self.assertTrue(self.owner.spend_mana(ref, 50, 6))
        self.assertFalse(self.owner.spend_mana(ref, 50, 5))
        self.assertEqual(self.owner.mana_of(ref, 50), 4)
        self.assertEqual(self.owner.drain_mana(ref, 50, 1), 0)

    def test_current_mp_clamp_negative_and_zero(self):
        ref = self.target.ref
        self.assertEqual(self.owner.drain_mana(ref, 2, -1), 0)
        self.assertEqual(self.owner.drain_mana(ref, 2, 9), 2)
        self.assertEqual(self.owner.drain_mana(ref, 2, 9), 0)

    def test_stale_generation_does_not_share_a_balance(self):
        ref = self.target.ref
        self.owner.drain_mana(ref, 10, 3)
        self.entities.kill(self.target.uid)
        self.assertEqual(self.owner.drain_mana(ref, 10, 2), 0)
        self.owner.prune()
        self.assertEqual(self.owner._mana, {})
        other = self.entities.add(Kind.NPC, 0, 1, 1)
        self.assertEqual(self.owner.mana_of(other.ref, 10), 10)
        self.owner.forget(other.uid)
        self.assertEqual(self.owner._mana, {})

    def test_install_reuses_owner_and_releases_on_death_and_close(self):
        from tools.local_original_session.world_extensions import WorldEvents
        world = NS(entities=self.entities, extensions={}, events=WorldEvents())
        first = resources.install(world)
        self.assertIs(resources.install(world), first)
        first.drain_mana(self.target.ref, 10, 1)
        world.events.emit('npc_died', self.target.uid, 100)
        self.assertEqual(first._mana, {})
        first.mana_of(self.target.ref, 10)
        world.events.emit('close')
        self.assertEqual(first._mana, {})


class WeaponEffectTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.
        data = load_m1()
        data = replace(data, spawns=tuple(row for row in data.spawns if row.group_id == 'm1_orc'))
        self.world = world_visibility.WorldView.create(data=data, terrain=GridTerrain(),
            clock=lambda: self.now, rng=random.Random(3))
        fields = status_fields(500)
        fields[12], fields[13] = 0, 100
        self.world.bind_pc(1, wc.PcProfile(1, 3, 0, 13, 13,
            weapon=replace(wc.ATHAME, enchant=0)), fields)
        self.world.update_pc(1, 0, 32590, 32880, reset=True)
        self.target = self.world.entities.get(self.world.spawner.groups[0].slots[0].uid)
        self.world.update_pc(1, 0, self.target.x - 1, self.target.y)
        self.world.drain(1)
        self.weapon = data.items[342]
        self.ctx = NS(world=self.world,
            _item_equipment_effect=NS(combat_inputs=lambda uid: (self.weapon, 0)))
        # The feature now reads the mandatory core selection/stats contract.
        # Keep the old fixture's equipment switch and every game expectation.
        from tools.local_original_session import world_stats
        writer = object()
        self.ctx._world_pcs = {id(writer): (writer, 1)}
        self.ctx.realm = NS(service=lambda _: NS(snapshot=lambda: NS(uid=1)))
        def stats(position, *, level):
            worn = () if self.ctx._item_equipment_effect is None else (
                world_stats.EquippedItem(self.weapon, enchant=0),)
            base = world_stats.CharacterStats(level, 3, world_stats.Attributes(13, 13, 13, 13, 13, 13))
            return world_stats.calculate_stats(base, worn), worn, {}
        self.ctx._world_stats_for = stats
        self.ctx.fold_sync_hooks = lambda name, value, *args: value
        self.ctx.has_hooks = lambda name: False
        effects._world_weapon_effects_initialize(self.ctx)

    def tearDown(self):
        self.world.close()

    def attack(self, swing=wc.Swing(True, 1)):
        with patch.object(wc, 'pc_hits_npc', return_value=swing):
            return self.world.pc_attack(1, self.target.uid)

    def events(self):
        result = {}
        effects._world_weapon_effects_report(self.ctx, result)
        return result['weapon_effects']['events']

    def test_hit_debits_actual_npc_mp_and_publishes_pc_status(self):
        wires = self.attack()
        event = self.events()[-1]
        self.assertGreater(event['drained'], 0)
        self.assertEqual(event['mp_after'] - event['mp_before'], event['drained'])
        self.assertEqual(event['npc_mp_before'] - event['npc_mp_after'], event['drained'])
        self.assertEqual(self.world.combat.pcs[1].mp, event['drained'])
        self.assertIn(0x4e38, [int.from_bytes(wire[2:4], 'little') for wire in wires])

    def test_miss_cadence_and_out_of_range_do_not_drain(self):
        self.attack(wc.Swing(False, 0))
        self.assertEqual(self.events(), [])
        self.attack()
        self.assertEqual(self.events(), [])  # same clock: cooldown admission fails
        self.now += 10
        self.world.update_pc(1, 0, self.target.x - 5, self.target.y)
        self.attack()
        self.assertEqual(self.events(), [])

    def test_ordinary_weapon_and_missing_equipment_do_not_drain(self):
        self.weapon = self.world.data.items[11]
        self.attack()
        self.assertEqual(self.events(), [])
        self.now += 10
        self.ctx._item_equipment_effect = None
        self.attack()
        self.assertEqual(self.events(), [])

    def test_spell_or_other_direct_damage_is_not_a_weapon_swing(self):
        group, slot = self.world.spawner.slot_for(self.target.uid)
        self.world._apply_monster_swing(1, 1, self.target, group.monster,
                                       slot.hp, wc.Swing(True, 1), self.now)
        self.assertEqual(self.events(), [])

    def test_depleted_mp_does_not_regenerate_on_later_hits(self):
        total = 0
        for _ in range(10):
            self.attack()
            self.now += 10
            total += self.events()[-1]['drained']
        initial = self.world.spawner.slot_for(self.target.uid)[0].monster.mp
        self.assertEqual(total, initial)
        self.assertEqual(self.world.combat.pcs[1].mp, initial)
        self.assertEqual(self.events()[-1]['drained'], 0)

    def test_full_pc_mp_still_drains_but_never_exceeds_max(self):
        state = self.world.combat.pcs[1]
        state.status_fields[12] = state.max_mp
        self.attack()
        event = self.events()[-1]
        self.assertGreater(event['drained'], 0)
        self.assertEqual(state.mp, state.max_mp)
        self.assertEqual(event['mp_before'], event['mp_after'])

    def test_lethal_hit_drains_before_npc_lifetime_cleanup(self):
        ref = self.target.ref
        self.attack(wc.Swing(True, 100000))
        self.assertGreater(self.events()[-1]['drained'], 0)
        self.assertNotIn(ref, self.world.extensions['npc_resources']._mana)

    def test_runtime_wrappers_compose_and_remove_in_either_owner_order(self):
        traces = []
        def outer(base):
            def call(*args):
                traces.append('other')
                return base(*args)
            return call
        other = self.world.runtime_extensions.wrap('other', self.world, 'pc_attack', outer)
        self.attack()
        self.assertTrue(self.events())
        self.assertEqual(traces, ['other'])
        self.world.close()  # weapon wrappers removed while other remains
        self.assertIn((id(self.world), 'pc_attack'), self.world.runtime_extensions._methods)
        other.close()
        self.assertNotIn((id(self.world), 'pc_attack'), self.world.runtime_extensions._methods)

    def test_exception_does_not_leave_a_physical_attack_context(self):
        with patch.object(wc, 'pc_hits_npc', side_effect=RuntimeError('test failure')):
            with self.assertRaisesRegex(RuntimeError, 'test failure'):
                self.world.pc_attack(1, self.target.uid)
        self.test_spell_or_other_direct_damage_is_not_a_weapon_swing()

    def test_feature_removed_preserves_plain_attack_without_absorption(self):
        # Removing the feature's runtime registrations restores the preceding
        # owners. This is the same attack implementation used when not installed.
        self.world.close()
        self.attack()
        self.assertEqual(self.world.combat.pcs[1].mp, 0)
        self.assertEqual(self.events(), [])


class PolicyTests(unittest.TestCase):
    def test_roll_negative_enchant_and_per_hit_cap(self):
        rng = NS(randint=lambda low, high: high)
        self.assertEqual(effects.mana_drain_roll(-3, rng), 0)
        self.assertEqual(effects.mana_drain_roll(-2, rng), 1)
        self.assertEqual(effects.mana_drain_roll(0, rng), 3)
        self.assertEqual(effects.mana_drain_roll(20, rng), 9)

    def test_optional_registration_and_core_only_remain_valid(self):
        from tools.local_original_session.world_handlers import CORE_MODULES, FEATURE_MODULES
        for omitted in (None, 'world_feature_weapon_effects', 'world_feature_magic'):
            enabled = tuple(module for module in FEATURE_MODULES if module != omitted)
            compiled = world_registry.build_registry(CORE_MODULES + enabled)
            self.assertEqual('_world_weapon_effects_initialize' in compiled.methods,
                             omitted != 'world_feature_weapon_effects')
        self.assertNotIn('_world_weapon_effects_initialize',
                         world_registry.build_registry(CORE_MODULES).methods)


if __name__ == '__main__':
    unittest.main()
