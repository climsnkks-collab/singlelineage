"""Observe production field populations, or exercise explicit template fixtures.

Reuses the population audit's normal wire login, attack and close lifecycle.
No production spawn tables are written. Native rendering/input are unverified.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
from pathlib import Path
import time
import uuid

from tools.local_original_session import hunt_bot_spawn_audit as audit


class MonsterFill(audit.Audit):
    def initialize_hunt_fixture(self):
        super().initialize_hunt_fixture()
        from tools.local_original_session.world_interest_spawn import InterestSpawner
        world = self.broker._world
        # Matrix calls this before broker.start and before any PC binds. Keep
        # the original runtime/spawner callbacks, terrain and RNG owners.
        data = dataclasses.replace(world.data, spawns=tuple(self.groups))
        fixture = InterestSpawner(world.entities, data,
            passable=world.spawner.passable, rng=world.spawner.rng)
        world.spawner.groups[:] = fixture.groups
        world.replace_data(data)
        self.expected_population = dict(monsters=len(data.monsters), groups=len(self.groups))
        self.fixture_notes.append(dict(test_only_spawn=[dict(group_id=g.group_id,
            template_id=g.template_id, map_id=g.map_id, rect=dataclasses.asdict(g.rect),
            target_count=g.target_count) for g in self.groups],
            scope='fresh pre-login test spawn fixture; production spawns unchanged; HP/RNG/combat unchanged'))


class PopulationFill(audit.Audit):
    """Normal login at a fresh saved-position fixture; production slots retained."""

    async def dungeon_items(self):
        world, bot = self.broker._world, self.bot
        bot.terrain = world.terrain
        bot.safe_hunt_cell = lambda point: True
        expected = audit.all_data()
        specs = {g.group_id: g for g in expected.spawns}
        actual = {g.spec.group_id: g for g in world.spawner.groups}
        self.record('production_specs_and_slots', set(actual) == set(specs) and all(
            actual[key].spec == spec and len(actual[key].slots) == spec.target_count
            for key, spec in specs.items()),
            groups=len(actual), target_count=sum(len(g.slots) for g in actual.values()))
        if self.args.combat_production:
            await super().dungeon_items()
            for row in self.audit_rows.values():
                self.record('selected_production_actor_killed', row['combat']=='KILLED',
                    group=row['group'], combat=row['combat'], errors=row['errors'])
                row['scope']='unchanged production group/slots; saved PC fixture, wire combat sample'
            return
        self.stage = 'production_receive_observation'
        until = time.monotonic() + self.args.observe_seconds
        while time.monotonic() < until:
            await self.beat()
        for spec in self.groups:
            row = self.audit_rows[spec.group_id]
            self.observe()
            # Broad SQL animal rectangles can place the selected species beyond
            # the initial screen. Search using only source coordinates and normal
            # movement, never hidden live NPC coordinates or a server relocation.
            if not row['received_uids']:
                until = time.monotonic() + self.args.approach_seconds
                sx, sy = bot.position
                goals = [(sx+dx,sy+dy) for dx,dy in
                    ((24,0),(24,24),(0,24),(-24,24),(-24,0),(-24,-24),(0,-24),(24,-24))
                    if spec.rect.contains(sx+dx,sy+dy)
                    and world.terrain.can_stand(spec.map_id,sx+dx,sy+dy) is True]
                index = 0
                while goals and time.monotonic() < until and not row['received_uids']:
                    goal = goals[index % len(goals)]
                    if audit.hb.distance(bot.position,goal) <= 1:
                        index += 1
                        goal = goals[index % len(goals)]
                    await bot.step(goal,radius=1)
                    await self.beat()
            self.record('selected_production_actor_received', bool(row['received_uids']),
                group=spec.group_id, issued_uids=row['issued_uids'], received_uids=row['received_uids'])
            row['combat'] = 'NOT_ATTEMPTED_PRODUCTION_RECEIVE_ONLY'
            row['scope'] = 'unchanged production group/slots; received Actor, not kill/native proof'
        self.fixture_notes.append(dict(production_population_unchanged=True,
            scope='saved PC start fixture only; no monster relocation/count/HP/RNG/AI changes'))


def population_groups(data):
    """One exact SQL row per requested mainland field plus map0 ambient birds."""
    raw = json.loads((Path(__file__).parent/'data/m6/field_population.json').read_text(encoding='utf-8'))
    specs = {g.group_id: g for g in data.spawns}
    map0_ids = (27546,)
    map0 = json.loads((Path(__file__).parent/'data/m6/map0_population.json').read_text(encoding='utf-8'))
    by_source = {r['l1j_spawn_id']: specs[r['group_id']['value']] for r in map0['groups']}
    selected = [by_source[sid] for sid in map0_ids]
    for area in ('글루디오', '켄트', '윈다우드', '용의 계곡', '오크 숲', '기란'):
        rows = [r for r in raw['groups'] if r['population_area'] == area]
        candidates = [specs[r['group_id']['value']] for r in rows]
        # A small own-SQL support has reliable visibility; do not resize a group
        # or use a hidden live server coordinate to manufacture a received actor.
        candidates = [g for g in candidates if g.rect.x2-g.rect.x1 <= 30
            and g.rect.y2-g.rect.y1 <= 30 and data.monsters[g.template_id].level <= 30]
        if not candidates:
            raise ValueError(f'NO_PRODUCTION_REPRESENTATIVE:{area}')
        selected.append(min(candidates, key=lambda g:(data.monsters[g.template_id].aggressive,
            data.monsters[g.template_id].level, g.group_id)))
    return selected


async def run_population(args):
    from tools.local_original_session.world_terrain import WorldTerrain
    data = audit.all_data()
    if args.groups:
        specs={g.group_id:g for g in data.spawns}
        selected=[specs[key] for key in args.groups]
        if any(g.map_id!=4 or not g.group_id.startswith('m6_field_l1j_') for g in selected):
            raise ValueError('EXACT_MAINLAND_PRODUCTION_GROUPS_REQUIRED')
    else:
        selected = population_groups(data)
    root = args.output_root
    root.mkdir(parents=True,exist_ok=True)
    directory = root/f'monster-fill-population-{uuid.uuid4().hex}'
    directory.mkdir()
    rows, epochs = [], []
    terrain = WorldTerrain.load(map_ids=(0, 4))
    original_bot = audit.hs.ScenarioBot
    audit.hs.ScenarioBot = audit.AuditBot
    print(json.dumps(dict(output_directory=str(directory),
        scope='PRODUCTION_POPULATION_COMBAT_SAMPLES' if args.combat_production else 'PRODUCTION_POPULATION_RECEIVE_SAMPLES', groups=[g.group_id for g in selected])), flush=True)
    try:
        for index, group in enumerate(selected, 1):
            start = audit.start_cell(terrain, group.map_id, group.rect)
            # A fixed spawn must not be occupied by the pre-login PC fixture.
            if group.rect.x1 == group.rect.x2 and group.rect.y1 == group.rect.y2:
                start = next((group.map_id, start[1]+dx, start[2]+dy)
                    for h,(dx,dy) in enumerate(audit.hb.DELTAS)
                    if terrain.can_step(*start,h) is True)
            output = directory/f'epoch-{index:03}'
            output.mkdir()
            scene = PopulationFill(args, output, [group], {})
            scene.map_start = start
            result = await scene.run_matrix()
            for row in scene.audit_rows.values():
                row.update(epoch=index, error=result.get('failure'), cleanup_complete=result['cleanup_complete'])
                rows.append(row)
            epochs.append(dict(epoch=index, group=group.group_id, map_id=group.map_id,
                status=result['status'], failure=result.get('failure'), cleanup_complete=result['cleanup_complete']))
            (directory/'groups.json').write_text(json.dumps(audit.matrix.safe(rows), ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(epochs[-1], ensure_ascii=False), flush=True)
            if not result['cleanup_complete']:
                break
    finally:
        audit.hs.ScenarioBot = original_bot
    if args.combat_production:
        audit.write_tables(directory,rows,data)
    summary = dict(output_directory=str(directory), scope='PRODUCTION_POPULATION_COMBAT_SAMPLES' if args.combat_production else 'PRODUCTION_POPULATION_RECEIVE_SAMPLES',
        requested_groups=[g.group_id for g in selected], received=sum(bool(r['received_uids']) for r in rows),
        **(dict(killed=sum(r['combat']=='KILLED' for r in rows)) if args.combat_production else {}),
        epochs=epochs, cleanup_complete=len(epochs)==len(selected) and all(e['cleanup_complete'] for e in epochs),
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__), Path(audit.__file__), Path(__file__).parent/'game_data.py',
             *sorted((Path(__file__).parent/'data').glob('m*/*.json')))},
        limitations='Saved-position/level/equipment fixtures; exact production-row samples only. Production spawns/HP/RNG/AI unchanged. No native rendering/input/whole-field coverage proof.')
    (directory/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def fixture_location(data, terrain):
    original = next(g for g in data.spawns if g.group_id == 'm1_orc')
    map_id, x, y = audit.start_cell(terrain, original.map_id, original.rect)
    for heading, (dx, dy) in enumerate(audit.hb.DELTAS):
        if terrain.can_step(map_id, x, y, heading) is True:
            return original, (map_id, x, y), audit.gd.Rect(x+dx, y+dy, x+dx, y+dy)
    raise ValueError('NO_ADJACENT_FIXTURE_SPAWN')


async def run(args):
    if not args.templates:
        return await run_population(args)
    from tools.local_original_session.world_terrain import WorldTerrain
    data = audit.all_data()
    missing = set(args.templates) - set(data.monsters)
    if missing:
        raise ValueError(f'UNREGISTERED_MONSTERS:{sorted(missing)}')
    if any(data.monsters[t].death_action is None for t in args.templates):
        raise ValueError('AMBIENT_NO_ORDINARY_DEATH_ACTION:use default production receive mode for birds')
    root = args.output_root
    root.mkdir(parents=True,exist_ok=True)
    directory = root/f'monster-fill-{uuid.uuid4().hex}'
    directory.mkdir()
    original, start, rect = fixture_location(data, WorldTerrain.load(map_ids=(0,)))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path(__file__), Path(audit.__file__), *sorted((Path(__file__).parent/'data').glob('m*/*.json')))}
    rows, epochs = [], []
    original_bot = audit.hs.ScenarioBot
    audit.hs.ScenarioBot = audit.AuditBot
    print(json.dumps(dict(output_directory=str(directory), templates=args.templates,
        scope='DEVELOPMENT_ISOLATED_SPAWN_FIXTURE')), flush=True)
    try:
        for index, template in enumerate(args.templates, 1):
            group = dataclasses.replace(original, group_id=f'test_monster_fill_{template}',
                template_id=template, rect=rect, target_count=1,
                placement=None,
                respawn_delay_min_ms=600000, respawn_delay_max_ms=600000)
            output = directory/f'epoch-{index:03}'
            output.mkdir()
            scene = MonsterFill(args, output, [group], {})
            scene.map_start = start
            result = await scene.run_matrix()
            for row in scene.audit_rows.values():
                row.update(epoch=index, source=dict(population_area='TEST_FIXTURE_MAP0'),
                    error=result.get('failure'), cleanup_complete=result['cleanup_complete'])
                rows.append(row)
            epochs.append(dict(epoch=index, template=template, status=result['status'],
                failure=result.get('failure'), cleanup_complete=result['cleanup_complete']))
            (directory/'groups.json').write_text(json.dumps(audit.matrix.safe(rows),
                ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(epochs[-1], ensure_ascii=False), flush=True)
            if not result['cleanup_complete']:
                break
    finally:
        audit.hs.ScenarioBot = original_bot
    audit.write_tables(directory, rows, data)
    summary = dict(output_directory=str(directory), scope='DEVELOPMENT_ISOLATED_SPAWN_FIXTURE',
        requested_templates=args.templates, received=sum(bool(r['received_uids']) for r in rows),
        killed=sum(r['combat'] == 'KILLED' for r in rows), epochs=epochs,
        source_sha256=hashes, cleanup_complete=all(e['cleanup_complete'] for e in epochs))
    (directory/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--templates', type=int, nargs='+', help='explicit isolated kill fixtures; default is7 production receive samples')
    cli.add_argument('--groups',nargs='+',help='exact mainland production groups, one saved-position epoch per row')
    cli.add_argument('--combat-production',action='store_true',help='attack received actors in unchanged production groups')
    cli.add_argument('--output-root',type=Path,default=Path(__file__).resolve().parents[2]/'work/local_original_session/runs')
    cli.add_argument('--fixture-level', type=int, default=99)
    cli.add_argument('--boss-fixture', action='store_true')
    cli.add_argument('--strong-fixture', action='store_true')
    cli.add_argument('--fixture-heal-template', type=int, choices=(130, 279), default=279)
    cli.add_argument('--fixture-heal-count', type=int, default=250)
    cli.add_argument('--one-group-per-epoch', action='store_true', help='always enabled')
    cli.add_argument('--timeout', type=audit.hb.positive, default=8)
    cli.add_argument('--observe-seconds', type=audit.hb.positive, default=6)
    cli.add_argument('--approach-seconds', type=audit.hb.positive, default=45)
    cli.add_argument('--combat-seconds', type=audit.hb.positive, default=420)
    cli.set_defaults(scenario='dungeon_items', minutes=1, potion_threshold=.7,
        companion_revive_exp=False, navigation_timeout=60)
    with audit.matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1, SL_COMPANION=0, SL_COMPANION_PET_UI=0,
            SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
        result = asyncio.run(run(cli.parse_args(argv)))
    print(json.dumps({k: v for k, v in result.items() if k not in ('epochs', 'source_sha256')},
        ensure_ascii=False))
    wanted = len(result.get('requested_templates', result.get('requested_groups', ())))
    completed = result.get('killed', result['received'])
    return 0 if (result['cleanup_complete'] and completed == wanted
        and all(e['status'] == 'PASS' for e in result['epochs'])) else 1


if __name__ == '__main__':
    raise SystemExit(main())
