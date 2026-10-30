"""In-memory recipient/lifecycle checks. No sockets, game or saved user state."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock

from tools.local_game_session import session
from tools.local_original_session import world_combat as wc
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_interest_spawn import InterestSpawner
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_status_frames import effect_frame
from tools.local_original_session.world_visibility import WorldView, MONSTER_BASE_FIELDS
from tools.local_movement_session_route.route import authority


def opcode(wire):
    return int.from_bytes(wire[2:4], 'little')


def actor(uid, x=100, y=100):
    # Explicit test DTO. Product registration uses the complete realm self DTO.
    fields = dict(MONSTER_BASE_FIELDS)
    fields.update({1: authority.pack_grid(x, y), 2: uid, 3: 61, 4: 0, 5: 7,
                   9: 'fixture', 16: True})
    return fields


def make_view():
    data = replace(load_m1(), spawns=())
    runtime = WorldRuntime(clock=lambda: 100.)
    return WorldView(runtime, InterestSpawner(runtime.entities, data, passable=lambda *_: True),
                     data=data)


def bind(view, uid, x=100, y=100, map_id=0):
    fields = {1: uid, 2: 10, 4: 13, 5: 13, 6: 10, 7: 15,
              8: 12, 9: 10, 10: 30, 11: 100, 12: 2, 13: 10,
              14: -10, 15: 0, 16: 0, 17: 0, 18: 0, 20: 0}
    view.bind_pc(uid, wc.PcProfile(10, 1, 0, 13, 13), fields)
    return view.update_pc_and_drain(uid, map_id, x, y, reset=True, actor_fields=actor(uid, x, y))


class PcResponseTests(unittest.TestCase):
    def setUp(self):
        self.view = make_view()
        bind(self.view, 1)
        bind(self.view, 2, 101)
        bind(self.view, 3, 200)
        bind(self.view, 4, 101, map_id=1)
        for uid in self.view.pcs:
            self.view.drain(uid)

    def test_mutual_introduction_then_only_existing_visible_peer_gets_pre_step(self):
        view = self.view
        self.assertEqual(view.pc_known, {1: {2}, 2: {1}, 3: set(), 4: set()})
        self.assertEqual(view.update_pc_and_drain(1, 0, 100, 101), [])
        wire, = view.drain(2)
        self.assertEqual(opcode(wire), 0x4e2c)
        from tools.local_entry_server import protobuf as pb
        with pb.parse_message(wire[4:-2]) as parsed:
            fields = {field.number: field.value for field in parsed.fields}
        self.assertEqual(fields, {1: 1, 2: authority.pack_grid(100, 100), 3: 4})
        self.assertEqual(view.drain(3), [])
        self.assertEqual(view.drain(4), [])

    def test_stationary_rejected_move_produces_no_peer_or_self_signal(self):
        self.assertEqual(self.view.update_pc_and_drain(1, 0, 100, 100), [])
        self.assertTrue(all(not self.view.drain(uid) for uid in self.view.pcs))

    def test_one_tile_teleport_uses_final_actor_and_destination_heading(self):
        view = self.view
        view.update_pc_and_drain(1, 0, 100, 101, heading=7, step=False)
        wire, = view.drain(2)
        self.assertEqual(opcode(wire), 0x4e96)
        fields = session.world.decode_payload(0x4e96, wire[4:-2])
        self.assertEqual((fields[1], fields[5]), (authority.pack_grid(100, 101), 7))

    def test_cross_screen_boundary_introduces_final_actor_and_removes_both_sides(self):
        view = self.view
        frames = view.update_pc_and_drain(3, 0, 102, 100)
        self.assertEqual([opcode(w) for w in frames], [0x4e96, 0x4e96])
        for uid in (1, 2):
            wire, = view.drain(uid)
            self.assertEqual(opcode(wire), 0x4e96)
            fields = session.world.decode_payload(0x4e96, wire[4:-2])
            self.assertEqual((fields[2], fields[1]), (3, authority.pack_grid(102, 100)))
        frames = view.update_pc_and_drain(3, 0, 200, 100)
        self.assertEqual([opcode(w) for w in frames], [0x4e40, 0x4e40])
        self.assertEqual([opcode(w) for w in view.drain(1)], [0x4e40])
        self.assertEqual([opcode(w) for w in view.drain(2)], [0x4e40])

    def test_map_reset_replaces_visible_set_and_clears_own_stale_outbox(self):
        view = self.view
        view._queue(1, effect_frame(1, 189))
        frames = view.update_pc_and_drain(1, 1, 100, 100, reset=True,
                                           actor_fields=actor(1))
        self.assertEqual([opcode(w) for w in frames], [0x4e96])
        self.assertEqual(view.pc_known[1], {4})
        self.assertEqual([opcode(w) for w in view.drain(2)], [0x4e40])
        self.assertEqual([opcode(w) for w in view.drain(4)], [0x4e96])
        self.assertNotIn(0x4ed8, [opcode(w) for w in frames])

    def test_logout_removes_known_peers_and_discards_own_state_before_rebind(self):
        view = self.view
        view._queue(1, effect_frame(1, 189))
        view.leave_pc(1)
        self.assertNotIn(1, view.pc_known)
        self.assertNotIn(1, view.pc_actors)
        self.assertEqual(view.drain(1), [])
        self.assertEqual([opcode(w) for w in view.drain(2)], [0x4e40])
        self.assertNotIn(1, view.pc_known[2])
        frames = bind(view, 1)
        self.assertEqual([opcode(w) for w in frames], [0x4e96])
        self.assertEqual([opcode(w) for w in view.drain(2)], [0x4e96])

    def test_death_action_self_and_known_peer_only(self):
        view = self.view
        view.combat.pcs[1].dead = True
        view._pc_died(1, 100.)
        self.assertEqual([opcode(w) for w in view.drain(1)], [0x4e39])
        self.assertEqual([opcode(w) for w in view.drain(2)], [0x4e39])
        self.assertEqual(view.drain(3), [])
        self.assertEqual(view.drain(4), [])
        self.assertNotIn(1, view.regen)

    def test_potion_broadcast_filters_private_status_inventory_and_icons(self):
        view = self.view
        public = (effect_frame(1, 189), wc.speed_frame(1, 1.5))
        view.broadcast_pc_effects(1, (*public, b'\x06\x00\x38\x4e\x00\x00',
                                          b'\x06\x00\x91\x4e\x00\x00',
                                          b'\x06\x00\x65\x09\x00\x00'))
        self.assertEqual(view.drain(2), list(public))
        for uid in (1, 3, 4):
            self.assertEqual(view.drain(uid), [])

    def test_speed_expiry_notifies_self_and_visible_peer(self):
        view = self.view
        buff = view.data.items[17].buff
        frame = view.apply_buff(1, buff)
        self.assertIsNotNone(frame)
        view._buff_expired(1, buff.kind, 100. + buff.add_s)
        self.assertEqual([opcode(w) for w in view.drain(1)], [0x4e5b])
        self.assertEqual([opcode(w) for w in view.drain(2)], [0x4e5b])
        self.assertEqual(view.drain(3), [])

    def test_equipment_actor_reuses_full_dto_for_visible_peer(self):
        fields = actor(1)
        fields[4] = 30
        self.view.publish_pc_actor(1, fields)
        wire, = self.view.drain(2)
        actual = session.world.decode_payload(0x4e96, wire[4:-2])
        self.assertEqual(actual, fields)
        self.assertEqual(self.view.drain(1), [])
        self.assertEqual(self.view.drain(3), [])
        self.assertEqual(self.view.drain(4), [])

    def test_no_dto_does_not_invent_pc_actor(self):
        view = self.view
        view.update_pc(5, 0, 100, 100)
        self.assertNotIn(5, view.pc_known[1])
        self.assertEqual(view.drain(1), [])

    def test_reset_cannot_inherit_stale_actor_and_explicit_new_dto_republishes(self):
        view = self.view
        fields = actor(1)
        fields[3], fields[4] = 48, 30
        view.update_pc_and_drain(1, 0, 100, 100, reset=True, actor_fields=fields)
        wire, = view.drain(2)
        self.assertEqual(session.world.decode_payload(0x4e96, wire[4:-2])[3], 48)
        view.update_pc_and_drain(1, 0, 100, 100, reset=True)
        self.assertNotIn(1, view.pc_actors)
        self.assertEqual([opcode(w) for w in view.drain(2)], [0x4e40])


class PotionLaneTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tools.local_original_session.world_item_effects import WorldItemEffects
        self.view = make_view()
        bind(self.view, 1)
        bind(self.view, 2, 101)
        bind(self.view, 3, 200)
        self.view.drain(1)
        self.view.drain(2)
        self.writer = object()
        self.lock = asyncio.Lock()
        self.row = dict(writer=self.writer, operation_lock=self.lock)
        self.ctx = NS(_world=self.view, _world_events={}, _world_pcs={id(self.writer): (self.writer, 1)},
                      _world_bound=lambda _: True, _world_send=AsyncMock(),
                      _world_item_effects=WorldItemEffects(self.view.combat, None))

    async def test_heal_route_self_order_and_observer_effect_only(self):
        from tools.local_original_session.world_feature_items import _world_potion_locked
        async with self.lock:
            await _world_potion_locked(self.ctx, self.writer, self.row, b'inventory', 14)
        frames = self.ctx._world_send.await_args.args[2]
        self.assertEqual([opcode(w) for w in frames[1:]], [0x4ed8, 0x4e38])
        self.assertEqual(frames[0], b'inventory')
        self.assertEqual([opcode(w) for w in self.view.drain(2)], [0x4ed8])
        self.assertEqual(self.view.drain(3), [])

    async def test_buff_route_observer_effect_and_speed_private_icon(self):
        from tools.local_original_session.world_feature_items import _world_buff_locked
        buff = self.view.data.items[17].buff
        async with self.lock:
            await _world_buff_locked(self.ctx, self.writer, self.row, b'inventory', buff, 17)
        frames = self.ctx._world_send.await_args.args[2]
        self.assertEqual(frames[0], b'inventory')
        self.assertEqual([opcode(w) for w in self.view.drain(2)], [0x4ed8, 0x4e5b])
        self.assertEqual(self.view.drain(3), [])

    async def test_rejected_dead_buff_sends_no_observer_effect(self):
        from tools.local_original_session.world_feature_items import _world_buff_locked
        self.view.combat.pcs[1].dead = True
        async with self.lock:
            result = await _world_buff_locked(self.ctx, self.writer, self.row, b'inventory',
                                              self.view.data.items[17].buff, 17)
        self.assertFalse(result['buff_applied'])
        self.assertEqual(self.view.drain(2), [])


class StanceLaneTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_refresh_after_self_drain_then_peer_equip_unequip_and_noop(self):
        from tools.local_original_session.world_core_kit import _world_refresh_stance_locked
        view = make_view()
        bind(view, 1)
        bind(view, 2, 101)
        bind(view, 3, 200)
        view.drain(1)
        writer = object()
        position = NS(uid=1)
        fields = actor(1)
        service = NS(snapshot=lambda: position, _actor_heading=7, _self_actor_appearance=(61, 0))

        def frames_for(*args, **kwargs):
            body = session.world.encode_payload(0x4e96, fields)
            return (b'map', b'status', (len(body) + 6).to_bytes(2, 'little')
                    + b'\x96\x4e' + body + b'\0\0')

        async def send(*args):
            # Product method must finish its own existing send before peer publication.
            self.assertEqual(view.drain(2), [])

        ctx = NS(_world_bound=lambda _: True, _world=view,
                 realm=NS(service=lambda _: service, _frames_for=frames_for, _world_frames={}),
                 _world_send=AsyncMock(side_effect=send))
        row = dict(operation_lock=asyncio.Lock())
        for stance in (30, 0):
            fields[4] = stance
            async with row['operation_lock']:
                self.assertEqual(await _world_refresh_stance_locked(ctx, writer, row), stance)
            wire, = view.drain(2)
            self.assertEqual(session.world.decode_payload(0x4e96, wire[4:-2]), fields)
            self.assertEqual(view.drain(3), [])
        await _world_refresh_stance_locked(ctx, writer, row)
        self.assertEqual(ctx._world_send.await_count, 2)
        self.assertEqual(view.drain(2), [])


if __name__ == '__main__':
    unittest.main()
