"""Static client-map tile passability (map S32 mask1) for world spawn and NPC moves.

Source bytes: current client ``map/<id>/<sx><sy>.s32`` chunks materialized
unchanged by the existing AssetProvider (``tools/local_resource_provider``
``save``) under ``work/local_resource_provider/assets/map``. Each chunk covers
64x64 cells; after the floor table (64 rows x 128 halves x 4 bytes) and the
decoration list (u16 count, 6 bytes each) it stores 64x64 cells of two uint16
half flags (half0, half1), the same layout as the S32 parse in
tools/source_scene_assets/scene_assets.cpp:41 (``Cell.attributes[2]``, .hpp:11).

Move rule (static mask1 only, same as tools/source_scene_rules/scene_rules.cpp
probes/tile_gate and the live-memory reader
tools/local_tile_passability_budget/inspect_tile.py probe_cells/flag_blocked):
probes are original type4 half-coordinates ``2*x + ox, y + oy`` read from cell
``(hx >> 1, y)`` half ``hx & 1``; bit 0x1 set means that edge is blocked.
Even headings read one probe; odd headings read A,B,C,D and are blocked when
``(A|B)&(C|D)`` (1, 5) or ``(A|C)&(B|D)`` (3, 7). This is NOT the L1J byte map
(set = allowed). Actor occupancy, doors, map overrides and full original
navigation are outside this module.

``can_stand`` is a local policy derived from that rule: the mask1 flags are edge
flags with no per-cell stand bit, so a loaded cell counts as standable when at
least one of its eight one-step moves is clear.
"""
from __future__ import annotations

from array import array
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_ROOT = ROOT / 'work/local_resource_provider/assets/map'
DEFAULT_MAP_IDS = (0,)
LAZY_MAP_IDS = (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
                19, 20, 21, 43, 44, 45, 46, 47, 48, 49, 50, 51)

# Heading deltas (0 = y-1, clockwise), scene_rules.cpp deltas / authority.DELTAS.
DELTAS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
# Original type4 half-coordinate probe offsets (scene_rules.cpp even/odd).
EVEN = ((0, 0), (1, 0), (0, 1), (-1, 0))
ODD = (((1, -1), (1, 0), (-1, 0), (-1, -1)),
       ((0, 0), (0, 1), (-2, 1), (-2, 0)),
       ((2, 0), (2, 1), (0, 1), (0, 0)),
       ((1, 0), (1, 1), (-1, 1), (-1, 0)))
MASK_MOVE = 0x1

SEGMENT_BASE = 0x7e00
CHUNK = 64
FLOOR_BYTES = CHUNK * 2 * CHUNK * 4
FLAG_COUNT = CHUNK * CHUNK * 2


def _probe_offsets(heading: int):
    if heading % 2 == 0:
        return (EVEN[heading // 2],)
    return tuple(row[heading // 2] for row in ODD)


def parse_s32_flags(data: bytes) -> array:
    """Return the chunk's 64x64x2 uint16 half flags (row-major y, x, half)."""
    if len(data) < FLOOR_BYTES + 2:
        raise ValueError('S32_TRUNCATED_FLOOR')
    decorations = int.from_bytes(data[FLOOR_BYTES:FLOOR_BYTES + 2], 'little')
    start = FLOOR_BYTES + 2 + decorations * 6
    end = start + FLAG_COUNT * 2
    if len(data) < end:
        raise ValueError('S32_TRUNCATED_FLAGS')
    flags = array('H')
    flags.frombytes(data[start:end])
    if sys.byteorder != 'little':
        flags.byteswap()
    return flags


class WorldTerrain:
    """Read-only per-map flags; optional lazy maps load on their first query."""

    def __init__(self, chunks: dict[int, dict[tuple[int, int], array]], sources: tuple[str, ...] = (),
                 *, root: Path | None = None, lazy_map_ids=()):
        self._chunks = chunks
        self.sources = sources
        self._root = root
        self._lazy_map_ids = frozenset(lazy_map_ids)
        self._load_lock = threading.Lock()

    @staticmethod
    def _load_map(root: Path, map_id: int):
        folder = root / str(map_id)
        loaded: dict[tuple[int, int], array] = {}
        sources = []
        for path in sorted(folder.glob('*.s32')):
            stem = path.stem
            if len(stem) != 8:
                raise ValueError(f'S32_NAME:{path.name}')
            key = (int(stem[:4], 16) - SEGMENT_BASE, int(stem[4:], 16) - SEGMENT_BASE)
            loaded[key] = parse_s32_flags(path.read_bytes())
            sources.append(f'{map_id}/{path.name}')
        if not loaded:
            raise FileNotFoundError(f'WORLD_TERRAIN_NO_S32:{folder}')
        return loaded, tuple(sources)

    @classmethod
    def load(cls, root: Path | str = DEFAULT_MAP_ROOT, map_ids=DEFAULT_MAP_IDS,
             *, lazy_map_ids=()) -> 'WorldTerrain':
        """Load requested maps now; optional lazy maps use the same S32 parser.

        Missing or malformed requested assets raise, including on a lazy map's
        first query. Maps not requested and cells outside chunks answer None.
        """
        root = Path(root)
        chunks: dict[int, dict[tuple[int, int], array]] = {}
        sources = []
        for map_id in map_ids:
            loaded, map_sources = cls._load_map(root, map_id)
            chunks[map_id] = loaded
            sources.extend(map_sources)
        return cls(chunks, tuple(sources), root=root, lazy_map_ids=lazy_map_ids)

    def _map_chunks(self, map_id: int):
        loaded = self._chunks.get(map_id)
        if loaded is not None or map_id not in self._lazy_map_ids:
            return loaded
        with self._load_lock:
            loaded = self._chunks.get(map_id)
            if loaded is None:
                loaded, sources = self._load_map(self._root, map_id)
                self._chunks[map_id] = loaded
                self.sources += sources
            return loaded

    # ---- raw -------------------------------------------------------------
    def flag(self, map_id: int, x: int, y: int, half: int) -> int | None:
        if x < 0 or y < 0:
            return None
        chunks = self._chunks.get(map_id)
        if chunks is None:
            chunks = self._map_chunks(map_id)
        chunk = None if chunks is None else chunks.get((x >> 6, y >> 6))
        if chunk is None:
            return None
        return chunk[(((y & 63) << 6) | (x & 63)) * 2 + half]

    def half_flags(self, map_id: int, x: int, y: int) -> tuple[int, int] | None:
        first = self.flag(map_id, x, y, 0)
        return None if first is None else (first, self.flag(map_id, x, y, 1))

    def loaded(self, map_id: int, x: int, y: int) -> bool:
        return self.flag(map_id, x, y, 0) is not None

    def bounds(self, map_id: int) -> tuple[int, int, int, int] | None:
        """Inclusive cell bounding box of loaded chunks (may contain gaps)."""
        keys = self._map_chunks(map_id)
        if not keys:
            return None
        xs = [k[0] for k in keys]
        ys = [k[1] for k in keys]
        return min(xs) * CHUNK, min(ys) * CHUNK, max(xs) * CHUNK + CHUNK - 1, max(ys) * CHUNK + CHUNK - 1

    # ---- rules -----------------------------------------------------------
    def edge_blocked(self, map_id: int, x: int, y: int, heading: int, mask: int = MASK_MOVE) -> bool | None:
        """Original static probe combination for one step; None if any probe is unloaded."""
        if type(heading) is not int or not 0 <= heading < 8:
            return None
        bits = []
        for ox, oy in _probe_offsets(heading):
            hx = 2 * x + ox
            value = self.flag(map_id, hx >> 1, y + oy, hx & 1)
            if value is None:
                return None
            bits.append(bool(value & mask))
        if len(bits) == 1:
            return bits[0]
        a, b, c, d = bits
        if heading in (3, 7):
            return (a or c) and (b or d)
        return (a or b) and (c or d)

    def can_step(self, map_id: int, x: int, y: int, heading: int) -> bool | None:
        """One-cell move from (x, y) by heading under static mask1; None = no data."""
        if type(heading) is not int or not 0 <= heading < 8:
            return None
        dx, dy = DELTAS[heading]
        if not self.loaded(map_id, x, y) or not self.loaded(map_id, x + dx, y + dy):
            return None
        blocked = self.edge_blocked(map_id, x, y, heading)
        return None if blocked is None else not blocked

    def can_stand(self, map_id: int, x: int, y: int) -> bool | None:
        """Local policy: loaded and at least one clear one-step move; None = no data."""
        if not self.loaded(map_id, x, y):
            return None
        unknown = False
        for heading in range(8):
            step = self.can_step(map_id, x, y, heading)
            if step is True:
                return True
            unknown = unknown or step is None
        return None if unknown else False

    def passable(self, map_id: int, x: int, y: int) -> bool | None:
        """InterestSpawner placement callback (only ``True`` places)."""
        return self.can_stand(map_id, x, y)


_default: WorldTerrain | None = None
_default_lock = threading.Lock()


def default_terrain() -> WorldTerrain:
    """Process-wide map0 terrain; supported extra maps may be preloaded at startup."""
    global _default
    with _default_lock:
        if _default is None:
            _default = WorldTerrain.load(lazy_map_ids=LAZY_MAP_IDS)
        return _default
