"""Staff342 socket trial on a preserved, declared pre-login mage fixture.

FIRST/login/selection/world, received owned UID, actual CS4E30, status delivery
and quit/reconnect use the existing bot and broker paths. No original client,
user save, post-entry HP/MP assignment, NPC definition or spawn is changed.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
from pathlib import Path
import random
import tempfile
import time
import uuid
from unittest.mock import patch

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session.hunt_bot_magic import MagicBot, MagicScenario
from tools.local_original_session import test_ports


class WeaponScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'weapon_effects', directory)
        self.fixture = None
        self.attacks = []
        self.saved_vitals = None

    @property
    def world(self):
        return self.broker._world

    def record(self, name, ok, **evidence):
        super().record(name, ok, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    def initialize_fixture(self):
        from tools.local_native_login_local_ack_hook import ack_enter_world as ack
        from tools.local_original_session import inventory, equipment_store, movement
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.hunt_bot_loopback import START
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        data = load_m1()
        growth = json.loads((Path(__file__).parent / 'data/companion/mage_growth.json').read_text(encoding='utf-8'))
        attributes = growth['local_build']['creation_original_stats']
        template = getattr(self.args, 'weapon_template', 342)
        attributes = dict(attributes)
        if template == 1094:
            # Source-backed diagnosis: STR8 damage bonus=-2 and this weapon's
            # small die1..2 can never produce a positive physical hit. Preserve
            # the creation-point total, moving five INT points to STR before
            # creation. No live stat/HP assignment or hit RNG is overridden.
            attributes['STR'] += 5
            attributes['INT'] -= 5
        stats = tuple(attributes[k] for k in ('STR', 'DEX', 'CON', 'WIS', 'CHA', 'INT'))
        character_class = next(iter(sorted(data.items[template].classes)))
        uid, _, _ = self.broker.realm.store.create(ack.realm.Creation('SoloMana', character_class, 0, stats))
        level, exp = 30, data.pc_exp[29]
        grown = on_kill(RewardPcState(0, PcProfile(1, character_class, 0, stats[0], stats[1],
            con=stats[2], wis=stats[3]), 12, 8),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x342), data=data)
        self.broker._world_progress.commit(uid, Progress(exp, level, grown.max_hp, grown.max_mp))
        self.broker._world_progress.save_vitals(uid, (grown.max_hp, 0))
        fallback = movement.authority.unpack_grid(self.broker.realm._actor_fields[1])
        current = self.broker.realm.positions.restore(movement.Position(uid, 'SoloMana', 0, *fallback))
        self.broker.realm.positions.commit(current, movement.Position(uid, 'SoloMana', 0, *START))
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(self.broker._inventory_kit_frame(character_class))]
        for index, row in enumerate(rows):
            row[1] = 0x20000000 + uid * inventory.KIT_MAX_ITEMS + index
        staff = dict(rows[0])
        staff.update({1: 0x20000000 + uid * inventory.KIT_MAX_ITEMS + len(rows),
                      2: template, 4: 1, 7: data.items[template].icon,
                      18: data.items[template].name_ko.encode('utf-8')})
        rows.append(staff)
        if template in (568, 2072):
            # Declared prelogin owned ammunition; real requests consume it.
            ammo = next((row for row in rows if row[2] == 29), None)
            if ammo is None:
                ammo = dict(rows[0])
                ammo.update({1: staff[1]+1, 2: 29, 7: data.items[29].icon,
                             18: data.items[29].name_ko.encode('utf-8')})
                rows.append(ammo)
            ammo[4] = 1 if template == 568 else 200
        frame = inventory.build_kit_frame(rows)
        self.store.grant(uid, frame)
        # The elf starter (class 2, used by bow 568) has no armour row; equip
        # the starter armour only when the selected class's kit owns one.
        armor = next((row for row in rows if data.items.get(row[2]) is not None
                      and data.items[row[2]].slot == 'armor'), None)
        self.equipment.initialize_kit(uid, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                                     weapon_uid=staff[1], slots=() if armor is None else ((2, armor[1]),))
        self.fixture = dict(character_uid=uid, character='SoloMana', level=level, exp=exp,
            initial_hp=grown.max_hp, initial_mp=0, max_hp=grown.max_hp, max_mp=grown.max_mp,
            staff_template=template, staff_uid=staff[1], character_class=character_class, position=START,
            creation_attributes=attributes, creation_attribute_total=sum(stats),
            scope='independent LOCAL prelogin Lv30/fullHP/MP0 fixture; ordinary mage starter '
                  'plus declared owned weapon saved-equipped; no native equip intent claim')

    async def open(self, *, seed, character=None):
        from tools.local_original_session import inventory
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        from tools.local_original_session.world_state_services import InventoryTransactions
        expected = str(uuid.uuid4())
        # reserve() and broker listeners share this scoped map: base and base+1
        # instead of the usual +2030 pair, so any SL_TEST_PORT_BASE stays valid.
        base = test_ports.port(12000)+self.args.port_offset
        physical = {12000: base, 14030: base+1}
        if not all(1 <= port <= 65535 for port in physical.values()):
            raise ValueError('WEAPON_TRIAL_PORT_OUTSIDE_TCP_RANGE')
        with patch.object(test_ports, 'port', side_effect=lambda logical: physical[logical]), \
                patch.object(test_ports, 'listener_ports', return_value=physical):
            self.broker, self.store, self.equipment = await hs.build_epoch(self.directory, expected, seed=seed)
        # Same saved-equipment-only adapter as MagicScenario, with actual stores.
        effect = object.__new__(ItemEquipmentEffect)
        effect.store, effect._defs = self.equipment, self.world.data.items
        effect._kit_policy, effect._collection_policy = inventory.KIT_POLICY, None
        effect._selection, effect._last = None, dict(status='FIXTURE_SAVED_EQUIPMENT_ONLY')
        self.broker._item_equipment_effect = effect
        self.broker._world_inventory_transactions = InventoryTransactions(self.store)
        self.broker._world_pc_profile = type(self.broker)._world_pc_profile.__get__(self.broker)
        if seed:
            self.initialize_fixture()
        original_attack = self.world.pc_attack
        def observe_attack(uid, target):
            # This synchronous owner runs inside the existing runtime lock:
            # a regeneration tick cannot interleave between these observations.
            before = self.world.combat.mp_of(uid)
            entity = self.world.entities.get(target)
            frames = original_attack(uid, target)
            after = self.world.combat.mp_of(uid)
            state = self.world.combat.pcs.get(uid)
            self.attacks.append(dict(pc_uid=uid, target_uid=target,
                target_template=None if entity is None else entity.template_id,
                mp_before=before, mp_after=after, at=self.world.runtime.clock(),
                attack_profile=None if state is None else dataclasses.asdict(state.profile),
                hit_raw=[] if frames is None else [hb.scalar(hb.fields(f[4:-2]), 4)
                    for f in frames if int.from_bytes(f[2:4], 'little') == 0x4e31
                    and hb.scalar(hb.fields(f[4:-2]), 2) == uid],
                frame_opcodes=[] if frames is None else [int.from_bytes(f[2:4], 'little') for f in frames],
                scope='read-only same synchronous pc_attack boundary; no interleaved regen tick'))
            return frames
        self.world.pc_attack = observe_attack
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected, '--minutes', str(self.args.minutes),
            '--timeout', str(self.args.timeout), '--potion-threshold', str(self.args.potion_threshold)])
        options.port, options.character = test_ports.port(options.port)+self.args.port_offset, 'SoloMana'
        self.bot = MagicBot(options)
        self.bots.append(self.bot)
        self.bot.data, self.bot.terrain, self.bot.started = self.world.data, self.world.terrain, time.monotonic()
        self.bot.heading = lambda goal, radius: MagicScenario.travel_heading(self, goal, radius)
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'FIXTURE_KIT_DELIVERY')

    async def weapon_effects(self):
        if self.fixture['staff_template'] == 144:
            return await self.haste_weapon()
        if self.fixture['staff_template'] == 568:
            return await self.sayha_weapon()
        if self.fixture['staff_template'] != 342:
            return await self.numeric_weapon_proc()
        bot = self.bot
        uid, staff_uid = bot.self_uid, self.fixture['staff_uid']
        saved = self.snapshot()
        self.record('login_world_owned_saved_staff342', bot.inventory[staff_uid][2] == 342
            and saved['equipment']['weapon_uid'] == staff_uid and bot.mp < bot.max_mp,
            fixture=self.fixture, wire_mp=bot.mp, wire_max_mp=bot.max_mp,
            saved_equipment=saved['equipment'], combat_weapon=saved['combat_equipment']['weapon'])
        until = time.monotonic() + self.args.navigation_timeout
        absorbed = None
        while time.monotonic() < until and absorbed is None:
            if bot.dead:
                raise hs.Unconfirmed('PLAYER_DIED_BEFORE_MANA_ABSORPTION')
            living = [(key, row) for key, row in bot.actors.items() if bot.hunt_target(row)
                      and bot.data.monsters[row['template']].mp > 0]
            if living:
                target, actor = min(living, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, actor['position']) > 1:
                    await bot.step(actor['position'], radius=1)
                else:
                    marker = bot.peer.ordinal
                    before_count = len(self.attacks)
                    await bot.attack(target)
                    for attack in self.attacks[before_count:]:
                        if (attack['mp_before'] is not None and attack['mp_after'] > attack['mp_before']):
                            absorbed = dict(attack, request_marker=marker)
                            break
            else:
                group = next(s for s in bot.data.spawns if s.group_id == 'm1_orc')
                await bot.step(((group.rect.x1 + group.rect.x2)//2,
                               (group.rect.y1 + group.rect.y2)//2), radius=2)
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.05)
        if absorbed is None:
            raise hs.Unconfirmed('NO_POSITIVE_MP_DELTA_INSIDE_ACTUAL_PC_ATTACK')
        statuses = [f for f in bot.peer.frames if f.ordinal > absorbed['request_marker']
                    and f.opcode == 0x4e38 and hb.scalar(f.values, 1) == uid
                    and hb.scalar(f.values, 12) == absorbed['mp_after']]
        swings = [f for f in bot.peer.frames if f.ordinal > absorbed['request_marker']
                  and f.opcode == 0x4e31 and hb.scalar(f.values, 2) == uid
                  and hb.scalar(f.values, 3) == absorbed['target_uid']]
        effects = self.broker.report().get('world', {}).get('weapon_effects', {})
        event = next((row for row in reversed(effects.get('events', ()))
                      if row.get('pc_uid') == uid and row.get('npc_uid') == absorbed['target_uid']
                      and row.get('drained', 0) > 0), None)
        self.record('real_CS4E30_positive_mp_absorption_separate_from_regen', bool(statuses and swings),
            observation=absorbed, status_ordinals=[f.ordinal for f in statuses],
            swing_ordinals=[f.ordinal for f in swings],
            target_definition_mp=bot.data.monsters[absorbed['target_template']].mp)
        self.record('product_effect_consumes_real_npc_mp', event is not None
            and event['npc_mp_before'] - event['npc_mp_after'] == event['drained']
            and event['mp_after'] - event['mp_before'] == absorbed['mp_after'] - absorbed['mp_before'],
            event=event, report=effects)
        before_close_mp = self.world.combat.mp_of(uid)
        if not await self.close():
            raise hs.Unconfirmed('ABSORPTION_QUIT_CLOSE_FAILED')
        vitals = json.loads((self.directory/'vitals.json').read_text(encoding='utf-8'))
        self.saved_vitals = next(row for row in vitals['rows'] if row['uid'] == uid)
        self.record('normal_quit_saved_absorbed_mp', self.saved_vitals['mp'] >= absorbed['mp_after'],
                    before_quit_mp=before_close_mp, saved=self.saved_vitals,
                    scope='quit may include ordinary regeneration after the observed absorption')
        await self.open(seed=False)
        initial_status = next(f for f in self.bot.peer.frames if f.opcode == 0x4e38
                              and hb.scalar(f.values, 1) == uid)
        restored = hb.scalar(initial_status.values, 12)
        self.record('new_FIRST_login_world_restores_saved_mp_and_owned_staff',
            restored == self.saved_vitals['mp']
            and self.snapshot()['equipment']['weapon_uid'] == staff_uid,
            saved_mp=self.saved_vitals['mp'], first_world_status_mp=restored, staff_uid=staff_uid)

    async def haste_weapon(self):
        uid = self.bot.self_uid
        rate = self.world.data.items[17].buff.rate
        await self.bot.alive()
        speed = [f for f in self.bot.peer.frames if f.opcode == 0x4e5b
                 and hb.scalar(f.values, 1) == uid]
        if not speed:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x4e5b), 'WEAPON_HASTE_SPEED')
        self.record('saved_144_haste_consumes_core_category_with_magic_enabled',
            abs(self.world.combat.speed_factor(uid, self.world.runtime.clock())-rate) < 1e-9,
            rate=rate, speed_factor=self.world.combat.speed_factor(uid, self.world.runtime.clock()),
            received_speed_ordinals=[f.ordinal for f in self.bot.peer.frames if f.opcode == 0x4e5b],
            scope='LOCAL potion haste category; current magic slow/berserk remain separate multipliers')
        if not await self.close():
            raise hs.Unconfirmed('HASTE_QUIT_CLOSE_FAILED')
        await self.open(seed=False)
        self.record('new_FIRST_restores_144_saved_equipment_haste',
            self.snapshot()['equipment']['weapon_uid'] == self.fixture['staff_uid']
            and abs(self.world.combat.speed_factor(self.bot.self_uid, self.world.runtime.clock())-rate) < 1e-9)

    async def sayha_weapon(self):
        deadline = time.monotonic()+self.args.navigation_timeout
        seen = set()
        marker = self.bot.peer.ordinal
        while time.monotonic() < deadline and seen != {66, 2349}:
            if self.bot.dead:
                raise hs.Unconfirmed('PLAYER_DIED_BEFORE_SAYHA_FALLBACK')
            if self.bot.hp <= self.bot.max_hp*self.args.potion_threshold:
                await self.bot.potion()
            living = [(key, row) for key, row in self.bot.actors.items() if self.bot.hunt_target(row)
                      and self.bot.data.monsters[row['template']].level <= 10]
            if living:
                target, actor = min(living, key=lambda pair: hb.distance(self.bot.position, pair[1]['position']))
                if hb.distance(self.bot.position, actor['position']) > 1:
                    await self.bot.step(actor['position'], radius=1)
                else:
                    await self.bot.attack(target)
            else:
                group = next(s for s in self.bot.data.spawns if s.group_id == 'm1_orc')
                await self.bot.step(((group.rect.x1+group.rect.x2)//2,
                                     (group.rect.y1+group.rect.y2)//2), radius=2)
            seen = {hb.scalar(f.values, 7) for f in self.bot.peer.frames if f.ordinal > marker
                    and f.opcode == 0x4e31 and hb.scalar(f.values, 2) == self.bot.self_uid}
            if time.monotonic()-self.bot.last_alive >= .5:
                await self.bot.alive()
            await asyncio.sleep(.05)
        ammo = [row for row in self.bot.inventory.values() if row[2] == 29]
        self.record('CS4E30_real_arrow_once_then_Sayha_virtual_projectile', seen == {66, 2349}
            and all(row.get(4, 0) == 0 for row in ammo), projectiles=sorted(seen),
            remaining_received_ammo=ammo, scope='LOCAL ArrowType f7 2349; native rendering UNKNOWN')
        await self.restore_bow_ammunition()

    async def restore_bow_ammunition(self):
        remaining = sum(row.get(4, 0) for row in self.bot.inventory.values() if row[2] == 29)
        if not await self.close():
            raise hs.Unconfirmed('BOW_QUIT_CLOSE_FAILED')
        await self.open(seed=False)
        restored = sum(row.get(4, 0) for row in self.bot.inventory.values() if row[2] == 29)
        self.record('new_FIRST_restores_consumed_arrow_count_and_saved_bow', restored == remaining
            and self.snapshot()['equipment']['weapon_uid'] == self.fixture['staff_uid'],
            before_quit_received_arrows=remaining, first_world_received_arrows=restored,
            template=self.fixture['staff_template'])

    async def numeric_weapon_proc(self):
        from tools.local_original_session.world_feature_weapon_effects import PROCS
        template = self.fixture['staff_template']
        self.record('login_world_received_owned_proc_weapon',
            self.bot.inventory[self.fixture['staff_uid']][2] == template
            and self.snapshot()['equipment']['weapon_uid'] == self.fixture['staff_uid'], fixture=self.fixture)
        deadline = time.monotonic()+self.args.navigation_timeout
        event, marker = None, self.bot.peer.ordinal
        while time.monotonic() < deadline and event is None:
            if self.bot.dead:
                raise hs.Unconfirmed('PLAYER_DIED_BEFORE_WEAPON_PROC')
            if self.bot.hp <= self.bot.max_hp*self.args.potion_threshold:
                await self.bot.potion()
            living = [(key, row) for key, row in self.bot.actors.items() if self.bot.hunt_target(row)
                      and self.bot.data.monsters[row['template']].level <= 10]
            if living:
                target, actor = min(living, key=lambda pair: hb.distance(self.bot.position, pair[1]['position']))
                if hb.distance(self.bot.position, actor['position']) > 1:
                    await self.bot.step(actor['position'], radius=1)
                else:
                    await self.bot.attack(target)
            else:
                group = next(s for s in self.bot.data.spawns if s.group_id == 'm1_orc')
                await self.bot.step(((group.rect.x1+group.rect.x2)//2,
                                     (group.rect.y1+group.rect.y2)//2), radius=2)
            report = self.broker.report()['world']['weapon_effects']
            event = next((row for row in reversed(report['events'])
                          if row['weapon_template'] == template
                          and (row.get('damage', 0) > 0 or template == 2072)), None)
            if time.monotonic()-self.bot.last_alive >= .5:
                await self.bot.alive()
            await asyncio.sleep(.05)
        if event is None:
            raise hs.Unconfirmed('NO_MOONBOW_PROC_ON_ACTUAL_CS4E30' if template == 2072
                                 else 'NO_POSITIVE_DAMAGE_PROC_ON_ACTUAL_CS4E30')
        await self.bot.alive()
        effects = [frame for frame in self.bot.peer.frames if frame.ordinal > marker and (
            frame.opcode == 0x4ed8 and hb.scalar(frame.values, 1) == event['npc_uid']
            and hb.scalar(frame.values, 2) == PROCS[template][5] if template != 2072 else
            frame.opcode == 0x4e31 and hb.scalar(frame.values, 3) == event['npc_uid']
            and hb.scalar(frame.values, 7) == 6288)]
        self.record('real_CS4E30_moonbow_zero_damage_and_Arrow6288' if template == 2072
                    else 'real_CS4E30_source_proc_damage_and_SC4ED8', bool(effects)
                    and (template != 2072 or event['damage'] == 0),
                    event=event, effect_ordinals=[frame.ordinal for frame in effects],
                    scope='LOCAL backend numeric proc; effect129 target binding is not native location equivalence')
        report = self.broker.report()['world']['weapon_effects']
        self.record('unknown_effects_and_missing_contributors_explicit',
                    set(map(int, report['unknown'])) == {789, 3018}
                    and 'weapon_proc_defense' in report['missing_contributors'],
                    unknown=report['unknown'], missing=report['missing_contributors'])
        if template == 2072:
            await self.restore_bow_ammunition()


def parser():
    result = hs.parser()
    result.description = __doc__
    action = next(a for a in result._actions if a.dest == 'scenario')
    action.choices, action.default = ('weapon_effects',), 'weapon_effects'
    result.add_argument('--proc-templates', default='342,144,568,2072,1094,1096,3019,3020',
                        help='sequential isolated prelogin fixtures; UNKNOWN weapons are not falsely activated')
    result.add_argument('--port-offset', type=int, default=0,
                        help='local trial listener offset within the declared port base')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-weapon-effects-', dir=root))
    results = []
    for template in map(int, args.proc_templates.split(',')):
        child = directory/str(template)
        child.mkdir()
        options = __import__('argparse').Namespace(**vars(args), weapon_template=template)
        scenario = WeaponScenario(options, child)
        item = await scenario.run()
        item.update(fixture=scenario.fixture, attacks=scenario.attacks, saved_vitals=scenario.saved_vitals)
        results.append(item)
        if item['status'] != 'SUCCESS':
            break
    result = dict(status='SUCCESS' if all(row['status'] == 'SUCCESS' for row in results) else 'FAIL',
                  results=results, physical_ports=[test_ports.port(12000)+args.port_offset,
                                                  test_ports.port(12000)+args.port_offset+1])
    result.update(
                  output_directory=str(directory), time_scale=os.environ.get('SL_TEST_TIME_SCALE'),
                  port_base=os.environ.get('SL_TEST_PORT_BASE'),
                  scope='LOCAL saved-equipment fixture; actual socket login/world/melee/status/save/reconnect; '
                        'native equip input/rendering and original-client milestone unverified',
                  changed_file='tools/local_original_session/hunt_bot_weapon_effects.py',
                  reused_from=['hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_magic.py'])
    (directory/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
