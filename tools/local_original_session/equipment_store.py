"""Explicit local Athame equipment state, separate from opaque inventory bytes.

No live account/selection/once/notify authority is produced here. The broker must
bind the current writer/generation and drain initial state before using it.
"""
from dataclasses import dataclass,replace,asdict
import json
import os
from pathlib import Path
import stat
import uuid
from tools.local_original_session import inventory,inventory_store
from tools.local_character_creation import realm

POLICY='LOCAL_ATHAME137_EQUIPMENT_SIDECAR_V1'
FIRST_ENABLE_EMPTY='EXPLICIT_LOCAL_FIRST_ENABLE_EMPTY'
COLLECTION_POLICY='EXPLICIT_LOCAL_OWNED_ATHAME_COLLECTION'
need=inventory.need

@dataclass(frozen=True,slots=True)
class EquipmentState:
    character_uid:int
    item_uid:int
    template:int
    weapon_uid:int
    revision:int


def _frame_items(frame,collection_policy):
    if collection_policy is None:return (inventory.validate_frame(frame),)
    need(type(collection_policy) is str and collection_policy==COLLECTION_POLICY,
         'EQUIPMENT_COLLECTION_EXPLICIT_POLICY_REQUIRED')
    return inventory.validate_collection_frame(frame,policy=inventory.COLLECTION_POLICY)

def _weapon_uids(items):
    return (0,)+tuple(item.identifier for item in items if item.template_bits==1)

class EquipmentStore:
    MAX_BYTES=4096
    def __init__(self,store,*,policy,collection_policy=None):
        need(type(store) is inventory_store.InventoryStore,'EQUIPMENT_REAL_INVENTORY_STORE_REQUIRED')
        need(type(policy) is str and policy==POLICY,'EQUIPMENT_EXPLICIT_POLICY_REQUIRED')
        need(collection_policy is None or (type(collection_policy) is str and
             collection_policy==COLLECTION_POLICY),'EQUIPMENT_COLLECTION_EXPLICIT_POLICY_REQUIRED')
        if collection_policy is not None:
            need(store._collection_policy==inventory_store.COLLECTION_STORE_POLICY,
                 'EQUIPMENT_COLLECTION_INVENTORY_POLICY_REQUIRED')
        self._collection_policy=collection_policy
        self.inventory_store=store
        self.profile=Path(store.profile);self.path=self.profile.with_name('equipment.json')
        self._profile=self.profile;self._inventory_path=Path(store.path);self._path=self.path
        with inventory_store._lock,realm._lock:self._read()

    def _paths(self):
        need(self.profile==self._profile and self.path==self._path and
             self.inventory_store.profile==self._profile and self.inventory_store.path==self._inventory_path,
             'EQUIPMENT_STORE_BINDING_CHANGED')
        need(self._collection_policy is None or (type(self._collection_policy) is str and
             self._collection_policy==COLLECTION_POLICY and
             self.inventory_store._collection_policy==inventory_store.COLLECTION_STORE_POLICY),
             'EQUIPMENT_COLLECTION_INVENTORY_POLICY_REQUIRED')
        inventory_store.InventoryStore._path_check(self.inventory_store)
        for part in (self.path,*self.path.parents):
            if not os.path.lexists(part):continue
            info=part.lstat()
            need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,
                 'EQUIPMENT_REPARSE_REFUSED')
            if part==self.path:
                need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'EQUIPMENT_REGULAR_SINGLE_FILE_REQUIRED')

    @staticmethod
    def _state(row,known,frames,*,collection_policy=None):
        need(type(row) is dict and set(row)=={'character_uid','item_uid','template','weapon_uid','revision'},
             'EQUIPMENT_ROW_SCHEMA')
        need(all(type(value) is int for value in row.values()),'EQUIPMENT_EXACT_INTEGER_REQUIRED')
        state=EquipmentState(**row)
        need(0<state.character_uid<1<<32 and state.character_uid in known,'EQUIPMENT_CHARACTER_NOT_CURRENT')
        supported=(0,state.item_uid) if collection_policy is None else range(1<<32)
        need(0<state.item_uid<1<<32 and state.template==1 and state.weapon_uid in supported and
             0<state.revision<1<<64,'EQUIPMENT_ROW_RANGE')
        frame=frames.get(state.character_uid)
        need(type(frame) is bytes,'EQUIPMENT_EXISTING_INVENTORY_ROW_REQUIRED')
        items=_frame_items(frame,collection_policy)
        item=items[0] # Existing first-instance anchor, never the selected weapon.
        if collection_policy is not None:
            need(state.weapon_uid in _weapon_uids(items),'EQUIPMENT_SUPPORTED_WEAPON_REQUIRED')
        need(item.identifier==state.item_uid and item.template_bits==state.template,'EQUIPMENT_ITEM_BINDING_CHANGED')
        return state

    def _read(self):
        self._paths()
        frames,known=inventory_store.InventoryStore._read(self.inventory_store)
        if not self.path.exists():return {},frames,known
        with self.path.open('rb') as stream:
            need(os.fstat(stream.fileno()).st_size<=self.MAX_BYTES,'EQUIPMENT_STORE_SIZE')
            raw=stream.read(self.MAX_BYTES+1)
        need(len(raw)<=self.MAX_BYTES,'EQUIPMENT_STORE_SIZE')
        try:data=json.loads(raw,object_pairs_hook=inventory.movement._unique_object)
        except (ValueError,UnicodeError):raise ValueError('EQUIPMENT_STORE_JSON') from None
        need(type(data) is dict and set(data)=={'version','policy','equipment'} and
             type(data['version']) is int and data['version']==1 and data['policy']==POLICY and
             type(data['equipment']) is list and len(data['equipment'])<=realm.MAX_CHARACTERS,
             'EQUIPMENT_STORE_SCHEMA')
        restored={}
        for row in data['equipment']:
            state=self._state(row,known,frames,collection_policy=self._collection_policy)
            need(state.character_uid not in restored,'EQUIPMENT_DUPLICATE_CHARACTER')
            restored[state.character_uid]=state
        return restored,frames,known

    def _current(self,character_uid,expected_frame,frames,known):
        inventory_store._uid(character_uid)
        need(character_uid in known,'EQUIPMENT_CHARACTER_NOT_CURRENT')
        need(type(expected_frame) is bytes and frames.get(character_uid)==expected_frame,
             'EQUIPMENT_EXPECTED_INVENTORY_CHANGED')
        item=_frame_items(expected_frame,self._collection_policy)[0]
        need(item.template_bits==1,'EQUIPMENT_TEMPLATE1_MAPPING_REQUIRED')
        return item

    def _write(self,rows):
        values=[asdict(rows[uid]) for uid in sorted(rows)]
        raw=(json.dumps(dict(version=1,policy=POLICY,equipment=values),separators=(',',':'))+'\n').encode('ascii')
        need(len(raw)<=self.MAX_BYTES,'EQUIPMENT_STORE_SIZE')
        temporary=self.path.with_name('.equipment-'+uuid.uuid4().hex+'.tmp');created=False
        try:
            self._paths()
            with temporary.open('xb') as stream:
                created=True
                need(stream.write(raw)==len(raw),'EQUIPMENT_STORE_PARTIAL_WRITE')
                stream.flush();os.fsync(stream.fileno())
            self._paths();os.replace(temporary,self.path)
        finally:
            if created and temporary.exists():temporary.unlink()

    def restore(self,character_uid,expected_frame):
        with inventory_store._lock,realm._lock:
            rows,frames,known=self._read();self._current(character_uid,expected_frame,frames,known)
            return rows.get(character_uid) # Missing is unknown, NOT empty.

    def owned_items(self,character_uid,expected_frame):
        """Actual locked Store/frame members. No selected/live/transport authority."""
        need(self._collection_policy==COLLECTION_POLICY,'EQUIPMENT_COLLECTION_EXPLICIT_POLICY_REQUIRED')
        with inventory_store._lock,realm._lock:
            _,frames,known=self._read()
            self._current(character_uid,expected_frame,frames,known)
            return _frame_items(expected_frame,self._collection_policy)

    def initialize_empty(self,character_uid,expected_frame,*,initialization):
        need(type(initialization) is str and initialization==FIRST_ENABLE_EMPTY,'EQUIPMENT_EXPLICIT_FIRST_ENABLE_REQUIRED')
        with inventory_store._lock,realm._lock:
            rows,frames,known=self._read();item=self._current(character_uid,expected_frame,frames,known)
            existing=rows.get(character_uid)
            if existing is not None:return existing # Never reset restored equipment.
            state=EquipmentState(character_uid,item.identifier,1,0,1)
            rows[character_uid]=state;self._write(rows);return state

    def compare_and_swap(self,character_uid,expected_frame,expected,weapon_uid):
        need(type(expected) is EquipmentState,'EQUIPMENT_EXACT_EXPECTED_STATE_REQUIRED')
        with inventory_store._lock,realm._lock:
            rows,frames,known=self._read();item=self._current(character_uid,expected_frame,frames,known)
            need(expected.character_uid==character_uid and expected.item_uid==item.identifier and
                 expected.template==1 and rows.get(character_uid)==expected,'EQUIPMENT_EXPECTED_STATE_CHANGED')
            supported=((0,item.identifier) if self._collection_policy is None else
                       _weapon_uids(_frame_items(expected_frame,self._collection_policy)))
            need(type(weapon_uid) is int and weapon_uid in supported,'EQUIPMENT_SUPPORTED_WEAPON_REQUIRED')
            need(weapon_uid!=expected.weapon_uid,'EQUIPMENT_ACTUAL_CHANGE_REQUIRED')
            need(expected.revision<(1<<64)-1,'EQUIPMENT_REVISION_CAPACITY')
            new=replace(expected,weapon_uid=weapon_uid,revision=expected.revision+1)
            rows[character_uid]=new;self._write(rows);return new
