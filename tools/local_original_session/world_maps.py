"""Pure local-policy stair candidates for Talking Island maps 0/1/2.

The four triggers are LOCAL policy, not native stair observations. The map0
source is adjusted to the reachable client S32 cell at (32478,32851); the
blocked L1J cell (32477,32851) remains recorded as reference_origin.
Source: work/local_original_session/game-core-prep/M3_DUNGEON_DATA.md,
"Dungeon entrance / floor transition evidence" section. Existing run273 and
run287 contracts establish only general packet handling, not these triggers.
Native teleport-book map0 (32477, 32853) is a destination, not an entry trigger;
lucas2 map0 (32478, 32853) is an unconfirmed destination candidate.
This module changes no state and emits no packets.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
import json
from pathlib import Path
import random

from tools.local_original_session.game_data import Rect


@dataclass(frozen=True)
class MapDestination:
    map_id: int
    x: int
    y: int
    heading: int


@dataclass(frozen=True)
class GetBackRule:
    map_id: int
    area: Rect | None
    points: tuple[MapDestination, ...]
    town_id: int
    elf_town_id: int
    ref: str


@dataclass(frozen=True)
class GetBackPolicy:
    """Startup-loaded L1J reference policy, limited to selected client maps.

    SQL area_x1 descending precedence and inclusive rectangles matter at
    overlapping boundaries. Town pools override the SQL point triplet.
    """
    rules: tuple[GetBackRule, ...]
    towns: Mapping[int, tuple[MapDestination, ...]]
    fallback: MapDestination | None
    supported_classes: tuple[int, ...]

    def candidates_for(self, map_id, x, y, character_class=None):
        if character_class is not None and character_class not in self.supported_classes:
            raise ValueError('GETBACK_UNSUPPORTED_CHARACTER_CLASS')
        rules = tuple(rule for rule in self.rules if rule.map_id == map_id)
        if not rules:
            return ()
        rule = next((rule for rule in rules if rule.area is None or rule.area.contains(x, y)), None)
        if rule is None:
            # Java has no matched-area fallback. This explicit LOCAL extension
            # uses its missing-map fallback, rather than inventing coordinates.
            return () if self.fallback is None else (self.fallback,)
        town_id = rule.elf_town_id if character_class == 2 and rule.elf_town_id else rule.town_id
        return self.towns.get(town_id, ()) if town_id else rule.points

    def return_for(self, map_id, x, y, character_class=None, *, rng=None):
        candidates = self.candidates_for(map_id, x, y, character_class)
        if candidates:
            return (rng or random).choice(candidates)
        if any(rule.map_id == map_id for rule in self.rules):
            raise ValueError('GETBACK_KNOWN_DESTINATION_REQUIRED')
        return None


def load_getback_policy(path, *, can_stand=None):
    """Read selected source rows once; optionally exclude unknown/blocked S32 cells.

    Filtering never substitutes new coordinates. Empty source pools stay empty
    so an admitted caller can refuse before consumption instead of teleporting
    to an unrelated legacy destination.
    """
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    def points(rows):
        candidates = (MapDestination(*row) for row in rows)
        return tuple(point for point in candidates if can_stand is None
                     or can_stand(point.map_id, point.x, point.y) is True)
    rules = tuple(GetBackRule(row['map_id'],
        None if row['area'] is None else Rect(*row['area']),
        points(row['points']), row['town_id'], row['elf_town_id'], row['ref'])
        for row in sorted(document['rules'], key=lambda row: (row['map_id'],
                            -(row['area'][0] if row['area'] else 0))))
    towns = MappingProxyType({row['town_id']: points(row['points']) for row in document['towns']})
    fallback = points([document['unmatched_area_fallback']['destination']])
    return GetBackPolicy(rules, towns, fallback[0] if fallback else None,
                         tuple(document['supported_classes']))


@dataclass(frozen=True)
class MapTransition:
    destination: MapDestination
    ref: str
    source: str = 'local_policy/l1j'
    native_trigger_status: str = 'UNKNOWN'
    reference_origin: tuple[int, int, int] | None = None
    local_basis: str | None = None


_SQL = 'D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql'

# The native entrance destinations are vicinity evidence, not trigger evidence.
# This reachable cell is one east of the L1J source and two north of the
# lucas2 destination candidate. S32 permits heading0 from (32478,32852).
TRANSITIONS: Mapping[tuple[int, int, int], MapTransition] = MappingProxyType({
    (0, 32478, 32851): MapTransition(MapDestination(1, 32669, 32802, 4), f'{_SQL}:14930',
        source='local_policy/client_s32+l1j', reference_origin=(0, 32477, 32851),
        local_basis='map0 S32 mask1: can_stand=True, step(32478,32852,0)=True; '
                    'travel_review/entermap-data-candidates.json:/1 supplies entrance vicinity only'),
    (1, 32669, 32802): MapTransition(MapDestination(0, 32477, 32853, 4), f'{_SQL}:15088'),
    (1, 32737, 32877): MapTransition(MapDestination(2, 32665, 32789, 4), f'{_SQL}:15535'),
    (2, 32665, 32788): MapTransition(MapDestination(1, 32738, 32877, 2), f'{_SQL}:15074'),
})


def resolve_transition(map_id: int, x: int, y: int, *, extra=None) -> MapDestination | None:
    """Return the exact candidate destination, or None for any other cell."""
    if any(type(value) is not int for value in (map_id, x, y)):
        return None
    transition = TRANSITIONS.get((map_id, x, y))
    if transition is None and extra is not None:
        transition = extra.get((map_id, x, y))
    return None if transition is None else transition.destination


@dataclass(frozen=True)
class DungeonPolicy:
    """Startup-loaded LOCAL extension; no request-time file access."""
    maps: tuple[int, ...]
    transitions: Mapping[tuple[int, int, int], MapTransition]
    returns: Mapping[int, MapDestination]

    def return_for(self, map_id: int) -> MapDestination | None:
        return self.returns.get(map_id)


def load_dungeon_policy(directory: str | Path | None = None) -> DungeonPolicy:
    directory = Path(__file__).resolve().parent / 'data/m6' if directory is None else Path(directory)
    maps = json.loads((directory / 'maps.json').read_text(encoding='utf-8'))
    travel = json.loads((directory / 'transitions.json').read_text(encoding='utf-8'))
    returns = json.loads((directory / 'returns.json').read_text(encoding='utf-8'))
    expansion = json.loads((directory / 'map_expansion2.json').read_text(encoding='utf-8'))
    expansion3 = json.loads((directory / 'map_expansion3.json').read_text(encoding='utf-8'))
    expansion4 = json.loads((directory / 'map_expansion4.json').read_text(encoding='utf-8'))
    ice = json.loads((directory / 'ice_cave.json').read_text(encoding='utf-8'))
    expansion5 = json.loads((directory / 'map_expansion5.json').read_text(encoding='utf-8'))
    expansion6 = json.loads((directory / 'map_expansion6.json').read_text(encoding='utf-8'))
    talkscroll_maps = json.loads((directory / 'talkscroll_maps.json').read_text(encoding='utf-8'))
    maps['maps'] += expansion['maps']
    travel['transitions'] += expansion['transitions']
    returns['returns'] += expansion['returns']
    maps['maps'] += expansion3['maps']
    travel['transitions'] += expansion3['transitions']
    returns['returns'] += expansion3['returns']
    maps['maps'] += expansion4['maps']
    travel['transitions'] += expansion4['transitions']
    returns['returns'] += expansion4['returns']
    maps['maps'] += ice['maps']
    travel['transitions'] += ice['transitions']
    returns['returns'] += ice['returns']
    maps['maps'] += expansion5['maps']
    travel['transitions'] += expansion5['transitions']
    returns['returns'] += expansion5['returns']
    maps['maps'] += expansion6['maps']
    travel['transitions'] += expansion6['transitions']
    returns['returns'] += expansion6['returns']
    maps['maps'] += talkscroll_maps['maps']
    # These two sourced quest interiors are prepared separately. They must not
    # enter the live policy before their canonical current-client S32 exists:
    # dungeon initialize preloads every admitted map. Test/extraction output is
    # deliberately not a runtime resource fallback.
    from tools.local_original_session.world_terrain import DEFAULT_MAP_ROOT
    knight = json.loads((directory / 'knight_maps.json').read_text(encoding='utf-8'))
    available = {row['map_id']['value'] for row in knight['maps']
                 if any((DEFAULT_MAP_ROOT / str(row['map_id']['value'])).glob('*.s32'))}
    maps['maps'] += [row for row in knight['maps'] if row['map_id']['value'] in available]
    travel['transitions'] += [row for row in knight['transitions']
                             if ({row['origin'][0], row['destination'][0]} & {3, 237}) <= available]
    returns['returns'] += [row for row in knight['returns'] if row['map_id'] in available]
    transitions = {tuple(row['origin']): MapTransition(
        MapDestination(*row['destination']), row['ref'], row['source'],
        row['native_trigger_status'], tuple(row['reference_origin']), row['local_basis'])
        for row in travel['transitions']}
    return DungeonPolicy(tuple(row['map_id']['value'] for row in maps['maps']),
        MappingProxyType(transitions), MappingProxyType({row['map_id']:
            MapDestination(*row['destination']) for row in returns['returns']}))


@dataclass(frozen=True)
class BoatRoute:
    route_id: str
    source_map: int
    dock: Rect
    ticket_id: int
    destination: MapDestination
    ref: str


@dataclass(frozen=True)
class GludinPolicy:
    town_return: MapDestination
    boats: tuple[BoatRoute, ...]

    def boat_at(self, map_id: int, x: int, y: int) -> BoatRoute | None:
        return next((route for route in self.boats
                     if route.source_map == map_id and route.dock.contains(x, y)), None)


def load_gludin_policy(directory: str | Path | None = None) -> GludinPolicy:
    """Read attributed travel plus explicit LOCAL choices once at startup.

    MapExp2 uses a direct harbor transfer: no map5/6, timetable, random radius
    or invented 4F0E. 4EF8.f1 stays opaque; it is NOT a ShipInfo/ticket/map key.
    The native official enter/arrival/consumption contract remains UNKNOWN.
    """
    directory = Path(__file__).resolve().parent / 'data/m4' if directory is None else Path(directory)
    policy = json.loads((directory / 'local_policy.json').read_text(encoding='utf-8'))
    travel = json.loads((directory / 'travel.json').read_text(encoding='utf-8'))
    point = policy['town_return']['value']
    routes = []
    for row in travel['boat_routes']:
        box = row['classic_static']['f6_box_raw']
        arrival = next(p for p in row['destination_candidates'] if p['source_kind'] == 'classic_static_raw')
        routes.append(BoatRoute(row['route_id'], row['source_map_id'],
            Rect(box['1'][0], box['2'][0], box['3'][0], box['4'][0]),
            row['ticket']['classic_item_id'],
            MapDestination(arrival['map_id'], arrival['x'], arrival['y'], 5),
            arrival['source_ref']))
    return GludinPolicy(MapDestination(point['map_id'], point['x'], point['y'], point['heading']),
                        tuple(routes))
