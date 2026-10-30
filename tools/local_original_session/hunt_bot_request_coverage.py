"""Owned loopback GET coverage: natural loot, oversized Q, then normal pickup.

Uses hunt_bot_loopback's temporary knight/equipment fixture and HuntBot's real
FIRST/login/select/hunt/Quit path. No native input/rendering claim. Requests
use only the received ground UID, coordinates and count; server reads observe
effects and never manufacture a target or authorize a pickup.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import uuid

from tools.local_original_session import hunt_bot as hb, hunt_bot_loopback as loopback
from tools.local_original_session import inventory, inventory_store, test_ports


def source_metadata(previous=None):
    """Existing bot convention: initial loaded-file fingerprints, not guards."""
    result = {} if previous is None else dict(previous)
    core = {'broker', 'inventory', 'inventory_store', 'equipment_store', 'movement',
            'item_transfer_protocol', 'world_visibility', 'world_ground_items',
            'world_bridge', 'world_handlers', 'hunt_bot', 'hunt_bot_loopback',
            'hunt_bot_request_coverage', 'test_ports', 'game_data', 'feature_config',
            'world_craft', 'world_town_services'}
    for name, module in tuple(sys.modules.items()):
        leaf = name.rsplit('.', 1)[-1]
        if (not name.startswith('tools.local_original_session.') or name in result
                or not (leaf in core or leaf.startswith(('world_feature_', 'world_core_')))):
            continue
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename)
            result[name] = dict(file=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                basis='first post-import on-disk fingerprint')
    for path in (Path(__file__).resolve(), Path(__file__).resolve().parent / 'data/crafting.json'):
        key = str(path)
        if key not in result:
            result[key] = dict(file=key, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                               basis='initial running harness/startup data fingerprint')
    return result


def saved_rows(store, uid):
    return {item.identifier: (item.template_bits, dict(item.raw_fields)[4])
            for item in inventory.validate_kit_frame(store.restore(uid))}


def quantities(rows):
    counts = Counter()
    for template, count in rows.values():
        counts[template] += count
    return counts


class RequestCoverageBot(hb.HuntBot):
    def __init__(self, args, broker, store):
        super().__init__(args)
        self.broker, self.store = broker, store
        self.pickup_pairs = []

    def ground_snapshot(self, uid):
        entity = self.broker._world.entities.get(uid)
        item = None if entity is None else self.broker._world.ground.get(entity.ref)
        if item is None:
            return None
        return dict(uid=item.ref.uid, generation=item.ref.generation, template=item.item_id,
                    count=item.count, map_id=item.map_id, position=(item.x, item.y),
                    owner_uid=item.owner_uid, source_npc_uid=item.source_ref.uid,
                    source_generation=item.source_ref.generation, expires_at=item.expires_at)

    def wire_rows(self):
        return {uid: (row[2] & 0xffffffff, row[4]) for uid, row in self.inventory.items()}

    async def pickup(self, uid):
        observed = copy.deepcopy(self.ground[uid])
        (x, y), count = observed['position'], observed['count']
        before_wire = copy.deepcopy(self.inventory)
        before_wire_rows, before_saved = self.wire_rows(), saved_rows(self.store, self.self_uid)
        ground_before = self.ground_snapshot(uid)
        pair = dict(uid=uid, requested_position=(x, y), received_quantity=count,
                    rejected_request_quantity=count + 1, ground_before=ground_before,
                    invalid_quantity_preserved=False, normal_pickup_complete=False)
        self.pickup_pairs.append(pair)
        # Read-only attribution, separate from wire target/value selection above.
        if (ground_before is None or ground_before['source_npc_uid'] not in self.kills
                or ground_before['owner_uid'] != self.self_uid
                or ground_before['count'] != count):
            raise hb.BotFailure('RECEIVED_LOOT_NATURAL_OWN_KILL_LINK_REQUIRED')
        template = ground_before['template']
        pair.update(wire_template_quantity_before=quantities(before_wire_rows)[template],
                    saved_template_quantity_before=quantities(before_saved)[template])
        child = hb.uint(1, x) + hb.uint(2, y) + hb.uint(3, uid) + hb.uint(4, count + 1)
        invalid = await self.peer.request(
            0x4e3e, hb.pb.encode_bytes(1, child), alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label='GET_oversized_Q_to_ALIVE_barrier')
        pair['invalid_response_opcodes'] = [f'0x{frame.opcode:04X}' for frame in invalid]
        pair['ground_after_invalid'] = self.ground_snapshot(uid)
        saved_after_invalid = saved_rows(self.store, self.self_uid)
        pair.update(wire_template_quantity_after_invalid=quantities(self.wire_rows())[template],
                    saved_template_quantity_after_invalid=quantities(saved_after_invalid)[template])
        if (self.inventory != before_wire or saved_after_invalid != before_saved
                or pair['ground_after_invalid'] != ground_before or self.ground.get(uid) != observed
                or any(frame.opcode in (0x0964, 0x0965, 0x0978) for frame in invalid)
                or hb.find(invalid, 0x4e40, **{'1': uid}) is not None):
            raise hb.BotFailure('OVERSIZED_GET_MUTATED_INVENTORY_OR_GROUND')
        pair['invalid_quantity_preserved'] = True
        marker, pickups_before = self.peer.ordinal, self.pickups
        result = await super().pickup(uid)
        normal = [frame for frame in self.peer.frames if frame.ordinal > marker]
        after_wire, after_saved = self.wire_rows(), saved_rows(self.store, self.self_uid)
        wire_delta, saved_delta = quantities(after_wire), quantities(after_saved)
        wire_delta.subtract(quantities(before_wire_rows))
        saved_delta.subtract(quantities(before_saved))
        wire_delta = {key: value for key, value in wire_delta.items() if value}
        saved_delta = {key: value for key, value in saved_delta.items() if value}
        pair.update(normal_response_opcodes=[f'0x{frame.opcode:04X}' for frame in normal],
                    wire_quantity_delta=wire_delta, saved_quantity_delta=saved_delta,
                    ground_after_normal=self.ground_snapshot(uid),
                    wire_template_quantity_after_normal=quantities(after_wire)[template],
                    saved_template_quantity_after_normal=quantities(after_saved)[template])
        if (self.pickups != pickups_before + 1 or uid in self.ground
                or pair['ground_after_normal'] is not None
                or hb.find(normal, 0x4e40, **{'1': uid}) is None
                or not any(frame.opcode in (0x0964, 0x0965) for frame in normal)
                or wire_delta != {template: count} or saved_delta != {template: count}):
            raise hb.BotFailure('NORMAL_GET_REPLY_GROUND_AND_SAVED_DELTA_REQUIRED')
        pair['normal_pickup_complete'] = True
        return result


async def run(args):
    started = time.monotonic()
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='request-coverage-', dir=root))
    expected = str(uuid.uuid4())
    broker = bot = None
    error, closed, summary, report = None, None, None, None
    stage, sources = 'build_loopback_fixture', source_metadata()
    final_saved = None
    try:
        broker, store = loopback.build(directory, expected)
        sources = source_metadata(sources)
        stage = 'normal_FIRST_login_select_hunt'
        await broker.start()
        options = hb.parser().parse_args(['--minutes', str(args.minutes), '--expected-uuid', expected,
                                         '--timeout', str(args.timeout)])
        options.port = test_ports.port(options.port)
        bot = RequestCoverageBot(options, broker, store)
        bot.terrain = broker._world.terrain
        summary = await bot.run()  # Includes normal Quit and every Peer.close in finally.
        if summary['failure']:
            raise hb.BotFailure(summary['failure_reason'] or summary['cleanup_failure'])
        if not any(pair['normal_pickup_complete'] for pair in bot.pickup_pairs):
            raise hb.BotFailure('AT_LEAST_ONE_OVERSIZED_AND_NORMAL_GET_PAIR_REQUIRED')
        stage = 'normal_Quit_broker_close_and_disk_restore'
        tasks = tuple(broker._tasks)
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=options.timeout)
            if pending:
                raise hb.BotFailure('BROKER_CONNECTION_CLEANUP_TIMEOUT')
        report = broker.report()
        expected_saved = saved_rows(store, bot.self_uid)
        closed = (await broker.close())['cleanup_complete']
        restored = inventory_store.InventoryStore(
            directory / 'characters.json', policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        durable_saved = saved_rows(restored, bot.self_uid)
        final_saved = {key: list(value) for key, value in durable_saved.items()}
        if durable_saved != expected_saved:
            raise hb.BotFailure('POST_QUIT_DISK_UID_QUANTITY_MISMATCH')
        if report['failure_code'] is not None:
            raise hb.BotFailure(f"BROKER_FAILURE: {report['failure_code']}")
        stage = 'observations_complete'
    except Exception as failure:
        error = f'{type(failure).__name__}: {str(failure)[:300]}'
    finally:
        if broker is not None:
            try:
                closed = (await broker.close())['cleanup_complete']
            except Exception as failure:
                closed = False
                error = error or f'BROKER_CLOSE: {type(failure).__name__}: {str(failure)[:160]}'
            report = report or broker.report()
    result = dict(status='SUCCESS' if error is None and closed is True else 'FAILED', error=error,
                  stopped_stage=stage, profile_path=str(directory), cleanup_complete=closed,
                  elapsed_seconds=round(time.monotonic() - started, 3),
                  scope='owned loopback fixture; ordered socket GET quantities and saved UID/Q only; native/UI unverified',
                  bot=summary if summary is not None else (None if bot is None else bot.summary()),
                  pickup_pairs=[] if bot is None else bot.pickup_pairs,
                  final_disk_rows=final_saved, broker_failure=None if report is None else report['failure_code'],
                  world=None if report is None else report.get('world'), source_sha256=sources)
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes', type=hb.positive, default=2)
    parser.add_argument('--timeout', type=hb.positive, default=15)
    result = asyncio.run(run(parser.parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
