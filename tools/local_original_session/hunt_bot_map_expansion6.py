"""MapExp6 ordered stair/paid-entry, representative kill, return/save and close."""
import asyncio
from collections import Counter
import hashlib
import json
import time
from pathlib import Path

from tools.local_original_session import hunt_bot_map_expansion4 as driver
from tools.local_original_session import hunt_bot as hb


class Expansion6Scenario(driver.ExpansionScenario):
    def record(self,name,passed,**fields):
        if name=='outside_entrance_saved_map_fixture':
            level=self.broker._world.combat.pcs[self.bot.self_uid].profile.level
            fields['scope']=f'fresh pre-login position/Lv{level} fixture; no mainland/boat continuous-travel claim'
        if name=='non_hunting_walk_only' and self.args.travel_only:
            name='explicit_hunting_map_travel_only'
            fields['scope']='combat skipped explicitly on unchanged hunting map; travel/return/save only'
        return super().record(name,passed,**fields)

    def initialize_hunt_fixture(self):
        import copy
        original_args = self.args
        self.args = copy.copy(original_args)
        if (self.case['map_id']==65 and self.args.strong_fixture) or (self.case['map_id']==74 and self.args.boss_retry_fixture):
            self.args.fixture_level = 99
        try:
            super().initialize_hunt_fixture()
        finally:
            self.args = original_args
        if not self.args.strong_fixture or not self.case['combat']:
            return
        from tools.local_original_session import inventory, equipment_store
        from tools.local_original_session import world_enchant_inventory as enchant
        supplied = [dict(item.raw_fields) for item in inventory.validate_kit_frame(self.broker._inventory_kit_frame(1))]
        wanted = {3,117,89,98,104,109,128,129,14,17,296,7,162}
        rows = [row for row in supplied if row[2] in wanted]
        data = self.broker._world.data
        weapon_enchant, armor_enchant = (20,20) if self.case['map_id']==65 or self.args.boss_retry_fixture else (9,6)
        for row in rows:
            item = data.items[row[2]]
            if item.kind in ('weapon','armor'):
                row[18] = enchant.enchanted_name(item,weapon_enchant if item.kind=='weapon' else armor_enchant)
            elif row[2]==14:
                if self.case['map_id']==65 or self.args.boss_retry_fixture:
                    # Reuse finite light ent-fruit policy of existing map37 fixture.
                    row.update({2:279,4:480,7:data.items[279].icon,18:b''})
                else:
                    row[4]=200
            elif row[2] in (17,296):
                row[4]=10
        self.retry_extra_uids = []
        if self.args.boss_retry_fixture:
            next_uid = max(row[1] for row in supplied)+1
            # Existing catalogued gear; real0960 equips after login. Water40,
            # MR18 sources are ItemDef modifiers, not synthetic PC bonuses.
            for template in (403,111,15090,3935,499,499):
                definition = data.items[template]
                row = dict(supplied[0])
                level = 0 if template in (15090,3935,499) else 20
                row.update({1:next_uid,2:template,4:1,7:definition.icon,
                    18:enchant.enchanted_name(definition,level)})
                rows.append(row); self.retry_extra_uids.append(next_uid); next_uid += 1
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1,frame)
        by_template = {row[2]:row[1] for row in rows}
        self.equipment.initialize_kit(1,frame,initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=by_template[3],slots=tuple((data.items[t].slot_key,by_template[t]) for t in (117,98,109)))
        self.fixture_notes.append(dict(pre_login_strong_map=self.case['map_id'],
            level=99 if self.case['map_id']==65 or self.args.boss_retry_fixture else original_args.fixture_level,
            weapon_enchant=weapon_enchant,armor_enchant=armor_enchant,
            healing_template=279 if self.case['map_id']==65 or self.args.boss_retry_fixture else 14,
            healing_count=480 if self.case['map_id']==65 or self.args.boss_retry_fixture else 200,haste17=10,brave296=10,
            scope='separate fresh pre-login kit; no live grant, NPC/HP/RNG/combat or original/user save edit'))

    async def open(self,**options):
        await super().open(**options)
        if self.args.strong_fixture and self.case['combat']:
            for uid in self.retry_extra_uids:
                await self.gear_uid(uid)
            await self.use(17)
            await self.use(296)
            state = self.broker._world.combat.pcs[self.bot.self_uid]
            self.record('strong_fixture_observed_gear',state.profile.weapon.enchant==(20 if self.case['map_id']==65 or self.args.boss_retry_fixture else 9),
                ac=state.profile.ac,weapon_enchant=state.profile.weapon.enchant,level=state.profile.level,
                scope='explicit strong starting fixture only; not natural acquisition/enchant or ordinary-gear survival')

    async def use(self,template,**options):
        if template==14 and self.args.strong_fixture and (self.case['map_id']==65 or self.args.boss_retry_fixture):
            template=279
        return await super().use(template,**options)

    async def dungeon_items(self):
        original = self.case
        if self.args.travel_only:
            self.case = dict(original, combat=False)
        try:
            await super().dungeon_items()
        finally:
            self.case = original
            self.record('travel_only_scope',True,enabled=self.args.travel_only,
                scope='explicit travel-only mode skips hunting on the unchanged product hunting map; not a kill PASS')

    async def case_combat(self):
        if not self.args.boss_retry_fixture:
            return await super().case_combat()
        bot = self.bot
        before, start_swings = set(bot.kills),bot.swings
        group = next(g for g in self.broker._world.data.spawns if g.group_id==self.case['group_id'])
        center = (group.rect.x1+group.rect.x2)//2,(group.rect.y1+group.rect.y2)//2
        deadline = time.monotonic()+self.args.hunt_timeout
        attacked, observations = {},[]
        try:
            while not bot.kills-before:
                if bot.dead: raise hb.BotFailure('OWNER_DIED_DURING_MAP6_RETRY_HUNT')
                if time.monotonic()>deadline:raise hb.BotFailure('MAP6_RETRY_HUNT_TIMEOUT')
                if bot.hp < bot.max_hp*.95:
                    await self.use(14)
                    continue
                living = [(u,a) for u,a in bot.actors.items() if a['alive'] and a['template']==group.template_id]
                if living:
                    uid,actor = min(living,key=lambda p:hb.distance(bot.position,p[1]['position']))
                    if hb.distance(bot.position,actor['position'])<=1:
                        attacked[uid]=dict(actor);await bot.attack(uid)
                    else: await bot.step(actor['position'],radius=1)
                else:await bot.step(center,radius=1)
                observations.append(dict(hp=bot.hp,position=bot.position,
                    living=[dict(uid=u,template=a['template'],position=a['position'])
                        for u,a in bot.actors.items() if a['alive']]))
                if time.monotonic()-bot.last_alive>=.5:await bot.alive()
                await asyncio.sleep(.03)
            self.record('received_actor_kill',bool(bot.kills-before) and bot.kills-before<=set(attacked),
                map_id=bot.map_id,template_id=group.template_id,killed_uids=sorted(bot.kills-before),
                swings=bot.swings-start_swings,received_targets=attacked)
        finally:
            self.record('boss_retry_observation',True,hp=bot.hp,max_hp=bot.max_hp,
                swings=bot.swings-start_swings,observations=observations[-12:],
                skill_events=[dict(e) for e in getattr(self.broker,'_world_monster_skills_events',())][-12:],
                scope='read-only runtime observations; proactive95pct real finite potion requests; no product policy change')


def main(argv=None):
    previous_data,previous_scenario = driver.DATA,driver.ExpansionScenario
    try:
        driver.DATA = Path(__file__).parent/'data/m6/map_expansion6.json'
        driver.ExpansionScenario = Expansion6Scenario
        for path in (Path(__file__),driver.DATA):
            driver.matrix.SOURCE_SHA256[str(path)] = dict(file=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),basis='MapExp6 startup source provenance')
        parser = driver.parser()
        parser.add_argument('--strong-fixture',action='store_true',
            help='combat cases: pre-login +9/+6 gear,200potions; map65 Lv99/+20 gear/480entfruit; finite10haste/brave')
        parser.add_argument('--travel-only',action='store_true',help='skip combat explicitly; travel/return/save only')
        parser.add_argument('--boss-retry-fixture',action='store_true',help='combat retry only: Lv99/+20 finite fixture with catalogued water/MR gear and95pct healing')
        args = parser.parse_args(argv)
        result = asyncio.run(driver.run(args))
        result['scope'] = ('LOCAL ordered MapExp6 packet cases on fresh entrance-neighbour saved fixtures. '
            'Real S32 stairs, walking, representative received-target combat, finite162 return/save and normal close. '
            'Separate saved fixture per case; map65 strong Lv99/+20; other combat Lv60/+9/+6 unless boss-retry Lv99/+20. '
            'Natural item acquisition/enchant, ordinary gear survival, all-species combat, underwater/native input/render UNKNOWN.')
        result['strong_fixture'] = args.strong_fixture
        result['travel_only'] = args.travel_only
        result['boss_retry_fixture'] = args.boss_retry_fixture
        (Path(result['output_directory'])/'summary.json').write_text(
            json.dumps(driver.matrix.safe(result),ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('output_directory','counts')},ensure_ascii=False))
        return 0 if set(result['counts'])=={'PASS'} else 1
    finally:
        driver.DATA,driver.ExpansionScenario = previous_data,previous_scenario


if __name__=='__main__':
    raise SystemExit(main())
