"""Monster population audit using retained Matrix socket/fixture lifecycle.

Every rect gets a fresh pre-login saved-position fixture. All game actions
after FIRST/login/select use ordinary wire requests. This is development
fixture evidence, never native sprite/input or original-client parity.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import dataclasses
import hashlib
import json
from pathlib import Path
import random
import tempfile
import time

from tools.local_original_session import game_data as gd, hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import hunt_bot_dungeons as dungeon


class AuditBot(hs.ScenarioBot):
    def __init__(self, args):
        super().__init__(args)
        self.last_seen_actors = {}

    def apply(self, frame):
        super().apply(frame)
        if frame.opcode in (0x4e96, 0x4e2c, 0x4e39):
            uid = hb.scalar(frame.values, 2 if frame.opcode == 0x4e96 else 1)
            if uid in self.actors:
                self.last_seen_actors[uid] = dict(self.actors[uid], map_id=self.map_id)

    async def login(self):
        try:
            await super().login()
        except hb.BotFailure as error:
            # The shared bot's historical client-side allowlist predates M6.
            # FIRST, roster reference, ACK/map/status/self must already exist.
            if (str(error) != 'MAP0_SELF_POSITION_AND_HP_REQUIRED' or not self.selected
                    or self.map_id not in (4, *range(7, 14), 19, 20, 21, *range(43, 52))
                    or self.position is None or self.hp is None or not self.max_hp):
                raise
            await self.alive()


def all_data():
    from tools.local_original_session.world_interest_spawn import with_dungeon_data
    from tools.local_original_session.world_feature_dungeons import load_dungeon_data
    from tools.local_original_session.world_feature_m5 import load_m5_data
    return load_m5_data(load_dungeon_data(with_dungeon_data(gd.load_m1())))


def start_cell(terrain, map_id, rect):
    center = ((rect.x1 + rect.x2)//2, (rect.y1 + rect.y2)//2)
    cells = [(x, y) for x in range(rect.x1, rect.x2+1) for y in range(rect.y1, rect.y2+1)]
    cells.sort(key=lambda p: hb.distance(p, center))
    for x, y in cells:
        if terrain.can_stand(map_id, x, y) is True and any(
                terrain.can_step(map_id, x, y, h) is True for h in range(8)):
            return map_id, x, y
    raise ValueError(f'NO_PASSABLE_START:{map_id}:{rect}')


class Audit(matrix.Matrix):
    def __init__(self, args, directory, groups, done):
        super().__init__(args, 'dungeon_items', directory)
        self.groups, self.done = groups, done
        catalog = all_data()
        self.expected_population = dict(monsters=len(catalog.monsters), groups=len(catalog.spawns))
        self.audit_rows = {g.group_id: dict(group=g.group_id, map_id=g.map_id,
            template=g.template_id, rect=dataclasses.asdict(g.rect), expected_slots=g.target_count,
            issued_uids=[], received_uids=[], wander_uids=[], moved_uids=[], states={},
            approached_uids=[], combat='NOT_ATTEMPTED', killed_uids=[], swings=0,
            hp_decreased=None, drops=[], picked=[], errors=[]) for g in groups}
        self.transitions = dungeon.world_maps.load_dungeon_policy().transitions | dungeon.world_maps.TRANSITIONS
        self.seen = {}

    def sync_native_position(self):
        super().sync_native_position()
        memory = getattr(self, 'fixture_memory', None)
        if memory is not None and self.bot is not None and self.bot.position is not None:
            # Shared Matrix wrote x+1 here but used x for the segment. At
            # x%64==63 that fabricated an inconsistent RAM coordinate pair.
            # Mirror the received grid exactly; retain every native validator.
            memory.put(0x470000 + memory.proof.position_source['coordinates']['transform_grid_offset'],
                       '<ii', *self.bot.position)

    def initialize_hunt_fixture(self):
        # Existing pure-growth pre-login initializer, using the selected table level.
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        from tools.local_native_login_self_actor_hook import hook
        data = gd.load_m1()
        owner = next(r for r in self.broker.realm.store._read()['characters'] if r['class'] == 1)
        stats = owner['attributes']
        profile = PcProfile(1, owner['class'], owner['gender'], stats[0], stats[1], con=stats[2], wis=stats[3])
        exp = data.pc_exp[self.args.fixture_level-1]
        baseline = hook.profiles()[0].fields
        growth = on_kill(RewardPcState(0, profile, baseline[11], baseline[13]),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x4f574e52), data=data)
        self.broker._world_progress.commit(owner['uid'], Progress(exp, self.args.fixture_level, growth.max_hp, growth.max_mp))
        self.fixture_notes.append(dict(pre_login_level=self.args.fixture_level,
            pre_login_exp=exp, max_hp=growth.max_hp, gear='unchanged test_knight starter',
            scope='development saved fixture, no natural growth/equipment acquisition claim'))
        if self.args.strong_fixture or self.args.boss_fixture:
            from tools.local_original_session import inventory, equipment_store
            from tools.local_original_session import world_enchant_inventory as enchant
            frame = self.broker._inventory_kit_frame(1)
            supplied = [dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)]
            wanted = {3, 117, 89, 98, 104, 109, 128, 129, 14, 17, 296, 7}
            rows = [row for row in supplied if row[2] in wanted]
            if self.args.boss_fixture:
                # Catalog-backed replacements in the fresh pre-login grant only.
                # Ancient equipment has no supported enchant contract: keep +0.
                replacements = {3: (672, 1), 98: (667, 1),
                    14: (self.args.fixture_heal_template, self.args.fixture_heal_count)}
                for row in rows:
                    if row[2] in replacements:
                        template, count = replacements[row[2]]
                        row.update({2: template, 4: count, 7: data.items[template].icon, 18: b''})
            for row in rows:
                item = self.broker._world.data.items[row[2]]
                if item.kind in ('weapon', 'armor'):
                    level = 0 if self.args.boss_fixture and row[2] in (672, 667) else 9 if item.kind == 'weapon' else 6
                    row[18] = enchant.enchanted_name(item, level)
                elif row[2] == 14:
                    row[4] = 200
                elif row[2] in (17, 296):
                    row[4] = 10
            frame = inventory.build_kit_frame(rows)
            self.store.grant(1, frame)
            by_template = {row[2]:row[1] for row in rows}
            data = self.broker._world.data
            self.equipment.initialize_kit(1, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                weapon_uid=by_template[672 if self.args.boss_fixture else 3], slots=tuple((data.items[t].slot_key, by_template[t])
                    for t in (117,89,667 if self.args.boss_fixture else 98,104,109,128,129)))
            self.fixture_notes.append(dict(pre_login_strong_kit=dict(
                weapon='+0 ancient sword672' if self.args.boss_fixture else '+9 long sword3',
                armor='+0 ancient plate667; +6 shield117/helmet89/shirt104/cloak109/boots128/gloves129' if self.args.boss_fixture else '+6 shield117/helmet89/armor98/shirt104/cloak109/boots128/gloves129',
                healing={self.args.fixture_heal_template:self.args.fixture_heal_count} if self.args.boss_fixture else {14:200}, haste17=10, brave296=10),
                scope='fresh test supplies; unused starter bag rows omitted before first grant; no user save, live HP, NPC, RNG or combat rule changed'))

    def travel_heading(self, goal, radius, **options):
        bot = self.bot
        bot.terrain = self.broker._world.terrain
        # Keep current living NPC/PC movement occupancy and the stair policy,
        # but share the complete-route planner with the ordinary hunt client.
        # A partial route toward a locally closer wall can otherwise oscillate.
        occupied = {(e.x, e.y) for e in self.broker._world.entities.near(
            bot.map_id, *bot.position, 32, alive_only=True)
            if e.uid != bot.self_uid and e.kind.value != 'item'}
        return bot.route_heading(goal, radius, occupied=occupied,
            excluded={(x, y) for map_id, x, y in self.transitions if map_id == bot.map_id},
            ignore_actors=options.get('ignore_actors', False), max_nodes=200000)

    async def owner_potion(self):
        if not self.args.boss_fixture:
            return await super().owner_potion()
        bot = self.bot
        if (not bot.dead and bot.hp is not None and bot.max_hp
                and bot.hp <= bot.max_hp * self.args.potion_threshold
                and any(row.get(2) == self.args.fixture_heal_template and row.get(4, 0) > 0 for row in bot.inventory.values())):
            await self.use(self.args.fixture_heal_template)

    def observe(self):
        bot, world = self.bot, self.broker._world
        for group in world.spawner.groups:
            row = self.audit_rows.get(group.spec.group_id)
            if row is None:
                continue
            for slot in group.slots:
                uid = slot.uid
                if uid is None:
                    continue
                if uid not in row['issued_uids']:
                    row['issued_uids'].append(uid)
                if uid in bot.appearances_seen and uid not in row['received_uids']:
                    row['received_uids'].append(uid)
                brain = world.ai.brains.get(uid)
                if brain is not None:
                    row['states'][brain.state.value] = row['states'].get(brain.state.value, 0)+1
                entity = world.entities.get(uid)
                if entity is not None:
                    previous = self.seen.get(uid)
                    point = (entity.x, entity.y)
                    if previous is not None and point != previous[0]:
                        if uid not in row['moved_uids']:
                            row['moved_uids'].append(uid)
                        if brain is not None and (brain.state.value == 'wander' or previous[1] == 'wander'):
                            if uid not in row['wander_uids']:
                                row['wander_uids'].append(uid)
                    self.seen[uid] = point, None if brain is None else brain.state.value
        # Packet proof of movement is retained separately from state sampling.
        for frame in bot.peer.frames:
            if frame.ordinal <= getattr(self, 'move_marker', 0) or frame.opcode != 0x4e2c:
                continue
            uid = hb.scalar(frame.values, 1)
            for row in self.audit_rows.values():
                if uid in row['issued_uids']:
                    row.setdefault('wire_move_ordinals', []).append(frame.ordinal)
        self.move_marker = bot.peer.ordinal

    async def beat(self):
        self.observe()
        if self.bot.dead:
            raise hb.BotFailure('AUDIT_OWNER_DIED')
        if self.bot.hp < self.bot.max_hp * .7:
            await self.owner_potion()
        if time.monotonic()-self.bot.last_alive >= .5:
            await self.bot.alive()
        await asyncio.sleep(.05)

    async def dungeon_items(self):
        bot, world = self.bot, self.broker._world
        bot.safe_hunt_cell = lambda point: True
        bot.hunt_target = lambda actor: actor['alive']
        self.loaded = dict(monsters=len(world.data.monsters), groups=len(world.spawner.groups))
        self.record('all_population_loaded', self.loaded == self.expected_population, **self.loaded)
        if self.args.strong_fixture or self.args.boss_fixture:
            await self.use(17)
            await self.use(296)
            state = world.combat.pcs[bot.self_uid]
            self.fixture_notes.append(dict(selected_combat_profile=dataclasses.asdict(state.profile),
                received_speed=dict(bot.speed)))
        self.stage = 'spawn_retry_and_idle_observation'
        until = time.monotonic()+self.args.observe_seconds
        while time.monotonic() < until:
            await self.beat()
        for spec in self.groups:
            row = self.audit_rows[spec.group_id]
            self.stage = 'group_'+spec.group_id
            self.observe()
            if not row['issued_uids']:
                row['errors'].append('NO_SPAWN_AFTER_RETRY_WINDOW')
                continue
            candidates = [uid for uid in row['received_uids'] if uid in bot.actors and bot.actors[uid]['alive']]
            if not candidates:
                # Actual movement towards the spawn rect, no live relocation.
                until = time.monotonic()+self.args.approach_seconds
                # Search the fixed rectangle with normal movement when a corner
                # spawn is outside the initial screen. No server coordinates used.
                rect = spec.rect
                goals = [(x, y) for x in (rect.x1+4, (rect.x1+rect.x2)//2, rect.x2-4)
                    for y in (rect.y1+4, (rect.y1+rect.y2)//2, rect.y2-4)
                    if world.terrain.can_stand(spec.map_id, x, y) is True]
                goal_index = 0
                while time.monotonic() < until and not candidates:
                    if not goals:
                        break
                    goal = goals[goal_index % len(goals)]
                    if hb.distance(bot.position, goal) <= 1:
                        goal_index += 1
                        goal = goals[goal_index % len(goals)]
                    await bot.step(goal, radius=1)
                    await self.beat()
                    candidates = [uid for uid in row['received_uids'] if uid in bot.actors and bot.actors[uid]['alive']]
            if not candidates:
                row['errors'].append('ISSUED_BUT_NO_RECEIVED_ACTOR')
                continue
            uid = min(candidates, key=lambda u: hb.distance(bot.position, bot.actors[u]['position']))
            until = time.monotonic()+self.args.approach_seconds
            before_moves = bot.moves
            combat_marker, slot = None, None
            row['target_uid'] = uid
            row['initial_target_uid'] = uid
            row['approach_start_position'] = bot.position
            row['approach_start_target'] = bot.actors[uid]['position']
            row['corrections_before_approach'] = bot.corrections
            try:
                search_index = 0
                while time.monotonic() < until:
                    # Select only this group's actually received living actors.
                    # Keep a viable pursuit unless another actor is adjacent or
                    # at least two cells closer, so moving peers do not make the
                    # bot switch targets on every observation.
                    live = [candidate for candidate in row['received_uids']
                            if candidate in bot.actors and bot.actors[candidate]['alive']]
                    live.sort(key=lambda candidate: (
                        hb.distance(bot.position, bot.actors[candidate]['position']), candidate))
                    adjacent = [candidate for candidate in live
                                if hb.distance(bot.position, bot.actors[candidate]['position']) <= 1]
                    selected = uid
                    if adjacent:
                        selected = uid if uid in adjacent else adjacent[0]
                    elif live:
                        current = bot.actors.get(uid)
                        current_distance = (hb.distance(bot.position, current['position'])
                                            if current is not None and current['alive'] else float('inf'))
                        current_reachable = (uid in live and
                            self.travel_heading(current['position'], 1, require_reached=True) is not None)
                        for candidate in live:
                            candidate_goal = bot.actors[candidate]['position']
                            if (candidate == uid or (current_reachable and
                                    hb.distance(bot.position, candidate_goal)+2 > current_distance)):
                                continue
                            if self.travel_heading(candidate_goal, 1, require_reached=True) is not None:
                                selected = candidate
                                break
                    if selected != uid:
                        uid = selected
                        row['target_uid'] = uid
                        search_index = 0
                    actor = bot.actors.get(uid)
                    if actor is not None:
                        if not actor['alive'] or hb.distance(bot.position, actor['position']) <= 1:
                            break
                        goal = actor['position']
                    else:
                        # A screen-removal packet is not a death. Walk toward
                        # the last received position, then look around it within
                        # the same approach budget; never read its hidden live
                        # coordinate from the server registry to pursue it.
                        last = bot.last_seen_actors.get(uid)
                        if last is None or not last['alive'] or last['map_id'] != bot.map_id:
                            break
                        goal = last['position']
                        if not search_index and hb.distance(bot.position, goal) <= 1:
                            search_index = 1
                        if search_index:
                            dx, dy = hb.DELTAS[(search_index-1) % 8]
                            goal = goal[0]+dx*4, goal[1]+dy*4
                            if hb.distance(bot.position, goal) <= 1:
                                search_index += 1
                    await bot.step(goal, radius=1)
                    await self.beat()
                if uid not in bot.actors or hb.distance(bot.position, bot.actors[uid]['position']) > 1:
                    row['errors'].append('APPROACH_NOT_REACHED')
                    if uid in bot.actors:
                        goal = bot.actors[uid]['position']
                        row['bounded_static_route_found'] = (hb.distance(bot.position, goal) <= 1 or
                            self.travel_heading(goal,1,require_reached=True,ignore_actors=True) is not None)
                        row['navigation_classification'] = ('STATIC_ROUTE_FOUND_DYNAMIC_TARGET_OR_OCCUPANCY_UNRESOLVED'
                            if row['bounded_static_route_found'] else 'BOT_ASTAR_200000_NODES_NO_ROUTE_TERRAIN_DISCONNECTION_UNKNOWN')
                    continue
                row['approached_uids'].append(uid)
                row['accepted_approach_steps'] = bot.moves-before_moves
                key = (spec.map_id, spec.template_id)
                if key in self.done:
                    row['combat'] = 'REPRESENTATIVE_OTHER_GROUP'
                    row['representative_group'] = self.done[key]
                    continue
                row['combat'] = 'ATTEMPTED'
                slot = world.spawner.slot_for(uid)[1]
                hp_before = slot.hp
                row['hp_before'] = hp_before
                combat_marker = bot.peer.ordinal
                until = time.monotonic()+self.args.combat_seconds
                while uid not in bot.kills and time.monotonic() < until:
                    if uid not in bot.actors or not bot.actors[uid]['alive']:
                        break
                    if hb.distance(bot.position, bot.actors[uid]['position']) <= 1:
                        await bot.attack(uid)
                    else:
                        await bot.step(bot.actors[uid]['position'], radius=1)
                    await self.beat()
                if uid in bot.kills:
                    row['combat'] = 'KILLED'
                    row['killed_uids'].append(uid)
                    self.done[key] = spec.group_id
                    await bot.alive()
                    for ground_uid, item in tuple(bot.ground.items()):
                        entity = world.entities.get(ground_uid)
                        ground = None if entity is None else world.ground.get(entity.ref)
                        if ground is None or ground.source_ref.uid != uid or ground.owner_uid != bot.self_uid:
                            continue
                        row['drops'].append(dict(uid=ground_uid, npc_uid=uid, template=ground.item_id,
                            count=ground.count, grade=ground.grade, position=[ground.x, ground.y]))
                        if hb.distance(bot.position, item['position']) <= 1:
                            old = bot.pickups
                            await bot.pickup(ground_uid)
                            if bot.pickups > old:
                                row['picked'].append(ground_uid)
                    row['drop_result'] = 'OBSERVED' if row['drops'] else 'ZERO_ROLL_OBSERVED_NOT_ERROR'
                else:
                    row['combat'] = 'NOT_KILLED_WITHIN_BUDGET'
            except hb.BotFailure as error:
                row['errors'].append(str(error))
                if bot.dead or bot.peer.error is not None:
                    raise
            finally:
                row['last_owner_position'] = bot.position
                row['last_target_position'] = None if uid not in bot.actors else bot.actors[uid]['position']
                row['last_received_target_position'] = bot.last_seen_actors.get(uid, {}).get('position')
                row['accepted_approach_steps'] = bot.moves-before_moves
                row['corrections_after'] = bot.corrections
                row['final_combat_profile'] = dataclasses.asdict(world.combat.pcs[bot.self_uid].profile)
                row['npc_magic_events'] = [dict(event) for event in getattr(self.broker, '_world_magic_events', ())
                    if event.get('npc_uid') == uid]
                if combat_marker is not None and slot is not None:
                    swings = [f for f in bot.peer.frames if f.ordinal > combat_marker
                        and f.opcode == 0x4e31 and hb.scalar(f.values,2) == bot.self_uid
                        and hb.scalar(f.values,3) == uid]
                    row['swings'] = len(swings)
                    row['swing_raw_effect_counts'] = dict(Counter(hb.scalar(f.values,4) for f in swings))
                    row['hp_after'] = slot.hp
                    row['hp_decreased'] = slot.hp < row['hp_before']
                    row['combat_observation_end_ordinal'] = bot.peer.ordinal
        self.observe()


def source_metadata():
    rows = {}
    for phase in ('m1', 'm3', 'm4', 'm5', 'm6'):
        path = Path(__file__).parent/'data'/phase/'spawns.json'
        for row in json.loads(path.read_text(encoding='utf-8'))['groups']:
            rows[row['group_id']['value']] = dict(file=str(path), town_id=row.get('town_id'),
                field_id=row.get('field_id'), region=row.get('region'),
                population_area=row.get('population_area'), rect_source=row['rect'])
    return rows


def write_tables(directory, rows, data):
    header = '|map/지역|group|template/name|생성 수신/목표|배회/이동UID|접근|전투|HP감소|처치|드롭/줍기|오류|원결과|\n|---|---|---|---|---|---|---|---|---|---|---|---|\n'
    text = '# 개발 fixture 스폰 감사\n\n4E96은 표시 패킷 수신이며 native sprite 렌더링은 UNKNOWN. 배회는 AI 상태와 위치 관측, 이동 패킷 ordinal은 JSON에 별도 보존. 무드롭은 오류 아님.\n\n'+header
    for r in rows:
        source = r.get('source', {})
        errors = list(r['errors']) + ([f"epoch:{r['error']}"] if r.get('error') else [])
        text += '|'+ '|'.join(map(str, (f"{r['map_id']}/{source.get('population_area') or source.get('town_id') or source.get('region') or ''}", r['group'], f"{r['template']} {data.monsters[r['template']].name_ko}",
            f"{len(r['received_uids'])}/{r['expected_slots']}", f"{len(r['wander_uids'])}/{len(r['moved_uids'])}",
            len(r['approached_uids']), r['combat'], r['hp_decreased'], len(r['killed_uids']),
            f"{len(r['drops'])}/{len(r['picked'])} {r.get('drop_result','UNTESTED')}", ';'.join(errors), f"[{r['epoch']}](epoch-{r['epoch']:03}/result.json)")))+'|\n'
    (directory/'groups.md').write_text(text, encoding='utf-8')
    pairs = []
    for key in sorted({(r['map_id'],r['template']) for r in rows}):
        subset = [r for r in rows if (r['map_id'], r['template']) == key]
        best = min(subset, key=lambda r:(r['combat'] != 'KILLED', not r['hp_decreased'], not bool(r['received_uids'])))
        pairs.append(dict(map_id=key[0], template=key[1], monster=data.monsters[key[1]].name_ko,
            groups=[r['group'] for r in subset], representative=best['group'], combat=best['combat'],
            spawned=any(r['issued_uids'] for r in subset), received=any(r['received_uids'] for r in subset),
            wander=any(r['wander_uids'] for r in subset), hp_decreased=best['hp_decreased'],
            kills=len(best['killed_uids']), drops=len(best['drops']),
            errors=list(best['errors'])+([f"epoch:{best['error']}"] if best.get('error') else []), epoch=best['epoch']))
    (directory/'monster-map.json').write_text(json.dumps(pairs, ensure_ascii=False, indent=2), encoding='utf-8')
    text = '# 몬스터 × 맵 대표 전투\n\n같은 맵/template의 대표 그룹 전투이며 나머지 지역별 행은 groups.md 참조. 드롭0은 확률 실패로 판정하지 않는다.\n\n|map|template/name|대표group|수신|배회|전투|HP감소|처치|드롭|오류|\n|---|---|---|---|---|---|---|---|---|---|\n'
    for r in pairs:
        text += '|'+ '|'.join(map(str, (r['map_id'],f"{r['template']} {r['monster']}",r['representative'],
            r['received'],r['wander'],r['combat'],r['hp_decreased'],r['kills'],r['drops'],';'.join(r['errors']))))+'|\n'
    (directory/'monster-map.md').write_text(text,encoding='utf-8')
    return pairs


async def run(args):
    from tools.local_original_session.world_terrain import WorldTerrain
    root = Path(__file__).resolve().parents[2]/'work/local_original_session/runs'
    directory = Path(tempfile.mkdtemp(prefix='spawn-audit-', dir=root))
    data, metadata = all_data(), source_metadata()
    selections = [g for g in data.spawns if (not args.maps or g.map_id in args.maps)
                  and (not args.groups or g.group_id in args.groups)]
    batches = {}
    for g in selections:
        key = (g.map_id, g.rect, g.group_id) if args.one_group_per_epoch else (g.map_id, g.rect)
        batches.setdefault(key, []).append(g)
    if args.limit:
        batches = dict(list(batches.items())[:args.limit])
    selections = [g for groups in batches.values() for g in groups]
    print(json.dumps(dict(output_directory=str(directory), batches=len(batches), groups=sum(map(len,batches.values())),
        templates=len(data.monsters), scope='DEVELOPMENT_FIXTURE')), flush=True)
    hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path(__file__), *sorted((Path(__file__).parent/'data').glob('m*/*.json')))}
    all_rows, epochs, done = [], [], {}
    original_bot = hs.ScenarioBot
    hs.ScenarioBot = AuditBot
    try:
        terrain = WorldTerrain.load(map_ids=tuple({g.map_id for g in selections}))
        for index, (batch_key, groups) in enumerate(batches.items(), 1):
            map_id, rect = batch_key[:2]
            output = directory/f'epoch-{index:03}'
            output.mkdir()
            scene = Audit(args, output, groups, done)
            try:
                scene.map_start = start_cell(terrain, map_id, rect)
            except Exception as error:
                # No broker has been constructed at this point.
                result = dict(status='FAIL', failure=f'{type(error).__name__}: {error}', cleanup_complete=scene.broker is None)
                (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            else:
                result = await scene.run_matrix()
            for row in scene.audit_rows.values():
                row.update(epoch=index, source=metadata[row['group']], error=result.get('failure'),
                    cleanup_complete=result['cleanup_complete'])
                all_rows.append(row)
            epochs.append(dict(epoch=index, groups=[g.group_id for g in groups], result=result['status'],
                error=result.get('failure'), cleanup_complete=result['cleanup_complete']))
            (directory/'groups.json').write_text(json.dumps(matrix.safe(all_rows), ensure_ascii=False, indent=2),encoding='utf-8')
            print(json.dumps(dict(epoch=index,total=len(batches),map=map_id,groups=len(groups),status=result['status'],
                received=sum(bool(r['received_uids']) for r in scene.audit_rows.values()),
                killed=sum(r['combat']=='KILLED' for r in scene.audit_rows.values()),error=result.get('failure')),ensure_ascii=False),flush=True)
            if not result['cleanup_complete']:
                break
    finally:
        hs.ScenarioBot = original_bot
    pairs = write_tables(directory, all_rows, data)
    summary = dict(output_directory=str(directory), scope=f'DEVELOPMENT saved-position/Lv{args.fixture_level} test_knight fixture; ordinary socket actions; native render/input UNKNOWN',
        strong_fixture=args.strong_fixture, boss_fixture=args.boss_fixture,
        expected_groups=len(selections), rows=len(all_rows), batches=len(epochs),
        spawned=sum(bool(r['issued_uids']) for r in all_rows), received=sum(bool(r['received_uids']) for r in all_rows),
        approached=sum(bool(r['approached_uids']) for r in all_rows), wandered=sum(bool(r['wander_uids']) for r in all_rows),
        monster_map_pairs=len(pairs), killed_pairs=sum(r['combat']=='KILLED' for r in pairs),
        drops=sum(len(r['drops']) for r in all_rows), group_error_counts=dict(Counter(e for r in all_rows
            for e in (list(r['errors'])+([f"epoch:{r['error']}"] if r.get('error') else [])))),
        epochs=epochs, source_sha256=hashes, cleanup_complete=all(r['cleanup_complete'] for r in epochs))
    (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--maps',type=int,nargs='*')
    cli.add_argument('--groups',nargs='*',help='explicit group IDs for bounded retry')
    cli.add_argument('--strong-fixture',action='store_true')
    cli.add_argument('--boss-fixture',action='store_true',help='catalog ancient equipment and selected healing supplies before login')
    cli.add_argument('--fixture-heal-template',type=int,choices=(130,279),default=130)
    cli.add_argument('--fixture-heal-count',type=int,default=150)
    cli.add_argument('--fixture-level',type=int,default=30,
                     help='pre-login saved fixture level from the loaded growth table')
    cli.add_argument('--one-group-per-epoch',action='store_true')
    cli.add_argument('--limit',type=int,default=0)
    cli.add_argument('--timeout',type=hb.positive,default=8)
    cli.add_argument('--observe-seconds',type=hb.positive,default=16)
    cli.add_argument('--approach-seconds',type=hb.positive,default=45)
    cli.add_argument('--combat-seconds',type=hb.positive,default=420)
    cli.set_defaults(scenario='dungeon_items',minutes=1,potion_threshold=.7,companion_revive_exp=False,navigation_timeout=60)
    with matrix.environment(SL_EXPERIMENT_MAP=2,SL_EXPERIMENT_M5=1,SL_EXPERIMENT_SHOP=1,
            SL_COMPANION=0,SL_COMPANION_PET_UI=0,SL_SPELL_EXP=0,SL_COMPANION_REVIVE_EXP=0):
        result=asyncio.run(run(cli.parse_args(argv)))
    print(json.dumps({k:v for k,v in result.items() if k not in ('epochs','source_sha256')},ensure_ascii=False))
    return 0 if result['cleanup_complete'] else 1


if __name__=='__main__':
    raise SystemExit(main())
