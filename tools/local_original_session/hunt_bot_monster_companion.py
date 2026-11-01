"""Natural companion poison and owned antidote consumption over real sockets.

Fresh declared saved-position/level/supply fixture; FIRST/login/select/world,
pet commands, ATS save, GIVE and Quit reuse existing bot paths. No original
client, live state mutation, handler call or RNG/clock forcing is performed.
SUCCESS is DEVELOPMENT socket evidence, never native input/rendering parity.
"""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from pathlib import Path
import random
import tempfile
import time

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_companion as companion
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import hunt_bot_spawn_audit as audit


GROUP = 'population_m5_kent_31'
ANTIDOTE = 126


class CompanionBot(audit.AuditBot):
    async def login(self):
        # CompanionScenario's historical load_m1 assignment omits expansion
        # monsters. Decode initial appearances against the same enabled data.
        self.data = audit.all_data()
        return await super().login()


class MonsterCompanion(companion.CompanionScenario):
    def __init__(self, args, directory):
        super().__init__(args, directory)
        self.enable_settings = True
        self.samples = []
        self.observations = {}
        self.ailment_events = []
        self.group = next(g for g in audit.all_data().spawns if g.group_id == GROUP)

    def initialize_mage_fixture(self):
        super().initialize_mage_fixture()
        from tools.local_original_session import inventory, movement
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        from tools.local_native_login_self_actor_hook import hook
        data = self.world.data
        owner = next(r for r in self.broker.realm.store._read()['characters'] if r['class'] == 1)
        stats, level = owner['attributes'], self.args.fixture_level
        exp = data.pc_exp[level - 1]
        baseline = hook.profiles()[0].fields
        profile = PcProfile(1, owner['class'], owner['gender'], stats[0], stats[1],
                            con=stats[2], wis=stats[3])
        growth = on_kill(RewardPcState(0, profile, baseline[11], baseline[13]),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x4f574e52), data=data)
        self.broker._world_progress.commit(owner['uid'], Progress(exp, level, growth.max_hp, growth.max_mp))
        start = audit.start_cell(self.world.terrain, self.group.map_id, self.group.rect)
        old = self.broker.realm.positions.restore(movement.Position(owner['uid'], owner['name'], *start))
        self.broker.realm.positions.commit(old, movement.Position(old.uid, old.name, *start),
                                           transition=old.map_id != start[0])
        before = self.store.restore(owner['uid'])
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(before)]
        for template, quantity in ((14, 200), (ANTIDOTE, 1)):
            row = next((r for r in rows if r[2] == template), None)
            if row is None:
                row = dict(rows[0])
                row.update({1: max(r[1] for r in rows) + 1, 2: template,
                            7: data.items[template].icon, 18: b''})
                rows.append(row)
            row[4] = quantity
        after = inventory.build_kit_frame(rows)
        self.store.replace_kit(owner['uid'], before, after, append=True)
        self.broker._inventory_current_frame = after
        # The member receives an ordinary fresh mage bag. Antidote is withheld
        # until actual poison damage is observed, then delivered by GIVE.
        member_uid = self.fixture_growth['character_id']
        member_rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.broker._inventory_kit_frame(3))]
        for index, row in enumerate(member_rows):
            row[1] = 0x20000000 + member_uid * inventory.KIT_MAX_ITEMS + index
            if row[2] == ANTIDOTE:
                row[4] = 0
            elif row[2] == 14:
                row[4] = 100
        self.store.grant(member_uid, inventory.build_kit_frame(member_rows))
        self.owner_fixture.update(initial_level=level, initial_exp=exp,
            initial_max_hp=growth.max_hp, initial_max_mp=growth.max_mp,
            initial_position=list(start), supplies={14: 200, ANTIDOTE: 1})
        self.fixture_growth.update(initial_antidote_count=0, initial_hp_potions=100,
            supplies_scope='fresh pre-login saved mage bag; antidote acquired only through actual owner GIVE')

    def ailments(self):
        if self.actor is None:
            return {'effects': {}, 'poison': None}
        adapter = next((value for value in self.broker.realm._world_context.collect_sync_hooks(
            'npc_magic_target', self.actor.ref.uid) if value is not None), None)
        if adapter is None or not hasattr(adapter, 'ailments'):
            raise hs.Unconfirmed('REGISTERED_COMPANION_AILMENTS_READER_REQUIRED')
        return adapter.ailments(self.world.runtime.clock())

    def events(self):
        return [dict(e) for e in self.broker._world_monster_skills_events
                if self.actor is not None and e.get('target') == self.actor.ref.uid]

    def bag_count(self, template):
        from tools.local_original_session import inventory
        return sum(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(
            self.broker._companion_inventory.frames[self.member_id]) if r.template_bits == template)

    async def close(self):
        if self.broker is not None:
            owner = getattr(self.broker, '_companion_ailments', None)
            self.ailment_events = list(getattr(owner, 'events', ()))
        return await super().close()

    async def configure_antidote(self):
        from tools.local_original_session import ats_config_codec as codec
        config = codec.wrap_blob(b'\x08\x01')
        owner_ats = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=70.0))
        await self.bot.peer.request(0x4ed6, hb.pb.encode_bytes(1, config) + hb.pb.encode_bytes(2, owner_ats),
            alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='OWNER_INITIAL_ATS_SAVE')
        marker, result = await self.signal('settings-load')
        self.record('member_ATS_edit_opened_over_socket', result.get('status') == 'EDIT_STARTED'
            and bool(self.frames(marker, 0x4ed7)), result=result)
        ats = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=70.0,
                                             function_templates=(ANTIDOTE,)))
        await self.bot.peer.request(0x4ed6, hb.pb.encode_bytes(1, config) + hb.pb.encode_bytes(2, ats),
            alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='ANTIDOTE_ATS_SAVE')
        policy = self.broker._companion_ats_policy(self.member)
        self.record('member_ATS_antidote_policy_saved', ANTIDOTE in policy['function_items'], policy=policy)
        await self.signal('ats-edit-close', actor=False)
        await self.signal('ats-edit-restored', actor=False)

    async def approach(self):
        bot, target = self.bot, None
        bot.safe_hunt_cell = lambda point: True
        until = time.monotonic() + self.args.navigation_timeout
        rect, search = self.group.rect, 0
        goals = [(x, y) for x in (rect.x1, (rect.x1 + rect.x2) // 2, rect.x2)
                 for y in (rect.y1, (rect.y1 + rect.y2) // 2, rect.y2)
                 if self.world.terrain.can_stand(self.group.map_id, x, y) is True]
        while time.monotonic() < until:
            if bot.dead:
                raise hs.Unconfirmed('OWNER_DIED_DURING_NATURAL_APPROACH')
            candidates = [(uid, row) for uid, row in bot.actors.items() if row['alive']
                and (slot := self.world.spawner.slot_for(uid)) is not None
                and slot[0].spec.group_id == GROUP]
            if candidates:
                target, row = min(candidates, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, row['position']) <= 1:
                    break
                await bot.step(row['position'], radius=1)
            elif goals:
                goal = goals[search % len(goals)]
                if hb.distance(bot.position, goal) <= 1:
                    search += 1
                    goal = goals[search % len(goals)]
                await bot.step(goal, radius=1)
            await self.tick_wait(.05)
        self.record('received_natural_ungoliant_approached', target is not None
            and hb.distance(bot.position, bot.actors[target]['position']) <= 1,
            target=target, group=GROUP, owner_position=bot.position,
            received_templates=sorted({r['template'] for r in bot.actors.values()}))
        return target

    async def monster_companion(self):
        await self.summon()
        await self.command(2)
        await self.configure_antidote()
        target = await self.approach()
        member_uid, marker = self.actor.ref.uid, self.bot.peer.ordinal
        self.stage = 'natural_companion_retaliation'
        await self.command(1, target)
        await self.wait_current('companion_actual_attack', lambda: bool(self.frames(marker,
            0x4e31, **{'2': member_uid, '3': target})), timeout=30, member_required=True)
        await self.command(4)
        self.record('pet_command_attack_then_passive_received', True, target=target, member_uid=member_uid)
        self.stage = 'natural_poison'
        await self.wait_current('natural_companion_poison', lambda: self.ailments().get('poison') is not None,
            timeout=self.args.death_timeout, member_required=True, marker=marker, target_uid=target)
        poison = dict(self.ailments()['poison'])
        hp_before = self.member.hp
        self.samples = self.events()
        self.record('actual_monster_hit_applied_companion_poison',
            poison.get('source_uid') == target and any(e.get('outcome') == 'poison_applied'
                and e.get('npc_uid') == target for e in self.samples)
            and bool(self.frames(marker, 0x4e31, **{'2': target, '3': member_uid})),
            poison=poison, hp=hp_before, events=self.samples)
        await self.wait_current('companion_poison_tick_consumed', lambda:
            any(e.get('kind') == 'poison_tick' and e.get('target') == member_uid
                and e.get('at', 0) >= poison['next_tick']
                for e in self.broker._companion_ailments.events), timeout=15, member_required=True)
        after_tick = dict(self.ailments()['poison'])
        tick = next(dict(e) for e in reversed(self.broker._companion_ailments.events)
                    if e.get('kind') == 'poison_tick' and e.get('target') == member_uid)
        _, children = await self.pet_status()
        hp_after = self.member.hp
        self.record('companion_poison_tick_and_real_pet_HP',
            after_tick['next_tick'] > poison['next_tick']
            and tick['hp_before'] - tick['hp_after'] == min(tick['hp_before'], poison['damage'])
            and any(hb.scalar(c, 3) == hp_after for c in children),
            poison_before=poison, poison_after=after_tick, hp_before=hp_before, hp_after=hp_after,
            actual_poison_tick=tick,
            note='tick event isolates actual poison HP debit; later pet HP may include physical damage or healing')
        self.stage = 'owned_antidote_GIVE'
        bags = self.broker._companion_inventory
        before = self.bag_count(ANTIDOTE)
        item_uid, item = next((uid, row) for uid, row in self.bot.inventory.items()
                              if row.get(2) == ANTIDOTE and row.get(4, 0) > 0)
        owner_quantity = item[4]
        sent_at = self.world.runtime.clock()
        def cure_events():
            return [dict(e) for e in bags.events if e.get('template') == ANTIDOTE
                and e.get('character_id') == self.member_id and e.get('consumed') == 1
                and e.get('poison_cured') is True and e.get('at', -1) >= sent_at]
        await self.bot.peer.request(0x4ef5, hb.uint(1, member_uid) + hb.uint(2, item_uid) + hb.uint(3, 1),
            check=lambda batch: next((f for f in batch if f.opcode in (0x0965, 0x0978)), None),
            label='GIVE_ACTUAL_ANTIDOTE')
        await self.wait_current('owned_member_antidote_consumed', lambda: bool(cure_events()),
                                timeout=10, member_required=True)
        cure_state = self.ailments()
        from tools.local_original_session import inventory
        saved_count = sum(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(
            self.store.restore(self.member_id)) if r.template_bits == ANTIDOTE)
        self.record('GIVE_debit_saved_member_antidote_spent_and_poison_cured',
            self.bot.inventory.get(item_uid, {}).get(4, 0) == owner_quantity - 1
            and self.bag_count(ANTIDOTE) == saved_count == before
            and cure_state.get('poison') is None
            and cure_events()[-1]['at'] < poison['until'],
            owner_uid=item_uid, owner_quantity_before=owner_quantity,
            owner_quantity_after=self.bot.inventory.get(item_uid, {}).get(4, 0),
            member_quantity_before=before, member_quantity_after=self.bag_count(ANTIDOTE),
            saved_member_quantity_after=saved_count,
            consumption_events=cure_events(), cure_state=cure_state,
            sent_at=sent_at, cured_at=self.world.runtime.clock())
        _, children = await self.pet_status()
        self.record('post_cure_real_pet_HP_received', any(hb.scalar(c, 3) == self.member.hp for c in children),
            hp=self.member.hp, alive=self.member.alive)
        self.observations = dict(member_uid=member_uid, target=target, poison=poison,
            after_tick=after_tick, cure_state=cure_state, consumption_events=cure_events())


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='monster-companion-natural-', dir=root))
    print(json.dumps({'directory': str(directory), 'scope': 'DEVELOPMENT fixture/socket'}), flush=True)
    original = hs.ScenarioBot
    hs.ScenarioBot = CompanionBot
    try:
        scenario = MonsterCompanion(args, directory)
        result = await scenario.run()
    finally:
        hs.ScenarioBot = original
    sources = [Path(__file__), *[Path(__file__).with_name(name) for name in (
        'world_monster_skills.py', 'world_feature_monster_skills.py', 'world_feature_companion.py',
        'companion_ai.py', 'world_companion_inventory.py', 'world_item_effects.py')],
        Path(__file__).parent / 'data/monster_skills.json']
    result.update(directory=str(directory), fixture={'owner': scenario.owner_fixture,
        'member': scenario.fixture_growth}, observations=scenario.observations, samples=scenario.samples,
        ailment_events=scenario.ailment_events,
        scope='DEVELOPMENT fresh saved fixture; real FIRST/login/select/world/ATS/pet/GIVE/close; native render/input UNKNOWN',
        source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = hs.parser()
    parser.description = __doc__
    next(a for a in parser._actions if a.dest == 'scenario').choices = ('monster_companion',)
    parser.set_defaults(scenario='monster_companion', minutes=1, fixture_level=30,
                        companion_revive_exp=False, potion_threshold=.7)
    parser.add_argument('--fixture-level', type=int, choices=(30,), default=30)
    args = parser.parse_args(argv)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1, SL_EXPERIMENT_SHOP=1,
            SL_COMPANION=1, SL_COMPANION_PET_UI=1, SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
        result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result['status'] == 'SUCCESS' and result['cleanup_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
