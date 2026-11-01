"""Auxiliary request unit tests; no socket, game, save or gameplay PASS."""
from types import SimpleNamespace as NS
import unittest

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import world_feature_aux_requests as feature
from tools.local_original_session import world_bridge, world_handlers, world_registry


def exclude(first=0, second=0, names=()):
    return (pb.encode_uint32(1, first) + pb.encode_uint32(2, second)
            + b''.join(pb.encode_bytes(3, value) for value in names))


class Context:
    def __init__(self):
        self.writer, self.game, self.row, self.lock = object(), object(), {}, object()
        self.position = NS(uid=7)
        self.bound, self.ready, self.current = True, True, True
        self.selected = self.game
        self.realm = NS(service=lambda writer: NS(snapshot=lambda: self.position))
        self.in_runtime = False
        self.world = NS(runtime=NS(dispatch_now=self.dispatch_now))
        self.sent = []
        self.send_error = None
        feature._aux_requests_initialize(self)

    async def dispatch_now(self, callback):
        self.in_runtime = True
        try:
            return callback()
        finally:
            self.in_runtime = False

    def _world_bound(self, writer):
        return self.bound

    def _world_ready(self, writer, game):
        return self if self.ready else None

    def selected_session(self, writer):
        assert self.in_runtime
        return self.selected

    def owner_current(self, writer, row, position):
        assert self.in_runtime
        return self.current

    async def _world_send(self, writer, row, frames, lock):
        assert writer is self.writer and row is self.row and lock is self.lock
        if self.send_error:
            raise self.send_error
        self.sent.extend(frames)

    async def request(self, opcode, payload):
        return await feature._aux_requests_request(self, self.writer, self.row, self.game,
            NS(opcode=opcode, payload=payload), self.lock)


class AuxiliaryRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrap_exact_empty_list_through_existing_send(self):
        ctx = Context()
        self.assertTrue(await ctx.request(feature.EXCLUDE, exclude()))
        self.assertEqual(ctx.sent, [bytes.fromhex('0800ee0310000000')])
        with pb.parse_message(ctx.sent[0][4:-2], schema={1: 2, 2: 0}) as parsed:
            self.assertFalse(parsed.occurrences(1))
            self.assertEqual(parsed.occurrences(2)[0].value, 0)
        self.assertEqual(ctx._aux_request_events[-1]['response'], 'drained')

    async def test_named_selectors_have_no_mutation_or_success_response(self):
        ctx = Context()
        for first in (1, 2):
            self.assertTrue(await ctx.request(feature.EXCLUDE, exclude(first, names=(b'Alice',))))
        self.assertFalse(ctx.sent)
        self.assertTrue(all(event['status'] == 'unsupported_exclusion_operation'
                            for event in ctx._aux_request_events))
        self.assertNotIn('Alice', repr(ctx._aux_request_events))
        self.assertEqual(ctx._aux_request_events[-1]['string_bytes'], 5)

    async def test_other_category_and_selector_zero_with_names_are_not_bootstrap(self):
        ctx = Context()
        for payload in (exclude(second=1), exclude(second=2), exclude(names=(b'name',))):
            await ctx.request(feature.EXCLUDE, payload)
        self.assertFalse(ctx.sent)

    async def test_emblem_is_logged_without_invented_ack(self):
        ctx = Context()
        payload = pb.encode_uint32(1, 42) + pb.encode_varint(2 << 3) + pb.encode_varint(2**63)
        self.assertTrue(await ctx.request(feature.EMBLEM_INFO, payload))
        event = ctx._aux_request_events[-1]
        self.assertEqual(event['scalars'], {'1': 42, '2': 2**63})
        self.assertEqual(event['status'], 'emblem_response_contract_unknown')
        self.assertEqual(event['response'], 'none')
        self.assertFalse(ctx.sent)

    async def test_emblem_requiredness_unknown_does_not_invent_required_fields(self):
        ctx = Context()
        self.assertTrue(await ctx.request(feature.EMBLEM_INFO, b''))
        self.assertEqual(ctx._aux_request_events[-1]['status'], 'emblem_response_contract_unknown')
        self.assertFalse(ctx.sent)

    async def test_malformed_inputs_logged_without_response(self):
        ctx = Context()
        invalid = (b'', pb.encode_uint32(1, 0), exclude(3),
                   exclude() + pb.encode_uint32(1, 0), exclude() + pb.encode_uint32(4, 1),
                   pb.encode_bytes(1, b'x') + pb.encode_uint32(2, 0),
                   exclude(names=(b'\xff',)), b'\x08\x80')
        for payload in invalid:
            self.assertTrue(await ctx.request(feature.EXCLUDE, payload))
            self.assertEqual(ctx._aux_request_events[-1]['status'], 'invalid')
        self.assertFalse(ctx.sent)

    async def test_malformed_emblem_logged_without_response(self):
        ctx = Context()
        for payload in (pb.encode_bytes(1, b'x'), pb.encode_uint32(2, 0) * 2, b'\x10\x80'):
            self.assertTrue(await ctx.request(feature.EMBLEM_INFO, payload))
            self.assertEqual(ctx._aux_request_events[-1]['status'], 'invalid')
        self.assertFalse(ctx.sent)

    async def test_unbound_or_unready_does_not_claim_request(self):
        ctx = Context()
        ctx.bound = False
        self.assertFalse(await ctx.request(feature.EXCLUDE, exclude()))
        ctx.bound, ctx.ready = True, False
        self.assertFalse(await ctx.request(feature.EXCLUDE, exclude()))
        self.assertFalse(ctx._aux_request_events)

    async def test_current_owner_and_selected_session_required(self):
        ctx = Context()
        for selected, current in ((object(), True), (ctx.game, False)):
            ctx.selected, ctx.current = selected, current
            with self.assertRaisesRegex(ValueError, 'AUX_CURRENT_SELECTED_PC_REQUIRED'):
                await ctx.request(feature.EXCLUDE, exclude())
        self.assertFalse(ctx.sent)
        self.assertFalse(ctx._aux_request_events)

    async def test_send_failure_propagates_without_claiming_drain(self):
        ctx = Context()
        ctx.send_error = RuntimeError('write failed')
        with self.assertRaisesRegex(RuntimeError, 'write failed'):
            await ctx.request(feature.EXCLUDE, exclude())
        self.assertEqual(ctx._aux_request_events[-1]['response'], 'attempted')

    async def test_events_bounded_and_report_describes_local_policy(self):
        ctx = Context()
        for _ in range(20):
            await ctx.request(feature.EMBLEM_INFO, pb.encode_uint32(1, 42))
        result = {}
        feature._aux_requests_report(ctx, result)
        report = result['auxiliary_requests']
        self.assertEqual(len(report['events']), 16)
        self.assertEqual(report['exclusion_policy'], 'LOCAL_EMPTY_BOOTSTRAP_ONLY')
        self.assertEqual(report['emblem_response'], 'UNKNOWN_NOT_SENT')

    async def test_unrelated_opcode_remains_unhandled(self):
        ctx = Context()
        self.assertFalse(await ctx.request(0x1234, exclude()))
        self.assertFalse(ctx._aux_request_events)


class RegistrationTests(unittest.TestCase):
    def test_optional_registry_binds_only_two_requests_and_one_response(self):
        self.assertIn('world_feature_aux_requests', world_handlers.FEATURE_MODULES)
        registry = world_registry.build_registry((feature,))
        self.assertEqual(set(registry.frames), {feature.EXCLUDE, feature.EMBLEM_INFO})
        self.assertEqual(registry.outgoing_opcodes, (feature.EXCLUDE_LIST,))
        self.assertFalse(registry.save_boundaries)
        self.assertFalse(world_registry.build_registry(()).frames)

    def test_policy_extensions_admit_registered_request_and_exact_response(self):
        policy = NS(world=True, restart_enabled=False, item_transfer=False)
        incoming = world_bridge.received_extensions(policy, ())
        self.assertIn(feature.EXCLUDE, incoming)
        self.assertIn(feature.EMBLEM_INFO, incoming)
        self.assertEqual(world_bridge.outgoing_extensions(policy, (), feature.EXCLUDE_LIST,
                         len(feature.empty_exclusion_frame()), 'menu'), (feature.EXCLUDE_LIST,))
        self.assertEqual(world_bridge.outgoing_extensions(policy, (), 0x072F, 6, 'menu'), ())
        self.assertEqual(world_bridge.received_extensions(NS(world=False), ()), ())


if __name__ == '__main__':
    unittest.main()
