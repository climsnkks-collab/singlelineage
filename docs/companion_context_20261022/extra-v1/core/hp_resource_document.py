"""Feature-owned RESOURCE DTO/transition/live phase authority for ITEM v2.

Ordinary schema reads never mint a live proof. Phase callbacks use the original
validated raw HP Snapshot borrow, avoiding missing-participant seed recursion
and canonical-commit-before-projection recursion. Caller owns actual selected
scope and the canonical inventory RLock throughout stage/prepare/commit.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib

POLICY = 'CANONICAL_SELECTED_STATUS_RESOURCE_V1'
MAX_REVISION = (1 << 53) - 1
RESOURCE_FIELDS = (10, 11, 12, 13)


def need(value, code):
    if not value:
        raise ValueError(code)


def signed32(value):
    return type(value) is int and -(1 << 31) <= value < (1 << 31)


def validate_document(document):
    need(type(document) is dict and set(document) ==
         {'schema', 'policy', 'uid', 'revision', 'values', 'source'}
         and type(document['schema']) is int and document['schema'] == 1
         and document['policy'] == POLICY and type(document['uid']) is int
         and 0 < document['uid'] <= 0xffffffff and type(document['revision']) is int
         and 0 <= document['revision'] <= MAX_REVISION, 'RESOURCE_DOCUMENT_BINDING')
    values = document['values']
    need(type(values) is dict and set(values) == {'10', '11', '12', '13'}
         and all(signed32(v) for v in values.values()), 'RESOURCE_DOCUMENT_SIGNED32')
    # Reuse the existing HP/life local domain, including death HP0. MP's
    # signed source storage does not establish legal gameplay min/max.
    need(0 <= values['10'] <= values['11'] and values['11'] > 0,
         'RESOURCE_EXISTING_HP_DOMAIN_REQUIRED')
    source = document['source']
    need(type(source) is dict and set(source) == {'kind', 'full_status_sha', 'status_revision'}
         and source['kind'] == 'VERIFIED_CURRENT_HP_STATUS_SNAPSHOT'
         and type(source['status_revision']) is int and 0 <= source['status_revision'] <= MAX_REVISION
         and type(source['full_status_sha']) is str and len(source['full_status_sha']) == 64
         and all(c in '0123456789abcdef' for c in source['full_status_sha']),
         'RESOURCE_SOURCE_PROVENANCE_REQUIRED')
    return document


@dataclass(frozen=True)
class Stage:
    binding: object = field(repr=False)
    snapshot: object = field(repr=False)
    before: dict | None = field(repr=False)
    after: dict = field(repr=False)
    reason: str
    token: object = field(default_factory=object, repr=False)


class ResourceDocument:
    def __init__(self, provider, status, status_module, *, owner=None):
        self.provider, self.status, self.status_module = provider, status, status_module
        self.owner = owner
        self._stage = None

    def validate(self, document):
        return validate_document(document)

    def capability(self, batch):
        return batch.DocumentCapability('RESOURCE', self.validate, scope='character',
            validate_change=self.validate_change, validate_authority=self.validate_authority)

    def seed(self, binding, snapshot):
        self.provider.current(binding)
        need(snapshot is self.status._resource_raw_current(binding.writer)
             and snapshot.target_uid == binding.uid and id(binding.writer) not in self.status._world,
             'RESOURCE_CURRENT_DRAINED_SNAPSHOT_REQUIRED')
        self.status_module.session.world.validate_input(0x4e38, snapshot.fields)
        fields = {str(n): snapshot.fields[n] for n in RESOURCE_FIELDS}
        doc = dict(schema=1, policy=POLICY, uid=binding.uid, revision=snapshot.revision,
            values=fields, source=dict(kind='VERIFIED_CURRENT_HP_STATUS_SNAPSHOT',
                full_status_sha=hashlib.sha256(self.status_module.frame(snapshot.fields)).hexdigest(),
                status_revision=snapshot.revision))
        return self.validate(doc)

    def next_values(self, before, *, values):
        self.validate(before)
        need(before['revision'] < MAX_REVISION, 'RESOURCE_REVISION_OVERFLOW')
        after = deepcopy(before)
        after['revision'] += 1
        after['values'] = deepcopy(values)
        return self.validate(after)

    def _live(self, stage):
        self.provider.current(stage.binding)
        need(self.owner is not None and self.owner.status is self.status
             and self.status._resource_owner is self.owner,
             'RESOURCE_SINGLE_WRITER_INTERCEPTOR_REQUIRED')
        need(self.status._resource_raw_current(stage.binding.writer) is stage.snapshot
             and stage.snapshot.target_uid == stage.binding.uid,
             'RESOURCE_STAGED_RAW_SNAPSHOT_CHANGED')
        need(self.owner.authorize_stage(stage) is True,
             'RESOURCE_OWNER_COMPUTED_OPERATION_REQUIRED')
        return True

    def validate_change(self, before, after, uid):
        self.validate(after)
        stage = self._stage
        need(type(stage) is Stage and stage.binding.uid == uid == after['uid']
             and before == stage.before and after == stage.after, 'RESOURCE_EXACT_STAGE_REQUIRED')
        if before is None:
            need(stage.reason == 'SEED' and after == self.seed(stage.binding, stage.snapshot),
                 'RESOURCE_EXACT_SOURCE_SEED_REQUIRED')
        else:
            self.validate(before)
            need(before['uid'] == uid and after['source'] == before['source']
                 and after['revision'] == before['revision'] + 1,
                 'RESOURCE_SELECTED_REVISION_TRANSITION_REQUIRED')
            need(stage.reason in ('CAST_COST', 'HP_EFFECT', 'PLAYER_LIFE'),
                 'RESOURCE_EXPLICIT_PRODUCER_REQUIRED')
        return self._live(stage)

    def validate_authority(self, binding, before, after, phase):
        need(phase in ('SEED', 'PREPARE', 'COMMIT'), 'RESOURCE_PHASE_REQUIRED')
        stage = self._stage
        need(type(stage) is Stage and binding is stage.binding
             and before == stage.before and after == stage.after,
             'RESOURCE_EXACT_PHASE_STAGE_REQUIRED')
        need((before is None and phase in ('SEED', 'COMMIT') and stage.reason == 'SEED')
             or before is not None and phase in ('PREPARE', 'COMMIT'),
             'RESOURCE_PHASE_TRANSITION_REQUIRED')
        self.validate_change(before, after, binding.uid)
        return True

    @contextmanager
    def staged(self, binding, snapshot, before, after, *, reason):
        need(self._stage is None, 'RESOURCE_PHASE_REENTRY_REFUSED')
        stage = Stage(binding, snapshot, deepcopy(before), deepcopy(after), reason)
        self._stage = stage
        try:
            self.validate_change(before, after, binding.uid)
            yield stage
        finally:
            self._stage = None
