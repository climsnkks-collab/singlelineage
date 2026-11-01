"""Run hunt_bot against a fresh loopback -World PersistentBroker (test harness).

    python -X utf8 -B -m tools.local_original_session.hunt_bot_loopback --minutes 3

The broker is built exactly like world_spawn_tests.BrokerWorldTests (fixture
owner/conversation, reserved test ports), with the world policy and the static
terrain edge fallback (no client-memory edge). A knight is created in a temporary
profile next to the north meadow. Two stand-ins replace launcher/native pieces
that a socket client cannot drive:
* kit inventory: world_m1_reward_tests.enable_world_kit grants the knight starter
  kit row (named test_knight kit) and the kit frame is sent once after selection;
  the kit's equipped weapon/armour stand in for the native-synced equipment row;
* potion use: CS0960 on a kit potion runs the same saved-row quantity change and
  broker._world_potion_locked (older frames -> 0965/0978 -> SC_STATUS) that
  item_equipment_effect._consume_potion uses after its native checks.
Everything else (combat, AI, reward, ground drops, pickup, saves) is product code.
SL_TEST_PORT_BASE shifts the test listeners (default 12000/14030).
Prints one JSON object: bot summary, broker world report, saved progression/kit,
and event-loop stall measurements. No game client, no screen.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
from pathlib import Path
import tempfile
import time
import uuid

from tools.local_original_session import broker as b, hunt_bot, inventory, inventory_update, equipment_store
from tools.local_original_session import item_transfer_protocol, movement as m, world_visibility as wv
from tools.local_original_session import world_combat as wc
from tools.local_original_session import test_ports
from tools.local_original_session.broker_tests import FixtureConversation, reserve
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_m1_reward_tests import enable_world_kit, kit_items

START = (32595, 32906)
KNIGHT = ('SoloKnight', 1, 0, (18, 12, 16, 9, 12, 8))


def build(temp: Path, expected_uuid: str):
    async def owner(peer):
        return True
    broker = b.PersistentBroker(sockets=reserve(), listener_ports=test_ports.listener_ports(), retained_owner=object(),
        owner_handle=object(), owner_job=object(), owner_guard=owner,
        owner_liveness_guard=lambda: True, source_guard=lambda: None,
        conversation_factory=FixtureConversation, expected_uuid=expected_uuid,
        store_path=temp / 'characters.json', world_policy=wv.POLICY)
    realm = broker.realm
    realm.store.create(b.ack.realm.Creation(*KNIGHT))
    x, y = m.authority.unpack_grid(realm._actor_fields[1])
    realm.positions.commit(m.Position(1, KNIGHT[0], 0, x, y), m.Position(1, KNIGHT[0], 0, *START))
    data = load_m1()
    # Same named kit as manual -TestKnight play (start-manual-play / run_auto_knight).
    broker._world_starter_kit = 'test_knight'
    store, kit_frame = enable_world_kit(broker, KNIGHT[1])
    # Same persisted first-enable equipment as the scenario fixture; the socket
    # harness supplies combat inputs without claiming native equipment sync.
    worn = [data.items[e.template_id] for e in data.starter.entries(KNIGHT[1], 'test_knight') if e.equipped]
    weapon = next(item for item in worn if item.kind == 'weapon')
    items = {item.template_bits: item.identifier for item in inventory.validate_kit_frame(kit_frame)}
    equipment = equipment_store.EquipmentStore(store, policy=equipment_store.POLICY,
        kit_policy=inventory.KIT_POLICY, item_defs=data.items)
    equipment.initialize_kit(1, kit_frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
        weapon_uid=items[weapon.template_id],
        slots=tuple((item.slot_key, items[item.template_id]) for item in worn if item.kind == 'armor'))
    original_profile = broker._world_pc_profile

    def profile(writer, position, *, level=None):
        state, saved_frame = equipment.peek(position.uid)
        by_uid = {item.identifier: data.items.get(item.template_bits)
                  for item in inventory.validate_kit_frame(saved_frame)}
        weapon = by_uid.get(state.weapon_uid)
        armour = sum(by_uid[uid].ac for _, uid in state.slots)
        return dataclasses.replace(original_profile(writer, position, level=level),
            weapon=wc.FIST if weapon is None else wc.weapon_from_item(weapon), ac=wc.DEFAULT_PC_AC + armour)
    broker._world_pc_profile = profile

    original_after = broker._world_after_request

    async def after(writer, row, game, opcode, lock):
        await original_after(writer, row, game, opcode, lock)
        bound = broker._world_pcs.get(id(writer))
        if opcode == 0x4e28 and bound is not None and bound[0] is writer:
            await broker._world_send(writer, row, inventory.kit_wire_frames(broker._inventory_current_frame), lock)
    broker._world_after_request = after

    original_grant = realm.grant

    def grant(writer, **options):
        game = original_grant(writer, **options)

        async def use(payload):
            item_uid = hunt_bot.scalar(hunt_bot.fields(payload), 1)
            frame = broker._inventory_current_frame
            items = inventory.validate_kit_frame(frame)
            target = next(i for i in items if i.identifier == item_uid)
            fields = dict(target.raw_fields)
            definition = data.items[fields[2] & 0xffffffff]
            if definition.kind != 'potion' or definition.buff is not None or fields[4] < 1:
                return ()
            remove = fields[4] == 1 and len(items) > 1
            rows = []
            for item in items:
                row_fields = dict(item.raw_fields)
                if item.identifier == item_uid:
                    if remove:
                        continue
                    row_fields[4] -= 1
                rows.append(row_fields)
            new_frame = inventory.build_kit_frame(rows)
            wire = (item_transfer_protocol._remove_frame(item_transfer_protocol.RemoveInventory(item_uid))
                    if remove else inventory_update._encode(inventory_update._values({1: item_uid, 4: fields[4] - 1})))
            store.replace_kit(1, frame, new_frame)
            broker._inventory_current_frame = new_frame
            row = next(r for rows in broker._claims.values() for r in rows if r['writer'] is writer)
            await broker._world_potion_locked(writer, row, wire, definition.heal_hp)
            return ()
        game.routes[b.ITEM_USE_REQUEST] = use
        return game
    realm.grant = grant
    broker.policy.item_use_intent = True
    return broker, store


async def run(args):
    expected = str(uuid.uuid4())
    lag = dict(max_ms=0.0, over_50ms=0, over_200ms=0, samples=0)

    async def watch():
        while True:
            before = time.perf_counter()
            await asyncio.sleep(.01)
            late = (time.perf_counter() - before - .01) * 1000
            lag['samples'] += 1
            lag['max_ms'] = max(lag['max_ms'], round(late, 1))
            lag['over_50ms'] += late > 50
            lag['over_200ms'] += late > 200
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    temp = tempfile.mkdtemp(prefix='hunt-loopback-', dir=root)
    try:
        broker, store = build(Path(temp), expected)
        await broker.start()
        watcher = asyncio.create_task(watch())
        bot_args = hunt_bot.parser().parse_args(['--minutes', str(args.minutes), '--expected-uuid', expected,
                                                 '--potion-threshold', str(args.potion_threshold)])
        bot_args.port = test_ports.port(bot_args.port)
        try:
            bot = hunt_bot.HuntBot(bot_args)
            bot.terrain = broker._world.terrain
            summary = await bot.run()
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        tasks = tuple(broker._tasks)
        if tasks:
            await asyncio.wait(tasks, timeout=bot_args.timeout)
        report = broker.report()
        progression = Path(temp) / 'progression.json'
        saved = json.loads(progression.read_text()) if progression.exists() else None
        kit = {template: fields[4] for template, fields in kit_items(store.restore(1)).items()}
        closed = await broker.close()
        return dict(bot=summary, broker_failure=report['failure_code'], world=report.get('world'),
                    movement=report.get('movement'),
                    saved_progression=saved, saved_kit_counts=kit,
                    profile_path=temp, broker_cleanup_complete=closed['cleanup_complete'], loop_lag=lag)
    finally:
        if 'broker' in locals():
            await broker.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--minutes', type=float, default=3)
    parser.add_argument('--potion-threshold', type=float, default=.5)
    args = parser.parse_args(argv)
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if result['bot']['failure'] or result['broker_failure'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
