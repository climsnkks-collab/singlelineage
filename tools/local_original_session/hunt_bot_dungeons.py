"""Ordered dungeon packets on fresh, retained test profiles; no game client.

Reuses hunt_bot_play_matrix's FIRST/login, inventory RAM peer, saved knight,
normal item-use router and finally/close. Each family starts just outside
its entrance on a separate saved-map fixture. That initialization is not proof
of travel from the original character creation point, mainland access or a boat.
Only received actors are attacked; every movement and return is a wire request.
LOCAL stairs/returns and static S32 navigation do not establish native UI parity.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, deque
import dataclasses
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


def floor_route(family, transitions):
    """Shortest existing directed map walk covering every family branch.

    Ant maps43..50 are branches, not a fabricated numerical stair chain.
    Same-map maze stairs are handled by the tile planner, not map traversal.
    """
    maps = FAMILIES[family]
    bits = {map_id: 1 << index for index, map_id in enumerate(maps)}
    start = maps[0], bits[maps[0]]
    queue, previous = deque([start]), {start: None}
    while queue:
        state = queue.popleft()
        map_id, visited = state
        if visited == (1 << len(maps)) - 1 and map_id == maps[-1]:
            route = []
            while previous[state] is not None:
                parent, edge = previous[state]
                route.append(edge)
                state = parent
            return tuple(reversed(route))
        for origin, row in transitions.items():
            target = row.destination.map_id
            if origin[0] != map_id or target not in bits or target == map_id:
                continue
            following = target, visited | bits[target]
            if following not in previous:
                previous[following] = state, (origin, row)
                queue.append(following)
    raise matrix.MissingFeature(f'{family}: existing stairs do not cover all floors')


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
        self.route = floor_route(family, transitions)
        self.floor_results = {m: dict(family=family, map_id=m, entry='UNATTEMPTED',
            walk='UNATTEMPTED', combat='UNATTEMPTED', next_floor='UNATTEMPTED',
            return162='UNATTEMPTED') for m in FAMILIES[family]}
        self.stair_history = []
        self._planned_steps = deque()
        self._planned_key = None
        self.stage = 'startup'

    def initialize_hunt_fixture(self):
        """Explicit fresh pre-FIRST growth fixture; no active HP/RNG edits."""
        import random
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        data = load_m1()
        owner = next(row for row in self.broker.realm.store._read()['characters'] if row['class'] == 1)
        stats, level = owner['attributes'], self.args.fixture_level
        exp = data.pc_exp[level - 1]
        baseline = actor_hook.profiles()[0].fields
        profile = PcProfile(1, owner['class'], owner['gender'], stats[0], stats[1],
                            con=stats[2], wis=stats[3])
        growth = on_kill(RewardPcState(0, profile, baseline[11], baseline[13]),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x4f574e52), data=data)
        self.broker._world_progress.commit(owner['uid'], Progress(exp, level, growth.max_hp, growth.max_mp))
        self.fixture_notes.append(dict(pre_login_level=level, pre_login_exp=exp,
            pre_login_max_hp=growth.max_hp, pre_login_max_mp=growth.max_mp,
            reason='explicit all-floor saved-knight test fixture; ordinary product growth, starter equipment and finite potions',
            formula='existing Matrix world_reward.on_kill pure growth; no live grant, HP, monster or RNG change'))

    def travel_heading(self, goal, radius, *, require_reached=False, ignore_actors=False):
        """Cached tile route including existing same-map maze stairs.

        Only bot navigation policy changes. Runtime still checks every packet's
        current position, static edge, occupancy, owner and movement interval.
        """
        bot, terrain = self.bot, self.broker._world.terrain
        start, now = bot.position, time.monotonic()
        occupied = {(e.x, e.y) for e in self.broker._world.entities.near(
            bot.map_id, *start, 32, alive_only=False)
            if e.uid != bot.self_uid and e.kind.value != 'item'}
        if ignore_actors:
            occupied = set()
        key = bot.map_id, goal, radius, ignore_actors
        if self._planned_key == key and self._planned_steps:
            while self._planned_steps and self._planned_steps[0][0] != start:
                self._planned_steps.popleft()
        if self._planned_key == key and self._planned_steps:
            point, heading, destination = self._planned_steps[0]
            if (point == start and destination not in occupied and
                    bot.blocked_edges.get((point, heading), 0) <= now):
                return heading
        self._planned_steps.clear()
        self._planned_key = key
        # Dijkstra remains admissible through non-geometric same-map stairs.
        heap = [(0, start)]
        costs, parents = {start: 0}, {}
        for _ in range(200000):
            if not heap:
                break
            cost, point = heapq.heappop(heap)
            if costs.get(point) != cost:
                continue
            if hb.distance(point, goal) <= radius:
                steps = []
                while point != start:
                    parent, heading = parents[point]
                    steps.append((parent, heading, point))
                    point = parent
                self._planned_steps.extend(reversed(steps))
                return self._planned_steps[0][1] if self._planned_steps else None
            for heading, (dx, dy) in enumerate(hb.DELTAS):
                dest = point[0]+dx, point[1]+dy
                if (dest in occupied or bot.blocked_edges.get((point, heading), 0) > now
                        or terrain.can_step(bot.map_id, *point, heading) is not True):
                    continue
                stair = self.transitions.get((bot.map_id, *dest))
                if stair is not None and dest != goal:
                    if stair.destination.map_id != bot.map_id:
                        continue
                    dest = stair.destination.x, stair.destination.y
                    if dest in occupied:
                        continue
                following = cost+1
                if following >= costs.get(dest, 1 << 30):
                    continue
                costs[dest] = following
                parents[dest] = point, heading
                heapq.heappush(heap, (following, dest))
        return None

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
            marker, request_index = self.bot.peer.ordinal, len(self.requests)
            source_map = self.bot.map_id
            result = await original_step(goal, radius)
            batch = [f for f in self.bot.peer.frames if f.ordinal > marker]
            if source_map == self.bot.map_id and hb.find(batch, 0x4e95) is not None:
                request = next((r for r in self.requests[request_index:] if r['opcode'] == '0x4E2B'), None)
                if request is not None:
                    start = hb.unpack(request['payload']['1'][0])
                    dx, dy = hb.DELTAS[request['payload']['2'][0]]
                    origin = source_map, start[0]+dx, start[1]+dy
                    row = self.transitions.get(origin)
                    if row is not None and row.destination.map_id == source_map:
                        map_frame = hb.find(batch, 0x4e95, **{'1': source_map})
                        status = hb.find([f for f in batch if f.ordinal > map_frame.ordinal],
                                         0x4e38, **{'1': self.bot.self_uid})
                        actor = None if status is None else hb.find(
                            [f for f in batch if f.ordinal > status.ordinal], 0x4e96,
                            **{'2': self.bot.self_uid})
                        self.record(f'same_map_stair_{len(self.stair_history)}', actor is not None and
                            self.bot.position == (row.destination.x, row.destination.y), origin=origin,
                            destination=dataclasses.asdict(row.destination), source=row.source,
                            ref=row.ref, native_trigger_status=row.native_trigger_status)
                        self.stair_history.append(dict(origin=origin,
                            destination=dataclasses.asdict(row.destination), accepted_steps=1,
                            same_map=True, source=row.source, ref=row.ref,
                            native_trigger_status=row.native_trigger_status))
            return result
        self.bot.step = step
        self.record('outside_entrance_saved_map_fixture', self.bot.map_id == self.entry[0][0],
                    family=self.family, start=self.map_start, entrance=self.entry[0],
                    scope=f'fresh pre-login position/level{self.args.fixture_level} fixture; no mainland/boat travel claim')

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
        self.stair_history.append(dict(origin=origin, destination=dataclasses.asdict(destination),
            accepted_steps=bot.moves-moves, source=row.source, ref=row.ref,
            native_trigger_status=row.native_trigger_status))
        if bot.map_id != destination.map_id or bot.position != (destination.x, destination.y):
            raise hb.BotFailure(f'UNEXPECTED_DUNGEON_DESTINATION:{bot.map_id}:{bot.position}')
        bot.blocked_edges.clear()  # bot-local edge observations belong to the old map
        self._planned_steps.clear()

    async def dungeon_items(self):
        # These are already owned, received starter rows. Their normal routes
        # supply armour and ordinary haste/bravery; no test stat override.
        await self.gear((89, 104, 128, 129))
        await self.cross(self.entry, 'walk_external_entry')
        await self.exercise_floor()
        for index, edge in enumerate(self.route):
            source_map = self.bot.map_id
            self.floor_results[source_map]['next_floor'] = 'IN_PROGRESS'
            await self.cross(edge, f'walk_stair_{index}_{source_map}_to_{edge[1].destination.map_id}')
            self.floor_results[source_map]['next_floor'] = 'PASS'
            self.floor_results[source_map]['next_map'] = self.bot.map_id
            if self.floor_results[self.bot.map_id]['combat'] == 'UNATTEMPTED':
                await self.exercise_floor()
        self.stage = 'return162'
        bot = self.bot
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
        returned = bot.map_id == expected_map and bot.position == expected
        self.record('return162_destination', returned,
                    departure=departure, map_id=bot.map_id, position=bot.position)
        from tools.local_original_session import movement
        saved = self.broker.realm.positions.restore(movement.Position(bot.self_uid, bot.character, 0, 0, 0))
        saved_ok = (saved.map_id, saved.word0, saved.word1) == (bot.map_id, *bot.position)
        self.record('return_position_saved', saved_ok, saved_map_id=saved.map_id,
                    saved_position=(saved.word0, saved.word1))
        self.floor_results[departure[0]]['next_floor'] = 'LAST_FLOOR_RETURN'
        for row in self.floor_results.values():
            row['return162'] = 'PASS' if returned and saved_ok else 'FAIL'
            row['return_from_map'] = departure[0]

    async def exercise_floor(self):
        """One accepted walk and observed own kill on each first visit."""
        bot, start = self.bot, self.bot.position
        map_id, moves = bot.map_id, bot.moves
        row = self.floor_results[map_id]
        row['entry'], row['entry_position'] = 'PASS', start
        self.stage = f'map{map_id}_walk'
        await self.use(17)
        await self.use(296)
        for dx, dy in hb.DELTAS:
            point = start[0]+dx, start[1]+dy
            if ((bot.map_id, *point) not in self.transitions and
                    self.broker._world.terrain.can_step(bot.map_id, *start, hb.DELTAS.index((dx, dy))) is True):
                await self.navigate(point)
                break
        walked = bot.position != start and bot.map_id == map_id and bot.moves > moves
        row['walk'] = 'PASS' if walked else 'FAIL'
        self.record(f'map{map_id}_dungeon_walk', walked, before=start, after=bot.position)
        self.stage = f'map{map_id}_wire_combat'
        row['combat'] = 'IN_PROGRESS'
        before = set(bot.kills)
        swings = bot.swings
        await self.first_floor_combat()
        row.update(combat='PASS' if bot.kills-before else 'FAIL',
                   killed_uids=sorted(bot.kills-before), swings=bot.swings-swings,
                   accepted_walk_steps=bot.moves-moves, finish_position=bot.position)
        self.record(f'map{map_id}_received_actor_kill', bool(bot.kills-before),
                    map_id=bot.map_id, killed_uids=sorted(bot.kills-before), swings=bot.swings,
                    policy='received current actor, actual attack packets and observed death; ordinary product RNG')

    async def first_floor_combat(self):
        """Attempt received current-floor mobs with no grant/roll."""
        bot, before = self.bot, set(self.bot.kills)
        until = time.monotonic()+self.args.hunt_timeout
        while not bot.kills-before:
            if bot.dead:
                raise hb.BotFailure('OWNER_DIED_DURING_DUNGEON_HUNT')
            if time.monotonic() >= until:
                raise hb.BotFailure('DUNGEON_KILL_OBSERVATION_DEADLINE')
            if bot.hp < bot.max_hp*.6:
                await self.use(14)
            living = sorted(((uid, row) for uid, row in bot.actors.items() if row['alive']),
                key=lambda p: (bot.data.monsters[p[1]['template']].level,
                               hb.distance(bot.position, p[1]['position'])))
            target = next((p for p in living if hb.distance(bot.position, p[1]['position']) <= 1 or
                           self.travel_heading(p[1]['position'], 1, require_reached=True) is not None), None)
            if target is not None:
                uid, actor = target
                if hb.distance(bot.position, actor['position']) <= 1:
                    await bot.attack(uid)
                else:
                    await bot.step(actor['position'], radius=1)
            else:
                groups = [g for g in bot.data.spawns if g.map_id == bot.map_id]
                if not groups:
                    raise matrix.MissingFeature(f'No spawn input on map{bot.map_id}')
                goals = sorted(groups, key=lambda g: (bot.data.monsters[g.template_id].level,
                    hb.distance(bot.position, ((g.rect.x1+g.rect.x2)//2, (g.rect.y1+g.rect.y2)//2))))
                goal = next((point for g in goals if hb.distance(bot.position, point :=
                    ((g.rect.x1+g.rect.x2)//2, (g.rect.y1+g.rect.y2)//2)) <= 1 or
                    self.travel_heading(point, 1, require_reached=True) is not None), None)
                if goal is None or hb.distance(bot.position, goal) <= 1:
                    await bot.alive()
                else:
                    await bot.step(goal, radius=1)
            if time.monotonic()-bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.03)


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--family', choices=(*FAMILIES, 'all'), default='all')
    cli.add_argument('--timeout', type=hb.positive, default=8)
    cli.add_argument('--navigation-timeout', type=hb.positive, default=420)
    cli.add_argument('--hunt-timeout', type=hb.positive, default=240)
    cli.add_argument('--fixture-level', type=int, choices=range(1, 61), default=60,
                     help='explicit fresh pre-login knight growth fixture (default60); product rules unchanged')
    cli.set_defaults(scenario='dungeon_items', minutes=1, potion_threshold=.5,
                     companion_revive_exp=False)
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
        for row in scenario.floor_results.values():
            for key in ('combat', 'next_floor'):
                if row[key] == 'IN_PROGRESS':
                    row[key] = 'FAIL'
        result['floor_results'] = list(scenario.floor_results.values())
        result['stair_history'] = scenario.stair_history
        result['planned_map_route'] = [scenario.entry[0][0], FAMILIES[family][0],
                                      *(edge[1].destination.map_id for edge in scenario.route)]
        # Keep the existing result artifact and add explicit family identity.
        (profile / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
        results.append(result)
        print(f"{result['status']} {family}: {result['elapsed_seconds']}s requests={result['requests']}", flush=True)
        if not result['cleanup_complete']:
            break
    summary = dict(output_directory=str(directory), scope='LOCAL dungeon socket paths on explicit saved-map fixtures; native UI/input UNKNOWN',
                   loaded_magic_startup=magic_startup,
                   excluded_maps={'5': 'ship interior; not a hunting dungeon', '6': 'ship interior; not a hunting dungeon'},
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
