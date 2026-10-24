"""Fail-closed LOCAL projectile/door source port. No live producer supplied."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

POLICY = 'LOCAL_CURRENT_PROJECTILE_AND_DOORS_V1'


def need(value, reason):
    if not value:
        raise ValueError(reason)


@dataclass(frozen=True)
class VisibilityQuery:
    operation: object = field(repr=False)
    decoded: object = field(repr=False)
    bound: object = field(repr=False)
    packet_current: object = field(repr=False)
    namespace: object = field(repr=False)
    issuer: object = field(repr=False)
    spawn: object = field(repr=False)
    resource_snapshot: object = field(repr=False)
    geometry: tuple


@dataclass(frozen=True)
class VisibilityDecision:
    query: VisibilityQuery = field(repr=False)
    producer: object = field(repr=False)
    policy: str
    verdict: str
    map_current: object = field(repr=False)
    doors_current: object = field(repr=False)
    classification: str = POLICY


class CurrentProjectileVisibility(ABC):
    """Trusted cold server source, never client data or a bool callback.

    decide must read current projectile-passability AND dynamic door/override
    authority under this operation's held lock. Every field is same-operation;
    current must raise if either map/door epoch, target, caster or lifetime has
    changed. CLEAR must cover the complete segment, including both endpoints
    and diagonal/corner policy. No await, guessed empty map, static-only S32,
    adjacency, range-only or movement-mask substitutions. This port is LOCAL;
    it proves no original/native spell visual or NPC HPbar contract.
    """
    @abstractmethod
    def decide(self, query): ...

    @abstractmethod
    def current(self, query, decision): ...


class UnresolvedVisibility(CurrentProjectileVisibility):
    def decide(self, query):
        raise ValueError('CAST_LOCAL_PROJECTILE_DOOR_CURRENT_PRODUCER_REQUIRED')

    def current(self, query, decision):
        raise ValueError('CAST_LOCAL_PROJECTILE_DOOR_CURRENT_PRODUCER_REQUIRED')


def geometry(bound):
    p = bound.attacker
    return (p.map_id, p.word0, p.word1, bound.map_id,
            bound.target_x, bound.target_y, p.uid, bound.target_uid)


class VisibilityGuard:
    def __init__(self, producer=None):
        producer = UnresolvedVisibility() if producer is None else producer
        need(isinstance(producer, CurrentProjectileVisibility),
             'CAST_LOCAL_TYPED_VISIBILITY_PRODUCER_REQUIRED')
        self.producer = producer

    def verify(self, operation, decoded, bound, context, namespace, issuer, spawn, snapshot):
        need(self.producer is not None, 'CAST_LOCAL_VISIBILITY_CLOSED')
        need(operation.binding.operation_lock.locked(), 'CAST_LOCAL_VISIBILITY_HELD_LOCK_REQUIRED')
        query = VisibilityQuery(operation, decoded, bound, context, namespace,
                                issuer, spawn, snapshot, geometry(bound))
        decision = self.producer.decide(query)
        need(type(decision) is VisibilityDecision and decision.query is query
             and decision.producer is self.producer,
             'CAST_LOCAL_SAME_OPERATION_MAP_DOOR_DECISION_REQUIRED')
        bypass = type(self.producer) is LocalTestVisibility
        need((bypass and decision.policy == TEST_POLICY and decision.classification == TEST_POLICY
              and decision.map_current is None and decision.doors_current is None)
             or (not bypass and decision.policy == POLICY and decision.classification == POLICY
                 and decision.map_current is not None and decision.doors_current is not None),
             'CAST_LOCAL_VISIBILITY_EXACT_POLICY_SCOPE_REQUIRED')
        need(decision.verdict in ('CLEAR', 'BLOCKED', 'UNKNOWN'), 'CAST_LOCAL_VISIBILITY_VERDICT_REQUIRED')
        need(self.producer.current(query, decision) is None,
             'CAST_LOCAL_VISIBILITY_CURRENT_MUST_RAISE_NOT_BOOLEAN')
        need(operation.binding.operation_lock.locked() and geometry(bound) == query.geometry,
             'CAST_LOCAL_VISIBILITY_GEOMETRY_OR_LOCK_CHANGED')
        need(decision.verdict == 'CLEAR', 'CAST_LOCAL_VISIBILITY_NOT_CLEAR')
        return decision

    def close(self):
        self.producer = None


# Explicit human authorization: "예, 시험 서버에서만 허용".
# This is an admission bypass for the LOCAL test stage, never a LOS observation.
TEST_POLICY = 'LOCAL_TEST_VISIBILITY_BYPASS'
TEST_PURPOSE = 'LOCAL_MP_DEBIT_NPC_HP_SERVER_STATE_TRIAL'
TEST_OWNER = '01a16d46-f794-7841-986e-1705a2b95c0b'


@dataclass(frozen=True)
class TestTrialScope:
    server: object = field(repr=False)
    factory: object = field(repr=False)
    admission: object = field(repr=False)
    broker: object = field(repr=False)
    plan: object = field(repr=False)
    owner: object = field(repr=False)
    hostile_policy: object = field(repr=False)
    original_evidence: object
    original_root: object
    profile: object
    account: object
    test_owner: str
    purpose: str
    opt_in: str


class LocalTestVisibility(CurrentProjectileVisibility):
    """TEST-only range/current bypass. map_current/doors_current stay None.

    Created solely by install_test_visibility_cold. No CLI/environment default;
    no override of current/lease/learned, range, costs, damage or receipt checks.
    """
    def __init__(self, scope, *, _seal):
        need(_seal is _TEST_SEAL and type(scope) is TestTrialScope,
             'CAST_TEST_VISIBILITY_COLD_INSTALL_REQUIRED')
        self.scope = scope

    def _current(self, q):
        s=self.scope; server=s.server; b=s.broker; a=s.admission
        need(s.opt_in == TEST_POLICY and s.purpose == TEST_PURPOSE and s.test_owner == TEST_OWNER,
             'CAST_TEST_VISIBILITY_EXPLICIT_SCOPE_REQUIRED')
        need(server.prepared and server.started and not server.closed and server.broker is b
             and b._started and not b._closing and server.basic_inputs.plan is s.plan
             and s.plan._hostile_cold_factory is s.factory and s.plan._broker is b
             and s.plan._owner is s.owner and s.owner is b._hp_resource_owner
             and s.owner._combat_hostile is s.hostile_policy
             and getattr(s.hostile_policy,'_local_server_state',False) is True
             and s.plan.profile == s.profile and server.store_path.resolve() == s.profile
             and s.profile == s.original_evidence.profile and server.expected_uuid == s.account
             and not a.closed and a.enabled and a is b._cast_feature.hostile_admission
             and a.visibility.producer is self,
             'CAST_TEST_VISIBILITY_SAME_RUNNING_TEST_PLAN_REQUIRED')
        need(q.operation.binding.operation_lock.locked() and q.operation.binding.uid == q.geometry[6] == 3
             and q.decoded.request.signed_lookup_key == 3,
             'CAST_TEST_VISIBILITY_ENERGYBOLT_OPERATION_REQUIRED')
        target,context,namespace,issuer,spawn,snapshot = a._current(q.operation,q.decoded)
        need(all(x is y for x,y in zip((context,namespace,issuer,spawn,snapshot),
             (q.packet_current,q.namespace,q.issuer,q.spawn,q.resource_snapshot)))
             and target == q.bound.target_uid and q.bound.attacker is context.position
             and a.targets.revalidate(q.bound) is q.operation.row
             and namespace.npc_issued_current(spawn) is True and namespace.setup.npc_issuer is issuer,
             'CAST_TEST_VISIBILITY_SAME_ISSUED_TARGET_CURRENT_REQUIRED')
        g=geometry(q.bound)
        need(g == q.geometry and g[0] == g[3]
             and max(abs(g[1]-g[4]),abs(g[2]-g[5])) <= a._direct.describe(3).ranged,
             'CAST_TEST_VISIBILITY_SAME_MAP_REFERENCE_RANGE_REQUIRED')
        # Intentionally DO NOT read or claim projectile/wall/door visibility.

    def describe(self):
        return dict(classification=TEST_POLICY, purpose=TEST_PURPOSE,
                    wall_door_visibility='INTENTIONALLY_SKIPPED_TEST_ONLY',
                    native_los='UNKNOWN', native_spell_visual='UNKNOWN', npc_hpbar='UNKNOWN')

    def decide(self, query):
        self._current(query)
        return VisibilityDecision(query,self,TEST_POLICY,'CLEAR',None,None,TEST_POLICY)

    def current(self, query, decision):
        need(type(decision) is VisibilityDecision and decision.query is query
             and decision.producer is self and decision.policy == TEST_POLICY
             and decision.classification == TEST_POLICY,
             'CAST_TEST_VISIBILITY_SAME_DECISION_REQUIRED')
        self._current(query)


_TEST_SEAL = object()


def install_test_visibility_cold(*, selected, factory, server, test_owner, purpose, opt_in):
    """Trusted Test caller only, after prepare and before normal factory enable.

    selected is the actual (modules, SourceModules) tuple returned by existing
    hostile_business_inputs.selected_sources. These are cold source identities,
    never a client payload or self-asserted runtime bool.
    """
    from pathlib import Path
    import ipaddress
    m,pins=selected
    source_type=m['canonical_feature_bootstrap'].SourceModule
    for role in ('original_evidence','local_visibility','cast_route','packet_server','attack_cold_factory'):
        need(type(pins[role]) is source_type and pins[role].module is m[role]
             and pins[role].check() is m[role], 'CAST_TEST_VISIBILITY_EXACT_COLD_SOURCE_REQUIRED')
    here=Path(__file__).resolve().parent
    need(Path(m['local_visibility'].__file__).resolve() == Path(__file__).resolve()
         and m['local_visibility'].LocalTestVisibility is LocalTestVisibility
         and Path(m['cast_route'].__file__).resolve() == here/'cast_route.py'
         and Path(m['original_evidence'].__file__).resolve() == here/'original_evidence.py',
         'CAST_TEST_VISIBILITY_EXACT_TEST_LEAF_REQUIRED')
    need(opt_in == TEST_POLICY and purpose == TEST_PURPOSE and test_owner == TEST_OWNER,
         'CAST_TEST_VISIBILITY_EXPLICIT_SCOPE_REQUIRED')
    need(type(factory) is m['attack_cold_factory'].ColdFactory
         and type(server) is m['packet_server'].PacketServer,
         'CAST_TEST_VISIBILITY_SELECTED_FACTORY_SERVER_REQUIRED')
    factory._current()
    proof=m['original_evidence'].verify_completed_original()
    need(type(proof) is m['original_evidence'].OriginalEvidence,
         'CAST_TEST_ORIGINAL_TYPED_COMPLETION_REQUIRED')
    original=proof.account
    b=server.broker; plan=server.basic_inputs.plan
    need(server.prepared and not server.started and not server.closed
         and not b._started and not b._closing and not b.realm.registry._sessions
         and type(plan) is m['canonical_feature_bootstrap'].CanonicalFeatureBootstrap
         and plan._hostile_cold_factory is factory and plan._lifetime_state == 'BOUND'
         and plan._broker is b and plan._owner is b._hp_resource_owner
         and plan.profile.is_file() and plan.profile == server.store_path.resolve()
         and plan.profile == proof.profile and server.expected_uuid == factory.account,
         'CAST_TEST_VISIBILITY_SAME_PREPARED_ORIGINAL_TEST101_PLAN_REQUIRED')
    need(server.sockets and all(ipaddress.ip_address(sock.getsockname()[0]).is_loopback
                               for sock in server.sockets.values()),
         'CAST_TEST_VISIBILITY_LOOPBACK_ONLY_REQUIRED')
    owner,policy,handle=factory._attached
    a=handle.admission; f=handle.feature
    need(owner is plan._owner and owner._combat_hostile is policy
         and not getattr(policy,'_local_server_state',False) and f is b._cast_feature and f.hostile_admission is a
         and type(a) is m['cast_route'].LocalPacketNpcAdmission and not a.closed
         and a.enabled is False and type(a.visibility) is VisibilityGuard
         and type(a.visibility.producer) is UnresolvedVisibility
         and a.targets is b._attack_session.targets and a.status is owner.status,
         'CAST_TEST_VISIBILITY_SAME_DISABLED_ADMISSION_REQUIRED')
    scope=TestTrialScope(server,factory,a,b,plan,owner,policy,proof,original,plan.profile,
                         server.expected_uuid,test_owner,purpose,opt_in)
    producer=LocalTestVisibility(scope,_seal=_TEST_SEAL)
    a.visibility=VisibilityGuard(producer)
    return producer
