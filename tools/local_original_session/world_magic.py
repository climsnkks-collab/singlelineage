"""Player magic rules and durable learning, using the retained spell data.

Numbers labelled LOCAL in player_spells.json remain backend policy. Runtime
UIDs, sessions, MP, HP, damage, and packets belong to the existing world owner.
The short learning intent uses InventoryStore's normal kit CAS and completes
forward on startup, so a crash cannot consume the same book twice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from functools import cache
import json
import math
from pathlib import Path
import time

from tools.local_original_session import world_magic_status as magic_status


BUFF_KINDS = frozenset(('shield', 'light', 'weapon_hit', 'weapon_damage',
                        'weight', 'armor', 'dexterity', 'job_stats', 'reduction',
                        'evasion', 'counter_barrier'))
# Known persisted timed effects may outlive the optional consumer configuration.
# They retain their deadline while unsupported, without admission or effects.
OPTIONAL_BUFF_KEYS = frozenset((89, 90))

# Runtime policy over the preserved SOURCE_ONLY catalog, never an edit to the
# official/client evidence. SQL keys are Classic spell key+1 (name joined).
# Official MP/HP/effect/duration take precedence over the older L1J numbers.
JOB_POLICIES = {
    86: dict(kind='stun', probability_base=50, probability_level_factor=2,
             local_reuse_seconds=1.5, l1j_skill=87),
    87: dict(kind='reduction', local_reuse_seconds=3, l1j_skill=88),
    88: dict(kind='job_stats', melee_hit=5, local_reuse_seconds=5, l1j_skill=89),
    128: dict(kind='job_stats', mr=10, local_reuse_seconds=1, l1j_skill=129),
    129: dict(kind='hp_to_mp', mp_restore=2, local_reuse_seconds=.4, l1j_skill=130),
    136: dict(kind='job_stats', wis=3, local_reuse_seconds=1, l1j_skill=137),
    137: dict(kind='job_stats', resist_earth=10, resist_fire=10,
              resist_water=10, resist_wind=10, local_reuse_seconds=1, l1j_skill=138),
    145: dict(kind='hp_to_mp', mp_restore=15, local_reuse_seconds=1.2, l1j_skill=146),
    146: dict(kind='job_stats', own_element_resist=50, local_reuse_seconds=1, l1j_skill=147),
    147: dict(kind='job_stats', melee_damage=3, exclusive_group='element_attack',
              local_reuse_seconds=1, l1j_skill=148),
    148: dict(kind='job_stats', ranged_hit=5, exclusive_group='element_attack',
              local_reuse_seconds=1, l1j_skill=149),
    150: dict(kind='shield', ac_bonus=-4, exclusive_group='armor_magic',
              local_reuse_seconds=1, l1j_skill=151),
    151: dict(kind='entangle', move_multiplier=2, probability_base=50,
              probability_dice=30, probability_level_factor=.5,
              local_reuse_seconds=1, l1j_skill=152),
    152: dict(kind='erase_magic', probability_base=50, probability_dice=30,
              probability_level_factor=.5, local_reuse_seconds=1, l1j_skill=153),
    162: dict(kind='job_stats', melee_damage=5, melee_hit=3, exclusive_group='element_attack',
              local_reuse_seconds=1, l1j_skill=163),
    165: dict(kind='job_stats', ranged_damage=4, ranged_hit=2, exclusive_group='element_attack',
              local_reuse_seconds=1, l1j_skill=166),
    167: dict(kind='shield', ac_bonus=-7, exclusive_group='armor_magic',
              local_reuse_seconds=1, l1j_skill=168),
    169: dict(kind='water_life', healing_multiplier=1.5, local_reuse_seconds=1, l1j_skill=170),
}

ELF_ELEMENTS = frozenset(('earth', 'fire', 'water', 'wind'))
ELEMENT_NAMES = {'땅': 'earth', '불': 'fire', '물': 'water', '바람': 'wind'}

# Missing producer/consumer contracts, not zero-cost approximations. Effects
# requiring another optional feature must wait for its registered service.
JOB_DEFERRED = {
    89: 'ER attack-evasion consumer absent',
    90: 'two-handed sword counterattack admission/damage service absent',
    112: 'target-following mark wire and tracking consumer unverified',
    113: 'party membership/recipient provider absent',
    115: 'clan membership and summon provider absent',
    116: 'party membership/recipient provider absent',
    117: 'clan membership and teleport provider absent',
    130: 'source-backed world-tree destination unavailable',
    131: 'registered atomic three-arrow/three-swing service absent',
    144: 'registered summon/tame dismissal service absent',
    149: 'movement-only acceleration consumer/native speed contract unverified',
    153: 'registered elemental summon and selected-element producer absent',
    154: 'party membership/recipient provider absent',
    155: 'party membership/recipient provider absent',
    156: 'complete damage-immunity/action-block contract absent',
    157: 'official instant heal conflicts with L1J periodic regeneration; numeric instant formula unknown',
    158: 'party membership/recipient provider absent',
    160: 'registered chat and all-NPC spell silence consumers absent',
    161: 'registered elemental summon and selected-element producer absent',
    163: 'party membership/recipient provider absent',
    172: 'all healing-potion paths lack registered received-heal multiplier',
    173: 'ER attack-evasion consumer absent',
    174: 'maximum weapon-die and durability consumer service absent',
}


def runtime_spell(raw, policies=None):
    key = raw['classic_key']['value']
    policies = JOB_POLICIES if policies is None else {**JOB_POLICIES, **policies}
    if key not in policies:
        return raw
    raw = deepcopy(raw)
    official = raw['source_snapshot']['official']
    policy = raw['player_policy']
    policy.update(policies[key], supported=True,
        implementation_status='LOCAL_RUNTIME_SUBSET',
        target_policy=official.get('target', 'UNKNOWN'),
        book_raw_weight=dict(value=7000 if key in (86, 87, 88, 89, 90) else 5000,
                             status='CLIENT_F10_EXISTING_WEIGHT_POLICY'),
        runtime_source='data/official/spells.json; l1jdb_m10.sql skills name join; '
                       'zero SQL reuse uses LOCAL existing default1s')
    element = ELEMENT_NAMES.get(official.get('elementalName'))
    if element:
        policy['required_element'] = element
        policy['implementation_status'] = 'CONDITIONAL_ELEMENT_INPUT_PROVIDER_REQUIRED'
    costs = official.get('consumables', {})
    # Null public fields stay null in the source catalog. These selected rows
    # have SQL zero for omitted MP/HP/catalysts, except Bounce's SQL HP120:
    # omitted HP uses that explicit LOCAL fallback, rather than assuming zero.
    raw['mp_cost'] = dict(value=costs.get('mp', 0), status='OFFICIAL_OR_L1J_ZERO_LOCAL')
    raw['hp_cost'] = dict(value=costs.get('hp', 120 if key == 88 else 50 if key == 87 else 0),
                           status='OFFICIAL_OR_L1J_HP_LOCAL_FALLBACK')
    raw['materials'] = dict(value=([dict(classic_item_key=569, count=costs['itemCount'])]
        if costs.get('itemName') == '정령옥' else []),
        status='OFFICIAL_ITEM_COUNT_CLIENT_NAME_JOIN_OR_L1J_ZERO')
    return raw


def need(value, code):
    if not value:
        raise ValueError(code)


@dataclass(frozen=True)
class Spell:
    key: int
    name: str
    book: int | None
    classes: dict
    kind: str
    mp: int
    range: int
    duration: float
    reuse: float
    raw: dict = field(repr=False)


@dataclass
class MagicState:
    learned: set[int] = field(default_factory=set)
    buffs: dict[int, float] = field(default_factory=dict)
    next_cast_at: float = 0.0
    weapon_uids: dict[int, int] = field(default_factory=dict)
    poison: dict | None = None
    invisible_until: float = 0.0
    armor_uids: dict[int, int] = field(default_factory=dict)
    effects: dict[str, dict] = field(default_factory=dict)
    elf_element: str | None = None
    buff_sources: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class MagicService:
    """Registered timed-effect owner; consumers never reach another feature."""
    engine: object
    save: object
    sync_icons: object
    buff_target: object = None


@dataclass(frozen=True)
class MagicBuffTarget:
    """Current buff recipient, with its own timer/equipment and commit owner."""
    state: MagicState
    weapon_uid: int
    armor_uid: int
    apply: object
    duration: float


def allows_received_buff(spell):
    targets = {part.strip() for part in spell.raw.get('target', {}).get(
        'client_required_target', '').split(',')}
    return spell.kind in BUFF_KINDS and bool(targets & {'pc', 'pledge', 'party'})


class PlayerMagic:
    def __init__(self, catalog, *, buff_seconds=None, runtime_policies=None):
        self.catalog = catalog
        self.spells = {}
        self.books = {}
        self.states: dict[int, MagicState] = {}
        # NPCs have their world EntityRef lifetime, not a durable character UID.
        self.npc_poison = {}
        self.npc_invisible = {}
        self.npc_statuses = {}
        for source in catalog['spells']:
            raw = runtime_spell(source, runtime_policies)
            policy = raw['player_policy']
            key = raw['classic_key']['value']
            duration = (raw.get('duration_seconds') or {}).get('value') or 0
            if buff_seconds is not None and duration:
                duration = buff_seconds
            spell = Spell(key, raw['id'], policy.get('book_classic_key'),
                {int(k): v for k, v in policy['allowed_class_min_levels'].items()},
                policy['kind'] if policy.get('supported', False) else 'unsupported',
                raw['mp_cost']['value'], raw['range_tiles']['value'] or 0,
                duration, policy.get('local_reuse_seconds',
                    catalog.get('local_policy', {}).get('default_reuse_seconds', 1.0)), raw)
            need(key not in self.spells, 'MAGIC_DUPLICATE_SPELL')
            self.spells[key] = spell
            if spell.book is not None:
                need(spell.book not in self.books, 'MAGIC_DUPLICATE_BOOK')
                self.books[spell.book] = spell

    def state(self, uid):
        return self.states.setdefault(uid, MagicState())

    def item_raw_weight(self, template):
        """Only source-backed magic items supplement the ordinary M1 table.

        Books and catalysts are separate domains. Unknown inventory templates
        retain a lookup failure instead of silently becoming weightless.
        """
        book = self.books.get(template)
        if book is not None:
            return book.raw['player_policy']['book_raw_weight']['value']
        if template == 569:
            return 781  # native-dump:1340 f10, existing LOCAL raw-weight units
        return self.catalog['local_policy']['material_raw_weights'][str(template)]['value']

    def eligibility(self, spell, character_class, level):
        minimum = spell.classes.get(character_class)
        need(minimum is not None, 'MAGIC_CLASS_NOT_ALLOWED')
        need(level >= minimum, 'MAGIC_LEVEL_TOO_LOW')

    def learn(self, uid, spell, character_class, level):
        # Incomplete effects do not spend a player's book. Existing saved
        # learned keys remain readable, but are not permission to fake a cast.
        need(spell.kind != 'unsupported', 'MAGIC_EFFECT_UNSUPPORTED')
        self.eligibility(spell, character_class, level)
        self.element_eligibility(uid, spell)
        need(spell.key not in self.state(uid).learned, 'MAGIC_ALREADY_LEARNED')
        # Proposal only: the inventory/learning save must finish before adopting.
        return self.state(uid).learned | {spell.key}

    def admit_cast(self, uid, key, character_class, level, mp, alive, now):
        spell = self.spells.get(key)
        need(spell is not None, 'MAGIC_UNKNOWN_SPELL')
        need(alive, 'MAGIC_LIVING_CASTER_REQUIRED')
        need(not magic_status.ai_status(self.effects(uid), now)['blocked'], 'MAGIC_CASTER_PARALYZED')
        need(key in self.state(uid).learned, 'MAGIC_NOT_LEARNED')
        self.eligibility(spell, character_class, level)
        self.element_eligibility(uid, spell)
        need(spell.kind != 'unsupported', 'MAGIC_EFFECT_UNSUPPORTED')
        need(now >= self.state(uid).next_cast_at, 'MAGIC_REUSE_NOT_READY')
        need(type(mp) is int and mp >= spell.mp, 'MAGIC_INSUFFICIENT_MP')
        return spell

    def committed(self, uid, spell, now):
        state = self.state(uid)
        state.next_cast_at = now + spell.reuse
        self.apply_buff(uid, spell, now)

    def apply_buff(self, uid, spell, now, *, weapon_uid=0, armor_uid=0, source_uid=None,
                   replace_weapon=False):
        """Apply to the recipient without changing that recipient's cast reuse."""
        state = self.state(uid)
        if spell.kind in BUFF_KINDS:
            group = spell.raw['player_policy'].get('exclusive_group')
            if spell.key == 2 and any(
                    key in state.buffs for key in (150, 167)):
                group = 'armor_magic'
            for key in tuple(state.buffs):
                candidate = self.spells[key]
                # L1SkillUse removes the existing armor/element attack family.
                if (group and (candidate.raw['player_policy'].get('exclusive_group') == group
                        or group == 'armor_magic' and candidate.key == 2)
                        or replace_weapon and spell.kind in ('weapon_hit', 'weapon_damage')
                        and candidate.kind in ('weapon_hit', 'weapon_damage') and key != spell.key):
                    state.buffs.pop(key)
                    state.armor_uids.pop(key, None)
                    state.weapon_uids.pop(key, None)
                    state.buff_sources.pop(key, None)
            state.buffs[spell.key] = now + spell.duration
            if source_uid is not None and source_uid != uid:
                state.buff_sources[spell.key] = source_uid
            else:
                state.buff_sources.pop(spell.key, None)
            if weapon_uid:
                state.weapon_uids[spell.key] = weapon_uid
            if armor_uid:
                state.armor_uids[spell.key] = armor_uid

    def element_eligibility(self, uid, spell):
        policy = spell.raw['player_policy']
        selected = self.state(uid).elf_element
        required = policy.get('required_element')
        need(not required or selected == required, 'MAGIC_ELF_ELEMENT_REQUIRED')
        need(not policy.get('own_element_resist') or selected in ELF_ELEMENTS,
             'MAGIC_ELF_ELEMENT_REQUIRED')

    def select_element(self, uid, element):
        """Trusted selection hook consumer; never select from the spell cast.

        No native selection packet is currently mapped. Existing profiles
        remain unselected; only an explicit producer or pre-login test save
        can supply this value. Changing school ends that school's buffs.
        """
        need(element is None or element in ELF_ELEMENTS, 'MAGIC_ELF_ELEMENT_VALUE')
        state = self.state(uid)
        if element != state.elf_element:
            for key in tuple(state.buffs):
                policy = self.spells[key].raw['player_policy']
                if policy.get('required_element') or policy.get('own_element_resist'):
                    del state.buffs[key]
                    state.weapon_uids.pop(key, None)
                    state.armor_uids.pop(key, None)
                    state.buff_sources.pop(key, None)
            state.elf_element = element

    def expire(self, now):
        changed = []
        for uid, state in self.states.items():
            expired = [key for key, until in state.buffs.items() if until <= now]
            for key in expired:
                del state.buffs[key]
                state.weapon_uids.pop(key, None)
                state.armor_uids.pop(key, None)
                state.buff_sources.pop(key, None)
            invisible_expired = bool(state.invisible_until and state.invisible_until <= now)
            if invisible_expired:
                state.invisible_until = 0.0
            poison_expired = state.poison is not None and state.poison['until'] <= now
            if poison_expired:
                state.poison = None
            effects_expired = magic_status.expire(state.effects, now)
            if expired or invisible_expired or poison_expired or effects_expired:
                changed.append(uid)
        return tuple(changed)

    def effects(self, uid, *, target_ref=None):
        if target_ref is None:
            state = self.states.get(uid)
            return {} if state is None else state.effects
        row = self.npc_statuses.get(uid)
        if row is None or row['ref'] != target_ref:
            row = self.npc_statuses[uid] = dict(ref=target_ref, effects={})
        return row['effects']

    def apply_status(self, uid, kind, now, duration, *, source_uid=0, spell=0,
                     params=None, target_ref=None, onset=0):
        if target_ref is None:
            self.state(uid)
        return magic_status.apply(self.effects(uid, target_ref=target_ref), kind,
            now, duration, source_uid=source_uid, spell=spell, params=params, onset=onset)

    def status(self, uid, kind, now):
        state = self.states.get(uid)
        effects = state.effects if state is not None else self.npc_statuses.get(uid, {}).get('effects', {})
        return magic_status.active(effects, kind, now)

    def consume_counter(self, uid, now):
        if self.status(uid, 'counter_magic', now) is None:
            return False
        effects = (self.states[uid].effects if uid in self.states
                   else self.npc_statuses[uid]['effects'])
        del effects['counter_magic']
        return True

    def effective_mr(self, uid, mr, now):
        return mr // 2 if self.status(uid, 'erase_magic', now) else mr

    def consume_erase(self, uid, now):
        if self.status(uid, 'erase_magic', now) is None:
            return False
        effects = self.states[uid].effects if uid in self.states else self.npc_statuses[uid]['effects']
        effects.pop('erase_magic', None)
        return True

    def healing_amount(self, uid, amount, now):
        """Official x1.5; one ordinary healing spell consumes it (L1J LOCAL)."""
        effect = self.status(uid, 'water_life', now)
        if effect is None:
            return amount
        self.state(uid).effects.pop('water_life')
        return int(amount * effect['params'].get('healing_multiplier', 1.5))

    def clear_curses(self, uid):
        effects = (self.states[uid].effects if uid in self.states
                   else self.npc_statuses.get(uid, {}).get('effects', {}))
        removed = tuple(kind for kind in effects if kind in magic_status.CURSES)
        for kind in removed:
            del effects[kind]
        return removed

    def clear_weapon_damage(self, uid, weapon_uid):
        """Pure repair producer; does not manufacture an item or repair action."""
        effects = self.effects(uid)
        effect = effects.get('weapon_break')
        if effect is not None and effect['params'].get('weapon_uid') == weapon_uid:
            del effects['weapon_break']
            return True
        return False

    def ac_bonus(self, uid, now, *, armor_uid=0):
        state = self.states.get(uid)
        if state is None:
            return 0
        return sum(self.spells[key].raw['player_policy'].get('ac_bonus', -2)
            for key, until in state.buffs.items() if until > now and (
                self.spells[key].kind == 'shield' or self.spells[key].kind == 'armor'
                and armor_uid and state.armor_uids.get(key) == armor_uid))

    def dexterity_bonus(self, uid, now):
        state = self.states.get(uid)
        return 0 if state is None else sum(
            self.spells[key].raw['player_policy'].get('dexterity_bonus', 0)
            for key, until in state.buffs.items()
            if until > now and self.spells[key].kind == 'dexterity')

    def job_bonuses(self, uid, now):
        state = self.states.get(uid)
        names = ('wis', 'mr', 'melee_hit', 'melee_damage', 'ranged_hit', 'ranged_damage',
                 'resist_earth', 'resist_fire', 'resist_water', 'resist_wind')
        result = {name: sum(self.spells[key].raw['player_policy'].get(name, 0)
            for key, until in (() if state is None else state.buffs.items())
            if until > now and self.spells[key].kind == 'job_stats') for name in names}
        if state is not None and state.elf_element:
            result['resist_' + state.elf_element] += sum(
                self.spells[key].raw['player_policy'].get('own_element_resist', 0)
                for key, until in state.buffs.items() if until > now)
        return result

    def reduction(self, uid, level, now):
        return 1 + max(0, level - 50) // 5 if self.active(uid, 'reduction', now) else 0

    def active(self, uid, kind, now):
        state = self.states.get(uid)
        return state is not None and any(until > now and self.spells[key].kind == kind
                                        for key, until in state.buffs.items())

    def is_lit(self, uid, now):
        return self.active(uid, 'light', now)

    def is_poisoned(self, uid, now):
        state = self.states.get(uid)
        poison = self.npc_poison.get(uid) if state is None else state.poison
        return poison is not None and poison['until'] > now

    def is_invisible(self, uid, now):
        state = self.states.get(uid)
        return (self.npc_invisible.get(uid, {}).get('until', 0) > now if state is None
                else state.invisible_until > now)

    def snapshot(self, uid, now, *, wall=None, learned=None):
        state = self.state(uid)
        row = dict(uid=uid, learned=sorted(state.learned if learned is None else learned),
            buffs=[dict(spell=key, remaining=until - now, **(
                       {'weapon_uid': state.weapon_uids[key]} if key in state.weapon_uids else {}), **(
                       {'armor_uid': state.armor_uids[key]} if key in state.armor_uids else {}), **(
                       {'source_uid': state.buff_sources[key]} if key in state.buff_sources else {}))
                   for key, until in sorted(state.buffs.items()) if until > now],
            reuse_remaining=max(0.0, state.next_cast_at - now),
            saved_at=time.time() if wall is None else wall)
        if state.elf_element is not None:
            row['elf_element'] = state.elf_element
        statuses = {}
        if state.poison is not None and state.poison['until'] > now:
            poison = state.poison
            statuses['poison'] = dict(remaining=poison['until'] - now,
                next_remaining=max(0.0, poison['next_tick'] - now),
                tick_seconds=poison['tick_seconds'], damage=poison['damage'],
                source_uid=poison['source_uid'])
        if state.invisible_until > now:
            statuses['invisible_remaining'] = state.invisible_until - now
        effects = magic_status.snapshot(state.effects, now)
        if effects:
            statuses['effects'] = effects
        if statuses:
            row['statuses'] = statuses
        return row

    def restore(self, uid, row, now, *, wall=None):
        elapsed = max(0.0, (time.time() if wall is None else wall) - row['saved_at'])
        state = MagicState(set(row['learned']), {
            buff['spell']: now + buff['remaining'] - elapsed for buff in row['buffs']
            if buff['remaining'] > elapsed},
            now + max(0.0, row['reuse_remaining'] - elapsed))
        state.elf_element = row.get('elf_element')
        received = {buff['spell']: buff['source_uid'] for buff in row['buffs'] if 'source_uid' in buff}
        need(state.learned <= self.spells.keys()
             and all(key in self.spells and type(source) is int and 0 < source <= 0xffffffff
                     and source != uid and allows_received_buff(self.spells[key])
                     for key, source in received.items())
             and all(key in self.spells and (key in state.learned or key in received)
                     and (self.spells[key].kind in BUFF_KINDS
                     or key in OPTIONAL_BUFF_KEYS and self.spells[key].kind == 'unsupported')
                     for key in state.buffs), 'MAGIC_SAVED_SPELL_UNSUPPORTED')
        state.buff_sources = {key: source for key, source in received.items() if key in state.buffs}
        state.weapon_uids = {buff['spell']: buff['weapon_uid'] for buff in row['buffs']
                             if buff['spell'] in state.buffs and 'weapon_uid' in buff}
        state.armor_uids = {buff['spell']: buff['armor_uid'] for buff in row['buffs']
                            if buff['spell'] in state.buffs and 'armor_uid' in buff}
        statuses = row.get('statuses', {})
        state.effects = magic_status.restore(statuses.get('effects', {}), now, elapsed)
        invisible_remaining = max(0.0, statuses.get('invisible_remaining', 0) - elapsed)
        state.invisible_until = now + invisible_remaining if invisible_remaining else 0.0
        poison = statuses.get('poison')
        if poison is not None and poison['remaining'] > elapsed:
            state.poison = dict(until=now + poison['remaining'] - elapsed,
                # Offline time expires poison but never replays damage on login.
                next_tick=now + (poison['next_remaining'] - elapsed
                    if poison['next_remaining'] > elapsed else poison['tick_seconds']),
                tick_seconds=poison['tick_seconds'], damage=poison['damage'],
                source_uid=poison['source_uid'])
        self.states[uid] = state
        return state


def load_catalog():
    return json.loads((Path(__file__).parent / 'data' / 'm3' / 'player_spells.json')
                      .read_text(encoding='utf-8'))


@cache
def _received_buff_keys():
    return frozenset(key for key, spell in PlayerMagic(load_catalog()).spells.items()
                     if allows_received_buff(spell))


def _row(row):
    required = {'uid', 'learned', 'buffs', 'reuse_remaining', 'saved_at'}
    need(type(row) is dict and required <= set(row) <= required | {'statuses', 'elf_element'}, 'MAGIC_SAVE_SCHEMA')
    need('elf_element' not in row or type(row['elf_element']) is str
         and row['elf_element'] in ELF_ELEMENTS, 'MAGIC_SAVE_ELF_ELEMENT')
    need(type(row['uid']) is int and 0 < row['uid'] <= 0xffffffff,
         'MAGIC_SAVE_CHARACTER')
    need(type(row['learned']) is list and all(type(k) is int and 0 <= k <= 0xffffffff
         for k in row['learned']) and len(set(row['learned'])) == len(row['learned']),
         'MAGIC_SAVE_LEARNED')
    need(type(row['buffs']) is list, 'MAGIC_SAVE_BUFFS')
    def number(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    need(number(row['saved_at']) and number(row['reuse_remaining']), 'MAGIC_SAVE_TIME')
    for buff in row['buffs']:
        need(type(buff) is dict and {'spell', 'remaining'} <= set(buff) <= {
                 'spell', 'remaining', 'weapon_uid', 'armor_uid', 'source_uid'}
             and type(buff['spell']) is int and 0 <= buff['spell'] <= 0xffffffff
             and (buff['spell'] in row['learned'] or 'source_uid' in buff)
             and number(buff['remaining']), 'MAGIC_SAVE_BUFF')
        need('source_uid' not in buff or type(buff['source_uid']) is int
             and 0 < buff['source_uid'] <= 0xffffffff and buff['source_uid'] != row['uid'],
             'MAGIC_SAVE_BUFF_SOURCE')
        need('source_uid' not in buff or buff['spell'] in _received_buff_keys(),
             'MAGIC_SAVE_RECEIVED_BUFF_TARGET')
        need('weapon_uid' not in buff or type(buff['weapon_uid']) is int
             and buff['weapon_uid'] > 0, 'MAGIC_SAVE_WEAPON')
        need('armor_uid' not in buff or type(buff['armor_uid']) is int
             and buff['armor_uid'] > 0, 'MAGIC_SAVE_ARMOR')
    need(len({b['spell'] for b in row['buffs']}) == len(row['buffs']),
         'MAGIC_SAVE_DUPLICATE_BUFF')
    statuses = row.get('statuses', {})
    need(type(statuses) is dict and set(statuses) <= {'poison', 'invisible_remaining', 'effects'},
         'MAGIC_SAVE_STATUSES')
    magic_status.validate(statuses.get('effects', {}))
    need('invisible_remaining' not in statuses or number(statuses['invisible_remaining']),
         'MAGIC_SAVE_INVISIBLE')
    if 'poison' in statuses:
        poison = statuses['poison']
        need(type(poison) is dict and set(poison) == {
            'remaining', 'next_remaining', 'tick_seconds', 'damage', 'source_uid'}
            and all(number(poison[k]) for k in ('remaining', 'next_remaining', 'tick_seconds'))
            and poison['tick_seconds'] > 0 and type(poison['damage']) is int
            and poison['damage'] > 0 and type(poison['source_uid']) is int
            and 0 < poison['source_uid'] <= 0xffffffff, 'MAGIC_SAVE_POISON')
    return row


class MagicStore:
    """One profile's startup cache and interrupted book-learning transaction.

    Ordinary saves never touch inventory. Only learn() participates in the
    existing inventory CAS, and only startup recovery may finish its intent.
    """
    def __init__(self, inventory_store, *, replace_kit=None):
        self.inventory = inventory_store
        # The host supplies its existing equipment-aware kit owner. The same
        # owner is used when startup completes an interrupted learning intent.
        self._replace_kit = replace_kit
        self.path = Path(inventory_store.profile).with_name('magic.json')
        self.intent_path = self.path.with_name('magic-learning.json')
        self.pending = None
        self.rows = {}
        if self.path.exists():
            document = json.loads(self.path.read_text(encoding='utf-8'))
            need(document.get('version') == 1 and type(document.get('rows')) is list,
                 'MAGIC_SAVE_VERSION')
            for raw in document['rows']:
                row = _row(raw)
                need(row['uid'] not in self.rows, 'MAGIC_SAVE_DUPLICATE_CHARACTER')
                self.rows[row['uid']] = row
        if self.intent_path.exists():
            intent = json.loads(self.intent_path.read_text(encoding='utf-8'))
            need(type(intent) is dict and set(intent) == {
                'version', 'before', 'after', 'inventory_before', 'inventory_after'}
                and intent['version'] == 1, 'MAGIC_LEARNING_INTENT_SCHEMA')
            _row(intent['after'])
            if intent['before'] is not None:
                _row(intent['before'])
                need(intent['before']['uid'] == intent['after']['uid'],
                     'MAGIC_LEARNING_CHARACTER')
            self.pending = intent
            self._finish(self.inventory.restore(intent['after']['uid']))

    def _write(self, rows):
        from tools.local_original_session.world_warehouse import _atomic_json
        _atomic_json(self.path, dict(version=1,
            rows=[row for _, row in sorted(rows.items())]))

    def save(self, row):
        _row(row)
        need(self.pending is None, 'MAGIC_LEARNING_RECOVERY_REQUIRED')
        rows = dict(self.rows)
        rows[row['uid']] = row
        self._write(rows)
        self.rows = rows

    def _finish(self, current):
        from tools.local_original_session import inventory
        intent = self.pending
        row, before = intent['after'], intent['before']
        expected, updated = bytes.fromhex(intent['inventory_before']), bytes.fromhex(intent['inventory_after'])
        inventory.validate_kit_frame(expected)
        inventory.validate_kit_frame(updated)
        need(self.rows.get(row['uid']) in (before, row), 'MAGIC_LEARNING_STATE_CONFLICT')
        need(current in (expected, updated), 'MAGIC_LEARNING_INVENTORY_CONFLICT')
        if current == expected:
            replace_kit = self._replace_kit or self.inventory.replace_kit
            need(replace_kit(row['uid'], expected, updated) is True,
                 'MAGIC_LEARNING_PERSISTED_CHANGE_REQUIRED')
        if self.rows.get(row['uid']) != row:
            rows = dict(self.rows)
            rows[row['uid']] = row
            self._write(rows)
            self.rows = rows
        self.intent_path.unlink()
        self.pending = None

    def learn(self, row, expected, updated):
        from tools.local_original_session import inventory
        from tools.local_original_session.world_warehouse import _atomic_json
        _row(row)
        inventory.validate_kit_frame(expected)
        inventory.validate_kit_frame(updated)
        need(self.pending is None, 'MAGIC_LEARNING_RECOVERY_REQUIRED')
        self.pending = dict(version=1, before=self.rows.get(row['uid']), after=row,
                            inventory_before=expected.hex(), inventory_after=updated.hex())
        _atomic_json(self.intent_path, self.pending)
        self._finish(expected)


def book_mutation(frame, item_uid):
    """The existing kit quantity/remove rules, proposed before the joint save."""
    from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
    items = inventory.validate_kit_frame(frame)
    selected = next((item for item in items if item.identifier == item_uid), None)
    need(selected is not None and dict(selected.raw_fields)[4] > 0,
         'MAGIC_OWNED_POSITIVE_BOOK_REQUIRED')
    quantity = dict(selected.raw_fields)[4]
    removed = quantity == 1 and len(items) > 1
    rows = []
    for item in items:
        if item.identifier == item_uid and removed:
            continue
        fields = dict(item.raw_fields)
        if item.identifier == item_uid:
            fields[4] = quantity - 1
        rows.append(fields)
    wire = (item_transfer_protocol.build_remove(uid=item_uid) if removed else
            inventory_update._encode(inventory_update._values({1: item_uid, 4: quantity - 1})))
    return inventory.build_kit_frame(rows), wire


def material_mutation(frame, materials, *, worn=()):
    """Propose positive catalyst debits through the ordinary kit row codecs."""
    from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
    items = inventory.validate_kit_frame(frame)
    rows = [dict(item.raw_fields) for item in items]
    original = {row[1]: dict(row) for row in rows}
    for material in materials:
        remaining = material['count']
        for row in rows:
            if row[1] not in worn and row[2] & 0xffffffff == material['classic_item_key']:
                taken = min(remaining, row[4])
                row[4] -= taken
                remaining -= taken
        need(remaining == 0, 'MAGIC_CURRENT_CATALYST_REQUIRED')
    changed_rows = rows
    rows = [row for row in changed_rows if row[4] > 0 or original[row[1]][4] == 0]
    # Like book_mutation, a completely depleted kit retains one real UID/Q0
    # anchor. Unrelated pre-existing zero rows are never removed by a catalyst.
    if not rows:
        rows = [changed_rows[-1]]
    updated = inventory.build_kit_frame(rows)
    after = {row[1]: row for row in rows}
    frames = []
    for uid, row in original.items():
        if uid not in after:
            frames.append(item_transfer_protocol.build_remove(uid=uid))
        elif row[4] != after[uid][4]:
            frames.append(inventory_update._encode(inventory_update._values({1: uid, 4: after[uid][4]})))
    return updated, tuple(frames)
