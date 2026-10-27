"""Socket expansion smoke: fresh fixture -> FIRST/login/select -> hunt -> real loot.

Reuses Scenario/loopback fixtures. Only the new development starting position
is seeded before selection; no HP/reward/RNG/readiness or live state is forced.
No original client, native rendering or input PASS is claimed.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import time
import uuid

from tools.local_original_session import game_data as gd, hunt_bot as hb, inventory
from tools.local_original_session import hunt_bot_scenarios as scenarios, movement


async def run(args):
    data = gd.load_m1()
    candidates = [g for g in data.spawns if g.group_id == args.group and g.map_id == 0]
    if not candidates:
        raise ValueError('NEW_MAP0_GROUP_REQUIRED')
    group = min(candidates, key=lambda g: (data.monsters[g.template_id].level, g.group_id))
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    directory = Path(tempfile.mkdtemp(prefix='expansion-bot-', dir=root))
    options = scenarios.parser().parse_args(['--timeout', str(args.timeout), '--minutes', '1'])
    scene = scenarios.Scenario(options, 'expansion', directory)
    error, closed = None, True
    evidence = {}
    broker = None
    stage = 'fresh_fixture_seed_before_FIRST'
    try:
        broker, _, _ = await scenarios.build_epoch(directory, str(uuid.uuid4()), seed=True)
        from tools.local_original_session.hunt_bot_loopback import START, KNIGHT
        old = broker.realm.positions.restore(movement.Position(1, KNIGHT[0], 0, *START))
        # All cells of new rectangles have been checked against real S32. Start
        # near its edge; move packets still have to reach a received live target.
        origin = (group.rect.x1, group.rect.y1)
        if broker._world.terrain.can_stand(0, *origin) is not True:
            raise ValueError('START_CELL_NOT_STANDABLE')
        broker.realm.positions.commit(old, movement.Position(1, old.name, 0, *origin))
        closed = (await broker.close())['cleanup_complete']
        if not closed:
            raise RuntimeError('SEED_CLEANUP_INCOMPLETE')
        broker = None
        stage = 'normal_FIRST_login_select'
        await scene.open(seed=False)
        bot = scene.bot
        stage = 'ordered_wire_move_attack_drop_pickup'
        def saved_counts():
            result = Counter()
            for item in inventory.validate_kit_frame(scene.store.restore(bot.self_uid)):
                row = dict(item.raw_fields)
                result[row[2] & 0xffffffff] += row[4]
            return result
        saved_before = saved_counts()
        evidence['start'] = dict(map_id=bot.map_id, position=bot.position, hp=bot.hp,
            selected=bot.selected, inventory_received=bot.inventory_received)
        appeared, killed, dropped, picked = set(), set(), set(), set()
        ground_origins = {}
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            if bot.dead:
                raise hb.BotFailure('PLAYER_DEAD')
            # Read-only linkage identifies current server-issued UIDs from this
            # new group. Requests always use the actually received wire actor.
            issued = {slot.uid for g in scene.broker._world.spawner.groups
                      if g.spec.group_id == group.group_id for slot in g.slots if slot.uid is not None}
            appeared.update(issued.intersection(bot.actors))
            killed.update(appeared.intersection(bot.kills))
            # GroundItems retains its actual corpse EntityRef and owner. Match
            # that immutable read-only record to our received/killed new-group
            # UID before permitting the wire ground UID as the loot candidate.
            for uid in bot.ground:
                entity = scene.broker._world.runtime.entities.get(uid)
                item = None if entity is None else scene.broker._world.ground.get(entity.ref)
                if item is not None and item.source_ref.uid in killed and item.owner_uid == bot.self_uid:
                    dropped.add(uid)
                    ground_origins[uid] = dict(source_npc_uid=item.source_ref.uid,
                        source_generation=item.source_ref.generation, owner_uid=item.owner_uid,
                        template=item.item_id, count=item.count, grade=item.grade,
                        map_id=item.map_id, position=(item.x, item.y))
            living = [(uid, actor) for uid, actor in bot.actors.items()
                      if uid in appeared and actor['alive']]
            loot = [(uid, item) for uid, item in bot.ground.items() if uid in dropped]
            if loot:
                uid, item = min(loot, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, item['position']) <= 1:
                    before = bot.pickups
                    await bot.pickup(uid)
                    if bot.pickups > before:
                        picked.add(uid)
                else:
                    await bot.step(item['position'], radius=1)
            elif living:
                uid, actor = min(living, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, actor['position']) <= 1:
                    await bot.attack(uid)
                else:
                    await bot.step(actor['position'], radius=1)
            else:
                await bot.step(((group.rect.x1 + group.rect.x2) // 2,
                                (group.rect.y1 + group.rect.y2) // 2), radius=1)
            if time.monotonic() - bot.last_alive >= 1:
                await bot.alive()
            if appeared and killed and dropped and picked and bot.moves and bot.swings:
                break
            await asyncio.sleep(.05)
        evidence.update(appeared_uids=sorted(appeared), killed_uids=sorted(killed),
            actual_ground_uids=sorted(dropped), picked_ground_uids=sorted(picked),
            ground_origins=ground_origins,
            moves=bot.moves, swings=bot.swings, pickups=bot.pickups,
            frames=dict(bot.frame_counts), request_counts=dict(bot.request_counts),
            handler_errors=list(scene.broker._world_handler_errors))
        if not (appeared and killed and dropped and picked and bot.moves and bot.swings):
            raise hb.BotFailure('NEW_GROUP_APPEAR_MOVE_COMBAT_DROP_PICKUP_REQUIRED')
        stage = 'saved_pickup_delta'
        saved_after, expected_delta = saved_counts(), Counter()
        for uid in picked:
            item = ground_origins[uid]
            expected_delta[item['template']] += item['count']
        actual_delta = saved_after.copy()
        actual_delta.subtract(saved_before)
        evidence.update(saved_pickup_delta={k: v for k, v in actual_delta.items() if v},
                        expected_pickup_delta=dict(expected_delta))
        if +actual_delta != expected_delta or any(v < 0 for v in actual_delta.values()):
            raise hb.BotFailure('PICKUP_SAVED_DELTA_MISMATCH')
        stage = 'observations_complete'
    except Exception as failure:
        error = f'{type(failure).__name__}: {failure}'
        partial = scene.bot
        if partial is not None:
            evidence['partial_at_failure'] = dict(map_id=partial.map_id,
                position=partial.position, hp=partial.hp, moves=partial.moves,
                swings=partial.swings, observed_kills=sorted(partial.kills),
                received_actors=partial.actors, ground_seen=sorted(partial.ground_seen),
                pickups=partial.pickups, frame_counts=dict(partial.frame_counts),
                request_counts=dict(partial.request_counts),
                appeared_group_uids=sorted(locals().get('appeared', ())),
                killed_group_uids=sorted(locals().get('killed', ())),
                ground_origins=locals().get('ground_origins', {}))
        if isinstance(failure, scenarios.IncompleteCleanup):
            closed = False
    finally:
        if broker is not None:
            closed = (await broker.close())['cleanup_complete']
        scene_closed = await scene.close()
        closed = closed and scene_closed
    source_hashes = {str(p.relative_to(Path(__file__).resolve().parents[2])):
        hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (gd.M1_DATA_DIR / 'monsters.json', gd.M1_DATA_DIR / 'spawns.json',
                  gd.M1_DATA_DIR / 'drops.json')}
    result = dict(status='SUCCESS' if error is None and closed else 'FAILED', error=error,
        stopped_stage=stage,
        scope='fresh loopback development fixture, real FIRST/login/select and ordered socket combat/loot; native/UI unverified',
        group=group.group_id, template=group.template_id, monster=data.monsters[group.template_id].name_ko,
        profile_path=str(directory), evidence=evidence, epochs=scene.epochs,
        cleanup_complete=closed, source_hashes=source_hashes)
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', required=True, help='explicit new map0 spawn group identifier')
    parser.add_argument('--seconds', type=hb.positive, default=120)
    parser.add_argument('--timeout', type=hb.positive, default=8)
    result = asyncio.run(run(parser.parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
