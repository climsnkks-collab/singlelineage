"""Ordered packet map4 paths on fresh saved-map Lv60 knight fixtures.

Reuse Matrix FIRST/login/select/enter/finite inventory/normal quit and the
existing S32 stair navigator. No native client or direct handler calls.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import time

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot_map_expansion2 as expansion2
from tools.local_original_session import world_maps
from tools.local_original_session import test_ports

DATA = Path(__file__).parent / 'data/m6/map_expansion4.json'


# Tower2-5 representatives are Lv53-55 (1025/891, AC-13/-25, 10..64 melee).
# The ordinary starter knight dealt 0 kills in 25-37 swings and drained 100
# potions or died (run hunt-map-expansion4-c7hc1nic). Reuse the MapExp5/6
# explicit pre-login strong kit for these four combat cases only.
STRONG_TOWER_MAPS = frozenset((102, 103, 104, 105))


class ExpansionScenario(expansion2.ExpansionScenario):
    def strong_tower_case(self):
        # Map ids 102-105 occur only in map_expansion4.json cases.
        return bool(self.case['combat']) and self.case['map_id'] in STRONG_TOWER_MAPS

    def initialize_hunt_fixture(self):
        super().initialize_hunt_fixture()
        if not self.strong_tower_case():
            return
        from tools.local_original_session import inventory, equipment_store
        from tools.local_original_session import world_enchant_inventory as enchant
        supplied = [dict(item.raw_fields) for item in inventory.validate_kit_frame(self.broker._inventory_kit_frame(1))]
        wanted = {3, 117, 89, 98, 104, 109, 128, 129, 14, 17, 296, 7, 162}
        rows = [row for row in supplied if row[2] in wanted]
        data = self.broker._world.data
        for row in rows:
            item = data.items[row[2]]
            if item.kind in ('weapon', 'armor'):
                row[18] = enchant.enchanted_name(item, 9 if item.kind == 'weapon' else 6)
            elif row[2] == 14:
                row[4] = 200
            elif row[2] in (17, 296):
                row[4] = 10
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1, frame)
        by_template = {row[2]: row[1] for row in rows}
        # Existing open() equips the other four pieces through real0960.
        self.equipment.initialize_kit(1, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=by_template[3], slots=tuple((data.items[t].slot_key, by_template[t]) for t in (117, 98, 109)))
        self.fixture_notes.append(dict(pre_login_strong_tower=self.case['map_id'], weapon='+9 long sword3',
            armor='+6 shield117/helmet89/armor98/shirt104/cloak109/boots128/gloves129',
            potion14=200, haste17=10, brave296=10,
            scope='separate fresh pre-login kit (MapExp5/6 strong fixture); no live grant, NPC/HP/RNG/combat or user save edit'))

    async def open(self, **options):
        await super().open(**options)
        if self.strong_tower_case():
            await self.use(17)
            await self.use(296)
            state = self.broker._world.combat.pcs[self.bot.self_uid]
            self.record('strong_tower_observed_gear', state.profile.weapon.enchant == 9,
                ac=state.profile.ac, weapon_enchant=state.profile.weapon.enchant, level=state.profile.level,
                scope='explicit strong starting fixture only; not natural acquisition/enchant or ordinary-gear survival')

    async def dungeon_items(self):
        bot = self.bot
        if self.case.get('region_id'):
            start, before = bot.position, bot.moves
            await self.navigate(self.entry[0][1:])
            self.record('walk_region_boundary', bot.position == self.entry[0][1:] and bot.moves > before,
                region_id=self.case['region_id'], before=start, after=bot.position,
                scope='actual walk on existing map4 across fixed-client region boundary; no warp')
        else:
            await self.cross(self.entry, 'walk_actual_stair_entry')
        self.stage = 'walk_inside'
        start = bot.position
        bounds = self.case.get('region_bounds')
        for h, (dx, dy) in enumerate(hb.DELTAS):
            point = start[0] + dx, start[1] + dy
            inside = bounds is None or (bounds['_left'] <= point[0] <= bounds['_right'] and bounds['_top'] <= point[1] <= bounds['_bottom'])
            if inside and (bot.map_id, *point) not in self.transitions and self.broker._world.terrain.can_step(bot.map_id, *start, h) is True:
                await self.navigate(point)
                break
        self.record('walk_inside', bot.position != start, before=start, after=bot.position)
        if self.case['combat']:
            self.stage = 'received_actor_combat'
            await self.case_combat()
        else:
            self.record('non_hunting_walk_only', True,
                scope='castle transit or town region walking only; no NPC/service or combat claim')
        self.stage = 'return162'
        departure = (bot.map_id, *bot.position)
        expected = self.dungeon_policy.return_for(bot.map_id) if bot.map_id != 4 else world_maps.load_gludin_policy().town_return
        await self.use(162)
        self.record('return162_destination', bot.map_id == expected.map_id and bot.position == (expected.x, expected.y),
            departure=departure, expected=(expected.map_id, expected.x, expected.y), actual=(bot.map_id, *bot.position))
        from tools.local_original_session import movement
        saved = self.broker.realm.positions.restore(movement.Position(bot.self_uid, bot.character, 0, 0, 0))
        self.record('return_position_saved', (saved.map_id, saved.word0, saved.word1) == (bot.map_id, *bot.position),
            saved=(saved.map_id, saved.word0, saved.word1))

    async def case_combat(self):
        bot = self.bot
        before = set(bot.kills)
        start_swings = bot.swings
        group = next(s for s in self.broker._world.data.spawns if s.group_id == self.case['group_id'])
        center = (group.rect.x1 + group.rect.x2) // 2, (group.rect.y1 + group.rect.y2) // 2
        deadline = time.monotonic() + self.args.hunt_timeout
        attacked = {}
        while not bot.kills - before:
            if bot.dead:
                raise hb.BotFailure('OWNER_DIED_DURING_MAP_EXPANSION4_HUNT')
            if time.monotonic() > deadline:
                raise hb.BotFailure('MAP_EXPANSION4_KILL_OBSERVATION_DEADLINE')
            if bot.hp < bot.max_hp * .6:
                await self.use(14)
            living = [(uid, row) for uid, row in bot.actors.items() if row['alive'] and row['template'] == group.template_id]
            if living:
                uid, actor = min(living, key=lambda p: hb.distance(bot.position, p[1]['position']))
                if hb.distance(bot.position, actor['position']) <= 1:
                    attacked[uid] = dict(actor)
                    await bot.attack(uid)
                else:
                    await bot.step(actor['position'], radius=1)
            else:
                await bot.step(center, radius=1)
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.03)
        killed = bot.kills - before
        self.record('received_actor_kill', bool(killed) and killed <= set(attacked) and bot.swings > start_swings,
            map_id=bot.map_id, template_id=group.template_id, killed_uids=sorted(killed),
            swings=bot.swings - start_swings, received_targets=attacked,
            scope='live received actor UID -> real attack frames -> observed death; unchanged monster/combat/drop RNG')


def parser():
    p = expansion2.parser()
    p.description = __doc__
    p.set_defaults(hunt_timeout=600)
    return p


async def run(args):
    data = json.loads(DATA.read_text(encoding='utf-8'))
    cases = data['cases'] if args.case == 'all' else [c for c in data['cases'] if c['case_id'] in args.case.split(',')]
    if not cases:
        raise ValueError('unknown case: ' + args.case)
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    directory = Path(tempfile.mkdtemp(prefix='hunt-map-expansion4-', dir=root))
    policy = world_maps.load_dungeon_policy()
    transitions = {**world_maps.TRANSITIONS, **policy.transitions}
    results = []
    for case in cases:
        profile = directory / case['case_id']
        profile.mkdir()
        scenario = ExpansionScenario(args, case, profile, transitions, policy)
        from tools.local_original_session import world_feature_dungeons, world_terrain
        inputs = [Path(__file__), Path(expansion2.__file__), Path(world_maps.__file__),
                  Path(world_feature_dungeons.__file__), Path(world_terrain.__file__), DATA]
        for folder in ('m1', 'm3', 'm4', 'm6'):
            inputs.extend(p for name in ('monsters.json', 'drops.json', 'map_expansion2.json', 'map_expansion2_population.json')
                          if (p := DATA.parent.parent / folder / name).exists())
        for path in inputs:
            matrix.SOURCE_SHA256[str(path)] = dict(file=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                                basis='map4 case startup input; provenance only')
        with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_SHOP=1, SL_COMPANION=0,
                                SL_COMPANION_PET_UI=0, SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
            print('START ' + case['case_id'], flush=True)
            result = await scenario.run_matrix()
        result['case'] = case
        (profile / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
        results.append(result)
        print(f"{result['status']} {case['case_id']}: {result['elapsed_seconds']}s requests={result['requests']}", flush=True)
        if not result['cleanup_complete']:
            break
    summary = dict(output_directory=str(directory), counts=dict(Counter(r['status'] for r in results)), results=results,
        scope=f'LOCAL ordered packets on fresh pre-login Lv{args.fixture_level} saved-map knight; existing ordinary starter equipment and finite kit, no special boss gear. Four new Tower hunting maps and one non-hunting entrance/transit map distinguished. Entrance neighbour saved fixture, not travel from creation. Native client/input/rendering unverified.',
        unresolved=data['unresolved'], physical_ports=test_ports.listener_ports(),
        disabled_features=__import__('os').environ.get('SL_DISABLE_FEATURES', ''))
    (directory / 'summary.json').write_text(json.dumps(matrix.safe(summary), ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps({k: result[k] for k in ('output_directory', 'counts')}, ensure_ascii=False))
    return 0 if set(result['counts']) == {'PASS'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
