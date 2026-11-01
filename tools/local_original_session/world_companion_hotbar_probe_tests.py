"""Registration regression for the promoted optional command feature."""
import unittest
from tools.local_original_session import world_registry,world_handlers
class HotbarProbeTests(unittest.TestCase):
    def test_registered_command_precedes_player_magic(self):
        registry=world_registry.build_registry(world_handlers.CORE_MODULES+world_handlers.FEATURE_MODULES)
        self.assertEqual(registry.frames[0x4ee6][0],'_hotbar_probe_frame')
        self.assertGreater(registry.hooks['after_enter'].index('_hotbar_probe_enter'),registry.hooks['after_enter'].index('_companion_enter'))
    def test_removal_keeps_core_registered(self):
        registry=world_registry.build_registry(world_handlers.CORE_MODULES+tuple(x for x in world_handlers.FEATURE_MODULES if x!='world_feature_companion_hotbar_probe'))
        self.assertNotIn('_hotbar_probe_frame',registry.methods)
        self.assertIn('_world_magic_frame',registry.frames[0x4ee6])
if __name__=='__main__':unittest.main()
