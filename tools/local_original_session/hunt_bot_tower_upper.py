"""Upper tower ordered socket scenarios; never launches a game client.

Fresh retained test profiles and pre-login supplies reuse Matrix's normal
FIRST/login/select/world, inventory UID delivery, decoder/router, and Quit.
15430 reuse includes an explicitly marked between-epoch position fixture;
it does not claim a walk from town back to the amulet's permitted area.
"""
from __future__ import annotations

import asyncio
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot_map_expansion2 as expansion
from tools.local_original_session import hunt_bot_dungeons as dungeon
from tools.local_original_session import world_maps, test_ports

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).parent / 'data/m6/map_expansion6.json'
UPPER = frozenset(range(111, 121))
AMULET_START = (101, 32818, 32780)
ARRIVAL = (111, 32669, 32814)


def upper_edges(transitions):
    """Keep only actual supplied directed upper-floor transitions."""
    return [(origin, row) for origin, row in transitions.items()
            if origin[0] in UPPER and row.destination.map_id in UPPER
            and row.destination.map_id != origin[0]]


class TowerScenario(expansion.ExpansionScenario):
    def __init__(self, args, case, directory, transitions, policy):
        matrix.Matrix.__init__(self, args, 'dungeon_items', directory)
        self.case, self.family = case, case['case_id']
        self.transitions, self.dungeon_policy = transitions, policy
        self._planned_steps, self._planned_key, self.stair_history = deque(), None, []
        self.danger_return = None
        self.entry = case['edge']
        self.map_start = tuple(case['start'])

    def record(self, name, ok, **fields):
        if name == 'outside_entrance_saved_map_fixture' and self.case['kind'] == 'item':
            name = 'item_departure_saved_map_fixture'
            ok = (self.bot.map_id, *self.bot.position) == self.map_start
            fields['scope'] = 'fresh pre-login item departure position, not a stair entrance or actual return travel'
        return super().record(name, ok, **fields)

    def initialize_hunt_fixture(self):
        dungeon.DungeonScenario.initialize_hunt_fixture(self)
        if self.case['kind'] != 'item':
            return
        from tools.local_original_session import inventory
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(
            self.broker._inventory_kit_frame(1))]
        template = self.case['template']
        definition = self.broker._world.data.items[template]
        # Reuse ordinary starter issuance's next available UID, persisted by
        # InventoryStore.grant before login. Never forge a live inventory row.
        uid = max(row[1] for row in rows) + 1
        row = dict(rows[0])
        row.update({1: uid, 2: template, 4: 2 if template == 15410 else 1,
                    7: definition.icon, 18: b''})
        rows.append(row)
        self.store.grant(1, inventory.build_kit_frame(rows))
        self.fixture_notes.append(dict(pre_login_item=template, uid=uid, count=row[4],
            scope='finite test supply through existing grant; natural acquisition unverified'))

    async def use(self, template, **options):
        if template != 15430:
            return await super().use(template, **options)
        await asyncio.sleep(.2)
        uid, row = self.item(template)
        before = row[4]
        batch = await self.barrier(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, matrix.RAW0),
                                  label='USE_REUSABLE_15430')
        after = self.bot.inventory.get(uid, {}).get(4, 0)
        self.record('use_15430_quantity', before == after == 1, uid=uid,
                    before=before, after=after, errors=self.error_codes())
        return batch

    def observe_placement(self):
        """Static group and runtime existence only; never implies a kill."""
        bot, world = self.bot, self.broker._world
        groups = [g for g in world.data.spawns if g.map_id == bot.map_id]
        expected = {g.template_id for g in groups}
        present = [dict(uid=e.uid, template=e.template_id, position=(e.x, e.y), alive=e.alive)
                   for e in world.entities if e.map_id == bot.map_id and e.template_id in expected]
        received = [dict(uid=u, **a) for u, a in bot.actors.items() if a['template'] in expected]
        self.record('floor_placement_configured', bool(groups) if bot.map_id not in (111, 116) else not groups,
                    map_id=bot.map_id, group_ids=[g.group_id for g in groups],
                    template_ids=sorted(expected), runtime_entities=present, received_actors=received,
                    scope='configured placement/runtime existence; received actors only within interest; no kill or all-species combat claim',
                    non_hunting_reason='source insufficient' if not groups else None)

    async def walk_and_observe(self):
        bot = self.bot
        self.stage = 'upper_floor_walk'
        before, moves = bot.position, bot.moves
        for heading, (dx, dy) in enumerate(hb.DELTAS):
            point = before[0] + dx, before[1] + dy
            if ((bot.map_id, *point) not in self.transitions and
                    self.broker._world.terrain.can_step(bot.map_id, *before, heading) is True):
                await self.navigate(point)
                break
        self.record('upper_floor_walk', bot.position != before and bot.moves > moves,
                    map_id=bot.map_id, before=before, after=bot.position)
        self.observe_placement()

    def verify_arrival(self, batch, label):
        map_frame = hb.find(batch, 0x4e95, **{'1': ARRIVAL[0]})
        status = None if map_frame is None else hb.find(
            [f for f in batch if f.ordinal > map_frame.ordinal], 0x4e38, **{'1': self.bot.self_uid})
        actor = None if status is None else hb.find(
            [f for f in batch if f.ordinal > status.ordinal], 0x4e96, **{'2': self.bot.self_uid})
        self.record(label, (self.bot.map_id, *self.bot.position) == ARRIVAL and actor is not None,
                    expected=ARRIVAL, actual=(self.bot.map_id, *self.bot.position),
                    map_status_self_ordinals=[None if f is None else f.ordinal for f in (map_frame, status, actor)],
                    scope='LOCAL destination policy; exact original item-coordinate causal contract unverified')
        if (self.bot.map_id, *self.bot.position) != ARRIVAL:
            raise hb.BotFailure('UPPER_ITEM_ARRIVAL_NOT_OBSERVED')

    def saved_inventory_row(self, uid):
        from tools.local_original_session import inventory
        return next((dict(i.raw_fields) for i in inventory.validate_kit_frame(
            self.store.restore(self.bot.self_uid)) if i.identifier == uid), {})

    async def item_visit(self, ordinal):
        self.stage = f'item_visit_{ordinal}'
        template = self.case['template']
        uid, row = self.item(template)
        before = row[4]
        batch = await self.use(template)
        self.verify_arrival(batch, f'item_{template}_arrival_{ordinal}')
        saved = self.saved_inventory_row(uid)
        self.record(f'item_{template}_quantity_saved_{ordinal}',
                    saved.get(4, 0) == before - (template == 15410),
                    uid=uid, before=before, saved_count=saved.get(4, 0))
        await self.walk_and_observe()
        await self.return_to_safety()
        return uid

    async def dungeon_items(self):
        if self.case['kind'] == 'stair':
            self.observe_placement()
            await self.cross(self.entry, 'upper_actual_s32_stair')
            await self.walk_and_observe()
            await self.return_to_safety()
            return
        first_uid = await self.item_visit(1)
        if self.case['template'] != 15430:
            return
        uid, character = self.bot.self_uid, self.bot.character
        await self.close()
        if not self.cleanup_ok:
            raise hb.BotFailure('FIRST_AMULET_EPOCH_CLEANUP_INCOMPLETE')
        preserved = self.directory / 'epoch1-closed'
        preserved.mkdir()
        for path in self.directory.iterdir():
            if path.is_file():
                shutil.copy2(path, preserved / path.name)
        from tools.local_original_session import movement
        # The broker's bridge wraps its PositionStore with a persist queue
        # which is closed by Quit. Use the ordinary store only while offline.
        positions = movement.PositionStore((self.directory / 'characters.json').resolve())
        current = positions.restore(movement.Position(uid, character, 0, 0, 0))
        positions.commit(current, movement.Position(uid, character, *AMULET_START),
                         transition=current.map_id != AMULET_START[0])
        self.fixture_notes.append(dict(between_epoch_position_fixture=AMULET_START,
            previous_position=(current.map_id, current.word0, current.word1),
            scope='test save only after normal Quit; explicit pre-login relocation, not actual return travel'))
        await self.open(seed=False)
        received_uid, row = self.item(15430)
        self.record('amulet_same_uid_reconnect', received_uid == first_uid and row[4] == 1,
                    first_uid=first_uid, received_uid=received_uid, quantity=row[4])
        second_uid = await self.item_visit(2)
        self.record('amulet_two_successful_uses', second_uid == first_uid,
                    uid=first_uid, successful_visits=2,
                    scope='same retained UID across two normal login epochs; explicit between-epoch position fixture')


def cases_for(transitions, terrain):
    placeholder = ((101, 32818, 32780), world_maps.MapTransition(
        world_maps.MapDestination(*ARRIVAL, 4), 'item fixture', 'LOCAL fixture', 'UNKNOWN'))
    cases = [dict(case_id='scroll15410', kind='item', template=15410, map_id=111,
                  combat=False, start=(0, 32595, 32906), edge=placeholder),
             dict(case_id='amulet15430_reuse', kind='item', template=15430, map_id=111,
                  combat=False, start=AMULET_START, edge=placeholder)]
    # One fixture per directed stair avoids inventing traversability through
    # disconnected S32 floor geometry. Every transition still takes real steps.
    for index, edge in enumerate(upper_edges(transitions)):
        origin, row = edge
        cases.append(dict(case_id=f'stair_{origin[0]}_to_{row.destination.map_id}_{index}',
            kind='stair', map_id=row.destination.map_id, combat=False, edge=edge,
            start=dungeon.entrance_start(terrain, origin, transitions)))
    return cases


def parser():
    cli = expansion.parser()
    cli.description = __doc__
    cli.set_defaults(output_root=ROOT / '_work/tower_upper', navigation_timeout=120)
    return cli


async def run(args):
    from tools.local_original_session.world_terrain import WorldTerrain
    from tools.local_original_session import world_feature_items, world_item_effects, world_feature_dungeons, world_terrain
    policy = world_maps.load_dungeon_policy()
    transitions = dict(world_maps.TRANSITIONS) | dict(policy.transitions)
    terrain = WorldTerrain.load(map_ids=UPPER)
    cases = cases_for(transitions, terrain)
    if args.case != 'all':
        wanted = set(args.case.split(','))
        cases = [c for c in cases if c['case_id'] in wanted]
        if {c['case_id'] for c in cases} != wanted:
            raise ValueError('Unknown case selection: ' + args.case)
    root = args.output_root.resolve()
    if not root.is_relative_to((ROOT / '_work/tower_upper').resolve()):
        raise ValueError('Tower output must remain below _work/tower_upper')
    root.mkdir(parents=True, exist_ok=True)
    directory = root / ('run-' + uuid.uuid4().hex[:12])
    directory.mkdir()
    inputs = [Path(__file__), DATA, DATA.parent.parent/'m1/item_effects.json',
              Path(world_maps.__file__), Path(world_feature_items.__file__),
              Path(world_item_effects.__file__), Path(world_feature_dungeons.__file__),
              Path(world_terrain.__file__),
              Path(expansion.__file__), Path(dungeon.__file__)]
    for path in inputs:
        matrix.SOURCE_SHA256[str(path)] = dict(file=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), basis='tower startup provenance')
    results = []
    for case in cases:
        profile = directory / case['case_id']
        profile.mkdir()
        scenario = TowerScenario(args, case, profile, transitions, policy)
        print('START ' + case['case_id'], flush=True)
        with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_SHOP=1, SL_COMPANION=0,
                SL_COMPANION_PET_UI=0, SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
            result = await scenario.run_matrix()
        result['case_id'] = case['case_id']
        result['stair_history'] = scenario.stair_history
        (profile/'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
        results.append(result)
        print(f"{result['status']} {case['case_id']}: requests={result['requests']} failure={result['failure']}", flush=True)
        if not result['cleanup_complete']:
            break
    summary = dict(output_directory=str(directory), counts=dict(Counter(r['status'] for r in results)),
        physical_ports=test_ports.listener_ports(), results=results,
        scope='LOCAL ordered decoder/router packets on retained pre-login Lv60 fixtures. All real S32 directed stairs tested separately. Explicit item supplies and amulet between-epoch relocation; no acquisition, connected whole-tower route, kill, native input/rendering or original-equivalence claim.')
    (directory/'summary.json').write_text(json.dumps(matrix.safe(summary), ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps({k: result[k] for k in ('output_directory', 'counts')}, ensure_ascii=False))
    return 0 if set(result['counts']) == {'PASS'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
