"""Owned loopback equipment failure recovery; no native client or user save.

Run sequentially with SL_TEST_PORT_BASE=26000. Results and partial saves stay
in the existing runs directory. Deliberate failures are development evidence.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot as hb


class FailureMatrix(matrix.Matrix):
    async def equip_all(self):
        effect = self.broker._item_equipment_effect
        uid, _ = self.item(41)
        peer = self.bot.peer
        self.fixture_notes.append(dict(
            scope='development one-shot equipment exceptions through real FIRST/login/select/world and CS0960 decoder/router; no native UI claim',
            injected_stages=['before_save', 'before_notify', 'after_notify']))
        for stage in ('before_save', 'before_notify', 'after_notify'):
            self.stage = 'development_fault_' + stage
            before = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
            dropped = getattr(self.broker, '_world_dropped_requests', 0)
            accepted = self.broker._item_use_session.accepted_count
            failure_start = len(self.server_failures)
            error = RuntimeError('DEVELOPMENT_EQUIPMENT_' + stage.upper())
            once = True
            if stage == 'before_save':
                owner, name = self.equipment, 'compare_and_swap_kit'
                original = getattr(owner, name)
                def fail_once(*args, **kwargs):
                    nonlocal once
                    if once:
                        once = False
                        raise error
                    return original(*args, **kwargs)
            else:
                owner, name = ((effect, '_notify_kit') if stage == 'before_notify'
                               else (self.broker, '_world_refresh_pc'))
                original = getattr(owner, name)
                async def fail_once(*args, **kwargs):
                    nonlocal once
                    if once:
                        once = False
                        raise error
                    return await original(*args, **kwargs)
            with patch.object(owner, name, fail_once):
                batch = await self.barrier(0x0960,
                    hb.uint(1, uid) + hb.pb.encode_bytes(2, matrix.RAW0), label='FAULT_' + stage)
            after = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
            receipt = effect.observation(self.native_case.writer)
            observed_failures = self.server_failures[failure_start:]
            expected_slots = self.equipped_slots(before)
            if stage != 'before_save':
                expected_slots[self.bot.data.items[41].slot_key] = uid
            self.record('packet_fault_' + stage + '_request_only_recovery',
                not once and self.bot.peer is peer and peer.error is None
                and not self.broker.failure.is_set()
                and getattr(self.broker, '_world_dropped_requests', 0) == dropped + 1
                and self.broker._item_use_session.accepted_count == accepted + 1
                and after.revision == before.revision + int(stage != 'before_save')
                and self.equipped_slots(after) == self.packet_equipment == expected_slots
                and receipt['status'] == 'UNKNOWN' and receipt.get('resync_status') == 'SYNCHRONIZED'
                and bool(observed_failures)
                and all(row['code'] == 'EQUIPMENT_WORLD_REQUEST_FAILED'
                        and (row.get('cause') or {}).get('type') == 'RuntimeError'
                        and (row.get('cause') or {}).get('error') == str(error)
                        and (row.get('cause') or {}).get('traceback', [])[-1:]
                        and row['cause']['traceback'][-1]['function'] == 'fail_once'
                        for row in observed_failures)
                and hb.find(batch, 0x4f57) is not None,
                injected_error=str(error), server_failures=observed_failures, receipt=receipt,
                before=matrix.dataclasses.asdict(before), after=matrix.dataclasses.asdict(after),
                packet_slots=self.packet_equipment,
                dropped_before=dropped, dropped_after=self.broker._world_dropped_requests)
            # These exact expected exceptions remain in the check above. Only
            # unexpected exceptions belong to Matrix's overall failure list.
            del self.server_failures[failure_start:]
            if self.equipped_slots(after).get(self.bot.data.items[41].slot_key) == uid:
                await self.gear_uid(uid)
            self.record('packet_fault_' + stage + '_following_equip', await self.gear_uid(uid))
            self.record('packet_fault_' + stage + '_following_unequip', not await self.gear_uid(uid))
            await self.bot.alive()
            self.record('packet_fault_' + stage + '_same_socket_alive',
                self.bot.peer is peer and peer.error is None and not self.broker.failure.is_set())


class EquipmentPacketFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_equipment_failures_keep_same_socket_and_current_save_usable(self):
        root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
        directory = Path(tempfile.mkdtemp(prefix='equipment-packet-failures-', dir=root))
        args = matrix.parser().parse_args(['--scenario', 'equip_all'])
        source = Path(__file__).resolve()
        matrix.SOURCE_SHA256['equipment_packet_failure_tests'] = dict(file=str(source),
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(), basis='running fault-injection test')
        scenario = FailureMatrix(args, 'equip_all', directory)
        with matrix.environment(SL_EXPERIMENT_MAP=0, SL_EXPERIMENT_SHOP=1,
                SL_EXPERIMENT_WAREHOUSE=1, SL_EXPERIMENT_ENCHANT=0,
                SL_EXPERIMENT_POLY='orc', SL_COMPANION=1, SL_COMPANION_PET_UI=1,
                SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
            result = await scenario.run_matrix()
        print('EQUIPMENT_FAILURE_RESULT=' + str(directory / 'result.json'), flush=True)
        self.assertEqual(result['status'], 'PASS',
            f"{directory / 'result.json'}: {result['failure']}; {result['failures']}")
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(sum(row['check'].endswith('_request_only_recovery')
                             for row in result['checks']), 3)


def main(argv=None):
    result = unittest.main(module=__name__, argv=[__name__, *(argv or [])], exit=False)
    return 0 if result.result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
