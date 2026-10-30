"""Owned-ticket map70 voyage and one real received-actor hunt over loopback.

The ticket is supplied in a fresh pre-login development save. Isbal's original
client NPC template is still unknown, so this case cannot establish purchase.
No original game client or input automation is used.
"""
from __future__ import annotations

import asyncio
from collections import deque
import hashlib
import json
from pathlib import Path
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix


class ShipScenario(matrix.Matrix):
    def __init__(self, args, directory):
        # Reuse the existing levelled dungeon fixture and long S32 navigator.
        super().__init__(args, 'dungeon_items', directory)
        self.map_start = (4, 33426, 33502)
        from tools.local_original_session.world_feature_dungeons import load_island_policy
        self.transitions = load_island_policy().transitions
        self._planned_steps = deque()
        self._planned_key = None

    def travel_heading(self, goal, radius, *, require_reached=False, ignore_actors=False):
        if self.bot.map_id == 70:
            # The island's S32 tm1..tm4 links join disconnected walking areas.
            # Reuse the existing link-aware client planner; each move still
            # goes through the ordinary packet/current/terrain checks.
            from tools.local_original_session.hunt_bot_dungeons import DungeonScenario
            return DungeonScenario.travel_heading(self, goal, radius,
                require_reached=require_reached, ignore_actors=ignore_actors)
        return super().travel_heading(goal, radius,
            require_reached=require_reached, ignore_actors=ignore_actors)

    def initialize_hunt_fixture(self):
        from tools.local_original_session import equipment_store, inventory
        from tools.local_original_session.hunt_bot_dungeons import DungeonScenario
        from tools.local_original_session.world_enchant_inventory import enchanted_name

        DungeonScenario.initialize_hunt_fixture(self)
        data = self.broker._world.data
        original = [dict(item.raw_fields) for item in
                    inventory.validate_kit_frame(self.broker._inventory_kit_frame(1))]
        rows = [dict(row) for row in original]
        for row in rows:
            template = row[2] & 0xffffffff
            definition = data.items.get(template)
            if definition is not None and template in (3, 117, 89, 98, 104, 109, 128, 129):
                row[18] = enchanted_name(definition, 9 if definition.kind == 'weapon' else 6)
            if template == 14:
                row[4] = 200
            if template in (17, 296):
                row[4] = 10
        ticket = dict(rows[0])
        ticket.update({1: max(row[1] for row in rows) + 1, 2: 12017,
                       4: 1, 7: 138, 18: b''})
        rows.append(ticket)
        frame = inventory.build_kit_frame(rows)
        self.store.grant(1, frame)
        by_template = {row[2] & 0xffffffff: row for row in rows}
        equipped = [entry.template_id for entry in data.starter.entries(1, 'test_knight')
                    if entry.equipped]
        self.equipment.initialize_kit(1, frame,
            initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=by_template[3][1],
            slots=tuple((data.items[template].slot_key, by_template[template][1])
                        for template in equipped if data.items[template].kind == 'armor'))
        self.fixture_notes.append(dict(ticket_template=12017, ticket_uid=ticket[1],
            ticket_count=1, level=self.args.fixture_level, gear='+9 weapon/+6 armor',
            potion14=200, haste17=10, brave296=10,
            scope='fresh pre-login development save; no shop purchase or natural ticket acquisition claim'))

    def saved_ticket_count(self):
        from tools.local_original_session import inventory
        frame = self.store.restore(self.bot.self_uid)
        return sum(dict(item.raw_fields)[4] for item in inventory.validate_kit_frame(frame)
                   if item.template_bits == 12017)

    def saved_position(self):
        from tools.local_original_session import movement
        return self.broker.realm.positions.restore(
            movement.Position(self.bot.self_uid, self.bot.character, 0, 0, 0))

    async def wait_for_map(self, marker, map_id):
        def ready(batch):
            changed = next((frame for frame in batch if frame.opcode == 0x4e95
                            and hb.scalar(frame.values, 1) == map_id), None)
            if changed is None:
                return None
            return next((frame for frame in batch if frame.ordinal > changed.ordinal
                         and frame.opcode == 0x4e96
                         and hb.scalar(frame.values, 2) == self.bot.self_uid), None)
        await self.bot.peer.wait(marker, ready, f'SHIP_MAP_{map_id}', timeout=360)
        await self.bot.alive()

    async def dungeon_items(self):
        bot = self.bot
        self.stage = 'pre_boarding'
        self.record('owned_pre_login_ticket', self.saved_ticket_count() == 1
                    and any(row.get(2) == 12017 and row.get(4) == 1
                            for row in bot.inventory.values()),
                    scope='explicit fresh development ticket only; Isbal purchase unavailable')
        for template in (17, 296):
            if any(row.get(2) == template and row.get(4, 0) > 0
                   for row in bot.inventory.values()):
                await self.use(template)

        self.stage = 'board_4ef8'
        marker = bot.peer.ordinal
        await self.barrier(0x4ef8, hb.uint(1, 4), label='SHIP_KEY4_BOARD_AND_ALIVE')
        self.record('waiting_at_dock_without_debit', bot.map_id == 4
                    and self.saved_ticket_count() == 1,
                    route_key=4, dock=(4, *bot.position),
                    scope='real decoder/router 4EF8; Alive is only an ordered processing barrier')

        self.stage = 'scheduled_departure'
        await self.wait_for_map(marker, 83)
        self.record('scheduled_map83_position_saved', bot.map_id == 83
                    and self.saved_position().map_id == 83
                    and self.saved_ticket_count() == 1,
                    position=(bot.map_id, *bot.position))

        self.stage = 'scheduled_arrival'
        marker = bot.peer.ordinal
        await self.wait_for_map(marker, 70)
        x, y = bot.position
        saved = self.saved_position()
        self.record('map70_arrival_and_one_ticket_debit_saved',
                    bot.map_id == saved.map_id == 70
                    and (x, y) == (saved.word0, saved.word1)
                    and abs(x - 32937) <= 7 and abs(y - 33042) <= 7
                    and self.saved_ticket_count() == 0,
                    position=(70, x, y), ticket_after=self.saved_ticket_count())

        self.stage = 'received_island_hunt'
        before = set(bot.kills)
        await self.hunt_count(kills=1, pickups=0, seconds=self.args.hunt_timeout)
        self.record('map70_received_target_killed', bot.map_id == 70
                    and bool(bot.kills - before), killed_uids=sorted(bot.kills - before))

        self.stage = 'return_scroll_162'
        await self.use(162)
        saved = self.saved_position()
        self.record('return_map4_position_saved', bot.map_id == saved.map_id == 4
                    and bot.position == (saved.word0, saved.word1),
                    position=(bot.map_id, *bot.position), ticket_after=self.saved_ticket_count())


def parser():
    args = matrix.parser()
    args.description = __doc__
    args.set_defaults(scenario='dungeon_items', hunt_timeout=600,
                      navigation_timeout=1200, minutes=12)
    args.add_argument('--fixture-level', type=int, default=60, choices=range(1, 61))
    args.add_argument('--output-root', type=Path, default=Path('_work/ship-bot'))
    return args


async def run(args):
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    directory = root / ('ship-' + uuid.uuid4().hex)
    directory.mkdir()
    workspace = Path(__file__).resolve().parents[2]
    inputs = (Path(__file__), Path(__file__).with_name('hunt_bot_dungeons.py'),
              Path(__file__).parent / 'data/m1/items_ext/ship_tickets.json',
              Path(__file__).with_name('world_feature_ship.py'),
              Path(__file__).with_name('world_feature_dungeons.py'),
              Path(__file__).with_name('world_terrain.py'),
              Path(__file__).with_name('data') / 'm6/ship_routes.json',
              Path(__file__).with_name('data') / 'm6/forgotten_island_spawns.json',
              *(workspace / 'work/local_resource_provider/assets/map/83').glob('*.s32'))
    for path in inputs:
        matrix.SOURCE_SHA256[str(path.relative_to(workspace))] = dict(file=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            basis='selected LOCAL ship scenario source at test start')
    scenario = ShipScenario(args, directory)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=0,
            SL_DISABLE_FEATURES='', SL_EXPERIMENT_SHOP=1,
            SL_COMPANION=0, SL_COMPANION_PET_UI=0, SL_SPELL_EXP=0,
            SL_COMPANION_REVIVE_EXP=0):
        result = await scenario.run_matrix()
    result['ticket_purchase_scope'] = 'UNRUN_ORIGINAL_ISBAL_TEMPLATE_UNKNOWN'
    result['route_scope'] = 'LOCAL five-minute departure/arrival; real packet path and saved owned-ticket fixture'
    (directory / 'result.json').write_text(
        json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps({key: result[key] for key in
        ('status', 'directory', 'failure', 'gaps', 'cleanup_complete', 'requests')}, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
