"""Owned socket-only consumables fixture; no native client, input or screenshots.

Reuses the normal FIRST/login/selection/world, item decoder/router, saved-kit
CAS and Quit/close from hunt_bot_scenarios. Only the fresh pre-login fixture
supplies the declared stacks and deficient MP. It never changes live vitals,
clock, ownership, receipt or readiness to obtain an effect.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import time
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import test_ports


TEMPLATES = (492, 297, 495, 279, 10, 22, 24, 417, 418)


class ConsumableBot(hs.ScenarioBot):
    def __init__(self, args):
        super().__init__(args)
        self.mp = self.max_mp = self.sp = None

    def apply(self, frame):
        super().apply(frame)
        if frame.opcode == 0x4e38 and hb.scalar(frame.values, 1) == self.self_uid:
            self.mp = hb.scalar(frame.values, 12, self.mp)
            self.max_mp = hb.scalar(frame.values, 13, self.max_mp)
            self.sp = hb.scalar(frame.values, 20, self.sp)


class ConsumableScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'consumables', directory)
        self.fixture = None
        self.uses = []
        self.handler_epochs = []

    def record(self, name, ok, **evidence):
        super().record(name, ok, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    @property
    def state(self):
        return self.broker._world.combat.pcs[self.bot.self_uid]

    @property
    def consumable_state(self):
        return self.broker._world_item_effects.state(self.bot.self_uid)

    def saved_consumable_state(self):
        return json.loads((self.directory / 'consumable-effects.json').read_text(encoding='utf-8'))

    def saved_bag(self):
        frame = self.store.restore(self.bot.self_uid)
        if frame is None:
            raise hs.Unconfirmed('CONSUMABLE_SAVED_BAG_UNSUPPLIED')
        # Compare as the server displays them (0964 stack-name projection).
        return hb.displayed_rows(frame)

    def wire_matches_saved(self):
        saved, wire = self.saved_bag(), self.bot.inventory
        if saved.keys() != wire.keys():
            return False
        for uid, canonical in saved.items():
            actual = dict(wire[uid])
            if uid in self.consumable_state.identified:
                name = canonical.get(18, b'')
                label = (name + b' ' + '[확인됨]'.encode('utf-8')).strip()
                if actual.get(18, b'') not in (name, label):
                    return False
                actual[18] = canonical[18]
            if actual != canonical:
                return False
        return True

    def received_identification(self, target_uid):
        return any(frame.opcode == 0x0965
            and any(hb.scalar(hb.fields(raw), 1) == target_uid
                and '[확인됨]'.encode('utf-8') in hb.scalar(hb.fields(raw), 18, b'')
                for raw in frame.values.get(1, ()))
            for frame in self.bot.peer.frames)

    def received_item(self, template):
        return next((uid, row) for uid, row in self.bot.inventory.items()
                    if row.get(2, -1) & 0xffffffff == template and row.get(4, 0) > 0)

    async def open(self, *, seed, character=None):
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(
            self.directory, expected, seed=seed)
        if seed:
            from tools.local_original_session import inventory, movement
            from tools.local_original_session.world_progress import Progress
            before = self.store.restore(1)
            rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(before)]
            next_uid = max(row[1] for row in rows) + 1
            for template in TEMPLATES:
                if any(row[2] == template for row in rows):
                    raise hs.Unconfirmed('FIXTURE_TEMPLATE_ALREADY_SUPPLIED:' + str(template))
                fields = dict(rows[0])
                fields.update({1: next_uid, 2: template, 4: 2,
                               7: self.broker._world.data.items[template].icon})
                rows.append(fields)
                next_uid += 1
            after = inventory.build_kit_frame(rows)
            self.store.replace_kit(1, before, after, append=True)
            self.broker._inventory_current_frame = after
            # Explicit initial LOCAL curse authority, before FIRST/login only.
            # No actual native equipment-removal contract is asserted.
            self.curse_target_uid = self.equipment.peek(1)[0].weapon_uid
            (self.directory / 'consumable-effects.json').write_text(json.dumps(
                dict(version=1, rows=[dict(uid=1, fullness=0,
                    wisdom_remaining=0, breath_remaining=0, identified=[],
                    curses=[self.curse_target_uid], saved_at=time.time())])),
                encoding='utf-8')
            self.broker._world_progress.commit(1, Progress(0, 1, 200, 200))
            self.broker._world_progress.save_vitals(1, (1, 1))
            from tools.local_original_session.hunt_bot_loopback import KNIGHT, START
            town = self.broker._world.data.town
            position = self.broker.realm.positions.restore(movement.Position(1, KNIGHT[0], 0, *START))
            self.broker.realm.positions.commit(position,
                movement.Position(1, KNIGHT[0], town.map_id, town.respawn_x, town.respawn_y))
            self.fixture = dict(character='SoloKnight', uid=1, kit='test_knight',
                templates=list(TEMPLATES), quantity_each=2,
                initial_hp=1, max_hp=200, initial_mp=1, max_mp=200,
                position=[town.map_id, town.respawn_x, town.respawn_y],
                inventory_sha256=hashlib.sha256(after).hexdigest(),
                initial_consumable_state=dict(fullness=0,
                    curses=[self.curse_target_uid], identified=[]),
                initialization='LOCAL independent pre-login development fixture: '
                    'existing test_knight kit/equipment, declared added saved stacks and '
                    'declared HP/MP/maxima through existing stores; no user saves',
                presentation='retained kit raw0 fields plus data icon; native rendering unverified')
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected,
            '--minutes', str(self.args.minutes), '--timeout', str(self.args.timeout)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = ConsumableBot(options)
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = self.broker._world.data, time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'FIXTURE_KIT_DELIVERY')
        self.record('FIRST_login_selection_world_' + str(len(self.bots)),
            self.bot.selected and self.bot.inventory_received and self.bot.hp > 0,
            uid=self.bot.self_uid, map_id=self.bot.map_id, position=self.bot.position,
            hp=self.bot.hp, mp=self.bot.mp, max_mp=self.bot.max_mp)

    async def close(self):
        if self.broker is not None:
            self.handler_epochs.append(dict(
                handler_errors=list(getattr(self.broker, '_world_handler_errors', ())),
                item_errors=list(getattr(self.broker, '_world_item_errors', ()))))
        return await super().close()

    @staticmethod
    def params(target_uid=None):
        value = hb.uint(1, 1)
        if target_uid is not None:
            value += hb.uint(2, target_uid) + hb.uint(3, 0)
        return value + hb.uint(15, 0) + hb.uint(16, 0)

    async def use(self, template, *, target_uid=None):
        uid, item = self.received_item(template)
        quantity = item[4]
        before_mp, before_sp = self.state.mp, self.bot.sp
        params = self.params(target_uid)

        def consumed(batch):
            return next((frame for frame in batch if frame.opcode == 0x0965
                and any(hb.scalar(hb.fields(raw), 1) == uid
                    and hb.scalar(hb.fields(raw), 4) == quantity - 1
                    for raw in frame.values.get(1, ()))), None)

        batch = await self.bot.peer.request(0x0960,
            hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
            check=consumed, label='CONSUMABLE_' + str(template))
        await self.bot.alive()
        saved, wire = self.saved_bag(), self.bot.inventory
        row = dict(template=template, uid=uid, quantity_before=quantity,
            wire_quantity_after=wire[uid][4], saved_quantity_after=saved[uid][4],
            mp_before=before_mp, mp_after=self.state.mp, sp_before=before_sp, sp_after=self.bot.sp,
            response_opcodes=[f'{frame.opcode:04X}' for frame in batch])
        self.uses.append(row)
        self.record('owned_UID_socket_and_saved_consumption_' + str(template),
            wire[uid][4] == saved[uid][4] == quantity - 1, **row)
        return row

    async def refused(self, template, reason, *, target_uid=None):
        """An alive barrier proves processing, never successful item use."""
        uid, item = self.received_item(template)
        before = self.saved_bag()
        batch = await self.bot.peer.request(0x0960,
            hb.uint(1, uid) + hb.pb.encode_bytes(2, self.params(target_uid)),
            alive=True, check=lambda frames: hb.find(frames, 0x4f57),
            label='CONSUMABLE_REFUSAL_' + str(template))
        errors = list(self.broker._world_item_errors)
        self.record('owned_UID_reasoned_refusal_' + str(template),
            before == self.saved_bag() == self.bot.inventory
            and any(reason in error for error in errors),
            template=template, uid=uid, quantity=item[4], target_uid=target_uid,
            reason=reason, observed_errors=errors,
            response_opcodes=[f'{frame.opcode:04X}' for frame in batch])

    async def wait_current(self, predicate, timeout=25):
        until = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= until:
                raise hs.Unconfirmed('NATURAL_CONSUMABLE_EFFECT_TIMEOUT')
            if time.monotonic() - self.bot.last_alive >= 1:
                await self.bot.alive()
            await asyncio.sleep(.05)
        await self.bot.alive()

    async def consumables(self):
        uid = self.bot.self_uid
        self.record('declared_prelogin_MP_deficit_received',
            self.state.mp == self.bot.mp == 1 and self.state.max_mp == self.bot.max_mp == 200,
            actual_mp=self.state.mp, wire_mp=self.bot.mp, max_mp=self.bot.max_mp)
        # The normal knight fixture must receive the actual class refusal.
        await self.refused(297, 'WISDOM_MAGE_REQUIRED')
        hp_before = self.state.hp
        await self.use(279)
        healed = self.state.hp - hp_before
        self.record('ent_fruit_positive_heal_and_SC4E38',
            44 <= healed <= 107 and self.bot.hp == self.state.hp,
            before_hp=hp_before, after_hp=self.state.hp, wire_hp=self.bot.hp,
            healed_hp=healed, official_range=[44, 107])
        blue = await self.use(492)
        base = self.broker._world.data.town.regen.mp_amount(self.state.profile.wis)
        bonus = max(self.state.profile.wis, 11) - 5
        expected_mp = min(self.state.max_mp, blue['mp_before'] + base + bonus)
        before_tick = self.broker._world.runtime.clock()
        await self.wait_current(lambda: self.state.mp >= expected_mp and self.bot.mp == self.state.mp)
        self.record('blue_real_natural_regen_tick_and_SC4E38_MP',
            self.state.mp == self.bot.mp == expected_mp and self.state.mp_points == 0,
            before_mp=blue['mp_before'], after_mp=self.state.mp, wire_mp=self.bot.mp,
            ordinary_recovery=base, added_recovery=bonus,
            elapsed_s=self.broker._world.runtime.clock() - before_tick,
            scope='actual runtime natural MP threshold; no clock/MP/points change after login')
        speed_before = self.broker._world.combat.speed_factor(uid, self.broker._world.runtime.clock())
        await self.use(495)
        now = self.broker._world.runtime.clock()
        expiry, rate = self.state.buffs['haste']
        self.record('greater_green_1800_seconds_and_actual_speed_consumer',
            1798 < expiry - now <= 1800 and rate < speed_before
            and self.broker._world.combat.speed_factor(uid, now) == rate
            and self.bot.speed[0] > 0 and self.bot.speed[1] > 0,
            remaining_s=expiry - now, interval_factor=rate,
            prior_interval_factor=speed_before, received_speed_keys=self.bot.speed,
            scope='saved cost, active combat speed factor and SC4E5B; native animation/cadence unverified')
        fullness = self.consumable_state.fullness
        await self.use(10)
        self.record('food10_positive_fullness_saved',
            self.consumable_state.fullness > fullness,
            before=fullness, after=self.consumable_state.fullness,
            scope='LOCAL fullness authority, no native hunger display claim')
        target_uid = self.curse_target_uid
        target_name = self.bot.inventory[target_uid].get(18, b'')
        self.record('declared_prelogin_cursed_target_bound',
            target_uid in self.bot.inventory and target_uid in self.consumable_state.curses
            and not self.broker._world_item_effects.can_unequip(uid, target_uid),
            target_uid=target_uid,
            scope='declared LOCAL curse authority; actual equipment removal not exercised')
        await self.use(22, target_uid=target_uid)
        self.record('identify22_owned_target_state_and_received_projection',
            target_uid in self.consumable_state.identified
            and self.broker._world_item_effects.item_label(uid, target_uid) == '확인됨'
            and self.received_identification(target_uid)
            and self.saved_bag()[target_uid].get(18, b'') == target_name
            and self.wire_matches_saved(),
            target_uid=target_uid,
            label=self.broker._world_item_effects.item_label(uid, target_uid),
            scope='LOCAL display-only SC0965 projection received; canonical item name preserved; native render unverified')
        await self.use(24, target_uid=target_uid)
        self.record('remove_curse24_owned_target_state_and_canonical_name',
            target_uid not in self.consumable_state.curses
            and self.broker._world_item_effects.can_unequip(uid, target_uid)
            and self.saved_bag()[target_uid].get(18, b'') == target_name
            and self.wire_matches_saved(),
            target_uid=target_uid,
            scope='LOCAL curse authority; actual equipment removal/native display unverified')
        breath_rows = []
        for template in (417, 418):
            before_breath = self.consumable_state.breath_until
            await self.use(template)
            now = self.broker._world.runtime.clock()
            breath_rows.append(dict(template=template,
                before_until=before_breath, remaining_s=self.consumable_state.breath_until - now))
            self.record('underwater' + str(template) + '_actual_timer_saved',
                self.consumable_state.breath_until > now,
                **breath_rows[-1],
                scope='LOCAL breath protection authority; actual underwater damage map unexercised')
        self.record('five_extended_consumables_actually_consumed',
            all(any(row['template'] == template for row in self.uses)
                for template in (10, 22, 24, 417, 418)),
            templates=[10, 22, 24, 417, 418], wisdom297='separate knight class refusal')
        extended_before = dict(fullness=self.consumable_state.fullness,
            identified=sorted(self.consumable_state.identified),
            curses=sorted(self.consumable_state.curses),
            breath_remaining=self.consumable_state.breath_until - self.broker._world.runtime.clock())
        saved_effects = self.saved_consumable_state()
        saved_row = next(row for row in saved_effects['rows'] if row['uid'] == uid)
        self.record('extended_effects_saved_before_Quit',
            saved_row['fullness'] == extended_before['fullness']
            and saved_row['identified'] == extended_before['identified']
            and saved_row['curses'] == extended_before['curses']
            and saved_row['breath_remaining'] > 0,
            saved_effects=saved_effects)
        before_bag, before_mp = self.saved_bag(), self.state.mp
        character = self.bot.character
        self.record('normal_Quit_before_reconnect', await self.bot.quit_selected())
        if not await self.close():
            raise hs.Unconfirmed('CONSUMABLE_FIRST_CLOSE_FAILED')
        saved_vitals = json.loads((self.directory / 'vitals.json').read_text(encoding='utf-8'))
        self.record('normal_Quit_saved_actual_MP',
            next(row['mp'] for row in saved_vitals['rows'] if row['uid'] == uid) == before_mp,
            mp=before_mp, saved_vitals=saved_vitals)
        await self.open(seed=False, character=character)
        self.record('fresh_FIRST_preserves_spent_stacks_and_saved_MP',
            self.saved_bag() == before_bag and self.wire_matches_saved()
            and self.state.mp == self.bot.mp == before_mp,
            mp_before=before_mp, mp_restored=self.state.mp,
            quantities={str(template): self.received_item(template)[1][4] for template in TEMPLATES})
        self.record('fresh_FIRST_received_saved_identification_projection',
            self.received_identification(target_uid)
            and self.saved_bag()[target_uid].get(18, b'') == target_name,
            target_uid=target_uid,
            scope='SC0965 received during re-entry; fixture canonical0964 may follow; native render unverified')
        active = getattr(self.broker._world_item_effects, 'active', {})
        self.record('first_generation_timed_potions_end_with_session_lifetime',
            not self.state.buffs and not active.get(uid),
            scope='existing session-only policy; offline timers/active effect restore not implemented')
        remaining = self.consumable_state.breath_until - self.broker._world.runtime.clock()
        self.record('fresh_FIRST_restores_extended_consumable_state',
            self.consumable_state.fullness == extended_before['fullness']
            and sorted(self.consumable_state.identified) == extended_before['identified']
            and sorted(self.consumable_state.curses) == extended_before['curses']
            and 0 < remaining <= extended_before['breath_remaining'],
            before=extended_before,
            restored=dict(fullness=self.consumable_state.fullness,
                identified=sorted(self.consumable_state.identified),
                curses=sorted(self.consumable_state.curses), breath_remaining=remaining),
            scope='actual normal Quit and fresh FIRST; wall elapsed time is retained')
        self.record('no_unexpected_handler_errors',
            not self.broker._world_handler_errors
            and all(not row['handler_errors'] for row in self.handler_epochs),
            item_refusals=self.handler_epochs[0]['item_errors'])


def parser():
    result = hs.parser()
    result.description = __doc__
    next(action for action in result._actions if action.dest == 'scenario').choices = ('consumables', 'all')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-consumables-', dir=root))
    source_paths = ['hunt_bot_consumables.py', 'hunt_bot.py', 'hunt_bot_scenarios.py',
        'hunt_bot_loopback.py', 'world_item_effects.py', 'world_combat.py',
        'world_feature_items.py', 'world_handlers.py', 'world_bridge.py',
        'world_feature_session.py', 'world_feature_stats.py', 'world_feature_magic.py',
        'world_magic.py', 'world_feature_kit.py', 'world_progress.py', 'broker.py',
        'inventory.py', 'inventory_store.py', 'equipment_store.py',
        'data/m1/items.json', 'data/m1/items_ext/consumables.json',
        'data/m1/item_gfx_ext/consumables.json', 'game_data.py',
        'data/m1/item_effects.json', 'data/m1/starter.json',
        'data/m1/town.json']
    def sources():
        return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in source_paths if (Path(__file__).parent / name).exists()}
    started_sources = sources()
    scenario = ConsumableScenario(args, directory)
    result = await scenario.run()
    result.update(fixture=scenario.fixture, uses=scenario.uses,
        handler_epochs=scenario.handler_epochs,
        scope='LOCAL fresh declared fixture; real FIRST/login/selection/world and '
            'socket decoder/router/owned UID/saved quantity. Native input/rendering '
            'and original-client 30-minute milestone are unverified.',
        source_sha256_start=started_sources, source_sha256=sources())
    result['source_changes_during_run'] = [name for name in source_paths
        if started_sources.get(name) != result['source_sha256'].get(name)]
    result['reused_from'] = {name: result['source_sha256'][name]
        for name in ('hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_loopback.py')}
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False,
        indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
