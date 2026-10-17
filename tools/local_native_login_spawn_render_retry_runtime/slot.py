"""Fresh CP73 transaction history; retain the exact CP49 owned producer."""
import contextlib
import hashlib
import json
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / 'work/local_native_login_state5_ack_runtime/slot'
PIN_FILE = HERE / 'cp49-baseline-pins.json'
PIN_SHA = '3e9c3b0f8a82b2047cf0d5c974f34da981bb91ec51187abd25a297c7320242bf'
OLD_FAMILY = 'LOCAL_NATIVE_LOGIN_STATE5_ACK_CP49'
FILE_ID = 'ce7884c9:00c600000006b6e8'
DLL_ID = 'ce7884c9:0010000000188270'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def baseline_pins():
    raw = PIN_FILE.read_bytes()
    need(sha(raw) == PIN_SHA, 'EXACT_CP49_BASELINE_PIN_FILE')
    return json.loads(raw)


def basis(read, product, module=None):
    pins = baseline_pins()
    rows = {}
    for name, digest in pins.items():
        raw = read(ROOT / name)
        need(sha(raw) == digest, 'FROZEN_CP49_BASELINE_CHANGED:' + name)
        if name.startswith(OLD.relative_to(ROOT).as_posix() + '/'):
            rows[Path(name).name] = json.loads(raw)
    record = rows['owned-producer.json']
    receipt = rows['receipt.json']
    journal = rows['transactions.json']
    review = json.loads(read(ROOT / 'tools/local_native_login_state5_ack_runtime/root-slot-review.json'))
    spec = product['producer_DLL']
    need(record['family'] == OLD_FAMILY and record['candidate_sha256'] == product['candidate']['sha256']
         and record['slot_file_id'] == FILE_ID and record['sibling_file_id'] == DLL_ID
         and record['sha256'] == spec['sha256'] and record['size'] == spec['size']
         and record['source_path'] == spec['path']
         and Path(record['sibling_path']) == ROOT / 'work/standalone_boot/current-unmodified-clone' / spec['basename']
         and record['CREATE_NEW'] is True and record['delete_rename_rewrite'] is False,
         'EXACT_CP49_OWNED_PRODUCER_PROVENANCE')
    need(receipt['status'] == 'VERIFIED' and receipt['phase'] == 'RESTORED'
         and receipt['action'] == 'RestoreControl' and receipt['restoration_required'] is False
         and receipt['outcome_unconfirmed'] is False and receipt['slot_file_id'] == FILE_ID
         and receipt['family'] == OLD_FAMILY and receipt['current_sha256'] == review['control_sha256']
         and receipt['slot_review_sha256'] == record['slot_review_sha256']
         and receipt['provenance_sha256'] == record['slot_provenance_sha256']
         and receipt['transaction_sha256'] == pins[(OLD / 'transactions.json').relative_to(ROOT).as_posix()]
         and receipt['slot_review_sha256'] == pins['tools/local_native_login_state5_ack_runtime/root-slot-review.json']
         and receipt['provenance_sha256'] == pins[(OLD / 'provenance.json').relative_to(ROOT).as_posix()],
         'EXACT_CP49_VERIFIED_RESTORED_RECEIPT')
    binding = {key: value for key, value in journal.items() if key != 'events'}
    need(len(journal['events']) == 4 and journal['events'][-1]['phase'] == 'RESTORED'
         and all(rows[f'event-{index:03d}.json'] == {'binding': binding, 'event': event}
                 for index, event in enumerate(journal['events'])), 'EXACT_CP49_FOUR_IMMUTABLE_EVENTS')
    if module is not None:
        need(module.validate_journal(journal, binding) == 'RESTORED', 'ORIGINAL_CP49_JOURNAL_VALIDATION')
    return record


def api(source, active, base_provider):
    def module():
        result = base_provider(source).module()
        policy = result.p
        product, _ = source.product_binding()
        record = basis(lambda path: path.read_bytes(), product, result)
        original_review = policy.fixed_review

        def fixed_review():
            row = original_review()
            row.update(schema='lc-cp73-fresh-slot-exact-cp49-producer-reuse-v1',
                       sibling_CREATE_NEW=False, producer_CREATE_NEW=False,
                       fresh_slot_history=True, owned_producer_reused=True,
                       cp49_producer_record=record, cp49_baseline_pins_sha256=PIN_SHA,
                       cp49_owned_record_recreation=False, sibling_create_delete_rename_rewrite=False,
                       kernel_trace='NOT_REQUESTED')
            return row

        policy.fixed_review = fixed_review
        Base = result.Backend

        class Backend(Base):
            def pin_inputs(self):
                self._baseline_ready = False
                super().pin_inputs()
                for name, digest in source.pins().items():
                    path = ROOT / name
                    for directory in reversed(path.parents):
                        if directory == ROOT or ROOT in directory.parents:
                            self.a.add(directory)
                    need(self.a.add(path).digest() == digest, 'CP73_SLOT_DEPENDENCY_PIN')
                self.a.add(PIN_FILE)
                for name, digest in baseline_pins().items():
                    need(self.a.add(ROOT / name).digest() == digest, 'CP49_BASELINE_RETAINED_PIN')
                target = Path(record['sibling_path'])
                held = self.a.add(target)
                held.verify()
                need(held.identity[0] == DLL_ID and held.identity[1] == record['size']
                     and held.digest() == record['sha256'],
                     'EXACT_CP49_SIBLING_FILE_ID_SIZE_SHA')
                self.verify_baseline_complete()
                self._baseline_ready = True
                self.verify_sources()

            def verify_baseline_complete(self):
                required = {PIN_FILE, Path(record['sibling_path'])}
                required.update(ROOT / name for name in baseline_pins())
                required.update(ROOT / name for name in source.pins())
                need(required.issubset(self.a.pins), 'CP73_COMPLETE_BASELINE_PINS_REQUIRED')
                need(self.a.pins[PIN_FILE].digest() == PIN_SHA, 'CP49_BASELINE_PIN_FILE_CHANGED')
                basis(lambda path: self.a.pins[path].read(1048576), product, result)
                held = self.a.pins[Path(record['sibling_path'])]
                held.verify()
                need(held.identity[0] == DLL_ID and held.identity[1] == record['size']
                     and held.digest() == record['sha256'],
                     'EXACT_CP49_COMPLETE_SIBLING_FILE_ID_SIZE_SHA')

            def verify_sources(self):
                super().verify_sources()
                for name, digest in source.pins().items():
                    path = ROOT / name
                    if path in self.a.pins:
                        need(self.a.pins[path].digest() == digest, 'CP73_SLOT_DEPENDENCY_CHANGED')
                if PIN_FILE in self.a.pins:
                    need(self.a.pins[PIN_FILE].digest() == PIN_SHA, 'CP49_BASELINE_PIN_FILE_CHANGED')
                    for name, digest in baseline_pins().items():
                        path = ROOT / name
                        if path in self.a.pins:
                            need(self.a.pins[path].digest() == digest, 'CP49_BASELINE_CHANGED')
                target = Path(record['sibling_path'])
                if target in self.a.pins:
                    held = self.a.pins[target]
                    held.verify()
                    need(held.identity[0] == DLL_ID and held.identity[1] == record['size']
                         and held.digest() == record['sha256'],
                         'CP49_SIBLING_CHANGED')
                if getattr(self, '_baseline_ready', False):
                    self.verify_baseline_complete()

            def overwrite(self, data):
                if sha(data) != policy.PROGRAM:
                    return super().overwrite(data)
                self.verify_sources()
                self.verify_baseline_complete()
                pending = json.loads(self.files['journal'].read(1048576))
                binding = {key: value for key, value in pending.items() if key != 'events'}
                need(policy.WORK == source.WORK / 'slot' and policy.FAMILY == source.FAMILY
                     and pending['slot_file_id'] == FILE_ID and len(pending['events']) == 1
                     and result.validate_journal(pending, binding) == 'PENDING',
                     'FRESH_CP73_SINGLE_PENDING_INTENT_REQUIRED')
                need(self.image() == (FILE_ID, policy.CONTROL), 'CP73_EXACT_CONTROL_PREWRITE')
                self.a.verify_all()
                # Preserve the native same-FileID resize/write/flush primitive.
                # No sibling file or CP49 ownership/transaction record is written.
                self.rw.overwrite(data)

        result.Backend = Backend
        return result

    @contextlib.contextmanager
    def context():
        result = module()
        with result.verified_installed_context() as ctx:
            with ctx.lock:
                product, _ = source.product_binding()
                record = basis(lambda path: ctx.b.a.pins[path].read(1048576), product, result)
                for name, digest in baseline_pins().items():
                    ctx.pinned_hashes[ROOT / name] = digest
                ctx.pinned_hashes[PIN_FILE] = PIN_SHA
                ctx.pinned_hashes[Path(record['sibling_path'])] = record['sha256']
                observer_spec = product['observer_DLL']
                observer = result.p.IMAGE.parent / observer_spec['basename']
                previous = ROOT / 'work/local_native_login_creation_entry_marker_runtime/slot/owned-dll-01.json'
                previous_pin = ctx.b.a.add(previous)
                previous_record = json.loads(previous_pin.read(32768))
                held = ctx.b.a.add(observer)
                held.verify()
                need(held.identity[0] == previous_record['sibling_file_id']
                     and held.identity[1] == observer_spec['size']
                     and held.digest() == observer_spec['sha256'] == previous_record['sha256']
                     and previous_record['CREATE_NEW'] is True, 'EXACT_RETAINED_OBSERVER_PROVENANCE')
                ctx.pinned_hashes[observer] = observer_spec['sha256']
                ctx.pinned_hashes[previous] = previous_pin.digest()
                session = active()
                if session is not None:
                    ctx.b.a.add(session.path)
                    ctx.b.a.add(session.forward_path)
                    session.ctx = ctx
                ctx.verify_sources()
            try:
                yield ctx
            finally:
                if session is not None:
                    session.ctx = None

    def expected_review():
        policy = module().p
        return dict(policy.fixed_review(), gate_review_sha256=policy.GATE_REVIEW_SHA)

    return types.SimpleNamespace(module=module, policy=lambda: module().p,
                                 expected_review=expected_review,
                                 verified_installed_context=context, main=lambda: module().main())
