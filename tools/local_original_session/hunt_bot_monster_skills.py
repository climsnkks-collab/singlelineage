"""Natural monster skills on fresh saved-position fixtures and ordinary sockets.

Reuses Audit/Matrix FIRST, login, character selection, inventory delivery and
Quit/close. No original process, user save, forced AI state or direct attack
handler is used. Results are DEVELOPMENT fixture evidence, not native input,
animation, full official behavior or formal original-client PASS.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import time

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import hunt_bot_spawn_audit as audit


GROUPS = {7: 'm3_tic1_elder', 28: 'population_m4_orc_forest_28',
          31: 'population_m5_kent_31'}


class SkillBot(audit.AuditBot):
    def __init__(self, args):
        super().__init__(args)
        self.skill_wire = []

    def apply(self, frame):
        super().apply(frame)
        if frame.opcode in (0x4ed8, 0x4e38, 0x4e31, 0x4e96):
            values = hb.fields(frame.wire[4:-2])
            self.skill_wire.append(dict(ordinal=frame.ordinal, at=frame.at,
                opcode=f'0x{frame.opcode:04X}',
                fields={str(n): hb.scalar(values, n) for n in
                        ((1, 2) if frame.opcode == 0x4ed8 else
                         (1, 10, 11) if frame.opcode == 0x4e38 else
                         (1, 2, 3, 4) if frame.opcode == 0x4e31 else (2, 39))}))


class SkillScene(audit.Audit):
    def __init__(self, args, directory, group):
        super().__init__(args, directory, [group], {})
        self.spec = group
        self.samples = []
        self.received_wire = []
        self.effect_consumers = []

    async def beat(self):
        if self.bot.dead:
            raise hb.BotFailure('MONSTER_SKILL_OWNER_DIED')
        await self.owner_potion()
        await self.bot.alive()
        await asyncio.sleep(.05)

    def received_candidates(self):
        # The group lookup identifies the source of an already received actor;
        # pursuit coordinates always come from the socket consumer.
        return [(uid, row) for uid, row in self.bot.actors.items()
                if row['alive'] and row['template'] == self.spec.template_id
                and (found := self.broker._world.spawner.slot_for(uid)) is not None
                and found[0].spec.group_id == self.spec.group_id]

    async def approach(self):
        bot = self.bot
        until = time.monotonic() + self.args.approach_seconds
        rect = self.spec.rect
        goals = [(x, y) for x in (rect.x1, (rect.x1+rect.x2)//2, rect.x2)
                 for y in (rect.y1, (rect.y1+rect.y2)//2, rect.y2)
                 if self.broker._world.terrain.can_stand(self.spec.map_id, x, y) is True]
        search = 0
        target = None
        while time.monotonic() < until:
            candidates = self.received_candidates()
            if candidates:
                target, actor = min(candidates,
                    key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                if hb.distance(bot.position, actor['position']) <= 1:
                    break
                await bot.step(actor['position'], radius=1)
            elif goals:
                goal = goals[search % len(goals)]
                if hb.distance(bot.position, goal) <= 1:
                    search += 1
                    goal = goals[search % len(goals)]
                await bot.step(goal, radius=1)
            await self.beat()
        self.record('received_spawn_and_ordinary_approach', target is not None
            and target in bot.actors and hb.distance(bot.position, bot.actors[target]['position']) <= 1,
            group=self.spec.group_id, template_id=self.spec.template_id, target=target,
            position=bot.position, moves=bot.moves)
        marker = bot.peer.ordinal
        # Passive monsters acquire retaliation only through this real attack.
        attack_until = time.monotonic() + 20
        while time.monotonic() < attack_until:
            await bot.attack(target)
            own = [r for r in bot.skill_wire if r['ordinal'] > marker
                   and r['opcode'] == '0x4E31' and r['fields']['2'] == bot.self_uid
                   and r['fields']['3'] == target]
            if own:
                self.record('received_attack_before_retaliation_observation', True,
                    target=target, own_swing_ordinal=own[-1]['ordinal'])
                return target
            await self.beat()
        self.record('received_attack_before_retaliation_observation', False, target=target)

    def events(self, target):
        return [dict(event) for event in getattr(self.broker, '_world_monster_skills_events', ())
                if event.get('npc_uid') == target and event.get('target') == self.bot.self_uid]

    async def sample_delayed_consumer(self, target):
        """Read existing effect state; exercise its ordinary packet consumer."""
        bot, view = self.bot, self.broker._world
        state = self.broker._world_magic.states.get(bot.self_uid)
        if state is None:
            return
        if self.spec.template_id == 31 and state.poison is not None:
            current = dict(state.poison)
            old = getattr(self, '_last_poison', None)
            if (old is not None and old['source_uid'] == target == current['source_uid']
                    and current['until'] == old['until']
                    and current['next_tick'] > old['next_tick']):
                self.effect_consumers.append(dict(kind='poison_tick_advanced',
                    at=view.runtime.clock(), next_tick_before=old['next_tick'],
                    next_tick_after=current['next_tick'], damage=current['damage'],
                    hp_after=view.combat.pcs[bot.self_uid].hp,
                    scope='existing poison timer advanced and resulting HP status received; overlapping natural physical attacks remain possible'))
            self._last_poison = current
        if self.spec.template_id != 28 or self.effect_consumers:
            return
        effect = state.effects.get('paralyze')
        now = view.runtime.clock()
        if (effect is None or effect['source_uid'] != target
                or not effect['starts_at'] <= now < effect['until']
                or target not in bot.actors or not bot.actors[target]['alive']
                or hb.distance(bot.position, bot.actors[target]['position']) > 1):
            return
        marker = bot.peer.ordinal
        target_hp = view.spawner.slot_for(target)[1].hp
        batch = await bot.peer.request(0x4e30, hb.uint(1, target), alive=True,
            check=lambda frames: hb.find(frames, 0x4f57), label='PARALYZED_REAL_ATTACK')
        self.effect_consumers.append(dict(kind='paralyze_attack_blocked', at=now,
            starts_at=effect['starts_at'], until=effect['until'], marker=marker,
            barrier_ordinal=next(f.ordinal for f in batch if f.opcode == 0x4f57),
            own_swing_received=hb.find(batch, 0x4e31,
                **{'2': bot.self_uid, '3': target}) is not None,
            target_hp_before=target_hp, target_hp_after=view.spawner.slot_for(target)[1].hp))

    async def close(self):
        if self.bot is not None:
            self.received_wire = self.bot.skill_wire
        return await super().close()

    async def dungeon_items(self):
        bot = self.bot
        bot.safe_hunt_cell = lambda point: True
        self.stage = 'natural_skill_approach'
        target = await self.approach()
        self.stage = 'natural_ai_special_attack_observation'
        until = time.monotonic() + self.args.observe_seconds
        while time.monotonic() < until:
            self.samples = self.events(target)
            await self.sample_delayed_consumer(target)
            if self.skill_received():
                break
            await self.beat()
        self.received_wire = bot.skill_wire
        self.record('natural_special_skill_received', self.skill_received(),
            group=self.spec.group_id, template_id=self.spec.template_id, target=target,
            events=self.samples, wire=self.received_wire,
            effect_consumers=self.effect_consumers,
            scope='DEVELOPMENT saved fixture; natural AI plus actual socket consumers')

    def skill_received(self):
        # Poison color is not a 4ED8 gfx. Those effects require their existing
        # timer/blocked consumer and a real received HP/ordered attack barrier.
        for event in self.samples:
            if self.spec.template_id == 28 and event.get('outcome') == 'poison_applied':
                if any(row['kind'] == 'paralyze_attack_blocked' and not row['own_swing_received']
                       and row['target_hp_before'] == row['target_hp_after'] for row in self.effect_consumers):
                    return True
            if self.spec.template_id == 31 and event.get('outcome') == 'poison_applied':
                if any(row['kind'] == 'poison_tick_advanced' and any(
                        r['opcode'] == '0x4E38' and r['fields']['1'] == self.bot.self_uid
                        and r['fields']['10'] == row['hp_after'] and r['at'] >= event['at']
                        for r in self.bot.skill_wire) for row in self.effect_consumers):
                    return True
            gfx = event.get('effect_id')
            if not gfx:
                continue
            effects = [r for r in self.bot.skill_wire if r['opcode'] == '0x4ED8'
                       and r['fields']['1'] == self.bot.self_uid and r['fields']['2'] == gfx
                       and r['at'] >= event['at']]
            if not effects:
                continue
            hp_after = event.get('hp_after')
            if hp_after is not None and event.get('amount', 0) > 0 and any(
                    r['opcode'] == '0x4E38' and r['fields']['1'] == self.bot.self_uid
                    and r['fields']['10'] == hp_after and r['at'] >= event['at']
                    for r in self.bot.skill_wire):
                return True
        return False


async def run(args):
    from tools.local_original_session.world_terrain import WorldTerrain
    root = (Path(args.output_root) if args.output_root is not None else
            Path(__file__).resolve().parents[2] / 'work/local_original_session/runs')
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='monster-skills-natural-', dir=root))
    data = audit.all_data()
    groups = [next(g for g in data.spawns if g.group_id == GROUPS[t]) for t in args.templates]
    print(json.dumps(dict(directory=str(directory), scope='DEVELOPMENT saved-fixture socket test',
                         templates=args.templates)), flush=True)
    results = []
    original_bot = hs.ScenarioBot
    hs.ScenarioBot = SkillBot
    try:
        terrain = WorldTerrain.load(map_ids=tuple({g.map_id for g in groups}))
        for index, group in enumerate(groups, 1):
            output = directory / f'epoch-{index:03}'
            output.mkdir()
            scene = SkillScene(args, output, group)
            scene.map_start = audit.start_cell(terrain, group.map_id, group.rect)
            result = await scene.run_matrix()
            result.update(template_id=group.template_id, group=group.group_id,
                          samples=scene.samples, received_wire=scene.received_wire,
                          effect_consumers=scene.effect_consumers)
            (output / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2), encoding='utf-8')
            results.append(result)
            print(json.dumps(dict(template_id=group.template_id, status=result['status'],
                failure=result['failure'], cleanup_complete=result['cleanup_complete'])), flush=True)
            if not result['cleanup_complete']:
                break
    finally:
        hs.ScenarioBot = original_bot
    sources = (Path(__file__), Path(__file__).with_name('world_feature_monster_skills.py'),
               Path(__file__).with_name('world_monster_skills.py'),
               Path(__file__).with_name('world_handlers.py'),
               Path(__file__).parent / 'data/monster_skills.json')
    summary = dict(status='PASS' if len(results) == len(groups) and all(r['status'] == 'PASS' for r in results) else 'FAIL',
        directory=str(directory), scope='DEVELOPMENT saved-position/level fixture; ordinary loopback socket AI skills; native render/input UNKNOWN',
        templates=args.templates, results=[dict(template_id=r['template_id'], group=r['group'],
            status=r['status'], failure=r['failure'], directory=r['directory']) for r in results],
        cleanup_complete=all(r['cleanup_complete'] for r in results),
        source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.exists()})
    (directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--templates', type=int, choices=tuple(GROUPS), nargs='+', default=[7, 28, 31])
    cli.add_argument('--timeout', type=hb.positive, default=8)
    cli.add_argument('--approach-seconds', type=hb.positive, default=120)
    cli.add_argument('--observe-seconds', type=hb.positive, default=180)
    cli.add_argument('--fixture-level', type=int, default=30)
    cli.add_argument('--output-root', help='Directory for isolated test saves and results')
    cli.set_defaults(scenario='dungeon_items', minutes=1, potion_threshold=.7,
        companion_revive_exp=False, navigation_timeout=60, strong_fixture=False,
        boss_fixture=False, fixture_heal_template=130, fixture_heal_count=150)
    with matrix.environment(SL_EXPERIMENT_MAP=2, SL_EXPERIMENT_M5=1, SL_EXPERIMENT_SHOP=1,
            SL_COMPANION=0, SL_COMPANION_PET_UI=0, SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0):
        result = asyncio.run(run(cli.parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' and result['cleanup_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
