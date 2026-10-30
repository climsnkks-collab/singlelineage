"""Scoped real-packet curse/equipment/save scenario using the existing Matrix.

Fresh pre-login supplies only. The retained-memory fixture is the existing
Matrix test adapter; no original client/input/rendering equivalence is claimed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_play_matrix as matrix
from tools.local_original_session import inventory, world_enchant_inventory as enchant


class CurseMatrix(matrix.Matrix):
    def initialize_accessory_fixture(self):
        from tools.local_original_session import equipment_store
        before = self.broker._inventory_kit_frame(1)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(before)]
        self.curse_uids = {}
        for template, grade in ((40, 2), (88, 2), (101, 0), (24, 1), (25, 2)):
            fields = dict(self.broker.INVENTORY_STARTER_FIELDS)
            uid = max(row[1] for row in rows) + 1
            definition = self.broker._world.data.items[template]
            fields.update({1: uid, 2: template, 4: 3 if template in (24, 25) else 1,
                           7: definition.icon,
                           18: enchant.scroll_name(template, grade) if template == 25 else
                               enchant.enchanted_name(definition, 0, grade=grade)})
            rows.append(fields)
            self.curse_uids[template] = uid
        after = inventory.build_kit_frame(rows)
        self.store.grant(1, after)
        by_template = {row[2]: row for row in rows[:len(rows)-5]}
        definitions = self.broker._world.data.items
        worn = [entry.template_id for entry in self.broker._world.data.starter.entries(1, 'test_knight')
                if entry.equipped]
        self.equipment.initialize_kit(1, after, initialization=equipment_store.FIRST_ENABLE_EMPTY,
            weapon_uid=next((by_template[t][1] for t in worn if definitions[t].kind == 'weapon'), 0),
            slots=tuple((definitions[t].slot_key, by_template[t][1]) for t in worn
                        if definitions[t].kind == 'armor'))
        self.fixture_notes.append(dict(pre_login_declared_curse_instances=self.curse_uids,
            source='Fixed-client f21 / m6 elf-forest orc156 equipment40,88 grade2; '
                   'L1J LOCAL removal policy C_ItemUSe.java596..620/3348/3394. '
                   'Declared test supplies, not an observed natural drop',
            inventory_sha256=hashlib.sha256(after).hexdigest()))

    def bag(self):
        return {item.identifier: item for item in inventory.validate_kit_frame(
            self.store.restore(self.bot.self_uid))}

    async def blocked(self, uid):
        before = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
        bag_before = self.store.restore(self.bot.self_uid)
        batch = await self.barrier(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, matrix.RAW0),
                                   label='CURSED_REMOVE_REFUSAL')
        after = self.equipment.restore(self.bot.self_uid, self.store.restore(self.bot.self_uid))
        actual = self.broker._item_equipment_effect._last
        self.record('cursed_toggle_or_replacement_refused_' + str(uid), before == after
            and bag_before == self.store.restore(self.bot.self_uid)
            and not any(frame.opcode == 0x097a for frame in batch)
            and actual['status'] == 'BLOCKED'
            and actual['reason'] == 'ITEM_USE_CURSED_EQUIPMENT_CANNOT_REMOVE',
            uid=uid, equipment_reason=actual['reason'], revision=after.revision)

    async def reconnect(self, label):
        before = self.store.restore(self.bot.self_uid)
        equipment = self.equipment.restore(self.bot.self_uid, before)
        character = self.bot.character
        await self.close()
        await self.open(seed=False, character=character)
        self.record(label, before == self.store.restore(self.bot.self_uid)
            and equipment == self.equipment.restore(self.bot.self_uid, before)
            and self.bot.inventory == hb.displayed_rows(self.store.restore(self.bot.self_uid)))

    async def equip_all(self):
        self.stage = 'curse_equipment_packets'
        normal = self.item(3)[0]
        scroll = self.curse_uids[25]
        before_damage = self.broker._world.combat.pcs[self.bot.self_uid].equipment_calculated.melee_damage_bonus
        for level in (-1, -2):
            await self.use(25, target=normal, item_uid=scroll)
            item = self.bag()[normal]
            self.record('cursed_enchant_result_' + str(level),
                enchant.enchant_level(item, self.bot.data.items[3]) == level and not item.cursed,
                grade=item.bless, level=level,
                distinction='cursed scroll lowers enchant, does not turn equipment into cursed grade')
        state = self.broker._world.combat.pcs[self.bot.self_uid]
        damage = state.equipment_calculated.melee_damage_bonus
        self.record('negative_enchant_actual_damage_consumer', damage == before_damage - 2
                    and state.profile.weapon.enchant == -2,
                    before=before_damage, after=damage, local_policy='existing L1J enchant damage')
        await self.gear_uid(normal)
        await self.gear_uid(normal)
        for template in (40, 88):
            uid = self.curse_uids[template]
            self.record('declared_grade2_' + str(template), self.bag()[uid].cursed)
            await self.gear_uid(uid)
            await self.blocked(uid)
        await self.blocked(normal)
        await self.blocked(self.item(89)[0])
        blessed = self.curse_uids[101]
        await self.gear_uid(blessed)
        await self.gear_uid(blessed)
        self.record('blessed_equipment_removes_normally', self.bag()[blessed].blessed)
        await self.reconnect('cursed_worn_grade_and_equipment_survive_fresh_FIRST')
        await self.blocked(self.curse_uids[40])
        await self.blocked(self.curse_uids[88])
        await self.use(24, item_uid=self.curse_uids[24])
        for template in (40, 88):
            uid = self.curse_uids[template]
            self.record('scroll24_actual_saved_curse_removed_' + str(template),
                not self.bag()[uid].cursed and self.broker._world_item_effects.can_unequip(
                    self.bot.self_uid, uid) and self.bot.inventory[uid][18] == dict(self.bag()[uid].raw_fields)[18])
            self.record('uncursed_equipment_takes_off_' + str(template), not await self.gear_uid(uid))
        await self.reconnect('uncursed_grade_consumed_scroll_and_equipment_survive_fresh_FIRST')
        self.record('no_handler_or_hook_errors', not self.broker._world_handler_errors
                    and not self.broker._world_hook_errors)


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    directory = Path(tempfile.mkdtemp(prefix='hunt-curse-', dir=root))
    source_paths = [Path(__file__).with_name(name) for name in (
        'hunt_bot_curse.py', 'inventory.py', 'item_equipment_effect.py',
        'world_enchant_inventory.py', 'world_item_effects.py', 'world_feature_items.py',
        'world_core_reward.py')]
    started = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    with matrix.environment(SL_EXPERIMENT_MAP=0, SL_EXPERIMENT_SHOP=1,
            SL_EXPERIMENT_WAREHOUSE=1, SL_EXPERIMENT_ENCHANT=0, SL_EXPERIMENT_POLY='orc',
            SL_COMPANION=0, SL_COMPANION_PET_UI=0, SL_SPELL_EXP=0):
        result = await CurseMatrix(args, 'equip_all', directory).run_matrix()
    result['scenario'] = 'curse_equipment'
    result['source_sha256'].update({f'tools.local_original_session.{path.stem}': dict(
        file=str(path), sha256=started[path], basis='on-disk before the first test epoch')
        for path in source_paths})
    result['source_changes_during_run'] = [str(path) for path in source_paths
        if hashlib.sha256(path.read_bytes()).hexdigest() != started[path]]
    result['scope'] = 'real FIRST/login/selection/world and 0960 decoder/router; declared pre-login supplies; no native client/input/render PASS'
    (directory / 'result.json').write_text(json.dumps(matrix.safe(result), ensure_ascii=False,
        indent=2), encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(matrix.parser().parse_args(argv)))
    print(json.dumps(matrix.safe(result), ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
