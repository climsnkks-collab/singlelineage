"""Pure transition policy and real map1/2 S32 coverage; no game/server runs."""
from dataclasses import FrozenInstanceError
import random
from types import MethodType, SimpleNamespace
import unittest

from tools.local_game_session import session
from tools.local_original_session import movement, world_maps as wm, world_terrain as wt
from tools.local_original_session.world_core_maps import _world_relocate_locked
from tools.local_original_session.world_visibility import MONSTER_BASE_FIELDS


class TransitionTests(unittest.TestCase):
    def test_explicit_destinations(self):
        cases = (
            ((0, 32478, 32851), (1, 32669, 32802, 4)),
            ((1, 32669, 32802), (0, 32477, 32853, 4)),
            ((1, 32737, 32877), (2, 32665, 32789, 4)),
            ((2, 32665, 32788), (1, 32738, 32877, 2)),
        )
        self.assertEqual(len(wm.TRANSITIONS), len(cases))
        for origin, destination in cases:
            self.assertEqual(wm.resolve_transition(*origin), wm.MapDestination(*destination))

    def test_adjacent_cells_and_wrong_maps_do_not_trigger(self):
        for map_id, x, y in wm.TRANSITIONS:
            for dx, dy in wt.DELTAS:
                self.assertIsNone(wm.resolve_transition(map_id, x + dx, y + dy))
            self.assertIsNone(wm.resolve_transition(77, x, y))
        self.assertIsNone(wm.resolve_transition(False, 32477, 32851))

    def test_native_destinations_are_not_triggers(self):
        self.assertIsNone(wm.resolve_transition(0, 32477, 32853))
        self.assertIsNone(wm.resolve_transition(0, 32478, 32853))
        # L1J floor2 arrival is one cell south of its return trigger.
        self.assertIsNone(wm.resolve_transition(2, 32665, 32789))
        self.assertIsNone(wm.resolve_transition(1, 32738, 32877))

    def test_immutable_policy_preserves_evidence_status(self):
        row = wm.TRANSITIONS[(0, 32478, 32851)]
        self.assertEqual(row.source, 'local_policy/client_s32+l1j')
        self.assertEqual(row.reference_origin, (0, 32477, 32851))
        self.assertEqual(row.native_trigger_status, 'UNKNOWN')
        self.assertTrue(row.ref.endswith('l1jdb_m10.sql:14930'))
        with self.assertRaises(TypeError):
            wm.TRANSITIONS[(0, 1, 1)] = row
        with self.assertRaises(FrozenInstanceError):
            row.destination.x = 1


class DungeonTerrainTests(unittest.TestCase):
    def test_adjusted_entrance_is_reachable_from_native_destination_vicinity(self):
        terrain = wt.WorldTerrain.load(map_ids=(0,))
        self.assertIs(terrain.can_stand(0, 32477, 32851), False)
        self.assertIsNone(wm.resolve_transition(0, 32477, 32851))
        for y in (32853, 32852):
            self.assertIs(terrain.can_step(0, 32478, y, 0), True)
        self.assertIsNotNone(wm.resolve_transition(0, 32478, 32851))

    def test_real_maps_load_and_passable_cells(self):
        for map_id, count, arrival, x_end in (
                (1, 12, (32669, 32802), 32768),
                (2, 16, (32665, 32789), 32832)):
            with self.subTest(map_id=map_id):
                terrain = wt.WorldTerrain.load(map_ids=(map_id,))
                self.assertEqual(len(terrain.sources), count)
                self.assertTrue(all(source.startswith(f'{map_id}/') for source in terrain.sources))
                self.assertIsNone(terrain.bounds(0))
                self.assertIsNotNone(terrain.half_flags(map_id, *arrival))
                # Reference spawn rectangles are search areas, not native map bounds.
                self.assertTrue(any(terrain.can_stand(map_id, x, y) is True
                                    for y in range(32768, 32896)
                                    for x in range(32640, x_end)))


class RelocationPublicationTests(unittest.TestCase):
    def test_same_map_and_cross_map_publish_full_map_self_and_nearby(self):
        def wire(opcode):
            return (6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little') + b'\0\0'

        for origin_map, target_map, map_exp, legacy_correction in (
                (0, 0, 0, False), (1, 1, 2, False),
                (1, 1, 2, True), (1, 1, 3, False), (0, 1, 2, False)):
            with self.subTest(origin_map=origin_map, target_map=target_map,
                              map_exp=map_exp, legacy_correction=legacy_correction):
                writer, game = object(), object()
                current = movement.Position(1, 'Knight', origin_map, 100, 100)
                service = SimpleNamespace(snapshot=lambda: current)

                def relocate(updated):
                    nonlocal current
                    current = updated

                service.relocate = relocate
                updates = []

                def frames_for(position, *, status_fields, heading):
                    actor = dict(MONSTER_BASE_FIELDS)
                    actor.update({1: position.packed, 2: position.uid, 3: 61, 4: 0,
                                  5: heading, 9: position.name, 16: True})
                    body = session.world.encode_payload(0x4e96, actor)
                    self_actor = ((len(body) + 6).to_bytes(2, 'little') + b'\x96\x4e'
                                  + body + b'\0\0')
                    return wire(0x4e95), wire(0x4e38), self_actor

                world = SimpleNamespace(
                    combat=SimpleNamespace(pcs={1: SimpleNamespace(hp=80, mp=10,
                        status_fields={10: 80, 12: 10})}),
                    terrain=SimpleNamespace(can_stand=lambda *args: True),
                    visibility=SimpleNamespace(known={1: {55}}),
                    item_known={1: {66}}, pc_known={1: set()},
                    drain=lambda uid: (wire(0x4f57),),
                    update_pc_and_drain=lambda uid, map_id, x, y, **kw:
                        updates.append((map_id, x, y, kw)) or (wire(0x4e96),))
                ctx = SimpleNamespace(_world=world, _world_map_exp=map_exp,
                    _world_map_transitions=0, owner_current=lambda *args: True,
                    realm=SimpleNamespace(service=lambda _: service, serves_map=lambda _: True,
                        registry=SimpleNamespace(resolve=lambda _: game), _world_frames={},
                        _frames_for=frames_for),
                    run_sync_hooks=lambda *args: None,
                    collect_sync_hooks=lambda *args: ())
                row = {'operation_lock': SimpleNamespace(locked=lambda: True)}
                clicked = []
                context = SimpleNamespace(commit_attempted=False,
                    begin_click=lambda: clicked.append(True))
                options = {'same_map_correction': True} if legacy_correction else {}
                result = _world_relocate_locked(ctx, writer, row, game,
                    wm.MapDestination(target_map, 200, 201, 4), context=context, **options)
                opcodes = [int.from_bytes(frame[2:4], 'little') for frame in result]
                self.assertEqual(opcodes, [0x4f57, 0x4e40, 0x4e40,
                                           0x4e95, 0x4e38, 0x4e96, 0x4e96])
                self.assertEqual((current.map_id, current.word0, current.word1),
                                 (target_map, 200, 201))
                self.assertEqual((updates[0][:3], updates[0][3]['reset'],
                                  updates[0][3]['actor_fields'][1]),
                                 ((target_map, 200, 201), True, current.packed))
                self.assertTrue(context.commit_attempted)
                self.assertEqual(clicked, [True])

    def test_same_and_cross_map_replay_speed_item_and_spell_icons_without_state_change(self):
        from tools.local_original_session import (game_data, world_combat, world_feature_items,
            world_feature_magic, world_handlers, world_item_effects, world_magic, world_registry)

        def wire(opcode):
            return (6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little') + b'\0\0'

        for origin_map, target_map, now in ((0, 0, 100), (0, 1, 100), (0, 0, 2000)):
            with self.subTest(origin_map=origin_map, target_map=target_map, now=now):
                writer, game = object(), object()
                current = movement.Position(1, 'Knight', origin_map, 100, 100)
                service = SimpleNamespace(snapshot=lambda: current)

                def relocate(updated):
                    nonlocal current
                    current = updated

                service.relocate = relocate
                combat = world_combat.WorldCombat(game_data.load_m1(), random.Random(7))
                pc = combat.bind_pc(1, world_combat.PcProfile(1, 1, 0, 13, 13),
                                    {10: 80, 11: 100, 12: 10, 13: 20})
                effects = world_item_effects.WorldItemEffects(combat)
                green = effects.use(1, 17, 100)
                brave = effects.use(1, 296, 100)
                self.assertEqual((green.outcome, brave.outcome), ('applied', 'applied'))
                magic = world_magic.PlayerMagic(world_magic.load_catalog())
                magic.state(1).buffs[7] = 160  # Holy Weapon
                magic_icons = {(1, 7): world_feature_magic.SPELL_BUFF_ICONS[7]}
                before = (dict(pc.buffs), dict(effects.state(1).potions),
                          dict(effects.icons[1]), dict(magic.state(1).buffs), dict(magic_icons))

                def frames_for(position, *, status_fields, heading):
                    actor = dict(MONSTER_BASE_FIELDS)
                    actor.update({1: position.packed, 2: position.uid, 3: 61, 4: 0,
                                  5: heading, 9: position.name, 16: True})
                    body = session.world.encode_payload(0x4e96, actor)
                    return (wire(0x4e95), wire(0x4e38),
                            (len(body) + 6).to_bytes(2, 'little') + b'\x96\x4e' + body + b'\0\0')

                world = SimpleNamespace(combat=combat, entities={},
                    runtime=SimpleNamespace(clock=lambda: now),
                    terrain=SimpleNamespace(can_stand=lambda *args: True),
                    visibility=SimpleNamespace(known={}), item_known={}, pc_known={},
                    drain=lambda uid: (), update_pc_and_drain=lambda *args, **kwargs: (wire(0x4e96),))
                ctx = SimpleNamespace(world=world, _world=world, _world_map_exp=2,
                    _world_map_transitions=0, _world_item_effects=effects,
                    _world_magic=magic, _world_magic_buff_ui=True, _world_magic_icons=magic_icons,
                    owner_current=lambda *args: True,
                    realm=SimpleNamespace(service=lambda _: service, serves_map=lambda _: True,
                        registry=SimpleNamespace(resolve=lambda _: game), _world_frames={},
                        _frames_for=frames_for), run_sync_hooks=lambda *args: None)
                registry = world_registry.build_registry(
                    (*world_handlers.CORE_MODULES, world_feature_items, world_feature_magic))
                ctx._world_registry = registry
                for name in (*registry.hooks['after_relocate'], '_world_magic_replay_invisible'):
                    setattr(ctx, name, MethodType(registry.methods[name], ctx))
                ctx.collect_sync_hooks = lambda name, *args: world_registry.collect_sync_hooks(
                    name, ctx, *args)

                result = _world_relocate_locked(ctx, writer,
                    {'operation_lock': SimpleNamespace(locked=lambda: True)}, game,
                    wm.MapDestination(target_map, 200, 201, 4))
                if now == 100:
                    self.assertEqual([int.from_bytes(frame[2:4], 'little') for frame in result],
                                     [0x4e95, 0x4e38, 0x4e96, 0x4e96,
                                      0x4e5b, 0x4e91, 0x4e91, 0x4e91])
                    self.assertEqual(result[4:], (
                        world_combat.speed_frame(1, combat.speed_factor(1, now)),
                        green.frames[-1], brave.frames[-1],
                        world_feature_magic.buff_icon_frame(7, magic_icons[(1, 7)], 60)))
                else:
                    self.assertEqual([int.from_bytes(frame[2:4], 'little') for frame in result],
                                     [0x4e95, 0x4e38, 0x4e96, 0x4e96])
                self.assertEqual(before, (dict(pc.buffs), dict(effects.state(1).potions),
                    dict(effects.icons[1]), dict(magic.state(1).buffs), dict(magic_icons)))


if __name__ == '__main__':
    unittest.main()
