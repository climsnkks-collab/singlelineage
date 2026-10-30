"""Offline request/lifetime tests. No sockets, original game or profile writes."""
import asyncio
from dataclasses import replace
import random
from types import MethodType, SimpleNamespace as NS
import unittest
from unittest import mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, inventory_update
from tools.local_original_session import world_combat as wc, world_feature_combat as feature
from tools.local_original_session import world_registry, world_visibility
from tools.local_original_session.world_core_session import _world_attack
from tools.local_original_session.world_decoupling_tests import actual_module_declarations
from tools.local_original_session.world_ai_tests import GridTerrain, status_fields, varints
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.broker import INVENTORY_STARTER_FIELDS


def opcode(frame):
    return int.from_bytes(frame[2:4], 'little')


class WireTests(unittest.TestCase):
    def test_required_uint32_and_explicit_bool(self):
        for uid in (0, 1, 0xffffffff):
            self.assertEqual(feature.decode_continue(pb.encode_uint32(1, uid)), uid)
        for payload in (b'', b'\x08', b'\x0a\x00', b'\x08\x01\x08\x02',
                        b'\x10\x01', b'\x08\x80\x80\x80\x80\x10'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                feature.decode_continue(payload)
        self.assertEqual(feature.continue_ack(False)[4:-2], b'\x08\x00')
        self.assertEqual(feature.continue_ack(True)[4:-2], b'\x08\x01')

    def test_registration_and_optional_feature_boundaries(self):
        core, optional = actual_module_declarations()
        for omitted in (None, 'combat', 'magic', 'iteminfo', 'town', 'companion', 'pet', 'items'):
            enabled = tuple(module for module in optional
                            if module.__name__ != 'world_feature_' + str(omitted))
            registry = world_registry.build_registry(core + enabled)
            self.assertEqual(registry.frames[0x4e30], ('_world_attack',))
            for op in (feature.CONTINUE_REQUEST, feature.FAR_ATTACK):
                self.assertEqual(op in registry.frames, omitted != 'combat')
            self.assertEqual(0x4e2f in registry.frames, omitted != 'iteminfo')
            self.assertEqual(feature.CONTINUE_ACK in registry.outgoing_opcodes, omitted != 'combat')


class RequestTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 100.0
        data = load_m1()
        data = replace(data, spawns=tuple(row for row in data.spawns if row.group_id == 'm1_orc'))
        world = self.world = world_visibility.WorldView.create(
            data=data, terrain=GridTerrain(), clock=lambda: self.now, rng=random.Random(3))
        world.bind_pc(1, wc.PcProfile(1, 1, 0, 13, 13, weapon=wc.ATHAME), status_fields(500))
        world.update_pc(1, 0, 32590, 32880, reset=True)
        self.target = world.entities.get(world.spawner.groups[0].slots[0].uid)
        world.update_pc(1, 0, self.target.x - 1, self.target.y)
        world.drain(1)
        self.writer, self.game, self.lock = object(), NS(selection=object()), asyncio.Lock()
        self.row = {'writer': self.writer, 'operation_lock': self.lock}
        self.sent, self.costs, self.saves = [], [], []
        self.weapon = data.items[11]
        self.ctx = NS(_world=world, _world_pcs={id(self.writer): (self.writer, 1)},
                      fold_sync_hooks=lambda name, value, *args: value,
                      _world_attack_errors=[], _world_events={1: asyncio.Event()},
                      _item_equipment_effect=NS(combat_inputs=lambda uid: (self.weapon, 0)),
                      _inventory_kit_policy=inventory.KIT_POLICY,
                      inventory_frame=inventory.build_kit_frame([
                          {**INVENTORY_STARTER_FIELDS, 1: 91, 2: 29, 4: 3}]),
                      _world_bound=lambda writer: writer is self.writer,
                      _world_ready=lambda writer, game: object(),
                      _world_save_progress=self.saves.append)

        async def send(writer, row, frames, lock):
            self.sent.extend(frames)

        def consume(writer, item_uid, count):
            rows = [dict(row.raw_fields) for row in inventory.validate_kit_frame(self.ctx.inventory_frame)]
            next(row for row in rows if row[1] == item_uid)[4] -= count
            # Existing inventory owner keeps a zero-count anchor for the final row.
            self.ctx.inventory_frame = inventory.build_kit_frame(
                [row for row in rows if row[4] > 0 or len(rows) == 1])
            self.costs.append((writer, item_uid, count))
            remaining = next((row[4] for row in rows if row[1] == item_uid), 0)
            return inventory_update._encode(inventory_update._values({1: item_uid, 4: remaining}))

        self.ctx._world_send, self.ctx._world_consume_kit = send, consume
        self.ctx._world_attack = MethodType(_world_attack, self.ctx)
        feature._world_combat_initialize(self.ctx)
        world.prepare_pc_attack = lambda *args: feature._world_prepare_pc_attack(self.ctx, *args)

    async def request(self, uid, *, opcode=feature.CONTINUE_REQUEST, payload=None):
        frame = NS(opcode=opcode, payload=pb.encode_uint32(1, uid) if payload is None else payload)
        handler = feature._world_attack_continue if opcode == feature.CONTINUE_REQUEST else feature._world_far_attack
        async with self.lock:
            return await handler(self.ctx, self.writer, self.row, self.game, frame, self.lock)

    def retained(self):
        return self.ctx._world_continue_targets.get(1)

    async def test_maintain_is_metadata_cancel_and_malformed_are_request_local(self):
        hp = self.world.spawner.slot_for(self.target.uid)[1].hp
        deadline = self.world.combat.pcs[1].next_attack_at
        for _ in range(2):
            self.assertTrue(await self.request(self.target.uid))
            self.assertEqual(self.sent[-1], feature.continue_ack(True))
        self.assertEqual(self.retained()[2], self.target.ref)
        self.assertEqual(self.costs, [])
        self.assertEqual(self.world.spawner.slot_for(self.target.uid)[1].hp, hp)
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, deadline)
        old = self.retained()
        sent = len(self.sent)
        await self.request(0, payload=b'')
        self.assertIs(self.retained(), old)
        self.assertEqual(len(self.sent), sent)
        self.assertTrue(await self.request(0))
        self.assertIsNone(self.retained())
        self.assertEqual(self.sent[-1], feature.continue_ack(False))
        await self.request(self.target.uid)
        await self.request(0xffffffff)
        self.assertIsNone(self.retained())
        self.assertEqual(self.sent[-1], feature.continue_ack(False))

    async def test_same_map_life_visibility_and_writer_binding(self):
        for mutate in (lambda: setattr(self.target, 'map_id', 1),
                       lambda: setattr(self.target, 'alive', False),
                       lambda: self.world.visibility.known[1].discard(self.target.uid),
                       lambda: setattr(self.world.combat.pcs[1], 'dead', True),
                       lambda: self.ctx._world_pcs.clear()):
            await self.asyncSetUp()
            await self.request(self.target.uid)
            self.assertIsNotNone(self.retained())
            mutate()
            self.world.events.emit('tick', self.now)
            self.assertIsNone(self.retained())
            self.assertEqual(self.world.drain(1)[-1], feature.continue_ack(False))

    async def test_death_map_change_leave_and_generation_release(self):
        for event, args in (('npc_died', (self.target.uid, self.now)),
                            ('pc_death', (1,)), ('before_map_change', (1,)),
                            ('before_pc_leave', (1,))):
            await self.request(self.target.uid)
            self.world.events.emit(event, *args)
            self.assertIsNone(self.retained())
            self.world.drain(1)
        await self.request(self.target.uid)
        self.world.entities.kill(self.target.uid)
        self.world.events.emit('tick', self.now)
        self.assertIsNone(self.retained())
        self.assertEqual(self.world.drain(1)[-1], feature.continue_ack(False))

    async def test_far_and_general_share_cost_cadence_and_range_without_implicit_swings(self):
        await self.request(self.target.uid)
        await self.request(0)  # cancellation never disables an explicit normal swing
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.assertEqual(len(self.costs), 1)
        self.assertTrue(any(opcode(wire) == 0x4e31 for wire in self.sent))
        first_clock = self.world.combat.pcs[1].next_attack_at
        self.sent.clear()
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.assertEqual(len(self.costs), 1)
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, first_clock)
        self.now += 2
        # The existing 4E30 compatibility lane uses the very same ammunition owner.
        await self.ctx._world_attack(self.writer, self.row, self.game,
            NS(payload=pb.encode_uint32(1, self.target.uid)), self.lock)
        self.assertEqual(len(self.costs), 2)
        self.now += 2
        self.world.entities.move(1, 0, self.target.x - 30, self.target.y)
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.assertEqual(len(self.costs), 2)

    async def test_far_nonbow_malformed_dead_and_los_have_no_cost(self):
        self.weapon = self.world.data.items[12]
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.weapon = self.world.data.items[11]
        await self.request(0, opcode=feature.FAR_ATTACK, payload=b'')
        self.world.combat.pcs[1].dead = True
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.world.combat.pcs[1].dead = False
        self.world.terrain = GridTerrain(blocked=lambda *_: True)
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.assertEqual(self.costs, [])
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, 0)

    async def test_last_arrow_then_exhausted_and_stale_target_cannot_fire(self):
        self.ctx.inventory_frame = inventory.build_kit_frame([
            {**INVENTORY_STARTER_FIELDS, 1: 91, 2: 29, 4: 1}])
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.assertEqual(len(self.costs), 1)
        self.now += 2
        await self.request(self.target.uid, opcode=feature.FAR_ATTACK)
        self.assertEqual(len(self.costs), 1)
        await self.request(0xffffffff, opcode=feature.FAR_ATTACK)
        self.assertEqual(len(self.costs), 1)

    async def test_weapon_tile_caps_through_general_attack_lane(self):
        for template, reach in ((12, 2), (31, 2), (32, 2), (3, 1), (40, 1)):
            self.weapon = self.world.data.items[template]
            self.assertEqual(self.weapon.attack_range, reach)
            self.assertEqual(self.weapon.sources['attack_range'].kind, 'local_policy')
            self.assertEqual(wc.weapon_from_item(self.weapon).attack_range, reach)
            for distance, allowed in ((reach + 1, False), (reach, True)):
                with self.subTest(template=template, distance=distance):
                    self.now += 2
                    self.sent.clear()
                    self.world.entities.move(1, 0, self.target.x - distance, self.target.y)
                    before = self.world.combat.pcs[1].next_attack_at
                    await self.ctx._world_attack(self.writer, self.row, self.game,
                        NS(payload=pb.encode_uint32(1, self.target.uid)), self.lock)
                    self.assertEqual(any(opcode(wire) == 0x4e31 for wire in self.sent), allowed)
                    self.assertEqual(self.world.combat.pcs[1].next_attack_at > before, allowed)
        self.assertEqual(self.costs, [])

    async def test_melee_faces_current_target_on_hit_and_miss_for_self_and_observer(self):
        self.weapon = self.world.data.items[3]
        self.world.spawner.set_hp(self.target.uid, 100)
        self.world.bind_pc(2, wc.PcProfile(1, 1, 0, 13, 13), status_fields(500))
        self.world.update_pc(2, 0, self.target.x + 3, self.target.y, reset=True)
        # Target offsets in native heading order: N, NE, E, SE, S, SW, W, NW.
        offsets = ((0, -1), (1, -1), (1, 0), (1, 1),
                   (0, 1), (-1, 1), (-1, 0), (-1, -1))
        for landed in (True, False):
            for heading, (dx, dy) in enumerate(offsets):
                with self.subTest(landed=landed, heading=heading):
                    self.now += 2
                    self.world.update_pc(1, 0, self.target.x - dx, self.target.y - dy,
                                         heading=(heading + 4) % 8)
                    self.world.drain(1)
                    self.world.drain(2)
                    self.sent.clear()
                    # Keep real admission/cadence/packet routing; isolate hit RNG.
                    with mock.patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(landed, int(landed))):
                        await self.ctx._world_attack(self.writer, self.row, self.game,
                            NS(payload=pb.encode_uint32(1, self.target.uid)), self.lock)
                    own, = [varints(w) for w in self.sent if opcode(w) == 0x4e31]
                    peer, = [varints(w) for w in self.world.drain(2) if opcode(w) == 0x4e31]
                    for fields, self_action in ((own, 1), (peer, 0)):
                        self.assertEqual((fields[2], fields[3], fields[4], fields[5], fields[13]),
                                         (1, self.target.uid, int(landed), heading, self_action))
                    self.assertEqual(self.world.entities.get(1).heading, heading)

    async def test_refused_melee_keeps_heading_and_sends_no_swing(self):
        self.weapon = self.world.data.items[3]
        pc = self.world.entities.get(1)
        # Each refusal happens before an accepted swing can change direction.
        for refused in ('range', 'los', 'cadence', 'dead_target'):
            with self.subTest(refused=refused):
                self.world.entities.move(1, 0, self.target.x - (2 if refused == 'range' else 1),
                                         self.target.y, heading=6)
                self.world.terrain = GridTerrain(blocked=lambda *_: refused == 'los')
                self.world.combat.pcs[1].next_attack_at = self.now + (5 if refused == 'cadence' else 0)
                self.target.alive = refused != 'dead_target'
                self.sent.clear()
                await self.ctx._world_attack(self.writer, self.row, self.game,
                    NS(payload=pb.encode_uint32(1, self.target.uid)), self.lock)
                self.assertFalse(any(opcode(w) == 0x4e31 for w in self.sent))
                self.assertEqual(pc.heading, 6)

    async def test_spear_still_requires_los_and_bare_hands_remain_adjacent(self):
        self.weapon = self.world.data.items[31]
        self.world.entities.move(1, 0, self.target.x - 2, self.target.y)
        self.world.terrain = GridTerrain(blocked=lambda *_: True)
        self.world.pc_attack(1, self.target.uid)
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, 0)
        self.world.terrain = GridTerrain()
        self.weapon = None
        self.world.pc_attack(1, self.target.uid)
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, 0)
        self.world.entities.move(1, 0, self.target.x - 1, self.target.y)
        self.world.pc_attack(1, self.target.uid)
        self.assertGreater(self.world.combat.pcs[1].next_attack_at, 0)


if __name__ == '__main__':
    unittest.main()
