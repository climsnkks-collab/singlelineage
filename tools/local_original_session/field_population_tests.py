"""Retained-source population/loader checks; no sockets or native client."""
from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import game_data as gd
from tools.local_original_session import world_feature_dungeons as dungeons
from tools.local_original_session import world_combat as wc
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_feature_m5 import load_m5_data
from tools.local_original_session.world_interest_spawn import InterestSpawner, SlotState, with_dungeon_data
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_terrain import WorldTerrain
from tools.local_original_session.world_visibility import WorldView

HERE = Path(__file__).parent
DATA = HERE/'data/m6'


class FieldPopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map0 = json.loads((DATA/'map0_population.json').read_text(encoding='utf-8'))
        cls.fields = json.loads((DATA/'field_population.json').read_text(encoding='utf-8'))
        cls.sources = json.loads((DATA/'field_population_sources.json').read_text(encoding='utf-8'))
        with patch.dict(os.environ, {'SL_EXPERIMENT_MAP':'2'}):
            cls.base = with_dungeon_data(gd.load_m1())
        cls.data = load_m5_data(dungeons.load_dungeon_data(cls.base))

    def test_map0_all_88_sql_rows_and_7_new_sprite_representatives(self):
        rows = self.map0['groups']
        self.assertEqual((len(rows),sum(r['target_count']['value'] for r in rows)), (88,2729))
        self.assertEqual(len({r['l1j_spawn_id'] for r in rows}),88)
        expected = {45005:(14,55,100),45010:(206,998,100),45012:(207,999,100),
            45021:(189,947,44),45060:(12,31,69),70984:(188,945,3),81159:(319,1094,1)}
        for npc,(tid,sprite,count) in expected.items():
            m=self.data.monsters[tid]
            self.assertEqual((m.l1j_npcid,m.sprite_id),(npc,sprite))
            self.assertEqual(sum(r['target_count']['value'] for r in rows if r['l1j_npcid']==npc),count)
            self.assertEqual(m.sources['level'].kind,'l1j')
        self.assertFalse(self.map0['excluded'])
        self.assertEqual(sum(r['count'] for r in self.map0['historical_excluded']),417)

    def test_source_rectangle_upper_bounds_are_exclusive(self):
        for r in (*self.map0['groups'], *self.fields['groups']):
            src=r['l1j_row']; rect=r['rect']['value']
            if int(src['locx1']) and int(src['locx2'])>int(src['locx1']):
                self.assertEqual(rect,dict(x1=int(src['locx1']),y1=int(src['locy1']),
                    x2=int(src['locx2'])-1,y2=int(src['locy2'])-1))

    def test_cow_triangular_policy_and_outside_slime_fallback_are_preserved(self):
        rows={r['l1j_spawn_id']:r for r in self.map0['groups']}
        for sid,point in ((27521,[32583,32946]),(27522,[32562,32956]),(27523,[32628,32958])):
            g=next(g for g in self.data.spawns if g.group_id==rows[sid]['group_id']['value'])
            self.assertEqual(dict(g.placement),dict(kind='triangular',origin=point,random=[10,10]))
            self.assertEqual(g.rect,gd.Rect(point[0]-9,point[1]-9,point[0]+9,point[1]+9))
        r=rows[62074]
        self.assertEqual(r['placement']['value']['fallback'],[32635,32843])
        self.assertFalse(gd._rect(r['rect']['value']).contains(32635,32843))
        self.assertEqual(r['l1j_row']['locx'],'32635')

    def test_bird_metadata_excludes_death8_and_passive_speeds_remain_explicit(self):
        bird=self.data.monsters[319]
        self.assertIsNone(bird.death_action)
        self.assertEqual((bird.move_interval_ms,bird.attack_interval_ms,bird.corpse_ms),(0,0,0))
        self.assertIn('fly',bird.sources['death_action'].ref)
        for tid in (14,206,207,189,188):
            self.assertEqual(self.data.monsters[tid].attack_interval_ms,0)
            self.assertGreater(self.data.monsters[tid].move_interval_ms,0)
        self.assertEqual(self.data.monsters[12].attack_interval_ms,667)

    def test_cow_runtime_uses_independent_l1j_triangular_draws(self):
        cow=next(g for g in self.data.spawns if g.group_id=='m6_map0_l1j_27521')
        # Across all seeds, compare actual placement to the independent L1J
        # draws, including RNG state consumed for heading; no statistics gate.
        for seed in range(32):
            with self.subTest(seed=seed):
                expected=random.Random(seed)
                ox,oy=cow.placement['origin']
                point=(ox+expected.randrange(10)-expected.randrange(10),
                       oy+expected.randrange(10)-expected.randrange(10))
                heading=expected.randrange(8)
                spawner=InterestSpawner(EntityRegistry(),replace(self.data,spawns=(cow,)),
                    passable=lambda *_:True,rng=random.Random(seed))
                spawner.update_interest([(0,ox,oy)],100)
                slot=spawner.groups[0].slots[0]
                entity=spawner.entities.get(slot.uid)
                self.assertEqual((entity.x,entity.y,entity.heading),(*point,heading))
                self.assertEqual(spawner.rng.getstate(),expected.getstate())
        # Other templates with triangular metadata still use their rectangle.
        other=replace(cow,template_id=12)
        expected=random.Random(4)
        point=(expected.randint(other.rect.x1,other.rect.x2),
               expected.randint(other.rect.y1,other.rect.y2))
        spawner=InterestSpawner(EntityRegistry(),replace(self.data,spawns=(other,)),
            passable=lambda *_:True,rng=random.Random(4))
        spawner.update_interest([(0,ox,oy)],100)
        self.assertEqual(spawner.groups[0].slots[0].home,point)

    def test_cow_runtime_keeps_passability_occupancy_and_retry(self):
        cow=next(g for g in self.data.spawns if g.group_id=='m6_map0_l1j_27521')
        ox,oy=cow.placement['origin']
        for tile_state in (False,None,'occupied'):
            with self.subTest(tile_state=tile_state):
                entities=EntityRegistry()
                if tile_state=='occupied':
                    entities.add(Kind.NPC,0,ox,oy,template_id=188)
                passable=Mock(return_value=True if tile_state=='occupied' else tile_state)
                spawner=InterestSpawner(entities,replace(self.data,spawns=(cow,)),
                    passable=passable,rng=Mock(randrange=Mock(return_value=0)))
                self.assertFalse(spawner.update_interest([(0,ox,oy)],100))
                slot=spawner.groups[0].slots[0]
                self.assertEqual((slot.state,slot.uid,slot.retry_at),(SlotState.EMPTY,None,105))
                self.assertEqual(passable.call_count,8)
                self.assertFalse(spawner.tick(104.999))
                self.assertEqual(passable.call_count,8)
                self.assertFalse(spawner.tick(105))
                self.assertEqual(passable.call_count,16)

    def test_bird_no_death8_retains_kill_reward_corpse_and_cleanup(self):
        bird=next(g for g in self.data.spawns if g.template_id==319)
        for template in (319,188):
            with self.subTest(template=template):
                spec=replace(bird,template_id=template,target_count=1)
                data=replace(self.data,spawns=(spec,))
                runtime=WorldRuntime(clock=lambda:100.0)
                spawner=InterestSpawner(runtime.entities,data,passable=lambda *_:True,
                    rng=random.Random(7))
                view=WorldView(runtime,spawner,data=data)
                self.addCleanup(view.close)
                view.update_pc(1,spec.map_id,spec.rect.x1-1,spec.rect.y1,reset=True)
                slot=spawner.groups[0].slots[0]
                target=runtime.entities.get(slot.uid)
                monster=data.monsters[template]
                timer=runtime.scheduler.schedule(200,target.ref,'test',lambda now:None)
                view._reward=Mock()
                with patch.object(wc,'death_frame',wraps=wc.death_frame) as death:
                    view._apply_monster_swing(1,1,target,monster,slot.hp,
                        wc.Swing(True,slot.hp),100)
                    self.assertEqual(death.call_count,0 if template==319 else 1)
                self.assertFalse(target.alive)
                self.assertTrue(timer.cancelled)
                self.assertEqual(slot.state,SlotState.WAIT)
                self.assertEqual(slot.corpse_at,100+monster.corpse_ms/1000)
                self.assertEqual(view.combat.kills[-1].npc_uid,target.uid)
                view._reward.assert_called_once_with(1,target,monster,100)
                self.assertIn(target.uid,view.visibility.known[1])
                view.drain(1)
                view.tick(slot.corpse_at)
                self.assertIsNone(runtime.entities.get(target.uid))
                self.assertIsNone(spawner.slot_for(target.uid))
                self.assertNotIn(target.uid,view.visibility.known[1])
                self.assertTrue(any(int.from_bytes(f[2:4],'little')==0x4e40
                    for f in view.drain(1)))

    def test_map4_sql_partition_and_source_density(self):
        rows=self.fields['groups'];excluded=self.sources['excluded']
        self.assertEqual((len(rows),sum(r['target_count']['value'] for r in rows)),(5344,6045))
        self.assertEqual((len(excluded),sum(r['count'] for r in excluded)),(180,2386))
        self.assertEqual(len({r['l1j_spawn_id'] for r in rows}|{r['spawn_id'] for r in excluded}),5524)
        self.assertFalse({r['l1j_spawn_id'] for r in rows}&{r['spawn_id'] for r in excluded})
        self.assertEqual(sum(r['count'] for r in excluded if r['npc_id'] in (45166,45167)),2200)
        self.assertEqual(sum(r['count'] for r in excluded if r['reason'].startswith('SOURCE_SUPPORT')),16)
        for row in rows:
            self.assertEqual(int(row['l1j_row']['count']),row['target_count']['value'])
            self.assertEqual(int(row['l1j_row']['mapid']),4)

    def test_c5_aliases_reuse_existing_stats_and_own_sql_population(self):
        expected={45133:(701,31),45207:(709,35),45351:(12179,56),
            45229:(501,22),45329:(879,21)}
        aliases={r['l1j_npcid']:r for r in self.sources['population_identity_aliases']}
        for npc,(tid,count) in expected.items():
            rows=[r for r in self.fields['groups'] if r['l1j_npcid']==npc]
            self.assertEqual(sum(r['target_count']['value'] for r in rows),count)
            self.assertEqual({r['template_id']['value'] for r in rows},{tid})
            self.assertFalse(any(r['npc_id']==npc for r in self.sources['excluded']))
            source=json.loads(Path(aliases[npc]['definition_ref']).read_text(encoding='utf-8'))
            definition=next(m for m in source['monsters'] if m['template_id']['value']==tid)
            self.assertEqual(next(m for m in self.fields['monsters'] if m['template_id']['value']==tid),definition)
            self.assertEqual(self.data.monsters[tid],gd._monsters({'monsters':[definition]})[tid])
        self.assertEqual(aliases[45351]['candidate_templates'],[468,12179])
        self.assertNotIn(468,self.data.monsters)

    def test_loader_retains_all_local_supplements_in_either_m5_order(self):
        reverse=dungeons.load_dungeon_data(load_m5_data(self.base))
        self.assertEqual({g.group_id:g for g in self.data.spawns},{g.group_id:g for g in reverse.spawns})
        self.assertEqual(len({g.group_id for g in self.data.spawns}),len(self.data.spawns))
        for mid,counts in ((0,(91,2732)),(4,(5557,6296))):
            groups=[g for g in self.data.spawns if g.map_id==mid]
            self.assertEqual((len(groups),sum(g.target_count for g in groups)),counts)
        for g in self.base.spawns:
            if g.map_id==4:
                self.assertIs(next(s for s in self.data.spawns if s.group_id==g.group_id),g)
        for name in ('items','town','starter','pc_exp','action_speed'):
            self.assertIs(getattr(self.data,name),getattr(self.base,name))

    def test_actual_startup_installs_specs_and_empty_slots_with_m5_on_or_off(self):
        terrain=WorldTerrain.load(map_ids=(0,4))
        for enabled in (False,True):
            base=load_m5_data(self.base) if enabled else self.base
            world=WorldView.create(data=base,terrain=terrain,rng=random.Random(18))
            spawner,combat=world.spawner,world.combat
            ctx=SimpleNamespace(world=world,_world_map_exp=2)
            with patch.object(dungeons,'load_island_policy',return_value=SimpleNamespace(maps=())):
                dungeons._world_dungeons_initialize(ctx)
            self.assertIs(world.spawner,spawner);self.assertIs(world.combat,combat)
            self.assertEqual({g.spec.group_id:g.spec for g in world.spawner.groups},
                {g.group_id:g for g in world.data.spawns})
            self.assertTrue(all(len(g.slots)==g.spec.target_count and all(s.uid is None for s in g.slots)
                for g in world.spawner.groups))
            groups=[g for g in world.spawner.groups if g.spec.map_id==4]
            self.assertEqual(sum(len(g.slots) for g in groups),6296 if enabled else 6185)
            world.close()

    def test_default_bot_samples_production_rows_without_template_fixture(self):
        from tools.local_original_session.hunt_bot_monster_fill import population_groups
        groups=population_groups(self.data)
        self.assertEqual(len(groups),7)
        self.assertEqual(groups[0].template_id,319)
        actual={g.group_id:g for g in self.data.spawns}
        self.assertTrue(all(actual[g.group_id] is g for g in groups))


if __name__=='__main__':
    unittest.main()
