"""Read-only M1 game data (Talking Island map0 hunting ground).

Loads the hand-picked JSON tables in ``data/m1`` into frozen dataclasses.
Every table value carries a :class:`Source` (client / official / l1j /
local_policy plus a short file:line reference). Standard library only; no
game, server or network access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    size: str = 'small'
    mr: int = 0
    weak_attr: int = 0  # Defender weakness; never an NPC attack element.
    death_action: int | None = 8  # None: no ordinary death selector (e.g. pigeon fly8).
    undead: int | None = None  # Sourced L1J NPC category; absent stays UNKNOWN.


@dataclass(frozen=True, slots=True)
class NpcSpellDef:
    """L1J gap-filling policy; skill_id is deliberately not a native key."""
    npc_id: int
    skill_id: int
    spell_name: str
    classic_key: int | None
    chance_percent: int
    max_distance: int
    leverage: int
    intelligence: int
    mp_cost: int
    reuse_seconds: float
    cast_interval_seconds: float
    drain: bool
    parameters: Mapping[str, int]
    source_refs: tuple[str, ...]


def load_npc_spells(path: Path | str | None = None) -> Mapping[int, tuple[NpcSpellDef, ...]]:
    """Optional magic producer catalog, loaded once at feature initialization."""
    path = M1_DATA_DIR / 'npc_magic_attacks.json' if path is None else Path(path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    rows = {}
    for row in raw['attacks']:
        values = {key: row[key] for key in NpcSpellDef.__dataclass_fields__}
        values['parameters'] = MappingProxyType(values['parameters'])
        values['source_refs'] = tuple(values['source_refs'])
        spell = NpcSpellDef(**values)
        rows.setdefault(spell.npc_id, []).append(spell)
    return MappingProxyType({npc_id: tuple(spells) for npc_id, spells in rows.items()})


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
    placement: Mapping[str, Any] | None = None


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
class EquipmentSetBonusDef:
    """One official Classic set threshold; descriptive effects stay in JSON."""
    set_id: str
    members: tuple[int, ...]
    degree: int
    modifiers: Mapping[str, int]
    sources: Sources


@dataclass(frozen=True, slots=True)
class ItemDef:
    """Client/official template; unavailable values retain explicit L1J sources."""
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
    weight: int | None = None  # client f10: 1000 raw units per burden unit
    safe_enchant: int | None = None  # official safe limit; no probability policy
    heal_hp_range: tuple[int, int] | None = None  # official inclusive endpoints
    slot_keys: tuple[int, ...] = ()  # allowed SC097A keys; ring uses both 13 and 14
    modifiers: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    class_modifiers: Mapping[int, Mapping[str, int]] = field(default_factory=lambda: MappingProxyType({}))
    set_bonuses: tuple[EquipmentSetBonusDef, ...] = ()
    attack_range: int = 1  # LOCAL tile cap; bows retain world_ammo's own policy

    def __post_init__(self):
        if not self.slot_keys and self.slot_key is not None:
            object.__setattr__(self, 'slot_keys', (self.slot_key,))

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
    raw = json.loads((directory / name).read_text(encoding='utf-8'))
    # Explicit population fragments share the existing startup overlay. This
    # keeps large field tables independent without a feature-to-feature call.
    for fragment in raw.get('population_includes', ()):
        path = Path(fragment)
        if path.name != fragment or fragment == name:
            raise ValueError('population include must be a sibling file')
        child = json.loads((directory / path).read_text(encoding='utf-8'))
        if child.get('population_includes'):
            raise ValueError('nested population includes are unsupported')
        for key in ('monsters', 'groups'):
            raw.setdefault(key, []).extend(child.get(key, ()))
    return raw


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
            corpse_ms=f('corpse_ms'), size=f('size') if 'size' in row else 'small',
            mr=f('l1j_mr') if 'l1j_mr' in row else 0,
            weak_attr=(f('weak_attr') if 'weak_attr' in row else
                       f('l1j_weak_attr') if 'l1j_weak_attr' in row else 0),
            death_action=f('death_action') if 'death_action' in row else 8,
            undead=f('l1j_undead') if 'l1j_undead' in row else None,
            sources=f.frozen_sources())
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
            placement=MappingProxyType(f('placement')) if 'placement' in row else None,
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


ITEM_KINDS = frozenset({'weapon', 'armor', 'potion', 'currency', 'ammo', 'scroll', 'misc'})
WEAPON_TYPES = frozenset({'sword', 'axe', 'blunt', 'spear', 'bow', 'staff', 'dagger', 'twohand'})


def _equipment_set_bonus(row: dict) -> EquipmentSetBonusDef:
    f = _Fields(row, 'equipment_sets')
    set_id, members = f('id'), tuple(f('members'))
    degree, modifiers = f('degree'), f('modifiers')
    if len(set(members)) != len(members) or not 1 <= degree <= len(members):
        raise ValueError(f'equipment_sets.{set_id}: members/degree')
    return EquipmentSetBonusDef(set_id, members, degree,
                               MappingProxyType(dict(modifiers)), f.frozen_sources())


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
        weight = f('weight') if 'weight' in row else None
        safe_enchant = f('safe_enchant') if 'safe_enchant' in row else None
        recovery = f('heal_hp_range') if 'heal_hp_range' in row else None
        hit = f('hit') if 'hit' in row else weapon.get('hit', 0)
        damage_bonus = f('dmg_bonus') if 'dmg_bonus' in row else weapon.get('damage', 0)
        slot_keys = () if slot is None else keys[slot]
        slot_keys = tuple(slot_keys) if isinstance(slot_keys, list) else (slot_keys,) if slot is not None else ()
        modifiers = f('modifiers') if 'modifiers' in row else {}
        class_modifiers = f('class_modifiers') if 'class_modifiers' in row else {}
        set_bonuses = (tuple(_equipment_set_bonus(bonus) for bonus in f('set_bonuses'))
                       if 'set_bonuses' in row else ())
        attack_range = f('attack_range') if 'attack_range' in row else 1
        out[template_id] = ItemDef(
            template_id=template_id, name_token=f('name_token'), name_ko=f('name_ko'), kind=kind,
            slot=slot, slot_key=slot_keys[0] if slot_keys else None, stackable=f('stackable'),
            dmg_small=weapon.get('small', 0), dmg_large=weapon.get('large', 0),
            hit=hit, dmg_bonus=damage_bonus, ac=f('ac'),
            heal_hp=f('heal_hp'), classes=frozenset(f('classes')), sources=f.frozen_sources(),
            buff=buff, icon=icon, weapon_type=weapon_type, weight=weight,
            safe_enchant=safe_enchant,
            heal_hp_range=None if recovery is None else (recovery['min'], recovery['max']),
            slot_keys=slot_keys, modifiers=MappingProxyType(dict(modifiers)),
            class_modifiers=MappingProxyType({int(key): MappingProxyType(dict(value))
                                             for key, value in class_modifiers.items()}),
            set_bonuses=set_bonuses, attack_range=attack_range)
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
                available = next((key for key in item.slot_keys if key not in slots), None)
                if not item.equippable or available is None or class_id not in item.classes:
                    raise ValueError(f'{where}: equipped {entry.template_id}')
                slots.add(available)
            entries.append(entry)
        return tuple(entries)

    classes = {int(class_id): kit_entries(int(class_id), rows, f'starter.{class_id}')
               for class_id, rows in raw['classes'].items()}
    kits = {}
    for name, kit in raw.get('kits', {}).items():
        class_id = _Fields(kit, f'starter.kits.{name}')('class')
        kits[name] = (class_id, kit_entries(class_id, kit['entries'], f'starter.kits.{name}'))
    return StarterKit(uid_base, MappingProxyType(classes), top.frozen_sources(), MappingProxyType(kits))


def _items_dir(directory: Path) -> Mapping[int, ItemDef]:
    """items.json plus any items_ext/*.json rows (same row schema, unique ids)."""
    raw = _read(directory, 'items.json')
    ext = directory / 'items_ext'
    if ext.is_dir():
        raw = dict(raw, items=list(raw['items']))
        for path in sorted(ext.glob('*.json')):
            raw['items'].extend(_read(ext, path.name)['items'])
    ranges_path = directory / 'weapon_ranges.json'
    if ranges_path.is_file():
        ranges = _read(directory, ranges_path.name)['ranges']
        raw = dict(raw, items=[dict(row, attack_range=ranges[str(row['id']['value'])])
                              if str(row['id']['value']) in ranges else row
                              for row in raw['items']])
    sets_path = directory / 'equipment_sets.json'
    if not sets_path.is_file():
        return _items(raw)
    # Expand the catalog into optional item-row fields in memory only. The
    # same _items schema also accepts a standalone row's explicit set_bonuses.
    # Base items.json stays untouched, and consumers need no global data I/O.
    by_item = {row['id']['value']: [] for row in raw['items']}
    seen = set()
    for row in _read(directory, sets_path.name)['sets']:
        bonus = _equipment_set_bonus(row)
        if bonus.set_id in seen or not set(bonus.members) <= by_item.keys():
            raise ValueError(f'equipment_sets.{bonus.set_id}: members/duplicate')
        seen.add(bonus.set_id)
        for member in bonus.members:
            by_item[member].append(row)
    rows = []
    for row in raw['items']:
        bonuses = by_item[row['id']['value']]
        if bonuses:
            existing = row.get('set_bonuses', {}).get('value', [])
            row = dict(row, set_bonuses={
                'value': [*existing, *bonuses], 'source': 'local_policy',
                'ref': 'equipment_sets.json members -> item row set_bonuses',
                'note': 'Membership projection only; each definition retains its official sources.'})
        rows.append(row)
    return _items(dict(raw, items=rows))


def load_items(directory: Path | str = M1_DATA_DIR) -> Mapping[int, ItemDef]:
    return _items_dir(Path(directory))


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
    items = _items_dir(directory)
    return M1Data(
        monsters=_monsters(_read(directory, 'monsters.json')),
        spawns=_spawns(_read(directory, 'spawns.json')),
        drops=drops, drops_unresolved=unresolved,
        pc_exp=_pc_exp(_read(directory, 'pc_exp.json')),
        action_speed=_action_speed(_read(directory, 'action_speed.json')),
        town=_town(_read(directory, 'town.json')),
        items=items, starter=_starter(_read(directory, 'starter.json'), items),
        level_growth=_level_growth(_read(directory, 'level_growth.json')))


def load_m4(base: M1Data, directory: Path | str | None = None) -> M1Data:
    """Extend the existing world with the sourced Gludin subset, at startup.

    Shared M3 monster/reward definitions retain their existing policy. M4 is
    an extension, not a replacement for M1's town, starter or growth tables.
    Its additional item67 is loaded alongside the existing item definitions.
    See game-core-prep/M4_GLUDIN_DATA.md for the 9-monster LOCAL subset and
    the separate unresolved drop/identity evidence.
    """
    from dataclasses import replace
    directory = M1_DATA_DIR.parent / 'm4' if directory is None else Path(directory)
    monsters = _monsters(_read(directory, 'monsters.json'))
    spawns = _spawns(_read(directory, 'spawns.json'))
    drops, unresolved = _drops(_read(directory, 'drops.json'))
    items = _items(_read(directory, 'items.json'))
    # Existing template-scoped policy also serves map1/2: do not silently
    # replace it with map4's smaller selection of the same official drops.
    new_templates = set(monsters) - set(base.monsters)
    return replace(base,
        monsters=MappingProxyType(dict(monsters) | dict(base.monsters)),
        spawns=base.spawns + spawns,
        drops=MappingProxyType(dict(drops) | dict(base.drops)),
        drops_unresolved=base.drops_unresolved + tuple(
            row for row in unresolved if row.template_id in new_templates),
        items=MappingProxyType(dict(items) | dict(base.items)))
