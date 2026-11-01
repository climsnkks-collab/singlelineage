"""Optional Lv51 bonus allocation and permanent elixirs; see BONUS_STATS.md.

Wire enum/schema and bonus notification come from preserved run395 static
analysis. Level entitlement/caps/+1 elixir are attributed L1J LOCAL policy.
"""
from __future__ import annotations

from tools.local_original_session import inventory
from tools.local_original_session.world_bridge import need

RAISE, BONUS = 0x4F10, 0x4F0F
# Native StatAttr, distinct from saved creation order STR/DEX/CON/WIS/CHA/INT.
ATTR_INFO = (11, 16, 14, 12, 13, 15)
ELIXIRS = {895: 0, 896: 3, 897: 4, 898: 1, 899: 2, 900: 5}
ELIXIR_NAMES = ('엘릭서(STR)', '엘릭서(DEX)', '엘릭서(CON)',
                '엘릭서(INT)', '엘릭서(WIS)', '엘릭서(CHA)')
ELIXIR_ICONS = (1143, 1140, 1141, 1142, 1144, 1139)
ZERO = (0,) * 6


def available(level, allocated):
    return max(0, level - 50 - sum(allocated))


def increase(level, base, bonus, attribute, *, elixir=False):
    """Pure LOCAL backend rule; base excludes gear/buffs, includes prior growth."""
    need(type(attribute) is int and 0 <= attribute < 6, 'BONUS_STAT_ATTRIBUTE')
    allocated, elixirs = bonus
    need(base[attribute] < 35, 'BONUS_STAT_CAP')
    if elixir:
        need(level >= 50, 'ELIXIR_LEVEL_REQUIRED')
        need(sum(elixirs) < 5, 'ELIXIR_COUNT_CAP')
    else:
        need(available(level, allocated) > 0, 'BONUS_STAT_NO_POINTS')
    values = list(elixirs if elixir else allocated)
    values[attribute] += 1
    return (tuple(allocated), tuple(values)) if elixir else (tuple(values), tuple(elixirs))


def _scalar(payload):
    pb = inventory.pb
    with pb.parse_message(payload, limits=pb.WireLimits(max_body=128, max_fields=1,
                                                       max_field_bytes=32)) as parsed:
        need(len(parsed.fields) == 1 and len(parsed.occurrences(1)) == 1
             and parsed.occurrences(1)[0].wire_type == 0, 'BONUS_STAT_REQUEST_SCHEMA')
        return parsed.occurrences(1)[0].value


def bonus_frame(count):
    body = inventory.pb.encode_varint(8) + inventory.pb.encode_varint(count)
    return (len(body) + 6).to_bytes(2, 'little') + BONUS.to_bytes(2, 'little') + body + b'\0\0'


def _bonus_base(self, info, position):
    allocated, elixirs = self.progress_store.bonus_stats(position.uid)
    result = dict(info)
    for index, field in enumerate(ATTR_INFO):
        result[field] += allocated[index] + elixirs[index]
    return result


def _bonus_values(self, uid, name):
    _, original = self.realm.store.select(name)
    bonus = self.progress_store.bonus_stats(uid)
    return tuple(original[field] + bonus[0][i] + bonus[1][i]
                 for i, field in enumerate(ATTR_INFO)), bonus


def _bonus_notice(self, uid):
    current = self.world.progress.snapshot(uid)
    count = available(current.level, self.progress_store.bonus_stats(uid)[0])
    if self._bonus_notified.get(uid) != count:
        self._bonus_notified[uid] = count
        self.world._queue(uid, bonus_frame(count))


def _bonus_initialize(self):
    from tools.local_original_session.world_handlers import KitItemPolicy
    self._bonus_notified = {}
    self._bonus_results = []
    policies = []
    for offset, (name, icon) in enumerate(zip(ELIXIR_NAMES, ELIXIR_ICONS)):
        fields = dict(self.starter_fields)
        fields.update({2: 895 + offset, 7: icon, 18: name.encode('utf8')})
        policies.append(KitItemPolicy(895 + offset, 20, True, fields))
    self.add_item_policies(policies)


async def _bonus_enter(self, writer, row, game, operation_lock):
    uid = self.realm.service(writer).snapshot().uid
    self._bonus_notice(uid)
    await self._world_flush(writer, row, game, operation_lock)


def _bonus_leave(self, writer, uid):
    self._bonus_notified.pop(uid, None)


def _bonus_report(self, result):
    result['bonus_stats'] = list(self._bonus_results)


async def _bonus_raise(self, writer, row, game, frame, operation_lock):
    if not self._world_bound(writer) or self._world_ready(writer, game) is None:
        return False
    position = self.realm.service(writer).snapshot()
    uid = position.uid
    def apply():
        current = self.world.progress.snapshot(uid)
        status = 'allocated'
        try:
            need(not self.world.combat.is_dead(uid), 'BONUS_STAT_DEAD')
            attribute = _scalar(frame.payload)
            base, bonus = self._bonus_values(uid, position.name)
            changed = increase(current.level, base, bonus, attribute)
        except ValueError as error:
            status = str(error)
        else:
            # Persist the growth snapshot and optional fields before projection/response.
            raw = self.progress_store.prepare_bonus(uid, current, *changed)
            self.progress_store.replace_document(raw)
            self.world.progress.clear(uid)
            self.run_sync_hooks('stats_changed', uid)
        self._bonus_notified.pop(uid, None)
        self._bonus_notice(uid)
        self._bonus_results = (self._bonus_results + [dict(uid=uid, action='raise', status=status)])[-16:]
        from tools.local_original_session.world_status_frames import full_status_frame
        return (*self.world.drain(uid), full_status_frame(self.world.combat.pcs[uid].status_fields))
    frames = await self.world.runtime.dispatch_now(apply)
    await self._world_send(writer, row, frames, operation_lock)
    return True


def _elixir_request(self, payload):
    pb = inventory.pb
    with pb.parse_message(payload, limits=pb.WireLimits(max_body=4096, max_fields=2,
                                                       max_field_bytes=2048)) as parsed:
        fields = parsed.occurrences(1)
        if len(fields) != 1 or fields[0].wire_type != 0:
            return None
        uid = fields[0].value
        current = self.inventory_frame
        item = next((member for member in inventory.validate_kit_frame(current)
                     if member.identifier == uid and member.template_bits in ELIXIRS), None)
        if item is None:
            return None
        params = parsed.occurrences(2)
        need(len(parsed.fields) == 2 and len(params) == 1 and params[0].wire_type == 2,
             'ELIXIR_REQUEST_SCHEMA')
        parameter_body = bytes(params[0].value)
    with pb.parse_message(parameter_body, limits=pb.WireLimits(max_body=2048, max_fields=3,
                                                              max_field_bytes=2048)) as parsed:
        need(len(parsed.fields) == 3 and all(len(parsed.occurrences(n)) == 1
             and parsed.occurrences(n)[0].wire_type == 0 and parsed.occurrences(n)[0].value == val
             for n, val in ((1, 1), (15, 0), (16, 0))), 'ELIXIR_PARAMS_SCHEMA')
    return item


async def _bonus_elixir(self, host, payload, now):
    item = self._elixir_request(payload)
    if item is None:
        return False
    uid = host.pc_uid
    current = self.world.progress.snapshot(uid)
    position = self.realm.service(host.writer).snapshot()
    base, bonus = self._bonus_values(uid, position.name)
    changed = increase(current.level, base, bonus, ELIXIRS[item.template_bits], elixir=True)
    before = self.inventory_frame
    rows = [dict(member.raw_fields) for member in inventory.validate_kit_frame(before)]
    owned = next(value for value in rows if value[1] == item.identifier)
    need(owned[4] > 0, 'ELIXIR_OWNED_QUANTITY')
    owned[4] -= 1
    rows = [value for value in rows if value[4] > 0]
    after = inventory.build_kit_frame(rows)
    updated = self.progress_store.prepare_bonus(uid, current, *changed)
    host.commit_attempted = True
    need(self._world_replace_kit(uid, before, after,
         progress_change=(self.progress_store, self.progress_store.document(), updated)) is True,
         'ELIXIR_PERSISTED_CHANGE_REQUIRED')
    self.inventory_frame = after
    self.world.progress.clear(uid)
    self.run_sync_hooks('inventory_changed', host.writer, host.row)
    self.run_sync_hooks('stats_changed', uid)
    from tools.local_original_session import inventory_update, item_transfer_protocol
    from tools.local_original_session.world_status_frames import full_status_frame
    wire = (inventory_update._encode(inventory_update._values({1: item.identifier, 4: owned[4]}))
            if owned[4] else item_transfer_protocol.build_remove(uid=item.identifier))
    for frame in (*self.world.drain(uid), wire, full_status_frame(self.world.combat.pcs[uid].status_fields)):
        host.send_frame(frame)
    self._bonus_results = (self._bonus_results + [dict(uid=uid, action='elixir',
        template=item.template_bits, status='consumed')])[-16:]
    return True


def _elixir_boundary(owner, args):
    # Flush only actual owned elixir requests; ordinary item queries remain cheap.
    if len(args) < 2 or owner._inventory_current_frame is None:
        return False
    try:
        from tools.local_original_session.world_bridge import Context
        return _elixir_request(Context(owner), args[1]) is not None
    except ValueError:
        return False


METHODS = (_bonus_base, _bonus_values, _bonus_notice, _bonus_initialize, _bonus_enter,
           _bonus_leave, _bonus_report, _bonus_raise, _elixir_request, _bonus_elixir)
HOOKS = {'initialize': ('_bonus_initialize',), 'base_attributes': ('_bonus_base',),
         'stats_changed': ('_bonus_notice',), 'after_enter': ('_bonus_enter',),
         'before_leave': ('_bonus_leave',), 'report': ('_bonus_report',),
         'item_use': ('_bonus_elixir',)}
HOOK_PRIORITY = {'item_use': 0}
FRAMES = {RAISE: ('_bonus_raise',)}
SAVE_BOUNDARIES = {'_bonus_raise': True, '_bonus_elixir': _elixir_boundary}
OUTGOING_OPCODES = (BONUS,)
NONCRITICAL_HOOKS = ('report',)
