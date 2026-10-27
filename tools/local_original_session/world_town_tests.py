"""Pure M2 town tests: no native graph, game, server, port, save or temp files."""
import json
import sys
import unittest

from tools.local_original_session.world_entities import EntityRegistry, Kind, UidAllocator
from tools.local_original_session.world_shop import M2_DATA_DIR
from tools.local_original_session.world_town import (
    TownConfig, TownError, TownNpcs, appearance_for, load_town,
)


def _plain(value):
    if hasattr(value, 'items'):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


class WorldTownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_town()

    def town(self, config=None, *, start=0x10000000):
        registry = EntityRegistry(allocate_uid=UidAllocator(start))
        return TownNpcs(registry, self.data, config)

    def click(self, town, entity, **changes):
        arguments = dict(player_map_id=entity.map_id, player_x=entity.x,
                         player_y=entity.y, max_distance=1)
        arguments.update(changes)
        target = entity.uid if entity.uid < (1 << 31) else entity.uid - (1 << 32)
        return town.route_click(target, **arguments)

    def test_complete_raw_documents_and_unknowns_preserved(self):
        for name in ('town_npcs', 'shop_npcs'):
            raw = json.loads((M2_DATA_DIR / (name + '.json')).read_text(encoding='utf-8'))
            self.assertEqual(_plain(self.data.source_documents[name]), raw)
        self.assertEqual(len(self.data.placements), 52)  # 48 town + 21 shop - 17 services.
        self.assertEqual(sum(p.shop_row is not None for p in self.data.placements.values()), 21)
        self.assertEqual(sum(p.spawn['count'] == 0 for p in self.data.placements.values()), 3)
        with self.assertRaises(TypeError):
            self.data.placements[(70523, 87192)].row['mapping_status'] = 'confirmed'

    def test_default_empty_even_for_confirmed_catalog(self):
        town = self.town()
        self.assertEqual(town.register(), ())
        self.assertEqual(len(town.entities), 0)
        self.assertEqual(self.data.placements[(70523, 87192)].mapping_status,
                         'confirmed_catalog_correspondence_only')

    def test_full_optin_keeps_scopes_and_count0(self):
        town = self.town(TownConfig(enable_candidates=True))
        self.assertEqual(len(town.register()), 37)  # 33 ordinary + 4 product merchants.
        self.assertEqual(town.register(), ())
        all_config = TownConfig(enable_candidates=True, include_special=True, include_adjacent=True)
        self.assertEqual(len(town.register(all_config)), 12)  # 2 special + 10 adjacent.
        self.assertEqual(len(town.entities), 49)
        self.assertFalse(any(town.npc_for(e.uid).spawn['count'] == 0 for e in town.entities))

    def test_overlap_dedup_and_fixed_position_heading_no_ai(self):
        ids = {60001, 70100, 70101, 70102, 70529, 70523}
        town = self.town(TownConfig(candidate_npc_ids=ids))
        entities = town.register()
        self.assertEqual(len(entities), 6)
        # randomx/randomy placements spread around the shared centre.
        self.assertEqual(sum((e.x, e.y) == (32575, 32946) for e in entities), 1)
        self.assertEqual(len({(e.x, e.y) for e in entities}), 6)
        for entity in entities:
            spawn = town.npc_for(entity.uid).spawn
            self.assertIs(entity.kind, Kind.NPC)
            self.assertEqual((entity.map_id, entity.heading), (spawn['mapid'], spawn['heading']))
            self.assertLessEqual(abs(entity.x - spawn['locx']), spawn['randomx'])
            self.assertLessEqual(abs(entity.y - spawn['locy']), spawn['randomy'])
        self.assertFalse(hasattr(town, 'tick'))

    def test_repeated_guard_placements_stay_distinct(self):
        town = self.town(TownConfig(candidate_npc_ids={60501, 60502}))
        entities = town.register()
        self.assertEqual(len(entities), 12)
        self.assertEqual(len({town.npc_for(e.uid).key for e in entities}), 12)
        self.assertTrue(all(e.template_id is None for e in entities))
        self.assertTrue(all(town.appearance(e.uid).sprite_id is None for e in entities))

    def test_count0_never_enabled_and_zeno_active_row_survives(self):
        town = self.town(TownConfig(enable_candidates=True, include_special=True))
        town.register()
        zeno = [town.npc_for(e.uid) for e in town.entities if town.npc_for(e.uid).npc_id == 50016]
        self.assertEqual([npc.spawn['id'] for npc in zeno], [90067])
        self.assertFalse(any(town.npc_for(e.uid).npc_id in {50111, 81000} for e in town.entities))

    def test_visibility_metadata_does_not_invent_wire_f39(self):
        town = self.town(TownConfig(candidate_npc_ids={70523, 70014}))
        town.register()
        entities = town.present(0, 32589, 32957, 0)
        self.assertEqual(len(entities), 1)
        appearance = town.appearance(entities[0].uid)
        self.assertEqual((appearance.catalog_template_id, appearance.sprite_id, appearance.name),
                         (300, 988, '가죽 세공사^라다르'))
        self.assertEqual(entities[0].template_id, 300)
        self.assertIsNone(appearance.wire_f39)
        self.assertEqual(town.present(1, 32589, 32957, 17), [])
        pandora = appearance_for(self.data.placements[(70014, 60801)])
        self.assertIsNone(pandora.catalog_template_id)
        self.assertIsNone(pandora.sprite_id)
        self.assertEqual(pandora.sprite_candidate['sprite_id'], 98)
        self.assertEqual(pandora.name_source, 'l1j_reference_label')

    def test_shop_click_returns_existing_listing_and_unknown_rows(self):
        town = self.town(TownConfig(candidate_npc_ids={70014}))
        entity, = town.register()
        result = self.click(town, entity)
        self.assertEqual((result.kind, result.npc.npc_id), ('shop', 70014))
        self.assertEqual((len(result.shop_listing.offers), len(result.shop_listing.unavailable)), (42, 13))
        self.assertIsNone(result.classic_menu_stem)
        self.assertIn('CLASSIC_NPC_IDENTITY_UNKNOWN', result.missing)

    def test_service_duplicate_routes_as_dialogue_not_empty_shop(self):
        town = self.town(TownConfig(candidate_npc_ids={70523}))
        entity, = town.register()
        result = self.click(town, entity)
        self.assertEqual(result.kind, 'dialogue')
        self.assertIsNone(result.shop_listing)
        self.assertEqual(result.dialogue['normal_action'], 'ladar1')
        self.assertEqual(result.dialogue['caotic_action'], 'ladarC1')
        self.assertEqual(result.dialogue['teleport_url'], '')
        self.assertIn('CLASSIC_MENU_RESOURCE_UNKNOWN', result.missing)
        self.assertIn('NPC_INPUT_DISPATCH_UNVERIFIED', result.missing)

    def test_teleport_and_other_services_are_decisions_only(self):
        town = self.town(TownConfig(candidate_npc_ids={50015, 60001, 70012, 80006},
                                    include_special=True))
        entities = town.register()
        decisions = {town.npc_for(e.uid).npc_id: self.click(town, e) for e in entities}
        self.assertEqual({npc: d.kind for npc, d in decisions.items()},
                         {50015: 'teleport', 60001: 'warehouse', 70012: 'inn', 80006: 'board'})
        self.assertEqual(decisions[50015].dialogue['normal_action'], 'teleisland1')
        self.assertIn('TELEPORT_DESTINATION_AND_COST_UNVERIFIED', decisions[50015].missing)
        self.assertEqual(decisions[70012].dialogue['caotic_action'], 'Inn1')
        self.assertTrue(all(d.classic_menu_stem is None for d in decisions.values()))

    def test_click_uses_live_uid_and_signed_low32(self):
        town = self.town(TownConfig(candidate_npc_ids={70523}), start=0x80000001)
        entity, = town.register()
        self.assertEqual(self.click(town, entity).ref, entity.ref)
        for target in (70523, 300, 87192):
            with self.assertRaisesRegex(TownError, '^TOWN_TARGET_NOT_CURRENT$'):
                town.route_click(target, player_map_id=0, player_x=entity.x,
                                 player_y=entity.y, max_distance=1)
        with self.assertRaisesRegex(TownError, '^DIALOG_TARGET_I32_REQUIRED$'):
            town.route_click(entity.uid, player_map_id=0, player_x=entity.x,
                             player_y=entity.y, max_distance=1)

    def test_lifetime_map_range_and_no_unrelated_npc_selection(self):
        town = self.town(TownConfig(candidate_npc_ids={70523}))
        entity, = town.register()
        for changes, code in (({'player_map_id': 1}, 'TOWN_TARGET_MAP_MISMATCH'),
                              ({'player_x': entity.x + 2}, 'TOWN_TARGET_OUT_OF_RANGE')):
            with self.assertRaisesRegex(TownError, '^' + code + '$'):
                self.click(town, entity, **changes)
        unrelated = town.entities.add(Kind.NPC, 0, entity.x, entity.y)
        self.assertNotIn(unrelated, town.present(0, entity.x, entity.y, 17))
        with self.assertRaisesRegex(TownError, '^TOWN_TARGET_NOT_CURRENT$'):
            self.click(town, unrelated)
        town.entities.kill(entity.uid)
        with self.assertRaisesRegex(TownError, '^TOWN_TARGET_NOT_CURRENT$'):
            self.click(town, entity)
        town.close()
        self.assertIsNone(town.entities.get(entity.uid))
        self.assertIs(town.entities.get(unrelated.uid), unrelated)

    def test_config_disable_and_close_keep_other_entities_and_burn_uids(self):
        config = TownConfig(candidate_npc_ids={70523})
        town = self.town(config)
        entity, = town.register()
        old_ref = entity.ref
        pc = town.entities.add(Kind.PC, 0, entity.x, entity.y)
        town.register(TownConfig(enable_candidates=True, disabled_npc_ids={70523}))
        self.assertIsNone(town.entities.resolve(old_ref))
        new_entity, = town.register(config)
        self.assertGreater(new_entity.uid, entity.uid)
        town.close()
        town.close()
        self.assertIs(town.entities.get(pc.uid), pc)
        self.assertEqual(len(town.entities), 1)
        self.assertEqual(town.present(0, pc.x, pc.y, 17), [])

    def test_imports_stay_outside_native_and_broker_graph(self):
        for name in ('broker', 'npc', 'world_visibility', 'session', 'inventory'):
            self.assertNotIn('tools.local_original_session.' + name, sys.modules)


if __name__ == '__main__':
    # The requested invocation ends with project-root '.', not a unittest name.
    unittest.main(argv=[sys.argv[0]], verbosity=2)
