"""Quest collection/exchange through FIRST and socket game requests.

Uses Matrix's retained fresh test_knight/LOCAL native-memory adapter and its
pre-login growth API on a saved map. Lyra prepares level12 without quest material,
reward, state, drop, live HP or RNG injection; materials must come from product
monster drops. Knight exchange prepares level15 and explicitly synthetic starting
materials639/633/650, then tests actual acceptance/consumption/reward651/652 and
restore. This latter scenario is socket development verification, not formal PASS
or proof of normal material acquisition.
Missing NPC/producer contracts are SKIP; a missing observation after an actual
supported request is FAIL. All saves, requests and failures remain under runs.
Packet success does not establish native input/rendering or Classic formulas.
Import/help do not bind ports or execute an original client.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session.hunt_bot_m5 import M5Scenario

QUEST_ID = 'mainland_lyra_totem_settlement'
NPC_ID = 70811
PRICES = {157: 200, 158: 100, 159: 50, 160: 30, 161: 50}


class QuestScenario(M5Scenario):
    def __init__(self, args, directory):
        super().__init__(args, directory)
        self.name = 'lyra'
        self.map_start = (4, 32744, 32429)
        self.acquisitions = []
        self.menu = None

    async def open(self, *, seed, character=None, deliver=True):
        # Matrix owns its ordinary pre-login hunt-fixture seam. It invokes our
        # pure growth initializer before starting FIRST; no live profile is set.
        self.seed_fixture = seed  # M5's inherited instrument() owns seed-only setup.
        self.name = 'dungeon_items' if seed else 'lyra'
        try:
            await matrix.Matrix.open(self, seed=seed, character=character, deliver=deliver)
        finally:
            self.name = 'lyra'
        if seed:
            self.fixture_notes.append(dict(
                quest_materials='none supplied; only product combat/drop/pickup may acquire totems',
                quest_state='fresh/unaccepted; no direct QuestStore commit',
                start_cell='map4/32744,32429 is standable in retained S32, next to LOCAL Lyra placement; old32746,32429 was fully blocked',
                start_scope='pre-login level12/test_knight saved-map fixture near Lyra; initial growth and public world travel are not tested'))

    def initialize_hunt_fixture(self):
        """Existing LOCAL pure growth -> pre-login ProgressStore, level12 only."""
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        data = load_m1()
        owner = next(row for row in self.broker.realm.store._read()['characters'] if row['class'] == 1)
        stats, level = owner['attributes'], getattr(self, 'fixture_level', 12)
        exp = data.pc_exp[level - 1]
        baseline = actor_hook.profiles()[0].fields
        profile = PcProfile(1, owner['class'], owner['gender'], stats[0], stats[1],
                            con=stats[2], wis=stats[3])
        growth = on_kill(RewardPcState(0, profile, baseline[11], baseline[13]),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x4f574e52), data=data)
        self.broker._world_progress.commit(owner['uid'], Progress(exp, level, growth.max_hp, growth.max_mp))
        self.fixture_notes.append(dict(pre_login_level=level, pre_login_exp=exp,
            pre_login_max_hp=growth.max_hp, pre_login_max_mp=growth.max_mp,
            reason=('Lv15 product Atuba is within the unchanged normal bot level+3 target ceiling'
                    if level == 12 else 'Fixed knight quest acceptance requires level15; pure pre-login development growth'),
            formula='existing LOCAL world_reward.on_kill pure growth then pre-login ProgressStore.commit',
            scope='temporary starting save; initial leveling/world travel excluded'))

    def quest_state(self):
        store = getattr(self.broker, '_world_quest_store', None)
        if store is None or QUEST_ID not in getattr(self.broker, '_world_quests', {}):
            raise matrix.MissingFeature('LYRA_PROMOTED_DEFINITION_AND_QUEST_STORE_REQUIRED')
        return store.get(self.bot.self_uid, QUEST_ID)

    def wire_counts(self):
        counts = Counter()
        for row in self.bot.inventory.values():
            counts[row[2] & 0xffffffff] += row[4]
        return counts

    async def click_lyra(self):
        npc = await self.approach(NPC_ID)
        batch = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
            check=lambda frames: hb.find(frames, 0x4e44), label='LYRA_CLICK')
        self.menu = hb.find(batch, 0x4e44).values
        self.record('lyra_received_menu', hb.scalar(self.menu, 2) == b'lyraEv1',
                    npc_uid=npc.uid, context=hb.scalar(self.menu, 1), stem='lyraEv1')

    async def menu_action(self, action, expected):
        if self.menu is None:
            raise hb.BotFailure('LYRA_RECEIVED_MENU_REQUIRED')
        stem = hb.scalar(self.menu, 2).decode('utf-8')
        dialogue = self.broker._world_quest_dialogues.get(NPC_ID)
        if dialogue is None or action not in dialogue.pages.get(stem, ()):
            raise matrix.MissingFeature(f'LYRA_ISSUED_ACTION_UNAVAILABLE:{stem}:{action}')
        payload = (hb.uint(1, hb.scalar(self.menu, 1))
            + hb.pb.encode_bytes(2, action.encode('utf-8')) + hb.uint(4, 0) + hb.uint(5, 0))
        batch = await self.bot.peer.request(0x4ed4, payload,
            check=lambda frames: hb.find(frames, 0x4e44), label='LYRA_' + action)
        self.menu = hb.find(batch, 0x4e44).values
        received = hb.scalar(self.menu, 2).decode('utf-8')
        self.record('lyra_menu_' + action, received == expected,
                    from_stem=stem, action=action, received=received)
        return batch

    async def acquire_totem(self):
        """Only current table-supported mobs and issued owned ground UIDs."""
        bot, data = self.bot, self.bot.data
        templates = {template for template, drops in data.drops.items()
                     if any(drop.item_id in PRICES and drop.chance > 0 for drop in drops)}
        groups = [g for g in data.spawns if g.map_id == bot.map_id and g.template_id in templates
                  and data.monsters[g.template_id].level <= (bot.level or 1) + 3]
        if not groups:
            raise matrix.MissingFeature('NO_CURRENT_LEVEL_APPROPRIATE_PRODUCT_TOTEM_DROP_SPAWN')
        self.record('normal_totem_producers_available', True,
            groups=[g.group_id for g in groups], templates=sorted(templates), player_level=bot.level,
            policy='current product chance/count/spawn/RNG unchanged; no fixture material grant')
        await self.gear()
        self.stage = 'normal_totem_collection'
        deadline = time.monotonic() + self.args.hunt_timeout
        before = self.saved_counts()
        while time.monotonic() < deadline:
            if bot.dead:
                raise hb.BotFailure('LYRA_OWNER_DIED_DURING_TOTEM_COLLECTION')
            if bot.hp < bot.max_hp * .6:
                await self.use(14)
            if await matrix.Matrix.retreat_threat(self):
                await asyncio.sleep(.03)
                continue
            drops = []
            for uid, row in bot.ground.items():
                entity = self.broker._world.entities.get(uid)
                item = None if entity is None else self.broker._world.ground.get(entity.ref)
                if (item is not None and item.owner_uid == bot.self_uid
                        and item.item_id in PRICES and item.source_ref.uid in bot.kills
                        and bot.pickup_refused[uid] < 3 and bot.safe_hunt_cell(row['position'])):
                    drops.append((uid, row, item))
            if drops:
                uid, row, item = min(drops, key=lambda p: hb.distance(bot.position, p[1]['position']))
                if hb.distance(bot.position, row['position']) <= 1:
                    marker, previous = bot.pickups, self.saved_counts()
                    evidence = dict(ground_uid=uid, source_uid=item.source_ref.uid,
                        source_generation=item.source_ref.generation, owner_uid=item.owner_uid,
                        template=item.item_id, count=item.count)
                    await bot.pickup(uid)
                    if bot.pickups > marker:
                        after = self.saved_counts()
                        expected = previous.copy()
                        expected[item.item_id] += item.count
                        self.record('normal_owned_totem_drop_pickup_saved',
                            after == expected and self.wire_counts() == after,
                            before=dict(previous), after=dict(after), **evidence)
                        self.acquisitions.append(evidence)
                        if any(after[t] > before[t] for t in PRICES):
                            return
                else:
                    await bot.step(row['position'], radius=1)
            else:
                targets = [(uid, row) for uid, row in bot.actors.items()
                           if row['template'] in templates and bot.hunt_target(row)]
                targets.sort(key=lambda p: hb.distance(bot.position, p[1]['position']))
                target = next((pair for pair in targets
                    if self.reachable_hunt_goal(pair[1]['position'], 1)), None)
                if target is not None:
                    uid, row = target
                    if hb.distance(bot.position, row['position']) <= 1:
                        await self.owner_attack_current(uid)
                    else:
                        await bot.step(row['position'], radius=1)
                else:
                    goals = [((g.rect.x1 + g.rect.x2)//2, (g.rect.y1 + g.rect.y2)//2) for g in groups]
                    goal = next((p for p in sorted(goals, key=lambda p: hb.distance(bot.position, p))
                                 if bot.safe_hunt_cell(p) and self.reachable_hunt_goal(p, 1)), None)
                    if goal is None or hb.distance(bot.position, goal) <= 1:
                        await bot.alive()
                    else:
                        await bot.step(goal, radius=1)
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.03)
        raise hb.BotFailure('LYRA_NORMAL_TOTEM_DROP_PICKUP_DEADLINE')

    async def lyra(self):
        self.stage = 'accept_lyra_contract'
        initial = self.quest_state()
        self.record('fresh_unaccepted_without_materials', not initial.accepted and not initial.completed
                    and not any(self.saved_counts()[t] for t in PRICES), state=dataclasses.asdict(initial))
        await self.click_lyra()
        await self.menu_action('queststart', 'lyraEv3')
        accepted = self.quest_state()
        self.record('lyra_acceptance_saved', accepted.accepted and not accepted.completed,
                    state=dataclasses.asdict(accepted))
        self.stage = 'normal_totem_collection'
        await self.acquire_totem()
        progressed = self.quest_state()
        self.record('lyra_collection_progress_saved', any(progressed.counts),
                    state=dataclasses.asdict(progressed), owned_counts=dict(self.saved_counts()))
        self.stage = 'lyra_variable_settlement'
        await self.click_lyra()
        await self.menu_action('queststart', 'lyraEv4')
        before = self.saved_counts()
        payout = sum(before[t] * price for t, price in PRICES.items())
        await self.menu_action('questExchange', 'lyraEv5')
        after, completed = self.saved_counts(), self.quest_state()
        expected = before.copy()
        for template in PRICES:
            expected.pop(template, None)
        expected[7] += payout
        self.record('lyra_all_owned_totems_consumed_exact_adena_saved', payout > 0
            and after == expected and after == self.wire_counts() and completed.completed
            and getattr(completed, 'cycles', 0) == getattr(accepted, 'cycles', 0) + 1,
            before=dict(before), after=dict(after), payout=payout,
            state=dataclasses.asdict(completed), acquisitions=self.acquisitions,
            receipt='Classic misc_quest_receipt dynamiclist UNKNOWN; ordinary quantity/add/remove frames only')
        self.stage = 'normal_quit_reconnect_settlement'
        character, saved_state, saved_position = self.bot.character, completed, self.position_snapshot()
        self.record('normal_quit_after_settlement', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('LYRA_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        self.record('lyra_settlement_restored_after_FIRST', self.quest_state() == saved_state
            and self.saved_counts() == after == self.wire_counts() and self.position_snapshot() == saved_position,
            state=dataclasses.asdict(self.quest_state()), inventory=dict(self.saved_counts()),
            scope='same preserved test save; no grant/quest/position mutation on reconnect')
        self.record('lyra_no_handler_errors', not any(self.error_codes().values()), errors=self.error_codes())


class KnightExchangeScenario(QuestScenario):
    """Synthetic starting materials; scoped socket development test, not formal PASS."""

    def __init__(self, args, directory):
        super().__init__(args, directory)
        self.name = 'knight_exchange'
        self.fixture_level = 15
        self.map_start = (4, 33126, 33365)

    async def open(self, *, seed, character=None, deliver=True):
        self.seed_fixture = seed
        self.name = 'dungeon_items' if seed else 'knight_exchange'
        try:
            await matrix.Matrix.open(self, seed=seed, character=character, deliver=deliver)
        finally:
            self.name = 'knight_exchange'

    def instrument(self):
        super().instrument()
        if not self.seed_fixture:
            return
        from tools.local_original_session import inventory
        frame = self.store.restore(1)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        for template in (639, 633, 650):
            # Materials use the same plain kit producer as startup policies.
            from tools.local_original_session.world_handlers import _starter_fields
            row = _starter_fields()
            row.update({1: max(r[1] for r in rows) + 1, 2: template, 4: 1,
                        7: {639: 927, 633: 919, 650: 920}[template]})
            rows.append(row)
        self.store.replace_kit(1, frame, inventory.build_kit_frame(rows), append=True)
        self.fixture_notes.append(dict(synthetic_materials={639: 1, 633: 1, 650: 1},
            scope='disposable pre-login development inventory; not normal acquisition or formal PASS; no quest state or reward651/652 injected',
            riky_actor='L1J2337 LOCAL appearance/placement; fixed NPC identity UNKNOWN'))

    async def exchange_menu(self, npc_id, action=None, expected=None):
        if action is None:
            npc = await self.approach(npc_id)
            batch = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
                check=lambda frames: hb.find(frames, 0x4e44), label='KNIGHT_QUEST_CLICK')
        else:
            payload = (hb.uint(1, hb.scalar(self.menu, 1))
                + hb.pb.encode_bytes(2, action.encode()) + hb.uint(4, 0) + hb.uint(5, 0))
            batch = await self.bot.peer.request(0x4ed4, payload,
                check=lambda frames: hb.find(frames, 0x4e44), label='KNIGHT_QUEST_' + action)
        self.menu = hb.find(batch, 0x4e44).values
        if expected:
            self.record('knight_quest_menu_' + expected, hb.scalar(self.menu, 2) == expected.encode(),
                        npc_id=npc_id, action=action, received=hb.scalar(self.menu, 2).decode())

    async def knight_exchange(self):
        store = self.broker._world_quest_store
        uid = self.bot.self_uid
        self.record('synthetic_start_without_rewards', self.saved_counts()[651] == self.saved_counts()[652] == 0,
                    scope='socket development test only; materials supplied to fresh pre-login save')
        for npc_id, qid, start, active, end in (
            (70798, 'knight_riky_pledge', 'riky1', 'riky3', 'riky5'),
            (70802, 'knight_aanon_red_hood', 'aanon4', 'aanon5', 'aanon6')):
            self.stage = qid
            before = self.saved_counts()
            await self.exchange_menu(npc_id, expected=start)
            await self.exchange_menu(npc_id, 'queststart', active)
            state = store.get(uid, qid)
            self.record(qid + '_accepted_and_progressed', state.accepted and not state.completed
                and all(n > 0 for n in state.counts), state=dataclasses.asdict(state))
            await self.exchange_menu(npc_id, 'questcomplete', end)
            definition = self.broker._world_quests[qid]
            expected = before.copy()
            for objective in definition.objectives:
                expected[objective.key] -= objective.count
            for reward in definition.rewards:
                expected[reward.item_id] += reward.count
            expected = +expected
            self.record(qid + '_consumed_and_rewarded', store.get(uid, qid).completed
                and self.saved_counts() == expected == self.wire_counts(),
                before=dict(before), after=dict(self.saved_counts()))
        self.record('riky_reward_actually_consumed_by_aanon', self.saved_counts()[651] == 0
                    and self.saved_counts()[652] == 1)
        states = {q: store.get(uid, q) for q in ('knight_riky_pledge', 'knight_aanon_red_hood')}
        after = self.saved_counts()
        character = self.bot.character
        self.record('knight_normal_quit', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('KNIGHT_QUEST_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=character)
        self.record('knight_quest_completion_and_reward_restored', self.saved_counts() == after == self.wire_counts()
            and all(self.broker._world_quest_store.get(uid, q) == state for q, state in states.items()))


def parser():
    result = matrix.parser()
    result.description = __doc__
    result.set_defaults(scenario='lyra', hunt_timeout=600, navigation_timeout=300)
    next(action for action in result._actions if action.dest == 'scenario').choices = ('lyra', 'knight_exchange')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='quest-bot-', dir=root))
    scene = (KnightExchangeScenario if args.scenario == 'knight_exchange' else QuestScenario)(args, directory)
    source_paths = ('hunt_bot_quest.py', 'hunt_bot_m5.py', 'hunt_bot_play_matrix.py',
        'world_quest.py', 'world_quest_store.py', 'world_feature_quest.py', 'data/m2/quests.json')
    selected_sources = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                        for name in source_paths}
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1, SL_EXPERIMENT_WAREHOUSE=1,
            SL_WORLD_TOWN_CANDIDATES='', SL_COMPANION=0, SL_SPELL_EXP=0,
            SL_COMPANION_PET_UI=0, SL_COMPANION_REVIVE_EXP=0):
        result = await scene.run_matrix()
    result.update(quest_id=QUEST_ID if args.scenario == 'lyra' else ['knight_riky_pledge', 'knight_aanon_red_hood'], selected_source_sha256=selected_sources,
                  test_port_base=os.environ.get('SL_TEST_PORT_BASE', '12000'),
                  material_acquisitions=scene.acquisitions,
                  starting_save=('fresh retained level12/test_knight saved-map fixture; initial leveling/world travel excluded; no quest material/state supplied'
                    if args.scenario == 'lyra' else 'fresh synthetic level15/test_knight save with639/633/650 one each; no651/652 or quest state supplied; socket development test, not formal PASS'))
    (directory / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(dict(status=result['status'], directory=result['directory'],
        failure=result['failure'], gaps=result['gaps'], checks=len(result['checks']),
        requests=result['requests'], cleanup_complete=result['cleanup_complete']), ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
