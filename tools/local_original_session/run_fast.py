"""Run an existing bot module's main() under fast_clock (bot files untouched).

    SL_TEST_TIME_SCALE=10 SL_TEST_PORT_BASE=42000 python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_loopback --minutes 3

fast_clock is enabled BEFORE the bot/broker modules are imported, so default
``clock=time.monotonic`` arguments bind to the virtual clock. stdout is the
module's own output; one JSON line with real/virtual seconds goes to stderr.
"""
import importlib
import json
import os
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from tools.local_original_session import fast_clock  # noqa: E402  (stdlib-only module)

fast_clock.enable_from_env()
real_start = fast_clock.real_monotonic()
module = importlib.import_module('tools.local_original_session.' + sys.argv[1])
code = 1
try:
    code = module.main(sys.argv[2:])
finally:
    info = fast_clock.report()
    info.update(module=sys.argv[1], argv=sys.argv[2:], exit=code,
                real_seconds_total=round(fast_clock.real_monotonic() - real_start, 3))
    print('FAST_CLOCK ' + json.dumps(info), file=sys.stderr, flush=True)
raise SystemExit(code)
