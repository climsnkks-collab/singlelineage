"""Talking-scroll LOCAL policy and transient selection; no IO while selecting.

The item identities and native groups are client catalog values. The official
beginner guide establishes unlimited uses for talking scrolls; Classic12163's
non-consuming behavior is a separate LOCAL policy. Exact expiration dates are unknown.
Menu fallback, stacking and absence of a level restriction are LOCAL choices.
Native TeleportBook UI/list operands are not inferred by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType

from tools.local_original_session.world_maps import MapDestination

TABLE = Path(__file__).resolve().parent / 'data/m2/talkscroll.json'


@dataclass(frozen=True)
class Catalog:
    items: object
    pages: object
    initial_page: str
    destinations: object
    native_destinations: object
    rows: tuple

    def destination_for_native(self, template_id, ordinal):
        """Resolve the item's own client group; ordinals never cross groups."""
        item = self.items.get(template_id)
        if item is None:
            return None
        return self.native_destinations.get(item['native_group'], {}).get(ordinal)


@dataclass
class Selection:
    pc_uid: int
    item_uid: int
    template_id: int
    origin: tuple[int, int, int]
    page: str
    delivered: bool = False


def load_catalog(path=TABLE):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    items = MappingProxyType({row['template_id']: MappingProxyType(row) for row in raw['items']})
    pages = MappingProxyType({page['stem']: MappingProxyType(page) for page in raw['pages']})
    destinations = {row['action']: MapDestination(
        row['map_id'], row['x'], row['y'], row['heading']) for row in raw['destinations']}
    # Reuse the current original table's complete group; retain zero-based
    # ordinals including heading rows, which are not selectable destinations.
    native_destinations = {}
    for row in raw['native_destinations']:
        if row['is_heading']:
            continue
        destination = MapDestination(
            row['f1_signed_destination_key'], row['f2_x_candidate'], row['f3_y_candidate'], 0)
        native_destinations.setdefault(row['group_id'], {})[row['ordinal']] = destination
        # Preserve the existing group10 API for older catalog consumers.
        if row['group_id'] == raw['native_group']:
            destinations['native:' + str(row['ordinal'])] = destination
    destinations = MappingProxyType(destinations)
    native_destinations = MappingProxyType({group: MappingProxyType(points)
        for group, points in native_destinations.items()})
    return Catalog(items, pages, raw['initial_page'], destinations, native_destinations,
                   tuple(MappingProxyType(row) for row in raw['native_destinations']))


def destination_status(row, *, serves_map, terrain):
    """Classify an unchanged original row using the current server owners.

    UI/item availability is deliberately separate from map/tile eligibility.
    This adds no destination, fallback coordinate or request-time file IO.
    """
    if row['is_heading']:
        return 'heading'
    map_id = row['f1_signed_destination_key']
    if not serves_map(map_id):
        return 'map_not_served'
    stand = terrain.can_stand(map_id, row['f2_x_candidate'], row['f3_y_candidate'])
    return 'open' if stand is True else ('coordinate_blocked' if stand is False
                                       else 'coordinate_data_missing')


def select(catalog, selection, *, pc_uid, target_uid, action, origin,
           owned_template, owned_count):
    """Return (next page, destination); cancellation returns (None, None)."""
    if (selection is None or not selection.delivered or selection.pc_uid != pc_uid
            or selection.item_uid != target_uid or selection.origin != origin
            or owned_template != selection.template_id or owned_count <= 0):
        raise ValueError('TALKSCROLL_CURRENT_OWNED_MENU_REQUIRED')
    if action in ('cancel', 'close'):
        return None, None
    page = catalog.pages[selection.page]
    if action not in page['actions']:
        raise ValueError('TALKSCROLL_ACTION_NOT_LISTED')
    next_page = page.get('links', {}).get(action)
    if next_page is not None:
        return next_page, None
    destination = catalog.destinations.get(action)
    if destination is None:
        raise ValueError('TALKSCROLL_DESTINATION_UNAVAILABLE')
    return None, destination
