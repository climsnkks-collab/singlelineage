"""MapExp5 ordered stair/paid-entry, representative kill, return/save and close."""
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path

from tools.local_original_session import hunt_bot_map_expansion4 as driver
from tools.local_original_session import hunt_bot as hb


class Expansion5Scenario(driver.ExpansionScenario):
    def initialize_hunt_fixture(self):
        super().initialize_hunt_fixture()
        if not self.args.strong_fixture or self.case['map_id'] != 303:
            return
        from tools.local_original_session import inventory, equipment_store
        from tools.local_original_session import world_enchant_inventory as enchant
        supplied = [dict(item.raw_fields) for item in inventory.validate_kit_frame(self.broker._inventory_kit_frame(1))]
        wanted = {3,117,89,98,104,109,128,129,14,17,296,7,162}
        rows = [row for row in supplied if row[2] in wanted]
        data = self.broker._world.data
        for row in rows:
            item = data.items[row[2]]
            if item.kind in ('weapon','armor'):
                row[18] = enchant.enchanted_name(item,9 if item.kind=='weapon' else 6)
            elif row[2]==14:
                row[4]=200
            elif row[2] in (17,296):
                row[4]=10
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1,frame)
        by_template = {row[2]:row[1] for row in rows}
        # Existing open() equips the other four pieces through real0960.
        self.equipment.initialize_kit(1,frame,initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=by_template[3],slots=tuple((data.items[t].slot_key,by_template[t]) for t in (117,98,109)))
        self.fixture_notes.append(dict(pre_login_strong_map303=True,weapon='+9 long sword3',
            armor='+6 shield117/helmet89/armor98/shirt104/cloak109/boots128/gloves129',
            potion14=200,haste17=10,brave296=10,
            scope='separate fresh pre-login kit; no live grant, NPC/HP/RNG/combat or original/user save edit'))

    async def open(self,**options):
        await super().open(**options)
        if self.args.strong_fixture and self.case['map_id']==303:
            await self.use(17)
            await self.use(296)
            state = self.broker._world.combat.pcs[self.bot.self_uid]
            self.record('strong_map303_observed_gear',state.profile.ac==-53,
                ac=state.profile.ac,weapon_enchant=state.profile.weapon.enchant,
                scope='explicit strong starting fixture only; ordinary-map303 failure retained')

    def saved_counts(self):
        from tools.local_original_session import inventory
        return Counter({item.template_bits:dict(item.raw_fields)[4] for item in
            inventory.validate_kit_frame(self.store.restore(self.bot.self_uid))})

    async def cross(self, entry, label):
        trip = self.case.get('teleport')
        if trip is None:
            return await super().cross(entry,label)
        town = self.broker._world.town
        targets = [(town.entities.resolve(ref),npc) for ref,npc,_ in town._owned.values()
                   if npc.npc_id==trip['npc_id']]
        entity,npc = next((e,n) for e,n in targets if e is not None)
        await self.navigate((entity.x,entity.y),radius=2)
        self.record('received_teleporter',entity.uid in self.bot.live_appearances,
            uid=entity.uid,placement=npc.key,scope='LOCAL role appearance; original NPC identity UNKNOWN')
        before = self.saved_counts()
        batch = await self.bot.peer.request(0x4e43,hb.uint(1,entity.uid),
            check=lambda frames:hb.find(frames,0x4e44),label='MAP5_CLICK_TELEPORTER')
        menu = hb.find(batch,0x4e44).values
        self.record('current_original_menu',hb.scalar(menu,2)==trip['stem'].encode()
            and hb.scalar(menu,1)&0xffffffff==entity.uid,stem=trip['stem'])
        await self.barrier(0x4ed4,hb.uint(1,hb.scalar(menu,1))
            +hb.pb.encode_bytes(2,trip['action'].encode())+hb.uint(4,0)+hb.uint(5,0),
            label='MAP5_PAID_TELEPORT')
        from tools.local_original_session import movement
        saved = self.broker.realm.positions.restore(movement.Position(self.bot.self_uid,self.bot.character,0,0,0))
        destination = tuple(trip['destination'][:3])
        self.record('paid_entry_position_and_fee_saved',
            (self.bot.map_id,*self.bot.position)==destination
            and (saved.map_id,saved.word0,saved.word1)==destination
            and self.saved_counts()[7]==before[7]-trip['price'],
            expected=destination,wire=(self.bot.map_id,*self.bot.position),
            saved=(saved.map_id,saved.word0,saved.word1),price=trip['price'],
            adena_before=before[7],adena_after=self.saved_counts()[7])


def main(argv=None):
    previous_data,previous_scenario = driver.DATA,driver.ExpansionScenario
    try:
        driver.DATA = Path(__file__).parent/'data/m6/map_expansion5.json'
        driver.ExpansionScenario = Expansion5Scenario
        for path in (Path(__file__),Path(__file__).with_name('world_feature_map_expansion5.py'),driver.DATA):
            driver.matrix.SOURCE_SHA256[str(path)] = dict(file=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),basis='MapExp5 startup source provenance')
        parser = driver.parser()
        parser.add_argument('--strong-fixture',action='store_true',
            help='map303 only: explicit pre-login +9 weapon/+6 armor/finite200potions and10haste/brave')
        args = parser.parse_args(argv)
        result = asyncio.run(driver.run(args))
        result['scope'] = (f'LOCAL ordered MapExp5 packet cases on fresh pre-login Lv{args.fixture_level} '
            'entrance-neighbour fixtures. Actual stairs or current-menu1000A teleport, walking, '
            'representative received-target combat, finite162 return and persisted location, normal close. '
            'Each case is a separate saved fixture, not one continuous trip. Underwater environment, '
            'native client/input/rendering and all-species combat remain UNKNOWN.')
        result['strong_map303_fixture'] = args.strong_fixture
        (Path(result['output_directory'])/'summary.json').write_text(
            json.dumps(driver.matrix.safe(result),ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('output_directory','counts')},ensure_ascii=False))
        return 0 if set(result['counts'])=={'PASS'} else 1
    finally:
        driver.DATA,driver.ExpansionScenario = previous_data,previous_scenario


if __name__=='__main__':
    raise SystemExit(main())
