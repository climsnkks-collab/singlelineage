"""Optional same-operation scalar sidecar. No Native request/query/ownership."""
from types import MethodType
from tools.local_original_session import commands, observe, item_equipment_ui as ui

RESULT = 'own-item-equipment-ui-lookup-role-result-v1'
_CURRENT = ui.ItemEquipmentUIObserver._current
need = observe.need


def _empty(reason):
    return dict(status='UNKNOWN', reason=reason, named_lookup_known=None,
                native_sequence=None, query_started_monotonic_ns=None)


class SelectedSlotLookupRole:
    def __init__(self, observer):
        need(type(observer) is ui.ItemEquipmentUIObserver, 'UI_ROLE_ORIGINAL_OBSERVER_REQUIRED')
        self.observer = observer
        self._key = self._life = None
        self._closed = False
        self.last_result = _empty('UI_ROLE_NOT_OBSERVED')

    def consume(self, value):
        """Read at most once per completed original UI seq. Failure stays data UNKNOWN."""
        try:
            observer = self.observer
            need(not self._closed and not observer._closed and not observer._terminal,
                 'UI_ROLE_OBSERVER_NOT_CURRENT')
            method = observer._current
            need(type(method) is MethodType and method.__self__ is observer
                 and method.__func__ is _CURRENT and type(observer)._current is _CURRENT,
                 'UI_ROLE_ORIGINAL_CURRENT_REQUIRED')
            actual = observer.last_result  # Read cache only; never rewrite original UI outcome.
            need(type(value) is dict and set(value) == set(actual)
                 and all(type(value[k]) is type(v) and value[k] == v for k, v in actual.items()),
                 'UI_ROLE_ACTUAL_OBSERVATION_REQUIRED')
            need(value['status'] == 'OBSERVED' and value['reason'] == 0
                 and type(value['reason']) is int and value['invoked'] is False
                 and value['observed'] is True and value['cleanup_required'] is False
                 and type(value['model_uid']) is int and value['model_uid'] == value['item_identifier']
                 and type(value['model_d4']) is bool,
                 'UI_ROLE_OBSERVED_UI_REQUIRED')
            need(type(value['native_sequence']) is int and value['native_sequence'] > 0
                 and type(value['query_started_monotonic_ns']) is int
                 and value['query_started_monotonic_ns'] > 0, 'UI_ROLE_ORIGINAL_QUERY_REQUIRED')
            current, life = _CURRENT(observer)
            need(observer._life is not None and observer._same(observer._life, life),
                 'UI_ROLE_CURRENT_LIFE_REQUIRED')
            expected = dict(schema=RESULT, **current[6], seq=value['native_sequence'],
                command=ui.COMMAND, player_uid=current[3].uid,
                item_identifier=life[6], map_id=current[3].map_id)
            need(all(type(value[k]) is type(v) and value[k] == v for k, v in {
                'source_pid': expected['pid'], 'source_birth': expected['birth'],
                'source_image_sha256': expected['candidate_sha256'],
                'player_uid': expected['player_uid'], 'item_identifier': expected['item_identifier'],
                'map_id': expected['map_id']}.items()), 'UI_ROLE_CURRENT_SOURCE_REQUIRED')
            key = (value['native_sequence'], value['query_started_monotonic_ns'])
            if self._key == key:
                need(self._life is not None and observer._same(self._life, life),
                     'UI_ROLE_CACHE_LIFE_CHANGED')
                return dict(self.last_result)
            self._key, self._life = key, life  # One file consumption, no independent wait/retry.
            row = commands._json(current[5] / ('item-equipment-ui-lookup-role-result-'
                                               + str(key[0]) + '.json'), 2048)
            need(type(row) is dict and set(row) == set(expected) | {'named_lookup_known'}
                 and all(type(row[k]) is type(v) and row[k] == v for k, v in expected.items()),
                 'UI_ROLE_REPLY_IDENTITY_REQUIRED')
            need(type(row['named_lookup_known']) is bool, 'UI_ROLE_PRIMITIVE_UNKNOWN')
            # No more file read. Original current lifetime must still agree after collection.
            _, after = _CURRENT(observer)
            need(observer._same(life, after) and observer._same(observer._life, after),
                 'UI_ROLE_POST_CURRENT_CHANGED')
            self.last_result = dict(status='OBSERVED', reason='UI_ROLE_SAME_OPERATION_BOUND',
                named_lookup_known=row['named_lookup_known'], native_sequence=key[0],
                query_started_monotonic_ns=key[1])
        except Exception as error:
            self.last_result = _empty(observe.reason(error))
        return dict(self.last_result)

    def close(self):
        self._closed = True
        self.last_result = _empty('UI_ROLE_CLOSED')
