"""Owned pledge socket flow, using the existing FIRST/login/select/quit harness.

Fresh pre-FIRST fixture: Lv5 monarch, 3000 adena, one same-account mage.
Every gameplay action is an ordered native request through the real decoder
and router. No original client, user save, live position/stat edit or input.
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

from tools.local_original_session import hunt_bot as hb, hunt_bot_scenarios as hs
from tools.local_original_session import test_ports

MONARCH = ('SoloMonarch', 0, 0, (18, 12, 16, 9, 12, 8))
MAGE = ('PledgeMage', 3, 0, (8, 7, 16, 18, 8, 18))
PLEDGE = '혈맹시험'
NOTICE = '싱글 혈맹 공지\n둘째 줄'
ACKS = (0x071C, 0x070A, 0x0723, 0x0724, 0x0716, 0x072B, 0x071F)


class PledgeBot(hs.ScenarioBot):
    def apply(self, frame):
        if frame.opcode in ACKS:
            frame.values = hb.fields(frame.wire[4:-2])
        super().apply(frame)


class PledgeScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'pledge', directory)
        self.fixture, self.actions = None, []

    def record(self, name, ok, **evidence):
        super().record(name, ok, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    def wallet(self):
        from tools.local_original_session import inventory
        return next(dict(v.raw_fields)[4] for v in inventory.validate_kit_frame(
            self.store.restore(1)) if v.template_bits == 7)

    async def open(self, *, seed, character=None):
        try:
            await self._open(seed=seed, character=character)
        except BaseException:
            (self.directory / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise

    async def _open(self, *, seed, character=None):
        from tools.local_original_session import broker as broker_module
        from tools.local_original_session import inventory, movement
        from tools.local_original_session.world_progress import Progress
        expected = str(uuid.uuid4())
        # The shared harness imports this fixture tuple at function entry.
        # This is pre-FIRST test construction, not a product class override.
        with patch('tools.local_original_session.hunt_bot_loopback.KNIGHT', MONARCH):
            self.broker, self.store, self.equipment = await hs.build_epoch(
                self.directory, expected, seed=seed)
        if seed:
            self.broker.realm.store.create(broker_module.ack.realm.Creation(*MAGE))
            before = self.store.restore(1)
            rows = [dict(v.raw_fields) for v in inventory.validate_kit_frame(before)]
            next(v for v in rows if v[2] & 0xffffffff == 7)[4] = 3000
            frame = inventory.build_kit_frame(rows)
            self.store.replace_kit(1, before, frame)
            self.broker._inventory_current_frame = frame
            town, data = self.broker._world.data.town, self.broker._world.data
            for uid, creation in ((1, MONARCH), (2, MAGE)):
                x, y = movement.authority.unpack_grid(self.broker.realm._actor_fields[1])
                origin = self.broker.realm.positions.restore(movement.Position(uid, creation[0], 0, x, y))
                self.broker.realm.positions.commit(origin, movement.Position(uid,
                    creation[0], town.map_id, town.respawn_x, town.respawn_y))
            self.broker._world_progress.commit(1, Progress(data.pc_exp[4], 5, 200, 100))
            # Member equipment is the same explicit saved-kit stand-in used by
            # the shared fixture. It is not a companion actor/runtime spawn.
            mage_frame = self.broker._inventory_kit_frame(3)
            self.store.grant(2, mage_frame)
            self.initialize_member_equipment(mage_frame)
            self.fixture = dict(monarch=dict(uid=1, name=MONARCH[0], character_class=0,
                level=5, adena=3000), member=dict(uid=2, name=MAGE[0], character_class=3),
                profile='fresh owned characters.json, inventory/equipment/position/progression stores',
                scope='pre-FIRST fixture supply only; no user save or live state edit')
            (self.directory / 'starting-fixture.json').write_text(json.dumps(self.fixture,
                ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected,
            '--minutes', str(self.args.minutes), '--timeout', str(self.args.timeout)])
        options.port, options.character = test_ports.port(options.port), character or MONARCH[0]
        self.bot = PledgeBot(options)
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = self.broker._world.data, time.monotonic()
        self.bot.terrain = self.broker._world.terrain
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'PLEDGE_KIT_DELIVERY')
        self.record('FIRST_login_selection_world_' + str(len(self.bots)),
            self.bot.selected and self.bot.inventory_received and self.bot.hp > 0,
            uid=self.bot.self_uid, character=self.bot.character, level=self.bot.level)

    def initialize_member_equipment(self, frame):
        from tools.local_original_session import inventory, equipment_store
        data = self.broker._world.data
        items = {v.template_bits: v.identifier for v in inventory.validate_kit_frame(frame)}
        equipped = [data.items[v.template_id] for v in data.starter.entries(3, 'test_knight') if v.equipped]
        weapon = next(v for v in equipped if v.kind == 'weapon')
        self.equipment.initialize_kit(2, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=items[weapon.template_id], slots=tuple((v.slot_key, items[v.template_id])
                for v in equipped if v.kind == 'armor'))

    async def request(self, opcode, payload=b'', expected=None):
        # ALIVE is an ordered processing barrier, never a pledge success reply.
        frames = await self.bot.peer.request(opcode, payload, alive=True,
            check=lambda rows: hb.find(rows, 0x4F57), label=f'PLEDGE_{opcode:04X}')
        notices = [v for v in frames if v.opcode in ACKS]
        self.actions.append(dict(uid=self.bot.self_uid, opcode=f'{opcode:04X}',
            replies=[dict(opcode=f'{v.opcode:04X}', ordinal=v.ordinal) for v in notices]))
        if expected is not None:
            self.record('ack_' + str(len(self.actions)), hb.find(notices, expected) is not None,
                action=self.actions[-1])
        return notices

    @staticmethod
    def member_names(frame):
        return [hb.scalar(hb.fields(raw), 1).decode('utf-8') for raw in frame.values.get(3, ())]

    async def info(self, *, name, members=()):
        batch = await self.request(0x0722, expected=0x0723)
        info = hb.find(batch, 0x0723)
        observed = hb.scalar(info.values, 1, b'').decode('utf-8')
        self.record('info_name_' + str(len(self.actions)), observed == name, observed=observed)
        if members:
            page = hb.find(batch, 0x0724)
            names = [] if page is None else self.member_names(page)
            keys = [] if page is None else [hb.scalar(hb.fields(raw), 4)
                                            for raw in page.values.get(3, ())]
            self.record('member_page_' + str(len(self.actions)), set(names) == set(members)
                and len(set(keys)) == len(members),
                observed=names, pagination=None if page is None else
                [hb.scalar(page.values, 1), hb.scalar(page.values, 2)], local_row_keys=keys)
        return info

    async def pledge(self):
        try:
            await self.flow()
        except BaseException:
            (self.directory / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise

    async def flow(self):
        await self.info(name='')
        create = lambda name: hb.pb.encode_bytes(1, name.encode('utf-8')) + hb.uint(2, 0)
        rejected = await self.request(0x071B, create('공백 이름'), expected=0x071C)
        self.record('bad_name_refused_connection_alive_without_cost',
            hb.scalar(hb.find(rejected, 0x071C).values, 1) == 0 and self.wallet() == 3000
            and self.broker.realm.store.pledges()['clans'] == [])
        made = await self.request(0x071B, create(PLEDGE), expected=0x071C)
        self.record('monarch_creation_ack_and_exact_saved_cost',
            hb.scalar(hb.find(made, 0x071C).values, 1) == 1 and self.wallet() == 2000
            and any(v.get(2, 0) & 0xffffffff == 7 and v.get(4) == 2000
                    for v in self.bot.inventory.values()),
            wallet_before=3000, wallet_after=self.wallet())
        await self.info(name=PLEDGE, members=(MONARCH[0],))
        repeated = await self.request(0x071B, create(PLEDGE), expected=0x071C)
        self.record('duplicate_creation_refused_without_second_payment',
            hb.scalar(hb.find(repeated, 0x071C).values, 1) == 0 and self.wallet() == 2000)
        malformed = await self.request(0x0727, hb.pb.encode_bytes(1, b'\xff'))
        self.record('malformed_notice_refused_connection_alive_without_mutation',
            hb.find(malformed, 0x072B) is None
            and self.broker.realm.store.pledges()['clans'][0]['notice'] == '')
        await self.request(0x0727, hb.pb.encode_bytes(1, NOTICE.encode('utf-8')), expected=0x072B)
        info = await self.info(name=PLEDGE, members=(MONARCH[0],))
        self.record('notice_persisted_and_consumed_by_info_field7',
            hb.scalar(info.values, 7) == NOTICE.encode('utf-8')
            and self.broker.realm.store.pledges()['clans'][0]['notice'] == NOTICE)
        listing = await self.request(0x071E, hb.pb.encode_bytes(1, PLEDGE.encode('utf-8')),
            expected=0x071F)
        found = [hb.scalar(hb.fields(raw), 1).decode('utf-8')
                 for raw in hb.find(listing, 0x071F).values.get(1, ())]
        self.record('LOCAL_pledge_list_name_projection', found == [PLEDGE], observed=found)
        await self.close()

        await self.open(seed=False, character=MAGE[0])
        await self.info(name='')
        rejected = await self.request(0x071B, create('법사창설거절'), expected=0x071C)
        self.record('non_prince_create_refused_connection_alive',
            hb.scalar(hb.find(rejected, 0x071C).values, 1) == 0)
        unknown = await self.request(0x0709, hb.pb.encode_bytes(1, '없는혈맹'.encode('utf-8')),
            expected=0x070A)
        self.record('unknown_pledge_native_refusal_enum4',
            hb.scalar(hb.find(unknown, 0x070A).values, 1) == 4)
        joined = await self.request(0x0709, hb.pb.encode_bytes(1, PLEDGE.encode('utf-8')),
            expected=0x070A)
        self.record('same_account_member_native_join_success',
            hb.scalar(hb.find(joined, 0x070A).values, 1) == 0)
        await self.info(name=PLEDGE, members=(MONARCH[0], MAGE[0]))
        no_notice = await self.request(0x0727, hb.pb.encode_bytes(1, b'not leader'))
        self.record('member_notice_refused_connection_alive_and_notice_preserved',
            hb.find(no_notice, 0x072B) is None
            and self.broker.realm.store.pledges()['clans'][0]['notice'] == NOTICE)
        left = await self.request(0x0715, hb.pb.encode_bytes(1, PLEDGE.encode('utf-8')), expected=0x0716)
        self.record('ordinary_member_leave_preserves_pledge',
            hb.scalar(hb.find(left, 0x0716).values, 1) == 1
            and self.broker.realm.store.pledges()['clans'][0]['members'] == [1])
        await self.info(name='')
        await self.request(0x0709, hb.pb.encode_bytes(1, PLEDGE.encode('utf-8')),
            expected=0x070A)
        await self.close()

        await self.open(seed=False)
        info = await self.info(name=PLEDGE, members=(MONARCH[0], MAGE[0]))
        self.record('reconnect_restores_pledge_members_notice_without_recharge',
            self.wallet() == 2000 and hb.scalar(info.values, 7) == NOTICE.encode('utf-8'),
            saved_wallet=self.wallet())
        dissolved = await self.request(0x0715, hb.pb.encode_bytes(1, PLEDGE.encode('utf-8')),
            expected=0x0716)
        self.record('leader_leave_disbands_and_preserves_id_lineage',
            hb.scalar(hb.find(dissolved, 0x0716).values, 1) == 1
            and self.broker.realm.store.pledges()['clans'] == []
            and self.broker.realm.store.pledges()['next_id'] == 2 and self.wallet() == 2000)
        await self.info(name='')
        self.record('no_handler_or_hook_errors', not getattr(self.broker, '_world_handler_errors', ())
            and not getattr(self.broker, '_world_hook_errors', ()))


def parser():
    result = hs.parser()
    result.description = __doc__
    result.set_defaults(scenario='pledge')
    next(v for v in result._actions if v.dest == 'scenario').choices = ('pledge',)
    return result


async def run(args):
    from tools.local_original_session.hunt_bot_play_matrix import environment
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-pledge-', dir=root))
    scene = PledgeScenario(args, directory)
    relevant = ('hunt_bot_pledge.py', 'world_pledge.py', 'world_feature_pledge.py',
        'world_handlers.py', 'world_bridge.py', 'world_core_session.py', 'world_core_kit.py',
        'world_state_services.py', 'inventory_store.py', 'world_progress.py', 'broker.py',
        'hunt_bot_scenarios.py', 'hunt_bot_loopback.py', '../local_character_creation/realm.py')
    sources = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
               for name in relevant}
    with environment(SL_EXPERIMENT_MAP=2, SL_WORLD_TOWN_CANDIDATES='',
            SL_COMPANION=0, SL_COMPANION_PET_UI=0):
        result = await scene.run()
    result.update(directory=str(directory), fixture=scene.fixture, actions=scene.actions,
        source_sha256=sources, time_scale=os.environ.get('SL_TEST_TIME_SCALE', '1'),
        physical_ports=test_ports.listener_ports(),
        scope='owned fixture, actual socket decoder/router and saved state; native UI/input/rendering and original-server equivalence unverified')
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False,
        indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(dict(status=result['status'], directory=result['directory'],
        error=result['error'], checks=len(result['checks']),
        cleanup_complete=result['cleanup_complete']), ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
