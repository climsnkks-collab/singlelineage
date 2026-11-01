"""Optional shared autonomous-actor runtime used by companion and pet features.

The world core owns entities, scheduler, combat and reward order. This explicit
startup installation owns follower state/AI and subscribes to the core's event
contracts. A world without this service imports or creates no followers.
Compatibility view/combat method names are installed through a checked API once.
"""
from __future__ import annotations

from dataclasses import replace as _replace
import logging
import uuid
from types import MethodType

from tools.local_original_session import world_combat
from tools.local_original_session.world_companion import WorldCompanions, split_exp
from tools.local_original_session.companion_ai import CompanionAI
from tools.local_original_session.npc_ai import heading_to, local_line_clear
from tools.local_original_session.world_entities import Entity, Kind
from tools.local_original_session.game_data import MonsterDef
from tools.local_original_session.world_combat import PcProfile, Swing
from tools.local_original_session.world_reward import RewardPcState, on_kill
from tools.local_original_session.world_visibility import (companion_spawn_frame, remove_frame, in_screen)

LOG = logging.getLogger(__name__)
# Fallback wizard-staff nominal timing (list.spr 50.walk/51.attack staff).
# A feature may install view.companion_intervals(runtime) -> (walk_s, attack_s)
# from its class/weapon data and current speed effects.
COMPANION_STAFF_WALK = 16 / 24
COMPANION_STAFF_ATTACK = 28 / 24


def _interval(view, runtime, index):
    provider = getattr(view, 'companion_intervals', None)
    value = None if provider is None else provider(runtime)
    if value is None:
        return (COMPANION_STAFF_WALK, COMPANION_STAFF_ATTACK)[index]
    return value[index]


def _install_methods(target, methods):
    for function in methods:
        if hasattr(target, function.__name__):
            raise ValueError('DUPLICATE_FOLLOWER_API:' + function.__name__)
        setattr(target, function.__name__, MethodType(function, target))


def install_companion_runtime(view):
    """Install once for either feature, before PCs/runtime start. Return the view API."""
    if 'followers' in view.extensions:
        return view.extensions['followers']
    runtime = view.runtime
    view.companions = WorldCompanions(runtime.entities, runtime.scheduler,
        release_target=lambda uid, now: view.ai.release_target(uid, now) if view.ai else None)
    _install_methods(view, (_save_companion, _companion_removed, dismiss_companions, summon_companion, _npc_attack_companion, companion_attack))
    _install_methods(view.combat, (companion_swing, npc_companion_swing, npc_companion_magic_swing))
    view.companions.on_remove = view._companion_removed
    view.combat.companions = view.companions
    view.companion_profiles = {}
    view.companion_looks = {}
    view.companion_owner_half = {}
    view.companion_reward_receipts = []
    view.companion_reward_epoch = uuid.uuid4().hex
    view.companion_save = None
    view.companion_save_errors = []
    view.companion_intervals = None
    view.companion_max_active = 1
    # Optional feature callback(owner_uid, now) -> character IDs it keeps after
    # the owner's death (scroll return / wait in place). Others are dismissed.
    view.companion_owner_death = None
    runtime.precise_kinds.add('companion_ai')
    view.companion_ai = CompanionAI(view, move_interval=lambda rt: _interval(view, rt, 0),
        attack_interval=lambda rt: _interval(view, rt, 1), tick_interval=runtime.tick_interval,
        attack_consumer=view.companion_attack, move_consumer=view.npc_step,
        wake=runtime.request_wake)
    view.extensions['followers'] = view
    events = view.events
    events.add('followers', 'ai_target', view.companions.can_be_attacked)
    events.add('followers', 'pc_attack_target',
               lambda target_uid, pc_uid: _pc_attack_target(view, pc_uid, target_uid))
    events.add('followers', 'tick', view.companion_ai.sync, isolate=True)
    events.add('followers', 'close', lambda: _close(view), priority=10)
    events.add('followers', 'visible_entities', lambda *args: _present(view, *args))
    events.add('followers', 'spawn_frame', lambda entity: _spawn(view, entity), priority=10)
    events.add('followers', 'before_map_change', lambda uid: _depart(view, uid))
    events.add('followers', 'before_pc_leave', lambda uid: _leave(view, uid))
    events.add('followers', 'pc_death', lambda uid: _owner_death(view, uid))
    events.add('followers', 'npc_target_attack', lambda *args: _npc_target(view, *args))
    events.add('followers', 'pc_hit', view.companion_ai.on_hit, isolate=True)
    events.add('followers', 'npc_died', view.companion_ai.release_target, isolate=True)
    events.add('followers', 'pc_attack_started', view.companion_ai.owner_attacked, isolate=True)
    events.add('followers', 'reward_plan', lambda *args: _reward_plan(view, *args))
    events.add('followers', 'reward_committed', view._save_companion)
    view.combat.events.add('followers', 'can_be_attacked', view.companions.can_be_attacked)
    return view


def _pc_attack_target(view, pc_uid, target_uid):
    """LOCAL owner click policy; keep ordinary attack admission and swings intact."""
    rt = view.companions.retained_actor(target_uid)
    if rt is None or rt.owner_ref.uid != pc_uid or '_pet' in rt.record.equipment:
        return target_uid
    pc, actor = view.entities.get(pc_uid), view.entities.resolve(rt.ref)
    if (pc is None or pc.ref != rt.owner_ref or not pc.alive
            or actor is None or not actor.alive or not rt.record.alive or rt.record.hp <= 0
            or pc.map_id != actor.map_id):
        return None

    def living_monster(entity):
        if (entity is None or not entity.alive or entity.kind is not Kind.NPC
                or entity.map_id != pc.map_id
                or view.companions.retained_actor(entity.uid) is not None):
            return False
        found = view.spawner.slot_for(entity.uid)
        return found is not None and found[0].active and found[1].hp > 0

    target = None if rt.target is None else view.entities.resolve(rt.target)
    if living_monster(target):
        return target.uid
    nearby = [entity.uid for entity in view.entities.near(
        actor.map_id, actor.x, actor.y, 1, kind=Kind.NPC) if living_monster(entity)]
    return nearby[0] if len(nearby) == 1 else None


def _close(view):
    for actor in tuple(view.companions.active.values()):
        view.companions.dismiss(actor.character_id)


def _strand(view, uid):
    """A member waiting by its dead owner's body is left behind on departure."""
    for actor in tuple(view.companions.active.values()):
        if actor.owner_ref.uid == uid and actor.owner_down:
            actor.record.summoned = False


def _depart(view, uid):
    _strand(view, uid)
    view.dismiss_companions(uid)


def _leave(view, uid):
    _depart(view, uid)
    view._save_companion(uid)


def _owner_death(view, uid):
    handler = view.companion_owner_death
    kept = set(handler(uid, view.runtime.clock()) if handler is not None else ())
    for actor in tuple(view.companions.active.values()):
        if actor.owner_ref.uid == uid and actor.character_id not in kept:
            view.companions.dismiss(actor.character_id)


def _present(view, pc_uid, map_id, x, y, known):
    return tuple(entity for actor in view.companions.active.values()
                 if (entity := view.entities.get(actor.ref.uid)) is not None
                 and entity.map_id == map_id and (entity.alive or entity.uid in known)
                 and in_screen(x, y, entity.x, entity.y))


def _spawn(view, entity):
    companion = view.companions.retained_actor(entity.uid)
    if companion is not None:
        return companion_spawn_frame(entity, view.companion_looks[companion.character_id])
    return None


def _npc_target(view, entity, monster, target_uid, now):
    companion = view.companions.get_actor(target_uid)
    if companion is None:
        return False
    view._npc_attack_companion(entity, monster, companion, now)
    return True


class FollowerRewardPlan:
    def __init__(self, view, pc_uid, corpse, monster, member, split):
        self.view, self.pc_uid, self.corpse = view, pc_uid, corpse
        self.monster, self.member, self.split = monster, member, split
        self.allocated = _replace(monster, kill_exp=split.owner_exp)
        self.growth = None

    def calculate(self):
        view, record, split = self.view, self.member.record, self.split
        profile = _replace(view.companion_profiles[record.character_id], level=record.level)
        bags = getattr(view.companion_ai, 'inventory', None)
        row = None if bags is None else bags.characters.get(record.character_id)
        attributes = None if row is None else row['attributes']
        self.growth = on_kill(RewardPcState.from_companion(record, profile, attributes=attributes),
            _replace(self.monster, template_id=-1, kill_exp=split.companion_exp),
            view.combat.rng, data=view.data)

    def commit(self):
        view, record, split, growth = self.view, self.member.record, self.split, self.growth
        record.exp, record.level = growth.new_exp, growth.new_level
        record.max_hp, record.max_mp = growth.max_hp, growth.max_mp
        record.exp_half = split.companion_half
        view.companion_owner_half[self.pc_uid] = split.owner_half
        corpse = self.corpse
        receipt = dict(kill_id=f'{view.companion_reward_epoch}:{corpse.uid}:{corpse.generation}',
            target_uid=corpse.uid, owner_character_id=self.pc_uid,
            member_character_id=record.character_id, kill_exp=self.monster.kill_exp,
            owner_exp=split.owner_exp, member_exp=split.companion_exp,
            owner_half=split.owner_half, member_half=split.companion_half,
            kill_once=True, joint_commit_count=0, durable=False)
        view.companion_reward_receipts.append(receipt)
        del view.companion_reward_receipts[:-32]
        return receipt


def _reward_plan(view, pc_uid, corpse, monster, now):
    member = next((rt for rt in view.companions.active.values()
        if rt.owner_ref.uid == pc_uid and view.companions.can_be_attacked(rt.ref.uid)
        and (entity := view.entities.resolve(rt.ref)) is not None
        and entity.map_id == corpse.map_id), None)
    if member is None:
        return None
    split = split_exp(monster.kill_exp, view.companion_owner_half.get(pc_uid, 0),
                      member.record.exp_half)
    return FollowerRewardPlan(view, pc_uid, corpse, monster, member, split)


def _save_companion(self, uid: int, receipt=None) -> None:
    if self.companion_save is not None:
        try:
            self.companion_save(uid, receipt)
        except Exception as error:
            # Keep the failed absolute snapshot in CompanionStore.pending.
            # Persistence failure must not skip death/leave/map cleanup.
            self.companion_save_errors = (self.companion_save_errors +
                [f'{type(error).__name__}: {error}'])[-8:]
            LOG.exception('Companion snapshot save failed')


def _companion_removed(self, actor) -> None:
    for uid in self.pcs:
        known = self.visibility.known.get(uid, set())
        if actor.ref.uid in known:
            known.discard(actor.ref.uid)
            self._queue(uid, remove_frame(actor.ref.uid))
    self._save_companion(actor.owner_ref.uid)
    self._announce()


def dismiss_companions(self, owner_uid: int) -> None:
    for actor in tuple(self.companions.active.values()):
        if actor.owner_ref.uid == owner_uid:
            self.companions.dismiss(actor.character_id)


def summon_companion(self, character_id: int, owner_uid: int):
    owner = self.entities.get(owner_uid)
    if (owner is None or owner_uid not in self.pcs or not self.combat.can_be_attacked(owner_uid)
            or character_id not in self.companion_profiles
            or self.companions.records[character_id].owner_character_id != owner_uid):
        raise ValueError('COMPANION_SELECTED_LIVING_OWNER_REQUIRED')
    active = sum(rt.owner_ref.uid == owner_uid for rt in self.companions.active.values())
    if active >= self.companion_max_active:
        raise ValueError('COMPANION_ONE_ACTIVE_MEMBER_REQUIRED' if self.companion_max_active == 1
                         else 'COMPANION_ACTIVE_MEMBER_LIMIT')
    # Same bounded terrain/occupied actor policy as existing AI. No teleport
    # onto the owner's tile, no allocation until a lawful tile is available.
    from tools.local_original_session.npc_ai import DELTAS
    for heading, (dx, dy) in enumerate(DELTAS):
        x, y = owner.x + dx, owner.y + dy
        if (self.terrain is not None
                and self.terrain.can_step(owner.map_id, owner.x, owner.y, heading) is True
                and not any(e.kind is not Kind.ITEM for e in self.entities.near(
                    owner.map_id, x, y, 0, alive_only=False))):
            actor = self.companions.summon(character_id, owner_uid, owner.map_id, x, y,
                now=self.runtime.clock(), heading=owner.heading)
            self.companion_ai.start(actor.ref, self.runtime.clock())
            for watcher in self.pcs:
                for frame in self._refresh(watcher):
                    self._queue(watcher, frame)
            self._save_companion(owner_uid)
            self._announce()
            return actor
    raise ValueError('COMPANION_FREE_SPAWN_TILE_REQUIRED')


def _npc_attack_companion(self, entity, monster, actor, now):
    target = self.entities.resolve(actor.ref)
    if (target is None or entity.map_id != target.map_id
            or max(abs(entity.x - target.x), abs(entity.y - target.y)) > monster.attack_range
            or not local_line_clear(self.terrain, entity.map_id, entity.x, entity.y, target.x, target.y)):
        return
    target_ref = target.ref
    heading = heading_to(entity.x, entity.y, target.x, target.y)
    self.entities.move(entity.uid, entity.map_id, entity.x, entity.y, heading)
    magic = self.events.first('npc_magic_attack', entity, monster, target.uid, now)
    swing = (self.combat.npc_companion_swing(monster, target.uid,
        self.companion_profiles[actor.character_id], now) if magic is None else magic[0])
    if swing is None:
        return
    frame = world_combat.attack_frame(entity.uid, target.uid,
        raw_effect=1 if swing.landed else 0, direction=heading, self_action=False,
        ranged=monster.template_id == 1 and monster.attack_range > 1,
        arrow_id=self.arrow_id, arrow_mode=self.arrow_mode)
    watchers = set(self._watchers(entity)) | set(self._watchers(target))
    for uid in watchers:
        self._queue(uid, frame)
    if not actor.record.alive:
        for uid in self._watchers(target):
            self._queue(uid, world_combat.death_frame(target.uid))
    elif swing.landed and swing.damage > 0:
        self.companion_ai.on_hit(target_ref, entity.ref, now)
    # Player HUD hit-ratio f3 is UNKNOWN: never fabricate 4F1A or self4E38.
    self._save_companion(actor.owner_ref.uid)


def companion_attack(self, intent) -> None:
    actor = self.companions.get_actor(intent.actor_ref.uid)
    attacker, target = self.entities.resolve(intent.actor_ref), self.entities.resolve(intent.target_ref)
    found = None if target is None else self.spawner.slot_for(target.uid)
    if (actor is None or actor.ref != intent.actor_ref or actor.target != intent.target_ref
            or attacker is None or target is None or not target.alive or found is None
            or actor.record.combat_mode == 'PASSIVE' or not actor.record.alive
            or attacker.map_id != target.map_id or self.companions.are_allies(attacker.uid, target.uid)
            or max(abs(attacker.x - target.x), abs(attacker.y - target.y))
               > self.companion_ai.attack_reach(attacker)
            or not local_line_clear(self.terrain, attacker.map_id, attacker.x, attacker.y, target.x, target.y)):
        return
    group, slot = found
    if not group.active or slot.hp <= 0:
        return
    profile = _replace(self.companion_profiles[actor.character_id], level=actor.record.level)
    swing = self.combat.companion_swing(actor, profile, group.monster)
    if swing is None:
        return
    heading = heading_to(attacker.x, attacker.y, target.x, target.y)
    self.entities.move(attacker.uid, attacker.map_id, attacker.x, attacker.y, heading)
    frame = world_combat.attack_frame(attacker.uid, target.uid,
        raw_effect=world_combat.PC_RAW_HIT if swing.landed else 0,
        direction=heading, self_action=False)
    for uid in set(self._watchers(attacker)) | set(self._watchers(target)):
        self._queue(uid, frame)
    self.events.emit('companion_weapon_hit', actor, target, group.monster, swing)
    self._apply_monster_swing(actor.owner_ref.uid, attacker.uid, target, group.monster,
                              slot.hp, swing, intent.at)
    self._announce()


def companion_swing(self, runtime, profile: PcProfile, monster: MonsterDef) -> Swing | None:
    """One admitted basic intent, using the saved member's own combat inputs.

    CompanionAI owns next_attack_at. The WorldView consumer validates the
    intent's current target, map, range and LOS before calling this method,
    and applies this swing through its normal monster HP/death path.
    """
    manager = self.companions
    if (manager is None or manager.get_actor(runtime.ref.uid) is not runtime
            or not manager.can_be_attacked(runtime.ref.uid)
            or not self.can_be_attacked(runtime.owner_ref.uid)):
        return None
    bags = getattr(self, 'companion_inventory', None)
    if bags is not None and bags.calculated(runtime.character_id)[0].weight.attack_blocked:
        return None
    return world_combat.pc_hits_npc(profile, monster, self.rng)


def npc_companion_swing(self, monster: MonsterDef, uid: int, profile: PcProfile,
                        now: float) -> Swing | None:
    """Debit only CompanionRecord HP; lethal damage cancels its whole life.

    The caller admits the NPC's current target/range/LOS and publishes the
    attack, companion HP and death frames. No own-player SC_STATUS is made.
    """
    manager = self.companions
    if manager is None or not manager.can_be_attacked(uid):
        return None
    runtime = manager.get_actor(uid)
    if runtime is None or not self.can_be_attacked(runtime.owner_ref.uid):
        return None
    # Shield is caster-only. Its expiry uses the shared monotonic clock;
    # checking the deadline here also handles a late expiry callback.
    if runtime.shield_until > now:
        from dataclasses import replace
        profile = replace(profile, ac=profile.ac - 2)
    swing = world_combat.npc_hits_pc(monster, profile, self.rng)
    if swing.landed and swing.damage > 0:
        record = runtime.record
        record.hp = max(0, record.hp - swing.damage)
        if record.hp == 0:
            manager.die(record.character_id, now)
    return swing


def npc_companion_magic_swing(self, monster, uid, profile, attack, now):
    """Shared NPC elemental/MR formula, follower's own profile and HP owner.

    Separate entry point keeps physical weapon-break wrappers out of spells.
    The registered producer owns NPC MP, reuse and spell selection.
    """
    manager = self.companions
    actor = manager.get_actor(uid)
    if (actor is None or not manager.can_be_attacked(uid)
            or not self.can_be_attacked(actor.owner_ref.uid)):
        return None
    view = manager.entities
    if view.resolve(actor.owner_ref) is None:
        return None
    swing = world_combat.npc_hits_pc(monster, profile, self.rng, magic=attack)
    if swing.landed and swing.damage > 0:
        actor.record.hp = max(0, actor.record.hp - swing.damage)
        if actor.record.hp == 0:
            manager.die(actor.character_id, now)
    return swing, None


class CompanionMagicTarget:
    """Optional target adapter; owns no NPC mana, reuse, or spell selection."""
    def __init__(self, view, actor):
        self.view, self.actor = view, actor

    @property
    def hp(self):
        return self.actor.record.hp

    @property
    def profile(self):
        return self.view.companion_profiles[self.actor.character_id]

    def apply(self, monster, attack, now):
        return self.view.combat.npc_companion_magic_swing(
            monster, self.actor.ref.uid, self.profile, attack, now)

    def counter(self, now):
        return False  # companion counter-magic is not an implemented producer
