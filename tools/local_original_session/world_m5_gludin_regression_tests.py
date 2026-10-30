"""Development registration check for Gludin's LOCAL warehouse presentation."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import world_town as town
from tools.local_original_session import world_feature_m5 as m5
from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_terrain import WorldTerrain
from tools.local_original_session.world_shop_menu import ShopExperiment
from tools.local_original_session.world_town_services import load_town_services


class GludinWarehouseTests(unittest.TestCase):
    def test_m5_registration_exposes_karim_without_borrowing_native_identity(self):
        terrain = WorldTerrain.load(map_ids=(4,))
        entities = EntityRegistry()
        old = town.TownNpcs(entities, town.with_gludin_town(town.load_town()),
            town.TownConfig(), passable=terrain.can_stand)
        context = SimpleNamespace(_world_map_exp=2,
            world=SimpleNamespace(entities=entities, terrain=terrain))
        with patch.dict('os.environ', {'SL_EXPERIMENT_M5': '1'}):
            configured = m5._m5_town_setup(context, town.TownSetup(old,
                load_town_services(), (), ShopExperiment()))
        self.addCleanup(configured.town.close)
        entity, npc = next((entities.resolve(ref), npc)
            for ref, npc, _ in configured.town._owned.values()
            if npc.npc_id == 60007)
        appearance = configured.town.appearance(entity.uid)
        self.assertIsNone(appearance.catalog_template_id)
        self.assertEqual(appearance.sprite_id, 143)
        self.assertEqual((entity.map_id, entity.x, entity.y), (4, 32619, 32800))
        self.assertEqual((npc.spawn['reference_locx'], npc.spawn['reference_locy']),
            (32618, 32800))
        self.assertIs(terrain.can_stand(4, entity.x, entity.y), True)
        self.assertIs(terrain.can_stand(4, 32618, 32800), False)
        self.assertTrue(any(source.placement_key == npc.key
            and source.stem == 'storage' for source in configured.sources))


if __name__ == '__main__':
    unittest.main(verbosity=2)
