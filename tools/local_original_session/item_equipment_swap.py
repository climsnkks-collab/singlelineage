"""Two owned weapons: default Use B x3, saved-B tail x2, explicit zero-Use reselect.

Only consumes original source-owned deliveries, intents and receipts. Public
requests keep their original once/no-retry producer and Native queue.
"""
from __future__ import annotations

import hashlib
import time

from tools.local_original_session.observe import need

PROFILE = 'sibling-background-item-equipment-swap-reselect-spawn'
DLL_SHA = 'bbda56d51c26def3aca345126c4dfe1740eb29b0311c10d21eba9ec0693c0b6d'


def configuration(config, *, inventory=False, auto_inventory=False):
    from tools.local_original_session import feature_config as fc, inventory as inv, inventory_store, restart
    from tools.local_original_session.item_use_session import POLICY as USE
    from tools.local_original_session.item_equipment_effect import POLICY as EFFECT
    need(type(config) is fc.Features and inventory is auto_inventory is True
         and config.inventory_policy == inv.POLICY and type(config.inventory_frame) is bytes
         and config.inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
         and config.inventory_collection_policy == inv.COLLECTION_POLICY
         and type(config.inventory_collection_grant) is tuple and len(config.inventory_collection_grant) == 2
         and config.inventory_collection_grant[0] == inventory_store.SECOND_INSTANCE_POLICY
         and type(config.inventory_collection_grant[1]) is frozenset
         and config.inventory_delivery_policy == fc.LOCAL_WORLD_READY_ONCE
         and config.inventory_reselection_policy == fc.LOCAL_SAVED_ROW_ON_RESELECTION
         and config.restart_policy == restart.POLICY and config.inventory_missing_row_policy is None
         and config.item_use_policy == USE and config.item_equipment_policy == EFFECT
         and config.item_equipment_first_enable is False and config.inventory_update_policy is None
         and config.hp_status_policy is config.hp_status_input is None
         and not config.spawns and config.attack_policy is config.attack_feedback is None
         and config.interval_ns is config.motion_policy is config.goal_policy is config.goal is None
         and config.attack_hp_provider is config.npc_death_policy is config.npc_remove_policy is None
         and config.npc_respawn_policy is config.npc_respawn_spawn is None,
         'SCENARIO_SWAP_EXPLICIT_SAVED_COLLECTION_CONFIG_REQUIRED')
    inv.validate_collection_frame(config.inventory_frame, policy=inv.COLLECTION_POLICY)
    return config


def collection(frame):
    from tools.local_original_session import inventory
    items = inventory.validate_collection_frame(frame, policy=inventory.COLLECTION_POLICY)
    need(len(items) == 2 and all(item.template_bits == 1 for item in items),
         'SCENARIO_SWAP_TWO_REAL_WEAPONS_REQUIRED')
    return items


def receipt_valid(receipt, *, position, items, initial, after, prior=None, ordinal=None):
    """Strict aggregate; the singleton toggle validator remains unchanged."""
    from tools.local_original_session import equipment_change, item_equipment_effect as effect
    uids = tuple(item.identifier for item in items)
    need(type(receipt) is dict and len(uids) == 2 and len(set(uids)) == 2
         and all(type(uid) is int and 0 < uid <= 0xffffffff for uid in uids)
         and type(after) is int and after in (0,) + uids,
         'SCENARIO_SWAP_RECEIPT_INPUT_REQUIRED')
    operation = 'INITIAL_SYNC' if initial else 'ITEM_USE_EFFECT'
    need(receipt.get('schema') == effect.SCHEMA and receipt.get('policy') == effect.POLICY
         and receipt.get('operation') == operation
         and receipt.get('status') == ('SYNCHRONIZED' if initial else 'COMMITTED')
         and receipt.get('phase') == 'DRAINED' and receipt.get('reason') is None
         and receipt.get('writer_bound') is receipt.get('generation_bound') is True
         and type(receipt.get('character_uid')) is int and receipt['character_uid'] == position.uid
         and type(receipt.get('item_uid')) is int and receipt['item_uid'] == (uids[0] if initial else uids[1])
         and type(receipt.get('template')) is int and receipt['template'] == 1
         and type(receipt.get('after_weapon_uid')) is int and receipt['after_weapon_uid'] == after
         and type(receipt.get('after_revision')) is int and 0 < receipt['after_revision'] < (1 << 64)
         and type(receipt.get('equipment_key_i32')) is int and -(1 << 31) <= receipt['equipment_key_i32'] < (1 << 31)
         and receipt.get('inventory_frame_changed') is False and receipt.get('client_state') == 'UNKNOWN'
         and type(receipt.get('notification_opcode')) is int and receipt['notification_opcode'] == 0x097a
         and all(receipt.get(k) is True for k in ('write_attempted', 'drain_returned', 'post_owner_verified')),
         'SCENARIO_SWAP_AUTHORITATIVE_RECEIPT_REQUIRED')
    if initial:
        need(receipt.get('accepted_ordinal') is None
             and receipt.get('initialization_source') == 'RESTORED_EQUIPMENT_SIDECAR'
             and type(receipt.get('before_weapon_uid')) is int and receipt['before_weapon_uid'] == after
             and type(receipt.get('before_revision')) is int and receipt['before_revision'] == receipt['after_revision']
             and receipt.get('persist_attempted') is receipt.get('persisted') is False,
             'SCENARIO_SWAP_RESTORED_SIDECAR_REQUIRED')
        changes = ((after or uids[0], after != 0),)
    else:
        need(type(prior) is dict and type(ordinal) is int and 1 <= ordinal <= 3
             and type(receipt.get('accepted_ordinal')) is int and receipt['accepted_ordinal'] == ordinal
             and receipt['equipment_key_i32'] == prior['equipment_key_i32']
             and type(receipt.get('before_weapon_uid')) is int
             and receipt['before_weapon_uid'] == prior['after_weapon_uid'] != after
             and type(receipt.get('before_revision')) is int
             and receipt['before_revision'] == prior['after_revision']
             and receipt['after_revision'] == prior['after_revision'] + 1
             and receipt.get('persist_attempted') is receipt.get('persisted') is True
             and receipt.get('initialization_source') is None
             and type(receipt.get('quantity_before')) is int
             and receipt['quantity_before'] == dict(items[1].raw_fields)[4]
             and type(receipt.get('quantity_after')) is int
             and receipt['quantity_after'] == receipt['quantity_before'],
             'SCENARIO_SWAP_EXACT_CAS_REQUIRED')
        before = prior['after_weapon_uid']
        changes = (() if before == 0 else ((before, False),)) + (() if after == 0 else ((after, True),))
    count = len(changes)
    need(all(type(receipt.get(k)) is int and receipt[k] == count for k in
             ('notification_count', 'notifications_attempted', 'notifications_drained'))
         and type(receipt.get('notification_records')) is list and len(receipt['notification_records']) == count,
         'SCENARIO_SWAP_COMPLETE_ORDERED_WIRES_REQUIRED')
    previous_sent = None
    for record, (uid, equipped) in zip(receipt['notification_records'], changes):
        wire = equipment_change.build_change(uid=uid, key=receipt['equipment_key_i32'], equipped=equipped)
        need(type(record) is dict and record.get('operation') == operation
             and record.get('accepted_ordinal') == (None if initial else ordinal)
             and (record.get('accepted_ordinal') is None if initial else type(record.get('accepted_ordinal')) is int)
             and type(record.get('notification_uid')) is int and record['notification_uid'] == uid
             and type(record.get('notification_equipped')) is bool and record['notification_equipped'] is equipped
             and type(record.get('notification_size')) is int and record['notification_size'] == len(wire)
             and record.get('notification_sha256') == hashlib.sha256(wire).hexdigest()
             and record.get('status') == record.get('phase') == 'DRAINED' and record.get('reason') is None
             and all(record.get(k) is True for k in ('write_attempted', 'drain_returned', 'post_owner_verified'))
             and type(record.get('sent_before')) is int and record['sent_before'] >= 0
             and type(record.get('sent_after')) is int and record['sent_after'] == record['sent_before'] + 1
             and (previous_sent is None or record['sent_before'] == previous_sent),
             'SCENARIO_SWAP_ORDERED_WIRE_PROOF_REQUIRED')
        previous_sent = record['sent_after']
    need((count == 2 and receipt.get('notification_size') is receipt.get('notification_sha256') is None)
         or (count == 1 and type(receipt.get('notification_size')) is int
             and receipt['notification_size'] == receipt['notification_records'][0]['notification_size']
             and receipt.get('notification_sha256') == receipt['notification_records'][0]['notification_sha256']),
         'SCENARIO_SWAP_SINGULAR_WIRE_FIELDS_REQUIRED')
    return True


def raw_valid(raw, receipt, position, *, allowed_previous=()):
    """An observed old A/intermediate empty is pending; UNKNOWN is terminal."""
    need(type(raw) is dict and raw.get('status') == 'OBSERVED' and raw.get('reason') is None
         and all(raw.get(k) is True for k in ('source_contract_valid', 'stable_double_read', 'source_owner_revalidated'))
         and raw.get('read_consistency') == 'STRICT_STABLE'
         and all(raw.get(k) is False for k in ('snapshot_atomic', 'equipped_state_proven',
             'item_uid_equivalence_proven', 'slot_names_proven', 'visible_screen_claimed'))
         and type(raw.get('selected_uid')) is int and raw['selected_uid'] == position.uid
         and type(raw.get('map_id')) is int and raw['map_id'] == position.map_id
         and type(raw.get('rows')) is list and type(raw.get('entry_count')) is int
         and raw['entry_count'] == len(raw['rows']) <= 128
         and type(raw.get('empty')) is bool and raw['empty'] is (not raw['rows'])
         and type(raw.get('typed_bytes_requested')) is int and 0 < raw['typed_bytes_requested'] <= 16384
         and raw.get('typed_byte_limit') == 16384 and raw.get('max_samples_per_second') == 2
         and type(raw.get('query_started_monotonic_ns')) is int and raw['query_started_monotonic_ns'] >= 0,
         'SCENARIO_SWAP_STRICT_RAW_REQUIRED')
    rows = raw['rows']
    need(all(type(r) is dict and set(r) == {'rawkey_i32', 'value_u64'}
             and type(r['rawkey_i32']) is int and -(1 << 31) <= r['rawkey_i32'] < (1 << 31)
             and type(r['value_u64']) is int and 0 <= r['value_u64'] < (1 << 64) for r in rows)
         and len({r['rawkey_i32'] for r in rows}) == len(rows), 'SCENARIO_SWAP_RAW_ROWS_REQUIRED')
    found = tuple(r['value_u64'] for r in rows if r['rawkey_i32'] == receipt['equipment_key_i32'])
    expected = () if receipt['after_weapon_uid'] == 0 else (receipt['after_weapon_uid'],)
    need(found == expected or found in allowed_previous, 'SCENARIO_SWAP_RAW_VALUE_MISMATCH')
    return found == expected


class CollectionSwap:
    def __init__(self, scenario, *, saved_b_tail=False, zero_use_tail=False):
        need(type(saved_b_tail) is bool, 'SCENARIO_SWAP_SAVED_B_TAIL_BOOL_REQUIRED')
        need(type(zero_use_tail) is bool and not (zero_use_tail and saved_b_tail),
             'SCENARIO_SWAP_ZERO_USE_EXPLICIT_EXCLUSIVE_BOOL_REQUIRED')
        self.saved_b_tail, self.zero_use_tail = saved_b_tail, zero_use_tail
        self.required_uses = 0 if zero_use_tail else 2 if saved_b_tail else 3
        self.scenario = scenario
        self.runtime = self.completed = self.identity = self.frame = self.items = self.initial_generation = None
        self.receipt = self.raw = self.open = None
        self.receipts, self.raws, self.ui_pairs, self.intents = [], [], [], []
        self.started = self.started_ns = None
        self.inventory_started_ns = None
        self.ordinal = 0
        self.open_queued = self.ui_queued = False
        self.ui_index = 0
        self.ui_rows = []
        self.last_query = self.last_sequence = 0
        self.result = dict(status='NOT_REQUESTED', accepted_count=0, completed_uses=0,
                           initial='UNKNOWN', restored='UNKNOWN', ui='UNKNOWN', proof_scope='UNKNOWN')
        if saved_b_tail:
            self.result.update(saved_b_tail=True, planned_uses=2)
        if zero_use_tail:
            self.result.update(zero_use_tail=True, planned_uses=0)

    def bind(self, runtime):
        from tools.local_original_session import launcher
        need(type(runtime) is launcher.ProductFeatures and self.runtime is None and not runtime._closed
             and runtime.manual.allow_use_item is (not self.zero_use_tail)
             and (not self.zero_use_tail or runtime.manual.consumer.allow_use_item is False)
             and runtime.manual.allow_inventory_update is False
             and runtime.equipment_observer is not None and runtime.inventory_ui_opener is not None
             and runtime.equipment_ui_observer is not None and runtime.npc_session is None
             and getattr(runtime, 'mark_on_indicator', None) is None,
             'SCENARIO_SWAP_ACTUAL_RUNTIME_REQUIRED')
        self.runtime = runtime

    def inventory_authority(self, row, broker):
        from tools.local_original_session import inventory
        s = self.scenario
        mover, position, _proof, known = s.current(row, broker)
        need(s.attack['status'] == 'NOT_REQUESTED' and not s.moves and not s.hold_complete
             and (s.origin is None or position.metadata() == s.origin)
             and (mover.requests_received, mover.committed, mover.corrections_prepared) == (0, 0, 0),
             'SCENARIO_SWAP_NO_OTHER_ACTION_REQUIRED')
        if not known and s.auto_inventory_binding is None:
            return position, False
        generation, selected, frame = broker._inventory_generation, broker._inventory_selection_binding, broker._inventory_frame
        need(generation is not None and generation.phase == 'ACTIVE' and generation.writer is s.move_bound[0]
             and selected is generation.selection_binding and type(selected) is tuple and len(selected) == 11
             and selected[0] is generation.writer and selected[1] is generation.row
             and generation.store is broker._inventory_store and broker._inventory_restored is True
             and type(frame) is bytes and frame is generation.frame,
             'SCENARIO_SWAP_SAVED_SELECTION_REQUIRED')
        broker._inventory_selection_frame_current(generation.writer, generation.row, frame)
        if self.saved_b_tail or self.zero_use_tail:
            collection(frame)  # Existing saved2 is mandatory; no new instance grant.
            need(generation.collection_grant is None, 'SCENARIO_SWAP_TAIL_EXISTING_TWO_ROWS_REQUIRED')
        else:
            inventory.validate_collection_frame(frame, policy=inventory.COLLECTION_POLICY)
        return position, known

    def collect_inventory(self, row, broker):
        s = self.scenario
        self.inventory_authority(row, broker)
        result = s._result()
        need(result is None or result['sequence'] <= s.INVENTORY_SEQUENCE,
             'SCENARIO_SWAP_ADD_SEQUENCE_REQUIRED')
        if result is not None and result['sequence'] == s.INVENTORY_SEQUENCE:
            need(result.get('command') == 'AddInventory' and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
                 and result.get('cleanup_required') is not True, 'SCENARIO_SWAP_ADD_REFUSED')
            if result['status'] == 'COMMITTED':
                need(result.get('phase') == 'CLIENT_CONFIRMED'
                     and result.get('proof_scope') == 'CLIENT_ITEM_ROWS_SCALARS_ONLY'
                     and result.get('client_inventory') == 'ROWS_5_SCALARS_MATCHED'
                     and type(result.get('item_count')) is int and result['item_count'] == 2
                     and result.get('transport_proof_scope') == 'TRANSPORT_DRAIN_ONLY' and result.get('invoked') is True
                     and all(result.get(k) == 'UNKNOWN' for k in ('render', 'equipped', 'save'))
                     and all(result.get(k) is False for k in ('all_17_wire_fields_proven',
                         'wire_field18_bytes_observed', 'catalog_live_materialization_proven')),
                     'SCENARIO_SWAP_TWO_ROW_CLIENT_PROOF_REQUIRED')
                self.frame = broker._inventory_current_frame
                self.items = collection(self.frame)
                s.auto_inventory_frame, s.auto_inventory_binding = self.frame, broker._inventory_selection_binding
                self.initial_generation = broker._inventory_generation
                s.inventory.update(status='COMMITTED', proof_scope=result['proof_scope'],
                    client_inventory=result['client_inventory'], item_count=2, trial_role='REQUIRED_SWAP_PREPARATION')
                self.start('SWAP_SYNC_WAIT')
                need(type(self.inventory_started_ns) is int and self.inventory_started_ns >= 0,
                     'SCENARIO_SWAP_INITIAL_PUBLICATION_TIME_REQUIRED')
                # Product poll may have completed the immutable ordinal0 raw
                # before the scenario consumes Add COMMITTED. Its lower bound
                # is the actual initial request, never this later consumption.
                self.started_ns = self.inventory_started_ns
                return
        need(s.clock() - s.inventory_started < 15, 'SCENARIO_SWAP_ADD_EXPIRED')

    def start(self, stage):
        self.started, self.started_ns = self.scenario.clock(), time.monotonic_ns()
        self.scenario.stage = stage

    def current(self, row, broker):
        from tools.local_original_session import launcher, item_use_session
        s, runtime = self.scenario, self.runtime
        need(type(runtime) is launcher.ProductFeatures and not runtime._closed
             and runtime.manual is s.restart_manual and runtime.manual.consumer.reader is s.reader,
             'SCENARIO_SWAP_RUNTIME_CHANGED')
        mover, position, _proof, known = s.current(row, broker)
        need(known is True and s.inventory['status'] == 'COMMITTED' and s.attack['status'] == 'NOT_REQUESTED'
             and not s.moves and s.hold_complete is False
             and (mover.requests_received, mover.committed, mover.corrections_prepared) == (0, 0, 0),
             'SCENARIO_SWAP_CURRENT_SOURCE_REQUIRED')
        s.reader.validate()
        need(s.owner.validate(s.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
        actual, writer, effect = runtime._equipment_binding(same_selection=True)
        generation = broker._inventory_generation
        need(actual is broker and writer is s.move_bound[0] and generation is runtime._equipment_generation
             and generation.phase == 'ACTIVE' and generation.writer is writer
             and generation.mover is mover and generation.game.selection is generation.selected
             and generation.selection_binding is broker._inventory_selection_binding
             and generation.current_frame is generation.frame is generation.operation_frame is broker._inventory_current_frame
             and generation.store is broker._inventory_store
             and runtime._equipment_delivery_complete(broker, generation) is True
             and generation.current_frame == self.frame
             and generation.store.restore(position.uid) == generation.current_frame,
             'SCENARIO_SWAP_CURRENT_GENERATION_REQUIRED')
        items = collection(generation.current_frame)
        need(items == self.items, 'SCENARIO_SWAP_ORDERED_MEMBERS_CHANGED')
        session = generation.item_use_session
        need(type(session) is item_use_session.ItemUseSession and session is broker._item_use_session
             and session is broker.realm._item_use_session and session.broker is broker and not session.closed
             and type(session.accepted_count) is int and 0 <= session.accepted_count <= (0 if self.completed else self.required_uses),
             'SCENARIO_SWAP_ORIGINAL_SESSION_REQUIRED')
        if self.saved_b_tail and self.completed is None and not self.ui_pairs or self.zero_use_tail and self.completed is None:
            need(type(self.ordinal) is int and self.ordinal == 0
                 and session.accepted_count == 0 and session._current is None,
                 'SCENARIO_SWAP_TAIL_FRESH_SESSION_REQUIRED')
        if self.completed is not None:
            old, new, bound, current = self.completed
            need(s.reselect_completed is self.completed and s.source_reselect['status'] == 'COMMITTED'
                 and launcher.ManualMoveRequests._source_reselect_current(runtime.manual) is self.completed
                 and new is generation and new.previous is old['restart_generation'] is self.initial_generation
                 and old['restart_generation'].phase == 'RETIRED' and current[3] is position
                 and writer is bound[0][0] and session._current is None,
                 'SCENARIO_SWAP_ORIGINAL_RESELECT_COMPLETION_REQUIRED')
        else:
            need(generation is self.initial_generation and generation.current_frame is self.frame,
                 'SCENARIO_SWAP_INITIAL_LIFE_CHANGED')
        identity = (writer, generation, generation.game, generation.selected,
                    generation.service, session, broker.realm._actor_fields)
        if self.identity is None:
            self.identity = identity
        need(len(self.identity) == 7 and all(a is b for a, b in zip(identity, self.identity)),
             'SCENARIO_SWAP_SEVEN_OWNERS_CHANGED')
        if self.receipt is not None:
            expected = runtime.item_equipment_initial if self.completed or self.ordinal == 0 else runtime.item_equipment_current
            accepted = None if self.completed or self.ordinal == 0 else self.ordinal
            need(expected == self.receipt and broker.item_equipment_observation(writer, accepted_ordinal=accepted) == self.receipt,
                 'SCENARIO_SWAP_RECEIPT_CHANGED')
        return position, runtime, session, effect, generation

    def expected(self):
        if self.zero_use_tail:
            return self.items[1].identifier
        if self.saved_b_tail:
            return self.items[1].identifier if self.completed or self.ordinal in (0, 2) else 0
        return self.items[1].identifier if self.completed or self.ordinal in (1, 3) else 0 if self.ordinal == 2 else self.items[0].identifier

    def collect_sync(self, row, broker):
        position, runtime, session, effect, generation = self.current(row, broker)
        initial = self.completed is not None or self.ordinal == 0
        receipt = runtime.item_equipment_initial if initial else runtime.item_equipment_current
        if receipt is None:
            return
        if not initial and receipt.get('accepted_ordinal') != self.ordinal:
            need(receipt.get('accepted_ordinal') == self.ordinal - 1 or self.ordinal == 1
                 and receipt.get('operation') == 'INITIAL_SYNC', 'SCENARIO_SWAP_EFFECT_ORDINAL_CHANGED')
            return
        receipt_valid(receipt, position=position, items=self.items, initial=initial,
                      after=self.expected(), prior=None if initial else self.receipts[-1], ordinal=None if initial else self.ordinal)
        if self.completed:
            previous = self.receipts[-1]
            need(receipt['after_revision'] == previous['after_revision']
                 and receipt['equipment_key_i32'] == previous['equipment_key_i32']
                 and receipt['after_weapon_uid'] == previous['after_weapon_uid'],
                 'SCENARIO_SWAP_EXACT_SAVED_B_RESTORE_REQUIRED')
        self.receipt = receipt
        self.current(row, broker)
        life = effect._selection
        need(type(life) is dict and life.get('synced') is True and type(life.get('identity')) is tuple
             and len(life['identity']) == 7 and all(a is b for a, b in zip(life['identity'], self.identity))
             and life.get('sync_receipt') == runtime.item_equipment_initial,
             'SCENARIO_SWAP_SYNC_LIFE_REQUIRED')
        state = effect.store.restore(position.uid, generation.current_frame)
        need(state.weapon_uid == self.expected() and state.revision == receipt['after_revision']
             and state.item_uid == self.items[0].identifier, 'SCENARIO_SWAP_SAVED_EQUIPMENT_REQUIRED')
        sample_ordinal = 0 if initial else self.ordinal
        if runtime._equipment_sample_ordinal != sample_ordinal or runtime.equipment_observation is None:
            return
        raw = runtime.equipment_observation
        need(type(raw) is dict and type(raw.get('query_started_monotonic_ns')) is int
             and self.started_ns <= raw['query_started_monotonic_ns'] <= time.monotonic_ns()
             and (not self.raws or raw['query_started_monotonic_ns'] > self.raws[-1]['query_started_monotonic_ns']),
             'SCENARIO_SWAP_FRESH_RAW_REQUIRED')
        if (self.saved_b_tail or self.zero_use_tail) and self.completed is None:
            previous = ((),) if self.ordinal in (0, 2) else ((self.items[1].identifier,),)
        else:
            previous = ((), (self.items[0].identifier,)) if self.completed or self.ordinal == 1 else (
                ((),) if self.ordinal == 0 else ((self.receipts[-1]['after_weapon_uid'],),) if self.ordinal == 2 else ((),))
        if not raw_valid(raw, receipt, position, allowed_previous=previous):
            return
        self.raw = dict(raw)
        self.receipts.append(dict(receipt)); self.raws.append(dict(raw))
        if self.ordinal == 0 or self.completed:
            if self.completed:
                need(runtime.retire_inventory_ui_open_after_reselect(
                    self.completed, current_after_reselect=self.zero_use_tail) is True,
                     'SCENARIO_SWAP_OLD_OPEN_RETIRE_REQUIRED')
            self.open_queued = False
            s = self.scenario
            s.stage = 'SWAP_OPEN_WAIT'
            self.open_started_ns = time.monotonic_ns()
            self.result['restored' if self.completed else 'initial'] = 'STRICT_STABLE'
        else:
            self.begin_ui()

    def collect_open(self, row, broker):
        position, runtime, _session, _effect, _generation = self.current(row, broker)
        if not self.open_queued:
            need(runtime.request_inventory_ui_open() is True, 'SCENARIO_SWAP_OPEN_REQUEST_REFUSED')
            self.open_queued = True
        value = self.open = dict(runtime.inventory_ui_open_observation)
        if value['status'] == 'UNKNOWN' and value['reason'] in ('NOT_SAMPLED', 'INVENTORY_UI_OPEN_REQUESTED', 'INVENTORY_UI_OPEN_PENDING'):
            need(all(value[k] is None for k in ('opened', 'before_own_visible', 'after_own_visible', 'native_sequence')),
                 'SCENARIO_SWAP_OPEN_PENDING_NULL_REQUIRED')
            return
        if self.zero_use_tail and self.completed is not None:
            from tools.local_original_session.inventory_ui_open import AFTER_RESULT, AFTER_COMMAND
            need(value.get('schema') == AFTER_RESULT and value.get('command') == AFTER_COMMAND,
                 'SCENARIO_SWAP_POST_RESELECT_OPEN_MODE_REQUIRED')
            opened = (value['status'] == 'RETURNED' and type(value['reason']) is int and value['reason'] == 0
                 and value['invoked'] is value['opened'] is True
                 and value['before_own_visible'] is False and value['after_own_visible'] is True
                 and value.get('branch') == 'OPEN_RETURNED' and value.get('current_own_visible') is None)
            current = (value['status'] == 'OBSERVED_ALREADY_OPEN' and type(value['reason']) is int and value['reason'] == 0
                 and value['invoked'] is False and value['opened'] is None
                 and value['before_own_visible'] is True and value['after_own_visible'] is None
                 and value.get('branch') == 'ALREADY_OPEN_CURRENT' and value.get('current_own_visible') is True)
            need((opened or current) and value['cleanup_required'] is False,
                 'SCENARIO_SWAP_POST_RESELECT_CURRENT_OPEN_REQUIRED')
        else:
            need(value['status'] == 'RETURNED' and type(value['reason']) is int and value['reason'] == 0
                 and value['invoked'] is value['opened'] is True
                 and value['before_own_visible'] is False and value['after_own_visible'] is True
                 and value['cleanup_required'] is False, 'SCENARIO_SWAP_ORIGINAL_OPEN_REQUIRED')
        self.scenario._restore_source(value, position, self.items[0].identifier, self.open_started_ns)
        need(value['native_sequence'] > self.last_sequence and value['query_started_monotonic_ns'] > self.last_query,
             'SCENARIO_SWAP_OPEN_FRESH_SEQUENCE_REQUIRED')
        need(self.completed is None or value['native_sequence'] > self.scenario.source_reselect['native_sequence'],
             'SCENARIO_SWAP_OPEN_AFTER_RESELECT_SEQUENCE_REQUIRED')
        self.last_sequence, self.last_query = value['native_sequence'], value['query_started_monotonic_ns']
        self.begin_ui()

    def begin_ui(self):
        self.ui_index, self.ui_rows, self.ui_queued = 0, [], False
        self.ui_started_ns = time.monotonic_ns()
        self.scenario.stage = 'SWAP_UI_WAIT'

    def collect_ui(self, row, broker):
        position, runtime, session, _effect, _generation = self.current(row, broker)
        identifier = self.items[self.ui_index].identifier
        if not self.ui_queued:
            need(runtime.request_item_equipment_ui_observation(item_identifier=identifier) is True,
                 'SCENARIO_SWAP_UI_REQUEST_REFUSED')
            self.ui_queued = True
        value = dict(runtime.equipment_ui_observation)
        fields = {'status', 'reason', 'invoked', 'observed', 'model_uid', 'model_d4', 'native_sequence',
                  'source_pid', 'source_birth', 'source_image_sha256', 'player_uid', 'item_identifier',
                  'map_id', 'query_started_monotonic_ns', 'cleanup_required'}
        need(set(value) == fields, 'SCENARIO_SWAP_UI_EXACT_DTO_REQUIRED')
        if value['status'] == 'UNKNOWN' and value['reason'] in ('NOT_SAMPLED', 'UI_OBSERVE_REQUESTED', 'UI_OBSERVE_PENDING'):
            need(all(value[k] is False for k in ('invoked', 'observed', 'cleanup_required'))
                 and all(value[k] is None for k in fields - {'status', 'reason', 'invoked', 'observed', 'cleanup_required'}),
                 'SCENARIO_SWAP_UI_PENDING_NULL_REQUIRED')
            return
        need(value['status'] == 'OBSERVED' and type(value['reason']) is int and value['reason'] == 0
             and value['invoked'] is False and value['observed'] is True and value['cleanup_required'] is False
             and type(value['model_uid']) is int and value['model_uid'] == identifier
             and type(value['model_d4']) is bool and value['model_d4'] is (self.expected() == identifier),
             'SCENARIO_SWAP_UI_UID_D4_REQUIRED')
        self.scenario._restore_source(value, position, identifier, self.ui_started_ns)
        need(value['native_sequence'] > self.last_sequence and value['query_started_monotonic_ns'] > self.last_query,
             'SCENARIO_SWAP_UI_SERIAL_FRESH_REQUIRED')
        self.last_sequence, self.last_query = value['native_sequence'], value['query_started_monotonic_ns']
        self.ui_rows.append(value)
        if self.ui_index == 0:
            self.ui_index, self.ui_queued = 1, False
            self.ui_started_ns = time.monotonic_ns()
            return
        self.ui_pairs.append(self.ui_rows)
        if self.completed:
            self.result.update(status='OBSERVED', ui='OBSERVED', proof_scope=(
                'ZERO_CURRENT_RUN_USES_STRICT_RAW_SERIAL_UID_D4_RESELECT_RESTORE' if self.zero_use_tail else
                'TWO_CURRENT_RUN_ORIGINAL_USES_ORDERED_EFFECTS_STRICT_RAW_SERIAL_UID_D4_RESELECT_RESTORE'
                if self.saved_b_tail else 'THREE_ORIGINAL_USES_ORDERED_EFFECTS_STRICT_RAW_SERIAL_UID_D4_RESELECT_RESTORE'))
            self.scenario.stage = 'SWAP_COMPLETE_STOP_REQUESTED'
            self.scenario.stop.set()
        elif self.zero_use_tail:
            need(self.zero_restart_prepared(row, broker, runtime.manual, position),
                 'SCENARIO_SWAP_ZERO_USE_BEFORE_RESTART_REQUIRED')
            self.result.update(status='READY_RESTART', completed_uses=0, accepted_count=0)
            self.scenario.stage = 'RESTART_READY'
        elif self.ordinal == self.required_uses:
            need(session.accepted_count == self.required_uses and self.runtime.manual.sequence == self.required_uses + 1,
                 'SCENARIO_SWAP_TAIL_TWO_USES_BEFORE_RESTART_REQUIRED' if self.saved_b_tail
                 else 'SCENARIO_SWAP_THREE_USES_BEFORE_RESTART_REQUIRED')
            self.result.update(status='READY_RESTART', completed_uses=self.required_uses)
            self.scenario.stage = 'RESTART_READY'
        else:
            if self.ordinal:
                self.result['completed_uses'] = self.ordinal
            self.start('SWAP_USE_READY')

    def submit_use(self, row, broker):
        need(not self.zero_use_tail, 'SCENARIO_SWAP_ZERO_USE_FORBIDDEN')
        from tools.local_original_session.commands import REQUEST_SCHEMA, _atomic
        from tools.local_original_session import launcher
        s = self.scenario
        position, runtime, session, _effect, generation = self.current(row, broker)
        manual = runtime.manual
        need(self.completed is None and session.accepted_count == self.ordinal and len(self.ui_pairs) == self.ordinal + 1
             and manual.sequence == self.ordinal + 1 and not manual.pending and manual.consumer.pending is None
             and launcher.ManualMoveRequests._actual_manual_producer(manual, asynchronous=True) is manual.consumer,
             'SCENARIO_SWAP_USE_ONCE_REQUIRED')
        self.ordinal += 1
        self.receipt = None
        self.event_start, self.received_base = broker.policy.events, generation.row['policy_row'].received
        self.start('SWAP_USE_WAIT')
        self.result.update(status='USE_PUBLISHED', accepted_count=session.accepted_count)
        s.save()
        _atomic(s.monitor.directory / 'command.request.json', dict(schema=REQUEST_SCHEMA, sequence=self.ordinal + 1,
            command='UseItem', uid=position.uid, item_identifier=self.items[1].identifier, map_id=position.map_id), 1024)

    def collect_use(self, row, broker):
        need(not self.zero_use_tail, 'SCENARIO_SWAP_ZERO_USE_FORBIDDEN')
        s = self.scenario
        _position, runtime, session, _effect, generation = self.current(row, broker)
        result = s._result()
        need(result is None or result['sequence'] <= self.ordinal + 1, 'SCENARIO_SWAP_USE_SEQUENCE_REQUIRED')
        if result is None or result['sequence'] != self.ordinal + 1:
            return
        need(result.get('command') == 'UseItem' and result.get('status') in ('CLAIMED', 'PENDING', 'COMMITTED')
             and result.get('cleanup_required') is not True and result.get('automatic_retry') is False,
             'SCENARIO_SWAP_USE_REFUSED')
        if result['status'] != 'COMMITTED':
            return
        events = list(broker.policy.log)
        offset = self.event_start - (broker.policy.events - len(events))
        need(0 <= offset <= len(events), 'SCENARIO_SWAP_RX_EVENTS_DROPPED')
        received = [event for event in events[offset:] if event[0] == 'rx'
                    and event[1] == generation.row['peer']['endpoint_port'] and event[2] == 0x0960]
        intent = session._current
        need(result.get('phase') == 'COMMITTED' and result.get('native_attempted') is True
             and result.get('proof_scope') == 'VALIDATED_ITEM_USE_INTENT_ONLY' and result.get('reason') is None
             and result.get('cleanup_required') is False and result.get('last_sequence') == self.ordinal + 1
             and all(result.get(k) == 'UNKNOWN' for k in ('use_effect', 'ack', 'equipped', 'render', 'save'))
             and runtime.manual.sequence == self.ordinal + 1 and not runtime.manual.pending
             and session.accepted_count == self.ordinal and len(received) == 1
             and intent is not None and intent.writer is generation.writer and intent.accepted_ordinal == self.ordinal
             and intent.request.identifier == self.items[1].identifier and intent.frame is self.frame
             and intent.selection_binding is generation.selection_binding
             and all(intent is not old for old in self.intents)
             and generation.row['policy_row'].received > self.received_base,
             'SCENARIO_SWAP_ORIGINAL_RECEIVED_INTENT_REQUIRED')
        self.intents.append(intent)
        self.result['accepted_count'] = self.ordinal
        s.stage = 'SWAP_SYNC_WAIT'  # Same request deadline includes effect/raw/UI.

    def begin(self, completed):
        if self.zero_use_tail:
            from tools.local_original_session import launcher
            s = self.scenario
            need(self.result['status'] == 'READY_RESTART' and self.ordinal == 0
                 and self.result['accepted_count'] == self.result['completed_uses'] == 0
                 and not self.intents and len(self.receipts) == len(self.raws) == len(self.ui_pairs) == 1
                 and self.identity is not None and self.identity[1] is self.initial_generation
                 and self.identity[5].accepted_count == 0 and self.identity[5]._current is None
                 and s.reselect_completed is completed and s.source_reselect['status'] == 'COMMITTED'
                 and launcher.ManualMoveRequests._source_reselect_current(self.runtime.manual) is completed,
                 'SCENARIO_SWAP_ZERO_USE_ACTUAL_RESELECT_REQUIRED')
        need(self.completed is None and self.result['completed_uses'] == self.required_uses and self.ordinal == self.required_uses,
             'SCENARIO_SWAP_RESELECT_ONCE_REQUIRED')
        self.completed = completed
        self.identity = self.receipt = None
        self.started, self.started_ns = self.scenario.reselect_started, self.scenario.reselect_started_ns
        self.scenario.stage = 'SWAP_SYNC_WAIT'

    def zero_restart_prepared(self, row, broker, manual, position):
        """Zero mode only: fresh initial UI completion, never an invented Use."""
        if not self.zero_use_tail or self.completed is not None:
            return False
        actual, runtime, session, effect, generation = self.current(row, broker)
        if not (self.saved_b_tail is False and type(self.required_uses) is int and self.required_uses == 0
                and type(self.ordinal) is int and self.ordinal == 0
                and self.result['accepted_count'] == self.result['completed_uses'] == 0
                and not self.intents and len(self.receipts) == len(self.raws) == len(self.ui_pairs) == 1
                and manual is runtime.manual is self.scenario.restart_manual
                and manual.allow_use_item is manual.consumer.allow_use_item is False
                and type(manual.sequence) is int and manual.sequence == self.scenario.INVENTORY_SEQUENCE == 1
                and not manual.pending and manual.consumer.pending is None
                and manual.consumer._readonly_pending is None
                and type(session.accepted_count) is int and session.accepted_count == 0
                and session._current is None and generation is self.initial_generation
                and generation.collection_grant is None and actual == position
                and self.receipt is runtime.item_equipment_initial
                and self.receipt == self.receipts[0] and self.raw == self.raws[0]):
            return False
        added = manual.last_result
        if not (added.get('command') == 'AddInventory' and added.get('status') == 'COMMITTED'
                and type(added.get('sequence')) is int and added['sequence'] == 1
                and added.get('phase') == 'CLIENT_CONFIRMED'
                and added.get('proof_scope') == 'CLIENT_ITEM_ROWS_SCALARS_ONLY'
                and added.get('client_inventory') == 'ROWS_5_SCALARS_MATCHED'
                and type(added.get('item_count')) is int and added['item_count'] == 2):
            return False
        receipt_valid(self.receipt, position=actual, items=self.items, initial=True, after=self.items[1].identifier)
        state = effect.store.restore(actual.uid, generation.current_frame)
        if not (state.weapon_uid == self.items[1].identifier and state.item_uid == self.items[0].identifier
                and state.revision == self.receipt['after_revision'] and raw_valid(self.raw, self.receipt, actual)
                and self.open is not None and self.open.get('status') == 'RETURNED'
                and self.open.get('invoked') is self.open.get('opened') is True
                and self.open.get('before_own_visible') is False and self.open.get('after_own_visible') is True):
            return False
        pair = self.ui_pairs[0]
        if type(pair) is not list or len(pair) != 2:
            return False
        previous_seq, previous_query = self.open['native_sequence'], self.open['query_started_monotonic_ns']
        for item, value in zip(self.items, pair):
            if not (value.get('status') == 'OBSERVED' and type(value.get('reason')) is int and value['reason'] == 0
                    and value.get('invoked') is False and value.get('observed') is True
                    and value.get('cleanup_required') is False
                    and value.get('model_uid') == value.get('item_identifier') == item.identifier
                    and value.get('model_d4') is (item.identifier == self.items[1].identifier)
                    and value['native_sequence'] > previous_seq
                    and value['query_started_monotonic_ns'] > previous_query):
                return False
            self.scenario._restore_source(value, actual, item.identifier, self.open_started_ns)
            previous_seq, previous_query = value['native_sequence'], value['query_started_monotonic_ns']
        return previous_seq == self.last_sequence and previous_query == self.last_query

    def restart_prepared(self, manual, position):
        if self.zero_use_tail:
            return False  # Zero requires the explicit row/broker source path above.
        s = self.scenario
        return (self.completed is None and self.result['completed_uses'] == self.required_uses and self.ordinal == self.required_uses
                and len(self.intents) == self.required_uses and len(self.ui_pairs) == self.required_uses + 1
                and manual.sequence == self.required_uses + 1
                and self.receipt is not None and self.receipt['after_weapon_uid'] == self.items[1].identifier
                and self.raw is not None and raw_valid(self.raw, self.receipt, position))

    def tick(self, row, broker):
        s = self.scenario
        need(s.clock() - self.started < 15, 'SCENARIO_SWAP_OBSERVATION_EXPIRED')
        if s.stage == 'SWAP_SYNC_WAIT': self.collect_sync(row, broker)
        elif s.stage == 'SWAP_OPEN_WAIT': self.collect_open(row, broker)
        elif s.stage == 'SWAP_UI_WAIT': self.collect_ui(row, broker)
        elif s.stage == 'SWAP_USE_READY': self.submit_use(row, broker)
        elif s.stage == 'SWAP_USE_WAIT': self.collect_use(row, broker)
        else: need(False, 'SCENARIO_SWAP_PHASE_REQUIRED')

    def detail(self):
        return dict(schema='manual-item-equipment-swap-observation-v1', result=self.result,
                    receipts=self.receipts, raw=self.raws, ui_pairs=self.ui_pairs, current_open=self.open)
