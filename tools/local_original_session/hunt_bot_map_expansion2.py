"""MapExp2 ordered socket smoke paths; retained fresh saved-map fixtures."""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter, deque
import json
import hashlib
from pathlib import Path
import time
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot_dungeons as dungeon
from tools.local_original_session import world_maps
from tools.local_original_session.world_terrain import WorldTerrain

DATA = Path(__file__).parent / 'data/m6/map_expansion2.json'
POPULATION = DATA.with_name('map_expansion2_population.json')

class ExpansionScenario(dungeon.DungeonScenario):
    def __init__(self,args,case,directory,transitions,policy):
        matrix.Matrix.__init__(self,args,'dungeon_items',directory)
        self.case=case; self.family=case['case_id']; self.transitions=transitions
        self.dungeon_policy=policy; self.stage='startup'
        self.danger_return = None
        self._planned_steps=deque(); self._planned_key=None; self.stair_history=[]
        r=case['entry']; origin=tuple(r['origin'])
        transition=world_maps.MapTransition(world_maps.MapDestination(*r['destination']),r['ref'],r['source'],r['native_trigger_status'])
        self.entry=origin,transition
        terrain=WorldTerrain.load(map_ids=(origin[0],))
        self.map_start=tuple(case['start']) if 'start' in case else dungeon.entrance_start(terrain,origin,transitions)

    def initialize_hunt_fixture(self):
        # Fresh saved test character only; use ordinary growth and existing
        # typed equipment initialization, never active HP or monster edits.
        import copy
        original=self.args
        self.args=copy.copy(original)
        self.args.fixture_level=99 if self.case['map_id']==37 else original.fixture_level
        try:
            super().initialize_hunt_fixture()
        finally:
            self.args=original
        if self.case['map_id'] not in (36,37):
            return
        from tools.local_original_session import inventory, equipment_store
        from tools.local_original_session import world_enchant_inventory as enchant
        data=self.broker._world.data
        fixture_enchant=20 if self.case['map_id']==37 else 9
        frame=self.broker._inventory_kit_frame(1)
        original_rows=[dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        rows=[row for row in original_rows if row[2] in (117,89,109,104,128,17,296,162)]
        # +9/+20 is an explicit retained starting fixture, not an acquisition or
        # enchant-RNG claim. The product still consumes real owned equipment.
        for row in rows:
            definition=data.items[row[2]]
            if definition.equippable:
                row[18]=enchant.enchanted_name(definition,fixture_enchant)
        next_uid=max(row[1] for row in original_rows)+1
        self.extra_gear=(78,92,280,306,15384,15384,567)
        self.extra_gear_uids=[]
        for template in self.extra_gear:
            definition=data.items[template]
            row=dict(original_rows[0])
            # Accessories are +0. These ordinary weapon/armor definitions
            # have known safety/normal-scroll policy; no probability run or
            # successful acquisition is claimed for this starting fixture.
            level=0 if template in (306,15384,567) else fixture_enchant
            row.update({1:next_uid,2:template,4:1,7:definition.icon,18:enchant.enchanted_name(definition,level)})
            if template in (306,15384,567):self.extra_gear_uids.append(next_uid)
            next_uid+=1;rows.append(row)
        fruit=dict(original_rows[0]);fruit_count=480 if self.case['map_id']==37 else 200
        fruit.update({1:next_uid,2:279,4:fruit_count,7:data.items[279].icon,18:b''})
        rows.append(fruit)
        frame=inventory.build_kit_frame(rows)
        self.store.grant(1,frame)
        by_template={row[2]:row for row in rows}
        equipped=(117,89,92,109,104,128,280)
        self.equipment.initialize_kit(1,frame,initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=by_template[self.extra_gear[0]][1],slots=tuple((data.items[t].slot_key,by_template[t][1])
                for t in equipped if data.items[t].kind=='armor'))
        self.fixture_notes.append(dict(starting_equipment_enchant=fixture_enchant,explicit_extra_equipment=self.extra_gear,
            non_enchantable_or_accessory_starting_level=0,ent_fruit279_count=fruit_count,
            scope='fresh pre-login retained fixture through InventoryStore.grant/FIRST equipment init; finite supplies; no live grants, RNG, monster or user-save change'))

    async def open(self,**options):
        # The shared bot's final login expectation predates these maps. Its
        # entered callback has already observed ACK -> map -> status -> self.
        # Broaden only this fixture's expectation, retaining actual wire values.
        from unittest.mock import patch
        original=matrix.hs.ScenarioBot
        expected=self.map_start
        class SavedMapBot(original):
            async def login(bot):
                try:
                    return await super().login()
                except hb.BotFailure as error:
                    if (str(error)!='MAP0_SELF_POSITION_AND_HP_REQUIRED' or not bot.selected or bot.position is None
                            or (bot.map_id,*bot.position)!=expected or bot.hp is None or not bot.max_hp):
                        raise
                    await bot.alive()
        with patch.object(matrix.hs,'ScenarioBot',SavedMapBot):
            await super().open(**options)
        if self.case['map_id'] not in (36,37):
            await self.gear((89,104,128,129))
        for uid in getattr(self,'extra_gear_uids',()):
            await self.gear_uid(uid)
        if self.case['map_id'] in (36,37):
            # Actual owned consumables; ordinary product speed and expiry.
            await self.use(17);await self.use(296)
            self.last_speed_use=time.monotonic()
            from tools.local_original_session import world_weight, inventory
            saved=self.store.restore(self.bot.self_uid)
            burden=world_weight.inventory_weight(inventory.validate_kit_frame(saved),
                world_weight.load_weight_catalog())
            # Read-only observation of the resulting combat profile confirms
            # the finite starting bag is admitted by the unchanged weight rule.
            state=self.broker._world.combat.pcs[self.bot.self_uid]
            data=self.bot.data
            capacity=world_weight.maximum_weight(state.profile.strength,state.profile.con)+data.items[567].modifiers['weight_bonus']
            weight=world_weight.weight_state(burden,capacity)
            self.record('finite_fixture_combat_profile',state.profile.weapon.small>0 and not weight.attack_blocked,
                level=state.profile.level,ac=state.profile.ac,strength=state.profile.strength,
                weapon=state.profile.weapon.name,weapon_enchant=state.profile.weapon.enchant,
                burden=burden,capacity=capacity,weight_gauge=weight.gauge,
                scope='observed ordinary worn-item projection; product guard remains active')

    async def use(self,template,**options):
        # Shared navigation asks for potion14. Strong-map fixtures explicitly
        # carry the catalogued lighter equivalent279; send its real owned UID.
        if template==14 and self.case['map_id'] in (36,37):template=279
        return await super().use(template,**options)

    async def dungeon_items(self):
        bot=self.bot
        if self.case.get('region_id'):
            start=bot.position; before=bot.moves
            await self.navigate(self.entry[0][1:])
            self.record('walk_region_boundary',bot.position==self.entry[0][1:] and bot.moves>before,
                        region_id=self.case['region_id'],before=start,after=bot.position,
                        scope='walk over client region bounds on existing map4, no map warp')
        else:
            await self.cross(self.entry,'walk_actual_stair_entry')
        self.stage='walk_inside'
        start=bot.position
        for h,(dx,dy) in enumerate(hb.DELTAS):
            point=start[0]+dx,start[1]+dy
            if (bot.map_id,*point) not in self.transitions and self.broker._world.terrain.can_step(bot.map_id,*start,h) is True:
                await self.navigate(point);break
        self.record('walk_inside',bot.position!=start,before=start,after=bot.position)
        if self.case.get('population_group_ids'):
            # Existing finite owned supplies, ordinary product speed/expiry.
            await self.use(17)
            await self.use(296)
        if self.case['combat']:
            self.stage='received_actor_combat'
            self.start_ground=set(bot.ground)
            await self.case_combat()
            await self.observe_population()
        else:
            self.record('non_hunting_transit_floor',True,scope='client IT floors1-3: movement/return only; no fabricated monsters')
        await self.return_to_safety()

    async def observe_population(self):
        """Walk to newly selected species; inspect slots without forcing spawns."""
        bot = self.bot
        for group_id in self.case.get('population_group_ids', ()):
            self.stage = 'population_' + group_id
            group = next(g for g in self.broker._world.spawner.groups
                         if g.spec.group_id == group_id)
            spec = group.spec
            center = ((spec.rect.x1 + spec.rect.x2)//2,
                      (spec.rect.y1 + spec.rect.y2)//2)
            def received():
                return [(uid, dict(actor)) for uid, actor in bot.actors.items()
                        if actor['alive'] and actor['template'] == spec.template_id]
            # A source-range rectangle can contain walls; walk towards the
            # nearest standable cell and stop on a real visibility observation.
            terrain = self.broker._world.terrain
            goal = min(((x, y) for x in range(spec.rect.x1, spec.rect.x2+1)
                        for y in range(spec.rect.y1, spec.rect.y2+1)
                        if terrain.can_stand(bot.map_id, x, y) is True),
                       key=lambda point: hb.distance(bot.position, point))
            await self.navigate(goal, predicate=lambda: bool(received()))
            # Initial random placement may leave vacancies until its ordinary
            # retry tick. Observe that lifecycle; never fill slots directly.
            until = time.monotonic() + 15
            while sum(slot.uid is not None for slot in group.slots) < spec.target_count:
                if bot.dead or time.monotonic() >= until:
                    break
                if bot.hp < bot.max_hp*.6:
                    await self.use(14)
                await bot.alive()
                await asyncio.sleep(.1)
            actors = received()
            homes = [slot.home for slot in group.slots if slot.uid is not None]
            self.record('population_received_' + str(spec.template_id),
                group.active and len(homes) == spec.target_count and bool(actors),
                map_id=bot.map_id, group_id=group_id, template_id=spec.template_id,
                target_count=spec.target_count, occupied_slots=len(homes),
                received_actors=[dict(uid=uid, **actor) for uid, actor in actors],
                spawn_homes=homes,
                scope='ordinary interest activation and received live actors; four-species combat/drop not tested')

    async def return_to_safety(self):
        bot = self.bot
        self.stage='return162'
        departure=(bot.map_id,*bot.position)
        expected=self.dungeon_policy.return_for(bot.map_id)
        if bot.map_id==4:
            expected=world_maps.load_gludin_policy().town_return
        await self.use(162)
        self.record('return162_destination',bot.map_id==expected.map_id and bot.position==(expected.x,expected.y),
                    departure=departure,expected=(expected.map_id,expected.x,expected.y),actual=(bot.map_id,*bot.position))
        from tools.local_original_session import movement
        saved=self.broker.realm.positions.restore(movement.Position(bot.self_uid,bot.character,0,0,0))
        self.record('return_position_saved',(saved.map_id,saved.word0,saved.word1)==(bot.map_id,*bot.position),
                    saved=(saved.map_id,saved.word0,saved.word1))
        if self.danger_return is not None:
            self.record('danger_return_survived',not bot.dead and bot.hp>0,
                        **self.danger_return,
                        scope='received boss reconnaissance and real scroll/position save only; boss kill/drop untested')

    async def case_combat(self):
        bot=self.bot; before=set(bot.kills); before_pickups=bot.pickups
        group=next(s for s in self.broker._world.data.spawns if s.group_id==self.case['group_id'])
        center=(group.rect.x1+group.rect.x2)//2,(group.rect.y1+group.rect.y2)//2
        until=time.monotonic()+(self.args.boss_timeout if self.case['map_id']==37 else self.args.hunt_timeout)
        # Some retained representatives (Blob145 on map26) have no active
        # drop policy. Require their real kill, without waiting for impossible
        # loot or manufacturing a drop. Populated drop tables retain GET/save.
        requires_pickup=bool(self.broker._world.data.drops.get(group.template_id,()))
        received_drops={}; pickup_rows=[]
        while not bot.kills-before or (requires_pickup and bot.pickups==before_pickups):
            if bot.dead:raise hb.BotFailure('OWNER_DIED_DURING_EXPANSION_HUNT')
            if time.monotonic()>until:raise hb.BotFailure('EXPANSION_KILL_OBSERVATION_DEADLINE')
            if self.case['map_id']==37:
                # This is Antharas, not an ordinary hunting-floor target. The
                # sourced L1J spell10054 is (250+12d10)*INT coefficient*5
                # even above 50% boss HP (mobskill act4); Eruption uses x20.
                # A 60% potion threshold cannot prevent a lethal single hit.
                # Observe the received live actor and return before engaging;
                # no boss kill/drop completion is claimed by this path.
                bosses=[(uid,r) for uid,r in bot.actors.items()
                        if r['alive'] and r['template']==group.template_id]
                if bosses:
                    uid,actor=min(bosses,key=lambda p:hb.distance(bot.position,p[1]['position']))
                    self.danger_return=dict(map_id=bot.map_id,template_id=group.template_id,
                        received_uid=uid,received_position=actor['position'],
                        hp=bot.hp,max_hp=bot.max_hp,own_swings=bot.swings,
                        boss_hp=22200,boss_ac=-99,boss_strength=80,
                        unresisted_spell10054_upper_bound=2890,
                        reason='solo Antharas spell burst risk; L1J npc45682/mobskill act2,4/skills45,10054')
                    self.record('received_boss_danger',True,**self.danger_return)
                    return
            if self.case['map_id'] in (36,37) and time.monotonic()-self.last_speed_use>=120:
                await self.use(17);await self.use(296);self.last_speed_use=time.monotonic()
            if bot.hp<bot.max_hp*(.8 if self.case['map_id'] in (36,37) else .6):
                await self.use(279 if self.case['map_id'] in (36,37) else 14)
            loot=[(uid,r) for uid,r in bot.ground.items() if uid not in self.start_ground and bot.pickup_refused[uid]<3]
            if loot and bot.kills-before:
                uid,row=min(loot,key=lambda p:hb.distance(bot.position,p[1]['position']))
                received_drops[uid]=dict(row)
                if hb.distance(bot.position,row['position'])<=1:
                    prior={k:dict(v) for k,v in bot.inventory.items()}; marker=bot.peer.ordinal;count=bot.pickups
                    await bot.pickup(uid)
                    if bot.pickups>count:
                        from tools.local_original_session import inventory
                        saved={i.identifier:dict(i.raw_fields) for i in inventory.validate_kit_frame(self.store.restore(bot.self_uid))}
                        changes=[dict(uid=k,template_id=v.get(2),before=prior.get(k,{}).get(4,0),after=v.get(4,0),saved=saved.get(k,{}).get(4,0))
                            for k,v in bot.inventory.items() if v.get(4,0)>prior.get(k,{}).get(4,0)]
                        self.record('received_drop_pickup_saved',bool(changes) and all(r['after']==r['saved'] for r in changes),
                            ground_uid=uid,received_ground=row,inventory_changes=changes,
                            response_ordinals=[f.ordinal for f in bot.peer.frames if f.ordinal>marker and f.opcode in (0x4e40,0x0964,0x0965)])
                        pickup_rows.append(dict(ground_uid=uid,changes=changes))
                else:await bot.step(row['position'],radius=1)
                continue
            if self.case['map_id']==36 and bot.kills-before:
                # Natural drop rolls are not guaranteed. Do not wait through
                # corpse lifetime + repeated respawns solely to force a loot
                # result; preserve a separate, honest unobserved-loot result.
                if set(bot.ground)-self.start_ground:
                    raise hb.BotFailure('RECEIVED_DROP_PICKUP_REFUSED')
                self.record('no_drop_observed',True,map_id=bot.map_id,
                    template_id=group.template_id,
                    scope='first real kill produced no received loot; drop/pickup unverified; no respawn farming')
                break
            living=[(uid,r) for uid,r in bot.actors.items() if r['alive'] and r['template']==group.template_id]
            if living:
                uid,actor=min(living,key=lambda p:hb.distance(bot.position,p[1]['position']))
                if hb.distance(bot.position,actor['position'])<=1:await bot.attack(uid)
                else:await bot.step(actor['position'],radius=1)
            else:await bot.step(center,radius=1)
            if time.monotonic()-bot.last_alive>=.5:await bot.alive()
            await asyncio.sleep(.03)
        self.record('received_actor_kill',True,map_id=bot.map_id,template_id=group.template_id,
                    killed_uids=sorted(bot.kills-before),swings=bot.swings,
                    policy='received live actor, attack requests and observed death; unchanged product RNG/stats')
        if requires_pickup and bot.pickups>before_pickups:
            self.record('received_drop_and_pickup',bool(received_drops) and bot.pickups>before_pickups,
                        map_id=bot.map_id,template_id=group.template_id,ground=received_drops,pickups=pickup_rows,
                        scope='representative species only; natural unchanged drop RNG; received ground UID -> GET -> remove/inventory -> durable inventory')
        elif not requires_pickup:
            self.record('no_active_drop_policy',True,map_id=bot.map_id,template_id=group.template_id,
                        scope='NO_ACTIVE_DROP_POLICY: kill required; drop/pickup untested, no drop added')

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',default='all')
    p.add_argument('--timeout',type=hb.positive,default=8)
    p.add_argument('--navigation-timeout',type=hb.positive,default=180)
    p.add_argument('--hunt-timeout',type=hb.positive,default=3600)
    p.add_argument('--boss-timeout',type=hb.positive,default=2400)
    p.add_argument('--fixture-level',type=int,default=60)
    p.add_argument('--output-root',type=Path,default=None,
                   help='Parent for preserved run evidence (use workspace _work if runs ACL prevents reading).')
    p.set_defaults(scenario='dungeon_items',minutes=1,potion_threshold=.5,companion_revive_exp=False)
    return p

async def run(args):
    data=json.loads(DATA.read_text(encoding='utf-8'))
    cases=data['cases'] if args.case=='all' else [c for c in data['cases'] if c['case_id'] in args.case.split(',')]
    if not cases:raise ValueError('unknown or not-ready case: '+args.case)
    root=(args.output_root or Path(__file__).resolve().parents[2]/'work/local_original_session/runs').resolve()
    root.mkdir(parents=True,exist_ok=True)
    # Python 3.13 mkdtemp's Windows mode0700 ACL can make the new folder
    # unreadable to this managed token. Inherit the workspace parent's ACL.
    directory=root/('hunt-map-expansion2-'+uuid.uuid4().hex[:12])
    directory.mkdir()
    policy=world_maps.load_dungeon_policy(); transitions={**world_maps.TRANSITIONS,**policy.transitions}
    results=[]
    for case in cases:
        profile=directory/case['case_id'];profile.mkdir()
        scenario=ExpansionScenario(args,case,profile,transitions,policy)
        # Contribute to the existing Matrix result provenance at startup only;
        # these fingerprints do not gate requests or replace terrain evidence.
        from tools.local_original_session import world_feature_dungeons
        inputs=[Path(__file__),Path(world_maps.__file__),Path(world_feature_dungeons.__file__),DATA,POPULATION]
        for folder in ('m1','m3','m4','m6'):
            inputs.extend(p for name in ('monsters.json','drops.json') if (p:=DATA.parent.parent/folder/name).exists())
        for p in inputs:
            matrix.SOURCE_SHA256[str(p)]=dict(file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),basis='map expansion case startup input')
        with matrix.environment(SL_EXPERIMENT_MAP=2,SL_EXPERIMENT_SHOP=1,SL_COMPANION=0,
                SL_COMPANION_PET_UI=0,SL_SPELL_EXP=0,SL_COMPANION_REVIVE_EXP=0):
            print('START '+case['case_id'],flush=True)
            result=await scenario.run_matrix()
        result['case']=case
        (profile/'result.json').write_text(json.dumps(matrix.safe(result),ensure_ascii=False,indent=2),encoding='utf-8')
        results.append(result)
        print(f"{result['status']} {case['case_id']}: {result['elapsed_seconds']}s requests={result['requests']}",flush=True)
        if not result['cleanup_complete']:break
    population=json.loads(POPULATION.read_text(encoding='utf-8'))
    rows=[]
    for result in results:
        checks={r['check']:r for r in result['checks']}
        case=result['case']; kill=checks.get('received_actor_kill',{}); drop=checks.get('received_drop_and_pickup',{})
        rows.append(dict(case_id=case['case_id'],name_ko=case['name_ko'],status=result['status'],
            template_id=kill.get('template_id',checks.get('received_boss_danger',{}).get('template_id')),
            combat=('NOT_ATTEMPTED_DANGER_RETURN' if 'received_boss_danger' in checks else
                kill.get('status','UNCONFIRMED') if case['combat'] else 'NOT_APPLICABLE_TRANSIT'),
            drop_pickup=('NOT_APPLICABLE_TRANSIT' if not case['combat'] else
                'NOT_ATTEMPTED_DANGER_RETURN' if 'received_boss_danger' in checks else
                'NO_ACTIVE_DROP_POLICY' if 'no_active_drop_policy' in checks else
                'NO_DROP_OBSERVED' if 'no_drop_observed' in checks else drop.get('status','UNCONFIRMED')),
            kill_count=len(kill.get('killed_uids',[])),pickup_count=len(drop.get('pickups',[])),
            return_saved=checks.get('return_position_saved',{}).get('status','UNATTEMPTED'),cleanup_complete=result['cleanup_complete'],
            first_failure=result.get('failure'),directory=result['directory']))
    summary=dict(output_directory=str(directory),counts=dict(Counter(r['status'] for r in results)),results=results,map_results=rows,
        scope=f'LOCAL ordered packet paths on fresh pre-login saved-map level{args.fixture_level} knight; map36 +9/200fruit279 first kill and any naturally received loot, without respawn farming; map37 level99/+20/480fruit279 received-boss reconnaissance and danger return only, boss kill/drop NOT TESTED. Catalogued strength/capacity gear and finite ordinary haste/brave. All gear is pre-login test supply: normal acquisition, enchant difficulty and ordinary level60 boss play are unverified. No travel from creation point or native client/UI/input equivalence.',
        unresolved=population['unresolved'],limitations=population['limitations'])
    (directory/'summary.json').write_text(json.dumps(matrix.safe(summary),ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['| 맵 | 대표 template | 전투 | 드롭/줍기 | 귀환 저장 | 정리 | 결과 |','|---|---:|---|---|---|---|---|']
    lines += [f"| {r['name_ko']} ({r['case_id']}) | {r['template_id']} | {r['combat']} | {r['drop_pickup']} | {r['return_saved']} | {r['cleanup_complete']} | {r['status']} |" for r in rows]
    lines += ['',summary['scope'],'','미해결 드롭 '+str(len(population['unresolved']))+'행은 summary.json에 원문 근거와 함께 보존. 대표종 결과를 전체 33종/63스폰 또는 원본 화면/입력 검증으로 확대하지 않음.']
    (directory/'map-results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary

def main(argv=None):
    result=asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps({k:result[k] for k in ('output_directory','counts')},ensure_ascii=False))
    return 0 if set(result['counts'])=={'PASS'} else 1

if __name__=='__main__':raise SystemExit(main())
