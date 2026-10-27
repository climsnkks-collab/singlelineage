"""Ordered dungeon packets on fresh, retained test profiles; no game client.

Reuses hunt_bot_play_matrix's FIRST/login, inventory RAM peer, saved level-six
knight, normal item-use router and finally/close. Each family starts just outside
its entrance on a separate saved-map fixture. That initialization is not proof
of travel from the original character creation point, mainland access or a boat.
Only received actors are attacked; every movement and return is a wire request.
LOCAL stairs/returns and static S32 navigation do not establish native UI parity.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import heapq
import json
from pathlib import Path
import sys
import tempfile
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import world_maps


FAMILIES = {'talking_island': (1, 2), 'gludio': tuple(range(7, 14)),
            'elven_forest': (19, 20, 21), 'ant_cave': tuple(range(43, 52))}


def family_route(family, transitions):
    """Pick an external entrance and an actual next-floor edge, never a warp."""
    maps = FAMILIES[family]
    entries = [(origin, row) for origin, row in transitions.items()
               if origin[0] in (0, 4) and row.destination.map_id == maps[0]]
    floors = [(origin, row) for origin, row in transitions.items()
              if origin[0] == maps[0] and row.destination.map_id in maps[1:]]
    if not entries or not floors:
        raise matrix.MissingFeature(f'{family}: external entrance/next floor missing')
    # Existing policy insertion order retains the source's preferred entrance.
    return entries[0], floors[0]


def entrance_start(terrain, origin, transitions):
    """A passable source neighbour, with a real S32 step into the entry cell."""
    map_id, x, y = origin
    for heading, (dx, dy) in enumerate(hb.DELTAS):
        start = (x-dx, y-dy)
        if ((map_id, *start) not in transitions and
                terrain.can_stand(map_id, *start) is True and
                terrain.can_step(map_id, *start, heading) is True):
            return map_id, *start
    raise matrix.MissingFeature(f'No passable external neighbour: {origin}')


class DungeonScenario(matrix.Matrix):
    def __init__(self, args, family, directory, transitions, policy):
        # Reuse the already documented dungeon_items fixture initialization.
        super().__init__(args, 'dungeon_items', directory)
        self.family, self.transitions = family, transitions
        self.dungeon_policy = policy
        self.entry, self.floor = family_route(family, transitions)
        self.stage = 'startup'

    def travel_heading(self, goal, radius):
        """Existing Matrix A* with other stair cells excluded from bot choices.

        Only bot navigation policy changes. Runtime still checks every packet's
        current position, static edge, occupancy, owner and movement interval.
        """
        bot, terrain = self.bot, self.broker._world.terrain
        start, now = bot.position, time.monotonic()
        occupied = {(e.x, e.y) for e in self.broker._world.entities.near(
            bot.map_id, *start, 32, alive_only=False)
            if e.uid != bot.self_uid and e.kind.value != 'item'}
        heap = [(hb.distance(start, goal), 0, start, None)]
        costs, best = {start: 0}, None
        for _ in range(20000):
            if not heap:
                break
            _, cost, point, first = heapq.heappop(heap)
            if costs.get(point) != cost:
                continue
            if hb.distance(point, goal) <= radius:
                return first
            if first is not None and (best is None or hb.distance(point, goal) < best[0]):
                best = hb.distance(point, goal), first
            for heading, (dx, dy) in enumerate(hb.DELTAS):
                dest = point[0]+dx, point[1]+dy
                if (dest in occupied or bot.blocked_edges.get((point, heading), 0) > now
                        or ((bot.map_id, *dest) in self.transitions and dest != goal)
                        or terrain.can_step(bot.map_id, *point, heading) is not True):
                    continue
                following = cost+1
                if following >= costs.get(dest, 1 << 30):
                    continue
                costs[dest] = following
                heapq.heappush(heap, (following+hb.distance(dest, goal), following,
                                     dest, heading if first is None else first))
        return None if best is None else best[1]

    async def open(self, **options):
        await super().open(**options)
        # Ant cave has real level12+ mobs. This permits attempting them, without
        # changing their stats, live HP, damage, RNG or server movement checks.
        self.bot.safe_hunt_cell = lambda point: True
        self.bot.hunt_target = lambda actor: actor['alive']
        original_step = self.bot.step

        async def step(goal, radius=0):
            if self.bot.hp is not None and 0 < self.bot.hp < self.bot.max_hp*.6:
                await self.use(14)
            return await original_step(goal, radius)
        self.bot.step = step
        self.record('outside_entrance_saved_map_fixture', self.bot.map_id == self.entry[0][0],
                    family=self.family, start=self.map_start, entrance=self.entry[0],
                    scope='fresh pre-login position/level6 fixture; no mainland/boat travel claim')

    async def cross(self, edge, label):
        origin, row = edge
        bot = self.bot
        if bot.map_id != origin[0]:
            raise hb.BotFailure(f'WRONG_SOURCE_MAP:{bot.map_id}:{origin[0]}')
        self.stage = label
        marker, moves, start = bot.peer.ordinal, bot.moves, bot.position
        await self.navigate(origin[1:], predicate=lambda: bot.map_id != origin[0])
        batch = [frame for frame in bot.peer.frames if frame.ordinal > marker]
        map_frame = hb.find(batch, 0x4e95, **{'1': row.destination.map_id})
        status = None if map_frame is None else hb.find(
            [f for f in batch if f.ordinal > map_frame.ordinal], 0x4e38,
            **{'1': bot.self_uid})
        actor = None if status is None else hb.find(
            [f for f in batch if f.ordinal > status.ordinal], 0x4e96,
            **{'2': bot.self_uid})
        destination = row.destination
        self.record(label, bot.map_id == destination.map_id and
            bot.position == (destination.x, destination.y) and actor is not None and bot.moves > moves,
            origin=origin, departure=start, map_id=bot.map_id, position=bot.position,
            accepted_steps=bot.moves-moves,
            map_status_self_ordinals=[None if f is None else f.ordinal for f in (map_frame, status, actor)],
            source=row.source, native_trigger_status=row.native_trigger_status)
        bot.blocked_edges.clear()  # bot-local edge observations belong to the old map

    async def dungeon_items(self):
        await self.cross(self.entry, 'walk_external_entry')
        self.stage = 'walk_inside_first_floor'
        bot, start = self.bot, self.bot.position
        for dx, dy in hb.DELTAS:
            point = start[0]+dx, start[1]+dy
            if ((bot.map_id, *point) not in self.transitions and
                    self.broker._world.terrain.can_step(bot.map_id, *start, hb.DELTAS.index((dx, dy))) is True):
                await self.navigate(point)
                break
        self.record('dungeon_walk', bot.position != start and bot.map_id == self.entry[1].destination.map_id,
                    before=start, after=bot.position)
        self.stage = 'first_floor_wire_combat'
        before = set(bot.kills)
        await self.first_floor_combat()
        self.record('first_floor_received_actor_kill', bool(bot.kills-before),
                    map_id=bot.map_id, killed_uids=sorted(bot.kills-before), swings=bot.swings,
                    policy='received current actor, actual attack packets and observed death; ordinary product RNG')
        await self.cross(self.floor, 'walk_next_floor')
        self.stage = 'return162'
        departure = (bot.map_id, *bot.position)
        await self.use(162)
        expected_map = self.entry[0][0]
        expected = (bot.data.town.respawn_x, bot.data.town.respawn_y)
        if expected_map == 4:
            dest = self.dungeon_policy.return_for(departure[0])
            if dest is None:
                raise matrix.MissingFeature(f'No dungeon return policy for map{departure[0]}')
            expected_map = dest.map_id
            expected = dest.x, dest.y
        self.record('return162_destination', bot.map_id == expected_map and bot.position == expected,
                    departure=departure, map_id=bot.map_id, position=bot.position)
        from tools.local_original_session import movement
        saved = self.broker.realm.positions.restore(movement.Position(bot.self_uid, bot.character, 0, 0, 0))
        self.record('return_position_saved', (saved.map_id, saved.word0, saved.word1) ==
                    (bot.map_id, *bot.position), saved_map_id=saved.map_id,
                    saved_position=(saved.word0, saved.word1))

    async def first_floor_combat(self):
        """Attempt real first-floor mobs, including ant12, with no grant/roll."""
        bot, before = self.bot, set(self.bot.kills)
        until = time.monotonic()+self.args.hunt_timeout
        while not bot.kills-before:
            if bot.dead:
                raise hb.BotFailure('OWNER_DIED_DURING_DUNGEON_HUNT')
            if time.monotonic() >= until:
                raise hb.BotFailure('DUNGEON_KILL_OBSERVATION_DEADLINE')
            if bot.hp < bot.max_hp*.6:
                await self.use(14)
            living = [(uid, row) for uid, row in bot.actors.items() if row['alive']]
            if living:
                uid, actor = min(living, key=lambda p: (bot.data.monsters[p[1]['template']].level,
                                                       hb.distance(bot.position, p[1]['position'])))
                if hb.distance(bot.position, actor['position']) <= 1:
                    await bot.attack(uid)
                else:
                    await bot.step(actor['position'], radius=1)
            else:
                groups = [g for g in bot.data.spawns if g.map_id == bot.map_id]
                if not groups:
                    raise matrix.MissingFeature(f'No spawn input on map{bot.map_id}')
                group = min(groups, key=lambda g: (bot.data.monsters[g.template_id].level,
                    hb.distance(bot.position, ((g.rect.x1+g.rect.x2)//2, (g.rect.y1+g.rect.y2)//2))))
                await bot.step(((group.rect.x1+group.rect.x2)//2, (group.rect.y1+group.rect.y2)//2), radius=1)
            if time.monotonic()-bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.03)


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--family', choices=(*FAMILIES, 'all'), default='all')
    cli.add_argument('--timeout', type=hb.positive, default=8)
    cli.add_argument('--navigation-timeout', type=hb.positive, default=420)
    cli.add_argument('--hunt-timeout', type=hb.positive, default=240)
    cli.set_defaults(scenario='dungeon_items', minutes=1, potion_threshold=.5,
                     fixture_level=6, companion_revive_exp=False)
    return cli


async def run(args):
    from tools.local_original_session import world_terrain
    from tools.local_original_session import world_feature_magic
    from tools.local_original_session.world_terrain import WorldTerrain
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-dungeons-', dir=root))
    # Extend Matrix's existing result provenance once, before any listener is
    # started. These hashes never gate or re-read a live request.
    inputs = (Path(__file__), Path(world_maps.__file__), Path(world_terrain.__file__),
              Path(world_feature_magic.__file__),
              *sorted((Path(__file__).parent / 'data/m6').glob('*.json')))
    for path in inputs:
        matrix.SOURCE_SHA256[str(path)] = dict(file=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), basis='dungeon run startup input')
    magic_startup = dict(module=world_feature_magic.__name__, file=world_feature_magic.__file__,
        initialize_module=world_feature_magic._world_magic_initialize.__module__,
        consumers_callable=callable(world_feature_magic._world_magic_initialize.__globals__.get('_world_magic_consumers')),
        sha256=matrix.SOURCE_SHA256[str(Path(world_feature_magic.__file__))]['sha256'])
    print(json.dumps({'loaded_magic_startup': magic_startup}, ensure_ascii=False), flush=True)
    policy = world_maps.load_dungeon_policy()
    transitions = {**world_maps.TRANSITIONS, **policy.transitions}
    names = tuple(FAMILIES) if args.family == 'all' else (args.family,)
    results = []
    for family in names:
        profile = directory / family
        profile.mkdir()
        scenario = DungeonScenario(args, family, profile, transitions, policy)
        terrain = WorldTerrain.load(map_ids=(scenario.entry[0][0],))
        scenario.map_start = entrance_start(terrain, scenario.entry[0], transitions)
        with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_SHOP=1,
                SL_COMPANION=0, SL_COMPANION_PET_UI=0, SL_SPELL_EXP=0,
                SL_COMPANION_REVIVE_EXP=0):
            print('START '+family, flush=True)
            result = await scenario.run_matrix()
        result['family'] = family
        # Keep the existing result artifact and add explicit family identity.
        (profile / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
        results.append(result)
        print(f"{result['status']} {family}: {result['elapsed_seconds']}s requests={result['requests']}", flush=True)
        if not result['cleanup_complete']:
            break
    summary = dict(output_directory=str(directory), scope='LOCAL dungeon socket paths on explicit saved-map fixtures; native UI/input UNKNOWN',
                   loaded_magic_startup=magic_startup,
                   counts=dict(Counter(r['status'] for r in results)), results=results)
    (directory / 'summary.json').write_text(json.dumps(matrix.safe(summary), ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main(argv=None):
    args = parser().parse_args(argv)
    result = asyncio.run(run(args))
    print(json.dumps({'output_directory': result['output_directory'], 'counts': result['counts']}, ensure_ascii=False))
    return 0 if result['counts'] == {'PASS': len(FAMILIES) if args.family == 'all' else 1} else 1


if __name__ == '__main__':
    raise SystemExit(main())
