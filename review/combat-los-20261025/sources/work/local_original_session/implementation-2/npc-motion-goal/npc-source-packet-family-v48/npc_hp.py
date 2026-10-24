"""Explicit backend HP inputs for a selected local NPC; no protocol or save.

Only AttackSession consumes this state under the existing broker row lock.
Provider outputs are local policy, never decoded from CS4E30/SC4E31. No
official damage formula, NPC reference mapping, removal or respawn is implied.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import uuid4

from tools.local_original_session.attack import U64_MAX, need

POLICY = 'EXPLICIT_LOCAL_NPC_HP_INPUT'


@dataclass(frozen=True, slots=True)
class Target:
    uid: int
    map_id: int
    sprite_id: int
    template_id: int


@dataclass(frozen=True, slots=True)
class Hp:
    current: int
    maximum: int

    def __post_init__(self):
        need(type(self.current) is int and type(self.maximum) is int
             and 0 <= self.current <= self.maximum <= U64_MAX and self.maximum > 0,
             'NPC_HP_EXPLICIT_RANGE_REQUIRED')

    @property
    def alive(self):
        return self.current > 0


@dataclass(frozen=True, slots=True)
class Hit:
    landed: bool
    damage: int

    def __post_init__(self):
        need(type(self.landed) is bool and type(self.damage) is int
             and 0 <= self.damage <= U64_MAX and (self.landed or self.damage == 0),
             'NPC_HP_EXPLICIT_HIT_DAMAGE_REQUIRED')


@dataclass(frozen=True, slots=True)
class Inputs:
    """One exact local actor mapping, with every gameplay number explicit."""
    target: Target
    hp: Hp
    hit: Hit

    def __post_init__(self):
        need(type(self.target) is Target and type(self.hp) is Hp and type(self.hit) is Hit
             and self.hp.alive, 'NPC_HP_EXPLICIT_LIVE_INPUTS_REQUIRED')
        need(all(type(n) is int for n in (self.target.uid, self.target.map_id,
                 self.target.sprite_id, self.target.template_id))
             and 0 < self.target.uid < U64_MAX and self.target.map_id >= 0
             and self.target.sprite_id >= 0 and self.target.template_id >= 0,
             'NPC_HP_EXPLICIT_TARGET_REQUIRED')


@dataclass(frozen=True, slots=True)
class ExplicitInputs:
    """Optional fixed local backend provider. No default rows or numbers.

    A different trusted synchronous backend provider may implement the same
    policy/initial_hp/resolve_hit interface. Nothing accepts a wire provider.
    """
    rows: tuple[Inputs, ...]
    policy: str = field(default=POLICY, init=False)

    def __post_init__(self):
        need(type(self.rows) is tuple and len(self.rows) > 0
             and all(type(row) is Inputs for row in self.rows)
             and len({(r.target.uid, r.target.map_id) for r in self.rows}) == len(self.rows),
             'NPC_HP_EXPLICIT_UNIQUE_INPUTS_REQUIRED')

    def _row(self, target):
        matches = [row for row in self.rows if row.target == target]
        need(len(matches) == 1, 'NPC_HP_EXPLICIT_TARGET_INPUT_REQUIRED')
        return matches[0]

    def initial_hp(self, target):
        return self._row(target).hp

    def resolve_hit(self, target, hp, *, attacker_uid, accepted_ordinal):
        return self._row(target).hit


@dataclass(frozen=True, slots=True)
class Result:
    accepted_ordinal: int
    target: Target
    before: Hp
    after: Hp
    hit: Hit

    @property
    def died(self):
        return self.before.alive and not self.after.alive

    def metadata(self):
        return dict(accepted_ordinal=self.accepted_ordinal, target_uid=self.target.uid,
                    map_id=self.target.map_id, hp_before=self.before.current,
                    hp=self.after.current, max_hp=self.after.maximum, alive=self.after.alive,
                    hit=self.hit.landed, damage=self.hit.damage, died=self.died,
                    notification='NOT_IMPLEMENTED_SOURCE_CONTRACT_REQUIRED')


@dataclass(frozen=True, slots=True)
class _Entry:
    writer: object
    row: object
    lock: object
    lifetime: tuple
    target: Target
    hp: Hp
    intent: object


@dataclass(frozen=True, slots=True)
class DamageContributor:
    source_uid: int
    accepted_events: int
    landed_events: int
    raw_damage: int
    hp_loss: int


@dataclass(frozen=True, slots=True)
class DamageContributions:
    """Accepted PC physical HP-entry chain only, from its first prepared entry.

    Not NPC birth freshness or complete spawn history; MP/external hate and
    first-attack/EXP/solo eligibility are outside this source. The COMBAT caller
    must also consume its original current Port/lifetime qualification.
    """
    target: Target
    initial_hp: Hp
    final_hp: Hp
    accepted_events: int
    contributors: tuple[DamageContributor, ...]
    last_intent: object = field(repr=False, compare=False)
    last_result: object = field(repr=False, compare=False)
    _entry: object = field(repr=False, compare=False)
    _session: object = field(repr=False, compare=False)
    scope: str = field(default='ACCEPTED_PC_PHYSICAL_HP_ENTRY_CHAIN_ONLY', init=False)


@dataclass(frozen=True, slots=True)
class HateContributor:
    source_uid: int
    hate: int


@dataclass(frozen=True, slots=True)
class RespawnHate:
    """Source-owned LOCAL history, not a reward or solo capability.

    UNKNOWN preserves last supported counters/first state for diagnostics only;
    it cannot be read as current/full history or rebound to false.
    """
    receipt: object = field(repr=False, compare=False)
    generation: object = field(repr=False, compare=False)
    source: object = field(repr=False, compare=False)
    maximum_hp: int
    first_attack: bool
    contributors: tuple[HateContributor, ...]
    total_hate: int
    status: str
    reason: str | None = None
    raw_contributions: object = field(default=None, repr=False, compare=False)
    scope: str = field(default='LOCAL_RESPAWN_PC_PHYSICAL_HATE_ONLY', init=False)


@dataclass(frozen=True, slots=True, init=False)
class KillReceipt:
    """Issuer-registered commit identity, never a request or transport receipt."""
    operation_id: str
    _issuer: object = field(repr=False)
    _entry: object = field(repr=False)
    _result: object = field(repr=False)
    _accepted_session: object = field(repr=False)


class Authority:
    """Selection-lifetime HP, independent of moving Position/motion.State.

    _prepare is side-effect free, including a first spawn's initial HP. Only
    _commit stores the one accepted immutable intent under the same row lock.
    Provider failure/cancellation before commit leaves previous HP untouched.
    """
    def __init__(self, provider):
        need(getattr(provider, 'policy', None) == POLICY
             and callable(getattr(provider, 'initial_hp', None))
             and callable(getattr(provider, 'resolve_hit', None)),
             'NPC_HP_EXPLICIT_BACKEND_PROVIDER_REQUIRED')
        self.provider = provider
        self._entries = {}
        self._kill_nonce = uuid4().hex
        self._kills = {}
        self._contributions = {}
        self._hate_source = None
        self._hate_closed = False
        self._hate_births = {}

    def configure_hate_source_cold(self, source):
        """Pin the existing pure policy once, after the actual COMBAT provider bind."""
        from pathlib import Path
        from types import FunctionType
        from tools.local_original_session import canonical_feature_bootstrap, combat_adapters
        need(type(source) is canonical_feature_bootstrap.SourceModule
             and source.sha256 == 'ac721cd3a87cce7f39d31ac2f856944dc9039c92ea44e38b518d365659cf5f47'
             and self._hate_source is None and not self._hate_closed and not self._entries and not self._kills
             and not self._contributions and not self._hate_births
             and type(self.provider) is combat_adapters.PcNpcProvider,
             'NPC_HATE_EXPLICIT_COLD_SOURCE_REQUIRED')
        module = source.check()
        function = getattr(module, 'hate_for_damage', None)
        broker = getattr(self.provider.hp_inputs, 'broker', None)
        need(type(function) is FunctionType and function.__globals__ is module.__dict__
             and function.__name__ == 'hate_for_damage'
             and Path(function.__code__.co_filename).resolve() == source.path.resolve()
             and type(module.INT_MAX) is int and module.INT_MAX > 0
             and broker is not None and not broker._started
             and broker._attack_session is broker.realm._attack_session
             and broker._attack_session._hp is self
             and broker._attack_session._hp_provider is self.provider,
             'NPC_HATE_SAME_POLICY_PROVIDER_REQUIRED')
        self._hate_source = (source,module,function,module.INT_MAX,
                             combat_adapters.PcNpcProvider,combat_adapters.Decision,
                             combat_adapters.physical.PcNpcContext,combat_adapters.physical.PhysicalResult,
                             combat_adapters.PcNpcProvider.capture_locked,combat_adapters.PcNpcProvider.hit_for_intent,
                             module._integer)

    def _respawn_birth_current(self, receipt):
        from tools.local_original_session import npc_respawn, npc_edge, attack_session
        need(type(receipt) is npc_respawn.Receipt and type(receipt._service) is npc_respawn.Service,
             'NPC_HATE_REGISTERED_RESPAWN_REQUIRED')
        service = receipt._service
        broker, generation = service.broker, receipt.generation
        key = (id(receipt.writer),receipt.spawn.uid)
        service_key = service._key(receipt.writer,receipt.spawn.uid)
        need(getattr(service,'_packet_server',None) is not None
             and service._packet_scope == npc_respawn.PACKET_SERVER_DRAINED_REMOVAL
             and broker._npc_respawn is broker.realm._npc_respawn is service
             and broker._attack_session is broker.realm._attack_session
             and type(broker._attack_session) is attack_session.AttackSession
             and not broker._attack_session.closed and not broker._attack_session.fatal
             and broker._attack_session._hp is self
             and broker._attack_session._hp_provider is self.provider
             and service._receipts.get(service_key) is receipt and service._phases.get(service_key) == 'COMMITTED'
             and service._generations.get(service_key) is generation
             and type(generation) is npc_respawn.Generation
             and type(receipt.old_generation) is npc_respawn.Generation
             and generation.ordinal == receipt.old_generation.ordinal+1 and generation.ordinal > 0
             and generation.recipe is receipt.recipe is receipt.old_generation.recipe
             and generation.spawn is receipt.spawn and receipt.spawn is not receipt.recipe
             and receipt.spawn is not receipt.old_generation.spawn
             and generation.mover is receipt.mover and receipt.mover is not receipt.old_generation.mover
             and receipt.mover.spawn_drained and not receipt.mover.closed and not receipt.mover.fatal
             and receipt.mover.state.uid == receipt.spawn.uid == receipt.recipe.uid
             and receipt.mover.state.map_id == receipt.spawn.map_id == receipt.recipe.map_id
             and type(receipt.adapter) is npc_edge.ServerNpcEdgeAdapter
             and receipt._server_provider is not None
             and generation.frames is not receipt.old_generation.frames
             and service.require_current(receipt) is generation,
             'NPC_HATE_COMMITTED_NEW_RESPAWN_REQUIRED')
        current = service._packet_life_current(receipt.writer)
        need(current.broker is broker and current.writer is receipt.writer
             and current.row is generation.row is receipt.row
             and receipt.row['operation_lock'].locked()
             and generation.writer is receipt.writer and generation.frames[0] is receipt.writer
             and generation.frames[1] is current.game and generation.frames[2] is current.mover,
             'NPC_HATE_CURRENT_RESPAWN_ROW_REQUIRED')
        return key, current

    def bind_respawn_birth(self, receipt):
        """Only a registered COMMITTED n+1 spawn establishes false/empty LOCAL state."""
        if self._hate_source is None:return None
        need(not self._hate_closed,'NPC_HATE_AUTHORITY_CLOSED')
        key, current = self._respawn_birth_current(receipt)
        previous = self._hate_births.get(key)
        need((previous is None or previous.receipt is not receipt)
             and key not in self._entries and key not in self._kills and key not in self._contributions,
             'NPC_HATE_ONCE_UNTOUCHED_RESPAWN_REQUIRED')
        target = Target(receipt.spawn.uid,receipt.spawn.map_id,receipt.spawn.fields[3],receipt.spawn.fields[39])
        hp = self.provider.initial_hp(target)
        need(type(hp) is Hp and hp.alive and hp.current == hp.maximum,
             'NPC_HATE_SOURCE_FRESH_MAXIMUM_REQUIRED')
        state = RespawnHate(receipt,receipt.generation,self._hate_source[0],hp.maximum,False,(),0,
                            'COMPLETE_SUPPORTED_PC_PHYSICAL')
        self._hate_births[key] = state
        return state

    def _invalidate_hate(self, key, reason):
        state = self._hate_births.get(key)
        if state is not None:
            self._hate_births[key] = replace(state,status='UNKNOWN',reason=reason)
        return None

    def invalidate_hate_history_locked(self, writer, target_uid, *, reason):
        """Unsupported MP/external setHate/clear producers must retire completeness."""
        key = (id(writer),target_uid)
        state = self._hate_births.get(key)
        if state is None:return None
        need(type(reason) is str and 0 < len(reason) <= 96
             and state.receipt.writer is writer and state.receipt.row['operation_lock'].locked(),
             'NPC_HATE_CURRENT_INVALIDATION_ROW_REQUIRED')
        self._respawn_birth_current(state.receipt)
        return self._invalidate_hate(key,reason)

    def _advance_hate(self, intent, result, snapshot, previous):
        key = (id(intent._bound._writer),result.target.uid)
        state = self._hate_births.get(key)
        if self._hate_source is None or state is None or state.status != 'COMPLETE_SUPPORTED_PC_PHYSICAL':return
        try:
            source,module,function,limit,provider_type,decision_type,context_type,result_type,capture_method,hit_method,integer_function = self._hate_source
            decision = intent.adjudication
            need(source is state.source and module.hate_for_damage is function
                 and function.__globals__ is module.__dict__ and module._integer is integer_function
                 and module.INT_MAX == limit
                 and type(self.provider) is provider_type and type(decision) is decision_type
                 and self.provider.capture_locked.__func__ is capture_method
                 and self.provider.hit_for_intent.__func__ is hit_method
                 and type(decision.context) is context_type and type(decision.result) is result_type
                 and decision.target == result.target and decision.target_uid == result.target.uid
                 and decision.source_uid == intent._bound.attacker.uid
                 and decision.accepted_ordinal == intent.accepted_ordinal
                 and decision.result.landed == result.hit.landed and decision.result.damage == result.hit.damage,
                 'NPC_HATE_SUPPORTED_PC_PHYSICAL_REQUIRED')
            # The selected provider already verified the exact PcNpcContext. No
            # file/source rehash and no second resolver/RNG draw is performed.
            # _accept_damage just established this accepted entry under the
            # held row without an intervening await. Reuse that exact proof;
            # full packet/RESOURCE current remains at bind and external reads.
            receipt, generation = state.receipt, state.generation
            service = receipt._service
            service_key = service._key(receipt.writer,receipt.spawn.uid)
            entry = snapshot._entry
            need(receipt.generation is generation
                 and service._receipts.get(service_key) is receipt
                 and service._generations.get(service_key) is generation
                 and service._phases.get(service_key) == 'COMMITTED'
                 and service.broker._npc_respawn is service.broker.realm._npc_respawn is service
                 and service.broker._attack_session is service.broker.realm._attack_session
                 and service.broker._attack_session._hp is self
                 and entry.writer is receipt.writer is intent._bound._writer
                 and entry.row is receipt.row is generation.row
                 and entry.lifetime[5] is generation.frames,
                 'NPC_HATE_ACCEPTED_REGISTERED_BIRTH_REQUIRED')
            need(snapshot.initial_hp.maximum == state.maximum_hp
                 and (previous is None and state.raw_contributions is None and snapshot.accepted_events == 1
                      and snapshot.initial_hp.current == state.maximum_hp
                      or previous is not None and state.raw_contributions is not None
                      and state.raw_contributions._entry is previous
                      and snapshot.accepted_events == state.raw_contributions.accepted_events+1),
                 'NPC_HATE_COMPLETE_HP_ENTRY_CHAIN_REQUIRED')
            increment, first = (function(damage=result.hit.damage,max_hp=state.maximum_hp,
                                        first_attack=state.first_attack) if result.hit.landed
                                else (0,state.first_attack))
            rows = state.contributors
            existing = tuple(c for c in rows if c.source_uid == intent._bound.attacker.uid)
            need(len(existing) <= 1,'NPC_HATE_UNIQUE_CONTRIBUTOR_REQUIRED')
            old_value = existing[0].hate if existing else 0
            value, total = old_value+increment, state.total_hate+increment
            need(0 <= value <= limit and 0 <= total <= limit,'NPC_HATE_ACCUMULATION_RANGE_UNSUPPORTED')
            if result.hit.landed:
                updated = HateContributor(intent._bound.attacker.uid,value)
                rows = tuple(updated if c is existing[0] else c for c in rows) if existing else rows+(updated,)
            self._hate_births[key] = replace(state,contributors=rows,total_hate=total,
                                            first_attack=first,raw_contributions=snapshot)
        except Exception:
            # HP/accepted results stay committed. Unsupported/partial hate is
            # never converted into a fresh false flag or reward eligibility.
            self._invalidate_hate(key,'UNSUPPORTED_OR_INCOMPLETE_HATE_HISTORY')

    def hate_for_kill(self, receipt):
        """Read supported registered LOCAL birth history with COMBAT's original Port checks."""
        raw = self.contributions_for_kill(receipt)
        key = (id(receipt._entry.writer),receipt._entry.target.uid)
        state = self._hate_births.get(key)
        need(self._hate_source is not None and type(state) is RespawnHate
             and state.status == 'COMPLETE_SUPPORTED_PC_PHYSICAL'
             and state.raw_contributions is raw and state.first_attack is True
             and state.source is self._hate_source[0]
             and sum(c.hate for c in state.contributors) == state.total_hate,
             'NPC_HATE_COMPLETE_REGISTERED_HISTORY_REQUIRED')
        self._respawn_birth_current(state.receipt)
        need(raw._entry.lifetime[5] is state.generation.frames,
             'NPC_HATE_SAME_GENERATION_KILL_REQUIRED')
        return state

    def retire_respawn_birth(self, receipt, generation):
        """Called only after the original Service discarded this exact generation/receipt."""
        key = (id(receipt.writer),receipt.spawn.uid)
        state = self._hate_births.get(key)
        if state is None or state.receipt is not receipt or state.generation is not generation:return False
        service = receipt._service
        service_key = service._key(receipt.writer,receipt.spawn.uid)
        need(service._receipts.get(service_key) is not receipt
             and service._generations.get(service_key) is not generation,
             'NPC_HATE_SERVICE_LIFETIME_NOT_RETIRED')
        del self._hate_births[key]
        return True

    def _prepare(self, writer, row, lifetime, target, intent):
        need(row['operation_lock'].locked(), 'NPC_HP_EXISTING_ROW_LOCK_REQUIRED')
        key = (id(writer), target.uid)
        previous = self._entries.get(key)
        if previous is not None:
            need(previous.writer is writer and previous.row is row
                 and len(previous.lifetime) == len(lifetime)
                 and all(a is b for a, b in zip(previous.lifetime, lifetime))
                 and previous.target == target, 'NPC_HP_SELECTION_LIFETIME_CHANGED')
            need(previous.intent is not intent, 'NPC_HP_INTENT_ALREADY_CONSUMED')
            hp = previous.hp
        else:
            hp = self.provider.initial_hp(target)
            need(type(hp) is Hp and hp.alive, 'NPC_HP_EXPLICIT_INITIAL_HP_REQUIRED')
        need(hp.alive, 'ATTACK_LOCAL_TARGET_DEAD')
        if intent.adjudication is None:
            hit = self.provider.resolve_hit(target, hp, attacker_uid=intent._bound.attacker.uid,
                                            accepted_ordinal=intent.accepted_ordinal)
        else:
            hit = self.provider.hit_for_intent(intent, target, hp)
        need(type(hit) is Hit, 'NPC_HP_EXPLICIT_HIT_REQUIRED')
        after = Hp(max(0, hp.current - hit.damage), hp.maximum)
        result = Result(intent.accepted_ordinal, target, hp, after, hit)
        replacement = _Entry(writer, row, row['operation_lock'], lifetime, target, after, intent)
        return key, previous, replacement, result

    def _commit(self, prepared):
        key, previous, replacement, result = prepared
        need(self._entries.get(key) is previous
             and replacement.row['operation_lock'] is replacement.lock
             and replacement.lock.locked(), 'NPC_HP_CURRENT_ONCE_COMMIT_REQUIRED')
        receipt = None
        if result.died:
            # Allocate before the authority store; no callbacks/awaits are added
            # between the original HP commit and AttackSession acceptance.
            receipt = object.__new__(KillReceipt)
            object.__setattr__(receipt, 'operation_id',
                               f'npc-kill.{self._kill_nonce}.{result.accepted_ordinal}')
            object.__setattr__(receipt, '_issuer', self)
            object.__setattr__(receipt, '_entry', replacement)
            object.__setattr__(receipt, '_result', result)
            object.__setattr__(receipt, '_accepted_session', None)
        self._entries[key] = replacement
        if receipt is not None:
            self._kills[key] = receipt
        return result

    def _accept_damage(self, session, intent, result, prepared):
        """Only the original synchronous accepted event extends this HP-entry chain."""
        from tools.local_original_session import attack_session
        need(type(session) is attack_session.AttackSession and session._hp is self
             and session._hp_provider is self.provider and not session.closed and not session.fatal
             and session._current is intent and session.last_hp_result is result
             and type(result) is Result and type(intent) is attack_session.AttackIntent
             and session.accepted_count == intent.accepted_ordinal == result.accepted_ordinal
             and type(session.last_outcome) is attack_session.AttackOutcome
             and session.last_outcome.kind is attack_session.OutcomeKind.ACCEPTED
             and session.last_outcome.accepted_ordinal == intent.accepted_ordinal,
             'NPC_DAMAGE_REAL_ACCEPTED_EVENT_REQUIRED')
        need(type(prepared) is tuple and len(prepared) == 4,
             'NPC_DAMAGE_EXACT_PREPARED_REQUIRED')
        key, previous, entry, actual_result = prepared
        writer = intent._bound._writer
        source_uid = intent._bound.attacker.uid
        need(type(source_uid) is int and 0 < source_uid < U64_MAX
             and key == (id(writer), result.target.uid) and actual_result is result
             and type(entry) is _Entry and self._entries.get(key) is entry
             and entry.writer is writer and entry.intent is intent and entry.target == result.target
             and entry.row['operation_lock'] is entry.lock and entry.lock.locked()
             and entry.hp is result.after and result.before.maximum == result.after.maximum
             and result.before.current-result.after.current == min(result.before.current,result.hit.damage),
             'NPC_DAMAGE_CURRENT_COMMITTED_ENTRY_REQUIRED')
        old = self._contributions.get(key)
        if previous is None:
            if old is not None:self._invalidate_hate(key,'HP_ENTRY_CHAIN_GAP')
            need(old is None, 'NPC_DAMAGE_INITIAL_CHAIN_REQUIRED')
            initial, count, contributors = result.before, 0, ()
        else:
            if (type(old) is not DamageContributions or old._entry is not previous
                    or old.final_hp is not result.before):
                self._invalidate_hate(key,'HP_ENTRY_CHAIN_GAP')
            need(type(previous) is _Entry and type(old) is DamageContributions
                 and old._entry is previous and old._session is session
                 and old.last_intent is previous.intent and old.final_hp is previous.hp is result.before
                 and old.target == entry.target == previous.target
                 and len(previous.lifetime) == len(entry.lifetime)
                 and all(a is b for a,b in zip(previous.lifetime,entry.lifetime))
                 and old.last_intent.accepted_ordinal < intent.accepted_ordinal,
                 'NPC_DAMAGE_COMPLETE_PREVIOUS_CHAIN_REQUIRED')
            initial, count, contributors = old.initial_hp, old.accepted_events, old.contributors
        matching = tuple(c for c in contributors if c.source_uid == source_uid)
        need(len(matching) <= 1, 'NPC_DAMAGE_UNIQUE_CONTRIBUTOR_REQUIRED')
        prior = matching[0] if matching else DamageContributor(source_uid,0,0,0,0)
        updated = DamageContributor(source_uid, prior.accepted_events+1,
            prior.landed_events+int(result.hit.landed), prior.raw_damage+result.hit.damage,
            prior.hp_loss+result.before.current-result.after.current)
        rows = tuple(updated if c is prior else c for c in contributors) if matching else contributors+(updated,)
        snapshot = DamageContributions(entry.target,initial,result.after,count+1,rows,intent,result,entry,session)
        need(sum(c.accepted_events for c in rows) == snapshot.accepted_events
             and sum(c.hp_loss for c in rows) == initial.current-result.after.current,
             'NPC_DAMAGE_COMPLETE_AGGREGATE_REQUIRED')
        self._contributions[key] = snapshot
        self._advance_hate(intent,result,snapshot,previous)
        return snapshot

    def contributions_for_kill(self, receipt):
        """Read the registered current dead HP-entry chain; no reward/once authority.

        Release/reselection may start another entry chain for the same spawn.
        This read does not establish fresh birth, first-attack state, MP/external
        hate history, or EXP/solo eligibility; retain the original COMBAT Port
        current/lifetime checks. No live-target project or last-kill gate is added."""
        from tools.local_original_session import attack_session
        need(type(receipt) is KillReceipt and receipt._issuer is self,
             'NPC_DAMAGE_REGISTERED_KILL_REQUIRED')
        entry, result, session = receipt._entry, receipt._result, receipt._accepted_session
        key = (id(entry.writer), entry.target.uid)
        snapshot = self._contributions.get(key)
        need(self._kills.get(key) is receipt and self._entries.get(key) is entry
             and type(session) is attack_session.AttackSession and session._hp is self
             and session._hp_provider is self.provider and not session.closed and not session.fatal
             and entry.row['operation_lock'] is entry.lock and entry.lock.locked()
             and type(result) is Result and result.died and not entry.hp.alive
             and entry.hp is result.after and result.target == entry.target
             and type(snapshot) is DamageContributions and snapshot._entry is entry
             and snapshot._session is session and snapshot.last_intent is entry.intent
             and snapshot.last_result is result and snapshot.final_hp is result.after
             and snapshot.target == result.target and snapshot.initial_hp.alive
             and snapshot.initial_hp.maximum == snapshot.final_hp.maximum
             and sum(c.accepted_events for c in snapshot.contributors) == snapshot.accepted_events
             and sum(c.hp_loss for c in snapshot.contributors) == snapshot.initial_hp.current-snapshot.final_hp.current,
             'NPC_DAMAGE_CURRENT_COMPLETE_KILL_CHAIN_REQUIRED')
        return snapshot

    def _accept_kill(self, session, intent, result):
        """The real session calls synchronously after its accepted event stores."""
        from tools.local_original_session import attack_session
        need(type(session) is attack_session.AttackSession and session._hp is self
             and session._current is intent and session.last_hp_result is result
             and session.accepted_count == intent.accepted_ordinal == result.accepted_ordinal,
             'NPC_KILL_REAL_ACCEPTED_EVENT_REQUIRED')
        key = (id(intent._bound._writer), result.target.uid)
        receipt = self._kills.get(key)
        need(type(receipt) is KillReceipt and receipt._issuer is self
             and receipt._accepted_session is None and receipt._result is result
             and self._entries.get(key) is receipt._entry
             and receipt._entry.intent is intent, 'NPC_KILL_COMMITTED_ACCEPTANCE_REQUIRED')
        object.__setattr__(receipt, '_accepted_session', session)

    def _require_alive(self, writer, row, lifetime, target):
        entry = self._entries.get((id(writer), target.uid))
        if entry is not None:
            need(entry.writer is writer and entry.row is row
                 and entry.lock is row['operation_lock'] and entry.lock.locked()
                 and len(entry.lifetime) == len(lifetime)
                 and all(a is b for a, b in zip(entry.lifetime, lifetime))
                 and entry.target == target, 'NPC_HP_SELECTION_LIFETIME_CHANGED')
            need(entry.hp.alive, 'NPC_HP_DEAD_MOTION_REFUSED')

    def release(self, writer, *, target_uid=None):
        for key, state in tuple(self._hate_births.items()):
            if state.receipt.writer is writer and (target_uid is None or state.generation.recipe.uid == target_uid):
                self._invalidate_hate(key,'HP_ENTRY_CHAIN_RELEASED')
        for key, entry in tuple(self._entries.items()):
            if entry.writer is writer and (target_uid is None or entry.target.uid==target_uid):
                del self._entries[key]
                self._kills.pop(key, None)
                self._contributions.pop(key, None)

    def close(self):
        self._entries.clear()
        self._kills.clear()
        self._contributions.clear()
        self._hate_births.clear()
        self._hate_closed = True

    def metadata(self):
        return dict(policy=POLICY, states=[dict(target_uid=e.target.uid, map_id=e.target.map_id,
                    hp=e.hp.current, max_hp=e.hp.maximum, alive=e.hp.alive,
                    last_accepted_ordinal=e.intent.accepted_ordinal) for e in self._entries.values()],
                    scope='CURRENT_SELECTION_MEMORY_ONLY',
                    notification='NOT_IMPLEMENTED_SOURCE_CONTRACT_REQUIRED')
