"""Offline registration/dispatch contracts; no legacy codecs, broker or sockets.

Synthetic feature modules exercise extension contracts independently of the
unavailable client-source fixtures. Actual registration declarations are checked
without importing their callback bodies; two small entrypoint bodies are also
extracted explicitly. These checks are not a full-server startup or gameplay
claim; existing integration tests retain their original expectations.
"""
import ast
from dataclasses import dataclass
from pathlib import Path
from types import MethodType, SimpleNamespace
import unittest

from tools.local_original_session import world_registry as registry


def module(name, *methods, **declarations):
    return SimpleNamespace(__name__=name, METHODS=methods, **declarations)


def context(*modules):
    compiled = registry.build_registry(modules)
    ctx = SimpleNamespace(_world_registry=compiled, calls=[])
    for name, function in compiled.methods.items():
        setattr(ctx, name, MethodType(function, ctx))
    return ctx


def actual_module_declarations():
    """Read real registration tables, never imports, defaults or callback bodies."""
    root = Path(__file__).parent
    attributes = {'METHODS', 'REALM_METHODS', 'FRAMES', 'HOOKS', 'REALM_HOOKS',
        'NONCRITICAL_HOOKS', 'HOOK_PRIORITY', 'FRAME_PRIORITY',
        'SAVE_BOUNDARIES', 'OUTGOING_OPCODES', 'WRAPS'}
    handlers = ast.parse((root / 'world_handlers.py').read_text(encoding='utf-8'))

    def constants(tree):
        values = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in attributes:
                    values[target.id] = value
                elif isinstance(target, ast.Tuple) and isinstance(value, (tuple, list)):
                    values.update((target.id, item) for target, item in zip(target.elts, value)
                                  if isinstance(target, ast.Name))
        return values

    shared = constants(handlers)
    shared['__builtins__'] = {}
    handler_table = next(node for node in handlers.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        and node.target.id == 'HANDLERS')
    shared['HANDLERS'] = {eval(compile(ast.Expression(key), 'HANDLERS', 'eval'), shared): None
                          for key in handler_table.value.args[0].keys}

    def declared(name):
        tree = ast.parse((root / (name + '.py')).read_text(encoding='utf-8'))
        values = {**shared, **constants(tree), '__name__': name}
        # Items owns its consumable helper declarations as one feature.
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == 'tools.local_original_session':
                for imported in node.names:
                    if imported.name == 'world_item_effects':
                        values[imported.asname or imported.name] = declared(imported.name)
                    elif (not imported.name.startswith('world_feature_')
                          and (root / (imported.name + '.py')).is_file()):
                        # Sibling protocol modules contribute literal constants
                        # only (e.g. opcodes in FRAMES); nothing is imported/run.
                        values[imported.asname or imported.name] = SimpleNamespace(**constants(
                            ast.parse((root / (imported.name + '.py')).read_text(encoding='utf-8-sig'))))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                def reference(*args, **kwargs):
                    raise AssertionError('Declaration-only callback must never execute')
                reference.__name__ = node.name
                values[node.name] = reference
        selected = []
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any((isinstance(target, ast.Name) and target.id in attributes)
                       or (isinstance(target, ast.Subscript)
                           and isinstance(target.value, ast.Name)
                           and target.value.id in attributes) for target in targets):
                    selected.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                function = node.value.func
                if (isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name)
                        and function.value.id in attributes):
                    selected.append(node)
        exec(compile(ast.Module(body=selected, type_ignores=[]), name, 'exec'), values)
        return SimpleNamespace(__name__=name,
            **{attribute: values[attribute] for attribute in attributes if attribute in values})

    return (tuple(declared(name) for name in shared['CORE_MODULES']),
            tuple(declared(name) for name in shared['FEATURE_MODULES']))


def extracted_function(module_name, name):
    """Compile one exact entrypoint body, without importing the containing module."""
    source = Path(__file__).with_name(module_name + '.py')
    tree = ast.parse(source.read_text(encoding='utf-8'))
    node = next(node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace[name]


class RegistryContractTests(unittest.TestCase):
    def test_actual_declarations_resolve_all_optional_subsets_without_callback_imports(self):
        """Declarations only: not importability, initialization or startup proof."""
        core, optional = actual_module_declarations()
        # WORLD_FEATURE_GUIDE: none, all, each one excluded and each one alone.
        # (All 2**N subsets stopped being tractable at 22 optional features.)
        everything = frozenset(range(len(optional)))
        masks = [frozenset(), everything]
        masks += [everything - {index} for index in range(len(optional))]
        masks += [frozenset({index}) for index in range(len(optional))]
        for mask in masks:
            enabled = tuple(feature for index, feature in enumerate(optional) if index in mask)
            with self.subTest(enabled=tuple(feature.__name__ for feature in enabled)):
                compiled = registry.build_registry(core + enabled)
                self.assertIn('_world_attack', compiled.frames[0x4e30])
                self.assertIn('_world_dispatch', compiled.frames[0x4e2b])
                self.assertIn('_world_pickup', compiled.frames[0x4e3e])

    def test_method_collision_never_silently_overwrites(self):
        def shared(ctx):
            return 'first'
        first = module('first_feature', shared)
        def shared(ctx):
            return 'second'
        second = module('second_feature', shared)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_METHODS'):
            registry.build_registry((first, second))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_METHODS'):
            registry.build_registry((first, first))

    def test_realm_method_collision_is_also_rejected(self):
        def realm_view(realm):
            return realm
        first = module('first_feature', REALM_METHODS=(realm_view,))
        second = module('second_feature', REALM_METHODS=(realm_view,))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_REALM_METHODS'):
            registry.build_registry((first, second))

    def test_only_explicit_wrapping_composes_a_named_method(self):
        def calculate(ctx, value):
            ctx.calls.append('base')
            return value + 1
        def twice(ctx, base, value):
            ctx.calls.append('twice')
            return 2 * base(value)
        def plus_three(ctx, base, value):
            ctx.calls.append('plus_three')
            return base(value) + 3
        ctx = context(module('core', calculate, SAVE_BOUNDARIES={'calculate': True}),
            module('first_extension', WRAPS={'calculate': twice}),
            module('second_extension', WRAPS={'calculate': plus_three}))
        self.assertEqual(ctx.calculate(4), 13)
        self.assertEqual(ctx.calls, ['plus_three', 'twice', 'base'])
        self.assertEqual(ctx.calculate.__name__, 'calculate')
        self.assertIs(ctx._world_registry.save_boundaries['calculate'], True)

    def test_missing_registration_targets_fail_at_build_time(self):
        def wrap(ctx, base):
            return base()
        for declaration in ({'HOOKS': {'enter': ('missing',)}},
                            {'FRAMES': {0x1234: ('missing',)}},
                            {'SAVE_BOUNDARIES': {'missing': True}},
                            {'WRAPS': {'missing': wrap}}):
            with self.subTest(declaration=declaration):
                with self.assertRaisesRegex(ValueError, 'UNKNOWN_'):
                    registry.build_registry((module('invalid', **declaration),))

    def test_each_optional_omission_removes_its_initialization_and_frames(self):
        def core_start(ctx):
            ctx.calls.append('core')
        def feature_a_start(ctx):
            ctx.calls.append('a')
        def feature_b_start(ctx):
            ctx.calls.append('b')
        core = module('core', core_start, HOOKS={'initialize': ('core_start',)})
        a = module('optional_a', feature_a_start,
            HOOKS={'initialize': ('feature_a_start',)}, FRAMES={1: ('feature_a_start',)})
        b = module('optional_b', feature_b_start,
            HOOKS={'initialize': ('feature_b_start',)}, FRAMES={2: ('feature_b_start',)})
        for optional, expected in (((a, b), ['core', 'a', 'b']),
                                   ((a,), ['core', 'a']), ((b,), ['core', 'b']),
                                   ((), ['core'])):
            with self.subTest(optional=optional):
                ctx = context(core, *optional)
                registry.run_sync_hooks('initialize', ctx)
                self.assertEqual(ctx.calls, expected)
                self.assertEqual(set(ctx._world_registry.frames),
                                 {opcode for item in optional for opcode in item.FRAMES})

    def test_frame_priority_preserves_explicit_protocol_precedence(self):
        def session(ctx):
            return False
        def pet(ctx):
            return False
        def magic(ctx):
            return False
        ctx = context(module('session_core', session,
                FRAMES={0x0960: ('session',)}, FRAME_PRIORITY=10),
            module('magic', magic, FRAMES={0x0960: ('magic',)}),
            module('pet', pet, FRAMES={0x0960: ('pet',)}, FRAME_PRIORITY=0))
        self.assertEqual(ctx._world_registry.frames[0x0960], ('pet', 'session', 'magic'))

    def test_save_boundaries_belong_only_to_enabled_methods(self):
        def save_item(ctx):
            return None
        optional = module('items', save_item, SAVE_BOUNDARIES={'save_item': True})
        self.assertIn('save_item', registry.build_registry((optional,)).save_boundaries)
        self.assertEqual(dict(registry.build_registry(()).save_boundaries), {})
        with self.assertRaises(TypeError):
            registry.build_registry((optional,)).save_boundaries['save_item'] = False


class SynchronousHookContractTests(unittest.TestCase):
    def test_empty_hooks_retain_core_defaults(self):
        ctx, value = context(), object()
        self.assertFalse(registry.has_hooks('missing', ctx))
        self.assertIsNone(registry.run_sync_hooks('missing', ctx))
        self.assertFalse(registry.chain_sync_hooks('missing', ctx))
        self.assertEqual(registry.collect_sync_hooks('missing', ctx), ())
        self.assertIs(registry.fold_sync_hooks('missing', ctx, value), value)
        self.assertIsNone(registry.prepare_attack(ctx, 1, object(), 0.))

    def test_chain_stops_only_after_first_consumer(self):
        def decline(ctx, payload):
            ctx.calls.append(('decline', payload))
            return False
        def consume(ctx, payload):
            ctx.calls.append(('consume', payload))
            return True
        def unreachable(ctx, payload):
            raise AssertionError('request replayed after consumption')
        ctx = context(module('routing', decline, consume, unreachable,
            HOOKS={'item_use': ('decline', 'consume', 'unreachable')}))
        self.assertTrue(registry.chain_sync_hooks('item_use', ctx, b'owned request'))
        self.assertEqual(ctx.calls, [('decline', b'owned request'), ('consume', b'owned request')])

    def test_events_run_all_observers_and_folds_compose_values(self):
        def first(ctx, value):
            ctx.calls.append('first')
            return value + 2
        def second(ctx, value):
            ctx.calls.append('second')
            return value * 3
        ctx = context(module('observers', first, second,
            HOOKS={'event': ('first', 'second'), 'stats': ('first', 'second')}))
        self.assertIsNone(registry.run_sync_hooks('event', ctx, 4))
        self.assertEqual(ctx.calls, ['first', 'second'])
        self.assertEqual(registry.collect_sync_hooks('event', ctx, 4), (6, 12))
        self.assertEqual(registry.fold_sync_hooks('stats', ctx, 4), 18)

    def test_noncritical_failure_is_bounded_and_does_not_skip_later_observer(self):
        def bad(ctx):
            raise ValueError('advisory error')
        def later(ctx):
            ctx.calls.append('later')
        ctx = context(module('optional_observer', bad,
                HOOKS={'report': ('bad',)}, NONCRITICAL_HOOKS=('report',)),
            module('next_observer', later, HOOKS={'report': ('later',)}))
        for _ in range(24):
            registry.run_sync_hooks('report', ctx)
        self.assertEqual(ctx.calls, ['later'] * 24)
        self.assertGreater(len(ctx._world_hook_errors), 0)
        self.assertLess(len(ctx._world_hook_errors), 24)
        self.assertEqual(ctx._world_hook_errors[-1]['error'], 'ValueError')

    def test_critical_transaction_failure_still_propagates(self):
        def save(ctx):
            raise OSError('durable write failed')
        def publish(ctx):
            ctx.calls.append('published')
        ctx = context(module('transaction', save, publish,
            HOOKS={'save': ('save', 'publish')}))
        with self.assertRaisesRegex(OSError, 'durable write failed'):
            registry.run_sync_hooks('save', ctx)
        self.assertEqual(ctx.calls, [])

    def test_noncritical_does_not_swallow_process_cancellation(self):
        def interrupt(ctx):
            raise KeyboardInterrupt()
        ctx = context(module('optional', interrupt,
            HOOKS={'report': ('interrupt',)}, NONCRITICAL_HOOKS=('report',)))
        with self.assertRaises(KeyboardInterrupt):
            registry.run_sync_hooks('report', ctx)

    def test_attack_reduction_retains_ammunition_and_combines_allowance(self):
        @dataclass(frozen=True)
        class Preparation:
            allowed: bool
            arrow: object = None
            cost: object = None
        arrow, cost = object(), object()
        def ammunition(ctx, *args):
            ctx.calls.append('cost')
            return Preparation(True, arrow, cost)
        def policy(ctx, *args):
            return Preparation(True)
        ctx = context(module('ammo', ammunition,
                HOOKS={'prepare_attack': ('ammunition',)},
                HOOK_PRIORITY={'prepare_attack': 100}),
            module('policy', policy, HOOKS={'prepare_attack': ('policy',)}))
        prepared = registry.prepare_attack(ctx, 1, object(), 0.)
        self.assertIs(prepared.arrow, arrow)
        self.assertIs(prepared.cost, cost)
        self.assertEqual(ctx.calls, ['cost'])
        ctx.calls.clear()
        ctx.policy = lambda *_: Preparation(False)
        self.assertIsNone(registry.prepare_attack(ctx, 1, object(), 0.))
        self.assertEqual(ctx.calls, [])


class AsynchronousHookContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracted_potion_entrypoints_require_explicit_items_wrapper(self):
        """Exact selected bodies; codecs, ItemEquipmentEffect and startup are not run."""
        core = extracted_function('world_core_kit', '_world_consume_kit_potion')
        wrapper = extracted_function('world_feature_items', '_world_items_kit_potion')
        blocked, consumed = [], []
        result = object()
        writer, request, receipt, definition = object(), object(), object(), object()

        def refuse(receipt, reason):
            blocked.append((receipt, reason))
            return result

        async def consume(*args):
            consumed.append(args)
            return result

        consumer = SimpleNamespace(_blocked=refuse, _consume_potion=consume)
        without = context(module('core', core))
        self.assertIs(await without._world_consume_kit_potion(
            consumer, writer, request, receipt, definition), result)
        self.assertEqual(blocked, [(receipt, 'ITEM_USE_KIT_NO_EFFECT')])
        self.assertFalse(consumed)
        enabled = context(module('core', core),
            module('items', WRAPS={'_world_consume_kit_potion': wrapper}))
        self.assertIs(await enabled._world_consume_kit_potion(
            consumer, writer, request, receipt, definition), result)
        self.assertEqual(consumed, [(writer, request, receipt, definition)])
        self.assertEqual(len(blocked), 1)

    async def test_async_chain_stops_after_consumption(self):
        async def decline(ctx):
            ctx.calls.append('decline')
            return False
        async def consume(ctx):
            ctx.calls.append('consume')
            return True
        async def unreachable(ctx):
            raise AssertionError('consumed frame reached another handler')
        ctx = context(module('route', decline, consume, unreachable,
            HOOKS={'request': ('decline', 'consume', 'unreachable')}))
        self.assertTrue(await registry.chain_hooks('request', ctx))
        self.assertEqual(ctx.calls, ['decline', 'consume'])

    async def test_mixed_async_observers_continue_after_advisory_error(self):
        async def bad(ctx, value):
            raise ValueError('advisory')
        def synchronous(ctx, value):
            ctx.calls.append(('sync', value))
        async def asynchronous(ctx, value):
            ctx.calls.append(('async', value))
        ctx = context(module('optional', bad, HOOKS={'after_leave': ('bad',)},
                NONCRITICAL_HOOKS=('after_leave',)),
            module('next', synchronous, asynchronous,
                HOOKS={'after_leave': ('synchronous', 'asynchronous')}))
        await registry.run_hooks('after_leave', ctx, 7)
        self.assertEqual(ctx.calls, [('sync', 7), ('async', 7)])
        self.assertEqual(ctx._world_hook_errors[-1]['error'], 'ValueError')

    async def test_async_folds_and_empty_defaults(self):
        async def increment(ctx, value, amount):
            return value + amount
        def double(ctx, value, amount):
            return value * 2
        ctx = context(module('stats', increment, double,
            HOOKS={'calculate': ('increment', 'double')}))
        self.assertEqual(await registry.fold_hooks('calculate', ctx, 3, 4), 14)
        self.assertEqual(await registry.collect_hooks('calculate', ctx, 3, 4), (7, 6))
        self.assertFalse(await registry.chain_hooks('missing', ctx))
        self.assertEqual(await registry.collect_hooks('missing', ctx), ())
        self.assertIsNone(await registry.run_hooks('missing', ctx))


if __name__ == '__main__':
    unittest.main()
