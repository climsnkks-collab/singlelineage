"""Offline attack ingress checks; no sockets, game, runtime task or profile writes."""
import unittest
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest import mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import world_combat as wc
from tools.local_original_session import world_combat_requests_tests as requests
from tools.local_original_session import world_feature_combat as combat
from tools.local_original_session.world_companion import CompanionRecord
from tools.local_original_session.world_companion_runtime import install_companion_runtime
from tools.local_original_session.world_entities import EntityRef, Kind
from tools.local_original_session.world_ai_tests import varints


class CompanionClickAttackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await requests.RequestTests.asyncSetUp(self)
        install_companion_runtime(self.world)
        self.weapon = self.world.data.items[3]
        for entity in tuple(self.world.entities):
            if entity.kind is Kind.NPC and entity.uid != self.target.uid:
                self.world.entities.move(entity.uid, 0, self.target.x + 20, self.target.y)
        self.record = CompanionRecord(2, 1, 'click-fixture', hp=12, max_hp=12,
                                      movement_mode='HOLD', combat_mode='PASSIVE')
        self.world.companions.register(self.record, roster={
            1: dict(account_id='click-fixture', class_id=1),
            2: dict(account_id='click-fixture', class_id=3)})
        self.world.companion_profiles[2] = wc.PcProfile(1, 3, 0, 8, 7)
        self.world.companion_looks[2] = dict(name='Fixture', owner_name='Owner',
                                            sprite_id=734, stance=50)
        self.actor = self.world.summon_companion(2, 1)
        self.member = self.world.entities.resolve(self.actor.ref)
        self.world.entities.move(self.member.uid, 0, self.target.x, self.target.y)
        self.world.spawner.set_hp(self.target.uid, 1000)
        self.world.drain(1)

    async def asyncTearDown(self):
        self.world.close()

    async def melee(self, uid, payload=None):
        async with self.lock:
            return await self.ctx._world_attack(self.writer, self.row, self.game,
                NS(payload=pb.encode_uint32(1, uid) if payload is None else payload), self.lock)

    async def select(self, uid):
        return await requests.RequestTests.request(self, uid)

    def resolve(self):
        return self.world.resolve_pc_attack_target(1, self.member.uid)

    def other_monster(self, dx=1, dy=0):
        other = next(entity for entity in self.world.entities
                     if entity.kind is Kind.NPC and entity.uid != self.target.uid
                     and entity.uid != self.member.uid)
        self.world.entities.move(other.uid, 0, self.member.x + dx, self.member.y + dy)
        return other

    async def test_ai_target_has_priority_over_ambiguous_neighbors_and_distance(self):
        self.other_monster()
        self.world.entities.move(self.target.uid, 0, self.member.x + 10, self.member.y)
        self.actor.target = self.target.ref
        self.assertEqual(self.resolve(), self.target.uid)
        self.world.visibility.known[1].add(self.target.uid)
        await self.select(self.member.uid)
        self.assertEqual(self.ctx._world_continue_targets[1][2], self.target.ref)
        self.assertEqual(self.sent[-1], combat.continue_ack(True))
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, 0)

    async def test_unique_monster_on_each_of_nine_tiles(self):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                with self.subTest(dx=dx, dy=dy):
                    self.world.entities.move(self.target.uid, 0,
                        self.member.x + dx, self.member.y + dy)
                    self.assertEqual(self.resolve(), self.target.uid)

    async def test_invalid_ai_targets_fall_back_to_unique_neighbor(self):
        other = self.other_monster(20)
        group, slot = self.world.spawner.slot_for(other.uid)
        self.world.spawner._slots[other.uid] = (replace(group, slots=[slot]), slot)
        for invalid in ('dead', 'other_map', 'stale_ref', 'zero_hp', 'inactive', 'pc', 'companion'):
            with self.subTest(invalid=invalid):
                group, slot = self.world.spawner.slot_for(other.uid)
                self.actor.target = other.ref
                other.alive, other.map_id, group.active, slot.hp = True, 0, True, 10
                if invalid == 'dead':
                    other.alive = False
                elif invalid == 'other_map':
                    other.map_id = 1
                elif invalid == 'stale_ref':
                    self.actor.target = EntityRef(other.uid, other.generation + 1)
                elif invalid == 'zero_hp':
                    slot.hp = 0
                elif invalid == 'inactive':
                    group.active = False
                elif invalid == 'pc':
                    self.actor.target = self.world.entities.get(1).ref
                else:
                    self.actor.target = self.actor.ref
                self.assertEqual(self.resolve(), self.target.uid)
                group.active = True

    async def test_no_candidate_or_multiple_candidates_ignore_and_release_selection(self):
        await self.select(self.target.uid)
        self.other_monster()
        before = (self.record.hp, self.world.combat.pcs[1].next_attack_at)
        self.ctx._attack_session = object()  # A refusal must not fall into this legacy lane.
        self.assertTrue(await self.melee(self.member.uid))
        self.assertEqual(self.sent[-1], combat.continue_ack(True))
        await self.select(self.member.uid)
        self.assertEqual(self.sent[-1], combat.continue_ack(False))
        self.assertNotIn(1, self.ctx._world_continue_targets)
        self.assertEqual((self.record.hp, self.world.combat.pcs[1].next_attack_at), before)
        self.world.entities.move(self.target.uid, 0, self.member.x + 10, self.member.y)
        self.other_monster(20)
        self.assertIsNone(self.resolve())
        self.assertTrue(await self.melee_ignored())
        await self.select(self.member.uid)
        self.assertEqual(self.sent[-1], combat.continue_ack(False))

    async def test_unique_fallback_uses_decoded_melee_and_selection_requests(self):
        self.assertIsNone(self.actor.target)
        await self.select(self.member.uid)
        self.assertEqual(self.ctx._world_continue_targets[1][2], self.target.ref)
        self.assertEqual(self.sent[-1], combat.continue_ack(True))
        self.sent.clear()
        with mock.patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(True, 1)):
            self.assertTrue(await self.melee(self.member.uid))
        own, = [varints(w) for w in self.sent if requests.opcode(w) == 0x4e31]
        self.assertEqual((own[2], own[3], own[4]), (1, self.target.uid, 1))
        self.assertEqual(self.record.hp, 12)

    async def melee_ignored(self):
        self.sent.clear()
        handled = await self.melee(self.member.uid)
        self.assertFalse(any(requests.opcode(w) == 0x4e31 for w in self.sent))
        return handled

    async def test_neighbor_filter_excludes_dead_other_map_and_zero_hp(self):
        other = self.other_monster()
        for invalid in ('dead', 'other_map', 'zero_hp'):
            with self.subTest(invalid=invalid):
                _, slot = self.world.spawner.slot_for(other.uid)
                other.alive, other.map_id, slot.hp = True, 0, 10
                if invalid == 'dead':
                    other.alive = False
                elif invalid == 'other_map':
                    other.map_id = 1
                else:
                    slot.hp = 0
                self.assertEqual(self.resolve(), self.target.uid)

    async def test_own_dead_different_map_or_stale_owner_companion_is_consumed(self):
        for invalid in ('dead', 'other_map', 'stale_owner', 'dead_record'):
            with self.subTest(invalid=invalid):
                self.member.alive, self.member.map_id = True, 0
                self.actor.owner_ref = self.world.entities.get(1).ref
                self.record.alive = True
                if invalid == 'dead':
                    self.member.alive = False
                elif invalid == 'other_map':
                    self.member.map_id = 1
                elif invalid == 'stale_owner':
                    self.actor.owner_ref = EntityRef(1, 999)
                else:
                    self.record.alive = False
                self.assertIsNone(self.resolve())
                self.assertTrue(await self.melee_ignored())

    async def test_wire_redirect_precedes_optional_attack_wrappers(self):
        self.actor.target = self.target.ref
        seen = []
        def wrapper(base):
            def call(uid, target_uid):
                seen.append((uid, target_uid))
                return base(uid, target_uid)
            return call
        self.world.runtime_extensions.wrap('click-fixture', self.world, 'pc_attack', wrapper)
        await self.melee(self.member.uid)
        self.assertEqual(seen, [(1, self.target.uid)])

    async def test_unrelated_monster_pc_other_owner_and_pet_targets_are_unchanged(self):
        for uid in (1, self.target.uid, 0, 0xffffffff):
            self.assertEqual(self.world.resolve_pc_attack_target(1, uid), uid)
        self.actor.owner_ref = EntityRef(7, 1)
        self.assertEqual(self.resolve(), self.member.uid)
        self.actor.owner_ref = self.world.entities.get(1).ref
        self.record.equipment['_pet'] = {}
        self.assertEqual(self.resolve(), self.member.uid)

    async def test_redirected_wire_melee_keeps_hit_miss_heading_and_cadence(self):
        self.actor.target = self.target.ref
        for landed in (True, False):
            with self.subTest(landed=landed):
                self.now += 2
                self.sent.clear()
                pc = self.world.entities.get(1)
                self.world.entities.move(1, 0, self.target.x - 1, self.target.y, heading=6)
                before = self.world.spawner.slot_for(self.target.uid)[1].hp
                # Coordinates describe the clicked member, never the redirected target.
                self.world.entities.move(self.member.uid, 0, self.target.x + 1, self.target.y)
                payload = (pb.encode_uint32(1, self.member.uid)
                           + pb.encode_uint32(2, self.member.x) + pb.encode_uint32(3, self.member.y))
                with mock.patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(landed, int(landed))):
                    self.assertTrue(await self.melee(self.member.uid, payload))
                own, = [varints(w) for w in self.sent if requests.opcode(w) == 0x4e31]
                self.assertEqual((own[2], own[3], own[4], own[5]),
                                 (1, self.target.uid, int(landed), 2))
                self.assertEqual(pc.heading, 2)
                self.assertEqual(self.world.spawner.slot_for(self.target.uid)[1].hp, before - int(landed))
                self.assertEqual(self.record.hp, 12)
                self.sent.clear()
                await self.melee(self.member.uid)
                self.assertFalse(any(requests.opcode(w) == 0x4e31 for w in self.sent))

    async def test_redirect_keeps_existing_range_refusal_then_accepts_after_move(self):
        self.actor.target = self.target.ref
        self.world.entities.move(1, 0, self.target.x - 3, self.target.y, heading=6)
        await self.melee(self.member.uid)
        self.assertEqual(self.world.combat.pcs[1].next_attack_at, 0)
        self.assertEqual(self.world.entities.get(1).heading, 6)
        self.assertFalse(any(requests.opcode(w) == 0x4e31 for w in self.sent))
        self.world.update_pc(1, 0, self.target.x - 1, self.target.y)
        await self.melee(self.member.uid)
        self.assertTrue(any(requests.opcode(w) == 0x4e31 for w in self.sent))


if __name__ == '__main__':
    unittest.main()
