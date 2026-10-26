"""Read-only M1 game data (Talking Island map0 hunting ground).

Loads the hand-picked JSON tables in ``data/m1`` into frozen dataclasses.
Every table value carries a :class:`Source` (client / official / l1j /
local_policy plus a short file:line reference). Standard library only; no
game, server or network access.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

M1_DATA_DIR = Path(__file__).resolve().parent / 'data' / 'm1'
SOURCE_KINDS = frozenset({'client', 'official', 'l1j', 'local_policy'})
CHANCE_DENOMINATOR = 1_000_000


@dataclass(frozen=True, slots=True)
class Source:
    kind: str
    ref: str
    note: str = ''


Sources = Mapping[str, Source]


@dataclass(frozen=True, slots=True)
class Rect:
    """Inclusive integer tile rectangle."""
    x1: int
    y1: int
    x2: int
    y2: int

    def contains(self, x: int, y: int) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


@dataclass(frozen=True, slots=True)
class DamageDef:
    """Raw NPC damage before PC defense; ``rule`` names the formula."""
    min: int
    max: int
    str: int
    rule: str


@dataclass(frozen=True, slots=True)
class MonsterDef:
    template_id: int
    name_token: str
    name_ko: str
    sprite_id: int
    l1j_npcid: int
    level: int
    hp: int
    mp: int
    ac: int
    kill_exp: int
    aggressive: bool
    move_interval_ms: int
    attack_interval_ms: int
    attack_range: int
    perception_range: int
    leash_range: int
    damage: DamageDef
    corpse_ms: int
    sources: Sources


@dataclass(frozen=True, slots=True)
class SpawnGroupDef:
    group_id: str
    template_id: int
    map_id: int
    rect: Rect
    target_count: int
    respawn_delay_min_ms: int
    respawn_delay_max_ms: int
    sources: Sources


@dataclass(frozen=True, slots=True)
class DropDef:
    """``chance`` is out of CHANCE_DENOMINATOR; grade 0=blessed 1=normal 2=cursed."""
    item_id: int
    item_token: str
    item_name_ko: str
    grade: int
    chance: int
    min_count: int
    max_count: int
    sources: Sources


@dataclass(frozen=True, slots=True)
class UnresolvedDrop:
    template_id: int
    item_id: int
    item_token: str
    item_name_ko: str
    grade: int
    ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class PcActionSpeed:
    sprite_id: int
    walk_ms: int
    attack_ms: int  # one-handed sword attack
    sources: Sources


@dataclass(frozen=True, slots=True)
class MonsterActionSpeed:
    sprite_id: int
    walk_ms: int
    attack_ms: int
    l1j_walk_ms: int
    l1j_attack_ms: int
    sources: Sources


@dataclass(frozen=True, slots=True)
class ActionSpeedDef:
    pc: Mapping[int, PcActionSpeed]
    monsters: Mapping[int, MonsterActionSpeed]


@dataclass(frozen=True, slots=True)
class RegenPolicy:
    tick_ms: int
    idle_points: int
    move_points: int
    attack_points: int
    hp_threshold_by_level: tuple[int, ...]
    hp_amount_base: int
    hp_con_offset: int
    mp_threshold: int
    mp_amount_by_wis: tuple[tuple[int, int], ...]
    sources: Sources

    def hp_threshold(self, level: int) -> int:
        table = self.hp_threshold_by_level
        return table[min(max(level, 1), len(table)) - 1]

    def hp_amount(self, con: int) -> int:
        return self.hp_amount_base + max(con - self.hp_con_offset, 0)

    def mp_amount(self, wis: int) -> int:
        amount = 0
        for minimum, value in self.mp_amount_by_wis:
            if wis >= minimum:
                amount = value
        return amount


@dataclass(frozen=True, slots=True)
class TownDef:
    map_id: int
    bounds: Rect
    respawn_x: int
    respawn_y: int
    regen: RegenPolicy
    sources: Sources


@dataclass(frozen=True, slots=True)
class BuffDef:
    """Timed speed potion (L1J useGreenPotion/useBravePotion): remaining + add_s, capped."""
    kind: str  # haste / brave (items.json buff_rate key)
    add_s: int
    cap_s: int
    rate: float  # action interval multiplier while active
    classes: frozenset  # classes that get the effect (others: consumed, no effect)


@dataclass(frozen=True, slots=True)
class ItemDef:
    """Classic item template with combat/use values (missing client values from L1J)."""
    template_id: int
    name_token: str
    name_ko: str
    kind: str  # weapon / armor / potion / currency / ammo (bag only)
    slot: str | None
    slot_key: int | None  # SC097A equipment key (rea238 UI slot table)
    stackable: bool
    dmg_small: int
    dmg_large: int
    hit: int
    dmg_bonus: int
    ac: int  # L1J sign: negative improves PC AC (10 + sum)
    heal_hp: int
    classes: frozenset
    sources: Sources
    buff: BuffDef | None = None
    icon: int = 0  # client CommonItemInfo f5 inventory icon number ('<icon>.png'); sent as 0964 ItemInfo f7
    weapon_type: str | None = None  # stance key; L1J weapon.type when native type semantics are unresolved

    @property
    def equippable(self) -> bool:
        return self.kind in ('weapon', 'armor') and self.slot_key is not None


@dataclass(frozen=True, slots=True)
class StarterEntry:
    template_id: int
    count: int
    equipped: bool
    source: Source
    grade: int | None = None  # Explicit LOCAL instance grade, never template-derived.


@dataclass(frozen=True, slots=True)
class StarterKit:
    uid_base: int
    classes: Mapping[int, tuple[StarterEntry, ...]]
    sources: Sources
    kits: Mapping[str, tuple[int, tuple[StarterEntry, ...]]] = MappingProxyType({})

    def entries(self, character_class: int, kit: str | None = None) -> tuple[StarterEntry, ...]:
        """Named kit (world.starter_kit) when it is for this class, else the class table."""
        named = None if kit is None else self.kits.get(kit)
        if named is not None and named[0] == character_class:
            return named[1]
        return self.classes.get(character_class, ())


@dataclass(frozen=True, slots=True)
class LevelGrowthDef:
    """L1J-derived local per-class level-up parameters (not Classic proof)."""
    character_class: int
    hp_base: int
    hp_cap: int
    mp_cap: int
    mp_numerator: int
    mp_denominator: int
    sources: Sources


@dataclass(frozen=True, slots=True)
class M1Data:
    monsters: Mapping[int, MonsterDef]
    spawns: tuple[SpawnGroupDef, ...]
    drops: Mapping[int, tuple[DropDef, ...]]
    drops_unresolved: tuple[UnresolvedDrop, ...]
    pc_exp: tuple[int, ...]  # cumulative EXP, index 0 = level 1
    action_speed: ActionSpeedDef
    town: TownDef
    items: Mapping[int, ItemDef] = MappingProxyType({})
    starter: StarterKit | None = None
    level_growth: Mapping[int, LevelGrowthDef] = MappingProxyType({})

    def exp_for_level(self, level: int) -> int:
        return self.pc_exp[level - 1]

    def level_for_exp(self, exp: int) -> int:
        level = 1
        for index, threshold in enumerate(self.pc_exp):
            if exp >= threshold:
                level = index + 1
        return level


class _Fields:
    """Unwraps ``{"value", "source", "ref", "note"}`` cells and keeps sources."""

    def __init__(self, row: Mapping[str, Any], where: str):
        self.row, self.where, self.sources = row, where, {}

    def __call__(self, key: str) -> Any:
        cell = self.row[key]
        kind = cell['source']
        if kind not in SOURCE_KINDS:
            raise ValueError(f'{self.where}.{key}: unknown source {kind!r}')
        self.sources[key] = Source(kind, cell['ref'], cell.get('note', ''))
        return cell['value']

    def frozen_sources(self) -> Sources:
        return MappingProxyType(dict(self.sources))


def _read(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding='utf-8'))


def _rect(raw: Mapping[str, int]) -> Rect:
    return Rect(raw['x1'], raw['y1'], raw['x2'], raw['y2'])


def _monsters(raw: dict) -> Mapping[int, MonsterDef]:
    out = {}
    for row in raw['monsters']:
        f = _Fields(row, 'monsters')
        template_id = f('template_id')
        damage = f('damage')
        out[template_id] = MonsterDef(
            template_id=template_id, name_token=f('name_token'), name_ko=f('name_ko'),
            sprite_id=f('sprite_id'), l1j_npcid=f('l1j_npcid'), level=f('level'),
            hp=f('hp'), mp=f('mp'), ac=f('ac'), kill_exp=f('kill_exp'),
            aggressive=f('aggressive'), move_interval_ms=f('move_interval_ms'),
            attack_interval_ms=f('attack_interval_ms'), attack_range=f('attack_range'),
            perception_range=f('perception_range'), leash_range=f('leash_range'),
            damage=DamageDef(damage['min'], damage['max'], damage['str'], damage['rule']),
            corpse_ms=f('corpse_ms'), sources=f.frozen_sources())
    return MappingProxyType(out)


def _spawns(raw: dict) -> tuple[SpawnGroupDef, ...]:
    out = []
    for row in raw['groups']:
        f = _Fields(row, 'spawns')
        delay = f('respawn_delay_ms')
        out.append(SpawnGroupDef(
            group_id=f('group_id'), template_id=f('template_id'), map_id=f('map_id'),
            rect=_rect(f('rect')), target_count=f('target_count'),
            respawn_delay_min_ms=delay['min'], respawn_delay_max_ms=delay['max'],
            sources=f.frozen_sources()))
    return tuple(out)


def _drops(raw: dict) -> tuple[Mapping[int, tuple[DropDef, ...]], tuple[UnresolvedDrop, ...]]:
    if raw['chance_denominator'] != CHANCE_DENOMINATOR:
        raise ValueError('drops: chance_denominator changed')
    table = {}
    for template, rows in raw['drops'].items():
        drops = []
        for row in rows:
            f = _Fields(row, f'drops.{template}')
            item, roll = f('item'), f('roll')
            drops.append(DropDef(
                item_id=item['id'], item_token=item['token'], item_name_ko=item['name_ko'],
                grade=item['grade'], chance=roll['chance'], min_count=roll['min'],
                max_count=roll['max'], sources=f.frozen_sources()))
        table[int(template)] = tuple(drops)
    unresolved = tuple(
        UnresolvedDrop(row['template_id'], row['item']['id'], row['item']['token'],
                       row['item']['name_ko'], row['item']['grade'], row['ref'], row['reason'])
        for row in raw['unresolved'])
    return MappingProxyType(table), unresolved


def _pc_exp(raw: dict) -> tuple[int, ...]:
    return tuple(_Fields(raw, 'pc_exp')('cumulative'))


def _action_speed(raw: dict) -> ActionSpeedDef:
    pc, monsters = {}, {}
    for row in raw['pc']:
        f = _Fields(row, 'action_speed.pc')
        sprite = f('sprite_id')
        pc[sprite] = PcActionSpeed(sprite, f('walk_ms'), f('attack_ms'), f.frozen_sources())
    for row in raw['monsters']:
        f = _Fields(row, 'action_speed.monsters')
        sprite, walk, attack, l1j = f('sprite_id'), f('walk_ms'), f('attack_ms'), f('l1j_reference')
        monsters[sprite] = MonsterActionSpeed(sprite, walk, attack, l1j['walk_ms'],
                                              l1j['attack_ms'], f.frozen_sources())
    return ActionSpeedDef(MappingProxyType(pc), MappingProxyType(monsters))


def _town(raw: dict) -> TownDef:
    r = _Fields(raw['regen'], 'town.regen')
    points = r('state_points')
    hp_amount = r('hp_amount')
    r('dead_or_offline')  # policy text only; kept in sources
    regen = RegenPolicy(
        tick_ms=r('tick_ms'), idle_points=points['idle'], move_points=points['move'],
        attack_points=points['attack'],
        hp_threshold_by_level=tuple(r('hp_threshold_by_level')),
        hp_amount_base=hp_amount['base'], hp_con_offset=hp_amount['con_offset'],
        mp_threshold=r('mp_threshold'),
        mp_amount_by_wis=tuple(tuple(pair) for pair in r('mp_amount_by_wis')),
        sources=r.frozen_sources())
    f = _Fields(raw, 'town')
    point = f('respawn_point')
    return TownDef(map_id=f('map_id'), bounds=_rect(f('bounds')), respawn_x=point['x'],
                   respawn_y=point['y'], regen=regen, sources=f.frozen_sources())


ITEM_KINDS = frozenset({'weapon', 'armor', 'potion', 'currency', 'ammo', 'scroll'})
WEAPON_TYPES = frozenset({'sword', 'axe', 'blunt', 'spear', 'bow', 'staff', 'dagger', 'twohand'})


def _items(raw: dict) -> Mapping[int, ItemDef]:
    top = _Fields(raw, 'items')
    keys = top('slot_keys')
    rates = top('buff_rate')
    out = {}
    for row in raw['items']:
        f = _Fields(row, 'items')
        template_id, kind, slot = f('id'), f('kind'), f('slot')
        weapon = f('weapon') or {}
        weapon_type = f('weapon_type') if 'weapon_type' in row else None
        if kind not in ITEM_KINDS or template_id in out:
            raise ValueError(f'items.{template_id}: kind/duplicate')
        if (kind == 'weapon' and weapon_type not in WEAPON_TYPES) or (kind != 'weapon' and weapon_type is not None):
            raise ValueError(f'items.{template_id}: weapon_type')
        if (slot is None) != (kind not in ('weapon', 'armor')) or (slot is not None and slot not in keys):
            raise ValueError(f'items.{template_id}: slot')
        if (kind == 'weapon') != (slot == 'weapon'):
            raise ValueError(f'items.{template_id}: weapon slot')
        buff = None
        if 'buff' in row:
            b = f('buff')
            if kind != 'potion' or b['kind'] not in rates:
                raise ValueError(f'items.{template_id}: buff')
            buff = BuffDef(b['kind'], b['add_s'], b['cap_s'], rates[b['kind']], frozenset(b['classes']))
        icon = f('icon') if 'icon' in row else 0
        out[template_id] = ItemDef(
            template_id=template_id, name_token=f('name_token'), name_ko=f('name_ko'), kind=kind,
            slot=slot, slot_key=None if slot is None else keys[slot], stackable=f('stackable'),
            dmg_small=weapon.get('small', 0), dmg_large=weapon.get('large', 0),
            hit=weapon.get('hit', 0), dmg_bonus=weapon.get('damage', 0), ac=f('ac'),
            heal_hp=f('heal_hp'), classes=frozenset(f('classes')), sources=f.frozen_sources(),
            buff=buff, icon=icon, weapon_type=weapon_type)
    return MappingProxyType(out)


def _starter(raw: dict, items: Mapping[int, ItemDef]) -> StarterKit:
    top = _Fields(raw, 'starter')
    uid_base = top('uid_base')
    top('class_ids')

    def kit_entries(class_id, rows, where):
        entries, slots = [], set()
        for row in rows:
            f = _Fields({'entry': row}, where)
            value = f('entry')
            entry = StarterEntry(value['item'], value['count'], value['equipped'],
                                 f.sources['entry'], value.get('grade'))
            if entry.grade is not None and (type(entry.grade) is not int or entry.grade not in (0, 1, 2)
                                           or entry.template_id not in (25, 26)):
                raise ValueError(f'{where}: explicit scroll grade')
            item = items.get(entry.template_id)
            if item is None or entry.count < 1 or (entry.count > 1 and not item.stackable):
                raise ValueError(f'{where}: item {entry.template_id}')
            if entry.equipped:
                if not item.equippable or item.slot_key in slots or class_id not in item.classes:
                    raise ValueError(f'{where}: equipped {entry.template_id}')
                slots.add(item.slot_key)
            entries.append(entry)
        return tuple(entries)

    classes = {int(class_id): kit_entries(int(class_id), rows, f'starter.{class_id}')
               for class_id, rows in raw['classes'].items()}
    kits = {}
    for name, kit in raw.get('kits', {}).items():
        class_id = _Fields(kit, f'starter.kits.{name}')('class')
        kits[name] = (class_id, kit_entries(class_id, kit['entries'], f'starter.kits.{name}'))
    return StarterKit(uid_base, MappingProxyType(classes), top.frozen_sources(), MappingProxyType(kits))


def load_items(directory: Path | str = M1_DATA_DIR) -> Mapping[int, ItemDef]:
    return _items(_read(Path(directory), 'items.json'))


def load_stances(directory: Path | str = M1_DATA_DIR) -> Mapping[str, int]:
    """Read the editable weapon-type → ActorNotify 4E96 f4 stance table (only bow 40 observed)."""
    raw = _read(Path(directory), 'stance.json')
    out = {}
    for kind, row in raw['stances'].items():
        value = _Fields({'stance': row}, f'stance.{kind}')('stance')
        if kind not in WEAPON_TYPES | {'unarmed'} or type(value) is not int or value < 0:
            raise ValueError(f'stance.{kind}: type/value')
        out[kind] = value
    if set(out) != WEAPON_TYPES | {'unarmed'}:
        raise ValueError('stance: missing weapon type/unarmed')
    return MappingProxyType(out)


def _level_growth(raw: dict) -> Mapping[int, LevelGrowthDef]:
    out = {}
    for row in raw['classes']:
        f = _Fields(row, 'level_growth')
        character_class = f('character_class')
        multiplier = f('mp_multiplier')
        out[character_class] = LevelGrowthDef(
            character_class, f('hp_base'), f('hp_cap'), f('mp_cap'),
            multiplier['numerator'], multiplier['denominator'], f.frozen_sources())
    return MappingProxyType(out)


def load_m1(directory: Path | str = M1_DATA_DIR) -> M1Data:
    """Read all M1 tables from ``directory``; returns immutable definitions."""
    directory = Path(directory)
    drops, unresolved = _drops(_read(directory, 'drops.json'))
    items = _items(_read(directory, 'items.json'))
    return M1Data(
        monsters=_monsters(_read(directory, 'monsters.json')),
        spawns=_spawns(_read(directory, 'spawns.json')),
        drops=drops, drops_unresolved=unresolved,
        pc_exp=_pc_exp(_read(directory, 'pc_exp.json')),
        action_speed=_action_speed(_read(directory, 'action_speed.json')),
        town=_town(_read(directory, 'town.json')),
        items=items, starter=_starter(_read(directory, 'starter.json'), items),
        level_growth=_level_growth(_read(directory, 'level_growth.json')))
