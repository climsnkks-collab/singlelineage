"""Native polymorph selection wire on a fresh retained socket-test profile.

The original client opens its XML list locally; this bot records that static
step, then sends the selected exact XML name with the received self/scroll UID.
No game client, user saves, forced clock/deadline or handler calls are used.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import test_ports


class PolymorphBot(hs.ScenarioBot):
    def apply(self, frame):
        if frame.opcode == 0x4e5c:
            frame.values = hb.fields(frame.wire[4:-2])
        super().apply(frame)


class PolymorphScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'polymorph', directory)
        self.fixture = None

    def record(self, name, ok, **evidence):
        super().record(name, ok, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    async def open(self, *, seed, character=None):
        from tools.local_original_session import inventory, movement
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(
            self.directory, expected, seed=seed)
        if seed:
            from tools.local_original_session.hunt_bot_loopback import KNIGHT, START
            position = self.broker.realm.positions.restore(movement.Position(1, KNIGHT[0], 0, *START))
            town = self.broker._world.data.town
            self.broker.realm.positions.commit(position,
                movement.Position(1, KNIGHT[0], town.map_id, town.respawn_x, town.respawn_y))
            self.fixture = dict(uid=1, character=KNIGHT[0], kit='test_knight', level=1,
                initialization='existing fresh saved starter/equipment, town position before FIRST; '
                    'no scroll UID/quantity injected and no user save modified',
                inventory_sha256=hashlib.sha256(self.store.restore(1)).hexdigest(),
                equipment='existing saved-equipment combat_inputs adapter; native memory sync unverified')
        data = self.broker._world.data
        def combat_inputs(uid):
            state, frame = self.equipment.peek(uid)
            by_uid = {i.identifier: data.items[i.template_bits]
                      for i in inventory.validate_kit_frame(frame)}
            return by_uid.get(state.weapon_uid), sum(by_uid[u].ac for _, u in state.slots)
        self.broker._item_equipment_effect = SimpleNamespace(store=self.equipment,
            combat_inputs=combat_inputs, _selection=None, _last={}, _defs=data.items)
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected,
            '--timeout', str(self.args.timeout), '--minutes', str(self.args.minutes)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = PolymorphBot(options)
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = data, time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda frames: hb.find(frames, 0x0964), 'POLYMORPH_KIT')
        self.record('FIRST_login_selection_world', self.bot.selected
            and self.bot.inventory_received and self.bot.hp > 0,
            uid=self.bot.self_uid, level=self.bot.level, position=self.bot.position)

    def saved_bag(self):
        from tools.local_original_session import inventory
        return {i.identifier: dict(i.raw_fields)
                for i in inventory.validate_kit_frame(self.store.restore(self.bot.self_uid))}

    def durable_bag(self):
        from tools.local_original_session import inventory
        rows, _ = self.store._read_disk()
        return {i.identifier: dict(i.raw_fields)
                for i in inventory.validate_kit_frame(rows[self.bot.self_uid])}

    def scroll(self):
        return next((uid, row) for uid, row in self.bot.inventory.items()
                    if row.get(2) == 299 and row.get(4, 0) > 0)

    def params(self, name):
        return (hb.uint(1, 1) + hb.uint(2, self.bot.self_uid)
            + hb.pb.encode_bytes(7, name.encode('utf-8')) + hb.uint(15, 0) + hb.uint(16, 0))

    async def select(self, name, *, refused=None):
        uid, item = self.scroll()
        before, count = self.saved_bag(), item[4]
        durable_before = self.durable_bag()
        client_before = {key: dict(fields) for key, fields in self.bot.inventory.items()}
        # The saved canonical ItemInfo and its received display projection may
        # differ (e.g. targeted-use f5 or a stack-name suffix). Each authority
        # must stay unchanged on refusal; they are not interchangeable bytes.
        differences = []
        def brief(value):
            return value.decode('utf-8', errors='replace')[:96] if isinstance(value, bytes) else value
        for member_uid in sorted(before.keys() | client_before.keys()):
            saved, client = before.get(member_uid, {}), client_before.get(member_uid, {})
            for number in sorted(saved.keys() | client.keys()):
                if saved.get(number) != client.get(number):
                    differences.append(dict(uid=member_uid, field=number,
                        saved=brief(saved.get(number)), client=brief(client.get(number))))
        differences.sort(key=lambda row: (row['field'] != 5, row['uid'], row['field']))
        marker = self.bot.peer.ordinal
        batch = await self.bot.peer.request(0x0960,
            hb.uint(1, uid) + hb.pb.encode_bytes(2, self.params(name)), alive=True,
            check=lambda frames: hb.find(frames, 0x4f57), label='POLYMORPH_SELECT_' + name)
        if refused:
            persisted_unchanged = before == self.saved_bag()
            durable_unchanged = durable_before == self.durable_bag()
            client_unchanged = client_before == self.bot.inventory
            no_poly_notice = not any(f.opcode == 0x4e5c for f in batch)
            handler_reason = (self.broker._world_handler_errors[-1]
                              if self.broker._world_handler_errors else None)
            peer_error = self.bot.peer.error
            broker_failed = self.broker.failure.is_set()
            self.record('refused_' + refused, persisted_unchanged and durable_unchanged
                and client_unchanged and handler_reason == refused
                and no_poly_notice and peer_error is None and not broker_failed,
                selected_xml_name=name, uid=uid, count=count, reason=refused,
                persisted_unchanged=persisted_unchanged, durable_unchanged=durable_unchanged,
                client_unchanged=client_unchanged, no_poly_notice=no_poly_notice,
                handler_reason=handler_reason, peer_error=None if peer_error is None else str(peer_error)[:120],
                broker_failed=broker_failed, initial_saved_client_difference_count=len(differences),
                initial_saved_client_differences=differences[:12],
                scope='only the invalid request refused; socket Alive response received')
        return marker, batch, count

    async def polymorph(self):
        uid, scroll = self.scroll()
        self.record('default_path_without_POLY_experiment', not os.environ.get('SL_EXPERIMENT_POLY'),
            env=os.environ.get('SL_EXPERIMENT_POLY'),
            report=self.broker.report().get('world', {}).get('polymorph_selection'))
        self.record('received_scroll_opens_original_client_local_list', scroll.get(5) == 16,
            uid=uid, template=scroll[2], raw=scroll.get(5), quantity=scroll[4],
            source='POLYMORPH_SELECT_UI.md: 4FD260 -> 5689D0 -> UI2; no initial use/list packet',
            scope='static client-local selection step; native window/click not executed')
        await self.select('invented polymorph', refused='POLYMORPH_UNKNOWN_NATIVE_FORM')
        await self.select('death knight morph', refused='level_too_low')
        actor = self.bot.live_appearances[self.bot.self_uid]
        base_sprite = hb.scalar(actor, 3)
        marker, batch, count = await self.select('orc morph')
        notification = hb.find(batch, 0x4e5c, **{'1': self.bot.self_uid, '2': 3906})
        active = self.broker._world_polymorphs.get(self.bot.self_uid)
        now = self.broker._world.runtime.clock()
        self.record('native_name_owned_scroll_consumed_and_transformed',
            notification is not None and active is not None
            and active.current_sprite_id == 3906 and active.base_sprite_id == base_sprite
            and active.active.form_key == self.broker._world_poly_catalog.native_names['orc morph']
            and self.bot.inventory[uid][4] == self.saved_bag()[uid][4]
                == self.durable_bag()[uid][4] == count - 1
            and 1790 < active.active.expires_at_ms / 1000 - now <= 1800,
            uid=uid, self_uid=self.bot.self_uid, selected_xml_name='orc morph',
            quantity_before=count, quantity_after=self.saved_bag()[uid][4],
            durable_quantity_after=self.durable_bag()[uid][4],
            base_sprite=base_sprite, sprite=active.current_sprite_id,
            remaining_s=active.active.expires_at_ms / 1000 - now,
            policy='existing data/m1/polymorph.json normal1800s LOCAL L1J policy',
            notification_ordinal=None if notification is None else notification.ordinal)
        started = now
        until = now + 1830
        while self.bot.self_uid in self.broker._world_polymorphs:
            if self.broker._world.runtime.clock() > until:
                raise hs.Unconfirmed('NATURAL_POLYMORPH_EXPIRY_NOT_OBSERVED')
            await asyncio.sleep(5)
            await self.bot.alive()
        await self.bot.alive()
        later = [f for f in self.bot.peer.frames if f.ordinal > marker]
        reverted = hb.find(later, 0x4e5c, **{'1': self.bot.self_uid, '2': base_sprite})
        self.record('natural_1800s_expiry_received_and_base_restored',
            reverted is not None and self.bot.self_uid not in self.broker._world_poly_timers
            and self.saved_bag()[uid][4] == self.bot.inventory[uid][4] == count - 1,
            base_sprite=base_sprite, elapsed_virtual_s=self.broker._world.runtime.clock() - started,
            revert_ordinal=None if reverted is None else reverted.ordinal,
            scope='real scheduler/clock expiry and SC4E5C; no timer/clock/source duration mutation')
        self.record('only_expected_request_refusals', self.broker._world_handler_errors ==
            ['POLYMORPH_UNKNOWN_NATIVE_FORM', 'level_too_low'],
            errors=list(self.broker._world_handler_errors))


def parser():
    result = hs.parser()
    result.description = __doc__
    next(a for a in result._actions if a.dest == 'scenario').choices = ('polymorph', 'all')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-polymorph-', dir=root))
    names = ('hunt_bot_polymorph.py', 'world_polymorph.py', 'world_feature_items.py',
        'hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_loopback.py', 'world_handlers.py',
        'world_bridge.py', 'world_core_kit.py', 'world_core_inventory.py', 'world_core_session.py',
        'world_core_stats.py', 'broker.py', 'inventory.py', 'inventory_store.py',
        'equipment_store.py', 'item_equipment_effect.py', 'world_state_services.py',
        'world_warehouse.py', 'data/m1/starter.json', 'data/m1/polymorph.json')
    def sources():
        return {n: hashlib.sha256((Path(__file__).parent / n).read_bytes()).hexdigest() for n in names}
    before = sources()
    scenario = PolymorphScenario(args, directory)
    result = await scenario.run()
    result.update(fixture=scenario.fixture, source_sha256_start=before, source_sha256=sources(),
        scope='fresh retained test profile; normal FIRST/login/selection/world, real socket '
            'decoder/router, owned UID, saved cost and real1800s expiry. Original window, input '
            'and rendering unverified. Incompatible-weapon native notification not exercised here.')
    result['source_changes_during_run'] = [n for n in names if before[n] != result['source_sha256'][n]]
    result['reused_from'] = {n: before[n] for n in
        ('hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_loopback.py')}
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2,
        default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
