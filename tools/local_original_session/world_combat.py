"""World combat: PC->NPC and NPC->PC hit/damage plus the frames they produce.

No combat-adjudication module is integrated under tools/ (its candidates live in
work/.../combat-adjudication and need SelectedStatsSource/owner bindings), so the
arithmetic below is the L1J reference formula taken as LOCAL policy:
l1j-en-classic src/l1j/server/server/model/L1Attack.java
  strHit/dexHit/strDmg tables :172-214, getBasePcHit :378-396,
  calcPcNpcHit :624-657, calcPcBaseDamage :750-796 (dmg<=0 -> miss, :924-940),
  dexDmg :220-248 / ranged status :324 / ammunition die :798-806.
  getNpcHitRate :659-683, calcNpcPcDamage :943-966, calcPcDefense :1106-1110
  (soft-AC divisor per class, classes/L1*ClassFeature.getAcDefenseMax).
Skills, buffs, weight, material/bless bonuses and NPC damage reduction are not
modelled (all zero for the M1 monsters/starter gear).

Frames reuse existing encoders only: SC4E31 kind1 (attack.py/npc_player_hit
layout), SC4E39 Death via npc_death.frame, SC4E38 full SC_STATUS via
hp_status.frame. NPC HP has no verified client display packet (SC_INSTANCE_HP
4EC8 field meaning is UNKNOWN, run27 findings) so none is sent.

Timed speed potions (data/m1/items.json buff/buff_rate, L1J useGreenPotion /
useBravePotion + AcceleratorChecker HASTE_RATE) multiply the PC attack interval
per active buff. The client is told through SC_SPEED_BONUS_NOTI 0x4E5B
(work/local_server_rea_20261016/run206_multi_buff_speed_meditation_contract/
worker/contract.md, run324 MAIN_REVIEW, tools/source_speed_inputs/README.md):
f1 actor UID, f2 Bonus{repeated f1 {f1 key, f2 signed32 value}}; MovingAction
reads key0, AttackAction key1 and divides its base interval by 1 + value/100.
The original server's value producer is not supplied (REA246/324), so the value
is LOCAL policy: round(100 * (1/factor - 1)) of the server interval factor.
The server has no PC move-interval check, so key0 only changes the client.

PC death (HP 0) uses the run102 own-player wires: full SC_STATUS f10=0 through
player_life_codec.full_status, then SC4E39 f1=own UID/f2=raw8 (same bytes as
player_life_codec.death) - work/local_server_rea_20261016/
run102_own_player_death_recovery/findings.md. SC_STATUS f12/f13 are current/max
MP (the project's RESOURCE reading: implementation-2/combat-hp-death/
repeated-player-life/canonical-hp1-input-290-v1). Natural HP/MP recovery follows
data/m1/town.json regen (L1J 1s tick + state points).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import random
import struct

from tools.local_original_session import attack, hp_status, npc_death, player_life_codec
from tools.local_original_session.game_data import M1Data, MonsterDef
from tools.local_original_session.world_ammo import ArrowDef, roll_arrow_damage

POLICY = 'LOCAL_L1J_SIMPLE_MELEE'
ATTACK_OPCODE = 0x4e31
DEATH_OPCODE = npc_death.DEATH_OPCODE
STATUS_OPCODE = hp_status.OPCODE
# Verified manual-play PC feedback (manual-play/item-equipment-runtime-config.json
# attack.feedback): raw_effect 1, direction 8 (current transform), f13 True.
PC_RAW_HIT = 1
PC_DIRECTION = 8
# Local policy: tolerate loopback/scheduling jitter on the client's own swing clock.
PC_ATTACK_GRACE_S = 0.05
MELEE_RANGE = 1
# Naked PC AC 10 (L1J base AC); worn armour adds its (negative) items.json ac.
DEFAULT_PC_AC = 10
# L1J clientpackets/C_ItemUSe.java:2704 healHp *= nextGaussian()/5 + 1 (int cast).
POTION_GAUSS_DIVISOR = 5
# L1J Config.SOFT_AC divisors (classes/L1RoyalClassFeature etc.). 0 royal 1 knight 2 elf 3 wizard.
AC_DEFENSE_DIVISOR = {0: 3, 1: 2, 2: 3, 3: 5}
# Class/gender -> client body sprite (game_data action_speed.pc rows).
PC_SPRITES = {(0, 0): 0, (0, 1): 1, (1, 0): 61, (1, 1): 48, (2, 0): 138, (2, 1): 37}
FALLBACK_ATTACK_MS = 1000  # Wizard sprites are outside M1 data; royal value.
SPEED_OPCODE = 0x4E5B  # SC_SPEED_BONUS_NOTI (work/source_status_integration_research/source.json)
SPEED_MOVE_KEY = 0  # MovingAction949D0 getter axis0 (REA206)
SPEED_ATTACK_KEY = 1  # AttackAction91880 getter axis1 (REA206)

STR_HIT = (-2, -2, -2, -2, -2, -2, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 5, 6, 6, 6,
           7, 7, 7, 8, 8, 8, 9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12,
           13, 13, 13, 14, 14, 14, 15, 15, 15, 16, 16, 16, 17, 17, 17)
DEX_HIT = (-2, -2, -2, -2, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 6, 7, 8, 9, 10, 11,
           12, 13, 14, 15, 16, 17, 18, 19, 19, 19, 20, 20, 20, 21, 21, 21, 22, 22, 22, 23,
           23, 23, 24, 24, 24, 25, 25, 25, 26, 26, 26, 27, 27, 27, 28)


def _str_damage_table():
    table, dmg = [0] * 128, -6
    for value in range(128):
        if value <= 22:
            dmg += value % 2 == 1
        elif value <= 28:
            dmg += value % 3 == 2
        elif value <= 32:
            dmg += value % 2 == 1
        elif value <= 34:
            dmg += 1
        else:
            dmg += (value + 1) % 4 == 0
        table[value] = dmg
    return tuple(table)


STR_DMG = _str_damage_table()


def _dex_damage_table():
    # L1Attack.java:220-248. Ranged status damage is DEX, without melee STR.
    table = [0] * 15 + [1, 2, 3, 4, 4, 4, 5, 5, 5]
    damage = 5
    for value in range(24, 128):
        damage += value % (3 if value <= 35 else 4) == 0
        table.append(damage)
    return tuple(table)


DEX_DMG = _dex_damage_table()


@dataclass(frozen=True, slots=True)
class Weapon:
    name: str
    small: int
    large: int
    hit: int = 0
    damage: int = 0
    enchant: int = 0


FIST = Weapon('fist', 0, 0)
# L1J weapon 137 Athame (l1jdb_m10.sql:63838 dmg 4/4, hitmodifier 2): the local
# $14 Athame mapping already used by athame_policy.
ATHAME = Weapon('athame', 4, 4, hit=2)


def weapon_from_item(item) -> Weapon:
    """game_data.ItemDef (kind weapon) -> combat Weapon (L1J dmg_small/large, hitmodifier)."""
    return Weapon(item.name_ko, item.dmg_small, item.dmg_large, hit=item.hit, damage=item.dmg_bonus)


def potion_heal(base: int, rng: random.Random) -> int:
    """L1J UseHealingPotion amount; Java's compound int assignment truncates toward zero."""
    return max(0, int(base * (rng.gauss(0.0, 1.0) / POTION_GAUSS_DIVISOR + 1.0)))


@dataclass(frozen=True, slots=True)
class PcProfile:
    """Selected character combat inputs (store attributes, SelfInfo level/HP)."""
    level: int
    character_class: int
    gender: int
    strength: int
    dexterity: int
    ac: int = DEFAULT_PC_AC
    weapon: Weapon = FIST
    con: int = 10  # regen inputs (store attributes[2]/[3])
    wis: int = 10

    def attack_interval_s(self, data: M1Data) -> float:
        sprite = PC_SPRITES.get((self.character_class, self.gender))
        row = None if sprite is None else data.action_speed.pc.get(sprite)
        return (FALLBACK_ATTACK_MS if row is None else row.attack_ms) / 1000


@dataclass(frozen=True, slots=True)
class Swing:
    landed: bool
    damage: int


def _clamp(table, value):
    return table[min(max(value, 1), len(table)) - 1]


def _d(rng, n):
    """Java nextInt(n)+1."""
    return rng.randint(1, n)


def pc_hits_npc(pc: PcProfile, monster: MonsterDef, rng: random.Random, *,
                arrow: ArrowDef | None = None) -> Swing:
    weapon = pc.weapon
    hit = pc.level + _clamp(STR_HIT, pc.strength) + _clamp(DEX_HIT, pc.dexterity)
    hit += weapon.hit + (weapon.enchant // 2 if weapon.enchant >= 0 else -((-weapon.enchant) // 2))
    dice = _d(rng, 20) + hit - 10
    defender = 10 - monster.ac
    rate = 0 if dice <= hit - 9 else 100 if dice >= hit + 10 else (100 if dice > defender else 0)
    if rate < _d(rng, 100):
        return Swing(False, 0)
    # Current selected M1/M3 monsters use the local small-target policy.
    # An explicit prepared arrow switches only the base damage calculation:
    # L1J ranged omits the melee weapon die and uses DEX status damage.
    if arrow is None:
        die = 0 if weapon.small <= 0 else _d(rng, weapon.small)
        status_damage = STR_DMG[min(max(pc.strength, 0), 127)]
    else:
        die = roll_arrow_damage(arrow, rng, target_size='small')
        status_damage = DEX_DMG[min(max(pc.dexterity, 0), 127)]
    damage = die + weapon.damage + weapon.enchant + status_damage
    return Swing(True, damage) if damage > 0 else Swing(False, 0)


def npc_hits_pc(monster: MonsterDef, pc: PcProfile, rng: random.Random) -> Swing:
    hit = monster.level
    dice = _d(rng, 20) + hit - 1
    defender = 10 - pc.ac if pc.ac >= 0 else 10 + _d(rng, -pc.ac)
    rate = 0 if dice <= hit else 100 if dice >= hit + 19 else (100 if dice > defender else 0)
    if rate < _d(rng, 100):
        return Swing(False, 0)
    # data damage.min/max == nextInt(level) + str/2 + 1 (monsters.json damage rule).
    damage = rng.randint(monster.damage.min, monster.damage.max)
    ac = max(0, 10 - pc.ac)
    damage -= rng.randint(0, ac // AC_DEFENSE_DIVISOR.get(pc.character_class, 3))
    return Swing(True, max(0, damage))


def attack_frame(attacker_uid: int, target_uid: int, *, raw_effect: int, direction: int,
                 self_action: bool, ranged: bool = False,
                 arrow_id: int = 0, arrow_mode: int = 1) -> bytes:
    """SC4E31 kind1; run384/386 Arrow66 requires present f6/f7.

    f6=0 is the authorized LOCAL presence candidate (Arrow replaces its UID),
    f14=1 is the native default. Raw coordinate fields remain unsupplied.
    """
    fields = [attack._field(1, 1), attack._field(2, attacker_uid), attack._field(3, target_uid),
              attack._field(4, raw_effect), attack._field(5, direction),
              attack.pb.encode_bool(13, self_action)]
    if ranged:
        if not -(1 << 31) <= arrow_id < (1 << 31) or arrow_mode not in (1, 2):
            raise ValueError('WORLD_ARROW_EXPERIMENT_REQUIRED')
        fields.extend((attack._field(6, arrow_id), attack._field(7, 66),
                       attack._field(14, arrow_mode)))
    body = attack.pb.encode_message(fields)
    return struct.pack('<HH', len(body) + 6, ATTACK_OPCODE) + body + b'\0\0'


def death_frame(uid: int) -> bytes:
    return npc_death.frame(DEATH_OPCODE, uid)


def speed_percent(factor: float) -> int:
    """Client bonus value for a server interval factor (local policy; 1.0 -> 0)."""
    return round(100 * (1 / factor - 1))


def speed_frame(uid: int, factor: float) -> bytes:
    """SC4E5B for the PC: the same total bonus on move key0 and attack key1.

    The client replaces existing keys (last value wins), so each frame carries the
    total of all active buffs; expiry sends the new total (0 when none is left).
    """
    percent = speed_percent(factor)
    bonus = b''.join(attack.pb.encode_bytes(1, attack._field(1, key) + attack._field(2, percent))
                     for key in (SPEED_MOVE_KEY, SPEED_ATTACK_KEY))
    body = attack._field(1, uid) + attack.pb.encode_bytes(2, bonus)
    return struct.pack('<HH', len(body) + 6, SPEED_OPCODE) + body + b'\0\0'


def status_frame(fields: dict, current_hp: int) -> bytes:
    values = dict(fields)
    values[10] = current_hp
    if 26 in values:
        # f26 EXP display percent (double): the world codec rejects that fixed
        # scalar, so the same full status goes through world_status_frames'
        # schema encoder. Every later status keeps f26 (an absent optional is
        # copied as the default by the client handler, M1_REWARD_PACKETS 1(1)).
        from tools.local_original_session import world_status_frames
        if not (type(values[10]) is type(values[11]) is int and 0 <= values[10] <= values[11]
                and values[11] > 0):
            raise ValueError('WORLD_STATUS_NONNEGATIVE_FULL_STATUS_REQUIRED')
        return world_status_frames.full_status_frame(values)
    if current_hp <= 0:  # run102: HP0 only through the life codec's full status
        return player_life_codec.full_status(values)
    return hp_status.frame(values)


@dataclass(slots=True)
class PcState:
    profile: PcProfile
    status_fields: dict = field(repr=False)  # f12 tracks current MP
    hp: int
    max_hp: int
    next_attack_at: float = 0.0
    dead: bool = False
    # L1J HpRegeneration/MpRegeneration: lowest state points of the running tick,
    # accumulated points per resource.
    regen_state: int = 0
    hp_points: int = 0
    mp_points: int = 0
    # Timed speed buffs: kind -> (monotonic expiry, interval rate). Dropped on leave.
    buffs: dict = field(default_factory=dict)

    @property
    def mp(self) -> int | None:
        return self.status_fields.get(12)

    @property
    def max_mp(self) -> int | None:
        return self.status_fields.get(13)


@dataclass(frozen=True, slots=True)
class KillEvent:
    """Handed to the kill hook (EXP/drops arrive in step 4)."""
    pc_uid: int
    npc_uid: int
    template_id: int
    kill_exp: int
    map_id: int
    x: int
    y: int
    at: float


class WorldCombat:
    """Owned by WorldView; every call runs under the world lock."""

    def __init__(self, data: M1Data, rng: random.Random | None = None):
        self.data = data
        self.rng = rng if rng is not None else random.Random()
        self.pcs: dict[int, PcState] = {}
        self.on_kill: Callable[[KillEvent], object] | None = None
        self.kills: list[KillEvent] = []  # Bounded log for tests/reports.
        # One HP authority per character for this server lifetime: the bound PC
        # state while selected, its last value after leave. The realm builds the
        # next SelfInfo (SC4E38 field10) from hp_of(), so reselect keeps it.
        self.vitals: dict[int, int] = {}
        self.mana: dict[int, int] = {}  # same for current MP (SC4E38 field12)
        self.regen = data.town.regen

    def bind_pc(self, uid: int, profile: PcProfile, status_fields: dict) -> PcState:
        fields = dict(status_fields)
        hp = min(fields[10], fields[11])
        if 12 in fields and 13 in fields:
            fields[12] = max(0, min(fields[12], fields[13]))
        state = PcState(profile, fields, hp, fields[11], regen_state=self.regen.idle_points)
        self.pcs[uid] = state
        return state

    def forget_pc(self, uid: int) -> bool:
        """Leave: keep HP/MP for the next SelfInfo. A dead PC leaves revived at max
        HP (local policy: restart = new life in town); returns True for that case."""
        state = self.pcs.pop(uid, None)
        if state is None:
            return False
        self.vitals[uid] = state.max_hp if state.dead else state.hp
        if state.mp is not None:
            self.mana[uid] = state.mp
        return state.dead

    def hp_of(self, uid: int) -> int | None:
        state = self.pcs.get(uid)
        return state.hp if state is not None else self.vitals.get(uid)

    def mp_of(self, uid: int) -> int | None:
        state = self.pcs.get(uid)
        return state.mp if state is not None else self.mana.get(uid)

    def is_dead(self, uid: int) -> bool:
        state = self.pcs.get(uid)
        return state is not None and state.dead

    def set_profile(self, uid: int, profile: PcProfile) -> bool:
        """Equipment changed: new weapon/AC for the bound PC; HP and swing clock stay."""
        state = self.pcs.get(uid)
        if state is None:
            return False
        state.profile = profile
        return True

    def heal(self, uid: int, base: int) -> tuple[int, bytes] | None:
        """Potion: L1J heal roll capped at max HP; returns (healed, SC_STATUS frame)."""
        state = self.pcs.get(uid)
        if state is None:
            return None
        if state.dead:  # no heal while dead; the status repeats HP 0
            return 0, status_frame(state.status_fields, state.hp)
        before = state.hp
        state.hp = min(state.max_hp, state.hp + potion_heal(base, self.rng))
        return state.hp - before, status_frame(state.status_fields, state.hp)

    def speed_factor(self, uid: int, now: float) -> float:
        """L1J AcceleratorChecker: each active buff multiplies the action interval."""
        state = self.pcs.get(uid)
        factor = 1.0
        for expires, rate in (() if state is None else state.buffs.values()):
            if expires > now:
                factor *= rate
        return factor

    def apply_buff(self, uid: int, buff, now: float) -> tuple[float, bytes] | None:
        """Speed potion: expiry = now + min(remaining + add_s, cap_s) (L1J Stacking).

        None when the PC is unbound/dead or its class gets no effect (L1J brave
        potion for a non-knight is consumed without effect). Else (expiry, SC4E5B).
        """
        state = self.pcs.get(uid)
        if state is None or state.dead or state.profile.character_class not in buff.classes:
            return None
        expires, _ = state.buffs.get(buff.kind, (now, buff.rate))
        expires = now + min(max(0.0, expires - now) + buff.add_s, buff.cap_s)
        state.buffs[buff.kind] = (expires, buff.rate)
        return expires, speed_frame(uid, self.speed_factor(uid, now))

    def expire_buff(self, uid: int, kind: str, now: float) -> bytes | None:
        """Due expiry: drop the buff and return the new total SC4E5B."""
        state = self.pcs.get(uid)
        entry = None if state is None else state.buffs.get(kind)
        if entry is None or entry[0] > now:
            return None
        del state.buffs[kind]
        return speed_frame(uid, self.speed_factor(uid, now))

    def can_be_attacked(self, uid: int) -> bool:
        state = self.pcs.get(uid)
        return state is not None and not state.dead

    def note_activity(self, uid: int, points: int) -> None:
        """L1J setRegenState: the running tick keeps the lowest state points seen."""
        state = self.pcs.get(uid)
        if state is not None:
            state.regen_state = min(state.regen_state, points)

    def regen_tick(self, uid: int) -> bytes | None:
        """One recovery tick (town.json regen); SC_STATUS frame when HP/MP changed.

        L1J HpRegeneration.run/MpRegeneration.run: points += tick state, state
        resets to idle; at the threshold points reset and the resource recovers,
        capped at max. Dead or unbound PCs do not recover.
        """
        state = self.pcs.get(uid)
        if state is None or state.dead:
            return None
        policy, profile = self.regen, state.profile
        points = state.regen_state
        state.regen_state = policy.idle_points
        state.hp_points += points
        state.mp_points += points
        changed = False
        if state.hp_points >= policy.hp_threshold(profile.level):
            state.hp_points = 0
            if state.hp < state.max_hp:
                state.hp = min(state.max_hp, state.hp + policy.hp_amount(profile.con))
                changed = True
        if state.mp is not None and state.max_mp is not None and state.mp_points >= policy.mp_threshold:
            state.mp_points = 0
            if state.mp < state.max_mp:
                state.status_fields[12] = min(state.max_mp, state.mp + policy.mp_amount(profile.wis))
                changed = True
        return status_frame(state.status_fields, state.hp) if changed else None

    def pc_swing_ready(self, uid: int, now: float) -> bool:
        """Read-only cadence/life admission before committing an arrow cost.

        The caller keeps its world lock through admission, inventory commit and
        try_pc_swing; this method reserves nothing and consumes no RNG.
        """
        state = self.pcs.get(uid)
        return (state is not None and not state.dead and state.hp > 0
                and now + PC_ATTACK_GRACE_S >= state.next_attack_at)

    def try_pc_swing(self, uid: int, monster: MonsterDef, now: float, *,
                     arrow: ArrowDef | None = None) -> Swing | None:
        """None = refused (unbound/dead PC or earlier than the attack interval).

        The caller admits target/range/LOS and commits a prepared arrow's cost
        before passing arrow here. This method never removes inventory items.
        """
        state = self.pcs.get(uid)
        if not self.pc_swing_ready(uid, now):
            return None
        state.next_attack_at = now + state.profile.attack_interval_s(self.data) * self.speed_factor(uid, now)
        state.regen_state = min(state.regen_state, self.regen.attack_points)
        return pc_hits_npc(state.profile, monster, self.rng, arrow=arrow)

    def npc_swing(self, monster: MonsterDef, pc_uid: int) -> tuple[Swing, bytes | None]:
        """Roll one NPC attack; returns the swing and the target's SC_STATUS frame if HP changed.

        HP 0 marks the PC dead (is_dead); the frame is then the HP0 full status.
        """
        state = self.pcs[pc_uid]
        swing = npc_hits_pc(monster, state.profile, self.rng)
        if not swing.landed or swing.damage <= 0:
            return swing, None
        state.hp = max(0, state.hp - swing.damage)
        if state.hp == 0:
            state.dead = True
        return swing, status_frame(state.status_fields, state.hp)

    def record_kill(self, event: KillEvent) -> None:
        self.kills.append(event)
        del self.kills[:-32]
        if self.on_kill is not None:
            self.on_kill(event)
