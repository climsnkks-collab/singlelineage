"""Owned Lv51 bonus/elixir socket scenario; source fixtures, no original client.

The fresh prelogin saved fixture is explicit development input. Only received
normal login/selection/world, owned UID use, distribution and reconnect count
as observed socket actions. A startup pin failure is retained, never bypassed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import traceback
import uuid
from unittest.mock import patch

from tools.local_original_session import hunt_bot as hb, hunt_bot_scenarios as hs, test_ports


class BonusBot(hs.ScenarioBot):
    def __init__(self, options):
        super().__init__(options)
        self.bonus_count = None
        self.status_fields = {}

    def apply(self, frame):
        if frame.opcode == 0x4f0f:
            frame.values = hb.fields(frame.wire[4:-2])
            self.bonus_count = hb.scalar(frame.values, 1)
        super().apply(frame)
        if frame.opcode == 0x4e38:
            self.status_fields.update({k: hb.scalar(frame.values, k) for k in range(4, 10)})


class BonusScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'bonus_stats', directory)
        self.fixture = None

    def record(self, name, ok, **evidence):
        super().record(name, ok, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    async def open(self, *, seed, character=None):
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(self.directory, expected, seed=seed)
        if seed:
            from tools.local_original_session import inventory
            from tools.local_original_session.game_data import load_m1
            from tools.local_original_session.world_progress import Progress
            from tools.local_original_session.world_feature_bonus_stat import ELIXIR_ICONS, ELIXIR_NAMES
            exp = load_m1().pc_exp[50]
            self.broker._world_progress.commit(1, Progress(exp, 51, 1000, 100))
            before = self.store.restore(1)
            rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(before)]
            for index, (name, icon) in enumerate(zip(ELIXIR_NAMES, ELIXIR_ICONS)):
                fields = dict(self.broker.INVENTORY_STARTER_FIELDS)
                fields.update({1: max(row[1] for row in rows) + 1, 2: 895 + index,
                               4: 2, 7: icon, 18: name.encode('utf8')})
                rows.append(fields)
            after = inventory.build_kit_frame(rows)
            self.store.replace_kit(1, before, after, append=True)
            self.broker._inventory_current_frame = after
            self.fixture = dict(level=51, exp=exp, max_hp=1000, max_mp=100,
                bonus_stats='absent; zero arrays', elixirs='895..900 two each',
                scope='fresh LOCAL prelogin development fixture; initial Lv1..51 growth not played')
            snapshot = self.directory / 'starting-profile'
            snapshot.mkdir()
            for name in ('characters.json', 'progression.json', 'inventory.json', 'equipment.json', 'positions.json'):
                path = self.directory / name
                if path.exists():
                    (snapshot / name).write_bytes(path.read_bytes())
            (self.directory / 'starting-fixture.json').write_text(json.dumps(self.fixture, indent=2), encoding='utf8')
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected, '--timeout', str(self.args.timeout)])
        options.port = test_ports.port(options.port)
        self.bot = BonusBot(options)
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = self.broker._world.data, time.monotonic()
        await self.bot.login()
        await self.bot.peer.wait(0, lambda frames: hb.find(frames, 0x4f0f), 'BONUS_ENTER_NOTICE')
        self.record('normal_FIRST_login_selection_world', self.bot.selected and self.bot.level == 51,
                    received_bonus=self.bot.bonus_count)

    async def bonus_stats(self):
        bot = self.bot
        self.record('Lv51_one_point', bot.bonus_count == 1)
        old = dict(bot.status_fields)
        await bot.peer.request(0x4f10, hb.uint(1, 0),
            check=lambda frames: hb.find(frames, 0x4f0f, **{'1': 0})
                and hb.find(frames, 0x4e38), label='RAISE_STR')
        self.record('allocated_once_selfinfo_and_saved', bot.status_fields[4] == old[4] + 1
                    and self.broker._world_progress.bonus_stats(1)[0][0] == 1)
        saved = self.broker._world_progress.path.read_bytes()
        await bot.peer.request(0x4f10, hb.uint(1, 0),
            check=lambda frames: hb.find(frames, 0x4f0f, **{'1': 0})
                and hb.find(frames, 0x4e38), label='RAISE_NO_POINTS')
        self.record('duplicate_no_extra_growth', saved == self.broker._world_progress.path.read_bytes())
        uid = next(uid for uid, row in bot.inventory.items() if row[2] == 897)
        quantity, con = bot.inventory[uid][4], bot.status_fields[8]
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        await bot.peer.request(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
            check=lambda frames: hb.find(frames, 0x0965) and hb.find(frames, 0x4e38), label='ELIXIR_CON')
        self.record('owned_elixir_consumed_and_base_CON', bot.inventory[uid][4] == quantity - 1
                    and bot.status_fields[8] == con + 1
                    and self.broker._world_progress.bonus_stats(1)[1][4] == 1)
        expected = dict(bot.status_fields)
        self.record('first_epoch_cleanup', await self.close())
        await self.open(seed=False)
        self.record('reconnect_permanent_growth_and_remaining', self.bot.status_fields == expected
                    and self.bot.bonus_count == 0 and self.bot.inventory[uid][4] == quantity - 1)


def parser():
    result = hs.parser()
    result.set_defaults(scenario='bonus_stats')
    next(action for action in result._actions if action.dest == 'scenario').choices = ('bonus_stats',)
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    directory = Path(tempfile.mkdtemp(prefix='hunt-bonus-stats-', dir=root))
    scene = BonusScenario(args, directory)
    files = ('world_feature_bonus_stat.py', 'world_bonus_stat_tests.py', 'hunt_bot_bonus_stat.py',
             'world_progress.py', 'world_core_stats.py', 'world_core_kit.py', 'world_handlers.py',
             'world_bridge.py', 'world_state_services.py', 'world_warehouse.py', 'broker.py')
    sources = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in files}
    # Existing endpoints keep their logical identity. Both physical test listeners
    # stay in this worker's56000..57999 allocation, instead of base+2030.
    base = int(os.environ.get('SL_TEST_PORT_BASE', '56000'))
    physical = {12000: base, 14030: base + 1}
    with patch.object(test_ports, 'port', side_effect=lambda logical: physical[logical]), \
         patch.object(test_ports, 'listener_ports', return_value=physical):
        try:
            result = await scene.run()
        except BaseException:
            (directory / 'first-failure.txt').write_text(traceback.format_exc(), encoding='utf8')
            raise
    result.update(directory=str(directory), fixture=scene.fixture, source_sha256=sources,
        physical_ports=physical, scale=os.environ.get('SL_TEST_TIME_SCALE', '1'),
        scope='normal socket path only; fresh declared Lv51 fixture; no original UI or rendering verification')
    if result.get('error'):
        (directory / 'first-failure.txt').write_text(str(result['error']) + '\n', encoding='utf8')
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps({k: result[k] for k in ('status', 'directory', 'error', 'cleanup_complete')}, ensure_ascii=False))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
