"""Opt-in original-client Monster spawn; no default actor or gameplay rules.

All wire values are caller-supplied local policy. In particular, NPC table f2
never supplies appearance. Only the independently verified SPR56/template0
pair is admitted by this first connection. No HP, AI or interaction is implied.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from tools.local_game_session import session

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'EXPLICIT_LOCAL_MONSTER_SPAWN'
# World interest spawn (world_visibility): same Actor format for the M1 table's
# (sprite f3, template f39) pairs. Each SPR carries 1002.type(10) like SPR56
# (SPR_PATH sprite_id 33/56/57/1022) and each native npc row id has f2=sprite
# (NPC_PATH npc 0->56, 1->57, 8->33, 245->1022); run22 findings.md:17 admits
# SPR selector 5/10 with f16=false, f21='' and f39>=0 as the Monster subset.
WORLD_POLICY = 'LOCAL_M1_WORLD_MONSTER_SPAWN'
WORLD_MONSTERS = frozenset({(56, 0), (57, 1), (1022, 245), (33, 8)})
# Existing data/m3/monsters.json selected client f2/SPR pairs. Enabled maps
# remain owned by the broker's explicit MapExp2 path; default spawn stays map0.
DUNGEON_MONSTERS = frozenset({(52, 27), (29, 11), (30, 29), (1096, 276), (49, 6), (145, 30)})
REQUIRED = frozenset(range(1, 25)) | {27, 28}
FIELDS = REQUIRED | {39}
MAX_SPAWNS = 1  # First NPC only; no inferred visibility/streaming policy.
SPR_PATH = ROOT / 'work/asset_link_audit_20261007/sprite/current-parsed.jsonl'
SPR_SHA = 'bd09ad5344d2fab1db2086c63f098fc2d7fb12e7750527fe93e74d48e35d7bcc'
NPC_PATH = ROOT / 'work/source_game_data/native-dump-v1.jsonl'
NPC_SHA = 'a4a188ce02054beb0ab429dff32fe7affe00a930eb78bf7d9bd223b21eb721a9'
# Reviewed fixed CONTROL source: 1002.type -> SPR payload+5C and the
# f16/f39/f21 dispatch predicates. This does not establish current runtime parity.
DISPATCH_PATH = ROOT / 'work/local_server_rea_20261016/run22_npc_spawn/source-evidence.json'
DISPATCH_SHA = 'dde6967e27ce05e96aea719c40e4ab935415eb242f5a0528d9a649d606473c5f'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _pinned(path, digest):
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == digest, 'NPC_SOURCE_CHANGED')
    return raw


def source_ready():
    """One construction-time check; never run extraction or inspect binaries."""
    need(DISPATCH_PATH is not None and DISPATCH_SHA is not None,
         'NPC_DISPATCH_SOURCE_UNVERIFIED_UNSAFE_NOT_EMITTED')
    _pinned(DISPATCH_PATH, DISPATCH_SHA)
    rows = [json.loads(line) for line in _pinned(SPR_PATH, SPR_SHA).splitlines()]
    sprite = next(row for row in rows if row['sprite_id'] == 56)
    need(sum(c['command_id'] == 1002 and c['body'] == '10'
             for c in sprite['commands']) == 1, 'NPC_SPR56_TYPE10_REQUIRED')
    rows = (json.loads(line) for line in _pinned(NPC_PATH, NPC_SHA).splitlines())
    template = next(row for row in rows if row['table'] == 'npc' and row['id'] == 0)
    need(template['body_sha256'] ==
         '1def0d91cf88097c0dec89cf8548e88ea282f69fb6d7a8e3c81f65fabe3fbef7',
         'NPC_TEMPLATE0_REQUIRED')


@dataclass(frozen=True, slots=True)
class NpcSpawn:
    fields: Mapping = field(repr=False)
    map_id: int
    policy: str

    def __post_init__(self):
        need(self.policy in (POLICY, WORLD_POLICY), 'EXPLICIT_NPC_LOCAL_POLICY_REQUIRED')
        need(type(self.map_id) is int and (self.map_id == 0 or self.policy == WORLD_POLICY
             and self.map_id in (1, 2)), 'NPC_MAP0_ONLY')
        need(isinstance(self.fields, Mapping) and set(self.fields) == FIELDS,
             'NPC_ALL_REQUIRED_AND_TEMPLATE39_EXPLICIT_ONLY')
        values = dict(self.fields)
        session.world.validate_input(0x4e96, values)
        # New local spawn policy reserves zero; this is not an original UID rule.
        need(values[2] > 0, 'NPC_LOCAL_POSITIVE_UID_REQUIRED')
        need(0 <= values[5] <= 7, 'NPC_DIRECTION_0_7_REQUIRED')
        need(values[16] is False and values[21] == '', 'NPC_MONSTER_DISPATCH_REQUIRED')
        pairs = WORLD_MONSTERS if self.map_id == 0 else DUNGEON_MONSTERS
        need(self.policy == POLICY and values[3] == 56 and values[39] == 0
             or self.policy == WORLD_POLICY and (values[3], values[39]) in pairs,
             'NPC_EXPLICIT_SPR56_TEMPLATE0_ONLY')
        object.__setattr__(self, 'fields', MappingProxyType(values))

    @property
    def uid(self):
        return self.fields[2]

    def frame(self):
        """Build only after the source contract and independent data pins pass."""
        source_ready()
        return self.encode()

    def encode(self):
        """Same frame without re-reading sources; caller ran source_ready() once."""
        body = session.world.encode_payload(0x4e96, self.fields)
        return (len(body) + 6).to_bytes(2, 'little') + b'\x96\x4e' + body + b'\0\0'


def prepare(spawns, *, self_uid):
    need(type(spawns) is tuple, 'NPC_BOUNDED_EXPLICIT_TUPLE_REQUIRED')
    if not spawns:
        return ()
    need(all(type(spawn) is NpcSpawn for spawn in spawns), 'NPC_TYPED_EXPLICIT_SPAWN_REQUIRED')
    need(all(spawn.policy == POLICY for spawn in spawns), 'EXPLICIT_NPC_LOCAL_POLICY_REQUIRED')
    need(len({spawn.uid for spawn in spawns}) == len(spawns), 'NPC_DUPLICATE_UID')
    need(len(spawns) <= MAX_SPAWNS, 'NPC_BOUNDED_EXPLICIT_TUPLE_REQUIRED')
    need(all(spawn.uid != self_uid for spawn in spawns), 'NPC_SELF_UID_COLLISION')
    return tuple((spawn, spawn.frame()) for spawn in spawns)
