"""Natural Elder attacks through ordinary sockets and owned equipment toggles.

Reuses Matrix's fresh saved fixture/native RAM peer, FIRST, inventory delivery,
gear0960 and normal Quit/close. No original process or user save is opened.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import time

from tools.local_original_session import hunt_bot as hb, hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import hunt_bot_spawn_audit as audit
from tools.local_original_session.hunt_bot_monster_skills import SkillBot


def spell_wire(event, rows, marker, self_uid):
    """Correlate one event with its new NPC swing and following HP delivery.

    A repeated historical HP value is insufficient. The HP must belong to the
    same received attack group, before another NPC swing, and (when supplied)
    its sourced effect must also be received in that group.
    """
    fresh = [row for row in rows if row['ordinal'] > marker and row['at'] >= event['at']]
    for index, swing in enumerate(fresh):
        if (swing['opcode'] != '0x4E31' or swing['fields'].get('2') != event['npc_uid']
                or swing['fields'].get('3') != self_uid):
            continue
        group = []
        for row in fresh[index + 1:]:
            if row['opcode'] == '0x4E31':
                break
            group.append(row)
        hp = next((row for row in group if row['opcode'] == '0x4E38'
                   and row['fields'].get('1') == self_uid
                   and row['fields'].get('10') == event['hp_after']), None)
        effect = next((row for row in group if row['opcode'] == '0x4ED8'
                       and row['fields'].get('1') == self_uid
                       and row['fields'].get('2') == event.get('effect_id')), None)
        if hp is not None and (not event.get('effect_id') or effect is not None):
            return dict(marker=marker, swing=swing, hp=hp, effect=effect)
    return None


class ElementScene(audit.Audit):
    def initialize_hunt_fixture(self):
        super().initialize_hunt_fixture()
        from tools.local_original_session import inventory, equipment_store
        data = self.broker._world.data
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(
            self.broker._inventory_kit_frame(1))]
        next_uid = max(row[1] for row in rows) + 1
        for template in (501, 3937):
            row = dict(rows[0])
            row.update({1: next_uid, 2: template, 4: 1, 7: data.items[template].icon, 18: b''})
            next_uid += 1
            rows.append(row)
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1, frame)
        by_template = {row[2]: row for row in rows}
        equipped = [entry.template_id for entry in data.starter.entries(1, 'test_knight') if entry.equipped]
        self.equipment.initialize_kit(1, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=next((by_template[t][1] for t in equipped if data.items[t].kind == 'weapon'), 0),
            slots=tuple((data.items[t].slot_key, by_template[t][1])
                        for t in equipped if data.items[t].kind == 'armor'))
        self.fixture_notes.append(dict(pre_login_test_supplies=[501, 3937],
            scope='fresh Lv30 saved fixture; wind ring/belt owned supply only; no acquisition claim'))

    async def beat(self):
        if self.bot.dead:
            raise hb.BotFailure('ELEMENT_OWNER_DIED')
        await self.owner_potion()
        await self.bot.alive()
        await asyncio.sleep(.05)

    async def reach_elder(self):
        bot = self.bot
        bot.safe_hunt_cell = lambda point: True
        until = time.monotonic() + self.args.observe_seconds
        target = None
        while time.monotonic() < until:
            candidates = [(uid, row) for uid, row in bot.actors.items()
                          if row['alive'] and self.broker._world.spawner.slot_for(uid) is not None
                          and self.broker._world.spawner.slot_for(uid)[0].monster.template_id == 7]
            if candidates:
                target, actor = min(candidates, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, actor['position']) <= 1:
                    break
                await bot.step(actor['position'], radius=1)
            await self.beat()
        self.record('received_and_approached_natural_elder', target is not None and
            hb.distance(bot.position, bot.actors[target]['position']) <= 1,
            npc_uid=target, position=bot.position)
        marker, started = bot.peer.ordinal, time.monotonic()
        # A request can be refused by cadence; receive the player's swing
        # before claiming that this passive Elder was provoked.
        while time.monotonic() - started < 20:
            await bot.attack(target)
            own = [r for r in bot.skill_wire if r['ordinal'] > marker
                   and r['opcode'] == '0x4E31' and r['fields']['2'] == bot.self_uid
                   and r['fields']['3'] == target]
            if own:
                self.record('received_attack_before_spell_observation', True,
                            target=target, ordinal=own[-1]['ordinal'])
                return target, marker, started
            await self.beat()
        self.record('received_attack_before_spell_observation', False, target=target)

    def spell_events(self, target, resistance, started):
        events = []
        defense = int(.32 * resistance) / 32
        for source, rows in (
                ('magic', getattr(self.broker, '_world_magic_events', ())),
                ('monster_skills', getattr(self.broker, '_world_monster_skills_events', ()))):
            for row in rows:
                if (row.get('npc_uid') != target or row.get('target') != self.bot.self_uid
                        or row.get('at', 0) < started or not row.get('trace')
                        or row['trace']['elemental_defense'] != defense):
                    continue
                event = dict(row, producer=source, resist_wind=resistance)
                if source == 'magic':
                    if row.get('outcome') != 'npc_magic':
                        continue
                else:
                    if row.get('kind') != 'magic' or row.get('outcome') != 'applied':
                        continue
                    definition = next(r for rows in self.broker._world_monster_skills_attacks.values()
                                      for r in rows if r['id'] == row['id'])
                    event.update(parameters=definition['parameters'],
                        intelligence=definition['intelligence'],
                        leverage=definition.get('leverage', 10))
                events.append(event)
        return events

    async def sample(self, target, resistance, marker=None, started=None):
        marker = self.bot.peer.ordinal if marker is None else marker
        started = time.monotonic() if started is None else started
        until = time.monotonic() + self.args.observe_seconds
        event = received = None
        while time.monotonic() < until:
            for candidate in self.spell_events(target, resistance, started):
                received = spell_wire(candidate, self.bot.skill_wire, marker, self.bot.self_uid)
                if received is not None:
                    event = candidate
                    break
            if event is not None:
                break
            await self.beat()
        self.record('natural_spell_observed_resist_' + str(resistance), event is not None,
                    target=target, resistance=resistance, marker=marker,
                    candidates=self.spell_events(target, resistance, started), received=received)
        trace = event['trace']
        coefficient = max(1 - trace['elemental_defense'] +
                          max(event['intelligence'] - 12, 1) * 3 / 32, 0)
        expected = int(int(trace['base_damage'] * coefficient) * event['leverage'] / 10)
        bare = int(int(trace['base_damage'] * (1 + max(event['intelligence']-12, 1)*3/32)) * event['leverage']/10)
        if trace['mr_roll'] <= trace['mr']:
            expected //= 2
            bare //= 2
        expected = max(0, expected)
        self.record('actual_dice_mr_resistance_hp_consumer_' + str(resistance),
            ('rolled_damage' not in event or event['rolled_damage'] == expected)
            and event['amount'] == min(event['hp_before'], expected)
            and event['hp_after'] == event['hp_before'] - event['amount']
            and received is not None
            and (expected < bare if resistance else expected == bare),
            event=event, independently_calculated_damage=expected,
            same_dice_mr_without_resistance=bare, received=received)
        self.samples.append(dict(event=event, received=received))

    async def dungeon_items(self):
        self.samples = []
        target, marker, started = await self.reach_elder()
        await self.sample(target, 0, marker, started)
        for template in (501, 3937):
            uid, _ = self.item(template)
            await self.gear_uid(uid)
        self.record('equipped_profile_wind20',
            self.broker._world.combat.pcs[self.bot.self_uid].profile.resist_wind == 20)
        await self.sample(target, 20)
        await self.close()
        await self.open(seed=False)
        self.record('reconnect_restores_equipment_wind20',
            self.broker._world.combat.pcs[self.bot.self_uid].profile.resist_wind == 20)
        for template in (501, 3937):
            uid, _ = self.item(template)
            await self.gear_uid(uid)
        self.record('unequipped_profile_wind0',
            self.broker._world.combat.pcs[self.bot.self_uid].profile.resist_wind == 0)
        target, marker, started = await self.reach_elder()
        await self.sample(target, 0, marker, started)


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    directory = Path(tempfile.mkdtemp(prefix='element-natural-', dir=root))
    data = audit.all_data()
    group = next(g for g in data.spawns if g.group_id == 'population_m1_0_7')
    scene = ElementScene(args, directory, [group], {})
    from tools.local_original_session.world_terrain import WorldTerrain
    scene.map_start = audit.start_cell(WorldTerrain.load(map_ids=(0,)), 0, group.rect)
    original_bot = hs.ScenarioBot
    hs.ScenarioBot = SkillBot
    print(json.dumps(dict(directory=str(directory), scope='DEVELOPMENT saved-fixture socket test')), flush=True)
    try:
        result = await scene.run_matrix()
    finally:
        hs.ScenarioBot = original_bot
    result['samples'] = getattr(scene, 'samples', [])
    result['source_sha256'].update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__), Path(__file__).with_name('world_combat.py'),
        Path(__file__).with_name('world_monster_skills.py'),
        Path(__file__).with_name('world_feature_monster_skills.py'),
        Path(__file__).with_name('world_feature_magic.py'),
        Path(__file__).with_name('data') / 'monster_skills.json',
        Path(__file__).with_name('world_magic_tests.py'),
        Path(__file__).with_name('data') / 'm1/npc_magic_attacks.json')})
    (directory / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--timeout', type=hb.positive, default=8)
    cli.add_argument('--observe-seconds', type=hb.positive, default=80)
    cli.set_defaults(scenario='dungeon_items', minutes=1, potion_threshold=.9, fixture_level=30,
                     companion_revive_exp=False, navigation_timeout=60, strong_fixture=False,
                     boss_fixture=False, fixture_heal_template=130, fixture_heal_count=150)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1, SL_EXPERIMENT_SHOP=1,
            SL_COMPANION=0, SL_COMPANION_PET_UI=0, SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
        result = asyncio.run(run(cli.parse_args(argv)))
    print(json.dumps({k: result[k] for k in ('status', 'directory', 'failure', 'cleanup_complete')}, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' and result['cleanup_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
