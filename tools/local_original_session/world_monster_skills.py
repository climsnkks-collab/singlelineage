"""Optional sourced monster actions, serialized by the existing world runtime.

All numbers are explicit LOCAL L1J backend policies. Client 4ED8 is only the
existing target-effect presentation, not proof of the original cast animation.
PC timed states use the registered consumable_magic_provider and its save API;
without that provider status actions refuse and ordinary attacks remain usable.
Summons use ordinary interest-spawn slots/AI/HP/death; their owned groups never
respawn and are removed when their summoner's EntityRef ends or becomes dormant.
Core EXP stays intact; owned summon corpses do not create ground-drop items.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from tools.local_original_session import npc_ai, world_combat as combat
from tools.local_original_session import world_magic_status as status
from tools.local_original_session import world_npc_resources
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import Group, Slot, SlotState
from tools.local_original_session.world_status_frames import effect_frame

DATA_PATH = Path(__file__).parent / 'data' / 'monster_skills.json'
STATUS_KINDS = frozenset(('poison', 'paralysis', 'silence', 'slow'))
SUPPORT_KINDS = frozenset(('haste', 'heal'))


def load_attacks(path=DATA_PATH):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = {}
    for row in raw['attacks']:
        if row.get('enabled', True):
            rows.setdefault(row['npc_id'], []).append(dict(row))
    return {key: tuple(value) for key, value in rows.items()}


class MonsterSkills:
    def __init__(self, view, attacks, *, provider=None, magic_target=None, cancel_target=None):
        self.view, self.attacks = view, attacks
        self.magic, self.save = (None, None) if provider is None else provider
        self.magic_target = magic_target or (lambda uid: None)
        self.cancel_target = cancel_target or (lambda uid: None)
        self.resources = world_npc_resources.install(view)
        self.events, self.handles, self.subscriptions = [], [], []
        self.cooldowns, self.counts, self.summons = {}, {}, {}
        self.haste = {}  # EntityRef -> (expiry, interval factor); transient NPC life
        self.active = []
        self.closed = True

    def start(self):
        if not self.closed:
            return
        self.closed = False
        view = self.view
        def wrap(owner, name, factory):
            self.handles.append(view.runtime_extensions.wrap('monster_skills', owner, name, factory))
        if view.ai is not None:
            wrap(view.ai, '_act', self._act_wrapper)
            wrap(view.ai, '_fight', self._fight_wrapper)
        wrap(view, 'npc_attack', self._attack_wrapper)
        wrap(view.combat, 'npc_swing', self._swing_wrapper)
        wrap(view.spawner, '_refill', self._refill_wrapper)
        wrap(view.ground, 'spawn_reward', self._spawn_reward_wrapper)
        if self.magic is not None:
            wrap(self.magic, 'admit_cast', self._admit_wrapper)
        for event, fn in (('tick', self.tick), ('npc_died', self.forget),
                          ('npc_speed_factors', self.speed_factors), ('close', self.close)):
            entry = view.events.add('monster_skills', event, fn)
            self.subscriptions.append((event, entry))

    def close(self, *_):
        if self.closed:
            return
        self.closed = True
        for ref in tuple(self.summons):
            self._remove_summons(ref)
        for handle in reversed(self.handles):
            handle.close()
        self.handles.clear()
        for event, entry in self.subscriptions:
            self.view.events.remove(event, entry)
        self.subscriptions.clear()
        self.cooldowns.clear()
        self.counts.clear()
        self.active.clear()
        hasted = tuple(self.haste)
        self.haste.clear()
        for ref in hasted:
            self.view.events.emit('npc_speed_changed', ref, self.view.runtime.clock())

    def speed_factors(self, factors, ref, now):
        """Contribute the existing LOCAL AI cadence; no client rate table."""
        current = self.haste.get(ref)
        if current is None or current[0] <= now:
            return factors
        return tuple(factor * current[1] for factor in factors)

    def _rows(self, monster):
        return tuple(row for row in self.attacks.get(monster.l1j_npcid, ())
                     if row['template_id'] == monster.template_id)

    def _admit_wrapper(self, base):
        def call(uid, key, character_class, level, mp, alive, now):
            if self.magic.status(uid, 'silence', now) is not None:
                raise ValueError('MAGIC_CASTER_SILENCED')
            return base(uid, key, character_class, level, mp, alive, now)
        return call

    def _record(self, entity, monster, target, row, now, **values):
        self.events.append(dict(npc_uid=entity.uid, npc_generation=entity.generation,
            template_id=monster.template_id, npc_id=monster.l1j_npcid, target=target.uid,
            id=row['id'], kind=row['kind'], effect_id=row.get('effect_id'), at=now,
            policy='local_policy', **values))
        del self.events[:-128]

    def _support_target(self, entity, row, now):
        if row['kind'] == 'haste':
            current = self.haste.get(entity.ref)
            return entity if current is None or current[0] <= now else None
        # LOCAL user policy includes the caster. L1J searches only visible
        # companions; the same sourced, nonempty family still gates all allies.
        family = row.get('family_npc_ids', ())
        if not row.get('family') or row['npc_id'] not in family:
            return None
        candidates = []
        for target in self.view.entities.near(entity.map_id, entity.x, entity.y,
                row['max_distance'], kind=Kind.NPC):
            found = self.view.spawner.slot_for(target.uid)
            if (not target.alive or found is None or not found[0].active
                    or found[0].monster.l1j_npcid not in family
                    or not 0 < found[1].hp < found[0].monster.hp
                    or not npc_ai.local_line_clear(self.view.terrain, entity.map_id,
                        entity.x, entity.y, target.x, target.y)):
                continue
            ratio = found[1].hp * 100 / found[0].monster.hp
            if ratio <= row['trigger_companion_hp_percent']:
                candidates.append((ratio, target.uid, target))
        return min(candidates, key=lambda item: item[:2])[2] if candidates else None

    def _act_wrapper(self, base):
        def call(uid, now):
            brain = self.view.ai.brains.get(uid)
            current = None if brain is None else self.haste.get(brain.ref)
            if current is None or current[0] <= now:
                return base(uid, now)
            original = brain.monster
            # L1NpcInstance.calcSleepTime moveSpeed=1 subtracts 25% for both
            # MOVE_SPEED and ATTACK_SPEED. Preserve the original definition.
            brain.monster = replace(original,
                move_interval_ms=int(original.move_interval_ms * current[1]),
                attack_interval_ms=int(original.attack_interval_ms * current[1]))
            try:
                return base(uid, now)
            finally:
                brain.monster = original
        return call

    def _eligible(self, entity, monster, target, row, now, *, on_hit=False):
        if self.closed or row.get('on_hit', False) != on_hit:
            return False
        support = row['kind'] in SUPPORT_KINDS
        if support:
            target = self._support_target(entity, row, now)
        if target is None:
            return False
        if (not entity.alive or self.view.entities.resolve(entity.ref) is not entity
                or not target.alive or entity.map_id != target.map_id):
            return False
        if not support and not self.view.combat.can_be_attacked(target.uid):
            return False
        found = self.view.spawner.slot_for(entity.uid)
        if found is None or not found[0].active or found[1].hp <= 0:
            return False
        hp_trigger = row.get('trigger_hp_percent', 0)
        if hp_trigger and found[1].hp * 100 > monster.hp * hp_trigger:
            return False
        count_limit = row.get('trigger_count_limit', 0)
        if count_limit and self.counts.get((entity.ref, row['id']), 0) >= count_limit:
            return False
        d = npc_ai.distance(entity.x, entity.y, target.x, target.y)
        if not row.get('min_distance', 0) <= d <= row['max_distance']:
            return False
        if not npc_ai.local_line_clear(self.view.terrain, entity.map_id,
                                      entity.x, entity.y, target.x, target.y):
            return False
        if now < self.cooldowns.get((entity.ref, row['id']), 0):
            return False
        adapter = None if target.uid in self.view.combat.pcs else self.magic_target(target.uid)
        if row['kind'] == 'cancel' and self.cancel_target(target.uid) is None:
            return False
        if row['kind'] in STATUS_KINDS:
            if row['kind'] == 'slow' and self.magic is None:
                return False  # probability formula belongs to the magic provider
            if target.uid in self.view.combat.pcs:
                if self.magic is None:
                    return False
            elif adapter is None or not hasattr(adapter, 'ailments'):
                return False
        if row.get('on_hit'):
            if target.uid in self.view.combat.pcs:
                if self.magic is None:
                    return False
                effects = self.magic.effects(target.uid)
                poisoned = self.magic.state(target.uid).poison
            elif adapter is not None and hasattr(adapter, 'ailments'):
                ailments = adapter.ailments(now)
                effects, poisoned = ailments['effects'], ailments['poison']
            else:
                return False
            if ((poisoned is not None and poisoned['until'] > now) or any(
                    r['params'].get('monster_poison') and (r['until'] is None or r['until'] > now)
                    for r in effects.values())):
                return False
        if row['kind'] == 'summon':
            limit = row.get('trigger_count_limit', 0)
            if (limit and self.counts.get((entity.ref, row['id']), 0) >= limit
                    or self.counts.get((entity.ref, 'summon_total'), 0) > row.get('summon_limit', 100)
                    or row['summon_template_id'] not in self.view.data.monsters):
                return False
        return self.resources.mana_of(entity.ref, monster.mp) >= row.get('mp_cost', 0)

    def _fight_wrapper(self, base):
        def call(brain, entity, now):
            target = self.view.entities.get(brain.target)
            if target is not None and now >= brain.next_attack_at:
                for row in self._rows(brain.monster):
                    if row['id'].endswith(':ranged'):
                        continue  # ordinary physical range belongs to base AI
                    if (self._eligible(entity, brain.monster, target, row, now)
                            and self.view.combat.rng.randint(1, 100) <= row['chance_percent']
                            and self.cast(entity, brain.monster, target, row, now)):
                        brain.next_attack_at = now + max(row.get('cast_interval_seconds', 0),
                            brain.monster.attack_interval_ms / 1000)
                        # Death/release_target already schedules RETURN itself.
                        if brain.target == target.uid and entity.alive:
                            self.view.ai._schedule(brain, brain.next_attack_at)
                        return
            # Only unconditional ordinary ranged rows widen fallback reach.
            # A conditional special attack's range never gives physical melee
            # an otherwise unavailable distant hit.
            ordinary = next((r for r in self._rows(brain.monster) if r['id'].endswith(':ranged')), None)
            if ordinary is None:
                return base(brain, entity, now)
            original = brain.monster
            brain.monster = replace(original, attack_range=ordinary['max_distance'])
            try:
                return base(brain, entity, now)
            finally:
                brain.monster = original
        return call

    def _attack_wrapper(self, base):
        def call(entity, monster, target_uid, now):
            target = self.view.entities.get(target_uid)
            if target is None:
                return base(entity, monster, target_uid, now)
            self.active.append((entity, monster, target, now))
            try:
                # Own the complete opportunity for these species. Otherwise the
                # legacy magic selector could roll/pay/cast again after refusal.
                adapter = None if target_uid in self.view.combat.pcs else self.magic_target(target_uid)
                if ((target_uid in self.view.combat.pcs or adapter is not None and hasattr(adapter, 'physical')) and any(
                        r['kind'] in ('magic', 'drain', 'explode') for r in self._rows(monster))):
                    if not self.view.combat.can_be_attacked(target_uid):
                        return
                    self._physical(entity, monster, target, now)
                    return
                # Companion damage does not pass CombatEngine.npc_swing. Use
                # the registered consumer once for contact-poison species too.
                if adapter is not None and hasattr(adapter, 'physical') and self._rows(monster):
                    self._physical(entity, monster, target, now)
                    return
                return base(entity, monster, target_uid, now)
            finally:
                self.active.pop()
        return call

    def _swing_wrapper(self, base):
        def call(monster, uid, **kwargs):
            result = base(monster, uid, **kwargs)
            if self.active:
                entity, definition, target, now = self.active[-1]
                if uid == target.uid and not self.view.combat.is_dead(uid):
                    self._on_hit(entity, definition, target, result[0], now)
            return result
        return call

    def _on_hit(self, entity, monster, target, swing, now):
        if not swing.landed or swing.damage <= 0:
            return
        for row in self._rows(monster):
            if (self._eligible(entity, monster, target, row, now, on_hit=True)
                    and self.view.combat.rng.randint(1, 100) <= row['chance_percent']):
                self.cast(entity, monster, target, row, now)

    def _physical(self, entity, monster, target, now, *, leverage=10):
        state = self.view.combat.pcs.get(target.uid)
        adapter = None if state is not None else self.magic_target(target.uid)
        if not self.view.combat.can_be_attacked(target.uid):
            return None
        if state is None:
            if adapter is None or not hasattr(adapter, 'physical'):
                return None
            factor = 1
            if self.magic is not None:
                self.magic.effects(entity.uid, target_ref=entity.ref)
                effect = self.magic.status(entity.uid, 'weapon_break', now)
                factor = 1 if effect is None else effect['params'].get('damage_multiplier', .5)
            before = adapter.hp
            swing = adapter.physical(monster, now, leverage=leverage, factor=factor)
            if swing is None:
                return None
            self._deliver(entity, monster, target, swing, None, now, adapter=adapter)
            if adapter.hp > 0:
                self._on_hit(entity, monster, target, swing, now)
            return before - adapter.hp
        before = state.hp
        swing = (self.view.events.first('npc_physical_swing', monster, target.uid, entity.ref, now)
                 or combat.npc_hits_pc(monster, state.profile, self.view.combat.rng))
        factor, reduction = 1, 0
        if self.magic is not None:
            # Public effects() binds the row to the current generation first.
            self.magic.effects(entity.uid, target_ref=entity.ref)
            effect = self.magic.status(entity.uid, 'weapon_break', now)
            factor = 1 if effect is None else effect['params'].get('damage_multiplier', .5)
            reduction = self.magic.reduction(target.uid, state.profile.level, now)
        swing = replace(swing, damage=max(0, int(swing.damage * leverage / 10 * factor) - reduction))
        wire = None
        if swing.landed and swing.damage > 0:
            state.hp = max(0, state.hp - swing.damage)
            state.dead = state.hp == 0
            wire = combat.status_frame(state.status_fields, state.hp)
        self._deliver(entity, monster, target, swing, wire, now)
        if not state.dead:
            self._on_hit(entity, monster, target, swing, now)
        return before - state.hp

    def _deliver(self, entity, monster, target, swing, wire, now, *, magic=False, adapter=None):
        view = self.view
        heading = npc_ai.heading_to(entity.x, entity.y, target.x, target.y)
        view.entities.move(entity.uid, entity.map_id, entity.x, entity.y, heading)
        frame = combat.attack_frame(entity.uid, target.uid, raw_effect=int(swing.landed),
            direction=heading, self_action=False,
            ranged=not magic and monster.template_id == 1 and monster.attack_range > 1,
            arrow_id=view.arrow_id, arrow_mode=view.arrow_mode)
        for watcher in set(view._watchers(entity)) | set(view._watchers(target)):
            view._queue(watcher, frame)
        if wire is not None:
            view._queue(target.uid, wire)
        if target.uid in view.combat.pcs:
            if view.combat.is_dead(target.uid):
                view._pc_died(target.uid, now)
            elif swing.landed and swing.damage > 0:
                view.events.emit('pc_hit', target.ref, entity.ref, now)
        elif adapter is not None:
            adapter.finish(entity.ref, swing, now)

    def _effect(self, entity, target, row):
        gfx = row.get('effect_id')
        if gfx is not None and gfx > 0:
            wire = effect_frame(target.uid, gfx)
            for uid in (set(self.view._watchers(entity)) | set(self.view._watchers(target))) & set(self.view.pcs):
                self.view._queue(uid, wire)

    def cast(self, entity, monster, target, row, now):
        """Commit one admitted action. Invoked under the world lock only."""
        view, kind = self.view, row['kind']
        if not self._eligible(entity, monster, target, row, now, on_hit=row.get('on_hit', False)):
            return False
        if kind in SUPPORT_KINDS:
            target = self._support_target(entity, row, now)
        state = view.combat.pcs.get(target.uid)
        adapter = None if state is not None else self.magic_target(target.uid)
        if kind in ('magic', 'drain', 'explode') and state is None and adapter is None:
            return False
        if kind == 'physical' and state is None and (adapter is None or not hasattr(adapter, 'physical')):
            return False
        cancel = self.cancel_target(target.uid) if kind == 'cancel' else None
        if kind == 'cancel' and cancel is None:
            return False
        before_mp = self.resources.mana_of(entity.ref, monster.mp)
        if not self.resources.spend_mana(entity.ref, monster.mp, row.get('mp_cost', 0)):
            return False
        due = now + max(row.get('reuse_seconds', 0), row.get('cast_interval_seconds', 0))
        self.cooldowns[entity.ref, row['id']] = due
        self.counts[entity.ref, row['id']] = self.counts.get((entity.ref, row['id']), 0) + 1
        support_slot = view.spawner.slot_for(target.uid) if kind in SUPPORT_KINDS else None
        before_hp = (support_slot[1].hp if support_slot is not None else
                     None if state is None and adapter is None else state.hp if state is not None else adapter.hp)
        amount, outcome, extra = 0, 'applied', {}
        if kind == 'cancel':
            # LOCAL buff-only policy: probability is the sourced mob row's
            # chance_percent, rolled by AI; no extra inferred MR/damage roll.
            extra['removed_buffs'] = list(cancel(now))
            outcome = 'buffs_cancelled'
        elif kind == 'haste':
            until = now + row['duration_seconds']
            self.haste[entity.ref] = (until, row['interval_factor'])
            view.events.emit('npc_speed_changed', entity.ref, now)
            outcome = 'haste_applied'
            extra.update(until=until, interval_factor=row['interval_factor'])
        elif kind == 'heal':
            params = row['parameters']
            dice = params['damage_value'] + min(10, row['healing_magic_bonus'])
            rolled = sum(view.combat.rng.randint(1, params['damage_dice'])
                         for _ in range(max(0, dice)))
            rolled = int(rolled * (1 + max(0, row['caster_lawful']) / 32768))
            rolled = int(rolled * row.get('leverage', 10) / 10)
            group, slot = support_slot
            slot.hp = min(group.monster.hp, slot.hp + max(0, rolled))
            amount, outcome = slot.hp - before_hp, 'healed'
            extra.update(rolled_heal=rolled, family=row['family'])
        elif kind == 'physical':
            amount = self._physical(entity, monster, target, now, leverage=row.get('leverage', 10))
        elif kind in ('magic', 'drain', 'explode'):
            countered = ((self.magic is not None and self.magic.consume_counter(target.uid, now))
                         if state is not None else adapter.counter(now))
            if countered:
                swing, wire, outcome = combat.Swing(True, 0), None, 'countered'
                if self.magic is not None and state is not None:
                    self.magic.consume_erase(target.uid, now)
                    self.save(target.uid, now)
                    view.events.emit('magic_status_changed', target.uid, now)
            else:
                attack = combat.NpcMagicAttack(row['parameters'], row['intelligence'],
                    leverage=row.get('leverage', 10), trace={})
                swing, wire = (view.combat.npc_magic_swing(monster, target.uid, attack)
                    if state is not None else adapter.apply(monster, attack, now))
                extra['trace'] = attack.trace
            after_hp = state.hp if state is not None else adapter.hp
            amount = before_hp - after_hp
            self._deliver(entity, monster, target, swing, wire, now, magic=True, adapter=adapter)
            if kind == 'drain' or row.get('drain'):
                found = view.spawner.slot_for(entity.uid)
                restored = min(monster.hp - found[1].hp, amount)
                found[1].hp += restored
                extra['drain_restored'] = restored
        elif kind in STATUS_KINDS:
            resisted = countered = False
            if not row.get('on_hit'):
                countered = (self.magic.consume_counter(target.uid, now) if state is not None
                             else adapter.counter(now))
                mr = (self.magic.effective_mr(target.uid, state.profile.mr, now)
                      if state is not None else adapter.profile.mr)
                if not countered:
                    # L1Magic.java:329-344 NPC dice omit the PC class +/-1.
                    bonus = self.magic.catalog['formula_policies']['l1j_healing']['magic_bonus_by_int_0_to_50']
                    intelligence = row['intelligence']
                    count = max(1, (bonus[intelligence] if intelligence <= 50 else intelligence - 25)
                                + monster.level // 4)
                    probability = int(sum(view.combat.rng.randint(1, row['probability_dice'])
                        for _ in range(count)) * row.get('leverage', 10) / 10) - mr
                    resisted = view.combat.rng.randint(1, 100) > min(90, probability)
                    extra.update(probability=probability, effective_mr=mr)
                if state is not None:
                    self.magic.consume_erase(target.uid, now)
            if resisted or countered:
                outcome = 'countered' if countered else 'resisted'
            elif kind == 'poison':
                poison = dict(until=now + row['duration_seconds'],
                    next_tick=now + row['tick_seconds'], tick_seconds=row['tick_seconds'],
                    damage=row['tick_damage'], source_uid=entity.uid)
                if state is not None:
                    self.magic.state(target.uid).poison = poison
                else:
                    adapter.ailments(now)['poison'] = poison
                outcome = 'poison_applied'
            else:
                effect_kind = {'paralysis': 'paralyze', 'silence': 'silence', 'slow': 'slow'}[kind]
                apply = ((lambda *args, **kwargs: self.magic.apply_status(target.uid, *args, **kwargs))
                         if state is not None else adapter.apply_status)
                apply(effect_kind, now, row.get('duration_seconds'),
                    source_uid=entity.uid, spell=row.get('skill_id', 0),
                    params={'monster_poison': bool(row.get('on_hit'))}, onset=row.get('delay_seconds', 0))
                outcome = 'poison_applied' if row.get('on_hit') else 'status_applied'
            if state is not None:
                self.save(target.uid, now)
                # The magic owner publishes its own HUD/other state views only
                # after persistence succeeds. NPCs never receive PC HUD rows.
                view.events.emit('magic_status_changed', target.uid, now)
            else:
                adapter.save(now)
        elif kind == 'summon':
            refs = self._summon(entity, monster, target, row, now)
            extra['summoned_uids'], outcome = [ref.uid for ref in refs], 'summoned'
            amount = len(refs)
        else:
            return False
        self._effect(entity, target, row)
        self._record(entity, monster, target, row, now, outcome=outcome, amount=amount,
            hp_before=before_hp, hp_after=(support_slot[1].hp if support_slot is not None else
                None if before_hp is None else state.hp if state else adapter.hp),
            mp_before=before_mp, mp_after=self.resources.mana_of(entity.ref, monster.mp),
            next_cast_at=due, **extra)
        if kind == 'explode' and entity.alive:
            view.ai.drop(entity.uid) if view.ai is not None else None
            view.events.emit('npc_died', entity.uid, now)
            view.runtime.scheduler.cancel_owner(entity.ref)
            watchers = view._watchers(entity)
            view.spawner.mark_dead(entity.uid, now)
            for uid in watchers:
                view._queue(uid, combat.death_frame(entity.uid))
        return True

    def cure_poison(self, uid):
        adapter = self.magic_target(uid) if uid not in self.view.combat.pcs else None
        if adapter is not None and hasattr(adapter, 'cure_poison'):
            adapter.cure_poison(self.view.runtime.clock())
            return
        if self.magic is None:
            return
        effects = self.magic.effects(uid)
        for kind in ('paralyze', 'silence'):
            if kind in effects and effects[kind]['params'].get('monster_poison'):
                del effects[kind]
        self.save(uid, self.view.runtime.clock())

    def _summon(self, entity, monster, target, row, now):
        view = self.view
        parent, _ = view.spawner.slot_for(entity.uid)
        count = view.combat.rng.randint(row['count_min'], row['count_max'])
        radius = row.get('summon_radius', 8)
        rect = replace(parent.spec.rect, x1=max(0, entity.x-radius), y1=max(0, entity.y-radius),
                       x2=entity.x+radius, y2=entity.y+radius)
        spec = replace(parent.spec, group_id=f'monster-summon-{entity.uid}-{len(self.summons.get(entity.ref, ()))}',
            template_id=row['summon_template_id'], rect=rect, target_count=count)
        group = Group(spec, view.data.monsters[spec.template_id], [Slot(i) for i in range(count)], True)
        self.summons.setdefault(entity.ref, []).append(group)
        view.spawner.groups.append(group)
        refs = []
        for slot in group.slots:
            if view.spawner._place(group, slot, now):
                ref = view.entities.get(slot.uid).ref
                refs.append(ref)
        self.counts[entity.ref, 'summon_total'] = self.counts.get((entity.ref, 'summon_total'), 0) + len(refs)
        if view.ai is not None:
            view.ai.sync(now)
            for ref in refs:
                view.ai.on_hit(ref.uid, target.uid, now)
        for uid in view.pcs:
            for wire in view._refresh(uid):
                view._queue(uid, wire)
        return refs

    def _refill_wrapper(self, base):
        def call(group, now, *, retry_now):
            if not any(group is owned for groups in self.summons.values() for owned in groups):
                return base(group, now, retry_now=retry_now)
            changed = False
            for slot in group.slots:
                if slot.state is SlotState.WAIT and slot.uid is not None and slot.corpse_at <= now:
                    self.view.spawner._remove_corpse(slot)
                    changed = True
            return changed
        return call

    def _spawn_reward_wrapper(self, base):
        def call(npc_ref, reward, *, owner_uid, now=None):
            entity = self.view.entities.resolve(npc_ref)
            if entity is not None and not entity.alive:
                # mark_dead bumps generation before core reward publication.
                # Resolve the exact corpse ref and retain ownership through its
                # normal corpse lifetime; never accept a stale living ref.
                for groups in self.summons.values():
                    if any(slot.uid == npc_ref.uid and slot.state is SlotState.WAIT
                           for group in groups for slot in group.slots):
                        # L1MobSkillUse.java:527-529 sets storeDroped(true)
                        # before onNpcAI; L1MonsterInstance.java:224-227 therefore
                        # skips initial DropTable population. Core EXP remains.
                        return ()
            return base(npc_ref, reward, owner_uid=owner_uid, now=now)
        return call

    def _remove_summons(self, ref):
        view = self.view
        for group in self.summons.pop(ref, ()):
            for slot in group.slots:
                if slot.uid is None:
                    continue
                entity = view.entities.get(slot.uid)
                if entity is not None:
                    if view.ai is not None:
                        view.ai.drop(slot.uid)
                    view.runtime.scheduler.cancel_owner(entity.ref)
                    view.entities.remove(slot.uid)
                view.spawner._slots.pop(slot.uid, None)
            view.spawner.groups.remove(group)
        for uid in view.pcs:
            for wire in view._refresh(uid):
                view._queue(uid, wire)

    def forget(self, uid, *_):
        for ref in tuple(self.haste):
            if ref.uid == uid:
                del self.haste[ref]
                self.view.events.emit('npc_speed_changed', ref, self.view.runtime.clock())
        for ref in {key[0] for key in self.cooldowns} | set(self.summons):
            if ref.uid == uid:
                self._remove_summons(ref)
                for table in (self.cooldowns, self.counts):
                    for key in tuple(table):
                        if key[0] == ref:
                            del table[key]

    def tick(self, now):
        for ref, (until, _) in tuple(self.haste.items()):
            entity = self.view.entities.resolve(ref)
            if entity is None or not entity.alive or until <= now:
                del self.haste[ref]
                self.view.events.emit('npc_speed_changed', ref, now)
        for ref in {key[0] for key in self.cooldowns} | set(self.summons):
            entity = self.view.entities.resolve(ref)
            found = self.view.spawner.slot_for(ref.uid)
            if entity is None or not entity.alive or found is None:
                self.forget(ref.uid)
            elif not found[0].active:
                # Dormancy ends transient servants, not the parent's life-bound
                # cumulative trigger counters or already paid reuse deadline.
                self._remove_summons(ref)
