"""Concrete SKILL consumer of ITEM's same-inventory.json participant API.

No independent skills file, asset store, MP balance or HP writer. The draft
backend is imported/injected by the integration owner; its final source pin is
pending. This module never acquires/adopts an already-held legacy operation
lock: caller enters provider.selected_operation at the original owning site.
"""
from contextlib import contextmanager, asynccontextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import uuid

API_PATH = 'work/local_original_session/implementation-1/item-equipment-product/transactions/shop-skill-batch-v1/API.md'
API_SHA256 = 'e9286eb772f2a93563aa9b455d5c9faabdab275d196d47192f7a13adb552a134'


def need(value, code):
    if not value:
        raise ValueError(code)


class SkillDocument:
    """Feature-owned schema and exact actor-only staged change capability."""
    def __init__(self, batch, core, provider, *, account, rules):
        need(type(account) is str and str(uuid.UUID(account)) == account, 'SKILL_ACCOUNT_INVALID')
        need(type(rules) is tuple and 0 < len(rules) <= 128
             and all(type(rule) is core.Rule for rule in rules), 'SKILL_RULES_REQUIRED')
        self.batch, self.core, self.provider = batch, core, provider
        self.rules = {r.spell_id: r for r in rules}
        need(len(self.rules) == len(rules), 'SKILL_DUPLICATE_RULE')
        self.account = account
        self.rule_hash = hashlib.sha256(json.dumps([asdict(self.rules[k]) for k in sorted(self.rules)],
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self._stage = None

    def validate(self, document):
        validator = object.__new__(self.core.Store)
        validator.rules, validator.account, validator.rule_hash = self.rules, self.account, self.rule_hash
        return validator._validate(document)

    def capability(self):
        return self.batch.DocumentCapability('SKILL', self.validate,
            scope='account', validate_change=self.validate_change)

    def initial_document(self, binding, *, now_ms):
        self.provider.current(binding)
        need(self.core.integer(now_ms), 'SKILL_SERVER_CLOCK_REQUIRED')
        return dict(schema=1, policy=self.core.POLICY, account=self.account, rules=self.rule_hash,
            characters={str(binding.uid): dict(learned=[], cooldowns={}, buffs={}, revision=0, clock=now_ms)})

    def validate_change(self, before, after, uid):
        self.validate(after)
        stage = self._stage
        need(stage is not None, 'SKILL_UNSTAGED_PARTICIPANT_CHANGE')
        binding, staged_before, staged_after = stage
        self.provider.current(binding)
        need(binding.uid == uid and before == staged_before and after == staged_after,
             'SKILL_STAGED_CHANGE_MISMATCH')
        if before is None:
            need(set(after['characters']) == {str(uid)}, 'SKILL_INITIAL_SELECTED_CHARACTER_ONLY')
        else:
            self.validate(before)
            need({k:v for k,v in before.items() if k != 'characters'} ==
                 {k:v for k,v in after.items() if k != 'characters'}, 'SKILL_ACCOUNT_BINDING_CHANGED')
            need({k:v for k,v in before['characters'].items() if k != str(uid)} ==
                 {k:v for k,v in after['characters'].items() if k != str(uid)},
                 'SKILL_OTHER_CHARACTER_MUTATION_REFUSED')
            old, new = before['characters'].get(str(uid)), after['characters'].get(str(uid))
            need(new is not None and (old is None and new['revision'] == 0
                 or old is not None and new['revision'] == old['revision'] + 1),
                 'SKILL_SELECTED_REVISION_TRANSITION')
        return True

    @contextmanager
    def authorize_staged(self, binding, before, after):
        self.provider.current(binding)
        need(self._stage is None, 'SKILL_PARTICIPANT_STAGE_ALREADY_ACTIVE')
        self.validate(after)
        self._stage = (binding, deepcopy(before), deepcopy(after))
        try:
            yield
        finally:
            self._stage = None


@dataclass(frozen=True)
class Outcome:
    receipt: dict = field(repr=False)
    semantic_result: dict | None = field(repr=False)
    replay: bool


class Service:
    """Owned-operation consumer; pure-entitlement learned save is supported.

    Cast/resource/book/trainer debit is unavailable. Request and txid originate
    from a source-backed server operation; the client cannot supply authority,
    time, revision or the staged document. Receipt lookup precedes planning.
    """
    def __init__(self, batch, core, store, schema, *, clock, catalog_digest,
                 entitlement=None, roster_grant=None):
        need(type(store) is batch.BatchStore and schema.provider is store.provider
             and callable(clock), 'SKILL_CANONICAL_STORE_AND_CLOCK_REQUIRED')
        self.batch, self.core, self.store, self.schema = batch, core, store, schema
        self.provider, self.clock, self.catalog_digest = store.provider, clock, catalog_digest
        self.entitlement, self.roster_grant = entitlement, roster_grant
        need(store.lock is batch.inventory_store._lock, 'SKILL_SAME_CANONICAL_LOCK_REQUIRED')

    @asynccontextmanager
    async def selected_operation(self, writer):
        # Integration replaces its original outer acquisition with this scope;
        # calling this from a legacy locked handler is deliberately unsupported.
        async with self.provider.selected_operation(writer) as binding:
            self.provider.current(binding)
            yield binding
            self.provider.current(binding)

    def _view(self, binding):
        self.provider.current(binding)
        view = self.batch.ParticipantView(self.store, binding, 'SKILL', self.schema.validate)
        need(view.lock is self.store.lock is self.batch.inventory_store._lock,
             'SKILL_PARTICIPANT_LOCK_CHANGED')
        self.schema.validate(view.data)
        return view

    def _now(self):
        value = self.core.Session._sync(self.clock)
        need(self.core.integer(value), 'SKILL_SERVER_CLOCK_REQUIRED')
        return value

    def initialize_locked(self, binding, *, txid, request):
        """Explicit trusted roster setup; never automatic on a missing read."""
        self.provider.current(binding)
        previous = self.store.lookup(binding, txid=txid, request_sha=self.batch.request_digest(request))
        if previous is not None:
            return Outcome(previous, None, True)
        need(callable(self.roster_grant) and self.core.Session._sync(self.roster_grant, binding) is True,
             'SKILL_EXPLICIT_ROSTER_GRANT_REQUIRED')
        try:
            participant = self.store.participant(binding, 'SKILL')
        except ValueError as error:
            if error.args != ('BATCH_PARTICIPANT_NOT_INSTALLED',):
                raise
            participant = dict(revision=-1, digest=self.batch.digest(None), document=None)
        before = participant['document']
        if before is None:
            after = self.schema.initial_document(binding, now_ms=self._now())
        else:
            self.schema.validate(before)
            need(str(binding.uid) not in before['characters'], 'SKILL_CHARACTER_EXISTS')
            after = deepcopy(before)
            after['characters'][str(binding.uid)] = self.schema.initial_document(
                binding, now_ms=self._now())['characters'][str(binding.uid)]
        return self._commit_document(binding, txid, request, participant, after,
                                     dict(kind='initialized', uid=binding.uid))

    def transition_locked(self, binding, *, txid, request, operation):
        self.provider.current(binding)
        previous = self.store.lookup(binding, txid=txid, request_sha=self.batch.request_digest(request))
        if previous is not None:
            return Outcome(previous, None, True)
        need(type(operation) is dict and set(operation) <= {'command', 'spell_id'}
             and 'command' in operation, 'SKILL_CLIENT_AUTHORITY_FIELDS_REFUSED')
        command = operation['command']
        need(command in ('learn', 'remove', 'tick', 'restore', 'close'),
             'SKILL_CANONICAL_HPMP_OR_ASSET_TRANSACTION_UNAVAILABLE')
        with self.store.lock:
            view = self._view(binding)
            row = view.data['characters'].get(str(binding.uid))
            need(row is not None, 'SKILL_EXPLICIT_ROSTER_GRANT_REQUIRED')
            shadow = object.__new__(self.core.Store)
            shadow.__dict__ = dict(rules=self.schema.rules, account=self.schema.account,
                rule_hash=self.schema.rule_hash, data=deepcopy(view.data), lock=view.lock, failed=False)
            def current():
                self.provider.current(binding)
                view._current()
            shadow._current = current
            shadow._save = lambda data: setattr(shadow, 'data', self.schema.validate(data))
            kwargs = dict(operation, now_ms=self._now(), expected_revision=row['revision'])
            if command == 'learn':
                # PURE entitlement check: no book/currency/provider mutation.
                need(callable(self.entitlement), 'SKILL_PURE_ENTITLEMENT_REQUIRED')
                kwargs['learn_grant'] = self.core.Session._sync(
                    self.entitlement, binding, operation.get('spell_id')) is True
            result = shadow.apply(binding.uid, **kwargs)
            participant = self.store.participant(binding, 'SKILL')
            need(participant['document'] == view.data, 'SKILL_PARTICIPANT_CHANGED_DURING_PREPARE')
            return self._commit_document(binding, txid, request, participant, shadow.data, result)

    def _commit_document(self, binding, txid, request, before, after, result):
        self.provider.current(binding)
        with self.store.lock:
            _, revision = self.store.restore(binding)
            change = self.batch.ParticipantChange('SKILL', before['revision'], before['digest'], deepcopy(after))
            with self.schema.authorize_staged(binding, before['document'], after):
                reservation = self.store.prepare(binding, txid=txid, request=request,
                    catalog_digest=self.catalog_digest, expected_revision=revision,
                    changes=(), participants=(change,))
            need(type(reservation) is self.batch.Reservation, 'SKILL_NEW_RESERVATION_REQUIRED')
            self.provider.current(binding)
            receipt = self.store.commit(binding, reservation)
            participant = self.store.participant(binding, 'SKILL')
            need(receipt['phase'] == 'COMMITTED' and participant['document'] == after
                 and participant['digest'] == self.batch.digest(after), 'SKILL_CANONICAL_COMMIT_READBACK')
            return Outcome(receipt, deepcopy(result), False)

    def read_locked(self, binding):
        """Current same-aggregate source; no independent save or auto-seeding."""
        with self.store.lock:
            view = self._view(binding)
            return deepcopy(view.data)

    def decode_cast_locked(self, binding, *, payload, codec, legacy_bindings):
        self.provider.current(binding)
        received = codec.parse_payload(payload).require_normal_source_shape()
        legacy = legacy_bindings.bound.get(id(binding.writer))
        need(legacy is not None and legacy[0].uid == binding.uid
             and legacy[0].lock is binding.operation_lock, 'SKILL_CAST_SAME_OWNED_OPERATION_REQUIRED')
        legacy_bindings.current(legacy[0])
        self.provider.current(binding)
        # Decode only: original target UID role and resource/effect remain open.
        return received

    def delivery_locked(self, binding, *, txid, request, state):
        self.provider.current(binding)
        self.store.delivery(binding, txid=txid, request=request, state=state)
