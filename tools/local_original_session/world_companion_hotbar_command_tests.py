"""Offline real companion-consumer checks; no sockets, client or user saves."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from tools.local_entry_server import protobuf as pb
from tools.local_original_session import world_feature_companion_hotbar_probe as command
from tools.local_original_session import world_companion_magic_tests as fixtures
from tools.local_original_session.world_feature_companion import CompanionCommands
from tools.local_original_session.world_magic import MagicService

class CommandTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.MagicTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.view,self.rt,self.record,self.magic=self.fixture.view,self.fixture.actor,self.fixture.record,self.fixture.magic
        self.record.summoned=True
        self.record.learned_spells=(0,2,3,7,43)
        self.record.level=60
        self.magic.policy_for=lambda r:None
        self.writer=object();self.learned={1:set(),2:set(self.record.learned_spells)}
        self.characters={2:{'name':'SoloMage'}}
        self.command_enabled=True
        self.commands=CompanionCommands(self.view,lambda:self.characters,lambda uid:self.learned.get(uid,set()))
        self.magic_service=MagicService(self.magic.engine,None,None)
        self.ctx=NS(world=self.view,_world_pcs={id(self.writer):(self.writer,1)},
            _world_bound=lambda w:w is self.writer,_world_ready=lambda *a:True,
            collect_sync_hooks=self.collect,chain_sync_hooks=lambda *args:False,sent=[])
        async def send(w,row,frames,lock):self.ctx.sent.extend(frames)
        self.ctx._world_send=send
        command._hotbar_probe_initialize(self.ctx)
        self.enter()
    def collect(self,name,*args):
        if name=='character_learned_spells':return (self.learned.get(args[0],set()),)
        if name=='companion_commands':return (self.commands,) if self.command_enabled else ()
        if name=='magic_service':return (self.magic_service,)
        return ()
    def enter(self):
        asyncio.run(command._hotbar_probe_enter(self.ctx,self.writer,{},None,None))
    def cast(self,key=0,target=1,payload=None):
        body=payload if payload is not None else pb.encode_uint32(1,key)+(b'' if target is None else pb.encode_bytes(2,pb.encode_uint32(1,target)))
        return asyncio.run(command._hotbar_probe_frame(self.ctx,self.writer,{},None,NS(opcode=command.CAST,payload=body),None))
    def keys(self):return self.ctx._hotbar_probe_sessions[id(self.writer)]['keys']
    def rows(self,wire):
        out=[]
        with pb.parse_message(wire[4:-2]) as msg:
            for f in msg.occurrences(1):
                with pb.parse_message(bytes(f.value)) as child:
                    out.append({n:[v.value for v in child.occurrences(n)] for n in (1,2,6)})
        return out
    def test_default_on_f6_one_supported_only_and_no_learning_grant(self):
        self.assertTrue(self.ctx._hotbar_probe_enabled)
        self.assertEqual(self.keys(),{0,2,3,7})
        self.assertEqual(self.learned[1],set())
        self.assertTrue(all(r[6]==[1] and r[2]==[1] for r in self.rows(self.ctx.sent[0])))
        self.assertNotIn(43,self.keys())
    def test_heal_uses_companion_mp_and_preserves_knight_resources_and_cooldown(self):
        self.fixture.owner_state.hp=1
        before=self.fixture.owner_state.mp
        self.assertTrue(self.cast())
        self.assertGreater(self.fixture.owner_state.hp,1)
        self.assertEqual((self.record.mp,self.fixture.owner_state.mp),(36,before))
        self.assertEqual(self.magic.engine.state(1).next_cast_at,0)
        self.assertEqual(self.magic.events[-1]['target'],1)
    def test_manual_attack_without_ats_passive_or_selected_auto_target(self):
        enemy=self.fixture.enemy()
        self.record.combat_mode='PASSIVE';self.rt.target=None
        hp=self.view.spawner.slot_for(enemy.uid)[1].hp
        self.assertTrue(self.cast(3,enemy.uid))
        self.assertLess(self.view.spawner.slot_for(enemy.uid)[1].hp,hp)
        self.assertEqual(self.record.mp,37)
        self.assertIsNone(self.rt.target)
    def test_explicit_companion_self_target(self):
        self.record.hp=1
        self.assertTrue(self.cast(0,self.rt.ref.uid))
        self.assertGreater(self.record.hp,1)
        self.assertEqual(self.fixture.owner_state.hp,100)
    def test_new_learning_and_dismiss_delete(self):
        self.learned[2].remove(7);self.enter()
        self.assertIn({1:[7],2:[0],6:[]},self.rows(self.ctx.sent[-1]))
        self.learned[2].add(7);self.enter()
        self.assertIn({1:[7],2:[1],6:[1]},self.rows(self.ctx.sent[-1]))
        self.view.companions.dismiss(2);self.enter()
        self.assertEqual(self.keys(),set())
        self.assertTrue(all(r[2]==[0] for r in self.rows(self.ctx.sent[-1])))
    def test_dead_member_removed_and_stale_command_gets_notice(self):
        self.view.companions.die(2);self.enter()
        self.assertFalse(self.keys())
        self.assertTrue(self.cast())
        self.assertEqual(self.ctx._hotbar_probe_events[-1]['event'],'command-refused')
    def test_own_key_passes_to_player_and_restores_mp_field(self):
        self.learned[1].add(0);self.enter()
        self.assertFalse(self.cast())
        self.assertNotIn(0,self.keys())
        self.assertIn({1:[0],2:[1],6:[4]},self.rows(self.ctx.sent[-1]))
    def test_missing_companion_or_feature_has_no_send_or_claim(self):
        self.view.companions.dismiss(2)
        command._hotbar_probe_initialize(self.ctx);self.ctx.sent.clear();self.enter()
        self.assertEqual(self.ctx.sent,[]);self.assertFalse(self.cast())
        self.command_enabled=False;self.enter();self.assertFalse(self.cast())
    def test_rejection_mp_range_silence_paralysis_cooldown(self):
        for mode,text in [('mp','MP가 부족'),('range','사거리'),('silence','침묵'),('paralyze','마비'),('reuse','재사용')]:
            with self.subTest(mode=mode):
                self.fixture.owner_state.hp=1;self.record.mp=40;self.rt.next_cast_at=0
                self.view.entities.move(self.fixture.owner.uid,0,100,100)
                self.view.events._callbacks['actor_action_status']=[]
                if mode=='mp':self.record.mp=0
                if mode=='range':self.view.entities.move(self.fixture.owner.uid,0,150,150)
                if mode in ('silence','paralyze'):
                    self.view.events.add('test','actor_action_status',lambda value,*a:dict(value,**({'silenced':True} if mode=='silence' else {'blocked':True})))
                if mode=='reuse':self.rt.next_cast_at=100
                before=self.record.mp
                self.assertTrue(self.cast());self.assertEqual(self.record.mp,before)
                self.assertIn(text,self.ctx._hotbar_probe_events[-1]['message'])
                self.assertEqual(int.from_bytes(self.ctx.sent[-1][2:4],'little'),0x4EEA)
    def test_auto_eligible_remains_ats_gated(self):
        self.assertFalse(self.magic.eligible(self.rt,'heal'))
        self.assertTrue(self.magic.eligible(self.rt,'heal',manual=True))
    def test_no_companion_never_publishes_empty_initial_ui_request(self):
        from unittest.mock import patch
        self.view.companions.dismiss(2)
        command._hotbar_probe_initialize(self.ctx)
        with patch.object(command,'_publish') as publish:
            self.enter()
            command._hotbar_probe_leave(self.ctx,self.writer)
        publish.assert_not_called()
    def test_line_of_sight_refusal_preserves_both_mp(self):
        from unittest.mock import patch
        self.fixture.owner_state.hp=1
        before=(self.record.mp,self.fixture.owner_state.mp)
        with patch('tools.local_original_session.npc_ai.local_line_clear',return_value=False):
            self.assertTrue(self.cast())
        self.assertEqual((self.record.mp,self.fixture.owner_state.mp),before)
        self.assertIn('보이지',self.ctx._hotbar_probe_events[-1]['message'])
    def test_bridge_command_serializes_key_list_basename_on_existing_route(self):
        from tools.local_original_session.companion_bridge_host import request_text
        import json
        value=json.loads(request_text(dict(pid=1,birth=2,candidate_sha256='a'*64),3,
            dict(command='hotbar-keys',owner_uid=1,view_file='companion-ats-view-1-2.json')))
        self.assertEqual((value['command'],value['owner_uid'],value['view_file']),
            ('hotbar-keys',1,'companion-ats-view-1-2.json'))
    def test_malformed_borrowed_spell_consumed(self):
        self.fixture.owner_state.hp=1
        before=self.record.mp
        self.assertTrue(self.cast(payload=pb.encode_uint32(1,0)+pb.encode_bytes(2,b'\x80')))
        self.assertEqual(self.record.mp,before)
    def test_before_settings_and_start_done_publish_order(self):
        from tools.local_original_session.world_extensions import RuntimeExtensions
        command._hotbar_probe_initialize(self.ctx)
        seen=[]
        async def base(w,row,replies,**kw):seen.extend(int.from_bytes(x[2:4],'little') for x in replies)
        self.ctx.broker=NS(_send=base)
        self.ctx.realm=NS(service=lambda w:NS(snapshot=lambda:NS(uid=1)))
        self.characters[1]={'class':1}
        async def send(w,row,frames,lock):seen.extend(int.from_bytes(x[2:4],'little') for x in frames)
        self.ctx._world_send=send
        command._hotbar_command_started(self.ctx)
        asyncio.run(self.ctx.broker._send(self.writer,{},(command._wire(0x4e38,b''),command._wire(0x4ed7,b'')),game=True))
        self.assertEqual(seen,[0x4e38,0x4e60,0x4ed7])
        command._hotbar_command_stopped(self.ctx)
        command._hotbar_probe_initialize(self.ctx)
        command._hotbar_command_started(self.ctx)
        seen.clear()
        asyncio.run(self.ctx.broker._send(self.writer,{},(b'\x08\0\xef\x4e\x08\x09\0\0',),game=True))
        self.assertEqual(seen,[0x4e60,0x4eef])
        command._hotbar_command_stopped(self.ctx)

if __name__=='__main__':unittest.main()
