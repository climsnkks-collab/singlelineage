"""Selected native crafting recipes on a retained fresh LOCAL socket test save.

FIRST/login/select/world, issued NPC UID, 4E43/4E44 and normal Quit/reconnect
reuse M5/Matrix. Materials are explicit pre-login LOCAL fixture supplies, never
normal acquisition evidence. No original client runs. request_craft is a
client-local command, not a 4ED4 action; unavailable native DTOs are SKIP.
Import/help do not open listeners or modify saves.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session.hunt_bot_m5 import M5Scenario


def refresh_local_inventory_observation(broker):
    """Reobserve the existing LOCAL owner after the physical pre-write read.

    Matrix's RAM peer can spend longer than the existing 250ms freshness window
    in that read. Reuse broker._sample (its current owner/source callbacks),
    then let the unchanged policy check the newly produced sample normally.
    No timestamp, freshness limit, saved state or native readiness is edited.
    """
    pending = {}
    before_send = broker._inventory_before_send
    policy_sample = broker._policy_sample

    async def observed_before_send(writer, row, *args, **kwargs):
        wire = await before_send(writer, row, *args, **kwargs)
        pending[id(row)] = await broker._sample(row)
        return wire

    def current_policy_sample(row, operation, *args, **kwargs):
        if getattr(operation, '__self__', None) is broker.policy and getattr(operation, '__name__', '') == 'begin_write':
            observed = pending.pop(id(row), None)
            if observed is not None:
                args = (args[0], observed, *args[2:])
        return policy_sample(row, operation, *args, **kwargs)

    broker._inventory_before_send = observed_before_send
    broker._policy_sample = current_policy_sample


class CraftScenario(M5Scenario):
    def __init__(self, args, directory):
        super().__init__(args, directory)
        self.name = 'craft'
        self.map_start = (4, 33438, 32796)
        self.town_id = 'giran'
        raw = json.loads((Path(__file__).parent / 'data/crafting.json').read_text(encoding='utf-8'))
        selected = args.recipes.split(',')
        by_id = {row['id']: row for row in raw['recipes']}
        if not selected or any(key not in by_id for key in selected):
            raise ValueError('CRAFT_BOT_REGISTERED_RECIPE_IDS_REQUIRED')
        self.recipe_set = tuple(by_id[key] for key in selected)
        self.craft_npcs = {npc['npc_template_id']: npc for npc in raw['npcs']}
        if any(self.craft_npcs[row['npc_template_id']]['menu_stem'] is None for row in self.recipe_set):
            raise matrix.MissingFeature('CRAFT_BOT_RETAINED_NATIVE_MENU_REQUIRED')
        self.start_source = None
        start_recipe = getattr(args, 'start_near_recipe', None)
        if start_recipe is not None:
            if start_recipe not in selected:
                raise ValueError('CRAFT_BOT_START_RECIPE_MUST_BE_SELECTED')
            from tools.local_original_session.world_terrain import WorldTerrain, DELTAS
            definition = self.craft_npcs[by_id[start_recipe]['npc_template_id']]
            map_id, x, y = definition['map_id'], definition['x'], definition['y']
            terrain = WorldTerrain.load(map_ids=(map_id,))
            start = next(((x + dx, y + dy) for dx, dy in DELTAS
                          if terrain.can_stand(map_id, x + dx, y + dy) is True), None)
            if start is None:
                raise matrix.MissingFeature('CRAFT_BOT_SOURCE_LOCATION_NEIGHBOUR_UNAVAILABLE')
            self.map_start = (map_id, *start)
            self.town_id = definition['id']
            self.start_source = dict(recipe=start_recipe, npc_template_id=definition['npc_template_id'],
                source_placement=(map_id, x, y), starting_position=self.map_start,
                sources=definition['sources'],
                policy='fresh pre-login LOCAL saved position on adjacent client-S32 standable cell; no public travel or normal material acquisition claim')

    def instrument(self):
        super().instrument()
        refresh_local_inventory_observation(self.broker)
        if self.seed_fixture:
            if self.start_source is not None:
                self.fixture_notes.append(dict(pre_login_craft_source_position=self.start_source))
            self.initialize_craft_fixture()

    def initialize_craft_fixture(self):
        """Append exact selected catalog supplies to this fresh saved kit only."""
        from tools.local_original_session import inventory
        frame = self.store.restore(1)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        uid = max(row[1] for row in rows)
        supplies = []
        policies = self.broker._world_handler_bindings.item_policies
        materials = Counter()
        for recipe in self.recipe_set:
            for material in recipe['materials']:
                materials[material['template_id']] += material['quantity']
        for template, quantity in materials.items():
            policy = policies.get(template)
            if policy is None or policy.grant_fields is None:
                raise matrix.MissingFeature(f'CRAFT_FIXTURE_MATERIAL_POLICY_REQUIRED:{template}')
            held = next((row for row in rows if policy.stackable
                         and row[2] & 0xffffffff == template
                         and all(row.get(n) == value for n, value in policy.grant_fields.items()
                                 if n not in (1, 4, 18))), None)
            if held is not None:
                held[4] += quantity
                supplies.append(dict(uid=held[1], template_id=template, quantity=quantity,
                                     existing_stack=True))
            else:
                for amount in ((quantity,) if policy.stackable else (1,) * quantity):
                    uid += 1
                    rows.append({**policy.grant_fields, 1: uid, 4: amount})
                    supplies.append(dict(uid=uid, template_id=template, quantity=amount))
        self.broker._world_inventory_transactions.commit_inventory(
            1, frame, inventory.build_kit_frame(rows), append=True)
        self.fixture_notes.append(dict(pre_login_crafting_materials=supplies,
            recipes=[dict(id=recipe['id'], native_recipe_id=recipe['native_recipe_id'], sources=recipe['sources'])
                     for recipe in self.recipe_set],
            producer='existing KitItemPolicy.grant_fields + fresh saved-kit UID suffix + core InventoryTransactions.commit_inventory append CAS',
            scope='LOCAL starting-save supplies only; initial material acquisition and original input/rendering are unverified'))

    async def open(self, *, seed, character=None, deliver=True):
        try:
            await super().open(seed=seed, character=character, deliver=deliver)
        finally:
            self.name = 'craft'

    def wire_counts(self):
        result = Counter()
        for row in self.bot.inventory.values():
            result[row[2] & 0xffffffff] += row[4]
        return result

    async def craft_one(self, recipe):
        definition = self.craft_npcs[recipe['npc_template_id']]
        label = recipe['id']
        self.stage = label + '_current_npc_menu'
        before = self.saved_counts()
        npc = await self.approach(recipe['l1j_npc_id'])
        actor = next((frame for frame in reversed(self.bot.peer.frames)
                      if frame.opcode == 0x4e96
                      and hb.scalar(frame.values, 2, 0) & 0xffffffff == npc.uid), None)
        self.record(label + '_actor_native_craft_template', actor is not None
                    and hb.scalar(actor.values, 39) == recipe['npc_template_id'],
            npc_uid=npc.uid, native_template=None if actor is None else hb.scalar(actor.values, 39),
            producer='actor f39→Actor+3C→hypertext consumer→UML+3C→native craft_output catalog')
        batch = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
            check=lambda frames: hb.find(frames, 0x4e44), label=label + '_CLICK')
        menu = hb.find(batch, 0x4e44).values
        self.record(label + '_current_issued_menu',
            hb.scalar(menu, 2) == definition['menu_stem'].encode('utf-8')
            and hb.scalar(menu, 1) & 0xffffffff == npc.uid,
            npc_uid=npc.uid, menu=menu,
            scope='real click decoder/router/menu; native rendering/input unverified')
        self.record(label + '_menu_does_not_consume_inventory', self.saved_counts() == before,
            counts=dict(before))
        self.stage = label + '_client_local_recipe_selection'
        native_id = recipe['native_recipe_id']
        self.record(label + '_catalog_recipe_selected', native_id in definition['native_recipe_ids'],
            native_npc_template=recipe['npc_template_id'], native_recipe_ids=definition['native_recipe_ids'],
            selected_recipe=native_id, selected_result=recipe['result'],
            navigation=f"{definition['menu_stem']} craft_output→{definition['detail_stem']} craft_input is client-local; no 4ED4",
            scope='retained craft.bin/npccraftlist.bin selection metadata; no native UI execution')
        inputs = tuple((int(entry['fields']['3']), int(entry['fields']['1']),
                        int(entry['fields']['2']), int(entry['fields']['4']),
                        int(entry['fields']['5']))
                       for entry in recipe['native_catalog']['inputs'])
        # 5c4520's typed producer: f1 uses the issued NPC UID, f2 the selected
        # native recipe, f3 quantity, f4 the source-owned slot rows. No handler
        # or provider is invoked directly by this bot.
        payload = hb.uint(1, hb.scalar(menu, 1) & 0xffffffff) + hb.uint(2, native_id) + hb.uint(3, 1)
        for selected in inputs:
            payload += hb.pb.encode_bytes(4, b''.join(hb.uint(n, value)
                for n, value in enumerate(selected, 1)))
        self.stage = label + '_native_request5'
        batch = await self.bot.peer.request(0x0005, payload,
            check=lambda frames: hb.find(frames, 0x0006), label=label + '_NATIVE_CRAFT')
        ack = hb.find(batch, 0x0006)
        values = hb.fields(ack.wire[4:-2])
        self.record(label + '_ack6_explicit_success', hb.scalar(values, 1, None) == 0,
            ack_fields=values, selected_recipe=native_id,
            native_consumer='4d1a10 explicit enum0 selects detail_stem_s; original UI unexecuted')
        expected = before.copy()
        for material in recipe['materials']:
            expected[material['template_id']] -= material['quantity']
        expected[recipe['result']['template_id']] += recipe['result']['quantity']
        after = self.saved_counts()
        self.record(label + '_materials_consumed_result_received_and_saved',
            after == expected == self.wire_counts(), before=dict(before), after=dict(after),
            inputs=inputs, received_opcodes=[f'0x{frame.opcode:04X}' for frame in batch],
            scope='LOCAL fixture supplies; exact native request fields through real decoder/router/core CAS')
        return after

    async def craft(self):
        for recipe in self.recipe_set:
            after = await self.craft_one(recipe)
        self.stage = 'craft_quit_reconnect_preservation'
        character, position = self.bot.character, self.position_snapshot()
        self.record('craft_normal_quit', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('CRAFT_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        self.record('crafted_inventory_position_restored',
            self.saved_counts() == after == self.wire_counts() and self.position_snapshot() == position,
            counts=dict(self.saved_counts()), position=self.position_snapshot(),
            scope='same retained LOCAL saved-map fixture; no grant on reconnect')
        self.record('craft_no_handler_errors', not any(self.error_codes().values()),
            errors=self.error_codes())


def parser():
    result = matrix.parser()
    result.description = __doc__
    result.set_defaults(scenario='craft', navigation_timeout=180)
    result.add_argument('--recipes', default='moria_magician_cap',
        help='comma-separated registered crafting.json recipe IDs, executed in order')
    result.add_argument('--start-near-recipe',
        help='selected recipe ID whose original NPC placement supplies a fresh LOCAL saved-position fixture; default retains Giran')
    next(action for action in result._actions if action.dest == 'scenario').choices = ('craft',)
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='craft-bot-', dir=root))
    scene = CraftScenario(args, directory)
    source_paths = ('hunt_bot_craft.py', 'hunt_bot_m5.py', 'hunt_bot_play_matrix.py',
        'world_craft.py', 'world_feature_craft.py', 'world_handlers.py',
        'data/crafting.json', 'data/m2/town_npcs.json', 'data/m5/town_npcs.json', 'data/m5/npc_menus.json')
    selected = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in source_paths if (Path(__file__).parent / name).is_file()}
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1, SL_EXPERIMENT_WAREHOUSE=1,
            SL_WORLD_TOWN_CANDIDATES='', SL_COMPANION=0, SL_SPELL_EXP=0,
            SL_COMPANION_PET_UI=0, SL_COMPANION_REVIVE_EXP=0):
        result = await scene.run_matrix()
    result.update(selected_source_sha256=selected,
        test_port_base=os.environ.get('SL_TEST_PORT_BASE', '12000'),
        starting_save=f'fresh M5 level5/test_knight saved-map LOCAL fixture at {scene.map_start}; exact selected recipe materials supplied before login',
        starting_position_source=scene.start_source,
        selected_recipes=[recipe['id'] for recipe in scene.recipe_set],
        native_craft='source-backed request5/ACK6 socket path; original craft_output/input rendering and local input unexecuted')
    (directory / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(dict(status=result['status'], directory=result['directory'],
        failure=result['failure'], gaps=result['gaps'], checks=len(result['checks']),
        requests=result['requests'], cleanup_complete=result['cleanup_complete']), ensure_ascii=False, indent=2))
    return 0 if result['status'] in ('PASS', 'SKIP') else 1


if __name__ == '__main__':
    raise SystemExit(main())
