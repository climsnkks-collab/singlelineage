"""LOCAL character quest state and interrupted inventory/EXP turn-in saves.

Construct once before requests, after InventoryStore/ProgressStore. Equipment
anchors remain valid even when EquipmentStore is constructed before recovery.
The host's
existing world lock must serialize all participants. Quest/progress reads use
startup caches; existing inventory/equipment preflight retains its IO. An intent
is a forward recovery record, never a receipt or permission to retry a reward.
Any failed write leaves this object pending until startup recovery. No quest,
class reference step, reward, or fresh-character policy is inferred here.
"""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import threading

from tools.local_original_session import inventory, inventory_store, world_progress
from tools.local_original_session.world_quest import QuestState
from tools.local_original_session.world_warehouse import (
    _atomic_json, _atomic_raw, _equipment_raw, _json_bytes, _raw_unhex,
)

MAX_BYTES = 2_000_000
INTENT_MAX_BYTES = 2 * MAX_BYTES + 6 * inventory.KIT_MAX_FRAME + 16_384


def _need(ok, code):
    if not ok:
        raise ValueError(code)


def _uid(uid):
    _need(type(uid) is int and 0 < uid <= 0xffffffff, 'QUEST_STORE_CHARACTER_UID')
    return uid


def _name(value):
    _need(type(value) is str and bool(value), 'QUEST_STORE_NAME')
    return value


def _references(value):
    _need(type(value) is dict and all(type(v) is int and v >= 0 for v in value.values()),
          'QUEST_STORE_REFERENCE_STEPS')
    return {_name(k): v for k, v in value.items()}


def _state_row(state):
    _need(type(state) is QuestState, 'QUEST_STORE_STATE')
    _name(state.quest_id)
    _need(type(state.accepted) is bool and type(state.completed) is bool
          and (not state.completed or state.accepted)
          and type(state.counts) is tuple
          and all(type(v) is int and v >= 0 for v in state.counts)
          and type(state.seen_events) is tuple
          and all(type(v) is str and bool(v) for v in state.seen_events)
          and len(set(state.seen_events)) == len(state.seen_events)
          and type(state.cycles) is int and state.cycles >= 0
          and type(state.issued) is tuple
          and all(type(row) is tuple and len(row) == 3
                  and all(type(v) is int and v > 0 for v in row) for row in state.issued)
          and len({row[0] for row in state.issued}) == len(state.issued), 'QUEST_STORE_STATE')
    _need(type(state.closed) is bool and (not state.closed or state.completed), 'QUEST_STORE_STATE')
    row = dict(quest_id=state.quest_id, accepted=state.accepted, completed=state.completed,
               counts=list(state.counts), seen_events=list(state.seen_events))
    # V1 remains readable; optional fields preserve old saves and old intents.
    if state.cycles:
        row['cycles'] = state.cycles
    if state.issued:
        row['issued'] = [list(item) for item in state.issued]
    if state.closed:
        row['closed'] = True
    return row


def _state(value):
    required = {'quest_id', 'accepted', 'completed', 'counts', 'seen_events'}
    _need(type(value) is dict and required <= set(value) <= required | {'cycles', 'issued', 'closed'}
        and type(value['counts']) is list and type(value['seen_events']) is list,
        'QUEST_STORE_STATE_SCHEMA')
    _need(type(value.get('issued', [])) is list
          and all(type(row) is list for row in value.get('issued', [])), 'QUEST_STORE_STATE_SCHEMA')
    state = QuestState(value['quest_id'], value['accepted'], value['completed'],
                       tuple(value['counts']), tuple(value['seen_events']),
                       value.get('cycles', 0), tuple(tuple(row) for row in value.get('issued', [])),
                       value.get('closed', False))
    _state_row(state)
    return state


def _row(value):
    _need(type(value) is dict and set(value) == {'uid', 'quests', 'reference_steps'}
          and type(value['quests']) is list and type(value['reference_steps']) is dict,
          'QUEST_STORE_ROW')
    uid = _uid(value['uid'])
    quests = {}
    for raw in value['quests']:
        state = _state(raw)
        _need(state.quest_id not in quests, 'QUEST_STORE_DUPLICATE_QUEST')
        quests[state.quest_id] = _state_row(state)
    refs = {_name(key): _references(steps) for key, steps in value['reference_steps'].items()}
    return dict(uid=uid, quests=[quests[key] for key in sorted(quests)], reference_steps=refs)


def _progress(value, uid):
    if value is None:
        return None
    _need(type(value) is world_progress.Progress, 'QUEST_STORE_PROGRESS')
    _need(world_progress._valid_row(dict(uid=uid, **asdict(value))), 'QUEST_STORE_PROGRESS')
    return value


def _decode_progress(value, uid):
    if value is None:
        return None
    _need(type(value) is dict and set(value) == {'exp', 'level', 'max_hp', 'max_mp', 'lawful'},
          'QUEST_STORE_PROGRESS_SCHEMA')
    return _progress(world_progress.Progress(**value), uid)


def _frame(value):
    if value is not None:
        inventory.validate_kit_frame(value)
    return value


def _decode_frame(value):
    _need(type(value) is str, 'QUEST_STORE_FRAME_HEX')
    try:
        frame = bytes.fromhex(value)
    except ValueError:
        raise ValueError('QUEST_STORE_FRAME_HEX') from None
    _need(frame.hex() == value, 'QUEST_STORE_FRAME_HEX')
    return _frame(frame)


def _read_json(path, limit):
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    _need(len(raw) <= limit, 'QUEST_STORE_SIZE')
    return json.loads(raw, object_pairs_hook=inventory.movement._unique_object)


def _anchor_stage(before, after, old_equipment, new_equipment):
    """Keep both anchors alive until equipment can reference the final one.

    An anchor already present before needs no stage: equipment saves first.
    Otherwise keep final surviving old rows, the old anchor, and the prefix of
    new reward rows ending at the new anchor. Remaining rewards append only in
    the final CAS. No row is restored after reaching the final inventory.
    """
    old_items = inventory.validate_kit_frame(before)
    new_items = inventory.validate_kit_frame(after)
    if any(item.identifier == new_equipment.item_uid
           and item.template_bits == new_equipment.template for item in old_items):
        return None
    old_uids = {item.identifier for item in old_items}
    final = {item.identifier: item for item in new_items}
    stage = []
    for item in old_items:
        if item.identifier in final:
            stage.append(dict(final[item.identifier].raw_fields))
        elif old_equipment is not None and item.identifier == old_equipment.item_uid:
            stage.append(dict(item.raw_fields))
    for item in new_items:
        if item.identifier not in old_uids:
            stage.append(dict(item.raw_fields))
        if item.identifier == new_equipment.item_uid:
            break
    return inventory.build_kit_frame(stage)


class QuestStore:
    """One profile, one startup-loaded quest document and one short intent.

    A missing quest returns its unaccepted QuestState; missing class references
    return {}. The caller explicitly supplies any LOCAL initialization policy.
    A commit replaces one quest plus one class's reference dict and preserves
    all other quests, classes and characters. It returns after all saves only.
    """
    def __init__(self, inventory_store, progress_store):
        self.inventory_store = inventory_store
        self.progress_store = progress_store
        profile = Path(inventory_store.profile)
        _need(profile.is_absolute(), 'QUEST_STORE_ABSOLUTE_PROFILE')
        _need(Path(progress_store.path) == profile.with_name('progression.json'),
              'QUEST_STORE_PROGRESS_OWNER')
        self.path = profile.with_name('quests.json')
        self.intent_path = profile.with_name('quest-transfer.json')
        self.equipment_path = profile.with_name('equipment.json')
        self._lock = threading.RLock()
        self._pending = None
        # ProgressStore's first read belongs to startup, including an empty save.
        with world_progress._lock:
            progress_store._load()
        self._rows = self._load()
        self._recover()

    def _load(self):
        if not self.path.exists():
            return {}
        data = _read_json(self.path, MAX_BYTES)
        _need(type(data) is dict and set(data) == {'version', 'rows'}
              and type(data['version']) is int and data['version'] == 1
              and type(data['rows']) is list, 'QUEST_STORE_SCHEMA')
        rows = {}
        for raw in data['rows']:
            row = _row(raw)
            _need(row['uid'] not in rows, 'QUEST_STORE_DUPLICATE_CHARACTER')
            self.inventory_store.restore(row['uid'])  # Startup roster validation.
            rows[row['uid']] = row
        return rows

    @staticmethod
    def _document(rows):
        data = dict(version=1, rows=[row for _, row in sorted(rows.items())])
        _need(len(_json_bytes(data)) <= MAX_BYTES, 'QUEST_STORE_SIZE')
        return data

    def _write_rows(self, rows):
        _atomic_json(self.path, self._document(rows))

    def get(self, uid, quest_id):
        _uid(uid)
        _name(quest_id)
        with self._lock:
            row = self._rows.get(uid)
            return next((_state(s) for s in row['quests'] if s['quest_id'] == quest_id),
                        QuestState(quest_id)) if row else QuestState(quest_id)

    def reference_steps(self, uid, class_key):
        _uid(uid)
        _name(class_key)
        with self._lock:
            row = self._rows.get(uid)
            return dict(row['reference_steps'].get(class_key, {})) if row else {}

    def _finish(self, intent, inventory_current=None, equipment_current=None):
        uid = intent['uid']
        _need(self._rows.get(uid) in (intent['row_before'], intent['row_after']),
              'QUEST_STORE_RECOVERY_STATE_CONFLICT')
        if 'inventory_after' in intent:
            exact_frames = (intent['inventory_before'], intent['inventory_after'])
            if 'inventory_stage' in intent:
                exact_frames += (intent['inventory_stage'],)
            _need(inventory_current in exact_frames,
                  'QUEST_STORE_RECOVERY_INVENTORY_CONFLICT')
        if 'equipment_after' in intent:
            _need(equipment_current in (intent['equipment_before'], intent['equipment_after']),
                  'QUEST_STORE_RECOVERY_EQUIPMENT_CONFLICT')
        progress_current = self.progress_store._rows.get(uid)
        if 'progress_after' in intent:
            _need(progress_current in (intent['progress_before'], intent['progress_after']),
                  'QUEST_STORE_RECOVERY_PROGRESS_CONFLICT')
        # Validate every participant before the first forward write.
        if 'inventory_stage' in intent and inventory_current == intent['inventory_before']:
            self.inventory_store.replace_kit(uid, inventory_current, intent['inventory_stage'], append=True)
            inventory_current = intent['inventory_stage']
        if 'equipment_after' in intent and equipment_current != intent['equipment_after']:
            _atomic_raw(self.equipment_path, intent['equipment_after'])
        if 'inventory_after' in intent and inventory_current != intent['inventory_after']:
            self.inventory_store.replace_kit(uid, inventory_current, intent['inventory_after'], append=True)
        if 'progress_after' in intent and progress_current != intent['progress_after']:
            self.progress_store.commit(uid, intent['progress_after'])
        if self._rows.get(uid) != intent['row_after']:
            rows = dict(self._rows)
            rows[uid] = intent['row_after']
            self._write_rows(rows)
            self._rows = rows
        self.intent_path.unlink()
        self._pending = None

    def _recover(self):
        if not self.intent_path.exists():
            return
        raw = _read_json(self.intent_path, INTENT_MAX_BYTES)
        base = {'version', 'uid', 'row_before', 'row_after'}
        ikeys = {'inventory_before', 'inventory_after'}
        pkeys = {'progress_before', 'progress_after'}
        ekeys = {'equipment_before', 'equipment_after'}
        stage_keys = {'inventory_stage'}
        _need(type(raw) is dict and base <= set(raw) <= base | ikeys | pkeys | ekeys | stage_keys
              and all(not (keys & raw.keys()) or keys <= raw.keys() for keys in (ikeys, pkeys, ekeys))
              and (not ekeys <= raw.keys() or ikeys <= raw.keys())
              and (not stage_keys <= raw.keys() or ikeys | ekeys <= raw.keys())
              and type(raw['version']) is int and raw['version'] == 1, 'QUEST_STORE_INTENT_SCHEMA')
        uid = _uid(raw['uid'])
        intent = dict(uid=uid, row_before=None if raw['row_before'] is None else _row(raw['row_before']),
                      row_after=_row(raw['row_after']))
        _need(intent['row_after']['uid'] == uid
              and (intent['row_before'] is None or intent['row_before']['uid'] == uid),
              'QUEST_STORE_INTENT_CHARACTER')
        if ikeys <= raw.keys():
            intent.update({key: _decode_frame(raw[key]) for key in ikeys})
        if stage_keys <= raw.keys():
            intent['inventory_stage'] = _decode_frame(raw['inventory_stage'])
        if pkeys <= raw.keys():
            intent.update({key: _decode_progress(raw[key], uid) for key in pkeys})
            _need(intent['progress_after'] is not None, 'QUEST_STORE_PROGRESS_AFTER')
        if ekeys <= raw.keys():
            intent.update({key: _raw_unhex(raw[key]) for key in ekeys})
            _need(intent['equipment_after'] is not None, 'QUEST_STORE_EQUIPMENT_AFTER_REQUIRED')
        self._pending = intent
        with inventory_store._lock, inventory_store.realm._lock:
            # Recovery is startup-only; restore must never be added to commit.
            current = self.inventory_store.restore(uid)
            self._finish(intent, current,
                         _equipment_raw(self.equipment_path) if ekeys <= raw.keys() else None)

    def commit(self, uid, quest_before, quest_after, *, class_key,
               reference_before, reference_after, inventory_before=None,
               inventory_after=None, progress_before=None, progress_after=None,
               equipment_store=None, equipment_before=None, equipment_after=None):
        """Persist one host-approved transition; uncertain writes require restart.

        Optional inventory/Progress participants must be supplied as both before
        and after. A missing saved Progress is compared with Progress(0, 1), and
        its actual absence is retained in the recovery preimage. Optional equipment
        uses warehouse's existing preflight and whole-document before/after bytes;
        it saves before final inventory and Progress. When its new anchor is a
        fresh reward, a minimal inventory stage keeps both anchors alive first.
        No rollback or
        live recovery occurs after an exception, even for an uncertain intent IO.
        """
        _uid(uid)
        old_state, new_state = _state_row(quest_before), _state_row(quest_after)
        _need(quest_before.quest_id == quest_after.quest_id, 'QUEST_STORE_QUEST_IDENTITY')
        _name(class_key)
        old_refs, new_refs = _references(reference_before), _references(reference_after)
        _need((inventory_before is None) == (inventory_after is None), 'QUEST_STORE_INVENTORY_PAIR')
        _frame(inventory_before)
        _frame(inventory_after)
        _need((progress_before is None) == (progress_after is None), 'QUEST_STORE_PROGRESS_PAIR')
        _progress(progress_before, uid)
        _progress(progress_after, uid)
        with self._lock, inventory_store._lock, inventory_store.realm._lock:
            _need(self._pending is None, 'QUEST_STORE_RECOVERY_REQUIRED')
            _need(self.get(uid, quest_before.quest_id) == quest_before, 'QUEST_STORE_EXPECTED_STATE_CHANGED')
            _need(self.reference_steps(uid, class_key) == old_refs, 'QUEST_STORE_EXPECTED_REFERENCE_CHANGED')
            current_progress = self.progress_store._rows.get(uid)
            if progress_before is not None:
                _need((current_progress if current_progress is not None else world_progress.Progress(0, 1))
                      == progress_before, 'QUEST_STORE_EXPECTED_PROGRESS_CHANGED')
            old_row = self._rows.get(uid)
            quests = {s['quest_id']: s for s in old_row['quests']} if old_row else {}
            quests[quest_after.quest_id] = new_state
            refs = dict(old_row['reference_steps']) if old_row else {}
            if new_refs:
                refs[class_key] = new_refs
            else:
                refs.pop(class_key, None)
            new_row = dict(uid=uid, quests=[quests[key] for key in sorted(quests)], reference_steps=refs)
            rows = dict(self._rows)
            rows[uid] = new_row
            self._document(rows)  # Refuse oversize proposals before creating intent.
            intent = dict(uid=uid, row_before=old_row, row_after=new_row)
            if inventory_before is not None:
                intent.update(inventory_before=inventory_before, inventory_after=inventory_after)
            if progress_before is not None:
                intent.update(progress_before=current_progress, progress_after=progress_after)
            equipment_current = None
            if equipment_store is not None:
                # Same preflight and exact whole-document preimage as warehouse.
                from tools.local_original_session import equipment_store as equipment
                _need(inventory_before is not None, 'QUEST_STORE_EQUIPMENT_INVENTORY_REQUIRED')
                _need(type(equipment_store) is equipment.EquipmentStore
                      and equipment_store.inventory_store is self.inventory_store
                      and equipment_store.path == self.equipment_path, 'QUEST_STORE_EQUIPMENT_OWNER')
                equipment_rows, frames, known = equipment_store._read()
                _need(equipment_rows.get(uid) == equipment_before and frames.get(uid) == inventory_before,
                      'QUEST_STORE_EXPECTED_EQUIPMENT_CHANGED')
                _need(type(equipment_after) is equipment.EquipmentState
                      and equipment_after.character_uid == uid, 'QUEST_STORE_EQUIPMENT_AFTER_REQUIRED')
                def validate_equipment(state, candidate_frames):
                    if equipment_store._kit is not None:
                        equipment_store._kit_state(equipment._row(state), known,
                                                   candidate_frames, equipment_store._kit)
                    else:
                        equipment_store._state(equipment._row(state), known, candidate_frames,
                                               collection_policy=equipment_store._collection_policy)
                changed_frames = dict(frames)
                changed_frames[uid] = inventory_after
                validate_equipment(equipment_after, changed_frames)
                equipment_current = _equipment_raw(self.equipment_path)
                old_document = dict(version=1, policy=equipment.POLICY,
                    equipment=[equipment._row(value) for _, value in sorted(equipment_rows.items())])
                _need((equipment_current is None and not equipment_rows)
                      or json.loads(equipment_current) == old_document,
                      'QUEST_STORE_EXPECTED_EQUIPMENT_CHANGED')
                equipment_rows[uid] = equipment_after
                equipment_new = _json_bytes(dict(version=1, policy=equipment.POLICY,
                    equipment=[equipment._row(value) for _, value in sorted(equipment_rows.items())]))
                _need(len(equipment_new) <= equipment_store.MAX_BYTES, 'QUEST_STORE_EQUIPMENT_SIZE')
                intent.update(equipment_before=equipment_current, equipment_after=equipment_new)
                stage = _anchor_stage(inventory_before, inventory_after,
                                      equipment_before, equipment_after)
                if stage is not None:
                    stage_frames = dict(frames)
                    stage_frames[uid] = stage
                    if equipment_before is not None:
                        validate_equipment(equipment_before, stage_frames)
                    validate_equipment(equipment_after, stage_frames)
                    intent['inventory_stage'] = stage
                else:
                    validate_equipment(equipment_after, frames)
            else:
                _need(equipment_before is None and equipment_after is None, 'QUEST_STORE_EQUIPMENT_OWNER')
            if (old_state == new_state and old_refs == new_refs
                    and inventory_before == inventory_after and progress_before == progress_after
                    and ('equipment_after' not in intent
                         or intent['equipment_before'] == intent['equipment_after'])):
                return False
            encoded = dict(version=1, **intent)
            if inventory_before is not None:
                encoded.update(inventory_before=inventory_before.hex(), inventory_after=inventory_after.hex())
            if 'inventory_stage' in intent:
                encoded['inventory_stage'] = intent['inventory_stage'].hex()
            if progress_before is not None:
                encoded.update(progress_before=None if current_progress is None else asdict(current_progress),
                               progress_after=asdict(progress_after))
            if 'equipment_after' in intent:
                encoded.update(equipment_before=None if equipment_current is None else equipment_current.hex(),
                               equipment_after=intent['equipment_after'].hex())
            self._pending = intent
            _atomic_json(self.intent_path, encoded)
            self._finish(intent, inventory_before, equipment_current)
            return True
