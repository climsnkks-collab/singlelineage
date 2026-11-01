"""Read-only map0 backend scale bench; no socket, broker, game or output files.

Run with ``python -B -m tools.local_original_session.world_scale_bench``.
This is a development benchmark, never a client/gameplay PASS. Catalog identities
remain candidates; seven unresolved identities use negative, bench-only IDs.
The pure view adapter follows world_visibility.update_pc/tick ordering but records
movement/attacks instead of encoding packets. The real WorldView cannot consume
this catalog: npc.NpcSpawn currently admits only the four M1 template/sprite pairs.
Thus packet encoding, combat arithmetic, recovery, transport and native rendering
are explicitly outside these measurements. Runtime, registry, scheduler, spawner,
NpcAi and client S32 static mask1 movement are the production implementations.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import cProfile
from dataclasses import dataclass, replace
import heapq
from itertools import combinations
import json
import logging
from pathlib import Path
import pstats
import random
import time
import tracemalloc
from types import MappingProxyType, SimpleNamespace

from tools.local_original_session import game_data as gd, npc_ai
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_interest_spawn import InterestSpawner, RON, ROFF, rect_distance
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_terrain import WorldTerrain, DEFAULT_MAP_ROOT

CATALOG = Path(__file__).resolve().parent / 'data/catalog/map0'
TICK_S = 0.150
BUDGET_MS = 45.0
PC = 1


def load_catalog(directory=CATALOG):
    """Use existing typed parsers; adapt only the catalog's unresolved identities.

    Existing game_data.load_m1 does not load catalog/map0. Unresolved original
    rows supply workload HP, range, aggro and L1J speeds, never Classic identities.
    No drop/catalog file is changed or made playable by this adapter.
    """
    directory = Path(directory)
    monsters_raw = json.loads((directory / 'monsters.json').read_text(encoding='utf-8'))
    spawns_raw = json.loads((directory / 'spawns.json').read_text(encoding='utf-8'))
    monsters = dict(gd._monsters(monsters_raw))
    base = gd.load_m1()
    unresolved = {}
    for entry in monsters_raw['unresolved_monsters']:
        row = entry['l1j_row']
        key = -int(row['npcid'])  # Never emitted as a native template ID.
        source = gd.Source('l1j', entry['l1j_ref'], 'BENCH ONLY: unresolved Classic identity')
        monsters[key] = gd.MonsterDef(
            key, row['nameid'], row['name'], int(row['gfxid']), int(row['npcid']),
            int(row['lvl']), int(row['hp']), int(row['mp']), int(row['ac']), int(row['exp']),
            bool(int(row['agro'])), int(row['passispeed']), int(row['atkspeed']),
            int(row['ranged']), 13, 20, gd.DamageDef(0, 0, int(row['str']), 'bench_not_consumed'),
            50000, MappingProxyType({'identity': gd.Source('local_policy', str(directory),
                'Negative bench ID; NOT a Classic template mapping'), 'workload': source}))
        unresolved[int(row['npcid'])] = key
    groups = list(spawns_raw['groups'])
    for entry in spawns_raw['unresolved_groups']:
        row = dict(entry)
        row['template_id'] = {'value': unresolved[row['l1j_npcid']], 'source': 'local_policy',
                              'ref': 'world_scale_bench.load_catalog: negative bench identity'}
        groups.append(row)
    spawns = gd._spawns({'groups': groups})
    if len({s.group_id for s in spawns}) != len(spawns):
        raise ValueError('BENCH_DUPLICATE_GROUP')
    count = sum(s.target_count for s in spawns)
    if count != spawns_raw['summary']['local_count_with_mobgroup'] or count != 254:
        raise ValueError(f'BENCH_EXPECTED_254_SLOTS:{count}')
    if any(s.map_id != 0 or s.template_id not in monsters for s in spawns):
        raise ValueError('BENCH_MAP_OR_IDENTITY_MISSING')
    return replace(base, monsters=MappingProxyType(monsters), spawns=spawns), {
        'groups': len(spawns), 'slots': count, 'candidate_monsters': len(monsters_raw['monsters']),
        'unresolved_monsters': len(unresolved), 'unresolved_slots': sum(
            s.target_count for s in spawns if s.template_id < 0),
        'identity_policy': 'candidate mappings retained; unresolved IDs are negative BENCH ONLY',
        'placement_policy': 'InterestSpawner uniform inclusive rectangles; not original L1J distributions'}


def geometric_maxima(spawns, radius):
    """Exact integer-plane overlap maxima of expanded inclusive rectangles.

    The active set is constant in each Cartesian interval induced by x1-r and
    x2+r+1 (and y). Testing one integer per cell is exhaustive, not grid sampling.
    ROFF gives only a retention upper bound: activation history can lower it.
    Terrain/reachability is a separate witness/route check.
    """
    xs = sorted({v for s in spawns for v in (s.rect.x1-radius, s.rect.x2+radius+1)})
    ys = sorted({v for s in spawns for v in (s.rect.y1-radius, s.rect.y2+radius+1)})
    out = {metric: {'value': -1, 'cells': []} for metric in ('groups', 'slots')}
    for x, nx in zip(xs, xs[1:]):
        candidates = [s for s in spawns if s.rect.x1-radius <= x <= s.rect.x2+radius]
        for y, ny in zip(ys, ys[1:]):
            active = [s for s in candidates if s.rect.y1-radius <= y <= s.rect.y2+radius]
            for metric, value in (('groups', len(active)), ('slots', sum(s.target_count for s in active))):
                best = out[metric]
                if value > best['value']:
                    best.update(value=value, cells=[])
                if value == best['value']:
                    best['cells'].append((x, y, nx-1, ny-1))
    return out


def reachable_group_bound(spawns, observed_lower):
    """Exact hysteresis feasibility bound above an actually observed group count.

    Every active set fits a ROFF point coverage. Its last-activated group must
    have a RON point inside all those ROFF rectangles. Peel such a group, then
    repeat; removing an eligible group only enlarges the remaining intersection,
    so greedy peeling cannot destroy another valid activation ordering. Every
    coverage set is contained in a coverage at some expanded left/bottom event.
    Enumerate only subsets larger than the observed lower bound (90 groups here,
    at most 52 concurrent; the catalog has just seven relevant coverage sets).
    This is a geometric upper bound; an observed walk meeting it proves equality.
    """
    coverages = set()
    for x in {s.rect.x1-ROFF for s in spawns}:
        live = [i for i, s in enumerate(spawns) if s.rect.x1-ROFF <= x <= s.rect.x2+ROFF]
        for y in {spawns[i].rect.y1-ROFF for i in live}:
            covered = frozenset(i for i in live if spawns[i].rect.y1-ROFF <= y <= spawns[i].rect.y2+ROFF)
            if len(covered) > observed_lower:
                coverages.add(covered)

    def can_peel(indices):
        pending = set(indices)
        while pending:
            left = max(spawns[i].rect.x1-ROFF for i in pending)
            top = max(spawns[i].rect.y1-ROFF for i in pending)
            right = min(spawns[i].rect.x2+ROFF for i in pending)
            bottom = min(spawns[i].rect.y2+ROFF for i in pending)
            eligible = next((i for i in pending
                if max(left, spawns[i].rect.x1-RON) <= min(right, spawns[i].rect.x2+RON)
                and max(top, spawns[i].rect.y1-RON) <= min(bottom, spawns[i].rect.y2+RON)), None)
            if eligible is None:
                return False
            pending.remove(eligible)
        return True

    examined = {}
    upper = max(map(len, coverages), default=observed_lower)
    for count in range(upper, observed_lower, -1):
        candidates = {frozenset(sub) for coverage in coverages if len(coverage) >= count
                      for sub in combinations(sorted(coverage), count)}
        examined[str(count)] = len(candidates)
        if any(can_peel(candidate) for candidate in candidates):
            return {'observed_lower': observed_lower, 'history_upper': count, 'exact': False,
                    'candidate_subsets_examined': examined}
    return {'observed_lower': observed_lower, 'history_upper': observed_lower, 'exact': True,
            'candidate_subsets_examined': examined}


def maximum_witness(maximum, terrain):
    """Find a static standable tile in a maximum plateau; no coordinate snapping."""
    for x1, y1, x2, y2 in maximum['cells']:
        points = [(x1, y1), ((x1+x2)//2, (y1+y2)//2), (x2, y2)]
        for point in points:
            if terrain.can_stand(0, *point) is True:
                return point
        for y in range(y1, y2+1):
            for x in range(x1, x2+1):
                if terrain.can_stand(0, x, y) is True:
                    return x, y
    return None


def static_path(terrain, start, goal, max_nodes=270000, bounds=None):
    """Planning only: A* on actual static edges, excluded from tick wall timing."""
    if start == goal:
        return [start]
    queue, scores, parents = [(npc_ai.distance(*start, *goal), 0, start)], {start: 0}, {}
    expanded = 0
    while queue:
        _, cost, here = heapq.heappop(queue)
        if cost != scores.get(here):
            continue
        if here == goal:
            route = [here]
            while here != start:
                here = parents[here]
                route.append(here)
            return route[::-1]
        expanded += 1
        if expanded > max_nodes:
            raise RuntimeError('BENCH_STATIC_PATH_NODE_LIMIT')
        for heading, (dx, dy) in enumerate(npc_ai.DELTAS):
            nxt = here[0]+dx, here[1]+dy
            if bounds is not None and not bounds.contains(*nxt):
                continue
            if cost+1 >= scores.get(nxt, 1 << 60):
                continue
            if terrain.can_step(0, *here, heading) is not True:
                continue
            scores[nxt], parents[nxt] = cost+1, here
            heapq.heappush(queue, (cost+1+npc_ai.distance(*nxt, *goal), cost+1, nxt))
    return None


def retention_walk(data, terrain, maximum):
    """Construct a sufficient ROFF witness while never leaving its retention intersection."""
    q = maximum_witness(maximum, terrain)
    if q is None:
        return None, {'status': 'NO_STANDABLE_MAXIMUM'}
    groups = [s for s in data.spawns if rect_distance(s.rect, *q) <= ROFF]
    box = gd.Rect(max(s.rect.x1-ROFF for s in groups), max(s.rect.y1-ROFF for s in groups),
                  min(s.rect.x2+ROFF for s in groups), min(s.rect.y2+ROFF for s in groups))
    route = [q]
    for spec in groups:
        activation = gd.Rect(max(box.x1, spec.rect.x1-RON), max(box.y1, spec.rect.y1-RON),
                             min(box.x2, spec.rect.x2+RON), min(box.y2, spec.rect.y2+RON))
        if activation.x1 > activation.x2 or activation.y1 > activation.y2:
            return None, {'status': 'SUFFICIENT_CONSTRUCTION_IMPOSSIBLE', 'first_group': spec.group_id}
        if rect_distance(spec.rect, *route[-1]) <= RON:
            continue
        point = maximum_witness({'cells': [(activation.x1, activation.y1, activation.x2, activation.y2)]}, terrain)
        path = None if point is None else static_path(terrain, route[-1], point, bounds=box)
        if path is None:
            return None, {'status': 'NO_STATIC_PATH_INSIDE_RETENTION_INTERSECTION', 'first_group': spec.group_id}
        route.extend(path[1:])
    return route, {'status': 'CONSTRUCTED_STATIC_S32_WALK', 'steps': len(route)-1,
                   'groups': len(groups), 'slots': sum(s.target_count for s in groups),
                   'retention_intersection': (box.x1, box.y1, box.x2, box.y2)}


def plan_walk(data, terrain):
    maxima, targets = {}, []
    for radius, label in ((RON, 'fresh_activation'), (ROFF, 'retention_upper_bound')):
        found = geometric_maxima(data.spawns, radius)
        maxima[label] = {'radius': radius, 'exact_integer_rectangle_overlap': True,
                        'history_attainable': True if label == 'fresh_activation' else None}
        for metric, maximum in found.items():
            point = maximum_witness(maximum, terrain)
            maxima[label][metric] = {'value': maximum['value'], 'standable_witness': point,
                                    'max_plateau_cells': len(maximum['cells'])}
            if point is not None:
                targets.append((f'{label}_{metric}', point))
    start = (32578, 32946)
    if terrain.can_stand(0, *start) is not True:
        raise ValueError('BENCH_NORMAL_START_NOT_STANDABLE')
    # Quadrants are source-coordinate waypoints; unknown/blocked sites are
    # explicitly recorded and skipped, never crossed with synthetic movement.
    targets = [('north', (32600, 32821)), ('northeast', (32702, 32841)),
               ('southeast', (32640, 33160)), ('southwest', (32350, 33120)),
               ('northwest', (32400, 32860))] + targets + [('town_return', start)]
    route, visits = [start], []
    for label, point in targets:
        if terrain.can_stand(0, *point) is not True:
            visits.append({'label': label, 'point': point, 'status': 'BLOCKED_OR_UNKNOWN'})
            continue
        path = static_path(terrain, route[-1], point)
        if path is None:
            visits.append({'label': label, 'point': point, 'status': 'UNREACHABLE_FROM_ROUTE'})
            continue
        route.extend(path[1:])
        visits.append({'label': label, 'point': point, 'status': 'VISITED', 'route_index': len(route)-1})
    retention = {}
    for metric, maximum in geometric_maxima(data.spawns, ROFF).items():
        witness, info = retention_walk(data, terrain, maximum)
        retention[metric] = info
        if witness is not None:
            connector = static_path(terrain, route[-1], witness[0])
            if connector is None:
                info['status'] = 'WITNESS_NOT_REACHABLE_FROM_ROUTE'
                continue
            route.extend(connector[1:] + witness[1:])
            info['route_index'] = len(route)-1
    return route, {'maxima': maxima, 'waypoints': visits, 'one_tile_walk_steps': len(route)-1,
                   'retention_witness': retention,
                   'pc_route_policy': 'static S32 only; PC/NPC collision and PC speed excluded'}


class ErrorLog(logging.Handler):
    """Runtime/scheduler intentionally log exceptions; make them benchmark failures."""
    def __init__(self):
        super().__init__(logging.ERROR)
        self.errors = []

    def emit(self, record):
        self.errors.append(record.getMessage() + (': '+str(record.exc_info[1]) if record.exc_info else ''))

    def check(self):
        if self.errors:
            raise RuntimeError('BENCH_CALLBACK_ERROR:'+'; '.join(self.errors[:3]))


class CheckedTerrain:
    """Do not let InterestSpawner's exception-to-unknown fallback hide failures."""
    def __init__(self, terrain):
        self.terrain, self.errors = terrain, []

    def passable(self, *args):
        try:
            return self.terrain.can_stand(*args)
        except Exception as error:
            self.errors.append(repr(error))
            raise

    def can_step(self, *args):
        return self.terrain.can_step(*args)


@dataclass
class Clock:
    now: float = 100.0

    def __call__(self):
        return self.now


class BenchWorld:
    """Pure view adapter modeled on npc_ai_range_tests and WorldView hook order."""
    def __init__(self, data, terrain, *, seed=20261026, entities=None):
        self.clock, self.errors = Clock(), ErrorLog()
        logger = logging.Logger('world_scale_bench', level=logging.ERROR)
        logger.addHandler(self.errors)
        self.runtime = WorldRuntime(clock=self.clock, entities=entities, logger=logger)
        self.entities = self.runtime.entities
        self.terrain = CheckedTerrain(terrain)
        self.spawner = InterestSpawner(self.entities, data, passable=self.terrain.passable,
                                      rng=random.Random(seed))
        self.pcs, self.moves, self.attacks = {}, 0, 0
        self.combat = SimpleNamespace(can_be_attacked=lambda uid: uid in self.pcs)
        self.ai = npc_ai.NpcAi(self, random.Random(seed+1))
        self.runtime.add_tick_hook(self.tick)

    def tick(self, now):
        self.spawner.tick(now)
        self.ai.sync(now)

    def update_pc(self, x, y):
        if self.entities.get(PC) is None:
            self.entities.add(Kind.PC, 0, x, y, uid=PC)
        else:
            self.entities.move(PC, 0, x, y)
        self.pcs[PC] = (0, x, y)
        self.spawner.update_interest(self.pcs.values(), self.clock.now)
        self.ai.sync(self.clock.now)

    def npc_step(self, entity, x, y, heading):
        self.entities.move(entity.uid, entity.map_id, x, y, heading)
        self.moves += 1

    def npc_attack(self, entity, monster, pc_uid, now):
        self.attacks += 1  # no fabricated damage/death or native packet

    def check(self):
        self.errors.check()
        if self.terrain.errors:
            raise RuntimeError('BENCH_TERRAIN_ERROR:'+self.terrain.errors[0])

    def snapshot(self):
        groups = [g for g in self.spawner.groups if g.active]
        return {'position': self.pcs.get(PC), 'active_groups': len(groups),
                'active_slots': sum(len(g.slots) for g in groups), 'brains': len(self.ai.brains),
                'registered_npcs': len(self.spawner._slots), 'entities': len(self.entities),
                'scheduler_pending': len(self.runtime.scheduler)}


class BfsMeter:
    """Separate replay only; wrappers are never used in baseline wall timing."""
    def __init__(self, world):
        self.calls = self.reached_probes = self.move_checks = self.near_queries = 0
        self.max_reached_probes, self.wall_ns = 0, 0
        self._path_depth = 0
        original_path, original_move, original_near = world.ai._path_step, world.ai._can_move, world.entities.near

        def path(entity, reached, goal):
            self.calls += 1
            probes = 0
            def count_reached(x, y):
                nonlocal probes
                probes += 1
                return reached(x, y)
            started = time.perf_counter_ns()
            self._path_depth += 1
            try:
                return original_path(entity, count_reached, goal)
            finally:
                self._path_depth -= 1
                self.wall_ns += time.perf_counter_ns()-started
                self.reached_probes += probes
                self.max_reached_probes = max(self.max_reached_probes, probes)

        def move(*args, **kwargs):
            if self._path_depth:
                self.move_checks += 1
            return original_move(*args, **kwargs)

        def near(*args, **kwargs):
            self.near_queries += 1
            return original_near(*args, **kwargs)

        world.ai._path_step, world.ai._can_move, world.entities.near = path, move, near

    def report(self):
        return {'calls': self.calls, 'reached_probes': self.reached_probes,
                'max_reached_probes_per_call': self.max_reached_probes,
                'can_move_checks': self.move_checks, 'all_registry_near_queries': self.near_queries,
                'instrumented_bfs_wall_ms': round(self.wall_ns/1e6, 3),
                'timing_scope': 'separate replay; wrappers included; not baseline tick timing'}


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, int((len(ordered)-1)*fraction))]


def timing_summary(samples):
    return {'samples': len(samples), 'p50_ms': round(percentile(samples, .5), 4),
            'p95_ms': round(percentile(samples, .95), 4),
            'p99_ms': round(percentile(samples, .99), 4), 'max_ms': round(max(samples), 4),
            'over_45ms': sum(s > BUDGET_MS for s in samples)}


async def replay(data, terrain, route, *, instrument=False, collect_timing=True, dwell_ticks=60,
                 profile_index=None):
    world = BenchWorld(data, terrain)
    meter = BfsMeter(world) if instrument else None
    ticks, moves, combined, worst, peak, peak_groups, worst_move = [], [], [], None, None, None, None
    load_intervals = {'groups': {}, 'slots': {}}
    profiler = cProfile.Profile() if profile_index is not None else None
    for index, point in enumerate(route + [route[-1]]*dwell_ticks):
        world.clock.now = 100.0 + index*TICK_S
        before_bfs = (meter.calls, meter.reached_probes, meter.move_checks, meter.wall_ns) if meter else None
        if profiler is not None and index == profile_index:
            profiler.enable()
        started = time.perf_counter_ns() if collect_timing else 0
        await world.runtime.dispatch_now(world.update_pc, *point)
        move_ms = (time.perf_counter_ns()-started)/1e6 if collect_timing else 0
        started = time.perf_counter_ns() if collect_timing else 0
        await world.runtime.tick_once()
        elapsed = (time.perf_counter_ns()-started)/1e6 if collect_timing else 0
        if profiler is not None and index == profile_index:
            profiler.disable()
        world.check()
        snap = world.snapshot()
        bfs_delta = tuple(after-before for after, before in zip(
            (meter.calls, meter.reached_probes, meter.move_checks, meter.wall_ns), before_bfs)) if meter else None
        for metric, buckets in load_intervals.items():
            bucket = buckets.setdefault(snap['active_'+metric],
                {'samples': 0, 'tick_wall': [], 'move_plus_tick_wall': [], 'bfs': [0, 0, 0, 0]})
            bucket['samples'] += 1
            if collect_timing:
                bucket['tick_wall'].append(elapsed)
                bucket['move_plus_tick_wall'].append(move_ms+elapsed)
            if bfs_delta is not None:
                bucket['bfs'] = [total+delta for total, delta in zip(bucket['bfs'], bfs_delta)]
        if peak is None or (snap['active_slots'], snap['active_groups']) > (peak['active_slots'], peak['active_groups']):
            peak = dict(snap, route_index=index)
        if peak_groups is None or snap['active_groups'] > peak_groups['active_groups']:
            peak_groups = dict(snap, route_index=index)
        if worst is None or elapsed > worst['wall_ms']:
            worst = dict(snap, route_index=index, wall_ms=elapsed)
        if worst_move is None or move_ms > worst_move['wall_ms']:
            worst_move = dict(snap, route_index=index, wall_ms=move_ms)
        if collect_timing:
            ticks.append(elapsed)
            moves.append(move_ms)
            combined.append(move_ms+elapsed)
    result = {'observed_peak_with_hysteresis': peak, 'final': world.snapshot(),
              'observed_peak_groups_with_hysteresis': peak_groups,
              'npc_moves': world.moves, 'npc_attacks_recorded': world.attacks,
              'fake_seconds': round((len(route)+dwell_ticks)*TICK_S, 2),
              'hook_order': 'dispatch update_interest+ai.sync; tick scheduler.run_due -> spawner.tick -> ai.sync',
              'worst_tick': worst, 'worst_move_dispatch': worst_move}
    if collect_timing:
        result.update(tick_wall=timing_summary(ticks), move_dispatch_wall=timing_summary(moves),
                      move_plus_tick_wall=timing_summary(combined))
    result['maximum_load_intervals'] = {}
    for metric, buckets in load_intervals.items():
        value = max(buckets)
        bucket = buckets[value]
        summary = {'active_'+metric: value, 'samples': bucket['samples']}
        if collect_timing:
            summary.update(tick_wall=timing_summary(bucket['tick_wall']),
                           move_plus_tick_wall=timing_summary(bucket['move_plus_tick_wall']))
        if meter:
            calls, probes, checks, wall_ns = bucket['bfs']
            summary['bfs'] = {'calls': calls, 'reached_probes': probes, 'can_move_checks': checks,
                             'instrumented_bfs_wall_ms': round(wall_ns/1e6, 3),
                             'scope': 'sum of dispatch+tick BFS deltas in this maximum-load interval; separate instrumented replay'}
        result['maximum_load_intervals']['max_active_'+metric] = summary
    if meter:
        result['bfs'] = meter.report()
    if profiler is not None:
        result['profile'] = profile_summary(profiler)
    return result


class OpenTerrain:
    """Synthetic stress only: infinite known open plane, not a client map."""
    def can_stand(self, *args):
        return True

    def can_step(self, *args):
        return True


async def bfs_burst(data, position, *, instrument=False, approach=None, profiler=None):
    """One synchronized, unreachable-goal search per real active NPC.

    Catalog counts/rectangles and real slot ownership are kept. Synthetic open
    terrain maximizes the searchable window; reached=False deliberately exhausts
    it. Direct searches scheduled together isolate path cost, not real combat.
    All callbacks still run through WorldRuntime.tick_once and real Scheduler.
    """
    world = BenchWorld(data, OpenTerrain())
    for point in approach or [position]:
        world.update_pc(*point)
    meter = BfsMeter(world) if instrument else None
    completed, headings = [], Counter()
    for brain in world.ai.brains.values():
        world.runtime.scheduler.cancel(brain.handle)
        entity = world.entities.get(brain.uid)
        def search(now, entity=entity):
            heading = world.ai._path_step(entity, lambda x, y: False, (entity.x+50, entity.y))
            headings[str(heading)] += 1
            completed.append(entity.uid)
        world.runtime.scheduler.schedule(world.clock.now, brain.ref, 'bench_unreachable_bfs', search)
    expected = len(world.ai.brains)
    if profiler is not None:
        profiler.enable()
    started = time.perf_counter_ns()
    await world.runtime.tick_once()
    wall = (time.perf_counter_ns()-started)/1e6
    if profiler is not None:
        profiler.disable()
    world.check()
    if len(completed) != expected or expected == 0:
        raise RuntimeError('BENCH_BFS_BURST_NOT_EXERCISED')
    result = {'scope': 'SYNTHETIC: scheduled direct BFS, unreachable predicate, open plane; not gameplay',
              'snapshot': world.snapshot(), 'completed_bfs': len(completed), 'headings': dict(headings),
              'tick_wall_ms': round(wall, 4), 'over_45ms': wall > BUDGET_MS}
    if meter:
        result['bfs'] = meter.report()
    return result


def profile_summary(profiler):
    rows = []
    for (file, line, name), (cc, nc, own, cumulative, callers) in pstats.Stats(profiler).stats.items():
        if 'local_original_session' in file:
            rows.append({'function': f'{Path(file).name}:{name}:{line}', 'calls': nc,
                         'own_ms': round(own*1000, 3), 'cumulative_ms': round(cumulative*1000, 3)})
    return {'scope': 'separate cProfile replay of measured dispatch/tick only; excluded from baseline',
            'top_cumulative': sorted(rows, key=lambda r: r['cumulative_ms'], reverse=True)[:5]}


async def benchmark(*, catalog=CATALOG, map_root=DEFAULT_MAP_ROOT):
    data, catalog_info = load_catalog(catalog)
    setup_started = time.perf_counter_ns()
    terrain = WorldTerrain.load(map_root, (0,))  # Missing S32 is an explicit failure.
    load_ms = (time.perf_counter_ns()-setup_started)/1e6
    setup_started = time.perf_counter_ns()
    # _pc_ok imports this pure module lazily. Production broker already imports
    # it at startup; isolate that cold import rather than charge a random PC step.
    from tools.local_original_session import world_visibility  # noqa: F401
    import_ms = (time.perf_counter_ns()-setup_started)/1e6
    setup_started = time.perf_counter_ns()
    route, route_info = plan_walk(data, terrain)
    plan_ms = (time.perf_counter_ns()-setup_started)/1e6
    baseline = await replay(data, terrain, route)
    group_bound = reachable_group_bound(data.spawns,
        baseline['observed_peak_groups_with_hysteresis']['active_groups'])
    slot_upper = route_info['maxima']['retention_upper_bound']['slots']['value']
    route_info['maximum_active_groups'] = group_bound
    route_info['maximum_active_slots'] = {
        'observed_lower': baseline['observed_peak_with_hysteresis']['active_slots'],
        'history_upper': slot_upper,
        'exact': baseline['observed_peak_with_hysteresis']['active_slots'] == slot_upper}
    measured = await replay(data, terrain, route, instrument=True, collect_timing=False)
    # Memory replay starts before loading terrain and creating a world. Baseline
    # timing did not run under tracemalloc; imports/catalog parsing are excluded.
    tracemalloc.start()
    try:
        memory_terrain = WorldTerrain.load(map_root, (0,))
        memory_result = await replay(data, memory_terrain, route, collect_timing=False)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    for replayed in (measured, memory_result):
        if (replayed['final'], replayed['npc_moves'], replayed['npc_attacks_recorded']) != (
                baseline['final'], baseline['npc_moves'], baseline['npc_attacks_recorded']):
            raise RuntimeError('BENCH_INSTRUMENTED_REPLAY_DIVERGED')
    observed = baseline['observed_peak_with_hysteresis']
    position = observed['position'][1:]
    approach = route[:min(observed['route_index']+1, len(route))]
    burst = await bfs_burst(data, position, approach=approach)
    burst_meter = await bfs_burst(data, position, instrument=True, approach=approach)
    profile = None
    if burst['over_45ms']:
        profiler = cProfile.Profile()
        await bfs_burst(data, position, approach=approach, profiler=profiler)
        profile = profile_summary(profiler)
    findings = []
    if burst['over_45ms']:
        findings.append({'scenario': 'synthetic_unreachable_bfs_burst', 'position': (0, *position),
            'active_slots': burst['snapshot']['active_slots'], 'wall_ms': burst['tick_wall_ms'],
            'slow_stage': 'world_scheduler.py:Scheduler.run_due -> npc_ai.py:NpcAi._path_step',
            'cause': 'one full bounded BFS per active NPC becomes due in the same scheduler drain',
            'minimal_followup': 'NOT IMPLEMENTED: evaluate staggered deadlines or bounded path work; these can change action latency and need separate design/verification'})
    for stage, sample, summary in (('tick', baseline['worst_tick'], baseline['tick_wall']),
                                   ('move_dispatch', baseline['worst_move_dispatch'], baseline['move_dispatch_wall'])):
        if summary['over_45ms']:
            profiled = await replay(data, terrain, route[:sample['route_index']+1], collect_timing=False,
                                    dwell_ticks=0, profile_index=sample['route_index'])
            findings.append({'scenario': 'static_s32_walk_'+stage, **sample,
                             'slow_stage': profiled['profile'],
                             'cause': 'see isolated replay profile; host scheduling noise is not excluded',
                             'minimal_followup': 'change only the identified hot function if the isolated cost reproduces'})
    return {'kind': 'BACKEND_SCALE_MEASUREMENT_NOT_GAMEPLAY_PASS', 'tick_ms': 150,
            'budget_ms': BUDGET_MS, 'catalog': catalog_info,
            'setup_excluded_from_ticks': {'terrain_load_ms': round(load_ms, 3),
                'world_visibility_cold_import_ms': round(import_ms, 3), 'route_plan_ms': round(plan_ms, 3)},
            'terrain': {'kind': 'ACTUAL_CLIENT_S32_STATIC_MASK1', 'root': str(map_root),
                        'chunks': len(terrain.sources), 'bounds': terrain.bounds(0)},
            'walk': route_info, 'baseline': baseline,
            'bfs_separate_walk_replay': dict(measured['bfs'],
                maximum_load_intervals=measured['maximum_load_intervals']),
            'memory_separate_replay': {'current_bytes': current, 'peak_bytes': peak,
                'scope': 'tracemalloc Python allocations: new S32 terrain+world+walk, excludes process RSS/imports/catalog',
                'final': memory_result['final']},
            'synthetic_bfs_burst': burst, 'synthetic_bfs_separate_instrumentation': burst_meter['bfs'],
            'profile_separate_replay': profile, 'over_budget_findings': findings,
            'limits': ['30 catalog identities are candidates; unresolved IDs are local bench identities',
                       'No broker, frames, combat arithmetic, recovery, persistence, client or network measured',
                       'Raw ROFF overlap is only a ceiling; maximum_active_groups tightens it using activation-history feasibility',
                       'Walking uses static S32 edges; dynamic PC collision and authentic player speed are excluded']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--map-root', type=Path, default=DEFAULT_MAP_ROOT)
    args = parser.parse_args()
    try:
        report = asyncio.run(benchmark(catalog=args.catalog, map_root=args.map_root))
    except Exception as error:
        print(json.dumps({'kind': 'BENCH_FAILED', 'error': f'{type(error).__name__}: {error}'}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
