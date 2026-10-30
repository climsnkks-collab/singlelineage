"""LOCAL Cancel development checks: real owners/stores/wire, no game/socket PASS."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import world_feature_magic as magic_feature
from tools.local_original_session import world_feature_companion as companion_feature
from tools.local_original_session import world_feature_monster_skills as monster_feature
from tools.local_original_session import world_magic, world_magic_tests, world_registry
from tools.local_original_session import world_monster_skills as skills
from tools.local_original_session import monster_skills_tests as monsters
from tools.local_original_session import world_companion_equipment_tests as equipment
from tools.local_original_session import world_companion_magic_tests as companion_magic
from tools.local_original_session.world_companion import CompanionStore, record_from_row


class CancelTests(unittest.TestCase):
    def setUp(self):
        self.f = world_magic_tests.WorldConsumerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.ctx, self.view, self.engine = self.f.ctx, self.f.view, self.f.magic
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        self.ctx._world_magic_store = world_magic.MagicStore(SimpleNamespace(profile=self.profile))
        self.ctx._world_magic_buff_ui = True
        self.now = self.f.fixture.now

    def target(self, uid=1):
        return next((value for value in self.ctx.collect_sync_hooks('cancel_magic_target', uid)
                     if value is not None), None)

    def buff(self):
        state = self.engine.state(1)
        state.learned.update((2, 7, 11))
        state.buffs.update({2: self.now + 100, 7: self.now + 100, 11: self.now + 100})
        state.weapon_uids[7] = 123
        state.armor_uids[11] = 456
        state.next_cast_at = self.now + 4
        self.engine.apply_status(1, 'counter_magic', self.now, 100, spell=30)
        self.engine.apply_status(1, 'slow', self.now, 100, spell=28)
        self.engine.apply_status(1, 'weapon_break', self.now, None, params={'weapon_uid': 123})
        state.poison = dict(until=self.now + 30, next_tick=self.now + 3,
                            tick_seconds=3, damage=5, source_uid=999)
        self.ctx._world_recalculate_uid(1)
        self.ctx._world_magic_sync_icons(1, self.now)
        self.view.drain(1)
        return state

    def test_public_pc_cancel_recalculates_then_durable_save_then_actual_4e91_delete(self):
        state = self.buff()
        learned = set(state.learned)
        order = []
        recalculate = self.ctx._world_recalculate_uid
        save = self.ctx._world_magic_save
        sync = self.ctx._world_magic_sync_icons
        def stats(uid):
            self.assertFalse(state.buffs)
            order.append('stats')
            recalculate(uid)
        def persist(uid):
            self.assertEqual(self.view.combat.pcs[uid].profile.ac, 10)
            order.append('save')
            save(uid)
        def icons(uid, now):
            self.assertTrue(self.ctx._world_magic_store.path.exists())
            order.append('icons')
            sync(uid, now)
        self.ctx._world_recalculate_uid, self.ctx._world_magic_save = stats, persist
        self.ctx._world_magic_sync_icons = icons
        self.assertEqual(self.target()(self.now), (2, 7, 11))
        self.assertEqual(order, ['stats', 'save', 'icons'])
        self.assertEqual((state.learned, state.next_cast_at), (learned, self.now + 4))
        self.assertFalse(state.weapon_uids or state.armor_uids)
        self.assertEqual(set(state.effects), {'slow', 'weapon_break'})
        self.assertIsNotNone(state.poison)
        wires = self.view.drain(1)
        for key in (2, 7, 11, 30):
            self.assertIn(magic_feature.buff_icon_frame(key,
                magic_feature.SPELL_BUFF_ICONS[key], 0, remove=True), wires)
        # A hostile Slow icon remains, including after a cold save/restore.
        self.assertEqual(set(self.ctx._world_magic_icons), {(1, 28)})
        cold = world_magic.MagicStore(SimpleNamespace(profile=self.profile))
        restored = world_magic.PlayerMagic(world_magic.load_catalog())
        row = cold.rows[1]
        restored.restore(1, row, 500, wall=row['saved_at'])
        self.assertFalse(restored.state(1).buffs)
        self.assertEqual(set(restored.state(1).effects), {'slow', 'weapon_break'})

    def test_pc_save_failure_propagates_before_icon_deletion_and_stale_callback_refuses(self):
        self.buff()
        cancel = self.target()
        with patch.object(self.ctx._world_magic_store, 'save', side_effect=OSError('disk-full')):
            with self.assertRaisesRegex(OSError, 'disk-full'):
                cancel(self.now)
        self.assertIn((1, 2), self.ctx._world_magic_icons)
        self.assertFalse(any(int.from_bytes(w[2:4], 'little') == 0x4e91
                             for w in self.view.drain(1)))
        self.view.combat.pcs[1].dead = True
        self.assertIsNone(self.target())
        with self.assertRaisesRegex(ValueError, 'CURRENT_TARGET'):
            cancel(self.now)

    def prepare_queen(self):
        data = monsters.all_data()
        entity, _ = self.f.fixture.monster(7)
        monster = data.monsters[454]
        group, slot = self.view.spawner.slot_for(entity.uid)
        group.monster, group.spec = monster, replace(group.spec, template_id=454)
        entity.template_id, slot.hp = 454, monster.hp
        self.ctx._world_registry = world_registry.build_registry((magic_feature, monster_feature))
        for fn in monster_feature.METHODS:
            setattr(self.ctx, fn.__name__, MethodType(fn, self.ctx))
        monster_feature._monster_skills_initialize(self.ctx)
        monster_feature._monster_skills_started(self.ctx)
        owner = self.ctx._world_monster_skills
        self.addCleanup(owner.close)
        row = next(r for r in owner.attacks[monster.l1j_npcid] if r['kind'] == 'cancel')
        return entity, monster, row, owner

    def test_queen_registered_cancel_real_ai_target_cost_reuse_range_and_owner_absence(self):
        self.buff()
        entity, monster, row, owner = self.prepare_queen()
        target = self.view.entities.get(1)
        self.view._refresh(1)
        self.view.drain(1)
        owner.attacks = {monster.l1j_npcid: (dict(row, chance_percent=100),)}
        self.view.ai.brains[entity.uid].monster = monster
        self.view.ai.on_hit(entity.uid, 1, self.now)
        before = self.view.combat.pcs[1].hp
        self.view.ai._act(entity.uid, self.now)
        event = owner.events[-1]
        self.assertEqual((event['target'], event['outcome'], event['mp_before'] - event['mp_after']),
                         (1, 'buffs_cancelled', 40))
        self.assertEqual(self.view.combat.pcs[1].hp, before)
        self.assertEqual(event['removed_buffs'], [2, 7, 11])
        self.assertFalse(owner.cast(entity, monster, target, row, self.now + .1))
        self.assertIn(0x4ed8, [int.from_bytes(w[2:4], 'little') for w in self.view.drain(1)])
        mana = owner.resources.mana_of(entity.ref, monster.mp)
        self.view.entities.move(1, entity.map_id, entity.x + 7, entity.y)
        self.assertFalse(owner.cast(entity, monster, target, row, self.now + 2))
        self.view.entities.move(1, entity.map_id, entity.x + 1, entity.y)
        owner.cancel_target = lambda uid: None
        self.assertFalse(owner.cast(entity, monster, target, row, self.now + 2))
        self.assertEqual(owner.resources.mana_of(entity.ref, monster.mp), mana)
        self.assertEqual(row['chance_percent'], 10)


class CompanionCancelTests(unittest.TestCase):
    def test_companion_stats_saved_restore_owner_hud_preserved_and_stale_actor_refused(self):
        f = equipment.CompanionEquipmentTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        view, actor, record, ctx = f.fixture.view, f.actor, f.record, f.ctx
        view.companion_ai.inventory = f.bags
        # Reuse the actual CompanionMagic setup/canonical catalog.
        source = companion_magic.MagicTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        magic = companion_feature.CompanionMagic(view, {}, source.magic.growth,
            source.magic.policy, source.magic.attributes)
        view.companion_ai.magic = magic
        magic.install_inventory()
        record.learned_spells = (2, 25)
        state = magic.engine.state(record.character_id)
        state.learned = set(record.learned_spells)
        state.buffs = {2: 110, 25: 110}
        actor.shield_until = 110
        f.bags.refresh(2, publish=False)
        buffed = view.companion_profiles[2]
        ctx._companion_enabled = True
        ctx._companion_ailments = None  # Cancel never touches hostile ailments.
        store = CompanionStore(Path(f.temp.name) / 'characters.json')
        order = []
        refresh = f.bags.refresh
        def calculate(uid, **kw):
            self.assertFalse(state.buffs)
            self.assertEqual(actor.shield_until, 0)
            order.append('stats')
            refresh(uid, **kw)
        f.bags.refresh = calculate
        def save(uid):
            order.append('save')
            self.assertLess(view.companion_profiles[2].dexterity, buffed.dexterity)
            self.assertGreater(view.companion_profiles[2].ac, buffed.ac)
            store.commit(view, uid)
        ctx._companion_save = save
        owner_icon = magic_feature.buff_icon_frame(2, magic_feature.SPELL_BUFF_ICONS[2], 100)
        view._queue(1, owner_icon)
        self.assertIn(owner_icon, view.drain(1))
        view.drain(1)
        cancel = companion_feature._companion_cancel_magic_target(ctx, actor.ref.uid)
        self.assertEqual(cancel(10), (2, 25))
        self.assertEqual(order, ['stats', 'save'])
        saved = record_from_row(CompanionStore(Path(f.temp.name) / 'characters.json').payload['records'][0])
        fresh = world_magic.PlayerMagic(world_magic.load_catalog())
        row = saved.equipment['magic_buffs']
        fresh.restore(2, row, 500, wall=row['saved_at'])
        self.assertFalse(fresh.state(2).buffs)
        # No companion icons were published; the owner's same-key 4E91 is
        # untouched instead of being deleted on behalf of a different actor.
        self.assertFalse(any(int.from_bytes(w[2:4], 'little') == 0x4e91
                             for w in view.drain(1)))
        # The same registered consumer reaches a companion selected by its
        # runtime actor UID, rather than confusing it with character UID 2.
        ctx._world_registry = world_registry.build_registry((companion_feature,))
        for fn in companion_feature.METHODS:
            setattr(ctx, fn.__name__, MethodType(fn, ctx))
        ctx._companion_save = save
        ctx.collect_sync_hooks = lambda name, *args: world_registry.collect_sync_hooks(name, ctx, *args)
        def contribution(name, uid):
            return next((value for value in ctx.collect_sync_hooks(name, uid) if value is not None), None)
        owner = skills.MonsterSkills(view, skills.load_attacks(),
            magic_target=lambda uid: contribution('npc_magic_target', uid),
            cancel_target=lambda uid: contribution('cancel_magic_target', uid))
        owner.start()
        self.addCleanup(owner.close)
        entity, _ = f.fixture.monster(7)
        queen = monsters.all_data().monsters[454]
        group, slot = view.spawner.slot_for(entity.uid)
        group.monster, group.spec = queen, replace(group.spec, template_id=454)
        entity.template_id, slot.hp = 454, queen.hp
        row = next(r for r in owner.attacks[queen.l1j_npcid] if r['kind'] == 'cancel')
        # Restore a real buff through its ordinary engine before casting again.
        state.buffs = {2: 110, 25: 110}
        actor.shield_until = 110
        f.bags.refresh = refresh
        refresh(2, publish=False)
        order.clear()
        self.assertTrue(owner.cast(entity, queen, view.entities.resolve(actor.ref), row, 10))
        event = owner.events[-1]
        self.assertEqual((event['target'], event['outcome'], event['removed_buffs']),
                         (actor.ref.uid, 'buffs_cancelled', [2, 25]))
        self.assertEqual(event['mp_before'] - event['mp_after'], 40)
        self.assertFalse(state.buffs)
        self.assertEqual(record.hp, event['hp_before'])
        with patch.object(ctx, '_companion_save', side_effect=OSError('disk-full')):
            with self.assertRaisesRegex(OSError, 'disk-full'):
                cancel(10)
        view.dismiss_companions(1)
        self.assertIsNone(companion_feature._companion_cancel_magic_target(ctx, actor.ref.uid))
        with self.assertRaisesRegex(ValueError, 'CURRENT_TARGET'):
            cancel(10)


if __name__ == '__main__':
    unittest.main()
