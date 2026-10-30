"""Offline LOCAL voyage integration: core CAS/relocation, real terrain, no ports/UI.

Character/ticket rows and controlled wall time are explicit development inputs.
These checks are not a formal gameplay PASS or natural ticket-purchase claim.
"""
import asyncio
from dataclasses import dataclass, replace
import json
from pathlib import Path
from types import MethodType, SimpleNamespace as NS
import unittest
from unittest.mock import patch
import uuid

from tools.local_game_session import session
from tools.local_original_session import inventory, inventory_store, movement
from tools.local_original_session import game_data, world_registry
from tools.local_original_session import world_feature_ship as ship
from tools.local_original_session.world_core_maps import _world_relocate_locked, _world_enter_ship
from tools.local_original_session.world_core_kit import _world_consume_kit
from tools.local_original_session.world_combat import PcProfile, ATHAME
from tools.local_original_session.world_maps import MapDestination
from tools.local_original_session.world_terrain import WorldTerrain
from tools.local_original_session.world_visibility import WorldView, MONSTER_BASE_FIELDS
from tools.local_original_session.inventory_tests import explicit_fields
from tools.local_native_login_self_actor_hook import hook as actor_hook


class ShipPolicyTests(unittest.TestCase):
    def test_original_values_and_local_label(self):
        route = ship.load_route()
        self.assertEqual((route.key, route.ticket_id, route.harbor_map, route.interior_map,
                          route.arrival_map), (4, 12017, 4, 83, 70))
        self.assertEqual(route.dock_box, (33417, 33496, 33430, 33505))
        self.assertEqual(route.interior_point, (32735, 32797))
        self.assertEqual(route.arrival_random, (32937, 33042, 7))
        raw = json.loads((Path(ship.__file__).with_name('data') / 'm6/ship_routes.json').read_text('utf-8'))
        self.assertEqual(raw['policy_label'], 'LOCAL 운항 정책(사용자 위임, Claude 결정)')
        self.assertEqual(raw['route']['schedule'], dict(days='1111111', interval_minutes=5,
                                                      entries=288, f3=2, f4=2))

    def test_schema_and_strict_next_schedule(self):
        self.assertEqual(ship.parse_portal(b'\x08\x04'), 4)
        self.assertEqual(ship.parse_portal(b'\x08' + b'\xff' * 9 + b'\x01'), -1)
        for body in (b'', b'\x08\x04\x08\x04', b'\x10\x04', b'\x0a\x01x',
                     b'\x08\x80\x80\x80\x80\x08'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                ship.parse_portal(body)
        self.assertEqual(ship.next_departure(299.999), 300)
        self.assertEqual(ship.next_departure(300), 600)
        self.assertEqual(ship.next_departure(86399), 86400)
        self.assertEqual(ship.next_departure(86400), 86700)

    def test_optional_feature_and_return_scroll(self):
        self.assertIn('_ship_enter', world_registry.build_registry((ship,)).methods)
        self.assertNotIn('_ship_enter', world_registry.build_registry(()).methods)
        ctx = NS(_world_map_exp=0)
        ship._ship_initialize(ctx)
        self.assertIsNone(ctx._ship_route)
        @dataclass(frozen=True)
        class Effect:
            kind: str
            destination: object
            requirements: object = None
        ctx._ship_route = ship.load_route()
        original = Effect('return_town', MapDestination(0, 1, 2, 4))
        for map_id in (70, 83):
            result = ship._ship_return_destination(ctx, original, NS(map_id=map_id))
            self.assertEqual(result.destination, MapDestination(4, 33426, 33502, 4))
        self.assertIs(ship._ship_return_destination(ctx, original, NS(map_id=4)), original)


class ShipVoyageTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = WorldTerrain.load(map_ids=(4, 70, 83))

    async def asyncSetUp(self):
        self.output = Path(__file__).resolve().parents[2] / '_work/ship-voyage' / uuid.uuid4().hex
        self.output.mkdir(parents=True)
        self.profile = self.output / 'characters.json'
        roster = inventory_store.realm.CharacterStore(self.profile)
        roster.create(inventory_store.realm.Creation('ShipKnight', 0, 0, (13,) * 6))
        self.store = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                   kit_policy=inventory.KIT_POLICY)
        self.fields = explicit_fields()
        self.fields.update({1: 71, 2: 12017, 4: 2, 18: b'Ticket'})
        self.initial = inventory.build_kit_frame((self.fields,))
        self.store.grant(1, self.initial)
        self.writer, self.game = object(), object()
        self.lock = asyncio.Lock()
        self.row = dict(writer=self.writer, operation_lock=self.lock)
        self.origin = movement.Position(1, 'ShipKnight', 4, 33426, 33502)
        self.positions = movement.PositionStore(self.profile)
        self.service = movement.MovementService(self.origin, connection=self.writer,
            owner_guard=lambda *_: True, edge_passability=lambda *_: True, store=self.positions)
        self.view = WorldView.create(data=replace(game_data.load_m1(), spawns=()), terrain=self.terrain)
        self.view.update_pc(1, 4, self.origin.word0, self.origin.word1)
        status = dict(actor_hook.profiles()[0].fields)
        status.update({1: 1, 2: 1, 10: 100, 11: 100, 12: 20, 13: 20, 18: 500})
        self.view.bind_pc(1, PcProfile(1, 0, 0, 18, 13, con=16, weapon=ATHAME), status)
        self.sent = []
        async def send(writer, row, frames, operation_lock):
            self.assertTrue(operation_lock.locked())
            self.assertFalse(self.view.runtime.lock.locked())
            self.sent.extend(frames)
        self.ctx = NS(_world=self.view, world=self.view, _world_map_exp=2,
            _world_map_transitions=0, _world_handler_errors=[],
            _world_pcs={id(self.writer): (self.writer, 1)},
            _world_handler_bindings=NS(wire=None, town=None, interaction_distance=15),
            inventory_frame=self.initial, _inventory_current_frame=self.initial,
            inventory_store=self.store, _inventory_kit_policy=inventory.KIT_POLICY,
            owner_current=lambda *_: True, _world_bound=lambda w: w is self.writer,
            _world_ready=lambda *_: self.service, _world_send=send,
            realm=NS(service=lambda _: self.service, serves_map=lambda m: m in (4,70,83),
                registry=NS(resolve=lambda _: self.game), _world_frames={}, _frames_for=self.frames_for))
        self.ctx.broker = self.ctx
        self.ctx._world_registry = world_registry.build_registry((ship,))
        for fn in ship.METHODS:
            setattr(self.ctx, fn.__name__, MethodType(fn, self.ctx))
        self.ctx.run_sync_hooks = lambda name, *args: world_registry.run_sync_hooks(name, self.ctx, *args)
        self.ctx.chain_sync_hooks = lambda name, *args: world_registry.chain_sync_hooks(name, self.ctx, *args)
        self.ctx.collect_sync_hooks = lambda name, *args: world_registry.collect_sync_hooks(name, self.ctx, *args)
        self.ctx._world_relocate_locked = MethodType(_world_relocate_locked, self.ctx)
        self.ctx._world_consume_kit = MethodType(_world_consume_kit, self.ctx)
        self.ctx.chain_hooks = lambda name, *args: world_registry.chain_hooks(name, self.ctx, *args)
        self.ctx._ship_initialize()
        self.now = 120.0
        self.view.runtime.clock = lambda: self.now
        self.time_patch = patch.object(ship.time, 'time', lambda: self.now)
        self.time_patch.start()

    async def asyncTearDown(self):
        await self.ctx._ship_stopped()
        self.time_patch.stop()
        self.view.close()

    def frames_for(self, position, *, heading, status_fields):
        fields = dict(MONSTER_BASE_FIELDS)
        fields.update({1: position.packed, 2: position.uid, 3: 61, 4: 0,
                       5: heading, 9: position.name, 16: True})
        def wire(opcode, values):
            body = session.world.encode_payload(opcode, values)
            return (len(body)+6).to_bytes(2,'little') + opcode.to_bytes(2,'little') + body + b'\0\0'
        return (wire(0x4e95, {1:position.map_id,2:0,3:False,4:False}),
                wire(0x4e38, status_fields), wire(0x4e96, fields))

    def count(self):
        return dict(inventory.validate_kit_frame(self.ctx.inventory_frame)[0].raw_fields)[4]

    async def enter(self, portal=4):
        async with self.lock:
            return await _world_enter_ship(self.ctx, self.writer, self.row, self.game,
                NS(payload=b'\x08'+bytes([portal])), self.lock)

    async def test_complete_time_cycle_uses_core_position_inventory_and_wire(self):
        waits = []
        async def clock(deadline, monotonic):
            waits.append(deadline)
            if len(waits) == 1:
                self.assertEqual((self.service.snapshot().map_id, self.count()), (4,2))
            else:
                self.assertEqual((self.service.snapshot().map_id, self.count()), (83,2))
                self.assertEqual(self.positions.restore(self.origin).map_id, 83)
            self.now = deadline
            await asyncio.sleep(0)
        with patch.object(ship, '_wait_until', clock):
            self.assertTrue(await self.enter())
            voyage = self.ctx._ship_voyages[1]
            self.assertTrue(await self.enter())
            self.assertIs(self.ctx._ship_voyages[1], voyage)
            await voyage.task
        self.assertEqual(waits, [300,600])
        position = self.service.snapshot()
        self.assertEqual((position.map_id,self.count(),self.ctx._ship_completed), (70,1,1))
        self.assertIs(self.terrain.can_stand(70,position.word0,position.word1),True)
        self.assertTrue(abs(position.word0-32937)<=7 and abs(position.word1-33042)<=7)
        self.assertEqual(movement.PositionStore(self.profile).restore(self.origin),position)
        self.assertEqual(self.store.restore(1),self.ctx.inventory_frame)
        maps = [session.world.decode_payload(0x4e95,w[4:-2])[1]
                for w in self.sent if int.from_bytes(w[2:4],'little')==0x4e95]
        self.assertEqual(maps,[83,70])
        self.assertNotIn(0x4f0e,[int.from_bytes(w[2:4],'little') for w in self.sent])
        self.assertEqual(len(self.ctx._ship_voyages),0)

    async def prepare_interior(self):
        await self.enter()
        voyage = self.ctx._ship_voyages[1]
        task = ship._cancel(voyage)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        async with self.lock:
            await self.ctx._ship_step(voyage,self.writer,self.row,self.game)
        return voyage

    async def test_disconnect_reconnect_keeps_deadline_and_single_debit(self):
        voyage = await self.prepare_interior()
        await self.ctx._ship_before_leave(self.writer,1)
        self.assertIsNone(voyage.task)
        self.now = 900
        async def clock(deadline, monotonic):
            self.assertEqual(deadline,600)
            await asyncio.sleep(0)
        with patch.object(ship,'_wait_until',clock):
            await self.ctx._ship_after_enter(self.writer,self.row,self.game,self.lock)
            await voyage.task
        self.assertEqual((self.service.snapshot().map_id,self.count()),(70,1))
        await self.ctx._ship_after_enter(self.writer,self.row,self.game,self.lock)
        self.assertFalse(self.ctx._ship_voyages)

    async def test_missing_resources_or_ticket_refuses_without_mutation(self):
        with patch.object(self.terrain,'can_stand',return_value=None):
            await self.enter()
        self.assertEqual(self.ctx._world_handler_errors[-1],'SHIP_INTERIOR_RESOURCE_UNAVAILABLE')
        self.assertEqual((self.service.snapshot().map_id,self.count()),(4,2))
        self.assertFalse(self.ctx._ship_voyages)
        self.ctx.inventory_frame=inventory.build_kit_frame((self.fields | {4:0},))
        await self.enter()
        self.assertEqual(self.ctx._world_handler_errors[-1],'SHIP_OWNED_TICKET_REQUIRED')

    async def test_departure_rechecks_dock_and_never_debits_on_relocation_failure(self):
        await self.enter()
        voyage=self.ctx._ship_voyages[1]
        await self.ctx._ship_before_leave(self.writer,1)
        self.assertFalse(self.ctx._ship_voyages)
        self.assertIsNone(voyage.task)
        voyage=ship.Voyage(1,300,600)
        self.ctx._ship_voyages[1]=voyage
        self.ctx._world_relocate_locked=lambda *a,**k: (_ for _ in ()).throw(OSError('position failure'))
        async with self.lock:
            with self.assertRaisesRegex(OSError,'position failure'):
                await self.ctx._ship_step(voyage,self.writer,self.row,self.game)
        self.assertEqual((self.count(),self.service.snapshot().map_id),(2,4))

    async def test_ambiguous_fare_failure_never_retries_or_claims_completion(self):
        voyage=await self.prepare_interior()
        original=self.ctx._world_consume_kit
        def ambiguous(*args):
            original(*args)
            raise OSError('fare replaced then failed')
        self.ctx._world_consume_kit=ambiguous
        async with self.lock:
            with self.assertRaisesRegex(OSError,'fare replaced then failed'):
                await self.ctx._ship_step(voyage,self.writer,self.row,self.game)
        self.assertEqual((voyage.phase,self.service.snapshot().map_id,self.count()),('FARE_ATTEMPTED',70,1))
        self.assertEqual(self.ctx._ship_completed,0)
        await self.ctx._ship_before_leave(self.writer,1)
        await self.ctx._ship_after_enter(self.writer,self.row,self.game,self.lock)
        self.assertIsNone(voyage.task)
        self.assertEqual(self.count(),1)

    async def test_external_return_cancels_and_feature_disabled_core_falls_through(self):
        voyage=await self.prepare_interior()
        ship._ship_before_relocate(self.ctx,1,{})
        self.assertNotIn(1,self.ctx._ship_voyages)
        self.assertIsNone(voyage.task)
        core=NS(chain_hooks=lambda *args: asyncio.sleep(0,result=False),_world_map_exp=0)
        self.assertFalse(await _world_enter_ship(core,self.writer,self.row,None,None,self.lock))
        self.assertEqual(len(ship._arrival_points(self.ctx,ship.load_route())),219)


if __name__=='__main__':
    unittest.main()
