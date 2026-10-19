"""Explicit same-process saved equipment restoration after original reselect.

This consumer creates neither selections nor receipts. Original ProductFeatures
prepares/samples the actual new generation; original Open and old UI APIs perform
their independent current acquisition. No Use/Update/Mark or Native retry.
"""
from __future__ import annotations

import time

from tools.local_original_session import observe

need = observe.need
PROFILE = 'sibling-background-item-equipment-reselect-restore-spawn'
DLL_SHA = 'bbda56d51c26def3aca345126c4dfe1740eb29b0311c10d21eba9ec0693c0b6d'


def configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import feature_config, inventory as inv, inventory_store, restart
    from tools.local_original_session.item_use_session import POLICY as USE_POLICY
    from tools.local_original_session.item_equipment_effect import POLICY as EFFECT_POLICY
    need(type(config) is feature_config.Features and inventory and auto_inventory
         and config.inventory_policy == inv.POLICY and type(config.inventory_frame) is bytes
         and config.inventory_store_policy == inventory_store.POLICY
         and config.inventory_delivery_policy == feature_config.LOCAL_WORLD_READY_ONCE
         and config.inventory_reselection_policy == feature_config.LOCAL_SAVED_ROW_ON_RESELECTION
         and config.restart_policy == restart.POLICY and config.inventory_missing_row_policy is None
         and config.item_use_policy == USE_POLICY and config.item_equipment_policy == EFFECT_POLICY
         and config.item_equipment_first_enable is False and config.inventory_update_policy is None
         and not config.spawns and config.attack_policy is config.attack_feedback is None
         and config.interval_ns is config.motion_policy is config.goal_policy is config.goal is None
         and config.attack_hp_provider is config.npc_death_policy is config.npc_remove_policy is None
         and config.npc_respawn_policy is config.npc_respawn_spawn is None,
         'SCENARIO_RESELECT_EQUIPMENT_SAVED_RESTORE_CONFIG_REQUIRED')
    inv.validate_frame(config.inventory_frame)
    return config


class RestoredEquipmentUI:
    """One new-generation sync/raw -> Open -> fresh primitive, then old Quit."""
    def __init__(self, scenario):
        self.scenario = scenario
        self.runtime = self.completed = self.identity = None
        self.receipt = self.raw = self.open = self.ui = None
        self.open_queued = self.ui_queued = False
        self.started = self.started_ns = self.open_started_ns = self.ui_started_ns = None
        self.result = dict(status='NOT_REQUESTED', initial_sync='UNKNOWN', raw='UNKNOWN',
                           open='NOT_REQUESTED', ui='UNKNOWN', model_uid=None, model_d4=None,
                           expected_model_d4=None, proof_scope='UNKNOWN')

    def bind(self, runtime):
        from tools.local_original_session import launcher
        need(type(runtime) is launcher.ProductFeatures and self.runtime is None
             and runtime.equipment_observer is not None and runtime.inventory_ui_opener is not None
             and runtime.equipment_ui_observer is not None and runtime.manual.allow_use_item is False
             and runtime.manual.allow_inventory_update is False and runtime.npc_session is None
             and getattr(runtime, 'mark_on_indicator', None) is None,
             'SCENARIO_RESELECT_EQUIPMENT_ACTUAL_RUNTIME_REQUIRED')
        self.runtime = runtime

    def begin(self, completed):
        need(self.completed is None and self.runtime is not None,
             'SCENARIO_RESELECT_EQUIPMENT_ONCE_REQUIRED')
        self.completed = completed  # Original old -> new completion, never manufactured.
        self.started, self.started_ns = self.scenario.clock(), self.scenario.reselect_started_ns
        self.scenario.stage = 'RESELECT_EQUIPMENT_SYNC_WAIT'
        self.result['status'] = 'WAITING_NEW_GENERATION_SYNC'

    def current(self, row, broker):
        from tools.local_original_session import inventory, launcher
        s, runtime = self.scenario, self.runtime
        need(self.completed is not None and s.reselect_completed is self.completed
             and s.source_reselect['status'] == 'COMMITTED' and s.inventory_only is True,
             'SCENARIO_RESELECT_EQUIPMENT_COMPLETION_REQUIRED')
        old, generation, bound, completed_current = self.completed
        need(launcher.ManualMoveRequests._source_reselect_current(runtime.manual) is self.completed,
             'SCENARIO_RESELECT_EQUIPMENT_ORIGINAL_CURRENT_REQUIRED')
        service, position, _proof, known = s.current(row, broker)
        need(known is True and service is generation.mover and position is completed_current[3]
             and s.move_bound[0] is generation.writer and generation is broker._inventory_generation
             and generation.previous is old['restart_generation'] and generation.phase == 'ACTIVE'
             and old['restart_generation'].phase == 'RETIRED'
             and generation.selected is generation.game.selection and generation.writer is bound[0][0]
             and generation.store is broker._inventory_store
             and generation.current_frame is broker._inventory_current_frame
             and generation.current_frame is generation.frame is generation.operation_frame
             and generation.selection_binding is broker._inventory_selection_binding,
             'SCENARIO_RESELECT_EQUIPMENT_NEW_LIFE_REQUIRED')
        s.reader.validate()
        need(s.owner.validate(s.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        actual, writer, effect = runtime._equipment_binding(same_selection=True)
        need(actual is broker and writer is generation.writer and runtime._equipment_generation is generation
             and runtime._equipment_delivery_complete(broker, generation) is True
             and s.attack['status'] == 'NOT_REQUESTED' and not s.moves and s.hold_complete is False
             and (service.requests_received, service.committed, service.corrections_prepared) == (0, 0, 0)
             and broker._item_use_session is generation.item_use_session
             and broker._item_use_session.accepted_count == 0 and broker._item_use_session._current is None,
             'SCENARIO_RESELECT_EQUIPMENT_CURRENT_SOURCE_REQUIRED')
        info = inventory.validate_frame(generation.current_frame)
        identity = (writer, generation, generation.game, generation.selected,
                    generation.service, generation.item_use_session, broker.realm._actor_fields)
        if self.identity is None:
            self.identity = identity
        need(all(a is b for a, b in zip(self.identity, identity)),
             'SCENARIO_RESELECT_EQUIPMENT_IDENTITY_CHANGED')
        if self.receipt is not None:
            life = effect._selection
            need(type(life) is dict and life.get('synced') is True
                 and type(life.get('identity')) is tuple and len(life['identity']) == 7
                 and all(a is b for a, b in zip(life['identity'], identity))
                 and life.get('sync_receipt') == self.receipt
                 and runtime.item_equipment_initial == self.receipt
                 and broker.item_equipment_observation(writer) == self.receipt,
                 'SCENARIO_RESELECT_EQUIPMENT_SYNC_LIFE_CHANGED')
            s._restore_receipt(self.receipt, initial=True, position=position, identifier=info.identifier)
        return position, info.identifier, runtime

    def tick(self, row, broker):
        s = self.scenario
        need(s.clock() - self.started < 15, 'SCENARIO_RESELECT_EQUIPMENT_OBSERVATION_EXPIRED')
        position, identifier, runtime = self.current(row, broker)
        if s.stage == 'RESELECT_EQUIPMENT_SYNC_WAIT':
            receipt = runtime.item_equipment_initial
            if receipt is None:
                return
            s._restore_receipt(receipt, initial=True, position=position, identifier=identifier)
            need(receipt.get('initialization_source') == 'RESTORED_EQUIPMENT_SIDECAR',
                 'SCENARIO_RESELECT_EQUIPMENT_EXISTING_SIDECAR_REQUIRED')
            self.receipt = receipt
            self.current(row, broker)  # Bind receipt to actual new seven-owner life.
            if runtime._equipment_sample_ordinal != 0 or runtime.equipment_observation is None:
                return
            self.raw = dict(runtime.equipment_observation)
            need(type(self.raw.get('query_started_monotonic_ns')) is int
                 and self.started_ns <= self.raw['query_started_monotonic_ns'] <= time.monotonic_ns(),
                 'SCENARIO_RESELECT_EQUIPMENT_FRESH_RAW_REQUIRED')
            if not s._restore_raw(self.raw, receipt, position):
                return  # Original raw sampler cadence; no new query or retry.
            self.result.update(status='RESTORED_SYNC_AND_RAW', initial_sync='SYNCHRONIZED',
                               raw='STRICT_STABLE', expected_model_d4=receipt['after_weapon_uid'] == identifier)
            self.open_started_ns = time.monotonic_ns()
            s.stage = 'RESELECT_EQUIPMENT_OPEN_WAIT'
            return
        need(self.receipt is not None and self.raw is not None
             and s._restore_raw(self.raw, self.receipt, position),
             'SCENARIO_RESELECT_EQUIPMENT_STRICT_RESTORE_REQUIRED')
        if s.stage == 'RESELECT_EQUIPMENT_OPEN_WAIT':
            queued = True if self.open_queued else runtime.request_inventory_ui_open()
            self.open = dict(runtime.inventory_ui_open_observation)  # Preserve requestFalse reason.
            need(queued is True, 'SCENARIO_RESELECT_EQUIPMENT_OPEN_REQUEST_REFUSED')
            self.open_queued = True
            if self.open['status'] == 'UNKNOWN' and self.open['reason'] in (
                    'NOT_SAMPLED', 'INVENTORY_UI_OPEN_REQUESTED', 'INVENTORY_UI_OPEN_PENDING'):
                need(all(self.open[k] is None for k in ('opened', 'before_own_visible', 'after_own_visible', 'native_sequence')),
                     'SCENARIO_RESELECT_EQUIPMENT_OPEN_PENDING_NULL_REQUIRED')
                return
            need(self.open['status'] == 'RETURNED' and type(self.open['reason']) is int and self.open['reason'] == 0
                 and self.open['invoked'] is self.open['opened'] is True
                 and self.open['before_own_visible'] is False and self.open['after_own_visible'] is True
                 and self.open['cleanup_required'] is False,
                 'SCENARIO_RESELECT_EQUIPMENT_NORMAL_OPEN_REQUIRED')
            s._restore_source(self.open, position, identifier, self.open_started_ns)
            need(self.open['native_sequence'] > s.source_reselect['native_sequence'],
                 'SCENARIO_RESELECT_EQUIPMENT_OPEN_SEQUENCE_REQUIRED')
            self.result['open'] = 'RETURNED'
            self.ui_started_ns = time.monotonic_ns()
            s.stage = 'RESELECT_EQUIPMENT_UI_WAIT'
            return
        queued = True if self.ui_queued else runtime.request_item_equipment_ui_observation()
        self.ui = dict(runtime.equipment_ui_observation)
        need(queued is True, 'SCENARIO_RESELECT_EQUIPMENT_UI_REQUEST_REFUSED')
        self.ui_queued = True
        fields = {'status', 'reason', 'invoked', 'observed', 'model_uid', 'model_d4', 'native_sequence',
                  'source_pid', 'source_birth', 'source_image_sha256', 'player_uid', 'item_identifier',
                  'map_id', 'query_started_monotonic_ns', 'cleanup_required'}
        need(set(self.ui) == fields, 'SCENARIO_RESELECT_EQUIPMENT_UI_SCHEMA_REQUIRED')
        if self.ui['status'] == 'UNKNOWN' and self.ui['reason'] in ('NOT_SAMPLED', 'UI_OBSERVE_REQUESTED', 'UI_OBSERVE_PENDING'):
            need(all(self.ui[k] is False for k in ('invoked', 'observed', 'cleanup_required'))
                 and all(self.ui[k] is None for k in fields - {'status', 'reason', 'invoked', 'observed', 'cleanup_required'}),
                 'SCENARIO_RESELECT_EQUIPMENT_UI_PENDING_NULL_REQUIRED')
            return
        need(self.ui['status'] == 'OBSERVED' and type(self.ui['reason']) is int and self.ui['reason'] == 0
             and self.ui['invoked'] is False and self.ui['observed'] is True
             and self.ui['cleanup_required'] is False and type(self.ui['model_uid']) is int
             and self.ui['model_uid'] == identifier and type(self.ui['model_d4']) is bool,
             'SCENARIO_RESELECT_EQUIPMENT_UI_OBSERVED_REQUIRED')
        s._restore_source(self.ui, position, identifier, self.ui_started_ns)
        need(self.ui['native_sequence'] > self.open['native_sequence']
             and self.ui['query_started_monotonic_ns'] > self.open['query_started_monotonic_ns']
             and self.ui['model_d4'] is (self.receipt['after_weapon_uid'] == identifier),
             'SCENARIO_RESELECT_EQUIPMENT_FRESH_MODEL_RESTORE_REQUIRED')
        self.current(row, broker)
        self.result.update(status='OBSERVED', ui='OBSERVED', model_uid=self.ui['model_uid'],
                           model_d4=self.ui['model_d4'], proof_scope='NEW_RESELECT_RESTORED_SYNC_STRICT_RAW_OPEN_FRESH_UID_D4')
        s.stage = 'RESELECT_EQUIPMENT_UI_COMPLETE_STOP_REQUESTED'
        s.stop.set()  # Existing normal SourceQuit owns cleanup.

    def detail(self):
        return dict(schema='manual-reselect-equipment-ui-observation-v1', restore=self.result,
                    initial=self.receipt, raw=self.raw, open=self.open, ui=self.ui)
