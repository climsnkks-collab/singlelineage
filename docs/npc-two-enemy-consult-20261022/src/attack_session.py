"""Opt-in validated attack intents and separately explicit local feedback trials.

The caller owns the real broker row operation lock and all transport/native
resources. Each handle call independently checks its actual request/writer;
identical payloads have no invented replay or request-ID interpretation.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum

from tools.local_original_session import attack

EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT = 'EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT'

# Only these exact local request-policy refusals are normal route results.
# Current owner/claim/selection/storage/source failures always propagate.
LOCAL_REJECTIONS = frozenset({
    'ATTACK_LOCAL_ACTOR_TARGET_REQUIRED',
    'ATTACK_LOCAL_SELF_TARGET_REFUSED',
    'ATTACK_CURRENT_TYPED_NPC_REQUIRED',
    'ATTACK_LOCAL_CURRENT_TARGET_COORDINATES_REQUIRED',
    'ATTACK_LOCAL_TARGET_DEAD',
    'ATTACK_LOCAL_TARGET_REMOVED',
})


class OutcomeKind(str, Enum):
    DISABLED = 'DISABLED'
    ACCEPTED = 'ACCEPTED'
    REJECTED = 'REJECTED'
    ERROR = 'ERROR'
    CANCELLED = 'CANCELLED'
    CLOSED = 'CLOSED'
    FATAL = 'FATAL'


@dataclass(frozen=True, slots=True)
class AttackOutcome:
    kind: OutcomeKind
    reason: str
    accepted_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class FeedbackConfig:
    """Explicit local trial values; no combat or self-prediction default."""
    policy: str
    raw_effect: int
    direction: int
    self_action: bool

    def __post_init__(self):
        from tools.local_original_session import attack_feedback
        attack.need(type(self.policy) is str and self.policy == attack_feedback.POLICY,
                    'ATTACK_FEEDBACK_EXPLICIT_POLICY_REQUIRED')
        attack._int32(self.raw_effect)
        attack.need(type(self.direction) is int and 0 <= self.direction <= 8,
                    'ATTACK_EXPLICIT_DIRECTION_REQUIRED')
        attack.need(type(self.self_action) is bool, 'ATTACK_FEEDBACK_EXPLICIT_F13_REQUIRED')


@dataclass(frozen=True, slots=True)
class AttackIntent:
    """Current capability, usable only after the service revalidates its bound.

    The bound is intentionally absent from repr and all metadata. It is never
    used to authorize a later incoming frame or stored as request history.
    """
    accepted_ordinal: int
    _bound: attack.BoundTarget = field(repr=False, compare=False)


def _error_category(error):
    # Never serialize arbitrary exception text, payload bytes or capabilities.
    if type(error) is ValueError:
        reason = str(error)
        if reason == 'MALFORMED_ATTACK_PAYLOAD':
            return 'MALFORMED_ATTACK_PAYLOAD'
        if reason == 'ATTACK_SOURCE_CHANGED':
            return 'ATTACK_SOURCE_CHANGED'
        if reason in LOCAL_REJECTIONS:
            return reason
        return 'CURRENT_AUTHORITY_INVALID'
    return 'UNEXPECTED_ERROR'


class AttackSession:
    """One bounded current intent for a real broker/retained-reader authority.

    Default off. No HP, raw-effect, direction or f13 value is inferred.
    Accepted counts are exact and bounded: capacity refuses before acceptance,
    rather than saturating and claiming another once-only event occurred.
    """
    def __init__(self, targets, *, policy=None, counter_limit=attack.U64_MAX, feedback=None, hp_provider=None,
                 death_policy=None, remove_policy=None):
        attack.need(type(targets) is attack.AttackTargets, 'ATTACK_SESSION_REAL_TARGETS_REQUIRED')
        attack.need(policy is None or (type(policy) is str
                    and policy == EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT),
                    'ATTACK_SESSION_EXPLICIT_POLICY_REQUIRED')
        attack.need(type(counter_limit) is int and 1 <= counter_limit <= attack.U64_MAX,
                    'ATTACK_SESSION_UINT64_COUNTER_LIMIT_REQUIRED')
        attack.need(feedback is None or type(feedback) is FeedbackConfig
                    and policy == EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT,
                    'ATTACK_FEEDBACK_REQUIRES_INTENT_POLICY')
        attack.need(hp_provider is None or policy == EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT,
                    'NPC_HP_REQUIRES_INTENT_POLICY')
        self._hp_provider = hp_provider
        self._hp = None
        self.last_hp_result = None
        if hp_provider is not None:
            from tools.local_original_session import npc_hp
            self._hp = npc_hp.Authority(hp_provider)
        self._notifications = None
        if death_policy is not None or remove_policy is not None:
            from tools.local_original_session import npc_death
            attack.need(type(death_policy) is str and death_policy == npc_death.DEATH_POLICY
                        and (remove_policy is None or type(remove_policy) is str
                             and remove_policy == npc_death.REMOVE_POLICY)
                        and self._hp is not None and feedback is not None,
                        'NPC_DEATH_REQUIRES_EXPLICIT_HP_AND_FEEDBACK')
            self._notifications = npc_death.Notifications(self, death_policy=death_policy,
                                                        remove_policy=remove_policy)
        self.feedback = feedback
        self._feedback_frame = self._feedback_intent = self._feedback_row = self._feedback_lock = None
        self._feedback_state = 'DISABLED' if feedback is None else 'NOT_REQUESTED'
        self.feedback_prepared = self.feedback_reserved = self.feedback_write_attempted = self.feedback_drained = 0
        self.targets = targets
        self.policy = policy
        self.counter_limit = counter_limit
        self.accepted_count = 0
        self.closed = False
        self.fatal = False
        self.last_outcome = None
        self.last_invalidation = None
        self._current = None
        self._lock = asyncio.Lock()  # Distinct from the caller-owned row lock.

    def _hp_binding(self, writer, row, uid):
        from tools.local_original_session import npc_hp
        broker = self.targets.broker
        realm = broker.realm
        attack.need(broker._attack_session is self and realm._attack_session is self
                    and self._hp.provider is self._hp_provider
                    and self._hp_provider.policy == npc_hp.POLICY,
                    'NPC_HP_SAME_REAL_ATTACK_SESSION_REQUIRED')
        game, service = realm.registry.resolve(writer), realm.service(writer)
        frames = realm.npc_frames(writer,target_uid=uid)
        spawn, = [spawn for spawn, wire in realm._npc_spawns if spawn.uid == uid]
        lock = row['operation_lock']
        attack.need(lock.locked(), 'NPC_HP_EXISTING_ROW_LOCK_REQUIRED')
        # The Position and motion.State in BoundTarget must be fresh for each
        # attack, but neither is the HP lifetime: normal motion preserves HP.
        lifetime = (realm, realm.registry, game, game.selection, service, frames,
                    realm._npc_spawns, spawn, lock, row['policy_row'])
        target = npc_hp.Target(spawn.uid, spawn.map_id, spawn.fields[3], spawn.fields[39])
        return lifetime, target

    def _hp_prepare(self, intent):
        bound = intent._bound
        row = self.targets.revalidate(bound)
        lifetime, target = self._hp_binding(bound._writer, row, bound.target_uid)
        return self._hp._prepare(bound._writer, row, lifetime, target, intent)

    def _hp_validate(self, intent, prepared):
        bound = intent._bound
        row = self.targets.revalidate(bound)
        lifetime, target = self._hp_binding(bound._writer, row, bound.target_uid)
        replacement = prepared[2]
        attack.need(replacement.intent is intent and replacement.row is row
                    and replacement.target == target
                    and len(replacement.lifetime) == len(lifetime)
                    and all(a is b for a, b in zip(replacement.lifetime, lifetime)),
                    'NPC_HP_SAME_INTENT_LIFETIME_REQUIRED')

    def require_live_npc_motion(self, writer, row, uid):
        """New motion admission only; an accepted lethal feedback stays valid."""
        if self._hp is None:
            return
        attack.need(not self.closed and not self.fatal, 'NPC_HP_SESSION_UNAVAILABLE')
        if self._notifications is not None and self._notifications.is_removed(writer, uid):
            raise ValueError('NPC_HP_DEAD_MOTION_REFUSED')
        attack.source_ready()
        actual = self.targets._project(writer, attack.AttackRequest(uid))
        attack.need(actual[0] is row, 'NPC_HP_SAME_MOTION_ROW_REQUIRED')
        lifetime, target = self._hp_binding(writer, row, uid)
        self._hp._require_alive(writer, row, lifetime, target)

    def _clear(self, reason):
        self._current = None
        if self._feedback_state in ('PREPARED', 'RESERVED', 'WRITE_ATTEMPTED'):
            self._feedback_state = 'TERMINAL'
        self.last_invalidation = reason

    def _outcome(self, kind, reason, ordinal=None):
        self.last_outcome = AttackOutcome(kind, reason, ordinal)
        return ()

    def _unavailable(self):
        if self.closed:
            return OutcomeKind.CLOSED, 'ATTACK_SESSION_CLOSED'
        if self.fatal:
            return OutcomeKind.FATAL, 'ATTACK_SESSION_FATAL'
        if self.policy is None:
            return OutcomeKind.DISABLED, 'ATTACK_SESSION_DISABLED'
        if self.accepted_count >= self.counter_limit:
            return OutcomeKind.REJECTED, 'ATTACK_SESSION_COUNTER_CAPACITY'
        return None

    async def handle(self, writer, payload) -> tuple[bytes, ...]:
        """Validate one CS4E30; only explicit feedback prepares one reply frame.

        Known local target refusals return REJECTED/(). Other failures retain
        their original exception; ERROR metadata distinguishes malformed wire,
        changed source, authority loss and unexpected exceptions. Cancellation
        clears intent and propagates. There is no retry and no nested row lock.
        """
        async with self._lock:
            unavailable = self._unavailable()
            if unavailable is not None:
                # Capacity ends the old intent too; it is no retry authority.
                self._clear(unavailable[1])
                return self._outcome(*unavailable)
            try:
                attack.need(self._feedback_state not in ('PREPARED', 'RESERVED', 'WRITE_ATTEMPTED', 'TERMINAL'),
                            'ATTACK_FEEDBACK_PREVIOUS_OUTCOME_UNRESOLVED')
                request = attack.parse_payload(payload)
                bound = await self.targets.authorize(writer, request)
                await self.targets.checkpoint(bound)
                # No await between this final authority/lifetime/capacity
                # check and the single accepted event commit below.
                attack.source_ready()
                self.targets.revalidate(bound)
                unavailable = self._unavailable()
                if unavailable is not None:
                    self._clear(unavailable[1])
                    return self._outcome(*unavailable)
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    # A synchronous owner/read callback can request cancel
                    # without yielding. Do not commit before its next delivery.
                    raise asyncio.CancelledError()
                ordinal = self.accepted_count + 1
                intent = AttackIntent(ordinal, bound)
                prepared_hp = None if self._hp is None else self._hp_prepare(intent)
                if prepared_hp is not None:
                    # Synchronous provider code may fail, cancel, close or
                    # mutate source authority. Nothing was stored by prepare.
                    attack.source_ready()
                    self._hp_validate(intent, prepared_hp)
                    unavailable = self._unavailable()
                    if unavailable is not None:
                        self._clear(unavailable[1])
                        return self._outcome(*unavailable)
                    if task is not None and task.cancelling():
                        raise asyncio.CancelledError()
                    self.last_hp_result = self._hp._commit(prepared_hp)
                # No await/callback between HP commit and this exact accepted
                # event. Later feedback errors never roll it back or replay it.
                self._current = intent
                self.accepted_count = ordinal
                self.last_invalidation = None
                self._outcome(OutcomeKind.ACCEPTED, 'LOCAL_VALIDATED_ATTACK_INTENT', ordinal)
                if prepared_hp is not None and self.last_hp_result.died:
                    self._hp._accept_kill(self, intent, self.last_hp_result)
                if self.feedback is None:
                    return ()
                from tools.local_original_session import attack_feedback
                # These exact objects remain owned by this current intent, not
                # a transferable receipt or a later frame's authorization.
                row = self.targets.revalidate(bound)
                lock = row['operation_lock']
                attack.need(lock.locked(), 'ATTACK_FEEDBACK_ROW_LOCK_REQUIRED')
                frame = attack_feedback.build_feedback(self.targets, bound,
                    policy=self.feedback.policy, raw_effect=self.feedback.raw_effect,
                    direction=self.feedback.direction, self_action=self.feedback.self_action)
                attack.need(self._current is not None and self._current._bound is bound
                            and row['operation_lock'] is lock and lock.locked(),
                            'ATTACK_FEEDBACK_SAME_INTENT_REQUIRED')
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                self._feedback_frame, self._feedback_intent = frame, self._current
                self._feedback_row, self._feedback_lock = row, lock
                self._feedback_state = 'PREPARED'
                self.feedback_prepared += 1
                return (frame,)
            except asyncio.CancelledError:
                self._clear('ATTACK_SESSION_CANCELLED')
                self._outcome(OutcomeKind.CANCELLED, 'ATTACK_SESSION_CANCELLED')
                raise
            except Exception as error:
                # Record a bounded category and re-raise every nonlocal error;
                # this is not an exception-to-success fallback.
                category = _error_category(error)
                self._clear(category)
                if type(error) is ValueError and str(error) in LOCAL_REJECTIONS:
                    return self._outcome(OutcomeKind.REJECTED, category)
                self._outcome(OutcomeKind.ERROR, category)
                raise

    def validate_feedback(self, writer, wire, *, state):
        """Revalidate the sole immutable frame under the original caller lock."""
        from tools.local_original_session import attack_feedback
        current, row, lock = self._feedback_intent, self._feedback_row, self._feedback_lock
        attack.need(self.feedback is not None and not self.closed and not self.fatal
                    and self._feedback_state == state and type(wire) is bytes
                    and wire is self._feedback_frame and current is not None
                    and current is self._current and current.accepted_ordinal == self.accepted_count
                    and current._bound._writer is writer,
                    'ATTACK_FEEDBACK_CURRENT_FRAME_REQUIRED')
        attack.source_ready()
        parsed = attack_feedback.validate_frame(wire, policy=self.feedback.policy)
        attack.need((parsed.attacker_uid, parsed.target_uid, parsed.raw_effect,
                     parsed.direction, parsed.self_action) ==
                    (current._bound.attacker.uid, current._bound.target_uid, self.feedback.raw_effect,
                     self.feedback.direction, self.feedback.self_action),
                    'ATTACK_FEEDBACK_EXACT_FIELDS_REQUIRED')
        actual = self.targets.revalidate(current._bound)
        attack.need(actual is row and row['operation_lock'] is lock and lock.locked()
                    and self.targets.broker._attack_session is self
                    and self.targets.broker.realm._attack_session is self
                    and self._current is current and self._feedback_frame is wire,
                    'ATTACK_FEEDBACK_SAME_ROW_LOCK_INTENT_REQUIRED')
        return current

    def reserve_feedback(self, writer, wire):
        self.validate_feedback(writer, wire, state='PREPARED')
        self._feedback_state = 'RESERVED'
        self.feedback_reserved += 1

    def feedback_attempt(self, writer, wire):
        self.validate_feedback(writer, wire, state='RESERVED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        self._feedback_state = 'WRITE_ATTEMPTED'
        self.feedback_write_attempted += 1

    def feedback_drain(self, writer, wire):
        self.validate_feedback(writer, wire, state='WRITE_ATTEMPTED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        self._feedback_state = 'DRAINED'
        self.feedback_drained += 1

    def current_intent(self) -> AttackIntent | None:
        """Revalidate the sole current capability; stale ValueError clears it.

        This observational API cannot grant another request. Unexpected errors
        propagate after clearing. The handle route propagates authority errors
        independently, even if an earlier observational query cleared intent.
        """
        current = self._current
        if current is None:
            return None
        if self.closed or self.fatal:
            self._clear('ATTACK_SESSION_CLOSED' if self.closed else 'ATTACK_SESSION_FATAL')
            return None
        try:
            attack.source_ready()
            self.targets.revalidate(current._bound)
        except ValueError as error:
            self._clear(_error_category(error))
            return None
        except Exception:
            self._clear('UNEXPECTED_ERROR')
            raise
        return current

    def metadata(self):
        current = self.current_intent()
        outcome = self.last_outcome
        result = dict(policy=self.policy, enabled=self.policy is not None,
                    closed=self.closed, fatal=self.fatal,
                    accepted_count=self.accepted_count, counter_limit=self.counter_limit,
                    current_ordinal=None if current is None else current.accepted_ordinal,
                    last_invalidation=self.last_invalidation,
                    last_outcome=None if outcome is None else dict(
                        kind=outcome.kind.value, reason=outcome.reason,
                        accepted_ordinal=outcome.accepted_ordinal),
                    response_policy=('NO_COMBAT_REPLY_UNTIL_SOURCE_CONTRACT' if self.feedback is None
                                     else self.feedback.policy),
                    feedback=dict(state=self._feedback_state,
                        ordinal=None if self._feedback_intent is None else self._feedback_intent.accepted_ordinal,
                        prepared=self.feedback_prepared,
                        reserved=self.feedback_reserved, write_attempted=self.feedback_write_attempted,
                        drained=self.feedback_drained, proof_scope='TRANSPORT_DRAIN_ONLY',
                        client_action='UNKNOWN', hp='UNKNOWN', combat_effect='UNKNOWN'),
                    duplicate_policy='EACH_FRAME_INDEPENDENTLY_VALIDATED')
        if self._notifications is not None:
            result['npc_notifications'] = self._notifications.metadata()
        if self._hp is not None:
            result['npc_hp'] = self._hp.metadata()
            result['npc_hp']['last_commit'] = (None if self.last_hp_result is None
                                               else self.last_hp_result.metadata())
        return result

    def release(self, writer, *, target_uid=None):
        """Drop only this writer's current intent; preserve accepted history.

        The caller uses this at realm writer teardown. Literal writer identity
        is sufficient to revoke, and grants no new request authority.
        """
        if self._notifications is not None:
            self._notifications.release(writer,target_uid=target_uid)
        if self._hp is not None:
            self._hp.release(writer,target_uid=target_uid)
        current = self._current
        if (current is not None and current._bound._writer is writer
                and (target_uid is None or current._bound.target_uid==target_uid)):
            self._clear('ATTACK_SESSION_WRITER_RELEASED')

    def close(self):
        if self._notifications is not None:
            self._notifications.close()
        if self._hp is not None:
            self._hp.close()
        self.closed = True
        self._clear('ATTACK_SESSION_CLOSED')
        self._outcome(OutcomeKind.CLOSED, 'ATTACK_SESSION_CLOSED')

    def fail(self):
        if self._notifications is not None:
            self._notifications.fail()
        if self._hp is not None:
            self._hp.close()
        self.fatal = True
        self._clear('ATTACK_SESSION_FATAL')
        self._outcome(OutcomeKind.FATAL, 'ATTACK_SESSION_FATAL')
