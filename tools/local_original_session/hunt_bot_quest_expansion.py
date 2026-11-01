"""Fixed Zero/Gereng exchanges through retained FIRST/login/socket requests.

Fresh pre-login test characters receive only explicitly synthetic materials.
Jem645 and Gereng710 are earned through actual preceding menu requests. No
quest state or intermediate/final reward is supplied. This verifies scoped
exchange/persistence behavior, not normal acquisition or native client input.
Import/help never starts a socket or an original game client.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
from pathlib import Path
import random
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.local_original_session import hunt_bot as hb, inventory
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session.hunt_bot_quest import QuestScenario


ZERO = 'royal_zero_search_document'
BONE = 'wizard_gereng_undead_bone'
STAFF = 'wizard_gereng_crystal_staff'


class ExpansionScenario(QuestScenario):
    def __init__(self, args, directory):
        super().__init__(args, directory)
        self.name = args.scenario
        self.scenario_name = args.scenario
        self.class_id = 0 if args.scenario == 'royal_zero' else 3
        self.selected_name = 'QuestRoyal' if self.class_id == 0 else 'QuestMage'
        self.fixture_level = 15 if self.class_id == 0 else 30
        self.materials = (636,) if self.class_id == 0 else (648, 649, 647, 690, 709)
        self.map_start = None  # Selected UID2 position is prepared below.

    async def open(self, *, seed, character=None, deliver=True):
        self.seed_fixture = seed
        # Existing Matrix saved-map fixture/native adapter and growth seam.
        self.name = 'dungeon_items' if seed else self.scenario_name
        try:
            await matrix.Matrix.open(self, seed=seed,
                character=character or self.selected_name, deliver=deliver)
        finally:
            self.name = self.scenario_name

    def instrument(self):
        matrix.Matrix.instrument(self)
        if not self.seed_fixture:
            return
        from tools.local_original_session import equipment_store
        from tools.local_native_login_local_ack_hook import ack_enter_world as ack
        stats = ((13, 10, 10, 11, 13, 18) if self.class_id == 3
                 else (13, 10, 13, 11, 13, 10))
        self.fixture_uid, _, _ = self.broker.realm.store.create(
            ack.realm.Creation(self.selected_name, self.class_id, 0, stats))
        frame = self.broker._inventory_kit_frame(self.class_id)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
        identifier = max(row[1] for row in rows)
        for template in self.materials:
            identifier += 1
            policy = self.broker._world_quest_item_policies
            prototype = next(p.grant_fields for p in policy if p.template_id == template)
            rows.append({**dict(prototype), 1: identifier, 2: template, 4: 1})
        frame = inventory.build_kit_frame(rows)
        self.store.grant(self.fixture_uid, frame)
        by_template = {row[2]: row for row in rows}
        data = self.broker._world.data
        equipped = [entry.template_id for entry in data.starter.entries(self.class_id, 'test_knight')
                    if entry.equipped]
        self.equipment.initialize_kit(self.fixture_uid, frame,
            initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=next((by_template[t][1] for t in equipped if data.items[t].kind == 'weapon'), 0),
            slots=tuple((data.items[t].slot_key, by_template[t][1])
                        for t in equipped if data.items[t].kind == 'armor'))
        self.fixture_notes.append(dict(selected_uid=self.fixture_uid, selected_class=self.class_id,
            synthetic_materials={t: 1 for t in self.materials},
            quest_state='fresh; no QuestStore state, reference step or intermediate/final reward supplied',
            scope='disposable pre-login development save; normal acquisition and formal PASS excluded'))

    def initialize_hunt_fixture(self):
        from tools.local_original_session import movement
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        data = load_m1()
        owner = next(r for r in self.broker.realm.store._read()['characters']
                     if r['uid'] == self.fixture_uid)
        stats = owner['attributes']
        exp = data.pc_exp[self.fixture_level - 1]
        profile = PcProfile(1, self.class_id, 0, stats[0], stats[1], con=stats[2], wis=stats[3])
        initial_hp, initial_mp = (12, 8) if self.class_id == 3 else (14, 2)
        growth = on_kill(RewardPcState(0, profile, initial_hp, initial_mp),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x51554553), data=data)
        self.broker._world_progress.commit(self.fixture_uid,
            Progress(exp, self.fixture_level, growth.max_hp, growth.max_mp))
        map_id, x, y = (4, 33047, 32756) if self.class_id == 0 else (0, 32595, 32906)
        before = self.broker.realm.positions.restore(
            movement.Position(self.fixture_uid, self.selected_name, 0, 0, 0))
        self.broker.realm.positions.commit(before,
            movement.Position(self.fixture_uid, self.selected_name, map_id, x, y),
            transition=before.map_id != map_id)
        self.fixture_notes.append(dict(pre_login_level=self.fixture_level,
            pre_login_exp=exp, pre_login_position=(map_id, x, y),
            growth='existing pure world_reward.on_kill -> ProgressStore; initial leveling/travel excluded'))

    async def exchange_menu(self, npc_id, action=None, expected=None):
        if action is None:
            npc = await self.approach(npc_id)
            batch = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
                check=lambda frames: hb.find(frames, 0x4e44), label='QUEST_EXPANSION_CLICK')
        else:
            stem = hb.scalar(self.menu, 2).decode()
            dialogue = self.broker._world_quest_dialogues[npc_id]
            if action not in dialogue.pages.get(stem, ()):
                raise matrix.MissingFeature(f'UNAVAILABLE_ISSUED_QUEST_ACTION:{stem}:{action}')
            payload = (hb.uint(1, hb.scalar(self.menu, 1))
                + hb.pb.encode_bytes(2, action.encode()) + hb.uint(4, 0) + hb.uint(5, 0))
            batch = await self.bot.peer.request(0x4ed4, payload,
                check=lambda frames: hb.find(frames, 0x4e44), label='QUEST_EXPANSION_' + action)
        self.menu = hb.find(batch, 0x4e44).values
        if expected is not None:
            self.record('received_' + expected, hb.scalar(self.menu, 2) == expected.encode(),
                npc_id=npc_id, action=action, actual=hb.scalar(self.menu, 2).decode())

    async def turn_in(self, npc_id, quest_id, start, active, result, *, click=True):
        self.stage = quest_id
        if click:
            await self.exchange_menu(npc_id, expected=start)
        before = self.saved_counts()
        await self.exchange_menu(npc_id, 'queststart', active)
        state = self.broker._world_quest_store.get(self.bot.self_uid, quest_id)
        self.record(quest_id + '_accepted', state.accepted and not state.completed,
                    state=dataclasses.asdict(state))
        await self.exchange_menu(npc_id, 'questcomplete', result)
        definition = self.broker._world_quests[quest_id]
        expected = before.copy()
        for objective in definition.objectives:
            expected[objective.key] -= objective.count
        for reward in definition.rewards:
            expected[reward.item_id] += reward.count
        self.record(quest_id + '_consumed_rewarded_saved',
            self.broker._world_quest_store.get(self.bot.self_uid, quest_id).completed
            and self.saved_counts() == +expected == self.wire_counts(),
            before=dict(before), after=dict(self.saved_counts()))

    async def restore(self, quest_ids):
        uid = self.bot.self_uid
        states = {q: self.broker._world_quest_store.get(uid, q) for q in quest_ids}
        counts = self.saved_counts()
        self.record('normal_quit_before_restore', await self.bot.quit_selected())
        if not await self.close():
            raise hb.BotFailure('QUEST_EXPANSION_FIRST_EPOCH_CLEANUP_INCOMPLETE')
        await self.open(seed=False, character=self.selected_name)
        self.record('completion_and_inventory_restored', self.saved_counts() == counts == self.wire_counts()
            and all(self.broker._world_quest_store.get(uid, q) == s for q, s in states.items()))

    async def royal_zero(self):
        self.record('no_zero_reward_or_state_injected', self.saved_counts()[646] == 0
            and not self.broker._world_quest_store.get(self.bot.self_uid, ZERO).accepted)
        await self.turn_in(70554, ZERO, 'zero1', 'zero3', 'zero7')
        await self.restore((ZERO,))

    async def wizard_gereng(self):
        self.record('no_jem_or_gereng_rewards_or_state_injected',
            not any(self.saved_counts()[t] for t in (644, 645, 710, 711))
            and not any(self.broker._world_quest_store.get(self.bot.self_uid, q).accepted
                        for q in ('ti_jem_cursed_spellbook', 'ti_jem_book_of_magic', BONE, STAFF)))
        await self.turn_in(70531, 'ti_jem_cursed_spellbook', 'jem1', 'jem3', 'jem8')
        await self.exchange_menu(70531, expected='jem1')
        await self.exchange_menu(70531, 'queststart', 'jem9')
        await self.turn_in(70531, 'ti_jem_book_of_magic', 'jem9', 'jem4', 'jem10', click=False)
        await self.turn_in(70009, BONE, 'gerengt1', 'gerengt2', 'gerengt3')
        await self.turn_in(70009, STAFF, 'gerengt3', 'gerengt4', 'gerengt5', click=False)
        self.record('actual_intermediate_consumed_and_final_retained',
            self.saved_counts()[710] == 0 and self.saved_counts()[711] == 1
            and self.saved_counts()[645] == 1)
        await self.restore(('ti_jem_cursed_spellbook', 'ti_jem_book_of_magic', BONE, STAFF))


def parser():
    result = matrix.parser()
    result.description = __doc__
    result.set_defaults(scenario='royal_zero', navigation_timeout=300)
    next(a for a in result._actions if a.dest == 'scenario').choices = ('royal_zero', 'wizard_gereng')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='quest-expansion-bot-', dir=root))
    scene = ExpansionScenario(args, directory)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1, SL_EXPERIMENT_WAREHOUSE=1,
            SL_WORLD_TOWN_CANDIDATES='', SL_COMPANION=0, SL_SPELL_EXP=0,
            SL_COMPANION_PET_UI=0, SL_COMPANION_REVIVE_EXP=0):
        result = await scene.run_matrix()
    result.update(test_port_base=os.environ.get('SL_TEST_PORT_BASE', '12000'),
        starting_save='fresh pre-login class/level/position plus explicitly synthetic materials; no quest state or intermediate/final rewards supplied',
        scope='socket development verification of exchange and restore; normal producers and native UI unverified')
    (directory / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps({key: result[key] for key in
        ('status', 'directory', 'failure', 'gaps', 'requests', 'cleanup_complete')}, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
