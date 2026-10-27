"""Talking-scroll feature; preserve the existing inventory/relocation owners.

The two registered wrappers compose the existing kit and dispatch entry points.
They do not replace equipment, movement, inventory storage or connection code.
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
from types import MappingProxyType

from tools.local_native_login_local_ack_hook import ack_enter_world as ack
from tools.local_original_session.world_bridge import need


def _talkscroll_initialize(self):
    from tools.local_original_session.game_data import ItemDef, Source
    from tools.local_original_session.world_handlers import KitItemPolicy
    from tools.local_original_session.world_talkscroll import load_catalog
    self._talkscroll_catalog = load_catalog()
    # Native group10 is the ordinary client-owned menu. The old NPC menu is a
    # separate explicit experiment; it only has a dungeon-entrance action.
    self._talkscroll_native = os.environ.get('SL_EXPERIMENT_TALKSCROLL', '') != 'npc'
    starter = Path(__file__).resolve().parent / 'data/m1/starter.json'
    self._talkscroll_supplies = tuple(json.loads(starter.read_text(encoding='utf-8'))[
        'kits']['test_knight'].get('talkscroll_supplies', ()))
    definitions = dict(self._world.data.items)
    policies = dict(self._world_handler_bindings.item_policies)
    for template, row in self._talkscroll_catalog.items.items():
        source = Source('client', row['ref'])
        definitions[template] = ItemDef(template, row['name_token'], row['name_ko'], 'scroll',
            None, None, True, 0, 0, 0, 0, 0, 0, frozenset((0, 1, 2, 3)),
            MappingProxyType({'identity': source,
                'stackable': Source('local_policy', 'talkscroll.json: explicit LOCAL stacking')}),
            icon=row['icon'], weight=row['weight'])
        policies[template] = KitItemPolicy(template, row['weight'], True)
    data = replace(self._world.data, items=MappingProxyType(definitions))
    self._world.data = self._world.combat.data = data
    self._world_handler_bindings = replace(self._world_handler_bindings,
        item_policies=MappingProxyType(policies))


def _inventory_kit_frame(self, character_class):
    from tools.local_original_session import inventory
    from tools.local_original_session.world_feature_kit import _inventory_kit_frame as base
    frame = base(self, character_class)
    if character_class == 3 and getattr(self, '_talkscroll_native', False):
        # The shared mage starter already owns its one scroll. Apply the same
        # existing native menu candidate without appending another copy.
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        for fields in rows:
            if fields[2] in self._talkscroll_catalog.items:
                fields[5] = 133
        return inventory.build_kit_frame(rows)
    if (getattr(self, '_world_starter_kit', None) != 'test_knight' or character_class != 1
            or not getattr(self, '_talkscroll_supplies', ())):
        return frame
    rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
    identifier = max(row[1] for row in rows) + 1
    for supply in self._talkscroll_supplies:
        value = supply['value']
        fields = dict(self.starter_fields)
        fields.update({1: identifier, 2: value['item'], 4: value['count'], 7: value['icon']})
        if getattr(self, '_talkscroll_native', False):
            # ItemInfo.f5 -> Entity+50 -> raw133 UI branch is source-confirmed.
            # The official server's actual raw133 supply remains unobserved.
            fields[5] = 133
        rows.append(fields)
        identifier += 1
    return inventory.build_kit_frame(rows)


async def _world_dispatch(self, writer, row, game, frame, operation_lock):
    from tools.local_original_session.world_feature_session import _world_dispatch as base
    if (not self._world_bound(writer) or self._world_ready(writer, game) is None
            or frame.opcode not in (0x0960, 0x4ed4)):
        if frame.opcode in (0x4e43, 0x4e2b):
            row.pop('_talkscroll_selection', None)
        return await base(self, writer, row, game, frame, operation_lock)
    if await _talkscroll_request(self, writer, row, game, frame, operation_lock):
        return True
    return await base(self, writer, row, game, frame, operation_lock)


async def _talkscroll_request(self, writer, row, game, frame, operation_lock):
    from tools.local_original_session import inventory, world_talkscroll
    from tools.local_original_session.world_handlers import HostContext
    pb = ack.realm.pb
    pending = row.get('_talkscroll_selection')
    item, params, fields = None, None, None
    if frame.opcode == 0x0960:
        try:
            with pb.parse_message(frame.payload, limits=pb.WireLimits(
                    max_body=4096, max_fields=2, max_field_bytes=2048)) as parsed:
                if not (len(parsed.fields) == 2
                        and len(parsed.occurrences(1)) == len(parsed.occurrences(2)) == 1
                        and parsed.occurrences(1)[0].wire_type == 0
                        and parsed.occurrences(2)[0].wire_type == 2):
                    return False
                identifier = parsed.occurrences(1)[0].value
                params = bytes(parsed.occurrences(2)[0].value)
            item = next((item for item in inventory.validate_kit_frame(self.inventory_frame)
                         if item.identifier == identifier), None)
            if item is None or item.template_bits not in self._talkscroll_catalog.items:
                return False
        except (ValueError, pb.WireError):
            return False  # The existing lane owns malformed unrelated item requests.
    elif pending is None:
        return False
    ctx = HostContext(self.broker, writer, row, game, operation_lock)
    published = None

    def apply():
        nonlocal published
        need(not self._world.combat.is_dead(ctx.pc_uid), 'TALKSCROLL_LIVING_PC_REQUIRED')
        position = self.realm.service(writer).snapshot()
        origin = position.map_id, position.word0, position.word1
        catalog = self._talkscroll_catalog
        destination = None
        if item is not None:
            current = next((member for member in inventory.validate_kit_frame(self.inventory_frame)
                            if member.identifier == item.identifier), None)
            need(current is not None and current.template_bits == item.template_bits
                 and dict(current.raw_fields)[4] > 0, 'TALKSCROLL_CURRENT_OWNED_STACK_REQUIRED')
            with pb.parse_message(params, limits=pb.WireLimits(
                    max_body=2048, max_fields=4, max_field_bytes=2048)) as parsed:
                values = {field.number: field.value for field in parsed.fields}
                need(all(field.wire_type == 0 for field in parsed.fields)
                     and len(values) == len(parsed.fields), 'TALKSCROLL_USE_PARAMS_REQUIRED')
            if 13 in values:
                need(self._talkscroll_native, 'TALKSCROLL_NATIVE_LIST_EXPERIMENT_REQUIRED')
                need(set(values) == {1, 13, 15, 16} and values[1] == 1,
                     'TALKSCROLL_NATIVE_SELECTION_PARAMS_REQUIRED')
                destination = catalog.destinations.get('native:' + str(values[13]))
                need(destination is not None, 'TALKSCROLL_UNKNOWN_NATIVE_DESTINATION')
                row.pop('_talkscroll_selection', None)
            else:
                need(not self._talkscroll_native, 'TALKSCROLL_RAW0_NPC_EXPERIMENT_REQUIRED')
                need(values == {1: 1, 15: 0, 16: 0}, 'TALKSCROLL_RAW0_PARAMS_REQUIRED')
                ctx.begin_click()
                published = world_talkscroll.Selection(ctx.pc_uid, item.identifier,
                    item.template_bits, origin, catalog.initial_page)
                row['_talkscroll_selection'] = published
        else:
            action = ctx.wire.dialogue.decode_haction_normal(frame.payload)
            current = next((member for member in inventory.validate_kit_frame(self.inventory_frame)
                            if member.identifier == pending.item_uid), None)
            next_page, destination = world_talkscroll.select(catalog, pending,
                pc_uid=ctx.pc_uid, target_uid=action[1] & 0xffffffff,
                action=action[2].decode('utf-8'), origin=origin,
                owned_template=None if current is None else current.template_bits,
                owned_count=0 if current is None else dict(current.raw_fields)[4])
            row.pop('_talkscroll_selection', None)
            if next_page is not None:
                published = world_talkscroll.Selection(ctx.pc_uid, pending.item_uid,
                    pending.template_id, origin, next_page)
                row['_talkscroll_selection'] = published
        if destination is None:
            if published is not None:
                target = published.item_uid
                target = target if target < 1 << 31 else target - (1 << 32)
                ctx.send_frame(ctx.wire.dialogue_frame({1: target, 2: published.page.encode('utf-8')}))
            return
        need(self.realm.serves_map(destination.map_id)
             and (destination.map_id == position.map_id or self._world_map_exp == 2)
             and self._world.terrain.can_stand(destination.map_id, destination.x, destination.y) is True,
             'TALKSCROLL_DESTINATION_UNAVAILABLE')
        for older in self._world.drain(ctx.pc_uid):
            ctx.send_frame(older)
        # Official beginner guide: unlimited uses until expiration. Preserve the
        # exact owned stack; acquisition/expiration timestamps are not supplied.
        # Existing relocation owns position saving and any partial failure.
        for wire in self._world_relocate_locked(writer, row, game, destination,
                context=ctx, same_map_correction=True):
            ctx.send_frame(wire)
        ctx.state.clear()

    try:
        await self._world.runtime.dispatch_now(apply)
    except (ValueError, pb.WireError, UnicodeError) as error:
        if ctx.commit_attempted:
            raise
        self._world_handler_errors = (self._world_handler_errors + [str(error)[:96]])[-8:]
        return True
    await self._world_send(writer, row, tuple(ctx.frames), operation_lock)
    if published is not None:
        published.delivered = True
    return True


METHODS = (_talkscroll_initialize, _inventory_kit_frame, _world_dispatch)
HOOKS = {'initialize': ('_talkscroll_initialize',)}
