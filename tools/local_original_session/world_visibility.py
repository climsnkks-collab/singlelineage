"""PC screen visibility (known-set enter/exit) and the broker-facing world view.

Screen test: L1J Point.isInScreen (l1j-en-classic src/l1j/server/server/types/
Point.java:137-155) - tile distance <=13 always, >17 never, otherwise the
diamond |dx+15|+|dy+15| in [17, 43]. No original-client screen range source was
found; this is a reference-server value used as local policy.

Frames reuse existing producers only: monster Actor 0x4E96 through npc.NpcSpawn,
town Actor through the same encode_payload/framing with selected sprite and
unknown optional f39 omitted, Remove 0x4E40 through
npc_death.frame, one-tile move SC4E2C through npc_motion.frame and combat frames
through world_combat. No new opcode, field or sender.

Tick-time changes (AI moves/attacks, corpse removal, respawn) are queued per PC
in ``outbox`` and announced through ``notify(pc_uid)``; the broker drains them
with its normal locked send path. Nothing here awaits or sends.

PC life (GAME_CORE_DESIGN p1 #8, p3 "AI와 타이머"): each bound PC has one
recovery entry on the world scheduler every town.json regen tick (1s). A monster
blow to HP 0 queues the run102 HP0 SC_STATUS + own SC4E39, drops every monster
target on that PC (RETURN) and stops its recovery; the PC stays dead until it
leaves (restart/disconnect), which revives it at max HP for a town respawn.

Kill reward (step 4): world_reward.on_kill on every PC kill -> cumulative EXP,
level/max HP/MP growth on the bound PcState, one full SC4E38 with f26 EXP
percent (world_status_frames; M1_REWARD_PACKETS 1(1)-(2)) and the rolled drops
placed by world_ground_items. Ground items are shown with the existing local
ground Item 4E96 recipe (item_ground PARAMETERS, f3 = client item f6 ground
graphic, data/m1/item_gfx.json) and removed with 4E40, per PC screen like NPCs.
Changed progression is left in ``progress_dirty`` for the broker to persist.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace as _replace
from functools import lru_cache
import json
import logging
from pathlib import Path
import random
import struct
import time

from tools.local_original_session import npc, npc_death, npc_motion, player_life_codec, world_combat
from tools.local_original_session import item_ground, item_ground_wire
from tools.local_original_session.world_ground_items import GroundItem, GroundItems
from tools.local_original_session.world_progress import Progress, exp_percent
from tools.local_original_session.world_reward import RewardPcState, on_kill
from tools.local_original_session.game_data import M1Data, MonsterDef, load_m1
from tools.local_original_session.npc_ai import NpcAi, heading_to, local_line_clear
from tools.local_original_session.world_entities import Entity, EntityRegistry, Kind
from tools.local_original_session.world_interest_spawn import InterestSpawner
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_terrain import WorldTerrain, default_terrain
from tools.local_original_session.world_town import TownAppearance, TownNpcs
from tools.local_movement_session_route.route import authority
from tools.local_game_session import session

POLICY = 'LOCAL_M1_WORLD_INTEREST_SPAWN'
LOG = logging.getLogger(__name__)
ITEM_GFX_PATH = Path(__file__).resolve().parent / 'data' / 'm1' / 'item_gfx.json'
SCREEN_ALWAYS = 13
SCREEN_LIMIT = 17

# Non-identity Actor fields of the existing verified local Monster spawn
# (work/local_original_session/manual-play/item-equipment-runtime-config.json,
# npc.spawn.fields). f1 grid, f2 UID, f3 sprite, f5 heading, f9 name and f39
# template are set per entity; f16=False/f21='' keep the Monster dispatch.
MONSTER_BASE_FIELDS = {
    4: 0, 6: 0, 7: 0, 8: 0, 10: '', 11: 0, 12: 0, 13: 0,
    14: False, 15: False, 16: False, 17: False, 18: False, 19: 0, 20: '', 21: '',
    22: 0, 23: 0, 24: 0, 27: 0, 28: 0,
}


def in_screen(cx: int, cy: int, x: int, y: int) -> bool:
    distance = max(abs(x - cx), abs(y - cy))
    if distance > SCREEN_LIMIT:
        return False
    if distance <= SCREEN_ALWAYS:
        return True
    return 17 <= abs(x - (cx - 15)) + abs(y - (cy - 15)) <= 43


class Visibility:
    """Per-PC known NPC UIDs; diff() yields what to show and what to remove."""

    def __init__(self):
        self.known: dict[int, set[int]] = {}

    def diff(self, pc_uid: int, present: Iterable[Entity], cx: int, cy: int):
        seen = {entity.uid: entity for entity in present if in_screen(cx, cy, entity.x, entity.y)}
        known = self.known.setdefault(pc_uid, set())
        enter = [seen[uid] for uid in sorted(seen.keys() - known)]
        leave = sorted(known - seen.keys())
        known.difference_update(leave)
        known.update(seen)
        return enter, leave

    def forget(self, pc_uid: int) -> None:
        self.known.pop(pc_uid, None)


def monster_fields(entity: Entity, monster: MonsterDef) -> dict:
    fields = dict(MONSTER_BASE_FIELDS)
    fields.update({1: authority.pack_grid(entity.x, entity.y), 2: entity.uid, 3: monster.sprite_id,
                   5: entity.heading, 9: monster.name_ko, 39: monster.template_id})
    return fields


def spawn_frame(entity: Entity, monster: MonsterDef) -> bytes:
    spawn = npc.NpcSpawn(monster_fields(entity, monster), map_id=entity.map_id, policy=npc.WORLD_POLICY)
    return spawn.encode()  # npc.source_ready() ran once when the view was built.


def remove_frame(uid: int) -> bytes:
    return npc_death.frame(npc_death.REMOVE_OPCODE, uid)


def town_spawn_frame(entity: Entity, appearance: TownAppearance) -> bytes:
    """Existing Actor codec/framing, with selected town catalog appearance only.

    Catalog identity is metadata, not evidence for wire f39. Leave that optional
    field absent while its source is unknown. This packet does not establish
    the sprite's input dispatch, dialogue resources or native rendering.
    """
    if appearance.sprite_id is None:
        raise ValueError('TOWN_NPC_SPRITE_UNSELECTED')
    fields = dict(MONSTER_BASE_FIELDS)
    fields.update({1: authority.pack_grid(entity.x, entity.y), 2: entity.uid,
                   3: appearance.sprite_id, 5: entity.heading, 9: appearance.name})
    if appearance.wire_f39 is not None:
        fields[39] = appearance.wire_f39
    body = session.world.encode_payload(0x4e96, fields)
    return struct.pack('<HH', len(body) + 6, 0x4e96) + body + b'\0\0'


@lru_cache(maxsize=1)
def item_gfx() -> dict[int, tuple[int, int]]:
    """item id -> (inventory icon f5, ground graphic f6) from data/m1/item_gfx.json."""
    raw = json.loads(ITEM_GFX_PATH.read_text(encoding='utf-8'))
    return {int(key): (row['icon'], row['ground']) for key, row in raw['items'].items()}


def ground_frame(item: GroundItem) -> bytes:
    """Ground Item 4E96: the existing local14 recipe with f3 = the item's ground graphic.

    item_ground.PARAMETERS supplies the nineteen remaining required fields;
    f4 action 0, f5 direction 0, f16 False and explicit f39 0 are the same local
    profile values (item_ground.PROFILE). item_ground_wire.source_ready() ran
    once at view creation; per item only the typed candidate is encoded.
    """
    fields = item_ground.PARAMETERS + (
        (1, authority.pack_grid(item.x, item.y)), (2, item.ref.uid), (3, item_gfx()[item.item_id][1]),
        (4, 0), (5, 0), (7, item.count), (16, False), (39, 0))
    candidate = item_ground_wire.ActorNoticeCandidate(tuple(sorted(fields)))
    body = item_ground_wire._payload(candidate.fields, item_ground_wire.KINDS)
    return struct.pack('<HH', len(body) + 6, item_ground_wire.OPCODE) + body + b'\0\0'


class WorldView:
    """Spawner + visibility + AI + combat for selected PCs. Call under the world lock only."""

    def __init__(self, runtime: WorldRuntime, spawner: InterestSpawner,
                 terrain: WorldTerrain | None = None, *, data: M1Data | None = None,
                 rng: random.Random | None = None):
        self.runtime, self.spawner = runtime, spawner
        self.town: TownNpcs | None = None  # broker registers under the same world lock
        # Static S32 mask1 terrain: can_stand for spawns, can_step for NPC moves.
        self.terrain = terrain
        self.visibility = Visibility()
        self.pcs: dict[int, tuple[int, int, int]] = {}
        self.closed = False
        self.data = data if data is not None else load_m1()
        self.combat = world_combat.WorldCombat(self.data, rng)
        self.ai = NpcAi(self, rng) if terrain is not None else None
        self.outbox: dict[int, list[bytes]] = {}
        self.notify = None  # callable(pc_uid), set by the broker; called under the world lock
        self.regen: dict[int, object] = {}  # pc uid -> scheduler Handle of its next recovery tick
        self.buffs: dict[tuple[int, str], object] = {}  # (pc uid, buff kind) -> expiry Handle
        passable = terrain.passable if terrain is not None else (lambda *_: True)
        self.ground = GroundItems(runtime.entities, runtime.scheduler, self.data, passable=passable)
        self.ground.on_remove = self._ground_removed
        self.item_known: dict[int, set[int]] = {}  # pc uid -> ground item UIDs its client shows
        self.exp: dict[int, int] = {}  # pc uid -> saved cumulative EXP while bound
        self.progress_dirty: dict[int, Progress] = {}  # changed by kills, persisted by the broker
        self.reward_errors: list[str] = []
        self.on_pc_death = None  # callable(pc_uid), before own death frame, under world lock
        self.prepare_pc_attack = None  # callable(pc_uid, target_entity, now) -> preparation or None
        self.on_npc_hit = None  # callable(npc_uid), after positive damage, including death
        self.arrow_id, self.arrow_mode = 0, 1  # run386 LOCAL f6 candidate / native enum default
        runtime.add_tick_hook(self.tick)

    @classmethod
    def create(cls, *, data: M1Data | None = None, terrain: WorldTerrain | None = None,
               passable=None, clock=time.monotonic,
               rng: random.Random | None = None) -> 'WorldView':
        """``passable`` overrides placement only (tests); default is terrain.passable."""
        npc.source_ready()  # Existing SPR56/template0 + dispatch source contract, once.
        npc_death.source_ready()
        npc_motion.source_ready(npc_motion.LOCAL_PRE_STEP)
        world_combat.hp_status.source_ready()
        world_combat.attack.source_ready()
        item_ground_wire.source_ready()  # ground Item 4E96 recipe contract, once
        item_gfx()
        if terrain is None:
            terrain = default_terrain()
        data = data if data is not None else load_m1()
        runtime = WorldRuntime(clock=clock)
        spawner = InterestSpawner(runtime.entities, data,
                                  passable=passable if passable is not None else terrain.passable,
                                  rng=rng)
        return cls(runtime, spawner, terrain, data=data, rng=rng)

    @property
    def entities(self) -> EntityRegistry:
        return self.runtime.entities

    def close(self) -> None:
        """Stop tick changes and release owned town placements before runtime stop.

        Broker selection cleanup still owns PC persistence and leave_pc; do not
        drop those states here before its final save.
        """
        self.closed = True
        if self.town is not None:
            self.town.close()

    # ---- outbox ------------------------------------------------------------
    def _queue(self, pc_uid: int, frame: bytes) -> None:
        self.outbox.setdefault(pc_uid, []).append(frame)

    def _announce(self) -> None:
        if self.notify is None:
            return
        for pc_uid, frames in tuple(self.outbox.items()):
            if frames:
                self.notify(pc_uid)

    def drain(self, pc_uid: int) -> list[bytes]:
        return self.outbox.pop(pc_uid, [])

    def _watchers(self, entity: Entity) -> list[int]:
        """PCs whose client currently shows this NPC."""
        return [pc_uid for pc_uid in self.pcs if entity.uid in self.visibility.known.get(pc_uid, ())]

    # ---- tick --------------------------------------------------------------
    def tick(self, now: float) -> None:
        if self.closed:
            return
        if self.spawner.tick(now):  # corpse removal (0x4E40) / respawn (0x4E96)
            for pc_uid in tuple(self.pcs):
                for frame in self._refresh(pc_uid):
                    self._queue(pc_uid, frame)
        if self.ai is not None:
            self.ai.sync(now)
        self._announce()

    def _present(self, pc_uid: int, map_id: int, x: int, y: int) -> list[Entity]:
        known = self.visibility.known.get(pc_uid, ())
        # A corpse stays shown to PCs that saw it alive; it never enters as a new actor.
        present = [entity for entity in self.entities.near(map_id, x, y, SCREEN_LIMIT, kind=Kind.NPC,
                                                           alive_only=False)
                   if self.spawner.visible(entity.uid) and (entity.alive or entity.uid in known)]
        if self.town is not None:
            present.extend(entity for entity in self.town.present(map_id, x, y, SCREEN_LIMIT)
                           if self.town.appearance(entity.uid).sprite_id is not None)
        return present

    def _spawn_frame(self, entity: Entity) -> bytes:
        appearance = self.town.appearance(entity.uid) if self.town is not None else None
        if appearance is not None:
            return town_spawn_frame(entity, appearance)
        return spawn_frame(entity, self.spawner.monster_for(entity.uid))

    def _refresh(self, pc_uid: int) -> list[bytes]:
        map_id, x, y = self.pcs[pc_uid]
        enter, leave = self.visibility.diff(pc_uid, self._present(pc_uid, map_id, x, y), x, y)
        return ([remove_frame(npc_uid) for npc_uid in leave]
                + [self._spawn_frame(entity) for entity in enter]
                + self._refresh_items(pc_uid, map_id, x, y))

    # ---- ground items ------------------------------------------------------
    def _refresh_items(self, pc_uid: int, map_id: int, x: int, y: int) -> list[bytes]:
        known = self.item_known.setdefault(pc_uid, set())
        seen = {}
        for entity in self.entities.near(map_id, x, y, SCREEN_LIMIT, kind=Kind.ITEM):
            if in_screen(x, y, entity.x, entity.y):
                item = self.ground.get(entity.ref)
                if item is not None:
                    seen[entity.uid] = item
        leave = sorted(known - seen.keys())
        enter = [seen[uid] for uid in sorted(seen.keys() - known)]
        known.difference_update(leave)
        known.update(seen)
        return [remove_frame(uid) for uid in leave] + [ground_frame(item) for item in enter]

    def _show_items(self, items) -> None:
        for pc_uid, (map_id, x, y) in self.pcs.items():
            known = self.item_known.setdefault(pc_uid, set())
            for item in items:
                if item.map_id == map_id and in_screen(x, y, item.x, item.y) and item.ref.uid not in known:
                    known.add(item.ref.uid)
                    self._queue(pc_uid, ground_frame(item))

    def _ground_removed(self, item: GroundItem) -> None:
        """Final pickup / 600 s expiry: 4E40 to every PC whose client shows it."""
        for pc_uid in self.pcs:
            known = self.item_known.get(pc_uid)
            if known is not None and item.ref.uid in known:
                known.discard(item.ref.uid)
                self._queue(pc_uid, remove_frame(item.ref.uid))

    def pc_pickup(self, pc_uid: int, item_uid: int, quantity: int, commit) -> list[bytes] | None:
        """CS4E3E on a world ground item (dispatch_now). None = not a world item.

        ``commit(item, count)`` is the caller's synchronous durable inventory
        insert returning its frames; it runs before the ground is consumed, so a
        failed insert (exception) leaves the item on the ground. Refused pickups
        (owner priority, distance, expiry, dead PC) return only queued frames.
        """
        entity = self.entities.get(item_uid)
        if entity is None or entity.kind is not Kind.ITEM:
            return None
        pc = self.entities.get(pc_uid)
        item = self.ground.get(entity.ref)
        if pc is None or item is None or pc_uid not in self.pcs or self.combat.is_dead(pc_uid):
            return self.drain(pc_uid)
        count = quantity if 0 < quantity <= item.count else item.count
        now = self.runtime.clock()  # one approval instant across the synchronous durable insert
        try:
            self.ground.check_pickup(pc.ref, item.ref, count, now=now)
        except ValueError:
            return self.drain(pc_uid)
        inventory_frames = list(commit(item, count))
        self.ground.pickup(pc.ref, item.ref, count, now=now)  # final pickup queues 4E40 via on_remove
        frames = self.drain(pc_uid) + inventory_frames
        self._announce()
        return frames

    # ---- PCs ---------------------------------------------------------------
    def update_pc(self, uid: int, map_id: int, x: int, y: int, *, reset: bool = False) -> list[bytes]:
        """Register/move the PC, refresh group interest, return exit+enter frames."""
        entities = self.entities
        entity = entities.get(uid)
        if entity is None:
            entities.add(Kind.PC, map_id, x, y, uid=uid)  # Existing profile UID.
        elif not entity.alive:
            entities.activate_pc(uid, map_id, x, y)
        else:
            entities.move(uid, map_id, x, y)
        if not reset and self.pcs.get(uid) not in (None, (map_id, x, y)):
            self.combat.note_activity(uid, self.combat.regen.move_points)
        if reset:
            self.visibility.forget(uid)  # New world entry: client starts with no NPCs.
            self.item_known.pop(uid, None)
            self.outbox.pop(uid, None)
        self.pcs[uid] = (map_id, x, y)
        now = self.runtime.clock()
        self.spawner.update_interest(self.pcs.values(), now)
        if self.ai is not None:
            self.ai.sync(now)
        return self._refresh(uid)

    def update_pc_and_drain(self, uid: int, map_id: int, x: int, y: int, *,
                            reset: bool = False) -> list[bytes]:
        """Queued tick frames first (older, already reflected in known), then this diff."""
        frames = self.update_pc(uid, map_id, x, y, reset=reset)
        return self.drain(uid) + frames

    def bind_pc(self, uid: int, profile: world_combat.PcProfile, status_fields: dict,
                exp: int = 0) -> bytes | None:
        """Bind combat state. With saved EXP, returns one full SC4E38 carrying the
        f26 EXP percent (SelfInfo has none); a fresh EXP-0 PC keeps the default
        0% display and gets f26 with its first kill status."""
        fields = dict(status_fields)
        if exp > 0:
            fields[26] = exp_percent(self.data, exp, profile.level)
        state = self.combat.bind_pc(uid, profile, fields)
        self.exp[uid] = exp
        self._schedule_regen(uid, self.runtime.clock() + self.combat.regen.tick_ms / 1000)
        return world_combat.status_frame(state.status_fields, state.hp) if exp > 0 else None

    def leave_pc(self, uid: int) -> bool:
        """Drop the PC; True when it left dead (revived at max HP, respawn in town)."""
        self._stop_regen(uid)
        for key in [key for key in self.buffs if key[0] == uid]:
            self.runtime.scheduler.cancel(self.buffs.pop(key))  # buffs end with the selection
        self.pcs.pop(uid, None)
        self.visibility.forget(uid)
        self.item_known.pop(uid, None)
        self.outbox.pop(uid, None)
        self.exp.pop(uid, None)
        dead = self.combat.forget_pc(uid)
        entity = self.entities.get(uid)
        if entity is not None and entity.kind is Kind.PC:
            self.runtime.scheduler.cancel_owner(entity.ref)
            self.entities.deactivate_pc(uid)
        now = self.runtime.clock()
        self.spawner.update_interest(self.pcs.values(), now)
        if self.ai is not None:
            self.ai.sync(now)
        return dead

    # ---- PC recovery / death -----------------------------------------------
    def _schedule_regen(self, uid: int, at: float) -> None:
        self._stop_regen(uid)
        self.regen[uid] = self.runtime.scheduler.schedule(
            at, None, 'pc_regen', lambda now: self._regen_tick(uid, at, now))

    def _stop_regen(self, uid: int) -> None:
        handle = self.regen.pop(uid, None)
        if handle is not None:
            self.runtime.scheduler.cancel(handle)

    def _regen_tick(self, uid: int, due: float, now: float) -> None:
        self.regen.pop(uid, None)
        if self.closed or uid not in self.combat.pcs or self.combat.is_dead(uid):
            return
        frame = self.combat.regen_tick(uid)
        if frame is not None:
            self._queue(uid, frame)
        tick = self.combat.regen.tick_ms / 1000
        # Only one runtime polling interval counts as ordinary jitter. Larger
        # delays rebase, even before a whole recovery interval was missed, so
        # an overdue callback cannot compress the next recovery into a burst.
        jitter = self.runtime.tick_interval + 1e-9  # tolerate float clock addition
        next_at = due + tick if now - due <= jitter else now + tick
        self._schedule_regen(uid, next_at)

    # ---- timed speed potions ----------------------------------------------
    def apply_buff(self, uid: int, buff) -> bytes | None:
        """Player potion (dispatch_now): new expiry on the world scheduler; SC4E5B or None."""
        now = self.runtime.clock()
        result = self.combat.apply_buff(uid, buff, now)
        if result is None:
            return None
        expires, frame = result
        key = (uid, buff.kind)
        old = self.buffs.pop(key, None)
        if old is not None:
            self.runtime.scheduler.cancel(old)
        self.buffs[key] = self.runtime.scheduler.schedule(
            expires, None, 'pc_buff', lambda now: self._buff_expired(uid, buff.kind, now))
        return frame

    def _buff_expired(self, uid: int, kind: str, now: float) -> None:
        self.buffs.pop((uid, kind), None)
        if self.closed:
            return
        frame = self.combat.expire_buff(uid, kind, now)
        if frame is not None:
            self._queue(uid, frame)  # announced by the tick hook, like recovery

    def _pc_died(self, pc_uid: int, now: float) -> None:
        """HP 0: own SC4E39 after the HP0 status, recovery stops, monsters let go."""
        if self.on_pc_death is not None:
            self.on_pc_death(pc_uid)
        self._queue(pc_uid, player_life_codec.death(pc_uid))
        self._stop_regen(pc_uid)
        if self.ai is not None:
            self.ai.release_target(pc_uid, now)

    # ---- NPC actions (AI scheduler callbacks) ------------------------------
    def npc_step(self, entity: Entity, x: int, y: int, heading: int) -> None:
        """Move one tile and update every PC's screen: SC4E2C, or exit/enter."""
        fx, fy = entity.x, entity.y
        self.entities.move(entity.uid, entity.map_id, x, y, heading)
        move = None
        for pc_uid, (map_id, px, py) in self.pcs.items():
            known = self.visibility.known.setdefault(pc_uid, set())
            inside = map_id == entity.map_id and in_screen(px, py, x, y)
            if entity.uid in known:
                if inside:
                    if move is None:  # npc_motion.LOCAL_PRE_STEP: report the start grid
                        move = npc_motion.frame(entity.uid, authority.pack_grid(fx, fy), heading)
                    self._queue(pc_uid, move)
                else:
                    known.discard(entity.uid)
                    self._queue(pc_uid, remove_frame(entity.uid))
            elif inside:
                known.add(entity.uid)
                self._queue(pc_uid, self._spawn_frame(entity))

    def npc_attack(self, entity: Entity, monster: MonsterDef, pc_uid: int, now: float) -> None:
        """One monster swing: SC4E31 to watchers, SC4E38 HP to the target when it lands."""
        pc = self.entities.get(pc_uid)
        heading = heading_to(entity.x, entity.y, pc.x, pc.y)
        self.entities.move(entity.uid, entity.map_id, entity.x, entity.y, heading)
        swing, status = self.combat.npc_swing(monster, pc_uid)
        # npc_player_hit layout: f13 False; raw f4 positive only when it lands (run27 gate).
        frame = world_combat.attack_frame(entity.uid, pc_uid, raw_effect=1 if swing.landed else 0,
                                          direction=heading, self_action=False,
                                          ranged=monster.template_id == 1 and monster.attack_range > 1,
                                          arrow_id=self.arrow_id, arrow_mode=self.arrow_mode)
        for watcher in self._watchers(entity):
            self._queue(watcher, frame)
        if status is not None:
            self._queue(pc_uid, status)
        if self.combat.is_dead(pc_uid):
            self._pc_died(pc_uid, now)

    # ---- kill reward -------------------------------------------------------
    def _reward(self, pc_uid: int, corpse: Entity, monster: MonsterDef, now: float) -> None:
        """EXP/growth -> PcState + one full SC4E38 to the killer; drops -> ground."""
        state = self.combat.pcs.get(pc_uid)
        if state is None or pc_uid not in self.exp:
            return
        try:
            reward = on_kill(RewardPcState.from_combat(state, exp=self.exp[pc_uid]), monster,
                             self.combat.rng, data=self.data)
        except ValueError as error:
            self.reward_errors = (self.reward_errors + [str(error)])[-8:]
            return
        self.exp[pc_uid] = reward.new_exp
        if reward.level_ups:
            state.profile = _replace(state.profile, level=reward.new_level)
            state.max_hp = reward.max_hp
        fields = state.status_fields
        fields.update({2: reward.new_level, 11: reward.max_hp,
                       26: exp_percent(self.data, reward.new_exp, reward.new_level)})
        if reward.max_mp is not None:
            fields[13] = reward.max_mp
        # Local policy: no level-up refill (current HP/MP unchanged).
        refresh_stats = getattr(self, 'on_stats_changed', None)
        if refresh_stats is not None:
            refresh_stats(pc_uid)
        self._queue(pc_uid, world_combat.status_frame(fields, state.hp))
        self.progress_dirty[pc_uid] = Progress(reward.new_exp, reward.new_level, reward.max_hp,
                                               reward.max_mp)
        if reward.drops:
            try:
                items = self.ground.spawn_reward(corpse.ref, reward, owner_uid=pc_uid, now=now)
            except ValueError as error:  # e.g. no passable neighbour tile: no loot
                self.reward_errors = (self.reward_errors + [str(error)])[-8:]
                return
            self._show_items(items)

    # ---- PC attack (player request through dispatch_now) -------------------
    def pc_attack(self, pc_uid: int, target_uid: int) -> list[bytes] | None:
        """Immediate PC swing; None when the target is not a world monster.

        Returns the attacker's frames (older queued frames first). Refused swings
        (dead/far target, earlier than the class attack interval) add nothing.
        """
        found = self.spawner.slot_for(target_uid)
        if found is None:
            return None
        now = self.runtime.clock()
        group, slot = found
        target, pc = self.entities.get(target_uid), self.entities.get(pc_uid)
        if (target is None or not target.alive or pc is None or pc_uid not in self.pcs
                or self.combat.is_dead(pc_uid) or pc.map_id != target.map_id):
            return self.drain(pc_uid)
        if (self.prepare_pc_attack is None
                and max(abs(pc.x - target.x), abs(pc.y - target.y)) > world_combat.MELEE_RANGE):
            return self.drain(pc_uid)
        # Consume the same conservative LOCAL static edges as NPC attacks before
        # RNG/cooldown/reward. Original projectile and dynamic-door LOS is unsupplied.
        if not local_line_clear(self.terrain, pc.map_id, pc.x, pc.y, target.x, target.y):
            return self.drain(pc_uid)
        if not self.combat.pc_swing_ready(pc_uid, now):
            return self.drain(pc_uid)
        arrow = None
        if self.prepare_pc_attack is not None:
            prepared = self.prepare_pc_attack(pc_uid, target, now)
            if prepared is None or not prepared.allowed:
                return self.drain(pc_uid)
            arrow = prepared.arrow
        swing = self.combat.try_pc_swing(pc_uid, group.monster, now, arrow=arrow)
        if swing is None:
            return self.drain(pc_uid)
        raw = world_combat.PC_RAW_HIT if swing.landed else 0
        for watcher in self.pcs:
            if watcher == pc_uid or target.uid in self.visibility.known.get(watcher, ()):
                self._queue(watcher, world_combat.attack_frame(
                    pc_uid, target.uid, raw_effect=raw, direction=world_combat.PC_DIRECTION,
                    self_action=watcher == pc_uid, ranged=arrow is not None,
                    arrow_id=self.arrow_id, arrow_mode=self.arrow_mode))
        if swing.landed and slot.hp - swing.damage <= 0:
            watchers = self._watchers(target)
            if self.ai is not None:
                self.ai.drop(target.uid)
            self.runtime.scheduler.cancel_owner(target.ref)
            self.spawner.mark_dead(target.uid, now)  # corpse until corpse_at, then 0x4E40
            if swing.damage > 0 and self.on_npc_hit is not None:
                self.on_npc_hit(target.uid)
            death = world_combat.death_frame(target.uid)
            for watcher in watchers:
                self._queue(watcher, death)
            self.combat.record_kill(world_combat.KillEvent(
                pc_uid, target.uid, group.monster.template_id, group.monster.kill_exp,
                target.map_id, target.x, target.y, now))
            self._reward(pc_uid, target, group.monster, now)
        else:
            if swing.landed:
                self.spawner.set_hp(target.uid, slot.hp - swing.damage)
                if swing.damage > 0 and self.on_npc_hit is not None:
                    self.on_npc_hit(target.uid)
            if self.ai is not None:
                self.ai.on_hit(target.uid, pc_uid, now)
        frames = self.drain(pc_uid)
        self._announce()
        return frames
