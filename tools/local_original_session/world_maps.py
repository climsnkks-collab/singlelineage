"""Pure local-policy stair candidates for Talking Island maps 0/1/2.

The four triggers are L1J reference policy, not native stair observations.
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


@dataclass(frozen=True)
class MapDestination:
    map_id: int
    x: int
    y: int
    heading: int


@dataclass(frozen=True)
class MapTransition:
    destination: MapDestination
    ref: str
    source: str = 'local_policy/l1j'
    native_trigger_status: str = 'UNKNOWN'


_SQL = 'D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql'

# Exact source cells and asymmetric returns are deliberately explicit.
TRANSITIONS: Mapping[tuple[int, int, int], MapTransition] = MappingProxyType({
    (0, 32477, 32851): MapTransition(MapDestination(1, 32669, 32802, 4), f'{_SQL}:14930'),
    (1, 32669, 32802): MapTransition(MapDestination(0, 32477, 32853, 4), f'{_SQL}:15088'),
    (1, 32737, 32877): MapTransition(MapDestination(2, 32665, 32789, 4), f'{_SQL}:15535'),
    (2, 32665, 32788): MapTransition(MapDestination(1, 32738, 32877, 2), f'{_SQL}:15074'),
})


def resolve_transition(map_id: int, x: int, y: int) -> MapDestination | None:
    """Return the exact candidate destination, or None for any other cell."""
    if any(type(value) is not int for value in (map_id, x, y)):
        return None
    transition = TRANSITIONS.get((map_id, x, y))
    return None if transition is None else transition.destination
