"""Runner binding only: original client-confirmed Add, UI owner, existing Quit.

No migration, sender, Native return gate, memory provider or retry is installed.
"""
import asyncio

from tools.local_original_session import item_custody, item_transfer_session, inventory as inv
from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration
from tools.local_original_session.item_transfer_ui import ItemTransferUI

PROFILE = item_transfer_session.PROFILE
DLL_SHA = '20e52b0bdacd36fcd4d37ce27bc61dff70cdeaafcafe60aca38faa92c74e52b4'
EXPECTED_UIDS = (65537, 65538)
WHOLE_QUANTITY = 3


def need(value, code):
    if not value:
        raise ValueError(code)


def configuration(features, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import item_use_session, item_equipment_effect
    item_transfer_session.configuration(features)
    need(inventory is True and auto_inventory is True
         and features.item_use_policy == item_use_session.POLICY
         and features.item_equipment_policy == item_equipment_effect.POLICY
         and features.item_equipment_first_enable is False,
         'SCENARIO_TRANSFER_REAL_EQUIPMENT_RESTORE_REQUIRED')
    one = inv.validate_frame(features.inventory_frame)
    fields = dict(one.raw_fields)
    need(fields[1] == EXPECTED_UIDS[0] and fields[2] == 1 and fields[4] == WHOLE_QUANTITY,
         'SCENARIO_TRANSFER_EXACT_SINGLE_A_CONFIG_REQUIRED')
    return features


class Runtime:
    def __init__(self, original, scenario, broker):
        from tools.local_original_session import launcher
        need(type(original) is launcher.ProductFeatures
             and type(original.item_transfer_ui) is ItemTransferUI
             and type(broker) is PersistentBroker
             and original.item_transfer_ui.broker is broker
             and original.manual.inventory_broker is broker
             and original.manual.consumer.reader is scenario.reader,
             'SCENARIO_TRANSFER_ACTUAL_RUNTIME_REQUIRED')
        self.original, self.scenario, self.broker = original, scenario, broker
        self.manual, self.npc_session = original.manual, original.npc_session
        self.requested = False
        scenario.transfer_runtime = self

    async def _start_after_actual_add(self):
        from tools.local_original_session import launcher
        ui, broker = self.original.item_transfer_ui, self.broker
        need(not self.requested and ui.started is False,
             'SCENARIO_TRANSFER_ONCE_REQUIRED')
        binding = launcher.current_manual_binding(broker)
        if binding is None:
            return
        generation = PersistentBroker.inventory_selection_current(broker, binding.writer)
        if generation is None or not self.original._equipment_initial_client_ready(
                broker, binding.writer, generation):
            return
        need(type(generation) is _InventoryGeneration and generation.phase == 'ACTIVE'
             and generation.previous is None and generation.writer is binding.writer,
             'SCENARIO_TRANSFER_FRESH_GENERATION_REQUIRED')
        need(type(generation.transfer_session) is item_transfer_session.ItemTransferSession
             and generation.transfer_session.broker is broker,
             'SCENARIO_TRANSFER_ORIGINAL_SESSION_REQUIRED')
        async with generation.row['operation_lock']:
            context = item_transfer_session.ItemTransferSession.context_locked(
                generation.transfer_session, binding.writer)
            a, b = item_custody._members(context.snapshot.frame_ab)
            need((a.identifier, b.identifier) == EXPECTED_UIDS
                 and all(dict(member.raw_fields)[2] == 1 and
                         dict(member.raw_fields)[4] == WHOLE_QUANTITY for member in (a,b))
                 and context.current_frame is context.initial_frame
                 and context.snapshot.phase == 'READY' and context.snapshot.owner == 'PLAYER'
                 and context.membership.phase == 'READY'
                 and context.item_use_session.accepted_count == 0
                 and context.item_use_session._current is None
                 and context.equipment.item_uid == a.identifier
                 and context.equipment.weapon_uid in (0, a.identifier, b.identifier),
                 'SCENARIO_TRANSFER_EXACT_FRESH_AB_INPUT_REQUIRED')
            prepare = context.equipment.weapon_uid == b.identifier
        self.requested = True  # Spend before public once-request, never retry.
        need(self.original.request_item_transfer_roundtrip(prepare_use=prepare) is True,
             'SCENARIO_TRANSFER_PUBLIC_ONCE_REQUEST_REQUIRED')
        self.scenario.transfer_result.update(status='PENDING', phase=ui.phase,
            prepare_use=prepare, equipped_before=context.equipment.weapon_uid)
        actual = self.manual.last_result
        self.scenario.inventory = {name: actual[name] for name in
            ('status','phase','proof_scope','client_inventory','item_count','transport_proof_scope')
            if name in actual}

    def _capture(self):
        ui = self.original.item_transfer_ui
        if self.requested:
            self.scenario.transfer_result.update(ui.last)
            if ui.phase == 'DONE':
                need(ui.last.get('status') == 'COMPLETE', 'SCENARIO_TRANSFER_DONE_RESULT_REQUIRED')
                self.scenario.stage = 'ITEM_TRANSFER_COMPLETE_STOP_REQUESTED'
                self.scenario.stop.set()
            elif ui.closed or ui.last.get('status') == 'UNKNOWN':
                raise ValueError('SCENARIO_TRANSFER_UI_UNKNOWN')

    async def poll(self, monitor=None):
        if self.scenario.stop.is_set():
            return {}
        try:
            need(monitor is self.scenario.monitor, 'SCENARIO_TRANSFER_SAME_MONITOR_REQUIRED')
            result = await self.original.poll(monitor)
            if self.scenario.stage == 'ITEM_TRANSFER_RUN' and not self.requested:
                await self._start_after_actual_add()
            self._capture()
            self.scenario.save()
            return result
        except asyncio.CancelledError:
            self.scenario.fail_transfer('SCENARIO_TRANSFER_CANCELLED')
            raise
        except Exception as error:
            from tools.local_original_session import launcher
            self.original.item_transfer_ui.close()
            self.scenario.fail_transfer(launcher.safe_error_code(error) or type(error).__name__)
            return {}

    def finalize(self):
        self._capture()

    def close(self):
        self.original.close()  # Original SourceQuit/owner cleanup retains all pending claims.
