"""Development-only stance/frame tests. No game, sockets, ports or saved files.

Owner, inventory persistence and existing 097A delivery are in-memory fixture
seams. Actor frames use the production codec and _world_send -> _send -> writer.
These checks do not establish native consumption or screen behavior.
"""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from tools.local_original_session import broker as b, item_equipment_effect as gear
from tools.local_original_session import item_use, movement


def realm_fixture():
    root = Path(__file__).resolve().parents[2]
    actor = json.loads((root / 'tools/local_self_actor_profile/profile.json').read_text(encoding='utf-8'))
    from tools.local_self_info_profile.model import _values
    realm = b.LocalRealm.__new__(b.LocalRealm)
    realm._actor_fields = {row['field']: row['value'] for row in actor['rows']}
    realm._self_fields = _values({'uid': realm._actor_fields[2],
                                 'attributes': [13, 10, 10, 11, 13, 10]}, 1)
    realm.profile_uid = realm._actor_fields[2]
    realm.profile_name = realm._actor_fields[9]
    realm.map_frame = b'fixture-map'
    realm._world_frames = {}
    realm._world_hp = lambda uid: 7
    realm._world_mp = lambda uid: 3
    realm._world_look = lambda name: (61, {})
    realm._npc_motion = {}
    realm._npc_spawns = ()
    position = movement.Position(realm.profile_uid, realm.profile_name, 0, 32511, 32919)
    return realm, position


class ActorFrameTests(unittest.TestCase):
    def setUp(self):
        self.realm, self.position = realm_fixture()
        self.producer = b.PersistentBroker.__new__(b.PersistentBroker)
        from tools.local_original_session.game_data import load_stances
        self.producer._world_stances = load_stances()
        self.weapon = None
        self.producer._item_equipment_effect = NS(combat_inputs=lambda uid: (self.weapon, 0))
        self.realm._world_stance = self.producer._world_stance_for
        self.env = mock.patch.dict('os.environ', {}, clear=False)
        self.env.start()
        import os
        self.old = os.environ.pop('SL_EXPERIMENT_ACTOR_F4', None)

    def tearDown(self):
        self.env.stop()

    def actor(self, **kwargs):
        frame = self.realm._frames_for(self.position, **kwargs)[2]
        return b.session.world.decode_payload(0x4e96, frame[4:-2])

    def test_entry_weapon_types_and_unarmed_fallback(self):
        expected = {'sword': 30, 'axe': 35, 'blunt': 35, 'bow': 40,
                    'spear': 45, 'staff': 50, 'dagger': 55, 'twohand': 60}
        for kind, stance in expected.items():
            with self.subTest(kind=kind):
                self.weapon = NS(weapon_type=kind)
                self.assertEqual(self.actor()[4], stance)
        for weapon in (None, NS(weapon_type='unknown')):
            self.weapon = weapon
            self.assertEqual(self.actor()[4], 0)

    def test_explicit_experiment_wins_including_zero(self):
        self.weapon = NS(weapon_type='sword')
        for value in ('0', '55'):
            with mock.patch.dict('os.environ', {'SL_EXPERIMENT_ACTOR_F4': value}):
                self.assertEqual(self.actor()[4], int(value))

    def test_current_position_heading_sprite_and_remaining_fields(self):
        self.weapon = NS(weapon_type='spear')
        actor = self.actor(heading=6)
        expected = dict(self.realm._actor_fields)
        expected.update({1: self.position.packed, 3: 61, 4: 45, 5: 6})
        self.assertEqual(actor, expected)
        self.assertEqual(actor[2], self.position.uid)
        self.assertTrue(actor[16])
        # A stance refresh does not change the source baseline or invent HP fields.
        self.assertEqual(self.realm._actor_fields[4], 0)

    def test_explicit_status_still_uses_weapon_stance(self):
        self.weapon = NS(weapon_type='dagger')
        self.assertEqual(self.actor(status_fields=dict(self.realm._self_fields))[4], 55)


class StanceSendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.realm, self.position = realm_fixture()
        self.producer = b.PersistentBroker.__new__(b.PersistentBroker)
        self.producer.realm = self.realm
        self.producer._npc_respawn = None
        self.producer._hp_status = None
        self.producer._player_life = None
        self.producer._npc_player_hit = None
        self.producer._closing = False
        self.producer.failure = asyncio.Event()
        self.writer = NS(write=mock.Mock(), drain=mock.AsyncMock(),
                         transport=NS(get_write_buffer_size=lambda: 0))
        self.lock = asyncio.Lock()
        self.row = {'writer': self.writer, 'operation_lock': self.lock,
                    'policy_row': NS(sent=0, pending_opcode=None, drain_started_ns=None)}
        service = NS(snapshot=lambda: self.position, _actor_heading=7)
        self.realm._movement = {id(self.writer): (self.writer, service, 1)}
        self.producer._world = NS(combat=NS(pcs={self.position.uid: object()}))
        self.producer._world_pcs = {id(self.writer): (self.writer, self.position.uid)}
        self.producer._checkpoint = mock.AsyncMock(return_value=object())
        self.producer._sample = mock.AsyncMock(return_value=object())
        policy_row = self.row['policy_row']

        def begin_write(writer, sample, opcode, size, queued, now):
            self.assertTrue(self.lock.locked())
            self.assertIs(writer, self.writer)
            self.assertIsNone(policy_row.pending_opcode)
            policy_row.pending_opcode, policy_row.drain_started_ns = opcode, now

        def drained(writer, sample, queued, now):
            self.assertEqual(queued, 0)
            self.assertEqual(policy_row.pending_opcode, 0x4e96)
            policy_row.pending_opcode = policy_row.drain_started_ns = None
            policy_row.sent += 1

        self.producer.policy = NS(begin_write=begin_write, drained=drained, DRAIN_NS=2_000_000_000)
        from tools.local_original_session.game_data import load_stances
        self.producer._world_stances = load_stances()
        self.realm._world_stance = self.producer._world_stance_for
        self.state = NS(weapon_uid=0, slots=(), revision=1)
        self.effect = gear.ItemEquipmentEffect.__new__(gear.ItemEquipmentEffect)
        self.effect.broker = self.producer
        self.producer._item_equipment_effect = self.effect
        self.effect.combat_inputs = lambda uid: (None if not self.state.weapon_uid else NS(weapon_type='sword'), 0)

    def sent_actors(self):
        return [b.session.world.decode_payload(0x4e96, call.args[0][4:-2])
                for call in self.writer.write.call_args_list]

    async def test_equipping_and_unequipping_send_same_self_through_production_lane(self):
        item = NS(identifier=65537, template_bits=3)
        context = dict(writer=self.writer, row=self.row, character_uid=self.position.uid,
                       frame=b'fixture-inventory', item=item, selected_class=1)
        self.effect._defs = {3: NS(kind='weapon', equippable=True, slot_key=9, classes={1})}
        self.effect._context = lambda writer, **kwargs: context
        self.effect._same = lambda before, after: self.assertIs(before, after)
        self.effect.store = NS(restore=lambda uid, frame: self.state)
        events = []

        def cas(uid, frame, old, *, weapon_uid, slots):
            self.assertIs(old, self.state)
            self.state = NS(weapon_uid=weapon_uid, slots=slots, revision=old.revision + 1)
            events.append(('persist', weapon_uid))
            return self.state

        async def notify(context, state, receipt, changes):
            self.assertIs(state, self.state)
            events.append(('097a_drained', state.weapon_uid))

        self.effect.store.compare_and_swap_kit = cas
        self.effect._notify_kit = notify
        self.producer._world_refresh_pc = mock.AsyncMock(return_value=True)
        params = item_use.UseItemParams(b'', tuple(item_use.ParamField(n, 'int32', v)
                                                   for n, v in ((1, 1), (15, 0), (16, 0))))
        intent = NS(request=NS(params=params))
        original_write = self.writer.write
        original_write.side_effect = lambda wire: events.append(('actor', self.sent_actors()[-1][4]))
        with mock.patch.dict('os.environ', {'SL_EXPERIMENT_ACTOR_F4': ''}):
            for ordinal in (1, 2):
                life = {'state': self.state}
                async with self.lock:
                    result = await self.effect._consume_kit(self.writer, context, intent,
                                                           gear._receipt('ITEM_USE_EFFECT', ordinal), life)
                self.assertEqual(result['status'], 'COMMITTED')
                self.assertTrue(result['stance_notification_sent'])
        actors = self.sent_actors()
        self.assertEqual([actor[4] for actor in actors], [30, 0])
        self.assertEqual(events, [('persist', 65537), ('097a_drained', 65537), ('actor', 30),
                                  ('persist', 0), ('097a_drained', 0), ('actor', 0)])
        for actor in actors:
            self.assertEqual((actor[1], actor[2], actor[3], actor[5]),
                             (self.position.packed, self.position.uid, 61, 7))
        self.assertEqual(self.row['policy_row'].sent, 2)
        self.assertEqual(self.writer.drain.await_count, 2)
        self.assertEqual(self.producer._checkpoint.await_count, 4)
        self.assertEqual(self.producer._sample.await_count, 2)

    async def test_no_bound_world_and_unlocked_send(self):
        self.producer._world_pcs.clear()
        self.assertIsNone(await self.producer._world_refresh_stance_locked(self.writer, self.row))
        self.writer.write.assert_not_called()
        self.producer._world_pcs[id(self.writer)] = (self.writer, self.position.uid)
        with self.assertRaisesRegex(ValueError, 'WORLD_LOCKED_SEND_REQUIRED'):
            await self.producer._world_refresh_stance_locked(self.writer, self.row)
        self.writer.write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
