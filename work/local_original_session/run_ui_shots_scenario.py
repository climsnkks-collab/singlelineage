"""Prepared UI capture scenario. Import/tests never launch a game or a listener.

An explicit CLI invocation uses the existing launcher, private desktop, Job and
SourceQuit/FIRST close. Calls and PNG capture are observations, not a UI PASS.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.local_original_session import launcher
from tools.local_original_session.ui_open_commands import UIOpenCommands, KitScreenshotObserver, current_kit

PROFILE = 'sibling-background-source-quit-spawn'
STEPS = (('open', 'open_magic_window'), ('capture', 'magic'),
         ('scroll', 'talking_scroll'), ('capture', 'talking_scroll'),
         ('open', 'open_stats_window'), ('capture', 'stats'))


class UISequence:
    """Serial actions, retaining the first original failure and preceding results."""
    def __init__(self, operations):
        self.operations = operations
        self.index = 0
        self.waiting = False
        self.results = []
        self.error = None

    @property
    def done(self):
        return self.error is not None or self.index == len(STEPS)

    async def tick(self):
        if self.done:
            return
        kind, name = STEPS[self.index]
        try:
            if not self.waiting:
                if not await self.operations.start(kind, name):
                    return
                self.waiting = True
            row = await self.operations.collect(kind, name)
            if row is None:
                return
            self.results.append(dict(step=name, kind=kind, result=row))
            expected = 'OBSERVED' if kind == 'capture' else 'RETURNED'
            if row.get('status') != expected:
                self.error = dict(step=name, kind=kind, result=row)
                return
            self.index += 1
            self.waiting = False
        except Exception as error:
            self.error = dict(step=name, kind=kind, error_type=type(error).__name__,
                              reason=str(error)[:256])


class Operations:
    def __init__(self, manual, directory):
        self.manual, self.directory = manual, directory
        self.ui = UIOpenCommands(manual)
        self.capture = None
        self.started = None

    async def start(self, kind, name):
        if kind == 'capture':
            self.capture = KitScreenshotObserver(self.manual)
            accepted = self.capture.request()
            if not accepted:
                raise ValueError(self.capture.observation().get('reason'))
            self.started = time.monotonic()
            return True
        if kind == 'scroll':
            return await self.ui.use_talking_scroll()
        return await self.ui.request(name)

    async def collect(self, kind, name):
        if kind != 'capture':
            row = self.ui.collect()
            return None if row['status'] == 'PENDING' else row
        await self.capture.sample()
        row = self.capture.collect()
        if row.get('status') == 'OBSERVED':
            # Preserve each original PNG before the next source capture uses
            # its normal destination. The original observer owns its backups.
            destination = self.directory / (name + '.png')
            with Path(row['image_path']).open('rb') as source, destination.open('xb') as target:
                shutil.copyfileobj(source, target)
            row = dict(row, retained_image_path=str(destination), visual_result='UNKNOWN')
            self.capture.close()
            self.capture = None
            return row
        if row.get('cleanup_required') or time.monotonic() - self.started > 15:
            return row
        return None

    def close(self):
        if self.capture is not None:
            self.capture.close()
        self.ui.close()


def load_baseline():
    path = ROOT / 'work/local_original_session/run_manual_baseline_scenario.py'
    spec = importlib.util.spec_from_file_location('ui_shots_baseline', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prepare_runtime(directory, bridge):
    """Copy an executable and bridges into a fresh private candidate directory.

    Keep the original resource directory and existing preflight; no fixed slot
    or on-disk product registry is changed. Digest is the launcher's existing pin.
    """
    original = launcher.PRODUCTS[PROFILE]
    directory.mkdir(parents=True, exist_ok=False)
    image = directory / original['image'].name
    shutil.copy2(original['image'], image)
    for name in original['bridges']:
        shutil.copy2(bridge if name == 'own-login-bridge-dg49.dll'
                     else original['image'].parent / name, directory / name)
    spec = dict(original, image=image, bridge_artifact=bridge,
                bridges={**original['bridges'], 'own-login-bridge-dg49.dll': launcher.digest(bridge)})
    launcher.PRODUCTS[PROFILE] = spec
    return image, original


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_name')
    parser.add_argument('--candidate-bridge', type=Path, required=True)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--feature-config', type=Path, required=True)
    parser.add_argument('--expected-uuid', required=True)
    parser.add_argument('--tool-timeout-seconds', type=float, default=180)
    args = parser.parse_args(argv)
    baseline = load_baseline()
    directory = ROOT / 'work/local_original_session/runs' / args.run_name
    image, old_spec = prepare_runtime(directory.with_name(args.run_name + '-runtime'),
                                      args.candidate_bridge.absolute())
    old_run, old_argv = launcher.run_session, sys.argv
    state = {'scenario': None, 'sequence': None}

    class Scenario(baseline.Scenario):
        def saved_store(self, broker):
            _, refs = broker.realm.store.snapshot()
            baseline.need(refs == {'SoloMage'} and broker.realm.store.select('SoloMage')[0] > 0,
                          'ONE_FRESH_SAVED_MAGE_REQUIRED')
            return refs

        def tick(self, row, broker, status):
            if self.stage != 'IDLE':
                super().tick(row, broker, status)

    async def run(owner, factory, stop, **kwargs):
        monitor = kwargs['monitor']
        scenario = Scenario(owner, monitor, stop, 0, background=True,
                            source_quit_test=True, profile=PROFILE)
        state['scenario'] = scenario
        original_tick = monitor.tick
        original_factory = kwargs['feature_factory']
        operations = None

        def tick(broker=None, *, state='RUNNING', force=False):
            row = original_tick(broker, state=state, force=force)
            scenario.tick(row or {}, broker, state)
            return row

        def feature_factory(broker):
            nonlocal operations
            features = original_factory(broker)
            operations = Operations(features.manual, monitor.directory)
            sequence = state['sequence'] = UISequence(operations)
            original_poll = features.poll

            async def poll(monitor=None, **options):
                row = await original_poll(monitor, **options)
                # Ordinary first-grant and client row confirmation finish before
                # any UI action. Do not synthesize or reset readiness.
                if scenario.stage == 'IDLE' and not features.manual.pending:
                    if features.manual.last_result.get('status') == 'COMMITTED':
                        await sequence.tick()
                        path = directory / 'ui-shots-scenario.json'
                        path.write_text(json.dumps(dict(results=sequence.results, error=sequence.error,
                            complete=sequence.done and sequence.error is None,
                            visual_result='UNKNOWN'), ensure_ascii=False, indent=2), encoding='utf-8')
                        if sequence.done:
                            stop.set()  # Existing SourceQuit and FIRST/finally own close.
                return row

            features.poll = poll
            return features

        monitor.tick = tick
        kwargs['feature_factory'] = feature_factory
        try:
            report = await old_run(owner, factory, stop, **kwargs)
            sequence = state['sequence']
            report['ui_shots'] = dict(results=[] if sequence is None else sequence.results,
                error=scenario.error or (None if sequence is None else sequence.error),
                complete=sequence is not None and sequence.done and sequence.error is None,
                visual_result='UNKNOWN')
            return report
        finally:
            monitor.tick = original_tick
            if operations is not None:
                operations.close()

    launcher.run_session = run
    sys.argv = ['launcher', '--run', '--product', PROFILE, '--control-mode', 'manual',
        '--background', '--source-quit-test', '--image', str(image), '--store', str(args.store),
        '--feature-config', str(args.feature_config), '--expected-uuid', args.expected_uuid,
        '--run-directory', str(directory), '--test-duration', str(args.tool_timeout_seconds)]
    try:
        code = launcher.main()
        sequence = state['sequence']
        return code if sequence is not None and sequence.done and sequence.error is None else 2
    finally:
        launcher.run_session, sys.argv = old_run, old_argv
        launcher.PRODUCTS[PROFILE] = old_spec


if __name__ == '__main__':
    raise SystemExit(main())
