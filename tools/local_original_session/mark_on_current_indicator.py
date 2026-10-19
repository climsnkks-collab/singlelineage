"""Opt-in current normal-caller primitives. No request, Native query or ownership."""
from types import MethodType
from tools.local_original_session import commands, observe, item_equipment_ui as ui, inventory_ui_open as op, mark_on_install as install

need = observe.need
CURRENT = ui.ItemEquipmentUIObserver._current
OPEN_CURRENT = op.InventoryUIOpen._current
OPEN_OBSERVATION = op.InventoryUIOpen.observation
INSTALL_CURRENT = install.InstallMarkOnCaller._current
INSTALL_OBSERVATION = install.InstallMarkOnCaller.observation
ACTION_SCHEMA = 'own-mark-on-action-result-v1'
CALLER_SCHEMA = 'own-mark-on-normal-caller-v2'
IMAGE_SIZE = 0x3e97000
RECEIVER_STAGES = tuple(range(1,17)) + tuple(range(101,117))
RECEIVER_RVA_STAGES = (3,5,6,9,103,105,106,109)
CALLSITE, RETURN_SITE = 0xC05D97, 0xC05D9A
MAX_FILES = 64


def empty(reason):
    return dict(status='UNKNOWN', reason=reason, mark_own_visible=None,
                callback_qpc=None, callback_qpc_frequency=None, action_command=None, action_seq=None,
                proof_scope='NORMAL_CALLER_ONLY_NOT_POST_EFFECT_UI_QUERY')


def caller_empty(reason):
    return dict(empty(reason), native_status=None, native_reason=None,
                receiver_stage=None, receiver_rva=None)


class MarkOnCurrentIndicator:
    def __init__(self, observer, installer, opener):
        need(type(observer) is ui.ItemEquipmentUIObserver and type(installer) is install.InstallMarkOnCaller
             and type(opener) is op.InventoryUIOpen and observer.manual is installer.manual is opener.manual,
             'MARK_ON_ACTUAL_CONSUMERS_REQUIRED')
        self.observer, self.installer, self.opener = observer, installer, opener
        self._caller_key = self._caller_life = self._caller_clock = None
        self._closed = False
        self._actions = {}
        self.caller = caller_empty('MARK_ON_NOT_CONSUMED')
        self.open = empty('MARK_ON_NOT_CONSUMED')
        self.use = empty('MARK_ON_NOT_CONSUMED')

    def _current(self):
        observer, installer = self.observer, self.installer
        need(not self._closed and not observer._closed and not observer._terminal,
             'MARK_ON_CURRENT_OBSERVER_REQUIRED')
        method = observer._current
        need(type(method) is MethodType and method.__self__ is observer and method.__func__ is CURRENT
             and type(observer)._current is CURRENT, 'MARK_ON_ORIGINAL_CURRENT_REQUIRED')
        current, life = CURRENT(observer)
        method = installer._current
        need(type(method) is MethodType and method.__self__ is installer
             and method.__func__ is INSTALL_CURRENT and type(installer)._current is INSTALL_CURRENT,
             'MARK_ON_ORIGINAL_INSTALL_CURRENT_REQUIRED')
        value = INSTALL_OBSERVATION(installer)
        need(value['status'] == 'RETURNED' and value['reason'] == 0 and value['invoked'] is True
             and value['installed'] is True and value['cleanup_required'] is False,
             'MARK_ON_INSTALL_SUCCESS_REQUIRED')
        need(installer._life is not None and observer._same(installer._life, life),
             'MARK_ON_INSTALLED_LIFE_CHANGED')
        return current, life

    def _clock(self, tick, frequency):
        now, actual_frequency = install.clock_pair()
        need(type(tick) is int and 0 < tick < (1 << 64) and type(frequency) is int
             and frequency > 0 and frequency == actual_frequency == self.installer.dispatch_qpc_frequency
             and type(self.installer.dispatch_qpc) is int and self.installer.dispatch_qpc <= tick <= now,
             'MARK_ON_QPC_IDENTITY_REQUIRED')
        need((now - tick) * 1_000_000_000 < install.m.WAIT_NS * frequency,
             'MARK_ON_CALLBACK_EXPIRED')

    def consume_action(self, command, native_sequence, primary):
        # The caller passes an actual old primary cache, never an expected bool.
        result = empty('MARK_ON_ACTION_UNKNOWN')
        try:
            need(command in ('OpenInventoryUI', 'UseItemAlreadyOpen') and type(native_sequence) is int
                 and 0 < native_sequence <= install.m.MAX_SEQUENCE, 'MARK_ON_ACTION_ID_REQUIRED')
            current, life = self._current()
            key = (command, native_sequence)
            if key in self._actions:
                previous, saved = self._actions[key]
                need(self.observer._same(previous, life), 'MARK_ON_ACTION_LIFE_CHANGED')
                return dict(saved)
            self._actions[key] = (life, result)  # At most one read; no publication wait/retry.
            if command == 'OpenInventoryUI':
                method = self.opener._current
                need(type(method) is MethodType and method.__self__ is self.opener
                     and method.__func__ is OPEN_CURRENT and type(self.opener)._current is OPEN_CURRENT,
                     'MARK_ON_ORIGINAL_OPEN_CURRENT_REQUIRED')
                actual = OPEN_OBSERVATION(self.opener)
                need(type(primary) is dict and set(primary) == set(actual)
                     and all(type(primary[k]) is type(v) and primary[k] == v for k,v in actual.items()),
                     'MARK_ON_ACTUAL_OPEN_PRIMARY_REQUIRED')
                need(type(primary) is dict and primary.get('status') == 'RETURNED'
                     and primary.get('reason') == 0 and type(primary.get('reason')) is int
                     and primary.get('invoked') is True and primary.get('opened') is True
                     and primary.get('cleanup_required') is False and primary.get('native_sequence') == native_sequence,
                     'MARK_ON_OPEN_PRIMARY_REQUIRED')
                source = {'source_pid':current[6]['pid'], 'source_birth':current[6]['birth'],
                          'source_image_sha256':current[6]['candidate_sha256'],
                          'player_uid':current[3].uid,'item_identifier':life[6],'map_id':current[3].map_id}
                need(all(type(primary.get(k)) is type(v) and primary[k] == v for k,v in source.items()),
                     'MARK_ON_OPEN_PRIMARY_SOURCE_REQUIRED')
            else:
                manual = self.observer.manual
                need(primary is manual.last_result and primary.get('command') == 'UseItem'
                     and primary.get('status') == 'COMMITTED' and primary.get('native_attempted') is True
                     and primary.get('cleanup_required') is False
                     and manual._actual_action_sequence(manual.consumer)
                     and manual.consumer._action_sequence == native_sequence,
                     'MARK_ON_USE_PRIMARY_REQUIRED')
            expected = dict(schema=ACTION_SCHEMA, **current[6], seq=native_sequence, command=command,
                            player_uid=current[3].uid,item_identifier=life[6],map_id=current[3].map_id)
            row = commands._json(current[5] / ('mark-on-action-result-' + str(native_sequence) + '.json'), 2048)
            fields = {'mark_own_visible', 'callback_qpc', 'callback_qpc_frequency'}
            need(type(row) is dict and set(row) == set(expected) | fields
                 and all(type(row[k]) is type(v) and row[k] == v for k,v in expected.items()),
                 'MARK_ON_ACTION_ECHO_REQUIRED')
            need(type(row['mark_own_visible']) is bool, 'MARK_ON_ACTION_UNOBSERVED')
            self._clock(row['callback_qpc'],row['callback_qpc_frequency'])
            _, after = self._current()
            need(self.observer._same(life,after),'MARK_ON_POST_LIFE_CHANGED')
            result = dict(status='OBSERVED',reason='MARK_ON_ACTION_CALLBACK_BOUND',
                          mark_own_visible=row['mark_own_visible'],callback_qpc=row['callback_qpc'],
                          callback_qpc_frequency=row['callback_qpc_frequency'],
                          action_command=command,action_seq=native_sequence,
                          proof_scope='ACTION_CALLBACK_ONLY_NOT_POST_EFFECT_UI_QUERY')
        except Exception as error:
            result = empty(observe.reason(error))
        if command in ('OpenInventoryUI','UseItemAlreadyOpen') and type(native_sequence) is int:
            if (command,native_sequence) in self._actions:
                self._actions[(command,native_sequence)] = (self._actions[(command,native_sequence)][0],result)
        if command == 'OpenInventoryUI':self.open = dict(result)
        else:self.use = dict(result)
        return dict(result)

    def consume_caller(self):
        # One bounded final-file enumeration in the existing explicit flow.
        # Native v2 claims independent work/publication only within its one-shot
        # 15s install window and <=2Hz (<=30 final files). The original 64-file
        # defense remains; never skip an invalid latest file or lift that bound.
        # Native writes pending/flush/close then nonreplace-renames final JSON.
        diagnostic = {}
        try:
            current, life = self._current()
            files = []
            for path in current[5].glob('mark-on-normal-caller-*.json'):
                files.append(path)
                need(len(files) <= MAX_FILES,'MARK_ON_FILE_BOUND')
            need(files,'MARK_ON_CALLER_ABSENT')
            expected_fields = {'schema','pid','birth','candidate_sha256','callback_qpc','callback_qpc_frequency',
                'source_callsite_rva','source_return_rva','item_identifier','status','reason',
                'mark_own_visible','action_command','action_seq','receiver_stage','receiver_rva'}
            # Read only the latest real timestamp file. No choosing around an
            # invalid/wrong-source result or retrying an earlier candidate.
            def timestamp(path):
                text = path.name[len('mark-on-normal-caller-'):-len('.json')]
                need(text.isascii() and text.isdecimal() and not text.startswith('0'), 'MARK_ON_FILENAME_REQUIRED')
                return int(text)
            path = max(files,key=timestamp)
            key = path.name
            if key == self._caller_key:
                need(self._caller_life is not None and self.observer._same(self._caller_life,life),
                     'MARK_ON_CALLER_CACHE_LIFE_CHANGED')
                if self.caller.get('native_status') is not None:
                    self._clock(*self._caller_clock)
                return dict(self.caller)
            self._caller_key,self._caller_life,self._caller_clock = key,life,None
            row = commands._json(path,2048)
            need(type(row) is dict and set(row) == expected_fields and row['schema'] == CALLER_SCHEMA,
                 'MARK_ON_CALLER_SCHEMA_REQUIRED')
            need(all(type(row[k]) is type(v) and row[k] == v for k,v in current[6].items())
                 and type(row['source_callsite_rva']) is int and row['source_callsite_rva'] == CALLSITE
                 and type(row['source_return_rva']) is int and row['source_return_rva'] == RETURN_SITE
                 and row['callback_qpc'] == timestamp(path), 'MARK_ON_CALLER_SOURCE_REQUIRED')
            self._clock(row['callback_qpc'],row['callback_qpc_frequency'])
            need(type(row['status']) is str and row['status'] in ('OBSERVED','UNKNOWN')
                 and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff,
                 'MARK_ON_CALLER_TYPES_REQUIRED')
            cmd, seq = row['action_command'],row['action_seq']
            need(cmd is None and seq is None or type(cmd) is str and cmd in ('OpenInventoryUI','UseItemAlreadyOpen')
                 and type(seq) is int and 0 < seq <= install.m.MAX_SEQUENCE,'MARK_ON_CALLER_SCOPE_REQUIRED')
            stage, rva = row['receiver_stage'], row['receiver_rva']
            need(stage is None or type(stage) is int and stage in RECEIVER_STAGES,
                 'MARK_ON_RECEIVER_STAGE_REQUIRED')
            need(rva is None or type(rva) is int and 0 <= rva < IMAGE_SIZE and stage in RECEIVER_RVA_STAGES,
                 'MARK_ON_RECEIVER_RVA_REQUIRED')
            need(row['item_identifier'] is None or type(row['item_identifier']) is int
                 and 0 < row['item_identifier'] < (1 << 64), 'MARK_ON_CALLER_UID_TYPE_REQUIRED')
            need(type(row['mark_own_visible']) is bool if row['status'] == 'OBSERVED'
                 else row['mark_own_visible'] is None, 'MARK_ON_CALLER_PRIMITIVE_TYPE_REQUIRED')
            _,after = self._current()
            need(self.observer._same(life,after),'MARK_ON_POST_LIFE_CHANGED')
            # Preserve only typed, source/clock/post-current validated Native
            # diagnostics. Missing/wrong UID and Native UNKNOWN stay UNKNOWN;
            # this does not grant a Slot/model/Mark observation or ownership.
            diagnostic = dict(native_status=row['status'],native_reason=row['reason'],
                              receiver_stage=stage,receiver_rva=rva)
            self._caller_clock = (row['callback_qpc'],row['callback_qpc_frequency'])
            need(type(row['item_identifier']) is int and row['item_identifier'] == life[6],
                 'MARK_ON_CALLER_SOURCE_REQUIRED')
            need(row['status'] == 'OBSERVED' and row['reason'] == 0,
                 'MARK_ON_CALLER_UNOBSERVED')
            self.caller = dict(status='OBSERVED',reason='MARK_ON_NORMAL_CALLER_SOURCE_BOUND',
                mark_own_visible=row['mark_own_visible'],callback_qpc=row['callback_qpc'],
                callback_qpc_frequency=row['callback_qpc_frequency'],action_command=cmd,action_seq=seq,
                proof_scope='NORMAL_CALLER_ONLY_NOT_ACTION_SUCCESS_OR_POST_EFFECT_UI_QUERY',**diagnostic)
        except Exception as error:
            self.caller = caller_empty(observe.reason(error))
            self.caller.update(diagnostic)
        return dict(self.caller)

    def close(self):
        self._closed = True
        self.caller = caller_empty('MARK_ON_CLOSED')
